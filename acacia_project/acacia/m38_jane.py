# ============================================================================
# [NEW] JANE  (patch layer, loaded last)
# ============================================================================
#
# Jane is the permanent character: an adult woman (28) with an INTJ mind and
# a deliberately glamorous, hyper-feminine look. Everything here drives the
# EXISTING renderer and brain - the rig's shape table, the garment/hair
# methods it already calls, and the personality system - so there is still
# one Creature, one renderer, one mind.
#
#   body      hourglass proportions through Creature.SHAPE (hips, waist,
#             ribcage, bust, narrower shoulders, softer jaw, smaller nose)
#   poise     a hip-led walk (sway + weight transfer), contrapposto at rest,
#             chin up, a composed half-smile and steady eye contact - her
#             magnetism is confidence and body language, not explicitness
#   styling   long voluminous hair that moves, full lips, lipstick, liner,
#             lashes, eyeshadow, blush, hoops and a pendant
#   wardrobe  fitted tops shaped over the bust, skirts that flare and
#             flutter, heels that really lift her, jeans + boots when cold,
#             a belted trench in rain - chosen by the mind's comfort system
#   mind      INTJ profile loaded through apply_profile(): analytical,
#             private, strategic, observant, selective - and still warm
#             underneath (emotions are fully present, just held with poise)

# Half-widths are fractions of H (head height). Full widths: hips ~1.9H,
# waist ~0.95H, ribcage ~1.36H, shoulders ~1.75H - a pronounced but coherent
# hourglass on an adult 8-head skeleton, with long legs (legs ~50% of height).
JANE_SHAPE = {
    "hip": 0.95, "waist": 0.475, "rib": 0.68, "bust": 1.3, "hip_span": 1.14,
    "shoulder": 0.9, "sway": 1.0, "jaw": 0.84, "nose": 0.78, "stride": 1.1,
    "thigh": 1.08, "legs": 1.02, "stance": 0.95, "speed": 1.9,
    "lips": 1.18, "lip_col": "#b3264e", "lip_amt": 0.6, "brow_w": 2, "brow_arch": 1.0,
    "hood": False,
}
JANE_LOOK = {
    "hair": "#e9d2a4", "hair_dark": "#b58f5c", "hair_hi": "#fff4dc",
    "liner": "#17100f", "lash": "#0f0a0a", "shadow": "#9a5d7c", "blush": "#e2707e",
    "gold": "#e0b24c",
    # outfit -> (top, bottom, shoes)
    "light": ("#e8588c", "#f6f1ea", "#e7c6b0"),
    "normal": ("#e8588c", "#2a2328", "#15111a"),
    "warm": ("#f2e6d8", "#2d3f66", "#3a2a24"),
    "rain": ("#c89868", "#2a2328", "#2a1f1c"),
}

Creature.SHAPE = JANE_SHAPE


def _j_outfit(self):
    return self._cloth_body().get("outfit", "normal")


def _j_heel(self):
    """(pitch radians, ankle rise in build units) for the current shoes."""
    o = _j_outfit(self)
    # (pitch, ankle rise in body units of H/22): pumps ~0.28H, boots ~0.1H
    return (0.34, 6.2) if o in ("light", "normal") else (0.12, 2.2)


def _j_hair_col(self):
    return JANE_LOOK["hair"]


def _j_palette(self):
    top, bottom, shoes = JANE_LOOK[_j_outfit(self)]
    return (top, bottom, shoes, JANE_LOOK["warm"][0], JANE_LOOK["rain"][0])


def _j_head_pos(self, neck, tilt, A):
    b = self.build
    hx = neck[0] + tilt * 0.3 + self.skull_shift + self.head_yaw * 4.0
    hy = neck[1] - 17.0 + self.head_pitch * 3.5
    hy += 3.2 * A["gaze"] - 2.0 * max(0.0, A["chest"]) - 1.4 * max(0.0, A["shoulder"])
    return hx, hy


# ---------------------------------------------------------------- hair

def _j_hair_back(self, neck, tilt, A, lod, low):
    """The long mass behind head and shoulders, falling to mid-back. It trails
    the cloth spring more the further it is from the crown, lies flatter and
    darker when wet, and splits into soft waves at the ends."""
    hx, hy = _j_head_pos(self, neck, tilt, A)
    bd = self._cloth_body()
    wet = bd["wet"]
    swing = self.__dict__.get("_cloth_x", 0.0)
    self._head_scale_begin(hx, hy + 17.0, self._H() / 55.5)
    try:
        dark = _shade(JANE_LOOK["hair_dark"], 1.0 - 0.3 * wet)
        main = _shade(JANE_LOOK["hair"], 1.0 - 0.3 * wet)
        vol = 1.0 - 0.3 * wet
        length = 133.0 - 14.0 * wet               # to mid-back: chin + ~2H
        for layer, col, grow in ((0, dark, 1.08), (1, main, 1.0)):
            pts = []
            n = 9
            for i in range(n + 1):                       # left side, crown -> tips
                t = i / n
                y = hy - 34 + t * (length + 34)
                w = (36 + 12 * _cw_math.sin(t * _cw_math.pi * 0.9) * vol) * grow
                x = hx - w - swing * t * t * 1.6 + _cw_math.sin(t * 7.0 + self.t * 1.3) * 1.4 * t
                pts += [x, y]
            for k in range(5):                           # wavy ends
                u = k / 4.0
                x = hx - 40 * grow + u * 80 * grow - swing * 1.6
                y = hy + length + 5 * _cw_math.sin(u * _cw_math.pi * 3 + self.t * 0.9)
                pts += [x, y]
            for i in range(n, -1, -1):                   # right side, tips -> crown
                t = i / n
                y = hy - 34 + t * (length + 34)
                w = (36 + 12 * _cw_math.sin(t * _cw_math.pi * 0.9) * vol) * grow
                x = hx + w - swing * t * t * 1.6 + _cw_math.sin(t * 7.0 + self.t * 1.3 + 1.1) * 1.4 * t
                pts += [x, y]
            self._poly(pts, col, "", smooth=True)
        if not low and lod >= 1:
            hi = _mix_hex(main, JANE_LOOK["hair_hi"], 0.45 - 0.3 * wet)
            for k in range(7):                           # long S-strands of shine
                off = -30 + k * 10
                self._line(hx + off, hy - 20,
                           hx + off * 1.15 - swing * 0.4, hy + 25,
                           hx + off * 1.2 + 4 * _cw_math.sin(k), hy + 55,
                           hx + off * 1.1 - swing * 1.4, hy + length - 6,
                           fill=hi if k % 2 else _shade(main, 0.85), width=1, smooth=True)
    finally:
        self._head_scale_end()


def _j_hair_volume(self, hx, hy, lod, low):
    """Crown volume + a deep side part with a swept fringe; drawn in head
    space over the skull, before the face features."""
    bd = self._cloth_body()
    wet = bd["wet"]
    main = _shade(JANE_LOOK["hair"], 1.0 - 0.3 * wet)
    swing = self.__dict__.get("_cloth_x", 0.0) * 0.3
    lift = 5.0 * (1.0 - 0.5 * wet)
    crown = []
    for i in range(13):
        a = _cw_math.pi * (1.0 + i / 12.0)
        crown += [hx + _cw_math.cos(a) * 37.0 + swing * _cw_math.sin(i / 12 * _cw_math.pi),
                  hy - 19.0 + _cw_math.sin(a) * (21.0 + lift)]
    # side part at hx+9: sweep across the forehead to the left temple
    crown += [hx + 33, hy - 16, hx + 22, hy - 25, hx + 9, hy - 31,
              hx - 6, hy - 28, hx - 20, hy - 22, hx - 31, hy - 12, hx - 35, hy - 2]
    self._poly(crown, main, "", smooth=True)
    if not low:
        hi = _mix_hex(main, JANE_LOOK["hair_hi"], 0.5 - 0.3 * wet)
        self._line(hx + 9, hy - 31, hx - 8, hy - 38 - lift * 0.6, hx - 26, hy - 30,
                   fill=hi, width=2, smooth=True)
        self._line(hx + 9, hy - 31, hx + 9, hy - 40 - lift * 0.5, fill=_shade(main, 0.7), width=1)


def _j_front_locks(self, hx, hy, lod, low):
    """Two long face-framing locks falling in front of the shoulders."""
    wet = self._cloth_body()["wet"]
    col = _shade(JANE_LOOK["hair"], 0.95 - 0.3 * wet)
    swing = self.__dict__.get("_cloth_x", 0.0)
    for side in (-1, 1):
        x0 = hx + side * 30
        pts = [x0, hy - 18, x0 + side * 7, hy - 6]
        for t in (0.25, 0.5, 0.75, 1.0):
            pts += [x0 + side * (8 + 4 * _cw_math.sin(t * 5)) - swing * t * 0.9,
                    hy + t * 84]
        pts += [x0 - side * 2 - swing * 0.9, hy + 86]
        for t in (0.75, 0.5, 0.25):
            pts += [x0 - side * (1 - 3 * _cw_math.sin(t * 5)) - swing * t * 0.9, hy + t * 82]
        pts += [x0 - side * 3, hy - 8]
        self._poly(pts, col, "", smooth=True)
        if not low:
            self._line(x0 + side * 4, hy - 10, x0 + side * 7 - swing * 0.4, hy + 40,
                       x0 + side * 4 - swing * 0.9, hy + 80,
                       fill=_mix_hex(col, JANE_LOOK["hair_hi"], 0.4), width=1, smooth=True)


