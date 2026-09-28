

# ============================================================================
# [3.7] RELATIONSHIPS + FRIENDS  (the social world's building blocks)
# ============================================================================

class Relationship:
    """How one character feels about another. Changes gradually from
    experience - same hard-cap-per-nudge philosophy as Personality, so nothing
    can make a relationship swing wildly from one event."""

    DIMS = ("familiarity", "trust", "affection", "respect", "tension", "compatibility")
    MAX_NUDGE = 0.06

    def __init__(self):
        self.familiarity = 0.05
        self.trust = 0.35
        self.affection = 0.15
        self.respect = 0.45
        self.tension = 0.0
        self.compatibility = 0.5
        # SOCIAL MODEL EXTENSIONS: cooperation/conflict pattern, a
        # confidence-scored inference about likely intent, and a count of
        # genuinely shared experiences - all driven only by real recorded
        # interactions, never guessed at creation time.
        self.cooperation = 0
        self.conflict = 0
        self.interactions = 0
        self.shared_experiences = 0
        self.predicted_intent = ""          # inferred label, "" until evidenced
        self.last_t = 0.0                   # [PHASE 58] when this pair last met

    def nudge(self, dim, delta):
        if dim not in self.DIMS:
            return
        delta = clamp(delta, -self.MAX_NUDGE, self.MAX_NUDGE)
        setattr(self, dim, clamp01(getattr(self, dim) + delta))

    def record_interaction(self, cooperative=None, shared=False):
        """Log one real interaction. `cooperative` is True/False when the
        interaction observably helped or hurt the relationship, or None for
        a neutral/ambiguous one - ambiguous interactions still count toward
        `interactions` (so uncertainty can fall) but not toward either
        cooperation or conflict (so the ratio stays honest)."""
        self.interactions += 1
        if cooperative is True:
            self.cooperation += 1
        elif cooperative is False:
            self.conflict += 1
        if shared:
            self.shared_experiences += 1
        self._update_intent()

    def uncertainty(self):
        """High when there is little real interaction history to go on -
        this is what makes 'I don't know what they'll do' representable."""
        return 1.0 - clamp01(self.interactions / (self.interactions + 6.0))

    def _update_intent(self):
        """Infer a likely-behaviour label from the observed cooperation vs
        conflict ratio. Requires a real minimum of evidence - otherwise the
        label stays empty (UNKNOWN), never a guess dressed as a fact."""
        total = self.cooperation + self.conflict
        if total < 3:
            self.predicted_intent = ""
            return
        ratio = self.cooperation / total
        if ratio >= 0.75:
            self.predicted_intent = "cooperative"
        elif ratio <= 0.25:
            self.predicted_intent = "antagonistic"
        elif self.tension > 0.5:
            self.predicted_intent = "unpredictable"
        else:
            self.predicted_intent = "mixed"

    def infer_intent(self):
        """(label, confidence) - confidence grows with real evidence only."""
        total = self.cooperation + self.conflict
        if not self.predicted_intent:
            return "unclear (not enough history)", 0.0
        return self.predicted_intent, clamp01(total / (total + 5.0))

    def to_dict(self):
        d = {dim: round(getattr(self, dim), 4) for dim in self.DIMS}
        d.update({
            "cooperation": self.cooperation, "conflict": self.conflict,
            "interactions": self.interactions,
            "shared_experiences": self.shared_experiences,
            "predicted_intent": self.predicted_intent,
            "last_t": self.last_t,
        })
        return d

    def from_dict(self, data):
        if isinstance(data, dict):
            for d in self.DIMS:
                if isinstance(data.get(d), (int, float)):
                    setattr(self, d, clamp01(float(data[d])))
            self.cooperation = int(data.get("cooperation", 0) or 0)
            self.conflict = int(data.get("conflict", 0) or 0)
            self.interactions = int(data.get("interactions", 0) or 0)
            self.shared_experiences = int(data.get("shared_experiences", 0) or 0)
            self.predicted_intent = str(data.get("predicted_intent", "") or "")
            # pre-58 records simply have no meeting time yet
            self.last_t = float(data.get("last_t", 0.0) or 0.0)

    def word(self):
        if self.tension > 0.55 and self.trust < 0.4:
            return "strained"
        if self.familiarity < 0.15:
            return "just met"
        if self.affection > 0.65 and self.trust > 0.6:
            return "close"
        if self.trust > 0.55:
            return "friendly"
        if self.tension > 0.35:
            return "a little tense"
        return "acquainted"

    def summary(self):
        return (f"{self.word()} (familiarity {self.familiarity:.0%}, trust {self.trust:.0%}, "
               f"affection {self.affection:.0%}, tension {self.tension:.0%})")


