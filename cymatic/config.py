"""Constants — modes, chakras, palettes."""

# Chladni mode pairs (m, n) sorted by m²+n² — matches how a real square plate
# resonates: lower frequencies excite simple low-order modes, higher frequencies
# excite complex high-order modes.  Every pair here produces a visually distinct
# figure; adjacent entries were chosen to maximise geometric contrast.
MODES = sorted([
    (1,2),(2,1),(1,3),(3,1),
    (2,3),(3,2),(2,4),(4,2),(1,4),(4,1),
    (3,4),(4,3),(2,5),(5,2),(1,5),(5,1),
    (3,5),(5,3),(4,5),(5,4),(2,6),(6,2),
    (1,6),(6,1),(3,6),(6,3),(4,6),(6,4),
    (5,6),(6,5),(2,7),(7,2),(3,7),(7,3),
    (4,7),(7,4),(5,7),(7,5),(1,7),(7,1),
    (6,7),(7,6),(3,8),(8,3),(5,8),(8,5),
    (4,8),(8,4),(6,8),(8,6),(7,8),(8,7),
    (5,9),(9,5),(6,9),(9,6),(7,9),(9,7),(8,9),(9,8),
], key=lambda mn: mn[0]**2 + mn[1]**2)

# Chladni modal-superposition bands.
# A real plate driven by a complex sound vibrates in EVERY resonant mode at
# once, each excited in proportion to the sound energy near that mode's
# resonant frequency.  The instantaneous surface is the weighted sum of those
# mode shapes; sand collects where the sum crosses zero.
#
# Ten log-spaced bands span sub-bass→air so every instrument lands in its own
# mode: kick/bass in the simple low figures, vocals and leads in the mid
# lattices, cymbals and air in the fine grids.  Modes rise in complexity with
# frequency (f ∝ m²+n²), and all use m≠n so each is a distinct figure.
#   (m, n, lo_hz, hi_hz)
CHLADNI_BANDS = [
    (1, 2,    30,    70),   # sub-bass        → simple bar
    (2, 3,    70,   130),   # bass            → 2x3 lattice
    (3, 4,   130,   220),   # low-mid         → diagonal weave
    (2, 5,   220,   350),   # low-mid / vox   → 2x5 ladder
    (4, 5,   350,   550),   # midrange        → dense lattice
    (3, 6,   550,   850),   # mid / leads     → 3x6 weave
    (5, 6,   850,  1400),   # upper-mid       → fine lattice
    (4, 7,  1400,  2400),   # presence        → complex weave
    (6, 7,  2400,  4500),   # brilliance      → fine grid
    (7, 8,  4500, 16000),   # air / cymbals   → very fine grid
]

CHAKRAS = [
    ("Root",     (220, 30,  30),  20,    120  ),
    ("Sacral",   (240, 120,  0),  120,   300  ),
    ("Solar",    (220, 210,  0),  300,   700  ),
    ("Heart",    (  0, 180, 60),  700,   1400 ),
    ("Throat",   ( 20, 130,240),  1400,  3000 ),
    ("3rd Eye",  ( 80,  20,190),  3000,  6000 ),
    ("Crown",    (175,  55,230),  6000,  20000),
]

PALETTES = {
    "Plasma": [(10,0,50),(85,0,145),(215,0,100),(255,80,0),(255,225,50)],
    "Neon":   [(0,0,8),(0,230,195),(110,0,255),(255,0,155),(215,255,0)],
    "Fire":   [(0,0,0),(85,0,0),(205,35,0),(255,145,0),(255,255,95)],
    "Ocean":  [(0,0,18),(0,28,85),(0,105,175),(0,205,205),(195,240,255)],
    "Mono":   [(0,0,0),(20,20,20),(65,65,65),(150,150,150),(255,255,255)],
    "Auric":  [(5,0,25),(60,0,80),(130,10,30),(200,120,0),(255,240,120)],
}
PALETTE_NAMES = list(PALETTES.keys())

FFT_SIZE    = 4096
SAMPLE_RATE = 44100
