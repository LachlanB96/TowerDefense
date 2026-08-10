"""The durable record: attempts, verdicts, champion. Append-only.

    python Assets/Blender/_tools/record.py mage000 --open   --run 412 --design d01
    python Assets/Blender/_tools/record.py mage000 --verdict --run 412 --cell 3 \
        --prefer challenger --margin 2 --note "..." --suggestion "..."
    python Assets/Blender/_tools/record.py mage000 --promote --run 412 --cell 3
    python Assets/Blender/_tools/record.py mage000 --show

Runs in SYSTEM Python.

WHY THIS EXISTS
---------------
The first real run of the v3 loop produced no record of any kind. Renders landed, chips
ran, three judges returned verdicts - and none of it was written anywhere. That is the
same failure the old pipeline had at scale: 114 of 123 logged attempts recorded no view
information and not one recorded a margin, which made every claim about judging quality
unfalsifiable, including the claims made in its defence.

Two files, both small, both append-only where it matters:

  attempts.jsonl   one line per judged cell. Never rewritten.
  champion.json    the current incumbent. Rewritten, but every promotion is also an
                   attempts.jsonl line, so the history survives.

MEASURING PROGRESS IN A PAIRWISE SYSTEM
---------------------------------------
There is no score here, by design - two absolute scales collapsed on this project before
the pairwise comparator survived a calibration probe. So "did it get better" needs care:

  margin_vs_incumbent  decides acceptance. It is NOT a progress measure: each attempt is
                       judged against a different, moving incumbent, so a run of +2s says
                       only that each step beat the step before it.
  margin_vs_origin     judged against the design's FIRST baseline, which never moves.
                       This is the ratchet. It is the number that answers "is this design
                       actually going anywhere", and it is the one to watch across a
                       refinement chain.

A design whose margin_vs_incumbent keeps reading +1 while margin_vs_origin stays flat is
walking in circles, and only the second number can tell you.
"""

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEW_ROOT = os.path.join(os.path.dirname(HERE), "_previews~")


def _paths(asset, root=None):
    a = os.path.join(root or PREVIEW_ROOT, asset)
    return (os.path.join(a, "attempts.jsonl"), os.path.join(a, "champion.json"))


