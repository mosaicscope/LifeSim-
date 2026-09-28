# ============================================================================
# [NEW] LIFE  (patch layer, loaded last) - persistent individual lives
# ============================================================================
#
# Layered, periodic, fail-safe:
#   PERCEPTION -> NEEDS/PHYSIOLOGY -> PERSONALITY -> GOALS -> DECISION ->
#   ACTION -> CONSEQUENCE -> MEMORY/RELATIONSHIPS -> (changes future choices)
#
# * Every animal gets a Psyche: a seeded identity (traits, attachment style,
#   likes, quirks, learning rate, memory span), needs + light physiology,
#   episodic memory, per-entity relationships that change only through what
#   actually happens, favourite places and a home spot. It decides every
#   ~0.8 s (staggered) with personality-weighted utilities; the existing
#   Fauna motion/render/reflex code executes the choice.
# * Residents (animals that have lived here a while or met Jane) persist in
#   living_mind.json and keep living off-screen: they leave, get fed, sleep,
#   and come back.
# * JaneLife: physiology (sleep pressure, bladder, hygiene, body temperature,
#   sweat, pain/injury, body condition, digestion), place memory and
#   favourite spots, a home she chooses to build/improve/repair, individual
#   opinions of animals (she names the ones she bonds with), learned
#   adjustments from consequences, and a utility planner that replaces the
#   fixed survival priority list: needs x personality x opportunity -> task.
# Any failure in these layers falls back to the previous behaviour.

import math as _lf_math
import random as _lf_random
import time as _lf_time

FAUNA["dog"] = dict(size=11, speed=150, flee=60, active=("morning", "afternoon", "evening", "night"),
                    body="#8a6a4a", belly="#e6d6c0", cap=1, fear=0.35, curious=0.8,
                    domestic=True, social=True)

# animals sized against the adult (8-head) Jane: the table was authored for the
# old 4-head figure, where a deer came up to her ankle
_LF_SIZE = {"rabbit": 2.4, "deer": 2.0, "fox": 2.3, "wolf": 2.4, "dog": 2.3,
            "bird": 1.4, "butterfly": 1.0, "firefly": 1.0}
for _sp in FAUNA:
    FAUNA[_sp]["size"] = FAUNA[_sp]["size"] * _LF_SIZE.get(_sp, 2.0)

_LF_NAMES = ("Ada", "Kepler", "Noether", "Hopper", "Curie", "Pascal", "Euler", "Gauss", "Lovelace",
             "Darwin", "Tesla", "Juno", "Pip", "Biscuit", "Ember", "Moss", "Rook", "Sable", "Wren", "Clover")
_LF_QUIRKS = {
    "dog": ("tilts its head at every new sound", "circles three times before lying down",
            "carries a stick about for no reason", "sneezes when excited", "sulks when ignored"),
    "rabbit": ("thumps a hind foot at shadows", "grooms its ears obsessively", "freezes before it bolts"),
    "deer": ("stamps a hoof when uneasy", "always looks back once before leaving", "grazes in the same corner"),
    "fox": ("pounces at nothing in the grass", "stares at the fire from a distance", "hoards scraps"),
    "wolf": ("paces the treeline", "howls at the moon", "never turns its back"),
    "bird": ("sings at dawn", "hops rather than walks", "chases other birds off its perch"),
    "butterfly": ("loves the pink flowers", "circles the same bush"),
    "firefly": ("glows brightest near water",),
}
_LF_COATS = {"dog": (("#8a6a4a", "#e6d6c0"), ("#2b2622", "#b9aa98"), ("#c9a36a", "#f1e6cf"),
                     ("#e8e2d6", "#fbf8f2"), ("#6b5a4a", "#cbb8a0"), ("#4a3a30", "#d9b48a"))}


def make_identity(sp, seed):
    """Deterministic: the same seed always yields the same individual."""
    r = _lf_random.Random(seed)
    base = FAUNA.get(sp, {})
    t = {k: round(r.betavariate(2.2, 2.2), 3) for k in
         ("boldness", "curiosity", "sociability", "energy", "intelligence", "playfulness",
          "territoriality", "greed", "patience")}
    # species pulls on the dice: dogs are social and playful, deer skittish ...
    t["boldness"] = round(0.5 * t["boldness"] + 0.5 * (1.0 - base.get("fear", 0.5)), 3)
    t["curiosity"] = round(0.5 * t["curiosity"] + 0.5 * base.get("curious", 0.3), 3)
    if base.get("social"):
        t["sociability"] = round(0.4 * t["sociability"] + 0.6, 3)
        t["playfulness"] = round(0.5 * t["playfulness"] + 0.5, 3)
    if sp in ("fox", "wolf", "dog"):
        t["territoriality"] = round(0.5 * t["territoriality"] + 0.35, 3)
    attach = r.choices(("secure", "anxious", "avoidant", "independent"),
                       weights=(0.4 + t["sociability"], 0.25, 0.2 + (1 - t["sociability"]) * 0.4,
                                0.15 + (1 - t["sociability"]) * 0.5))[0]
    coat = r.choice(_LF_COATS[sp]) if sp in _LF_COATS else None
    return {
        "traits": t, "attachment": attach,
        "learning_rate": round(0.4 + 0.8 * t["intelligence"], 3),
        "memory_span": int(12 + 36 * t["intelligence"]),
        "likes": r.sample(("sunny spots", "the water's edge", "tall grass", "the treeline",
                           "quiet", "company", "the warmth of the fire"), 2),
        "dislikes": r.sample(("rain", "loud noises", "strangers", "the dark", "open ground", "smoke"), 2),
        "quirk": r.choice(_LF_QUIRKS.get(sp, ("keeps to itself",))),
        "coat": coat,
        "name": _LF_NAMES[seed % len(_LF_NAMES)],
    }


# prediction hooks (no-ops here; M41 installs the predictive substrate)
def _m41_adjust(psy, a, fa, world, jane, u):
    return u


def _m41_chose(psy, a, fa, world, jane, goal):
    return None


def _m41_plan_adjust(sv, app, life, cand):
    return None


def _m41_approach(sv, app, life, kind, subj):
    return 1.0


def _m42_decide(sv, app, life, cand, task):
    return None


def _m42_after(psy, a, fa, world, jane, goal):
    return None


