# ============================================================================
# [NEW] M46 - AUTONOMOUS SOCIETY  (+ M44 persistent NPC individuals)
# ============================================================================
#
# Beyond the valley: settlements of individual people (traits, mood,
# health, age, memories, relationships, faction, wealth, role) living an
# abstract daily life. Society time: one society-day per real hour, stepped
# every 30 s and advanced offline by M43.
#
#   economy   production by role (farm, wood, craft), consumption, stock,
#             supply/demand prices; traders move surplus to shortage and
#             earn from it; famine when food runs out
#   politics  leaders need legitimacy (welfare, faction support); unrest from
#             hunger, inequality (Gini of wealth) and war; revolts replace
#             leaders and can change the form of government
#   factions  Old Ways / Merchants / Wardens by members' traits; the dominant
#             faction slowly shifts the settlement's culture
#   relations drift with culture, trade and scarcity -> alliances (food aid)
#             or war (raids, casualties, loot, weariness, peace)
#   rise/fall population grows on surplus, shrinks in famine and war; small
#             settlements are abandoned (refugees); crowded open ones found
#             new settlements
# Jane meets this world through the valley: routes between the two sides pass
# through it, so real traders walk through (carrying news of real events),
# refugees flee collapses, and she can barter her surplus for goods that
# matter to her life (blanket = warmth, salt = better meals, lantern = home).

import math as _so_math
import random as _so_random
import time as _so_time

SOC_DAY = 3600.0
_SO_SYL = ("ash", "brook", "fen", "hol", "mere", "wick", "thorn", "stead", "ley", "ford", "dun", "vale",
           "oak", "ridge", "mar", "cot", "wyn", "burn")
_SO_FIRST = ("Tamsin", "Ewan", "Isolde", "Rafe", "Maren", "Cole", "Anwen", "Bram", "Lise", "Hale", "Oona",
             "Piers", "Rhea", "Soren", "Tilde", "Wade", "Yara", "Nell", "Corin", "Esme", "Fen", "Garrick")
_SO_LAST = ("Ashdown", "Brightwater", "Colbrook", "Dunmore", "Fairweather", "Greaves", "Hollins", "Marsh",
            "Penrose", "Quill", "Rookwood", "Stone", "Thatcher", "Underhill", "Wren", "Yardley", "Abbot", "Barrow",
            "Cartwright", "Delaney", "Everly", "Fletcher", "Garnet", "Hale", "Ingram", "Joss", "Kettle", "Lark",
            "Merrow", "Nettle", "Oakes", "Pike", "Rowan", "Sallow", "Tanner", "Vesey", "Weaver", "Yeoman")
_SO_ROLES = ("farmer", "farmer", "farmer", "woodcutter", "crafter", "trader", "guard", "priest")
_SO_FACTIONS = ("Old Ways", "Merchants", "Wardens")
_SO_GOODS = {"blanket": ("a wool blanket", 3), "salt": ("a pouch of salt", 2), "lantern": ("a tin lantern", 4)}


def _so_name(r):
    return (r.choice(_SO_SYL) + r.choice(_SO_SYL)).capitalize()


class NPC:
    def __init__(self, r, sett, role=None, nid=None):
        self.id = nid or f"n{r.getrandbits(30)}"
        self.name = f"{r.choice(_SO_FIRST)} {r.choice(_SO_LAST)}"
        self.sett = sett
        self.role = role or r.choice(_SO_ROLES)
        self.t = {k: round(r.random(), 3) for k in ("ambition", "sociability", "piety", "aggression", "honesty")}
        self.emo = {"valence": 0.1, "stress": 0.2}
        self.phys = {"health": 1.0, "hunger": 0.2, "age": r.randint(16, 60)}
        self.mem = []
        self.rel = {}
        self.wealth = r.uniform(1, 10) * (3 if self.role in ("trader", "priest") else 1)
        self.faction = None
        self.alive = True
        self.away = 0.0                                   # travelling (society days left)

    def remember(self, day, text, val):
        self.mem = (self.mem + [(round(day, 1), text, round(val, 2))])[-10:]
        self.emo["valence"] = clamp(self.emo["valence"] + 0.3 * val, -1.0, 1.0)

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d):
        n = cls.__new__(cls)
        n.__dict__.update(d)
        n.mem = [tuple(m) for m in n.mem]
        return n