# -------------------------------------------------------------- makeup

def _j_makeup(self, hx, hy, head_color, lod, low):
    """Eyeshadow, winged liner, mascara lashes, blush, hoops - in head space,
    after the face so it sits on top of the skin. Lids follow openness."""
    o = self.__dict__.get("_eye_o", 1.0)
    ry = max(0.3, 5.4 * o)
    for side in (-1, 1):
        ex, ey = hx + side * 14, hy - 14
        lid = ey - ry
        # eyeshadow: soft band between lid and crease
        self._poly([ex - 7.4, lid + 0.4, ex, lid - 3.6, ex + 7.4, lid + 0.4,
                    ex + side * 8.2, lid - 1.6, ex, lid - 5.2, ex - side * 8.2, lid - 1.6],
                   _mix_hex(head_color, JANE_LOOK["shadow"], 0.5), "", smooth=True)
        # liner along the lid with a flicked wing at the outer corner
        self._line(ex - side * 7.2, lid + 1.6 + ry * 0.35, ex - side * 2.5, lid - 0.1,
                   ex + side * 3.5, lid, ex + side * 7.6, lid + 1.4 + ry * 0.1,
                   ex + side * 11.0, lid - 2.4,
                   fill=JANE_LOOK["liner"], width=2, smooth=True)
        if not low:
            for k in range(5):                     # mascara: long, curled, fanned
                u = k / 4.0
                bx = ex - side * 5.5 + side * u * 12.0
                by = lid + 0.2 + 0.6 * abs(u - 0.5)
                lx = side * (0.8 + 2.2 * u)
                self._line(bx, by, bx + lx * 0.6, by - 2.6, bx + lx, by - 3.8,
                           fill=JANE_LOOK["lash"], width=1, smooth=True)
        # blush high on the cheekbone
        self._oval(hx + side * 19 - 5.5, hy - 3.2, hx + side * 19 + 5.5, hy + 1.8,
                   _mix_hex(head_color, JANE_LOOK["blush"], 0.3), "")
        # gold hoops, swinging a little with motion
        sw = self.__dict__.get("_cloth_x", 0.0) * 0.25
        ex2, ey2 = hx + side * 33.5 + sw, hy + 4.0
        self._oval(ex2 - 3.2, ey2 - 0.5, ex2 + 3.2, ey2 + 7.0, "", JANE_LOOK["gold"])
    if not low:
        _j_front_locks(self, hx, hy, lod, low)


# ------------------------------------------------------------- wardrobe

def _j_bust(self, chest, pw, b, col, lod, low):
    """Two soft volumes under the fabric: underside shadow, body, and a
    highlight on the side facing the key light."""
    r = pw * 0.235 * JANE_SHAPE["bust"]
    klx, kly = _KEY_LIGHT
    for side in (-1, 1):
        cx, cy = chest[0] + side * pw * 0.3, chest[1] + pw * 0.3
        self._oval(cx - r, cy - r * 0.62, cx + r, cy + r * 1.0, _shade(col, 0.74), "")
        self._oval(cx - r * 0.98, cy - r * 0.8, cx + r * 0.98, cy + r * 0.82, col, "")
        if not low:
            hx, hy = cx + klx * r * 0.35, cy + kly * r * 0.3
            self._oval(hx - r * 0.42, hy - r * 0.3, hx + r * 0.42, hy + r * 0.3,
                       _mix_hex(col, "#ffffff", 0.2), "")
    if not low:                                     # tension folds toward the waist
        for side in (-1, 1):
            self._line(chest[0] + side * pw * 0.3, chest[1] + pw * 0.55,
                       chest[0] + side * pw * 0.14, chest[1] + pw * 0.95,
                       fill=_shade(col, 0.82), width=1, smooth=True)


def _j_shirt(self, pelvis, pelvis_top, spine1, chest, arms, pw, b, lod, low):
    S, bd = JANE_SHAPE, self._cloth_body()
    o = bd["outfit"]
    top, bottom, _sh = JANE_LOOK[o]
    wet = bd["wet"] * (0.2 if o == "rain" else 1.0)
    top = _shade(top, 1.0 - 0.25 * wet)
    bottom = _shade(bottom, 1.0 - 0.25 * wet)
    lsh, rsh = arms["L"][0], arms["R"][0]
    hipw, waist, rib = pw * S["hip"], pw * S["waist"], pw * S["rib"]
    cx = self.__dict__.get("_cloth_x", 0.0)
    walk = _cw_math.sin(self._loco.phase * _cw_math.tau) * min(1.0, self._loco.speed / 40.0)

    if o == "rain":                                 # belted trench, knee length
        hem = pelvis[1] + 2.0 * pw               # trench to the knee
        coat = [lsh[0] - 1.8 * b, lsh[1] - 1.2 * b, chest[0] - 5 * b, chest[1] - 1.5 * b,
                chest[0] + 5 * b, chest[1] - 1.5 * b, rsh[0] + 1.8 * b, rsh[1] - 1.2 * b,
                rsh[0] + 1.2 * b, rsh[1] + 9 * b, spine1[0] + rib * 1.02, spine1[1],
                pelvis_top[0] + waist * 1.1, pelvis_top[1],
                pelvis[0] + hipw * 1.06, pelvis[1],
                pelvis[0] + hipw * 1.18 + cx * 0.9 + walk * 2.5 * b, hem,
                pelvis[0] + cx * 1.1, hem + 2 * b,
                pelvis[0] - hipw * 1.18 + cx * 0.9 + walk * 2.5 * b, hem,
                pelvis[0] - hipw * 1.06, pelvis[1], pelvis_top[0] - waist * 1.1, pelvis_top[1],
                spine1[0] - rib * 1.02, spine1[1], lsh[0] - 1.2 * b, lsh[1] + 9 * b]
        self._poly(coat, top, "", smooth=True)
        _j_bust(self, chest, pw, b, top, lod, low)
        self._poly([pelvis_top[0] - waist * 1.14, pelvis_top[1] - 1.6 * b,
                    pelvis_top[0] + waist * 1.14, pelvis_top[1] - 1.6 * b,
                    pelvis_top[0] + waist * 1.14, pelvis_top[1] + 1.6 * b,
                    pelvis_top[0] - waist * 1.14, pelvis_top[1] + 1.6 * b],
                   _shade(top, 0.72), "")
        if not low:
            self._line(chest[0], chest[1] + 4 * b, pelvis[0] + cx, hem,
                       fill=_shade(top, 0.7), width=1)
            for k in range(3):
                for side in (-1, 1):
                    yy = chest[1] + (7 + k * 5) * b
                    xx = chest[0] + side * 3.2 * b
                    self._oval(xx - 0.8 * b, yy - 0.8 * b, xx + 0.8 * b, yy + 0.8 * b,
                               _shade(top, 0.55), "")
            self._line(chest[0] + _KEY_LIGHT[0] * 7 * b, chest[1] + 4 * b,
                       pelvis[0] + _KEY_LIGHT[0] * 10 * b, hem - 4 * b,
                       fill=_mix_hex(top, "#ffffff", 0.25), width=2, smooth=True)
        return

    crop = o == "light"
    hem_top = (spine1[1] + pelvis_top[1]) * 0.5 if crop else pelvis_top[1] + 1.5 * b
    shirt = [lsh[0] - 1.0 * b, lsh[1] - 0.8 * b,
             chest[0] - 6.5 * b, chest[1] - 1.0 * b,
             chest[0], chest[1] + 5.5 * b,                     # scoop neckline
             chest[0] + 6.5 * b, chest[1] - 1.0 * b,
             rsh[0] + 1.0 * b, rsh[1] - 0.8 * b,
             rsh[0] + 0.6 * b, rsh[1] + 7.5 * b,
             spine1[0] + rib * 1.0, spine1[1],
             spine1[0] + (waist * 1.02 if crop else waist * 1.04), hem_top,
             spine1[0] - (waist * 1.02 if crop else waist * 1.04), hem_top,
             spine1[0] - rib * 1.0, spine1[1],
             lsh[0] - 0.6 * b, lsh[1] + 7.5 * b]
    if o == "warm":                                             # cropped jacket over a knit
        self._poly(shirt, top, "", smooth=True)
        _j_bust(self, chest, pw, b, top, lod, low)
        jacket = _shade("#8a6a52", 1.0 - 0.25 * wet)
        for side in (-1, 1):
            sh = lsh if side < 0 else rsh
            self._poly([sh[0] + side * 1.8 * b, sh[1] - 1.2 * b, chest[0] + side * 5.5 * b,
                        chest[1] - 1.2 * b, chest[0] + side * 4.0 * b, spine1[1],
                        spine1[0] + side * rib * 0.7, pelvis_top[1] - 1 * b,
                        spine1[0] + side * rib * 1.05, pelvis_top[1] - 1 * b,
                        spine1[0] + side * rib * 1.06, spine1[1],
                        sh[0] + side * 1.2 * b, sh[1] + 9 * b], jacket, "", smooth=True)
            if not low:
                self._line(chest[0] + side * 5.5 * b, chest[1], chest[0] + side * 8 * b,
                           chest[1] + 6 * b, chest[0] + side * 4.2 * b, chest[1] + 11 * b,
                           fill=_shade(jacket, 0.7), width=1, smooth=True)
        return
    self._poly(shirt, top, "", smooth=True)
    _j_bust(self, chest, pw, b, top, lod, low)
    if crop and not low:                                       # a glimpse of waist + navel
        nav = (pelvis_top[0], (hem_top + pelvis_top[1]) * 0.5 + 1.0 * b)
        self._oval(nav[0] - 0.7 * b, nav[1] - 0.9 * b, nav[0] + 0.7 * b, nav[1] + 0.9 * b,
                   _shade(self._skin_tone(), 0.62), "")
    # skirt: waistband high on the waist, over the hips, flaring to the hem
    mini = o == "light"
    hem = pelvis[1] + (0.95 if mini else 1.55) * pw     # mid-thigh / above the knee
    flare = (1.14 if mini else 0.98)
    wave = _cw_math.sin(self.t * 5.0) * 0.8 * b * min(1.0, abs(cx) / 4.0 + abs(walk))
    skirt = [pelvis_top[0] - waist * 1.06, pelvis_top[1],
             pelvis_top[0] + waist * 1.06, pelvis_top[1],
             pelvis[0] + hipw * 1.04, pelvis[1],
             pelvis[0] + hipw * flare + cx * 0.6 + walk * 2.2 * b, hem + wave,
             pelvis[0] + cx * 0.8, hem + 1.2 * b - wave,
             pelvis[0] - hipw * flare + cx * 0.6 + walk * 2.2 * b, hem + wave,
             pelvis[0] - hipw * 1.04, pelvis[1]]
    self._poly(skirt, bottom, "", smooth=True)
    if not low:
        self._limb_light([pelvis_top, pelvis, (pelvis[0], hem)],
                         [waist * 1.04, hipw * 1.0, hipw * flare * 0.95], bottom, lod, ruddy=False)
        self._line(pelvis_top[0] - waist * 1.06, pelvis_top[1] + 1.2 * b,
                   pelvis_top[0] + waist * 1.06, pelvis_top[1] + 1.2 * b,
                   fill=_shade(bottom, 0.7), width=2)
        for k in (-1, 1):                                       # drape folds
            self._line(pelvis[0] + k * hipw * 0.5, pelvis[1] + 2 * b,
                       pelvis[0] + k * hipw * 0.62 + cx * 0.4, hem - 1 * b,
                       fill=_shade(bottom, 0.8), width=1, smooth=True)


