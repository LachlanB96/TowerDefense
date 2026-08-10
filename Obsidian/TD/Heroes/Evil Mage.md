*Agent-authored concept, 2026-08-10. The user's brief is quoted below verbatim;
everything else is invention and is theirs to redirect.*

Whatever went into the Weeping Gate a thousand years ago, this is what came back
out of it the second time. He is the same man — the same slouched broad brim, the
same midnight silk, the same five forked locks of beard, the same silver hand the
Grey Lanterns wrought and closed around the Staff — and none of that has been
taken from him, which is the part the camp finds hardest to sit with. Nothing was
taken. Something was *added*. He hangs clear of the ground and the hem of the robe
hangs below him without ever finding it, and the dark he used to merely carry now
comes off him: a slow soundless weather that fills a tent and puts out the lamps
at the far wall. The violet gem at the head of the Staff is dead — cracked open,
cold, an empty socket where the most complexly beautiful object in all the realms
used to sit — and anyone who looks at him understands at once where its light
went, because it is coming out of *him* now, out of the throat of the robe and
from under the brim and off the ends of the beard, in the colour that used to show
only at the very edge of the silk when he turned. He has not spoken. The hand
never opened. That is the only reason anybody is certain he is still the Mage:
whatever he is now, he could not put the Staff down if he wanted to.

---

## Brief — 2026-08-10 (first pass)

*The user's words, verbatim. This is the whole aim; everything else in this
document is an agent's reading of it and is theirs to overrule.*

> Lets create an alternate version of the mage called evilMage000. The evil mage
> will look like an undead version of the original mage, and have lots of
> supernatural aura.

Three things to aim at, drawn from that:

1. **He is the same model, corrupted — not a new character.** The build script
   begins as a byte-identical copy of the accepted `blender_mage000.py`. Every
   change is a transformation of something that is already there. A maker who
   finds themselves authoring a new part from nothing has probably wandered off
   the brief; the interesting work is in what death did to the parts that exist.
2. **Undead means *preserved*, not decomposed.** He is not a zombie and not a
   green-fire lich. The man is gone but nothing about him has been allowed to
   fall apart, because whatever is holding him up is also holding his clothes on.
   See **The rot has a rule** below — this is what stops the design becoming a
   wash of generic decay.
3. **The aura is the headline, and the parent's history says it is the hard
   part.** [[Mage]]'s aura was measured `absent, not weak` after five passes of
   trying. Everything that failed there failed the same way: it was shader-side,
   symmetric, or bounded. This character is the licence to overspend on it.

## Appearance

### The rot has a rule

"Everything is rotted" is not a design, it is a wash — a uniformly ruined figure
reads as noise and loses the parent's identity at exactly the detail level where
it most needs to survive. So decay on this model is **directional and bounded**:

> Decay proceeds **from the outside in and the bottom up** — from every point
> where the figure met the world: the hem that dragged on the ground, the cuffs
> that rubbed the wrists, the outer edge of the brim, the back of the sash he
> leaned on. It **stops** where the aura is strongest — the torso, the throat,
> the silver arm — and what it stops at is not merely undamaged but *uncannily*
> intact.

The read that produces is: **ruined at its boundary, impossibly whole at its
heart.** That is worth more than rot everywhere, because it makes the aura's
source legible in a completely still frame with no motion and no glow — the
preservation itself points at where the thing lives.

The corollary is a licence: any part in the protected core may be left exactly as
the parent built it, and that is a decision rather than an omission.

### Part by part

The heart of this document. Left column is a feature of the accepted `mage000`;
right column is the transformation. Anything not in this table is unchanged.

