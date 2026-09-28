// ============================================================================
// ACACIA world renderer - light and weather
// Night is a light map: ambient darkness at half resolution, with holes cut
// by the real light sources (fires, lit windows, lamps, the crystal,
// fireflies), then warm glow added. Weather reads the simulation's weather.
// ============================================================================
"use strict";

const Fx = {
  sun: null, pointLights: [], lightCv: null, lightG: null, rain: [], snow: [], vign: null, tod: "day", dark: 0,
  resize() {
    this.lightCv = offscreen(Math.ceil(W / 2), Math.ceil(H / 2)); this.lightG = this.lightCv.getContext("2d"); this.vign = null;
  },
  shadowDir() {                                                // cast shadows away from the sun, only in real daylight
    const s = this.sun; if (!s || s.night) return { dx: 0, a: 0 };
    const dx = clamp((W / 2 - s.x) / W, -0.5, 0.5) * 2 * (1.3 - clamp(s.elev, 0, 1));
    return { dx, a: clamp((1 - ((this._st && this._st.weather || {}).cloud || 0)) * clamp(s.elev * 2, 0, 1), 0, 1) };
  },
  grade(st) {
    this._st = st; this.pointLights = [];
    const h = st.hour; this.tod = h < 5 || h >= 21 ? "night" : h < 7.5 ? "dawn" : h >= 18 ? "dusk" : "day";
    const w = st.weather || {};
    this.dark = clamp(0.82 - st.light, 0, 0.72) + (w.storm || 0) * 0.12;
  },
  draw(st, t, dt) {
    const w = st.weather || {}, wind = (w.wind || 0.2) * ((w.wind_dir || 1) >= 0 ? 1 : -1);
    if (World.biomeName === "forest" && this.tod === "day" && (w.cloud || 0) < 0.55) this.shafts(t);
    this.weather(st, t, dt, w, wind);
    if ((w.fog || 0) > 0.04) this.fog(st, t, w.fog);
    this.night(st, t);
    this.gradeOverlay(st, w);
    if ((w.flash || 0) > 0.05) { ctx.fillStyle = `rgba(232,238,255,${0.55 * w.flash})`; ctx.fillRect(0, 0, W, H); }
    this.vignette();
  },
  shafts(t) {
    ctx.save(); ctx.globalCompositeOperation = "lighter";
    for (let i = 0; i < 4; i++) {
      const x0 = ((i * 0.27 + 0.1) * W - Cam.x * Cam.ppm * 0.15) % (W * 1.2), a = 0.05 + 0.025 * Math.sin(t * 0.3 + i);
      const g = ctx.createLinearGradient(x0, 0, x0 + W * 0.12, Cam.gy); g.addColorStop(0, `rgba(255,236,190,${a})`); g.addColorStop(1, "rgba(255,236,190,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x0, 0); ctx.lineTo(x0 + W * 0.05, 0); ctx.lineTo(x0 + W * 0.18, Cam.gy); ctx.lineTo(x0 + W * 0.1, Cam.gy); ctx.fill();
    }
    ctx.restore();
  },
  weather(st, t, dt, w, wind) {
    const snow = !!st.snow, precip = w.precip || 0;
    if (!snow) {
      const want = Math.round(precip * 260);
      while (this.rain.length < want) this.rain.push({ x: Math.random() * W, y: Math.random() * H, v: 700 + Math.random() * 450, near: Math.random() < 0.35 });
      if (this.rain.length > want) this.rain.length = want;
      for (const pass of [false, true]) {
        ctx.strokeStyle = pass ? "rgba(210,222,238,.42)" : "rgba(190,205,225,.22)"; ctx.lineWidth = pass ? 1.3 : 1; ctx.beginPath();
        for (const d of this.rain) {
          if (d.near !== pass) continue;
          d.y += d.v * dt * (pass ? 1.25 : 0.8); d.x += wind * 170 * dt;
          if (d.y > H) { d.y = -20; d.x = Math.random() * W; }
          if (d.x > W) d.x -= W; if (d.x < 0) d.x += W;
          const L = pass ? 16 : 9; ctx.moveTo(d.x, d.y); ctx.lineTo(d.x - wind * 5, d.y - L);
        }
        ctx.stroke();
      }
      if (precip > 0.15) {                                      // splashes on the path
        ctx.strokeStyle = "rgba(220,230,245,.35)"; ctx.lineWidth = 1; ctx.beginPath();
        for (let i = 0; i < Math.round(precip * 14); i++) { const x = (Math.sin(t * 7.3 + i * 12.9) * 0.5 + 0.5) * W, y = Cam.gy - Cam.ppm * (0.3 - (i % 5) * 0.12), r = 2 + ((t * 9 + i) % 1) * 5; ctx.moveTo(x - r, y); ctx.quadraticCurveTo(x, y - r * 0.8, x + r, y); }
        ctx.stroke();
      }
    } else {
      const want = Math.round(precip * 220);
      while (this.snow.length < want) this.snow.push({ x: Math.random() * W, y: Math.random() * H, v: 40 + Math.random() * 60, r: 1 + Math.random() * 2.2, ph: Math.random() * 6 });
      if (this.snow.length > want) this.snow.length = want;
      ctx.fillStyle = "rgba(245,248,252,.85)"; ctx.beginPath();
      for (const s of this.snow) { s.y += s.v * dt; s.x += (wind * 40 + Math.sin(t + s.ph) * 20) * dt; if (s.y > H) { s.y = -5; s.x = Math.random() * W; } if (s.x > W) s.x -= W; if (s.x < 0) s.x += W; ctx.moveTo(s.x + s.r, s.y); ctx.arc(s.x, s.y, s.r, 0, TAU); }
      ctx.fill();
    }
  },
  fog(st, t, fog) {
    const c = mix(World.hazeColor(st), "#c8d0d8", 0.4);
    for (let i = 0; i < 3; i++) {
      const y = Cam.gy - Cam.ppm * (0.5 + i * 1.4), off = (t * (6 + i * 3) + i * 300 - Cam.x * Cam.ppm * (0.3 + i * 0.2)) % W;
      const g = ctx.createLinearGradient(0, y - Cam.ppm * 2, 0, y + Cam.ppm * 1.2);
      g.addColorStop(0, rgba(c, 0)); g.addColorStop(0.5, rgba(c, 0.32 * fog)); g.addColorStop(1, rgba(c, 0));
      ctx.fillStyle = g; ctx.fillRect(0, y - Cam.ppm * 2, W, Cam.ppm * 3.2);
      ctx.fillStyle = rgba(c, 0.12 * fog);
      for (let k = -1; k < 3; k++) { ctx.beginPath(); ctx.ellipse(off + k * W * 0.5, y, W * 0.22, Cam.ppm * 0.5, 0, 0, TAU); ctx.fill(); }
    }
  },
  night(st, t) {
    const d = this.dark; if (d < 0.02 || !this.lightG) return;
    const g = this.lightG, lw = this.lightCv.width, lh = this.lightCv.height;
    g.globalCompositeOperation = "source-over"; g.clearRect(0, 0, lw, lh);
    g.fillStyle = `rgba(6,10,26,${d})`; g.fillRect(0, 0, lw, lh);
    // moonlight keeps the sky and silhouettes readable (slightly lighter up top)
    if (this.tod === "night") { const mg = g.createLinearGradient(0, 0, 0, lh); mg.addColorStop(0, "rgba(0,0,0,.18)"); mg.addColorStop(1, "rgba(0,0,0,0)"); g.globalCompositeOperation = "destination-out"; g.fillStyle = mg; g.fillRect(0, 0, lw, lh * 0.5); }
    g.globalCompositeOperation = "destination-out";
    const lights = World.lights.map(L => ({ x: sx(L.x), y: sy(L.y), r: L.r * Cam.ppm, a: L.a * (L.flick ? 0.9 + 0.1 * Math.sin(t * 13 + L.x) : 1), col: L.col })).concat(this.pointLights);
    for (const L of lights) {
      if (L.x < -L.r || L.x > W + L.r) continue;
      const rg = g.createRadialGradient(L.x / 2, L.y / 2, 0, L.x / 2, L.y / 2, L.r / 2);
      rg.addColorStop(0, `rgba(0,0,0,${clamp(L.a, 0, 1)})`); rg.addColorStop(0.55, `rgba(0,0,0,${clamp(L.a * 0.45, 0, 1)})`); rg.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = rg; g.fillRect((L.x - L.r) / 2, (L.y - L.r) / 2, L.r, L.r);
    }
    ctx.drawImage(this.lightCv, 0, 0, W, H);
    ctx.save(); ctx.globalCompositeOperation = "lighter";         // warm colour from each light
    for (const L of lights) {
      if (L.x < -L.r || L.x > W + L.r) continue;
      const rg = ctx.createRadialGradient(L.x, L.y, 0, L.x, L.y, L.r * 0.8);
      rg.addColorStop(0, rgba(L.col, 0.22 * clamp(L.a, 0, 1) * clamp(d * 1.6, 0.25, 1))); rg.addColorStop(1, rgba(L.col, 0));
      ctx.fillStyle = rg; ctx.fillRect(L.x - L.r, L.y - L.r, L.r * 2, L.r * 2);
    }
    ctx.restore();
  },
  gradeOverlay(st, w) {
    const tod = this.tod;
    if (tod === "dawn" || tod === "dusk") {
      ctx.save(); ctx.globalCompositeOperation = "soft-light";
      ctx.fillStyle = tod === "dusk" ? "rgba(255,150,90,.35)" : "rgba(255,190,150,.3)"; ctx.fillRect(0, 0, W, H); ctx.restore();
    }
    const grey = clamp((w.cloud || 0) * 0.35 + (w.storm || 0) * 0.35 + (w.precip || 0) * 0.2, 0, 0.6);
    if (grey > 0.05) { ctx.save(); ctx.globalCompositeOperation = "saturation"; ctx.fillStyle = `rgba(128,128,128,${grey})`; ctx.fillRect(0, 0, W, H); ctx.restore(); }
    if (st.snow) { ctx.fillStyle = "rgba(200,215,235,.08)"; ctx.fillRect(0, 0, W, H); }
  },
  vignette() {
    if (!this.vign) { this.vign = offscreen(W, H); const g = this.vign.getContext("2d"); const rg = g.createRadialGradient(W / 2, H * 0.55, Math.min(W, H) * 0.45, W / 2, H * 0.55, Math.max(W, H) * 0.78); rg.addColorStop(0, "rgba(0,0,0,0)"); rg.addColorStop(1, "rgba(0,0,0,.35)"); g.fillStyle = rg; g.fillRect(0, 0, W, H); }
    ctx.drawImage(this.vign, 0, 0, W, H);
  },
};
