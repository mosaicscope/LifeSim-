# ============================================================================
# [NEW] MORAL & EMOTIONAL LIFE  (extends the M44/M46 society, loaded after it)
# ============================================================================
#
# Nothing here is a scripted event. Each society day, individuals act on
# one another; WHICH act is chosen by who they are (compassion, cruelty,
# courage, forgiveness - from their traits), what is happening to them
# (hunger, poverty, grief, war, stress) and what lies between them (affection,
# trust, grudges, gratitude, family). Kind and dark acts go through the same
# scoring, so kindness has the same systemic weight as cruelty - which one
# a person reaches for depends on the person and the moment.
#
# Every act has consequences that persist and feed back:
#   bonds change (affection, trust, grudge, gratitude); injuries and deaths
#   are physical (health, recovery, graves); guards catch crimes and punish;
#   reputations rise and fall; the bereaved grieve (and grief drives the next
#   choices - withdrawal, revenge, or turning to comfort others); lovers
#   pair and raise children who inherit their parents' natures; people who
#   wronged others may carry guilt, apologise and be forgiven - or not.
# Raids (M46 war) now fall on individuals: defenders fight, the brave shield
# the people they love, and some give their lives doing it.

import random as _mo_random


def _mo(n):
    """Lazily extend an NPC with moral/emotional state (save-compatible)."""
    d = n.__dict__
    if "bonds" not in d:
        t = n.t
        d["bonds"] = {}
        d["partner"] = None
        d["kids"] = []
        d["parents"] = []
        d["grief"] = [None, 0.0]               # (for whom, how much)
        d["injury"] = 0.0
        d["crimes"] = 0
        d["honor"] = 0.0
        d["guilt"] = {}                        # victim id -> weight
        d["mourned"] = False
        d["kindness"] = round(0.4 * t["sociability"] + 0.4 * t["piety"] + 0.2 * t["honesty"], 3)
        d["cruelty"] = round(0.6 * t["aggression"] + 0.4 * (1 - t["honesty"]) - 0.2 * t["piety"], 3)
        d["courage"] = round(0.5 * t["aggression"] + 0.3 * t["sociability"] + 0.2 * (n.role == "guard"), 3)
        d["mercy"] = round(0.5 * t["piety"] + 0.3 * t["sociability"] + 0.2 * (1 - t["aggression"]), 3)
    return n


def _bond(a, b):
    return _mo(a).bonds.setdefault(b.id, {"aff": 0.0, "trust": 0.3, "grudge": 0.0, "grat": 0.0, "kin": ""})


def _adult(n):
    return 18 <= n.phys["age"] <= 60 and n.role != "child"


