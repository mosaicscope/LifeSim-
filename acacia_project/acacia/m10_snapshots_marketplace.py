

# ============================================================================
# [4.9] SNAPSHOTS · MARKETPLACE · INTER-CREATURE   [PHASES 62 / 63 / 64 / 65]
# ============================================================================

SNAPSHOT_FORMAT = "acacia_snapshot"
SNAPSHOT_VERSION = 1

# the live files a creature IS - each stays in its own existing schema; a
# bundle is a container, never a second format
SNAPSHOT_PARTS = ("state", "memory", "knowledge", "friends", "settings",
                  "visual_memory", "listings", "exchanges")

# never leave the machine inside a shareable bundle
SECRET_KEYS = ("claude_api_key", "gemini_api_key", "ig_password", "password")


def _snapshot_files(iid=None):
    d = instance_dir(iid)
    return {"state": d / "state.json", "memory": d / "memory.json",
            "knowledge": d / "knowledge.json", "friends": d / "friends.json",
            "settings": d / "settings.json",
            "visual_memory": d / "visual_memory.json",
            "listings": d / "listings.json", "exchanges": d / "exchanges.json"}


def export_snapshot(path, iid=None):
    """[PHASE 62] -> (ok, message). One instance's whole mind as one file.

    Each part is the SAME versioned structure the live file already holds -
    no parallel serialisation, so an export can never drift from what the
    app actually reads. Secrets are stripped, not exported."""
    iid = _safe_instance_id(iid if iid is not None else INSTANCE_ID)
    parts, missing = {}, []
    for name, fp in _snapshot_files(iid).items():
        if not Path(fp).exists():
            missing.append(name)
            continue
        data = load_json(fp, None)
        if data is None:
            missing.append(name)
            continue
        if name == "settings" and isinstance(data, dict):
            data = {k: v for k, v in data.items() if k not in SECRET_KEYS}
        parts[name] = data
    if not parts:
        return False, f"instance '{iid}' has nothing saved yet"
    bundle = {"format": SNAPSHOT_FORMAT, "version": SNAPSHOT_VERSION,
              "instance": iid, "created": time.time(),
              "app": "acacia", "parts": parts, "omitted": missing}
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if not save_json(Path(path), bundle):
        return False, "could not write the snapshot file"
    return True, f"exported {len(parts)} part(s) of '{iid}' to {path}"


def snapshot_summary(bundle):
    """-> [str] what is actually inside a bundle, before importing it."""
    if not isinstance(bundle, dict) or bundle.get("format") != SNAPSHOT_FORMAT:
        return ["(not an acacia snapshot)"]
    parts = bundle.get("parts") or {}
    out = [f"snapshot of '{bundle.get('instance', '?')}' "
           f"(v{bundle.get('version')}, {len(parts)} parts)"]
    mem = (parts.get("memory") or {}).get("long_term")
    if isinstance(mem, list):
        out.append(f"  memories: {len(mem)}")
    works = (parts.get("visual_memory") or {}).get("works")
    if isinstance(works, list):
        out.append(f"  works: {len(works)}")
    hyp = (parts.get("knowledge") or {}).get("hypotheses")
    if isinstance(hyp, list):
        out.append(f"  hypotheses: {len(hyp)}")
    return out


def import_snapshot(path, into_instance, overwrite=False):
    """[PHASE 62/61] -> (ok, message). Restores a bundle into a named
    instance.

    REFUSES to write into an instance that already has state unless
    `overwrite` is explicitly passed: importing must never silently merge
    two creatures' memories, which is the one mistake that cannot be
    undone."""
    bundle = load_json(Path(path), None)
    if not isinstance(bundle, dict) or bundle.get("format") != SNAPSHOT_FORMAT:
        return False, "that file is not an acacia snapshot"
    if int(bundle.get("version", 0) or 0) > SNAPSHOT_VERSION:
        return False, (f"snapshot is version {bundle.get('version')}, this build "
                       f"reads up to {SNAPSHOT_VERSION}")
    iid = _safe_instance_id(into_instance)
    target = instance_dir(iid)
    existing = [p.name for p in _snapshot_files(iid).values() if Path(p).exists()]
    if existing and not overwrite:
        return False, (f"instance '{iid}' already has {len(existing)} file(s) - "
                       f"import refused so nothing is merged; pick a new "
                       f"instance id or pass overwrite")
    parts = bundle.get("parts") or {}
    written = 0
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return False, f"could not create instance directory: {exc}"
    for name, fp in _snapshot_files(iid).items():
        if name not in parts:
            continue
        if save_json(Path(fp), parts[name]):
            written += 1
    if not written:
        return False, "snapshot contained nothing this build recognises"
    return True, (f"imported {written} part(s) into '{iid}' - "
                  f"restart with CREATURE_INSTANCE={iid} to run it")


