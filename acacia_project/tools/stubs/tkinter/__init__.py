"""Minimal tkinter stand-in - TEST HARNESS ONLY, never shipped.

This sandbox has no python3-tk, but m00_preamble imports tkinter
unconditionally (exactly as the original file did). This stub provides
permissive dummy classes so the import chain can be exercised and the split
verified. It is not part of the acacia package.
"""
import sys
import types

_cache = {}


class _Dummy:
    def __init__(self, *a, **k):
        self._v = k.get("value", "")

    def __call__(self, *a, **k):
        return self

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Dummy()

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

    def get(self, *a, **k):
        return self._v

    def set(self, v=None):
        self._v = v

    def __getitem__(self, k):
        return _Dummy()

    def __setitem__(self, k, v):
        pass

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return True

    def __str__(self):
        return ""


def _mk(name):
    if name not in _cache:
        _cache[name] = type(name, (_Dummy,), {})
    return _cache[name]


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    if name.isupper() or (name[:1].islower() and name not in ("font",)):
        # constants like END / LEFT and functions like mainloop
        return _mk(name)
    return _mk(name)


TclError = type("TclError", (Exception,), {})


def _submodule(modname, names=()):
    m = types.ModuleType("tkinter." + modname)
    m.__getattr__ = __getattr__
    m.TclError = TclError
    sys.modules["tkinter." + modname] = m
    return m


for _n in ("ttk", "font", "filedialog", "messagebox", "colorchooser",
           "simpledialog", "scrolledtext", "commondialog", "constants"):
    _submodule(_n)
