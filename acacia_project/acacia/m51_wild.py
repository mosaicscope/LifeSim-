# ============================================================================
# [NEW] WILD ANIMALS, EARNED TRUST
# ============================================================================
#
# Fear of Jane was SPECIES-wide familiarity that only grew, so after a few
# sessions every deer let her walk up to it. Now fear and trust belong to the
# individual, start where a wild animal's would, and change only through
# what actually happens between them:
#
#   flight distance  per species (a deer bolts at ~18 m, a rabbit at ~6 m),
#                    individual (boldness), shrinking as THIS animal's trust
#                    grows, growing with its fear and with how fast Jane is
#                    coming at it
#   alert zone       beyond it: the animal stops, lifts its head and watches
#   flight           it runs well clear, then turns and watches from safety;
#                    its alarm spreads to others of its kind nearby
#   habituation      calm presence outside its comfort zone slowly builds
#                    trust (faster if she sits still); rushing it, cornering
#                    it or hunting near it sets it back - all persistent
#   food             she can leave food out and back off; a hungry animal
#                    that trusts her a little comes to eat it, and trusts her
#                    more for it
#
# Jane decides by herself - from curiosity, loneliness, her opinion of the
# animal and what she has learned (M41) - to sit and watch an animal from a
# respectful distance, or to leave food for it. Touching comes only after
# trust. Animals also keep their own space from each other (no overlapping).

import math as _wd_math

# flight initiation distance (m), starting trust, habituation speed
WILD = {
    "rabbit": dict(fid=6.0, t0=0.03, hab=1.0),
    "deer": dict(fid=18.0, t0=0.02, hab=0.6),
    "fox": dict(fid=12.0, t0=0.03, hab=0.8),
    "wolf": dict(fid=25.0, t0=0.0, hab=0.3),
    "bird": dict(fid=5.0, t0=0.05, hab=1.2),
    "dog": dict(fid=3.0, t0=0.35, hab=1.5),
    "cat": dict(fid=4.0, t0=0.15, hab=1.0),
}


def _wd_trust_fear(psy):
    R = psy.rel_of("jane")
    return R["trust"], R["fear"]


def wild_fid(a, jane=None, jspeed=0.0):
    """This animal's flight distance from Jane right now, in px."""
    W = WILD.get(a.sp)
    p = getattr(a, "psy", None)
    if W is None or p is None:
        return None
    trust, fear = _wd_trust_fear(p)
    bold = p.idn["traits"]["boldness"]
    base = W["fid"] * WS.px * (1.4 - 0.8 * bold)
    tamed = clamp01((trust - W["t0"]) / 0.85)
    fid = base * (1.0 - 0.88 * tamed) * (1.0 + 0.8 * fear)
    toward = 0.0
    if jane is not None:
        vx = getattr(getattr(jane, "_loco", None), "vx", 0.0)
        if (vx > 0) == (a.x > jane.x):
            toward = abs(vx) / (1.2 * WS.px)                   # metres per second toward it
    # being walked toward only alarms an animal that doesn't trust her
    return fid * (1.0 + 0.6 * toward * (1.0 - clamp01(trust / 0.6))), toward


# fresh individuals meet Jane as wild animals do
_wd_prev_rel_of = Psyche.rel_of


def _wd_rel_of(self, who):
    fresh = who not in self.rel
    R = _wd_prev_rel_of(self, who)
    if fresh and who == "jane":
        W = WILD.get(self.sp)
        if W is not None:
            R["trust"] = W["t0"]
            R["fear"] = 0.25 * (1.0 - self.idn["traits"]["boldness"]) + (0.0 if self.sp == "dog" else 0.15)
    return R


Psyche.rel_of = _wd_rel_of


