"""GLSL shader sources."""

VERT = """
#version 330
in vec2 in_vert;
void main() { gl_Position = vec4(in_vert, 0.0, 1.0); }
"""

# ── Chladni plate ──────────────────────────────────────────────────────────────
# Formula: cos(m·π·x)·cos(n·π·y) − cos(n·π·x)·cos(m·π·y)  with x,y ∈ [−1,1]
# Nodal lines are where |result| < threshold.  Integers m,n ONLY.
CHLADNI = """
#version 330
uniform vec2  u_res;
uniform float u_m, u_n, u_m2, u_n2, u_blend;
uniform float u_thresh, u_bright;
uniform vec3  u_col;
out vec4 f;
const float PI = 3.14159265358979323846;
void main() {
    vec2 uv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
    float v1 = cos(u_m  * PI * uv.x) * cos(u_n  * PI * uv.y)
             - cos(u_n  * PI * uv.x) * cos(u_m  * PI * uv.y);
    float v2 = cos(u_m2 * PI * uv.x) * cos(u_n2 * PI * uv.y)
             - cos(u_n2 * PI * uv.x) * cos(u_m2 * PI * uv.y);
    float v  = mix(v1, v2, clamp(u_blend, 0.0, 1.0));
    float t  = pow(max(0.0, 1.0 - abs(v) / u_thresh), 2.0);
    f = vec4(u_col * t * u_bright, 1.0);
}
"""

# ── Wave rings ──────────────────────────────────────────────────────────────
# 7 point sources (one per chakra band) emitting radial sine waves.
RINGS = """
#version 330
uniform vec2  u_res;
uniform vec2  u_src[7];
uniform float u_amp[7], u_wl[7];
uniform vec3  u_scol[7];
uniform float u_time;
out vec4 f;
void main() {
    vec2 uv = gl_FragCoord.xy / u_res;
    float sum = 0.0, wt = 0.0;
    vec3 col = vec3(0.0);
    for (int i = 0; i < 7; i++) {
        float d = length(uv - u_src[i]);
        float w = sin(6.28318 * d / max(u_wl[i], 0.001) - u_time);
        sum += u_amp[i] * w;
        col += u_scol[i] * u_amp[i];
        wt  += u_amp[i];
    }
    float norm = wt > 0.001 ? (sum / wt + 1.0) * 0.5 : 0.5;
    if (wt > 0.001) col /= wt;
    f = vec4(col * norm, 1.0);
}
"""

# ── Kaleidoscope post-process ───────────────────────────────────────────────
KALEI = """
#version 330
uniform sampler2D u_tex;
uniform vec2  u_res;
uniform int   u_segs;
uniform float u_rot, u_zoom;
uniform bool  u_mirror;
out vec4 f;
const float PI2 = 6.28318530718;
void main() {
    vec2 uv = (gl_FragCoord.xy / u_res - 0.5) / max(u_zoom, 0.1);
    float angle = atan(uv.y, uv.x) + u_rot;
    float r = length(uv);
    float slice = PI2 / float(u_segs);
    angle = mod(angle, slice);
    if (angle < 0.0) angle += slice;
    if (u_mirror) {
        float t = mod(angle / slice * 2.0, 2.0);
        if (t > 1.0) angle = slice - angle;
    }
    vec2 newUV = vec2(r * cos(angle), r * sin(angle)) + 0.5;
    f = texture(u_tex, newUV);
}
"""

# ── Passthrough blit ───────────────────────────────────────────────────────
PASS = """
#version 330
uniform sampler2D u_tex;
uniform vec2 u_res;
out vec4 f;
void main() { f = texture(u_tex, gl_FragCoord.xy / u_res); }
"""
