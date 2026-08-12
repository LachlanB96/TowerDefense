# The Gloomfell Suite — one coherent gallery app (design)

**Date:** 2026-08-12 · **Status:** approved (user approved section-by-section in session;
directed spec + implementation in one pass)

## Problem

The preview server hosts three pages from three skill eras that do not know about each
other. `index.html` (v1–v3 gallery) has the good viewer — side-by-side, pixel diff,
star/cross, directives — but reads `iteration-log.json`, which the v4 pipeline no longer
writes, so it renders stale data while a fleet is live. `live.html` is an unlinked side
page. `v4.html` (mission control) has the current data but is the least visual page:
text-only design lanes, no viewer, no reaction machinery, and no way to see what a
design looks like without hand-correlating run numbers.

Meanwhile the data on disk outgrew every page. `attempts.jsonl` records per-cell waves
and per-judge verdicts, including `margin` vs **origin** — which `record.py` documents
as the only real progress measure ("the ratchet") — and the judge's `suggestion` text.
None of it is displayed anywhere.

## Decision

Rebuild `v4.html` as **the suite**: a single self-contained app with three levels —
fleet overview → per-asset war room → design/attempt dossier — with the live feed and
the old `preview.py --variants` compare workflow as tabs inside the war room. The two
old pages become redirect stubs so nothing stale can ever be on screen.

Navigation model (user-selected): **war room is the resident screen; the dossier is a
slide-over panel** on top of it (Esc closes), so ambient status never leaves the screen
on a second monitor. Fleet overview is a compact route visited occasionally; the fleet
strip in the top bar is always present.

## Non-goals

