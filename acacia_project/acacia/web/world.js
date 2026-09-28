// ============================================================================
// ACACIA world renderer - environment
// Everything static is baked once into offscreen canvases (per region, per
// zoom bucket, per light tint) and drawn with drawImage; per frame only the
// animated parts run (sway via skew, water, fire, near grass).
// Simulation facts (trees, places, buildings, hut, fires) come from Python;
// far scenery (ranges, distant forest) is decorative backdrop.
// ============================================================================
"use strict";

const BIOMES = {
  meadow: { ground: "#4f7d3e", ground2: "#6b9448", soil: "#8a6b4a", far: ["#9fb3cc", "#7f96b5", "#5f7f73"], treeMix: { oak: 0.45, pine: 0.35, birch: 0.2 }, props: { rock: 0.16, shrub: 0.2, flowers: 0.34, tallgrass: 0.3 }, snowPeaks: true },
  forest: { ground: "#34512a", ground2: "#436033", soil: "#5e4a34", far: ["#8196a6", "#557060", "#2f4a38"], treeMix: { oak: 0.2, pine: 0.7, birch: 0.1 }, props: { log: 0.14, fern: 0.34, mushroom: 0.16, stump: 0.1, rock: 0.1, shrub: 0.16 }, snowPeaks: false, dense: true },
  town: { ground: "#5a7a44", ground2: "#6b8a4f", soil: "#8d8274", far: ["#a3b3c6", "#8497ad", "#6d7f76"], treeMix: { oak: 0.7, birch: 0.3 }, props: { barrel: 0.2, crate: 0.2, fence: 0.25, lamp: 0.2, shrub: 0.15 }, snowPeaks: true, cobbles: true },
};

