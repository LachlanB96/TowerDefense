# Review brief — `/blender-model-mode`

Hand this verbatim to a fresh agent. It is a self-contained assignment.

---

You are reviewing the design and architecture of a Claude Code skill. Your output is a
written review, not a code change. **Do not edit `SKILL.md` or any pipeline file** unless
the person who dispatched you asks for it in a follow-up.

## What the skill is for

`.claude/skills/blender-model-mode/SKILL.md` (866 lines, 44 KB) primes a session to run a
five-tier agent pipeline that iterates a 3D model. The model is Python source driving
Blender headlessly; a change to the model is a change to that source, a headless build, and
a render that gets judged. The tiers are:

- **A · supervisor** ×1 — the session you would be talking to. Talks to the user, writes
  process notes, never designs or models.
- **B · orchestrator** ×1 — routes, aggregates, decides. Never looks at a render.
- **C · designer** ×3 — invents changes from a loose brief. Touches no files.
- **D · modeller** ×7 — implements ONE change in its own git worktree, renders it.
  Persists across retries of the same design.
- **E · verifier** ×3 per attempt — scores the render 0–100. Fresh every attempt, never
  sees the other two.

**The objective you are optimising for is explicit: the best model output per unit of
resource consumed.** Resource means tokens, wall-clock, and GPU contention on a single
desktop that is also running Unity. A recommendation that improves quality at unbounded
cost is not automatically a win, and neither is one that saves tokens by making the loop
converge worse. Where you propose a change, say which side of that ratio it moves and
roughly by how much.

## Read these first, in this order

1. `.claude/skills/blender-model-mode/SKILL.md` — the whole thing.
2. `CLAUDE.md` at the repo root — the project's own conventions, which the skill sits on
   top of. In particular the "Asset pipeline" and "Preview harness" sections.
3. `Assets/Blender/_tools/preview.py` (550 lines), `serve.py` (46), `build_one.py` (117) —
   the actual machinery the skill drives. **The skill describes behaviour these files may
   or may not implement.** Check the ones that matter: the render slot semaphore, the
   `--samples` default, the `--audit` flag, the variant-hook safety interlock, the
   `--root` handling, UTF-8 encoding on state files.
4. `git log --oneline -- .claude/skills/blender-model-mode/SKILL.md` — eight revisions. The
   diffs show which rules were added in response to which failure. Rules that keep getting
   re-tightened are rules that are not working.

## Ground truth: do not review the prose alone

The skill argues from measurement — roughly fifteen claims of the form "measured over one
session, N of M...". Those sessions left artifacts, and they are still on disk. **Your
review is worth much more if it is grounded in them than if it is grounded in your reading
of the prose.**

```
Assets/Blender/_previews~/mage000/iteration-log.json           359 KB   <- the live log
Assets/Blender/_previews~/mage000/iteration-log-archive.json    22 KB
Assets/Blender/_previews~/mage000/iteration-log-archive-2.json  38 KB
Assets/Blender/_previews~/mage000/process-notes.md              48 KB   <- A's observations
Assets/Blender/_previews~/mage000/process-notes-pass2.md          8 KB
Assets/Blender/_previews~/mage000/asset-facts.md                 5 KB
Assets/Blender/_previews~/mage000/control.json
Assets/Blender/_previews~/knight000/control.json
docs/shelved/mage000/{d08,d09,d12}.patch                        <- three shelved designs
```

**Do not read the 359 KB log into context.** Extract from it with a script — Python with
`encoding="utf-8"` (Windows defaults to cp1252 and will mangle it). Compute, don't skim:

- the distribution of totals out of 300, and how many attempts landed in each band
- accept / needs-work / shelve rates, and attempts-per-design
- per-design score trajectories — how often does the loop actually climb?
- verifier spread (max − min of the three) per attempt, and its distribution
- whether each verifier's `SCORE` tracks its own four sub-scores, or diverges
- which sub-score axis is systematically lowest
- how many attempts exist with no verdict — i.e. work that was done and lost

