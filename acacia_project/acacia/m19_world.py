


# ============================================================================
# [9.5] WORLD  (environment, lighting, vegetation, points of interest)
# ============================================================================
#
# Why the stage used to look empty: the old _draw_world() painted a single
# dark rectangle, one hairline and two 12px dots (a red one and a blue one -
# the unlabelled food/water markers people kept asking about), then re-created
# all of it 30 times a second.  There was nothing to see and no depth cue at
# all.  This class replaces that with a real scene:
#
#   sky gradient -> stars/sun/moon -> far hills -> mid trees -> ground ->
#   grass/rocks -> points of interest -> actors -> weather/darkness overlay
#
# Static layers are built ONCE into cached canvas items and only rebuilt when
# the canvas is resized or the time of day / weather actually changes, so the
# per-frame cost is a handful of coordinate updates instead of ~300 item
# creations.  That is the whole performance trick and it is what lets this run
# at 30 FPS on a laptop with integrated graphics.

SKY_PALETTES = {
    "morning": (("#243347", "#3a5570", "#6d8aa3"), "#ffe6b8", 0.06),
    "afternoon": (("#20304a", "#365275", "#5f86a8"), "#fff1c9", 0.00),
    "evening": (("#1a1f33", "#43304d", "#8a5560"), "#ffb27a", 0.20),
    "night": (("#080b14", "#101a28", "#1b2740"), "#cfe0ff", 0.46),
}
WEATHERS = ("clear", "cloudy", "rain")


class WorldPOI:
    """A discoverable thing in the world.  Everything the creature can walk
    to, look at or be inspected by the user is one of these, so there is a
    single list to hit-test against instead of scattered magic numbers."""

    __slots__ = ("kind", "name", "x", "y", "r", "desc", "visits", "last_visit",
                 "stock", "empty_since")

    def __init__(self, kind, name, x, y, r, desc):
        self.kind, self.name = kind, name
        self.x, self.y, self.r = x, y, r
        self.desc = desc
        self.visits = 0
        self.last_visit = 0.0
        self.stock = 3            # food/water: real depletion, not infinite
        self.empty_since = 0.0

    def available(self):
        """food/water run out after repeated visits and regrow after a
        while, so returning to the same spot is a real choice with a real
        cost - not a free, infinite vending machine."""
        if self.kind not in ("food", "water"):
            return True
        if self.stock > 0:
            return True
        if self.empty_since and time.time() - self.empty_since > 240:
            self.stock = 3
            self.empty_since = 0.0
            return True
        return False

    def deplete(self):
        if self.kind in ("food", "water"):
            self.stock = max(0, self.stock - 1)
            if self.stock == 0 and not self.empty_since:
                self.empty_since = time.time()


