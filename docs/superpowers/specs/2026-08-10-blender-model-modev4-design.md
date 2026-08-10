# Blender Model Mode v4 — design spec

**Date:** 2026-08-10 · **Status:** approved by the user (this conversation, "Approve all")
· **Supersedes nothing:** v1/v2/v3 skills remain invocable; v4 is a new skill.

## 1 · What this is

`/blender-model-modev4` — an agentic workflow for continuous, autonomous improvement of
Gloomfell's Blender models. The user's requirements, verbatim in intent:

1. **Create a new model** — from a user description when given; otherwise invent one
   informed by the other models' descriptions in the project.
2. **Iterate on an existing model** — new details and features, plus modification of
   current ones. Every addition is reviewed by **multiple reviewers**, who can **scrap**
   the design, **send it back** to the modifier with their feedback, or **accept it as a
   new change**.
3. **Live output of everything happening** in a modern styled web page.
4. **A chat interface with the user** that can tell the workflow to stop, add a design
   to the list, and generally steer.

Plus the scaling requirement, given when choosing the architecture: *"At one point I
might want to be working on 4 different models, and even have 2 agents on the same
model. If I wanted to have 10 agents on 1 model I should be able to as well. I might
also want to create 10 npcs quickly."* Use as many agents as needed, but never
wastefully.

## 2 · Decisions taken with the user (2026-08-10)

| Question | Decision |
|---|---|
| Reviewer accept power | **Autonomous.** Panel accepts land immediately and become the new baseline; the user can rework/revert afterwards via page or chat. This deliberately reverses v3's user-only-promoter rule. |
| Chat location | **In the web page.** Terminal steering continues to work, but the page chat is the primary channel. |
| v3's three laws | **All stand.** (1) Never think about Unity — the model is a model. (2) Size is unknown and may change drastically — no pixel-size rules anywhere. (3) No privileged camera — judging uses the seeded 360° orbit stimulus. |
| New model with no description | **Invent and go.** The workflow writes its own concept brief (labelled agent-authored), announces it in chat, and starts building. The user redirects via chat; nothing blocks on them. |
| Architecture | **Fleet of per-asset pipelines; the unit of concurrency is the design, not the file.** Approved in full, sections 1–7 of the presented design. |

## 3 · Laws and carried rules

These are load-bearing constraints, most of them paid for in prior sessions
(receipts: `.claude/skills/blender-model-modev2/references/evidence.md`).

- **The three v3 laws** (above) appear in every brief. Any rule a different size or
  camera would falsify is a rendering preference, not a fact — delete it.
- **Never save, export, or treat a model as finished** until the user says **finish**
  for that asset. Until then every build is a preview. The `# --- variant hook ---`
  interlock in `preview.py`/`build_one.py` is never loosened or bypassed.
- **The 2-slot machine-wide GPU render semaphore is a safety limit, not a throughput
  knob.** At high maker counts, waves queue. Never raised to buy speed; the user may
  set `GLOOMFELL_RENDER_SLOTS` on a machine with headroom.
- **Blind pairwise comparison with a 0–3 margin is the judging instrument.** Two
  absolute scales collapsed before it; it is the only one that passed a calibration
  probe. No scores, no rubrics, no added criteria in judge briefs.
- **Mechanism beats prose.** Every rule that can be a template slot, a derived value,
  a semaphore, or a tool refusal becomes one.
- **Provenance:** every verdict names its judge and source; agent-authored designs are
  labelled as such; `control.json` notes are date-and-author stamped; an instruction
  that cannot be attributed is never acted on and never undone — ask the user.
- **Front-loading:** child agents read only (a) a file they must edit and (b) images
  they must look at. Everything else arrives inlined in their brief.
- **UTF-8 on every state-file read/write** (Windows defaults to cp1252).
- **`_previews~` keeps its trailing tilde.** Builds go through `blender -b -P`, never
  MCP. Modifiers stay live, never applied. Characters face −Y, Z-up, origin between
  the feet. `python Assets/Blender/_tools/selftest.py` after any `_tools/` change.

## 4 · Topology

