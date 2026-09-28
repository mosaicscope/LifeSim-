// ============================================================================
// ACACIA world renderer - animals
// Dimensions are real metres (same table as Python's SPECIES), times the
// animal's own scale (juveniles). States come from the simulation: graze,
// sniff, watch, flee, sleep, hunt/stalk, follow, play... and fear/trust.
// ============================================================================
"use strict";

const SPEC = {
  deer: { L: 1.15, sh: 0.95, dp: 0.40, hd: [0.30, 0.15], nk: 0.36, na: 46, lf: 0.56, lh: 0.60, ear: [0.14, 0.06], tl: 0.13, rump: 1.03, kind: "cervid" },
  fox: { L: 0.60, sh: 0.38, dp: 0.19, hd: [0.17, 0.10], nk: 0.12, na: 30, lf: 0.21, lh: 0.23, ear: [0.08, 0.05], tl: 0.40, rump: 0.97, kind: "canid", bushy: true },
  wolf: { L: 1.05, sh: 0.76, dp: 0.36, hd: [0.28, 0.16], nk: 0.20, na: 28, lf: 0.42, lh: 0.44, ear: [0.10, 0.06], tl: 0.42, rump: 0.96, kind: "canid", bushy: true },
  dog: { L: 0.75, sh: 0.55, dp: 0.27, hd: [0.20, 0.14], nk: 0.14, na: 34, lf: 0.30, lh: 0.32, ear: [0.11, 0.07], tl: 0.30, rump: 0.98, kind: "canid", floppy: true },
  cat: { L: 0.45, sh: 0.25, dp: 0.14, hd: [0.09, 0.085], nk: 0.05, na: 20, lf: 0.13, lh: 0.15, ear: [0.045, 0.04], tl: 0.28, rump: 1.02, kind: "felid" },
};
const Fauna = {
  gait: new Map(),
  gaitOf(id, xm, dt, stride) {
    let g = this.gait.get(id); if (!g) { g = { ph: 0, lastX: xm, spd: 0, turn: 0 }; this.gait.set(id, g); }
    const d = xm - g.lastX; g.lastX = xm; const v = Math.abs(d) / Math.max(dt, 1e-3);
    g.spd = lerp(g.spd, v, 1 - Math.exp(-dt / 0.2)); g.ph = (g.ph + Math.abs(d) / stride) % 1; return g;
  },
  draw(a, st, t, dt, lane) {
    const light = st.light, dim = c => mix(c, "#141b2c", clamp(0.72 - light, 0, 0.6) * 0.3);
    const depth = 1 - lane * 0.06, G = Cam.gy - lane * Cam.ppm;
    if (a.sp === "firefly") return this.firefly(a, t);
    if (a.sp === "butterfly") return this.butterfly(a, t, dim);
    if (a.sp === "bird") return this.bird(a, st, t, dt, dim, G);
    if (a.sp === "rabbit") return this.rabbit(a, st, t, dt, dim, G, depth);
    const d = SPEC[a.sp]; if (!d) return;
    const k = Cam.ppm * (a.scale || 1) * depth, f = a.facing >= 0 ? 1 : -1, x = sx(a.x);
    const L = d.L * k, sh = d.sh * k, dp = d.dp * k;
    const g = this.gaitOf(a.id, a.x, dt, d.L * 1.1), spd = g.spd, moving = spd > 0.08, run = spd > 2.2;
    const st8 = a.state, sleep = st8 === "sleep", graze = st8 === "graze" || st8 === "drink" || st8 === "sniff";
    const alert = st8 === "watch" || st8 === "alert", afraid = (a.fear || 0) > 0.5, stalk = st8 === "hunt" || st8 === "stalk";
    const ph = g.ph * TAU;
    const body = dim(a.body), belly = dim(a.belly), dark = shade(body, 0.72);
    const crouch = sleep ? sh - dp * 0.95 : stalk ? sh * 0.22 : afraid && !moving ? sh * 0.08 : 0;
    const bob = moving ? Math.abs(Math.sin(ph * 2)) * sh * (run ? 0.06 : 0.025) : Math.sin(t * 1.5 + a.x) * sh * 0.006;
    const sX = x + f * L * 0.3, hX = x - f * L * 0.32;
    const gal = run && d.kind === "cervid" ? Math.sin(ph) : 0;                    // bounding: the spine pitches
    const sY = G - sh + crouch - bob - gal * sh * 0.08, hY = G - sh * d.rump + crouch - bob + gal * sh * 0.08;
    const sd = Fx.shadowDir();
    ctx.fillStyle = `rgba(10,12,16,${0.14 * sd.a})`; ctx.beginPath(); ctx.ellipse(x + sd.dx * sh * 0.8, G + 1, L * 0.55 + Math.abs(sd.dx) * sh, Math.max(1.5, dp * 0.16), 0, 0, TAU); ctx.fill();
    ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.beginPath(); ctx.ellipse(x, G + 1, L * 0.5, Math.max(1.5, dp * 0.14), 0, 0, TAU); ctx.fill();
    const leg = (px, py, hind, phase, col) => {
      const top = py + dp * 0.55, len = G - top;
      if (sleep) { limb(ctx, [[px, top], [px + f * len * 0.6, G - 0.02 * k]], [dp * 0.28, dp * 0.18], col); return; }
      let sw = 0, lift = 0;
      if (moving) {
        if (run && d.kind === "cervid") { sw = Math.sin(phase + (hind ? 0 : Math.PI)) * 0.55 * len; lift = Math.max(0, Math.cos(phase)) * len * 0.35; }
        else { sw = Math.sin(phase) * (run ? 0.42 : 0.24) * len; lift = Math.max(0, Math.cos(phase)) * len * (run ? 0.25 : 0.12); }
      }
      const foot = [px + sw * f, G - lift], wd = hind ? L * 0.1 : L * 0.075;
      if (hind) limb(ctx, [[px, top], [px + f * len * 0.18 + sw * 0.4 * f, top + len * 0.42], [px - f * len * 0.12 + sw * 0.7 * f, top + len * 0.78 - lift * 0.3], foot], [wd * 2.0, wd * 1.25, wd * 0.62, wd * 0.5], col);
      else limb(ctx, [[px, top], [px + sw * 0.5 * f, top + len * 0.55 - lift * 0.4], foot], [wd * 1.45, wd * 0.72, wd * 0.5], col);
      ctx.fillStyle = d.kind === "cervid" ? "#2a2220" : shade(col, 0.55); ctx.beginPath(); ctx.ellipse(foot[0] + f * wd * 0.15, foot[1] - wd * 0.2, wd * 0.42, wd * 0.3, 0, 0, TAU); ctx.fill();
    };
    // trot: diagonal pairs; gallop handled inside leg()
    leg(sX - f * L * 0.04, sY, false, ph + Math.PI, dark); leg(hX + f * L * 0.04, hY, true, ph, dark);
    const tg = ctx.createLinearGradient(0, Math.min(sY, hY), 0, Math.max(sY, hY) + dp); tg.addColorStop(0, shade(body, 1.12)); tg.addColorStop(1, shade(body, 0.84));
    ctx.fillStyle = tg; ctx.beginPath();
    const mY = (sY + hY) / 2 - dp * 0.05;
    ctx.moveTo(hX - f * L * 0.1, hY + dp * 0.4);
    ctx.bezierCurveTo(hX - f * L * 0.12, hY - dp * 0.12, hX, hY - dp * 0.06, x, mY);
    ctx.bezierCurveTo(sX - f * L * 0.1, sY - dp * 0.06, sX + f * L * 0.05, sY - dp * 0.06, sX + f * L * 0.12, sY + dp * 0.45);
    ctx.bezierCurveTo(sX + f * L * 0.1, sY + dp * 0.95, x + f * L * 0.1, mY + dp * (afraid ? 0.85 : 1.0), x, mY + dp * (afraid ? 0.82 : 0.95));
    ctx.bezierCurveTo(hX + f * L * 0.1, hY + dp * 0.95, hX - f * L * 0.05, hY + dp * 0.85, hX - f * L * 0.1, hY + dp * 0.4); ctx.fill();
    ctx.fillStyle = belly; ctx.beginPath(); ctx.ellipse(x + f * L * 0.02, mY + dp * 0.78, L * 0.28, dp * 0.16, 0, 0, TAU); ctx.fill();
    if (L > 26) {                                                                  // fur: a few strokes along the lie of the coat
      ctx.strokeStyle = rgba(shade(body, 0.7), 0.5); ctx.lineWidth = 1; ctx.beginPath();
      for (let i = 0; i < 9; i++) { const u = i / 8, bx = lerp(hX, sX, u), by = lerp(hY, sY, u) + dp * (0.15 + (i % 3) * 0.15); ctx.moveTo(bx, by); ctx.lineTo(bx - f * L * 0.05, by + dp * 0.06); }
      ctx.stroke();
      ctx.strokeStyle = rgba(shade(body, 1.25), 0.35); ctx.beginPath(); ctx.moveTo(hX, hY + dp * 0.05); ctx.quadraticCurveTo(x, mY - dp * 0.02, sX, sY + dp * 0.05); ctx.stroke();
    }
    if (d.kind === "cervid") { ctx.fillStyle = dim("#f2ece2"); ctx.beginPath(); ctx.ellipse(hX - f * L * 0.08, hY + dp * 0.25, L * 0.05, dp * 0.22, 0, 0, TAU); ctx.fill(); }  // rump patch
    // tail - body language from state/fear
    const tl = d.tl * k, t0 = [hX - f * L * 0.02, hY + dp * 0.1];
    const excited = st8 === "excited" || st8 === "play" || st8 === "follow" || (a.sp === "dog" && (a.trust || 0) > 0.6 && !afraid);
    const wag = a.sp === "dog" ? Math.sin(t * (excited ? 17 : 4)) * (excited ? 0.45 : 0.15) : 0;
    let droop = { wolf: 0.75, fox: 0.45, deer: -0.6, dog: -0.35, cat: -0.9 }[a.sp] || 0.3;
    if (afraid && a.sp !== "deer") droop = 1.15; if (st8 === "flee" && a.sp === "deer") droop = -1.3; if (stalk) droop = 0.15;
    const t2 = [t0[0] - f * tl * 0.95, t0[1] + tl * (droop + wag) * 0.95];
    limb(ctx, [t0, [t0[0] - f * tl * 0.55, t0[1] + tl * (droop + wag) * 0.5], t2], [tl * (d.bushy ? 0.26 : 0.12), tl * (d.bushy ? 0.34 : 0.1), tl * (d.bushy ? 0.2 : 0.06)], body);
    if (a.sp === "fox") { ctx.fillStyle = "#f4efe8"; ctx.beginPath(); ctx.arc(t2[0], t2[1], tl * 0.1, 0, TAU); ctx.fill(); }
    if (a.sp === "deer" && st8 === "flee") { ctx.fillStyle = "#f8f4ee"; ctx.beginPath(); ctx.ellipse(t2[0], t2[1], tl * 0.2, tl * 0.35, 0, 0, TAU); ctx.fill(); }
    // neck + head: grazing low, alert high, stalking level and forward
    let na = (d.na + (alert ? 20 : 0)) * Math.PI / 180; if (graze) na = -38 * Math.PI / 180; if (sleep) na = -8 * Math.PI / 180; if (stalk) na = 2 * Math.PI / 180;
    const nk = d.nk * k, n0 = [sX + f * L * 0.06, sY + dp * 0.25], n1 = [n0[0] + f * nk * Math.cos(na), n0[1] - nk * Math.sin(na)];
    if (nk > 0.03 * k) limb(ctx, [n0, [(n0[0] + n1[0]) / 2, (n0[1] + n1[1]) / 2], n1], [dp * 0.55, dp * 0.42, dp * 0.3], body);
    const hl = d.hd[0] * k, hh = d.hd[1] * k; let hX2 = n1[0] + f * hl * 0.2, hY2 = n1[1] - hh * 0.1;
    if (graze) hY2 = Math.min(G - hh * 0.5, hY2 + dp * 0.6); if (sleep) hY2 = G - hh * 0.55;
    if (st8 === "sniff") hY2 += Math.sin(t * 9) * hh * 0.08;
    ctx.fillStyle = body; ctx.beginPath();
    ctx.moveTo(hX2 - f * hl * 0.4, hY2 + hh * 0.1); ctx.quadraticCurveTo(hX2 - f * hl * 0.35, hY2 - hh * 0.6, hX2 + f * hl * 0.1, hY2 - hh * 0.55);
    ctx.quadraticCurveTo(hX2 + f * hl * 0.55, hY2 - hh * 0.3, hX2 + f * hl * 0.66, hY2 + hh * 0.05);
    ctx.quadraticCurveTo(hX2 + f * hl * 0.6, hY2 + hh * 0.3, hX2 + f * hl * 0.2, hY2 + hh * 0.35); ctx.quadraticCurveTo(hX2 - f * hl * 0.2, hY2 + hh * 0.5, hX2 - f * hl * 0.4, hY2 + hh * 0.1); ctx.fill();
    if (d.kind === "canid" && a.sp !== "dog") { ctx.fillStyle = dim("#f2ece4"); ctx.beginPath(); ctx.ellipse(hX2 + f * hl * 0.35, hY2 + hh * 0.2, hl * 0.25, hh * 0.15, 0, 0, TAU); ctx.fill(); }
    // ears: pinned back when afraid; a deer's turn toward Jane while watching
    const el = d.ear[0] * k, ew = d.ear[1] * k, jx = sx(st.jane.x), toward = (jx - x) * f > 0 ? 1 : -1;
    if (d.floppy) { ctx.fillStyle = dark; ctx.beginPath(); ctx.moveTo(hX2 - f * hl * 0.15, hY2 - hh * 0.45); ctx.quadraticCurveTo(hX2 - f * hl * 0.45, hY2, hX2 - f * hl * 0.3, hY2 + el * 0.5); ctx.lineTo(hX2 - f * hl * 0.05, hY2 + el * 0.3); ctx.fill(); }
    else {
      const back = afraid || stalk ? 0.55 : 0, orient = alert && a.sp === "deer" ? toward * 0.25 : 0;
      for (const e of d.kind === "cervid" ? [-0.1, 0.15] : [0]) {
        const ex = hX2 - f * hl * (0.12 + e);
        ctx.fillStyle = e > 0 ? shade(body, 0.85) : body; ctx.beginPath(); ctx.moveTo(ex - ew * 0.5, hY2 - hh * 0.4);
        ctx.lineTo(ex + f * ew * (0.1 + orient) - f * el * back, hY2 - hh * 0.4 - el * (1 - back * 0.5)); ctx.lineTo(ex + ew * 0.55, hY2 - hh * 0.38); ctx.fill();
      }
    }
    if (a.antlers) { ctx.strokeStyle = dim("#8a6a44"); ctx.lineWidth = Math.max(1, hh * 0.1); ctx.lineCap = "round"; const ax = hX2 - f * hl * 0.05, ay = hY2 - hh * 0.45; ctx.beginPath(); ctx.moveTo(ax, ay); ctx.quadraticCurveTo(ax - f * hl * 0.25, ay - hh * 1.3, ax - f * hl * 0.45, ay - hh * 2.1); ctx.moveTo(ax - f * hl * 0.2, ay - hh * 1.25); ctx.lineTo(ax + f * hl * 0.15, ay - hh * 1.9); ctx.moveTo(ax - f * hl * 0.35, ay - hh * 1.75); ctx.lineTo(ax - f * hl * 0.1, ay - hh * 2.2); ctx.stroke(); ctx.lineCap = "butt"; }
    if (!sleep) { ctx.fillStyle = a.sp === "wolf" && light < 0.5 ? "#f4e08a" : "#111"; ctx.beginPath(); ctx.arc(hX2 + f * hl * 0.12, hY2 - hh * 0.15, Math.max(0.8, hh * 0.1), 0, TAU); ctx.fill(); if (hh > 6) { ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(hX2 + f * hl * 0.1, hY2 - hh * 0.2, Math.max(0.5, hh * 0.03), 0, TAU); ctx.fill(); } }
    else { ctx.strokeStyle = "#111"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(hX2 + f * hl * 0.06, hY2 - hh * 0.15); ctx.lineTo(hX2 + f * hl * 0.2, hY2 - hh * 0.13); ctx.stroke(); }
    ctx.fillStyle = "#1a1414"; ctx.beginPath(); ctx.arc(hX2 + f * hl * 0.63, hY2 + hh * 0.02, Math.max(0.7, hh * 0.08), 0, TAU); ctx.fill();
    leg(sX + f * L * 0.02, sY, false, ph, body); leg(hX - f * L * 0.02, hY, true, ph + Math.PI, body);
  },
  rabbit(a, st, t, dt, dim, G, depth) {
    const k = Cam.ppm * (a.scale || 1) * depth, f = a.facing >= 0 ? 1 : -1, x = sx(a.x);
    const g = this.gaitOf(a.id, a.x, dt, 0.45), moving = g.spd > 0.1, hop = moving ? Math.abs(Math.sin(g.ph * TAU * 0.5)) : 0;
    const afraid = (a.fear || 0) > 0.5, flee = a.state === "flee", graze = a.state === "graze" || a.state === "sniff" || a.state === "drink", sleep = a.state === "sleep";
    const freeze = afraid && !moving && !flee;
    const body = dim(a.body), belly = dim(a.belly), L = 0.3 * k, Hh = 0.17 * k, y = G - hop * 0.2 * k;
    ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.beginPath(); ctx.ellipse(x, G + 1, L * 0.55 * (1 - hop * 0.3), Math.max(1.2, 0.03 * k), 0, 0, TAU); ctx.fill();
    const stretch = 1 + hop * 0.4, crouch = sleep ? 0.72 : freeze ? 0.9 : 1;
    const bg = ctx.createRadialGradient(x - f * L * 0.1, y - Hh * 0.9, L * 0.05, x, y - Hh * 0.5, L * 0.7);
    bg.addColorStop(0, shade(body, 1.14)); bg.addColorStop(1, shade(body, 0.8));
    ctx.fillStyle = bg; ctx.beginPath();
    ctx.moveTo(x - f * L * 0.5 * stretch, y);
    ctx.bezierCurveTo(x - f * L * 0.62 * stretch, y - Hh * 1.25 * crouch, x + f * L * 0.05, y - Hh * 1.35 * crouch, x + f * L * 0.32 * stretch, y - Hh * 0.8 * crouch);
    ctx.bezierCurveTo(x + f * L * 0.42 * stretch, y - Hh * 0.45, x + f * L * 0.3, y, x + f * L * 0.18, y); ctx.closePath(); ctx.fill();
    ctx.fillStyle = shade(body, 0.88); ctx.beginPath(); ctx.ellipse(x - f * L * 0.28, y - Hh * 0.45, L * 0.2, Hh * 0.45, 0, 0, TAU); ctx.fill();
    ctx.fillStyle = belly; ctx.beginPath(); ctx.ellipse(x + f * L * 0.08, y - Hh * 0.14, L * 0.2, Hh * 0.13, 0, 0, TAU); ctx.fill();
    ctx.fillStyle = shade(body, 0.8); ctx.beginPath(); ctx.ellipse(x - f * L * 0.3 - f * hop * L * 0.3, G - 0.012 * k, L * 0.2, 0.025 * k, 0, 0, TAU); ctx.fill();
    ctx.beginPath(); ctx.ellipse(x + f * L * 0.26 + f * hop * L * 0.25, G - 0.01 * k, L * 0.07, 0.018 * k, 0, 0, TAU); ctx.fill();
    const hx = x + f * L * (graze ? 0.42 : 0.36), hy = y - Hh * (graze ? 0.55 : sleep ? 0.6 : 1.05), hr = 0.045 * k;
    ctx.fillStyle = body; ctx.beginPath(); ctx.ellipse(hx, hy, hr * 1.15, hr, 0, 0, TAU); ctx.fill();
    const back = flee || afraid && moving ? 0.85 : sleep ? 1.0 : freeze ? 0 : 0.15, el = 0.095 * k;   // frozen: ears bolt upright
    for (const e of [-0.35, 0.25]) {
      const ex = hx - f * hr * e, ang = -Math.PI / 2 - f * back * 1.2 + e * 0.15 + (graze ? Math.sin(t * 2 + a.x) * 0.08 : 0);
      ctx.fillStyle = body; ctx.beginPath(); ctx.ellipse(ex + Math.cos(ang) * el * 0.5, hy - hr * 0.6 + Math.sin(ang) * el * 0.5, el * 0.5, 0.016 * k, ang, 0, TAU); ctx.fill();
      if (k > 60) { ctx.fillStyle = "#d8a8a8"; ctx.beginPath(); ctx.ellipse(ex + Math.cos(ang) * el * 0.5, hy - hr * 0.6 + Math.sin(ang) * el * 0.5, el * 0.35, 0.007 * k, ang, 0, TAU); ctx.fill(); }
    }
    ctx.fillStyle = "#f4efe8"; ctx.beginPath(); ctx.arc(x - f * L * 0.52, y - Hh * 0.5, 0.03 * k * (flee ? 1.3 : 1), 0, TAU); ctx.fill();
    if (!sleep) { ctx.fillStyle = "#111"; ctx.beginPath(); ctx.arc(hx + f * hr * 0.35, hy - hr * 0.2, Math.max(0.7, hr * 0.22), 0, TAU); ctx.fill(); }
    const tw = a.state === "sniff" || graze ? Math.sin(t * 22) * hr * 0.06 : 0;                   // nose twitch
    ctx.fillStyle = "#b07a7a"; ctx.beginPath(); ctx.arc(hx + f * hr * 1.1, hy + hr * 0.1 + tw, Math.max(0.5, hr * 0.14), 0, TAU); ctx.fill();
  },
  bird(a, st, t, dt, dim, G) {
    const alt = a.alt || 0, x = sx(a.x), y = G - alt * Cam.ppm, s = 0.16 * Cam.ppm * (a.scale || 1), f = a.facing >= 0 ? 1 : -1;
    const g = this.gaitOf(a.id, a.x, dt, 0.08), col = dim(a.body);
    if (alt > 0.4) {
      const fl = Math.sin(t * 13 + a.x), glide = g.spd > 3 && Math.sin(t * 0.7 + a.x) > 0.6;
      ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(x, y, s * 0.42, s * 0.16, 0, 0, TAU); ctx.fill();
      ctx.beginPath(); ctx.arc(x + f * s * 0.4, y - s * 0.05, s * 0.13, 0, TAU); ctx.fill();
      ctx.strokeStyle = col; ctx.lineWidth = Math.max(1, s * 0.14); ctx.lineCap = "round"; const w = glide ? 0.1 : fl;
      ctx.beginPath(); ctx.moveTo(x - s * 0.8, y - s * 0.5 * w); ctx.quadraticCurveTo(x - s * 0.3, y - s * 0.6 * w, x, y); ctx.quadraticCurveTo(x + s * 0.3, y - s * 0.6 * w, x + s * 0.8, y - s * 0.5 * w); ctx.stroke(); ctx.lineCap = "butt";
      return;
    }
    const hop = g.spd > 0.05 ? Math.abs(Math.sin(g.ph * TAU)) * s * 0.35 : 0, peck = a.state === "graze" || a.state === "sniff" ? Math.max(0, Math.sin(t * 5 + a.x)) : 0;
    ctx.fillStyle = "rgba(0,0,0,.25)"; ctx.beginPath(); ctx.ellipse(x, G + 1, s * 0.35, Math.max(1, s * 0.06), 0, 0, TAU); ctx.fill();
    ctx.fillStyle = col; ctx.beginPath(); ctx.ellipse(x, y - s * 0.32 - hop, s * 0.4, s * 0.24, -f * 0.2, 0, TAU); ctx.fill();
    ctx.beginPath(); ctx.moveTo(x - f * s * 0.3, y - s * 0.35 - hop); ctx.lineTo(x - f * s * 0.72, y - s * 0.5 - hop); ctx.lineTo(x - f * s * 0.3, y - s * 0.25 - hop); ctx.fill();
    const hx = x + f * s * 0.32, hy = y - s * (0.52 - peck * 0.3) - hop;
    ctx.beginPath(); ctx.arc(hx, hy, s * 0.16, 0, TAU); ctx.fill();
    ctx.fillStyle = "#e0a53a"; ctx.beginPath(); ctx.moveTo(hx + f * s * 0.13, hy - s * 0.03); ctx.lineTo(hx + f * s * 0.32, hy + s * 0.03); ctx.lineTo(hx + f * s * 0.13, hy + s * 0.06); ctx.fill();
    ctx.fillStyle = "#111"; ctx.beginPath(); ctx.arc(hx + f * s * 0.05, hy - s * 0.04, Math.max(0.6, s * 0.035), 0, TAU); ctx.fill();
    ctx.strokeStyle = "#8a6a3a"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x - s * 0.05, y - s * 0.12 - hop); ctx.lineTo(x - s * 0.08, y); ctx.moveTo(x + s * 0.08, y - s * 0.12 - hop); ctx.lineTo(x + s * 0.05, y); ctx.stroke();
  },
  butterfly(a, t, dim) {
    const fl = Math.abs(Math.sin(t * 14 + a.x)), x = sx(a.x), y = sy((a.alt || 0) + 0.8), s = 0.045 * Cam.ppm;
    ctx.fillStyle = dim(a.body); ctx.beginPath(); ctx.ellipse(x - s * fl, y - s * 0.4, s * fl, s * 0.7, 0, 0, TAU); ctx.ellipse(x + s * fl, y - s * 0.4, s * fl, s * 0.7, 0, 0, TAU); ctx.fill();
  },
  firefly(a, t) {
    const gl = 0.5 + 0.5 * Math.sin(t * 4 + a.x * 7), x = sx(a.x), y = sy((a.alt || 0) + 0.6);
    Fx.pointLights.push({ x, y, r: 0.35 * Cam.ppm * gl + 3, col: "#dcff8c", a: 0.9 * gl });
  },
};
