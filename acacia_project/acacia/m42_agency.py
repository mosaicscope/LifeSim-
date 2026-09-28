# ============================================================================
# [NEW] M42 - EMERGENT AGENCY & AFFORDANCE PLANNING  (+ M44 animal affect)
# ============================================================================
#
# Goals still come from the existing utility layer (M40 needs x personality x
# opportunity, M41 expectations). M42 turns a goal into a PLAN by searching
# a library of actions defined only by data - preconditions, effects,
# duration, place and risk - so a sequence like "gather wood x3 -> light a
# fire -> cook the berries" is found, not written. Costs are travel + time,
# weighted by fatigue; risks and values are M41 predictions for this
# individual; risk tolerance comes from temperament. Plans run step by step
# through the existing task executor, are re-validated as the world
# changes, can be interrupted by a more urgent goal (paused, kept, resumed
# and re-planned from the new state), and their success or failure feeds
# back into M41. Unfinished plans persist in the save.
#
# Animals: goals from Psyche.drive become small affordance plans (travel to
# the best-known place for it, then act), resumed after a flee reflex, with
# place choice learned from outcomes. M44: each animal carries a persistent
# mood (valence / arousal / fear) from needs, events and temperament that
# biases its choices.

import heapq as _ag_heapq
import itertools as _ag_it

# --------------------------------------------------------------------------
# Jane's action library (data only)
#   pre:  fact -> minimum value (int) or "need" (resolved from state)
#   eff:  fact -> +n / -n / ("set", v)
#   at:   where it happens (resolved against the live world)
# --------------------------------------------------------------------------
_AG_ACTIONS = {
    "gather_wood":  dict(pre={}, eff={"wood": 1}, dur=2.6, at="tree", task="wood"),
    "gather_berries": dict(pre={"food_avail": 1}, eff={"berries": 1}, dur=1.5, at="food", task="berries",
                           cap={"berries": 3}),
    "craft_bow":    dict(pre={"wood": 2}, eff={"wood": -2, "bow": ("set", 1)}, dur=3.0, at="here", task="craft"),
    "hunt":         dict(pre={"bow": 1, "hunting": 1}, eff={"meat": 1}, dur=25.0, at="prey", task="hunt",
                         risk=("shoot", "miss")),
    "light_fire":   dict(pre={"wood": 3}, eff={"wood": -3, "fire": ("set", 1)}, dur=3.0, at="firesite",
                         task="build", risk=("light_fire", "drowned")),
    "cook_berries": dict(pre={"fire": 1, "berries": 1}, eff={"berries": -1, "fed": ("set", 1)}, dur=3.0,
                         at="fire", task="cook", value="cook"),
    "cook_meat":    dict(pre={"fire": 1, "meat": 1}, eff={"meat": -1, "fed": ("set", 1)}, dur=3.0, at="fire",
                         task="cook", bonus=0.3),
    "eat_raw":      dict(pre={"berries": 1}, eff={"berries": -1, "fed": ("set", 1)}, dur=1.5, at="here",
                         task="eat", value="eat_raw"),
    "sleep":        dict(pre={}, eff={"rested": ("set", 1)}, dur=90.0, at="bed", task="sleep"),
    "build_home":   dict(pre={"wood": "home_need"}, eff={"wood": "-home_need", "home": 1}, dur=9.0,
                         at="homesite", task="homebuild"),
    "repair_home":  dict(pre={"wood": 1, "home": 1}, eff={"wood": -1, "home_ok": ("set", 1)}, dur=3.0,
                         at="home", task="repair"),
    "relieve":      dict(pre={}, eff={"relieved": ("set", 1)}, dur=4.0, at="bush", task="relieve"),
    "wash":         dict(pre={}, eff={"clean": ("set", 1)}, dur=4.0, at="water", task="wash"),
    "warm_up":      dict(pre={"fire": 1}, eff={"warm": ("set", 1)}, dur=25.0, at="fire_side", task="warm"),
    "pet":          dict(pre={}, eff={"bonded": ("set", 1)}, dur=2.0, at="subject", task="pet",
                         risk=("approach_fast", "retreated")),
    "offer_food":   dict(pre={"berries": 1}, eff={"berries": -1, "bonded": ("set", 1)}, dur=2.0,
                         at="subject", task="offer", risk=("approach_fast", "retreated")),
    "call":         dict(pre={}, eff={"called": ("set", 1)}, dur=1.0, at="here", task="call"),
    "explore":      dict(pre={}, eff={"explored": ("set", 1)}, dur=4.0, at="frontier", task="explore"),
    "visit_fav":    dict(pre={}, eff={"at_fav": ("set", 1)}, dur=3.0, at="favourite", task="favourite"),
    "check_friend": dict(pre={}, eff={"checked": ("set", 1)}, dur=3.0, at="friend", task="check"),
}