class Settlement:
    def __init__(self, r, name, side, dist):
        self.name, self.side, self.dist = name, side, dist
        self.culture = {k: round(r.random(), 3) for k in ("tradition", "militarism", "openness", "piety")}
        self.gov = r.choice(("council", "chief", "elders"))
        self.pop = r.randint(70, 180)
        self.stock = {"food": self.pop * 3.0, "wood": 60.0, "goods": 20.0}
        self.unrest, self.legit = 0.2, 0.7
        self.rel, self.war, self.allies = {}, {}, []
        self.leader = None
        self.alive = True
        self.hunger_days = 0.0
        self.jane_rep = 0.0                                 # what they think of "the woman in the valley"

    def to_dict(self):
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d):
        s = cls.__new__(cls)
        s.__dict__.update(d)
        return s


class Society:
    def __init__(self, seed=1):
        self.r = _so_random.Random(seed)
        self.day = 0.0
        self.sets = {}
        self.npcs = {}
        self.events = []                                    # (day, where, kind, text, importance)
        self.travel = []                                    # pending trips through the valley
        r = self.r
        for i in range(4):
            name = _so_name(r)
            while name in self.sets:
                name = _so_name(r)
            self.sets[name] = Settlement(r, name, -1 if i % 2 == 0 else 1, r.uniform(1.0, 4.0))
        for s in self.sets.values():
            for role in ("leader",) + tuple(r.choice(_SO_ROLES) for _ in range(7)):
                n = NPC(r, s.name, role)
                self.npcs[n.id] = n
                if role == "leader":
                    s.leader = n.id
            for o in self.sets.values():
                if o is not s:
                    s.rel[o.name] = round(r.uniform(-0.2, 0.4), 3)
        self._factions()

    # -- helpers -------------------------------------------------------------------
    def people(self, sname):
        return [n for n in self.npcs.values() if n.sett == sname and n.alive]

    def log(self, where, kind, text, imp):
        self.events.append((round(self.day, 2), where, kind, text, imp))
        del self.events[:-200]
        for n in self.people(where)[:8]:
            n.remember(self.day, text, -0.4 if kind in ("famine", "raid", "revolt", "collapse", "war") else 0.2)

    def _factions(self):
        for n in self.npcs.values():
            self._assign(n)

    def _assign(self, n):
        if True:
            scores = {"Old Ways": n.t["piety"] + (0.3 if n.role == "priest" else 0),
                      "Merchants": n.t["ambition"] + (0.3 if n.role in ("trader", "crafter") else 0) + n.wealth / 60,
                      "Wardens": n.t["aggression"] + (0.3 if n.role == "guard" else 0)}
            n.faction = max(scores, key=scores.get)

    @staticmethod
    def _gini(vals):
        v = sorted(max(0.0, x) for x in vals)
        n = len(v)
        if n < 2 or sum(v) <= 0:
            return 0.0
        cum = sum((i + 1) * x for i, x in enumerate(v))
        return (2 * cum) / (n * sum(v)) - (n + 1) / n

    # -- one society day (or fraction) ------------------------------------------------
    def step(self, days):
        if days <= 0:
            return
        r = self.r
        self.day += days
        alive = [s for s in self.sets.values() if s.alive]
        for s in alive:
            ppl = self.people(s.name)
            share = lambda role: max(0.05, sum(1 for n in ppl if n.role == role) / max(1, len(ppl)))
            harvest = r.uniform(0.75, 1.25)
            s.stock["food"] += days * s.pop * (0.9 * share("farmer") + 0.25) * harvest
            s.stock["food"] -= days * s.pop * 0.5
            s.stock["wood"] += days * s.pop * 0.3 * share("woodcutter")
            made = min(s.stock["wood"], days * s.pop * 0.08 * share("crafter"))
            s.stock["wood"] -= made
            s.stock["goods"] += made * 0.5
            for k, cap in (("food", s.pop * 8), ("wood", 400), ("goods", 200)):
                s.stock[k] = clamp(s.stock[k], 0.0, cap)
            famine = s.stock["food"] <= 0.5
            s.hunger_days = s.hunger_days + days if famine else max(0.0, s.hunger_days - days)
            growth = 0.004 if s.stock["food"] > s.pop * 2 else (-0.012 * min(3.0, s.hunger_days) if famine else 0.0)
            s.pop = max(0, int(round(s.pop * (1 + growth * days))))
            if famine and r.random() < days * 0.5 and s.hunger_days > 0.5:
                self.log(s.name, "famine", f"{s.name} is starving - the stores are empty", 0.7)
            # politics
            wealth = [n.wealth for n in ppl]
            gini = self._gini(wealth)
            wars = sum(1 for _ in s.war)
            s.unrest += days * (0.25 * famine + 0.12 * gini + 0.05 * wars - 0.08 * (not famine))
            s.unrest = clamp01(s.unrest)
            support = sum(1 for n in ppl if self.npcs.get(s.leader) and n.faction == self.npcs[s.leader].faction)
            s.legit += days * (0.06 * (support / max(1, len(ppl)) - 0.35) - 0.08 * famine + 0.02 * (not wars))
            s.legit = clamp01(s.legit)
            if s.unrest > 0.7 and s.legit < 0.35 and r.random() < days:
                self._revolt(s, ppl)
            # culture drifts toward the dominant faction's values
            infl = {f: sum(1 + n.wealth / 20 for n in ppl if n.faction == f) for f in _SO_FACTIONS}
            top = max(infl, key=infl.get)
            key = {"Old Ways": "tradition", "Merchants": "openness", "Wardens": "militarism"}[top]
            s.culture[key] = clamp01(s.culture[key] + 0.003 * days)
            # people: their own lives
            for n in ppl:
                n.phys["age"] += days / 30.0
                n.phys["hunger"] = clamp01(n.phys["hunger"] + (0.4 if famine else -0.3) * days)
                n.phys["health"] = clamp01(n.phys["health"] - 0.15 * days * (n.phys["hunger"] > 0.7)
                                           + 0.05 * days - (0.02 * days if n.phys["age"] > 60 else 0))
                earn = {"farmer": 0.6, "woodcutter": 0.7, "crafter": 1.0, "trader": 1.4, "guard": 0.8,
                        "priest": 0.9, "leader": 1.6}.get(n.role, 0.6)
                n.wealth = max(0.0, n.wealth + days * (earn * (0.5 if famine else 1.0) - 0.5))
                n.emo["valence"] = clamp(n.emo["valence"] + days * (0.1 * (not famine) - 0.3 * famine
                                                                     - 0.1 * s.unrest), -1.0, 1.0)
                n.emo["stress"] = clamp01(0.3 * famine + 0.4 * s.unrest + 0.2 * wars)
                if n.phys["health"] <= 0.02 or (n.phys["age"] > 68 and r.random() < days * 0.05):
                    n.alive = False
                    self.log(s.name, "death", f"{n.name} the {n.role} of {s.name} died", 0.4)
                    if s.leader == n.id:
                        self._succession(s)
                    self._replace(s)
                elif n.emo["valence"] < -0.6 and n.role not in ("leader",) and r.random() < days * 0.2:
                    dest = self._best_home(s)
                    if dest is not None:
                        n.sett = dest.name
                        n.remember(self.day, f"left {s.name} for {dest.name}", 0.1)
                        self._route(s, dest, n, "migrant")
                # relationships within the settlement
                if ppl and r.random() < days * 2:
                    o = r.choice(ppl)
                    if o is not n:
                        sim = 1 - abs(n.t["sociability"] - o.t["sociability"]) + (0.3 if o.faction == n.faction else -0.1)
                        n.rel[o.id] = clamp(n.rel.get(o.id, 0.0) + 0.05 * (sim - 0.6), -1.0, 1.0)
            if s.pop < 15:
                self._collapse(s)
            elif s.pop > 220 and s.culture["openness"] > 0.45 and r.random() < days * 0.1:
                self._found(s)
        self._relations(days, alive)
        self._trade(days, alive)
        if int(self.day) != int(self.day - days):              # allegiances shift as fortunes change
            self._factions()

    def _revolt(self, s, ppl):
        old = self.npcs.get(s.leader)
        rivals = [n for n in ppl if n.faction != (old.faction if old else None)]
        if not rivals:
            return
        new = max(rivals, key=lambda n: n.t["ambition"] + n.wealth / 30)
        if old:
            old.role = "farmer"
            old.remember(self.day, "was thrown out as leader", -0.8)
        new.role = "leader"
        s.leader = new.id
        s.gov = {"Wardens": "chief", "Merchants": "council", "Old Ways": "elders"}.get(new.faction, s.gov)
        s.unrest, s.legit = 0.3, 0.55
        self.log(s.name, "revolt", f"{s.name} rose up - {new.name} of the {new.faction} now rules ({s.gov})", 0.85)

    def _succession(self, s):
        ppl = [n for n in self.people(s.name) if n.role != "leader"]
        if ppl:
            heir = max(ppl, key=lambda n: n.t["ambition"] + n.wealth / 30 + (0.3 if s.gov == "elders" and n.phys["age"] > 45 else 0))
            heir.role = "leader"
            s.leader = heir.id
            self.log(s.name, "succession", f"{heir.name} now leads {s.name}", 0.5)

    def _replace(self, s):
        if s.pop > 20 and len(self.people(s.name)) < 8:
            n = NPC(self.r, s.name)
            n.phys["age"] = 17
            self._assign(n)
            self.npcs[n.id] = n

    def _best_home(self, s):
        opts = [o for o in self.sets.values() if o.alive and o is not s and o.name not in s.war]
        return max(opts, key=lambda o: o.stock["food"] / max(1, o.pop) + o.rel.get(s.name, 0)) if opts else None

    def _collapse(self, s):
        s.alive = False
        self.log(s.name, "collapse", f"{s.name} has been abandoned", 0.95)
        dest = self._best_home(s)
        for n in self.people(s.name):
            if dest is not None:
                n.sett = dest.name
                n.remember(self.day, f"fled {s.name} when it fell", -0.7)
                self._route(s, dest, n, "refugee")
        if dest is not None:
            dest.pop += s.pop

    def _found(self, s):
        name = _so_name(self.r)
        if name in self.sets:
            return
        n = Settlement(self.r, name, -s.side if self.r.random() < 0.5 else s.side, self.r.uniform(1.5, 5.0))
        n.culture = {k: clamp01(v + self.r.uniform(-0.15, 0.15)) for k, v in s.culture.items()}
        n.pop, s.pop = 40, s.pop - 40
        n.stock = {"food": 120.0, "wood": 30.0, "goods": 5.0}
        movers = [p for p in self.people(s.name) if p.role != "leader"][:3]
        for p in movers:
            p.sett = name
        if movers:
            movers[0].role = "leader"
            n.leader = movers[0].id
        for o in self.sets.values():
            n.rel[o.name] = 0.3 if o is s else 0.0
            o.rel[name] = 0.3 if o is s else 0.0
        self.sets[name] = n
        self.log(name, "founding", f"settlers from {s.name} founded {name}", 0.8)
        if movers:
            self._route(s, n, movers[0], "settler")

    def _relations(self, days, alive):
        r = self.r
        for s in alive:
            for o in alive:
                if o is s:
                    continue
                dist = sum(abs(s.culture[k] - o.culture[k]) for k in s.culture) / 4
                drift = 0.01 * (0.35 - dist) - (0.03 if s.hunger_days > 0 and o.hunger_days > 0 else 0)
                s.rel[o.name] = clamp(s.rel.get(o.name, 0.0) + drift * days, -1.0, 1.0)
                allied = o.name in s.allies
                if s.rel[o.name] > 0.55 and not allied:
                    s.allies.append(o.name)
                    self.log(s.name, "alliance", f"{s.name} and {o.name} swore friendship", 0.6)
                if o.name not in s.war and s.rel[o.name] < -0.5 and s.culture["militarism"] > 0.5 and not allied \
                        and r.random() < days * 0.3:
                    s.war[o.name] = 0.0
                    o.war[s.name] = 0.0
                    self.log(s.name, "war", f"{s.name} went to war with {o.name}", 0.9)
                if o.name in s.war:
                    s.war[o.name] += days * 0.05
                    if r.random() < days * 0.4:
                        a_str = s.pop * (0.5 + s.culture["militarism"])
                        d_str = o.pop * (0.5 + o.culture["militarism"])
                        win = r.random() < a_str / (a_str + d_str)
                        loser, winner = (o, s) if win else (s, o)
                        dead = int(loser.pop * r.uniform(0.02, 0.06))
                        loser.pop -= dead
                        loot = loser.stock["food"] * 0.2
                        loser.stock["food"] -= loot
                        winner.stock["food"] += loot
                        self.log(loser.name, "raid", f"raiders from {winner.name} struck {loser.name} - {dead} dead", 0.75)
                        if s.side != o.side:
                            self.travel.append({"kind": "raider", "from": winner.name, "to": loser.name,
                                                "who": None, "news": None})
                    if s.war[o.name] > 0.6 and o.war.get(s.name, 0) > 0.4:
                        del s.war[o.name]
                        o.war.pop(s.name, None)
                        s.rel[o.name] = o.rel[s.name] = -0.1
                        self.log(s.name, "peace", f"{s.name} and {o.name} made peace", 0.7)
                if allied and o.hunger_days > 0 and s.stock["food"] > s.pop * 3:
                    aid = s.stock["food"] * 0.15
                    s.stock["food"] -= aid
                    o.stock["food"] += aid
                    if r.random() < 0.2:
                        self.log(o.name, "aid", f"{s.name} sent grain to their friends in {o.name}", 0.55)

    def _trade(self, days, alive):
        r = self.r
        for s in alive:
            traders = [n for n in self.people(s.name) if n.role == "trader" and n.away <= 0]
            for tr in traders:
                if r.random() > days * 1.5:
                    continue
                opts = [o for o in alive if o is not s and o.name not in s.war and s.rel.get(o.name, 0) > -0.3]
                if not opts:
                    continue
                price = lambda x, k: (x.pop * (0.5 if k == "food" else 0.1) + 1) / (x.stock[k] + 1)
                dest = max(opts, key=lambda o: price(o, "food") - price(s, "food") + 0.3 * (price(o, "goods") - price(s, "goods")))
                amt = min(s.stock["food"] * 0.1, 40.0)
                if amt <= 1:
                    continue
                s.stock["food"] -= amt
                dest.stock["food"] += amt
                profit = amt * max(0.0, price(dest, "food") - price(s, "food")) * 0.5 + 0.5
                tr.wealth += profit
                s.rel[dest.name] = clamp(s.rel.get(dest.name, 0) + 0.02, -1, 1)
                dest.rel[s.name] = clamp(dest.rel.get(s.name, 0) + 0.02, -1, 1)
                tr.away = s.dist + dest.dist
                tr.remember(self.day, f"traded grain in {dest.name}", 0.2)
                if s.side != dest.side:
                    self._route(s, dest, tr, "trader")
            for n in self.people(s.name):
                n.away = max(0.0, n.away - days)

    def _route(self, a, b, who, kind):
        """Journeys between the two sides of the valley pass through it."""
        if a.side != b.side:
            news = [e for e in self.events[-12:] if e[4] >= 0.55]
            self.travel.append({"kind": kind, "from": a.name, "to": b.name, "who": who.id if who else None,
                                "news": news[-1] if news else None})
            del self.travel[:-6]

    def to_dict(self):
        return {"day": self.day, "seed": self.r.random(),
                "sets": {k: v.to_dict() for k, v in self.sets.items()},
                "npcs": {k: v.to_dict() for k, v in self.npcs.items() if v.alive or v.mem},
                "events": self.events[-120:], "travel": self.travel[-6:]}

    @classmethod
    def from_dict(cls, d):
        s = cls.__new__(cls)
        s.r = _so_random.Random(d.get("seed", 1))
        s.day = float(d.get("day", 0.0))
        s.sets = {k: Settlement.from_dict(v) for k, v in d.get("sets", {}).items()}
        s.npcs = {k: NPC.from_dict(v) for k, v in d.get("npcs", {}).items()}
        s.events = [tuple(e) for e in d.get("events", [])]
        s.travel = list(d.get("travel", []))
        return s