def _wd_threat(fa, a, d, jspeed, jane, dt, world):
    p = getattr(a, "psy", None)
    if p is None or jane is None or a.sp not in WILD or a.S["flee"] <= 0:
        return None
    fid, toward = wild_fid(a, jane)
    R = p.rel_of("jane")
    clock = getattr(fa, "clock", 0.0)
    if R["trust"] > 0.6 and R["fear"] < 0.3 and toward < 2.0:
        return 0.0                                  # a friend doesn't bolt when she steps near
    sitting = jane.behavior == "rest" or getattr(jane._loco, "sit", 0.0) > 0.5
    if d < fid:
        if a.state != "flee":
            # it ran because she came too close - remembered, and felt
            if toward > 0.05:
                p.learn("jane", clock, "Jane came at me", -0.25, fear=0.05 * (1 + toward), trust=-0.01)
            a._flee_run = fid * 1.6 + WS.m(6.0)
            p._watch_until = clock + 8.0 + 10.0 * (1.0 - p.idn["traits"]["boldness"])
            for o in fa.animals:                                   # alarm spreads to its kind
                if o is not a and o.sp == a.sp and abs(o.x - a.x) < WS.m(15.0) and getattr(o, "psy", None):
                    ot, _of = _wd_trust_fear(o.psy)
                    o.fear = max(o.fear, 0.55 * (1.0 - ot))
        return 1.0
    # beyond its comfort zone: calm, patient presence slowly builds trust
    p._hab_acc = getattr(p, "_hab_acc", 0.0) + dt
    if p._hab_acc > 0.5:
        span = p._hab_acc
        p._hab_acc = 0.0
        if d < fid * 3.5 and jspeed < 0.9 * WS.px:
            rate = 0.0022 * WILD[a.sp]["hab"] * p.idn["learning_rate"] * (2.2 if sitting else 1.0)
            R["trust"] = clamp01(R["trust"] + span * rate * (1.0 - R["trust"]))
            R["fear"] = max(0.0, R["fear"] - span * rate * 0.8)
            R["fam"] = clamp01(R["fam"] + span * 0.003)
    if d < fid * 1.7:
        return 0.3                                                  # alert, not yet running
    return 0.0


_wild_threat = _wd_threat


# after a scare it watches her from safety; offered food draws a hungry one in
_wd_prev_drive = Psyche.drive


def _wd_drive(self, a, fa, world, jane, dt):
    clock = getattr(fa, "clock", 0.0)
    if jane is not None and a.sp in WILD and not a.S.get("flyer"):
        fid, _t = wild_fid(a, jane)
        d = abs(a.x - jane.x)
        # food she left out
        offs = getattr(fa, "_offerings", None) or []
        trust, fear = _wd_trust_fear(self)
        # a hungry animal takes food left out as long as she is far enough
        # away to feel safe - the trust comes FROM eating it
        if offs and self.need["hunger"] > 0.2 and a.sp != "wolf":
            o = min(offs, key=lambda o: abs(o["x"] - a.x))
            if abs(o["x"] - a.x) < WS.m(25.0) and abs(o["x"] - jane.x) > fid * 0.75:
                if abs(a.x - o["x"]) > WS.m(0.4):
                    a.state, a.goal = "approach", o["x"]
                else:
                    a.state, a.goal = "graze", a.x
                    o["eat"] = o.get("eat", 0.0) + dt
                    if o["eat"] > 3.0:
                        o["eat"] = 0.0
                        o["amount"] -= 1
                        self.need["hunger"] = max(0.0, self.need["hunger"] - 0.35)
                        self.learn("jane", clock, "Jane left food for me", 0.6, trust=0.09, like=0.1, fear=-0.05)
                        o["eaten_by"] = (a.sp, self.seed)
                return True
        # a friend: comes along when she walks off, no defensive distance
        if trust > 0.6 and fear < 0.3:
            r = _wd_prev_drive(self, a, fa, world, jane, dt)
            walking_off = abs(getattr(jane._loco, "vx", 0.0)) > 0.4 * WS.px and d > WS.m(3.0)
            if walking_off and a.sp in ("dog", "cat") and a.state not in ("drink", "graze", "sleep") \
                    and self.need["hunger"] < 0.7 and self.need["fatigue"] < 0.8:
                a.state = "follow"
                a.goal = jane.x - (1.0 if jane._loco.vx > 0 else -1.0) * WS.m(1.8)
            return r
        # watching her from a safe distance after a scare
        if getattr(self, "_watch_until", 0.0) > clock and a.state != "flee" and d < fid * 4.0:
            a.state, a.goal = "watch", a.x
            a.facing = 1.0 if jane.x > a.x else -1.0
            return True
        # wild animals don't wander up to her; curiosity keeps a safe distance
        r = _wd_prev_drive(self, a, fa, world, jane, dt)
        if a.state in ("approach", "sniff", "follow", "play", "beg", "excited") and self.goal in ("jane", "follow", "play", "beg", "greet"):
            if d < fid * 1.1:
                a.state, a.goal = "watch", a.x                      # this close and no closer
                a.facing = 1.0 if jane.x > a.x else -1.0
        return r
    return _wd_prev_drive(self, a, fa, world, jane, dt)