# the utility layer's candidate names -> the state the goal wants
_AG_GOALS = {
    "fire": {"fire": 1}, "fire_cook": {"fed": 1}, "cook": {"fed": 1}, "eat": {"fed": 1},
    "berries": {"berries": 3}, "hunt": {"meat": 1}, "sleep": {"rested": 1}, "home": {"home": "+1"},
    "repair": {"home_ok": 1}, "relieve": {"relieved": 1}, "wash": {"clean": 1}, "warm": {"warm": 1},
    "explore": {"explored": 1}, "favourite": {"at_fav": 1}, "check": {"checked": 1},
}


def _ag_goal_facts(name, s):
    if name.startswith(("pet:", "offer:")):
        return {"bonded": 1}
    if name.startswith("call:"):
        return {"called": 1}
    if name.startswith("trade"):
        return {"traded": 1}
    g = _AG_GOALS.get(name)
    if g is None:
        return None
    out = {}
    for k, v in g.items():
        out[k] = s.get(k, 0) + 1 if v == "+1" else v
    return out


def _ag_state(app, sv, life):
    world = app.world
    f = sv.fire
    food = world.poi("food")
    h = life.home
    return {"wood": sv.inv.get("wood", 0), "berries": sv.inv.get("berries", 0),
            "meat": sv.inv.get("meat", 0), "bow": sv.inv.get("bow", 0),
            "fire": int(bool(f and f.lit)), "home": h["stage"] if h else 0,
            "home_ok": int(bool(h) and h["cond"] >= 0.9),
            "food_avail": int(bool(food and food.available())),
            "hunting": int(bool(app.settings.data.get("hunting_enabled", False))),
            "surplus": int(sv.inv.get("wood", 0) >= 3 or sv.inv.get("meat", 0) >= 1 or sv.inv.get("berries", 0) >= 2)}


def _ag_resolve(v, s):
    if v == "home_need":
        return 4 if s.get("home", 0) == 0 else 3 + s.get("home", 0)
    if v == "-home_need":
        return -(4 if s.get("home", 0) == 0 else 3 + s.get("home", 0))
    return v


def _ag_applicable(a, s):
    for k, v in a["pre"].items():
        if s.get(k, 0) < _ag_resolve(v, s):
            return False
    for k, v in a.get("cap", {}).items():
        if s.get(k, 0) >= v:
            return False
    return True


def _ag_apply(a, s):
    s = dict(s)
    for k, v in a["eff"].items():
        v = _ag_resolve(v, s)
        if isinstance(v, tuple):
            s[k] = v[1]
        else:
            s[k] = s.get(k, 0) + v
    return s


def _ag_satisfied(goal, s):
    return all(s.get(k, 0) >= v for k, v in goal.items())


def _ag_relevant(goal, lib):
    """Regression closure: only actions that can contribute to the goal, or
    to preconditions of actions that can, are searched."""
    facts, acts = set(goal), set()
    changed = True
    while changed:
        changed = False
        for n, a in lib.items():
            if n in acts:
                continue
            if any(k in facts and (isinstance(v, tuple) or _ag_resolve(v, {"home": 1}) > 0 or v == "home_need")
                   for k, v in a["eff"].items()):
                acts.add(n)
                for p in a["pre"]:
                    if p not in facts:
                        facts.add(p)
                        changed = True
                changed = True
    return {n: lib[n] for n in acts}