def _append(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Append-only, one JSON object per line: a crash can lose at most the line being
    # written, and nothing that already landed can be silently rewritten later.
    with open(path, "a", encoding="utf-8") as fh:     # utf-8: Windows defaults cp1252
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_attempts(asset, root=None):
    p, _ = _paths(asset, root)
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue                              # a torn final line is not fatal
    return out


def champion(asset, root=None):
    _, p = _paths(asset, root)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def manifest_for(asset, run, root=None):
    p = os.path.join(root or PREVIEW_ROOT, asset, "run-%03d" % int(run), "manifest.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def open_attempt(asset, run, design, attempt=None, note="", root=None):
    """Record that a wave was rendered, before anything judges it.

    Opened from the manifest rather than from arguments, so the record cannot disagree
    with what was actually built: seed, wave draw, per-cell labels, clauses and chips all
    come off disk. An attempt that dies before judging still leaves this line, which is
    what makes an abandoned wave visible instead of merely absent.
    """
    m = manifest_for(asset, run, root)
    if not m:
        raise SystemExit("no manifest for run %s" % run)
    prior = [a for a in read_attempts(asset, root)
             if a.get("design") == design and a.get("kind") == "wave"]
    rec = {
        "kind": "wave",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "asset": asset,
        "design": design,
        "attempt": int(attempt) if attempt else len(prior) + 1,
        "run": int(run),
        "tag": m.get("tag"),
        "seed": m.get("seed"),
        "script_sha": m.get("script_sha"),
        "draw": (m.get("wave") or {}).get("draw"),
        "note": note,
        "cells": [{"n": v["n"], "label": v.get("label"), "clauses": v.get("clauses"),
                   "sheet": v.get("sheet"), "exit": v.get("exit"),
                   "chips": [c["chip"] for c in (v.get("chips") or [])]}
                  for v in m.get("variants", [])],
    }
    p, _ = _paths(asset, root)
    _append(p, rec)
    return rec


def origin_of(asset, design, run, root=None):
    """Where the design's origin lives, expressed inside THIS wave's draw.

    Cell 1 of every wave is the all-clauses-off baseline, so while the asset script is
    unchanged it reproduces the design's origin geometry - and it does so under the
    current wave's own camera draw, which is the only way the comparison is controlled.
    So the origin for run N is (N, 1), not the first wave's cell 1.

    That equivalence holds only while the script is the same. The first wave's
    `script_sha` is compared against this one's and a change is reported rather than
    absorbed: comparing a new script's cell 1 to an old one's would measure the script
    change and call it design progress.
    """
    waves = [a for a in read_attempts(asset, root)
             if a.get("kind") == "wave" and a.get("design") == design]
    if not waves:
        return None, "no recorded wave for design %s" % design
    first = min(waves, key=lambda w: w.get("attempt", 0))
    here = next((w for w in waves if w.get("run") == int(run)), None)
    warn = None
    if here and first.get("script_sha") and here.get("script_sha") \
            and first["script_sha"] != here["script_sha"]:
        warn = ("the asset script changed since attempt 1 (%s -> %s), so cell 1 no longer "
                "reproduces the design's original geometry. The ratchet is measuring the "
                "script change as well as the design."
                % (first["script_sha"], here["script_sha"]))
    return (int(run), 1), warn


def record_verdict(asset, run, cell, prefer, margin, vs="incumbent", note="",
                   suggestion="", flip=None, judge="", root=None, source="judge",
                   against=None, seed=None):
    """One judged comparison.

    `prefer` is normalised to the SEMANTIC side (challenger / incumbent / tie), never to
    the presentation side (A / B). A hand-flipped pair whose flip was not recorded
    inverts the verdict on the one instrument with a passing calibration probe behind it,
    so the decode happens once, here, and A/B never reaches the record.
    """
    if prefer not in ("challenger", "incumbent", "tie"):
        raise SystemExit("prefer must be challenger|incumbent|tie, not %r" % prefer)
    if source not in ("judge", "synthetic", "user"):
        raise SystemExit("source must be judge|synthetic|user, not %r" % source)
    if source == "judge" and not judge:
        raise SystemExit(
            "a real verdict must name its judge (--judge). An unattributed verdict is "
            "indistinguishable from a fabricated one, and this record has already been "
            "contaminated once by a synthetic verdict nobody could later identify.")
    rec = {
        "kind": "verdict",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "asset": asset, "run": int(run), "cell": int(cell),
        "vs": vs,                                     # "incumbent" or "origin"
        "prefer": prefer, "margin": int(margin),
        "flip": flip, "judge": judge,
        # WHAT THIS WAS COMPARED AGAINST, and under which draw. A verdict that does not
        # name its counterpart cannot be re-checked once champion.json moves, and a
        # verdict whose two sides came from different orbit draws is not a comparison of
        # models at all - it is a comparison of cameras wearing a model's name.
        "against": against, "seed": seed,
        # WHO PRODUCED THIS. Caught by dogfooding: a synthetic verdict was written to
        # exercise the plumbing, a real judge later returned the OPPOSITE, and nothing on
        # disk distinguished the two. That is the same provenance failure that once
        # halted this project on an instruction attributed to a user who never sent it.
        # Anything not from a real judge must say so, and refine.py ignores it.
        "source": source,
        "note": note,
        # The judge's single most valuable next move, in its own words. This is what a
        # refinement round consumes; without it a critique is unactionable prose.
        "suggestion": suggestion,
    }
    p, _ = _paths(asset, root)
    _append(p, rec)
    return rec


def promote(asset, run, cell, by="user", quote="", root=None):
    """Make a cell the incumbent. Only ever called for a human decision."""
    m = manifest_for(asset, run, root)
    if not m:
        raise SystemExit("no manifest for run %s" % run)
    v = next((x for x in m.get("variants", []) if x["n"] == int(cell)), None)
    if not v:
        raise SystemExit("run %s has no cell %s" % (run, cell))
    rec = {"asset": asset, "run": int(run), "cell": int(cell),
           "label": v.get("label"), "clauses": v.get("clauses"),
           "seed": m.get("seed"), "sheet": v.get("sheet"),
           "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": by, "quote": quote}
    ap, cp = _paths(asset, root)
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(cp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    _append(ap, dict(rec, kind="promotion"))
    return rec


def trajectory(asset, design, root=None):
    """Per-attempt margins for one design, both against the incumbent and the origin.

    The pair of series is the point. Rising `vs_incumbent` with flat `vs_origin` is a
    design going nowhere while every individual step looks like a win.
    """
    rows = read_attempts(asset, root)
    waves = {a["run"]: a for a in rows if a.get("kind") == "wave"
             and a.get("design") == design}
    out = []
    for r in rows:
        if r.get("kind") != "verdict" or r.get("run") not in waves:
            continue
        w = waves[r["run"]]
        signed = 0 if r["prefer"] == "tie" else (
            r["margin"] if r["prefer"] == "challenger" else -r["margin"])
        out.append({"attempt": w["attempt"], "run": r["run"], "cell": r["cell"],
                    "vs": r["vs"], "signed_margin": signed,
                    "suggestion": r.get("suggestion", "")})
    out.sort(key=lambda x: (x["attempt"], x["vs"]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("asset")
    ap.add_argument("--root")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--verdict", action="store_true")
    ap.add_argument("--promote", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--trajectory", metavar="DESIGN")
    ap.add_argument("--run", type=int)
    ap.add_argument("--cell", type=int)
    ap.add_argument("--design", default="d01")
    ap.add_argument("--attempt", type=int)
    ap.add_argument("--prefer", choices=["challenger", "incumbent", "tie"])
    ap.add_argument("--margin", type=int, default=0)
    ap.add_argument("--vs", choices=["incumbent", "origin"], default="incumbent")
    ap.add_argument("--flip", type=int)
    ap.add_argument("--judge", default="")
    ap.add_argument("--source", choices=["judge", "synthetic", "user"], default="judge",
                    help="synthetic marks a plumbing test; refine.py ignores those")
    ap.add_argument("--note", default="")
    ap.add_argument("--suggestion", default="")
    ap.add_argument("--by", default="user")
    a = ap.parse_args()

    if a.open:
        r = open_attempt(a.asset, a.run, a.design, a.attempt, a.note, a.root)
        print("wave %s attempt %d recorded (%d cells)"
              % (r["design"], r["attempt"], len(r["cells"])))
    elif a.verdict:
        r = record_verdict(a.asset, a.run, a.cell, a.prefer, a.margin, a.vs,
                           a.note, a.suggestion, a.flip, a.judge, a.root, a.source)
        print("verdict vs %s: %s %+d" % (r["vs"], r["prefer"], r["margin"]))
    elif a.promote:
        r = promote(a.asset, a.run, a.cell, a.by, a.note, a.root)
        print("champion -> run %d cell %d (%s)" % (r["run"], r["cell"], r["label"]))
    elif a.trajectory:
        for t in trajectory(a.asset, a.trajectory, a.root):
            print("  attempt %d  run %-4d cell %-2d  vs %-9s %+d   %s"
                  % (t["attempt"], t["run"], t["cell"], t["vs"],
                     t["signed_margin"], t["suggestion"][:60]))
    else:
        c = champion(a.asset, a.root)
        rows = read_attempts(a.asset, a.root)
        print("champion: %s" % (("run %d cell %d - %s (by %s)"
                                 % (c["run"], c["cell"], c["label"], c["by"]))
                                if c else "none yet"))
        print("attempts.jsonl: %d records (%d waves, %d verdicts, %d promotions)"
              % (len(rows),
                 sum(1 for r in rows if r.get("kind") == "wave"),
                 sum(1 for r in rows if r.get("kind") == "verdict"),
                 sum(1 for r in rows if r.get("kind") == "promotion")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