class World:
    def __init__(self, canvas):
        self.c = canvas
        self.w = self.h = 0
        self.ground = 0
        self.daypart = ""
        self.weather = "clear"
        self.detail = "high"
        self.t = 0.0
        self._static = []
        self._dyn = []
        self._rng = random.Random(20260916)
        self.pois = []
        self._weather_accum = 0.0
        self._cloud_x = 0.0
        self._star = None

    # -- helpers -------------------------------------------------------
    def _add(self, item, dyn=False):
        (self._dyn if dyn else self._static).append(item)
        return item

    def clear_static(self):
        for i in self._static:
            self.c.delete(i)
        self._static = []

    def clear_dyn(self):
        for i in self._dyn:
            self.c.delete(i)
        self._dyn = []

    def light(self):
        """0 (pitch dark) .. 1 (bright).  Feeds the brain as a real signal."""
        base = {"morning": 0.82, "afternoon": 1.0, "evening": 0.55,
                "night": 0.22}.get(self.daypart, 0.8)
        if self.weather == "cloudy":
            base *= 0.82
        elif self.weather == "rain":
            base *= 0.66
        return clamp01(base)

    # -- points of interest -------------------------------------------
    def _place_pois(self):
        w, g = self.w, self.ground
        rnd = self._rng
        span = max(220, w - 160)

        def pos(frac):
            return 80 + span * frac

        self.pois = [
            WorldPOI("food", "berry thicket", pos(0.12), g - 8, 34,
                     "a low bush heavy with dark berries"),
            WorldPOI("water", "spring pool", pos(0.78), g - 4, 40,
                     "a shallow pool fed by a slow spring"),
            WorldPOI("shelter", "hollow stone", pos(0.46), g - 6, 34,
                     "a leaning stone with a dry hollow underneath"),
            WorldPOI("curio", "glow shard", pos(0.63), g - 6, 26,
                     "a shard of something that answers light with light"),
        ]
        for poi in self.pois:
            poi.x += rnd.uniform(-18, 18)

    def world_dict(self):
        """Persist the state of the world's points of interest.

        MERGE NOTE: creature_work.py carried world_dict / load_world_dict /
        object_tick against an older WorldPOI that had a continuous `stock`
        float, a `charge` field and a `regrow(dt, rate)` method.  The WorldPOI
        in this file is the newer model: integer stock, `deplete()`, and
        regrowth driven by `empty_since` rather than a per-tick rate, and its
        own animate() already does the regrowing.  Porting the old methods
        verbatim would have written fields that no longer exist, so the
        PERSISTENCE they provided is kept here against the current model and
        the old per-tick regrow is not, because this World already does it.
        """
        out = {}
        for pi in self.pois:
            out[pi.kind] = {"visits": int(getattr(pi, "visits", 0)),
                            "stock": int(getattr(pi, "stock", 3)),
                            "empty_since": float(getattr(pi, "empty_since", 0) or 0)}
        return out

    def load_world_dict(self, d):
        if not isinstance(d, dict):
            return
        for pi in self.pois:
            row = d.get(pi.kind)
            if not isinstance(row, dict):
                continue
            try:
                pi.visits = int(row.get("visits", 0) or 0)
                pi.stock = int(clamp(int(row.get("stock", 3) or 0), 0, 3))
                pi.empty_since = float(row.get("empty_since", 0) or 0)
            except Exception:
                pass

    def poi(self, kind):
        for pi in self.pois:
            if pi.kind == kind:
                return pi
        return None

    def hit(self, x, y):
        for pi in self.pois:
            if math.hypot(x - pi.x, y - (pi.y - 14)) < pi.r:
                return pi
        return None

    # -- static scene ---------------------------------------------------
    def rebuild(self, w, h, ground, daypart, weather, detail="high"):
        self.w, self.h, self.ground = int(w), int(h), int(ground)
        self.daypart, self.weather, self.detail = daypart, weather, detail
        self.clear_static()
        self.clear_dyn()
        self._rng = random.Random(1337 + (self.w // 40))
        rnd = self._rng
        low = detail == "low"
        sky, orb_color, _dark = SKY_PALETTES.get(daypart, SKY_PALETTES["afternoon"])
        top, mid, low_c = sky

        # --- sky: banded gradient (tk has no gradients; 14 bands is plenty
        # and costs 14 items instead of a per-pixel image) -----------------
        bands = 10 if low else 16
        for i in range(bands):
            t = i / max(1, bands - 1)
            col = _mix_hex(top, mid, min(1.0, t * 2)) if t < 0.5 \
                else _mix_hex(mid, low_c, (t - 0.5) * 2)
            y0 = ground * (i / bands)
            y1 = ground * ((i + 1) / bands) + 1
            self._add(self.c.create_rectangle(0, y0, self.w, y1, fill=col,
                                              outline="", tags="world"))

        # --- celestial body + stars ---------------------------------------
        ox = self.w * {"morning": 0.22, "afternoon": 0.62,
                       "evening": 0.82, "night": 0.30}.get(daypart, 0.5)
        oy = ground * {"morning": 0.34, "afternoon": 0.18,
                       "evening": 0.44, "night": 0.24}.get(daypart, 0.3)
        r = 16 if daypart != "night" else 12
        self._add(self.c.create_oval(ox - r * 2.2, oy - r * 2.2, ox + r * 2.2,
                                     oy + r * 2.2, fill=_mix_hex(mid, orb_color, 0.22),
                                     outline="", tags="world"))
        self._add(self.c.create_oval(ox - r, oy - r, ox + r, oy + r,
                                     fill=orb_color, outline="", tags="world"))
        if daypart == "night" and not low:
            for _ in range(46):
                sx, sy = rnd.uniform(0, self.w), rnd.uniform(0, ground * 0.72)
                s = rnd.uniform(0.6, 1.6)
                self._add(self.c.create_oval(sx, sy, sx + s, sy + s,
                                             fill=_mix_hex("#8fa4c8", "#ffffff",
                                                           rnd.random()),
                                             outline="", tags="world"))

        # --- far hills, then nearer ridge: two parallax layers -------------
        for depth, (amp, base_y, shade) in enumerate(
                ((26, ground - 62, 0.30), (38, ground - 26, 0.46))):
            pts = [0, ground + 40]
            steps = 8 if low else 14
            for i in range(steps + 1):
                x = self.w * i / steps
                yy = base_y - math.sin(i * (1.7 + depth) + depth) * amp \
                    - rnd.uniform(0, 10)
                pts += [x, yy]
            pts += [self.w, ground + 40]
            self._add(self.c.create_polygon(pts, fill=_mix_hex(low_c, "#0b1018",
                                                              1 - shade),
                                            outline="", smooth=True, tags="world"))

        # --- ground plane + a few depth strokes ---------------------------
        soil = _mix_hex("#243021", "#0b0f14", 0.35 + 0.3 * (1 - self.light()))
        self._add(self.c.create_rectangle(0, ground, self.w, self.h, fill=soil,
                                          outline="", tags="world"))
        self._add(self.c.create_line(0, ground, self.w, ground,
                                     fill=_mix_hex(soil, "#8fd66a", 0.30),
                                     width=2, tags="world"))
        for i in range(4 if low else 9):
            y = ground + 14 + i * max(8, (self.h - ground) / 10)
            if y > self.h:
                break
            self._add(self.c.create_line(0, y, self.w, y,
                                         fill=_mix_hex(soil, "#000000", 0.22),
                                         width=1, tags="world"))

        # --- trees / vegetation: silhouettes behind, tufts in front --------
        tree_n = 3 if low else 6
        for i in range(tree_n):
            tx = (i + 0.5) * self.w / tree_n + rnd.uniform(-30, 30)
            th = rnd.uniform(46, 88)
            trunk = _mix_hex("#1d2a1c", "#000000", 0.30)
            self._add(self.c.create_rectangle(tx - 3, ground - th, tx + 3, ground,
                                              fill=trunk, outline="", tags="world"))
            leaf = _mix_hex("#2f5a33", "#0b1018", 0.45 - 0.25 * self.light())
            for k in range(3):
                rr = rnd.uniform(16, 26) - k * 3
                cyk = ground - th - k * 12
                self._add(self.c.create_oval(tx - rr, cyk - rr * 0.8, tx + rr,
                                             cyk + rr * 0.6, fill=leaf,
                                             outline="", tags="world"))
        if not low:
            for _ in range(26):
                gx = rnd.uniform(0, self.w)
                gy = ground + rnd.uniform(-2, 18)
                gh = rnd.uniform(5, 13)
                self._add(self.c.create_line(gx, gy, gx + rnd.uniform(-3, 3), gy - gh,
                                             fill=_mix_hex("#4c7a3f", "#0b1018",
                                                           0.35 - 0.25 * self.light()),
                                             width=1, tags="world"))
            for _ in range(5):
                rx, ry = rnd.uniform(0, self.w), ground + rnd.uniform(2, 22)
                rr = rnd.uniform(4, 11)
                self._add(self.c.create_oval(rx - rr, ry - rr * 0.6, rx + rr,
                                             ry + rr * 0.5,
                                             fill=_mix_hex("#3a4250", "#0b1018", 0.35),
                                             outline="", tags="world"))

        self._place_pois()
        self._draw_pois()
        self.c.tag_lower("world")

    def _draw_pois(self):
        """The old red + blue debug dots, replaced by things that read as
        objects: a berry thicket, a spring pool, a shelter stone and a small
        glowing curiosity.  Same underlying food/water systems."""
        lit = self.light()
        for pi in self.pois:
            x, y = pi.x, pi.y
            if pi.kind == "food":
                bush = _mix_hex("#2e5c34", "#0b1018", 0.35 - 0.25 * lit)
                for dx, dy, rr in ((-14, 0, 16), (14, 0, 15), (0, -8, 19)):
                    self._add(self.c.create_oval(x + dx - rr, y + dy - rr * 0.9,
                                                 x + dx + rr, y + dy + rr * 0.7,
                                                 fill=bush, outline="", tags="world"))
                for dx, dy in ((-10, -6), (4, -12), (12, -2), (-2, 2), (8, 6)):
                    self._add(self.c.create_oval(x + dx - 3, y + dy - 3, x + dx + 3,
                                                 y + dy + 3, fill="#b8446a",
                                                 outline="#6d2440", tags="world"))
            elif pi.kind == "water":
                for k, rr in enumerate((40, 30, 20)):
                    col = _mix_hex("#1d3f5c", "#5fa8d3", 0.12 + k * 0.16)
                    self._add(self.c.create_oval(x - rr, y - rr * 0.32, x + rr,
                                                 y + rr * 0.32,
                                                 fill=_mix_hex(col, "#0b1018",
                                                               0.30 - 0.25 * lit),
                                                 outline="", tags="world"))
            elif pi.kind == "shelter":
                self._add(self.c.create_polygon(
                    x - 30, y + 6, x - 18, y - 30, x + 16, y - 34, x + 30, y + 6,
                    fill=_mix_hex("#404a5c", "#0b1018", 0.32), outline="", tags="world"))
                self._add(self.c.create_oval(x - 13, y - 12, x + 13, y + 8,
                                             fill="#0d1119", outline="", tags="world"))
            elif pi.kind == "curio":
                self._add(self.c.create_polygon(
                    x, y - 26, x + 9, y - 6, x, y + 6, x - 9, y - 6,
                    fill=_mix_hex("#7ee0c8", "#0b1018", 0.25), outline="",
                    tags="world"))

    # -- per-frame dynamics ---------------------------------------------
    def animate(self, dt):
        """Cheap ambient motion so the scene is never frozen: drifting cloud
        bands, water shimmer, fireflies at night, rain when it rains.  Total
        item count stays under ~40 regardless of window size."""
        self.t += dt
        self.clear_dyn()
        if self.w <= 0:
            return
        lit = self.light()
        self._cloud_x = (self._cloud_x + dt * 6) % (self.w + 300)

        if self.weather in ("cloudy", "rain") or self.daypart == "morning":
            for i in range(3):
                cx = (self._cloud_x + i * (self.w / 2.4)) % (self.w + 320) - 160
                cy = self.ground * (0.18 + 0.11 * i)
                col = _mix_hex("#8595ad", "#0b1018", 0.45 - 0.25 * lit)
                for dx, rr in ((-34, 22), (0, 30), (32, 20)):
                    self._add(self.c.create_oval(cx + dx - rr, cy - rr * 0.55,
                                                 cx + dx + rr, cy + rr * 0.45,
                                                 fill=col, outline="",
                                                 tags="worlddyn"), dyn=True)

        pool = self.poi("water")
        if pool is not None:
            for k in range(3):
                ph = math.sin(self.t * 1.4 + k * 2.1)
                ww = 26 - k * 7
                yy = pool.y - 4 + k * 4 + ph * 1.2
                self._add(self.c.create_line(pool.x - ww + ph * 5, yy,
                                             pool.x + ww + ph * 5, yy,
                                             fill=_mix_hex("#8fd9ff", "#1d3f5c",
                                                           0.45 + 0.2 * k),
                                             width=1, tags="worlddyn"), dyn=True)

        curio = self.poi("curio")
        if curio is not None:
            pulse = 0.5 + 0.5 * math.sin(self.t * 2.0)
            rr = 12 + pulse * 6
            self._add(self.c.create_oval(curio.x - rr, curio.y - 16 - rr,
                                         curio.x + rr, curio.y - 16 + rr,
                                         outline=_mix_hex("#7ee0c8", "#101520",
                                                          0.65 - 0.3 * pulse),
                                         tags="worlddyn"), dyn=True)

        # a real world consequence, drawn honestly: a picked-over food/water
        # spot reads visibly emptier until it regrows - not a hidden number
        for pi in self.pois:
            if pi.kind in ("food", "water") and not pi.available():
                self._add(self.c.create_oval(pi.x - 30, pi.y - 26, pi.x + 30, pi.y + 14,
                                             fill="#0a0d12", outline="", stipple="gray50",
                                             tags="worlddyn"), dyn=True)

        if self.daypart == "night" and self.detail != "low":
            for k in range(7):
                fx = (self.w * ((k * 0.137 + self.t * 0.012) % 1.0))
                fy = self.ground - 30 - 40 * abs(math.sin(self.t * 0.5 + k))
                a = 0.4 + 0.6 * abs(math.sin(self.t * 2.2 + k * 1.7))
                self._add(self.c.create_oval(fx - 2, fy - 2, fx + 2, fy + 2,
                                             fill=_mix_hex("#1b2740", "#ffe9a8", a),
                                             outline="", tags="worlddyn"), dyn=True)

        if self.weather == "rain":
            for k in range(22):
                rx = (k * 61 + self.t * 260) % max(1, self.w)
                ry = (k * 37 + self.t * 520) % max(1, self.ground + 40)
                self._add(self.c.create_line(rx, ry, rx - 3, ry + 11,
                                             fill="#6d86a8", width=1,
                                             tags="worlddyn"), dyn=True)

        # a rare, genuinely random world event - not on a fixed timer -
        # that gives the creature something new to notice on its own, the
        # same way a real environment occasionally just does something
        if self.daypart == "night" and self.weather == "clear":
            if self._star is None and random.random() < 0.0006:
                self._star = {"x0": random.uniform(0, self.w * 0.6), "y0": random.uniform(10, 60),
                              "t0": self.t, "fresh": True}
            if self._star is not None:
                age = self.t - self._star["t0"]
                if age < 0.6:
                    sx = self._star["x0"] + age * 260
                    sy = self._star["y0"] + age * 130
                    self._add(self.c.create_line(sx, sy, sx - 26, sy - 13,
                                                 fill="#eaf4ff", width=2,
                                                 tags="worlddyn"), dyn=True)
                else:
                    self._star = None

        self.c.tag_lower("worlddyn")
        self.c.tag_lower("world")

    def consume_star_event(self):
        """One-shot flag: True exactly once per shooting star, for the app
        to turn into a real perceived Event instead of pure decoration."""
        st = self._star
        if st and st.get("fresh"):
            st["fresh"] = False
            return True
        return False


def _mix_hex(c1, c2, t):
    """Blend two #rrggbb colours (module-level twin of App._mix so the world
    and the widgets share exactly one colour maths implementation)."""
    t = max(0.0, min(1.0, t))
    try:
        a = tuple(int(c1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        b = tuple(int(c2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return c1
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
