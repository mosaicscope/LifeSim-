// ============================================================================
// ACACIA world renderer - minimal HUD
// Everything shown is read from the snapshot. Diagnostics (F3) show the
// renderer's measured frame rate - not an estimate.
// ============================================================================
"use strict";

const Hud = {
  diag: false, acc: 0, hover: null,
  el: { card: document.getElementById("hud-card"), tip: document.getElementById("tip"), diag: document.getElementById("diag"), wait: document.getElementById("wait") },
  esc(s) { return String(s == null ? "" : s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]); },
  waiting() { this.el.wait.classList.remove("hidden"); },
  update(st, dt) {
    this.el.wait.classList.add("hidden");
    this.acc += dt; if (this.acc < 0.25) return; this.acc = 0;
    const j = st.jane, d = j.decision || {}, n = j.needs || {};
    const needs = [["hungry", n.hunger], ["thirsty", n.thirst], ["tired", 1 - (n.energy == null ? 1 : n.energy)], ["lonely", n.social]].sort((a, b) => (b[1] || 0) - (a[1] || 0));
    const need = (needs[0][1] || 0) > 0.45 ? `${needs[0][0]} ${Math.round(needs[0][1] * 100)}%` : "";
    const rows = [];
    if (d.goal) rows.push(`<div class="goal">${this.esc(d.goal)}</div>`);
    rows.push(`<div class="act">${this.esc(j.action || j.emotion)}</div>`);
    const meta = [need, d.reason && d.reason !== need ? d.reason : ""].filter(Boolean).join(" · ");
    if (meta) rows.push(`<div class="meta">${this.esc(meta)}</div>`);
    if (st.event) rows.push(`<div class="event">${this.esc(st.event)}</div>`);
    this.el.card.innerHTML = rows.join("");
    if (this.diag) {
      const age = performance.now() - S.lastMsg;
      this.el.diag.textContent = `${S.fps.toFixed(0)} fps · frame ${S.frameMs.toFixed(1)} ms · js ${S.jsMs.toFixed(1)} ms · ${(st.animals || []).length} animals · ${(st.people || []).length} people · snapshot ${age.toFixed(0)} ms · zoom ${Cam.zoom.toFixed(2)} · ${st.region.name} (${World.biomeName}) · cache ${World.cache.size}`;
      this.el.diag.classList.remove("hidden");
    } else this.el.diag.classList.add("hidden");
    this.card(st);
  },
  card(st) {
    if (!this.hover) { this.el.tip.classList.add("hidden"); return; }
    const wx = toWorldX(this.hover[0]); let best = null, bd = 1.0;
    for (const a of st.animals || []) { const dd = Math.abs(a.x - wx); if (dd < bd && a.sp !== "firefly" && a.sp !== "butterfly") { bd = dd; best = { t: a.name || a.sp, l: `${a.state} · trust ${Math.round(a.trust * 100)}% · fear ${Math.round(a.fear * 100)}%` }; } }
    for (const n of st.people || []) { const dd = Math.abs(n.x - wx); if (!n.hidden && dd < bd) { bd = dd; best = { t: n.name || n.role, l: n.role }; } }
    if (Math.abs(st.jane.x - wx) < Math.min(bd, 0.5)) best = { t: "Jane", l: st.jane.emotion };
    if (!best) { this.el.tip.classList.add("hidden"); return; }
    this.el.tip.innerHTML = `<b>${this.esc(best.t)}</b><span>${this.esc(best.l)}</span>`;
    this.el.tip.style.left = this.hover[0] + 14 + "px"; this.el.tip.style.top = this.hover[1] + 12 + "px"; this.el.tip.classList.remove("hidden");
  },
};
cv.addEventListener("mousemove", e => { Hud.hover = [e.clientX, e.clientY]; });
cv.addEventListener("mouseleave", () => { Hud.hover = null; });
document.getElementById("z-in").onclick = () => { Cam.zoomT = clamp(Cam.zoomT * 1.2, 0.55, 2.6); };
document.getElementById("z-out").onclick = () => { Cam.zoomT = clamp(Cam.zoomT / 1.2, 0.55, 2.6); };
document.getElementById("follow").onclick = () => setMode(Cam.mode === "follow" ? "free" : "follow");
document.getElementById("full").onclick = () => toggleFull();
start();
