# ============================================================================
# [NEW] WORLD OBJECTS + GROUNDED CONVERSATION
# ============================================================================
#
# 1. Persistent world objects. Fires are entities with a stable id, a region
#    and a position; they are created exactly once, relit in place (building
#    next to an old fire pit relights THAT pit), burn down on their own
#    (everywhere, not only where Jane is) and persist through save/load and
#    offline time. Each fire owns its drawing; a fire that is not in the
#    current view has its drawing hidden - the old campfire used to leave its
#    last frame of flames/smoke frozen in SCREEN space, which "followed" Jane
#    as the camera moved and looked like duplicates.
#    The same registry indexes everything else that already persists - her
#    home/bed, resources, trees, animals, townsfolk, places - under stable ids.
#
# 2. Conversation and simulation share one world state. Every chat turn the
#    system prompt carries a ground-truth brief of where she is and what is
#    around her (distances, directions, states), where her animals are, the
#    weather, what she carries and what she is doing - so "what's the closest
#    place?" or "where's the dog?" is answered from the simulation.
#
# 3. Spoken requests become real intentions. "Let's go home", "go there",
#    "light a fire", "find the dog", "stay here"... are parsed against the
#    registry and become a command her planner acts on (she walks, travels
#    between regions, builds) - and the prompt tells her what she decided,
#    so what she says matches what she does.

import re as _wo_re
import itertools as _wo_it


class WorldObjects:
    def __init__(self):
        self.fires = {}                 # oid -> Campfire
        self._ids = _wo_it.count(1)
        self.frame = 0

    def new_id(self, prefix):
        n = next(self._ids)
        while f"{prefix}{n}" in self.fires:
            n = next(self._ids)
        return f"{prefix}{n}"

    # -- fires --------------------------------------------------------------
    def adopt_fire(self, f, region, near=None):
        """A newly built fire: relight an existing pit here instead of
        making a second one; otherwise register exactly one new object."""
        for g in self.fires.values():
            ws = globals().get("WS")
            if g is not f and g.region == region and abs(g.x - f.x) < (near or (ws.m(4.0) if ws else 120)):
                g.lit, g.fuel, g.intensity = True, max(g.fuel, f.fuel), max(g.intensity, 0.5)
                g.relit = getattr(g, "relit", 0) + 1
                _wo_hide(f)
                return g
        f.oid = self.new_id("fire")
        f.region = region
        f.built_at = _ct_time.time()
        f.known = True
        self.fires[f.oid] = f
        return f

    def fires_in(self, region):
        return [f for f in self.fires.values() if f.region == region]

    def nearest_fire(self, region, x, lit_only=False):
        c = [f for f in self.fires_in(region) if f.lit or not lit_only]
        return min(c, key=lambda f: (not f.lit, abs(f.x - x))) if c else None

    def to_dict(self):
        return [{"oid": f.oid, "region": list(f.region), "x": round(f.x, 1), "fuel": round(f.fuel, 3),
                 "lit": f.lit, "built_at": getattr(f, "built_at", 0.0), "relit": getattr(f, "relit", 0)}
                for f in self.fires.values()]

    def from_list(self, items, elapsed=0.0):
        for d in items or []:
            try:
                f = Campfire(float(d["x"]))
                f.oid, f.region = d["oid"], tuple(d["region"])
                f.fuel = float(d["fuel"]) - elapsed / 240.0 * (1.0 if d.get("lit") else 0.0)
                f.lit = bool(d.get("lit")) and f.fuel > 0
                f.fuel = max(0.0, f.fuel)
                f.intensity = 1.0 if f.lit else 0.0
                f.built_at, f.relit, f.known = d.get("built_at", 0.0), d.get("relit", 0), True
                self.fires[f.oid] = f
                num = int(_wo_re.sub(r"\D", "", f.oid) or 0)
                self._ids = _wo_it.count(max(num + 1, next(self._ids)))
            except Exception:
                continue

    def prune(self):
        """Cold fire pits linger as ash for a while, then are gone."""
        cold = sorted((f for f in self.fires.values() if not f.lit), key=lambda f: getattr(f, "built_at", 0))
        while len(cold) > 4:
            f = cold.pop(0)
            _wo_hide(f)
            self.fires.pop(f.oid, None)


