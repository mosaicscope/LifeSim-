



# ============================================================================
# [11.5] TRIPPYGRAM ENGINE  (the complete original implementation)
# ============================================================================
#
# Everything from here to section [12] is the TrippyGram source, preserved:
# every fx_* effect, the effect registry, the NFT character generator and its
# metadata, the cloud-HD path, the reel generator, the video pipeline, the
# browser automation and the whole original interface.
#
# What was removed, and only this:
#   * the top-level imports          -> merged into the single import block
#   * _pip() / _ensure_deps()        -> it opened a second Tk root at import
#                                       time to show an installer popup; the
#                                       merged app guards its imports instead
#   * the `if __name__ == "__main__"` launcher and its crash handler
#                                    -> there is one entry point now, main()
#
# What was renamed, and only this:
#   * FONT_MONO -> TG_FONT_MONO      -> the single name collision with CREATURE
#
# Note on internal shadowing: the original file defines _arr, _img, _hex,
# _blend, _draw_rounded_rect and the NFT trait tables twice, with the second
# definition winning at import.  That is preserved exactly as-is - the order
# is unchanged, so the runtime behaviour is identical to the original.

#!/usr/bin/env python3
"""
🌀 TrippyGram — Psychedelic Instagram Bulk Poster (Selenium Edition) v10
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
50 Trippy Effects  ·  Auto Generate & Post 100x  ·  SUPERCHARGED posting engine
🎬 VIDEO MODE: NFT Generator now has a VIDEO MODE checkbox — tick it to render
               5-second animated trippy Reels from each NFT and auto-post them
               to Instagram (generates again every 10 posts, posts as Reels).
POSTING v7: 5-strategy Create finder · adaptive upload wait · video dialog drain
            error-banner scanner · 3-strategy caption · 0.15s poll (was 0.3s)
Deps:  pip install Pillow numpy selenium opencv-python
       Brave or Chrome must be installed
Supports photos and videos up to 4 minutes.
"""

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff'}
MAX_VIDEO_SECONDS = 240  # Instagram Reels / Feed cap enforced here


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTO-INSTALL
# ═══════════════════════════════════════════════════════════════════════════════




# ─── Safe imports ─────────────────────────────────────────────────────────────



# ═══════════════════════════════════════════════════════════════════════════════
#  TRIPPY EFFECTS
# ═══════════════════════════════════════════════════════════════════════════════

def _arr(img): return np.array(img.convert('RGB'), dtype=np.float32)
def _img(arr): return Image.fromarray(np.clip(arr,0,255).astype(np.uint8))

def fx_hue_rotate(img, angle=None):
    angle = angle if angle is not None else random.uniform(30,330)
    a = math.radians(angle); c,s = math.cos(a),math.sin(a); sq3 = math.sqrt(3)
    m = [c+(1-c)/3,(1-c)/3-s/sq3,(1-c)/3+s/sq3,
         (1-c)/3+s/sq3,c+(1-c)/3,(1-c)/3-s/sq3,
         (1-c)/3-s/sq3,(1-c)/3+s/sq3,c+(1-c)/3]
    a = _arr(img); r,g,b = a[:,:,0],a[:,:,1],a[:,:,2]
    return _img(np.stack([r*m[0]+g*m[1]+b*m[2],r*m[3]+g*m[4]+b*m[5],r*m[6]+g*m[7]+b*m[8]],axis=2))

def fx_glitch(img, intensity=None):
    intensity = intensity or _ri(8,30)
    a = np.array(img.convert('RGB')); h,w = a.shape[:2]; out = a.copy()
    out[:,:,0] = np.roll(a[:,:,0],_ri(-intensity,intensity),axis=1)
    out[:,:,1] = np.roll(a[:,:,1],_ri(-intensity,intensity),axis=0)
    out[:,:,2] = np.roll(a[:,:,2],_ri(-intensity,intensity),axis=1)
    for _ in range(_ri(5,20)):
        y = _ri(0,h-1); out[y] = np.roll(out[y],_ri(-40,40),axis=0)
    return Image.fromarray(out)

def fx_psychedelic(img):
    a = _arr(img); result = np.zeros_like(a)
    for ch in range(3):
        result[:,:,ch] = np.clip(
            random.uniform(80,160) + random.uniform(80,127.5) *
            np.sin(a[:,:,ch]*random.uniform(0.008,0.04)+random.uniform(0,math.pi*2)), 0, 255)
    return _img(result)

