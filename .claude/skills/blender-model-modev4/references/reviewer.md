# Reviewers (modev4) — why the panel works the way it does

Reviewers never read this file: their entire brief is `judge.py` output plus two
closing lines (the return format, then `Subagents: start none.`), generated and
recorded by the asset's session (`SKILL.md`, "The panel" is the operating copy). This
file records why each constraint exists, so nobody "improves" one away.

## Fresh, blind, taste-only — each for a measured reason

- **Fresh every verdict, never resumed.** A resumed judge anchors on its own previous
  verdict and approves whatever it just asked for. Builders need continuity; judges
  need independence.
- **Blind.** The reviewer is not told which sheet is the incumbent, what changed, what
  the clauses were, what the chips measured, or what any other judge said. Nine
  verifiers once "found" a band at hip height because they were told to look for a
  band. The A/B flip is derived from `sha256(seed:cell:vs:judge)` — deterministic,
  recorded, impossible to forget; including the judge id decorrelates flips across a
  panel so position bias cancels instead of adding. `judge.py` decodes the answer
  once; A/B never enters the record.
- **Taste-only, margin 0–3.** Two absolute scales collapsed on this project (verdicts:
  "change" 68/78; scores: an 18-point strip with the "ship it" anchor never used).
  Blind pairwise preference with a graded margin is the only instrument that passed a
  calibration probe. **Do not regress it to scores, and do not add rubrics, checklists
  or criteria to the brief.**
- **SUGGESTION is asked last**, after the verdict, so it cannot become the thing the
  judge optimises. It must be an observable outcome, never a parameter — a judge
  cannot inspect the model, and panels have been unanimously wrong about mechanism.
- **No helpers.** A reviewer starts no subagent of its own: the session holds the
  cap (8 at once, all kinds together) by counting what it started, and a judge that
  delegated would also stop being one judgement. The closing line says so; it is
  logistics, not a criterion, so it does not break "no rubrics".
- **Spawned as slots allow.** A verdict's reviewers may start one at a time when the
  session is at its cap; they are independent and blind, so nothing is lost by it.
- **Same seed, or no comparison.** `judge.py` refuses a pair whose sheets come from
  different orbit draws — that would compare two cameras wearing a model's name. This
  is why the incumbent is always cell 1 of the challenger's own wave.

## The reviewers' three powers

They map exactly to the user's specification, with thresholds living in
`control.json` (`accept_margin`, `reject_margin`), never here:

| Panel outcome | Meaning |
|---|---|
| **accept** (2 fresh reviewers at ≥ `accept_margin`, or 2 of 3 after escalation) | the change is baked into the script and becomes the baseline — autonomous, by the user's explicit decision (2026-08-10). A `blocks_auto` chip downgrades this to **staged**, waiting for the user. |
| **send back** (margins in the −1..+1 band) | the same maker retries with every SUGGESTION verbatim via `refine.py`; at most three points are acted on. |
| **scrap** (2 at ≤ `reject_margin`) | the idea is wrong, not the execution; the design is shelved — kept, visible, resurrectable — never deleted. |

The user's directives (rework / revert / resurrect / `promote` in chat) outrank any
panel verdict, always.
