# ACACIA — architecture state

Read this first. It exists so a future session (human or Claude) can open two
or three files instead of 35,000 lines.

## Layout

```
acacia.py                 launcher — the file you run
acacia_unified.py         the original monolith, kept for verification
STATE.md                  this file
acacia/
    __init__.py           the ONE piece of glue (shared-namespace loader)
    _manifest.py          load order: MODULES (original slices) + PATCHES
    m00_preamble.py …     34 verbatim slices of the original, in file order
    m33_app.py
    m34_poly_physics.py   the only NEW file — polygon/physics HD renderer
tools/
    split.py              regenerates the slices from the monolith
    verify.py             proves the package == the monolith
    stubs/tkinter/        test-only tkinter stand-in (never shipped)
```

## What happened

`acacia_unified.py` (35,126 lines, one file) was cut into 34 modules. **No
original behaviour was changed, and nothing was removed.** Cuts were made only
at line boundaries that the splitter proved no top-level statement crosses, and
every module is a byte-for-byte slice — no reindenting, no import fixups, no
rewriting. All 35,126 lines are accounted for exactly once.

Verified, not assumed (`python3 tools/verify.py`):

```
original top-level names : 657
package  top-level names : 657
missing: []      extra: []
callables compared: 424      source mismatches: []
constant-value diffs: []
RESULT: IDENTICAL
```

That compares the live package against the monolith executed in the same
process: same 657 top-level names, and every function and class body
byte-identical via `inspect.getsource`.

Functional smoke tests that passed: `--effects` lists all 183 effects;
`generate_nft_with_effects` renders a real 1080×1080 NFT end to end; `Brain`
runs 120 ticks; `Settings`, `CreatureVisualState`, `VisualMemory` and
`TrippyGramEngine` all construct; `use_instance()` rebinding is visible from
every slice.

## The one non-obvious trick: one namespace, not an import chain

The original was a single script, so every section shared one globals dict.
Three things depend on that, and all three break under an ordinary
ordered-import split:

1. **Forward references.** Code near the top calls names defined near the
   bottom. Legal in one file because the lookup happens at call time.
2. **`globals().get(...)`.** Used in ~15 places (sections [6.5] and [12]) to
   fetch `EFFECTS`, `EFFECT_MAP`, `FX_FAMILY_KEYWORDS`, `np`, `Image` at call
   time.
3. **Runtime `global` rebinds.** `use_instance()` in `[0]` rebinds
   `STATE_FILE`, `MEMORY_FILE`, `INSTANCE_DIR` and nine more. Every other
   section reads those names. A split that copies namespaces would leave the
   copies stale the moment the instance is switched — a silent, data-losing
   bug, not a cosmetic one.

So `acacia/__init__.py` does not import the slices; it **executes them, in
order, into one shared dict** (`acacia.NS`), then publishes each slice in
`sys.modules` as a *view* onto that dict. Ordinary imports keep working:

```python
from acacia.m33_app import main
from acacia.m18_renderer import Creature
import acacia; acacia.NS["EFFECT_MAP"]          # the shared namespace itself
```

and `acacia.m01_config.STATE_FILE is acacia.m04_memory.STATE_FILE` is `True`,
live, after a rebind. While a slice executes, `NS["__name__"]` is pointed at
that slice, so classes get a `__module__` that resolves to the file they are
actually written in — tracebacks, `inspect.getsource` and pickling all land in
the right place.

**Do not** replace this with per-module imports and a namespace back-fill. A
back-fill is a snapshot; it fixes forward references but not item 3 above.

## Module map (top-to-bottom = the original file's line order)

| Module | Original section | Responsibility |
|---|---|---|
| `m00_preamble.py` | imports + pre-[0] | stdlib/tkinter/PIL/numpy/cv2/selenium/tkinterdnd2 imports (all optional deps behind `HAS_*` flags), `compute_capability` / GPU-offload planning |
| `m01_config.py` | [0] | config, util, persistence: paths, JSON load/save, `Settings`, `use_instance()` |
| `m02_events.py` | [1] | `Event` + perception — raw happenings become structured events |
| `m03_emotion.py` | [2] | emotion: smoothed sticky affect with hysteresis and momentum |
| `m04_memory.py` | [3] | short-term + scored long-term memory, persisted across launches |
| `m05_inner_life.py` | [3.5] | idle simulation: time awareness, interests, daydreaming |
| `m06_personality.py` | [3.6] | stable traits that slowly evolve from experience |
| `m07_relationships.py` | [3.7] | relationships + friends — the social world's building blocks |
| `m08_needs_goals.py` | [4] | needs + goal system |
| `m09_decision.py` | [5] | decision layer: shapes behaviour and how the creature talks |
| `m10_snapshots_marketplace.py` | [4.9] | snapshots · marketplace · inter-creature (phases 62–65) |
| `m11_attention.py` | [5.5] | attention: a finite budget spent on what matters now |
| `m12_spiking_net.py` | [6] | the original spiking neural net (preserved) |
| `m13_knowledge.py` | [6.4] | knowledge: entities, places, falsifiable hypotheses, plans |
| `m14_cognition.py` | [6.5] | cognition: world model / self model / prediction / planning |
| `m15_brain.py` | [7] | `Brain` — ties emotion/memory/needs/decision/cognition together |
| `m16_model_backends.py` | [8] | LLM backends (LOCAL GGUF / OLLAMA / CLAUDE / GEMINI), GGUF + model managers |
| `m17_social_world.py` | [8.5] | social world: friend-to-friend interactions |
| `m18_renderer.py` | [9] | `Creature` — procedural segmented anatomy over a 2D rig (the in-app creature, **not** the NFT renderer) |
| `m19_world.py` | [9.5] | world: environment, lighting, vegetation, points of interest |
| `m20_friend_actors.py` | [9.6] | friends as real bodies in the world, not list rows |
| `m21_brain_view.py` | [9.7] | anatomical brain-activity render |
| `m22_ui_toolkit.py` | [10] | shared UI widgets / toolkit |
| `m23_live_mode.py` | [10.5] | live mode: real-time computer-interaction awareness |
| `m24_computer_agent.py` | [10.5] | computer agent: event-driven awareness of the host machine |
| `m25_fx_core.py` | [11.5a] | the original 50 `fx_*` effects |
| `m26_nft_character.py` | [11.5b] | NFT HD patch: `NFT_TRAIT_CONFIG`, `_SCHEME_PALETTES`, the classic 3× supersampled `generate_nft_character`, `generate_nft_with_effects`, v6/v7 fx batches |
| `m27_fx_registry.py` | [11.5c] | `EFFECTS` / `EFFECT_NAMES` / `EFFECT_MAP` / `INTENSITY_FX` + `_nft_standalone_test` |
| `m28_media_pipeline.py` | [11.5d] | `generate_trippy`, OpenCV video pipeline, NFT reel generator |
| `m29_posting.py` | [11.5e] | Selenium automation — Instagram / Facebook / X posting |
| `m30_bridge_helpers.py` | [11.5f] | TrippyGram-side Acacia bridge helpers, AI-generated NFT traits |
| `m31_trippygram_app.py` | [11.5g] | `IGSession`, `TrippyGramApp` — the original TrippyGram interface, embedded |
| `m32_acacia_bridge.py` | [12] | **the joint**: `CreatureVisualState` (mind → visual params), the mind-to-engine call path, `VisualMemory` (visuals → mind, effect scoring) |
| `m33_app.py` | [11] | `App` — the merged application window; `main()` — the entry point |
| `m34_poly_physics.py` | **new** | polygon mesh renderer + Verlet physics; overrides the HD NFT path (below) |

