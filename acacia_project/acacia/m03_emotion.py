

# ============================================================================
# [2] EMOTION SYSTEM
# ============================================================================
#
# Continuous dimensions are the ground truth.  Categorical emotions are
# DERIVED from them, then:
#     raw score -> EMA smoothing -> sticky selection with hysteresis
# so the displayed emotion cannot flicker frame to frame.

EMOTIONS = [
    "neutral", "happy", "sad", "angry", "anxious", "excited", "curious",
    "bored", "surprised", "calm", "frustrated", "affectionate", "confident",
    "tired",
]

# emotions allowed to interrupt a held emotion early (real startles)
INTERRUPT_EMOTIONS = {"surprised", "angry", "anxious"}

EMOTION_COLORS = {
    "neutral": "#8fd66a", "happy": "#ffe066", "curious": "#7ec8e3",
    "scared": "#d98fd6", "tired": "#b7a78a",
    "excited": "#ff9d4d", "bored": "#b0b0b0", "calm": "#bfe3d0",
    "sad": "#7f9bd1", "angry": "#e8654f", "anxious": "#d98fd6",
    "surprised": "#f2f0a0", "frustrated": "#e09a63",
    "affectionate": "#ff9fc4", "confident": "#9ee07e",
}

EMOTION_UI = {
    "neutral": "#9aa6bd", "happy": "#ffd95e", "sad": "#7f9bd1",
    "angry": "#ff7a63", "anxious": "#c99bff", "excited": "#ffab5e",
    "curious": "#7ec8e3", "bored": "#94a0b3", "surprised": "#f4f08f",
    "calm": "#8fe0c0", "frustrated": "#ffa066", "affectionate": "#ff9fc4",
    "confident": "#9ee07e", "tired": "#b7a78a",
}