def _wo_hide(f):
    pool = getattr(f, "pool", None)
    if pool is not None:
        pool.begin()
        pool.end()


def _wo_objects(app):
    ob = getattr(app, "objects", None)
    if ob is None:
        ob = app.objects = WorldObjects()
    return ob


# one update per frame per fire, whoever asks
_wo_prev_fire_update = Campfire.update


def _wo_fire_update(self, dt, wx):
    fr = getattr(Campfire, "_frame_now", None)
    if fr is not None and getattr(self, "_frame", None) == fr:
        return
    self._frame = fr
    return _wo_prev_fire_update(self, dt, wx)


Campfire.update = _wo_fire_update


# all fires are drawn by the registry: the one in view drawn, others hidden
def _wo_sv_draw(self, app):
    ob = _wo_objects(app)
    here = _rw_here(app)
    cam = getattr(app, "_camera", None)
    wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
    for f in list(ob.fires.values()):
        if f.region == here and cam is not None:
            f.draw(app.stage, cam, app.world, getattr(app, "_scene_grade", None), wx, k=app.creature._H() / 12.0)
        else:
            _wo_hide(f)


Survival.draw = _wo_sv_draw

# the old single-fire save becomes the registry's list
_m43_save_hooks.append(lambda app: ("fire", None))
_m43_save_hooks.append(lambda app: ("objects", _wo_objects(app).to_dict()))


def _wo_load(app, w):
    ob = _wo_objects(app)
    elapsed = max(0.0, _ct_time.time() - float(w.get("saved_at", _ct_time.time())))
    items = w.get("objects")
    if items is None and w.get("fire"):                          # older save: one fire, valley
        fs = w["fire"]
        items = [{"oid": "fire1", "region": ["valley", "valley"], "x": fs["x"], "fuel": fs["fuel"], "lit": fs["lit"]}]
        w["fire"] = None
    ob.from_list(items, elapsed)


_m43_load_hooks.append(_wo_load)


# ============================================================================
# The world as Jane knows it right now
# ============================================================================

def _wo_m(app):
    """px -> metres, from the one world scale (WS)."""
    ws = globals().get("WS")
    return 1.0 / ws.px if ws else 0.3


def _wo_place_name(kind, name):
    return {"settlement": f"the town of {name}", "road": f"the road toward {name}", "valley": "your valley"}.get(kind, name)


def world_snapshot(app):
    """Everything around her, from the live simulation, with stable ids."""
    cr, w = app.creature, app.world
    here = _rw_here(app)
    life = _lf_life(app)
    m = _wo_m(app)
    out = []

    def add(oid, kind, name, x, state="", **kw):
        if x is None:
            return
        d = x - cr.x
        out.append(dict(id=oid, kind=kind, name=name, x=x, dist=abs(d) * m,
                        side="right" if d > 0 else "left", state=state, **kw))
    for f in _wo_objects(app).fires_in(here):
        add(f.oid, "fire", "your campfire" if getattr(f, "known", False) else "a campfire", f.x,
            "burning" if f.lit and f.intensity > 0.3 else ("smouldering" if f.lit else "a cold fire pit"))
    if here[0] == "valley" and life.home:
        h = life.home
        name = {1: "your lean-to", 2: "your shelter", 3: "your hut"}.get(h["stage"], "your home")
        add("home", "home", name, h["x"], "sound" if h["cond"] > 0.8 else ("weathered" if h["cond"] > 0.5 else "storm-damaged"))
        if h["stage"] >= 3:
            add("bed", "bed", "your bed (in the hut)", h["x"])
    for p in getattr(w, "pois", []):
        st = ""
        if p.kind in ("food", "water"):
            st = "plenty" if p.available() else "picked clean for now"
        add(f"poi:{here[1]}:{p.kind}", p.kind, p.name, p.x, st)
    trees = getattr(w, "_tree_x", None) or []
    if trees:
        t = min(trees, key=lambda t: abs(t - cr.x))
        add(f"tree:{here[1]}:{trees.index(t)}", "tree", "the nearest trees", t, f"{len(trees)} trees here")
    fa = getattr(app, "fauna", None)
    for a in (fa.animals if fa else []):
        p = getattr(a, "psy", None)
        if p is None:
            continue
        op = life.animals.get(str(p.seed), {})
        if a.sp in ("firefly", "butterfly") and not op.get("name"):
            continue                                   # small life isn't worth listing one by one
        nm = f"{op['name']} the {a.sp}" if op.get("name") else f"a {a.sp}"
        add(f"animal:{p.seed}", "animal", nm, a.x, a.state, named=bool(op.get("name")))
    for b in getattr(app, "bodies", []) or []:
        if b.npc is not None and not b.hidden:
            add(f"npc:{b.npc.id}", "person", f"{b.npc.name} ({b.role})", b.x, b.state)
    out.sort(key=lambda o: o["dist"])
    return out