`acacia/__init__.py` and `acacia/_manifest.py` are not sections of the original
file — they are the loader described above.

## `m34_poly_physics.py` — the new HD renderer

The old HD path supersampled 3× and downscaled, which made edges crisp but
left the *surface* flat: every part was one solid fill with a rounded-rectangle
outline. Nothing caught light, nothing hung, nothing had geometry. "HD" meant
resolution only.

This module adds:

1. **A real (small) 3D pipeline.** Meshes of explicit `(x, y, z)` vertices —
   `mesh_lathe`, `mesh_ellipsoid`, `mesh_capsule`, `mesh_prism`,
   `mesh_from_grid` — perspective projection, painter depth sort, auto-framing
   camera (`Camera.fit`), and **per-facet flat shading** off each polygon's own
   true surface normal: Lambert key + fill, Blinn specular (metal-tinted for
   metals), Fresnel rim, depth-based ambient occlusion and distance fog.
   Per-facet, non-interpolated shading is what produces the faceted look.
   `Mesh.jitter` displaces vertices along their radial normal so a smooth lathe
   becomes a hand-cut solid.
2. **A Verlet physics solver.** Particles, distance + bend constraints,
   gravity, coherent value-noise wind, air drag, and sphere/capsule collision
   against the character's own body. Builders: `VerletWorld.strand` (hair,
   whiskers, antennae, chains) and `VerletWorld.cloth` (capes, hoods, scarves,
   with structural/shear/bend constraints). The rig is **settled** (~220 steps)
   and the rest pose is what gets rendered, then skinned into real polygons —
   `strand_mesh` makes tapered tubes, `mesh_from_grid` turns the settled cloth
   into quad facets whose normals are the actual folds.
3. **Species-driven anatomy.** `_SPECIES_SHAPE` / `_SURFACE_TWEAK` map the
   `Species` trait onto skull proportions, jaw, muzzle length, ear kind, horns
   and surface material (plates / smooth / ridged / scaled / furred / bone).
   All features are measured off one `face_z` plane so nothing ends up drawn
   behind the jaw it should sit in front of.
4. **A faceted low-poly background** (`render_poly_background`) and a contact
   shadow derived from the settled silhouette.

Entry points:

```python
generate_nft_character(size, seed, override_traits)   # now routes to poly
generate_nft_character_poly(...)                      # same signature/return
generate_nft_character_classic(...)                   # the original, untouched
render_poly_physics_portrait(traits, size, seed)      # bare RGBA character layer
poly_hd(False)                                        # toggle at runtime
```

`generate_nft_character` keeps its exact signature and `(PIL.Image, traits)`
return, so every existing caller — the NFT batch, `generate_nft_with_effects`,
the reel pipeline, the TrippyGram UI, the Acacia bridge — picks it up with no
changes.

Knobs (env vars, read at import):

| Variable | Default | Meaning |
|---|---|---|
| `ACACIA_POLY_HD` | `1` | `0` restores the classic renderer as default |
| `ACACIA_POLY_SS` | `4` | internal supersample factor |
| `ACACIA_POLY_SETTLE` | `220` | physics settle steps |
| `ACACIA_POLY_TESS` | `1.0` | tessellation density multiplier |
| `ACACIA_NO_PATCHES` | `0` | `1` loads only the original slices |

A 1080 portrait is ~5,500 facets / 330 particles / 890 constraints and takes a
few seconds on CPU. If anything in the poly path raises, it prints a warning
and falls back to the classic renderer — it can't take the app down.

## Running it

```bash
python acacia.py                  # the merged application window
python acacia.py --effects        # list the 183 effects and exit
python acacia.py --test-nft       # NFT batch, no UI (uses the poly renderer)
python acacia.py --test-poly      # poly/physics HD path only  [--n N --size S]
python acacia.py --classic ...    # any of the above, classic HD renderer
```

