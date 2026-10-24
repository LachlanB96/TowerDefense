The Silent Knight is a feared hero among monsters. A knight in shiny medieval armour, trimmed with the finest gold stolen from the monsters he has slain. The knight bears the emblem of the Templar, a shiny T of pure gold. The Silent Knight has bedazzled his own rubies into the T, signifying the Knight's lust for blood. In his right hand he holds his Golden Sword, a gift from the elves for an old quest. The knight's left hand holds The Templar's Book — a magic book written by Old Knights who seemed to never die. Although none of the knight's body is visible, covered in shiny armour, a red glow emits from within the helmet; one can only guess this power emanates from their eyes.


---

## Mechanics

*Status: design approved 2026-04-20. Not yet implemented. See [[Framework]] for the hero system this hero plugs into.*

### Identity

| Field | Value |
|-------|-------|
| Type code | `knight000` |
| Cost | $1500 |
| Sell value | $750 (50%) |
| Range | 3.5 |
| Footprint | 1.4 unit placement radius (same as towers) |
| Target priority | Strongest enemy in range — fits his lore ("lust for blood") |

### Auto-attack — Golden Sword

- **Type:** homing projectile (reuses `Velocity.cs` in homing mode).
- **Damage:** 5 per hit.
- **Cooldown:** 0.8s.
- **Visual:** thrown sword arcs toward target; on hit, projectile destroyed. Knight always holds a sword in hand between throws (cosmetic — the "return" is not simulated).

### Passive (L1) — Templar's Zeal

Attack-rate aura on every tower within 4 units of the knight.

| Level | Attack-rate bonus |
|-------|-------------------|
| 1 | +10% |
| 2 | +12% |
| 3 | +14% |
| 4 | +16% |
| 5 | +18% |
| 6 | +20% |
| 7 | +22% |
| 8 | +24% |
| 9 | +26% |
| 10 | +28% |

Implementation: each affected tower's cooldown is divided by `(1 + bonus)`. Applied per-frame or on range enter/exit. Visual: subtle red ground-glow ring under affected tower bases.

### Active 1 (L5 unlock) — Crimson Arc

Instant 360° sword sweep centred on the knight.

- **Area:** full circle at range 3.5 (same as his auto-attack range).
- **Damage:** 25 to every enemy in range.
- **Cooldown:** 12s.
- **Cast time:** instant, no channel.
- **Visual:** radial red slash VFX on the ground.

*Design note — why 360° and not a frontal cone:* The knight is a static hero with no facing direction controllable by the player. A frontal cone would require inventing a "face" mechanic for a fringe case; 360° solves it with zero UX wrinkle and still reads as "sword sweep."

### Active 2 (L10 ultimate) — The Templar's Book

Knight opens the book and channels for 3 seconds. During the channel:

- All enemies within range 8 of the knight take **5 damage per second**.
- Every enemy hit gains the **Judged** debuff: **+25% damage taken from all sources**, lasts **10 seconds** after application. Judged survives the channel ending.

- **Cooldown:** 60s (measured from channel start).
- **Interaction with auto-attack:** auto-attacks are paused during the 3s channel.
- **Visual:** red beam from the open book to every enemy in range + a floating cross glyph over each Judged enemy.

*Implementation note:* Judged is the first status effect beyond `BurnEffect`. Add a new `JudgedEffect.cs` component following the `BurnEffect` pattern. `Movement.Hit(damage)` gains a small hook that scales incoming damage by the multiplier of any active status effects on the target — tiny refactor.

### Design notes on lore → mechanics mapping

- **Golden Sword** from the lore → auto-attack.
- **Templar's Book** from the lore → Active 2 ultimate. The book is what the *old knights who never died* wrote; having it project the "Judged" debuff (literally marking enemies for judgement and amplifying their death from any source) cashes in that fantasy better than making the book deal its own damage alone.
- **Red glow from helmet** → shared colour motif across VFX (ground-glow under Zeal towers, Crimson Arc slash, beam from the book). Ties him visually to his own abilities without needing a separate "aura" effect on the knight himself.
- **Templar emblem / rubies / lust for blood** → target priority "strongest in range" instead of "closest" (attacks whatever's most worth killing, not whatever's nearest).
- **"Never die"** → the hero is genuinely invincible in game terms. The lore and the mechanics agree.