def _wo_where_animals(app):
    """Where each animal she has named is, wherever it is."""
    life = _lf_life(app)
    fa = getattr(app, "fauna", None)
    here = _rw_here(app)
    lines = []
    for k, op in life.animals.items():
        if not op.get("name"):
            continue
        a = next((x for x in (fa.animals if fa else []) if getattr(x, "psy", None) and str(x.psy.seed) == k), None)
        if a is not None:
            d = (a.x - app.creature.x) * _wo_m(app)
            lines.append(f"{op['name']} the {op['sp']}: here, {abs(d):.0f} m to your {'right' if d > 0 else 'left'}, {a.state}")
            continue
        stash = getattr(fa, "_stash", None) or []
        if any(getattr(x, "psy", None) and str(x.psy.seed) == k for x in stash):
            lines.append(f"{op['name']} the {op['sp']}: back in your valley")
        elif fa and any(str(wv[2].seed) == k for wv in fa.away):
            lines.append(f"{op['name']} the {op['sp']}: off somewhere beyond the valley (it comes and goes)")
        else:
            lines.append(f"{op['name']} the {op['sp']}: you haven't seen it for a while")
    return lines


def world_brief(app):
    cr = app.creature
    here = _rw_here(app)
    life = _lf_life(app)
    snap = world_snapshot(app)
    m = _wo_m(app)
    wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
    lines = [f"- where you are: {_wo_place_name(*here)}, {cr.x * m:.0f} m from its west edge"
             f" (it is {app.world.w * m:.0f} m across)"]
    near = [o for o in snap if o["kind"] not in ("animal", "person")][:7]
    if near:
        lines.append("- closest places, nearest first: " + "; ".join(
            f"{o['name']} ({o['dist']:.0f} m {o['side']}{', ' + o['state'] if o['state'] else ''})" for o in near))
    beings = [o for o in snap if o["kind"] in ("animal", "person")][:6]
    if beings:
        lines.append("- living things near you: " + "; ".join(
            f"{o['name']} ({o['dist']:.0f} m {o['side']}, {o['state']})" for o in beings))
    named = _wo_where_animals(app)
    if named:
        lines.append("- your animals: " + "; ".join(named))
    regions = getattr(app, "_regions", None) or []
    if here in regions:
        i = regions.index(here)
        west = regions[i - 1] if i > 0 else None
        east = regions[i + 1] if i + 1 < len(regions) else None
        lines.append("- the way on: " + ", ".join(x for x in (
            f"west leads to {_wo_place_name(*west)}" if west else "", f"east leads to {_wo_place_name(*east)}" if east else "") if x))
    if here[0] != "valley":
        lines.append("- home: your valley" + (f" ({'hut' if life.home and life.home['stage'] >= 3 else 'shelter'} there)" if life.home else ""))
    if wx:
        lines.append(f"- weather: {wx.get('state', 'clear')}, about {wx.get('temp', 15):.0f} C, "
                     f"wind {'strong' if wx.get('wind', 0) > 0.6 else 'light' if wx.get('wind', 0) < 0.25 else 'moderate'}; "
                     f"it is {app.world.daypart}")
    inv = {k: v for k, v in (getattr(app, "survival", None).inv if getattr(app, "survival", None) else life.inv).items() if v}
    if inv or getattr(life, "coins", 0) or getattr(life, "possessions", None):
        lines.append("- you carry: " + ", ".join(f"{v} {k}" for k, v in inv.items() if k != "bow")
                     + (" and a bow" if inv.get("bow") else "") + (f"; {life.coins} coins" if getattr(life, "coins", 0) else "")
                     + (f"; you own {', '.join(life.possessions)}" if getattr(life, "possessions", None) else ""))
    plan = getattr(life, "plan", None)
    cmd = getattr(life, "command", None)
    if cmd:
        lines.append(f"- what you are doing: {cmd['text']}")
    elif getattr(life, "journey", None) is not None and regions:
        lines.append(f"- what you are doing: travelling to {_wo_place_name(*regions[life.journey])}")
    elif plan:
        lines.append(f"- what you are doing: {_ag_describe(plan['steps'][plan['i']:])}")
    ack = getattr(app.brain.mind, "_cmd_ack", None)
    if ack and _ct_time.time() - getattr(app.brain.mind, "_cmd_ack_t", 0) < 30:
        lines.append(f"- just now: {ack}")
    lines.append("- answer anything about places, distances, animals, objects, weather or what you are doing from "
                 "THIS list only; if something isn't on it, you don't know it - never invent places or objects")
    return "\n".join(lines)


