# ============================================================================
# [NEW] M41 - INDIVIDUALISED PREDICTIVE COGNITION  (additive, loaded last)
# ============================================================================
#
# Memory records what happened. Prediction represents what is expected.
# Experience changes the expectation. The changed expectation changes
# behaviour. Behaviour creates new experience.
#
# Expectations: one per individual (Jane, every Psyche). A lightweight
# hierarchical contingency model:
#     P(outcome | action, context), E[value | action, context], evidence n
# stored at four abstraction levels, from exact to general:
#     L0  action + who + full situation       ("approaching Gauss, fast, at dusk")
#     L1  action + kind + situation            ("approaching a dog, fast")
#     L2  action + who                          ("approaching Gauss")
#     L3  action                                ("approaching animals")
# Predictions back off across levels weighted by evidence, and by the
# individual's GENERALISATION tendency for the abstract levels - sparse
# evidence stays uncertain instead of hardening into a rule.
#
# Update: prediction -> outcome -> prediction error (value) + surprise
# (categorical) -> incremental revision. Evidence decays (memory span), so
# contradicted expectations attenuate and are superseded. Negative outcomes
# are weighted by the individual's loss aversion (temperament/attachment).
# Everything individual: learning rate, memory span, generalisation, loss
# aversion and neophobic prior all come from the existing identity traits,
# so two animals fed identical events end up expecting different things.
#
# Integration (no new AI layer - the existing utilities get an expectation
# term): animal goal utilities (M40 Psyche.drive), Jane's utility planner,
# her approach pace, shot range, fire-vs-weather, eat raw vs cook, and a
# learned vocal signal (Jane calls; an animal that has found calls
# rewarding comes). Surprises feed emotion and episodic memory.
# Persistence: inside Psyche / JaneLife dicts. Any failure: no-op fallback.

import math as _px_math
import random as _px_random
import time as _px_time

_PX_K = (1.5, 2.5, 2.0, 4.0)             # evidence needed per level before it is trusted
_PX_MAX = 160                            # entries kept per individual (most evidence wins)


