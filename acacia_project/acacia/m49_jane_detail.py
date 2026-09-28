# ============================================================================
# [NEW] JANE - PAINTED DETAIL  (2D, same renderer; layered on the part hooks)
# ============================================================================
#
# Jane stays the same 2D procedural character. This adds the layers that
# make a flat figure read as a lit, physical one - each drawn inside the
# existing part hooks so stacking stays correct, each LOD-gated so normal
# gameplay adds ~25 items and close-ups get the full detail:
#
#   volume   a directional cast shadow on the ground (away from the sky
#            light), rim light along the lit edge of legs, arms and torso
#   hair     strand lines through the crown and along each pigtail's curve,
#            alternating highlight and shadow tones
#   fabric   folds under the bust and at the waist, side seams, a hem
#            highlight; denim seams + knee creases; knit ribbing; trench
#            lapel and gathered folds at the belt
#   shoes    sole line, toe highlight, and stitching up close
#   motion   eye saccades (small, quick gaze shifts that settle) and
#            fleeting micro-expressions driven by her mood
# Colours derive from the outfit palette, so no alpha is needed.

import math as _jd_math
import random as _jd_random

_JD_LIGHT = (0.62, -0.78)                        # key light: upper right (sun/moon side)


def _jd_on(self):
    return bool(self.SHAPE.get("face_hd"))


def _jd_rim(self, pts, offs, col, width):
    """A thin lit edge offset from a bone chain toward the key light."""
    out = []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = _jd_math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        if nx * _JD_LIGHT[0] + ny * _JD_LIGHT[1] < 0:
            nx, ny = -nx, -ny
        out += [x + nx * offs[i], y + ny * offs[i]]
    if len(out) >= 4:
        self._line(*out, fill=col, width=width, smooth=True)


# ---- cast shadow: first body layer (drawn before the back hair) -------------
_jd_prev_hair_back = Creature._draw_hair_back


def _jd_hair_back(self, neck, tilt, A, lod, low):
    sun = self.__dict__.get("_sunlight", 0.0)
    if _jd_on(self) and not low and sun > 0.35:
        # only real sunlight casts a shadow: anchored at her feet, stretching
        # away from the sun, longer when it is low, ground-toned (not black)
        H = self._H()
        g = self._terrain_at(self.x) - 1.0
        fl, fr = min(self._loco.foot["L"], self._loco.foot["R"]), max(self._loco.foot["L"], self._loco.foot["R"])
        L = (1.6 + 2.2 * (1.0 - self.__dict__.get("_sun_high", 0.6))) * H
        col = _mix_hex("#3b5a33", "#1f2e1c", clamp01((sun - 0.35) / 0.65))
        self._poly([fl - 0.3 * H, g + 0.05 * H, fr + 0.3 * H, g + 0.05 * H, fr - L + 0.4 * H, g + 0.55 * H,
                    fl - L - 0.2 * H, g + 0.4 * H], col, "", smooth=True)
    return _jd_prev_hair_back(self, neck, tilt, A, lod, low)


Creature._draw_hair_back = _jd_hair_back


# ---- hair: strands through the crown ------------------------------------------
_jd_prev_hair_volume = Creature._draw_hair_volume


def _jd_hair_volume(self, hx, hy, lod, low):
    r = _jd_prev_hair_volume(self, hx, hy, lod, low)
    if _jd_on(self) and not low:
        main = JANE_LOOK["hair"]
        hi = _mix_hex(main, JANE_LOOK["hair_hi"], 0.7)
        dk = JANE_LOOK["hair_dark"]
        n = 4 if lod == 0 else 9
        for k in range(n):
            f = (k + 0.5) / n
            side = -1 if k % 2 == 0 else 1
            x0 = hx + side * (1.5 + 3 * f)
            y0 = hy - 31 + 2 * f
            x1 = hx + side * (17 + 9 * f)
            y1 = hy - 22 + 10 * f
            self._line(x0, y0, (x0 + x1) / 2 + side * 3, (y0 + y1) / 2 - 4, x1, y1,
                       fill=hi if k % 3 != 2 else dk, width=1, smooth=True)
    return r


