# ============================================================================
# [NEW] WORLD SCALE + ANATOMY + WORLD TAB
# ============================================================================
#
# One scale for everything. The world used pixel sizes tuned independently
# per object (Jane 240 px, near trees 70-110 px, rabbits on a dog-sized
# generic blob), so a house reached her shoulder and rabbits looked like
# capybaras. Now:
#
#   WS.px  = pixels per metre, derived from the viewport so Jane (1.70 m)
#            always fills the same share of the view;
#   every species, Jane, trees, POIs, her home, buildings and region widths
#   are defined in metres and drawn through WS.m(metres).
#   If the scale changes (window resize, reload on another screen), every
#   persistent position is rescaled with it, so nothing drifts.
#
# Animals are drawn by an anatomical renderer from per-species dimensions
# (body length, shoulder height, chest depth, head, neck, fore/hind legs,
# ears, tail, posture, gait) instead of one generic blob.
#
# The WORLD tab re-grids the existing stage (same canvas, same renderer):
# the stage takes the whole window under the tab strip + a world toolbar;
# other tabs get the original layout back. Camera: dead-zone follow (she
# moves freely through the middle of the view) with the ground framed low.

import math as _sc_math
import random as _sc_random

JANE_HEIGHT_M = 1.70


class WorldScale:
    """Pixels per metre. Jane's height is ~19% of the height above ground."""

    def __init__(self):
        self.px = 30.0 * 8.1 / JANE_HEIGHT_M          # the old scale until a viewport exists
        self.listeners = []

    def m(self, metres):
        return metres * self.px

    def to_m(self, px):
        return px / self.px

    def fit(self, ground_y):
        new = max(20.0, ground_y * 0.19 / JANE_HEIGHT_M)
        if abs(new - self.px) / self.px > 0.005:
            ratio = new / self.px
            self.px = new
            for fn in list(self.listeners):
                try:
                    fn(ratio)
                except Exception:
                    traceback.print_exc()


WS = WorldScale()

# ---- species dimensions (metres, m/s) --------------------------------------------
#   L body length (chest to rump), sh shoulder height, dp chest depth,
#   hd (head length, head height), nk neck length, na neck angle (deg up),
#   lf/lh fore/hind leg length, ear (len, width), tl tail length, rump rump/shoulder
SPECIES = {
    "rabbit": dict(kind="lagomorph", L=0.30, sh=0.15, dp=0.14, hd=(0.085, 0.07), nk=0.02, na=15,
                   lf=0.06, lh=0.10, ear=(0.095, 0.03), tl=0.04, rump=1.35, walk=0.5, run=8.0, flee=6.0),
    "deer": dict(kind="cervid", L=1.15, sh=0.95, dp=0.40, hd=(0.30, 0.15), nk=0.36, na=46, nw=0.34,
                 lf=0.56, lh=0.60, ear=(0.14, 0.06), tl=0.13, rump=1.03, walk=1.3, run=12.0, flee=25.0),
    "fox": dict(kind="canid", L=0.60, sh=0.38, dp=0.19, hd=(0.17, 0.10), nk=0.12, na=30,
                lf=0.21, lh=0.23, ear=(0.08, 0.05), tl=0.40, rump=0.97, walk=1.2, run=11.0, flee=12.0, bushy=True),
    "wolf": dict(kind="canid", L=1.05, sh=0.76, dp=0.36, hd=(0.28, 0.16), nk=0.20, na=28,
                 lf=0.42, lh=0.44, ear=(0.10, 0.06), tl=0.42, rump=0.96, walk=1.5, run=12.0, flee=8.0, bushy=True),
    "dog": dict(kind="canid", L=0.75, sh=0.55, dp=0.27, hd=(0.20, 0.14), nk=0.14, na=34, nw=0.5,
                lf=0.30, lh=0.32, ear=(0.11, 0.07), tl=0.30, rump=0.98, walk=1.3, run=8.0, flee=5.0, floppy=True),
    "cat": dict(kind="felid", L=0.45, sh=0.25, dp=0.14, hd=(0.09, 0.085), nk=0.05, na=20,
                lf=0.13, lh=0.15, ear=(0.045, 0.04), tl=0.28, rump=1.02, walk=0.9, run=8.0, flee=5.0),
    "bird": dict(kind="bird", L=0.16, span=0.26, walk=0.3, run=9.0, flee=4.0),
    "butterfly": dict(kind="insect", span=0.06, run=1.5, flee=0.8),
    "firefly": dict(kind="glow", span=0.015, run=0.8, flee=0.0),
}