def ag_plan(goal, s0, cost_fn, lib=_AG_ACTIONS, max_nodes=700):
    """A* over the relevant actions. Returns (steps, cost) or (None, inf)."""
    rel = _ag_relevant(goal, lib)
    if not rel:
        return None, float("inf")

    def h(s):
        return sum(max(0, v - s.get(k, 0)) for k, v in goal.items()) * 2.0

    key = lambda s: tuple(sorted(s.items()))
    tie = _ag_it.count()
    open_ = [(h(s0), 0.0, next(tie), s0, [])]
    seen = {}
    nodes = 0
    while open_ and nodes < max_nodes:
        f, g, _t, s, path = _ag_heapq.heappop(open_)
        if _ag_satisfied(goal, s):
            return path, g
        k = key(s)
        if seen.get(k, 1e18) <= g:
            continue
        seen[k] = g
        nodes += 1
        if len(path) >= 12:
            continue
        for n, a in rel.items():
            if not _ag_applicable(a, s):
                continue
            s2 = _ag_apply(a, s)
            c = cost_fn(n, a, s, len(path))
            if c >= 1e8:
                continue
            _ag_heapq.heappush(open_, (g + c + h(s2), g + c, next(tie), s2, path + [n]))
    return None, float("inf")


# --------------------------------------------------------------------------
# Jane: places, costs, execution
# --------------------------------------------------------------------------
def _ag_where(app, sv, life, at, cand):
    world, cr = app.world, app.creature
    H = cr._Hb()
    trees = getattr(world, "_tree_x", None) or [world.w * 0.3]
    f = sv.fire
    sh = world.poi("shelter")
    home = life.home
    if at == "here":
        return cr.x
    if at == "tree":
        return min(trees, key=lambda t: abs(t - cr.x))
    if at == "bush":
        return min(trees, key=lambda t: abs(t - cr.x)) + 1.5 * H
    if at in ("food", "water"):
        p = world.poi(at)
        return p.x if p else None
    if at == "fire":
        return (f.x + (1 if cr.x >= f.x else -1) * 2.4 * H) if f else None
    if at == "fire_side":
        return (f.x + (1 if cr.x >= f.x else -1) * 3.4 * H) if f else None
    if at == "firesite":
        base = home["x"] + 2.5 * H if home else ((sh.x + 80) if sh else cr.x)
        return clamp(base, 60, world.w - 60)
    if at == "homesite":
        return home["x"] if home else clamp(life.favourite_x(cr.x), 80, world.w - 80)
    if at == "home":
        return home["x"] if home else None
    if at == "bed":
        if home and home["stage"] >= 1:
            return home["x"]
        return (f.x + 2.6 * H) if (f and f.lit) else ((sh.x if sh else cr.x))
    for key in (at,):
        pass
    # places the utility layer already worked out precisely
    for name, (_u, task) in cand.items():
        if task and ((at == "prey" and task[0] == "hunt") or (at == "subject" and task[0] in ("pet", "offer"))
                     or (at == "frontier" and task[0] == "explore") or (at == "favourite" and task[0] == "favourite")
                     or (at == "friend" and task[0] == "check")):
            return task[1]
    if at == "favourite":
        return life.favourite_x(cr.x)
    return cr.x


def _ag_cost_fn(app, sv, life, cand):
    """Travel + time, weighted by fatigue and temperament; risks and values
    are this individual's M41 expectations."""
    cr, b = app.creature, app.brain
    x = getattr(life, "exp", None)
    temper = b.mind.temperament
    risk_w = 1.6 - temper.get("risk_tolerance", 0.5)
    tired = 1.0 + 0.8 * max(0.0, 0.6 - b.goals.energy) + 0.5 * life.phys.get("pain", 0.0)
    wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
    rain_b = sum(1 for e in (0.25, 0.5, 0.75) if wx.get("precip", 0.0) >= e)
    pos = {}

    def cost(n, a, s, depth):
        if n in getattr(sv, "_ag_banned", {}) and life.clock < sv._ag_banned[n]:
            return 1e9
        if a["at"] not in pos:
            pos[a["at"]] = _ag_where(app, sv, life, a["at"], cand)
        px = pos[a["at"]]
        if px is None:
            return 1e9
        travel = abs(px - cr.x) / 110.0 if depth == 0 else 3.0     # later steps: rough
        c = (a["dur"] + travel) * tired
        if x is not None:
            if "risk" in a:
                act, bad = a["risk"]
                ctx = {"who": "fire", "kind": "fire", "rain": rain_b} if act == "light_fire" else {"who": "?", "kind": "?"}
                ev, dist, conf = x.predict(act, ctx)
                c += risk_w * dist.get(bad, 0.25 if conf < 0.2 else 0.0) * 25.0
            if "value" in a:
                ev, _d, conf = x.predict(a["value"], {"who": "food", "kind": "berries"})
                c -= 20.0 * ev * conf
            ev, dist, conf = x.predict("do:" + n, {"who": n, "kind": "act"})
            c += 15.0 * dist.get("failed", 0.0) * conf                 # learned unreliability
        c -= 8.0 * a.get("bonus", 0.0)
        return max(0.2, c)
    return cost