---

## Model

*Rebuilt 2026-07-30. Supersedes `char_knight2`, which the [[../Marketing/Steam store page|store-page spec]] rejected for hero duty: "at capsule scale it reads as a chrome blob with a red skirt, not a Templar."*

| | |
|---|---|
| Build script | `Assets/Blender/blender_knight000.py` (procedural, reproducible) |
| Authoring file | `Assets/Blender/knight000.blend` — every part named, modifiers live |
| Game asset | `Assets/Models/knight000.fbx` — **rigged**: 31 skinned meshes, 26 bones, 4 clips, ~118k tris, 5 attach empties |
| Renders | `Assets/Blender/_knight000/`, audit close-ups in `_audit/`, posed frames in `_pose/` |
| **Health check** | `Assets/Blender/_knight000/audit_knight000.py` — **must print PASS** |

Rebuild with `blender -b -P Assets/Blender/blender_knight000.py -- save render export`.

Run the audit after any geometry change. It checks non-manifold meshes, geometry
below the floor plane, coplanar emblem patches, and whether clasping bands are
concentric with the limb they sit on — all things that are invisible in a hero
render and obvious in a close-up.

### The three legibility rules it is built around

The model exists to fix a legibility failure, so these override normal realism:

1. **Silhouette first.** Spiked pauldrons, a swept golden crest and a flaring cape have to name the character at 184×184 with all interior detail lost. `_knight000/icon_184.png` is the standing test — if he stops reading as a Templar there, a change has regressed.
2. **Gold draws the form.** Steel sits deliberately dark (base ~0.24, roughness 0.31). Physically-correct bright polished plate is exactly what produced the chrome blob — it clips to white under any usable key and the internal drawing disappears. Every plate boundary is outlined in gold instead, so the form survives downscaling the way an inked drawing does.
3. **Dark recesses.** Mail voiders, plate undersides and the helmet interior use a near-black material. Without them the red eye glow has nothing to glow against.

### Lore → geometry

| Doc line | In the model |
|---|---|
| Shiny plate, no skin | Closed harness: cuirass + plackart, gorget, fauld, tassets, pauldrons, couters, poleyns, sabatons. Dark mail voiders fill every joint |
| Gold trim from slain monsters | Gold piping on every plate edge; three gold-capped monster fangs on a chain at his left hip |
| Gold **T** with rubies | Curved emblem standing 5 cm proud of the breastplate, five rubies set into it |
| Golden Sword (elven gift) | Fullered longsword planted point-down, wire-wrapped grip, faceted pommel, and a glowing **elven inscription** running down the fuller |
| The Templar's Book | Open tome on the flat of the left gauntlet, oxblood boards, gold corners, red light in the gutter, three gold Templar glyphs spiralling off the pages |
| Barbute, red glow from within | T-shaped aperture booleaned through the dome; a black inner shell behind it; two small saturated red emitters recessed inside |
| Golden plume | Crest of nine flat clumps arcing back off a gold socket |
| Vivid slightly-dark-blue cape | Parametric drape with wind sway, ~3.7 fold cycles, torn hem, gold hem trim, dark lining, and the gold T embroidered on the back |

### Rig

26 bones: `Root → Hips → Spine → Chest → Neck → Head`, a clavicle/arm chain and a
leg chain per side, `Sword` parented to `Hand_R`, `Book` to `Hand_L`, and a
four-bone `Cape1..4` chain off the chest.

Plate armour is the easy skinning case — every plate is **rigid**, so each mesh
is weighted 100% to one bone and nothing stretches. Two exceptions:

- **The cape** is one continuous sheet and gets graded weights down its bone
  chain, blended by height (`cape_weights`).
- **The tassets** are graded between `Hips` and `Thigh_{side}` across their three
  lames. Weighted purely to the hips they stand still while the thigh swings
  forward and strand the leg outside its own armour; weighted purely to the
  thigh they stop hanging from the belt.

