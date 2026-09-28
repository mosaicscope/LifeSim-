# ============================================================================
# [NEW] CAMERA + HD CREATURE  (injected upgrade layer, loaded last)
# ============================================================================
#
# Two independent upgrades, both installed WITHOUT editing m18/m19/m33 (the
# original slices):
#
# 1. StageCamera - a real WORLD -> CAMERA -> SCREEN transform for the stage.
#    World/Creature/FriendActor are untouched: they still call plain
#    self.c.create_polygon(...) etc. in world-space exactly as before. The
#    only change is that `self.world.c` / `self.creature.c` / each
#    FriendActor's `.c` are repointed, post-construction, to a thin proxy
#    that runs every coordinate through the camera before handing it to the
#    REAL canvas. UI chrome (`_draw_overlay`'s inspector card, the brain-flow
#    strip, the emotion chip) draws on its own canvas or keeps using the
#    real `self.stage` directly and is therefore untouched by the camera.
#    WASD / drag / wheel / Space / F are bound with add="+" so the
#    already-bound click/resize/hover handlers keep firing unmodified.
#    `_on_stage_click` / `_on_stage_motion` are the two places original code
#    compares `event.x/y` straight against world-space entity coordinates
#    (`self.creature.x`, `actor.x`, `poi.x`); those two methods are wrapped
#    (original captured, still called) to convert the raw screen event into
#    world space first, so every existing hit-test keeps working unchanged.
#
# 2. HD Creature - `Creature_classic` keeps the original class (same
#    physics/gaze/gait/emotion, verified byte-identical). The new `Creature`
#    SUBCLASSES it and overrides only `draw()`: a layered pelvis/abdomen/
#    chest torso with faceted side-shading, foot/shoulder contact shadows,
#    and a distinctive procedural face (broad brow, pronounced nose, wide
#    jaw) - the same anatomical rig, physics and API, just redrawn.
#
# `tools/verify.py`'s OVERRIDES set has "Creature" added alongside the
# existing "generate_nft_character" entry (m34's own override), so
# `python3 tools/verify.py` still reports RESULT: IDENTICAL, and
# `ACACIA_NO_PATCHES=1 python3 tools/verify.py` (patches off) proves the
# original slices were never touched.

import math as _cw_math
import random as _cw_random
import time as _cw_time

# -- names already live in the shared namespace by the time this loads:
# math, random, time, tk, clamp, clamp01, approach, _shade, _limb_quad,
# _mix_hex, EMOTION_COLORS, FACE, Creature, World, FriendActor, App.


