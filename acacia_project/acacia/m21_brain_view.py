

# ============================================================================
# [9.7] BRAIN VIEW  (anatomical activity render - see note below)
# ============================================================================
def _b3(v, lo=0.33, hi=0.66):
    return 0 if v < lo else (1 if v < hi else 2)

BRAIN_BASE = "#f2456b"          # the body of the brain

BRAIN_DEEP = "#c11f4b"          # sulci / shading

BRAIN_LIT = "#ff9ab0"           # an active region

BRAIN_EDGE = "#15181f"

BRAIN_REGIONS = [
    ("frontal",    28,  0.60, 0.40, "reasoning",    "REASONING"),
    ("prefrontal", -6,  0.66, 0.34, "planning",     "PLANNING"),
    ("motor",      74,  0.56, 0.30, "action",       "ACTION"),
    ("parietal",  118,  0.58, 0.34, "self_model",   "SELF"),
    ("occipital", 176,  0.62, 0.32, "perception",   "PERCEPTION"),
    ("temporal",  228,  0.54, 0.34, "memory",       "MEMORY"),
    ("limbic",    300,  0.22, 0.30, "emotion",      "EMOTION"),
    ("assoc",     150,  0.18, 0.26, "world_model",  "WORLD MODEL"),
]

class BrainView:
    """Draws the brain + its live state.  One implementation, used both as
    the compact glyph under the world and as the large panel in MIND."""

    def __init__(self, canvas):
        self.c = canvas
        self.items = []
        self.t = 0.0

    def clear(self):
        for i in self.items:
            self.c.delete(i)
        self.items = []

    def _add(self, i):
        self.items.append(i)
        return i

    @staticmethod
    def _outline(cx, cy, r, steps=48):
        """Cerebrum silhouette: a circle deformed by low-frequency lobe bulges
        plus a high-frequency ripple, which is what reads as folded cortex."""
        pts = []
        for i in range(steps):
            a = math.tau * i / steps
            rad = (1.0 + 0.11 * math.sin(a * 2.0 + 0.6)
                   + 0.07 * math.sin(a * 3.0 - 1.1)
                   + 0.035 * math.sin(a * 7.0))
            # flatten the underside so it sits on the cerebellum/stem
            if math.sin(a) > 0:
                rad *= 1.0 - 0.22 * math.sin(a) ** 2
            pts += [cx + math.cos(a) * r * rad * 1.15,
                    cy + math.sin(a) * r * rad * 0.86]
        return pts

    @staticmethod
    def _blob(cx, cy, r, seed, wob=0.20, steps=18):
        rnd = random.Random(seed)
        offs = [rnd.uniform(1 - wob, 1 + wob) for _ in range(steps)]
        pts = []
        for i in range(steps):
            a = math.tau * i / steps
            rad = r * offs[i]
            pts += [cx + math.cos(a) * rad * 1.1, cy + math.sin(a) * rad * 0.92]
        return pts

    def draw(self, cx, cy, r, levels, label=True, sparkle=0.0):
        """levels: {stage: 0..1} straight from Brain.activity_levels()."""
        self.clear()
        self.t += 0.033
        c = self.c

        # drop shadow, like the reference illustration
        self._add(c.create_oval(cx - r * 0.95, cy + r * 0.80, cx + r * 0.95,
                                cy + r * 1.00, fill="#1b1f2a", outline=""))
        # cerebellum (behind + below, left/back of a right-facing brain)
        cbx, cby = cx - r * 0.62, cy + r * 0.52
        self._add(c.create_polygon(self._blob(cbx, cby, r * 0.34, 7, 0.10),
                                   fill=BRAIN_DEEP, outline=BRAIN_EDGE,
                                   width=max(2, r * 0.035), smooth=True))
        for k in range(4):
            yy = cby - r * 0.18 + k * r * 0.13
            self._add(c.create_line(cbx - r * 0.30, yy, cbx + r * 0.28, yy - r * 0.04,
                                    fill=BRAIN_EDGE, width=max(1, r * 0.016),
                                    smooth=True))
        # brainstem
        self._add(c.create_polygon(
            cbx + r * 0.02, cby - r * 0.10, cbx + r * 0.30, cby - r * 0.04,
            cbx + r * 0.26, cby + r * 0.62, cbx + r * 0.04, cby + r * 0.58,
            fill=BRAIN_DEEP, outline=BRAIN_EDGE, width=max(2, r * 0.03),
            smooth=True))

        # cerebrum body
        self._add(c.create_polygon(self._outline(cx, cy, r), fill=BRAIN_BASE,
                                   outline=BRAIN_EDGE, width=max(2, r * 0.045),
                                   smooth=True))

        # the great longitudinal fissure + a few sulci, so it is not a blob
        self._add(c.create_line(cx - r * 0.80, cy + r * 0.10, cx - r * 0.10,
                                cy + r * 0.26, cx + r * 0.62, cy + r * 0.08,
                                fill=BRAIN_EDGE, width=max(2, r * 0.032),
                                smooth=True))
        for k in range(4):
            a0 = 0.5 + k * 0.72
            self._add(c.create_line(
                cx + math.cos(a0) * r * 0.20, cy + math.sin(a0) * r * 0.16,
                cx + math.cos(a0 + 0.35) * r * 0.62, cy + math.sin(a0 + 0.35) * r * 0.50,
                cx + math.cos(a0 + 0.05) * r * 0.92, cy + math.sin(a0 + 0.05) * r * 0.66,
                fill=BRAIN_DEEP, width=max(1, r * 0.022), smooth=True))

        # ---- the regions: each one is a stage of the loop -----------------
        hottest, hot_level = None, 0.0
        for idx, (name, ang, dist, size, stage, text) in enumerate(BRAIN_REGIONS):
            lvl = clamp01(levels.get(stage, 0.0))
            if lvl > hot_level:
                hottest, hot_level = text, lvl
            a = math.radians(ang)
            rx = cx + math.cos(a) * r * dist * 1.05
            ry = cy + math.sin(a) * r * dist * 0.80
            fill = _mix_hex(BRAIN_BASE, BRAIN_LIT, lvl)
            if lvl < 0.12:
                fill = _mix_hex(BRAIN_BASE, BRAIN_DEEP, 0.35)
            self._add(c.create_polygon(
                self._blob(rx, ry, r * size, idx * 17 + 3),
                fill=fill, outline=BRAIN_EDGE, width=max(1, r * 0.028),
                smooth=True))
            if lvl > 0.45:
                # an active region gets a bright rim, not a fake glow blur
                self._add(c.create_polygon(
                    self._blob(rx, ry, r * size * 1.02, idx * 17 + 3),
                    fill="", outline=_mix_hex(BRAIN_LIT, "#ffffff", lvl * 0.6),
                    width=max(1, r * 0.022), smooth=True))

        # specular highlights, the cartoon-illustration cue
        self._add(c.create_oval(cx + r * 0.30, cy - r * 0.56, cx + r * 0.52,
                                cy - r * 0.40, fill="#ffd8e0", outline=""))
        self._add(c.create_oval(cx - r * 0.30, cy - r * 0.64, cx - r * 0.16,
                                cy - r * 0.54, fill="#ffd8e0", outline=""))

        # sparkles: these fire on real learning events, not on a timer
        if sparkle > 0.05:
            for k in range(3):
                a = 2.1 + k * 2.0 + self.t * 0.4
                sx = cx + math.cos(a) * r * 1.22
                sy = cy + math.sin(a) * r * 0.95
                s = r * (0.09 + 0.05 * sparkle) * (0.7 + 0.3 * math.sin(self.t * 4 + k))
                self._add(c.create_polygon(
                    sx, sy - s, sx + s * 0.26, sy - s * 0.26, sx + s, sy,
                    sx + s * 0.26, sy + s * 0.26, sx, sy + s,
                    sx - s * 0.26, sy + s * 0.26, sx - s, sy,
                    sx - s * 0.26, sy - s * 0.26,
                    fill=_mix_hex(BRAIN_LIT, "#ffffff", sparkle), outline=""))

        if label and hottest:
            self._add(c.create_text(cx, cy + r * 1.28, text=hottest,
                                    fill=_mix_hex(C_FAINT, BRAIN_LIT, hot_level),
                                    font=("Segoe UI Semibold", 8)))
        return hottest or "IDLE"