class Marketplace:
    """[PHASE 63] Listings for generated work, under the STRICTEST consent
    rule in the project.

    A listing is only ever PREPARED here. Nothing is published, priced or
    transacted automatically: every single listing needs its own typed
    confirmation naming that listing, exactly like Phase 16's posting
    consent but tighter - there is deliberately no bulk path, no
    confirm_all, and no autonomous trigger anywhere in the codebase.

    Lifecycle mirrors Phase 36's post lifecycle:
        draft -> confirmed -> listed -> sold | cancelled
    """

    STATUSES = ("draft", "confirmed", "listed", "sold", "cancelled")
    CONFIRM_PHRASE = "list {lid}"

    def __init__(self, path=None):
        self.path = Path(path or LISTINGS_FILE)
        self.listings = []
        self.load()

    def load(self):
        data = load_json(self.path, {})
        if isinstance(data, dict):
            self.listings = [r for r in (data.get("listings") or [])
                             if isinstance(r, dict)][-200:]

    def save(self):
        return save_json(self.path, {"format": "acacia_listings", "version": 1,
                                     "listings": self.listings[-200:],
                                     "saved": time.time()})

    def get(self, lid):
        for r in self.listings:
            if r.get("id") == lid:
                return r
        return None

    def propose(self, work, price=None, currency="USD", market="", note=""):
        """Prepare a draft. Never lists anything by itself."""
        if not isinstance(work, dict) or not work.get("path"):
            return None
        lid = f"l{int(time.time() * 1000) % 10 ** 9}"
        rec = {"id": lid, "status": "draft", "created": time.time(),
               "work_path": work.get("path"), "kind": work.get("kind", "image"),
               "effects": list(work.get("effects") or [])[:8],
               "price": None if price is None else round(float(price), 2),
               "currency": str(currency or "USD")[:8],
               "market": str(market or "")[:40], "note": str(note or "")[:200],
               "provenance": dict(work.get("provenance") or {}),
               "log": [(time.time(), "drafted")], "sales": []}
        self.listings.append(rec)
        self.save()
        return rec

    def confirm(self, lid, typed):
        """-> (ok, message). The ONLY path out of draft, and it requires the
        user to type the phrase naming this exact listing."""
        rec = self.get(lid)
        if rec is None:
            return False, f"no listing {lid}"
        if rec["status"] != "draft":
            return False, f"listing {lid} is already {rec['status']}"
        want = self.CONFIRM_PHRASE.format(lid=lid)
        if (typed or "").strip().lower() != want:
            return False, (f"not confirmed - to list this one, type exactly: "
                           f"{want}")
        if rec.get("price") is None:
            return False, "set a price before confirming"
        rec["status"] = "confirmed"
        rec["log"].append((time.time(), "confirmed by user"))
        self.save()
        return True, f"listing {lid} confirmed - ready to publish"

    def mark_listed(self, lid, url=""):
        rec = self.get(lid)
        if rec is None or rec["status"] != "confirmed":
            return False, "only a confirmed listing can be marked as listed"
        rec["status"] = "listed"
        rec["url"] = str(url or "")[:300]
        rec["listed_at"] = time.time()
        rec["log"].append((time.time(), "listed"))
        self.save()
        return True, f"listing {lid} marked as listed"

    def cancel(self, lid, why=""):
        rec = self.get(lid)
        if rec is None or rec["status"] in ("sold", "cancelled"):
            return False, "nothing to cancel"
        rec["status"] = "cancelled"
        rec["log"].append((time.time(), f"cancelled {why}".strip()))
        self.save()
        return True, f"listing {lid} cancelled"

    def record_sale(self, lid, amount, currency=None, note=""):
        """User-reported outcome. The app never reads a wallet or an API."""
        rec = self.get(lid)
        if rec is None or rec["status"] not in ("listed", "sold"):
            return False, "only a listed item can record a sale"
        rec["sales"].append({"t": time.time(), "amount": round(float(amount), 2),
                             "currency": str(currency or rec["currency"])[:8],
                             "note": str(note or "")[:120]})
        rec["status"] = "sold"
        rec["log"].append((time.time(), "sale recorded by user"))
        self.save()
        return True, f"sale recorded on {lid}"

    def by_status(self, status):
        return [r for r in self.listings if r.get("status") == status]

    def totals(self):
        """[PHASE 64] Pure aggregation over what is already recorded."""
        out = {"listings": len(self.listings), "revenue": {}, "sold": 0}
        for st in self.STATUSES:
            out[st] = len(self.by_status(st))
        for rec in self.listings:
            for sale in rec.get("sales") or []:
                cur = sale.get("currency", "USD")
                out["revenue"][cur] = round(
                    out["revenue"].get(cur, 0.0) + float(sale.get("amount", 0.0)), 2)
                out["sold"] += 1
        return out