Psyche.drive = _wd_drive

_wd_prev_fauna_update = Fauna.update


def _wd_fauna_update(self, dt, world, jane):
    _wd_prev_fauna_update(self, dt, world, jane)
    # bodies keep their own space: no two animals standing inside each other
    ground = [a for a in self.animals if a.alt < 2 and SPECIES.get(a.sp, {}).get("L")]
    ground.sort(key=lambda a: a.x)
    for i in range(len(ground) - 1):
        a, b = ground[i], ground[i + 1]
        need = 0.45 * (SPECIES[a.sp]["L"] * a.scale + SPECIES[b.sp]["L"] * b.scale) * WS.px
        gap = b.x - a.x
        if gap < need:
            push = (need - gap) * 0.5                       # resolve half the overlap every frame
            a.x -= push if a.state != "sleep" else 0.0
            b.x += push if b.state != "sleep" else 0.0
            if abs(a.goal - b.x) < need:                    # and don't walk straight back in
                a.goal = b.x - need
            if abs(b.goal - a.x) < need:
                b.goal = a.x + need
    offs = getattr(self, "_offerings", None)
    if offs is not None:
        self._offerings[:] = [o for o in offs if o["amount"] > 0 and self.clock - o["t0"] < 900]


Fauna.update = _wd_fauna_update


# ============================================================================
# Jane: patient befriending, from her own state
# ============================================================================

_wd_prev_plan_adjust = _m41_plan_adjust


def _wd_plan_adjust(sv, app, life, cand):
    _wd_prev_plan_adjust(sv, app, life, cand)
    fa = getattr(app, "fauna", None)
    if fa is None or _rw_here(app)[0] == "settlement":
        return
    cr, b = app.creature, app.brain
    g, tr = b.goals, b.personality.traits
    x = getattr(life, "exp", None)
    # touching an animal needs its trust first
    for k in list(cand):
        if k.startswith(("pet:", "offer:")):
            seed = int(k.split(":")[1])
            a = next((o for o in fa.animals if getattr(o, "psy", None) and o.psy.seed == seed), None)
            if a is not None and a.sp in WILD and _wd_trust_fear(a.psy)[0] < (0.35 if a.sp == "dog" else 0.55):
                del cand[k]
    best = None
    for a in fa.animals:
        p = getattr(a, "psy", None)
        if p is None or a.sp not in WILD or a.sp == "wolf" or a.S.get("flyer") or a.state == "flee":
            continue
        d = abs(a.x - cr.x)
        if d > WS.m(35.0):
            continue
        trust, fear = _wd_trust_fear(p)
        if trust >= 0.55:
            continue
        op = life.opinion(p)
        if life.clock - op.get("watched", -1e9) < 90:
            continue
        want = (0.18 + 0.4 * tr.get("curiosity", 0.5) * (0.4 + g.stimulation) + 0.25 * g.social + 0.3 * op["like"])
        if x is not None:
            ev, _d, conf = x.predict("watch", {"who": str(p.seed), "kind": a.sp})
            want += 0.4 * ev * conf                                # what sitting with it has been like
        if best is None or want > best[0]:
            best = (want, a)
    if best is None:
        return
    want, a = best
    fid, _t = wild_fid(a)
    side = 1.0 if cr.x > a.x else -1.0
    spot = clamp(a.x + side * fid * 1.35, 60, app.world.w - 60)
    sv._wd_subject = a.psy.seed
    cand[f"watch:{a.psy.seed}"] = (want, ("watch", spot))
    food = sv.inv.get("berries", 0) + sv.inv.get("meat", 0)
    if food and _wd_trust_fear(a.psy)[0] < 0.4 and a.sp != "wolf":
        drop = clamp(a.x + side * fid * 0.8, 60, app.world.w - 60)
        cand[f"leave:{a.psy.seed}"] = (want * 0.9 + 0.12 * tr.get("friendliness", 0.5), ("leave", drop))