def _ag_think(app, text):
    try:
        _lf_think(app.brain, app.brain.mind, text, "plan")
    except Exception:
        pass


_AG_SAY = {"gather_wood": "gather wood", "gather_berries": "pick berries", "craft_bow": "make a bow",
           "hunt": "hunt", "light_fire": "light a fire", "cook_berries": "cook the berries",
           "cook_meat": "cook the meat", "eat_raw": "eat", "sleep": "sleep", "build_home": "build",
           "repair_home": "patch the shelter", "wash": "wash", "warm_up": "warm up by the fire",
           "pet": "go and say hello", "offer_food": "offer some food", "call": "call out",
           "explore": "have a look around", "visit_fav": "go to my favourite spot",
           "check_friend": "look for my friend", "relieve": "find a bush", "trade": "trade"}


def _ag_describe(steps):
    out, last, n = [], None, 0
    for s in steps + [None]:
        if s == last:
            n += 1
            continue
        if last is not None:
            out.append(_AG_SAY.get(last, last) + (f" (x{n})" if n > 1 else ""))
        last, n = s, 1
    return ", then ".join(out)


def _ag_snapshot(app, sv, life):
    return {"s": _ag_state(app, sv, life), "hunger": app.brain.goals.hunger,
            "sp": life.phys["sleep_pressure"], "bl": life.phys["bladder"], "hy": life.phys["hygiene"],
            "petted": max([op.get("petted", -1) for op in life.animals.values()] or [-1]),
            "call": getattr(life, "_px_last_call", -1), "home": dict(life.home) if life.home else None}


def _ag_step_done(n, snap, app, sv, life):
    """Did this step's effect actually happen in the world?"""
    s1 = _ag_state(app, sv, life)
    s0 = snap["s"]
    a = _AG_ACTIONS.get(n) or _AG_EXTRA.get(n)
    P = life.phys
    if n in ("cook_berries", "cook_meat", "eat_raw"):
        # done when she has actually eaten: food gone, or hunger relieved
        # relative to how hungry she was (0.15 absolute can't happen near 0)
        s1 = _ag_state(app, sv, life)
        ate = s1.get("berries", 0) < snap["s"].get("berries", 0) or s1.get("meat", 0) < snap["s"].get("meat", 0)
        return ate or app.brain.goals.hunger < snap["hunger"] - min(0.15, 0.5 * snap["hunger"])
    if n == "sleep":
        return P["sleep_pressure"] < 0.1
    if n == "relieve":
        return P["bladder"] < 0.1
    if n == "wash":
        return P["hygiene"] > 0.9
    if n == "warm_up":
        return life.clock - snap.get("t", life.clock) > 25 or app.brain.mind.comfort.cold < 0.05
    if n in ("pet", "offer_food"):
        return max([op.get("petted", -1) for op in life.animals.values()] or [-1]) > snap["petted"]
    if n == "call":
        return getattr(life, "_px_last_call", -1) > snap["call"]
    if n in ("explore", "visit_fav", "check_friend"):
        return sv.task is None
    if n == "trade":
        return getattr(sv, "_traded_t", -1) > snap.get("t", 0)
    for k, v in a["eff"].items():
        v = _ag_resolve(v, s0)
        if isinstance(v, tuple):
            if s1.get(k, 0) < v[1]:
                return False
        elif v > 0 and s1.get(k, 0) < s0.get(k, 0) + v:
            return False
        elif v < 0 and s1.get(k, 0) > s0.get(k, 0) + v:
            return False
    return True


_AG_EXTRA = {}          # other modules add actions here (e.g. M46 trade)


def _ag_lib():
    lib = dict(_AG_ACTIONS)
    lib.update(_AG_EXTRA)
    return lib


def _ag_exec(n, app, sv, life, cand):
    a = _ag_lib()[n]
    x = _ag_where(app, sv, life, a["at"], cand)
    if x is None:
        return None
    if a["task"] in ("pet", "offer"):
        for name, (_u, task) in cand.items():
            if task and task[0] in ("pet", "offer") and name.startswith(("pet:", "offer:")):
                sv._subject = int(name.split(":")[1])
                sv._cand = name
                break
    return (a["task"], x)