class Expectations:
    def __init__(self, lr=0.7, span=30, gen=0.5, loss=1.2, prior_v=0.0, gain=1.0):
        self.lr, self.span, self.gen, self.loss, self.prior_v = lr, span, gen, loss, prior_v
        self.gain = gain                 # how much GOOD outcomes weigh for this individual
        self.t = {}                      # key -> [n, sum_v, {outcome: count}, stamp]
        self.stamp = 0

    # -- keys at each abstraction level -------------------------------------------
    @staticmethod
    def _keys(action, ctx):
        who = ctx.get("who", "?")
        kind = ctx.get("kind", "?")
        sit = "|".join(f"{k}={ctx[k]}" for k in sorted(ctx) if k not in ("who", "kind"))
        return (f"0|{action}|{who}|{sit}", f"1|{action}|{kind}|{sit}", f"2|{action}|{who}", f"3|{action}")

    def _decay(self, e):
        # evidence ages by how many updates this individual has made since:
        # a short memory span forgets (and so revises) faster
        age = self.stamp - e[3]
        if age > 0:
            f = 0.5 ** (age / max(8.0, self.span * 2.0))
            e[0] *= f
            e[1] *= f
            for o in e[2]:
                e[2][o] *= f
            e[3] = self.stamp

    def predict(self, action, ctx):
        """-> (expected value, {outcome: p}, confidence 0..1)"""
        ws, vs, dist, n_eff = 0.0, 0.0, {}, 0.0
        for lvl, key in enumerate(self._keys(action, ctx)):
            e = self.t.get(key)
            if e is None or e[0] <= 1e-6:
                continue
            self._decay(e)
            w = e[0] / (e[0] + _PX_K[lvl])
            if lvl in (1, 3):
                w *= self.gen                       # abstraction is trait-limited
            ws += w
            vs += w * e[1] / e[0]
            n_eff += w * e[0]
            tot = sum(e[2].values()) or 1.0
            for o, c in e[2].items():
                dist[o] = dist.get(o, 0.0) + w * c / tot
        prior_w = 1.0
        ev = (vs + prior_w * self.prior_v) / (ws + prior_w)
        if ws > 0:
            s = sum(dist.values()) or 1.0
            dist = {o: v / s for o, v in dist.items()}
        conf = n_eff / (n_eff + 3.0)
        return ev, dist, conf

    def update(self, action, ctx, outcome, value, weight=1.0):
        """Returns (prediction error, surprise, confidence before)."""
        ev, dist, conf = self.predict(action, ctx)
        pe = value - ev
        surprise = 1.0 - dist.get(outcome, 0.0) if dist else 0.5
        self.stamp += 1
        v_adj = value * (self.loss if value < 0 else self.gain)
        for lvl, key in enumerate(self._keys(action, ctx)):
            e = self.t.get(key)
            if e is None:
                e = self.t[key] = [0.0, 0.0, {}, self.stamp]
            self._decay(e)
            # abstract levels learn less per event than the specific memory
            inc = self.lr * weight * (1.0 if lvl in (0, 2) else 0.35 + 0.5 * self.gen)
            e[0] += inc
            e[1] += inc * v_adj
            e[2][outcome] = e[2].get(outcome, 0.0) + inc
        if len(self.t) > _PX_MAX:
            for k in sorted(self.t, key=lambda k: self.t[k][0])[: len(self.t) - _PX_MAX]:
                del self.t[k]
        return pe, surprise, conf

    def to_dict(self):
        return {"p": [self.lr, self.span, self.gen, self.loss, self.prior_v, self.gain], "s": self.stamp,
                "t": {k: [round(e[0], 4), round(e[1], 4), {o: round(c, 4) for o, c in e[2].items()}, e[3]]
                      for k, e in self.t.items() if e[0] > 0.01}}

    @classmethod
    def from_dict(cls, d):
        x = cls(*(list(d.get("p", [0.7, 30, 0.5, 1.2, 0.0]))[:6]))
        x.stamp = int(d.get("s", 0))
        for k, e in (d.get("t") or {}).items():
            if isinstance(e, list) and len(e) == 4 and isinstance(e[2], dict):
                x.t[k] = [float(e[0]), float(e[1]), {str(o): float(c) for o, c in e[2].items()}, int(e[3])]
        return x


def _px_for_psyche(psy):
    """Individual learning parameters from the animal's identity."""
    t = psy.idn["traits"]
    att = psy.idn["attachment"]
    return Expectations(
        lr=0.35 + 0.5 * psy.idn["learning_rate"],
        span=psy.idn["memory_span"],
        gen=clamp01(0.2 + 0.65 * t["intelligence"] - 0.15 * (att == "anxious")),
        loss=0.8 + 1.4 * (1.0 - t["boldness"]) + (0.6 if att == "anxious" else 0.0),
        prior_v=round(0.12 * t["sociability"] - 0.18 * (1.0 - t["boldness"]), 3),
        gain=round((0.5 + 0.9 * t["sociability"]) * {"avoidant": 0.6, "independent": 0.75,
                                                        "anxious": 1.25}.get(att, 1.0), 3))


def _px_for_jane(brain):
    tr = brain.personality.traits
    return Expectations(lr=0.55 + 0.35 * tr.get("curiosity", 0.6),
                        span=int(24 + 30 * tr.get("openness", 0.6)),
                        gen=clamp01(0.45 + 0.3 * tr.get("openness", 0.6)),   # pattern-seeking
                        loss=1.15, prior_v=0.0)


def _px(obj, maker):
    x = getattr(obj, "exp", None)
    if x is None:
        x = obj.exp = maker()
    return x


def _bucket(v, edges):
    for i, e in enumerate(edges):
        if v < e:
            return i
    return len(edges)


# ============================================================================
# Animals
# ============================================================================

