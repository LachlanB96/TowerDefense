"""Generate a conforming-from-birth Gloomfell asset script.

    python Assets/Blender/_tools/scaffold.py boar000
    python Assets/Blender/_tools/scaffold.py boar000 --dist 4.2 --aim-z 0.8

Writes Assets/Blender/blender_<asset>.py from _scaffold_template.py: variant
hook, RENDER_ONLY/SAMPLE_SCALE, EXTRA_VIEWS orbit cells with rig yaw, mask
passes, save/export behind DO_SAVE/DO_EXPORT. Used by modev4 genesis so a new
asset is drivable by preview.py from its first commit - retrofitting later is
how eight of the nine legacy scripts became undrivable.

Refuses to overwrite an existing script without --force: a generated blockout
must never silently replace a grown asset.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)
TEMPLATE = os.path.join(HERE, "_scaffold_template.py")

# Lowercase alnum/underscore, letter first: matches the <name>000 convention and
# stays a valid module/file name. Same shape serve.py's ASSET_RE trusts.
ASSET_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


def scaffold(asset, dist=5.6, aim_z=1.15, out_dir=None, force=False):
    """Write blender_<asset>.py and return its path."""
    if not ASSET_RE.match(asset):
        raise SystemExit(
            "asset code must be lowercase letters/digits/underscores starting "
            "with a letter, not %r" % asset)
    out_dir = out_dir or BLENDER_DIR
    out = os.path.join(out_dir, "blender_%s.py" % asset)
    if os.path.exists(out) and not force:
        raise SystemExit("refusing to overwrite %s (pass --force if the "
                         "blockout really should replace it)" % out)
    with open(TEMPLATE, encoding="utf-8") as fh:
        src = fh.read()
    # Numbers first (they contain no token text), then the asset name - which
    # also fills ___ASSET__ (the _<asset> render-folder convention).
    src = src.replace("__DIST__", repr(float(dist)))
    src = src.replace("__AIMZ__", repr(float(aim_z)))
    src = src.replace("__ASSET__", asset)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("asset", help="asset code, e.g. boar000")
    ap.add_argument("--dist", type=float, default=5.6,
                    help="orbit camera distance (per-asset framing constant)")
    ap.add_argument("--aim-z", type=float, default=1.15,
                    help="orbit aim height (per-asset framing constant)")
    ap.add_argument("--out-dir", help="target directory (default Assets/Blender)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    out = scaffold(a.asset, a.dist, a.aim_z, a.out_dir, a.force)
    print("scaffolded %s" % out)
    print("next: preview it -  python Assets/Blender/_tools/preview.py %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
