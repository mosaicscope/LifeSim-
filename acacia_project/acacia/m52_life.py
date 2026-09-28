# ============================================================================
# [NEW] A LIFE THAT MOVES - destinations, investigation, physical food,
#       friends who visit, a truthful decision display, less noise
# ============================================================================
#
# Cleanup pass on the existing systems (no new renderer, no new AI layer):
#   * real destinations in each region (grove, glade, warren, meadow, paths,
#     lookout, town squares...) that she remembers visiting; animals live in
#     habitats (rabbits by the warren, deer on the meadow)
#   * purposeful candidates in the SAME utility planner: explore somewhere
#     she hasn't been lately, investigate an animal she noticed, go to town
#     every so often, greet a visitor, visit a friend in town
#   * sitting is governed: after she has sat down she won't sit again for a
#     few minutes unless she is actually tired; watching an animal is done
#     standing still
#   * food is physical: walk to the bush -> inspect -> pick with her hand ->
#     carry -> eat hand to mouth, bite by bite; food left out is placed with
#     a reach to the ground, and animals sniff before they eat
#   * friends come to her: people from the settlements decide to visit, walk
#     in, wave and call out, talk (topics from what actually happened to her
#     or to them), bring something, disagree, invite her, and leave
#   * a truthful decision record (goal, action, target, reason, need,
#     memory, priority) written only by the planner's actual choice and the
#     body's actual state, shown under the WORLD toolbar
#   * less noise: fewer idle thoughts, less rain clutter, fewer insects

import math as _lv_math
import random as _lv_random
import time as _lv_time

_LV_TOWN_EVERY = 540.0              # s of her time: she wants town again after this
_LV_VISIT_CHECK = 45.0              # s: how often people consider visiting her

# ---- less noise -------------------------------------------------------------
for _sp, _cap in (("butterfly", 2), ("firefly", 4), ("bird", 2)):
    if _sp in FAUNA:
        FAUNA[_sp]["cap"] = min(FAUNA[_sp].get("cap", _cap), _cap)

_lv_prev_thought_tick = ThoughtStream.tick


def _lv_thought_tick(self, brain, mind, dt):
    # ambient musings at most every ~1.5-3 min; event thoughts (plans,
    # surprises) are emitted directly and are unaffected
    now = brain.age_seconds
    if now < getattr(self, "_lv_next", 0.0):
        return None
    r = _lv_prev_thought_tick(self, brain, mind, dt)
    if r:
        self._lv_next = now + _lv_random.uniform(90.0, 180.0)
    return r


ThoughtStream.tick = _lv_thought_tick


# ============================================================================
# Destinations
# ============================================================================

def _lv_build_places(world):
    kind = getattr(world, "_region_kind", "valley")
    region = getattr(world, "_region_name", "valley")
    W = world.w
    out = []

    def add(pid, name, k, x):
        out.append({"id": f"{region}:{pid}", "name": name, "kind": k, "x": clamp(x, 70, W - 70)})
    for p in getattr(world, "pois", []):
        add(p.kind, p.name, p.kind, p.x)
    if kind == "valley":
        trees = sorted(getattr(world, "_tree_x", None) or [])
        if trees:
            dens = max(trees, key=lambda t: sum(1 for u in trees if abs(u - t) < WS.m(12)))
            add("grove", "the old pine grove", "woodland", dens)
            gaps = [(b - a, (a + b) / 2) for a, b in zip(trees, trees[1:])]
            if gaps:
                add("glade", "the sunny glade", "clearing", max(gaps)[1])
        add("warren", "the rabbit warren", "habitat", W * 0.2)
        add("meadow", "the deer meadow", "habitat", W * 0.64)
        add("west", "the west path", "path", 80)
        add("east", "the east path", "path", W - 80)
    elif kind == "road":
        add("lookout", "the lookout rock", "landmark", W * 0.5)
        add("verge", "the roadside thicket", "woodland", W * 0.3)
    else:
        P = getattr(world, "_places", {}) or {}
        for key, nm in (("market", "the market square"), ("tavern", "the tavern"), ("shrine", "the shrine"),
                        ("hall", "the hall"), ("well", "the well")):
            if isinstance(P.get(key), (int, float)):
                add(key, f"{nm} of {region}", "town", P[key])
    return out


_lv_prev_rebuild = World.rebuild


def _lv_rebuild(self, *a, **k):
    r = _lv_prev_rebuild(self, *a, **k)
    try:
        self._dest = _lv_build_places(self)
        if getattr(self, "_region_kind", "valley") == "valley":       # habitats you can see
            c, add, G = self.c, self._add, self.ground
            lit = self.light()
            dim = lambda col: _mix_hex(col, "#0b1018", 0.45 - 0.35 * lit)
            for d in self._dest:
                x = d["x"]
                if d["id"].endswith(":warren"):
                    for k2 in range(3):
                        mx = x + (k2 - 1) * WS.m(1.1)
                        add(c.create_oval(mx - WS.m(0.45), G - WS.m(0.2), mx + WS.m(0.45), G + WS.m(0.12),
                                          fill=dim("#6b5238"), outline="", tags="world"))
                        add(c.create_oval(mx - WS.m(0.12), G - WS.m(0.06), mx + WS.m(0.12), G + WS.m(0.06),
                                          fill=dim("#221812"), outline="", tags="world"))
                elif d["id"].endswith(":meadow"):
                    rnd = _lv_random.Random(int(x))
                    for _ in range(18):
                        gx = x + WS.m(rnd.uniform(-4, 4))
                        hgt = WS.m(rnd.uniform(0.3, 0.55))
                        add(c.create_line(gx, G + 2, gx + rnd.uniform(-2, 2), G + 2 - hgt, fill=dim("#7a8a3a"),
                                          width=1, tags="world"))
                elif d["id"].endswith(":glade"):
                    add(c.create_oval(x - WS.m(3.5), G - WS.m(0.05), x + WS.m(3.5), G + WS.m(0.35),
                                      fill=dim("#5f7a3e"), outline="", tags="world"))
                    add(c.create_polygon(x + WS.m(1.2), G, x + WS.m(1.2), G - WS.m(0.35), x + WS.m(1.75), G - WS.m(0.35),
                                         x + WS.m(1.75), G, fill=dim("#6a4a30"), outline="", tags="world"))   # a stump
    except Exception:
        traceback.print_exc()
    return r