Clips shipped: **Idle** (72f), **Walk** (32f, loops), **SwordSwing** (30f),
**BookCast** (60f). They double as the deformation test — the walk exercises
every leg joint, the swing the whole right arm and the sword bone, the cast the
left arm and the book. Render them with `_pose/` shots after any rig change.

- **Every action keys EVERY bone at rest on its first frame** (`key_all_rest`).
  An action only constrains the bones it animates; un-keyed bones inherit
  whatever pose was last evaluated, so BookCast picked up the sword arm
  mid-swing from SwordSwing — and that leaks into the baked FBX takes, not just
  the viewport.
- **`bake_merged` forces the armature to REST while baking.** Otherwise a posed
  rig gets baked into the merged mesh *and* applied again by the merged object's
  own armature modifier.
- **Side is stamped on each object at build time** (`CURRENT_SIDE`), not parsed
  from the name. Lame suffixes produce names like `Finger_R0_L0`, so looking for
  a trailing `_L`/`_R` finds the wrong token and mirrors the bone assignment.
- **Bone-local axes are not world axes, and this bites twice.** The spine bones
  stand upright, so their local **Y is the spine axis** and local Z is
  horizontal: a "torso twist" written as `rz` is actually a sideways *lean*,
  and an 18° lean swings the 1.2 m cape hem 140 mm down through the floor.
  Likewise `pose_bone.location` is in bone space, so a hip bob belongs in `.y`,
  not `.z` — written to `.z` it shoves him forwards and backwards instead.
- **Hip height is solved, not authored** (`ground_hips`). FK legs have no IK, so
  the hip-to-ankle vertical changes with every joint angle and the correct bob
  is a different number on every frame. Hand-tuning it got the phase inverted
  (hips driven down exactly when the support leg was straight). The solver
  measures the lowest sabaton per frame and drops the hips to match.
- **The cape hem needs ~55 mm of ground clearance at rest.** A 9° torso pitch
  swings it down by ~47 mm, so a hem that only just clears the floor standing
  still goes through it the moment he moves.

`check_anim.py`-style verification is worth re-running after any animation
change: per frame, lowest geometry z (must stay positive) and whether a foot is
actually planted.

### Things that will bite whoever edits this next