class EmotionSystem:
    """Continuous affective state + sticky categorical read-out.

    Tuning knobs (all deliberately exposed):
      SMOOTH_TAU     how fast raw emotion scores are smoothed (seconds)
      SWITCH_MARGIN  how much better a candidate must be to take over
      MIN_HOLD       minimum commitment time for the current emotion
      MOMENTUM       extra margin proportional to current intensity
    """

    SMOOTH_TAU = 1.6
    SWITCH_MARGIN = 0.08
    MOMENTUM = 0.12
    MIN_HOLD = 5.0
    # slow, low-arousal states persist much longer than quick spikes do
    HOLD_OVERRIDE = {"tired": 14.0, "bored": 11.0, "sad": 11.0, "calm": 8.0,
                     "affectionate": 8.0, "surprised": 2.5}
    INTERRUPT_MARGIN = 0.34
    INTERRUPT_HOLD = 1.6

    # homeostatic baselines: everything drifts back here, slowly
    BASELINE = {
        "valence": 0.12, "arousal": 0.34, "stress": 0.08, "curiosity": 0.42,
        "confidence": 0.55, "boredom": 0.30, "attention": 0.35, "novelty": 0.10,
    }
    # per-dimension return rates (1/seconds).  Stress decays slowly, surprise fast.
    RATE = {
        "valence": 0.035, "arousal": 0.10, "stress": 0.022, "curiosity": 0.030,
        "confidence": 0.018, "boredom": 0.010, "attention": 0.12, "novelty": 0.40,
    }

    def __init__(self):
        # --- continuous dimensions -------------------------------------
        self.valence = 0.12          # -1 .. +1
        self.arousal = 0.34          # 0 .. 1
        self.energy = 1.0            # 0 .. 1 (metabolic, owned by needs too)
        self.stress = 0.05
        self.curiosity = 0.40
        self.confidence = 0.55
        self.boredom = 0.25
        self.attention = 0.35
        self.novelty = 0.05
        self.affection = 0.15        # warmth toward the user
        self.frustration = 0.0       # accumulates on blocked goals

        # mood = very slow moving average of valence ("how life is going")
        self.mood = 0.1

        # --- categorical read-out --------------------------------------
        self.scores = {e: 0.0 for e in EMOTIONS}
        self.smoothed = {e: 0.0 for e in EMOTIONS}
        self.smoothed["neutral"] = 0.4
        self.emotion = "neutral"
        self.intensity = 0.3
        self.last_switch = time.time()
        self.previous = "neutral"
        self.last_cause = "waking up"
        self._cause_time = 0.0
        self.history = deque(maxlen=40)     # (t, emotion, cause)

        # internal clock: all hold/debounce timing is in SIMULATED seconds,
        # so hysteresis behaves identically if the loop lags or is stepped fast
        self.clock = 0.0
        self.last_switch = 0.0

        # novelty/sensory debounce
        self._novelty_target = 0.05
        self._novelty_next = 0.0

    # -- state io ------------------------------------------------------
    DIMS = ("valence", "arousal", "energy", "stress", "curiosity", "confidence",
            "boredom", "attention", "novelty", "affection", "frustration", "mood")

    def to_dict(self):
        d = {k: round(float(getattr(self, k)), 4) for k in self.DIMS}
        d["emotion"] = self.emotion
        d["intensity"] = round(self.intensity, 3)
        return d

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        for k in self.DIMS:
            if isinstance(data.get(k), (int, float)):
                setattr(self, k, float(data[k]))
        if data.get("emotion") in EMOTIONS:
            self.emotion = data["emotion"]
            self.smoothed[self.emotion] = 0.5
        self.intensity = float(data.get("intensity", 0.3) or 0.3)
        self.last_switch = self.clock

    # -- perturbation --------------------------------------------------
    def nudge(self, dim: str, delta: float, cause: str = ""):
        """The only way anything changes instantly.  Always has a cause."""
        if not hasattr(self, dim):
            return
        lo = -1.0 if dim in ("valence", "mood") else 0.0
        setattr(self, dim, clamp(getattr(self, dim) + delta, lo, 1.0))
        if cause and abs(delta) >= 0.05:
            self.last_cause = cause
            self._cause_time = self.clock

    def bump_novelty(self, value: float, cause: str = ""):
        """Novelty is debounced: it only re-targets a few times a second so
        sensory noise cannot regenerate a new emotional world every frame."""
        self._novelty_target = max(self._novelty_target, clamp01(value))
        if cause:
            self.last_cause = cause

    # -- integration ---------------------------------------------------
    def tick(self, dt: float, ctx: dict):
        dt = clamp(dt, 0.001, 0.5)
        self.clock += dt
        now = self.clock

        # 1. debounced novelty: re-sample target at most every 400ms
        if now >= self._novelty_next:
            self._novelty_next = now + 0.4
            ambient = 0.02 + 0.05 * random.random()
            self._novelty_target = max(ambient, self._novelty_target * 0.55)
        self.novelty = approach(self.novelty, self._novelty_target, self.RATE["novelty"], dt)

        # 2. homeostatic drift (inertia: nothing snaps back instantly)
        for dim in ("valence", "arousal", "stress", "curiosity", "confidence", "attention"):
            base = self.BASELINE[dim]
            if dim == "valence":
                base = clamp(self.BASELINE["valence"] + 0.5 * self.mood, -0.6, 0.7)
            setattr(self, dim, approach(getattr(self, dim), base, self.RATE[dim], dt))
        self.frustration = approach(self.frustration, 0.0, 0.05, dt)
        self.affection = approach(self.affection, 0.12, 0.004, dt)

        # 3. boredom: grows with monotony, dies with stimulation
        stim = clamp01(0.6 * self.novelty + 0.4 * ctx.get("stimulation", 0.0))
        bored_target = clamp01(0.85 - 1.1 * stim + 0.25 * (1.0 - self.arousal))
        rate = 0.012 if bored_target > self.boredom else 0.16   # slow to bore, quick to un-bore
        self.boredom = approach(self.boredom, bored_target, rate, dt)

        # 4. couplings
        self.energy = clamp01(ctx.get("energy", self.energy))
        if self.stress > 0.6:
            self.confidence = approach(self.confidence, 0.25, 0.02, dt)
        if self.energy < 0.3:
            self.arousal = approach(self.arousal, 0.2, 0.05, dt)
        self.curiosity = clamp01(self.curiosity + 0.015 * self.boredom * dt)

        # 5. mood: very slow integral of valence
        self.mood = clamp(approach(self.mood, self.valence, 0.006, dt), -1.0, 1.0)

        # 6. raw -> smoothed emotion scores, then sticky selection
        self._score(ctx)
        alpha = 1.0 - math.exp(-dt / self.SMOOTH_TAU)
        for name, raw in self.scores.items():
            self.smoothed[name] = self.smoothed[name] + (raw - self.smoothed[name]) * alpha
        self._select(now)

        # intensity follows the winning score, also smoothed
        self.intensity = approach(self.intensity, clamp01(self.smoothed[self.emotion]), 1.2, dt)

    def _score(self, ctx):
        """Map the continuous state onto categorical candidates.
        Scores are tuned so that a clearly-felt state (a dimension above ~0.5)
        beats the neutral floor, while a merely drifting state does not."""
        v, a = self.valence, self.arousal
        pos, neg = clamp01(v), clamp01(-v)
        calm_ = 1.0 - a
        low_stress = 1.0 - self.stress
        energy = self.energy
        fit_mid = clamp01(1.0 - abs(a - 0.55) * 1.6)     # "comfortably awake"
        closeness = ctx.get("social_closeness", 0.0)
        s = self.scores

        s["neutral"] = 0.22 + 0.10 * (1.0 - abs(v)) * low_stress
        s["happy"] = pos * (0.65 + 0.35 * fit_mid) * low_stress * 1.15
        s["excited"] = pos * (0.45 + 0.55 * a) * (0.5 + 0.5 * self.novelty) \
            * (0.45 + 0.55 * energy) * 1.10
        s["calm"] = (0.30 + 0.50 * pos) * (0.5 + 0.5 * calm_) * low_stress \
            * (1.0 - 0.5 * self.boredom)
        s["sad"] = neg * (0.55 + 0.45 * calm_) * (0.65 + 0.35 * (1.0 - energy)) * 1.25
        s["angry"] = neg * (0.35 + 0.65 * a) * (0.5 + 0.5 * self.frustration) \
            * (0.6 + 0.4 * self.confidence) * 1.35
        s["frustrated"] = self.frustration * (0.55 + 0.45 * neg) * (0.5 + 0.5 * a) * 1.25
        s["anxious"] = self.stress * (0.55 + 0.45 * a) \
            * (0.6 + 0.4 * (1.0 - self.confidence)) * 1.25
        s["curious"] = self.curiosity * (0.45 + 0.55 * self.novelty) \
            * (0.55 + 0.45 * clamp01(v + 0.5)) * (0.5 + 0.5 * energy) * 1.20
        s["bored"] = self.boredom * (0.6 + 0.4 * (1.0 - self.novelty)) \
            * (0.6 + 0.4 * calm_) * low_stress
        s["surprised"] = clamp01((self.novelty - 0.5) * 2.0) * (0.45 + 0.55 * a)
        s["affectionate"] = self.affection * (0.55 + 0.45 * clamp01(0.4 + v)) \
            * (0.5 + 0.5 * closeness) * 1.30
        s["confident"] = clamp01(self.confidence - 0.45) * 1.8 \
            * (0.5 + 0.5 * clamp01(0.4 + v)) * low_stress
        s["tired"] = clamp01(0.75 - energy * 1.7) * (0.6 + 0.4 * calm_)

        for k in s:
            s[k] = clamp01(s[k])

    def _select(self, now):
        """Sticky emotion selection with hysteresis + minimum hold time."""
        current = self.emotion
        cur_score = self.smoothed.get(current, 0.0)
        best = max(self.smoothed, key=lambda k: self.smoothed[k])
        if best == current:
            return

        held = now - self.last_switch
        margin = self.SWITCH_MARGIN + self.MOMENTUM * self.intensity
        gap = self.smoothed[best] - cur_score

        interrupting = best in INTERRUPT_EMOTIONS and gap >= self.INTERRUPT_MARGIN
        min_hold = (self.INTERRUPT_HOLD if interrupting
                    else self.HOLD_OVERRIDE.get(current, self.MIN_HOLD))
        if held < min_hold:
            return
        if not interrupting and gap < margin:
            return

        if self.clock - self._cause_time > 25.0:
            self.last_cause = self._explain(best)     # no recent event: say why
        self.previous = current
        self.emotion = best
        self.last_switch = now
        self.history.append((time.time(), best, self.last_cause))

    def _explain(self, emotion_name):
        """When nothing recent caused the shift, name the drifting dimension."""
        return {
            "tired": f"energy has drained to {self.energy:.0%}",
            "bored": f"nothing has happened for a while (boredom {self.boredom:.0%})",
            "curious": f"curiosity built up to {self.curiosity:.0%}",
            "calm": "things settled down",
            "anxious": f"stress climbed to {self.stress:.0%}",
            "sad": "mood drifted low",
            "happy": "mood drifted up",
            "confident": "feeling steady",
            "neutral": "everything levelled out",
            "excited": "energy and novelty built up",
            "frustrated": "something keeps not working",
            "affectionate": "warmth toward the user built up",
            "angry": "irritation built up",
            "surprised": "something unexpected",
        }.get(emotion_name, "internal drift")

    # -- read-out ------------------------------------------------------
    def mood_word(self):
        m = self.mood
        if m > 0.45:
            return "buoyant"
        if m > 0.15:
            return "good"
        if m > -0.1:
            return "level"
        if m > -0.4:
            return "low"
        return "heavy"

    def level_word(self, value, low="low", mid="moderate", high="high"):
        return low if value < 0.33 else (mid if value < 0.66 else high)

    def dims(self):
        return {
            "valence": self.valence, "arousal": self.arousal, "energy": self.energy,
            "stress": self.stress, "curiosity": self.curiosity,
            "confidence": self.confidence, "boredom": self.boredom,
            "attention": self.attention, "novelty": self.novelty,
            "affection": self.affection, "frustration": self.frustration,
            "mood": self.mood,
        }
