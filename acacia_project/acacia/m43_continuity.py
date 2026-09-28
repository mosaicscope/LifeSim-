# ============================================================================
# [NEW] M43 - WORLD CONTINUITY  +  M45 - A CONTINUOUS LIFETIME
# ============================================================================
#
# M43: the world is saved with a real-time timestamp (inside the existing
# living_mind.json, written on exit via save_all and every 2 minutes). On
# reopening, elapsed real time is simulated for the SAME world in coarse
# hourly steps (capped at 60 days): weather, the fire burning down, storm
# wear on her home, regrowth, Jane living on her own (sleeping at night,
# foraging, pursuing her unfinished plan through the M42 planner's own
# action effects), resident animals living (bonds, births, losses), and any
# registered subsystem (the M46 society). What happened becomes memories.
#
# M45: Jane's life is continuous: days lived and age follow real time,
# significant experiences become milestones, milestones become chapters,
# and the story so far is part of how she understands herself.

import time as _ct_time
import random as _ct_random

_m43_offline_hooks = []          # fn(app, elapsed_seconds, report) - other systems advance too
_m43_save_hooks = []             # fn(app) -> (key, data)
_m43_load_hooks = []             # fn(app, world_dict)


def _ct_human(sec):
    d, h = int(sec // 86400), int(sec % 86400 // 3600)
    m = int(sec % 3600 // 60)
    if d:
        return f"{d} day{'s' if d != 1 else ''}" + (f" and {h} hour{'s' if h != 1 else ''}" if h else "")
    if h:
        return f"{h} hour{'s' if h != 1 else ''}"
    return f"{m} minute{'s' if m != 1 else ''}"


# ---- save --------------------------------------------------------------------
_ct_prev_to = LivingMind.to_dict
_ct_prev_from = LivingMind.from_dict


def _ct_to(self):
    d = _ct_prev_to(self)
    try:
        app = getattr(self, "_app_ref", None)
        w = {"saved_at": _ct_time.time(), "born_at": getattr(self, "_born_at", _ct_time.time())}
        if app is not None:
            sv = getattr(app, "survival", None)
            f = sv.fire if sv else None
            w["fire"] = {"x": f.x, "fuel": f.fuel, "lit": f.lit} if f else None
            w["pois"] = {p.kind: [p.stock, p.empty_since] for p in app.world.pois if p.kind in ("food", "water")}
            for hook in _m43_save_hooks:
                try:
                    k, v = hook(app)
                    w[k] = v
                except Exception:
                    pass
        elif isinstance(getattr(self, "_world_saved", None), dict):
            prev = dict(self._world_saved)
            prev.update(w)
            w = prev
        d["world"] = w
    except Exception:
        pass
    return d


def _ct_from(self, d):
    _ct_prev_from(self, d)
    if isinstance(d, dict) and isinstance(d.get("world"), dict):
        self._world_saved = d["world"]
        self._born_at = float(d["world"].get("born_at", _ct_time.time()))


LivingMind.to_dict = _ct_to
LivingMind.from_dict = _ct_from


# ---- offline advance ----------------------------------------------------------------
def _ct_offline(app, w):
    mind, b = app.brain.mind, app.brain
    now = _ct_time.time()
    elapsed = max(0.0, now - float(w.get("saved_at", now)))
    report = []
    if elapsed < 60:
        return 0.0, report
    E = min(elapsed, 60 * 86400.0)
    rnd = _ct_random.Random(int(w.get("saved_at", 0)))
    life = _lf_life(app)
    # weather: really stepped for the first two hours, then sampled
    sim = getattr(app, "weather_sim", None)
    storms = 0
    if sim is not None:
        for _ in range(int(min(E, 7200) / 5)):
            sim.update(5.0)
        if E > 7200:
            try:
                sim.force(rnd.choice(("clear", "cloudy", "overcast", "drizzle", "rain", "clear", "fog")))
            except Exception:
                pass
    hours = int(E // 3600)
    # the fire burned down
    fs = w.get("fire")
    if fs and app.survival is not None:
        fuel = fs["fuel"] - E / 240.0
        if fuel > 0 and fs["lit"]:
            fire = Campfire(fs["x"])
            fire.fuel = fuel
            app.survival.fire = fire
        elif fs["lit"]:
            report.append(("the campfire burned out while I was away", 0.35, -0.05))
    # resources regrow (POI empty_since is wall-clock based: restore as saved)
    for p in app.world.pois:
        st = (w.get("pois") or {}).get(p.kind)
        if st:
            p.stock, p.empty_since = int(st[0]), float(st[1] or 0.0)
    # Jane lives on: nights asleep, days foraging and pursuing her plan
    s_inv = app.survival.inv if app.survival is not None else life.inv
    plan = getattr(life, "plan", None)
    built = 0
    for hr in range(hours):
        lt = _ct_time.localtime(float(w.get("saved_at", now)) + hr * 3600)
        night = lt.tm_hour < 6 or lt.tm_hour >= 21
        stormy = rnd.random() < 0.06
        storms += stormy
        if life.home and stormy:
            life.home["cond"] = max(0.0, life.home["cond"] - 0.08 * (1.5 - 0.3 * life.home["stage"]))
        if night:
            continue
        if rnd.random() < 0.35:
            s_inv["wood"] = min(8, s_inv.get("wood", 0) + 1)         # she gathers as she goes
        if plan and rnd.random() < 0.5:
            s = _ag_state(app, app.survival, life)
            s["fire"] = 0
            while plan and plan["i"] < len(plan["steps"]):
                n = plan["steps"][plan["i"]]
                a = _ag_lib().get(n)
                if a is None or not _ag_applicable(a, s):
                    break
                s2 = _ag_apply(a, s)
                if n == "build_home":
                    life.home = life.home or {"x": _ag_where(app, app.survival, life, "homesite", {}) or app.world.w * 0.3,
                                              "stage": 0, "cond": 1.0}
                    life.home["stage"] += 1
                    life.home["cond"] = 1.0
                    built += 1
                    report.append(({1: "built a lean-to on my own", 2: "raised the walls of my shelter",
                                    3: "finished the hut - a door and a bed"}.get(life.home["stage"], "worked on my home"),
                                   0.7, 0.5))
                elif n == "repair_home" and life.home:
                    life.home["cond"] = 1.0
                for k in ("wood", "berries", "meat", "bow"):
                    if k in s2:
                        s_inv[k] = max(0, int(s2[k]))
                s = s2
                plan["i"] += 1
                break
            if plan and plan["i"] >= len(plan["steps"]):
                life.plan = plan = None
    if storms >= 3:
        report.append((f"sat out {storms} rough spells of weather", 0.45, -0.1))
    if life.home and life.home["cond"] < 0.6:
        report.append(("storms have damaged my shelter", 0.55, -0.3))
    # body: she has looked after herself
    P = life.phys
    P.update({"sleep_pressure": 0.15, "bladder": 0.2, "hygiene": max(0.5, P["hygiene"] - 0.02 * hours),
              "pain": max(0.0, P["pain"] - E / 500.0)})
    b.goals.hunger, b.goals.thirst = 0.35, 0.3
    b.goals.social = min(1.0, b.goals.social + 0.02 * hours)
    # resident animals lived too
    pop = list(getattr(mind, "_fauna_saved", None) or [])
    days = E / 86400.0
    named = {k: op for k, op in life.animals.items() if op.get("name")}
    survivors = []
    for d in pop:
        sp = d.get("sp")
        risk = {"rabbit": 0.03, "deer": 0.01, "bird": 0.02}.get(sp, 0.005) * days
        op = named.get(str(d.get("seed")))
        if rnd.random() < risk:
            if op:
                report.append((f"{op['name']} the {sp} is gone - I haven't seen it since", 0.7, -0.5))
            continue
        rel = (d.get("rel") or {}).get("jane")
        if rel and op and hours:
            rel["fam"] = min(1.0, rel["fam"] + 0.02 * days)
            rel["like"] = min(1.0, rel["like"] + 0.03 * days * rel.get("trust", 0.3))
            op["like"] = min(1.0, op["like"] + 0.02 * days)
        d["x"] = None                                            # out and about when she returns
        survivors.append(d)
    by_sp = {}
    for d in survivors:
        by_sp.setdefault(d["sp"], []).append(d)
    for sp, grp in by_sp.items():
        if len(grp) >= 2 and sp in ("rabbit", "deer", "bird", "fox") and rnd.random() < min(0.8, 0.12 * days):
            seed = rnd.getrandbits(31)
            baby = Psyche(sp, seed).to_dict()
            baby["x"] = None
            survivors.append(baby)
            report.append((f"there are young {sp}s in the valley now", 0.5, 0.3))
    mind._fauna_saved = survivors[:24]
    for hook in _m43_offline_hooks:
        try:
            hook(app, E, report)
        except Exception:
            traceback.print_exc()
    return E, report


def _ct_welcome(app, E, report):
    b = app.brain
    dur = _ct_human(E)
    b.perceive(Event("time", f"{dur} passed while I was on my own", salience=0.6, valence=0.05))
    for text, imp, val in report[:8]:
        b.memory.remember("episode", text, importance=imp, emotion=b.emotion.emotion, valence=val, subject="self")
    try:
        _lf_think(b, b.mind, f"{dur} on my own. " + (report[0][0] if report else "Quiet, mostly."), "memory")
    except Exception:
        pass


# ---- M45: a continuous lifetime --------------------------------------------------------
_CT_THEMES = {"home": "building a home", "animal": "the animals", "survival": "learning to live off the land",
              "news": "news from the settlements", "trade": "traders and bargains", "time": "time alone",
              "injury": "hard knocks", "social": "company"}


def _ct_life(app):
    life = _lf_life(app)
    if not hasattr(life, "milestones"):
        saved = getattr(life, "_ct_saved", None) or {}
        life.milestones = list(saved.get("milestones", []))
        life.chapters = list(saved.get("chapters", []))
        life.firsts = set(saved.get("firsts", []))
    return life


def _ct_days(app):
    born = getattr(app.brain.mind, "_born_at", None)
    if born is None:
        born = app.brain.mind._born_at = _ct_time.time()
    return (_ct_time.time() - born) / 86400.0


def _ct_milestone(app, kind, text, sal):
    life = _ct_life(app)
    theme = kind if kind in _CT_THEMES else ("animal" if "animal" in kind else None)
    if theme is None:
        return
    first = theme + ":" + text.split()[0]
    if sal < 0.7 and first in life.firsts:
        return
    life.firsts.add(first)
    day = round(_ct_days(app), 2)
    life.milestones.append({"day": day, "theme": theme, "text": text})
    del life.milestones[:-60]
    since = [m for m in life.milestones if m["day"] > (life.chapters[-1]["to"] if life.chapters else -1)]
    span = day - (since[0]["day"] if since else day)
    if len(since) >= 5 or (since and span >= 7):
        counts = {}
        for m in since:
            counts[m["theme"]] = counts.get(m["theme"], 0) + 1
        top = max(counts, key=counts.get)
        life.chapters.append({"from": since[0]["day"], "to": day, "title": _CT_THEMES[top],
                              "summary": "; ".join(m["text"] for m in since[-3:])})
        del life.chapters[:-12]
        app.brain.memory.remember("episode", f"a new chapter of my life: {_CT_THEMES[top]}", importance=0.75,
                                  emotion=app.brain.emotion.emotion, valence=0.2, subject="self")


_ct_prev_perceive = Brain.perceive


def _ct_perceive(self, event):
    r = _ct_prev_perceive(self, event)
    try:
        app = getattr(self.mind, "_app_ref", None)
        if app is not None and getattr(event, "salience", 0) >= 0.55:
            _ct_milestone(app, event.kind, event.text, event.salience)
    except Exception:
        pass
    return r


Brain.perceive = _ct_perceive

_ct_prev_life_to = JaneLife.to_dict
_ct_prev_life_from = JaneLife.from_dict


def _ct_life_to(self):
    d = _ct_prev_life_to(self)
    d["milestones"] = getattr(self, "milestones", [])
    d["chapters"] = getattr(self, "chapters", [])
    d["firsts"] = sorted(getattr(self, "firsts", set()))
    return d


def _ct_life_from(self, d):
    _ct_prev_life_from(self, d)
    if isinstance(d, dict):
        self._ct_saved = {k: d.get(k) or [] for k in ("milestones", "chapters", "firsts")}


JaneLife.to_dict = _ct_life_to
JaneLife.from_dict = _ct_life_from

_ct_prev_sys = Brain.build_system_prompt


def _ct_sys(self, decision, recalled, perception):
    text = _ct_prev_sys(self, decision, recalled, perception)
    try:
        app = getattr(self.mind, "_app_ref", None)
        if app is None:
            return text
        life = _ct_life(app)
        days = _ct_days(app)
        age = 28 + days / 365.25
        chap = "; ".join(f"'{c['title']}'" for c in life.chapters[-3:])
        last = "; ".join(m["text"] for m in life.milestones[-3:])
        line = (f"- your life so far: day {days:.0f} of your life here (you are {age:.0f})"
                + (f"; chapters: {chap}" if chap else "") + (f"; lately: {last}" if last else ""))
        marker = "--- how to reply ---"
        return text.replace(marker, line + "\n" + marker, 1) if marker in text else text
    except Exception:
        return text


Brain.build_system_prompt = _ct_sys


# ---- wiring ----------------------------------------------------------------------------------
_ct_prev_update = App._update_world


def _ct_update(self, dt):
    mind = self.brain.mind
    mind._app_ref = self
    if not getattr(self, "_ct_loaded", False):
        self._ct_loaded = True
        w = getattr(mind, "_world_saved", None)
        if getattr(mind, "_born_at", None) is None:
            mind._born_at = _ct_time.time()
        if isinstance(w, dict):
            try:
                if getattr(self, "survival", None) is None:
                    self.survival = Survival()
                    self.survival.inv = _lf_life(self).inv
                for hook in _m43_load_hooks:
                    try:
                        hook(self, w)
                    except Exception:
                        traceback.print_exc()
                E, report = _ct_offline(self, w)
                if E >= 60:
                    self._ct_pending = (E, report)
            except Exception:
                traceback.print_exc()
    _ct_prev_update(self, dt)
    pend = getattr(self, "_ct_pending", None)
    if pend is not None:
        self._ct_pending = None
        try:
            _ct_welcome(self, *pend)
        except Exception:
            traceback.print_exc()
    t = _ct_time.time()
    if t - getattr(self, "_ct_autosave", t) > 120:
        self._ct_autosave = t
        try:
            self.brain.save_state()
        except Exception:
            pass
    elif not hasattr(self, "_ct_autosave"):
        self._ct_autosave = t


App._update_world = _ct_update
