"""Measure a BEFORE/AFTER render pair. CPU-only, no Blender, sub-second.

    python Assets/Blender/_tools/measure.py <before-dir> <after-dir> \
        [--views hero_34,front,icon_full_184] [--out path.json]

Emits a plain-text FACTS block on stdout (inlined verbatim into comparator briefs)
and, with --out, a JSON packet. Run by the orchestrator between a modeller's return
and the panel. Two jobs:

  1. A pixel-identical pair is the signature of the wrong-preview.py plumbing bug
     (a worktree modeller rendering the main repo's unchanged script) — the caller
     bounces the attempt back to the modeller without convening any judge.
  2. Measured facts stop judges asserting things the pixels refute: the record has
     nine independent verifiers unanimously placing a feature at a height where its
     mask was provably zero. Facts are observations, not targets — they do not fall
     under the "never put a number in a brief" rule, which is about targets.

See docs/shelved/skills/blender-model-modev2/orchestrator.md, "The verdict" (v2 retired 2026-10-24).
"""

import argparse
import json
import os
import sys

# MUST precede the numpy import - see the same block in chips.py. OpenBLAS sizes a
# thread-buffer pool per process from the core count (36 here) and reads these only at
# load time; a dozen concurrent tool processes exhausted its allocator with 10.8 GB of
# RAM free. This work is per-frame means and masks, so BLAS threading buys nothing.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np                                              # noqa: E402
from PIL import Image                                           # noqa: E402

DIFF_L = 0.02        # |dL| above this counts as a changed pixel (below is EEVEE noise)
BG_TOL = 0.06        # distance from corner-estimated background that counts as figure
BRIGHT_L = 0.50      # luminance threshold for the bright-component table
TOP_COMPONENTS = 5   # how many bright components to report per image
MASK_A = 0.5         # alpha above this is figure, in a rendered silhouette pass

LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def _corner_mask(rgb):
    """Legacy fallback: figure = pixels differing from the corner-estimated background.

    ONLY correct on an empty backdrop. This rig stands the model on a ground disc with
    `film_transparent = False`, so the floor is counted as figure - measured at 55.18%
    coverage with 45.2% of the mask in the bottom third of frame. Kept so that old runs
    (and any asset script without a mask pass) still produce a number, but every
    silhouette statistic derived from it is compressed toward a constant and should not
    be compared against one derived from a real mask.
    """
    c = np.concatenate([
        rgb[:8, :8].reshape(-1, 3), rgb[:8, -8:].reshape(-1, 3),
        rgb[-8:, :8].reshape(-1, 3), rgb[-8:, -8:].reshape(-1, 3),
    ])
    bg = np.median(c, axis=0)
    return np.abs(rgb - bg).sum(axis=2) > BG_TOL


def figure_mask(rgb, png_path=None):
    """Figure mask for an image, preferring a rendered alpha silhouette.

    The asset script writes `<view>_mask.png` beside each judged view: a cheap RGBA pass
    with the ground hidden (see render_mask there). Its alpha IS the silhouette, exactly,
    with no backdrop guessing. It is rendered at quarter resolution because a silhouette
    needs no samples, so it is upscaled here with NEAREST - the mask must stay boolean,
    and interpolation would invent half-figure pixels along every edge.

    Falls back to the corner estimate when no mask exists, so existing runs and
    non-conforming assets keep working rather than erroring.
    """
    if png_path:
        mp = os.path.splitext(png_path)[0] + "_mask.png"
        if os.path.exists(mp):
            m = Image.open(mp)
            if "A" in m.getbands():
                a = m.getchannel("A")
                h, w = rgb.shape[:2]
                if a.size != (w, h):
                    a = a.resize((w, h), Image.NEAREST)
                return np.asarray(a, dtype=np.float32) / 255.0 > MASK_A
    return _corner_mask(rgb)


def label_components(mask):
    """Connected components (4-neighbour) without scipy: iterative flood fill.

    Only ever run on the sparse bright mask, so the pixel count is small; a cap
    guards the pathological all-bright case rather than letting it stall a wave.
    """
    labels = np.zeros(mask.shape, dtype=np.int32)
    h, w = mask.shape
    nxt = 0
    todo = np.argwhere(mask)
    if len(todo) > 200_000:      # pathological: report as one blob, stay fast
        labels[mask] = 1
        return labels, 1
    for y0, x0 in todo:
        if labels[y0, x0]:
            continue
        nxt += 1
        stack = [(int(y0), int(x0))]
        labels[y0, x0] = nxt
        while stack:
            y, x = stack.pop()
            for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = nxt
                    stack.append((ny, nx))
    return labels, nxt


def frac(v, lo, span):
    return round(float((v - lo) / span), 3) if span else 0.0


def bright_table(rgb, fig, fig_box):
    """Top bright components inside the figure: area, height fraction, mean L."""
    L = rgb @ LUMA
    labels, n = label_components((L > BRIGHT_L) & fig)
    y0, y1 = fig_box
    rows = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(labels == i)
        rows.append({
            "area_px": int(len(ys)),
            "y_frac": frac(ys.mean(), y0, y1 - y0),   # 0 = figure top, 1 = feet
            "mean_L": round(float(L[ys, xs].mean()), 3),
        })
    rows.sort(key=lambda r: -r["area_px"])
    return rows[:TOP_COMPONENTS]


