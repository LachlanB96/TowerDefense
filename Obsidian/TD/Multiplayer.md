# Gloomfell — Multiplayer Design

*Status: design sketch (2026-04-20). Not yet implemented. Single-player must reach feature-complete before this work begins.*

## Pillars

- **Mode:** Competitive, separate maps (Bloons Battles DNA).
- **Pacing:** Synchronized escalating rounds. Both players face the same wave schedule starting round 1; waves scale infinitely.
- **Win condition:** 100 lives each. First to zero loses. No round cap — matches end when someone breaks.
- **Economy:** Classic triple-tension sends (see below).
- **Content access:** Pre-match loadout — 4 towers + 1 hero per player, hidden from opponent.

## Send economy (triple tension)

When you send an enemy to your opponent:

1. You **pay money** from your wallet — directly reducing what you can spend on your own defense this round.
2. You **gain eco** — your passive income per tick goes up permanently (or for the rest of the match).
3. Your opponent **keeps the kill bounty** if they successfully defend against it.

Every send is a three-way bet: short-term damage to them, short-term weakness for you, long-term income lead. This is the mechanic the whole competitive game orbits around. Balancing it is the hardest part.

## Pre-match loadout

Each player picks 4 towers + 1 hero before the match starts. Opponent's pick is hidden. This is where:

- Strategic depth lives (counter-picks, specialisation builds).
- New content scales in cleanly — adding a tower adds loadout combinations rather than adding to a fixed arsenal.
- Early-game balance is tuned — restricting loadout size is easier than balancing every possible tower being always-available.

Exact number (4) is tentative — could be 3 for tighter early game, 5 for more flex.

## Netcode model: deterministic lockstep

Synchronised rounds + identical wave schedule = both clients can run the same simulation from the same seed. Only **inputs** cross the wire — tower placements, upgrades, sends. Everything else (enemy positions, projectile physics, hit detection, kills) is simulated identically on both machines.

- **Bandwidth:** trivial (a few bytes per player action).
- **Main risk:** desyncs from non-deterministic code.
- **Alternative considered:** server-authoritative state replication (streaming every enemy's position every tick). Rejected — heavier bandwidth, and the current code isn't built for it.

## Required refactors before netcode can land

These are *preconditions*, not implementation tasks — the single-player game should work after each of these and still be shippable.

### 1. Fixed-tick simulation
`Movement.Update()` currently uses `Time.deltaTime` directly. That's per-machine non-deterministic. Sim logic needs to move to `FixedUpdate` or a custom tick driver with a fixed step (e.g. 30 Hz sim, 60+ Hz rendering). Visuals lag the sim by a frame or two; players won't notice.

### 2. Seeded RNG throughout sim
Any randomness inside the simulation (wave composition, crits, targeting tiebreaks) must go through a single shared `System.Random` instance seeded from the match seed. No calls to `UnityEngine.Random` from sim code.

### 3. Replace global singletons with match context
Today: `EconomyManager.Instance`, `Spawn.UnitsParent` — global state, one per scene. Multiplayer needs each player's state isolated. Introduce a `MatchState` object that holds both players' economy, unit lists, tower lists. Single-player becomes "match with one player."

### 4. Extract wave schedule
`RoundManager` has hard-coded round-to-wave mapping. Needs to become a pure function: `(round, seed) -> WaveSpec`. Both clients call it and get identical results.

### 5. Input intent layer
Mouse clicks currently mutate the scene directly (place tower, upgrade tower, sell). These need to become *intents* that get queued and applied at a tick boundary — so they can be broadcast to the other client and applied simultaneously on both sides.

## Scope estimate

**Minimum playable multiplayer prototype** — both players defend, synchronised waves work, sends work, no loadout UI, no heroes, no polish, no matchmaking: **2–4 weeks** of focused work, assuming single-player is otherwise feature-complete.

**Full feature set** — loadout screen, hero integration, matchmaking, spectator, replays: roughly double again.

## Open questions

- Loadout size: 3, 4, or 5? Needs prototyping.
- Hero bans — can you pick a hero your opponent also picked, or are heroes unique per match?
- Eco boost formula: flat increase per send? Diminishing returns? Per-enemy-type scaling?
- Is there a "ready" / countdown before round 1 starts, or does the clock just run?
- Surrender button / graceful loss flow.
- Spectator mode as stretch goal.

## When to start

After single-player has: all 3 paths specced and implemented for at least 2 towers, the Silent Knight hero functional in-scene, basic audio, and the economy loop feeling tight. That's the "ready to compete over" bar.