def _j_pants(self, side, hip, knee, ankle, b, lod, low, face):
    """Skirt outfits: sheer tights (normal/rain) or bare legs with a glossy
    shin highlight (light). Cold weather: skinny jeans."""
    o = _j_outfit(self)
    nodes = [hip, ((hip[0] + knee[0]) * 0.5, (hip[1] + knee[1]) * 0.5), knee,
             ((knee[0] + ankle[0]) * 0.5, (knee[1] + ankle[1]) * 0.5), (ankle[0], ankle[1] - 1.5 * b)]
    if o == "warm":
        col = _shade(JANE_LOOK["warm"][1], (1.0 - 0.25 * self._cloth_body()["wet"]) * self._far(side))
        wid = [w * 1.07 for w in self._leg_wid()]
        self._poly(_chain_skin(nodes, wid, 1.06, 0.2), col, "", smooth=True)
        if not low:
            self._limb_light(nodes, wid, col, lod, ruddy=False)
            self._line(hip[0] + face * 7.4 * b, hip[1], knee[0] + face * 5.8 * b, knee[1],
                       ankle[0] + face * 3.8 * b, ankle[1] - 2 * b, fill="#c79a4a", width=1,
                       smooth=True)                              # contrast seam
        return
    if o in ("normal", "rain"):
        col = _shade(_mix_hex(self._skin_tone(), "#8a5e4a", 0.2), self._far(side))   # sheer nude: skin, faintly tinted
        wid = [w * 1.01 for w in self._leg_wid()]
        self._poly(_chain_skin(nodes, wid, 1.12, 0.28), col, "", smooth=True)
    else:
        col = self._skin_tone()
    if not low:
        klx = _KEY_LIGHT[0]
        self._line(knee[0] + klx * 2.5 * b, knee[1] + 2 * b,
                   (knee[0] + ankle[0]) * 0.5 + klx * 3.0 * b, (knee[1] + ankle[1]) * 0.5,
                   ankle[0] + klx * 1.6 * b, ankle[1] - 4 * b,
                   fill=_mix_hex(col, "#ffffff", 0.3), width=1, smooth=True)


def _j_shoe(self, side, ankle, b, lod, low, face):
    """Pumps with a stiletto (skirt outfits) or ankle boots (cold / rain).
    Drawn inside the foot's rotation scope, so they roll with the gait."""
    o = _j_outfit(self)
    col = JANE_LOOK[o][2]
    fx, fy = ankle
    heel, toe = fx - face * 4.0 * b, fx + face * 12.5 * b
    if o in ("light", "normal"):
        self._poly([heel, fy - 0.8 * b, fx + face * 3.0 * b, fy + 1.0 * b,
                    toe - face * 1.4 * b, fy + 4.4 * b, toe + face * 1.2 * b, fy + 5.8 * b,
                    toe - face * 1.0 * b, fy + 6.6 * b, heel - face * 0.4 * b, fy + 5.2 * b],
                   col, "", smooth=True)
        # stiletto from the heel down to the ground
        self._poly([heel - face * 0.4 * b, fy + 4.6 * b, heel + face * 1.2 * b, fy + 4.8 * b,
                    heel + face * 0.9 * b, fy + 10.5 * b, heel + face * 0.3 * b, fy + 10.5 * b],
                   _shade(col, 0.7), "")
        if not low:
            self._line(heel, fy + 0.4 * b, fx + face * 2.8 * b, fy + 2.2 * b,
                       toe - face * 1.6 * b, fy + 5.0 * b,
                       fill=_mix_hex(col, "#ffffff", 0.4), width=1, smooth=True)
    else:
        self._poly([fx - 3.8 * b, fy - 9.0 * b, fx + 3.8 * b, fy - 9.0 * b,
                    fx + face * 4.6 * b, fy + 1.0 * b, toe, fy + 3.6 * b,
                    toe + face * 0.6 * b, fy + 6.4 * b, heel - face * 0.6 * b, fy + 6.4 * b,
                    heel - face * 0.2 * b, fy - 1.0 * b], col, "", smooth=True)
        self._poly([heel - face * 0.6 * b, fy + 6.0 * b, heel + face * 2.6 * b, fy + 6.0 * b,
                    heel + face * 2.4 * b, fy + 8.6 * b, heel - face * 0.4 * b, fy + 8.6 * b],
                   _shade(col, 0.6), "")
        if not low:
            self._line(fx - 3.8 * b, fy - 7.6 * b, fx + 3.8 * b, fy - 7.6 * b,
                       fill=_shade(col, 0.7), width=1)


def _j_sleeve(self, side, shoulder, elbow, wrist, b, lod, low):
    o = _j_outfit(self)
    if o == "light":
        return                                                  # sleeveless
    col = {"normal": JANE_LOOK["normal"][0], "warm": "#8a6a52", "rain": JANE_LOOK["rain"][0]}[o]
    col = _shade(col, (0.92 if side == "L" else 1.0) - 0.25 * self._cloth_body()["wet"] *
                 (0.2 if o == "rain" else 1.0))
    if o == "normal":                                           # fitted three-quarter
        end = (elbow[0] + (wrist[0] - elbow[0]) * 0.55, elbow[1] + (wrist[1] - elbow[1]) * 0.55)
        nodes = [shoulder, ((shoulder[0] + elbow[0]) * 0.5, (shoulder[1] + elbow[1]) * 0.5),
                 elbow, end]
        wid = [w * 1.12 for w in self._arm_wid()[:4]]
    else:
        end = (wrist[0] + (elbow[0] - wrist[0]) * 0.08, wrist[1] + (elbow[1] - wrist[1]) * 0.08)
        nodes = [shoulder, ((shoulder[0] + elbow[0]) * 0.5, (shoulder[1] + elbow[1]) * 0.5),
                 elbow, ((elbow[0] + end[0]) * 0.5, (elbow[1] + end[1]) * 0.5), end]
        wid = [w * 1.2 for w in self._arm_wid()]
    self._poly(_chain_skin(nodes, wid, 1.06, 0.2), col, "", smooth=True)
    if not low:
        self._limb_light(nodes, wid, col, lod, ruddy=False)
        ex, ey = nodes[-1]
        self._line(ex - wid[-1] * 0.9, ey, ex + wid[-1] * 0.9, ey, fill=_shade(col, 0.66), width=2)


def _j_collar(self, chest, neck, arms, b, lod, low):
    """Neckline jewellery: a fine chain and a pendant resting in the scoop."""
    if low:
        return
    nx, ny = neck[0], neck[1] + 6.0 * b
    g = JANE_LOOK["gold"]
    self._line(nx - 6.4 * b, ny - 1.0 * b, nx - 3.0 * b, ny + 4.5 * b, nx, ny + 6.4 * b,
               nx + 3.0 * b, ny + 4.5 * b, nx + 6.4 * b, ny - 1.0 * b, fill=g, width=1, smooth=True)
    px, py = nx, ny + 7.6 * b
    self._oval(px - 1.1 * b, py - 1.3 * b, px + 1.1 * b, py + 1.3 * b, g, "")
    self._oval(px - 0.4 * b, py - 0.8 * b, px + 0.2 * b, py - 0.2 * b, "#fff6d6", "")


