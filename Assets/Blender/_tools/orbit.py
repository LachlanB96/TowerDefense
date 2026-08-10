"""Generate a scale-free, angle-free judging stimulus: an orbit of camera cells.

    python Assets/Blender/_tools/orbit.py --seed 41                # show the draw
    python Assets/Blender/_tools/orbit.py --seed 41 --json v.json  # EXTRA_VIEWS specs
    python Assets/Blender/_tools/orbit.py --sheet run-420/v1 --out sheet.png

Runs in SYSTEM Python. Emits view specifications that a conforming asset script
consumes through its `EXTRA_VIEWS` loop, and composites the resulting PNGs into one
contact sheet for a judge.

THE RULE THIS IMPLEMENTS
------------------------
The model may be rendered at any size and seen from any angle, and that may change
drastically. Therefore:

  * No camera angle is privileged. Bearings are spaced evenly over the WHOLE circle,
    not over a wedge - a wedge reproduces the blind spot that let 47 defects survive
    five passes unnoticed on the back of the figure.
  * The whole condition - azimuth, elevation, and the key light's offset - is DRAWN
    PER WAVE from a seed, so no design can be tuned to a fixed rig. A fixed light is a
    privileged condition just as much as a fixed camera is.
  * The draw is IDENTICAL for both members of a comparison. A pairwise judgement is
    only meaningful if the only difference is the model, so the caller passes one seed
    for the pair and records it. Varying within a pair would corrupt the comparator
    that took three attempts to calibrate.
  * No absolute pixel size appears anywhere in this module, and none may be added.
    Resolution below is a fidelity choice, never a criterion.

WHY FRAMING IS FIXED AND NOT NORMALISED
---------------------------------------
The obvious implementation is to fit each candidate to a constant fraction of frame
height. That is wrong here, and subtly: it makes "taller and narrower" invisible
against the baseline, which is exactly the change (d26) the user reverted for giving
the character a weak stature. Normalising to the figure deletes proportion - the thing
most worth judging - while claiming to remove bias.

So the camera sits at a FIXED distance from the origin and aims at a FIXED height
above the ground plane. A figure that grows genuinely renders larger. The ground plane
and the up axis are intrinsic to the model, not assumptions about a viewer.

`FIT` exists only to keep a very large or very small asset inside the frame at all,
and it scales distance and aim together so proportion survives. It is per-ASSET, not
per-candidate: it must never be recomputed between a champion and its challenger.
"""

import argparse
import json
import math
import os
import random
import sys

CELLS = 6                 # renders per candidate. Full azimuth coverage at 60 deg.
SHEET_COLS = 3            # 3x2 contact sheet

# Elevation band, degrees above the ground plane. Deliberately wide and deliberately
# including below-horizon: an "ant" is seen from above and a "giant" from below, and
# neither is privileged. Straight up and straight down are excluded because they are
# degenerate for a standing figure - the silhouette collapses - not because they are
# unlikely.
ELEV_MIN, ELEV_MAX = -20.0, 70.0

# Extra rake, degrees, applied to the light rig ON TOP of following the camera.
#
# The rig follows each cell's bearing so every cell is lit comparably - otherwise a
# back bearing would render an unlit silhouette and the comparison would be about
# lighting, not about the model. The EXTRA rake is drawn per wave so that no single
# raking direction is privileged and no design can be tuned to one.
#
# The whole rig is rotated about world Z rather than the key being repositioned. The
# key/fill/rim/spill relationship is tuned art direction (the comment in the asset
# script explains why the energies are a third of the knight's); rotating preserves it.
#
# HONEST LIMIT: only the rig's YAW is drawn. Light ELEVATION stays as authored, so it
# remains a fixed condition. Varying it would mean re-tuning energies per cell, and a
# stimulus whose brightness moves is a worse trade than one whose rake does not.
RAKE_MIN, RAKE_MAX = -35.0, 35.0

CELL_RES = (600, 840)     # per cell; fidelity, not a criterion
CELL_LENS = 62


def draw(seed, cells=CELLS):
    """The per-wave condition draw. Deterministic in `seed` - that is the whole point.

    Returns a dict that is safe to record verbatim on an attempt: replaying the seed
    reproduces the exact stimulus a verdict was formed against, which is what makes a
    past judgement re-checkable at all.
    """
    rng = random.Random(seed)

    # One azimuth offset for the whole wave, then evenly spaced bearings from it.
    # Even spacing over 360 is what guarantees no side of the model can hide.
    az0 = rng.uniform(0.0, 360.0 / cells)
    step = 360.0 / cells

    # Elevation is drawn per cell rather than once, so a single wave sees the model
    # from several heights. Sorted only for legible reporting; the pairing of a
    # bearing to an elevation stays as drawn.
    elevs = [rng.uniform(ELEV_MIN, ELEV_MAX) for _ in range(cells)]

    return {
        "seed": seed,
        "cells": cells,
        "az0": round(az0, 3),
        "bearings": [round((az0 + i * step) % 360.0, 3) for i in range(cells)],
        "elevations": [round(e, 3) for e in elevs],
        "rake_deg": round(rng.uniform(RAKE_MIN, RAKE_MAX), 3),
    }