## Working with this codebase

- **Open only the module whose responsibility matches the task.** Use the table
  above. Changing one effect, one memory-scoring rule or one dialog does not
  require reading the package.
- **Cross-references between modules just work.** Treat `acacia/` as one
  namespace. A name defined in `m19_world.py` is visible from a function in
  `m01_config.py` at call time. **Do not add imports between `mNN_*` files** —
  they are not importable in isolation by design.
- **Do not reorder or renumber the `mNN_*` files**, and do not reorder
  `MODULES` in `_manifest.py`. That order is the original file's line order and
  it is what makes definition-time evaluation come out the same.
- **New code**: prefer the most relevant existing module. A genuinely new
  subsystem that only needs to be *called* (no definition-time dependency on
  later sections) goes in `PATCHES` at the end, like `m34`. One that must be
  defined mid-chain goes in at the right position, with everything after it
  renumbered and this table updated.
- **The large modules** (`m26`, `m31`, `m29`, `m16`, `m15`) are large because
  they are one class or one registry in the original (all effects live in one
  dict; `TrippyGramApp` is one big UI class). Splitting further would mean
  splitting a single class body — deliberately not done, since that is the one
  edit that could change behaviour.
- **Overriding original behaviour**: define the replacement in a `PATCHES`
  module and keep the original reachable under a `*_classic` name, as `m34`
  does. Never edit an original slice — that breaks `tools/verify.py`.

## Re-verifying

```bash
python3 tools/verify.py                      # with the patch layer loaded
ACACIA_NO_PATCHES=1 python3 tools/verify.py  # original slices only — exact
```

Both must end in `RESULT: IDENTICAL`. The first tolerates the one documented
override (it compares `generate_nft_character_classic` against the original
`generate_nft_character`) and reports how many names the patch layer added.

To regenerate the slices from scratch after editing the monolith:

```bash
python3 tools/split.py && python3 tools/verify.py
```

`tools/split.py` refuses to cut inside a top-level statement and asserts that
every line of the original is accounted for exactly once.

## Known environment notes

- PIL / numpy / cv2 / selenium / tkinterdnd2 are all optional, each guarded in
  `m00_preamble.py` behind `try/except` and a `HAS_*` flag, exactly as in the
  original. Nothing became a hard dependency. The poly renderer needs PIL and
  degrades to the classic path without it.
- `tkinter` (stdlib) is required to run anything, including `--effects`,
  because `m00_preamble.py` imports it unconditionally — same as the original
  file. On Debian/Ubuntu that is the `python3-tk` system package.
- `tools/stubs/tkinter/` is a test-only stand-in used to exercise the package
  on a machine without `python3-tk`. It is not part of `acacia/` and must never
  be on the path in production.

## Patch layer: m35_camera_world + m36_living_mind

Both are PATCHES (loaded after the original slices; `ACACIA_NO_PATCHES=1`
disables them). Original slices are untouched - `tools/verify.py` reports
IDENTICAL with and without patches.

**m35_camera_world** - renderer
- `StageCamera` (WASD / drag / wheel / Space / F), NOT named `Camera`:
  m34 owns `Camera(width, height, focal, dist)` in the shared namespace and
  polyHD resolves it by name at call time. Reusing the name crashed polyHD.
- `_CamCanvasProxy` keeps each world item's WORLD coordinates so
  `reproject()` moves the scenery when the camera changes, and `apply_sway()`
  bends classified trees/grass in the wind. The creature uses a separate,
  untracked proxy.
- Creature / atmosphere / night-grade items are POOLED: allocated once, then
  only moved. Steady-state frames create and delete nothing (the old
  per-frame stippled grade rectangle exhausted Windows GDI).
- Pool stacking: pooled items keep creation order, so `_restack_if_needed()`
  re-raises in draw order when the sequence of drawn kinds changes. Keep
  conditional detail ALWAYS emitted (zero-size when off) to avoid restacks.
- Stage layering each frame: world -> worlddyn -> grade -> atmo_back ->
  creature -> actor -> atmo_front -> overlay.

**m36_living_mind** - weather + mind
- `WeatherSim` owns weather (m35's `_update_world` uses it instead of the
  random pick) and emits Events into `Brain.perceive`.
- `LivingMind` (brain.mind): triggers, habits, routines, anticipation,
  conflict, risk, thermal comfort + outfit, day variation, reflection,
  thought stream. Acts on decisions only via `DecisionSystem._behavior_utilities`.
- All mind timing uses `brain.age_seconds` (simulated clock), like EmotionSystem.
- Personality JSON: schema `acacia.personality/2`; drop zone + export on the
  PERSONALITY tab; inner-life panel on the MIND tab. State in `living_mind.json`.
- The TrippyGram TAB is disabled (engine kept - STUDIO uses it).

### Polish pass: no stipple, emotional inertia, continuous expression, paste
- **No Tk stipple anywhere in the render path.** Stipple is Tk's only
  "transparency" and renders as a screen-door dot pattern on Windows.
  Night/storm darkness, distance haze/fog, dawn/dusk warmth and lightning
  are a per-item COLOUR GRADE (`SceneGrade`), applied by the proxy when the
  quantised grade changes (not per frame). The proxy strips `stipple` from
  any caller, including m19's picked-over-POI overlay (drawn as a ring).
- Tk on Windows has no anti-aliasing; organic silhouettes use Tk spline
  smoothing (`smooth=True` on the pooled `_poly`) instead.
