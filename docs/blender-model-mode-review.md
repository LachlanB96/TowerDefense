# Review — `/blender-model-mode`

Assignment: `docs/blender-model-mode-review-brief.md`. Output is a written review; no
pipeline file or `SKILL.md` was edited.

## Method and snapshot

All numbers below were computed from the artifacts, not read off the prose. Extraction was
Python with `encoding="utf-8"`; the 387 KB log was never loaded into context.

**The log is live.** `iteration-log.json` grew from 359 200 → 386 973 bytes while I was
reading it, and `heartbeat` advanced to `2026-08-02T18:16:55`. An orchestrator is running
right now. Every figure below is a snapshot at that heartbeat, and the four scored panels
in particular are the whole scoring dataset *as of now* — it will grow. I did not touch the
pipeline, the gallery or any render.

Sources: `iteration-log.json` (42 attempts, 20 designs), `iteration-log-archive.json` (24),
`iteration-log-archive-2.json` (15), `process-notes.md` (862 lines), `asset-facts.md`,
`control.json`, 224 run manifests, 908 PNGs, and read-only git.

---

## The three I would do first

1. **Make `preview.py` stamp its own provenance into the manifest.** Ten lines in a file
   that already exists replaces the pipeline's most-repeated failure — losing the handle to
   work that was already paid for. 11 of 42 attempts (26%) currently have no verdict; the
   last crash cost ~20 minutes of forensic grepping for a mapping that the render process
   knew for free. *(Robustness R1.)*
2. **Cap in-flight modellers at the measured merge capacity, not at 6.** The contention
   matrix in `process-notes.md:356-400` shows at most **3 of 6** pending patches can
   co-land. At a cap of 6, half of every wave is guaranteed rework before a panel ever sees
   it. This is the largest measured waste in the system. *(Economics E1.)*
3. **Make the panel adaptive: one verifier, escalate to three only near a band edge.** All
   four scored panels landed 141–159/300 — **≥ 81 points from either threshold**. Not one
   was close enough for verifiers 2 and 3 to have changed the outcome. ~58% of panel tokens
   for zero observed decision change. *(Economics E2.)*

---

## The headline finding: the decision rule has almost no data behind it

Questions 3–7 of the brief all assume a scored corpus. There isn't one yet.

