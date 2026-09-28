

# ============================================================================
# [6.4] KNOWLEDGE  --  entities, places, falsifiable hypotheses, plans,
#                       and an explicit model of the self
# ============================================================================
#
# This is the substrate the cognitive loop learns INTO.  Three rules keep it
# honest and stop it degenerating into "counters that look like learning":
#
#   1. Everything stored here came from a real measured observation.  No
#      entry is ever created by a script, a timer or an LLM.
#   2. Every hypothesis carries a NUMERIC prediction and is scored by the
#      absolute error between that prediction and what actually happened.
#      A hypothesis that keeps being wrong is marked refuted - and staying
#      wrong is itself useful knowledge (see SelfModel.limitations).
#   3. Confidence is always a function of how much real evidence exists, so
#      "I don't know" is representable and is what you get by default.

def cue_tokens(brain, extra=()):
    """A handful of coarse tokens describing 'the kind of moment this is'.
    Deliberately a SMALL vocabulary - with a big one every situation is
    unique and nothing can ever generalise."""
    e, g = brain.emotion, brain.goals
    out = {f"time:{day_part()}"}
    w = brain.world_state or {}
    if w.get("weather"):
        out.add(f"weather:{w['weather']}")
    light = float(w.get("light", 1.0) or 1.0)
    out.add("light:dark" if light < 0.4 else ("light:dim" if light < 0.75 else "light:bright"))
    need, val = max((("hunger", g.hunger), ("thirst", g.thirst),
                     ("tired", 1.0 - g.energy), ("lonely", g.social),
                     ("restless", g.stimulation)), key=lambda kv: kv[1])
    if val > 0.45:
        out.add(f"need:{need}")
    out.add(f"feel:{e.emotion}")
    if e.stress > 0.55:
        out.add("state:stressed")
    if e.boredom > 0.6:
        out.add("state:bored")
    if brain.last_interaction and time.time() - brain.last_interaction < 90:
        out.add("social:user_here")
    for token in extra:
        if token:
            out.add(str(token))
    return out


def domain_for_goal(goal_name, goal_kind):
    """Map a live Goal onto one of SelfModel's fixed competence domains, so
    real attempts accumulate into a small, stable set of honest self-
    knowledge instead of one entry per ever-changing goal name."""
    name = (goal_name or "").lower()
    if "food" in name:
        return "finding food"
    if "water" in name:
        return "finding water"
    if "rest" in name or "calm" in name:
        return "calming down" if "calm" in name else "resting"
    if "company" in name or goal_kind == "social":
        return "being with others"
    if "understand" in name or goal_kind == "cognitive":
        return "understanding"
    if goal_kind in ("explore", "discovery", "investigate"):
        return "exploring"
    if goal_kind == "reflect":
        return "understanding"
    return "talking"