```
YOU ── web page: live feed + chat ──────────────────┐
 │                                                  │
 ▼                                                  ▼
SUPERVISOR (main session)                     serve.py :8777
  fleet control · chat · genesis · incidents        ▲
  │ one per active asset                            │ state json/jsonl
  ▼                                                 │
SHEPHERD agent  ×N assets ───── publishes ──────────┘
  design queue · dispatch · panels · accept/bake · records
  │ one per in-flight design                │ fresh per verdict
  ▼                                         ▼
MAKER agent  ×M per asset (1..10)      REVIEWER ×2–3
  rows · critique consumption            blind pairwise, margin 0–3
  bakes accepted clauses                 accept / send-back / scrap
```

**Supervisor** — the main Claude session. Owns the chat (watches `chat.jsonl`, replies
into `feed.jsonl`), spawns and monitors shepherds (background agents, resumed by id
when quiet — respawn only if resume fails), runs genesis for new assets, handles
crashes, orphans and provenance disputes. Never designs, models, or judges quality.

**Shepherd** — one background agent per active asset; the only coordinator for that
asset. Loop: read `control.json` + queue → keep makers dispatched → convene panels on
returned waves → apply the decision rule → serialize bakes → write records as they
happen → stamp `heartbeat` → publish `pipeline.json`. All state on disk; crash-resume
by reconciling records against run directories before dispatching anything
(rendered-but-unjudged waves are judged first).

**Maker** — one per design, persistent across that design's attempts (builders need
continuity; judges need freshness). Proposes clause rows over real genes, renders
waves through the existing toolchain, consumes reviewer suggestions via `refine.py`,
contests panel claims only with measurements, and — on accept — bakes the winning
clauses into the asset script.

**Reviewer** — spawned fresh for every verdict, never resumed, never told what changed.
Receives the `judge.py` blind brief (character summary + two contact sheets under one
orbit draw) and answers in presentation terms (A/B/TIE + margin + WORKS/PROBLEMS/
SUGGESTION). The shepherd decodes and records through `judge.py --answer`.

**Concurrency dials** — per-asset `control.json`: `makers` (default 2, 1..10), panel
size (default 2, escalating to 3), wave cap (≤ 8 cells). Fleet-level `fleet.json`:
max concurrently active assets (default 4). All user-tunable via chat.

## 5 · The design lifecycle

1. **Claim.** A maker claims the oldest unclaimed design from `design-queue.jsonl`
   (user-added via chat, or generated: when the queue runs dry the shepherd spawns a
   cheap text-only designer batch that reads the standing brief digest and appends
   agent-authored design specs).
2. **Row.** The maker writes a row spec — named clauses over real genes — checking
   names with `genes.py --check`/`--find`. Refusals are honoured; `patch` is the
   documented escape hatch for derived genes, never a way around a refusal.
3. **Wave.** `axis.py` expands clauses factorially (cell 1 = all-off baseline) and
   draws the orbit seed; `preview.py --variants wave.json --tag <maker> --design <id>`
   renders all cells in parallel under the GPU cap, composites sheets, runs chips,
   and opens the attempt record. The maker reports run number the moment it starts.
4. **Triage.** If the intended winning cell measures `inert` (silhouette IoU vs cell 1
   above threshold in every view), the shepherd bounces it straight back to the maker —
   judges are never spent on render noise. Other chips ride along as flags.
5. **Panel.** The shepherd picks the wave's best cell (maker nominates; shepherd may
   also panel a second cell if the maker flags a genuine rival) and convenes 2 fresh
   reviewers: challenger vs **cell 1**. Invariant: **the champion is always the baked
   script**, so cell 1 of every wave *is* the incumbent — every comparison is in-wave,
   same seed, always fair, and no cross-wave pairing can exist.
6. **Decision** (§6) — accept, send back, or scrap.
7. **Arc policy.** `refine.py` governs the design's life: refine / redesign / abandon /
   **report at attempt 8** — past 8 the call is the user's, asked in chat and on the
   page. Scrapped and abandoned designs are shelved, never deleted.

## 6 · Verdict protocol and decision rule

Signed margin `s` points toward the challenger. Thresholds live in `control.json`
(defaults: `accept_margin +2`, `reject_margin −2`, `panel 2`, `escalate_to 3`) — never
hardcoded.