| | count |
|---|---|
| attempts in the live log | 42 |
| attempts carrying **any** verifier score | **4** |
| verifier scores in existence | **12** |
| attempts carrying `total` | 0 (B computes it in `note`, doesn't store it) |
| designs carrying `scores[]` | 4 of 20 |

The other 77 critiques are from the previous regime and carry `stance: keep|change`, the
exact vocabulary `SKILL.md:123` bans. So the score bands, the `no_improvement_limit`
that reads `designs[].scores`, the `report_at_attempt` safety valve and the sub-score
diagnosis have collectively been exercised **four times**. Several sections of the skill
are specifications, not descriptions — and the brief's framing ("check the numeric claims")
mostly resolves to *not yet decidable*, which is itself the finding: the skill's newest and
most structural change is the one with the least evidence under it.

What the four panels do show, and it is consistent:

```
attempt  design  scores        total  silhouette contrast material brief
a37      d10     44, 52, 56     152      70/55/52  78/78/84  55/64/55  35/45/58
a38      d13     54, 44, 61     159      57/57/68  68/55/74  44/35/47  55/45/63
a39      d11     42, 58, 41     141      74/82/68  34/66/52  47/38/35  37/47/40
a40      d16     52, 52, 54     158      80/80/70  74/78/68  32/40/34  44/50/42
```

- **Median total 155.** Distance to accept (240): 81, 88, 82, 99. Distance to reject (60):
  81, 92, 98, 99. Every panel sat in the dead centre of a 180-point band.
- **Verifier spread** (max − min per attempt): 2, 12, 17, 17 — mean 12 on a 0–100 scale,
  i.e. up to ~51 points of swing on the 300 total, which is nearly the width of the reject
  band. Real, but never decision-relevant here.
- **Slot means**: v1 = 48.0, v2 = 51.5, v3 = 53.0. Suggestive of a first-seat harshness of
  ~5 points, but n = 4 per slot. **Not a finding.** Worth re-running at n ≥ 20.
- **`SCORE` runs below its own sub-scores in 11 of 12 critiques**, mean −5.7, worst −15.5.
  Verifiers' holistic number is systematically harsher than the axes they justify it with.
  That is a calibration fact about the panel, and it is the kind of thing the sub-scores
  were introduced to detect — see A3.
- **Material (43.8) and brief (46.8) sit ~22 points below silhouette (67.8) and contrast
  (67.4).** Consistent across all 12. That is where designs are dying, and nothing in the
  decision rule reads it.

---

## Architecture

### A1 — Every rule that is a norm rather than a mechanism has failed, and the failure rate is 100% where it is observable

**Claim.** The skill correctly argues at `SKILL.md:318-320` that "an instruction is
something an agent can forget, a semaphore is not", and then enforces exactly one rule that
way. Every other rule in that class is currently being violated.

**Evidence.**

| Rule | Where | Observed |
|---|---|---|
| "Do not use `isolation: worktree`; B creates the worktree" | `SKILL.md:278-284` | **22 of 22** recorded worktree paths are `.claude/worktrees/agent-<id>` — harness-created. Zero exceptions. |
| "B must remove the worktree and branch on accept/shelve/abandon" | `SKILL.md:299-307` | `git branch --list 'worktree-agent-*'` → **27**; `git worktree list` → main only. Tips sit at 4 stale commits (13× `52877da`, 7× `6a60374`, 6× `8ee2e24`, 1× `f3759c7`), none at `model/mage000` (`03e14b1`) — the literal "lands on an arbitrary commit" failure the rule exists to prevent. |
| "Record the worktree path at dispatch time" | `SKILL.md:309-313` | 22 of 42 attempts have `worktree`; **0 of 42** have `branch`. |
| "Every accept is a commit on `model/<asset>`" | `SKILL.md:258-266` | 3 accepted attempts; `model/mage000` carries **1** pipeline commit ("accepted state at session start"), reconstructed by A after the fact. |
| "B passes at most the three highest-impact points" | `SKILL.md:151-153` | Post-rule reports carry 3, 6, 6, 7 `[CONSENSUS]` items (a37–a40). Followed 1 time in 4. |
| "Never put a number in a brief" | `SKILL.md:559-563` | B wrote "albedo ~0.30" into the d22 dispatch **in the session after the rule was written**; the modeller measured it and overruled it (`iteration-log.json`, supervisor note 22). |
| "Only A writes `control.json`" | `SKILL.md:451` | Not violated in the surviving files, but unverifiable — the file has no provenance, which is the point. |
| Render cap of 2 | `preview.py:63-102` | **Held.** The one mechanised rule. |

**Impact.** Quality-neutral, resource-negative, and it compounds: the worktree leak is what
made two prior recoveries expensive. Order of magnitude, ~20 min of A's attention per
crash plus the 27 branches now needing manual cleanup.

**Proposed change.** Do not add more prose. Add the two cheapest mechanisms:

1. `preview.py` already runs inside the modeller's worktree and already writes a manifest.
   Have it stamp what it knows (see R1). That makes the dispatch-time bookkeeping a
   by-product rather than a discipline.
2. Add a `_tools/wt.py` with `new <design-id>` / `done <design-id>` that wraps
   `git worktree add -b … model/<asset>` and the removal pair, and refuses to create one
   outside `.claude/worktrees/<asset>-<design>`. Then the D brief's workspace block is
   generated, not hand-filled, and a leaked worktree is a `wt.py list` away from visible.
   ~60 lines, no new dependency, Windows-safe (`git worktree` handles the paths).

Replacement text for `SKILL.md:299-307`:

> **B never creates or removes a worktree by hand, and never passes
> `isolation: "worktree"`.** Both are `_tools/wt.py`:
>
> ```bash
> python Assets/Blender/_tools/wt.py new <asset> <design-id>    # prints path, branch, sha
> python Assets/Blender/_tools/wt.py done <asset> <design-id>   # removes worktree + branch
> python Assets/Blender/_tools/wt.py list <asset>               # anything leaked
> ```
>
> The rule used to be prose. Measured after three sessions: 22 of 22 worktrees were
> harness-created anyway and 27 branches leaked. A helper that prints the brief block is
> the only version of this rule that has ever held.

**Risk.** A helper script is another thing to maintain, and if B does not call it the rule
fails identically. Evidence I'm wrong: if the next two sessions show `agent-*` worktrees
disappearing after a plain re-tightening of the prose. I doubt it — this is the fourth
tightening.

### A2 — Tier A earns its cost, and the evidence is specific

**Claim.** The brief asks whether A is redundant with B. It is not, and the case is
concrete rather than principled.

**Evidence.** From `process-notes.md:13-92`, A caught four defects *before dispatching
anything*, at least one of them session-fatal:

- the skill's modeller render command named `icon_184` (a head crop) where the brief needs
  `icon_full_184` (the whole figure) — every silhouette judgement in the prior session was
  made against the wrong image;
- the audit was auditing the main-repo file from inside every worktree, so it printed PASS
  regardless of what the modeller built (now fixed in `audit_mage000.py:33-37`);
- "check the port, not the task status" was insufficient as a gallery liveness check.

A also produced the patch-contention matrix (`process-notes.md:356-400`), which is the
single most decision-relevant measurement in the corpus, and which B — by design, since it
never looks at a render and never leaves the routing loop — was not going to produce.

**Impact.** Quality-positive. Two of those four defects would each have invalidated a whole
wave of panels: call it 15–25 panel-verifier spawns, ~100k tokens, per session avoided.

**Proposed change.** None to the tier. One small consolidation: B currently keeps a
`process_notes_for_supervisor` array **inside** `iteration-log.json` — 20 232 bytes, 5.3%
of the file, duplicating a channel A already owns. Fold it into the per-attempt `notes`
field and let A harvest, or accept the duplication and stop growing it.

**Risk.** None material. This is a "found sound" answer to hypothesis 2.

### A3 — The sub-scores are unpaid overhead *only because nothing reads them*; the cheapest fix is to read them

**Claim.** Four axes are recorded per critique (12 × 4 = 48 numbers so far) and the
decision rule reads none of them. But they already contain the two most actionable signals
in the corpus, so dropping them is the wrong direction.

**Evidence.** `material` mean 43.8 and `brief` mean 46.8 against `silhouette` 67.8 and
`contrast` 67.4 — a consistent ~22-point gap over all 12 critiques. Independently,
`panel_pattern` in the log says the same thing in prose: *"every panel praised the concept
and rejected the render … the gem-contrast constraint was read by modellers as 'stay
dark', when what the panel wants is a confident mid-value."* That is a `material`-axis
failure, and the axis found it numerically in four panels where the prose took thirty.

**Impact.** Quality-positive, resource-neutral. The numbers already exist; only the reading
is missing.

**Proposed change.** Two lines, no new agent work. Add to `SKILL.md:151-153`:

> Rank the three points you pass down by **the axis with the lowest mean sub-score across
> the panel**, not by how many verifiers said it. A point on the dragging axis is worth
> more than a `[CONSENSUS]` on a healthy one — measured over four panels, `material` and
> `brief` ran ~22 points below `silhouette` and `contrast` and every one of those attempts
> was praised on concept and killed on surface.

And add to A's duties (`SKILL.md:754-757`), where the instruction already exists but has no
trigger: *"Report the dragging axis to the user the first time it is 15+ points below the
others across three consecutive panels."*

**Risk.** The overall `SCORE` is explicitly not an average of the axes (`SKILL.md:718`), so
axis-ranking can diverge from what actually cost score. Mitigated by the fact that `SCORE`
runs *below* the axis mean in 11 of 12 cases — the axes are, if anything, the more generous
reading.

### A4 — Sum vs median: the spread is large enough to matter, but the threshold is the actual problem

**Claim.** No single harsh judge has vetoed anything, because nothing has come near the
accept band. The band is unreachable at current calibration, and that is the live defect.

**Evidence.** Highest individual verifier score ever recorded: **61**. Accept requires a
three-verifier mean of 80. Median total 155 against an accept at 240. Meanwhile the
previous two regimes: archive-1 accepted **17 of 24** (71%) under a single critic;
archive-2 accepted **0 of 15**; the live log 3 of 42 (7%). Three regimes, accept rates 71%,
0%, 7%. The dial has never sat anywhere sensible.

A's own duty already covers this — *"if almost everything lands in one band, the thresholds
are set wrong and that is a one-line fix"* (`SKILL.md:750-753`) — and 4 of 4 landed in one
band without the dial moving. Another norm without a trigger.

**Impact.** Directly on quality: an unreachable accept band means the ratchet never engages
and every design runs to the no-improvement rule. That is the most expensive possible
failure mode, because it spends full modeller-and-panel cost per attempt and banks nothing.

**Proposed change.** Two, in order of value:

1. **Give the threshold a trigger, not just a dial.** Add to A's table
   (`SKILL.md:729-737`): *"If eight consecutive panels land in one band with none within
   30 points of an edge, tell the user the dial is mis-set and propose a number. Do not
   move it yourself — it is theirs — but do not wait to be asked."*
2. **Switch the total from sum to `3 × median`.** Same scale, same thresholds, same
   `control.json`, but one outlier verifier moves the total by 0 instead of by up to 17.
   Given the observed spreads (2, 12, 17, 17) that is a real robustness gain for a one-word
   change in `SKILL.md:132`. Trimmed mean buys nothing over median at n=3.

**Risk.** Median discards the information in disagreement — and the pipeline's own history
says wide spread means "the character summary is too vague" (`SKILL.md:758-760`). Keep
recording all three; only the *decision* uses the median. Evidence I'm wrong: if spread
turns out to predict which accepts the user later dislikes, sum is doing useful work.

### A5 — Relative scoring has already produced a documented drift failure, and there is no absolute check

**Claim.** Hypothesis 7 is confirmed, with the cleanest possible experiment sitting in the
log.

**Evidence.** `iteration-log.json` summary, d13: *"accepted 3/3 against run-117, REJECTED
3/3 against run-157 after rebasing onto d07 with not one line altered."* An identical
change, judged twice against two accepted baselines, unanimously both ways. Also recorded
at `process-notes.md:480`.

**Impact.** Quality. It means "accepted" is not a property of a change, and a chain of
accepts is not a chain of improvements. Over many small accepts, nothing measures the whole.

**Proposed change.** One periodic absolute check, cheap because it reuses the existing
mechanism. After every **third** accept, B renders `model/<asset>` HEAD and sends the
*single* render to one verifier with a different prompt:

> This is the model as it currently stands. There is no BEFORE. Score 0–100 against what
> this character is meant to be, and name the one thing most in the way of it.

One verifier, one render, ~5k tokens, every third accept. It gives the user and the
designers an absolute datum, and it is the only thing in the pipeline that would catch
drift.

**Risk.** It is a new dispatch shape, and the brief warns against adding tiers — this adds
no tier, it reuses E with a different prompt. Risk is that an absolute score is
uncalibratable in the same way relative ones are; mitigated by only ever comparing it to
its own history.

### A6 — The verifier brief forbids the image its own first sub-score requires

**Claim.** E is handed one BEFORE and one AFTER PNG and told *"Do not read any file other
than those two"* (`SKILL.md:696`), then asked to score `SILHOUETTE: does it still read at
184x184` (`SKILL.md:711`). The modeller renders three views. Whether the panel sees the
icon is left to whether B improvises.

**Evidence.** `SKILL.md:693-696` versus `SKILL.md:711`; D's render command
(`SKILL.md:657`) produces `hero_34`, `front`, `icon_full_184`. In practice B has been
passing more than two — a01's report discusses the icon at length — so this is a brief the
orchestrator has been quietly working around, which is exactly the front-loading failure
mode the skill is elsewhere ruthless about.

**Impact.** Quality, and the cost of fixing is negative — the icons are 184×184, ~45 tokens
each, versus ~1 560 for a 900×1300 hero.

**Proposed change.** Replace `SKILL.md:693-696` with:

> BEFORE — the model as accepted before this change:
> hero: `<abs path>`   icon: `<abs path to icon_full_184>`
> AFTER  — the model with this change:
> hero: `<abs path>`   icon: `<abs path to icon_full_184>`
>
> Look at all four. The icons are the silhouette test and cost almost nothing to look at.
> **Do not read any file other than those four.**

**Risk.** None identified.

---

## Economics

### E1 — The modeller cap is set to twice the measured merge capacity

**Claim.** `control.json` caps modellers at 6 (`SKILL.md` says 7). The measured maximum
number of in-flight patches that can co-land is **3 of 6**. At least half of every full
wave is rework by construction, decided before any panel sits.

**Evidence.** `process-notes.md:356-400` — a full pairwise `git apply --check` matrix built
by applying A for real and testing B, twice (5 patches then 6). Largest mutually compatible
set: 3. `d07` is the hub and coexists only with `d14`, so accepting it caps the wave at 2.
The log's `patch_contention.structural_note` reaches the same conclusion:
*"Six modellers editing one 2521-line file from a single baseline can only ever land two
changes cleanly."* (The file is now 3 216 lines, so the hot region has if anything grown.)

Corroborating: 224 run directories against 42 attempts = **5.3 renders per attempt**. A
modeller re-deriving and rebasing is where those extra builds go.

**Impact.** Resource, large. Halving the wave from 6 to 3 removes ~3 modeller lifetimes per
wave. Modeller token cost is not measurable from disk (transcripts don't survive), but at
5.3 build-render-measure cycles against a 3 216-line file, a modeller is plainly the most
expensive agent in the system — an order of magnitude above a verifier. This is the biggest
recoverable number in the pipeline, and it is bigger than the panel (E2).

**Proposed change.** Add to "Concurrency, isolation and contention":

> **The modeller cap is bounded by merge capacity, not by CPU.** Six modellers editing one
> file from one baseline were measured at a maximum of **three** mutually-appliable
> patches; four of the seven conflicting pairs collided in the same shared material block.
> Do not run more in-flight modellers than the last measured compatible set. Re-measure it
> whenever the queue reaches that size:
>
> ```bash
> # for every ordered pair: apply A for real at HEAD, then
> git apply --check <B.patch>
> ```
>
> Where a wave must be larger, **route by region**: give each in-flight design a disjoint
> part of the script and say so in its brief. The contention is not diffuse — it is one hot
> block near the top of the file.

**Risk.** Fewer in-flight modellers means fewer attempts per wall-clock hour, and the user
has asked for breadth. Counter: breadth that cannot land is not breadth. Evidence I'm
wrong: if region-routing is adopted and the compatible-set size rises to 5–6, the cap can
go back up — that is the measurement to watch.

### E2 — A fixed panel of three is spending ~58% of its tokens on decisions that were never in doubt

**Claim.** Hypothesis 6, confirmed on the data that exists.

**Evidence.** All four scored panels landed ≥ 81 points from both thresholds. Extrapolating
each attempt from **verifier 1 alone** (`3 × s₁`) gives 132, 162, 126, 156 against actual
152, 159, 141, 158 — errors of −20, +3, −15, −2, and **all four land in the same band**. A
single verifier would have produced the identical decision 4 times out of 4.

Escalation frequency, estimated from the larger old-regime corpus: 10 "keep" stances out of
78 critiques = 13% of verifiers were positive enough to be near an accept edge. So
expected panel size under "one verifier, escalate to three if `s ≥ 70` or `s ≤ 25`" ≈
1 + 0.13 × 2 = **1.26 verifiers per attempt**, versus 3.

Cost per verifier, measured from the artifacts: renders are 900×1300 (`front.png`,
`hero_34.png`) ≈ 1 560 image tokens each; icons 184×184 ≈ 45. A four-image panel member is
~3 200 image tokens + ~800 brief + ~400 output ≈ **4.4k tokens**. A panel is ~13k; 30
panels have been convened so far ≈ **400k tokens**. Adaptive panels would have cost ~170k.

**Impact.** Resource, ~230k tokens over the sessions to date, no observed quality change.
Second-largest recoverable cost after E1, and much cheaper to implement.

**Proposed change.** Replace the panel-size paragraph at `SKILL.md:236-240` with:

> **Panel size is adaptive.** Dispatch **one** verifier. Multiply its score by three: if
> the result falls within `escalate_margin` of either threshold, dispatch two more and
> decide on all three. Otherwise decide on the one.
>
> `control.json`: `"escalate_margin": 40`.
>
> Measured over the first four scored panels, every total sat 81–99 points from the nearest
> band edge and verifier 1 alone would have produced the same verdict in all four. Three
> judges are for close calls; most calls are not close. A wide-spread panel is still
> informative, so **always** run three when the user asks why something was rejected, and
> when a design is on its final attempt before shelving.

**Risk.** The adaptive rule assumes verifier 1 is unbiased, and slot means hint at v1 being
~5 points harsh (n=4). That biases toward *escalating* near the accept edge, which is the
safe direction, but it also biases toward premature rejection near 60. Mitigate by only
allowing a *single-verifier* verdict of `needs-work` — never a single-verifier reject or
accept. Evidence I'm wrong: if spread at n≥20 turns out to exceed ~25, a single sample is
too noisy and this should be reverted.

### E3 — Designer output already outruns build capacity 2:1, so closing the C→score loop buys little

**Claim.** Hypothesis 8 is real as a gap but low-value as a fix, because C is not and has
never been the constraint.

**Evidence.** 20 designs exist; **11** have ever been built; **9** (`d17`–`d21`, `d23`–`d26`)
have never been dispatched. `process-notes-pass2.md:106` reached the same conclusion a
session earlier: *"The designers were never the bottleneck."* Whether later designs score
better than earlier ones is **unverifiable** — only 4 designs have any score at all, and
they are contemporaneous.

The user's current instruction is explicitly breadth (`control.json` note, 2026-08-02), so
cutting designers conflicts with stated intent. But *continuous* designer dispatch against
a 9-deep queue is spend with no consumer.

**Impact.** Resource, small-to-moderate. A designer spawn is cheap (no images, no files) —
call it 3–5k tokens — but 3 running continuously against an unconsumed queue is pure waste.

**Proposed change.** Change the dispatch trigger, not the cap. In B's brief
(`SKILL.md:550`), replace *"keep the queue topped up with designers"* with:

> Dispatch designers only when the queue holds fewer designs than the modeller cap. The
> queue reached nine unbuilt designs in one session while three designers ran continuously;
> designs are cheap to invent and the queue has never been the constraint.

If the loop is closed later, the cheapest version is one line in the "already tried" list:
`d11 — the stole; scored 141/300, all three read it as a bare forearm`. That is free — B
already has the number — and it gives C the only signal it currently lacks.

**Risk.** Under-supply if the modeller cap rises. The trigger is proportional to the cap, so
it self-adjusts.

### E4 — Splitting `SKILL.md` is not worth doing for token reasons

**Claim.** Hypothesis 1, refuted on the numbers. The rationale is not expensive enough to
be worth relocating.

**Evidence.** Measured section budget (chars ÷ 3.6):

```
Dispatching                       9 721   ~2 700 tok
The pipeline                      5 970   ~1 658
Concurrency, isolation, contention 5 514   ~1 531
Your own duties                   4 334   ~1 203
State files                       4 263   ~1 184
Asset facts                       2 571     ~714
Front-load everything             2 004     ~556
Gotchas                           1 819     ~505
Getting the gallery in front...   1 379     ~383
Setting up                        1 495     ~415
Preferences                       1 126     ~312
(intro + STOP + never-do + audit)         ~800
TOTAL                            44 057  ~11 965 tok
```

A clean A-facing / B-facing split saves A about 8.5k tokens and B about 2.7k — **~11k
tokens once per session**, against ~400k spent on panels alone and an unmeasured but larger
figure on modellers. It is under 2% of a session and it costs the thing the brief says to
preserve: the rationale sitting next to the rule it justifies.

**Impact.** Resource, negligible. Ranked last deliberately.

**Proposed change.** None for cost. If the file is split later, split it for a different
reason — that A and B need different things at different times — and split it at
`Dispatching`, the one section that is purely B's and is 23% of the file. Do not strip
evidence from the directive sections; A1 above is the argument for why the evidence is what
keeps the rules alive.

**Risk.** This is a refutation, so the risk is that I've mis-costed the wave. If a session
spawns B repeatedly (it has — B "keeps exiting early", `process-notes.md:674`), the file is
re-read each time and the number multiplies. Even at 5 B-spawns it is ~60k, still below E2.

---

## Robustness

### R1 — The render process knows everything the pipeline keeps losing, and writes none of it down

**Claim.** Every attribution failure in three sessions has the same shape: work is done, the
agent that did it dies or forgets to report, and nothing on disk says whose it was.
`preview.py` is running *inside* the worktree at the moment the work happens and could
record it for free.

**Evidence.**

- 11 of 42 attempts (26%) currently carry no verdict — 5 `in-flight`, 6 `awaiting-panel` at
  the pause. `note` in the log: *"six attempts are rendered, measured and have never been
  judged … the expensive half of that work is already paid for."*
- `handoff.unattributed_runs` lists **runs 144–149, 158–168, 195–196, 198, 203, 205–206,
  212, 215, 219–221** as unlinkable to any attempt, with the standing instruction *"Do not
  link any to an attempt without a modeller naming it."*
- `process-notes.md:429-478`: after the crash, the worktree→design mapping was rebuilt by
  grepping four diffs for `GODET_`, `TRAIN_`, `CROWN_`, `VOW_`, *"which only worked because
  the modellers happened to name their globals after their designs."*
- 224 run directories against 42 attempts. Most renders are anonymous.

**Impact.** Both sides. It is the largest source of *lost* work (26% of attempts open) and
of A's attention (the scarcest resource in the system).

**Proposed change.** In `preview.py`, in the manifest built at line 455, add what the
process already knows:

```python
"provenance": {
    "cwd": os.getcwd(),
    "script": script,
    "branch": _git(script, "rev-parse", "--abbrev-ref", "HEAD"),
    "sha":    _git(script, "rev-parse", "--short", "HEAD"),
    "design": os.environ.get("GLOOMFELL_DESIGN"),   # B sets it in the D brief
},
```

with `_git` a three-line `subprocess.run(..., cwd=os.path.dirname(script))` that returns
`None` on failure. Then:

- every run is attributable without an agent surviving to say so;
- `git branch --list 'worktree-agent-*'` minus the branches named in manifests is exactly
  the leak set;
- B's "poll, do not wait to be notified" loop (`SKILL.md:572-575`) gets the design id from
  the manifest instead of guessing from run numbers above the last logged attempt.

One line in the D brief sets the env var:
`$env:GLOOMFELL_DESIGN='<design-id>'; python ...preview.py ...` — PowerShell-native, and
harmless on Bash where `GLOOMFELL_DESIGN=<id> python ...` works.

**Risk.** `os.getcwd()` is the caller's cwd, not necessarily the worktree — hence also
recording `script`, which is always the worktree path. If a modeller renders from the main
repo the provenance is still correct, just less interesting. Nothing here can break a build:
all four fields are best-effort and `None` is an acceptable value.

### R2 — B's death is survivable; B's *silent success* is not

**Claim.** Hypothesis 11. The crash path is actually well-covered; the uncovered failure is
B returning normally while `control.json` still says `run`.

**Evidence.** From `process-notes.md:429-460`, what survived a real terminal death: the
whole log with 20 attempts and every report, 168 run directories, the gallery server (still
answering on 8777 hours later), all four worktrees with uncommitted work, and the two
landed changes. What did not: the four modeller agents. Recovery cost was *re-identification*
(R1), not lost work.

The worse case is `process-notes.md:674-685`: *"B has now returned twice while
`control.json` still said `run`, both times mid-wave, and both times only resumed because a
relay happened to arrive."* Four silent exits in one session (`SKILL.md:503-506`). The
heartbeat was added for exactly this and it works — it is stamped and current right now —
but **nothing reads it on a schedule.** A checks it "when asked" (`SKILL.md:506`).

**Impact.** Robustness. A silently-exited B costs the entire in-flight wave's worth of
attention to notice and restart.

**Proposed change.** Give the heartbeat a consumer. Add to A's duties:

> **Check `heartbeat` before every reply to the user, not only when asked.** If it is more
> than fifteen minutes old while `state` is `run`, say so unprompted and offer to restart B
> — a B that has silently returned looks exactly like a B that is thinking, and four exits
> in one session were each caught only by accident.

Cheaper and stronger than any recovery protocol, because the recovery path is already good.

**Risk.** Fifteen minutes may be short for a long modeller wave; the fix is a number in
`control.json` if it turns out to be noisy.

### R3 — `iteration-log.json` should split hot from cold, not become JSONL

**Claim.** Hypothesis 12, half-confirmed. The file is a problem, but append-only JSONL
solves the wrong half.

**Evidence.** Composition of the 387 KB, measured:

```
attempts                       318 895   84.1%
  ├─ critiques within them     131 641   34.7%
  └─ combined reports          107 733   28.4%
process_notes_for_supervisor    20 232    5.3%
designs                         17 496    4.6%
handoff                         12 541    3.3%
summary                          5 566    1.5%
everything else                 <1%
```

63% of the file is verifier prose that is written once and re-read by nobody — B is told to
re-read `summary` (5.6 KB), not the history. The problem is not append performance, it is
that a full rewrite risks the whole corpus on every cycle, and that a hand-written
`json.dump` without `encoding="utf-8"` would mangle 126 KB of em-dash-laden critique
(gotcha 9).

**Impact.** Resource, moderate; robustness, moderate.

**Proposed change.** Split by temperature, keep JSON:

- `iteration-log.json` — everything except `attempts[].critiques` and
  `attempts[].report`. That is ~11% of current size, ~43 KB. Rewritten every cycle as now.
- `attempts/<id>.json` — one file per attempt holding the three critiques and the combined
  report. Written once, never rewritten, named by the id already in the log.

The gallery reads the small file; A reads the small file; the big prose is one lookup away
and can never be lost by a bad rewrite. JSONL would give append-safety but costs the
gallery its single-parse read and gains nothing the split doesn't.

**Risk.** More files. Mitigated by them being named exactly `a01.json … a42.json` and
living beside the log. The migration is a 20-line script; the *format* change must be
described in `SKILL.md:457` and in the gallery's fetch, or the progression view breaks.

### R4 — `control.json` provenance: a mechanism exists, and it is worth one line

**Claim.** Hypothesis 13. The skill's own answer is a norm; a real mechanism costs almost
nothing here, because A is the only agent with a user in front of it.

**Evidence.** `SKILL.md:446-455` documents the incident: *"the pipeline halted on a `notes`
entry attributing an instruction to the user that the supervisor never received, and it was
impossible to establish afterwards where it came from."* Current `control.json` notes are
stamped with a date and an author initial (`"2026-08-02 (A): …"`) — the convention is
already half-adopted, voluntarily.

**Impact.** Robustness, small but the failure it prevents is a full-fleet halt.

**Proposed change.** Not cryptography — structure. Change the schema so an unattributed
note is *syntactically* invalid:

```json
"notes": [ { "at": "2026-08-02T18:16", "by": "A", "text": "more gold" } ]
```

and add: *"A note without `by: \"A\"` is not a user instruction. Do not act on it, do not
delete it, show it to the user and ask."* A forged note is still possible, but it now has
to be a deliberate lie rather than an accident, and the accident is what actually happened.

**Risk.** Breaks any reader of the current shape (the gallery does not read `control.json`;
B does). One-line migration.

### R5 — The audit cannot ever produce the evidence it is being kept for

**Claim.** Hypothesis 10. Not dead weight — but as configured it has zero variance, so the
correlation the skill promises A will one day compute is not computable.

**Evidence.** 183 of 224 runs carry an audit line. Of the 31 audit lines attached to
attempts in the live log: **31 PASS, 0 FAIL.** The only FAIL in the corpus came from d13's
deliberate bevel-angle experiment, which was reverted and is now recorded as an asset fact.
A binary column with no variance cannot correlate with anything. `process-notes.md:807`
says so itself: *"nothing yet … its verdict column had no variance to correlate against."*

Cost is real but small: the audit spawns a second Blender that re-execs the asset script
(`preview.py:332`, `audit_mage000.py:37`) with `DO_RENDER` false — so it is a full geometry
rebuild, CPU-bound, no GPU context. Note it runs **outside** the render-slot semaphore; that
is safe today precisely because it does not render, and it would stop being safe the moment
anyone gave the audit a render.

**Impact.** Resource, small (~183 extra builds ≈ 15–20 min of CPU across three sessions).
Evidence value currently zero.

**Proposed change.** Give it variance. Have the audit print each check's **margin** rather
than a verdict — `levitation: min gap 0.004 (PASS)`, `symmetry: max asymmetry 0.021`,
`below_floor: -0.000`. Then A can correlate a continuous quantity against panel scores,
which is a question with an answer. Add to `SKILL.md:355-357`:

> The audit has returned PASS on every judged attempt to date, so as a binary it can never
> correlate with anything. Its checks must print margins, not verdicts, before the "promote
> or delete this rule" decision is possible at all.

And add a note next to `preview.py:332` that the audit deliberately bypasses `render_slot`
because it does not render, and must take a slot if that ever changes.

**Risk.** None; the PASS/FAIL line the gallery colours is kept as the last line.

---

## Authoring

### A7 — Front-loading is complete for D, incomplete for E, and over-complete for C

**Claim.** Hypothesis 15. The doctrine is the skill's best idea and D's row is genuinely
exhaustive. The other two rows have gaps in opposite directions.

**Evidence.**

- **D** — nothing left to discover that B knows. The symbol-index command
  (`SKILL.md:674-677`) is the model, and asset-facts inlining is the highest-value item in
  any brief in the file. **Sound.** One addition: D is told the file is `<N>` lines but not
  *which region it owns* — see E1's region-routing.
- **E** — has a genuine gap: the icon (A6), and the recurring constraint below (A8).
- **C** — the designer brief inlines the nine preferences (`SKILL.md:592`) at ~312 tokens
  per spawn, for a tier explicitly told to invent freely and touch nothing. The preferences
  are about *how to build* (bevel ≥ 0.03, subsurf, shade smooth, boots as shells) — five of
  the nine are modelling technique a designer cannot act on. Trim C's copy to the four that
  shape ideas (silhouette-first, trim draws the form, dark recesses, no levitation) and
  keep all nine for D.

**Impact.** Small each; A6 is the one that matters.

### A8 — The panel keeps rediscovering the same constraint because nobody is allowed to tell it

**Claim.** Hypothesis 17. Withholding the preferences from E is right. Withholding the
*character's own contrast budget* from E is not, and it is costing the same discovery
ninety times.

**Evidence.** `panel_pattern` in the log, computed by A over six panels and eighteen
reports: *"THREE changes put new bright pixels somewhere other than the gem and were killed
for it … THREE changes put no bright pixels anywhere, vanished at 184 and were killed for
that … two verifiers independently pointed at the same missing middle."* Ninety critiques
have been written; every panel arrives at the same constraint from scratch. Sub-scores
agree: `contrast` is the axis with the widest range (34–84), i.e. the one the panel is
least consistent on.

This is not a preference and not a rule — it is a property of *this character* (a gem is
the brightest element and everything else must lose to it). The skill already has the right
home for it: the character summary, which E does receive, and which B writes once and
reuses verbatim (`SKILL.md:543-544`).

**Impact.** Quality, and it costs nothing — the character summary is already inlined.

**Proposed change.** Add to B's startup instructions, after the character summary line:

> The character summary must carry the model's **contrast budget** — which single element
> is allowed to be the brightest thing, and what everything else must therefore do. It is
> not a preference and not a rule; it is a fact about this character that a verifier cannot
> infer from two images. Update it whenever the panel establishes one. Measured over six
> panels, three changes were killed for adding bright pixels away from the gem and three for
> adding none anywhere — the panel was re-deriving the same budget every time.

**Risk.** This is the thin end of giving E a rulebook, which the skill bans deliberately and
for good reason. The line to hold: the summary says *what the character is*, never *what a
good change looks like*. Evidence I'm wrong: if panel spread on `contrast` collapses to
near-zero after adding it, the panel has started agreeing with the brief instead of judging.

### A9 — "Never put a number in a brief" is stated at the wrong level and pairs badly with "measure from the render"

**Claim.** Hypothesis 16. The pairing works — it is the pipeline's best-evidenced success —
but the ban is written as a rule about *numbers* when the real rule is about *unverified*
numbers, and B broke it within one session of it being written.

**Evidence.**

- The pairing works: `process-notes.md` observation 20 — *"four consecutive attempts — d10
  a2, d13 a5, d11 a2, d16 a1 — measured themselves from the PNGs rather than the model, and
  all four report landing in the target"*. And `SKILL.md:645-648`: five modellers contested
  a unanimous instruction with data, five were right.
- The ban does not hold: supervisor note 22 — B wrote *"albedo ~0.30 with a faint blue
  cast"* into the d22 brief; built exactly, it rendered as the brightest thing on the model
  and the modeller caught it by measuring. That is the same failure the rule at
  `SKILL.md:559-563` was written to prevent, recurring after it was written.
- Meanwhile numbers B *has* measured are exactly what the front-loading section demands it
  pass down (sha, line count, symbol index, scores).

**Impact.** Quality, moderate. The current phrasing is over-broad, which is part of why it
is ignored.

**Proposed change.** Replace `SKILL.md:559-563`:

> **Never put a number in a brief that you have not measured.** Shas, line counts, scores
> and file offsets are yours to pass down and the front-loading section requires it. Target
> values for anything that *renders* are not — you never see a render, so any albedo,
> height or width you specify is a guess dressed as an instruction. State the intent and let
> the modeller bracket it against the pixels. One session's orchestrator wrote "albedo
> ~0.30" into a brief, the modeller built exactly that, and it rendered as the brightest
> thing on the model; where the same orchestrator gave intent instead, the modellers landed
> it.

**Risk.** None. This is a clarification of a rule already agreed.

### A10 — `asset-facts.md` should gain an eviction path and a section for what the *panel* gets wrong

**Claim.** Hypothesis 9. A ledger that only grows has two failure modes, and the pipeline
has already hit the second.

**Evidence.** The file is 5 516 chars / 15 bullets — ~1 500 tokens inlined into every
modeller brief. At 6 modellers × several waves that is real but affordable *today*; there is
no eviction rule, and nothing marks a fact as superseded when the rig changes.

The sharper gap is the one the brief names. Verifier perceptual errors are documented,
mechanical, and reproducible:

- *"Three separate independent panels told d08's modeller the effect was 'too high', at hip
  and belt height — where the height mask is provably and exactly zero."*
- *"d10's panel unanimously asked for a collar below the brim's underside and inboard of it
  — geometrically invisible to every camera"*, proven by building it.
- The front camera / brim fact is already in `asset-facts.md` as a *modelling* constraint —
  its consequence for how the *panel* will misread the image is not.

These are not opinions and they satisfy the file's own admission test (mechanical,
verifiable, about this rig). They currently reach nobody: E is not allowed a rulebook, and D
only learns them by being wrong.

