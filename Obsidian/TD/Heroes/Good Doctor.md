He arrived the week after the sickness did, and nobody has ever established which
order those two events belong in. He is shorter than either of the others and half
again as wide, and most of that width is not him: strapped to his back is a copper
still — a bulbous boiler, a firebox glowing bilious green through its grate, a
swan-neck condenser arcing over one shoulder and a stub chimney venting sweet
vapour over the other. He walks bent forward under it. Where his face should be
there is a long down-curved beak of waxed black leather, ringed in brass, and two
flat glass lenses that show you nothing but a small green fog moving behind them.
In one hand he carries a censer on a chain, swinging low, and it is never quite
still even when he is. In the other, a flask.

He calls everyone *patient*. He has never once been seen to cure anything.

*Working name. `plague000` is the code name; a player-facing name in the
[[Silent Knight]]'s register is still to be picked — see Naming.*

---

## Brief — 2026-08-03 (first pass)

*The user's words, verbatim.*

> Lets work on a new model. I am going to give you absolute control for the design
> of this model. It should be a concept similiar to the mage and knight, having its
> own unique style. You have full control to make it whatever you want

Design authority for this pass was delegated in full. What follows is the brief
written against that delegation, and it is the aim for the current round of work.

### The gap this hero is designed to fill

The two existing heroes converge more than they look like they do. Both are
**tall, upright, symmetric and vertically planted** — one around a sword, one
around a staff. Both hide the face. Both hang their whole colour identity on a
single saturated accent (red / violet) against a cold dark ground. A third hero
built the same way would be a third silhouette of the same shape.

So the design constraint driving every decision below: **be different in mass and
in material, not merely in costume.**

| | Silent Knight | Mage | Good Doctor |
|---|---|---|---|
| Material language | Steel + gold | Silk + silver | **Copper, brass, glass, tarred leather** |
| Mass | Upright, broad-shouldered | Upright, tall, narrow | **Squat, hunched, back-heavy, leaning** |
| Signature object | Sword, planted | Staff, planted | **Censer, swinging — the first that is not planted** |
| Reads above the head | Crest, swept back | Brim, spread wide | **Chimney, rising behind one shoulder** |
| Reads in front | — | — | **A 30 cm beak, jutting forward** |
| Accent | Red | Violet | **Bilious green** |
| Hidden face, solved by | Void + red eye-slits | Void under a brim | **Blank reflective glass** |

The three heroes then answer the same question — *hide the face* — three different
ways, which is a family resemblance rather than a repetition.

### The three features that must name him at 184×184

In priority order. Everything else yields to these.

1. **The beak.** Long, down-curved, brass-ringed, and pointing **forward** — into
   the axis neither other hero uses. It is the single feature that names the
   character with all interior detail gone.
2. **The still on his back.** The boiler, the chimney over the left shoulder and
   the swan-neck condenser over the right are what make the silhouette wide,
   asymmetric and back-heavy. He leans forward against its weight; that lean is
   part of the silhouette, not a pose note.
3. **The censer, swinging.** Hung on a chain, low, out from the body and off the
   vertical. Every other hero's signature object is a vertical line planted in the
   ground. This one is a pendulum caught mid-arc, and it is what puts an
   asymmetric mass down near the feet where both other heroes are empty.

### Standing decisions

| Decision | Value | Why |
|---|---|---|
| Face | Hidden behind two flat glass lenses, faint green fog behind them | The third answer to the family's hidden-face question. Reflective, not void — the knight took the glow, the mage took the darkness |
| Hood, **not a brim** | Waxed canvas cowl, open at the front, no brim at all | The broad brim is the mage's silhouette. Taking it here would collapse the two |
| Accent colour | **Bilious green**, emitted from the firebox grate, the censer seams and the flask | Must never be confused with the knight's red or the mage's violet at a glance in a busy fight. Every VFX this hero gets inherits this green |
| Copper, not gold | Hammered, patinated, warm-but-dirty | Gold is the knight's. Copper is the same warm family read as *equipment* rather than as *wealth* |
| Recesses | Near-black: hood interior, coat lining, beak underside, firebox surround | The green needs something to glow against. Same rule as the other two |
| Build / stance | Short, wide, hunched, braced — head roughly 1.64, chimney to ~2.04 | He is a static hero; this is the pose players stare at all match. Deliberately the shortest and widest of the three |
| Symmetry | Broken on purpose — chimney left, condenser right, censer hand low, flask hand up | The other two are near-symmetric. Asymmetry is this hero's character note the way "nothing is ever straightened" is the mage's |

