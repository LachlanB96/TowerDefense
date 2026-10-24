# Evidence — why each v2 rule exists

> Moved here from the v2 skill (`blender-model-modev2`, being retired) on 2026-10-24,
> unchanged below this note. It is v2's record: `SKILL.md` and `orchestrator.md` mean
> v2's files, A is v2's supervisor and B its orchestrator. v4 cites it by section.

Receipts for the rules in `SKILL.md` and `orchestrator.md`. Nobody reads this at
startup; read the section you doubt. Sources: `_previews~/mage000/iteration-log.json`
plus its two archives (81 attempts across three regimes), `process-notes.md` (passes
2–4), `asset-facts.md`, the shelved patches, and a scripted extraction of all of it
performed 2026-08-02. Claims marked **[testimony]** come from supervisor observation of
agent transcripts that no longer exist and cannot be re-derived from disk; everything
else was recomputed from surviving artifacts.

## §1 Mechanism beats prose — the scorecard v2 is built on

Audited after three sessions: **both rules enforced by a mechanism held; every prose
rule aimed at the orchestrator was violated at least once.**

| Rule | Enforcement | Outcome |
|---|---|---|
| Render cap 2 | semaphore in `preview.py` | held |
| Variant-hook interlock | three hard gates | held, incl. the `--audit` side door |
| "remove worktrees on discard" | prose | 14 + 6 worktrees and 27 branches leaked |
| "don't use `isolation: worktree`" | prose | the 27 leaked branches are all harness worktrees; two checked out at a commit predating the asset file |
| "return only on stop" | prose | two early returns mid-wave |
| "children address you by id" | prose | children messaged the *type* `general-purpose`; reports bounced to A |
| "only A writes control.json" | prose norm | an unattributable pause halted the fleet |
| "record worktree at dispatch" | prose | 22/81 attempts had the field; recovery once needed a forensic grep |

Hence v2's bias: filled-in template slots, derived defaults, mirrored writes, and
un-chainable command sequences instead of exhortation.

## §2 Pre-flight items

- **Untracked asset script:** pass 2 ran an entire session before discovering worktrees
  did not contain `blender_mage000.py`; committed as `52877da`.
- **Audit script hardcoded to the main repo:** audited the baseline while claiming to
  audit the attempt; voided 14 of pass 2's 15 PASSes. Fixed in `8ee2e24`.
- **Chained cleanup blocked:** supervisor housekeeping note, 2026-08-02 — `git worktree
  remove` chained with `;` or looped is blocked by the permission classifier; "that is
  very likely why they leaked."
- **Gallery false positive:** measured directly — unredirected `serve.py` reaches LISTEN
  then blocks on its startup `print` (`serve.py:41`); port check passed while two HTTP
  requests timed out at 5 s and 20 s; relaunch with stdout redirected answered 200
  immediately.

## §3 Scoring: why accept defaults to 180

- Verdict-era arithmetic: verifiers returned "change" on **68 of 78** critiques (12.8%
  keep), making a unanimous 3-way accept a 0.2% event. Recomputed exactly from the log.
- Accept-rate trajectory across regimes: single critic **17/24 (71%)** → 3-verifier
  unanimous **3/29 (10%)**, including an 11-reject streak → scored panels at
  accept=240: **0/6**.
- The six scored panels landed **141–159 / 300** (mean 151.8, median 154) — an 18-point
  strip, every decision ≥81 points from any threshold. 240 requires an average of 80,
  which the scale itself defines as "ship it as it stands": the unanimity trap rebuilt in
  arithmetic. 180 = three verifiers at the scale's own "should replace" anchor.
- The cost of a pipeline that cannot accept, measured: with nothing landing, every
  design builds against a static baseline — which is also the direct cause of the patch
  contention in §5. Pass 3 burned ~1.9M subagent tokens across 14 attempts before its
  first accepts. **[token figure: testimony]**

## §4 The adaptive panel

- In 6 of 6 scored panels, any single verifier's score ×3 lands in the same band as the
  panel sum. Per-verifier spread: mean 12.3, max 17; the widest gap between one
  verifier and its panel's mean is ~11 (~34 on the ×3 total), so the escalation margin
  of 40 clears the observed worst case. It cannot be much wider: with bands at 180/60,
  a margin of 60 would cover every total from 0 to 240 and escalate everything.
