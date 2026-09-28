
# ============================================================================
# [12] ACACIA BRIDGE  --  where the mind reaches the visual engine
# ============================================================================
#
# Everything above this line is either the original CREATURE mind or the
# original TrippyGram engine, preserved.  Nothing above knows the other
# exists.  This section is the only place that knows both, which is what
# keeps the two halves independently debuggable.
#
# Three directions of traffic:
#
#   mind -> engine    CreatureVisualState turns dims into visual parameters;
#                     TrippyGramEngine turns those into real effect calls.
#   engine -> mind    TG_EVENTS become real Events through the existing
#                     perception path.  No second event system.
#   host  -> TG UI    the in-process bridge overrides below make the
#                     TrippyGram UI's ACACIA indicators read the live host
#                     instead of a heartbeat file written by another process.


# ---------------------------------------------------------------- TG events
# These go through Brain.perceive(Event(...)) like anything else that happens
# to the creature.  They are named as constants so the UI, the engine and the
# brain all agree on the spelling.

TG_EVENT_GENERATION_STARTED = "tg_generation_started"
TG_EVENT_GENERATION_COMPLETED = "tg_generation_completed"
TG_EVENT_GENERATION_FAILED = "tg_generation_failed"
TG_EVENT_EFFECT_SELECTED = "tg_effect_selected"
TG_EVENT_IMAGE_EXPORTED = "tg_image_exported"
TG_EVENT_PRESET_CHANGED = "tg_preset_changed"
TG_EVENT_SOURCE_LOADED = "tg_source_loaded"
TG_EVENT_LOOKED_AT_RESULT = "tg_looked_at_result"

# How each one lands emotionally.  Kept as data rather than scattered nudges
# so the mapping can be read in one place and tuned without hunting.
#            salience  valence  novelty  curiosity  boredom  arousal
TG_EVENT_TONE = {
    TG_EVENT_GENERATION_STARTED:   (0.30,  0.05, 0.10, 0.06, -0.10, 0.08),
    TG_EVENT_GENERATION_COMPLETED: (0.55,  0.20, 0.45, 0.05, -0.30, 0.05),
    TG_EVENT_GENERATION_FAILED:    (0.45, -0.25, 0.05, 0.02,  0.05, 0.10),
    TG_EVENT_EFFECT_SELECTED:      (0.20,  0.02, 0.12, 0.08, -0.05, 0.02),
    TG_EVENT_IMAGE_EXPORTED:       (0.40,  0.15, 0.05, 0.00, -0.05, 0.00),
    TG_EVENT_PRESET_CHANGED:       (0.25,  0.02, 0.20, 0.10, -0.08, 0.02),
    TG_EVENT_SOURCE_LOADED:        (0.30,  0.05, 0.25, 0.12, -0.12, 0.04),
    TG_EVENT_LOOKED_AT_RESULT:     (0.35,  0.10, 0.30, 0.10, -0.20, 0.02),
}


def tg_emit(brain, kind, text="", salience=None, valence=None, **data):
    """Push a TrippyGram happening into the creature's existing event path.

    Safe to call from any thread only in the sense that it never raises; the
    caller should still marshal through the UI queue when it can, because
    emotion integration belongs to the brain loop."""
    if brain is None:
        return None
    tone = TG_EVENT_TONE.get(kind, (0.3, 0.0, 0.1, 0.0, 0.0, 0.0))
    sal = tone[0] if salience is None else salience
    val = tone[1] if valence is None else valence
    try:
        ev = Event(kind, text or kind.replace("tg_", "").replace("_", " "),
                   salience=sal, valence=val, **data)
        brain.perceive(ev)
        e = brain.emotion
        if tone[2]:
            e.bump_novelty(tone[2], "something visual changed")
        if tone[3]:
            e.nudge("curiosity", tone[3], "the visuals are doing something")
        if tone[4]:
            e.nudge("boredom", tone[4], "making something")
        if tone[5]:
            e.nudge("arousal", tone[5])
        return ev
    except Exception:
        return None


# ------------------------------------------------------- creature -> visuals
class CreatureVisualState:
    """Translation layer: internal state -> visual parameters.

    Deliberately NOT a pile of one-to-one mappings sprinkled through the UI.
    Every dimension contributes to several parameters and every parameter is
    fed by several dimensions, which is what stops the output from looking
    like a set of sliders wired directly to the emotion meters.

    It also has its own smoothing with a dead zone.  The brain runs at 10 Hz;
    without this the palette would twitch on every tick, and a visual style
    that changes ten times a second is not a style.
    """

    # visual parameters this layer produces
    KEYS = ("intensity", "effect_count", "saturation", "contrast", "distortion",
            "glitch", "psychedelic", "randomness", "complexity", "movement",
            "warmth", "stability")

    # palettes are named, not computed, so the look stays coherent
    PALETTES = {
        "ember":    ("#ff7a3d", "#ffd27a", "#40120a"),   # warm, positive, calm
        "bloom":    ("#ff5fa2", "#ffd0e4", "#2a0a1c"),   # warm, positive, awake
        "verdant":  ("#6fe3a0", "#dffbe8", "#08251a"),   # settled, content
        "glacier":  ("#7ec8ff", "#dff0ff", "#07182b"),   # cool, calm, low arousal
        "voidlight":("#a86bff", "#e6d4ff", "#120827"),   # curious, strange
        "acid":     ("#c6ff2e", "#f2ffb0", "#1b2400"),   # high arousal, high curiosity
        "static":   ("#ff3b3b", "#ffb0b0", "#240707"),   # stressed
        "ash":      ("#8993a8", "#d6dbe6", "#111319"),   # flat, low energy, bored
    }

    def __init__(self, smoothing=0.10, dead_zone=0.04):
        self.smoothing = clamp01(smoothing)
        self.dead_zone = clamp01(dead_zone)
        self.params = {k: 0.5 for k in self.KEYS}
        self.params["effect_count"] = 0.4
        self.palette = "verdant"
        self._palette_since = time.time()
        self.last_raw = dict(self.params)
        self.locked = False          # UI can freeze the mapping for manual work

    # -- the actual translation -----------------------------------------
    def read(self, snapshot):
        """snapshot: Brain.snapshot().  Returns the raw (unsmoothed) params."""
        d = (snapshot or {}).get("dims", {}) or {}
        val = float(d.get("valence", 0.5))
        aro = float(d.get("arousal", 0.4))
        eng = float(d.get("energy", 0.6))
        stress = float(d.get("stress", 0.2))
        cur = float(d.get("curiosity", 0.4))
        conf = float(d.get("confidence", 0.5))
        bore = float(d.get("boredom", 0.3))
        fam = float(d.get("familiarity", 0.3))
        nov = float(d.get("novelty", 0.3))
        att = float(d.get("attention", 0.4))

        p = {}
        # loudness of the pipeline: arousal drives it, stress adds to it,
        # low energy damps it however excited the creature claims to be
        p["intensity"] = clamp01(0.20 + aro * 0.55 + stress * 0.25 - (1 - eng) * 0.25)
        # how many effects get stacked: curiosity and boredom both push for more
        p["effect_count"] = clamp01(0.15 + cur * 0.45 + bore * 0.30 + aro * 0.15
                                    - stress * 0.12)
        # colour: positive mood saturates, stress bleaches toward extremes
        p["saturation"] = clamp01(0.30 + val * 0.50 + aro * 0.15 - stress * 0.10)
        p["contrast"] = clamp01(0.30 + stress * 0.40 + aro * 0.20 - val * 0.10)
        # deformation of the image itself
        p["distortion"] = clamp01(0.10 + stress * 0.45 + aro * 0.25 + (1 - conf) * 0.20)
        p["glitch"] = clamp01(stress * 0.60 + (1 - conf) * 0.25 + aro * 0.15
                              - val * 0.15)
        p["psychedelic"] = clamp01(cur * 0.45 + nov * 0.25 + val * 0.20 + aro * 0.15)
        # willingness to reach for effects it has never used
        p["randomness"] = clamp01(cur * 0.50 + bore * 0.35 - fam * 0.20
                                  - conf * 0.10 + 0.10)
        p["complexity"] = clamp01(0.20 + cur * 0.35 + att * 0.25 + eng * 0.20
                                  - stress * 0.15)
        p["movement"] = clamp01(0.15 + eng * 0.40 + aro * 0.40 - stress * 0.10)
        p["warmth"] = clamp01(0.50 + val * 0.35 - stress * 0.20 + eng * 0.10)
        # stability is the inverse of everything that wants to shake
        p["stability"] = clamp01(0.30 + conf * 0.45 + val * 0.20
                                 - stress * 0.40 - aro * 0.15)
        self.last_raw = p
        return p

    def update(self, snapshot, dt=0.1):
        """Smooth toward the raw reading.  Returns the smoothed params."""
        raw = self.read(snapshot)
        if self.locked:
            return dict(self.params)
        rate = clamp01(self.smoothing * max(0.0, dt) * 10.0)
        for k, target in raw.items():
            cur = self.params.get(k, 0.5)
            if abs(target - cur) < self.dead_zone:
                continue                       # dead zone: ignore the twitch
            self.params[k] = cur + (target - cur) * rate
        self._pick_palette(snapshot)
        return dict(self.params)

    def _pick_palette(self, snapshot):
        """Palette changes are committed, not continuous: once chosen it is
        held for a while, because a palette that changes every second is not
        a palette either."""
        if time.time() - self._palette_since < 12.0:
            return
        d = (snapshot or {}).get("dims", {}) or {}
        val = float(d.get("valence", 0.5))
        aro = float(d.get("arousal", 0.4))
        stress = float(d.get("stress", 0.2))
        cur = float(d.get("curiosity", 0.4))
        eng = float(d.get("energy", 0.6))
        bore = float(d.get("boredom", 0.3))

        if stress > 0.62:
            want = "static"
        elif bore > 0.66 and eng < 0.45:
            want = "ash"
        elif cur > 0.66 and aro > 0.5:
            want = "acid"
        elif cur > 0.58:
            want = "voidlight"
        elif val > 0.62 and aro > 0.55:
            want = "bloom"
        elif val > 0.58:
            want = "ember"
        elif aro < 0.35:
            want = "glacier"
        else:
            want = "verdant"
        if want != self.palette:
            self.palette = want
            self._palette_since = time.time()

    # -- readable form for the UI and for the LLM context ----------------
    def palette_colors(self):
        return self.PALETTES.get(self.palette, self.PALETTES["verdant"])

    def describe(self):
        p = self.params
        bits = []
        bits.append("loud" if p["intensity"] > 0.62 else
                    "quiet" if p["intensity"] < 0.32 else "measured")
        bits.append("saturated" if p["saturation"] > 0.64 else
                    "washed out" if p["saturation"] < 0.36 else "tempered")
        if p["glitch"] > 0.55:
            bits.append("breaking up")
        if p["psychedelic"] > 0.6:
            bits.append("psychedelic")
        if p["stability"] < 0.32:
            bits.append("unstable")
        if p["randomness"] > 0.62:
            bits.append("experimental")
        return ", ".join(bits) + f" ({self.palette})"

    def intensity_1_5(self):
        """The engine's existing 1..5 intensity scale."""
        return int(clamp(round(1 + self.params["intensity"] * 4), 1, 5))

    def effect_budget(self):
        """How many effects to stack, inside the engine's own INTENSITY_FX
        band so the result stays in the range the effects were tuned for."""
        try:
            lo, hi = INTENSITY_FX.get(self.intensity_1_5(), (2, 4))
        except Exception:
            lo, hi = 2, 4
        span = max(0, hi - lo)
        return int(clamp(round(lo + span * self.params["effect_count"]), 1, 8))

    def to_dict(self):
        return {"params": {k: round(v, 3) for k, v in self.params.items()},
                "palette": self.palette, "locked": self.locked}

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        for k, v in (data.get("params") or {}).items():
            if k in self.params:
                try:
                    self.params[k] = clamp01(float(v))
                except Exception:
                    pass
        if data.get("palette") in self.PALETTES:
            self.palette = data["palette"]
        self.locked = bool(data.get("locked", False))


# ------------------------------------------------------------- effect index
# The engine ships ~250 effects in one flat list.  Nothing in it is changed
# here; this is only an index over EFFECTS so the visual state can ask for a
# KIND of effect rather than needing to know 250 names.

FX_FAMILY_KEYWORDS = {
    "glitch":   ("glitch", "datamosh", "corrupt", "vhs", "scanline", "bit crush",
                 "tape", "data", "freeze", "stripes", "shatter", "slit"),
    "colour":   ("hue", "duotone", "chromatic", "rainbow", "prism", "iridescent",
                 "solarize", "color", "colour", "thermal", "infrared", "zebra"),
    "neon":     ("neon", "glow", "aura", "bloom", "electric", "uv", "hologram",
                 "retrowave", "glitter", "bokeh"),
    "geometry": ("kaleid", "mirror", "hex", "grid", "cube", "fractal", "sacred",
                 "low poly", "crystal", "tile", "mosaic", "topographic",
                 "wireframe", "diamond", "cel"),
    "distort":  ("warp", "melt", "liquid", "wave", "smear", "swirl", "vortex",
                 "gravity", "ripple", "wind", "perspective", "tunnel", "luma",
                 "displacement", "stripe warp"),
    "paint":    ("paint", "watercolor", "oil", "ink", "splatter", "pour", "knife",
                 "pointillism", "silk", "cross hatch", "emboss", "contour"),
    "cosmic":   ("star", "aurora", "nebula", "plasma", "void", "dark matter",
                 "shockwave", "rift", "constellation", "lightning", "smoke"),
    "lofi":     ("pixel", "dither", "posterize", "halftone", "comic", "ascii",
                 "crt", "grain", "deep fry", "bit", "pop art", "retro"),
    "dark":     ("shadow", "void", "burn", "fog", "xray", "night", "negative",
                 "bleach", "depth"),
    "texture":  ("frosted", "soap", "bubble", "glass", "metal", "chrome",
                 "marble", "lace", "veins", "crystalline", "acid"),
}


def fx_family_index(effect_pairs=None):
    """-> {family: [(name, fn), ...]} built from the live EFFECTS registry.

    An effect can belong to more than one family; that is intentional, since
    'Neon Grid' is honestly both neon and geometry."""
    pairs = effect_pairs if effect_pairs is not None else globals().get("EFFECTS", [])
    index = {fam: [] for fam in FX_FAMILY_KEYWORDS}
    index["other"] = []
    for name, fn in pairs:
        low = name.lower()
        placed = False
        for fam, kws in FX_FAMILY_KEYWORDS.items():
            if any(k in low for k in kws):
                index[fam].append((name, fn))
                placed = True
        if not placed:
            index["other"].append((name, fn))
    return index