def _sc_apply_fauna():
    """FAUNA's logic numbers (speed, flee distance, size) from real dimensions."""
    for sp, d in SPECIES.items():
        F = FAUNA.get(sp)
        if F is None:
            continue
        F["speed"] = d["run"] * WS.px * 0.62
        F["flee"] = d["flee"] * WS.px
        F["size"] = max(2.0, (d.get("sh") or d.get("span", 0.1)) * 0.5 * WS.px)


_sc_apply_fauna()
WS.listeners.append(lambda r: _sc_apply_fauna())


# ---- Jane's size comes from the same scale ---------------------------------------
_sc_prev_H = Creature._H


def _sc_H(self):
    base = _sc_prev_H(self) / 30.0                     # build + shape variation, relative
    return WS.m(JANE_HEIGHT_M) / 8.1 * base


Creature._H = _sc_H
# behaviour distances (sensing, approach, arrival, spacing) in one real unit: 1 m
Creature._Hb = lambda self: WS.m(1.0)


# ---- keeping persistent positions consistent when the scale changes ---------------
def _sc_rescale(app, r):
    cr = app.creature
    cr.x *= r
    if isinstance(getattr(cr, "target", None), tuple):
        cr.target = (cr.target[0] * r, cr.target[1])
    L = getattr(cr, "_loco", None)
    if L is not None:
        L.px = cr.x
        for sd in ("L", "R"):
            if L.foot.get(sd) is not None:
                L.foot[sd] *= r
            if L.plant.get(sd) is not None:                 # a foot mid-step has no plant point
                L.plant[sd] *= r
    fa = getattr(app, "fauna", None)
    for a in list(getattr(fa, "animals", []) or []) + list(getattr(fa, "_stash", None) or []):
        a.x *= r
        a.goal *= r
        p = getattr(a, "psy", None)
        if p is not None and p.home is not None:
            p.home *= r
    ob = getattr(app, "objects", None)
    for f in (ob.fires.values() if ob else []):
        f.x *= r
    life = _lf_life(app)
    if life.home:
        life.home["x"] *= r
    cmd = getattr(life, "command", None)
    if cmd and cmd.get("x") is not None:
        cmd["x"] *= r
    for b in getattr(app, "bodies", []) or []:
        b.x *= r
        b.target *= r
        b.home *= r
    for tv in getattr(app, "travellers", []) or []:
        tv.x *= r
    for d in getattr(app.brain.mind, "_fauna_saved", None) or []:
        if d.get("x") is not None:
            d["x"] *= r
    cam = getattr(app, "_camera", None)
    if cam is not None:
        cam.pos[0] *= r
        cam._dz = getattr(cam, "_dz", cam.pos[0]) * r


# saved positions are in the scale they were saved at
_m43_save_hooks.append(lambda app: ("px_per_m", WS.px))


def _sc_load(app, w):
    px = w.get("px_per_m")
    if px:
        WS.px = float(px)                                # positions load in their own scale
        _sc_apply_fauna()


_m43_load_hooks.insert(0, _sc_load)

# world width and vegetation are built in metres: fit the scale BEFORE building
_SC_REGION_M = {"valley": 48.0, "road": 70.0, "settlement": 100.0}
_sc_prev_rebuild = World.rebuild


def _sc_rebuild(self, w, h, ground, daypart, weather, detail="high"):
    WS.fit(ground)
    return _sc_prev_rebuild(self, w, h, ground, daypart, weather, detail)


World.rebuild = _sc_rebuild


# ============================================================================
# Anatomical animal renderer
# ============================================================================

