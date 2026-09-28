// ============================================================================
// ACACIA world renderer - people (Jane + townspeople)
// Locomotion: every foot has a planted world position; the trailing foot
// lifts and swings forward on an arc, then plants - the body moves over it.
// No sliding. Posture comes from the simulation's real state (energy, mood,
// sitting, reaching, carrying); nothing is invented here.
// ============================================================================
"use strict";

class Stepper {
  constructor(x, half) { this.f = [{ x: x - half, lift: 0, sw: null }, { x: x + half, lift: 0, sw: null }]; this.last = x; this.half = half; }
  update(x, vxIn, dt, stride, half) {
    if (Math.abs(x - this.last) > 3) { this.f[0] = { x: x - half, lift: 0, sw: null }; this.f[1] = { x: x + half, lift: 0, sw: null }; }
    // the motion actually being drawn decides the steps (not a lagging report)
    const mv = (x - this.last) / Math.max(dt, 1e-3); this.v = lerp(this.v || 0, mv, 1 - Math.exp(-dt / 0.12));
    const vx = vxIn === 0 ? 0 : this.v;
    this.last = x; this.half = half;
    for (const q of this.f) if (!q.sw && Math.abs(q.x - x) > stride * 1.4) { q.x = x - (vx >= 0 ? 1 : -1) * stride * 0.3; }   // never left far behind
    const spd = Math.abs(vx), dir = vx >= 0 ? 1 : -1;
    for (const q of this.f) if (q.sw) {
      q.sw.t += dt / q.sw.d; const k = Math.min(1, q.sw.t);
      q.x = lerp(q.sw.x0, q.sw.x1, smooth(k)); q.lift = Math.sin(Math.PI * k) * q.sw.h;
      if (k >= 1) { q.sw = null; q.lift = 0; }
    }
    if (this.f.some(q => q.sw)) return;
    if (spd > 0.08) {
      // real gait timing: step length S, swing ~40% of the cycle (0.8 S / v),
      // the foot lands ~0.45 S ahead of the hips -> spread stays ~0.45 S
      const trail = dir * (this.f[0].x - x) < dir * (this.f[1].x - x) ? this.f[0] : this.f[1];
      if (dir * (trail.x - x) < -stride * 0.45) {
        const d = clamp(0.8 * stride / Math.max(spd, 0.3), 0.16, 0.55);
        trail.sw = { x0: trail.x, x1: x + dir * (stride * 0.45 + spd * d), t: 0, d, h: Math.min(0.12, stride * 0.16) };
      }
    } else {                                                   // settle under the hips, one foot at a time
      for (let i = 0; i < 2; i++) { const q = this.f[i], rest = x + (i ? half : -half); if (Math.abs(q.x - rest) > 0.07) { q.sw = { x0: q.x, x1: rest, t: 0, d: 0.28, h: 0.035 }; break; } }
    }
  }
  spread(x) { return Math.max(Math.abs(this.f[0].x - x), Math.abs(this.f[1].x - x)); }
}
class Spring { constructor() { this.p = 0; this.v = 0; } step(target, dt, k = 30, d = 6) { this.v += (k * (target - this.p) - d * this.v) * dt; this.p += this.v * dt; return this.p; } }

// ---------------------------------------------------------------- Jane (her own look, from m38)
const JANE_LOOK = {
  skin: "#f4d3c1", hair: "#f3e2bd", hairD: "#cdb07e", hairHi: "#fffaf0", iris: "#6b7f94", lips: "#c8102e", brow: "#8a6644",
  shadow: "#ec7fa2", liner: "#17100f", blush: "#f27892", tie: "#1d1a1c", clip: "#ff8fbf", gold: "#e0b24c",
  outfits: {
    normal: { top: "#f7b8cb", print: true, bottom: "#f2a9c2", btype: "skirt", shoes: "#f7f2ec", heel: true },
    light: { top: "#f7b8cb", print: true, bottom: "#f7f2ec", btype: "mini", shoes: "#f4c2d0", heel: true },
    warm: { top: "#f2e6d8", knit: true, bottom: "#2d3f66", btype: "jeans", shoes: "#3a2a24", heel: false, sleeves: true },
    rain: { top: "#c89868", bottom: "#2a2328", btype: "trench", shoes: "#2a1f1c", heel: false, sleeves: true },
  },
};
const Pat = {};
function makePatterns() {
  const tile = (w, h, fn, avg) => { const c = offscreen(w, h); fn(c.getContext("2d")); const pt = ctx.createPattern(c, "repeat"); if (pt) pt._avg = avg; return pt; };
  Pat.berry = tile(48, 48, g => {
    g.fillStyle = "#f7b8cb"; g.fillRect(0, 0, 48, 48);
    for (const [x, y] of [[10, 12], [34, 8], [24, 30], [6, 38], [40, 36]]) {
      g.fillStyle = "#e0304a"; g.beginPath(); g.moveTo(x - 4, y - 2); g.quadraticCurveTo(x, y + 8, x + 4, y - 2); g.quadraticCurveTo(x, y - 4, x - 4, y - 2); g.fill();
      g.fillStyle = "#4a8a3a"; g.fillRect(x - 3, y - 4, 6, 2); g.fillStyle = "#ffe07a"; g.fillRect(x - 1, y + 1, 1, 1); g.fillRect(x + 1, y + 3, 1, 1);
    }
  }, "#f3a9bd");
  Pat.knit = tile(12, 12, g => { g.fillStyle = "#f2e6d8"; g.fillRect(0, 0, 12, 12); g.fillStyle = "#dccfbf"; g.fillRect(0, 0, 2, 12); g.fillRect(6, 0, 2, 12); g.fillStyle = "#fbf3e8"; g.fillRect(3, 0, 1, 12); g.fillRect(9, 0, 1, 12); }, "#ecdfcf");
  Pat.denim = tile(10, 10, g => { g.fillStyle = "#2d3f66"; g.fillRect(0, 0, 10, 10); g.strokeStyle = "#3d5280"; g.lineWidth = 1; for (let i = -10; i < 20; i += 3) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i + 10, 10); g.stroke(); } }, "#33466f");
}
function usePat(pt, fallback, scale, dim) {
  if (!pt || dim > 0.35) return fallback;
  if (pt.setTransform && typeof DOMMatrix !== "undefined") pt.setTransform(new DOMMatrix().scale(scale));
  return pt;
}

