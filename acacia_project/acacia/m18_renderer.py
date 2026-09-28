

# ============================================================================
# [9] CREATURE RENDERER  (procedural segmented anatomy over a light 2D rig)
# ============================================================================
#
# The creature is a small skeleton - pelvis -> spine -> chest -> neck ->
# skull, plus two 2-joint arms and two 2-joint legs - rendered as tapered
# polygon segments instead of a couple of decorated blobs. Per-instance
# proportions/asymmetry are rolled ONCE in __init__ (a stable identity, not
# frame noise); every frame just re-poses that fixed rig from the current
# behaviour/emotion/talk state and redraws it, which is why the silhouette
# stays coherent instead of jittering. Detail (ears, joint dots, the extra
# pelvis plate) is skipped on `low` detail so weak machines still run at a
# reasonable frame rate instead of losing frames to canvas item count.

BOUNDS = (70, 300, 390, 330)     # creature roams within this box

# eyes/mouth per emotion so all 14 states read differently on the face
FACE = {
    "neutral":      ("open", "small_smile"),
    "happy":        ("open", "smile"),
    "excited":      ("wide", "big_smile"),
    "curious":      ("open", "small_o"),
    "calm":         ("soft", "small_smile"),
    "affectionate": ("soft", "smile"),
    "confident":    ("open", "smirk"),
    "surprised":    ("wide", "o"),
    "anxious":      ("wide", "wobble"),
    "scared":       ("wide", "o"),
    "angry":        ("angry", "frown"),
    "frustrated":   ("angry", "flat"),
    "sad":          ("sad", "frown"),
    "bored":        ("half", "flat"),
    "tired":        ("closed", "flat"),
}


def _shade(hexcolor, factor):
    """Lighten (factor>1) or darken (factor<1) a #rrggbb colour - the cheap
    stand-in for real lighting: every body part gets a slightly different
    factor so the creature reads as having material/surface variation
    instead of being flat-filled."""
    hexcolor = hexcolor.lstrip("#")
    try:
        r, g, b = int(hexcolor[0:2], 16), int(hexcolor[2:4], 16), int(hexcolor[4:6], 16)
    except Exception:
        return "#" + hexcolor if hexcolor else "#888888"
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _limb_quad(p0, p1, w0, w1):
    """A tapered quad (flat coord list, ready for create_polygon) running
    from p0 (half-width w0) to p1 (half-width w1) - one segment of a limb
    or torso plate. This is the whole trick behind the anatomy: every bone
    is just two joint points and two widths."""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / length, dx / length
    return [x0 + nx * w0, y0 + ny * w0, x1 + nx * w1, y1 + ny * w1,
            x1 - nx * w1, y1 - ny * w1, x0 - nx * w0, y0 - ny * w0]


