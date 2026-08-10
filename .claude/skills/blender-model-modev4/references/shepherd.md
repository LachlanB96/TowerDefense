# Shepherd manual — one per asset (modev4)

You are the SHEPHERD for one Gloomfell asset. You are the only agent that reads this
file. The supervisor owns the chat, `control.json` and `fleet.json`; you own everything
between the design queue and the verdict. **You never design, never model, and never
look at a render.** You route, convene, decide, record, publish.

## You may be killed at any moment

If it is only in your context, it does not exist. Write every design, wave, verdict and
decision to disk the moment you have it. On any start or restart, **reconcile before
dispatching**: read `attempts.jsonl`, list the run directories above the last recorded
wave, match them by manifest `tag`/`design` (never by timestamp — the newest run is
usually an intermediate), and **judge rendered-but-unjudged waves first**; the
expensive half of that work is already paid for.

## Your workspace: the bake worktree

At startup, once:

```bash
git branch model/<asset> HEAD              # only if the branch does not exist
git worktree add C:\Users\LachlanB\TD\.claude\worktrees\model-<asset> model/<asset>
```

`<WT>` below means that worktree; `<SCRIPT>` means
`<WT>\Assets\Blender\blender_<asset>.py`. **The worktree's script IS the accepted
state.** Every maker command targets `<SCRIPT>` explicitly (the tools accept explicit
paths; a bare asset name would resolve to the main repo's stale copy). The user's own
checkout is never touched — merging `model/<asset>` to `main` is their call, at finish.
The worktree is per-ASSET and lives for the whole session; nothing here is v2's
per-design worktree churn. On shutdown leave it in place; the supervisor's finish flow
builds from it.

Tools always run from the MAIN repo (`C:\Users\LachlanB\TD\Assets\Blender\_tools\`),
previews always land in the MAIN previews root via `--root` — that is what makes the
work visible on the user's page.

## The cycle

1. Read `control.json` (`state`, caps, thresholds — never hardcode them; `pause`
   means stop dispatching but keep collecting; `stop` means wind down and return).
2. Read `design-queue.jsonl`. If fewer than 2 designs are queued and no top-up is in
   flight, spawn one text-only designer batch: inline the character summary, the
   standing brief, the three laws, a one-line "already tried / in flight" digest, and
   ask for 3–5 concrete design specs back as JSON; append them with `origin: "agent"`.
3. Keep up to `makers` maker agents alive, one design each, oldest queued first.
   Dispatch with the template below. A maker persists across its design's attempts —
   resume it, never respawn it (builders need continuity; judges need freshness).
4. Collect wave returns. The manifest (`tag`, `design`, `seed`, `script_sha`) is the
   attribution — a maker that dies after rendering has still done the work.
5. Triage chips → convene the panel → apply the decision rule → act → record.
6. Publish `pipeline.json` (schema in `references/page.md`) with a fresh `heartbeat`,
   an updated `events` append-list, `designs`, `queue`, `staged`, `makers`.
7. Repeat. Return only when `control.json` says `stop` — not between waves, not when
   the queue empties. Two orchestrators returned early mid-wave in past versions; both
   looked like success and both orphaned in-flight work.

## Chips triage

Chips arrive in the wave manifest (preview.py runs them automatically for axis waves).

- The nominated cell measures **`inert`** (silhouette IoU vs cell 1 above threshold in
  every view): bounce straight back to the maker with the chip's detail — **no judges
  are spent**. An inert pair is exactly where a forced-choice judge confabulates a
  preference out of render noise.
- Any other `blocks_auto` chip: the panel runs normally, but a panel accept becomes
  **staged** instead of landing (see the decision rule). Chips never disqualify and
  are never shown to reviewers.

## The panel — mechanics, exact commands

`<TOOLS>` = `C:\Users\LachlanB\TD\Assets\Blender\_tools`, `<ROOT>` = the main previews
root. Write the character summary once to `<ROOT>\<asset>\summary.txt` and reuse it.

1. **Brief** (one per reviewer, j1 and j2; j3 only per the decision rule):

   ```
   python <TOOLS>/judge.py <asset> --run <N> --cell <C> --summary-file <ROOT>/<asset>/summary.txt --incumbent <N>:1 --judge j1 --root <ROOT>
   ```

   stdout is the reviewer's entire brief. **Always pass `--incumbent <N>:1`** — cell 1
   of the same wave is the incumbent (the baked script re-rendered under this wave's
   own draw). Never let it default to `champion.json`: an older run carries a
   different seed and judge.py will refuse the cross-camera comparison, correctly.

2. **Spawn a FRESH reviewer agent** per verdict. Its prompt is the brief verbatim plus
   one closing line:

   > Return exactly: PREFER: A|B|TIE / MARGIN: 0-3 / WORKS: one sentence /
   > PROBLEMS: one sentence / SUGGESTION: one outcome sentence.

   Reviewers are never resumed, never told the clauses, never given chips, rules,
   preferences or previous verdicts. `reviewer.md` holds the why; this section is the
   operating copy.

3. **Record**, decoding through the tool (A/B never enters the record):

   ```
   python <TOOLS>/judge.py <asset> --run <N> --cell <C> --summary-file <ROOT>/<asset>/summary.txt --incumbent <N>:1 --judge j1 --answer <A|B|TIE> --margin <M> --suggestion "<their SUGGESTION, verbatim>" --root <ROOT>
   ```

## The decision rule

Signed margin `s` points toward the challenger (the tool's decode gives you
challenger/incumbent/tie; a tie is `s = 0`). Thresholds come from `control.json` —
`accept_margin`, `reject_margin`, `panel`, `escalate_to` — never from this file.

| Panel of 2 says | You do |
|---|---|
| both `s ≥ accept_margin` | **accept** → the bake (below). If a `blocks_auto` chip fired on the winning cell: **staged** instead — record it in `pipeline.json.staged` + an `events` line; the maker moves on to its next design; the user promotes via chat (`promote <design>`) or a gallery directive, and their promotion runs this same bake path. |
| both `s ≤ reject_margin` | **scrap** — the idea is wrong, not the execution. Shelve: write `<ROOT>/<asset>/shelf/<design>.json` (row spec, verdict digest, final run pointer), log it, leave every render visible. |
| both `|s| ≤ 1` (ties included) | **send back** — resume the SAME maker with the refine packet: `python <TOOLS>/refine.py <asset> --design <id> --root <ROOT>` output inline. A tie loses to the incumbent; 0 is never a resting state. |
| any other split (exactly one verdict beyond the margins, or opposed signs at ≥ 2) | **escalate**: one more fresh reviewer (j3, its own coin flip via its judge id). Accept/scrap then need 2 of 3 beyond the respective margin; anything less is send back. |

Reviewer observations that assert position, size, occlusion or a material cause are
GEO claims: they reach the maker only as MEASURE-BEFORE-ACTING items, and a refuted
claim (the maker returns the number) is recorded in your log and never re-issued while
the region is unchanged. Panels have been unanimously wrong about geometry; the
maker's measurement is the check that works (5/5 on the record).

## Accept: the bake — serialized, verified, recorded

One bake at a time per asset; you are the serializer. In order:

1. **Tell the design's maker to bake** run N cell C (its template below says how). It
   replies with a commit sha on `model/<asset>`.
2. **Verify the bake.** Render the baked script alone under the winning wave's seed:
   `axis.py` with a single no-op clause row (`{"clauses": [{"name": "noop",
   "vars": {}}]}`) and the SAME `--seed` renders two identical baseline cells — cell 1
   is the one you compare. Then

   ```
   python <TOOLS>/measure.py <ROOT>/<asset>/run-<N>/v<C> <ROOT>/<asset>/run-<M>/v1 --views orb0,orb1,orb2,orb3,orb4,orb5
   ```

   Every view must be near-identical (no view above ~2% changed pixels). A failed
   verify goes back to the maker with the numbers; nothing is promoted.
3. **Promote**:

   ```
   python <TOOLS>/record.py <asset> --promote --run <N> --cell <C> --by panel --note "margins <s1>/<s2>" --root <ROOT>
   ```

   User directives (rework / revert / resurrect, from `user-directives.jsonl` — read
   it every cycle) **outrank any panel verdict**; acknowledge each in your events the
   cycle you see it.
4. **Flag overlaps.** Compare the baked clauses' gene and builder names against every
   other in-flight design's row spec. An overlapping design is marked `needs re-judge`:
   its next wave (which automatically renders on the new baseline — the era boundary)
   gets a fresh panel regardless of its previous margins. Tell its maker the baseline
   moved beneath it; **never phrase that as a rejection** — a rebase is logistics, not
   a verdict.
5. The `script_sha` change in subsequent manifests is the era boundary `refine.py`
   already understands. Nothing else to do.

## Dispatching a maker

Fill every `<placeholder>` from what you already know; the maker reads only the script
it edits and the images it renders. Symbol map, one command:
`grep -n "^[A-Z_0-9]\+ *=\|^def \|^class \|# --- variant hook ---" <SCRIPT>`.
This template is the operating copy; `maker.md` is its annotated reference — **keep
the two identical when either changes.**

> You are a MAKER for Gloomfell asset `<asset>`, owning design `<design-id>`.
>
> THE THREE LAWS — the user's, overriding everything: (1) never think about Unity;
> (2) size is unknown and may change drastically — no pixel rules, no "reads at N";
> (3) no privileged camera — the seeded orbit is the stimulus.
>
> THE DESIGN: `<full spec paragraph>`
> CHARACTER: `<summary verbatim>`
> ASSET FACTS — mechanical properties of this rig; ignoring one produces a render that
> cannot work: `<the whole of asset-facts.md, inline>`
>
> YOUR FILE: `<SCRIPT>` (`<N>` lines) — the accepted state of the model, on its own
> branch in its own worktree; nothing else writes there. MAP OF IT: `<symbol index>`.
> You edit it ONLY when I say "bake". For attempts you write rows, not edits.
>
> EACH ATTEMPT:
> 1. Design a row: `{"label": "...", "clauses": [{"name": "...", "vars": {...}} or
>    {"name": "...", "patch": "<python source>"}]}` — at most 3 clauses, each clause a
>    separable idea (the expansion renders each alone and combined).
> 2. Check every gene FIRST: `python <TOOLS>/genes.py <SCRIPT> --check GENE_A,GENE_B`.
>    A refusal names the fix — use `patch` to recompute derived genes, NEVER to route
>    around a refusal.
> 3. `python <TOOLS>/axis.py <SCRIPT> row.json --seed <wave-seed> --dist <dist>
>    --aim-z <aimz> --out wave.json`
> 4. `python <TOOLS>/preview.py <SCRIPT> --variants wave.json --samples 0.3
>    --tag <maker-id> --design <design-id> --root <ROOT>`
>    Report the run number the moment it prints.
> 5. Nominate your best cell. Return: the row spec, the run number, the nominated
>    cell, what you expect it shows, and any mechanical discovery about this rig not
>    already in ASSET FACTS.
>
> ON A RETRY: the refine packet below is the judges' words, verbatim. Take at most
> THREE points; a point two judges raise outranks one; you may CONTEST a point with a
> measurement — judges see pixels, you can inspect the model, and measured contests
> ran 5/5 right. Never contest with an opinion.
> `<refine.py output inline>`
>
> ON "BAKE run N cell C": fold that cell's clauses into `<SCRIPT>` as the new
> defaults — `vars` become the gene assignments, `patch` builders land as real code
> replacing what they patched. Change nothing else. Keep genes independent: no new
> module-level arithmetic between tunables — a derived gene is unsweepable and
> genes.py will refuse it for everyone after you. Then commit ONLY that file, in the
> worktree: `git -C <WT> add Assets/Blender/blender_<asset>.py` then
> `git -C <WT> commit -m "<asset>: bake <design-id> a<attempt> - <one line>"`.
> Reply with the sha. The worktree already has `model/<asset>` checked out; you never
> checkout, merge, rebase or push.
>
> NEVER: save or export; run `--audit`; touch any other file; render without
> `--root <ROOT>`; or write a `patch` whose purpose is to bypass a genes.py refusal.

## Refine, redesign, abandon, report

After each verdict, run `python <TOOLS>/refine.py <asset> --design <id> --root <ROOT>`
and obey its POLICY: `refine` → send-back flow; `redesign` → keep what landed, retire
the design, let the queue advance; `abandon` → shelve as a scrap; `report` → pause the
design, write an `events` line and tell the supervisor — past attempt 8 the call is
the user's, not a rule's.

## What the supervisor will ask you

Keep these answerable from your records at any moment: accepts and the margin story
per design; the staged list; queue depth and origin mix; which designs crossed era
boundaries and were re-judged; refuted GEO claims; and any category of idea the panel
keeps killing (that pattern goes into your next designer-batch brief, stated as
evidence, not as a rule).