- **Emission strength fights AgX.** Above ~5 the view transform desaturates emitters toward white, so cranking it makes the eyes *paler*, not redder. Saturated colour against a black interior does the work, not intensity.
- **The cape emblem is laid out in world X, not in cloth UV.** The cape sways and widens as it falls; a UV-parameterised T comes out sheared and reads as a "7". `cape_u_for_x()` inverts the cross-section to keep it a cross.
- **The drape is flattened under the emblem** by a quartic plateau in `cape_point`. A fold running through the T bows the crossbar out of shape.
- **Key art must stay within ~20° of head-on.** Further round and the T foreshortens across the keel of the breastplate and reads as a 7 again.
- **Anything swept uses a rotation-minimizing frame.** A fixed world-up reference flips on near-vertical paths and detonates the tube into a spike.
- **`revolve(close_profile=True)` bridges to the ORIGINAL ring**, it does not append a duplicate point. Duplicating the first profile entry looks closed and leaves two coincident open loops — still non-manifold, and the audit will keep failing while the render looks fine.
- **Any patch on a curved shell must go through `densify_rows()`.** A stepped outline written as bare control points produces long quad bands that chord across the curvature; the cape emblem's stem spanned 40% of the cloth in one band and vanished inside it.
- **`finger_plates()` takes an explicit `up_dir`.** Deriving the plate normal as radial-from-an-axis works for fingers wrapping a grip cylinder and is degenerate for an open flat hand — the vector comes out parallel to the finger, orthogonalisation collapses, and every lame silently falls back to world Z, standing on edge as a row of teeth.
- **The wrist must sit ~78 mm back up the forearm from the grip.** With them coincident the whole fist generates inside the vambrace cuff.
- **Do not flute the breastplate.** Tried twice, heavy and light. Surface tubes on a panel that already carries the plackart step, the breast reinforce, rivets and the emblem catch shadow along their undersides and read as claw marks. Deepen the keel in `TORSO_TABLE` instead if it ever needs more form.
- **Emission fights AgX everywhere, not just the eyes.** Rubies at strength 0.9 read as pink plastic; the floating glyphs at 1.1 read as cream tags. Both sit near 0.35 now.
- **`pauldron_frame()`'s third axis must be negated by `side`.** `U.cross(A)` is *not* mirror-symmetric: it comes out outward-and-down on the right shoulder and inward-and-up on the left. Everything placed by a beta angle — spike, rondel, ruby, haute-piece — then lands somewhere different on each side, and the left haute-piece gets flung outward off the shoulder where it reads as a fourth limb. The audit's symmetry check exists because this was invisible in every hero render.
- **The cape's `ybase` is clamped against `torso_profile(z)`.** The cuirass is deepest at the chest, *below* the collar the cape hangs from, so any straight interpolation downward dips back inside the backplate over the shoulder blades and the cloth appears to erupt out of the armour partway down.
- **Gold must follow the form.** A gold heel disc and a gold toe bead were primitives parked near the sabaton rather than shaped to it, and they read as golden balls stuck on at random. Gold piping swept along each lame's leading edge does the same job correctly. Same lesson as the chest ribs: never park a primitive near a surface and hope.
- **Eyes are angular slits, not ellipsoids.** A soft round emitter reads as a cartoon eye however red it is.
- **Cloth folds are `|sin|^0.45`, not `sin`.** A sine is symmetric and rounded at both extremes, so a sine-folded cape still reads as a smooth sheet. Heavy cloth hangs in broad flat ridges separated by narrow cusped valleys, which is what the fractional power gives. The fold *spacing* is also modulated by a slow sine — evenly pitched folds read as corrugated metal.
- **Ribs must not taper to a point at their convergence.** A pauldron flute run all the way to the polar cap and thinned to zero becomes a needle lying across the shoulder. Start them off the pole and floor the taper around 0.55.
- **Rivets need a `lift` that clears the rib they sit on**, otherwise they generate inside it and vanish.
- **Ridges and fluting must modulate the surface's OWN cross-section**, never be swept tubes laid on top. `revolve(radial_fn=…)` and `limb(ridge_dir=…, flutes=…)` add a gaussian swell / cosine fluting to the radius. As separate tubes they read unmistakably as wire glued to the armour — the shin ridge looked like a splinter through the greave and the arm ribs like a rod running shoulder to hand. Same for the pauldron (folded into the cop shell) and the sabaton instep (a `crest` term in `superellipse_ring`).
- **Reduce the keel at source, not per-overlay.** Dropping `keel_scale` for the emblem alone pulls it *into* the chest — the keel is what holds the surface out — so it sank behind the plackart rim and the T came apart. The table's keel column is halved instead.
- **Cape fold damping is a GAUSSIAN.** A quartic plateau creates a genuinely flat panel with a hard boundary, and that boundary reads as a warp across the middle of the cape exactly where the emblem sits.
- **Anything arrayed radially must be built as mirrored pairs** about `THETA_FRONT`, not by stepping a fixed offset round the circle. Eight circlet gems at `2πi/8 + 22°` put the two rubies at 22° and 202° — visibly lopsided round the neck.
- **Three steels, not one.** Base plates dark and rougher, overlapping lames and rolled edges bright and polished, recesses near-black, plus anisotropy for a forged highlight. A single mid-grey metal is what made the armour read as featureless.

**Process:** diagnostic render scripts must `exec` the build script, **not** `open_mainfile` the saved `.blend`. Opening the blend renders whatever was last saved and silently hides every edit since — it made a whole fix pass look like it had done nothing.

### Not done

`Assets/Prefabs/knight000.prefab` still references `char_knight2.fbx` and hand-assembles its parts, so it does **not** pick this model up automatically. Rebuilding the prefab against `knight000.fbx` is a separate job.
