"""ModernGL GPU renderer — Chladni, Rings, Kaleidoscope, passthrough."""

import moderngl
import numpy as np
from .shaders import VERT, CHLADNI, RINGS, KALEI, PASS


class Renderer:
    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx

        quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype='f4')
        vbo  = ctx.buffer(quad.tobytes())

        self.p_chladni = ctx.program(vertex_shader=VERT, fragment_shader=CHLADNI)
        self.p_rings   = ctx.program(vertex_shader=VERT, fragment_shader=RINGS)
        self.p_kalei   = ctx.program(vertex_shader=VERT, fragment_shader=KALEI)
        self.p_pass    = ctx.program(vertex_shader=VERT, fragment_shader=PASS)

        def vao(p): return ctx.vertex_array(p, [(vbo, '2f', 'in_vert')])
        self.vao_c = vao(self.p_chladni)
        self.vao_r = vao(self.p_rings)
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

    def chladni(self, w, h, m, n, m2, n2, blend, thresh, bright, phase, col):
        p = self.p_chladni
        p['u_res'].value    = (w, h)
        p['u_m'].value      = float(m)
        p['u_n'].value      = float(n)
        p['u_m2'].value     = float(m2)
        p['u_n2'].value     = float(n2)
        p['u_blend'].value  = float(blend)
        p['u_thresh'].value = float(thresh)
        p['u_bright'].value = float(bright)
        p['u_phase'].value  = float(phase)
        p['u_col'].value    = tuple(col)
        self.vao_c.render(moderngl.TRIANGLE_STRIP)

    def rings(self, w, h, srcs, amps, wls, cols, t):
        p = self.p_rings
        p['u_res'].value  = (w, h)
        p['u_time'].value = float(t)
        for i in range(7):
            p[f'u_src[{i}]'].value  = tuple(srcs[i])
            p[f'u_amp[{i}]'].value  = float(amps[i])
            p[f'u_wl[{i}]'].value   = float(wls[i])
            p[f'u_scol[{i}]'].value = tuple(cols[i])
        self.vao_r.render(moderngl.TRIANGLE_STRIP)

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