class MoralEngine:
    def __init__(self, soc):
        self.soc = soc

    # -- act utilities: the same scale for light and dark -----------------------------
    def _options(self, a, b, s, circ):
        A, B = _mo(a), _mo(b)
        ab = _bond(a, b)
        need_b = max(b.phys["hunger"], B.injury, B.grief[1])
        desperate = max(a.phys["hunger"], 1.0 - min(1.0, a.wealth / 6.0)) * (0.5 + circ["famine"])
        stress = a.emo["stress"] + 0.5 * A.grief[1]
        o = {
            "help": A.kindness * need_b * (0.5 + ab["aff"]) * (1.0 - 0.5 * a.phys["hunger"]) * (a.wealth > 0.5),
            "comfort": A.kindness * B.grief[1] * (0.4 + ab["aff"]),
            "befriend": 0.35 * a.t["sociability"] * (1.0 - ab["grudge"]) * (1.0 - abs(a.t["sociability"] - b.t["sociability"])),
            "court": 0.0,
            "forgive": ab["grudge"] * A.mercy * (0.3 + ab["grat"] + 0.5 * B.guilt.get(a.id, 0.0)),
            "apologize": A.guilt.get(b.id, 0.0) * (0.4 + 0.6 * a.t["honesty"]),
            "quarrel": stress * (1.0 - ab["aff"]) * a.t["aggression"] * 0.6 + 0.4 * ab["grudge"],
            "assault": A.cruelty * (ab["grudge"] + 0.3 * desperate + 0.3 * stress) * (1.0 - 0.6 * circ["guards"]) - 0.25,
            "steal": desperate * (1.0 - a.t["honesty"]) * min(1.0, b.wealth / 10.0) * (1.0 - 0.5 * circ["guards"]) - 0.1,
            "betray": a.t["ambition"] * (1.0 - a.t["honesty"]) * ab["trust"] * circ["unrest"] - 0.2,
            "exploit": (a.role in ("leader", "trader")) * a.t["ambition"] * (1.0 - a.t["honesty"])
                       * max(0.0, (a.wealth - b.wealth) / 20.0) - 0.1,
        }
        if (_adult(a) and _adult(b) and A.partner is None and B.partner is None and ab["aff"] > 0.45
                and a.name.split()[-1] != b.name.split()[-1] and ab["kin"] == ""      # not family
                and _bond(b, a)["aff"] > 0.35):
            spark = (hash((min(a.id, b.id), max(a.id, b.id))) % 1000) / 1000.0     # chemistry is personal
            o["court"] = ab["aff"] * (0.4 + spark) * (1.0 - circ["famine"] * 0.5)
        return o

    # -- consequences ---------------------------------------------------------------------
    def _log(self, s, kind, text, imp, who=()):
        self.soc.log(s.name, kind, text, imp)
        for n in who:
            n.remember(self.soc.day, text, {"help": 0.4, "love": 0.7, "forgive": 0.4, "birth": 0.6, "comfort": 0.3,
                                             "sacrifice": 0.2}.get(kind, -0.4))

    def _injure(self, n, amt, s, cause):
        m = _mo(n)
        m.injury = clamp01(m.injury + amt)
        n.phys["health"] = clamp01(n.phys["health"] - amt * 0.8)
        if n.phys["health"] <= 0.05:
            n.alive = False
            n.cause = cause
            return True
        return False

    def _act(self, kind, a, b, s, circ, ppl):
        A, B = _mo(a), _mo(b)
        ab, ba = _bond(a, b), _bond(b, a)
        r = self.soc.r
        if kind == "help":
            give = min(a.wealth * 0.3, 3.0)
            a.wealth -= give
            b.wealth += give
            b.phys["hunger"] = max(0.0, b.phys["hunger"] - 0.4)
            B.injury = max(0.0, B.injury - 0.2)
            ba["grat"] = clamp01(ba["grat"] + 0.35)
            ba["aff"] = clamp01(ba["aff"] + 0.2)
            ab["aff"] = clamp01(ab["aff"] + 0.1)
            A.honor += 0.1
            a.emo["valence"] = clamp(a.emo["valence"] + 0.15, -1, 1)
            if b.phys["hunger"] > 0.3 or B.injury > 0.3 or give > 1.5:
                self._log(s, "help", f"{a.name} shared what they had with {b.name}, who was in need", 0.45, (a, b))
        elif kind == "comfort":
            B.grief[1] = max(0.0, B.grief[1] - 0.25)
            ba["aff"] = clamp01(ba["aff"] + 0.15)
            ab["aff"] = clamp01(ab["aff"] + 0.1)
            if r.random() < 0.3:
                self._log(s, "comfort", f"{a.name} sat with the grieving {b.name}", 0.35, (a, b))
        elif kind == "befriend":
            ab["aff"] = clamp01(ab["aff"] + 0.08)
            ba["aff"] = clamp01(ba["aff"] + 0.06)
            ab["trust"] = clamp01(ab["trust"] + 0.03)
        elif kind == "court":
            A.partner, B.partner = b.id, a.id
            ab["aff"] = ba["aff"] = max(ab["aff"], ba["aff"], 0.8)
            ab["kin"] = ba["kin"] = "partner"
            self._log(s, "love", f"{a.name} and {b.name} fell in love", 0.6, (a, b))
        elif kind == "forgive":
            ab["grudge"] = 0.0
            ab["aff"] = clamp01(ab["aff"] + 0.15)
            B.guilt.pop(a.id, None)
            self._log(s, "forgive", f"{a.name} forgave {b.name}", 0.55, (a, b))
        elif kind == "apologize":
            pay = min(a.wealth * 0.4, 4.0)
            a.wealth -= pay
            b.wealth += pay
            A.guilt[b.id] = A.guilt.get(b.id, 0.0) * 0.4
            ba["grudge"] = max(0.0, ba["grudge"] - 0.25 * B.mercy)
            if r.random() < 0.5:
                self._log(s, "apology", f"{a.name} went to {b.name} to make amends", 0.4, (a, b))
        elif kind == "quarrel":
            ab["grudge"] = clamp01(ab["grudge"] + 0.1)
            ba["grudge"] = clamp01(ba["grudge"] + 0.1)
            ab["aff"] = max(0.0, ab["aff"] - 0.1)
            ba["aff"] = max(0.0, ba["aff"] - 0.1)
        elif kind == "assault":
            self._violence(a, b, s, circ, ppl)
        elif kind == "steal":
            take = min(b.wealth * 0.3, 5.0)
            caught = r.random() < 0.15 + 0.6 * circ["guards"]
            if caught:
                A.crimes += 1
                A.honor -= 0.4
                ba["grudge"] = clamp01(ba["grudge"] + 0.3)
                a.wealth = max(0.0, a.wealth - 2.0)
                self._punish(a, s, "theft")
                self._log(s, "crime", f"{a.name} was caught stealing from {b.name}", 0.55, (a, b))
            else:
                a.wealth += take
                b.wealth -= take
                A.guilt[b.id] = A.guilt.get(b.id, 0.0) + 0.3 * (a.t["piety"] + a.t["honesty"])
                b.emo["valence"] = clamp(b.emo["valence"] - 0.2, -1, 1)
                if take > 1.5 and r.random() < 0.3:
                    self._log(s, "crime", f"someone robbed {b.name} in the night", 0.45, (b,))
        elif kind == "betray":
            ba["trust"] = 0.0
            ba["grudge"] = clamp01(ba["grudge"] + 0.6)
            ba["aff"] = max(0.0, ba["aff"] - 0.4)
            a.wealth += 3.0
            b.emo["valence"] = clamp(b.emo["valence"] - 0.5, -1, 1)
            if B.partner == a.id:
                B.partner = A.partner = None
            A.guilt[b.id] = A.guilt.get(b.id, 0.0) + 0.3 * a.t["piety"]
            self._log(s, "betrayal", f"{a.name} betrayed {b.name}'s trust", 0.65, (a, b))
        elif kind == "exploit":
            take = min(b.wealth * 0.25, 4.0)
            a.wealth += take
            b.wealth -= take
            ba["grudge"] = clamp01(ba["grudge"] + 0.2)
            s.unrest = clamp01(s.unrest + 0.02)

    def _violence(self, a, b, s, circ, ppl):
        r = self.soc.r
        A, B = _mo(a), _mo(b)
        # someone may step in: whoever cares enough and is brave enough
        guards = [n for n in ppl if n.role == "guard" and n is not a and n is not b]
        protectors = sorted((n for n in ppl if n not in (a, b) and _bond(n, b)["aff"] > 0.4),
                            key=lambda n: -(_bond(n, b)["aff"] * _mo(n).courage))
        target = b
        if protectors and r.random() < _bond(protectors[0], b)["aff"] * _mo(protectors[0]).courage * 1.5:
            p = protectors[0]
            target = p
            self._log(s, "protect", f"{p.name} threw themself between {a.name} and {b.name}", 0.6, (p, b))
            _bond(b, p)["grat"] = clamp01(_bond(b, p)["grat"] + 0.5)
            _bond(b, p)["aff"] = clamp01(_bond(b, p)["aff"] + 0.3)
            _mo(p).honor += 0.3
        pa = a.phys["health"] * (0.5 + a.t["aggression"]) * (1.3 if a.role == "guard" else 1.0)
        pt = target.phys["health"] * (0.5 + target.t["aggression"]) * (1.3 if target.role == "guard" else 1.0)
        loser = target if r.random() < pa / (pa + pt) else a
        died = self._injure(loser, r.uniform(0.2, 0.7), s, f"killed in a fight with {(a if loser is target else target).name}")
        if died:
            killer = a if loser is not a else target
            _mo(killer).crimes += 1
            _mo(killer).honor -= 0.8
            if target is not b and loser is target:
                self._log(s, "sacrifice", f"{target.name} died protecting {b.name}", 0.9, (b,))
            else:
                self._log(s, "violence", f"{loser.name} was killed by {killer.name}", 0.85, ())
            self._punish(killer, s, "killing")
        else:
            self._log(s, "violence", f"{a.name} attacked {b.name if target is b else target.name}; {loser.name} was hurt", 0.6, (a, target))
            if guards and r.random() < 0.3 + 0.5 * circ["guards"]:
                _mo(a).crimes += 1
                self._punish(a, s, "assault")
        _bond(b, a)["grudge"] = clamp01(_bond(b, a)["grudge"] + 0.5)
        for kin in (x for x in ppl if _bond(x, b)["kin"] in ("partner", "parent", "child")):
            _bond(kin, a)["grudge"] = clamp01(_bond(kin, a)["grudge"] + 0.4)      # feuds start here

    def _punish(self, n, s, crime):
        r = self.soc.r
        harsh = 0.3 + 0.5 * s.culture["tradition"] + 0.3 * (s.gov == "chief")
        mercy = sum(_mo(x).mercy for x in self.soc.people(s.name)) / max(1, len(self.soc.people(s.name)))
        if crime == "killing" and r.random() < harsh - 0.3 * mercy:
            others = [o for o in self.soc.sets.values() if o.alive and o is not s]
            if others:
                n.sett = r.choice(others).name
                n.remember(self.soc.day, f"was exiled from {s.name} for {crime}", -0.8)
                self._log(s, "exile", f"{n.name} was exiled for {crime}", 0.7, ())
                return
        n.wealth = max(0.0, n.wealth - 2.0 * harsh)
        n.emo["valence"] = clamp(n.emo["valence"] - 0.3, -1, 1)

    # -- raids fall on individuals ---------------------------------------------------------
    def raid(self, s):
        r = self.soc.r
        ppl = self.soc.people(s.name)
        if not ppl:
            return
        for victim in r.sample(ppl, min(len(ppl), 2)):
            circ = {"guards": 0.0}
            defenders = sorted((n for n in ppl if n is not victim and (n.role == "guard" or _bond(n, victim)["aff"] > 0.5)),
                               key=lambda n: -_mo(n).courage)
            if defenders and r.random() < _mo(defenders[0]).courage + 0.2:
                d = defenders[0]
                if self._injure(d, r.uniform(0.3, 0.9), s, "fell defending the village"):
                    self._log(s, "sacrifice", f"{d.name} fell holding off the raiders so {victim.name} could escape", 0.9, (victim,))
                else:
                    self._log(s, "rescue", f"{d.name} fought off raiders to save {victim.name}", 0.7, (d, victim))
                _bond(victim, d)["grat"] = clamp01(_bond(victim, d)["grat"] + 0.6)
                _bond(victim, d)["aff"] = clamp01(_bond(victim, d)["aff"] + 0.4)
                _mo(d).honor += 0.5
            elif self._injure(victim, r.uniform(0.3, 1.0), s, "killed by raiders"):
                self._log(s, "violence", f"{victim.name} was killed in the raid", 0.8, ())

    # -- one society step -------------------------------------------------------------------
    def step(self, days):
        soc = self.soc
        r = soc.r
        for s in [x for x in soc.sets.values() if x.alive]:
            ppl = soc.people(s.name)
            if len(ppl) < 2:
                continue
            guards = sum(1 for n in ppl if n.role == "guard")
            circ = {"famine": float(s.hunger_days > 0), "guards": min(1.0, guards / 3.0),
                    "unrest": s.unrest, "war": float(bool(s.war))}
            for _ in range(int(days * len(ppl) * 1.2 + r.random())):
                a = r.choice(ppl)
                known = [p for p in ppl if p.id in _mo(a).bonds and p is not a]
                b = r.choice(known) if known and r.random() < 0.7 else r.choice(ppl)
                if b is a or not a.alive or not b.alive:
                    continue
                opts = self._options(a, b, s, circ)
                kind = max(opts, key=lambda k: opts[k] + r.uniform(0, 0.15))
                if opts[kind] > 0.18:
                    self._act(kind, a, b, s, circ, ppl)
            # physiology of the heart: grief fades (faster with comfort), injuries heal
            for n in ppl:
                m = _mo(n)
                m.grief[1] = max(0.0, m.grief[1] - days * 0.03)
                m.injury = max(0.0, m.injury - days * 0.05)
                if m.grief[1] > 0.3:
                    n.emo["valence"] = clamp(n.emo["valence"] - days * 0.1, -1, 1)
                for bid, bd in m.bonds.items():
                    bd["grudge"] = max(0.0, bd["grudge"] - days * 0.004 * m.mercy)
                # a grieving person may seek the one who caused it
                cause = getattr(soc.npcs.get(m.grief[0]), "cause", "") if m.grief[0] else ""
                if m.grief[1] > 0.5 and "killed" in cause:
                    killer_name = cause.split("with ")[-1] if "with " in cause else None
                    k = next((x for x in ppl if x.name == killer_name), None)
                    if k is not None and r.random() < days * n.t["aggression"] * 0.5:
                        self._log(s, "revenge", f"{n.name} went after {k.name} for what happened", 0.7, (n,))
                        self._violence(n, k, s, circ, ppl)
            # families grow
            for n in ppl:
                m = _mo(n)
                p = soc.npcs.get(m.partner) if m.partner else None
                if p and p.alive and p.sett == n.sett and n.id < p.id and _adult(n) and n.phys["age"] < 45 \
                        and s.stock["food"] > s.pop and r.random() < days * 0.02:
                    child = NPC(r, s.name, role="child")
                    child.phys["age"] = 0
                    child.t = {k: clamp01((n.t[k] + p.t[k]) / 2 + r.uniform(-0.15, 0.15)) for k in n.t}
                    child.name = f"{r.choice(_SO_FIRST)} {n.name.split()[-1]}"      # family name
                    soc._assign(child)
                    _mo(child).parents = [n.id, p.id]
                    for par in (n, p):
                        _mo(par).kids.append(child.id)
                        _bond(par, child).update(aff=0.9, kin="child")
                        _bond(child, par).update(aff=0.9, kin="parent")
                    soc.npcs[child.id] = child
                    s.pop += 1
                    self._log(s, "birth", f"a child, {child.name}, was born to {n.name} and {p.name}", 0.6, (n, p))
                if n.role == "child" and n.phys["age"] >= 16:
                    n.role = r.choice(_SO_ROLES)
        # the dead are mourned by those who loved them
        for n in list(soc.npcs.values()):
            if n.alive or _mo(n).mourned:
                continue
            _mo(n).mourned = True
            for o in soc.people(n.sett) + [x for x in soc.npcs.values() if x.alive and n.id in _mo(x).bonds]:
                bd = _mo(o).bonds.get(n.id)
                if bd and bd["aff"] > 0.3:
                    _mo(o).grief = [n.id, max(_mo(o).grief[1], bd["aff"])]
                    o.remember(soc.day, f"lost {n.name}", -0.8)
                    if _mo(o).partner == n.id:
                        _mo(o).partner = None


# ---- integration with the society ------------------------------------------------------
_mo_prev_step = Society.step


def _mo_step(self, days):
    _mo_prev_step(self, days)
    if days > 0:
        try:
            eng = self.__dict__.setdefault("_moral", None) or MoralEngine(self)
            self._moral = eng
            eng.step(days)
        except Exception:
            traceback.print_exc()


Society.step = _mo_step

_mo_prev_log = Society.log


def _mo_log(self, where, kind, text, imp):
    _mo_prev_log(self, where, kind, text, imp)
    if kind == "raid" and not getattr(self, "_in_raid", False):
        s = self.sets.get(where)
        if s is not None:
            self._in_raid = True
            try:
                (self.__dict__.get("_moral") or MoralEngine(self)).raid(s)
            except Exception:
                traceback.print_exc()
            finally:
                self._in_raid = False


Society.log = _mo_log

_mo_prev_to = Society.to_dict


def _mo_to(self):
    d = _mo_prev_to(self)
    return d


Society.to_dict = _mo_to
