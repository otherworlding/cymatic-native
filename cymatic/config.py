"""Constants — modes, chakras, palettes."""

# Chladni modal-superposition bands.
# A real plate driven by a complex sound vibrates in EVERY resonant mode at
# once, each excited in proportion to the sound energy near that mode's
# resonant frequency.  The instantaneous surface is the weighted sum of those
# mode shapes; sand collects where the sum crosses zero.
#
# Sixteen bands span sub-bass→air so every instrument lands in its own mode.
# Spacing is mid-dense — the 165 Hz–2.2 kHz region where melody and harmony
# live gets the most bands for the finest pitch discrimination, while sub-bass
# and air are coarser.  Modes rise in complexity with frequency (f ∝ m²+n²),
# all use m≠n so each is a distinct figure.  Sixteen is near the legibility
# ceiling: more modes superpose into noise rather than geometry.
# NOTE: len(CHLADNI_BANDS) MUST equal N in the CHLADNI shader (shaders.py).
#   (m, n, lo_hz, hi_hz)
CHLADNI_BANDS = [
    (1, 2,    30,    55),   # sub-bass
    (1, 3,    55,    85),   # bass
    (2, 3,    85,   120),   # bass
    (1, 4,   120,   165),   # low-mid
    (3, 4,   165,   220),   # low-mid
    (2, 5,   220,   290),   # low-mid / vox
    (3, 5,   290,   380),   # mid
    (4, 5,   380,   500),   # mid
    (3, 6,   500,   660),   # mid / leads
    (4, 6,   660,   870),   # mid
    (5, 6,   870,  1150),   # upper-mid
    (4, 7,  1150,  1550),   # upper-mid
    (5, 7,  1550,  2200),   # presence
    (6, 7,  2200,  3300),   # presence
    (5, 8,  3300,  5500),   # brilliance
    (7, 8,  5500, 16000),   # air / cymbals
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

# Solfeggio frequencies (Hz) with their traditional chakra colours.  Unlike the
# CHAKRAS table (which spreads 7 colours across the whole audible spectrum for a
# lively visualiser), these are the literal Solfeggio tones — colour boundaries
# fall on the actual frequencies, so the mapping is "accurate" to the tradition.
#   (hz, (r, g, b), chakra)
SOLFEGGIO = [
    (396, (220,  30,  30), "Root"),        # UT  — liberating fear   — red
    (417, (240, 120,   0), "Sacral"),      # RE  — facilitating change — orange
    (528, (220, 210,   0), "Solar"),       # MI  — transformation    — yellow
    (639, (  0, 180,  60), "Heart"),       # FA  — connection        — green
    (741, ( 20, 130, 240), "Throat"),      # SOL — expression        — blue
    (852, ( 80,  20, 190), "Third Eye"),   # LA  — intuition         — indigo
    (963, (175,  55, 230), "Crown"),       # SI  — divine            — violet
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