def fx_wave(img, amplitude=None, freq=None):
    amplitude = amplitude or _ri(15,45); freq = freq or random.uniform(0.02,0.08)
    a = np.array(img.convert('RGB')); h,w = a.shape[:2]; out = np.zeros_like(a)
    for y in range(h): out[y] = np.roll(a[y],int(amplitude*math.sin(y*freq)),axis=0)
    return Image.fromarray(out)

def fx_kaleidoscope(img):
    img = img.convert('RGB'); w,h = img.size; hw,hh = w//2,h//2
    q = img.crop((0,0,hw,hh)); result = Image.new('RGB',(w,h))
    result.paste(q,(0,0)); result.paste(q.transpose(Image.FLIP_LEFT_RIGHT),(hw,0))
    result.paste(q.transpose(Image.FLIP_TOP_BOTTOM),(0,hh))
    result.paste(q.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM),(hw,hh))
    return result

def fx_posterize(img): return ImageOps.posterize(img.convert('RGB'),_ri(2,4))

def fx_neon_glow(img):
    base = img.convert('RGB')
    edges = ImageEnhance.Color(ImageEnhance.Brightness(
        base.filter(ImageFilter.FIND_EDGES)).enhance(4)).enhance(5)
    return Image.blend(base, edges.filter(ImageFilter.GaussianBlur(_ri(2,5))),
                       random.uniform(0.5,0.9))

def fx_vhs(img):
    a = _arr(img); a[::2] *= random.uniform(0.7,0.88)
    a = np.clip(a+np.random.randint(-25,25,a.shape,dtype=np.int16),0,255)
    a[:,:,0] = np.clip(a[:,:,0]*random.uniform(1.05,1.2),0,255)
    a[:,:,2] = np.clip(a[:,:,2]*random.uniform(0.7,0.9),0,255)
    return _img(a)