_m41_plan_adjust = _wd_plan_adjust

# these goals are behaviours, not plans: let the chosen one run
_wd_prev_decide = _m42_decide


def _wd_decide(sv, app, life, cand, task):
    if cand:
        top = max(cand, key=lambda k: cand[k][0])
        if top.startswith(("watch:", "leave:", "cmd", "call:")):
            return None
    return _wd_prev_decide(sv, app, life, cand, task)


_m42_decide = _wd_decide


def _wd_subject(app, sv):
    fa = getattr(app, "fauna", None)
    seed = getattr(sv, "_wd_subject", None)
    return next((o for o in (fa.animals if fa else []) if getattr(o, "psy", None) and o.psy.seed == seed), None)


_wd_prev_act = Survival._act


def _wd_act(self, app, dt):
    t = self.task
    if not t or t[0] not in ("watch", "leave"):
        self._wd_t = 0.0
        return _wd_prev_act(self, app, dt)
    cr, b = app.creature, app.brain
    life = _lf_life(app)
    a = _wd_subject(app, self)
    if a is None or a.dead:
        self.task = None
        return
    op = life.opinion(a.psy)
    who = op["name"] or f"the {a.sp}"
    body = getattr(cr, "_body", None)
    if abs(cr.x - t[1]) > WS.m(0.6):
        cr.set_target(t[1], cr.y)
        if isinstance(body, dict):
            body["pace"] = body.get("pace", 1.0) * 0.45            # a slow, unthreatening approach
        self.bias = {"move": 0.4}
        return
    if t[0] == "leave":
        k = "berries" if self.inv.get("berries", 0) else "meat"
        if self.inv.get(k, 0):
            self.inv[k] -= 1
            offs = app.fauna.__dict__.setdefault("_offerings", [])
            offs.append({"x": cr.x, "amount": 2 if k == "berries" else 3, "t0": app.fauna.clock, "kind": k})
            b.perceive(Event("animal", f"left some {k} out for {who} and backed away", salience=0.45, valence=0.25))
        fid, _t = wild_fid(a)
        side = 1.0 if cr.x > a.x else -1.0
        self.task = ("watch", clamp(cr.x + side * fid * 0.9, 60, app.world.w - 60))
        return
    # watching: sit still, face it, and let it get used to her
    cr._loco.facing = 1.0 if a.x > cr.x else -1.0
    self.bias = {"rest": 1.2, "move": -0.9}
    self._wd_t = getattr(self, "_wd_t", 0.0) + dt
    if not hasattr(self, "_wd_trust0"):
        self._wd_trust0 = _wd_trust_fear(a.psy)[0]
    fled = a.state == "flee" or abs(a.x - cr.x) > WS.m(45.0)
    if self._wd_t > 35.0 or fled:
        gained = _wd_trust_fear(a.psy)[0] - self._wd_trust0
        x = getattr(life, "exp", None)
        if x is not None:
            x.update("watch", {"who": str(a.psy.seed), "kind": a.sp}, "fled" if fled else "stayed",
                     -0.3 if fled else 0.3 + gained * 3)
        op["watched"] = life.clock
        op["fam"] = clamp01(op["fam"] + 0.05)
        if not fled:
            op["like"] = clamp01(op["like"] + 0.04)
            b.perceive(Event("animal", f"sat quietly watching {who}" + (" - it is getting used to me" if gained > 0.02 else ""),
                             salience=0.45, valence=0.3))
            b.goals.satisfy("stimulation", 0.15, f"watched {who}")
        else:
            b.perceive(Event("animal", f"{who} slipped away before I could settle", salience=0.35, valence=-0.05))
        del self._wd_trust0
        self._wd_t = 0.0
        self.task = None