Creature._draw_hair_volume = _jd_hair_volume


# ---- pigtails: strands that follow the same pendulum curve --------------------
_jd_prev_pigtail = _j_pigtail                 # a module helper the makeup pass calls by name


def _jd_pigtail(self, hx, hy, side, lod, low):
    r = _jd_prev_pigtail(self, hx, hy, side, lod, low)
    if not low:
        wet = self._cloth_body()["wet"]
        swing = self.__dict__.get("_cloth_x", 0.0)
        tx, ty = hx + side * 27.0, hy - 32.0
        spread = 1.0 - 0.35 * wet
        nodes, wid = [], []
        for t in (0.0, 0.18, 0.4, 0.62, 0.82, 1.0):
            out = side * (9.0 + 13.0 * _jd_math.sin(min(1.0, t * 1.6) * _jd_math.pi * 0.5)) * spread
            x = tx + out - swing * 1.4 * t * t + _jd_math.sin(t * 6.0 + self.t * 1.6 + side) * 1.2 * t
            nodes.append((x, ty + t * 104.0))
            wid.append((7.5 + 6.0 * _jd_math.sin(t * _jd_math.pi) * spread) * (1.0 - 0.55 * t) + 1.2)
        main = _shade(JANE_LOOK["hair"], 1.0 - 0.3 * wet)
        hi = _mix_hex(main, JANE_LOOK["hair_hi"], 0.75 - 0.3 * wet)
        dk = _shade(main, 0.78)
        offs = (-0.6, 0.05, 0.55) if lod == 0 else (-0.7, -0.45, -0.15, 0.1, 0.35, 0.62)
        for j, off in enumerate(offs):
            pts = []
            for (x, y), w in zip(nodes, wid):
                pts += [x + w * off * (0.9 + 0.1 * _jd_math.sin(y * 0.05 + j)), y]
            self._line(*pts, fill=hi if j % 2 else dk, width=1, smooth=True)
    return r


_j_pigtail = _jd_pigtail


# ---- torso: folds, seams, hem light, rim --------------------------------------
_jd_prev_shirt = Creature._draw_shirt


def _jd_shirt(self, pelvis, pelvis_top, spine1, chest, arms, pw, b, lod, low):
    r = _jd_prev_shirt(self, pelvis, pelvis_top, spine1, chest, arms, pw, b, lod, low)
    if not _jd_on(self) or low:
        return r
    H = self._H()
    outfit = _j_outfit(self)
    top, bottom, _shoes = JANE_LOOK[outfit]
    cx, cy = chest
    px_, py_ = pelvis
    fold = _shade(top, 0.8)
    light = _mix_hex(top, "#ffffff", 0.35)
    if outfit in ("light", "normal"):
        # soft tension folds under the bust toward the waist
        for s in (-1, 1):
            self._line(cx + s * 0.35 * H, cy + 0.55 * H, cx + s * 0.18 * H, cy + 1.05 * H,
                       px_ + s * 0.1 * H, py_ - 0.9 * H, fill=fold, width=1, smooth=True)
        self._line(px_ - 0.9 * H, py_ + 1.25 * H, px_ + 0.9 * H, py_ + 1.25 * H,
                   fill=_mix_hex(bottom, "#ffffff", 0.3), width=1)                  # hem light
    elif outfit == "warm":
        n = 3 if lod == 0 else 7                                                    # knit ribbing
        for k in range(n):
            x = cx - 0.6 * H + 1.2 * H * (k + 0.5) / n
            self._line(x, cy + 0.2 * H, x + (px_ - cx) * 0.3, py_ - 0.2 * H, fill=fold, width=1)
    elif outfit == "rain":
        for s in (-1, 1):                                                           # lapels + belt gathers
            self._line(cx + s * 0.1 * H, cy - 0.55 * H, cx + s * 0.45 * H, cy + 0.35 * H, fill=fold, width=1)
            self._line(px_ + s * 0.25 * H, py_ - 0.2 * H, px_ + s * 0.55 * H, py_ + 0.9 * H, fill=fold, width=1)
    # side seam + rim light on the lit side of the torso
    self._line(cx + 0.72 * H, cy + 0.1 * H, px_ + 0.62 * H, py_ - 0.1 * H, fill=_shade(top, 0.72), width=1)
    _jd_rim(self, [(cx + 0.55 * H, cy - 0.4 * H), (cx + 0.6 * H, cy + 0.6 * H), (px_ + 0.5 * H, py_ - 0.2 * H)],
            [0.25 * H, 0.2 * H, 0.18 * H], light, 1 if lod == 0 else 2)
    if lod >= 1:                                                                    # fine weave up close
        for k in range(5):
            y = cy + 0.1 * H + k * 0.28 * H
            self._line(cx - 0.45 * H, y, cx + 0.45 * H, y + 0.12 * H, fill=_mix_hex(top, fold, 0.35), width=1)
    return r