_wo_prev_sys = Brain.build_system_prompt


def _wo_sys(self, decision, recalled, perception):
    text = _wo_prev_sys(self, decision, recalled, perception)
    try:
        app = getattr(self.mind, "_app_ref", None)
        if app is None:
            return text
        block = "--- the world around you right now (ground truth) ---\n" + world_brief(app)
        marker = "--- how to reply ---"
        return text.replace(marker, block + "\n" + marker, 1) if marker in text else text + "\n" + block
    except Exception:
        traceback.print_exc()
        return text


Brain.build_system_prompt = _wo_sys


# ============================================================================
# Spoken requests -> intentions
# ============================================================================

def _wo_resolve(app, phrase):
    """A phrase ('home', 'the fire', 'Ridgebrook', 'the dog', 'there') ->
    (region, x or None, description) using the live world."""
    life = _lf_life(app)
    phrase = phrase.lower().strip()
    regions = getattr(app, "_regions", None) or []
    here = _rw_here(app)
    if phrase in ("there", "that place", "it"):
        last = getattr(app.brain.mind, "_last_place", None)
        if last:
            phrase = last.lower()
    if any(k in phrase for k in ("home", "hut", "shelter", "lean-to", "bed")):
        hx = life.home["x"] if life.home else None
        return ("valley", "valley"), hx, "home" + (" to your hut" if life.home else " to the valley")
    for kind, name in regions:
        if name.lower() in phrase and kind == "settlement":
            return (kind, name), None, f"to {name}"
    if "valley" in phrase:
        return ("valley", "valley"), None, "back to the valley"
    if "fire" in phrase:
        f = _wo_objects(app).nearest_fire(here, app.creature.x)
        if f is None:
            f = next(iter(_wo_objects(app).fires_in(("valley", "valley"))), None)
        if f is not None:
            return f.region, f.x, "to your campfire"
    for key, kind in (("spring", "water"), ("water", "water"), ("well", "water"), ("berr", "food"),
                      ("market", "food"), ("tavern", "shelter"), ("inn", "shelter")):
        if key in phrase:
            p = app.world.poi(kind)
            if p is not None:
                return here, p.x, f"to {p.name}"
    fa = getattr(app, "fauna", None)
    for a in (fa.animals if fa else []):
        p = getattr(a, "psy", None)
        if p is None:
            continue
        op = life.animals.get(str(p.seed), {})
        if a.sp in phrase or (op.get("name") and op["name"].lower() in phrase):
            return here, a.x, f"to {op.get('name') or 'the ' + a.sp}"
    for b in getattr(app, "bodies", []) or []:
        if b.npc is not None and b.npc.name.split()[0].lower() in phrase:
            return here, b.x, f"to {b.npc.name}"
    return None


