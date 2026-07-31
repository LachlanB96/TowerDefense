"""Runs INSIDE Blender. Seeds a namespace and execs a conforming asset script.

    blender -b -P _tools/build_one.py -- \
        --script Assets/Blender/blender_knight000.py \
        --variant path/to/variant.json \
        --out    path/to/out/dir

Why a bootstrap rather than running the asset script directly: the asset script
has no way to receive a variant dict from the command line, and we do not want
to teach every script an argument parser. Pre-seeding a namespace and exec'ing
is the pattern _knight000/audit_knight000.py already uses.

"Conforming" is enforced, not assumed: a script without the variant-hook marker
is refused outright rather than exec'd. See HOOK_MARKER below.
"""

import argparse
import json
import os
import sys
import traceback

# SAFETY INTERLOCK, not a style marker. Must stay byte-identical to
# preview.py's HOOK_MARKER; it is duplicated rather than imported because this
# file runs inside Blender, where _tools/ is not on sys.path.
#
# The seeded DO_SAVE / DO_EXPORT below only protect a script that READS them.
# Eight of the nine blender_*.py scripts in this repo never do - they save
# and/or export unconditionally at module scope - so exec'ing one here would
# overwrite the real .blend and .fbx. preview.py gates this too, but build_one
# is directly invocable (`blender -b -P build_one.py -- --script ...`), so that
# gate alone is not enough.
HOOK_MARKER = "# --- variant hook ---"

# Distinct from 3 ("the script raised") so the refusal is tellable apart from a
# build failure by exit code alone, without parsing _build.json.
EXIT_NOT_CONFORMING = 4


def parse_args():
    # Blender swallows everything before "--"; our flags live after it.
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True, help="asset script to exec")
    ap.add_argument("--variant", required=True, help="JSON file of overrides")
    ap.add_argument("--out", required=True, help="render output directory")
    return ap.parse_args(argv)


def main():
    a = parse_args()
    os.makedirs(a.out, exist_ok=True)
    status_path = os.path.join(a.out, "_build.json")

    # Read the script before doing anything else with it, so the interlock can
    # be checked before a single line of it is compiled or run.
    with open(a.script, encoding="utf-8") as fh:
        src = fh.read()

    if HOOK_MARKER not in src:
        # Reported through _build.json for the same reason build failures are:
        # the runner reads that file, and Blender's exit code for a -P script
        # is not a channel worth trusting on its own.
        msg = ("refused: %s has no %r block, so it has not opted into the "
               "preview harness. Running it would save and export over the "
               "real .blend and .fbx. See CLAUDE.md, \"Preview harness\"."
               % (a.script, HOOK_MARKER))
        with open(status_path, "w", encoding="utf-8") as fh:
            json.dump({"ok": False, "error": msg}, fh, indent=2)
        print(msg, file=sys.stderr)
        return EXIT_NOT_CONFORMING

    with open(a.variant, encoding="utf-8") as fh:
        variant = dict(json.load(fh))

    # RENDER_DIR rides in VARIANT, not just in the seeded namespace. Asset
    # scripts assign RENDER_DIR themselves near the top of the file, which would
    # clobber a plain seed; VARIANT is applied at the hook, after that
    # assignment and before any render call reads it.
    variant["RENDER_DIR"] = a.out
    variant.setdefault("DO_RENDER", True)

    # Previews are strictly non-destructive: never touch the real .blend or FBX.
    variant["DO_SAVE"] = False
    variant["DO_EXPORT"] = False

    ns = {
        "__name__": "__main__",
        "__file__": a.script,
        "VARIANT": variant,
        # Seeded as well as passed via VARIANT so that scripts using the
        # _flag() idiom (which reads globals() at import time, before the hook
        # runs) also see the right values.
        "RENDER_DIR": a.out,
        "DO_RENDER": True,
        "DO_SAVE": False,
        "DO_EXPORT": False,
    }

    try:
        exec(compile(src, a.script, "exec"), ns)
    except Exception:
        # Written rather than raised: Blender's exit code for an exception in a
        # -P script is not reliable enough to be the only channel, and the
        # runner needs the traceback text regardless.
        with open(status_path, "w", encoding="utf-8") as fh:
            json.dump({"ok": False, "error": traceback.format_exc()}, fh, indent=2)
        traceback.print_exc()
        return 3

    with open(status_path, "w", encoding="utf-8") as fh:
        json.dump({"ok": True}, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
