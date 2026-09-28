# ═══════════════════════════════════════════════════════════════════════════════
#  ACACIA AI CONNECTOR  — optional bridge to an Acacia v48+ instance
# ═══════════════════════════════════════════════════════════════════════════════

_acacia_mod   = None   # the loaded acacia module, or None
_acacia_error = ''     # last load error

def acacia_load(path: str) -> bool:
    """
    Dynamically import an acacia .py file so TrippyGram can use its
    cloud_call / ollama functions for AI-powered NFT trait generation.
    Returns True on success.
    """
    global _acacia_mod, _acacia_error
    try:
        import importlib.util, sys as _sys
        spec = importlib.util.spec_from_file_location('acacia_bridge', path)
        mod  = importlib.util.module_from_spec(spec)
        # Suppress Acacia's GUI startup — it checks __name__
        mod.__name__ = 'acacia_bridge'
        # Exec only the module-level code (no mainloop called)
        spec.loader.exec_module(mod)
        _acacia_mod   = mod
        _acacia_error = ''
        return True
    except Exception as e:
        _acacia_error = str(e)
        _acacia_mod   = None
        return False

def acacia_is_loaded() -> bool:
    return _acacia_mod is not None


# ── TrippyGram ↔ ACACIA live bridge ─────────────────────────────────────────
# Uses ~/.acacia/trippygram_bridge.json (written by both apps).
# TrippyGram reads ACACIA's running status + current model/provider from there,
# and keeps its own heartbeat ticking so ACACIA knows we're alive too.

_bridge_mod = None   # acacia_trippygram_bridge, if importable

def _bridge_init():
    """Try to import the bridge module once."""
    global _bridge_mod
    if _bridge_mod is not None:
        return _bridge_mod
    try:
        import importlib, pathlib as _pl, sys as _sys
        # Look next to this script first, then ~/.acacia/
        candidates = [
            _pl.Path(__file__).parent / 'acacia_trippygram_bridge.py',
            _pl.Path.home() / '.acacia' / 'acacia_trippygram_bridge.py',
        ]
        for cand in candidates:
            if cand.exists():
                spec = importlib.util.spec_from_file_location(
                    'acacia_trippygram_bridge', cand)
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                _bridge_mod = m
                _bridge_mod.trippygram_heartbeat()          # announce ourselves
                _bridge_mod.start_heartbeat_loop("trippygram")
                return _bridge_mod
    except Exception:
        pass
    return None

def bridge_acacia_is_running() -> bool:
    """True if ACACIA has written a fresh heartbeat in the last 30 s."""
    b = _bridge_init()
    return b.acacia_is_running() if b else False

def bridge_get_acacia_status() -> dict:
    """Return ACACIA's status dict: {model, provider, running, …} or {}."""
    b = _bridge_init()
    return b.get_acacia_status() if b else {}

def bridge_shutdown():
    """Call on TrippyGram exit to mark ourselves as gone."""
    if _bridge_mod:
        try: _bridge_mod.trippygram_shutdown()
        except Exception: pass

# ── Prompts used for AI trait generation ──────────────────────────────────────
_NFT_TRAIT_SYSTEM = (
    "You are a creative NFT character designer. "
    "Respond ONLY with a valid JSON object — no markdown, no explanation. "
    "All values must be plain strings."
)

# _NFT_TRAIT_KEYS — now aliased to the HD upgrade's expanded NFT_TRAIT_CONFIG
_NFT_TRAIT_KEYS = NFT_TRAIT_CONFIG

# ═══════════════════════════════════════════════════════════════════════════════
#  ACACIA IMAGE ROUTING  — TrippyGram → ACACIA → generate image
# ═══════════════════════════════════════════════════════════════════════════════

