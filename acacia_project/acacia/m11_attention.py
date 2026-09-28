

# ============================================================================
# [5.5] ATTENTION  (a finite budget, spent on whatever matters most right now)
# ============================================================================
#
# Every real cue the rest of the mind already computes - danger, goal
# urgency, novelty, uncertainty, prediction error, social relevance,
# curiosity, memory salience - competes for a SINGLE limited budget instead
# of all firing at once. This is also what keeps behaviour from getting
# stuck: a cooldown per target stops the same "investigate X" impulse from
# firing every single tick once X wins attention once.

class Attention:
    CHANNELS = ("danger", "goals", "novelty", "uncertainty", "prediction_error",
                "social", "curiosity", "memory")

    def __init__(self):
        self.scores = {c: 0.0 for c in self.CHANNELS}
        self.focus = "goals"
        self.focus_score = 0.0
        self._cooldowns = {}          # target key -> last-fired timestamp
        self.budget = self.BUDGET_MAX   # [PHASE 59] shared, refilled per tick

    def ready(self, key, cooldown=45.0):
        last = self._cooldowns.get(key, 0.0)
        return (time.time() - last) >= cooldown

    def spent(self, key):
        self._cooldowns[key] = time.time()

    # ------------------------------------ [PHASE 59] the budget arbiter -----
    # THE SINGLE ARBITER. Every idle-driven subsystem (inner life, dreaming,
    # planning, reflection, studio autonomy, social exchanges, digests) asks
    # HERE for time instead of each keeping its own timer. This is the fix
    # for the "second scheduler" risk flagged since Phase 19, so it is
    # deliberately built ON the cooldown store that already existed rather
    # than beside it: `request` is `ready`+`spent` plus a shared budget.
    #
    # It owns no timer of its own and never runs anything. Subsystems still
    # decide WHETHER they want to act (rest state, boredom, focus); the
    # arbiter only decides whether there is capacity to act right now.

    BUDGET_MAX = 1.0
    REFILL_PER_SEC = 0.10          # full budget from empty in ~10s of idle
    COSTS = {"inner_thought": 0.30, "dream": 0.50, "plan": 0.15,
             "reflect": 0.25, "studio": 0.60, "social": 0.40, "digest": 0.35}
    MIN_GAP = {"inner_thought": 45.0, "dream": 90.0, "plan": 20.0,
               "reflect": 60.0, "studio": 120.0, "social": 480.0, "digest": 600.0}

    def refill(self, dt):
        self.budget = clamp(getattr(self, "budget", self.BUDGET_MAX) +
                            self.REFILL_PER_SEC * max(0.0, float(dt)),
                            0.0, self.BUDGET_MAX)

    def request(self, subsystem, importance=0.5, cost=None, min_gap=None):
        """-> True if this subsystem may run NOW. Grants deduct from the
        shared budget and stamp the same cooldown store `ready`/`spent`
        use, so nothing can be granted twice inside its own gap."""
        key = f"budget:{subsystem}"
        gap = self.MIN_GAP.get(subsystem, 45.0) if min_gap is None else float(min_gap)
        if not self.ready(key, gap):
            return False
        price = (self.COSTS.get(subsystem, 0.3) if cost is None else float(cost))
        price *= clamp(1.25 - clamp01(importance), 0.5, 1.25)
        if getattr(self, "budget", self.BUDGET_MAX) < price:
            return False
        self.budget -= price
        self.spent(key)
        return True

    def budget_report(self):
        now = time.time()
        rows = [f"attention budget {getattr(self, 'budget', self.BUDGET_MAX):.2f}"
                f"/{self.BUDGET_MAX:.2f}"]
        for sub in sorted(self.COSTS):
            last = self._cooldowns.get(f"budget:{sub}", 0.0)
            when = "never" if not last else f"{now - last:.0f}s ago"
            rows.append(f"  {sub}: cost {self.COSTS[sub]:.2f}, "
                        f"gap {self.MIN_GAP.get(sub, 45.0):.0f}s, last {when}")
        return rows

    def tick(self, brain):
        e, g, k, c = brain.emotion, brain.goals, brain.knowledge, brain.cognition
        near = int((brain.world_state or {}).get("friends_near", 0))
        top_goal = g.goals[0].urgency if g.goals else 0.0
        recent_mem = brain.memory.long_term[-1].importance if brain.memory.long_term else 0.0
        scores = {
            "danger": clamp01(g.safety * 1.2 + e.stress * 0.4),
            "goals": clamp01(top_goal),
            "novelty": clamp01(e.novelty),
            "uncertainty": clamp01(c.uncertainty * 0.6 + 0.4 * (len(k.unknowns(6)) / 6.0)),
            "prediction_error": clamp01(k.prediction_error),
            "social": clamp01(0.25 * near + brain.user_relationship.tension * 0.5 +
                              (0.3 if brain.last_interaction and
                               time.time() - brain.last_interaction < 60 else 0.0)),
            "curiosity": clamp01(e.curiosity),
            "memory": clamp01(recent_mem),
        }
        self.scores = scores
        self.focus, self.focus_score = max(scores.items(), key=lambda kv: kv[1])
        return self.focus, self.focus_score

    def snapshot(self):
        return {"focus": self.focus, "score": round(self.focus_score, 3),
                "scores": {k: round(v, 3) for k, v in self.scores.items()}}