Then check the skill's numeric claims against what you computed. Say plainly which hold,
which do not, and which are unverifiable from what survived. A claim that no longer holds is
a rule that may have outlived its cause.

**One live contradiction to start you off.** The skill requires B to remove each modeller's
worktree and branch on accept, shelve, or abandonment, and warns that "one session leaked
fifteen full checkouts". Right now:

```bash
git branch --list 'worktree-agent-*' | wc -l     # 27
git worktree list                                 # only the main checkout
```

Twenty-seven orphaned branches, from harness-auto-created worktrees the skill explicitly
tells B not to use. Work out what that implies about the difference between a rule stated
in prose and a rule enforced by a mechanism — the skill makes exactly this argument itself
about the render cap ("an instruction is something an agent can forget, a semaphore is
not") and then does not apply it anywhere else. Look for every other rule in the same
category.

## What to interrogate

Answer all of these. They are hypotheses to confirm or refute against evidence, **not
conclusions** — several may turn out to be fine, and saying so with evidence is a useful
finding. This list is not exhaustive; the most valuable thing you can return is a real
problem nobody thought to look for.

**Structure and context cost**

1. The skill is one 44 KB file. B reads all of it at startup; A reads all of it at invoke.
   Roughly half is post-mortem rationale ("measured in one session, six modellers spent 123
   tool calls..."). Rationale is what stops a future editor deleting a rule they don't
   understand — but it is paid for on every read. Is there a split (directive vs. evidence,
   or A-facing vs. B-facing reference files) that keeps the rationale discoverable without
   putting it in every context window? Cost it in tokens.
2. A and B are separate agents. Enumerate what A actually does that B could not, and say
   whether the tier earns its cost. Argue it either way, but argue it from the transcript
   of duties in the skill, not from principle.

**The decision rule**

3. Three holistic scores are **summed** and compared to fixed bands. Consider sum vs.
   median vs. trimmed mean under one outlier verifier. Is a single harsh judge able to veto
   an otherwise-accepted change, and did that happen in the log?
4. Verifiers are uncalibrated — no anchor examples, no shared scale beyond three sentences
   of guidance. Check the log for systematic offset between verifier slots. If one verifier
   position consistently scores lower, the sum is measuring seat position as much as
   quality.
5. Four sub-scores are recorded and **nothing in the decision rule reads them**. They feed
   only B's "top three points" ranking and A's notes. Is there a cheap way to make them
   load-bearing, or should they be dropped as unpaid overhead?
6. Panel size is fixed at three per attempt regardless of how clear-cut the attempt is.
   Given the score distribution you computed, how many attempts were decided so far from a
   band edge that one verifier would have sufficed? Model an adaptive panel — one verifier,
   escalate to three only near a threshold — and estimate the token saving. This is likely
   the single largest recoverable cost in the pipeline; check whether it is.
7. Scoring is **relative to the previous accepted state**, every time. Over many small
   accepts, does anything prevent slow drift away from the brief? Is there an absolute or
   periodic whole-model check, and if not, does the log show drift?

**Feedback loops that don't close**

8. Designers (C) receive an "already tried" list but **never see any score**. The tier that
   generates ideas gets no signal about which ideas the panel rewards. Establish whether
   this is a real gap — do later designs in the log outperform early ones? — and what the
   cheapest closing of that loop would be.
9. `asset-facts.md` is the pipeline's shared learning ledger and is the mechanism the skill
   is proudest of. Its write path is B-only, sourced from modeller reports. Verifier
   perceptual errors — which the skill documents as real and unanimous — never enter it.
   Should they? What is the failure mode of a fact ledger that only grows?
10. The audit runs on every render, gates nothing, and is seen by nobody. The skill says the
    user will promote or delete rules "later, from data". Nothing owns that decision or
    triggers it. Is this a dormant good idea or dead weight?

**Failure, recovery and state**

11. B is a single point of failure with a heartbeat but no documented recovery. What
    actually happens mid-wave if B dies? Trace it: which state survives, which in-flight
    modellers are unattributable, what a restarting B can and cannot reconstruct.
12. `iteration-log.json` is 359 KB and B rewrites it. Consider append-only JSONL, or
    splitting the hot summary from the cold attempt history. Quantify.
13. `control.json` is the user's stop button and the skill's own answer to "any agent could
    forge a note" is a norm ("only A writes it"), not a mechanism — the same class of error
    it criticises elsewhere. Is there a mechanism available? Is one warranted?
14. D persists across retries; the skill justifies this at "~35k tokens to re-learn".
    Re-derive that number if you can, and find where the crossover sits — by attempt 6 or 8
    a resumed D's context contains every prior critique. Is there a point where a fresh D
    with a summary is cheaper *and* better?

**The briefs themselves**

15. The front-loading doctrine (inline everything, children read almost nothing) is the
    skill's best idea. Audit it for completeness: for each of C, D and E, is there anything
    still left for the child to discover that B already knows? The symbol-index command is
    the model to follow.
16. "Never put a number in a brief" (B) versus "measure from the render, not the model" (D).
    Check the log for whether that pairing worked, and whether the ban is stated at the
    right level of generality.
17. Verifiers are deliberately given no preferences and no rulebook. The user's nine
    preferences reach C and D but never E. Does the log show the panel rejecting things the
    preferences would have permitted, or vice versa?

## Constraints your recommendations must respect

Anything violating these is not a usable finding.

- **One desktop, one GPU**, shared with Unity and a browser. Render concurrency is a safety
  cap, not a throughput knob; the skill documents a driver-reset freeze at three slots.
  Do not propose buying speed with GPU parallelism.
- **Windows / PowerShell primary.** Bash exists but the harness is Windows-native. Anything
  you propose must survive cp1252 defaults and Windows path handling.
- **No test suite, no CI.** There is no automated way to know a model got better. The user's
  eye is the only ground truth for taste, and their attention is the scarcest resource in
  the whole system. Weigh proposals by how much user attention they consume.
- **The user is deliberately running without gates** to observe what the pipeline does
  unconstrained. Proposing "add a gate" is allowed but must be argued against that stated
  intent.
- **Two hard rules exist because they were violated and cost real work**: never offer the
  user variants to pick between, and never save/export until the user says "finish". Do not
  propose relaxing either without a strong, specific reason.
- **Preserve the voice.** The skill is written in a terse, evidence-first, second-person
  register with the reasoning attached to each rule. Do not propose rewriting it into
  generic documentation prose, and do not propose stripping the evidence merely because it
  is long — if you want it moved, say where to.

## What a good finding looks like

Ranked by expected value: `(quality gained + resource saved) ÷ cost to implement`.

Each finding gets:

- **Claim** — one sentence.
- **Evidence** — a file:line in `SKILL.md`, a computed number from the log, or a command
  and its output. A finding with no evidence is an opinion; mark it as one explicitly and
  rank it below the evidenced ones.
- **Impact** — which side of the quality/resource ratio it moves, and your estimate of the
  magnitude. Order-of-magnitude is fine; "unknown" is an acceptable and useful answer.
- **Proposed change** — concrete enough to act on. Where it is a `SKILL.md` edit, quote the
  replacement text.
- **Risk** — what it breaks, and what evidence would prove you wrong.

Group findings into: **architecture** (tier structure, control flow, decision rules),
**economics** (token and wall-clock cost per unit of progress), **robustness** (failure,
recovery, leaked state), and **authoring** (structure of the file itself). Open with the
three you would do first and a one-line reason for each; close with the things you checked
and found genuinely sound, because knowing what not to touch has value too.

## Non-goals

- Do not do a prose or grammar pass.
- Do not propose new agent tiers by default. The pipeline has five; adding a sixth needs to
  clear a high bar. Removing one is a legitimate finding.
- Do not propose anything you cannot ground in this repo — no "consider a vector database",
  no generic agent-framework advice.
- Do not run the pipeline, start a build, launch a render, or start `serve.py`. This is a
  read-and-analyse task. Read-only git commands and scripted extraction from the logs are
  fine; anything that writes to the repo is not.
