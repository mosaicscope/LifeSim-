

EFFECTS = [
    # ── Original 20 ───────────────────────────────────────────────────────────
    ("Hue Rotate",           fx_hue_rotate),
    ("Glitch",               fx_glitch),
    ("Psychedelic",          fx_psychedelic),
    ("Wave Distort",         fx_wave),
    ("Kaleidoscope",         fx_kaleidoscope),
    ("Posterize",            fx_posterize),
    ("Neon Glow",            fx_neon_glow),
    ("VHS",                  fx_vhs),
    ("Pixelate",             fx_pixelate),
    ("Chromatic Aberration", fx_chromatic),
    ("Partial Invert",       fx_invert_partial),
    ("Color Noise",          fx_color_noise),
    ("Radial Zoom",          fx_radial_zoom),
    ("Duotone",              fx_duotone),
    ("Mirror Diagonal",      fx_mirror_diagonal),
    ("Scanlines",            fx_scanlines),
    ("Channel Shift",        fx_color_shift_channels),
    ("Thermal",              fx_thermal),
    ("Oil Paint",            fx_oil_paint),
    ("Pixel Sort",           fx_pixel_sort_rows),
    # ── 30 New Effects ────────────────────────────────────────────────────────
    ("RGB Column Split",     fx_rgb_split_cols),
    ("Tilt Shift",           fx_tilt_shift),
    ("Deep Fry",             fx_deep_fry),
    ("Color Burn",           fx_color_burn),
    ("LSD Warp",             fx_lsd_warp),
    ("Edge Burn",            fx_edge_burn),
    ("Neon Outline",         fx_neon_outline),
    ("Matrix Rain",          fx_matrix_rain),
    ("Emboss",               fx_emboss),
    ("Contour",              fx_contour),
    ("Cross Hatch",          fx_cross_hatch),
    ("Color Solarize",       fx_color_solarize),
    ("Dreamy Bloom",         fx_dreamy_bloom),
    ("RGB Rings",            fx_rgb_rings),
    ("Watercolor",           fx_watercolor),
    ("Bit Crush",            fx_bit_crush),
    ("Negative Glow",        fx_negative_glow),
    ("Comic Dots",           fx_comic_dots),
    ("Hex Mosaic",           fx_hex_mosaic),
    ("Liquid Metal",         fx_liquid_metal),
    ("Stained Glass",        fx_stained_glass),
    ("Tunnel Vision",        fx_tunnel_vision),
    ("Infrared",             fx_infrared),
    ("Comic Kaboom",         fx_comic_kaboom),
    ("Prism Shift",          fx_prism_shift),
    ("Lo-Fi Dither",         fx_lo_fi_dither),
    ("Luma Warp",            fx_luma_warp),
    ("Analog Noise",         fx_analog_noise),
    ("Zoom Blur",            fx_zoom_blur),
    # ── #50 ───────────────────────────────────────────────────────────────────
    ("Mirror Horizontal",    lambda img: img.convert('RGB').transpose(Image.FLIP_LEFT_RIGHT)),
    # ── 20 New Unique FX ─────────────────────────────────────────────────────
    ("ASCII Shade",          fx_ascii_shade),
    ("Bubble Wrap",          fx_bubble_wrap),
    ("Lightning Strike",     fx_lightning_strike),
    ("Crystallize",          fx_crystallize),
    ("Aurora",               fx_aurora),
    ("Shatter",              fx_shatter),
    ("Paint Splatter",       fx_paint_splatter),
    ("Double Exposure",      fx_double_exposure),
    ("Datamosh",             fx_datamosh),
    ("Neon Grid",            fx_neon_grid),
    ("Smoke Tendrils",       fx_smoke_tendrils),
    ("Melting",              fx_melting),
    ("Star Field",           fx_star_field),
    ("Mosaic Shift",         fx_mosaic_shift),
    ("Rainbow Streak",       fx_rainbow_streak),
    ("Glitch Blocks",        fx_glitch_blocks),
    ("Retro Halftone",       fx_retro_halftone),
    ("Mirror Radial",        fx_mirror_radial),
    ("Electric Aura",        fx_electric_aura),
    ("Color Gravity",        fx_color_gravity),
    # ── 40 More Unique FX ────────────────────────────────────────────────────
    ("Lava Lamp",            fx_lava_lamp),
    ("Tape Warp",            fx_tape_warp),
    ("Oil Slick",            fx_oil_slick),
    ("Pulse Rings",          fx_pulse_rings),
    ("Ghost Echo",           fx_ghost_echo),
    ("Spliced Columns",      fx_spliced_columns),
    ("Glowing Veins",        fx_glowing_veins),
    ("Depth Fog",            fx_depth_fog),
    ("Slit Scan",            fx_slit_scan),
    ("Bleach Bypass",        fx_bleach_bypass),
    ("CRT Curvature",        fx_crt_curvature),
    ("Pointillism",          fx_pointillism),
    ("Film Grain Heavy",     fx_film_grain_heavy),
    ("X-Ray",                fx_xray),
    ("Neon Swirl",           fx_neon_swirl),
    ("Spliced Rows",         fx_spliced_rows),
    ("Pixel Wind",           fx_pixel_wind),
    ("Thermal Night",        fx_thermal_night),
    ("Silk Screen",          fx_silk_screen),
    ("Frosted Glass",        fx_frosted_glass),
    ("Retro TV Bars",        fx_retro_tv_bars),
    ("Zoom Tunnel",          fx_zoom_tunnel),
    ("Soap Bubble",          fx_soap_bubble),
    ("Shadow Puppet",        fx_shadow_puppet),
    ("Displacement Map",     fx_displacement_map),
    ("Neon Rain",            fx_neon_rain),
    ("Cubist",               fx_cubist),
    ("Scanline Color",       fx_scanline_color),
    ("Mirror Four Way",      fx_mirror_four_way),
    ("Burning Edges",        fx_burning_edges),
    ("Time Slice",           fx_time_slice),
    ("Color Dodge Burn",     fx_color_dodge_burn),
    ("Wireframe",            fx_wireframe),
    ("Negative Space",       fx_negative_space),
    ("Acid Wash",            fx_acid_wash),
    ("Glitch Stripes",       fx_glitch_stripes),
    ("Topographic",          fx_topographic),
    ("Pixel Sort Cols",      fx_pixel_sort_cols),
    ("Neon Bokeh",           fx_neon_bokeh),
    ("Low Poly",             fx_low_poly),
    ("Hologram",             fx_hologram),
    ("Retrowave",            fx_retrowave),
    # ── 50 New Unique NFT FX (v6) ─────────────────────────────────────────────
    ("Void Rift",            fx_void_rift),
    ("Plasma Field",         fx_plasma_field),
    ("Vortex Spin",          fx_vortex_spin),
    ("Neon Circuit",         fx_neon_circuit),
    ("Cel Shade",            fx_cel_shade),
    ("Acid Rain",            fx_acid_rain),
    ("Kaleidoscope 6-fold",  fx_mirror_kaleid_6),
    ("Light Leak",           fx_light_leak),
    ("Data Corruption",      fx_data_corruption),
    ("Paint Knife",          fx_paint_knife),
    ("RGB Explosion",        fx_rgb_explosion),
    ("Mosaic Color Bands",   fx_mosaic_color_bands),
    ("Smoke Explosion",      fx_smoke_explosion),
    ("Glitch Color Planes",  fx_glitch_color_planes),
    ("Rainbow Aura",         fx_rainbow_aura),
    ("Pixel Avalanche",      fx_pixel_avalanche),
    ("Chroma Melt",          fx_chroma_melt),
    ("UV Blacklight",        fx_uv_blacklight),
    ("Neon Splatter",        fx_neon_splatter),
    ("Perspective Warp",     fx_perspective_warp),
    ("Gravity Waves",        fx_gravity_waves),
    ("Mirror Mosaic",        fx_mirror_mosaic),
    ("Crystalline Shards",   fx_crystalline_shards),
    ("Liquid Chrome",        fx_liquid_chrome),
    ("Color Shockwave",      fx_color_shockwave),
    ("Glitter Burst",        fx_glitter_burst),
    ("Dark Matter",          fx_dark_matter),
    ("Ink Bleed",            fx_ink_bleed),
    ("Frequency Bands",      fx_frequency_bands),
    ("Diamond Prism",        fx_diamond_prism),
    ("Ghost Trails",         fx_ghost_trails),
    ("Zebra Color",          fx_zebra_color),
    ("Cyber Grid",           fx_cyber_grid),
    ("Retro Sunset",         fx_retro_sunset),
    ("Thermal Zones",        fx_thermal_zones),
    ("Splattered Pixels",    fx_splattered_pixels),
    ("Oil On Water",         fx_oil_on_water),
    ("Shattered Mirror",     fx_shattered_mirror),
    ("Retro Dithered",       fx_retro_dithered),
    ("Neon Fog",             fx_neon_fog),
    ("Double Mirror Offset", fx_double_mirror_offset),
    ("Acid Bubble",          fx_acid_bubble),
    ("Scanline RGB",         fx_scanline_rgb),
    ("Starburst Rays",       fx_starburst_rays),
    ("Neon Lace",            fx_neon_lace),
    ("Disco Tiles",          fx_disco_tiles),
    ("Vertical Smear",       fx_vertical_smear),
    ("Pixel Ripple",         fx_pixel_ripple),
    ("Comic Halftone Color", fx_comic_halftone_color),
    ("Fractal Noise",        fx_fractal_noise),
    ("Mirror Thirds",        fx_mirror_thirds),
    ("Warp Grid",            fx_warp_grid),
    ("Glitch RGB Rows",      fx_glitch_rgb_rows),
    ("Neon Wireframe Mesh",  fx_neon_wireframe_mesh),
    ("Color Inversion Zones",fx_color_inversion_zones),
    ("Long Exposure",        fx_long_exposure),
    ("Cube Map Fold",        fx_cube_map_fold),
    ("Neon Hex Grid",        fx_neon_hex_grid),
    ("Chromatic Rings",      fx_chromatic_rings),
    ("Shadow Burn",          fx_shadow_burn),
    ("Paint Pour",           fx_paint_pour),
    ("Pixel Constellation",  fx_pixel_constellation),
    ("Glitch Freeze Frame",  fx_glitch_freeze_frame),
    ("Pop Art Dots",         fx_pop_art_dots),
    ("Aurora Columns",       fx_aurora_columns),
    ("Stripe Warp",          fx_stripe_warp),
    # ── 3 HD Detailed FX (v10) ───────────────────────────────────────────────
    ("Deep Fractal Plasma",  fx_deep_fractal_plasma),
    ("Iridescent Oil",       fx_iridescent_oil),
    ("Neural Mosaic",        fx_neural_mosaic),
    # ── π-Based Pattern FX ───────────────────────────────────────────────────
    ("π Sacred Geometry",    fx_pi_sacred_geometry),
    ("π Algorithmic Painter",fx_pi_algorithmic_painter),
]
EFFECT_NAMES   = [name for name,_ in EFFECTS]
EFFECT_MAP     = {name: fn for name,fn in EFFECTS}
INTENSITY_FX   = {1:(1,2), 2:(2,3), 3:(2,4), 4:(3,5), 5:(4,7)}