**Impact.** Quality. Five contested-and-correct instructions in one session is five attempts
where D had to spend a render proving the panel wrong before doing any work.

**Proposed change.** Two edits to the asset-facts section:

1. Add a subsection, and say what belongs in it:

   > **## What the render invites the panel to misread**
   >
   > Verifiers judge images and cannot inspect the model, so a misleading image produces a
   > *unanimous* wrong instruction, not a split one — independence multiplies a perceptual
   > error into `[CONSENSUS]` rather than filtering it. A entry belongs here only when a
   > modeller has *measured* the contradiction:
   >
   > - The brim's projected disc makes anything under it look like it sits at chest height.
   >   Three panels called an effect "too high, at hip and belt" where its mask is exactly
   >   zero.
   > - A collar inboard of the brim's underside is invisible to every camera in the rig. A
   >   panel unanimously prescribed one; it was built and proved invisible.

2. Add an eviction rule, since nothing else will:

   > A fact leaves this file when the rig changes under it. When a modeller reports that a
   > fact no longer holds, **strike it, keep one line saying it was struck and when** — a
   > fact that quietly disappears will be rediscovered, and a fact that is silently wrong is
   > worse than no fact. Keep the file under ~25 entries; it is inlined into every modeller
   > brief and it is the one thing in there nobody is allowed to skim.