World.rebuild = _lv_rebuild


def _lv_dests(app):
    return getattr(app.world, "_dest", None) or []


# animals live somewhere: rabbits by the warren, deer on the meadow
_lv_prev_animal_init = Animal.__init__


def _lv_animal_init(self, species, x, y, rng, juvenile=False):
    _lv_prev_animal_init(self, species, x, y, rng, juvenile)
    p = getattr(self, "psy", None)
    hab = {"rabbit": "warren", "deer": "meadow", "fox": "grove"}.get(species)
    if p is not None and hab and p.home is None:
        p._habitat = hab


Animal.__init__ = _lv_animal_init
_lv_prev_drive = Psyche.drive


def _lv_drive(self, a, fa, world, jane, dt):
    hab = getattr(self, "_habitat", None)
    if hab and self.home is None:
        d = next((x for x in getattr(world, "_dest", []) if x["id"].endswith(":" + hab)), None)
        if d is not None:
            self.home = d["x"]
    return _lv_prev_drive(self, a, fa, world, jane, dt)


Psyche.drive = _lv_drive


# ============================================================================
# The decision record: written only by what she actually chose and does
# ============================================================================

def _lv_life(app):
    life = _lf_life(app)
    for k, v in (("visits", {}), ("invites", {}), ("sits", []), ("decision", None), ("last_town", None),
                 ("investigated", {})):
        if not hasattr(life, k):
            setattr(life, k, v if not isinstance(v, (dict, list)) else type(v)())
    return life


def _lv_name_of(app, name, task):
    """Human-readable goal + target for a planner candidate name."""
    life = _lf_life(app)
    fa = getattr(app, "fauna", None)
    regions = getattr(app, "_regions", []) or []

    def animal(seed):
        a = next((o for o in (fa.animals if fa else []) if getattr(o, "psy", None) and str(o.psy.seed) == str(seed)), None)
        if a is None:
            return None, "an animal"
        op = life.opinion(a.psy)
        return a, (op["name"] or f"the {a.sp}")
    base, _, arg = name.partition(":")
    if base == "explore" and arg:
        d = next((x for x in _lv_dests(app) if x["id"] == arg), None)
        return (f"Explore {d['name']}" if d else "Explore"), (d["name"] if d else "somewhere new")
    if base == "investigate":
        a, nm = animal(arg)
        return f"Investigate {nm}", nm
    if base in ("watch", "leave", "pet", "offer"):
        a, nm = animal(arg)
        return {"watch": f"Watch {nm} quietly", "leave": f"Leave food for {nm}", "pet": f"Greet {nm}",
                "offer": f"Feed {nm} by hand"}[base], nm
    if base in ("greet", "visit", "help"):
        soc = getattr(app, "society", None)
        n = soc.npcs.get(arg) if soc else None
        nm = n.name if n else "someone"
        return {"greet": f"Greet {nm}", "visit": f"Visit {nm}", "help": f"Help {nm}"}[base], nm
    if base == "journey" and arg.isdigit() and int(arg) < len(regions):
        kind, rn = regions[int(arg)]
        if kind == "valley":
            return "Go home to the valley", "the valley"
        return (f"Visit {rn}" if kind == "settlement" else f"Walk the road to {rn}"), rn
    table = {"fire": ("Light a fire", "firesite"), "fire_cook": ("Cook a proper meal", "the fire"),
             "cook": ("Cook food", "the fire"), "eat": ("Eat", "the berries she carries"),
             "berries": ("Pick berries", "the berry thicket"), "hunt": ("Hunt", "prey"),
             "sleep": ("Sleep", "bed"), "home": ("Work on her home", "the hut"), "repair": ("Repair the hut", "the hut"),
             "relieve": ("Relieve herself", "the bushes"), "wash": ("Wash", "the water"),
             "warm": ("Warm up", "the fire"), "market": ("Trade at the market", "the market"),
             "cmd": ("Do what was asked", "as asked"), "check": ("Look for a friend", "a friend"),
             "favourite": ("Go to a favourite spot", "a favourite spot"), "trade": ("Trade with the traveller", "the traveller")}
    g, t = table.get(base, (base.capitalize(), ""))
    return g, t