# ============================================================================
# StageCamera
# ============================================================================
class StageCamera:
    """(Named StageCamera, not Camera: m34_poly_physics already defines a 3D
    projection `Camera(width, height, focal, dist)` in the shared namespace,
    and the polyHD renderer resolves it by name at call time. Reusing the
    name here replaced it and crashed polyHD with "unexpected keyword
    argument 'focal'".)

    Position + zoom + smooth follow. Runs its own tick loop (canvas.after)
    so it never needs the app's render loop touched. dt-scaled, NaN-safe."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.pos = [0.0, 0.0]
        self.zoom = 1.15                   # third-person framing; wheel still zooms
        self.follow_target = None
        # Follow is OFF by default and `pos` is parked at the canvas centre,
        # which makes world_to_screen an exact identity transform - the stage
        # renders pixel-identical to the un-camera'd original until the user
        # actually presses a key / drags / zooms. The world is authored in
        # screen-space (m19 builds 0..w, 0..h), so auto-following the creature
        # would shove that scene off-view on the first frame.
        # follow is ON: a third-person camera framing her (F toggles it off)
        self.follow_enabled = True
        self.follow_lerp = 6.0
        self.vel = [0.0, 0.0]
        self.pan_speed = 240.0
        self.min_zoom, self.max_zoom = 0.4, 7.0
        self.keys = set()
        self._drag = None
        self._last_wh = [800, 600]
        self._last_t = _cw_time.time()
        self._alive = True
        self._touched = False   # stays home (identity) until real user input
        self._bind()

    def _bind(self):
        c = self.canvas
        try:
            c.bind("<KeyPress>", self._kd, add="+")
            c.bind("<KeyRelease>", self._ku, add="+")
            c.bind("<Button-1>", self._down, add="+")
            c.bind("<ButtonRelease-1>", self._up, add="+")
            c.bind("<B1-Motion>", self._drag_move, add="+")
            c.bind("<MouseWheel>", self._wheel, add="+")
            c.bind("<Button-4>", self._wheel, add="+")
            c.bind("<Button-5>", self._wheel, add="+")
            # take keyboard focus only on a real CLICK on the stage - never
            # just because the pointer crossed it. Hover-to-focus used to pull
            # focus out of text fields (e.g. the API-key entry) the moment the
            # mouse passed over the stage, so Ctrl+V pasted into the canvas.
            c.bind("<Button-1>", self._take_focus, add="+")
            c.bind("<Configure>", self._on_resize, add="+")
        except Exception:
            pass

    def _take_focus(self, _e=None):
        try:
            cur = self.canvas.focus_get()
            if cur is not None and cur.winfo_class() in ("Entry", "Text", "TEntry",
                                                         "TCombobox", "Spinbox"):
                return                      # never steal from something you're typing in
            self.canvas.focus_set()
        except Exception:
            pass

    def _kd(self, e):
        self._touched = True
        k = e.keysym.lower()
        if k == "f" and k not in self.keys:
            self.follow_enabled = not self.follow_enabled
        self.keys.add(k)

    def _ku(self, e):
        self.keys.discard(e.keysym.lower())

    def _down(self, e):
        self._drag = [e.x, e.y]

    def _up(self, e):
        self._drag = None

    def _drag_move(self, e):
        self._touched = True
        self._manual_until = _cw_time.time() + 2.5
        if self._drag is None:
            self._drag = [e.x, e.y]
            return
        dx, dy = e.x - self._drag[0], e.y - self._drag[1]
        z = self.zoom if self.zoom > 1e-4 else 1.0
        self.pos[0] -= dx / z
        self.pos[1] -= dy / z
        self._drag = [e.x, e.y]

    def _wheel(self, e):
        self._touched = True
        num = getattr(e, "num", None)
        delta = getattr(e, "delta", 0)
        factor = 1.1 if (num == 4 or delta > 0) else 0.9
        self.zoom = clamp(self.zoom * factor, self.min_zoom, self.max_zoom)

    def set_follow(self, creature):
        self.follow_target = creature

    def _on_resize(self, e):
        """Viewport changed (maximize / fullscreen / aspect change).

        The world is authored in screen space and the app rebuilds it to the
        new width/height, so the fix is to keep the camera framing the SAME
        part of that world. `pos` is a world point pinned to the viewport
        centre, so when the centre moves the camera has to move with it -
        otherwise going fullscreen slides the world sideways under a
        stationary camera and crops the trees/terrain off the edges.

        An untouched camera simply re-homes (exact identity, world fills the
        viewport). A camera the user has panned/zoomed keeps its OFFSET from
        centre, so their framing survives the resize instead of snapping."""
        w, h = max(1, getattr(e, "width", 0)), max(1, getattr(e, "height", 0))
        if w <= 1 or h <= 1:
            return
        self._last_wh = [w, h]
        if not self._touched and not (self.follow_enabled and self.follow_target is not None):
            self.home()
            return
        # `pos` IS the world point pinned to the viewport centre, so leaving
        # it alone is precisely what keeps the user's framing across a
        # resize - the same world point stays centred and the larger
        # viewport simply reveals more world around it. (Shifting it by the
        # centre delta would move the framing, which is the bug this used
        # to have.) Only the cached size needs updating, done above.
        self._sanitize()

    def fit_world(self, world_w, world_h, margin=0.0):
        """Zoom so a world of this size fits the viewport on BOTH axes - the
        limiting axis wins, so nothing is cropped when the aspect changes."""
        w, h = self._wh()
        if world_w <= 0 or world_h <= 0:
            return
        z = min(w / float(world_w), h / float(world_h)) * (1.0 - margin)
        self.zoom = clamp(z, self.min_zoom, self.max_zoom)
        self._sanitize()

    def _frame_target(self, dt):
        """Where the camera wants to be: ahead of her in the direction of
        travel (smoothed), her body centred a little below the middle."""
        cr = self.follow_target
        w, h = self._wh()
        vw = w / max(self.zoom, 1e-3)
        vx = getattr(getattr(cr, "_loco", None), "vx", 0.0)
        want = clamp(vx * 0.55, -0.16 * vw, 0.16 * vw)
        self._look = getattr(self, "_look", 0.0)
        self._look += (want - self._look) * (1.0 - _cw_math.exp(-dt / 0.9))
        bb = getattr(cr, "_bbox", None)
        mid = (bb[1] + bb[3]) * 0.5 if bb else cr.y
        tx, ty = cr.x + self._look, mid - 0.05 * h / max(self.zoom, 1e-3)
        # clamp the TARGET to the world, so the spring decelerates smoothly
        # into an edge instead of being stopped dead by the hard clamp
        z = max(self.zoom, 1e-3)
        vw, vh = w / z, h / z
        ew, eh = self.__dict__.get("world_ext") or (w, h)
        if vw < ew:
            tx = clamp(tx, vw * 0.5, ew - vw * 0.5)
        if vh < eh:
            ty = clamp(ty, vh * 0.5, eh - vh * 0.5)
        return tx, ty

    def _clamp_to_world(self):
        """Never show past the world's edges (no cut-off trees / empty
        space), even after resizes. The world may be wider than the
        viewport (settlements): world_ext overrides the canvas size."""
        w, h = self._wh()
        ew, eh = self.__dict__.get("world_ext") or (w, h)
        z = max(self.zoom, 1e-3)
        for i, (ext, view) in enumerate(((ew, w / z), (eh, h / z))):
            if view >= ext:
                self.pos[i] = ext * 0.5
                self.vel[i] = 0.0
            else:
                lo, hi = view * 0.5, ext - view * 0.5
                if self.pos[i] < lo or self.pos[i] > hi:
                    self.pos[i] = clamp(self.pos[i], lo, hi)
                    self.vel[i] = 0.0

    def home(self):
        """Park at the canvas centre => world_to_screen becomes identity."""
        w, h = self._wh()
        self.pos = [w / 2.0, h / 2.0]
        # identity only for the free camera; the follow camera keeps its
        # framing zoom (at 1.0 the view IS the whole world: nothing to follow)
        self.zoom = 1.15 if (self.follow_enabled and self.follow_target is not None) else 1.0

    def is_home(self):
        w, h = self._wh()
        return (abs(self.pos[0] - w / 2.0) < 0.5 and abs(self.pos[1] - h / 2.0) < 0.5
                and abs(self.zoom - 1.0) < 1e-3 and not self.follow_enabled)

    def focus(self):
        if self.follow_target is not None:
            self.pos = [self.follow_target.x, self.follow_target.y]

    def _wh(self):
        try:
            w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
            if w > 1 and h > 1:
                self._last_wh = [w, h]
        except Exception:
            pass
        return self._last_wh

    def stop(self):
        self._alive = False

    def tick(self):
        if not self._alive:
            return
        now = _cw_time.time()
        dt = clamp(now - self._last_t, 0.0, 0.1)
        self._last_t = now

        follow = self.follow_target is not None and self.follow_enabled
        if not self._touched and not follow:
            # never drifted: keep the transform exactly identity, and keep it
            # correct across window resizes
            self.home()
            try:
                self.canvas.after(16, self.tick)
            except Exception:
                self._alive = False
            return

        if "space" in self.keys:
            self.focus()
            self.vel = [0.0, 0.0]

        mult = 2.0 if ("shift_l" in self.keys or "shift_r" in self.keys) else 1.0
        mv = [0.0, 0.0]
        for k, (dx, dy) in (("w", (0, -1)), ("s", (0, 1)), ("a", (-1, 0)), ("d", (1, 0))):
            if k in self.keys:
                mv[0] += dx
                mv[1] += dy
        if mv[0] or mv[1]:
            self._manual_until = now + 2.5          # manual control pauses following
            n = _cw_math.hypot(*mv) or 1.0
            self.pos[0] += mv[0] / n * self.pan_speed * mult * dt
            self.pos[1] += mv[1] / n * self.pan_speed * mult * dt

        if follow and now >= getattr(self, "_manual_until", 0.0):
            # third-person follow: critically damped spring per axis (no
            # overshoot, no jitter), toward a framed target with look-ahead
            tx, ty = self._frame_target(dt)
            for i, (t, w0) in enumerate(((tx, 2.8), (ty, 3.4))):
                acc = w0 * w0 * (t - self.pos[i]) - 2.0 * w0 * self.vel[i]
                self.vel[i] += acc * dt
                self.pos[i] += self.vel[i] * dt
        self._clamp_to_world()
        self._sanitize()
        try:
            self.canvas.after(16, self.tick)
        except Exception:
            self._alive = False

    def _sanitize(self):
        for i in (0, 1):
            v = self.pos[i]
            if not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
                self.pos[i] = 0.0
        if not isinstance(self.zoom, (int, float)) or self.zoom != self.zoom or self.zoom <= 0:
            self.zoom = 1.0
        self.zoom = clamp(self.zoom, self.min_zoom, self.max_zoom)

    def world_to_screen(self, x, y):
        w, h = self._wh()
        cx, cy = w / 2.0, h / 2.0
        return (x - self.pos[0]) * self.zoom + cx, (y - self.pos[1]) * self.zoom + cy

    def screen_to_world(self, sx, sy):
        w, h = self._wh()
        cx, cy = w / 2.0, h / 2.0
        z = self.zoom if self.zoom > 1e-4 else 1.0
        return (sx - cx) / z + self.pos[0], (sy - cy) / z + self.pos[1]


class _CamCanvasProxy:
    """Coordinate-transforming stand-in for a Tk canvas. World/Creature/
    FriendActor keep calling self.c.create_polygon(...) etc. unmodified;
    this is the ONE place world-space becomes screen-space. Everything not
    about placing geometry (winfo_*, after, bind, delete, tag_*, cget,
    itemconfig...) passes straight through to the real widget."""

    #: Cap on recycled items held per kind. Bounded so a pathological caller
    #: cannot grow the free lists without limit.
    RECYCLE_CAP = 400

    def __init__(self, real_canvas, camera):
        object.__setattr__(self, "_real", real_canvas)
        object.__setattr__(self, "_cam", camera)
        # --- transparent item recycling -----------------------------------
        # m19's World.clear_dyn() deletes every dynamic item each frame and
        # animate() immediately recreates them (clouds, ripples, fireflies,
        # rain) - up to ~40 destroy+create pairs per frame. On Windows each
        # canvas item carries GDI objects, and that churn is what drains the
        # handle table into "Tk_GetPixmap: Error from CreateDIBSection".
        # m19 is an original slice and must not be edited, so the recycling
        # happens HERE instead: delete() hides the item and files it by kind,
        # and the next create_<kind>() re-points that item rather than
        # allocating a new one. Callers see the same ids and the same
        # behaviour; the handle count simply stops growing.
        object.__setattr__(self, "_free", {})       # kind -> [item ids]
        object.__setattr__(self, "_kind_of", {})    # item id -> kind
        # --- world-space registry -----------------------------------------
        # The scenery (sky, hills, ground, trees, POIs) is built ONCE per
        # rebuild. Transforming only at creation meant panning/zooming moved
        # the creature but left the whole environment frozen on screen. Each
        # item's WORLD coordinates are kept here so reproject() can re-place
        # everything when the camera changes, and so wind can sway specific
        # items (trees, grass) around their roots.
        object.__setattr__(self, "_track", True)
        object.__setattr__(self, "_reg", {})        # item -> [mode, world_flat, kind, tags, fill, outline, yc]
        object.__setattr__(self, "_grade", None)    # SceneGrade: colour grading instead of stipple
        object.__setattr__(self, "_grade_key", None)
        object.__setattr__(self, "_hidden", set())
        object.__setattr__(self, "_cam_sig", None)
        object.__setattr__(self, "_sway", {})       # item -> (root_y, height, phase, stiffness)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_real"), name)

    @staticmethod
    def _flatten(coords):
        """Tk accepts BOTH create_polygon([x0,y0,...]) and
        create_polygon(x0, y0, ...). The original code uses both forms:
        m18's _poly / m20's actor limbs pass a single list from
        _limb_quad(), while m19's shelter/curio pass flat varargs. Normalise
        either into one flat list before transforming."""
        if len(coords) == 1 and isinstance(coords[0], (list, tuple)):
            flat = list(coords[0])
        else:
            flat = list(coords)
        # tolerate nested pairs, e.g. [(x, y), (x, y)]
        if flat and isinstance(flat[0], (list, tuple)):
            out = []
            for pt in flat:
                out.extend(pt)
            flat = out
        return flat

    def _xy(self, coords):
        cam = object.__getattribute__(self, "_cam")
        flat = self._flatten(coords)
        out = []
        for i in range(0, len(flat) - 1, 2):
            sx, sy = cam.world_to_screen(flat[i], flat[i + 1])
            out.append(sx)
            out.append(sy)
        return out

    def _bbox(self, coords):
        cam = object.__getattribute__(self, "_cam")
        flat = self._flatten(coords)
        if len(flat) < 4:
            return flat
        sx0, sy0 = cam.world_to_screen(flat[0], flat[1])
        sx1, sy1 = cam.world_to_screen(flat[2], flat[3])
        return [sx0, sy0, sx1, sy1]

    def _register(self, item, kind, mode, world_flat, kw):
        if self._track:
            ys = world_flat[1::2] if world_flat else [0.0]
            yc = (min(ys) + max(ys)) * 0.5 if ys else 0.0
            self._reg[item] = [mode, list(world_flat), kind, kw.get("tags", ""),
                               kw.get("_fill0", kw.get("fill", "")),
                               kw.get("_outline0", kw.get("outline", "")), yc,
                               {k: v for k, v in kw.items() if k in ("smooth", "width", "start", "extent", "style")}]
            self._hidden.discard(item)
            self._sway.pop(item, None)

    def _graded(self, kw, world_flat):
        """Stipple is REMOVED here - it is Tk's only 'transparency' and
        renders as a screen-door dot pattern on Windows. Colour grading
        does the darkening/fog/glow instead, on solid colours."""
        kw = dict(kw)
        if kw.pop("stipple", None) and kw.get("fill"):
            # a stippled darkening overlay (m19's picked-over food spot):
            # become an honest dark ring instead of a dotted blob
            kw["outline"] = kw.pop("fill")
            kw["fill"] = ""
            kw["width"] = 2
        g = self._grade
        kw["_fill0"], kw["_outline0"] = kw.get("fill", ""), kw.get("outline", "")
        if g is not None and world_flat:
            ys = world_flat[1::2]
            yc = (min(ys) + max(ys)) * 0.5 if ys else 0.0
            for key in ("fill", "outline"):
                if key in kw:
                    kw[key] = g.color(kw[key], yc)
        return kw

    @staticmethod
    def _clean(kw):
        return {k: v for k, v in kw.items() if not k.startswith("_")}

    def regrade(self, force=False):
        """Re-colour every tracked item for the current grade. Runs only when
        the (quantised) grade actually changed - not per frame."""
        g = self._grade
        if g is None:
            return 0
        key = g.key()
        if not force and key == self._grade_key:
            return 0
        self._grade_key = key
        n = 0
        baked = self.__dict__.get("_baked", ())
        for item, ent in list(self._reg.items()):
            if item in self._hidden or item in baked:
                continue                              # baked into the cached world image
            fill0, out0, yc = ent[4], ent[5], ent[6]
            cfg = {}
            if isinstance(fill0, str) and fill0.startswith("#"):
                cfg["fill"] = g.color(fill0, yc)
            if isinstance(out0, str) and out0.startswith("#"):
                cfg["outline"] = g.color(out0, yc)
            if cfg:
                try:
                    self._real.itemconfig(item, **cfg)
                    n += 1
                except Exception:
                    self._reg.pop(item, None)
        return n

    def _recycle(self, kind, flat, kw, mode="xy", world_flat=None):
        """Reuse a hidden item of this kind if one is free; else create."""
        kw = self._graded(kw, world_flat)
        free = self._free.get(kind)
        if free:
            item = free.pop()
            try:
                self._real.coords(item, *flat)
                cfg = self._clean(kw)
                cfg["state"] = "normal"
                self._real.itemconfig(item, **cfg)
                self._register(item, kind, mode, world_flat or [], kw)
                return item
            except Exception:
                self._kind_of.pop(item, None)       # stale: fall through
                self._reg.pop(item, None)
        item = getattr(self._real, "create_" + kind)(*flat, **self._clean(kw))
        self._kind_of[item] = kind
        self._register(item, kind, mode, world_flat or [], kw)
        return item

    # -- camera re-projection ---------------------------------------------
    def _project(self, mode, world_flat, dx=None):
        cam = object.__getattribute__(self, "_cam")
        if mode == "bbox":
            x0, y0 = cam.world_to_screen(world_flat[0], world_flat[1])
            x1, y1 = cam.world_to_screen(world_flat[2], world_flat[3])
            return [x0, y0, x1, y1]
        out = []
        for i in range(0, len(world_flat) - 1, 2):
            x = world_flat[i]
            if dx is not None:
                x += dx(world_flat[i + 1])
            sx, sy = cam.world_to_screen(x, world_flat[i + 1])
            out.append(sx)
            out.append(sy)
        return out

    def camera_signature(self):
        cam = object.__getattribute__(self, "_cam")
        w, h = cam._wh()
        return (round(cam.pos[0], 2), round(cam.pos[1], 2), round(cam.zoom, 4), w, h)

    def reproject(self, force=False):
        """Re-place every tracked item after a camera change. Returns the
        number of items moved (0 when the camera hasn't changed).

        PERF (profiled: 818 coords() calls/frame while the follow camera
        pans): a pure pan - same zoom, same viewport - is an exact
        translation of every item, so it is ONE Tk move() per tag. Only a
        zoom or resize re-projects items individually."""
        sig = self.camera_signature()
        if not force and sig == self._cam_sig:
            return 0
        old = self._cam_sig
        self._cam_sig = sig
        if not force and old is not None and old[2:] == sig[2:] and self._reg:
            dx = -(sig[0] - old[0]) * sig[2]
            dy = -(sig[1] - old[1]) * sig[2]
            try:
                for tag in ("world", "worlddyn"):
                    self._real.move(tag, dx, dy)
                return len(self._reg)
            except Exception:
                pass                                   # fall back to per-item placement
        n = 0
        for item, ent in list(self._reg.items()):
            mode, flat = ent[0], ent[1]
            if item in self._hidden or item in self._sway or not flat:
                continue
            try:
                self._real.coords(item, *self._project(mode, flat))
                n += 1
            except Exception:
                self._reg.pop(item, None)
        return n

    def set_sway(self, table):
        """table: item -> (root_y, height, phase, stiffness)."""
        object.__setattr__(self, "_sway", dict(table))

    def apply_sway(self, t, wind, gust, wind_dir):
        """Bend each swaying item about its root: displacement grows with
        height above the root (x ~ h^1.6), so a tree bends from the trunk
        and grass whips at the tip. Only these items are touched per frame."""
        # PERF: each swaying item is refreshed on every 3rd frame (staggered),
        # ~20 Hz per item - wind motion is slow, a third of the Tk calls
        frame = self.__dict__.get("_sway_frame", 0) + 1
        object.__setattr__(self, "_sway_frame", frame)
        for idx, (item, (root, height, phase, stiff)) in enumerate(self._sway.items()):
            if item in self._hidden or (idx + frame) % 3:
                continue
            ent = self._reg.get(item)
            if not ent:
                continue
            mode, flat = ent[0], ent[1]
            amp = (wind * 7.0 + gust * 9.0) * wind_dir / stiff \
                + _cw_math.sin(t * (1.1 + 0.9 / stiff) + phase) * (0.6 + 4.5 * wind) / stiff

            def dx(y, root=root, height=height, amp=amp):
                k = clamp01((root - y) / max(height, 1.0))
                return amp * (k ** 1.6)
            try:
                if mode == "bbox":
                    cx = dx((flat[1] + flat[3]) * 0.5)
                    shifted = [flat[0] + cx, flat[1], flat[2] + cx, flat[3]]
                    self._real.coords(item, *self._project("bbox", shifted))
                else:
                    self._real.coords(item, *self._project("xy", flat, dx))
            except Exception:
                pass

    def delete(self, *items):
        """Hide and file for reuse instead of destroying. `delete_real()`
        still performs a true delete when something must actually go."""
        for item in items:
            if item in ("all", "ALL"):               # wholesale clear: honour it
                self._real.delete(item)
                self._free.clear()
                self._kind_of.clear()
                self._reg.clear()
                self._hidden.clear()
                self._sway.clear()
                continue
            kind = self._kind_of.get(item)
            if kind is None:
                self._real.delete(item)
                self._reg.pop(item, None)
                continue
            try:
                self._real.itemconfig(item, state="hidden")
                self._hidden.add(item)
            except Exception:
                self._kind_of.pop(item, None)
                self._reg.pop(item, None)
                continue
            bucket = self._free.setdefault(kind, [])
            if len(bucket) < self.RECYCLE_CAP:
                bucket.append(item)
            else:
                self._real.delete(item)
                self._kind_of.pop(item, None)
                self._reg.pop(item, None)
                self._hidden.discard(item)

    def delete_real(self, *items):
        for item in items:
            self._kind_of.pop(item, None)
            self._reg.pop(item, None)
            self._hidden.discard(item)
            self._real.delete(item)

    def create_polygon(self, *coords, **kw):
        return self._recycle("polygon", self._xy(coords), kw, "xy", self._flatten(coords))

    def create_line(self, *coords, **kw):
        return self._recycle("line", self._xy(coords), kw, "xy", self._flatten(coords))

    def create_oval(self, *coords, **kw):
        return self._recycle("oval", self._bbox(coords), kw, "bbox", self._flatten(coords)[:4])

    def create_rectangle(self, *coords, **kw):
        return self._recycle("rectangle", self._bbox(coords), kw, "bbox",
                             self._flatten(coords)[:4])

    def create_arc(self, *coords, **kw):
        return self._recycle("arc", self._bbox(coords), kw, "bbox", self._flatten(coords)[:4])

    def create_text(self, x, y, **kw):
        cam = object.__getattribute__(self, "_cam")
        sx, sy = cam.world_to_screen(x, y)
        return self._real.create_text(sx, sy, **kw)

    def coords(self, item, *coords):
        if not coords:
            return self._real.coords(item)
        ent = self._reg.get(item) if self._track else None
        if ent is not None:
            flat = self._flatten(coords)
            ent[1] = flat[:4] if ent[0] == "bbox" else flat
            if ent[0] == "bbox":
                return self._real.coords(item, *self._project("bbox", ent[1]))
        return self._real.coords(item, *self._xy(coords))


# ============================================================================
# Procedural skin: anatomy-region micro-detail, rolled ONCE per identity
# ============================================================================
#
# Detail is NOT random dots sprayed over the silhouette. Each feature is
# sampled inside a named anatomical REGION (forehead, cheek, nose, jaw,
# chin, brow-ridge), and each region carries its own pore density, pore size
# range, oiliness (specular lift) and tonal shift - which is what makes the
# forehead/nose read shiny and coarse-pored while the cheeks read softer and
# more diffuse, the way real skin does.
#
# Everything is stored in HEAD-LOCAL units (offsets from the head anchor, in
# the same scale the face polygons use), so it rides the head automatically
# as the skull moves, tilts and the camera zooms - no per-frame regeneration,
# no positional drift, no frame-to-frame flicker. The seed is the creature's
# persistent body_seed, so a given creature keeps the same freckles and pores
# across restarts.

# region -> (name, cx, cy, rx, ry, density, pore_min, pore_max, oil, tone)
_SKIN_REGIONS = (
    ("forehead",   0.0, -24.0, 23.0,  8.0, 1.00, 0.45, 1.05, 0.85,  0.03),
    ("brow_l",   -14.0, -17.0, 10.0,  4.0, 0.55, 0.40, 0.85, 0.40, -0.04),
    ("brow_r",    14.0, -17.0, 10.0,  4.0, 0.55, 0.40, 0.85, 0.40, -0.04),
    ("nose",       0.0,   0.0,  6.5, 10.0, 1.25, 0.50, 1.25, 1.00,  0.05),
    ("cheek_l",  -21.0,  -1.0, 10.0,  8.0, 0.70, 0.35, 0.80, 0.25, -0.02),
    ("cheek_r",   21.0,  -1.0, 10.0,  8.0, 0.70, 0.35, 0.80, 0.25, -0.02),
    ("jaw_l",    -22.0,  10.0, 10.0,  5.0, 0.50, 0.35, 0.75, 0.20, -0.05),
    ("jaw_r",     22.0,  10.0, 10.0,  5.0, 0.50, 0.35, 0.75, 0.20, -0.05),
    ("chin",       0.0,  15.0, 11.0,  5.0, 0.60, 0.40, 0.85, 0.35, -0.03),
    ("upper_lip",  0.0,   7.0,  9.0,  2.5, 0.45, 0.30, 0.65, 0.30,  0.02),
)


def _skin_build(seed, asym=0.0):
    """Roll one creature's permanent skin. Head-local feature lists."""
    rnd = _cw_random.Random((int(seed) ^ 0x5B17A9) & 0xFFFFFFFF)
    skin = {}

    pores = []
    for (name, cx, cy, rx, ry, dens, pmin, pmax, oil, tone) in _SKIN_REGIONS:
        n = int(rx * ry * dens * 0.55)
        for _ in range(n):
            while True:
                u, v = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
                if u * u + v * v <= 1.0:
                    break
            px = cx + u * rx + asym * 0.3
            py = cy + v * ry
            depth = 1.0 - 0.45 * (u * u + v * v)
            pores.append((px, py, rnd.uniform(pmin, pmax), depth, oil, tone))
    skin["pores"] = pores

    freckles = []
    clusters = [(rnd.uniform(-24, 24), rnd.uniform(-22, 12))
                for _ in range(rnd.randint(3, 6))]
    for (ccx, ccy) in clusters:
        for _ in range(rnd.randint(4, 11)):
            fx = ccx + rnd.gauss(0, 4.5)
            fy = ccy + rnd.gauss(0, 3.2)
            if abs(fx) > 32 or fy < -30 or fy > 20:
                continue
            freckles.append((fx, fy, rnd.uniform(0.5, 1.5), rnd.uniform(0.25, 0.62)))
    skin["freckles"] = freckles

    wr = []
    for i in range(rnd.randint(2, 4)):
        yy = -29 + i * 3.4 + rnd.uniform(-0.5, 0.5)
        span = rnd.uniform(15, 21)
        wr.append(("forehead",
                   [(-span + j * (2 * span / 5), yy + _cw_math.sin(j * 1.1 + i) * 0.7)
                    for j in range(6)], rnd.uniform(0.35, 0.6)))
    for side in (-1, 1):
        for k in range(rnd.randint(2, 3)):
            ox, oy = side * 22, -15 + k * 2.6
            wr.append(("eye",
                       [(ox + side * j * 2.2,
                         oy + (j * j) * 0.16 * (1 if k % 2 else -1) + k * 0.3)
                        for j in range(4)], rnd.uniform(0.3, 0.5)))
    for side in (-1, 1):
        wr.append(("nasolabial",
                   [(side * 7, -2), (side * 11, 3), (side * 13.5, 9), (side * 13, 14)],
                   rnd.uniform(0.5, 0.75)))
    for i in range(rnd.randint(1, 3)):
        for side in (-1, 1):
            yy = -8 + i * 1.9
            wr.append(("undereye",
                       [(side * 9, yy), (side * 15, yy + 0.6), (side * 20, yy + 1.7)],
                       rnd.uniform(0.22, 0.4)))
    skin["wrinkles"] = wr

    skin["neck_folds"] = [(-7 + rnd.uniform(-1, 1), 4 + i * 3.2,
                           7.5 + rnd.uniform(-1, 1), rnd.uniform(0.3, 0.55))
                          for i in range(rnd.randint(2, 3))]

    brows = []
    for side in (-1, 1):
        n = rnd.randint(26, 36)
        for i in range(n):
            t = i / (n - 1.0)
            bx = side * (7.5 + t * 15.5)
            by = -19.5 - _cw_math.sin(t * 3.0) * 2.4 + rnd.uniform(-0.6, 0.6)
            ang = (-0.95 + t * 0.75) * side + rnd.uniform(-0.16, 0.16)
            brows.append((bx, by, ang, rnd.uniform(2.0, 3.6) * (1.0 - 0.3 * t),
                          rnd.uniform(0.55, 1.0)))
    skin["brows"] = brows

    lashes = []
    for side in (-1, 1):
        n = rnd.randint(9, 13)
        for i in range(n):
            t = i / (n - 1.0)
            a = -0.55 + t * 1.75
            lx = side * 14 + _cw_math.cos(a) * 7.4 * side
            ly = -14 - _cw_math.sin(a) * 4.6
            curl = -1.15 - 0.35 * _cw_math.sin(t * _cw_math.pi)
            lashes.append((lx, ly, curl, rnd.uniform(2.1, 3.4), side))
    skin["lashes"] = lashes

    hair = []
    n = rnd.randint(46, 68)
    for i in range(n):
        t = i / (n - 1.0)
        hx0 = -31 + t * 62
        hy0 = -34 + abs(hx0) * 0.10 + rnd.uniform(-1.2, 1.2)
        hair.append((hx0, hy0, rnd.uniform(0.7, 1.35), rnd.uniform(5.0, 10.0),
                     rnd.uniform(0.4, 1.0)))
    skin["hair"] = hair

    stub = []
    for _ in range(rnd.randint(70, 120)):
        sx = rnd.uniform(-26, 26)
        sy = rnd.uniform(4, 19)
        if abs(sx) > 8 and sy < 7:
            continue
        stub.append((sx, sy, rnd.uniform(-0.5, 0.5), rnd.uniform(0.7, 1.5)))
    skin["stubble"] = stub

    skin["lip_creases"] = [(rnd.uniform(-10, 10), rnd.uniform(0.6, 1.5),
                            rnd.uniform(0.3, 0.6)) for _ in range(rnd.randint(9, 15))]
    skin["knuckles"] = [(-3.2 + i * 2.1, rnd.uniform(-0.8, 0.8), rnd.uniform(1.1, 1.9))
                        for i in range(4)]
    return skin


#: Hard ceiling on micro-detail canvas items per frame. Tk item creation is
#: the real cost (roughly 10-40us each), so the pore/stubble lists are strided
#: down to fit this budget rather than emitted whole. Raise it on a fast box.
SKIN_ITEM_BUDGET = 260


def _stride(seq, budget):
    """Evenly subsample a feature list to at most `budget` entries. Striding
    (not truncating) keeps the spatial distribution intact - truncation would
    leave one side of the face bare."""
    n = len(seq)
    if n <= budget or budget <= 0:
        return seq
    step = (n + budget - 1) // budget
    return seq[::step]


def _skin_lod(zoom):
    """0 = silhouette only, 1 = anatomy + tone, 2 = full micro-surface.
    Gating on zoom keeps the canvas item count flat when pulled back - the
    detail is simply not emitted."""
    if zoom < 1.35:
        return 0
    if zoom < 2.4:
        return 1
    return 2


# ============================================================================
# HD Creature - same rig/physics/gaze/emotion (inherited), richer draw()
# ============================================================================
Creature_classic = Creature


def _hd_seg(p0, p1, w0, w1, segs=2):
    """Two/three tapered sub-quads instead of one, for a faceted read."""
    out = []
    for i in range(segs):
        t0, t1 = i / segs, (i + 1) / segs
        a = (p0[0] + (p1[0] - p0[0]) * t0, p0[1] + (p1[1] - p0[1]) * t0)
        b = (p0[0] + (p1[0] - p0[0]) * t1, p0[1] + (p1[1] - p0[1]) * t1)
        wa, wb = w0 + (w1 - w0) * t0, w0 + (w1 - w0) * t1
        out.append(_limb_quad(a, b, wa, wb))
    return out


class Creature(Creature_classic):
    """Visual-only upgrade. __init__/update/_pose/set_*/gaze all inherited
    unchanged from Creature_classic - only draw() is replaced, plus a small
    dt-scaled idle weight-shift accumulator layered on top in update()."""

    def __init__(self, canvas, x, y, bounds, identity=None):
        super().__init__(canvas, x, y, bounds, identity)
        self._sway = 0.0
        self._sway_seed = _cw_random.uniform(0, _cw_math.tau)
        ident = identity or {}
        seed = ident.get("body_seed")
        if seed is None:
            seed = int(abs(self.asym * 1000) + abs(self.build * 7919)) & 0xFFFFFFFF
        self._skin = _skin_build(seed, self.asym)
        self._skin["_seed"] = seed
        self._skin_lod_cur = 0

    def _zoom(self):
        """Current camera zoom, via the proxy the app installed. 1.0 when
        there is no camera (bare/test Creature) - detail then stays off."""
        c = self.c
        cam = getattr(c, "_cam", None)
        if cam is None:
            try:
                cam = object.__getattribute__(c, "_cam")
            except Exception:
                return 1.0
        try:
            return float(cam.zoom)
        except Exception:
            return 1.0

    def update(self, dt):
        super().update(dt)
        dt = clamp(dt, 0.0, 0.1)
        if self.behavior in ("move", "curious"):
            self._sway = approach(self._sway, 0.0, 2.0, dt)
        else:
            idle = _cw_math.sin(self.t * 0.6 + self._sway_seed) * 2.4
            self._sway = approach(self._sway, idle, 1.2, dt)



    # -- head scaling ---------------------------------------------------
    def _head_scale_begin(self, hx, hy, hs):
        """Temporarily rebind the drawing primitives so every head-local
        coordinate is scaled about (hx, hy) by `hs`. The face/skin code is
        authored at a fixed ~+/-35 unit scale; the BODY scales with
        self.build, so without this the skull stays a fixed pixel size and
        ends up ~40% of the figure. One factor here rescales the cranium,
        planes, eyes, mouth AND the head-local skin detail together, so
        nothing drifts out of register."""
        self._hs_saved = (self._poly, self._oval, self._line, self._arc)
        op, oo, ol, oa = self._hs_saved

        def sx(x):
            return hx + (x - hx) * hs

        def sy(y):
            return hy + (y - hy) * hs

        def _poly(pts, fill, outline="#0a0c10", smooth=False):
            out = []
            for i in range(0, len(pts) - 1, 2):
                out.append(sx(pts[i]))
                out.append(sy(pts[i + 1]))
            return op(out, fill, outline, smooth)

        def _oval(x0, y0, x1, y1, fill, outline="#0a0c10"):
            return oo(sx(x0), sy(y0), sx(x1), sy(y1), fill, outline)

        def _line(*coords, **kw):
            out = []
            for i in range(0, len(coords) - 1, 2):
                out.append(sx(coords[i]))
                out.append(sy(coords[i + 1]))
            return ol(*out, **kw)

        def _arc(x0, y0, x1, y1, **kw):
            return oa(sx(x0), sy(y0), sx(x1), sy(y1), **kw)

        self._poly, self._oval, self._line, self._arc = _poly, _oval, _line, _arc

    def _head_scale_end(self):
        if getattr(self, "_hs_saved", None):
            self._poly, self._oval, self._line, self._arc = self._hs_saved
            self._hs_saved = None

    # -- skin micro-surface -------------------------------------------
    def _draw_skin(self, hx, hy, head_color, lod, phase):
        """Emit the cached skin features in head-local space. `phase` is
        which pass: "under" (pores/tone/wrinkles, below the eyes) or
        "over" (lashes/brows/hair, above them)."""
        sk = self._skin
        L = self._line
        dark = _shade(head_color, 0.60)
        darker = _shade(head_color, 0.47)
        crease = _shade(head_color, 0.55)
        lift = _shade(head_color, 1.16)
        hair_c = _shade(head_color, 0.42)

        if phase == "under":
            # --- broad tonal zones first: a cheap stand-in for subsurface
            # scatter - warm lift on the forehead/nose ridge (oily, more
            # specular), cooler soften on the cheeks -------------------
            if lod >= 1:
                self._poly([hx - 20, hy - 30, hx + 20, hy - 30,
                            hx + 16, hy - 20, hx - 16, hy - 20], lift, "")
                self._poly([hx - 4, hy - 7, hx + 4, hy - 7,
                            hx + 3, hy + 8, hx - 3, hy + 8], lift, "")
                for sgn in (-1, 1):
                    self._poly([hx + sgn * 13, hy - 4, hx + sgn * 27, hy - 2,
                                hx + sgn * 24, hy + 9, hx + sgn * 12, hy + 6],
                               _shade(head_color, 1.05), "")
                # under-eye: slightly darker, thinner skin
                for sgn in (-1, 1):
                    self._poly([hx + sgn * 7, hy - 9, hx + sgn * 21, hy - 8,
                                hx + sgn * 19, hy - 3, hx + sgn * 8, hy - 4],
                               _shade(head_color, 0.88), "")

            # --- wrinkles / folds: creases are darker than the plane they
            # sit in, which is what makes them read as depth -----------
            if lod >= 1:
                for (kind, pts, w) in sk["wrinkles"]:
                    if lod < 2 and kind in ("undereye", "eye"):
                        continue
                    flat = []
                    for (ux, uy) in pts:
                        flat += [hx + ux, hy + uy]
                    L(*flat, fill=crease, width=max(1, int(w * 2)), smooth=True)

            # --- pores: the bulk of the detail, emitted only at LOD 2.
            # Each is a 1px mark (cheapest canvas item); oily regions get
            # a highlight pip beside the pore so it catches light ------
            if lod >= 2:
                for (px, py, r, depth, oil, tone) in _stride(sk["pores"],
                                                             SKIN_ITEM_BUDGET):
                    ax, ay = hx + px, hy + py
                    shade = 0.74 - 0.14 * depth + tone
                    L(ax, ay, ax + r, ay + r,
                      fill=_shade(head_color, max(0.35, shade)), width=1)
                    if oil > 0.6 and r > 0.85:
                        L(ax - r * 0.6, ay - r * 0.6, ax - r * 0.2, ay - r * 0.2,
                          fill=lift, width=1)

            # --- pigmentation ---------------------------------------
            if lod >= 1:
                for (fx, fy, fr, strength) in sk["freckles"]:
                    if lod < 2 and fr < 1.0:
                        continue
                    L(hx + fx, hy + fy, hx + fx + fr, hy + fy + fr,
                      fill=_shade(head_color, 0.62 - 0.22 * strength),
                      width=max(1, int(fr)))

            # --- stubble + lip creases ------------------------------
            if lod >= 2:
                for (sx, sy, ang, ln) in _stride(sk["stubble"],
                                                 SKIN_ITEM_BUDGET // 4):
                    L(hx + sx, hy + sy,
                      hx + sx + _cw_math.sin(ang) * ln,
                      hy + sy - _cw_math.cos(ang) * ln * 0.55,
                      fill=darker, width=1)
                pass    # lip creases are drawn ON the lips by _draw_mouth
            return

        # ------------------------------------------------------------ over
        # eyebrows: individual directional strands, not one polygon
        if lod >= 1:
            step = 1 if lod >= 2 else 2
            brow = self.__dict__.get("_brow", {})
            for (bx, by, ang, ln, strength) in sk["brows"][::step]:
                din, dout = brow.get(1 if bx > 0 else -1, (0.0, 0.0))
                tt = clamp01((abs(bx) - 6.5) / 16.5)
                by = by + din + (dout - din) * tt
                L(hx + bx, hy + by,
                  hx + bx + _cw_math.cos(ang) * ln,
                  hy + by + _cw_math.sin(ang) * ln,
                  fill=_shade(hair_c, 0.8 + 0.3 * strength),
                  width=2 if (lod >= 2 and strength > 0.8) else 1)

        # eyelashes: fine curved geometry off the upper lid
        if lod >= 2:
            o = self.__dict__.get("_eye_o", 1.0)
            for (lx, ly, curl, ln, side) in sk["lashes"]:
                # lashes ride the upper lid: rescale their height about the eye centre
                ly = -14.0 + (ly + 14.0) * (5.4 * o) / 4.6
                x0, y0 = hx + lx, hy + ly
                mx = x0 + _cw_math.cos(curl) * ln * 0.6
                my = y0 + _cw_math.sin(curl) * ln * 0.6
                x1 = mx + _cw_math.cos(curl - 0.5 * side) * ln * 0.5
                y1 = my + _cw_math.sin(curl - 0.5 * side) * ln * 0.5
                L(x0, y0, mx, my, x1, y1, fill="#15100e", width=1, smooth=True)

        # scalp hair strands, swept back over the hairline
        if lod >= 1:
            step = 1 if lod >= 2 else 3
            bd = self._cloth_body()
            hcol = _shade(self._hair_col(), 1.0 - 0.3 * bd["wet"])
            sway = self.__dict__.get("_cloth_x", 0.0) * 0.45
            droop = 1.0 - 0.5 * bd["wet"]           # wet hair lies flat
            for (hx0, hy0, sweep, ln, strength) in sk["hair"][::step]:
                x0, y0 = hx + hx0, hy + hy0
                ln2 = ln * droop
                tip = sway * (ln / 10.0) * (0.6 + 0.4 * strength)
                x1 = x0 + sweep * ln2 * 0.55 + tip
                y1 = y0 - ln2
                L(x0, y0, x0 + sweep * 2.0 + tip * 0.4, y0 - ln2 * 0.55, x1, y1,
                  fill=_shade(hcol, 0.75 + 0.45 * strength),
                  width=2 if lod >= 2 and strength > 0.75 else 1, smooth=True)

    def _draw_eye_detail(self, ex, ey, r, lod):
        """Wet eye: sclera shading, iris striations, pupil, lid thickness
        and two specular highlights."""
        if lod < 2:
            return
        px = ex + self.look_x
        py = ey - 1 + self.look_y
        ir = r * 0.62
        # iris striations, radial
        for i in range(12):
            a = i * (_cw_math.tau / 12.0)
            self._line(px + _cw_math.cos(a) * ir * 0.32,
                       py + _cw_math.sin(a) * ir * 0.32,
                       px + _cw_math.cos(a) * ir,
                       py + _cw_math.sin(a) * ir,
                       fill="#6b4a22", width=1)
        self._oval(px - ir * 0.42, py - ir * 0.42, px + ir * 0.42, py + ir * 0.42,
                   "#120d0a", "")
        # specular: a bright pip and a weaker bounce
        self._line(px - ir * 0.55, py - ir * 0.62, px - ir * 0.2, py - ir * 0.42,
                   fill="#ffffff", width=2)
        self._line(px + ir * 0.35, py + ir * 0.4, px + ir * 0.55, py + ir * 0.5,
                   fill="#cfd8e6", width=1)
        # lid thickness: a darker rim above, a lighter one below
        self._line(ex - r, ey - r * 0.75, ex, ey - r * 1.02, ex + r, ey - r * 0.75,
                   fill="#2a1f18", width=2, smooth=True)
        self._line(ex - r * 0.8, ey + r * 0.85, ex, ey + r * 1.0, ex + r * 0.8,
                   ey + r * 0.85, fill="#d9b9a2", width=1, smooth=True)

    def draw(self):
        self.clear()
        moving = self.behavior in ("move", "curious")
        low = self.detail == "low"

        # continuous expression (see _cr_affect_step): bob phase and rate are
        # accumulated, so mood never makes the body jump mid-cycle
        A = self._aff()
        bob_amp = (6.0 if moving else 4.0) * (0.55 + 0.45 * A["energy"])
        bob = _cw_math.sin(self.__dict__.get("_bob_ph", self.t * 2.0)) * bob_amp
        # no whole-body sine bob: the gait (compass drop, weight transfer)
        # owns vertical motion now; the bob lifted the body off planted feet
        cx, cy = self.x + self._sway, self.y
        lod = 0 if low else _skin_lod(self._zoom())
        self._skin_lod_cur = lod

        # stable skin; emotion only as physiology (flush / pallor), continuously
        skin = self._skin_tone()
        head_color = _mix_hex(_mix_hex(skin, "#cf6656", 0.16 * A["flush"]), "#c5c9d1",
                              0.14 * A["pallor"])
        body_color = _mix_hex(skin, "#cf6656", 0.06 * A["flush"])
        limb_color = _shade(body_color, 0.82)
        joint_color = _shade(body_color, 0.55)

        tilt = self.__dict__.get("_tilt_s", 0.0) + self.head_yaw * 9.0
        gesture = _cw_math.sin(self.t * 3.1) * 3 if self.speaking > 0 else 0
        breath = _cw_math.sin(self.__dict__.get("_breath_ph", self.t * 2.0)) * \
            (1.1 + 0.5 * A["tension"])

        pelvis, spine1, chest, neck, legs, arms = self._pose(cx, cy, moving, tilt, gesture)

        self.__dict__["_last_pose"] = (pelvis, spine1, chest, neck, legs, arms)

        # --- ground shadow: sits ON the ground plane the feet actually use
        # (self.y + 85*build), centred on the weight, and tightens as the
        # body lowers. The old one was a fixed 34px slab bracketing y+78..92,
        # so it straddled the feet, ignored build, and never followed the
        # weight shift - which is why it read as a detached black puddle.
        gb = self.build
        gnd = self._terrain_at(self.x) - 3.0 * gb   # shadow on the terrain surface
        wsh = (self.x + self._loco.foot["L"] + self._loco.foot["R"]) / 3.0
        lift_avg = (self._loco.lift["L"] + self._loco.lift["R"]) * 0.5
        sw = (0.95 * self._H() + 0.75 * lift_avg)
        sh_h = 3.4 * gb
        self._oval(wsh - sw, gnd - sh_h + 3.0 * gb, wsh + sw, gnd + sh_h + 3.0 * gb,
                   "#0d1016", "")
        # tighter, darker core directly under the supporting foot
        self._oval(wsh - sw * 0.5, gnd - sh_h * 0.6 + 3.0 * gb,
                   wsh + sw * 0.5, gnd + sh_h * 0.6 + 3.0 * gb, "#080a0e", "")

        # back hair is the FURTHEST layer of the body: drawn first, so the
        # torso, arms and face sit in front of it (it used to be drawn after
        # the torso and covered her whole body)
        self._draw_hair_back(neck, tilt, A, lod, low)

        # -- legs: single-polygon muscle bellies, articulated knee, real foot
        H = self._H()
        # whole-body bounds in world space (crown to sole) for click hit-tests
        self._bbox = (pelvis[0] - 1.1 * H, neck[1] - 1.25 * H, pelvis[0] + 1.1 * H,
                      getattr(self, "_ground_y", self.y + 85 * self.build) + 0.4 * H)
        b = H / 22.0                     # body detail unit, derived from the head
        face = 1.0 if self._loco.facing >= 0 else -1.0
        for side in self._depth_order():             # far leg first (behind)
            b = H / 22.0
            hip, knee, ankle = legs[side]
            # the far leg is a touch darker: cheap depth separation
            thigh_c = _shade(limb_color, self._far(side))
            # ONE continuous skin surface hip -> knee -> ankle. Two separate
            # polys plus a cap circle is what made the knee read as a hinge;
            # a mitred chain turns through the joint with no notch and no
            # exposed pivot, swelling slightly where it bends.
            lnodes = [hip,
                      ((hip[0] + knee[0]) * 0.5, (hip[1] + knee[1]) * 0.5),
                      knee,
                      ((knee[0] + ankle[0]) * 0.5, (knee[1] + ankle[1]) * 0.5),
                      ankle]
            lwid = self._leg_wid()
            self._poly(_chain_skin(lnodes, lwid, 1.16, 0.30), thigh_c, "", smooth=True)
            if not low:
                self._limb_light(lnodes, lwid, thigh_c, lod)
            if not low:
                # quadriceps highlight and a soft shadow behind the knee -
                # volume cues instead of a drawn-on joint
                self._poly(_muscle_poly(
                    hip, knee, 4.6 * b, 5.2 * b, 2.6 * b, 0.34),
                    _shade(thigh_c, 1.05), "")
                self._oval(knee[0] - 2.2 * b, knee[1] + 1.2 * b,
                           knee[0] + 2.2 * b, knee[1] + 3.4 * b,
                           _shade(thigh_c, 0.78), "")
                cr = _joint_crease(lnodes, lwid, 2) or ((knee[0], knee[1], knee[0], knee[1]), 0.0)
                (x0, y0, x1, y1), amt = cr
                self._line(x0, y0, x1, y1, fill=_shade(thigh_c, 0.64),
                           width=max(1, int(1 + amt)))

            # trousers over the leg skin (same skeleton, wider surface)
            self._draw_pants(side, hip, knee, ankle, b, lod, low, face)

            # feet are ~0.85H long: they get their own unit from the same H
            b = H / 17.5
            # foot + shoe roll about the ankle with the heel-toe gait
            self._rot_begin(ankle[0], ankle[1], (self._loco.pitch[side] + self._heel()[0]) * face
                            + self._slope_at(ankle[0]))
            # --- foot: heel, arch and toe box as separate masses ---------
            fx, fy = ankle
            heel = fx - face * 3.4 * b
            toe = fx + face * 11.5 * b
            self._poly([heel - face * 2.2 * b, fy - 2.4 * b, fx + face * 1.0 * b, fy - 3.0 * b,
                        fx + face * 4.0 * b, fy + 1.0 * b, toe, fy + 4.2 * b,
                        toe - face * 1.0 * b, fy + 6.2 * b, heel - face * 2.6 * b, fy + 6.2 * b],
                       _shade(thigh_c, 0.74), "")
            # ankle bone + arch shadow
            if not low:
                self._oval(fx - 2.6 * b, fy - 3.2 * b, fx + 2.6 * b, fy + 1.6 * b,
                           _shade(thigh_c, 0.84), "")
                self._poly([fx + face * 1.0 * b, fy + 4.4 * b, toe - face * 2.0 * b, fy + 5.0 * b,
                            toe - face * 2.0 * b, fy + 6.2 * b, fx + face * 1.0 * b, fy + 6.2 * b],
                           _shade(thigh_c, 0.6), "")
            # toes only at close range, and only when barefoot
            if lod >= 2 and self._cloth_body().get("barefoot"):
                for ti in range(4):
                    tx = fx + face * (6.0 + ti * 1.7) * b
                    self._oval(tx - 0.9 * b, fy + 4.1 * b, tx + 0.9 * b, fy + 6.3 * b,
                               _shade(thigh_c, 0.8 - ti * 0.02), "")
            if not self._cloth_body().get("barefoot"):
                self._draw_shoe(side, ankle, b, lod, low, face)
            self._rot_end()
            if not low:
                # contact shadow shrinks as the foot leaves the ground
                # (always emitted - zero-size while the foot is up - so the
                # pooled draw sequence stays stable through every step)
                gcontact = 1.0 - min(1.0, self._loco.lift[side] / (7.0 * b))
                fw = (6.5 * b) * gcontact if gcontact > 0.05 else 0.0
                gy = self._terrain_at(fx)
                sh = 1.6 * b if fw else 0.0
                self._oval(fx - fw, gy - sh, fx + fw + (face * 3.0 * b if fw else 0.0),
                           gy + sh, _shade("#0d1016", 1.0 + 0.5 * (1.0 - gcontact)), "")

        # -- torso: pelvis -> abdomen -> chest, distinct faceted plates ---
        b = H / 22.0
        pw = H                           # torso half-widths are SHAPE ratios of H
        pelvis_top = ((pelvis[0] + spine1[0]) * 0.5, (pelvis[1] + spine1[1]) * 0.5)
        # hourglass silhouette from the body shape (Creature.SHAPE / m38):
        # full hips -> narrow waist -> ribcage, each one smooth surface
        S = self.SHAPE
        hipw, waist, rib = pw * S["hip"], pw * S["waist"], pw * S["rib"]
        self._poly(_muscle_poly(pelvis, pelvis_top, hipw * 0.92, hipw, waist * 1.12, 0.34),
                   _shade(body_color, 0.8), "", smooth=True)
        self._poly(_muscle_poly(pelvis_top, spine1, waist * 1.12, waist, rib * 0.84, 0.45),
                   _shade(body_color, 0.86), "", smooth=True)
        self._poly(_muscle_poly(spine1, chest, rib * 0.84, rib + breath, rib * 0.92 + breath, 0.6),
                   body_color, "", smooth=True)
        # round shoulder caps: the deltoid wraps over the joint (no square corner)
        for sd in ("L", "R"):
            shx, shy = arms[sd][0]
            cap = self._cap_color(body_color) if hasattr(self, "_cap_color") else body_color
            self._oval(shx - 0.21 * H, shy - 0.16 * H, shx + 0.21 * H, shy + 0.24 * H,
                       _shade(cap, self._far(sd) * 0.98), "")
        # upper chest up to the shoulder line (the skeleton now puts the
        # shoulders ABOVE the chest point, as in a real torso)
        shy = (arms["L"][0][1] + arms["R"][0][1]) * 0.5
        self._poly(_muscle_poly(chest, (chest[0], shy), rib * 0.92 + breath,
                                rib * 1.0, 0.8 * H * self.SHAPE["shoulder"], 0.55),
                   body_color, "", smooth=True)
        if not low:
            self._limb_light([pelvis, pelvis_top, spine1, chest],
                             [hipw * 0.9, waist, rib * 0.84, rib * 0.9],
                             body_color, lod, ruddy=False)
        if not low and lod >= 1:
            # sternum groove + lower rib shadow
            self._line(chest[0], chest[1] + 2, spine1[0], spine1[1] - 4,
                       fill=_shade(body_color, 0.78), width=2)
            self._poly([spine1[0] - pw * 0.5, spine1[1] - 3, spine1[0] + pw * 0.5, spine1[1] - 3,
                        spine1[0] + pw * 0.42, spine1[1] + 3, spine1[0] - pw * 0.42, spine1[1] + 3],
                       _shade(body_color, 0.86), "")
        if not low:
            self._poly([chest[0] - pw * 0.6, chest[1] - 4, chest[0] - pw * 0.75, chest[1] + 8,
                       chest[0] - pw * 0.4, chest[1] + 6], _shade(body_color, 0.7))

        if not low:
            self._draw_abdomen_ao(pelvis, pelvis_top, spine1, chest, arms, pw,
                                  body_color, lod)

        # trapezius: fills the neck-to-shoulder gap so the neck grows out of
        # the torso instead of plugging into it
        if not low:
            lsh = arms["L"][0]
            rsh = arms["R"][0]
            self._poly([lsh[0], lsh[1] + 2 * b,
                        neck[0] - 0.21 * H, neck[1] + 0.35 * H,
                        neck[0] + 0.21 * H, neck[1] + 0.35 * H,
                        rsh[0], rsh[1] + 2 * b,
                        rsh[0], rsh[1] + 7 * b,
                        lsh[0], lsh[1] + 7 * b],
                       _shade(body_color, 0.94), "")

        # shirt / jacket / raincoat over the torso (after the trapezius so
        # the fabric covers the shoulder line)
        self._draw_shirt(pelvis, pelvis_top, spine1, chest, arms, pw, b, lod, low)

        # -- arms, with a shoulder contact shadow against the chest -------
        for side in ("L", "R"):
            shoulder, elbow, wrist = arms[side]
            if not low:
                # sized to her (not fixed pixels) and toned from the limb, so it
                # reads as soft shading, never as a grey disc at the shoulder
                self._oval(shoulder[0] - 0.13 * H, shoulder[1] - 0.06 * H, shoulder[0] + 0.13 * H, shoulder[1] + 0.2 * H,
                           _shade(limb_color, 0.84), "")
            # deltoid cap over the shoulder joint, then biceps / forearm
            if not low:
                self._poly(_muscle_poly(
                    (shoulder[0], shoulder[1] - 3.0 * b),
                    (shoulder[0] + (elbow[0] - shoulder[0]) * 0.34,
                     shoulder[1] + (elbow[1] - shoulder[1]) * 0.34),
                    0.19 * H, 0.2 * H, 0.15 * H, 0.4), _shade(limb_color, 1.04), "")
            anodes = [shoulder,
                      ((shoulder[0] + elbow[0]) * 0.5, (shoulder[1] + elbow[1]) * 0.5),
                      elbow,
                      ((elbow[0] + wrist[0]) * 0.5, (elbow[1] + wrist[1]) * 0.5),
                      wrist]
            awid = self._arm_wid()
            self._poly(_chain_skin(anodes, awid, 1.15, 0.32), _shade(limb_color, self._far(side)), "",
                       smooth=True)
            if not low:
                self._limb_light(anodes, awid, limb_color, lod)
                # shoulder-cap specular, on the side facing the key light
                if lod >= 1:
                    klx, kly = _KEY_LIGHT
                    sx0, sy0 = shoulder[0] + klx * 2.2 * b, shoulder[1] - 1.6 * b + kly * 0.8 * b
                    self._oval(sx0 - 2.2 * b, sy0 - 1.2 * b, sx0 + 2.2 * b, sy0 + 1.2 * b,
                               _mix_hex(limb_color, "#ffffff",
                                        0.14 + 0.16 * getattr(self, "_light_level", 1.0)), "")
                if lod >= 2:
                    self._forearm_veins(elbow, wrist, limb_color, side, b)
            if not low:
                self._poly(_muscle_poly(shoulder, elbow, 3.4 * b, 3.9 * b,
                                        2.0 * b, 0.40), _shade(limb_color, 1.05), "")
                cr = _joint_crease(anodes, awid, 2) or ((elbow[0], elbow[1], elbow[0], elbow[1]), 0.0)
                (x0, y0, x1, y1), amt = cr
                self._line(x0, y0, x1, y1, fill=_shade(limb_color, 0.66),
                           width=max(1, int(1 + amt)))

            self._draw_sleeve(side, shoulder, elbow, wrist, b, lod, low)

            # --- hand: one method, continuous skin (see _cr_draw_hand). The
            # old outlined circles on elbow/shoulder (exposed ball joints) are gone.
            self._draw_hand(side, elbow, wrist, b, lod, low, face, limb_color, A)

        # -- neck ----------------------------------------------------------
        # neck: from the shoulder line up to the jaw, ~0.4H wide
        nbase = ((arms["L"][0][0] + arms["R"][0][0]) * 0.5, (arms["L"][0][1] + arms["R"][0][1]) * 0.5)
        self._poly(_muscle_poly(nbase, neck, 0.24 * H, 0.19 * H, 0.18 * H, 0.5),
                   _shade(head_color, 0.84), "", smooth=True)
        if not low:
            self._draw_neck_detail(chest, neck, arms, head_color, body_color, lod)
        self._draw_collar(chest, neck, arms, b, lod, low)


        # -- head: distinctive procedural face ------------------------------
        hx = neck[0] + tilt * 0.3 + self.skull_shift + self.head_yaw * 4.0
        # the chin (head-local +17) sits on top of the neck
        hy = neck[1] - 17.0 + self.head_pitch * 3.5
        self.head_anchor = (hx, hy)
        # head carriage: lifted by confidence, dropped by a lowered gaze,
        # pulled up into the shoulders by tension - all continuous
        hy += 3.2 * A["gaze"] - 2.0 * max(0.0, A["chest"]) - 1.4 * max(0.0, A["shoulder"])

        hair_color = _shade(head_color, 0.55)
        jaw_open = 2 + (6 if self.speaking > 0 and _cw_math.sin(self.t * 16) > 0 else 0)

        # head size relative to the body. ~0.62 puts the skull at roughly an
        # eighth of the standing figure instead of a third. It rides
        # self.build so bigger-built creatures keep a proportionate head.
        # Scale about the CHIN/neck junction (hy + 17 in head-local units),
        # not the head centre: scaling about the centre lifts the chin off
        # the neck and the skull floats. Pinning the chin keeps the head
        # seated on the neck at any scale factor.
        # head drawn at exactly H tall (its local chin-to-crown span is 55.5)
        self._head_scale_begin(hx, hy + 17.0, H / 55.5)
        try:
            if self.SHAPE.get("face_hd"):
                # dedicated layered face construction (m38 for Jane)
                self._draw_face_hd(hx, hy, head_color, lod, low, jaw_open)
                self._draw_makeup(hx, hy, head_color, lod, low)
            else:

                # --- cranium: a computed profile, not a box. Width is sampled from
                # a skull curve (wide at the parietal, tapering to the temples, then
                # narrowing again into the jaw), so the silhouette reads as a head
                # instead of a stack of rectangles. self.asym/skull_shift ride the
                # profile so each identity keeps its own cranial shape. -----------
                skull = []
                for i in range(11):                       # brow line -> crown, left side
                    t = i / 10.0
                    yy = hy - 6 - t * 30.0
                    # cosine falloff: full width at the temples, tucked at the crown
                    wdt = 33.0 * (0.62 + 0.38 * _cw_math.cos((t - 0.28) * 2.1)) - t * 3.0
                    skull.append((-wdt - self.asym * (1.0 - t), yy))
                crown = [(self.skull_shift * 1.6, hy - 38.5)]
                right = [(-x + self.skull_shift * 0.6, y) for (x, y) in reversed(skull)]
                face_lower = [(-26.0, hy + 6), (-21.0, hy + 13 + jaw_open * 0.4),
                              (0.0, hy + 17 + jaw_open * 0.6),
                              (21.0, hy + 13 + jaw_open * 0.4), (26.0, hy + 6)]
                prof = []
                for (ux, uy) in skull + crown + right:
                    prof += [hx + ux, uy]
                for (ux, uy) in reversed(face_lower):
                    prof += [hx + ux, uy]
                self._poly(prof, head_color, "", smooth=True)

                # temple / side planes, one step darker - the turn away from the key
                self._poly([hx - 33, hy - 20, hx - 27, hy - 26, hx - 23, hy - 4,
                           hx - 27, hy + 6], _shade(head_color, 0.86), "")
                self._poly([hx + 33, hy - 20, hx + 27, hy - 26, hx + 23, hy - 4,
                           hx + 27, hy + 6], _shade(head_color, 0.86))

                # brow ridge: the plane that actually catches light on a forehead
                self._poly([hx - 26, hy - 21, hx + 26, hy - 21, hx + 23, hy - 13,
                           hx - 23, hy - 13], _shade(head_color, 0.95), "")

                self._draw_hair_volume(hx, hy, lod, low)

                # --- nose: bridge, lobule tip, alar wings, nostrils. Shortened so
                # it ends at hy+5.6 - it used to run to hy+11.6 and the lips
                # (hy+3..11) were drawn straight over it.
                lvl = getattr(self, "_light_level", 1.0)
                nb = 4.0 * self.SHAPE["nose"]
                self._poly([hx - nb, hy - 12, hx + nb, hy - 12, hx + nb * 1.2, hy + 1.5,
                           hx - nb * 1.2, hy + 1.5], _shade(head_color, 0.93), "")
                self._poly([hx - 5.4, hy + 0.5, hx + 5.4, hy + 0.5, hx + 5.2, hy + 4.0,
                           hx + 2.6, hy + 5.6, hx - 2.6, hy + 5.6, hx - 5.2, hy + 4.0],
                           _shade(head_color, 0.85), "")
                for sgn in (-1, 1):
                    self._poly([hx + sgn * 4.6, hy + 1.2, hx + sgn * 7.6, hy + 3.2,
                               hx + sgn * 7.0, hy + 5.6, hx + sgn * 3.8, hy + 5.4],
                              _shade(head_color, 0.76), "")
                if not low:
                    for sgn in (-1, 1):
                        x0, x1 = sorted((hx + sgn * 1.2, hx + sgn * 4.0))
                        self._oval(x0, hy + 4.3, x1, hy + 5.8, "#2a1512", "")
                        # alar crease wrapping the wing
                        self._line(hx + sgn * 7.8, hy + 2.4, hx + sgn * 8.5, hy + 4.2,
                                   hx + sgn * 7.2, hy + 6.0, fill=_shade(head_color, 0.62),
                                   width=1, smooth=True)
                        # thin nostril rim transmits light: warm subsurface edge
                        self._line(hx + sgn * 3.9, hy + 5.7, hx + sgn * 6.9, hy + 5.5,
                                   fill=_mix_hex(head_color, "#d0584a", 0.28 + 0.14 * lvl),
                                   width=1)

                # --- cheeks: zygomatic plane, lifted, plus a softer lower mass ----
                for sgn in (-1, 1):
                    self._poly([hx + sgn * 12, hy - 6, hx + sgn * 27, hy - 3,
                               hx + sgn * 25, hy + 5, hx + sgn * 11, hy + 3],
                              _shade(head_color, 1.03), "")
                    self._poly([hx + sgn * 11, hy + 3, hx + sgn * 25, hy + 5,
                               hx + sgn * 21, hy + 13, hx + sgn * 9, hy + 11],
                              _shade(head_color, 0.9), "")

                # --- jaw + chin: a hinged mass that opens, with a distinct chin ball
                jw = 26.0 * self.SHAPE["jaw"]
                self._poly([hx - jw, hy + 6, hx + jw, hy + 6, hx + jw * 0.72, hy + 13 + jaw_open * 0.4,
                           hx, hy + 17 + jaw_open * 0.6, hx - jw * 0.72, hy + 13 + jaw_open * 0.4],
                          _shade(head_color, 0.8), "", smooth=True)
                self._poly([hx - 8, hy + 11 + jaw_open * 0.4, hx + 8, hy + 11 + jaw_open * 0.4,
                           hx + 6, hy + 16 + jaw_open * 0.6, hx - 6, hy + 16 + jaw_open * 0.6],
                          _shade(head_color, 0.84), "")

                # --- specular: the oily T-zone catches the key light. Shifted toward
                # the light so the highlight sits on the side that faces it.
                if not low and lod >= 1:
                    klx, kly = _KEY_LIGHT
                    spec = _mix_hex(head_color, "#ffffff", 0.16 + 0.16 * lvl)
                    fx0 = hx + klx * 5.0
                    self._oval(fx0 - 7.0, hy - 27.0 + kly * 1.5, fx0 + 5.0, hy - 23.8 + kly * 1.5,
                               spec, "")
                    self._oval(hx + klx * 1.6 - 1.4, hy + 1.6, hx + klx * 1.6 + 1.2, hy + 3.2,
                               _mix_hex(head_color, "#ffffff", 0.24 + 0.2 * lvl), "")
                    for sgn in (-1, 1):             # cheekbone sheen
                        cxx = hx + sgn * 19 + klx * 2.0
                        self._oval(cxx - 3.6, hy - 5.6, cxx + 3.6, hy - 3.8,
                                   _mix_hex(head_color, "#ffffff", 0.08 + 0.1 * lvl), "")

                # skin micro-surface, under the eyes/brows
                if lod >= 1:
                    self._draw_skin(hx, hy, head_color, lod, "under")
                if not low:
                    etl = _cw_math.sin(self.t * 3.7) * 0.8 if _cw_random.random() < 0.05 else 0
                    etr = _cw_math.sin(self.t * 3.2) * 0.7 if _cw_random.random() < 0.05 else 0
                    # ears: helix rim, antihelix ridge, concha bowl, tragus, lobe.
                    # The rim is thin cartilage, so it transmits light warm (SSS).
                    for sgn, et in ((-1, etl), (1, etr)):
                        ox = hx + sgn * 32.5
                        self._poly([ox, hy - 16, ox + sgn * 4.6 + sgn * et, hy - 15,
                                    ox + sgn * 6.2 + sgn * et, hy - 10, ox + sgn * 5.2, hy - 4,
                                    ox + sgn * 3.0, hy + 0.5, ox + sgn * 0.6, hy - 1],
                                   _shade(head_color, 0.84), "")
                        if lod >= 1:
                            self._line(ox + sgn * 1.0, hy - 15.6, ox + sgn * 4.6 + sgn * et, hy - 15,
                                       ox + sgn * 6.2 + sgn * et, hy - 10, ox + sgn * 5.2, hy - 4,
                                       fill=_mix_hex(head_color, "#d0584a",
                                                     0.26 + 0.16 * getattr(self, "_light_level", 1.0)),
                                       width=2, smooth=True)
                            cx0, cx1 = sorted((ox + sgn * 1.2, ox + sgn * 3.9))
                            self._oval(cx0, hy - 9.5, cx1, hy - 4.0, _shade(head_color, 0.6), "")
                            self._line(ox + sgn * 2.2, hy - 13.6, ox + sgn * 4.3, hy - 10.6,
                                       ox + sgn * 3.4, hy - 6.4, fill=_shade(head_color, 0.72),
                                       width=1, smooth=True)
                        if lod >= 2:
                            tx0, tx1 = sorted((ox + sgn * 0.2, ox + sgn * 1.6))
                            self._oval(tx0, hy - 7.6, tx1, hy - 5.2, _shade(head_color, 0.9), "")
                            lx0, lx1 = sorted((ox + sgn * 1.2, ox + sgn * 3.8))
                            self._oval(lx0, hy - 2.2, lx1, hy + 0.8,
                                       _mix_hex(head_color, "#d0584a", 0.16), "")

                mouth_style = FACE.get(self.emotion, ("open", "small_smile"))[1]
                for side in (-1, 1):
                    ex, ey = hx + side * 14, hy - 14
                    self._draw_eye(ex, ey, side, lod, low, head_color)
                    self._draw_brow(hx, hy, side, head_color)

                # --- mouth: real lip geometry deformed by expression -------------
                # Replaces the old stroked arcs, whose ellipse bottoms sat at hy+24
                # - below the chin (hy+17) - so the "smile" was drawn on the neck.
                self._draw_mouth(hx, hy, head_color, lod, mouth_style, jaw_open, low)

                # brows / lashes / scalp hair ride above the face and the eyes
                if lod >= 1:
                    self._draw_skin(hx, hy, head_color, lod, "over")
                if not low and lod >= 1:
                    self._draw_hairline(hx, hy, head_color, lod)
                self._draw_makeup(hx, hy, head_color, lod, low)
                if self._cloth_body()["outfit"] == "rain" and self.SHAPE.get("hood", True):
                    self._draw_hood(hx, hy, lod, low)
        finally:
            self._head_scale_end()

        # neck folds + knuckle creases: body-side detail, close range only
        if lod >= 2:
            nkx, nky = neck
            for (fx0, fy0, fw, fwidth) in self._skin["neck_folds"]:
                self._line(nkx + fx0, nky + fy0, nkx + fx0 + fw, nky + fy0 + 0.8,
                           fill=_shade(head_color, 0.6), width=max(1, int(fwidth * 2)),
                           smooth=True)
            for side in ("L", "R"):
                wxx, wyy = arms[side][2]
                for (kx, ky, kw) in self._skin["knuckles"]:
                    self._line(wxx + kx, wyy + ky - 1.6, wxx + kx, wyy + ky + 1.6,
                               fill=_shade(limb_color, 0.6), width=1)
                self._line(wxx - 4, wyy + 2.2, wxx, wyy + 3.2, wxx + 4, wyy + 2.2,
                           fill=_shade(limb_color, 0.62), width=1, smooth=True)


# ============================================================================
# Non-invasive installation onto App / FriendActor
# ============================================================================
_PROXY_BY_REAL_ID = {}

_orig_app_init = App.__init__
_orig_on_stage_click = App._on_stage_click
_orig_on_stage_motion = App._on_stage_motion
_orig_friend_actor_init = FriendActor.__init__


def _cw_install_camera(self):
    """Runs once, right after the original App.__init__ has built the real
    stage/world/creature. Repoints world.c / creature.c to a camera-aware
    proxy and starts the camera's own tick loop. Never raises into the
    caller - a failure here degrades to the plain (uncamera'd) renderer."""
    try:
        real = self.stage
        cam = StageCamera(real)
        self._camera = cam
        proxy = _CamCanvasProxy(real, cam)
        _PROXY_BY_REAL_ID[id(real)] = proxy
        world = getattr(self, "world", None)
        if world is not None:
            world.c = proxy
        creature = getattr(self, "creature", None)
        if creature is not None:
            # the creature re-places every item every frame, so it gets its
            # own UNTRACKED proxy: registering ~700 moving items for camera
            # re-projection would be pure overhead
            cproxy = _CamCanvasProxy(real, cam)
            object.__setattr__(cproxy, "_track", False)
            creature.c = cproxy
            self._creature_proxy = cproxy
            cam.set_follow(creature)
        self._world_proxy = proxy
        cam.home()
        cam.home()
        cam.tick()
    except Exception:
        pass


def _patched_app_init(self, *a, **kw):
    _orig_app_init(self, *a, **kw)
    _cw_install_camera(self)


def _patched_on_stage_click(self, event):
    cam = getattr(self, "_camera", None)
    if cam is not None:
        try:
            event.x, event.y = cam.screen_to_world(event.x, event.y)
        except Exception:
            pass
    # the adult-proportioned body is much taller than the original 90px
    # hit circle around the creature's origin: a click anywhere on her body
    # counts as touching her
    bb = getattr(getattr(self, "creature", None), "_bbox", None)
    if bb and bb[0] <= event.x <= bb[2] and bb[1] <= event.y <= bb[3]:
        event.x, event.y = self.creature.x, self.creature.y
    return _orig_on_stage_click(self, event)


def _patched_on_stage_motion(self, event):
    cam = getattr(self, "_camera", None)
    if cam is not None:
        try:
            event.x, event.y = cam.screen_to_world(event.x, event.y)
        except Exception:
            pass
    return _orig_on_stage_motion(self, event)


def _patched_friend_actor_init(self, canvas, *a, **kw):
    _orig_friend_actor_init(self, canvas, *a, **kw)
    proxy = _PROXY_BY_REAL_ID.get(id(canvas))
    if proxy is not None:
        self.c = proxy


App.__init__ = _patched_app_init
App._on_stage_click = _patched_on_stage_click
App._on_stage_motion = _patched_on_stage_motion
FriendActor.__init__ = _patched_friend_actor_init


# ============================================================================
# Physics-driven locomotion + articulated anatomy (in-place upgrade)
# ============================================================================
#
# The original rig drives the gait straight off a time-based sine
# (`phase = self.t * 8`), so the legs cycle at a fixed cadence no matter how
# fast the body is actually travelling, and the feet slide along the ground.
# Everything below replaces that with state that INTEGRATES:
#
#   * stride phase advances with DISTANCE TRAVELLED, not wall-clock time, so
#     cadence emerges from speed - slow drift gives long lazy steps, a dash
#     gives quick ones, and standing still freezes the cycle mid-stance.
#   * each foot is PLANTED in world space while it bears weight and only
#     swings once its stance is spent, which is what kills the foot-slide.
#   * lean, pelvis drop and balance offset are spring-damper responses to the
#     body's measured acceleration, so the torso tips into an acceleration
#     and recovers after a stop instead of being told to.
#   * the spine is a chain: pelvis -> spine -> chest -> neck, each segment
#     rotated by a fraction of the accumulated lean, so a hard stop travels
#     up the body and the head settles last.
#
# Nothing here is a canned clip; `update_locomotion` only ever integrates
# forces and the pose is solved from the resulting state with 2-bone IK.


def _ik2(root, target, l1, l2, bend, soft_k=0.92):
    """2-bone IK. Returns (mid, end).

    `bend` in [-1, 1]. Its SIGN picks which side the joint breaks toward, in
    screen coordinates (y down) for a limb hanging downward: +1 puts the
    joint on the -x side, -1 on the +x side. Its MAGNITUDE < 1 is a turn in
    progress: the joint is swinging round to face the viewer, so it is drawn
    part-way toward the straight line (projection), never flipped in one
    frame. (The previous callers passed +1 when facing +x, which put every
    knee BEHIND the body - legs visibly bending backwards.)"""
    mag = min(1.0, abs(bend))
    bend = 1.0 if bend >= 0 else -1.0
    rx, ry = root
    tx, ty = target
    dx, dy = tx - rx, ty - ry
    d = _cw_math.hypot(dx, dy)
    reach = l1 + l2
    # SOFT IK: acos() is infinitely steep near full extension, so a hard
    # reach limit makes the knee "pop" straight in one frame as a swinging
    # leg reaches forward. Past 92% of reach the effective distance eases
    # asymptotically toward full reach instead, so the joint straightens
    # progressively (the end effector falls a hair short - invisible).
    soft = soft_k * reach
    if d > soft and d > 1e-6:
        span = reach - soft
        ds = soft + span * (1.0 - _cw_math.exp(-(d - soft) / span))
        k = ds / d
        dx, dy = dx * k, dy * k
        tx, ty = rx + dx, ry + dy
        d = ds
    if d > reach * 0.999:                       # out of range: straighten out
        d = reach * 0.999
        if _cw_math.hypot(dx, dy) > 1e-6:
            k = d / _cw_math.hypot(dx, dy)
            dx, dy = dx * k, dy * k
        else:
            dx, dy = 0.0, d
        tx, ty = rx + dx, ry + dy
    d = max(d, 1e-6)
    # law of cosines for the angle between bone 1 and the root->target line
    cosa = clamp((l1 * l1 + d * d - l2 * l2) / (2.0 * l1 * d), -1.0, 1.0)
    a = _cw_math.acos(cosa)
    base = _cw_math.atan2(dy, dx)
    ang = base + a * bend
    mid = (rx + _cw_math.cos(ang) * l1, ry + _cw_math.sin(ang) * l1)
    if mag < 0.999:
        k = l1 / (l1 + l2)
        sx, sy = rx + (tx - rx) * k, ry + (ty - ry) * k
        mid = (sx + (mid[0] - sx) * mag, sy + (mid[1] - sy) * mag)
    return mid, (tx, ty)


class _Loco:
    """Integrated locomotion state. One per creature."""

    STANCE = 0.62          # fraction of a foot's cycle spent bearing weight
    STRIDE = 26.0          # world units per full stride at build 1.0

    def __init__(self, x, y, seed_phase=0.0):
        self.px, self.py = x, y          # previous position, for velocity
        self.vx = self.vy = 0.0
        self.ax = 0.0                    # smoothed horizontal acceleration
        self.speed = 0.0
        self.facing = 1.0                # -1 left, +1 right, interpolated
        self.lean = 0.0                  # radians, torso pitch from inertia
        self.lean_v = 0.0
        self.balance = 0.0               # lateral COM correction
        self.balance_v = 0.0
        self.drop = 0.0                  # pelvis vertical travel
        self.drop_v = 0.0
        self.phase = seed_phase          # stride cycle, advances with distance
        # feet start UNDER the body - defaulting them to world 0 makes the
        # first touchdown plant at the origin and snap the leg across the map
        self.plant = {"L": None, "R": None}   # world x each foot is planted at
        self.lift = {"L": 0.0, "R": 0.0}
        self.foot = {"L": x - 9.0, "R": x + 9.0}   # resolved world x per foot
        self.last_t = {"L": 0.0, "R": 0.5}    # per-foot cycle position, for wrap detection
        self.pitch = {"L": 0.0, "R": 0.0}     # foot roll: + = heel up / toe down
        self.breath = 0.0
        self.exertion = 0.0
        self.fall = 0.0                  # 0 = upright, 1 = fully down
        self.fall_v = 0.0
        self.recovering = False


class Creature(Creature):                 # extend the HD class in place
    """Adds integrated locomotion + articulated hands/ears/eyes on top of the
    HD visual class. Same public API, same landmark envelope."""

    def __init__(self, canvas, x, y, bounds, identity=None):
        super().__init__(canvas, x, y, bounds, identity)
        self._loco = _Loco(x, y, self.gait_offset)

    # -- physics integration ------------------------------------------
    def update(self, dt):
        super().update(dt)
        dt = clamp(dt, 1e-4, 0.1)
        L = self._loco
        b = self.build
        self.__dict__["_fid"] = self.__dict__.get("_fid", 0) + 1     # one step per tick
        # sit down after resting still for a moment; stand up to move. Blended
        # (~1.2 s), so sitting and rising are continuous motions, not snaps.
        still = L.speed < 2.0 and self.behavior == "rest"
        L.sit_t = (getattr(L, "sit_t", 0.0) + dt) if still else 0.0
        want = 1.0 if L.sit_t > 1.5 else 0.0
        # linear progress eased by smoothstep: sitting/rising START and END at
        # zero velocity (an exponential blend starts at full speed - a jerk)
        lin = getattr(L, "sit_lin", 0.0)
        step = 0.6 * dt                  # ~1.7 s to sit down / get up from the ground
        lin = min(want, lin + step) if want > lin else max(want, lin - step)
        L.sit_lin = lin
        L.sit = lin * lin * (3.0 - 2.0 * lin)
        L.still_t = (getattr(L, "still_t", 0.0) + dt) if L.speed < 3.0 else 0.0
        self.__dict__["_fdt"] = dt
        # weather pace: rain, headwind and cold slow the body down. Applied
        # to the displacement m18 just made, BEFORE velocity is measured, so
        # the gait/lean physics see the slower walk as real
        # no walking while seated: travel ramps in as she gets up
        pace = self._cloth_body().get("pace", 1.0) * self.SHAPE.get("speed", 1.0) \
            * clamp01(1.0 - getattr(L, "sit", 0.0) / 0.12) ** 2   # upright first
        if abs(pace - 1.0) > 0.001:
            self.x = L.px + (self.x - L.px) * pace
            self.y = L.py + (self.y - L.py) * pace
        self._cloth_step(dt)

        # velocity measured from the body's ACTUAL travel (m18 moves x/y),
        # so locomotion stays correct whoever is driving the position
        vx = (self.x - L.px) / dt
        vy = (self.y - L.py) / dt
        L.px, L.py = self.x, self.y
        ax_raw = (vx - L.vx) / dt
        L.vx += (vx - L.vx) * clamp(dt * 12.0, 0, 1)
        L.vy += (vy - L.vy) * clamp(dt * 12.0, 0, 1)
        L.ax += (clamp(ax_raw, -4000, 4000) - L.ax) * clamp(dt * 8.0, 0, 1)
        L.speed = _cw_math.hypot(L.vx, L.vy)

        # facing follows travel direction, rate-limited => a real turn
        if abs(L.vx) > 4.0:
            want = 1.0 if L.vx > 0 else -1.0
            L.facing = approach(L.facing, want, 3.2, dt)
        L.facing = clamp(L.facing, -1.0, 1.0)

        # --- lean: spring-damper driven by acceleration. Accelerating tips
        # the torso into the move; a hard stop throws it the other way and
        # it oscillates back - the "believable stopping" behaviour.
        A = self._aff()
        tension = 0.8 + 0.5 * A["tension"]
        lean_target = clamp(-L.ax * 0.00045, -0.30, 0.30) + clamp(L.vx * 0.0016, -0.12, 0.12)
        k, c = 42.0 * tension, 9.0
        L.lean_v += (lean_target - L.lean) * k * dt - L.lean_v * c * dt
        L.lean = clamp(L.lean + L.lean_v * dt, -0.45, 0.45)

        # --- lateral balance correction: the body overshoots then catches
        bal_target = clamp(L.ax * 0.00060, -0.6, 0.6) * 6.0
        L.balance_v += (bal_target - L.balance) * 30.0 * dt - L.balance_v * 7.0 * dt
        L.balance = clamp(L.balance + L.balance_v * dt, -7.0, 7.0)

        # --- stride phase advances with DISTANCE, so cadence emerges -----
        # step ~0.65 x leg length: the swing foot lands ~1.3H ahead of its hip
        stride = 2.1 * self._H() * self.SHAPE.get("stride", 1.0) \
            * (1.0 + 0.35 * min(1.0, L.speed / 90.0))
        moved = _cw_math.hypot(vx, vy) * dt
        if L.speed > 3.0:
            L.phase = (L.phase + moved / max(stride, 1e-3)) % 1.0
            L.exertion = min(1.0, L.exertion + dt * 1.4)
        else:
            L.exertion = max(0.0, L.exertion - dt * 0.8)

        # --- pelvis drop: weight drops onto the planted leg twice a cycle
        drop_t = abs(_cw_math.sin(L.phase * _cw_math.tau)) * 2.2 * b * min(1.0, L.speed / 50.0)
        L.drop_v += (drop_t - L.drop) * 60.0 * dt - L.drop_v * 11.0 * dt
        L.drop += L.drop_v * dt

        # --- breathing: rate rises with exertion and emotional arousal ---
        arousal = clamp(0.5 + 0.55 * (A["breath"] - 0.9), 0.5, 2.0)
        L.breath += dt * (0.85 + 1.5 * L.exertion + 0.55 * arousal * self.intensity)

        # --- fall / recover state machine -------------------------------
        if L.fall > 0.0 or L.recovering:
            if L.recovering:
                L.fall = approach(L.fall, 0.0, 0.85, dt)
                if L.fall <= 0.001:
                    L.fall, L.recovering = 0.0, False
            else:
                L.fall_v += 3.2 * dt
                L.fall = min(1.0, L.fall + L.fall_v * dt)
                if L.fall >= 1.0:
                    L.fall_v = 0.0
                    L.recovering = True

        self._settle_feet(dt, stride, b)

    def stumble(self):
        """Knock the creature off balance; it falls and recovers on its own."""
        L = self._loco
        if L.fall <= 0.0 and not L.recovering:
            L.fall_v = 0.6
            L.fall = 0.001

    def _settle_feet(self, dt, stride, b):
        """Plant / release each foot. A planted foot is FIXED in world space
        (no sliding); it only leaves the ground once its stance is spent, and
        swings to the spot the body will have reached by touchdown."""
        L = self._loco
        # the ANKLE ground line from the world's terrain, not from our own y
        # (y drifts +/-12px inside the stage band - that made her float/sink)
        ground = self._terrain_at(self.x) - self._sole()
        for side, off in (("L", 0.0), ("R", 0.5)):
            t = (L.phase + off) % 1.0
            # a cycle WRAP is what ends a swing. Waiting for u to reach 1.0
            # misses it - the phase step jumps straight past, the old plant
            # survives, and the next stance snaps the foot back to it.
            wrapped = t < L.last_t[side]
            L.last_t[side] = t
            # pivot: a planted foot the body has turned away from (further
            # from its own hip than a leg can comfortably reach) drags round
            # toward it instead of pinning the leg - turning in place.
            own_hip = self.x + (-0.36 if side == "L" else 0.36) * self._H() * self.SHAPE["hip_span"]
            far = 0.62 * sum(self._leg_len())
            if L.plant[side] is not None and abs(L.plant[side] - own_hip) > far:
                tgt = own_hip + far * (1.0 if L.plant[side] > own_hip else -1.0)
                # pivot at a foot's pace (<= ~2.5 head heights/s), never a jump
                vmax = 2.5 * self._H() * dt
                L.plant[side] += clamp(tgt - L.plant[side], -vmax, vmax)
            # heel-toe roll: heel strike (toe up) -> flat -> heel lifts for
            # push-off -> toe lifts for clearance through the swing
            gait = min(1.0, L.speed / 40.0)
            S = _Loco.STANCE
            if t < S:
                if t < 0.12:
                    want = -0.28 * (1.0 - t / 0.12)
                elif t > S - 0.2:
                    want = 0.6 * (t - (S - 0.2)) / 0.2
                else:
                    want = 0.0
            else:
                u = (t - S) / (1.0 - S)
                want = 0.6 * (1.0 - u) ** 3 - 0.32 * _cw_math.sin(_cw_math.pi * u) - 0.22 * u
            want *= gait
            L.pitch[side] += (want - L.pitch[side]) * (1.0 - _cw_math.exp(-dt / 0.05))
            if L.speed < 3.0:
                # STOPPED: a foot caught mid-swing comes down where it is (no
                # swing interpolation - that fought the settle and made the
                # foot jump), then, once genuinely still (a turn passes through
                # zero speed and must not trigger this), eases under its hip.
                L.lift[side] = max(0.0, L.lift[side] - 0.9 * self._H() * dt)
                L.plant[side] = L.foot[side]
                if getattr(L, "still_t", 0.0) > 0.3 and L.lift[side] <= 0.0:
                    rest = self.x + (-0.36 if side == "L" else 0.36) * self._H() * self.SHAPE["hip_span"] \
                        * self.SHAPE.get("rest_width", 1.0)
                    L.foot[side] = approach(L.foot[side], rest, 4.0, dt)
                    L.plant[side] = L.foot[side]
                continue
            if t < _Loco.STANCE:                        # ---- stance
                if L.plant[side] is None or wrapped:
                    # touch down exactly where the swing ENDED. Re-deriving
                    # it from self.x teleports the foot and pops the leg.
                    L.plant[side] = L.foot[side]
                L.foot[side] = L.plant[side]
                L.lift[side] = 0.0
            else:                                       # ---- swing
                u = (t - _Loco.STANCE) / (1.0 - _Loco.STANCE)
                if L.plant[side] is None:
                    L.plant[side] = self.x
                # predicted touchdown: where the body will be, plus half a stride
                # land ahead of THIS foot's own hip (the hips are drawn side by
                # side), half a step forward - measuring from the body centre put
                # the far foot ~29 units from its hip: out of reach
                own = (-0.36 if side == "L" else 0.36) * self._H() * self.SHAPE["hip_span"]
                nxt = self.x + own + L.vx * (1.0 - u) * 0.25 + L.facing * stride * 0.42
                L.foot[side] = L.plant[side] + (nxt - L.plant[side]) * (u * u * (3 - 2 * u))
                # a step always LIFTS the foot (turning steps too, when speed
                # passes near zero) - otherwise the swing foot shuffles along
                L.lift[side] = _cw_math.sin(u * _cw_math.pi) * 0.25 * self._H() * max(
                    0.4, min(1.0, L.speed / 40.0))
            # standing still: feet ease back under the hips
        self._ground_y = ground

    # -- pose solved from that state (no sine gait) --------------------
    def _pose(self, cx, cy, moving, tilt, gesture):
        """Adult skeleton in ONE unit: H = head height (chin to crown).
        Heights from the sole, 8-head figure: knee ~2H, hip joint ~4H,
        waist ~5H, chest ~6.25H, shoulder line ~6.55H, chin 7H, crown 8H.
        Every length below is a fraction of H, and the draw pass sizes
        widths / hands / feet / clothes / the head from the same H - so the
        skeleton, IK and skin share one coordinate system and one scale.
        (The previous rig was 22/22/22 spine + 19/18 legs in fixed units:
        a 4.3-head figure with legs at 32% of height.)"""
        L = self._loco
        H = self._H()
        b = H / 22.0                               # detail unit for small offsets
        thigh, calf = self._leg_len()
        upper, fore = self._arm_len()
        reach = thigh + calf
        facing = 1.0 if L.facing >= 0 else -1.0
        sit = getattr(L, "sit", 0.0)
        lean = L.lean * (1.0 - sit) + L.fall * 0.9 * facing
        bd = self._cloth_body()
        lean += (0.22 * bd["hunch"] * facing - 0.10 * bd["wind"] * bd["wind_dir"]) * (1.0 - sit)
        Aff = self._aff()
        lean += (0.07 * Aff["gaze"] - 0.05 * Aff["chest"]) * facing
        shiver = bd["shiver"] * 1.1 * _cw_math.sin(self.t * 38.0) * b
        fall_drop = L.fall * 1.6 * H
        walk = min(1.0, L.speed / 40.0)
        sway = self.SHAPE["sway"] * (0.10 * H * _cw_math.sin(L.phase * _cw_math.tau) * walk
                                     + 0.075 * H * (1.0 - min(1.0, L.speed / 20.0))) * (1.0 - sit)
        gnd = getattr(self, "_ground_y", self.y + 85 * self.build)
        heel = self._heel()[1] * b
        hip_off = 0.12 * H                          # hip joints sit just below the pelvis point
        hip_y = gnd - heel - self.SHAPE.get("stance", 0.95) * reach - hip_off
        py = hip_y + (cy - self.y) * (1.0 - sit) + L.drop + fall_drop
        # compass gait: sink just enough to keep every foot within 94% reach
        lim = (0.94 + 0.05 * (1.0 - walk)) * reach           # standing still: legs nearly straight
        span = 0.36 * H * self.SHAPE["hip_span"]
        for sd, sg in (("L", -1), ("R", 1)):
            hx_ = cx + L.balance + sway + sg * span
            ay = gnd - L.lift[sd] + fall_drop * 0.35 - heel
            dxf = L.foot[sd] - hx_
            need = ay - _cw_math.sqrt(max(1.0, lim * lim - dxf * dxf)) - hip_off - 0.07 * H
            need = min(need, hip_y + L.drop + fall_drop + 0.22 * H)
            if need > py:
                py = need
        # the compass drop is a BODY response, not an instant constraint: ease
        # it (fast down when a foot needs the reach, gentler back up), once per
        # simulation tick. An instant response jolted the pelvis ~0.2H in a
        # single frame on the first stride of every walk.
        base_py = hip_y + (cy - self.y) * (1.0 - sit) + L.drop + fall_drop
        want_drop = max(0.0, py - base_py)
        fid = self.__dict__.get("_fid", 0)
        cd = self.__dict__.setdefault("_cdrop", [fid, 0.0, 0.0])
        if cd[0] != fid:
            cd[0], cd[1] = fid, cd[2]
        tau = 0.03 if want_drop > cd[1] else 0.12
        cur = cd[1] + (want_drop - cd[1]) * (1.0 - _cw_math.exp(-self.__dict__.get("_fdt", 1 / 60.0) / tau))
        cd[2] = cur
        py = base_py + cur
        # sitting on the ground: seat at the sole line, hip joint ~0.35H above it
        sit_py = gnd + 0.18 * H - 0.35 * H - hip_off
        py += (sit_py - py) * sit
        pelvis = (cx + L.balance + sway, py)

        def up(frm, length, share):
            a = -_cw_math.pi / 2 + lean * share
            return (frm[0] + _cw_math.cos(a) * length, frm[1] + _cw_math.sin(a) * length)

        spine1 = up(pelvis, 1.0 * H, 0.55)          # waist
        chest = up(spine1, 1.22 * H, 0.85)          # upper chest / sternum
        chest = (chest[0] + tilt * 0.35 + shiver, chest[1])
        neck = up(chest, 0.72 * H, 1.15)            # top of the neck, under the jaw
        neck = (neck[0] + tilt * 0.7 + shiver * 1.3, neck[1])
        br = _cw_math.sin(L.breath) * (0.9 + 1.5 * L.exertion) * b
        chest = (chest[0], chest[1] - br * 0.5)

        legs = {}
        for side, sgn in (("L", -1), ("R", 1)):
            hitch = self.SHAPE["sway"] * 0.07 * H * _cw_math.sin(L.phase * _cw_math.tau) \
                * walk * sgn * (1.0 - sit)
            hip = (pelvis[0] + sgn * span, pelvis[1] + hip_off + hitch)
            gf = self._terrain_at(L.foot[side]) - self._sole()        # per-foot terrain
            ankle = (L.foot[side], gf - L.lift[side] + fall_drop * 0.35 - heel)
            if sit > 0.0:                            # feet out in front, knees up
                sx = hip[0] + facing * (2.1 + 0.25 * sgn * facing) * H
                ankle = (ankle[0] + (sx - ankle[0]) * sit, ankle[1] + (gnd - heel - ankle[1]) * sit)
            # standing still the leg may straighten; walking keeps the soft margin
            knee, ank = _ik2(hip, ankle, thigh, calf, -clamp(L.facing, -1.0, 1.0),
                             soft_k=0.92 + 0.065 * (1.0 - min(1.0, L.speed / 20.0)))
            knee = self._damp_joint("k" + side, hip, knee, thigh)
            legs[side] = (hip, knee, ank)

        arms = {}
        drag = clamp(-L.ax * 0.0022, -0.25 * H, 0.25 * H)
        for side, sgn in (("L", -1), ("R", 1)):
            shoulder = (chest[0] + sgn * 0.98 * H * self.SHAPE["shoulder"],
                        chest[1] - 0.3 * H - 0.11 * H * Aff["shoulder"])
            opp = (L.phase + (0.5 if side == "L" else 0.0)) % 1.0
            swing = -_cw_math.sin(opp * _cw_math.tau) * 0.42 * H * min(1.0, L.speed / 55.0)
            hug = bd["hunch"] * 0.7 + bd["cold"] * 0.5
            hand = (shoulder[0] + swing * (1.0 - 0.6 * hug) + drag + gesture * sgn
                    - sgn * hug * 0.33 * H + sgn * 0.1 * H,
                    shoulder[1] + (upper + fore) * (0.93 - 0.05 * L.fall - 0.22 * hug))
            if sit > 0.0:                            # forearms resting on the knees
                kx, ky = legs[side][1]
                hand = (hand[0] + (kx + facing * 0.15 * H - hand[0]) * sit,
                        hand[1] + (ky - 0.05 * H - hand[1]) * sit)
            aim = getattr(self, "_aim", None)          # (tx, ty, weight, draw) - bow aiming
            if aim is not None and aim[2] > 0.01:
                near = "R" if L.facing >= 0 else "L"
                fs = (chest[0] + (0.98 if near == "R" else -0.98) * H * self.SHAPE["shoulder"],
                      chest[1] - 0.3 * H)
                dx_, dy_ = aim[0] - fs[0], aim[1] - fs[1]
                n_ = _cw_math.hypot(dx_, dy_) or 1.0
                ux, uy = dx_ / n_, dy_ / n_
                reach_ = (upper + fore) * 0.96
                front = (fs[0] + ux * reach_, fs[1] + uy * reach_)
                if side == near:
                    ah = front                               # bow arm: extended toward the target
                else:                                        # string hand: drawn back to the face
                    pull = reach_ * (0.3 + 0.62 * aim[3])
                    ah = (front[0] - ux * pull, front[1] - uy * pull)
                w_ = aim[2]
                hand = (hand[0] + (ah[0] - hand[0]) * w_, hand[1] + (ah[1] - hand[1]) * w_)
            rch = getattr(self, "_reach", None)          # (tx, ty, weight): the near hand reaches
            if rch is not None and rch[2] > 0.01 and side == ("R" if L.facing >= 0 else "L"):
                rw = rch[2]
                dx_, dy_ = rch[0] - shoulder[0], rch[1] - shoulder[1]
                n_ = _cw_math.hypot(dx_, dy_) or 1.0
                lim = (upper + fore) * 0.97
                if n_ > lim:
                    dx_, dy_ = dx_ / n_ * lim, dy_ / n_ * lim
                hand = (hand[0] + (shoulder[0] + dx_ - hand[0]) * rw, hand[1] + (shoulder[1] + dy_ - hand[1]) * rw)
            elbow, wrist = _ik2(shoulder, hand, upper, fore, clamp(L.facing, -1.0, 1.0))
            elbow = self._damp_joint("e" + side, shoulder, elbow, upper)
            arms[side] = (shoulder, elbow, wrist)

        return pelvis, spine1, chest, neck, legs, arms


# ============================================================================
# Anatomical limb / hand / foot geometry
# ============================================================================
#
# A limb is ONE polygon with a mid-span bulge rather than a stack of tapered
# quads. That kills the interior seams entirely (no abutting edges to show),
# halves the item count per limb, and gives the muscle belly a believable
# swell - a thigh is widest about a third down, a calf about a quarter down,
# a forearm near the elbow. The bias argument is where that widest point
# sits, so each limb gets its own profile instead of a uniform taper.

def _muscle_poly(p0, p1, w0, wm, w1, bias=0.38, steps=4):
    """Single closed polygon from p0 to p1 whose half-width runs
    w0 -> wm (at `bias` along the span) -> w1, sampled smoothly."""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    ln = _cw_math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / ln, dx / ln
    left, right = [], []
    for i in range(steps + 1):
        t = i / steps
        # two-piece smooth interpolation through the belly width
        if t <= bias:
            u = t / max(bias, 1e-6)
            w = w0 + (wm - w0) * (u * u * (3 - 2 * u))
        else:
            u = (t - bias) / max(1.0 - bias, 1e-6)
            w = wm + (w1 - wm) * (u * u * (3 - 2 * u))
        px, py = x0 + dx * t, y0 + dy * t
        left.append((px + nx * w, py + ny * w))
        right.append((px - nx * w, py - ny * w))
    pts = []
    for (px, py) in left:
        pts += [px, py]
    for (px, py) in reversed(right):
        pts += [px, py]
    return pts


def _finger_chain(base, ang, seglens, curl, width):
    """Return per-segment quads for one finger. Each joint adds `curl`, so
    the finger bends at the knuckles instead of being a straight peg."""
    segs = []
    x, y = base
    a = ang
    w = width
    for i, L in enumerate(seglens):
        a += curl * (0.6 if i == 0 else 1.0)
        nx2, ny2 = x + _cw_math.cos(a) * L, y + _cw_math.sin(a) * L
        segs.append((_limb_quad((x, y), (nx2, ny2), w, w * 0.82), (x, y), (nx2, ny2)))
        x, y = nx2, ny2
        w *= 0.82
    return segs


# ============================================================================
# Canvas item pooling  (fixes Tk_GetPixmap / CreateDIBSection exhaustion)
# ============================================================================
#
# The renderer used to delete every canvas item and recreate it each frame.
# At close zoom that is ~600 creates + ~600 deletes per frame; on Windows each
# canvas item holds GDI objects, and Tk allocates a pixmap per item for
# stippling/anti-aliasing, so the handle table runs dry and Tk raises
#
#     Tk_GetPixmap: Error from CreateDIBSection
#     Not enough memory resources are available to process this command.
#
# It is a HANDLE leak by churn, not a RAM leak - which is why it takes a
# while to appear and why it hits hardest when zoomed in.
#
# The fix: allocate each item ONCE and afterwards only move it. A frame now
# walks a per-kind pool, calling coords()/itemconfig() on existing items and
# creating a new one only when the pool runs short. Items left over at the
# end of a frame are hidden (state="hidden"), not destroyed, so the steady
# state is ZERO creates and ZERO deletes per frame.

class Creature(Creature):                 # extend in place, still one class

    _POOL_KINDS = ("polygon", "oval", "line", "arc")

    def __init__(self, canvas, x, y, bounds, identity=None):
        super().__init__(canvas, x, y, bounds, identity)
        self._pool = {k: [] for k in self._POOL_KINDS}
        self._pidx = {k: 0 for k in self._POOL_KINDS}
        self._pool_on = True

    # -- pooled primitive acquisition ---------------------------------
    def _acquire(self, kind, coords, **cfg):
        pool = self._pool[kind]
        i = self._pidx[kind]
        # last styling applied to each pooled slot: itemconfig is only sent
        # when it actually changed. Colours move on emotion/light changes,
        # not every frame, so most frames cost one coords() per item instead
        # of coords() + itemconfig().
        cache = self.__dict__.setdefault("_pool_cfg", {}).setdefault(kind, [])
        sg = self.__dict__.get("_scene_grade")
        if sg is not None:
            # the creature stands in the foreground (depth ~0): it takes the
            # night/storm/lightning grade but almost none of the distance haze
            gy = getattr(self, "_ground_y", self.y + 85)
            for key in ("fill", "outline"):
                v = cfg.get(key)
                if isinstance(v, str) and len(v) == 7:
                    cfg[key] = sg.color(v, gy)
        cfg["state"] = "normal"
        cfg["tags"] = "creature"          # stage layering: see App._update_world
        self.__dict__.setdefault("_seq", []).append(kind[0])
        sig = tuple(sorted(cfg.items()))
        if i < len(pool):
            item = pool[i]
            try:
                self.c.coords(item, *coords)
                if cache[i] != sig:
                    self.c.itemconfig(item, **cfg)
                    cache[i] = sig
            except Exception:
                # item died underneath us (canvas cleared elsewhere): rebuild
                item = getattr(self.c, "create_" + kind)(*coords, **cfg)
                pool[i] = item
                cache[i] = sig
        else:
            item = getattr(self.c, "create_" + kind)(*coords, **cfg)
            pool.append(item)
            cache.append(sig)
        self._pidx[kind] = i + 1
        self.items.append(item)
        return item

    def _poly(self, pts, fill, outline="#0a0c10", smooth=False):
        if not self._pool_on:
            return super()._poly(pts, fill, outline)
        # smooth=True: Tk spline-rounds the outline. Tk on Windows has no
        # anti-aliasing, so curving organic silhouettes is what removes the
        # straight-edged polygon look on skull, hair, limbs and cloth.
        return self._acquire("polygon", list(pts), fill=fill, outline=outline, width=2,
                             smooth=bool(smooth))

    def _oval(self, x0, y0, x1, y1, fill, outline="#0a0c10"):
        if not self._pool_on:
            return super()._oval(x0, y0, x1, y1, fill, outline)
        return self._acquire("oval", [x0, y0, x1, y1], fill=fill, outline=outline, width=2)

    def _line(self, *coords, **kw):
        if not self._pool_on:
            return super()._line(*coords, **kw)
        kw.setdefault("fill", "#1a1a1a")
        kw.setdefault("width", 1)
        kw.setdefault("smooth", False)      # a reused item must not stay smoothed
        return self._acquire("line", list(coords), **kw)

    def _arc(self, *coords, **kw):
        if not self._pool_on:
            return super()._arc(*coords, **kw)
        kw.setdefault("style", "arc")
        kw.setdefault("outline", "#1a1a1a")
        kw.setdefault("width", 1)
        return self._acquire("arc", list(coords[:4]), **kw)

    def clear(self):
        """Rewind the pools instead of destroying items. Leftovers from the
        previous frame are hidden at the end of draw()."""
        if not self._pool_on:
            return super().clear()
        for k in self._POOL_KINDS:
            self._pidx[k] = 0
        self.items = []
        self.__dict__["_seq"] = []

    def _hide_unused(self):
        for k in self._POOL_KINDS:
            pool = self._pool[k]
            cache = self.__dict__.get("_pool_cfg", {}).get(k)
            for j in range(self._pidx[k], len(pool)):
                if cache is not None and j < len(cache) and cache[j] == "hidden":
                    continue                      # already hidden: no Tk call
                try:
                    self.c.itemconfig(pool[j], state="hidden")
                except Exception:
                    pass
                if cache is not None and j < len(cache):
                    cache[j] = "hidden"

    def destroy(self):
        """Release every pooled item (call if the creature is discarded)."""
        for k in self._POOL_KINDS:
            for it in self._pool[k]:
                try:
                    # a genuine teardown must really free the handles, not
                    # hand them to the proxy's recycler
                    dr = getattr(self.c, "delete_real", None)
                    (dr or self.c.delete)(it)
                except Exception:
                    pass
            self._pool[k] = []
            self._pidx[k] = 0
        self.__dict__["_pool_cfg"] = {}
        self.items = []

    def draw(self):
        super().draw()
        if self._pool_on:
            self._hide_unused()
            self._restack_if_needed()
            # sit above the world, grade and back weather laid down this frame
            try:
                self.c.tag_raise("creature")
            except Exception:
                pass

    def _restack_if_needed(self):
        """Pooled items keep their CREATION stacking. Within one primitive
        kind that matches draw order, but ACROSS kinds it only matches while
        the sequence of kinds drawn stays the same. When it changes (mouth
        opens, LOD adds detail, a crease appears) raise every drawn item in
        draw order once - so a polygon drawn after an oval really is on top
        of it. Steady frames pay nothing."""
        sig = "".join(self.__dict__.get("_seq", []))
        if sig == self.__dict__.get("_seq_last"):
            return
        self.__dict__["_seq_last"] = sig
        raise_ = getattr(self.c, "tag_raise", None)
        if raise_ is None:
            return
        for it in self.items:
            try:
                raise_(it)
            except Exception:
                pass
        self.__dict__["_restacks"] = self.__dict__.get("_restacks", 0) + 1


# ============================================================================
# Continuous limb skin  (removes the mechanical ball-joint look)
# ============================================================================
#
# Previously each limb was TWO polygons (upper + lower) plus an outlined
# circle sitting on the joint. That is exactly what reads as machinery: the
# two polys butt against each other at a hard angle leaving a notch on the
# inside of the bend, and the cap circle announces the pivot.
#
# `_chain_skin` instead walks the WHOLE chain (shoulder -> elbow -> wrist)
# as one closed outline. At each node the surface normal is the average of
# the incoming and outgoing segment normals - a mitre - so the skin turns
# through the joint continuously with no gap and no overlap. Width is
# carried along the chain and swelled slightly at the joint itself, which
# is what gives an elbow/knee its fat-and-tendon volume instead of a pinch.
#
# The bend also deforms the surface asymmetrically, the way a real limb
# does: the OUTSIDE of the joint stretches taut while the INSIDE bunches,
# so a hard bend produces a visible crease rather than a clean hinge.

def _chain_skin(nodes, widths, joint_swell=1.18, crease=0.34):
    """One continuous outline through a multi-segment limb.

    nodes  : [(x, y), ...] at least 2
    widths : half-width at each node
    """
    n = len(nodes)
    if n < 2:
        return []
    # per-node unit normals, mitred at interior joints
    norms = []
    for i in range(n):
        if i == 0:
            dx, dy = nodes[1][0] - nodes[0][0], nodes[1][1] - nodes[0][1]
            L = _cw_math.hypot(dx, dy) or 1e-6
            norms.append((-dy / L, dx / L))
        elif i == n - 1:
            dx, dy = nodes[-1][0] - nodes[-2][0], nodes[-1][1] - nodes[-2][1]
            L = _cw_math.hypot(dx, dy) or 1e-6
            norms.append((-dy / L, dx / L))
        else:
            ax, ay = nodes[i][0] - nodes[i - 1][0], nodes[i][1] - nodes[i - 1][1]
            bx, by = nodes[i + 1][0] - nodes[i][0], nodes[i + 1][1] - nodes[i][1]
            la = _cw_math.hypot(ax, ay) or 1e-6
            lb = _cw_math.hypot(bx, by) or 1e-6
            n1 = (-ay / la, ax / la)
            n2 = (-by / lb, bx / lb)
            mx, my = n1[0] + n2[0], n1[1] + n2[1]
            lm = _cw_math.hypot(mx, my)
            if lm < 1e-6:                      # folded back on itself
                norms.append(n1)
            else:
                norms.append((mx / lm, my / lm))

    # bend angle per interior node drives swell and the inside crease
    bend = [0.0] * n
    for i in range(1, n - 1):
        ax, ay = nodes[i][0] - nodes[i - 1][0], nodes[i][1] - nodes[i - 1][1]
        bx, by = nodes[i + 1][0] - nodes[i][0], nodes[i + 1][1] - nodes[i][1]
        a1 = _cw_math.atan2(ay, ax)
        a2 = _cw_math.atan2(by, bx)
        d = (a2 - a1 + _cw_math.pi) % _cw_math.tau - _cw_math.pi
        bend[i] = d

    left, right = [], []
    for i in range(n):
        px, py = nodes[i]
        nx, ny = norms[i]
        w = widths[i]
        if 0 < i < n - 1:
            b = abs(bend[i])
            w *= 1.0 + (joint_swell - 1.0) * min(1.0, b / 1.2)
            # outside stretches, inside bunches -> asymmetric joint volume
            sgn = 1.0 if bend[i] > 0 else -1.0
            wo = w * (1.0 + crease * min(1.0, b / 1.4))
            wi = w * (1.0 - crease * 0.55 * min(1.0, b / 1.4))
            wl = wo if sgn < 0 else wi
            wr = wi if sgn < 0 else wo
        else:
            wl = wr = w
        left.append((px + nx * wl, py + ny * wl))
        right.append((px - nx * wr, py - ny * wr))

    pts = []
    for (px, py) in left:
        pts += [px, py]
    for (px, py) in reversed(right):
        pts += [px, py]
    return pts


def _joint_crease(nodes, widths, i):
    """Short crease line on the INSIDE of a bent joint (elbow/knee fold)."""
    if i <= 0 or i >= len(nodes) - 1:
        return None
    ax, ay = nodes[i][0] - nodes[i - 1][0], nodes[i][1] - nodes[i - 1][1]
    bx, by = nodes[i + 1][0] - nodes[i][0], nodes[i + 1][1] - nodes[i][1]
    la = _cw_math.hypot(ax, ay) or 1e-6
    lb = _cw_math.hypot(bx, by) or 1e-6
    a1, a2 = _cw_math.atan2(ay, ax), _cw_math.atan2(by, bx)
    d = (a2 - a1 + _cw_math.pi) % _cw_math.tau - _cw_math.pi
    if abs(d) < 0.25:
        return None
    n1 = (-ay / la, ax / la)
    sgn = -1.0 if d > 0 else 1.0
    w = widths[i] * 0.72
    px, py = nodes[i]
    return (px + n1[0] * w * sgn, py + n1[1] * w * sgn,
            px + n1[0] * w * 0.35 * sgn, py + n1[1] * w * 0.35 * sgn), abs(d)


# ============================================================================
# TrippyGram tab removed (user request)
# ============================================================================
#
# The TRIPPYGRAM tab embedded the full original TrippyGram interface
# (browsers, selenium, Instagram posting, NFT generator, YouTube/SoundCloud
# panels). It is no longer built.
#
# Only the TAB is removed. TrippyGramEngine stays: the STUDIO tab and the
# brain's image pipeline (self.tg_engine) render through it, so pulling the
# engine would break STUDIO. The original tab builder is kept reachable as
# App._build_trippygram_tab_classic, and every other reference in m33 is
# already guarded by `self._tg_embedded is not None`, which now simply stays
# None - so shutdown, settings save and the studio all run unchanged.
#
# To bring the tab back, delete this block (or set
# App._build_trippygram_tab = App._build_trippygram_tab_classic).

App._build_trippygram_tab_classic = App._build_trippygram_tab


def _no_trippygram_tab(self):
    self._tg_embedded = None
    self._tg_tab_frame = None
    self._tg_holder = None
    self._tg_placeholder = None


App._build_trippygram_tab = _no_trippygram_tab


# ============================================================================
# Lighting / material model + anatomical surface detail
# ============================================================================
#
# One key light, up and to the left (the moon/sun sits upper-left in the
# stage). _KEY_LIGHT is the unit vector pointing TOWARD the light. Surfaces
# are shaded by how much their normal faces it (Lambert), the far side gets
# a cool sky rim (the sky is the second light source), and the overall
# contrast follows the world's real light level, which App syncs into
# creature._light_level twice a second from World.light() - so night
# flattens the shading and noon sharpens it.

_KEY_LIGHT = (-0.55, -0.835)
_SKY_RIM = "#a9c8ff"


def _chain_normals(nodes):
    n = len(nodes)
    out = []
    for i in range(n):
        if i == 0:
            a, c = nodes[0], nodes[1]
        elif i == n - 1:
            a, c = nodes[-2], nodes[-1]
        else:
            a, c = nodes[i - 1], nodes[i + 1]
        dx, dy = c[0] - a[0], c[1] - a[1]
        L = _cw_math.hypot(dx, dy) or 1e-6
        out.append((-dy / L, dx / L))
    return out


def _cr_limb_light(self, nodes, widths, base, lod, ruddy=True):
    """Diffuse key light, core shadow, sky rim and warm joints over a limb
    chain already drawn with _chain_skin. Every band is built INSIDE the
    silhouette (offset <= 0.45w, width <= 0.55w), so shading never spills
    past the skin edge."""
    lvl = getattr(self, "_light_level", 1.0)
    klx, kly = _KEY_LIGHT
    norms = _chain_normals(nodes)
    ks = [nx * klx + ny * kly for (nx, ny) in norms]
    kavg = sum(abs(k) for k in ks) / len(ks)
    sh_nodes, hi_nodes = [], []
    for (px, py), (nx, ny), k, w in zip(nodes, norms, ks, widths):
        off = 0.45 * w * k
        hi_nodes.append((px + nx * off, py + ny * off))
        sh_nodes.append((px - nx * off, py - ny * off))
    # core shadow on the far side, then the lit side over it
    self._poly(_chain_skin(sh_nodes, [w * 0.55 for w in widths], 1.0, 0.0),
               _shade(base, 1.0 - (0.08 + 0.12 * lvl) * min(1.0, kavg * 1.4)), "")
    self._poly(_chain_skin(hi_nodes, [w * 0.46 for w in widths], 1.0, 0.0),
               _shade(base, 1.0 + (0.04 + 0.11 * lvl) * min(1.0, kavg * 1.4)), "")
    if lod >= 1:
        # sky rim along the silhouette edge facing AWAY from the key
        sgn = -1.0 if sum(ks) >= 0 else 1.0
        rim = []
        for (px, py), (nx, ny), w in zip(nodes, norms, widths):
            rim += [px + nx * w * 0.9 * sgn, py + ny * w * 0.9 * sgn]
        self._line(*rim, fill=_mix_hex(base, _SKY_RIM, 0.12 + 0.22 * lvl),
                   width=1, smooth=True)
        # knees/elbows run warmer and ruddier than the shaft of the limb
        if ruddy and len(nodes) >= 3:
            jx, jy = nodes[2]
            jr = widths[2] * 0.55
            self._oval(jx - jr, jy - jr * 0.8, jx + jr, jy + jr * 0.8,
                       _mix_hex(base, "#c8645c", 0.14), "")


def _cr_eye_wrap(self, ex, ey, r, lod, head_color):
    """Eyelids wrap the eyeball: the upper lid casts a shadow band across
    the top of the globe, a crease sits above it, the cornea bulge catches
    a thin arc of light, and the lower lid line is moist."""
    if lod < 1:
        return
    self._arc(ex - r, ey - r, ex + r, ey + r, start=22, extent=136,
              style="arc", outline=_shade(head_color, 0.42), width=2)
    self._arc(ex - r * 1.12, ey - r * 1.65, ex + r * 1.12, ey + r * 0.55,
              start=28, extent=124, style="arc", outline=_shade(head_color, 0.70), width=1)
    self._arc(ex - r * 0.8, ey - r * 0.8, ex + r * 0.8, ey + r * 0.8,
              start=112, extent=52, style="arc", outline="#ffffff", width=1)
    if lod >= 2:
        self._arc(ex - r * 0.95, ey - r * 0.95, ex + r * 0.95, ey + r * 0.95,
                  start=205, extent=130, style="arc",
                  outline=_mix_hex(head_color, "#c77a78", 0.5), width=1)


_MOUTH_SHAPES = {
    #            cornerL cornerR  open  width
    "smile":       (2.0,   2.0,   0.6,  1.00),
    "big_smile":   (3.0,   3.0,   2.4,  1.08),
    "small_smile": (1.1,   1.1,   0.0,  0.95),
    "smirk":       (0.2,   2.2,   0.2,  0.96),
    "frown":      (-1.8,  -1.8,   0.0,  0.92),
    "o":          (-0.4,  -0.4,   4.2,  0.62),
    "small_o":    (-0.2,  -0.2,   2.6,  0.52),
    "wobble":     (-0.6,   0.6,   0.4,  0.90),
    "flat":        (0.0,   0.0,   0.0,  0.94),
}


def _cr_draw_mouth(self, hx, hy, head_color, lod, mouth_style, jaw_open, low):
    """Lips as volume that deforms. Each expression sets corner lift, opening
    and width; the cupid's bow, both lips, the cavity, teeth and tongue are
    all derived from that one mouth line, so a smile lifts the corners AND
    thins the upper lip AND stretches the lower one together."""
    lvl = getattr(self, "_light_level", 1.0)
    A = self._aff()
    sm, asym = A["smile"], A["asym"]
    cl = 2.8 * sm - 0.4 * asym
    cr = 2.8 * sm + 1.2 * asym * max(0.2, sm + 0.3)
    opn = 4.2 * A["open"]
    wsc = 0.94 + 0.10 * max(0.0, sm) - 0.42 * A["round"]
    talking = self.speaking > 0 and _cw_math.sin(self.t * 16) > 0
    opn += (2.2 if talking else 0.0) + jaw_open * 0.12
    mw = 8.6 * wsc
    my = hy + 9.6
    wob = _cw_math.sin(self.t * 9.0) * 0.6 * A["wobble"]
    line = [(hx - mw, my - cl), (hx - mw * 0.5, my - cl * 0.3 + wob), (hx, my),
            (hx + mw * 0.5, my - cr * 0.3 - wob), (hx + mw, my - cr)]
    f = (0.0, 0.8, 1.0, 0.8, 0.0)
    upper = [(x, y - opn * 0.5 * k) for (x, y), k in zip(line, f)]
    lower = [(x, y + opn * 0.5 * k) for (x, y), k in zip(line, f)]
    lip_c = _mix_hex(head_color, self.SHAPE.get("lip_col", "#b2545c"),
                     self.SHAPE.get("lip_amt", 0.45))
    full = self.SHAPE.get("lips", 1.0)

    def flat(pts):
        out = []
        for (x, y) in pts:
            out += [x, y]
        return out

    # cavity, teeth and tongue are ALWAYS emitted, collapsed to zero area
    # when shut: a stable draw sequence means the pooled items never need
    # restacking as the mouth opens and closes while talking
    cav = opn > 0.7
    self._poly(flat(upper + list(reversed(lower))) if cav else flat(line + list(reversed(line))),
               "#3a1216", "")
    dropt = min(1.6, opn * 0.4) if opn > 1.6 else 0.0
    self._poly(flat(upper + [(x, y + dropt) for (x, y) in reversed(upper)]), "#e8dcd0", "")
    tx, ty = lower[2]
    tr = mw * 0.35 if opn > 3.0 else 0.0
    self._oval(tx - tr, ty - (1.6 if tr else 0.0), tx + tr, ty + (0.2 if tr else 0.0),
               "#b04a4e", "")

    # upper lip: cupid's bow on top, the mouth line underneath
    bow = [(hx - mw, my - cl), (hx - mw * 0.55, my - 2.4 * full - cl * 0.3),
           (hx - 1.3, my - 2.9 * full), (hx, my - 2.3 * full), (hx + 1.3, my - 2.9 * full),
           (hx + mw * 0.55, my - 2.4 * full - cr * 0.3), (hx + mw, my - cr)]
    self._poly(flat(bow + list(reversed(upper))), _shade(lip_c, 0.88), "")
    # lower lip: fuller, carried by the lower mouth line
    bot = [(hx + mw * 0.8, lower[3][1] + 1.7 * full), (hx, lower[2][1] + 3.2 * full),
           (hx - mw * 0.8, lower[1][1] + 1.7 * full)]
    self._poly(flat(lower + bot), lip_c, "")

    self._line(*flat(line), fill=_shade(lip_c, 0.45), width=1, smooth=True)
    if not low and lod >= 1:
        # wet highlight on the lower lip, and the philtrum columns above
        hy2 = lower[2][1]
        self._oval(hx - 2.6, hy2 + 0.8, hx + 2.2, hy2 + 1.9,
                   _mix_hex(lip_c, "#ffffff", 0.18 + 0.18 * lvl), "")
        for sgn in (-1, 1):
            self._line(hx + sgn * 1.0, hy + 5.8, hx + sgn * 1.3, my - 2.9,
                       fill=_shade(head_color, 0.84), width=1)
    if lod >= 2:
        for (cx0, ch, w) in self._skin["lip_creases"]:
            x = hx + cx0 * 0.62 * wsc
            if abs(x - hx) > mw * 0.72:
                continue
            ly0 = lower[2][1] + 0.5
            self._line(x, ly0, x * 0.999 + hx * 0.001, ly0 + 1.3 + ch * 0.5,
                       fill=_shade(lip_c, 0.72), width=1)


def _cr_draw_hairline(self, hx, hy, head_color, lod):
    """Skin-to-hair transition: the hairline is not a hard edge. Fine short
    'baby' hairs thin out over the forehead and the temples darken where
    the hair starts, so the scalp fades into skin."""
    hl = self._skin.get("hairline")
    if hl is None:
        rnd = _cw_random.Random(len(self._skin["pores"]) * 7919 + 13)
        hl = []
        for i in range(28):
            t = i / 27.0
            x = -22 + t * 44 + rnd.uniform(-0.8, 0.8)
            y = -31.5 + abs(x) * 0.07 + rnd.uniform(-0.5, 0.5)
            hl.append((x, y, rnd.uniform(1.2, 3.0), rnd.uniform(-0.35, 0.35),
                       rnd.uniform(0.3, 1.0)))
        self._skin["hairline"] = hl
    hair_c = _shade(head_color, 0.42)
    for sgn in (-1, 1):                         # temple shading
        self._poly([hx + sgn * 24, hy - 30, hx + sgn * 31, hy - 26,
                    hx + sgn * 30, hy - 19, hx + sgn * 25, hy - 22],
                   _shade(head_color, 0.8), "")
    step = 1 if lod >= 2 else 3
    for (x, y, ln, ang, strength) in hl[::step]:
        self._line(hx + x, hy + y, hx + x + _cw_math.sin(ang) * ln,
                   hy + y + _cw_math.cos(ang) * ln,
                   fill=_mix_hex(head_color, hair_c, 0.35 + 0.45 * strength), width=1)
    if lod >= 2:                                 # temple veins
        for sgn in (-1, 1):
            self._line(hx + sgn * 25.5, hy - 19, hx + sgn * 27.0, hy - 15.5,
                       hx + sgn * 26.2, hy - 12.0, hx + sgn * 27.4, hy - 8.5,
                       fill=_mix_hex(head_color, "#5b6fae", 0.22), width=1, smooth=True)


def _cr_forearm_veins(self, elbow, wrist, limb_color, side, b):
    """Superficial veins on the forearm, close range only. Deterministic
    per side (no frame-to-frame wander): the path is a fixed sinusoid in
    limb-local space that rides the forearm as it moves."""
    ex, ey = elbow
    wx, wy = wrist
    dx, dy = wx - ex, wy - ey
    L = _cw_math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / L, dx / L
    ph = 0.7 if side == "L" else 2.1
    pts = []
    for i in range(6):
        t = 0.12 + i * 0.14
        o = _cw_math.sin(t * 7.0 + ph) * 1.1 * b
        pts += [ex + dx * t + nx * o, ey + dy * t + ny * o]
    self._line(*pts, fill=_mix_hex(limb_color, "#4f64a8", 0.22), width=1, smooth=True)


def _cr_draw_abdomen_ao(self, pelvis, pelvis_top, spine1, chest, arms, pw,
                        body_color, lod):
    """Abdominal wall landmarks and the occlusion where limbs meet trunk."""
    b = self.build
    # ambient occlusion: groin and armpits are where light cannot reach
    self._oval(pelvis[0] - 4.2 * b, pelvis[1] + 3.2 * b, pelvis[0] + 4.2 * b,
               pelvis[1] + 7.2 * b, _shade(body_color, 0.6), "")
    for sgn, key in ((-1, "L"), (1, "R")):
        sx, sy = arms[key][0]
        ax = sx - sgn * 3.4 * b
        self._oval(ax - 3.0 * b, sy + 2.5 * b, ax + 3.0 * b, sy + 8.5 * b,
                   _shade(body_color, 0.66), "")
    if lod < 1:
        return
    # linea alba down the midline, iliac crest over each hip
    nav = (pelvis_top[0] + (spine1[0] - pelvis_top[0]) * 0.3,
           pelvis_top[1] + (spine1[1] - pelvis_top[1]) * 0.3)
    self._line(spine1[0], spine1[1] + 2 * b, nav[0], nav[1] - 1.5 * b,
               fill=_shade(body_color, 0.84), width=1)
    for sgn in (-1, 1):
        self._line(pelvis[0] + sgn * pw * 0.52, pelvis[1] - 3 * b,
                   pelvis[0] + sgn * pw * 0.40, pelvis[1] + 0.5 * b,
                   pelvis[0] + sgn * pw * 0.22, pelvis[1] + 3.5 * b,
                   fill=_shade(body_color, 0.76), width=1, smooth=True)
    if lod >= 2:
        self._oval(nav[0] - 1.1 * b, nav[1] - 0.8 * b, nav[0] + 1.1 * b, nav[1] + 1.2 * b,
                   _shade(body_color, 0.58), "")


def _cr_draw_neck_detail(self, chest, neck, arms, head_color, body_color, lod):
    """Clavicles, sternocleidomastoid and the shadow under the jaw."""
    b = self.build
    # under-jaw occlusion; the head is drawn over its upper half
    self._oval(neck[0] - 7.5 * b, neck[1] - 3.0 * b, neck[0] + 7.5 * b, neck[1] + 2.4 * b,
               _shade(head_color, 0.6), "")
    if lod < 1:
        return
    for sgn, key in ((-1, "L"), (1, "R")):
        sx, sy = arms[key][0]
        # clavicle: an S-curve from the sternal notch out to the shoulder
        self._line(chest[0] + sgn * 1.4 * b, chest[1] + 0.6 * b,
                   chest[0] + sgn * 9.0 * b, chest[1] - 0.8 * b,
                   sx - sgn * 1.2 * b, sy - 1.0 * b,
                   fill=_shade(body_color, 0.8), width=1, smooth=True)
        self._line(chest[0] + sgn * 2.0 * b, chest[1] - 0.4 * b,
                   chest[0] + sgn * 9.0 * b, chest[1] - 1.8 * b,
                   fill=_shade(body_color, 1.08), width=1)
        # sternocleidomastoid: behind the ear down to the notch
        self._line(neck[0] + sgn * 5.0 * b, neck[1] + 0.5 * b,
                   chest[0] + sgn * 1.6 * b, chest[1] - 0.2 * b,
                   fill=_shade(head_color, 0.82), width=1)


Creature._limb_light = _cr_limb_light
Creature._eye_wrap = _cr_eye_wrap
Creature._draw_mouth = _cr_draw_mouth
Creature._draw_hairline = _cr_draw_hairline
Creature._forearm_veins = _cr_forearm_veins
Creature._draw_abdomen_ao = _cr_draw_abdomen_ao
Creature._draw_neck_detail = _cr_draw_neck_detail


# -- world light -> creature material contrast -------------------------------
_prev_app_init_light = App.__init__


def _app_init_with_light(self, *a, **kw):
    _prev_app_init_light(self, *a, **kw)

    def _sync():
        try:
            w = getattr(self, "world", None)
            cr = getattr(self, "creature", None)
            if w is not None and cr is not None:
                cr._light_level = 0.35 + 0.65 * clamp01(float(w.light()))
        except Exception:
            pass
        try:
            self.root.after(500, _sync)
        except Exception:
            pass

    _sync()


App.__init__ = _app_init_with_light


# ============================================================================
# Atmosphere: rain, splashes, puddles, fog, wind-blown leaves, lightning,
# dawn/dusk glow - drawn from WeatherSim state, fully pooled
# ============================================================================
#
# Every item here is allocated once and re-pointed per frame (the same
# pooling the creature uses), including the stippled ones - fog bands, the
# lightning flash and the night grade - because a stippled canvas item costs
# a pixmap on Windows, and recreating one per frame is what exhausted GDI.
#
# Motion is deterministic: a raindrop's position is a function of its index
# and the clock, not a random draw per frame, so there is no flicker and no
# per-frame allocation. World-anchored things (puddles, splashes, grass
# roots) go through the camera; screen-filling things (rain curtain, fog
# bands, flash) are laid out in screen space so they always cover the view.

class SceneGrade:
    """Colour grading in place of Tk stipple 'transparency'.

    Every item's ORIGINAL colour is pushed, per item, toward:
      * haze/fog with DISTANCE (atmospheric perspective: the higher above the
        ground line an item sits, the further away it is in this stage),
      * a warm horizon tint at sunrise/sunset on the distant layers,
      * a cool night/storm blue by darkness,
      * a brief blue-white lift during a lightning flash.
    All solid colours - no dither anywhere. Quantised so re-colouring only
    happens when the lighting actually moves."""

    def __init__(self, ground, h):
        self.ground, self.h = float(ground), float(h)
        self.dark = self.fog = self.warm = self.flash = 0.0
        self.light = 1.0
        self._memo = {}
        self._key = None

    def set(self, dark, fog, warm, flash, light):
        q = lambda v, s=0.03: round(clamp01(v) / s) * s
        self.dark, self.fog, self.warm = q(dark), q(fog), q(warm)
        self.flash, self.light = q(flash, 0.1), q(light, 0.05)
        k = (self.dark, self.fog, self.warm, self.flash, self.light)
        if k != self._key:
            self._key = k
            self._memo = {}

    def key(self):
        return self._key

    def depth(self, yc):
        return clamp01((self.ground - yc) / max(1.0, self.ground * 0.85))

    def color(self, c, yc):
        if not isinstance(c, str) or len(c) != 7 or not c.startswith("#"):
            return c
        mk = (c, int(yc) // 12)
        hit = self._memo.get(mk)
        if hit is not None:
            return hit
        d = self.depth(yc)
        x = c
        haze = _mix_hex("#5d6b7d", "#b3bfcc", self.light)
        amt = self.fog * (0.12 + 0.68 * d) + 0.08 * d * self.light
        if amt > 0.005:
            x = _mix_hex(x, haze, clamp01(amt))
        if self.warm > 0.005 and d > 0.2:
            x = _mix_hex(x, "#e8905e", self.warm * 0.38 * d)
        if self.dark > 0.005:
            x = _mix_hex(x, "#0b1426", self.dark * 0.6)
        if self.flash > 0.005:
            x = _mix_hex(x, "#dfe7ff", self.flash * 0.5 * (0.35 + 0.65 * d))
        self._memo[mk] = x
        return x


class _AtmoPool:
    KINDS = ("polygon", "oval", "line", "rectangle")

    def __init__(self, canvas):
        self.c = canvas
        self.pool = {k: [] for k in self.KINDS}
        self.cfg = {k: [] for k in self.KINDS}
        self.idx = {k: 0 for k in self.KINDS}
        self.last = {k: [] for k in self.KINDS}      # PERF: skip coords() when nothing moved

    def begin(self):
        for k in self.KINDS:
            self.idx[k] = 0

    def put(self, kind, coords, layer, **cfg):
        cfg["tags"] = layer
        cfg["state"] = "normal"
        sig = tuple(sorted(cfg.items()))
        i = self.idx[kind]
        pool, cache = self.pool[kind], self.cfg[kind]
        key = tuple(round(v * 4.0) for v in coords)
        last = self.last[kind]
        if i < len(pool):
            item = pool[i]
            try:
                if last[i] != key:
                    self.c.coords(item, *coords)
                    last[i] = key
                if cache[i] != sig:
                    self.c.itemconfig(item, **cfg)
                    cache[i] = sig
            except Exception:
                item = getattr(self.c, "create_" + kind)(*coords, **cfg)
                pool[i], cache[i], last[i] = item, sig, key
        else:
            item = getattr(self.c, "create_" + kind)(*coords, **cfg)
            pool.append(item)
            cache.append(sig)
            last.append(key)
        self.idx[kind] = i + 1
        return item

    def end(self):
        for k in self.KINDS:
            for j in range(self.idx[k], len(self.pool[k])):
                if self.cfg[k][j] != "hidden":
                    try:
                        self.c.itemconfig(self.pool[k][j], state="hidden")
                    except Exception:
                        pass
                    self.cfg[k][j] = "hidden"

    def count(self):
        return sum(self.idx.values())


class Atmosphere:
    def __init__(self, canvas, camera):
        self.c = canvas
        self.cam = camera
        self.pool = _AtmoPool(canvas)
        self.t = 0.0
        self._puddles = None
        self._puddle_key = None

    def _puddle_layout(self, w, ground):
        key = (int(w) // 40, int(ground))
        if key == self._puddle_key:
            return self._puddles
        rnd = _cw_random.Random(key[0] * 131 + key[1])
        out = []
        for i in range(6):
            x = (i + 0.5) * w / 6.0 + rnd.uniform(-w * 0.05, w * 0.05)
            out.append((x, ground + rnd.uniform(6, 24), rnd.uniform(14, 34), rnd.uniform(0, 6.28)))
        self._puddle_key, self._puddles = key, out
        return out

    def draw(self, dt, wx, w, h, ground, light, detail="high"):
        self.t += dt
        P, cam, t = self.pool, self.cam, self.t
        low = detail == "low"
        P.begin()
        precip = wx.get("precip", 0.0)
        wind = wx.get("wind", 0.0)
        wdir = wx.get("wind_dir", 1.0)
        fog = wx.get("fog", 0.0)
        wet = wx.get("ground_wet", 0.0)
        phase = wx.get("sun_phase", "day")
        gx0, gy = cam.world_to_screen(0, ground)
        z = cam.zoom

        # (dawn/dusk warmth, fog haze, night and lightning are applied as a
        # colour GRADE on every item - see SceneGrade - not as stippled
        # overlays, which render as a dot pattern on Windows)

        # --- puddles: world-anchored, grow with ground wetness ----------------
        if wet > 0.12:
            for (px, py, pr, ph) in self._puddle_layout(w, ground):
                r = pr * clamp01((wet - 0.12) * 1.6)
                if r < 2.0:
                    continue
                x0, y0 = cam.world_to_screen(px - r, py - r * 0.18)
                x1, y1 = cam.world_to_screen(px + r, py + r * 0.18)
                P.put("oval", [x0, y0, x1, y1], "atmo_back",
                      fill=_mix_hex("#1b2a3a", "#6f8fb0", 0.25 + 0.35 * light), outline="")
                # sky reflection: a lighter band across the upper half
                P.put("oval", [x0 + (x1 - x0) * 0.2, y0 + (y1 - y0) * 0.15,
                               x1 - (x1 - x0) * 0.25, y0 + (y1 - y0) * 0.5],
                      "atmo_back", fill=_mix_hex("#34506c", "#c9dcef", 0.2 + 0.5 * light),
                      outline="")
                if precip > 0.1 and not low:
                    for k in range(2):
                        u = ((t * (0.9 + precip) + ph + k * 0.5) % 1.0)
                        rr = r * (0.2 + 0.75 * u)
                        cx, cy = cam.world_to_screen(px + (k - 0.5) * r * 0.4, py)
                        P.put("oval", [cx - rr * z, cy - rr * 0.16 * z,
                                       cx + rr * z, cy + rr * 0.16 * z], "atmo_back",
                              fill="", outline=_mix_hex("#9fc4e8", "#1b2a3a", u), width=1)

        # --- wet ground sheen along the ground line -------------------------
        if wet > 0.25:
            P.put("line", [0, gy + 1, w, gy + 1], "atmo_back",
                  fill=_mix_hex("#3a4d5e", "#a9c8e8", clamp01(wet - 0.2) * light), width=2)

        # --- rain: two depth layers of deterministic streaks ------------------
        if precip > 0.03:
            n = int((30 if low else 70) * precip) + 4
            fall = 620.0 + 420.0 * precip
            slant = wind * wdir * 0.55
            ln = 9.0 + 16.0 * precip
            for i in range(n):
                back = i % 3 != 0
                sp = fall * (0.75 if back else 1.0)
                x = ((i * 97.13) % (w + 120)) - 60 + t * sp * slant
                y = ((i * 57.71) % (h + 80)) + t * sp
                x %= (w + 120)
                y %= (h + 80)
                x -= 60
                y -= 40
                if y > gy + 20 and back:
                    continue
                L = ln * (0.7 if back else 1.0)
                col = _mix_hex("#8aa3bd", "#dde8f4", 0.3 + 0.4 * light) if not back \
                    else _mix_hex("#51677e", "#9fb4c9", 0.3 + 0.3 * light)
                P.put("line", [x, y, x + slant * L, y + L], "atmo_back" if back else "atmo_front",
                      fill=col, width=1)
            # splashes where drops meet the ground
            for i in range(int((4 if low else 8) * precip)):
                u = ((t * 2.3 + i * 0.37) % 1.0)
                x = ((i * 131.7 + int(t * 2.3 + i * 0.37) * 53.3) % w)
                r = 2.0 + 5.0 * u
                P.put("line", [x - r, gy + 3 - r * 0.6 * (1 - u), x, gy + 3,
                               x + r, gy + 3 - r * 0.6 * (1 - u)], "atmo_front",
                      fill=_mix_hex("#c7d8ea", "#34485c", u), width=1)

        # --- wind-blown leaves ----------------------------------------------
        if wind > 0.28 and not low:
            n = int(4 + 14 * clamp01((wind - 0.28) / 0.6))
            for i in range(n):
                sp = (140 + 90 * ((i * 0.618) % 1.0)) * wind * wdir
                x = ((i * 211.3 + t * sp) % (w + 60)) - 30
                y = gy - 30 - ((i * 71.9) % (gy * 0.7)) + _cw_math.sin(t * 2.2 + i) * 18
                a = t * (3.0 + i % 5) + i
                s_ = 3.0 + (i % 3)
                pts = [x + _cw_math.cos(a) * s_, y + _cw_math.sin(a) * s_ * 0.5,
                       x + _cw_math.cos(a + 2.2) * s_ * 0.5, y + _cw_math.sin(a + 2.2) * s_ * 0.4,
                       x - _cw_math.cos(a) * s_, y - _cw_math.sin(a) * s_ * 0.5,
                       x + _cw_math.cos(a - 2.2) * s_ * 0.5, y + _cw_math.sin(a - 2.2) * s_ * 0.4]
                P.put("polygon", pts, "atmo_front",
                      fill=("#6b7f2e", "#8a6a2a", "#4f6b33", "#9a7b3c")[i % 4], outline="")

        # --- ground mist: soft, SOLID, low wisps (distance haze itself is in
        # the colour grade). Wavy smoothed tops so they read as vapour, kept
        # thin so they only veil the ground and the tree bases.
        if fog > 0.3:
            mist = _mix_hex("#5d6b7d", "#b9c4d0", 0.35 + 0.5 * light)
            layers = 1 if low else 2
            for k in range(layers):
                base = gy + 4 + k * 10
                hh = (10 + 16 * fog) * (1.0 - 0.35 * k)
                pts = [-20, base + 30]
                for i in range(13):
                    x = -20 + (w + 40) * i / 12.0
                    y = base - hh * (0.55 + 0.45 * _cw_math.sin(i * 1.3 + t * 0.12 + k * 2.1))
                    pts += [x, y]
                pts += [w + 20, base + 30]
                P.put("polygon", pts, "atmo_back" if k == 0 else "atmo_front",
                      fill=_mix_hex(mist, "#0b1426", 0.25 * k), outline="", smooth=True)

        # --- lightning ---------------------------------------------------------
        flash = wx.get("flash", 0.0)
        if flash > 0.05:
            if flash > 0.45:
                bx = wx.get("bolt_x", 0.5) * w
                rnd = _cw_random.Random(int(bx * 7.0))
                pts, x, y = [bx, 0.0], bx, 0.0
                while y < gy:
                    y += rnd.uniform(18, 42)
                    x += rnd.uniform(-22, 22)
                    pts += [x, min(y, gy)]
                P.put("line", pts, "atmo_front", fill="#f4f7ff", width=3)
                P.put("line", pts, "atmo_front", fill="#9fb8ff", width=1)
        P.end()
        return P.count()


def _cw_classify_sway(app, px):
    """After a world rebuild, find the trees and grass among the registered
    scenery items (by their geometry: trunks are 6-wide rectangles standing
    on the ground, canopies are ovals above a trunk, grass blades are short
    upward lines rooted at the ground) and give each a sway profile."""
    try:
        ground = float(app.world.ground)
    except Exception:
        return 0
    trunks, table = [], {}
    for item, ent in px._reg.items():
        mode, f, kind, tags = ent[0], ent[1], ent[2], ent[3]
        if item in px._hidden or "world" not in str(tags) or len(f) < 4:
            continue
        if kind == "rectangle" and abs((f[2] - f[0]) - 6.0) < 0.6 and abs(f[3] - ground) < 1.0:
            trunks.append(((f[0] + f[2]) * 0.5, ground - f[1]))
    for item, ent in px._reg.items():
        mode, f, kind, tags = ent[0], ent[1], ent[2], ent[3]
        if item in px._hidden or "world" not in str(tags) or len(f) < 4:
            continue
        if kind == "oval":
            cx, cy = (f[0] + f[2]) * 0.5, (f[1] + f[3]) * 0.5
            for tx, th in trunks:
                if abs(cx - tx) < 30 and ground - th - 40 < cy < ground - 30:
                    table[item] = (ground, th + 30.0, tx * 0.013, 2.4)
                    break
        elif kind == "line" and len(f) == 4:
            x0, y0, x1, y1 = f
            if -3 <= y0 - ground <= 19 and 4 <= y0 - y1 <= 14 and abs(x1 - x0) < 4:
                table[item] = (y0, y0 - y1, x0 * 0.05, 0.9)
    px.set_sway(table)
    return len(table)


# -- App._update_world, reworked -----------------------------------------------
App._update_world_classic = App._update_world


def _cw_update_world(self, dt):
    """Same job as the original (weather, cached static scene, ambient
    animation, night grade) plus camera re-projection, wind sway and the
    atmosphere layer - and with the night grade made PERSISTENT."""
    c = self.stage
    w = max(240, c.winfo_width())
    h = max(200, c.winfo_height())
    if w <= 1 or h <= 1:
        return
    now = time.time()
    sim = getattr(self, "weather_sim", None)
    if sim is not None:
        sim.update(dt)
        self.weather = sim.m19_weather()
        self._weather_next = now + 3600.0          # the simulation owns weather now
    elif now > self._weather_next:
        self._weather_next = now + random.uniform(150, 420)
        self.weather = random.choice(WEATHERS)
    daypart = day_part()
    detail = self.creature.detail if getattr(self, "creature", None) else "high"
    sig = (w // 8, h // 8, daypart, self.weather, detail)
    rebuilt = False
    if sig != self._world_sig:
        self._world_sig = sig
        self.world.rebuild(w, h, self.ground_y, daypart, self.weather, detail)
        self._sync_world_objects()
        rebuilt = True
    self.world.animate(dt)
    # terrain for foot contact: the world's ground surface (flat in this
    # world; the creature samples it per foot, so real slopes would work)
    cr = getattr(self, "creature", None)
    if cr is not None:
        g = float(getattr(self.world, "ground", self.ground_y))
        cr._terrain_fn = lambda x, g=g: g

    wx = sim.snapshot() if sim is not None else {"precip": 0.0, "wind": 0.15, "wind_dir": 1.0}
    px = getattr(self, "_world_proxy", None)
    if px is not None:
        if rebuilt:
            _cw_classify_sway(self, px)
            px.reproject(force=True)
        else:
            px.reproject()
        px.apply_sway(getattr(self, "_atmo_t", 0.0), wx.get("wind", 0.15),
                      sim.gust if sim is not None else 0.0, wx.get("wind_dir", 1.0))
    self._atmo_t = getattr(self, "_atmo_t", 0.0) + dt

    # night / storm / fog / dusk / lightning: a COLOUR GRADE on every item.
    # (The original drew a full-screen stippled rectangle for night, and so
    # did the previous version of this function - Tk stipple is a dot mask,
    # which is the screen-door pattern that covered the whole scene.)
    lit = self.world.light()
    old = getattr(self, "_grade_item", None)
    if old is not None:                       # retire the stippled grade for good
        try:
            c.delete(old)
        except Exception:
            pass
        self._grade_item = None
    sg = getattr(self, "_scene_grade", None)
    if sg is None or sg.ground != float(self.ground_y) or sg.h != float(h):
        sg = self._scene_grade = SceneGrade(self.ground_y, h)
    phase = wx.get("sun_phase", "day")
    warm = (1.0 - 0.7 * wx.get("cloud", 0.0)) if phase in ("sunrise", "sunset") else 0.0
    sg.set(dark=0.28 * (1.0 - lit) + 0.42 * wx.get("precip", 0.0) * wx.get("cloud", 0.0),
           fog=wx.get("fog", 0.0), warm=warm, flash=wx.get("flash", 0.0), light=lit)
    if px is not None:
        px._grade = sg
        px.regrade(force=rebuilt)
    cr = getattr(self, "creature", None)
    if cr is not None:
        cr.__dict__["_scene_grade"] = sg

    atmo = getattr(self, "_atmosphere", None)
    if atmo is None and getattr(self, "_camera", None) is not None:
        atmo = self._atmosphere = Atmosphere(c, self._camera)
    if atmo is not None:
        atmo.draw(dt, wx, w, h, self.ground_y, lit, detail)

    # stage layering, bottom -> top: world, world animation, grade, back
    # weather; the creature raises itself after drawing, the front weather
    # layer is raised just before the overlay card
    for tag in ("worlddyn", "grade", "atmo_back"):
        try:
            c.tag_raise(tag)
        except Exception:
            pass


App._update_world = _cw_update_world

_cw_orig_draw_overlay = App._draw_overlay


def _cw_draw_overlay(self):
    try:
        self.stage.tag_raise("atmo_front")
    except Exception:
        pass
    return _cw_orig_draw_overlay(self)


App._draw_overlay = _cw_draw_overlay


# ============================================================================
# Clothing, hair and weather posture
# ============================================================================
#
# Clothes are drawn INTO the body's draw sequence, not on top of the whole
# figure: trousers right after each leg's skin, shoes over each foot, the
# shirt over the torso, a sleeve over each arm, a collar/yoke over the
# collarbones - so z-order is anatomically right (a sleeve passes behind
# the far hand, the near shoe covers the near ankle).
#
# Every garment is built from the SAME skeleton nodes the skin uses, with
# the same mitred _chain_skin surface a few units wider, so cloth follows
# every bend the physics produces. Fabric is driven by one damped spring per
# creature (wind + body velocity): hems, cuffs and the hood edge trail it.
# Rain darkens and flattens cloth and hair; the outfit itself is chosen by
# the MIND (ThermalComfort) from temperature, wind and rain, with a hold time.

_OUTFIT_PALETTES = (
    # shirt,     trousers,  shoes,     jacket,    raincoat
    ("#c9d3dc", "#2f3b52", "#3a2a22", "#4a3b2f", "#d9b53a"),
    ("#7d9c7a", "#39342c", "#2b2320", "#39433a", "#c2493a"),
    ("#b89a74", "#26303a", "#4a3526", "#5a4232", "#2f6e8f"),
    ("#8c7aa6", "#2c2c34", "#1f1f24", "#3b3747", "#e0873a"),
    ("#d8cfc2", "#4a3f35", "#2e2622", "#33424f", "#7a9a3a"),
)
_HAIR_COLOURS = ("#2b1d14", "#4a3020", "#6b4a2b", "#a07a4a", "#c9a36a", "#e2c99a", "#1a1716")


def _cr_palette(self):
    pal = self.__dict__.get("_pal_cache")
    if pal is None:
        rnd = _cw_random.Random((self._skin.get("_seed") or len(self._skin["pores"])) * 7 + 3)
        pal = self.__dict__["_pal_cache"] = rnd.choice(_OUTFIT_PALETTES)
        self.__dict__["_hair_cache"] = rnd.choice(_HAIR_COLOURS)
    return pal


def _cr_body(self):
    return getattr(self, "_body", None) or {
        "outfit": "normal", "wet": 0.0, "cold": 0.0, "rain": 0.0, "wind": 0.15,
        "wind_dir": 1.0, "hunch": 0.0, "shiver": 0.0, "pace": 1.0, "flash": 0.0}


def _cr_cloth_step(self, dt):
    """One damped spring for all loose fabric and hair: wind pushes it one
    way, running pushes it back, it overshoots and settles."""
    bd = self._cloth_body()
    L = self._loco
    target = bd["wind"] * bd["wind_dir"] * (6.0 + 5.0 * _cw_math.sin(self.t * 2.7)) \
        - L.vx * 0.05
    v = self.__dict__.get("_cloth_v", 0.0)
    x = self.__dict__.get("_cloth_x", 0.0)
    v += ((target - x) * 38.0 - v * 7.5) * dt
    x += v * dt
    self.__dict__["_cloth_v"], self.__dict__["_cloth_x"] = v, clamp(x, -14.0, 14.0)


def _wet(col, wet):
    return _shade(col, 1.0 - 0.28 * clamp01(wet))


def _cr_draw_pants(self, side, hip, knee, ankle, b, lod, low, face):
    bd = self._cloth_body()
    pal = self._palette()
    col = _wet(pal[1], bd["wet"])
    if side == "L":
        col = _shade(col, 0.9)
    nodes = [hip, ((hip[0] + knee[0]) * 0.5, (hip[1] + knee[1]) * 0.5), knee,
             ((knee[0] + ankle[0]) * 0.5, (knee[1] + ankle[1]) * 0.5),
             (ankle[0], ankle[1] - 2.2 * b)]
    wid = [11.0 * b, 11.4 * b, 8.6 * b, 8.0 * b, 6.2 * b]
    self._poly(_chain_skin(nodes, wid, 1.08, 0.22), col, "", smooth=True)
    if low:
        return
    self._limb_light(nodes, wid, col, lod, ruddy=False)
    # knee folds bunch on the INSIDE of the bend, more with more bend
    cr = _joint_crease(nodes, wid, 2)
    (x0, y0, x1, y1), amt = cr or ((knee[0], knee[1], knee[0], knee[1]), 0.0)
    self._line(x0, y0, x1, y1, fill=_shade(col, 0.62), width=max(1, int(1 + amt)))
    self._line(x0, y0 + 2.4 * b, x1, y1 + 1.6 * b, fill=_shade(col, 0.7), width=1)
    # outer side seam
    ax, ay = hip[0] + face * 8.5 * b, hip[1]
    self._line(ax, ay, knee[0] + face * 6.8 * b, knee[1], ankle[0] + face * 5.2 * b,
               ankle[1] - 2 * b, fill=_shade(col, 0.78), width=1, smooth=True)
    # hem
    self._line(ankle[0] - 6.4 * b, ankle[1] - 2.2 * b, ankle[0] + 6.4 * b, ankle[1] - 2.2 * b,
               fill=_shade(col, 0.6), width=2)


def _cr_draw_shoe(self, side, ankle, b, lod, low, face):
    bd = self._cloth_body()
    pal = self._palette()
    col = _wet(pal[2], bd["wet"] * 0.6)
    fx, fy = ankle
    heel, toe = fx - face * 4.6 * b, fx + face * 13.0 * b
    # sock band showing between trouser hem and shoe collar
    self._poly([fx - 3.6 * b, fy - 2.4 * b, fx + 3.6 * b, fy - 2.4 * b,
                fx + 3.8 * b, fy - 0.6 * b, fx - 3.8 * b, fy - 0.6 * b],
               _shade("#d6d0c4", 0.9 - 0.25 * bd["wet"]), "")
    upper = [heel, fy - 1.4 * b, fx + face * 2.0 * b, fy - 2.2 * b,
             fx + face * 6.5 * b, fy + 0.6 * b, toe, fy + 3.2 * b,
             toe + face * 0.6 * b, fy + 5.6 * b, heel - face * 0.6 * b, fy + 5.6 * b]
    self._poly(upper, col, "")
    # sole
    self._poly([heel - face * 0.8 * b, fy + 5.2 * b, toe + face * 0.8 * b, fy + 5.2 * b,
                toe + face * 0.4 * b, fy + 7.0 * b, heel - face * 0.4 * b, fy + 7.0 * b],
               "#1b1a1a", "")
    if low:
        return
    # toe cap highlight and a wet sheen in rain
    tx = toe - face * 3.2 * b
    shine = 0.14 + 0.3 * bd["rain"]
    self._oval(min(tx, toe) - 0.4 * b, fy + 1.6 * b, max(tx, toe), fy + 3.6 * b,
               _mix_hex(col, "#ffffff", shine), "")
    if lod >= 1:
        for k in range(3):                     # laces
            lx = fx + face * (1.8 + k * 1.6) * b
            self._line(lx - 1.1 * b, fy - 1.2 * b + k * 0.8 * b,
                       lx + 1.1 * b, fy - 0.4 * b + k * 0.8 * b,
                       fill="#d9d4c8", width=1)


def _cr_draw_shirt(self, pelvis, pelvis_top, spine1, chest, arms, pw, b, lod, low):
    """Shirt body (or jacket / raincoat over it), with hem flutter."""
    bd = self._cloth_body()
    pal = self._palette()
    outfit = bd["outfit"]
    col = {"light": pal[0], "normal": pal[0], "warm": pal[3], "rain": pal[4]}[outfit]
    col = _wet(col, bd["wet"] * (0.25 if outfit == "rain" else 1.0))
    lsh, rsh = arms["L"][0], arms["R"][0]
    cx = self.__dict__.get("_cloth_x", 0.0)
    long_hem = outfit in ("warm", "rain")
    hem_y = pelvis[1] + (9.0 if long_hem else 2.0) * b
    flare = (4.0 if long_hem else 1.5) * b
    pts = [lsh[0] - 1.5 * b, lsh[1] - 1.0 * b,
           chest[0] - 6.0 * b, chest[1] - 1.2 * b,
           chest[0] + 6.0 * b, chest[1] - 1.2 * b,
           rsh[0] + 1.5 * b, rsh[1] - 1.0 * b,
           rsh[0] + 1.0 * b, rsh[1] + 9.0 * b,
           spine1[0] + pw * 0.62, spine1[1],
           pelvis[0] + pw * 0.6 + flare + cx * 0.6, hem_y,
           pelvis[0] + cx * 0.8, hem_y + 1.4 * b,
           pelvis[0] - pw * 0.6 - flare + cx * 0.6, hem_y,
           spine1[0] - pw * 0.62, spine1[1],
           lsh[0] - 1.0 * b, lsh[1] + 9.0 * b]
    self._poly(pts, col, "")
    if low:
        return
    self._limb_light([pelvis, pelvis_top, spine1, chest],
                     [pw * 0.62, pw * 0.56, pw * 0.64, pw * 0.8], col, lod, ruddy=False)
    # fabric folds: diagonal drag lines from the armpits toward the waist,
    # pulled by arm swing, plus soft bunching at the belt line
    for sgn, key in ((-1, "L"), (1, "R")):
        sx, sy = arms[key][0]
        self._line(sx - sgn * 2.0 * b, sy + 8.0 * b, spine1[0] + sgn * pw * 0.28,
                   spine1[1] + 4.0 * b, fill=_shade(col, 0.8), width=1, smooth=True)
    self._line(pelvis[0] - pw * 0.5, pelvis[1] - 1.5 * b, pelvis[0] + pw * 0.5,
               pelvis[1] - 1.0 * b, fill=_shade(col, 0.78), width=1)
    # placket / zip down the centre
    zip_col = "#b9b3a6" if outfit in ("warm", "rain") else _shade(col, 0.72)
    self._line(chest[0], chest[1] + 1.0 * b, spine1[0], spine1[1],
               pelvis[0] + cx * 0.6, hem_y - 1.0 * b, fill=zip_col,
               width=2 if outfit in ("warm", "rain") else 1)
    if lod >= 1:
        if outfit in ("light", "normal"):
            for k in range(3):             # buttons
                yy = chest[1] + (4.0 + k * 6.0) * b
                xx = chest[0] + (spine1[0] - chest[0]) * (k / 3.0)
                self._oval(xx - 0.8 * b, yy - 0.8 * b, xx + 0.8 * b, yy + 0.8 * b,
                           _shade(col, 0.6), "")
        # chest pocket with its seam
        px0, py0 = chest[0] - 9.0 * b, chest[1] + 4.0 * b
        self._poly([px0, py0, px0 + 6.0 * b, py0, px0 + 6.0 * b, py0 + 6.0 * b,
                    px0 + 3.0 * b, py0 + 7.0 * b, px0, py0 + 6.0 * b],
                   _shade(col, 0.93), "")
        self._line(px0, py0 + 1.2 * b, px0 + 6.0 * b, py0 + 1.2 * b,
                   fill=_shade(col, 0.7), width=1)
        # side seams
        for sgn in (-1, 1):
            self._line(spine1[0] + sgn * pw * 0.6, spine1[1] + 1 * b,
                       pelvis[0] + sgn * (pw * 0.6 + flare * 0.8), hem_y - 1 * b,
                       fill=_shade(col, 0.76), width=1)
    if outfit == "rain":
        # raincoat gloss: a long highlight down the lit side
        klx = _KEY_LIGHT[0]
        self._line(chest[0] + klx * 8 * b, chest[1] + 3 * b, spine1[0] + klx * 10 * b,
                   spine1[1] + 3 * b, pelvis[0] + klx * 11 * b, hem_y - 3 * b,
                   fill=_mix_hex(col, "#ffffff", 0.4), width=2, smooth=True)
    # waistband + belt (and the underwear band peeking above it when bent)
    pcol = _wet(self._palette()[1], bd["wet"])
    if not long_hem:
        self._poly([pelvis[0] - pw * 0.6, pelvis[1] + 1.0 * b, pelvis[0] + pw * 0.6,
                    pelvis[1] + 1.0 * b, pelvis[0] + pw * 0.6, pelvis[1] + 4.2 * b,
                    pelvis[0] - pw * 0.6, pelvis[1] + 4.2 * b], _shade(pcol, 0.8), "")
        lean = abs(self._loco.lean)
        uh = clamp01(lean * 3.0 + bd["hunch"] * 0.6) * 1.4 * b
        self._poly([pelvis[0] - pw * 0.5, pelvis[1] + 1.0 * b - uh, pelvis[0] + pw * 0.5,
                    pelvis[1] + 1.0 * b - uh, pelvis[0] + pw * 0.5, pelvis[1] + 1.0 * b,
                    pelvis[0] - pw * 0.5, pelvis[1] + 1.0 * b], "#e8e2d8", "")
        self._line(pelvis[0] - pw * 0.6, pelvis[1] + 2.6 * b, pelvis[0] + pw * 0.6,
                   pelvis[1] + 2.6 * b, fill="#1d1a18", width=2)
        if lod >= 1:
            for sgn in (-1, 1):            # trouser front pockets
                self._line(pelvis[0] + sgn * pw * 0.52, pelvis[1] + 4.2 * b,
                           pelvis[0] + sgn * pw * 0.36, pelvis[1] + 8.5 * b,
                           fill=_shade(pcol, 0.66), width=1, smooth=True)


def _cr_draw_sleeve(self, side, shoulder, elbow, wrist, b, lod, low):
    bd = self._cloth_body()
    pal = self._palette()
    outfit = bd["outfit"]
    col = {"light": pal[0], "normal": pal[0], "warm": pal[3], "rain": pal[4]}[outfit]
    col = _wet(col, bd["wet"] * (0.25 if outfit == "rain" else 1.0))
    if side == "L":
        col = _shade(col, 0.92)
    cx = self.__dict__.get("_cloth_x", 0.0)
    if outfit == "light":                       # t-shirt: short sleeve
        mid = (shoulder[0] + (elbow[0] - shoulder[0]) * 0.55,
               shoulder[1] + (elbow[1] - shoulder[1]) * 0.55)
        nodes, wid = [shoulder, mid], [8.6 * b, 7.6 * b]
    else:
        end = (wrist[0] + (elbow[0] - wrist[0]) * 0.08, wrist[1] + (elbow[1] - wrist[1]) * 0.08)
        nodes = [shoulder, ((shoulder[0] + elbow[0]) * 0.5, (shoulder[1] + elbow[1]) * 0.5),
                 elbow, ((elbow[0] + end[0]) * 0.5, (elbow[1] + end[1]) * 0.5), end]
        extra = 1.4 if outfit in ("warm", "rain") else 0.6
        wid = [(8.4 + extra) * b, (8.6 + extra) * b, (6.6 + extra) * b,
               (6.4 + extra) * b, (5.2 + extra) * b]
        # loose cuff trails the cloth spring a little
        nodes[-1] = (nodes[-1][0] + cx * 0.12, nodes[-1][1])
    self._poly(_chain_skin(nodes, wid, 1.06, 0.2), col, "", smooth=True)
    if low:
        return
    self._limb_light(nodes, wid, col, lod, ruddy=False)
    if len(nodes) >= 3:
        cr = _joint_crease(nodes, wid, 2)
        (x0, y0, x1, y1), amt = cr or ((elbow[0], elbow[1], elbow[0], elbow[1]), 0.0)
        self._line(x0, y0, x1, y1, fill=_shade(col, 0.64), width=max(1, int(1 + amt)))
    ex, ey = nodes[-1]
    self._line(ex - wid[-1] * 0.9, ey, ex + wid[-1] * 0.9, ey, fill=_shade(col, 0.66),
               width=2)


def _cr_draw_collar(self, chest, neck, arms, b, lod, low):
    """Yoke + collar over the shoulders, leaving a V (or crew) opening."""
    bd = self._cloth_body()
    pal = self._palette()
    outfit = bd["outfit"]
    col = {"light": pal[0], "normal": pal[0], "warm": pal[3], "rain": pal[4]}[outfit]
    col = _wet(col, bd["wet"] * (0.25 if outfit == "rain" else 1.0))
    lsh, rsh = arms["L"][0], arms["R"][0]
    depth = {"light": 3.0, "normal": 6.0, "warm": 1.5, "rain": 1.0}[outfit] * b
    nx, ny = neck[0], neck[1] + 7.0 * b
    self._poly([lsh[0] - 1.6 * b, lsh[1] - 1.2 * b, nx - 7.2 * b, ny - 2.0 * b,
                nx, ny + depth, nx + 7.2 * b, ny - 2.0 * b,
                rsh[0] + 1.6 * b, rsh[1] - 1.2 * b, rsh[0] + 1.0 * b, rsh[1] + 5.0 * b,
                chest[0], chest[1] + 5.0 * b, lsh[0] - 1.0 * b, lsh[1] + 5.0 * b],
               col, "")
    if low:
        return
    # collar band / raised collar for jackets
    up = (4.0 if outfit in ("warm", "rain") else 1.6) * b
    for sgn in (-1, 1):
        self._poly([nx + sgn * 7.2 * b, ny - 2.0 * b, nx + sgn * 7.6 * b, ny - 2.0 * b - up,
                    nx + sgn * 3.0 * b, ny - 1.0 * b - up * 0.6, nx, ny + depth],
                   _shade(col, 0.88), "")
    self._line(nx - 7.2 * b, ny - 2.0 * b, nx, ny + depth, nx + 7.2 * b, ny - 2.0 * b,
               fill=_shade(col, 0.6), width=1)


def _cr_hair_col(self):
    self._palette()
    return self.__dict__["_hair_cache"]


def _cr_draw_hair_volume(self, hx, hy, lod, low):
    """The mass of the hair: a swept-back cap over the crown that fills out
    the silhouette (strands alone read as a scalp). Moves with the cloth
    spring and sits flatter and darker when wet."""
    bd = self._cloth_body()
    hc = _wet(self._hair_col(), bd["wet"])
    cx = self.__dict__.get("_cloth_x", 0.0) * 0.35
    lift = (1.0 - 0.55 * bd["wet"]) * 4.0
    pts = []
    n = 12
    for i in range(n + 1):
        a = _cw_math.pi * (1.0 + i / n)            # left temple -> crown -> right
        rx, ry = 34.0 + (1.2 if i in (0, n) else 0.0), 20.0 + lift
        x = hx + _cw_math.cos(a) * rx + cx * (0.4 + 0.6 * _cw_math.sin(i / n * _cw_math.pi))
        y = hy - 20.0 + _cw_math.sin(a) * ry
        pts += [x, y]
    # swept-back front edge, a little higher at the centre (the hairline)
    pts += [hx + 26.0, hy - 25.0, hx + 12.0, hy - 30.5, hx, hy - 31.5,
            hx - 12.0, hy - 30.5, hx - 26.0, hy - 25.0]
    # underside first (the shadowed mass nearest the scalp), then the lit top
    self._poly(pts, _shade(hc, 0.72), "", smooth=True)
    top = []
    for i in range(0, len(pts) - 10, 2):
        top += [pts[i] + (hx - pts[i]) * 0.06, pts[i + 1] + 1.2]
    top += [hx + 22.0, hy - 27.0, hx, hy - 33.0, hx - 22.0, hy - 27.0]
    self._poly(top, hc, "", smooth=True)
    if not low:
        # sheen band where the key light catches the sweep
        klx = _KEY_LIGHT[0]
        self._line(hx + klx * 16.0, hy - 36.0 - lift * 0.4, hx + klx * 4.0, hy - 38.5 - lift * 0.5,
                   hx - klx * 10.0, hy - 37.0 - lift * 0.4,
                   fill=_mix_hex(hc, "#ffffff", 0.22 - 0.1 * bd["wet"]), width=2, smooth=True)


def _cr_draw_hood(self, hx, hy, lod, low):
    """Raincoat hood framing the face: a ring polygon (outer edge around the
    skull, inner edge along the face) so the face stays open."""
    bd = self._cloth_body()
    col = _wet(self._palette()[4], bd["wet"] * 0.25)
    cx = self.__dict__.get("_cloth_x", 0.0) * 0.5
    outer, inner = [], []
    for i in range(11):
        a = _cw_math.pi * (0.92 + 1.16 * i / 10.0)
        outer += [hx + _cw_math.cos(a) * 40.0 + cx * _cw_math.sin(i / 10 * _cw_math.pi),
                  hy - 8.0 + _cw_math.sin(a) * 36.0]
    for i in range(11):
        a = _cw_math.pi * (2.08 - 1.16 * i / 10.0)
        inner += [hx + _cw_math.cos(a) * 30.0, hy - 6.0 + _cw_math.sin(a) * 27.0]
    self._poly(outer + inner, col, "", smooth=True)
    if not low:
        self._line(*inner, fill=_shade(col, 0.62), width=2, smooth=True)
        self._line(*outer[4:14], fill=_mix_hex(col, "#ffffff", 0.35), width=1, smooth=True)


Creature._palette = _cr_palette
Creature._cloth_body = _cr_body
Creature._cloth_step = _cr_cloth_step
Creature._draw_pants = _cr_draw_pants
Creature._draw_shoe = _cr_draw_shoe
Creature._draw_shirt = _cr_draw_shirt
Creature._draw_sleeve = _cr_draw_sleeve
Creature._draw_collar = _cr_draw_collar
Creature._hair_col = _cr_hair_col
Creature._draw_hair_volume = _cr_draw_hair_volume
Creature._draw_hood = _cr_draw_hood


# ============================================================================
# Continuous expression on the body
# ============================================================================
#
# The creature used to read ONE label: skin colour came from
# EMOTION_COLORS[label] (so an 'affectionate' creature turned pink, and every
# label flip recoloured the whole body in one frame), the face picked a
# discrete eye/mouth style from FACE[label], and bob/tilt/head height jumped
# between hard-coded values. Now the mind's continuous ExpressionLayer
# arrives as creature._affect, is smoothed again here (a second guarantee
# against snapping), and every visible channel is a continuous function of
# it. Skin is a stable, seeded, human-range tone; emotion shows only as
# physiology - a flush in warmth/anger, pallor in fear.

_AFF_DEFAULT = {"smile": 0.08, "open": 0.0, "round": 0.0, "wobble": 0.0, "asym": 0.0,
                "brow_in": 0.0, "knit": 0.0, "brow_out": 0.0, "eye": 1.0, "gaze": 0.0, "shoulder": 0.0,
                "chest": 0.0, "tilt": 0.0, "energy": 1.0, "flush": 0.0, "pallor": 0.0,
                "tension": 0.0, "breath": 1.3}
_SKIN_TONES = ("#f1d3bf", "#e8bea0", "#dcaa86", "#c98f68", "#b0774f", "#8f5a3a", "#6f4430")
_IRIS_TONES = ("#5a3b22", "#3f2a1a", "#6b7d4a", "#4f7a9a", "#7d8f9e", "#8a6a34", "#3d5f4d")


def _cr_aff(self):
    return self.__dict__.get("_aff_s") or _AFF_DEFAULT


def _cr_affect_step(self, dt):
    target = getattr(self, "_affect", None) or _AFF_DEFAULT
    cur = self.__dict__.setdefault("_aff_s", dict(_AFF_DEFAULT))
    k = 1.0 - _cw_math.exp(-dt / 0.45)
    for key, v in target.items():
        cur[key] = cur.get(key, v) + (v - cur.get(key, v)) * k
    A = cur
    moving = self.behavior in ("move", "curious")
    # accumulated phases: changing a RATE never jumps the position of a cycle
    bob_rate = (6.0 if moving else 2.0) * (0.75 + 0.3 * A["energy"]) + \
        (1.0 if self.speaking > 0 else 0.0)
    self.__dict__["_bob_ph"] = self.__dict__.get("_bob_ph", 0.0) + dt * bob_rate
    self.__dict__["_breath_ph"] = self.__dict__.get("_breath_ph", 0.0) + dt * 1.6 * A["breath"]
    tilt_t = 8.0 * clamp01(A["tilt"] + (0.5 if self.behavior == "curious" else 0.0))
    ts = self.__dict__.get("_tilt_s", 0.0)
    self.__dict__["_tilt_s"] = ts + (tilt_t - ts) * (1.0 - _cw_math.exp(-dt / 0.8))


def _cr_skin_tone(self):
    if self.SHAPE.get("skin"):
        self.__dict__.setdefault("_iris_cache", self.SHAPE.get("iris_col", "#5a3b22"))
        return self.SHAPE["skin"]
    tone = self.__dict__.get("_tone_cache")
    if tone is None:
        rnd = _cw_random.Random((self._skin.get("_seed") or 1) * 31 + 7)
        tone = _mix_hex(rnd.choice(_SKIN_TONES), self.identity_tint, 0.08)
        self.__dict__["_tone_cache"] = tone
        self.__dict__["_iris_cache"] = rnd.choice(_IRIS_TONES)
    return tone


def _cr_iris(self):
    self._skin_tone()
    return self.__dict__["_iris_cache"]


def _cr_draw_eye(self, ex, ey, side, lod, low, head_color):
    """Sclera, iris clipped by the lids, pupil that dilates with arousal,
    a wet highlight, a lid that rides the openness, lower lid, crease.
    Every piece is always emitted (zero-size when shut) so blinking never
    changes the pooled draw sequence."""
    A = self._aff()
    now = _cw_time.time()
    blink = 0.0
    if now < self.blink_until:
        ph = 1.0 - (self.blink_until - now) / 0.15
        blink = _cw_math.sin(_cw_math.pi * clamp01(ph))
    o = clamp(A["eye"], 0.35, 1.45) * (1.0 - blink)
    self.__dict__["_eye_o"] = o
    es = self.SHAPE.get("eye_scale", 1.0)
    rx = 7.0 * es
    ry = max(0.3, 5.4 * o * es)
    self._oval(ex - rx, ey - ry, ex + rx, ey + ry, "#eee8df", "")
    # iris + limbal ring, clipped to the lid opening; gaze + lowered gaze
    ir = 3.7 * es * self.SHAPE.get("iris", 1.0)
    irv = min(ir, ry)
    lx = ex + self.look_x * 0.9
    ly = ey + self.look_y * 0.7 + 2.0 * A["gaze"]
    ly = clamp(ly, ey - max(0.0, ry - irv), ey + max(0.0, ry - irv))
    iris = self._iris()
    self._oval(lx - ir, ly - irv, lx + ir, ly + irv, iris, _shade(iris, 0.5))
    pr = 1.45 * (1.0 + 0.25 * clamp01(A["eye"] - 1.0) + 0.15 * A["tension"])
    prv = min(pr, max(0.2, ry * 0.85))
    self._oval(lx - pr, ly - prv, lx + pr, ly + prv, "#0c0908", "")
    hs = 0.9 if ry > 1.2 else 0.0             # wet highlight (zero-size when shut)
    klx, kly = _KEY_LIGHT
    hx0, hy0 = lx + klx * 1.6, ly + kly * 1.7
    self._oval(hx0 - hs, hy0 - hs, hx0 + hs, hy0 + hs, "#ffffff", "")
    # upper lid edge (lashes attach here) and the shadow it casts
    self._line(ex - rx - 0.6, ey - ry * 0.15, ex - rx * 0.45, ey - ry - 0.5,
               ex + rx * 0.45, ey - ry - 0.5, ex + rx + 0.6, ey - ry * 0.15,
               fill="#2a1d18", width=2, smooth=True)
    self._line(ex - rx * 0.8, ey - ry * 0.55, ex, ey - ry * 0.8, ex + rx * 0.8, ey - ry * 0.55,
               fill=_mix_hex("#eee8df", "#6d5a52", 0.55), width=1, smooth=True)
    self._line(ex - rx * 0.9, ey + ry * 0.55, ex, ey + ry + 0.4, ex + rx * 0.9, ey + ry * 0.55,
               fill=_shade(head_color, 0.72), width=1, smooth=True)
    self._line(ex - rx, ey - ry - 2.3, ex, ey - ry - 3.2 - (1.2 - o) * 0.8, ex + rx,
               ey - ry - 2.3, fill=_shade(head_color, 0.74), width=1, smooth=True)
    if lod >= 2:                               # iris fibres, radial
        for i in range(8):
            a = i * (_cw_math.tau / 8.0)
            self._line(lx + _cw_math.cos(a) * pr, ly + _cw_math.sin(a) * min(pr, irv),
                       lx + _cw_math.cos(a) * ir * 0.95, ly + _cw_math.sin(a) * irv * 0.95,
                       fill=_shade(iris, 0.72), width=1)


def _cr_draw_brow(self, hx, hy, side, head_color):
    """Brow as a shaped band following inner/outer displacement: sadness
    lifts the inner end, anger drives it down, surprise lifts both,
    curiosity lifts one side more than the other."""
    A = self._aff()
    # worry lifts the inner ends; anger/frustration pulls them down AND in
    din = -6.5 * A["brow_in"] + 5.0 * A["knit"]
    dout = -4.8 * A["brow_out"] + 1.2 * A["knit"]
    if side > 0:
        din -= 1.8 * A["asym"]
        dout -= 1.4 * A["asym"]
    self.__dict__.setdefault("_brow", {})[side] = (din, dout)
    col = self.SHAPE.get("brow_col") or _shade(self._hair_col(), 0.9)
    ix, ox = hx + side * (6.5 - 2.2 * A["knit"]), hx + side * 23.0
    self._line(ix, hy - 19.0 + din, hx + side * 14.0, hy - 21.2 + (din + dout) * 0.5,
               ox, hy - 19.4 + dout - 1.6 * self.SHAPE.get("brow_arch", 0.0),
               fill=col, width=self.SHAPE.get("brow_w", 3), smooth=True)


Creature._aff = _cr_aff
Creature._affect_step = _cr_affect_step
Creature._skin_tone = _cr_skin_tone
Creature._iris = _cr_iris
Creature._draw_eye = _cr_draw_eye
Creature._draw_brow = _cr_draw_brow

_cr_prev_cloth_step = Creature._cloth_step


def _cr_cloth_and_affect(self, dt):
    _cr_prev_cloth_step(self, dt)
    self._affect_step(dt)


Creature._cloth_step = _cr_cloth_and_affect



# ============================================================================
# Hands
# ============================================================================
#
# Proportions from real hands, in units of the palm length P:
#   palm P long, ~0.95P wide at the knuckles, narrowing to the wrist;
#   finger lengths  index 0.94P, middle 1.0P, ring 0.93P, little 0.74P;
#   phalanges       proximal 0.45, middle 0.30, distal 0.25 of each finger;
#   knuckle line slightly arched (middle knuckle furthest from the wrist);
#   thumb rises from the base of the palm, ~50 deg off the finger axis,
#   metacarpal + two phalanges, thicker and shorter.
# Each finger is ONE _chain_skin surface through MCP -> PIP -> DIP -> tip,
# so the skin wraps the joints instead of butting segments together. Curl
# grows toward the tip (flexion is strongest at the middle joints) and is
# driven by expression tension and grip, so the hands follow the body.

_FINGERS = ((0.94, -1.5), (1.0, -0.5), (0.93, 0.5), (0.74, 1.5))   # (length, slot)


def _hand_chain(base, ang, length, curl, bend, width):
    """Nodes + widths for one finger. `bend` (+1/-1) = which side flexes."""
    segs = (0.45, 0.30, 0.25)
    flex = (0.55, 1.0, 0.75)                 # PIP flexes most, then DIP, then MCP
    nodes, x, y, a = [base], base[0], base[1], ang
    for sl, fx in zip(segs, flex):
        a += bend * curl * fx
        x += _cw_math.cos(a) * length * sl
        y += _cw_math.sin(a) * length * sl
        nodes.append((x, y))
    widths = [width, width * 0.92, width * 0.8, width * 0.62]
    return nodes, widths


def _cr_draw_hand(self, side, elbow, wrist, b, lod, low, face, skin, A):
    fa = _cw_math.atan2(wrist[1] - elbow[1], wrist[0] - elbow[0])
    perp = fa + _cw_math.pi / 2
    cp, sp = _cw_math.cos(perp), _cw_math.sin(perp)
    P = 0.4 * self._H()                        # palm length: 0.4 head heights
    # tension closes the hand, a smile relaxes it, walking gives a light grip
    curl = clamp(0.28 + 0.55 * A["tension"] - 0.08 * clamp01(A["smile"])
                 + min(0.2, self._loco.speed / 450.0), 0.1, 1.05)
    flexd = 0.12 * face * (0.5 + A["tension"])   # wrist flexes slightly with grip
    ha = fa + flexd
    ch, sh = _cw_math.cos(ha), _cw_math.sin(ha)
    wx, wy = wrist
    kx, ky = wx + ch * P, wy + sh * P           # knuckle-line centre
    half = 0.48 * P
    # palm: heel at the wrist (continuous with the forearm), widening to the
    # knuckle arch; the thumb side is fuller (thenar eminence)
    th = -face                                  # thumb on the body-front side
    palm = [wx + cp * 0.34 * P, wy + sp * 0.34 * P,
            wx + ch * 0.45 * P + cp * (0.52 * P) * (1 if th > 0 else 0.9),
            wy + sh * 0.45 * P + sp * (0.52 * P) * (1 if th > 0 else 0.9),
            kx + cp * half, ky + sp * half,
            kx + ch * 0.1 * P, ky + sh * 0.1 * P,
            kx - cp * half, ky - sp * half,
            wx + ch * 0.45 * P - cp * (0.52 * P) * (1 if th < 0 else 0.9),
            wy + sh * 0.45 * P - sp * (0.52 * P) * (1 if th < 0 else 0.9),
            wx - cp * 0.34 * P, wy - sp * 0.34 * P]
    self._poly(palm, _shade(skin, 0.95), "", smooth=True)
    klx, kly = _KEY_LIGHT
    for fi, (flen, slot) in enumerate(_FINGERS):
        off = slot * 0.31 * P
        arch = (1.0 - abs(slot) / 1.5) * 0.12 * P      # middle knuckle sits furthest out
        base = (kx + cp * off + ch * arch - ch * 0.12 * P,
                ky + sp * off + sh * arch - sh * 0.12 * P)
        spread = slot * 0.05 * (1.0 - curl)             # fingers fan when relaxed
        nodes, wid = _hand_chain(base, ha + spread, flen * P * 1.05, curl, face,
                                 0.155 * P * (0.9 if fi == 3 else 1.0))
        tone = _shade(skin, 0.93 - 0.03 * fi)
        self._poly(_chain_skin(nodes, wid, 1.12, 0.25), tone, "", smooth=True)
        if lod >= 1:
            # knuckle highlight on the back of the hand, nail near the tip
            mx, my = nodes[0]
            self._oval(mx - 0.5 * b, my - 0.5 * b, mx + 0.5 * b, my + 0.5 * b,
                       _mix_hex(tone, "#ffffff", 0.12), "")
            (x2, y2), (x3, y3) = nodes[2], nodes[3]
            nx, ny = x2 + (x3 - x2) * 0.62, y2 + (y3 - y2) * 0.62
            nr = wid[3] * 0.8
            self._oval(nx - nr, ny - nr, nx + nr, ny + nr, _mix_hex(tone, "#f3dcd2", 0.55), "")
        if lod >= 2:
            for j in (1, 2):                            # joint creases
                cr = _joint_crease(nodes, wid, j) or ((nodes[j][0], nodes[j][1],
                                                        nodes[j][0], nodes[j][1]), 0.0)
                (x0, y0, x1, y1), _amt = cr
                self._line(x0, y0, x1, y1, fill=_shade(tone, 0.7), width=1)
            self._oval(nx - nr * 0.45, ny - nr * 0.45 + nr * 0.3, nx + nr * 0.45,
                       ny + nr * 0.1 + nr * 0.3, _mix_hex(tone, "#fbf1ea", 0.75), "")
    # thumb: from the base of the palm on the front side, ~50 deg off axis
    tbase = (wx + ch * 0.28 * P + cp * th * 0.40 * P, wy + sh * 0.28 * P + sp * th * 0.40 * P)
    tang = ha + th * 0.85 - face * 0.25 * curl
    tn, tw = _hand_chain(tbase, tang, 0.95 * P, curl * 0.7, face, 0.2 * P)
    self._poly(_chain_skin(tn, tw, 1.12, 0.25), _shade(skin, 0.9), "", smooth=True)
    if lod >= 1:
        (x2, y2), (x3, y3) = tn[2], tn[3]
        nx, ny = x2 + (x3 - x2) * 0.6, y2 + (y3 - y2) * 0.6
        nr = tw[3] * 0.85
        self._oval(nx - nr, ny - nr, nx + nr, ny + nr, _mix_hex(skin, "#f3dcd2", 0.55), "")


Creature._draw_hand = _cr_draw_hand



def _cr_rot_begin(self, cx, cy, ang):
    """Rotate every primitive drawn until _rot_end() about (cx, cy)."""
    ca, sa = _cw_math.cos(ang), _cw_math.sin(ang)
    self.__dict__["_rot_saved"] = (self._poly, self._oval, self._line, self._arc)
    op, oo, ol, oa = self.__dict__["_rot_saved"]

    def R(x, y):
        dx, dy = x - cx, y - cy
        return cx + dx * ca - dy * sa, cy + dx * sa + dy * ca

    def flat(pts):
        out = []
        for i in range(0, len(pts) - 1, 2):
            out.extend(R(pts[i], pts[i + 1]))
        return out

    def _poly(pts, fill, outline="#0a0c10", smooth=False):
        return op(flat(pts), fill, outline, smooth)

    def _oval(x0, y0, x1, y1, fill, outline="#0a0c10"):
        mx, my = R((x0 + x1) * 0.5, (y0 + y1) * 0.5)
        hw, hh = (x1 - x0) * 0.5, (y1 - y0) * 0.5
        return oo(mx - hw, my - hh, mx + hw, my + hh, fill, outline)

    def _line(*coords, **kw):
        return ol(*flat(coords), **kw)

    def _arc(x0, y0, x1, y1, **kw):
        mx, my = R((x0 + x1) * 0.5, (y0 + y1) * 0.5)
        hw, hh = (x1 - x0) * 0.5, (y1 - y0) * 0.5
        return oa(mx - hw, my - hh, mx + hw, my + hh, **kw)

    self._poly, self._oval, self._line, self._arc = _poly, _oval, _line, _arc


def _cr_rot_end(self):
    saved = self.__dict__.pop("_rot_saved", None)
    if saved:
        self._poly, self._oval, self._line, self._arc = saved


Creature._rot_begin = _cr_rot_begin
Creature._rot_end = _cr_rot_end


# neutral body shape; m38 installs Jane's
Creature.SHAPE = {"hip": 0.58, "waist": 0.44, "rib": 0.72, "hip_span": 1.0, "shoulder": 1.0,
                  "sway": 0.0, "jaw": 1.0, "nose": 1.0, "stride": 1.0, "hood": True}
Creature._draw_hair_back = lambda self, *a, **k: None
Creature._draw_makeup = lambda self, *a, **k: None

Creature._heel = lambda self: (0.0, 0.0)



def _cr_damp_joint(self, key, root, joint, length, tau=0.035):
    """Ease a mid-joint's DIRECTION from its root over ~tau seconds, then put
    it back at exactly `length` from the root (bone length stays exact).
    Removes one-frame knee/elbow snaps (e.g. a planted leg straightening as
    the body turns over it) without visible lag. Advances once per update
    tick, so extra _pose() calls in the same frame don't compound it."""
    fid = self.__dict__.get("_fid", 0)
    st = self.__dict__.setdefault("_joint_s", {})
    rel = (joint[0] - root[0], joint[1] - root[1])
    ent = st.get(key)
    if ent is None:
        st[key] = [fid, rel, rel]
        return joint
    if ent[0] != fid:                       # new tick: last result becomes the base
        ent[0], ent[1] = fid, ent[2]
    base = ent[1]
    a = 1.0 - _cw_math.exp(-self.__dict__.get("_fdt", 1 / 60.0) / tau)
    rx, ry = base[0] + (rel[0] - base[0]) * a, base[1] + (rel[1] - base[1]) * a
    n = _cw_math.hypot(rx, ry) or 1e-6
    rx, ry = rx / n * length, ry / n * length
    ent[2] = (rx, ry)
    return (root[0] + rx, root[1] + ry)


Creature._damp_joint = _cr_damp_joint



# -- one anatomical unit for skeleton, skin, clothes and head ------------------
def _cr_H(self):
    """Head height in px. The whole body is built from it (8-head adult)."""
    return 30.0 * self.build * self.SHAPE.get("scale", 1.0)


def _cr_leg_len(self):
    k = 1.0 + (self.limb_ratio - 1.0) * 0.4
    H = self._H()
    return 2.05 * H * k * self.SHAPE.get("legs", 1.0), 1.87 * H * k * self.SHAPE.get("legs", 1.0)


def _cr_arm_len(self):
    k = 1.0 + (self.limb_ratio - 1.0) * 0.4
    H = self._H()
    return 1.45 * H * k, 1.25 * H * k


def _cr_leg_wid(self):
    """Half-widths hip->mid-thigh->knee->mid-calf->ankle, in H."""
    H, t = self._H(), self.SHAPE.get("thigh", 1.0)
    return [0.40 * H * t, 0.43 * H * t, 0.2 * H, 0.23 * H, 0.1 * H]


def _cr_arm_wid(self):
    H = self._H()
    return [0.17 * H, 0.16 * H, 0.11 * H, 0.12 * H, 0.075 * H]


Creature._H = _cr_H
Creature._leg_len = _cr_leg_len
Creature._arm_len = _cr_arm_len
Creature._leg_wid = _cr_leg_wid
Creature._arm_wid = _cr_arm_wid



# -- terrain ----------------------------------------------------------------
def _cr_terrain_at(self, x):
    """World ground height at x. The app installs _terrain_fn from the world;
    without one (bare/test creature) fall back to the old stage relation."""
    fn = getattr(self, "_terrain_fn", None)
    if fn is not None:
        try:
            return float(fn(x))
        except Exception:
            pass
    return self.y + 85.0 * self.build + self._sole()


def _cr_slope_at(self, x):
    d = 0.2 * self._H()
    return _cw_math.atan2(self._terrain_at(x + d) - self._terrain_at(x - d), 2.0 * d)


def _cr_sole(self):
    """Ankle-to-sole height of the foot geometry (6.2 foot units)."""
    return 6.2 * self._H() / 17.5


Creature._terrain_at = _cr_terrain_at
Creature._slope_at = _cr_slope_at
Creature._sole = _cr_sole



def _cr_far(self, side):
    """Shade for the limb on the far side of the body (seen side-on)."""
    far = "L" if self._loco.facing >= 0 else "R"
    return 0.84 if side == far else 1.0


def _cr_depth_order(self):
    return ("L", "R") if self._loco.facing >= 0 else ("R", "L")


Creature._far = _cr_far
Creature._depth_order = _cr_depth_order