**Risk.** The new subsection is one step from becoming a rulebook by the back door — it must
stay in D's brief and stay out of E's, which the current structure already guarantees. If
the panel's misreads turn out to be design signal ("if it looks too high, it *is* too high
for a viewer"), this section teaches D to dismiss real feedback. The measured-contradiction
admission test is the guard.

### A11 — D's persistence-versus-respawn crossover is not derivable from what survived

**Claim.** Hypothesis 14. I cannot re-derive the ~35k figure and neither can anyone else
from disk — agent transcripts do not survive. But the natural experiment the pipeline needs
has already happened once and was not measured.

**Evidence.** `SKILL.md:192` asserts ~35k tokens to re-learn; nothing on disk supports or
refutes it. The crash handed four designs to fresh modellers who inherited the code without
the reasoning (`process-notes.md:697-710`), and A flagged at the time that this was *"the
only chance to observe"* whether handed-back attempts fare worse. Outcome: of the four,
d09 and d12 both went on to be shelved; d13 was accepted-then-rejected on rebase; d08
shelved. But every one of those was already deep in a losing design, so the comparison is
confounded and I will not draw a conclusion from it.

Directionally, the argument for a crossover is sound and cheap to state: by attempt 6 a
resumed D's context holds every prior critique verbatim — with critiques averaging 1 403
chars and three per attempt, that is ~4 200 chars/attempt of accumulated panel prose plus
its own renders and measurements. Somewhere past attempt 5 that exceeds a written summary
of the same material.