# ============================================================================
# Travellers in the valley: visible people, news, barter
# ============================================================================

class Traveller:
    def __init__(self, trip, society, world, rng):
        self.trip = trip
        self.npc = society.npcs.get(trip.get("who")) if trip.get("who") else None
        self.kind = trip["kind"]
        src = society.sets.get(trip["from"])
        self.dir = 1 if (src is None or src.side < 0) else -1
        self.x = -40 if self.dir > 0 else world.w + 40
        self.t = rng.uniform(0, 5)
        self.stop = 0.0
        self.met = False
        self.traded = False
        cult = src.culture if src else {"tradition": 0.5, "militarism": 0.3}
        self.col = _mix_hex("#5a6e8a", "#8a4a3a", cult.get("militarism", 0.3))
        self.col = _mix_hex(self.col, "#6b7a4a", cult.get("tradition", 0.5) * 0.5)
        self.skin = rng.choice(("#f0cdb5", "#d9a882", "#b27a55", "#8a5a3c", "#f6dccb"))
        self.name = self.npc.name if self.npc else rng.choice(_SO_FIRST)
        self.pool = None


def _so_draw_traveller(tv, app):
    cam = getattr(app, "_camera", None)
    if cam is None:
        return
    if tv.pool is None:
        tv.pool = _AtmoPool(app.stage)
    P = tv.pool
    P.begin()
    W = cam.world_to_screen
    H = app.creature._H()
    G = app.world.ground + app.creature._sole() * 0.2
    sg = getattr(app, "_scene_grade", None)
    gc = (lambda c, y: sg.color(c, y)) if sg else (lambda c, y: c)
    x = tv.x
    walking = tv.stop <= 0
    ph = tv.t * 6.0
    hip = (x, G - 3.9 * H)
    for k, sgn in ((0, -1), (1, 1)):
        sw = _so_math.sin(ph + k * _so_math.pi) * 0.7 * H * walking
        knee = (x + sw * 0.5 * tv.dir, G - 2.0 * H)
        foot = (x + sw * tv.dir, G)
        P.put("line", [*W(*hip), *W(*knee), *W(*foot)], "fauna", fill=gc("#3a3028", G), width=max(3, int(0.28 * H * cam.zoom)))
    body = [x - 0.8 * H, G - 3.7 * H, x + 0.8 * H, G - 3.7 * H, x + 0.7 * H, G - 6.4 * H, x - 0.7 * H, G - 6.4 * H]
    P.put("polygon", [c for i in range(0, 8, 2) for c in W(body[i], body[i + 1])], "fauna",
          fill=gc(tv.col, G - 5 * H), outline="", smooth=False)
    if tv.kind == "trader":
        px_ = x - tv.dir * 0.9 * H
        pk = [px_ - 0.5 * H, G - 6.2 * H, px_ + 0.5 * H, G - 6.2 * H, px_ + 0.5 * H, G - 4.3 * H, px_ - 0.5 * H, G - 4.3 * H]
        P.put("polygon", [c for i in range(0, 8, 2) for c in W(pk[i], pk[i + 1])], "fauna",
              fill=gc("#6b4a2e", G - 5 * H), outline="", smooth=False)
    elif tv.kind == "raider":
        P.put("line", [*W(x + tv.dir * 0.9 * H, G - 7.8 * H), *W(x + tv.dir * 0.9 * H, G - 2.5 * H)], "fauna",
              fill=gc("#8a8a8a", G), width=2)
    elif tv.kind in ("refugee", "migrant"):
        P.put("line", [*W(x + tv.dir * 0.8 * H, G - 5.5 * H), *W(x + tv.dir * 1.0 * H, G)], "fauna",
              fill=gc("#5a4632", G), width=2)
    arm = _so_math.sin(ph) * 0.5 * H * walking
    P.put("line", [*W(x, G - 6.1 * H), *W(x + arm * tv.dir, G - 4.4 * H)], "fauna",
          fill=gc(tv.skin, G - 5 * H), width=max(2, int(0.18 * H * cam.zoom)))
    (hx, hy) = W(x, G - 6.95 * H)
    r = 0.5 * H * cam.zoom
    P.put("oval", [hx - r, hy - r * 1.15, hx + r, hy + r * 1.15], "fauna", fill=gc(tv.skin, G - 7 * H), outline="")
    P.put("oval", [hx - r * 1.05, hy - r * 1.3, hx + r * 1.05, hy - r * 0.2], "fauna",
          fill=gc("#4a3424" if tv.kind != "raider" else "#2a2a2a", G - 7 * H), outline="")
    P.end()