def _lv_reason(app, name):
    """The need or cause that actually made this candidate win."""
    b, life = app.brain, _lf_life(app)
    g, P = b.goals, life.phys
    base = name.split(":")[0]
    if base in ("eat", "cook", "berries", "fire_cook", "hunt"):
        return f"Hungry ({g.hunger:.0%})", "hunger"
    if base == "sleep":
        return f"Tired (sleep pressure {P['sleep_pressure']:.0%})", "sleep"
    if base in ("fire", "warm"):
        return f"Cold ({b.mind.comfort.cold:.0%})" if b.mind.comfort.cold > 0.15 else "Evening coming - wants a fire", "warmth"
    if base == "relieve":
        return "Needs a moment behind the trees", "bladder"
    if base == "wash":
        return f"Feels grubby ({1 - P['hygiene']:.0%})", "hygiene"
    if base in ("home", "repair"):
        return "Wants a proper place to live", "shelter"
    if base in ("greet", "visit") or (base == "journey" and _lv_social_reason(app)):
        mins = (life.clock - getattr(life, "_lv_social_t", 0.0)) / 60.0
        return (f"Hasn't talked to anyone in {mins:.0f} min" if mins > 3 else "Enjoys the company"), "social"
    if base == "journey":
        return "Wants to see the town and its people", "stimulation"
    if base in ("explore", "investigate"):
        return (f"Curious ({b.emotion.curiosity:.0%}), restless ({g.stimulation:.0%})"), "curiosity"
    if base in ("watch", "leave", "pet", "offer"):
        return "Wants the animal to trust her", "curiosity"
    if base == "cmd":
        return "You asked her to", "request"
    return "It seemed the most worthwhile thing to do", "—"


def _lv_social_reason(app):
    return app.brain.goals.social > 0.45


def _lv_memory_for(app, target, goal):
    """A real memory mentioning the target (or the kind of thing), or nothing."""
    keys = [w.lower() for w in (target or "").replace("the ", "").split()[:2] if len(w) > 2]
    for m in reversed(list(app.brain.memory.long_term)[-80:]):
        t = m.text.lower()
        if any(k in t for k in keys):
            return m.text.split(" (")[0][:70]
    return "—"


_lv_prev_plan = Survival._plan


def _lv_plan(self, app, wx):
    r = _lv_prev_plan(self, app, wx)
    try:
        life = _lv_life(app)
        name = getattr(self, "_cand", None) if self.task else None
        dec = life.decision or {}
        if name and name != dec.get("name"):
            goal, target = _lv_name_of(app, name, self.task)
            reason, need = _lv_reason(app, name)
            util = (getattr(self, "_lv_cands", {}) or {}).get(name, (None,))[0]
            life.decision = {"name": name, "goal": goal, "target": target, "reason": reason, "need": need,
                             "memory": _lv_memory_for(app, target, goal),
                             "priority": round(float(util), 2) if util is not None else None,
                             "since": life.clock}
        elif not self.task and dec:
            life.decision = None
    except Exception:
        traceback.print_exc()
    return r


Survival._plan = _lv_plan


def _lv_action(app):
    """What her body is actually doing right now."""
    cr, sv = app.creature, getattr(app, "survival", None)
    life = _lf_life(app)
    L = cr._loco
    moving = abs(L.vx) > 0.15 * WS.px
    sitting = getattr(L, "sit", 0.0) > 0.5
    t = sv.task if sv else None
    phase = getattr(sv, "_lv_phase", None) if sv else None
    dec = getattr(life, "decision", None) or {}
    tgt = dec.get("target", "")
    if getattr(life, "sleeping", False):
        return "Sleeping"
    if phase:
        return phase
    if moving:
        return f"{'Hurrying' if abs(L.vx) > 1.6 * WS.px else 'Walking'} to {tgt}" if tgt else "Walking"
    if sitting:
        return "Sitting"
    if t:
        return {"wood": "Gathering wood", "build": "Building a fire", "cook": "Cooking", "homebuild": "Building",
                "repair": "Repairing the hut", "wash": "Washing", "sell": "Trading", "watch": f"Watching {tgt}",
                "investigate": f"Looking at {tgt}", "talk": f"Talking with {tgt}", "leave": "Setting food down",
                "pet": f"Reaching out to {tgt}", "craft": "Making a bow", "hunt": "Hunting"}.get(t[0], "Standing")
    return "Standing, looking around"


# ============================================================================
# Purposeful candidates
# ============================================================================

_lv_prev_plan_adjust = _m41_plan_adjust