def _ag_new_plan(app, sv, life, cand, name, util):
    s = _ag_state(app, sv, life)
    goal = _ag_goal_facts(name, s)
    if goal is None:
        return None
    if _ag_satisfied(goal, s) and not name.startswith(("pet:", "offer:", "call:", "trade")):
        return None
    lib = _ag_lib()
    if name.startswith("offer:"):
        lib = {k: v for k, v in lib.items() if k != "pet"}
    elif name.startswith("pet:"):
        lib = {k: v for k, v in lib.items() if k != "offer_food"}
    steps, cost = ag_plan(goal, s, _ag_cost_fn(app, sv, life, cand), lib)
    if not steps:
        return None
    return {"goal": name, "facts": goal, "steps": steps, "i": 0, "util": util, "cost": round(cost, 1),
            "t0": life.clock, "st": life.clock, "snap": None}


def _ag_decide(sv, app, life, cand, task_m40):
    life = _lf_life(app)
    now = life.clock
    plan = getattr(life, "plan", None)
    paused = life.__dict__.setdefault("paused", [])
    x = getattr(life, "exp", None)
    wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
    ctx = {"who": "plan", "kind": "plan", "rain": int(wx.get("precip", 0.0) > 0.4),
           "dark": int(app.world.daypart in ("evening", "night"))}
    # learned feasibility of goals (M41): plans that tend to fail are less wanted
    if x is not None:
        for k in list(cand):
            ev, dist, conf = x.predict("plan:" + k.split(":")[0], ctx)
            u, t = cand[k]
            cand[k] = (u + 0.25 * ev * conf, t)
    # --- advance / validate the current plan ------------------------------------
    if plan is not None:
        n = plan["steps"][plan["i"]]
        fresh = plan.get("snap") is None
        if fresh:                                    # the step starts now; judge it from next tick
            plan["snap"] = _ag_snapshot(app, sv, life)
            plan["snap"]["t"] = now
            plan["st"] = now
        if not fresh and _ag_step_done(n, plan["snap"], app, sv, life):
            plan["i"] += 1
            plan["snap"] = None
            sv.task = None
            if plan["i"] >= len(plan["steps"]):
                if x is not None:
                    x.update("plan:" + plan["goal"].split(":")[0], ctx, "done", 0.3)
                life.plans_done = getattr(life, "plans_done", 0) + 1
                life.plan = plan = None
        elif now - plan["st"] > 45 + 3 * _ag_lib()[n]["dur"]:
            # the step isn't working: learn it, ban it briefly, re-plan
            if x is not None:
                x.update("do:" + n, {"who": n, "kind": "act"}, "failed", -0.4)
                x.update("plan:" + plan["goal"].split(":")[0], ctx, "failed", -0.4)
            sv.__dict__.setdefault("_ag_banned", {})[n] = now + 40
            _ag_think(app, f"that isn't working - I'll try another way to {_AG_SAY.get(n, n)}")
            life.plan = plan = None
    # --- choose: continue, interrupt, resume, or start ------------------------------
    ranked = sorted(cand, key=lambda k: -cand[k][0])
    if plan is not None:
        cur_u = cand[plan["goal"]][0] if plan["goal"] in cand else plan["util"] * 0.85
        plan["util"] = cur_u
        best = ranked[0] if ranked else None
        margin = 0.25 + 0.1 * len(plan["steps"][plan["i"]:])      # commitment grows with what's left
        if best and best != plan["goal"] and cand[best][0] > cur_u + margin:
            if plan["i"] > 0 or plan["goal"] in ("home", "fire", "hunt", "fire_cook"):
                paused.append(dict(plan, snap=None, paused_at=now))
                del paused[:-4]
                _ag_think(app, f"that can wait - I'll come back to it ({_ag_describe(plan['steps'][plan['i']:])})")
            life.plan = plan = None
        elif cur_u < 0.05:
            life.plan = plan = None
    if plan is None:
        # resume what was paused, if it still matters
        for p in reversed(list(paused)):
            if p["goal"] in cand and cand[p["goal"]][0] >= 0.6 * (cand[ranked[0]][0] if ranked else 0):
                paused.remove(p)
                np_ = _ag_new_plan(app, sv, life, cand, p["goal"], cand[p["goal"]][0])   # re-plan from now
                if np_:
                    life.plan = plan = np_
                    _ag_think(app, f"back to what I was doing: {_ag_describe(plan['steps'])}")
                    break
            elif now - p["paused_at"] > 900:
                paused.remove(p)
    if plan is None:
        for name in ranked[:4]:
            np_ = _ag_new_plan(app, sv, life, cand, name, cand[name][0])
            if np_:
                life.plan = plan = np_
                if len(plan["steps"]) > 1:
                    _ag_think(app, f"plan: {_ag_describe(plan['steps'])}")
                break
    if plan is None:
        return None                                              # no plan: M40's own choice stands
    n = plan["steps"][plan["i"]]
    t = _ag_exec(n, app, sv, life, cand)
    if t is None:
        life.plan = None
        return None
    if t[0] == "hunt" and getattr(sv, "task", None) and sv.task[0] == "hunt":
        return sv.task
    return t


