

# ============================================================================
# [0] CONFIG / UTIL / PERSISTENCE
# ============================================================================

APP_TITLE = "ACACIA"
APP_VERSION = "v1"
APP_TAGLINE = "a mind with hands"
# The creature's own name is separate from the product name and is
# still user-editable in settings, as it always was.
CREATURE_NAME = "Vessel"

APP_DIR = Path(os.environ.get("CREATURE_HOME", str(Path.home() / ".creature_mind")))

# ------------------------------------------- [PHASE 61] instance isolation
# More than one creature can live under CREATURE_HOME. Each instance owns
# its own mind-state files; nothing mutable is shared between them.
#
#   main (default)      CREATURE_HOME/*.json          <- unchanged, in place
#   any other instance  CREATURE_HOME/instances/<id>/*.json
#
# MIGRATION SAFETY: the default instance keeps using the exact paths it
# always used, so an existing install is untouched and nothing is moved.
# A new instance starts EMPTY - state is never copied, merged or inherited
# from another instance, because a silent merge would mix two creatures'
# memories together irreversibly. Use Phase 62's export/import to move a
# creature deliberately.
#
# MODELS_DIR and PACKS_DIR stay shared on purpose: they hold large,
# read-mostly assets (GGUF weights, effect packs), not mind state.

def _safe_instance_id(iid):
    cleaned = re.sub(r"[^a-z0-9_-]", "", str(iid or "").lower())[:32]
    return cleaned or "main"


INSTANCE_ID = _safe_instance_id(os.environ.get("CREATURE_INSTANCE", "main"))


def instance_dir(iid=None):
    iid = _safe_instance_id(iid if iid is not None else INSTANCE_ID)
    return APP_DIR if iid == "main" else APP_DIR / "instances" / iid


def instance_ids():
    """-> every instance that actually has a directory, 'main' first."""
    out = ["main"]
    try:
        root = APP_DIR / "instances"
        if root.is_dir():
            out += sorted(d.name for d in root.iterdir() if d.is_dir())
    except Exception:
        pass
    return out


def use_instance(iid):
    """Point every mind-state path at one instance. Rebinds names only -
    it never reads, writes, moves or merges a single file."""
    global INSTANCE_ID, INSTANCE_DIR, STATE_FILE, MEMORY_FILE, FRIENDS_FILE
    global MODELS_FILE, SETTINGS_FILE, KNOWLEDGE_FILE, PACKS_FILE, VISUAL_FILE
    global LISTINGS_FILE, EXCHANGES_FILE, AUDIO_DIR
    INSTANCE_ID = _safe_instance_id(iid)
    INSTANCE_DIR = instance_dir(INSTANCE_ID)
    STATE_FILE = INSTANCE_DIR / "state.json"
    MEMORY_FILE = INSTANCE_DIR / "memory.json"
    FRIENDS_FILE = INSTANCE_DIR / "friends.json"
    MODELS_FILE = INSTANCE_DIR / "models.json"
    SETTINGS_FILE = INSTANCE_DIR / "settings.json"
    KNOWLEDGE_FILE = INSTANCE_DIR / "knowledge.json"
    PACKS_FILE = INSTANCE_DIR / "packs.json"
    VISUAL_FILE = INSTANCE_DIR / "visual_memory.json"
    LISTINGS_FILE = INSTANCE_DIR / "listings.json"        # [PHASE 63]
    EXCHANGES_FILE = INSTANCE_DIR / "exchanges.json"      # [PHASE 65]
    AUDIO_DIR = INSTANCE_DIR / "audio"                    # [PHASE 56]
    return INSTANCE_DIR


MODELS_DIR = APP_DIR / "models"      # shared: large read-mostly assets
PACKS_DIR = APP_DIR / "packs"        # shared: effect packs
use_instance(INSTANCE_ID)

BRAIN_HZ = 10.0                 # internal state integration rate
BRAIN_INTERVAL_MS = int(1000 / BRAIN_HZ)
RENDER_INTERVAL_MS = 33         # ~30 FPS, drawing only
UI_PUMP_MS = 50                 # worker -> UI message pump

INSTALL_HINTS = {
    "llama": "pip install llama-cpp-python",
    "dnd": "pip install tkinterdnd2",
}

# --- palette (modern dark) --------------------------------------------------
C_BG = "#0c0e13"
C_PANEL = "#151922"
C_PANEL_2 = "#1c2230"
C_BORDER = "#252c3b"
C_TEXT = "#e6ebf5"
C_DIM = "#8a94a8"
C_FAINT = "#5a6376"
C_ACCENT = "#7ee0c8"
C_ACCENT_2 = "#8fb4ff"
C_WARN = "#ffcf7a"
C_BAD = "#ff8a8a"
C_GOOD = "#93e58c"
C_USER = "#1f2a3d"
C_AI = "#1b2420"

# --- fonts ------------------------------------------------------------------
# "Segoe UI" only exists on Windows - on Linux/macOS Tk silently substitutes
# some other font, and widths/paddings tuned for its metrics stop lining
# up, which is a real (if invisible-in-code) source of an "ugly" UI on
# anything but Windows. Pick a real family per platform instead; bold
# weight is expressed with the standard Tk "bold" modifier so it works
# everywhere rather than depending on a "Semibold"-named family existing.
_SYS = platform.system()
if _SYS == "Windows":
    FONT_FAMILY, FONT_FAMILY_MONO = "Segoe UI", "Consolas"