| Panel of 2 says | Outcome |
|---|---|
| both `s ≥ +2` | **accept** (§7) — unless a `blocks_auto` chip fired on the winning cell, in which case the attempt is **staged**: visible on the page as "panel accepted — chip X fired", waiting for the user's promote/reject; the maker moves on meanwhile |
| both `s ≤ −2` | **scrap** — the idea is wrong, not the execution; shelve it |
| both `|s| ≤ 1` (ties included) | **send back** — resume the same maker with the `refine.py` packet: every SUGGESTION verbatim, agreement counted, at most three points acted on |
| any other split (exactly one verdict beyond ±2, or opposed signs at ≥ 2) | **escalate**: one more fresh reviewer, fresh coin flip; accept/scrap then need 2 of 3 beyond the respective margin, else send back |

A tie always loses to the incumbent — margin 0 is never a resting state. Reviewers'
GEO-type claims (position, size, occlusion, material cause) reach the maker only as
MEASURE-BEFORE-ACTING items; a refuted claim is recorded and never re-issued while the
region is unchanged. Makers may contest any point **with a measurement, never an
opinion** (measured contests of unanimous panels ran 5/5 correct).

**The ratchet.** v3 needed two series (vs a moving incumbent, vs a fixed origin)
because promotions were unbaked overlays and the incumbent could move mid-arc. In v4
the incumbent is the baked script and **send-backs never bake**, so within one
`script_sha` era the incumbent is fixed and the panel's vs-incumbent margins *are* the
ratchet — no separate origin verdicts are taken (one fewer judge call per wave, and
the walking-in-circles failure cannot occur against a fixed baseline). When another
design's bake changes the script, the era ends: **stall/abandon counters re-anchor to
the design's first wave on the new `script_sha`**, while the attempt count for
report-at-8 spans eras. (`record.py` already stamps `script_sha` per wave and warns on
change; `refine.py` learns to partition by era — §11.)

## 7 · Acceptance, baking, and the baseline

On accept:

1. The **maker bakes** the winning clauses into `blender_<asset>.py` (fold `vars` into
   the gene defaults; land `patch` builders as real code).
2. The **shepherd verifies the bake**: re-render the baked script (cell-1-only wave,
   same seed) and compare against the winning cell's renders — near-identical or the
   bake is wrong and goes back to the maker.
3. The shepherd **commits** to the `model/<asset>` branch (created from the current
   base at pipeline start), message carrying design id + attempt. The commit is the
   accepted state; the user's working copy and `main` are never touched. Merging to
   `main` happens at *finish*, as the user's call.
4. `record.py --promote` records the new champion with `by: "panel"` and the panel's
   margins as the quote. User directives (rework / revert / resurrect from the page)
   **outrank any panel verdict** and are acknowledged in the records the cycle they
   are seen. A user promotion of a **staged** attempt (§6) and a resurrect of a
   shelved design both go through this same bake-verify-commit path — the champion
   never exists as an unbaked overlay.

**Bakes are serialized per asset — the only lock in the system.** Concurrent designs
are unaffected at proposal time (rows are JSON overlays, zero merge surface). After a
bake, every other in-flight design's next wave automatically re-renders on the new
baseline. If the accepted change touched genes or builders that another in-flight
design's row also touches, the shepherd flags the overlap and that design's next
verdict is a fresh re-judge — the v2 re-judge-on-rebase rule, now costing one wave
render instead of a git merge. Where possible the shepherd avoids dispatching two
designs onto heavily-overlapping gene sets at the same time (soft region reservation
from the gene map), but overlap is legal and resolved by sequencing bakes.

On *finish* (per asset): stop the shepherd → real build
(`blender -b -P blender_<asset>.py -- save export render`) → prune asset facts →
final report (accepts, margin story, panel-vs-user signal agreement, shelf contents).

## 8 · Genesis — new models, and the 10-NPC case

Triggered from chat (`new <name>: <description>`, `new hero`, `new 10 npcs`) or at
skill startup.

1. **Concept.** A concept agent reads the Obsidian vault (existing heroes, towers,
   tone: the deliberate grim/silly clash) and — when the user gave a description —
   extrapolates it, otherwise invents. It writes the concept brief to
   `Obsidian/TD/Heroes/<Name>.md`, `Obsidian/TD/NPCs/<Name>.md` (new folder), or
   `Towers/<Name>/Base.md`, **labelled agent-authored**, announces it in chat, and
   registers the asset (`<name>000` code convention; towers use path-tier codes).