# ---------------------------------------------------------------- poise

_j_prev_affect_step = Creature._affect_step


def _j_affect_step(self, dt):
    """Her baseline presence: chin up, a composed half-smile, a little asymmetry
    (the INTJ 'knowing' look), steady gaze. Added to whatever she feels, so
    every emotion still shows - just carried with poise."""
    base = getattr(self, "_affect", None)
    if base is not None:
        poised = dict(base)
        for k, v in (("smile", 0.12), ("asym", 0.22), ("chest", 0.22), ("tilt", 0.12),
                     ("eye", -0.04), ("energy", 0.0)):
            poised[k] = poised.get(k, 0.0) + v
        self._affect = poised
        try:
            _j_prev_affect_step(self, dt)
        finally:
            self._affect = base
    else:
        _j_prev_affect_step(self, dt)


for _n, _f in (("_heel", _j_heel), ("_hair_col", _j_hair_col), ("_palette", _j_palette),
               ("_draw_hair_back", _j_hair_back), ("_draw_hair_volume", _j_hair_volume),
               ("_draw_makeup", _j_makeup), ("_draw_shirt", _j_shirt),
               ("_draw_pants", _j_pants), ("_draw_shoe", _j_shoe),
               ("_draw_sleeve", _j_sleeve), ("_draw_collar", _j_collar),
               ("_affect_step", _j_affect_step)):
    setattr(Creature, _n, _f)


# ---------------------------------------------------------------- INTJ mind

JANE_PROFILE = {
    "schema": PROFILE_SCHEMA,
    "identity": {"name": "Jane", "pronouns": "she/her", "age": 28, "type": "INTJ",
                 "self_description": "a composed, observant woman who plans three moves "
                                     "ahead and enjoys being underestimated"},
    "background": "Grew up reading systems manuals for fun; learned early that people "
                  "judge the glamour and miss the strategy. She likes it that way.",
    "values": ["competence", "independence", "honesty", "doing things properly"],
    "temperament": {"baseline_mood": 0.15, "anxiety": 0.22, "energy_level": 0.55,
                    "stability": 0.78, "reactivity": 0.38, "recovery": 0.68,
                    "risk_tolerance": 0.62, "inertia": 0.72},
    "traits": {"curiosity": 0.86, "confidence": 0.82, "assertiveness": 0.74,
               "friendliness": 0.46, "openness": 0.8, "humour": 0.55, "energy": 0.55},
    "humour": {"level": 0.55, "style": "dry, understated, occasionally wicked"},
    "communication": {"verbosity": 0.35, "formality": 0.45, "directness": 0.85,
                      "warmth": 0.55, "notes": "precise, economical sentences; warm but "
                      "never gushing; asks sharp questions; comfortable with silence"},
    "preferences": {"likes": ["well-made plans", "quiet mornings", "good tailoring",
                              "strong coffee", "long walks"],
                    "dislikes": ["small talk", "sloppiness", "being rushed"],
                    "weather": {"rain": 0.35, "storm": -0.2, "fog": 0.45, "clear": 0.3},
                    "temperature_c": 21},
    "habits": ["explores in the morning", "rests in the evening",
               "watches before she approaches"],
    "interests": ["strategy", "architecture", "psychology", "fashion as armour",
                  "how things work"],
    "fears": ["losing control", "being dependent on anyone"],
    "goals": [{"name": "map the whole valley", "why": "information is leverage"},
              {"name": "understand the other creatures", "why": "patterns first, trust later"}],
    "relationships": [{"name": "user", "role": "user", "trust": 0.55, "affection": 0.5}],
    "memories": [{"text": "I decided a long time ago that I'd rather be understood by a few "
                          "than liked by everyone", "importance": 0.7, "valence": 0.2}],
    "quirks": ["notices exits and sightlines before anything else",
               "rehearses conversations she'll probably never have",
               "tucks her hair back when she's thinking hard"],
    "speech_patterns": {"fillers": ["mm.", "right -"], "catchphrases": ["noted."],
                        "avoid": ["as an AI", "OMG"]},
    "emotional_tendencies": {"triggers": {"praise": 0.35, "thunder": -0.3, "insult": -0.5}},
}

_j_prev_app_init = App.__init__


def _j_app_init(self, *a, **kw):
    _j_prev_app_init(self, *a, **kw)
    try:
        if not self.settings.get("jane_identity_v1"):
            apply_profile(self.brain, self.brain.mind, JANE_PROFILE)
            self.settings.set("jane_identity_v1", True)
            self.brain.save_state()
        self.brain.name = "Jane"
    except Exception:
        traceback.print_exc()


App.__init__ = _j_app_init


# ============================================================================
# Reference aesthetic (procedural reconstruction - an original character)
# ============================================================================
#
# Style cues taken from the supplied reference, rebuilt as geometry: high twin
# pigtails with ties + heart clips, centre part and face-framing wisps; big
# doe eyes with a large iris and double catch-light; pink eyeshadow, black
# wing, white inner-corner / lower-lid liner; strong rosy blush across the
# cheeks and nose; glossy red pout; pastel-pink strappy cami with scalloped
# white lace, a little bow and a strawberry print; layered necklaces.

JANE_SHAPE.update({"brow_col": "#8a6644", "eye_scale": 1.08, "iris": 1.0, "skin": "#f4d3c1", "iris_col": "#6b7f94",
                   "lip_col": "#c8102e", "lip_amt": 0.82, "lips": 1.45, "brow_w": 2,
                   "brow_arch": 1.3})
JANE_LOOK.update({
    "hair": "#f3e2bd", "hair_dark": "#cdb07e", "hair_hi": "#fffaf0",
    "shadow": "#ec7fa2", "blush": "#f27892", "tie": "#1d1a1c", "clip": "#ff8fbf",
    "light": ("#f7b8cb", "#f7f2ec", "#f4c2d0"),
    "normal": ("#f7b8cb", "#f2a9c2", "#f7f2ec"),
})
_J_BERRIES = ((-0.55, 0.35), (-0.15, 0.55), (0.3, 0.3), (0.62, 0.62), (-0.42, 0.85),
              (0.1, 0.95), (0.5, 1.05), (-0.7, 1.12))


def _j_hair_back2(self, neck, tilt, A, lod, low):
    """Behind the body: the nape and the backs of the pigtails. Shoulder
    length - the length lives in the pigtails now."""
    hx, hy = _j_head_pos(self, neck, tilt, A)
    wet = self._cloth_body()["wet"]
    self._head_scale_begin(hx, hy + 17.0, self._H() / 55.5)
    try:
        col = _shade(JANE_LOOK["hair_dark"], 1.0 - 0.3 * wet)
        pts = []
        for i in range(13):
            a = _cw_math.pi * (1.0 + i / 12.0)
            pts += [hx + _cw_math.cos(a) * 38.0, hy - 17.0 + _cw_math.sin(a) * 23.0]
        pts += [hx + 36, hy + 8, hx + 26, hy + 34, hx, hy + 40, hx - 26, hy + 34, hx - 36, hy + 8]
        self._poly(pts, col, "", smooth=True)
    finally:
        self._head_scale_end()


def _j_hair_volume2(self, hx, hy, lod, low):
    """Smooth crown, centre part, hair swept up toward the pigtail ties."""
    wet = self._cloth_body()["wet"]
    main = _shade(JANE_LOOK["hair"], 1.0 - 0.3 * wet)
    crown = []
    for i in range(15):
        a = _cw_math.pi * (1.0 + i / 14.0)
        crown += [hx + _cw_math.cos(a) * 36.5, hy - 18.0 + _cw_math.sin(a) * 23.5]
    crown += [hx + 31, hy - 12, hx + 20, hy - 25, hx + 5, hy - 31, hx, hy - 30,
              hx - 5, hy - 31, hx - 20, hy - 25, hx - 31, hy - 12]
    self._poly(crown, main, "", smooth=True)
    if not low:
        self._line(hx, hy - 30.5, hx, hy - 41.0, fill=_shade(main, 0.72), width=1)  # part
        hi = _mix_hex(main, JANE_LOOK["hair_hi"], 0.55 - 0.3 * wet)
        for side in (-1, 1):                    # combed-up sheen toward each tie
            self._line(hx + side * 4, hy - 34, hx + side * 14, hy - 38, hx + side * 24, hy - 36,
                       fill=hi, width=2, smooth=True)