# ------------------------------------------------------------------ presets
class TrippyGramPreset:
    """A named creative direction: which families to pull from, how hard, and
    which parameters of the visual state it overrides.

    Presets do not contain effect lists.  They contain family weights, so a
    preset keeps working when the effect registry grows."""

    __slots__ = ("name", "families", "intensity", "count", "overrides", "note")

    def __init__(self, name, families, intensity=None, count=None,
                 overrides=None, note=""):
        self.name = name
        self.families = families            # {family: weight}
        self.intensity = intensity          # 1..5 or None = follow the creature
        self.count = count                  # int or None = follow the creature
        self.overrides = overrides or {}    # visual params forced by the preset
        self.note = note

    def to_dict(self):
        return {"name": self.name, "families": self.families,
                "intensity": self.intensity, "count": self.count,
                "overrides": self.overrides, "note": self.note}


TG_PRESETS = [
    TrippyGramPreset("Follow the creature", {}, None, None, {},
                     "whatever it currently wants - no override at all"),
    TrippyGramPreset("Calm", {"colour": 1.0, "paint": 1.2, "texture": 0.8},
                     2, 2, {"glitch": 0.05, "distortion": 0.15, "stability": 0.85},
                     "soft, slow, nothing breaking"),
    TrippyGramPreset("Dream", {"colour": 1.0, "neon": 0.9, "distort": 0.8,
                               "paint": 0.6},
                     3, 3, {"psychedelic": 0.7, "glitch": 0.1},
                     "soft-edged and strange"),
    TrippyGramPreset("Psychedelic", {"colour": 1.2, "geometry": 1.0,
                                     "distort": 1.0, "neon": 0.8},
                     4, 5, {"psychedelic": 0.95, "saturation": 0.9},
                     "the original TrippyGram look, turned up"),
    TrippyGramPreset("Glitch storm", {"glitch": 1.5, "lofi": 0.8, "distort": 0.6},
                     4, 4, {"glitch": 0.9, "stability": 0.15, "contrast": 0.8},
                     "broken transport, damaged tape"),
    TrippyGramPreset("Cosmic", {"cosmic": 1.5, "neon": 0.8, "dark": 0.6},
                     4, 4, {"psychedelic": 0.7, "warmth": 0.3},
                     "deep space, rifts and starfields"),
    TrippyGramPreset("Lo-fi", {"lofi": 1.5, "colour": 0.5},
                     2, 3, {"complexity": 0.3, "saturation": 0.45},
                     "pixels, dither, print dots"),
    TrippyGramPreset("Neon night", {"neon": 1.5, "dark": 0.9, "geometry": 0.5},
                     4, 4, {"warmth": 0.25, "contrast": 0.8},
                     "black ground, burning edges"),
    TrippyGramPreset("Paint", {"paint": 1.6, "texture": 0.7},
                     3, 3, {"glitch": 0.05, "complexity": 0.6},
                     "brush, knife and ink"),
    TrippyGramPreset("Overload", {"glitch": 1.0, "neon": 1.0, "distort": 1.0,
                                  "cosmic": 0.8, "geometry": 0.8},
                     5, 7, {"intensity": 0.95, "randomness": 0.8},
                     "everything at once - this is what OVERLOADED looks like"),
]
TG_PRESET_MAP = {p.name: p for p in TG_PRESETS}


# ----------------------------------------------------------------- pipeline
class TrippyGramPipeline:
    """An ordered, reproducible list of effect names plus the parameters it
    was built with.

    Nondestructive by construction: a pipeline never touches an image, it is
    a description.  TrippyGramEngine applies it to a COPY of the source and
    keeps the original untouched, which is how the preview workflow in the
    original TrippyGram UI already behaved and must keep behaving."""

    __slots__ = ("effects", "intensity", "seed", "preset", "origin", "params", "t")

    def __init__(self, effects=None, intensity=3, seed=None, preset="",
                 origin="manual", params=None):
        self.effects = list(effects or [])
        self.intensity = int(clamp(intensity, 1, 5))
        self.seed = seed if seed is not None else random.randint(1, 2 ** 31 - 1)
        self.preset = preset
        self.origin = origin          # manual | creature | preset | random
        self.params = dict(params or {})
        self.t = time.time()

    def pairs(self):
        """-> [(name, fn)] using the real effect implementations."""
        emap = globals().get("EFFECT_MAP", {})
        return [(n, emap[n]) for n in self.effects if n in emap]

    def label(self):
        if not self.effects:
            return "(empty pipeline)"
        head = ", ".join(self.effects[:3])
        return head + (f" +{len(self.effects) - 3}" if len(self.effects) > 3 else "")

    def to_dict(self):
        return {"effects": self.effects, "intensity": self.intensity,
                "seed": self.seed, "preset": self.preset, "origin": self.origin,
                "params": {k: round(v, 3) for k, v in self.params.items()},
                "t": self.t}

    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict):
            return cls()
        p = cls(d.get("effects"), d.get("intensity", 3), d.get("seed"),
                d.get("preset", ""), d.get("origin", "manual"), d.get("params"))
        p.t = float(d.get("t", time.time()))
        return p


# ------------------------------------------------------------------- engine
class TrippyGramEngine:
    """A clean interface over the preserved TrippyGram implementation.

    Every method below ends up calling the ORIGINAL functions from the engine
    section: EFFECT_MAP entries, generate_trippy, generate_trippy_video,
    generate_nft_character, generate_nft_with_effects, generate_nft_reel,
    auto_scramble, save_nft_metadata.  Nothing is reimplemented here.

    The engine holds no Tk references and never touches the UI, so it is safe
    to call from a worker thread.  It also never mutates a loaded source
    image: apply_pipeline copies first."""

    def __init__(self, brain=None, visual_state=None, out_dir=None, log=None):
        self.brain = brain
        self.visual = visual_state or CreatureVisualState()
        self.out_dir = Path(out_dir or (APP_DIR / "trippygram"))
        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.log = log or (lambda *_a, **_k: None)

        self.source_path = None
        self.source_image = None      # the ORIGINAL - never written to
        self.source_kind = "image"    # image | video | generated
        self.preview = None           # last result (a separate image)
        self.last_pipeline = None
        self.last_output = None
        self.history = []             # [(path, pipeline)] newest last
        self.preset_name = TG_PRESETS[0].name
        self._index = None
        self._lock = threading.Lock()
        self.genome = None    # StyleGenome, attached by the host (Phase 13)
        self.param_net = None  # [PHASE 26] ParameterNet, attached by the host
        self.meta = None       # [PHASE 54] MetaLearner, attached by the host

    # -- availability ----------------------------------------------------
    @staticmethod
    def available():
        """The engine needs PIL and numpy.  CREATURE itself does not, so this
        has to be answerable without crashing the host."""
        missing = []
        if globals().get("Image") is None:
            missing.append("Pillow")
        if globals().get("np") is None:
            missing.append("numpy")
        return (not missing), ("missing: " + ", ".join(missing) if missing else "ready")

    @staticmethod
    def video_available():
        return has_module("cv2")

    # -- registry --------------------------------------------------------
    def get_effects(self):
        """-> [name] straight from the preserved EFFECTS registry."""
        return list(globals().get("EFFECT_NAMES", []))

    def get_effect_pairs(self):
        return list(globals().get("EFFECTS", []))

    def families(self):
        if self._index is None:
            self._index = fx_family_index(self.get_effect_pairs())
        return self._index

    def get_presets(self):
        return list(TG_PRESETS)

    def set_preset(self, name):
        if name in TG_PRESET_MAP and name != self.preset_name:
            self.preset_name = name
            tg_emit(self.brain, TG_EVENT_PRESET_CHANGED,
                    f"switched to the {name} preset", preset=name)
        return TG_PRESET_MAP.get(self.preset_name)

    def preset(self):
        return TG_PRESET_MAP.get(self.preset_name, TG_PRESETS[0])

    # -- source ----------------------------------------------------------
    def load_image(self, path):
        """Load a source WITHOUT modifying it.  Returns (ok, detail)."""
        ok, why = self.available()
        if not ok:
            return False, why
        p = Path(path)
        if not p.exists():
            return False, "that file is not there"
        if p.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            self.source_path = str(p)
            self.source_kind = "video"
            self.source_image = None
            self.preview = None
            tg_emit(self.brain, TG_EVENT_SOURCE_LOADED,
                    f"looking at a video: {p.name}", source=str(p))
            return True, "video loaded"
        try:
            img = Image.open(str(p))
            img.load()
            self.source_image = img.convert("RGB")
            self.source_path = str(p)
            self.source_kind = "image"
            self.preview = None
            tg_emit(self.brain, TG_EVENT_SOURCE_LOADED,
                    f"looking at an image: {p.name}", source=str(p))
            return True, f"{self.source_image.width}x{self.source_image.height}"
        except Exception as exc:
            return False, f"couldn't open it: {exc}"

    def load_generated(self, seed=None, traits=None):
        """Use the preserved NFT character generator as a source."""
        ok, why = self.available()
        if not ok:
            return False, why
        try:
            img, tr = generate_nft_character(size=1080, seed=seed,
                                             override_traits=traits)
            self.source_image = img.convert("RGB")
            self.source_path = None
            self.source_kind = "generated"
            self.preview = None
            tg_emit(self.brain, TG_EVENT_SOURCE_LOADED,
                    "made a new character to work from", generated=True)
            return True, tr
        except Exception as exc:
            traceback.print_exc()
            return False, f"character generation failed: {exc}"

    def clear_source(self):
        self.source_image = None
        self.source_path = None
        self.preview = None

    # -- selection -------------------------------------------------------
    def random_effect(self):
        names = self.get_effects()
        return random.choice(names) if names else None

    def random_pipeline(self, count=None, intensity=None):
        names = self.get_effects()
        if not names:
            return TrippyGramPipeline(origin="random")
        inten = int(clamp(intensity or 3, 1, 5))
        try:
            lo, hi = INTENSITY_FX.get(inten, (2, 4))
        except Exception:
            lo, hi = 2, 4
        n = int(count or random.randint(lo, hi))
        pipe = TrippyGramPipeline(random.sample(names, min(n, len(names))),
                                  inten, origin="random")
        return pipe

    def pipeline_from_state(self, snapshot=None, preset_name=None, count=None,
                            intensity=None):
        """THE bridge method: internal state -> a concrete effect pipeline.

        Weighting, not switching.  Every candidate effect gets a score built
        from the preset's family weights, how well the family suits the
        current parameters, and an exploration term driven by curiosity and
        boredom.  Two runs in the same mood give related but not identical
        pipelines, which is the point."""
        pairs = self.get_effect_pairs()
        if not pairs:
            return TrippyGramPipeline(origin="creature")

        if snapshot is not None:
            self.visual.update(snapshot, dt=0.1)
        p = dict(self.visual.params)
        preset = TG_PRESET_MAP.get(preset_name or self.preset_name, TG_PRESETS[0])
        p.update(preset.overrides)

        # [PHASE 26] continuous parameter learning: bounded, family-keyed
        # additive offsets on top of the mood-driven baseline, applied
        # BEFORE affinity/intensity/budget are derived from `p` - so it
        # actually shapes which effects and how much gets chosen, not just
        # a recorded-but-inert number. Refines HOW a family is rendered;
        # WHICH family is chosen stays affinity's job, further down.
        if self.param_net is not None and self.genome is not None:
            top_fams = [f for f, _ in
                       sorted(self.genome.families.items(), key=lambda kv: -kv[1])[:2]]
            for k, off in self.param_net.bias(top_fams).items():
                if k in p:
                    p[k] = clamp01(p[k] + off)

        inten = intensity or preset.intensity or self.visual.intensity_1_5()
        inten = int(clamp(inten, 1, 5))
        budget = count or preset.count or self.visual.effect_budget()
        budget = int(clamp(budget, 1, 8))

        # family affinity from the visual parameters
        affinity = {
            "glitch":   p["glitch"] * 1.3 + p["distortion"] * 0.4,
            "colour":   p["saturation"] * 1.0 + p["psychedelic"] * 0.5,
            "neon":     p["saturation"] * 0.6 + p["intensity"] * 0.5 + (1 - p["warmth"]) * 0.3,
            "geometry": p["complexity"] * 1.0 + p["psychedelic"] * 0.4,
            "distort":  p["distortion"] * 1.2 + p["movement"] * 0.5,
            "paint":    p["stability"] * 0.9 + (1 - p["glitch"]) * 0.5 + p["warmth"] * 0.3,
            "cosmic":   p["psychedelic"] * 0.9 + p["complexity"] * 0.4 + (1 - p["warmth"]) * 0.3,
            "lofi":     (1 - p["complexity"]) * 0.8 + p["contrast"] * 0.4,
            "dark":     (1 - p["warmth"]) * 0.8 + p["contrast"] * 0.5 - p["saturation"] * 0.2,
            "texture":  p["complexity"] * 0.6 + p["stability"] * 0.4,
            "other":    0.35,
        }
        for fam, w in (preset.families or {}).items():
            affinity[fam] = affinity.get(fam, 0.4) * (0.4 + w)

        # [PHASE 13] persistent taste on top of momentary mood: the genome,
        # shaped by personality and by trust in the user, biases the same
        # affinity table rather than forking a second selection path.
        if self.genome is not None:
            personality = getattr(self.brain, "personality", None) if self.brain else None
            relationship = getattr(self.brain, "user_relationship", None) if self.brain else None
            genome_bias = self.genome.bias_from_state(personality, relationship)
            for fam in list(affinity):
                affinity[fam] = affinity[fam] * genome_bias.get(fam, 1.0)



        index = self.families()
        explore = p["randomness"]
        # [PHASE 54] bounded exploration/exploitation balance - the gain is
        # clamped inside MetaLearner.EXPLORE_RANGE, so this can shade the
        # balance but never abandon either side of it.
        if self.meta is not None:
            explore = clamp01(explore * self.meta.explore_gain())
        scored = []
        for fam, members in index.items():
            base = max(0.0, affinity.get(fam, 0.3))
            if preset.families and fam not in preset.families:
                base *= 0.35      # a preset narrows the field without closing it
            for name, _fn in members:
                scored.append((base + random.uniform(0.0, 0.25 + explore * 0.9), name))

        scored.sort(key=lambda x: -x[0])
        chosen, seen = [], set()
        for _s, name in scored:
            if name in seen:
                continue
            seen.add(name)
            chosen.append(name)
            if len(chosen) >= budget:
                break

        pipe = TrippyGramPipeline(chosen, inten, preset=preset.name,
                                  origin="creature", params=p)
        return pipe

    # -- application (nondestructive) ------------------------------------
    def apply_effect(self, image, name):
        """Apply ONE preserved effect to a copy.  Returns a new image."""
        emap = globals().get("EFFECT_MAP", {})
        fn = emap.get(name)
        if fn is None or image is None:
            return image
        try:
            return fn(image.copy())
        except Exception as exc:
            self.log(f"effect '{name}' failed: {exc}")
            return image

    def apply_pipeline(self, pipeline, image=None, progress=None, cancel=None):
        """Run a pipeline over a COPY of the source.  The original is never
        touched.  Returns (result_image, applied_names)."""
        src = image if image is not None else self.source_image
        if src is None:
            return None, []
        work = src.copy()
        applied = []
        names = pipeline.effects if isinstance(pipeline, TrippyGramPipeline) else list(pipeline)
        emap = globals().get("EFFECT_MAP", {})
        total = max(1, len(names))
        rnd_state = random.getstate()
        try:
            random.seed(getattr(pipeline, "seed", None) or random.randint(1, 2 ** 31))
            for i, name in enumerate(names):
                if cancel is not None and cancel.is_set():
                    break
                fn = emap.get(name)
                if fn is None:
                    continue
                try:
                    work = fn(work)
                    applied.append(name)
                except Exception as exc:
                    self.log(f"effect '{name}' failed: {exc}")
                if progress:
                    try:
                        progress((i + 1) / total)
                    except Exception:
                        pass
        finally:
            random.setstate(rnd_state)
        self.preview = work
        return work, applied

    def scramble(self, image, strength=0.5):
        """The preserved auto_scramble, on a copy."""
        if image is None:
            return None
        try:
            return auto_scramble(image.copy(), strength)
        except Exception as exc:
            self.log(f"scramble failed: {exc}")
            return image

    # -- generation ------------------------------------------------------
    def generate(self, pipeline=None, snapshot=None, source=None,
                 progress=None, cancel=None, save=True, kind=None):
        """The one call the UI and the autonomous loop both use.

        Chooses a route through the PRESERVED engine functions depending on
        what the source is:
          video source   -> generate_trippy_video
          image source   -> in-process pipeline over a copy (nondestructive)
          no source      -> generate_nft_character + pipeline
        Returns a result dict; never raises."""
        ok, why = self.available()
        if not ok:
            return {"ok": False, "error": why}

        with self._lock:
            pipe = pipeline or self.pipeline_from_state(snapshot)
            self.last_pipeline = pipe
            stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{random.randint(100, 999)}"

            src_path = source or self.source_path
            is_video = (kind == "video") or (
                self.source_kind == "video" and src_path and not source)

            try:
                # ---- video route: the preserved frame-by-frame function
                if is_video and src_path:
                    if not self.video_available():
                        return {"ok": False, "error": "video needs opencv-python"}
                    out = self.out_dir / f"acacia_{stamp}.mp4"
                    applied = generate_trippy_video(
                        str(src_path), str(out), intensity=pipe.intensity,
                        effect_mode="__acacia_pipeline__", scramble=False,
                        progress_cb=progress, extra_effects=pipe.pairs())
                    self.last_output = str(out)
                    self.history.append((str(out), pipe))
                    return {"ok": True, "path": str(out), "kind": "video",
                            "effects": applied or pipe.effects, "pipeline": pipe,
                            "image": None}

                # ---- image route
                base = None
                traits = None
                if source:
                    base = Image.open(str(source)).convert("RGB")
                elif self.source_image is not None:
                    base = self.source_image
                else:
                    base, traits = generate_nft_character(size=1080,
                                                          seed=pipe.seed)
                    base = base.convert("RGB")
                    if self.source_image is None:
                        self.source_image = base
                        self.source_kind = "generated"

                result, applied = self.apply_pipeline(pipe, base,
                                                      progress=progress,
                                                      cancel=cancel)
                path = None
                if save and result is not None:
                    path = str(self.out_dir / f"acacia_{stamp}.jpg")
                    result.save(path, "JPEG", quality=95)
                    if traits:
                        try:
                            save_nft_metadata(traits, path)
                        except Exception:
                            pass
                    self.last_output = path
                    self.history.append((path, pipe))
                return {"ok": True, "path": path, "kind": "image",
                        "effects": applied, "pipeline": pipe, "image": result,
                        "traits": traits}
            except Exception as exc:
                traceback.print_exc()
                return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def generate_reel(self, image=None, duration=5, fps=30, intensity=None,
                      log_cb=None):
        """The preserved NFT reel generator, on the current preview/source."""
        img = image if image is not None else (self.preview or self.source_image)
        if img is None:
            return {"ok": False, "error": "nothing to animate yet"}
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out = self.out_dir / f"acacia_reel_{stamp}.mp4"
        try:
            generate_nft_reel(img, str(out), duration_sec=duration, fps=fps,
                              intensity=int(intensity or self.visual.intensity_1_5()),
                              effect_mode='🎲 Randomizer',
                              log_cb=log_cb or (lambda m: self.log(str(m))))
            if Path(out).exists():
                self.last_output = str(out)
                return {"ok": True, "path": str(out), "kind": "reel"}
            return {"ok": False, "error": "the reel encoder produced nothing"}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def save(self, path=None, image=None):
        """Export the preview (or a given image) without touching the source."""
        img = image if image is not None else self.preview
        if img is None:
            return False, "there is no result to save yet"
        try:
            target = Path(path) if path else (
                self.out_dir / f"acacia_export_{time.strftime('%Y%m%d_%H%M%S')}.png")
            if target.suffix.lower() in (".jpg", ".jpeg"):
                img.convert("RGB").save(str(target), "JPEG", quality=95)
            else:
                img.save(str(target))
            self.last_output = str(target)
            tg_emit(self.brain, TG_EVENT_IMAGE_EXPORTED,
                    f"saved a piece: {target.name}", path=str(target))
            return True, str(target)
        except Exception as exc:
            return False, f"save failed: {exc}"

    # -- what the result was like ---------------------------------------
    def read_result(self, image=None):
        """Measure the finished image so the creature can PERCEIVE it rather
        than only remember that it pressed a button.

        Real measurements of the pixels: edge energy, saturation, luminance
        spread, histogram entropy, warm/cool balance.  These become the
        properties of the perception event."""
        img = image if image is not None else self.preview
        if img is None or globals().get("np") is None:
            return None
        try:
            small = img.convert("RGB").copy()
            small.thumbnail((192, 192))
            a = np.asarray(small, dtype=np.float32) / 255.0
        except Exception:
            return None
        try:
            r, g, b = a[..., 0], a[..., 1], a[..., 2]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            mx, mn = a.max(axis=2), a.min(axis=2)
            sat = (mx - mn) / (mx + 1e-5)
            gx = float(np.abs(lum[:, 1:] - lum[:, :-1]).mean())
            gy = float(np.abs(lum[1:, :] - lum[:-1, :]).mean())
            edge = (gx + gy) * 0.5
            hist, _ = np.histogram(lum, bins=32, range=(0.0, 1.0))
            pr = hist / max(1.0, float(hist.sum()))
            pr = pr[pr > 0]
            entropy = float(-(pr * np.log2(pr)).sum()) / 5.0
            return {
                "energy": clamp01(edge * 6.0),
                "colour": clamp01(float(sat.mean()) * 1.35),
                "contrast": clamp01(float(lum.std()) * 3.2),
                "density": clamp01(entropy),
                "warmth": clamp01(float(r.mean() - b.mean()) * 0.5 + 0.5),
                "brightness": clamp01(float(lum.mean())),
            }
        except Exception:
            return None

    def snapshot(self):
        return {
            "source": Path(self.source_path).name if self.source_path else
                      ("generated" if self.source_kind == "generated" else "none"),
            "source_kind": self.source_kind,
            "preset": self.preset_name,
            "effects_available": len(self.get_effects()),
            "history": len(self.history),
            "last": Path(self.last_output).name if self.last_output else "",
            "pipeline": self.last_pipeline.to_dict() if self.last_pipeline else None,
            "visual": self.visual.to_dict(),
        }


