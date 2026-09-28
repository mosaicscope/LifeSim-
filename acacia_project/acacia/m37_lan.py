# ============================================================================
# [NEW] ACACIA LOCAL NETWORK  (patch layer, loaded after m36)
# ============================================================================
#
# LAN-only shared world. One ACACIA hosts, others on the same network find it
# and join; each creature then appears in every connected world.
#
#   discovery  UDP 47811: a client broadcasts "ACACIA_FIND?"; a host answers
#              with its name/port. Only private/loopback/link-local senders
#              are answered.
#   session    TCP 47812, newline-delimited JSON. The host accepts ONLY
#              private/loopback/link-local peers. Nothing is opened to the
#              internet: no UPnP, no port mapping, no relay.
#   pairing    host shows a random 3-digit PIN; the client must send it;
#              then the HOST USER must explicitly accept. The client's
#              explicit step is pressing CONNECT with that PIN. The PIN is a
#              pairing code against mis-joins on a shared LAN - NOT security.
#              5 wrong PINs from one address blocks it for the session.
#   sync       ~10 Hz "state" messages built from a WHITELIST (position,
#              facing, behaviour, emotion, expression numbers, clothing,
#              appearance seed). Brains, memories, settings and keys are never
#              read by this module. Incoming messages are sanitised the same way.
#   safety     peer timeout 6 s, pairing timeout 45 s, auto-reconnect (3 tries,
#              same PIN), "bye" on clean shutdown, duplicate protection
#              (self-join, same install twice, second host on one machine).

import socket as _ln_socket
import threading as _ln_threading
import queue as _ln_queue
import secrets as _ln_secrets
import ipaddress as _ln_ipaddress
import uuid as _ln_uuid
import json as _ln_json
import time as _ln_time

LAN_PROTO = "acacia-lan/1"
LAN_DISC_PORT = 47811
LAN_GAME_PORT = 47812
LAN_MAX_LINE = 8192
LAN_PEER_TIMEOUT = 6.0
LAN_CONFIRM_TIMEOUT = 45.0
LAN_MAX_PIN_TRIES = 5
LAN_PROBE = b"ACACIA_FIND?"

_LN_AFF_KEYS = ("smile", "open", "round", "wobble", "asym", "brow_in", "knit", "brow_out",
                "eye", "gaze", "shoulder", "chest", "tilt", "energy", "flush", "pallor",
                "tension", "breath")
_LN_OUTFITS = ("light", "normal", "warm", "rain")
_LN_BEHAVIORS = ("idle", "move", "rest", "alert", "curious")


