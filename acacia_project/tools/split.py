"""Mechanically cut acacia_unified.py into acacia/mNN_*.py at safe boundaries.

A boundary is "safe" iff no top-level statement spans it. Each module file is
a verbatim slice of the original source - no rewriting, no reindenting, no
import fixups. Shared-namespace execution (acacia/__init__.py) is what keeps
behaviour identical.
"""
import ast
import os
import sys

SRC = "acacia_unified.py"
OUT = "acacia"

# (line of the "# [k] ..." banner title, module slug, one-line responsibility)
SECTIONS = [
    (1,     "m00_preamble",             "module docstring, stdlib/optional-dep imports (HAS_* guards), GPU capability helpers"),
    (318,   "m01_config",               "[0]  config / util / persistence: paths, JSON load+save, app constants"),
    (629,   "m02_events",               "[1]  Event + perception: raw happenings become structured events"),
    (939,   "m03_emotion",              "[2]  emotion: smoothed sticky affect with hysteresis and momentum"),
    (1245,  "m04_memory",               "[3]  short-term + scored long-term memory, persisted across launches"),
    (1708,  "m05_inner_life",           "[3.5] idle simulation: time awareness, interests, daydreaming"),
    (1860,  "m06_personality",          "[3.6] stable traits that slowly evolve from experience"),
    (2018,  "m07_relationships",        "[3.7] relationships + friends: the social world's building blocks"),
    (2225,  "m08_needs_goals",          "[4]  needs + goal system"),
    (2475,  "m09_decision",             "[5]  decision layer: shapes behaviour and how the creature talks"),
    (2734,  "m10_snapshots_marketplace","[4.9] snapshots / marketplace / inter-creature (phases 62-65)"),
    (3101,  "m11_attention",            "[5.5] attention: a finite budget spent on what matters right now"),
    (3207,  "m12_spiking_net",          "[6]  the original spiking neural net (preserved)"),
    (3331,  "m13_knowledge",            "[6.4] knowledge: entities, places, falsifiable hypotheses, plans"),
    (4236,  "m14_cognition",            "[6.5] cognition: world model / self model / prediction / planning"),
    (4686,  "m15_brain",                "[7]  Brain - ties emotion/memory/needs/decision/cognition together"),
    (5540,  "m16_model_backends",       "[8]  LLM backends (LOCAL GGUF / OLLAMA / CLAUDE / GEMINI), model manager"),
    (6674,  "m17_social_world",         "[8.5] social world: friends and friend-to-friend interactions"),
    (7034,  "m18_renderer",             "[9]  creature renderer: procedural segmented anatomy over a 2D rig"),
    (7510,  "m19_world",                "[9.5] world: environment, lighting, vegetation, points of interest"),
    (7946,  "m20_friend_actors",        "[9.6] friends as real bodies in the world, not list rows"),
    (8057,  "m21_brain_view",           "[9.7] anatomical brain-activity render"),
    (8222,  "m22_ui_toolkit",           "[10] shared UI widgets / toolkit"),
    (8514,  "m23_live_mode",            "[10.5] live mode: real-time computer-interaction awareness"),
    (8760,  "m24_computer_agent",       "[10.5] computer agent: event-driven awareness of the host machine"),
    (8872,  "m25_fx_core",              "[11.5a] TrippyGram base fx_* effects (the original 50)"),
    (9402,  "m26_nft_character",        "[11.5b] NFT HD patch: trait config, palettes, HD supersampled character generator, v6/v7 fx batches"),
    (15839, "m27_fx_registry",          "[11.5c] EFFECTS / EFFECT_NAMES / EFFECT_MAP / INTENSITY_FX registry + standalone NFT test"),
    (16136, "m28_media_pipeline",       "[11.5d] trippy image generation, OpenCV video pipeline, NFT reel generator"),
    (17236, "m29_posting",              "[11.5e] Selenium browser automation: Instagram / Facebook / X posting"),
    (19101, "m30_bridge_helpers",       "[11.5f] TrippyGram-side Acacia bridge helpers + AI-generated NFT traits"),
    (19708, "m31_trippygram_app",       "[11.5g] IGSession + TrippyGramApp - the original TrippyGram interface"),
    (28235, "m32_acacia_bridge",        "[12] the joint: CreatureVisualState, mind->engine call path, VisualMemory"),
    (31056, "m33_app",                  "[11] App - the merged application window; main() - the entry point"),
]

DECOR = ("# =", "# \u2550", "# \u2500", "# -", "#=", "# _")


def main():
    src = open(SRC, encoding="utf-8").read()
    lines = src.splitlines(keepends=True)
    n = len(lines)
    tree = ast.parse(src)

    # 1-based line ranges occupied by top-level statements
    spans = []
    for node in tree.body:
        start = node.lineno
        for d in getattr(node, "decorator_list", []) or []:
            start = min(start, d.lineno)
        spans.append((start, node.end_lineno))

    def safe(cut):
        """cut == the 1-based line that starts a new module."""
        return all(not (a < cut <= b) for a, b in spans)

    cuts = []
    for lineno, slug, desc in SECTIONS:
        c = lineno
        # walk up over the banner decoration lines directly above the title
        while c > 1 and lines[c - 2].startswith(DECOR):
            c -= 1
        # walk up over blank lines so the banner keeps its breathing room
        while c > 1 and not lines[c - 2].strip():
            c -= 1
        if not safe(c):
            orig = c
            while c > 1 and not safe(c):
                c -= 1
            print(f"  ! {slug}: cut {orig} unsafe -> snapped to {c}")
        cuts.append((c, slug, desc))

    for i in range(1, len(cuts)):
        assert cuts[i][0] > cuts[i - 1][0], f"non-monotonic cut at {cuts[i]}"

    os.makedirs(OUT, exist_ok=True)
    manifest = []
    for i, (start, slug, desc) in enumerate(cuts):
        end = cuts[i + 1][0] - 1 if i + 1 < len(cuts) else n
        body = "".join(lines[start - 1:end])
        if not body.endswith("\n"):
            body += "\n"
        path = os.path.join(OUT, slug + ".py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        manifest.append((slug, start, end, end - start + 1, desc))
        print(f"  {slug:28s} lines {start:6d}-{end:6d}  ({end - start + 1:5d})")

    total = sum(m[3] for m in manifest)
    assert total == n, f"line accounting mismatch: {total} != {n}"
    with open(os.path.join(OUT, "_manifest.py"), "w", encoding="utf-8") as fh:
        fh.write("# generated by tools/split.py - load order for the shared namespace\n")
        fh.write("MODULES = [\n")
        for slug, a, b, c, desc in manifest:
            fh.write(f"    ({slug!r}, {a}, {b}, {desc!r}),\n")
        fh.write("]\n")
    print(f"\n{len(manifest)} modules, {total} lines accounted for (original {n}).")


if __name__ == "__main__":
    sys.exit(main())