Creature._draw_shirt = _jd_shirt


# ---- legs: seams/creases (denim), rim light (skin or cloth) --------------------
_jd_prev_pants = Creature._draw_pants


def _jd_pants(self, side, hip, knee, ankle, b, lod, low, face):
    r = _jd_prev_pants(self, side, hip, knee, ankle, b, lod, low, face)
    if not _jd_on(self) or low:
        return r
    H = self._H()
    outfit = _j_outfit(self)
    top, bottom, _s = JANE_LOOK[outfit]
    far = self._far(side) if hasattr(self, "_far") else False
    if outfit == "warm":                                                            # jeans
        self._line(hip[0] + 0.2 * H, hip[1], knee[0] + 0.18 * H, knee[1], ankle[0] + 0.12 * H, ankle[1],
                   fill=_mix_hex(bottom, "#c9a76a", 0.35), width=1, smooth=True)     # outer seam, gold thread
        for k in (-1, 1):
            self._line(knee[0] - 0.2 * H, knee[1] + k * 0.12 * H, knee[0] + 0.15 * H, knee[1] + k * 0.08 * H,
                       fill=_shade(bottom, 0.7), width=1)                           # knee creases
        col = _mix_hex(bottom, "#dfe8ff", 0.35)
    else:
        col = _mix_hex(self._skin_tone(), "#fff4e8", 0.45)                          # bare leg catching light
    if not far:
        _jd_rim(self, [hip, knee, ankle], [0.3 * H, 0.2 * H, 0.13 * H], col, 1 if lod == 0 else 2)
    return r


Creature._draw_pants = _jd_pants


# ---- shoes: sole, toe highlight, stitching -------------------------------------
_jd_prev_shoe = Creature._draw_shoe


def _jd_shoe(self, side, ankle, b, lod, low, face):
    r = _jd_prev_shoe(self, side, ankle, b, lod, low, face)
    if not _jd_on(self) or low:
        return r
    H = self._H()
    _t, _b, shoes = JANE_LOOK[_j_outfit(self)]
    fx = 1.0 if face >= 0 else -1.0
    ax, ay = ankle
    g = self._terrain_at(ax) - 0.5
    self._line(ax - 0.25 * H * fx, g, ax + 0.75 * H * fx, g, fill=_shade(shoes, 0.45), width=2)      # sole
    self._line(ax + 0.35 * H * fx, g - 0.28 * H, ax + 0.62 * H * fx, g - 0.12 * H,
               fill=_mix_hex(shoes, "#ffffff", 0.55), width=1)                                        # toe gloss
    if lod >= 1:
        for k in range(4):
            sx = ax + (0.0 + 0.18 * k) * H * fx
            self._line(sx, g - 0.12 * H, sx + 0.06 * H * fx, g - 0.12 * H, fill=_shade(shoes, 0.7), width=1)
    return r


Creature._draw_shoe = _jd_shoe


# ---- arms: rim light over skin or sleeve ---------------------------------------
_jd_prev_sleeve = Creature._draw_sleeve