def _sc_draw_animals(self, canvas, cam, world, grade):
    if self.pool is None:
        self.pool = _AtmoPool(canvas)
    P = self.pool
    P.begin()
    W = cam.world_to_screen
    lit = world.light()
    S_ = WS.px
    vx0, _ = cam.screen_to_world(-60, 0)
    vx1, _ = cam.screen_to_world(canvas.winfo_width() + 60, 0)
    gc = (lambda c_, y: grade.color(c_, y)) if grade else (lambda c_, y: c_)

    def poly(pts, col, smooth=True):
        out = []
        for i in range(0, len(pts), 2):
            out.extend(W(pts[i], pts[i + 1]))
        P.put("polygon", out, "fauna", fill=col, outline="", smooth=smooth)

    def line(pts, col, width=1.0):
        out = []
        for i in range(0, len(pts), 2):
            out.extend(W(pts[i], pts[i + 1]))
        P.put("line", out, "fauna", fill=col, width=max(1, int(round(width * cam.zoom))), capstyle="round")

    def oval(cx, cy, rx, ry, col):
        (x0, y0), (x1, y1) = W(cx - rx, cy - ry), W(cx + rx, cy + ry)
        P.put("oval", [x0, y0, x1, y1], "fauna", fill=col, outline="")

    for a in self.animals:
        if not (vx0 - 80 < a.x < vx1 + 80):
            continue
        d = SPECIES.get(a.sp)
        if d is None:
            continue
        k = S_ * a.scale                                   # px per metre for THIS individual
        g = world.ground + 8 - a.alt
        f = a.facing
        x = a.x
        body = gc(a.S["body"], g)
        belly = gc(a.S["belly"], g)
        dark = _shade(body, 0.72)
        hi = _mix_hex(body, "#ffffff", 0.22)
        kind = d["kind"]
        if kind == "glow":
            gl = 0.5 + 0.5 * _sc_math.sin(a.t * 4 + a.id)
            r = max(1.0, (0.012 + 0.02 * gl) * k)
            oval(x, g, r, r, _mix_hex("#304020", a.S["body"], 0.3 + 0.6 * gl))
            continue
        if kind == "insect":
            flap = abs(_sc_math.sin(a.t * 14 + a.id))
            sp = d["span"] * k * 0.5
            poly([x, g, x - sp * flap, g - sp * 0.9, x - sp * 0.9, g + sp * 0.25], body, False)
            poly([x, g, x + sp * flap, g - sp * 0.9, x + sp * 0.9, g + sp * 0.25], belly, False)
            continue
        if kind == "bird":
            bl = d["L"] * k
            if a.alt > 3:
                flap = _sc_math.sin(a.t * 12 + a.id)
                sp = d["span"] * k * 0.5
                oval(x, g, bl * 0.45, bl * 0.18, body)
                line([x, g, x - sp * 0.55, g - sp * 0.7 * flap, x - sp, g - sp * 0.35 * flap], body, max(1.0, bl * 0.12))
                line([x, g, x + sp * 0.55, g - sp * 0.7 * flap, x + sp, g - sp * 0.35 * flap], body, max(1.0, bl * 0.12))
            else:
                oval(x, g - bl * 0.32, bl * 0.42, bl * 0.24, body)                       # perched body
                oval(x + f * bl * 0.34, g - bl * 0.52, bl * 0.16, bl * 0.15, body)        # head
                poly([x + f * bl * 0.48, g - bl * 0.54, x + f * bl * 0.66, g - bl * 0.5, x + f * bl * 0.48, g - bl * 0.46],
                     gc("#e0a53a", g), False)
                line([x - f * bl * 0.35, g - bl * 0.34, x - f * bl * 0.7, g - bl * 0.25], dark, max(1.0, bl * 0.1))
                line([x, g - bl * 0.1, x, g], _shade(dark, 0.6), 1)
            continue
        # ---- quadrupeds ---------------------------------------------------------------
        L, sh, dp = d["L"] * k, d["sh"] * k, d["dp"] * k
        lf, lh = d["lf"] * k, d["lh"] * k
        hl, hh = d["hd"][0] * k, d["hd"][1] * k
        moving = abs(a.vx) > 0.05 * k
        run = abs(a.vx) > 0.35 * d["run"] * k * 0.62
        sleep = a.state == "sleep"
        sit = a.state == "beg" or (kind == "lagomorph" and not moving and not sleep)
        graze = a.state in ("graze", "sniff", "drink")
        stride = max(0.05 * k, sh * 0.6)
        ph = a.__dict__.get("_gph", 0.0) + abs(a.vx) / max(1.0, stride) * 0.016 * 6.3
        a._gph = ph
        bounce = 0.0
        if kind == "lagomorph" and moving:
            bounce = abs(_sc_math.sin(ph * 0.5)) * sh * (1.2 if run else 0.6)            # hopping
        elif a.state in ("play", "excited"):
            bounce = abs(_sc_math.sin(ph)) * sh * 0.25
        # body frame: shoulder point (front) and hip point (back) at the top line
        low = 0.0 if not sleep else (sh - dp * 0.9)
        sx_, hx_ = x + f * L * 0.30, x - f * L * 0.32
        sy_ = g - sh - bounce + low
        hy_ = g - sh * d["rump"] - bounce + low * 1.05
        if sit and kind != "lagomorph":
            hy_ = g - dp * 0.9                               # sitting: rump on the ground
        # shadow (contact), scaled to the animal
        oval(x, world.ground + 9, L * 0.55, max(1.5, dp * 0.18), gc("#0d1210", world.ground))
        # legs: far pair darker and first, near pair after the body
        def limb(pts, wids, col):
            nodes = [(pts[i], pts[i + 1]) for i in range(0, len(pts), 2)]
            if len(nodes) >= 2:
                poly(_chain_skin(nodes, wids, 1.0, 0.0), col)

        def leg(px0, py0, length, hind, phase, col, wdt):
            if sleep:
                limb([px0, py0 + dp * 0.4, px0 + f * length * 0.5, g - 0.02 * k], [wdt * 1.2, wdt * 0.6], col)
                return
            sw = _sc_math.sin(phase) * (0.45 if run else 0.25) * length if moving and kind != "lagomorph" else 0.0
            if kind == "lagomorph":
                sw = (-0.5 if hind else 0.35) * length * (1 if bounce > sh * 0.2 else 0) * f
            top = py0 + dp * 0.55
            foot = (px0 + sw * f, g)
            hoof = "#2a2220" if kind == "cervid" else _shade(col, 0.55)
            if hind:
                if sit and kind != "lagomorph":
                    limb([px0, top, px0 + f * length * 0.6, g - 0.02 * k, px0 + f * length * 0.9, g],
                         [wdt * 1.9, wdt * 1.1, wdt * 0.55], col)
                    return
                knee = (px0 + f * length * 0.18 + sw * 0.4 * f, top + (g - top) * 0.42)
                hock = (px0 - f * length * 0.12 + sw * 0.7 * f, top + (g - top) * 0.78)
                limb([px0, top, *knee, *hock, *foot], [wdt * 2.0, wdt * 1.25, wdt * 0.62, wdt * 0.5], col)
            else:
                knee = (px0 + sw * 0.5 * f, top + (g - top) * 0.55)
                limb([px0, top, *knee, *foot], [wdt * 1.45, wdt * 0.72, wdt * 0.5], col)
            if foot[1] >= g - 0.01 * k and abs(sw) < length * 0.2:
                oval(foot[0], g + 0.004 * k, wdt * 0.9, max(0.8, wdt * 0.28), gc("#0d1210", g))    # foot on the ground
            oval(foot[0] + f * wdt * 0.15, foot[1] - wdt * 0.2, wdt * 0.42, wdt * 0.3, hoof)
        lw_f, lw_h = max(1.0, L * 0.075), max(1.0, L * 0.1)
        if kind == "lagomorph":
            lw_f, lw_h = max(1.0, L * 0.06), max(1.0, L * 0.16)
        leg(sx_ - f * L * 0.04, sy_, g - sy_ - dp * 0.55, False, ph + _sc_math.pi, dark, lw_f)
        leg(hx_ + f * L * 0.04, hy_, g - hy_ - dp * 0.55, True, ph, dark, lw_h)
        # torso: rump -> back -> withers -> chest -> belly
        back_mid = ((sx_ + hx_) / 2, (sy_ + hy_) / 2 - dp * (0.05 if kind != "lagomorph" else 0.18))
        torso = [hx_ - f * L * 0.08, hy_ + dp * 0.35, hx_, hy_ - dp * 0.02, *back_mid, sx_, sy_ - dp * 0.04,
                 sx_ + f * L * 0.1, sy_ + dp * 0.45, sx_ + f * L * 0.02, sy_ + dp * 0.95,
                 x, (sy_ + hy_) / 2 + dp * 0.92, hx_ + f * L * 0.02, hy_ + dp * 0.85]
        poly(torso, body)
        if L * cam.zoom > 14:                                       # muscle masses give the body volume
            oval(hx_ + f * L * 0.06, hy_ + dp * 0.4, L * 0.17, dp * 0.42, _shade(body, 0.9))
            oval(sx_ - f * L * 0.02, sy_ + dp * 0.42, L * 0.14, dp * 0.4, _shade(body, 0.93))
            oval(hx_ + f * L * 0.1, hy_ + dp * 0.25, L * 0.1, dp * 0.2, hi)
        poly([sx_ + f * L * 0.04, sy_ + dp * 0.6, x, (sy_ + hy_) / 2 + dp * 0.9, hx_ + f * L * 0.05, hy_ + dp * 0.75,
              x, (sy_ + hy_) / 2 + dp * 0.62], belly)
        if kind in ("cervid", "canid") and L * cam.zoom > 18:
            line([hx_, hy_ + dp * 0.06, *back_mid, sx_, sy_ + dp * 0.06], _shade(body, 0.7), max(1.0, dp * 0.08))
        if L * cam.zoom > 18:
            line([hx_, hy_ + dp * 0.02, *back_mid, sx_, sy_ + dp * 0.02], hi, max(1.0, dp * 0.06))      # back light
        # tail
        tl = d["tl"] * k
        if kind == "lagomorph":
            oval(hx_ - f * L * 0.1, hy_ + dp * 0.3, tl * 0.55, tl * 0.5, gc("#f4efe8", g))
        else:
            wag = _sc_math.sin(a.t * (16 if a.state in ("excited", "play", "follow") else 4)) * 0.35 if a.sp == "dog" else 0.0
            droop = {"wolf": 0.75, "fox": 0.45, "deer": -0.6, "dog": -0.35, "cat": -0.9}.get(a.sp, 0.3)
            if a.state == "flee" and a.sp == "deer":
                droop = -1.2                                                                        # white flag up
            t0 = (hx_ - f * L * 0.02, hy_ + dp * 0.1)
            t1 = (t0[0] - f * tl * 0.6, t0[1] + tl * (droop + wag) * 0.5)
            t2 = (t0[0] - f * tl * 0.95, t0[1] + tl * (droop + wag) * 0.95)
            tw = max(1.0, tl * (0.28 if d.get("bushy") else 0.12))
            line([*t0, *t1, *t2], body, tw)
            if a.sp == "fox":
                oval(t2[0], t2[1], tw * 0.5, tw * 0.5, gc("#f4efe8", g))
            if a.sp == "deer":
                line([*t0, *t1], gc("#f4efe8", g), max(1.0, tw * 0.6))
        # neck + head
        na = _sc_math.radians(d["na"] + (18 if a.state == "watch" else 0) if not graze else -35)
        if sleep:
            na = _sc_math.radians(-10)
        nk = d["nk"] * k
        n0 = (sx_ + f * L * 0.06, sy_ + dp * 0.25)
        n1 = (n0[0] + f * nk * _sc_math.cos(na), n0[1] - nk * _sc_math.sin(na))
        if nk > 0.03 * k:                                   # a tapered neck: thick at the shoulders, slim at the head
            nw = d.get("nw", 0.5) * dp
            poly(_chain_skin([n0, ((n0[0] + n1[0]) / 2, (n0[1] + n1[1]) / 2), n1], [nw * 1.6, nw * 1.05, nw * 0.8], 1.0, 0.0), body)
        hx, hy = n1[0] + f * hl * 0.2, n1[1] - hh * 0.1
        if graze:
            hy = min(g - hh * 0.5, hy + dp * 0.6)
        if sleep:
            hy = g - hh * 0.5
        skull = [hx - f * hl * 0.35, hy - hh * 0.5, hx + f * hl * 0.15, hy - hh * 0.55,
                 hx + f * hl * 0.65, hy - hh * 0.05 + (0.0 if kind != "felid" else -hh * 0.1),
                 hx + f * hl * 0.62, hy + hh * 0.2, hx - f * hl * 0.1, hy + hh * 0.45, hx - f * hl * 0.4, hy + hh * 0.1]
        poly(skull, body)
        if kind in ("canid", "felid"):
            oval(hx - f * hl * 0.08, hy - hh * 0.12, hl * 0.36, hh * 0.52, body)                      # cranium
        if kind in ("canid", "cervid"):
            poly([hx + f * hl * 0.15, hy + hh * 0.05, hx + f * hl * 0.62, hy + hh * 0.08, hx + f * hl * 0.55, hy + hh * 0.3,
                  hx, hy + hh * 0.4], belly)                                                        # lighter muzzle/jaw
        # ears
        el, ew = d["ear"][0] * k, d["ear"][1] * k
        if kind == "lagomorph":
            back = 0.55 if a.state == "flee" else 0.12
            for e in (-0.25, 0.1):
                ex = hx + f * hl * e
                poly([ex - ew * 0.5, hy - hh * 0.4, ex - f * el * back - ew * 0.3, hy - hh * 0.4 - el,
                      ex - f * el * back + ew * 0.5, hy - hh * 0.4 - el * 0.97, ex + ew * 0.5, hy - hh * 0.4], body)
            poly([hx - ew * 0.2, hy - hh * 0.45, hx - f * el * back, hy - hh * 0.4 - el * 0.85,
                  hx - f * el * back + ew * 0.3, hy - hh * 0.4 - el * 0.85], _mix_hex(body, "#e8b0a8", 0.4))
        elif d.get("floppy"):
            poly([hx - f * hl * 0.15, hy - hh * 0.45, hx - f * hl * 0.35, hy + el * 0.5,
                  hx - f * hl * 0.05, hy + el * 0.35], dark)
        else:
            ex = hx - f * hl * 0.12
            poly([ex - ew * 0.5, hy - hh * 0.4, ex + f * ew * 0.1, hy - hh * 0.4 - el, ex + ew * 0.55, hy - hh * 0.38], body, False)
        if a.sp == "deer" and a.id % 2 == 0 and a.scale > 0.8:                                    # a stag's antlers
            ax0 = (hx - f * hl * 0.05, hy - hh * 0.45)
            line([*ax0, ax0[0] - f * hl * 0.2, ax0[1] - hh * 1.3, ax0[0] - f * hl * 0.45, ax0[1] - hh * 2.1], gc("#8a6a44", g), max(1.0, hh * 0.1))
            line([ax0[0] - f * hl * 0.2, ax0[1] - hh * 1.3, ax0[0] + f * hl * 0.15, ax0[1] - hh * 1.9], gc("#8a6a44", g), max(1.0, hh * 0.08))
        # eye + nose
        er = max(0.6, hh * 0.1)
        eye_col = "#f4e08a" if (a.sp == "wolf" and lit < 0.5) else "#111111"
        if not sleep:
            oval(hx + f * hl * 0.12, hy - hh * 0.15, er, er, eye_col)
        else:
            line([hx + f * hl * 0.05, hy - hh * 0.15, hx + f * hl * 0.2, hy - hh * 0.12], "#111111", 1)
        oval(hx + f * hl * 0.63, hy + hh * 0.02, max(0.6, hh * 0.08), max(0.6, hh * 0.07), "#1a1414")
        # near legs last (in front of the body)
        leg(sx_ + f * L * 0.02, sy_, g - sy_ - dp * 0.55, False, ph, body, lw_f)
        leg(hx_ - f * L * 0.02, hy_, g - hy_ - dp * 0.55, True, ph + _sc_math.pi, body, lw_h)
    P.end()