**Impact.** Unknown. Marked as such.

**Proposed change.** Make it measurable rather than guessing. Add to B's brief:

> When you resume a D at attempt 6 or beyond, record `"resumed": true` on the attempt. When
> you hand a design to a fresh modeller with history, record `"resumed": false`. Nothing
> else on disk distinguishes them, and the question of when a fresh modeller with a summary
> beats a resumed one is otherwise unanswerable.

**Risk.** None; it is one boolean.

---

## Claims checked against the artifacts

| Claim in `SKILL.md` | Verdict |
|---|---|
| `:126-128` verifiers returned "change" on 68 of 78 critiques (87%) | **Holds exactly.** Counted: 68 `change`, 10 `keep`, n = 78. |
| `:147-149` 176 consensus items / 26 closed attempts = 6.8 per attempt | **Holds, and has not improved.** Now 198 across 30 reported attempts = 6.6/attempt, *after* the "pass at most three points" rule was added. Post-rule reports carry 3, 6, 6, 7. |
| `:307` "one session leaked fifteen full checkouts" | **Directionally confirmed, count unverifiable.** 27 orphan `worktree-agent-*` branches today, 0 live worktrees, 6 leaked in the most recent session (`process-notes.md:463`). |
| `:192` resuming D saves ~35k tokens | **Unverifiable.** Transcripts do not survive. See A11. |
| `:220-222` six modellers, 123 tool calls before first edit | **Unverifiable** from disk; consistent with 224 run dirs / 42 attempts = 5.3 renders per attempt. |
| `:317-318` renders capped machine-wide at 2 by a semaphore | **Holds.** `preview.py:63-102`, mkdir-based, `GLOOMFELL_RENDER_SLOTS` default 2. Caveat: `run_audit` (`preview.py:332`) bypasses it — safe only because the audit does not render (R5). |
| `:325` "a render is ~7 seconds" | **Holds.** 314 measured builds: mean 7.5 s, median 6.6 s, max 33.5 s. |
| `:331-332` `--samples` scales TAA and defaults to 0.5 | **Holds.** `preview.py:522`. |
| `:342-344` `--root` points worktree renders at the real previews root | **Holds.** `preview.py:527-529`; 224 runs landed in the main repo from worktree builds. |
| `:836` `preview.py` refuses any script without the variant hook | **Holds, and understates it.** Three gates: `require_variant_hook` before any Blender starts (`:436`), `audit_hook_refusal` up front (`:440-444`), and again inside `run_audit` (`:326`). |
| `:859-862` gotcha 9, UTF-8 on state files | **Holds.** Every `open()` in `preview.py` passes `encoding="utf-8"`. |
| `:226-227` "the log was already 20 KB an hour into one run" | **Holds and has worsened 19×.** 387 KB now, 84% of it `attempts`. |
| `:503-506` B silently exited four times in one session | **Corroborated** (`process-notes.md:674-685`, two more instances). Heartbeat now present and current — but unread (R2). |
| `:645-648` five modellers contested a unanimous instruction and all five were right | **Corroborated in A's notes**, with two independently proven cases (the zero-valued height mask; the geometrically invisible collar). The "all five were right" cannot be independently re-derived. |
| `:369-374` three modellers independently found the Base Color / specular fact | **Corroborated**, `asset-facts.md` records all three sites. |
| `:132-140` the score bands, `no_improvement_limit`, `report_at_attempt` | **Not yet decidable.** 4 scored attempts total; no design has reached the no-improvement rule under scoring, and nothing has come within 81 points of the accept band. |

