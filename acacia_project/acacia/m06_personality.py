

# ============================================================================
# [3.6] PERSONALITY  (stable traits that slowly evolve from experience)
# ============================================================================

PERSONALITY_TRAITS = (
    "friendliness", "curiosity", "confidence", "patience", "humour",
    "sociability", "openness", "assertiveness", "empathy", "energy",
)

# plain-language hint per trait at each extreme - the LLM and UI only ever
# see these words, never the raw numbers
_TRAIT_HIGH = {
    "friendliness": "warm", "curiosity": "inquisitive", "confidence": "self-assured",
    "patience": "even-tempered", "humour": "playful", "sociability": "outgoing",
    "openness": "open-minded", "assertiveness": "direct", "empathy": "attentive to feelings",
    "energy": "energetic",
}
_TRAIT_LOW = {
    "friendliness": "reserved", "curiosity": "incurious", "confidence": "unsure of itself",
    "patience": "quick to tire of things", "humour": "serious", "sociability": "solitary",
    "openness": "set in its ways", "assertiveness": "deferential", "empathy": "matter-of-fact",
    "energy": "low-energy",
}


class Personality:
    """A persistent character. Traits only ever move in small, capped steps
    driven by an explicit evaluation of recent experience (see
    Brain._evolve_personality) - never per-tick, never randomly."""

    MAX_NUDGE = 0.035           # hard ceiling per single nudge() call
    LIKE_MAX = 3.0

    def __init__(self, seed=None):
        rng = random.Random(seed) if seed is not None else random
        # a little natural variation at birth, stable from then on
        self.traits = {t: clamp01(0.5 + rng.uniform(-0.16, 0.16)) for t in PERSONALITY_TRAITS}
        self.likes = {}             # topic -> strength (derived from experience + manual)
        self.dislikes = {}
        self.values = []            # short, user/self-authored statements
        self.habits = []
        self.opinions = {}          # topic -> one-line stance
        self.evolution_log = deque(maxlen=20)     # (t, trait, delta, reason)
        # rolled once, at birth, and never again - this is what makes the
        # creature's body its OWN body across restarts instead of a new
        # random shape every time the app happens to launch
        self.body_seed = rng.randint(1, 2 ** 31 - 1)

    # -- persistence -----------------------------------------------------
    def to_dict(self):
        return {
            "traits": {k: round(v, 4) for k, v in self.traits.items()},
            "likes": {k: round(v, 3) for k, v in self.likes.items()},
            "dislikes": {k: round(v, 3) for k, v in self.dislikes.items()},
            "values": list(self.values)[:24],
            "habits": list(self.habits)[:24],
            "opinions": dict(list(self.opinions.items())[:24]),
            "evolution_log": [list(row) for row in list(self.evolution_log)],
            "body_seed": self.body_seed,
        }

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        traits = data.get("traits")
        if isinstance(traits, dict):
            for t in PERSONALITY_TRAITS:
                if isinstance(traits.get(t), (int, float)):
                    self.traits[t] = clamp01(float(traits[t]))
        if isinstance(data.get("body_seed"), int):
            self.body_seed = data["body_seed"]
        for field in ("likes", "dislikes"):
            val = data.get(field)
            if isinstance(val, dict):
                bucket = getattr(self, field)
                for k, v in val.items():
                    try:
                        bucket[str(k)] = float(v)
                    except Exception:
                        pass
        for field in ("values", "habits"):
            val = data.get(field)
            if isinstance(val, list):
                setattr(self, field, [str(x) for x in val][:24])
        opinions = data.get("opinions")
        if isinstance(opinions, dict):
            self.opinions = {str(k): str(v) for k, v in opinions.items()}
        for row in data.get("evolution_log", []) or []:
            if isinstance(row, (list, tuple)) and len(row) == 4:
                self.evolution_log.append(tuple(row))

    # -- evolution -------------------------------------------------------
    def nudge(self, trait, delta, reason=""):
        """The ONLY way a trait changes - hard-capped per call, so nothing
        else in the app can make the personality swing wildly."""
        if trait not in self.traits:
            return
        delta = clamp(delta, -self.MAX_NUDGE, self.MAX_NUDGE)
        before = self.traits[trait]
        self.traits[trait] = clamp01(before + delta)
        if abs(self.traits[trait] - before) >= 0.004:
            self.evolution_log.append((time.time(), trait, round(delta, 4), reason))

    def note_like(self, topic, strength=0.15):
        if not topic:
            return
        self.likes[topic] = min(self.LIKE_MAX, self.likes.get(topic, 0.0) + strength)
        self.dislikes.pop(topic, None)

    def note_dislike(self, topic, strength=0.15):
        if not topic:
            return
        self.dislikes[topic] = min(self.LIKE_MAX, self.dislikes.get(topic, 0.0) + strength)
        self.likes.pop(topic, None)

    def top_likes(self, n=5):
        return [k for k, _ in sorted(self.likes.items(), key=lambda kv: -kv[1])[:n]]

    def top_dislikes(self, n=5):
        return [k for k, _ in sorted(self.dislikes.items(), key=lambda kv: -kv[1])[:n]]

    # -- read-out ----------------------------------------------------
    def descriptors(self, n=4):
        """The n most distinctive traits (furthest from neutral 0.5), each
        rendered as a plain-language adjective - never a raw number."""
        ranked = sorted(self.traits.items(), key=lambda kv: -abs(kv[1] - 0.5))
        out = []
        for trait, value in ranked[:n]:
            table = _TRAIT_HIGH if value >= 0.5 else _TRAIT_LOW
            out.append(table.get(trait, trait))
        return out

    def style_descriptor(self):
        return ", ".join(self.descriptors(3)) or "even-keeled, still forming a personality"

    def summary_line(self):
        bits = [self.style_descriptor()]
        if self.top_likes(3):
            bits.append("likes " + ", ".join(self.top_likes(3)))
        if self.top_dislikes(2):
            bits.append("dislikes " + ", ".join(self.top_dislikes(2)))
        return " · ".join(bits)

    def prompt_block(self):
        """Compact personality section for an LLM system prompt - plain
        language, no raw trait numbers, no internal bookkeeping."""
        lines = [f"personality: {self.style_descriptor()}"]
        if self.top_likes(4):
            lines.append("likes: " + ", ".join(self.top_likes(4)))
        if self.top_dislikes(3):
            lines.append("dislikes: " + ", ".join(self.top_dislikes(3)))
        if self.values:
            lines.append("values: " + ", ".join(self.values[:4]))
        if self.habits:
            lines.append("habits: " + ", ".join(self.habits[:3]))
        return "\n".join(lines)