def _lv_plan_adjust(sv, app, life, cand):
    _lv_prev_plan_adjust(sv, app, life, cand)
    life = _lv_life(app)
    cr, b, world = app.creature, app.brain, app.world
    g, tr = b.goals, b.personality.traits
    here = _rw_here(app)
    dark = world.daypart in ("evening", "night")
    cur = tr.get("curiosity", 0.6)
    # patient watching sits her down: keep it for when trust-building needs it
    for k in list(cand):
        if k.startswith("watch:"):
            u, t = cand[k]
            cand[k] = (u * 0.5, t)
    # 1. explore: places she hasn't seen lately
    if not dark:
        idle_t = life.clock - getattr(life, "_lv_busy_t", life.clock)
        for d in _lv_dests(app):
            v = life.visits.get(d["id"], {"n": 0, "last": -1e9})
            since = life.clock - v["last"]
            if since < 120:
                continue
            dist_m = abs(d["x"] - cr.x) / WS.px
            if dist_m < 4:
                continue
            nov = 1.0 / (1.0 + 0.6 * v["n"])
            u = (0.2 + 0.45 * cur) * (0.35 + g.stimulation) * nov * min(1.0, since / 300.0) \
                + 0.15 * min(1.0, idle_t / 45.0) - 0.004 * dist_m
            if d["kind"] == "habitat":
                u += 0.08
            if u > 0.12:
                cand[f"explore:{d['id']}"] = (u, ("explore", d["x"]))
    # 2. investigate an animal she notices (moving, new, or one she knows)
    fa = getattr(app, "fauna", None)
    for a in (fa.animals if fa else []):
        p = getattr(a, "psy", None)
        if p is None or a.sp in ("butterfly", "firefly") or a.S.get("flyer"):
            continue
        dist_m = abs(a.x - cr.x) / WS.px
        if dist_m > 30 or dist_m < 3:
            continue
        if life.clock - life.investigated.get(str(p.seed), -1e9) < 150:
            continue
        op = life.opinion(p)
        moving = abs(a.vx) > 0.2 * WS.px
        u = 0.2 + 0.5 * cur * (1.0 - op["fam"]) + (0.2 if moving else 0.0) + (0.25 if op.get("name") else 0.0)
        if a.S.get("danger"):
            u -= 0.5
        fid = (wild_fid(a) or (WS.m(6.0), 0))[0]
        stand = a.x + (1 if cr.x > a.x else -1) * max(WS.m(3.0), fid * 1.25)
        cand[f"investigate:{p.seed}"] = (u, ("investigate", clamp(stand, 60, world.w - 60)))
    # 3. town, on a real rhythm
    regions = getattr(app, "_regions", []) or []
    if here[0] == "valley" and not dark and regions:
        since = life.clock - (life.last_town if life.last_town is not None else -1e9)
        near = [(abs(i - regions.index(here)), i) for i, (k, n) in enumerate(regions) if k == "settlement"
                and (getattr(app, "society", None) and app.society.sets.get(n) and app.society.sets[n].alive
                     and not app.society.sets[n].war)]
        if near:
            _dist, idx = min(near)
            name = regions[idx][1]
            inv = 0.35 if life.clock - life.invites.get(name, -1e9) < 600 else 0.0
            u = 0.08 + 0.3 * g.social + 0.15 * g.stimulation + inv + (0.3 if since > _LV_TOWN_EVERY else 0.0)
            key = f"journey:{idx}"
            cand[key] = (max(cand.get(key, (0.0, None))[0], u), ("travel", idx))
    # 4. people: a visitor who called out; friends in town
    for tv in getattr(app, "travellers", []) or []:
        if getattr(tv, "kind", "") == "visitor" and tv.npc is not None and tv.called and not tv.talked:
            cand[f"greet:{tv.npc.id}"] = (1.0 + 0.4 * g.social, ("talk", tv.x))
    for bd in getattr(app, "bodies", []) or []:
        if bd.npc is None or bd.hidden or getattr(bd, "scene", None) is not None:
            continue
        p = getattr(life, "people", {}).get(bd.npc.id)
        if p and p.get("like", 0) > 0.05 and life.clock - p.get("talked", -1e9) > 240:
            cand[f"visit:{bd.npc.id}"] = (0.3 + 0.6 * g.social + 0.3 * p["like"], ("talk", bd.x))
        elif p is None and bd.npc.t.get("sociability", 0.5) > 0.5 and abs(bd.x - cr.x) < WS.m(14) \
                and life.clock - getattr(life, "_lv_meet_t", -1e9) > 120:
            # a stranger in town who seems open to talking: strike up a conversation
            cand[f"visit:{bd.npc.id}"] = (0.25 + 0.5 * g.social * (0.5 + tr.get("friendliness", 0.5)), ("talk", bd.x))
    sv._lv_cands = dict(cand)


_m41_plan_adjust = _lv_plan_adjust

_lv_prev_decide = _m42_decide


def _lv_decide(sv, app, life, cand, task):
    if cand:
        top = max(cand, key=lambda k: cand[k][0])
        # a journey in progress yields to something clearly more pressing
        # (hunger, a visitor calling...), and resumes afterwards
        j = getattr(life, "journey", None)
        if j is not None and not top.startswith("journey:"):
            ju = cand.get(f"journey:{j}", (0.3, None))[0]
            if cand[top][0] > ju + 0.25:
                if top.startswith(("explore:", "investigate:", "greet:", "visit:", "watch:", "leave:", "cmd", "call:")):
                    return None
                return _rw_prev_decide(sv, app, life, cand, task)        # plan it, skipping the journey hop
        if top.startswith(("explore:", "investigate:", "greet:", "visit:")):
            return None                                     # behaviours, not plans: let it run
    return _lv_prev_decide(sv, app, life, cand, task)


_m42_decide = _lv_decide


# ============================================================================
# Doing it: walking with purpose, investigating, talking, physical food
# ============================================================================

def _lv_person(app, sv):
    name = getattr(sv, "_cand", "") or ""
    pid = name.split(":", 1)[1] if ":" in name else None
    for tv in getattr(app, "travellers", []) or []:
        if tv.npc is not None and tv.npc.id == pid:
            return tv, tv.npc
    for bd in getattr(app, "bodies", []) or []:
        if bd.npc is not None and bd.npc.id == pid:
            return bd, bd.npc
    return None, None


