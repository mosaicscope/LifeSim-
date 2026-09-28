

# ============================================================================
# [3] MEMORY SYSTEM
# ============================================================================

class MemoryItem:
    __slots__ = ("id", "kind", "text", "importance", "created", "last_access",
                 "uses", "keys", "emotion", "valence", "subject",
                 "links", "peak_importance")

    _counter = 0
    MAX_LINKS = 8            # how many associations one memory can hold at once
    LINK_STEP = 0.10         # how much one co-activation strengthens a link

    def __init__(self, kind, text, importance=0.5, emotion="neutral", valence=0.0,
                 created=None, mid=None, keys=None, uses=0, last_access=None,
                 subject="user", links=None, peak_importance=None):
        MemoryItem._counter += 1
        self.id = mid or f"m{int(time.time()*1000)%10**9}_{MemoryItem._counter}"
        self.kind = kind                    # fact | preference | identity | episode |
                                             # instruction | reflection | thought | event
        self.text = text
        self.importance = clamp01(importance)
        self.created = created or time.time()
        self.last_access = last_access or self.created
        self.uses = uses
        self.keys = set(keys) if keys else set(keywords(text, 14))
        self.emotion = emotion
        self.valence = clamp(valence, -1, 1)
        self.subject = subject or "user"    # who this is about - "user" today,
        # ASSOCIATIVE MEMORY: which other memory ids this one tends to come up
        # alongside, and how strongly - built only from real co-activation
        # (things recalled together, or written in the same turn), never
        # assigned up front. This is what lets one memory pull a related one
        # into recall even when the query text doesn't overlap with it.
        self.links = dict(links) if links else {}
        # highest importance this memory ever reached - kept so that, if it
        # eventually decays away, whether losing it was actually significant
        # can still be judged honestly (importance itself has by then decayed).
        self.peak_importance = clamp01(peak_importance if peak_importance is not None
                                       else self.importance)

    def link(self, other_id, step=None):
        """Strengthen (or create) an association toward another memory.
        Capped per-link and in total count, same hard-cap philosophy as
        Personality/Relationship nudges - association can never explode."""
        if not other_id or other_id == self.id:
            return
        step = self.LINK_STEP if step is None else step
        cur = self.links.get(other_id, 0.0)
        self.links[other_id] = clamp01(cur + step)
        if len(self.links) > self.MAX_LINKS:
            weakest = min(self.links.items(), key=lambda kv: kv[1])[0]
            if weakest != other_id:
                del self.links[weakest]

    def to_dict(self):
        return {
            "id": self.id, "kind": self.kind, "text": self.text,
            "importance": round(self.importance, 3), "created": self.created,
            "last_access": self.last_access, "uses": self.uses,
            "keys": sorted(self.keys), "emotion": self.emotion,
            "valence": round(self.valence, 3), "subject": self.subject,
            "links": {k: round(v, 3) for k, v in self.links.items()},
            "peak_importance": round(self.peak_importance, 3),
        }

    @staticmethod
    def from_dict(d):
        try:
            return MemoryItem(
                d.get("kind", "episode"), d.get("text", ""),
                importance=float(d.get("importance", 0.5)),
                emotion=d.get("emotion", "neutral"),
                valence=float(d.get("valence", 0.0)),
                created=float(d.get("created", time.time())),
                mid=d.get("id"), keys=d.get("keys"),
                uses=int(d.get("uses", 0)),
                last_access=float(d.get("last_access", time.time())),
                subject=d.get("subject", "user"),
                links=d.get("links"),
                peak_importance=float(d.get("peak_importance", d.get("importance", 0.5))),
            )
        except Exception:
            return None

    def strength(self, now=None):
        """Retention score: important, recently used and frequently used
        memories survive consolidation; trivia decays away."""
        now = now or time.time()
        age_days = (now - self.created) / 86400.0
        recency = math.exp(-(now - self.last_access) / (86400.0 * 3.0))
        return clamp01(0.62 * self.importance + 0.25 * recency
                       + 0.13 * clamp01(self.uses / 6.0) - 0.04 * clamp01(age_days / 30.0))


