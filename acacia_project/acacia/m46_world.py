# ============================================================================
# [NEW] PHYSICAL CIVILISATION  (regions, settlements, bodies, journeys)
# ============================================================================
#
# The society (M46) stops being off-screen only. The world is a chain of
# regions built from its live state:
#     ... <settlement> - road - VALLEY - road - <settlement> - road - ...
# Each settlement is drawn from what the simulation says about it now:
# houses for its households (charred after raids, ruins once abandoned), a
# market, tavern, shrine with the graves of its actual dead, hall, workshop,
# guard towers, well and fields. Its real NPCs are physical bodies with a
# home, a workplace, a daily schedule by role and hour, clothes and gear by
# class and wealth, and visible grief, injury and childhood; a crowd scales
# with the population.
#
# While Jane is present, the moral engine's acts in that settlement are
# ENACTED: the people walk to each other and do it, and the outcome uses
# physical facts - a theft is caught only if a guard is actually near. Jane
# witnesses what happens within sight, and can act herself (share food with
# the hungry or injured, trade at the market with coins).
#
# Jane travels on her own reasons: to trade, to see someone she knows, out
# of curiosity about a place she heard of, and home again at dusk. Valley
# life doesn't stop: its animals sleep (paused and advanced on return),
# her fire and home stay where they are.
#
# LOD / performance: bodies exist only in the current region; others are
# the abstract society. Bodies are culled off-camera, simplified when small,
# their schedules decided at ~4 Hz (staggered), neighbour queries through a
# spatial hash; pooled items skip unchanged coordinates.

import random as _rw_random
import math as _rw_math
import time as _rw_time

_RW_ALLOWED = {"settlement": {"bird", "dog", "butterfly"},
               "road": {"rabbit", "deer", "bird", "butterfly", "fox", "firefly", "wolf"}}


# ---- region map ------------------------------------------------------------------------
def _rw_regions(soc):
    west = sorted((s for s in soc.sets.values() if s.side < 0), key=lambda s: s.dist)
    east = sorted((s for s in soc.sets.values() if s.side > 0), key=lambda s: s.dist)
    reg = []
    for s in reversed(west):
        reg += [("settlement", s.name), ("road", s.name)]
    reg.append(("valley", "valley"))
    for s in east:
        reg += [("road", s.name), ("settlement", s.name)]
    return reg


def _rw_here(app):
    return getattr(app, "region", ("valley", "valley"))


def _rw_valley(app):
    return _rw_here(app)[0] == "valley"


# ---- region-aware world building ----------------------------------------------------------
_rw_prev_rebuild = World.rebuild


_RW_WIDTH = {"valley": 1.0, "road": 1.6, "settlement": 2.4}     # in viewport widths


def _rw_rebuild(self, w, h, ground, daypart, weather, detail="high"):
    kind = getattr(self, "_region_kind", "valley")
    _ws = globals().get("WS")
    width = int(max(w, _SC_REGION_M.get(kind, 48.0) * _ws.px)) if _ws else int(w * _RW_WIDTH.get(kind, 1.0))
    _rw_prev_rebuild(self, width, h, ground, daypart, weather, detail)
    if kind == "settlement":
        _rw_build_settlement(self)
    elif kind == "road":
        self.pois = [p for p in self.pois if p.kind == "water"]
    self._built_for = (kind, getattr(self, "_region_name", "valley"))   # what was ACTUALLY built
    self.c.tag_lower("world")


World.rebuild = _rw_rebuild

_rw_prev_draw_pois = World._draw_pois


def _rw_draw_pois(self):
    if getattr(self, "_region_kind", "valley") == "settlement":
        return                                          # settlements draw their own buildings
    return _rw_prev_draw_pois(self)


World._draw_pois = _rw_draw_pois