class Creature:
    def __init__(self, canvas, x, y, bounds, identity=None):
        self.c = canvas
        self.x, self.y = x, y
        self.target = (x, y)
        self.bounds = bounds          # (xmin, ymin, xmax, ymax)
        self.behavior = "idle"
        self.emotion = "neutral"
        self.intensity = 0.3
        self.t = 0.0
        self.blink_until = 0
        self.next_blink = time.time() + random.uniform(2, 5)
        self.look_x, self.look_y = 0.0, 0.0        # final pupil offset (px)
        self.look_target = (0.0, 0.0)
        self.next_look = time.time() + random.uniform(1.5, 4)
        self.items = []
        self.speaking = 0.0           # animates while the creature is talking

        # -- gaze / eye-contact rig ------------------------------------
        # `gaze` is a point in CANVAS space the creature is trying to look
        # at (the live cursor, a friend, a point of interest).  Eyes lead,
        # the head/neck follows a beat later with a smaller amplitude and a
        # hard anatomical limit - which is what stops it reading as a
        # billboard that snaps to the mouse.
        self.gaze = None                  # (x, y) or None -> idle wandering
        self.gaze_weight = 0.0            # 0..1 how committed the look is
        self.eye_yaw = 0.0                # -1..1 normalised eye direction
        self.eye_pitch = 0.0
        self.head_yaw = 0.0               # -1..1, lags the eyes
        self.head_pitch = 0.0
        self.avert_until = 0.0            # nervous glance-away window
        self.next_avert = time.time() + random.uniform(4, 9)
        self.attention = 0.0              # 0..1 drives posture + gaze gain
        self.head_anchor = (x, y - 55)    # updated every draw for hit-tests

        # -- per-instance body identity: rolled ONCE at birth from a seed
        # that is saved and reloaded with the rest of the creature's state
        # (Personality.body_seed) - so it keeps its own body across
        # restarts, and that body is shaped a little by who it is, not
        # just randomised. Falls back to a throwaway per-launch look only
        # if no identity was supplied (e.g. a bare/test Creature).
        # (a private RNG stream so this never disturbs the global `random`
        # calls the rest of the sim relies on for behaviour/timing)
        identity = identity or {}
        seed = identity.get("body_seed")
        if seed is None:
            seed = (id(self) ^ int(time.time() * 1000)) & 0xFFFFFFFF
        traits = identity.get("traits") or {}
        energy_t = traits.get("energy", 0.5)
        confidence_t = traits.get("confidence", 0.5)
        curiosity_t = traits.get("curiosity", 0.5)
        humour_t = traits.get("humour", 0.5)
        rnd = random.Random(seed)
        # confident creatures carry themselves straighter; energetic ones
        # read a little larger/springier; curious ones a bit more coltish;
        # a playful streak shows up as more mismatched ears - small, honest
        # readouts of the persistent Personality, not just cosmetic noise
        self.asym = rnd.uniform(-2.2, 2.2) * (1.35 - 0.6 * confidence_t)
        self.build = rnd.uniform(0.93, 1.07) * (0.94 + 0.14 * energy_t)
        self.limb_ratio = rnd.uniform(0.9, 1.1) * (0.95 + 0.12 * curiosity_t)
        self.ear_l = rnd.uniform(0.8, 1.2) * (0.88 + 0.32 * humour_t)
        self.ear_r = rnd.uniform(0.8, 1.25) * (0.88 + 0.32 * humour_t)
        self.skull_shift = rnd.uniform(-1.5, 1.5)
        self.gait_offset = rnd.uniform(0, math.tau)
        # a persistent colour identity, independent of mood, so the same
        # creature always reads as itself even as its emotion colour shifts
        hue_rnd = random.Random(seed ^ 0x9E3779B1)
        self.identity_tint = "#%02x%02x%02x" % (
            hue_rnd.randint(80, 235), hue_rnd.randint(80, 235), hue_rnd.randint(80, 235))

        # -- graceful degradation on weak hardware (cheap: no subprocess,
        # just a core-count heuristic so this never adds startup latency) --
        self.detail = "low" if (os.cpu_count() or 4) <= 2 else "high"

    # -- primitives ----------------------------------------------------
    def _poly(self, pts, fill, outline="#0a0c10"):
        i = self.c.create_polygon(pts, fill=fill, outline=outline, width=2)
        self.items.append(i)
        return i

    def _oval(self, x0, y0, x1, y1, fill, outline="#0a0c10"):
        i = self.c.create_oval(x0, y0, x1, y1, fill=fill, outline=outline, width=2)
        self.items.append(i)
        return i

    def _line(self, *coords, **kw):
        i = self.c.create_line(*coords, **kw)
        self.items.append(i)
        return i

    def _arc(self, *coords, **kw):
        i = self.c.create_arc(*coords, **kw)
        self.items.append(i)
        return i

    def clear(self):
        for i in self.items:
            self.c.delete(i)
        self.items = []

    def set_target(self, tx, ty):
        xmin, ymin, xmax, ymax = self.bounds
        self.target = (max(xmin, min(xmax, tx)), max(ymin, min(ymax, ty)))

    def set_behavior(self, name):
        self.behavior = name

    def set_emotion(self, name, intensity=0.3):
        self.emotion = name
        self.intensity = clamp01(intensity)

    def look_at(self, x, y, weight=1.0):
        """Point the gaze rig at a canvas position. Smoothed in update()."""
        self.gaze = (float(x), float(y))
        self.gaze_weight = clamp01(weight)

    def look_away(self):
        self.gaze = None
        self.gaze_weight = 0.0

    def set_attention(self, value):
        self.attention = clamp01(value)

    # emotion -> (gaze gain, tracking speed, avert chance)
    GAZE_STYLE = {
        "curious":      (1.00, 7.0, 0.00),
        "excited":      (0.95, 8.0, 0.00),
        "surprised":    (1.00, 9.0, 0.00),
        "happy":        (0.90, 6.0, 0.00),
        "affectionate": (0.95, 5.0, 0.00),
        "confident":    (0.90, 6.0, 0.00),
        "calm":         (0.75, 3.5, 0.02),
        "neutral":      (0.80, 4.5, 0.02),
        "bored":        (0.55, 2.5, 0.10),
        "tired":        (0.45, 1.8, 0.06),
        "sad":          (0.50, 2.2, 0.18),
        "anxious":      (0.85, 6.5, 0.38),
        "scared":       (0.90, 8.0, 0.45),
        "angry":        (1.00, 7.5, 0.05),
        "frustrated":   (0.85, 6.0, 0.12),
    }

    def set_detail(self, level):
        """'high' or 'low' - lets the app override the auto-picked detail
        level (e.g. from a future settings toggle) without touching the
        rest of the rig."""
        self.detail = "low" if level == "low" else "high"

    # -- animation -----------------------------------------------------
    def update(self, dt):
        self.t += dt
        now = time.time()
        self.speaking = max(0.0, self.speaking - dt)

        speed = {"move": 60, "curious": 35, "rest": 0, "alert": 0}.get(self.behavior, 15)
        if self.emotion in ("tired", "sad"):
            speed *= 0.6
        elif self.emotion in ("excited",):
            speed *= 1.25
        tx, ty = self.target
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist > 2 and speed > 0:
            step = min(dist, speed * dt)
            self.x += dx / dist * step
            self.y += dy / dist * step

        if now > self.next_blink:
            self.blink_until = now + 0.15
            self.next_blink = now + random.uniform(2, 5)
        gain, speed, avert_chance = self.GAZE_STYLE.get(
            self.emotion, (0.8, 4.5, 0.02))
        gain *= 0.55 + 0.45 * self.attention
        speed *= 0.6 + 0.6 * self.attention

        # nervous / low states occasionally break eye contact for a moment
        if self.gaze and now > self.next_avert:
            self.next_avert = now + random.uniform(3.5, 9.0)
            if random.random() < avert_chance:
                self.avert_until = now + random.uniform(0.4, 1.1)
        averting = now < self.avert_until

        if self.gaze and not averting:
            hx, hy = self.head_anchor
            dx, dy = self.gaze[0] - hx, self.gaze[1] - hy
            # normalise into an anatomically believable cone rather than
            # letting the eyes point anywhere on screen
            tgt_yaw = clamp(dx / 240.0, -1.0, 1.0) * gain * self.gaze_weight
            tgt_pitch = clamp(dy / 180.0, -1.0, 1.0) * gain * self.gaze_weight
        else:
            if now > self.next_look:
                self.look_target = (random.uniform(-1, 1), random.uniform(-0.6, 0.6))
                self.next_look = now + random.uniform(1.5, 4)
            tgt_yaw, tgt_pitch = self.look_target
            if averting:
                tgt_yaw = clamp(tgt_yaw + (0.6 if self.asym > 0 else -0.6), -1, 1)
            speed = max(1.6, speed * 0.5)

        self.eye_yaw = approach(self.eye_yaw, tgt_yaw, speed, dt)
        self.eye_pitch = approach(self.eye_pitch, tgt_pitch, speed, dt)
        # head trails the eyes: slower, smaller, and clamped tighter
        self.head_yaw = approach(self.head_yaw, self.eye_yaw * 0.62, speed * 0.38, dt)
        self.head_pitch = approach(self.head_pitch, self.eye_pitch * 0.45, speed * 0.32, dt)
        self.head_yaw = clamp(self.head_yaw, -0.85, 0.85)
        self.head_pitch = clamp(self.head_pitch, -0.7, 0.7)

        # pupil offsets in pixels (what draw() consumes)
        self.look_x = self.eye_yaw * 5.0
        self.look_y = self.eye_pitch * 3.0

    # -- skeleton: joint positions for the current frame -----------------
    def _pose(self, cx, cy, moving, tilt, gesture):
        b = self.build
        phase = self.t * (8 if moving else 1.6) + self.gait_offset

        # landmarks are calibrated so feet land ~85px below cy and the head
        # centre lands ~55px above it - the same envelope the original
        # hexagon-blob creature used, so the ground line / click-to-pet
        # radius / stage bounds (tuned for that envelope) still line up
        # with the now much more articulated rig without retuning those.
        pelvis = (cx, cy + 42 * b)
        spine1 = (cx, cy + 20 * b)
        chest = (cx + tilt * 0.35, cy - 2 * b)
        neck = (cx + tilt * 0.7, cy - 24 * b)

        legs = {}
        for side, sgn in (("L", -1), ("R", 1)):
            hip = (cx + sgn * 10 * b, cy + 46 * b)
            p = phase + (0 if sgn < 0 else math.pi)
            swing = math.sin(p) * (15 if moving else 1.5)
            lift = max(0.0, math.sin(p)) * (6 if moving else 0)
            knee = (hip[0] + swing * 0.35, hip[1] + 17 * b * self.limb_ratio - lift)
            ankle = (hip[0] + swing, hip[1] + 35 * b * self.limb_ratio)
            legs[side] = (hip, knee, ankle)

        arms = {}
        for side, sgn in (("L", -1), ("R", 1)):
            shoulder = (chest[0] + sgn * 23 * b, chest[1] + 5 * b)
            p = phase + (math.pi if sgn < 0 else 0)         # opposite the legs
            swing = math.sin(p) * (13 if moving else 3.5) + gesture * sgn
            elbow = (shoulder[0] + sgn * 3 * b + swing * 0.3,
                     shoulder[1] + 21 * b * self.limb_ratio)
            wrist = (shoulder[0] + sgn * 5 * b + swing,
                     shoulder[1] + 40 * b * self.limb_ratio)
            arms[side] = (shoulder, elbow, wrist)

        return pelvis, spine1, chest, neck, legs, arms

    def draw(self):
        self.clear()
        moving = self.behavior in ("move", "curious")
        low = self.detail == "low"

        bob_speed = 6 if moving else 2
        bob_amp = 6 if moving else 4
        if self.emotion in ("excited", "surprised"):
            bob_speed += 2
            bob_amp += 2
        elif self.emotion in ("bored", "tired", "sad"):
            bob_speed = max(1, bob_speed - 1)
            bob_amp = max(1, bob_amp - 2)
        if self.speaking > 0:
            bob_speed += 1
        bob = math.sin(self.t * bob_speed) * bob_amp
        cx, cy = self.x, self.y + bob
        body_color = _mix_hex(EMOTION_COLORS.get(self.emotion, "#7fc45f"),
                              self.identity_tint, 0.15)
        head_color = _mix_hex(EMOTION_COLORS.get(self.emotion, "#8fd66a"),
                              self.identity_tint, 0.15)
        limb_color = _shade(body_color, 0.82)
        joint_color = _shade(body_color, 0.55)

        tilt = 8 if (self.behavior == "curious" or self.emotion == "curious") else 0
        tilt += self.head_yaw * 9.0          # head/neck turns toward the gaze
        if self.emotion in ("sad", "tired", "bored"):
            tilt *= 0.6
        gesture = math.sin(self.t * 3.1) * 3 if self.speaking > 0 else 0
        breath = math.sin(self.t * (2.2 + 2.0 * self.intensity)) * 1.5

        pelvis, spine1, chest, neck, legs, arms = self._pose(cx, cy, moving, tilt, gesture)

        # soft shadow on the floor - stretches a little with the bob so the
        # creature reads as having weight, not just floating up and down
        shadow_w = 34 - bob * 0.4
        sh = self.c.create_oval(cx - shadow_w, self.y + 78, cx + shadow_w, self.y + 92,
                                fill="#0a0d12", outline="")
        self.items.append(sh)

        # -- legs: hip -> knee -> ankle, tapered, with a small foot pad ----
        for side in ("L", "R"):
            hip, knee, ankle = legs[side]
            thigh_c = limb_color if side == "R" else _shade(limb_color, 0.92)
            self._poly(_limb_quad(hip, knee, 9 * self.build, 6.5 * self.build), thigh_c)
            self._poly(_limb_quad(knee, ankle, 6.5 * self.build, 4.5 * self.build),
                      _shade(thigh_c, 0.88))
            fx, fy = ankle
            fdir = 1 if side == "R" else -1
            self._poly([fx - 7, fy - 2, fx + fdir * 10, fy - 1, fx + fdir * 12, fy + 6,
                       fx - 6, fy + 7], _shade(thigh_c, 0.7))
            if not low:
                self._oval(knee[0] - 3, knee[1] - 3, knee[0] + 3, knee[1] + 3,
                          joint_color, "")

        # -- torso: pelvis wedge + abdomen plate + chest plate (segmented,
        # not one blob) - breathing widens the chest plate a little ---------
        pw = 30 * self.build
        if not low:
            self._poly(_limb_quad(pelvis, spine1, pw * 0.5, pw * 0.66),
                      _shade(body_color, 0.8))
        self._poly(_limb_quad(spine1, chest, pw * 0.68, pw * 0.8 + breath), body_color)

        # -- arms: shoulder -> elbow -> wrist, tapered, small hand ---------
        for side in ("L", "R"):
            shoulder, elbow, wrist = arms[side]
            self._poly(_limb_quad(shoulder, elbow, 7 * self.build, 5.3 * self.build),
                      limb_color)
            self._poly(_limb_quad(elbow, wrist, 5.3 * self.build, 3.8 * self.build),
                      _shade(limb_color, 0.9))
            self._oval(wrist[0] - 5, wrist[1] - 5, wrist[0] + 5, wrist[1] + 5,
                      _shade(limb_color, 0.85))
            if not low:
                self._oval(elbow[0] - 2.5, elbow[1] - 2.5, elbow[0] + 2.5, elbow[1] + 2.5,
                          joint_color, "")
                self._oval(shoulder[0] - 3, shoulder[1] - 3, shoulder[0] + 3, shoulder[1] + 3,
                          joint_color, "")

        # -- neck --------------------------------------------------------
        self._poly(_limb_quad(chest, neck, 10 * self.build, 8 * self.build),
                  _shade(head_color, 0.78))

        # -- skull (asymmetric, per-instance) -----------------------------
        hx = neck[0] + tilt * 0.3 + self.skull_shift + self.head_yaw * 4.0
        hy = neck[1] - 22 * self.build + self.head_pitch * 3.5
        self.head_anchor = (hx, hy)
        sw = 30 * self.build
        self._poly([hx - sw - self.asym, hy + 10, hx - sw * 0.92, hy - 16,
                   hx + self.skull_shift * 2, hy - 34 * self.build,
                   hx + sw * 0.92, hy - 16, hx + sw + self.asym, hy + 10,
                   hx, hy + 20], head_color)

        # -- ears / sensory nubs, deliberately not a matched pair ----------
        if not low:
            self._poly([hx - sw - 1, hy - 3, hx - sw - 9 * self.ear_l, hy - 11 * self.ear_l,
                       hx - sw - 3, hy + 7], _shade(head_color, 0.8))
            self._poly([hx + sw + 1, hy - 3, hx + sw + 9 * self.ear_r, hy - 11 * self.ear_r,
                       hx + sw + 3, hy + 7], _shade(head_color, 0.8))

        # -- jaw: a hinged plate under the skull that actually opens while
        # the creature talks, instead of just swapping a mouth icon ---------
        jaw_open = 2 + (6 if self.speaking > 0 and math.sin(self.t * 16) > 0 else 0)
        self._poly([hx - 15, hy + 15, hx + 15, hy + 15,
                   hx + 11, hy + 16 + jaw_open, hx - 11, hy + 16 + jaw_open],
                  _shade(head_color, 0.72))

        # -- eyes / mouth: same per-emotion table as before, so all 14
        # emotions still read distinctly on the (now more detailed) face ---
        eye_style, mouth_style = FACE.get(self.emotion, ("open", "small_smile"))
        blinking = time.time() < self.blink_until and eye_style not in ("wide", "closed")
        ex_off = self.look_x

        for side in (-1, 1):
            ex, ey = hx + side * 12, hy - 4
            if eye_style == "closed" or (eye_style == "half" and blinking):
                self._line(ex - 7, ey, ex + 7, ey - 3, fill="#1a1a1a", width=3)
            elif eye_style == "half":
                self._line(ex - 7, ey, ex + 7, ey - 1, fill="#1a1a1a", width=3)
            elif blinking:
                self._line(ex - 6, ey, ex + 6, ey, fill="#1a1a1a", width=2)
            else:
                r = {"wide": 10, "soft": 6, "sad": 7, "angry": 7}.get(eye_style, 7)
                self._oval(ex - r, ey - r, ex + r, ey + r, "#fff")
                pupil = 3 if eye_style != "wide" else 3.5
                py = ey - 3 + self.look_y + (2 if eye_style == "sad" else 0)
                self._oval(ex - pupil + ex_off, py, ex + pupil + ex_off, py + 2 * pupil,
                          "#1a1a1a")
                if eye_style == "angry":
                    self._line(ex - 9, ey - 11 + abs(side) * 0, ex + 9 * side, ey - 6,
                              fill="#1a1a1a", width=3)
                elif eye_style == "sad":
                    self._line(ex - 9, ey - 9, ex + 9 * side, ey - 12,
                              fill="#1a1a1a", width=2)

        talk = 4 if self.speaking > 0 and math.sin(self.t * 16) > 0 else 0
        if mouth_style == "smile":
            self._arc(hx - 12, hy + 2, hx + 12, hy + 18 + talk, start=200, extent=140,
                     style=tk.ARC, width=3)
        elif mouth_style == "big_smile":
            self._arc(hx - 14, hy, hx + 14, hy + 20 + talk, start=190, extent=160,
                     style=tk.ARC, width=4)
        elif mouth_style == "small_smile":
            self._arc(hx - 10, hy + 6, hx + 10, hy + 18 + talk, start=200, extent=140,
                     style=tk.ARC, width=2)
        elif mouth_style == "smirk":
            self._arc(hx - 4, hy + 4, hx + 14, hy + 16, start=200, extent=120,
                     style=tk.ARC, width=3)
        elif mouth_style == "frown":
            self._arc(hx - 11, hy + 10, hx + 11, hy + 26, start=20, extent=140,
                     style=tk.ARC, width=3)
        elif mouth_style == "o":
            self._oval(hx - 6, hy + 8, hx + 6, hy + 18 + talk, "#3a1414")
        elif mouth_style == "small_o":
            self._oval(hx - 4, hy + 9, hx + 4, hy + 16 + talk, "#3a1414")
        elif mouth_style == "wobble":
            self._line(hx - 9, hy + 14, hx - 3, hy + 10, hx + 3, hy + 14, hx + 9, hy + 10,
                      fill="#1a1a1a", width=2, smooth=True)
        else:   # flat
            self._line(hx - 8, hy + 13, hx + 8, hy + 13, fill="#1a1a1a", width=2)