| Parent feature | What death did to it |
|---|---|
| **Hat crown & curled point** | Preserved in silhouette — it is the first thing read and it is what proves the derivation. But the crown has **slumped**, no longer held out from inside by a head that is full: the crease deepens into a real fold, and the backward curl of the point goes further, drooping past its own brim line so the tip hangs down beside the head rather than arcing behind it. The parent's 7.5° cock becomes a larger, uglier angle. |
| **Hat brim** | The edge is **broken**, eaten back in a few large bites rather than scalloped all round. Few and large is load-bearing: a uniformly ragged edge averages straight back into a smooth edge the moment detail drops, which is the same failure the parent recorded for hairline silver. |
| **Head height (the 93 mm lift)** | **Unchanged, and now a feature.** It exists because a brim near the shoulder reads as a table resting on him. On this character the strip of visible neck it buys is the only place the body is exposed at all, and therefore the best real estate on the model — vertebrae, a collar of bare bone, or the point where the light gets out. |
| **The void under the brim** | Stops being empty and becomes **the source**. See below — this is the largest single opportunity and it has a trap in it. |
| **Beard — five forked locks** | The count, the forking and the build are preserved: this is the wizard read and it is what makes him recognisably the same man. What changes is that the locks **no longer hang** — they lift and splay outward at the tips as if in a rising draft or underwater. One lock is gone below the jaw, ending in a blunt break, so the matched five is broken. Material: the silk sheen comes off it, so it reads as dry fibre rather than hair. **Do not brighten it** — see the value budget below. |
| **Robe — the silk shell** | The robe **no longer touches him.** With the body hollow it hangs off nothing between shoulder and hip, so the shell stands away from the figure and its vertical axis is no longer the figure's vertical axis: the garment leans one way while the head and staff go another. |
| **Robe folds (7 lobes + 13 fine)** | Fold count preserved — the fine cusped silk is the parent's fingerprint. Added: **horizontal gathering** the parent does not have, where the cloth has slumped against itself for a thousand years. Tears go **along the fold valleys, never across the ridges** — cloth fails in the cusps — and they are few and large for the same reason the brim's bites are. |
| **Hem pooling on the ground** | **Gone, because he is off the ground.** The hem stops reaching, hangs free, and its lowest points trail off into vapour instead of resting. The ground contact is not deleted, it is *detached*: a separate pool of dark on the floor beneath him that he is not touching. |
| **Body cross-section (`BODY_DEPTH`)** | The ellipse **stays at the shoulder** — a circular section is a cone with no shoulder, and that lesson still binds. What changes is the waist, pulled in hard, so the torso narrows to almost nothing between ribs and hips and the robe has nothing left to hang on. |
| **Open left hand (skin, knuckled digits)** | Goes to **bone**. It is the only skin on the model, so it is the single strongest statement available that the man died. Keep the pose and the knuckled build; thin the digits and deepen the gaps so it reads as a claw in outline. Bone reads as *shape*, not as value — do not let it go bright. |
| **Wrought-silver prosthetic forearm** | **Untouched. Do not corrode it.** The Grey Lanterns' work outlives the man wearing it. A mirror-clean, unbothered silver arm on a corpse is far more unsettling than a pitted one, and it is the anchor that proves the two characters are the same person. Its consequence also survives: the hand never opened, which is why he is still holding the Staff and still standing. |
| **Staff shaft — blackwood, ridges, gnarl** | The wood **died with him, from the bottom up.** The violet grain veins go out along the shaft as a gradient, dead-dry at the ground with only the top third still holding a trace. A directional fade reads as a process; a uniform dimming reads as a settings change. |
| **Wound leather grip cord** | Rotted and **partly unwound** — a few turns hanging loose off the shaft. The turns *under the silver hand* survive intact, because the hand has been clamped over them the whole time. |
| **Five tendrils cradling the stone** | The cradle has **failed on one side**: one or two tendrils snapped, so the stone sits crooked in a broken silver seat. Asymmetry, silhouette, and a story, for very little geometry. |
| **The violet gem** | **Dead.** Cracked through with a wedge missing, hollow, near-black inside. Geometrically preserved — it must still clear the hat and hold the top of the silhouette — but it is now the *darkest recess on the model* rather than its brightest point. See the rule-break below. |
| **Silver trim (hem, cuffs, front opening, yoke, studs)** | **Tarnishes, with a boundary.** A dull film creeping upward from every edge that met the world, densest at the hem band and cuff rings, thinning as it climbs. The hat band stays bright — it is furthest from everything. Material warning inherited from the parent's prosthetic: do **not** express this as a dark metal. A metallic surface has no diffuse term and only shows where a highlight lands, which is exactly how the first prosthetic pass came out as a grubby ribbed hose. Tarnish is a dielectric dull film: metallic down, roughness far up. |
| **Slung sash + rear strap** | The sash still hangs, but has **rotted through at the back** so the rear strap is broken and both ends hang free. This is a gift from the parent: five passes of judging failed to notice that the rear strap did as much tailored-greatcoat work as the front belt. A severed one is the strongest possible version of "loosened, kit kept," and this character gets it for free. |
| **Belt kit — pouch and scroll case** | **Kept and emptied.** The pouch hangs slack and flat with nothing in it; the scroll case is open at one end and the scroll is gone. They still carry the epic-past brief; now they also say that the past is over. |
| **Collar askew, asymmetric lapels, one-sided studs** | **Unchanged.** These carry "nothing about him is ever straightened," which death does not alter, and they are the fingerprint that identifies him. Spending effort here buys nothing. |
| **Asymmetric sleeves (bell left, short right)** | **Unchanged.** They are what gives the staff arm its clearance, and undoing that brings back a defect that took a close-up to find. |