def acacia_generate_image(prompt: str, width: int = 1024, height: int = 1024,
                          quality: str = 'hd', style: str = 'vivid',
                          log_cb=None):
    """
    Route an image request through ACACIA, then generate.

    Step 1 — ENHANCE: use whichever AI ACACIA has a key for
             (Anthropic → OpenAI → Groq → Ollama → skip, use raw prompt)

    Step 2 — GENERATE: try each image backend in order until one works
             DALL-E 3 (needs OpenAI key) → Pollinations free (no key needed)

    Enhancement and generation are INDEPENDENT — no OpenAI key just means
    we skip DALL-E 3 for generation; we can still enhance via Claude/Groq
    and generate via Pollinations.

    Returns (PIL.Image, enhanced_prompt, provider_tag) or None if ACACIA
    is not reachable at all.
    """
    import json as _j, urllib.request as _ur, urllib.parse as _up
    import base64 as _b64, io as _io, urllib.error

    def _log(msg):
        if log_cb: log_cb(msg)

    def _xor(s):
        KEY = b'acacia-v18-key'
        try:
            raw = _b64.b64decode(s)
            return ''.join(chr(b ^ KEY[i % len(KEY)]) for i, b in enumerate(raw))
        except Exception:
            return s   # already plaintext

    def _get_key(keys, name):
        """Decode and return a key, or '' if missing/blank."""
        v = keys.get(name, '').strip()
        return _xor(v) if v else ''

    def _cloud_keys():
        import pathlib as _pl
        try:
            return _j.loads((_pl.Path.home() / '.acacia' / 'cloud_keys.json')
                            .read_text(encoding='utf-8'))
        except Exception:
            return {}

    _ENHANCE_SYS = (
        "You are an expert prompt engineer for AI image generation. "
        "Rewrite the user's description into one vivid, detailed image generation prompt. "
        "Add lighting, mood, artistic style, camera angle, colour palette, textures. "
        "Under 300 words. Return ONLY the enhanced prompt — no preamble, no quotes."
    )

    # ── Enhancement helpers (each raises on failure) ──────────────────────────
    def _enhance_anthropic(key, model):
        body = {'model': model or 'claude-haiku-4-5-20251001', 'max_tokens': 400,
                'system': _ENHANCE_SYS, 'messages': [{'role': 'user', 'content': prompt}]}
        req = _ur.Request('https://api.anthropic.com/v1/messages',
                          data=_j.dumps(body).encode(),
                          headers={'x-api-key': key, 'anthropic-version': '2023-06-01',
                                   'content-type': 'application/json'}, method='POST')
        with _ur.urlopen(req, timeout=30) as r:
            return _j.loads(r.read())['content'][0]['text'].strip()

    def _enhance_openai(key, model):
        body = {'model': model or 'gpt-4o-mini', 'max_tokens': 400,
                'messages': [{'role': 'system', 'content': _ENHANCE_SYS},
                             {'role': 'user',   'content': prompt}]}
        req = _ur.Request('https://api.openai.com/v1/chat/completions',
                          data=_j.dumps(body).encode(),
                          headers={'Authorization': f'Bearer {key}',
                                   'Content-Type': 'application/json'}, method='POST')
        with _ur.urlopen(req, timeout=30) as r:
            return _j.loads(r.read())['choices'][0]['message']['content'].strip()

    def _enhance_groq(key, model):
        body = {'model': model or 'llama3-8b-8192', 'max_tokens': 400,
                'messages': [{'role': 'system', 'content': _ENHANCE_SYS},
                             {'role': 'user',   'content': prompt}]}
        req = _ur.Request('https://api.groq.com/openai/v1/chat/completions',
                          data=_j.dumps(body).encode(),
                          headers={'Authorization': f'Bearer {key}',
                                   'Content-Type': 'application/json'}, method='POST')
        with _ur.urlopen(req, timeout=30) as r:
            return _j.loads(r.read())['choices'][0]['message']['content'].strip()

    def _enhance_ollama(base, model):
        body = {'model': model, 'stream': False,
                'prompt': f'{_ENHANCE_SYS}\n\n{prompt}',
                'options': {'temperature': 0.8, 'num_predict': 400}}
        req = _ur.Request(f'{base}/api/generate',
                          data=_j.dumps(body).encode(),
                          headers={'Content-Type': 'application/json'}, method='POST')
        with _ur.urlopen(req, timeout=60) as r:
            data = _j.loads(r.read())
        return (data.get('response') or
                (data.get('message') or {}).get('content', '')).strip()

    # ── Image generation helpers (each raises on failure) ─────────────────────
    def _dalle3(oai_key, final_prompt):
        # DALL-E 3 only supports 1024x1024, 1792x1024, 1024x1792
        allowed = {(1024,1024),(1792,1024),(1024,1792)}
        w, h = width, height
        if (w, h) not in allowed:
            w, h = 1024, 1024
        body = {'model': 'dall-e-3', 'prompt': final_prompt, 'n': 1,
                'size': f'{w}x{h}', 'quality': quality, 'style': style,
                'response_format': 'b64_json'}
        req = _ur.Request('https://api.openai.com/v1/images/generations',
                          data=_j.dumps(body).encode(),
                          headers={'Authorization': f'Bearer {oai_key}',
                                   'Content-Type': 'application/json'}, method='POST')
        try:
            with _ur.urlopen(req, timeout=120) as r:
                data = _j.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'DALL-E 3 {e.code}: {e.read().decode()[:200]}')
        raw = _b64.b64decode(data['data'][0]['b64_json'])
        return Image.open(_io.BytesIO(raw)).convert('RGB')

    def _pollinations(final_prompt):
        safe = _up.quote(final_prompt[:500])
        seed = _ri(1, 999999)
        url  = (f'https://image.pollinations.ai/prompt/{safe}'
                f'?width={width}&height={height}&seed={seed}'
                f'&model=flux&enhance=true&nologo=true')
        req = _ur.Request(url, headers={'User-Agent': 'TrippyGram/7'})
        with _ur.urlopen(req, timeout=120) as r:
            return Image.open(_io.BytesIO(r.read())).convert('RGB')

    # ═════════════════════════════════════════════════════════════════════════
    #  MAIN LOGIC
    # ═════════════════════════════════════════════════════════════════════════

    acacia_live   = bridge_acacia_is_running()
    acacia_module = acacia_is_loaded()

    if not acacia_live and not acacia_module:
        _log('[Acacia→image] ACACIA not running and no module loaded — skipping')
        return None

    keys = _cloud_keys()

    # ── STEP 1: Enhance prompt — try every available AI until one works ───────
    enhanced     = prompt
    enhance_used = 'none'

    if acacia_live:
        status   = bridge_get_acacia_status()
        provider = status.get('provider', 'local')
        model    = status.get('model', '')
        _log(f'[Acacia→image] bridge active — provider={provider}  model={model}')

        # Try active provider first, then fall through to others
        enhance_order = []
        if provider == 'anthropic':
            enhance_order = ['anthropic', 'groq', 'openai']
        elif provider == 'openai':
            enhance_order = ['openai', 'anthropic', 'groq']
        elif provider == 'groq':
            enhance_order = ['groq', 'anthropic', 'openai']
        else:
            enhance_order = ['anthropic', 'openai', 'groq']

        for ep in enhance_order:
            k = _get_key(keys, ep)
            if not k:
                _log(f'[Acacia→image] no {ep} key — skipping {ep} enhancement')
                continue
            try:
                _log(f'[Acacia→image] enhancing prompt via {ep}…')
                if ep == 'anthropic':
                    enhanced = _enhance_anthropic(k, model if provider == 'anthropic' else '')
                elif ep == 'openai':
                    enhanced = _enhance_openai(k, model if provider == 'openai' else '')
                elif ep == 'groq':
                    enhanced = _enhance_groq(k, model if provider == 'groq' else '')
                enhance_used = ep
                _log(f'[Acacia→image] ✓ enhanced via {ep}: {enhanced[:100]}…')
                break
            except Exception as e:
                _log(f'[Acacia→image] {ep} enhance failed: {e}')

        # Ollama fallback for enhancement if all cloud keys missing/failed
        if enhance_used == 'none' and provider == 'local' and model:
            try:
                import pathlib as _pl
                ocfg_path = _pl.Path.home() / '.acacia' / 'ollama_config.json'
                ollama_base = 'http://127.0.0.1:11434'
                try:
                    ocfg = _j.loads(ocfg_path.read_text(encoding='utf-8'))
                    h = ocfg.get('host', '').strip().rstrip('/')
                    p = ocfg.get('port', 11434)
                    if h: ollama_base = f'{h}:{p}'
                except Exception:
                    pass
                _log(f'[Acacia→image] enhancing via Ollama ({model})…')
                enhanced = _enhance_ollama(ollama_base, model)
                enhance_used = f'ollama/{model}'
                _log(f'[Acacia→image] ✓ enhanced via ollama: {enhanced[:100]}…')
            except Exception as e:
                _log(f'[Acacia→image] ollama enhance failed: {e}')

    elif acacia_module:
        try:
            reply = _acacia_mod.cloud_call(prompt, system=_ENHANCE_SYS, max_tokens=400)
            if reply and not reply.startswith('['):
                enhanced = reply.strip()
                enhance_used = 'acacia_module'
                _log(f'[Acacia(mod)→image] ✓ enhanced: {enhanced[:100]}…')
        except Exception as e:
            _log(f'[Acacia(mod)→image] enhance failed: {e}')

    if enhance_used == 'none':
        _log('[Acacia→image] no enhancement possible — using raw prompt as-is')

    # ── STEP 2: Generate image — try each backend until one works ─────────────
    # Tag for reporting which path was used
    provider_tag = f'acacia({enhance_used})'

    # 2a. DALL-E 3 — only if OpenAI key exists
    oai_key = _get_key(keys, 'openai')
    if oai_key:
        try:
            _log('[Acacia→image] generating via DALL-E 3…')
            img = _dalle3(oai_key, enhanced)
            _log('[Acacia→image] ✓ DALL-E 3 done')
            return img, enhanced, f'{provider_tag}+dalle3'
        except Exception as e:
            _log(f'[Acacia→image] DALL-E 3 failed: {e} — falling back to Pollinations')
    else:
        _log('[Acacia→image] no OpenAI key — skipping DALL-E 3, using Pollinations free')

    # 2b. Pollinations.ai — always free, no key needed
    try:
        _log('[Acacia→image] generating via Pollinations.ai (free)…')
        img = _pollinations(enhanced)
        _log('[Acacia→image] ✓ Pollinations done')
        return img, enhanced, f'{provider_tag}+pollinations'
    except Exception as e:
        _log(f'[Acacia→image] Pollinations failed: {e}')

    _log('[Acacia→image] all image backends failed')
    return None