- **Emotional inertia**: `_lm_apply_inertia()` sets EmotionSystem's exposed
  per-instance knobs (profile `temperament.inertia`, default 0.6) and adds a
  RETURN COOLDOWN in `_select` (no A->B->A bounce). Startles still interrupt.
- **Continuous expression**: `ExpressionLayer` blends all emotions with
  rise 2.4 s / fall 9 s; the creature reads `creature._affect`, never the
  label. Skin is a stable seeded tone (emotion = flush/pallor only). Brow
  channels: `brow_in` (worry lift) and `knit` (anger) kept separate.
- **Paste**: stage takes focus on click only (hover-to-focus stole focus from
  text fields). Every `_entry` gets a right-click menu, layout-independent
  Ctrl+V (Windows VK 86) and, for masked fields, whitespace stripping.

### Multiplayer + hands + key field
- **m37_lan**: LAN shared world. UDP 47811 discovery, TCP 47812 JSON lines,
  private/loopback/link-local peers only (no UPnP/port mapping). 3-digit PIN
  = pairing code (not security) + explicit host confirmation dialog.
  `lan_clean_state()` whitelists everything sent AND received. Remote
  creatures use the same `Creature` class (own untracked proxy). Peer
  timeout 6 s, pairing 45 s, 3 reconnect tries, `bye` on close.
- Hands: `_cr_draw_hand` - palm + 4 fingers (real length ratios, 3
  phalanges, one `_chain_skin` each) + thumb from palm base; old outlined
  elbow/shoulder joint circles removed.
- API key: Tk clipboard falls back to native CF_UNICODETEXT; a key saved in
  the MODELS tab outranks a (possibly stale) ANTHROPIC_API_KEY env var;
  commits on paste/Enter/focus-out; PASTE + TEST buttons with status.

### Visibility + gait fixes
- The MODELS tab is not scrollable and its GGUF list stretches, so anything
  added at its bottom is off-screen. The Claude key box now lives in the
  backend STATUS card (`_ln_key_row`); networking is its own LOCAL NETWORK tab.
- Gait: `_ik2` bend sign was inverted (knees bent backwards both ways).
  Knees use `-facing`, elbows `+facing`; fractional bend = smooth turn;
  soft IK past 92% reach removes the knee pop; heel-toe roll via
  `_loco.pitch` + `_rot_begin/_rot_end` about the ankle.

### Jane (m38_jane)
- Permanent identity: Jane, adult (28), INTJ; applied once via apply_profile
  (settings flag `jane_identity_v1`). Clothed, glamorous styling; appeal is
  proportion, styling and body language - no explicit content.
- Body via `Creature.SHAPE` (hip/waist/rib/bust/hip_span/shoulder/jaw/nose/
  lips/sway/stride/stance); garments/hair/makeup replace the Creature
  `_draw_*` methods; `_heel()` lifts the body and pitches the foot.
- Gait fixes found while doing this: hip height now derives from leg length
  (feet used to hover); feet step from their OWN hip; bounded compass-gait
  pelvis drop; planted-foot pivot when turning; `_damp_joint` (35 ms
  direction easing, exact bone length) removes one-frame knee/elbow snaps.

### Adult anatomy (one unit: H = head height)
- `_pose` builds an 8-head skeleton from H (`_H()`, `_leg_len()`,
  `_arm_len()`, `_leg_wid()`, `_arm_wid()`); SHAPE hip/waist/rib are
  half-widths in H. Head drawn at exactly H (scale H/55.5, chin on the neck).
  Feet use unit H/17.5, body details H/22, palm 0.4H. Never reintroduce
  fixed-pixel segment lengths - that is what made the 4.3-head chibi figure.
- Gait in H: stride 2.1H*shape, lift 0.25H (floor 0.4 while stepping),
  foot rest/own-hip +/-0.36H*hip_span, speed scale SHAPE["speed"].
- Stopped mode: a foot caught mid-swing comes down where it is; settle to
  rest only after 0.3 s still (approach() is EXPONENTIAL - rates are 1/s).
- Compass drop eased per tick (tau 0.03 down / 0.12 up); sit blend is
  linear progress + smoothstep; no travel until sit < 0.12.
- Click hit-test: `creature._bbox` (whole body) mapped onto the original
  90px circle in the camera click wrapper.

### Jane's look (reference aesthetic, procedural)
- Back hair is drawn FIRST in draw() (behind legs/torso); pigtails, wisps
  and makeup are drawn in the head scope after the face.
- Style: twin high pigtails (+ ties, heart clips), centre part, big doe eyes
  (SHAPE eye_scale/iris), pink shadow + black wing + white inner/lower liner,
  strong blush, glossy red lips, pastel strappy cami with lace/bow/strawberry
  print, layered necklaces. Reference used for aesthetic only, no likeness.

### Face HD, terrain grounding, follow camera
- Jane's head uses `_draw_face_hd` (m38) via SHAPE["face_hd"]: layered
  planes lit from _KEY_LIGHT; eyes = socket -> sclera -> iris -> upper/lower
  LID OCCLUDERS (blink = lid descending); nose bridge/tip/wings/nostrils;
  volumetric lips; brows on the ridge; hair from a hairline root band.
  The legacy skin pass (stubble, wrinkles, straight scalp strands) is not
  used for Jane.
- Feet stand on `_terrain_at(x)` (App installs `_terrain_fn` from
  world.ground each frame; remote Janes too); foot pitch includes terrain
  slope. No whole-body sine bob.
- StageCamera: follow ON by default, zoom 1.15, critically damped spring,
  look-ahead, body framed slightly low; TARGET clamped to the world rect
  (smooth at edges) + hard clamp safety. Manual WASD/drag pauses follow 2.5s.