def generate_nft_with_effects(out_path, intensity=3, seed=None, apply_effects=True,
                               override_traits=None, save_metadata=True,
                               use_cloud_hd=False, effect_mode=None, log_cb=None):
    """
    Generate an HD NFT character, optionally apply trippy effects, save.
    Returns (PIL.Image, traits dict, applied_effects list).

    New params vs original:
      save_metadata  — write .json sidecar alongside image
      use_cloud_hd   — use Pollinations Flux for ultra-HD (takes ~30s, free)
      log_cb         — callable for logging
    """
    # Use the EFFECTS and INTENSITY_FX defined in this file
    _EFFECTS = EFFECTS
    _INTENSITY_FX = INTENSITY_FX

    img, traits = generate_nft_character(size=1080, seed=seed, override_traits=override_traits)

    # Cloud HD override
    if use_cloud_hd:
        cloud_path = str(out_path).replace('.jpg','_cloud.png')
        cloud_img  = generate_nft_cloud_hd(traits, cloud_path, size=1080, log_cb=log_cb)
        if cloud_img:
            img = cloud_img

    img = img.resize((1080, 1080), Image.LANCZOS)
    applied = []

    if apply_effects and _EFFECTS:
        lo, hi = _INTENSITY_FX.get(intensity, (2,4))
        _mode  = (effect_mode or '').strip()
        if _mode and _mode != '🎲 Randomizer' and _mode in EFFECT_MAP:
            # Specific effect chosen — use it plus random companions
            pinned = [(_mode, EFFECT_MAP[_mode])]
            others = [e for e in _EFFECTS if e[0] != _mode]
            extra  = random.sample(others, min(_ri(lo-1, hi-1), len(others)))
            chosen = pinned + extra
        else:
            chosen = random.sample(_EFFECTS, min(_ri(lo, hi), len(_EFFECTS)))
        for name, fn in chosen:
            try:
                img = fn(img)
                applied.append(name)
            except Exception:
                pass

    img.save(out_path, 'JPEG', quality=99)

    if save_metadata:
        try:
            save_nft_metadata(traits, out_path)
        except Exception:
            pass

    return img, traits, applied