### The void under the brim, and the trap in it

This is the most tempting change on the model and the parent already paid for the
lesson: **there is no visible face from any angle.** The brim's outer edge droops
below the top of the beard, so between them they occlude the entire front of the
head across every heading and every downward tilt. The parent built eye glints,
rendered them on and off, and the images were indistinguishable everywhere.

So:

- **Do not add a skull, eyes, or a glowing socket under the brim and expect it to
  show.** It will not. The fix is upstream — lift the brim's underside, or start
  the beard lower — and that is a legitimate design in its own right, but it is
  *the* change, not a free precondition of some other change.
- **The version that works without touching the brim is a vent.** Light does not
  need line of sight to its source if what escapes is geometry. Emitted matter
  spilling out from under the brim, over the top of the beard and down the chest
  reads from every heading in the orbit, because it lives *outside* the occluder.

### The aura: what it is made of

The parent's target statement is the clearest thing anyone has written about this
and it carries over unchanged, because it is already scale-free:

> A render in which you could cover the figure entirely with your thumb and still
> see where he had been — a stain of dark left in the frame around the thumb's
> edge. Right now the backdrop touching his shoulders is exactly the backdrop at
> the far edge of the image; the figure takes no territory.

Four constraints on how it gets built, every one of them paid for already:

1. **Geometry, not shader.** The standing evidence is that silhouette changes
   survive and pure shader tricks do not. A glow that is only a material is the
   failure mode, not the design.
2. **Asymmetric.** A symmetric halo reads as a lighting artifact rather than as
   something the figure is doing. Whatever the aura is made of, it should be
   denser on one side, higher on one shoulder, and heavier where it comes out.
3. **Nothing flat.** The judged stimulus is a fresh 360° orbit, so any card,
   billboard or plane that vanishes edge-on has failed at a quarter of the
   headings. Everything in the aura must have thickness from every direction.
4. **Few and large, not many and small.** Fine particulate averages into a
   uniform fog the instant detail drops, which puts it back to being a shader
   effect. Bodies big enough to individually survive are the ones that read.

Buildable materials for it, in rough order of how much frame territory they win:

- **A pool on the floor** beneath a figure that is no longer touching it. This is
  the one that most directly wins the thumb test, because it takes area the
  figure's own outline never occupies from any heading.
- **Tatters**, continuing the robe's own fold system as detached rising sheets
  off the hem and the yoke seam — so the aura is visibly made *of him* rather
  than added on top of him.
