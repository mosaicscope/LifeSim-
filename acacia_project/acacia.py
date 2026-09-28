#!/usr/bin/env python3
"""ACACIA launcher.

    python acacia.py                 # the merged application window
    python acacia.py --effects       # list the effect registry and exit
    python acacia.py --test-nft      # render a batch of NFTs, no UI
    python acacia.py --test-poly     # render only the polygon/physics HD path
    python acacia.py --classic ...   # use the original HD renderer instead

All behaviour lives in the ``acacia`` package; this file exists so the program
still starts exactly the way it always did.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if "--classic" in sys.argv:
    os.environ["ACACIA_POLY_HD"] = "0"
    sys.argv.remove("--classic")

import acacia  # noqa: E402
from acacia.m33_app import main  # noqa: E402


def _cli():
    if "--test-poly" in sys.argv:
        n, size = 3, 1080
        if "--n" in sys.argv:
            try:
                n = int(sys.argv[sys.argv.index("--n") + 1])
            except Exception:
                pass
        if "--size" in sys.argv:
            try:
                size = int(sys.argv[sys.argv.index("--size") + 1])
            except Exception:
                pass
        acacia.NS["_poly_standalone_test"](n=n, out_dir="./test_poly", size=size)
        return 0
    return main()


if __name__ == "__main__":
    sys.exit(_cli())
