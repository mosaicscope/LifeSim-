

# ============================================================================
# [1] EVENTS + PERCEPTION
# ============================================================================

class Event:
    """Everything that happens to the creature becomes an Event.
    Events are the ONLY way the internal state is perturbed, which is what
    makes every emotional change traceable to a cause."""

    __slots__ = ("kind", "text", "salience", "valence", "data", "t")

    def __init__(self, kind, text="", salience=0.3, valence=0.0, **data):
        self.kind = kind
        self.text = text
        self.salience = clamp01(salience)
        self.valence = clamp(valence, -1.0, 1.0)
        self.data = data
        self.t = time.time()

    def __repr__(self):
        return f"<Event {self.kind} sal={self.salience:.2f} val={self.valence:+.2f}>"


POSITIVE_WORDS = {
    "thanks", "thank", "love", "great", "good", "nice", "awesome", "amazing",
    "beautiful", "happy", "glad", "well", "cool", "brilliant", "clever",
    "smart", "please", "friend", "yes", "fun", "excellent", "perfect", "proud",
    "wonderful", "sweet", "kind", "enjoy", "like",
}
NEGATIVE_WORDS = {
    "stupid", "hate", "bad", "awful", "terrible", "useless", "wrong", "shut",
    "boring", "annoying", "dumb", "broken", "angry", "sad", "no", "never",
    "worthless", "idiot", "garbage", "fail", "failure", "ugly", "worse",
}
CURIOSITY_WORDS = {
    "why", "how", "what", "who", "where", "when", "imagine", "explain",
    "wonder", "think", "suppose", "curious", "mean", "because",
}

FACT_PATTERNS = [
    (re.compile(r"\bmy name is ([A-Z][\w'-]{1,24})", re.I), "identity", "the user's name is {0}", 0.95),
    (re.compile(r"\bi(?:'m| am) called ([A-Z][\w'-]{1,24})", re.I), "identity", "the user's name is {0}", 0.95),
    (re.compile(r"\byou can call me ([A-Z][\w'-]{1,24})", re.I), "identity", "the user's name is {0}", 0.9),
    (re.compile(r"\bi (?:really )?(?:love|adore)\s+([^.!?,;]{2,60})", re.I), "preference", "the user loves {0}", 0.75),
    (re.compile(r"\bi (?:really )?(?:like|enjoy|prefer)\s+([^.!?,;]{2,60})", re.I), "preference", "the user likes {0}", 0.65),
    (re.compile(r"\bi (?:really )?(?:hate|dislike|can't stand)\s+([^.!?,;]{2,60})", re.I), "preference", "the user dislikes {0}", 0.7),
    (re.compile(r"\bi work (?:as|at|for)\s+(?:an?\s+)?([^.!?,;]{2,60}?)(?=\s+and\b|[.!?,;]|$)", re.I),
     "fact", "the user's work: {0}", 0.7),
    (re.compile(r"\bi live in\s+([^.!?,;]{2,60}?)(?=\s+and\b|[.!?,;]|$)", re.I),
     "fact", "the user lives in {0}", 0.75),
    (re.compile(r"\bi(?:'m| am) (?:a|an)\s+([^.!?,;]{2,50})", re.I), "fact", "the user is {0}", 0.55),
    (re.compile(r"\bmy ([a-z]{3,15}) is ([^.!?,;]{2,50}?)(?=\s+and\b|[.!?,;]|$)", re.I),
     "fact", "the user's {0} is {1}", 0.6),
    (re.compile(r"\bremember (?:that )?([^.!?]{4,90})", re.I), "instruction", "the user asked me to remember: {0}", 0.95),
    (re.compile(r"\byour name is ([A-Z][\w'-]{1,24})", re.I), "identity", "the user calls me {0}", 0.9),
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on", "for",
    "with", "is", "are", "was", "were", "be", "been", "am", "it", "its", "this",
    "that", "these", "those", "i", "you", "he", "she", "we", "they", "me",
    "my", "your", "do", "does", "did", "so", "as", "at", "by", "from", "not",
    "have", "has", "had", "can", "will", "just", "about", "there", "then",
}