def lan_local_ip():
    """The address other LAN machines would reach us on. The UDP 'connect'
    sends no packet; it only asks the OS which interface it would use."""
    s = _ln_socket.socket(_ln_socket.AF_INET, _ln_socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def lan_is_local(ip):
    try:
        a = _ln_ipaddress.ip_address(ip)
        return a.is_private or a.is_loopback or a.is_link_local
    except Exception:
        return False


def _ln_num(v, lo, hi, default=0.0):
    try:
        f = float(v)
        if f != f:
            return default
        return max(lo, min(hi, f))
    except Exception:
        return default


def _ln_str(v, n=40):
    return str(v)[:n] if isinstance(v, (str, int, float)) else ""


def lan_clean_state(obj):
    """Whitelist + clamp. Used for what we SEND and what we RECEIVE."""
    if not isinstance(obj, dict):
        return {}
    aff = obj.get("affect") if isinstance(obj.get("affect"), dict) else {}
    beh = obj.get("behavior")
    out = {
        "nx": _ln_num(obj.get("nx"), 0.0, 1.0, 0.5),
        "facing": _ln_num(obj.get("facing"), -1.0, 1.0, 1.0),
        "behavior": beh if beh in _LN_BEHAVIORS else "idle",
        "emotion": _ln_str(obj.get("emotion"), 16),
        "intensity": _ln_num(obj.get("intensity"), 0.0, 1.0, 0.3),
        "affect": {k: _ln_num(aff.get(k), -2.0, 3.0, 0.0) for k in _LN_AFF_KEYS if k in aff},
        "outfit": obj.get("outfit") if obj.get("outfit") in _LN_OUTFITS else "normal",
        "wet": _ln_num(obj.get("wet"), 0.0, 1.0, 0.0),
        "speaking": _ln_num(obj.get("speaking"), 0.0, 10.0, 0.0),
        "action": _ln_str(obj.get("action"), 24),
    }
    return out


def lan_clean_look(obj):
    obj = obj if isinstance(obj, dict) else {}
    return {"seed": int(_ln_num(obj.get("seed"), 0, 2 ** 31 - 1, 1)),
            "name": _ln_str(obj.get("name"), 24) or "someone"}


class _LanConn:
    def __init__(self, sock, addr):
        self.sock, self.addr = sock, addr
        self.id = None
        self.install = None
        self.name = ""
        self.look = {}
        self.stage = "handshake"         # handshake -> pending -> live
        self.last = _ln_time.time()
        self.since = _ln_time.time()
        self.alive = True
        self.lock = _ln_threading.Lock()
        self.graceful = False

    def send(self, obj):
        if not self.alive:
            return False
        try:
            data = (_ln_json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
            with self.lock:
                self.sock.sendall(data)
            return True
        except Exception:
            self.alive = False
            return False

    def close(self):
        self.alive = False
        try:
            self.sock.shutdown(_ln_socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


class LanNode:
    """All socket work runs on background threads; everything that touches
    app state happens in poll(), which the Tk loop calls on the main thread."""

    def __init__(self, install_id, name, look, game_port=LAN_GAME_PORT,
                 disc_port=LAN_DISC_PORT):
        self.install_id = str(install_id)
        self.id = f"{self.install_id}:{_ln_uuid.uuid4().hex[:6]}"
        self.name = name
        self.look = lan_clean_look(dict(look, name=name))
        self.game_port, self.disc_port = game_port, disc_port
        self.role = "idle"               # idle | host | joining | client
        self.pin = None
        self.q = _ln_queue.Queue()
        self.peers = {}                  # id -> _LanConn (live, directly connected)
        self.pending = {}                # id -> _LanConn awaiting host confirmation
        self.remote = {}                 # id -> {"name", "look"} everyone we can see
        self.found = []
        self.error = ""
        self._stop = _ln_threading.Event()
        self._srv = self._udp = None
        self._tries = {}
        self._accepted = set()           # installs accepted this session (reconnects)
        self._client = None
        self._join_args = None
        self._reconnect_at = None
        self._reconnects = 0

    # -- host -------------------------------------------------------------
    def host(self):
        if self.role != "idle":
            self.error = "already in a session"
            return False
        try:
            srv = _ln_socket.socket(_ln_socket.AF_INET, _ln_socket.SOCK_STREAM)
            # no SO_REUSEADDR on the game port: a second ACACIA hosting on the
            # same machine must fail loudly (duplicate-instance protection)
            srv.bind(("", self.game_port))
            srv.listen(4)
            srv.settimeout(0.5)
        except OSError:
            self.error = "another ACACIA is already hosting on this computer (port busy)"
            return False
        try:
            udp = _ln_socket.socket(_ln_socket.AF_INET, _ln_socket.SOCK_DGRAM)
            udp.setsockopt(_ln_socket.SOL_SOCKET, _ln_socket.SO_REUSEADDR, 1)
            udp.bind(("", self.disc_port))
            udp.settimeout(0.5)
        except OSError:
            udp = None                   # discovery unavailable; direct join still works
        self._srv, self._udp = srv, udp
        self._stop.clear()
        self.pin = f"{_ln_secrets.randbelow(1000):03d}"
        self.role, self.error = "host", ""
        _ln_threading.Thread(target=self._accept_loop, daemon=True).start()
        if udp is not None:
            _ln_threading.Thread(target=self._udp_loop, daemon=True).start()
        return True

    def _accept_loop(self):
        while not self._stop.is_set():
            try:
                sock, addr = self._srv.accept()
            except _ln_socket.timeout:
                continue
            except Exception:
                break
            if not lan_is_local(addr[0]):
                sock.close()             # LAN only, always
                continue
            sock.setsockopt(_ln_socket.IPPROTO_TCP, _ln_socket.TCP_NODELAY, 1)
            conn = _LanConn(sock, addr)
            _ln_threading.Thread(target=self._reader, args=(conn,), daemon=True).start()

    def _udp_loop(self):
        while not self._stop.is_set():
            try:
                data, addr = self._udp.recvfrom(256)
            except _ln_socket.timeout:
                continue
            except Exception:
                break
            if data == LAN_PROBE and lan_is_local(addr[0]) and self.role == "host":
                info = {"proto": LAN_PROTO, "id": self.id, "name": self.name,
                        "port": self.game_port, "players": 1 + len(self.peers)}
                try:
                    self._udp.sendto(_ln_json.dumps(info).encode(), addr)
                except Exception:
                    pass

    # -- discovery ----------------------------------------------------------
    def find(self, timeout=1.2, extra=("127.0.0.1",)):
        """Blocking probe; call from a thread (find_async) in the UI."""
        s = _ln_socket.socket(_ln_socket.AF_INET, _ln_socket.SOCK_DGRAM)
        s.setsockopt(_ln_socket.SOL_SOCKET, _ln_socket.SO_BROADCAST, 1)
        s.settimeout(0.2)
        targets = ["255.255.255.255"] + list(extra)
        ip = lan_local_ip()
        if ip.count(".") == 3 and not ip.startswith("127."):
            targets.append(ip.rsplit(".", 1)[0] + ".255")
        for t in targets:
            try:
                s.sendto(LAN_PROBE, (t, self.disc_port))
            except Exception:
                pass
        hosts, end = {}, _ln_time.time() + timeout
        while _ln_time.time() < end:
            try:
                data, addr = s.recvfrom(1024)
            except _ln_socket.timeout:
                continue
            except Exception:
                break
            if not lan_is_local(addr[0]):
                continue
            try:
                info = _ln_json.loads(data.decode())
            except Exception:
                continue
            if info.get("proto") != LAN_PROTO or info.get("id") == self.id:
                continue
            hosts[info["id"]] = {"id": info["id"], "name": _ln_str(info.get("name"), 24),
                                 "ip": addr[0], "port": int(_ln_num(info.get("port"), 1, 65535,
                                                                    LAN_GAME_PORT)),
                                 "players": int(_ln_num(info.get("players"), 0, 64, 1))}
        s.close()
        self.found = list(hosts.values())
        return self.found

    def find_async(self):
        def run():
            self.q.put(("found", self.find()))
        _ln_threading.Thread(target=run, daemon=True).start()

    # -- client --------------------------------------------------------------
    def join(self, ip, port, pin):
        if self.role != "idle":
            self.error = "leave the current session first"
            return False
        if not lan_is_local(ip):
            self.error = "only local-network addresses can be joined"
            return False
        pin = "".join(ch for ch in str(pin) if ch.isdigit())
        if len(pin) != 3:
            self.error = "the PIN is 3 digits"
            return False
        self._join_args = (ip, int(port), pin)
        self._reconnects = 0
        self._stop.clear()
        self.role, self.error = "joining", ""
        self._connect()
        return True

    def _connect(self):
        ip, port, pin = self._join_args

        def run():
            try:
                sock = _ln_socket.create_connection((ip, port), timeout=4.0)
                sock.setsockopt(_ln_socket.IPPROTO_TCP, _ln_socket.TCP_NODELAY, 1)
            except Exception:
                self.q.put(("connect_failed", None))
                return
            conn = _LanConn(sock, (ip, port))
            self._client = conn
            conn.send({"t": "hello", "proto": LAN_PROTO, "id": self.id,
                       "install": self.install_id, "name": self.name, "pin": pin,
                       "look": self.look})
            self._reader(conn)
        _ln_threading.Thread(target=run, daemon=True).start()

    # -- shared reader ----------------------------------------------------------
    def _reader(self, conn):
        buf = b""
        conn.sock.settimeout(1.0)
        while conn.alive and not self._stop.is_set():
            try:
                chunk = conn.sock.recv(4096)
            except _ln_socket.timeout:
                continue
            except Exception:
                break
            if not chunk:
                break
            buf += chunk
            if len(buf) > LAN_MAX_LINE * 4:
                break                    # garbage / abuse: drop the connection
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if len(line) > LAN_MAX_LINE:
                    continue
                try:
                    obj = _ln_json.loads(line.decode("utf-8"))
                except Exception:
                    continue
                if isinstance(obj, dict):
                    conn.last = _ln_time.time()
                    self.q.put(("msg", conn, obj))
        self.q.put(("closed", conn))

    # -- main-thread pump ------------------------------------------------------
    def poll(self):
        events = []
        while True:
            try:
                item = self.q.get_nowait()
            except _ln_queue.Empty:
                break
            kind = item[0]
            if kind == "found":
                events.append({"ev": "found", "hosts": item[1]})
            elif kind == "connect_failed":
                events.extend(self._client_lost("couldn't reach that world"))
            elif kind == "msg":
                events.extend(self._on_msg(item[1], item[2]))
            elif kind == "closed":
                events.extend(self._on_closed(item[1]))
        now = _ln_time.time()
        for pid, conn in list(self.peers.items()):
            if now - conn.last > LAN_PEER_TIMEOUT:
                conn.close()
                events.extend(self._on_closed(conn, reason="timed out"))
        for pid, conn in list(self.pending.items()):
            if now - conn.since > LAN_CONFIRM_TIMEOUT:
                conn.send({"t": "reject", "reason": "host didn't confirm in time"})
                conn.close()
                self.pending.pop(pid, None)
                events.append({"ev": "request_expired", "id": pid})
        if self._reconnect_at and now >= self._reconnect_at:
            self._reconnect_at = None
            self.role = "joining"
            self._connect()
            events.append({"ev": "status", "text": f"reconnecting ({self._reconnects}/3)..."})
        return events

    def _on_msg(self, conn, m):
        t = m.get("t")
        ev = []
        if self.role == "host" and conn.stage == "handshake":
            if t != "hello":
                conn.close()
                return ev
            ip = conn.addr[0]
            reason = None
            if m.get("proto") != LAN_PROTO:
                reason = "different ACACIA network version"
            elif self._tries.get(ip, 0) >= LAN_MAX_PIN_TRIES:
                reason = "too many wrong PINs from this computer"
            elif not _ln_secrets.compare_digest(str(m.get("pin", "")), str(self.pin)):
                self._tries[ip] = self._tries.get(ip, 0) + 1
                reason = "wrong PIN"
            elif m.get("id") == self.id or m.get("install") == self.install_id:
                reason = "that's this same ACACIA"
            elif any(c.install == m.get("install") for c in
                     list(self.peers.values()) + list(self.pending.values())):
                reason = "that ACACIA is already connected"
            if reason:
                conn.send({"t": "reject", "reason": reason})
                conn.close()
                ev.append({"ev": "request_refused", "reason": reason, "ip": ip})
                return ev
            conn.id = _ln_str(m.get("id"), 64)
            conn.install = _ln_str(m.get("install"), 64)
            conn.name = _ln_str(m.get("name"), 24) or "someone"
            conn.look = lan_clean_look(dict(m.get("look") or {}, name=conn.name))
            conn.stage, conn.since = "pending", _ln_time.time()
            self.pending[conn.id] = conn
            conn.send({"t": "pending"})
            if conn.install in self._accepted:
                ev.extend(self.accept(conn.id))          # a remembered pairing reconnecting
            else:
                ev.append({"ev": "join_request", "id": conn.id, "name": conn.name, "ip": ip})
            return ev
        if t == "pending" and self.role == "joining":
            ev.append({"ev": "status", "text": "PIN accepted - waiting for the host to confirm"})
        elif t == "welcome" and self.role == "joining":
            hid = _ln_str(m.get("id"), 64)
            conn.id, conn.stage = hid, "live"
            conn.name = _ln_str(m.get("name"), 24) or "host"
            conn.look = lan_clean_look(dict(m.get("look") or {}, name=conn.name))
            self.peers[hid] = conn
            self.role = "client"
            self._reconnects = 0
            self.remote[hid] = {"name": conn.name, "look": conn.look}
            ev.append({"ev": "joined", "id": hid, "name": conn.name, "look": conn.look})
            for p in m.get("others") or []:
                if isinstance(p, dict) and p.get("id") and p.get("id") != self.id:
                    pid = _ln_str(p["id"], 64)
                    lk = lan_clean_look(p.get("look"))
                    self.remote[pid] = {"name": lk["name"], "look": lk}
                    ev.append({"ev": "joined", "id": pid, "name": lk["name"], "look": lk})
        elif t == "reject":
            self._join_args = None               # an explicit refusal: don't retry
            ev.extend(self._client_lost(_ln_str(m.get("reason"), 80) or "refused"))
        elif t == "state" and conn.stage == "live":
            src = conn.id
            if self.role == "client" and m.get("from"):
                src = _ln_str(m["from"], 64)
            st = lan_clean_state(m.get("s"))
            if src != self.id:
                ev.append({"ev": "state", "id": src, "state": st})
            if self.role == "host":             # relay so every client sees everyone
                for pid, c in self.peers.items():
                    if pid != conn.id:
                        c.send({"t": "state", "from": conn.id, "s": st})
        elif t == "act" and conn.stage == "live":
            src = _ln_str(m.get("from"), 64) if (self.role == "client" and m.get("from")) else conn.id
            what = _ln_str(m.get("what"), 16)
            if src != self.id and what in ("wave", "greet", "look"):
                ev.append({"ev": "act", "id": src, "what": what,
                           "to": _ln_str(m.get("to"), 64)})
            if self.role == "host":
                for pid, c in self.peers.items():
                    if pid != conn.id:
                        c.send({"t": "act", "from": conn.id, "what": what, "to": m.get("to")})
        elif t == "peer_join" and self.role == "client":
            pid = _ln_str(m.get("id"), 64)
            if pid and pid != self.id:
                lk = lan_clean_look(m.get("look"))
                self.remote[pid] = {"name": lk["name"], "look": lk}
                ev.append({"ev": "joined", "id": pid, "name": lk["name"], "look": lk})
        elif t == "peer_left" and self.role == "client":
            pid = _ln_str(m.get("id"), 64)
            if self.remote.pop(pid, None) is not None:
                ev.append({"ev": "left", "id": pid, "reason": "left the world"})
        elif t == "bye":
            conn.graceful = True
            conn.close()
        return ev

    def _on_closed(self, conn, reason="left"):
        ev = []
        conn.alive = False
        if conn.id and self.pending.pop(conn.id, None) is not None:
            ev.append({"ev": "request_expired", "id": conn.id})
        if conn.id and self.peers.get(conn.id) is conn:
            self.peers.pop(conn.id, None)
            self.remote.pop(conn.id, None)
            ev.append({"ev": "left", "id": conn.id,
                       "reason": "left" if conn.graceful else reason})
            if self.role == "host":
                for c in self.peers.values():
                    c.send({"t": "peer_left", "id": conn.id})
        if self.role in ("client", "joining") and conn is self._client:
            for pid in list(self.remote):
                ev.append({"ev": "left", "id": pid, "reason": "disconnected"})
            self.remote.clear()
            self.peers.clear()
            ev.extend(self._client_lost("host closed the world" if conn.graceful
                                        else "connection lost"))
        return ev

    def _client_lost(self, why):
        self._client = None
        if self._join_args and self._reconnects < 3 and why in (
                "connection lost", "couldn't reach that world"):
            self._reconnects += 1
            self._reconnect_at = _ln_time.time() + 2.0 * self._reconnects
            self.role = "joining"
            return [{"ev": "status", "text": f"{why} - retrying"}]
        self.role = "idle"
        self._join_args = None
        return [{"ev": "ended", "text": why}]

    # -- host decisions ----------------------------------------------------------
    def accept(self, pid):
        conn = self.pending.pop(pid, None)
        if conn is None or not conn.alive:
            return []
        conn.stage = "live"
        conn.last = _ln_time.time()
        self.peers[pid] = conn
        self._accepted.add(conn.install)
        others = [{"id": i, "look": c.look} for i, c in self.peers.items() if i != pid]
        conn.send({"t": "welcome", "id": self.id, "name": self.name, "look": self.look,
                   "others": others})
        for i, c in self.peers.items():
            if i != pid:
                c.send({"t": "peer_join", "id": pid, "look": conn.look})
        self.remote[pid] = {"name": conn.name, "look": conn.look}
        return [{"ev": "joined", "id": pid, "name": conn.name, "look": conn.look}]

    def reject(self, pid, reason="the host declined"):
        conn = self.pending.pop(pid, None)
        if conn is not None:
            conn.send({"t": "reject", "reason": reason})
            conn.close()

    # -- outgoing ----------------------------------------------------------------
    def send_state(self, state):
        st = lan_clean_state(state)
        for c in list(self.peers.values()):
            c.send({"t": "state", "s": st})

    def send_act(self, what, to=None):
        for c in list(self.peers.values()):
            c.send({"t": "act", "what": what, "to": to})

    # -- shutdown ----------------------------------------------------------------
    def leave(self):
        self._join_args = None
        self._reconnect_at = None
        for c in list(self.peers.values()) + list(self.pending.values()):
            c.send({"t": "bye"})
            c.close()
        if self._client is not None:
            self._client.send({"t": "bye"})
            self._client.close()
        self.peers.clear()
        self.pending.clear()
        self.remote.clear()
        self._stop.set()
        for s in (self._srv, self._udp):
            try:
                if s is not None:
                    s.close()
            except Exception:
                pass
        self._srv = self._udp = self._client = None
        self.role, self.pin = "idle", None

    def status(self):
        return {"role": self.role, "pin": self.pin, "ip": lan_local_ip(),
                "peers": [{"id": i, "name": r["name"]} for i, r in self.remote.items()],
                "pending": [{"id": i, "name": c.name} for i, c in self.pending.items()],
                "error": self.error}


# ============================================================================
# App integration: remote creatures, social behaviour, UI, shutdown
# ============================================================================
#
# A remote ACACIA is drawn by the SAME Creature class (same renderer, own
# pooled items, its own untracked camera proxy), seeded with the remote's
# appearance seed so it looks the same on every screen. It is driven only by
# the synced state: a target position (so the existing locomotion physics
# walks it there), behaviour, emotion, the expression numbers and clothing.
# Positions travel as a fraction of world width, so different window sizes
# still share one layout.
#
# Meeting is real experience for the LOCAL brain: a first meeting is a
# perceived event + an episodic memory + a knowledge entry for that person;
# staying near keeps reinforcing familiarity and satisfies the social need;
# their visible mood nudges ours a little (emotional contagion); they wave,
# we notice and look at them.

LAN_NEAR = 160.0


def lan_own_state(app):
    cr = app.creature
    w = max(1.0, float(getattr(app.world, "w", 0) or app.stage.winfo_width() or 1))
    body = getattr(cr, "_body", None) or {}
    return {"nx": cr.x / w, "facing": getattr(getattr(cr, "_loco", None), "facing", 1.0),
            "behavior": cr.behavior, "emotion": cr.emotion, "intensity": cr.intensity,
            "affect": dict(getattr(cr, "_affect", None) or {}),
            "outfit": body.get("outfit", "normal"), "wet": body.get("wet", 0.0),
            "speaking": cr.speaking, "action": cr.behavior}


def _ln_app_init_hook(self):
    iid = self.settings.get("lan_install_id")
    if not iid:
        iid = _ln_uuid.uuid4().hex[:12]
        self.settings.set("lan_install_id", iid)
    self.lan = LanNode(iid, self.brain.name, {"seed": self.brain.personality.body_seed})
    self._remote = {}
    self._ln_met = set()
    self._ln_social_t = 0.0
    self._ln_send_t = 0.0
    self._ln_status = "not connected"
    self.root.after(100, self._lan_pump)


def _ln_add_remote(self, pid, name, look):
    if pid in self._remote:
        return
    from_proxy = getattr(self, "_world_proxy", None)
    cam = getattr(self, "_camera", None)
    canvas = _CamCanvasProxy(self.stage, cam) if cam is not None else self.stage
    if cam is not None:
        object.__setattr__(canvas, "_track", False)
    cr = self.creature
    w = max(1.0, float(getattr(self.world, "w", 0) or 1))
    rc = Creature(canvas, w * 0.5, cr.y, cr.bounds, identity={"body_seed": look.get("seed", 1)})
    rc.set_detail(cr.detail)
    self._remote[pid] = {"c": rc, "name": name, "nx": 0.5, "state": {}, "last": _ln_time.time()}


def _ln_drop_remote(self, pid):
    r = self._remote.pop(pid, None)
    if r is not None:
        try:
            r["c"].destroy()
        except Exception:
            pass


def _lan_pump(self):
    try:
        lan = self.lan
        for e in lan.poll():
            ev = e["ev"]
            if ev == "join_request":
                okay = messagebox.askyesno(
                    "ACACIA - local network",
                    f"{e['name']} ({e['ip']}) entered your PIN and wants to join your world.\n\n"
                    "Allow this ACACIA in?", parent=self.root)
                if okay:
                    for e2 in lan.accept(e["id"]):
                        if e2["ev"] == "joined":
                            self._ln_add_remote(e2["id"], e2["name"], e2["look"])
                else:
                    lan.reject(e["id"])
            elif ev == "joined":
                self._ln_add_remote(e["id"], e["name"], e["look"])
                self._ln_status = f"connected - {e['name']} is in the world"
            elif ev == "state":
                r = self._remote.get(e["id"])
                if r is not None:
                    r["state"], r["last"] = e["state"], _ln_time.time()
            elif ev == "act":
                r = self._remote.get(e["id"])
                if r is not None and e["what"] == "wave" and e.get("to") in (None, lan.id):
                    self.brain.perceive(Event("friend_seen", f"{r['name']} waved at me",
                                              salience=0.5, valence=0.3, friend_name=r["name"]))
                    self.creature.look_at(r["c"].x, r["c"].y - 40, 0.9)
            elif ev == "left":
                r = self._remote.get(e["id"])
                if r is not None:
                    self.brain.perceive(Event("friend_seen", f"{r['name']} left",
                                              salience=0.35, valence=-0.1,
                                              friend_name=r["name"]))
                self._ln_drop_remote(e["id"])
            elif ev in ("status", "ended", "request_refused"):
                self._ln_status = e.get("text") or e.get("reason", "")
                if ev == "ended":
                    for pid in list(self._remote):
                        self._ln_drop_remote(pid)
            elif ev == "found":
                self._ln_found = e["hosts"]
                self._ln_refresh_found()
        now = _ln_time.time()
        if lan.peers and now - self._ln_send_t >= 0.1:
            self._ln_send_t = now
            lan.send_state(lan_own_state(self))
        if now - self._ln_social_t >= 1.0:
            self._ln_social_t = now
            self._ln_social()
        self._ln_refresh_ui()
    except Exception:
        traceback.print_exc()
    self.root.after(100, self._lan_pump)


def _ln_social(self):
    own, b = self.creature, self.brain
    for pid, r in self._remote.items():
        rc, name = r["c"], r["name"]
        d = abs(rc.x - own.x)
        if d < LAN_NEAR:
            own.look_at(rc.x, rc.y - 40, 0.7)
            rc.look_at(own.x, own.y - 40, 0.7)
            b.goals.satisfy("social", 0.01, f"near {name}")
            if pid not in self._ln_met:
                self._ln_met.add(pid)
                b.perceive(Event("friend_seen", f"met {name}, another ACACIA from a nearby computer",
                                 salience=0.6, valence=0.25, friend_name=name))
                b.memory.remember("episode", f"met {name}, another ACACIA from a nearby computer",
                                  importance=0.6, emotion=b.emotion.emotion,
                                  valence=b.emotion.valence, subject="self")
                self.lan.send_act("wave", to=pid)
            else:
                # staying together keeps building familiarity (knowledge store)
                b.knowledge.see("person", name, valence=0.05, note="spent time together")
            aff = r["state"].get("affect") or {}
            b.emotion.nudge("valence", 0.012 * clamp(aff.get("smile", 0.0), -1, 1), "")
            b.emotion.nudge("stress", 0.01 * clamp01(aff.get("tension", 0.0) - 0.5), "")
            mind = getattr(b, "mind", None)
            if mind is not None:
                row = next((x for x in mind.relationships if x.get("name") == name), None)
                if row is None:
                    row = {"name": name, "role": "acacia on the network", "trust": 0.4,
                           "affection": 0.4, "time_together": 0.0}
                    mind.relationships.append(row)
                row["time_together"] = round(row.get("time_together", 0.0) + 1.0, 1)
                row["affection"] = round(clamp01(row.get("affection", 0.4) + 0.002), 3)
        elif (own.behavior in ("idle", "curious") and b.goals.social > 0.4
              and random.random() < 0.15):
            # lonely and idle: wander over to them - one gentle push, the
            # brain's own decisions still own the creature
            own.set_target(rc.x - 70 if rc.x > own.x else rc.x + 70, own.y)


_ln_orig_friend_actors = App._update_friend_actors


def _ln_update_friend_actors(self, dt):
    _ln_orig_friend_actors(self, dt)
    w = max(1.0, float(getattr(self.world, "w", 0) or 1))
    sg = getattr(self, "_scene_grade", None)
    for pid, r in list(self._remote.items()):
        rc, st = r["c"], r["state"]
        if st:
            rc.set_target(st["nx"] * w, rc.y)
            rc.set_behavior(st["behavior"])
            rc.set_emotion(st["emotion"] or "neutral", st["intensity"])
            if st["affect"]:
                rc._affect = dict(rc._aff(), **st["affect"])
            rc._body = {"outfit": st["outfit"], "wet": st["wet"], "cold": 0.0, "rain": 0.0,
                        "wind": 0.15, "wind_dir": 1.0, "hunch": 0.0, "shiver": 0.0,
                        "pace": 1.0, "flash": 0.0}
            rc.speaking = st["speaking"]
        if sg is not None:
            rc.__dict__["_scene_grade"] = sg
        rc._terrain_fn = getattr(self.creature, "_terrain_fn", None)
        rc.update(dt)
        rc.draw()


def _ln_on_close_wrap(orig):
    def on_close(self):
        try:
            if getattr(self, "lan", None) is not None:
                self.lan.leave()            # "bye" to everyone, sockets closed
        except Exception:
            pass
        return orig(self)
    return on_close


# -- LOCAL NETWORK panel (MODELS tab) -------------------------------------------

def _ln_build_panel(self):
    tab = self.tabs.nametowidget(self.tabs.tabs()[-1])
    card = Card(tab, pad=12, expand=False)
    if tab.grid_slaves():
        cols, rows = tab.grid_size()
        card.grid(row=rows, column=0, columnspan=max(1, cols), sticky="ew", padx=6, pady=(0, 10))
    else:
        card.pack(fill="x", padx=6, pady=(0, 10))
    b = card.body
    self._section(b, "local network (same Wi-Fi / LAN only - never the internet)").pack(fill="x")
    top = tk.Frame(b, bg=C_PANEL)
    top.pack(fill="x", pady=(6, 4))
    self.ln_ip_lbl = tk.Label(top, text="", bg=C_PANEL, fg=C_TEXT, font=FONT_MONO)
    self.ln_ip_lbl.pack(side="left")
    self.ln_status_lbl = tk.Label(top, text="", bg=C_PANEL, fg=C_FAINT, font=FONT_UI_SMALL)
    self.ln_status_lbl.pack(side="left", padx=12)
    host = tk.Frame(b, bg=C_PANEL)
    host.pack(fill="x", pady=2)
    self._button(host, "HOST WORLD", self._ln_host, accent=True).pack(side="left")
    self._button(host, "STOP / LEAVE", self._ln_leave).pack(side="left", padx=6)
    self.ln_pin_lbl = tk.Label(host, text="", bg=C_PANEL, fg=C_ACCENT,
                               font=(FONT_FAMILY_MONO, 16, "bold"))
    self.ln_pin_lbl.pack(side="left", padx=12)
    join = tk.Frame(b, bg=C_PANEL)
    join.pack(fill="x", pady=(6, 2))
    self._button(join, "FIND LOCAL WORLDS", self._ln_find).pack(side="left")
    self.ln_found = tk.Listbox(join, height=3, bg=C_PANEL_2, fg=C_TEXT, relief="flat",
                               highlightthickness=0, font=FONT_MONO, exportselection=False)
    self.ln_found.pack(side="left", fill="x", expand=True, padx=6)
    pinrow = tk.Frame(b, bg=C_PANEL)
    pinrow.pack(fill="x", pady=2)
    tk.Label(pinrow, text="PIN", bg=C_PANEL, fg=C_FAINT, font=FONT_UI_SMALL).pack(side="left")
    self.ln_pin_var = tk.StringVar()
    self._entry(pinrow, self.ln_pin_var, width=5).pack(side="left", padx=6)
    self._button(pinrow, "CONNECT", self._ln_connect, accent=True).pack(side="left")
    self.ln_peers_lbl = tk.Label(b, text="", bg=C_PANEL, fg=C_TEXT, font=FONT_UI_SMALL,
                                 anchor="w", justify="left")
    self.ln_peers_lbl.pack(fill="x", pady=(6, 0))
    self._ln_found = []


def _ln_host(self):
    if self.lan.host():
        self._ln_status = "hosting - share the PIN with the other computer"
    else:
        self._ln_status = self.lan.error


def _ln_leave(self):
    self.lan.leave()
    for pid in list(self._remote):
        self._ln_drop_remote(pid)
    self._ln_status = "not connected"


def _ln_find(self):
    self._ln_status = "searching the local network..."
    self.lan.find_async()


def _ln_refresh_found(self):
    lb = getattr(self, "ln_found", None)
    if lb is None:
        return
    lb.delete(0, "end")
    for h in self._ln_found:
        lb.insert("end", f"{h['name']}  ({h['ip']}, {h['players']} here)")
    self._ln_status = f"found {len(self._ln_found)} world(s)" if self._ln_found \
        else "no worlds found - is the other ACACIA hosting?"


def _ln_connect(self):
    sel = self.ln_found.curselection() if getattr(self, "ln_found", None) else ()
    if not sel or not self._ln_found:
        self._ln_status = "pick a world from the list first"
        return
    h = self._ln_found[sel[0]]
    if self.lan.join(h["ip"], h["port"], self.ln_pin_var.get()):
        self._ln_status = f"connecting to {h['name']}..."
    else:
        self._ln_status = self.lan.error


def _ln_refresh_ui(self):
    lab = getattr(self, "ln_ip_lbl", None)
    if lab is None:
        return
    st = self.lan.status()
    lab.config(text=f"local IP  {st['ip']}")
    self.ln_status_lbl.config(text=f"{st['role']} · {self._ln_status}")
    self.ln_pin_lbl.config(text=f"PIN {st['pin']}" if st["pin"] else "")
    names = [p["name"] for p in st["peers"]]
    self.ln_peers_lbl.config(text="connected creatures: " + (", ".join(names) if names else "none"))


_ln_prev_build_models = App._build_models_tab


def _ln_build_models(self):
    _ln_prev_build_models(self)
    try:
        self._ln_build_panel()
    except Exception:
        traceback.print_exc()


_ln_prev_app_init = App.__init__


def _ln_app_init(self, *a, **kw):
    _ln_prev_app_init(self, *a, **kw)
    try:
        _ln_app_init_hook(self)
    except Exception:
        traceback.print_exc()


App.__init__ = _ln_app_init
App._update_friend_actors = _ln_update_friend_actors
App.on_close = _ln_on_close_wrap(App.on_close)
for _n, _f in (("_lan_pump", _lan_pump), ("_ln_social", _ln_social),
               ("_ln_add_remote", _ln_add_remote), ("_ln_drop_remote", _ln_drop_remote),
               ("_ln_build_panel", _ln_build_panel), ("_ln_host", _ln_host),
               ("_ln_leave", _ln_leave), ("_ln_find", _ln_find),
               ("_ln_refresh_found", _ln_refresh_found), ("_ln_connect", _ln_connect),
               ("_ln_refresh_ui", _ln_refresh_ui)):
    setattr(App, _n, _f)



# ============================================================================
# Visible controls: LOCAL NETWORK tab + the Claude key box where it's seen
# ============================================================================
#
# The previous build put the key field and the network panel at the BOTTOM of
# the MODELS tab: that tab isn't scrollable and its model list stretches to
# fill the height, so both were pushed below the window edge. The key box now
# sits inside the backend STATUS card (the card that says "No Anthropic API
# key"), and the network UI is its own tab.

def _ln_card(parent, title, row, col, colspan=1):
    card = Card(parent, pad=14, expand=False)
    card.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=6, pady=(10, 6))
    return card


def _ln_build_network_tab(self):
    tab = tk.Frame(self.tabs, bg=C_BG)
    self.tabs.add(tab, text="LOCAL NETWORK")
    tab.grid_columnconfigure(0, weight=1)
    tab.grid_columnconfigure(1, weight=1)
    tab.grid_rowconfigure(2, weight=1)

    head = _ln_card(tab, "", 0, 0, 2)
    top = tk.Frame(head.body, bg=C_PANEL)
    top.pack(fill="x")
    tk.Label(top, text="LOCAL NETWORK", bg=C_PANEL, fg=C_TEXT,
             font=(FONT_FAMILY, 13, "bold")).pack(side="left")
    self.ln_dot = tk.Canvas(top, width=14, height=14, bg=C_PANEL, highlightthickness=0)
    self.ln_dot.pack(side="left", padx=8)
    self.ln_role_lbl = tk.Label(top, text="Status: Offline", bg=C_PANEL, fg=C_DIM,
                                font=(FONT_FAMILY, 11, "bold"))
    self.ln_role_lbl.pack(side="left")
    self.ln_status_lbl = tk.Label(head.body, text="", bg=C_PANEL, fg=C_FAINT,
                                  font=FONT_UI_SMALL, anchor="w")
    self.ln_status_lbl.pack(fill="x", pady=(6, 0))
    tk.Label(head.body, text="Same Wi-Fi / LAN only - nothing is opened to the internet. "
             "Only position, movement, mood and clothing are shared: never keys, "
             "memories or settings.", bg=C_PANEL, fg=C_FAINT, font=FONT_UI_SMALL,
             anchor="w", justify="left", wraplength=760).pack(fill="x", pady=(4, 0))

    host = _ln_card(tab, "", 1, 0)
    self._section(host.body, "host a world").pack(fill="x")
    hb = tk.Frame(host.body, bg=C_PANEL)
    hb.pack(fill="x", pady=(10, 6))
    self.ln_host_btn = self._button(hb, "HOST WORLD", self._ln_host, accent=True)
    self.ln_host_btn.pack(side="left")
    self._button(hb, "STOP HOSTING", self._ln_leave).pack(side="left", padx=8)
    self.ln_ip_lbl = tk.Label(host.body, text="", bg=C_PANEL, fg=C_TEXT, font=FONT_MONO,
                              anchor="w")
    self.ln_ip_lbl.pack(fill="x")
    self.ln_port_lbl = tk.Label(host.body, text=f"Port: {LAN_GAME_PORT} (default)",
                                bg=C_PANEL, fg=C_DIM, font=FONT_MONO, anchor="w")
    self.ln_port_lbl.pack(fill="x")
    tk.Label(host.body, text="PAIRING PIN", bg=C_PANEL, fg=C_FAINT,
             font=(FONT_FAMILY, 8, "bold"), anchor="w").pack(fill="x", pady=(12, 0))
    self.ln_pin_lbl = tk.Label(host.body, text="---", bg=C_PANEL, fg=C_ACCENT,
                               font=(FONT_FAMILY_MONO, 30, "bold"), anchor="w")
    self.ln_pin_lbl.pack(fill="x")
    tk.Label(host.body, text="Tell the other person this PIN. You'll be asked to confirm "
             "before they join.", bg=C_PANEL, fg=C_FAINT, font=FONT_UI_SMALL,
             anchor="w", justify="left", wraplength=330).pack(fill="x")

    join = _ln_card(tab, "", 1, 1)
    self._section(join.body, "join a world").pack(fill="x")
    jb = tk.Frame(join.body, bg=C_PANEL)
    jb.pack(fill="x", pady=(10, 6))
    self._button(jb, "FIND WORLDS", self._ln_find, accent=True).pack(side="left")
    self._button(jb, "LEAVE", self._ln_leave).pack(side="left", padx=8)
    self.ln_found = tk.Listbox(join.body, height=4, bg=C_PANEL_2, fg=C_TEXT, relief="flat",
                               highlightthickness=1, highlightbackground=C_BORDER,
                               selectbackground=C_ACCENT, selectforeground="#08110e",
                               font=FONT_MONO, exportselection=False, activestyle="none")
    self.ln_found.pack(fill="x", pady=(2, 8))
    pr = tk.Frame(join.body, bg=C_PANEL)
    pr.pack(fill="x")
    tk.Label(pr, text="PIN", bg=C_PANEL, fg=C_FAINT, font=(FONT_FAMILY, 9, "bold")).pack(side="left")
    self.ln_pin_var = tk.StringVar()
    pin_entry = self._entry(pr, self.ln_pin_var, width=6)
    pin_entry.configure(font=(FONT_FAMILY_MONO, 14, "bold"), justify="center")
    pin_entry.pack(side="left", padx=8)
    pin_entry.bind("<Return>", lambda _e: self._ln_connect())
    self._button(pr, "JOIN", self._ln_connect, accent=True).pack(side="left")

    who = Card(tab, pad=14)
    who.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=(6, 10))
    self._section(who.body, "in this world").pack(fill="x")
    self.ln_peers_lbl = tk.Label(who.body, text="", bg=C_PANEL, fg=C_TEXT,
                                 font=FONT_UI_SMALL, anchor="nw", justify="left")
    self.ln_peers_lbl.pack(fill="both", expand=True, pady=(8, 0))


def _ln_refresh_ui(self):                     # replaces the MODELS-panel version
    lab = getattr(self, "ln_role_lbl", None)
    if lab is None:
        return
    st = self.lan.status()
    role = st["role"]
    txt, col = {"idle": ("Status: Offline", C_DIM), "host": ("Status: HOSTING", C_GOOD),
                "joining": ("Status: Connecting...", C_WARN),
                "client": ("Status: CONNECTED", C_GOOD)}[role]
    lab.config(text=txt, fg=col)
    self.ln_dot.delete("all")
    self.ln_dot.create_oval(2, 2, 12, 12, fill=col, outline="")
    self.ln_status_lbl.config(text=self._ln_status)
    self.ln_ip_lbl.config(text=f"Local IP: {st['ip']}")
    self.ln_pin_lbl.config(text=st["pin"] if st["pin"] else "---",
                           fg=C_ACCENT if st["pin"] else C_FAINT)
    rows = [f"  {self.brain.name}  (you)"]
    for pid, r in self._remote.items():
        rc = r["c"]
        d = abs(rc.x - self.creature.x)
        rows.append(f"  {r['name']}  -  {r['state'].get('emotion') or 'arriving'}, "
                    f"{r['state'].get('behavior', '...')}, "
                    f"{'right next to you' if d < LAN_NEAR else f'{d:.0f} px away'}")
    for p in st["pending"]:
        rows.append(f"  {p['name']}  -  waiting for your confirmation")
    self.ln_peers_lbl.config(text="\n".join(rows))


# -- Claude key box inside the backend STATUS card ---------------------------------

def _ln_key_row(self):
    status_body = self.backend_status.master
    row = tk.Frame(status_body, bg=C_PANEL)
    row.pack(fill="x", pady=(10, 0))
    tk.Label(row, text="Anthropic API key", bg=C_PANEL, fg=C_TEXT,
             font=(FONT_FAMILY, 9, "bold")).pack(side="left")
    self.claude_key_box = self._entry(row, self.var_claude_key, show="•", width=40)
    self.claude_key_box.pack(side="left", padx=8, fill="x", expand=True)
    self.claude_key_box.bind("<Return>", lambda _e: self._ln_claude_connect())
    self._button(row, "CONNECT", self._ln_claude_connect, accent=True).pack(side="left")
    self.claude_conn_lbl = tk.Label(status_body, text="", bg=C_PANEL, fg=C_FAINT,
                                    font=FONT_UI_SMALL, anchor="w")
    self.claude_conn_lbl.pack(fill="x", pady=(4, 0))
    self._ln_show_saved_key()


def _ln_key_tail(key):
    return f"sk-ant-...{key[-4:]}" if len(key) > 12 else "(short key)"


def _ln_show_saved_key(self):
    key = self.settings.secret("claude_api_key")
    lab = getattr(self, "claude_conn_lbl", None)
    if lab is not None:
        lab.config(text=(f"saved key {_ln_key_tail(key)} ({self.settings.secret_source('claude_api_key')})"
                         " - press CONNECT to check it" if key else
                         "paste your key (Ctrl+V or right-click) and press CONNECT"),
                   fg=C_FAINT)


def _ln_claude_connect(self):
    self._lm_commit_key()
    key = self.settings.secret("claude_api_key")
    status, msg = lm_key_format(key)
    lab = self.claude_conn_lbl
    if status != "ok":
        lab.config(text=msg, fg=C_WARN if status == "warn" else C_BAD)
        return
    lab.config(text=f"checking {_ln_key_tail(key)} with Anthropic...", fg=C_FAINT)
    model = self.settings.get("claude_model")

    def run():
        ok, msg = lm_test_claude_key(key, model)

        def done():
            lab.config(text=(f"Claude connected - key {_ln_key_tail(key)} verified"
                             if ok else f"Claude not connected: {msg}"),
                       fg=C_GOOD if ok else C_BAD)
            if getattr(self.models.current, "key", "") == "claude":
                self.check_backend(async_=True)      # repaint the real status card
        self.root.after(0, done)
    threading.Thread(target=run, daemon=True).start()


_ln_prev_claude_available = ClaudeBackend.available


def _ln_claude_available(self):
    ok, msg = _ln_prev_claude_available(self)
    if not ok:
        msg = "No Anthropic API key yet - paste it in the box below and press CONNECT."
    return ok, msg


ClaudeBackend.available = _ln_claude_available

_ln_prev_init2 = App.__init__


def _ln_init2(self, *a, **kw):
    _ln_prev_init2(self, *a, **kw)
    try:
        self._ln_build_network_tab()
    except Exception:
        traceback.print_exc()
    try:
        self._ln_key_row()
    except Exception:
        traceback.print_exc()


App.__init__ = _ln_init2
for _n, _f in (("_ln_build_network_tab", _ln_build_network_tab), ("_ln_refresh_ui", _ln_refresh_ui),
               ("_ln_key_row", _ln_key_row), ("_ln_show_saved_key", _ln_show_saved_key),
               ("_ln_claude_connect", _ln_claude_connect)):
    setattr(App, _n, _f)