def _lv_talk(app, sv, who_obj, npc, dt):
    """A real exchange: topics from what actually happened, gifts, disagreement, invitations."""
    life = _lv_life(app)
    b = app.brain
    sv._lv_talk_t = getattr(sv, "_lv_talk_t", 0.0) + dt
    who_obj.talking = True
    tt = sv._lv_talk_t
    sv._lv_phase = f"Talking with {npc.name.split()[0]}"
    p = life.__dict__.setdefault("people", {}).setdefault(npc.id, {"name": npc.name, "from": npc.sett, "met": 0, "like": 0.0})
    if tt < dt * 1.5:                                           # the opening: what they remember
        p["met"] += 1
        last = next((m[1] for m in reversed(npc.mem) if "talked with Jane about" in m[1]), None)
        if last:
            b.perceive(Event("social", f"{npc.name.split()[0]} remembered we {last.replace('talked with Jane about', 'talked about')}",
                             salience=0.5, valence=0.3))
    if 6.0 <= tt < 6.0 + dt * 1.5:                              # the topic: something real
        topics = [m.text.split(" (")[0] for m in list(b.memory.long_term)[-25:]
                  if any(k in m.text for k in ("fox", "deer", "rabbit", "dog", "hut", "fire", "berries", "raiders", "market"))]
        soc = getattr(app, "society", None)
        news = [e[3] for e in (soc.events[-8:] if soc else []) if e[1] == npc.sett and e[4] >= 0.5]
        # a topic is a THING that happened, phrased as one
        nouns = {"fox": "the fox", "deer": "the deer", "rabbit": "the rabbits", "dog": "the dog", "hut": "my hut",
                 "fire": "my campfire", "berries": "the berry thicket", "raiders": "the raiders", "market": "the market"}
        topic = next((nouns[k] for k in nouns if topics and k in topics[-1]), None) or \
            (news[-1] if news else "the weather")
        npc.remember(soc.day if soc else 0.0, f"talked with Jane about {topic[:40]}", 0.3)
        disagree = abs(npc.t.get("aggression", 0.5) - (1 - b.personality.traits.get("agreeableness", 0.5))) > 0.45 \
            and _lv_random.random() < 0.35
        if disagree:
            p["like"] = clamp(p["like"] - 0.05, -1, 1)
            b.perceive(Event("social", f"{npc.name.split()[0]} and I disagreed about {topic[:40]}", salience=0.5, valence=-0.2))
        else:
            p["like"] = clamp(p["like"] + 0.08, -1, 1)
            b.perceive(Event("social", f"talked with {npc.name.split()[0]} about {topic[:40]}", salience=0.5, valence=0.35))
    if 14.0 <= tt < 14.0 + dt * 1.5:                            # a gift or an invitation
        kind = npc.__dict__.get("kindness", 0.5)
        if npc.wealth > 3 and kind > 0.45 and _lv_random.random() < 0.6:
            gift = _lv_random.choice(("berries", "wood"))
            sv.inv[gift] = sv.inv.get(gift, 0) + 2
            npc.wealth -= 1
            b.perceive(Event("social", f"{npc.name.split()[0]} brought me some {gift}", salience=0.55, valence=0.45))
        elif _lv_random.random() < 0.5:
            life.invites[npc.sett] = life.clock
            b.perceive(Event("social", f"{npc.name.split()[0]} invited me to come to {npc.sett}", salience=0.55, valence=0.35))
    if tt > 22.0:
        life._lv_meet_t = life.clock
        npc.rel["jane"] = clamp(npc.rel.get("jane", 0.0) + 0.2, -1, 1)
        p["talked"] = life.clock
        life._lv_social_t = life.clock
        b.goals.satisfy("social", 0.4, f"talked with {npc.name}")
        who_obj.talking = False
        if hasattr(who_obj, "talked"):
            who_obj.talked = True
        sv._lv_talk_t = 0.0
        sv._lv_phase = None
        sv.task = None


_lv_prev_act = Survival._act