def _px_ctx(psy, a, fa, world, jane):
    jspeed = abs(getattr(getattr(jane, "_loco", None), "vx", 0.0)) if jane is not None else 0.0
    sv_aim = getattr(jane, "_aim", None) is not None
    return {"who": "jane", "kind": "human",
            "pace": _bucket(jspeed, (25, 170)),                         # still / walking / hurrying
            "armed": int(bool(sv_aim)),
            "fire": int(fa.fire_x is not None),
            "food": int(bool(fa.jane_has_food)),
            "call": int(fa.clock - getattr(psy, "heard_call", -1e9) < 15.0),
            "dark": int(world.daypart in ("evening", "night"))}


_PX_SOCIAL = ("jane", "follow", "play", "beg", "avoid", "greet")


def _px_adjust(psy, a, fa, world, jane, u):
    """Expected consequences join needs x personality x relationships."""
    if jane is None:
        return u
    x = _px(psy, lambda: _px_for_psyche(psy))
    ctx = _px_ctx(psy, a, fa, world, jane)
    psy._px_ctx = ctx
    t = psy.idn["traits"]
    use = 0.35 + 0.6 * t["intelligence"]                              # how much it acts on expectations
    for g in _PX_SOCIAL:
        if g in u:
            ev, _dist, conf = x.predict(g, ctx)
            u[g] += use * ev * conf
    # a learned signal: a call that has predicted good things pulls it in
    if ctx["call"] and "jane" in u:
        ev, _d, conf = x.predict("jane", ctx)
        if ev > 0.1 and conf > 0.2:
            u["jane"] += 0.4 * ev * conf
    # rest spots: expect where sleep goes undisturbed
    if "sleep" in u and psy.places:
        best, best_v = psy.home, -1e9
        for k in list(psy.places)[:12]:
            ev, _d, conf = x.predict("rest", {"who": f"p{k}", "kind": "place"})
            v = psy.places[k] * 0.3 + ev * conf
            if v > best_v:
                best, best_v = int(k) * 60 + 30, v
        if best is not None and best_v > 0.1:
            psy.home = best
    return u


def _px_chose(psy, a, fa, world, jane, goal):
    if goal in _PX_SOCIAL and getattr(psy, "_px_ctx", None):
        tr = getattr(psy, "_px_trace", [])
        if not tr or tr[-1][1] != goal:
            tr.append([fa.clock, goal, psy._px_ctx, False])
            psy._px_trace = tr[-6:]


def _px_credit(psy, clock, outcome, value):
    """Consequence arrives: credit recent choices (eligibility decays)."""
    x = getattr(psy, "exp", None)
    if x is None:
        return
    for tr in getattr(psy, "_px_trace", []):
        age = clock - tr[0]
        if 0 <= age < 14.0:
            pe, surprise, conf = x.update(tr[1], tr[2], outcome, value, weight=_px_math.exp(-age / 6.0))
            tr[3] = True
            if conf > 0.35 and abs(pe) > 0.5:
                psy.mem.append((round(clock, 1), "jane", round(value, 2),
                                f"expected {'good' if value < 0 else 'trouble'} from {tr[1]}, got {outcome}"))
                psy.mem = psy.mem[-psy.idn["memory_span"]:]


_px_prev_learn = Psyche.learn


def _px_learn(self, who, clock, text, val, **d):
    _px_prev_learn(self, who, clock, text, val, **d)
    try:
        # only CONSEQUENCES of its choices count - not its own choices or mere sightings
        if who == "jane" and text.startswith(("Jane fed", "Jane petted", "Jane shot", "Jane rushed")):
            outcome = "kind" if val > 0.3 else ("threat" if val < -0.15 else "calm")
            _px_credit(self, clock, outcome, val)
    except Exception:
        pass


Psyche.learn = _px_learn

_px_prev_psy_to = Psyche.to_dict
_px_prev_psy_from = Psyche.from_dict.__func__


def _px_psy_to(self):
    d = _px_prev_psy_to(self)
    if getattr(self, "exp", None) is not None:
        d["exp"] = self.exp.to_dict()
    return d


def _px_psy_from(cls, d):
    p = _px_prev_psy_from(cls, d)
    try:
        if isinstance(d.get("exp"), dict):
            p.exp = Expectations.from_dict(d["exp"])
    except Exception:
        pass
    return p


Psyche.to_dict = _px_psy_to
Psyche.from_dict = classmethod(_px_psy_from)