def stem(word: str) -> str:
    """Crude suffix stripping - enough for keyword matching between
    'work', 'works' and 'working' without pulling in a dependency."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def keywords(text: str, limit: int = 12):
    words = re.findall(r"[a-z0-9']{3,}", (text or "").lower())
    out = []
    for w in words:
        if w in STOPWORDS:
            continue
        w = stem(w)
        if w in out or len(w) < 3:
            continue
        out.append(w)
        if len(out) >= limit:
            break
    return out


_POS_POLARITY = re.compile(r"\b(likes|loves|enjoys|prefers)\b", re.I)
_NEG_POLARITY = re.compile(r"\b(dislikes|hates|can't stand|doesn't like)\b", re.I)


def text_polarity(text: str) -> int:
    """+1 / -1 / 0 - crude but enough to tell 'likes X' from 'dislikes X'
    so preference memories can be checked for contradictions."""
    if _NEG_POLARITY.search(text or ""):
        return -1
    if _POS_POLARITY.search(text or ""):
        return 1
    return 0


class Perception:
    """Turns raw input (a user message, a world event) into structured
    features the rest of the mind can act on."""

    def __init__(self):
        self._recent_texts = deque(maxlen=12)
        self._recent_raw = deque(maxlen=8)

    def read_message(self, text: str, familiarity: float) -> dict:
        raw = (text or "").strip()
        low = raw.lower()
        tokens = set(re.findall(r"[a-z']+", low))
        n_words = max(1, len(re.findall(r"\w+", raw)))

        pos = len(tokens & POSITIVE_WORDS)
        neg = len(tokens & NEGATIVE_WORDS)
        sentiment = clamp((pos - neg) / 2.5, -1.0, 1.0)

        question = "?" in raw or bool(re.match(r"^(who|what|why|how|when|where|do|does|did|are|is|can|could|would|will|should)\b", low))
        shouting = raw.isupper() and n_words > 1
        exclaim = raw.count("!")

        # novelty: how different is this from what was recently said to us?
        novelty = 1.0
        kws = set(keywords(raw, 16))
        if kws:
            for old in self._recent_texts:
                overlap = len(kws & old) / max(1, len(kws | old))
                novelty = min(novelty, 1.0 - overlap)
        repeated = any(raw.lower() == t for t in self._recent_raw)
        self._recent_texts.append(kws)
        self._recent_raw.append(raw.lower())

        complexity = clamp01(len(kws) / 10.0)
        curious_pull = clamp01(len(tokens & CURIOSITY_WORDS) / 3.0 + (0.3 if question else 0.0))

        salience = clamp01(
            0.25 + 0.3 * novelty + 0.2 * complexity + 0.25 * abs(sentiment)
            + (0.15 if shouting else 0.0) + 0.05 * min(3, exclaim)
        )

        return {
            "text": raw,
            "words": n_words,
            "sentiment": sentiment,
            "question": question,
            "shouting": shouting,
            "novelty": novelty,
            "repeated": repeated,
            "complexity": complexity,
            "curiosity_pull": curious_pull,
            "salience": salience,
            "keywords": sorted(kws),
            "warmth": clamp01(pos / 2.0 + 0.25 * familiarity),
        }

    @staticmethod
    def extract_facts(text: str):
        """Heuristic long-term-memory candidates pulled out of a message."""
        found = []
        for pattern, kind, template, importance in FACT_PATTERNS:
            for match in pattern.finditer(text or ""):
                groups = [g.strip(" .,'\"") for g in match.groups() if g]
                if not groups:
                    continue
                try:
                    phrase = template.format(*groups)
                except Exception:
                    continue
                if len(phrase) > 160:
                    phrase = phrase[:157] + "..."
                found.append((kind, phrase, importance))
        return found

    # ------------------------------------------- [PHASE 55] multimodal
    # ONE interface for perceiving a made thing, whatever medium it is in.
    #
    # Phase 31 measured rendered images into six properties.  Audio and
    # text now report the SAME six, measured honestly from their own
    # material, so everything downstream - embedding (53), affinity,
    # motifs (22/57), novelty, the evaluate/learn loop - works on any
    # modality without knowing which one it is looking at.
    #
    # These are stateless @staticmethods living on the SAME canonical
    # Perception class as the conversational API above, so both
    #     brain.perception.read_message(text, familiarity)
    #     brain.perception.read(thing)   /  Perception.read_audio(...)
    # resolve against one class and nothing can shadow anything.
    MODALITIES = ("image", "audio", "text")

    @staticmethod
    def _blank():
        return {k: 0.5 for k in VisualMemory.FEATURES}

    @staticmethod
    def read_image(engine=None, image=None, features=None):
        """Image perception stays exactly where it was: the engine's own
        pixel measurement. Passed-through features are accepted so a
        recorded work can be re-perceived without re-rendering it."""
        if features:
            return {"modality": "image", "features": dict(features)}
        feats = None
        if engine is not None:
            try:
                feats = engine.read_result(image)
            except Exception:
                feats = None
        return {"modality": "image", "features": feats or Perception._blank()}

    @staticmethod
    def read_audio(samples, rate=22050):
        """Real measurements of the samples, mapped onto the same six:

            energy      mean absolute amplitude
            colour      spectral spread (zero-crossing rate)
            contrast    peak-to-mean dynamic range
            density     onset rate - how often it changes direction sharply
            warmth      low-band share of the signal
            brightness  high-band share

        Deliberately DSP-light: no FFT, no dependency, bounded single pass,
        so this stays cheap enough to run on every rendered clip."""
        n = len(samples or ())
        if not n:
            return {"modality": "audio", "features": Perception._blank()}
        total = peak = 0.0
        crossings = onsets = 0
        prev = float(samples[0])
        prev_d = 0.0
        low = high = 0.0
        for i in range(n):
            v = float(samples[i])
            a = abs(v)
            total += a
            peak = max(peak, a)
            d = v - prev
            if (v >= 0.0) != (prev >= 0.0):
                crossings += 1
            if abs(d) > abs(prev_d) * 2.5 and abs(d) > 0.05:
                onsets += 1
            # a one-pole split is enough to say "mostly low" vs "mostly high"
            low += abs(v + prev) * 0.5
            high += abs(d)
            prev, prev_d = v, d
        mean = total / n
        band = low + high + 1e-9
        return {"modality": "audio", "features": {
            "energy": clamp01(mean * 2.2),
            "colour": clamp01(crossings / n * 8.0),
            "contrast": clamp01((peak - mean) * 1.8),
            "density": clamp01(onsets / n * 60.0),
            "warmth": clamp01(low / band),
            "brightness": clamp01(high / band * 1.5)}}

    @staticmethod
    def read_text(text):
        """A caption measured as text: length, punctuation, lexical variety
        and the warm/cool, bright/dark vocabulary it actually uses. Crude on
        purpose - it is a comparable reading, not a language model."""
        raw = (text or "").strip()
        if not raw:
            return {"modality": "text", "features": Perception._blank()}
        words = re.findall(r"[a-z']+", raw.lower())
        n = max(1, len(words))
        uniq = len(set(words)) / n
        warm_w = {"warm", "gold", "amber", "sun", "fire", "red", "orange", "glow",
                  "soft", "honey", "close", "home"}
        cool_w = {"cold", "blue", "ice", "steel", "night", "grey", "gray", "void",
                  "distant", "chrome", "rain"}
        bright_w = {"bright", "light", "white", "neon", "shine", "flash", "clear"}
        dark_w = {"dark", "black", "shadow", "deep", "dim", "murk", "heavy"}
        hits = lambda bag: sum(1 for w in words if w in bag)
        warm, cool = hits(warm_w), hits(cool_w)
        bright, dark = hits(bright_w), hits(dark_w)
        shouty = (raw.count("!") + sum(1 for c in raw if c.isupper())) / max(1, len(raw))
        return {"modality": "text", "features": {
            "energy": clamp01(shouty * 4.0 + min(0.4, n / 60.0)),
            "colour": clamp01(uniq),
            "contrast": clamp01((warm + cool + bright + dark) / max(3.0, n / 4.0)),
            "density": clamp01(n / 45.0),
            "warmth": clamp01(0.5 + (warm - cool) * 0.18),
            "brightness": clamp01(0.5 + (bright - dark) * 0.18)}}

    @staticmethod
    def read(thing, **kw):
        """Dispatch on what it actually is - the single entry point."""
        if isinstance(thing, str):
            return Perception.read_text(thing)
        if isinstance(thing, (list, tuple)) or (
                globals().get("np") is not None and hasattr(thing, "dtype")):
            return Perception.read_audio(thing, **kw)
        return Perception.read_image(image=thing, **kw)

    @staticmethod
    def coherence(a, b):
        """-> 0..1: do these two readings describe the same piece? Uses the
        shared embedding's feature block, so 'does the sound match the
        visual' and 'does the caption match the piece' are the same
        question asked twice."""
        if not a or not b:
            return 0.0
        va = {"feat": CreativeEmbedding._feat_vector(a.get("features")), "fam": []}
        vb = {"feat": CreativeEmbedding._feat_vector(b.get("features")), "fam": []}
        return CreativeEmbedding.similarity(va, vb)
