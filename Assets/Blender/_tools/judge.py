"""Prepare a blind pairwise comparison, and decode the answer back to meaning.

    python Assets/Blender/_tools/judge.py mage000 --run 412 --cell 3        # brief
    python Assets/Blender/_tools/judge.py mage000 --run 412 --cell 3 \
        --answer B --margin 2 --suggestion "..."                            # record

Runs in SYSTEM Python. Does NOT call a model - it produces the brief a judge is given,
and decodes what the judge returns. Keeping the model call outside means the same
protocol works whether the judge is an agent, a second person, or you.

WHY THE FLIP IS DERIVED, NOT CHOSEN
-----------------------------------
Position bias is real and the standing mitigation is to flip A/B per pair. On the first
real run of this loop the flip was done BY HAND and not written down anywhere. A flip
that happens but is not recorded silently inverts the verdict, on the one instrument in
this project with a passing calibration probe behind it.

So the flip is derived from (seed, cell) - deterministic, reproducible from the record,
and impossible to forget. `--answer` is always in PRESENTATION terms (A or B, what the
judge actually saw) and is decoded here, once, into semantic terms (challenger /
incumbent / tie) before it reaches the record. A or B never enters attempts.jsonl.

WHAT THE JUDGE IS NOT TOLD
--------------------------
Which side is the incumbent. What changed. What the clauses were. What any previous
judge said. What the chips measured. The brief carries the character summary and nothing
else - no rubric, no checklist, no criteria. Two absolute scales collapsed on this
project when judges were given more structure, not less.

The one addition v3 makes is a SUGGESTION field, because a critique that cannot be
turned into the next row is unactionable prose. It is asked for last, after the verdict,
so it cannot become the thing the judge is optimising.
"""

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import record as _record                              # noqa: E402

PREVIEW_ROOT = _record.PREVIEW_ROOT


def flip_for(seed, cell, vs="incumbent", judge=""):
    """Deterministic A/B order for one pair. True == challenger is shown as B.

    Hashed over (seed, cell, vs, judge), not (seed, cell) alone. With only the first two
    every judge on a panel sees the same cell in the SAME orientation, so position bias
    adds across the panel instead of cancelling - on the one instrument here with a
    passing calibration probe behind it. Including the judge id and the comparison axis
    decorrelates them while staying fully reproducible from the record.
    """
    h = hashlib.sha256(("%s:%s:%s:%s" % (seed, cell, vs, judge)).encode()).digest()
    return bool(h[0] & 1)


def decode(answer, flipped):
    """Presentation answer (A/B/TIE) -> semantic side (challenger/incumbent/tie)."""
    a = (answer or "").strip().upper()
    if a in ("TIE", "T", "0", ""):
        return "tie"
    if a not in ("A", "B"):
        raise SystemExit("answer must be A, B or TIE, not %r" % answer)
    challenger_is_b = flipped
    if a == "B":
        return "challenger" if challenger_is_b else "incumbent"
    return "incumbent" if challenger_is_b else "challenger"


def _sheet(asset, run, cell, root=None):
    m = _record.manifest_for(asset, run, root)
    if not m:
        raise SystemExit("no manifest for run %s" % run)
    v = next((x for x in m.get("variants", []) if x["n"] == int(cell)), None)
    if not v:
        raise SystemExit("run %s has no cell %s" % (run, cell))
    if not v.get("sheet"):
        raise SystemExit(
            "cell %s has no contact sheet. A judge given six loose PNGs is the "
            "mismatched-pair failure the sheet exists to prevent - re-render the wave "
            "through axis.py so preview.py composites one." % cell)
    return os.path.join(root or PREVIEW_ROOT, asset, "run-%03d" % int(run),
                        v["sheet"]), v, m


