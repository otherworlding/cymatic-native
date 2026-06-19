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
uniform float u_m[16];     // mode m numbers (one per frequency band)
uniform float u_n[16];     // mode n numbers
uniform float u_w[16];     // excitation weight per mode = live audio energy
uniform float u_ca[16];    // cos(mix angle) — symmetric/antisymmetric blend
uniform float u_sa[16];    // sin(mix angle)
uniform float u_thresh;    // nodal line half-width (sand thickness)
uniform float u_bright;
uniform vec3  u_col;
uniform int   u_chakra;    // 0 = single-colour summed field, 1 = per-mode chakra
uniform vec3  u_mcol[16];  // per-mode chakra colour (by band frequency)
out vec4 f;
const int   N  = 16;       // must match len(config.CHLADNI_BANDS)
const float PI = 3.14159265358979323846;

void main() {
    // Square plate domain x,y in [-1, 1]
    vec2 uv = gl_FragCoord.xy / u_res * 2.0 - 1.0;

    if (u_chakra == 1) {
        // Chakra mode: each frequency band draws ITS OWN nodal lines in the
        // chakra colour for that frequency, and the line's brightness AND width
        // scale with how active that band is — so you read the spectrum
        // directly as coloured sand: red bass figures, violet cymbal grids,
        // each glowing in proportion to how much of that range is sounding.
        vec3 c = vec3(0.0);
        for (int k = 0; k < N; k++) {
            float A = cos(u_m[k] * PI * uv.x) * cos(u_n[k] * PI * uv.y);
            float B = cos(u_n[k] * PI * uv.x) * cos(u_m[k] * PI * uv.y);
            float phi = u_ca[k] * A + u_sa[k] * B;
            float d  = abs(phi);
            float wk = u_w[k];                          // band activity (0..1)
            float tw = u_thresh * (0.5 + 3.0 * wk);     // width grows with energy
            float line = 1.0 - smoothstep(0.0, tw,        d);
            float glow = 0.3 * (1.0 - smoothstep(0.0, tw * 3.0, d));
            c += u_mcol[k] * (line + glow) * (0.25 + 4.0 * wk);
        }
        f = vec4(c * u_bright, 1.0);
        return;
    }

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
    for (int k = 0; k < N; k++) {
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

// value noise + fractal Brownian motion — the organic "liquid" texture
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}
float vnoise(vec2 p) {
    vec2 i = floor(p), fp = fract(p);
    vec2 u = fp * fp * (3.0 - 2.0 * fp);
    float a = hash(i),            b = hash(i + vec2(1, 0));
    float c = hash(i + vec2(0,1)), d = hash(i + vec2(1, 1));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
float fbm(vec2 p) {
    float s = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++) { s += a * vnoise(p); p = p * 2.02 + 7.1; a *= 0.5; }
    return s;
}

void main() {
    vec2 uv = gl_FragCoord.xy / u_res;
    vec2 p  = uv * 2.0 - 1.0;
    p.x    *= u_res.x / max(u_res.y, 1.0);   // aspect-correct
    float t = u_time;

    // ── Iterated domain warp (IQ-style fbm-of-fbm): churning, marbled flow ──
    // Each layer advects the next, so the dye folds into itself like real oil
    // on water.  Global turbulence is smooth (continuous energy via u_warp);
    // bass mostly swells the blobs (below) rather than lurching the whole field.
    float turb = 0.9 + u_warp * 2.0 + u_bass * 0.5;
    vec2 q = vec2(fbm(p + vec2(0.0, t * 0.25)),
                  fbm(p + vec2(5.2, 1.3) - t * 0.21));
    vec2 r = vec2(fbm(p + turb * q + vec2(1.7, 9.2) + t * 0.18),
                  fbm(p + turb * q + vec2(8.3, 2.8) - t * 0.16));
    vec2 flow = p + turb * 0.6 * r;          // advected coordinate

    // ── Metaball dye blobs — more of them, faster, erratic, bass-driven ────
    float field = 0.0;
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        // erratic paths: two incommensurate sinusoids per axis
        vec2 c = vec2(sin(t * (0.33 + 0.07 * fi) + fi * 1.7) * 0.6
                    + sin(t * (0.11 + 0.03 * fi) + fi) * 0.3,
                      cos(t * (0.29 + 0.06 * fi) + fi * 2.3) * 0.6
                    + cos(t * (0.13 + 0.04 * fi) + fi) * 0.3);
        // blobs swell on bass and pulse individually
        float r0 = 0.18 + 0.10 * sin(t * 0.7 + fi * 2.0) + u_bass * 0.55;
        float d  = length(flow - c);
        field += (r0 * r0) / (d * d + 0.02);
    }

    // ── Colour: dye bands flow through the palette, marbled by the fbm ─────
    float marble = fbm(flow * 1.5 + t * 0.1);
    float v   = field * 0.10 + marble * 0.6 + t * 0.04 + u_mid * 0.6;
    vec3  col = palette(v);

    // Bleed a second palette tap for richer oil-slick colour mixing
    col = mix(col, palette(v + 0.35 + marble), 0.35);

    // Sharp marbled veins where dye fronts collide; treble crisps them
    float veins = sin((field + marble * 4.0) * 3.0 + t + u_treble * 8.0);
    col += 0.18 * veins * veins;

    // Backlit translucency + sustained brightness.  No beat/warp term here so
    // transients pulse the BLOBS (local) rather than flashing the whole frame.
    col *= 0.42 + u_level * 1.5;

    // Soft pool-of-light vignette
    float vig = smoothstep(1.8, 0.15, length(p));
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