def _so_society(app):
    soc = getattr(app, "society", None)
    if soc is None:
        saved = (getattr(app.brain.mind, "_world_saved", None) or {}).get("society")
        try:
            soc = Society.from_dict(saved) if saved else Society(seed=getattr(app.brain.personality, "body_seed", 7))
        except Exception:
            soc = Society(seed=7)
        app.society = soc
        app.travellers = []
    return soc


def _so_tick(app, dt):
    soc = _so_society(app)
    app._so_acc = getattr(app, "_so_acc", 0.0) + dt
    if app._so_acc >= 30.0:
        soc.step(app._so_acc / SOC_DAY)
        app._so_acc = 0.0
    # journeys through the valley become visible travellers
    while soc.travel and len(app.travellers) < 2:
        trip = soc.travel.pop(0)
        app.travellers.append(Traveller(trip, soc, app.world, _so_random))
    life = _lf_life(app)
    cr, b = app.creature, app.brain
    H = cr._Hb()
    keep = []
    for tv in app.travellers:
        tv.t += dt
        d = abs(tv.x - cr.x)
        if tv.stop > 0:
            tv.stop -= dt
        else:
            tv.x += tv.dir * (55.0 if tv.kind != "raider" else 90.0) * dt
        inside = 100 <= tv.x <= app.world.w - 100          # only meet where she can actually reach
        if not tv.met and d < 7 * H and inside:
            tv.met = True
            where = tv.trip["from"]
            if tv.kind == "raider":
                b.perceive(Event("danger", f"armed raiders from {where} are passing through", salience=0.8, valence=-0.6))
                b.mind.risk.recent_lightning = max(b.mind.risk.recent_lightning, 0.9)
                sv = getattr(app, "survival", None)
                if sv and d < 4 * H and (sv.inv.get("meat", 0) or sv.inv.get("wood", 0) > 2):
                    took = "meat" if sv.inv.get("meat", 0) else "wood"
                    sv.inv[took] = max(0, sv.inv[took] - (1 if took == "meat" else 3))
                    b.perceive(Event("danger", f"the raiders took my {took}", salience=0.8, valence=-0.7))
            else:
                news = tv.trip.get("news")
                text = f"{tv.name}, a {tv.kind} from {where}, passed through"
                if news:
                    text += f" - they said {news[3]}"
                    b.perceive(Event("news", text, salience=0.6, valence=-0.2 if news[2] in ("war", "raid", "famine", "collapse", "revolt") else 0.2))
                else:
                    b.perceive(Event("social", text, salience=0.5, valence=0.2))
                try:
                    b.knowledge.see("place", where, valence=0.0, note=f"a settlement {tv.kind}s come from")
                    b.knowledge.see("person", tv.name, valence=0.1, note=f"{tv.kind} from {where}")
                except Exception:
                    pass
                people = life.__dict__.setdefault("people", {})
                pid = tv.npc.id if tv.npc else tv.name
                p = people.setdefault(pid, {"name": tv.name, "from": where, "met": 0, "like": 0.0})
                p["met"] += 1
                if tv.npc:
                    tv.npc.rel["jane"] = clamp(tv.npc.rel.get("jane", 0.0) + 0.1, -1, 1)
                    tv.npc.remember(soc.day, "met the woman who lives in the valley", 0.2)
                if tv.kind == "trader":
                    tv.stop = 25.0                              # a trader lingers near a customer
                b.goals.satisfy("social", 0.15, f"talked with {tv.name}")
        if -80 < tv.x < app.world.w + 80:
            keep.append(tv)
            _so_draw_traveller(tv, app)
        elif tv.pool is not None:
            tv.pool.begin()
            tv.pool.end()
    app.travellers = keep


