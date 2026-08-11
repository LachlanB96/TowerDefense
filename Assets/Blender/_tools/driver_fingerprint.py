"""Render a fixed reference wave and hash it, so a driver/backend change is detectable.

    python Assets/Blender/_tools/driver_fingerprint.py capture   # before you change anything
    python Assets/Blender/_tools/driver_fingerprint.py compare   # after the driver update

WHY. A manifest records `script_sha` and the orbit draw, so a verdict can be replayed
against the same code and the same cameras. The RENDERER is an input too. Measured
2026-08-11 on evilMage000: switching Blender's GPU backend OpenGL -> Vulkan moved 2.3%
of frame pixels by up to 24/255, against the 1-2/255 that a genuine no-op produces. A
GPU driver update is a change to the same layer and can move the baseline the same way.

If it does, every stored champion belongs to an older rendering era, and a comparison
across the boundary measures the driver as well as the model - the same silent failure
as re-deriving cameras from a seed after the draw changed. This makes the boundary
visible: capture before, compare after, and know rather than assume.

Fixed everything that can be fixed - one asset, one seed, one sample scale, the named
`front` view plus two orbit cells - so the ONLY variable is the renderer.
"""
import argparse
import json
import os
import shutil
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np                                              # noqa: E402
from PIL import Image                                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import orbit                                                    # noqa: E402
import preview                                                  # noqa: E402

ASSET = "evilMage000"
SEED = 4242                    # fixed forever; changing it invalidates every capture
DIST, AIM_Z = 5.6, 1.15
STORE = os.path.join(HERE, "..", "_previews~", "_fingerprints")


def _cells():
    return orbit.views(orbit.draw(SEED, dist=DIST, aim_z=AIM_Z), DIST, AIM_Z)[:2]


# A render is NOT byte-reproducible: re-running an identical wave shifts a small number
# of pixels by 1-2 levels of 255, from shader-compilation ordering. The first version of
# this tool compared sha256 digests and duly reported "baseline moved" against its own
# capture, on an unchanged machine - the same class of error as re-deriving cameras from
# a seed. So compare PIXELS with the tolerance the project already calibrated:
#   <= 2/255  shader rounding, the renderer is equivalent
#   24/255 on 2.3% of frame  the measured OpenGL -> Vulkan backend switch
EQUIV_MAX_DELTA = 2


def _render():
    cells = _cells()
    names = [c["name"] for c in cells] + ["front"]
    man = preview.run(asset=ASSET,
                      variants=[{"label": "fingerprint", "vars": {"EXTRA_VIEWS": cells}}],
                      views=names, sample_scale=0.5, tag="fingerprint")
    run_dir = os.path.join(preview.PREVIEW_ROOT, ASSET, "run-%03d" % man["run"], "v1")
    return sorted(names), man.get("render_env"), man.get("script_sha"), run_dir


def _delta(pa, pb):
    """(changed-pixel %, max delta) between two renders of the same view."""
    A = np.asarray(Image.open(pa).convert("RGB"), dtype=np.int16)
    B = np.asarray(Image.open(pb).convert("RGB"), dtype=np.int16)
    if A.shape != B.shape:
        return None, None
    d = np.abs(A - B)
    changed = float((d.max(axis=2) > 0).sum()) * 100.0 / (A.shape[0] * A.shape[1])
    return changed, int(d.max())


def capture():
    names, env, sha, run_dir = _render()
    os.makedirs(STORE, exist_ok=True)
    kept = []
    for n in names:
        src = os.path.join(run_dir, n + ".png")
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(STORE, n + ".png"))
            kept.append(n)
    with open(os.path.join(STORE, "baseline.json"), "w", encoding="utf-8") as fh:
        json.dump({"asset": ASSET, "seed": SEED, "script_sha": sha,
                   "render_env": env, "views": kept}, fh, indent=2)
    print("captured %d views under %s" % (len(kept), env))
    print("  reference images kept in %s" % STORE)
    return 0


def compare():
    path = os.path.join(STORE, "baseline.json")
    if not os.path.exists(path):
        print("no baseline captured - run `capture` first", file=sys.stderr)
        return 2
    old = json.load(open(path, encoding="utf-8"))
    names, env, sha, run_dir = _render()

    print("renderer  before  %s" % old.get("render_env"))
    print("          now     %s" % env)
    if old.get("script_sha") != sha:
        print("\nSCRIPT CHANGED (%s -> %s) - this cannot isolate the renderer. Re-capture "
              "on the current script instead." % (old.get("script_sha"), sha),
              file=sys.stderr)
        return 2

    worst, moved = 0, []
    for n in old.get("views", []):
        ref, new = os.path.join(STORE, n + ".png"), os.path.join(run_dir, n + ".png")
        if not os.path.exists(new):
            print("  %-8s MISSING from the new render" % n)
            continue
        changed, mx = _delta(ref, new)
        if mx is None:
            print("  %-8s RESOLUTION CHANGED" % n)
            moved.append(n)
            continue
        worst = max(worst, mx)
        verdict = "equivalent" if mx <= EQUIV_MAX_DELTA else "MOVED"
        if mx > EQUIV_MAX_DELTA:
            moved.append(n)
        print("  %-8s %-10s  %6.2f%% of pixels differ, max delta %d/255"
              % (n, verdict, changed, mx))

    if not moved:
        print("\nRENDERER IS EQUIVALENT (worst delta %d/255, at or under the %d/255 "
              "shader-rounding floor). Every stored champion and verdict still stands."
              % (worst, EQUIV_MAX_DELTA))
        return 0
    print("\nBASELINE MOVED on %d view(s), worst delta %d/255. Stored champions belong to "
          "the OLD rendering era: a comparison across this boundary measures the renderer "
          "as well as the model.\nRe-render the champion and treat it as a new baseline "
          "era, the same discipline as a bake." % (len(moved), worst))
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["capture", "compare"])
    sys.exit({"capture": capture, "compare": compare}[ap.parse_args().action]())