Survival._act = _wd_act


# ---- food left out, drawn where it lies ----------------------------------------------------
_wd_prev_update = App._update_world


def _wd_update(self, dt):
    _wd_prev_update(self, dt)
    try:
        fa = getattr(self, "fauna", None)
        cam = getattr(self, "_camera", None)
        pool = getattr(self, "_wd_pool", None)
        if pool is None and cam is not None:
            pool = self._wd_pool = _AtmoPool(self.stage)
        if pool is None:
            return
        pool.begin()
        if fa is not None and _rw_valley(self) or (fa is not None and _rw_here(self)[0] == "road"):
            W = cam.world_to_screen
            G = self.world.ground + 8
            for o in getattr(fa, "_offerings", []) or []:
                for k in range(min(5, o["amount"] * 2)):
                    bx = o["x"] + (k - 2) * WS.m(0.05)
                    by = G - WS.m(0.03) - (k % 2) * WS.m(0.04)
                    (x0, y0), (x1, y1) = W(bx - WS.m(0.03), by - WS.m(0.03)), W(bx + WS.m(0.03), by + WS.m(0.03))
                    pool.put("oval", [x0, y0, x1, y1], "fauna", fill="#b8284a" if o["kind"] == "berries" else "#8a4a3a",
                             outline="")
        pool.end()
    except Exception:
        traceback.print_exc()


App._update_world = _wd_update


# ============================================================================
# Frame stability: a camera at rest stays at rest (Tk redraws only what moves)
# ============================================================================

_wd_prev_frame_target = StageCamera._frame_target


def _wd_frame_target(self, dt):
    tx, ty = _wd_prev_frame_target(self, dt)
    cr = self.follow_target
    try:
        g = cr._terrain_at(cr.x)                               # the ground, not the bobbing body
        w, h = self._wh()
        vh = h / max(self.zoom, 1e-3)
        ty = g - 0.3 * vh
        ew, eh = self.__dict__.get("world_ext") or (w, h)
        if vh < eh:
            ty = clamp(ty, vh * 0.5, eh - vh * 0.5)
    except Exception:
        pass
    tx, ty = round(tx * 2) / 2, round(ty * 2) / 2
    self._wd_tgt = (tx, ty)
    return tx, ty


StageCamera._frame_target = _wd_frame_target
_wd_prev_tick = StageCamera.tick


def _wd_tick(self):
    before = (self.pos[0], self.pos[1])
    _wd_prev_tick(self)
    tg = getattr(self, "_wd_tgt", None)
    if tg is not None and self.follow_enabled:
        for i in (0, 1):
            if abs(self.pos[i] - tg[i]) < 0.4 and abs(self.vel[i]) < 3.0:
                self.pos[i] = tg[i]                             # settle: no sub-pixel creep = no full redraws
                self.vel[i] = 0.0


StageCamera.tick = _wd_tick

# clouds drift at a few Hz, not 60: their motion was forcing full-canvas redraws
_wd_prev_clouds = _bk_clouds


def _wd_clouds(app, dt):
    app._wd_cloud_acc = getattr(app, "_wd_cloud_acc", 0.0) + dt
    if app._wd_cloud_acc < 0.25:
        return
    acc = app._wd_cloud_acc
    app._wd_cloud_acc = 0.0
    _wd_prev_clouds(app, acc)


_bk_clouds = _wd_clouds
