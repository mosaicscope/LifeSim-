"""
================================================================================
 ACACIA  v1  --  a persistent artificial mind with hands.
================================================================================

 ACACIA is CREATURE and TrippyGram merged into one application and one file.

 CREATURE is the host: the mind, the body, the world, the model backends and
 the interface all stay exactly as they were.  TrippyGram is no longer a
 separate program that CREATURE talks to over a heartbeat file - its entire
 image engine, its ~250 effects, its NFT generator, its video and reel
 pipelines and its complete original interface now live inside this process
 as a native subsystem.

 The joint between them is section [12]:

     mind  -> visuals   CreatureVisualState turns valence / arousal / stress /
                        curiosity / boredom / confidence / energy into visual
                        parameters; TrippyGramEngine turns those into real
                        calls into the preserved effect implementations.
     visuals -> mind    what gets made is measured and comes back through the
                        existing Event / perception path, so the creature
                        reacts to its own output instead of merely logging it.
     memory             VisualMemory scores effects over time, so what it
                        reaches for is history-dependent rather than random.

 Nothing from either original file has been summarised, approximated or
 replaced with a placeholder.  Where the two codebases disagreed, the
 conflict is resolved in a comment at the point of the conflict.

 Original CREATURE header follows.
================================================================================
 CREATURE  --  a small persistent artificial mind.
================================================================================

A single-file simulated creature with:

  * a continuous internal state (valence / arousal / energy / stress /
    curiosity / confidence / boredom / familiarity / novelty / attention)
  * a smoothed, sticky emotion system with hysteresis and momentum
  * short-term + scored long-term memory that persists across launches
  * needs, goals, priorities and a decision layer that shapes behaviour
    AND the way the creature talks
  * a pluggable language backend:  LOCAL GGUF | OLLAMA | CLAUDE | GEMINI
  * a GGUF drop-zone: drag a .gguf file onto the app and it is registered,
    validated and selectable as the local brain (remembered between launches)
  * the original spiking neural net, needs/metabolism world and animated
    low-poly creature from earlier phases (preserved and extended)

Core architecture (see section markers below):

    EVENT -> PERCEPTION -> MEMORY RETRIEVAL -> INTERNAL STATE ->
    EMOTION UPDATE -> GOALS/DECISION -> LLM CONTEXT -> RESPONSE ->
    MEMORY UPDATE -> STATE UPDATE

Three decoupled loops:

    UI / render loop   ~30 FPS   (drawing only)
    brain loop         ~10 Hz    (cheap state integration, emotions)
    LLM inference      worker threads, only on demand

Everything lives in this one file on purpose.  Sections:

    [0] CONFIG / UTIL / PERSISTENCE
    [1] EVENTS + PERCEPTION
    [2] EMOTION SYSTEM
    [3] MEMORY SYSTEM
    [4] NEEDS + GOAL SYSTEM
    [5] DECISION SYSTEM
    [6] SPIKING NET  (original neural brain)
    [7] BRAIN        (the mind that ties it all together)
    [8] MODEL BACKENDS / GGUF MANAGER / MODEL MANAGER
    [9] CREATURE RENDERER
    [10] UI TOOLKIT
    [11] APP
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import platform
import queue
import socket
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import http.client
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# --------------------------------------------------------- merged imports
# The TrippyGram half needs Pillow, numpy, OpenCV and selenium.  The CREATURE
# half needs none of them and has always started without its optional
# dependencies, so every one of these is guarded: a missing package disables
# the part of the app that needs it and nothing else.  The original
# TrippyGram auto-installer (which opened its own Tk root at import time) is
# deliberately NOT carried over - a second Tk root inside one application is
# exactly the collision this merge exists to remove.
from datetime import datetime

try:
    from PIL import (Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter,
                     ImageFont, ImageOps, ImageTk)
    HAS_PIL = True
except Exception:  # pragma: no cover - optional
    Image = ImageChops = ImageDraw = ImageEnhance = None
    ImageFilter = ImageFont = ImageOps = ImageTk = None
    HAS_PIL = False

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:  # pragma: no cover - optional
    np = None
    HAS_NUMPY = False

try:
    import cv2
    HAS_CV2 = True
except Exception:  # pragma: no cover - optional
    cv2 = None
    HAS_CV2 = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    HAS_SELENIUM = True
except Exception:  # pragma: no cover - optional
    webdriver = Options = Service = By = None
    HAS_SELENIUM = False


def missing_visual_deps():
    """Which of the image-side packages are absent, for the UI to report."""
    out = []
    if not HAS_PIL:
        out.append("Pillow")
    if not HAS_NUMPY:
        out.append("numpy")
    return out

# ------------------------------------------------------------------ optional
# Drag & drop is optional: without it the drop zone still works as a
# click-to-browse / paste-a-path target.
try:  # pragma: no cover - depends on local install
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except Exception:  # pragma: no cover
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False


def has_module(name: str) -> bool:
    """Cheap check for an optional dependency without importing it."""
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def llama_cpp_has_gpu_support() -> bool:
    """Best-effort check for whether the installed llama-cpp-python build was
    compiled with GPU offload (CUDA/Metal/Vulkan) support. A CPU-only wheel
    happily accepts n_gpu_layers>0 and just silently ignores it, so we
    actively ask the library rather than assume."""
    if not has_module("llama_cpp"):
        return False
    try:
        import llama_cpp
        fn = getattr(llama_cpp, "llama_supports_gpu_offload", None)
        if callable(fn):
            return bool(fn())
    except Exception:
        pass
    return False


def gguf_layer_count(path) -> int:
    """Best-effort transformer block/layer count straight out of the GGUF
    header (the `<arch>.block_count` key every architecture writes). Used to
    plan GPU offload precisely instead of guessing. Returns 0 if it can't be
    determined, so callers fall back to a conservative fixed offload."""
    try:
        with open(path, "rb") as fh:
            if fh.read(4) != b"GGUF":
                return 0
            version = struct.unpack("<I", fh.read(4))[0]
            fh.read(8)                                    # n_tensors, unused
            n_kv = struct.unpack("<Q", fh.read(8))[0]
            if version < 2:
                return 0

            def read_string():
                length = struct.unpack("<Q", fh.read(8))[0]
                if length > 1 << 20:
                    raise ValueError("string too long")
                return fh.read(length).decode("utf-8", "replace")

            SCALAR = {1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f",
                     7: "?", 10: "Q", 11: "q", 12: "d", 0: "B"}
            SIZE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}

            def skip_value(vtype):
                if vtype in SIZE:
                    return struct.unpack(SCALAR[vtype], fh.read(SIZE[vtype]))[0]
                if vtype == 8:
                    return read_string()
                if vtype == 9:
                    item_type = struct.unpack("<I", fh.read(4))[0]
                    count = struct.unpack("<Q", fh.read(8))[0]
                    for _ in range(min(count, 1 << 22)):
                        skip_value(item_type)
                    return None
                raise ValueError(f"unknown value type {vtype}")

            for _ in range(int(n_kv)):
                key = read_string()
                vtype = struct.unpack("<I", fh.read(4))[0]
                value = skip_value(vtype)
                if key.endswith(".block_count") and isinstance(value, int):
                    return int(value)
    except Exception:
        pass
    return 0


COMPUTE_MODES = ("auto", "cpu", "gpu", "hybrid")


_COMPUTE_CAPS = {}


def compute_capability():
    """Honest, cheap capability probe for the BRAIN/PROCESSING control.

    Returns {mode: (supported: bool, reason: str)}.  We never claim a mode
    works just because a button exists for it: GPU/hybrid are only offered
    when the installed llama-cpp-python was actually built with an offload
    backend.  Ollama does its own placement, so its modes are advisory
    (num_gpu hints) rather than hard guarantees - said plainly in the UI.
    """
    if _COMPUTE_CAPS:
        return _COMPUTE_CAPS
    gpu = llama_cpp_has_gpu_support()
    if gpu:
        why = "llama-cpp built with GPU offload"
        _COMPUTE_CAPS.update({
            "auto": (True, "let CREATURE choose based on free VRAM"),
            "cpu": (True, "CPU only - always available"),
            "gpu": (True, why + " - offload as many layers as fit"),
            "hybrid": (True, why + " - split layers CPU/GPU")})
        return _COMPUTE_CAPS
    why = "installed llama-cpp-python has no GPU backend"
    _COMPUTE_CAPS.update({
        "auto": (True, "let CREATURE choose (CPU on this machine)"),
        "cpu": (True, "CPU only - always available"),
        "gpu": (False, why),
        "hybrid": (False, why)})
    return _COMPUTE_CAPS


def gpu_free_vram_mb():
    """Free VRAM in MB, or None if no NVIDIA GPU is visible. Never raises,
    never blocks for long - hard-timed out for callers on the UI thread."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=1.5)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip().splitlines()[0])
    except Exception:
        pass
    return None


