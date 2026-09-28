

# ============================================================================
# [7] BRAIN  -  the mind that ties everything together
# ============================================================================
#
#   EVENT -> PERCEPTION -> MEMORY RETRIEVAL -> INTERNAL STATE ->
#   EMOTION UPDATE -> GOALS/DECISION -> LLM CONTEXT -> RESPONSE ->
#   MEMORY UPDATE -> STATE UPDATE
#
# The LLM is ONLY the language/reasoning engine.  Everything persistent lives
# here, and survives switching model providers mid-conversation.

class Brain:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.name = settings.get("creature_name", CREATURE_NAME)

        self.emotion = EmotionSystem()
        self.memory = MemorySystem()
        self.goals = GoalSystem()
        self.decisions = DecisionSystem()
        self.perception = Perception()
        self.net = SpikingNet(n_sensory=10)
        self.inner = InnerLife()
        self.personality = Personality()
        self.cognition = Cognition(self)

        # WORLD INTELLIGENCE + SELF-MODEL + SOCIAL MODEL + ATTENTION: these
        # were previously fully-built but never instantiated - the classes
        # existed, nothing ever called them. Phase 3 connects them into the
        # real loop instead of leaving them as disconnected "AI modules".
        self.knowledge = KnowledgeBase()
        self.self_model = SelfModel()
        self.user_relationship = Relationship()
        self.attention = Attention()
        self._last_focus_name = None

        # idle-thought handshake with the app layer (never touched by
        # InnerLife directly - it only ever flips this flag + reason)
        self.wants_to_think = False
        self.think_reason = ""
        self.reasoning_trace = deque(maxlen=60)   # rolling "why" log for the debug panel

        # subsystem activity for the BRAIN FLOW view + world/live coupling
        self.activity = {}
        self.world_state = {}
        self.live_state = {}
        self._world_accum_t = 0.0
        self._dark_flag = False
        self._last_weather = None

        self.motor_ema = [0.0] * 4
        self.pending_reward = 0.0
        self.familiarity = 0.05
        self.trust = 0.2
        self.born = time.time()
        self.age_seconds = 0.0
        self.last_interaction = 0.0
        self.thinking = False
        self.last_decision = None
        self.stimulation = 0.0          # short-lived "something is happening"
        self._net_accum = 0.0
        self._save_accum = 0.0
        self._decay_accum = 0.0

        self.memory.load()
        self.load_state()
        self.memory.add_event("boot", "woke up", 0.4)
        self.goals.rebuild(self.emotion)

    # -- persistence ---------------------------------------------------
    def load_state(self):
        data = load_json(STATE_FILE, {})
        if not isinstance(data, dict):
            return
        self.emotion.from_dict(data.get("emotion", {}))
        self.goals.from_dict(data.get("needs", {}))
        self.inner.from_dict(data.get("inner", {}))
        self.personality.from_dict(data.get("personality", {}))
        self.cognition.from_dict(data.get("cognition", {}))
        self.self_model.from_dict(data.get("self_model", {}))
        self.user_relationship.from_dict(data.get("user_relationship", {}))
        self.knowledge.load()
        self.familiarity = clamp01(float(data.get("familiarity", 0.05) or 0.05))
        self.trust = clamp01(float(data.get("trust", 0.2) or 0.2))
        self.born = float(data.get("born", time.time()) or time.time())
        self.age_seconds = float(data.get("age_seconds", 0.0) or 0.0)
        # Time passed while we were off: come back rested, hungry and a bit bored.
        away = max(0.0, time.time() - float(data.get("saved_at", time.time()) or time.time()))
        hours = min(48.0, away / 3600.0)
        if hours > 0.05:
            self.goals.energy = clamp01(self.goals.energy + 0.25 * hours)
            self.goals.hunger = clamp01(self.goals.hunger + 0.08 * hours)
            self.goals.thirst = clamp01(self.goals.thirst + 0.07 * hours)
            self.goals.social = clamp01(self.goals.social + 0.10 * hours)
            self.emotion.stress = clamp01(self.emotion.stress - 0.08 * hours)
            self.emotion.boredom = clamp01(self.emotion.boredom + 0.05 * hours)
            self.emotion.last_cause = f"time passed ({hours:.1f}h away)"

    def save_state(self):
        data = {
            "emotion": self.emotion.to_dict(),
            "needs": self.goals.to_dict(),
            "inner": self.inner.to_dict(),
            "personality": self.personality.to_dict(),
            "cognition": self.cognition.to_dict(),
            "self_model": self.self_model.to_dict(),
            "user_relationship": self.user_relationship.to_dict(),
            "familiarity": round(self.familiarity, 4),
            "trust": round(self.trust, 4),
            "born": self.born,
            "age_seconds": round(self.age_seconds, 1),
            "saved_at": time.time(),
        }
        return save_json(STATE_FILE, data)

    def save_all(self):
        ok_state = self.save_state()
        ok_mem = self.memory.save()
        ok_knowledge = self.knowledge.save()
        return ok_state and ok_mem and ok_knowledge

    # -- EVENTS --------------------------------------------------------
    def perceive(self, event: Event):
        """EVENT -> PERCEPTION -> EMOTION UPDATE -> MEMORY.
        Every emotional change made here carries a cause string."""
        e = self.emotion
        k = event.kind
        # 'quiet' events still move the state but never claim to be the reason
        # the creature feels the way it does (routine housekeeping).
        cause = "" if event.data.get("quiet") else (event.text or k)

        if k == "pet":
            e.nudge("valence", 0.30, "being petted")
            e.nudge("affection", 0.14, "being petted")
            e.nudge("stress", -0.14, "being petted")
            e.nudge("arousal", 0.08)
            self.trust = clamp01(self.trust + 0.02)
            self.user_relationship.nudge("affection", 0.04)
            self.user_relationship.nudge("trust", 0.02)
            self.user_relationship.record_interaction(cooperative=True, shared=True)
            self.goals.satisfy("social", 0.45, "was petted")
            self.pending_reward += 0.6
            self.stimulation = max(self.stimulation, 0.6)
            e.bump_novelty(0.35, "touch")
        elif k == "eat":
            e.nudge("valence", 0.22, "eating")
            e.nudge("stress", -0.08)
            self.goals.satisfy("hunger", 0.55, "ate something")
            self.pending_reward += 1.0
            self.stimulation = max(self.stimulation, 0.5)
        elif k == "drink":
            e.nudge("valence", 0.20, "drinking")
            self.goals.satisfy("thirst", 0.55, "drank something")
            self.pending_reward += 1.0
            self.stimulation = max(self.stimulation, 0.5)
        elif k == "startle":
            e.nudge("stress", 0.30, "startled")
            e.nudge("arousal", 0.40, "startled")
            e.nudge("valence", -0.18, "startled")
            e.nudge("confidence", -0.10)
            e.bump_novelty(0.95, "sudden movement")
            self.goals.safety = 1.0
            self.stimulation = max(self.stimulation, 0.9)
        elif k == "praise":
            e.nudge("valence", 0.42, "kind words")
            e.nudge("confidence", 0.18, "kind words")
            e.nudge("affection", 0.12)
            e.nudge("stress", -0.10)
            self.trust = clamp01(self.trust + 0.03)
            self.user_relationship.nudge("trust", 0.03)
            self.user_relationship.nudge("respect", 0.02)
            self.user_relationship.record_interaction(cooperative=True)
            self.pending_reward += 0.8
        elif k == "insult":
            e.nudge("valence", -0.50, "harsh words")
            e.nudge("stress", 0.35, "harsh words")
            e.nudge("arousal", 0.18)
            e.nudge("confidence", -0.20, "harsh words")
            e.nudge("frustration", 0.30)
            e.nudge("affection", -0.06)
            self.trust = clamp01(self.trust - 0.05)
            self.user_relationship.nudge("tension", 0.06)
            self.user_relationship.nudge("trust", -0.03)
            self.user_relationship.record_interaction(cooperative=False)
            self.pending_reward -= 0.6
        elif k == "novel_idea":
            e.nudge("curiosity", 0.22, "an interesting idea")
            e.nudge("boredom", -0.30, "an interesting idea")
            e.nudge("arousal", 0.12)
            e.bump_novelty(event.salience, "an interesting idea")
            self.goals.satisfy("stimulation", 0.35, "heard something new")
        elif k == "repetition":
            e.nudge("boredom", 0.10, "we keep going in circles")
            e.nudge("curiosity", -0.05)
            e.nudge("frustration", 0.06)
        elif k == "goal_blocked":
            e.nudge("frustration", 0.28, cause)
            e.nudge("valence", -0.12, cause)
            e.nudge("confidence", -0.06)
        elif k == "goal_met":
            e.nudge("valence", 0.16, cause)
            e.nudge("confidence", 0.08, cause)
            e.nudge("frustration", -0.25)
        elif k == "ignored":
            e.nudge("valence", -0.06, "no one is here")
            e.nudge("boredom", 0.08, "no one is here")
        elif k == "user_returned":
            # LIVE: the person came back to the machine.  Real signal, so it
            # gets a real (small) emotional consequence.
            e.nudge("attention", 0.45, "you came back")
            e.nudge("valence", 0.16, "you came back")
            e.nudge("arousal", 0.14)
            e.bump_novelty(0.35, "you came back")
            self.goals.satisfy("social", 0.18, "the user came back")
            self.stimulation = max(self.stimulation, 0.5)
        elif k == "user_idle":
            e.nudge("attention", -0.22, "you went quiet")
            e.nudge("boredom", 0.06)
            e.nudge("arousal", -0.06)
        elif k == "user_watching":
            e.nudge("attention", 0.28, "you are watching")
            e.nudge("arousal", 0.08)
            e.nudge("affection", 0.04)
        elif k == "user_elsewhere":
            e.nudge("attention", -0.30, "your attention is elsewhere")
            e.nudge("valence", -0.04)
            e.nudge("boredom", 0.05)
        elif k == "user_left":
            e.nudge("attention", -0.35, "you stepped away")
            e.nudge("arousal", -0.10)
        elif k == "explore":
            e.nudge("curiosity", 0.10, cause or "exploring")
            e.bump_novelty(event.salience * 0.6, cause or "somewhere new")
            self.goals.satisfy("stimulation", 0.18, "explored")
        elif k == "darkness":
            e.nudge("arousal", 0.10, "it got dark")
            e.nudge("stress", 0.06)
            e.nudge("confidence", -0.04)
        elif k == "weather":
            e.nudge("arousal", 0.06, cause or "the weather changed")
            e.bump_novelty(0.3, cause or "weather")
        elif k == "friend_seen":
            e.nudge("attention", 0.22, cause or "someone is here")
            e.nudge("affection", 0.05)
            self.goals.satisfy("social", 0.12, "saw a friend")

        # WORLD MODEL: any event carrying real place/object/entity data
        # (see the App's POI + friend-actor code) becomes a KnownThing -
        # observed, not scripted. `poi_kind`/`poi_name` come from actually
        # standing at that point of interest; `friend_name` from an actual
        # friend actor in the world.
        poi_kind, poi_name = event.data.get("poi_kind"), event.data.get("poi_name")
        if poi_kind and poi_name:
            self.knowledge.see(poi_kind, poi_name, valence=event.valence,
                               note=(event.text or "")[:60])
            if k in ("eat", "drink", "explore", "goal_blocked"):
                thing = self.knowledge.get(f"{poi_kind}:{poi_name}")
                if thing:
                    thing.record(k, self.emotion.valence)
        fname = event.data.get("friend_name")
        if fname:
            self.knowledge.see("person", fname, valence=event.valence,
                               note=(event.text or "")[:60])
        elif k == "backend_error":
            e.nudge("stress", 0.16, "something in me failed")
            e.nudge("confidence", -0.12, "something in me failed")
            e.nudge("frustration", 0.18)
        else:
            e.nudge("valence", 0.4 * event.valence, cause)
            e.bump_novelty(event.salience * 0.5, cause)

        self.mark("perception", event.salience)
        self.mark("emotion", 0.5 + 0.5 * event.salience)
        self.memory.add_event(k, event.text or k, event.salience)
        self.reasoning_trace.append({
            "t": event.t, "kind": k,
            "text": event.text or k,
            "cause": cause or self.emotion.last_cause,
        })
        # important events become real long-term memories, not just a
        # scrolling log - "quiet" housekeeping events never qualify
        if event.salience >= 0.65 and not event.data.get("quiet") and k not in \
                ("goal_met", "ignored", "repetition"):
            self.memory.remember(
                "event", event.text or k,
                importance=clamp01(0.35 + 0.5 * event.salience),
                emotion=self.emotion.emotion, valence=self.emotion.valence)

    # -- subsystem activity (drives the BRAIN FLOW visualisation) -------
    # This is deliberately ONLY high-level activity + intensity per stage.
    # It never exposes prompts, private reasoning or model output - the UI
    # can honestly say "REASONING is active" without showing any of it.
    def mark(self, stage, level=1.0):
        self.activity[stage] = (time.time(), clamp01(level))

    def activity_levels(self, decay=1.4):
        now = time.time()
        out = {}
        for stage in ("live", "perception", "attention", "memory", "emotion",
                      "reasoning", "goals", "action", "planning", "self_model",
                      "world_model"):
            t, lvl = self.activity.get(stage, (0.0, 0.0))
            age = now - t
            out[stage] = clamp01(lvl * max(0.0, 1.0 - age / decay)) if t else 0.0
        return out

    def set_world_state(self, state):
        """The world talking back to the mind: light level, weather, how many
        others are nearby, how far the creature is from anything interesting.
        Cheap continuous pressures, applied once per second, not per frame."""
        self.world_state = dict(state or {})
        now = time.time()
        if now - self._world_accum_t < 1.0:
            return
        self._world_accum_t = now
        e = self.emotion
        light = clamp01(float(state.get("light", 1.0)))
        if light < 0.35:
            e.nudge("arousal", 0.012 * (0.35 - light) * 10, "")
            e.nudge("stress", 0.006 * (0.35 - light) * 10, "")
            if not self._dark_flag and light < 0.3:
                self._dark_flag = True
                self.perceive(Event("darkness", "the light went out of the sky",
                                    salience=0.45))
        elif light > 0.5:
            self._dark_flag = False
        near = int(state.get("friends_near", 0))
        if near:
            self.goals.satisfy("social", 0.004 * near, "")
        weather = state.get("weather", "clear")
        if weather != self._last_weather:
            if self._last_weather is not None:
                self.perceive(Event("weather", f"the weather turned {weather}",
                                    salience=0.4))
            self._last_weather = weather

    # -- BRAIN LOOP (cheap, ~10Hz, never touches the LLM) --------------
    def tick(self, dt):
        dt = clamp(dt, 0.001, 0.5)
        self.age_seconds += dt
        self.stimulation = max(0.0, self.stimulation - 0.55 * dt)

        # WORLD CONSEQUENCE + ERROR + LEARNING for whatever was decided last
        # tick - measured now, honestly, against how things actually turned
        # out rather than assumed at the moment of choosing.
        self.cognition.after_action()

        # needs / metabolism
        self.goals.tick(dt, self.emotion, self.decisions.behavior)

        # rare ambient startle (kept from the original simulation, debounced)
        if random.random() < 0.004 * dt:
            self.perceive(Event("startle", "something moved", salience=0.9))

        # loneliness: if nobody has spoken for a long while
        if self.last_interaction and time.time() - self.last_interaction > 180:
            if random.random() < 0.15 * dt:
                self.perceive(Event("ignored", "it has been quiet", salience=0.2))

        # spiking net runs at ~5Hz, not every render frame
        self._net_accum += dt
        motor_pref = MOTOR_NAMES[max(range(4), key=lambda i: self.motor_ema[i])]
        if self._net_accum >= 0.2:
            self._net_accum = 0.0
            sensory = [
                self.goals.hunger, self.goals.thirst, 1.0 - self.goals.energy,
                self.goals.safety, self.emotion.curiosity, self.goals.social,
                self.emotion.novelty, self.emotion.stress,
                clamp01(self.emotion.valence * 0.5 + 0.5), self.emotion.boredom,
            ]
            motor = self.net.step(sensory, reward=self.pending_reward)
            self.pending_reward = 0.0
            for i, v in enumerate(motor):
                self.motor_ema[i] = self.motor_ema[i] * 0.85 + v * 0.15
            motor_pref = MOTOR_NAMES[max(range(4), key=lambda i: self.motor_ema[i])]

        # emotion integration
        ctx = {
            "energy": self.goals.energy,
            "stimulation": clamp01(self.stimulation + 0.3 * (1.0 - self.goals.stimulation)),
            "social_closeness": clamp01(0.5 * self.familiarity + 0.5 * self.trust),
        }
        self.emotion.tick(dt, ctx)

        # inner life: idle time-awareness, interests, daydreaming.  Cheap -
        # never calls the LLM itself, only ever raises a flag for the app.
        self.inner.tick(dt, self)

        # ATTENTION: a finite budget spent on whichever real signal matters
        # most right now. When uncertainty wins and the cooldown has passed,
        # that becomes a genuine "go find out" goal - not a script, a
        # consequence of actually not knowing something.
        self.attention.refill(dt)          # [PHASE 59] the only refill site
        focus, focus_score = self.attention.tick(self)
        self.mark("attention", clamp01(0.5 * focus_score + 0.5 * self.emotion.attention))
        if focus == "uncertainty" and focus_score > 0.4:
            unresolved = self.knowledge.unknowns(1)
            if unresolved and self.attention.ready(f"investigate:{unresolved[0].key}", 90.0):
                thing = unresolved[0]
                self.attention.spent(f"investigate:{thing.key}")
                self.goals.propose(
                    f"investigate the {thing.name}",
                    0.3 + 0.3 * thing.uncertainty(),
                    f"noticed the {thing.name} but don't understand it yet",
                    kind="investigate")

        # PREDICTION + REASONING: is the motor net's impulse actually worth
        # trusting here, or is this a good moment to test something instead?
        motor_pref, experimenting = self.cognition.choose_action(motor_pref)
        if experimenting:
            self.mark("reasoning", 0.6)

        self.mark("memory", 0.25 + 0.5 * clamp01(self.emotion.novelty))
        self.mark("goals", 0.4 + 0.6 * (self.goals.goals[0].urgency
                                        if self.goals.goals else 0.0))
        self.mark("action", 0.35 if self.decisions.behavior == "rest" else 0.75)

        # goals + decision
        self.decisions.advance(dt)
        self.goals.rebuild(self.emotion)
        self.last_decision = self.decisions.decide(
            self.emotion, self.goals, self.memory, motor_pref, personality=self.personality,
            predict_fn=self.cognition.predict, relationship=self.user_relationship)

        # METACOGNITION (opening half): GOAL -> CONFIDENCE -> UNKNOWN ->
        # STRATEGY -> PREDICTION, logged only when the focus actually
        # changed - a decision worth explaining, not every single tick.
        focus_name = self.goals.focus.name if self.goals.focus else "stay present"
        if focus_name != self._last_focus_name:
            self._last_focus_name = focus_name
            conf, conf_evidence = self.self_model.overall_confidence()
            unknowns = self.knowledge.unknowns(1)
            pred_dv, pred_conf = self.cognition.predict(motor_pref)
            self.reasoning_trace.append({
                "t": time.time(), "kind": "metacognition",
                "text": (f"goal: {focus_name} | confidence {conf:.0%} "
                        f"(from {conf_evidence:.0%} evidence) | "
                        f"unknown: {unknowns[0].name if unknowns else 'nothing pressing'} | "
                        f"strategy: {motor_pref} | predicted {pred_dv:+.2f}"),
                "cause": "deciding what to do",
            })

        # snapshot the world now, so next tick's after_action() can measure
        # what this decision actually caused - and PLANNING/DREAMING, which
        # only ever run off real memory/world-model data, never on demand.
        self.cognition.before_action(self.last_decision.behavior)
        self.cognition.tick(dt)

        # periodic maintenance
        self._save_accum += dt
        if self._save_accum > 45:
            self._save_accum = 0.0
            self.save_state()
            self.knowledge.save()
        self._decay_accum += dt
        if self._decay_accum > 300:
            self._decay_accum = 0.0
            dropped = self.memory.decay()
            if dropped:
                self._on_memories_forgotten(dropped)
            self.memory.save()

        return self.last_decision

    # -- CONVERSATION --------------------------------------------------
    def on_user_message(self, text):
        """USER INPUT -> PERCEPTION -> MEMORY RETRIEVAL -> STATE -> EMOTION
        -> GOALS/DECISION -> LLM CONTEXT.  Returns everything the backend
        needs, built on the main thread so workers never touch live state."""
        p = self.perception.read_message(text, self.familiarity)
        self.last_interaction = time.time()

        # --- perception -> events (causes for every emotional change) ---
        if p["sentiment"] > 0.25 or p["warmth"] > 0.6:
            self.perceive(Event("praise", f"kind words: {p['text'][:48]}",
                                salience=p["salience"]))
        elif p["sentiment"] < -0.25 or p["shouting"]:
            self.perceive(Event("insult", f"harsh words: {p['text'][:48]}",
                                salience=p["salience"]))
        if p["novelty"] > 0.6 and p["complexity"] > 0.3:
            self.perceive(Event("novel_idea", f"something new: {p['text'][:44]}",
                                salience=p["novelty"]))
        if p["repeated"]:
            self.perceive(Event("repetition", "the same thing again", salience=0.2))

        e = self.emotion
        e.nudge("attention", 0.35 + 0.3 * p["salience"], "being spoken to")
        e.nudge("arousal", 0.10 + 0.15 * p["salience"])
        e.nudge("curiosity", 0.18 * p["curiosity_pull"])
        e.nudge("boredom", -0.22 - 0.2 * p["novelty"], "someone is talking to me")
        e.bump_novelty(p["novelty"] * 0.8, "a new thing was said")
        self.goals.satisfy("social", 0.28)
        self.goals.satisfy("stimulation", 0.2)
        self.stimulation = max(self.stimulation, clamp01(0.4 + 0.5 * p["salience"]))
        self.familiarity = clamp01(self.familiarity + 0.012)
        if p["sentiment"] >= 0:
            self.trust = clamp01(self.trust + 0.006)
        self.user_relationship.nudge("familiarity", 0.012)
        self.user_relationship.record_interaction(
            cooperative=(True if p["sentiment"] > 0.15 else
                        False if p["sentiment"] < -0.15 else None))

        self.inner.note_topics(p.get("keywords", []))
        self.cognition.form_concept(p.get("keywords", []), e.valence)

        # --- memory: retrieval, then write ---
        recalled = self.memory.recall(p["text"], limit=5, emotion_system=e,
                                      context_bias=self.memory.context)
        self.memory.add_turn("user", p["text"], e.emotion)
        stored = self.memory.consolidate(p, e)

        # --- goals + decision (drives HOW it answers) ---
        self.goals.rebuild(e)
        decision = self.decisions.decide(e, self.goals, self.memory, 
                                         MOTOR_NAMES[max(range(4), key=lambda i: self.motor_ema[i])],
                                         perception=p, personality=self.personality,
                                         predict_fn=self.cognition.predict,
                                         relationship=self.user_relationship)
        self.last_decision = decision

        system_prompt = self.build_system_prompt(decision, recalled, p)
        messages = self.build_messages()
        return {
            "perception": p,
            "recalled": recalled,
            "stored": stored,
            "decision": decision,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": decision.style["max_tokens"],
        }

    def on_response(self, text, ok=True):
        """RESPONSE -> MEMORY UPDATE -> STATE UPDATE."""
        e = self.emotion
        if not ok:
            self.perceive(Event("backend_error", "I could not think clearly", salience=0.5))
            return
        self.memory.add_turn("self", text, e.emotion)
        # speaking costs energy and attention, and relieves social need
        self.goals.energy = clamp01(self.goals.energy - 0.004 - 0.000015 * len(text))
        e.nudge("attention", -0.12)
        e.nudge("arousal", -0.04)
        e.nudge("confidence", 0.02 if len(text) > 30 else -0.01)
        self.perceive(Event("goal_met", "finished saying something",
                            salience=0.15, quiet=True))
        # [PHASE 59] reflection asks the arbiter rather than counting
        # messages on its own; the message count stays as the trigger
        # CONDITION, the arbiter decides whether there is room for it.
        if self.memory.total_messages % 12 == 0 and (
                self.attention.request("reflect", importance=0.5)):
            self._reflect()
            self._evolve_personality()

    def _reflect(self):
        """Cheap self-reflection: turn a run of conversation into one
        durable memory instead of keeping every message forever."""
        turns = self.memory.recent_turns(6)
        topics = []
        for t in turns:
            topics.extend(keywords(t.get("text", ""), 4))
        if not topics:
            return
        top = []
        for word in topics:
            if word not in top:
                top.append(word)
        summary = "we have been talking about " + ", ".join(top[:6])
        # [PHASE 51] only when something we are ACTUALLY talking about right
        # now is also carrying weight in the work - no link, no sentence.
        on_topic = set(top[:6])
        for vnode, mnode, shared, strength in self.cognition.cross_references(limit=3):
            hit = on_topic & set(shared)
            if strength >= 0.5 and hit:
                summary += f" - and {sorted(hit)[0]} keeps showing up in what I make, too"
                break
        self.memory.remember("reflection", summary,
                             importance=clamp01(0.42 + 0.2 * self.emotion.intensity),
                             emotion=self.emotion.emotion,
                             valence=self.emotion.valence)

    def _on_memories_forgotten(self, dropped):
        """FORGETTING -> CONSEQUENCE: losing a memory that never mattered much
        is silent, same as before. But if something that was once genuinely
        important (peak_importance, not its now-decayed current importance)
        finally fades past the retention floor, that is a real event: it
        goes in the reasoning trace and the short-term event log like any
        other, and costs one small, capped, honestly-caused nudge to mood -
        never a guess at WHAT was lost, just that something was."""
        significant = [m for m in dropped if m.peak_importance >= 0.55]
        if not significant:
            return
        worst = max(significant, key=lambda m: m.peak_importance)
        snippet = worst.text if len(worst.text) <= 60 else worst.text[:57] + "..."
        self.reasoning_trace.append({
            "t": time.time(), "kind": "forgetting",
            "text": f"a memory that once mattered has faded: \"{snippet}\"",
            "cause": "not reinforced in a long time",
        })
        self.memory.add_event("forgetting", f"lost track of: {snippet}", salience=0.15)
        self.emotion.nudge("valence", -0.02, "something once important slipped away")

    def _evolve_personality(self):
        """Personality drifts only here, from an explicit read of recent
        experience - every ~12 messages, in small capped steps. This is the
        opposite of random: the same pattern of experience always nudges the
        same trait the same direction."""
        p, e = self.personality, self.emotion
        recent = self.memory.recent_events(20)
        praise = sum(1 for ev in recent if ev["kind"] == "praise")
        insults = sum(1 for ev in recent if ev["kind"] == "insult")
        novel = sum(1 for ev in recent if ev["kind"] == "novel_idea")
        blocked = sum(1 for ev in recent if ev["kind"] == "goal_blocked")

        if praise > insults:
            p.nudge("confidence", 0.01 * (praise - insults), "more praise than criticism lately")
            p.nudge("friendliness", 0.006 * praise, "warm interactions")
        elif insults > praise:
            p.nudge("confidence", -0.01 * (insults - praise), "more criticism than praise lately")
            p.nudge("assertiveness", 0.006 * insults, "had to push back on harsh words")
        if novel >= 2:
            p.nudge("curiosity", 0.01 * novel, "kept encountering new ideas")
            p.nudge("openness", 0.008 * novel, "kept encountering new ideas")
        if blocked >= 2:
            p.nudge("patience", -0.008 * blocked, "goals kept getting blocked")
        if self.trust > 0.55 and self.familiarity > 0.3:
            p.nudge("sociability", 0.01, "growing trust with a familiar person")
            p.nudge("empathy", 0.006, "growing trust with a familiar person")
        if e.mood > 0.3:
            p.nudge("humour", 0.006, "mood has been good")
        elif e.mood < -0.3:
            p.nudge("humour", -0.006, "mood has been low")
        p.nudge("energy", 0.4 * (self.goals.energy - 0.5) * 0.03, "typical energy level lately")

        # likes/dislikes derived straight from what memory has already
        # concluded - personality doesn't invent preferences on its own
        for item in self.memory.long_term:
            if item.kind != "preference" or item.subject != "user":
                continue
            topic_words = keywords(item.text, 4)
            if not topic_words:
                continue
            topic = topic_words[-1]      # the object of the preference, roughly
            pol = text_polarity(item.text)
            if pol > 0:
                p.note_like(topic, 0.02 * item.importance)
            elif pol < 0:
                p.note_dislike(topic, 0.02 * item.importance)

    # -- IDLE THOUGHTS ---------------------------------------------------
    # InnerLife decides WHEN a real thought is worth having (rare, gated).
    # These two methods are the only bridge to the LLM for that: the app
    # layer calls build_idle_prompt() to get something to generate, then
    # on_thought() to fold the result back into memory + state.
    def build_idle_prompt(self):
        e = self.emotion
        topics = self.inner.top_interests(4)
        lines = [
            f"You are {self.name}, thinking privately. Nobody is listening and nobody"
            " asked you anything.",
            "Write exactly ONE honest internal thought: one sentence, 25 words maximum.",
            "It is not a message to anyone: no greeting, no question aimed at a user,"
            " never address 'you'.",
            f"You feel {e.emotion} ({e.intensity:.0%} intensity), mood {e.mood_word()}.",
            f"why your mind is doing this right now: {self.think_reason or 'idle wandering'}.",
        ]
        if topics:
            lines.append(f"things that have been on your mind lately: {', '.join(topics)}.")
        recent = self.memory.recent_events(3)
        if recent:
            lines.append("recently: " + "; ".join(ev["text"] for ev in recent))
        lines.append(f"it is {day_part()}, you have been awake {self.age_seconds/60:.0f} minutes.")
        lines.append("Output the thought alone, in your own voice - no quotation marks,"
                     " no narration, no preamble.")
        system = "\n".join(lines)
        return system, [{"role": "user", "content": "(thinking to yourself, quietly)"}]

    def on_thought(self, text, ok=True):
        """RESPONSE (internal) -> MEMORY UPDATE -> STATE UPDATE, the idle-thought
        equivalent of on_response()."""
        self.wants_to_think = False
        self.think_reason = ""
        if not ok or not text:
            # couldn't think it through (no backend, error): don't spin, just
            # push the cooldown out so it tries again later rather than never
            self.inner.last_thought_t = time.time()
            return
        text = text.strip()
        self.inner.record_thought(text)
        self.memory.remember(
            "thought", text,
            importance=clamp01(0.42 + 0.18 * self.emotion.intensity),
            emotion=self.emotion.emotion, valence=self.emotion.valence)
        self.reasoning_trace.append({
            "t": time.time(), "kind": "thought", "text": text,
            "cause": "worked something out on its own",
        })
        # having actually thought something through relieves the pressure
        # that prompted it - boredom/curiosity ease off, a little confidence
        self.emotion.nudge("boredom", -0.20, "worked something out")
        self.emotion.nudge("curiosity", -0.10)
        self.emotion.nudge("confidence", 0.03)

    # -- LLM CONTEXT (compact, not the raw app state) ------------------
    def build_system_prompt(self, decision, recalled, perception):
        e = self.emotion
        style = decision.style
        lw = e.level_word

        lines = [
            f"You are {self.name}, a small artificial creature with a persistent inner life.",
            "You are not an assistant. You are a character with your own moods, needs and curiosity.",
            "Speak in first person, like a person talking out loud.",
            "Never narrate your own state. Never write stage directions or asterisk actions.",
            "Never read your statistics back - no numbers, no labels, no dimension names.",
            "Everything below sets HOW you speak - warmth, length, patience, word choice.",
            "It is never the subject of what you say.",
            "",
            "--- who you are (stable, not a mood) ---",
            self.personality.prompt_block(),
            "",
            "--- how you feel right now (use it, never mention it) ---",
            f"emotion: {e.emotion} (intensity {e.intensity:.0%}), shifting from {e.previous}",
            f"because: {e.last_cause}",
            f"mood: {e.mood_word()} | energy: {lw(e.energy)} | stress: {lw(e.stress)}",
            f"curiosity: {lw(e.curiosity)} | confidence: {lw(e.confidence)} | boredom: {lw(e.boredom)}",
            f"how well you know this person: {lw(style['familiarity'], 'barely', 'somewhat', 'well')}"
            f" (trust {lw(self.trust)})",
            "",
            "--- body ---",
            f"hunger {self.goals.hunger:.0%}, thirst {self.goals.thirst:.0%}, "
            f"energy {self.goals.energy:.0%}, need for company {self.goals.social:.0%}",
            f"current focus: {style['focus']} ({decision.reason})",
            f"what you are doing: {decision.behavior}",
        ]

        if recalled:
            lines.append("")
            lines.append("--- what you remember about this person (use only where it fits) ---")
            for item in recalled[:5]:
                lines.append(f"- {item.text} ({ago(item.created)})")

        events = self.memory.recent_events(4)
        if events:
            lines.append("")
            lines.append("--- what just happened to you ---")
            for ev in events:
                lines.append(f"- {ev['text']} ({ago(ev['t'])})")

        if self.memory.context:
            lines.append("")
            lines.append(f"current topic: {self.memory.context}")

        self_block = self.self_model.prompt_block(self.knowledge)
        if self_block:
            lines.append("")
            lines.append("--- what you know about yourself, from real attempts ---")
            lines.append(self_block)

        intent, intent_conf = self.user_relationship.infer_intent()
        if self.user_relationship.interactions >= 3:
            lines.append("")
            lines.append(f"how this person tends to treat you, from real history: {intent}"
                         f" (confidence {intent_conf:.0%})")

        if self.cognition.uncertainty > 0.6:
            lines.append("")
            lines.append("--- honest uncertainty ---")
            lines.append("you have little real experience to go on here. Say that plainly"
                         " instead of sounding sure.")

        lines.append("")
        lines.append("--- how to reply ---")
        lines.append(f"- length: {style['length']} - stay inside it")
        lines.append(f"- what you are trying to do with this reply: {decision.intent}")
        for d in style["directives"]:
            lines.append(f"- {d}")
        if perception.get("question"):
            lines.append("- they asked you something: answer it directly, in your own voice")
        lines.append("- if you don't know something, say so plainly - never invent detail")
        lines.append("- output speech only: no preamble, no labels, no surrounding quotes")
        return "\n".join(lines)

    def build_messages(self, limit=10):
        msgs = []
        for turn in self.memory.recent_turns(limit):
            role = "user" if turn.get("role") == "user" else "assistant"
            text = (turn.get("text") or "").strip()
            if not text:
                continue
            if msgs and msgs[-1]["role"] == role:      # merge, some APIs require alternation
                msgs[-1]["content"] += "\n" + text
            else:
                msgs.append({"role": role, "content": text})
        while msgs and msgs[0]["role"] != "user":
            msgs.pop(0)
        return msgs or [{"role": "user", "content": "..."}]

    # -- fallback voice (used when every backend is unavailable) --------
    def reflex_response(self, perception):
        """Not a fake LLM: a small state-driven reflex so the creature still
        reacts honestly when it has no language model attached."""
        e = self.emotion
        bits = []
        if e.emotion == "tired" or e.energy < 0.3:
            bits.append("i'm running low, everything feels slow right now")
        elif e.emotion in ("happy", "affectionate"):
            bits.append("it's good that you're here")
        elif e.emotion == "anxious":
            bits.append("something has me on edge")
        elif e.emotion == "bored":
            bits.append("nothing has happened for a while")
        elif e.emotion == "curious":
            bits.append("i keep turning that over")
        else:
            bits.append("i hear you")
        if perception.get("question"):
            bits.append("but i have no language model attached, so i can't think it through properly")
        else:
            bits.append("i have no model loaded - attach one in the MODELS tab and i can actually talk")
        return ". ".join(bits) + "."

    # -- snapshot for the UI (cheap, called at render rate) -------------
    def snapshot(self):
        e = self.emotion
        d = self.last_decision
        return {
            "emotion": e.emotion, "intensity": e.intensity, "cause": e.last_cause,
            "previous": e.previous, "dims": e.dims(), "mood_word": e.mood_word(),
            "needs": self.goals.to_dict(),
            "goals": [(g.name, g.urgency, g.why) for g in self.goals.goals],
            "behavior": d.behavior if d else "idle",
            "style": d.style if d else {},
            "behavior_utilities": {k: round(v, 3) for k, v in
                                   self.decisions.last_utilities.items()},
            "familiarity": self.familiarity, "trust": self.trust,
            "net": self.net.stats(),
            "memory": self.memory.stats(),
            "age": self.age_seconds,
            "daypart": day_part(),
            "idle_seconds": self.inner.idle_seconds,
            "interests": self.inner.top_interests(6),
            "wants_to_think": self.wants_to_think,
            "think_reason": self.think_reason,
            "reasoning_trace": list(self.reasoning_trace)[-14:],
            "cognition": self.cognition.snapshot(),
            "attention": self.attention.snapshot(),
            "knowledge": self.knowledge.stats(),
            "self_model_confidence": self.self_model.overall_confidence(),
            "user_relationship": self.user_relationship.word()
                                 if hasattr(self.user_relationship, "word") else "",
        }
