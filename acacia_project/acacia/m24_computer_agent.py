

# ============================================================================
# [10.5] COMPUTER AGENT  --  event-driven awareness of the machine CREATURE
#                             runs on, turned into genuine perceptions
# ============================================================================
#
# Everything here is read-only sensing that runs on background threads and
# reports back through the SAME ui_queue/_pump() pattern the rest of the app
# already uses for worker -> UI messages - so it can never block the render
# or brain thread, and never touches Tk from a non-UI thread. There is no
# destructive capability (no delete/execute/write) implemented anywhere in
# this class; _permit() exists as the one gate any future destructive action
# would have to pass, and defaults closed.

class ComputerAgent:
    FOLDER_POLL_S = 4.0
    NET_POLL_S = 20.0
    MAX_WATCH = 6
    MAX_ENTRIES_PER_FOLDER = 400

    def __init__(self, ui_queue, settings):
        self.q = ui_queue
        self.settings = settings
        self._stop = False
        self._snapshots = {}        # folder -> {relpath: mtime}
        self._threads_started = False

    def _permit(self, action):
        """The one gate a destructive/external action would have to pass.
        Nothing in this class currently performs one - this exists so that
        if a future capability is added, it fails closed by default rather
        than needing a gate bolted on after the fact."""
        return bool(self.settings.get(f"permit_{action}", False))

    def start(self):
        if self._threads_started:
            return
        self._threads_started = True
        threading.Thread(target=self._folder_loop, daemon=True).start()
        threading.Thread(target=self._net_loop, daemon=True).start()

    # -- filesystem: polled listing + mtime diff, debounced by definition
    # (nothing is reported until it survives one full poll interval) -------
    def _scan_folder(self, path):
        out = {}
        try:
            with os.scandir(path) as it:
                for i, entry in enumerate(it):
                    if i >= self.MAX_ENTRIES_PER_FOLDER:
                        break
                    try:
                        out[entry.name] = entry.stat(follow_symlinks=False).st_mtime
                    except OSError:
                        pass
        except OSError:
            return None
        return out

    def _folder_loop(self):
        while not self._stop:
            try:
                folders = list(self.settings.get("watched_folders", []) or [])[:self.MAX_WATCH]
                if not self.settings.get("computer_agent_enabled", False):
                    time.sleep(self.FOLDER_POLL_S)
                    continue
                for folder in folders:
                    cur = self._scan_folder(folder)
                    if cur is None:
                        continue
                    prev = self._snapshots.get(folder)
                    self._snapshots[folder] = cur
                    if prev is None:
                        continue           # first sighting establishes baseline only
                    added = [n for n in cur if n not in prev]
                    removed = [n for n in prev if n not in cur]
                    changed = [n for n in cur if n in prev and cur[n] != prev[n]]
                    if added or removed or changed:
                        self.q.put(("computer_event", {
                            "kind": "file_change", "folder": folder,
                            "added": added[:5], "removed": removed[:5],
                            "changed": changed[:5], "t": time.time(),
                        }))
            except Exception:
                pass
            time.sleep(self.FOLDER_POLL_S)

    # -- network: cheap reachability probe, never DNS/HTTP (no app deps) --
    def _net_loop(self):
        last_state = None
        while not self._stop:
            try:
                if self.settings.get("computer_agent_enabled", False):
                    ok = False
                    try:
                        s = socket.create_connection(("1.1.1.1", 53), timeout=1.5)
                        s.close()
                        ok = True
                    except OSError:
                        ok = False
                    if ok != last_state:
                        last_state = ok
                        self.q.put(("computer_event", {
                            "kind": "network", "online": ok, "t": time.time()}))
            except Exception:
                pass
            time.sleep(self.NET_POLL_S)

    def stop(self):
        self._stop = True
