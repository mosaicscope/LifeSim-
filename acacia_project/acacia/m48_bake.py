# ============================================================================
# [NEW] BAKED WORLD  (performance + visual quality; vector fallback)
# ============================================================================
#
# Profiling the live app showed the frame is dominated by Tk redrawing ~800
# static world polygons every time the follow camera moves. They don't
# change between rebuilds, so they are rasterised ONCE into a single image
# (supersampled 2x -> anti-aliased, which Tk vector items never are), with
# procedural texture, soft contact shadows and a rolling foreground bank
# added during the bake, then shown as one canvas image item. The vector
# items are hidden (they stay in the registry: nothing else changes).
#
#   * rebake only on world rebuild (region/daypart/weather class/resize)
#     or zoom change - never per frame;
#   * lighting (night, fog, dusk warmth) is applied to the cached image with
#     numpy using exactly SceneGrade's per-height formula, only when the
#     quantised grade actually moves (lightning flashes stay vector-only);
#   * wind: tree canopies and a third of the grass stay live vector items
#     (they sway); the rest of the grass is baked at rest;
#   * the per-frame blob clouds become a few soft, blurred cloud sprites
#     with parallax (one canvas item each).
# If PIL/numpy are unavailable, or anything fails, the vector world is used
# exactly as before.

import math as _bk_math
import random as _bk_random
import time as _bk_time

_BK_OK = bool(HAS_PIL and HAS_NUMPY)
_BK_SS = 2                                     # supersampling factor


def _bk_photo(img):
    return ImageTk.PhotoImage(img)


def _bk_rgb(c):
    try:
        return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
    except Exception:
        return None


def _bk_mid(a, b):
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)


def _bk_quad(p0, c, p1, n=6):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0], u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1]))
    return out


def _bk_smooth(pts, closed):
    """Tk's smooth=True spline, reproduced so the bake matches the vectors."""
    n = len(pts)
    if n < 3:
        return pts
    if closed:
        out = [_bk_mid(pts[-1], pts[0])]
        for i in range(n):
            out += _bk_quad(out[-1], pts[i], _bk_mid(pts[i], pts[(i + 1) % n]))
        return out
    out = [pts[0]]
    for i in range(1, n - 1):
        end = pts[i + 1] if i == n - 2 else _bk_mid(pts[i], pts[i + 1])
        out += _bk_quad(out[-1], pts[i], end)
    return out


def _bk_draw(d, ent, s):
    kind, flat, fill, outline, opt = ent[2], ent[1], ent[4], ent[5], ent[7] if len(ent) > 7 else {}
    c = [v * s for v in flat]
    width = max(1, int(round(float(opt.get("width", 1) or 1) * s)))
    fill = fill if isinstance(fill, str) and fill.startswith("#") else None
    outline = outline if isinstance(outline, str) and outline.startswith("#") else None
    if kind == "polygon":
        pts = list(zip(c[0::2], c[1::2]))
        if len(pts) < 3:
            return
        if opt.get("smooth"):
            pts = _bk_smooth(pts, True)
        d.polygon(pts, fill=fill, outline=outline)
    elif kind == "line":
        pts = list(zip(c[0::2], c[1::2]))
        if len(pts) < 2 or not fill:
            return
        if opt.get("smooth"):
            pts = _bk_smooth(pts, False)
        d.line(pts, fill=fill, width=width, joint="curve")
    elif kind in ("oval", "rectangle", "arc") and len(c) >= 4:
        x0, y0, x1, y1 = c[:4]
        box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
        if box[2] - box[0] < 0.5 or box[3] - box[1] < 0.5:
            return
        if kind == "oval":
            d.ellipse(box, fill=fill, outline=outline)
        elif kind == "rectangle":
            d.rectangle(box, fill=fill, outline=outline)
        else:
            st = float(opt.get("start", 0))
            ex = float(opt.get("extent", 90))
            d.arc(box, -st - ex, -st, fill=outline or fill, width=width)


class _BakedWorld:
    def __init__(self):
        self.item = None
        self.photo = None
        self.base = None               # float32 HxWx3, ungraded
        self.depth = None              # per-row depth (H,)
        self.zoom = None
        self.sig = None
        self.grade_key = None
        self.size = None
        self.clouds = []
        self.cloud_cache = {}