def _build_trait_prompt(style_hint: str = '') -> str:
    lines = [
        "Design a unique NFT PFP character. "
        f"{'Style direction: ' + style_hint + '. ' if style_hint else ''}"
        "Pick ONE value for each trait from the allowed options listed below. "
        "Be creative — pick unusual, interesting combinations. "
        "Return a JSON object with exactly these keys:\n"
    ]
    for key, opts in _NFT_TRAIT_KEYS.items():
        lines.append(f'  "{key}": one of {opts}')
    lines.append('\nAlso add a "Lore" key with 1 evocative sentence (max 20 words) '
                 'describing this character\'s backstory.')
    lines.append('Also add a "Skin" key: pick a hex colour like "#a87040" '
                 'that fits the species and vibe.')
    lines.append('Also add an "Eye Color" key: pick a vivid hex colour like "#00ffcc".')
    return '\n'.join(lines)

def _parse_ai_traits(text: str) -> dict:
    """Pull a JSON object out of an AI response and validate the keys."""
    import json as _json, re as _re
    # strip markdown fences if present
    text = _re.sub(r'```(?:json)?', '', text).strip().strip('`')
    # grab first {...}
    m = _re.search(r'\{.*\}', text, _re.S)
    if not m:
        raise ValueError(f"No JSON found in: {text[:200]}")
    data = _json.loads(m.group())
    # Fill any missing trait keys with a random valid option
    for key, opts in _NFT_TRAIT_KEYS.items():
        if key not in data or data[key] not in opts:
            data[key] = random.choice(opts)
    # Skin / Eye Color — validate hex format, else use defaults
    for col_key, default_pool in [('Skin', _NFT_SKIN_COLORS), ('Eye Color', _NFT_EYE_COLORS)]:
        val = data.get(col_key, '')
        if not (isinstance(val, str) and len(val) == 7 and val.startswith('#')):
            data[col_key] = random.choice(default_pool)
    # Lore
    if 'Lore' not in data or not isinstance(data['Lore'], str):
        data['Lore'] = _SPECIES_LORE.get(data['Species'], 'Unknown origin.')
    return data

