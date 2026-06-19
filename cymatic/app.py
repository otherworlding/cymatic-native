"""Main application — window, loop, patterns, UI."""

import math
from pathlib import Path

import numpy as np
import pygame
import moderngl

from .config import MODES, CHAKRAS, PALETTES, PALETTE_NAMES, FFT_SIZE, SAMPLE_RATE
from .audio import AudioEngine, AUDIO_OK
from .renderer import Renderer
from .system_audio import find_blackhole, open_download_page, open_audio_midi_setup


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient(stops, t):
    t = max(0.0, min(1.0, t))
    s = (len(stops) - 1) * t
    i = min(len(stops) - 2, int(s))
    return _lerp(stops[i], stops[i + 1], s - i)


def _rand_pal():
    rng = np.random.default_rng()
    return [tuple(int(x) for x in rng.integers(0, 256, 3)) for _ in range(5)]


class App:
    WIN_W, WIN_H = 1280, 800

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Cymatic Visualizer")

        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK,
                                        pygame.GL_CONTEXT_PROFILE_CORE)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 2)

        flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
        self.win = pygame.display.set_mode((self.WIN_W, self.WIN_H), flags)

        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        self.rdr = Renderer(self.ctx)
        self.rdr.resize(self.WIN_W, self.WIN_H)

        # Audio
        self.audio    = AudioEngine()
        self.fft      = np.zeros(FFT_SIZE // 2 + 1)
        self.devices  = AudioEngine.list_devices()

        # Setup guide overlay (shown when SYSTEM AUDIO clicked and BlackHole not installed)
        self.show_setup_guide = False
        self._guide_bh_found  = False

        # Beat state
        self.beat_flash = 0.0
        self.e_avg = self.k_avg = 0.0
        self.on_beat = False

        # Chladni state
        self.mode_idx      = 2    # current mode index into MODES
        self.mode_hold     = 0    # frames remaining before mode can switch again
        self.mode_target   = 2    # target mode we're moving toward
        self.mode_stable   = 0    # frames target has stayed the same

        # Lissajous state
        self.liss_a     = 3.0
        self.liss_b     = 2.0
        self.liss_trail = []
        self.liss_surf  = None
        self.liss_tex   = None

        # Settings dict
        self.S = dict(
            pattern='chladni', color_mode='palette', palette_idx=0,
            kaleidoscope=False, mirror=True,
            segments=8, spin_speed=0.0005, zoom=1.0,
            sensitivity=8.0, thresh=6.0,
            rot=0.0, t=0.0,
            src=None,      # 'mic' | 'file'
        )
        self.random_pal = _rand_pal()

        # UI
        self.show_panel  = True
        self.show_picker = True
        self.status_msg  = "Select an audio device to start"
        self.font        = pygame.font.SysFont('helvetica', 13)
        self.font_sm     = pygame.font.SysFont('helvetica', 11)
        self.ui_surf     = None

        # UI interaction maps (populated by _draw_panel)
        self.btns      = {}   # name → screen Rect
        self.bars      = {}   # key  → (screen_x, screen_y, width, lo, hi)
        self.dev_rects = []   # [(Rect, device_idx), ...]
        self.dragging  = None

        self.clock   = pygame.time.Clock()
        self.running = True

        # Start default mic so audio is ready immediately
        self.audio.start_mic()

    # ══════════════════════════════════════════════════════════════════════════
    # Color
    # ══════════════════════════════════════════════════════════════════════════

    def _color(self, t: float, band: int = 0):
        cm = self.S['color_mode']
        if cm == 'chakra':
            r, g, b = CHAKRAS[min(band, 6)][1]
            f = max(0.0, min(1.0, 0.1 + 0.9 * t))
            return (r * f / 255, g * f / 255, b * f / 255)
        stops = self.random_pal if cm == 'random' else PALETTES[PALETTE_NAMES[self.S['palette_idx']]]
        c = _gradient(stops, t)
        return (c[0] / 255, c[1] / 255, c[2] / 255)

    # ══════════════════════════════════════════════════════════════════════════
    # Audio helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _be(self, lo, hi):
        return self.audio.band(self.fft, lo, hi) * self.S['sensitivity'] / 8

    def _energies(self):
        return [self._be(c[2], c[3]) for c in CHAKRAS]

    def _dom_band(self, e):
        return max(range(len(e)), key=lambda i: e[i]) if e else 0

    def _beat(self):
        e = self._be(20, 20000)
        k = self._be(40, 150)
        self.e_avg = self.e_avg * 0.90 + e * 0.10
        self.k_avg = self.k_avg * 0.90 + k * 0.10
        sp = e / max(0.002, self.e_avg)
        ks = k / max(0.001, self.k_avg)
        self.on_beat = sp > 1.5 or ks > 1.9
        if self.on_beat:
            self.beat_flash = 1.0
        self.beat_flash *= 0.70

    def _hz_to_mode(self, hz):
        """Map a frequency to the mode index whose m²+n² best matches.
        Real square plates resonate at f ∝ m²+n², so this is physically accurate."""
        hz = max(50, min(10000, hz))
        # Scale so that 50 Hz → complexity 2, 10 kHz → complexity ~200
        target = 2.0 + (math.log2(hz / 50) / math.log2(200)) * (9**2 + 8**2 - 2)
        best, best_d = 0, float('inf')
        for i, (m, n) in enumerate(MODES):
            d = abs(m*m + n*n - target)
            if d < best_d:
                best_d, best = d, i
        return best

    # ══════════════════════════════════════════════════════════════════════════
    # Patterns
    # ══════════════════════════════════════════════════════════════════════════

    def _draw_chladni(self, w, h, energies):
        vol = self._be(20, 20000)

        # ── Mode selection (physics-based) ────────────────────────────────────
        if vol > 0.008:
            dom = self.audio.dominant_hz(self.fft)
            tgt = self._hz_to_mode(dom)

            # Track how long the target has been stable
            if tgt == self.mode_target:
                self.mode_stable += 1
            else:
                self.mode_target  = tgt
                self.mode_stable  = 0

            # Switch rules:
            # • On a beat: switch immediately to the target
            # • Target stable for 6+ frames and current hold expired: switch
            # • Jump of 4+ modes: switch immediately (dramatic frequency shift)
            jump = abs(tgt - self.mode_idx)
            if self.mode_hold > 0:
                self.mode_hold -= 1
            can_switch = self.mode_hold == 0

            if can_switch and (
                self.on_beat or
                self.mode_stable >= 6 or
                jump >= 4
            ):
                self.mode_idx  = tgt
                self.mode_hold = 4   # hold at least 4 frames before next change

        m, n = MODES[self.mode_idx]

        # ── Visual parameters ─────────────────────────────────────────────────
        # Threshold: keep it tight. "Line Width" slider 1-20 maps to 0.012-0.055.
        base_thresh = 0.012 + (self.S['thresh'] - 1) / 19 * 0.043
        # Beat widens lines briefly so they flash visible
        thresh = base_thresh + self.beat_flash * 0.025

        # Brightness: quiet = dim, loud = bright, beat = flash
        bright = 0.25 + vol * 2.8 + self.beat_flash * 1.8
        bright = min(2.8, bright)

        # Glow widens on beats (1 = no extra glow, 4 = wide halo)
        glow = 1.8 + self.beat_flash * 2.2

        col = self._color(min(1.0, 0.2 + vol * 2.0), self._dom_band(energies))

        self.rdr.chladni(w, h, m, n, thresh, bright, glow, col)

    def _draw_rings(self, w, h, energies):
        vol = self._be(20, 20000)
        bb  = 1 + self.beat_flash * 4
        t   = self.S['t'] * (0.014 + vol * 0.05 + self.beat_flash * 0.08)

        srcs, amps, wls, cols = [], [], [], []
        for i, (_, color, lo, hi) in enumerate(CHAKRAS):
            angle = (i / 7) * 2 * math.pi - math.pi / 2
            srcs.append((0.5 + 0.22 * math.cos(angle),
                         0.5 + 0.22 * math.sin(angle)))
            a = self._be(lo, hi) * bb
            amps.append(a)
            wls.append(max(0.01, min(0.2, 60 / max(1, (lo + hi) / 2))))
            if self.S['color_mode'] == 'chakra':
                cols.append(tuple(c / 255 for c in color))
            else:
                cols.append(self._color(a, i))

        self.rdr.rings(w, h, srcs, amps, wls, cols, t)

    def _draw_lissajous(self, w, h, energies):
        # Lazy-init surface
        if self.liss_surf is None or self.liss_surf.get_size() != (w, h):
            self.liss_surf = pygame.Surface((w, h))
            self.liss_surf.fill((0, 0, 0))
            self.liss_trail.clear()

        # Fade
        vol   = self._be(20, 20000)
        fade  = max(0.85, 0.96 - self.beat_flash * 0.25)
        arr   = pygame.surfarray.pixels3d(self.liss_surf)
        arr[:] = (arr * fade).astype(np.uint8)
        del arr

        # Update a:b ratio from spectral peaks
        pks = self.audio.top_peaks(self.fft, 2)
        if len(pks) >= 2:
            ratio = pks[0][0] / max(1, pks[1][0])
            tA    = round(min(9, max(1, ratio if ratio >= 1 else 1 / ratio)))
            self.liss_a += (tA - self.liss_a) * 0.04

        cx, cy   = w // 2, h // 2
        radius   = min(cx, cy) * 0.84 * min(1.0, 0.15 + vol * 2.2 + self.beat_flash * 0.6)
        speed    = 0.009 + vol * 0.03 + self.beat_flash * 0.015
        t        = self.S['t']
        px       = cx + radius * math.sin(self.liss_a * t * speed)
        py       = cy + radius * math.cos(self.liss_b * t * speed)
        band     = self._dom_band(energies)

        self.liss_trail.append({'x': px, 'y': py, 'b': band, 'fl': self.beat_flash})
        if len(self.liss_trail) > 6000:
            self.liss_trail.pop(0)

        if len(self.liss_trail) >= 2:
            step = max(1, len(self.liss_trail) // 1200)
            for i in range(step, len(self.liss_trail), step):
                p0, p1 = self.liss_trail[i - step], self.liss_trail[i]
                tf  = i / len(self.liss_trail)
                c   = self._color(tf, p1['b'])
                fl  = p1['fl']
                lw  = max(1, int(0.5 + tf * 2 + fl * 3.5))
                rgb = (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))
                pygame.draw.line(self.liss_surf, rgb,
                                 (int(p0['x']), int(p0['y'])),
                                 (int(p1['x']), int(p1['y'])), lw)

        # Upload surface as texture
        if self.liss_tex:
            self.liss_tex.release()
        raw = pygame.image.tostring(self.liss_surf, 'RGB', True)
        self.liss_tex = self.ctx.texture((w, h), 3, raw)
        self.liss_tex.filter = moderngl.LINEAR, moderngl.LINEAR
        self.rdr.blit(self.liss_tex, w, h)

    # ══════════════════════════════════════════════════════════════════════════
    # UI drawing
    # ══════════════════════════════════════════════════════════════════════════

    PANEL_H = 180

    def _draw_ui(self, w, h):
        if self.ui_surf is None or self.ui_surf.get_size() != (w, h):
            self.ui_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        self.ui_surf.fill((0, 0, 0, 0))

        if self.show_picker:
            self._draw_picker(w, h)
            return

        if self.show_setup_guide:
            self._draw_setup_guide(w, h)
            return

        if not self.show_panel:
            hint = self.font_sm.render(
                "H = controls   F = fullscreen   K = kaleidoscope",
                True, (55, 55, 75))
            self.ui_surf.blit(hint, (w // 2 - hint.get_width() // 2, h - 16))
            return

        PH = self.PANEL_H
        panel = pygame.Surface((w, PH), pygame.SRCALPHA)
        panel.fill((5, 5, 14, 220))

        self.btns = {}
        self.bars = {}

        # ── helper closures ────────────────────────────────────────────────

        def btn(label, active, bx, by, bw=90, bh=22, dim=False):
            fc = (38, 22, 210) if active else (14, 14, 28)
            bc = (80, 60, 255) if active else (34, 34, 54)
            tc = (255, 255, 255) if active else (65, 65, 80) if dim else (110, 110, 135)
            pygame.draw.rect(panel, fc, (bx, by, bw, bh), border_radius=4)
            pygame.draw.rect(panel, bc, (bx, by, bw, bh), 1, border_radius=4)
            lbl = self.font_sm.render(label, True, tc)
            panel.blit(lbl, (bx + bw // 2 - lbl.get_width() // 2,
                              by + bh // 2 - lbl.get_height() // 2))
            return pygame.Rect(bx, h - PH + by, bw, bh)

        def sldr(label, key, val, lo, hi, sx, sy, sw=125):
            lbl = self.font_sm.render(label, True, (65, 65, 88))
            panel.blit(lbl, (sx, sy + 5))
            bx, by = sx + 82, sy + 9
            pygame.draw.rect(panel, (22, 22, 42), (bx, by, sw, 4), border_radius=2)
            t  = max(0.0, min(1.0, (val - lo) / (hi - lo)))
            kx = int(bx + t * sw)
            pygame.draw.rect(panel, (28, 22, 68), (bx, by, int(t * sw), 4), border_radius=2)
            pygame.draw.circle(panel, (96, 80, 255), (kx, by + 2), 6)
            # Store screen-space bar rect for dragging
            self.bars[key] = (bx, h - PH + by - 7, sw, lo, hi)

        def row_lbl(text, sx, sy):
            l = self.font_sm.render(text, True, (55, 55, 78))
            panel.blit(l, (sx, sy + 5))

        # ── Row 1 : Audio source ───────────────────────────────────────────
        x, y = 10, 10
        row_lbl("SOURCE", x, y)
        self.btns['mic']    = btn("MIC / LINE IN",  self.S['src'] == 'mic',    x + 65,  y, 108)
        self.btns['system'] = btn("SYSTEM AUDIO",   self.S['src'] == 'system', x + 178, y, 105)
        self.btns['file']   = btn("OPEN FILE",       self.S['src'] == 'file',   x + 288, y, 85)
        self.btns['midi']   = btn("Audio MIDI Setup", False,                    x + 378, y, 122)

        st = self.font_sm.render(self.status_msg, True, (55, 55, 78))
        panel.blit(st, (w - st.get_width() - 10, y + 5))

        # ── Row 2 : Pattern ────────────────────────────────────────────────
        y += 34
        row_lbl("PATTERN", x, y)
        self.btns['chladni'] = btn("Chladni",   self.S['pattern'] == 'chladni',   x + 65,  y, 78)
        self.btns['rings']   = btn("Rings",     self.S['pattern'] == 'rings',     x + 148, y, 62)
        self.btns['liss']    = btn("Lissajous", self.S['pattern'] == 'lissajous', x + 215, y, 80)

        # Mode indicator
        if self.S['pattern'] == 'chladni':
            m, n = MODES[self.mode_idx]
            ml = self.font_sm.render(f"mode ({m},{n})", True, (38, 38, 58))
            panel.blit(ml, (x + 305, y + 5))

        # ── Row 2b : Color ─────────────────────────────────────────────────
        cx2 = x + 430
        row_lbl("COLOR", cx2, y)
        self.btns['pal'] = btn("Palette", self.S['color_mode'] == 'palette', cx2 + 52, y, 65)
        self.btns['rnd'] = btn("Random",  self.S['color_mode'] == 'random',  cx2 + 122, y, 65)
        self.btns['chk'] = btn("Chakra",  self.S['color_mode'] == 'chakra',  cx2 + 192, y, 65)
        pname = PALETTE_NAMES[self.S['palette_idx']]
        self.btns['pcyc'] = btn(f"< {pname} >", False, cx2 + 264, y, 90)

        # ── Row 3 : Main sliders ───────────────────────────────────────────
        y += 34
        sldr("SENSITIVITY", 'sensitivity', self.S['sensitivity'], 1, 20, x, y)
        sldr("LINE WIDTH",  'thresh',      self.S['thresh'],      1, 20, x + 240, y)

        # ── Row 4 : Kaleidoscope ───────────────────────────────────────────
        y += 34
        row_lbl("KALEIDO", x, y)
        self.btns['kalei']  = btn("ON" if self.S['kaleidoscope'] else "OFF",
                                  self.S['kaleidoscope'], x + 65, y, 50)
        self.btns['mirror'] = btn("MIRROR", self.S['mirror'],      x + 120, y, 65)
        sldr("SEGMENTS",   'segments',   self.S['segments'],          2,   32,  x + 200, y, 115)
        sldr("SPIN",       'spin_speed', self.S['spin_speed'] * 40000, 0,  200, x + 445, y, 115)
        sldr("ZOOM",       'zoom',       self.S['zoom'] * 100,        30, 350,  x + 690, y, 115)

        # Help line
        hl = self.font_sm.render(
            "H=hide panel   F=fullscreen   K=kaleidoscope   drag files to play",
            True, (38, 38, 55))
        panel.blit(hl, (w // 2 - hl.get_width() // 2, PH - 14))

        self.ui_surf.blit(panel, (0, h - PH))

    def _draw_picker(self, w, h):
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 10, 210))
        self.ui_surf.blit(ov, (0, 0))

        title = self.font.render("Select Audio Input Device", True, (180, 180, 210))
        self.ui_surf.blit(title, (w // 2 - title.get_width() // 2, h // 2 - 195))

        hint = self.font_sm.render(
            "For Apple Music / system audio: install BlackHole (free) and select it here, "
            "or drag an audio file onto the window.",
            True, (75, 75, 105))
        self.ui_surf.blit(hint, (w // 2 - hint.get_width() // 2, h // 2 - 165))

        self.dev_rects = []
        for i, (idx, name) in enumerate(self.devices):
            r = pygame.Rect(w // 2 - 290, h // 2 - 125 + i * 30, 580, 25)
            pygame.draw.rect(self.ui_surf, (18, 18, 38), r, border_radius=4)
            pygame.draw.rect(self.ui_surf, (38, 38, 65), r, 1, border_radius=4)
            lbl = self.font_sm.render(f"  {idx}: {name}", True, (180, 180, 210))
            self.ui_surf.blit(lbl, (r.x + 8, r.y + 5))
            self.dev_rects.append((r, idx))

        skip = self.font_sm.render("ENTER or ESC — use default device", True, (50, 50, 72))
        self.ui_surf.blit(skip, (w // 2 - skip.get_width() // 2, h // 2 + 130))

    def _draw_setup_guide(self, w, h):
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        ov.fill((0, 0, 10, 215))
        self.ui_surf.blit(ov, (0, 0))

        def txt(msg, y, color=(170, 170, 200), big=False):
            f   = self.font if big else self.font_sm
            lbl = f.render(msg, True, color)
            self.ui_surf.blit(lbl, (w // 2 - lbl.get_width() // 2, y))
            return lbl.get_height()

        def box_btn(label, bx, by, bw=220, bh=28, highlight=False):
            fc = (38, 22, 210) if highlight else (28, 22, 100)
            bc = (140, 120, 255) if highlight else (80, 60, 255)
            r  = pygame.Rect(bx, by, bw, bh)
            pygame.draw.rect(self.ui_surf, fc, r, border_radius=5)
            pygame.draw.rect(self.ui_surf, bc, r, 1, border_radius=5)
            lbl = self.font_sm.render(label, True, (220, 210, 255) if highlight else (200, 190, 255))
            self.ui_surf.blit(lbl, (bx + bw // 2 - lbl.get_width() // 2,
                                    by + bh // 2 - lbl.get_height() // 2))
            return r

        cx = w // 2
        y  = h // 2 - 200

        txt("System Audio Setup  —  one-time, 5 minutes", y, (210, 200, 255), big=True); y += 34

        bh_installed = getattr(self, '_guide_bh_found', False)
        if bh_installed:
            txt("BlackHole found!  Now complete the routing step below.", y, (80, 220, 120)); y += 28
        else:
            txt("BlackHole is a free virtual driver that routes Mac audio into the visualizer.", y, (115, 115, 155)); y += 24

        steps = [
            ("1", "Download  BlackHole 2ch  (free) and install the .pkg",
             not bh_installed, "(already installed)" if bh_installed else ""),
            ("2", "Open Audio MIDI Setup  (button below)",   False, ""),
            ("3", "Click  +  at bottom-left  →  Create Multi-Output Device", False, ""),
            ("4", "Tick  BlackHole 2ch  AND  your speakers / headphones", False, ""),
            ("5", "Right-click the new Multi-Output Device  →  Use This Device For Sound Output", False, ""),
            ("6", "Click  Done — BlackHole is set up  below  to finish", False, ""),
        ]
        y += 8
        for num, desc, bold, note in steps:
            color  = (200, 200, 230) if bold else (130, 130, 160)
            prefix = f"  {num}.  "
            line   = prefix + desc + (f"  {note}" if note else "")
            txt(line, y, color); y += 21
        y += 16

        # Row 1 — download + midi setup
        self.btns['bh_download'] = box_btn("Download BlackHole  (free)",  cx - 252, y, 235, highlight=not bh_installed)
        self.btns['bh_midi']     = box_btn("Open Audio MIDI Setup",        cx + 18,  y, 200)
        y += 42

        # Row 2 — check again + close
        self.btns['bh_check'] = box_btn("Done — BlackHole is set up", cx - 252, y, 235, highlight=True)
        self.btns['bh_close'] = box_btn("Cancel  (ESC)",               cx + 18,  y, 200)

    # ══════════════════════════════════════════════════════════════════════════
    # Event handling
    # ══════════════════════════════════════════════════════════════════════════

    def _events(self, w, h):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False

            elif ev.type == pygame.VIDEORESIZE:
                self.win = pygame.display.set_mode(
                    ev.size, pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)
                self.rdr.resize(*ev.size)
                self.liss_surf = None
                self.ui_surf   = None

            elif ev.type == pygame.KEYDOWN:
                self._key(ev.key)

            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1:
                    self._click(*ev.pos, w, h)
                elif ev.button == 4:
                    self.S['sensitivity'] = min(20, self.S['sensitivity'] + 0.5)
                elif ev.button == 5:
                    self.S['sensitivity'] = max(1, self.S['sensitivity'] - 0.5)

            elif ev.type == pygame.MOUSEBUTTONUP:
                self.dragging = None

            elif ev.type == pygame.MOUSEMOTION and ev.buttons[0]:
                self._drag(*ev.pos)

            elif ev.type == pygame.DROPFILE:
                self._play_file(ev.file)

    def _key(self, key):
        if key == pygame.K_ESCAPE:
            if self.show_setup_guide:
                self.show_setup_guide = False
            elif self.show_picker:
                self.show_picker = False
            else:
                self.running = False
        elif key == pygame.K_RETURN and self.show_picker:
            self.show_picker = False
        elif key == pygame.K_h:
            self.show_panel = not self.show_panel
        elif key == pygame.K_f:
            pygame.display.toggle_fullscreen()
        elif key == pygame.K_k:
            self.S['kaleidoscope'] = not self.S['kaleidoscope']
        elif key == pygame.K_r:
            self.random_pal = _rand_pal()
            self.S['color_mode'] = 'random'

    def _click(self, mx, my, w, h):
        if self.show_picker:
            for r, idx in self.dev_rects:
                if r.collidepoint(mx, my):
                    self.show_picker = False
                    self._start_mic(idx)
            return

        if self.show_setup_guide:
            B = self.btns
            if 'bh_download' in B and B['bh_download'].collidepoint(mx, my):
                open_download_page()
            elif 'bh_midi' in B and B['bh_midi'].collidepoint(mx, my):
                open_audio_midi_setup()
            elif 'bh_check' in B and B['bh_check'].collidepoint(mx, my):
                bh = find_blackhole()
                if bh:
                    self._guide_bh_found = True
                    self.show_setup_guide = False
                    idx, name = bh
                    ok = self.audio.start_mic(idx)
                    self.status_msg = f"System audio via {name}" if ok else "BlackHole error"
                    self.S['src'] = 'system' if ok else None
                else:
                    self._guide_bh_found = False
                    self.status_msg = "BlackHole not found — make sure you installed the .pkg"
            elif 'bh_close' in B and B['bh_close'].collidepoint(mx, my):
                self.show_setup_guide = False
            return

        # Slider drag start
        for key, (bx, by, sw, lo, hi) in self.bars.items():
            if bx <= mx <= bx + sw and by <= my <= by + 14:
                self.dragging = key
                self._drag(mx, my)
                return

        # Buttons
        B = self.btns
        def hit(k): return k in B and B[k].collidepoint(mx, my)

        if hit('mic'):        self._start_mic()
        elif hit('system'):   self._start_system()
        elif hit('file'):     self._open_file()
        elif hit('midi'):     open_audio_midi_setup()
        elif hit('chladni'):  self.S['pattern'] = 'chladni'
        elif hit('rings'):    self.S['pattern'] = 'rings'
        elif hit('liss'):
            self.S['pattern'] = 'lissajous'
            self.liss_trail.clear()
        elif hit('pal'):  self.S['color_mode'] = 'palette'
        elif hit('rnd'):  self.S['color_mode'] = 'random'; self.random_pal = _rand_pal()
        elif hit('chk'):  self.S['color_mode'] = 'chakra'
        elif hit('pcyc'):
            self.S['palette_idx'] = (self.S['palette_idx'] + 1) % len(PALETTE_NAMES)
            self.S['color_mode']  = 'palette'
        elif hit('kalei'):  self.S['kaleidoscope'] = not self.S['kaleidoscope']
        elif hit('mirror'): self.S['mirror'] = not self.S['mirror']

    def _drag(self, mx, my):
        if not self.dragging or self.dragging not in self.bars:
            return
        bx, by, sw, lo, hi = self.bars[self.dragging]
        t   = max(0.0, min(1.0, (mx - bx) / sw))
        val = lo + (hi - lo) * t
        key = self.dragging
        if key == 'segments':   val = int(round(val))
        if key == 'spin_speed': val = val / 40000
        self.S[key] = val

    # ══════════════════════════════════════════════════════════════════════════
    # Audio control
    # ══════════════════════════════════════════════════════════════════════════

    def _start_mic(self, device=None):
        ok   = self.audio.start_mic(device)
        name = dict(self.devices).get(device, 'default') if device is not None else 'default'
        self.status_msg = f"Listening: {name}" if ok else "Mic error — check permissions"
        self.S['src'] = 'mic'

    def _start_system(self):
        bh = find_blackhole()
        if bh:
            idx, name = bh
            ok = self.audio.start_mic(idx)
            self.status_msg = f"System audio via {name}" if ok else "BlackHole error"
            self.S['src'] = 'system' if ok else None
        else:
            # BlackHole not installed — show the setup guide overlay
            self.show_setup_guide = True

    def _open_file(self):
        # Use osascript (AppleScript) — tkinter crashes inside a pygame/SDL window on macOS
        import subprocess
        script = (
            'set f to choose file with prompt "Open Audio File" '
            'of type {"public.audio","public.mp3","public.aiff-audio",'
            '"com.apple.m4a-audio","org.xiph.flac","public.ogg-vorbis"}\n'
            'return POSIX path of f'
        )
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True, timeout=120,
            )
            path = result.stdout.strip()
            if path:
                self._play_file(path)
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            self.status_msg = f"File picker error: {e}"

    def _play_file(self, path: str):
        ok = self.audio.start_file(path)
        self.status_msg = f"▶ {Path(path).name}" if ok else "File error"
        self.S['src'] = 'file'

    # ══════════════════════════════════════════════════════════════════════════
    # Main loop
    # ══════════════════════════════════════════════════════════════════════════

    def run(self):
        while self.running:
            w, h = pygame.display.get_surface().get_size()

            self.fft = self.audio.get_fft()
            self._beat()
            energies = self._energies()
            self.S['t'] += 1.0
            if self.S['kaleidoscope']:
                self.S['rot'] += self.S['spin_speed']

            # ── Render pattern → FBO ──────────────────────────────────────
            self.rdr.fbo.use()
            self.ctx.viewport = (0, 0, w, h)
            self.ctx.clear(0.0, 0.0, 0.0)

            pat = self.S['pattern']
            if   pat == 'chladni':   self._draw_chladni(w, h, energies)
            elif pat == 'rings':     self._draw_rings(w, h, energies)
            elif pat == 'lissajous': self._draw_lissajous(w, h, energies)

            # ── Composite → screen ────────────────────────────────────────
            self.ctx.screen.use()
            self.ctx.viewport = (0, 0, w, h)
            self.ctx.clear(0.0, 0.0, 0.0)

            if self.S['kaleidoscope']:
                self.rdr.kaleidoscope(w, h,
                    self.S['segments'], self.S['rot'],
                    self.S['zoom'], self.S['mirror'])
            else:
                self.rdr.blit(self.rdr.fbo_tex, w, h)

            # ── UI overlay ────────────────────────────────────────────────
            self._draw_ui(w, h)
            raw = pygame.image.tostring(self.ui_surf, 'RGBA', True)
            ui_tex = self.ctx.texture((w, h), 4, raw)
            ui_tex.filter = moderngl.LINEAR, moderngl.LINEAR
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            self.rdr.blit(ui_tex, w, h)
            ui_tex.release()

            self._events(w, h)
            pygame.display.flip()
            self.clock.tick(60)

        self.audio.stop()
        if self.liss_tex:
            self.liss_tex.release()
        pygame.quit()