def _rw_build_settlement(self):
    soc = getattr(self, "_soc", None)
    s = soc.sets.get(self._region_name) if soc else None
    c, G, W = self.c, self.ground, self.w
    _ws = globals().get("WS")
    H = _ws.m(1.0) if _ws else getattr(self, "_H_hint", 30.0)   # 1 m: houses 4.8 m wide, doors 2.2 m
    lit = self.light()
    night = self.daypart in ("evening", "night")
    rnd = _rw_random.Random(hash(self._region_name) & 0xffff)
    dead = s is None or not s.alive
    damage = getattr(s, "damage", 0.0) if s else 1.0
    wall_c = _mix_hex(rnd.choice(("#8a6a4a", "#9a8a6a", "#7a5a42", "#a08870")), "#0b1018", 0.45 - 0.35 * lit)
    roof_c = _mix_hex(rnd.choice(("#6a3a2a", "#5a4a3a", "#7a5a3a", "#4a4a52")), "#0b1018", 0.45 - 0.35 * lit)
    burnt = _mix_hex("#2a2320", "#0b1018", 0.3)
    add = self._add
    P = {}

    def rect(x0, y0, x1, y1, col):
        return add(c.create_polygon(x0, y0, x1, y0, x1, y1, x0, y1, fill=col, outline="", tags="world"))

    def house(x, wdt, hgt, ruined, burned, sign=None):
        col = burnt if burned else wall_c
        if ruined:
            add(c.create_polygon(x - wdt / 2, G, x - wdt / 2, G - hgt * 0.6, x - wdt * 0.1, G - hgt * 0.35,
                                 x + wdt * 0.2, G - hgt * 0.55, x + wdt / 2, G - hgt * 0.2, x + wdt / 2, G,
                                 fill=_mix_hex(col, "#3a3a3a", 0.4), outline="", tags="world"))
            return
        rect(x - wdt / 2, G - hgt, x + wdt / 2, G, col)
        for k in range(1, 4):
            rect(x - wdt / 2, G - hgt * k / 4, x + wdt / 2, G - hgt * k / 4 + 1.5, _shade(col, 0.8))
        rr = roof_c if not burned else burnt
        pts = [x - wdt / 2 - 0.4 * H, G - hgt, x, G - hgt - 0.55 * wdt, x + wdt / 2 + 0.4 * H, G - hgt]
        if burned:
            pts = [x - wdt / 2 - 0.2 * H, G - hgt, x - wdt * 0.2, G - hgt - 0.35 * wdt, x - wdt * 0.05, G - hgt - 0.1 * wdt,
                   x + wdt * 0.15, G - hgt - 0.3 * wdt, x + wdt / 2, G - hgt]
        add(c.create_polygon(*pts, fill=rr, outline="", tags="world"))
        rect(x - 0.5 * H, G - 2.2 * H, x + 0.5 * H, G, _shade(col, 0.55))                     # door
        win = "#ffd27a" if (night and not burned) else _shade(col, 0.5)
        rect(x + wdt * 0.2, G - hgt * 0.7, x + wdt * 0.2 + 0.9 * H, G - hgt * 0.7 + 0.9 * H, win)
        if sign:
            rect(x - wdt / 2 - 1.2 * H, G - hgt * 0.8, x - wdt / 2 - 0.1 * H, G - hgt * 0.8 + 0.8 * H,
                 _mix_hex("#c9a66b", "#0b1018", 0.4 - 0.3 * lit))

    # layout: gates at the edges, fields, then the town around a central market
    xs = {"gate": (0.07 * W, 0.93 * W), "fields": (0.16 * W, 0.84 * W), "tavern": 0.33 * W,
          "workshop": 0.42 * W, "market": 0.5 * W, "hall": 0.6 * W, "shrine": 0.7 * W, "well": 0.54 * W}
    for fx in xs["fields"]:
        for k in range(6):
            yy = G + 6 + k * 5
            add(c.create_line(fx - 3 * H, yy, fx + 3 * H, yy, fill=_mix_hex("#8a7a3a", "#0b1018", 0.45 - 0.35 * lit),
                              width=2, tags="world"))
        for k in range(8):
            px = fx - 2.8 * H + k * 0.8 * H
            add(c.create_line(px, G, px, G - 0.9 * H, fill=_mix_hex("#9aa04a", "#0b1018", 0.45 - 0.35 * lit),
                              width=2, tags="world"))
    ppl = soc.people(s.name) if s and not dead else []
    n_houses = max(3, min(9, len(ppl) // 2 + (s.pop // 40 if s else 0)))
    reserved = [(xs["tavern"], 4.5 * H), (xs["workshop"], 3.5 * H), (xs["market"], 7.5 * H), (xs["hall"], 5.0 * H),
                (xs["shrine"], 3.0 * H), (xs["shrine"] + 9 * H, 7.0 * H), (xs["well"], 2.0 * H)]
    reserved += [(fx, 4.0 * H) for fx in xs["fields"]] + [(gx, 2.5 * H) for gx in xs["gate"]]
    houses = []
    x = 0.21 * W
    while x < 0.8 * W and len(houses) < n_houses:
        if all(abs(x - rx) > rw + 2.8 * H for rx, rw in reserved) and all(abs(x - hx) > 6.0 * H for hx in houses):
            houses.append(x)
        x += 0.7 * H
    for i, x in enumerate(houses):
        house(x, 4.8 * H, 4.2 * H, dead, (i / max(1, len(houses))) < damage * 0.6)
    house(xs["tavern"], 7.0 * H, 5.0 * H, dead, damage > 0.7, sign=True)
    house(xs["hall"], 8.0 * H, 5.6 * H, dead, damage > 0.85)
    if not dead:
        # market stalls with striped awnings
        for k, dx in enumerate((-4.2, 0.0, 4.2)):
            mx = xs["market"] + dx * H
            rect(mx - 1.5 * H, G - 1.3 * H, mx + 1.5 * H, G, _shade(wall_c, 0.9))
            for p_ in (-1.4, 1.4):
                rect(mx + p_ * H - 1, G - 3.4 * H, mx + p_ * H + 1, G - 1.3 * H, _shade(wall_c, 0.6))
            for st in range(4):
                col = _mix_hex(("#c24a3a", "#e8e0d0")[st % 2] if k != 1 else ("#3a6ac2", "#e8e0d0")[st % 2],
                               "#0b1018", 0.45 - 0.35 * lit)
                x0 = mx - 1.8 * H + st * 0.9 * H
                add(c.create_polygon(x0, G - 3.4 * H, x0 + 0.9 * H, G - 3.4 * H, x0 + 1.0 * H, G - 2.8 * H,
                                     x0 + 0.1 * H, G - 2.8 * H, fill=col, outline="", tags="world"))
        # shrine with a spire; graves of this settlement's real dead
        sx = xs["shrine"]
        rect(sx - 2 * H, G - 3.8 * H, sx + 2 * H, G, _mix_hex("#b8b0a0", "#0b1018", 0.45 - 0.35 * lit))
        add(c.create_polygon(sx - 2.3 * H, G - 3.8 * H, sx, G - 7.5 * H, sx + 2.3 * H, G - 3.8 * H,
                             fill=roof_c, outline="", tags="world"))
        graves = [n for n in soc.npcs.values() if not n.alive and n.sett == s.name][:12] if soc else []
        for k, n in enumerate(graves):
            gx = sx + 3.2 * H + k * 1.1 * H
            rect(gx - 0.35 * H, G - 1.1 * H, gx + 0.35 * H, G, _mix_hex("#8a8a8a", "#0b1018", 0.45 - 0.35 * lit))
        P["graves"] = sx + 3.2 * H + max(0, len(graves) - 1) * 0.55 * H
        # well
        wx = xs["well"]
        rect(wx - 1.1 * H, G - 1.2 * H, wx + 1.1 * H, G, _mix_hex("#7a7a74", "#0b1018", 0.45 - 0.35 * lit))
        add(c.create_polygon(wx - 1.4 * H, G - 3.2 * H, wx, G - 4.0 * H, wx + 1.4 * H, G - 3.2 * H,
                             fill=roof_c, outline="", tags="world"))
        # guard towers at the gates
        for gx in xs["gate"]:
            rect(gx - 1.1 * H, G - 7.0 * H, gx + 1.1 * H, G, _shade(wall_c, 0.85))
            rect(gx - 1.6 * H, G - 7.4 * H, gx + 1.6 * H, G - 6.8 * H, _shade(wall_c, 0.7))
    P.update(xs)
    P["houses"] = houses
    self._places = P
    # affordances for anyone here, Jane included
    if not dead:
        self.pois = [WorldPOI("food", f"{s.name} market", xs["market"], G, 60, "stalls selling bread and goods"),
                     WorldPOI("water", f"{s.name} well", xs["well"], G, 40, "a stone well"),
                     WorldPOI("shelter", f"{s.name} tavern", xs["tavern"], G, 60, "a warm tavern with rooms")]
    else:
        self.pois = [WorldPOI("shelter", f"ruins of {s.name if s else 'a village'}", 0.5 * W, G, 60, "broken walls")]


# ---- bodies ------------------------------------------------------------------------------------
_RW_ROLE_COL = {"farmer": "#7a6a3a", "woodcutter": "#5a6a3a", "crafter": "#6a4a3a", "trader": "#3a5a7a",
                "guard": "#5a5a66", "priest": "#d8d0c0", "leader": "#7a2a3a", "child": "#8a7a9a", "citizen": "#6a6a5a"}
_RW_WORK = {"farmer": "fields", "woodcutter": "gate", "crafter": "workshop", "trader": "market",
            "guard": "gate", "priest": "shrine", "leader": "hall", "child": "market", "citizen": "market"}


class Body:
    def __init__(self, npc, places, H, rng, extra=False):
        self.npc = npc
        self.extra = extra
        self.role = npc.role if npc else "citizen"
        seed = hash(npc.id if npc else rng.random()) & 0xffffff
        r = _rw_random.Random(seed)
        self.x = r.uniform(0.2, 0.8) * places.get("_w", 900)
        self.target = self.x
        self.state = "walk"
        self.t = r.uniform(0, 10)
        self.facing = 1
        self.bubble = None
        self.bubble_t = 0.0
        self.hidden = False
        self.skin = r.choice(("#f0cdb5", "#d9a882", "#b27a55", "#8a5a3c", "#f6dccb", "#c89070"))
        self.hair = r.choice(("#2a1e16", "#5a3a22", "#8a6a3a", "#c9a36a", "#9a9a9a", "#1a1a1a"))
        wealth = min(1.0, (npc.wealth if npc else 3.0) / 25.0)
        self.col = _mix_hex(_RW_ROLE_COL.get(self.role, "#6a6a5a"), "#b89a4a", 0.25 * wealth)
        age = npc.phys["age"] if npc else r.uniform(18, 60)
        self.scale = 0.55 if age < 12 else (0.8 if age < 16 else 1.0)
        self.build = r.uniform(0.85, 1.15)
        houses = places.get("houses") or [places.get("_w", 900) * 0.5]
        self.home = houses[seed % len(houses)]
        self.pace = r.uniform(0.85, 1.1)
        self.lie = 0.0
        self.next = r.uniform(0, 0.25)
        self.off = r.uniform(-1.0, 1.0)                    # where around a shared place THEY stand

    def work_x(self, places):
        w = places.get(_RW_WORK.get(self.role, "market"))
        if isinstance(w, tuple):
            # shared work sites on both sides of town: people split between them
            w = w[0] if (self.off < 0) else w[1]
        return w if w is not None else self.home


def _rw_schedule(b, places, hour, rng):
    """Where this person should be now: role x hour x their inner state."""
    n = b.npc
    grief = n.grief[1] if (n is not None and "grief" in n.__dict__) else 0.0
    injury = n.injury if (n is not None and "injury" in n.__dict__) else 0.0
    if b.lie > 0:
        return b.x, "hurt"
    if injury > 0.6:
        return b.home, "home"
    if hour >= 22 or hour < 6:
        return b.home, "home"
    if grief > 0.4 and 17 <= hour < 21 and places.get("graves"):
        return places["graves"], "mourn"
    if 12 <= hour < 13 or 18 <= hour < 19:
        return (places.get("tavern") if n is not None and n.t.get("sociability", 0.5) > 0.55 else b.home), "eat"
    if 19 <= hour < 22:
        soc_ = n.t.get("sociability", 0.5) if n is not None else 0.5
        return (places.get("tavern") if soc_ > 0.45 else b.home), "evening"
    wx = b.work_x(places)
    if b.role == "guard":
        g = places.get("gate", (100, 800))
        wx = g[int((b.t // 20) % 2)] if isinstance(g, tuple) else wx
    if b.role in ("child", "citizen"):
        wx = wx + rng.uniform(-6, 6) * 30
    return wx, "work"


def _rw_spawn_bodies(app):
    world = app.world
    places = dict(getattr(world, "_places", {}) or {})
    places["_w"] = world.w
    H = app.creature._H()
    soc = app.society
    s = soc.sets.get(_rw_here(app)[1])
    bodies = []
    rng = _rw_random.Random(7)
    if s and s.alive:
        for n in soc.people(s.name)[:14]:
            b = Body(n, places, H, rng)
            bodies.append(b)
        for k in range(min(8, s.pop // 20)):
            bodies.append(Body(None, places, H, _rw_random.Random(hash((s.name, k)) & 0xffff), extra=True))
    app.bodies = bodies
    app._rw_places = places


def _rw_grid(bodies, cell=150.0):
    g = {}
    for b in bodies:
        if not b.hidden:
            g.setdefault(int(b.x // cell), []).append(b)
    return g


def _rw_near(grid, x, r, cell=150.0):
    out = []
    for k in range(int((x - r) // cell), int((x + r) // cell) + 1):
        for b in grid.get(k, ()):
            if abs(b.x - x) <= r:
                out.append(b)
    return out


def _rw_bodies_tick(app, dt):
    bodies = getattr(app, "bodies", None)
    if not bodies:
        return
    places = app._rw_places
    hour = _rw_time.localtime().tm_hour
    rng = _rw_random
    H = app.creature._Hb()
    for b in bodies:
        b.t += dt
        b.next -= dt
        if b.bubble_t > 0:
            b.bubble_t -= dt
            if b.bubble_t <= 0:
                b.bubble = None
        if b.lie > 0:
            b.lie -= dt
            continue
        if getattr(b, "scene", None) is None and b.next <= 0:          # staggered ~4 Hz decisions
            b.next = 0.25
            tx, st = _rw_schedule(b, places, hour, rng)
            if st != "home":
                tx += b.off * 4.5 * H                      # people spread around a stall, a door, a grave
                if st == b.state and abs(b.x - tx) < 5.5 * H:
                    tx = b.target                           # already in the area: don't pull them back into a knot
            if abs(tx - b.target) > 25 or st != b.state:
                b.target, b.state = tx, st
        d = b.target - b.x
        inj = b.npc.__dict__.get("injury", 0.0) if b.npc else 0.0
        grief = b.npc.__dict__.get("grief", [None, 0.0])[1] if b.npc else 0.0
        speed = 70.0 * b.pace * b.scale ** 0.5 * (1.0 - 0.5 * inj) * (1.0 - 0.3 * grief)
        if getattr(b, "scene", None) is not None and b.scene.get("run"):
            speed *= 1.8
        if abs(d) > 4:
            step = max(-speed * dt, min(speed * dt, d))
            b.x += step
            b.facing = 1 if d > 0 else -1
            b.moving = True
        else:
            b.moving = False
        # home at night / after injury: inside the house
        b.hidden = b.state == "home" and not b.moving and abs(b.x - b.home) < 6
    grid = app._rw_grid = _rw_grid(bodies)
    # personal space: bodies that stand too close drift apart (people who are
    # talking to each other keep a conversational distance instead)
    gap = 1.5 * H
    for b in bodies:
        if b.hidden or b.lie > 0:
            continue
        push = 0.0
        for o in _rw_near(grid, b.x, gap):
            if o is b or o.lie > 0:
                continue
            d = b.x - o.x
            if abs(d) < gap:
                side = 1.0 if (d > 0 or (d == 0 and id(b) > id(o))) else -1.0
                push += side * (gap - abs(d)) * 0.5
        if push and getattr(b, "scene", None) is None:
            b.x += max(-40 * dt, min(40 * dt, push))
            if not getattr(b, "moving", False):
                b.target = b.x


def _rw_draw_bodies(app):
    bodies = getattr(app, "bodies", None)
    cam = getattr(app, "_camera", None)
    if cam is None:
        return
    pool = getattr(app, "_rw_pool", None)
    if pool is None:
        pool = app._rw_pool = _AtmoPool(app.stage)
    pool.begin()
    if bodies:
        W = cam.world_to_screen
        H = app.creature._H()
        G = app.world.ground + app.creature._sole() * 0.2
        sg = getattr(app, "_scene_grade", None)
        gc = (lambda c_, y: sg.color(c_, y)) if sg else (lambda c_, y: c_)
        vx0, _ = cam.screen_to_world(-80, 0)
        vx1, _ = cam.screen_to_world(app.stage.winfo_width() + 80, 0)
        for b in sorted(bodies, key=lambda b: b.x):
            if b.hidden or not (vx0 < b.x < vx1):
                continue
            _rw_draw_body(b, pool, W, H, G, gc, cam)
    pool.end()


def _rw_draw_body(b, P, W, H, G, gc, cam):
    k = b.scale * b.build
    hgt = 7.4 * H * b.scale
    x = b.x
    small = hgt * cam.zoom < 70
    ph = b.t * 7.0 * b.pace
    walk = getattr(b, "moving", False)
    if b.lie > 0 or b.state == "hurt":                                  # on the ground
        body = [x - 3.4 * H, G - 0.2 * H, x + 3.0 * H, G - 0.2 * H, x + 3.0 * H, G - 1.1 * H, x - 3.4 * H, G - 1.1 * H]
        P.put("polygon", [c_ for i in range(0, 8, 2) for c_ in W(body[i], body[i + 1])], "fauna",
              fill=gc(b.col, G), outline="", smooth=False)
        hx, hy = W(x + 3.6 * H, G - 0.6 * H)
        r = 0.5 * H * cam.zoom
        P.put("oval", [hx - r, hy - r, hx + r, hy + r], "fauna", fill=gc(b.skin, G), outline="")
        return
    kneel = b.state == "mourn" and not walk
    hip_y = G - (3.9 if not kneel else 2.2) * H * b.scale
    trousers = _shade(b.col, 0.55) if b.role != "priest" else _shade(b.col, 0.8)
    for s_ in (-1, 1):
        sw = _rw_math.sin(ph + (s_ > 0) * _rw_math.pi) * 0.7 * H * b.scale * walk
        knee = (x + sw * 0.5 * b.facing + s_ * 0.15 * H, G - (2.0 if not kneel else 0.4) * H * b.scale)
        foot = (x + sw * b.facing + s_ * 0.2 * H + (1.2 * H * b.facing if kneel and s_ > 0 else 0), G - 0.3 * H)
        P.put("line", [*W(x + s_ * 0.32 * H * k, hip_y), *W(*knee), *W(*foot)], "fauna",
              fill=gc(trousers, G), width=max(3, int(0.42 * H * k * cam.zoom)))
        if not small:                                                  # boots
            P.put("line", [*W(foot[0] - 0.2 * H * b.facing, G - 0.15 * H), *W(foot[0] + 0.45 * H * b.facing, G - 0.15 * H)],
                  "fauna", fill=gc("#2a2019", G), width=max(3, int(0.3 * H * cam.zoom)))
    top = hip_y - 2.8 * H * b.scale
    robe = b.role == "priest"
    hem = G - 0.4 * H if robe else hip_y + 0.3 * H
    # torso: sloped shoulders, narrower waist, the hem flares a little
    sh = 0.95 * H * k * (0.9 if b.scale < 1 else 1.0)
    body = [x - 0.62 * H * k, hip_y - 0.1 * H, x - 0.78 * H * k, hem, x + 0.78 * H * k, hem, x + 0.62 * H * k, hip_y - 0.1 * H,
            x + sh, top + 0.35 * H, x + 0.45 * H, top, x - 0.45 * H, top, x - sh, top + 0.35 * H]
    P.put("polygon", [c_ for i in range(0, 16, 2) for c_ in W(body[i], body[i + 1])], "fauna",
          fill=gc(b.col, G - 5 * H), outline="", smooth=True)
    if not small:
        P.put("line", [*W(x - 0.62 * H * k, hip_y - 0.15 * H), *W(x + 0.62 * H * k, hip_y - 0.15 * H)], "fauna",
              fill=gc(_shade(b.col, 0.5), G), width=max(2, int(0.14 * H * cam.zoom)))           # belt
    work = b.state == "work" and not walk and b.role in ("farmer", "woodcutter", "crafter")
    for s_ in (-1, 1):
        arm = _rw_math.sin(ph + (s_ > 0) * _rw_math.pi) * 0.5 * H * walk
        if work and s_ > 0:
            arm = _rw_math.sin(b.t * 3.0) * 0.9 * H
        sx0 = x + s_ * sh * 0.85
        elbow = (sx0 + arm * 0.5 * b.facing, top + 1.2 * H * b.scale)
        hand = (sx0 + arm * b.facing, top + 2.3 * H * b.scale)
        P.put("line", [*W(sx0, top + 0.4 * H), *W(*elbow), *W(*hand)], "fauna",
              fill=gc(_shade(b.col, 0.9), G - 5 * H), width=max(2, int(0.3 * H * k * cam.zoom)))
        hr = 0.17 * H * cam.zoom
        hx_, hy_ = W(*hand)
        P.put("oval", [hx_ - hr, hy_ - hr, hx_ + hr, hy_ + hr], "fauna", fill=gc(b.skin, G - 4 * H), outline="")
    nx0, ny0 = W(x - 0.2 * H, top - 0.1 * H)
    nx1, ny1 = W(x + 0.2 * H, top + 0.25 * H)
    P.put("oval", [nx0, ny0, nx1, ny1], "fauna", fill=gc(_shade(b.skin, 0.9), G - 6 * H), outline="")
    hx, hy = W(x, top - 0.6 * H * b.scale)
    r = 0.55 * H * b.scale * cam.zoom
    head_y = top - 0.6 * H * b.scale + (0.25 * H if b.npc is not None and b.npc.__dict__.get("grief", [0, 0])[1] > 0.4 else 0)
    hx, hy = W(x, head_y)
    P.put("oval", [hx - r, hy - r * 1.15, hx + r, hy + r * 1.15], "fauna", fill=gc(b.skin, G - 7 * H), outline="")
    if b.role == "guard":
        P.put("oval", [hx - r * 1.1, hy - r * 1.35, hx + r * 1.1, hy - r * 0.1], "fauna", fill=gc("#8a8a90", G), outline="")
        P.put("line", [*W(x + 1.0 * H * b.facing, top - 2.4 * H), *W(x + 1.0 * H * b.facing, G - 0.3 * H)], "fauna",
              fill=gc("#8a8a8a", G), width=2)
    elif b.role == "farmer" and not small:
        P.put("oval", [hx - r * 1.7, hy - r * 1.0, hx + r * 1.7, hy - r * 0.55], "fauna", fill=gc("#c9b06a", G), outline="")
    else:
        P.put("oval", [hx - r * 1.05, hy - r * 1.3, hx + r * 1.05, hy - r * 0.2], "fauna", fill=gc(b.hair, G), outline="")
    if b.role == "leader" and not small:
        P.put("line", [*W(x - 0.7 * H, top + 0.4 * H), *W(x + 0.7 * H, hip_y - 0.2 * H)], "fauna",
              fill=gc("#c9a040", G), width=2)
    if b.bubble and not small:
        bx, by = W(x, top - 2.4 * H * b.scale)
        s_ = 0.45 * H * cam.zoom
        if b.bubble == "heart":
            P.put("polygon", [bx, by + s_, bx - s_, by - 0.2 * s_, bx - 0.6 * s_, by - 0.8 * s_, bx, by - 0.4 * s_,
                              bx + 0.6 * s_, by - 0.8 * s_, bx + s_, by - 0.2 * s_], "fauna", fill="#e25a7a", outline="", smooth=True)
        elif b.bubble == "anger":
            P.put("line", [bx - s_, by, bx - 0.3 * s_, by - s_, bx + 0.3 * s_, by, bx + s_, by - s_], "fauna",
                  fill="#e24a3a", width=2)
        elif b.bubble == "alarm":
            P.put("line", [bx, by - s_, bx, by + 0.2 * s_], "fauna", fill="#f2c14e", width=3)
        elif b.bubble == "tear":
            P.put("oval", [bx - 0.3 * s_, by - 0.4 * s_, bx + 0.3 * s_, by + 0.4 * s_], "fauna", fill="#6aa8e8", outline="")


# ---- enacted moral scenes (only where Jane is) --------------------------------------------------
_RW_BUBBLE = {"help": "heart", "comfort": "heart", "court": "heart", "forgive": "heart", "apologize": "heart",
              "befriend": None, "quarrel": "anger", "assault": "anger", "steal": None, "betray": "anger",
              "exploit": None}

_rw_prev_act = MoralEngine._act


def _rw_act(self, kind, a, b, s, circ, ppl):
    app = getattr(self.soc, "_app_ref", None)
    if app is not None and _rw_here(app) == ("settlement", s.name) and kind != "befriend":
        bs = {bd.npc.id: bd for bd in getattr(app, "bodies", []) if bd.npc is not None}
        ba, bb = bs.get(a.id), bs.get(b.id)
        if ba is not None and bb is not None and not ba.hidden and not bb.hidden \
                and getattr(ba, "scene", None) is None and getattr(bb, "scene", None) is None:
            sc = {"kind": kind, "a": ba, "b": bb, "s": s, "circ": dict(circ), "ppl": ppl, "t": 0.0,
                  "run": kind in ("assault", "steal")}
            ba.scene = bb.scene = sc
            app.__dict__.setdefault("scenes", []).append(sc)
            return                                               # outcome decided when it plays out
    return _rw_prev_act(self, kind, a, b, s, circ, ppl)


MoralEngine._act = _rw_act


def _rw_scenes_tick(app, dt):
    scenes = getattr(app, "scenes", None)
    if not scenes:
        return
    H = app.creature._Hb()
    grid = getattr(app, "_rw_grid", {})
    keep = []
    for sc in scenes:
        a, b = sc["a"], sc["b"]
        sc["t"] += dt
        if sc["t"] < 12.0 and abs(a.x - b.x) > 1.6 * H:
            a.target = b.x - (1.4 * H if a.x < b.x else -1.4 * H)       # go to them
            keep.append(sc)
            continue
        if sc.get("done_t") is None:
            sc["done_t"] = sc["t"]
            # physical facts decide: is a guard close enough to see?
            guards = [g for g in _rw_near(grid, a.x, 9 * H) if g.role == "guard" and g is not a and g is not b]
            sc["circ"]["guards"] = 1.0 if guards else 0.0
            for g in guards:
                g.target, g.bubble, g.bubble_t = a.x, "alarm", 4.0
            eng = app.society.__dict__.get("_moral")
            try:
                if eng is not None:
                    n_ev = len(app.society.events)
                    _rw_prev_act(eng, sc["kind"], a.npc, b.npc, sc["s"], sc["circ"], sc["ppl"])
                    new = app.society.events[n_ev:]
                    _rw_witness(app, sc, new)
            except Exception:
                traceback.print_exc()
            bub = _RW_BUBBLE.get(sc["kind"])
            if bub:
                a.bubble = b.bubble = bub
                a.bubble_t = b.bubble_t = 4.0
            if sc["kind"] == "assault":
                loser = a if (a.npc.__dict__.get("injury", 0) > b.npc.__dict__.get("injury", 0)) else b
                loser.lie = 12.0
                loser.bubble, loser.bubble_t = "tear", 10.0
            if sc["kind"] == "steal" and not sc["circ"]["guards"]:
                a.target = a.x + (a.x - b.x) * 3                        # the thief slips away
        if sc["t"] - sc["done_t"] < 3.0:
            keep.append(sc)
        else:
            a.scene = b.scene = None
    app.scenes = keep


def _rw_witness(app, sc, new_events):
    cr, b = app.creature, app.brain
    H = cr._Hb()
    near = min(abs(sc["a"].x - cr.x), abs(sc["b"].x - cr.x)) < 11 * H
    texts = [e[3] for e in new_events] or ([f"{sc['a'].npc.name} and {sc['b'].npc.name} made up"]
                                           if sc["kind"] == "forgive" else [])
    if not near or not texts:
        return
    dark = sc["kind"] in ("assault", "steal", "betray", "quarrel", "exploit")
    for t in texts[:1]:
        b.perceive(Event("witness", f"I saw it: {t}", salience=0.75 if dark else 0.55, valence=-0.5 if dark else 0.45))
    life = _lf_life(app)
    people = life.__dict__.setdefault("people", {})
    for body, sign in ((sc["a"], -1 if dark else 1), (sc["b"], 1)):
        p = people.setdefault(body.npc.id, {"name": body.npc.name, "from": sc["s"].name, "met": 0, "like": 0.0})
        p["like"] = clamp(p["like"] + 0.1 * sign, -1.0, 1.0)


# ---- Jane's own kindness: sharing food with someone in need --------------------------------------
_AG_EXTRA["give_food"] = dict(pre={"food_any": 1}, eff={"helped": ("set", 1)}, dur=2.5, at="needy", task="give")
_AG_SAY["give_food"] = "share some food"
_AG_EXTRA["sell_goods"] = dict(pre={"surplus": 1, "market": 1}, eff={"coins": 3, "surplus": ("set", 0),
                                                                      "traded": ("set", 1)}, dur=3.0,
                               at="market", task="sell")
_AG_EXTRA["buy_food"] = dict(pre={"coins": 1, "market": 1}, eff={"coins": -1, "berries": 2}, dur=2.0, at="market",
                             task="buyfood")
_AG_EXTRA["buy_item"] = dict(pre={"coins": 4, "market": 1}, eff={"coins": -4, "traded": ("set", 1)}, dur=3.0,
                             at="market", task="buy")
for _k, _v in (("sell_goods", "sell what I can spare"), ("buy_food", "buy bread"), ("buy_item", "buy something I need")):
    _AG_SAY[_k] = _v
_AG_GOALS["market"] = {"traded": 1}

_rw_prev_state = _ag_state


def _rw_state(app, sv, life):
    s = _rw_prev_state(app, sv, life)
    here = _rw_here(app)
    s["coins"] = int(getattr(life, "coins", 0))
    s["market"] = int(here[0] == "settlement" and bool(app.world.poi("food")))
    s["food_any"] = int(sv.inv.get("berries", 0) > 0 or sv.inv.get("meat", 0) > 0)
    if here[0] != "valley":
        s["fire"] = 0                                   # her fire and home are in the valley
        s["home"] = 0
        if here[0] == "settlement":
            s["food_avail"] = 0                         # food here is bought, not picked
    return s


_ag_state = _rw_state

_rw_prev_where = _ag_where


def _rw_where(app, sv, life, at, cand):
    here = _rw_here(app)
    if here[0] != "valley" and at in ("home", "homesite", "firesite", "fire", "fire_side"):
        return None
    if at == "bed" and here[0] == "settlement":
        p = app.world.poi("shelter")
        return p.x if p else None
    if at == "market":                                   # the spot beside the stall - one point for everyone
        p = app.world.poi("food") if here[0] == "settlement" else None
        return p.x + 1.5 * app.creature._Hb() if p else None
    if at == "needy":
        tgt = getattr(sv, "_needy", None)
        return tgt.x + (1.3 if app.creature.x > tgt.x else -1.3) * app.creature._Hb() if tgt else None
    return _rw_prev_where(app, sv, life, at, cand)


_ag_where = _rw_where

_rw_prev_goal_facts = _ag_goal_facts


def _rw_goal_facts(name, s):
    if name.startswith("help:"):
        return {"helped": 1}
    return _rw_prev_goal_facts(name, s)


_ag_goal_facts = _rw_goal_facts

# ---- candidate goals: journeys, market, helping --------------------------------------------------
_rw_prev_plan_adjust = _m41_plan_adjust


def _rw_plan_adjust(sv, app, life, cand):
    _rw_prev_plan_adjust(sv, app, life, cand)
    soc = getattr(app, "society", None)
    if soc is None:
        return
    regions = getattr(app, "_regions", None) or _rw_regions(soc)
    here = _rw_here(app)
    g, cr, b = app.brain.goals, app.creature, app.brain
    tr = b.personality.traits
    idx = regions.index(here) if here in regions else regions.index(("valley", "valley"))
    dark = app.world.daypart in ("evening", "night")
    P = life.phys
    away_for = life.clock - getattr(life, "_rw_left", life.clock)
    surplus = sv.inv.get("wood", 0) >= 4 or sv.inv.get("meat", 0) >= 1 or sv.inv.get("berries", 0) >= 3
    owned = life.__dict__.setdefault("possessions", [])
    wants = [x for x in ("blanket", "salt", "lantern") if x not in owned]
    if here[0] == "valley":
        best = None
        for i, (kind, name) in enumerate(regions):
            if kind != "settlement":
                continue
            s = soc.sets.get(name)
            if s is None or not s.alive or s.war:          # not into a war
                continue
            dist = abs(i - idx)
            known = b.knowledge.get(f"place:{name}") is not None if hasattr(b.knowledge, "get") else False
            friends = [p for p in getattr(life, "people", {}).values() if p.get("from") == name and p.get("like", 0) > 0.3]
            u = (0.35 if (surplus and wants) else 0.0) + 0.3 * g.social * bool(friends) \
                + 0.25 * g.stimulation * tr.get("curiosity", 0.5) * (1.0 if known else 0.4) - 0.08 * dist
            if not dark and P["sleep_pressure"] < 0.5 and u > 0.15 and (best is None or u > best[0]):
                best = (u, i, name)
        if best:
            cand[f"journey:{best[1]}"] = (best[0], ("travel", best[1]))
    else:
        # her fire, her home and their chores exist only in the valley
        for k_ in ("fire", "fire_cook", "home", "repair", "warm", "cook"):
            cand.pop(k_, None)
        home_u = 0.2 + 0.5 * dark + 0.5 * max(0.0, P["sleep_pressure"] - 0.4) + 0.001 * away_for
        coins = int(getattr(life, "coins", 0))
        if here[0] == "settlement" and (surplus or (coins >= 4 and wants) or (g.hunger > 0.4 and coins >= 1)):
            cand["market"] = (0.45 + 0.2 * bool(wants), ("sell", cr.x))
            home_u -= 0.25
        cand[f"journey:{regions.index(('valley', 'valley'))}"] = (home_u, ("travel", regions.index(("valley", "valley"))))
        # someone here needs help, and she has food
        needy = [bd for bd in getattr(app, "bodies", []) if bd.npc is not None and not bd.hidden
                 and abs(bd.x - cr.x) < 10 * cr._Hb()
                 and (bd.npc.phys["hunger"] > 0.6 or bd.npc.__dict__.get("injury", 0) > 0.4 or bd.lie > 0)]
        if needy and (sv.inv.get("berries", 0) or sv.inv.get("meat", 0)):
            nb = needy[0]
            sv._needy = nb
            kind_ = 0.3 + 0.5 * tr.get("friendliness", 0.5) + 0.2 * b.emotion.valence
            cand[f"help:{nb.npc.id}"] = (kind_ * (0.6 + nb.npc.phys["hunger"]), ("give", nb.x))


_m41_plan_adjust = _rw_plan_adjust

# journeys are hops between regions; M42 plans within a region
_rw_prev_decide = _m42_decide


def _rw_decide(sv, app, life, cand, task):
    life = _lf_life(app)
    ranked = sorted(cand, key=lambda k: -cand[k][0])
    jn = next((k for k in ranked[:1] if k.startswith("journey:")), None)
    if jn is not None and getattr(life, "journey", None) is None:
        life.journey = int(jn.split(":")[1])
        life.plan = None
        _ag_think(app, "I'm going to " + (app._regions[life.journey][1] if app._regions[life.journey][0] != "valley"
                                            else "head home to the valley"))
    j = getattr(life, "journey", None)
    if j is not None:
        idx = app._regions.index(_rw_here(app))
        if idx == j:
            life.journey = None
        else:
            edge = 40 if j < idx else app.world.w - 40
            return ("travel", edge)
    return _rw_prev_decide(sv, app, life, cand, task)


_m42_decide = _rw_decide

# ---- executing travel, market, giving ---------------------------------------------------------------
_rw_prev_sv_act = Survival._act


def _rw_sv_act(self, app, dt):
    t = self.task
    cr = app.creature
    H = cr._Hb()
    life = _lf_life(app)
    if t and t[0] == "travel":
        cr.set_target(t[1], cr.y)
        if (t[1] < app.world.w / 2 and cr.x <= 75) or (t[1] > app.world.w / 2 and cr.x >= app.world.w - 75):
            _rw_switch(app, -1 if t[1] < app.world.w / 2 else 1)
            self.task = None
        return
    if t and t[0] in ("sell", "buyfood", "buy", "give"):
        tx = t[1]
        if t[0] == "give" and getattr(self, "_needy", None) is not None:
            tx = self._needy.x + (1.3 if cr.x > self._needy.x else -1.3) * H
            self.task = ("give", tx)                     # keep the world step aiming at the same spot
        if abs(cr.x - tx) > 18:
            cr.set_target(tx, cr.y)
            return
        self.timer += dt
        if self.timer < 2.5:
            return
        self.timer = 0.0
        s = app.society.sets.get(_rw_here(app)[1])
        rep = s.jane_rep if s else 0.0
        if t[0] == "sell":
            earned = 0
            for k, n, v in (("meat", 1, 3), ("wood", 3, 2), ("berries", 3, 1)):
                while self.inv.get(k, 0) >= n and earned < 8:
                    self.inv[k] -= n
                    earned += int(round(v * (1.0 + 0.3 * rep)))
            life.coins = int(getattr(life, "coins", 0)) + earned
            owned = life.__dict__.setdefault("possessions", [])
            want = next((x for x in ("blanket", "salt", "lantern") if x not in owned), None)
            price = max(2, int(round((4 if want == "lantern" else 3) * (1.2 - 0.4 * rep))))
            bought = None
            if want and life.coins >= price:
                life.coins -= price
                owned.append(want)
                bought = want
            if app.brain.goals.hunger > 0.4 and life.coins >= 1:
                life.coins -= 1
                self.inv["berries"] = self.inv.get("berries", 0) + 2
            self._traded_t = life.clock
            if s:
                s.jane_rep = clamp(s.jane_rep + 0.05, -1, 1)
                s.stock["food"] += 2
            msg = f"sold goods at the {s.name if s else ''} market for {earned} coins" + \
                (f" and bought {_SO_GOODS[bought][0]}" if bought else "")
            app.brain.perceive(Event("trade", msg, salience=0.55, valence=0.35))
        elif t[0] == "give":
            nb = getattr(self, "_needy", None)
            if nb is not None and nb.npc is not None:
                k = "meat" if self.inv.get("meat", 0) else "berries"
                if self.inv.get(k, 0):
                    self.inv[k] -= 1
                    n = nb.npc
                    n.phys["hunger"] = max(0.0, n.phys["hunger"] - 0.5)
                    if "injury" in n.__dict__:
                        n.injury = max(0.0, n.injury - 0.15)
                    n.rel["jane"] = clamp(n.rel.get("jane", 0.0) + 0.4, -1, 1)
                    n.remember(app.society.day, "the woman from the valley shared her food with me", 0.7)
                    nb.bubble, nb.bubble_t = "heart", 4.0
                    if s:
                        s.jane_rep = clamp(s.jane_rep + 0.1, -1, 1)
                    people = life.__dict__.setdefault("people", {})
                    p = people.setdefault(n.id, {"name": n.name, "from": n.sett, "met": 0, "like": 0.0})
                    p["like"] = clamp(p["like"] + 0.2, -1, 1)
                    app.brain.perceive(Event("social", f"shared my food with {n.name}, who needed it", salience=0.6, valence=0.5))
                    app.brain.goals.satisfy("social", 0.2, f"helped {n.name}")
            self._needy = None
            self._traded_t = life.clock
        self.task = None
        return
    return _rw_prev_sv_act(self, app, dt)


Survival._act = _rw_sv_act


def _rw_switch(app, direction):
    """Walk off the edge of one region into the next."""
    regions = app._regions
    here = _rw_here(app)
    idx = regions.index(here) + direction
    if not (0 <= idx < len(regions)):
        return
    life = _lf_life(app)
    fa = getattr(app, "fauna", None)
    devoted = lambda a: getattr(a, "psy", None) is not None and a.sp == "dog" and a.psy.rel_of("jane")["like"] > 0.5
    followers = [a for a in (fa.animals if fa else []) if devoted(a)]          # a devoted dog follows her
    if here[0] == "valley":
        life._rw_left = life.clock
        if fa is not None:                                 # valley animals sleep while she's away
            fa._stash = [a for a in fa.animals if a not in followers]
            fa._stash_t = fa.clock
    # what she was doing belongs to the place she's leaving: set it aside
    plan = getattr(life, "plan", None)
    if plan is not None:
        life.__dict__.setdefault("paused", []).append(dict(plan, snap=None, paused_at=life.clock))
        del life.paused[:-4]
        life.plan = None
    sv = getattr(app, "survival", None)
    if sv is not None:
        sv.task = None
    app.region = regions[idx]
    kind, name = app.region
    if fa is not None:
        if kind == "valley" and getattr(fa, "_stash", None) is not None:
            away = fa.clock - fa._stash_t
            for a in fa._stash:
                if getattr(a, "psy", None):
                    a.psy.need["hunger"] = min(1.0, a.psy.need["hunger"] + away * 0.001)
            fa.animals = fa._stash + followers
            fa._stash = None
        else:
            fa.animals = followers
    w = app.world
    w._region_kind, w._region_name = kind, name
    w._region_seed = (hash(name) & 0x3ff) if kind != "valley" else 0
    w._soc = app.society
    w._H_hint = app.creature._Hb()
    app._world_sig = None
    app._rw_arrive = direction                           # placed at the edge once the region is built
    cam = getattr(app, "_camera", None)
    if cam is not None:
        cam.vel = [0.0, 0.0]
    app.bodies = []
    app._rw_spawn_pending = kind == "settlement"
    if kind != "valley":
        app.brain.perceive(Event("travel", f"arrived at {name}" if kind == "settlement" else f"on the road toward {name}",
                                 salience=0.5 if kind == "settlement" else 0.3, valence=0.2))
        try:
            app.brain.knowledge.see("place", name, valence=0.1, note="I have been there")
        except Exception:
            pass
    else:
        app.brain.perceive(Event("travel", "back home in the valley", salience=0.45, valence=0.3))


def _rw_fauna_capacity(self, sp, daypart, weather):
    allowed = getattr(self, "_allowed", None)
    if allowed is not None and sp not in allowed:
        return 0
    return _rw_prev_capacity(self, sp, daypart, weather)


_rw_prev_capacity = Fauna._capacity
Fauna._capacity = _rw_fauna_capacity

# valley-only things stay in the valley
_rw_prev_sv_draw = Survival.draw


def _rw_sv_draw(self, app):
    if _rw_valley(app):
        return _rw_prev_sv_draw(self, app)
    f = self.fire
    if f is not None and f.pool is not None:
        f.pool.begin()
        f.pool.end()


Survival.draw = _rw_sv_draw
_rw_prev_home = _lf_draw_home


def _rw_home(app, life):
    if _rw_valley(app):
        return _rw_prev_home(app, life)
    if life.pool is not None:
        life.pool.begin()
        life.pool.end()


_lf_draw_home = _rw_home
_rw_prev_so_tick = _so_tick


def _rw_so_tick(app, dt):
    if _rw_valley(app):
        return _rw_prev_so_tick(app, dt)
    soc = _so_society(app)
    app._so_acc = getattr(app, "_so_acc", 0.0) + dt
    if app._so_acc >= 30.0:
        soc.step(app._so_acc / SOC_DAY)
        app._so_acc = 0.0
    for tv in getattr(app, "travellers", []):
        if tv.pool is not None:
            tv.pool.begin()
            tv.pool.end()
    app.travellers = []


_so_tick = _rw_so_tick

# ---- persistence ----------------------------------------------------------------------------------
_m43_save_hooks.append(lambda app: ("region", list(_rw_here(app))))


def _rw_load(app, w):
    r = w.get("region")
    if isinstance(r, list) and len(r) == 2 and r[0] in ("valley", "road", "settlement"):
        app.region = tuple(r)


_m43_load_hooks.append(_rw_load)
_rw_prev_life_to = JaneLife.to_dict
_rw_prev_life_from = JaneLife.from_dict


def _rw_life_to(self):
    d = _rw_prev_life_to(self)
    d["coins"] = int(getattr(self, "coins", 0))
    d["journey"] = getattr(self, "journey", None)
    return d


def _rw_life_from(self, d):
    _rw_prev_life_from(self, d)
    if isinstance(d, dict):
        self.coins = int(d.get("coins", 0) or 0)
        self.journey = d.get("journey")


JaneLife.to_dict = _rw_life_to
JaneLife.from_dict = _rw_life_from

# ---- wiring ------------------------------------------------------------------------------------
_rw_prev_update = App._update_world


def _rw_update(self, dt):
    soc = getattr(self, "society", None)
    if soc is not None:
        soc._app_ref = self
        regions = _rw_regions(soc)
        if _rw_here(self) not in regions:
            self.region = ("valley", "valley")
        self._regions = regions
        w = self.world
        kind, name = _rw_here(self)
        if getattr(w, "_region_name", "valley") != name or getattr(w, "_region_kind", "valley") != kind:
            w._region_kind, w._region_name = kind, name
            w._region_seed = (hash(name) & 0x3ff) if kind != "valley" else 0
            self._world_sig = None
        w._soc = soc
        w._H_hint = self.creature._Hb()
        fa = getattr(self, "fauna", None)
        if fa is not None:
            fa._allowed = _RW_ALLOWED.get(kind)
    _rw_prev_update(self, dt)
    try:
        w = self.world
        cam = getattr(self, "_camera", None)
        if cam is not None:
            cam.world_ext = (w.w, getattr(w, "h", self.stage.winfo_height()))
        cr = self.creature
        b = cr.bounds
        if b and b[2] != w.w - 60:
            cr.bounds = (60, b[1], max(160, w.w - 60), b[3])
        arr = getattr(self, "_rw_arrive", None)
        if arr is not None and getattr(w, "_built_for", None) == tuple(_rw_here(self)):
            self._rw_arrive = None
            cr.x = (w.w - 90) if arr < 0 else 90
            cr.target = (cr.x, cr.y)
            L = cr._loco
            # every locomotion anchor moves with her: pace scaling mixes the
            # current x with L.px, and a stale one extrapolated her off-world
            L.px = cr.x
            L.vx = 0.0
            for sd in ("L", "R"):
                L.foot[sd] = cr.x
                L.plant[sd] = cr.x
            fa = getattr(self, "fauna", None)
            for a in (fa.animals if fa else []):
                if getattr(a, "psy", None) is not None and a.sp == "dog":
                    a.x, a.goal = cr.x + (60 if arr < 0 else -60), cr.x
            if cam is not None:
                cam.pos[0] = cr.x
                cam.vel = [0.0, 0.0]
        if getattr(self, "_rw_spawn_pending", False) or (_rw_here(self)[0] == "settlement" and not getattr(self, "bodies", None)
                                                          and getattr(self.world, "_places", None)):
            self._rw_spawn_pending = False
            _rw_spawn_bodies(self)
        if _rw_here(self)[0] != "settlement" and getattr(self, "bodies", None):
            self.bodies = []
        _rw_bodies_tick(self, dt)
        _rw_scenes_tick(self, dt)
        _rw_draw_bodies(self)
        self.stage.tag_raise("fauna")
    except Exception:
        traceback.print_exc()


App._update_world = _rw_update


# market/giving steps complete when the exchange actually happened
_rw_prev_step_done = _ag_step_done


def _rw_step_done(n, snap, app, sv, life):
    if n in ("sell_goods", "buy_food", "buy_item", "give_food"):
        return getattr(sv, "_traded_t", -1) > snap.get("t", 0)
    return _rw_prev_step_done(n, snap, app, sv, life)


_ag_step_done = _rw_step_done

# raids scar a settlement's buildings; its people rebuild with their wood
_rw_prev_raid = MoralEngine.raid


def _rw_raid(self, s):
    _rw_prev_raid(self, s)
    s.damage = min(1.0, getattr(s, "damage", 0.0) + 0.2)


MoralEngine.raid = _rw_raid
_rw_prev_soc_step = Society.step


def _rw_soc_step(self, days):
    _rw_prev_soc_step(self, days)
    for s in self.sets.values():
        dmg = getattr(s, "damage", 0.0)
        if dmg > 0 and s.alive and s.stock["wood"] > 10:
            fix = min(dmg, days * 0.05)
            s.damage = dmg - fix
            s.stock["wood"] -= fix * 40