class Psyche:
    """An animal's own mind. Relationships are never set directly - only
    learn() from interpreted events, scaled by this individual's learning
    rate and temperament."""

    def __init__(self, sp, seed):
        self.sp, self.seed = sp, int(seed)
        self.idn = make_identity(sp, self.seed)
        r = _lf_random.Random(self.seed + 1)
        self.need = {"hunger": r.uniform(0.1, 0.5), "thirst": r.uniform(0.1, 0.4),
                     "fatigue": r.uniform(0.0, 0.4), "social": 0.3, "boredom": 0.3}
        self.phys = {"stomach": 0.3, "condition": r.uniform(0.5, 0.8), "injury": 0.0}
        self.rel = {}
        self.mem = []
        self.places = {}
        self.home = None
        self.goal = "explore"
        self.prev_goal = None
        self.goal_commit_time = 0.0  # time spent on current goal (prevent rapid switching)
        self.next = r.uniform(0.0, 0.8)
        self.acc = 0.0
        self.jane_last = -1e9
        self.named = False
        self.age = 0.0
        self.resident = sp == "dog"

    # -- memory --------------------------------------------------------------
    def rel_of(self, who):
        return self.rel.setdefault(who, {"fam": 0.0, "trust": 0.2, "fear": 0.0, "like": 0.0, "n": 0})

    def learn(self, who, clock, text, val, **d):
        lr = self.idn["learning_rate"]
        R = self.rel_of(who)
        for k, v in d.items():
            cur = R.get(k, 0.0)
            # diminishing returns: feelings firm up gradually and resist extremes
            step = v * lr * ((1.0 - cur) if v > 0 else (0.3 + cur))
            R[k] = clamp01(cur + step * 0.6)
        R["n"] += 1
        self.mem.append((round(clock, 1), who, round(val, 2), text))
        self.mem = self.mem[-self.idn["memory_span"]:]

    def place_note(self, x, val):
        k = int(x // 60)
        self.places[k] = round(self.places.get(k, 0.0) * 0.9 + val, 3)

    def fav_x(self, default):
        if not self.places:
            return default
        k = max(self.places, key=self.places.get)
        return k * 60 + 30

    def to_dict(self):
        return {"sp": self.sp, "seed": self.seed, "need": self.need, "phys": self.phys,
                "rel": self.rel, "mem": self.mem[-20:], "places": self.places, "home": self.home,
                "named": self.named, "age": round(self.age, 1), "goal": self.goal, "prev_goal": self.prev_goal,
                "goal_commit_time": round(self.goal_commit_time, 1)}

    @classmethod
    def from_dict(cls, d):
        p = cls(d["sp"], d["seed"])
        for key in ("need", "phys", "rel", "places"):
            if isinstance(d.get(key), dict):
                getattr(p, key).update(d[key])
        p.mem = [tuple(m) for m in d.get("mem", []) if isinstance(m, (list, tuple)) and len(m) == 4]
        p.home, p.named, p.age = d.get("home"), bool(d.get("named")), float(d.get("age", 0.0))
        p.goal = d.get("goal", "explore")
        p.prev_goal = d.get("prev_goal")
        p.goal_commit_time = float(d.get("goal_commit_time", 0.0))
        p.resident = True
        return p

    # -- the periodic mind ---------------------------------------------------------
    def drive(self, a, fa, world, jane, dt):
        """Returns True when it chose this tick (the old random wander is skipped)."""
        self.acc += dt
        self.age += dt
        self.next -= dt
        t = self.idn["traits"]
        S = a.S
        # physiology every frame (cheap)
        night = world.daypart not in S["active"]
        rest = a.state in ("sleep", "perch")
        self.need["hunger"] = clamp01(self.need["hunger"] + dt * 0.0035 * (0.7 + 0.6 * t["energy"]))
        self.need["thirst"] = clamp01(self.need["thirst"] + dt * 0.0045)
        self.need["fatigue"] = clamp01(self.need["fatigue"] + dt * (-0.02 if rest else 0.0025 * (1.6 if night else 1.0)))
        self.need["social"] = clamp01(self.need["social"] + dt * 0.002 * t["sociability"])
        self.need["boredom"] = clamp01(self.need["boredom"] + dt * 0.003 * t["curiosity"])
        dig = min(self.phys["stomach"], dt * 0.004)
        self.phys["stomach"] -= dig
        self.phys["condition"] = clamp01(self.phys["condition"] + dig * 0.3 - dt * 0.0002 * (self.need["hunger"] > 0.8))
        self.phys["injury"] = max(0.0, self.phys["injury"] - dt * 0.002)
        if a.state == "graze" and S.get("prey"):
            self.need["hunger"] = max(0.0, self.need["hunger"] - dt * 0.03)
            self.phys["stomach"] = min(1.0, self.phys["stomach"] + dt * 0.02)
        if a.state == "drink":
            self.need["thirst"] = max(0.0, self.need["thirst"] - dt * 0.12)
        if a.state in ("approach", "follow", "play", "sniff") and self.goal in ("social", "jane", "follow", "play"):
            self.need["social"] = max(0.0, self.need["social"] - dt * 0.02)
        if a.state in ("wander", "sniff"):
            self.need["boredom"] = max(0.0, self.need["boredom"] - dt * 0.01)
        if self.next > 0.0:
            return self.goal is not None
        self.next = 0.7 + 0.3 * _lf_random.random()
        span = self.acc
        self.acc = 0.0
        H = jane._Hb() if jane is not None else 30.0
        # ---- perception + interpretation of Jane --------------------------------
        jx = jane.x if jane is not None else None
        R = self.rel_of("jane")
        dj = abs(a.x - jx) if jx is not None else 1e9
        sense = (14 if a.sp == "dog" else 9) * H
        if dj < sense:
            jspeed = abs(getattr(getattr(jane, "_loco", None), "vx", 0.0))
            away = fa.clock - self.jane_last
            if away > 45 and R["like"] > 0.45 and self.jane_last > 0:
                self.goal = "greet"                                   # she's back!
                self.learn("jane", fa.clock, "Jane came back", 0.4, like=0.03)
                fa.jane_events.append(("greet", a))
            self.jane_last = fa.clock
            jvx = getattr(getattr(jane, "_loco", None), "vx", 0.0)
            toward = (jvx > 0) == (a.x > jx)                          # moving AT this animal
            if (jspeed > 210 and toward and dj < 5 * H
                    and self.goal not in ("follow", "play", "greet")):
                self.learn("jane", fa.clock, "Jane rushed at me", -0.2,
                           fear=0.06 * (1.0 - t["boldness"]), trust=-0.02)
            elif dj < 4 * H:
                self.learn("jane", fa.clock, "Jane was near and calm", 0.05,
                           fam=0.02, trust=0.012 * (0.5 + t["sociability"]), fear=-0.01,
                           like=0.006 * (0.4 + t["sociability"]))
            else:
                self.learn("jane", fa.clock, "saw Jane", 0.0, fam=0.008)
        # other animals: kin, friends, threats
        near = [o for o in fa.animals if o is not a and abs(o.x - a.x) < 7 * H and getattr(o, "psy", None)]
        for o in near[:4]:
            key = f"{o.sp}:{o.psy.seed}"
            if o.S.get("predator") == a.sp or (o.S.get("danger") and not S.get("danger")):
                self.learn(key, fa.clock, f"a {o.sp} was near", -0.3, fear=0.08)
            elif o.sp == a.sp:
                self.learn(key, fa.clock, f"time with another {o.sp}", 0.1, fam=0.03, like=0.02 * t["sociability"])
        # ---- utilities: needs x personality x opportunity -----------------------------
        n = self.need
        fear_j = R["fear"]
        like_j = R["like"] * (1.0 - fear_j)
        u = {
            "eat": n["hunger"] * (1.1 + 0.4 * t["greed"]),
            "drink": n["thirst"] * 1.15,
            "sleep": n["fatigue"] * (1.5 if night else 0.8),
            "explore": 0.15 + n["boredom"] * (0.5 + t["curiosity"]),
            "social": n["social"] * t["sociability"] * (1.0 if any(o.sp == a.sp for o in near) else 0.3),
        }
        if jx is not None and dj < sense and not S.get("flutter"):
            novelty = 1.0 - R["fam"]
            u["jane"] = (novelty * t["curiosity"] * 0.6 + like_j * (0.4 + n["social"])
                         + (0.3 + 0.3 * n["social"] if S.get("domestic") else 0.0)) * (1.0 - fear_j) \
                * (0.6 + 0.8 * t["boldness"])
            u["avoid"] = fear_j * (1.2 - t["boldness"])
            if S.get("domestic") or t["sociability"] > 0.7:
                attach = like_j * R["trust"]
                u["follow"] = attach * (1.3 if self.idn["attachment"] == "anxious" else
                                        0.6 if self.idn["attachment"] in ("avoidant", "independent") else 1.0)
                u["play"] = t["playfulness"] * like_j * (1.0 - n["fatigue"]) * 0.8
                if n["hunger"] > 0.5 and R["trust"] > 0.35 and fa.jane_has_food:
                    u["beg"] = n["hunger"] * R["trust"]
            if S.get("danger") and night:
                u["stalk"] = 0.5 + 0.4 * n["hunger"] - 0.6 * t["patience"] * (fa.fire_x is not None)
        if t["territoriality"] > 0.55 and self.home is not None:
            u["patrol"] = 0.2 + 0.4 * t["territoriality"] * (1.0 - n["fatigue"])
        if self.goal == "greet":
            u["greet"] = 1.5
        try:
            u = _m41_adjust(self, a, fa, world, jane, u) or u          # expectations shape choice
        except Exception:
            pass
        # --- commitment: don't thrash between goals ---
        self.goal_commit_time += span
        min_commit = (1.2 if t["energy"] > 0.6 else 2.0) / (1.0 + t["patience"])  # energetic animals commit less
        if self.goal in u:
            u[self.goal] += 0.12 + 0.15 * min(1.0, self.goal_commit_time / max(0.1, min_commit))
        goal = max(u, key=u.get)
        try:
            _m41_chose(self, a, fa, world, jane, goal)
        except Exception:
            pass
        if goal != self.goal:
            if self.goal_commit_time < min_commit * 0.6:  # too soon to switch
                goal = self.goal  # stay with current goal
            else:
                self.prev_goal = self.goal
                self.goal_commit_time = 0.0
                if goal in ("follow", "play") and self.goal not in ("follow", "play"):
                    self.learn("jane", fa.clock, "chose to stay with Jane", 0.2, like=0.01)
        self.goal = goal
        # ---- act: choose state + target (Fauna executes motion/render) ------------------
        wx_ = world.poi("water")
        if goal == "eat":
            if S.get("predator") and n["hunger"] > 0.4:
                return True                                              # existing hunt logic
            if S.get("flyer"):
                a.state, a.goal = "perch", a.x
            elif S.get("flutter"):
                a.state = "wander"
            else:
                a.state = "graze" if S.get("prey") else "sniff"
                a.goal = a.x
            if S.get("flyer") or S.get("flutter"):
                self.need["hunger"] = max(0.0, n["hunger"] - span * 0.02)
            if S.get("domestic"):                                        # scavenge
                self.need["hunger"] = max(0.0, n["hunger"] - span * 0.01)
            self.place_note(a.x, 0.3)
        elif goal == "drink" and wx_ is not None:
            if abs(a.x - wx_.x) > 20:
                a.state, a.goal = "approach", wx_.x
            else:
                a.state, a.goal = "drink", a.x
                self.place_note(a.x, 0.2)
        elif goal == "sleep":
            home = self.home if self.home is not None else self.fav_x(a.x)
            if abs(a.x - home) > 25:
                a.state, a.goal = "wander", home
            else:
                a.state, a.goal = ("perch" if S.get("flyer") else "sleep"), a.x
                if self.home is None:
                    self.home = a.x
                self.place_note(a.x, 0.4)
        elif goal == "explore":
            if abs(a.x - a.goal) < 10 or a.state not in ("wander", "fly"):
                lo, hi = -40, world.w + 40
                if self.home is not None and not S.get("flyer"):
                    rng = (220 + 300 * t["curiosity"])
                    lo, hi = self.home - rng, self.home + rng
                a.goal = _lf_random.uniform(max(-40, lo), min(world.w + 40, hi))
                a.state = "fly" if S.get("flyer") else "wander"
            if _lf_random.random() < 0.25 and not S.get("flyer"):
                a.state = "sniff"
        elif goal == "social":
            kin = [o for o in near if o.sp == a.sp]
            if kin:
                best = max(kin, key=lambda o: self.rel_of(f"{o.sp}:{o.psy.seed}")["like"])
                a.state, a.goal = "approach", best.x + (18 if best.x < a.x else -18)
        elif goal in ("jane", "greet"):
            side = 1 if a.x >= jx else -1
            stop = jx + side * 1.4 * H
            if abs(a.x - stop) > 12:
                a.state, a.goal = ("excited" if goal == "greet" else "approach"), stop
            else:
                a.state, a.goal = ("excited" if goal == "greet" else "sniff"), a.x
                if goal == "jane" and R["n"] % 5 == 0:
                    self.learn("jane", fa.clock, "sniffed and investigated Jane", 0.2, fam=0.05, like=0.02)
                    fa.jane_events.append(("sniff", a))
                if goal == "greet":
                    self.goal = "follow"
        elif goal == "follow":
            side = 1 if a.x >= jx else -1
            a.goal = jx + side * 1.8 * H
            a.state = "follow" if abs(a.x - a.goal) > 12 else "sniff"
            fa.jane_events.append(("follow", a))
        elif goal == "play":
            a.state = "play"
            a.goal = jx + _lf_random.choice((-1, 1)) * _lf_random.uniform(1.5, 4.0) * H
            fa.jane_events.append(("play", a))
        elif goal == "beg":
            a.state, a.goal = ("beg" if dj < 2 * H else "approach"), jx + (1 if a.x >= jx else -1) * 1.3 * H
            fa.jane_events.append(("beg", a))
        elif goal == "avoid":
            a.state, a.goal = "wander", a.x + (1 if a.x >= jx else -1) * 8 * H
        elif goal == "stalk":
            a.state, a.goal = "stalk", jx + (1 if a.x >= jx else -1) * 5 * H
        elif goal == "patrol":
            a.state = "wander"
            if abs(a.x - a.goal) < 10:
                a.goal = self.home + _lf_random.uniform(-250, 250)
        try:
            _m42_after(self, a, fa, world, jane, goal)
        except Exception:
            pass
        # a home range emerges where it rests/eats most
        if self.home is None and self.age > 60:
            self.home = self.fav_x(a.x)
        if self.age > 90 or R["fam"] > 0.15:
            self.resident = True
        return True


# ---- Fauna integration: every animal gets a Psyche; residents persist ------------
_lf_prev_animal_init = Animal.__init__


def _lf_animal_init(self, species, x, y, rng, juvenile=False):
    _lf_prev_animal_init(self, species, x, y, rng, juvenile)
    try:
        self.psy = Psyche(species, rng.getrandbits(31))
        coat = self.psy.idn.get("coat")
        if coat:
            self.S = dict(self.S, body=coat[0], belly=coat[1])
        else:
            tint = _lf_random.Random(self.psy.seed).uniform(-0.08, 0.08)
            self.S = dict(self.S, body=_shade(self.S["body"], 1.0 + tint))
    except Exception:
        self.psy = None


Animal.__init__ = _lf_animal_init

_lf_prev_fauna_init = Fauna.__init__


def _lf_fauna_init(self, seed=7):
    _lf_prev_fauna_init(self, seed)
    self.clock = 0.0
    self.away = []              # residents living off-screen: (return_time, side, Psyche, sp)
    self.jane_events = []
    self.jane_has_food = False
    self.fire_x = None


Fauna.__init__ = _lf_fauna_init

_lf_prev_fauna_update = Fauna.update


def _lf_fauna_update(self, dt, world, jane):
    self.clock = getattr(self, "clock", 0.0) + dt
    before = {id(a): a for a in self.animals}
    for a in self.animals:
        psy = getattr(a, "psy", None)
        a._psy_ok = False
        if psy is None or (a.fear > 0.45 and a.S["flee"] > 0) or a.state == "hunt":
            continue
        try:
            a._psy_ok = psy.drive(a, self, world, jane, dt)
        except Exception:
            a.psy = None                                   # safe fallback: old behaviour
    _lf_prev_fauna_update(self, dt, world, jane)
    alive = {id(a) for a in self.animals}
    for key, a in before.items():
        psy = getattr(a, "psy", None)
        if key not in alive and psy is not None and psy.resident and not getattr(a, "_killed", False):
            # a resident wandered off: it keeps living off-screen and comes back
            side = -1 if a.x < world.w * 0.5 else 1
            self.away.append([self.clock + _lf_random.uniform(40, 160), side, psy, a.sp])
    back = [w for w in self.away if w[0] <= self.clock]
    self.away = [w for w in self.away if w[0] > self.clock]
    for _t, side, psy, sp in back:
        if world.daypart not in FAUNA[sp]["active"] and not FAUNA[sp].get("domestic"):
            self.away.append([self.clock + 60, side, psy, sp])
            continue
        a = Animal(sp, -30 if side < 0 else world.w + 30, world.ground, self.rng)
        psy.need["hunger"] *= 0.4                          # it found food out there
        psy.need["fatigue"] *= 0.3
        a.psy = psy
        coat = psy.idn.get("coat")
        if coat:
            a.S = dict(FAUNA[sp], body=coat[0], belly=coat[1])
        a.goal = psy.home if psy.home is not None else world.w * 0.5
        self.animals.append(a)


Fauna.update = _lf_fauna_update


def _lf_witness(self, x, radius, text, fear=0.5, who="jane"):
    for o in self.animals:
        if abs(o.x - x) < radius and getattr(o, "psy", None):
            t = o.psy.idn["traits"]
            o.psy.learn(who, self.clock, text, -0.8, fear=fear * (1.2 - t["boldness"]), trust=-0.3, like=-0.2)


def _lf_kindness(self, a, text, like=0.18, trust=0.14):
    if getattr(a, "psy", None):
        a.psy.learn("jane", self.clock, text, 0.8, like=like, trust=trust, fear=-0.1, fam=0.05)
        a.psy.need["social"] = max(0.0, a.psy.need["social"] - 0.3)


Fauna.witness = _lf_witness
Fauna.kindness = _lf_kindness


def _lf_residents(self):
    out = []
    for a in self.animals:
        p = getattr(a, "psy", None)
        if p is not None and p.resident:
            out.append(dict(p.to_dict(), x=round(a.x, 1)))
    for w in self.away:
        out.append(dict(w[2].to_dict(), x=None))
    return out[:24]


def _lf_restore(self, saved, world):
    for d in saved or []:
        try:
            psy = Psyche.from_dict(d)
            x = d.get("x")
            if x is None:
                self.away.append([self.clock + _lf_random.uniform(20, 90), _lf_random.choice((-1, 1)), psy, psy.sp])
                continue
            a = Animal(psy.sp, float(x), world.ground, self.rng)
            a.psy = psy
            coat = psy.idn.get("coat")
            if coat:
                a.S = dict(FAUNA[psy.sp], body=coat[0], belly=coat[1])
            self.animals.append(a)
        except Exception:
            continue


Fauna.residents = _lf_residents
Fauna.restore = _lf_restore


# ============================================================================
# Jane's life
# ============================================================================

class JaneLife:
    def __init__(self):
        self.inv = {"wood": 0, "berries": 0, "bow": 0, "meat": 0}
        self.phys = {"sleep_pressure": 0.2, "bladder": 0.2, "hygiene": 0.9, "pain": 0.0,
                     "condition": 0.6, "stomach": 0.3, "sweat": 0.0}
        self.places = {}                    # bucket -> valence, what happened there
        self.visited = {}                   # bucket -> seconds spent (exploration)
        self.home = None                    # {"x", "stage", "cond"}
        self.animals = {}                   # seed -> opinion
        self.learned = {"fire_rain": 0.7, "shot_range": 7.0, "exposed_nights": 0}
        self.projects = []                  # [{"kind", "why", "t0"}]
        self.sleeping = False
        self.clock = 0.0
        self.obs_t = 0.0
        self.pool = None

    # -- persistence ---------------------------------------------------------------
    def to_dict(self):
        return {"inv": self.inv, "phys": self.phys, "places": self.places, "visited": self.visited,
                "home": self.home, "animals": self.animals, "learned": self.learned,
                "projects": self.projects[-8:]}

    def from_dict(self, d):
        if not isinstance(d, dict):
            return
        for k in ("inv", "phys", "places", "visited", "animals", "learned"):
            if isinstance(d.get(k), dict):
                getattr(self, k).update(d[k])
        if isinstance(d.get("home"), dict):
            self.home = d["home"]
        if isinstance(d.get("projects"), list):
            self.projects = d["projects"]

    # -- helpers -----------------------------------------------------------------------
    def place_note(self, x, val):
        k = str(int(x // 60))
        self.places[k] = round(self.places.get(k, 0.0) * 0.95 + val, 3)

    def favourite_x(self, default):
        if not self.places:
            return default
        k = max(self.places, key=self.places.get)
        return int(k) * 60 + 30

    def opinion(self, psy):
        k = str(psy.seed)
        return self.animals.setdefault(k, {"sp": psy.sp, "like": 0.0, "fam": 0.0, "fear": 0.0,
                                           "name": None, "seen": 0.0, "notes": []})

    def project(self, kind, why, brain, mind):
        if any(p["kind"] == kind for p in self.projects):
            return
        self.projects.append({"kind": kind, "why": why, "t0": round(self.clock)})
        _lf_think(brain, mind, f"I want to {why}", "plan")
        brain.memory.remember("episode", f"decided to {why}", importance=0.55,
                              emotion=brain.emotion.emotion, valence=0.1, subject="self")


def _lf_think(brain, mind, text, kind):
    try:
        mind.thoughts._emit(brain, mind, kind, text, None)
    except Exception:
        pass


def _lf_life(app):
    mind = app.brain.mind
    life = getattr(mind, "life", None)
    if life is None:
        life = mind.life = JaneLife()
        saved = getattr(mind, "_life_saved", None)
        if saved:
            life.from_dict(saved)
    return life


def _lf_tick(app, dt):
    """Physiology + observation + consequences for Jane (every frame, cheap)."""
    life = _lf_life(app)
    b, mind, cr, g = app.brain, app.brain.mind, app.creature, app.brain.goals
    life.clock += dt
    P = life.phys
    night = app.world.daypart in ("evening", "night")
    moving = abs(getattr(cr._loco, "vx", 0.0)) > 20
    life.sleeping = life.sleeping and P["sleep_pressure"] > 0.08 and (night or P["sleep_pressure"] > 0.3)
    if life.sleeping:
        P["sleep_pressure"] = max(0.0, P["sleep_pressure"] - dt / 240.0)
    else:
        P["sleep_pressure"] = min(1.0, P["sleep_pressure"] + dt / (900.0 if not night else 600.0))
    P["bladder"] = min(1.0, P["bladder"] + dt / 700.0)
    precip = app.weather_sim.snapshot().get("precip", 0.0) if getattr(app, "weather_sim", None) else 0.0
    P["hygiene"] = max(0.0, P["hygiene"] - dt / 2400.0 * (2.0 if moving else 1.0) - dt * 0.0006 * precip)
    heat = mind.comfort.feel - mind.comfort.preferred
    P["sweat"] = clamp01(P["sweat"] + dt * (0.01 * max(0.0, heat - 3.0) * (1.5 if moving else 0.6) - 0.02))
    g.thirst = clamp01(g.thirst + dt * 0.0015 * P["sweat"])
    if cr._loco.fall > 0.9 and not getattr(life, "_fallen", False):
        life._fallen = True
        P["pain"] = min(1.0, P["pain"] + 0.25)
        b.perceive(Event("injury", "fell and hurt myself", salience=0.6, valence=-0.4))
    elif cr._loco.fall < 0.1:
        life._fallen = False
    P["pain"] = max(0.0, P["pain"] - dt / 500.0)
    dig = min(P["stomach"], dt * 0.002)
    P["stomach"] -= dig
    P["condition"] = clamp01(P["condition"] + dig * 0.05 - dt * 0.00002 * (1.0 + moving))
    # the body shapes the mind: discomfort, tiredness and pain colour mood and choices
    discomfort = max(0.0, P["bladder"] - 0.75) + max(0.0, 0.3 - P["hygiene"]) + P["pain"] * 0.8
    if discomfort > 0.05:
        b.emotion.nudge("stress", dt * 0.02 * discomfort, "")
        b.emotion.nudge("valence", -dt * 0.01 * discomfort, "")
    if P["sleep_pressure"] > 0.7:
        b.emotion.nudge("curiosity", -dt * 0.01, "")
    body = getattr(cr, "_body", None)
    if isinstance(body, dict):
        body["pace"] = body.get("pace", 1.0) * (1.0 - 0.35 * P["pain"]) * (1.0 - 0.25 * max(0.0, P["sleep_pressure"] - 0.6))
    if life.sleeping and isinstance(getattr(cr, "_affect", None), dict):
        cr._affect = dict(cr._affect, eye=0.12, energy=0.5)
    # place memory: time spent, and how it felt
    k = str(int(cr.x // 60))
    life.visited[k] = round(life.visited.get(k, 0.0) + dt, 1)
    if life.clock - life.obs_t > 1.0:
        life.obs_t = life.clock
        life.place_note(cr.x, 0.02 * b.emotion.valence)
        _lf_observe(app, life)
    # home: sheltering, weather damage
    h = life.home
    if h is not None:
        if abs(cr.x - h["x"]) < 2.6 * cr._Hb() and h["stage"] >= 1:     # inside the 5 m hut
            mind.sheltered = True
        wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
        if wx.get("wind", 0.0) > 0.6 or wx.get("precip", 0.0) > 0.8:
            h["cond"] = max(0.0, h["cond"] - dt * 0.0015 * (1.5 - 0.3 * h["stage"]))
    elif night and not getattr(life, "_night_counted", False):
        life._night_counted = True
        life.learned["exposed_nights"] += 1
    if not night:
        life._night_counted = False


def _lf_observe(app, life):
    """Jane watches the animals as individuals and forms her own opinions."""
    fa = getattr(app, "fauna", None)
    if fa is None:
        return
    b, mind, cr = app.brain, app.brain.mind, app.creature
    H = cr._Hb()
    fa.jane_has_food = life.inv.get("berries", 0) > 0 or life.inv.get("meat", 0) > 0
    events = fa.jane_events
    fa.jane_events = []
    for kind, a in events:
        p = getattr(a, "psy", None)
        if p is None:
            continue
        op = life.opinion(p)
        who = op["name"] or f"the {p.sp}"
        if kind == "greet":
            op["like"] = clamp01(op["like"] + 0.08)
            b.perceive(Event("animal", f"{who} came bounding over to greet me", salience=0.6, valence=0.5))
            b.goals.satisfy("social", 0.25, f"{who} greeted me")
        elif kind == "sniff" and op["fam"] < 0.3:
            op["like"] = clamp01(op["like"] + 0.03)
            _lf_think(b, mind, f"{who} is sniffing at me - curious little thing", "social")
        elif kind == "follow":
            op["like"] = clamp01(op["like"] + 0.004)
            b.goals.satisfy("social", 0.004, "")
        elif kind == "play":
            op["like"] = clamp01(op["like"] + 0.01)
            b.emotion.nudge("valence", 0.01, "")
        elif kind == "beg":
            op["notes"] = (op["notes"] + ["begs for food"])[-5:]
    for a in fa.animals:
        p = getattr(a, "psy", None)
        if p is None or abs(a.x - cr.x) > 9 * H:
            continue
        op = life.opinion(p)
        gap = life.clock - op["seen"] if op["seen"] else 0
        op["seen"] = life.clock
        op["fam"] = clamp01(op["fam"] + 0.006)
        if a.state == "stalk":
            op["fear"] = clamp01(op["fear"] + 0.05)
            op["like"] = clamp01(op["like"] - 0.02)
        if gap > 90 and op["fam"] > 0.2:
            who = op["name"] or f"the {p.sp} ({p.idn['quirk']})"
            b.perceive(Event("animal", f"{who} is back", salience=0.5, valence=0.25 if op["like"] > 0.3 else 0.0))
        # a bond forms from repeated good encounters: she gives it a name
        if not op["name"] and op["like"] > 0.4 and op["fam"] > 0.35:
            op["name"] = p.idn["name"]
            p.named = True
            b.memory.remember("episode", f"started calling the {p.sp} '{op['name']}' - it {p.idn['quirk']}",
                              importance=0.7, emotion=b.emotion.emotion, valence=0.4, subject="self")
            _lf_think(b, mind, f"I'm calling the {p.sp} {op['name']}. It {p.idn['quirk']}.", "social")
            b.knowledge.see("animal", f"{p.sp} {op['name']}", valence=0.4, note=p.idn["quirk"])


# ---- utility planner (replaces the fixed survival priority list) -----------------
_lf_prev_plan = Survival._plan


def _lf_plan(self, app, wx):
    try:
        return _lf_plan_inner(self, app, wx)
    except Exception:
        traceback.print_exc()
        return _lf_prev_plan(self, app, wx)                   # safe fallback


def _lf_plan_inner(self, app, wx):
    life = _lf_life(app)
    self.inv = life.inv
    world, cr, b = app.world, app.creature, app.brain
    g, mind = b.goals, b.mind
    tr = b.personality.traits
    H = cr._Hb()
    P = life.phys
    dark = world.daypart in ("evening", "night")
    rain = wx.get("precip", 0.0)
    f = self.fire
    lit = f is not None and f.lit
    food = world.poi("food")
    water = world.poi("water")
    trees = getattr(world, "_tree_x", None) or [world.w * 0.3]
    near_tree = min(trees, key=lambda t: abs(t - cr.x))
    cold = mind.comfort.cold
    hunt_ok = app.settings.data.get("hunting_enabled", False)
    fa = getattr(app, "fauna", None)
    cand = {}

    def c(name, util, task):
        if util > 0.05:
            cand[name] = (util, task)
    # warmth / fire (learned: don't bother lighting fires in heavy rain)
    if (dark or cold > 0.3) and not lit and rain < life.learned["fire_rain"]:
        u = 0.5 + 0.6 * cold + 0.1 * dark
        c("fire", u, ("wood", near_tree) if self.inv["wood"] < 3 else
          ("build", clamp((life.home["x"] + 2.5 * H) if life.home else
                          ((world.poi("shelter").x + 80) if world.poi("shelter") else cr.x), 60, world.w - 60)))
    # food
    hunger = g.hunger * (1.0 + 0.3 * (P["condition"] < 0.4))
    if lit and (self.inv["berries"] or self.inv["meat"]):
        c("cook", hunger * 1.3, ("cook", f.x + (1 if cr.x >= f.x else -1) * 2.4 * H))
    elif self.inv["berries"] and not lit:
        c("eat", hunger * 1.1, ("eat", cr.x))
    if self.inv["berries"] < 3 and food is not None and food.available():
        c("berries", hunger * 0.95 + (0.05 if self.inv["berries"] == 0 else 0.0), ("berries", food.x))
    if hunt_ok and not self.inv["berries"] and not self.inv["meat"] and not (food and food.available()):
        if not self.inv["bow"]:
            c("hunt", hunger * 0.8, ("wood", near_tree) if self.inv["wood"] < 2 else ("craft", cr.x))
        elif fa:
            prey = [a for a in fa.animals if a.sp in ("rabbit", "deer") and not a.dead
                    and not (getattr(a, "psy", None) and life.opinion(a.psy)["name"])]   # never her friends
            if prey:
                q = min(prey, key=lambda a: abs(a.x - cr.x))
                self.quarry = q
                c("hunt", hunger * (0.8 + 0.3 * tr.get("confidence", 0.5)),
                  ("hunt", clamp(q.x - (1 if q.x >= cr.x else -1) * life.learned["shot_range"] * H, 40, world.w - 40)))
    if self.inv["meat"] and not lit and rain < life.learned["fire_rain"]:
        c("fire", 0.4 + hunger, ("wood", near_tree) if self.inv["wood"] < 3 else ("build", cr.x))
    # sleep: pressure, darker is easier; somewhere safe and warm
    sp_ = P["sleep_pressure"]
    if sp_ > 0.45:
        spot = life.home["x"] if life.home and life.home["stage"] >= 1 else (
            f.x + 2.6 * H if lit else (world.poi("shelter").x if world.poi("shelter") else cr.x))
        c("sleep", sp_ * (1.5 if dark else 0.8) - 0.1, ("sleep", spot))
    # home: desire grows from nights spent exposed; building is a project she returns to
    if life.home is None or life.home["stage"] < 3:
        want_home = 0.15 + 0.12 * min(4, life.learned["exposed_nights"]) + 0.1 * (life.home is not None)
        if want_home > 0.3:
            life.project("home", "build myself somewhere to live", b, mind)
        need_w = 4 if not life.home else 3 + life.home["stage"]
        site = life.home["x"] if life.home else clamp(life.favourite_x(cr.x), 80, world.w - 80)
        if rain < 0.6 and not dark:
            c("home", want_home * (0.6 + 0.4 * tr.get("conscientiousness", tr.get("confidence", 0.5))),
              ("wood", near_tree) if self.inv["wood"] < need_w else ("homebuild", site))
    if life.home and life.home["cond"] < 0.6 and rain < 0.6:
        c("repair", 0.7 * (1.0 - life.home["cond"]),
          ("wood", near_tree) if self.inv["wood"] < 1 else ("repair", life.home["x"]))
    # body
    if P["bladder"] > 0.7:
        c("relieve", P["bladder"] * 1.25, ("relieve", near_tree + 1.5 * H))
    if P["hygiene"] < 0.4 and water is not None:
        c("wash", (1.0 - P["hygiene"]) * 0.8, ("wash", water.x))
    # animals: check on friends she hasn't seen, befriend the approachable
    if fa:
        for a in fa.animals:
            p = getattr(a, "psy", None)
            if p is None:
                continue
            op = life.opinion(p)
            d = abs(a.x - cr.x)
            r = p.rel_of("jane")
            calm = a.state in ("sniff", "follow", "beg", "approach", "sleep", "graze", "excited", "play", "drink")
            if (d < 8 * H and r["trust"] > 0.2 and r["fear"] < 0.35 and calm and not a.S.get("danger")
                    and not a.S.get("flyer") and not a.S.get("flutter")
                    and life.clock - op.get("petted", -1e9) > 120):
                want = (0.2 + 0.4 * g.social + 0.3 * op["like"]) * (0.6 + tr.get("curiosity", 0.5) * 0.6)
                if self.inv["berries"] and p.need["hunger"] > 0.4 and op["like"] > 0.2:
                    c(f"offer:{p.seed}", want + 0.1, ("offer", a.x))
                else:
                    c(f"pet:{p.seed}", want * (0.7 if a.S.get("domestic") else 0.35), ("pet", a.x))
        missing = [(k, op) for k, op in life.animals.items() if op["name"] and life.clock - op["seen"] > 150]
        if missing:
            k, op = missing[0]
            c("check", 0.3 + 0.4 * op["like"], ("check", life.favourite_x(cr.x) if not life.home else life.home["x"]))
    # stimulation: explore the least-known part of the valley, or visit a favourite spot
    if g.stimulation > 0.4:
        buckets = [str(i) for i in range(0, max(1, world.w // 60))]
        least = min(buckets, key=lambda k: life.visited.get(k, 0.0))
        c("explore", g.stimulation * (0.5 + tr.get("curiosity", 0.5) * 0.6), ("explore", int(least) * 60 + 30))
    elif not dark and b.emotion.valence < 0.1:
        c("favourite", 0.25, ("favourite", life.favourite_x(cr.x)))
    if dark and lit:
        c("warm", 0.3 + 0.5 * cold, ("warm", f.x + (1 if cr.x >= f.x else -1) * 3.4 * H))
    try:
        _m41_plan_adjust(self, app, life, cand)                      # expectations shape choice
    except Exception:
        pass
    # decide: best utility, with commitment to what she's already doing
    cur = getattr(self, "_cand", None)
    if cur in cand:
        cand[cur] = (cand[cur][0] + 0.15, cand[cur][1])
    task = None
    if cand:
        name = max(cand, key=lambda k: cand[k][0])
        self._cand = name
        task = cand[name][1]
        if name.startswith(("offer:", "pet:")):
            self._subject = int(name.split(":")[1])
    try:
        mt = _m42_decide(self, app, life, cand, task)       # multi-step plans (M42)
        if mt is not None:
            task = mt or None
    except Exception:
        pass
    if task != self.task and not (self.task and self.task[0] == "hunt" and task and task[0] == "hunt"):
        self.task, self.timer = task, 0.0
    self.bias = {}
    if task:
        far = abs(cr.x - task[1]) > 30
        if far:
            self.bias["move"] = 0.35
        elif task[0] in ("warm", "cook", "sleep"):
            self.bias["rest"] = 0.9 if task[0] != "sleep" else 1.2
            self.bias["move"] = -0.6
        elif task[0] in ("homebuild", "repair", "relieve", "wash", "pet", "offer", "wood", "berries", "craft"):
            self.bias["move"] = -0.4


Survival._plan = _lf_plan

_lf_prev_act = Survival._act


def _lf_act(self, app, dt):
    try:
        if self.task and self.task[0] in ("sleep", "homebuild", "repair", "relieve", "wash", "pet",
                                          "offer", "check", "explore", "favourite"):
            return _lf_act_new(self, app, dt)
    except Exception:
        traceback.print_exc()
        self.task = None
    life = _lf_life(app)
    was = dict(self.inv)
    _lf_prev_act(self, app, dt)
    # consequences feed learning and place memory
    if self.inv.get("meat", 0) > was.get("meat", 0):
        life.place_note(app.creature.x, 0.3)
    fire = self.fire
    if getattr(self, "_had_fire", False) and (fire is None or not fire.lit):
        wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
        if wx.get("precip", 0.0) > 0.5:
            life.learned["fire_rain"] = max(0.35, life.learned["fire_rain"] - 0.1)   # learned from the drowned fire
    self._had_fire = fire is not None and fire.lit


def _lf_act_new(self, app, dt):
    life = _lf_life(app)
    cr, b, mind = app.creature, app.brain, app.brain.mind
    H = cr._Hb()
    kind, tx = self.task
    fa = getattr(app, "fauna", None)
    subj = None
    if kind in ("pet", "offer") and fa:
        subj = next((a for a in fa.animals if getattr(a, "psy", None) and a.psy.seed == getattr(self, "_subject", -1)), None)
        if subj is None:
            self.task = None
            return
        tx = subj.x + (1.2 * H if cr.x > subj.x else -1.2 * H)
    if abs(cr.x - tx) > 18:
        cr.set_target(tx, cr.y)
        if kind in ("pet", "offer"):
            try:
                pace = _m41_approach(self, app, life, kind, subj)
                body = getattr(cr, "_body", None)
                if isinstance(body, dict) and pace < 1.0:
                    body["pace"] = body.get("pace", 1.0) * pace
            except Exception:
                pass
        if kind == "sleep":
            life.sleeping = False
        self._chase = getattr(self, "_chase", 0.0) + dt
        if kind in ("pet", "offer") and self._chase > 10.0:        # it keeps its distance: give up
            op = life.opinion(subj.psy)
            op["petted"] = life.clock
            op["notes"] = (op["notes"] + ["keeps its distance"])[-5:]
            self.task, self._chase = None, 0.0
        return
    self._chase = 0.0
    self.timer += dt
    if kind == "sleep":
        life.sleeping = True
        if life.phys["sleep_pressure"] < 0.08:
            life.sleeping = False
            self.task = None
            b.memory.remember("episode", "slept" + (" at home" if life.home and abs(cr.x - life.home["x"]) < 2 * H else " out in the open"),
                              importance=0.35, emotion=b.emotion.emotion, valence=0.2, subject="self")
            life.place_note(cr.x, 0.3 if life.home else 0.05)
    elif kind == "homebuild" and self.timer > 9.0:
        need = 4 if not life.home else 3 + life.home["stage"]
        if self.inv["wood"] >= need:
            self.inv["wood"] -= need
            if life.home is None:
                life.home = {"x": tx, "stage": 1, "cond": 1.0}
                txt = "built a lean-to - the start of a home"
            else:
                life.home["stage"] += 1
                life.home["cond"] = 1.0
                txt = {2: "raised proper walls on my shelter", 3: "finished my hut: a door and a bed"}.get(life.home["stage"], "improved my home")
            b.perceive(Event("home", txt, salience=0.7, valence=0.55))
            life.place_note(tx, 0.8)
            if life.home["stage"] >= 3:
                life.projects = [p for p in life.projects if p["kind"] != "home"]
        self.task = None
    elif kind == "repair" and self.timer > 3.0:
        if self.inv["wood"] and life.home:
            self.inv["wood"] -= 1
            life.home["cond"] = min(1.0, life.home["cond"] + 0.5)
            b.perceive(Event("home", "patched up the storm damage on my shelter", salience=0.5, valence=0.25))
        self.task = None
    elif kind == "relieve" and self.timer > 4.0:
        life.phys["bladder"] = 0.0
        life.phys["stomach"] *= 0.7
        self.task = None
    elif kind == "wash" and self.timer > 4.0:
        life.phys["hygiene"] = 1.0
        b.perceive(Event("self", "washed in the spring - clean again", salience=0.4, valence=0.3))
        life.place_note(tx, 0.2)
        self.task = None
    elif kind in ("pet", "offer") and self.timer > 2.0 and subj is not None:
        op = life.opinion(subj.psy)
        who = op["name"] or f"the {subj.sp}"
        if kind == "offer" and self.inv["berries"]:
            self.inv["berries"] -= 1
            subj.psy.need["hunger"] = max(0.0, subj.psy.need["hunger"] - 0.4)
            fa.kindness(subj, "Jane fed me", like=0.25, trust=0.2)
            txt = f"fed {who} a handful of berries"
        else:
            fa.kindness(subj, "Jane petted me gently")
            txt = f"petted {who}"
        op["like"] = clamp01(op["like"] + 0.08)
        op["fam"] = clamp01(op["fam"] + 0.05)
        op["petted"] = life.clock
        b.goals.satisfy("social", 0.2, txt)
        b.perceive(Event("animal", txt, salience=0.5, valence=0.4))
        life.place_note(cr.x, 0.2)
        self.task = None
    elif kind in ("check", "explore", "favourite"):
        if kind == "explore":
            b.goals.satisfy("stimulation", 0.15, "explored a new corner of the valley")
        self.task = None


Survival._act = _lf_act

# hunting has consequences for every animal that saw it
_lf_prev_release = Survival._release


def _lf_release(self, app, q):
    _lf_prev_release(self, app, q)
    fa = getattr(app, "fauna", None)
    if fa is not None:
        fa.witness(q.x, 300, "Jane shot at one of us", fear=0.35)
        life = _lf_life(app)
        if fa.clock and life.learned["shot_range"] > 4.5 and len(self.arrows) > 1:
            life.learned["shot_range"] = max(4.5, life.learned["shot_range"] - 0.2)  # stalk closer next time


Survival._release = _lf_release


# ---- home rendering: lean-to -> walls -> finished hut (behind Jane) ------------------
def _lf_draw_home(app, life):
    h = life.home
    cam = getattr(app, "_camera", None)
    if cam is None:
        return
    if life.pool is None:
        life.pool = _AtmoPool(app.stage)
    P = life.pool
    P.begin()
    if h is not None:
        W = cam.world_to_screen
        G = app.world.ground
        _ws = globals().get("WS")
        H = _ws.m(1.0) if _ws else app.creature._H()        # 1 m: walls 2.6 m, 5.2 m wide, door 1.9 m
        sg = getattr(app, "_scene_grade", None)
        gc = (lambda col, y: sg.color(col, y)) if sg else (lambda col, y: col)
        x = h["x"]
        cond = h["cond"]

        def poly(pts, col):
            out = []
            for i in range(0, len(pts), 2):
                out.extend(W(pts[i], pts[i + 1]))
            P.put("polygon", out, "fauna", fill=col, outline="", smooth=False)
        wood, dark_w = gc("#7a5634", G), gc("#4e3522", G)
        roof = gc(_mix_hex("#8c7a4a", "#4a3a26", 1.0 - cond), G - 3 * H)
        w_ = 2.6 * H
        if h["stage"] == 1:
            poly([x - w_, G, x - w_ + 0.2 * H, G, x + w_ * 0.2, G - 3.2 * H, x, G - 3.2 * H], dark_w)
            poly([x - w_ - 0.3 * H, G + 0.2 * H, x + w_ * 0.25, G - 3.5 * H, x + w_ * 0.55, G - 3.2 * H,
                  x - w_ * 0.5, G + 0.2 * H], roof)
        else:
            wall_h = 2.6 * H
            poly([x - w_, G, x + w_, G, x + w_, G - wall_h, x - w_, G - wall_h], wood)
            for k in range(1, 5):
                yy = G - wall_h * k / 5
                poly([x - w_, yy, x + w_, yy, x + w_, yy - 0.06 * H, x - w_, yy - 0.06 * H], dark_w)
            poly([x - w_ - 0.5 * H, G - wall_h, x, G - wall_h - 2.2 * H, x + w_ + 0.5 * H, G - wall_h], roof)
            if cond < 0.7:
                poly([x + 0.4 * H, G - wall_h - 1.2 * H, x + 1.2 * H, G - wall_h - 0.8 * H,
                      x + 0.9 * H, G - wall_h - 0.3 * H], dark_w)          # storm damage gap
            if h["stage"] >= 3:
                poly([x - 0.7 * H, G, x + 0.7 * H, G, x + 0.7 * H, G - 1.9 * H, x - 0.7 * H, G - 1.9 * H],
                     gc("#3a2616", G))
                # a framed window, lit from inside after dark (it used to be a bare
                # disc that floated like a second moon)
                wx0, wy0 = x + w_ * 0.45, G - wall_h * 0.72
                ww_, wh_ = 0.8 * H, 0.7 * H
                lit_in = app.world.daypart in ("evening", "night")
                poly([wx0 - 0.08 * H, wy0 - 0.08 * H, wx0 + ww_ + 0.08 * H, wy0 - 0.08 * H,
                      wx0 + ww_ + 0.08 * H, wy0 + wh_ + 0.08 * H, wx0 - 0.08 * H, wy0 + wh_ + 0.08 * H], dark_w)
                poly([wx0, wy0, wx0 + ww_, wy0, wx0 + ww_, wy0 + wh_, wx0, wy0 + wh_],
                     "#ffcf73" if lit_in else gc("#3a4452", G))
                poly([wx0 + ww_ * 0.47, wy0, wx0 + ww_ * 0.53, wy0, wx0 + ww_ * 0.53, wy0 + wh_, wx0 + ww_ * 0.47, wy0 + wh_], dark_w)
                poly([wx0, wy0 + wh_ * 0.46, wx0 + ww_, wy0 + wh_ * 0.46, wx0 + ww_, wy0 + wh_ * 0.54, wx0, wy0 + wh_ * 0.54], dark_w)
    P.end()


# ---- app wiring ------------------------------------------------------------------------
_lf_prev_update_world = App._update_world


def _lf_update_world(self, dt):
    _lf_prev_update_world(self, dt)
    try:
        fa = getattr(self, "fauna", None)
        mind = self.brain.mind
        if fa is not None and not getattr(fa, "_restored", False):
            fa._restored = True
            fa.restore(getattr(mind, "_fauna_saved", None), self.world)
        _lf_tick(self, dt)
        life = mind.life
        sv = getattr(self, "survival", None)
        for k_, v_ in list(life.inv.items()):
            if isinstance(v_, (int, float)) and v_ < 0:
                life.inv[k_] = 0                              # stock can't go below nothing
        if sv is not None and sv.inv is not life.inv:
            life.inv.update({k: v for k, v in sv.inv.items() if k not in life.inv or not life.inv[k]})
            sv.inv = life.inv
        if fa is not None:
            fa.fire_x = sv.fire.x if (sv and sv.fire and sv.fire.lit) else None
            if int(fa.clock) % 5 == 0:
                mind._fauna_saved = fa.residents()
        _lf_draw_home(self, life)
        self.stage.tag_raise("fauna")
    except Exception:
        traceback.print_exc()


App._update_world = _lf_update_world

_lf_prev_to_dict = LivingMind.to_dict
_lf_prev_from_dict = LivingMind.from_dict


def _lf_to_dict(self):
    d = _lf_prev_to_dict(self)
    try:
        if getattr(self, "life", None) is not None:
            d["life"] = self.life.to_dict()
        d["fauna_pop"] = list(getattr(self, "_fauna_saved", None) or [])
    except Exception:
        pass
    return d


def _lf_from_dict(self, d):
    _lf_prev_from_dict(self, d)
    if isinstance(d, dict):
        self._life_saved = d.get("life")
        self._fauna_saved = d.get("fauna_pop") or []


LivingMind.to_dict = _lf_to_dict
LivingMind.from_dict = _lf_from_dict

# the prompt knows about her physical state and her animal friends
_lf_prev_sys = Brain.build_system_prompt


def _lf_sys(self, decision, recalled, perception):
    text = _lf_prev_sys(self, decision, recalled, perception)
    try:
        life = getattr(self.mind, "life", None)
        if life is None:
            return text
        P = life.phys
        bits = []
        if P["sleep_pressure"] > 0.6:
            bits.append("tired")
        if P["pain"] > 0.2:
            bits.append("sore from a fall")
        if P["hygiene"] < 0.35:
            bits.append("grubby")
        friends = [f"{op['name']} the {op['sp']}" for op in life.animals.values() if op.get("name")]
        home = life.home
        line = ("- your life: " + ("; ".join(bits) + "; " if bits else "")
                + (f"you have a {'finished hut' if home['stage'] >= 3 else 'shelter'} you built yourself; " if home else "no home yet; ")
                + (f"animal friends: {', '.join(friends[:4])}" if friends else "no animal friends yet"))
        marker = "--- how to reply ---"
        return text.replace(marker, line + "\n" + marker, 1) if marker in text else text
    except Exception:
        return text


Brain.build_system_prompt = _lf_sys

# clicking an animal inspects it (the individual, not the species)
_lf_prev_click = App._on_stage_click


def _lf_click(self, event):
    try:
        fa = getattr(self, "fauna", None)
        cam = getattr(self, "_camera", None)
        if fa is not None and cam is not None:
            wx_, wy_ = cam.screen_to_world(event.x, event.y)
            for a in fa.animals:
                p = getattr(a, "psy", None)
                if p is None:
                    continue
                s = a.S["size"] * a.scale
                ay = self.world.ground + 8 - a.alt - s
                if abs(wx_ - a.x) < 2.2 * s + 6 and abs(wy_ - ay) < 2.0 * s + 8:
                    life = _lf_life(self)
                    op = life.opinion(p)
                    r = p.rel_of("jane")
                    t = p.idn["traits"]
                    top = max(t, key=t.get)
                    self._inspect_until = _lf_time.time() + 7.0
                    self.inspected = (op["name"] or f"a {p.sp}", [
                        f"{p.idn['attachment']} · mostly {top} · {p.goal} ({a.state})",
                        f"it {p.idn['quirk']}"[:52],
                        f"toward Jane: trust {r['trust']:.0%} · fear {r['fear']:.0%} · likes her {r['like']:.0%}"])
                    self.brain.perceive(Event("animal_seen", f"looked closely at {op['name'] or 'a ' + p.sp}",
                                              salience=0.45, valence=0.15))
                    return
    except Exception:
        traceback.print_exc()
    return _lf_prev_click(self, event)


App._on_stage_click = _lf_click
