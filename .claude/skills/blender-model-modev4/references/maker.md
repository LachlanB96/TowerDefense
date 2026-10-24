# Maker discipline (modev4) — reference copy

Makers never read this file (or any skill file): the session inlines the template
below, filled, into each maker's dispatch. This is the annotated reference; the
operating copy lives in `SKILL.md` ("Dispatching a maker") and **the two must stay
identical** — when you change one, change the other in the same commit.

## Why rows, not edits

Design d26 bundled a narrower skirt with a forward lean in one edit; the panel
accepted it for one half and the user reverted it for the other, and nobody could say
which half failed. Rows make attribution structural: `axis.py` expands each clause
alone and combined, so a two-idea change is three comparable renders and zero merge
surface. The script is only ever edited at a bake — one serialized writer, no
worktree-per-design, no rebase archaeology.

## Why the bake is the maker's job

The maker owns the design's meaning: it knows which gene values were the clause and
which were scaffolding, and whether a `patch` builder replaces or augments. The
session verifies the bake mechanically (re-render + measure) precisely so the maker's
judgment here does not need to be trusted blindly.

## Why the wave is a detached warden job

Every Blender run on this PC queues with the Process Warden, and `preview.py` starts
its Blenders out of the hook's sight, so the maker submits the wave itself through
`warden-run`: `--cpus` is the cell count (one Blender per granted CPU), `--mem` 2 GB a
cell, at least 4, and `--gpu`. `--detach` makes the wave outlive the maker: a maker
that dies after rendering has still done the work, and the manifest's `tag` and
`design` attribute it. `warden-run wait` in the foreground keeps the maker's turn open
until the render is done, so it never ends a turn with a render still running in its
own shell; a wait that times out (exit 124) is a wave still queued or rendering, and
the maker waits again.

## Why makers start none

The cap gives the session 8 subagents and each of those 1 (Lachlan, 2026-10-21). A
maker needs no helper, and nothing below the session spawning keeps the count exact:
the session can only hold a ceiling it can see.

## Mechanical discoveries

Any rig fact a maker finds the hard way (a clamp that does not bound the specular, a
camera that cannot see a region, a mesh below a feature's sampling limit) returns in
its report; the session curates `asset-facts.md`. Facts pass the substitution test —
if a different camera, size or engine would change whether it is true, it is a
rendering preference, not a fact — and the file is capped and regenerated per session,
never grow-only.

## The template (verbatim from SKILL.md)

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
> EACH ATTEMPT (I give its number every time; this is attempt `<attempt>`):
> 1. Design a row: `{"label": "...", "clauses": [{"name": "...", "vars": {...}} or
>    {"name": "...", "patch": "<python source>"}]}` — at most 3 clauses, each clause a
>    separable idea (the expansion renders each alone and combined).
> 2. Check every gene FIRST: `python <TOOLS>/genes.py <SCRIPT> --check GENE_A,GENE_B`.
>    A refusal names the fix — use `patch` to recompute derived genes, NEVER to route
>    around a refusal.
> 3. `python <TOOLS>/axis.py <SCRIPT> row.json --seed <wave-seed> --dist <dist>
>    --aim-z <aimz> --out wave.json` — it prints how many cells it wrote: that is C.
> 4. Render through the Process Warden, detached, so the wave survives you:
>    `warden-run --name <asset>-<design-id>-a<attempt> --cpus C --mem M --gpu --max 30m
>    --detach -- python <TOOLS>/preview.py <SCRIPT> --variants wave.json --samples 0.3
>    --tag <maker-id> --design <design-id> --root <ROOT>`, where M is 2 × C, at least 4.
>    It prints the job id and its log. Then `warden-run wait <job id>`, with a 600000 ms
>    tool timeout: exit 124 means still queued or rendering (the PC renders one wave at
>    a time, and none while a game runs) — wait again; never start a second render
>    meanwhile. Exit 0 is done; anything else failed, and the log's tail says why. The
>    run number is in the log.
> 5. Nominate your best cell. Return, job id and run number first: the row spec, the
>    run number, the nominated cell, what you expect it shows, and any mechanical
>    discovery about this rig not already in ASSET FACTS.
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
> `--root <ROOT>`; run `preview.py`, `build_one.py` or Blender outside `warden-run`; or
> write a `patch` whose purpose is to bypass a genes.py refusal.
>
> Subagents: start none.