Fauna.draw = _sc_draw_animals


# ============================================================================
# Camera: dead-zone follow, ground framed low, no zooming out past the world
# ============================================================================

def _sc_frame_target(self, dt):
    cr = self.follow_target
    w, h = self._wh()
    z = max(self.zoom, 1e-3)
    vw, vh = w / z, h / z
    vx = getattr(getattr(cr, "_loco", None), "vx", 0.0)
    ahead = clamp(vx * 0.35, -0.12 * vw, 0.12 * vw)
    self._look = getattr(self, "_look", 0.0)
    self._look += (ahead - self._look) * (1.0 - _sc_math.exp(-dt / 1.2))
    dz = getattr(self, "_dz", None)
    if dz is None:
        dz = cr.x
    zone = 0.2 * vw                                     # she walks freely through the middle 40%
    px_ = cr.x + self._look
    if px_ > dz + zone:
        dz = px_ - zone
    elif px_ < dz - zone:
        dz = px_ + zone
    self._dz = dz
    bb = getattr(cr, "_bbox", None)
    feet = bb[3] if bb else cr.y
    tx, ty = dz, feet - 0.3 * vh                        # the ground sits ~80% down the view
    ew, eh = self.__dict__.get("world_ext") or (w, h)
    if vw < ew:
        tx = clamp(tx, vw * 0.5, ew - vw * 0.5)
    if vh < eh:
        ty = clamp(ty, vh * 0.5, eh - vh * 0.5)
    return tx, ty