class KnownThing:
    """One entity, place or object CREATURE has actually encountered.

    `outcomes` is the affordance table: what measurably happened the times it
    did each action here.  That is what lets it *predict* before acting, and
    what makes "I have no idea what this does" a real, reportable state."""

    __slots__ = ("key", "kind", "name", "desc", "first_seen", "last_seen", "seen",
                 "valence", "outcomes", "props", "notes", "interactions")

    def __init__(self, key, kind, name, desc=""):
        self.key = key
        self.kind = kind                  # place | plant | animal | person | object | weather
        self.name = name
        self.desc = desc
        self.first_seen = time.time()
        self.last_seen = self.first_seen
        self.seen = 0
        self.interactions = 0
        self.valence = 0.0                # running mean of how it felt to be near
        self.outcomes = {}                # action -> (n, mean_dv)
        self.props = {}                   # observed attributes, e.g. {"edible": True}
        self.notes = []                   # short observed statements

    # -- observation ---------------------------------------------------
    def observe(self, valence=0.0, note=""):
        self.seen += 1
        self.last_seen = time.time()
        self.valence += (valence - self.valence) * 0.2
        if note and note not in self.notes:
            self.notes.append(note)
            del self.notes[:-4]

    def record(self, action, dv):
        n, mean = self.outcomes.get(action, (0, 0.0))
        rate = 0.5 if n < 2 else 0.25
        self.outcomes[action] = (n + 1, mean + (dv - mean) * rate)
        self.interactions += 1
        self.last_seen = time.time()

    # -- prediction ----------------------------------------------------
    def expect(self, action):
        n, mean = self.outcomes.get(action, (0, 0.0))
        return mean, clamp01(n / (n + 3.0))

    def confidence(self):
        return clamp01(self.seen / (self.seen + 5.0))

    def uncertainty(self):
        """High for things barely looked at - this is what curiosity chases."""
        return 1.0 - self.confidence()

    def familiar(self):
        return self.seen >= 3

    def summary(self):
        bits = [f"{self.name} ({self.kind})", f"seen {self.seen}x"]
        if self.outcomes:
            best = max(self.outcomes.items(), key=lambda kv: kv[1][1])
            bits.append(f"{best[0]} here -> {best[1][1]:+.2f}")
        if abs(self.valence) > 0.04:
            bits.append("pleasant" if self.valence > 0 else "unpleasant")
        if not self.familiar():
            bits.append("barely known")
        return " · ".join(bits)

    def to_dict(self):
        return {"key": self.key, "kind": self.kind, "name": self.name,
                "desc": self.desc, "first_seen": self.first_seen,
                "last_seen": self.last_seen, "seen": self.seen,
                "interactions": self.interactions,
                "valence": round(self.valence, 4),
                "outcomes": {k: [v[0], round(v[1], 4)] for k, v in self.outcomes.items()},
                "props": self.props, "notes": self.notes[-4:]}

    @staticmethod
    def from_dict(d):
        try:
            t = KnownThing(d["key"], d.get("kind", "object"),
                           d.get("name", "something"), d.get("desc", ""))
            t.first_seen = float(d.get("first_seen", time.time()))
            t.last_seen = float(d.get("last_seen", t.first_seen))
            t.seen = int(d.get("seen", 0))
            t.interactions = int(d.get("interactions", 0))
            t.valence = float(d.get("valence", 0.0))
            for k, v in (d.get("outcomes") or {}).items():
                if isinstance(v, (list, tuple)) and len(v) == 2:
                    t.outcomes[str(k)] = (int(v[0]), float(v[1]))
            props = d.get("props")
            if isinstance(props, dict):
                t.props = dict(props)
            notes = d.get("notes")
            if isinstance(notes, list):
                t.notes = [str(n) for n in notes][-4:]
            return t
        except Exception:
            return None


class Hypothesis:
    """A falsifiable belief of the form  (cue, action) -> expected valence
    change.  Scored ONLY by measured error against what really happened."""

    __slots__ = ("hid", "cue", "action", "predicted", "tests", "support", "refute",
                 "mean_error", "created", "last_test", "status", "domain")

    TOLERANCE = 0.12          # how close a prediction has to be to count as right

    def __init__(self, cue, action, predicted, hid=None, domain=""):
        self.hid = hid or f"h{int(time.time()*1000)%10**8}_{random.randint(10,99)}"
        self.cue = cue
        self.action = action
        self.predicted = float(predicted)
        # [PHASE 52] which domain this belief was learned in, so confidence can
        # transfer along explicit coefficients instead of pooling blindly.
        # Pre-52 records load with "" and simply never act as a transfer source.
        self.domain = str(domain or "")
        self.tests = 0
        self.support = 0
        self.refute = 0
        self.mean_error = 0.0
        self.created = time.time()
        self.last_test = 0.0
        self.status = "open"              # open | supported | refuted

    def matches(self, cues, action):
        return self.cue in cues and (self.action is None or self.action == action)

    def test(self, actual):
        """Returns the prediction error. This is the ONLY way status moves."""
        error = abs(actual - self.predicted)
        self.tests += 1
        self.last_test = time.time()
        self.mean_error += (error - self.mean_error) * (0.5 if self.tests < 3 else 0.2)
        if error <= self.TOLERANCE:
            self.support += 1
            # a supported prediction is also refined toward reality
            self.predicted += (actual - self.predicted) * 0.15
        else:
            self.refute += 1
        if self.tests >= 4:
            ratio = self.support / max(1, self.tests)
            self.status = ("supported" if ratio >= 0.6 else
                           "refuted" if ratio <= 0.3 else "open")
        return error

    def confidence(self):
        if not self.tests:
            return 0.0
        return clamp01((self.support / self.tests) * (self.tests / (self.tests + 3.0)))

    def text(self):
        cue = self.cue.split(":", 1)[-1].replace("_", " ")
        verb = self.action or "just being here"
        if self.predicted > 0.05:
            effect = "tends to help"
        elif self.predicted < -0.05:
            effect = "tends to make things worse"
        else:
            effect = "doesn't seem to change much"
        tail = {"supported": "and that has held up",
                "refuted": "- but that turned out to be wrong",
                "open": "(still testing)"}.get(self.status, "")
        return f"when {cue}, {verb} {effect} {tail}".strip()

    def to_dict(self):
        return {"hid": self.hid, "cue": self.cue, "action": self.action,
                "predicted": round(self.predicted, 4), "tests": self.tests,
                "support": self.support, "refute": self.refute,
                "mean_error": round(self.mean_error, 4), "created": self.created,
                "last_test": self.last_test, "status": self.status,
                "domain": self.domain}

    @staticmethod
    def from_dict(d):
        try:
            h = Hypothesis(d["cue"], d.get("action"), d.get("predicted", 0.0),
                           hid=d.get("hid"), domain=d.get("domain", ""))
            h.tests = int(d.get("tests", 0))
            h.support = int(d.get("support", 0))
            h.refute = int(d.get("refute", 0))
            h.mean_error = float(d.get("mean_error", 0.0))
            h.created = float(d.get("created", time.time()))
            h.last_test = float(d.get("last_test", 0.0))
            h.status = d.get("status", "open")
            return h
        except Exception:
            return None