# ------------------------------------------------ [PHASE 53] embedding space
class CreativeEmbedding:
    """ONE embedding applied to works, territories and motifs, so "more like
    this" is a single real operation instead of three ad hoc lookups.

    A vector has two blocks:

        feat   the six measured FEATURES of an actual rendered image
        fam    weight per effect family, L1-normalised

    Territories and motifs have no rendered image, so their `feat` block is
    None rather than a neutral fill: similarity then compares only what both
    sides genuinely have, instead of quietly asserting that a motif is of
    average brightness. That is the whole reason the blocks are separate."""

    FAMILIES = None            # filled on first use from FX_FAMILY_KEYWORDS
    FEAT_WEIGHT = 0.55         # when both sides have measured features

    @classmethod
    def _families(cls):
        if cls.FAMILIES is None:
            cls.FAMILIES = tuple(sorted(globals().get("FX_FAMILY_KEYWORDS") or {}))
        return cls.FAMILIES

    @classmethod
    def _fam_vector(cls, weights):
        fams = cls._families()
        vec = [float(weights.get(f, 0.0)) for f in fams]
        total = sum(abs(v) for v in vec)
        return [v / total for v in vec] if total > 1e-9 else [0.0] * len(fams)

    @classmethod
    def families_of_effect(cls, name):
        """[PHASE 57] accepts any motif component: a bare visual effect
        name, or a tagged one like "au:Pulse"."""
        raw = str(name or "")
        bare = raw.split(":", 1)[1] if ":" in raw else raw
        audio_fam = (globals().get("AUDIO_FAMILY") or {}).get(bare)
        if audio_fam:
            return [audio_fam]
        low = bare.lower()
        return [f for f, kws in (globals().get("FX_FAMILY_KEYWORDS") or {}).items()
                if any(k in low for k in kws)]

    @classmethod
    def _feat_vector(cls, features):
        if not features:
            return None
        out = []
        for k in VisualMemory.FEATURES:
            v = features.get(k)
            # explicit None check: a genuine 0.0 (no energy at all) is a real
            # measurement and must not be coerced to the 0.5 default
            out.append(clamp01(float(0.5 if v is None else v)))
        return out

    @classmethod
    def of_work(cls, work):
        counts = {}
        for name in work.get("effects") or []:
            for fam in cls.families_of_effect(name):
                counts[fam] = counts.get(fam, 0.0) + 1.0
        return {"feat": cls._feat_vector(work.get("features")),
                "fam": cls._fam_vector(counts)}

    @classmethod
    def of_territory(cls, territory):
        return {"feat": None,
                "fam": cls._fam_vector(territory.get("families") or {})}

    @classmethod
    def of_motif(cls, effect_a, effect_b):
        counts = {}
        for name in (effect_a, effect_b):
            for fam in cls.families_of_effect(name):
                counts[fam] = counts.get(fam, 0.0) + 1.0
        return {"feat": None, "fam": cls._fam_vector(counts)}

    @staticmethod
    def _cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na < 1e-9 or nb < 1e-9:
            return 0.0
        return clamp(dot / (na * nb), -1.0, 1.0)

    @classmethod
    def similarity(cls, a, b):
        """-> 0..1. Compares the family block always, and the feature block
        only when BOTH sides actually have measured features."""
        if not a or not b:
            return 0.0
        has_fam = bool(a.get("fam")) and bool(b.get("fam")) and \
            any(a["fam"]) and any(b["fam"])
        feat = None
        if a.get("feat") and b.get("feat"):
            d = math.sqrt(sum((x - y) ** 2 for x, y in zip(a["feat"], b["feat"])))
            feat = clamp01(1.0 - d / math.sqrt(len(a["feat"])))
        fam = clamp01((cls._cosine(a["fam"], b["fam"]) + 1.0) / 2.0) if has_fam else None
        if feat is not None and fam is not None:
            return clamp01(feat * cls.FEAT_WEIGHT + fam * (1.0 - cls.FEAT_WEIGHT))
        if feat is not None:
            return feat
        return fam if fam is not None else 0.0


class EmbeddingIndex:
    """A DERIVED cache over VisualMemory. It owns no truth: every entry is
    rebuilt from works/territories/affinity, it is never persisted, and any
    change to the record counts rebuilds it. Deleting it costs nothing but
    the next rebuild."""

    MAX_WORKS = 300           # bounded: the newest N works, like novelty()'s window

    def __init__(self, memory):
        self.memory = memory
        self.entries = []      # [{"kind","id","label","vec","score"}]
        self._stamp = None

    def _current_stamp(self):
        vm = self.memory
        return (len(getattr(vm, "works", ())), len(getattr(vm, "territories", ())),
                len(getattr(vm, "affinity", ())))

    def rebuild(self):
        vm = self.memory
        entries = []
        for i, w in enumerate(list(getattr(vm, "works", []))[-self.MAX_WORKS:]):
            if not isinstance(w, dict):
                continue
            entries.append({
                "kind": "work", "id": w.get("path") or f"work:{i}",
                "label": Path(str(w.get("path") or f"work {i}")).name,
                "vec": CreativeEmbedding.of_work(w),
                "score": float(w.get("user_verdict", 0) or 0.0)})
        for t in list(getattr(vm, "territories", [])):
            if not isinstance(t, dict):
                continue
            entries.append({"kind": "territory", "id": t.get("name", "?"),
                            "label": t.get("name", "?"),
                            "vec": CreativeEmbedding.of_territory(t),
                            "score": float(t.get("uses", 0) or 0)})
        try:
            motifs = vm.motifs(min_uses=2, limit=24)
        except Exception:
            motifs = []
        for a, b, score, uses in motifs:
            entries.append({"kind": "motif", "id": f"{a}|{b}", "label": f"{a} + {b}",
                            "vec": CreativeEmbedding.of_motif(a, b), "score": score})
        self.entries = entries
        self._stamp = self._current_stamp()
        return len(entries)

    def ensure(self):
        if self._stamp != self._current_stamp():
            self.rebuild()
        return self.entries

    def find(self, text):
        """-> entry whose label/id contains `text`, newest first, or None."""
        q = (text or "").strip().lower()
        if not q:
            return None
        for e in reversed(self.ensure()):
            if q in str(e["label"]).lower() or q in str(e["id"]).lower():
                return e
        return None

    def similar(self, vec, k=5, kinds=None, exclude_id=None):
        out = []
        for e in self.ensure():
            if kinds and e["kind"] not in kinds:
                continue
            if exclude_id is not None and e["id"] == exclude_id:
                continue
            out.append((CreativeEmbedding.similarity(vec, e["vec"]), e))
        out.sort(key=lambda r: -r[0])
        return out[:k]

    def similar_to_entry(self, entry, k=5, kinds=None):
        return self.similar(entry["vec"], k=k, kinds=kinds, exclude_id=entry["id"])


