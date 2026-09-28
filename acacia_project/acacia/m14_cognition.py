

# ============================================================================
# [6.5] COGNITION  --  world model / self model / prediction / planning /
#                       concepts / experimentation / dreaming / meta-learning
# ============================================================================
#
#   ... EMOTION -> WORLD MODEL -> SELF MODEL -> PREDICTION -> REASONING ->
#   PLANNING -> ACTION -> WORLD CONSEQUENCE -> ERROR -> LEARNING ->
#   CONSOLIDATION -> ...
#
# This closes the loop that the rest of the file leaves open: Brain.tick()
# already turns state into a chosen behaviour every frame, but nothing
# remembered whether that behaviour actually *worked*, predicted what would
# happen before doing it, or went back over experience later. Cognition adds
# exactly that, on top of real observed (situation, action) -> outcome pairs.
# No scripted insights, no LLM calls in here - the LLM only ever narrates a
# thought Cognition already produced.

class Cognition:
    def __init__(self, brain):
        self.brain = brain
        # WORLD MODEL: (goal-kind, behaviour) -> [n seen, running mean valence delta]
        self.world = {}
        # SELF MODEL: behaviour -> [n tried, n that improved valence] - calibrates
        # how much CREATURE should trust its own motor impulses per situation
        self.self_model = {}
        # CONCEPTS: recurring co-occurring keyword clusters -> stats
        self.concepts = {}
        self.last_state = None            # snapshot taken in before_action()
        self.last_prediction = (0.0, 0.0)
        self.uncertainty = 0.5
        self.meta_lr = 0.06               # meta-learned world-model update rate
        self.experiments = deque(maxlen=20)
        self.plan = []                    # short lookahead over current goals
        self._dream_accum = 0.0   # how long it has been resting, not a schedule
        self._mine_accum = 0
        self.fail_streak = {}             # key -> consecutive bad outcomes
        self._xref_cache = None           # [PHASE 51] derived, never persisted

    def _key(self, behavior):
        g = self.brain.goals.focus
        return (g.kind if g else "idle", behavior)

    # -- PREDICTION: expected payoff of a behaviour, with honest confidence -
    def predict(self, behavior):
        self.brain.mark("world_model", 0.5)
        key = self._key(behavior)
        n, mean_dv = self.world.get(key, (0, 0.0))
        conf = clamp01(n / (n + 4.0))     # confidence rises with real experience
        if self.fail_streak.get(key, 0) >= 3:
            # ADAPTIVE STRATEGY: a repeatedly-failing approach stops looking
            # attractive even if it once worked, until it's tried again fresh
            mean_dv -= 0.15
        return mean_dv, conf

    # -- PLANNING: greedy multi-step lookahead over the top goals -----------
    def plan_steps(self):
        self.brain.mark("planning", 0.8)
        seq = []
        for g in self.brain.goals.goals[:3]:
            best_b, best_score = MOTOR_NAMES[0], -9.0
            for b in MOTOR_NAMES:
                dv, conf = self.predict(b)
                # known-good options win; unknown ones keep a small curiosity
                # bonus so the plan doesn't just repeat whatever worked once
                score = dv * conf + 0.15 * (1.0 - conf)
                if score > best_score:
                    best_b, best_score = b, score
            seq.append((g.name, best_b))
        self.plan = seq
        return seq

    # -- REASONING + ACTION: pick a behaviour, occasionally testing a ------
    # -- hypothesis instead of trusting the motor net blindly (EXPERIMENT) --
    def choose_action(self, motor_pref):
        dv, conf = self.predict(motor_pref)
        self.uncertainty = clamp01(1.0 - conf)
        if conf < 0.3 and random.random() < 0.35:
            trial = random.choice(MOTOR_NAMES)
            self.experiments.append((time.time(), self._key(trial)))
            return trial, True
        return motor_pref, False

    def before_action(self, behavior):
        """Snapshot the world right before a behaviour is committed to, so
        the *actual* consequence can be measured honestly next tick.

        Also takes the CUE-BASED prediction from the KnowledgeBase - a
        richer situational fingerprint (time/weather/light/need/mood) than
        the coarse (goal-kind, behaviour) key alone - so the same behaviour
        in a different real situation isn't judged by one pooled average."""
        g = self.brain.goals.focus
        cues = cue_tokens(self.brain)
        self.last_state = {
            "valence": self.brain.emotion.valence,
            "behavior": behavior,
            "key": self._key(behavior),
            "cues": cues,
            "goal_name": g.name if g else "stay present",
            "goal_kind": g.kind if g else "idle",
        }
        self.last_prediction = self.predict(behavior)

    # -- WORLD CONSEQUENCE + ERROR + LEARNING -------------------------------
    def after_action(self):
        self.brain.mark("self_model", 0.7)
        st = self.last_state
        if not st:
            return
        dv = self.brain.emotion.valence - st["valence"]
        pred_dv, _ = self.last_prediction
        error = abs(dv - pred_dv)

        # meta-learning: the world model itself learns faster when it has
        # been consistently wrong, and settles down once it's reliable
        self.meta_lr = clamp(self.meta_lr + (0.01 if error > 0.25 else -0.002), 0.02, 0.25)

        n, mean_dv = self.world.get(st["key"], (0, 0.0))
        mean_dv += (dv - mean_dv) * self.meta_lr
        self.world[st["key"]] = (n + 1, mean_dv)

        # fail/replan: repeated bad outcomes from the same (goal, behavior)
        # pairing erode trust in it (see predict()) until it works again
        if dv < -0.02:
            self.fail_streak[st["key"]] = self.fail_streak.get(st["key"], 0) + 1
        else:
            self.fail_streak[st["key"]] = 0

        sn, ss = self.self_model.get(st["behavior"], (0, 0))
        self.self_model[st["behavior"]] = (sn + 1, ss + (1 if dv > 0 else 0))

        # a real surprise (not a scripted one) has honest emotional weight
        if error > 0.30:
            self.brain.emotion.nudge("curiosity", 0.05, "that didn't go how I expected")
        elif dv > pred_dv + 0.15:
            self.brain.emotion.nudge("confidence", 0.02)
        elif dv < pred_dv - 0.15:
            self.brain.emotion.nudge("confidence", -0.02)

        # WORLD INTELLIGENCE (KnowledgeBase) + SELF MODEL: the same measured
        # (situation, action) -> outcome is fed into the richer cue-based
        # knowledge base (OBSERVED FACT -> HYPOTHESIS -> PREDICTION ->
        # EXPERIMENT -> RESULT -> ERROR -> KNOWLEDGE UPDATE) and into the
        # explicit self-model (capability/domain confidence), not just the
        # coarse goal-kind table above.
        cues = st.get("cues") or set()
        kb = self.brain.knowledge
        domain = domain_for_goal(st.get("goal_name"), st.get("goal_kind"))
        kb.add_episode(cues, st["behavior"], dv, domain=domain)
        kb_errors = kb.test(cues, st["behavior"], dv)
        self._mine_accum = getattr(self, "_mine_accum", 0) + 1
        if self._mine_accum >= 10:
            self._mine_accum = 0
            kb.mine()

        self.brain.self_model.record(st["behavior"], dv, domain=domain)
        if dv < -0.12:
            self.brain.self_model.note_mistake(f"{st['behavior']} while {st.get('goal_name')}",
                                               f"made things worse ({dv:+.2f})")

        # GOAL LIFECYCLE: if the current focus is a self-proposed (dynamic)
        # goal rather than a metabolic need, its measured payoff moves it
        # toward SUCCEEDED or FAILED.
        if st.get("goal_kind") in ("discovery", "investigate"):
            resolved = self.brain.goals.record_progress(st["goal_name"], dv)
            if resolved in ("succeeded", "failed"):
                self.brain.reasoning_trace.append({
                    "t": time.time(), "kind": "goal_lifecycle",
                    "text": f"goal '{st['goal_name']}' {resolved}",
                    "cause": "measured outcome",
                })

        # METACOGNITION: RESULT -> ERROR -> STRATEGY EVALUATION -> MODEL
        # UPDATE, logged with real numbers only - this is the second half of
        # the trace opened in Brain.tick() before the action was taken.
        if error > 0.25 or kb_errors:
            label, conf = kb.classify(cues, st["behavior"])
            self.brain.reasoning_trace.append({
                "t": time.time(), "kind": "metacognition",
                "text": f"result {dv:+.2f} vs predicted {pred_dv:+.2f} "
                        f"(error {error:.2f}) - now {label.lower()} "
                        f"(confidence {conf:.0%}) about {st['behavior']} here",
                "cause": "model update",
            })
        self.last_state = None

    # -- CONCEPT FORMATION: recurring co-occurring keywords become a -------
    # -- named generalisation, not just another line in the event log -------
    def form_concept(self, kws, valence):
        kws = [w for w in kws if len(w) > 2][:3]
        if len(kws) < 2:
            return
        label = "+".join(sorted(kws))
        c = self.concepts.setdefault(label, {"n": 0, "valence": 0.0})
        c["n"] += 1
        c["valence"] += (valence - c["valence"]) * 0.25
        if c["n"] == 3:      # a real pattern, not a one-off - worth keeping
            self.brain.memory.remember(
                "concept", f"these tend to go together: {', '.join(sorted(kws))}",
                importance=0.4, emotion=self.brain.emotion.emotion, valence=c["valence"])

    # ------------------------------------------ [PHASE 51] one concept graph
    # Conversational concept mining (above) and Phase 22 motif mining (in
    # VisualMemory) have been two separate educations since Phase 11.  They
    # are now ONE graph with one node schema, typed by where the node was
    # learned: `verbal` nodes are the persisted concepts above, `motif` nodes
    # are a READ-TIME PROJECTION of VisualMemory's own pair tallies.
    #
    # The projection is deliberate and is the whole reason this phase adds no
    # state: the pair rows keep their single owner in visual_memory.json, so
    # nothing is copied, nothing new is persisted, no migration is needed, and
    # a motif node can never drift out of sync with the affinity row behind
    # it.  Old saves load unchanged - the label already carries the terms.

    MIN_XREF_TERM = 4        # shorter overlaps are coincidence, not meaning

    @staticmethod
    def _concept_node(label, n, valence, kind, terms):
        """The shared node schema both mining paths now produce."""
        return {"label": label, "kind": kind, "n": int(n or 0),
                "valence": float(valence or 0.0),
                "terms": sorted(t for t in terms if t)}

    def _verbal_nodes(self):
        out = {}
        for label, row in list(self.concepts.items()):
            if not isinstance(row, dict):
                continue
            out[label] = self._concept_node(
                label, row.get("n", 0), row.get("valence", 0.0), "verbal",
                [t for t in str(label).split("+") if t])
        return out

    @staticmethod
    def _fx_terms(name):
        """An effect name reduced to the same vocabulary conversation uses:
        stemmed words plus the families it belongs to, so 'Neon Grid' can
        honestly meet a conversation about grids or about neon."""
        low = (name or "").lower()
        terms = {stem(w) for w in re.findall(r"[a-z]{4,}", low)}
        for fam, kws in (globals().get("FX_FAMILY_KEYWORDS") or {}).items():
            if any(k in low for k in kws):
                terms.add(fam)
                if fam == "colour":
                    terms.add("color")      # same idea, other spelling
        return terms

    def _motif_nodes(self, limit=12, min_uses=3):
        host = acacia_host()
        vm = getattr(host, "visual_memory", None)
        if vm is None or not hasattr(vm, "motifs"):
            return {}                        # mind running without the studio
        try:
            # the studio thread can be reinforcing pairs while this reads
            # them; a torn read is not worth a lock, it just means no motif
            # nodes this pass
            rows = vm.motifs(min_uses=min_uses, limit=limit)
        except Exception:
            return {}
        out = {}
        for a, b, score, uses in rows:
            label = f"motif:{a}+{b}"
            out[label] = self._concept_node(
                label, uses, score, "motif", self._fx_terms(a) | self._fx_terms(b))
        return out

    def concept_graph(self, motif_limit=12, min_uses=3):
        """-> {label: node} across BOTH mining paths, one schema, typed."""
        g = self._verbal_nodes()
        g.update(self._motif_nodes(motif_limit, min_uses))
        return g

    def cross_references(self, min_n=3, min_uses=3, limit=4):
        """-> [(verbal_node, motif_node, shared_terms, strength)], strongest
        first.

        Gated on real evidence on BOTH sides and on genuinely shared terms:
        the point is to FIND the connections that already exist between what
        gets talked about and what actually works visually, never to invent
        one between domains that are honestly unrelated."""
        now = time.time()
        cached = self._xref_cache
        if cached and now - cached[0] < 20.0:
            return cached[1][:limit]
        motifs = self._motif_nodes(12, min_uses)
        out = []
        if motifs:
            for vnode in self._verbal_nodes().values():
                if vnode["n"] < min_n:       # same "real pattern" floor
                    continue                 # form_concept() already uses
                vterms = {t for t in vnode["terms"] if len(t) >= self.MIN_XREF_TERM}
                if not vterms:
                    continue
                for mnode in motifs.values():
                    shared = sorted(vterms & {t for t in mnode["terms"]
                                              if len(t) >= self.MIN_XREF_TERM})
                    if not shared:
                        continue
                    # evidence DOMINATES and term overlap only modifies it:
                    # two words matching at the bare minimum of evidence is a
                    # coincidence, and must not outrank a single word that
                    # both sides have earned many times over
                    ev = clamp((min(vnode["n"], mnode["n"]) - 2) / 8.0, 0.0, 1.0)
                    strength = clamp(ev * min(1.0, 0.6 + 0.2 * len(shared)), 0.0, 1.0)
                    out.append((vnode, mnode, shared, round(strength, 2)))
        out.sort(key=lambda r: -r[3])
        self._xref_cache = (now, out)
        return out[:limit]

    # -- DREAMING / CONSOLIDATION: only during genuine rest, never on demand
    def tick(self, dt):
        # [PHASE 59] WHETHER to dream is still this subsystem's own call
        # (genuine rest, energy to spare); WHEN it may is the arbiter's.
        # The accumulator that used to be this subsystem's private timer is
        # gone - Attention.request owns the gap now.
        att = getattr(self.brain, "attention", None)
        resting = (self.brain.decisions.behavior == "rest"
                   and self.brain.goals.energy > 0.3)
        if resting:
            self._dream_accum += dt
        else:
            self._dream_accum = 0.0
        if resting and self._dream_accum > 5.0 and (
                att is None or att.request("dream", importance=0.55)):
            self._dream_accum = 0.0
            self._dream()
        if att is None or att.request("plan", importance=0.4):
            self.plan_steps()

    def _dream(self):
        mem = self.brain.memory
        items = sorted(mem.long_term, key=lambda m: m.strength(), reverse=True)[:12]
        if len(items) < 4:
            return
        seen = {}
        for it in items:
            words = frozenset(keywords(it.text, 3))
            merged = False
            for label, other in seen.items():
                if len(words & label) >= 2:
                    other.importance = clamp01(other.importance + 0.05)
                    mem.forget(it.id)
                    merged = True
                    break
            if not merged:
                seen[words] = it
        mem.decay()
        best = max(self.world.items(), key=lambda kv: kv[1][0], default=None)
        if best and best[1][0] >= 3:
            (goal_kind, behavior), (n, mean_dv) = best
            verb = "helps" if mean_dv > 0.05 else "doesn't help" if mean_dv < -0.05 else "doesn't seem to matter much"
            self.brain.reasoning_trace.append({
                "t": time.time(), "kind": "dream",
                "text": f"noticing: {behavior} {verb} when the focus is {goal_kind}",
                "cause": "dreaming",
            })
            # CONSOLIDATION -> NEW GOALS: a strong, well-evidenced discovery
            # becomes something CREATURE decides to pursue on its own, not
            # just a fact sitting in the world model
            if mean_dv > 0.18 and n >= 4:
                self.brain.goals.propose(
                    f"do more {behavior}", 0.3 + 0.2 * clamp01(n / 10),
                    f"discovered {behavior} reliably helps when {goal_kind}",
                    kind="discovery")

        # REFLECTION / CONSOLIDATION over the richer knowledge base + self
        # model: durable, well-evidenced patterns get written to long-term
        # memory; genuinely unresolved questions become goals to chase.
        kb = self.brain.knowledge
        sm = self.brain.self_model
        strong = sm.best_strategies(1)
        if strong:
            key, ratio, uses = strong[0]
            mem.remember("insight",
                        f"strategy that keeps working: {key.replace('|', ' -> ')}"
                        f" ({ratio:.0%} of {uses} tries)",
                        importance=0.5, valence=0.3)
        weak = sm.failed_strategies(1)
        if weak:
            key, uses = weak[0]
            sm.note_limitation(f"{key.replace('|', ' -> ')} keeps not working")
        # [PHASE 51] the one place the two educations meet: a term carrying
        # weight in conversation AND in a pair that keeps paying off visually
        # is a connection that already exists, so it becomes something to
        # pursue rather than a coincidence nobody ever notices.
        for vnode, mnode, shared, strength in self.cross_references(limit=1):
            if strength < 0.55:
                break
            if abs(mnode["valence"]) < 0.15:
                break            # the pairing has not actually landed either way
            term = shared[0]
            verdict = ("what works visually" if mnode["valence"] > 0
                       else "a pairing that keeps not working")
            mem.remember(
                "concept",
                f"'{term}' keeps coming up both when we talk and in "
                f"{verdict} ({mnode['label'][6:]})",
                importance=clamp01(0.35 + 0.25 * strength),
                valence=0.5 * (vnode["valence"] + mnode["valence"]))
            self.brain.goals.propose(
                f"follow the {term} thread",
                0.2 + 0.2 * strength,
                f"'{term}' is landing in conversation and in the work at once",
                kind="discovery")

        unresolved = kb.unknowns(1)
        if unresolved:
            thing = unresolved[0]
            self.brain.goals.propose(
                f"investigate the {thing.name}",
                0.25 + 0.3 * thing.uncertainty(),
                f"still don't understand the {thing.name} ({thing.seen}x seen)",
                kind="investigate")

    def snapshot(self):
        return {
            "uncertainty": round(self.uncertainty, 2),
            "meta_lr": round(self.meta_lr, 3),
            "known_situations": len(self.world),
            "concepts": len(self.concepts),
            "cross_links": len(self.cross_references(limit=8)),   # [PHASE 51]
            "experiments": len(self.experiments),
            "plan": self.plan[:3],
        }

    # -- persistence: what's been learned must survive a restart, or none --
    # -- of this is actually learning, just a session-long illusion of it --
    def to_dict(self):
        return {
            "world": {f"{k[0]}|{k[1]}": v for k, v in self.world.items()},
            "self_model": dict(self.self_model),
            "concepts": self.concepts,
            "meta_lr": self.meta_lr,
        }

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        self.world = {}
        for k, v in (data.get("world") or {}).items():
            if "|" in k and isinstance(v, (list, tuple)) and len(v) == 2:
                gk, b = k.split("|", 1)
                self.world[(gk, b)] = (int(v[0]), float(v[1]))
        self.self_model = {b: (int(v[0]), int(v[1]))
                           for b, v in (data.get("self_model") or {}).items()
                           if isinstance(v, (list, tuple)) and len(v) == 2}
        self.concepts = {k: v for k, v in (data.get("concepts") or {}).items()
                         if isinstance(v, dict)}
        self.meta_lr = clamp(float(data.get("meta_lr", 0.06) or 0.06), 0.02, 0.25)
