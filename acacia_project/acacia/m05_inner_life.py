

# ============================================================================
# [3.5] INNER LIFE  (idle simulation: time awareness, interests, daydreaming)
# ============================================================================
#
# Runs the creature's mind when nobody is talking to it.  Everything here is
# cheap per-tick bookkeeping - NO language model call ever happens inside
# this class.  All it ever does is set brain.wants_to_think = True with a
# reason; the app layer (which owns the worker threads) decides whether and
# when to actually spend an inference call on it, gated by a cooldown so the
# model is invoked for genuinely meaningful moments, not continuously.

DAYPARTS = [
    (5, 8, "early morning"), (8, 12, "morning"), (12, 14, "midday"),
    (14, 18, "afternoon"), (18, 22, "evening"), (22, 24, "night"),
    (0, 5, "the middle of the night"),
]


def day_part(ts=None) -> str:
    hour = time.localtime(ts or time.time()).tm_hour
    for lo, hi, name in DAYPARTS:
        if lo <= hour < hi:
            return name
    return "night"


class InnerLife:
    """Time awareness + interests + idle daydreaming + reflection triggers.

    Two tiers of idle activity, on purpose:
      1. CHEAP idle events (state-only, every tick): mind wandering to a
         known interest, noticing the time of day changed.  These use the
         normal Event pipeline so they show up in the log with a cause,
         same as anything else - but never touch the LLM.
      2. RARE, gated 'real thoughts': only when genuinely idle for a while
         AND boredom/curiosity is high AND the cooldown has elapsed does it
         ask the app layer for an actual model-generated internal monologue.
    """

    IDLE_THRESHOLD = 50.0        # seconds of silence before any wandering
    THINK_IDLE_MULT = 2.0        # real thoughts need this many x the threshold
    MIN_THOUGHT_GAP = 210.0      # hard floor: >= ~3.5 minutes between real thoughts
    IDLE_EVENT_CHANCE = 0.05     # base per-second chance of a cheap wander event
    INTEREST_DECAY = 0.985

    def __init__(self):
        self.interests = {}                 # topic -> strength (unbounded, soft cap ~3)
        self.thoughts = deque(maxlen=30)     # (t, text, kind)
        self.idle_seconds = 0.0
        self.last_thought_t = 0.0
        self.last_daypart = day_part()
        self.awake_at = time.time()
        self._decay_accum = 0.0

    # -- persistence -----------------------------------------------------
    def to_dict(self):
        top = sorted(self.interests.items(), key=lambda kv: -kv[1])[:40]
        return {
            "interests": {k: round(v, 3) for k, v in top},
            "last_thought_t": self.last_thought_t,
            "thoughts": [list(row) for row in list(self.thoughts)[-15:]],
        }

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        interests = data.get("interests")
        if isinstance(interests, dict):
            for k, v in interests.items():
                try:
                    self.interests[str(k)] = float(v)
                except Exception:
                    pass
        self.last_thought_t = float(data.get("last_thought_t", 0.0) or 0.0)
        for row in data.get("thoughts", []) or []:
            if isinstance(row, (list, tuple)) and len(row) == 3:
                self.thoughts.append(tuple(row))

    # -- interests ---------------------------------------------------------
    def note_topic(self, word, weight=0.12):
        if not word or len(word) < 3:
            return
        self.interests[word] = min(3.0, self.interests.get(word, 0.0) + weight)

    def note_topics(self, words, weight=0.10):
        for w in list(words)[:6]:
            self.note_topic(w, weight)

    def top_interests(self, n=5):
        return [w for w, _ in sorted(self.interests.items(), key=lambda kv: -kv[1])[:n]]

    # -- tick ----------------------------------------------------------
    def tick(self, dt, brain):
        """Called every brain tick (~10Hz).  Cheap: state updates only."""
        now = time.time()
        self.idle_seconds = (now - brain.last_interaction) if brain.last_interaction \
            else self.idle_seconds + dt

        # time-of-day awareness: notice a change, a genuinely cheap event
        part = day_part(now)
        if part != self.last_daypart:
            self.last_daypart = part
            brain.perceive(Event("daypart_change", f"it is now {part}",
                                 salience=0.12, quiet=True))

        # interests fade slowly unless reinforced by conversation
        self._decay_accum += dt
        if self._decay_accum > 20.0:
            self._decay_accum = 0.0
            for k in list(self.interests):
                self.interests[k] *= self.INTEREST_DECAY
                if self.interests[k] < 0.03:
                    del self.interests[k]

        if self.idle_seconds < self.IDLE_THRESHOLD or brain.thinking:
            return

        e = brain.emotion
        # cheap idle 'wandering': state-only, never calls the model
        wander_pull = clamp01(0.6 * e.boredom + 0.4 * e.curiosity)
        if random.random() < self.IDLE_EVENT_CHANCE * wander_pull * dt:
            topic = random.choice(self.top_interests(6) or [None])
            text = f"mind drifted to {topic}" if topic else \
                "mind wandered without landing on anything"
            brain.perceive(Event("idle_wander", text, salience=0.15,
                                 valence=0.03, quiet=True))
            self.thoughts.append((now, text, "drift"))

        # rare, gated: ask the app layer for a real, model-generated thought
        # [PHASE 59] the MIN_THOUGHT_GAP check this subsystem used to do for
        # itself is now one request to the single arbiter; ripeness (idle,
        # bored or curious) is still decided here, where the evidence is.
        deeply_idle = self.idle_seconds > (self.IDLE_THRESHOLD * self.THINK_IDLE_MULT)
        ripe = (e.boredom > 0.62 or e.curiosity > 0.66) and deeply_idle
        att = getattr(brain, "attention", None)
        cooldown_ok = (ripe and not brain.wants_to_think and
                       (att.request("inner_thought",
                                    importance=max(e.boredom, e.curiosity),
                                    min_gap=self.MIN_THOUGHT_GAP)
                        if att is not None
                        else (now - self.last_thought_t) >= self.MIN_THOUGHT_GAP))
        if cooldown_ok and ripe and not brain.wants_to_think:
            brain.wants_to_think = True
            brain.think_reason = (f"boredom built up to {e.boredom:.0%}"
                                  if e.boredom >= e.curiosity
                                  else f"curiosity built up to {e.curiosity:.0%}")

    def record_thought(self, text):
        self.thoughts.append((time.time(), text, "generated"))
        self.last_thought_t = time.time()