- No rendering of v1–v3 `iteration-log.json` (old passes remain reachable through the
  Compare tab's run history only).
- No server-side computation; the server stays a static file host plus the three
  existing POST doors (`/chat`, `/signal`, `/directive`). No new endpoints.
- No schema changes to any state file; no new writers. `references/page.md` schemas
  stay byte-compatible.
- No queue reordering, no verdict streaming (blind judging stays blind — verdicts
  appear only once they land), no light theme (dark-room use is deliberate).

## Architecture

One file: `Assets/Blender/_tools/gallery/v4.html` (vanilla JS, no external requests,
copied into the previews root by `serve.py` at startup — restart after editing).

### Routes (hash-based; `?asset=x` legacy param redirects to `#/a/x` on load)

| Route | View |
|---|---|
| `#/` | Fleet overview |
| `#/a/<asset>` | War room, Overview tab |
| `#/a/<asset>/live` | War room, Live tab |
| `#/a/<asset>/compare` | War room, Compare tab |
| `#/a/<asset>/d/<design>` | Dossier slide-over (over the war room) |

Unknown asset → fleet view with a note. The image viewer is a modal, not a route.

### Global chrome (every route)

- **Top bar:** brand · fleet strip (per asset: name, state pill, heartbeat-age chip,
  `✓ accepted · q queue · ⚑ staged` counters; click switches war room; `aria-current`
  marks focus) · **Needs-you bell** with a fleet-wide count · connection dot · chat
  toggle.
- **Chat dock:** collapsible right rail (340 px), persists across routes. User/
  supervisor bubbles, per-asset scope toggle, undelivered-message state, and the verb
  hint line **byte-identical** to the list in `page.md` and `SKILL.md`.
- **Red banner** only when the server itself misses 3 consecutive polls; last good
  state stays rendered.

### Fleet overview (`#/`)

Cards per asset: champion thumb (or placeholder), state pill, heartbeat, counters,
`fleet.json` note, staged flags. Assets present on disk (`assets.json`) but absent from
`fleet.json` — e.g. a manual `preview.py` target like knight000 — appear as a subdued
"not in fleet" row so their war room (and Compare tab) stays reachable. Plus the
aggregated **Needs-you inbox** as a list:
staged designs awaiting promote (from each `pipeline.json.staged[]`), stale heartbeats
(age ≥ 300 s while state is `run`), paused assets holding staged work. Every inbox item
links to its asset/card.

### War room — Overview tab

Cards top to bottom:

1. **Needs you** (rendered only when non-empty): each staged design with contact-sheet
   thumb (`run-NNN/v<cell>/_sheet.png`), margins, chips, and a **Promote** button.
   *Verb buttons never POST silently:* they pre-fill the chat input (`promote d02`) and
   focus it; the user presses Enter. Provenance stays "the user typed it".
2. **Champion:** sheet image (zoomable), label + clauses, seed, promoted-by, time, and
   the provenance quote. Below it a **lineage strip**: past champions from
   `attempts.jsonl` promotion lines (tolerant of the exact `kind`; hidden when absent).
3. **Designs board:** one card per active design — id, origin badge (`yours` /
   `agent`), status, attempt count, chips (amber), latest panel margins vs incumbent,
   **vs-origin ratchet** (latest value + sparkline across attempts), and a thumbnail
   per attempt (the judged cell's render; fallback chain judged-cell `hero_34.png` →
   `_sheet.png` → v1). Click anywhere → dossier.
4. **Queue:** read-only rows (id, origin, summary) + an "add design" button that
   pre-fills `add design <asset>: ` in chat.
5. **Makers:** chip row from `pipeline.json.makers[]` (`m1 · d61 a2 · rendering`).
6. **Events:** newest 15, relative times, monospace.
7. **Dials:** read-only `control.json` display — state, makers, panel, escalate_to,
   accept/reject margins, and the newest stamped note (truncated, title = full).
8. **NEW watermark** (ported from index.html): per-asset localStorage snapshot of
   attempt→verdict; unseen or verdict-changed rows get a NEW dot; "mark seen" commits;
   generation signature guards archive rotation.

### Dossier (slide-over, `min(720px, 60vw)`, focus-trapped, Esc/scrim closes)

Header: design id, origin, status, summary, chips, ratchet headline.
Body, newest attempt first — per attempt:

- Wave block: run number, tag, seed, `script_sha`, draw info (cells, az0), and the
  **cell grid** — every cell with label, clauses, chips, exit state (non-zero exit =
  error styling), the judged cell highlighted.
- **Verdicts:** one row per judge — prefer, signed margin, flip, judge id, and the
  full `suggestion` text (the actionable feedback, currently invisible anywhere).
- **Ratchet chart:** margin-vs-origin series across attempts (primary line), margin-
  vs-incumbent as secondary marks. If no `vs:"origin"` verdicts exist, show the
  incumbent series alone, labeled honestly ("no origin series recorded").
- **Star/cross** per attempt → existing `POST /signal` (`{asset, attempt, design, run,
  mark}`), reflected from `user-signals.jsonl` on poll.
- **Directive block** per attempt (rework / revert / resurrect + note, withdraw) →
  existing `POST /directive`, pending state read back from `user-directives.jsonl`.

### War room — Live tab

The tap feed (`live.json`), professionalized: sticky sub-header (total runs, unclaimed
count, stamp, filters: claimed-only · failures-only), newest 20 runs with **Load
more**, never all 400+. Each claimed run is labeled with its design/attempt (joined
from `attempts.jsonl` wave lines: run → `d61 a2`); unclaimed runs stay dashed/dimmed
with the "rendered, never attributed" explainer. Empty state = the exact `tap.py`
command.

### War room — Compare tab

The `preview.py --variants` workflow, first-class: reads `latest.json`; variant columns
with label, diff-vars block, renders, exit errors with stderr tail, seconds, and the
manifest's renderer fingerprint line. Past runs: collapsible sections fetched from
`run-NNN/manifest.json` walking back from the current run (≤ 12), plus a run-number
jump field. Empty state = the exact `preview.py` command.

### Viewer (modal on top of anything)

Filmstrip of the clicked context (attempt cells, run shots, variant renders, champion
lineage). Modes: single · side-by-side · pixel diff (canvas, threshold 24, amber
heat over the new render — ported from index.html). **Pin as compare base**: any image
can be pinned as A; side-by-side/diff then compare current against the pin (replaces
the old accepted-before-only rule). Dimension-mismatch → warning, side-by-side still
allowed. Keyboard: `← →` navigate, `1/S/D` modes, `Esc` close, `?` shortcuts dialog.

## Data contract (reads — all existing files, no writer changes)

| File | Cadence | Notes |
|---|---|---|
| `fleet.json` | 5 s | fleet strip + overview cards |
| `assets.json` | 5 s | discovery of on-disk assets not in the fleet |
| `<focused>/pipeline.json` | 1 s | war room; heartbeat drives staleness UI |
| every other asset's `pipeline.json` | 5 s | strip heartbeats + inbox |
| `<focused>/live.json` | 1 s while the Live tab is mounted; not fetched otherwise | run feed |
| `<focused>/champion.json` | 5 s | champion card |
| `<focused>/attempts.jsonl` | HEAD content-length+mtime gate every 5 s; GET only on change | dossier, ratchet, run attribution, lineage |
| `<focused>/control.json` | 5 s | dials card (read-only) |
| `<focused>/user-signals.jsonl`, `user-directives.jsonl` | 5 s | reflect marks/pending directives |
| `chat.jsonl` + `feed.jsonl` | 1 s | merged by `at`, ties user-first, last 200 |
| `<focused>/latest.json`, `run-NNN/manifest.json` | 1 s (Compare tab mounted); manifests memoized permanently | compare workflow |

Attempts parsing: tolerate torn final line; skip unknown `kind`s; join `kind:"wave"`
(design, attempt, run, cells[]) with `kind:"verdict"` (run, cell, vs, prefer, margin,
flip, judge, suggestion) on run. Margin sign is toward the challenger. Cell `n` maps to
variant directory `v<n>`. `pipeline.json.state` may be absent — fleet state wins, then
pipeline, then control.

Images are immutable once written: never cache-busted, `loading="lazy"`, `onerror` →
placeholder/fallback chain. JSON/JSONL always `?t=` cache-busted (existing rule).
Renders are signature-guarded (skip DOM work when the underlying slice didn't change);
lanes/cards patch keyed by id so images never flicker or restart loads.

## Writes from the page (existing doors only)

- `POST /chat` — the chat form. Verb buttons only pre-fill the input.
- `POST /signal` — star/cross (dossier, staged cards).
- `POST /directive` — rework/revert/resurrect/withdraw (dossier).

## serve.py (two small changes, no behavior change otherwise)

1. `PREVIEW_ROOT` honors env override `GLOOMFELL_PREVIEW_ROOT` (testing against
   scratch data without touching the live previews root).
2. Startup print names the suite: `suite: http://localhost:8777/v4.html`.

It keeps copying `index.html`, `live.html`, `v4.html` at startup; the first two become
stubs (below).

## Redirect stubs

`gallery/index.html` and `gallery/live.html` shrink to no-JS-required stubs:
`<meta http-equiv="refresh">` to `/v4.html` plus a script that maps `?asset=x` →
`/v4.html#/a/x` (and `live.html?asset=x` → `/v4.html#/a/x/live`) before the meta fires.

## Failure modes

- Missing file = **empty state naming the missing producer and the exact command**
  (tap, preview.py, "supervisor not running — no fleet.json").
- Red banner reserved for the server missing 3 polls; keep last good state.
- Heartbeat chip amber ≥ 90 s, red + "stuck?" ≥ 300 s, **only** while that asset is
  `run` (a stopped pipeline's old heartbeat is expected).
- Torn JSONL final lines skipped; half-written JSON keeps the previous good parse.
- Unknown fields/kinds ignored everywhere. No render path may throw on absent data.

## Visual system

Keep the dark token family (no pure white — dark-room use); tighten into a real scale:
spacing on a 4/8 px grid, radii 4/6/10, type 11/12/13/15 with tabular numerals for all
counters, uppercase micro-labels for card titles, one accent, existing semantic status
hues (ok/warn/dead/shelf/pend). Status is always triple-encoded: color + glyph + text.
`:focus-visible` everywhere; `prefers-reduced-motion` respected; skip link; `aria-live`
announcements edge-triggered (port `announce()`); dialogs focus-trapped. Charts follow
the dataviz skill (load before implementing the ratchet chart/sparklines).

## Docs to update in the same change

- `references/page.md`: rewrite "Page behaviour the tools rely on" (routes, tabs,
  cadences, HEAD gate, stubs, verb-button pre-fill rule). **Schemas section untouched.**
  The chat-verb list stays byte-identical in its three homes (page.md, SKILL.md table,
  page hint line).
- No change to SKILL.md pre-flight (URL `v4.html` unchanged, still must return 200).

## Verification

1. `python Assets/Blender/_tools/selftest.py` still passes.
2. Scratch-root server (`GLOOMFELL_PREVIEW_ROOT` + port 8778): empty root; asset with
   only `pipeline.json`; torn final JSONL line; missing images — every state renders,
   zero console errors. POST doors exercised **only** against the scratch root.
3. Read-only pass on the live previews root (port 8778): fleet (mage000 run +
   evilMage000 paused with staged card + champion), war room, dossier (mage000 d61,
   evilMage000 d02), Live tab (416 runs → 20 + load more), Compare tab (knight000
   `latest.json`), viewer modes incl. pixel diff. Screenshot review of every route;
   console clean.
4. Keyboard-only walk: strip → tabs → lane → dossier → viewer → chat, Esc unwinds.
5. Restart the real server; `Invoke-WebRequest http://localhost:8777/v4.html` returns
   200; `/` and `/live.html` land on the suite; live fleet undisturbed (tap and
   shepherds never depend on the server).