def _jd_sleeve(self, side, shoulder, elbow, wrist, b, lod, low):
    r = _jd_prev_sleeve(self, side, shoulder, elbow, wrist, b, lod, low)
    if not _jd_on(self) or low:
        return r
    far = self._far(side) if hasattr(self, "_far") else False
    if far:
        return r
    H = self._H()
    outfit = _j_outfit(self)
    top = JANE_LOOK[outfit][0]
    col = _mix_hex(top, "#ffffff", 0.35) if outfit in ("warm", "rain") else _mix_hex(self._skin_tone(), "#fff4e8", 0.45)
    _jd_rim(self, [shoulder, elbow, wrist], [0.2 * H, 0.14 * H, 0.1 * H], col, 1 if lod == 0 else 2)
    return r


Creature._draw_sleeve = _jd_sleeve


# ---- motion: saccades and micro-expressions ------------------------------------
_jd_prev_affect = Creature._affect_step


def _jd_affect(self, dt):
    r = _jd_prev_affect(self, dt)
    if not _jd_on(self):
        return r
    d = self.__dict__
    # saccades: a quick hop to a new fixation point, then holding still
    d["_sac_t"] = d.get("_sac_t", 0.0) - dt
    if d["_sac_t"] <= 0:
        d["_sac_t"] = _jd_random.uniform(0.6, 2.6)
        d["_sac_goal"] = (_jd_random.uniform(-0.9, 0.9), _jd_random.uniform(-0.45, 0.35))
    gx, gy = d.get("_sac_goal", (0.0, 0.0))
    sx, sy = d.get("_sac", (0.0, 0.0))
    k = min(1.0, dt * 22.0)                                            # saccades are fast
    sx += (gx - sx) * k
    sy += (gy - sy) * k
    d["_sac"] = (sx, sy)                                               # applied after update (below)
    # micro-expressions: a flicker of what she feels, gone in a moment
    A = getattr(self, "_affect", None)
    if isinstance(A, dict):
        d["_micro_t"] = d.get("_micro_t", 0.0) - dt
        if d["_micro_t"] <= 0:
            d["_micro_t"] = _jd_random.uniform(3.0, 9.0)
            pos = A.get("smile", 0.0)
            d["_micro"] = _jd_random.choice((("smile", 0.25 + 0.3 * max(0.0, pos)), ("brow_out", 0.3),
                                              ("brow_in", 0.2 if pos < 0.1 else 0.08)))
            d["_micro_age"] = 0.0
        m = d.get("_micro")
        if m:
            d["_micro_age"] = d.get("_micro_age", 0.0) + dt
            env = max(0.0, _jd_math.sin(min(1.0, d["_micro_age"] / 0.45) * _jd_math.pi))
            if d["_micro_age"] < 0.45:
                A = dict(A)
                A[m[0]] = A.get(m[0], 0.0) + m[1] * env
                self._affect = A
    return r


Creature._affect_step = _jd_affect


# the renderer sets look_x/look_y absolutely each update; the saccade is
# added after that, so it can't be overwritten or accumulate
_jd_prev_update = Creature.update


def _jd_update(self, dt):
    r = _jd_prev_update(self, dt)
    if _jd_on(self):
        sx, sy = self.__dict__.get("_sac", (0.0, 0.0))
        self.look_x = getattr(self, "look_x", 0.0) + sx
        self.look_y = getattr(self, "look_y", 0.0) + sy
    return r


Creature.update = _jd_update


# the world tells her body how much sun there is (for the cast shadow)
_jd_prev_app_update = App._update_world


def _jd_app_update(self, dt):
    _jd_prev_app_update(self, dt)
    try:
        wx = self.weather_sim.snapshot() if getattr(self, "weather_sim", None) else {}
        day = self.world.daypart in ("morning", "afternoon")
        c = self.creature
        c._sunlight = (1.0 if day else 0.0) * (1.0 - clamp01(wx.get("cloud", 0.3))) * (1.0 - clamp01(wx.get("precip", 0.0) * 2))
        c._sun_high = clamp01(wx.get("sun", 0.6))
    except Exception:
        pass


App._update_world = _jd_app_update