def fig_bbox(fig):
    ys, xs = np.nonzero(fig)
    if not len(ys):
        return (0, 1), (0, 1)
    return (ys.min(), ys.max() or 1), (xs.min(), xs.max() or 1)


def measure_view(before_png, after_png):
    a, b = load(before_png), load(after_png)
    out = {"size": list(b.shape[:2][::-1])}
    if a.shape != b.shape:
        out["error"] = "size mismatch %s vs %s" % (a.shape[:2], b.shape[:2])
        return out
    La, Lb = a @ LUMA, b @ LUMA
    dmask = np.abs(Lb - La) > DIFF_L
    fig = figure_mask(b, after_png)
    # Say which mask produced these numbers. A coverage figure from the corner estimate
    # and one from a rendered silhouette are not comparable, and silently mixing them
    # is how a metric stops meaning anything.
    out["mask_source"] = ("render"
                          if os.path.exists(os.path.splitext(after_png)[0] + "_mask.png")
                          else "corner-estimate")
    (fy0, fy1), (fx0, fx1) = fig_bbox(fig)
    changed = int(dmask.sum())
    out["identical"] = bool(np.array_equal(a, b))
    out["changed_px"] = changed
    out["changed_pct_of_figure"] = round(100.0 * changed / max(1, int(fig.sum())), 2)
    if changed:
        ys, xs = np.nonzero(dmask)
        out["change_bbox_y"] = [frac(ys.min(), fy0, fy1 - fy0),
                                frac(ys.max(), fy0, fy1 - fy0)]
        out["change_bbox_x"] = [frac(xs.min(), fx0, fx1 - fx0),
                                frac(xs.max(), fx0, fx1 - fx0)]
        out["mean_dL_in_change"] = round(float((Lb - La)[dmask].mean()), 4)
    fa = figure_mask(a, before_png)
    out["bright_after"] = bright_table(b, fig, (fy0, fy1))
    out["bright_before"] = bright_table(a, fa, fig_bbox(fa)[0])
    # Silhouette facts. Coverage is a FRACTION of frame, never a pixel count, and IoU is
    # dimensionless - both hold whatever size the model is finally rendered at.
    fb = fig
    out["coverage_pct"] = [round(100.0 * fa.mean(), 2), round(100.0 * fb.mean(), 2)]
    inter, union = int((fa & fb).sum()), int((fa | fb).sum())
    out["silhouette_iou"] = round(inter / union, 4) if union else 1.0
    return out


def facts_text(views):
    lines = ["MEASURED FACTS (computed from the pixels; y 0 = figure top, 1 = feet)"]
    for name, v in views.items():
        if "error" in v:
            lines.append("  %s: %s" % (name, v["error"]))
            continue
        if v["identical"]:
            lines.append("  %s: IDENTICAL — the two renders are the same image" % name)
            continue
        seg = ("  %s: changed %s px (%.1f%% of figure)"
               % (name, format(v["changed_px"], ","), v["changed_pct_of_figure"]))
        if v.get("change_bbox_y"):
            seg += (" in y %.2f-%.2f, x %.2f-%.2f, mean dL %+0.3f"
                    % (v["change_bbox_y"][0], v["change_bbox_y"][1],
                       v["change_bbox_x"][0], v["change_bbox_x"][1],
                       v["mean_dL_in_change"]))
        lines.append(seg)
        for tag in ("before", "after"):
            rows = v["bright_%s" % tag]
            if rows:
                lines.append("    brightest %s: %s" % (tag.upper(), " | ".join(
                    "#%d %spx @y%.2f L%.2f" % (i + 1, format(r["area_px"], ","),
                                               r["y_frac"], r["mean_L"])
                    for i, r in enumerate(rows))))
        lines.append("    silhouette coverage %.1f%% -> %.1f%%, IoU %.3f"
                     % (v["coverage_pct"][0], v["coverage_pct"][1],
                        v["silhouette_iou"]))
    idents = [v.get("identical") for v in views.values() if "error" not in v]
    lines.append("ALL-VIEWS-IDENTICAL: %s"
                 % ("yes — bounce this attempt, nothing was rendered from the edit"
                    if idents and all(idents) else "no"))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("before", help="directory holding the BEFORE view PNGs")
    ap.add_argument("after", help="directory holding the AFTER view PNGs")
    ap.add_argument("--views", default="hero_34,front,icon_full_184")
    ap.add_argument("--out", help="also write the JSON packet here")
    a = ap.parse_args()

    views = {}
    for name in a.views.split(","):
        bp = os.path.join(a.before, name + ".png")
        fp = os.path.join(a.after, name + ".png")
        if not (os.path.exists(bp) and os.path.exists(fp)):
            views[name] = {"error": "missing %s" % [p for p in (bp, fp)
                                                    if not os.path.exists(p)]}
            continue
        views[name] = measure_view(bp, fp)

    text = facts_text(views)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"before": os.path.abspath(a.before),
                       "after": os.path.abspath(a.after),
                       "views": views, "facts": text}, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