2. **Scaffold.** A maker creates `Assets/Blender/blender_<asset>.py` **conforming from
   birth**: tunables as module globals, single top-level build call, the variant-hook
   block, `render_view()` honouring `RENDER_ONLY`/`SAMPLE_SCALE`, save/export behind
   `DO_SAVE`/`DO_EXPORT`, an `EXTRA_VIEWS` orbit loop and quarter-res `_mask.png`
   silhouette passes (pattern lifted from `blender_mage000.py`, minimal form in a v4
   template), plus per-asset orbit framing constants (`dist`, `aim_z`). The script is
   git-tracked immediately (v2 pre-flight lesson).
3. **Conformance smoke.** The shepherd renders a cell-1-only wave and checks: hook
   present, orbit views render, masks render, `genes.py` map is non-trivial. Only then
   does the asset enter normal cycles.
4. **Blockout.** The maker builds a rough blockout as design d01 via normal waves, then
   the pipeline iterates as usual.

**Batch mode** (`new 10 npcs`): ten pipelines with a small per-asset budget (default:
blockout + 3 accepted refinements, then auto-pause with a chat report), admitted
through the fleet cap (default 4 active at once, the rest queued). GPU queueing makes
this safe; the page's fleet strip makes it visible.

## 9 · Mission control — the live page and chat

A new `v4.html` served by `serve.py` alongside the existing pages (which keep
working for old assets). Same dark, modern aesthetic and conventions as
`live.html`/`index.html`: static single file, no external requests, tiny-element-
builder pattern (no innerHTML injection), localhost only, restart server after page
edits (it copies pages at startup).

Zones:

- **Fleet strip** (top): one card per active asset — status pill (run/pause/stop),
  makers in flight, queue depth, accepts count, heartbeat age (stale = amber warning).
  Click to focus an asset. `?asset=` deep-links.
- **Asset view**: live render feed (every run including unclaimed intermediates —
  tap.py's discard-visibility principle), design lanes (per-design story: attempts,
  signed margins, verdicts, chips, staged-awaiting-user cards, shelf), and the current
  champion large with its provenance (who promoted, when, quote).
- **Chat panel** (persistent): the user ↔ supervisor conversation. Free text; the
  documented verbs the supervisor guarantees to understand: `stop` / `pause` /
  `resume` (fleet or `<asset>`), `add design <asset>: <text>`, `new <hero|npc|tower>
  [<name>] [: <description>]`, `new N npcs`, `status`, `makers <asset> N`,
  `finish <asset>`, plus free questions. Everything else is interpreted in context.
  Existing star/cross signals and rework/revert/resurrect directives stay as they are
  (separate files, separate doors — instructions never share a channel with taste
  data).

Data flow: the page polls static JSON/JSONL only; the server never computes.
`POST /chat` appends `{at, text}` to the fleet-level `chat.jsonl` (validated,
size-capped, same pattern as `/signal`). The supervisor watches that file (Monitor/
wakeup loop), acts, and appends replies to `feed.jsonl`, which the page merges with
the user's messages into one conversation. Shepherds publish `pipeline.json` per
asset; a tap process (extended `tap.py`) publishes per-asset `live.json` from disk
truth; the supervisor maintains `fleet.json`. Chat latency is one supervisor wakeup
(seconds), and pipelines never block on it.

## 10 · State files

Per asset under `_previews~/<asset>/` unless noted. All append-only where feasible;
atomic replace elsewhere; UTF-8 always.