class MemorySystem:
    """Short-term (recent turns + events + context) and long-term
    (importance-scored, consolidated, pruned, persisted)."""

    STM_TURNS = 24
    STM_EVENTS = 40
    LTM_MAX = 320
    PROMOTE_THRESHOLD = 0.55

    def __init__(self):
        self.turns = deque(maxlen=self.STM_TURNS)     # {role, text, t, emotion}
        self.events = deque(maxlen=self.STM_EVENTS)   # {kind, text, t, salience}
        self.context = ""                              # what we're talking about
        self.long_term = []                            # [MemoryItem]
        self.total_messages = 0
        self.sessions = 0
        self.first_seen = time.time()
        self.contradictions = 0
        self._lock = threading.RLock()
        self.dirty = False

    # -- persistence ---------------------------------------------------
    def load(self):
        data = load_json(MEMORY_FILE, {})
        if not isinstance(data, dict):
            return
        items = []
        for raw in data.get("long_term", [])[: self.LTM_MAX * 2]:
            item = MemoryItem.from_dict(raw)
            if item and item.text:
                items.append(item)
        self.long_term = items
        self.total_messages = int(data.get("total_messages", 0) or 0)
        self.sessions = int(data.get("sessions", 0) or 0) + 1
        self.first_seen = float(data.get("first_seen", time.time()) or time.time())
        self.contradictions = int(data.get("contradictions", 0) or 0)
        for turn in data.get("recent_turns", [])[-self.STM_TURNS:]:
            if isinstance(turn, dict) and turn.get("text"):
                self.turns.append(turn)
        self.context = data.get("context", "") or ""

    def save(self):
        with self._lock:
            data = {
                "long_term": [m.to_dict() for m in self.long_term],
                "recent_turns": list(self.turns)[-12:],
                "context": self.context,
                "total_messages": self.total_messages,
                "sessions": self.sessions,
                "first_seen": self.first_seen,
                "contradictions": self.contradictions,
                "saved_at": time.time(),
            }
        ok = save_json(MEMORY_FILE, data)
        self.dirty = not ok
        return ok

    # -- short term ----------------------------------------------------
    def add_turn(self, role, text, emotion="neutral"):
        with self._lock:
            self.turns.append({"role": role, "text": text, "t": time.time(),
                               "emotion": emotion})
            self.total_messages += 1

    def add_event(self, kind, text, salience=0.3):
        with self._lock:
            self.events.append({"kind": kind, "text": text, "t": time.time(),
                                "salience": clamp01(salience)})

    def set_context(self, topic):
        if topic:
            self.context = topic[:120]

    def recent_turns(self, n=8):
        with self._lock:
            return list(self.turns)[-n:]

    def recent_events(self, n=6):
        with self._lock:
            return list(self.events)[-n:]

    # -- long term -----------------------------------------------------
    def remember(self, kind, text, importance=0.5, emotion="neutral", valence=0.0,
                subject="user"):
        """Store only if it clears the bar and isn't a near-duplicate.
        Detects contradictions (e.g. a new 'dislikes X' vs an existing
        'likes X' with the same subject) and supersedes the old memory
        instead of silently merging into it."""
        text = (text or "").strip()
        if len(text) < 4 or importance < 0.3:
            return None
        with self._lock:
            new_keys = set(keywords(text, 14))
            new_pol = text_polarity(text)
            for item in self.long_term:
                if item.subject != subject:
                    continue
                if item.text.lower() == text.lower():
                    item.importance = clamp01(max(item.importance, importance) + 0.05)
                    item.peak_importance = max(item.peak_importance, item.importance)
                    item.last_access = time.time()
                    item.uses += 1
                    return item
                if new_keys and item.kind == kind:
                    overlap = len(new_keys & item.keys) / max(1, len(new_keys | item.keys))
                    item_pol = text_polarity(item.text)
                    if new_pol and item_pol and new_pol != item_pol and overlap >= 0.3:
                        # contradiction: fade the old belief rather than merge -
                        # both stay visible in the viewer, but only the new one
                        # is strong enough to be retrieved or trusted
                        item.importance = clamp01(item.importance * 0.2)
                        if "(may no longer be true)" not in item.text:
                            item.text = f"(may no longer be true) {item.text}"
                        item.last_access = time.time()
                        self.contradictions += 1
                        break
                    if overlap > 0.72:
                        # near-duplicate: refine the existing memory instead
                        if importance >= item.importance:
                            item.text = text
                            item.keys = new_keys
                        item.importance = clamp01(max(item.importance, importance) + 0.03)
                        item.peak_importance = max(item.peak_importance, item.importance)
                        item.last_access = time.time()
                        item.uses += 1
                        return item
            item = MemoryItem(kind, text, importance, emotion, valence, subject=subject)
            self.long_term.append(item)
            self._prune()
            return item

    def _prune(self):
        if len(self.long_term) <= self.LTM_MAX:
            return
        now = time.time()
        self.long_term.sort(key=lambda m: m.strength(now), reverse=True)
        del self.long_term[self.LTM_MAX:]

    def recall(self, query, limit=5, min_score=0.12, emotion_system=None, context_bias=None):
        """Relevance = keyword overlap x importance x recency x context x mood,
        plus one hop of ASSOCIATIVE SPREADING from whatever that scoring
        already surfaces - so a memory with no direct textual overlap with
        the query can still come up because it keeps co-occurring with
        something that does. `emotion_system` and `context_bias` are both
        optional (Friend recall calls this without either) so nothing that
        already calls recall() needs to change."""
        qk = set(keywords(query, 16))
        ctx_kw = set(keywords(context_bias, 10)) if context_bias else set()
        now = time.time()
        direct = []          # (score, item) from real query/context/mood match
        by_id = {}
        with self._lock:
            for item in self.long_term:
                by_id[item.id] = item
                overlap = len(qk & item.keys)
                sim = overlap / max(1, len(qk | item.keys)) if qk else 0.0
                recency = math.exp(-(now - item.last_access) / (86400.0 * 5.0))
                score = 0.55 * sim + 0.27 * item.importance + 0.10 * recency
                if item.kind in ("identity", "instruction"):
                    score += 0.22           # always keep who-you-are facts near
                if ctx_kw:
                    # CONTEXTUAL RECALL: bias toward whatever the ongoing
                    # conversation topic already is, not only this message's
                    # literal words - self.context is set every turn but,
                    # before this, was never actually read back.
                    c_overlap = len(ctx_kw & item.keys) / max(1, len(ctx_kw | item.keys))
                    score += 0.14 * c_overlap
                if emotion_system is not None:
                    # MOOD-CONGRUENT RECALL: a real, small bias toward memories
                    # whose stored emotional valence matches how it feels right
                    # now - capped low so it colours retrieval, never hijacks it.
                    closeness = 1.0 - min(2.0, abs(item.valence - emotion_system.valence)) / 2.0
                    score += 0.07 * closeness
                if score >= min_score:
                    direct.append((score, item))
            direct.sort(key=lambda p: p[0], reverse=True)

            # ASSOCIATIVE SPREADING: one hop out from the strongest direct
            # hits, along links built from real past co-activation. A linked
            # memory that scored below min_score on its own can still surface
            # if it keeps coming up alongside something that clearly matches.
            seen_ids = {it.id for _, it in direct}
            spread = []
            for base_score, item in direct[:3]:
                for linked_id, weight in item.links.items():
                    if linked_id in seen_ids:
                        continue
                    target = by_id.get(linked_id)
                    if not target:
                        continue
                    spread.append((0.30 * weight * base_score, target))
                    seen_ids.add(linked_id)

            pool = direct + spread
            pool.sort(key=lambda p: p[0], reverse=True)
            picked = [it for _, it in pool[:limit]]

            for item in picked:
                item.uses += 1
                item.last_access = now
            # REINFORCEMENT: things recalled together become associated with
            # each other a little more, purely from co-activation - the same
            # "fire together, wire together" rule the dreaming/consolidation
            # pass already uses when it merges near-duplicate memories.
            for a in picked:
                for b in picked:
                    if a is not b:
                        a.link(b.id)
        return picked

    def consolidate(self, perception, emotion_system, response_text=""):
        """Runs AFTER a conversational turn: decides what is worth keeping.
        Importance is boosted by emotional arousal (like real encoding)."""
        stored = []
        arousal_boost = 0.18 * emotion_system.intensity + 0.12 * abs(emotion_system.valence)
        for kind, phrase, base in Perception.extract_facts(perception["text"]):
            stored.append(self.remember(kind, phrase,
                                        importance=clamp01(base + 0.05 * arousal_boost),
                                        emotion=emotion_system.emotion,
                                        valence=emotion_system.valence))
        salience = perception["salience"] + arousal_boost
        if salience >= self.PROMOTE_THRESHOLD and perception["words"] >= 4:
            snippet = perception["text"]
            if len(snippet) > 150:
                snippet = snippet[:147] + "..."
            stored.append(self.remember(
                "episode", f"the user said: {snippet}",
                importance=clamp01(0.35 + 0.45 * salience),
                emotion=emotion_system.emotion, valence=emotion_system.valence))
        if perception["keywords"]:
            self.set_context(", ".join(perception["keywords"][:5]))
        stored = [s for s in stored if s]
        # ASSOCIATION AT ENCODING TIME: things learned in the same breath get
        # a real (if light) link from the start, not only once they happen to
        # be recalled together later.
        with self._lock:
            for a in stored:
                for b in stored:
                    if a is not b:
                        a.link(b.id, step=0.06)
        return stored

    # -- maintenance ---------------------------------------------------
    def decay(self):
        """Called occasionally: weak memories fade, strong ones persist.
        Returns the list of memories actually dropped this pass (not just a
        count) so the brain can react honestly when something that once
        mattered is finally gone - forgetting is a real event here, not a
        silent deletion. Any surviving links pointing at a dropped memory
        are cleaned up too, so association data never points at a ghost."""
        now = time.time()
        with self._lock:
            for item in self.long_term:
                if now - item.last_access > 86400 * 2:
                    item.importance = clamp01(item.importance - 0.01)
            kept, dropped = [], []
            for m in self.long_term:
                if m.importance > 0.18 or m.kind in ("identity", "instruction"):
                    kept.append(m)
                else:
                    dropped.append(m)
            if dropped:
                dropped_ids = {m.id for m in dropped}
                for m in kept:
                    for did in dropped_ids & set(m.links):
                        del m.links[did]
            self.long_term = kept
            return dropped

    def clear_short_term(self):
        with self._lock:
            self.turns.clear()
            self.events.clear()
            self.context = ""

    def clear_long_term(self):
        with self._lock:
            self.long_term = []
        self.save()

    def forget(self, mem_id):
        with self._lock:
            self.long_term = [m for m in self.long_term if m.id != mem_id]
        self.save()

    def edit(self, mem_id, text=None, importance=None, kind=None):
        """Manual correction from the memory viewer - lets a person fix or
        annotate what the creature believes, rather than only delete it."""
        with self._lock:
            for item in self.long_term:
                if item.id != mem_id:
                    continue
                if text is not None and text.strip():
                    item.text = text.strip()
                    item.keys = set(keywords(item.text, 14))
                if importance is not None:
                    item.importance = clamp01(importance)
                if kind is not None and kind.strip():
                    item.kind = kind.strip()
                item.last_access = time.time()
                self.save()
                return item
        return None

    def export_dict(self):
        """A portable snapshot of everything long-term - used by the EXPORT
        button and, later, by save-to-file / share-a-character features."""
        with self._lock:
            return {
                "format": "creature_memory_export", "version": 1,
                "exported_at": time.time(),
                "long_term": [m.to_dict() for m in self.long_term],
                "total_messages": self.total_messages,
                "sessions": self.sessions,
                "first_seen": self.first_seen,
            }

    def import_dict(self, data, merge=True, persist=True):
        """Merge (default) or replace long-term memory from an exported
        dict. Goes back through remember() item by item, so the same
        dedup/contradiction handling applies to imported memories as to
        ones formed in conversation - an import is just many small
        'rememberings' at once. Returns the number of items added/merged.
        persist=False is used when this MemorySystem belongs to a Friend
        and is serialized as part of friends.json instead of memory.json."""
        if not isinstance(data, dict):
            return 0
        items = data.get("long_term", [])
        if not isinstance(items, list):
            return 0
        if not merge:
            with self._lock:
                self.long_term = []
        added = 0
        for raw in items:
            if not isinstance(raw, dict):
                continue
            text = (raw.get("text") or "").strip()
            if not text:
                continue
            try:
                result = self.remember(
                    raw.get("kind", "episode"), text,
                    importance=float(raw.get("importance", 0.5) or 0.5),
                    emotion=raw.get("emotion", "neutral"),
                    valence=float(raw.get("valence", 0.0) or 0.0),
                    subject=raw.get("subject", "user"))
            except Exception:
                result = None
            if result:
                added += 1
        if persist:
            self.save()
        return added

    def stats(self):
        with self._lock:
            kinds = {}
            links = 0
            for m in self.long_term:
                kinds[m.kind] = kinds.get(m.kind, 0) + 1
                links += len(m.links)
            return {"stm": len(self.turns), "ltm": len(self.long_term),
                    "kinds": kinds, "messages": self.total_messages,
                    "sessions": self.sessions, "contradictions": self.contradictions,
                    "associations": links}