StageCamera._frame_target = _sc_frame_target
_sc_prev_cam_init = StageCamera.__init__


def _sc_cam_init(self, *a, **kw):
    _sc_prev_cam_init(self, *a, **kw)
    self.min_zoom = 1.0                                 # never show past the authored world
    self.max_zoom = 3.2


StageCamera.__init__ = _sc_cam_init


# ============================================================================
# The WORLD tab
# ============================================================================

def _sc_layout_parts(app):
    main = app.tabs.master
    w = app.stage
    while w is not None and w.master is not main:
        w = w.master
    left = w
    quick = [c for c in left.grid_slaves() if int(c.grid_info().get("row", 0)) == 1] if left else []
    return main, left, (quick[0] if quick else None)


def _sc_world_mode(app, on):
    if getattr(app, "_world_mode", False) == on:
        return
    main, left, quick = _sc_layout_parts(app)
    if left is None:
        return
    app._world_mode = on
    if on:
        # a Notebook asks for its TALLEST page's height; pin the pane to the
        # world toolbar, or the tab strip would squeeze the world
        app.tabs.configure(height=max(28, app.world_tab.winfo_reqheight()))
        app.tabs.grid_configure(row=0, column=0, columnspan=2, sticky="ew")
        left.grid_configure(row=1, column=0, columnspan=2, sticky="nsew", padx=0)
        main.grid_rowconfigure(0, weight=0)
        main.grid_rowconfigure(1, weight=1)
        if quick is not None:
            quick.grid_remove()
    else:
        app.tabs.configure(height=0)
        app.tabs.grid_configure(row=0, column=1, columnspan=1, sticky="nsew")
        left.grid_configure(row=0, column=0, columnspan=1, sticky="nsew", padx=(0, 10))
        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=0)
        if quick is not None:
            quick.grid()