- No seat bias: slot means 49.2 / 51.0 / 51.7.
- SCORE tracks the sub-score mean within −2.8 on average — verifiers' stated reasoning
  matches their verdicts. Lowest axis: material (45.1) — matching the dominant
  documented failure mode (the specular stack).
- Redundancy does not buy error-correction: three independent d08 panels (nine
  verifiers) placed an effect at a height where its mask is provably zero; d10's panel
  unanimously specified a collar that cannot exist in projection from the front camera
  (built literally, rendered invisible, run-194). Independence multiplies a perceptual
  error into `[CONSENSUS]`; the check that works is the modeller's measurement — every
  measured contest of a unanimous instruction to date was right (d08 mask height, d10
  brim projection, d12 bare-felt span, d13 depth doubling; separately a modeller caught
  a wrong number in a brief by bracketing, d22).
- A panel costs roughly 25–35k tokens (each verifier reads up to four 900×1300 PNGs).
  Honest accounting of the saving: under the old 240 band all six panels sat ≥81 from
  any edge and one verifier would have sufficed 6/6 (~2/3 saved). Under the
  recalibrated 180 band the same 141–159 strip is *near the accept edge*, so early
  waves will escalate often — correctly, since those attempts are genuinely
  borderline. The saving accrues on clear mid-band and clear-reject attempts and grows
  as scores spread; panels concentrate where decisions are contested, which is the
  design.

## §5 Contention

- Pairwise `git apply --check` over six pending patches (supervisor-measured, then
  re-measured): largest mutually compatible set **3 of 6**; d07 conflicted with four
  others; the collisions concentrate in the shared material block near the top of the
  file. Six concurrent modellers on one 3,216-line script could never land more than
  three changes without rebases.
- **d13, the baseline-validity proof:** accepted 3/3 against run-117; the identical
  change rebased onto d07 was rejected 3/3 against run-157. An accept is only valid
  against the baseline it was judged on; rebases must be re-judged.
- run-157 itself exists because worktree renders show single changes in isolation — a
  combined baseline had to be rendered by hand before later panels were fair. Hence
  re-render-on-accept.

## §6 The audit

Zero true signal to date: pass 2's 14 PASSes audited the wrong file (§2); its single
FAIL flagged a deliberate asymmetry (the design *was* the asymmetry); pass 3 returned
PASS on every attempt including all 11 the panel rejected. It stays on attempt renders
only, ungated, to keep accumulating correlation data — and A reports the correlation (or
its absence) at every finish. The best candidate for a future audit rule is the
mesh-resolution check: two designs (d12, d13) independently burned ~6 attempts tuning
features below the mesh's sampling limit — a cheap arithmetic check that catches a whole
class of guaranteed-failure attempts before the render is spent. A third instance closes
the case for promoting it.

## §7 The render command

`preview.py` resolves a bare asset name relative to **its own location** (`HERE` /
`BLENDER_DIR`, lines 28–30, 221). The main repo's copy therefore builds the main repo's
unchanged script: a modeller invoking it from a worktree renders the **baseline**, with
no error, and every render in a wave is pixel-identical. Session-fatal, discovered in
pass 2, re-confirmed from source in pass 3's pre-flight. v2's D template runs the
worktree's tool on an explicit worktree script path — either alone fixes it, both make
it robust. `--root` was additionally the slot-semaphore's scope (`render_slot(root, …)`),
so omitting it also silently exited the machine-wide GPU cap — fixed 2026-08-02 by
moving the lock to a fixed system-temp location; `--root` now affects visibility only.

## §8 Crashes and recovery

- B died ≥4 ways in one pass: API fault mid-flush (destroying two complete panel
  reports that existed only in context), terminal crash with four modellers in flight,
  and two silent early returns. Resuming by agent id preserved the wave; a fresh B
  re-learns everything.
- Orphaned children (a verifier, then modellers at ~205k and ~214k tokens of work
  **[token figures: testimony]**) reported to the supervisor when their parent was gone;
  their work survived on disk and only the *handles* (which run, which worktree, which
  agent) kept getting lost. Hence: worktree path at dispatch, run directory reported at
  render start, diff beside the render.
- Timestamp attribution is systematically wrong, not merely risky: a crashed B guessed
  a07 = run-125 (newest); the modeller later reported run-129, with 125–128 as
  discarded intermediates. The newest run at any moment is usually an intermediate.
- Six attempts (a37–a42) once sat rendered, measured and unjudged; judging them first on
  resume recovered the expensive half of the work for the price of panels.