def views(d, dist, aim_z, fit=1.0, res=CELL_RES, lens=CELL_LENS, prefix="orb"):
    """Turn a draw into EXTRA_VIEWS specs the asset script can render.

    `dist` and `aim_z` are per-ASSET framing constants. `fit` scales both together, so
    a change in fit moves the camera without changing what "twice as tall" looks like.
    Both must be held constant across a comparison - see the module docstring.
    """
    out = []
    for i, (az, el) in enumerate(zip(d["bearings"], d["elevations"])):
        a, e = math.radians(az), math.radians(el)
        r = dist * fit * math.cos(e)
        out.append({
            "name": "%s%d" % (prefix, i),
            # Blender is Z-up and these assets face -Y. Bearing 0 is therefore the
            # front, and bearings increase anticlockwise seen from above.
            "cam_loc": [round(r * math.sin(a), 4),
                        round(-r * math.cos(a), 4),
                        round(aim_z * fit + dist * fit * math.sin(e), 4)],
            "target": [0.0, 0.0, round(aim_z * fit, 4)],
            "res": list(res),
            "lens": lens,
            # Yaw for the whole light rig, so this cell is lit like every other one
            # plus the wave's drawn rake. Consumed by the asset script's EXTRA_VIEWS
            # loop; a script that ignores it still renders, just with a fixed rake.
            "rig_yaw": round((az + d["rake_deg"]) % 360.0, 3),
        })
    return out


def sheet(view_dir, out_path, cells=CELLS, cols=SHEET_COLS, prefix="orb", label=None):
    """Composite one candidate's orbit into a single contact sheet.

    A judge sees one image, not six. That removes the entire class of failure where a
    pair is assembled from views that are not the same shot - which happened once with
    two different icon crops and would, in the log's own words, "have corrupted the
    judgement it was meant to inform".
    """
    from PIL import Image                       # imported late: only --sheet needs it

    tiles = []
    for i in range(cells):
        p = os.path.join(view_dir, "%s%d.png" % (prefix, i))
        if os.path.exists(p):
            tiles.append(Image.open(p).convert("RGB"))
    if not tiles:
        return None

    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new("RGB", (w * cols, h * rows), (12, 13, 18))
    for i, t in enumerate(tiles):
        if t.size != (w, h):
            t = t.resize((w, h), Image.LANCZOS)
        canvas.paste(t, ((i % cols) * w, (i // cols) * h))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    canvas.save(out_path)
    return {"path": os.path.abspath(out_path), "tiles": len(tiles),
            "size": list(canvas.size), "label": label}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, help="wave seed; identical for both sides of a pair")
    ap.add_argument("--cells", type=int, default=CELLS)
    ap.add_argument("--dist", type=float, default=5.6, help="per-asset camera distance")
    ap.add_argument("--aim-z", type=float, default=1.15, help="per-asset aim height")
    ap.add_argument("--fit", type=float, default=1.0, help="per-asset framing scale")
    ap.add_argument("--json", help="write EXTRA_VIEWS specs here")
    ap.add_argument("--sheet", help="directory of rendered orbit PNGs to composite")
    ap.add_argument("--out", help="contact sheet output path")
    a = ap.parse_args()

    if a.sheet:
        if not a.out:
            print("--sheet needs --out", file=sys.stderr)
            return 2
        r = sheet(a.sheet, a.out, cells=a.cells)
        if not r:
            print("no orbit PNGs found in %s" % a.sheet, file=sys.stderr)
            return 1
        print("sheet %s  (%d tiles, %dx%d)" % (r["path"], r["tiles"], *r["size"]))
        return 0

    if a.seed is None:
        print("--seed is required (or use --sheet)", file=sys.stderr)
        return 2

    d = draw(a.seed, a.cells)
    v = views(d, a.dist, a.aim_z, a.fit, prefix="orb")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:   # utf-8: Windows defaults cp1252
            json.dump({"draw": d, "views": v}, fh, indent=2)

    print("orbit draw  seed=%s  cells=%d" % (d["seed"], d["cells"]))
    print("  az0 %.1f deg, bearings %s"
          % (d["az0"], ", ".join("%.0f" % b for b in d["bearings"])))
    print("  elevations %s" % ", ".join("%+.0f" % e for e in d["elevations"]))
    print("  rig rake %+.0f deg on top of each bearing" % d["rake_deg"])
    for s in v:
        print("  %-6s cam (%7.3f,%7.3f,%7.3f) -> z %.3f  rig_yaw %6.1f"
              % (s["name"], *s["cam_loc"], s["target"][2], s["rig_yaw"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