---

## Checked and found sound — leave these alone

- **The render cap and everything around it.** 314 builds totalling 2 345 s (39 min) across
  ~45 hours of elapsed session time: renders are **1.4%** of wall clock. The skill's claim
  that render throughput has never been the bottleneck is not just true, it is true by two
  orders of magnitude. Do not touch `RENDER_SLOTS`, and the "never raise it to buy speed"
  instruction is correct.
- **The variant-hook interlock.** Three independent gates, all correct, all commented with
  the reason. Nothing to add.
- **Keeping raytracing on while cutting samples.** The reasoning at `SKILL.md:336-340` is
  sound and the brief in play (pearlescence, nacre, fresnel-gated hue) is exactly the case
  where it matters.
- **Tier A.** Earns its cost, evidenced (A2).
- **D's brief.** The most complete front-load in the file; the symbol-index command is the
  right pattern and the workspace-ownership sentence is doing real work.
- **`asset-facts.md` as a concept.** The single highest-value item in any brief here. My
  proposals (A10) extend it; none of them weaken it.
- **Shelving.** Three patches on disk (`d08` 122 KB, `d09` 88 KB, `d12` 40 KB), tracked in
  git, each with its full attempt history in the log. This worked exactly as specified,
  including the part where the most valuable diagnosis of the session (sampling below
  Nyquist) arrived on a design that was shelved and was preserved anyway.
