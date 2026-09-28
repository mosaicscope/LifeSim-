

# ============================================================================
# [8] MODEL BACKENDS / GGUF MANAGER / MODEL MANAGER
# ============================================================================

class BackendError(Exception):
    """Raised by backends; never allowed to escape into the UI thread."""


def _http_json(url, payload=None, headers=None, timeout=20, method=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
    try:
        return json.loads(raw)
    except Exception:
        raise BackendError("the server sent a malformed response")


def _http_stream(url, payload, headers=None, timeout=120):
    """Yields decoded lines from a streaming HTTP response."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            yield raw.decode("utf-8", "replace").rstrip("\r\n")


def _download_with_progress(url, dest_path, progress_cb=None, timeout=30):
    """Stream a URL to disk, reporting (bytes_done, total_bytes_or_None) to
    progress_cb as it goes. Raises on failure - callers decide how to word
    that for the user (no internet, host unreachable, etc.)."""
    req = urllib.request.Request(url, headers={"User-Agent": "CREATURE/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = resp.headers.get("Content-Length")
        total = int(total) if total and total.isdigit() else None
        done = 0
        tmp_path = str(dest_path) + ".part"
        with open(tmp_path, "wb") as f:
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
    os.replace(tmp_path, dest_path)


def _explain_http_error(exc, what):
    if isinstance(exc, urllib.error.HTTPError):
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        if exc.code in (401, 403):
            return f"{what}: authentication failed ({exc.code}) - check the API key."
        if exc.code == 404:
            return f"{what}: model or endpoint not found (404). {body}"
        if exc.code == 429:
            return f"{what}: rate limited (429). Wait a moment and try again."
        return f"{what}: HTTP {exc.code}. {body}"
    if isinstance(exc, urllib.error.URLError):
        return f"{what}: could not connect ({exc.reason})."
    return f"{what}: {exc}"


# ---------------------------------------------------------------- base class
class LLMBackend:
    key = "base"
    label = "BASE"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.status = "unknown"       # ready | loading | error | unavailable
        self.detail = ""

    def available(self):
        """-> (bool, human readable reason)."""
        return False, "not implemented"

    def describe(self):
        return self.label

    def prepare(self):
        """Optional heavy set-up (model load).  Runs in a worker thread."""
        return True

    def generate(self, system, messages, max_tokens, on_token, cancel):
        raise BackendError("not implemented")

    def unload(self):
        pass


# ---------------------------------------------------------------- local gguf
class LocalGGUFBackend(LLMBackend):
    key = "local"
    label = "LOCAL GGUF"

    def __init__(self, settings, gguf_manager):
        super().__init__(settings)
        self.gguf = gguf_manager
        self._llm = None
        self._loaded_path = None
        self._lock = threading.RLock()

    def available(self):
        if not has_module("llama_cpp"):
            return False, ("llama-cpp-python is not installed.\n"
                           f"Install it with:  {INSTALL_HINTS['llama']}")
        path = self.settings.get("gguf_path", "")
        if not path:
            return False, "No GGUF selected. Drop a .gguf file into the MODELS tab."
        p = Path(path).expanduser()
        if not p.is_file():
            return False, f"GGUF file is missing:\n{p}"
        if p.suffix.lower() != ".gguf":
            return False, f"Selected file is not a .gguf model:\n{p.name}"
        info = self.gguf.models.get(str(p))
        if info and info.get("status") == "invalid":
            return False, info.get("note", "GGUF failed validation")
        return True, f"{p.name} ready to load"

    def describe(self):
        path = self.settings.get("gguf_path", "")
        return Path(path).name if path else "no model"

    def prepare(self):
        ok, reason = self.available()
        if not ok:
            self.status = "unavailable"
            self.detail = reason
            raise BackendError(reason)
        path = str(Path(self.settings.get("gguf_path")).expanduser())
        with self._lock:
            if self._llm is not None and self._loaded_path == path:
                self.status = "ready"
                return True
            self._unload_locked()
            self.status = "loading"
            self.detail = f"loading {Path(path).name}..."
            try:
                from llama_cpp import Llama
            except Exception as exc:
                self.status = "error"
                self.detail = f"llama-cpp-python failed to import: {exc}\n{INSTALL_HINTS['llama']}"
                raise BackendError(self.detail)
            n_ctx = int(self.settings.get("n_ctx", 4096) or 4096)
            n_threads = max(1, (os.cpu_count() or 4) - 1)
            has_gpu = llama_cpp_has_gpu_support()
            mode = str(self.settings.get("compute_mode", "auto") or "auto").lower()
            if mode not in COMPUTE_MODES:
                mode = "auto"
            if mode == "cpu" or not has_gpu:
                has_gpu = False           # honest fallback, never a crash
            # Plan offload from actual free VRAM and the model's layer count.
            # A fixed layer count is unsafe because layer memory varies by model.
            n_gpu_layers = 0
            if has_gpu:
                try:
                    total_layers = gguf_layer_count(path)
                    size_bytes = Path(path).stat().st_size
                    n_gpu_layers, _gpu_reason = plan_gpu_layers(
                        size_bytes, max(512, n_ctx), total_layers)
                    if mode == "gpu":
                        # ask for everything; the retry path below still
                        # rescues us if VRAM turns out to be too small
                        n_gpu_layers = total_layers or n_gpu_layers or 999
                    elif mode == "hybrid":
                        half = max(1, int((total_layers or 32) * 0.5))
                        n_gpu_layers = min(half, n_gpu_layers or half)
                except Exception:
                    n_gpu_layers = 0
            try:
                self._llm = Llama(
                    model_path=path,
                    n_ctx=max(512, n_ctx),
                    n_threads=n_threads,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
                self._loaded_path = path
                self.status = "ready"
                gpu_note = f", {n_gpu_layers} layers on GPU" if n_gpu_layers else ", CPU only"
                self.detail = f"{Path(path).name} loaded (ctx {n_ctx}{gpu_note})"
                return True
            except Exception as exc:
                first_error = exc
                if n_gpu_layers > 0:
                    # GPU offload can fail for reasons that have nothing to do
                    # with the file itself (out of VRAM, missing CUDA DLLs,
                    # driver mismatch) - retry CPU-only before giving up, but
                    # only report the GPU failure if the CPU retry also fails
                    # (so we never *pretend* a broken file loaded fine).
                    try:
                        self._llm = Llama(
                            model_path=path,
                            n_ctx=max(512, n_ctx),
                            n_threads=n_threads,
                            n_gpu_layers=0,
                            verbose=False,
                        )
                        self._loaded_path = path
                        self.status = "ready"
                        self.detail = (f"{Path(path).name} loaded (ctx {n_ctx}, CPU only - "
                                       f"GPU offload failed: {first_error})")
                        return True
                    except Exception as exc2:
                        exc = exc2
                self._llm = None
                self._loaded_path = None
                self.status = "error"
                self.detail = (f"could not load this GGUF: {exc}\n"
                               "The file may be corrupt, truncated, or built for a "
                               "newer llama.cpp than the installed one.")
                raise BackendError(self.detail)

    def generate(self, system, messages, max_tokens, on_token, cancel):
        self.prepare()
        chat = [{"role": "system", "content": system}] + list(messages)
        out = []
        with self._lock:
            llm = self._llm
            if llm is None:
                raise BackendError("no local model loaded")
            try:
                stream = llm.create_chat_completion(
                    messages=chat,
                    max_tokens=int(max_tokens),
                    temperature=float(self.settings.get("temperature", 0.85)),
                    stream=True,
                )
                for chunk in stream:
                    if cancel.is_set():
                        break
                    try:
                        delta = chunk["choices"][0].get("delta", {})
                        piece = delta.get("content") or ""
                    except Exception:
                        piece = ""
                    if piece:
                        out.append(piece)
                        on_token(piece)
            except BackendError:
                raise
            except Exception as exc:
                # Some older builds lack chat templates: fall back to raw completion.
                if not out:
                    try:
                        prompt = system + "\n\n" + "\n".join(
                            f"{m['role']}: {m['content']}" for m in messages) + f"\n{CREATURE_NAME}:"
                        result = llm(prompt, max_tokens=int(max_tokens),
                                     temperature=float(self.settings.get("temperature", 0.85)))
                        piece = result["choices"][0]["text"]
                        out.append(piece)
                        on_token(piece)
                    except Exception as exc2:
                        raise BackendError(f"local generation failed: {exc2}")
                else:
                    raise BackendError(f"local generation interrupted: {exc}")
        return "".join(out).strip()

    def _unload_locked(self):
        if self._llm is not None:
            try:
                del self._llm
            except Exception:
                pass
        self._llm = None
        self._loaded_path = None

    def unload(self):
        with self._lock:
            self._unload_locked()
            self.status = "unknown"
            self.detail = "unloaded"


# ------------------------------------------------------------------- ollama
class OllamaBackend(LLMBackend):
    key = "ollama"
    label = "OLLAMA"

    # a small, sane default someone can chat with immediately after install -
    # llama3.2 (~2GB) comfortably fits a 3GB-VRAM card like a GTX 1060.
    RECOMMENDED_MODEL = "llama3.2"

    # official Windows installer - a small self-extracting setup.exe that
    # installs per-user (no admin token required, but Windows may still show
    # a SmartScreen/UAC prompt - that's normal and out of our control).
    WINDOWS_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"

    def host(self):
        return (self.settings.get("ollama_host") or "http://localhost:11434").rstrip("/")

    def model(self):
        """Whatever is currently saved - may or may not actually be
        installed. Use resolve_model() before generating."""
        return self.settings.get("ollama_model") or ""

    def _installed_names(self):
        """Raw query of /api/tags. Returns None if Ollama isn't reachable at
        all (vs. an empty list, which means it's up but has zero models) -
        callers need to tell those two cases apart to report the right
        error. Preserves tags such as 'model:latest' verbatim."""
        try:
            data = _http_json(self.host() + "/api/tags", timeout=4)
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return None

    def list_models(self):
        names = self._installed_names()
        return names or []

    def resolve_model(self, names=None):
        """Return (model_name_or_None, note). Never hands back a model name
        that isn't actually installed: if the saved model is missing, this
        picks the first installed model instead (and remembers that choice)
        rather than silently trying - and failing on - a stale or
        hard-coded name."""
        if names is None:
            names = self._installed_names()
        if names is None:
            return None, "unreachable"
        if not names:
            return None, "no_models"
        configured = self.settings.get("ollama_model") or ""
        if configured in names:
            return configured, "ok"
        # tolerate a saved name without its tag matching an installed
        # name with one (e.g. saved "llama3.2" vs installed "llama3.2:latest")
        configured_base = configured.split(":")[0].strip().lower()
        base_matches = [n for n in names if n.split(":")[0].strip().lower() == configured_base]
        if base_matches:
            return base_matches[0], "ok"
        chosen = names[0]
        if configured != chosen:
            self.settings.set("ollama_model", chosen)
        return chosen, "auto_selected"

    def available(self):
        names = self._installed_names()
        if names is None:
            return False, ("Ollama is not reachable at " + self.host() +
                           ".\nStart it with:  ollama serve")
        if not names:
            return False, (f"Ollama is running at {self.host()} but has no models.\n"
                           f"Try: ollama pull {self.RECOMMENDED_MODEL}")
        chosen, note = self.resolve_model(names)
        if note == "auto_selected":
            return True, (f"saved model wasn't installed - now using '{chosen}' "
                          f"({len(names)} model(s) available)")
        return True, f"Ollama up ({len(names)} models) - using '{chosen}'"

    def describe(self):
        return self.model() or "no model selected"

    # ---------------------------------------------------- install / setup
    @staticmethod
    def _windows_candidate_paths():
        """Common places the Windows installer puts ollama.exe. It installs
        per-user by default (%LOCALAPPDATA%\\Programs\\Ollama), but check the
        machine-wide Program Files locations too in case it was installed
        for all users."""
        candidates = []
        for env_var, sub in (("LOCALAPPDATA", "Programs/Ollama/ollama.exe"),
                             ("PROGRAMFILES", "Ollama/ollama.exe"),
                             ("PROGRAMW6432", "Ollama/ollama.exe"),
                             ("PROGRAMFILES(X86)", "Ollama/ollama.exe")):
            base = os.environ.get(env_var)
            if base:
                candidates.append(Path(base) / Path(sub))
        return candidates

    @classmethod
    def binary_path(cls):
        """Where ollama.exe actually is, checking PATH first and then the
        usual Windows install locations (a freshly-installed Ollama often
        isn't on PATH yet in the *current* process's environment, since
        Windows only refreshes PATH for new processes)."""
        found = shutil.which("ollama")
        if found:
            return found
        if platform.system() == "Windows":
            for candidate in cls._windows_candidate_paths():
                if candidate.exists():
                    return str(candidate)
        return None

    @classmethod
    def is_installed(cls):
        return cls.binary_path() is not None

    def service_reachable(self, timeout=2.5):
        try:
            _http_json(self.host() + "/api/version", timeout=timeout)
            return True
        except Exception:
            return False

    def status_snapshot(self):
        """One cheap, best-effort read of everything the setup UI needs.
        Safe to call from a background thread; never raises."""
        installed = self.is_installed()
        running = self.service_reachable() if installed else False
        models = self.list_models() if running else []
        return {"installed": installed, "running": running, "models": models,
                "host": self.host(), "current_model": self.model()}

    def try_start_service(self):
        """Best-effort: launch `ollama serve` detached in the background.
        Never raises; returns (started, detail)."""
        path = self.binary_path()
        if not path:
            return False, "ollama is not installed"
        try:
            kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                     "stdin": subprocess.DEVNULL}
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            else:
                kwargs["start_new_session"] = True
            subprocess.Popen([path, "serve"], **kwargs)
            return True, "starting ollama serve..."
        except Exception as exc:
            return False, f"could not start ollama: {exc}"

    @staticmethod
    def install_hint():
        """(can_auto_install: bool, manual_instructions: str) - shown as the
        one-click-or-manual fallback the spec asks for."""
        system = platform.system()
        if system == "Darwin":
            if shutil.which("brew"):
                return True, "brew install ollama"
            return False, ("Download the installer from https://ollama.com/download/mac "
                           "and drag Ollama.app into Applications.")
        if system == "Linux":
            return True, "curl -fsSL https://ollama.com/install.sh | sh"
        if system == "Windows":
            return True, ("download the official Windows installer from "
                          "ollama.com and run it")
        return False, "Visit https://ollama.com/download for your platform."

    def install(self, log_cb):
        """Best-effort automatic install for platforms where it's practical
        and permitted (macOS with Homebrew, Linux via the official install
        script). Runs on a worker thread; streams output lines to log_cb().
        NEVER raises - always returns (ok, detail) so the UI can show a
        clear manual fallback instead of crashing."""
        system = platform.system()
        try:
            if system == "Windows":
                return self._install_windows(log_cb)
            if system == "Darwin" and shutil.which("brew"):
                log_cb("installing Ollama via Homebrew...")
                proc = subprocess.Popen(["brew", "install", "ollama"],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1)
            elif system == "Linux":
                log_cb("running the official Ollama install script...")
                # plain `curl | sh` hides a curl failure behind sh's exit code
                # (sh sees an empty pipe and exits 0), so use bash -o pipefail
                # when it's available, and verify the binary landed either way.
                bash = shutil.which("bash")
                if bash:
                    argv = [bash, "-c",
                           "set -o pipefail; curl -fsSL https://ollama.com/install.sh | sh"]
                else:
                    argv = ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"]
                proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, bufsize=1)
            else:
                can_auto, manual = self.install_hint()
                return False, manual
            for line in proc.stdout:
                log_cb(line.rstrip())
            proc.wait(timeout=900)
            installed_now = self.is_installed()
            if proc.returncode == 0 and installed_now:
                return True, "install finished"
            if installed_now:
                return True, "install finished (with warnings - check the log above)"
            return False, (f"installer exited with code {proc.returncode} and the "
                           f"ollama binary still isn't on PATH")
        except FileNotFoundError as exc:
            return False, f"required installer tool not found: {exc}"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    def _install_windows(self, log_cb):
        """Download the official Windows installer, launch it, and wait for
        ollama.exe to actually show up. Windows installers are typically a
        UI that runs and exits in the background, so 'the process launched'
        does NOT mean 'installed' - we poll for the real binary instead.
        NEVER raises; always returns (ok, detail)."""
        if self.is_installed():
            return True, "Ollama is already installed"

        log_cb("checking internet connection...")
        try:
            urllib.request.urlopen(
                urllib.request.Request("https://ollama.com",
                                       headers={"User-Agent": "CREATURE/1.0"}),
                timeout=8)
        except Exception:
            return False, ("no internet connection - couldn't reach ollama.com to "
                           "download the installer. Check your connection and try again.")

        try:
            tmp_dir = Path(tempfile.gettempdir()) / "creature_ollama_setup"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            installer_path = tmp_dir / "OllamaSetup.exe"
        except Exception as exc:
            return False, f"couldn't prepare a temp folder for the installer: {exc}"

        log_cb(f"downloading Ollama installer from {self.WINDOWS_INSTALLER_URL} ...")
        last_pct = [-1]

        def _progress(done, total):
            if total:
                pct = int(done * 100 / total)
                if pct != last_pct[0] and pct % 10 == 0:
                    last_pct[0] = pct
                    log_cb(f"downloading... {pct}%  ({human_size(done)}/{human_size(total)})")
            elif done % (2 * 1024 * 1024) < 262144:
                log_cb(f"downloading... {human_size(done)}")

        try:
            _download_with_progress(self.WINDOWS_INSTALLER_URL, installer_path,
                                    progress_cb=_progress, timeout=30)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return False, f"download failed: {exc}"
        except Exception as exc:
            return False, f"download failed: {type(exc).__name__}: {exc}"

        log_cb("installer downloaded - launching it now.")
        log_cb("Ollama needs permission to install. Windows may show a security prompt.")
        try:
            # Launch normally (no /S / silent flag): this lets Windows show its
            # own UAC / SmartScreen prompt rather than us trying to suppress
            # it, per the requirement that install permission be visible to
            # the user rather than faked or forced through.
            subprocess.Popen([str(installer_path)], shell=False)
        except Exception as exc:
            return False, f"could not launch the installer: {exc}"

        log_cb("waiting for installation to finish...")
        deadline = time.time() + 900          # up to 15 minutes for a slow machine/click-through
        found = False
        while time.time() < deadline:
            time.sleep(2)
            if self.is_installed():
                found = True
                break
        if not found:
            return False, ("the installer is still running (or was closed without "
                           "finishing) - ollama.exe hasn't appeared yet. Finish the "
                           "install window if it's still open, then click RE-CHECK.")

        log_cb("ollama.exe found - install looks complete.")
        return True, "install finished"

    def pull_model(self, name, progress_cb, cancel=None):
        """Streams /api/pull progress. progress_cb(status_text, pct_or_None).
        Returns (ok, detail). Never raises past this point."""
        try:
            for line in _http_stream(self.host() + "/api/pull",
                                     {"name": name, "stream": True}, timeout=3600):
                if cancel is not None and cancel.is_set():
                    return False, "cancelled"
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("error"):
                    return False, str(obj["error"])
                status = obj.get("status", "")
                total, completed = obj.get("total"), obj.get("completed")
                pct = (completed / total) if (total and completed is not None and total > 0) \
                    else None
                progress_cb(status, pct)
                if status == "success":
                    return True, "done"
            return True, "done"
        except Exception as exc:
            return False, _explain_http_error(exc, "Ollama pull")

    @staticmethod
    def _looks_like_gpu_crash(exc):
        """HTTP 5xx or a dropped connection means the llama-server child
        process died (e.g. a CUDA/PTX driver mismatch) rather than a normal
        API error - those are worth an automatic CPU retry. A process that
        dies mid-stream (the actual crash case) surfaces as a truncated
        chunked response or a reset socket, not always a plain
        ConnectionError, so those are matched too."""
        if isinstance(exc, urllib.error.HTTPError) and exc.code >= 500:
            return True
        return isinstance(exc, (ConnectionError, EOFError,
                                http.client.HTTPException))

    def _stream_chat(self, payload, on_token, cancel, out):
        for line in _http_stream(self.host() + "/api/chat", payload, timeout=180):
            if cancel.is_set():
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue                          # malformed line: skip, don't crash
            if obj.get("error"):
                raise BackendError(f"Ollama: {obj['error']}")
            piece = (obj.get("message") or {}).get("content") or ""
            if piece:
                out.append(piece)
                on_token(piece)
            if obj.get("done"):
                break
        return "".join(out).strip()

    def generate(self, system, messages, max_tokens, on_token, cancel):
        names = self._installed_names()
        if names is None:
            raise BackendError("Ollama is not reachable at " + self.host() +
                               ".\nStart it with:  ollama serve")
        if not names:
            raise BackendError(f"Ollama has no models installed. "
                               f"Try: ollama pull {self.RECOMMENDED_MODEL}")
        model, note = self.resolve_model(names)
        if not model:
            raise BackendError("no usable Ollama model is installed")
        options = {
            "temperature": float(self.settings.get("temperature", 0.85)),
            "num_predict": int(max_tokens),
        }
        # once a GPU crash has been seen this session, stop asking Ollama to
        # use the GPU at all - avoids a crash-retry-crash loop on every turn.
        if getattr(self, "_force_cpu", False):
            options["num_gpu"] = 0
        else:
            mode = str(self.settings.get("compute_mode", "auto") or "auto").lower()
            # Ollama places layers itself; num_gpu is a hint, not a promise -
            # so we only send it when the user explicitly picked a mode.
            if mode == "cpu":
                options["num_gpu"] = 0
            elif mode == "hybrid":
                options["num_gpu"] = 20
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + list(messages),
            "stream": True,
            "options": options,
        }
        out = []
        try:
            return self._stream_chat(payload, on_token, cancel, out)
        except BackendError:
            raise
        except Exception as exc:
            if out:
                traceback.print_exc()             # log only - reply already has content
                return "".join(out).strip()
            if not getattr(self, "_force_cpu", False) and self._looks_like_gpu_crash(exc):
                traceback.print_exc()             # technical detail -> log only
                self._force_cpu = True
                payload["options"]["num_gpu"] = 0
                out2 = []
                try:
                    return self._stream_chat(payload, on_token, cancel, out2)
                except BackendError:
                    raise
                except Exception:
                    traceback.print_exc()
                    if out2:
                        return "".join(out2).strip()
                    raise BackendError(
                        "Ollama crashed on the GPU and the automatic CPU retry also "
                        "failed. CREATURE will keep using CPU mode for Ollama; try a "
                        "smaller model or restart Ollama.")
            traceback.print_exc()
            raise BackendError(_explain_http_error(exc, "Ollama"))


# ------------------------------------------------------------------- claude
class ClaudeBackend(LLMBackend):
    key = "claude"
    label = "CLAUDE"
    URL = "https://api.anthropic.com/v1/messages"

    def available(self):
        if not self.settings.secret("claude_api_key"):
            return False, ("No Anthropic API key.\nSet the ANTHROPIC_API_KEY environment "
                           "variable, or paste a key in the MODELS tab.")
        return True, f"key from {self.settings.secret_source('claude_api_key')}"

    def describe(self):
        return self.settings.get("claude_model")

    def generate(self, system, messages, max_tokens, on_token, cancel):
        key = self.settings.secret("claude_api_key")
        if not key:
            raise BackendError(self.available()[1])
        payload = {
            "model": self.settings.get("claude_model"),
            "max_tokens": int(max_tokens),
            "system": system,
            "temperature": float(self.settings.get("temperature", 0.85)),
            "messages": list(messages),
            "stream": True,
        }
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        out = []
        try:
            for line in _http_stream(self.URL, payload, headers, timeout=120):
                if cancel.is_set():
                    break
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if not body or body == "[DONE]":
                    continue
                try:
                    obj = json.loads(body)
                except Exception:
                    continue
                if obj.get("type") == "error":
                    raise BackendError(f"Claude: {obj.get('error', {}).get('message', 'unknown error')}")
                if obj.get("type") == "content_block_delta":
                    piece = (obj.get("delta") or {}).get("text") or ""
                    if piece:
                        out.append(piece)
                        on_token(piece)
                elif obj.get("type") == "message_stop":
                    break
        except BackendError:
            raise
        except Exception as exc:
            if not out:
                raise BackendError(_explain_http_error(exc, "Claude API"))
        return "".join(out).strip()

    # [PHASE 45] a capability distinct from the shared chat `generate()`
    # above: a one-shot, non-streaming, MULTIMODAL call. Deliberately kept
    # separate and explicitly Claude-only (real vision input is not
    # available identically on every backend) rather than added as a
    # silent branch inside `generate`, so callers can never confuse "the
    # currently selected chat backend" with "commentary from Claude" - the
    # two must stay distinguishable, per the no-fake-AI-claims requirement.
    def generate_vision(self, image_b64, media_type, prompt, max_tokens=200):
        key = self.settings.secret("claude_api_key")
        if not key:
            return None, self.available()[1]
        payload = {
            "model": self.settings.get("claude_model"),
            "max_tokens": int(max_tokens),
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": media_type,
                                             "data": image_b64}},
                {"type": "text", "text": prompt},
            ]}],
        }
        req = urllib.request.Request(
            self.URL, data=json.dumps(payload).encode("utf-8"),
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                    "content-type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                obj = json.loads(resp.read().decode("utf-8"))
            if obj.get("type") == "error":
                return None, obj.get("error", {}).get("message", "unknown error")
            text = "".join(b.get("text", "") for b in obj.get("content", [])
                           if b.get("type") == "text").strip()
            return (text or None), None
        except Exception as exc:
            return None, _explain_http_error(exc, "Claude API")


# ------------------------------------------------------------------- gemini
class GeminiBackend(LLMBackend):
    key = "gemini"
    label = "GEMINI"
    BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def available(self):
        if not self.settings.secret("gemini_api_key"):
            return False, ("No Gemini API key.\nSet the GEMINI_API_KEY environment "
                           "variable, or paste a key in the MODELS tab.")
        return True, f"key from {self.settings.secret_source('gemini_api_key')}"

    def describe(self):
        return self.settings.get("gemini_model")

    def generate(self, system, messages, max_tokens, on_token, cancel):
        key = self.settings.secret("gemini_api_key")
        if not key:
            raise BackendError(self.available()[1])
        contents = [{"role": "user" if m["role"] == "user" else "model",
                     "parts": [{"text": m["content"]}]} for m in messages]
        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {
                "maxOutputTokens": int(max_tokens),
                "temperature": float(self.settings.get("temperature", 0.85)),
            },
        }
        url = f"{self.BASE}/{self.settings.get('gemini_model')}:streamGenerateContent?alt=sse&key={key}"
        out = []
        try:
            for line in _http_stream(url, payload, timeout=120):
                if cancel.is_set():
                    break
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if not body:
                    continue
                try:
                    obj = json.loads(body)
                except Exception:
                    continue
                if obj.get("error"):
                    raise BackendError(f"Gemini: {obj['error'].get('message', 'unknown error')}")
                for cand in obj.get("candidates", []):
                    for part in (cand.get("content") or {}).get("parts", []):
                        piece = part.get("text") or ""
                        if piece:
                            out.append(piece)
                            on_token(piece)
        except BackendError:
            raise
        except Exception as exc:
            if not out:
                raise BackendError(_explain_http_error(exc, "Gemini API"))
        return "".join(out).strip()


# --------------------------------------------------------------- gguf files
class GGUFManager:
    """Detects, validates and remembers .gguf models.
    Files are registered in place (never copied) so a 20GB model costs nothing."""

    MAGIC = b"GGUF"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.models = {}            # path -> info dict
        self.load()
        self.scan_folder(MODELS_DIR)

    # -- registry ------------------------------------------------------
    def load(self):
        data = load_json(MODELS_FILE, {})
        for info in (data.get("models", []) if isinstance(data, dict) else []):
            path = info.get("path")
            if path:
                info["exists"] = Path(path).exists()
                self.models[path] = info

    def save(self):
        save_json(MODELS_FILE, {"models": list(self.models.values()),
                                "updated": time.time()})

    def scan_folder(self, folder):
        """Anything dropped into ~/.creature_mind/models is picked up too."""
        found = []
        try:
            folder = Path(folder)
            if folder.exists():
                for path in sorted(folder.glob("*.gguf")):
                    if str(path) not in self.models:
                        info = self.register(str(path), save=False)
                        if info:
                            found.append(info)
        except Exception as exc:
            print(f"[creature] model scan failed: {exc}")
        if found:
            self.save()
        return found

    # -- validation ----------------------------------------------------
    def inspect(self, path):
        """Best-effort GGUF header read.  Returns (ok, info|error)."""
        p = Path(path)
        if not p.exists():
            return False, "file does not exist"
        if p.is_dir():
            return False, "that's a folder, not a .gguf file"
        if p.suffix.lower() != ".gguf":
            return False, f"not a .gguf file (got '{p.suffix or 'no extension'}')"
        size = p.stat().st_size
        if size < 1024 * 128:
            return False, "file is too small to be a real GGUF model"
        try:
            with open(p, "rb") as fh:
                magic = fh.read(4)
                if magic != self.MAGIC:
                    return False, "invalid GGUF header (magic bytes don't match)"
                version = struct.unpack("<I", fh.read(4))[0]
                n_tensors = struct.unpack("<Q", fh.read(8))[0]
                n_kv = struct.unpack("<Q", fh.read(8))[0]
                meta = self._read_metadata(fh, min(n_kv, 256)) if version >= 2 else {}
        except Exception as exc:
            return False, f"could not read GGUF header: {exc}"
        if version not in (1, 2, 3):
            return False, f"unsupported GGUF version {version}"
        return True, {
            "path": str(p), "name": meta.get("general.name") or p.stem,
            "file": p.name, "size": size, "version": version,
            "tensors": int(n_tensors),
            "arch": meta.get("general.architecture", "unknown"),
            "quant": self._guess_quant(p.name),
            "added": time.time(), "status": "registered", "exists": True,
        }

    @staticmethod
    def _guess_quant(name):
        m = re.search(r"(Q\d[_A-Za-z0-9]*|F16|F32|BF16|IQ\d[_A-Za-z0-9]*)", name, re.I)
        return m.group(1).upper() if m else "?"

    def _read_metadata(self, fh, n_kv):
        """Minimal GGUF KV reader - only pulls the couple of keys we display."""
        wanted = {"general.name", "general.architecture"}
        out = {}

        def rd(fmt, size):
            return struct.unpack(fmt, fh.read(size))[0]

        def read_string():
            length = rd("<Q", 8)
            if length > 1 << 20:
                raise ValueError("string too long")
            return fh.read(length).decode("utf-8", "replace")

        def read_value(vtype):
            if vtype == 0:
                return rd("<B", 1)
            if vtype == 1:
                return rd("<b", 1)
            if vtype == 2:
                return rd("<H", 2)
            if vtype == 3:
                return rd("<h", 2)
            if vtype == 4:
                return rd("<I", 4)
            if vtype == 5:
                return rd("<i", 4)
            if vtype == 6:
                return rd("<f", 4)
            if vtype == 7:
                return rd("<?", 1)
            if vtype == 8:
                return read_string()
            if vtype == 9:
                item_type = rd("<I", 4)
                count = rd("<Q", 8)
                for _ in range(min(count, 1 << 22)):
                    read_value(item_type)
                return f"[{count} items]"
            if vtype == 10:
                return rd("<Q", 8)
            if vtype == 11:
                return rd("<q", 8)
            if vtype == 12:
                return rd("<d", 8)
            raise ValueError(f"unknown value type {vtype}")

        try:
            for _ in range(int(n_kv)):
                key = read_string()
                vtype = rd("<I", 4)
                value = read_value(vtype)
                if key in wanted and isinstance(value, str):
                    out[key] = value
                if len(out) == len(wanted):
                    break
        except Exception:
            pass          # metadata is a bonus, never a requirement
        return out

    # -- registration --------------------------------------------------
    def register(self, path, save=True):
        # Normalize paths so relative/absolute spellings cannot create duplicates.
        path = str(Path(path).expanduser().resolve(strict=False))
        ok, result = self.inspect(path)
        if not ok:
            info = {"path": path, "file": Path(path).name, "name": Path(path).stem,
                    "size": Path(path).stat().st_size if Path(path).exists() else 0,
                    "status": "invalid", "note": result, "added": time.time(),
                    "exists": Path(path).exists(), "arch": "-", "quant": "-"}
            self.models[path] = info
            if save:
                self.save()
            return info
        result["note"] = "ok"
        self.models[path] = result
        if save:
            self.save()
        return result

    def register_many(self, paths):
        added, rejected = [], []
        for path in paths:
            info = self.register(path, save=False)
            (added if info.get("status") == "registered" else rejected).append(info)
        self.save()
        return added, rejected

    def remove(self, path):
        key = str(Path(path).expanduser().resolve(strict=False))
        self.models.pop(key, None)
        selected = str(Path(self.settings.get("gguf_path", "")).expanduser().resolve(strict=False)) if self.settings.get("gguf_path") else ""
        if selected == key:
            self.settings.set("gguf_path", "")
        self.save()

    def refresh(self):
        for path in list(self.models.keys()):
            exists = Path(path).exists()
            self.models[path]["exists"] = exists
            if not exists:
                self.models[path]["status"] = "missing"
                self.models[path]["note"] = "file no longer exists"
            elif self.models[path].get("status") != "registered":
                # file exists now but wasn't previously usable (missing,
                # invalid, or an interrupted copy) - re-inspect it properly
                # instead of leaving stale status/metadata behind
                self.register(path, save=False)
        self.scan_folder(MODELS_DIR)
        self.save()

    def valid_models(self):
        return [m for m in self.models.values()
                if m.get("status") == "registered" and m.get("exists")]

    @staticmethod
    def parse_drop(payload):
        """tkdnd hands over a brace-quoted, space separated list."""
        paths, buf, in_brace = [], "", False
        for ch in payload or "":
            if ch == "{":
                in_brace, buf = True, ""
            elif ch == "}":
                in_brace = False
                if buf:
                    paths.append(buf)
                buf = ""
            elif ch == " " and not in_brace:
                if buf:
                    paths.append(buf)
                buf = ""
            else:
                buf += ch
        if buf:
            paths.append(buf)
        return [p for p in paths if p]


# -------------------------------------------------------------- dispatcher
class ModelManager:
    """Owns the backends, the current selection, and safe dispatch.
    A failure in one backend can never take down the application."""

    ORDER = ["local", "ollama", "claude", "gemini"]

    def __init__(self, settings: Settings):
        self.settings = settings
        self.gguf = GGUFManager(settings)
        self.backends = {
            "local": LocalGGUFBackend(settings, self.gguf),
            "ollama": OllamaBackend(settings),
            "claude": ClaudeBackend(settings),
            "gemini": GeminiBackend(settings),
        }
        self.current_key = settings.get("backend", "local")
        if self.current_key not in self.backends:
            self.current_key = "local"
        self.last_error = ""

    @property
    def current(self) -> LLMBackend:
        return self.backends[self.current_key]

    def select(self, key):
        if key in self.backends:
            self.current_key = key
            self.settings.set("backend", key)
            self.last_error = ""
        return self.current

    def status(self):
        try:
            ok, reason = self.current.available()
        except Exception as exc:
            ok, reason = False, f"backend check failed: {exc}"
        return ok, reason

    def generate(self, system, messages, max_tokens, on_token, cancel):
        """Returns (text, error_or_None).  Never raises."""
        backend = self.current
        try:
            ok, reason = backend.available()
            if not ok:
                raise BackendError(reason)
            text = backend.generate(system, messages, max_tokens, on_token, cancel)
            if not text or not text.strip():
                raise BackendError("the model returned an empty response")
            self.last_error = ""
            return text.strip(), None
        except BackendError as exc:
            self.last_error = str(exc)
            return None, str(exc)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            return None, self.last_error