# ═══════════════════════════════════════════════════════════════════════════════
#  STANDALONE TEST — run this file directly to preview NFT output
#  Usage: python trippygram_nft_upgraded.py --test [--n 6] [--out ./test_nfts]
# ═══════════════════════════════════════════════════════════════════════════════

def _nft_standalone_test(n=6, out_dir='./test_nfts', open_after=True):
    """Generate n NFT characters and save them to out_dir for quick preview."""
    import os, sys
    os.makedirs(out_dir, exist_ok=True)
    print(f'\n⬡  TrippyGram NFT Standalone Test — generating {n} characters…\n')
    for i in range(n):
        seed = _ri(0, 999999)
        out  = os.path.join(out_dir, f'nft_{i+1:03d}_seed{seed}.png')
        try:
            img, traits, applied = generate_nft_with_effects(
                out, intensity=3, seed=seed, apply_effects=True, save_metadata=True)
            rl = traits.get('_rarity_label','?')
            rs = traits.get('_rarity_score',0)
            sp = traits.get('Species','?')
            ey = traits.get('Eyes','?')
            hw = traits.get('Headwear','None')
            rt = traits.get('Rare Trait','None')
            au = traits.get('Aura Type','None')
            fa = traits.get('Faction','None')
            print(f'  #{i+1:02d}  {sp:12s}  Eyes:{ey:16s}  Wear:{hw:16s}  '
                  f'Rare:{rt:18s}  Aura:{au:14s}  Faction:{fa:18s}  '
                  f'[{rl}  score={rs}]  → {os.path.basename(out)}')
        except Exception as e:
            import traceback as _tb
            print(f'  #{i+1:02d} FAILED: {e}')
            _tb.print_exc()
    print(f'\n✓  Saved {n} NFTs to  {os.path.abspath(out_dir)}\n')
    if open_after:
        import subprocess, sys as _sys
        folder = os.path.abspath(out_dir)
        try:
            if _sys.platform == 'darwin':   subprocess.Popen(['open', folder])
            elif _sys.platform == 'win32':  subprocess.Popen(['explorer', folder])
            else:                           subprocess.Popen(['xdg-open', folder])
        except Exception: pass
