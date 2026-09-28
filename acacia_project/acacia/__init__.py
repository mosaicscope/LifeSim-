"""ACACIA - package form of the original single-file ``acacia_unified.py``.

The original was ONE script, so every section shared ONE globals dict. Code
near the top called names defined near the bottom, functions mutated
module-level state with ``global``, and roughly a hundred call sites look
names up dynamically with ``globals().get(...)``. All of that is only correct
if there is exactly one namespace.

So that is what this package gives it. ``m00_preamble.py`` ... ``m33_app.py``
are verbatim slices of the original file, in original order, and they are
executed - in that order - into a single shared dict, :data:`NS`. Each slice
is also published in ``sys.modules`` as ``acacia.mNN_name`` so ordinary
imports keep working::

    from acacia.m33_app import main
    from acacia.m18_renderer import Creature

Those module objects are views onto :data:`NS`, not copies of it, so a
``global`` rebind in one file is seen by every other file - exactly as in the
single original file, and unlike a plain ordered-import split.

``m34_poly_physics.py`` is the only file that is NOT original source; it is an
injected upgrade layer (see STATE.md) and is loaded last so its definitions
override the earlier ones, mirroring the "HD UPGRADE PATCH - injected"
pattern the original file already used internally.

See STATE.md at the project root for the module map.
"""

import os as _os
import sys as _sys
import types as _types

from ._manifest import MODULES as _MODULES, PATCHES as _PATCHES

__all__ = ["NS", "MODULES", "PATCHES", "module_of", "reload_namespace"]

MODULES = _MODULES
PATCHES = _PATCHES

#: Set ACACIA_NO_PATCHES=1 to load ONLY the original slices - used by
#: tools/verify.py to prove the split itself changed nothing.
LOAD_PATCHES = _os.environ.get("ACACIA_NO_PATCHES", "0") not in ("1", "true", "True")

_PKG_DIR = _os.path.dirname(_os.path.abspath(__file__))
_ROOT_DIR = _os.path.dirname(_PKG_DIR)

#: The one shared namespace. Every slice executes into this dict.
NS = {
    "__name__": __name__,
    # The original file lived at the project root and section [11.5f] does
    # ``Path(__file__).parent`` to find a sibling bridge script, so __file__
    # points at the launcher, not at this package directory.
    "__file__": _os.path.join(_ROOT_DIR, "acacia.py"),
    "__package__": __name__,
    "__doc__": None,
    "__builtins__": __builtins__,
}


class _NamespaceView(_types.ModuleType):
    """A module object whose attributes resolve against the shared :data:`NS`.

    Attribute *reads* fall through to the shared dict; attribute *writes* go
    into it. That is what makes ``acacia.m01_config.STATE_FILE`` and
    ``acacia.m04_memory.STATE_FILE`` the same live binding, which matters
    because ``set_instance()`` rebinds those paths at runtime.
    """

    __slots__ = ()

    def __getattr__(self, key):
        try:
            return NS[key]
        except KeyError:
            raise AttributeError(
                f"module {self.__dict__.get('__name__', '?')!r} has no attribute {key!r}"
            ) from None

    def __setattr__(self, key, value):
        if key in ("__name__", "__file__", "__package__", "__loader__", "__spec__", "__doc__"):
            object.__setattr__(self, key, value)
        else:
            NS[key] = value

    def __delattr__(self, key):
        try:
            del NS[key]
        except KeyError:
            object.__delattr__(self, key)

    def __dir__(self):
        return sorted(set(NS) | set(self.__dict__))


def _make_view(slug, path, doc):
    full = f"{__name__}.{slug}"
    view = _NamespaceView(full, doc)
    view.__dict__["__file__"] = path
    view.__dict__["__package__"] = __name__
    view.__dict__["__loader__"] = None
    view.__dict__["__spec__"] = None
    return view


def _load():
    views = []
    chain = [(slug, desc) for slug, _a, _b, desc in MODULES]
    if LOAD_PATCHES:
        chain += list(PATCHES)
    for slug, desc in chain:
        path = _os.path.join(_PKG_DIR, slug + ".py")
        view = _make_view(slug, path, desc)
        _sys.modules[view.__dict__["__name__"]] = view
        globals()[slug] = view
        views.append((slug, path))

    for slug, path in views:
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        try:
            code = compile(src, path, "exec")
        except SyntaxError as exc:
            raise ImportError(f"acacia: {slug} failed to compile: {exc}") from exc
        # __name__ is pointed at the slice while it executes, so classes get a
        # __module__ that resolves to the file they are actually written in -
        # which is what makes inspect.getsource(), pickling and tracebacks
        # land in the right place. It also keeps the trailing
        # `if __name__ == "__main__"` guard false, exactly as an import of the
        # original file would have.
        NS["__name__"] = f"{__name__}.{slug}"
        NS["__file__"] = _os.path.join(_ROOT_DIR, "acacia.py")
        try:
            exec(code, NS)
        except Exception as exc:  # pragma: no cover - surfaced to the user
            raise ImportError(f"acacia: {slug} failed to execute: {exc!r}") from exc
        finally:
            NS["__name__"] = __name__


_load()


def module_of(name):
    """Return the slice that *defines* ``name`` - handy when navigating."""
    import inspect

    obj = NS.get(name)
    try:
        return _os.path.basename(inspect.getfile(obj))
    except Exception:
        return None


def reload_namespace():
    """Re-execute every slice into the shared namespace (dev helper)."""
    _load()


def __getattr__(name):
    """Expose the shared namespace directly: ``from acacia import App``."""
    try:
        return NS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


def __dir__():
    return sorted(set(globals()) | set(NS))