# ------------------------------------------- [PHASE 55] unified perception
# The unified multimodal perception interface lives on the ONE canonical
# Perception class defined in section [1] above (search: 'class Perception').
# It used to be declared again here, which re-bound the module-level name
# and silently removed the conversational read_message()/extract_facts()
# API that Brain.on_user_message() depends on.  Merged upward; kept as an
# explicit marker so the phase ordering stays readable.  Do NOT redeclare
# `class Perception` anywhere below this point.
UnifiedPerception = Perception   # historical alias for the Phase 55 name



# ------------------------------------------------ [PHASE 56] generative audio
def au_drone(t, rate, p):
    """Slow detuned sine bed - the audio equivalent of a wash effect."""
    f = 55.0 + 110.0 * p.get("warmth", 0.5)
    return [0.45 * (math.sin(2 * math.pi * f * x / rate) +
                    0.6 * math.sin(2 * math.pi * (f * 1.005) * x / rate)) / 1.6
            for x in range(t)]


def au_pulse(t, rate, p):
    """Rhythmic amplitude pulse - density maps to rate, like effect count."""
    hz = 1.0 + 6.0 * p.get("density", 0.5)
    f = 80.0 + 160.0 * p.get("brightness", 0.5)
    out = []
    for x in range(t):
        env = 0.5 + 0.5 * math.sin(2 * math.pi * hz * x / rate)
        out.append(0.5 * env * math.sin(2 * math.pi * f * x / rate))
    return out


def au_shimmer(t, rate, p):
    """Bright upper partials - the counterpart of the neon family."""
    f = 440.0 + 660.0 * p.get("brightness", 0.5)
    return [0.3 * (math.sin(2 * math.pi * f * x / rate) +
                   0.5 * math.sin(2 * math.pi * f * 2.01 * x / rate)) / 1.5
            for x in range(t)]


def au_grit(t, rate, p):
    """Deterministic pseudo-noise - the lofi/glitch counterpart. Seeded, so
    the same pipeline renders the same clip, exactly like the visual side."""
    out, state = [], 12345
    amt = 0.2 + 0.6 * p.get("intensity", 0.5)
    for _x in range(t):
        state = (1103515245 * state + 12345) % (2 ** 31)
        out.append(amt * ((state / (2 ** 30)) - 1.0) * 0.4)
    return out


def au_sweep(t, rate, p):
    """A slow filter-style sweep in pitch - the distort family's cousin."""
    f0, f1 = 60.0, 60.0 + 500.0 * p.get("energy", 0.5)
    out, phase = [], 0.0
    for x in range(t):
        f = f0 + (f1 - f0) * (x / max(1, t))
        phase += 2 * math.pi * f / rate
        out.append(0.4 * math.sin(phase))
    return out


AUDIO_FX = [("Drone", au_drone), ("Pulse", au_pulse), ("Shimmer", au_shimmer),
            ("Grit", au_grit), ("Sweep", au_sweep)]
AUDIO_FX_MAP = dict(AUDIO_FX)

# which visual family each audio layer belongs beside - the bridge Phase 57
# generalises the motif grammar over
AUDIO_FAMILY = {"Drone": "cosmic", "Pulse": "glitch", "Shimmer": "neon",
                "Grit": "lofi", "Sweep": "distort"}


class AudioEngine:
    """[PHASE 56] Procedural audio, structured exactly like the effect side:
    named generators, a bounded pipeline, a rendered artifact, and a reading
    that goes back through Phase 55's perception so it is scored by the same
    evaluate/learn loop as an image.

    BOUNDED LIKE PHASE 15's VIDEO SAMPLING: mono, MAX_SECONDS, fixed sample
    rate, at most MAX_LAYERS generators, pure-Python maths and stdlib `wave`
    only. Worst case is a few hundred thousand floats."""

    RATE = 22050
    MAX_SECONDS = 6.0
    MAX_LAYERS = 3

    def __init__(self, out_dir=None, log=None):
        self.out_dir = Path(out_dir or AUDIO_DIR)  # [PHASE 61] per instance
        self.log = log or (lambda *_a, **_k: None)

    def choose(self, params, budget=2, seed=None):
        """-> [names]: which layers this mood asks for. Same weighting-not-
        switching philosophy the visual pipeline uses."""
        p = params or {}
        want = {
            "Drone": 0.3 + p.get("warmth", 0.5) * 0.7,
            "Pulse": 0.2 + p.get("density", 0.5) * 0.9,
            "Shimmer": 0.2 + p.get("brightness", 0.5) * 0.8,
            "Grit": 0.1 + p.get("intensity", 0.5) * 0.8,
            "Sweep": 0.2 + p.get("energy", 0.5) * 0.7,
        }
        rnd = random.Random(seed)
        scored = [(w + rnd.uniform(0.0, 0.25), name) for name, w in want.items()]
        scored.sort(reverse=True)
        n = int(clamp(budget, 1, self.MAX_LAYERS))
        return [name for _w, name in scored[:n]]

    def render(self, names, params=None, seconds=3.0, path=None):
        """-> (path, samples). Mixed, normalised, written as 16-bit mono WAV."""
        import wave
        import array as _array
        p = dict(params or {})
        secs = float(clamp(seconds, 0.5, self.MAX_SECONDS))
        t = int(self.RATE * secs)
        layers = [n for n in (names or []) if n in AUDIO_FX_MAP][:self.MAX_LAYERS]
        if not layers:
            layers = ["Drone"]
        mix = [0.0] * t
        for name in layers:
            try:
                buf = AUDIO_FX_MAP[name](t, self.RATE, p)
            except Exception as exc:
                self.log(f"audio layer '{name}' failed: {exc}")
                continue
            for i in range(min(t, len(buf))):
                mix[i] += buf[i]
        peak = max((abs(v) for v in mix), default=0.0)
        if peak > 1e-6:
            mix = [v / peak * 0.95 for v in mix]
        out = Path(path or (self.out_dir / f"acacia_{int(time.time())}.wav"))
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(out), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self.RATE)
                w.writeframes(_array.array(
                    "h", [int(clamp(v, -1.0, 1.0) * 32000) for v in mix]).tobytes())
        except Exception as exc:
            self.log(f"could not write audio: {exc}")
            return None, mix
        return str(out), mix

    def make_work(self, names, params=None, seconds=3.0, origin="creature",
                  visual_reading=None):
        """-> a work record structurally parallel to a visual work, so it
        lands in the same VisualMemory store, the same embedding index and
        the same affinity/motif tallies. `kind` is what tells them apart."""
        path, samples = self.render(names, params, seconds)
        reading = Perception.read_audio(samples, self.RATE)
        work = {"t": time.time(), "path": path, "kind": "audio",
                "effects": list(names or []), "intensity": int(
                    clamp(round((params or {}).get("intensity", 0.5) * 5), 1, 5)),
                "preset": "", "origin": origin, "seconds": round(float(seconds), 2),
                "features": reading["features"], "user_verdict": 0}
        if visual_reading is not None:
            # [PHASE 55] does the sound actually match the picture - a real
            # measured number, not an assertion
            work["coherence"] = round(Perception.coherence(reading, visual_reading), 3)
        return work