def build_market_report(app):
    """[PHASE 64] READ-ONLY. Reports what Phase 63 recorded and nothing
    else: no pricing advice, no automated decision, no action taken."""
    mk = getattr(app, "marketplace", None)
    if mk is None:
        return ["(no marketplace in this session)"]
    t = mk.totals()
    lines = [f"listings: {t['listings']} "
             f"(draft {t['draft']}, confirmed {t['confirmed']}, "
             f"listed {t['listed']}, sold {t['sold']}, "
             f"cancelled {t['cancelled']})"]
    if t["revenue"]:
        lines.append("reported revenue: " + ", ".join(
            f"{amt:.2f} {cur}" for cur, amt in sorted(t["revenue"].items())))
    else:
        lines.append("reported revenue: none recorded")
    for rec in mk.listings[-5:]:
        price = "no price" if rec.get("price") is None else \
            f"{rec['price']:.2f} {rec['currency']}"
        lines.append(f"  {rec['id']}  {rec['status']:<9} {price}  "
                     f"{Path(str(rec.get('work_path') or '?')).name}")
    lines.append("(reporting only - nothing here acts on these numbers)")
    return lines


class InterCreature:
    """[PHASE 65] Exchange of creative opinion between two INSTANCES.

    Opt-in and local by construction: it reads and writes files the user
    hands over, and there is no discovery, no listening socket and no
    network call anywhere in this class. It stays off until the setting is
    explicitly turned on.

    An incoming opinion is EVIDENCE, never authority - exactly Phase 33's
    rule for Friend collaboration. It can only be weighed once this
    creature has formed its own measured verdict, and its influence is hard
    capped at MAX_INFLUENCE, so another instance can nudge taste and never
    set it."""

    FORMAT = "acacia_opinion"
    VERSION = 1
    MAX_INFLUENCE = 0.15        # same bounded-nudge philosophy as everywhere

    def __init__(self, path=None, enabled=False):
        self.path = Path(path or EXCHANGES_FILE)
        self.enabled = bool(enabled)
        self.exchanges = []
        self.load()

    def load(self):
        data = load_json(self.path, {})
        if isinstance(data, dict):
            self.exchanges = [r for r in (data.get("exchanges") or [])
                              if isinstance(r, dict)][-100:]

    def save(self):
        return save_json(self.path, {"format": "acacia_exchanges", "version": 1,
                                     "exchanges": self.exchanges[-100:],
                                     "saved": time.time()})

    def export_opinion(self, work, verdict, note="", instance=None):
        """What THIS creature thinks of a piece, as a portable record."""
        return {"format": self.FORMAT, "version": self.VERSION,
                "instance": _safe_instance_id(instance or INSTANCE_ID),
                "t": time.time(),
                "work_path": (work or {}).get("path"),
                "effects": list((work or {}).get("effects") or [])[:8],
                "verdict": round(clamp01(float(verdict)), 3),
                "note": str(note or "")[:200]}

    def receive(self, opinion):
        """-> (ok, message). Validates and RECORDS only; weighing is a
        separate, verdict-gated step."""
        if not self.enabled:
            return False, "inter-creature exchange is off (opt-in only)"
        if isinstance(opinion, (str, Path)):
            opinion = load_json(Path(opinion), None)
        if not isinstance(opinion, dict) or opinion.get("format") != self.FORMAT:
            return False, "not an acacia opinion record"
        if int(opinion.get("version", 0) or 0) > self.VERSION:
            return False, "opinion record is from a newer build"
        sender = _safe_instance_id(opinion.get("instance"))
        if sender == INSTANCE_ID:
            return False, "that opinion came from this same instance"
        rec = {"t": time.time(), "from": sender,
               "work_path": opinion.get("work_path"),
               "effects": list(opinion.get("effects") or [])[:8],
               "verdict": clamp01(float(opinion.get("verdict", 0.5) or 0.5)),
               "note": str(opinion.get("note", ""))[:200],
               "weighed": False}
        self.exchanges.append(rec)
        self.save()
        return True, f"recorded an opinion from '{sender}'"

    def weigh(self, rec, own_verdict):
        """-> (adjustment, why). The bounded influence an outside opinion
        may have on a LOCAL measured verdict.

        own_verdict is required: with nothing of its own to compare
        against, the creature does not adopt someone else's judgement."""
        if own_verdict is None:
            return 0.0, "no local verdict yet - outside opinion not adopted"
        gap = clamp01(float(rec.get("verdict", 0.5))) - clamp01(float(own_verdict))
        # agreement from an instance that has agreed before counts slightly
        # more, but never past the cap
        history = [r for r in self.exchanges
                   if r.get("from") == rec.get("from") and r.get("weighed")]
        trust = clamp01(0.4 + 0.1 * len(history))
        adj = clamp(gap * trust, -self.MAX_INFLUENCE, self.MAX_INFLUENCE)
        rec["weighed"] = True
        rec["influence"] = round(adj, 4)
        self.save()
        return adj, (f"'{rec.get('from')}' rated it {rec.get('verdict'):.2f} "
                     f"against my {float(own_verdict):.2f} - moved {adj:+.3f}")

    def report(self):
        if not self.enabled:
            return ["inter-creature exchange: off"]
        lines = [f"inter-creature exchange: on, {len(self.exchanges)} record(s)"]
        for r in self.exchanges[-5:]:
            lines.append(f"  from {r['from']}: {r['verdict']:.2f} on "
                         f"{Path(str(r.get('work_path') or '?')).name}"
                         + (f" (moved {r['influence']:+.3f})" if r.get("weighed")
                            else " (not weighed)"))
        return lines
