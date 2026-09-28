// ============================================================================
// ACACIA world renderer - core
// Python is the brain and the source of truth. This file receives its
// snapshots (metres, 10 Hz, SSE), interpolates them, runs the camera and the
// frame loop. Other files: world.js (environment), jane.js (people),
// fauna.js (animals), fx.js (light/weather), hud.js (overlay).
// ============================================================================
"use strict";

const cv = document.getElementById("world");
const ctx = cv.getContext("2d", { alpha: false });
let W = 0, H = 0, DPR = 1;

// ---------------------------------------------------------------- utilities
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = t => t * t * (3 - 2 * t);
const TAU = Math.PI * 2;
function hexRgb(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function rgbHex(r, g, b) { return "#" + ((1 << 24) | (Math.round(clamp(r, 0, 255)) << 16) | (Math.round(clamp(g, 0, 255)) << 8) | Math.round(clamp(b, 0, 255))).toString(16).slice(1); }
function mix(a, b, t) { const A = hexRgb(a), B = hexRgb(b); return rgbHex(lerp(A[0], B[0], t), lerp(A[1], B[1], t), lerp(A[2], B[2], t)); }
function shade(a, f) { const A = hexRgb(a); return rgbHex(A[0] * f, A[1] * f, A[2] * f); }
function rgba(h, a) { const A = hexRgb(h); return `rgba(${A[0]},${A[1]},${A[2]},${a})`; }
function rng(seed) { let s = (seed >>> 0) || 1; return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 100000) / 100000; }; }
function hash(str) { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function noise1(seed) {
  const r = rng(seed), v = []; for (let i = 0; i < 512; i++) v.push(r());
  return x => { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(v[i & 511], v[(i + 1) & 511], u); };
}
function offscreen(w, h) {
  const c = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(Math.max(1, w | 0), Math.max(1, h | 0)) : document.createElement("canvas");
  if (!(typeof OffscreenCanvas !== "undefined" && c instanceof OffscreenCanvas)) { c.width = Math.max(1, w | 0); c.height = Math.max(1, h | 0); }
  return c;
}
// tapered limb through joints (used by people and animals)
function limb(g, pts, ws, col) {
  const L = [], R = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    let nx = -(b[1] - a[1]), ny = b[0] - a[0]; const n = Math.hypot(nx, ny) || 1; nx /= n; ny /= n;
    L.push([pts[i][0] + nx * ws[i] / 2, pts[i][1] + ny * ws[i] / 2]); R.push([pts[i][0] - nx * ws[i] / 2, pts[i][1] - ny * ws[i] / 2]);
  }
  g.fillStyle = col; g.beginPath(); g.moveTo(L[0][0], L[0][1]);
  for (let i = 1; i < L.length; i++) g.quadraticCurveTo(L[i - 1][0], L[i - 1][1], (L[i - 1][0] + L[i][0]) / 2, (L[i - 1][1] + L[i][1]) / 2);
  g.lineTo(L[L.length - 1][0], L[L.length - 1][1]); g.lineTo(R[R.length - 1][0], R[R.length - 1][1]);
  for (let i = R.length - 2; i >= 0; i--) g.quadraticCurveTo(R[i + 1][0], R[i + 1][1], (R[i + 1][0] + R[i][0]) / 2, (R[i + 1][1] + R[i][1]) / 2);
  g.lineTo(R[0][0], R[0][1]); g.closePath(); g.fill();
  g.beginPath(); g.arc(pts[pts.length - 1][0], pts[pts.length - 1][1], ws[ws.length - 1] / 2, 0, TAU); g.fill();
  g.beginPath(); g.arc(pts[0][0], pts[0][1], ws[0] / 2, 0, TAU); g.fill();
}
function ik(root, tgt, l1, l2, dir) {                        // 2-bone IK; bend toward dir (+1 = +x)
  const dx = tgt[0] - root[0], dy = tgt[1] - root[1]; let d = Math.hypot(dx, dy); d = clamp(d, Math.abs(l1 - l2) + 1e-3, (l1 + l2) * 0.9995);
  const a = Math.acos(clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1)), base = Math.atan2(dy, dx), ang = base - a * dir;
  return [root[0] + Math.cos(ang) * l1, root[1] + Math.sin(ang) * l1];
}