# --------------------------------------------------- visual memory + taste
class VisualMemory:
    """What the creature has made, what it was like, and how it felt about it.

    Stored separately from the language memory because the retrieval key is a
    feature vector rather than words, but it writes summaries INTO the
    existing MemorySystem so the creature can also talk about its work."""

    FEATURES = ("energy", "colour", "contrast", "density", "warmth", "brightness")

    def __init__(self, path=None):
        self.path = Path(path or VISUAL_FILE)      # [PHASE 61] per instance
        self.works = []          # newest last
        self.affinity = {}       # effect name -> {"n": int, "w": float}
        self.territories = []    # [PHASE 21] discovered {name, families, uses, ...}
        self.experiments = []    # [PHASE 28] control/variant experiments
        self._territory_candidates = {}   # family-combo -> streak count (not persisted)
        # [PHASE 53] derived similarity index - never persisted, rebuilt on
        # demand from the records below, so it cannot become a second truth
        self.index = EmbeddingIndex(self)
        self.load()

    def load(self):
        data = load_json(self.path, {})
        if isinstance(data, dict):
            self.works = [w for w in (data.get("works") or []) if isinstance(w, dict)][-500:]
            self.affinity = {k: v for k, v in (data.get("affinity") or {}).items()
                             if isinstance(v, dict)}
            self.territories = [t for t in (data.get("territories") or [])
                                if isinstance(t, dict)][-24:]
            self.experiments = [e for e in (data.get("experiments") or [])
                               if isinstance(e, dict)][-12:]

    def save(self):
        return save_json(self.path, {"works": self.works[-500:],
                                     "affinity": self.affinity,
                                     "territories": self.territories,
                                     "experiments": self.experiments[-12:],
                                     "saved": time.time()})

    # -- scoring ---------------------------------------------------------
    def score(self, effect_name):
        a = self.affinity.get(effect_name)
        if not a or not a.get("n"):
            return 0.0
        return clamp(a["w"] / a["n"], -1.0, 1.0)

    def confidence(self, effect_name):
        a = self.affinity.get(effect_name)
        return clamp01((a.get("n", 0) if a else 0) / 6.0)

    def reinforce(self, effects, reward):
        for name in effects or []:
            a = self.affinity.setdefault(name, {"n": 0, "w": 0.0})
            a["n"] += 1
            a["w"] += clamp(reward, -1.0, 1.0)

    def novelty(self, features, window=12):
        """Distance from the last N things it made.  1.0 = unlike anything."""
        if not features:
            return 0.5
        recent = [w.get("features") for w in self.works[-window:] if w.get("features")]
        if not recent:
            return 1.0
        # [PHASE 53] the same shared embedding the index uses, restricted to
        # the measured-feature block. Numerically identical to the ad hoc
        # distance this replaced (1 - d/sqrt(n) inverted), so every reward
        # and experiment recorded under the old metric stays comparable.
        here = {"feat": CreativeEmbedding._feat_vector(features), "fam": []}
        best = max(CreativeEmbedding.similarity(
            here, {"feat": CreativeEmbedding._feat_vector(f), "fam": []}) for f in recent)
        return clamp01((1.0 - best) * 2.0)

    # ------------------------------------------- [PHASE 53] similarity search
    def similar_to_work(self, work, k=5, kinds=None):
        """-> [(similarity, entry)] across works, territories and motifs."""
        return self.index.similar(CreativeEmbedding.of_work(work), k=k, kinds=kinds,
                                  exclude_id=work.get("path"))

    def similar_query(self, text, k=5, kinds=None):
        """-> (matched_entry, [(similarity, entry)]) for a typed query."""
        entry = self.index.find(text)
        if entry is None:
            return None, []
        return entry, self.index.similar_to_entry(entry, k=k, kinds=kinds)

    def add(self, work):
        self.works.append(work)
        self.save()

    def best(self, k=5):
        rows = [(n, self.score(n)) for n in self.affinity
                if self.affinity[n].get("n", 0) >= 2]
        rows.sort(key=lambda x: -x[1])
        return rows[:k]

    def worst(self, k=5):
        rows = [(n, self.score(n)) for n in self.affinity
                if self.affinity[n].get("n", 0) >= 2]
        rows.sort(key=lambda x: x[1])
        return rows[:k]

    def stats(self):
        liked = len([w for w in self.works if w.get("user_verdict", 0) > 0])
        return {"works": len(self.works), "liked": liked,
                "effects_rated": len(self.affinity)}

    # ---------------------------------------------------- [PHASE 22] motifs
    # A motif is a recurring, rewarded EFFECT PAIR - not a new store, just a
    # co-occurrence tally over the same `works` list that already exists.
    # [PHASE 57] A motif component is now any stylistic choice, not only a
    # visual effect: "Neon Grid" (visual, bare - the original form), or a
    # tagged one like "au:Pulse" / "pace:slow". Tags keep the same flat
    # "pair:A|B" key space, so every row written before Phase 57 stays
    # valid and keeps scoring - an untagged component simply means visual.
    MEDIA_TAGS = {"au": "audio", "pace": "pacing", "fx": "visual"}

    @classmethod
    def component_media(cls, component):
        tag = str(component).split(":", 1)[0] if ":" in str(component) else ""
        return cls.MEDIA_TAGS.get(tag, "visual")

    def reinforce_pairs(self, effects, reward):
        """Visual-only entry point, unchanged for every existing caller."""
        self.reinforce_components(effects, reward)

    def reinforce_components(self, components, reward):
        """The generalised form: any mix of media in one co-occurrence
        tally, which is what makes a motif a STYLE rather than a list of
        effects."""
        names = sorted(set(str(c) for c in (components or []) if c))
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                key = f"{names[i]}|{names[j]}"
                a = self.affinity.setdefault("pair:" + key, {"n": 0, "w": 0.0})
                a["n"] += 1
                a["w"] += clamp(reward, -1.0, 1.0)

    def synergy(self, a, b):
        key = "pair:" + "|".join(sorted((a, b)))
        row = self.affinity.get(key)
        if not row or not row.get("n"):
            return 0.0
        return clamp(row["w"] / row["n"], -1.0, 1.0)

    def motifs(self, min_uses=3, limit=6, media=None):
        """-> [(component_a, component_b, score, uses)] - the pairs that keep
        earning their place, sorted by how reliably they pay off.

        [PHASE 57] `media` optionally filters: "visual", "audio", "pacing",
        or "cross" for the pairs that span two media. Omitted, it returns
        everything, which is what every pre-57 caller expects."""
        out = []
        for key, row in list(self.affinity.items()):
            if not key.startswith("pair:") or row.get("n", 0) < min_uses:
                continue
            a, b = key[5:].split("|", 1)
            if media:
                ma, mb = self.component_media(a), self.component_media(b)
                if media == "cross":
                    if ma == mb:
                        continue
                elif media not in (ma, mb):
                    continue
            out.append((a, b, clamp(row["w"] / row["n"], -1.0, 1.0), row["n"]))
        out.sort(key=lambda r: -r[2])
        return out[:limit]

    def style_signature(self, min_uses=3):
        """[PHASE 57] -> {media: n_motifs} - one coherent notion of style,
        counted across every medium it has actually learned in."""
        counts = {}
        for a, b, _s, _n in self.motifs(min_uses=min_uses, limit=999):
            for m in {self.component_media(a), self.component_media(b)}:
                counts[m] = counts.get(m, 0) + 1
        return counts

    # ------------------------------------------------- [PHASE 21] territory
    # A Territory is a NAMED region of family-weight space the creature has
    # discovered for itself, distinct from the fixed hand-authored presets.
    # It is additive state on this same file - not a second taste source.
    def discover_territory(self, name, family_weights, sample_work=None):
        for t in self.territories:
            if t["name"] == name:
                t["uses"] += 1
                t["last"] = time.time()
                return t
        t = {"name": name, "families": dict(family_weights), "uses": 1,
             "created": time.time(), "last": time.time(),
             "example": (sample_work or {}).get("path")}
        self.territories.append(t)
        del self.territories[:-24]
        return t

    # ------------------------------------------------- [PHASE 28] experiments
    # Formal control/variant grouping over sessions that already happen.
    # Bounded to a small number of concurrent experiments - no new scheduler,
    # governed by the same cooldown discipline as everything else. Outcomes
    # feed directly back into KnowledgeBase.test via the caller.
    MAX_EXPERIMENTS = 3

    def start_experiment(self, dimension, control_family, variant_family, goal="", spec=None):
        """`spec` [PHASE 49] is the optional design the ExperimentPlanner
        produced - hypothesis, question, the variable under test, what is
        being held constant, the pre-registered prediction, and the
        information-gain/cost estimate that made it worth running. Purely
        additive: every field is optional, so an experiment started the old
        way (no spec) is exactly the record Phase 28 always produced, and a
        saved experiment from before Phase 49 loads with these simply
        absent - nothing reads them without `.get()`."""
        active = [e for e in getattr(self, "experiments", []) if e["status"] == "running"]
        if len(active) >= self.MAX_EXPERIMENTS:
            return None
        exp = {
            "id": f"exp{int(time.time())%10**7}_{random.randint(10,99)}",
            "dimension": dimension, "control": control_family, "variant": variant_family,
            "goal": goal, "status": "running", "created": time.time(),
            "control_scores": [], "variant_scores": [],
        }
        if isinstance(spec, dict):
            for k in ("hypothesis", "question", "variable", "controls",
                      "expected_direction", "predicted_margin", "information_gain",
                      "cost", "reason"):
                if k in spec:
                    exp[k] = spec[k]
        self.experiments = getattr(self, "experiments", [])
        self.experiments.append(exp)
        del self.experiments[:-12]
        return exp

    def record_experiment_trial(self, exp_id, arm, verdict, auto_conclude=True):
        """`auto_conclude=False` [PHASE 49] lets the ExperimentPlanner append
        a trial without triggering the plain minimum-sample rule below, so it
        can apply its own adaptive-sampling judgement (still calling
        `_conclude` itself, the SAME conclusion mechanism, never a second
        one) instead of always stopping at exactly four and four."""
        for e in getattr(self, "experiments", []):
            if e["id"] != exp_id or e["status"] != "running":
                continue
            bucket = "control_scores" if arm == "control" else "variant_scores"
            e[bucket].append(clamp01(verdict))
            if auto_conclude and len(e["control_scores"]) >= 4 and len(e["variant_scores"]) >= 4:
                self._conclude(e)
            return e
        return None

    def _conclude(self, e, stopping_reason="minimum sample reached"):
        """The one place a running experiment becomes a concluded one -
        used directly by the plain four-and-four rule above and by
        ExperimentPlanner's adaptive sampling, so there is exactly one
        conclusion mechanism regardless of who decided it was time."""
        c = sum(e["control_scores"]) / len(e["control_scores"]) if e["control_scores"] else 0.0
        v = sum(e["variant_scores"]) / len(e["variant_scores"]) if e["variant_scores"] else 0.0
        e["status"] = "concluded"
        e["winner"] = e["variant"] if v > c + 0.05 else (
            e["control"] if c > v + 0.05 else "inconclusive")
        e["control_mean"], e["variant_mean"] = round(c, 3), round(v, 3)
        e["concluded"] = time.time()
        e["stopping_reason"] = stopping_reason
        return e

    def active_experiment_for(self, family):
        for e in getattr(self, "experiments", []):
            if e["status"] == "running" and family in (e["control"], e["variant"]):
                return e, ("control" if family == e["control"] else "variant")
        return None, None

    # ------------------------------------------------- [PHASE 37] portfolios
    # A Portfolio is a curated VIEW over `works` - no new store, no new
    # scheduler. Coherence = how tightly a candidate group shares dominant
    # families/territory; only kept-or-better verdicts are eligible.
    def build_portfolios(self, min_size=4, max_size=10, min_verdict=0.55):
        groups = {}
        for w in self.works:
            if w.get("verdict", 0) < min_verdict:
                continue
            prov = w.get("provenance") or {}
            fams = sorted({e.split(":", 1)[0] for e in (w.get("effects") or [])})[:1]
            key = prov.get("territory") or (fams[0] if fams else "untitled")
            groups.setdefault(key, []).append(w)
        portfolios = []
        for key, items in groups.items():
            if len(items) < min_size:
                continue
            items = sorted(items, key=lambda w: -w.get("verdict", 0))[:max_size]
            verdicts = [w.get("verdict", 0) for w in items]
            coherence = clamp01(1.0 - (max(verdicts) - min(verdicts)))
            portfolios.append({
                "name": key, "size": len(items), "coherence": round(coherence, 3),
                "avg_verdict": round(sum(verdicts) / len(verdicts), 3),
                "paths": [w.get("path") for w in items if w.get("path")],
                "since": min(w.get("t", time.time()) for w in items),
            })
        portfolios.sort(key=lambda p: -(p["coherence"] * p["avg_verdict"] * math.log(1 + p["size"])))
        return portfolios

    def maybe_discover_territory(self, work, dominant_families):
        """Called after a verdict is known. A repeated, well-liked family
        combination earns a name; this is deliberately rare and evidence-
        gated (>=0.62 verdict, seen colliding on the same families >=3x)."""
        if not dominant_families or work.get("verdict", 0) < 0.62:
            return None
        key = "+".join(sorted(dominant_families[:2]))
        counts = self._territory_candidates.setdefault(key, 0) + 1
        self._territory_candidates[key] = counts
        if counts < 3:
            return None
        name = " ".join(w.capitalize() for w in key.split("+")) + " Territory"
        weights = {f: (1.4 if f in dominant_families[:2] else 0.5)
                  for f in FX_FAMILY_KEYWORDS}
        return self.discover_territory(name, weights, work)


# --------------------------------------------------------------- StyleGenome
class StyleGenome:
    """A persistent, slowly-drifting taste vector - what the creature's work
    tends toward across many sessions, as distinct from CreatureVisualState
    (momentary mood -> parameters) and VisualMemory's per-effect affinity
    (which effect, not which overall direction).

    Family weights only ever move by REINFORCE's hard-capped step, driven by
    a measured verdict or explicit user feedback - same discipline as
    Personality.nudge, so taste cannot swing wildly from one image."""

    MAX_STEP = 0.04

    def __init__(self):
        self.families = {fam: 1.0 for fam in FX_FAMILY_KEYWORDS}
        self.generation = 0
        self.log = deque(maxlen=12)          # (t, reason) style-shift log
        self._since_shift = 0

    def reinforce(self, dominant_families, reward):
        reward = clamp(reward, -1.0, 1.0)
        moved = False
        for fam in dominant_families or []:
            if fam not in self.families:
                continue
            step = clamp(reward * 0.10, -self.MAX_STEP, self.MAX_STEP)
            before = self.families[fam]
            self.families[fam] = clamp(before + step, 0.15, 3.0)
            if abs(self.families[fam] - before) > 0.005:
                moved = True
        if moved:
            self._since_shift += 1
        if self._since_shift >= 18:      # a style era has passed
            self._since_shift = 0
            self.generation += 1
            top = sorted(self.families.items(), key=lambda kv: -kv[1])[:2]
            self.log.append((time.time(),
                             f"gen {self.generation}: leaning toward "
                             f"{', '.join(f for f, _ in top)}"))

    def bias_from_state(self, personality=None, relationship=None):
        """-> {family: multiplier}. Genome first; then the persistent
        character (Personality.likes/dislikes, curious/bold traits) and the
        relationship with the user (trust) nudge it further - taste as a
        character trait, not only a mood readout (Phase 13)."""
        out = dict(self.families)
        if personality is not None:
            try:
                curious = personality.traits.get("curious", 0.5)
                bold = personality.traits.get("bold", personality.traits.get("brave", 0.5))
                for fam in ("neon", "cosmic", "geometry", "glitch"):
                    out[fam] = out.get(fam, 1.0) * (0.75 + curious * 0.5)
                for fam in ("glitch", "distort"):
                    out[fam] = out.get(fam, 1.0) * (0.8 + bold * 0.4)
                for like in personality.top_likes(6):
                    low = like.lower()
                    for fam, kws in FX_FAMILY_KEYWORDS.items():
                        if any(k in low for k in kws):
                            out[fam] = out.get(fam, 1.0) * 1.15
            except Exception:
                pass
        if relationship is not None:
            try:
                # trust widens the palette it's willing to try in front of
                # the user; low trust plays it safe (paint/colour, calmer)
                trust = float(getattr(relationship, "trust", 0.35))
                for fam in ("glitch", "cosmic", "lofi"):
                    out[fam] = out.get(fam, 1.0) * (0.7 + trust * 0.5)
                for fam in ("paint", "colour"):
                    out[fam] = out.get(fam, 1.0) * (1.2 - trust * 0.3)
            except Exception:
                pass
        return out

    def signature(self):
        top = sorted(self.families.items(), key=lambda kv: -kv[1])[:3]
        return ", ".join(f for f, _ in top) if top else "undeveloped"

    def to_dict(self):
        return {"families": {k: round(v, 4) for k, v in self.families.items()},
                "generation": self.generation,
                "log": [list(r) for r in self.log]}

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        fam = data.get("families")
        if isinstance(fam, dict):
            for k, v in fam.items():
                if k in self.families:
                    try:
                        self.families[k] = clamp(float(v), 0.15, 3.0)
                    except Exception:
                        pass
        self.generation = int(data.get("generation", 0) or 0)
        for row in data.get("log", []) or []:
            if isinstance(row, (list, tuple)) and len(row) == 2:
                self.log.append(tuple(row))


# --------------------------------------------------------------- ParameterNet
class ParameterNet:
    """[PHASE 26] Continuous parameter learning - same reward-modulated,
    Hebbian-style philosophy as SpikingNet (correlate what was pushed with
    whether it paid off, hard-capped step), but a SEPARATE small instance
    over continuous pipeline parameters instead of discrete motor behaviour.
    Never touches SpikingNet used for physical motor behaviour.

    Learns, per dominant effect-family, a bounded additive offset to a small
    set of continuous params (intensity/saturation/contrast/complexity/
    warmth) - within-family refinement, layered UNDER family/motif choice,
    never replacing it."""

    PARAMS = ("intensity", "saturation", "contrast", "complexity", "warmth")
    MAX_STEP = 0.05
    MAX_OFFSET = 0.22
    LR = 0.06

    def __init__(self):
        self.weights = {}   # family -> {param: offset}

    def bias(self, families):
        """-> {param: offset} averaged over up to the top-2 families given,
        weighted toward the first (dominant) one."""
        fams = [f for f in (families or []) if f][:2]
        if not fams:
            return {}
        out = {k: 0.0 for k in self.PARAMS}
        weights = [0.65, 0.35][:len(fams)]
        for fam, wgt in zip(fams, weights):
            row = self.weights.get(fam)
            if not row:
                continue
            for k in self.PARAMS:
                out[k] += row.get(k, 0.0) * wgt
        return {k: clamp(v, -self.MAX_OFFSET, self.MAX_OFFSET) for k, v in out.items()}

    def learn(self, families, reward, used_params):
        """Hebbian-style: correlate reward with how far each param was
        pushed from baseline (0.5) when this family was in play. A push
        that helped gets reinforced; one that hurt gets pushed back."""
        if not families or used_params is None:
            return
        reward = clamp(float(reward), -1.0, 1.0)
        for fam in families[:2]:
            row = self.weights.setdefault(fam, {k: 0.0 for k in self.PARAMS})
            for k in self.PARAMS:
                used = float(used_params.get(k, 0.5))
                grad = reward * (used - 0.5) * self.LR
                step = clamp(grad, -self.MAX_STEP, self.MAX_STEP)
                row[k] = clamp(row.get(k, 0.0) + step, -self.MAX_OFFSET, self.MAX_OFFSET)

    def to_dict(self):
        return {fam: {k: round(v, 4) for k, v in row.items()}
                for fam, row in self.weights.items()}

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        for fam, row in data.items():
            if isinstance(row, dict):
                self.weights[str(fam)] = {k: float(v) for k, v in row.items()
                                          if k in self.PARAMS}