elif _SYS == "Darwin":
    FONT_FAMILY, FONT_FAMILY_MONO = "Helvetica Neue", "Menlo"
else:
    FONT_FAMILY, FONT_FAMILY_MONO = "DejaVu Sans", "DejaVu Sans Mono"

FONT_UI = (FONT_FAMILY, 10)
FONT_UI_SMALL = (FONT_FAMILY, 9)
FONT_UI_BOLD = (FONT_FAMILY, 10, "bold")
FONT_TITLE = (FONT_FAMILY, 15, "bold")
FONT_MONO = (FONT_FAMILY_MONO, 9)
FONT_CHAT = (FONT_FAMILY, 11)


def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def approach(value: float, target: float, rate: float, dt: float) -> float:
    """Frame-rate independent exponential approach (gives everything inertia)."""
    return value + (target - value) * (1.0 - math.exp(-max(0.0, rate) * dt))


def human_size(nbytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024 or unit == "TB":
            return f"{nbytes:.0f} {unit}" if unit in ("B", "KB") else f"{nbytes:.2f} {unit}"
        nbytes /= 1024.0
    return f"{nbytes:.2f} TB"


def ago(ts: float) -> str:
    d = max(0.0, time.time() - ts)
    if d < 60:
        return f"{int(d)}s ago"
    if d < 3600:
        return f"{int(d/60)}m ago"
    if d < 86400:
        return f"{int(d/3600)}h ago"
    return f"{int(d/86400)}d ago"


def read_system_stats() -> dict:
    """Best-effort, cheap system resource snapshot. Never raises, never blocks
    for long - callers should only invoke this from a background thread since
    the GPU probe shells out to nvidia-smi with a hard timeout."""
    out = {"cpu": None, "ram": None, "ram_total": None, "gpu": None}
    if has_module("psutil"):
        try:
            import psutil  # local import: optional dependency
            out["cpu"] = psutil.cpu_percent(interval=None)
            vm = psutil.virtual_memory()
            out["ram"] = vm.percent
            out["ram_total"] = vm.total
        except Exception:
            pass
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=1.0)
        if result.returncode == 0 and result.stdout.strip():
            first = result.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first.split(",")]
            if len(parts) == 3:
                util, used, total = parts
                out["gpu"] = f"{util}% util, {used}/{total} MB"
    except Exception:
        pass
    return out


def ensure_dirs() -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        INSTANCE_DIR.mkdir(parents=True, exist_ok=True)   # [PHASE 61]
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        PACKS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover
        print(f"[creature] could not create {APP_DIR}: {exc}")


def load_json(path: Path, default):
    """Never let a corrupt/missing file stop the app."""
    try:
        if not Path(path).exists():
            return default
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print(f"[creature] could not read {path}: {exc}")
        return default


def save_json(path: Path, data, private: bool = False) -> bool:
    """Atomic-ish write; `private` chmods to 0600 (used for API keys)."""
    try:
        ensure_dirs()
        tmp = Path(str(path) + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
        if private:
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass
        return True
    except Exception as exc:
        print(f"[creature] could not write {path}: {exc}")
        return False


class Settings:
    """User settings + secrets.  API keys come from the environment first,
    then from this file.  Nothing is ever hard-coded."""

    ENV = {
        "claude_api_key": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
        "gemini_api_key": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    }

    DEFAULTS = {
        "backend": "ollama",
        "gguf_path": "",
        "ollama_host": "http://localhost:11434",
        "ollama_model": "llama3.2",
        "claude_model": "claude-sonnet-4-5",
        "gemini_model": "gemini-2.0-flash",
        "claude_api_key": "",
        "gemini_api_key": "",
        "n_ctx": 4096,
        "max_tokens": 320,
        "temperature": 0.85,
        "creature_name": CREATURE_NAME,
        "idle_thoughts_enabled": True,
        "social_enabled": True,
        "social_min_gap_seconds": 480,
        "inter_creature_enabled": False,     # [PHASE 65] opt-in, never default-on
        # BRAIN/PROCESSING placement for local inference:
        #   auto | cpu | gpu | hybrid   (validated against real capability)
        "compute_mode": "auto",
        # LIVE MODE - real-time, high-level computer-interaction awareness.
        # Off by default; never stores keystrokes/clipboard/screen contents.
        "live_enabled": False,
        "live_eye_contact": True,
        "world_detail": "auto",
        "debug_panel": False,
        # COMPUTER AGENT - off by default (security-first). Read-only
        # folder watching + network status; no write/execute capability.
        "computer_agent_enabled": False,
        "watched_folders": [],
    }

    def __init__(self):
        self.data = dict(self.DEFAULTS)
        stored = load_json(SETTINGS_FILE, {})
        if isinstance(stored, dict):
            for key, value in stored.items():
                if key in self.DEFAULTS:
                    self.data[key] = value

    def get(self, key, default=None):
        return self.data.get(key, self.DEFAULTS.get(key, default))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        save_json(SETTINGS_FILE, self.data, private=True)

    def secret(self, key: str) -> str:
        """Environment variable wins over the stored settings field."""
        for env_name in self.ENV.get(key, ()):
            val = os.environ.get(env_name)
            if val:
                return val.strip()
        return str(self.data.get(key, "") or "").strip()

    def secret_source(self, key: str) -> str:
        for env_name in self.ENV.get(key, ()):
            if os.environ.get(env_name):
                return f"env:{env_name}"
        return "settings" if self.data.get(key) else "missing"