- Visual testing: /tmp harness rasterises the real canvas calls with PIL
  (Tk spline smoothing reproduced) - see test notes in this session.

### Living world (m39_living_world)
- World.rebuild replaced (classic kept as World._rebuild_classic): fine sky
  gradient + horizon haze, corona, 4 midpoint-displacement ranges with rim
  light, snow, atmospheric perspective and forested near hills; depth-layered
  pines/broadleaf trees, bushes, rocks, flowers, grass, worn path. Near
  trees/grass passed to wind sway via world._sway_hint.
- Fauna (App.fauna): FAUNA table (rabbit, deer, fox, wolf, bird, butterfly,
  firefly). Spawn by daypart/weather/capacity + breeding; per-animal state
  machine; fox hunts rabbits; threat appraisal of Jane with per-species
  familiarity (persisted in living_mind.json "fauna"). Jane perceives via
  Brain.perceive + knowledge.see("animal", sp); wolves at night raise risk.
  Rendered via _AtmoPool through the camera, tag "fauna", colour-graded.

### Survival + campfire (m39)
- App.survival (Survival): inventory wood/berries; needs-driven planner
  (dark/cold -> gather wood at trees -> build fire near shelter; hungry ->
  gather berries at the food POI -> cook at the fire; night -> warm/sit by
  fire). Biases DecisionSystem utilities via mind.survival_bias; its target
  is re-applied after App._world_step. Campfire: fuel, rain/wind response,
  warmth into ThermalComfort (fire_heat), firelight lowers Jane's night
  grade, animals keep away; drawn sized to H. Far leg drawn first + shaded
  (Creature._far/_depth_order); rounded shoulder caps.
- Optional hunting (settings "hunting_enabled", MIND-tab checkbox, off by
  default): craft reed bow (2 wood) -> stalk (pace x0.45) -> aim pose
  (Creature._aim: bow arm to target, string hand drawn back) -> ballistic
  arrow (gravity 900, aim error from distance/target speed/confidence) ->
  hit takes the animal (meat), species familiarity -0.4, nearby animals
  bolt; misses remembered. Meat cooked at the fire (hunger -0.75).
  Berries eaten raw when there is no fire. Animals take cover in rain.
  Bow/arrows drawn in the "gear" pool above the creature (Creature.draw
  wrapper via _app_ref).

### Life layer (m40_life)
- Psyche per animal (seeded identity: traits, attachment, likes/dislikes,
  quirk, learning rate, memory span, coat, name); needs + light physiology;
  episodic memory; relationships changed ONLY by learn() from interpreted
  events (diminishing returns); places/home range; periodic utility
  decisions (0.7-1.0 s) executed by Fauna's motion/render/reflexes.
  Residents persist (living_mind.json "fauna_pop") and live off-screen.
- Dog species (domestic instinct toward people). New animal states:
  follow, play, excited (greeting), sniff, drink, beg.
- JaneLife: physiology (sleep pressure, bladder, hygiene, sweat, pain,
  condition, digestion), places/visited/favourite, home (lean-to -> hut,
  storm damage, repair, shelter), per-animal opinions + naming, learned
  thresholds (fire in rain, shot range), projects. Survival._plan is a
  utility planner (fallback to the old one on error).

### M41 predictive cognition (m41_predictive)
- `Expectations` per individual (Jane: life.exp; animals: psy.exp):
  hierarchical contingency model P(outcome|action,ctx), E[value], evidence,
  4 abstraction levels (who+situation / kind+situation / who / action)
  with evidence-weighted backoff; abstract levels scaled by the
  individual's generalisation. Updates return prediction error + surprise;
  evidence decays with memory span (contradictions revise). Individual
  params from identity: lr, span, gen, loss aversion, reward gain (attachment),
  neophobic prior. Persisted inside Psyche / JaneLife dicts.
- Hooks in M40 (no-ops unless M41 loaded): _m41_adjust (animal goal
  utilities + learned call signal + rest-spot choice), _m41_chose
  (eligibility traces), _m41_plan_adjust (Jane: pet/offer by expected
  reaction, fire-rain threshold, eat raw vs cook, shot range, calling
  friends), _m41_approach (fast/slow approach pace).
- Outcomes: animal consequences only from Jane's actions (fed/petted/shot/
  rushed) credited to recent choices; unrewarded choices decay ("nothing");
  rest disturbances; Jane: approach reaction, fire lifetime vs rain, hunger
  relief raw/cooked, hit/miss by range, stalk spooked/held, call came/ignored.
  Large confident surprises -> emotion + episodic memory + thought.

### M42-M46 (m42_agency, m43_continuity, m44_society)
- M42: `ag_plan` A* over a data-defined action library (_AG_ACTIONS +
  _AG_EXTRA): pre/eff/dur/at/risk/value; cost = travel+time x fatigue,
  risk/value from M41 per individual, risk weight from temperament. Goals
  come from the M40/M41 candidate utilities (_AG_GOALS map). life.plan /
  life.paused persist; interruption margin grows with remaining steps;
  paused plans resume by re-planning from the current state; failed steps
  are learned ("do:<action>") and banned briefly; plan outcomes feed
  "plan:<goal>". Animals: _m42_after builds go->act plans at learned best
  places, resumes after reflexes. M44 animal mood (valence/arousal/fear).
- M43: world dict in living_mind.json (saved_at, fire, POIs, society via
  _m43_save_hooks); autosave every 120 s; on load, offline advance
  (<=60 days, hourly): weather, fire, storm wear, Jane's offline life +
  plan progress, residents (bonds, births, losses), _m43_offline_hooks.
  M45: born_at/days/age, milestones (from salient perceptions), chapters,
  system-prompt biography.
