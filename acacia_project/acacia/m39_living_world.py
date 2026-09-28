# ============================================================================
# [NEW] LIVING WORLD  (patch layer, loaded last)
# ============================================================================
#
# 1. World.rebuild (original kept as World._rebuild_classic): the flat
#    backdrop becomes a layered landscape - smooth sky with horizon haze, four
#    mountain/hill ranges with atmospheric perspective and snow on the far
#    peaks, a treeline, varied near vegetation (pines, broadleaf trees,
#    bushes, flowers, grass), shaded rocks and a worn path. Same POIs, same
#    state, same tags; still built once per rebuild and re-projected by the
#    camera. Near trees and grass hand their items to the wind-sway system.
#
# 2. Fauna: a real ecosystem inside the world simulation.
#       spawn   species arrive from the edges by time of day, weather and
#               carrying capacity; well-fed neighbours breed; they leave
#               when they wander off-world.
#       sim     each animal has hunger, energy, fear and a state machine
#               (wander / graze / flee / hunt / sleep / fly / perch). Foxes
#               hunt rabbits; rabbits and deer flee foxes and wolves.
#       percept every animal perceives Jane (distance, her speed) and
#               decides to ignore / watch / flee / approach from its species
#               temperament and how familiar she has become.
#       Jane    perceives animals through Brain.perceive (Events +
#               knowledge.see("animal", ...)), so they reach attention,
#               thoughts, emotion, memory; a wolf feeds her risk system.
#       render  pooled geometry through the camera, colour-graded like the
#               rest of the scene, layered between world and creature.

import math as _lw_math
import random as _lw_random
import time as _lw_time


def _lw_ridge(rng, w, base, amp, rough, n=48):
    """Midpoint-displacement ridgeline -> list of (x, y) across the width."""
    pts = [base + rng.uniform(-amp, amp) * 0.5, base + rng.uniform(-amp, amp) * 0.5]
    a = amp
    while len(pts) < n:
        nxt = []
        for i in range(len(pts) - 1):
            nxt.append(pts[i])
            nxt.append((pts[i] + pts[i + 1]) * 0.5 + rng.uniform(-a, a))
        nxt.append(pts[-1])
        pts = nxt
        a *= rough
    step = (w + 80) / (len(pts) - 1)
    return [(-40 + i * step, y) for i, y in enumerate(pts)]


def _lw_blob(cx, cy, rx, ry, rng, n=9, jag=0.18):
    out = []
    for i in range(n):
        a = _lw_math.tau * i / n
        k = 1.0 + rng.uniform(-jag, jag)
        out += [cx + _lw_math.cos(a) * rx * k, cy + _lw_math.sin(a) * ry * k]
    return out


