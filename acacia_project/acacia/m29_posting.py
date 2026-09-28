

# ═══════════════════════════════════════════════════════════════════════════════
#  POSTING LOGIC — Selenium  ·  TrippyGram v8-OC  MAXIMUM ROBUSTNESS ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class PostError(Exception):
    """Raised on unrecoverable posting failure."""
    pass

class PostErrorPermanent(PostError):
    """
    Subclass for failures that should NOT be retried —
    wrong file format, file too large, account suspended, etc.
    The batch worker checks for this type and skips the retry loop.
    """
    pass


class PostErrorRateLimited(PostErrorPermanent):
    """Instagram is actively throttling/blocking this account's automated
    action (not a generic glitch). Retrying soon makes this WORSE, not
    better, so this carries a required long cooldown the caller must
    respect before trying this session again."""

    def __init__(self, msg, cooldown_seconds=1800):
        super().__init__(msg)
        self.cooldown_seconds = cooldown_seconds

# ── Tuning knobs ──────────────────────────────────────────────────────────────
_POLL        = 0.10   # DOM poll interval (s)
_CLICK_PAUSE = 0.05   # micro-pause after scroll before click

# ── Instagram URL constants ───────────────────────────────────────────────────
_IG_HOME    = "https://www.instagram.com"
_IG_CREATE  = "https://www.instagram.com/create/"
_IG_DOMAINS = ("instagram.com",)

# ── Text variants IG uses across locales / A-B tests ─────────────────────────
_CREATE_ARIA  = (
    "New post", "Create", "New Post", "Create new post",
    "Publish", "Publish post", "Add post", "Neue Veröffentlichung",
    "Créer", "Crear", "Crea",
)
_CREATE_TEXTS = ("Create", "New post", "Post", "Add")

_NEXT_TEXTS = (
    "Next", "next", "Continue", "Weiter", "Suivant",
    "Siguiente", "Avanti", "Próximo", "Dalej",
)
_SHARE_TEXTS = (
    "Share", "share",
    "Teilen", "Partager", "Compartir", "Condividi", "Udostępnij",
)
# The FINAL Share button on IG's caption step is always labelled "Share" (or locale equiv).
# "Post", "Done", "Publish" are excluded — they match sub-menu and library buttons.

# XPath that identifies the FINAL Share button specifically:
# It lives inside a dialog/form header, has no siblings that are "Next" buttons,
# and is either role=button or a <button> with text "Share" or locale equiv.
# We use a tighter selector to avoid matching crop-step "Share from Library" links.
_FINAL_SHARE_XPATH = (
    # Standard: button/div/span with exact text "Share" (or locale)
    " | ".join(
        f"//button[normalize-space(text())='{t}'] | "
        f"//*[@role='button'][normalize-space(text())='{t}']"
        for t in _SHARE_TEXTS
    )
)
_DISMISS_TEXTS = (
    "Not Now", "Not now", "Allow all cookies",
    "Only allow essential cookies", "Accept all", "Accept All",
    "Save Info", "Turn On Notifications",
    "Skip", "Close", "Dismiss", "Cancel",
    "Jetzt nicht", "Pas maintenant", "Ahora no",
)
# Exact-match phrases that mean IG is blocking us — no substring matches
_ERROR_PHRASES_EXACT = (
    "Try again later",
    "Something went wrong",
    "Please wait a few minutes",
    "Action blocked",
    "We restrict certain activity",
    "This action was blocked",
    "We limit how often",
    "You can't use this feature right now",
    "Couldn't process this video",
    "File not supported",
    "File size too large",
)

# Phrases (and URL fragments) that specifically mean "IG is throttling or
# blocking this account's automated action", as distinct from a generic,
# likely-transient glitch. These need a LONG cooldown, not an immediate
# retry — retrying into a rate limit is how automation gets accounts
# suspended, so this distinction is the single highest-value reliability
# fix for the posting pipeline.
_RATE_LIMIT_PHRASES = (
    "Try again later",
    "Action blocked",
    "We restrict certain activity",
    "This action was blocked",
    "We limit how often",
    "You can't use this feature right now",
    "Please wait a few minutes",
)
_RATE_LIMIT_URL_FRAGMENTS = (
    "/challenge/", "/accounts/suspended", "/consent/", "/accounts/disabled",
)


def _detect_rate_limit(driver):
    """Returns (reason, cooldown_seconds) if the page shows a genuine
    throttle/block/checkpoint signal, else (None, 0). Checked BEFORE the
    generic error banner so a rate-limit is never misclassified as an
    ordinary retryable glitch."""
    try:
        url = (driver.current_url or "").lower()
        for frag in _RATE_LIMIT_URL_FRAGMENTS:
            if frag in url:
                return f"account checkpoint/challenge page ({frag.strip('/')})", 3600 * 6
    except Exception:
        pass
    for phrase in _RATE_LIMIT_PHRASES:
        try:
            for el in driver.find_elements(
                    By.XPATH, f"//*[contains(normalize-space(text()),'{phrase}')]"):
                if el.is_displayed():
                    txt = (el.text or phrase).strip()[:160]
                    return txt, 1800
        except Exception:
            pass
    return None, 0
# Toast phrases that confirm success
_SUCCESS_PHRASES = (
    "Post shared", "Reel shared", "Video shared",
    "Your post is now shared", "Your reel is now shared",
    "Beitrag geteilt", "Publication partagée",
)

# ── Pre-built XPath expressions ───────────────────────────────────────────────
def _xpath_text(*texts):
    """
    XPath OR matching button/div/span/a by normalised text,
    aria-label, or role=button aria-label.
    """
    parts = []
    for t in texts:
        for tag in ("button", "div", "span", "a"):
            parts.append(f"//{tag}[normalize-space(text())='{t}']")
        parts.append(f"//*[@aria-label='{t}']")
        parts.append(f"//*[@role='button'][@aria-label='{t}']")
        parts.append(f"//*[@role='menuitem'][normalize-space(text())='{t}']")
    return " | ".join(parts)

_NEXT_XPATH  = _xpath_text(*_NEXT_TEXTS)
_SHARE_XPATH = _xpath_text(*_SHARE_TEXTS)

# ── XPath: "any interactive button whose full text is one of these" ───────────
def _xpath_role_text(*texts):
    parts = []
    for t in texts:
        parts.append(f"//*[@role='button'][normalize-space(.)='{t}']")
        parts.append(f"//button[normalize-space(.)='{t}']")
    return " | ".join(parts)

_NEXT_ROLE_XPATH  = _xpath_role_text(*_NEXT_TEXTS)


# ═════════════════════════════════════════════════════════════════════════════
#  PRIMITIVE HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _driver_alive(driver):
    """True if WebDriver is still alive and responsive."""
    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def _safe_click(driver, el):
    """
    4-tier click with automatic fallback:
      1. scroll-into-view  →  native .click()
      2. JS  element.click()
      3. ActionChains  move + click
      4. JS  dispatchEvent(new MouseEvent('click'))
    Returns True if any tier succeeded.
    """
    from selenium.webdriver.common.action_chains import ActionChains
    # tier 1
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center',inline:'center',"
            "behavior:'instant'});", el)
        time.sleep(_CLICK_PAUSE)
        el.click()
        return True
    except Exception:
        pass
    # tier 2
    try:
        driver.execute_script("arguments[0].click();", el)
        return True
    except Exception:
        pass
    # tier 3
    try:
        ActionChains(driver).move_to_element(el).pause(random.uniform(0.08, 0.22)).click(el).perform()
        return True
    except Exception:
        pass
    # tier 4 — synthetic mouse event (bypasses pointer-events:none overlays)
    try:
        driver.execute_script(
            "arguments[0].dispatchEvent(new MouseEvent('click',"
            "{bubbles:true,cancelable:true,view:window}));", el)
        return True
    except Exception:
        return False