# persistence of unfinished and paused plans
_ag_prev_life_to = JaneLife.to_dict
_ag_prev_life_from = JaneLife.from_dict


def _ag_life_to(self):
    d = _ag_prev_life_to(self)
    clean = lambda p: {k: v for k, v in p.items() if k != "snap"}
    d["plan"] = clean(self.plan) if getattr(self, "plan", None) else None
    d["paused"] = [clean(p) for p in getattr(self, "paused", [])]
    d["plans_done"] = getattr(self, "plans_done", 0)
    return d


def _ag_life_from(self, d):
    _ag_prev_life_from(self, d)
    if isinstance(d, dict):
        p = d.get("plan")
        lib = _ag_lib()
        ok = lambda p: isinstance(p, dict) and all(s in lib for s in p.get("steps", [])) and p.get("steps")
        self.plan = dict(p, snap=None, st=0.0) if ok(p) else None
        self.paused = [dict(q, snap=None) for q in d.get("paused", []) if ok(q)]
        self.plans_done = int(d.get("plans_done", 0))


JaneLife.to_dict = _ag_life_to
JaneLife.from_dict = _ag_life_from


# --------------------------------------------------------------------------
# Animals: affordance plans + (M44) persistent mood
# --------------------------------------------------------------------------
def _ag_mood(psy, dt_hint=0.8):
    """M44: a persistent mood - needs, recent experience, temperament."""
    m = psy.__dict__.setdefault("mood", {"valence": 0.1, "arousal": 0.3, "fear": 0.0})
    t = psy.idn["traits"]
    n = psy.need
    lack = (n["hunger"] + n["thirst"] + n["fatigue"]) / 3.0
    recent = [v for (_t, _w, v, _x) in psy.mem[-6:]]
    exp_v = sum(recent) / len(recent) if recent else 0.0
    base = 0.15 * t["boldness"] + 0.1 * t["sociability"] - 0.1
    k = 0.15
    m["valence"] += ((base + 0.6 * exp_v - 0.7 * lack) - m["valence"]) * k
    m["arousal"] += ((0.2 + 0.5 * t["energy"] * (1 - n["fatigue"]) + 0.3 * m["fear"]) - m["arousal"]) * k
    threat = max([r.get("fear", 0.0) for r in psy.rel.values()] or [0.0])
    m["fear"] += ((threat * (1.2 - t["boldness"])) - m["fear"]) * k
    for key in m:
        m[key] = round(clamp(m[key], -1.0 if key == "valence" else 0.0, 1.0), 3)
    return m


_ag_prev_adjust = _m41_adjust


def _ag_adjust(psy, a, fa, world, jane, u):
    u = _ag_prev_adjust(psy, a, fa, world, jane, u) or u
    m = _ag_mood(psy)
    if "play" in u:
        u["play"] *= 0.6 + 0.8 * max(0.0, m["valence"] + 0.3)
    if "avoid" in u:
        u["avoid"] += 0.4 * m["fear"]
    if "explore" in u:
        u["explore"] *= 0.7 + 0.6 * m["arousal"] - 0.4 * m["fear"]
    if "sleep" in u:
        u["sleep"] += 0.15 * max(0.0, 0.3 - m["arousal"])
    # a plan interrupted by a reflex keeps its pull
    pl = getattr(psy, "plan", None)
    if pl and pl["goal"] in u and pl["i"] < len(pl["steps"]):
        u[pl["goal"]] += 0.15
    return u