- **Scores over verdicts.** The regime change is right even though it is barely tested: 71%
  / 0% / 7% accept across three regimes shows the binary scale was the problem, and the
  arithmetic argument at `SKILL.md:126-130` is correct.
- **Both hard rules** (no variants to pick between, no save/export until "finish").
  Untouched by anything above.
- **The voice.** The rationale-next-to-rule style is what makes A1 diagnosable at all — I
  could tell which rules were re-tightened and how often because the file says so. E4 is a
  refutation of the argument for stripping it.

---

## Two things I would flag that were not on the list

1. **`model/mage000` carries one commit for three accepts, and it was built by A with git
   plumbing after the fact** (`process-notes.md:844-852`). The "accepted state is a commit"
   section is the most-argued in the file and it has never been executed by B in normal
   operation — only reconstructed by A during recovery. That is the same category as A1 and
   it is arguably the most consequential instance, because it is the thing every other
   worktree rule depends on.
2. **Nine of twenty designs have never been built, and two of them arrived independently
   from two different designers as near-duplicates** (`process-notes.md:857-862`, d17 and
   d26). Convergent invention across isolated designers, with no score signal reaching
   them, is the first sign the design space is being exhausted in one direction — and the
   "already tried" list cannot prevent it because both designs were invented in the same
   wave and neither was on the list yet. Worth a cross-check in B's collection step: when
   two designers return in the same wave, dedupe before queueing.