- **The vent** from under the brim, over the beard, down the chest.
- **Motes or shards** rising in a column, densest at the torso, thinning at the
  extremes. This is where "from his soul" locates the source.

### The one rule this character breaks

The parent's standing rule: *the gem is the only bright thing, the aura is dark
emission, and they occupy opposite ends.* **This character inverts it, and the
inversion is deliberate.**

The gem goes out. The body lights up. What was the brightest point on the model
becomes the darkest recess on it, and the light that used to live in the stone is
now what the figure emits.

Why this is a break worth making, and not just vandalism of a settled decision:

- **The discipline survives; only the location moves.** There is still exactly
  **one** luminant on the model, and everything else still yields contrast to it.
  That was always the real rule. The gem was the instance, not the principle.
- **Rule 4 survives inverted.** The parent needed near-black recesses for the gem
  to glow against. Here the dead gem's hollow socket is the near-black, and the
  luminous body is what it reads against. The pairing is intact, swapped.
- **It separates the two characters at the level of value distribution**, not
  just decoration. Parent: dark figure, bright point above the hat. This one:
  luminous figure, dark hole above the hat. That difference survives any amount
  of lost detail, and no amount of added ornament would have done the same job.
- **It answers "lots of aura" structurally** rather than by piling more on. The
  parent's aura kept failing partly because it had to stay quieter than the gem.
  Take the gem out and that ceiling is gone.

**Hue.** The parent's robe ramps to a cyan-teal at grazing angles — the colour
that only ever shows at the silk's outermost edge when he turns. That is the
colour this character emits, brought inward and pushed to a witchfire pale. It is
a derivation rather than an invention, it keeps a family resemblance to `mage000`,
and it stays clear of the [[Silent Knight]]'s red at a glance in a busy fight.

**Value budget.** Exactly one thing is allowed to be bright, and it is the emitted
light. The bone hand, the beard and the tarnished trim all stay **down** — the
parent's notes on `C_HAIR` and `C_SKIN` record what happens when a second pale
thing appears on the model, and the bright-thing slot is already spent. The one
exception is the silver forearm, which keeps its parent value on purpose: it was
already second only to the gem, and with the gem gone it becomes the highlight the
new light plays against.

### Silhouette test (scale-free)

With every interior detail lost, the outline must read as **pointed hat + a robe
that does not reach the ground + a tall staff with a dark socket on top**, and the
frame must still be stained where he is.

Two notes on how this differs from the parent's:

- **No size is named, deliberately.** The parent's test was pinned to a fixed icon
  size; this one is not, because the model's final size is unknown and may change
  drastically. The test is "at whatever detail survives," not "at N across."
- **No heading is privileged.** He is judged on a seeded 360° orbit drawn fresh
  each time, so nothing may be tuned to one camera. Every asymmetry — the drooped
  hat point, the broken cradle, the leaning robe, the failed sash, the heavy side
  of the aura — should be distributed around him so that **any** heading shows at
  least one of them. "It reads from the front" is not a passing result.

## Identity

| Field | Value |
|-------|-------|
| Type code | `evilMage000` |
| Display name | TBD |
| Derived from | [[Mage]] (`mage000`) — same man, second return |
| Cost | TBD |
| Sell value | TBD |
| Range | TBD |
| Footprint | TBD |
| Target priority | TBD |

## Deliberately preserved

Named explicitly so that leaving them alone reads as a decision rather than as
unfinished work. Each one is protected by **The rot has a rule** above — they sit
in the aura's core, where decay stops.