- M46: Society (1 society-day per real hour): settlements, NPC individuals,
  economy/prices/trade, legitimacy/unrest/revolt, factions + culture drift,
  alliances/aid/war/raids/peace, famine/collapse/founding. Cross-valley
  journeys become visible Travellers (news, barter via the "trade" action,
  raiders); possessions: blanket (+3C resting), salt (x1.25 cooked meals),
  lantern (home at night). Reputation per settlement changes prices.

### Moral life (m45_moral) + physical civilisation (m46_world) + performance
- PERF (profiled): proxy.reproject pans with ONE canvas.move per tag when
  zoom/viewport are unchanged (was ~800 coords()/frame); sway staggered
  1/3 per frame; _AtmoPool skips coords() for unchanged items; face detail
  by LOD; fauna/body culling. Valley ~276 coords/frame, town ~428.
- MoralEngine (per society step, batched): acts scored on one scale from
  traits (kindness, cruelty, courage, mercy), circumstances and bonds
  (aff/trust/grudge/grat/kin): help, comfort, befriend, court (-> partners,
  children with inherited traits and surnames), forgive, apologize,
  quarrel, assault (protectors, injuries, deaths, guards, punishment,
  exile, feuds), steal (guards/guilt), betray, exploit; grief from deaths
  (comfort speeds it; can drive revenge); raids fall on individuals
  (defenders, rescue, sacrifice). NPC state lazily added (save-compatible).
- Regions: _rw_regions(society) -> settlements/roads/valley chain; world
  width 2.4x (settlement) / 1.6x (road) viewport; camera world_ext;
  creature bounds follow; arrival placement after world._built_for matches
  and resets loco anchors (L.px!). Settlement built from live state
  (houses, damage from raids, ruins, market, tavern, shrine + real graves,
  hall, towers, well, fields); POIs food=market, water=well, shelter=tavern.
- Bodies: real NPCs + crowd; role/hour schedules with per-person offsets,
  personal-space separation via spatial hash, hidden at home at night,
  grief/injury visible. Moral acts in Jane's current settlement are
  ENACTED (walk to each other; guards physically near decide "caught");
  Jane witnesses within sight. Jane: journeys (trade/social/curiosity/home),
  market (sell/buy with coins; reputation prices), sharing food with the
  needy. Valley animals stashed while away (devoted dog follows).

### World objects, grounding, baked world, Jane detail (m47-m49)
- m47_objects: WorldObjects registry (app.objects). Fires are persistent
  entities (oid, region, x, fuel, lit); a new build within ~4H of an
  existing pit RELIGHTS that pit; all fires burn every frame (one update per
  frame guard); Survival.draw draws the in-region fires and HIDES the pool
  of every other fire (the old bug: a replaced campfire left its last
  flames/smoke frozen in SCREEN space, which "followed" Jane with the
  camera and looked like duplicates). Saved as world["objects"] (legacy
  single "fire" migrated). sv.fire = nearest real fire in region each frame.
  world_snapshot()/world_brief(): ground-truth block in every system prompt
  (region, nearest places with m/direction/state, living things, named
  animals wherever they are, routes, weather, inventory, activity, command
  ack). Landscape scale 0.3 m/px. Spoken commands parsed in
  Brain.on_user_message -> life.command (goto home/fire/place/animal/person,
  "go there" = last place mentioned, light fire, sleep, eat, stay); planner
  candidate "cmd"/boosted goals; cross-region via life.journey.
- m48_bake: static world items rasterised (supersampled within a 2.4 MP
  budget, textured, contact shadows, foreground bank) on a WORKER thread;
  main thread swaps in one canvas image and hides the vector items
  (px._baked; regrade skips them). Grade = SceneGrade formula in numpy on
  the cached base, only when the quantised grade moves. Canopies + 1/3 of
  grass stay live (tag livesway, raised above worldimg). Soft RGBA cloud
  sprites with parallax replace per-frame blob clouds (World.animate
  override while baked). Rebuild clears _baked; never unhide recycled items.
- m49_jane_detail: sun-driven cast shadow, rim light (legs/arms/torso),
  hair strands (crown + pigtails via the _j_pigtail helper), outfit folds/
  seams/ribbing/lapels, shoe sole/gloss/stitching, saccades (applied after
  update), micro-expressions. LOD-gated: ~205 items gameplay, ~395 close-up.

### World scale, anatomy, WORLD tab (m50_scale)
- WS (WorldScale): px per metre = 0.19 * ground_y / 1.70 (Jane keeps the
  same share of the view); fit() in World.rebuild BEFORE building; listeners
  rescale every persistent position (Jane+loco, animals+homes, fires, her
  home, command x, bodies, travellers, unsaved residents, camera) so
  nothing drifts on resize; saved as world["px_per_m"] and loaded first.
- Creature._H() = true head height from WS (Jane 1.70 m). Creature._Hb() =
  1 m BEHAVIOUR unit: all sensing/approach/arrival/spacing distances in
  m39(_hunt,_plan), m40-m47 use _Hb (bodies/travellers/fire drawing keep _H).
