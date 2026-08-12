# Gloomfell Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `v4.html` as the single coherent gallery suite (fleet → war room → design dossier, with Live and Compare tabs and a universal viewer), retire the two stale pages to redirect stubs, and update the page contract doc.

**Architecture:** One self-contained vanilla-JS HTML file polling static JSON/JSONL from `serve.py` (which stays a dumb file host with three POST doors). Hash router over one state store; every render function is signature-guarded so the 1 Hz poll never rebuilds unchanged DOM. All new depth (dossier, ratchet, run attribution) comes from client-side joins over `attempts.jsonl` — zero writer/schema changes.

**Tech Stack:** Vanilla JS + CSS in a single file (no build, no CDN — the page must work offline), Python stdlib `http.server` (`serve.py`), Python for fixtures. Verification via a scratch-root server instance + Chrome (screenshots + console), since the repo has no JS test infra by convention.

**Spec:** `docs/superpowers/specs/2026-08-12-gallery-suite-design.md` (committed 66a16c3). The spec is the requirements authority; this plan is the build order.

## Global Constraints

- `v4.html` stays the file name and URL — the modev4 skill pre-flight requires `http://localhost:8777/v4.html` → 200.
- No external requests of any kind from any gallery page (offline, CSP-free file).
- Server computes nothing; only existing POST doors `/chat`, `/signal`, `/directive`. No new endpoints.
- All state-file schemas byte-compatible (`references/page.md` schemas section untouched).
- Chat verb hint line byte-identical in its three homes (page.md, SKILL.md table, page hint):
  `stop · pause <asset> · resume <asset> · status · add design <asset>: <text> · new <hero|npc|tower> [name]: <desc> · new N npcs · makers <asset> N · promote <design> · finish <asset>`
- Verb buttons pre-fill the chat input, never POST silently (provenance: user presses Enter). Exception: none.
- Images never `?t=` cache-busted (immutable once written); JSON/JSONL always cache-busted.
- Dark theme only, no pure white. Status always triple-encoded: color + glyph + text.
- Missing file = named empty state with the exact command to start the missing producer. Red banner = server missed 3 polls, keep last good state.
- Heartbeat: amber ≥ 90 s, red + "stuck?" ≥ 300 s, only while that asset's state is `run`.
- Never crash on absent/unknown data: torn JSONL final lines skipped, unknown `kind`s skipped, unknown fields ignored.
- A LIVE FLEET IS RUNNING (mage000). Do not restart the real 8777 server until the final task; test on port 8778. Never POST to the real previews root during testing. Do not touch `_previews~` state files by hand.
- Commit style: short lowercase messages, direct to `main` (repo convention). `git add` only files this plan names — the working tree has unrelated dirt.
- After any change in `_tools/`: `python Assets/Blender/_tools/selftest.py` must pass.

## File Structure