_px_prev_fauna_update = Fauna.update


def _px_fauna_update(self, dt, world, jane):
    # disturbances of rest are consequences of WHERE it chose to rest
    for a in self.animals:
        p = getattr(a, "psy", None)
        if p is None:
            continue
        resting = a.state in ("sleep", "drink", "perch")
        if resting:
            a._px_rest = int(a.x // 60)
        elif getattr(a, "_px_rest", None) is not None:
            spot = a._px_rest
            a._px_rest = None
            x = _px(p, lambda: _px_for_psyche(p))
            if a.fear > 0.45:
                x.update("rest", {"who": f"p{spot}", "kind": "place"}, "disturbed", -0.6)
            else:
                x.update("rest", {"who": f"p{spot}", "kind": "place"}, "rested", 0.3)
    _px_prev_fauna_update(self, dt, world, jane)
    # choices that led nowhere attenuate: nothing happened is also an outcome
    for a in self.animals:
        p = getattr(a, "psy", None)
        if p is None or not getattr(p, "_px_trace", None):
            continue
        keep = []
        for tr in p._px_trace:
            if self.clock - tr[0] >= 14.0:
                if not tr[3] and getattr(p, "exp", None) is not None:
                    p.exp.update(tr[1], tr[2], "nothing", 0.0, weight=0.5)
            else:
                keep.append(tr)
        p._px_trace = keep
    # a call carries: residents off-screen that expect good things come back
    for sig in getattr(self, "signals", [])[-3:]:
        if self.clock - sig[0] > 0.5:
            continue
        for a in self.animals:
            if getattr(a, "psy", None) and abs(a.x - sig[1]) < 900:
                a.psy.heard_call = self.clock
        for w in self.away:
            psy = w[2]
            x = getattr(psy, "exp", None)
            ev, _d, conf = x.predict("jane", {"who": "jane", "kind": "human", "call": 1}) if x else (0.0, {}, 0.0)
            if ev * conf > 0.05 or psy.idn["traits"]["sociability"] > 0.8:
                psy.heard_call = self.clock
                w[0] = min(w[0], self.clock + _px_random.uniform(3.0, 8.0))


Fauna.update = _px_fauna_update


# ============================================================================
# Jane
# ============================================================================

def _px_jane(app):
    life = _lf_life(app)
    x = getattr(life, "exp", None)
    if x is None:
        x = life.exp = _px_for_jane(app.brain)
    return life, x


def _px_surprise(app, text, pe, conf):
    """A violated expectation is felt and remembered - evidence for next time."""
    b = app.brain
    if conf < 0.3 or abs(pe) < 0.35:
        return
    b.emotion.nudge("arousal", min(0.25, 0.3 * abs(pe)), "surprise")
    b.emotion.nudge("valence", 0.15 * max(-1.0, min(1.0, pe)), "")
    b.memory.remember("episode", text, importance=0.5 + 0.3 * min(1.0, abs(pe)),
                      emotion=b.emotion.emotion, valence=0.3 * pe, subject="self")
    _lf_think(b, b.mind, text, "surprise")


def _px_actx(a, world):
    return {"who": str(a.psy.seed), "kind": a.sp, "dark": int(world.daypart in ("evening", "night")),
            "st": {"sniff": "calm", "graze": "calm", "sleep": "calm", "drink": "calm", "follow": "near",
                   "excited": "near", "play": "near", "beg": "near"}.get(a.state, "moving")}


def _px_approach(sv, app, life_, kind, subj):
    """Choose HOW to approach from what approaching this animal has led to."""
    life, x = _px_jane(app)
    ctx = _px_actx(subj, app.world)
    pend = getattr(sv, "_px_app", None)
    if pend is None or pend["seed"] != subj.psy.seed:
        ev_f, df, cf = x.predict("approach_fast", ctx)
        ev_s, ds, cs = x.predict("approach_slow", ctx)
        ev_s -= 0.05                                          # a slow approach costs time
        # untried: patient / anxious-to-please animals get the careful approach
        mode = "approach_slow" if (ev_s > ev_f and cs > 0.15) or \
            (cf > 0.3 and df.get("retreated", 0.0) > 0.45) else "approach_fast"
        sv._px_app = {"seed": subj.psy.seed, "mode": mode, "ctx": ctx, "t0": life.clock,
                      "d0": abs(subj.x - app.creature.x), "done": False,
                      "pred": (ev_s if mode == "approach_slow" else ev_f)}
        pend = sv._px_app
    return 0.45 if pend["mode"] == "approach_slow" else 1.0


def _px_plan_adjust(sv, app, life_, cand):
    life, x = _px_jane(app)
    world, cr, b = app.world, app.creature, app.brain
    H = cr._Hb()
    g = b.goals
    wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
    fa = getattr(app, "fauna", None)
    dark = int(world.daypart in ("evening", "night"))
    # approaching animals: expected reaction scales the wish to go and pet/feed
    for k in list(cand):
        if k.startswith(("pet:", "offer:")) and fa:
            seed = int(k.split(":")[1])
            a = next((o for o in fa.animals if getattr(o, "psy", None) and o.psy.seed == seed), None)
            if a is None:
                continue
            ctx = _px_actx(a, world)
            best = max(x.predict("approach_fast", ctx)[0] * x.predict("approach_fast", ctx)[2],
                       x.predict("approach_slow", ctx)[0] * x.predict("approach_slow", ctx)[2])
            u, task = cand[k]
            cand[k] = (u + 0.6 * best, task)
    # fire vs weather: the rain level she now expects a fire to survive
    rains = [r for r in (0.0, 0.3, 0.55, 0.8)]
    ok = [r for r in rains if x.predict("light_fire", {"who": "fire", "kind": "fire", "rain": _bucket(r, (0.25, 0.5, 0.75))})[2] < 0.25
          or x.predict("light_fire", {"who": "fire", "kind": "fire", "rain": _bucket(r, (0.25, 0.5, 0.75))})[0] > -0.1]
    life.learned["fire_rain"] = max(0.3, max(ok) + 0.12) if ok else 0.3
    # eat raw vs cook: what each has actually done for her hunger
    ev_raw, _d, c_raw = x.predict("eat_raw", {"who": "food", "kind": "berries"})
    ev_cook, _d, c_cook = x.predict("cook", {"who": "food", "kind": "berries"})
    if "eat" in cand and c_raw > 0.3 and c_cook > 0.3 and ev_cook - ev_raw > 0.08 and g.hunger < 0.75:
        u, task = cand["eat"]
        cand["eat"] = (u * 0.5, task)                          # worth the wait for the fire
        if not (sv.fire and sv.fire.lit) and "fire" not in cand and wx.get("precip", 0.0) < life.learned["fire_rain"]:
            trees = getattr(world, "_tree_x", None) or [world.w * 0.3]
            t_ = min(trees, key=lambda t: abs(t - cr.x))
            cand["fire_cook"] = (g.hunger * (0.6 + ev_cook - ev_raw),
                                 ("wood", t_) if sv.inv["wood"] < 3 else ("build", cr.x))
    # shot range: the stand-off she expects to hit from without spooking it
    kinds = ("rabbit", "deer")

    def range_value(r):
        v = 0.0
        for k_ in kinds:
            hit, _d, ch = x.predict("shoot", {"who": k_, "kind": k_, "range": int(r)})
            spook, _d, cs = x.predict("stalk", {"who": k_, "kind": k_, "range": int(r)})
            v += hit * ch + spook * cs
        return v
    best_r = life.learned.get("shot_range", 7.0)
    best_v = range_value(best_r)
    for r in (4.5, 6.0, 7.5):
        v = range_value(r)
        if v > best_v + 0.05:                                  # only evidence moves it
            best_r, best_v = r, v
    life.learned["shot_range"] = best_r
    # calling a friend who isn't here: worth it in proportion to how calls went
    if fa and g.social > 0.45:
        friends = [(k, op) for k, op in life.animals.items() if op.get("name")]
        here = {str(o.psy.seed) for o in fa.animals if getattr(o, "psy", None) and abs(o.x - cr.x) < 6 * H}
        for k, op in friends:
            if k in here or life.clock - getattr(life, "_px_last_call", -1e9) < 40:
                continue
            ev, _d, conf = x.predict("call", {"who": k, "kind": op["sp"], "dark": dark})
            cand[f"call:{k}"] = (g.social * (0.35 + ev * conf) + 0.05, ("call", cr.x))
            break


def _px_on_act(sv, app, dt):
    """Handles the call action and watches outcomes of pending predictions."""
    life, x = _px_jane(app)
    cr, fa, world = app.creature, getattr(app, "fauna", None), app.world
    H = cr._Hb()
    dark = int(world.daypart in ("evening", "night"))
    # --- a call: a signal, whose meaning each animal learns for itself -------
    if sv.task and sv.task[0] == "call":
        name = getattr(sv, "_cand", "") or ""
        seed = name.split(":")[1] if ":" in name else None
        cr.speaking = max(cr.speaking, 1.2)
        if fa is not None:
            fa.signals = (getattr(fa, "signals", []) + [(fa.clock, cr.x)])[-6:]
        op = life.animals.get(seed) if seed else None
        life._px_last_call = life.clock
        sv._px_call = {"seed": seed, "t0": life.clock, "sp": op["sp"] if op else "animal",
                       "name": (op or {}).get("name") or "it"}
        app.brain.perceive(Event("social", f"called out for {sv._px_call['name']}", salience=0.4, valence=0.1))
        sv.task = None
        return True
    pc = getattr(sv, "_px_call", None)
    if pc and fa is not None:
        came = any(getattr(o, "psy", None) and str(o.psy.seed) == pc["seed"] and abs(o.x - cr.x) < 4 * H
                   for o in fa.animals)
        if came or life.clock - pc["t0"] > 25:
            ctx = {"who": pc["seed"], "kind": pc["sp"], "dark": dark}
            pe, s, conf = x.update("call", ctx, "came" if came else "ignored", 0.6 if came else -0.2)
            _px_surprise(app, f"called {pc['name']} and {'it came running' if came else 'it never came'}"
                              f" - {'not what I expected' if pe * (1 if came else -1) > 0 else 'as I thought'}", pe, conf)
            sv._px_call = None
    # --- approach outcome ------------------------------------------------------------
    pa = getattr(sv, "_px_app", None)
    if pa and not pa["done"] and fa is not None:
        a = next((o for o in fa.animals if getattr(o, "psy", None) and o.psy.seed == pa["seed"]), None)
        outcome = None
        if a is None or a.state == "flee" or (a is not None and abs(a.x - cr.x) > pa["d0"] + 2.5 * H):
            outcome, val = "retreated", -0.5
        elif abs(a.x - cr.x) < 1.6 * H:
            outcome, val = ("welcomed", 0.7) if a.state in ("follow", "excited", "play", "sniff", "beg") else ("stayed", 0.35)
        elif life.clock - pa["t0"] > 12:
            outcome, val = "avoided", -0.3
        if outcome:
            pa["done"] = True
            pe, s, conf = x.update(pa["mode"], pa["ctx"], outcome, val)
            if a is not None and a.psy is not None:
                op = life.opinion(a.psy)
                who = op["name"] or f"the {a.sp}"
                _px_surprise(app, f"went up to {who} {'slowly' if pa['mode'] == 'approach_slow' else 'directly'}"
                                  f" and it {outcome} - I expected otherwise", pe, conf)
            sv._px_app = None if outcome != "stayed" and outcome != "welcomed" else pa
    # --- fire lifetime vs the weather it was lit in ---------------------------------------
    f = sv.fire
    wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
    if f is not None and getattr(f, "_px", None) is None:
        f._px = {"rain": _bucket(wx.get("precip", 0.0), (0.25, 0.5, 0.75)), "t0": life.clock}
    tracked = getattr(sv, "_px_fire", None)
    if f is not None and tracked is not f:
        sv._px_fire = f
    if tracked is not None and (not tracked.lit or f is not tracked):
        age = life.clock - tracked._px["t0"]
        drowned = age < 90 and wx.get("precip", 0.0) > 0.4
        pe, s, conf = x.update("light_fire", {"who": "fire", "kind": "fire", "rain": tracked._px["rain"]},
                               "drowned" if drowned else "lasted", -0.6 if drowned else 0.5)
        if drowned:
            _px_surprise(app, "the rain beat my fire - I thought it would hold", pe, conf)
        sv._px_fire = f if f is not tracked else None
    return False


_px_prev_act = Survival._act


def _px_act(self, app, dt):
    try:
        if _px_on_act(self, app, dt):
            return
    except Exception:
        traceback.print_exc()
    was = dict(self.inv)
    hunger0 = app.brain.goals.hunger
    kind0 = self.task[0] if self.task else None
    stuck0 = sum(1 for ar in self.arrows if ar["stuck"] > 0)
    _px_prev_act(self, app, dt)
    try:
        life, x = _px_jane(app)
        # food consequences: what eating raw vs cooked actually did for her hunger
        relief = hunger0 - app.brain.goals.hunger
        if self.inv.get("berries", 0) < was.get("berries", 0) and relief > 0.01:
            x.update("cook" if kind0 == "cook" else "eat_raw", {"who": "food", "kind": "berries"},
                     "sated" if relief > 0.35 else "snack", round(relief, 3))
        # shots: hit or miss, from the range she chose
        ps = getattr(self, "_px_shot", None)
        if ps:
            stuck1 = sum(1 for ar in self.arrows if ar["stuck"] > 0)
            if self.inv.get("meat", 0) > was.get("meat", 0):
                x.update("shoot", ps["ctx"], "hit", 0.7)
                self._px_shot = None
            elif stuck1 > stuck0:
                pe, s, conf = x.update("shoot", ps["ctx"], "miss", -0.3)
                _px_surprise(app, "missed a shot I was sure of", pe, conf)
                self._px_shot = None
        # stalking: did the quarry hold still long enough?
        q = self.quarry
        st = getattr(self, "_px_stalk", None)
        if self.task and self.task[0] == "hunt" and q is not None and st is None:
            self._px_stalk = {"kind": q.sp, "range": int(life.learned.get("shot_range", 7.0)), "q": q}
        elif st is not None:
            if st["q"].state == "flee" and self.draw_t < 0.99:
                x.update("stalk", {"who": st["kind"], "kind": st["kind"], "range": st["range"]}, "spooked", -0.4)
                self._px_stalk = None
            elif getattr(self, "_px_shot", None) or st["q"].dead:
                x.update("stalk", {"who": st["kind"], "kind": st["kind"], "range": st["range"]}, "held", 0.15)
                self._px_stalk = None
    except Exception:
        traceback.print_exc()


Survival._act = _px_act

_px_prev_release = Survival._release


def _px_release(self, app, q):
    _px_prev_release(self, app, q)
    try:
        life, _x = _px_jane(app)
        H = app.creature._Hb()
        self._px_shot = {"ctx": {"who": q.sp, "kind": q.sp,
                                 "range": int(round(min(7.5, max(4.5, abs(q.x - app.creature.x) / H))))}}
    except Exception:
        pass


Survival._release = _px_release

# persistence: Jane's expectations live in her life record
_px_prev_life_to = JaneLife.to_dict
_px_prev_life_from = JaneLife.from_dict


def _px_life_to(self):
    d = _px_prev_life_to(self)
    if getattr(self, "exp", None) is not None:
        d["exp"] = self.exp.to_dict()
    return d


def _px_life_from(self, d):
    _px_prev_life_from(self, d)
    if isinstance(d, dict) and isinstance(d.get("exp"), dict):
        try:
            self.exp = Expectations.from_dict(d["exp"])
        except Exception:
            self.exp = None


JaneLife.to_dict = _px_life_to
JaneLife.from_dict = _px_life_from

# install into M40's hook points (shared namespace)
_m41_adjust = _px_adjust
_m41_chose = _px_chose
_m41_plan_adjust = _px_plan_adjust
_m41_approach = _px_approach