# ---- barter: an affordance while a trader is here ---------------------------------
_AG_EXTRA["trade"] = dict(pre={"surplus": 1}, eff={"traded": ("set", 1)}, dur=4.0, at="trader", task="trade")
_AG_SAY["trade"] = "trade with the traveller"

_so_prev_where = _ag_where


def _so_where(app, sv, life, at, cand):
    if at == "trader":
        tv = next((t for t in getattr(app, "travellers", []) if t.kind == "trader" and t.stop > 0), None)
        return tv.x + (1.3 if app.creature.x > tv.x else -1.3) * app.creature._Hb() if tv else None
    return _so_prev_where(app, sv, life, at, cand)


_ag_where = _so_where

_so_prev_plan_adjust = _m41_plan_adjust


def _so_plan_adjust(sv, app, life, cand):
    _so_prev_plan_adjust(sv, app, life, cand)
    tv = next((t for t in getattr(app, "travellers", []) if t.kind == "trader" and t.stop > 0 and not t.traded), None)
    if tv is None:
        return
    owned = life.__dict__.setdefault("possessions", [])
    wants = [g for g in ("blanket", "salt", "lantern") if g not in owned]
    if not wants or not (sv.inv.get("wood", 0) >= 3 or sv.inv.get("meat", 0) >= 1 or sv.inv.get("berries", 0) >= 2):
        return
    cold = app.brain.mind.comfort.cold
    want = 0.3 + 0.4 * ("blanket" in wants) * (0.5 + cold) + 0.2 * app.brain.goals.social
    cand["trade"] = (want, ("trade", tv.x))