_WO_GO = _wo_re.compile(r"\b(?:let'?s|let us|go|head|walk|come|take (?:us|me)|get|travel|return)\b(?:\s+(?:back|over|on|off|now|straight|home))*\s*(?:to|toward|towards|into|for)?\s*(the\s+)?(?P<dest>[a-z' -]{2,30})", _wo_re.I)


def _wo_parse(app, text):
    t = text.lower()
    if _wo_re.search(r"\b(stop|stay( here| put)?|wait( here)?|hold on)\b", t) and len(t) < 40:
        return {"kind": "stay", "text": "staying put where you are, as asked"}
    if _wo_re.search(r"\b(light|make|build|start)\b.{0,12}\bfire\b", t):
        return {"kind": "goal", "goal": "fire", "text": "building a fire, as asked"}
    if _wo_re.search(r"\b(go to (sleep|bed)|get some (sleep|rest)|rest now|sleep now)\b", t):
        return {"kind": "goal", "goal": "sleep", "text": "going to sleep, as asked"}
    if _wo_re.search(r"\b(eat something|get something to eat|go eat|have (some )?food)\b", t):
        return {"kind": "goal", "goal": "eat", "text": "getting something to eat, as asked"}
    if _wo_re.search(r"\b(go home|head home|let'?s go home|go back home|come home|take (us|me) home)\b", t):
        dest = "home"
    elif _wo_re.search(r"\b(go|head|walk|let'?s go)\b.{0,10}\bthere\b", t):
        dest = "there"
    elif _wo_re.search(r"\b(find|check on|look for|go to|go and see)\b", t) or _wo_re.search(r"\b(go|head|walk|travel)\b", t):
        mt = _WO_GO.search(t) or _wo_re.search(r"\b(?:find|check on|look for|go and see)\s+(?:the\s+)?(?P<dest>[a-z' -]{2,30})", t)
        dest = mt.group("dest") if mt else None
    else:
        return None
    if not dest:
        return None
    r = _wo_resolve(app, dest)
    if r is None:
        return None
    region, x, desc = r
    return {"kind": "goto", "region": tuple(region), "x": x, "text": f"going {desc}, as asked"}


_wo_prev_on_user = Brain.on_user_message


def _wo_on_user(self, text):
    app = getattr(self.mind, "_app_ref", None)
    if app is not None:
        try:
            for kind, name in getattr(app, "_regions", []) or []:        # remember the last place mentioned
                if kind == "settlement" and name.lower() in text.lower():
                    self.mind._last_place = name
            if "home" in text.lower():
                self.mind._last_place = "home"
            cmd = _wo_parse(app, text)
            if cmd is not None:
                life = _lf_life(app)
                urgent = life.phys["bladder"] > 0.95 or app.brain.mind.risk.risk > 0.85
                if urgent:
                    self.mind._cmd_ack = f"the user asked you to {cmd['text'].split(',')[0].replace('going ', 'go ')}; you'll do it in a moment, something urgent first"
                cmd["t0"] = life.clock
                life.command = cmd
                life.plan = None
                if cmd["kind"] == "goto":
                    regions = getattr(app, "_regions", [])
                    if cmd["region"] != _rw_here(app) and cmd["region"] in regions:
                        life.journey = regions.index(cmd["region"])
                if not urgent:
                    self.mind._cmd_ack = f"the user asked and you agreed: you are now {cmd['text'].replace(', as asked', '')}"
                self.mind._cmd_ack_t = _ct_time.time()
        except Exception:
            traceback.print_exc()
    return _wo_prev_on_user(self, text)


Brain.on_user_message = _wo_on_user

# commands outrank her own wishes while they last (planner candidates)
_wo_prev_plan_adjust = _m41_plan_adjust


