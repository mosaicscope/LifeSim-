# ============================================================================
# [NEW] STATE BRIDGE  -  Python simulation  ->  browser renderer
# ============================================================================
#
# Python stays the only brain and the only source of truth. This module
# publishes what the simulation says, in world units (metres), at the
# simulation's pace (10 Hz, never per render frame), to a browser renderer
# (acacia/web: HTML + Canvas, GPU-composited) that interpolates between
# snapshots and draws at the display's frame rate.
#
#   GET  /            the renderer page (index.html, renderer.js, style.css)
#   GET  /stream      Server-Sent Events: one JSON snapshot per sim publish
#   GET  /state       the latest snapshot (polling fallback)
#   GET  /static      slow-changing world description (region, trees, places)
#   POST /input       user intent from the renderer (e.g. right-click "go
#                     there"); applied on the Tk thread by EXISTING functions
#
# stdlib only (http.server + threads). The renderer never invents facts:
# every value it shows comes from these snapshots.

import http.server as _br_http
import socketserver as _br_ss
import threading as _br_thr
import json as _br_json
import os as _br_os
import sys as _br_sys
import time as _br_time
import shutil as _br_shutil
import subprocess as _br_sp
import webbrowser as _br_web

BRIDGE_PORT = int(_br_os.environ.get("ACACIA_BRIDGE_PORT", "47833"))
def _br_web_dir():
    """acacia/web - found from the package itself: the loader runs modules
    in a shared namespace, where __file__ is not this module's path."""
    cands = []
    pkg = _br_sys.modules.get("acacia")
    if pkg is not None and getattr(pkg, "__file__", None):
        cands.append(_br_os.path.join(_br_os.path.dirname(_br_os.path.abspath(pkg.__file__)), "web"))
    here = globals().get("__file__")
    if here:
        d = _br_os.path.dirname(_br_os.path.abspath(here))
        cands += [_br_os.path.join(d, "web"), _br_os.path.join(d, "acacia", "web")]
    cands.append(_br_os.path.join(_br_os.getcwd(), "acacia", "web"))
    for c in cands:
        if _br_os.path.isfile(_br_os.path.join(c, "index.html")):
            return c
    return cands[0] if cands else "web"


WEB_DIR = _br_web_dir()
_BR_HZ = 10.0