- Metres everywhere: SPECIES table (L, sh, dp, head, neck+angle, fore/hind
  legs, ears, tail, rump, walk/run m/s, flee m) -> FAUNA speed/flee/size;
  vegetation (near trees 6.5-10 m, spacing per metre), shrubs, stones,
  flowers, grass; POIs (_sc_draw_pois via m46's _rw_prev_draw_pois); hut
  (1 m unit: walls 2.6, 5.2 wide, framed lit window); town buildings (1 m
  unit); region widths valley 48 / road 70 / settlement 100 m.
- Fauna.draw = anatomical renderer: torso/belly/back light, neck+head wedge
  (muzzle), jointed fore legs + hind legs with hock, trot/bound/hop gaits,
  ears (upright/floppy/long), tails (puff/bushy/flag/wag), antlers, sit,
  sleep, graze postures; birds/insects/fireflies sized by span.
- Camera: dead-zone follow (middle 40%), feet framed ~80% down, zoom 1.0-3.2.
- WORLD tab (inserted first): toolbar (−, +, reset, follow, fullscreen F11,
  status line); on select, the notebook spans the top (pane pinned to the
  toolbar height) and the stage card spans the window; other tabs restore
  the original grid. m48 bake: chunked textures, uint8 cached base.

### Wild animals, earned trust (m51_wild)
- m39 fear appraisal calls _wild_threat(fa, a, d, jspeed, jane, dt, world)
  (old species-familiarity formula = fallback); flee run length a._flee_run;
  "watch" is a stationary state.
- WILD table: flight distance (m), starting trust, habituation speed.
  wild_fid(): base * (1.4-0.8*boldness) * (1-0.88*earned trust) *
  (1+0.8*fear) * (1+0.6*approach speed). Fresh Psyche rel "jane" starts
  wild (Psyche.rel_of wrapper). Inside fid: flee (runs 1.6 fid + 6 m),
  learns "Jane came at me" if she approached, watches afterwards, alarm to
  conspecifics within 15 m. Alert zone < 1.7 fid. Habituation beyond fid
  (< 3.5 fid, Jane calm): trust += 0.0022*hab*lr/s (x2.2 sitting).
- Offerings (fauna._offerings): hungry animal eats if Jane is > 0.75 fid
  from the food; +trust/like via learn (M41 credit). Drawn as berries.
- Jane: candidates watch:<seed> (sit quietly at 1.35 fid, 35 s, M41
  "watch" outcome) and leave:<seed> (drop food at 0.8 fid, back off);
  pet/offer only when trust >= 0.55 (dog 0.35). _m42_decide lets these
  behaviour goals run (not planned). Ground animals keep body spacing.
- Perf: camera frames the terrain (not the bobbing body), targets on half
  pixels and settles (no sub-pixel creep -> no full-canvas pans inside
  the dead-zone); clouds update at 4 Hz.
- Anatomy: tapered limbs (_chain_skin), hooves/paws, per-foot contact
  shadows, shoulder/haunch masses, dorsal line, tapered necks (nw), canid
  cranium, alert head while watching.

### Purposeful life (m52_life)
- Destinations per region (world._dest): POIs + grove/glade/warren/meadow/
  west+east paths (valley), lookout/verge (road), market/tavern/shrine/hall/
  well (town); habitats drawn subtly; rabbits->warren, deer->meadow,
  fox->grove homes. life.visits remembers them.
- Candidates in the same planner: explore:<dest> (novelty x recency x
  curiosity x boredom), investigate:<seed> (walk to 1.25 fid, look 7 s),
  town journey every ~9 min / invitations, greet:<npc> (visitor who called),
  visit:<npc> (friends AND sociable strangers in town -> acquaintances).
  Behaviour goals bypass M42; a journey yields to anything clearly more
  pressing (+0.25) and resumes. watch utility halved.
- Sitting governor: after a sit, rest bias -0.9 for 4 min unless tired.
- Physical food: berries = walk -> inspect -> pick (reach, +1 per cycle,
  deplete per 2) ; eat = hand-to-mouth bites (0.3 hunger each), meal
  remembered once; leave = reach to the ground; animals sniff 1.6 s first.
  Creature._reach (m35) moves the near hand; shoulder shading sized in H.
- Visitors: every 45 s (valley, day) people who know her (x3) or sociable
  neighbours may walk in, wave + call out, talk (topic = a real memory or
  their settlement's news), gift / disagree / invite, remember it, leave.
- life.decision (goal/target/reason/need/memory/priority) written only from
  the planner's actual pick; action from the body's state; shown under the
  WORLD toolbar. Persisted with visits/invites/sits/investigated.
- Noise: ambient thoughts >= 90-180 s apart, rain 70 streaks, insect caps.
- Friends (trust > 0.6) don't bolt when she steps near; dogs/cats follow.

### Ten upgrades (m53_upgrades)
1 attention: _up_focus(app) -> cr.look_at(target) (renderer gaze rig, weight
  0.9) for investigate/watch/leave/pet/talk/berries/explore/goto/travel/
  shelter; turns to face a target behind her when still; look_away after.
2 carried: wood bundle in _draw_hair_back (behind her), basket/meat at the
  near hand in pool tag "gear" (hidden while eating).
3 indoors: cr._inside when asleep (or sheltering) at a hut stage>=2 ->
  Creature.draw hides every pooled item; the lit window shows she's home.
4 shelter: candidate "shelter" (precip>0.55 / storm) -> hut, overhang or
  tavern; waits until precip<0.35; decision "Take shelter from the storm".
5 calm wildlife: inside fid but she is NOT coming at it (toward<0.1, d>0.35
  fid) -> it steps away (wander) with alert 0.3, no bolt/alarm/learning.
6 quality: real frame time (perf_counter) EMA; <40 fps for 3 s -> level
  up (balanced: 2 clouds; fast: creature detail low, no clouds); >56 fps
  for 8 s -> level down. Shown in the WORLD decision line.
7 right-click (Button-3/2): _up_point -> animal/person/place under the
  cursor -> life.command goto (existing command path).
8 diary: life.diary from salient perceptions (kinds list), persisted;
  DIARY button in the WORLD toolbar opens it grouped by day.
9 stance: rest_width 1.3 (feet under hips), stance 1.02, leg IK soft
  margin relaxes when still (_ik2 soft_k) -> 99.7% extension standing.
10 chat: world_brief adds people she knows (+last talked), current
  visitors, and today's diary lines.

### Browser renderer + state bridge (m54_bridge, acacia/web)
- Python remains the only brain. m54_bridge: stdlib HTTP server on
  127.0.0.1:47833 (ACACIA_BRIDGE_PORT), started on the first world update.
  br_snapshot(app) -> metres: jane (x, vx, facing, sit, sleeping, inside,
  emotion + affect channels, gaze, reach, held, needs, decision, action),
  animals (id, sp, x, vx, state, fear, trust, name, colours), people (town
  bodies + travellers/visitors), fires (registry), offerings, home, POIs,
  weather, daypart, light, hour. Published at 10 Hz (never per frame) to
  /stream (SSE) and /state; br_static -> /static (region width, trees,
  places, town plan) keyed by BRIDGE.static_key. POST /input -> inbox,
  applied on the Tk thread via existing functions (point -> _up_point).
- acacia/web: index.html + style.css (ACACIA theme HUD) + renderer.js:
  snapshot interpolation (150 ms buffer), dead-zone camera (wheel zoom,
  drag to inspect, follow toggle, fullscreen), sky/sun/moon/stars, soft
  clouds, parallax ridges with snow + treeline, textured ground + path,
  trees (pine/broadleaf, wind sway, contact shadows), clutter, POIs, hut,
  town plan, fires (flames/glow/smoke/embers), rain, fog, night + firelight,
  people (IK legs/arms, gait from motion, outfits, face with expression from
  the affect channels), animals (anatomical quadrupeds, dedicated rabbit,
  birds, insects), truthful HUD (decision, needs) + hover cards (trust/fear).
- WORLD tab: OPEN GPU VIEW -> pywebview window (web/viewer.py) if installed,
  else Edge/Chrome --app window, else default browser. While a renderer is
  connected, Tk creature drawing drops to ~5 Hz (the sim keeps running).
- Verified headless: real renderer.js in Node against the live bridge
  (tools: /tmp/uitest/headless.js + replay.py), 0 JS errors.
- renderer.js: Jane has her own drawJane/janeHead/janeShoe (from m38's
  JANE_SHAPE/JANE_LOOK): hourglass torso (shoulders 0.9, bust, waist 0.475,
  hips ~1.05 hu) with a forward bust projection; outfits normal (pink cami
  with strawberry-print pattern, white scalloped lace, bow, straps, pleated
  pink skirt, white stilettos), light (mini + pink heels), warm (knit
  pattern + denim pattern jeans with gold seams, belt, boots), rain (belted
  trench, lapels, buttons, tights, boots); choker, two gold chains +
  pendant, hoops; pigtails with black ties + pink heart clips falling
  outward; pink eyeshadow, winged liner, lashes, white lower liner, iris
  with double catchlight, arched brows, blush, glossy red lips; one-piece
  neck from the shoulders up under the jaw with collarbones. Near leg is
  drawn under the skirt/coat. Patterns fade to flat colour at night.

## Browser WORLD renderer (acacia/web) — rebuilt
Presentation only. Python (m54 bridge, 10 Hz SSE) is the sole source of truth; nothing is simulated in JS.
Load order (index.html): core.js → world.js → jane.js → fauna.js → fx.js → hud.js (plain scripts, shared globals).
- core.js — utils, SSE + snapshot interpolation (120 ms delay; x/vx/alt/hour/light), camera `Cam`
  (Jane ≈27% of view height; critically-damped spring with velocity feed-forward; look-ahead + travel third;
  framing of her real decision target; safety box keeps her in frame; zoom 0.55–2.6 eased; drag / arrows / F = free
  camera; region-change fade; world bounds), depth lanes `laneOf` (presentation-only separation, others keep clear
  of Jane's lane), frame loop.
- world.js — biomes: meadow (valley), forest (road: pine wall, soft ranges, canopy), town (settlement: cobbles,
  timber houses, tavern, workshop, hall, shrine+graves, market stalls, well, gates, fields). Cached offscreen:
  far/mid/near parallax layers, clouds, stars, tree variants (sway = skew, no re-raster), props, houses, ground
  patterns; caches keyed by zoom bucket (×1.15) + light tint, bounded. Wet path sheen + sky-reflecting puddles from
  `weather.ground_wet`; hut/POIs/fires/offerings from the snapshot; light sources collected for fx.
- jane.js — `Stepper`: world-space foot plants, real gait timing (step 0.4–0.8 m walk / longer run, swing ≈40%),
  velocity measured from drawn motion, hip height from leg reach (floor 82%), no sliding. Jane's look (m38),
  seated pose, reach/carry, posture from real energy/valence, spring pigtails + skirt (motion + wind), rim light.
  `People` (townsfolk/visitors) share the stepper.
- fauna.js — species in real metres (rabbit/bird dedicated), gaits, state body language (graze/sniff/watch/flee/
  sleep/hunt, fear, trust), deer ears toward Jane, tail language.
- fx.js — half-res night light map with holes cut by real lights (fires, windows, lamps, crystal, fireflies) + warm
  glow; rain (2 layers + splashes), snow (bridge `snow`), fog bands, forest sun shafts, dawn/dusk/overcast grading,
  lightning, cached vignette; sun-driven shadow direction.
- hud.js — one card: goal, action, dominant need, reason, latest real diary event; hover card with real trust/fear;
  F3 = measured fps / frame ms / JS ms / counts / snapshot age (never estimated).
Bridge additions (m54): `static.biome`, `weather.ground_wet`, `snow`, `event`.
Verification harness lives outside the project (Node vm + PIL replay); JS cost measured there excludes GPU raster.