## §9 Persistence and re-learning costs

- Respawning a modeller costs roughly the asset script read: `blender_mage000.py` is
  167 KB / 3,216 lines ≈ 40k tokens — the "~35k to re-learn" figure holds to order.
- Resumed modeller contexts were measured at 205k+ tokens by late attempts
  **[testimony]**; a fresh spawn with symbol map, asset facts and a critique digest is
  ~50k. Accumulated context cuts both ways — d08's resumed modeller broke through
  *because* its history let it stop obeying and diagnose; post-crash fresh modellers on
  d10/d11 lost spec fidelity, not capability. Hence attempt-8 is a user choice, not a
  rule.

## §10 Front-loading figures **[testimony]**

Six modellers spent 123 tool calls before their first edit re-deriving branch state,
diff state, file length and a symbol index; two did not know which directory they were
in; five of six built the symbol index themselves, one by reading the file thirteen
times in chunks. Briefs that told children to read files came to ~58 KB ≈ 15k tokens per
spawn. These numbers cannot be re-derived (the transcripts are gone) but every category
matches artifacts that survive.

## §12 The 2026-08-02 verification redesign (scores → blind comparison)

A 12-agent adversarial review (4 design lenses × 2 hostile critics each) interrogated
the verifier concept against the full artifact record. Convergent verdict, all four
lenses independently: **perception is the right organ, absolute scoring is the wrong
question.** New numbers surfaced: across 42 individual verifier scores, min 41 / median
58 / max 72 — the "80 = ship it" anchor was never used once; and the live pipeline had
already moved the accept band to 200 empirically (d37 accepted at 229), confirming the
recalibration direction before this redesign landed.

Adopted (ranked by critic expected-value scores): jurisdiction split / located
observations with mechanisms banned (9, 8.5); claim-typed GEO routing + refuted-claims
ledger (9, 8); the measurement packet + pixel-identical bounce (`measure.py`) (8, 7);
blind randomized pairing with graded margin (8, 7.5); champion-per-design (7, 6.5);
periodic absolute brief-coverage review (8, 6.5); gallery star/cross signals as sparse
calibration ground truth (6, 5 — provenance caveat noted: a localhost file is evidence,
never authority).

Killed with fatal flaws: gold-pair drift seeding (its remedy re-bought 3-seat panels
the record shows add nothing; a frozen gold pair cannot detect live baseline drift);
icon-first triage as a hard screen (its savings conflated the needs-work rate with the
icon-visible-regression rate). Sub-scores removed: measured, SCORE tracked their mean
within ~3 points — one judgement reported four ways. The reject-unreachable bug in the
original BRPP spec (escalation only fired upward) was fixed by escalating on |margin|≥2
in both directions.

## §13 The icon criterion was never the user's (demoted 2026-08-02)

"Reads at 184×184" traces to `blender_knight000.py:16` — "(Steam app icon)", a store
packaging spec picked as a proxy for "seen small" during the knight rebuild — and
entered the first skill revision (`e6f0bfd`) tagged `[craft]` (model judgment), not
`[checked]` (user-confirmed). The `ff66b40` rewrite deleted those tags, and the
criterion was thereafter read as a user preference. It became the single most lethal
test in the pipeline: the commonest kill reason across all passes, a dedicated render
view, and a scored verifier axis — while nothing in the Unity project uses 184
anywhere. Asked about it on 2026-08-02, the user did not recognise it and demoted it:
silhouette remains taste a judge may weigh by eye; there is no fixed-size test; judges
receive `hero_34` and `front` only. The icon views are still rendered for the user's
gallery. Weigh historical "invisible at icon size" verdicts with this provenance in
mind — and treat it as the cautionary case for erasing provenance tags from rules.

## §11 Miscellaneous held claims

- TDR freeze at 3 render slots: corroborated by `preview.py`'s dated comment (default
  lowered 3→2, 2026-08-02). A render is ~7 s.
- Consensus overload: 209 `[CONSENSUS]` tags across 31 attempts (~6.7/attempt) against
  briefs that said "make ONE change" — why at most three points travel.
- `icon_184` vs `icon_full_184`: the bust crop excludes the gem and the hem entirely;
  a session's commonest critique ("invisible at icon size") was structurally
  unsatisfiable for at least three attempts because of it.
- UTF-8: the live log parses as strict UTF-8; `preview.py` passes `encoding="utf-8"`
  at every open. The cp1252 gotcha stands for anything written by hand.