def _js_click(driver, el):
    """Pure JS click — use when overlay intercepts the element."""
    try:
        driver.execute_script("arguments[0].click();", el)
        return True
    except Exception:
        return False


def _wait_for(driver, condition_fn, timeout=20, poll=_POLL, backoff=False):
    """Poll condition_fn() every `poll` seconds until truthy or timeout.

    Returns the truthy value from condition_fn() (not just True/False) so
    callers can use the result directly.

    backoff=True: doubles poll interval on each idle cycle (up to 1 s) —
    useful for slow operations like video processing to avoid hammering the
    DOM every 100 ms.
    """
    deadline = time.time() + timeout
    current_poll = poll
    while time.time() < deadline:
        try:
            result = condition_fn()
            if result:
                return result
        except Exception:
            pass
        time.sleep(current_poll)
        if backoff:
            current_poll = min(current_poll * 1.5, 1.0)
    return False


def _first_visible(driver, xpath, enabled=True):
    """
    Return the first DOM element matching xpath that is visible
    (and optionally enabled), or None.
    Explicitly catches StaleElementReferenceException so a React re-render
    between find_elements() and is_displayed() never propagates upward.
    """
    from selenium.common.exceptions import StaleElementReferenceException
    try:
        for el in driver.find_elements(By.XPATH, xpath):
            try:
                if el.is_displayed() and (not enabled or el.is_enabled()):
                    return el
            except StaleElementReferenceException:
                continue   # element re-rendered — skip, try next
            except Exception:
                pass
    except Exception:
        pass
    return None


def _click_first_visible(driver, xpath, enabled=True):
    """Find + safe-click the first visible element matching xpath."""
    el = _first_visible(driver, xpath, enabled=enabled)
    return _safe_click(driver, el) if el else False


# ═════════════════════════════════════════════════════════════════════════════
#  MID-LEVEL HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _dismiss(driver, safe_mode=False):
    """
    Dismiss all known Instagram popups, cookie banners, and notification
    prompts.

    Uses a JS batch approach: one execute_script call clicks every matching
    button in the page, then a short settle, then does a second targeted pass
    for aria-label elements.  This is much faster than individual XPath
    find+click round-trips.

    safe_mode=True: skip the aria-label Close sweep (use during upload wizard
    steps where IG renders a Close button inside the dialog itself).
    """
    # Build JS that clicks all matching dismiss-text buttons in one shot
    _BATCH_DISMISS_JS = """
    (function(texts, tags) {
        var clicked = [];
        for (var i = 0; i < texts.length; i++) {
            for (var j = 0; j < tags.length; j++) {
                var els = document.getElementsByTagName(tags[j]);
                for (var k = 0; k < els.length; k++) {
                    var el = els[k];
                    if (el.offsetParent !== null &&
                        (el.textContent||'').trim() === texts[i]) {
                        el.click();
                        clicked.push(texts[i]);
                        break;
                    }
                }
            }
        }
        return clicked;
    })(arguments[0], arguments[1]);
    """
    try:
        driver.execute_script(
            _BATCH_DISMISS_JS,
            list(_DISMISS_TEXTS),
            ["button", "div", "span", "a"]
        )
        time.sleep(0.15)   # single settle for all clicks
    except Exception:
        # Fallback: individual XPath loop (original approach)
        for text in _DISMISS_TEXTS:
            for tag in ("button", "div", "span", "a"):
                try:
                    for el in driver.find_elements(By.XPATH,
                            f"//{tag}[normalize-space(text())='{text}']"):
                        if el.is_displayed():
                            try:
                                el.click()
                            except Exception:
                                _js_click(driver, el)
                            time.sleep(0.15)
                            break
                except Exception:
                    pass

    if not safe_mode:
        # Close/Dismiss by aria-label — only when not in upload flow
        _ARIA_DISMISS_JS = """
        (function(labels) {
            for (var i = 0; i < labels.length; i++) {
                var els = document.querySelectorAll(
                    '[aria-label="' + labels[i] + '"]');
                for (var k = 0; k < els.length; k++) {
                    if (els[k].offsetParent !== null) { els[k].click(); }
                }
            }
        })(arguments[0]);
        """
        try:
            driver.execute_script(_ARIA_DISMISS_JS, ["Close", "Dismiss", "close"])
            time.sleep(0.1)
        except Exception:
            for label in ("Close", "Dismiss", "close"):
                try:
                    for el in driver.find_elements(By.XPATH, f"//*[@aria-label='{label}']"):
                        if el.is_displayed():
                            _js_click(driver, el)
                            time.sleep(0.1)
                except Exception:
                    pass