def _sc_zoom(app, factor=None, reset=False):
    cam = getattr(app, "_camera", None)
    if cam is None:
        return
    cam._touched = True
    cam.zoom = 1.15 if reset else clamp(cam.zoom * factor, cam.min_zoom, cam.max_zoom)


def _sc_fullscreen(app, on=None):
    root = app.root
    cur = str(root.attributes("-fullscreen")) in ("1", "True", "true")
    root.attributes("-fullscreen", (not cur) if on is None else on)
    if not cur and on is not False:
        _sc_select_world(app)


def _sc_select_world(app):
    tab = getattr(app, "world_tab", None)
    if tab is not None:
        app.tabs.select(tab)


def _sc_build_world_tab(app):
    tab = tk.Frame(app.tabs, bg=C_BG)
    app.world_tab = tab
    app.tabs.insert(0, tab, text="WORLD")
    bar = tk.Frame(tab, bg=C_BG)
    bar.pack(fill="x", padx=6, pady=(6, 4))

    def btn(text, cmd):
        b = app._button(bar, text, cmd, bg=C_PANEL_2, pady=3)
        b.pack(side="left", padx=(0, 6))
        return b
    btn("−", lambda: _sc_zoom(app, 1 / 1.2))
    btn("+", lambda: _sc_zoom(app, 1.2))
    btn("RESET VIEW", lambda: _sc_zoom(app, reset=True))

    def toggle_follow():
        cam = getattr(app, "_camera", None)
        if cam is not None:
            cam.follow_enabled = not cam.follow_enabled
            cam._touched = True
            app._sc_follow_btn.config(text="FOLLOW JANE ✓" if cam.follow_enabled else "FOLLOW JANE ✗")
    app._sc_follow_btn = btn("FOLLOW JANE ✓", toggle_follow)
    btn("FULLSCREEN (F11)", lambda: _sc_fullscreen(app))
    app._sc_status = tk.Label(bar, text="", bg=C_BG, fg=C_DIM, font=FONT_UI_SMALL, anchor="e")
    app._sc_status.pack(side="right", fill="x", expand=True)

    def changed(_e=None):
        try:
            _sc_world_mode(app, app.tabs.select() == str(tab))
        except Exception:
            traceback.print_exc()
    app.tabs.bind("<<NotebookTabChanged>>", changed, add="+")
    root = app.root
    root.bind("<F11>", lambda e: _sc_fullscreen(app))
    root.bind("<Escape>", lambda e: _sc_fullscreen(app, False)
              if str(root.attributes("-fullscreen")) in ("1", "True", "true") else None, add="+")
    for key, fac in (("<KeyPress-plus>", 1.2), ("<KeyPress-equal>", 1.2), ("<KeyPress-minus>", 1 / 1.2)):
        app.stage.bind(key, lambda e, f_=fac: _sc_zoom(app, f_))
    app.stage.bind("<Button-1>", lambda e: app.stage.focus_set(), add="+")