def _bk_state(app):
    st = getattr(app, "_bk", None)
    if st is None:
        st = app._bk = _BakedWorld()
    return st


def _bk_static_items(px, real):
    """Static world items: tagged world, not dynamic, not recycled-free."""
    out = []
    for item, ent in px._reg.items():
        tags = ent[3]
        tg = " ".join(tags) if isinstance(tags, (list, tuple)) else str(tags)
        if "worlddyn" in tg or "world" not in tg or item in px._hidden:
            continue
        out.append((item, ent))
    return out


def _bk_prepare(app):
    """MAIN thread, fast: snapshot what to bake (no Tk calls after this)."""
    px = app._world_proxy
    real = app.stage
    cam = app._camera
    w = app.world
    statics = _bk_static_items(px, real)
    sway = px._sway
    live = set()
    for idx, (item, ent) in enumerate(statics):
        if item in sway and (ent[2] != "line" or idx % 3 == 0):
            live.add(item)                               # canopies + a third of the grass keep swaying
    ents = [(item, [ent[0], list(ent[1]), ent[2], ent[3], ent[4], ent[5], ent[6], dict(ent[7]) if len(ent) > 7 else {}])
            for item, ent in statics if item not in live]
    Hd = int(getattr(w, "h", real.winfo_height()) or real.winfo_height())
    return {"ents": ents, "live": live, "z": cam.zoom, "Wd": int(w.w), "Hd": Hd, "G": w.ground,
            "seed": hash((getattr(w, "_region_name", "valley"), int(w.w))) & 0xffffffff}


