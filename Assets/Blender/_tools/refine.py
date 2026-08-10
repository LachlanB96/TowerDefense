"""Turn judged verdicts into the next move: refine, redesign, or abandon.

    python Assets/Blender/_tools/refine.py mage000 --design d01          # the packet
    python Assets/Blender/_tools/refine.py mage000 --design d01 --policy # just the call

Runs in SYSTEM Python. Reads attempts.jsonl and emits the brief a maker consumes.

WHY THIS EXISTS — a regression being repaired
---------------------------------------------
v2 had a real critique -> build -> re-judge cycle: the orchestrator synthesised its three
verifier reports into one, marked points raised by two or more judges as [CONSENSUS] and
single-judge points as [SUGGESTION], passed at most the three highest-impact ones back
down, and RESUMED THE SAME MODELLER so it kept its knowledge of the design and the file.

v3 collapsed five tiers into one maker, and that feedback wiring went out with the
orchestrator. It should not have. The fleet was bad because several agents edited one
3,216-line script at once and re-derived their world at every context boundary - NOT
because critique was fed back. One maker can consume its own judges perfectly well; that
needs no extra tier. The two were in the same box and both got thrown out.

WHAT IS DETERMINISTIC HERE, AND WHAT IS NOT
-------------------------------------------
Deterministic, in this file: the POLICY (refine / redesign / abandon) computed from the
margin trajectory, and the assembly of the packet.

Not deterministic, and deliberately left to the maker: synthesising several judges' prose
into ranked points. That is a language task and pretending otherwise with keyword
matching would produce confident nonsense. What this file guarantees is that the maker
receives every suggestion, in the judges' own words, with agreement counted by how many
judges spoke - never a paraphrase, and never a silent drop.

THE MEASUREMENT PROBLEM, STATED HONESTLY
----------------------------------------
There is no score - two absolute scales collapsed on this project before the pairwise
comparator survived a calibration probe. So "did the suggestion help?" is not directly
answerable, and the naive answer is wrong: a run of +1s against a MOVING incumbent means
only that each step beat the step before it. A design can walk in circles while every
individual comparison looks like a win.

Progress is `vs origin` - judged against the design's first baseline, which never moves.
Every policy decision below reads that series and not the other one.

Under modev4 there are no separate origin verdicts: the incumbent is the baked script
and send-backs never bake, so within one script_sha era the vs-incumbent series is the
ratchet, and stall/abandon read only the trailing era. Origin verdicts, where they
exist (v3 data), still take precedence.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import record as _record                              # noqa: E402

# --- policy thresholds -------------------------------------------------------------
# ALL FOUR ARE GUESSES. They are stated here as named constants precisely so they can be
# argued with and tuned from data, rather than buried in a branch. v2's equivalents were
# "four consecutive attempts below the design's first score" plus a report-at-attempt-8
# safety valve; neither was ever tuned from outcomes either.
GRACE_ATTEMPTS = 2      # attempts before any policy can abandon: an idea deserves a build
STALL_ROUNDS = 3        # consecutive attempts failing to beat the design's best vs-origin
ABANDON_AT = -2         # vs-origin this bad, after grace, means the IDEA is wrong
REPORT_AT = 8           # never auto-kill past here; hand it to the user instead


def _by_attempt(asset, design, root=None):
    """Per-attempt best signed margin, separately vs incumbent and vs origin."""
    rows = _record.read_attempts(asset, root)
    waves = {a["run"]: a for a in rows
             if a.get("kind") == "wave" and a.get("design") == design}
    per = {}
    for r in rows:
        if r.get("kind") != "verdict" or r.get("run") not in waves:
            continue
        # Only real judges move policy. A synthetic verdict exists to exercise plumbing
        # and must never reach a decision; records written before `source` existed are
        # treated as real, which is the conservative reading for historical lines.
        if r.get("source", "judge") != "judge":
            continue
        w = waves[r["run"]]
        n = w["attempt"]
        signed = 0 if r["prefer"] == "tie" else (
            r["margin"] if r["prefer"] == "challenger" else -r["margin"])
        slot = per.setdefault(n, {"attempt": n, "run": r["run"],
                                  "script_sha": w.get("script_sha"),
                                  "incumbent": [], "origin": [], "suggestions": []})
        slot[r["vs"]].append(signed)
        if r.get("suggestion"):
            slot["suggestions"].append({"cell": r["cell"], "vs": r["vs"],
                                        "margin": signed,
                                        "text": r["suggestion"],
                                        "judge": r.get("judge", "")})
    out = []
    for n in sorted(per):
        s = per[n]
        # Best cell in the wave is what the design is judged on: a wave offers several
        # candidates and the design's progress is its best one, not its average.
        s["best_incumbent"] = max(s["incumbent"]) if s["incumbent"] else None
        s["best_origin"] = max(s["origin"]) if s["origin"] else None
        out.append(s)
    return out


def _ratchet_series(hist):
    """(series, era_len, mode) — the numbers policy() decides from.

    v3 recorded explicit vs-origin verdicts; when any exist they remain the
    ratchet ("origin" mode, exactly the old behaviour). v4 records only
    vs-incumbent verdicts: send-backs never bake, so within one script_sha era
    the incumbent is FIXED and the incumbent series IS the ratchet. A bake
    (any design's) changes the sha and ends the era; margins from different
    eras measure against different baselines, so stall/abandon read only the
    TRAILING era ("incumbent-era" mode). record.eras() is the tested statement
    of the same grouping.
    """
    origin = [h["best_origin"] for h in hist if h["best_origin"] is not None]
    if origin:
        return origin, len(hist), "origin"
    cur = hist[-1]["script_sha"] if hist else None
    era = []
    for h in reversed(hist):
        if h["script_sha"] != cur:
            break
        era.append(h)
    era.reverse()
    series = [h["best_incumbent"] for h in era if h["best_incumbent"] is not None]
    return series, len(era), "incumbent-era"


def policy(hist):
    """refine | redesign | abandon | report, from the ratchet series.

    Attempt count for report-at-8 spans the design's whole life; grace, abandon
    and stall evaluate within the current era — see _ratchet_series.
    """
    if not hist:
        return {"call": "refine", "why": "no attempts judged yet"}

    n_total = len(hist)
    series, n_era, mode = _ratchet_series(hist)

    if n_total >= REPORT_AT:
        return {"call": "report",
                "why": "attempt %d. Past this point the decision is the user's, not a "
                       "rule's - the rule exists to stop a design running forever, not "
                       "to kill one the user still wants." % n_total}

    if not series:
        return {"call": "refine",
                "why": "no judged comparison yet%s - convene a panel on the newest wave "
                       "before building again, or progress is unmeasurable"
                       % (" in the current script era" if mode == "incumbent-era" else "")}

    latest, best = series[-1], max(series)

    if n_era <= GRACE_ATTEMPTS:
        return {"call": "refine",
                "why": "attempt %d of the current era is within the grace window; an "
                       "idea gets a real build before any policy can kill it" % n_era}

    if latest <= ABANDON_AT:
        return {"call": "abandon",
                "why": "ratchet %+d after %d judged attempts this era. That is the panel "
                       "saying the IDEA is wrong rather than the execution - refining it "
                       "spends renders on a premise nobody is buying." % (latest, n_era)}

    # Stall: several consecutive attempts, none beating the design's own best.
    since = 0
    for v in reversed(series):
        if v >= best:
            break
        since += 1
    if since >= STALL_ROUNDS:
        return {"call": "redesign",
                "why": "%d consecutive attempts have failed to beat this design's best "
                       "ratchet margin (%+d) in the current era. The feedback has "
                       "stopped being actionable; take what landed and open a new "
                       "design rather than grinding this one." % (since, best)}

    if latest >= best and latest > 0:
        return {"call": "refine",
                "why": "ratchet %+d, the design's best this era. It is still climbing - "
                       "carry the critique forward." % latest}

    return {"call": "refine",
            "why": "ratchet %+d against a best of %+d this era. Oscillating but not "
                   "stalled; a design that wobbles is still learning something."
                   % (latest, best)}


def packet(asset, design, root=None):
    hist = _by_attempt(asset, design, root)
    p = policy(hist)
    latest = hist[-1] if hist else None
    return {
        "asset": asset, "design": design,
        "attempts": len(hist),
        "trajectory": [{"attempt": h["attempt"], "run": h["run"],
                        "vs_incumbent": h["best_incumbent"],
                        "vs_origin": h["best_origin"]} for h in hist],
        "policy": p,
        # Every suggestion, verbatim, with how many judges spoke this round. Counting is
        # deterministic; deciding which points AGREE is a language task and is left to
        # the maker rather than faked with keyword matching.
        "judges_this_round": len(latest["suggestions"]) if latest else 0,
        "suggestions": latest["suggestions"] if latest else [],
    }


def brief(pk):
    """The text a maker acts on."""
    p = pk["policy"]
    L = ["DESIGN %s - attempt %d" % (pk["design"], pk["attempts"] + 1),
         "POLICY: %s" % p["call"].upper(), "  %s" % p["why"], ""]

    if pk["trajectory"]:
        L.append("TRAJECTORY (vs origin is the ratchet; vs incumbent only says each step")
        L.append("beat the one before it, which a design walking in circles also does):")
        for t in pk["trajectory"]:
            L.append("  attempt %-2d  vs incumbent %-5s  vs origin %-5s"
                     % (t["attempt"],
                        "-" if t["vs_incumbent"] is None else "%+d" % t["vs_incumbent"],
                        "-" if t["vs_origin"] is None else "%+d" % t["vs_origin"]))
        L.append("")

    if p["call"] == "abandon":
        L += ["Do not refine this. Record what was learned and open a new design.", ""]
        return "\n".join(L)
    if p["call"] == "redesign":
        L += ["Keep whatever landed. Open a NEW design rather than another attempt at "
              "this one.", ""]
        return "\n".join(L)
    if p["call"] == "report":
        L += ["Stop and ask the user whether to continue.", ""]
        return "\n".join(L)

    L.append("WHAT THE JUDGES SAID - %d judge(s) this round, verbatim and unranked:"
             % pk["judges_this_round"])
    for s in pk["suggestions"]:
        L.append("  [cell %s, %+d vs %s] %s" % (s["cell"], s["margin"], s["vs"], s["text"]))
    L += ["",
          "YOUR JOB:",
          "  1. Read them together. A point raised by two or more judges is CONSENSUS and",
          "     outranks one raised by a single judge.",
          "  2. Take AT MOST THE THREE highest-impact points. v2 measured 6.8 mandatory",
          "     blockers per attempt against a brief that said make one change; that is",
          "     incoherent and it is most of why designs stalled. Everything else is logged,",
          "     not built.",
          "  3. Turn them into a row spec: named clauses over real genes. Check the names",
          "     with `genes.py <asset> --find <substring>` before writing them.",
          "  4. You may CONTEST a point with a measurement. Judges see images and cannot",
          "     inspect the model; five modellers contested a unanimous instruction with",
          "     data and all five were right. Contest on a measurement, never on opinion.",
          "  5. Do not act on a suggestion that would break a character invariant. Say so",
          "     and do something better.",
          ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("asset")
    ap.add_argument("--design", required=True)
    ap.add_argument("--root")
    ap.add_argument("--policy", action="store_true", help="print only the call")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    pk = packet(a.asset, a.design, a.root)
    if a.json:
        print(json.dumps(pk, indent=1))
    elif a.policy:
        print("%s: %s" % (pk["policy"]["call"], pk["policy"]["why"]))
    else:
        print(brief(pk))
    return 0


if __name__ == "__main__":
    sys.exit(main())