def plan_gpu_layers(size_bytes, n_ctx, total_layers):
    """How many of a model's layers to offload to the GPU, and why. Measured,
    not guessed: free VRAM comes from nvidia-smi, per-layer cost is estimated
    from the file size, and a fixed slice is reserved for the KV cache and
    CUDA's own overhead so a 3GB card never gets over-committed. Returns
    (n_gpu_layers, human_readable_reason)."""
    if not llama_cpp_has_gpu_support():
        return 0, "no GPU-enabled llama-cpp-python build installed - staying on CPU"
    free_mb = gpu_free_vram_mb()
    if free_mb is None:
        return 0, "no NVIDIA GPU detected - staying on CPU"
    if not total_layers:
        n = 20 if free_mb > 1500 else 0
        return n, f"layer count unknown, {free_mb:.0f}MB free -> fixed offload of {n}"
    overhead_mb = 350 + n_ctx * 0.06          # CUDA context + KV cache, rough
    usable_mb = max(0.0, free_mb - overhead_mb)
    per_layer_mb = max(1.0, (size_bytes / (1024 * 1024)) / max(1, total_layers) * 1.05)
    n = int(max(0, min(total_layers, usable_mb / per_layer_mb)))
    return n, (f"{free_mb:.0f}MB free, ~{per_layer_mb:.0f}MB/layer -> "
              f"{n}/{total_layers} layers on GPU")
