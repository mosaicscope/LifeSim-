


# ============================================================================
# [10.5] LIVE MODE  -  real-time, high-level computer-interaction awareness
# ============================================================================
#
# WHAT IS SENSED (all of it high-level, all of it derivable from the window
# manager's pointer position and focus state):
#
#     cursor position / velocity      -> is the pointer moving, and where
#     cursor in / out of our window   -> is the user looking at CREATURE
#     clicks (count only, no target)  -> is the user interacting
#     window focus                    -> CREATURE vs another application
#     foreground window TITLE         -> only on Windows, only the title,
#                                        truncated, never stored to disk
#
# WHAT IS NEVER TOUCHED - and there is no code path here that could:
#
#     keystrokes, typed text, passwords, clipboard contents, screenshots,
#     screen pixels, file contents, webcam, microphone, network traffic.
#
# There is no global hook, no key listener and no screen capture anywhere in
# this file.  Everything below uses Tk's own pointer/focus queries plus (on
# Windows) one read-only user32 call for the foreground window title.
#
# Signals are *throttled*: the creature reacts to changes in state, not to
# every mouse move, so LIVE adds a fixed ~12Hz of cheap polling and NEVER
# triggers the language model on its own - it only raises the odds that the
# existing idle-thought system has something to say.

# Hard ceiling on how often LIVE may cause a language-model call.  Everything
# else LIVE does (gaze, attention, emotion, memory) is pure local simulation
# and costs nothing, which is the point: awareness should be cheap.
LIVE_THINK_GAP = 240.0

LIVE_SIGNALS = ("USER_PRESENT", "CURSOR_MOVING", "USER_IDLE", "USER_RETURNED",
                "USER_INTERACTING", "EXTERNAL_APP_ACTIVE", "CURSOR_AWAY")