class MetaLearner:
    """[PHASE 54] Which of the learning mechanisms is actually paying off,
    measured the same way everything else here is measured: by outcome.

    Each finished work reports which mechanisms were IN PLAY for it. Their
    running mean outcome is compared against the baseline mean over all
    work, and the difference - only once there is enough of it - moves two
    knobs: ParameterNet's learning rate and the exploration term the engine
    scores candidates with.

    THE BOUNDS ARE THE POINT. LR_RANGE and EXPLORE_RANGE are class
    constants, every tuning step is clamped to MAX_ADJUST, and nothing in
    this class can widen its own limits: `_bounded` is the only writer of
    either knob and it reads the constants directly. Meta-learning tunes
    parameters; it never removes its own caps."""

    MECHANISMS = ("param_net", "experiment", "curiosity", "genome")
    MIN_SAMPLES = 6           # below this a mechanism tunes nothing at all
    LR_RANGE = (0.03, 0.10)   # hard bounds around ParameterNet.LR (0.06)
    EXPLORE_RANGE = (0.75, 1.25)     # hard bounds on the exploration multiplier
    MAX_ADJUST = 0.03         # per update, as a fraction of the range
    DEFAULT_LR = 0.06

    def __init__(self):
        self.stats = {"baseline": {"n": 0, "mean": 0.0}}
        self.lr = self.DEFAULT_LR
        self.explore = 1.0
        self.log = []          # [(t, what)] - bounded, for the console

    # -- bounds ---------------------------------------------------------
    @classmethod
    def _bounded(cls, value, lo_hi):
        lo, hi = lo_hi
        return clamp(float(value), lo, hi)

    # -- observation ----------------------------------------------------
    def observe(self, mechanisms, dv):
        """One finished outcome, attributed to whichever mechanisms shaped
        it. dv is the same measured [-1, 1] outcome everything else uses."""
        dv = clamp(float(dv), -1.0, 1.0)
        for key in ("baseline",) + tuple(m for m in (mechanisms or [])
                                         if m in self.MECHANISMS):
            row = self.stats.setdefault(key, {"n": 0, "mean": 0.0})
            row["n"] += 1
            row["mean"] += (dv - row["mean"]) * (0.5 if row["n"] < 3 else 0.2)
        self._retune()

    def effectiveness(self, name):
        """-> (gain_vs_baseline, confidence). Gain is the mechanism's own
        measured mean minus the baseline mean; confidence grows with how
        many outcomes stand behind it."""
        row = self.stats.get(name)
        base = self.stats.get("baseline", {"n": 0, "mean": 0.0})
        if not row or row["n"] < self.MIN_SAMPLES or not base["n"]:
            return 0.0, 0.0
        return (clamp(row["mean"] - base["mean"], -1.0, 1.0),
                clamp01(row["n"] / (row["n"] + 8.0)))

    def _retune(self):
        p_gain, p_conf = self.effectiveness("param_net")
        step_lr = (self.LR_RANGE[1] - self.LR_RANGE[0]) * self.MAX_ADJUST
        target = self.lr + p_gain * p_conf * step_lr * 10.0
        new_lr = self._bounded(clamp(target, self.lr - step_lr, self.lr + step_lr),
                               self.LR_RANGE)
        # exploration answers to the two mechanisms whose whole job is
        # finding out rather than exploiting
        e_gain, e_conf = self.effectiveness("experiment")
        c_gain, c_conf = self.effectiveness("curiosity")
        drive = e_gain * e_conf + c_gain * c_conf
        step_ex = (self.EXPLORE_RANGE[1] - self.EXPLORE_RANGE[0]) * self.MAX_ADJUST
        new_ex = self._bounded(
            clamp(self.explore + drive * step_ex * 10.0,
                  self.explore - step_ex, self.explore + step_ex),
            self.EXPLORE_RANGE)
        if abs(new_lr - self.lr) > 1e-6 or abs(new_ex - self.explore) > 1e-6:
            self.log.append((time.time(),
                             f"lr {self.lr:.3f}->{new_lr:.3f}, "
                             f"explore x{self.explore:.2f}->x{new_ex:.2f}"))
            del self.log[:-8]
        self.lr, self.explore = new_lr, new_ex

    # -- read-out -------------------------------------------------------
    def learning_rate(self):
        return self._bounded(self.lr, self.LR_RANGE)

    def explore_gain(self):
        return self._bounded(self.explore, self.EXPLORE_RANGE)

    def apply_to(self, param_net):
        """Shadow ParameterNet's class-level LR on the instance, inside the
        hard range. The class constant is never modified."""
        if param_net is not None:
            param_net.LR = self.learning_rate()

    def report(self):
        out = []
        for name in self.MECHANISMS:
            gain, conf = self.effectiveness(name)
            n = self.stats.get(name, {}).get("n", 0)
            if not n:
                continue
            verdict = ("paying off" if gain > 0.03 else
                       "costing" if gain < -0.03 else "neutral so far")
            out.append(f"{name}: {verdict} ({gain:+.2f} vs baseline, x{n}, "
                       f"confidence {conf:.0%})")
        out.append(f"learning rate {self.learning_rate():.3f} "
                   f"(bounds {self.LR_RANGE[0]}-{self.LR_RANGE[1]}), "
                   f"exploration x{self.explore_gain():.2f} "
                   f"(bounds {self.EXPLORE_RANGE[0]}-{self.EXPLORE_RANGE[1]})")
        return out

    # -- persistence ----------------------------------------------------
    def to_dict(self):
        return {"stats": {k: {"n": int(v["n"]), "mean": round(float(v["mean"]), 4)}
                          for k, v in self.stats.items()},
                "lr": round(self.lr, 4), "explore": round(self.explore, 4)}

    def from_dict(self, data):
        if not isinstance(data, dict):
            return
        for k, v in (data.get("stats") or {}).items():
            if isinstance(v, dict) and "n" in v and "mean" in v:
                try:
                    self.stats[str(k)] = {"n": int(v["n"]), "mean": float(v["mean"])}
                except Exception:
                    pass
        # a tampered or corrupted save cannot widen the bounds either
        self.lr = self._bounded(data.get("lr", self.DEFAULT_LR), self.LR_RANGE)
        self.explore = self._bounded(data.get("explore", 1.0), self.EXPLORE_RANGE)


# ------------------------------------------------------------- CuriosityEngine
class CuriosityEngine:
    """[PHASE 46] Where the uncertainty is, and what is worth doing about it.

    Until now the creature explored because it was BORED - a scalar that says
    "do something different" but cannot say *what* would teach it anything.
    This reads the gaps in what it actually knows and turns them into concrete,
    bounded probes, so exploration aims at the thing most worth finding out.

    Five honest sources, every one of them read from state that already
    exists - no new store, no new counters kept in parallel:

        unexplored     a family with no episode behind it at all
        thin           a family with too little evidence to mean anything
        untested       an open hypothesis that a few more trials would settle
        contradiction  two beliefs about one cue pointing opposite ways
        stale          a discovered territory that has not been revisited

    Probes are deduplicated, rate-limited, scored by information gain over
    cost, and - critically - RETIRED once the record answers them. Without
    that last part curiosity becomes a creature that keeps asking a question
    it already knows the answer to.

    [PHASE 47/48] Two things this used to leave undone, both closed at the
    App level rather than here (App._pick_experiment_arm,
    App._apply_experiment_conclusion): a probe or a genome coin-flip could
    START a Phase-28 experiment, but nothing then made sure BOTH arms
    actually got sampled - it just hoped the ambient mood-driven pipeline
    would wander into each one; and once an experiment concluded, the
    winner was announced in chat and then forgotten, never nudging the
    genome or becoming something KnowledgeBase could test. Phase 47 spends
    an idle cycle with no sharper curiosity probe on whichever arm is
    furthest behind instead of leaving it ambient. Phase 48 makes the
    conclusion itself change something: a genome pull sized to the
    measured margin, and an `experiment:<dimension>` episode for
    KnowledgeBase.mine() to work with, same as every other measured
    outcome in this file already does.
    """

    MIN_GAP = 90.0            # shares the studio's cooldown discipline
    RETIRE_AFTER = 3          # attempts before a probe is given up on
    KNOWN_EPISODES = 3        # evidence that counts as "explored"
    TESTS_FOR_SETTLED = 4     # matches Hypothesis's own status threshold
    STALE_AFTER = 7 * 86400.0
    MAX_PROBES = 6

    def __init__(self, brain, memory, engine, log=None):
        self.brain = brain
        self.memory = memory
        self.engine = engine
        self.log = log or (lambda *_a, **_k: None)
        self.probes = {}          # key -> probe dict
        self.answered = 0
        self._last_select = 0.0

    # -- the shape of what is known ---------------------------------------
    def _families(self):
        return list(FX_FAMILY_KEYWORDS.keys()) + ["other"]

    def _episode_counts(self):
        """family -> how many recorded outcomes mention it. One pass over the
        episode ring the KnowledgeBase already keeps."""
        counts = {}
        for e in getattr(self.brain.knowledge, "episodes", []):
            for cue in (e.get("c") or ()):
                if str(cue).startswith("family:"):
                    fam = str(cue).split(":", 1)[1]
                    counts[fam] = counts.get(fam, 0) + 1
        return counts

    def coverage(self):
        """Fraction of the family space with real evidence behind it. This is
        the single number Phase 46 exists to move."""
        counts = self._episode_counts()
        fams = self._families()
        known = sum(1 for f in fams if counts.get(f, 0) >= self.KNOWN_EPISODES)
        return round(known / max(1, len(fams)), 3)

    # -- finding the gaps ---------------------------------------------------
    def scan(self):
        kb = getattr(self.brain, "knowledge", None)
        if kb is None:
            return []
        counts = self._episode_counts()
        found = []

        # 1/2. never tried, or barely tried
        for fam in self._families():
            n = counts.get(fam, 0)
            if n == 0:
                found.append(self._probe("unexplored", fam,
                                         f"nothing has ever been made from {fam}",
                                         gain=1.0, cost=0.4))
            elif n < self.KNOWN_EPISODES:
                found.append(self._probe("thin", fam,
                                         f"only {n} outcome(s) behind {fam} so far",
                                         gain=0.55, cost=0.35))

        # 3/4. beliefs that are undecided, or that disagree with each other
        by_cue = {}
        for h in getattr(kb, "hypotheses", []):
            cue = str(getattr(h, "cue", "") or "")
            if not cue.startswith("family:"):
                continue
            fam = cue.split(":", 1)[1]
            by_cue.setdefault(cue, []).append(h)
            if h.status == "open" and h.tests < self.TESTS_FOR_SETTLED:
                found.append(self._probe(
                    "untested", fam,
                    f"{h.text()} - {self.TESTS_FOR_SETTLED - h.tests} more trial(s) "
                    f"would settle it",
                    gain=clamp01(0.8 - 0.1 * h.tests), cost=0.3))
        for cue, group in by_cue.items():
            if len(group) < 2:
                continue
            hi = max(group, key=lambda h: h.predicted)
            lo = min(group, key=lambda h: h.predicted)
            if hi.predicted - lo.predicted > 0.5 and hi.tests and lo.tests:
                found.append(self._probe(
                    "contradiction", cue.split(":", 1)[1],
                    f"two beliefs about {cue.split(':', 1)[1]} cannot both be right",
                    gain=1.0, cost=0.5))

        # 5. something it named for itself and then never went back to
        now = time.time()
        for t in getattr(self.memory, "territories", []):
            if (now - float(t.get("last", now))) < self.STALE_AFTER:
                continue
            fams = [f for f, w in (t.get("families") or {}).items() if w > 1.0]
            if fams:
                found.append(self._probe(
                    "stale", fams[0],
                    f"{t['name']} has not been revisited - is it still any good?",
                    gain=0.5, cost=0.35))

        for probe in found:
            existing = self.probes.get(probe["key"])
            if existing is None:
                self.probes[probe["key"]] = probe
            else:                       # refresh the reasoning, keep the tries
                existing["kind"] = probe["kind"]
                existing["gain"] = probe["gain"]
                existing["why"] = probe["why"]
        self._retire(counts)
        if len(self.probes) > self.MAX_PROBES * 3:
            for p in self.pending(99)[self.MAX_PROBES * 2:]:
                self.probes.pop(p["key"], None)
        return self.pending()

    # "unexplored" and "thin" are the SAME question at two strengths, so they
    # share one key: a family that has just earned its first outcome must be
    # downgraded, not asked about twice.
    _GROUP = {"unexplored": "gap", "thin": "gap"}

    def _probe(self, kind, target, why, gain=0.5, cost=0.4):
        return {"key": f"{self._GROUP.get(kind, kind)}:{target}",
                "kind": kind, "target": target,
                "why": why, "gain": clamp01(gain), "cost": clamp01(cost),
                "tries": 0, "born": time.time(), "last": 0.0}

    def _retire(self, counts):
        for key, probe in list(self.probes.items()):
            done = probe["tries"] >= self.RETIRE_AFTER
            if not done and probe["kind"] in ("unexplored", "thin"):
                done = counts.get(probe["target"], 0) >= self.KNOWN_EPISODES
            if done:
                self.probes.pop(key, None)
                self.answered += 1

    # -- choosing what to find out -----------------------------------------
    def pending(self, limit=None):
        rows = sorted(self.probes.values(),
                      key=lambda p: -(p["gain"] / max(0.1, p["cost"])))
        return rows[:limit or self.MAX_PROBES]

    def value(self):
        """0..1 - how much there is to learn right now. Low means the honest
        answer is that making something familiar is fine."""
        rows = self.pending(3)
        return clamp01(sum(p["gain"] for p in rows) / 3.0) if rows else 0.0

    def select(self, now=None, min_gain=0.35):
        """The single highest-value bounded probe, or None. Rate-limited so it
        shares the studio's existing autonomy budget instead of competing with
        it - this never schedules anything itself."""
        now = now or time.time()
        if (now - self._last_select) < self.MIN_GAP:
            return None
        self.scan()
        rows = self.pending(1)
        if not rows or rows[0]["gain"] < min_gain:
            return None
        probe = rows[0]
        self._last_select = now
        probe["tries"] += 1
        probe["last"] = now
        try:
            self.brain.goals.propose(f"find out about {probe['target']}",
                                     0.4 + 0.3 * probe["gain"], probe["why"],
                                     ttl=600.0, kind="discovery")
            self.brain.emotion.nudge("curiosity", 0.05,
                                     "there is something I don't know")
        except Exception:
            pass
        self.log(f"[curiosity] probing {probe['target']}: {probe['why']}")
        return probe

    # -- turning a probe into an actual pipeline ----------------------------
    def focus(self, pipeline, family, keep=1):
        """Bend an already-built pipeline toward the family in question,
        in place, without touching the engine's own weighting.

        Deliberately partial: it swaps in members of the target family but
        keeps some of what the mood chose, so a probe is still a piece of work
        and not a laboratory swatch."""
        if pipeline is None or not family:
            return pipeline
        members = [n for n, _fn in (self.engine.families() or {}).get(family, [])]
        if not members:
            return pipeline
        budget = max(2, len(pipeline.effects))
        take = max(1, budget - max(0, int(keep)))
        picked = random.sample(members, min(take, len(members)))
        rest = [e for e in pipeline.effects if e not in picked]
        pipeline.effects = list(dict.fromkeys(picked + rest))[:budget]
        return pipeline

    # -- learning from the answer -------------------------------------------
    def observe(self, families, verdict=None):
        """Called once a work's verdict is known. Evidence about a probed
        family answers its question; the probe goes away rather than being
        asked again."""
        for fam in list(families or []):
            for key, probe in list(self.probes.items()):
                if probe["target"] != fam:
                    continue
                if probe["kind"] in ("unexplored", "thin", "stale"):
                    self.probes.pop(key, None)
                    self.answered += 1
                else:
                    # a settled belief is handled by _retire via the episode
                    # count; here we only reduce its pull so one trial does
                    # not monopolise the budget
                    probe["gain"] = clamp01(probe["gain"] - 0.15)

    def report(self):
        rows = self.pending(4)
        if not rows:
            return ["nothing it is actively curious about right now"]
        return [f"{p['kind']:<14} {p['target']:<10} gain {p['gain']:.2f}  {p['why']}"
                for p in rows]

    def snapshot(self):
        return {"coverage": self.coverage(), "value": round(self.value(), 3),
                "answered": self.answered,
                "probes": [(p["kind"], p["target"], round(p["gain"], 2))
                           for p in self.pending(4)]}