def _bk_compute(job):
    """Worker thread: rasterise + texture + shadows. PIL/numpy only."""
    z, Wd, Hd, G = job["z"], job["Wd"], job["Hd"], job["G"]
    ss = max(1.0, min(float(_BK_SS), (2.4e6 / max(1.0, Wd * z * Hd * z)) ** 0.5))
    s = z * ss
    Wi, Hi = max(4, int(Wd * s)), max(4, int(Hd * s))
    img = Image.new("RGB", (Wi, Hi), "#0b1018")
    d = ImageDraw.Draw(img)
    shadows = []
    for item, ent in job["ents"]:
        _bk_draw(d, ent, s)
        if ent[2] in ("polygon", "oval", "rectangle") and ent[1]:
            xs, ys = ent[1][0::2], ent[1][1::2]
            if xs and ys:
                wdt = max(xs) - min(xs)
                if G - 6 <= max(ys) <= G + 14 and 8 < wdt < 420 and max(ys) - min(ys) > 6:
                    shadows.append(((min(xs) + max(xs)) / 2, max(ys), wdt))
    arr = np.asarray(img, dtype=np.float32).copy()
    del img, d
    rng = np.random.default_rng(job["seed"])
    if shadows:                                          # soft contact shadows / AO at object bases
        sh = Image.new("L", (Wi, Hi), 0)
        sd = ImageDraw.Draw(sh)
        for (cx, by, wdt) in shadows:
            rx, ry = wdt * 0.55 * s, max(3.0, wdt * 0.09) * s
            sd.ellipse([cx * s - rx, by * s - ry * 0.6, cx * s + rx, by * s + ry], fill=110)
        sh = sh.filter(ImageFilter.GaussianBlur(radius=max(2, int(5 * s))))
        m = np.asarray(sh, dtype=np.float32)
        m *= 0.55 / 255.0
        arr *= (1.0 - m)[..., None]
        del m, sh
    # painterly grain everywhere, turf on the ground - noise kept as 8-bit
    # images and applied in column chunks, so wide real-scale regions don't
    # need several full-size float buffers at once
    lo = np.asarray(Image.fromarray((rng.random((max(2, Hi // 24), max(2, Wi // 24))) * 255).astype(np.uint8))
                    .resize((Wi, Hi), Image.BICUBIC))
    hi = np.asarray(Image.fromarray((rng.random((max(2, Hi // 4), max(2, Wi // 4))) * 255).astype(np.uint8))
                    .resize((Wi, Hi), Image.BILINEAR))
    ground = ((np.arange(Hi, dtype=np.float32) / s) > G - 2).astype(np.float32)[:, None]
    a_lo = 0.035 + 0.09 * ground
    a_hi = 0.015 + 0.07 * ground
    top = G + (Hd - G) * 0.58
    r0 = max(0, int((top - 14) * s))
    c_bank = np.array(_bk_rgb("#2f5a2c"), dtype=np.float32)
    c_rim = np.array(_bk_rgb("#6d9a52"), dtype=np.float32)
    CH = 1024
    for c0 in range(0, Wi, CH):
        c1 = min(Wi, c0 + CH)
        n1 = lo[:, c0:c1].astype(np.float32) / 255.0 - 0.5
        n2 = hi[:, c0:c1].astype(np.float32) / 255.0 - 0.5
        arr[:, c0:c1] *= (1.0 + a_lo * n1 + a_hi * n2)[..., None]
        if r0 < Hi - 2:                                # rolling foreground bank: elevation below the walk line
            xw = np.arange(c0, c1, dtype=np.float32) / s
            edge = top + 6 * np.sin(xw / 83.0) + 4 * np.sin(xw / 37.0 + 1.3) + 2.5 * np.sin(xw / 13.0)
            yy = (np.arange(r0, Hi, dtype=np.float32) / s)[:, None]
            rel = yy - edge[None, :]
            mask = np.clip(rel / 3.0, 0.0, 1.0)
            below = np.clip(rel / max(8.0, Hd - top), 0.0, 1.0)
            rim = np.clip(1.0 - np.abs(rel - 1.5) / 2.0, 0.0, 1.0)
            bank = c_bank[None, None, :] * ((1.0 - 0.45 * below) * (1.0 + 0.12 * n1[r0:] + 0.08 * n2[r0:]))[..., None]
            bank += (c_rim - bank) * rim[..., None]
            sub = arr[r0:, c0:c1]
            sub += (bank - sub) * mask[..., None]
    del lo, hi
    gy0 = int((G + 2) * s)
    if gy0 < Hi - 2:
        n = int(Wi * (Hi - gy0) / (60.0 * ss))
        ys = rng.integers(gy0, Hi - 3, n)
        xs = rng.integers(0, Wi - 1, n)
        ln = rng.integers(2, 4 + int(ss * 2), n)
        tone = np.where(rng.random(n) < 0.6, 0.78, 1.18).astype(np.float32)
        for y0, x0, l, t in zip(ys, xs, ln, tone):
            arr[max(0, y0 - l):y0, x0] *= t
    np.clip(arr, 0, 255, out=arr)
    small = Image.fromarray(arr.astype(np.uint8)).resize((max(2, int(Wd * z)), max(2, int(Hd * z))), Image.LANCZOS)
    base = np.asarray(small, dtype=np.uint8).copy()          # kept 8-bit; float only while grading
    rows = np.arange(base.shape[0], dtype=np.float32) / z
    depth = np.clip((G - rows) / max(1.0, G * 0.85), 0.0, 1.0)
    return base, depth, small.size


def _bk_finish(app, job, result):
    """MAIN thread: swap the vector world for the finished image."""
    px = app._world_proxy
    real = app.stage
    st = _bk_state(app)
    st.base, st.depth, st.size = result
    st.zoom = job["z"]
    st.grade_key = None
    sway = px._sway
    baked = set()
    for item, _ent in job["ents"]:
        if item in px._reg and item not in px._hidden:   # still exists (not deleted/recycled)
            baked.add(item)
            try:
                real.itemconfig(item, state="hidden")
            except Exception:
                pass
    object.__setattr__(px, "_baked", baked)
    for item in baked:
        sway.pop(item, None)                             # baked grass no longer animates invisibly
    for item in job["live"]:
        try:
            real.addtag_withtag("livesway", item)
        except Exception:
            pass
    _bk_regrade(app, force=True)
    if st.item is not None:
        real.itemconfig(st.item, state="normal")


def _bk_bake(app, background=False):
    """Snapshot on the main thread; rasterise on a worker (background=True)
    or inline. The vector world stays visible until the image is ready."""
    st = _bk_state(app)
    st.gen = getattr(st, "gen", 0) + 1
    # until the new image is ready, the correct picture is the vector world
    px = app._world_proxy
    for item in list(getattr(px, "_baked", ()) or ()):
        if item in px._reg and item not in px._hidden:      # never resurrect recycled (deleted) items
            try:
                app.stage.itemconfig(item, state="normal")
            except Exception:
                pass
    object.__setattr__(px, "_baked", set())
    if st.item is not None:
        try:
            app.stage.itemconfig(st.item, state="hidden")
        except Exception:
            pass
    job = _bk_prepare(app)
    job["gen"] = st.gen
    if not background:
        _bk_finish(app, job, _bk_compute(job))
        return

    def work():
        try:
            res = _bk_compute(job)
        except Exception:
            traceback.print_exc()
            res = None
        st.ready = (job, res)

    st.ready = None
    import threading as _bk_thr
    _bk_thr.Thread(target=work, daemon=True).start()


def _bk_regrade(app, force=False):
    """SceneGrade's per-height colour model, applied to the whole image at once."""
    st = _bk_state(app)
    if st.base is None:
        return
    g = getattr(app, "_scene_grade", None)
    q = lambda v: round(v / 0.06) * 0.06
    key = (q(g.dark), q(g.fog), q(g.warm), q(g.light)) if g is not None else (0, 0, 0, 1)
    if not force and key == st.grade_key:
        return
    st.grade_key = key
    dark, fog, warm, light = key
    x = st.base.astype(np.float32)
    dcol = st.depth[:, None, None]
    haze = np.array(_bk_rgb(_mix_hex("#5d6b7d", "#b3bfcc", clamp01(light))), dtype=np.float32)
    amt = np.clip(fog * (0.12 + 0.68 * dcol) + 0.08 * dcol * light, 0.0, 1.0)
    x += (haze - x) * amt
    if warm > 0.005:
        t = warm * 0.38 * dcol * (dcol > 0.2)
        x += (np.array(_bk_rgb("#e8905e"), dtype=np.float32) - x) * t
    if dark > 0.005:
        x += (np.array(_bk_rgb("#0b1426"), dtype=np.float32) - x) * (dark * 0.6)
    img = Image.fromarray(np.clip(x, 0, 255).astype(np.uint8))
    real = app.stage
    try:
        if st.photo is not None and getattr(st, "_psize", None) == img.size and hasattr(st.photo, "paste"):
            st.photo.paste(img)
        else:
            st.photo = _bk_photo(img)
            st._psize = img.size
            if st.item is None:
                st.item = real.create_image(0, 0, image=st.photo, anchor="nw", tags=("worldimg",))
            else:
                real.itemconfig(st.item, image=st.photo)
    except Exception:
        traceback.print_exc()
    _bk_place(app, force=True)


def _bk_place(app, force=False):
    st = _bk_state(app)
    if st.item is None:
        return
    cam = app._camera
    sig = (round(cam.pos[0], 2), round(cam.pos[1], 2), round(cam.zoom, 4))
    if force or sig != getattr(st, "_place_sig", None):
        st._place_sig = sig
        x0, y0 = cam.world_to_screen(0.0, 0.0)
        app.stage.coords(st.item, x0, y0)
    real = app.stage
    real.tag_lower("worldimg")
    try:
        real.tag_raise("livesway", "worldimg")                     # canopies/grass above the image
    except Exception:
        pass


# ---- soft clouds -------------------------------------------------------------
def _bk_cloud_sprite(st, shape, col, dark):
    key = (shape, col)
    img = st.cloud_cache.get(key)
    if img is not None:
        return img
    r = _bk_random.Random(shape * 7919)
    Wc, Hc = 340, 130
    a = Image.new("L", (Wc, Hc), 0)
    d = ImageDraw.Draw(a)
    for _ in range(9):
        cx = r.uniform(60, Wc - 60)
        cy = r.uniform(55, 80)
        rr = r.uniform(26, 48)
        d.ellipse([cx - rr * 1.3, cy - rr, cx + rr * 1.3, cy + rr * 0.7], fill=255)
    d.rectangle([40, 78, Wc - 40, 96], fill=255)
    a = a.filter(ImageFilter.GaussianBlur(9))
    top = np.array(_bk_rgb(col), dtype=np.float32)
    bot = top * (0.72 - 0.2 * dark)
    grad = np.linspace(0.0, 1.0, Hc, dtype=np.float32)[:, None, None]
    rgb = top * (1 - grad) + bot * grad
    rgb = np.broadcast_to(rgb, (Hc, Wc, 3)).astype(np.uint8)
    alpha = (np.asarray(a, dtype=np.float32) * 0.82).astype(np.uint8)
    img = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
    photo = _bk_photo(img)
    st.cloud_cache[key] = photo
    if len(st.cloud_cache) > 40:
        st.cloud_cache.pop(next(iter(st.cloud_cache)))
    return photo


def _bk_clouds(app, dt):
    st = _bk_state(app)
    w, cam, real = app.world, app._camera, app.stage
    wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
    cover = clamp01(wx.get("cloud", 0.3))
    n = int(round(1 + 4 * cover)) if w.daypart != "night" or cover > 0.5 else 1
    lit = w.light()
    storm = wx.get("state") in ("storm", "rain")
    base = _mix_hex("#f4f6fa", "#8a94a6", 0.55 if storm else 0.1)
    col = _mix_hex(base, "#1a2233", clamp01(0.75 - 0.75 * lit))
    col = _mix_hex(col, "#f2b48a", 0.25 * clamp01(getattr(getattr(app, "_scene_grade", None), "warm", 0.0)))
    col = _mix_hex(col, col, 0)                                     # quantise via hex
    q = lambda c_: "#%02x%02x%02x" % tuple((v // 12) * 12 for v in _bk_rgb(c_))
    col = q(col)
    while len(st.clouds) < n:
        k = len(st.clouds)
        st.clouds.append({"x": _bk_random.uniform(0, 1), "y": 0.03 + 0.06 * (k % 3), "shape": k, "item": None,
                          "par": 0.25 + 0.1 * (k % 3), "spd": 0.004 + 0.002 * (k % 2)})
    vw = real.winfo_width() or 900
    wind = wx.get("wind", 0.3) * (1 if wx.get("wind_dir", 1) >= 0 else -1)
    for k, cl in enumerate(st.clouds):
        if k >= n:
            if cl["item"] is not None and not cl.get("off"):
                real.itemconfig(cl["item"], state="hidden")
                cl["off"] = True
            continue
        if cl.get("off") and cl["item"] is not None:
            real.itemconfig(cl["item"], state="normal")
            cl["off"] = False
        cl["x"] = (cl["x"] + dt * cl["spd"] * (0.4 + wind)) % 1.4
        photo = _bk_cloud_sprite(st, cl["shape"], col, 1 - lit)
        sx = (cl["x"] - 0.2) * vw * 1.2 - (cam.pos[0] - w.w / 2) * cam.zoom * cl["par"]
        sy = w.ground * cl["y"] * cam.zoom
        if cl["item"] is None:
            cl["item"] = real.create_image(sx, sy, image=photo, anchor="nw", tags=("cloudspr",))
            cl["img"] = photo
        else:
            if cl.get("img") is not photo:
                real.itemconfig(cl["item"], image=photo, state="normal")
                cl["img"] = photo
            real.coords(cl["item"], sx, sy)
    try:
        real.tag_raise("cloudspr", "worldimg")
    except Exception:
        pass


# ---- the ambient layer without the blob clouds or duplicate rain -------------
_bk_prev_animate = World.animate


def _bk_animate(self, dt):
    if not getattr(self, "_bk_active", False):
        return _bk_prev_animate(self, dt)
    self.t += dt
    self.clear_dyn()
    if self.w <= 0:
        return
    pool = self.poi("water")
    if pool is not None and getattr(self, "_region_kind", "valley") != "settlement":
        for k in range(3):
            ph = _bk_math.sin(self.t * 1.4 + k * 2.1)
            ww = 26 - k * 7
            yy = pool.y - 4 + k * 4 + ph * 1.2
            self._add(self.c.create_line(pool.x - ww + ph * 5, yy, pool.x + ww + ph * 5, yy,
                                         fill=_mix_hex("#8fd9ff", "#1d3f5c", 0.45 + 0.2 * k),
                                         width=1, tags="worlddyn"), dyn=True)
    curio = self.poi("curio")
    if curio is not None:
        pulse = 0.5 + 0.5 * _bk_math.sin(self.t * 2.0)
        rr = 12 + pulse * 6
        self._add(self.c.create_oval(curio.x - rr, curio.y - 16 - rr, curio.x + rr, curio.y - 16 + rr,
                                     outline=_mix_hex("#7ee0c8", "#101520", 0.65 - 0.3 * pulse),
                                     tags="worlddyn"), dyn=True)
    for pi in self.pois:
        if pi.kind in ("food", "water") and not pi.available():
            self._add(self.c.create_oval(pi.x - 30, pi.y - 26, pi.x + 30, pi.y + 14, fill="#0a0d12",
                                         outline="", stipple="gray50", tags="worlddyn"), dyn=True)
    if self.daypart == "night" and self.weather == "clear":
        if self._star is None and _bk_random.random() < 0.0006:
            self._star = {"x0": _bk_random.uniform(0, self.w * 0.6), "y0": _bk_random.uniform(10, 60),
                          "t0": self.t, "fresh": True}
        if self._star is not None:
            age = self.t - self._star["t0"]
            if age < 0.6:
                sx = self._star["x0"] + age * 260
                sy = self._star["y0"] + age * 130
                self._add(self.c.create_line(sx, sy, sx - 26, sy - 13, fill="#eaf4ff", width=2,
                                             tags="worlddyn"), dyn=True)
            else:
                self._star = None
    self.c.tag_lower("worlddyn")
    self.c.tag_lower("world")


World.animate = _bk_animate

# rebuilds invalidate the bake
_bk_prev_rebuild = World.rebuild


def _bk_rebuild(self, *a, **k):
    px = self.c if hasattr(self.c, "_reg") else None
    if px is not None:
        object.__setattr__(px, "_baked", set())            # the old world's items are gone
    r = _bk_prev_rebuild(self, *a, **k)
    self._bk_dirty = True
    return r


World.rebuild = _bk_rebuild

_bk_prev_update = App._update_world


def _bk_update(self, dt):
    _bk_prev_update(self, dt)
    if not _BK_OK or getattr(self, "_bk_disabled", False):
        return
    try:
        w = self.world
        cam = getattr(self, "_camera", None)
        px = getattr(self, "_world_proxy", None)
        if cam is None or px is None or not getattr(px, "_reg", None):
            return
        st = _bk_state(self)
        now = _bk_time.time()
        zoom_moved = st.zoom is not None and abs(cam.zoom - st.zoom) / max(1e-3, st.zoom) > 0.02
        if zoom_moved:
            st._zoom_t = st.__dict__.get("_zoom_t") or now
        ready = getattr(st, "ready", None)
        if ready is not None:
            st.ready = None
            job, res = ready
            if res is not None and job["gen"] == st.gen:
                _bk_finish(self, job, res)
                w._bk_active = True
        if getattr(w, "_bk_dirty", False) or (zoom_moved and now - st._zoom_t > 0.25):
            w._bk_dirty = False
            st._zoom_t = None
            _bk_bake(self, background=not getattr(self, "_bk_sync", False))
        elif st.base is not None:
            _bk_regrade(self)
        _bk_place(self)
        _bk_clouds(self, dt)
    except Exception:
        traceback.print_exc()
        self._bk_disabled = True                       # safe fallback: the vector world
        px = getattr(self, "_world_proxy", None)
        for item in getattr(px, "_baked", ()) or ():
            try:
                self.stage.itemconfig(item, state="normal")
            except Exception:
                pass
        if px is not None:
            object.__setattr__(px, "_baked", set())
        self.world._bk_active = False


App._update_world = _bk_update
