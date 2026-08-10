"""Expand a design row into variants, factorially, and refuse what cannot be swept.

    python Assets/Blender/_tools/axis.py mage000 row.json --out variants.json
    python Assets/Blender/_tools/axis.py mage000 row.json --seed 41 --out variants.json

Runs in SYSTEM Python. Reads a *row spec* and writes the `--variants` file that
preview.py consumes.

WHY THIS REPLACES A PROSE RULE
------------------------------
Both earlier skill versions told the modeller to "make ONE change", in prose, and both
watched it get violated by well-briefed agents. Design d26 bundled a narrower skirt with
a forward lean; the panel accepted it 204/300 and the user reverted it, and because the
two clauses had never been separated **nobody could say which one failed**. The recovery
("the un-conflated half of d26") had to be invented afterwards as a fresh design.

So this module stops asking. A row that names two clauses is EXPANDED into A alone,
B alone, and A+B. The rule becomes the shape of the work rather than an instruction to
remember, which is the only kind of rule this project has ever managed to keep.

A ROW SPEC
----------
    {
      "label": "the column, without the lean",
      "clauses": [
        {"name": "column",  "vars": {"SKIRT_FLARE": 0.27}},
        {"name": "lean",    "patch": "def build_torso(): ..."}
      ],
      "sweep": {"gene": "HAT_TILT", "points": 5}      # optional, exclusive with clauses
    }

`clauses` expands factorially (2 clauses -> 4 cells including the baseline; 3 -> 8).
`sweep` walks one independent gene across its range. The two are mutually exclusive:
crossing a sweep with clauses multiplies renders without making any single comparison
easier to attribute, which is the failure this module exists to prevent.
"""

import argparse
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import genes                                        # noqa: E402

MAX_CLAUSES = 3          # 2^3 = 8 cells; beyond this a wave stops being reviewable
MAX_SWEEP = 8
DEFAULT_SWEEP = 5


def _merge_patches(patches):
    """Concatenate clause patches into one source string.

    Patches are executed with `exec(src, globals())` inside the asset script's own
    namespace, so several builder redefinitions concatenate cleanly - later definitions
    simply win. Order follows clause order so a row's own precedence is predictable.
    """
    return "\n\n".join(p for p in patches if p)


def expand(row, gene_map):
    """Row spec -> list of preview.py variants. Raises ValueError on a refused sweep."""
    clauses = row.get("clauses") or []
    sweep = row.get("sweep")

    if clauses and sweep:
        raise ValueError(
            "a row may have clauses OR a sweep, not both: crossing them multiplies "
            "renders without making any single comparison easier to attribute, which "
            "is the whole reason this module exists")

    if sweep:
        gene = sweep["gene"]
        ok, problems = genes.check(gene_map, [gene])
        if not ok:
            raise ValueError("\n".join(problems))
        g = gene_map["genes"][gene]
        lo, hi = sweep.get("range") or g.get("range") or (None, None)
        if lo is None:
            raise ValueError(
                "%s has no literal value to derive a range from; give an explicit "
                "\"range\": [lo, hi] in the row" % gene)
        n = min(int(sweep.get("points", DEFAULT_SWEEP)), MAX_SWEEP)
        if n < 2:
            raise ValueError("a sweep needs at least 2 points")
        step = (hi - lo) / (n - 1)
        return [{"label": "%s=%.4g" % (gene, lo + i * step),
                 "vars": {gene: lo + i * step}}
                for i in range(n)]

    if not clauses:
        raise ValueError("row has neither clauses nor a sweep")
    if len(clauses) > MAX_CLAUSES:
        raise ValueError(
            "%d clauses is %d cells. Split the row: a wave you cannot review in one "
            "sitting is not a comparison, it is a backlog."
            % (len(clauses), 2 ** len(clauses)))

    # Every gene any clause touches must be sweepable before ANY of it is rendered.
    # Checking up front rather than per-cell means a bad row costs zero Blender time.
    touched = sorted({k for c in clauses for k in (c.get("vars") or {})})
    if touched:
        ok, problems = genes.check(gene_map, touched)
        if not ok:
            raise ValueError("\n".join(problems))

    out = []
    for combo in itertools.product([False, True], repeat=len(clauses)):
        on = [c for c, use in zip(clauses, combo) if use]
        # The all-off cell is the baseline. It is rendered rather than assumed: the
        # comparison is only honest if both sides came out of the same build path,
        # and a baseline carried over from another run has a different seed.
        label = "baseline" if not on else " + ".join(c["name"] for c in on)
        v = {"label": label, "vars": {}, "_clauses": [c["name"] for c in on]}
        for c in on:
            v["vars"].update(c.get("vars") or {})
        patch = _merge_patches([c.get("patch") for c in on])
        if patch:
            v["patch"] = patch
        out.append(v)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("asset")
    ap.add_argument("row", help="row spec JSON")
    ap.add_argument("--out", required=True, help="variants file for preview.py")
    ap.add_argument("--seed", type=int,
                    help="orbit seed; adds EXTRA_VIEWS to every cell so the whole wave "
                         "is judged under one identical drawn condition")
    ap.add_argument("--dist", type=float, default=5.6)
    ap.add_argument("--aim-z", type=float, default=1.15)
    a = ap.parse_args()

    path = genes.script_path(a.asset)
    if not os.path.exists(path):
        print("no such script: %s" % path, file=sys.stderr)
        return 2
    gene_map = genes.build_map(path)

    with open(a.row, encoding="utf-8") as fh:        # utf-8: Windows defaults to cp1252
        row = json.load(fh)

    try:
        variants = expand(row, gene_map)
    except ValueError as e:
        print("REFUSED:\n  %s" % str(e).replace("\n", "\n  "), file=sys.stderr)
        return 1

    wave = None
    if a.seed is not None:
        import orbit
        d = orbit.draw(a.seed)
        v = orbit.views(d, a.dist, a.aim_z)
        # One draw for the whole wave. Varying the condition between cells would make
        # the comparison about the camera instead of about the model.
        for cell in variants:
            cell.setdefault("vars", {})["EXTRA_VIEWS"] = v
        # The draw travels WITH the cells. It used to be re-typed into preview.py --seed
        # by hand, which meant a typo produced a manifest claiming a stimulus the images
        # were not rendered under - silently, and forever, since the seed is the only
        # thing that makes a verdict replayable.
        wave = {"seed": a.seed, "draw": d, "dist": a.dist, "aim_z": a.aim_z}

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"wave": wave, "cells": variants} if wave else variants, fh, indent=1)

    print("%d cells -> %s" % (len(variants), a.out))
    for c in variants:
        print("  %-40s %s" % (c["label"], ",".join(k for k in c.get("vars", {})
                                                   if k != "EXTRA_VIEWS") or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