def fx_pixelate(img):
    px = _ri(6,22); w,h = img.size
    return img.resize((w//px,h//px),Image.NEAREST).resize((w,h),Image.NEAREST)

def fx_chromatic(img):
    shift = _ri(4,15); r,g,b = img.convert('RGB').split()
    r = r.transform(r.size,Image.AFFINE,(1,0,-shift,0,1,0))
    b = b.transform(b.size,Image.AFFINE,(1,0,+shift,0,1,0))
    return Image.merge('RGB',(r,g,b))

def fx_invert_partial(img):
    a = np.array(img.convert('RGB')); mask = a.mean(axis=2)>_ri(80,180)
    a[mask] = 255-a[mask]; return Image.fromarray(a)

def fx_color_noise(img):
    a = _arr(img); ch = _ri(0,2)
    a[:,:,ch] = np.clip(a[:,:,ch]+np.random.randn(*a.shape[:2])*random.uniform(20,60),0,255)
    return _img(a)

def fx_radial_zoom(img):
    w,h = img.size; scale = random.uniform(0.92,0.99)
    result = img.convert('RGBA').copy(); layer = result.copy()
    for _ in range(_ri(5,12)):
        layer = layer.resize((int(layer.width*scale),int(layer.height*scale)),Image.LANCZOS)
        canvas = Image.new('RGBA',(w,h),(0,0,0,0))
        canvas.paste(layer,((w-layer.width)//2,(h-layer.height)//2))
        result = Image.blend(result,canvas,alpha=0.35)
    return result.convert('RGB')

def fx_duotone(img):
    dark,light = random.choice([((20,0,60),(255,50,200)),((0,30,60),(0,255,180)),
                                 ((60,0,0),(255,220,0)),((0,60,30),(180,0,255))])
    gray = np.array(img.convert('L'),dtype=np.float32)/255.0
    return _img(np.stack([dark[i]+(light[i]-dark[i])*gray for i in range(3)],axis=2))

def fx_mirror_diagonal(img):
    """Reflect across the main diagonal (transpose + optional flip)."""
    img = img.convert('RGB')
    t = img.transpose(Image.TRANSPOSE)
    return Image.blend(img, t, alpha=random.uniform(0.4, 0.8))

def fx_scanlines(img):
    """Horizontal TV scanlines with slight brightness dip on alternating rows."""
    a = _arr(img); h = a.shape[0]
    step = _ri(2, 5)
    fade = random.uniform(0.45, 0.72)
    a[::step] = np.clip(a[::step] * fade, 0, 255)
    return _img(a)

def fx_color_shift_channels(img):
    """Rotate R→G→B channel values for an alien colour palette."""
    a = np.array(img.convert('RGB'))
    shift = _ri(1, 2)
    return Image.fromarray(np.roll(a, shift, axis=2).astype(np.uint8))

def fx_thermal(img):
    """Pseudo-thermal camera look — heat-map colouring."""
    gray = np.array(img.convert('L'), dtype=np.float32) / 255.0
    r = np.clip(gray * 3.0,       0, 1)
    g = np.clip(gray * 3.0 - 1.0, 0, 1)
    b = np.clip(gray * 3.0 - 2.0, 0, 1)
    return _img(np.stack([r*255, g*255, b*255], axis=2))

def fx_oil_paint(img):
    """Approximated oil-paint smoothing via median + saturation boost."""
    img2 = img.convert('RGB').filter(ImageFilter.MedianFilter(size=5))
    return ImageEnhance.Color(img2).enhance(random.uniform(1.8, 2.8))

def fx_pixel_sort_rows(img):
    """Sort pixels in random rows by brightness — subtle data-glitch effect."""
    a = np.array(img.convert('RGB'))
    h = a.shape[0]
    n_rows = _ri(h // 6, h // 2)
    rows = random.sample(range(h), n_rows)
    for y in rows:
        brightness = a[y].mean(axis=1)
        order = np.argsort(brightness)
        if random.random() < 0.5:
            order = order[::-1]
        a[y] = a[y][order]
    return Image.fromarray(a)

# ── 30 NEW EFFECTS (brings total to 50) ──────────────────────────────────────

def fx_rgb_split_cols(img):
    """Vertical column-wise RGB split — neon fringe on edges."""
    a = np.array(img.convert('RGB')); w = a.shape[1]
    shift = _ri(6, 20)
    out = a.copy()
    out[:, :, 0] = np.roll(a[:, :, 0], shift,  axis=1)
    out[:, :, 2] = np.roll(a[:, :, 2], -shift, axis=1)
    return Image.fromarray(out)

def fx_tilt_shift(img):
    """Miniature / tilt-shift blur: sharp band in centre, blurred top & bottom."""
    img = img.convert('RGB'); w, h = img.size
    band = random.uniform(0.20, 0.45)
    cy   = int(h * random.uniform(0.3, 0.7))
    half = int(h * band / 2)
    blurred = img.filter(ImageFilter.GaussianBlur(_ri(6, 14)))
    out = blurred.copy()
    sharp_crop = img.crop((0, max(0, cy-half), w, min(h, cy+half)))
    out.paste(sharp_crop, (0, max(0, cy-half)))
    return out

def fx_deep_fry(img):
    """Deep-fried meme look: extreme saturation, JPEG artefacts, hard sharpen."""
    img = img.convert('RGB')
    img = ImageEnhance.Color(img).enhance(random.uniform(4.0, 7.0))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(2.5, 4.0))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(1.3, 1.8))
    img = img.filter(ImageFilter.SHARPEN)
    img = img.filter(ImageFilter.SHARPEN)
    # Simulate JPEG re-compression noise
    import io
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=_ri(5, 18))
    buf.seek(0)
    return Image.open(buf).copy()

def fx_color_burn(img):
    """Color-dodge / burn blend — hyper-saturated highlights."""
    a = _arr(img)
    burned = np.clip(255 - (255 - a) * 255 / (a + 1), 0, 255)
    t = random.uniform(0.3, 0.7)
    return _img(a * (1-t) + burned * t)

def fx_lsd_warp(img):
    """Sine-wave warp in both axes — psychedelic LSD distortion (vectorised)."""
    a = np.array(img.convert('RGB')); h, w = a.shape[:2]
    amp_x = _ri(12, 35); freq_x = random.uniform(0.03, 0.09)
    amp_y = _ri(8,  25); freq_y = random.uniform(0.03, 0.09)
    ys, xs = np.mgrid[0:h, 0:w]
    nx = (xs + amp_x * np.sin(ys * freq_x)).astype(int) % w
    ny = (ys + amp_y * np.sin(xs * freq_y)).astype(int) % h
    return Image.fromarray(a[ny, nx])

def fx_edge_burn(img):
    """Burned / vignetted edges with colour tint (vectorised)."""
    img = img.convert('RGB'); w, h = img.size
    a = np.array(img, dtype=np.float32)
    cx, cy = w / 2, h / 2
    ys, xs = np.mgrid[0:h, 0:w]
    dist = np.sqrt(((xs - cx) / cx) ** 2 + ((ys - cy) / cy) ** 2)
    fade = np.clip(1.0 - dist * random.uniform(0.55, 0.80), 0.0, 1.0)
    a *= fade[:, :, np.newaxis]
    return _img(a)

def fx_neon_outline(img):
    """Cartoon-style neon edge detection overlay."""
    base  = img.convert('RGB')
    edges = base.filter(ImageFilter.FIND_EDGES)
    edges = ImageEnhance.Brightness(edges).enhance(5.0)
    edges = ImageEnhance.Color(edges).enhance(6.0)
    edges = edges.filter(ImageFilter.GaussianBlur(1))
    col   = random.choice([(0,255,200),(255,0,180),(255,220,0),(0,180,255)])
    tinted= Image.new('RGB', base.size, col)
    mask  = edges.convert('L')
    result= base.copy()
    result.paste(tinted, mask=mask)
    return result

def fx_matrix_rain(img):
    """Green matrix-code scanline texture layered on top."""
    from PIL import ImageDraw as _IDrawMR
    img  = img.convert('RGB'); w, h = img.size
    over = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d    = _IDrawMR.Draw(over)
    col_count = w // 16
    for c in range(col_count):
        x    = c * 16 + _ri(0, 8)
        y    = _ri(0, h)
        ln   = _ri(40, 200)
        bri  = _ri(120, 255)
        for row in range(ln):
            yy = (y + row * 14) % h
            d.text((x, yy), random.choice('01アイウエオカキクケコ'),
                   fill=(0, bri, _ri(30, 80),
                         max(20, int(bri * (1 - row/ln)))))
    result = img.copy().convert('RGBA')
    result.alpha_composite(over)
    return result.convert('RGB')

def fx_emboss(img):
    """Emboss relief with colour tint."""
    embossed = img.convert('RGB').filter(ImageFilter.EMBOSS)
    return Image.blend(img.convert('RGB'), embossed, random.uniform(0.4, 0.85))

def fx_contour(img):
    """Psychedelic contour-line overlay."""
    base    = img.convert('RGB')
    contour = base.filter(ImageFilter.CONTOUR)
    inv     = ImageOps.invert(contour)
    return Image.blend(base, inv.convert('RGB'), random.uniform(0.35, 0.65))

def fx_cross_hatch(img):
    """Diagonal hatching lines over image — retro print feel."""
    from PIL import ImageDraw as _IDrawCH
    img  = img.convert('RGB'); w, h = img.size
    over = Image.new('RGBA', (w, h), (0,0,0,0))
    d    = _IDrawCH.Draw(over)
    step = _ri(6, 18)
    col  = tuple(random.choice([(255,0,255),(0,255,255),(255,255,0)])) + (_ri(40,90),)
    for i in range(-h, w, step):
        d.line([(i, 0),(i+h, h)], fill=col, width=1)
    for i in range(w+h, -h, -step):
        d.line([(i, 0),(i-h, h)], fill=col, width=1)
    result = img.convert('RGBA')
    result.alpha_composite(over)
    return result.convert('RGB')

def fx_color_solarize(img):
    """Selective solarization at random threshold."""
    t = _ri(60, 200)
    return ImageOps.solarize(img.convert('RGB'), threshold=t)

def fx_dreamy_bloom(img):
    """Soft dreamy bloom: screen blend of blurred highlight."""
    img  = img.convert('RGB')
    blur = img.filter(ImageFilter.GaussianBlur(_ri(8, 20)))
    a    = np.array(img,  dtype=np.float32) / 255.0
    b    = np.array(blur, dtype=np.float32) / 255.0
    out  = 1 - (1-a)*(1-b)   # screen blend
    return _img(out * 255)

def fx_rgb_rings(img):
    """Concentric circular colour bands emanating from a random point (vectorised)."""
    img = img.convert('RGB'); w, h = img.size
    a   = np.array(img, dtype=np.float32)
    cx  = _ri(w//4, 3*w//4)
    cy  = _ri(h//4, 3*h//4)
    freq = random.uniform(0.02, 0.06)
    ys, xs = np.mgrid[0:h, 0:w]
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    v = np.sin(d * freq)
    a[:, :, 0] = np.clip(a[:, :, 0] + v * 60, 0, 255)
    a[:, :, 2] = np.clip(a[:, :, 2] - v * 60, 0, 255)
    return _img(a)

def fx_watercolor(img):
    """Watercolour painterly look via median + edge dampening."""
    img2 = img.convert('RGB')
    for _ in range(_ri(2, 4)):
        img2 = img2.filter(ImageFilter.MedianFilter(size=random.choice([3,5])))
    img2 = ImageEnhance.Color(img2).enhance(random.uniform(1.4, 2.0))
    img2 = ImageEnhance.Contrast(img2).enhance(random.uniform(0.8, 1.1))
    return img2

def fx_bit_crush(img):
    """Reduce colour depth to 3-5 bits per channel — arcade bit-crush."""
    bits  = _ri(3, 5)
    a     = np.array(img.convert('RGB'))
    step  = 256 >> bits
    a     = (a // step) * step
    return Image.fromarray(a.astype(np.uint8))

def fx_negative_glow(img):
    """Invert + high-pass glow, then blend back — alien negative aura."""
    inv  = ImageOps.invert(img.convert('RGB'))
    glow = inv.filter(ImageFilter.GaussianBlur(_ri(4, 12)))
    return Image.blend(img.convert('RGB'), glow, random.uniform(0.3, 0.6))

def fx_comic_dots(img):
    """Ben-Day dot halftone pattern — pop-art comics feel."""
    from PIL import ImageDraw as _IDrawCD
    img  = img.convert('RGB').resize((540,540), Image.LANCZOS)
    w, h = img.size
    dot_size = _ri(6, 14)
    out  = Image.new('RGB', (w, h), (255,255,255))
    d    = _IDrawCD.Draw(out)
    for y in range(0, h, dot_size):
        for x in range(0, w, dot_size):
            patch = img.crop((x, y, min(x+dot_size,w), min(y+dot_size,h)))
            avg   = np.array(patch).mean(axis=(0,1)).astype(int)
            r     = int(dot_size/2 * min(1.0, np.array(avg).mean()/255))
            cx2, cy2 = x+dot_size//2, y+dot_size//2
            d.ellipse([cx2-r,cy2-r,cx2+r,cy2+r], fill=tuple(avg))
    return out.resize((1080,1080), Image.LANCZOS)

def fx_hex_mosaic(img):
    """Chunky hexagonal mosaic tiles."""
    from PIL import ImageDraw as _IDrawHM
    img = img.convert('RGB'); w, h = img.size
    tile = _ri(18, 45)
    out  = img.copy()
    d    = _IDrawHM.Draw(out)
    rows = h // tile + 2
    cols = w // tile + 2
    for row in range(rows):
        for col in range(cols):
            cx2 = col * tile + (tile//2 if row%2 else 0)
            cy2 = row * tile
            x0 = max(0, cx2 - tile//2); y0 = max(0, cy2 - tile//2)
            x1 = min(w, cx2 + tile//2); y1 = min(h, cy2 + tile//2)
            if x1 <= x0 or y1 <= y0: continue
            patch = img.crop((x0, y0, x1, y1))
            if patch.size[0] == 0 or patch.size[1] == 0: continue
            avg = tuple(int(x) for x in np.array(patch).mean(axis=(0,1)))
            pts = [(cx2+int(tile/2*math.cos(math.radians(60*i-30))),
                    cy2+int(tile/2*math.sin(math.radians(60*i-30)))) for i in range(6)]
            d.polygon(pts, fill=avg)
    return out

def fx_liquid_metal(img):
    """Silver/chrome liquid metal sheen via emboss + high contrast."""
    gray  = img.convert('L').filter(ImageFilter.EMBOSS)
    metal = ImageEnhance.Contrast(gray.convert('RGB')).enhance(3.0)
    metal = ImageEnhance.Brightness(metal).enhance(1.4)
    return Image.blend(img.convert('RGB'), metal, random.uniform(0.4, 0.75))

def fx_stained_glass(img):
    """Stained-glass segmentation using posterize + edge overlay."""
    poster = ImageOps.posterize(img.convert('RGB'), _ri(2,3))
    edges  = img.convert('RGB').filter(ImageFilter.FIND_EDGES)
    dark   = ImageEnhance.Brightness(edges).enhance(0.0)  # black edges
    mask   = ImageOps.invert(edges.convert('L'))
    result = poster.copy()
    result.paste(dark, mask=ImageOps.invert(mask))
    return result

def fx_tunnel_vision(img):
    """Concentric zoom tunnel: repeated resized pastes toward centre."""
    img  = img.convert('RGB'); w, h = img.size
    out  = img.copy()
    steps = _ri(6, 14)
    for s in range(steps, 0, -1):
        scale = s / steps
        nw, nh = max(1, int(w*scale)), max(1, int(h*scale))
        small  = img.resize((nw, nh), Image.LANCZOS)
        ox, oy = (w-nw)//2, (h-nh)//2
        out.paste(small, (ox, oy))
    return out

def fx_infrared(img):
    """Infrared false-colour: swaps red & green, boosts blue."""
    a = np.array(img.convert('RGB'), dtype=np.float32)
    r, g, b = a[:,:,0].copy(), a[:,:,1].copy(), a[:,:,2].copy()
    a[:,:,0] = np.clip(g * 1.4, 0, 255)
    a[:,:,1] = np.clip(r * 0.6, 0, 255)
    a[:,:,2] = np.clip(b * 1.6 + 30, 0, 255)
    return _img(a)

def fx_comic_kaboom(img):
    """Primary-colour comic book + CMYK-split halftone mix."""
    img2 = ImageOps.posterize(img.convert('RGB'), 2)
    img2 = ImageEnhance.Color(img2).enhance(5.0)
    img2 = ImageEnhance.Contrast(img2).enhance(2.5)
    edges = img.convert('RGB').filter(ImageFilter.FIND_EDGES)
    edges = ImageEnhance.Brightness(edges).enhance(0.0)
    mask  = ImageOps.invert(edges.convert('L'))
    img2.paste(Image.new('RGB', img2.size, (0,0,0)), mask=ImageOps.invert(mask))
    return img2

def fx_prism_shift(img):
    """Coloured prismatic light-refraction: per-channel rotation offsets (vectorised)."""
    a = _arr(img); h, w = a.shape[:2]
    angles = [random.uniform(5, 20), 0, random.uniform(-20, -5)]
    ys, xs = np.mgrid[0:h, 0:w]
    cy2, cx2 = h / 2, w / 2
    for ch, angle in enumerate(angles):
        if angle == 0:
            continue
        rad = math.radians(angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        nx = (cos_a * (xs - cx2) - sin_a * (ys - cy2) + cx2).astype(int) % w
        ny = (sin_a * (xs - cx2) + cos_a * (ys - cy2) + cy2).astype(int) % h
        a[:, :, ch] = a[ny, nx, ch]
    return _img(a)

def fx_lo_fi_dither(img):
    """Floyd-Steinberg-style error-diffusion dither to limited palette."""
    n_cols = _ri(4, 8)
    img2   = img.convert('RGB').quantize(colors=n_cols).convert('RGB')
    return img2

def fx_luma_warp(img):
    """Displace pixels based on local luminance — smeared motion look (vectorised)."""
    a    = np.array(img.convert('RGB')); h, w = a.shape[:2]
    gray = a.mean(axis=2)
    amp  = _ri(8, 25)
    xs   = np.arange(w)
    # broadcast xs across all rows, then shift per-pixel
    nx   = (xs[np.newaxis, :] + amp * (gray / 255.0 - 0.5)).astype(int) % w
    row_idx = np.arange(h)[:, np.newaxis]
    return Image.fromarray(a[row_idx, nx])

def fx_analog_noise(img):
    """Film-grain analog noise with slight colour temperature shift."""
    a    = _arr(img)
    grain= np.random.randn(*a.shape[:2]) * random.uniform(15, 40)
    a[:,:,0] = np.clip(a[:,:,0] + grain * 1.1 + random.uniform(-8,8), 0, 255)
    a[:,:,1] = np.clip(a[:,:,1] + grain * 0.9,                        0, 255)
    a[:,:,2] = np.clip(a[:,:,2] + grain * 0.7 + random.uniform(-8,8), 0, 255)
    return _img(a)

def fx_zoom_blur(img):
    """Radial zoom motion blur from centre — speed-blur feel."""
    img  = img.convert('RGB'); w, h = img.size
    cx, cy = w//2, h//2
    steps  = _ri(8, 18)
    out    = np.zeros((h, w, 3), dtype=np.float32)
    scale_range = np.linspace(1.0, random.uniform(1.05, 1.15), steps)
    for sc in scale_range:
        nw, nh = int(w*sc), int(h*sc)
        resized = img.resize((nw, nh), Image.BILINEAR)
        ox, oy  = (nw-w)//2, (nh-h)//2
        crop    = resized.crop((ox, oy, ox+w, oy+h))
        out    += np.array(crop, dtype=np.float32)
    return _img(out / steps)
