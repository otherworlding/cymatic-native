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
uniform float u_ca[6];     // cos(mix angle) — symmetric/antisymmetric blend
uniform float u_sa[6];     // sin(mix angle)
uniform float u_thresh;    // nodal line half-width (sand thickness)
uniform float u_bright;
uniform vec3  u_col;
out vec4 f;
const float PI = 3.14159265358979323846;

void main() {
    // Square plate domain x,y in [-1, 1]
    vec2 uv = gl_FragCoord.xy / u_res * 2.0 - 1.0;

    // Physical model: the plate's displacement is the weighted superposition
    // of every excited resonant mode.  The (m,n) and (n,m) modes are degenerate
    // (same resonant frequency), so the real plate vibrates in an arbitrary
    // linear combination of them:  phi = cos(a)*A + sin(a)*B.
    //   a = 135deg -> A-B  (antisymmetric: both diagonals are nodal -> an "X")
    //   a =  45deg -> A+B  (symmetric: diagonals are antinodes, no X)
    //   a =   0deg -> A     (a rectangular grid)
    // Letting each band's angle drift sweeps through the whole family of real
    // Chladni figures, so the diagonals are no longer permanently nodal.
    float W = 0.0;
    for (int k = 0; k < 6; k++) {
        float m = u_m[k];
        float n = u_n[k];
        float A = cos(m * PI * uv.x) * cos(n * PI * uv.y);
        float B = cos(n * PI * uv.x) * cos(m * PI * uv.y);
        float phi = u_ca[k] * A + u_sa[k] * B;
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

# ── Liquid light show ───────────────────────────────────────────────────────
# 1960s overhead-projector oil-and-water look: blobs of saturated dye that
# swell, drift, merge and split, with marbled veins where colours bleed.
# Built from domain-warped metaballs so the motion is organic and fluid.
LIQUID = """
#version 330
uniform vec2  u_res;
uniform float u_time;
uniform float u_bass;     // swells the blobs
uniform float u_mid;      // shifts colour flow
uniform float u_treble;   // fine marbled veins
uniform float u_level;    // overall backlight brightness
uniform float u_warp;     // turbulence amount
uniform vec3  u_pal[5];   // colour palette stops
out vec4 f;

vec3 palette(float t) {
    t = fract(t) * 5.0;            // cycle through the 5 stops
    int i = int(floor(t));
    float fr = t - float(i);
    return mix(u_pal[i % 5], u_pal[(i + 1) % 5], fr);
}

void main() {
    vec2 uv = gl_FragCoord.xy / u_res;
    vec2 p  = uv * 2.0 - 1.0;
    p.x    *= u_res.x / max(u_res.y, 1.0);   // aspect-correct
    float t = u_time;

    // ── Domain warp — three octaves of swirling flow (the "liquid") ──────
    float warp = 0.35 + u_warp * 0.65;
    vec2 q = p;
    q += warp        * vec2(sin(p.y * 2.5 + t * 0.60), cos(p.x * 2.5 - t * 0.50));
    q += warp * 0.50 * vec2(sin(q.y * 5.0 - t * 0.80), cos(q.x * 5.0 + t * 0.70));
    q += warp * 0.25 * vec2(sin(q.y * 9.0 + t * 1.10), cos(q.x * 9.0 - t * 0.90));

    // ── Metaball dye blobs — drift on slow Lissajous paths, swell on bass ─
    float field = 0.0;
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        vec2 c = 0.72 * vec2(sin(t * (0.18 + 0.05 * fi) + fi * 1.7),
                             cos(t * (0.15 + 0.04 * fi) + fi * 2.3));
        float r = 0.22 + 0.12 * sin(t * 0.4 + fi) + u_bass * 0.35;
        float d = length(q - c);
        field += (r * r) / (d * d + 0.03);
    }

    // ── Colour: flowing bands through the palette ────────────────────────
    float v   = field * 0.12 + t * 0.03 + u_mid * 0.5;
    vec3  col = palette(v);

    // Marbled veins where dye boundaries crowd; treble sharpens them
    float veins = sin(field * 3.0 + t + u_treble * 6.0);
    col += 0.14 * veins * veins;

    // Backlit translucency + sustained brightness
    col *= 0.42 + u_level * 1.5;

    // Soft pool-of-light vignette
    float vig = smoothstep(1.7, 0.2, length(p));
    col *= 0.55 + 0.45 * vig;

    f = vec4(col, 1.0);
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