def _lw_rebuild(self, w, h, ground, daypart, weather, detail="high"):
    self.w, self.h, self.ground = int(w), int(h), int(ground)
    self.daypart, self.weather, self.detail = daypart, weather, detail
    self.clear_static()
    self.clear_dyn()
    self._rng = random.Random(1337 + (self.w // 40) + getattr(self, "_region_seed", 0))
    rnd = self._rng
    low = detail == "low"
    c = self.c
    sky, orb, _dark = SKY_PALETTES.get(daypart, SKY_PALETTES["afternoon"])
    top, mid, horizon = sky
    lit = self.light()
    G = self.ground
    hints = []
    trees = []

    def add(item):
        return self._add(item)

    # --- sky: fine gradient, brightest haze at the horizon -----------------
    bands = 14 if low else 28
    for i in range(bands):
        t = i / (bands - 1)
        col = _mix_hex(top, mid, min(1.0, t * 1.6)) if t < 0.62 else \
            _mix_hex(mid, _mix_hex(horizon, "#c9d6e2", 0.25 * lit), (t - 0.62) / 0.38)
        y0 = G * 0.92 * i / bands
        add(c.create_rectangle(0, y0, self.w, G * 0.92 * (i + 1) / bands + 1, fill=col,
                               outline="", tags="world"))
    add(c.create_rectangle(0, G * 0.92, self.w, G, fill=_mix_hex(horizon, "#d7e0ea", 0.3 * lit),
                           outline="", tags="world"))
    # --- sun / moon with a soft corona -------------------------------------
    ox = self.w * {"morning": 0.22, "afternoon": 0.64, "evening": 0.82, "night": 0.30}.get(daypart, .5)
    oy = G * {"morning": 0.36, "afternoon": 0.17, "evening": 0.46, "night": 0.22}.get(daypart, .3)
    r = 15 if daypart != "night" else 11
    for k, (rr, mix) in enumerate(((5.0, 0.05), (3.6, 0.09), (2.5, 0.15), (1.6, 0.3))):
        add(c.create_oval(ox - r * rr, oy - r * rr, ox + r * rr, oy + r * rr,
                          fill=_mix_hex(mid, orb, mix), outline="", tags="world"))
    add(c.create_oval(ox - r, oy - r, ox + r, oy + r, fill=orb, outline="", tags="world"))
    if daypart == "night":
        for _ in range(0 if low else 70):
            sx, sy = rnd.uniform(0, self.w), rnd.uniform(0, G * 0.7)
            s = rnd.uniform(0.6, 1.7)
            add(c.create_oval(sx, sy, sx + s, sy + s, fill=_mix_hex("#8fa4c8", "#ffffff", rnd.random()),
                              outline="", tags="world"))

    # --- ranges: far (snow) -> near (forested), atmospheric perspective ------
    # (base fraction of ground, peak height, roughness, haze, snow)
    ranges = ((0.66, 0.30, 0.56, 0.58, True), (0.76, 0.20, 0.52, 0.42, True),
              (0.86, 0.11, 0.5, 0.26, False), (0.93, 0.06, 0.45, 0.14, False))
    rock = _mix_hex("#3a4758", "#5d6b80", lit)
    for depth_i, (by, amp, rough, haze, snow) in enumerate(ranges):
        base = G * by
        ridge = _lw_ridge(rnd, self.w, base - G * amp * 0.55, G * amp, rough, n=96)
        col = _mix_hex(_mix_hex(rock, "#233a28", depth_i / 3.0), horizon, haze)
        def rng_poly(dy, fill):
            pts = []
            for (x, y) in ridge:
                pts += [x, min(y, base) + dy]
            pts += [self.w + 40, G + 2, -40, G + 2]
            add(c.create_polygon(pts, fill=fill, outline="", smooth=False, tags="world"))
        if not low:
            rng_poly(0.0, _mix_hex(col, orb, 0.22 + 0.12 * lit))          # sunlit rim on the crest
        rng_poly(2.2 if not low else 0.0, col)
        if not low:                                                    # darker foot of the range
            foot = []
            for (x, y) in ridge:
                foot += [x, base - (base - min(y, base)) * 0.25 + 4]
            foot += [self.w + 40, G + 2, -40, G + 2]
            add(c.create_polygon(foot, fill=_shade(col, 0.9), outline="", smooth=True, tags="world"))
        if snow and not low:
            sn = _mix_hex("#e6edf4", horizon, 0.25 + 0.3 * depth_i)
            for i in range(2, len(ridge) - 2):
                x, y = ridge[i]
                if y < ridge[i - 1][1] and y < ridge[i + 1][1] and y < base - G * amp * 0.6:
                    add(c.create_polygon(x - 10, y + 9, x - 4, y + 5, x, y, x + 5, y + 6, x + 11, y + 10,
                                         x + 4, y + 8, x - 1, y + 11, fill=sn, outline="", tags="world"))
        if depth_i >= 2:                                   # forest texture on near hills
            tree_c = _mix_hex("#1b2e21", horizon, haze * 0.8)
            for (x, y) in ridge[::2]:
                for k in range(2):
                    tx = x + k * 4 + rnd.uniform(-2, 2)
                    th = rnd.uniform(6, 11) * (1.0 + 0.4 * (depth_i - 2))
                    ty = min(y, base) + rnd.uniform(0, 3)
                    add(c.create_polygon(tx - th * 0.35, ty + 2, tx, ty - th, tx + th * 0.35, ty + 2,
                                         fill=tree_c, outline="", tags="world"))

    # --- ground: layered bands, worn path, texture --------------------------
    g_top = _mix_hex("#3d5a32", "#1a2616", 0.6 - 0.5 * lit)
    g_deep = _mix_hex("#223319", "#0d140c", 0.6 - 0.5 * lit)
    for i in range(6):
        t = i / 5.0
        y0 = G + (self.h - G) * (t ** 1.4) - 1
        y1 = G + (self.h - G) * (((i + 1) / 5.0) ** 1.4)
        add(c.create_rectangle(0, y0, self.w, y1 + 1, fill=_mix_hex(g_top, g_deep, t), outline="",
                               tags="world"))
    path_c = _mix_hex("#6b5a44", "#2a241c", 0.55 - 0.4 * lit)
    add(c.create_polygon(-20, G + 5, self.w * 0.3, G + 3, self.w * 0.7, G + 6, self.w + 20, G + 4,
                         self.w + 20, G + 15, self.w * 0.6, G + 17, self.w * 0.25, G + 14, -20, G + 16,
                         fill=path_c, outline="", smooth=True, tags="world"))
    if not low:
        for _ in range(60):                                 # pebbles / ground texture
            x, y = rnd.uniform(0, self.w), rnd.uniform(G + 18, self.h)
            s = rnd.uniform(1.0, 2.6)
            add(c.create_oval(x, y, x + s * 1.6, y + s, fill=_mix_hex(g_deep, "#6f6a5e", rnd.uniform(0.1, 0.35)),
                              outline="", tags="world"))

    # --- vegetation in depth: far small -> near large ------------------------
    def pine(x, by, hgt, depth):
        col = _mix_hex(_mix_hex("#1f3d24", "#2e5a31", depth), horizon, (1 - depth) * 0.35)
        col = _mix_hex(col, "#0b1018", 0.45 - 0.35 * lit)
        # Trunk width scales with height for visual believability
        tw = max(2.5, hgt * 0.08 + depth * 1.2)  # Better trunk-to-height ratio
        trunk_color = _mix_hex("#3a2a1e", "#0b1018", 0.4 - 0.3 * lit)
        # Draw trunk in two parts for depth
        add(c.create_rectangle(x - tw, by - hgt * 0.25, x + tw, by, fill=trunk_color, outline="", tags="world"))
        add(c.create_rectangle(x - tw * 0.7, by - hgt * 0.25, x + tw * 0.7, by - hgt * 0.2,
                               fill=_shade(trunk_color, 1.15), outline="", tags="world"))  # sunlit top
        items = []
        for k in range(4):
            yb = by - hgt * (0.15 + 0.2 * k)
            wdt = hgt * (0.34 - 0.06 * k)
            it = add(c.create_polygon(x - wdt, yb, x, yb - hgt * 0.36, x + wdt, yb,
                                      fill=_shade(col, 0.9 + 0.06 * k), outline="", tags="world"))
            items.append(it)
            if not low:
                add(c.create_polygon(x - wdt, yb, x, yb - hgt * 0.36, x - wdt * 0.2, yb,
                                     fill=_shade(col, 1.12), outline="", tags="world"))
        return items

    def broadleaf(x, by, hgt, depth):
        col = _mix_hex(_mix_hex("#2c4f28", "#3f6b33", depth), horizon, (1 - depth) * 0.35)
        col = _mix_hex(col, "#0b1018", 0.45 - 0.35 * lit)
        # Trunk width scales with height
        tw = max(2.5, hgt * 0.09 + depth * 1.4)  # Broadleaf trees have thicker trunks
        trunk_color = _mix_hex("#4a3627", "#0b1018", 0.4 - 0.3 * lit)
        # Trunk is more tapered for broadleaf (suggests natural growth)
        add(c.create_polygon(x - tw * 0.9, by, x - tw * 0.5, by - hgt * 0.55, x + tw * 0.5, by - hgt * 0.55, x + tw * 0.9, by,
                             fill=trunk_color, outline="", tags="world"))
        add(c.create_polygon(x - tw * 0.6, by - hgt * 0.15, x - tw * 0.3, by - hgt * 0.55, x + tw * 0.3, by - hgt * 0.55, x + tw * 0.6, by - hgt * 0.15,
                             fill=_shade(trunk_color, 1.18), outline="", tags="world"))  # sunlit side
        items = []
        for k, (dx, dy, rr, sh) in enumerate(((-0.22, -0.62, 0.32, 0.86), (0.2, -0.64, 0.3, 0.9),
                                              (0.0, -0.8, 0.36, 1.0), (-0.1, -0.9, 0.24, 1.14))):
            it = add(c.create_polygon(_lw_blob(x + dx * hgt, by + dy * hgt, rr * hgt, rr * hgt * 0.85, rnd),
                                      fill=_shade(col, sh), outline="", smooth=True, tags="world"))
            items.append(it)
        return items

    _ws = globals().get("WS")
    _m = (lambda v, px: _ws.m(v)) if _ws else (lambda v, px: px)
    _wm = self.w / (_ws.px if _ws else 20.0)                      # world width in metres
    # real sizes: near trees 6.5-10 m, the mid/far rows smaller with distance;
    # spacing in metres, so a wider world is not a denser one
    for layer, (count, hmin, hmax, depth) in enumerate(((max(6, int(_wm / 3.5)), _m(2.0, 22), _m(3.2, 34), 0.35),
                                                         (max(5, int(_wm / 6.0)), _m(3.6, 40), _m(5.4, 60), 0.6),
                                                         (max(3, int(_wm / 11.0)), _m(6.5, 70), _m(10.0, 110), 0.9))):
        if low and layer == 0:
            continue
        for k in range(count):
            x = (k + rnd.uniform(0.1, 0.9)) * self.w / count
            if any(abs(x - p.x) < _m(4.0, 45) for p in self.pois) and layer == 2:
                continue
            by = G - (6 - layer * 3)
            hgt = rnd.uniform(hmin, hmax)
            items = (pine if rnd.random() < 0.55 else broadleaf)(x, by, hgt, depth)
            if layer == 2:
                for it in items:
                    hints.append((it, G, hgt, x * 0.013, 2.4))
            if layer >= 1:
                trees.append(x)
    # bushes, rocks, flowers, grass at the walk line
    for _ in range(0 if low else max(3, int(_wm / 8))):
        x = rnd.uniform(0, self.w)
        bc = _mix_hex("#2f5a2c", "#0b1018", 0.45 - 0.35 * lit)
        for k in range(3):                                         # shrubs ~0.7-0.9 m
            add(c.create_polygon(_lw_blob(x + (k - 1) * _m(0.35, 9), G - _m(0.28, 6) - (k == 1) * _m(0.15, 4),
                                          _m(0.45, 12), _m(0.36, 9), rnd),
                                 fill=_shade(bc, 0.9 + 0.1 * k), outline="", smooth=True, tags="world"))
    for _ in range(0 if low else max(4, int(_wm / 6))):
        x, y = rnd.uniform(0, self.w), G + rnd.uniform(2, 24)
        s = rnd.uniform(_m(0.12, 5), _m(0.35, 13))                 # stones 0.25-0.7 m
        rc = _mix_hex("#6d6a66", "#1a1c20", 0.45 - 0.35 * lit)
        add(c.create_polygon(_lw_blob(x, y, s, s * 0.6, rnd, 7, 0.25), fill=rc, outline="", smooth=True,
                             tags="world"))
        add(c.create_polygon(_lw_blob(x - s * 0.25, y - s * 0.2, s * 0.55, s * 0.3, rnd, 6, 0.2),
                             fill=_shade(rc, 1.25), outline="", smooth=True, tags="world"))
    fl = ("#f2c14e", "#e86a92", "#f4f1ea", "#9a7ce0")
    for _ in range(0 if low else int(_wm * 0.6)):
        x, y = rnd.uniform(0, self.w), G + rnd.uniform(-2, 30)
        fr = max(1.0, _m(0.03, 1.6))
        add(c.create_line(x, y + _m(0.08, 4), x, y, fill=_shade(g_top, 1.2), width=1, tags="world"))
        add(c.create_oval(x - fr, y - fr, x + fr, y + fr,
                          fill=_mix_hex(rnd.choice(fl), "#0b1018", 0.4 - 0.35 * lit), outline="", tags="world"))
    gc = _shade(g_top, 1.3)
    for _ in range(int(_wm * (0.7 if low else 2.2))):
        x = rnd.uniform(0, self.w)
        y = G + rnd.uniform(-1, 40)
        hgt = rnd.uniform(_m(0.08, 5), _m(0.22, 13)) * (1 + (y - G) / 60)
        lean = rnd.uniform(-3, 3)
        it = add(c.create_line(x, y, x + lean, y - hgt, fill=_mix_hex(gc, g_deep, rnd.uniform(0, 0.4)),
                               width=1, tags="world"))
        hints.append((it, y, hgt, x * 0.05, 0.9))

    self._cloud_x = getattr(self, "_cloud_x", 0.0)
    self._sway_hint = hints
    self._tree_x = trees
    self._place_pois()
    self._draw_pois()
    self.c.tag_lower("world")


World._rebuild_classic = World.rebuild
World.rebuild = _lw_rebuild

_lw_prev_classify = _cw_classify_sway


def _lw_classify(app, px):
    hints = getattr(app.world, "_sway_hint", None)
    if hints:
        px.set_sway({it: (root, hgt, ph, st) for (it, root, hgt, ph, st) in hints if it in px._reg})
        return len(hints)
    return _lw_prev_classify(app, px)


_cw_classify_sway = _lw_classify


# ============================================================================
# Fauna
# ============================================================================

# species: size, speed, flee_dist, day/night, kind, colours, cap, fear, curious
FAUNA = {
    "rabbit": dict(size=7, speed=95, flee=150, active=("morning", "afternoon", "evening"),
                   body="#9a8570", belly="#d9ccbb", cap=5, fear=0.8, curious=0.2, prey=True),
    "deer":   dict(size=17, speed=120, flee=220, active=("morning", "evening", "afternoon"),
                   body="#8a5f3c", belly="#d6bfa3", cap=3, fear=0.7, curious=0.25, prey=True),
    "fox":    dict(size=10, speed=110, flee=130, active=("evening", "night", "morning"),
                   body="#c0622a", belly="#f1e3d2", cap=2, fear=0.55, curious=0.45, predator="rabbit"),
    "wolf":   dict(size=15, speed=135, flee=90, active=("night",),
                   body="#5f6468", belly="#b9bdc0", cap=2, fear=0.2, curious=0.6, danger=True),
    "bird":   dict(size=4, speed=160, flee=110, active=("morning", "afternoon", "evening"),
                   body="#3b3f52", belly="#c8a86a", cap=8, fear=0.85, curious=0.1, flyer=True),
    "butterfly": dict(size=2.5, speed=30, flee=25, active=("morning", "afternoon"),
                      body="#f2a93b", belly="#f7e7b4", cap=6, fear=0.3, curious=0.3, flutter=True),
    "firefly": dict(size=1.2, speed=18, flee=0, active=("evening", "night"),
                    body="#e8f28a", belly="#e8f28a", cap=14, fear=0.0, curious=0.0, flutter=True, glow=True),
}


class Animal:
    _next = 1

    def __init__(self, species, x, y, rng, juvenile=False):
        self.id = Animal._next
        Animal._next += 1
        self.sp = species
        self.S = FAUNA[species]
        self.x, self.y = x, y
        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1.0 if rng.random() < 0.5 else -1.0
        self.state = "wander"
        self.hunger = rng.uniform(0.1, 0.5)
        self.energy = rng.uniform(0.6, 1.0)
        self.fear = 0.0
        self.t = rng.uniform(0, 10)
        self.goal = x
        self.scale = 0.65 if juvenile else rng.uniform(0.9, 1.1)
        self.alt = 0.0 if not (self.S.get("flyer") or self.S.get("flutter")) else rng.uniform(40, 170)
        self.seen = False
        self.dead = False
        self.age = 0.0


def _wild_threat(fa, a, d, jspeed, jane, dt, world):
    return None                                  # replaced by the individual appraisal (m51)


class Fauna:
    """Spawn -> simulate -> render, owned by the App, stepped with the world."""

    def __init__(self, seed=7):
        self.rng = _lw_random.Random(seed)
        self.animals = []
        self.spawn_t = 0.0
        self.pool = None
        self.familiar = {}          # species -> 0..1: Jane has been harmless around them
        self.events = []

    # -- population ----------------------------------------------------------
    def _capacity(self, sp, daypart, weather):
        S = FAUNA[sp]
        if daypart not in S["active"]:
            return 0
        cap = S["cap"]
        if weather in ("rain",) and sp in ("butterfly", "bird", "firefly"):
            cap //= 3
        return cap

    def _populate(self, dt, world):
        self.spawn_t -= dt
        if self.spawn_t > 0:
            return
        self.spawn_t = self.rng.uniform(2.0, 5.0)
        dp, wx = world.daypart, world.weather
        counts = {}
        for a in self.animals:
            counts[a.sp] = counts.get(a.sp, 0) + 1
        for sp in FAUNA:
            cap = self._capacity(sp, dp, wx)
            n = counts.get(sp, 0)
            if n < cap and self.rng.random() < 0.55:
                side = -1 if self.rng.random() < 0.5 else 1
                x = -30 if side < 0 else world.w + 30
                if FAUNA[sp].get("flutter"):
                    x = self.rng.uniform(40, world.w - 40)
                a = Animal(sp, x, world.ground, self.rng)
                a.goal = self.rng.uniform(world.w * 0.1, world.w * 0.9)
                self.animals.append(a)
            # breeding: two well-fed adults of a species near each other
            if 2 <= n < cap:
                same = [a for a in self.animals if a.sp == sp and a.hunger < 0.3 and a.scale > 0.8]
                if len(same) >= 2 and abs(same[0].x - same[1].x) < 60 and self.rng.random() < 0.08:
                    self.animals.append(Animal(sp, same[0].x, world.ground, self.rng, juvenile=True))

    # -- simulation -----------------------------------------------------------
    def update(self, dt, world, jane):
        self._populate(dt, world)
        jx = jane.x if jane else -1e9
        jspeed = abs(getattr(getattr(jane, "_loco", None), "vx", 0.0)) if jane else 0.0
        for a in self.animals:
            S = a.S
            a.t += dt
            a.age += dt
            a.hunger = min(1.0, a.hunger + dt * 0.004)
            night = world.daypart not in S["active"]
            d = abs(a.x - jx)
            # perception of Jane -> threat appraisal (species x familiarity x her pace)
            fam = self.familiar.get(a.sp, 0.0)
            threat = None
            try:
                threat = _wild_threat(self, a, d, jspeed, jane, dt, world)   # individual appraisal (m51)
            except Exception:
                threat = None
            if threat is None:
                threat = 0.0
                if S["flee"] > 0 and d < S["flee"] * (1.0 + jspeed / 150.0):
                    threat = S["fear"] * (1.0 - 0.7 * fam) * (1.0 + jspeed / 120.0)
            a.fear += (clamp01(threat) - a.fear) * min(1.0, dt * 3.0)
            # predators and prey
            if S.get("predator"):
                prey = [p for p in self.animals if p.sp == S["predator"] and not p.dead]
                if prey and a.hunger > 0.4:
                    tgt = min(prey, key=lambda p: abs(p.x - a.x))
                    if abs(tgt.x - a.x) < 200:
                        a.state, a.goal = "hunt", tgt.x
                        if abs(tgt.x - a.x) < 8:
                            tgt.dead = True
                            tgt._killed = True
                            a.hunger = 0.0
                            self.events.append(("animal_hunt", f"a {a.sp} caught a {tgt.sp}", 0.55, -0.1))
            if S.get("prey"):
                pred = [p for p in self.animals if (p.S.get("predator") == a.sp or p.S.get("danger"))
                        and abs(p.x - a.x) < 160]
                if pred:
                    a.fear = max(a.fear, 0.9)
                    jx_threat = pred[0].x
                else:
                    jx_threat = jx
            else:
                jx_threat = jx
            if world.weather == "rain" and not S.get("danger") and a.state in ("wander", "graze", "fly") \
                    and self.rng.random() < dt * 0.4:
                a.state = "perch" if S.get("flyer") else "sleep"     # hunker down / take cover
                a.goal = a.x
            fx = getattr(self, "fire_x", None)
            if fx is not None and abs(a.x - fx) < 170 and not S.get("flutter") and not S.get("flyer"):
                a.fear = max(a.fear, 0.5 if S.get("danger") else 0.3)
                jx_threat = fx                              # flames: back off from the fire
            # state machine
            if a.fear > 0.45 and S["flee"] > 0:
                a.state = "flee"
                a.goal = a.x + (-1 if jx_threat > a.x else 1) * getattr(a, "_flee_run", 400)
            elif getattr(a, "_psy_ok", False) and a.state != "hunt":
                pass                                             # its own mind chose (m40)
            elif S.get("danger") and d < 260 and not night:
                a.state, a.goal = "wander", a.x + (a.x - jx)       # wolves avoid daylight encounters
            elif S.get("danger") and d < 300 and night:
                a.state, a.goal = "stalk", jx + (60 if a.x > jx else -60)
            elif a.state not in ("hunt",):
                if abs(a.x - a.goal) < 6 or a.rng_due(dt):
                    r = self.rng.random()
                    if S.get("flyer"):
                        a.state = "fly" if r < 0.7 else "perch"
                    elif r < 0.45 and not S.get("flutter"):
                        a.state = "graze"
                    elif r < 0.55 and a.energy < 0.4:
                        a.state = "sleep"
                    elif r < 0.7 and S["curious"] * (0.5 + fam) > 0.35 and d < 300:
                        a.state, a.goal = "approach", jx + self.rng.uniform(-90, 90)
                    else:
                        a.state = "wander"
                    if a.state in ("wander", "fly"):
                        a.goal = self.rng.uniform(-60, world.w + 60)
            # motion
            spd = S["speed"] * a.scale
            want = 0.0
            if a.state in ("wander", "approach", "stalk"):
                want = spd * 0.35
            elif a.state == "follow":
                want = spd * min(0.8, 0.25 + abs(a.goal - a.x) / 200.0)
            elif a.state in ("play", "excited"):
                want = spd * 0.6
            elif a.state in ("sniff", "beg", "drink", "watch"):
                want = 0.0
            elif a.state in ("flee", "hunt", "fly"):
                want = spd
            elif a.state in ("graze", "sleep", "perch"):
                want = 0.0
                a.energy = min(1.0, a.energy + dt * (0.05 if a.state == "sleep" else 0.01))
                if a.state == "graze":
                    a.hunger = max(0.0, a.hunger - dt * 0.02)
            if S.get("flutter"):
                want = spd
            if a.state not in ("flee", "hunt", "fly") and not S.get("flutter"):
                want *= min(1.0, abs(a.goal - a.x) / 30.0)       # ease in: no orbiting the goal
            dirn = 1.0 if a.goal > a.x else -1.0
            a.vx += (dirn * want - a.vx) * min(1.0, dt * 4.0)
            a.x += a.vx * dt
            if abs(a.vx) > 4:
                a.facing = 1.0 if a.vx > 0 else -1.0
            a.energy = max(0.0, a.energy - dt * 0.003 * (abs(a.vx) / max(spd, 1)))
            if S.get("flyer"):
                tgt_alt = 0.0 if a.state == "perch" else (90 + 50 * _lw_math.sin(a.t * 0.5 + a.id))
                if a.state == "flee":
                    tgt_alt = 200
                a.alt += (tgt_alt - a.alt) * min(1.0, dt * 1.5)
            elif S.get("flutter"):
                a.alt = max(6.0, a.alt + _lw_math.sin(a.t * 3.1 + a.id) * 18 * dt)
            # remember Jane: time spent near her without harm builds familiarity
            if d < 220 and a.fear < 0.3:
                self.familiar[a.sp] = min(1.0, fam + dt * 0.004)
            # Jane's perception of it: first sighting per animal becomes an Event
            if not a.seen and 0 < d < 320 and jane is not None:
                a.seen = True
                doing = {"graze": "grazing", "flee": "bolting away", "hunt": "hunting",
                         "sleep": "asleep", "fly": "flying over", "perch": "perched nearby",
                         "approach": "coming closer", "stalk": "watching me from the dark"}.get(a.state, "nearby")
                sal = clamp01(0.25 + a.S["size"] / 75.0 + (0.4 if S.get("danger") else 0.0))
                val = -0.35 if S.get("danger") else (0.12 if a.state != "flee" else 0.02)
                self.events.append(("animal_seen", f"a {a.sp} {doing}", sal, val, a.sp, a.state))
        self.animals = [a for a in self.animals if not a.dead and -120 < a.x < world.w + 120]
        for a in self.animals:
            if a.state == "flee" and (a.x < -80 or a.x > world.w + 80):
                a.dead = True

    # -- render (pooled, camera-projected, colour-graded) -------------------------
    def draw(self, canvas, cam, world, grade):
        if self.pool is None:
            self.pool = _AtmoPool(canvas)
        P = self.pool
        P.begin()
        W = cam.world_to_screen
        lit = world.light()
        # PERF: cull what the camera can't see (pool hides the rest)
        vx0, _ = cam.screen_to_world(-60, 0)
        vx1, _ = cam.screen_to_world(canvas.winfo_width() + 60, 0)
        for a in self.animals:
            if not (vx0 - 80 < a.x < vx1 + 80):
                continue
            S = a.S
            s = S["size"] * a.scale
            gy = world.ground + 8 - a.alt
            f = a.facing
            body = grade.color(S["body"], gy) if grade else S["body"]
            belly = grade.color(S["belly"], gy) if grade else S["belly"]

            def poly(pts, col, smooth=True, layer="fauna"):
                out = []
                for i in range(0, len(pts), 2):
                    out.extend(W(pts[i], pts[i + 1]))
                P.put("polygon", out, layer, fill=col, outline="", smooth=smooth)

            def line(pts, col, width=1):
                out = []
                for i in range(0, len(pts), 2):
                    out.extend(W(pts[i], pts[i + 1]))
                P.put("line", out, "fauna", fill=col, width=width)

            x = a.x
            if S.get("glow"):
                g = 0.5 + 0.5 * _lw_math.sin(a.t * 4 + a.id)
                sx, sy = W(x, gy)
                r = (1.2 + 2.2 * g) * cam.zoom
                P.put("oval", [sx - r, sy - r, sx + r, sy + r], "fauna",
                      fill=_mix_hex("#304020", S["body"], 0.3 + 0.6 * g), outline="")
                continue
            if S.get("flutter"):
                flap = abs(_lw_math.sin(a.t * 14 + a.id))
                poly([x, gy, x - 2.4 * s * flap, gy - 2.2 * s, x - 2.2 * s, gy + 0.6 * s], body, False)
                poly([x, gy, x + 2.4 * s * flap, gy - 2.2 * s, x + 2.2 * s, gy + 0.6 * s], belly, False)
                continue
            if S.get("flyer"):
                if a.alt > 3:
                    flap = _lw_math.sin(a.t * 12 + a.id)
                    poly([x - 1.4 * s, gy, x + 1.4 * s, gy - 0.3 * s, x + 1.6 * s, gy + 0.4 * s, x - 1.2 * s, gy + 0.5 * s], body)
                    line([x - 0.3 * s, gy, x - 2.6 * s, gy - 2.2 * s * flap, x - 4.2 * s, gy - 1.2 * s * flap], body, 2)
                    line([x + 0.3 * s, gy, x + 2.6 * s, gy - 2.2 * s * flap, x + 4.2 * s, gy - 1.2 * s * flap], body, 2)
                else:
                    poly(_lw_blob(x, gy - s, 1.6 * s, 1.1 * s, _lw_random.Random(a.id), 7, 0.05), body)
                    poly([x + f * 1.4 * s, gy - 1.3 * s, x + f * 2.3 * s, gy - 1.0 * s, x + f * 1.4 * s, gy - 0.8 * s],
                         grade.color("#e0a53a", gy) if grade else "#e0a53a", False)
                continue
            # quadrupeds: gait phase from travel, legs alternate, body bobs
            moving = abs(a.vx) > 6
            ph = a.t * (abs(a.vx) / max(4.0, s) * 0.9 + 0.1)
            hop = a.sp == "rabbit" or a.state in ("play", "excited")
            sleep = a.state == "sleep"
            by = gy - (0.9 * s if not sleep else 0.45 * s)
            if hop and moving:
                by -= abs(_lw_math.sin(ph * 2)) * s * 0.9
            leg = 0.0 if sleep else 0.9 * s
            # shadow
            sx0, sy0 = W(x - 1.6 * s, world.ground + 7)
            sx1, sy1 = W(x + 1.6 * s, world.ground + 10)
            P.put("oval", [sx0, sy0, sx1, sy1], "fauna", fill=grade.color("#0d1210", world.ground) if grade else "#0d1210",
                  outline="")
            if leg:
                for k, off in enumerate((-0.9, 0.9)):
                    sw = _lw_math.sin(ph * 2 + k * _lw_math.pi) * 0.5 * s if moving else 0.0
                    hx = x + off * s
                    line([hx, by + 0.3 * s, hx + sw * f, gy], _shade(body, 0.8), max(1, int(s * 0.22)))
            poly(_lw_blob(x, by, 1.5 * s, 0.75 * s, _lw_random.Random(a.id), 10, 0.04), body)
            poly(_lw_blob(x - 0.1 * s * f, by + 0.3 * s, 1.1 * s, 0.35 * s, _lw_random.Random(a.id + 1), 8, 0.05), belly)
            graze = a.state in ("graze", "sniff", "drink")
            hx, hy = x + f * 1.5 * s, by - (0.6 * s if not graze else -0.5 * s)
            poly(_lw_blob(hx, hy, 0.55 * s, 0.45 * s, _lw_random.Random(a.id + 2), 8, 0.05), body)
            if a.sp == "rabbit":
                for e in (-0.15, 0.15):
                    poly([hx + e * s, hy - 0.3 * s, hx + (e - 0.05 * f) * s, hy - 1.5 * s,
                          hx + (e + 0.2 * f) * s, hy - 0.3 * s], body, True)
            elif a.sp in ("fox", "wolf"):
                poly([hx - 0.2 * s * f, hy - 0.3 * s, hx, hy - 0.95 * s, hx + 0.25 * s * f, hy - 0.35 * s], body, False)
                line([x - f * 1.4 * s, by, x - f * 2.4 * s, by - 0.2 * s, x - f * 2.9 * s, by + 0.2 * s],
                     body if a.sp == "wolf" else _mix_hex(body, "#f4efe8", 0.4), max(2, int(s * 0.35)))
            elif a.sp == "dog":
                poly([hx - 0.1 * s * f, hy - 0.25 * s, hx - 0.35 * s * f, hy + 0.35 * s,
                      hx - 0.05 * s * f, hy + 0.2 * s], _shade(body, 0.8), True)       # floppy ear
                wag = _lw_math.sin(a.t * (18 if a.state in ("excited", "play", "follow") else 5)) * 0.5
                line([x - f * 1.4 * s, by - 0.1 * s, x - f * 2.2 * s, by - (0.7 + wag * 0.4) * s,
                      x - f * (2.4 + wag) * s, by - 1.0 * s], body, max(2, int(s * 0.25)))
            elif a.sp == "deer":
                line([hx, hy - 0.4 * s, hx - 0.2 * s * f, hy - 1.3 * s, hx + 0.1 * s * f, hy - 1.7 * s],
                     _shade(body, 0.7), 1)
            eye = W(hx + 0.25 * s * f, hy - 0.1 * s)
            er = max(0.6, 0.12 * s * cam.zoom)
            P.put("oval", [eye[0] - er, eye[1] - er, eye[0] + er, eye[1] + er], "fauna",
                  fill="#f4e08a" if (a.sp == "wolf" and lit < 0.5) else "#111111", outline="")
        P.end()


# -- App integration: the world owns the fauna, Jane perceives it ---------------
_lw_prev_update_world = App._update_world


def _lw_update_world(self, dt):
    _lw_prev_update_world(self, dt)
    fa = getattr(self, "fauna", None)
    if fa is None:
        fa = self.fauna = Fauna(seed=getattr(self.brain.personality, "body_seed", 7))
        mem = getattr(self.brain.mind, "fauna_memory", None)
        if isinstance(mem, dict):
            fa.familiar.update(mem)
    fa.update(dt, self.world, self.creature)
    cam = getattr(self, "_camera", None)
    if cam is not None:
        fa.draw(self.stage, cam, self.world, getattr(self, "_scene_grade", None))
        try:
            self.stage.tag_raise("fauna")
        except Exception:
            pass
    mind = getattr(self.brain, "mind", None)
    if mind is not None:
        mind.fauna_memory = dict(fa.familiar)
    for ev in fa.events:
        kind, text, sal, val = ev[:4]
        self.brain.perceive(Event(kind, text, salience=sal, valence=val))
        if kind == "animal_seen":
            sp, state = ev[4], ev[5]
            try:
                self.brain.knowledge.see("animal", sp, valence=val, note=text)
            except Exception:
                pass
            if FAUNA[sp].get("danger") and mind is not None:
                mind.risk.recent_lightning = max(mind.risk.recent_lightning, 0.8)   # threat pulse
            elif mind is not None and state in ("graze", "approach", "perch", "sleep"):
                # a calm animal pulls a curious Jane toward it
                if self.brain.emotion.curiosity > 0.55 and self.creature.behavior in ("idle", "curious"):
                    near = [a for a in fa.animals if a.sp == sp]
                    if near:
                        self.creature.set_target(near[0].x + (-50 if near[0].x > self.creature.x else 50),
                                                 self.creature.y)
    fa.events = []


def _animal_rng_due(self, dt):
    return _lw_random.random() < dt * 0.25


Animal.rng_due = _animal_rng_due
App._update_world = _lw_update_world

# persist familiarity with species alongside the rest of the mind
_lw_prev_to_dict = LivingMind.to_dict
_lw_prev_from_dict = LivingMind.from_dict


def _lw_to_dict(self):
    d = _lw_prev_to_dict(self)
    d["fauna"] = dict(getattr(self, "fauna_memory", {}) or {})
    return d


def _lw_from_dict(self, d):
    _lw_prev_from_dict(self, d)
    if isinstance(d, dict) and isinstance(d.get("fauna"), dict):
        self.fauna_memory = {k: clamp01(float(v)) for k, v in d["fauna"].items()}


LivingMind.to_dict = _lw_to_dict
LivingMind.from_dict = _lw_from_dict



# ============================================================================
# Survival: campfire, gathering, cooking, warmth - driven by Jane's real needs
# ============================================================================

class Campfire:
    def __init__(self, x):
        self.x = x
        self.fuel = 0.85
        self.lit = True
        self.t = 0.0
        self.intensity = 1.0
        self.smoke = [i / 8.0 for i in range(8)]       # puff ages 0..1 (staggered)
        self.pool = None

    def update(self, dt, wx):
        self.t += dt
        rain = wx.get("precip", 0.0)
        if self.lit:
            self.fuel -= dt / 240.0 * (1.0 + 2.5 * rain)
            if self.fuel <= 0.0:
                self.lit = False
        want = (min(1.0, self.fuel * 1.6) * (1.0 - 0.55 * rain)) if self.lit else 0.0
        self.intensity += (want - self.intensity) * min(1.0, dt * 2.0)
        rate = 0.35 if self.lit else 0.2
        self.smoke = [(a + dt * rate) % 1.0 for a in self.smoke]

    def draw(self, canvas, cam, world, grade, wx, k=1.0):
        if self.pool is None:
            self.pool = _AtmoPool(canvas)
        P = self.pool
        P.begin()
        W = cam.world_to_screen
        G = world.ground
        x = self.x
        z = cam.zoom
        gc = (lambda col, y: grade.color(col, y)) if grade else (lambda col, y: col)
        I = self.intensity
        wind = wx.get("wind", 0.2) * wx.get("wind_dir", 1.0) if isinstance(wx, dict) else 0.2

        def S(px_, py_):                      # scale about the fire base (x, G)
            return x + (px_ - x) * k, G + (py_ - G) * k

        def poly(pts, col, smooth=True):
            out = []
            for i in range(0, len(pts), 2):
                out.extend(W(*S(pts[i], pts[i + 1])))
            P.put("polygon", out, "fauna", fill=col, outline="", smooth=smooth)

        def oval(cx, cy, rx, ry, col):
            cx, cy = S(cx, cy)
            rx, ry = rx * k, ry * k
            (a0, b0), (a1, b1) = W(cx - rx, cy - ry), W(cx + rx, cy + ry)
            P.put("oval", [a0, b0, a1, b1], "fauna", fill=col, outline="")
        # ground light pool + halo (solid colours mixed toward firelight)
        warm = "#ff9a3c"
        base = gc("#2c3a24", G)
        if I > 0.02:
            oval(x, G + 5, 46 * I + 14, 5 * I + 2, _mix_hex(base, warm, 0.14 * I))
            oval(x, G + 5, 22 * I + 8, 3 * I + 1.5, _mix_hex(base, warm, 0.3 * I))
        # stones + logs
        for kk in range(7):
            a_ = _lw_math.pi * (kk / 6.0)
            sx = x + _lw_math.cos(a_) * 9
            oval(sx, G + 3 + _lw_math.sin(a_) * 1.2, 2.4, 1.7, gc("#6c6a66", G))
        poly([x - 8, G + 2.5, x + 7, G - 1, x + 8, G + 1, x - 7, G + 4.5], gc("#4a3222", G), False)
        poly([x + 8, G + 2.5, x - 7, G - 1, x - 8, G + 1, x + 7, G + 4.5], gc("#5a3c28", G), False)
        # flames: flickering tongues leaning with the wind
        if I > 0.03:
            for kk, (col, wk, hk) in enumerate((("#d9431c", 1.0, 1.0), ("#f5892a", 0.72, 0.8),
                                                ("#ffd766", 0.42, 0.55))):
                for j in range(3):
                    ph = self.t * (7 + j * 2.3) + j * 1.7 + kk
                    hgt = (22 + 7 * _lw_math.sin(ph)) * hk * (0.35 + 0.65 * I)
                    bw = (5.5 - j) * wk * (0.6 + 0.4 * I)
                    bx = x + (j - 1) * 3.4 * wk
                    tip = bx + wind * 8 * hk + 2.2 * _lw_math.sin(ph * 1.3)
                    poly([bx - bw, G + 1, bx - bw * 0.45, G - hgt * 0.5, tip, G - hgt,
                          bx + bw * 0.45, G - hgt * 0.45, bx + bw, G + 1], col)
            for kk in range(4):                                     # embers
                ea = (self.t * 0.6 + kk * 0.25) % 1.0
                ex = x + _lw_math.sin(kk * 2.1 + self.t) * 8 + wind * 30 * ea
                ey = G - 10 - ea * 50
                oval(ex, ey, 0.9, 0.9, _mix_hex("#ffb347", gc("#1a2030", ey), ea))
        # smoke: rises, drifts downwind, spreads and fades into the sky
        if I > 0.02 or self.fuel > -0.2:
            for age in self.smoke[:6]:
                sy = G - 26 - age * 70
                sx = x + wind * 40 * age + _lw_math.sin(age * 9 + self.t) * 2.5
                r = 2.2 + age * 7
                sky = gc("#5a6a80", sy)
                oval(sx, sy, r, r * 0.75, _mix_hex("#9a9aa0", sky, 0.55 + 0.42 * age))
        P.end()


class Survival:
    """Inventory + a small needs-driven planner for Jane. It only sets
    movement targets and biases her decision utilities - her brain still
    decides; the planner gives those decisions something real to do."""

    def __init__(self):
        self.inv = {"wood": 0, "berries": 0, "bow": 0, "meat": 0}
        self.arrows = []                # in-flight / stuck projectiles
        self.quarry = None
        self.aim = 0.0                  # 0..1 raise weight
        self.draw_t = 0.0               # 0..1 string draw
        self.gear_pool = None
        self.fire = None
        self.task = None
        self.timer = 0.0
        self.plan_t = 0.0
        self.bias = {}

    def _emit(self, app, text, val, sal=0.5):
        app.brain.perceive(Event("survival", text, salience=sal, valence=val))

    def update(self, app, dt):
        world, cr, b = app.world, app.creature, app.brain
        mind = b.mind
        wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
        f = self.fire
        if f is not None:
            f.update(dt, wx)
            if f.lit and wx.get("precip", 0.0) > 0.75 and random.random() < dt * 0.03:
                f.lit = False
                self._emit(app, "the rain drowned my campfire", -0.3)
            if not f.lit and f.intensity < 0.02 and f.fuel <= 0.0:
                self.fire = f = None                     # burnt out: a new fire can be built
        heat = 0.0
        if f is not None and f.lit:
            d = abs(cr.x - f.x)
            heat = 12.0 * f.intensity * max(0.0, 1.0 - d / 170.0)
            if self.inv["wood"] and f.fuel < 0.35 and d < 60:
                self.inv["wood"] -= 1
                f.fuel = min(1.0, f.fuel + 0.4)
        mind.comfort.fire_heat = heat
        if hasattr(app, "fauna"):
            app.fauna.fire_x = f.x if (f is not None and f.lit) else None
        # firelight on Jane: less night grade, the nearer she is
        sg = getattr(app, "_scene_grade", None)
        if sg is not None and heat > 0.5:
            fg = self.__dict__.setdefault("_fg", SceneGrade(sg.ground, sg.h))
            k = heat / 12.0
            fg.ground, fg.h = sg.ground, sg.h
            fg.set(dark=sg.dark * (1.0 - 0.65 * k), fog=sg.fog, warm=sg.warm, flash=sg.flash, light=sg.light)
            cr.__dict__["_scene_grade"] = fg
        # --- planner ------------------------------------------------------
        self.plan_t -= dt
        if self.plan_t <= 0.0:
            self.plan_t = 0.5
            self._plan(app, wx)
        self._act(app, dt)

    def _plan(self, app, wx):
        world, cr, g = app.world, app.creature, app.brain.goals
        comfort = app.brain.mind.comfort
        dark = world.daypart in ("evening", "night")
        f = self.fire
        lit = f is not None and f.lit
        food = world.poi("food")
        task = None
        if (dark or comfort.cold > 0.3) and not lit and wx.get("precip", 0.0) < 0.7:
            if self.inv["wood"] < 3:
                trees = getattr(world, "_tree_x", None) or [world.w * 0.3]
                task = ("wood", min(trees, key=lambda t: abs(t - cr.x)))
            else:
                sh = world.poi("shelter")
                site = (sh.x + 80) if sh is not None else cr.x
                task = ("build", clamp(site, 60, world.w - 60))
        elif lit and g.hunger > 0.3 and (self.inv["berries"] > 0 or self.inv["meat"] > 0):
            task = ("cook", f.x + (1 if cr.x >= f.x else -1) * 2.4 * cr._Hb())
        elif g.hunger > 0.3 and self.inv["berries"] > 0 and not lit:
            task = ("eat", cr.x)                            # no fire: eat them raw
        elif (app.settings.data.get("hunting_enabled", False) and g.hunger > 0.35
              and self.inv["berries"] == 0 and self.inv["meat"] == 0
              and not (food is not None and food.available())):
            if not self.inv["bow"]:
                if self.inv["wood"] < 2:
                    trees = getattr(world, "_tree_x", None) or [world.w * 0.3]
                    task = ("wood", min(trees, key=lambda t: abs(t - cr.x)))
                else:
                    task = ("craft", cr.x)
            else:
                fa = getattr(app, "fauna", None)
                prey = [a for a in (fa.animals if fa else []) if a.sp in ("rabbit", "deer") and not a.dead]
                if prey:
                    q = min(prey, key=lambda a: abs(a.x - cr.x))
                    self.quarry = q
                    stand = q.x - (1 if q.x >= cr.x else -1) * 7.0 * cr._Hb()
                    task = ("hunt", clamp(stand, 40, world.w - 40))
        elif g.hunger > 0.25 and self.inv["berries"] < 3 and food is not None and food.available():
            task = ("berries", food.x)
        elif self.inv["meat"] > 0 and not lit and wx.get("precip", 0.0) < 0.7:
            if self.inv["wood"] < 3:
                trees = getattr(world, "_tree_x", None) or [world.w * 0.3]
                task = ("wood", min(trees, key=lambda t: abs(t - cr.x)))
            else:
                sh = world.poi("shelter")
                task = ("build", clamp((sh.x + 80) if sh is not None else cr.x, 60, world.w - 60))
        elif lit and dark:
            task = ("warm", f.x + (1 if cr.x >= f.x else -1) * 3.4 * cr._Hb())
        if task != self.task and not (self.task and self.task[0] == "hunt" and task and task[0] == "hunt"):
            self.task, self.timer = task, 0.0
        # bias her decisions: travel when a task is far, rest by the fire
        self.bias = {}
        if task:
            far = abs(cr.x - task[1]) > 30              # hysteresis vs the 18px arrival
            if far:
                self.bias["move"] = 0.35
            elif task[0] in ("warm", "cook"):
                self.bias["rest"] = 0.9                 # settle down (sits) by the fire
                self.bias["move"] = -0.6                # ...and stay there

    def _hunt(self, app, dt):
        """Stalk into range, raise the bow, draw, release - the arrow is a
        real projectile (gravity, collision) handled in _arrows()."""
        cr, q = app.creature, self.quarry
        H = cr._Hb()
        if q is None or q.dead or q.state == "flee" and abs(q.x - cr.x) > 12 * H:
            self.task, self.quarry = None, None
            self.aim = 0.0
            return
        d = abs(q.x - cr.x)
        if d > 9.0 * H:
            cr.set_target(q.x - (1 if q.x >= cr.x else -1) * 7.0 * H, cr.y)
            self.aim = max(0.0, self.aim - dt * 3.0)
            self.draw_t = 0.0
            return
        cr.set_target(cr.x, cr.y)                           # plant the feet, face the quarry
        cr._loco.facing = 1.0 if q.x >= cr.x else -1.0
        self.aim = min(1.0, self.aim + dt * 2.5)
        if self.aim > 0.95:
            self.draw_t = min(1.0, self.draw_t + dt / 1.1)
        if self.draw_t >= 1.0:
            self._release(app, q)
            self.draw_t = 0.0
            self.timer = -1.5                               # recover before the next shot

    def _release(self, app, q):
        cr = app.creature
        pose = cr.__dict__.get("_last_pose")
        if not pose:
            return
        near = "R" if cr._loco.facing >= 0 else "L"
        hx, hy = pose[5][near][2]
        H = cr._H()
        ty = app.world.ground + 8 - q.alt - q.S["size"] * q.scale * 0.9
        # aim error: distance, a moving target, and her confidence
        conf = app.brain.personality.traits.get("confidence", 0.6)
        spread = (0.02 + abs(q.vx) / 1800.0 + abs(q.x - hx) / 9000.0) * (1.3 - 0.6 * conf)
        rnd = _lw_random.gauss(0.0, 1.0) * spread
        vx = (650.0 if q.x >= hx else -650.0)
        t = max(0.05, abs((q.x + q.vx * 0.25) - hx) / abs(vx))
        g = 900.0
        vy = (ty - hy - 0.5 * g * t * t) / t
        ang = _lw_math.atan2(vy, vx) + rnd
        sp = _lw_math.hypot(vx, vy)
        self.arrows.append({"x": hx, "y": hy, "vx": _lw_math.cos(ang) * sp, "vy": _lw_math.sin(ang) * sp,
                            "stuck": 0.0, "q": q, "hit": False, "len": 1.1 * H})
        cr.speaking = max(cr.speaking, 0.2)

    def _arrows(self, app, dt):
        fa = getattr(app, "fauna", None)
        G = app.world.ground
        keep = []
        for ar in self.arrows:
            if ar["stuck"] > 0:
                ar["stuck"] += dt
                if ar["stuck"] < 6.0:
                    keep.append(ar)
                continue
            ar["vy"] += 900.0 * dt
            ar["x"] += ar["vx"] * dt
            ar["y"] += ar["vy"] * dt
            q = ar["q"]
            if q is not None and not q.dead:
                qy = G + 8 - q.alt - q.S["size"] * q.scale * 0.9
                if abs(ar["x"] - q.x) < q.S["size"] * q.scale * 1.6 and abs(ar["y"] - qy) < q.S["size"] * q.scale * 1.1:
                    q.dead = True                           # taken - no gore, it is simply caught
                    q._killed = True
                    self.inv["meat"] += 1
                    self.task, self.quarry, self.aim = None, None, 0.0
                    if fa:
                        fa.familiar[q.sp] = max(0.0, fa.familiar.get(q.sp, 0.0) - 0.4)   # they remember
                        for o in fa.animals:
                            if abs(o.x - q.x) < 260:
                                o.fear = 1.0                # everything nearby bolts
                    self._emit(app, f"brought down a {q.sp} with my bow", 0.2, 0.65)
                    continue
            if ar["y"] >= G + 6:                            # hit the ground: stick in it
                ar["y"] = G + 6
                ar["stuck"] = 1e-3
                if not ar["hit"] and q is not None and not q.dead:
                    q.fear = 1.0
                    self._emit(app, f"missed the {q.sp} - it bolted", -0.15, 0.45)
                keep.append(ar)
                continue
            if -200 < ar["x"] < app.world.w + 200:
                keep.append(ar)
        self.arrows = keep

    def _act(self, app, dt):
        self._arrows(app, dt)
        if not self.task:
            self.aim = max(0.0, self.aim - dt * 3.0)
            return
        cr, b = app.creature, app.brain
        kind, tx = self.task
        if kind == "hunt":
            if self.timer < 0:
                self.timer += dt
                self.aim = max(0.0, self.aim - dt * 2.0)
                return
            self._hunt(app, dt)
            return
        self.aim = max(0.0, self.aim - dt * 3.0)
        if abs(cr.x - tx) > 18:
            cr.set_target(tx, cr.y)
            return
        self.timer += dt
        if kind == "wood" and self.timer > 2.6:
            self.inv["wood"] += 1
            self.timer = 0.0
            if self.inv["wood"] == 1:
                self._emit(app, "gathered firewood under the trees", 0.1, 0.4)
        elif kind == "berries" and self.timer > 1.5:
            food = app.world.poi("food")
            if food is not None and food.available():
                self.inv["berries"] += 1
                if self.inv["berries"] >= 3:
                    food.deplete()
                    self._emit(app, "gathered berries from the thicket", 0.2, 0.4)
            self.timer = 0.0
        elif kind == "build" and self.timer > 3.0:
            self.inv["wood"] -= 3
            self.fire = Campfire(tx)
            self.task = None
            self._emit(app, "built and lit a campfire", 0.45, 0.65)
        elif kind == "cook" and self.timer > 3.0:
            self.timer = 0.0
            if self.inv["meat"] > 0:
                self.inv["meat"] -= 1
                b.goals.satisfy("hunger", 0.75, "a proper meal cooked over the fire")
                self._emit(app, "cooked what I hunted over the fire and ate well", 0.4, 0.6)
            elif self.inv["berries"] > 0:
                self.inv["berries"] -= 1
                b.goals.satisfy("hunger", 0.45, "ate berries cooked over the fire")
                self._emit(app, "ate berries cooked over the fire", 0.35, 0.55)
        elif kind == "eat" and self.timer > 1.5:
            self.timer = 0.0
            if self.inv.get("berries", 0) <= 0:          # nothing left to eat
                self.task = None
                return
            self.inv["berries"] -= 1
            b.goals.satisfy("hunger", 0.3, "ate a handful of raw berries")
            if self.inv["berries"] == 0:
                self._emit(app, "ate the berries I gathered", 0.2, 0.4)
        elif kind == "craft" and self.timer > 3.0:
            self.inv["wood"] -= 2
            self.inv["bow"] = 1
            self.task = None
            self._emit(app, "made a reed bow from gathered wood", 0.3, 0.6)

    def draw(self, app):
        f = self.fire
        cam = getattr(app, "_camera", None)
        if f is not None and cam is not None:
            wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
            # campfire sized to the world's people: flames ~knee-high on Jane
            f.draw(app.stage, cam, app.world, getattr(app, "_scene_grade", None), wx,
                   k=app.creature._H() / 12.0)


_sv_prev_comfort = ThermalComfort.update


def _sv_comfort_update(self, dt, wx, sheltered, moving):
    heat = getattr(self, "fire_heat", 0.0)
    if heat > 0.05:
        wx = dict(wx, temp=wx.get("temp", 20.0) + heat)
        self.wet = max(0.0, self.wet - dt * 0.004 * heat)            # drying by the fire
    return _sv_prev_comfort(self, dt, wx, sheltered, moving)


ThermalComfort.update = _sv_comfort_update

_sv_prev_adjust = LivingMind.adjust_utilities


def _sv_adjust(self, scores):
    _sv_prev_adjust(self, scores)
    for k, v in (getattr(self, "survival_bias", None) or {}).items():
        if k in scores:
            scores[k] += v


LivingMind.adjust_utilities = _sv_adjust

_sv_prev_update_world = App._update_world


def _sv_update_world(self, dt):
    _sv_prev_update_world(self, dt)
    sv = getattr(self, "survival", None)
    if sv is None:
        sv = self.survival = Survival()
    sv.update(self, dt)
    self.brain.mind.survival_bias = sv.bias
    cr = self.creature
    q = sv.quarry
    if sv.task and sv.task[0] == "hunt" and q is not None and isinstance(getattr(cr, "_body", None), dict):
        if abs(q.x - cr.x) < 14 * cr._H():
            cr._body["pace"] = cr._body.get("pace", 1.0) * 0.45      # stalk
    if sv.aim > 0.01 and q is not None:
        cr._aim = (q.x, self.world.ground + 8 - q.alt - q.S["size"] * q.scale, sv.aim, sv.draw_t)
    else:
        cr._aim = None
    sv.draw(self)
    try:
        self.stage.tag_raise("fauna")
    except Exception:
        pass


App._update_world = _sv_update_world


# the app's own world step (rest -> shelter, idle wander) runs after the
# survival update and used to overwrite its target: re-apply it afterwards
_sv_prev_world_step = App._world_step


def _sv_world_step(self, decision):
    _sv_prev_world_step(self, decision)
    sv = getattr(self, "survival", None)
    if sv is not None and sv.task and sv.task[0] != "hunt":     # the hunt steers itself
        tx = sv.task[1]
        if abs(self.creature.x - tx) > 18:
            self.creature.set_target(tx, self.creature.y)
        else:
            self.creature.set_target(self.creature.x, self.creature.y)   # stay put here


App._world_step = _sv_world_step



# -- bow + arrows: drawn ABOVE the creature (held in her hands) ---------------
def _sv_draw_gear(self):
    sv = getattr(self, "survival", None)
    cam = getattr(self, "_camera", None)
    if sv is None or cam is None:
        return
    if sv.gear_pool is None:
        sv.gear_pool = _AtmoPool(self.stage)
    P = sv.gear_pool
    P.begin()
    W = cam.world_to_screen
    cr = self.creature
    grade = cr.__dict__.get("_scene_grade")
    gc = (lambda col, y: grade.color(col, y)) if grade else (lambda col, y: col)
    H = cr._H()
    pose = cr.__dict__.get("_last_pose")
    if sv.inv.get("bow") and pose and sv.aim > 0.05:
        near = "R" if cr._loco.facing >= 0 else "L"
        far_ = "L" if near == "R" else "R"
        fx, fy = pose[5][near][2]
        rx, ry = pose[5][far_][2]
        dx, dy = fx - rx, fy - ry
        n = _lw_math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        px_, py_ = -uy, ux
        L = 0.8 * H
        bend = 0.18 * H + 0.28 * H * sv.draw_t
        t1 = (fx + px_ * L - ux * bend * 0.4, fy + py_ * L - uy * bend * 0.4)
        t2 = (fx - px_ * L - ux * bend * 0.4, fy - py_ * L - uy * bend * 0.4)
        mid = (fx + ux * 0.08 * H, fy + uy * 0.08 * H)
        wood = gc("#7a5230", fy)
        for tip in (t1, t2):
            pts = [*W(*tip), *W((tip[0] + mid[0]) / 2 + ux * bend * 0.5, (tip[1] + mid[1]) / 2 + uy * bend * 0.5), *W(*mid)]
            P.put("line", pts, "gear", fill=wood, width=max(2, int(0.1 * H * cam.zoom)), smooth=True)
        nock = (rx, ry) if sv.draw_t > 0.05 else (fx - ux * 0.25 * H, fy - uy * 0.25 * H)
        P.put("line", [*W(*t1), *W(*nock), *W(*t2)], "gear", fill=gc("#e8e0d0", fy), width=1)
        if sv.draw_t > 0.02:                                      # nocked arrow along the aim line
            P.put("line", [*W(*nock), *W(nock[0] + ux * 1.15 * H, nock[1] + uy * 1.15 * H)], "gear",
                  fill=gc("#c9b48a", fy), width=2)
    for ar in sv.arrows:
        v = _lw_math.hypot(ar["vx"], ar["vy"]) or 1.0
        ux, uy = ar["vx"] / v, ar["vy"] / v
        L = ar["len"]
        tail = (ar["x"] - ux * L, ar["y"] - uy * L)
        P.put("line", [*W(*tail), *W(ar["x"], ar["y"])], "gear", fill=gc("#c9b48a", ar["y"]), width=2)
        P.put("line", [*W(*tail), *W(tail[0] + ux * 0.2 * H + uy * 0.1 * H, tail[1] + uy * 0.2 * H - ux * 0.1 * H)],
              "gear", fill=gc("#e25a6a", ar["y"]), width=2)                     # fletching
    P.end()
    try:
        self.stage.tag_raise("gear")
    except Exception:
        pass


App._sv_draw_gear = _sv_draw_gear
_sv_prev_cr_draw = Creature.draw


def _sv_creature_draw(self):
    _sv_prev_cr_draw(self)
    app = self.__dict__.get("_app_ref")
    if app is not None:
        app._sv_draw_gear()


Creature.draw = _sv_creature_draw
_sv_prev_update_world2 = App._update_world


def _sv_update_world2(self, dt):
    _sv_prev_update_world2(self, dt)
    self.creature.__dict__["_app_ref"] = self


App._update_world = _sv_update_world2

# optional hunting: a toggle on the MIND tab (off by default)
_sv_prev_build_mind = App._build_mind_tab


def _sv_build_mind(self):
    _sv_prev_build_mind(self)
    try:
        tab = self.tabs.nametowidget(self.tabs.tabs()[-1])
        var = tk.BooleanVar(value=bool(self.settings.data.get("hunting_enabled", False)))

        def toggle():
            self.settings.data["hunting_enabled"] = bool(var.get())
            self.settings.save()
        cb = tk.Checkbutton(tab, text="Allow hunting (optional): Jane may craft a bow and hunt when hungry",
                            variable=var, command=toggle, bg=C_BG, fg=C_TEXT, selectcolor=C_PANEL_2,
                            activebackground=C_BG, activeforeground=C_TEXT, font=FONT_UI_SMALL,
                            anchor="w", highlightthickness=0)
        if tab.grid_slaves():
            cols, rows = tab.grid_size()
            cb.grid(row=rows, column=0, columnspan=max(1, cols), sticky="w", padx=10, pady=(4, 8))
        else:
            cb.pack(fill="x", padx=10, pady=(4, 8))
        self._hunt_var = var
    except Exception:
        traceback.print_exc()


App._build_mind_tab = _sv_build_mind