FRIEND_ACTIVITIES = ["idle", "resting", "exploring", "thinking", "working on a goal"]


class Friend:
    """A separate simulated individual - own personality, own memory, own
    light emotional/activity state. NOT a copy of the main character:
    personality is generated independently (or authored by the user) and
    never shares state with Brain. Deliberately lighter-weight than Brain
    (no spiking net, no 10Hz emotion tick) - see SocialWorld for why."""

    def __init__(self, name, seed=None, interests=None, fid=None):
        self.id = fid or f"f_{int(time.time()*1000)%10**9}_{random.randint(100,999)}"
        self.name = name
        self.personality = Personality(seed=seed)
        self.interests = list(interests or [])
        self.memory = MemorySystem()            # this friend's own memories
        self.relationship_user = Relationship()  # how they feel about the user
        self.relationships = {}                  # other friend id -> Relationship
        self.mood_valence = 0.1
        self.energy = 0.8
        self.activity = "idle"
        self.activity_with = None                # name of whoever they're 'with'
        self.last_active = time.time()
        self.created = time.time()
        self.conversation = deque(maxlen=20)      # 1:1 chat with the user

    def relationship_with(self, other_id):
        if other_id not in self.relationships:
            self.relationships[other_id] = Relationship()
        return self.relationships[other_id]

    def mood_word(self):
        if self.mood_valence > 0.35:
            return "upbeat"
        if self.mood_valence < -0.3:
            return "down"
        return "even"

    def to_dict(self):
        return {
            "id": self.id, "name": self.name,
            "personality": self.personality.to_dict(),
            "interests": self.interests,
            "memory": self.memory.export_dict(),
            "relationship_user": self.relationship_user.to_dict(),
            "relationships": {k: v.to_dict() for k, v in self.relationships.items()},
            "mood_valence": round(self.mood_valence, 3),
            "energy": round(self.energy, 3),
            "activity": self.activity, "activity_with": self.activity_with,
            "last_active": self.last_active, "created": self.created,
            "conversation": list(self.conversation)[-20:],
        }

    @classmethod
    def from_dict(cls, data):
        try:
            f = cls(data.get("name", "Friend"), fid=data.get("id"))
            f.personality.from_dict(data.get("personality", {}))
            f.interests = list(data.get("interests", []) or [])
            mem_data = data.get("memory")
            if mem_data:
                f.memory.import_dict(mem_data, merge=True, persist=False)
            f.relationship_user.from_dict(data.get("relationship_user", {}))
            rels = data.get("relationships", {})
            if isinstance(rels, dict):
                for k, v in rels.items():
                    r = Relationship()
                    r.from_dict(v)
                    f.relationships[k] = r
            f.mood_valence = float(data.get("mood_valence", 0.1) or 0.1)
            f.energy = clamp01(float(data.get("energy", 0.8) or 0.8))
            f.activity = data.get("activity", "idle") or "idle"
            f.activity_with = data.get("activity_with")
            f.last_active = float(data.get("last_active", time.time()) or time.time())
            f.created = float(data.get("created", time.time()) or time.time())
            for row in data.get("conversation", []) or []:
                if isinstance(row, dict):
                    f.conversation.append(row)
            return f
        except Exception:
            traceback.print_exc()
            return None
