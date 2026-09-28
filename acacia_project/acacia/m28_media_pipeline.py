
# ═══ END NFT HD UPGRADE PATCH ═══

def auto_scramble(img, strength=0.5):
    """
    Mild block-shuffle scramble — keeps the image recognisable.
    strength 0..1 controls how many blocks get swapped (0.5 = moderate).
    """
    img = img.convert('RGB')
    w, h  = img.size
    bsize = _ri(48, 96)          # block size in px
    cols  = w // bsize
    rows  = h // bsize
    if cols < 2 or rows < 2:
        return img
    # build list of block coords
    blocks = [(c, r) for c in range(cols) for r in range(rows)]
    n_swaps = max(1, int(len(blocks) * strength * 0.25))   # gentle
    out = img.copy()
    for _ in range(n_swaps):
        (c1,r1),(c2,r2) = random.sample(blocks, 2)
        x1,y1 = c1*bsize, r1*bsize
        x2,y2 = c2*bsize, r2*bsize
        b1 = img.crop((x1,y1,x1+bsize,y1+bsize))
        b2 = img.crop((x2,y2,x2+bsize,y2+bsize))
        out.paste(b2,(x1,y1)); out.paste(b1,(x2,y2))
    return out


def generate_trippy(src, out, intensity=3,
                    effect_mode='🎲 Randomizer', scramble=False, scramble_strength=0.5,
                    extra_effects=None):
    """extra_effects: optional list of (name, fn) tuples appended after the main pipeline."""
    img = Image.open(src).convert('RGB')
    s   = min(img.width, img.height)
    img = img.crop(((img.width-s)//2, (img.height-s)//2,
                    (img.width+s)//2, (img.height+s)//2))
    img = img.resize((1080,1080), Image.LANCZOS)

    # ── optional scramble before effects ────────────────────────────────────
    if scramble:
        img = auto_scramble(img, scramble_strength)

    # ── choose which effects to apply ────────────────────────────────────────
    applied = []
    if effect_mode == '🎲 Randomizer':
        lo, hi = INTENSITY_FX.get(intensity, (2,4))
        chosen = random.sample(EFFECTS, min(_ri(lo, hi), len(EFFECTS)))
    else:
        # single named effect — still apply intensity times for a richer look
        fn = EFFECT_MAP.get(effect_mode)
        chosen = [(effect_mode, fn)] * max(1, intensity // 2) if fn else []

    for name, fn in chosen:
        try: img = fn(img); applied.append(name)
        except Exception: pass

    # ── π-pattern extras (always applied last) ───────────────────────────────
    for name, fn in (extra_effects or []):
        try: img = fn(img); applied.append(name)
        except Exception: pass

    img.save(out, 'JPEG', quality=95)
    return applied


# ═══════════════════════════════════════════════════════════════════════════════
#  VIDEO PROCESSING  — apply trippy effects frame-by-frame via OpenCV
# ═══════════════════════════════════════════════════════════════════════════════

def get_video_duration(path):
    """Return duration in seconds, or None on failure."""
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        fps   = cap.get(cv2.CAP_PROP_FPS) or 30
        total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        return total / fps if total > 0 else None
    except Exception:
        return None


def generate_trippy_video(src, out, intensity=3,
                          effect_mode='🎲 Randomizer', scramble=False,
                          scramble_strength=0.5, progress_cb=None,
                          extra_effects=None):
    """
    Apply trippy effects to every frame of a video using OpenCV.
    - Trims to MAX_VIDEO_SECONDS if needed.
    - Outputs a 1080×1080 square-cropped MP4 (H.264).
    - progress_cb(0.0–1.0) called each frame.
    - extra_effects: optional list of (name, fn) tuples appended after the main pipeline.
    Returns list of applied effect names.
    """
    import cv2

    # ── Pick effects once (consistent look across all frames) ────────────────
    if effect_mode == '🎲 Randomizer':
        lo, hi = INTENSITY_FX.get(intensity, (2, 4))
        chosen = random.sample(EFFECTS, min(_ri(lo, hi), len(EFFECTS)))
    else:
        fn = EFFECT_MAP.get(effect_mode)
        chosen = [(effect_mode, fn)] * max(1, intensity // 2) if fn else []
    chosen = chosen + list(extra_effects or [])
    applied = [name for name, _ in chosen]

    cap = cv2.VideoCapture(str(src))
    fps         = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames= int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    max_frames  = int(fps * MAX_VIDEO_SECONDS)
    frames_to_write = min(total_frames, max_frames)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(out), fourcc, fps, (1080, 1080))

    frame_idx = 0
    while True:
        ret, frame_bgr = cap.read()
        if not ret or frame_idx >= max_frames:
            break

        # BGR → RGB PIL image
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)

        # Square-crop + resize
        w, h = img.size
        s    = min(w, h)
        img  = img.crop(((w-s)//2, (h-s)//2, (w+s)//2, (h+s)//2))
        img  = img.resize((1080, 1080), Image.LANCZOS)

        # Scramble
        if scramble:
            img = auto_scramble(img, scramble_strength)

        # Apply effects
        for name, fn in chosen:
            try: img = fn(img)
            except Exception: pass

        # RGB PIL → BGR numpy → write
        out_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        writer.write(out_bgr)

        frame_idx += 1
        if progress_cb and frames_to_write > 0:
            progress_cb(frame_idx / frames_to_write)

    cap.release()
    writer.release()

    # Re-mux with ffmpeg to get proper H.264 + copy original audio if available
    tmp = str(out) + '_tmp.mp4'
    os.rename(str(out), tmp)
    ffmpeg_cmd = (
        f'ffmpeg -y -i "{tmp}" -i "{src}" '
        f'-map 0:v:0 -map 1:a:0? '
        f'-c:v libx264 -crf 23 -preset fast '
        f'-c:a aac -shortest '
        f'"{out}" 2>/dev/null'
    )
    ret = os.system(ffmpeg_cmd)
    if ret != 0 or not os.path.exists(str(out)):
        # ffmpeg not available — just rename the raw mp4v file
        os.rename(tmp, str(out))
    else:
        try: os.remove(tmp)
        except Exception: pass

    return applied


# ═══════════════════════════════════════════════════════════════════════════════
#  NFT REEL GENERATOR  — turn a static NFT image into a 5-second Instagram Reel
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_face_region(B, S):
    """
    Heuristic face/character region detector — no external libs needed.
    Looks for warm, saturated pixels in the upper-centre quadrant.
    Falls back to the upper-centre 40 % crop if nothing convincing found.
    Returns (fy0, fy1, fx0, fx1) pixel bounding box.
    """
    r, g, b_ch = B[:,:,0], B[:,:,1], B[:,:,2]
    mx  = np.maximum(np.maximum(r, g), b_ch)
    mn  = np.minimum(np.minimum(r, g), b_ch)
    sat = np.where(mx > 1e-3, (mx - mn) / mx, 0.0)
    lum  = r*0.299 + g*0.587 + b_ch*0.114
    warm = r > b_ch
    skin = (lum > 50) & (lum < 230) & (sat > 0.08) & (sat < 0.75) & warm
    h_lim = int(S * 0.70); w_lo = int(S * 0.15); w_hi = int(S * 0.85)
    roi   = np.zeros_like(skin)
    roi[:h_lim, w_lo:w_hi] = skin[:h_lim, w_lo:w_hi]
    if roi.sum() > 200:
        ys_i, xs_i = np.where(roi)
        fy0 = max(0,   int(ys_i.min()) - 20)
        fy1 = min(S-1, int(ys_i.max()) + 20)
        fx0 = max(0,   int(xs_i.min()) - 20)
        fx1 = min(S-1, int(xs_i.max()) + 20)
        if (fy1 - fy0) > 40 and (fx1 - fx0) > 40:
            return fy0, fy1, fx0, fx1
    return int(S*0.08), int(S*0.58), int(S*0.20), int(S*0.80)


def _apply_living_layer(frame, B_orig, fi, N, face_box, lp, S):
    """
    Apply living-character animations to the face_box region of `frame`.

    Animations (all pure numpy, no PIL in the frame loop):
      • Breathing  — vertical scale oscillation of the face crop
      • Micro-sway — horizontal sine drift
      • Skin pulse — warm RGB throb (subsurface glow)
      • Eye blink  — brightness dip on upper-third of face at blink frames
      • Aura shimmer — neon edge flicker around the face bounding box

    Returns the modified frame as uint8.
    """
    fy0, fy1, fx0, fx1 = face_box
    t   = fi / max(N - 1, 1)
    ph  = t * math.pi * 2

    frame = frame.astype(np.float32)
    fh    = fy1 - fy0
    fw    = fx1 - fx0
    if fh < 4 or fw < 4:
        return frame.astype(np.uint8)

    crop = frame[fy0:fy1, fx0:fx1].copy()

    # ── Breathing: vertical scale ─────────────────────────────────────────────
    breath_off = int(lp['breath_amp'] * math.sin(ph * lp['breath_freq']))
    if abs(breath_off) > 0 and fh > 8:
        new_h = max(4, fh + breath_off)
        src_rows = np.clip((np.linspace(0, fh-1, new_h)).astype(np.int32), 0, fh-1)
        scaled = crop[src_rows, :]
        if new_h <= fh:
            pad    = (fh - new_h) // 2
            canvas = crop.copy()
            canvas[pad:pad+new_h, :] = scaled
            crop = canvas
        else:
            crop = scaled[:fh, :]

    # ── Micro-sway: horizontal shift ──────────────────────────────────────────
    sway_px = int(lp['sway_amp'] * math.sin(ph * lp['sway_freq'] + lp['sway_phase']))
    if sway_px != 0:
        crop = np.roll(crop, sway_px, axis=1)
        if sway_px > 0:
            crop[:, :sway_px] = frame[fy0:fy1, fx0:min(fx0+abs(sway_px), S-1)]
        else:
            crop[:, sway_px:] = frame[fy0:fy1, max(fx1+sway_px, 0):fx1]

    # ── Skin pulse: warm luminance throb ─────────────────────────────────────
    pulse = lp['pulse_amp'] * (0.5 + 0.5 * math.sin(ph * lp['pulse_freq']))
    crop[:,:,0] = np.clip(crop[:,:,0] + pulse * 1.2, 0, 255)
    crop[:,:,1] = np.clip(crop[:,:,1] + pulse * 0.5, 0, 255)
    crop[:,:,2] = np.clip(crop[:,:,2] + pulse * 0.2, 0, 255)

    # ── Eye blink: darkness on upper-third of face ────────────────────────────
    if fi in lp['blink_frames']:
        ey1 = max(1, fh // 3)
        crop[:ey1, :] = np.clip(crop[:ey1, :] * lp['blink_dark'], 0, 255)

    # ── Aura shimmer: neon edge glow ─────────────────────────────────────────
    if lp.get('aura'):
        aura_str = lp['aura_str'] * (0.4 + 0.6 * abs(math.sin(ph * 3.7 + fi * 0.13)))
        ac = np.array(lp['aura_col'], dtype=np.float32)
        for edge_s in [np.s_[0:2, :], np.s_[-2:, :], np.s_[:, 0:2], np.s_[:, -2:]]:
            crop[edge_s] = np.clip(crop[edge_s]*(1-aura_str) + ac*aura_str, 0, 255)

    frame[fy0:fy1, fx0:fx1] = crop
    return frame.astype(np.uint8)


def generate_nft_reel(nft_img, out_path, duration_sec=5, fps=30, intensity=3,
                      effect_mode='🎲 Randomizer', log_cb=None):
    """
    SUPERCHARGED NFT REEL GENERATOR v13 — LIVING CHARACTERS edition

    v13 adds a face-region "living character" layer on top of the global VFX:
      • Breathing  — face crop expands/contracts on a sine wave
      • Micro-sway — subtle horizontal drift like a living being
      • Skin pulse  — warm luminance throb (subsurface glow)
      • Eye blink   — brightness dip on the upper face at randomised frames
      • Aura shimmer— neon edge flicker around the face (45 % chance)

    8 global VFX presets (unchanged from v11.3):
      1. GLITCH STORM    ·  2. VORTEX PULL  ·  3. PLASMA WAVE
      4. SCANLINE BURN   ·  5. DATA MELT    ·  6. MIRROR FRACTURE
      7. STROBE PULSE    ·  8. VOID COLLAPSE

    Pipes raw RGB → ffmpeg H.264/yuv420p for guaranteed IG Reels compat.
    """
    import subprocess, shutil

    def _log(msg):
        if log_cb: log_cb(msg)

    out_path = str(out_path)
    size     = 1080
    N        = int(fps * duration_sec)   # total frames
    S        = size

    # ── Step 1: bake ONE trippy effect on the base image (PIL, done once) ────
    _log('[Reel] Baking base frame…')
    base = nft_img.convert('RGB').resize((S, S), Image.LANCZOS)

    if effect_mode == '🎲 Randomizer':
        chosen_fx = random.sample(EFFECTS, min(2, len(EFFECTS)))
    else:
        fn = EFFECT_MAP.get(effect_mode)
        chosen_fx = [(effect_mode, fn)] if fn else [random.choice(EFFECTS)]

    for _name, _fn in chosen_fx:
        try:
            _res = _fn(base)
            if _res is not None:
                base = _res.convert('RGB').resize((S, S), Image.BILINEAR)
        except Exception:
            pass

    B = np.array(base, dtype=np.float32)          # (H,W,3) base float

    # ── Step 1b: detect face/character region for living-char animation ──────
    _log('[Reel] Detecting face/character region…')
    _face_box = _detect_face_region(B, S)
    _log(f'[Reel] Face region: y={_face_box[0]}–{_face_box[1]}, x={_face_box[2]}–{_face_box[3]}')

    # Build living-character per-frame animation parameters
    _living_params = {
        'breath_amp':   random.uniform(4, 10),
        'breath_freq':  random.uniform(0.8, 1.4),
        'sway_amp':     random.uniform(2, 6),
        'sway_freq':    random.uniform(0.5, 1.0),
        'sway_phase':   random.uniform(0, math.pi),
        'pulse_amp':    random.uniform(6, 18),
        'pulse_freq':   random.uniform(1.2, 2.5),
        'blink_dark':   random.uniform(0.15, 0.40),
        'blink_frames': set(),
        'aura':         random.random() < 0.45,
        'aura_str':     random.uniform(0.25, 0.65),
        'aura_col':     [random.choice([255, 0, 200, 180]),
                         random.choice([0, 255, 200, 100]),
                         random.choice([255, 200, 255, 100])],
    }
    # 2–4 blinks per clip, each 2–3 frames long
    for _ in range(_ri(2, 4)):
        bs = _ri(5, N - 6)
        for k in range(_ri(2, 3)):
            _living_params['blink_frames'].add(bs + k)


    ys, xs = np.mgrid[0:S, 0:S].astype(np.float32)
    cx = cy = S / 2.0
    dx0 = xs - cx;  dy0 = ys - cy          # centred coords (reused)
    dist0 = np.sqrt(dx0**2 + dy0**2)       # radial distance (reused)
    angle0 = np.arctan2(dy0, dx0)          # polar angle (reused)

    # Random VFX preset selection
    PRESETS = ['glitch_storm','vortex_pull','plasma_wave','scanline_burn',
               'data_melt','mirror_fracture','strobe_pulse','void_collapse']
    preset = random.choice(PRESETS)
    _log(f'[Reel] VFX preset: {preset.upper().replace("_"," ")} — {N} frames…')

    # ── Per-preset parameter randomisation ───────────────────────────────────
    p = {}   # parameter dict

    if preset == 'glitch_storm':
        p['chr_max']   = _ri(8, 28)           # max chromatic split px
        p['tear_n']    = _ri(3, 9)            # scan tear count
        p['hue_spd']   = random.uniform(60, 180)
        p['zoom_amp']  = random.uniform(0.02, 0.05)

    elif preset == 'vortex_pull':
        p['swirl_str'] = random.uniform(1.8, 4.5)   # spiral strength
        p['radius']    = random.uniform(0.25, 0.55) * S
        p['zoom_amp']  = random.uniform(0.04, 0.09)
        p['hue_spd']   = random.uniform(40, 120)

    elif preset == 'plasma_wave':
        p['ax']   = random.uniform(18, 45)    # wave amplitude x
        p['ay']   = random.uniform(12, 30)    # wave amplitude y
        p['fx']   = random.uniform(0.025, 0.07)
        p['fy']   = random.uniform(0.025, 0.07)
        p['hue_spd'] = random.uniform(90, 270)
        p['tint'] = np.array([random.uniform(0.6,1.4),
                               random.uniform(0.6,1.4),
                               random.uniform(0.6,1.4)], dtype=np.float32)

    elif preset == 'scanline_burn':
        p['scan_gap']  = _ri(3, 7)
        p['scan_fade'] = random.uniform(0.35, 0.65)
        p['vig_str']   = random.uniform(0.6, 1.1)
        p['zoom_amp']  = random.uniform(0.03, 0.07)
        p['zoom_freq'] = random.uniform(2.0, 4.0)

    elif preset == 'data_melt':
        p['melt_amp']  = random.uniform(15, 50)   # px column vertical shift
        p['melt_freq'] = random.uniform(0.004, 0.012)
        p['chr_shift'] = _ri(4, 18)
        p['hue_spd']   = random.uniform(30, 90)

    elif preset == 'mirror_fracture':
        p['rot_amp']   = random.uniform(4, 12)    # degrees full rotation
        p['zoom_amp']  = random.uniform(0.03, 0.07)
        p['chr_bleed'] = _ri(3, 14)
        p['hue_spd']   = random.uniform(20, 60)
        # half-sizes for 4-way fold
        h2, w2 = S // 2, S // 2

    elif preset == 'strobe_pulse':
        p['bpm']       = random.choice([120, 128, 140, 160])  # beats per minute
        p['sat_boost'] = random.uniform(1.3, 2.2)
        p['hue_spd']   = random.uniform(45, 135)
        p['zoom_amp']  = random.uniform(0.02, 0.06)
        # pre-bake greyscale for flash frames
        grey_B = B.mean(axis=2, keepdims=True)

    elif preset == 'void_collapse':
        p['pull_str']  = random.uniform(0.08, 0.22)   # radial pull strength
        p['desat_r']   = random.uniform(0.55, 0.85) * S  # desat radius
        p['zoom_amp']  = random.uniform(0.05, 0.12)
        p['hue_spd']   = random.uniform(20, 80)

    # ── Step 3: frame factory (pure numpy, ~8 ops/frame) ─────────────────────

    def _make_frame(fi):
        t     = fi / max(N - 1, 1)      # 0→1
        ph    = t * math.pi * 2          # phase 0→2π

        # ── GLITCH STORM ──────────────────────────────────────────────────────
        if preset == 'glitch_storm':
            # Chromatic RGB split (oscillates left/right per channel)
            cs = int(p['chr_max'] * math.sin(ph * 2.3))
            r_xs = np.clip(xs.astype(np.int32) + cs,      0, S-1)
            b_xs = np.clip(xs.astype(np.int32) - cs,      0, S-1)
            yi   = ys.astype(np.int32)
            frame = np.empty((S, S, 3), np.float32)
            frame[:,:,0] = B[yi, r_xs, 0]
            frame[:,:,1] = B[yi, xs.astype(np.int32), 1]
            frame[:,:,2] = B[yi, b_xs, 2]
            # Horizontal scan tears (random rows get horizontally shifted)
            rng = np.random.default_rng(fi * 7919)
            for _ in range(p['tear_n']):
                ty  = int(rng.integers(0, S))
                tsz = int(rng.integers(2, 12))
                tsh = int(rng.integers(-60, 60))
                y0  = max(0, ty); y1 = min(S, ty + tsz)
                frame[y0:y1] = np.roll(frame[y0:y1], tsh, axis=1)
            # Zoom throb
            sc  = 1.0 + p['zoom_amp'] * math.sin(ph * 3)
            cos_a = sc; sin_a = 0.0
            sx2 = np.clip((cos_a * dx0 + cx).astype(np.int32), 0, S-1)
            sy2 = np.clip((cos_a * dy0 + cy).astype(np.int32), 0, S-1)
            frame = frame[sy2, sx2]
            # Hue pulse
            ha = math.radians(p['hue_spd'] * t)
            c_h, s_h, sq3 = math.cos(ha), math.sin(ha), math.sqrt(3)
            r2,g2,b2 = frame[:,:,0], frame[:,:,1], frame[:,:,2]
            nr = r2*(c_h+(1-c_h)/3) + g2*((1-c_h)/3-s_h/sq3) + b2*((1-c_h)/3+s_h/sq3)
            ng = r2*((1-c_h)/3+s_h/sq3) + g2*(c_h+(1-c_h)/3) + b2*((1-c_h)/3-s_h/sq3)
            nb = r2*((1-c_h)/3-s_h/sq3) + g2*((1-c_h)/3+s_h/sq3) + b2*(c_h+(1-c_h)/3)
            return np.clip(np.stack([nr,ng,nb], axis=2), 0, 255).astype(np.uint8)

        # ── VORTEX PULL ───────────────────────────────────────────────────────
        elif preset == 'vortex_pull':
            # Spiral: rotation angle increases toward centre over time
            swirl = p['swirl_str'] * t * (1.0 - np.clip(dist0 / p['radius'], 0, 1))**2
            ang_w = angle0 + swirl
            sc    = 1.0 + p['zoom_amp'] * math.sin(ph * 1.7)
            r_pull = dist0 * sc
            src_x = np.clip((cx + r_pull * np.cos(ang_w)).astype(np.int32), 0, S-1)
            src_y = np.clip((cy + r_pull * np.sin(ang_w)).astype(np.int32), 0, S-1)
            frame = B[src_y, src_x]
            # Bloom: bright regions glow harder at peak vortex
            bloom_t = 0.5 + 0.5 * math.sin(ph * 2)
            lum = frame.mean(axis=2, keepdims=True) / 255.0
            frame = frame * (1 + bloom_t * 0.35 * lum)
            # Hue
            ha = math.radians(p['hue_spd'] * t)
            c_h,s_h,sq3 = math.cos(ha),math.sin(ha),math.sqrt(3)
            r2,g2,b2 = frame[:,:,0],frame[:,:,1],frame[:,:,2]
            nr = r2*(c_h+(1-c_h)/3)+g2*((1-c_h)/3-s_h/sq3)+b2*((1-c_h)/3+s_h/sq3)
            ng = r2*((1-c_h)/3+s_h/sq3)+g2*(c_h+(1-c_h)/3)+b2*((1-c_h)/3-s_h/sq3)
            nb = r2*((1-c_h)/3-s_h/sq3)+g2*((1-c_h)/3+s_h/sq3)+b2*(c_h+(1-c_h)/3)
            return np.clip(np.stack([nr,ng,nb],2),0,255).astype(np.uint8)

        # ── PLASMA WAVE ───────────────────────────────────────────────────────
        elif preset == 'plasma_wave':
            # Dual-axis sine warp (X shifted by Y wave, Y shifted by X wave)
            wx = (p['ax'] * np.sin(ys * p['fx'] + ph * 2.1)).astype(np.int32)
            wy = (p['ay'] * np.sin(xs * p['fy'] + ph * 1.7)).astype(np.int32)
            src_x = np.clip(xs.astype(np.int32) + wx, 0, S-1)
            src_y = np.clip(ys.astype(np.int32) + wy, 0, S-1)
            frame = B[src_y, src_x]
            # Full hue rotation
            ha = math.radians(p['hue_spd'] * t)
            c_h,s_h,sq3 = math.cos(ha),math.sin(ha),math.sqrt(3)
            r2,g2,b2 = frame[:,:,0],frame[:,:,1],frame[:,:,2]
            nr = r2*(c_h+(1-c_h)/3)+g2*((1-c_h)/3-s_h/sq3)+b2*((1-c_h)/3+s_h/sq3)
            ng = r2*((1-c_h)/3+s_h/sq3)+g2*(c_h+(1-c_h)/3)+b2*((1-c_h)/3-s_h/sq3)
            nb = r2*((1-c_h)/3-s_h/sq3)+g2*((1-c_h)/3+s_h/sq3)+b2*(c_h+(1-c_h)/3)
            frame = np.stack([nr,ng,nb],2)
            # Neon tint pulse (colour temperature breathing)
            tint_t = 0.5 + 0.5 * math.sin(ph * 3)
            tint = 1.0 + (p['tint'] - 1.0) * tint_t
            return np.clip(frame * tint, 0, 255).astype(np.uint8)

        # ── SCANLINE BURN ─────────────────────────────────────────────────────
        elif preset == 'scanline_burn':
            # Zoom throb
            sc   = 1.0 + p['zoom_amp'] * math.sin(ph * p['zoom_freq'])
            src_x= np.clip((sc*dx0+cx).astype(np.int32), 0, S-1)
            src_y= np.clip((sc*dy0+cy).astype(np.int32), 0, S-1)
            frame= B[src_y, src_x].copy()
            # CRT horizontal scanlines — dim every Nth row
            fade = 1.0 - p['scan_fade'] * (0.5 + 0.5 * math.sin(ph * 4))
            frame[::p['scan_gap']] *= fade
            # Radial vignette burn (edges darken / char as t increases)
            norm_d = np.clip(dist0 / (S * 0.6), 0, 1)
            vig    = (1.0 - norm_d * p['vig_str'] * (0.6 + 0.4 * t))[:,:, np.newaxis]
            frame *= np.clip(vig, 0, 1)
            # Edge colour burn — edges shift toward deep orange/red
            burn_col = np.array([255*t, 80*t, 0], np.float32)
            edge_mask= np.clip((norm_d - 0.55) * 3, 0, 1)[:,:, np.newaxis]
            frame = frame*(1-edge_mask*0.6) + burn_col*edge_mask*0.6
            return np.clip(frame, 0, 255).astype(np.uint8)

        # ── DATA MELT ─────────────────────────────────────────────────────────
        elif preset == 'data_melt':
            # Column-wise vertical melt: each column shifts down proportional to sin
            col_shift = (p['melt_amp'] * t *
                         np.sin(np.arange(S, dtype=np.float32) * p['melt_freq'] * 2 * math.pi)
                        ).astype(np.int32)   # (W,)
            src_y = np.clip(ys.astype(np.int32) - col_shift[np.newaxis, :], 0, S-1)
            src_x = xs.astype(np.int32)
            frame = B[src_y, src_x]
            # Per-channel horizontal glitch offset
            cs = int(p['chr_shift'] * math.sin(ph * 5.3))
            r_col = np.clip(src_x + cs,  0, S-1)
            b_col = np.clip(src_x - cs,  0, S-1)
            frame_r = B[src_y, r_col, 0]
            frame_b = B[src_y, b_col, 2]
            frame = frame.copy()
            frame[:,:,0] = frame_r
            frame[:,:,2] = frame_b
            # Hue drift
            ha = math.radians(p['hue_spd'] * t)
            c_h,s_h,sq3 = math.cos(ha),math.sin(ha),math.sqrt(3)
            r2,g2,b2 = frame[:,:,0],frame[:,:,1],frame[:,:,2]
            nr = r2*(c_h+(1-c_h)/3)+g2*((1-c_h)/3-s_h/sq3)+b2*((1-c_h)/3+s_h/sq3)
            ng = r2*((1-c_h)/3+s_h/sq3)+g2*(c_h+(1-c_h)/3)+b2*((1-c_h)/3-s_h/sq3)
            nb = r2*((1-c_h)/3-s_h/sq3)+g2*((1-c_h)/3+s_h/sq3)+b2*(c_h+(1-c_h)/3)
            return np.clip(np.stack([nr,ng,nb],2),0,255).astype(np.uint8)

        # ── MIRROR FRACTURE ───────────────────────────────────────────────────
        elif preset == 'mirror_fracture':
            # Slowly rotate base then 4-way fold
            ang = math.radians(p['rot_amp'] * math.sin(ph))
            sc  = 1.0 + p['zoom_amp'] * math.sin(ph * 2)
            cos_a = math.cos(ang) * sc; sin_a = math.sin(ang) * sc
            src_x = np.clip((cos_a*dx0 - sin_a*dy0 + cx).astype(np.int32), 0, S-1)
            src_y = np.clip((sin_a*dx0 + cos_a*dy0 + cy).astype(np.int32), 0, S-1)
            rot = B[src_y, src_x]          # rotated base
            # 4-way fold: tile top-left quadrant with mirrors
            h2 = S // 2
            q  = rot[:h2, :h2]             # top-left quad
            frame = np.empty((S, S, 3), np.float32)
            frame[:h2, :h2] = q
            frame[:h2, h2:] = q[:, ::-1]           # top-right (H flip)
            frame[h2:, :h2] = q[::-1, :]           # bottom-left (V flip)
            frame[h2:, h2:] = q[::-1, ::-1]        # bottom-right (both)
            # Chromatic bleed outward from seam
            cb = p['chr_bleed']
            seam_r = np.clip(xs.astype(np.int32) + cb, 0, S-1)
            seam_b = np.clip(xs.astype(np.int32) - cb, 0, S-1)
            frame[:,:,0] = frame[ys.astype(np.int32), seam_r, 0]
            frame[:,:,2] = frame[ys.astype(np.int32), seam_b, 2]
            # Hue
            ha = math.radians(p['hue_spd'] * t)
            c_h,s_h,sq3 = math.cos(ha),math.sin(ha),math.sqrt(3)
            r2,g2,b2 = frame[:,:,0],frame[:,:,1],frame[:,:,2]
            nr = r2*(c_h+(1-c_h)/3)+g2*((1-c_h)/3-s_h/sq3)+b2*((1-c_h)/3+s_h/sq3)
            ng = r2*((1-c_h)/3+s_h/sq3)+g2*(c_h+(1-c_h)/3)+b2*((1-c_h)/3-s_h/sq3)
            nb = r2*((1-c_h)/3-s_h/sq3)+g2*((1-c_h)/3+s_h/sq3)+b2*(c_h+(1-c_h)/3)
            return np.clip(np.stack([nr,ng,nb],2),0,255).astype(np.uint8)

        # ── STROBE PULSE ──────────────────────────────────────────────────────
        elif preset == 'strobe_pulse':
            # Beat-synced: at beat peaks, flash to desaturated + colour swap
            beat_phase = (fi * p['bpm'] / (fps * 60)) % 1.0   # 0→1 per beat
            beat_hit   = max(0.0, 1.0 - beat_phase * 6)        # sharp attack, fast decay
            # Zoom throb on beat
            sc   = 1.0 + p['zoom_amp'] * (math.sin(ph * 2) + beat_hit * 0.5)
            src_x= np.clip((sc*dx0+cx).astype(np.int32), 0, S-1)
            src_y= np.clip((sc*dy0+cy).astype(np.int32), 0, S-1)
            frame= B[src_y, src_x]
            # Hue rotate continuously
            ha = math.radians(p['hue_spd'] * t)
            c_h,s_h,sq3 = math.cos(ha),math.sin(ha),math.sqrt(3)
            r2,g2,b2 = frame[:,:,0],frame[:,:,1],frame[:,:,2]
            nr = r2*(c_h+(1-c_h)/3)+g2*((1-c_h)/3-s_h/sq3)+b2*((1-c_h)/3+s_h/sq3)
            ng = r2*((1-c_h)/3+s_h/sq3)+g2*(c_h+(1-c_h)/3)+b2*((1-c_h)/3-s_h/sq3)
            nb = r2*((1-c_h)/3-s_h/sq3)+g2*((1-c_h)/3+s_h/sq3)+b2*(c_h+(1-c_h)/3)
            frame = np.stack([nr,ng,nb],2)
            # On beat: flash to high-sat + colour channel cycle
            if beat_hit > 0.1:
                grey = frame.mean(axis=2, keepdims=True)
                sat_frame = grey + (frame - grey) * p['sat_boost']
                # RGB channel cycle (beat_hit selects which rotation)
                ch_shift = int(beat_hit * 3) % 3
                sat_frame = np.roll(sat_frame, ch_shift, axis=2)
                frame = frame * (1 - beat_hit) + sat_frame * beat_hit
            return np.clip(frame, 0, 255).astype(np.uint8)

        # ── VOID COLLAPSE ─────────────────────────────────────────────────────
        elif preset == 'void_collapse':
            # Radial pull toward centre — gets stronger over time
            pull    = p['pull_str'] * (0.3 + 0.7 * math.sin(ph * 1.5))
            stretch = 1.0 / (1.0 + pull * (1.0 - np.clip(dist0 / (S*0.7), 0, 1)))
            src_x   = np.clip((cx + dx0 * stretch).astype(np.int32), 0, S-1)
            src_y   = np.clip((cy + dy0 * stretch).astype(np.int32), 0, S-1)
            frame   = B[src_y, src_x]
            # Outer ring desaturates and darkens (falling into void)
            outer   = np.clip((dist0 - p['desat_r']) / (S*0.3), 0, 1)[:,:, np.newaxis]
            grey    = frame.mean(axis=2, keepdims=True)
            frame   = frame*(1-outer) + grey*outer*0.3     # desat + darken edge
            # Hue
            ha = math.radians(p['hue_spd'] * t)
            c_h,s_h,sq3 = math.cos(ha),math.sin(ha),math.sqrt(3)
            r2,g2,b2 = frame[:,:,0],frame[:,:,1],frame[:,:,2]
            nr = r2*(c_h+(1-c_h)/3)+g2*((1-c_h)/3-s_h/sq3)+b2*((1-c_h)/3+s_h/sq3)
            ng = r2*((1-c_h)/3+s_h/sq3)+g2*(c_h+(1-c_h)/3)+b2*((1-c_h)/3-s_h/sq3)
            nb = r2*((1-c_h)/3-s_h/sq3)+g2*((1-c_h)/3+s_h/sq3)+b2*(c_h+(1-c_h)/3)
            return np.clip(np.stack([nr,ng,nb],2),0,255).astype(np.uint8)

        # fallback
        return np.clip(B, 0, 255).astype(np.uint8)

    # ── v13 Living-character post-process: wrap _make_frame ──────────────────
    # All per-preset paths already built their uint8 frame; we now apply the
    # living-character layer on top of whatever VFX was rendered this frame.
    _raw_make_frame = _make_frame

    def _make_frame(fi):  # noqa: F811  (intentional shadow)
        raw = _raw_make_frame(fi)
        return _apply_living_layer(raw, B, fi, N, _face_box, _living_params, S)

    # ── Step 3: find ffmpeg ───────────────────────────────────────────────────
    _ffmpeg = shutil.which('ffmpeg') or shutil.which('ffmpeg.exe')
    _iio_ffmpeg = None
    try:
        import imageio_ffmpeg as _iio_ff
        _iio_ffmpeg = _iio_ff.get_ffmpeg_exe()
    except Exception:
        pass
    _ffmpeg = _ffmpeg or _iio_ffmpeg

    # ── Step 4a: pipe raw RGB → ffmpeg (best path) ───────────────────────────
    if _ffmpeg:
        _log(f'[Reel] Piping {N} frames → ffmpeg H.264…')
        cmd = [
            _ffmpeg, '-y',
            '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-pix_fmt', 'rgb24', '-s', f'{S}x{S}', '-r', str(fps),
            '-i', 'pipe:0',
            '-vcodec', 'libx264', '-pix_fmt', 'yuv420p',
            '-crf', '18', '-preset', 'ultrafast',
            '-movflags', '+faststart', '-an',
            out_path,
        ]
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            for fi in range(N):
                proc.stdin.write(_make_frame(fi).tobytes())
            proc.stdin.close()
            proc.wait(timeout=120)
            if proc.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
                _log(f'[Reel] ✓ H.264 saved ({os.path.getsize(out_path)//1024} KB) → {out_path}')
                return out_path
            _log(f'[Reel] ffmpeg returned {proc.returncode} — trying fallback')
        except Exception as e:
            _log(f'[Reel] ffmpeg pipe error: {e} — trying fallback')

    # ── Step 4b: imageio fallback ─────────────────────────────────────────────
    try:
        import imageio
        _log('[Reel] imageio fallback path…')
        frames_list = [_make_frame(fi) for fi in range(N)]
        try:
            imageio.mimwrite(out_path, frames_list, format='FFMPEG', codec='libx264',
                             output_params=['-pix_fmt','yuv420p','-crf','18',
                                            '-preset','ultrafast','-movflags','+faststart'],
                             fps=fps)
        except Exception:
            imageio.mimwrite(out_path, frames_list, fps=fps)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            _log(f'[Reel] ✓ imageio saved ({os.path.getsize(out_path)//1024} KB) → {out_path}')
            return out_path
    except Exception as e:
        _log(f'[Reel] imageio failed: {e}')

    # ── Step 4c: cv2 last-resort ──────────────────────────────────────────────
    try:
        import cv2
        _log('[Reel] ⚠ cv2 last-resort (install ffmpeg for best results)')
        frames_list = [_make_frame(fi) for fi in range(N)]
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        writer = cv2.VideoWriter(out_path, fourcc, float(fps), (S, S))
        if not writer.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(out_path, fourcc, float(fps), (S, S))
        for fr in frames_list:
            writer.write(cv2.cvtColor(fr, cv2.COLOR_RGB2BGR))
        writer.release()
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            _log(f'[Reel] ✓ cv2 saved ({os.path.getsize(out_path)//1024} KB) → {out_path}')
            return out_path
    except Exception as e:
        _log(f'[Reel] cv2 failed: {e}')

    _log('[Reel] ✗ All render paths failed — check ffmpeg/cv2/imageio install')
    return None


def find_browser():
    """Locate an installed Chromium-family browser binary.

    [FIX] Previously missed common install names/paths (google-chrome-stable,
    plain 'chrome', snap/flatpak chromium, Chrome for Testing, additional
    Windows locations) which meant 'Launch Browser & Connect' silently
    raised RuntimeError on many otherwise-valid systems. Now checked, in
    priority order: absolute path candidates, then PATH lookups, then
    snap/flatpak wrapper scripts.
    """
    candidates = [
        # macOS — Intel + Apple Silicon (same .app paths, ARM via Rosetta/native)
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/opt/homebrew/bin/brave-browser",   # Homebrew on Apple Silicon
        "/opt/homebrew/bin/chromium",
        "/usr/local/bin/chromium",
        # Linux
        "/usr/bin/brave-browser", "/usr/bin/brave",
        "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser", "/usr/bin/chromium",
        "/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable",
        "/snap/bin/chromium", "/snap/bin/brave",
        "/var/lib/flatpak/exports/bin/com.google.Chrome",
        "/var/lib/flatpak/exports/bin/org.chromium.Chromium",
        "/var/lib/flatpak/exports/bin/com.brave.Browser",
        os.path.expanduser("~/.local/share/flatpak/exports/bin/com.google.Chrome"),
        os.path.expanduser("~/.local/share/flatpak/exports/bin/org.chromium.Chromium"),
        # Windows
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Chromium\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for c in candidates:
        try:
            if c and Path(c).exists():
                return c
        except Exception:
            continue
    for name in ("brave-browser", "brave", "google-chrome", "google-chrome-stable",
                 "chromium", "chromium-browser", "chrome", "microsoft-edge",
                 "microsoft-edge-stable"):
        p = shutil.which(name)
        if p:
            return p
    return None


# ── Realistic user-agent pool (Chrome 120-124 on Win/Mac/Linux) ──────────────
_USER_AGENTS = [
    # Windows — Chrome 130-135
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # macOS — Chrome 130-135 / Safari 17-18
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    # Linux — Chrome 130-134
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Windows — Firefox 125-128
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    # macOS — Firefox
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.6; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Windows — Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
]

# Varied window sizes — avoids identical viewport fingerprint across sessions
_WINDOW_SIZES = [
    (1366, 768), (1440, 900), (1536, 864), (1600, 900),
    (1280, 800), (1920, 1080), (1280, 720), (1400, 900),
]

# JS injected after every page load — comprehensive fingerprint masking
_STEALTH_JS = """
(function() {
    // ── 1. Kill webdriver flag ────────────────────────────────────────────────
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    delete navigator.__proto__.webdriver;

    // ── 2. Realistic navigator properties ────────────────────────────────────
    const _plat   = ['Win32','MacIntel','Linux x86_64'][Math.floor(Math.random()*3)];
    const _cores  = [2,4,4,4,6,8,8,12,16][Math.floor(Math.random()*9)];
    const _mem    = [2,4,4,8,8,8,16][Math.floor(Math.random()*7)];
    Object.defineProperty(navigator, 'platform',           { get: () => _plat  });
    Object.defineProperty(navigator, 'hardwareConcurrency',{ get: () => _cores });
    Object.defineProperty(navigator, 'deviceMemory',       { get: () => _mem   });
    Object.defineProperty(navigator, 'languages',  { get: () => ['en-US','en'] });
    Object.defineProperty(navigator, 'language',   { get: () => 'en-US'        });
    Object.defineProperty(navigator, 'appVersion', {
        get: () => '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
                   '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    });

    // ── 3. Realistic plugin list ──────────────────────────────────────────────
    const makePlugin = (name, desc, filename, mimeTypes) => {
        const p = Object.create(Plugin.prototype);
        Object.defineProperty(p, 'name',        { value: name });
        Object.defineProperty(p, 'description', { value: desc });
        Object.defineProperty(p, 'filename',    { value: filename });
        Object.defineProperty(p, 'length',      { value: mimeTypes.length });
        mimeTypes.forEach((mt, i) => { p[i] = mt; });
        return p;
    };
    const fakePlugins = [
        makePlugin('Chrome PDF Plugin',      'Portable Document Format', 'internal-pdf-viewer',  []),
        makePlugin('Chrome PDF Viewer',       '',                         'mhjfbmdgcfjbbpaeojofohoefgiehjai', []),
        makePlugin('Native Client',           '',                         'internal-nacl-plugin',  []),
    ];
    Object.defineProperty(navigator, 'plugins', {
        get: () => Object.assign(Object.create(PluginArray.prototype), fakePlugins,
                                 { length: fakePlugins.length })
    });
    Object.defineProperty(navigator, 'mimeTypes', {
        get: () => Object.assign(Object.create(MimeTypeArray.prototype), { length: 0 })
    });

    // ── 4. chrome runtime — must look like real Chrome ────────────────────────
    if (!window.chrome) window.chrome = {};
    window.chrome.runtime = window.chrome.runtime || {
        PlatformOs:       { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
        PlatformArch:     { ARM: 'arm', ARM64: 'arm64', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64' },
        PlatformNaclArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
        RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' },
        OnInstalledReason:        { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
        OnRestartRequiredReason:  { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
    };
    window.chrome.app = { isInstalled: false, InstallState: { DISABLED:'disabled', INSTALLED:'installed', NOT_INSTALLED:'not_installed' }, RunningState: { CANNOT_RUN:'cannot_run', READY_TO_RUN:'ready_to_run', RUNNING:'running' } };
    window.chrome.csi            = () => ({});
    window.chrome.loadTimes      = () => ({});
    window.chrome.gpuBenchmarking = undefined;

    // ── 5. Canvas fingerprint noise ───────────────────────────────────────────
    const _origToDataURL    = HTMLCanvasElement.prototype.toDataURL;
    const _origToBlob       = HTMLCanvasElement.prototype.toBlob;
    const _origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    function _noiseCanvas(canvas) {
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        const img = _origGetImageData.call(ctx, 0, 0, canvas.width || 1, canvas.height || 1);
        for (let i = 0; i < img.data.length; i += 4) {
            img.data[i]   += Math.floor(Math.random() * 3) - 1;
            img.data[i+1] += Math.floor(Math.random() * 3) - 1;
            img.data[i+2] += Math.floor(Math.random() * 3) - 1;
        }
        ctx.putImageData(img, 0, 0);
    }
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
        _noiseCanvas(this); return _origToDataURL.apply(this, args);
    };
    HTMLCanvasElement.prototype.toBlob = function(...args) {
        _noiseCanvas(this); return _origToBlob.apply(this, args);
    };

    // ── 6. WebGL fingerprint masking ──────────────────────────────────────────
    const _getParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        if (param === 37445) return 'Intel Inc.';
        if (param === 37446) return 'Intel Iris OpenGL Engine';
        return _getParam.call(this, param);
    };
    if (window.WebGL2RenderingContext) {
        const _getParam2 = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(param) {
            if (param === 37445) return 'Intel Inc.';
            if (param === 37446) return 'Intel Iris OpenGL Engine';
            return _getParam2.call(this, param);
        };
    }

    // ── 7. AudioContext fingerprint noise ─────────────────────────────────────
    const _AudioContext = window.AudioContext || window.webkitAudioContext;
    if (_AudioContext) {
        const _origCreateOscillator = _AudioContext.prototype.createOscillator;
        _AudioContext.prototype.createOscillator = function() {
            const osc = _origCreateOscillator.apply(this, arguments);
            const _origConnect = osc.connect.bind(osc);
            osc.connect = function(dest, ...args) {
                if (dest && dest.constructor && dest.constructor.name === 'AnalyserNode') {
                    dest._fakeNoise = true;
                }
                return _origConnect(dest, ...args);
            };
            return osc;
        };
    }

    // ── 8. Permissions API — don't reveal automation ──────────────────────────
    const _origQuery = window.navigator.permissions && window.navigator.permissions.query;
    if (_origQuery) {
        window.navigator.permissions.query = function(parameters) {
            if (parameters.name === 'notifications') {
                return Promise.resolve({ state: Notification.permission });
            }
            return _origQuery.call(this, parameters);
        };
    }

    // ── 9. Screen / window dimensions — match the chrome launch args ──────────
    // (already set via --window-size; just ensure outerWidth/Height are non-zero)
    if (window.outerWidth === 0)  window.outerWidth  = window.innerWidth;
    if (window.outerHeight === 0) window.outerHeight = window.innerHeight;

    // ── 10. Hide Selenium/CDP globals ────────────────────────────────────────
    ['$cdc_asdjflasutopfhvcZLmcfl_', '$chrome_asyncScriptInfo',
     '__webdriver_evaluate', '__selenium_evaluate', '__fxdriver_evaluate',
     '__driver_unwrapped', '__webdriver_unwrapped', '__driver_evaluate',
     '__selenium_unwrapped', '__fxdriver_unwrapped',
     '_Selenium_IDE_Recorder', '_selenium', 'calledSelenium',
     '_WEBDRIVER_ELEM_CACHE', 'ChromeDriverw', 'driver-evaluate',
     'webdriver-evaluate', 'selenium-evaluate', 'webdriverCommand',
     'webdriver-evaluate-response', '__webdriverFunc', '__webdriver_script_fn',
     '__$webdriverAsyncExecutor', '__lastWatirAlert', '__lastWatirConfirm',
     '__lastWatirPrompt', '$chrome_asyncScriptInfo', '$cdc_asdjflasutopfhvcZLmcfl_'
    ].forEach(key => {
        try { Object.defineProperty(window, key, { get: () => undefined }); } catch(_) {}
    });

    // ── 11. toString cloaking — prevent native-code checks ───────────────────
    const _toString = Function.prototype.toString;
    const _patched  = new WeakSet();
    Function.prototype.toString = function() {
        if (_patched.has(this)) return 'function () { [native code] }';
        return _toString.call(this);
    };
    [
        HTMLCanvasElement.prototype.toDataURL,
        HTMLCanvasElement.prototype.toBlob,
        WebGLRenderingContext.prototype.getParameter,
        window.navigator.permissions && window.navigator.permissions.query,
    ].forEach(fn => { if (fn) _patched.add(fn); });

})();
"""

def launch_driver(sid=0):
    """Launch Brave/Chrome with stealth hardening and a per-session profile.

    [FIX] find_browser() returning None used to hard-abort with no attempt
    to actually start anything. Now that's only a *warning path*: opts.binary_location
    is simply left unset, letting Selenium Manager (4.6+) locate and, if
    needed, download a matching Chrome build itself. This is what lets
    'Launch Browser & Connect' still work on machines where our path/PATH
    probing misses an unusual but valid install.
    """
    if not HAS_SELENIUM:
        raise RuntimeError(
            "The 'selenium' package is not installed.\n"
            "Run:  pip install selenium")
    browser_path = find_browser()
    profile_dir = str(Path.home() / f".trippygram_browser_profile_{sid}")

    # ── Per-instance isolated RNG — same sid always produces same fingerprint,
    #    but different sids are maximally diverse even when launched simultaneously.
    _rng = random.Random(sid ^ 0xDEADBEEF)

    ua   = _USER_AGENTS[sid % len(_USER_AGENTS)]
    # Also pick a secondary UA variant based on rng so instances don't just cycle
    if _rng.random() < 0.35 and len(_USER_AGENTS) > 1:
        ua = _rng.choice(_USER_AGENTS)

    # Window size: cycle through list then add small per-instance jitter
    _base_w, _base_h = _WINDOW_SIZES[sid % len(_WINDOW_SIZES)]
    w = _base_w + _rng.randint(-40, 40)
    h = _base_h + _rng.randint(-30, 30)

    opts = Options()
    if browser_path:
        opts.binary_location = browser_path
    opts.add_argument(f"--user-data-dir={profile_dir}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(f"--user-agent={ua}")
    opts.add_argument(f"--window-size={w},{h}")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--lang=en-US")
    if sys.platform != 'darwin':          # --no-sandbox not needed (or desired) on macOS
        opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # Extra fingerprint-hardening flags
    opts.add_argument("--disable-features=IsolateOrigins,site-per-process")
    opts.add_argument("--disable-site-isolation-trials")
    opts.add_argument("--disable-client-side-phishing-detection")
    opts.add_argument("--disable-component-update")
    opts.add_argument("--disable-background-networking")
    opts.add_argument("--disable-sync")
    opts.add_argument("--metrics-recording-only")
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--mute-audio")
    opts.add_argument("--use-fake-ui-for-media-stream")
    opts.add_argument("--use-fake-device-for-media-stream")
    # Allow autoplay in automated sessions so video plays without a real gesture
    opts.add_argument("--autoplay-policy=no-user-gesture-required")
    opts.add_argument("--disable-features=PreloadMediaEngagementData,MediaEngagementBypassAutoplayPolicies")
    opts.add_argument("--disable-oopr-debug-crash-dump")
    opts.add_argument("--no-crash-upload")
    # Per-instance accept-lang q-value — use isolated RNG, not shared random state
    _q = round(_rng.uniform(0.6, 0.95), 2)
    opts.add_argument(f"--accept-lang=en-US,en;q={_q}")
    opts.add_experimental_option("excludeSwitches",
                                 ["enable-automation", "enable-logging",
                                  "enable-blink-features"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "profile.exit_type": "Normal",
        "profile.exited_cleanly": True,
    })

    try:
        driver = webdriver.Chrome(options=opts)
    except Exception:
        # Try to find chromedriver — check Homebrew paths on macOS first
        cd = (shutil.which("chromedriver") or
              (sys.platform == 'darwin' and (
                  Path("/opt/homebrew/bin/chromedriver").exists() and
                  "/opt/homebrew/bin/chromedriver" or
                  Path("/usr/local/bin/chromedriver").exists() and
                  "/usr/local/bin/chromedriver")) or None)
        svc = Service(cd) if cd else Service()
        driver = webdriver.Chrome(service=svc, options=opts)

    # Hard cap on how long driver.get() is allowed to block.
    # Without this, Selenium's default is infinite — any stalled navigation
    # hangs the entire thread forever.  30 s is generous for IG/YT/SC.
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(0)   # keep explicit waits in control; no global implicit stall

    # Mask automation fingerprints on every new page
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                           {"source": _STEALTH_JS})
    # Also run stealth on the blank page that's already open
    try:
        driver.execute_script(_STEALTH_JS)
    except Exception:
        pass
    # Randomise window position — use per-instance RNG for true independence
    driver.set_window_position(
        _rng.randint(0, 120) + (sid % 10) * 12,
        _rng.randint(0, 60)  + (sid % 10) * 6,
    )
    return driver