// ---------------------------------------------------------------- simulation state
const S = { snaps: [], stat: null, statKey: null, lastMsg: 0, fps: 60, frameMs: 0, jsMs: 0, regionChangedAt: -1e9 };
function onSnap(s) {
  s._rt = performance.now();
  const prev = S.snaps[S.snaps.length - 1];
  if (prev && prev.region.name !== s.region.name) { S.snaps = []; S.regionChangedAt = s._rt; }
  S.snaps.push(s); if (S.snaps.length > 40) S.snaps.shift();
  S.lastMsg = s._rt;
  if (s.static_key !== S.statKey) {
    S.statKey = s.static_key;
    fetch("/static").then(r => r.json()).then(st => { S.stat = st; World.build(st); }).catch(() => {});
  }
}
function connect() {
  if (typeof EventSource !== "undefined") {
    const es = new EventSource("/stream");
    es.onmessage = e => { try { onSnap(JSON.parse(e.data)); } catch (err) {} };
    es.onerror = () => { es.close(); setTimeout(connect, 1500); };
  } else {
    const poll = () => fetch("/state").then(r => r.json()).then(onSnap).catch(() => {}).finally(() => setTimeout(poll, 100));
    poll();
  }
}
// render ~120 ms behind the newest snapshot, interpolating positions AND velocities
const DELAY = 120;
function lerpList(A, B, t) {
  const m = new Map(); for (const a of A || []) m.set(a.id, a);
  return (B || []).map(b => { const a = m.get(b.id); return a ? Object.assign({}, b, { x: lerp(a.x, b.x, t), alt: lerp(a.alt || 0, b.alt || 0, t), vx: lerp(a.vx || 0, b.vx || 0, t) }) : b; });
}
function frameState(now) {
  const n = S.snaps.length; if (!n) return null;
  const t = now - DELAY;
  let a = S.snaps[0], b = S.snaps[n - 1];
  for (let i = n - 1; i > 0; i--) { if (S.snaps[i - 1]._rt <= t) { a = S.snaps[i - 1]; b = S.snaps[i]; break; } }
  const k = clamp((t - a._rt) / Math.max(1, b._rt - a._rt), 0, 1);
  const out = Object.assign({}, b);
  out.jane = Object.assign({}, b.jane, { x: lerp(a.jane.x, b.jane.x, k), vx: lerp(a.jane.vx, b.jane.vx, k), sit: lerp(a.jane.sit, b.jane.sit, k) });
  out.animals = lerpList(a.animals, b.animals, k);
  out.people = lerpList(a.people, b.people, k);
  out.hour = lerp(a.hour, b.hour, k); out.light = lerp(a.light, b.light, k);
  return out;
}

// ---------------------------------------------------------------- camera
// Jane ~27% of the view height at zoom 1; follow with look-ahead, a travel
// third, and gentle framing of whatever she is actually engaged with.
const Cam = { x: 0, vx: 0, zoom: 1, zoomT: 1, mode: "follow", ppm: 60, gy: 0, basePpm: 60, fade: 0, lastRegion: null, manualUntil: 0 };
function camUpdate(st, dt) {
  Cam.zoom += (Cam.zoomT - Cam.zoom) * (1 - Math.exp(-dt / 0.22));
  Cam.basePpm = H * 0.27 / 1.70;
  Cam.ppm = Cam.basePpm * Cam.zoom;
  Cam.gy = H * 0.8;
  const viewM = W / Cam.ppm, width = st.region.width, j = st.jane;
  if (Cam.lastRegion !== st.region.name) { Cam.lastRegion = st.region.name; Cam.x = j.x; Cam.vx = 0; Cam.fade = 1; }
  let tx = Cam.x, tvx = 0;
  const following = Cam.mode === "follow" && performance.now() > Cam.manualUntil;
  if (following) {
    const moving = Math.abs(j.vx) > 0.25, dir = j.vx >= 0 ? 1 : -1;
    tx = j.x + (moving ? dir * viewM * 0.12 : 0) + clamp(j.vx * 0.8, -viewM * 0.08, viewM * 0.08);
    tvx = j.vx;                                                // feed-forward: no steady-state lag while she walks
    // framing: include the animal / person her real decision targets, if close
    const d = j.decision && j.decision.target;
    if (d && !moving) {
      const cand = (st.animals || []).concat(st.people || []).find(e => e.name === d || (d.includes && d.includes(e.sp || "~")));
      if (cand && Math.abs(cand.x - j.x) < viewM * 0.6) tx = lerp(tx, (j.x + cand.x) / 2, 0.45);
    }
  }
  if (viewM < width) tx = clamp(tx, viewM / 2, width - viewM / 2); else tx = width / 2;
  // critically damped spring tracking a moving target: no snapping, no jitter, no lag
  const w0 = 2.4, acc = w0 * w0 * (tx - Cam.x) + 2 * w0 * (tvx - Cam.vx);
  Cam.vx += acc * dt; Cam.x += Cam.vx * dt;
  if (following) {                                             // she never leaves the frame
    const box = viewM * 0.36, off = j.x - Cam.x;
    if (Math.abs(off) > box) { Cam.x = j.x - Math.sign(off) * box; Cam.vx = j.vx; }
  }
  if (viewM < width) Cam.x = clamp(Cam.x, viewM / 2, width - viewM / 2);
  Cam.fade = Math.max(0, Cam.fade - dt * 1.6);
}
const sx = xm => (xm - Cam.x) * Cam.ppm + W / 2;
const sy = ym => Cam.gy - ym * Cam.ppm;
const toWorldX = px => (px - W / 2) / Cam.ppm + Cam.x;
function inView(xm, marginM) { return Math.abs(xm - Cam.x) < W / Cam.ppm / 2 + (marginM || 4); }
// depth lanes: entities at the same x stand at slightly different depths
// (presentation only - the simulation's x is untouched)
function laneOf(id) {                                         // everyone else keeps clear of Jane's lane (0)
  if (id === "jane") return 0; const u = (hash(String(id)) % 1000) / 1000 * 2 - 1;
  return Math.sign(u || 1) * (0.38 + 0.62 * Math.abs(u));
}
function laneY(z) { return z * 0.32; }                        // metres "into" the scene

