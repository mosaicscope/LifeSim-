

# ============================================================================
# [4] NEEDS + GOAL SYSTEM
# ============================================================================

class Goal:
    __slots__ = ("name", "urgency", "why", "kind")

    def __init__(self, name, urgency, why, kind="need"):
        self.name = name
        self.urgency = clamp01(urgency)
        self.why = why
        self.kind = kind

    def __repr__(self):
        return f"<Goal {self.name} {self.urgency:.2f}>"


class GoalSystem:
    """Needs -> goals -> priorities -> current focus.
    Needs are the metabolic layer preserved from the original simulation."""

    def __init__(self):
        self.hunger = 0.2
        self.thirst = 0.2
        self.energy = 1.0
        self.social = 0.3
        self.stimulation = 0.3     # need for novelty / input
        self.safety = 0.0          # rises on startle
        self.goals = []
        self.focus = None
        self.recent_actions = deque(maxlen=12)
        self.last_satisfied = {}
        self.dynamic = []          # goals CREATURE proposes to itself, not need-driven

    NEED_KEYS = ("hunger", "thirst", "energy", "social", "stimulation", "safety")
    RESOLVED_TTL = 240.0        # how long a succeeded/failed goal stays around
                                 # for reflection before it's actually dropped

    def to_dict(self):
        d = {k: round(float(getattr(self, k)), 4) for k in self.NEED_KEYS}
        # GOAL LIFECYCLE persistence: long-running self-proposed goals survive
        # a restart instead of evaporating the moment the app closes.
        d["dynamic"] = [dict(g) for g in self.dynamic]
        return d

    def from_dict(self, data):
        if isinstance(data, dict):
            for k in self.NEED_KEYS:
                if isinstance(data.get(k), (int, float)):
                    setattr(self, k, clamp01(float(data[k])))
            now = time.time()
            restored = []
            for g in data.get("dynamic", []) or []:
                if not isinstance(g, dict) or "name" not in g:
                    continue
                g = dict(g)
                g.setdefault("status", "created")
                g.setdefault("created", now)
                g.setdefault("updated", now)
                g.setdefault("good", 0)
                g.setdefault("bad", 0)
                # a goal that survives a restart isn't stale just because the
                # process was closed - only drop ones already fully resolved
                # long enough ago that they've served their reflective purpose
                if g["status"] in ("succeeded", "failed", "abandoned") and \
                        now - float(g.get("updated", now)) > self.RESOLVED_TTL:
                    continue
                g["expires"] = max(float(g.get("expires", now + 180.0)), now + 60.0)
                restored.append(g)
            self.dynamic = restored[:8]

    def tick(self, dt, emotion, behavior):
        """Metabolism.  Rates are per-second (the original per-frame values
        scaled by 30fps) so the simulation no longer depends on frame rate."""
        self.hunger = clamp01(self.hunger + 0.0035 * dt)
        self.thirst = clamp01(self.thirst + 0.0040 * dt)
        drain = 0.0012 + 0.0020 * emotion.arousal
        if behavior in ("move", "curious"):
            drain += 0.0015
        self.energy = clamp01(self.energy - drain * dt)
        if behavior == "rest":
            self.energy = clamp01(self.energy + 0.020 * dt)
        self.social = clamp01(self.social + 0.0020 * dt)
        self.stimulation = clamp01(self.stimulation + 0.0025 * dt - 0.25 * emotion.novelty * dt)
        self.safety = clamp01(self.safety - 0.25 * dt)
        emotion.energy = self.energy

    def satisfy(self, need, amount, note=""):
        if hasattr(self, need):
            setattr(self, need, clamp01(getattr(self, need) - amount))
            self.last_satisfied[need] = time.time()
            if note:
                self.recent_actions.append((time.time(), note))

    def act(self, note):
        self.recent_actions.append((time.time(), note))

    def propose(self, name, urgency, why, ttl=180.0, kind="discovery"):
        """CONSOLIDATION/CURIOSITY -> NEW GOALS: something CREATURE itself
        decided is worth pursuing (a discovery or an open question, not a
        metabolic need). Deduplicated by name so re-discovering the same
        thing refreshes it instead of piling up duplicates.

        GOAL LIFECYCLE: CREATED -> ACTIVE -> PAUSED -> SUCCEEDED/FAILED/
        ABANDONED. A goal that already resolved and is re-proposed (the same
        discovery keeps re-surfacing) gets a genuine second chance rather
        than staying dead forever."""
        now = time.time()
        for d in self.dynamic:
            if d["name"] == name:
                d["urgency"], d["expires"] = clamp01(urgency), now + ttl
                d["updated"] = now
                if d["status"] in ("succeeded", "failed", "abandoned"):
                    d["status"], d["good"], d["bad"] = "created", 0, 0
                return
        self.dynamic.append({
            "name": name, "urgency": clamp01(urgency), "why": why, "kind": kind,
            "expires": now + ttl, "status": "created",
            "created": now, "updated": now, "good": 0, "bad": 0,
        })
        if len(self.dynamic) > 8:
            self.dynamic.sort(key=lambda d: d["urgency"])
            self.dynamic.pop(0)

    def record_progress(self, name, dv, threshold=0.02):
        """AUTONOMOUS AGENCY -> GOAL LIFECYCLE: measured consequence of
        actually pursuing a self-proposed goal moves it toward SUCCEEDED
        (repeatedly pays off) or FAILED (repeatedly doesn't). Only ever
        driven by real valence deltas measured after the fact."""
        for d in self.dynamic:
            if d["name"] != name or d["status"] in ("succeeded", "failed", "abandoned"):
                continue
            d["status"] = "active"
            d["updated"] = time.time()
            if dv > threshold:
                d["good"] = d.get("good", 0) + 1
            elif dv < -threshold:
                d["bad"] = d.get("bad", 0) + 1
            if d["good"] >= 3:
                d["status"] = "succeeded"
            elif d["bad"] >= 3:
                d["status"] = "failed"
            return d["status"]
        return None

    # ------------------------------------------------- [PHASE 38] projects
    # A Project is a long-lived `dynamic` goal (already restart-safe, already
    # persisted) with milestone tracking layered on top - no new class, no
    # new persistence file, no new scheduler. Spans many sessions instead of
    # resolving after 3 measured outcomes like an ordinary dynamic goal.
    def start_project(self, name, why, milestones=4, ttl=14 * 86400.0, kind="project"):
        for d in self.dynamic:
            if d["name"] == name:
                return d
        self.propose(name, urgency=0.35, why=why, ttl=ttl, kind=kind)
        for d in self.dynamic:
            if d["name"] == name:
                d["milestones_total"] = max(1, int(milestones))
                d["milestones_done"] = 0
                return d
        return None

    def advance_project(self, name, dv, threshold=0.05):
        """Measured progress on one session of a project. Every threshold-
        beating positive outcome completes one milestone; the project as a
        whole succeeds only once all milestones are actually done - real,
        cumulative multi-session continuity, not a single lucky result."""
        for d in self.dynamic:
            if d["name"] != name or d.get("kind") != "project":
                continue
            if d["status"] in ("succeeded", "failed", "abandoned"):
                return d
            d["status"] = "active"
            d["updated"] = time.time()
            total = d.get("milestones_total", 4)
            if dv > threshold:
                d["milestones_done"] = min(total, d.get("milestones_done", 0) + 1)
            elif dv < -threshold:
                d["bad"] = d.get("bad", 0) + 1
            if d.get("milestones_done", 0) >= total:
                d["status"] = "succeeded"
            elif d.get("bad", 0) >= 6:
                d["status"] = "failed"
            return d
        return None

    def projects(self):
        return [d for d in self.dynamic if d.get("kind") == "project"]

    def pause(self, name):
        for d in self.dynamic:
            if d["name"] == name and d["status"] == "active":
                d["status"] = "paused"
                d["updated"] = time.time()
                return True
        return False

    def abandon(self, name, why=""):
        for d in self.dynamic:
            if d["name"] == name and d["status"] not in ("succeeded", "failed", "abandoned"):
                d["status"] = "abandoned"
                d["updated"] = time.time()
                if why:
                    d["why"] = why
                return True
        return False

    def active_dynamic(self):
        """Dynamic goals still worth actually pursuing right now."""
        now = time.time()
        return [d for d in self.dynamic
                if d["expires"] > now and d["status"] in ("created", "active", "paused")]

    def rebuild(self, emotion):
        """Recompute goal priorities from needs + affect."""
        now = time.time()
        # keep resolved goals around briefly (for reflection/history) but
        # only ever let unresolved or paused ones actually expire outright
        self.dynamic = [d for d in self.dynamic
                        if d["expires"] > now or
                        (d["status"] in ("succeeded", "failed", "abandoned") and
                         now - d.get("updated", now) < self.RESOLVED_TTL)][:8]
        g = []
        g.append(Goal("find food", self.hunger * 1.1, f"hunger {self.hunger:.0%}"))
        g.append(Goal("find water", self.thirst * 1.05, f"thirst {self.thirst:.0%}"))
        g.append(Goal("rest", (1.0 - self.energy) * 1.15, f"energy {self.energy:.0%}"))
        g.append(Goal("seek company", self.social * (0.75 + 0.5 * emotion.affection),
                      f"social need {self.social:.0%}", kind="social"))
        g.append(Goal("find something new", 0.55 * self.stimulation + 0.6 * emotion.boredom,
                      f"boredom {emotion.boredom:.0%}", kind="explore"))
        g.append(Goal("understand what the user means",
                      0.75 * emotion.curiosity * (0.4 + 0.6 * emotion.attention),
                      f"curiosity {emotion.curiosity:.0%}", kind="cognitive"))
        g.append(Goal("calm down", emotion.stress * 1.2, f"stress {emotion.stress:.0%}",
                      kind="regulate"))
        g.append(Goal("let my mind wander", 0.5 * emotion.boredom + 0.4 * emotion.curiosity,
                      f"idle, boredom {emotion.boredom:.0%} curiosity {emotion.curiosity:.0%}",
                      kind="reflect"))
        g.append(Goal("stay present", 0.28, "baseline", kind="idle"))
        for d in self.active_dynamic():
            g.append(Goal(d["name"], d["urgency"], d["why"], kind=d.get("kind", "discovery")))
            if d["status"] == "created":
                d["status"] = "active"
                d["updated"] = now
        g.sort(key=lambda goal: goal.urgency, reverse=True)
        self.goals = g[:6]
        self.focus = self.goals[0]
        return self.focus