const Jane = {
  step: null, fs: 1, tails: [new Spring(), new Spring()], skirt: new Spring(), lastVx: 0,
  draw(j, st, t, dt) {
    if (!inView(j.x, 3)) return;
    if (!Pat.berry) makePatterns();
    const p = Cam.ppm, h = 1.70 * p, hu = h / 8.1, O = JANE_LOOK.outfits[j.outfit] || JANE_LOOK.outfits.normal, light = st.light;
    const fTarget = j.facing >= 0 ? 1 : -1; this.fs += (fTarget - this.fs) * (1 - Math.exp(-dt / 0.09));
    const f = this.fs >= 0 ? 1 : -1, fe = this.fs;              // fe: continuous (turning), f: discrete (IK)
    const nd = clamp(0.72 - light, 0, 0.6), dim = c => mix(c, "#141b2c", nd * 0.3);   // Fx does the real night
    const G = Cam.gy, detail = hu > 9.5, sit = clamp(j.sit || 0, 0, 1);
    const energy = (j.needs || {}).energy == null ? 0.8 : j.needs.energy, tired = clamp((0.35 - energy) / 0.35, 0, 1), low = clamp(-(j.valence || 0) - 0.2, 0, 0.6);
    // ---- feet (world metres) ----
    const vNow = Math.abs(this.step ? this.step.v || 0 : 0);                                  // walk: 0.4-0.8 m steps; running lengthens the stride
    const halfM = 0.1, strideM = (vNow < 2.2 ? clamp(0.45 + vNow * 0.2, 0.4, 0.8) : clamp(0.55 + vNow * 0.18, 0.8, 1.5)) * (O.heel ? 0.85 : 1);
    if (!this.step) this.step = new Stepper(j.x, halfM);
    this.step.update(j.x, sit > 0.5 ? 0 : 1, dt, strideM, halfM);
    const walk = clamp(Math.abs(this.step.v || 0) / 1.0, 0, 1);
    const heel = O.heel ? hu * 0.36 : hu * 0.1, legLen = 3.96 * hu;
    const X0 = sx(j.x);
    const spreadPx = this.step.spread(j.x) * p, reachY = Math.sqrt(Math.max(0.1, legLen * legLen - spreadPx * spreadPx)) * 0.992;
    const standY = clamp(reachY, legLen * 0.82, legLen * 0.992);                             // never a crouch-walk
    const breath = Math.sin(t * 1.6) * hu * 0.018;
    const hipY = G - lerp(standY + heel, hu * 0.95, sit);
    const hipRoll = (this.step.f[0].lift - this.step.f[1].lift) / p * hu * 0.6;
    const sway = (1 - walk) * Math.sin(t * 0.45) * hu * 0.05;
    const pel = [X0 + sway, hipY];
    const lean = walk * hu * 0.1 * fe + tired * hu * 0.12 * fe;
    const waist = [pel[0] + lean * 0.5, hipY - hu * 0.8], bust = [pel[0] + lean * 0.8, hipY - hu * 1.62 - breath + tired * hu * 0.06];
    const sh = [pel[0] + lean, hipY - hu * 2.33 - breath + tired * hu * 0.1];
    const chin = [sh[0] + fe * hu * 0.08 + (tired + low) * fe * hu * 0.08, sh[1] - hu * 0.55 + (tired + low) * hu * 0.08];
    const head = [chin[0] + fe * hu * 0.02, chin[1] - hu * 0.52];
    // contact shadow + a soft directional shadow from the sun
    const sd = Fx.shadowDir();
    ctx.fillStyle = `rgba(10,12,16,${0.14 * sd.a})`; ctx.beginPath(); ctx.ellipse(X0 + sd.dx * hu * 2.2, G + hu * 0.02, hu * (1.0 + Math.abs(sd.dx) * 2.4), hu * 0.16, 0, 0, TAU); ctx.fill();
    ctx.fillStyle = "rgba(0,0,0,.34)"; ctx.beginPath(); ctx.ellipse(X0, G + 1, hu * 0.9, hu * 0.12, 0, 0, TAU); ctx.fill();
    // ---- legs ----
    const thigh = 1.98 * hu, shin = 1.98 * hu, legs = [];
    for (let i = 0; i < 2; i++) {
      const s = i === 0 ? -1 : 1, q = this.step.f[i];
      const hp = [pel[0] + s * hu * 0.36 * fe, hipY + (s > 0 ? hipRoll : -hipRoll)];
      let foot;
      if (sit > 0.5) { foot = [pel[0] + f * hu * (2.35 + s * 0.12), G - heel * 0.25]; legs.push({ s, hp, knee: ik(hp, foot, thigh, shin, f), foot, lift: 0 }); continue; }
      foot = [sx(q.x) + s * hu * 0.12 * fe, G - heel - q.lift * p];
      legs.push({ s, hp, knee: ik(hp, foot, thigh, shin, f), foot, lift: q.lift });
    }
    const skin = dim(JANE_LOOK.skin), skinL = shade(skin, 1.07);
    const legPaint = (L, far) => {
      const k = far ? 0.84 : 1, mid = [lerp(L.knee[0], L.foot[0], 0.4), lerp(L.knee[1], L.foot[1], 0.4)];
      let col;
      if (O.btype === "jeans") col = usePat(Pat.denim, dim(O.bottom), hu / 30, nd);
      else if (O.btype === "trench") col = shade(dim("#3a2f35"), k);
      else { const gg = ctx.createLinearGradient(L.hp[0] - f * hu * 0.4, 0, L.hp[0] + f * hu * 0.4, 0); gg.addColorStop(0, shade(skin, 0.86 * k)); gg.addColorStop(1, shade(skin, 1.05 * k)); col = gg; }
      limb(ctx, [L.hp, L.knee, mid, L.foot], [hu * 0.7, hu * 0.36, hu * 0.4, hu * 0.21], col);
      if (O.btype !== "jeans" && O.btype !== "trench" && detail) { ctx.strokeStyle = rgba("#ffffff", 0.22 * k); ctx.lineWidth = Math.max(1, hu * 0.05); ctx.beginPath(); ctx.moveTo(L.knee[0] + f * hu * 0.12, L.knee[1] - hu * 0.1); ctx.lineTo(mid[0] + f * hu * 0.14, mid[1]); ctx.stroke(); }
      if (O.btype === "jeans" && detail) { ctx.strokeStyle = rgba(JANE_LOOK.gold, 0.5); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(L.hp[0] + f * hu * 0.3, L.hp[1]); ctx.lineTo(L.knee[0] + f * hu * 0.16, L.knee[1]); ctx.lineTo(L.foot[0] + f * hu * 0.1, L.foot[1] - hu * 0.3); ctx.stroke(); }
      janeShoe(L.foot, f, O, dim, hu, k, L.lift > 0.005);
    };
    ctx.fillStyle = dim(JANE_LOOK.hairD); ctx.beginPath(); ctx.ellipse(head[0] - fe * hu * 0.1, head[1] + hu * 0.1, hu * 0.46, hu * 0.5, 0, 0, TAU); ctx.fill();
    legPaint(legs[0], true);
    // ---- arms: counter-swing to the legs ----
    const armsOf = s => {
      const shj = [sh[0] + s * hu * 0.78 * Math.max(0.55, Math.abs(fe)), sh[1] + hu * 0.1], up = 1.42 * hu, fo = 1.3 * hu;
      const oppFoot = this.step.f[s > 0 ? 0 : 1];
      let hand;
      if (j.reach && s > 0 && j.reach[2] > 0.3) hand = [sx(j.reach[0]), sy(j.reach[1])];
      else if (sit > 0.5) hand = [pel[0] + f * hu * (1.55 + s * 0.1), hipY - hu * 1.1];      // hands resting on her knees
      else { const a = clamp((oppFoot.x - j.x) / Math.max(strideM, 0.3), -1, 1) * 0.5 * walk + (1 - walk) * 0.08 * s + tired * 0.05; hand = [shj[0] + f * Math.sin(a * 1.45) * (up + fo) * 0.85 + s * hu * 0.1, shj[1] + Math.cos(a) * (up + fo) * 0.95]; }
      return { s, shj, elbow: ik(shj, hand, up, fo, -f), hand };
    };
    const armPaint = (A, far) => {
      const k = far ? 0.84 : 1; let col = shade(skin, k);
      if (O.sleeves) col = O.knit ? usePat(Pat.knit, dim(O.top), hu / 30, nd) : shade(dim(O.top), k);
      limb(ctx, [A.shj, A.elbow, A.hand], [hu * 0.34, hu * 0.25, hu * 0.19], col);
      ctx.fillStyle = shade(skin, k); ctx.beginPath(); ctx.ellipse(A.hand[0] + f * hu * 0.04, A.hand[1] + hu * 0.1, hu * 0.12, hu * 0.17, 0, 0, TAU); ctx.fill();
      if (detail) { ctx.strokeStyle = shade(skin, 0.78 * k); ctx.lineWidth = 1; for (let i = -1; i <= 1; i++) { ctx.beginPath(); ctx.moveTo(A.hand[0] + i * hu * 0.05, A.hand[1] + hu * 0.14); ctx.lineTo(A.hand[0] + i * hu * 0.06, A.hand[1] + hu * 0.27); ctx.stroke(); } }
    };
    const arms = [armsOf(-1), armsOf(1)];
    armPaint(arms[0], true);
    if (j.held && j.held.wood) { ctx.strokeStyle = dim("#7a5634"); ctx.lineWidth = hu * 0.2; ctx.lineCap = "round"; for (let k = 0; k < Math.min(4, j.held.wood); k++) { ctx.beginPath(); ctx.moveTo(sh[0] - f * hu * 1.0 + k * hu * 0.08, sh[1] - hu * 0.3 + k * hu * 0.08); ctx.lineTo(pel[0] - f * hu * 0.1 + k * hu * 0.08, hipY + hu * 0.3 + k * hu * 0.08); ctx.stroke(); } ctx.lineCap = "butt"; }
    // ---- torso: hourglass ----
    const torso = () => {
      ctx.beginPath();
      ctx.moveTo(sh[0] - hu * 0.9, sh[1] + hu * 0.12);
      ctx.bezierCurveTo(sh[0] - hu * 0.88, sh[1] + hu * 0.45, bust[0] - hu * 0.95, bust[1] - hu * 0.2, bust[0] - hu * 0.9, bust[1] + hu * 0.22);
      ctx.bezierCurveTo(bust[0] - hu * 0.84, bust[1] + hu * 0.6, waist[0] - hu * 0.5, waist[1] - hu * 0.25, waist[0] - hu * 0.475, waist[1]);
      ctx.bezierCurveTo(waist[0] - hu * 0.52, waist[1] + hu * 0.38, pel[0] - hu * 1.08, hipY - hu * 0.32, pel[0] - hu * 1.05, hipY + hu * 0.18);
      ctx.lineTo(pel[0] + hu * 1.05, hipY + hu * 0.18);
      ctx.bezierCurveTo(pel[0] + hu * 1.08, hipY - hu * 0.32, waist[0] + hu * 0.52, waist[1] + hu * 0.38, waist[0] + hu * 0.475, waist[1]);
      ctx.bezierCurveTo(waist[0] + hu * 0.5, waist[1] - hu * 0.25, bust[0] + hu * 0.84, bust[1] + hu * 0.6, bust[0] + hu * 0.9, bust[1] + hu * 0.22);
      ctx.bezierCurveTo(bust[0] + hu * 0.95, bust[1] - hu * 0.2, sh[0] + hu * 0.88, sh[1] + hu * 0.45, sh[0] + hu * 0.9, sh[1] + hu * 0.12);
      ctx.quadraticCurveTo(sh[0], sh[1] - hu * 0.1, sh[0] - hu * 0.9, sh[1] + hu * 0.12); ctx.closePath();
    };
    const sg = ctx.createLinearGradient(sh[0] - hu, 0, sh[0] + hu, 0);
    sg.addColorStop(f > 0 ? 0 : 1, shade(skin, 0.86)); sg.addColorStop(f > 0 ? 1 : 0, skinL);
    ctx.fillStyle = sg; torso(); ctx.fill();
    legPaint(legs[1], false);
    const bx = [bust[0] - hu * 0.38 + fe * hu * 0.12, bust[0] + hu * 0.38 + fe * hu * 0.12], br = hu * 0.5, cupY = bust[1] + hu * 0.08;
    const topFill = O.print ? usePat(Pat.berry, dim(O.top), hu / 34, nd) : O.knit ? usePat(Pat.knit, dim(O.top), hu / 30, nd) : dim(O.top);
    ctx.save(); torso(); ctx.clip();
    if (O.print) { ctx.fillStyle = topFill; ctx.beginPath(); ctx.moveTo(sh[0] - hu, bust[1] - hu * 0.22); ctx.quadraticCurveTo(bust[0], bust[1] - hu * 0.02, sh[0] + hu, bust[1] - hu * 0.22); ctx.lineTo(sh[0] + hu * 1.2, hipY + hu * 0.25); ctx.lineTo(sh[0] - hu * 1.2, hipY + hu * 0.25); ctx.fill(); }
    else { ctx.fillStyle = topFill; ctx.fillRect(sh[0] - hu * 1.3, sh[1] - hu * 0.2, hu * 2.6, hipY - sh[1] + hu * 0.5); }
    const shadeG = ctx.createLinearGradient(sh[0] - hu, 0, sh[0] + hu, 0);
    shadeG.addColorStop(f > 0 ? 0 : 1, "rgba(40,20,40,.24)"); shadeG.addColorStop(0.55, "rgba(0,0,0,0)"); shadeG.addColorStop(f > 0 ? 1 : 0, "rgba(255,255,255,.12)");
    ctx.fillStyle = shadeG; ctx.fillRect(sh[0] - hu * 1.3, sh[1] - hu * 0.3, hu * 2.6, hipY - sh[1] + hu * 0.6);
    ctx.restore();
    { const px = bust[0] + fe * hu * 0.86, py = cupY; ctx.fillStyle = O.print || O.knit || O.sleeves ? topFill : skin; ctx.beginPath(); ctx.ellipse(px - fe * hu * 0.12, py, hu * 0.34 * Math.abs(fe), br * 0.95, 0, 0, TAU); ctx.fill(); }
    for (let i = 0; i < 2; i++) {
      const cx = bx[i], cg = ctx.createRadialGradient(cx - hu * 0.1, cupY - hu * 0.14, br * 0.1, cx, cupY, br);
      ctx.save(); ctx.beginPath(); ctx.ellipse(cx, cupY, br, br * 0.9, 0, 0, TAU); ctx.clip();
      if (O.print || O.knit || O.sleeves) { ctx.fillStyle = topFill; ctx.fillRect(cx - br, cupY - br, br * 2, br * 2); }
      cg.addColorStop(0, "rgba(255,255,255,.28)"); cg.addColorStop(0.6, "rgba(255,255,255,0)"); cg.addColorStop(1, "rgba(60,20,40,.25)");
      ctx.fillStyle = cg; ctx.fillRect(cx - br, cupY - br, br * 2, br * 2); ctx.restore();
    }
    if (O.print) {
      ctx.fillStyle = skin; ctx.beginPath(); ctx.moveTo(bust[0] - hu * 0.05 + fe * hu * 0.12, cupY - br * 0.75); ctx.quadraticCurveTo(bust[0] + fe * hu * 0.12, cupY - br * 0.1, bust[0] + hu * 0.05 + fe * hu * 0.12, cupY - br * 0.75); ctx.fill();
      ctx.strokeStyle = shade(skin, 0.72); ctx.lineWidth = Math.max(1, hu * 0.04); ctx.beginPath(); ctx.moveTo(bust[0] + fe * hu * 0.12, cupY - br * 0.55); ctx.lineTo(bust[0] + fe * hu * 0.12, cupY - br * 0.05); ctx.stroke();
      ctx.fillStyle = dim("#fbf7f2");
      for (let i = 0; i < 2; i++) for (let k = 0; k < 5; k++) { const a = Math.PI * (1.1 + k * 0.2); ctx.beginPath(); ctx.arc(bx[i] + Math.cos(a) * br * 0.95, cupY + Math.sin(a) * br * 0.86, hu * 0.07, 0, TAU); ctx.fill(); }
      ctx.fillStyle = dim("#ffffff"); const bwx = bust[0] + fe * hu * 0.12, bwy = cupY - br * 0.62;
      ctx.beginPath(); ctx.moveTo(bwx, bwy); ctx.lineTo(bwx - hu * 0.14, bwy - hu * 0.08); ctx.lineTo(bwx - hu * 0.14, bwy + hu * 0.08); ctx.fill(); ctx.beginPath(); ctx.moveTo(bwx, bwy); ctx.lineTo(bwx + hu * 0.14, bwy - hu * 0.08); ctx.lineTo(bwx + hu * 0.14, bwy + hu * 0.08); ctx.fill();
      ctx.strokeStyle = dim(shade(O.top, 0.8)); ctx.lineWidth = Math.max(1, hu * 0.045);
      for (const s of [-1, 1]) { ctx.beginPath(); ctx.moveTo(bx[s > 0 ? 1 : 0] + s * br * 0.3, cupY - br * 0.8); ctx.lineTo(sh[0] + s * hu * 0.52, sh[1] + hu * 0.08); ctx.stroke(); }
      ctx.strokeStyle = rgba(shade(dim(O.top), 0.7), 0.55); ctx.lineWidth = Math.max(1, hu * 0.035);
      for (const s of [-1, 1]) { ctx.beginPath(); ctx.moveTo(bx[s > 0 ? 1 : 0], cupY + br * 0.85); ctx.quadraticCurveTo(waist[0] + s * hu * 0.2, waist[1] - hu * 0.2, waist[0] + s * hu * 0.12, waist[1] + hu * 0.2); ctx.stroke(); }
    }
    // ---- bottoms: skirt swings with motion and wind (spring) ----
    const wind = ((st.weather || {}).wind || 0.2) * (((st.weather || {}).wind_dir || 1) >= 0 ? 1 : -1);
    const acc = (j.vx - this.lastVx) / Math.max(dt, 1e-3); this.lastVx = j.vx;
    const skirtSw = this.skirt.step(-clamp(acc, -4, 4) * 0.05 - j.vx * 0.06 + wind * 0.12 + Math.sin(t * 2.3) * wind * 0.05, dt) * hu;
    if (O.btype === "skirt" || O.btype === "mini") {
      const len = O.btype === "mini" ? hu * 1.0 : hu * 1.55, flare = hu * 1.2, top = hipY - hu * 0.42, base = dim(O.bottom), n = 9;
      for (let i = 0; i < n; i++) {
        const a0 = i / n, a1 = (i + 1) / n, tx0 = lerp(pel[0] - hu * 0.97, pel[0] + hu * 0.97, a0), tx1 = lerp(pel[0] - hu * 0.97, pel[0] + hu * 0.97, a1);
        const bx0 = lerp(pel[0] - flare, pel[0] + flare, a0) + skirtSw, bx1 = lerp(pel[0] - flare, pel[0] + flare, a1) + skirtSw, lit = f > 0 ? a0 : 1 - a0;
        ctx.fillStyle = shade(base, (i % 2 ? 0.9 : 1.03) * (0.9 + 0.14 * lit));
        ctx.beginPath(); ctx.moveTo(tx0, top); ctx.lineTo(tx1, top); ctx.lineTo(bx1, hipY + len + Math.sin(a1 * 7 + t * 3) * hu * 0.03 * walk); ctx.lineTo(bx0, hipY + len + Math.sin(a0 * 7 + t * 3) * hu * 0.03 * walk); ctx.fill();
      }
      ctx.fillStyle = shade(base, 0.8); ctx.fillRect(pel[0] - hu * 0.97, top - hu * 0.02, hu * 1.94, hu * 0.14);
    } else if (O.btype === "jeans") {
      ctx.fillStyle = usePat(Pat.denim, dim(O.bottom), hu / 30, nd); ctx.beginPath(); ctx.moveTo(pel[0] - hu * 0.97, hipY - hu * 0.35); ctx.lineTo(pel[0] + hu * 0.97, hipY - hu * 0.35); ctx.lineTo(pel[0] + hu * 0.9, hipY + hu * 0.45); ctx.lineTo(pel[0] - hu * 0.9, hipY + hu * 0.45); ctx.fill();
      ctx.fillStyle = dim("#2a1f18"); ctx.fillRect(pel[0] - hu * 0.97, hipY - hu * 0.38, hu * 1.94, hu * 0.12); ctx.fillStyle = dim(JANE_LOOK.gold); ctx.fillRect(pel[0] - hu * 0.1, hipY - hu * 0.38, hu * 0.2, hu * 0.12);
    } else if (O.btype === "trench") {
      const len = hu * 2.5;
      const cg = ctx.createLinearGradient(pel[0] - hu, 0, pel[0] + hu, 0); cg.addColorStop(f > 0 ? 0 : 1, shade(dim(O.top), 0.82)); cg.addColorStop(f > 0 ? 1 : 0, shade(dim(O.top), 1.06));
      ctx.fillStyle = cg; ctx.beginPath(); ctx.moveTo(sh[0] - hu * 0.95, sh[1] + hu * 0.1); ctx.lineTo(sh[0] + hu * 0.95, sh[1] + hu * 0.1);
      ctx.lineTo(pel[0] + hu * 1.15 + skirtSw, hipY + len); ctx.lineTo(pel[0] - hu * 1.15 + skirtSw, hipY + len); ctx.closePath(); ctx.fill();
      ctx.fillStyle = shade(dim(O.top), 0.62); ctx.fillRect(waist[0] - hu * 0.62, waist[1] - hu * 0.08, hu * 1.24, hu * 0.16);
      ctx.strokeStyle = shade(dim(O.top), 0.6); ctx.lineWidth = Math.max(1, hu * 0.05);
      for (const s of [-1, 1]) { ctx.beginPath(); ctx.moveTo(sh[0] + s * hu * 0.12, sh[1] + hu * 0.05); ctx.lineTo(bust[0] + s * hu * 0.42, bust[1] + hu * 0.1); ctx.lineTo(waist[0] + s * hu * 0.1, waist[1] - hu * 0.1); ctx.stroke(); }
      ctx.strokeStyle = rgba(shade(O.top, 0.55), 0.5); ctx.lineWidth = 1; for (const s of [-1, 1]) { ctx.beginPath(); ctx.moveTo(pel[0] + s * hu * 0.5, hipY); ctx.lineTo(pel[0] + s * hu * 0.8 + skirtSw, hipY + len * 0.95); ctx.stroke(); }
      ctx.fillStyle = dim("#3a2a1c"); for (const yy of [0.3, 0.9, 1.5]) { ctx.beginPath(); ctx.arc(pel[0] + fe * hu * 0.25, hipY - hu * 1.6 + yy * hu, hu * 0.06, 0, TAU); ctx.fill(); }
    }
    // ---- neck (one piece up under the jaw), collarbones, jewellery ----
    const ng = ctx.createLinearGradient(chin[0] - hu * 0.25, 0, chin[0] + hu * 0.25, 0); ng.addColorStop(f > 0 ? 0 : 1, shade(skin, 0.8)); ng.addColorStop(f > 0 ? 1 : 0, skin);
    ctx.fillStyle = ng; ctx.beginPath();
    ctx.moveTo(sh[0] - hu * 0.55, sh[1] + hu * 0.14); ctx.quadraticCurveTo(chin[0] - hu * 0.26, sh[1] - hu * 0.02, chin[0] - hu * 0.21, head[1]);
    ctx.lineTo(chin[0] + hu * 0.21, head[1]); ctx.quadraticCurveTo(chin[0] + hu * 0.26, sh[1] - hu * 0.02, sh[0] + hu * 0.55, sh[1] + hu * 0.14); ctx.closePath(); ctx.fill();
    if (detail) { ctx.strokeStyle = shade(skin, 0.8); ctx.lineWidth = Math.max(1, hu * 0.03); for (const s of [-1, 1]) { ctx.beginPath(); ctx.moveTo(sh[0] + s * hu * 0.12, sh[1] + hu * 0.2); ctx.quadraticCurveTo(sh[0] + s * hu * 0.35, sh[1] + hu * 0.12, sh[0] + s * hu * 0.62, sh[1] + hu * 0.16); ctx.stroke(); } }
    const jy = chin[1] + hu * 0.26;
    ctx.fillStyle = dim("#141014"); ctx.fillRect(chin[0] - hu * 0.22, jy, hu * 0.44, hu * 0.08);
    ctx.strokeStyle = dim(JANE_LOOK.gold); ctx.lineWidth = Math.max(1, hu * 0.03);
    for (const [dy] of [[0.55], [0.95]]) { ctx.beginPath(); ctx.moveTo(chin[0] - hu * 0.24, jy + hu * 0.1); ctx.quadraticCurveTo(chin[0], jy + hu * dy * 1.6, chin[0] + hu * 0.24, jy + hu * 0.1); ctx.stroke(); }
    ctx.fillStyle = dim(JANE_LOOK.gold); ctx.beginPath(); ctx.arc(chin[0], jy + hu * 0.78, hu * 0.06, 0, TAU); ctx.fill();
    armPaint(arms[1], false);
    const A = arms[1];
    if (j.held && (j.held.berries || j.held.meat) && !(j.reach && j.reach[2] > 0.3)) {
      const bx2 = A.hand[0], by2 = A.hand[1] + hu * 0.2;
      ctx.fillStyle = dim(j.held.berries ? "#8a6a3e" : "#c9b8a0"); ctx.beginPath(); ctx.moveTo(bx2 - hu * 0.45, by2); ctx.lineTo(bx2 + hu * 0.45, by2); ctx.lineTo(bx2 + hu * 0.36, by2 + hu * 0.4); ctx.lineTo(bx2 - hu * 0.36, by2 + hu * 0.4); ctx.fill();
      ctx.strokeStyle = dim("#6a4e2e"); ctx.lineWidth = Math.max(1, hu * 0.05); ctx.beginPath(); ctx.moveTo(bx2 - hu * 0.4, by2); ctx.quadraticCurveTo(bx2, by2 - hu * 0.5, bx2 + hu * 0.4, by2); ctx.stroke();
      if (j.held.berries) { ctx.fillStyle = "#b8284a"; for (let k = 0; k < Math.min(5, j.held.berries); k++) { ctx.beginPath(); ctx.arc(bx2 + (k - 2) * hu * 0.16, by2 - hu * 0.02, hu * 0.08, 0, TAU); ctx.fill(); } }
    }
    // pigtails: springs driven by her real motion and the wind
    const tgt = -clamp(acc, -4, 4) * 0.04 - j.vx * 0.05 + wind * 0.15;
    const tsw = [this.tails[0].step(tgt + Math.sin(t * 1.3) * 0.03, dt, 22, 4), this.tails[1].step(tgt + Math.sin(t * 1.3 + 1) * 0.03, dt, 22, 4)];
    janeHead(j, head, chin, hu, fe, f, skin, dim, t, detail, tsw);
    // rim light from the key light (sun / moon), on the side facing it
    if (detail && light > 0.3) { const rs = Fx.sun && Fx.sun.x > X0 ? 1 : -1; ctx.strokeStyle = rgba("#fff6e6", 0.22 * light); ctx.lineWidth = Math.max(1, hu * 0.05); ctx.beginPath(); ctx.moveTo(sh[0] + rs * hu * 0.88, sh[1] + hu * 0.2); ctx.bezierCurveTo(bust[0] + rs * hu * 0.95, bust[1], waist[0] + rs * hu * 0.5, waist[1], pel[0] + rs * hu * 1.05, hipY); ctx.stroke(); }
  },
};
function janeShoe(foot, f, O, dim, hu, k, lifting) {
  const c = shade(dim(O.shoes), k), pitch = lifting ? -0.25 : 0;
  ctx.save(); ctx.translate(foot[0], foot[1]); ctx.rotate(pitch * f); ctx.translate(-foot[0], -foot[1]);
  if (O.heel) {
    ctx.fillStyle = c; ctx.beginPath(); ctx.moveTo(foot[0] - f * hu * 0.14, foot[1] - hu * 0.12);
    ctx.quadraticCurveTo(foot[0] + f * hu * 0.12, foot[1] + hu * 0.05, foot[0] + f * hu * 0.48, foot[1] + hu * 0.34);
    ctx.lineTo(foot[0] + f * hu * 0.2, foot[1] + hu * 0.36); ctx.quadraticCurveTo(foot[0] - f * hu * 0.02, foot[1] + hu * 0.12, foot[0] - f * hu * 0.18, foot[1] + hu * 0.02); ctx.fill();
    ctx.strokeStyle = c; ctx.lineWidth = Math.max(1, hu * 0.06); ctx.beginPath(); ctx.moveTo(foot[0] - f * hu * 0.16, foot[1]); ctx.lineTo(foot[0] - f * hu * 0.14, foot[1] + hu * 0.36); ctx.stroke();
    ctx.fillStyle = rgba("#ffffff", 0.45 * k); ctx.beginPath(); ctx.ellipse(foot[0] + f * hu * 0.22, foot[1] + hu * 0.15, hu * 0.08, hu * 0.03, f * 0.6, 0, TAU); ctx.fill();
  } else {
    ctx.fillStyle = c; ctx.beginPath(); ctx.moveTo(foot[0] - f * hu * 0.18, foot[1] - hu * 0.55); ctx.lineTo(foot[0] + f * hu * 0.14, foot[1] - hu * 0.55);
    ctx.lineTo(foot[0] + f * hu * 0.18, foot[1] - hu * 0.05); ctx.quadraticCurveTo(foot[0] + f * hu * 0.5, foot[1] - hu * 0.02, foot[0] + f * hu * 0.52, foot[1] + hu * 0.1);
    ctx.lineTo(foot[0] - f * hu * 0.2, foot[1] + hu * 0.1); ctx.closePath(); ctx.fill();
    ctx.fillStyle = shade(c, 0.55); ctx.fillRect(Math.min(foot[0] - f * hu * 0.2, foot[0] + f * hu * 0.52), foot[1] + hu * 0.05, hu * 0.72, hu * 0.06);
    ctx.strokeStyle = rgba("#ffffff", 0.3 * k); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(foot[0] + f * hu * 0.02, foot[1] - hu * 0.45); ctx.lineTo(foot[0] + f * hu * 0.06, foot[1] - hu * 0.12); ctx.stroke();
  }
  ctx.restore();
}
function janeHead(j, head, chin, hu, fe, f, skin, dim, t, detail, tsw) {
  const L = JANE_LOOK, hx = head[0], hy = head[1], hr = hu * 0.5, fx = hx + fe * hr * 0.14;
  const hair = dim(L.hair), hairD = dim(L.hairD), hairHi = dim(L.hairHi);
  const tail = (s, sw0) => {
    const tx = hx + s * hr * 1.02, ty = hy - hr * 0.62, sw = sw0 * hu * 1.2;
    const g = ctx.createLinearGradient(tx, ty, tx + s * hu * 0.4, ty + hu * 2.6); g.addColorStop(0, hairHi); g.addColorStop(0.35, hair); g.addColorStop(1, hairD);
    ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(tx - s * hu * 0.05, ty);
    ctx.bezierCurveTo(tx + s * hu * 1.35, ty + hu * 0.25, tx + s * hu * 1.2 + sw * 0.6, ty + hu * 1.6, tx + s * hu * 0.95 + sw, ty + hu * 2.6);
    ctx.bezierCurveTo(tx + s * hu * 0.62 + sw * 0.8, ty + hu * 1.9, tx + s * hu * 0.3, ty + hu * 0.8, tx - s * hu * 0.1, ty + hu * 0.1); ctx.fill();
    if (detail) { ctx.lineWidth = 1; for (let k = 0; k < 5; k++) { ctx.strokeStyle = k % 2 ? rgba(L.hairHi, 0.55) : rgba(L.hairD, 0.6); ctx.beginPath(); ctx.moveTo(tx + s * hu * (0.05 + k * 0.12), ty + hu * 0.12); ctx.bezierCurveTo(tx + s * hu * (1.05 + k * 0.04), ty + hu * 0.8, tx + s * hu * (1.0 + k * 0.02) + sw * 0.6, ty + hu * 1.8, tx + s * hu * (0.85 + k * 0.02) + sw, ty + hu * 2.5); ctx.stroke(); } }
    ctx.fillStyle = L.tie; ctx.beginPath(); ctx.ellipse(tx, ty, hu * 0.1, hu * 0.14, 0, 0, TAU); ctx.fill();
    ctx.fillStyle = L.clip; ctx.beginPath(); const cx = tx - s * hu * 0.1, cy = ty - hu * 0.12, r = hu * 0.07;
    ctx.moveTo(cx, cy + r * 1.2); ctx.bezierCurveTo(cx - r * 1.6, cy, cx - r * 0.6, cy - r * 1.3, cx, cy - r * 0.4); ctx.bezierCurveTo(cx + r * 0.6, cy - r * 1.3, cx + r * 1.6, cy, cx, cy + r * 1.2); ctx.fill();
  };
  tail(-1, tsw[0]); tail(1, tsw[1]);
  for (const s of [-1, 1]) { const ex = hx + s * hr * 0.9, ey = hy + hr * 0.02; ctx.fillStyle = shade(skin, 0.9); ctx.beginPath(); ctx.ellipse(ex, ey, hr * 0.13, hr * 0.22, 0, 0, TAU); ctx.fill(); ctx.strokeStyle = dim(L.gold); ctx.lineWidth = Math.max(1, hu * 0.035); ctx.beginPath(); ctx.arc(ex, ey + hr * 0.42, hr * 0.2, 0, TAU); ctx.stroke(); }
  const fg = ctx.createRadialGradient(hx + fe * hr * 0.3, hy - hr * 0.35, hr * 0.1, hx, hy, hr * 1.25);
  fg.addColorStop(0, shade(skin, 1.06)); fg.addColorStop(0.7, skin); fg.addColorStop(1, shade(skin, 0.84));
  ctx.fillStyle = fg; ctx.beginPath();
  ctx.moveTo(hx - hr * 0.9, hy - hr * 0.2); ctx.bezierCurveTo(hx - hr * 0.95, hy - hr * 1.15, hx + hr * 0.95, hy - hr * 1.15, hx + hr * 0.9, hy - hr * 0.2);
  ctx.bezierCurveTo(hx + hr * 0.88, hy + hr * 0.45, hx + hr * 0.5, hy + hr * 0.85, chin[0] + fe * hr * 0.05, hy + hr * 1.02);
  ctx.bezierCurveTo(hx - hr * 0.5, hy + hr * 0.85, hx - hr * 0.88, hy + hr * 0.45, hx - hr * 0.9, hy - hr * 0.2); ctx.fill();
  ctx.strokeStyle = rgba("#7a4a40", 0.18); ctx.lineWidth = Math.max(1, hr * 0.06);
  ctx.beginPath(); ctx.moveTo(hx - f * hr * 0.85, hy + hr * 0.1); ctx.quadraticCurveTo(hx - f * hr * 0.6, hy + hr * 0.8, chin[0], hy + hr * 1.0); ctx.stroke();
  if (detail) {
    const eo = clamp(j.eye == null ? 1 : j.eye, 0.08, 1.2) * (j.blink ? 0.08 : 1), look = clamp(j.look_x || 0, -1, 1) * hr * 0.07;
    for (const s of [-1, 1]) { const bg = ctx.createRadialGradient(fx + s * hr * 0.46, hy + hr * 0.28, 0, fx + s * hr * 0.46, hy + hr * 0.28, hr * 0.34); bg.addColorStop(0, rgba(L.blush, 0.5)); bg.addColorStop(1, rgba(L.blush, 0)); ctx.fillStyle = bg; ctx.fillRect(fx + s * hr * 0.46 - hr * 0.35, hy - hr * 0.1, hr * 0.7, hr * 0.8); }
    for (const s of [-1, 1]) {
      const near = s === f, ex = fx + s * hr * 0.4 * (near ? 1 : 0.86) * Math.max(0.6, Math.abs(fe)), ey = hy - hr * 0.06, ew = hr * 0.3 * (near ? 1 : 0.84), eh = hr * 0.17 * eo;
      const sh2 = ctx.createRadialGradient(ex, ey - hr * 0.12, 0, ex, ey - hr * 0.12, ew * 1.3); sh2.addColorStop(0, rgba(L.shadow, 0.55)); sh2.addColorStop(1, rgba(L.shadow, 0));
      ctx.fillStyle = sh2; ctx.fillRect(ex - ew * 1.4, ey - hr * 0.45, ew * 2.8, hr * 0.5);
      const eyePath = () => { ctx.beginPath(); ctx.moveTo(ex - ew, ey); ctx.quadraticCurveTo(ex, ey - eh * 1.6, ex + ew, ey); ctx.quadraticCurveTo(ex, ey + eh * 1.2, ex - ew, ey); };
      ctx.fillStyle = "#fbf8f5"; eyePath(); ctx.fill();
      if (eo > 0.2) {
        const ir = Math.min(hr * 0.14, eh * 1.2), ix = ex + look, iy = ey + hr * 0.005;
        ctx.save(); eyePath(); ctx.clip();
        const ig = ctx.createRadialGradient(ix, iy, ir * 0.2, ix, iy, ir); ig.addColorStop(0, shade(L.iris, 1.35)); ig.addColorStop(0.7, L.iris); ig.addColorStop(1, shade(L.iris, 0.55));
        ctx.fillStyle = ig; ctx.beginPath(); ctx.arc(ix, iy, ir, 0, TAU); ctx.fill();
        ctx.fillStyle = "#0d0b0b"; ctx.beginPath(); ctx.arc(ix, iy, ir * 0.45, 0, TAU); ctx.fill();
        ctx.fillStyle = "#ffffff"; ctx.beginPath(); ctx.arc(ix - ir * 0.35, iy - ir * 0.35, ir * 0.22, 0, TAU); ctx.fill(); ctx.beginPath(); ctx.arc(ix + ir * 0.3, iy + ir * 0.25, ir * 0.1, 0, TAU); ctx.fill();
        ctx.restore();
      }
      ctx.strokeStyle = L.liner; ctx.lineWidth = Math.max(1.2, hr * 0.085);
      ctx.beginPath(); ctx.moveTo(ex - ew, ey); ctx.quadraticCurveTo(ex, ey - eh * 1.65, ex + ew, ey - eh * 0.1); ctx.lineTo(ex + s * ew * 1.35, ey - eh * 0.9 - hr * 0.05); ctx.stroke();
      ctx.lineWidth = Math.max(1, hr * 0.035);
      for (let k = 0; k < 5; k++) { const a = k / 4, lx = lerp(ex - ew * 0.7, ex + ew * 0.9, a), ly = ey - eh * (1.3 - Math.abs(a - 0.5)); ctx.beginPath(); ctx.moveTo(lx, ly); ctx.lineTo(lx + s * hr * 0.05, ly - hr * 0.09); ctx.stroke(); }
      ctx.strokeStyle = rgba("#ffffff", 0.7); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(ex - ew * 0.8, ey + eh * 0.5); ctx.quadraticCurveTo(ex, ey + eh * 1.15, ex + ew * 0.8, ey + eh * 0.4); ctx.stroke();
      const bi = (j.brow_in || 0) * hr * 0.12 * -s, bo = (j.brow_out || 0) * hr * 0.14;
      ctx.strokeStyle = dim(L.brow); ctx.lineWidth = Math.max(1.2, hr * 0.1); ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(ex - s * ew * 0.95, ey - hr * 0.3 - bo + bi); ctx.quadraticCurveTo(ex + s * ew * 0.2, ey - hr * 0.5 - bo, ex + s * ew * 1.1, ey - hr * 0.32 - bo * 0.6); ctx.stroke(); ctx.lineCap = "butt";
    }
    ctx.strokeStyle = rgba("#ffffff", 0.35); ctx.lineWidth = Math.max(1, hr * 0.05); ctx.beginPath(); ctx.moveTo(fx + fe * hr * 0.03, hy - hr * 0.12); ctx.lineTo(fx + fe * hr * 0.05, hy + hr * 0.22); ctx.stroke();
    ctx.fillStyle = shade(skin, 0.78); ctx.beginPath(); ctx.ellipse(fx + fe * hr * 0.1, hy + hr * 0.33, hr * 0.12, hr * 0.06, 0, 0, TAU); ctx.fill();
    ctx.fillStyle = shade(skin, 0.6); for (const s of [-1, 1]) { ctx.beginPath(); ctx.ellipse(fx + fe * hr * 0.1 + s * hr * 0.07, hy + hr * 0.36, hr * 0.03, hr * 0.02, 0, 0, TAU); ctx.fill(); }
    const sm = clamp(j.smile || 0, -1, 1), my = hy + hr * 0.6, mw = hr * 0.34, open = j.speaking ? hr * 0.06 * Math.abs(Math.sin(t * 14)) : 0;
    ctx.fillStyle = dim(L.lips);
    ctx.beginPath(); ctx.moveTo(fx - mw, my - sm * hr * 0.06); ctx.quadraticCurveTo(fx - mw * 0.45, my - hr * 0.12, fx - mw * 0.12, my - hr * 0.1);
    ctx.lineTo(fx, my - hr * 0.06); ctx.lineTo(fx + mw * 0.12, my - hr * 0.1); ctx.quadraticCurveTo(fx + mw * 0.45, my - hr * 0.12, fx + mw, my - sm * hr * 0.06);
    ctx.quadraticCurveTo(fx, my + hr * (0.02 + 0.03 * sm) + open, fx - mw, my - sm * hr * 0.06); ctx.fill();
    ctx.fillStyle = shade(dim(L.lips), 1.08);
    ctx.beginPath(); ctx.moveTo(fx - mw * 0.9, my - sm * hr * 0.05 + open); ctx.quadraticCurveTo(fx, my + hr * (0.22 + 0.06 * sm) + open, fx + mw * 0.9, my - sm * hr * 0.05 + open);
    ctx.quadraticCurveTo(fx, my + hr * 0.02 + open, fx - mw * 0.9, my - sm * hr * 0.05 + open); ctx.fill();
    ctx.fillStyle = rgba("#ffffff", 0.55); ctx.beginPath(); ctx.ellipse(fx + fe * hr * 0.06, my + hr * 0.1 + open, hr * 0.08, hr * 0.025, 0, 0, TAU); ctx.fill();
  } else {
    ctx.fillStyle = "#222"; for (const s of [-1, 1]) { ctx.beginPath(); ctx.arc(fx + s * hr * 0.36, hy - hr * 0.05, Math.max(0.8, hr * 0.09), 0, TAU); ctx.fill(); }
    ctx.fillStyle = dim(L.lips); ctx.beginPath(); ctx.ellipse(fx, hy + hr * 0.6, hr * 0.22, hr * 0.08, 0, 0, TAU); ctx.fill();
  }
  const hg = ctx.createLinearGradient(hx, hy - hr * 1.4, hx, hy - hr * 0.2); hg.addColorStop(0, hairHi); hg.addColorStop(0.45, hair); hg.addColorStop(1, hairD);
  ctx.fillStyle = hg; ctx.beginPath();
  ctx.moveTo(hx - hr * 1.0, hy - hr * 0.05); ctx.bezierCurveTo(hx - hr * 1.18, hy - hr * 1.35, hx + hr * 1.18, hy - hr * 1.35, hx + hr * 1.0, hy - hr * 0.05);
  ctx.bezierCurveTo(hx + hr * 0.9, hy - hr * 0.55, hx + hr * 0.4, hy - hr * 0.72, hx + fe * hr * 0.06, hy - hr * 0.8);
  ctx.bezierCurveTo(hx - hr * 0.4, hy - hr * 0.72, hx - hr * 0.9, hy - hr * 0.55, hx - hr * 1.0, hy - hr * 0.05); ctx.fill();
  if (detail) {
    ctx.strokeStyle = rgba(L.hairD, 0.7); ctx.lineWidth = Math.max(1, hr * 0.04); ctx.beginPath(); ctx.moveTo(hx + fe * hr * 0.06, hy - hr * 0.8); ctx.lineTo(hx + fe * hr * 0.02, hy - hr * 1.1); ctx.stroke();
    ctx.lineWidth = 1;
    for (let k = 0; k < 8; k++) { const s = k % 2 ? 1 : -1, a = (k >> 1) / 4; ctx.strokeStyle = k % 3 ? rgba(L.hairHi, 0.55) : rgba(L.hairD, 0.55); ctx.beginPath(); ctx.moveTo(hx + fe * hr * 0.04, hy - hr * (0.82 + a * 0.3)); ctx.quadraticCurveTo(hx + s * hr * (0.5 + a * 0.3), hy - hr * (1.1 - a * 0.1), hx + s * hr * (0.95 - a * 0.08), hy - hr * (0.35 + a * 0.3)); ctx.stroke(); }
  }
}