def _ag_animal_place(psy, a, world, kind):
    """Where to do it: the place its own experience rates best."""
    if kind == "water":
        p = world.poi("water")
        return p.x if p else None
    if kind == "home":
        return psy.home if psy.home is not None else a.x
    best, bv = None, -1e9
    x = getattr(psy, "exp", None)
    for k, v in list(psy.places.items())[:16]:
        px = int(k) * 60 + 30
        val = v - abs(px - a.x) / 600.0
        if x is not None:
            ev, _d, conf = x.predict("forage", {"who": f"p{k}", "kind": "place"})
            val += ev * conf
        if val > bv:
            best, bv = px, val
    return best if best is not None and bv > 0.05 else a.x


def _ag_after(psy, a, fa, world, jane, goal):
    S = a.S
    if S.get("flyer") or S.get("flutter"):
        return
    pl = getattr(psy, "plan", None)
    if goal not in ("eat", "drink", "sleep"):
        if pl and pl["goal"] != goal and pl["i"] < len(pl["steps"]):
            psy.paused_plan = pl                               # kept for later
        psy.plan = None
        return
    if pl is None or pl["goal"] != goal:
        pp = getattr(psy, "paused_plan", None)
        if pp and pp["goal"] == goal:
            pl = psy.plan = pp                                  # resume
            psy.paused_plan = None
        else:
            where = {"drink": "water", "sleep": "home", "eat": "forage"}[goal]
            dest = _ag_animal_place(psy, a, world, where)
            if dest is None:
                return
            steps = [("go", dest), (goal, dest)]
            # hungry AND thirsty: fold the drink into the trip if water is on the way
            if goal == "eat" and psy.need["thirst"] > 0.5:
                w = world.poi("water")
                if w is not None and abs(w.x - a.x) < abs(dest - a.x) + 150:
                    steps = [("go", w.x), ("drink", w.x)] + steps
            pl = psy.plan = {"goal": goal, "steps": steps, "i": 0, "t": fa.clock}
    if pl["i"] >= len(pl["steps"]):
        psy.plan = None
        return
    kind, dest = pl["steps"][pl["i"]]
    if kind == "go":
        if abs(a.x - dest) > 16:
            a.state, a.goal = "wander", dest
            return
        pl["i"] += 1
        kind, dest = pl["steps"][pl["i"]] if pl["i"] < len(pl["steps"]) else (None, None)
    if kind == "drink":
        a.state, a.goal = "drink", a.x
        if psy.need["thirst"] < 0.1:
            pl["i"] += 1
    elif kind == "eat":
        a.state, a.goal = ("graze" if S.get("prey") else "sniff"), a.x
        if psy.need["hunger"] < 0.15:
            x = getattr(psy, "exp", None)
            if x is not None:
                x.update("forage", {"who": f"p{int(a.x // 60)}", "kind": "place"}, "fed",
                         0.4 - 0.3 * min(1.0, (fa.clock - pl["t"]) / 120.0))
            pl["i"] += 1
    elif kind == "sleep":
        a.state, a.goal = "sleep", a.x
        if psy.need["fatigue"] < 0.1:
            pl["i"] += 1
    if pl["i"] >= len(pl["steps"]):
        psy.plan = None


# persistence of animal plans + mood
_ag_prev_psy_to = Psyche.to_dict
_ag_prev_psy_from = Psyche.from_dict.__func__


def _ag_psy_to(self):
    d = _ag_prev_psy_to(self)
    d["mood"] = getattr(self, "mood", None)
    pl = getattr(self, "plan", None) or getattr(self, "paused_plan", None)
    d["plan"] = {"goal": pl["goal"], "steps": pl["steps"], "i": pl["i"]} if pl else None
    return d


def _ag_psy_from(cls, d):
    p = _ag_prev_psy_from(cls, d)
    if isinstance(d.get("mood"), dict):
        p.mood = {k: float(v) for k, v in d["mood"].items()}
    if isinstance(d.get("plan"), dict):
        p.paused_plan = dict(d["plan"], t=0.0, steps=[tuple(s) for s in d["plan"]["steps"]])
    return p


Psyche.to_dict = _ag_psy_to
Psyche.from_dict = classmethod(_ag_psy_from)

_m41_adjust = _ag_adjust
_m42_after = _ag_after
_m42_decide = _ag_decide