| Preserved | Why |
|---|---|
| **The wrought-silver forearm**, at full polish | The Grey Lanterns' work outlives its wearer. Clean silver on a corpse is more unsettling than pitted silver, and it is the strongest single piece of evidence that this is the same man. It also inherits the parent's best material lesson intact — a dielectric-leaning bright metal, not a dark mirror. |
| **The five forked locks** of the beard, in count and construction | They carry the wizard read that a shadowed void alone cannot. Re-aim them; do not rebuild them. The parent already proved that a single lofted mass reads as a bib and that carving ridges into one surface does not survive the subsurf. |
| **The hat's overall silhouette** | It is the first thing read and it is the derivation. Slump it and droop its point; do not reshape or shrink it. |
| **The asymmetric sleeves** and the staff standing out from the body | Structural, not stylistic — the hand is *on* the staff and a wide bell always swallows the shaft. Undoing either brings back a defect that took a close-up render to find. |
| **The elliptical body section at the shoulder** | A torso as deep as it is wide is a cone with no shoulder, and the arms read as tubes rammed into its side. Narrow the waist; leave the ellipse. |
| **Collar askew, asymmetric lapels, one-sided fastenings** | "Nothing about him is ever straightened" is unaffected by dying, and these are his fingerprint. |
| **The belt kit's objects** — pouch, scroll case, buckle | They carry the epic-past brief. Empty them; do not delete them. The parent lost five passes to a tailoring problem and the answer was never subtraction. |
| **The head's 93 mm lift** | Load-bearing. Without it the brim drops toward the shoulder and the hat reads as a table. Here it also buys the only exposed body on the model. |
| **The crown-heavy gem cut** | A correct jeweller's brilliant is mostly pavilion and renders from the side as a small cap on a lot of silver. Keep the cut; hollow and crack what is inside it. |

## Mechanics

*Not designed. Nothing here is decided.*

| Slot | Status |
|---|---|
| Auto-attack | TBD |
| Passive | TBD |
| Active 1 | TBD |
| Active 2 (ultimate) | TBD |

When these are eventually designed, follow the [[Silent Knight]]'s lore →
mechanics discipline and cash in lines from the paragraph at the top of this file
rather than bolting abilities on. The hooks sitting unused are the **dead gem**,
the **hand that never opened**, and the **lamps going out at the far wall**.

## Opening design directions

The initial design queue. Each is independently buildable, names the part of the
existing model it changes, and can be started immediately without waiting on any
of the others.

1. **The dead gem** — hollow and crack the crown-heavy stone at the staff head
   into a near-black socket and move the emission budget off it onto the torso,
   so the top of the silhouette becomes the darkest recess on the model.
2. **He is off the ground** — lift the whole figure clear of the floor, stop the
   robe hem from pooling so its lowest points hang free and trail, and replace
   the lost ground contact with a separate flat pool of dark on the floor beneath
   him.
3. **The beard drifts** — re-aim the five forked locks from hanging to rising,
   splaying their tips outward and up, and break one lock short below the jaw so
   the matched set is gone.
4. **The robe hangs off nothing** — pull the body's waist radius in hard while
   keeping the shoulder ellipse, and push the robe shell off the body between
   shoulder and hip so the garment stands away and leans on a different axis to
   the head and staff.
5. **The vent under the brim** — build the face void as a source and let what it
   emits escape as geometry past the brim's edge and over the top of the beard,
   since the head itself is occluded from every heading in the orbit.
6. **Tatters off the hem and yoke** — continue the robe's own fold system upward
   as detached rising sheets, so the aura is made of him rather than added to him.
7. **Tarnish with a boundary** — replace the flat cold-mirror silver on the hem
   band, cuff rings and lapel studs with a dull dielectric film creeping upward
   from every edge that met the world, leaving the hat band and the wrought silver
   forearm at full polish.
8. **The cradle has failed** — snap one or two of the five tendrils so the dead
   stone sits crooked in its broken silver seat, and run the staff's violet grain
   veins out from the bottom up so only the top of the shaft still holds a trace.

## Model

| | |
|---|---|
| Build script | `Assets/Blender/blender_evilMage000.py` — begins as a byte-identical copy of `blender_mage000.py` |
| Authoring file | `Assets/Blender/evilMage000.blend` |
| Renders | `Assets/Blender/_evilMage000/` |
| Health check | to be derived from `Assets/Blender/_mage000/audit_mage000.py` |

*Status: concept only. Nothing built.*