class LiveSense:
    """Polled from the UI loop (never its own thread, so it can't race Tk).
    Produces a small state dict + a throttled queue of high-level events."""

    POLL_HZ = 12.0
    IDLE_AFTER = 6.0          # seconds of no cursor movement -> USER_IDLE
    RETURN_GAP = 12.0         # how long away before coming back is "notable"
    EVENT_COOLDOWN = {        # min seconds between repeats of one signal
        "USER_RETURNED": 25.0,
        "USER_IDLE": 45.0,
        "USER_INTERACTING": 30.0,
        "EXTERNAL_APP_ACTIVE": 60.0,
        "CURSOR_AWAY": 40.0,
        "USER_PRESENT": 90.0,
    }

    def __init__(self, root, stage):
        self.root = root
        self.stage = stage
        self.enabled = False
        self.available = True
        self.reason = "ready"

        self.cursor = (0, 0)          # screen coords
        self.local = None             # (x, y) in stage coords, or None
        self.speed = 0.0
        self.moving = False
        self.in_window = False
        self.focused = True
        self.clicks = 0
        self.last_click = 0.0
        self.last_move = time.time()
        self.last_seen = time.time()  # last time the user did anything at all
        self.idle_seconds = 0.0
        self.app_name = ""
        self.state = "unknown"

        self._last_poll = 0.0
        self._last_app_poll = 0.0
        self._fired = {}
        self._queue = deque(maxlen=24)
        self._was_idle = False
        self._was_focused = True

        self._user32 = None
        if sys.platform.startswith("win"):
            try:
                import ctypes
                self._user32 = ctypes.windll.user32
                self._ctypes = ctypes
            except Exception:
                self._user32 = None

        # Clicks are the only input binding, and it records a COUNT and a
        # timestamp - never which widget, never any key or character.
        try:
            root.bind_all("<Button>", self._on_click, add="+")
            root.bind("<FocusIn>", lambda _e: self._set_focus(True), add="+")
            root.bind("<FocusOut>", lambda _e: self._set_focus(False), add="+")
        except Exception:
            self.available = False
            self.reason = "this window manager does not report pointer events"

    # -- control -------------------------------------------------------
    def set_enabled(self, on):
        self.enabled = bool(on) and self.available
        if self.enabled:
            self.last_seen = time.time()
            self._fired.clear()
            self._queue.clear()
            self.state = "watching"
        else:
            self.state = "off"
            self.local = None
            self._queue.clear()
        return self.enabled

    def _set_focus(self, val):
        self.focused = bool(val)

    def _on_click(self, _event=None):
        if not self.enabled:
            return
        self.clicks += 1
        self.last_click = time.time()
        self.last_seen = self.last_click

    # -- sensing -------------------------------------------------------
    def _foreground_app(self):
        """Windows only, best effort, title text only, truncated.  Everything
        else falls back to 'is CREATURE focused' - which is enough to know
        whether the user's attention is here or elsewhere."""
        if self._user32 is None:
            return "CREATURE" if self.focused else "another application"
        try:
            hwnd = self._user32.GetForegroundWindow()
            if not hwnd:
                return ""
            length = self._user32.GetWindowTextLengthW(hwnd)
            if length <= 0 or length > 300:
                return ""
            buf = self._ctypes.create_unicode_buffer(length + 1)
            self._user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value.strip()[:48]
        except Exception:
            return ""

    def poll(self):
        """Call every frame; internally rate-limited to POLL_HZ.  Returns the
        current state dict (cheap) and queues any state-CHANGE events."""
        now = time.time()
        if not self.enabled:
            return None
        if now - self._last_poll < 1.0 / self.POLL_HZ:
            return self.snapshot()
        dt = max(1e-3, now - self._last_poll)
        self._last_poll = now

        try:
            px, py = self.root.winfo_pointerxy()
        except Exception:
            return self.snapshot()
        dx, dy = px - self.cursor[0], py - self.cursor[1]
        self.cursor = (px, py)
        self.speed = math.hypot(dx, dy) / dt
        moved = self.speed > 12
        if moved:
            self.last_move = now
            self.last_seen = now
        self.moving = moved
        self.idle_seconds = now - self.last_seen

        # cursor in our stage?  (rootx/rooty are cheap Tk queries)
        try:
            sx, sy = self.stage.winfo_rootx(), self.stage.winfo_rooty()
            sw, sh = self.stage.winfo_width(), self.stage.winfo_height()
            lx, ly = px - sx, py - sy
            self.in_window = 0 <= lx <= sw and 0 <= ly <= sh
            if self.in_window:
                self.local = (lx, ly)
            elif self.local is not None:
                # remember where they were last seen rather than snapping away
                self.local = (clamp(lx, 0, max(1, sw)), clamp(ly, 0, max(1, sh)))
        except Exception:
            self.in_window = False

        if now - self._last_app_poll > 1.5:
            self._last_app_poll = now
            self.app_name = self._foreground_app()

        # ---- derive one clean state + queue the transitions --------------
        away = self.idle_seconds
        prev_state = self.state
        if not self.focused and self.app_name and "CREATURE" not in self.app_name:
            self.state = "elsewhere"
        elif away > self.IDLE_AFTER:
            self.state = "idle"
        elif now - self.last_click < 1.2:
            self.state = "interacting"
        elif self.in_window and moved:
            self.state = "watching"
        elif moved:
            self.state = "present"
        else:
            self.state = prev_state if prev_state != "off" else "present"

        if prev_state in ("idle", "elsewhere", "off") and \
                self.state in ("watching", "interacting", "present") and \
                self._was_idle:
            self._was_idle = False
            self._fire("USER_RETURNED", "you came back to the machine", 0.65)
        if self.state == "idle" and not self._was_idle:
            self._was_idle = True
            self._fire("USER_IDLE", "you have gone quiet", 0.3)
        if self.state == "elsewhere":
            self._was_idle = True
            self._fire("EXTERNAL_APP_ACTIVE",
                       "your attention is on something else", 0.35)
        if self.state == "interacting":
            self._fire("USER_INTERACTING", "you are doing something here", 0.45)
        if self.state == "watching":
            self._fire("USER_PRESENT", "you are here, watching", 0.3)
        if not self.in_window and self.focused and self.state != "idle":
            self._fire("CURSOR_AWAY", "the cursor drifted out of the world", 0.25)
        return self.snapshot()

    def _fire(self, signal, text, salience):
        now = time.time()
        gap = self.EVENT_COOLDOWN.get(signal, 30.0)
        if now - self._fired.get(signal, 0.0) < gap:
            return
        self._fired[signal] = now
        self._queue.append((signal, text, salience, now))

    def drain(self):
        out = list(self._queue)
        self._queue.clear()
        return out

    def snapshot(self):
        return {
            "enabled": self.enabled, "state": self.state,
            "local": self.local, "in_window": self.in_window,
            "moving": self.moving, "speed": round(self.speed, 1),
            "idle": round(self.idle_seconds, 1), "clicks": self.clicks,
            "app": self.app_name, "focused": self.focused,
        }