const World = {
  stat: null, biome: BIOMES.meadow, biomeName: "meadow", seed: 1, width: 50,
  trees: [], props: [], puddles: [], grass: [], cache: new Map(), ppmKey: 0, tintKey: "",
  lights: [],                                                  // light sources this frame (for Fx)

  build(stat) {
    this.stat = stat; this.biomeName = stat.biome || "meadow"; this.biome = BIOMES[this.biomeName] || BIOMES.meadow;
    this.seed = stat.seed || 1337; this.width = stat.region.width;
    const r = rng(this.seed), B = this.biome;
    const pick = mixd => { let u = r(), acc = 0; for (const k in mixd) { acc += mixd[k]; if (u <= acc) return k; } return Object.keys(mixd)[0]; };
    this.trees = stat.trees.map(x => ({ x, type: pick(B.treeMix), v: Math.floor(r() * 2), s: 0.85 + r() * 0.3, flip: r() < 0.5, ph: r() * 6 }));
    this.props = [];
    const avoid = [...stat.trees.map(x => [x, 1.2]), ...(stat.dests || []).filter(d => d.kind !== "habitat" && d.kind !== "path").map(d => [d.x, 2.5])];
    const clear = x => !avoid.some(([ax, w]) => Math.abs(ax - x) < w);
    for (let x = 1; x < this.width - 1; x += 1.6 + r() * 3.2) {
      if (!clear(x)) continue;
      const k = pick(B.props); if (k === "lamp" && !stat.town) continue;
      const low = k === "flowers" || k === "tallgrass" || k === "rock" || k === "mushroom";
      this.props.push({ x, k, v: Math.floor(r() * 3), s: (0.75 + r() * 0.5) * (low ? 1 : 1), back: !low || r() < 0.5 });
    }
    this.puddles = []; for (let x = 2; x < this.width - 2; x += 5 + r() * 9) this.puddles.push({ x, w: 0.6 + r() * 1.2, z: r() });
    this.grass = []; for (let x = 0; x < this.width; x += 0.22 + r() * 0.3) this.grass.push({ x, h: 0.18 + r() * 0.3, c: r(), f: r() < 0.06 ? Math.floor(r() * 4) + 1 : 0 });
    this.invalidate();
  },
  invalidate() { this.cache.clear(); this.ppmKey = 0; },
  cached(key, w, h, draw) {
    let c = this.cache.get(key);
    if (!c) { c = offscreen(w, h); const g = c.getContext("2d"); draw(g, c.width, c.height); this.cache.set(key, c); }
    return c;
  },
  // zoom bucket: sprites re-bake only when zoom changes by >15%
  bucketPpm() { return Math.pow(1.15, Math.round(Math.log(Cam.ppm) / Math.log(1.15))); },

  // ------------------------------------------------------------ sky
  skyColors(st) {
    const h = st.hour, w = st.weather || {}, cloud = w.cloud || 0.2, storm = w.storm || 0;
    let top, bot;
    if (h < 4.5 || h >= 21.5) { top = "#050913"; bot = "#141d35"; }
    else if (h < 6.5) { const k = (h - 4.5) / 2; top = mix("#141d35", "#5a86c0", k); bot = mix("#2e2a46", "#f4c7a0", k); }
    else if (h < 9) { const k = (h - 6.5) / 2.5; top = mix("#5a86c0", "#4c8bd0", k); bot = mix("#f4c7a0", "#cfe3f2", k); }
    else if (h < 17) { top = "#4c8bd0"; bot = "#cfe3f2"; }
    else if (h < 19.5) { const k = (h - 17) / 2.5; top = mix("#4c8bd0", "#3d5d99", k); bot = mix("#cfe3f2", "#f2a36a", k); }
    else { const k = (h - 19.5) / 2; top = mix("#3d5d99", "#050913", k); bot = mix("#f2a36a", "#141d35", k); }
    const grey = clamp(cloud * 0.55 + storm * 0.45, 0, 0.85), gl = clamp(st.light + 0.25, 0.08, 1);
    return [mix(top, shade("#64707f", gl), grey), mix(bot, shade("#8e98a4", gl), grey)];
  },
  tint(st) {                                                    // a coarse light tint for baked layers
    const h = st.hour, w = st.weather || {};
    const tod = h < 5 || h >= 21 ? "night" : h < 7.5 ? "dawn" : h >= 18 ? "dusk" : "day";
    const wx = (w.storm || 0) > 0.4 ? "storm" : (w.cloud || 0) > 0.65 ? "grey" : "clear";
    return `${tod}|${wx}|${st.snow ? "snow" : ""}`;
  },
  hazeColor(st) { return this.skyColors(st)[1]; },
  drawSky(st, t) {
    const [top, bot] = this.skyColors(st);
    const g = ctx.createLinearGradient(0, 0, 0, Cam.gy); g.addColorStop(0, top); g.addColorStop(1, bot);
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    if (st.light < 0.45) {                                      // stars: one cached image, twinkle by alpha
      const stars = this.cached("stars|" + W + "x" + H, W, H * 0.6, (g2, w, h) => { const r = rng(7); g2.fillStyle = "#e8eefc"; for (let i = 0; i < 220; i++) { const s = r() < 0.9 ? 1 : 2; g2.globalAlpha = 0.3 + r() * 0.7; g2.fillRect(r() * w, r() * h, s, s); } });
      ctx.globalAlpha = clamp((0.45 - st.light) * 2.2, 0, 1) * (1 - ((st.weather || {}).cloud || 0) * 0.8) * (0.85 + 0.15 * Math.sin(t * 1.3));
      ctx.drawImage(stars, 0, 0, W, H * 0.6); ctx.globalAlpha = 1;
    }
    const h = st.hour, night = h < 5.5 || h >= 20.5;
    const f = night ? ((h + 24 - 20.5) % 24) / 9 : clamp((h - 5.5) / 15, 0, 1);
    const bx = W * (0.08 + 0.84 * f) - Cam.x * 0.6, by = Cam.gy * (0.66 - 0.56 * Math.sin(f * Math.PI));
    const r = Math.max(14, H * 0.03), cov = (st.weather || {}).cloud || 0.2, col = night ? "#cfd9ff" : (h < 8 || h > 17.5 ? "#ffd29a" : "#fff4d6");
    const gl = ctx.createRadialGradient(bx, by, r * 0.4, bx, by, r * 7);
    gl.addColorStop(0, rgba(col, (night ? 0.3 : 0.6) * (1 - cov * 0.7))); gl.addColorStop(1, rgba(col, 0));
    ctx.fillStyle = gl; ctx.fillRect(bx - r * 7, by - r * 7, r * 14, r * 14);
    ctx.globalAlpha = 1 - cov * 0.75; ctx.fillStyle = night ? "#e6ebf8" : shade(col, 1.02); ctx.beginPath(); ctx.arc(bx, by, r, 0, TAU); ctx.fill();
    if (night) { ctx.fillStyle = rgba("#9aa6c8", 0.35); ctx.beginPath(); ctx.arc(bx - r * 0.3, by - r * 0.2, r * 0.25, 0, TAU); ctx.arc(bx + r * 0.3, by + r * 0.25, r * 0.18, 0, TAU); ctx.fill(); }
    ctx.globalAlpha = 1;
    Fx.sun = { x: bx, y: by, night, elev: Math.sin(f * Math.PI) };
  },
  cloudSprite(i, tint) {
    return this.cached(`cloud|${i}|${tint}`, 420, 170, (g, w, h) => {
      const r = rng(1000 + i * 17), storm = tint.includes("storm"), grey = tint.includes("grey");
      const tod = tint.split("|")[0];
      const lit = tod === "night" ? "#6d7894" : tod === "dawn" ? "#ffd7c0" : tod === "dusk" ? "#ffc39a" : "#ffffff";
      const body = storm ? "#6e7684" : grey ? "#a9b0ba" : tod === "night" ? "#39425a" : "#e9eef5";
      for (let k = 0; k < 11; k++) {
        const px = w * (0.15 + r() * 0.7), py = h * (0.45 + r() * 0.25), pr = h * (0.18 + r() * 0.22);
        const gg = g.createRadialGradient(px, py - pr * 0.3, pr * 0.1, px, py, pr);
        gg.addColorStop(0, rgba(mix(body, lit, 0.55), 0.95)); gg.addColorStop(0.6, rgba(body, 0.8)); gg.addColorStop(1, rgba(body, 0));
        g.fillStyle = gg; g.fillRect(px - pr, py - pr, pr * 2, pr * 2);
      }
    });
  },
  drawClouds(st, t, tint) {
    const w = st.weather || {}, cover = clamp(w.cloud || 0.25, 0.05, 1), n = Math.round(1 + cover * 7);
    const drift = t * (5 + 20 * (w.wind || 0.3)) * ((w.wind_dir || 1) >= 0 ? 1 : -1), span = W + 900;
    for (let i = 0; i < n; i++) {
      const r = rng(50 + i), s = (0.8 + r() * 0.9) * H / 900, cy = Cam.gy * (0.08 + r() * 0.3);
      const cx = (((r() * span + drift * (0.6 + r() * 0.6) - Cam.x * Cam.ppm * 0.05) % span) + span) % span - 450;
      ctx.globalAlpha = 0.55 + 0.45 * cover; ctx.drawImage(this.cloudSprite(i % 6, tint), cx, cy, 420 * s, 170 * s);
    }
    ctx.globalAlpha = 1;
  },

  // ------------------------------------------------------------ far + mid layers (baked)
  layerCanvas(i, tint, st) {
    const B = this.biome, base = Cam.basePpm, par = [0.1, 0.22, 0.42][i];
    const pxW = Math.ceil(W + this.width * base * par + 200), hgt = Math.ceil(Cam.gy);
    return this.cached(`layer|${i}|${tint}|${pxW}|${hgt}|${this.biomeName}`, pxW, hgt, (g, w, h) => {
      const nz = noise1(this.seed + i * 101), nz2 = noise1(this.seed * 7 + i), k = base * [0.05, 0.07, 0.1][i];
      const haze = this.hazeColor(st), tod = tint.split("|")[0];
      let col = mix(B.far[i], haze, [0.55, 0.35, 0.15][i]);
      if (tod === "night") col = mix(col, "#0d1426", 0.6); else if (tod === "dusk" || tod === "dawn") col = mix(col, "#b98c86", 0.18);
      const amp = [60, 26, 9][i] * k, baseH = [28, 11, 4][i] * k, pts = [];
      for (let x = 0; x <= w; x += 4) {
        const xm = x / k;
        let y = baseH + amp * (0.62 * nz(xm / (i === 0 ? 30 : 16)) + 0.38 * nz2(xm / (i === 0 ? 8 : 5)));
        if (i === 0 && !B.dense) y += amp * 0.35 * Math.pow(Math.max(0, nz(xm / 55 + 3) - 0.45), 2) * 4;   // a few real peaks
        if (B.dense) y *= i === 0 ? 0.55 : 0.8;
        pts.push([x, h - y]);
      }
      const grad = g.createLinearGradient(0, h - baseH - amp * 1.4, 0, h);
      grad.addColorStop(0, shade(col, 1.1)); grad.addColorStop(1, shade(col, 0.8));
      g.fillStyle = grad; g.beginPath(); g.moveTo(0, h); for (const [x, y] of pts) g.lineTo(x, y); g.lineTo(w, h); g.closePath(); g.fill();
      if (i === 0) {                                             // lit faces + snow on the high ridges
        if (B.snowPeaks) {
          g.fillStyle = mix("#f3f6fb", col, tod === "night" ? 0.6 : 0.15);
          for (let j = 2; j < pts.length - 2; j++) {
            const y = pts[j][1];
            if (h - y > baseH + amp * 0.72 && y <= pts[j - 1][1] && y <= pts[j + 1][1]) {
              const hw = 16 + (h - y - baseH - amp * 0.72) * 0.8;
              g.beginPath(); g.moveTo(pts[j][0] - hw, y + hw * 0.55); g.lineTo(pts[j][0], y); g.lineTo(pts[j][0] + hw, y + hw * 0.55);
              g.lineTo(pts[j][0] + hw * 0.4, y + hw * 0.35); g.lineTo(pts[j][0], y + hw * 0.6); g.lineTo(pts[j][0] - hw * 0.4, y + hw * 0.38); g.fill();
            }
          }
        }
      }
      if (i >= 1) {                                              // forest on the hills: a textured treeline
        const r = rng(this.seed + i * 31), dense = B.dense ? 1 : this.biomeName === "town" ? 0.35 : 0.6;
        const tc = shade(col, i === 1 ? 0.8 : 0.7);
        for (let j = 0; j < pts.length; j += 1) {
          if (r() > dense * (i === 2 ? 0.75 : 0.5)) continue;
          const [x, y] = pts[j], th = (i === 1 ? 0.9 : 1.6) * k * (0.6 + r() * 0.8);
          g.fillStyle = shade(tc, 0.9 + r() * 0.2);
          if (r() < (B.dense ? 0.8 : 0.5)) { g.beginPath(); g.moveTo(x - th * 0.28, y + 2); g.lineTo(x, y - th); g.lineTo(x + th * 0.28, y + 2); g.fill(); }
          else { g.beginPath(); g.arc(x, y - th * 0.45, th * 0.4, 0, TAU); g.fill(); }
        }
        if (B.dense && i === 2) {                                // forest: a dense wall of pines, two depths
          for (const [row, cmul, hmul] of [[0, 0.62, 1.0], [1, 0.45, 1.25]]) {
            for (let x = -20; x < w + 20; x += k * (0.9 + r() * 0.8)) {
              const th = k * (6 + r() * 5) * hmul * 0.5, bx = x, by = h - baseH * (row ? 0.2 : 0.8), cw = th * 0.24;
              g.fillStyle = shade(tc, cmul * (0.9 + r() * 0.2));
              g.fillRect(bx - cw * 0.06, by - th * 0.3, cw * 0.12, th * 0.3);
              g.beginPath(); g.moveTo(bx - cw, by - th * 0.18);
              for (let s2 = 0; s2 < 4; s2++) { const yy = by - th * (0.18 + s2 * 0.2); g.lineTo(bx - cw * (1 - s2 * 0.22), yy); g.lineTo(bx - cw * (0.6 - s2 * 0.12), yy - th * 0.05); }
              g.lineTo(bx, by - th); for (let s2 = 3; s2 >= 0; s2--) { const yy = by - th * (0.18 + s2 * 0.2); g.lineTo(bx + cw * (0.6 - s2 * 0.12), yy - th * 0.05); g.lineTo(bx + cw * (1 - s2 * 0.22), yy); }
              g.closePath(); g.fill();
            }
          }
          g.fillStyle = shade(tc, 0.4); g.fillRect(0, h - baseH * 0.2, w, baseH * 0.2 + 2);
        }
        if (this.biomeName === "town" && i === 2) {             // distant rooftops
          for (let j = 0; j < 7; j++) { const x = w * (0.3 + j * 0.05) + r() * 30, y = h - baseH - amp * 0.4, u = k * 0.9; g.fillStyle = shade(col, 0.75); g.fillRect(x, y - 1.4 * u, 3 * u, 1.4 * u); g.beginPath(); g.moveTo(x - 0.3 * u, y - 1.4 * u); g.lineTo(x + 1.5 * u, y - 2.5 * u); g.lineTo(x + 3.3 * u, y - 1.4 * u); g.fill(); }
        }
      }
    });
  },
  drawLayers(st, tint) {
    for (let i = 0; i < 3; i++) {
      const par = [0.1, 0.22, 0.42][i], img = this.layerCanvas(i, tint, st);
      const zk = 1 + (Cam.zoom - 1) * par * 0.6;                 // distant layers barely scale with zoom
      const x0 = -Cam.x * Cam.basePpm * par * zk - 100 * zk;
      const w = img.width * zk, h = img.height * zk;
      ctx.drawImage(img, x0, Cam.gy - h + (i === 2 ? 2 : 0) - Cam.ppm * 0.9 * (i === 2 ? 1 : 0.7), w, h);
    }
    const haze = this.hazeColor(st), fog = (st.weather || {}).fog || 0;   // aerial perspective between layers
    const hg = ctx.createLinearGradient(0, Cam.gy - Cam.ppm * 5, 0, Cam.gy - Cam.ppm * 0.6);
    hg.addColorStop(0, rgba(haze, 0)); hg.addColorStop(1, rgba(haze, 0.22 + fog * 0.5));
    ctx.fillStyle = hg; ctx.fillRect(0, Cam.gy - Cam.ppm * 5, W, Cam.ppm * 4.4);
  },

  // ------------------------------------------------------------ ground
  groundPattern(tint, st) {
    const B = this.biome, snow = !!st.snow;
    return this.cached(`gpat|${this.biomeName}|${snow}`, 256, 256, (g, w, h) => {
      const r = rng(this.seed + 3);
      g.fillStyle = snow ? "#dfe6ee" : B.ground; g.fillRect(0, 0, w, h);
      for (let i = 0; i < 70; i++) { g.fillStyle = rgba(snow ? "#c9d3de" : (r() < 0.5 ? B.ground2 : shade(B.ground, 0.8)), 0.35); g.beginPath(); g.ellipse(r() * w, r() * h, 10 + r() * 30, 4 + r() * 10, 0, 0, TAU); g.fill(); }
      if (!snow) for (let i = 0; i < 1400; i++) {
        const x = r() * w, y = r() * h, l = 2 + r() * 6;
        g.strokeStyle = r() < 0.5 ? shade(B.ground, 0.8) : shade(B.ground2, 1.1); g.lineWidth = 1;
        g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - 0.5) * 2, y - l); g.stroke();
      }
      if (this.biomeName === "forest" && !snow) for (let i = 0; i < 160; i++) { g.fillStyle = ["#7a5a2e", "#8a6a34", "#5e4a2a", "#9a7a3e"][Math.floor(r() * 4)]; g.beginPath(); g.ellipse(r() * w, r() * h, 2 + r() * 3, 1 + r() * 2, r() * 3, 0, TAU); g.fill(); }
    });
  },
  soilPattern(st) {
    const B = this.biome, cob = !!B.cobbles;
    return this.cached(`spat|${this.biomeName}|${!!st.snow}`, 128, 64, (g, w, h) => {
      const r = rng(this.seed + 9);
      g.fillStyle = st.snow ? "#e6ebf1" : B.soil; g.fillRect(0, 0, w, h);
      if (cob && !st.snow) { for (let y = 0; y < h; y += 10) for (let x = (y / 10) % 2 * 7; x < w; x += 14) { g.fillStyle = shade(B.soil, 0.85 + r() * 0.3); g.beginPath(); g.ellipse(x + 6, y + 5, 6, 4, 0, 0, TAU); g.fill(); } }
      else for (let i = 0; i < 260; i++) { g.fillStyle = rgba(r() < 0.5 ? "#5a4632" : "#a88a64", st.snow ? 0.1 : 0.35); g.fillRect(r() * w, r() * h, 1 + r() * 2, 1 + r() * 2); }
    });
  },
  patternAt(pat, scale, offX) {
    if (pat && pat.setTransform && typeof DOMMatrix !== "undefined") pat.setTransform(new DOMMatrix().translateSelf(offX, 0).scaleSelf(scale));
    return pat;
  },
  drawGround(st, tint) {
    const gy = Cam.gy, p = Cam.ppm, w = st.weather || {}, wet = clamp(w.ground_wet != null ? w.ground_wet : (w.precip || 0), 0, 1);
    const top = gy - p * 0.9;
    const gctx = ctx.createPattern ? this.patternAt(ctx.createPattern(this.groundPattern(tint, st), "repeat"), Cam.zoom * 0.9, -Cam.x * p) : null;
    ctx.fillStyle = gctx || this.biome.ground; ctx.fillRect(0, top, W, H - top);
    const dg = ctx.createLinearGradient(0, top, 0, H);          // depth: darker far edge, deeper foreground
    dg.addColorStop(0, "rgba(20,30,20,.35)"); dg.addColorStop(0.25, "rgba(0,0,0,0)"); dg.addColorStop(1, "rgba(10,14,10,.35)");
    ctx.fillStyle = dg; ctx.fillRect(0, top, W, H - top);
    // the worn path she walks on
    const pw = p * 0.95, py = gy - pw * 0.42;
    const spat = this.patternAt(ctx.createPattern(this.soilPattern(st), "repeat"), Cam.zoom * 0.8, -Cam.x * p);
    ctx.save(); ctx.beginPath();
    ctx.moveTo(0, py + pw * 0.1);
    for (let x = 0; x <= W + 40; x += 40) { const xm = toWorldX(x); ctx.lineTo(x, py + Math.sin(xm * 0.7) * p * 0.04); }
    for (let x = W + 40; x >= 0; x -= 40) { const xm = toWorldX(x); ctx.lineTo(x, py + pw + Math.sin(xm * 0.9 + 2) * p * 0.05); }
    ctx.closePath(); ctx.clip();
    ctx.fillStyle = spat || this.biome.soil; ctx.fillRect(0, py - pw * 0.2, W, pw * 1.4);
    const eg = ctx.createLinearGradient(0, py, 0, py + pw);      // soft worn edges, wet darkening
    eg.addColorStop(0, "rgba(40,60,30,.45)"); eg.addColorStop(0.2, "rgba(0,0,0,0)"); eg.addColorStop(0.8, "rgba(0,0,0,0)"); eg.addColorStop(1, "rgba(40,60,30,.45)");
    ctx.fillStyle = eg; ctx.fillRect(0, py, W, pw);
    if (wet > 0.05) {
      ctx.fillStyle = `rgba(25,20,18,${0.28 * wet})`; ctx.fillRect(0, py, W, pw);
      const sky = this.skyColors(st)[1];                          // wet sheen reflecting the sky
      ctx.fillStyle = rgba(sky, 0.16 * wet);
      for (let i = 0; i < 9; i++) { const xm = Math.floor(toWorldX(0)) + i * (W / p / 8), x = sx(xm - (xm % 3)); ctx.fillRect(x, py + pw * (0.3 + (i % 3) * 0.15), p * 1.6, Math.max(1, p * 0.025)); }
    }
    ctx.restore();
    // puddles when wet: reflect the sky, ripple when it rains
    if (wet > 0.3) {
      const sky = this.skyColors(st);
      for (const q of this.puddles) {
        if (!inView(q.x, 2)) continue;
        const x = sx(q.x), y = py + pw * (0.3 + q.z * 0.45), rw = q.w * p * 0.5 * clamp((wet - 0.3) * 2, 0, 1), rh = rw * 0.16;
        const pg = ctx.createLinearGradient(0, y - rh, 0, y + rh); pg.addColorStop(0, sky[0]); pg.addColorStop(1, sky[1]);
        ctx.fillStyle = pg; ctx.globalAlpha = 0.85; ctx.beginPath(); ctx.ellipse(x, y, rw, rh, 0, 0, TAU); ctx.fill(); ctx.globalAlpha = 1;
        if ((w.precip || 0) > 0.1) { ctx.strokeStyle = "rgba(230,240,255,.45)"; ctx.lineWidth = 1; for (let k = 0; k < 2; k++) { const ph = ((performance.now() / 1000) * 1.3 + q.x + k * 0.5) % 1; ctx.beginPath(); ctx.ellipse(x + (k - 0.5) * rw * 0.6, y, rw * 0.35 * ph, rh * 0.35 * ph, 0, 0, TAU); ctx.globalAlpha = 1 - ph; ctx.stroke(); } ctx.globalAlpha = 1; }
      }
    }
  },

  // ------------------------------------------------------------ trees (baked variants, skew sway)
  treeSprite(type, v, pb, tint) {
    const hM = type === "pine" ? 9.5 : type === "birch" ? 8.5 : 8.0, wM = type === "pine" ? 4.4 : type === "birch" ? 3.8 : 6.6;
    const w = Math.ceil(wM * pb), h = Math.ceil(hM * pb);
    return this.cached(`tree|${type}|${v}|${pb.toFixed(1)}|${tint}`, w, h, (g, W2, H2) => {
      const r = rng(900 + v * 13 + type.length * 7), cx = W2 / 2, base = H2, p = pb;
      const tod = tint.split("|")[0], night = tod === "night", snow = tint.includes("snow");
      const leaf = night ? ["#1b2a22", "#233527", "#2d4230"] : type === "pine" ? ["#1f3a26", "#2c5234", "#3f7042"] : type === "birch" ? ["#4d7a34", "#6a9a44", "#8cb85a"] : ["#2e5a28", "#447a34", "#6a9e46"];
      const bark = type === "birch" ? ["#d9d4c8", "#b8b0a2"] : ["#4a3424", "#6e4e34"];
      // trunk with a root flare and bark texture
      const tw = (type === "oak" ? 0.34 : 0.22) * p, th = H2 * (type === "pine" ? 0.35 : 0.55);
      const tg = g.createLinearGradient(cx - tw, 0, cx + tw, 0); tg.addColorStop(0, shade(bark[0], 0.7)); tg.addColorStop(0.55, bark[1]); tg.addColorStop(1, shade(bark[0], 0.85));
      g.fillStyle = tg; g.beginPath(); g.moveTo(cx - tw * 1.7, base); g.quadraticCurveTo(cx - tw, base - p * 0.3, cx - tw * 0.6, base - th); g.lineTo(cx + tw * 0.6, base - th); g.quadraticCurveTo(cx + tw, base - p * 0.3, cx + tw * 1.7, base); g.fill();
      g.strokeStyle = type === "birch" ? "#2a2622" : rgba("#20140c", 0.5); g.lineWidth = Math.max(1, p * 0.03);
      for (let i = 0; i < 9; i++) { const y = base - r() * th, x = cx + (r() - 0.5) * tw; g.beginPath(); g.moveTo(x, y); g.lineTo(x + (type === "birch" ? tw * 0.5 : 0), y - (type === "birch" ? 0 : p * 0.25)); g.stroke(); }
      if (type === "pine") {
        for (let i = 0; i < 7; i++) {                            // tiers of needles, darker underneath
          const f = i / 7, ty = base - H2 * (0.18 + f * 0.72), wd = W2 * (0.48 - f * 0.055), top = ty - H2 * 0.2;
          const gg = g.createLinearGradient(cx - wd, 0, cx + wd, 0); gg.addColorStop(0, leaf[0]); gg.addColorStop(0.6, leaf[1]); gg.addColorStop(1, leaf[2]);
          g.fillStyle = gg; g.beginPath(); g.moveTo(cx - wd, ty);
          for (let k = 0; k <= 8; k++) { const a = k / 8; g.lineTo(lerp(cx - wd, cx + wd, a), ty + (k % 2 ? p * 0.12 : -p * 0.02)); }
          g.quadraticCurveTo(cx + wd * 0.3, ty - H2 * 0.08, cx, top); g.quadraticCurveTo(cx - wd * 0.3, ty - H2 * 0.08, cx - wd, ty); g.fill();
          g.strokeStyle = rgba(leaf[2], 0.5); g.lineWidth = 1;
          for (let k = 0; k < 10; k++) { const x = cx + (r() - 0.5) * wd * 1.6, y = ty - r() * H2 * 0.12; g.beginPath(); g.moveTo(x, y); g.lineTo(x + (x > cx ? 1 : -1) * p * 0.2, y + p * 0.1); g.stroke(); }
          if (snow) { g.fillStyle = "rgba(240,244,250,.85)"; g.beginPath(); g.moveTo(cx - wd * 0.8, ty - p * 0.05); g.quadraticCurveTo(cx, ty - H2 * 0.06, cx + wd * 0.8, ty - p * 0.05); g.lineTo(cx + wd * 0.6, ty); g.lineTo(cx - wd * 0.6, ty); g.fill(); }
        }
      } else {
        // branches, then foliage clusters lit from the upper left
        g.strokeStyle = bark[0]; g.lineCap = "round";
        const crownY = base - th, crownH = H2 - th;
        for (let i = 0; i < 5; i++) { const a = -Math.PI / 2 + (i - 2) * 0.45; g.lineWidth = Math.max(1, tw * (0.7 - i % 2 * 0.2)); g.beginPath(); g.moveTo(cx, crownY + p * 0.2); g.quadraticCurveTo(cx + Math.cos(a) * W2 * 0.12, crownY - crownH * 0.2, cx + Math.cos(a) * W2 * 0.3, crownY + Math.sin(a) * crownH * 0.5); g.stroke(); }
        const blobs = [];
        for (let i = 0; i < (type === "oak" ? 16 : 11); i++) blobs.push([cx + (r() - 0.5) * W2 * 0.72, crownY - crownH * (0.15 + r() * 0.65), W2 * (type === "oak" ? 0.13 + r() * 0.08 : 0.1 + r() * 0.06)]);
        blobs.sort((a, b) => a[1] - b[1]);
        for (const [bx, by, br] of blobs) { g.fillStyle = leaf[0]; g.beginPath(); g.arc(bx + br * 0.1, by + br * 0.15, br, 0, TAU); g.fill(); }
        for (const [bx, by, br] of blobs) {
          const gg = g.createRadialGradient(bx - br * 0.4, by - br * 0.45, br * 0.1, bx, by, br);
          gg.addColorStop(0, leaf[2]); gg.addColorStop(0.65, leaf[1]); gg.addColorStop(1, leaf[0]);
          g.fillStyle = gg; g.beginPath(); g.arc(bx, by, br * 0.92, 0, TAU); g.fill();
          g.fillStyle = rgba(leaf[2], 0.55); for (let k = 0; k < 7; k++) { g.beginPath(); g.arc(bx + (r() - 0.6) * br, by + (r() - 0.7) * br, Math.max(1, p * 0.06), 0, TAU); g.fill(); }
        }
        if (snow) { g.fillStyle = "rgba(240,244,250,.8)"; for (const [bx, by, br] of blobs.slice(0, 6)) { g.beginPath(); g.ellipse(bx, by - br * 0.6, br * 0.7, br * 0.25, 0, Math.PI, 0); g.fill(); } }
      }
    });
  },
  drawTrees(st, t, tint) {
    const pb = this.bucketPpm(), w = st.weather || {}, wind = (w.wind || 0.2) * ((w.wind_dir || 1) >= 0 ? 1 : -1);
    for (const tr of this.trees) {
      if (!inView(tr.x, 6)) continue;
      const img = this.treeSprite(tr.type, tr.v, pb, tint), k = Cam.ppm / pb * tr.s;
      const iw = img.width * k, ih = img.height * k, x = sx(tr.x), y = Cam.gy - Cam.ppm * 0.62;   // trees stand just behind the path
      const sway = (Math.sin(t * 0.8 + tr.ph) * 0.6 + Math.sin(t * 1.9 + tr.ph * 2) * 0.25) * wind * 0.035;
      const sh = Fx.shadowDir();                                  // cast shadow across the ground
      ctx.fillStyle = `rgba(10,16,10,${0.22 * sh.a})`; ctx.beginPath(); ctx.ellipse(x + sh.dx * ih * 0.12, y + Cam.ppm * 0.1, iw * 0.35 + Math.abs(sh.dx) * ih * 0.12, Cam.ppm * 0.14, 0, 0, TAU); ctx.fill();
      ctx.save(); ctx.setTransform(DPR * (tr.flip ? -1 : 1), 0, DPR * sway * (tr.flip ? -1 : 1), DPR, DPR * x, DPR * y);
      ctx.drawImage(img, -iw / 2 - sway * ih * 0.0, -ih, iw, ih); ctx.restore();
    }
  },

  // ------------------------------------------------------------ props (baked variants)
  propSprite(k, v, pb, tint) {
    const size = { rock: [1.2, 0.7], shrub: [1.6, 1.1], flowers: [1.0, 0.45], tallgrass: [1.0, 0.7], log: [2.6, 0.6], fern: [1.3, 0.8], mushroom: [0.5, 0.35], stump: [0.8, 0.6], barrel: [0.7, 1.0], crate: [0.8, 0.8], fence: [2.4, 1.1], lamp: [0.5, 3.2] }[k] || [1, 1];
    const w = Math.ceil(size[0] * pb), h = Math.ceil(size[1] * pb);
    return this.cached(`prop|${k}|${v}|${pb.toFixed(1)}|${tint}`, w, h, (g, W2, H2) => {
      const r = rng(300 + v * 7 + k.length * 31), night = tint.startsWith("night"), p = pb;
      const nd = c => night ? mix(c, "#101826", 0.45) : c;
      if (k === "rock") {
        const pts = []; for (let i = 0; i <= 8; i++) { const a = Math.PI + (i / 8) * Math.PI; pts.push([W2 / 2 + Math.cos(a) * W2 * (0.38 + r() * 0.1), H2 + Math.sin(a) * H2 * (0.75 + r() * 0.25)]); }
        const gg = g.createLinearGradient(0, 0, W2, H2); gg.addColorStop(0, nd("#aaa59d")); gg.addColorStop(0.5, nd("#86817a")); gg.addColorStop(1, nd("#55514c"));
        g.fillStyle = gg; g.beginPath(); g.moveTo(pts[0][0], H2); for (const q of pts) g.lineTo(q[0], q[1]); g.closePath(); g.fill();
        g.strokeStyle = rgba("#2e2b28", 0.45); g.lineWidth = 1; g.beginPath(); g.moveTo(W2 * 0.4, H2 * 0.35); g.lineTo(W2 * 0.5, H2 * 0.7); g.lineTo(W2 * 0.45, H2); g.stroke();
        g.fillStyle = rgba("#6f8a4a", 0.6); g.beginPath(); g.ellipse(W2 * 0.35, H2 * 0.3, W2 * 0.12, H2 * 0.06, 0, 0, TAU); g.fill();   // moss
      } else if (k === "shrub" || k === "fern") {
        const cols = k === "fern" ? [nd("#2f5a2a"), nd("#4c8a3a"), nd("#6aaa4a")] : [nd("#284a24"), nd("#3d6a30"), nd("#5c8e42")];
        if (k === "fern") { g.lineCap = "round"; for (let i = 0; i < 9; i++) { const a = -Math.PI / 2 + (i - 4) * 0.28, L = H2 * (0.7 + r() * 0.3); g.strokeStyle = cols[i % 3]; g.lineWidth = Math.max(1, p * 0.04); g.beginPath(); g.moveTo(W2 / 2, H2); g.quadraticCurveTo(W2 / 2 + Math.cos(a) * L * 0.5, H2 + Math.sin(a) * L * 0.8, W2 / 2 + Math.cos(a) * L, H2 + Math.sin(a) * L * 0.7); g.stroke(); for (let s = 1; s < 8; s++) { const tt = s / 8, bx = W2 / 2 + Math.cos(a) * L * tt, by = H2 + Math.sin(a) * L * 0.75 * tt; g.beginPath(); g.moveTo(bx, by); g.lineTo(bx + p * 0.07, by + p * 0.05); g.moveTo(bx, by); g.lineTo(bx - p * 0.07, by + p * 0.05); g.stroke(); } } }
        else { for (let i = 0; i < 9; i++) { const bx = W2 * (0.2 + r() * 0.6), by = H2 * (0.4 + r() * 0.45), br = W2 * (0.14 + r() * 0.1); const gg = g.createRadialGradient(bx - br * 0.3, by - br * 0.4, 1, bx, by, br); gg.addColorStop(0, cols[2]); gg.addColorStop(0.7, cols[1]); gg.addColorStop(1, cols[0]); g.fillStyle = gg; g.beginPath(); g.arc(bx, by, br, 0, TAU); g.fill(); } if (v === 0) { g.fillStyle = nd("#c9406a"); for (let i = 0; i < 6; i++) { g.beginPath(); g.arc(W2 * (0.25 + r() * 0.5), H2 * (0.35 + r() * 0.4), Math.max(1, p * 0.04), 0, TAU); g.fill(); } } }
      } else if (k === "flowers" || k === "tallgrass") {
        g.lineCap = "round";
        for (let i = 0; i < 24; i++) { const x = W2 * r(), hh = H2 * (0.4 + r() * 0.6); g.strokeStyle = nd(r() < 0.5 ? "#5a8a3c" : "#78a24a"); g.lineWidth = Math.max(1, p * 0.02); g.beginPath(); g.moveTo(x, H2); g.quadraticCurveTo(x + (r() - 0.5) * W2 * 0.1, H2 - hh * 0.6, x + (r() - 0.5) * W2 * 0.15, H2 - hh); g.stroke(); }
        if (k === "flowers") { const pal = ["#f2e27a", "#e7a3c8", "#b9a6f0", "#ffffff", "#f29a6a"]; for (let i = 0; i < 12; i++) { g.fillStyle = nd(pal[Math.floor(r() * 5)]); g.beginPath(); g.arc(W2 * r(), H2 * (0.1 + r() * 0.5), Math.max(1.2, p * 0.035), 0, TAU); g.fill(); } }
        else { g.fillStyle = nd("#b8a868"); for (let i = 0; i < 8; i++) { g.beginPath(); g.ellipse(W2 * r(), H2 * (0.05 + r() * 0.2), Math.max(1, p * 0.02), Math.max(1.5, p * 0.06), 0, 0, TAU); g.fill(); } }
      } else if (k === "log") {
        const gg = g.createLinearGradient(0, H2 * 0.2, 0, H2); gg.addColorStop(0, nd("#7a5a3a")); gg.addColorStop(1, nd("#3e2a1a"));
        g.fillStyle = gg; g.beginPath(); g.ellipse(W2 * 0.5, H2 * 0.6, W2 * 0.46, H2 * 0.38, 0, 0, TAU); g.fill();
        g.fillStyle = nd("#b08a5a"); g.beginPath(); g.ellipse(W2 * 0.93, H2 * 0.6, W2 * 0.05, H2 * 0.36, 0, 0, TAU); g.fill();
        g.strokeStyle = nd("#8a6a44"); g.lineWidth = 1; g.beginPath(); g.ellipse(W2 * 0.93, H2 * 0.6, W2 * 0.025, H2 * 0.2, 0, 0, TAU); g.stroke();
        g.fillStyle = rgba("#5f8a3a", 0.7); g.beginPath(); g.ellipse(W2 * 0.35, H2 * 0.3, W2 * 0.18, H2 * 0.1, 0, 0, TAU); g.fill();
      } else if (k === "mushroom") {
        for (let i = 0; i < 3; i++) { const x = W2 * (0.25 + i * 0.25), hh = H2 * (0.5 + r() * 0.4), cr = W2 * (0.12 + r() * 0.06); g.fillStyle = nd("#efe6d6"); g.fillRect(x - cr * 0.25, H2 - hh, cr * 0.5, hh); g.fillStyle = nd(v === 1 ? "#c23a2a" : "#b48a5a"); g.beginPath(); g.ellipse(x, H2 - hh, cr, cr * 0.6, 0, Math.PI, 0); g.fill(); if (v === 1) { g.fillStyle = "#fff"; g.beginPath(); g.arc(x - cr * 0.3, H2 - hh - cr * 0.3, Math.max(1, cr * 0.12), 0, TAU); g.fill(); } }
      } else if (k === "stump") {
        g.fillStyle = nd("#5e4430"); g.fillRect(W2 * 0.2, H2 * 0.3, W2 * 0.6, H2 * 0.7); g.fillStyle = nd("#a8845a"); g.beginPath(); g.ellipse(W2 * 0.5, H2 * 0.3, W2 * 0.3, H2 * 0.12, 0, 0, TAU); g.fill();
      } else if (k === "barrel") {
        const gg = g.createLinearGradient(0, 0, W2, 0); gg.addColorStop(0, nd("#5a3e26")); gg.addColorStop(0.5, nd("#8a6440")); gg.addColorStop(1, nd("#4a3220"));
        g.fillStyle = gg; g.beginPath(); g.ellipse(W2 / 2, H2 / 2, W2 * 0.45, H2 * 0.5, 0, 0, TAU); g.fill(); g.fillStyle = nd("#3a3a3a"); g.fillRect(W2 * 0.06, H2 * 0.22, W2 * 0.88, H2 * 0.06); g.fillRect(W2 * 0.06, H2 * 0.72, W2 * 0.88, H2 * 0.06);
      } else if (k === "crate") {
        g.fillStyle = nd("#9a7a4e"); g.fillRect(0, 0, W2, H2); g.strokeStyle = nd("#6a5232"); g.lineWidth = Math.max(1, p * 0.05); g.strokeRect(1, 1, W2 - 2, H2 - 2); g.beginPath(); g.moveTo(0, 0); g.lineTo(W2, H2); g.stroke();
      } else if (k === "fence") {
        g.fillStyle = nd("#7a5e40"); for (let i = 0; i < 4; i++) g.fillRect(W2 * (0.05 + i * 0.3), H2 * 0.1, W2 * 0.05, H2 * 0.9); g.fillRect(0, H2 * 0.3, W2, H2 * 0.08); g.fillRect(0, H2 * 0.62, W2, H2 * 0.08);
      } else if (k === "lamp") {
        g.fillStyle = nd("#2c2a28"); g.fillRect(W2 * 0.44, H2 * 0.15, W2 * 0.12, H2 * 0.85); g.fillRect(W2 * 0.25, H2 * 0.12, W2 * 0.5, H2 * 0.05);
        g.fillStyle = night ? "#ffd27a" : "#cfd6dc"; g.fillRect(W2 * 0.3, H2 * 0.02, W2 * 0.4, H2 * 0.1);
      }
    });
  },
  drawProps(st, tint, back) {
    const pb = this.bucketPpm(), night = st.light < 0.45;
    for (const q of this.props) {
      if (q.back !== back || !inView(q.x, 3)) continue;
      const img = this.propSprite(q.k, q.v, pb, tint), k = Cam.ppm / pb * q.s;
      const fk = back ? 1 : 0.7, iw = img.width * k * fk, ih = img.height * k * fk, x = sx(q.x), y = Cam.gy - (back ? Cam.ppm * 0.55 : -Cam.ppm * 0.95);
      if (q.k !== "flowers" && q.k !== "tallgrass") { ctx.fillStyle = "rgba(10,14,10,.25)"; ctx.beginPath(); ctx.ellipse(x, y, iw * 0.45, Math.max(1.5, Cam.ppm * 0.06), 0, 0, TAU); ctx.fill(); }
      ctx.drawImage(img, x - iw / 2, y - ih, iw, ih);
      if (q.k === "lamp" && night) this.lights.push({ x: q.x, y: 3.0 * q.s, r: 6, col: "#ffc86a", a: 0.85 });
    }
  },

  // ------------------------------------------------------------ town, hut, places, fires
  houseSprite(v, wM, hM, roof, alive, pb, tint, sign) {
    const w = Math.ceil((wM + 1.2) * pb), h = Math.ceil((hM + wM * 0.55 + 1.2) * pb);
    return this.cached(`house|${v}|${wM}|${hM}|${roof}|${alive}|${pb.toFixed(1)}|${tint}|${sign}`, w, h, (g, W2, H2) => {
      const p = pb, bw = wM * p, bh = hM * p, x0 = (W2 - bw) / 2, y0 = H2 - bh, night = tint.startsWith("night");
      const nd = c => night ? mix(c, "#101826", 0.45) : c, r = rng(v * 17 + 5);
      if (!alive) { g.fillStyle = nd("#5a524a"); g.beginPath(); g.moveTo(x0, H2); g.lineTo(x0, y0 + bh * 0.4); g.lineTo(x0 + bw * 0.3, y0 + bh * 0.2); g.lineTo(x0 + bw * 0.6, y0 + bh * 0.5); g.lineTo(x0 + bw, y0 + bh * 0.35); g.lineTo(x0 + bw, H2); g.fill(); return; }
      const wall = [nd("#d8c8a8"), nd("#c9b48e")][v % 2];
      const gg = g.createLinearGradient(x0, 0, x0 + bw, 0); gg.addColorStop(0, shade(wall, 0.86)); gg.addColorStop(1, wall);
      g.fillStyle = gg; g.fillRect(x0, y0, bw, bh);
      g.strokeStyle = nd("#5a3e28"); g.lineWidth = Math.max(2, p * 0.14);             // timber frame
      g.strokeRect(x0, y0, bw, bh); for (let i = 1; i < 3; i++) { g.beginPath(); g.moveTo(x0 + bw * i / 3, y0); g.lineTo(x0 + bw * i / 3, H2); g.stroke(); }
      g.beginPath(); g.moveTo(x0, y0 + bh * 0.48); g.lineTo(x0 + bw, y0 + bh * 0.48); g.stroke();
      g.beginPath(); g.moveTo(x0, y0 + bh * 0.48); g.lineTo(x0 + bw / 3, y0); g.moveTo(x0 + bw, y0 + bh * 0.48); g.lineTo(x0 + bw * 2 / 3, y0); g.stroke();
      const rg = g.createLinearGradient(0, y0 - bw * 0.55, 0, y0); rg.addColorStop(0, shade(nd(roof), 1.15)); rg.addColorStop(1, shade(nd(roof), 0.8));
      g.fillStyle = rg; g.beginPath(); g.moveTo(x0 - p * 0.5, y0 + p * 0.1); g.lineTo(W2 / 2, y0 - bw * 0.5); g.lineTo(x0 + bw + p * 0.5, y0 + p * 0.1); g.fill();
      g.strokeStyle = rgba("#000000", 0.18); g.lineWidth = 1;                             // tile rows
      for (let i = 1; i < 7; i++) { const yy = y0 - bw * 0.5 * (1 - i / 7); const half = (bw / 2 + p * 0.5) * i / 7; g.beginPath(); g.moveTo(W2 / 2 - half, yy + p * 0.1 * i / 7); g.lineTo(W2 / 2 + half, yy + p * 0.1 * i / 7); g.stroke(); }
      g.fillStyle = nd("#6a5a52"); g.fillRect(x0 + bw * 0.7, y0 - bw * 0.42, p * 0.5, bw * 0.3);   // chimney
      g.fillStyle = nd("#3a2a1c"); g.fillRect(W2 / 2 - p * 0.5, H2 - p * 2.1, p * 1.0, p * 2.1); // door
      g.fillStyle = nd("#c9a86a"); g.beginPath(); g.arc(W2 / 2 + p * 0.3, H2 - p * 1.0, Math.max(1, p * 0.06), 0, TAU); g.fill();
      for (const wx of [x0 + bw * 0.12, x0 + bw * 0.7]) { g.fillStyle = night ? "#ffcf73" : nd("#415062"); g.fillRect(wx, y0 + bh * 0.58, p * 0.8, p * 0.75); g.strokeStyle = nd("#3a2a1c"); g.lineWidth = Math.max(1, p * 0.06); g.strokeRect(wx, y0 + bh * 0.58, p * 0.8, p * 0.75); g.beginPath(); g.moveTo(wx + p * 0.4, y0 + bh * 0.58); g.lineTo(wx + p * 0.4, y0 + bh * 0.58 + p * 0.75); g.stroke(); if (!night) { g.fillStyle = "rgba(255,255,255,.25)"; g.fillRect(wx + p * 0.05, y0 + bh * 0.6, p * 0.2, p * 0.3); } }
      if (sign) { g.fillStyle = nd("#6a4a2a"); g.fillRect(x0 - p * 0.9, y0 + bh * 0.2, p * 0.9, p * 0.08); g.fillStyle = nd("#c9a66b"); g.fillRect(x0 - p * 0.85, y0 + bh * 0.25, p * 0.8, p * 0.55); }
    });
  },
  drawTown(st, tint) {
    const T = S.stat && S.stat.town; if (!T) return;
    const pb = this.bucketPpm(), night = st.light < 0.45, y = Cam.gy - Cam.ppm * 0.62;
    const house = (x, wM, hM, roof, v, sign) => {
      if (!inView(x, wM)) return;
      const img = this.houseSprite(v, wM, hM, roof, T.alive, pb, tint, !!sign), k = Cam.ppm / pb;
      ctx.drawImage(img, sx(x) - img.width * k / 2, y - img.height * k, img.width * k, img.height * k);
      if (night && T.alive) { this.lights.push({ x: x - wM * 0.3, y: hM * 0.4, r: 4, col: "#ffc070", a: 0.7 }); this.lights.push({ x: x + wM * 0.28, y: hM * 0.4, r: 4, col: "#ffc070", a: 0.7 }); }
    };
    (T.houses || []).forEach((hx, i) => house(hx, 4.8, 3.8, ["#7a3a2a", "#5a4a3a", "#6a3048"][i % 3], i));
    if (T.tavern) house(T.tavern, 7, 4.6, "#5a4232", 7, true);
    if (T.workshop) {                                           // workshop: a house with an open lean-to and a workbench
      house(T.workshop, 5.4, 3.9, "#4e4238", 11, true);
      if (T.alive && inView(T.workshop + 3.6, 3)) { const X = sx(T.workshop + 3.4), p = Cam.ppm; ctx.fillStyle = "#5a3e28"; ctx.fillRect(X - 0.1 * p, y - 2.6 * p, 0.14 * p, 2.6 * p); ctx.fillStyle = "#6a4e32"; ctx.beginPath(); ctx.moveTo(X - 1.6 * p, y - 3.2 * p); ctx.lineTo(X + 0.3 * p, y - 2.6 * p); ctx.lineTo(X - 1.6 * p, y - 2.4 * p); ctx.fill(); ctx.fillStyle = "#7a5a3a"; ctx.fillRect(X - 1.4 * p, y - 0.9 * p, 1.3 * p, 0.12 * p); ctx.fillRect(X - 1.3 * p, y - 0.9 * p, 0.1 * p, 0.9 * p); ctx.fillRect(X - 0.25 * p, y - 0.9 * p, 0.1 * p, 0.9 * p); }
    }
    for (const fx0 of T.fields || []) {                         // fields: crop rows on the far side of the road
      if (!inView(fx0, 8)) continue; const p = Cam.ppm, X = sx(fx0), yb = Cam.gy - p * 0.7;
      ctx.fillStyle = T.alive ? "#7a6a3a" : "#5a5040"; ctx.fillRect(X - 5 * p, yb - 0.25 * p, 10 * p, 0.25 * p);
      if (T.alive) { ctx.strokeStyle = "#8aa04a"; ctx.lineWidth = Math.max(1, p * 0.04); ctx.beginPath(); for (let i = 0; i < 26; i++) { const cx = X - 4.8 * p + i * 0.38 * p; ctx.moveTo(cx, yb); ctx.lineTo(cx - 0.05 * p, yb - 0.55 * p); ctx.moveTo(cx, yb); ctx.lineTo(cx + 0.08 * p, yb - 0.45 * p); } ctx.stroke(); ctx.fillStyle = "#d9b84a"; for (let i = 0; i < 26; i++) { ctx.beginPath(); ctx.ellipse(X - 4.85 * p + i * 0.38 * p, yb - 0.58 * p, 0.04 * p, 0.1 * p, 0, 0, TAU); ctx.fill(); } }
    }
    if (T.hall) house(T.hall, 8, 5.2, "#7a2a3a", 8);
    if (T.shrine) { house(T.shrine, 4, 3.6, "#4a4a52", 9); if (T.alive && inView(T.shrine + 5, 8)) { for (let i = 0; i < Math.min(12, T.graves || 0); i++) { const gx = sx(T.shrine + 3.2 + i * 1.1), p = Cam.ppm; ctx.fillStyle = "#8a8a86"; ctx.beginPath(); ctx.moveTo(gx - 0.28 * p, y); ctx.lineTo(gx - 0.28 * p, y - 0.7 * p); ctx.quadraticCurveTo(gx, y - 1.0 * p, gx + 0.28 * p, y - 0.7 * p); ctx.lineTo(gx + 0.28 * p, y); ctx.fill(); } } }
    if (T.market && T.alive) for (const dx of [-4.2, 0, 4.2]) {
      const mx = T.market + dx; if (!inView(mx, 3)) continue; const X = sx(mx), p = Cam.ppm;
      ctx.fillStyle = "#6a4a2e"; ctx.fillRect(X - 1.5 * p, y - 1.1 * p, 3 * p, 1.1 * p); ctx.fillRect(X - 1.45 * p, y - 3.3 * p, 0.1 * p, 2.2 * p); ctx.fillRect(X + 1.35 * p, y - 3.3 * p, 0.1 * p, 2.2 * p);
      for (let i = 0; i < 6; i++) { ctx.fillStyle = i % 2 ? "#ece4d4" : (dx === 0 ? "#3a6ac2" : dx < 0 ? "#c24a3a" : "#3a9a5a"); ctx.beginPath(); ctx.moveTo(X - 1.7 * p + i * 0.57 * p, y - 3.4 * p); ctx.lineTo(X - 1.13 * p + i * 0.57 * p, y - 3.4 * p); ctx.lineTo(X - 1.1 * p + i * 0.57 * p, y - 2.85 * p); ctx.quadraticCurveTo(X - 1.4 * p + i * 0.57 * p, y - 2.7 * p, X - 1.67 * p + i * 0.57 * p, y - 2.85 * p); ctx.fill(); }
      ctx.fillStyle = "#b8392a"; for (let i = 0; i < 5; i++) { ctx.beginPath(); ctx.arc(X - 1.1 * p + i * 0.5 * p, y - 1.2 * p, 0.09 * p, 0, TAU); ctx.fill(); }
    }
    if (T.well && T.alive && inView(T.well, 2)) { const X = sx(T.well), p = Cam.ppm; ctx.fillStyle = "#7d7a74"; ctx.fillRect(X - 1.1 * p, y - 1.0 * p, 2.2 * p, 1.0 * p); ctx.strokeStyle = "#5a5650"; ctx.lineWidth = 1; for (let i = 1; i < 4; i++) { ctx.beginPath(); ctx.moveTo(X - 1.1 * p, y - i * 0.25 * p); ctx.lineTo(X + 1.1 * p, y - i * 0.25 * p); ctx.stroke(); } ctx.fillStyle = "#5a3a2a"; ctx.fillRect(X - 1.0 * p, y - 3.0 * p, 0.12 * p, 2.0 * p); ctx.fillRect(X + 0.88 * p, y - 3.0 * p, 0.12 * p, 2.0 * p); ctx.beginPath(); ctx.moveTo(X - 1.4 * p, y - 2.9 * p); ctx.lineTo(X, y - 3.7 * p); ctx.lineTo(X + 1.4 * p, y - 2.9 * p); ctx.fill(); }
    for (const gx of T.gate || []) if (inView(gx, 2) && T.alive) { const X = sx(gx), p = Cam.ppm; ctx.fillStyle = "#6b5a44"; ctx.fillRect(X - 1.2 * p, y - 6.5 * p, 0.35 * p, 6.5 * p); ctx.fillRect(X + 0.85 * p, y - 6.5 * p, 0.35 * p, 6.5 * p); ctx.fillRect(X - 1.6 * p, y - 6.9 * p, 3.2 * p, 0.5 * p); }
  },
  drawHome(st, tint) {
    const h = st.home; if (!h || !inView(h.x, 6)) return;
    const p = Cam.ppm, x = sx(h.x), y = Cam.gy - p * 0.62, night = st.light < 0.45, nd = c => night ? mix(c, "#101826", 0.35) : c;
    ctx.fillStyle = "rgba(10,14,10,.3)"; ctx.beginPath(); ctx.ellipse(x, y + p * 0.08, 3.1 * p, 0.2 * p, 0, 0, TAU); ctx.fill();
    if (h.stage === 1) {
      ctx.strokeStyle = nd("#6b4a30"); ctx.lineWidth = 0.14 * p; ctx.lineCap = "round";
      for (let i = 0; i < 6; i++) { ctx.beginPath(); ctx.moveTo(x - 2.2 * p + i * 0.45 * p, y); ctx.lineTo(x + 0.3 * p, y - 3 * p); ctx.stroke(); }
      ctx.fillStyle = nd("#8c7a4a"); ctx.beginPath(); ctx.moveTo(x - 2.6 * p, y); ctx.lineTo(x + 0.4 * p, y - 3.2 * p); ctx.lineTo(x + 0.9 * p, y - 2.9 * p); ctx.lineTo(x - 1.6 * p, y); ctx.globalAlpha = 0.6; ctx.fill(); ctx.globalAlpha = 1; ctx.lineCap = "butt";
      return;
    }
    const ww = 2.6 * p, wh = 2.6 * p;
    for (let i = 0; i < 8; i++) {                                 // log walls, each log rounded and lit
      const ly = y - wh + i * wh / 8, lg = ctx.createLinearGradient(0, ly, 0, ly + wh / 8);
      lg.addColorStop(0, nd("#9a7048")); lg.addColorStop(0.5, nd("#7a5634")); lg.addColorStop(1, nd("#4e3620"));
      ctx.fillStyle = lg; ctx.fillRect(x - ww, ly, ww * 2, wh / 8 + 1);
      ctx.fillStyle = nd("#b08a5a"); ctx.beginPath(); ctx.ellipse(x - ww - p * 0.05, ly + wh / 16, p * 0.1, wh / 16, 0, 0, TAU); ctx.ellipse(x + ww + p * 0.05, ly + wh / 16, p * 0.1, wh / 16, 0, 0, TAU); ctx.fill();
    }
    const worn = 1 - h.cond, rg = ctx.createLinearGradient(0, y - wh - 2.2 * p, 0, y - wh);
    rg.addColorStop(0, nd(mix("#c4a864", "#6a5638", worn))); rg.addColorStop(1, nd(mix("#86703e", "#3a2e20", worn)));
    ctx.fillStyle = rg; ctx.beginPath(); ctx.moveTo(x - ww - 0.6 * p, y - wh + 0.1 * p); ctx.lineTo(x, y - wh - 2.3 * p); ctx.lineTo(x + ww + 0.6 * p, y - wh + 0.1 * p); ctx.fill();
    ctx.strokeStyle = rgba("#3a2a14", 0.35); ctx.lineWidth = 1;   // thatch
    for (let i = 0; i < 26; i++) { const a = i / 25, bx = lerp(x - ww - 0.6 * p, x + ww + 0.6 * p, a); ctx.beginPath(); ctx.moveTo(bx, y - wh + 0.1 * p); ctx.lineTo(lerp(bx, x, 0.25), y - wh - 2.3 * p * (1 - Math.abs(a - 0.5) * 2) * 0.35); ctx.stroke(); }
    if (h.stage >= 3) {
      ctx.fillStyle = nd("#2e1f14"); ctx.fillRect(x - 0.55 * p, y - 1.95 * p, 1.1 * p, 1.95 * p);
      const wx = x + ww * 0.45, wy = y - wh * 0.72;
      ctx.fillStyle = night ? "#ffcf73" : nd("#3a4452"); ctx.fillRect(wx, wy, 0.8 * p, 0.7 * p);
      ctx.fillStyle = nd("#3e2a1a"); ctx.fillRect(wx + 0.37 * p, wy, 0.06 * p, 0.7 * p); ctx.fillRect(wx, wy + 0.32 * p, 0.8 * p, 0.06 * p);
      if (night) this.lights.push({ x: h.x + 2.0, y: 1.7, r: 4.5, col: "#ffc070", a: 0.8 });
    }
  },
  drawPOIs(st, t) {
    const p = Cam.ppm, y0 = Cam.gy - p * 0.62;
    for (const q of st.pois || []) {
      if (!inView(q.x, 5)) continue;
      const x = sx(q.x);
      if (q.kind === "food") {
        const r = rng(Math.floor(q.x * 100)), shr = this.propSprite("shrub", 1, this.bucketPpm(), this.tintKey), k = Cam.ppm / this.bucketPpm();
        for (let i = 0; i < 3; i++) { const bx = x + (i - 1) * 0.8 * p, s = 1.1 + r() * 0.4; ctx.drawImage(shr, bx - shr.width * k * s / 2, y0 - shr.height * k * s + p * 0.1, shr.width * k * s, shr.height * k * s); }
        if (q.available) { for (let i = 0; i < 22; i++) { const bx = x + (r() - 0.5) * 2.2 * p, by = y0 - (0.2 + r() * 1.0) * p; ctx.fillStyle = "#a8203e"; ctx.beginPath(); ctx.arc(bx, by, Math.max(1.3, 0.04 * p), 0, TAU); ctx.fill(); ctx.fillStyle = "rgba(255,255,255,.5)"; ctx.fillRect(bx - 0.012 * p, by - 0.02 * p, Math.max(1, 0.015 * p), Math.max(1, 0.015 * p)); } }
      } else if (q.kind === "water") {
        const sky = this.skyColors(st), yy = Cam.gy + p * 0.05, rw = 2.0 * p, rh = 0.32 * p;
        ctx.fillStyle = "#5a554e"; ctx.beginPath(); ctx.ellipse(x, yy, rw * 1.08, rh * 1.25, 0, 0, TAU); ctx.fill();
        const wg = ctx.createLinearGradient(0, yy - rh, 0, yy + rh); wg.addColorStop(0, sky[1]); wg.addColorStop(0.5, mix(sky[0], "#1f4d6d", 0.5)); wg.addColorStop(1, "#173a52");
        ctx.fillStyle = wg; ctx.beginPath(); ctx.ellipse(x, yy, rw, rh, 0, 0, TAU); ctx.fill();
        ctx.strokeStyle = "rgba(230,245,255,.55)"; ctx.lineWidth = 1;
        for (let i = 0; i < 3; i++) { const ph = (t * 0.45 + i / 3) % 1; ctx.globalAlpha = 1 - ph; ctx.beginPath(); ctx.ellipse(x + (i - 1) * 0.6 * p, yy, ph * 0.7 * p, ph * 0.11 * p, 0, 0, TAU); ctx.stroke(); }
        ctx.globalAlpha = 1; ctx.fillStyle = "rgba(255,255,255,.35)"; ctx.fillRect(x - rw * 0.5, yy - rh * 0.35, rw * 0.35, Math.max(1, p * 0.02));
        for (let i = 0; i < 6; i++) { ctx.strokeStyle = "#4a7a38"; ctx.lineWidth = Math.max(1, p * 0.03); ctx.beginPath(); ctx.moveTo(x - rw + i * 0.1 * p, yy - rh * 0.4); ctx.quadraticCurveTo(x - rw - 0.1 * p + i * 0.12 * p, yy - rh * 0.4 - 0.6 * p, x - rw + i * 0.15 * p, yy - rh * 0.4 - 1.0 * p); ctx.stroke(); }
      } else if (q.kind === "shelter" && !S.stat.town) {
        // a rock overhang: an irregular boulder with a dark hollow, lit from the sky
        const q2 = 0.75 * p, g = ctx.createLinearGradient(x - 2 * q2, y0 - 2.8 * q2, x + 2 * q2, y0); g.addColorStop(0, "#a8a39c"); g.addColorStop(0.5, "#7c7872"); g.addColorStop(1, "#4a4845");
        ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x - 2.2 * q2, y0); ctx.bezierCurveTo(x - 2.5 * q2, y0 - 1.6 * q2, x - 1.6 * q2, y0 - 2.8 * q2, x - 0.2 * q2, y0 - 2.9 * q2);
        ctx.bezierCurveTo(x + 1.1 * q2, y0 - 3.0 * q2, x + 2.2 * q2, y0 - 2.2 * q2, x + 2.5 * q2, y0 - 1.0 * q2); ctx.lineTo(x + 2.3 * q2, y0); ctx.closePath(); ctx.fill();
        ctx.strokeStyle = "rgba(40,36,32,.45)"; ctx.lineWidth = Math.max(1, q2 * 0.03); ctx.beginPath(); ctx.moveTo(x - 1.2 * q2, y0 - 2.6 * q2); ctx.lineTo(x - 0.6 * q2, y0 - 1.8 * q2); ctx.lineTo(x - 0.9 * q2, y0 - 1.2 * q2); ctx.moveTo(x + 1.4 * q2, y0 - 2.3 * q2); ctx.lineTo(x + 1.0 * q2, y0 - 1.6 * q2); ctx.stroke();
        const hg = ctx.createRadialGradient(x + 0.2 * q2, y0, 0, x + 0.2 * q2, y0, 1.3 * q2); hg.addColorStop(0, "#0e1012"); hg.addColorStop(1, "#2a2a2c");
        ctx.fillStyle = hg; ctx.beginPath(); ctx.ellipse(x + 0.2 * q2, y0, 1.2 * q2, 1.25 * q2, 0, Math.PI, 0); ctx.fill();
        ctx.fillStyle = rgba("#6f8a4a", 0.75); ctx.beginPath(); ctx.ellipse(x - 0.7 * q2, y0 - 2.75 * q2, 0.9 * q2, 0.2 * q2, -0.15, 0, TAU); ctx.fill();
      } else if (q.kind === "curio") {
        const pulse = 0.5 + 0.5 * Math.sin(t * 2);
        this.lights.push({ x: q.x, y: 0.4, r: 2.2, col: "#7ee0c8", a: 0.5 + 0.3 * pulse });
        ctx.fillStyle = "#8fe8d2"; ctx.beginPath(); ctx.moveTo(x - 0.14 * p, y0); ctx.lineTo(x - 0.06 * p, y0 - 0.5 * p); ctx.lineTo(x + 0.05 * p, y0 - 0.6 * p); ctx.lineTo(x + 0.15 * p, y0); ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,.6)"; ctx.beginPath(); ctx.moveTo(x - 0.06 * p, y0 - 0.1 * p); ctx.lineTo(x - 0.03 * p, y0 - 0.45 * p); ctx.lineTo(x, y0 - 0.1 * p); ctx.fill();
      }
    }
  },
  smoke: [], embers: [],
  drawFires(st, t, dt) {
    const p = Cam.ppm, w = st.weather || {}, wind = (w.wind || 0.2) * ((w.wind_dir || 1) >= 0 ? 1 : -1), y = Cam.gy - p * 0.1;
    for (const f of st.fires || []) {
      if (!inView(f.x, 5)) continue;
      const x = sx(f.x), I = f.lit ? f.intensity : 0;
      for (let i = 0; i < 9; i++) { const a = Math.PI * (i / 8); ctx.fillStyle = i % 2 ? "#6a6660" : "#56524c"; ctx.beginPath(); ctx.ellipse(x + Math.cos(a) * 0.45 * p, y - Math.sin(a) * 0.06 * p, 0.12 * p, 0.08 * p, 0, 0, TAU); ctx.fill(); }
      ctx.strokeStyle = "#3e2616"; ctx.lineWidth = 0.1 * p; ctx.lineCap = "round"; ctx.beginPath(); ctx.moveTo(x - 0.38 * p, y - 0.02 * p); ctx.lineTo(x + 0.32 * p, y - 0.16 * p); ctx.moveTo(x - 0.32 * p, y - 0.16 * p); ctx.lineTo(x + 0.38 * p, y - 0.02 * p); ctx.stroke(); ctx.lineCap = "butt";
      if (I > 0.02) {
        this.lights.push({ x: f.x, y: 0.5, r: 7 * I + 2, col: "#ff9a4a", a: 0.95 * I, flick: true });
        ctx.save(); ctx.globalCompositeOperation = "lighter";
        const gl = ctx.createRadialGradient(x, y - 0.3 * p, 0, x, y - 0.3 * p, 2.6 * p * I); gl.addColorStop(0, `rgba(255,150,60,${0.4 * I})`); gl.addColorStop(1, "rgba(255,120,40,0)");
        ctx.fillStyle = gl; ctx.fillRect(x - 2.6 * p, y - 3 * p, 5.2 * p, 3.2 * p);
        for (const [col, sc, sp] of [["#ff5a14", 1, 7], ["#ffa632", 0.75, 9], ["#fff0a0", 0.42, 12]]) {
          for (let k = -1; k <= 1; k++) {
            const fl = Math.sin(t * sp + k * 1.7 + f.x) * 0.06 * p, hh = (0.6 + 0.25 * Math.sin(t * sp * 0.7 + k)) * p * I * sc, ww = 0.17 * p * sc;
            ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(x + k * 0.14 * p - ww, y - 0.04 * p);
            ctx.quadraticCurveTo(x + k * 0.14 * p - ww * 0.8 + wind * hh * 0.2, y - hh * 0.6, x + k * 0.14 * p + fl + wind * hh * 0.45, y - hh);
            ctx.quadraticCurveTo(x + k * 0.14 * p + ww * 0.8 + wind * hh * 0.2, y - hh * 0.6, x + k * 0.14 * p + ww, y - 0.04 * p); ctx.fill();
          }
        }
        ctx.restore();
        if (Math.random() < dt * 5 * I && this.smoke.length < 60) this.smoke.push({ x: f.x, y: 1.0 * I, r: 0.15, a: 0.3, vx: wind * 0.5, vy: 0.5 });
        if (Math.random() < dt * 4 * I && this.embers.length < 40) this.embers.push({ x: f.x + (Math.random() - 0.5) * 0.3, y: 0.5, vx: (Math.random() - 0.5) * 0.3 + wind * 0.3, vy: 0.9 + Math.random(), life: 1.4 });
      } else { ctx.fillStyle = "#3a3632"; ctx.beginPath(); ctx.ellipse(x, y - 0.03 * p, 0.3 * p, 0.05 * p, 0, 0, TAU); ctx.fill(); }
    }
    for (const s of this.smoke) { s.x += s.vx * dt; s.y += s.vy * dt; s.r += 0.25 * dt; s.a -= 0.06 * dt; }
    this.smoke = this.smoke.filter(s => s.a > 0);
    for (const s of this.smoke) { if (!inView(s.x, 4)) continue; ctx.fillStyle = `rgba(160,160,165,${s.a})`; ctx.beginPath(); ctx.arc(sx(s.x), sy(s.y + 0.1), s.r * p, 0, TAU); ctx.fill(); }
    for (const e of this.embers) { e.x += e.vx * dt; e.y += e.vy * dt; e.life -= dt; }
    this.embers = this.embers.filter(e => e.life > 0);
    ctx.fillStyle = "#ffb050"; for (const e of this.embers) { ctx.globalAlpha = clamp(e.life, 0, 1); ctx.fillRect(sx(e.x), sy(e.y + 0.1), 2, 2); } ctx.globalAlpha = 1;
  },
  drawOfferings(st) {
    const p = Cam.ppm;
    for (const o of st.offerings || []) { if (!inView(o.x, 2)) continue; for (let k = 0; k < Math.min(6, o.amount * 2); k++) { ctx.fillStyle = o.kind === "berries" ? "#a8203e" : "#8a4a3a"; ctx.beginPath(); ctx.arc(sx(o.x) + (k - 2.5) * 0.05 * p, Cam.gy - 0.03 * p - (k % 2) * 0.04 * p, Math.max(1.2, 0.03 * p), 0, TAU); ctx.fill(); } }
  },

  // ------------------------------------------------------------ foreground grass (over feet)
  canopy(st, t) {                                               // forest roof: cached leaf mass along the top edge
    const img = this.cached(`canopy|${this.tintKey}|${W}`, W + 400, Math.ceil(H * 0.26), (g, w, h) => {
      const r = rng(this.seed + 77), night = this.tintKey.startsWith("night"), cols = night ? ["#0c140f", "#121c15", "#18241a"] : ["#16261a", "#1f3524", "#2b4a30"];
      for (let i = 0; i < 90; i++) { const x = r() * w, y = r() * h * 0.55, rr = h * (0.12 + r() * 0.22); g.fillStyle = cols[i % 3]; g.beginPath(); g.arc(x, y, rr, 0, TAU); g.fill(); }
      g.fillStyle = cols[0]; g.fillRect(0, 0, w, h * 0.18);
    });
    const off = ((Cam.x * Cam.ppm * 1.08) % 400 + 400) % 400, sway = Math.sin(t * 0.5) * 4;
    ctx.drawImage(img, -off + sway, -H * 0.03, img.width, img.height);
  },
  drawFront(st, t, dt) {
    const p = Cam.ppm, w = st.weather || {}, wind = (w.wind || 0.2) * ((w.wind_dir || 1) >= 0 ? 1 : -1), light = st.light;
    if (this.biome.dense) this.canopy(st, t);
    if (st.snow || this.biome.cobbles) { this.drawProps(st, this.tintKey, false); return; }
    const base = Cam.gy + p * 0.5, step = Cam.ppm < 60 ? 2 : 1;             // LOD: fewer blades when small
    const cols = [shade(this.biome.ground2, 0.9), shade(this.biome.ground2, 1.1), shade(this.biome.ground, 0.8)];
    for (let c = 0; c < 3; c++) {
      ctx.strokeStyle = cols[c]; ctx.lineWidth = Math.max(1, p * 0.018); ctx.beginPath();
      for (let i = c; i < this.grass.length; i += 3 * step) {
        const gb = this.grass[i]; if (!inView(gb.x, 1)) continue;
        const x = sx(gb.x), hh = gb.h * p, sw = (Math.sin(t * 1.6 + gb.x * 1.3) * 0.5 + 0.5) * wind * hh * 0.35;
        const yb = base + gb.c * p * 0.9;
        ctx.moveTo(x, yb); ctx.quadraticCurveTo(x + sw * 0.4, yb - hh * 0.6, x + sw, yb - hh);
      }
      ctx.stroke();
    }
    const pal = ["#f2e27a", "#e7a3c8", "#b9a6f0", "#ffffff"];
    for (const gb of this.grass) { if (!gb.f || !inView(gb.x, 1)) continue; const x = sx(gb.x) + (Math.sin(t * 1.6 + gb.x * 1.3) * 0.5 + 0.5) * wind * gb.h * p * 0.35, yb = base + gb.c * p * 0.9 - gb.h * p; ctx.fillStyle = pal[gb.f - 1]; ctx.beginPath(); ctx.arc(x, yb, Math.max(1.3, p * 0.03), 0, TAU); ctx.fill(); }
    this.drawProps(st, this.tintKey, false);
  },

  // ------------------------------------------------------------ the back pass
  drawBack(st, t, dt) {
    this.lights = [];
    const tint = this.tint(st); this.tintKey = tint;
    const pk = this.bucketPpm(); if (pk !== this.ppmKey) { for (const k of [...this.cache.keys()]) if (k.startsWith("tree|") || k.startsWith("prop|") || k.startsWith("house|")) { if (!k.includes("|" + pk.toFixed(1) + "|")) this.cache.delete(k); } this.ppmKey = pk; }
    if (this.cache.size > 260) this.cache.clear();              // bounded memory
    this.drawSky(st, t); this.drawClouds(st, t, tint); this.drawLayers(st, tint);
    this.drawGround(st, tint);
    this.drawProps(st, tint, true);
    this.drawTown(st, tint); this.drawTrees(st, t, tint); this.drawHome(st, tint);
    this.drawPOIs(st, t); this.drawOfferings(st); this.drawFires(st, t, dt);
  },
};