// ---------------------------------------------------------------- townspeople + visitors
const ROLE_LOOK = { farmer: { hat: "#c9b06a" }, guard: { helm: true }, priest: { robe: true }, trader: { pack: true }, visitor: {}, leader: { sash: "#c9a040" } };
const People = {
  steps: new Map(),
  draw(n, st, t, dt, lane) {
    const p = Cam.ppm * (1 - lane * 0.05), h = 1.72 * (n.scale || 1) * p, hu = h / 7.6, f = n.facing >= 0 ? 1 : -1;
    const R = ROLE_LOOK[n.role] || {}, X0 = sx(n.x), G = Cam.gy - lane * Cam.ppm, female = (hash(String(n.id)) % 2) === 0;
    let stp = this.steps.get(n.id); if (!stp) { stp = new Stepper(n.x, 0.1); this.steps.set(n.id, stp); }
    stp.update(n.x, 1, dt, clamp(0.45 + Math.abs(stp.v || 0) * 0.2, 0.4, 0.8), 0.1);
    ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.beginPath(); ctx.ellipse(X0, G + 1, hu * 0.9, hu * 0.13, 0, 0, TAU); ctx.fill();
    if (n.lie) { ctx.fillStyle = n.col; ctx.beginPath(); ctx.ellipse(X0, G - hu * 0.4, h * 0.42, hu * 0.45, 0, 0, TAU); ctx.fill(); ctx.fillStyle = n.skin; ctx.beginPath(); ctx.arc(X0 + f * h * 0.45, G - hu * 0.5, hu * 0.45, 0, TAU); ctx.fill(); return; }
    const legLen = 3.8 * hu, spread = stp.spread(n.x) * Cam.ppm, stand = Math.min(legLen * 0.99, Math.sqrt(Math.max(0.1, legLen * legLen - spread * spread)) * 0.99);
    const hipY = G - stand - hu * 0.08, pel = [X0, hipY], sh = [X0 + f * hu * 0.08, hipY - hu * 2.35], head = [sh[0] + f * hu * 0.06, sh[1] - hu * 0.95];
    const col = n.col, dark = shade(col, 0.7), legs = [];
    for (let i = 0; i < 2; i++) { const s = i ? 1 : -1, q = stp.f[i], hp = [pel[0] + s * hu * 0.3, hipY], foot = [sx(q.x) + s * hu * 0.08, G - hu * 0.08 - q.lift * Cam.ppm]; legs.push({ s, hp, knee: ik(hp, foot, legLen / 2, legLen / 2, f), foot }); }
    const legCol = R.robe ? col : shade(col, 0.55);
    for (const L of legs) { limb(ctx, [L.hp, L.knee, L.foot], [hu * 0.5, hu * 0.36, hu * 0.26], L.s < 0 ? shade(legCol, 0.82) : legCol); ctx.fillStyle = "#2a2019"; ctx.beginPath(); ctx.ellipse(L.foot[0] + f * hu * 0.18, L.foot[1] + hu * 0.02, hu * 0.3, hu * 0.12, 0, 0, TAU); ctx.fill(); }
    const tg = ctx.createLinearGradient(pel[0] - hu, 0, pel[0] + hu, 0); tg.addColorStop(f > 0 ? 0 : 1, shade(col, 0.8)); tg.addColorStop(f > 0 ? 1 : 0, shade(col, 1.06));
    ctx.fillStyle = tg; ctx.beginPath();
    const shw = hu * (female ? 0.72 : 0.9), wst = hu * (female ? 0.55 : 0.7), hpw = hu * (female ? 0.85 : 0.72), hem = R.robe ? G - hu * 0.3 : hipY + hu * (female ? 0.9 : 0.3);
    ctx.moveTo(sh[0] - shw, sh[1] + hu * 0.1); ctx.quadraticCurveTo(sh[0] - shw * 1.05, sh[1] + hu * 1.0, pel[0] - wst, hipY - hu * 0.8);
    ctx.quadraticCurveTo(pel[0] - hpw * 1.1, hipY, pel[0] - hpw * (R.robe || female ? 1.25 : 1), hem); ctx.lineTo(pel[0] + hpw * (R.robe || female ? 1.25 : 1), hem);
    ctx.quadraticCurveTo(pel[0] + hpw * 1.1, hipY, pel[0] + wst, hipY - hu * 0.8); ctx.quadraticCurveTo(sh[0] + shw * 1.05, sh[1] + hu * 1.0, sh[0] + shw, sh[1] + hu * 0.1);
    ctx.quadraticCurveTo(sh[0], sh[1] - hu * 0.1, sh[0] - shw, sh[1] + hu * 0.1); ctx.fill();
    ctx.fillStyle = dark; ctx.fillRect(pel[0] - wst * 1.05, hipY - hu * 0.85, wst * 2.1, hu * 0.16);
    if (R.sash) { ctx.strokeStyle = R.sash; ctx.lineWidth = hu * 0.15; ctx.beginPath(); ctx.moveTo(sh[0] - shw * 0.8, sh[1] + hu * 0.2); ctx.lineTo(pel[0] + wst, hipY - hu * 0.9); ctx.stroke(); }
    if (R.pack && n.moving) { ctx.fillStyle = "#6a4a2e"; ctx.fillRect(sh[0] - f * hu * 1.3, sh[1] + hu * 0.2, hu * 0.8, hu * 1.3); }
    // arms: counter-swing
    for (const s of [-1, 1]) {
      const shj = [sh[0] + s * shw * 0.85, sh[1] + hu * 0.2], opp = stp.f[s > 0 ? 0 : 1];
      let hand;
      if (n.wave && s > 0) hand = [shj[0] + f * hu * 0.5, shj[1] - hu * 2.0 + Math.sin(t * 12) * hu * 0.2];
      else { const a = clamp((opp.x - n.x) / 0.35, -1, 1) * 0.45 * (n.moving ? 1 : 0); hand = [shj[0] + f * Math.sin(a) * hu * 2.4, shj[1] + Math.cos(a) * hu * 2.5]; }
      limb(ctx, [shj, ik(shj, hand, hu * 1.3, hu * 1.25, -f), hand], [hu * 0.34, hu * 0.28, hu * 0.22], s < 0 ? shade(col, 0.8) : col);
      ctx.fillStyle = n.skin; ctx.beginPath(); ctx.arc(hand[0], hand[1] + hu * 0.1, hu * 0.16, 0, TAU); ctx.fill();
    }
    ctx.fillStyle = shade(n.skin, 0.85); ctx.fillRect(head[0] - hu * 0.17, sh[1] - hu * 0.4, hu * 0.34, hu * 0.5);
    const hr = hu * 0.52, fg = ctx.createRadialGradient(head[0] + f * hr * 0.3, head[1] - hr * 0.3, hr * 0.1, head[0], head[1], hr * 1.2);
    fg.addColorStop(0, shade(n.skin, 1.06)); fg.addColorStop(1, shade(n.skin, 0.86)); ctx.fillStyle = fg;
    ctx.beginPath(); ctx.ellipse(head[0], head[1], hr * 0.88, hr, 0, 0, TAU); ctx.fill();
    const hair = R.helm ? "#8a8a90" : n.hair;
    ctx.fillStyle = hair; ctx.beginPath(); ctx.ellipse(head[0] - f * hr * 0.1, head[1] - hr * 0.35, hr * 0.95, hr * 0.72, 0, Math.PI, 0); ctx.fill();
    if (female && !R.helm) { ctx.beginPath(); ctx.ellipse(head[0] - f * hr * 0.75, head[1] + hr * 0.4, hr * 0.35, hr * 1.0, 0, 0, TAU); ctx.fill(); }
    if (R.hat) { ctx.fillStyle = R.hat; ctx.beginPath(); ctx.ellipse(head[0], head[1] - hr * 0.8, hr * 1.5, hr * 0.26, 0, 0, TAU); ctx.fill(); ctx.fillRect(head[0] - hr * 0.7, head[1] - hr * 1.4, hr * 1.4, hr * 0.62); }
    if (hu > 7) {
      ctx.fillStyle = "#2a1f1a"; for (const s of [-1, 1]) { ctx.beginPath(); ctx.arc(head[0] + f * hr * 0.2 + s * hr * 0.3, head[1] - hr * 0.05, Math.max(0.8, hr * 0.08), 0, TAU); ctx.fill(); }
      ctx.strokeStyle = shade(n.skin, 0.6); ctx.lineWidth = Math.max(1, hr * 0.06); ctx.beginPath(); ctx.arc(head[0] + f * hr * 0.2, head[1] + hr * 0.3, hr * 0.2, 0.2, Math.PI - 0.2); ctx.stroke();
    }
    if (n.talking && Math.floor(t * 1.6) % 2 === 0) { const bx = head[0] + f * hu * 1.2, by = head[1] - hu * 1.2; ctx.fillStyle = "rgba(236,240,246,.92)"; ctx.beginPath(); ctx.ellipse(bx, by, hu * 0.6, hu * 0.4, 0, 0, TAU); ctx.fill(); ctx.fillStyle = "#56606e"; for (let k = -1; k <= 1; k++) { ctx.beginPath(); ctx.arc(bx + k * hu * 0.22, by, hu * 0.055, 0, TAU); ctx.fill(); } }
  },
};