### The tone clash, stated explicitly

Project tone is a grim/silly collision. This character is the collision inside one
figure: the grim half is plague, a beak and a censer swung over the dead; the silly
half is that he is **40% laboratory** — comically over-equipped, clinking, venting,
bent double under a chemistry set he clearly built himself. He is sincerely trying
to help. It has never worked.

Designers should feel free to invent backstory that cashes this in. What the still
is actually distilling, what is in the flask, and why the censer never stops moving
are all open and all fair game.

### Where NOT to spend effort

Learned from the mage's five passes, recorded here so it is not re-learned:

- **Do not decorate the coat.** Almost every mage design decorated the robe, and
  silhouette changes were what survived the icon test. Here the silhouette lives in
  the beak, the pack and the censer — reach for those first.
- **Emission is not brightness.** Above ~0.5 strength AgX desaturates emitters
  toward white, so cranking the green makes it *paler*, not sicker. Saturated
  colour against a near-black recess does the work.
- **The green must not out-compete itself.** The firebox is the brightest green;
  the censer seams and the flask are quieter. Three equally bright greens and the
  eye has nowhere to land.

## Identity

| Field | Value |
|-------|-------|
| Type code | `plague000` |
| Display name | **TBD** — see Naming |
| Cost | TBD |
| Sell value | 50% (framework default) |
| Range | TBD |
| Footprint | 1.4 unit placement radius (same as towers) |
| Target priority | TBD |

Plugs into [[Framework]] like every other hero: static, invincible, one per match,
ten levels, four slots (auto-attack + passive at L1, active at L5, ultimate at L10).

## Mechanics

*Not designed. Nothing below is decided.*

| Slot | Unlock | Status |
|---|---|---|
| Auto-attack | L1 | TBD |
| Passive | L1 | TBD |
| Active 1 | L5 | TBD |
| Active 2 (ultimate) | L10 | TBD |

When these are designed, follow the [[Silent Knight]]'s lore → mechanics mapping
discipline: every ability should cash in a line from the paragraph at the top of
this file rather than being bolted on. The obvious hooks waiting to be used are the
**censer** (a persistent ground-area effect that lingers where it has swung), the
**still** (something that converts one resource into another over time — the only
hero with a *process* rather than a strike), and **"he has never once been seen to
cure anything"** (an effect that is unambiguously a debuff while being described in
the language of medicine).

## Naming

Needs a proper name in the [[Silent Knight]]'s register — two words, evocative,
and ideally carrying the same wink that "Silent Knight" does. `plague000` stays as
the type code regardless. Candidates to be proposed and picked before anything
player-facing ships.

## Model

| | |
|---|---|
| Build script | `Assets/Blender/blender_plague000.py` (procedural, reproducible, harness-conforming from the first commit) |
| Authoring file | `Assets/Blender/plague000.blend` |
| Game asset | `Assets/Models/plague000.fbx` |
| Renders | `Assets/Blender/_plague000/` |
| Health check | **None yet** — see below |

Rebuild with `blender -b -P Assets/Blender/blender_plague000.py -- save render export`.

Preview variants without touching the `.blend` or the FBX:
`python Assets/Blender/_tools/preview.py plague000 --variants v.json`.

*Status: **blockout**. Built 2026-08-03 as a starting point for the modelling
pipeline, not as a finished asset. Proportions, silhouette, palette and camera set
are in place; surface detail is deliberately absent — that is the pipeline's job.*

### Known gaps at blockout

Recorded so they are not mistaken for oversights:

- **No audit script.** The knight and mage both have one
  (`_<asset>/audit_<asset>.py`) checking non-manifold geometry, levitation and
  below-floor verts. This asset has none yet. Until it exists, levitation and
  manifoldness are unverified and any claim that geometry "touches" is by
  construction, not by measurement.
- **Not rigged.** No armature, no clips, no Unity prefab.
- **Hands are mitts.** Rounded blockout masses, no digits.
- **No smoke or vapour.** The chimney vents nothing yet. Whether that is geometry
  or a Unity-side VFX is an open design question.