def _lv_act(self, app, dt):
    t = self.task
    cr, b = app.creature, app.brain
    life = _lv_life(app)
    self._lv_phase = None
    cr._reach = None
    if t:
        life._lv_busy_t = life.clock
    if not t:
        return _lv_prev_act(self, app, dt)
    kind = t[0]
    if kind != "eat":
        self._lv_bites = 0
    if kind == "explore":
        if abs(cr.x - t[1]) > WS.m(1.2):
            cr.set_target(t[1], cr.y)
            return
        d = min(_lv_dests(app), key=lambda d: abs(d["x"] - cr.x), default=None)
        if d is not None:
            v = life.visits.setdefault(d["id"], {"n": 0, "last": -1e9})
            first = v["n"] == 0
            v["n"] += 1
            v["last"] = life.clock
            if first:
                b.perceive(Event("place", f"found {d['name']}", salience=0.55, valence=0.3))
            b.goals.satisfy("stimulation", 0.2, f"explored {d['name']}")
        self._lv_look = getattr(self, "_lv_look", 0.0) + dt
        self._lv_phase = f"Looking around {d['name']}" if d else "Looking around"
        if self._lv_look > 4.0:
            self._lv_look = 0.0
            self.task = None
        return
    if kind == "investigate":
        a = next((o for o in (app.fauna.animals if app.fauna else []) if getattr(o, "psy", None)
                  and str(o.psy.seed) == (getattr(self, "_cand", "") or "").split(":")[-1]), None)
        if a is None:
            self.task = None
            return
        fid = (wild_fid(a) or (WS.m(6.0), 0))[0]
        stand = a.x + (1 if cr.x > a.x else -1) * max(WS.m(3.0), fid * 1.25)
        self.task = ("investigate", clamp(stand, 60, app.world.w - 60))
        if abs(cr.x - self.task[1]) > WS.m(1.0) and a.state != "flee":
            cr.set_target(self.task[1], cr.y)
            body = getattr(cr, "_body", None)
            if isinstance(body, dict) and abs(cr.x - a.x) < fid * 2.2:
                body["pace"] = body.get("pace", 1.0) * 0.5                  # slows as she gets close
            return
        cr._loco.facing = 1.0 if a.x > cr.x else -1.0
        self.bias = {"curious": 0.9, "move": -0.8}
        self._lv_look = getattr(self, "_lv_look", 0.0) + dt
        op = life.opinion(a.psy)
        who = op["name"] or f"the {a.sp}"
        self._lv_phase = f"Watching {who} ({a.state})"
        if self._lv_look > 7.0 or a.state == "flee":
            self._lv_look = 0.0
            life.investigated[str(a.psy.seed)] = life.clock
            op["fam"] = clamp01(op["fam"] + 0.08)
            what = {"graze": "grazing", "sniff": "sniffing around", "watch": "watching me back", "flee": "bolting away",
                    "sleep": "asleep", "drink": "drinking", "hunt": "hunting", "wander": "wandering"}.get(a.state, a.state)
            b.perceive(Event("animal", f"went to look at {who}: it was {what}", salience=0.5,
                             valence=-0.05 if a.state == "flee" else 0.25))
            b.goals.satisfy("stimulation", 0.15, f"watched {who}")
            self.task = None
        return
    if kind == "talk":
        who_obj, npc = _lv_person(app, self)
        if who_obj is None:
            self.task = None
            return
        tx = who_obj.x + (1 if cr.x > who_obj.x else -1) * WS.m(1.2)
        self.task = ("talk", tx)
        if abs(cr.x - tx) > WS.m(0.5):
            cr.set_target(tx, cr.y)
            return
        cr._loco.facing = 1.0 if who_obj.x > cr.x else -1.0
        if hasattr(who_obj, "stop"):
            who_obj.stop = max(who_obj.stop, 5.0)
        if hasattr(who_obj, "scene") and who_obj.scene is None:
            who_obj.target = who_obj.x
        self.bias = {"idle": 0.6, "move": -0.8}
        _lv_talk(app, self, who_obj, npc, dt)
        return
    # ---- food: physical, step by step --------------------------------------------------
    if kind == "berries":
        fp = app.world.poi("food")
        if fp is None or not fp.available():
            self.task = None
            return
        if abs(cr.x - fp.x) > WS.m(1.3):
            cr.set_target(fp.x + (1 if cr.x > fp.x else -1) * WS.m(0.9), cr.y)
            return
        cr._loco.facing = 1.0 if fp.x > cr.x else -1.0
        self._lv_f = getattr(self, "_lv_f", 0.0) + dt
        f_ = self._lv_f
        bush = (fp.x, app.world.ground - WS.m(0.8))
        if f_ < 1.5:
            self._lv_phase = "Inspecting the berries"
            cr._reach = (bush[0], bush[1], 0.35)
            if f_ < dt * 1.5 and "berries" not in getattr(life, "_lv_known_food", set()):
                life.__dict__.setdefault("_lv_known_food", set()).add("berries")
                b.perceive(Event("survival", "these red berries look ripe - the same kind as before, safe to eat",
                                 salience=0.45, valence=0.2))
            return
        cyc = (f_ - 1.5) % 1.4
        self._lv_phase = "Picking berries"
        cr._reach = (bush[0], bush[1] + WS.m(0.2) * _lv_math.sin(cyc * 4.5), 0.95 if cyc < 0.9 else 0.4)
        if cyc < dt * 1.2 and f_ > 1.6:
            self.inv["berries"] = self.inv.get("berries", 0) + 1
            if self.inv["berries"] % 2 == 0:
                fp.deplete()
            if self.inv["berries"] >= 3 or not fp.available():
                self._lv_f = 0.0
                self.task = None
                b.perceive(Event("survival", f"picked a handful of berries ({self.inv['berries']})", salience=0.35, valence=0.2))
        return
    if kind == "eat":
        if self.inv.get("berries", 0) <= 0:
            self.task = None
            return
        self._lv_f = getattr(self, "_lv_f", 0.0) + dt
        cyc = self._lv_f % 1.5
        pose = getattr(cr, "_last_pose", None) or cr.__dict__.get("_last_pose")
        mouth = (cr.x + cr._loco.facing * cr._H() * 0.3, pose[3][1] - cr._H() * 0.25) if pose else (cr.x, cr.y - cr._H() * 7)
        self._lv_phase = "Eating berries"
        cr._reach = (mouth[0], mouth[1], 0.95 if cyc < 0.8 else 0.3)
        if cyc < dt * 1.2 and self._lv_f > 0.3:
            self.inv["berries"] -= 1
            b.goals.satisfy("hunger", 0.3, "ate a handful of raw berries")
            self._lv_bites = getattr(self, "_lv_bites", 0) + 1
            if self._lv_bites == 2:                              # a meal, not a nibble: remembered once
                b.perceive(Event("survival", "ate the berries I picked - sweet, a little sour", salience=0.4, valence=0.35))
            if self.inv["berries"] <= 0 or b.goals.hunger < 0.05:
                self._lv_f = 0.0
                self._lv_bites = 0
                self.task = None
        return
    if kind == "leave":
        # reach down and set the food on the ground, then step back (m51 finishes it)
        if abs(cr.x - t[1]) <= WS.m(0.6):
            self._lv_f = getattr(self, "_lv_f", 0.0) + dt
            if self._lv_f < 1.0:
                self._lv_phase = "Setting food down"
                cr._reach = (cr.x + cr._loco.facing * WS.m(0.4), app.world.ground, 0.9)
                self.bias = {"idle": 0.6, "move": -0.8}
                return
            self._lv_f = 0.0
    if kind in ("pet", "offer"):
        a = next((o for o in (app.fauna.animals if app.fauna else []) if getattr(o, "psy", None)
                  and o.psy.seed == getattr(self, "_subject", -1)), None)
        if a is not None and abs(cr.x - a.x) < WS.m(1.6):
            cr._reach = (a.x, app.world.ground - SPECIES.get(a.sp, {}).get("sh", 0.4) * WS.px, 0.9)
            self._lv_phase = "Reaching out to it"
    return _lv_prev_act(self, app, dt)