_m41_plan_adjust = _so_plan_adjust

_so_prev_act = Survival._act


def _so_act(self, app, dt):
    if self.task and self.task[0] == "trade":
        tv = next((t for t in getattr(app, "travellers", []) if t.kind == "trader" and t.stop > 0), None)
        cr = app.creature
        if tv is None:
            self.task = None
            return
        tx = tv.x + (1.3 if cr.x > tv.x else -1.3) * cr._Hb()
        if abs(cr.x - tx) > 18:
            cr.set_target(tx, cr.y)
            tv.stop = max(tv.stop, 8.0)
            return
        life = _lf_life(app)
        owned = life.__dict__.setdefault("possessions", [])
        good = next((g for g in ("blanket", "salt", "lantern") if g not in owned), None)
        rep = 0.0
        soc = getattr(app, "society", None)
        src = soc.sets.get(tv.trip["from"]) if soc else None
        if src:
            rep = src.jane_rep
        pay = None
        for k, n in (("wood", 3), ("meat", 1), ("berries", 2)):
            need = max(1, int(round(n * (1.2 - 0.4 * rep))))          # reputation changes the price
            if self.inv.get(k, 0) >= need:
                pay = (k, need)
                break
        if good and pay:
            self.inv[pay[0]] -= pay[1]
            owned.append(good)
            tv.traded = True
            self._traded_t = life.clock
            if tv.npc:
                tv.npc.wealth += pay[1]
                tv.npc.rel["jane"] = clamp(tv.npc.rel.get("jane", 0) + 0.2, -1, 1)
                tv.npc.remember(soc.day if soc else 0, f"traded with the valley woman", 0.3)
            if src:
                src.jane_rep = clamp(src.jane_rep + 0.1, -1, 1)
                src.stock["goods"] = max(0.0, src.stock["goods"] - 1)
            p = life.__dict__.setdefault("people", {}).get(tv.npc.id if tv.npc else tv.name)
            if p:
                p["like"] = clamp01(p["like"] + 0.2)
            app.brain.perceive(Event("trade", f"traded {pay[1]} {pay[0]} with {tv.name} for {_SO_GOODS[good][0]}",
                                     salience=0.6, valence=0.45))
        self.task = None
        return
    return _so_prev_act(self, app, dt)