_sc_prev_build_ui = App._build_ui


def _sc_build_ui(self):
    _sc_prev_build_ui(self)
    try:
        _sc_build_world_tab(self)
    except Exception:
        traceback.print_exc()


App._build_ui = _sc_build_ui

_sc_prev_update = App._update_world


def _sc_update(self, dt):
    if not getattr(self, "_sc_listening", False):              # before the first world build
        self._sc_listening = True
        WS.listeners.append(lambda r, app=self: _sc_rescale(app, r))
    _sc_prev_update(self, dt)
    try:
        st = getattr(self, "_sc_status", None)
        t = getattr(self, "_sc_status_t", 0.0) + dt
        self._sc_status_t = t
        if st is not None and t > 0.5:
            self._sc_status_t = 0.0
            here = _rw_here(self)
            life = _lf_life(self)
            plan = getattr(life, "plan", None)
            doing = (life.command or {}).get("text") if getattr(life, "command", None) else \
                (_ag_describe(plan["steps"][plan["i"]:]) if plan else self.creature.behavior)
            st.config(text=f"{_wo_place_name(*here)}  ·  {self.world.daypart}  ·  Jane: {doing}"[:120])
    except Exception:
        pass


App._update_world = _sc_update


# ============================================================================
# Places drawn at their real size (valley / road; towns draw their own)
# ============================================================================

