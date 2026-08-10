"""Measure character invariants on a rendered orbit. Chips, never gates.

    python Assets/Blender/_tools/chips.py mage000 <run>/v2 --baseline <run>/v1
    python Assets/Blender/_tools/chips.py mage000 <run>/v2 --json chips.json

Runs in SYSTEM Python. PIL + numpy + scipy only.

WHAT A CHIP IS, AND IS NOT
--------------------------
A chip is a measurement attached to a candidate. It blocks AUTOMATIC promotion and does
nothing else: the candidate is still built, still rendered, still judged, still visible,
and the user can still promote it by hand.

It is deliberately not a gate. The user's own ruling: *"the rules are quite weak and good
design might get left behind because the audit failed it on some legacy rule. I dont
think we should have those binary rules and just see what the model can produce."* A hard
gate would have killed design d26 before it ever rendered - and d26 is how the narrower
skirt was discovered to be worth having, even though its other half was reverted.

Everything here is MEASURED, never asserted. An assert crashes the build, which makes
"violated an invariant" indistinguishable from "the build is broken" - and the second is
the one that must never be silent.

SCALE-FREE BY CONSTRUCTION
--------------------------
Every quantity below is a ratio, a fraction of the figure, or an angle. Nothing is a
pixel count and nothing may become one: the model's final rendered size is unknown and
may change drastically, so a threshold in pixels would be a guess dressed as a rule.
The silhouette masks are read from the `<view>_mask.png` companions the asset scripts
render, which are geometric and independent of lighting.
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

try:
    from scipy import ndimage
except ImportError:                                  # scipy is present, but say so clearly
    ndimage = None

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)

MASK_A = 0.5          # alpha above this is figure
LEAN_TOL_DEG = 3.0    # INV-2: how far the figure's axis may tilt
OFFSET_TOL = 0.040    # INV-1: apex offset, as a fraction of figure HEIGHT (not pixels)
SPECK = 0.002         # components smaller than this fraction of the figure are noise
# "Inert" thresholds. Both are fractions, never pixel counts - the rendered size is
# unknown by rule. Calibrated against a measured no-op: a 2.3x HAT_OVAL sweep moved
# coverage 0.0001 and mirror-IoU 0.0004, so anything at that magnitude is noise.
# A candidate whose silhouette IoU against the incumbent stays above this in EVERY view
# has not meaningfully changed the shape. Calibrated on a measured no-op: a 2.3x
# HAT_OVAL sweep held IoU at ~0.999 in all views.
INERT_IOU_MIN = 0.995


def masks_in(view_dir):
    """Every rendered silhouette in a variant directory, keyed by view name."""
    out = {}
    for f in sorted(os.listdir(view_dir)):
        if not f.endswith("_mask.png"):
            continue
        im = Image.open(os.path.join(view_dir, f))
        if "A" not in im.getbands():
            continue
        a = np.asarray(im.getchannel("A"), dtype=np.float32) / 255.0
        out[f[:-len("_mask.png")]] = a > MASK_A
    return out


def _axis_and_offset(m):
    """Lean angle and apex offset for one silhouette.

    The figure's axis is taken as the line from the centroid of its lowest decile (the
    base, i.e. the feet) to the centroid of its highest decile (the apex). That is
    robust to an asymmetric silhouette in a way a bounding box is not, and it is what
    "carries his own weight" actually means: the mass above is over the mass below.

    Offset is normalised by figure HEIGHT, so a giant and an ant lean identically.
    """
    ys, xs = np.nonzero(m)
    if len(ys) < 50:
        return None, None
    y0, y1 = ys.min(), ys.max()
    h = max(1, y1 - y0)
    lo = ys >= y1 - 0.10 * h
    hi = ys <= y0 + 0.10 * h
    if lo.sum() < 5 or hi.sum() < 5:
        return None, None
    base_x, apex_x = xs[lo].mean(), xs[hi].mean()
    dx = apex_x - base_x
    return float(np.degrees(np.arctan2(dx, h))), float(dx / h)


def _components(m):
    """(count, largest-fraction) over connected components, ignoring specks.

    Specks are dropped by area fraction rather than by pixel count, because a pixel
    threshold would silently mean different things at different render sizes.
    """
    if ndimage is None:
        return None, None
    lab, n = ndimage.label(m)
    if n == 0:
        return 0, 0.0
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    total = sizes.sum()
    real = [s for s in sizes if s / total >= SPECK]
    return len(real), float(max(sizes) / total)


def _symmetry(m):
    """IoU of the silhouette against its own mirror, about its centroid column.

    A lean shows up here as a drop, and it is a whole-shape measure rather than a
    two-point one - so it catches a curve that _axis_and_offset would read as upright.
    """
    ys, xs = np.nonzero(m)
    if not len(xs):
        return None
    c = int(round(xs.mean()))
    w = min(c, m.shape[1] - c - 1)
    if w < 8:
        return None
    a = m[:, c - w:c + 1]
    b = m[:, c:c + w + 1][:, ::-1]
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else None


def iou_vs(view_dir, base_dir):
    """Per-view silhouette IoU between a candidate and the incumbent.

    The honest "did this change the shape" measure. Both masks come from the same
    orbit draw, so they are the same camera on two models and IoU is directly
    comparable. Dimensionless, so it means the same thing at any rendered size.
    """
    a, b = masks_in(view_dir), masks_in(base_dir)
    out = {}
    for k in sorted(set(a) & set(b)):
        x, y = a[k], b[k]
        if x.shape != y.shape:
            continue
        u = np.logical_or(x, y).sum()
        out[k] = round(float(np.logical_and(x, y).sum() / u), 5) if u else 1.0
    return out


def measure(view_dir):
    """Per-view invariant measurements for one candidate."""
    masks = masks_in(view_dir)
    if not masks:
        return {"error": "no *_mask.png in %s - render with mask=True" % view_dir}
    views = {}
    for name, m in sorted(masks.items()):
        lean, off = _axis_and_offset(m)
        n, largest = _components(m)
        views[name] = {
            "coverage": round(float(m.mean()), 5),        # fraction of frame, not pixels
            "lean_deg": None if lean is None else round(lean, 2),
            "apex_offset": None if off is None else round(off, 4),
            "components": n,
            "largest_frac": None if largest is None else round(largest, 4),
            "mirror_iou": (lambda s: None if s is None else round(s, 4))(_symmetry(m)),
        }
    return {"views": views}


def chips(meas, base=None):
    """Turn measurements into named chips. A chip is a flag plus its evidence.

    LEAN AND WEIGHT ARE MEASURED AS A CHANGE FROM THE INCUMBENT, NEVER AS AN ABSOLUTE.
    This is not a softening; the absolute form was measuring the wrong object. The
    silhouette includes the staff, which he holds out to one side, so from a high
    bearing the topmost region of the outline is the gem rather than his head - and
    "apex offset from the feet" then reports a held prop as a lean. Run against the
    accepted champion it fired 21 degrees of lean on a figure the user had specifically
    reverted a lean out of.

    A delta cancels the prop, because the prop is in both images. It also matches how
    everything else here decides: candidate against incumbent, never against an
    absolute scale invented by an agent. Absolute lean is a property of the geometry
    and wants a 3D measurement out of the build, not an outline out of a picture -
    that is a real gap and it is recorded in the invariants file rather than faked here.
    """
    if "error" in meas:
        return [{"chip": "unmeasurable", "detail": meas["error"], "blocks_auto": True}]
    v = meas["views"]
    out = []

    # Detachment IS honestly readable from one silhouette: a floating part is a second
    # connected component whatever the camera or the size.
    multi = [k for k, d in v.items() if d["components"] and d["components"] > 1]
    if multi:
        out.append({"chip": "INV-4 detached",
                    "detail": "more than one silhouette component in %s - allowed only "
                              "if the detachment is deliberate and declared"
                              % ", ".join(multi),
                    "blocks_auto": True})

    if base and "views" in base:
        # INERT CHANGE. Found by running the loop: a 2.3x sweep of HAT_OVAL moved
        # silhouette coverage by 0.0001 across five builds. The gene barely reaches the
        # outline, so five renders and - had it gone further - five judge calls would
        # have been spent separating images that are not meaningfully different.
        #
        # This is the cheapest guard in the system and it belongs before the judge, not
        # after: an inert pair is exactly the case where a forced-choice judge will
        # confabulate a preference out of render noise, which is the failure mode the
        # margin scale exists to avoid. It is a CHIP, not a gate - a change can be
        # deliberately subtle, and the user decides - but it must be visible.
        #
        # MEASURED AS IoU AGAINST THE INCUMBENT'S OWN SILHOUETTE, not as a change in
        # coverage. The first version of this check used coverage and was wrong in a
        # way worth recording: coverage is AREA, and a wave along an edge adds and
        # removes roughly equal area, so an area measure is blind to precisely the
        # shape change it was written to detect. It passed the inert HAT_OVAL sweep
        # and then also flagged a real brim-waviness change as inert.
        #
        # IoU is a shape measure and catches both. It is dimensionless, so it holds at
        # any rendered size.
        iou = meas.get("_iou_vs_base") or {}
        if iou:
            worst_shape = min(iou.values())
            if worst_shape > INERT_IOU_MIN:
                out.append({"chip": "inert",
                            "detail": "silhouette IoU against the incumbent is %.4f at "
                                      "worst across %d views - this change barely "
                                      "reaches the outline. Expected for a surface or "
                                      "colour change; if it was meant to alter the "
                                      "shape, it did not."
                                      % (worst_shape, len(iou)),
                            "blocks_auto": True})

    if not base or "views" not in base:
        out.append({"chip": "no-baseline",
                    "detail": "lean and weight are only measurable as a change from the "
                              "incumbent; pass --baseline to evaluate them",
                    "blocks_auto": False})
        return out

    bv = base["views"]
    shared = [k for k in v if k in bv]

    dl = [(k, v[k]["lean_deg"] - bv[k]["lean_deg"]) for k in shared
          if v[k]["lean_deg"] is not None and bv[k]["lean_deg"] is not None]
    worst = max(dl, key=lambda kv: abs(kv[1])) if dl else None
    if worst and abs(worst[1]) > LEAN_TOL_DEG:
        out.append({"chip": "INV-2 lean",
                    "detail": "axis moved %+.1f deg against the incumbent in %s "
                              "(tolerance %.0f)" % (worst[1], worst[0], LEAN_TOL_DEG),
                    "blocks_auto": True})

    do = [(k, v[k]["apex_offset"] - bv[k]["apex_offset"]) for k in shared
          if v[k]["apex_offset"] is not None and bv[k]["apex_offset"] is not None]
    woff = max(do, key=lambda kv: abs(kv[1])) if do else None
    if woff and abs(woff[1]) > OFFSET_TOL:
        out.append({"chip": "INV-1 weight",
                    "detail": "apex shifted %+.3f of figure height against the incumbent "
                              "in %s" % (woff[1], woff[0]),
                    "blocks_auto": True})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("asset")
    ap.add_argument("view_dir", help="a variant directory holding rendered orbit views")
    ap.add_argument("--baseline", help="the incumbent's directory, for a delta")
    ap.add_argument("--json", help="write the packet here")
    a = ap.parse_args()

    inv = os.path.join(BLENDER_DIR, "_chars", "%s.invariants.md" % a.asset)
    meas = measure(a.view_dir)
    base = measure(a.baseline) if a.baseline else None
    if a.baseline and "error" not in meas:
        meas["_iou_vs_base"] = iou_vs(a.view_dir, a.baseline)
    got = chips(meas, base)

    packet = {"asset": a.asset, "dir": os.path.abspath(a.view_dir),
              "invariants_file": inv if os.path.exists(inv) else None,
              "measured": meas, "chips": got}

    if base:
        if "views" in base and "views" in meas:
            packet["delta"] = {
                k: {"coverage": round(meas["views"][k]["coverage"]
                                      - base["views"][k]["coverage"], 5),
                    "mirror_iou": (None if base["views"][k]["mirror_iou"] is None
                                   or meas["views"][k]["mirror_iou"] is None
                                   else round(meas["views"][k]["mirror_iou"]
                                              - base["views"][k]["mirror_iou"], 4))}
                for k in meas["views"] if k in base["views"]}

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:   # utf-8: Windows is cp1252
            json.dump(packet, fh, indent=2)

    if not os.path.exists(inv):
        print("note: no invariants file at %s - measuring anyway" % inv)
    if "error" in meas:
        print("UNMEASURABLE: %s" % meas["error"])
        return 1
    print("%s  %d views" % (os.path.basename(a.view_dir), len(meas["views"])))
    for k, d in meas["views"].items():
        print("  %-6s cover %.3f  lean %+5s  apex %+7s  comps %-3s  mirror %s"
              % (k, d["coverage"], d["lean_deg"], d["apex_offset"],
                 d["components"], d["mirror_iou"]))
    print("chips: %s" % ("none" if not got else ""))
    for c in got:
        print("  [%s] %s" % (c["chip"], c["detail"]))
    # Chips never fail the process. Exit 0 even when one fires: this is a measurement
    # tool, and a non-zero exit is how a measurement quietly becomes a gate.
    return 0


if __name__ == "__main__":
    sys.exit(main())
