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
uniform float u_m[6];      // mode m numbers (one per frequency band)
uniform float u_n[6];      // mode n numbers
uniform float u_w[6];      // excitation weight per mode = live audio energy
uniform float u_thresh;    // nodal line half-width (sand thickness)
uniform float u_bright;
uniform vec3  u_col;
out vec4 f;
const float PI = 3.14159265358979323846;

void main() {
    // Square plate domain x,y in [-1, 1]
    vec2 uv = gl_FragCoord.xy / u_res * 2.0 - 1.0;

    // Physical model: the plate's displacement is the weighted superposition
    // of every excited resonant mode.  Each term is a TRUE integer Chladni
    // figure, so the geometry is always authentic; as the audio spectrum
    // shifts, the weights shift, and the combined nodal lines migrate exactly
    // like sand redistributing on a real driven plate.
    float W = 0.0;
    for (int k = 0; k < 6; k++) {
        float m = u_m[k];
        float n = u_n[k];
        float phi = cos(m * PI * uv.x) * cos(n * PI * uv.y)
                  - cos(n * PI * uv.x) * cos(m * PI * uv.y);
        W += u_w[k] * phi;
    }

    // Sand collects where the surface is motionless: |W| ~ 0 (the nodal set)
    float d = abs(W);
    float line = 1.0 - smoothstep(0.0, u_thresh,        d);   // crisp sand line
    float halo = 0.28 * (1.0 - smoothstep(0.0, u_thresh * 3.0, d)); // tight glow
    float intensity = clamp(line + halo, 0.0, 1.0);

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