# ---------------------------------------------------------- ExperimentPlanner
class ExperimentPlanner:
    """[PHASE 49] Self-directed experiment planning.

    Phases 28/47/48 already let the creature pick two families and run a
    control/variant comparison, sample the underrepresented arm, and let a
    concluded result nudge the genome and become a KnowledgeBase episode.
    What none of that ever wrote down explicitly: WHY this comparison and
    not some other one, WHAT exactly is uncertain, WHAT is being held
    constant so the comparison actually isolates one variable, WHAT result
    would count as decisive, and WHAT the creature expected before it saw
    anything - so that prediction and outcome can be told apart afterward
    instead of the "prediction" quietly becoming whatever happened.

    This is a reader and a designer, not a second memory. Every method here
    reads CuriosityEngine, KnowledgeBase, VisualMemory, StyleGenome and
    SelfModel - state that already exists - and writes back only through
    mechanisms those objects already expose (`VisualMemory.start_experiment`'s
    optional `spec`, `VisualMemory._conclude`, `SelfModel.record_strategy`,
    `CuriosityEngine.observe`). It owns no timer: the studio's existing
    autonomy cooldown decides when the next piece is made; this only decides
    what that piece should be FOR, once the studio has already decided to
    make one."""

    MIN_WORTH = 1.1           # information_gain / cost must clear this to run
    EARLY_MIN_TRIALS = 3      # never conclude on fewer trials than this, per arm
    MIN_TRIALS = 4            # the floor Phase 28 always enforced - unchanged
    MAX_TRIALS = 8            # bounded extension - adaptive sampling never grows past this
    DECISIVE_MARGIN = 0.18    # a gap this large this early is not noise
    CLOSE_MARGIN = 0.05       # same threshold `_conclude` already uses for "inconclusive"

    def __init__(self, brain, memory, engine, style_genome, param_net, curiosity, log=None):
        self.brain = brain
        self.memory = memory                # VisualMemory
        self.engine = engine                # TrippyGramEngine
        self.style_genome = style_genome
        self.param_net = param_net
        self.curiosity = curiosity
        self.log = log or (lambda *_a, **_k: None)

    # -- reading what is already known --------------------------------
    def _recent_test_count(self, control, variant):
        """How many times (running or concluded) this exact pair has already
        been compared - the record VisualMemory.experiments already keeps,
        just read rather than duplicated."""
        pair = frozenset((control, variant))
        return sum(1 for e in getattr(self.memory, "experiments", [])
                  if frozenset((e.get("control"), e.get("variant"))) == pair)

    def _duplicate_running(self, control, variant):
        """#9 - a running experiment already answers substantially this
        question."""
        pair = frozenset((control, variant))
        for e in getattr(self.memory, "experiments", []):
            if e.get("status") == "running" and \
                    frozenset((e.get("control"), e.get("variant"))) == pair:
                return True
        return False

    def _already_known(self, control, variant):
        """#7 - both arms already have real, confident, clearly separated
        evidence, so re-running the same comparison would not teach
        anything the record does not already show."""
        c_conf = self.memory.confidence(control)
        v_conf = self.memory.confidence(variant)
        if c_conf < 0.6 or v_conf < 0.6:
            return False
        return abs(self.memory.score(control) - self.memory.score(variant)) > 0.35

    def _prediction(self, control, variant):
        """The pre-registered guess: expected winner, expected margin, and
        how confident that guess is - blended from measured VisualMemory
        affinity where there is any, and from the slower StyleGenome taste
        vector where there is not yet. Read once, at planning time, and
        never touched again once the experiment starts."""
        c_score, v_score = self.memory.score(control), self.memory.score(variant)
        c_w = self.style_genome.families.get(control, 1.0)
        v_w = self.style_genome.families.get(variant, 1.0)
        c_mix = c_score if self.memory.confidence(control) > 0.2 else (c_w - 1.0) / 2.0
        v_mix = v_score if self.memory.confidence(variant) > 0.2 else (v_w - 1.0) / 2.0
        if v_mix > c_mix + 0.02:
            direction = variant
        elif c_mix > v_mix + 0.02:
            direction = control
        else:
            direction = "inconclusive"
        margin = clamp01(abs(v_mix - c_mix))
        confidence = clamp01((self.memory.confidence(control) +
                              self.memory.confidence(variant)) / 2.0)
        # [PHASE 52] a cold creative comparison is not the same as a blind
        # one if the mind already has real, related evidence about itself.
        # Bounded by SelfModel.MAX_TRANSFER and by how little is measured
        # here, so a well-evidenced pair is never moved by borrowing.
        try:
            _r, borrowed = self.brain.self_model.transfer_prior(
                "making art", self.brain.knowledge)
            confidence = clamp01(confidence + borrowed * (1.0 - confidence))
        except Exception:
            pass
        return direction, margin, confidence

    # -- estimating whether it is worth running ------------------------
    def _information_gain(self, control, variant):
        """Bounded, honest, interpretable - not statistically rigorous.
        Rises with uncertainty and with how much the two arms currently
        disagree; falls the more this exact pair has already been tested."""
        c_conf, v_conf = self.memory.confidence(control), self.memory.confidence(variant)
        evidence = (c_conf + v_conf) / 2.0
        uncertainty = 1.0 - evidence
        disagreement = abs(self.memory.score(control) - self.memory.score(variant))
        gain = 0.20 + uncertainty * 0.45 + disagreement * 0.35
        repeats = self._recent_test_count(control, variant)
        gain -= min(0.5, repeats * 0.15)
        return clamp01(gain)

    def _cost(self, control, variant):
        """A family with little real coverage costs more to compare
        cleanly - the first few pieces from it are noisier before the
        pipeline has settled into what that family actually looks like."""
        unfamiliar = 1.0 - (self.memory.confidence(control) +
                            self.memory.confidence(variant)) / 2.0
        return clamp01(0.30 + unfamiliar * 0.35)

    # -- what stays fixed while the variable changes --------------------
    def _controls_for(self, control, variant):
        """#6 in the phase notes: use the existing parameter machinery to
        name what CAN reasonably be held constant - ParameterNet's own
        continuous params, plus intensity and preset, which the pipeline
        already keeps stable across a run unless the mood itself moves
        them. This does not build a new rendering path; it is a record of
        what `focus()` already leaves alone when it swaps in a family."""
        held = list(ParameterNet.PARAMS) + ["intensity", "preset"]
        return held

    # -- the design itself -----------------------------------------------
    def plan(self, probe=None, fams=None):
        """-> a bounded experiment spec dict, or None if nothing is worth
        running right now. `probe` is a CuriosityEngine probe (or None for
        the ambient genome-extremes comparison the studio already does);
        `fams` is the StyleGenome family ranking, so callers that already
        computed it once do not pay for it twice."""
        fams = fams if fams is not None else sorted(
            self.style_genome.families.items(), key=lambda kv: -kv[1])
        if not fams:
            return None

        if probe is not None:
            variant = probe["target"]
            control = next((f for f, _w in fams if f != variant),
                           fams[0][0] if fams[0][0] != variant else
                           (fams[1][0] if len(fams) > 1 else None))
            if control is None:
                return None
            dimension = "curiosity"
            question = probe["why"]
            base_reason = probe["why"]
        elif len(fams) >= 2:
            control, variant = fams[0][0], fams[-1][0]
            dimension = "family preference"
            question = f"does {variant} actually outperform {control} right now?"
            base_reason = question
        else:
            return None

        if not control or not variant or control == variant:
            return None
        # #9/#8 - a running experiment, or one already answered, settles this
        if self._duplicate_running(control, variant):
            return None
        if self._already_known(control, variant):
            return None

        gain = self._information_gain(control, variant)
        cost = self._cost(control, variant)
        if gain / max(0.1, cost) < self.MIN_WORTH:
            return None

        direction, margin, _conf = self._prediction(control, variant)
        if direction == variant:
            hypothesis = f"{variant} will outperform {control}"
        elif direction == control:
            hypothesis = f"{control} will hold up better than {variant}"
        else:
            hypothesis = f"{control} and {variant} will come out about the same"

        return {
            "dimension": dimension, "control": control, "variant": variant,
            "goal": base_reason,
            "hypothesis": hypothesis,
            "question": question,
            "variable": "effect family",
            "controls": self._controls_for(control, variant),
            "expected_direction": direction,
            "predicted_margin": round(margin, 3),
            "information_gain": round(gain, 3),
            "cost": round(cost, 3),
            "reason": f"information gain {gain:.2f} vs cost {cost:.2f} - {base_reason}",
        }

    def start(self, spec):
        """Turn a plan into an actual running Phase-28 experiment. No new
        scheduler, no new store - the SAME `VisualMemory.start_experiment`
        every earlier phase already used, just handed the fuller design."""
        if not spec:
            return None
        return self.memory.start_experiment(
            spec["dimension"], spec["control"], spec["variant"],
            goal=spec.get("goal", ""), spec=spec)

    # -- adaptive sampling, trial by trial --------------------------------
    def record_trial(self, exp_id, arm, verdict):
        """Append a trial and decide what should happen next: keep the
        existing four-per-arm floor, but let the experiment run longer when
        the evidence is close and still worth the cost, and let it stop
        earlier - conservatively, never before EARLY_MIN_TRIALS per arm -
        when the gap is already too large to be noise."""
        exp = self.memory.record_experiment_trial(exp_id, arm, verdict, auto_conclude=False)
        if exp is None:
            return None
        return self._evaluate(exp)

    def _evaluate(self, exp):
        c_scores, v_scores = exp["control_scores"], exp["variant_scores"]
        nc, nv = len(c_scores), len(v_scores)

        if nc < self.EARLY_MIN_TRIALS or nv < self.EARLY_MIN_TRIALS:
            exp["planner_action"] = ("collect balanced evidence" if abs(nc - nv) > 1 else
                                     ("continue control" if nc <= nv else "continue variant"))
            return exp

        c_mean = sum(c_scores) / nc
        v_mean = sum(v_scores) / nv
        diff = v_mean - c_mean

        # decisive early stop - conservative: requires BOTH a real gap and a
        # real minimum of evidence on both arms, never just "it looked good
        # once"
        if abs(diff) >= self.DECISIVE_MARGIN and nc >= self.EARLY_MIN_TRIALS \
                and nv >= self.EARLY_MIN_TRIALS:
            self.memory._conclude(exp, stopping_reason="evidence was decisive early")
            return exp

        if nc >= self.MIN_TRIALS and nv >= self.MIN_TRIALS:
            if nc >= self.MAX_TRIALS or nv >= self.MAX_TRIALS:
                self.memory._conclude(exp, stopping_reason="reached the sampling cap")
                return exp
            info_gain = exp.get("information_gain", 0.5)
            close = abs(diff) < self.CLOSE_MARGIN
            if close and info_gain < 0.35:
                # #10 - abandon: the gap is tiny and there was never much to
                # learn here even before sampling started
                self.memory._conclude(
                    exp, stopping_reason="too close to matter, not worth the cost")
                return exp
            if close and (nc + nv) >= self.MIN_TRIALS * 2:
                self.memory._conclude(
                    exp, stopping_reason="inconclusive after extended sampling")
                return exp
            # still ambiguous but plausibly worth one more balanced round
            exp["planner_action"] = "collect balanced evidence"
            return exp

        exp["planner_action"] = "continue control" if nc <= nv else "continue variant"
        return exp

    def next_arm(self):
        """[PHASE 49] -> a probe-shaped dict steering the next autonomous
        piece, the same "aim the next piece here" contract Phase 46/47
        already built (`studio_generate` reads `target` and calls
        `curiosity.focus()` with it) - now driven by the planner's own
        per-trial judgement (`planner_action`) instead of only "whichever
        arm has fewer trials so far". Experiments started before Phase 49,
        or a freshly-balanced one, have no `planner_action` yet and fall
        back to that same least-sampled rule."""
        running = [e for e in getattr(self.memory, "experiments", []) if e["status"] == "running"]
        if not running:
            return None
        exp = min(running, key=lambda e: len(e["control_scores"]) + len(e["variant_scores"]))
        action = exp.get("planner_action")
        if action == "continue control":
            arm, fam = "control", exp["control"]
        elif action == "continue variant":
            arm, fam = "variant", exp["variant"]
        else:
            nc, nv = len(exp["control_scores"]), len(exp["variant_scores"])
            arm, fam = ("control", exp["control"]) if nc <= nv else ("variant", exp["variant"])
        why = exp.get("question") or (
            f"testing {exp['control']} against {exp['variant']} - still needs {arm} trials")
        return {"kind": "experiment_arm", "target": fam,
                "gain": exp.get("information_gain", 0.5), "why": why}

    # -- after the result is in -------------------------------------------
    def after_conclusion(self, exp):
        """[PHASE 49] What the planner itself does once Phase 48 has already
        moved the genome and written the KnowledgeBase episode: compare the
        pre-registered prediction against what actually happened, let the
        self-model tell "I tested this against X" apart from a plain
        affinity number, retire the question, and let CuriosityEngine look
        at what the result exposes next. Does NOT start anything - the
        studio's own cooldown remains the only authority over when the next
        piece actually gets made."""
        winner = exp.get("winner")
        control, variant = exp.get("control"), exp.get("variant")
        predicted_dir = exp.get("expected_direction")
        predicted_margin = exp.get("predicted_margin")
        c_mean = float(exp.get("control_mean", 0.5))
        v_mean = float(exp.get("variant_mean", 0.5))
        actual_margin = abs(v_mean - c_mean)

        # PREDICTION -> OUTCOME -> ERROR, kept as its own field rather than
        # folded into or overwriting the original prediction.
        if predicted_margin is not None:
            exp["prediction_error"] = round(abs(actual_margin - float(predicted_margin)), 4)
        if predicted_dir is not None:
            exp["prediction_correct"] = (
                (winner == predicted_dir) if winner not in (None, "inconclusive") else None)

        # SELF-MODEL: "I know this because I tested it against X under these
        # conditions" is a more specific, better-earned claim than "I know
        # this family performs well" - recorded as its own strategy entry,
        # never overwriting the plain per-effect affinity VisualMemory and
        # StyleGenome already keep.
        if winner and winner not in (None, "inconclusive"):
            loser = variant if winner == control else control
            try:
                self.brain.self_model.record_strategy(
                    f"family:{winner}", f"tested_against:{loser}", True)
                self.brain.self_model.record_strategy(
                    f"family:{loser}", f"tested_against:{winner}", False)
            except Exception:
                pass

        # retire the question this experiment stood in for, and let curiosity
        # surface whatever the result itself exposed (a family that just won
        # a controlled comparison but is still thin on raw episodes, say) -
        # it is free to pick that up on its own next `select()`, nothing here
        # chains a new experiment or a new generation.
        try:
            self.curiosity.observe([f for f in (control, variant) if f])
            self.curiosity.scan()
        except Exception:
            pass