def _j_pigtail(self, hx, hy, side, lod, low):
    """A high ponytail as one tapered, wavy mass hanging from its tie; the
    free end trails the cloth spring (pendulum) and lies flatter when wet."""
    wet = self._cloth_body()["wet"]
    swing = self.__dict__.get("_cloth_x", 0.0)
    main = _shade(JANE_LOOK["hair"], 1.0 - 0.3 * wet)
    tx, ty = hx + side * 27.0, hy - 32.0
    spread = 1.0 - 0.35 * wet
    nodes, wid = [], []
    for k, t in enumerate((0.0, 0.18, 0.4, 0.62, 0.82, 1.0)):
        out = side * (9.0 + 13.0 * _cw_math.sin(min(1.0, t * 1.6) * _cw_math.pi * 0.5)) * spread
        x = tx + out - swing * 1.4 * t * t + _cw_math.sin(t * 6.0 + self.t * 1.6 + side) * 1.2 * t
        y = ty + t * 104.0
        nodes.append((x, y))
        wid.append((7.5 + 6.0 * _cw_math.sin(t * _cw_math.pi) * spread) * (1.0 - 0.55 * t) + 1.2)
    self._poly(_chain_skin(nodes, [w * 1.12 for w in wid], 1.0, 0.0),
               _shade(JANE_LOOK["hair_dark"], 1.0 - 0.3 * wet), "", smooth=True)
    self._poly(_chain_skin(nodes, wid, 1.0, 0.0), main, "", smooth=True)
    if not low:
        hi = _mix_hex(main, JANE_LOOK["hair_hi"], 0.55 - 0.3 * wet)
        for off in (-0.35, 0.3):
            pts = []
            for (x, y), w in zip(nodes, wid):
                pts += [x + w * off, y]
            self._line(*pts, fill=hi if off > 0 else _shade(main, 0.84), width=1, smooth=True)
    # tie + heart clip
    self._oval(tx - 3.2, ty - 2.6, tx + 3.2, ty + 2.6, JANE_LOOK["tie"], "")
    if not low:
        cx, cy = tx + side * 2.0, ty - 4.5
        self._poly([cx, cy + 3.6, cx - 3.8, cy - 0.2, cx - 2.6, cy - 3.0, cx, cy - 1.6,
                    cx + 2.6, cy - 3.0, cx + 3.8, cy - 0.2], JANE_LOOK["clip"], "", smooth=True)


def _j_makeup2(self, hx, hy, head_color, lod, low):
    o = self.__dict__.get("_eye_o", 1.0)
    es = JANE_SHAPE["eye_scale"]
    ry = max(0.3, 5.4 * o * es)
    rx = 7.0 * es
    for side in (-1, 1):
        ex, ey = hx + side * 14, hy - 14
        lid = ey - ry
        # pink eyeshadow up to the crease, deepest at the outer corner
        self._poly([ex - side * rx, lid + 0.8, ex, lid - 4.4, ex + side * rx, lid + 0.8,
                    ex + side * (rx + 1.8), lid - 1.8, ex + side * 2, lid - 6.4,
                    ex - side * (rx - 1), lid - 2.2],
                   _mix_hex(head_color, JANE_LOOK["shadow"], 0.62), "", smooth=True)
        # black wing along the lid, flicked up past the outer corner
        self._line(ex - side * rx * 0.95, lid + 1.4 + ry * 0.3, ex - side * 2.5, lid - 0.3,
                   ex + side * 3.5, lid - 0.1, ex + side * rx, lid + 1.2,
                   ex + side * (rx + 4.6), lid - 3.2,
                   fill=JANE_LOOK["liner"], width=2, smooth=True)
        # white liner: inner-corner flick + lower lid (the reference's bright eye)
        self._line(ex - side * rx * 0.9, ey + 0.4, ex - side * (rx + 1.6), ey - 0.8,
                   fill="#fbf7f4", width=2)
        self._line(ex - side * rx * 0.7, ey + ry * 0.62, ex, ey + ry + 0.6,
                   ex + side * rx * 0.8, ey + ry * 0.5, fill="#fbf7f4", width=1, smooth=True)
        if not low:
            for k in range(6):                  # long, curled, fanned lashes
                u = k / 5.0
                bx = ex - side * rx * 0.7 + side * u * rx * 1.7
                by = lid + 0.2 + 0.7 * abs(u - 0.5)
                lx = side * (0.9 + 2.8 * u)
                self._line(bx, by, bx + lx * 0.6, by - 3.0, bx + lx, by - 4.6,
                           fill=JANE_LOOK["lash"], width=1, smooth=True)
        # blush: high and wide, sweeping toward the nose
        self._oval(hx + side * 18 - 8.0, hy - 5.0, hx + side * 18 + 8.0, hy + 3.0,
                   _mix_hex(head_color, JANE_LOOK["blush"], 0.36), "")
        sw = self.__dict__.get("_cloth_x", 0.0) * 0.25
        ex2, ey2 = hx + side * 33.5 + sw, hy + 4.0
        self._oval(ex2 - 3.4, ey2 - 0.5, ex2 + 3.4, ey2 + 7.4, "", JANE_LOOK["gold"])
    # flush across the bridge of the nose
    self._oval(hx - 6.0, hy - 5.5, hx + 6.0, hy - 1.5, _mix_hex(head_color, JANE_LOOK["blush"], 0.22), "")
    if not low:
        for side in (-1, 1):                    # face-framing wisps
            self._line(hx + side * 22, hy - 27, hx + side * 30, hy - 14, hx + side * 28, hy + 2,
                       fill=_shade(JANE_LOOK["hair"], 0.95), width=2, smooth=True)
    for side in (-1, 1):
        _j_pigtail(self, hx, hy, side, lod, low)


def _j_cami(self, pelvis, pelvis_top, spine1, chest, arms, pw, b, lod, low):
    """Strappy pastel cami: sweetheart neckline with scalloped lace, thin
    straps, a bow, and a strawberry print that follows the body."""
    S, bd = JANE_SHAPE, self._cloth_body()
    o = bd["outfit"]
    top, bottom, _sh = JANE_LOOK[o]
    wet = bd["wet"]
    top = _shade(top, 1.0 - 0.25 * wet)
    H = pw
    lsh, rsh = arms["L"][0], arms["R"][0]
    hipw, waist, rib = pw * S["hip"], pw * S["waist"], pw * S["rib"]
    crop = o == "light"
    hem_top = (spine1[1] + pelvis_top[1]) * 0.5 if crop else pelvis_top[1] + 0.05 * H
    nl = chest[1] + 0.08 * H                                     # neckline height
    body = [lsh[0] + 0.14 * H, lsh[1] + 0.36 * H,
            chest[0] - 0.52 * H, nl, chest[0] - 0.12 * H, nl - 0.1 * H,
            chest[0], nl + 0.16 * H,
            chest[0] + 0.12 * H, nl - 0.1 * H, chest[0] + 0.52 * H, nl,
            rsh[0] - 0.14 * H, rsh[1] + 0.36 * H,
            spine1[0] + rib, spine1[1], spine1[0] + waist * 1.03, hem_top,
            spine1[0] - waist * 1.03, hem_top, spine1[0] - rib, spine1[1]]
    self._poly(body, top, "", smooth=True)
    _j_bust(self, chest, pw, b, top, lod, low)
    for side, sh in ((-1, lsh), (1, rsh)):                         # straps
        self._line(chest[0] + side * 0.44 * H, nl + 0.02 * H, sh[0] - side * 0.2 * H, sh[1] - 0.02 * H,
                   fill=_shade(top, 0.95), width=2)
    if not low:
        lace = "#fdfbf8"
        pts = []
        for i in range(13):                                         # scalloped lace
            u = i / 12.0
            x = chest[0] - 0.52 * H + u * 1.04 * H
            dip = 0.16 * H * (1.0 - abs(u - 0.5) * 2) ** 2 - 0.1 * H * _cw_math.sin(u * _cw_math.pi) * 0.3
            pts += [x, nl + dip + (0.03 * H if i % 2 else -0.01 * H)]
        self._line(*pts, fill=lace, width=2, smooth=True)
        bx, by = chest[0], nl + 0.18 * H                            # bow
        self._poly([bx, by, bx - 0.14 * H, by - 0.07 * H, bx - 0.14 * H, by + 0.07 * H], lace, "")
        self._poly([bx, by, bx + 0.14 * H, by - 0.07 * H, bx + 0.14 * H, by + 0.07 * H], lace, "")
        if lod >= 1:                                                # strawberry print
            span = max(1.0, hem_top - nl)
            for (u, v) in _J_BERRIES:
                y = nl + 0.2 * H + v / 1.15 * (span - 0.25 * H)
                if y > hem_top - 0.05 * H:
                    continue
                w_here = rib if y < spine1[1] else waist
                x = chest[0] + u * w_here * 0.85
                r = 0.055 * H
                self._oval(x - r, y - r * 0.9, x + r, y + r * 1.1, "#e0334f", "")
                self._oval(x - r * 0.6, y - r * 1.4, x + r * 0.6, y - r * 0.6, "#4f9a4a", "")
        self._line(spine1[0] - waist * 1.03, hem_top - 0.02 * H, spine1[0] + waist * 1.03,
                   hem_top - 0.02 * H, fill="#fdfbf8", width=2)
    if crop and not low:
        nav = (pelvis_top[0], (hem_top + pelvis_top[1]) * 0.5 + 0.05 * H)
        self._oval(nav[0] - 0.03 * H, nav[1] - 0.04 * H, nav[0] + 0.03 * H, nav[1] + 0.04 * H,
                   _shade(self._skin_tone(), 0.62), "")
    # skirt
    mini = o == "light"
    hem = pelvis[1] + (0.9 if mini else 1.2) * H
    cx = self.__dict__.get("_cloth_x", 0.0)
    walk = _cw_math.sin(self._loco.phase * _cw_math.tau) * min(1.0, self._loco.speed / 40.0)
    flare = 1.16
    bottom = _shade(bottom, 1.0 - 0.25 * wet)
    wave = _cw_math.sin(self.t * 5.0) * 0.03 * H * min(1.0, abs(cx) / 4.0 + abs(walk))
    skirt = [pelvis_top[0] - waist * 1.06, pelvis_top[1], pelvis_top[0] + waist * 1.06, pelvis_top[1],
             pelvis[0] + hipw * 1.04, pelvis[1],
             pelvis[0] + hipw * flare + cx * 0.6 + walk * 0.08 * H, hem + wave,
             pelvis[0] + cx * 0.8, hem + 0.04 * H - wave,
             pelvis[0] - hipw * flare + cx * 0.6 + walk * 0.08 * H, hem + wave,
             pelvis[0] - hipw * 1.04, pelvis[1]]
    self._poly(skirt, bottom, "", smooth=True)
    if not low:
        self._limb_light([pelvis_top, pelvis, (pelvis[0], hem)],
                         [waist * 1.04, hipw, hipw * flare * 0.95], bottom, lod, ruddy=False)
        if o == "normal":                                           # pleats
            for k in range(-3, 4):
                self._line(pelvis[0] + k * hipw * 0.24, pelvis[1] + 0.05 * H,
                           pelvis[0] + k * hipw * 0.3 + cx * 0.4, hem - 0.03 * H,
                           fill=_shade(bottom, 0.84), width=1)


