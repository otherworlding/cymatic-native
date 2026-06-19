"""ModernGL GPU renderer — Chladni, Liquid, Kaleidoscope, passthrough."""

import moderngl
import numpy as np
from .shaders import VERT, CHLADNI, LIQUID, KALEI, PASS


class Renderer:
    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx

        quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype='f4')
        vbo  = ctx.buffer(quad.tobytes())

        self.p_chladni = ctx.program(vertex_shader=VERT, fragment_shader=CHLADNI)
        self.p_liquid  = ctx.program(vertex_shader=VERT, fragment_shader=LIQUID)
        self.p_kalei   = ctx.program(vertex_shader=VERT, fragment_shader=KALEI)
        self.p_pass    = ctx.program(vertex_shader=VERT, fragment_shader=PASS)

        def vao(p): return ctx.vertex_array(p, [(vbo, '2f', 'in_vert')])
        self.vao_c = vao(self.p_chladni)
        self.vao_l = vao(self.p_liquid)
        self.vao_k = vao(self.p_kalei)
        self.vao_p = vao(self.p_pass)

        self.fbo     = None
        self.fbo_tex = None

    def resize(self, w: int, h: int):
        if self.fbo:     self.fbo.release()
        if self.fbo_tex: self.fbo_tex.release()
        self.fbo_tex = self.ctx.texture((w, h), 4)
        self.fbo     = self.ctx.framebuffer([self.fbo_tex])

    # ── Patterns ──────────────────────────────────────────────────────────────

    def chladni(self, w, h, ms, ns, ws, cas, sas, thresh, bright, col):
        """Render modal superposition: six integer Chladni modes (ms, ns)
        summed with live per-band audio weights (ws).  cas/sas are the
        cos/sin of each mode's symmetric↔antisymmetric mixing angle."""
        p = self.p_chladni
        p['u_res'].value    = (w, h)
        self._set_array(p, 'u_m',  ms)
        self._set_array(p, 'u_n',  ns)
        self._set_array(p, 'u_w',  ws)
        self._set_array(p, 'u_ca', cas)
        self._set_array(p, 'u_sa', sas)
        p['u_thresh'].value = float(thresh)
        p['u_bright'].value = float(bright)
        p['u_col'].value    = tuple(col)
        self.vao_c.render(moderngl.TRIANGLE_STRIP)

    def liquid(self, w, h, t, bass, mid, treble, level, warp, pal):
        """Render the 1960s liquid light show.  pal = five (r,g,b) stops in 0–1."""
        p = self.p_liquid
        p['u_res'].value    = (w, h)
        p['u_time'].value   = float(t)
        p['u_bass'].value   = float(bass)
        p['u_mid'].value    = float(mid)
        p['u_treble'].value = float(treble)
        p['u_level'].value  = float(level)
        p['u_warp'].value   = float(warp)
        self._set_vec3_array(p, 'u_pal', pal)
        self.vao_l.render(moderngl.TRIANGLE_STRIP)

    @staticmethod
    def _set_array(prog, name, values):
        """Set a GLSL float[] uniform portably.  Some drivers expose the array as
        one member (``u_m``), others element-wise (``u_m[0]``); handle both."""
        vals = [float(v) for v in values]
        if name in prog:
            prog[name].value = vals
        else:
            for i, v in enumerate(vals):
                prog[f'{name}[{i}]'].value = v

    @staticmethod
    def _set_vec3_array(prog, name, vecs):
        """Set a GLSL vec3[] uniform portably (bulk list-of-rows, or element-wise)."""
        rows = [tuple(float(c) for c in v) for v in vecs]
        if name in prog:
            prog[name].value = rows
        else:
            for i, row in enumerate(rows):
                prog[f'{name}[{i}]'].value = row

    def kaleidoscope(self, w, h, segs, rot, zoom, mirror):
        self.fbo_tex.use(0)
        p = self.p_kalei
        p['u_tex'].value    = 0
        p['u_res'].value    = (w, h)
        p['u_segs'].value   = int(segs)
        p['u_rot'].value    = float(rot)
        p['u_zoom'].value   = float(zoom)
        p['u_mirror'].value = 1 if mirror else 0
        self.vao_k.render(moderngl.TRIANGLE_STRIP)

    def blit(self, tex, w, h):
        tex.use(0)
        self.p_pass['u_tex'].value = 0
        self.p_pass['u_res'].value = (w, h)
        self.vao_p.render(moderngl.TRIANGLE_STRIP)