// ---------------------------------------------------------------- input (intent only, sent to Python)
cv.addEventListener("contextmenu", e => { e.preventDefault(); fetch("/input", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: "point", x: toWorldX(e.clientX) }) }).catch(() => {}); });
cv.addEventListener("wheel", e => { e.preventDefault(); Cam.zoomT = clamp(Cam.zoomT * Math.pow(1.12, -e.deltaY / 100), 0.55, 2.6); }, { passive: false });
let drag = null;
cv.addEventListener("mousedown", e => { if (e.button === 0) drag = [e.clientX, Cam.x]; });
window.addEventListener("mouseup", () => { drag = null; });
window.addEventListener("mousemove", e => { if (drag) { Cam.x = drag[1] - (e.clientX - drag[0]) / Cam.ppm; Cam.vx = 0; if (Cam.mode === "follow") Cam.manualUntil = performance.now() + 5000; } });
window.addEventListener("keydown", e => {
  if (e.key === "f" || e.key === "F") setMode(Cam.mode === "follow" ? "free" : "follow");
  else if (e.key === "+" || e.key === "=") Cam.zoomT = clamp(Cam.zoomT * 1.2, 0.55, 2.6);
  else if (e.key === "-") Cam.zoomT = clamp(Cam.zoomT / 1.2, 0.55, 2.6);
  else if (e.key === "ArrowLeft" || e.key === "a") { Cam.x -= 3; Cam.vx = 0; Cam.manualUntil = performance.now() + 5000; }
  else if (e.key === "ArrowRight" || e.key === "d") { Cam.x += 3; Cam.vx = 0; Cam.manualUntil = performance.now() + 5000; }
  else if (e.key === "F3") { e.preventDefault(); Hud.diag = !Hud.diag; }
  else if (e.key === "F11" || e.key === "Enter" && e.altKey) { e.preventDefault(); toggleFull(); }
});
function setMode(m) { Cam.mode = m; Cam.manualUntil = 0; const b = document.getElementById("follow"); if (b) b.className = m === "follow" ? "on" : ""; }
function toggleFull() { if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => {}); else document.exitFullscreen(); }

// ---------------------------------------------------------------- frame loop
function resize() {
  DPR = Math.min(window.devicePixelRatio || 1, 2); W = window.innerWidth; H = window.innerHeight;
  cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  World.invalidate(); Fx.resize();
}
window.addEventListener("resize", resize);
let last = performance.now();
function frame(now) {
  const t0 = performance.now();
  const dt = clamp((now - last) / 1000, 0, 0.1); last = now;
  S.frameMs = lerp(S.frameMs, dt * 1000, 0.08); S.fps = 1000 / Math.max(1, S.frameMs);
  const st = frameState(now);
  if (!st || !S.stat || S.stat.region.name !== st.region.name) {
    ctx.fillStyle = "#0c0e13"; ctx.fillRect(0, 0, W, H); Hud.waiting(); requestAnimationFrame(frame); return;
  }
  const t = now / 1000;
  camUpdate(st, dt);
  Fx.grade(st);
  World.drawBack(st, t, dt);                                   // sky, clouds, far + mid layers, ground, trees, props
  const ents = [];
  for (const a of st.animals || []) if (inView(a.x, 3)) ents.push({ z: laneOf(a.id), kind: "a", e: a });
  for (const n of st.people || []) if (!n.hidden && inView(n.x, 3)) ents.push({ z: laneOf(n.id), kind: "p", e: n });
  if (!st.jane.inside) ents.push({ z: 0, kind: "j", e: st.jane });
  ents.sort((a, b) => b.z - a.z);                              // far lanes first
  for (const it of ents) {
    const lane = laneY(it.z);
    if (it.kind === "a") Fauna.draw(it.e, st, t, dt, lane);
    else if (it.kind === "p") People.draw(it.e, st, t, dt, lane);
    else Jane.draw(it.e, st, t, dt);
  }
  World.drawFront(st, t, dt);                                  // foreground grass/flowers over feet
  Fx.draw(st, t, dt);                                          // weather, fog, night + lights, grading
  if (Cam.fade > 0) { ctx.fillStyle = `rgba(8,10,14,${Cam.fade})`; ctx.fillRect(0, 0, W, H); }
  S.jsMs = lerp(S.jsMs, performance.now() - t0, 0.08);
  Hud.update(st, dt);
  requestAnimationFrame(frame);
}
function start() { resize(); connect(); requestAnimationFrame(frame); }