_j_prev_shirt = _j_shirt


def _j_shirt2(self, pelvis, pelvis_top, spine1, chest, arms, pw, b, lod, low):
    if self._cloth_body()["outfit"] in ("light", "normal"):
        return _j_cami(self, pelvis, pelvis_top, spine1, chest, arms, pw, b, lod, low)
    return _j_prev_shirt(self, pelvis, pelvis_top, spine1, chest, arms, pw, b, lod, low)


_j_prev_sleeve = _j_sleeve


def _j_sleeve2(self, side, shoulder, elbow, wrist, b, lod, low):
    if _j_outfit(self) in ("light", "normal"):
        return                                                      # strappy cami
    return _j_prev_sleeve(self, side, shoulder, elbow, wrist, b, lod, low)


def _j_collar2(self, chest, neck, arms, b, lod, low):
    """Layered necklaces: a choker, a fine chain and a longer pendant chain."""
    if low:
        return
    H = self._H()
    g = JANE_LOOK["gold"]
    nx, ny = neck[0], neck[1]
    self._line(nx - 0.2 * H, ny + 0.22 * H, nx, ny + 0.3 * H, nx + 0.2 * H, ny + 0.22 * H,
               fill="#2a2426", width=2, smooth=True)                                   # choker
    for depth, w in ((0.55, 0.3), (0.9, 0.36)):
        self._line(nx - w * H, ny + 0.3 * H, nx - w * 0.5 * H, ny + depth * H, nx, ny + (depth + 0.06) * H,
                   nx + w * 0.5 * H, ny + depth * H, nx + w * H, ny + 0.3 * H, fill=g, width=1, smooth=True)
    px, py = nx, ny + 0.99 * H
    self._oval(px - 0.05 * H, py - 0.06 * H, px + 0.05 * H, py + 0.06 * H, g, "")


for _n, _f in (("_draw_hair_back", _j_hair_back2), ("_draw_hair_volume", _j_hair_volume2),
               ("_draw_makeup", _j_makeup2), ("_draw_shirt", _j_shirt2),
               ("_draw_sleeve", _j_sleeve2), ("_draw_collar", _j_collar2)):
    setattr(Creature, _n, _f)


# ============================================================================
# Jane's face: layered 3D construction (replaces the symbol face for Jane)
# ============================================================================
#
# Head-local units: chin at +17, crown at -38.5 (H = 55.5 units). Adult female
# proportions: hairline -28, brows ~-15.5, eye line -9 (head midpoint),
# nose base +3.5, lip line +8.5, chin +17. Lighting from the stage key light
# (upper-left): every plane is shaded by which way it faces, so the face
# reads as a volume - forehead and left cheekbone catch the light, the far
# cheek, temple, jaw underside, eye sockets and the underside of the nose
# fall into shadow. The eyes sit IN sockets: the sclera is drawn first, then
# real upper/lower lid shapes occlude it, so blinking is the lid descending.

JANE_SHAPE["face_hd"] = True


def _fh_face_outline(hx, hy, asym):
    a = asym * 0.25
    # cheekbones widest at eye level, then a soft taper into a narrow chin
    pts = [(0, -38.5), (-17, -36.5), (-27.5, -30), (-31.0, -20), (-31.2, -10.5),
           (-29.6 - a, -3.5), (-26.2 - a, 3.5), (-21.0 - a, 9.5), (-14.5, 14.0),
           (-8.5, 16.9), (-3.8, 18.2), (0, 18.4), (3.8, 18.2), (8.5, 16.9),
           (14.5, 14.0), (21.0 + a, 9.5), (26.2 + a, 3.5), (29.6 + a, -3.5),
           (31.2, -10.5), (31.0, -20), (27.5, -30), (17, -36.5)]
    out = []
    for (u, v) in pts:
        out += [hx + u, hy + v]
    return out


def _fh_P(hx, hy, pts):
    out = []
    for (u, v) in pts:
        out += [hx + u, hy + v]
    return out


def _fh_eye(self, hx, hy, side, skin, lod, low, A, o):
    """Socket -> sclera almond -> iris -> pupil -> catch-lights -> upper lid
    (occluder, carries the eyeshadow) -> crease -> lower lid -> liner/lashes."""
    L = JANE_LOOK
    es = JANE_SHAPE["eye_scale"]
    ex, ey = hx + side * 12.8, hy - 9.0
    rx = 5.9 * es
    ry = 3.5 * es                                   # fully open half-height
    inner, outer = ex - side * rx, ex + side * rx
    tilt = -0.6                                     # slight lift at the outer corner
    # socket: recessed, a touch darker, deepest under the brow
    # socket: recessed; the far eye's socket and the under-brow fall deeper
    deep = 0.85 if side > 0 else 0.89
    self._oval(ex - rx * 1.4, ey - ry * 1.9, ex + rx * 1.4, ey + ry * 1.5, _shade(skin, deep + 0.03), "")
    self._oval(ex - rx * 1.15, ey - ry * 1.85, ex + rx * 1.1, ey - ry * 0.5, _shade(skin, deep), "")
    # sclera: almond, with the upper curve peaking toward the inner third
    up = [(inner, ey), (ex - side * rx * 0.55, ey - ry * 1.05),
          (ex + side * rx * 0.1, ey - ry * 1.12), (ex + side * rx * 0.62, ey - ry * 0.8 + tilt),
          (outer, ey + tilt)]
    lo = [(ex + side * rx * 0.62, ey + ry * 0.72), (ex, ey + ry * 0.86),
          (ex - side * rx * 0.6, ey + ry * 0.64)]
    sclera = []
    for (x, y) in up + lo:
        sclera += [x, y]
    self._poly(sclera, "#f1ece6", "", smooth=True)
    for sx0 in ((inner, outer) if lod >= 1 else ()):  # corner shading: the eyeball is round
        self._oval(sx0 - rx * 0.32, ey - ry * 0.55, sx0 + rx * 0.32, ey + ry * 0.55,
                   "#d9cfc8", "")
    # iris: large, gaze-driven but kept inside the opening
    ir = 3.0 * es * JANE_SHAPE["iris"]
    gx = clamp(self.look_x * 0.55, -rx * 0.35, rx * 0.35)
    gy = clamp(self.look_y * 0.4 + 1.0 * A["gaze"], -ry * 0.25, ry * 0.35)
    cx, cy = ex + gx, ey + gy + 0.2
    iris = JANE_SHAPE["iris_col"]
    self._oval(cx - ir, cy - ir, cx + ir, cy + ir, _shade(iris, 0.62), "")        # limbal ring
    self._oval(cx - ir * 0.84, cy - ir * 0.84, cx + ir * 0.84, cy + ir * 0.84, iris, "")
    if lod >= 1:
        self._oval(cx - ir * 0.52, cy - ir * 0.52, cx + ir * 0.52, cy + ir * 0.52,
                   _mix_hex(iris, "#e8f0f4", 0.28), "")                         # lighter collarette
    pr = ir * 0.4 * (1.0 + 0.2 * clamp01(A["eye"] - 1.0) + 0.12 * A["tension"])
    self._oval(cx - pr, cy - pr, cx + pr, cy + pr, "#0b0808", "")
    if lod >= 2:
        for i in range(10):                                                     # iris fibres
            a_ = i * (_cw_math.tau / 10.0)
            self._line(cx + _cw_math.cos(a_) * pr * 1.1, cy + _cw_math.sin(a_) * pr * 1.1,
                       cx + _cw_math.cos(a_) * ir * 0.8, cy + _cw_math.sin(a_) * ir * 0.8,
                       fill=_shade(iris, 0.8), width=1)
    klx, kly = _KEY_LIGHT
    self._oval(cx + klx * ir * 0.45 - 0.75, cy + kly * ir * 0.45 - 0.75,
               cx + klx * ir * 0.45 + 0.75, cy + kly * ir * 0.45 + 0.75, "#ffffff", "")
    if lod >= 1:
        self._oval(cx - klx * ir * 0.35 - 0.35, cy - kly * ir * 0.3 - 0.35,
                   cx - klx * ir * 0.35 + 0.35, cy - kly * ir * 0.3 + 0.35, "#e8eef5", "")
    # upper lid: an occluder whose lower edge IS the lid line. o=1 open, 0 shut.
    lidf = 1.0 - clamp01(o)                          # 0 open .. 1 closed
    lid_line = []
    for (x, y) in up:
        yy = y + (ey + ry * 0.7 - y) * lidf          # descends onto the lower lid
        lid_line.append((x, yy))
    lid_col = _mix_hex(_shade(skin, 0.9), L["shadow"], 0.42)
    top = [(outer + side * 1.2, ey - ry * 1.55), (ex, ey - ry * 1.75), (inner - side * 1.0, ey - ry * 1.45)]
    self._poly(_fh_flat(lid_line + top), lid_col, "", smooth=True)
    # lid thickness / crease following the lid, deeper when open
    if lod >= 1:
        crease = [(x, y - ry * (0.62 + 0.25 * (1 - lidf))) for (x, y) in lid_line]
        self._line(*_fh_flat(crease), fill=_shade(lid_col, 0.8), width=1, smooth=True)
    # lower lid: occludes from below, with the soft under-eye plane
    low_line = [(inner, ey)] + lo[::-1] + [(outer, ey + tilt)]
    low_line = [(inner, ey), (ex - side * rx * 0.6, ey + ry * 0.64), (ex, ey + ry * 0.86),
                (ex + side * rx * 0.62, ey + ry * 0.72), (outer, ey + tilt)]
    under = [(outer + side * 1.2, ey + ry * 1.6), (ex, ey + ry * 2.0), (inner - side * 1.0, ey + ry * 1.3)]
    self._poly(_fh_flat(low_line + under), _shade(skin, 0.95), "", smooth=True)
    # white waterline + lash line / liner with the wing
    self._line(*_fh_flat(low_line[1:4]), fill="#fbf8f5", width=1, smooth=True)
    self._line(*_fh_flat(lid_line + [(outer + side * 4.4, ey - ry * 1.15 + tilt)]),
               fill=L["liner"], width=2, smooth=True)
    self._line(inner, ey, inner - side * 1.8, ey - 0.6, fill="#fbf8f5", width=1)   # inner-corner accent
    if not low and lod >= 1:
        for k in range(7):                                                      # lashes off the lid edge
            u = k / 6.0
            i0 = min(len(lid_line) - 2, int(u * (len(lid_line) - 1)))
            f = u * (len(lid_line) - 1) - i0
            (x0, y0), (x1, y1) = lid_line[i0], lid_line[i0 + 1]
            bx, by = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            ln = (2.2 + 2.4 * u) * (1.0 - 0.4 * lidf)
            self._line(bx, by, bx + side * ln * 0.35, by - ln * 0.75, bx + side * ln * 0.8, by - ln * 0.95,
                       fill=L["lash"], width=1, smooth=True)
    return ex, ey, rx, ry