| File | Writer | Content |
|---|---|---|
| `attempts.jsonl` | shepherd via `record.py` | waves, verdicts (judge/source/margin/flip/seed/against), promotions — the durable record |
| `champion.json` | `record.py --promote` | current champion + provenance (`by`: panel/user, quote) |
| `design-queue.jsonl` | supervisor (user adds), shepherd (agent designs; labelled) | `{id, at, origin: user/agent, spec, status}` |
| `control.json` | supervisor only (user's channel) | state run/pause/stop, makers, panel, thresholds, stamped notes |
| `pipeline.json` | shepherd | live digest for the page: designs, makers, staged cards, last verdicts, heartbeat |
| `live.json` | tap process | run directories + shots, claimed/unclaimed |
| `asset-facts.md` | shepherd curates | mechanical facts only, substitution-tested, capped, regenerated per session |
| `Assets/Blender/_chars/<asset>.invariants.md` | user (+ genesis starter, labelled) | character invariants measured as chips |
| `shelf/<design-id>.json` + renders | shepherd | scrapped/abandoned designs: row spec, verdicts, final wave pointer — resurrectable by re-rendering against the current baseline |
| *(fleet level, `_previews~/`)* `fleet.json`, `chat.jsonl`, `feed.jsonl` | supervisor / page POST / supervisor | fleet registry + the conversation |

Git: accepted state lives on `model/<asset>` branches; shelved design specs are
committed (survival is the point); `main` is only touched by the user at finish.

## 11 · Tooling deltas (exhaustive — everything else is reused as-is)

1. `serve.py`: add `POST /chat` (validate, cap, append fleet `chat.jsonl`); serve
   `v4.html`; everything else unchanged.
2. `gallery/v4.html`: new page (§9).
3. `tap.py`: multi-asset mode (or a thin `fleet-tap` wrapper) so one process publishes
   `live.json` for every active asset.
4. `preview.py`: fix the `next_run_dir` allocation race (two concurrent makers can
   currently claim the same run number — `exist_ok=False` + retry).
5. `record.py`: allow `promote(by="panel")` (docstring currently says human-only —
   the user's directive channel keeps outranking); helper to partition a design's
   waves by `script_sha` era (for §6 re-anchoring).
6. `refine.py`: read the vs-incumbent series as the ratchet, era-partitioned;
   stall/abandon evaluate within the current era; report-at-8 spans eras.
7. New `_tools/scaffold.py` (or template file): the conforming-from-birth new-asset
   skeleton with orbit `EXTRA_VIEWS` + mask passes (§8.2).
8. `selftest.py`: extend to cover the new/changed pieces; it runs after any `_tools`
   change.

## 12 · Skill packaging and who reads what

```
.claude/skills/blender-model-modev4/
  SKILL.md                 — supervisor manual (the only file the main session reads)
  references/shepherd.md   — shepherd's complete operating manual
  references/maker.md      — maker discipline: rows, genes, baking, contesting
  references/reviewer.md   — how the shepherd briefs/records reviewers (reviewers
                             themselves read nothing; their brief is judge.py output)
  references/page.md       — page + chat protocol and state-file contracts
```

Frontmatter mirrors prior versions: invoke ONLY on explicit `/blender-model-modev4`;
never auto-invoke. On invocation the supervisor asks its two questions (what to work
on — which may be several assets and/or new ones — and a loose brief each), starts
the server + tap, tells the user the URL in plain words, pre-flights (tracked script,
stale state, gallery answering via HTTP check, control.json present), then spawns
shepherds and enters the chat loop. Shepherds read `shepherd.md` and nothing else;
makers and reviewers read no skill file ever — their briefs are self-contained, with
the maker reading only the asset script it edits and reviewers reading only their two
sheets.

## 13 · Cost discipline

- Per attempt: one maker turn + one wave (≤ 8 renders ≈ ~7 s each through 2 GPU
  slots) + 2–3 reviewer calls, each reading one or two contact sheets. No context
  reconstruction: briefs are front-loaded; makers persist per design.
- Reviewers and text-only designers are cheap, short-lived agents; shepherd context is
  bounded by writing state to disk instead of holding it.
- Queue top-ups are small batches (3–5 design specs), not floods. An idle maker is
  refilled; ten makers are only spawned when the user dialled ten.
- Waves are the breadth mechanism — eight candidates cost eight renders and zero extra
  agent deliberation (the user's standing complaint about variant dithering).

## 14 · Failure and recovery

- Shepherd heartbeats in `pipeline.json`; the page shows staleness; the supervisor
  resumes a quiet shepherd **by agent id** (context preserved), respawning fresh only
  if resume fails — a fresh shepherd reconciles records against disk before any
  dispatch, judging rendered-but-unjudged waves first.
- Run attribution is stamped at render time (`--tag`, `--design`), never self-reported
  after the fact; unattributable runs stay unattributed and visible as such.
- Orphaned makers/reviewers report to the supervisor (their parent may be gone);
  artifacts on disk (manifest, records) mean the work survives the handles.
- A torn JSONL line is tolerated by every reader; manifests and mirrors are written
  via temp-file + atomic replace with Windows sharing-violation retries (existing
  patterns, reused).

## 15 · Out of scope

Unity integration of any kind (law 1) — export/rig/prefab work happens outside this
workflow at the user's request. Changing the judge protocol or its thresholds' meaning.
Raising the GPU cap. Retrofitting the eight non-conforming legacy scripts (only assets
the workflow touches get conformed, via genesis or explicit user request). Multiplayer
of the gallery (it stays localhost, single-user).