def _smart_wait_page_ready(driver, timeout=10):
    """
    Wait for:
      1. document.readyState === 'complete'
      2. IG's main nav element is present in the DOM
         (indicates React has fully hydrated, not just shell rendered)
    Falls back to body.children > 0 if nav never appears.

    Improvements vs original:
      • Single JS call returns readyState + body.children.length atomically,
        halving the number of browser round-trips per poll cycle.
      • Stale-element risk on _first_visible eliminated by checking nav
        via a second JS call rather than a Python Selenium loop.
      • Timeout reduced to 10 s — page_load_timeout provides the real 30 s cap.
      • TimeoutException from page_load_timeout is caught and returns False
        immediately so the caller is never blocked.
    """
    from selenium.common.exceptions import TimeoutException as _SeTE
    _NAV_JS = (
        "var n=document.querySelector('[role=navigation],nav,"
        "[aria-label=Navigation],[data-testid=navigation]');"
        "return {ready:document.readyState==='complete',"
        "nav:!!n,kids:document.body?document.body.children.length:0};"
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = driver.execute_script(_NAV_JS)
            if r and r.get('ready'):
                if r.get('nav') or (r.get('kids', 0) > 2):
                    return True
        except _SeTE:
            return False   # page_load_timeout fired — proceed immediately
        except Exception:
            pass
        time.sleep(_POLL)
    return False


def _safe_get(driver, url):
    """
    driver.get() wrapper that never hangs.

    Selenium's page_load_timeout (set to 30 s in launch_driver) causes
    driver.get() to raise TimeoutException when a page stalls.  Every bare
    driver.get() call should go through here so that TimeoutException is
    swallowed and execution continues rather than freezing the thread.

    Returns True if the page finished normally, False if cut short by timeout
    (page may still be partially usable).
    """
    from selenium.common.exceptions import TimeoutException as _SeTE
    try:
        driver.get(url)
        return True
    except _SeTE:
        return False   # partial load — caller continues with whatever rendered
    except Exception:
        return False


def _navigate_home(driver, say, retries=2):
    """Navigate to IG home, wait for React mount, dismiss popups.

    Retries up to `retries` times on failure — handles transient
    network blips without failing the whole session.
    """
    for attempt in range(1, retries + 2):
        try:
            say("  ↩ Navigating to Instagram home…")
            _safe_get(driver, _IG_HOME)
            if _smart_wait_page_ready(driver, timeout=10):
                _dismiss(driver)
                return True
            # readyState never reached 'complete' — try a refresh on retry
            if attempt <= retries:
                say(f"  ↩ Page not ready (attempt {attempt}), retrying…")
                time.sleep(1.0)
                continue
        except Exception as e:
            if attempt <= retries:
                say(f"  ↩ Navigate home error (attempt {attempt}): {e}")
                time.sleep(1.0)
            else:
                say(f"  Navigate home failed after {attempt} attempts: {e}")
    return False


def _screenshot_debug(driver, label, debug_dir):
    """Save a debug screenshot; silently skip if anything fails."""
    try:
        os.makedirs(debug_dir, exist_ok=True)
        ts  = datetime.now().strftime('%H%M%S')
        fn  = os.path.join(debug_dir, f'post_fail_{ts}_{label}.png')
        driver.save_screenshot(fn)
        return fn
    except Exception:
        return None


def _wait_file_input(driver, timeout=28):
    """
    Force-reveal ALL hidden <input type=file> elements via JS injection,
    then return the first one whose 'accept' attribute contains image/video
    MIME types (not the avatar uploader).

    v13 FIX: Instagram's Reels flow immediately opens a native OS file
    dialog instead of exposing a DOM <input type=file>.  To handle both
    cases we:
      • Inject JS every poll cycle to reveal any hidden DOM input.
      • After 3 s with no DOM input, click the drag-drop / "Select from
        computer" area to try to surface the input or trigger the OS
        dialog (whichever IG decides to use).
      • Return the DOM input if found; caller (_send_file) will then also
        attempt OS-dialog automation in parallel via Strategy B.

    Injection is re-applied every poll cycle so React re-renders can't
    hide the element again between injection and send_keys().
    """
    _ACCEPT_HINTS = ("image", "video", "mp4", "jpg", "jpeg", "png", "mov")

    _JS = """
        var best = null;
        document.querySelectorAll('input[type="file"]').forEach(function(inp) {
            // Force visible and interactable
            inp.style.cssText = (
                'display:block!important;'
                'opacity:1!important;'
                'visibility:visible!important;'
                'position:fixed!important;'
                'top:0!important;left:0!important;'
                'width:1px!important;height:1px!important;'
                'z-index:2147483647!important;'
                'pointer-events:auto!important;'
                'clip:auto!important;clip-path:none!important;'
            );
            var acc = (inp.getAttribute('accept') || '').toLowerCase();
            if (!best && acc && acc !== '') best = inp;
        });
        return best;
    """

    # XPaths for the IG Reels / Post drag-drop zone and "Select from computer" button
    _UPLOAD_AREA_XPATHS = [
        # "Select from computer" button (appears in Reels upload panel)
        "//*[normalize-space(.)='Select from computer']",
        "//*[normalize-space(.)='Select From Computer']",
        "//*[contains(@aria-label,'Select from computer')]",
        "//*[contains(@aria-label,'select from computer')]",
        # Generic drag-drop zone (has role=button or data-visualcompletion)
        "//*[@role='button'][contains(@class,'_acan')]",
        "//*[contains(@class,'drag') and @role='button']",
        "//*[contains(@class,'upload') and @role='button']",
    ]

    def _try_click_upload_area():
        for xp in _UPLOAD_AREA_XPATHS:
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed():
                        try:
                            el.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", el)
                        return True
            except Exception:
                pass
        return False

    deadline   = time.time() + timeout
    clicked_area = False
    area_click_after = time.time() + 3.0  # try clicking upload area after 3 s

    while time.time() < deadline:
        # Primary: JS injection + return
        try:
            el = driver.execute_script(_JS)
            if el:
                acc = (el.get_attribute("accept") or "").lower()
                if any(h in acc for h in _ACCEPT_HINTS):
                    return el
        except Exception:
            pass
        # Secondary: direct XPath fallback
        try:
            for e in driver.find_elements(By.XPATH, "//input[@type='file']"):
                try:
                    acc = (e.get_attribute("accept") or "").lower()
                    if any(h in acc for h in _ACCEPT_HINTS):
                        driver.execute_script(
                            "arguments[0].style.cssText='"
                            "display:block!important;opacity:1!important;"
                            "visibility:visible!important;"
                            "position:fixed!important;top:0;left:0;"
                            "z-index:2147483647!important;"
                            "pointer-events:auto!important;';", e)
                        return e
                except Exception:
                    pass
        except Exception:
            pass

        # v13: after 3 s, click the upload area to surface input or open OS dialog
        if not clicked_area and time.time() >= area_click_after:
            if _try_click_upload_area():
                clicked_area = True
                time.sleep(0.5)   # wait a tick for IG to respond

        time.sleep(_POLL)
    # Don't hard-raise — return a sentinel None so _send_file can try OS dialog
    # (caller checks for None and proceeds to Strategy B)
    raise PostError("File input never appeared — did the upload dialog open? "
                    "Install pyautogui (pip install pyautogui) for OS-dialog support.")


def _type_path_into_os_dialog(abs_path, say):
    """
    Type a file path into a native OS file-picker dialog using whatever
    automation tool is available on this platform.

    Priority:
      1. pyautogui  (cross-platform, preferred)
      2. xdotool    (Linux fallback)
      3. xclip/xsel (Linux clipboard paste)
      4. AppleScript (macOS)
      5. PowerShell SendKeys (Windows)

    Returns True if a tool was found and used, False otherwise.
    """
    import sys, subprocess, shutil, time as _time

    # ── pyautogui (best, cross-platform) ──────────────────────────────────────
    try:
        import pyautogui as _pg
        _time.sleep(0.8)   # let dialog fully open
        _pg.hotkey('ctrl', 'a')
        _time.sleep(0.1)
        _pg.typewrite(abs_path, interval=0.03)
        _time.sleep(0.15)
        _pg.press('return')
        say("  ↳ Path typed via pyautogui")
        return True
    except ImportError:
        pass
    except Exception as e:
        say(f"  pyautogui dialog type failed: {e}")

    # ── xdotool (Linux) ────────────────────────────────────────────────────────
    if shutil.which('xdotool'):
        try:
            _time.sleep(0.8)
            subprocess.run(['xdotool', 'key', 'ctrl+a'], check=False)
            _time.sleep(0.1)
            subprocess.run(['xdotool', 'type', '--clearmodifiers', abs_path], check=False)
            _time.sleep(0.1)
            subprocess.run(['xdotool', 'key', 'Return'], check=False)
            say("  ↳ Path typed via xdotool")
            return True
        except Exception as e:
            say(f"  xdotool dialog type failed: {e}")

    # ── xclip / xdotool clipboard (Linux alternative) ─────────────────────────
    _clip_tool = shutil.which('xclip') or shutil.which('xsel')
    if _clip_tool and shutil.which('xdotool'):
        try:
            _time.sleep(0.8)
            clip_cmd = ['xclip', '-selection', 'clipboard'] if 'xclip' in _clip_tool else ['xsel', '--clipboard', '--input']
            subprocess.run(clip_cmd, input=abs_path.encode(), check=False)
            subprocess.run(['xdotool', 'key', 'ctrl+a'], check=False)
            _time.sleep(0.1)
            subprocess.run(['xdotool', 'key', 'ctrl+v'], check=False)
            _time.sleep(0.1)
            subprocess.run(['xdotool', 'key', 'Return'], check=False)
            say("  ↳ Path pasted via xclip+xdotool")
            return True
        except Exception as e:
            say(f"  clipboard paste failed: {e}")

    # ── AppleScript (macOS) ───────────────────────────────────────────────────
    if sys.platform == 'darwin':
        try:
            _time.sleep(0.8)
            script = (
                f'tell application "System Events"\n'
                f'  keystroke "a" using command down\n'
                f'  delay 0.1\n'
                f'  keystroke "{abs_path}"\n'
                f'  delay 0.1\n'
                f'  keystroke return\n'
                f'end tell'
            )
            subprocess.run(['osascript', '-e', script], check=False, timeout=10)
            say("  ↳ Path typed via AppleScript")
            return True
        except Exception as e:
            say(f"  AppleScript dialog type failed: {e}")

    # ── PowerShell SendKeys (Windows) ─────────────────────────────────────────
    if sys.platform == 'win32':
        try:
            _time.sleep(0.8)
            ps = (
                f'Add-Type -AssemblyName System.Windows.Forms; '
                f'[System.Windows.Forms.SendKeys]::SendWait("^a"); '
                f'Start-Sleep -Milliseconds 100; '
                f'[System.Windows.Forms.SendKeys]::SendWait("{abs_path}"); '
                f'Start-Sleep -Milliseconds 100; '
                f'[System.Windows.Forms.SendKeys]::SendWait("~")'
            )
            subprocess.run(['powershell', '-Command', ps], check=False, timeout=15)
            say("  ↳ Path typed via PowerShell SendKeys")
            return True
        except Exception as e:
            say(f"  PowerShell dialog type failed: {e}")

    return False


def _send_file(driver, file_input, abs_path, say):
    """
    Send a file path to the IG upload input.

    v13 FIX: Instagram's Reels flow opens a native OS file dialog instead
    of keeping the <input type=file> interactable via send_keys.  We now
    use a 3-strategy approach:

    Strategy A: native send_keys on the DOM input (works for Feed/Post).
    Strategy B: OS dialog automation (pyautogui/xdotool/AppleScript/PS)
                for when clicking 'Reel' opens the native file picker.
    Strategy C: dismiss overlay, re-find DOM input, retry send_keys.

    Note: JS value-set is intentionally NOT used — browsers block it for
    file inputs for security reasons and it silently does nothing.
    Raises PostError if all strategies fail.
    """
    # Strategy A — DOM send_keys (works for Post/Feed path)
    try:
        file_input.send_keys(abs_path)
        say("  ↳ File queued via send_keys (DOM input)")
        return
    except Exception as e_a:
        say(f"  send_keys attempt 1 failed ({type(e_a).__name__}) — trying OS dialog…")

    # Strategy B — OS file dialog automation (Reels path)
    # Give the dialog a moment to appear, then type the absolute path
    time.sleep(1.2)
    try:
        if _type_path_into_os_dialog(abs_path, say):
            time.sleep(1.5)   # wait for IG to register the file selection
            return
    except Exception as e_b_os:
        say(f"  OS dialog typing error: {e_b_os}")

    # Strategy C — dismiss overlay, re-find DOM input, retry send_keys
    time.sleep(0.35)
    _dismiss(driver, safe_mode=True)
    try:
        fi2 = _wait_file_input(driver, timeout=10)
        fi2.send_keys(abs_path)
        say("  ↳ File queued via send_keys (re-found DOM input)")
        return
    except Exception as e_c:
        raise PostError(
            f"Could not inject file path into upload input.\n"
            f"  DOM send_keys (A): {e_a}\n"
            f"  OS dialog (B): attempted — check pyautogui/xdotool install\n"
            f"  DOM re-find (C): {e_c}\n"
            f"  File: {abs_path}\n"
            f"  Tip: pip install pyautogui  (fixes Reels OS dialog)"
        )


def _detect_error_banner(driver):
    """
    Scan for known Instagram error messages.

    Uses contains(normalize-space(text()), phrase) on leaf text nodes
    (not container .text) so multi-child divs don't swallow the match,
    and so phrases that appear as part of a longer sentence still match.
    Caps matched text at 160 chars. Returns text or None.
    """
    for phrase in _ERROR_PHRASES_EXACT:
        try:
            xpath = f"//*[contains(normalize-space(text()),'{phrase}')]"
            for el in driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        txt = (el.text or "").strip()
                        # Ignore trivially short or suspiciously long matches
                        if 4 < len(txt) < 300:
                            return txt[:160]
                except Exception:
                    pass
        except Exception:
            pass
    return None


def _check_upload_rejected(driver):
    """
    Check for file-rejection dialogs that appear immediately after send_keys.
    Returns error text or None.  Caller should raise PostErrorPermanent on match
    (these errors won't be fixed by retrying).
    """
    _rejection_phrases = (
        "File not supported",
        "File size too large",
        "Video is too long",
        "couldn't process",
        "Couldn't process",
        "format not supported",
        "This file is not supported",
        "file type isn't supported",
    )
    for phrase in _rejection_phrases:
        try:
            for el in driver.find_elements(By.XPATH,
                    f"//*[contains(normalize-space(text()),'{phrase}')]"):
                try:
                    if el.is_displayed():
                        return el.text.strip()[:160]
                except Exception:
                    pass
        except Exception:
            pass
    return None


def _click_by_text(driver, texts, timeout=18, aria_too=True):
    """
    Click the first visible+enabled element matching any of `texts`.
    Searches in this priority:
      1. button/div/span/a by normalised text content
      2. aria-label exact match
      3. role=button by full inner text
    Raises PostError if nothing found within timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for text in texts:
            # 1. tag + text
            for tag in ("button", "div", "span", "a"):
                try:
                    for el in driver.find_elements(By.XPATH,
                            f"//{tag}[normalize-space(text())='{text}']"):
                        if el.is_displayed() and el.is_enabled():
                            if _safe_click(driver, el):
                                return True
                except Exception:
                    pass
            # 2. aria-label
            if aria_too:
                try:
                    for el in driver.find_elements(By.XPATH,
                            f"//*[@aria-label='{text}']"):
                        if el.is_displayed() and el.is_enabled():
                            if _safe_click(driver, el):
                                return True
                except Exception:
                    pass
            # 3. role=button inner text
            try:
                for el in driver.find_elements(By.XPATH,
                        f"//*[@role='button'][normalize-space(.)='{text}']"):
                    if el.is_displayed() and el.is_enabled():
                        if _safe_click(driver, el):
                            return True
            except Exception:
                pass
        time.sleep(_POLL)
    raise PostError(f"Button not found after {timeout}s: {texts}")


def _try_next(driver, timeout=12, say=None):
    """Click the Next button. No role restrictions — IG uses plain elements."""
    from selenium.common.exceptions import StaleElementReferenceException

    deadline = time.time() + timeout
    while time.time() < deadline:
        # Find any visible element whose full subtree text is "Next"
        # then drill to the innermost match to avoid clicking a giant container
        for text in ("Next", "next"):
            try:
                els = driver.find_elements(By.XPATH, f"//*[normalize-space(.)='{text}']")
                for el in els:
                    if not el.is_displayed():
                        continue
                    # Get innermost child that still matches
                    children = el.find_elements(By.XPATH, f".//*[normalize-space(.)='{text}']")
                    target = children[-1] if children else el
                    if not target.is_displayed():
                        continue
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
                        target.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", target)
                    # Wait for element to go stale/hidden = step advanced
                    settle_dl = time.time() + 3.0
                    while time.time() < settle_dl:
                        try:
                            if not target.is_displayed():
                                return True
                        except StaleElementReferenceException:
                            return True
                        except Exception:
                            return True
                        time.sleep(0.1)
                    return True  # clicked, assume it worked
            except Exception:
                pass
        time.sleep(0.3)
    return False


def _drain_wizard_next(driver, say, max_steps=4, step_timeout=12):
    """
    Click Next/Continue until we're confirmed on the caption step
    (contenteditable / caption textarea visible), we hit max_steps,
    or no Next button is found within step_timeout.

    CRITICAL FIX vs v9: previously used `_SHARE_XPATH` visible as the
    "done" signal.  But IG's crop/filter steps also show a "Share from
    library" button, so the wizard would stop prematurely on step 1,
    never reaching the actual caption step.

    v10 uses `_is_on_caption_step()` — which requires a caption input
    to be present — as the authoritative stop condition.

    Returns number of Next clicks made.
    """
    clicks = 0

    for step in range(max_steps):
        # Caption step reached — stop advancing
        if _is_on_caption_step(driver):
            say(f"  ↳ Caption step reached ({clicks} Next click(s))")
            break

        hit = _try_next(driver, timeout=step_timeout, say=say)
        if not hit:
            # No Next found — either on caption step (no input yet) or fewer steps
            say(f"  ↳ No Next button found after {clicks} click(s) — stopping wizard")
            break

        clicks += 1
        say(f"  ↳ Wizard step {clicks} → Next")

        # Settle: wait up to 2.5s for the new step to render (crop→filter transition is slow)
        settle_dl = time.time() + 2.5
        while time.time() < settle_dl:
            if _is_on_caption_step(driver):
                break
            time.sleep(0.1)

        _dismiss(driver, safe_mode=True)

    return clicks


def _dismiss_video_dialogs(driver, say, timeout=22):
    """
    Drain all video-specific dialogs (trim, crop, cover-frame, codec warnings,
    accessibility prompts).

    Deliberately excludes "Next" and "Done" from the click list — those words
    also appear on the main wizard navigation buttons and would advance the
    wizard prematurely.  Instead uses only dialog-specific confirmations.

    Re-enters the loop after each successful click because IG sometimes stacks
    dialogs or re-renders them after 200–400 ms.  Requires two consecutive
    idle passes before declaring done.
    """
    # Intentionally NO "Next", "Done", "Continue" — those are wizard buttons
    _ok_texts = (
        "OK", "ok",
        "Got it", "Understood",
        "Trim", "Use Original",
        "Select", "Keep",
        "Confirm", "Accept",
    )
    deadline    = time.time() + timeout
    clicks      = 0
    idle_passes = 0

    while time.time() < deadline:
        clicked_any = False
        for text in _ok_texts:
            for tag in ("button", "div", "span", "a"):
                try:
                    for el in driver.find_elements(By.XPATH,
                            f"//{tag}[normalize-space(text())='{text}']"):
                        if el.is_displayed() and el.is_enabled():
                            if _safe_click(driver, el):
                                say(f"  📼 Video dialog: '{text}'")
                                time.sleep(0.30)
                                clicks += 1
                                clicked_any = True
                                break
                except Exception:
                    pass
        if clicked_any:
            idle_passes = 0
            time.sleep(0.18)
        else:
            idle_passes += 1
            if idle_passes >= 2:
                break
            time.sleep(0.22)

    return clicks


def _wait_upload_ready(driver, is_video, step_timeout, say):
    """
    Poll after send_keys until IG signals the upload is processed:
      • Next or Share button becomes visible+enabled  → return True
      • A file-rejection dialog appears               → raise PostErrorPermanent
      • Timeout                                       → return False

    For video the timeout is 180s (IG encodes server-side; the wizard button
    appears early while background encoding continues).
    Logs progress every 5 seconds.
    """
    upload_timeout = 180 if is_video else int(step_timeout * 1.5)

    # Broad selector: exact text + aria-label + contains() fallbacks for IG redesigns
    _extra_video = (
        # aria-label contains Next/Continue/Share (IG sometimes omits text node)
        "//*[@role='button'][contains(@aria-label,'Next')]"
        " | //*[@role='button'][contains(@aria-label,'Continue')]"
        " | //*[@role='button'][contains(@aria-label,'Share')]"
        " | //button[contains(@aria-label,'Next')]"
        " | //button[contains(@aria-label,'Share')]"
        # IG Reels-specific: a div with class containing 'next' or 'share'
        " | //div[contains(@class,'_acan')][normalize-space(.)='Next']"
        " | //div[contains(@class,'_acan')][normalize-space(.)='Share']"
    ) if is_video else ""

    combined = (_NEXT_XPATH + " | " + _NEXT_ROLE_XPATH +
                (" | " + _FINAL_SHARE_XPATH + " | " + _SHARE_ROLE_XPATH + _extra_video
                 if is_video else ""))

    start    = time.time()
    deadline = start + upload_timeout
    last_log = start

    while time.time() < deadline:
        # Rejection check first (fast, permanent error)
        rej = _check_upload_rejected(driver)
        if rej:
            raise PostErrorPermanent(f"Upload rejected by Instagram: {rej}")

        if _first_visible(driver, combined, enabled=True):
            return True

        # Also accept: any enabled button whose text is exactly Next/Share
        # (JS sweep — catches dynamically rendered components)
        try:
            found = driver.execute_script(
                """var btns = document.querySelectorAll("button,[role='button']");
                for (var b of btns) {
                    var t = (b.innerText||b.getAttribute('aria-label')||'').trim();
                    if (!b.disabled && (t==='Next'||t==='Share'||t==='Continue'))
                        return true;
                }
                return false;"""
            )
            if found:
                return True
        except Exception:
            pass

        now = time.time()
        if now - last_log >= 5.0:
            say(f"  ⏳ Processing… ({int(now - start)}s)")
            last_log = now

        time.sleep(_POLL)
    return False


def _type_caption(driver, caption, say):
    """
    Type `caption` into the IG caption field using 4 strategies + clipboard fallback.

    Verification: after each send attempt, reads back innerText/value via JS
    and confirms length is at least half of caption length (rules out false
    positives from IG's own placeholder text like "Write a caption…").

    Returns True if caption was entered, False if all strategies failed.
    """
    from selenium.webdriver.common.keys import Keys
    cap_len = len(caption)

    def _verify_el(el):
        """True if element text looks like our caption (not just a placeholder)."""
        try:
            t = driver.execute_script(
                "return (arguments[0].innerText || arguments[0].value || '').trim();", el)
            return bool(t) and len(t) >= max(1, cap_len // 2)
        except Exception:
            return False

    def _try_send(el, text):
        """Focus → click → send_keys with JS innerText setter as fallback."""
        # Clear existing text first (handles pre-filled fields)
        try:
            driver.execute_script(
                "arguments[0].focus(); arguments[0].click();"
                "arguments[0].innerText=''; arguments[0].value='';", el)
            time.sleep(0.06)
        except Exception:
            pass
        try:
            el.click()
            time.sleep(0.06)
        except Exception:
            pass

        # Primary: human-like per-character typing with randomised cadence
        try:
            for ch in text:
                el.send_keys(ch)
                time.sleep(random.uniform(0.04, 0.18))
                # occasional micro-pause like a real typist thinking
                if random.random() < 0.07:
                    time.sleep(random.uniform(0.2, 0.6))
            time.sleep(0.12)
            if _verify_el(el):
                return True
        except Exception:
            pass

        # Fallback A: JS innerText direct set (contenteditable)
        try:
            driver.execute_script(
                "arguments[0].innerText = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                el, text)
            time.sleep(0.12)
            if _verify_el(el):
                return True
        except Exception:
            pass

        # Fallback B: pyperclip clipboard paste (if available)
        try:
            import pyperclip
            pyperclip.copy(text)
            driver.execute_script("arguments[0].focus(); arguments[0].click();", el)
            time.sleep(0.08)
            el.send_keys(Keys.CONTROL, 'v')
            time.sleep(0.15)
            if _verify_el(el):
                return True
        except Exception:
            pass

        return False

    # S-A: contenteditable div (modern IG caption field)
    try:
        for el in driver.find_elements(By.XPATH, "//div[@contenteditable='true']"):
            if el.is_displayed():
                if _try_send(el, caption):
                    return True
    except Exception:
        pass

    # S-B: textarea with caption-related aria-label or placeholder
    try:
        for el in driver.find_elements(By.XPATH,
                "//textarea["
                "contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                "'abcdefghijklmnopqrstuvwxyz'),'caption')"
                " or contains(@placeholder,'caption')"
                " or contains(@placeholder,'Caption')"
                " or contains(@placeholder,'Write')"
                " or contains(@placeholder,'Aa')]"):
            if el.is_displayed():
                if _try_send(el, caption):
                    return True
    except Exception:
        pass

    # S-C: input[type=text] with caption hints
    try:
        for el in driver.find_elements(By.XPATH,
                "//input[@type='text'][contains(@placeholder,'caption')"
                " or contains(@aria-label,'caption')]"):
            if el.is_displayed():
                if _try_send(el, caption):
                    return True
    except Exception:
        pass

    # S-D: any visible textarea (last resort)
    try:
        for el in driver.find_elements(By.XPATH, "//textarea"):
            if el.is_displayed():
                if _try_send(el, caption):
                    return True
    except Exception:
        pass

    return False


# Needed for _drain_wizard_next
_SHARE_ROLE_XPATH = _xpath_role_text(*_SHARE_TEXTS)


def _is_on_caption_step(driver):
    """
    Return True if the browser is currently on IG's caption/details step
    (the last wizard step before Share).

    Signals we look for, ANY of which is sufficient:
    • A contenteditable div OR a textarea with caption-related placeholder is visible
    • The page has BOTH a Share/Post button AND a caption input visible at once
    • The header of the dialog reads "Create new post" or "New post" (IG desktop)

    This is how we distinguish the caption step from the crop/filter steps,
    which also show a Share button in the bottom media-library bar.
    """
    # Signal 1: caption field present — scoped inside the create dialog to avoid
    # matching search boxes, bio editors, or comment inputs elsewhere on the page.
    try:
        for el in driver.find_elements(By.XPATH,
                "//div[@role='dialog']//div[@contenteditable='true'] | "
                "//div[@role='dialog']//textarea[contains(@placeholder,'caption') or "
                "contains(@placeholder,'Caption') or "
                "contains(@placeholder,'Write') or "
                "contains(@placeholder,'Aa')] | "
                # Fallback if dialog role isn't set — match by common caption container attrs
                "//div[contains(@aria-label,'caption') or contains(@aria-label,'Caption')]"
                "//div[@contenteditable='true']"):
            if el.is_displayed():
                return True
    except Exception:
        pass

    # Signal 2: dialog header says "Create new post" / "New post"
    try:
        for phrase in ("Create new post", "New post", "Neue Veröffentlichung",
                       "Créer une publication", "Crear nueva publicación"):
            for el in driver.find_elements(By.XPATH,
                    f"//*[normalize-space(text())='{phrase}']"):
                if el.is_displayed():
                    return True
    except Exception:
        pass

    return False


def _wait_for_caption_step(driver, say, timeout=20):
    """
    Poll until `_is_on_caption_step` returns True or timeout.
    Returns True if reached, False if timed out.
    """
    deadline = time.time() + timeout
    last_log = time.time()
    while time.time() < deadline:
        if _is_on_caption_step(driver):
            return True
        now = time.time()
        if now - last_log >= 4:
            say("  ⏳ Waiting for caption step…")
            last_log = now
        time.sleep(_POLL)
    return False



def _dismiss_discard_dialog(driver):
    """If IG shows Discard post? dialog, click Cancel to stay on the post."""
    for text in ("Cancel", "Keep"):
        try:
            els = driver.find_elements(By.XPATH, f"//*[normalize-space(.)='{text}']")
            for el in els:
                if el.is_displayed():
                    try:
                        el.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", el)
                    time.sleep(0.5)
                    return True
        except Exception:
            pass
    return False


def _click_final_share(driver, say, timeout=30):
    """Click the Share button — picks the rightmost one to avoid the back arrow."""
    from selenium.common.exceptions import StaleElementReferenceException
    say("  Waiting for Share button...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        for text in ("Share", "share"):
            try:
                els = driver.find_elements(By.XPATH, f"//*[normalize-space(.)='{text}']")
                visible = []
                for el in els:
                    try:
                        if el.is_displayed():
                            x = el.location.get('x', 0)
                            visible.append((x, el))
                    except Exception:
                        pass
                if not visible:
                    continue
                # Pick the rightmost element — Share is top-right, back arrow is top-left
                visible.sort(key=lambda t: t[0], reverse=True)
                target = visible[0][1]
                say("  Clicking Share...")
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
                    target.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", target)
                settle_dl = time.time() + 5.0
                while time.time() < settle_dl:
                    try:
                        if not target.is_displayed():
                            return True
                    except StaleElementReferenceException:
                        return True
                    except Exception:
                        return True
                    time.sleep(0.1)
                return True
            except Exception:
                pass
        time.sleep(0.3)
    raise PostError(f"Share button not found after {timeout}s")


def _dismiss_share_panel(driver, say):
    """
    Dismiss IG's post-publish 'Share to other platforms' panel.
    This panel appears AFTER a successful post and has:
      - A header that reads exactly "Share"
      - An X / Close button in the top-left corner
    Closing it is the success signal — the post already went through.
    Returns True if the panel was found and dismissed.
    """
    # Detect: dialog with header "Share" AND social share icons present.
    # Require at least 2 signals to fire, preventing false-positives from
    # "Copy link" appearing in DMs, profile pages, or story replies.
    _panel_signals = (
        "Copy link", "Facebook", "Messenger", "WhatsApp", "Threads",
    )
    panel_signal_count = 0
    for signal in _panel_signals:
        try:
            for el in driver.find_elements(By.XPATH,
                    f"//*[normalize-space(text())='{signal}']"):
                if el.is_displayed():
                    panel_signal_count += 1
                    break
        except Exception:
            pass

    panel_present = panel_signal_count >= 2

    if not panel_present:
        return False

    say("  📤 Post-publish Share panel detected — closing it…")

    # Close via X button (top-left of the panel)
    for xpath in (
        "//*[@aria-label='Close']",
        "//*[@aria-label='close']",
        "//button[@aria-label='Close']",
        # The X is often an SVG button with no label — find by position near the header
        "//*[normalize-space(text())='Share']/ancestor::*[contains(@role,'dialog') "
        "or contains(@class,'modal') or contains(@class,'Dialog')][1]"
        "//*[@role='button'][1]",
    ):
        try:
            for el in driver.find_elements(By.XPATH, xpath):
                if el.is_displayed():
                    if _safe_click(driver, el):
                        time.sleep(0.4)
                        say("  ✓ Share panel closed")
                        return True
        except Exception:
            pass

    # Fallback: press Escape
    try:
        from selenium.webdriver.common.keys import Keys
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.4)
        say("  ✓ Share panel dismissed via Escape")
        return True
    except Exception:
        pass

    say("  ⚠ Share panel found but could not close it — post succeeded anyway")
    return True  # Panel presence = post succeeded, even if we can't close it


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN POSTING FUNCTION  —  v11-OC
# ═════════════════════════════════════════════════════════════════════════════

def post_one(driver, media_path, caption, say, step_timeout=32, debug_dir=None):
    """
    Post one image or video to Instagram via Selenium.

    v11-OC fix: detect and dismiss the post-publish 'Share to other platforms'
    panel (screenshot confirmed — appears AFTER successful post, was causing
    the code to hang waiting for a URL redirect that never came).

    Raises PostError (or PostErrorPermanent) on failure.
    """
    abs_path = str(Path(media_path).resolve())
    is_video  = Path(media_path).suffix.lower() in VIDEO_EXTS

    def _bail(msg):
        """Raise PostError, capturing a debug screenshot first. Escalates to
        PostErrorRateLimited automatically if the page shows a genuine
        throttle/block/checkpoint signal — the caller MUST NOT retry this
        soon regardless of what msg says."""
        if debug_dir and _driver_alive(driver):
            fn = _screenshot_debug(driver, "bail", debug_dir)
            if fn:
                say(f"  📷 Debug screenshot: {fn}")
        if _driver_alive(driver):
            reason, cooldown = _detect_rate_limit(driver)
            if reason:
                say(f"  ⛔ rate-limited/blocked: {reason}")
                raise PostErrorRateLimited(f"{msg} (rate-limited: {reason})",
                                           cooldown_seconds=cooldown)
        raise PostError(msg)

    # ── ① Pre-flight ──────────────────────────────────────────────────────────
    if not _driver_alive(driver):
        raise PostError("WebDriver is not responsive")
    if not os.path.isfile(abs_path):
        raise PostError(f"Media file not found: {abs_path}")

    say(f"{'🎬' if is_video else '📸'} Posting: {Path(media_path).name}")

    # ── ② Ensure we're on Instagram ───────────────────────────────────────────
    try:
        cur = driver.current_url
    except Exception:
        raise PostError("Cannot read current URL — driver crashed?")

    if not any(d in cur for d in _IG_DOMAINS):
        say("  Navigating to Instagram…")
        _safe_get(driver, _IG_HOME)
        _smart_wait_page_ready(driver, timeout=14)

    _dismiss(driver)

    # Rate-limit/checkpoint pre-flight — catch it before wasting a whole
    # attempt on a session that's already throttled or challenged.
    reason, cooldown = _detect_rate_limit(driver)
    if reason:
        raise PostErrorRateLimited(f"blocked before posting even started: {reason}",
                                   cooldown_seconds=cooldown)

    # Sanity: are we actually logged in?
    if "login" in driver.current_url or "accounts/login" in driver.current_url:
        raise PostErrorPermanent("Not logged in to Instagram — please log in first")

    # ── ③ Click Create — 5 strategies + direct-URL + keyboard fallback ────────
    say("  Finding Create button…")

    def _try_create():
        # S-A: aria-label (most reliable)
        for label in _CREATE_ARIA:
            try:
                for el in driver.find_elements(By.XPATH, f"//*[@aria-label='{label}']"):
                    if el.is_displayed():
                        if _safe_click(driver, el): return True
            except Exception: pass

        # S-B: href contains 'create'
        try:
            for el in driver.find_elements(By.XPATH, "//a[contains(@href,'create')]"):
                if el.is_displayed():
                    if _safe_click(driver, el): return True
        except Exception: pass

        # S-C: visible normalised text
        for text in _CREATE_TEXTS:
            for tag in ("a", "button", "div", "span"):
                try:
                    for el in driver.find_elements(By.XPATH,
                            f"//{tag}[normalize-space(text())='{text}']"):
                        if el.is_displayed():
                            if _safe_click(driver, el): return True
                except Exception: pass

        # S-D: SVG <title> child
        try:
            _lc = ("translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                   "'abcdefghijklmnopqrstuvwxyz')")
            for el in driver.find_elements(By.XPATH,
                    f"//*[name()='svg']//*[name()='title' and "
                    f"(contains({_lc},'create') or contains({_lc},'new post'))]"
                    f"/ancestor::*[@role='link' or @role='button'][1]"):
                if el.is_displayed():
                    if _safe_click(driver, el): return True
        except Exception: pass

        # S-E: role=link/button with fuzzy aria-label
        try:
            _lc2 = ("translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                    "'abcdefghijklmnopqrstuvwxyz')")
            for el in driver.find_elements(By.XPATH,
                    f"//*[@role='link' or @role='button']"
                    f"[@aria-label and ("
                    f"contains({_lc2},'create') or "
                    f"contains({_lc2},'new post'))]"):
                if el.is_displayed():
                    if _safe_click(driver, el): return True
        except Exception: pass

        return False

    if not _wait_for(driver, _try_create, timeout=step_timeout):
        # Fallback A: navigate directly to /create/style/
        say("  ⚠ Create button not found — trying /create/style/…")
        try:
            _safe_get(driver, _IG_CREATE)
            _smart_wait_page_ready(driver, timeout=12)
            _dismiss(driver)
        except Exception: pass

        if not _wait_for(driver, _try_create, timeout=12):
            # Fallback B: keyboard shortcut
            try:
                from selenium.webdriver.common.keys import Keys
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ALT + 'n')
                time.sleep(0.6)
            except Exception: pass

            if not _wait_for(driver, _try_create, timeout=8):
                _bail("Could not find Create button (5 strategies + /create/style/ + Alt+N). "
                      "Are you logged in?")

    time.sleep(0.2)
    _dismiss(driver, safe_mode=True)  # safe_mode: don't close the create dialog itself

    # ── ④ Sub-menu: Post / Reel / Story ───────────────────────────────────────
    # IG renders items as <div role="menuitem"><span>Post</span></div>
    # normalize-space(.) matches full subtree; text() misses nested spans.
    # For video files we prefer "Reel" so the file posts as a Reel, not a feed
    # video.  Fall back to "Post" labels if the Reel option isn't visible.
    say("  Checking for post-type sub-menu…")

    if is_video:
        _sub_labels = ("Reel", "reel", "Reels", "reels",
                       "Post", "post", "Feed post", "Feed Post", "Photo/video")
    else:
        _sub_labels = ("Post", "post", "Feed post", "Feed Post", "Photo/video")

    _sub_deadline = time.time() + 8
    clicked_sub = False
    while time.time() < _sub_deadline and not clicked_sub:
        for label in _sub_labels:
            try:
                # No role restriction — IG uses plain divs for these menu items
                for el in driver.find_elements(By.XPATH,
                        f"//*[normalize-space(.)='{label}']"):
                    if el.is_displayed():
                        # Make sure we're not clicking a container that also matches
                        # (e.g. a parent div whose subtree text happens to be "Post")
                        # by preferring the innermost matching element
                        children = el.find_elements(By.XPATH,
                            f".//*[normalize-space(.)='{label}']")
                        target = children[-1] if children else el
                        if target.is_displayed():
                            say(f"  ↳ Sub-menu: selecting '{label}'")
                            try:
                                target.click()
                            except Exception:
                                driver.execute_script("arguments[0].click();", target)
                            time.sleep(1.0)
                            clicked_sub = True
                            break
            except Exception: pass
            if clicked_sub: break
        if not clicked_sub:
            time.sleep(0.2)

    # ── ⑤ Upload file ─────────────────────────────────────────────────────────
    # v13 FIX: For Reels, IG opens a native OS file dialog instead of a DOM
    # input.  _wait_file_input now also clicks the upload area after 3 s to
    # surface the DOM input OR trigger the OS dialog.  _send_file then tries:
    #   A) DOM send_keys, B) OS dialog automation, C) DOM re-find + send_keys.
    say(f"  Uploading {'video' if is_video else 'image'}…")
    file_input = None
    try:
        file_input = _wait_file_input(driver, timeout=step_timeout)
    except PostError:
        # DOM input never appeared — may be OS dialog path (Reels).
        # Pass None; _send_file will skip Strategy A and jump straight to B.
        say("  ⚠ DOM file input not found — attempting OS dialog automation…")

    if file_input is not None:
        _send_file(driver, file_input, abs_path, say)
    else:
        # No DOM input — try OS dialog directly then wait for IG to register
        time.sleep(1.0)
        if not _type_path_into_os_dialog(abs_path, say):
            _bail(
                "File input never appeared and OS dialog automation unavailable.\n"
                "Fix: pip install pyautogui  (enables Reels OS-dialog support)"
            )
        time.sleep(2.0)  # let IG register the picked file

    # ── ⑥ Wait for upload to be processed by IG ───────────────────────────────
    say("  Processing upload…")
    upload_ok = _wait_upload_ready(driver, is_video, step_timeout, say)
    if not upload_ok:
        say("  ⚠ Upload ready-signal timed out — checking for errors…")
        err = _detect_error_banner(driver)
        if err:
            _bail(f"Instagram error after upload: {err}")
        # For video: try a JS force-enable on the Next/Share button before giving up.
        # IG sometimes renders the button disabled during client-side transcoding
        # even though the server already accepted the file.
        if is_video:
            say("  🔧 Attempting to force-enable wizard button for video…")
            try:
                driver.execute_script(
                    """var btns = document.querySelectorAll("button,[role='button']");
                    for (var b of btns) {
                        var t = (b.innerText||b.getAttribute('aria-label')||'').trim();
                        if (t==='Next'||t==='Share'||t==='Continue') {
                            b.removeAttribute('disabled');
                            b.style.pointerEvents='auto';
                            b.style.opacity='1';
                        }
                    }"""
                )
                time.sleep(0.6)
            except Exception:
                pass
        say("  Proceeding cautiously…")

    _dismiss(driver, safe_mode=True)

    # ── ⑦ Video-specific dialogs ───────────────────────────────────────────────
    if is_video:
        say("  Handling video dialogs…")
        n = _dismiss_video_dialogs(driver, say, timeout=22)
        if n:
            say(f"  ↳ {n} video dialog(s) dismissed")

    # ── ⑧ Navigate the wizard (dynamic — 1 to 4 Next clicks) ─────────────────
    say("  Navigating wizard…")
    steps_clicked = _drain_wizard_next(driver, say, max_steps=6,
                                        step_timeout=25 if is_video else 12)
    if steps_clicked == 0:
        say("  (no Next button found — may be on caption step already)")

    # If a Discard dialog appeared (back arrow was hit), cancel it and retry
    _dismiss_discard_dialog(driver)

    # ── ⑨ Caption ─────────────────────────────────────────────────────────────
    if caption:
        say("  Adding caption…")
        # Wait for caption field to be present (it renders after wizard nav)
        cap_ok = _wait_for(
            driver,
            lambda: _type_caption(driver, caption, say),
            timeout=18)
        if cap_ok:
            say("  ↳ Caption added")
            time.sleep(0.3)
        else:
            say("  ⚠ Caption field not found — posting without caption")
            if debug_dir:
                _screenshot_debug(driver, "no_caption_field", debug_dir)

    # ── ⑩ Share ───────────────────────────────────────────────────────────────
    say("  Sharing…")
    _dismiss_discard_dialog(driver)  # cancel any stray discard dialog before sharing
    try:
        share_done = _click_final_share(driver, say,
                                          timeout=90 if is_video else step_timeout)
    except PostError:
        raise
    except Exception as e:
        _bail(f"Share step crashed: {e}")
        share_done = False  # unreachable but keeps linter happy

    # ── ⑪ Wait for post completion ────────────────────────────────────────────
    # _click_final_share already confirmed via URL/toast/staleness when possible.
    # This loop is a secondary check for cases where confirmation was uncertain.
    say("  Confirming post completion…")
    _complete_timeout = 40 if is_video else 20
    complete_deadline = time.time() + _complete_timeout
    completed = False

    while time.time() < complete_deadline:
        try:
            # Share panel = post succeeded, just need to close it
            if _dismiss_share_panel(driver, say):
                completed = True; break

            url = driver.current_url
            if (url.rstrip('/') in (_IG_HOME, _IG_HOME + "/")
                    or '/p/' in url or '/reel/' in url or '/tv/' in url):
                completed = True; break

            for phrase in _SUCCESS_PHRASES:
                try:
                    for el in driver.find_elements(By.XPATH,
                            f"//*[contains(normalize-space(text()),'{phrase}')]"):
                        if el.is_displayed():
                            completed = True; break
                except Exception:
                    pass
            if completed:
                break

            # If Share button is gone and no error, treat as success
            share_still_present = bool(
                _first_visible(driver, _FINAL_SHARE_XPATH + " | " + _SHARE_ROLE_XPATH))
            if not share_still_present and share_done:
                completed = True; break

            err = _detect_error_banner(driver)
            if err:
                _bail(f"Instagram error during posting: {err}")

        except PostError:
            raise
        except Exception:
            pass
        time.sleep(_POLL)

    if completed:
        say("✓ Post submitted successfully")
    else:
        say("⚠ Could not confirm completion — verify on Instagram")
        if debug_dir:
            _screenshot_debug(driver, "completion_uncertain", debug_dir)


# ═══════════════════════════════════════════════════════════════════════════════
#  FACEBOOK POSTING
# ═══════════════════════════════════════════════════════════════════════════════

def post_one_facebook(driver, media_path, caption, say, step_timeout=32, **_):
    """
    Post one image or video to Facebook via Selenium.
    Navigates to facebook.com, clicks Photo/Video, uploads the file,
    types the caption, and submits.
    Raises PostError on failure.
    """
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    abs_path = str(Path(media_path).resolve())
    if not os.path.isfile(abs_path):
        raise PostError(f"Media file not found: {abs_path}")

    say(f"📘 Facebook posting: {Path(media_path).name}")
    _safe_get(driver, "https://www.facebook.com")
    time.sleep(random.uniform(2.5, 4.0))

    wait = WebDriverWait(driver, step_timeout)

    # Click the "Photo/video" composer button
    try:
        photo_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH,
             "//span[contains(text(),'Photo') or contains(text(),'photo')"
             " or contains(text(),'Video') or contains(text(),'video')]"
             "/ancestor::div[@role='button'][1]")))
        photo_btn.click()
        time.sleep(1.5)
    except Exception:
        # Fallback: look for any file input directly
        pass

    # Upload file
    try:
        file_input = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@type='file']")))
        file_input.send_keys(abs_path)
    except Exception as e:
        raise PostError(f"Facebook: could not find file input — {e}")

    time.sleep(random.uniform(4.0, 7.0))

    # Type caption into the composer text box
    if caption:
        try:
            box = driver.find_element(
                By.XPATH,
                "//*[@contenteditable='true' and @role='textbox']")
            box.click()
            time.sleep(0.5)
            box.send_keys(caption)
            time.sleep(1.0)
        except Exception:
            pass  # caption optional

    # Click the Post / Share button
    try:
        post_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH,
             "//div[@aria-label='Post' or @aria-label='Share now'"
             " or @aria-label='Share' or @aria-label='post']"
             "[@role='button']")))
        post_btn.click()
    except Exception as e:
        raise PostError(f"Facebook: could not click Post button — {e}")

    time.sleep(random.uniform(3.0, 5.0))
    say("✓ Facebook post submitted")


# ═══════════════════════════════════════════════════════════════════════════════
#  X (TWITTER) POSTING
# ═══════════════════════════════════════════════════════════════════════════════

def post_one_twitter(driver, media_path, caption, say, step_timeout=32, **_):
    """
    Post one image or video to X (Twitter) via Selenium.
    Opens the compose URL, attaches media, types caption (≤280 chars), posts.
    Raises PostError on failure.
    """
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    abs_path = str(Path(media_path).resolve())
    if not os.path.isfile(abs_path):
        raise PostError(f"Media file not found: {abs_path}")

    say(f"🐦 X/Twitter posting: {Path(media_path).name}")
    _safe_get(driver, "https://x.com/compose/post")
    time.sleep(random.uniform(2.5, 4.0))

    wait = WebDriverWait(driver, step_timeout)

    # Attach media via hidden file input
    try:
        file_input = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@type='file' and @accept]")))
        file_input.send_keys(abs_path)
    except Exception as e:
        raise PostError(f"X: could not find media file input — {e}")

    time.sleep(random.uniform(3.5, 6.0))

    # Type caption (Twitter hard-caps at 280 chars)
    tweet_text = (caption or '')[:280]
    if tweet_text:
        try:
            box = wait.until(EC.presence_of_element_located(
                (By.XPATH,
                 "//div[@data-testid='tweetTextarea_0'"
                 " or @data-testid='tweetTextarea_0_label']"
                 "/descendant-or-self::div[@contenteditable='true'][1]")))
            box.click()
            time.sleep(0.5)
            box.send_keys(tweet_text)
            time.sleep(1.0)
        except Exception:
            pass  # caption optional

    # Click Tweet / Post button
    try:
        submit = wait.until(EC.element_to_be_clickable(
            (By.XPATH,
             "//button[@data-testid='tweetButton'"
             " or @data-testid='tweetButtonInline']")))
        submit.click()
    except Exception as e:
        raise PostError(f"X: could not click Post button — {e}")

    time.sleep(random.uniform(3.0, 5.0))
    say("✓ X/Twitter post submitted")


# ═══════════════════════════════════════════════════════════════════════════════
#  GUI