def _fh_flat(pts):
    out = []
    for (x, y) in pts:
        out += [x, y]
    return out


def _fh_brow(self, hx, hy, side, A):
    """On the brow ridge, tapering from a soft head to a fine tail; worry
    lifts the inner end, anger pulls it down and in, surprise lifts it all."""
    din = -5.0 * A["brow_in"] + 4.0 * A["knit"]
    dout = -3.8 * A["brow_out"] + 1.0 * A["knit"]
    if side > 0:
        din -= 1.4 * A["asym"]
        dout -= 1.1 * A["asym"]
    ih = hx + side * (5.0 - 1.6 * A["knit"])
    pts = [(ih, hy - 14.6 + din), (hx + side * 10.5, hy - 16.9 + (din + dout) * 0.55),
           (hx + side * 15.5, hy - 17.8 + dout * 0.8), (hx + side * 20.8, hy - 15.4 + dout),
           (hx + side * 15.0, hy - 16.4 + dout * 0.8), (hx + side * 10.0, hy - 15.4 + (din + dout) * 0.5),
           (ih + side * 0.3, hy - 13.2 + din)]
    self._poly(_fh_flat(pts), JANE_SHAPE["brow_col"], "", smooth=True)
    self._line(ih + side * 1.0, hy - 14.0 + din, hx + side * 10.5, hy - 16.3 + (din + dout) * 0.55,
               hx + side * 16.0, hy - 17.0 + dout * 0.8, fill=_shade(JANE_SHAPE["brow_col"], 0.8),
               width=1, smooth=True)


def _fh_nose(self, hx, hy, skin, lod):
    klx = _KEY_LIGHT[0]
    self._poly(_fh_P(hx, hy, [(1.2, -11.0), (3.8, -3.0), (5.0, 1.5), (2.4, 1.8), (1.0, -4.0)]),
               _shade(skin, 0.8), "", smooth=True)                                 # shaded side of the bridge
    self._line(hx - 1.0, hy - 10.5, hx - 1.1, hy - 3.0, hx - 0.6, hy + 0.2,
               fill=_shade(skin, 1.07), width=2, smooth=True)                      # bridge highlight
    for sd in (-1, 1):                                                              # alar wings
        self._oval(hx + sd * 3.7 - 2.1, hy + 1.6, hx + sd * 3.7 + 2.1, hy + 4.6,
                   _shade(skin, 0.9 if sd > 0 else 0.96), "")
    self._oval(hx - 3.1, hy - 0.4, hx + 3.1, hy + 4.2, _shade(skin, 1.0), "")      # tip
    self._oval(hx + klx * 1.1 - 1.0, hy + 0.3, hx + klx * 1.1 + 1.0, hy + 1.8,
               _shade(skin, 1.09), "")                                             # tip highlight
    self._poly(_fh_P(hx, hy, [(-3.3, 3.6), (0, 4.9), (3.3, 3.6), (2.2, 4.8), (0, 5.4), (-2.2, 4.8)]),
               _shade(skin, 0.8), "", smooth=True)                                  # underside of the nose
    for sd in (-1, 1):
        self._oval(hx + sd * 1.9 - 1.0, hy + 3.7, hx + sd * 1.9 + 1.0, hy + 4.7, "#6e3b35", "")
    self._oval(hx - 2.8, hy + 5.4, hx + 2.8, hy + 6.8, _shade(skin, 0.9), "")      # cast shadow on the lip


def _fh_mouth(self, hx, hy, skin, lod, low, jaw_open):
    A = self._aff()
    sm, asym = A["smile"], A["asym"]
    talk = self.speaking > 0 and _cw_math.sin(self.t * 16) > 0
    opn = 3.4 * A["open"] + (1.8 if talk else 0.0) + jaw_open * 0.08
    mw = 7.4 * (0.95 + 0.08 * max(0.0, sm) - 0.35 * A["round"])
    ml = hy + 8.8
    cl = 2.0 * sm - 0.3 * asym
    cr = 2.0 * sm + 0.9 * asym * max(0.2, sm + 0.3)
    full = JANE_SHAPE["lips"]
    lip = _mix_hex(skin, JANE_SHAPE["lip_col"], JANE_SHAPE["lip_amt"])
    line = [(hx - mw, ml - cl), (hx - mw * 0.5, ml - cl * 0.3), (hx, ml), (hx + mw * 0.5, ml - cr * 0.3),
            (hx + mw, ml - cr)]
    f = (0.0, 0.8, 1.0, 0.8, 0.0)
    upper = [(x, y - opn * 0.5 * k) for (x, y), k in zip(line, f)]
    lower = [(x, y + opn * 0.5 * k) for (x, y), k in zip(line, f)]
    # philtrum + shadow above the lip
    for sd in ((-1, 1) if lod >= 1 else ()):
        self._line(hx + sd * 1.0, hy + 5.6, hx + sd * 1.5, ml - 2.6 * full,
                   fill=_shade(skin, 0.9), width=1)
    # cavity / teeth (always emitted, zero-size when shut - stable draw order)
    cav = opn > 0.6
    self._poly(_fh_flat(upper + list(reversed(lower))) if cav else _fh_flat(line + list(reversed(line))),
               "#3a1216", "")
    drop = min(1.4, opn * 0.4) if opn > 1.4 else 0.0
    self._poly(_fh_flat(upper + [(x, y + drop) for (x, y) in reversed(upper)]), "#efe6de", "")
    # upper lip: faces down -> darker; cupid's bow
    bow = [(hx - mw, ml - cl), (hx - mw * 0.55, ml - 2.2 * full - cl * 0.3), (hx - 1.5, ml - 2.9 * full),
           (hx, ml - 2.3 * full), (hx + 1.5, ml - 2.9 * full), (hx + mw * 0.55, ml - 2.2 * full - cr * 0.3),
           (hx + mw, ml - cr)]
    self._poly(_fh_flat(bow + list(reversed(upper))), _shade(lip, 0.82), "", smooth=True)
    # lower lip: fuller, faces up -> lighter, with a gloss highlight
    bot = [(hx + mw * 0.75, lower[3][1] + 1.9 * full), (hx, lower[2][1] + 3.3 * full),
           (hx - mw * 0.75, lower[1][1] + 1.9 * full)]
    self._poly(_fh_flat(lower + bot), lip, "", smooth=True)
    gy = lower[2][1] + 1.2 * full
    self._oval(hx - 3.2, gy - 0.3, hx + 1.8, gy + 1.3, _mix_hex(lip, "#ffffff", 0.42), "")
    self._line(*_fh_flat(line), fill=_shade(lip, 0.45), width=1, smooth=True)
    for sd, c_ in ((-1, cl), (1, cr)):                                               # corners
        self._oval(hx + sd * mw - 0.8, ml - c_ - 0.6, hx + sd * mw + 0.8, ml - c_ + 0.8,
                   _shade(skin, 0.78), "")
    self._oval(hx - 4.5, lower[2][1] + 3.6 * full, hx + 4.5, lower[2][1] + 5.2 * full,
               _shade(skin, 0.9), "")                                                  # under-lip shadow