class StateBridge:
    def __init__(self):
        self.snap = b"{}"
        self.static = b"{}"
        self.static_key = None
        self.seq = 0
        self.cond = _br_thr.Condition()
        self.inbox = []
        self.lock = _br_thr.Lock()
        self.last_client = 0.0
        self.server = None

    def publish(self, snap):
        data = _br_json.dumps(snap, separators=(",", ":")).encode("utf-8")
        with self.cond:
            self.snap = data
            self.seq += 1
            self.cond.notify_all()

    def set_static(self, key, static):
        if key != self.static_key:
            self.static_key = key
            self.static = _br_json.dumps(static, separators=(",", ":")).encode("utf-8")

    def client_active(self):
        return _br_time.time() - self.last_client < 3.0

    def take_input(self):
        with self.lock:
            msgs, self.inbox = self.inbox, []
        return msgs

    # -- server -------------------------------------------------------------------------
    def start(self, port=BRIDGE_PORT):
        if self.server is not None:
            return True
        bridge = self

        class Handler(_br_http.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = self.path.split("?")[0]
                if path == "/stream":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    seen = -1
                    try:
                        while True:
                            with bridge.cond:
                                if bridge.seq == seen:
                                    bridge.cond.wait(timeout=1.0)
                                seq, data = bridge.seq, bridge.snap
                            bridge.last_client = _br_time.time()
                            if seq != seen:
                                seen = seq
                                self.wfile.write(b"data: " + data + b"\n\n")
                            else:
                                self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                    except Exception:
                        return
                if path == "/state":
                    bridge.last_client = _br_time.time()
                    return self._send(200, bridge.snap, "application/json")
                if path == "/static":
                    return self._send(200, bridge.static, "application/json")
                name = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
                web = WEB_DIR if _br_os.path.isfile(_br_os.path.join(WEB_DIR, "index.html")) else _br_web_dir()
                full = _br_os.path.normpath(_br_os.path.join(web, name))
                if not full.startswith(_br_os.path.normpath(web)) or not _br_os.path.isfile(full):
                    return self._send(404, b"not found", "text/plain")
                ctype = {"html": "text/html", "js": "application/javascript", "css": "text/css"}.get(
                    full.rsplit(".", 1)[-1], "application/octet-stream")
                with open(full, "rb") as fh:
                    return self._send(200, fh.read(), ctype + "; charset=utf-8")

            def do_POST(self):
                if self.path.split("?")[0] != "/input":
                    return self._send(404, b"", "text/plain")
                n = int(self.headers.get("Content-Length", "0") or 0)
                try:
                    msg = _br_json.loads(self.rfile.read(min(n, 65536)) or b"{}")
                    with bridge.lock:
                        bridge.inbox = (bridge.inbox + [msg])[-20:]
                    return self._send(200, b'{"ok":true}', "application/json")
                except Exception:
                    return self._send(400, b'{"ok":false}', "application/json")

        class Server(_br_ss.ThreadingMixIn, _br_http.HTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        for p in (port, port + 1, port + 2):
            try:
                self.server = Server(("127.0.0.1", p), Handler)
                self.port = p
                break
            except OSError:
                self.server = None
        if self.server is None:
            return False
        _br_thr.Thread(target=self.server.serve_forever, daemon=True).start()
        return True

    def url(self):
        return f"http://127.0.0.1:{getattr(self, 'port', BRIDGE_PORT)}/"


BRIDGE = StateBridge()


# ============================================================================
# Snapshot: the simulation, in metres
# ============================================================================

def _br_m(px):
    return round(px / WS.px, 3)


def _br_col(c, default="#888888"):
    return c if isinstance(c, str) and c.startswith("#") and len(c) == 7 else default


def br_snapshot(app):
    """Everything the renderer needs, straight from the live simulation."""
    cr, w, b = app.creature, app.world, app.brain
    life = _lf_life(app)
    sv = getattr(app, "survival", None)
    L = cr._loco
    here = _rw_here(app)
    G = w.ground
    wx = app.weather_sim.snapshot() if getattr(app, "weather_sim", None) else {}
    A = getattr(cr, "_affect", None) or {}
    e = b.emotion
    reach = getattr(cr, "_reach", None)
    dec = getattr(life, "decision", None) or {}
    lt = _br_time.localtime()
    jane = {
        "x": _br_m(cr.x), "vx": round(L.vx / WS.px, 3), "facing": 1 if L.facing >= 0 else -1,
        "speed": round(abs(L.vx) / WS.px, 3), "sit": round(float(getattr(L, "sit", 0.0)), 3),
        "sleeping": bool(getattr(life, "sleeping", False)), "inside": bool(getattr(cr, "_inside", False)),
        "behavior": cr.behavior, "emotion": e.emotion,
        "valence": round(e.valence, 3), "arousal": round(e.arousal, 3), "stress": round(e.stress, 3),
        "smile": round(float(A.get("smile", 0.0)), 3), "brow_in": round(float(A.get("brow_in", 0.0)), 3),
        "brow_out": round(float(A.get("brow_out", 0.0)), 3), "eye": round(float(A.get("eye", 1.0)), 3),
        "look_x": round(float(getattr(cr, "eye_yaw", 0.0)), 3), "look_y": round(float(getattr(cr, "eye_pitch", 0.0)), 3),
        "head_yaw": round(float(getattr(cr, "head_yaw", 0.0)), 3),
        "blink": bool(_br_time.time() < getattr(cr, "blink_until", 0)),
        "speaking": bool(getattr(cr, "speaking", 0) > 0),
        "outfit": cr._cloth_body().get("outfit", "normal"), "wet": round(cr._cloth_body().get("wet", 0.0), 2),
        "shiver": round(cr._cloth_body().get("shiver", 0.0), 2), "hunch": round(cr._cloth_body().get("hunch", 0.0), 2),
        "reach": [_br_m(reach[0]), _br_m(G - reach[1]), round(reach[2], 2)] if reach else None,
        "gaze": _br_m(cr.gaze[0]) if getattr(cr, "gaze", None) else None,
        "held": {k: int(sv.inv.get(k, 0)) for k in ("wood", "berries", "meat", "bow")} if sv else {},
        "needs": {"hunger": round(b.goals.hunger, 2), "thirst": round(b.goals.thirst, 2),
                  "energy": round(b.goals.energy, 2), "social": round(b.goals.social, 2)},
        "decision": {k: dec.get(k) for k in ("goal", "target", "reason", "need", "memory", "priority")} if dec else None,
        "action": _lv_action(app),
    }
    animals = []
    fa = getattr(app, "fauna", None)
    for a in (fa.animals if fa else []):
        p = getattr(a, "psy", None)
        R = p.rel_of("jane") if p is not None else {}
        op = life.animals.get(str(p.seed), {}) if p is not None else {}
        animals.append({
            "id": f"a{p.seed}" if p is not None else f"x{a.id}", "sp": a.sp, "x": _br_m(a.x),
            "vx": round(a.vx / WS.px, 3), "facing": 1 if a.facing >= 0 else -1, "state": a.state,
            "alt": round(a.alt / WS.px, 3), "scale": round(a.scale, 2), "fear": round(a.fear, 2),
            "trust": round(R.get("trust", 0.0), 2), "name": op.get("name"), "body": _br_col(a.S.get("body")),
            "belly": _br_col(a.S.get("belly")), "antlers": bool(a.sp == "deer" and a.id % 2 == 0 and a.scale > 0.8),
        })
    people = []
    for bd in getattr(app, "bodies", []) or []:
        if bd.npc is None and not getattr(bd, "extra", False):
            continue
        people.append({"id": bd.npc.id if bd.npc else f"c{id(bd) % 99999}", "name": bd.npc.name if bd.npc else "",
                       "role": bd.role, "x": _br_m(bd.x), "facing": bd.facing, "moving": bool(getattr(bd, "moving", False)),
                       "hidden": bool(bd.hidden), "lie": bd.lie > 0, "state": bd.state, "bubble": bd.bubble,
                       "talking": bool(getattr(bd, "talking", False)), "col": _br_col(bd.col), "skin": _br_col(bd.skin),
                       "hair": _br_col(bd.hair), "scale": round(bd.scale, 2)})
    for tv in getattr(app, "travellers", []) or []:
        people.append({"id": tv.npc.id if tv.npc else f"t{id(tv) % 99999}", "name": tv.name, "role": tv.kind,
                       "x": _br_m(tv.x), "facing": tv.dir, "moving": tv.stop <= 0, "hidden": False, "lie": False,
                       "state": tv.kind, "bubble": None, "talking": bool(getattr(tv, "talking", False)),
                       "wave": bool(getattr(tv, "wave", 0) > 0), "col": _br_col(tv.col), "skin": _br_col(tv.skin),
                       "hair": "#4a3424", "scale": 1.0})
    ob = getattr(app, "objects", None)
    fires = [{"id": f.oid, "x": _br_m(f.x), "lit": bool(f.lit), "intensity": round(f.intensity, 2),
              "fuel": round(f.fuel, 2)} for f in (ob.fires_in(here) if ob else [])]
    offerings = [{"x": _br_m(o["x"]), "amount": o["amount"], "kind": o.get("kind", "berries")}
                 for o in (getattr(fa, "_offerings", None) or [])] if fa else []
    h = life.home if here[0] == "valley" else None
    return {
        "t": round(life.clock, 2), "wall": _br_time.time(),
        "hour": lt.tm_hour + lt.tm_min / 60.0,
        "region": {"kind": here[0], "name": here[1], "width": _br_m(w.w)},
        "static_key": BRIDGE.static_key,
        "daypart": w.daypart, "light": round(w.light(), 3),
        "weather": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in wx.items()
                    if k in ("state", "cloud", "precip", "wind", "wind_dir", "fog", "temp", "flash", "sun", "storm",
                             "ground_wet")},
        "snow": bool(wx.get("temp", 10.0) < 0.5 and wx.get("precip", 0.0) > 0.15),
        "event": _br_event(life),
        "jane": jane, "animals": animals, "people": people, "fires": fires, "offerings": offerings,
        "home": {"x": _br_m(h["x"]), "stage": h["stage"], "cond": round(h["cond"], 2)} if h else None,
        "pois": [{"kind": p.kind, "name": p.name, "x": _br_m(p.x),
                  "available": bool(p.available()) if p.kind in ("food", "water") else True}
                 for p in getattr(w, "pois", [])],
    }


def _br_event(life):
    """Her latest real event (from the diary), if it is recent."""
    d = getattr(life, "diary", None) or []
    if d and _br_time.time() - d[-1][0] < 90:
        return d[-1][1]
    return None


_BR_BIOME = {"valley": "meadow", "road": "forest", "settlement": "town"}


def br_static(app):
    """The slow-changing world: region layout, trees, places, town plan."""
    w = app.world
    here = _rw_here(app)
    places = getattr(w, "_places", {}) or {}
    soc = getattr(app, "society", None)
    s = soc.sets.get(here[1]) if (soc and here[0] == "settlement") else None
    town = None
    if here[0] == "settlement":
        conv = lambda v: [_br_m(x) for x in v] if isinstance(v, (list, tuple)) else (_br_m(v) if isinstance(v, (int, float)) else None)
        town = {k: conv(v) for k, v in places.items() if k != "_w"}
        town["alive"] = bool(s and s.alive)
        town["damage"] = round(getattr(s, "damage", 0.0), 2) if s else 1.0
        town["graves"] = sum(1 for n in soc.npcs.values() if not n.alive and n.sett == here[1]) if soc else 0
    return {
        "key": BRIDGE.static_key, "region": {"kind": here[0], "name": here[1], "width": _br_m(w.w)},
        "biome": _BR_BIOME.get(here[0], "meadow"),
        "seed": (hash(here[1]) & 0xffffff) if here[0] != "valley" else 1337,
        "trees": [_br_m(x) for x in (getattr(w, "_tree_x", None) or [])],
        "dests": [{"name": d["name"], "kind": d["kind"], "x": _br_m(d["x"])} for d in getattr(w, "_dest", []) or []],
        "town": town,
    }


def _br_apply_input(app, msg):
    """User intent from the renderer, applied through the existing systems."""
    kind = msg.get("type")
    if kind == "point" and isinstance(msg.get("x"), (int, float)):
        cam = app._camera
        px = float(msg["x"]) * WS.px
        sx, sy = cam.world_to_screen(px, app.world.ground - 5)
        _up_point(app, sx, sy)


# ---- publishing at the simulation's pace --------------------------------------------------------
_br_prev_update = App._update_world


def _br_update(self, dt):
    _br_prev_update(self, dt)
    try:
        if BRIDGE.server is None and not getattr(self, "_br_tried", False):
            self._br_tried = True
            BRIDGE.start()
        for msg in BRIDGE.take_input():
            _br_apply_input(self, msg)
        self._br_acc = getattr(self, "_br_acc", 0.0) + dt
        if self._br_acc >= 1.0 / _BR_HZ:
            self._br_acc = 0.0
            w = self.world
            key = f"{_rw_here(self)}|{int(w.w)}|{len(getattr(w, '_tree_x', []) or [])}|{w.daypart}"
            BRIDGE.set_static(key, br_static(self))
            BRIDGE.publish(br_snapshot(self))
    except Exception:
        traceback.print_exc()


App._update_world = _br_update


# ---- while the GPU view is showing, Tk stops being the presentation -----------------------------
_br_prev_cr_draw = Creature.draw


def _br_cr_draw(self):
    if BRIDGE.client_active() and self.__dict__.get("_app_ref") is not None:
        n = self.__dict__.get("_br_n", 0) + 1
        self.__dict__["_br_n"] = n
        if n % 6:
            return                           # ~5 Hz: keeps _last_pose fresh for the sim, saves the CPU
    return _br_prev_cr_draw(self)


Creature.draw = _br_cr_draw


# ---- opening the view: a native-feeling window if possible ---------------------------------------
def br_open_view(app):
    if BRIDGE.server is None:
        BRIDGE.start()
    url = BRIDGE.url()
    viewer = _br_os.path.join(_br_web_dir(), "viewer.py")
    try:
        import webview  # noqa: F401  (pywebview: a native window, Edge WebView2 on Windows)
        _br_sp.Popen([_br_sys.executable, viewer, url])
        return "window"
    except Exception:
        pass
    cands = [_br_shutil.which(n) for n in ("msedge", "chrome", "google-chrome", "chromium", "chromium-browser")]
    cands += [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
    for exe in cands:
        if exe and _br_os.path.isfile(exe):
            try:
                _br_sp.Popen([exe, f"--app={url}", "--start-maximized"])
                return "app"
            except Exception:
                continue
    _br_web.open(url)
    return "browser"


_br_prev_build = _sc_build_world_tab


def _br_build_world_tab(app):
    _br_prev_build(app)
    bar = app.world_tab.winfo_children()[0]
    b = app._button(bar, "OPEN GPU VIEW", lambda: br_open_view(app), bg=C_ACCENT, fg=C_BG, pady=3)
    b.pack(side="left", padx=(0, 6))


_sc_build_world_tab = _br_build_world_tab