def dominant_families_from_names(names, engine):
    """Which families a set of effect names actually drew from, ranked by
    count - the shared vocabulary Provenance, the genome, KnowledgeBase cues
    and territory-discovery all key off."""
    index = engine.families() if engine else {}
    names = set(names or [])
    counts = {}
    for fam, members in index.items():
        n = sum(1 for m, _fn in members if m in names)
        if n:
            counts[fam] = n
    return [f for f, _n in sorted(counts.items(), key=lambda kv: -kv[1])]


def dominant_families(pipeline, engine):
    """Same as above, for a TrippyGramPipeline."""
    if pipeline is None:
        return []
    return dominant_families_from_names(pipeline.effects, engine)


def creative_cues(pipeline, engine, territory=None):
    """-> cue list for KnowledgeBase.predict/add_episode/test - the thin
    translation layer Phase 11 calls for, additive to CreativeMemory, no
    change to KnowledgeBase's own internals."""
    fams = dominant_families(pipeline, engine)[:2]
    cues = [f"family:{f}" for f in fams]
    if territory:
        cues.append(f"territory:{territory}")
    return cues or ["family:other"]


def _console_curiosity_lines(app):
    """[PHASE 46] What it currently does not know, as real measured gaps."""
    cur = getattr(app, "curiosity", None)
    if cur is None:
        return []
    try:
        cur.scan()
        snap = cur.snapshot()
        return (["", f"CURIOSITY  coverage {snap['coverage']:.0%} of the family "
                     f"space · {snap['answered']} question(s) answered"]
                + ["  " + line for line in cur.report()])
    except Exception:
        return []


def build_similarity_report(app, query):
    """[PHASE 53] `similar to X` answered from the derived index - real
    vectors over real records, no generated text."""
    vm = getattr(app, "visual_memory", None)
    if vm is None or getattr(vm, "index", None) is None:
        return "(no visual memory in this session)"
    try:
        entry, rows = vm.similar_query(query, k=5)
    except Exception as exc:
        return f"(similarity lookup failed: {exc})"
    if entry is None:
        return f"(nothing in the index matches '{query}')"
    if not rows:
        return f"{entry['label']} ({entry['kind']}) - nothing else indexed yet"
    out = [f"most like {entry['label']} ({entry['kind']}):"]
    for sim, e in rows:
        out.append(f"  {sim:.0%}  {e['label']}  [{e['kind']}]")
    return "\n".join(out)


def build_console_report(app):
    """[PHASE 43] Console - a genuine inspection of real runtime state: the
    taste vector, discovered territories, motifs, and the creative domain of
    SelfModel/KnowledgeBase. Nothing here is generated text; every line is
    read straight out of the objects it names."""
    lines = ["=== STUDIO CONSOLE ==="]
    vm_i = getattr(app, "visual_memory", None)
    if vm_i is not None and getattr(vm_i, "index", None) is not None:
        try:
            n = len(vm_i.index.ensure())          # [PHASE 53]
            lines.append(f"similarity index: {n} embedded item(s) - "
                         f"ask 'similar to <name>'")
        except Exception:
            pass
    meta = getattr(app, "meta_learner", None)
    if meta is not None:
        try:
            lines += ["how the learning itself is doing:"] + \
                     ["  " + ln for ln in meta.report()]      # [PHASE 54]
        except Exception:
            pass
    try:
        lines += ["market (reporting only):"] + \
                 ["  " + ln for ln in build_market_report(app)]     # [PHASE 64]
        inter = getattr(app, "inter", None)
        if inter is not None:
            lines += ["  " + ln for ln in inter.report()]           # [PHASE 65]
    except Exception:
        pass
    genome = getattr(app, "style_genome", None)
    if genome:
        lines.append(f"style genome: gen {genome.generation}, "
                     f"leaning {genome.signature()}")
        if genome.log:
            lines.append("  last shift: " + genome.log[-1][1])
    vm = getattr(app, "visual_memory", None)
    if vm:
        st = vm.stats()
        lines.append(f"works archive: {st['works']} pieces, {st['liked']} kept, "
                     f"{st['effects_rated']} effects rated")
        motifs = vm.motifs()
        if motifs:
            lines.append("motifs (recurring, rewarded pairs): " + "; ".join(
                f"{a}+{b} ({s:+.2f}, x{n})" for a, b, s, n in motifs[:4]))
        if vm.territories:
            lines.append("discovered territories: " + ", ".join(
                f"{t['name']} (x{t['uses']})" for t in vm.territories[-5:]))
        try:
            portfolios = vm.build_portfolios()
            if portfolios:
                lines.append("curated portfolios: " + "; ".join(
                    f"{p['name']} ({p['size']} pieces, coherence {p['coherence']:.0%})"
                    for p in portfolios[:3]))
        except Exception:
            pass
        running = [e for e in getattr(vm, "experiments", []) if e["status"] == "running"]
        done = [e for e in getattr(vm, "experiments", []) if e["status"] == "concluded"]
        if running:
            lines.append("running experiments:")
            for e in running:
                n_c, n_v = len(e.get("control_scores", [])), len(e.get("variant_scores", []))
                bit = f"  {e['control']} vs {e['variant']} ({n_c}c/{n_v}v trials)"
                if e.get("hypothesis"):
                    bit += f" - hypothesis: {e['hypothesis']}"
                lines.append(bit)
        if done:
            lines.append("concluded experiments:")
            for e in done[-3:]:
                bit = (f"  {e['control']} vs {e['variant']} -> {e.get('winner','?')}"
                      f" ({e.get('stopping_reason', 'minimum sample reached')})")
                if e.get("expected_direction"):
                    correct = e.get("prediction_correct")
                    tag = ("predicted correctly" if correct else
                          "prediction was wrong" if correct is False else "prediction unclear")
                    bit += f" - predicted {e['expected_direction']}, {tag}"
                    if "prediction_error" in e:
                        bit += f" (margin error {e['prediction_error']:.2f})"
                lines.append(bit)
    try:
        projects = app.brain.goals.projects()
        if projects:
            lines.append("active creative projects: " + "; ".join(
                f"{p['name']} ({p.get('milestones_done',0)}/{p.get('milestones_total','?')}, "
                f"{p['status']})" for p in projects))
    except Exception:
        pass
    try:
        comp, conf, borrowed = app.brain.self_model.competence_with_transfer(
            "making art", app.brain.knowledge)          # [PHASE 52]
        if conf > 0.05:
            line = (f"self-assessed skill at making art: {comp:.0%} "
                    f"(confidence {conf:.0%})")
            if borrowed > 0.0:
                line += f" - {borrowed:.0%} of that is borrowed from related domains"
            lines.append(line)
    except Exception:
        pass
    try:
        beliefs = [h for h in app.brain.knowledge.beliefs(8)
                  if h.cue.startswith(("family:", "territory:"))]
        if beliefs:
            lines.append("creative hypotheses:")
            for h in beliefs[:4]:
                lines.append(f"  [{h.status}] {h.text()}")
    except Exception:
        pass
    recent = (vm.works[-3:] if vm and vm.works else [])
    if recent:
        lines.append("recent provenance:")
        for w in recent:
            prov = w.get("provenance", {})
            lines.append(
                f"  {Path(w.get('path','?')).name if w.get('path') else '(unsaved)'}: "
                f"trigger={prov.get('trigger','?')} "
                f"territory={prov.get('territory') or '-'} "
                f"hypothesis={prov.get('hypothesis') or '-'} "
                f"verdict={w.get('verdict', 0):.2f}")
            if w.get("claude_critique"):
                lines.append(f"    Claude (external commentary): {w['claude_critique']}")
    lines.extend(_console_curiosity_lines(app))
    return "\n".join(lines)


# ------------------------------------------- in-process ACACIA bridge
# The engine section above contains an optional bridge that talked to a
# separate ACACIA process through ~/.acacia/trippygram_bridge.json.  Inside
# this merged application there is no second process: the host IS Acacia.
#
# The original file-based implementations are kept (renamed) so nothing is
# lost and an external Acacia instance still works when this file is used as
# an importable module; the names the TrippyGram UI calls are re-pointed to
# the live host, so its connection indicators report the real model manager
# instead of a heartbeat file.

_tg_file_bridge_is_running = bridge_acacia_is_running
_tg_file_bridge_status = bridge_get_acacia_status
_tg_file_bridge_shutdown = bridge_shutdown

_ACACIA_HOST = None          # set by App.__init__


def acacia_register_host(app):
    """Called once by the host application at startup."""
    global _ACACIA_HOST
    _ACACIA_HOST = app


def acacia_host():
    return _ACACIA_HOST


def bridge_acacia_is_running() -> bool:          # noqa: F811 - deliberate override
    """True whenever the host is up, which in-process it always is."""
    if _ACACIA_HOST is not None:
        return True
    try:
        return _tg_file_bridge_is_running()
    except Exception:
        return False


def bridge_get_acacia_status() -> dict:          # noqa: F811 - deliberate override
    """Report the live host: backend, model, mood, and whether it is busy."""
    app = _ACACIA_HOST
    if app is None:
        try:
            return _tg_file_bridge_status()
        except Exception:
            return {}
    out = {"running": True, "in_process": True, "app": APP_TITLE}
    try:
        mm = getattr(app, "models", None)
        if mm is not None:
            out["provider"] = mm.current_key
            try:
                out["model"] = mm.current.describe()
            except Exception:
                out["model"] = mm.current_key
            ok, reason = mm.status()
            out["ready"] = bool(ok)
            out["detail"] = reason
    except Exception:
        pass
    try:
        snap = app.brain.snapshot()
        out["mood"] = snap.get("emotion")
        out["mood_word"] = snap.get("mood_word")
        out["busy"] = bool(getattr(app, "busy", False))
    except Exception:
        pass
    return out


def bridge_shutdown():                            # noqa: F811 - deliberate override
    try:
        _tg_file_bridge_shutdown()
    except Exception:
        pass


def acacia_is_loaded() -> bool:                   # noqa: F811 - deliberate override
    """The TrippyGram AI panels use this to decide whether an Acacia brain is
    reachable.  In-process, it is."""
    return _ACACIA_HOST is not None or _acacia_mod is not None


def acacia_host_complete(prompt, system="", max_tokens=400, timeout=90):
    """Let the TrippyGram side ask the HOST's model manager for text.

    This is the in-process replacement for shelling out to a separate Acacia:
    same backends (local GGUF / Ollama / Claude / Gemini), same settings, one
    process.  Blocking - call it from a worker, never from the UI thread."""
    app = _ACACIA_HOST
    if app is None or getattr(app, "models", None) is None:
        return None, "no host model manager"
    try:
        text, err = app.models.generate(
            system or "You are a concise, imaginative visual director.",
            [{"role": "user", "content": str(prompt)}],
            int(max_tokens), lambda _t: None, lambda: False)
        return text, err
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _acacia_restyle_host():
    """Re-assert the host's ttk styles after the embedded engine writes the
    base ones.  Harmless when there is no host."""
    app = _ACACIA_HOST
    if app is None:
        return
    try:
        app._build_styles()
    except Exception:
        pass


# ------------------------------------------------- embedding the TG window
class TrippyGramHost(tk.Frame):
    """A Frame that can stand in for a Tk root.

    The original TrippyGramApp builds itself against `self.root`, using it as
    a widget parent and calling .after / .clipboard_get / .configure on it,
    plus a handful of window-manager calls (title, geometry, resizable,
    protocol, mainloop) that only make sense for a real toplevel.

    Subclassing Frame means every parenting call and every .after works
    unchanged; the window-manager calls are swallowed here.  That is what
    lets the entire original TrippyGram interface live inside a CREATURE tab
    without editing its 8,000 lines of UI code."""

    def title(self, *_a, **_k):
        return APP_TITLE

    def geometry(self, *_a, **_k):
        return ""

    def resizable(self, *_a, **_k):
        return ("1", "1")

    def minsize(self, *_a, **_k):
        return None

    def maxsize(self, *_a, **_k):
        return None

    def protocol(self, *_a, **_k):
        return None

    def iconbitmap(self, *_a, **_k):
        return None

    def iconphoto(self, *_a, **_k):
        return None

    def wm_attributes(self, *_a, **_k):
        return None

    attributes = wm_attributes

    def state(self, *_a, **_k):
        return "normal"

    def deiconify(self, *_a, **_k):
        return None

    def withdraw(self, *_a, **_k):
        return None

    def mainloop(self, *_a, **_k):
        # the host already owns the event loop
        return None

    def quit(self, *_a, **_k):
        return None