def _fh_ears(self, hx, hy, skin, lod):
    for sd in (-1, 1):
        ox = hx + sd * 31.0
        self._poly(_fh_P(ox, hy, [(0, -11), (sd * 3.6, -10.5), (sd * 4.6, -6), (sd * 3.8, -1),
                                  (sd * 2.2, 2.8), (sd * 0.4, 2.2)]),
                   _shade(skin, 0.9 if sd > 0 else 0.95), "", smooth=True)
        ix0, ix1 = sorted((ox + sd * 1.0, ox + sd * 3.0))
        self._oval(ix0, hy - 7.5, ix1, hy - 2.0, _shade(skin, 0.74), "")


def _fh_hair_scalp(self, hx, hy, skin, lod, low):
    """Hair GROWS from a hairline: a soft root band blends skin into hair,
    then the swept-up mass (centre part) with shading and flow toward the
    pigtail ties."""
    L = JANE_LOOK
    wet = self._cloth_body()["wet"]
    main = _shade(L["hair"], 1.0 - 0.3 * wet)
    dark = _shade(L["hair_dark"], 1.0 - 0.3 * wet)
    hairline = [(-30.5, -14), (-26, -22), (-18, -27.2), (-8, -29.2), (0, -28.6),
                (8, -29.2), (18, -27.2), (26, -22), (30.5, -14)]
    # root band: sparse hair just below the line, halfway between skin and hair
    band = [(x, y + 1.6) for (x, y) in hairline]
    self._poly(_fh_P(hx, hy, band + [(33.5, -18), (0, -40), (-33.5, -18)]),
               _mix_hex(skin, dark, 0.45), "", smooth=True)
    mass = hairline + [(33.2, -18), (31, -29), (20, -38.5), (0, -41.5), (-20, -38.5), (-31, -29), (-33.2, -18)]
    self._poly(_fh_P(hx, hy, mass), main, "", smooth=True)
    self._poly(_fh_P(hx, hy, [(4, -29), (18, -27.5), (27, -22), (32.5, -15), (32.8, -24),
                              (26, -33), (14, -38)]), _shade(main, 0.93), "", smooth=True)  # far side in shade
    if low:
        return
    self._line(hx, hy - 28.8, hx + 0.4, hy - 41.0, fill=_shade(main, 0.7), width=1)          # centre part
    hi = _mix_hex(main, L["hair_hi"], 0.55 - 0.3 * wet)
    self._line(hx - 3, hy - 36, hx - 13, hy - 39.5, hx - 24, hy - 35, fill=hi, width=2, smooth=True)
    for sd in ((-1, 1) if lod >= 1 else ()):                  # flow lines toward each tie
        for k in range(4 if lod >= 1 else 2):
            x0 = sd * (4 + k * 6.5)
            self._line(hx + x0, hy - 28.8 + k * 0.8, hx + x0 + sd * 5, hy - 34.5 + k * 0.4,
                       hx + sd * 25, hy - 34.0, fill=_shade(main, 0.82 if k % 2 else 0.92),
                       width=1, smooth=True)


def _draw_face_hd(self, hx, hy, skin, lod, low, jaw_open):
    A = self._aff()
    L = JANE_LOOK
    klx, kly = _KEY_LIGHT
    asym = self.asym
    _fh_ears(self, hx, hy, skin, lod)
    self._poly(_fh_face_outline(hx, hy, asym), skin, "", smooth=True)
    # form shading: far-side plane, temple, cheek hollow, jaw underside
    self._poly(_fh_P(hx, hy, [(19, -25), (30.2, -18), (30.8, -8), (29, -1), (24.5, 6.5), (18.5, 12),
                              (11.5, 16.2), (17, 8), (21.5, 0), (23.5, -12)]),
               _shade(skin, 0.85), "", smooth=True)
    self._poly(_fh_P(hx, hy, [(24, -22), (31.5, -14), (31.8, -4), (27, -12)]),
               _shade(skin, 0.8), "", smooth=True)                              # far temple
    self._poly(_fh_P(hx, hy, [(-15, -27), (0, -28.5), (-2, -18), (-14, -18.5), (-22, -21)]),
               _shade(skin, 1.05), "", smooth=True)                            # lit forehead
    for sd in (-1, 1):
        self._poly(_fh_P(hx, hy, [(sd * 13, 3.8), (sd * 24, 1.0), (sd * 26.5, 5.5), (sd * 20, 10), (sd * 12, 8)]),
                   _shade(skin, 0.92 if sd > 0 else 0.95), "", smooth=True)    # under the cheekbone
        self._poly(_fh_P(hx, hy, [(sd * 15, -4.5), (sd * 25.5, -6), (sd * 28.5, -1.5), (sd * 24, 1.5), (sd * 15, 0.5)]),
                   _shade(skin, 1.06 if sd < 0 else 1.0), "", smooth=True)     # cheekbone plane
    self._poly(_fh_P(hx, hy, [(-14, 13.2), (-5, 16.9), (0, 17.3), (5, 16.9), (14, 13.2), (7, 17.9), (0, 18.3), (-7, 17.9)]),
               _shade(skin, 0.78), "", smooth=True)                            # jaw underside
    self._oval(hx - 3.6, hy + 13.2, hx + 3.2, hy + 16.0, _shade(skin, 1.05), "")  # chin
    # blush over the cheekbones and across the nose
    for sd in (-1, 1):
        self._oval(hx + sd * 18.5 - 7.5, hy - 5.0, hx + sd * 18.5 + 7.5, hy + 2.5,
                   _mix_hex(skin, L["blush"], 0.3), "")
    self._oval(hx - 6.5, hy - 5.2, hx + 6.5, hy - 1.8, _mix_hex(skin, L["blush"], 0.18), "")
    # pores (close range): sampled from the identity's pore map, faint
    if lod >= 2:
        for (px, py, r, depth, oil, tone) in self._skin["pores"][::6]:
            if abs(px) > 26 or py < -26 or py > 15 or (abs(px) > 6 and -13 < py < -5):
                continue                                  # not on the eyes
            x, y = hx + px, hy + py
            self._line(x, y, x + 0.5, y + 0.5, fill=_shade(skin, 0.94), width=1)
    o = clamp(A["eye"], 0.35, 1.3)
    now = _cw_time.time()
    if now < self.blink_until:
        ph = 1.0 - (self.blink_until - now) / 0.15
        o *= 1.0 - _cw_math.sin(_cw_math.pi * clamp01(ph))
    self.__dict__["_eye_o"] = o
    for sd in (-1, 1):
        _fh_eye(self, hx, hy, sd, skin, lod, low, A, o)
        _fh_brow(self, hx, hy, sd, A)
    _fh_nose(self, hx, hy, skin, lod)
    _fh_mouth(self, hx, hy, skin, lod, low, jaw_open)
    # specular: oily T-zone catches the key light
    if not low:
        self._oval(hx + klx * 4 - 5, hy - 25.5, hx + klx * 4 + 4, hy - 23.2,
                   _mix_hex(skin, "#ffffff", 0.18), "")
    _fh_hair_scalp(self, hx, hy, skin, lod, low)


def _j_makeup_hd(self, hx, hy, head_color, lod, low):
    """In face_hd mode the makeup is part of the face construction; this hook
    only adds what hangs off the head: hoops and pigtails."""
    sw = self.__dict__.get("_cloth_x", 0.0) * 0.25
    for side in (-1, 1):
        ex2, ey2 = hx + side * 33.2 + sw, hy + 2.4
        self._oval(ex2 - 3.2, ey2 - 0.4, ex2 + 3.2, ey2 + 7.0, "", JANE_LOOK["gold"])
    for side in (-1, 1):
        _j_pigtail(self, hx, hy, side, lod, low)


def _j_hair_back_hd(self, neck, tilt, A, lod, low):
    """Behind the head only: the nape, ending at chin level (hair is up)."""
    hx, hy = _j_head_pos(self, neck, tilt, A)
    wet = self._cloth_body()["wet"]
    self._head_scale_begin(hx, hy + 17.0, self._H() / 55.5)
    try:
        pts = []
        for i in range(13):
            a = _cw_math.pi * (1.0 + i / 12.0)
            pts += [hx + _cw_math.cos(a) * 36.0, hy - 17.0 + _cw_math.sin(a) * 25.0]
        pts += [hx + 33, hy + 2, hx + 22, hy + 13, hx, hy + 15, hx - 22, hy + 13, hx - 33, hy + 2]
        self._poly(pts, _shade(JANE_LOOK["hair_dark"], 1.0 - 0.3 * wet), "", smooth=True)
    finally:
        self._head_scale_end()


Creature._draw_face_hd = _draw_face_hd
Creature._draw_makeup = _j_makeup_hd
Creature._draw_hair_back = _j_hair_back_hd
