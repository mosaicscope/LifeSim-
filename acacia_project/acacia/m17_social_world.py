

# ============================================================================
# [8.5] SOCIAL WORLD  (friends + friend-to-friend interactions)
# ============================================================================
#
# Performance/behaviour contract, straight from the spec:
#   - friends are NOT full Brain instances - no spiking net, no 10Hz emotion
#     tick. Their state is a handful of scalars updated only on events.
#   - friend-to-friend interactions are rare, cooldown-gated, LLM-backed
#     events (a short exchange, not an endless conversation) - never a
#     continuous background simulation.
#   - SocialWorld.tick() is cheap and safe to call every brain tick; the
#     actual LLM work only ever happens inside run_interaction(), which the
#     app layer calls from a worker thread.

SEED_TOPICS = ["music", "food", "the weather", "a book", "a game", "travel",
              "a dream from last night", "a hobby", "the news", "art", "a joke",
              "something that happened recently"]


class SocialWorld:
    """Owns every Friend and the relationships between them."""

    MAX_EXCHANGE_TURNS = 3          # a short exchange, never an endless one

    def __init__(self, settings: Settings):
        self.settings = settings
        self.friends = {}                      # id -> Friend
        self.friend_relationships = {}         # "idA|idB" -> Relationship
        self.last_interaction_t = 0.0
        self.wants_interaction = False
        self.pending_pair = None
        self._activity_accum = 0.0
        self.recent_log = deque(maxlen=30)     # (t, text) for the Friends tab feed
        self.load()

    # -- persistence -------------------------------------------------
    def load(self):
        data = load_json(FRIENDS_FILE, {})
        if not isinstance(data, dict):
            return
        for raw in data.get("friends", []) or []:
            f = Friend.from_dict(raw)
            if f:
                self.friends[f.id] = f
        rels = data.get("friend_relationships", {})
        if isinstance(rels, dict):
            for key, val in rels.items():
                r = Relationship()
                r.from_dict(val)
                self.friend_relationships[key] = r
        self.last_interaction_t = float(data.get("last_interaction_t", 0.0) or 0.0)
        for row in data.get("recent_log", []) or []:
            if isinstance(row, (list, tuple)) and len(row) == 2:
                self.recent_log.append(tuple(row))

    def save(self):
        data = {
            "friends": [f.to_dict() for f in self.friends.values()],
            "friend_relationships": {k: v.to_dict()
                                     for k, v in self.friend_relationships.items()},
            "last_interaction_t": self.last_interaction_t,
            "recent_log": [list(row) for row in list(self.recent_log)],
            "saved_at": time.time(),
        }
        return save_json(FRIENDS_FILE, data)

    # -- roster management ---------------------------------------------
    def add_friend(self, name, interests=None, seed=None):
        f = Friend(name, seed=seed, interests=interests)
        self.friends[f.id] = f
        self.save()
        return f

    def remove_friend(self, fid):
        self.friends.pop(fid, None)
        self.friend_relationships = {k: v for k, v in self.friend_relationships.items()
                                     if fid not in k.split("|")}
        for f in self.friends.values():
            f.relationships.pop(fid, None)
        self.save()

    @staticmethod
    def pair_key(a, b):
        return "|".join(sorted([a, b]))

    def relationship_between(self, a, b):
        key = self.pair_key(a, b)
        if key not in self.friend_relationships:
            self.friend_relationships[key] = Relationship()
        return self.friend_relationships[key]

    # -- cheap tick: activity cycling + cooldown-gated trigger only -------
    def tick(self, dt, social_enabled=True):
        self._activity_accum += dt
        if self._activity_accum > 25.0:
            self._activity_accum = 0.0
            for f in self.friends.values():
                if f.activity in FRIEND_ACTIVITIES and random.random() < 0.4:
                    f.activity = random.choice(FRIEND_ACTIVITIES)
                    f.activity_with = None

        if not social_enabled or len(self.friends) < 2 or self.wants_interaction:
            return
        now = time.time()
        min_gap = float(self.settings.get("social_min_gap_seconds", 480) or 480)
        # still rare even once the cooldown has elapsed - a small per-second
        # chance, not an immediate trigger the instant the gap is satisfied
        if random.random() > 0.05 * dt:
            return
        # [PHASE 59] the gap itself is the arbiter's call. SocialWorld has no
        # brain reference, so the host attaches one; without it this falls
        # back to the timestamp check it always used.
        att = getattr(self, "attention", None)
        if att is not None:
            if not att.request("social", importance=0.45, min_gap=min_gap):
                return
        elif now - self.last_interaction_t < min_gap:
            return
        a, b = self.choose_pair()
        if not a or not b:
            return
        self.wants_interaction = True
        self.pending_pair = (a, b)

    # ------------------------------------------- [PHASE 58] the social graph
    # Friend-to-Friend Relationships already existed and already moved under
    # the same MAX_NUDGE cap as everything else; what was missing was any
    # READING of them as a graph. Nothing below writes a relationship - it
    # only draws on the ones real interactions produced.

    def edges(self, min_interactions=0):
        """-> [(id_a, id_b, Relationship)] for pairs that really interacted."""
        out = []
        for key, rel in self.friend_relationships.items():
            ids = key.split("|")
            if len(ids) != 2 or not all(i in self.friends for i in ids):
                continue
            if rel.interactions < min_interactions:
                continue
            out.append((ids[0], ids[1], rel))
        return out

    @staticmethod
    def edge_strength(rel):
        """One bounded 0..1 number for how strong a tie is, from the
        dimensions Relationship already tracks. Tension subtracts."""
        return clamp01(0.35 * rel.familiarity + 0.25 * rel.trust +
                       0.25 * rel.affection + 0.20 * rel.compatibility -
                       0.30 * rel.tension)

    def closest_to(self, fid, limit=3, min_interactions=1):
        out = []
        for a, b, rel in self.edges(min_interactions):
            if fid not in (a, b):
                continue
            other = b if a == fid else a
            out.append((self.edge_strength(rel), other))
        out.sort(reverse=True)
        return [(self.friends[o].name, round(s, 2)) for s, o in out[:limit]
                if o in self.friends]

    def tensest(self, limit=3, min_interactions=1):
        out = [(rel.tension, a, b) for a, b, rel in self.edges(min_interactions)
               if rel.tension > 0.15]
        out.sort(reverse=True)
        return [(self.friends[a].name, self.friends[b].name, round(t, 2))
                for t, a, b in out[:limit] if a in self.friends and b in self.friends]

    def collaboration_pairs(self, limit=3, min_interactions=2):
        """[PHASE 58 -> 33] Who would actually work well together: strong
        tie, low tension, and at least one shared interest. Evidence-based,
        so an unevidenced pair never surfaces as a good collaboration."""
        out = []
        for a, b, rel in self.edges(min_interactions):
            fa, fb = self.friends.get(a), self.friends.get(b)
            if not fa or not fb:
                continue
            shared = sorted(set(fa.interests or ()) & set(fb.interests or ()))
            if not shared or rel.tension > 0.4:
                continue
            fit = clamp01(self.edge_strength(rel) * 0.75 +
                          min(0.25, 0.08 * len(shared)))
            out.append((round(fit, 2), fa.name, fb.name, shared[:3]))
        out.sort(reverse=True)
        return out[:limit]

    def choose_pair(self):
        """Who talks to whom next. Weighted by tie strength AND by how long
        it has been since that pair last spoke, so the graph keeps its shape
        without the same two friends monopolising it. Falls back to the
        uniform draw this replaced when there is nothing to go on."""
        ids = list(self.friends.keys())
        if len(ids) < 2:
            return None, None
        now = time.time()
        weighted = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                rel = self.friend_relationships.get(self.pair_key(ids[i], ids[j]))
                if rel is None:
                    weight = 0.5                    # unmet pairs stay plausible
                else:
                    idle = clamp01((now - getattr(rel, "last_t", 0.0)) / 86400.0)
                    weight = 0.15 + self.edge_strength(rel) * 0.85 + idle * 0.5
                weighted.append((max(0.01, weight), ids[i], ids[j]))
        total = sum(w for w, _a, _b in weighted)
        if total <= 0:
            return tuple(random.sample(ids, 2))
        pick = random.uniform(0.0, total)
        for w, a, b in weighted:
            pick -= w
            if pick <= 0:
                return a, b
        return weighted[-1][1], weighted[-1][2]

    def graph_report(self):
        """-> [str] real lines about the real graph, for the Friends tab."""
        lines = []
        for fid, f in self.friends.items():
            close = self.closest_to(fid)
            if close:
                lines.append(f"{f.name} is closest to " +
                             ", ".join(f"{n} ({s:.2f})" for n, s in close))
        for a, b, t in self.tensest():
            lines.append(f"{a} and {b} are strained ({t:.2f} tension)")
        for fit, a, b, shared in self.collaboration_pairs():
            lines.append(f"{a} + {b} would work well together ({fit:.2f}) "
                         f"- shared: {', '.join(shared)}")
        return lines

    # -- triggered friend-to-friend pipeline (LLM-backed) -----------------
    # CHARACTER A -> perception -> personality+emotion+memory -> LLM ->
    # ACTION -> CHARACTER B -> perception -> response -> relationship update.
    # Synchronous: the app layer runs this on a worker thread.
    def run_interaction(self, models: "ModelManager", pair=None):
        a_id, b_id = pair or self.pending_pair or (None, None)
        a, b = self.friends.get(a_id), self.friends.get(b_id)
        self.wants_interaction = False
        self.pending_pair = None
        self.last_interaction_t = time.time()
        if not a or not b:
            return None
        rel = self.relationship_between(a.id, b.id)
        shared = set(a.interests) & set(b.interests)
        topic = random.choice(list(shared)) if shared else random.choice(SEED_TOPICS)

        lines = []
        speaker, listener = a, b
        opener = "(start talking)"
        for _turn in range(self.MAX_EXCHANGE_TURNS):
            system = self._character_system(speaker, listener, rel, topic, lines)
            messages = [{"role": "user", "content": opener}]
            text, err = models.generate(system, messages, 90, lambda _p: None,
                                        threading.Event())
            if err or not text:
                break
            text = text.strip()
            lines.append((speaker.name, text))
            speaker.conversation.append({"role": speaker.name, "text": text, "t": time.time()})
            opener = text
            speaker, listener = listener, speaker

        if not lines:
            return None
        rel.last_t = time.time()          # [PHASE 58] graph edge freshness
        self._apply_outcome(a, b, rel, topic, lines)
        self.recent_log.append((time.time(), f"{a.name} and {b.name} talked about {topic}"))
        self.save()
        return {"topic": topic, "lines": lines, "a": a.name, "b": b.name}

    def _character_system(self, speaker, listener, rel, topic, lines_so_far):
        p = speaker.personality
        lines = [
            f"You are {speaker.name}, talking with {listener.name}, someone you know.",
            f"Your personality: {p.style_descriptor()}.",
        ]
        if p.top_likes(3):
            lines.append(f"You like: {', '.join(p.top_likes(3))}.")
        lines.append(f"How you feel about {listener.name}: {rel.summary()}.")
        lines.append(f"The topic right now: {topic}.")
        if lines_so_far:
            lines.append("Conversation so far:")
            for name, text in lines_so_far[-4:]:
                lines.append(f"  {name}: {text}")
        lines.append("Reply with ONE short, natural line of dialogue (max ~30 words). "
                     "Just the line - no quotes, no stage directions, no name prefix.")
        return "\n".join(lines)

    def _apply_outcome(self, a, b, rel, topic, lines):
        """Cheap heuristic sentiment on the generated lines (no extra LLM
        call) drives the relationship + memory updates."""
        joined = " ".join(text for _, text in lines).lower()
        pos = sum(1 for w in POSITIVE_WORDS if w in joined)
        neg = sum(1 for w in NEGATIVE_WORDS if w in joined)
        warmth = clamp(0.04 * (pos - neg), -0.05, 0.05)
        rel.nudge("familiarity", 0.03)
        rel.nudge("trust", warmth)
        rel.nudge("affection", warmth)
        rel.nudge("tension", max(0.0, -warmth))
        rel.nudge("compatibility", 0.01 if warmth >= 0 else -0.01)
        a.memory.remember("relationship", f"talked with {b.name} about {topic}",
                          importance=0.45, subject=b.name)
        b.memory.remember("relationship", f"talked with {a.name} about {topic}",
                          importance=0.45, subject=a.name)
        a.mood_valence = clamp(a.mood_valence + warmth, -1, 1)
        b.mood_valence = clamp(b.mood_valence + warmth, -1, 1)
        a.activity = b.activity = "interacting with another friend"
        a.activity_with, b.activity_with = b.name, a.name
        a.last_active = b.last_active = time.time()

    # -- 1:1 friend <-> user chat (lighter than the main Brain pipeline) --
    def build_friend_chat_prompt(self, friend: "Friend", user_text: str):
        p = friend.personality
        rel = friend.relationship_user
        recalled = friend.memory.recall(user_text, limit=4)
        lines = [
            f"You are {friend.name}, a character with your own personality - not an assistant.",
            p.prompt_block(),
            f"relationship with the person you're talking to: {rel.summary()}",
        ]
        if recalled:
            lines.append("what you remember about them (use only where it fits):")
            for item in recalled:
                lines.append(f"- {item.text}")
        lines.append("Talk in character, 1-3 sentences, first person. No stage directions, "
                     "no narrating your own feelings - just speak.")
        system = "\n".join(lines)
        messages = []
        for turn in list(friend.conversation)[-8:]:
            role = "user" if turn.get("role") == "user" else "assistant"
            text = (turn.get("text") or "").strip()
            if not text:
                continue
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"] += "\n" + text
            else:
                messages.append({"role": role, "content": text})
        messages.append({"role": "user", "content": user_text})
        return system, messages

    def on_friend_user_message(self, friend: "Friend", text):
        friend.conversation.append({"role": "user", "text": text, "t": time.time()})
        friend.relationship_user.nudge("familiarity", 0.01)
        low = text.lower()
        pos = any(w in low for w in POSITIVE_WORDS)
        neg = any(w in low for w in NEGATIVE_WORDS)
        if pos and not neg:
            friend.relationship_user.nudge("affection", 0.02)
            friend.relationship_user.nudge("trust", 0.015)
        elif neg and not pos:
            friend.relationship_user.nudge("tension", 0.03)
        for kind, phrase, base in Perception.extract_facts(text):
            friend.memory.remember(kind, phrase, importance=base, subject="user")

    def on_friend_response(self, friend: "Friend", text):
        friend.conversation.append({"role": friend.name, "text": text, "t": time.time()})
        friend.last_active = time.time()
        self.save()
