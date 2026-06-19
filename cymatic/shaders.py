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
uniform float u_m,  u_n;
uniform float u_m2, u_n2;
uniform float u_blend;
uniform float u_thresh;
uniform float u_bright;
uniform float u_phase;
uniform vec3  u_col;
out vec4 f;
const float PI = 3.14159265358979323846;
void main() {
    vec2 uv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
    float px = uv.x + sin(u_phase * 0.31) * 0.018;
    float py = uv.y + cos(u_phase * 0.23) * 0.018;

    // Interpolate mode numbers, not field values.
    // This is equivalent to sweeping the plate's driving frequency between two
    // resonances: the nodal lines deform continuously in place, just as sand
    // physically migrates to new rest positions during a frequency sweep.
    float mi = mix(u_m, u_m2, u_blend);
    float ni = mix(u_n, u_n2, u_blend);

    float v = cos(mi * PI * px) * cos(ni * PI * py)
            - cos(ni * PI * px) * cos(mi * PI * py);

    // Second harmonic ghost peaks mid-transition, adding extra structure
    // while the primary mode is in flux — collapses cleanly at blend=0 or 1
    float ghost = sin(u_blend * PI) * 0.25;
    float v2 = cos((mi + 1.0) * PI * px) * cos((ni + 1.0) * PI * py)
             - cos((ni + 1.0) * PI * px) * cos((mi + 1.0) * PI * py);
    v += ghost * v2;

    float d = abs(v);
    float line    = 1.0 - smoothstep(0.0,          u_thresh,        d);
    float glow    = 0.45 * (1.0 - smoothstep(0.0,  u_thresh * 4.5,  d));
    float ambient = 0.06 * (1.0 - smoothstep(0.0,  u_thresh * 18.0, d));
    float intensity = clamp(line + glow + ambient, 0.0, 1.0);
    f = vec4(u_col * intensity * u_bright, 1.0);
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
uniform int   u_mirror;
out vec4 f;
const float PI2 = 6.28318530718;
void main() {
    vec2 uv = (gl_FragCoord.xy / u_res - 0.5) / max(u_zoom, 0.1);
    float angle = atan(uv.y, uv.x) + u_rot;
    float r = length(uv);
    float slice = PI2 / float(max(u_segs, 2));
    angle = mod(angle, slice);
    if (angle < 0.0) angle += slice;
    if (u_mirror != 0) {
        float t = mod(angle / slice * 2.0, 2.0);
        if (t > 1.0) angle = slice - angle;
    }
    // Clamp to [0.01, 0.99] to avoid edge-sampling artefacts on the FBO texture
    vec2 newUV = clamp(vec2(r * cos(angle), r * sin(angle)) + 0.5, 0.01, 0.99);
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