def _wo_plan_adjust(sv, app, life, cand):
    _wo_prev_plan_adjust(sv, app, life, cand)
    cmd = getattr(life, "command", None)
    if not cmd:
        return
    if life.clock - cmd.get("t0", life.clock) > 300:
        life.command = None
        return
    if cmd["kind"] == "stay":
        for k in list(cand):
            u, t = cand[k]
            cand[k] = (u - 0.8, t)
        cand["cmd"] = (1.2, ("goto", app.creature.x))
    elif cmd["kind"] == "goal":
        g = cmd["goal"]
        if g in cand:
            u, t = cand[g]
            cand[g] = (u + 1.5, t)
        elif g == "fire":
            trees = getattr(app.world, "_tree_x", None) or [app.creature.x]
            cand["fire"] = (1.5, ("wood", min(trees, key=lambda t: abs(t - app.creature.x))))
        elif g == "sleep":
            cand["sleep"] = (1.5, ("sleep", app.creature.x))
        s = _ag_state(app, sv, life)
        if (g == "fire" and s.get("fire")) or (g == "sleep" and life.phys["sleep_pressure"] < 0.1) or \
                (g == "eat" and app.brain.goals.hunger < 0.1):
            life.command = None
    elif cmd["kind"] == "goto":
        if cmd["region"] == _rw_here(app):
            if cmd.get("x") is None or abs(app.creature.x - cmd["x"]) < 1.6 * app.creature._Hb():
                app.brain.perceive(Event("social", f"did what they asked: {cmd['text'].replace(', as asked', '')}",
                                         salience=0.45, valence=0.25))
                life.command = None
            else:
                cand["cmd"] = (1.6, ("goto", cmd["x"]))


_m41_plan_adjust = _wo_plan_adjust

_wo_prev_goal_facts = _ag_goal_facts


def _wo_goal_facts(name, s):
    if name == "cmd":
        return None
    return _wo_prev_goal_facts(name, s)


_ag_goal_facts = _wo_goal_facts

_wo_prev_act = Survival._act


def _wo_act(self, app, dt):
    t = self.task
    if t and t[0] == "goto":
        cr = app.creature
        if abs(cr.x - t[1]) > 18:
            cr.set_target(t[1], cr.y)
        else:
            self.task = None
        return
    return _wo_prev_act(self, app, dt)


Survival._act = _wo_act


# ---- per-frame: the registry owns fires ------------------------------------------
_wo_prev_update = App._update_world


def _wo_update(self, dt):
    ob = _wo_objects(self)
    ob.frame += 1
    Campfire._frame_now = ob.frame
    sv = getattr(self, "survival", None)
    here = _rw_here(self)
    if sv is not None:
        # the fire she uses is the nearest real one where she is - never a copy
        sv.fire = ob.nearest_fire(here, self.creature.x, lit_only=True) or ob.nearest_fire(here, self.creature.x)
    before = sv.fire if sv is not None else None
    _wo_prev_update(self, dt)
    try:
        if sv is not None and sv.fire is not None and getattr(sv.fire, "oid", None) is None:
            sv.fire = ob.adopt_fire(sv.fire, here)                    # built this frame
            f = sv.fire
            if getattr(f, "relit", 0):
                self.brain.perceive(Event("survival", "relit my old fire", salience=0.45, valence=0.3))
            try:
                self.brain.knowledge.see("place", f"campfire {f.oid}", valence=0.3,
                                         note=f"{_wo_place_name(*here)}, {f.x * _wo_m(self):.0f} m in")
            except Exception:
                pass
        wx = self.weather_sim.snapshot() if getattr(self, "weather_sim", None) else {}
        for f in list(ob.fires.values()):
            f.update(dt, wx)                                          # every fire burns, wherever it is
            if abs(f.x - self.creature.x) < 12 * self.creature._Hb() and f.region == here:
                f.known = True
        if ob.frame % 300 == 0:
            ob.prune()
    except Exception:
        traceback.print_exc()


App._update_world = _wo_update