Survival._act = _lv_act

# animals inspect food before eating it
_lv_prev_wd_drive = Psyche.drive


def _lv_sniff_first(self, a, fa, world, jane, dt):
    r = _lv_prev_wd_drive(self, a, fa, world, jane, dt)
    offs = getattr(fa, "_offerings", None) or []
    if a.state == "graze" and offs:
        o = min(offs, key=lambda o: abs(o["x"] - a.x))
        if abs(o["x"] - a.x) < WS.m(0.6):
            s = o.setdefault("sniffed", {})
            k = str(self.seed)
            s[k] = s.get(k, 0.0) + dt
            if s[k] < 1.6:
                a.state = "sniff"                                   # inspect first
                o["eat"] = 0.0
    return r


Psyche.drive = _lv_sniff_first


# ============================================================================
# Friends who come to her
# ============================================================================

def _lv_visits(app, dt):
    soc = getattr(app, "society", None)
    if soc is None or not _rw_valley(app) or app.world.daypart in ("evening", "night"):
        return
    life = _lv_life(app)
    app._lv_vacc = getattr(app, "_lv_vacc", 0.0) + dt
    if app._lv_vacc < _LV_VISIT_CHECK:
        return
    app._lv_vacc = 0.0
    if any(getattr(t, "kind", "") == "visitor" for t in getattr(app, "travellers", []) or []):
        return
    regions = getattr(app, "_regions", []) or []
    near = {n for (k, n) in regions[max(0, regions.index(("valley", "valley")) - 2): regions.index(("valley", "valley")) + 3]
            if k == "settlement"} if ("valley", "valley") in regions else set()
    cands = []
    for n in soc.npcs.values():
        if not n.alive or n.role in ("child", "leader") or n.away > 0:
            continue
        rel = n.rel.get("jane", 0.0)
        knows = rel > 0.15 or n.id in getattr(life, "people", {})
        neighbour = n.sett in near and n.t.get("sociability", 0.5) > 0.6
        if not (knows or neighbour):
            continue
        if life.clock - n.__dict__.get("_lv_visited", -1e9) < 900:
            continue
        p = 0.12 * n.t.get("sociability", 0.5) * (0.4 + max(0.0, rel)) * (3.0 if knows else 1.0)
        cands.append((p, n))
    if not cands:
        return
    p, n = max(cands, key=lambda c: c[0] * _lv_random.random())
    if _lv_random.random() < p * 3:
        n._lv_visited = life.clock
        src = soc.sets.get(n.sett)
        tv = Traveller({"kind": "visitor", "from": n.sett, "to": n.sett, "who": n.id, "news": None}, soc, app.world, _lv_random)
        tv.called = tv.talked = tv.talking = False
        tv.wave = 0.0
        app.travellers.append(tv)


_lv_prev_so_tick = _so_tick


def _lv_so_tick(app, dt):
    _lv_prev_so_tick(app, dt)
    life = _lv_life(app)
    cr, b = app.creature, app.brain
    for tv in getattr(app, "travellers", []) or []:
        if getattr(tv, "kind", "") != "visitor":
            continue
        tv.met = True                                            # visitors don't get the passer-by treatment
        d = abs(tv.x - cr.x)
        if not tv.talked:
            tgt = cr.x + (1 if tv.x > cr.x else -1) * WS.m(1.3)
            if abs(tv.x - tgt) > WS.m(0.4):
                tv.dir = 1 if tgt > tv.x else -1
                tv.stop = 0.0 if d > WS.m(1.8) else max(tv.stop, 1.0)
            else:
                tv.stop = max(tv.stop, 2.0)
            if not tv.called and d < WS.m(14):
                tv.called = True
                tv.wave = 1.8
                b.perceive(Event("social", f"{tv.name.split()[0]} waved and called out to me", salience=0.65, valence=0.45))
            if life.clock - getattr(tv, "_t0", life.clock) > 240:
                tv.talked = True                                  # she never came over: they give up and go
                tv.__dict__.setdefault("_t0", life.clock)
            tv.__dict__.setdefault("_t0", life.clock)
        else:
            tv.stop = 0.0
            tv.dir = -1 if tv.x < app.world.w / 2 else 1          # home the way they came
        tv.wave = max(0.0, getattr(tv, "wave", 0.0) - dt)