Survival._act = _so_act

# goods change her life: warmth, meals, a lit home
_so_prev_comfort = ThermalComfort.update


def _so_comfort(self, dt, wx, sheltered, moving):
    if "blanket" in getattr(self, "_possessions", ()) and not moving:
        wx = dict(wx, temp=wx.get("temp", 20.0) + 3.0)
    return _so_prev_comfort(self, dt, wx, sheltered, moving)


ThermalComfort.update = _so_comfort

_so_prev_satisfy = GoalSystem.satisfy


def _so_satisfy(self, need, amount, note=""):
    if need == "hunger" and "cooked" in (note or "") and "salt" in getattr(self, "_possessions", ()):
        amount *= 1.25
    return _so_prev_satisfy(self, need, amount, note)


GoalSystem.satisfy = _so_satisfy

# persistence + offline advance through M43
_m43_save_hooks.append(lambda app: ("society", app.society.to_dict()) if getattr(app, "society", None) else ("society", None))


def _so_offline(app, E, report):
    soc = _so_society(app)
    days = E / SOC_DAY
    n0 = len(soc.events)
    step = 1.0
    t = 0.0
    while t < days:
        soc.step(min(step, days - t))
        t += step
    new = sorted(soc.events[n0:], key=lambda e: -e[4])
    if new:
        passed = [e for e in new if e[4] >= 0.7][:2]
        for e in passed:
            report.append((f"a traveller passing through said {e[3]}", 0.6, -0.1 if e[2] in ("war", "raid", "famine", "collapse") else 0.1))
    soc.travel = soc.travel[-2:]


_m43_offline_hooks.append(_so_offline)

_so_prev_update = App._update_world


def _so_update(self, dt):
    _so_prev_update(self, dt)
    try:
        _so_tick(self, dt)
        life = _lf_life(self)
        pos = tuple(life.__dict__.get("possessions", []))
        self.brain.mind.comfort._possessions = pos
        self.brain.goals._possessions = pos
        if "lantern" in pos and life.home and self.world.daypart in ("evening", "night") \
                and abs(self.creature.x - life.home["x"]) < 2 * self.creature._Hb():
            self.brain.emotion.nudge("valence", dt * 0.005, "")
    except Exception:
        traceback.print_exc()


App._update_world = _so_update

_so_prev_life_to = JaneLife.to_dict
_so_prev_life_from = JaneLife.from_dict


def _so_life_to(self):
    d = _so_prev_life_to(self)
    d["possessions"] = list(getattr(self, "possessions", []))
    d["people"] = getattr(self, "people", {})
    return d


def _so_life_from(self, d):
    _so_prev_life_from(self, d)
    if isinstance(d, dict):
        self.possessions = list(d.get("possessions") or [])
        self.people = dict(d.get("people") or {})


JaneLife.to_dict = _so_life_to
JaneLife.from_dict = _so_life_from
