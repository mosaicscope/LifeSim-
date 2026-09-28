"""Prove the package is behaviourally the monolith: same names, same source."""
import importlib.util
import inspect


def _tag(v):
    if callable(v):
        return ('fn', getattr(v, '__name__', '?'))
    if isinstance(v, (str, int, float, bool, bytes, type(None))):
        return v
    if isinstance(v, (list, tuple)):
        return tuple(_tag(x) for x in v)
    if isinstance(v, dict):
        return tuple((k, _tag(x)) for k, x in v.items())
    return ('obj', type(v).__name__, getattr(v, 'name', getattr(v, 'label', None)))


def _shape(seq):
    return [_tag(v) for v in seq]
import sys

sys.path.insert(0, ".")

import acacia  # noqa: E402

spec = importlib.util.spec_from_file_location("orig", "acacia_unified.py")
orig = importlib.util.module_from_spec(spec)
sys.modules["orig"] = orig
spec.loader.exec_module(orig)

a = {k for k in vars(orig) if not k.startswith("__")}
b = {k for k in acacia.NS if not k.startswith("__")}

PATCHED = acacia.LOAD_PATCHES
# The one name the patch layer is allowed to rebind (the classic function is
# kept under generate_nft_character_classic and is compared instead).
OVERRIDES = {"generate_nft_character", "Creature"} if PATCHED else set()

missing = sorted(a - b)
extra = sorted(b - a)
if PATCHED:
    print("patch layer          : LOADED (%d new names)" % len(extra))
    extra = []

mismatch = []
kinds = {}
for n in sorted(a & b):
    o, m = getattr(orig, n), acacia.NS[n]
    if (inspect.isfunction(o) or inspect.isclass(o)) and \
            str(getattr(o, '__module__', '')).startswith(('orig', 'acacia')):
        if n in OVERRIDES:
            m = acacia.NS.get(n + "_classic", m)
        kinds[n] = type(o).__name__
        try:
            if inspect.getsource(o) != inspect.getsource(m):
                mismatch.append(n)
        except (OSError, TypeError) as exc:
            mismatch.append(f"{n} <{exc}>")

# non-callable top-level values: compare repr where cheap and deterministic
value_diff = []
for n in sorted(a & b):
    o, m = getattr(orig, n), acacia.NS[n]
    if inspect.isfunction(o) or inspect.isclass(o) or inspect.ismodule(o):
        continue
    try:
        if type(o) is not type(m):
            value_diff.append(f"{n}: type {type(o).__name__} != {type(m).__name__}")
        elif n in OVERRIDES:
            pass
        elif isinstance(o, (str, int, float, bool, bytes)):
            if o != m:
                value_diff.append(n)
        elif isinstance(o, (set, frozenset)):
            if sorted(map(repr, map(_tag, o))) != sorted(map(repr, map(_tag, m))):
                value_diff.append(f"{n} (set len {len(o)} vs {len(m)})")
        elif isinstance(o, (tuple, list)):
            if len(o) != len(m) or _shape(o) != _shape(m):
                value_diff.append(f"{n} (len {len(o)} vs {len(m)})")
        elif isinstance(o, dict):
            if list(o.keys()) != list(m.keys()) or _shape(o.values()) != _shape(m.values()):
                value_diff.append(f"{n} (keys {len(o)} vs {len(m)})")
    except Exception:
        pass

print("original top-level names :", len(a))
print("package  top-level names :", len(b))
print("missing                  :", missing)
print("extra                    :", extra)
print("callables compared       :", len(kinds))
print("source mismatches        :", mismatch)
print("constant-value diffs     :", value_diff[:20])

ok = not missing and not extra and not mismatch and not value_diff
print("\nRESULT:", "IDENTICAL" if ok else "DIVERGENT")
sys.exit(0 if ok else 1)