_so_tick = _lv_so_tick

# visitors wave and show they're talking (the traveller renderer, extended)
_lv_prev_draw_tv = _so_draw_traveller


def _lv_draw_tv(tv, app):
    _lv_prev_draw_tv(tv, app)
    if getattr(tv, "kind", "") != "visitor" or tv.pool is None:
        return
    cam = app._camera
    W = cam.world_to_screen
    H = app.creature._H()
    G = app.world.ground + app.creature._sole() * 0.2
    P = tv.pool
    if getattr(tv, "wave", 0.0) > 0:
        sw = _lv_math.sin(tv.t * 12) * 0.4 * H
        P.put("line", [*W(tv.x, G - 6.1 * H), *W(tv.x + tv.dir * 0.4 * H + sw, G - 8.0 * H)], "fauna",
              fill=tv.skin, width=max(2, int(0.18 * H * cam.zoom)))
    if getattr(tv, "talking", False) and int(tv.t * 1.5) % 2 == 0:
        bx, by = W(tv.x + 0.4 * H, G - 8.6 * H)
        r = 0.35 * H * cam.zoom
        P.put("oval", [bx - r * 1.4, by - r, bx + r * 1.4, by + r], "fauna", fill="#e8edf2", outline="")
    P.end()


_so_draw_traveller = _lv_draw_tv

# ============================================================================
# Sitting governor + bookkeeping + the display
# ============================================================================

_lv_prev_update = App._update_world


def _lv_update(self, dt):
    _lv_prev_update(self, dt)
    try:
        life = _lv_life(self)
        cr = self.creature
        L = cr._loco
        sitting = getattr(L, "sit", 0.0) > 0.5
        if sitting and not getattr(self, "_lv_was_sit", False):
            life.sits = (life.sits + [life.clock])[-20:]
        self._lv_was_sit = sitting
        recent = [t for t in life.sits if life.clock - t < 240]
        tired = self.brain.goals.energy < 0.3 or life.phys["sleep_pressure"] > 0.7 or getattr(life, "sleeping", False)
        mind = self.brain.mind
        bias = dict(getattr(mind, "survival_bias", {}) or {})
        if recent and not tired and not sitting:
            bias["rest"] = bias.get("rest", 0.0) - 0.9                    # she just sat; she won't again soon
            bias["move"] = bias.get("move", 0.0) + 0.15
        mind.survival_bias = bias
        here = _rw_here(self)
        if here[0] == "settlement":
            life.last_town = life.clock
        for d in _lv_dests(self):                                         # places she passes are remembered too
            if abs(d["x"] - cr.x) < WS.m(2.5):
                v = life.visits.setdefault(d["id"], {"n": 0, "last": -1e9})
                if life.clock - v["last"] > 60:
                    v["n"] += 1
                v["last"] = life.clock
        _lv_visits(self, dt)
        lab = getattr(self, "_lv_label", None)
        if lab is None and getattr(self, "world_tab", None) is not None:
            lab = self._lv_label = tk.Label(self.world_tab, text="", bg=C_BG, fg=C_TEXT, font=FONT_UI_SMALL,
                                            anchor="w", justify="left")
            lab.pack(fill="x", padx=8, pady=(0, 4))
        self._lv_acc = getattr(self, "_lv_acc", 0.0) + dt
        if self._lv_acc > 0.4:
            self._lv_acc = 0.0
            self._lv_status = _lv_status_text(self)
            if lab is not None:
                lab.config(text=self._lv_status)
    except Exception:
        traceback.print_exc()


App._update_world = _lv_update


def _lv_status_text(app):
    life = _lf_life(app)
    d = getattr(life, "decision", None)
    act = _lv_action(app)
    if not d:
        return f"GOAL: —   ACTION: {act}"
    pr = f"{d['priority']:.2f}" if d.get("priority") is not None else "—"
    return (f"GOAL: {d['goal']}   ACTION: {act}   TARGET: {d['target']}   PRIORITY: {pr}\n"
            f"REASON: {d['reason']}   NEED: {d['need']}   MEMORY: {d['memory']}")


# persistence
_lv_prev_life_to = JaneLife.to_dict
_lv_prev_life_from = JaneLife.from_dict


def _lv_life_to(self):
    dct = _lv_prev_life_to(self)
    for k in ("visits", "invites", "sits", "decision", "last_town", "investigated"):
        dct["lv_" + k] = getattr(self, k, None)
    return dct


def _lv_life_from(self, dct):
    _lv_prev_life_from(self, dct)
    if isinstance(dct, dict):
        for k in ("visits", "invites", "sits", "decision", "last_town", "investigated"):
            v = dct.get("lv_" + k)
            if v is not None:
                setattr(self, k, v)


JaneLife.to_dict = _lv_life_to
JaneLife.from_dict = _lv_life_from



# ---- Jane's figure: bare shoulders are skin; she stands on straight legs ----
def _lv_cap_color(self, body_color):
    try:
        if self.SHAPE.get("face_hd") and _j_outfit(self) in ("light", "normal"):
            return self._skin_tone()                  # a cami: the shoulder is skin, not a grey disc
    except Exception:
        pass
    return body_color


Creature._cap_color = _lv_cap_color
JANE_SHAPE["stance"] = 1.02                           # standing: legs nearly straight (the body-bob term sinks her ~3.5%)
