"""Runs INSIDE Blender. Seeds a namespace and execs a conforming asset script.

    blender -b -P _tools/build_one.py -- \
        --script Assets/Blender/blender_knight000.py \
        --variant path/to/variant.json \
        --out    path/to/out/dir

Why a bootstrap rather than running the asset script directly: the asset script
has no way to receive a variant dict from the command line, and we do not want
to teach every script an argument parser. Pre-seeding a namespace and exec'ing
is the pattern _knight000/audit_knight000.py already uses.
"""

import argparse
import json
import os
import sys
import traceback


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

    with open(a.script, encoding="utf-8") as fh:
        src = fh.read()

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