class KnowledgeBase:
    """Everything learned about the world that is not an episodic memory:
    the entities, their affordances, the hypotheses, and the raw episode
    buffer those hypotheses are mined from."""

    MAX_THINGS = 160
    MAX_HYPOTHESES = 90
    EPISODES = 260

    def __init__(self):
        self.things = {}
        self.hypotheses = []
        self.episodes = deque(maxlen=self.EPISODES)
        self.prediction_error = 0.35        # running mean |error|, drives learning rate
        self.tested = 0
        self.learned = 0                    # hypotheses that reached 'supported'
        self.refuted = 0
        self.last_learned = ""
        self.last_learned_t = 0.0
        self._lock = threading.RLock()

    # -- entities ------------------------------------------------------
    def see(self, kind, name, desc="", valence=0.0, note="", key=None):
        key = key or f"{kind}:{name}"
        with self._lock:
            thing = self.things.get(key)
            if thing is None:
                if len(self.things) >= self.MAX_THINGS:
                    self._prune_things()
                thing = KnownThing(key, kind, name, desc)
                self.things[key] = thing
            thing.observe(valence, note)
            return thing

    def get(self, key):
        return self.things.get(key)

    def _prune_things(self):
        """Forget the least-evidenced, least-recently-seen things first."""
        ranked = sorted(self.things.values(),
                        key=lambda t: (t.seen * 2 + t.interactions * 3, t.last_seen))
        for t in ranked[:max(1, len(ranked) // 8)]:
            self.things.pop(t.key, None)

    def unknowns(self, limit=4):
        """Things worth investigating: encountered, but barely understood."""
        with self._lock:
            cands = [t for t in self.things.values()
                     if t.uncertainty() > 0.45 and
                     t.kind in ("place", "plant", "animal", "object")]
        cands.sort(key=lambda t: (-t.uncertainty(), t.last_seen))
        return cands[:limit]

    def most_known(self, limit=5):
        with self._lock:
            return sorted(self.things.values(),
                          key=lambda t: -(t.seen + 2 * t.interactions))[:limit]

    def favourites(self, limit=3):
        with self._lock:
            out = [t for t in self.things.values() if t.valence > 0.03 and t.seen >= 2]
        out.sort(key=lambda t: -t.valence)
        return out[:limit]

    # -- episodes ------------------------------------------------------
    def add_episode(self, cues, action, dv, label="", domain=""):
        # [PHASE 52] `d` is the domain this happened in - what lets a mined
        # hypothesis know where it was learned. Episodes are not persisted,
        # so older saves need nothing.
        self.episodes.append({"c": tuple(sorted(cues))[:6], "a": action,
                              "dv": round(float(dv), 4), "t": time.time(),
                              "l": (label or "")[:40], "d": (domain or "")[:32]})

    # -- prediction ----------------------------------------------------
    def predict(self, cues, action):
        """Best available prediction for (situation, action) plus confidence.
        Returns (predicted_dv, confidence, hypothesis_or_None).

        NOTE: best_conf starts below zero, not at zero - a freshly-mined,
        still-untested hypothesis legitimately has confidence() == 0.0, and
        that is a real PREDICTION (a numeric guess actively being tested),
        not the same as UNKNOWN (no hypothesis at all). Starting at 0.0
        would make ties with "no match" indistinguishable from a genuine
        open hypothesis, silently collapsing PREDICTION into UNKNOWN."""
        best, best_conf = None, -1.0
        for h in self.hypotheses:
            if h.status == "refuted" or not h.matches(cues, action):
                continue
            conf = h.confidence()
            if conf > best_conf:
                best, best_conf = h, conf
        if best is None:
            return 0.0, 0.0, None
        return best.predicted, best_conf, best

    def test(self, cues, action, actual):
        """Score every matching hypothesis against the measured outcome."""
        errors = []
        for h in list(self.hypotheses):
            if h.status == "refuted" or not h.matches(cues, action):
                continue
            before = h.status
            errors.append(h.test(actual))
            self.tested += 1
            if h.status != before:
                if h.status == "supported":
                    self.learned += 1
                    self.last_learned, self.last_learned_t = h.text(), time.time()
                elif h.status == "refuted":
                    self.refuted += 1
                    self.last_learned = "was wrong about: " + h.text()
                    self.last_learned_t = time.time()
        if errors:
            err = sum(errors) / len(errors)
            self.prediction_error += (err - self.prediction_error) * 0.2
        return errors

    # -- OBSERVATION -> HYPOTHESIS -------------------------------------
    def mine(self, budget=140):
        """Look for a real regularity in the episode buffer and turn it into
        ONE new falsifiable hypothesis.  Budgeted so this can run on the
        brain loop without ever costing a visible frame."""
        if len(self.episodes) < 8:
            return None
        groups, group_domains = {}, {}
        for ep in list(self.episodes)[-budget:]:
            for cue in ep["c"]:
                groups.setdefault((cue, ep["a"]), []).append(ep["dv"])
                if ep.get("d"):
                    dom = group_domains.setdefault((cue, ep["a"]), {})
                    dom[ep["d"]] = dom.get(ep["d"], 0) + 1
        existing = {(h.cue, h.action) for h in self.hypotheses}
        best, best_score = None, 0.0
        for key, vals in groups.items():
            if key in existing or len(vals) < 4:
                continue
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            # a regularity worth believing: a real effect, seen consistently
            score = abs(mean) / (0.05 + math.sqrt(var)) * min(1.0, len(vals) / 6.0)
            if abs(mean) < 0.02 or score <= best_score:
                continue
            best, best_score = (key, mean), score
        if best is None or best_score < 0.8:
            return None
        (cue, action), mean = best
        if len(self.hypotheses) >= self.MAX_HYPOTHESES:
            self.prune()
        doms = group_domains.get((cue, action)) or {}
        domain = max(doms.items(), key=lambda kv: kv[1])[0] if doms else ""
        h = Hypothesis(cue, action, mean, domain=domain)
        self.hypotheses.append(h)
        return h

    def prune(self):
        """Drop stale hypotheses, keeping the ones that earned their place.
        Refuted ones survive a while on purpose: knowing what does NOT work
        is knowledge too."""
        now = time.time()

        def keep_score(h):
            age = (now - max(h.created, h.last_test)) / 3600.0
            base = h.confidence() * 2 + (0.5 if h.status == "refuted" else 0.0)
            return base + min(1.0, h.tests / 6.0) - min(1.5, age / 48.0)

        self.hypotheses.sort(key=keep_score, reverse=True)
        del self.hypotheses[max(10, self.MAX_HYPOTHESES - 10):]

    def beliefs(self, limit=6, include_refuted=True):
        out = [h for h in self.hypotheses
               if h.status == "supported" or (include_refuted and h.status == "refuted")]
        out.sort(key=lambda h: -h.confidence())
        if len(out) < limit:
            open_ = sorted((h for h in self.hypotheses if h.status == "open"),
                           key=lambda h: -h.tests)
            out += open_[: limit - len(out)]
        return out[:limit]

    # -- persistence ---------------------------------------------------
    def to_dict(self):
        with self._lock:
            return {
                "format": "creature_knowledge", "version": 1,
                "things": [t.to_dict() for t in self.things.values()],
                "hypotheses": [h.to_dict() for h in self.hypotheses],
                "prediction_error": round(self.prediction_error, 4),
                "tested": self.tested, "learned": self.learned,
                "refuted": self.refuted, "saved_at": time.time(),
            }

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        for raw in data.get("things", [])[: self.MAX_THINGS]:
            t = KnownThing.from_dict(raw) if isinstance(raw, dict) else None
            if t:
                self.things[t.key] = t
        for raw in data.get("hypotheses", [])[: self.MAX_HYPOTHESES]:
            h = Hypothesis.from_dict(raw) if isinstance(raw, dict) else None
            if h:
                self.hypotheses.append(h)
        self.prediction_error = clamp01(float(data.get("prediction_error", 0.35) or 0.35))
        self.tested = int(data.get("tested", 0) or 0)
        self.learned = int(data.get("learned", 0) or 0)
        self.refuted = int(data.get("refuted", 0) or 0)

    def stats(self):
        open_n = sum(1 for h in self.hypotheses if h.status == "open")
        sup = sum(1 for h in self.hypotheses if h.status == "supported")
        ref = sum(1 for h in self.hypotheses if h.status == "refuted")
        return {"things": len(self.things), "hypotheses": len(self.hypotheses),
                "open": open_n, "supported": sup, "refuted": ref,
                "error": self.prediction_error, "tested": self.tested,
                "episodes": len(self.episodes)}

    # -- EPISTEMIC STATUS: the honest four-way split the whole cognitive ---
    # -- loop is built on. Nothing here is ever set by a script or a timer -
    def classify(self, cues, action):
        """(label, confidence) for a (situation, action) pair, ONE of:
        OBSERVED  - a supported hypothesis with a healthy amount of testing
        INFERENCE - a supported/refuted hypothesis, evidence exists either way
        PREDICTION- an open hypothesis: a real numeric guess, still being tested
        UNKNOWN   - nothing matches at all.
        Looks at ALL matching hypotheses directly (not just predict()'s pick,
        which deliberately ignores refuted ones) - a refuted hypothesis is
        still real, evidenced knowledge, just knowledge of what doesn't work."""
        best = None
        for h in self.hypotheses:
            if not h.matches(cues, action):
                continue
            if best is None or h.confidence() > best.confidence():
                best = h
        if best is None:
            return "UNKNOWN", 0.0
        conf = best.confidence()
        if best.status in ("supported", "refuted"):
            return ("OBSERVED" if best.tests >= 8 else "INFERENCE"), conf
        return "PREDICTION", conf

    # -- persistence (disk round-trip; separate file, like memory/friends) -
    def load(self):
        self.from_dict(load_json(KNOWLEDGE_FILE, {}))

    def save(self):
        return save_json(KNOWLEDGE_FILE, self.to_dict())


class SelfModel:
    """What CREATURE believes about ITSELF: what it can do, what it keeps
    failing at, what it is currently trying to do, and - importantly - what
    it does not know.  Every number here derives from a recorded attempt."""

    DOMAINS = ("finding food", "finding water", "resting", "exploring",
               "calming down", "being with others", "talking", "understanding")

    def __init__(self):
        self.capabilities = {}        # action -> (tries, successes, mean_dv)
        self.domains = {}             # domain -> (tries, successes)
        self.limitations = {}         # text -> evidence count
        self.strategies = {}          # "cue|action" -> (uses, wins)
        self.mistakes = deque(maxlen=14)
        self.intention = ""
        self.intention_why = ""
        self.last_surprise = ""
        self.identity_notes = []

    # -- recording -----------------------------------------------------
    def record(self, action, dv, domain=""):
        tries, wins, mean = self.capabilities.get(action, (0, 0, 0.0))
        mean += (dv - mean) * (0.5 if tries < 2 else 0.2)
        self.capabilities[action] = (tries + 1, wins + (1 if dv > 0.01 else 0), mean)
        if domain:
            d_tries, d_wins = self.domains.get(domain, (0, 0))
            self.domains[domain] = (d_tries + 1, d_wins + (1 if dv > 0.01 else 0))

    def record_strategy(self, cue, action, ok):
        key = f"{cue}|{action}"
        uses, wins = self.strategies.get(key, (0, 0))
        self.strategies[key] = (uses + 1, wins + (1 if ok else 0))
        if len(self.strategies) > 120:
            for k, _ in sorted(self.strategies.items(), key=lambda kv: kv[1][0])[:20]:
                self.strategies.pop(k, None)

    def note_limitation(self, text):
        self.limitations[text] = self.limitations.get(text, 0) + 1
        if len(self.limitations) > 24:
            weakest = min(self.limitations.items(), key=lambda kv: kv[1])[0]
            self.limitations.pop(weakest, None)

    def note_mistake(self, what, why=""):
        self.mistakes.append((time.time(), str(what)[:90], str(why)[:90]))

    def set_intention(self, what, why=""):
        self.intention, self.intention_why = what or "", why or ""

    # -- read-out ------------------------------------------------------
    # ------------------------------------------- [PHASE 52] transfer -----
    # Confidence earned in one domain may inform a RELATED one, along
    # explicit coefficients, never by pooling. Three hard rules:
    #
    #   1. DIRECTION IS DECLARED, NOT SYMMETRIC. The table below is read
    #      target -> {source: coeff}. "making art" borrows from exploring
    #      and understanding; there is deliberately no entry anywhere with
    #      "making art" as a SOURCE, because being good at making things
    #      is not evidence of being good at finding food.
    #   2. THE SOURCE MUST HAVE REAL EVIDENCE. Below MIN_SOURCE_CONF a
    #      source contributes nothing at all - a guess cannot be laundered
    #      into a prior by travelling between domains.
    #   3. BORROWED WEIGHT IS CAPPED AND ONLY FILLS THE GAP. Total weight
    #      can never exceed MAX_TRANSFER, and is scaled by how little the
    #      target knows about itself, so first-hand evidence always wins
    #      and transfer decays to nothing as the domain learns. Same
    #      philosophy as MAX_NUDGE: bounded per call, bounded overall.
    MAX_TRANSFER = 0.20       # hard ceiling on borrowed weight - never raised
    MIN_SOURCE_CONF = 0.35    # a source this thin is not evidence
    MIN_SOURCE_TESTS = 3      # ...and neither is a barely-tested hypothesis
    TRANSFER_COEFF = {
        "making art":    {"exploring": 0.18, "understanding": 0.12},
        "understanding": {"talking": 0.10},
        "posting":       {"talking": 0.10, "being with others": 0.08},
    }

    def transfer_prior(self, target_domain, knowledge=None):
        """-> (prior_ratio, weight) borrowed from genuinely related domains.

        weight is 0.0 when nothing qualifies, and never exceeds
        MAX_TRANSFER. `knowledge` is optional: when given, domain-tagged
        hypotheses that have actually held up act as a second source of
        evidence alongside domain competence."""
        coeffs = self.TRANSFER_COEFF.get(target_domain) or {}
        if not coeffs:
            return 0.5, 0.0
        hyp = {}
        if knowledge is not None:
            for h in getattr(knowledge, "hypotheses", []) or []:
                dom = getattr(h, "domain", "")
                if (not dom or dom not in coeffs or h.status != "supported"
                        or h.tests < self.MIN_SOURCE_TESTS):
                    continue
                acc, n, tests = hyp.get(dom, (0.0, 0, 0))
                hyp[dom] = (acc + h.confidence(), n + 1, tests + h.tests)
        num = den = 0.0
        for source, coeff in coeffs.items():
            ratio, conf = self.competence(source)
            evidence = [(ratio, conf)]
            h_acc, h_n, h_tests = hyp.get(source, (0.0, 0, 0))
            if h_n:
                # confidence of the source beliefs, weighted by how much
                # testing stands behind them - same tries/(tries+4) shape
                # competence() already uses, so the two sources are
                # measured on comparable terms
                evidence.append((clamp01(h_acc / h_n),
                                 clamp01(h_tests / (h_tests + 4.0))))
            for e_ratio, e_conf in evidence:
                if e_conf < self.MIN_SOURCE_CONF:
                    continue
                w = coeff * e_conf
                num += e_ratio * w
                den += w
        if den <= 0.0:
            return 0.5, 0.0
        return clamp01(num / den), clamp(den, 0.0, self.MAX_TRANSFER)

    def competence_with_transfer(self, domain, knowledge=None):
        """-> (ratio, confidence, borrowed_weight). Identical to
        competence() whenever nothing qualifies to transfer, and collapses
        back to it as the domain accumulates its own evidence."""
        ratio, conf = self.competence(domain)
        p_ratio, p_w = self.transfer_prior(domain, knowledge)
        if p_w <= 0.0:
            return ratio, conf, 0.0
        w = clamp(p_w * (1.0 - conf), 0.0, self.MAX_TRANSFER)
        return (clamp01(ratio * (1.0 - w) + p_ratio * w),
                clamp01(conf + w * 0.5), round(w, 3))

    def can(self, action):
        tries, wins, _mean = self.capabilities.get(action, (0, 0, 0.0))
        if not tries:
            return 0.5, 0.0
        return wins / tries, clamp01(tries / (tries + 4.0))

    def competence(self, domain):
        tries, wins = self.domains.get(domain, (0, 0))
        if not tries:
            return 0.5, 0.0
        return wins / tries, clamp01(tries / (tries + 4.0))

    def best_strategies(self, limit=4):
        out = []
        for key, (uses, wins) in self.strategies.items():
            if uses >= 3 and wins / uses >= 0.6:
                out.append((wins / uses, uses, key))
        out.sort(reverse=True)
        return [(k, r, u) for r, u, k in out[:limit]]

    def failed_strategies(self, limit=3):
        out = []
        for key, (uses, wins) in self.strategies.items():
            if uses >= 3 and wins / uses <= 0.25:
                out.append((uses - wins, uses, key))
        out.sort(reverse=True)
        return [(k, u) for _f, u, k in out[:limit]]

    def strong_domains(self, limit=2):
        out = [(self.competence(d)[0], d) for d in self.domains
               if self.competence(d)[1] > 0.35]
        out.sort(reverse=True)
        return [d for r, d in out[:limit] if r > 0.55]

    def weak_domains(self, limit=2):
        out = [(self.competence(d)[0], d) for d in self.domains
               if self.competence(d)[1] > 0.35]
        out.sort()
        return [d for r, d in out[:limit] if r < 0.45]

    def overall_confidence(self):
        vals = [self.competence(d) for d in self.domains]
        conf = [c for _r, c in vals]
        if not conf or not sum(conf):
            return 0.5, 0.0
        weighted = sum(r * c for r, c in vals)
        return weighted / max(1e-6, sum(conf)), clamp01(sum(conf) / len(conf))

    def knows_about(self, topic, knowledge: "KnowledgeBase"):
        """Explicit ignorance check: can I say anything evidenced about this?"""
        topic = (topic or "").lower().strip()
        if not topic:
            return False, 0.0
        best = 0.0
        for thing in knowledge.things.values():
            low = thing.name.lower()
            if topic in low or low in topic:
                best = max(best, thing.confidence())
        return best > 0.3, best

    def prompt_block(self, knowledge: "KnowledgeBase"):
        """Compact, plain-language self-knowledge for the LLM.  It is allowed -
        encouraged - to say it does not know something."""
        lines = []
        conf, conf_conf = self.overall_confidence()
        if conf_conf > 0.2:
            attempts = sum(t for t, _w in self.domains.values())
            lines.append(f"how capable you feel overall: {conf:.0%} "
                         f"(from {attempts} real attempts)")
        good, bad = self.strong_domains(2), self.weak_domains(2)
        if good:
            lines.append("you are reliably good at: " + ", ".join(good))
        if bad:
            lines.append("you keep struggling with: " + ", ".join(bad))
        lims = sorted(self.limitations.items(), key=lambda kv: -kv[1])[:3]
        if lims:
            lines.append("things you have learned you cannot do: " +
                         "; ".join(t for t, _ in lims))
        strat = self.best_strategies(2)
        if strat:
            lines.append("strategies that have worked: " +
                         "; ".join(k.replace("|", " -> ").replace(":", " ")
                                   for k, _r, _u in strat))
        if self.mistakes:
            t, what, why = self.mistakes[-1]
            lines.append(f"most recent mistake ({ago(t)}): {what}" +
                         (f" - {why}" if why else ""))
        if self.intention:
            lines.append(f"what you are trying to do right now: {self.intention}"
                         + (f" ({self.intention_why})" if self.intention_why else ""))
        beliefs = knowledge.beliefs(3)
        if beliefs:
            lines.append("things you have worked out for yourself: " +
                         "; ".join(h.text() for h in beliefs))
        unknown = knowledge.unknowns(2)
        if unknown:
            lines.append("things you have noticed but do not understand yet: " +
                         ", ".join(t.name for t in unknown))
        if knowledge.prediction_error > 0.3:
            lines.append("the world has been surprising you lately - be less sure of"
                         " yourself than usual, and say so if it comes up.")
        return "\n".join(lines)

    # -- persistence ---------------------------------------------------
    def to_dict(self):
        return {
            "capabilities": {k: [v[0], v[1], round(v[2], 4)]
                             for k, v in self.capabilities.items()},
            "domains": {k: list(v) for k, v in self.domains.items()},
            "limitations": dict(list(self.limitations.items())[:20]),
            "strategies": {k: list(v) for k, v in self.strategies.items()},
            "mistakes": [list(m) for m in self.mistakes],
            "intention": self.intention, "intention_why": self.intention_why,
            "identity_notes": self.identity_notes[:10],
        }

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        for k, v in (data.get("capabilities") or {}).items():
            if isinstance(v, (list, tuple)) and len(v) == 3:
                self.capabilities[str(k)] = (int(v[0]), int(v[1]), float(v[2]))
        for k, v in (data.get("domains") or {}).items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                self.domains[str(k)] = (int(v[0]), int(v[1]))
        lims = data.get("limitations")
        if isinstance(lims, dict):
            for k, v in lims.items():
                try:
                    self.limitations[str(k)] = int(v)
                except Exception:
                    pass
        for k, v in (data.get("strategies") or {}).items():
            if isinstance(v, (list, tuple)) and len(v) == 2:
                self.strategies[str(k)] = (int(v[0]), int(v[1]))
        for row in data.get("mistakes", []) or []:
            if isinstance(row, (list, tuple)) and len(row) == 3:
                self.mistakes.append(tuple(row))
        self.intention = str(data.get("intention", "") or "")
        self.intention_why = str(data.get("intention_why", "") or "")
        notes = data.get("identity_notes")
        if isinstance(notes, list):
            self.identity_notes = [str(n) for n in notes][:10]


class PlanStep:
    """One concrete, checkable intention.  `predicted` is what CREATURE
    expects this step to do to its own valence - so a step can be scored
    honestly rather than merely marked 'completed'."""

    __slots__ = ("kind", "target", "why", "predicted", "status", "attempts",
                 "started", "deadline")

    def __init__(self, kind, target=None, why="", predicted=0.0, timeout=45.0):
        self.kind = kind                # goto | observe | interact | rest | wait | retreat
        self.target = target            # a KnownThing key, or None
        self.why = why
        self.predicted = predicted
        self.status = "pending"         # pending | active | done | failed
        self.attempts = 0
        self.started = 0.0
        self.deadline = timeout

    def describe(self, things=None):
        name = self.target or ""
        if things and self.target in things:
            name = things[self.target].name
        elif ":" in name:
            name = name.split(":", 1)[1]
        verb = {"goto": "go to", "observe": "watch", "interact": "try",
                "rest": "rest", "wait": "wait", "retreat": "back off"}.get(
                    self.kind, self.kind)
        return f"{verb} {name}".strip()

    def to_dict(self):
        return {"kind": self.kind, "target": self.target, "why": self.why,
                "predicted": round(self.predicted, 4), "status": self.status,
                "attempts": self.attempts, "deadline": self.deadline}

    @staticmethod
    def from_dict(d):
        try:
            s = PlanStep(d.get("kind", "wait"), d.get("target"), d.get("why", ""),
                         float(d.get("predicted", 0.0)),
                         float(d.get("deadline", 45.0)))
            s.status = d.get("status", "pending")
            s.attempts = int(d.get("attempts", 0))
            return s
        except Exception:
            return None


class Plan:
    """A short sequence of steps toward one goal, with a real abandon path: a
    plan that keeps failing gets given up on and recorded as a failed
    strategy, which is how the self model learns its own limits."""

    MAX_FAILS = 2

    def __init__(self, goal, steps, why="", cues=()):
        self.goal = goal
        self.steps = [s for s in steps if s]
        self.index = 0
        self.why = why
        self.cues = tuple(cues)[:4]
        self.created = time.time()
        self.status = "active"          # active | done | abandoned
        self.fails = 0
        self.abandon_reason = ""
        self.start_valence = 0.0
        self.score = 0.0                # measured valence change while running

    def current(self):
        if self.status != "active" or self.index >= len(self.steps):
            return None
        step = self.steps[self.index]
        if step.status == "pending":
            step.status = "active"
            step.started = time.time()
        return step

    def advance(self, ok=True, reason=""):
        if self.index < len(self.steps):
            self.steps[self.index].status = "done" if ok else "failed"
        if not ok:
            self.fails += 1
        self.index += 1
        if self.fails >= self.MAX_FAILS:
            self.abandon(reason or "it kept not working")
        elif self.index >= len(self.steps):
            self.status = "done"

    def abandon(self, reason):
        self.status = "abandoned"
        self.abandon_reason = reason

    def expired(self):
        step = self.steps[self.index] if self.index < len(self.steps) else None
        return bool(step and step.started and
                    time.time() - step.started > step.deadline)

    def progress(self):
        return self.index / max(1, len(self.steps))

    def describe(self, things=None):
        rest = self.steps[self.index:][:3]
        return " → ".join(s.describe(things) for s in rest) or self.goal

    def to_dict(self):
        return {"goal": self.goal, "why": self.why, "index": self.index,
                "status": self.status, "fails": self.fails,
                "cues": list(self.cues), "created": self.created,
                "steps": [s.to_dict() for s in self.steps]}

    @staticmethod
    def from_dict(d):
        try:
            steps = [PlanStep.from_dict(s) for s in d.get("steps", [])]
            steps = [s for s in steps if s]
            if not steps:
                return None
            p = Plan(d.get("goal", "carry on"), steps, d.get("why", ""),
                     d.get("cues", ()))
            p.index = min(int(d.get("index", 0)), len(steps))
            p.status = d.get("status", "active")
            p.fails = int(d.get("fails", 0))
            p.created = float(d.get("created", time.time()))
            return p
        except Exception:
            return None