- `Assets/Blender/_tools/serve.py` — modify: env-overridable preview root, startup print.
- `Assets/Blender/_tools/gallery/v4.html` — rewrite: the suite (only gallery file with logic).
- `Assets/Blender/_tools/gallery/index.html` — replace with redirect stub.
- `Assets/Blender/_tools/gallery/live.html` — replace with redirect stub.
- `.claude/skills/blender-model-modev4/references/page.md` — modify: page-behaviour section only.
- `<scratchpad>/fixtures/make_fixtures.py` → generates `<scratchpad>/roots/empty/` and `<scratchpad>/roots/mini/` (session-only; not committed — the spec's verification section documents the procedure).

Inside `v4.html`, fixed section order (mirrors old index.html discipline):
`TOKENS · BASE · COMPONENTS · CHROME · FLEET · WARROOM · DOSSIER · LIVE · COMPARE · VIEWER · CHAT` (CSS), then script sections
`utils · router · net (fetch/HEAD-gate/poller) · attempts (parser+joins) · watermark · signals+directives · store · render-chrome · render-fleet · render-overview · render-dossier · render-live · render-compare · viewer · chat · boot`.

---

### Task 1: serve.py — preview-root override + suite banner

**Files:**
- Modify: `Assets/Blender/_tools/serve.py:26-28` (root), `:146-148` (print)

**Interfaces:**
- Produces: env var `GLOOMFELL_PREVIEW_ROOT` (absolute path) selects the served root; default unchanged. Every later task's test server depends on this.

- [ ] **Step 1: Implement the override + print**

```python
HERE = os.path.dirname(os.path.abspath(__file__))
# Overridable so a second instance can serve scratch fixtures on another port
# without touching the live previews root (testing; see the suite spec).
PREVIEW_ROOT = (os.environ.get("GLOOMFELL_PREVIEW_ROOT")
                or os.path.join(os.path.dirname(HERE), "_previews~"))
```

and in `main()` replace the print with:

```python
print("suite:   http://localhost:%d/v4.html   (index/live redirect here)" % PORT)
print("root:    %s" % PREVIEW_ROOT)
```

- [ ] **Step 2: Verify against a scratch root (server on 8778)**

```powershell
$env:GLOOMFELL_PREVIEW_ROOT = "<scratchpad>\roots\empty"; $env:GLOOMFELL_GALLERY_PORT = "8778"
Start-Process python -ArgumentList "Assets/Blender/_tools/serve.py" -WindowStyle Hidden `
  -RedirectStandardOutput "$env:TEMP\gf-suite-test.out" -RedirectStandardError "$env:TEMP\gf-suite-test.err"
Invoke-WebRequest http://127.0.0.1:8778/v4.html -TimeoutSec 5   # expect 200
Invoke-WebRequest http://127.0.0.1:8778/chat -Method POST -Body '{"text":"ping"}' -ContentType application/json
Get-Content "<scratchpad>\roots\empty\chat.jsonl"               # expect the ping line HERE, not in _previews~
```

Also confirm the real root default still works: run once with no env → printed `root:` ends in `_previews~`.

- [ ] **Step 3: selftest + commit**

Run: `python Assets/Blender/_tools/selftest.py` → PASS.
```bash
git add Assets/Blender/_tools/serve.py
git commit -m "serve: GLOOMFELL_PREVIEW_ROOT override and suite banner"
```

---

### Task 2: Fixture roots (scratchpad only, no commit)

**Files:**
- Create: `<scratchpad>/fixtures/make_fixtures.py`

**Interfaces:**
- Produces: `<scratchpad>/roots/empty/` (bare dir) and `<scratchpad>/roots/mini/` containing asset `alpha000` with every reader-visible file, including deliberate damage. Later tasks verify against these paths.

- [ ] **Step 1: Write the generator**

`make_fixtures.py` writes, under `roots/mini/`:

- `assets.json` → `["alpha000", "loose000"]` (loose000 = dir with only `latest.json` — the not-in-fleet case).
- `fleet.json` → one asset `alpha000`, `state:"run"`, makers 2, queue 1, accepted 1, staged 1, note.
- `chat.jsonl` (2 user lines) / `feed.jsonl` (2 supervisor lines, one with `asset`).
- `alpha000/pipeline.json` → heartbeat = generation time (fresh), one staged entry `{design:"d02",run:3,cell:2,margins:[2,2],chips:["INV-1 weight"],at:...}`, designs `d01` (attempts 2, last_margins [2,2], chips []) and `d02` (attempts 1, last_margins [1,2], chips ["INV-1 weight"]), queue `d03`, makers `[{id:"m1",design:"d01",attempt:3,status:"rendering"}]`, events (3, oldest first).
- `alpha000/attempts.jsonl` → `kind:"open"` line (unknown kind — must be skipped), wave d01 a1 run 1 (8 cells, cell 5 `exit:11`), verdicts run 1 cell 2: `vs:"incumbent"` margin +1 and `vs:"origin"` margin +1 with `suggestion` text; wave d01 a2 run 2, verdicts +2/+2 (incumbent) and origin +2; `kind:"promote"` line `{run:2,cell:2,at:...}`; wave d02 a1 run 3, verdict margin +1 flip 1 judge w2c with a long suggestion; **final line torn** (write `{"kind":"verdict","run":3` with no newline).
- `alpha000/champion.json` → run 2 cell 2, label, clauses, seed, `sheet:"v2/_sheet.png"`, by "panel", quote.
- `alpha000/control.json` → `{state:"run", notes:["2026-08-12 (supervisor): fixture note"], makers:2, panel:2, escalate_to:3, accept_margin:2, reject_margin:-2}`.
- `alpha000/live.json` → runs 3,2,1: run 3 `claimed:true, tag:"m1", done:false`; run 2 claimed; run 1 `claimed:false` (unclaimed styling), each variant with shots pointing at the PNGs below.
- `alpha000/latest.json` → manifest shape from real knight000 (copy structure: run 3, variants with `n/label/diff/exit/renders/seconds`, one variant `exit:1, stderr_tail:"boom"`, `renderer:"OPTIX RTX"`), plus `alpha000/run-001..003/manifest.json` similar for history.
- PNGs: `alpha000/run-00N/v{1,2}/{hero_34.png,_sheet.png,front.png}` — distinct solid-color 32×48 PNGs (raw zlib, stdlib only) so side-by-side/diff have real pixels; run-002 v2 images a different color from run-001 v1 (diff must light up).
- `alpha000/user-signals.jsonl`, `alpha000/user-directives.jsonl` → absent on purpose (created by POSTs during tests).
- `loose000/latest.json` + `loose000/run-001/manifest.json` + one PNG.

- [ ] **Step 2: Generate and eyeball**

Run: `python <scratchpad>/fixtures/make_fixtures.py` then `ls -R <scratchpad>/roots/mini` — every path above exists; `python -c "import json;json.load(open('.../alpha000/pipeline.json'))"` parses.

No commit (session artifacts).

---

### Task 3: v4.html skeleton — tokens, chrome, router, poller, chat, banner

**Files:**
- Rewrite: `Assets/Blender/_tools/gallery/v4.html` (from scratch; keep a copy of the old file in scratchpad for porting reference — git has it anyway)

**Interfaces:**
- Produces (later tasks rely on these exact names):
  - `h(tag, attrs, ...kids)` element builder; `$(id)`; `q(path)` cache-buster (JSON only); `esc` not needed (no innerHTML with data — keep it that way).
  - `S` store: `{route, fleet, assetsOnDisk, pipes:Map, control, live, champion, attempts, chat:[], marks:Map, dirs:Map, seen, failures, tick}`.
  - `parseRoute()/applyRoute()/nav(hash)`: route object `{view:'fleet'} | {view:'asset', asset, tab:'overview'|'live'|'compare', design|null}`; legacy `?asset=x` → `#/a/x` via `location.replace` on boot; `live.html`-style deep link `#/a/x/live` works.
  - `sig(key, value)` — JSON-signature guard, per-render-region.
  - `jget(url)` (null on !ok), `tget(url)`, `headSig(url)` → `"len|mtime"` or null.
  - `postJSON(path, body)` → bool ok.
  - `tickLoop()` cadences: focused pipeline + chat/feed 1 s; fleet/assets/champion/control/signals/directives + non-focused pipes 5 s; attempts via `headSig` gate 5 s; live 1 s only when `route.tab==='live'`; compare fetches only when `route.tab==='compare'`.
  - Chrome DOM ids: `#bar` (top bar), `#strip` (fleet cards), `#bell` (needs-you count button), `#dot`, `#net` (banner), `#main`, `#chat`, `#chat-in`, `#chat-form`, `#chat-scope`, `#verbs`.
  - `prefillChat(text)` — sets `#chat-in` value, focuses, opens dock if collapsed.
  - CSS tokens exactly: `--bg --s1 --s2 --s3 --line --line2 --ink --ink2 --ink3 --accent --ok --warn --dead --shelf --pend --mono --r1 --r2 --r3` and spacing `--sp1..--sp5` (4/8/12/16/24). Type sizes 11/12/13/15 only. Class contracts reused everywhere: `.card .chip .badge .pill .empty .mono .num .dim .faint .imgbtn .noimg`.
- Consumes: Task 1 server; Task 2 fixtures.

- [ ] **Step 1: Head comment + CSS (TOKENS/BASE/COMPONENTS/CHROME/CHAT) + static DOM shell**

Head comment: purpose, RESTART-THE-SERVER warning, data contract table (same files as spec), pointer to page.md and the spec. Shell: skip link → `#bar` (brand `GLOOMFELL · SUITE`, `#dot`, `#strip`, spacer, `#bell` ⚑ (hidden at 0), chat toggle) → `#net` banner → `#wrap` grid (`#main` + `#chat` aside) → dialogs (added by later tasks). Chat dock ported from old v4.html (bubbles, scope toggle, undelivered rows, verbs hint line **byte-identical** per Global Constraints, hide/show via localStorage `gf-suite-chat`, mobile bottom-sheet media query). Reduced-motion + `:focus-visible` rules in BASE.

- [ ] **Step 2: Script — utils, router, net, store, boot**

Router per Interfaces. Poller: single `tick()` with re-entrancy latch (`ticking`); `S.failures>=3` → `#dot.err` + `#net.on`, else clear; every fetch that resolves after a route change is discarded by comparing a captured `S.route.asset`. `refreshTimes()` walks `[data-ts]` (port `fmtRel/timeEl` from old v4.html verbatim). `render()` dispatches by route: chrome always; view functions stubbed as labeled `.empty` cards for now ("fleet view — task 6" etc.).

- [ ] **Step 3: Verify on fixtures + damage cases**

Server on 8778 → mini root, in Chrome:
- `/v4.html` → fleet stub renders; `#/a/alpha000` → war-room stub; `/v4.html?asset=alpha000` → URL becomes `#/a/alpha000`; `#/a/alpha000/live` survives reload.
- Chat: send "hello" → bubble renders, line lands in mini root `chat.jsonl`; supervisor lines from `feed.jsonl` interleave by `at`; kill server → 3 ticks → red banner + undelivered row on send; restart → recovers.
- Console: zero errors including during the killed-server window.

- [ ] **Step 4: Commit**

```bash
git add Assets/Blender/_tools/gallery/v4.html
git commit -m "suite: skeleton - tokens, chrome, router, poller, chat dock"
```

---

### Task 4: Data layer — attempts parser, joins, watermark, signals/directives readers

**Files:**
- Modify: `Assets/Blender/_tools/gallery/v4.html` (script sections `attempts`, `watermark`, `signals`)

**Interfaces:**
- Produces:
  - `parseAttempts(text)` → `{designs: Map<designId, Attempt[]>, byRun: Map<run, {design, attempt}>, promos: Promo[]}` where `Attempt = {attempt, run, tag, seed, scriptSha, at, draw, note, cells:[{n,label,clauses,chips,exit}], verdicts:[{at,cell,vs,prefer,margin,flip,judge,suggestion,note}]}` sorted by (attempt, run). Unknown kinds and unparseable lines skipped. Verdicts joined on `run`.
  - `judgedCell(attempt)` → most-frequent `verdicts[].cell` or null.
  - `marginSeries(attempts, 'origin'|'incumbent')` → `[{attempt, mean}]`, sign toward challenger; missing `vs` counts as incumbent; empty → [].
  - `signedMean(verdicts)` → per the pairwise convention: `prefer==='challenger' ? +margin : -margin` averaged (margins in files are already signed toward challenger when `prefer` is absent — tolerate both by: if `prefer` present, apply sign; else use raw).
  - `runDir(n)` → `'run-' + String(n).padStart(3,'0')`; `cellDir(n)` → `'v'+n`.
  - `thumbSrcs(asset, run, cell)` → ordered fallback array `[hero_34, _sheet, v1/hero_34]` full paths; `imgFallback(imgEl, srcs)` walks it on error, ends in `.noimg` swap.
  - Watermark: `loadSeen(asset, attemptsParsed)`, `isNewRow(seen, key, verdictSig)`, `commitSeen(...)`; row key `` `${design}·a${attempt}·r${run}` ``; generation sig = first wave's `design|run` + first verdict's `at`; storage `gf-seen-<asset>`.
  - `pollSignals(asset)` / `pollDirectives(asset)` fill `S.marks: Map<rowKey, 'star'|'cross'>`, `S.dirs: Map<rowKey, {directive, note, at}>` (latest wins, withdraw deletes) from the two JSONL files; `sendSignal(asset, rowKey, design, run, mark)` and `sendDirective(asset, rowKey, design, run, directive, note)` POST to the existing doors and update the maps optimistically.
- Consumes: Task 3 `tget/headSig/S`.

- [ ] **Step 1: Implement** — parser core:

```js
function parseAttempts(text) {
  const waves = [], verdicts = [], promos = [];
  for (const line of (text || '').split('\n')) {
    if (!line.trim()) continue;
    let r; try { r = JSON.parse(line); } catch (e) { continue; }   // torn tail line
    if (r.kind === 'wave') waves.push(r);
    else if (r.kind === 'verdict') verdicts.push(r);
    else if (r.kind === 'promote' || r.kind === 'promotion' || r.kind === 'champion') promos.push(r);
    // any other kind: recorded for the pipeline, not for us — skip silently
  }
  const vByRun = new Map();
  for (const v of verdicts) {
    if (!Number.isFinite(v.run)) continue;
    if (!vByRun.has(v.run)) vByRun.set(v.run, []);
    vByRun.get(v.run).push({ at: v.at || null, cell: v.cell ?? null,
      vs: v.vs || 'incumbent', prefer: v.prefer || null,
      margin: Number.isFinite(v.margin) ? v.margin : null,
      flip: v.flip ?? null, judge: v.judge || '?',
      suggestion: typeof v.suggestion === 'string' ? v.suggestion : '',
      note: typeof v.note === 'string' ? v.note : '' });
  }
  const designs = new Map(), byRun = new Map();
  for (const w of waves) {
    const id = w.design || 'ungrouped';
    if (!designs.has(id)) designs.set(id, []);
    designs.get(id).push({ attempt: w.attempt ?? null, run: w.run, tag: w.tag || '',
      seed: w.seed ?? null, scriptSha: w.script_sha || '', at: w.at || null,
      draw: w.draw || null, note: w.note || '',
      cells: Array.isArray(w.cells) ? w.cells : [],
      verdicts: vByRun.get(w.run) || [] });
    if (Number.isFinite(w.run)) byRun.set(w.run, { design: id, attempt: w.attempt ?? null });
  }
  for (const list of designs.values())
    list.sort((a, b) => (a.attempt ?? 0) - (b.attempt ?? 0) || a.run - b.run);
  return { designs, byRun, promos };
}
```

`signedMean`: if any verdict has `prefer`, value = `prefer === 'challenger' ? margin : -Math.abs(margin)`… **no** — spec says margins are signed toward the challenger already; when `prefer` is present it names the winner and `margin` magnitude. Implement: `val = v.prefer ? (v.prefer === 'challenger' ? Math.abs(v.margin) : -Math.abs(v.margin)) : v.margin`. (mage000 real data: `prefer:"incumbent", margin:1` = challenger lost by 1 → −1.)

- [ ] **Step 2: Verify with the browser console against fixtures**

On `#/a/alpha000` run via DevTools/javascript_tool:
`__gf.attempts.designs.get('d01').length === 2`; d01 a1 has 8 cells, cell 5 `exit === 11`; `judgedCell(d01[0]) === 2`; `marginSeries(d01, 'origin').map(x=>x.mean)` → `[1, 2]`; torn final line did not throw (console clean); `byRun.get(3)` → `{design:'d02', attempt:1}`; promos length 1. (Expose `window.__gf = S` behind a `location.hash` no — just always: one line, harmless, aids future debugging.)
Then POST a star via UI-less call `sendSignal('alpha000','d02·a1·r3','d02',3,'star')` → line appears in mini `user-signals.jsonl`, `S.marks` updated, second call with 'star' clears (toggle semantics port from old index).

- [ ] **Step 3: Commit**

```bash
git add Assets/Blender/_tools/gallery/v4.html
git commit -m "suite: attempts parser, joins, ratchet series, watermark, signal doors"
```

---

### Task 5: Viewer modal — filmstrip, modes, pin-base, pixel diff

**Files:**
- Modify: `Assets/Blender/_tools/gallery/v4.html` (VIEWER css + `viewer` script)

**Interfaces:**
- Produces: `openViewer(items, idx)` where `items = [{src, caption, group?}]`; `pinBase(item)`; modal `<dialog id="viewer">` with `#v-stage`, `#v-strip`, mode radios single/side/diff, `#v-pin` toggle button, `?` shortcuts `<dialog id="shortcuts">`. Keyboard: `← → Home End` navigate, `1/S/D` modes, `P` pin/unpin current, `Esc` close (shortcuts dialog first), `?` help. Every image button in later tasks calls `openViewer` with its context list.
- Consumes: `h`, tokens.

- [ ] **Step 1: Implement** — port from old `index.html` (git show `HEAD:Assets/Blender/_tools/gallery/index.html`): `drawDiff` (threshold 24, amber heat, dimension-mismatch warning), dialog dismissal rules (`data-keep` + pointerdown outside interactive), focus restore on close event. Replace before/after logic with the pin: `A = pinned || previous item`, B = current; side/diff disabled (with tooltip) when no pin and no previous. Strip shows all `items` with `aria-current`.

- [ ] **Step 2: Verify on fixtures**

Open run-002 v2 image → strip navigation works; pin run-001 v1 → side-by-side shows both; diff lights amber (different solid colors); pin a 32×48 vs a mismatched size (use `_sheet.png` if different, else skip) → warning text, side still works; keyboard walk `→ → S D 1 P Esc`; focus returns to the opener button; console clean.

- [ ] **Step 3: Commit**

```bash
git add Assets/Blender/_tools/gallery/v4.html
git commit -m "suite: universal viewer - filmstrip, pin-base compare, pixel diff"
```

---

### Task 6: Fleet strip, fleet overview route, needs-you inbox

**Files:**
- Modify: `Assets/Blender/_tools/gallery/v4.html` (FLEET css + `render-chrome`/`render-fleet`)

**Interfaces:**
- Produces: `renderStrip()` (always-on top-bar cards: name, state pill `st-run/pause/stop/unknown` with pulse on run, hb chip via `hbAge` rules, `✓n · q n · ⚑n` nums, `aria-current` on focus, click → `nav('#/a/'+asset)`); `renderFleet()` (route `#/`): asset cards (champion thumb via `champion.json` fetch per asset at 5 s — reuse `S.pipes` cadence loop — name, pills, counters, `fleet.json` note, click-through), "not in fleet" subdued row for `assets.json` entries missing from `fleet.json` (skip `_`-prefixed like `_selftest_asset`), and `needsYou()` → `[{asset, kind:'staged'|'stale-hb'|'paused-staged', label, href}]` from all `S.pipes` + fleet states; `#bell` shows the count, click → `#/` scrolled to inbox.
- Consumes: Task 3 chrome/poller, Task 4 nothing.

- [ ] **Step 1: Implement** (heartbeat thresholds and pill classes exactly as Global Constraints; all counters `.num` tabular).

- [ ] **Step 2: Verify**

Fixtures: strip shows alpha000 (run, fresh hb, ✓1 q1 ⚑1); bell = 1 (staged d02); fleet route shows alpha000 card + `loose000` in "not in fleet" row; inbox row "alpha000 — d02 staged +2/+2, awaiting promote" links to `#/a/alpha000`. Doctor the mini `pipeline.json` heartbeat to −6 min → hb chip red + "stuck?" + inbox gains stale-hb row (then regenerate fixtures). Empty root on 8778: fleet route shows "no fleet running — waiting for the supervisor" empty state, no console errors.

- [ ] **Step 3: Commit**

```bash
git add Assets/Blender/_tools/gallery/v4.html
git commit -m "suite: fleet strip, fleet overview, needs-you inbox"
```

---

### Task 7: War room — Overview tab

**Files:**
- Modify: `Assets/Blender/_tools/gallery/v4.html` (WARROOM css + `render-overview`)

**Interfaces:**
- Produces: `renderOverview()` composing, in order: `cardNeedsYou` (staged: sheet thumb `runDir/v<cell>/_sheet.png` → viewer; margins chips; **Promote** button → `prefillChat('promote '+design)`; star/cross via Task 4), `cardChampion` (sheet image → viewer; label/clauses/seed/by/at + quote; lineage strip from `promos` ordered by `at`, thumbs via `thumbSrcs`, current highlighted), `cardDesigns` (per `pipeline.json.designs[]`: id, origin badge `yours/agent-authored`, status chip verbatim, `a<n>` count, amber chips, margin chips (`.m.pos/.neg/.mid` at ±2), ratchet headline `▲+2 vs origin` + sparkline over `marginSeries(...,'origin')`, attempt thumb row from `S.attempts.designs` joined by id (NEW dot via watermark), whole card → `nav(dossier)`), `cardQueue` (+ "add design" → `prefillChat('add design '+asset+': ')`), `cardMakers`, `cardEvents` (newest 15, `.at` mono times), `cardDials` (control.json read-only: state/makers/panel/escalate_to/margins + newest note, full note in `title`), "mark seen" pill in the war-room sub-header when NEW > 0.
- Consumes: Tasks 3–5 (store, parser, viewer, watermark, prefill).

- [ ] **Step 1: Load the dataviz skill, then implement**

Invoke `dataviz` before writing the sparkline/ratchet marks; apply its color/contrast rules to the status hues used in charts (single-series line, no legend, `aria-label` with the series values — same discipline as old index.html's sparkline).

- [ ] **Step 2: Verify on fixtures**

`#/a/alpha000`: needs-you shows d02 with thumb + Promote → chat input reads `promote d02` and is focused (nothing POSTed); champion card shows run-002 sheet + lineage 1 entry; d01 card: 2 attempt thumbs, ratchet `+2` with 2-point sparkline; d02: chips amber `INV-1 weight`, margins `+1 +2`; queue d03 + add-design prefill; makers `m1 · d01 a3 · rendering`; events 3 rows relative times; dials show `accept ≥ +2 · reject ≤ −2 · panel 2→3`; star d01 a2 from the card → flag renders, line in scratch signals file; "mark seen" clears NEW dots (localStorage survives reload). Console clean.

- [ ] **Step 3: Commit**

```bash
git add Assets/Blender/_tools/gallery/v4.html
git commit -m "suite: war room overview - needs-you, champion lineage, ratcheted design board"
```

---

### Task 8: Dossier slide-over

**Files:**
- Modify: `Assets/Blender/_tools/gallery/v4.html` (DOSSIER css + `render-dossier`)

**Interfaces:**
- Produces: route `{design}` non-null → `#dossier` (`<dialog>` styled as right slide-over, `min(720px,60vw)`, native focus trap, close = Esc/scrim/✕ → `nav('#/a/'+asset)` preserving tab). Content: header (id, origin badge, status, summary, chips, ratchet headline + chart); per attempt (newest first): wave header (`a2 · run 3 · tag m1 · seed · sha`, `data-ts` time), cell grid (chip per cell: `n label`, clauses mono, amber chips, `exit≠0` → `.dead` + exit code, judged cell ringed `--accent`, click → viewer with the attempt's rendered cells as items), verdict rows (judge id, prefer+signed margin chip, flip glyph `⇄`, suggestion as `.rep` block — full text, no truncation), star/cross + directive block (rework/revert/resurrect + note input + confirm/withdraw — port interaction from old index.html `directiveBlock`, keyed by rowKey). Ratchet chart: inline SVG ≤ 560×120, origin series as line+dots, incumbent means as hollow marks, zero axis line, `aria-label` listing values; absent origin series → incumbent only + `.faint` caption "no origin series recorded".
- Consumes: Tasks 4, 5, 7.

- [ ] **Step 1: Implement** (chart per dataviz rules loaded in Task 7).

- [ ] **Step 2: Verify on fixtures**

Open d01 → 2 attempts newest-first; a1 cell 5 shows dead styling `exit 11`; judged cell 2 ringed; suggestion text renders in full; chart shows origin line `+1 → +2` and incumbent marks; d02 → single attempt, long suggestion wraps, directive: file rework with note → line in scratch `user-directives.jsonl`, pending chip renders, withdraw clears; Esc closes back to `#/a/alpha000` with focus on the design card; deep-link reload `#/a/alpha000/d/d01` opens directly. Console clean.

- [ ] **Step 3: Commit**

```bash
git add Assets/Blender/_tools/gallery/v4.html
git commit -m "suite: design dossier - attempt trail, verdicts with suggestions, ratchet chart, directives"
```

---

### Task 9: Live tab

**Files:**
- Modify: `Assets/Blender/_tools/gallery/v4.html` (LIVE css + `render-live`)

**Interfaces:**
- Produces: `renderLive()` under war-room tab bar (`role="tablist"`, Overview/Live/Compare, `aria-selected`, routes): sticky sub-bar (`total_runs`, `unclaimed_runs`, stamp, filter toggles `claimed only` / `failures only` persisted `gf-live-filter`), run sections newest-first capped at 20 + **Load more** (+30 each press), run header: `run-N`, claimed → `tag` + attribution chip `d02 · a1` from `byRun` join (unclaimed → dashed card, `.untag` "unclaimed" + header explainer line kept from old page), seed, shot count, `rendering…` when `done===false`, `data-ts` started; shot strips lazy-imaged, click → viewer with that run's shots. Live poll only while mounted (Task 3 cadence hook).
- Consumes: Tasks 3–5, `byRun`.

- [ ] **Step 1: Implement.**

- [ ] **Step 2: Verify**

Fixtures: 3 runs; run-3 shows `d02 · a1` + `rendering…`; run-1 dashed unclaimed; claimed-only filter hides it; failures-only shows none (fixture exits are per-cell in attempts, not live) — confirm empty-filter state message; load-more hidden (< 20 runs). Kill tap analogue: delete `live.json` from mini → empty state shows exact `python Assets/Blender/_tools/tap.py alpha000` command (regenerate after). Console clean.

- [ ] **Step 3: Commit**

```bash
git add Assets/Blender/_tools/gallery/v4.html
git commit -m "suite: live tab - attribution, filters, load-more"
```

---

### Task 10: Compare tab

**Files:**
- Modify: `Assets/Blender/_tools/gallery/v4.html` (COMPARE css + `render-compare`)

**Interfaces:**
- Produces: `renderCompare()`: current `latest.json` → header (`run N`, started, `building…`/`done`, audit chip — FAIL substring → `.dead`, renderer fingerprint `.faint mono`), variant columns (n chip, label, diff-vars `<pre>`-ish block, renders → viewer, `exit≠0` → stderr tail block, seconds chip); history: previous ≤ 12 manifests as `<details>` (fetched once, memoized Map keyed `asset|run`, generation-guarded against asset switches — port `loadHistory` fix pattern from old index.html), run-number jump input → fetch that manifest into an opened details. Empty state: exact `python Assets/Blender/_tools/preview.py <asset> --variants <file>.json` command.
- Consumes: Tasks 3, 5.

- [ ] **Step 1: Implement.**

- [ ] **Step 2: Verify**

Fixtures `#/a/alpha000/compare`: 2-variant columns, err variant shows `exit 1` + `boom`, renderer line renders; history lists run-002/001 collapsed, opening fetches once (network tab: no refetch on toggle); jump to `1` opens run-001. `#/a/loose000/compare` (not-in-fleet asset) works end-to-end. Console clean.

- [ ] **Step 3: Commit**

```bash
git add Assets/Blender/_tools/gallery/v4.html
git commit -m "suite: compare tab - variants, history, renderer fingerprint"
```

---

### Task 11: Redirect stubs

**Files:**
- Rewrite: `Assets/Blender/_tools/gallery/index.html`, `Assets/Blender/_tools/gallery/live.html`

**Interfaces:**
- Produces: both files ≤ 15 lines, no external requests. `index.html`:

```html
<!doctype html>
<meta charset="utf-8">
<title>Gloomfell → suite</title>
<script>
  var a = new URLSearchParams(location.search).get('asset');
  location.replace('/v4.html' + (a ? '#/a/' + encodeURIComponent(a) : ''));
</script>
<meta http-equiv="refresh" content="0;url=/v4.html">
<p>The gallery moved into <a href="/v4.html">the Gloomfell suite</a>.</p>
```

`live.html` identical except the replace target appends `'/live'` inside the hash (`'#/a/' + encodeURIComponent(a) + '/live'`) and, with no asset param, plain `/v4.html`.

- [ ] **Step 1: Write both stubs.**
- [ ] **Step 2: Verify** — on 8778: `/` → suite fleet; `/index.html?asset=alpha000` → `#/a/alpha000`; `/live.html?asset=alpha000` → `#/a/alpha000/live`.
- [ ] **Step 3: Commit**

```bash
git add Assets/Blender/_tools/gallery/index.html Assets/Blender/_tools/gallery/live.html
git commit -m "gallery: index and live become redirect stubs into the suite"
```

---

### Task 12: page.md behaviour section

**Files:**
- Modify: `.claude/skills/blender-model-modev4/references/page.md` (behaviour section + reads table only; **schemas untouched**)

- [ ] **Step 1: Rewrite "Page behaviour the tools rely on"**: routes table, tabs, slide-over, cadences incl. HEAD gate on `attempts.jsonl`, image-cache rule, verb-buttons-prefill rule, redirect stubs, `GLOOMFELL_PREVIEW_ROOT`, needs-you inbox sources, watermark, and the note that the page now *reads* `attempts.jsonl`/`control.json`/`latest.json`/manifests (readers only — the "Who writes which file" table gains no new writers; extend its Reader(s) column where accurate).
- [ ] **Step 2: Verify the verb line is byte-identical in its three homes:**

Run: `grep -F "makers <asset> N" .claude/skills/blender-model-modev4/references/page.md .claude/skills/blender-model-modev4/SKILL.md Assets/Blender/_tools/gallery/v4.html` → 3 hits, identical verb sequence by eye.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/blender-model-modev4/references/page.md
git commit -m "modev4: page contract - suite routes, cadences, prefill rule"
```

---

### Task 13: Full verification sweep + live cutover

- [ ] **Step 1: selftest** — `python Assets/Blender/_tools/selftest.py` → PASS.
- [ ] **Step 2: Empty-root pass (8778 → roots/empty)** — fleet empty state; `#/a/nothere000` → war room of empty states (each names its producer command); zero console errors.
- [ ] **Step 3: Live-data read-only pass (8778 → real `_previews~`, POST buttons untouched)** — screenshot + console check every route: `#/` (mage000 run + evilMage000 pause + knight000 in not-in-fleet row; inbox shows evilMage000 staged d02), `#/a/mage000` (dials show the brim note; designs d61/d62 with thumbs + ratchets; queue 5; events), `#/a/mage000/d/d61` (real verdicts + suggestions render), `#/a/mage000/live` (416 runs → 20 + load more, attribution chips, unclaimed dimmed), `#/a/knight000/compare` (real latest.json), evilMage000 war room (champion + staged card + lineage). Fix anything found; console must end clean on every route.
- [ ] **Step 4: Keyboard walk** — Tab from skip-link through strip → tabs → design card → dossier → viewer; Esc unwinds viewer → dossier → war room; `?` opens/closes shortcuts.
- [ ] **Step 5: Cutover** — stop the 8778 test server; restart the real one exactly per SKILL.md pre-flight §3 (kill listener on 8777, `Start-Process` with redirected stdout/stderr, no env overrides); then `Invoke-WebRequest http://localhost:8777/v4.html` → 200, `/` and `/live.html` redirect, `#/a/mage000` shows the live fleet breathing (heartbeat < 90 s). Confirm `tap.py` and shepherd untouched (fresh `live.json` stamps continue).
- [ ] **Step 6: Final commit if the sweep produced fixes**

```bash
git add Assets/Blender/_tools/gallery/v4.html
git commit -m "suite: verification sweep fixes"
```

---

## Self-Review (done at write time)

1. **Spec coverage:** routes/chrome (T3, T6), fleet+inbox+not-in-fleet (T6), overview cards incl. ratchet + lineage + dials + watermark (T7), dossier incl. suggestions + directives + chart (T8), live attribution/filters/load-more (T9), compare incl. fingerprint + jump (T10), viewer incl. pin + diff (T5), serve env + banner (T1), stubs (T11), page.md + verb-line identity (T12), failure modes + cadences (T3/T4 + fixtures' damage cases), verification incl. live cutover (T13). No gaps found.
2. **Placeholder scan:** none — every step names files, code, or exact checks.
3. **Type consistency:** route object, `parseAttempts` shape, `rowKey` format, `thumbSrcs`/`imgFallback`, `prefillChat` used consistently across T4–T10.