def ai_generate_nft_traits(style_hint: str = '', log_cb=None) -> dict:
    """
    Use Acacia's AI backend to generate a trait dict for one NFT character.

    Priority:
      1. Acacia loaded as module (file path set) → use its cloud_call / Ollama
      2. Acacia running externally (bridge heartbeat alive) → connect to
         whichever model/provider Acacia is currently using via the bridge file
      3. Neither → return None (caller falls back to random traits)
    """
    def _log(msg):
        if log_cb: log_cb(msg)

    prompt = _build_trait_prompt(style_hint)

    # ── Path 1: Acacia loaded as a module ────────────────────────────────────
    if acacia_is_loaded():
        mod = _acacia_mod
        # Cloud provider first
        try:
            reply = mod.cloud_call(prompt, system=_NFT_TRAIT_SYSTEM, max_tokens=600)
            if reply and not reply.startswith('['):
                traits = _parse_ai_traits(reply)
                _log(f'[Acacia→cloud] traits: {traits["Species"]} / {traits["Background"]}')
                return traits
            elif reply:
                _log(f'[Acacia→cloud] error reply: {reply[:80]}')
        except Exception as e:
            _log(f'[Acacia→cloud] {e}')

        # Local Ollama fallback
        try:
            url  = f'{mod.OLLAMA_BASE}/api/generate'
            body = {
                'model':  mod.DEFAULT_MODEL,
                'prompt': f'{_NFT_TRAIT_SYSTEM}\n\n{prompt}',
                'stream': False,
                'options': {'temperature': 0.95, 'num_predict': 600},
            }
            import json as _json, urllib.request as _ur
            req = _ur.Request(url,
                              data=_json.dumps(body).encode(),
                              headers={'Content-Type': 'application/json'},
                              method='POST')
            with _ur.urlopen(req, timeout=60) as resp:
                data = _json.loads(resp.read())
            reply = data.get('response') or (data.get('message') or {}).get('content', '')
            if reply:
                traits = _parse_ai_traits(reply)
                _log(f'[Acacia→ollama] traits: {traits["Species"]} / {traits["Background"]}')
                return traits
        except Exception as e:
            _log(f'[Acacia→ollama] {e}')

        _log('[Acacia] all backends failed — using random traits')
        return None

    # ── Path 2: Acacia running as a separate process (live bridge) ────────────
    if bridge_acacia_is_running():
        status   = bridge_get_acacia_status()
        provider = status.get('provider', 'local')
        model    = status.get('model', '')
        _log(f'[Bridge] Acacia is live — provider={provider}  model={model}')

        if provider in ('anthropic', 'openai', 'groq'):
            # Read the cloud keys from ~/.acacia/cloud_keys.json directly
            try:
                import json as _json, pathlib as _pl
                keys_path = _pl.Path.home() / '.acacia' / 'cloud_keys.json'
                raw = _json.loads(keys_path.read_text(encoding='utf-8'))

                def _xor_decode(s: str) -> str:
                    import base64
                    KEY = b'acacia-v18-key'
                    try:
                        data = base64.b64decode(s)
                        return ''.join(
                            chr(b ^ KEY[i % len(KEY)]) for i, b in enumerate(data)
                        )
                    except Exception:
                        return s   # plain-text fallback

                def _get_key(name: str) -> str:
                    v = raw.get(name, '')
                    return _xor_decode(v) if v else ''

                if provider == 'anthropic':
                    import urllib.request as _ur
                    key = _get_key('anthropic')
                    if not key:
                        raise ValueError('No Anthropic key in cloud_keys.json')
                    headers = {
                        'x-api-key': key,
                        'anthropic-version': '2023-06-01',
                        'content-type': 'application/json',
                    }
                    body = {
                        'model': model or 'claude-haiku-4-5-20251001',
                        'max_tokens': 600,
                        'system': _NFT_TRAIT_SYSTEM,
                        'messages': [{'role': 'user', 'content': prompt}],
                    }
                    req = _ur.Request(
                        'https://api.anthropic.com/v1/messages',
                        data=_json.dumps(body).encode(),
                        headers=headers,
                        method='POST',
                    )
                    with _ur.urlopen(req, timeout=60) as resp:
                        reply_body = _json.loads(resp.read())
                    reply = reply_body['content'][0]['text']

                elif provider == 'openai':
                    import urllib.request as _ur
                    key = _get_key('openai')
                    if not key:
                        raise ValueError('No OpenAI key in cloud_keys.json')
                    body = {
                        'model': model or 'gpt-4o-mini',
                        'max_tokens': 600,
                        'messages': [
                            {'role': 'system', 'content': _NFT_TRAIT_SYSTEM},
                            {'role': 'user', 'content': prompt},
                        ],
                    }
                    req = _ur.Request(
                        'https://api.openai.com/v1/chat/completions',
                        data=_json.dumps(body).encode(),
                        headers={'Authorization': f'Bearer {key}',
                                 'Content-Type': 'application/json'},
                        method='POST',
                    )
                    with _ur.urlopen(req, timeout=60) as resp:
                        reply = _json.loads(resp.read())['choices'][0]['message']['content']

                elif provider == 'groq':
                    import urllib.request as _ur
                    key = _get_key('groq')
                    if not key:
                        raise ValueError('No Groq key in cloud_keys.json')
                    body = {
                        'model': model or 'llama3-8b-8192',
                        'max_tokens': 600,
                        'messages': [
                            {'role': 'system', 'content': _NFT_TRAIT_SYSTEM},
                            {'role': 'user', 'content': prompt},
                        ],
                    }
                    req = _ur.Request(
                        'https://api.groq.com/openai/v1/chat/completions',
                        data=_json.dumps(body).encode(),
                        headers={'Authorization': f'Bearer {key}',
                                 'Content-Type': 'application/json'},
                        method='POST',
                    )
                    with _ur.urlopen(req, timeout=60) as resp:
                        reply = _json.loads(resp.read())['choices'][0]['message']['content']

                traits = _parse_ai_traits(reply)
                _log(f'[Bridge→{provider}] traits: {traits["Species"]} / {traits["Background"]}')
                return traits

            except Exception as e:
                _log(f'[Bridge→{provider}] {e}')

        # Acacia is on local Ollama — hit its endpoint directly
        if model:
            try:
                import json as _json, urllib.request as _ur, pathlib as _pl
                # Read Ollama config to find host/port
                ocfg_path = _pl.Path.home() / '.acacia' / 'ollama_config.json'
                ollama_base = 'http://127.0.0.1:11434'
                try:
                    ocfg = _json.loads(ocfg_path.read_text(encoding='utf-8'))
                    host = ocfg.get('host', '').strip().rstrip('/')
                    port = ocfg.get('port', 11434)
                    if host:
                        ollama_base = f'{host}:{port}'
                except Exception:
                    pass
                url  = f'{ollama_base}/api/generate'
                body = {
                    'model':  model,
                    'prompt': f'{_NFT_TRAIT_SYSTEM}\n\n{prompt}',
                    'stream': False,
                    'options': {'temperature': 0.95, 'num_predict': 600},
                }
                req = _ur.Request(url,
                                  data=_json.dumps(body).encode(),
                                  headers={'Content-Type': 'application/json'},
                                  method='POST')
                with _ur.urlopen(req, timeout=60) as resp:
                    data = _json.loads(resp.read())
                reply = data.get('response') or (data.get('message') or {}).get('content', '')
                if reply:
                    traits = _parse_ai_traits(reply)
                    _log(f'[Bridge→ollama/{model}] traits: {traits["Species"]} / {traits["Background"]}')
                    return traits
            except Exception as e:
                _log(f'[Bridge→ollama] {e}')

    _log('[Acacia] not available — using random traits')
    return None


# ═══════════════════════════════════════════════════════════════════════════════

BG='#080810'; PANEL='#10101e'; ACCENT='#cc33ff'; ACCENT2='#ff3399'; DIM='#2a1a3a'
FG='#e0d0ff'; FG_DIM='#776699'; GREEN='#00ffaa'; RED='#ff3344'
YELLOW='#ffee00'; CYAN='#00ccff'; ORANGE='#ff8800'
FONT_H=('Helvetica',13,'bold'); FONT_BODY=('Helvetica',10); TG_FONT_MONO=('Courier',9)

_CONN = {
    'disconnected': dict(dot=RED,    label='⬤  Disconnected',           fg=RED,    bar='🔴  Not connected'),
    'browser_open': dict(dot=ORANGE, label='⬤  Browser open…',          fg=ORANGE, bar='🟡  Browser open — log in'),
    'connected':    dict(dot=GREEN,  label='⬤  Connected to Instagram',  fg=GREEN,  bar='🟢  Connected'),
}



# ═══════════════════════════════════════════════════════════════════════════════
#  MULTI-SESSION MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