def _sc_draw_pois(self):
    c, add, G = self.c, self._add, self.ground
    lit = self.light()
    rnd = _sc_random.Random(hash((getattr(self, "_region_name", "valley"), int(self.w))) & 0xffff)
    m = WS.m
    dim = lambda col: _mix_hex(col, "#0b1018", 0.45 - 0.35 * lit)
    for p in self.pois:
        x = p.x
        if p.kind == "food":                                    # berry thicket ~1.3 m tall, 2.2 m across
            for k, (dx, hh, rr) in enumerate(((-0.7, 0.8, 0.55), (0.0, 1.25, 0.7), (0.75, 0.9, 0.55), (0.3, 0.55, 0.45))):
                add(c.create_polygon(_lw_blob(x + m(dx), G - m(hh) * 0.6, m(rr), m(rr) * 0.8, rnd),
                                     fill=dim(_shade("#2f5a2c", 0.85 + 0.08 * k)), outline="", smooth=True, tags="world"))
            for _ in range(14):
                bx, by = x + m(rnd.uniform(-0.9, 0.9)), G - m(rnd.uniform(0.2, 1.1))
                r = max(1.2, m(0.025))
                add(c.create_oval(bx - r, by - r, bx + r, by + r, fill=dim("#b8284a"), outline="", tags="world"))
        elif p.kind == "water":                                 # spring pool ~3.4 m across
            add(c.create_oval(x - m(1.9), G - m(0.05), x + m(1.9), G + m(0.42), fill=dim("#5a5650"), outline="", tags="world"))
            add(c.create_oval(x - m(1.7), G, x + m(1.7), G + m(0.36), fill=dim("#1d4a6a"), outline="", tags="world"))
            add(c.create_oval(x - m(1.3), G + m(0.04), x + m(1.1), G + m(0.22), fill=dim("#3f7fa6"), outline="", tags="world"))
            add(c.create_line(x - m(0.9), G + m(0.09), x + m(0.4), G + m(0.09), fill=dim("#a8dcf2"), width=1, tags="world"))
            for k in range(7):                                  # rim stones
                a_ = _sc_math.pi * (k / 6.0)
                sx, sy = x + m(1.85) * _sc_math.cos(a_), G + m(0.18) - m(0.22) * _sc_math.sin(a_) * 0.2
                rr = m(rnd.uniform(0.12, 0.22))
                add(c.create_polygon(_lw_blob(sx, sy, rr, rr * 0.6, rnd, 7, 0.2), fill=dim("#6d6a66"), outline="",
                                     smooth=True, tags="world"))
        elif p.kind == "shelter":                               # a stone overhang ~2.6 m tall
            add(c.create_polygon(x - m(1.9), G, x - m(1.7), G - m(1.6), x - m(0.9), G - m(2.6), x + m(0.8), G - m(2.5),
                                 x + m(1.9), G - m(1.4), x + m(2.0), G, fill=dim("#5c5a58"), outline="", smooth=True,
                                 tags="world"))
            add(c.create_polygon(x - m(0.9), G - m(2.3), x + m(0.6), G - m(2.35), x + m(1.5), G - m(1.5),
                                 x + m(0.2), G - m(1.9), fill=dim("#7a7874"), outline="", smooth=True, tags="world"))
            add(c.create_oval(x - m(1.0), G - m(1.35), x + m(1.1), G + m(0.05), fill=dim("#1a1c20"), outline="",
                              tags="world"))
        elif p.kind == "curio":                                 # a glowing crystal ~0.45 m
            add(c.create_polygon(x - m(0.12), G, x - m(0.06), G - m(0.38), x + m(0.02), G - m(0.46), x + m(0.1), G - m(0.3),
                                 x + m(0.14), G, fill=_mix_hex("#7ee0c8", "#1a2a30", 0.3 - 0.2 * lit), outline="",
                                 tags="world"))
            add(c.create_line(x - m(0.03), G - m(0.35), x + m(0.01), G - m(0.08), fill="#d8fff2", width=1, tags="world"))


_rw_prev_draw_pois = _sc_draw_pois                      # m46 defers valley/road POIs to this