def brief(asset, run, cell, summary, incumbent=None, root=None, vs="incumbent",
          design=None, judge=""):
    """The blind brief for one comparison, plus the flip needed to decode it."""
    cand_path, cell_rec, man = _sheet(asset, run, cell, root)

    if vs == "origin":
        # `origin` must SELECT the design's first wave, not merely label a verdict. It
        # was free text, so `--vs origin --incumbent <anything>` wrote a moving-incumbent
        # result into the ratchet series and trajectory() reported it as progress. The
        # ratchet is the only series that answers "is this going anywhere"; it cannot be
        # populated by whatever happened to be on the command line.
        if incumbent:
            raise SystemExit("--incumbent cannot be combined with --vs origin: the "
                             "origin is the design's first wave, not a choice")
        if not design:
            raise SystemExit("--vs origin needs --design to find the design's first wave")
        o, warn = _record.origin_of(asset, design, run, root)
        if not o:
            raise SystemExit(warn)
        if warn:
            # Reported, never absorbed. A ratchet that silently folds in a script change
            # is worse than no ratchet, because it reads as evidence.
            print("WARNING: %s" % warn, file=sys.stderr)
        inc_run, inc_cell = o
    elif incumbent:
        inc_run, inc_cell = incumbent
    else:
        c = _record.champion(asset, root)
        if c:
            inc_run, inc_cell = c["run"], c["cell"]
        else:
            # No champion yet: axis.py always emits the all-clauses-off cell first, so
            # cell 1 of this same wave is the in-wave baseline.
            inc_run, inc_cell = run, 1
    inc_path, _, inc_man = _sheet(asset, inc_run, inc_cell, root)

    if os.path.abspath(inc_path) == os.path.abspath(cand_path):
        raise SystemExit("cell %s is the incumbent; there is nothing to compare" % cell)

    # SAME DRAW, OR NO COMPARISON.
    #
    # The brief tells the judge that the only difference between the two sheets is the
    # model. That is true only when both were rendered under the same orbit draw - and a
    # reference from an earlier wave carries its own seed, so from wave two onward this
    # silently became a comparison of cameras presented as a controlled one. Caught by
    # review after it had already produced a reported result.
    if inc_man.get("seed") != man.get("seed"):
        raise SystemExit(
            "run %s was drawn under seed %s and run %s under seed %s. Judging them "
            "against each other compares two cameras, not two models, while the brief "
            "claims otherwise. Re-render the reference inside this wave's draw - give "
            "axis.py the reference's own clauses as a cell - and compare that."
            % (run, man.get("seed"), inc_run, inc_man.get("seed")))

    flipped = flip_for(man.get("seed"), cell, vs, judge)
    a_path, b_path = (inc_path, cand_path) if flipped else (cand_path, inc_path)

    text = """You are judging two renders of the same 3D character.

WHAT THE CHARACTER IS MEANT TO BE:
%s

Each image is a contact sheet: the SAME model photographed from six camera bearings
spaced evenly around it, at varying heights. Both sheets use an identical camera draw,
so the only difference between them is the model.

IMAGE A: %s
IMAGE B: %s

Look at both. Do not read any other file.

Judge on your own taste. There is no rulebook and no checklist - do not ask for one and
do not go looking. Do not reason about pixel sizes, icons, or how large this will appear
anywhere: its final rendered size is unknown and may change drastically.

Return, in this order:
  PREFER:     A, B or TIE
  MARGIN:     0-3   (0 = you genuinely cannot separate them, 3 = decisively better)
  WORKS:      one sentence on what the preferred one gets right
  PROBLEMS:   one sentence on what still holds it back
  SUGGESTION: the single most valuable change someone could make next, stated as an
              observable outcome rather than as a parameter to set
""" % (summary.strip(), a_path, b_path)

    return {"text": text, "flip": flipped, "cell": cell, "run": run,
            "seed": man.get("seed"), "a": a_path, "b": b_path,
            "incumbent": [inc_run, inc_cell], "label": cell_rec.get("label"),
            "vs": vs}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("asset")
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--cell", type=int, required=True)
    ap.add_argument("--summary", default="", help="character summary; or --summary-file")
    ap.add_argument("--summary-file")
    ap.add_argument("--incumbent", help="RUN:CELL to compare against (default: champion)")
    ap.add_argument("--vs", choices=["incumbent", "origin"], default="incumbent")
    ap.add_argument("--answer", help="what the judge returned: A, B or TIE")
    ap.add_argument("--margin", type=int, default=0)
    ap.add_argument("--suggestion", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--judge", default="")
    ap.add_argument("--design", help="required with --vs origin")
    ap.add_argument("--root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    summary = a.summary
    if a.summary_file:
        with open(a.summary_file, encoding="utf-8") as fh:
            summary = fh.read()

    inc = None
    if a.incumbent:
        r, c = a.incumbent.split(":")
        inc = (int(r), int(c))

    b = brief(a.asset, a.run, a.cell, summary or "(no summary supplied)", inc, a.root,
              a.vs, a.design, a.judge)

    if a.answer is None:
        print(json.dumps(b, indent=1) if a.json else b["text"])
        return 0

    prefer = decode(a.answer, b["flip"])
    # A tie means the judge could not separate the two images, so its "most valuable
    # change" is about neither model in particular. Recording it would hand a directive
    # full authority on the strength of a non-verdict.
    suggestion = "" if a.margin == 0 else a.suggestion
    _record.record_verdict(a.asset, a.run, a.cell, prefer, a.margin, a.vs,
                           a.note, suggestion, int(b["flip"]), a.judge, a.root,
                           against=b["incumbent"], seed=b["seed"])
    print("cell %d (%s) shown as %s -> %s %+d  [vs %s]"
          % (a.cell, b["label"], "B" if b["flip"] else "A", prefer, a.margin, a.vs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
