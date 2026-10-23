"""
Gloomfell - THE EVIL MAGE  (hero type code `evilMage000`)

An undead alternate of THE MAGE. This file began life on 2026-08-10 as a
byte-identical copy of the accepted `blender_mage000.py` (branch `model/mage000`,
commit 78977da), and is diverging from it by corruption rather than by rebuild.
That ancestry is the point: shared bones make the two characters read as the same
man before and after something happened to him. Prefer editing the parent's
existing tunables and builders over adding parallel ones - a global the parent
already exposes is a global the preview harness can already sweep.

Design source: Obsidian/TD/Heroes/Evil Mage.md
Parent design source: Obsidian/TD/Heroes/Mage.md (still authoritative for
anything the evil brief does not explicitly overturn)
  - broad-brimmed wizard hat, face lost in its shadow
  - long pale beard, the only thing that escapes the shadow
  - midnight-blue silk robe worn LOOSELY: open front, bell sleeves, flared hem
  - silver trim on every edge          - near-black under-robe and linings
  - gnarled blackwood staff planted point-down, taller than he is
  - a large violet gem crested on top in a silver claw setting

Modelling rules this is built around (see .claude/skills/blender-model-modev4):
  1. NOTHING LEVITATES. Every part touches or overlaps another. Several numbers
     below look arbitrary and are not - they are what makes two surfaces meet.
     The comments say so where that is the case. (Note this rule is about
     CONTACT, not about spectacle: an undead brief may legitimately want matter
     drifting free of the body, which is a deliberate exception to argue for
     in a design, not an accident to leave lying around.)
  2. SILHOUETTE FIRST. Hat + flared robe + staff-with-gem must name him from the
     outline alone, with every interior detail gone. This is a SCALE-FREE rule:
     it is about what survives when detail is lost, and it names no pixel size,
     because the size this model will be seen at is unknown and may change
     drastically.
  3. TRIM DRAWS THE FORM. Silver piping outlines the hem, the front opening, the
     cuffs, the mantle and the hat band, so the internal lines survive loss of
     detail. Blue-on-blue alone flattens to a blob.
  4. DARK RECESSES. Face void, robe opening, sleeve interiors and under-brim all
     use a near-black material, so the gem has something to glow against.
  5-9. Rounded forms only. Everything here is a lathe, a loft or a swept tube.
     There is not a single cube in this file, which is the easiest way to obey
     "never visible cubes".

No camera is privileged. The judged stimulus is a seeded 360 degree orbit drawn
fresh per wave; the named views below are conveniences, not the test.

Run headless:   blender -b -P Assets/Blender/blender_evilMage000.py -- save export render
Preview:        python Assets/Blender/_tools/preview.py evilMage000 --variants v.json

Conventions (shared with blender_knight000.py):
  * He faces -Y (Blender's front orthographic view). So:
        forward = -Y     back = +Y     his right = -X     his left = +X
    With the export axes below this lands facing +Z in Unity.
  * Z-up, origin on the ground between the feet. ~1.86 to the crown of the head,
    2.26 to the hat tip, 2.53 to the top of the gem.
  * Modifiers are left LIVE, never applied: they survive into the FBX (the
    exporter evaluates the depsgraph), they keep the .blend editable, and
    bpy.ops.mesh.bevel needs a 3D-viewport context that does not exist under
    `blender -b`. Everything is built with bmesh.ops + modifiers instead, both
    of which are entirely context-free.
"""

import bpy
import bmesh
import math
import os
import sys
from math import radians, sin, cos, pi
from mathutils import Vector, Matrix

# -- Paths ---------------------------------------------------------------------
# Worked out from this file's own path (the name its code was compiled under, which
# `blender -P`, build_one.py and exec(compile(src, PATH, "exec")) all set), so they
# hold wherever the repo lives. A copy run from a worktree under .claude/worktrees/
# still writes into the main checkout (CLAUDE.md, "Asset pipeline").
_REPO = os.path.abspath(os.path.join(os.path.dirname(sys._getframe().f_code.co_filename), "..", ".."))
_REPO = _REPO.split(os.sep + os.path.join(".claude", "worktrees") + os.sep)[0]
BLEND_PATH = os.path.join(_REPO, "Assets", "Blender", "evilMage000.blend")
FBX_PATH   = os.path.join(_REPO, "Assets", "Models", "evilMage000.fbx")
RENDER_DIR = os.path.join(_REPO, "Assets", "Blender", "_evilMage000")


def _flag(name, default=False):
    """Flags come from either of the two ways this file gets run:
    headless   -> blender -b -P blender_evilMage000.py -- save export render
    in-session -> set the name in the namespace before exec'ing the file
    """
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return globals().get(name, default) or name.replace("DO_", "").lower() in argv


DO_RENDER = _flag("DO_RENDER")
DO_EXPORT = _flag("DO_EXPORT")
DO_SAVE   = _flag("DO_SAVE")

# EEVEE TAA samples for any view that does not name its own count. It is a global
# so a preview run can override it, and so there is exactly one place to look.
#
# This exists because of a real bug: render_view() used to set the sample count
# ONLY when a view passed `samples=`, so every view that did not - front, side,
# back, both icons - silently inherited whatever the previous view had left on the
# scene, and SAMPLE_SCALE never touched them at all. A view's quality therefore
# depended on which views happened to run before it in that run, which made pixel
# measurements across runs with different view sets not strictly comparable. That
# matters now that modellers are asked to measure from rendered pixels.
BASE_SAMPLES = 96

# ==============================================================================
#  SKELETON + TUNABLES
#
#  Every value the shape depends on lives here as a module-level global, which is
#  what makes the file drivable by _tools/preview.py: a variant can override any
#  of them without touching the source.
# ==============================================================================

Z_GROUND   = 0.008        # not 0.0: solidify and bevel both nudge boundary verts
                          # downward, and the audit fails anything below z=-0.001.
                          # 8 mm is invisible at 2.5 m and leaves margin for both.
                          # ROBE_TABLE and STAFF_SPINE both start here.
Z_HIP      = 1.020
Z_WAIST    = 1.145
Z_CHEST    = 1.440
Z_SHOULDER = 1.495
Z_NECK     = 1.620
# Head, neck, beard and hat were all lifted 93 mm on 2026-08-01. Before that the
# brim's outer edge drooped to z 1.648 against a shoulder line at 1.495 - a 70 cm
# hat hovering 15 cm above a 48 cm frame - and the whole thing read as a table
# resting on his shoulders. Two rounds of variants blamed the mantle and then the
# collar; removing each of them changed nothing, because the shelf was always the
# brim. The fix is the gap of neck between brim and shoulder, not a smaller hat:
# "broad-brimmed" is in the brief.
Z_NECK_BASE = 1.545
Z_NECK_TOP  = 1.793
Z_HEAD     = 1.838        # head centre
Z_BRIM     = 1.883        # hat brim reference plane
Z_HAT_TIP  = 2.265        # crown apex. The TIP itself hangs below this - see
                          # HAT_SPINE, the point curls back over and down.

HEAD_R     = 0.106
HEAD_SCALE = (1.00, 1.02, 1.06)

# Eye glints in the face shadow. OFF, and the code is kept only to record why.
#
# TESTED 2026-08-01 and rejected on evidence, not taste. Rendered with the glints
# on and off, the two images are pixel-for-pixel indistinguishable at every
# camera the model has, including the 184 icon. A deliberately low, close camera
# aimed up under the brim shows the same thing: THERE IS NO VISIBLE FACE. The
# brim's outer edge droops to z 1.741 and the beard's top ring starts at 1.815,
# so between them they occlude the entire front of the head from any horizontal
# or downward view - and the game camera looks down. Eye glints here are
# geometry no player can ever see.
#
# Two things follow for whoever picks this up. First, if a visible face is ever
# wanted, the fix is upstream: lift the brim's underside or start the beard
# lower, and only then revisit this flag. Second, they are NOT floaters - each
# slit is seated into the head sphere so it straddles the surface, so the
# FLOATERS_OK entry this was originally expected to need never applied.
EYES_ON    = False
EYE_X      = 0.040
EYE_Z      = 1.848
EYE_SCALE  = (0.030, 0.011, 0.0085)
EYE_CANT   = radians(9.0)     # inner corners drop: a scowl, not a stare
C_EYE      = (0.62, 0.16, 1.00, 1.0)
EYE_EMIT   = 2.2              # small and in deep shadow, so it can carry more
                              # than the gem without going white under AgX

THETA_FRONT = -pi / 2.0   # front centreline: he faces -Y
THETA_BACK  = pi / 2.0

# -- Robe ----------------------------------------------------------------------
# Radius and fold depth by height. The hem is deliberately WIDE: a heavy flare
# reads as immovable, which is what a static hero wants, and it gives the icon
# silhouette a broad base under the narrow hat.
#                 z,     radius, fold amplitude
ROBE_TABLE = [
    # The bottom three rows are the POOL, and they are not a continuation of the
    # cone above them. 0.354 -> 0.396 over the last 18 cm is a 4 cm flare, which
    # is a skirt that simply STOPS 8 mm above the floor - the hem close-up showed
    # daylight under its edge. Cloth that has run out of leg spreads: the kick
    # below happens in the last 4 cm, which is what reads as fabric lying on the
    # ground rather than hanging over it.
    #
    # The first row sits at 0.020, NOT at Z_GROUND. Solidify and bevel nudge the
    # boundary verts down by roughly the hem's own wall thickness projected onto
    # z, and the flatter the cloth is where it ends the more of that thickness
    # points straight down: at 0.008 with this flare the robe reached -0.0062 and
    # the audit failed it as below the floor. The wider foot hides the extra
    # clearance anyway - a pooled hem casts a tight contact shadow.
    (0.020, 0.442, 0.030),   # hem, pooling on the ground
    (0.046, 0.412, 0.044),
    (0.076, 0.388, 0.055),
    (0.190, 0.354, 0.060),
    (0.350, 0.324, 0.057),
    (0.530, 0.298, 0.049),
    (0.710, 0.273, 0.041),
    (0.880, 0.247, 0.031),
    (1.020, 0.223, 0.022),   # hip
    (1.145, 0.201, 0.013),   # waist - the sash pulls the cloth in
    (1.265, 0.238, 0.018),
    (1.360, 0.268, 0.022),
    (1.440, 0.287, 0.022),   # chest
    (1.505, 0.293, 0.017),   # shoulder shelf - the widest point of the body
    (1.556, 0.256, 0.013),
    (1.600, 0.196, 0.009),
    (1.640, 0.152, 0.006),   # neck opening
]

# Half-DEPTH as a fraction of half-width, by height, plus a superellipse power.
#
# This is the single most important table in the file for the shoulders. With a
# circular cross-section the torso is as deep as it is wide, so it has no front,
# no back and no shoulder - it is a cone, and the arms read as tubes rammed into
# the side of it. A real body at chest height is roughly 0.7 as deep as it is
# wide, and the power below flattens the chest and back further so the section
# has actual flat faces for light to describe.
BODY_DEPTH = [
    (0.008, 0.96),           # the skirt is nearly circular - it is a cone of cloth
    (0.530, 0.92),
    (0.880, 0.85),
    (1.145, 0.78),           # waist
    (1.360, 0.71),
    (1.505, 0.66),           # shoulders: broad and shallow
    (1.640, 0.78),           # neck rounds back off
]
BODY_POWER = 0.90            # <1 squares the section off; 1.0 is a pure ellipse

# Silk, not wool. The knight's cape lesson applies in reverse: heavy cloth wants
# few broad ridges, silk wants MANY fine ones. FOLD_LOBES must stay an integer or
# the fold function stops being 2*pi periodic and the loft seam tears open.
FOLD_LOBES = 7            # |sin(7*theta)| -> 14 folds around
FOLD_POWER = 0.32         # not sin(): a sine is rounded at both extremes and
                          # reads as a smooth sheet. The fractional power gives
                          # broad ridges separated by narrow CUSPED valleys, and
                          # the cusp is the whole effect - at 0.45 the valleys
                          # were still wide enough that smooth shading turned
                          # them into gradients, so the robe read as shaded
                          # rather than as folded.
FOLD_MEAN  = 0.83         # mean of |sin|^FOLD_POWER, so folds sit ON the radius
                          # rather than inflating it. Recompute this if the power
                          # changes or the whole robe gains a few millimetres.
FOLD_SKEW  = 0.55         # slow modulation of fold SPACING - evenly pitched
                          # folds read as corrugated metal
FOLD_PHASE = 0.90
FOLD_TWIST = 0.34         # folds drift round as they fall
# A second, finer set of folds at a different pitch and drifting the other way.
# Real cloth does not fold at a single frequency; one harmonic is what made the
# first robe look machine-pleated.
FOLD_LOBES2 = 13
FOLD_TWIST2 = -0.62
FOLD_FINE   = 0.42        # depth of the fine set, relative to the main one

ROBE_THICK  = 0.018       # solidify depth of the outer robe shell
UNDER_INSET = 0.020       # under-robe radius offset. MUST be a touch larger than
                          # ROBE_THICK: the two surfaces then sit 2 mm apart and
                          # count as touching under rule 1. Equal values leave
                          # them coincident, larger ones float the under-robe.

# How far the robe is open at the front, as a half-angle in radians per height.
# Wide V at the collar, pinched shut at the sash, parting again down the skirt.
ROBE_OPEN = [
    (0.008, 0.150),
    (0.300, 0.115),
    (0.620, 0.090),
    (0.900, 0.078),
    (1.080, 0.070),
    (1.160, 0.090),
    (1.280, 0.235),
    (1.400, 0.365),
    (1.500, 0.470),
    (1.620, 0.560),
]

TRIM_R = 0.0075           # silver piping radius
HEM_BAND = 0.105          # depth of the darker border round the bottom
LAPEL_STUDS = 6           # fastenings down the right-hand lapel edge

# -- Mantle / collar -----------------------------------------------------------
# The shoulder mantle was removed on 2026-08-01 - see build_yoke() for why. Its
# MANTLE_* tunables went with it rather than being left behind as dead globals a
# variant could still set and wonder why nothing happened.
COLLAR_TOP  = 1.688
COLLAR_OPEN = 0.640
COLLAR_FLARE = 0.048      # any fatter and it reads as a padded neck roll in the
                          # side view rather than as a collar
# Where the yoke seam finishes, as a fraction of pi round from the front, and how
# far it drops below its starting height once it is past the shoulder.
#
# It used to stop at 0.92 and come back up to the height it started at, so the
# two seams ended 7 cm short of the spine, 14 cm apart, at the same z as the
# front - two silver dashes floating on the largest untrimmed field on the model.
# Its own docstring said "down the back", and it never went down the back.
#
# Note for anyone tempted to lift this seam off the cloth instead: tried on
# 2026-08-01, 30 mm at the apex, on the theory that it was being buried in the
# shoulder cap. It was not - from a front-quarter camera it disappears over the
# shoulder's own horizon, which is just occlusion - and the lift changed nothing.
YOKE_END  = 0.99
YOKE_FALL = 0.095

COLLAR_NECK_R = 0.105     # radius the wall closes to at the lip.
                          #
                          # The collar has to START on the robe or it levitates,
                          # and the robe at z0 is at its shoulder shelf - 0.262.
                          # Carrying that radius straight up, which is what it
                          # used to do, wraps a 14 cm wall round a neck capsule of
                          # radius 0.06 and leaves a 20 cm annular hole you look
                          # down into: a bucket, not a collar. So the wall narrows
                          # as it rises. 0.105 clears the neck by ~4 cm, which is
                          # a collar standing off the throat; much tighter and the
                          # rolled lip closes on the neck itself.

# -- Sash ----------------------------------------------------------------------
SASH_Z   = 1.148
SASH_R   = 0.207
SASH_H   = 0.052          # half-height of the wrap
SASH_D   = 0.017          # half-depth (radial)

# -- Arms ----------------------------------------------------------------------
# His right (-X) grips the staff; his left (+X) is held forward, open.
SHOULDER_R = Vector((-0.262, -0.006, 1.470))
ELBOW_R    = Vector((-0.350, -0.060, 1.250))
# The wrist is swung FORWARD (-y) as well as out, so the staff arm approaches the
# shaft from the camera side instead of from directly behind it.
#
# This is not a pose tweak, it is what makes the prosthetic visible at all. At the
# old y = -0.109 the forearm ran almost straight down the line of sight into the
# shaft: the staff's own silhouette covered the outer half of the limb, the only
# lighter pixels left were finger tips poking past the FAR edge of the wood, and
# they read as rivets stuck on the staff rather than as a hand holding it. Out
# here the whole plated cylinder sits in the open gap between robe and shaft,
# silhouetted against background rather than against wood, and the fingers wrap
# across the near face where they can actually be seen. It also costs nothing:
# the wrist is still 0.068 from the shaft axis, the same grip distance as before.
WRIST_R    = Vector((-0.452, -0.158, 1.090))

SHOULDER_L = Vector(( 0.262, -0.006, 1.470))
ELBOW_L    = Vector(( 0.312, -0.050, 1.240))
WRIST_L    = Vector(( 0.235, -0.215, 1.150))

# Fraction of the ELBOW->WRIST span at which the cuff sits. Less than 1.0 so the
# hand actually emerges - the lore says the beard and the two hands are the only
# proof there is a man in there.
SLEEVE_END_R = 0.22       # the staff arm's sleeve stops just past the elbow.
                          # Bounded above by staff clearance: at 0.35 the cuff
                          # has travelled far enough down the forearm that the
                          # bell reaches the shaft again.
                          #
                          # Now also bounded above by the prosthetic. This cuff is
                          # what REVEALS the wrought arm, and it is already rolled
                          # back well behind mid-forearm - the short sleeve was
                          # always this side - so the whole plated run from
                          # PROS_T0 down is in the open with a few centimetres of
                          # near-black stump above it. It did not need moving and
                          # it must not be lengthened to "match" the left: the two
                          # asymmetries are supposed to stack, not cancel.
SLEEVE_END_L = 0.44
SLEEVE_R0    = 0.104      # radius at the shoulder
# The two sleeves are deliberately NOT the same. His left hangs as a full bell;
# his right is pushed back up the arm to grip the staff, which is both what
# actually happens when you hold something and the only way the bell can clear
# the shaft. Asymmetry here is a feature, not an oversight - the lore says
# nothing about him is ever straightened.
SLEEVE_FLARE_R = 0.096    # barely flared at all - a straight sleeve. Wider than
                          # this and, being short, it gapes and reads as a pot
                          # balanced on the elbow.
SLEEVE_FLARE_L = 0.188    # 0.152 was not a bell. The flare goes on as t**1.8, so
                          # the sleeve holds ~0.118 through its whole midsection
                          # and only opens at the very lip: a tube with a small
                          # trumpet on the end. "Wide bell sleeves" is one of the
                          # three clauses the doc uses to define the robe, so this
                          # one has to actually read as one. Bounded above by the
                          # hand: the mouth sits ~11 cm back along the axis from
                          # the wrist, and past ~0.21 the rim swings forward of
                          # the fingers and veils the hand - and the hands are
                          # half the doc's evidence that there is a man in there.
SLEEVE_WALL  = 0.015
SLEEVE_RIPPLE = 0.055     # cloth ripple, as a FRACTION of radius
SLEEVE_MOUTH  = 0.030     # how far the cuff edge waves along the arm axis. A
                          # mouth cut as a flat plane is what made the first
                          # sleeve read as a metal bucket.
# The sleeve tube starts INSIDE the body, not at the shoulder joint, so its open
# end is buried in the robe instead of showing as a hole through the armpit.
SLEEVE_ROOT  = 0.45       # fraction of the shoulder's x kept at the tube's start

FINGER_KNUCKLE = 0.17     # how far the knuckle bulges swell a digit's radius

# Where the forearm stops, as a fraction of elbow -> wrist, and its end radius.
#
# The problem this fixes: the grip hand's palm is centred ON the wrist point, so
# a forearm ending there at radius 0.034 put a 6.8 cm near-black ball inside the
# hand. The palm is only 5.2 cm thick, so the ball came out through both faces -
# only fragments of skin survived, with a jagged intersection edge across the
# middle of the palm, and at figure scale the staff hand read as a dark blob
# with pale specks on it.
#
# The fix is the RADIUS, not the length. 0.021 is under the palm's 0.026
# half-thickness, so the cap is swallowed by the hand instead of the other way
# round. FOREARM_END must stay at 1.0: the endpoint IS the contact. Shortened to
# 0.88 the left forearm's nearest neighbour went to 12.8 mm and the audit failed
# it as levitating, because the open left hand sits ~18 mm forward of the wrist
# and the forearm has nothing else within reach - the bell sleeve's wall is
# 11 cm away by the elbow.
FOREARM_END = 1.00
FOREARM_R1  = 0.021

# -- The staff hand: a wrought-silver prosthetic -------------------------------
# At the Weeping Gate he held the door shut from the inside for one night. The arm
# did not come back out with him. The hand the Grey Lanterns wrought for him closed
# on the staff and has not opened since - which is why the staff is never set down,
# and why the gem is always exactly where he is.
#
# Built as an articulated vambrace: a bright collar band where the cloth stops, four
# overlapping lames ringed round the forearm, two tiles over the back of the fist,
# then four fingers of three shells each, fused around the shaft.
#
# Two things bound every number below.
#
# STAFF CLEARANCE. The lames are full rings about the limb axis, and that axis still
# runs toward the shaft, though far less steeply now that WRIST_R has swung forward:
# a ring drawn perpendicular to it reaches ~1.01x its own radius in the direction of
# the staff (it was 1.13x), and the shaft's ridge crests and wound cord put its
# effective surface out near 0.046 rather than at STAFF_RADII's 0.034. Past t = 0.68
# a ring still big enough to read as armour is inside that, so the ring stack stops
# there and the fist is plated with open tiles instead.
#
# VALUE. This is where the first attempt failed and it failed in the obvious
# direction. "Do not compete with the gem" was read as "be dark", the arm came out
# at the same value as the near-black under-sleeve and the staff shaft, and what it
# rendered as was a grubby ribbed hose. There is an enormous amount of room between
# near-black and stealing the frame, and the whole point of this limb is that it is
# the one LIGHT thing on a dark figure. So M_PROS sits a clear step below the beard
# and a clear step above the robe's silver trim - it was at beard value until d37,
# which was one step too high - and it gets there through
# a partly DIELECTRIC response rather than through a brighter mirror. That matters:
# a metallic=1.0 surface has no diffuse term and only shows where a highlight lands,
# which is exactly why the first pass read as dark no matter what its base colour
# said. Hue stays neutral grey; hue is the gem's lever, value is this arm's.
PROS_COLLAR  = 0.30       # where the metal STARTS, as a fraction of elbow ->
                          # wrist: a hard bright band, not a fade. The cuff is
                          # back at SLEEVE_END_R = 0.22 and its mouth waves +-3 cm
                          # along the arm, so a plate here would be half-swallowed
                          # by cloth and the reveal would read as a lumpy rolled
                          # sleeve. The collar is the terminator: cloth stops, one
                          # unmistakable ring of bright metal, then plate.
PROS_T0      = 0.35       # first lame, as a fraction of elbow -> wrist
PROS_T1      = 0.68       # last lame on the forearm - see STAFF CLEARANCE above
PROS_LAMES   = 4          # + 2 tiles over the fist = 6 plates in the run.
                          # FOUR, not the eight the shape suggests. At the size
                          # this is actually seen a fine stack of rings averages
                          # out into grey corduroy and the segmentation stops
                          # being information; four chunky plates each survive on
                          # their own. Same reason the fingers are big.
PROS_R0      = 0.0410     # lame mid-surface radius at PROS_T0 ...
PROS_R1      = 0.0262     # ... and at PROS_T1. The two together are the taper.
                          # Both are ~12% fatter than a forearm needs. The plated
                          # cylinder has to be a MASS bridging the gap between
                          # robe and shaft, not a pipe: at 184 px it is about six
                          # pixels of width and there is nothing to spare.
PROS_HL_LIP  = 0.0128     # half-length of a lame toward the HAND, and toward the
PROS_HL_HEAD = 0.0062     # elbow. Deliberately unequal: the long end is the lip,
                          # it stands ~9 mm of radius proud of the next lame down
                          # the arm and overhangs it, and the 4.5 mm the two ends
                          # leave between them is the slot the gasket shows
                          # through. Made equal, the stack reads as a row of
                          # separate rings instead of as overlapping plate.
PROS_D       = 0.0075     # half-thickness of a shell
PROS_LIFT    = 0.0070     # how far the lip rises off the mid-surface
PROS_PHI0    = radians(-17.0)   # where the wrap starts, measured from body-side
PROS_SPAN    = radians(304.0)   # ... and how far round it runs. The 56 deg left
                                # open faces away from every rendered camera, so
                                # the vambrace reads closed from the front and the
                                # opening only ever contributes more near-black.
PROS_EDGE_R  = 0.0042     # the bright band along each lip. A HAIRLINE here (it
PROS_EDGE_HL = 0.0045     # was 1.8 mm) does not survive: it broke up into a few
                          # scattered speculars and was gone by hero scale, let
                          # alone at 184. At 8-9 mm it is four or five pixels of
                          # continuous bright edge at hero scale and it is the
                          # thing that draws the plate boundaries (rule 3).
PROS_GAP_R   = 0.0030     # how far the near-black gasket stands proud of the
                          # mid-surface. Still well BELOW the crest on purpose: a
                          # gap has to read as a recess (rule 4), not a third band.
PROS_CORE_IN = 0.0055     # how far the near-black core sits inside the mid-
                          # surface - i.e. just behind the shells' inner face, so
                          # it fills every joint without poking through one

# -- Beard ---------------------------------------------------------------------
# Runs from inside the head, out under the brim shadow, and down over the chest.
# The y values are what keep it PROUD of the robe: sunk into the chest surface it
# reads as a stain rather than as hair.
#                 z,      y,      half-width, half-depth
# (z, y, half_width, half_depth) down the beard. The y column is the one that
# matters and it is not free: the beard hangs down the CHEST, so each row wants to
# sit just proud of the surface behind it, which below z 1.640 is the UNDER-robe
# (the outer robe is open across this whole width) at UNDER_INSET inside the robe
# radius. Run the y column out much further than this and every check still
# passes - the locks are manifold, symmetric, and touching the head at the top -
# while the beard hangs in mid-air a hand's width off the chest and reads from the
# side as a beak rather than as hair. It did exactly that until 2026-08-01: the
# tip was at -0.360 against an under-robe front of -0.189.
BEARD_TABLE = [
    (1.815, -0.078, 0.076, 0.052),   # inside the head sphere: the anchor
    (1.741, -0.122, 0.096, 0.064),
    (1.653, -0.152, 0.100, 0.060),   # BEARD_TABLE[2][0] is the audit's cut height
    (1.565, -0.176, 0.092, 0.052),   # from here down, ~2 cm proud of the underrobe
    (1.489, -0.188, 0.060, 0.034),
    (1.429, -0.192, 0.016, 0.012),
]
# The beard is five separate locks. Each entry is (x offset, width scale, length
# scale) - the length scale is what makes the bottom edge fork instead of running
# straight across, which is most of why this reads as hair at all.
BEARD_LOCKS = [
    (-0.072, 0.80, 0.56),
    (-0.037, 0.94, 0.82),
    ( 0.000, 1.00, 1.00),
    ( 0.037, 0.94, 0.86),
    ( 0.072, 0.80, 0.62),
]
BEARD_LOCK_R = 0.35       # lock radius as a fraction of the table's top width.
                          # Wide enough that neighbouring locks MERGE near the
                          # chin and only separate lower down - five distinct
                          # tubes all the way up reads as a mop, not a beard.
                          #
                          # 0.56 with the offsets half the above was the same
                          # mistake in numbers: one lock was then ~9 cm across at
                          # the widest table row while adjacent axes were 2.6 cm
                          # apart, so each lock's axis sat well inside its
                          # neighbour and the union had no notch anywhere. The
                          # five-lock build is only worth anything if the outer
                          # ones break the silhouette, and they cannot break what
                          # they are buried in.
                          #
                          # Thickness and spread move TOGETHER, and both are
                          # bounded. Breaking the locks apart at 0.30 also cost
                          # the beard about a third of its mass, and the doc
                          # gives it a job that needs mass - it is what carries
                          # the wizard read at icon size, which a shadowed void
                          # cannot. Putting the thickness back alone would just
                          # re-fuse them, so the axes moved out by the same
                          # proportion.
                          #
                          # Two ceilings, both live at these numbers:
                          #   * the notch: a lock's radius has to stay under the
                          #     axis spacing at the beard's widest row, or its
                          #     neighbour's axis sits inside it and the union has
                          #     no silhouette break. That caps this at ~0.366.
                          #   * the anchor: the outermost axis has to stay near
                          #     the head ellipsoid at the top row, which is what
                          #     keeps all five off the levitation list. Past
                          #     ~0.075 the axis leaves the sphere, and only the
                          #     lock's own radius is then holding it on.
BEARD_TAPER_FALL = 0.45   # extra monotone thinning down the lock, on top of the
                          # table. Without it the table's mid-beard bulge (0.076
                          # -> 0.100) makes every lock FATTER exactly where they
                          # most need to come apart.

# -- Hat -----------------------------------------------------------------------
# THE BRIM IS THE SILHOUETTE (d24). It spans ~1.6x the shoulder line, drops its
# front edge well below eye height so the face void is total, and is warped hard
# and asymmetrically: his LEFT sags almost onto the shoulder, his RIGHT lifts and
# hooks back over itself. The point of spending the largest silhouette change on
# this asset here is that a huge brim adds no VALUE at all - every new square
# centimetre of it is dark cloth or near-black lining - while changing the
# outline more than anything else on the model could. Six previous changes were
# rejected either for being invisible at 184 or for putting a bright area on the
# model; this is deliberately neither.
#
# Brim cross-section, traced out along the top and back along the underside.
# close_profile wraps it into a manifold shell. The first entry is deliberately
# INSIDE the head sphere - that intersection is the whole reason the hat is not
# a levitating part.
#
# The first column is NOT a radius in metres. It is a NORMALISED radius u, where
# u = 1 is the outer edge AT THAT AZIMUTH; only the second column (the shell's
# own thickness, and the slight fall of the top surface) is in metres. Every
# scrap of reach, droop and irregularity has to vary with azimuth, and a lathe
# profile cannot express that - so it all lives in brim_rz() instead.
# Rows are dense in the OUTER half on purpose. The fold lobes below turn through
# 130 degrees inside the last third of the width, and a bend cannot be smoother
# than the rows that carry it - four rows across a 130 degree turn is a chamfer,
# not a fold.
# WEIGHT, not sheet. 3/3 verifiers read the previous section as "cut sheet",
# "paper", "card", "sheet metal", with "both wingtips tapering to a knife edge".
# So the felt is now 44 mm where it leaves the crown and tapers to 16 mm at the
# lip - thinning, but never to a point - and the outer edge is finished with a
# real rolled hem (Hat_BrimHem, below) rather than by running the two surfaces
# together. Thick root plus heavy hem is also the shape that makes the droop read
# as ancient felt collapsing under its own weight instead of cloth in wind.
BRIM_PROFILE = [
    (0.150,  0.020),      # inside the head sphere: the anchor
    (0.250,  0.017),
    (0.350,  0.014),
    (0.450,  0.012),
    (0.550,  0.010),
    (0.650,  0.009),
    (0.740,  0.008),
    (0.810,  0.008),
    (0.870,  0.007),
    (0.920,  0.007),
    (0.960,  0.007),
    (0.985,  0.006),      # outer edge, top - buried inside the rolled hem
    (0.985, -0.010),      # outer edge, underside      <- BRIM_UNDER_FROM
    (0.960, -0.010),
    (0.920, -0.011),
    (0.870, -0.012),
    (0.810, -0.013),
    (0.740, -0.015),
    (0.650, -0.016),
    (0.550, -0.018),
    (0.450, -0.020),
    (0.350, -0.022),
    (0.250, -0.024),
    (0.165, -0.024),      # close_profile bridges this back to the anchor
]
# Index of the first UNDERSIDE row. Everything from here on is the return run,
# and it is what selects the near-black lining - see build_hat().
BRIM_UNDER_FROM = 12
# Index of the first row that is DARK - the hanging skirt.
#
# MEASURED, run-308, per-object emissive ID pass on Hat_Brim's two material
# slots: of every hat pixel the camera can see, the underside is 5.2% in
# hero_34, 5.5% at icon_full_184 and **0.0% - zero pixels - in front**. Three
# verifiers asked for a near-black underside; in the view they asked it of
# there is no underside on screen at all to darken.
#
# The mechanism is the fold itself. Section C's "the front camera sits at chest
# height, so the brim is seen from below" was written for a brim folding ~0-20
# degrees. This one folds 46-52 degrees at rest with a 68-degree sag lobe, and
# past roughly 40 degrees of droop the TOP surface has rotated far enough to
# face a chest-height camera square on: a point at the front with 50 degrees of
# fold has normal (0, -0.77, +0.64) against a view vector of about (0, -1.0,
# -0.1), i.e. n.v = +0.71. The underside swings up out of sight in the same
# motion. So the whole of BRIM_UNDER_FROM's near-black lining is on the far side
# of the cloth from every judged camera, and no value change to it can reach the
# render.
#
# What the camera DOES see out there is the hanging outer skirt - the part that
# has turned past the knee and dropped - and on a rain-soaked felt that is the
# part in its own shadow. So the dark side of the brim moves ONTO it. Everything
# from this row outward, on both surfaces, is one matte near-black felt; the
# rows inboard of it stay the lit shelf around the crown.
#
# Expressed as a profile ROW, not as a fold angle, on purpose. Row indices are a
# constant-u ring, so the boundary is r = u*R(a) - a smooth closed curve that
# inherits every warp and dent in the outline and cannot stagger. A threshold on
# the local fold angle would snap radially to whichever of the 12 rows it landed
# between as the azimuth swept, and 0.04*R is an 11 px staircase in hero_34;
# that is the aliasing failure section E warns about, arrived at from the other
# direction.
BRIM_DARK_FROM = 6
# The rolled hem: a real bead of cloth swept round the outer edge, in METRES, so
# it stays the same physical thickness at every azimuth however far the reach
# swings. 34 mm against a 16 mm lip, so it visibly swells out of the sheet.
BRIM_HEM_R = 0.017
BRIM_HEM_U = 1.000        # just outboard of the sheet's lip at 0.985, so the
BRIM_HEM_Z = -0.002       # sheet's cut edge is buried inside the roll
BRIM_NOM   = 0.590        # reach used for the INNER rows. They must not swing
                          # with the per-azimuth reach or the anchor ring walks
                          # out of the head sphere on the wide side and the hat
                          # goes back on the levitation list.

# ---- reach ----
# Four anchors, at his LEFT (+X), the BACK (+Y), his RIGHT (-X) and the FRONT
# (-Y). brim_quad() interpolates them as a 4-point DFT, so each number below is
# exactly the value at its own anchor and can be retuned on its own.
#
# Metres to the outer edge, before the fold bends it back in. His right is held
# IN on purpose: the staff passes within ~0.50 m of the hat axis at brim height,
# and cloth through wood is a failure this asset has already paid for once (see
# SLEEVE_FLARE_R).
BRIM_REACH = (0.700, 0.560, 0.450, 0.630)
# Hand-warp on the reach. TWO incommensurate lobe counts plus a dent, because a
# single harmonic at any amplitude is still an ellipse - which is exactly what
# three verifiers called the first attempt. Peak deviation here is ~0.13 m on a
# ~0.60 m reach, i.e. +-21%. The first attempt ran 5-8% and every verifier read
# the outline as "a clean smooth ellipse simply rotated about the forward axis".
# Relative pixel counts were what hid that: 0.030 -> 0.050 moved 39% more pixels
# and was still nowhere near enough to break the ellipse. Judge this one in
# absolute metres against the reach, not in percent-change against itself.
BRIM_WAVE3    = 0.085
BRIM_WAVE3_PH = radians(54.0)   # phased so a TROUGH lands at the staff's
                                # azimuth. This is a CLEARANCE number, not a look.
BRIM_WAVE5    = 0.042
BRIM_WAVE5_PH = radians(200.0)
BRIM_DENT   = 0.130
BRIM_DENT_A = radians(312.0)   # front-left: a silhouette edge in BOTH judged
BRIM_DENT_W = radians(24.0)    # views

# ---- fold ----
# Degrees of arc the radial axis turns between the fold line and the edge.
# Positive folds DOWN.
#
# The first attempt expressed this as four anchors alone, which decomposes to a
# dominant cos(theta) term - and a cos(theta) bend on a disc is, exactly and
# only, a tilt about the forward axis. That is why all three verifiers described
# a rotated disc with "only one idea in it". So the anchors now carry a modest
# residual slouch and the actual shape comes from two LOCALISED lobes plus a
# ripple, none of which a low-order harmonic can imitate.
# Raised across the board from (40, 26, 6, 34): 2/3 verifiers read the upswept
# side as "jaunty - sombrero, swashbuckler, rakish", which pulls against exalted
# and grim. A heavier base slouch biases the whole deformation from WINDSWEPT
# toward COLLAPSING UNDER ITS OWN WEIGHT, which is the same instruction as the
# rolled hem above. The flip lobe was made proportionally stronger to compensate,
# so the one upward event survives the extra droop instead of being cancelled by
# it - see BRIM_FLIP.
BRIM_TILT   = (52.0, 40.0, 26.0, 46.0)
# The sag: a real flop over the front-left, past vertical, so cloth hangs rather
# than slopes. Centred where it lands on the silhouette edge of BOTH judged
# views (front reads theta 0/180, hero_34 reads theta ~321/141).
BRIM_SAG    = 68.0
BRIM_SAG_A  = radians(348.0)
BRIM_SAG_W  = radians(46.0)
# The flip-back. NEGATIVE and past -90, which is the whole point: under -90 the
# edge has turned further than straight up, so it rolls back over itself and the
# silhouette gets a re-entrant curve. At -42 it merely rose, and 2/3 verifiers
# said the promised event on that side never happened.
BRIM_FLIP   = -155.0
# Placed at 140, not at his right (180), for two reasons that happen to agree.
# It is the silhouette edge of hero_34 and therefore of icon_full_184 too, so the
# event is on the outline in the two views the panel judges. And it is 52 degrees
# clear of the staff's azimuth (~192), which is what stops the raised edge
# running up the shaft: 2/3 verifiers called that "a muddled dark cluster in
# exactly the space that should run cleanly up to the gem".
BRIM_FLIP_A = radians(140.0)
BRIM_FLIP_W = radians(34.0)
# THE DRAPE. Four more localised fold lobes, alternating sign, so the hanging
# cloth breaks into separate folds instead of sweeping round in one bend.
# Each entry is (degrees, azimuth, half-width), same Gaussian form as the sag and
# the flip above - which is deliberate, because those two are the only shape
# events on this brim that every verifier has ever reported seeing.
#
# ALTERNATING SIGN IS THE WHOLE MECHANISM, not a stylistic choice. A monotonic
# fold can only turn further away from a key sitting 43 degrees up, so every
# successive band is darker than the last: it can manufacture shadow bands and it
# can never manufacture a highlight band. 3/3 verifiers asked for "fold bands
# each with its own light and shadow side", "a highlight/shadow pair", "a seam of
# lighter cloth where a fold would catch light" - all three are asking for the
# cloth to come back UP somewhere. A negative lobe is that: the cloth lifts, its
# face turns into the key, and the pair completes.
#
# Placed as two pairs, one per judged view, because a fold nobody can see is
# geometry spent for nothing. The file's own note records that theta 0/180 are
# the silhouette bearings in `front` and ~321/141 in hero_34; 30/75 sits inside
# hero_34's facing quadrant and 215/262 inside `front`'s. The existing sag (348)
# and flip (140) are left untouched and the new lobes are kept clear of both, so
# the re-entrant hook and the total face-void - the two things scoring 80+ on
# contrast - are not disturbed.
#
# WHY THIS AND NOT A RIPPLE ON THE FOLD ARC. Attempt 6 first built the drape as a
# wave in the RADIAL direction - the turn rate oscillating between the knee and
# the lip, which is what "several overlapping folds" sounds like it means. Built
# and measured, it does almost nothing: the skirt's median peak-to-trough along a
# radial scanline went 0.015 -> 0.041 in `front` and 0.048 -> 0.056 in hero_34
# even at an extreme amplitude, because the hanging cloth is seen nearly edge-on
# and a radial undulation is foreshortened into the band's thin direction. The
# skirt measures 47 px thick radially in `front`, 33 in hero_34 and **4 px at
# icon_full_184** - so two radial folds are 2 px each at icon, which is below the
# plateau floor entirely. Azimuthally the same skirt runs 163 / 59 / 8 px, so the
# identical feature costs the same geometry and gets 3-7x the room. Measured
# after the switch: median peak-to-trough across the skirt roughly doubled,
# 0.076 -> 0.14 in `front`.
BRIM_FOLD_LOBES = (
    ( 52.0,  30.0, 20.0),      # hero_34: near fold, drops
    (-38.0,  75.0, 18.0),      # hero_34: lifts back into the key - the highlight
    ( 46.0, 215.0, 20.0),      # front: far fold, drops
    (-34.0, 262.0, 18.0),      # front: lifts - the lit seam over the beard
)
# There is NO ripple term on the fold any more. It ran at 15 degrees against two
# lobes of 68 and 155, and 3/3 verifiers reported it invisible at every size -
# carrying it cost geometry for nothing. Deleted rather than enlarged, because
# the two big events are what this shape is about and a third competing
# undulation is what would make it read as scalloped.
# Where the fold starts, as a FRACTION of the reach. Interpolated by how hard the
# fold is: a gentle bend curves from far in (no flat plate, so no sombrero), a
# hard one starts late and folds tight (so it reads as a crease in cloth rather
# than as a cone). One expression, and it is what stops a 130 degree turn eating
# the whole width and taking the span with it.
BRIM_KNEE_F = 0.30
BRIM_FOLD_F = 0.72
BRIM_FOLD_REF = 115.0     # |bend| at which the fold line has fully moved out

# Crown spine + radii. Chosen 2026-08-01 from three rendered options: the tip
# arcs backward and then CURLS BACK DOWN, so the hat reads as slouched and worn
# rather than as a costume cone. The straight-cone version was more legible
# head-on and more generic; the wide-floppy version merged its brim with the
# shoulders into one mass at icon size.
#
# The curl only reads off-axis. Any future camera work that only checks `front`
# will conclude the hat is a stubby cone and be wrong.
HAT_SPINE = [
    (0.000, 0.000, 1.788),
    (0.000, 0.022, 1.958),
    (0.000, 0.078, 2.105),
    (0.000, 0.165, 2.211),
    (0.000, 0.300, Z_HAT_TIP),
    (0.000, 0.438, 2.241),   # the tip, hanging back and down
]
HAT_RADII = [0.122, 0.100, 0.074, 0.049, 0.027, 0.008]

HATBAND_Z = 1.919         # sits just above where the brim springs
HATBAND_R = 0.104
HATBAND_MINOR = 0.016

# The whole hat is cocked over to his left. Straight on the head it looks issued
# rather than worn, and the lore is explicit that nothing about him is ever
# straightened. Everything hat-shaped goes through hat_xf() so the tilt cannot be
# applied to some parts and forgotten on others.
HAT_TILT  = radians(7.5)
HAT_PIVOT = Vector((0.0, 0.010, 1.760))
# Crown cross-section: slightly oval, with a crease down one side. A perfectly
# circular felt cone is the one shape that never occurs on a hat anyone has
# actually worn.
HAT_OVAL   = 0.10
HAT_CREASE = 0.13

# -- Staff ---------------------------------------------------------------------
# Point-down on the ground at his right. The spine passes through the grip point
# by construction - see the comment on GRIP_C.
# Planted well OUT from the body, not tucked against it.
#
# This is a clearance constraint, not a stylistic choice. The sleeve is a tube
# around the forearm and the hand is ON the staff, so the staff necessarily sits
# within a sleeve-radius of the arm - and a 150 mm bell simply swallows it, which
# is what produced the shaft visibly passing through the cloth. Either the sleeve
# shrinks to nothing or the staff moves out; it moved out, and the staff-arm's
# sleeve narrowed as well (see SLEEVE_FLARE_R). Standing clear of the figure also
# just reads better: a staff leaning against the ribs looks mislaid.
STAFF_SPINE = [
    (-0.525, -0.082, 0.008),
    (-0.518, -0.104, 0.320),
    (-0.512, -0.116, 0.680),
    (-0.508, -0.120, 1.090),   # the grip
    (-0.500, -0.116, 1.500),
    (-0.486, -0.102, 1.900),
    (-0.476, -0.088, 2.180),
    (-0.470, -0.080, 2.310),
]
STAFF_RADII = [0.038, 0.037, 0.035, 0.034, 0.032, 0.031, 0.029, 0.027]
STAFF_KNOT   = 0.15       # gnarl: radius wobble along the shaft
STAFF_KNOT_F = 9.0
# Three ridges winding up the shaft. This is what turns a dowel into a piece of
# grown wood: a smooth tapered tube reads as a broom handle no matter how dark
# the material is, because nothing on its surface tells you which way is up.
STAFF_RIDGE  = 0.34       # ridge depth as a fraction of radius
STAFF_LOBES  = 3          # must be an integer or the section stops closing
STAFF_TWIST  = 7.2        # radians of rotation over the shaft's length
STAFF_SEGS   = 30

# Leather cord wound round the shaft where the hand grips it.
#
# Pulled DOWN and shortened so the winding ends just under the fist instead of
# running up past it. It used to span z 0.84 -> 1.39, which put a tightly ribbed
# tube directly alongside the plated forearm, at the same height, at almost the
# same pitch and the same value. Two corrugated cylinders side by side do not read
# as two things; they read as noise, and neither the armour nor the rope survived
# it. Ending at z ~1.04 the cord still does its actual job - it says where the hand
# goes, and now it says it by stopping exactly where the hand starts - while the
# lames get a stretch of plain shaft to be seen against.
GRIP_T0, GRIP_T1 = 0.29, 0.45
GRIP_TURNS  = 24          # over the 0.37 m of shaft between GRIP_T0 and GRIP_T1.
                          # 19 turns is a 29 mm pitch around a 12.4 mm cord -
                          # 17 mm of bare wood between every turn, which is a
                          # rope ladder however thin the cord gets. A binding
                          # pulled tight has its turns almost touching, so the
                          # pitch has to land near the cord's own diameter.
GRIP_CORD_R = 0.0062      # fewer, fatter turns read as a rope ladder rather
                          # than as a tight binding

# The setting: tendrils of the same wood that split off the shaft and curl in
# around the stone, rather than a ring of identical metal claws.
TENDRILS = 5
TENDRIL_SPLIT = 0.90      # where along the shaft they leave it

# The hand grips the shaft at the 4th spine point, so the two cannot drift apart
# when the staff is re-posed.
GRIP_C = Vector(STAFF_SPINE[3])
GRIP_R = 0.041            # must track the shaft radius at the grip PLUS the
                          # wound cord, or the fingers close on empty air /
                          # bury themselves in the winding

# Taken from the top of the shaft rather than written out again, so moving the
# staff cannot leave the stone hanging where the staff used to be.
GEM_C         = Vector((STAFF_SPINE[-1][0], STAFF_SPINE[-1][1], 2.372))
GEM_R         = 0.092
# A CUT stone, lathed at 8 segments and flat shaded: pavilion, girdle, crown,
# table. The icosphere it replaces read as a shiny egg - facets are how a gem
# reads, and a real cut has a flat table catching one hard highlight, which an
# evenly-faceted ball never does.
#
# The proportions are deliberately NOT a jeweller's brilliant. A real brilliant
# is mostly pavilion, below the girdle, because it is designed to be viewed from
# above through the table while set in a ring. This one is seen from the side,
# from below, at the top of a staff - so the pavilion is short and buried in the
# seat and the crown carries almost the whole stone. Cut the other way round it
# renders as a small purple cap sitting on a lot of silver.
#
# THE CROWN WAS RECUT on 2026-08-02, and only the crown. Nothing at or below the
# girdle is free to move: Staff_Seat's inner wall is cut to follow these three
# pavilion points and hugs them to about a centimetre (at z -0.44 R the stone is
# 0.54 R and the cup is 0.55 R), so a few hundredths on a pavilion point pushes
# the stone out through the silver. The tendrils have the same problem - they
# close over the girdle at a fixed height, GEM_C.z + 0.030, and bite at 0.72 R,
# which only works while the stone is ~0.89 R wide there.
#
# What was wrong with the old crown was RESOLUTION, not shape. Four bands of
# 0.20 / 0.32 / 0.34 / 0.20 R spanned the crown, and the crown is nearly all you
# see: the seat hides everything below the girdle, so the VISIBLE stone is 77x46
# px at hero_34 and a band was about 4 px tall. Four bands of four pixels is not
# a facet you can see, it is a gradient - the exact failure the file's own note
# on flat chords warns about. Three bands of 0.34 / 0.52 / 0.26 R put the same
# silhouette on planes 9-13 px tall, which is a facet.
#
# The last two entries share a z, and that is the other half of the fix. The old
# profile ended at radius 0, i.e. a CONE APEX - so the promise three paragraphs
# up, "a real cut has a flat table catching one hard highlight", described
# something the mesh did not have. (0.30, 1.12) then (0.00, 1.12) is a genuine
# flat disc. These cameras all sit BELOW the gem, so the table is the most
# grazing plane on the stone and the facet gate hands it the top of the ramp: it
# is the brightest single plane on the model, which is what a table is for.
GEM_PROFILE = [
    (0.00, -0.78),        # culet, in units of GEM_R - buried in the seat
    (0.52, -0.46),        # pavilion  \  DO NOT MOVE - Staff_Seat's inner wall
    (0.86, -0.16),        # pavilion  /  is cut to follow these
    (1.00,  0.00),        # girdle - the widest line, and where the claws bite
    (0.88,  0.34),        # bezel
    (0.50,  0.86),        # star
    (0.30,  1.12),        # table edge
    (0.00,  1.12),        # TABLE - flat, because this z repeats the line above
]
GEM_FACETS    = 8

# -- The Gatestone -------------------------------------------------------------
# Why the staff is "never seen to move": it cannot be lifted. The point went
# through the lintel of the Weeping Gate and the stone came away with it, slid
# down the shaft and jammed on the ferrule. So there is a broken block of the
# gate lying at his foot with the shaft still through it.
#
# Everything below is measured from the ROBE, not chosen freely, because the
# staff is planted only 87 mm outboard of a hem that pools to radius 0.444. A
# block centred on the shaft would have its inner face inside the cloth. Three
# consequences follow, and none of them are stylistic:
#   * the bore sits at the block's INNER end, not in its middle, and the mass
#     runs outboard from there;
#   * the inner end is a thin LIP, lifted clear of the ground (GS_LIFT) so it
#     spans only the heights where the robe has already narrowed - the pooled
#     hem is the widest thing on the figure and the block must not sit beside
#     its widest 8 cm;
#   * the whole plan is swung GS_ROT off the radial line, which points the
#     dressed face at both the key light and the 3/4 camera and swings the
#     outboard mass toward frame-left, away from the robe's silhouette.
# _gatestone_report() prints the resulting clearance every build. If a change
# drops it under ~0.04 the block is touching the cloth.
GS_ROT      = radians(-20.0)
# Fracture planes, as (angle from the outward radial, distance from the bore
# axis at the block's underside, distance at its top). The block is the
# INTERSECTION of these half-spaces, which is how real rock breaks and is also
# the cheapest way to guarantee the thing this design can most easily fail at:
# no two of these are parallel and none of them are mirrored, so there is no
# angle from which it reads as a cube, a crate or a suitcase.
GS_PLANES = [
    (0.00, 0.318, 0.262),
    (0.63, 0.268, 0.224),
    (1.28, 0.192, 0.180),    # the one dressed, tooled face - see GS_DRESSED
    (2.05, 0.168, 0.148),
    (3.02, 0.098, 0.091),    # inner lip. The tight one: see the note above.
    (3.68, 0.101, 0.093),    # 0.086/0.090 left 37 mm of wall between the bore
    (4.46, 0.142, 0.126),    # and this face, and a 45 mm bevel biting it from
                             # both sides turned the lip into a curled flake in
                             # the front render. Widened until it reads solid.
                             # Costs 12 mm of hem clearance: 0.056 -> 0.044.
    (5.30, 0.226, 0.196),
    (5.78, 0.276, 0.243),
]
GS_DRESSED  = 2
GS_INNER_A  = 3.02        # which direction counts as "toward the figure"
GS_Z_FLOOR  = 0.016       # underside at the outboard end. Not 0: the displace
                          # warp swings +-GS_WARP/2 and the audit fails anything
                          # that dips below the floor.
GS_LIFT     = 0.105       # how far the inner lip rides up off the ground
# The TOP is three more fracture planes, and this is a correction.
#
# It used to be a single smooth function of phi - GS_TOP minus a cosine falloff
# toward the inner lip, plus two small cosine wobbles - and the top cap was a
# ring of quads at CONSTANT z per column. That is a C1-continuous ruled surface:
# it has no facets, no crest and no hard edge anywhere on it, so the nine planes
# in GS_PLANES only ever shaped the block's FLANKS. Three verifiers, judging the
# render, said the top read as "a single sweeping ramp", "a flat ground-parallel
# top plane", "an axe head or an anvil", and two of them counted three facets on
# a block advertised as having nine. They were describing the top exactly.
#
# Measured off the built mesh (evaluated modifier stack, normals clustered at 12
# degrees): the old top carried 0.083 m2 of up-facing area whose largest cluster
# was tilted 14.8 degrees from vertical and whose second largest was tilted 2.2
# degrees - i.e. 46% of the up-facing area lay within 15 degrees of dead level.
#
# So the top now joins the intersection, which is what the design claimed all
# along. Each entry is (height directly above the bore axis, DOWNHILL azimuth in
# degrees measured in the block's own frame from the outboard direction, slope).
# The block's top is the MINIMUM of the three, so where two of them cross there
# is a genuine crest, and the bore rim and the outer rim now ride the same
# planes at their own radii - which is what stops the cap being level in the
# radial direction.
#
# Chosen by search, not by hand, against six hard constraints: every plane at
# least 22 degrees off level (none can read as "the flat top"); at least 65 mm of
# stone left at the thinnest point; the top over the dressed face no lower than
# 0.218 so the inscription, which tops out at w = 0.198, is never truncated; the
# outboard end still the tall end so the wedge survives; nothing taller than the
# 0.307 the old top already reached; and all three planes actually visible from
# the 3/4 camera. Of 1.2 M candidates 615 were feasible; this one maximises the
# value STEP across the crests while keeping the brightest facet the smallest.
#
# Predicted from the plane normals against the key: 24.7 / 22.3 / 24.7 degrees of
# tilt, Lambert n.k of 0.63 / 0.81 / 0.46, and 46% / 18% / 36% of the top's
# camera-projected area. The brightest facet is now the SMALLEST one - which is
# the answer to "the up-facing planes are at the beard's value", because that
# complaint was about a large uniform plateau rather than about a peak value.
GS_TOP_PLANES = [
    (0.359, 310.0, 0.46),
    (0.317,  92.0, 0.41),
    (0.233, 164.0, 0.46),
]
# The bore. Tapered, and deliberately TIGHTER than the shaft at the bottom
# (STAFF_RADII[0] is 0.038 before the ridges, which run it out past 0.047) so
# the stone grips the wood instead of hovering round it - rule 1 is satisfied by
# real contact, not by proximity. At the mouth it opens out to leave a visible
# ring of dark bore interior round the shaft, which is what makes the join read
# as a drilled hole rather than as a shaft disappearing into a lump.
GS_BORE_LO  = 0.038
GS_BORE_HI  = 0.048
GS_BORE_SPAN = 0.276      # z over which the bore opens from LO to HI
# Sampling. Deliberately non-uniform: the carved face needs samples fine enough
# to represent a 26 mm groove (six across it), the fracture faces do not. A
# smooth density bump rather than two blocks of spacing, because a step change
# in column width shows up as a seam under smooth shading.
GS_SEGS     = 112
GS_LEVELS   = 36
GS_FINE_C   = 1.02        # centre of the dense band, in local phi
GS_FINE_W   = 0.55
GS_FINE_GAIN = 5.0
# Chipping on the fracture faces only. Integer harmonics or the section stops
# being 2*pi periodic and the loft tears open, exactly as it would on the robe.
# Biased inward (GS_FRAC_BIAS) so the noise can never eat the robe clearance.
GS_FRAC     = (0.008, 0.005, 0.003)
GS_FRAC_BIAS = 0.006
GS_BEVEL    = 0.045
GS_WARP     = 0.014       # displace strength, weathering the whole block
GS_WARP_SCALE = 0.20
# The inscription. Strokes in face-local (s = across the dressed face, w = world
# z) metres, grouped into four glyph fragments at IRREGULAR pitch - 52, 62 and
# 46 mm apart. Evenly spaced glyphs read as machine-set type or as a decorative
# band; this has to read as the middle of a sentence. The leftmost fragment runs
# off the outboard fracture edge and the rightmost off the inner one, so the
# line is cut mid-word at both ends and is a partial, non-repeating detail.
GS_GLYPH_D  = 0.011       # cut depth. Over-cut on purpose: subsurf takes about
                          # a third back off a groove this narrow.
GS_GLYPH_W  = 0.013       # half-width of a stroke
GS_GLYPHS = [
    ((-0.150, 0.100), (-0.150, 0.170)),
    ((-0.150, 0.152), (-0.126, 0.176)),
    ((-0.098, 0.092), (-0.098, 0.182)),
    ((-0.098, 0.182), (-0.074, 0.140)),
    ((-0.098, 0.130), (-0.078, 0.130)),
    ((-0.036, 0.100), (-0.036, 0.186)),
    ((-0.036, 0.186), (-0.012, 0.160)),
    ((-0.036, 0.100), (-0.014, 0.118)),
    (( 0.010, 0.112), ( 0.010, 0.176)),
    (( 0.010, 0.176), ( 0.038, 0.198)),
]

# -- Palette -------------------------------------------------------------------
# "Void and starlight", chosen 2026-08-01 from four rendered directions.
#
# Midnight blue sits LOW in value on purpose. A brighter blue leaves the silver
# trim nowhere to go and the whole figure flattens - the same failure that made
# char_knight2 read as a chrome blob. This palette pushes the base DARKER still
# and buys the richness back from angle-dependent colour rather than from
# brightness: the robe is nearly black facing the camera and only blooms violet
# and cyan where it turns away. That is what separates silk from painted cloth,
# and it costs nothing in the one currency the figure cannot spare, which is
# contrast against the gem.
#
# The robe's base colour is an ANGLE MIX, not a single value, and the mix is
# split into two ramps hanging off one Layer Weight: a HUE ramp and a VALUE
# ramp. Two ramps rather than one because the whole point of nacre is that it is
# a hue shift, not a brightening - and with a single colour ramp there is no way
# to travel through teal/lilac/rose without also travelling up in value, which
# is exactly the "just make it brighter" failure this palette exists to avoid.
# Split, the value ceiling is one number and the hue is free to move under it.
#
# C_ROBE is what faces you. It sits a shade under the 0.046 it was before the
# nacre work, but a long way back up from the 0.030 that first pass tried: at
# 0.030 the facing planes were at the WORLD BACKGROUND's own luminance, the
# figure bled into the backdrop at icon size, and "midnight blue" came back as
# sooty charcoal. Value is only half of why - the other half is chroma, so this
# is a deep SATURATED indigo (normalised it is 0.26/0.21/1.00, a blue-violet
# with almost no grey in it) rather than a dark neutral with a blue cast.
C_ROBE      = (0.011, 0.009, 0.042, 1.0)
# Hue stops for the band, normalised so the brightest channel is 1.0. They carry
# no value of their own - NACRE_V supplies all of it - so retinting one of these
# can never lift the robe. The first stop is not listed here: it is the
# material's own core colour, normalised, so that facing 0 reproduces C_ROBE
# exactly whatever the hue ramp is doing further up.
#
# The sweep is COLD from end to end and stays a NEIGHBOUR OF THE ROBE'S OWN
# INDIGO. Two failures got it here, and both were costume-identity failures
# rather than finish failures, which is why the stops are so tightly boxed in:
#
#   * indigo -> teal -> rose (first pass): the traverse crosses the neutral axis
#     over a dark blue base and lands on brown-grey.
#   * indigo -> cyan -> silver-blue (second pass): the cyan stop at 0.20/0.90/1.00
#     is a GREEN, and over a broad surface it rendered as seafoam. The character
#     stopped being a midnight-blue silk wizard and became a frost/sea mage - a
#     different costume, arrived at by a shader tweak.
#
# So: no green stop exists any more. The band runs indigo -> periwinkle -> pale
# silver-blue, all within one hue neighbourhood, and the only trace of the cool
# lean is that G sits a hair above R in the periwinkle stop. Chroma falls as the
# band opens, because the widest parts of the band cover the largest areas and
# that is exactly where a saturated hue reads as a coloured light rather than as
# a material.
NACRE_PERI      = (0.60, 0.68, 1.00, 1.0)  # periwinkle, the faintest cool lean
NACRE_SILVER    = (0.82, 0.87, 1.00, 1.0)  # pale silver-blue - carries the sweep
NACRE_SILVER_HI = (0.90, 0.93, 1.00, 1.0)  # same hue, a shade paler, at the rim
# NO WARM TERMINUS, and this was decided rather than defaulted. A rose flush at
# the true rim was in the last two passes and registered in neither - it fires
# on so few pixels that it cost a ramp stop for nothing. The choice was to make
# it genuinely visible or to cut it, and cutting it is the better trade: WARM is
# now the gem's only uncontested monopoly (value is shared with the trim, and
# blue is the whole costume), so spending it on cloth buys a hue nobody asked
# for and weakens the one contrast that has never been in dispute.
# Where the core stop SITS on the facing axis, and it is the number that decides
# whether this is a robe with a pearl contour or a pearl robe. A ColorRamp holds
# its first stop's value for everything below it, so this is the angle at which
# the band is allowed to start at all: with NACRE_BLEND's exponent, 0.32 is
# ~70 degrees off face-on, and everything inside that renders as exactly C_ROBE.
#
# It has been raised twice, and the reason is that a FLAT SURFACE and a ROUND
# one are not the same problem. At 0.20 (~45 degrees) the flat skirt panels were
# right - dark facing planes, nacre on the fold edges - while the hat brim, the
# crown and the shoulder spheres went a flat wash end to end, because on a
# strongly curved form most of the visible area is already past 45 degrees. The
# threshold has to be set by the roundest thing wearing the material, not the
# flattest.
NACRE_FLOOR = 0.32
# The two upper VALUE stops, as (facing position, linear value). The third stop
# is the core, pinned at NACRE_FLOOR and taken from the material's own colour.
# 0.51 is where the band is fully open - about 82 degrees off face-on - so the
# whole travel from plain cloth to full nacre happens in the last ~12 degrees
# before the silhouette, and the top stop is the true rim itself.
NACRE_V = ((0.51, 0.360), (1.00, 0.575))
# Hard ceiling on the nacre - roughly half the gem's rendered luminance. This is
# a CHOSEN ceiling, not a derivation: the gem's rendered brightness comes mostly
# from its coat specular under the key rather than from GEM_EMIT, so it cannot
# be computed from the material constants. What can be guaranteed is that the
# cloth never breaches it, via a Math/MINIMUM after the value ramp - so retuning
# NACRE_V can never accidentally let the robe out-shine the stone.
NACRE_PEAK = 0.575
# How wide the band is. NOTE this drives Layer Weight's FACING output, not its
# Fresnel output, and that is the single most important line in this block.
#
# Fresnel cannot produce this effect at all. Its shape is ~F0 + (1-F0)(1-cos)^5,
# which is flat to within a percent or two until about 65 degrees and then
# snaps: at blend 0.17 the mid stop was not reached until ~87 degrees and the
# top stop was never reached anywhere on the model. The result was a two-pixel
# hairline at the true silhouette that vanished entirely at 184x184 - all of the
# cost of darkening the robe and none of the pearl.
#
# Facing is 1 - |dot(N, V)|^p, which is close to linear in the projected width
# of a form, so the band wraps ONTO the curvature of a shoulder or a sleeve
# instead of clinging to its outline. Layer Weight maps blend to that exponent
# as p = 2*blend below 0.5 (and 0.5/(1-blend) above), so 0.18 gives p = 0.36.
#
# This is the KNEE, and NACRE_FLOOR is the threshold; both had to move and the
# knee is the one that was missed last time. A smaller p holds the facing output
# down through the whole mid-angle range and then turns hard near the
# silhouette, which is what "a sharp knee" means in this graph. At p = 0.60 the
# output had already climbed to 0.34 by 60 degrees, so raising the threshold
# alone just traded a wash for a slightly smaller wash; at p = 0.36 it is still
# only 0.22 there, and the whole 0.32 -> 0.51 travel that opens the band is
# packed into 70-82 degrees.
#
# The trade this makes explicit: the band is now a CONTOUR, not a gradient
# across each form. It occupies roughly the outer 6% of a form's projected width
# - which sounds like nothing and is not, because on a folded garment every
# crest has its own pair of silhouettes.
NACRE_BLEND = 0.18
# Fine warp/weft grain, multiplied over the VALUE at +/- 8%. Modulating value
# rather than colour is what makes the weave self-masking: it is worth ~0.002
# where the robe is dark (invisible) and ~0.036 inside the band (visible), so
# the cloth shows its threads exactly where the pearl is and nowhere else.
# GOTCHA: at scale 120 in object space a thread is about a pixel wide at
# 900x1300, so this WILL alias if the amplitude is raised. 8% is quiet enough
# that the aliasing reads as thread sparkle along the rim rather than as noise.
NACRE_WEAVE      = 120.0
NACRE_WEAVE_WARP = 2.0     # distortion: threads wander instead of ruling lines
NACRE_WEAVE_AMP  = 0.08
# The hem band, sash and hatband share every stop above and differ only in how
# much nacre they are allowed, so they stay readable as a deeper, quieter cloth
# instead of merging with the robe. Same saturated indigo, a clear stop down in
# value - the gap between 0.030 and the robe's 0.042 is what keeps the sash from
# disappearing into the garment it is tied around.
C_ROBE_D       = (0.008, 0.006, 0.030, 1.0)
NACRE_STR_DEEP = 0.75
# The same silk, at a third of the nacre, for the three ROUND masses: the hat
# brim, the hat crown and the shoulder deltoids. Threshold and knee are set by
# geometry, and these three have the wrong geometry for either to save them - a
# broad disc seen almost edge-on from a chest-height camera is past the knee
# across its entire top surface, and a sphere spends most of its projected area
# there too. They came back the brightest, most saturated things on the model,
# which is exactly backwards: the hat is the single biggest silhouette read on
# the character and it should be the DARKEST graphic mass, so the eye falls down
# the beard into the void instead of being pulled up and out to the brim.
#
# Damped rather than exempted: at zero these read as a different fabric from the
# robe, which is the same complaint in the other direction.
NACRE_STR_QUIET = 0.30
# Thin-film interference - a soap-bubble layer over the silk. This is the actual
# iridescence: the fresnel ramp alone shifts colour with angle, but thin film
# shifts the HIGHLIGHT's hue too, which is what stops the shimmer reading as a
# simple two-tone gradient. ~430 nm lands the break in the violet/cyan band we
# want; ~550 nm swings it green and fights the gem.
FILM_T   = 430.0
FILM_IOR = 1.92

# TRUE black, and darker than it has ever been. The open front, the face void
# and the sleeve interiors are one job: give the outer robe something to sit a
# clear notch above, so the garment reads as two layers and the void reads as
# absence rather than as more cloth. Giving this material any nacre at all -
# tried at a quarter strength, 2026-08-01 - closed that gap: the outer robe and
# the under-robe converged, the layered read flattened to a single mass, and the
# face void lost the lit boundary that is the best idea on the model. There is
# no add_nacre_band() call for this material, and that is deliberate.
C_ROBE_IN  = (0.0010, 0.0011, 0.0026, 1.0)
# Silver as a cold mirror. At this roughness it is mostly reflecting the dark
# world rather than generating its own value, which is precisely what makes it
# read as precious metal instead of grey paint - a rough silver has to be lit to
# look like anything, and this one does not.
#
# d37, "yield the silver to the gem" (2026-08-02). These were 0.925/0.945/0.985
# and 0.400/0.435/0.520 and they were the brightest thing on the whole model: the
# trim measured p99 0.97 and max 0.99 in front, i.e. NEAR WHITE, against a gem
# whose p99 is 0.221. d07 wrote down that "the silver trim now out-brightens the
# gem on value" and nothing acted on it for six designs; three separate panels
# then rejected robe designs for adding mid-value elements when the real thief was
# this trim. 1545 px of the front view sat above luma 0.85 and every one of them
# was hardware. After: 46.
#
# The cut is roughly x0.20 on both, and it is a BASE COLOUR cut and nothing else,
# because on a metallic=1.0 surface the base colour IS the mirror's tint and the
# thin specular streak down each swept tube is the only thing the trim actually
# contributes. Darkening the tint dims that streak and leaves it a streak. Every
# other lever was measured and rejected - see the note on M_SILVER below.
#
# Pre-cooled to B:R = 1.39 at constant Rec709 luma rather than kept near-neutral.
# The old near-white trim rendered B-R = +0.080, matching the robe's +0.065, but
# only because it was clipping; darkened at the original neutral hue it came back
# at +0.049, i.e. visibly WARMER than the cloth beside it, because what survives
# the cut is mostly the warm key. The cool hue puts it back at +0.077. This is the
# same "a near-neutral albedo renders warm here" trap the hat stone hit.
C_SILVER   = (0.159, 0.194, 0.221, 1.0)
C_SILVER_D = (0.096, 0.118, 0.134, 1.0)
# Two more tints off the same cool hue, both LIGHTER than the runs. A uniform cut
# across the whole stack was the right first move and the wrong last one: a long
# swept run keeps a legible specular streak at x0.20 because it has hundreds of
# pixels for the streak to live in, but a 300-pixel boss has nowhere to put one
# and comes back as a dark pebble with a single speck on it. Size, not just
# material, decides how far an element can be cut. See M_SILVER_B / M_SILVER_H.
C_SILVER_B = (0.318, 0.389, 0.442, 1.0)   # small isolated fittings
C_SILVER_H = (0.239, 0.292, 0.331, 1.0)   # the hem band
C_VOID     = (0.004, 0.004, 0.006, 1.0)
C_WOOD     = (0.038, 0.039, 0.068, 1.0)   # "blackwood", but not literally black:
                                          # at 0.036 the staff was a silhouette
                                          # with no form, and the ridges wound up
                                          # it were invisible. That reason is
                                          # about VALUE, so the luminance here is
                                          # held at the old 0.044 and only the hue
                                          # has moved.
                                          #
                                          # It had to move. The old value was a
                                          # NEUTRAL, and the Key is warm
                                          # (1.00, 0.84, 0.62), so the shaft came
                                          # back as ordinary brown timber - the
                                          # one warm mass in a cold figure, and
                                          # warm advances. The robe gets away with
                                          # facing the same light because its
                                          # fresnel ramp, blue sheen and coat all
                                          # push back cold; bare rough wood has
                                          # nothing to push back with, so the cold
                                          # has to be in the base colour.
# Light living in the grain. The branch is lore-wise a fallen limb of an
# immortal tree, so the timber stays black and the life shows as veins running
# through it. Emission via a pinched noise ramp, not a flat glow: a uniformly
# lit stick reads as plastic, and the whole point is that only filaments of it
# are alight.
C_WOOD_VEIN    = (0.34, 0.10, 0.78, 1.0)
WOOD_VEIN_EMIT = 0.85
# The five tendrils cradling the stone run hotter than the shaft. They are the
# closest wood to the gem, so the light is concentrating where it comes out.
C_WOOD_VEIN_L    = (0.42, 0.14, 0.92, 1.0)
WOOD_VEIN_EMIT_L = 1.85   # At 1.20 the cradle was as dark as the shaft and the
                          # whole crest read as a black tangle with a purple cap
                          # on it - which is the doc's THIRD identity feature
                          # rendering as a blob. The seat cannot carry it: silver
                          # here is a mirror in a dark room and enlarging it only
                          # added black (tried 2026-08-01, reverted). So the
                          # tendrils do the work, which is what the doc says they
                          # are for - the light concentrates in them because that
                          # is where it is coming out. Bounded above by AgX,
                          # which desaturates a bright emitter toward white and
                          # would turn the violet grey.
C_HAIR     = (0.268, 0.244, 0.183, 1.0)   # pale WARM bone. Still grey rather than
                                          # white - the beard is a broad,
                                          # fully-lit surface right under the key,
                                          # so it renders far lighter than its
                                          # base value suggests, and at 0.46 it
                                          # was the brightest thing in frame and
                                          # pulled the eye off the gem entirely.
                                          #
                                          # This was (0.252, 0.262, 0.298) until
                                          # 2026-08-02: blue-dominant, i.e. the
                                          # beard was LITERALLY SPECIFIED COOL.
                                          # With the whole silver stack dimmed
                                          # (d37) it had become the largest pale
                                          # mass on the figure and three verifiers
                                          # independently called it bluish-white /
                                          # grey / white-lavender. The doc gives it
                                          # the opposite job: it is the warm,
                                          # friendly proof there is a man under
                                          # the hat, and it was the second cold
                                          # thing in a wholly cold palette.
                                          #
                                          # Two things make this NOT a free hue
                                          # swap, and both are handled here:
                                          #
                                          #  * NEUTRAL IS NOT NEUTRAL. Measured on
                                          #    the beard itself over a four-rung
                                          #    albedo ladder, rendered B-R tracks
                                          #    albedo B-R at slope 0.84 with a
                                          #    +0.022 offset - so a grey albedo
                                          #    still renders cool-of-neutral and
                                          #    the albedo has to go PAST neutral
                                          #    to arrive warm. (The same +0.02
                                          #    offset the Gatestone found; it
                                          #    applies to a BRIGHT surface too,
                                          #    not only to a dark one.)
                                          #  * HUE AND VALUE ARE COUPLED. So this
                                          #    is not a re-hue of the old numbers,
                                          #    it is a re-hue at a key-weighted
                                          #    luma (R + 0.84G + 0.62B, Rec709)
                                          #    held 5.5% BELOW the old colour's.
                                          #    Rendered front: p50 0.415 -> 0.393,
                                          #    p95 0.599 -> 0.580, p99 0.613 ->
                                          #    0.596. The beard is the model's
                                          #    value ceiling, two accepted designs
                                          #    just bought that darkness, and a
                                          #    warmer beard that was also brighter
                                          #    would have spent it. IF YOU RETUNE
                                          #    THIS HUE, RESCALE IT TO THE SAME
                                          #    KEY-WEIGHTED LUMA.
                                          #
                                          # Why exactly here and not warmer: this
                                          # is the rung where the beard TIPS reach
                                          # G-B = 0.000 (front) / -0.001 (hero_34)
                                          # - the crossover where the gem's violet
                                          # spill stops tinting them and the hue
                                          # becomes clean R-dominant bone. Below
                                          # it the beard is still violet-tinged;
                                          # one rung above it (albedo B/R 0.61)
                                          # the render goes visibly tan and reads
                                          # as leather, not as an old man's hair.
                                          # Against M_PARCH measured in the same
                                          # frame - the model's existing warm
                                          # reference - this sits at 57% of the
                                          # parchment's chroma, which is the
                                          # "ancient pale, not ginger" budget.
C_SKIN     = (0.268, 0.192, 0.158, 1.0)   # weathered and old. Brighter than
                                          # this and the hands are the lightest
                                          # thing on the model after the beard,
                                          # and the eye goes to them instead of
                                          # to the gem.
C_GEM      = (0.098, 0.008, 0.360, 1.0)
# The BIG stone's own base colour, roughly half C_GEM. Separate constant because
# C_GEM still belongs to the hat stone, which is smooth, ungated and deliberately
# a whisper - halving its albedo would just make it dim.
#
# This is the lever the file already recorded as worthless, and that note was
# right about its own experiment and wrong as a general rule. A 10x base cut
# moved the display peak only ~0.16 sRGB because the stone was NEAR-WHITE
# everywhere and AgX's shoulder will not let you tint a highlight out of white.
# With the facet gate in (see gate_facet_emission) most of the stone is no longer
# near white - the inner facets sit at emission 0.0-0.9 - and down there the base
# colour is doing work again. Bracketed as a bundle with M_GEM's transmission and
# roughness below, and worth about +0.003 rendered chroma at hero_34, confirmed
# at two different ramp peaks (0.1456 -> 0.1488 at peak 7.5, 0.1378 -> 0.1411 at
# peak 8.0). Small, but it is the deepest part of the core that gets it.
C_GEM_CORE = (0.052, 0.004, 0.210, 1.0)
# GREEN IS ZERO, and that is the whole reason this can be turned up at all.
# Was (0.430, 0.055, 1.000). AgX desaturates a bright emitter toward white, and
# what "toward white" MEANS in channel terms is that the small channel gets lifted
# relative to the big one. Green is the small channel in a violet, so green is the
# entire desaturation budget. Measured at emission 2.0, front view, gem chroma
# (OKLab C): 0.055 green -> 0.1132, 0.000 green -> 0.1317. Sixteen percent more
# chroma for no change in value and no change in hue. Base-colour saturation
# (0.1345 -> 0.1347), coat (0.60 -> 0.35) and transmission (0.68 -> 0.85) were all
# bracketed in the same frame and are worth nothing here by comparison.
C_GEM_EM   = (0.330, 0.000, 1.000, 1.0)
# The GRAZING end of the facet ramp - see gate_facet_emission(), which is where
# this number is now spent. It is no longer a flat strength: 2.6 everywhere was
# what made the stone a smooth luminous dome, because emission is
# normal-independent and a constant is as constant on 64 planes as on a sphere.
# 8.5 lands only on the facets turned furthest from the camera.
GEM_EMIT_RIM = 8.5
# facing -> multiplier on GEM_EMIT_RIM. Starts at ZERO: the facet pointed
# straight at you emits nothing at all and is pure lit, transmissive stone, which
# is the "deep violet core you can see into". It is also, not by accident, where
# this material's chroma peaks - the old bracket below found chroma falling
# monotonically above emission ~0.5, so the darkest facet is the most saturated
# one and the brightest facet pays for it. That is the trade this ramp makes.
GEM_FACET_RAMP = [(0.00, 0.00), (0.24, 0.10), (0.58, 0.46), (1.00, 1.00)]
#
# HISTORY, kept because the curve it records is what the ramp above is shaped
# around. This was a single flat GEM_EMIT: 0.10 originally, then 2.6 on
# 2026-08-01. The note that came with 2.6 read:
#
                          # Was 0.10, and the old comment above it was right about
                          # the mechanism and wrong about the conclusion. AgX does
                          # desaturate bright emitters toward white - so the value
                          # to find is not "as bright as possible" but the one
                          # where CHROMA is still intact. That is measurable, and
                          # nobody had measured it. Emission vs rendered chroma,
                          # front view, at the old emission colour:
                          #     0.10 -> value 0.169  chroma 0.1381   (shipped)
                          #     0.5  -> value 0.367  chroma 0.1714   (chroma peak)
                          #     1.2  -> value 0.562  chroma 0.1394
                          #     3.0  -> value 0.743  chroma 0.0944
                          #     7.0  -> value 0.861  chroma 0.0597
                          #     35   -> value 0.987  chroma 0.0073   (white)
                          # So the stone was sitting a long way BELOW its own
                          # chroma peak: it was not being kept saturated by being
                          # dim, it was just dim. 2.0 with the green removed lands
                          # at value 0.621 / chroma 0.1345 - 3.7x the brightness at
                          # 97% of the saturation, and it finally puts the gem's
                          # top percentile (0.651) above the brightest beard pixel
                          # (0.645), which is what "the gem wins the frame" means.
                          # Do not go past ~2.5 chasing value: past there chroma
                          # falls off a cliff and the hue starts sliding violet ->
                          # magenta (300 deg at 2.0, 326 deg at 35). 2.6 is the
                          # last stop that still clears the brightest beard pixel
                          # in the FRONT view, which is the tightest of the three:
                          # gem max 0.704 against beard max 0.668. At 2.0 it is
                          # 0.654 against 0.668 and the beard still wins.
                          #
                          # The old note about emission flattening facet contrast
                          # still stands and is the other reason not to push it:
                          # emission lights every facet equally.
#
# That last line was the whole problem and nobody followed it: "emission lights
# every facet equally" is not a caveat on the number, it is a reason the number
# can never be a number. At 2.6 flat the entire stone spanned 0.011 in OKLab L
# and read as a smooth luminous dome. The fix is not a different constant, it is
# to stop it being a constant.

# ==============================================================================
#  SCENE RESET
# ==============================================================================
# read_homefile rather than read_factory_settings: identical result for our
# purposes and read_factory_settings is blocked inside the MCP sandbox.
bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)

SCENE = bpy.context.scene
COL_MAGE = bpy.data.collections.new("Mage")
COL_RIG  = bpy.data.collections.new("PreviewRig")
for c in (COL_MAGE, COL_RIG):
    SCENE.collection.children.link(c)

# ==============================================================================
#  MATERIALS
# ==============================================================================


def make_material(name, rgba, metallic=0.0, roughness=0.5,
                  emission=None, emission_strength=0.0,
                  transmission=0.0, coat=0.0, coat_roughness=None,
                  sheen=0.0, sheen_tint=None, sheen_roughness=None,
                  anisotropic=0.0, anisotropic_rotation=0.0,
                  specular=None, film_thickness=0.0, film_ior=1.5):
    """Principled BSDF wrapper. Socket names are the Blender 4.x/5.x spelling
    ("Emission Color", not "Emission"); guarded by `in` so a rename downstream
    degrades to a missing highlight rather than a hard crash mid-build."""
    mat = bpy.data.materials.new(name=name)
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    if anisotropic and "Anisotropic" in b.inputs:
        b.inputs["Anisotropic"].default_value = anisotropic
    if anisotropic_rotation and "Anisotropic Rotation" in b.inputs:
        b.inputs["Anisotropic Rotation"].default_value = anisotropic_rotation
    if transmission and "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = transmission
    if coat and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
    if coat_roughness is not None and "Coat Roughness" in b.inputs:
        b.inputs["Coat Roughness"].default_value = coat_roughness
    if sheen and "Sheen Weight" in b.inputs:
        b.inputs["Sheen Weight"].default_value = sheen
    # Sheen Tint is a COLOUR socket, not a scalar - it tints the fibre highlight
    # rather than scaling it. Tinting it blue is most of why the silk reads as
    # moonlit rather than merely shiny.
    if sheen_tint is not None and "Sheen Tint" in b.inputs:
        b.inputs["Sheen Tint"].default_value = sheen_tint
    if sheen_roughness is not None and "Sheen Roughness" in b.inputs:
        b.inputs["Sheen Roughness"].default_value = sheen_roughness
    if specular is not None and "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = specular
    # Thin film needs BOTH sockets set to do anything; a thickness with the
    # default IOR of 1.5 produces almost no visible interference.
    if film_thickness and "Thin Film Thickness" in b.inputs:
        b.inputs["Thin Film Thickness"].default_value = film_thickness
        if "Thin Film IOR" in b.inputs:
            b.inputs["Thin Film IOR"].default_value = film_ior
    if emission is not None:
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = emission
        if "Emission Strength" in b.inputs:
            b.inputs["Emission Strength"].default_value = emission_strength
    mat.diffuse_color = rgba          # keeps the solid viewport readable
    mat.metallic = metallic
    mat.roughness = roughness
    return mat


def add_nacre_band(mat, core, strength=1.0, blend=NACRE_BLEND):
    """Pearlescent by ANGLE, not by brightness: an angle-gated nacre band.

    The cloth stays dark and saturated facing the camera and only the silhouette
    edges and fold crests carry a bright pearl contour, so the figure
    self-outlines at 184x184. What goes down is the value of the part pointed at
    you, not the mean of the whole garment - a band wide enough to see costs
    mean value, and that trade is made deliberately (see NACRE_BLEND). The
    contrast the gem needs is bought back with HUE instead: everything here is
    cold, and the stone is the only warm thing in the frame.

    Layer Weight's FACING output is 0 face-on and 1 at the silhouette, and it is
    close to linear in a form's projected width - which is why it, and not
    Fresnel, drives this (see NACRE_BLEND for the full reason). Two ramps hang
    off that one output:

      HUE   - LINEAR, four stops, all inside one hue neighbourhood: the core
              colour's own indigo, a periwinkle handoff, then pale silver-blue
              held to the rim. This is the part that does the work. A fold crest
              turning away from you travels up the ramp, so the SAME cloth reads
              indigo on one flank of a crest and pale silver on the other. That
              is what real shot silk does and what no amount of specular will
              fake. Cold end to end on purpose: the gem is the only warm thing
              in the frame, and that is how it keeps its dominance now that
              value is not doing it on its own.
      VALUE - EASE, three stops: core, open band, rim peak. EASE and not LINEAR
              because the ease-in holds the near-face-on region flat and dark;
              a linear ramp starts lifting the instant a surface turns at all,
              and the whole garment greys out.

    The two are multiplied, so VALUE is the only thing that can brighten the robe
    - and it is capped. A Math/MINIMUM against NACRE_PEAK sits between the value
    ramp and the multiply, because "the gem is the brightest thing on the model"
    is a promise that has to survive somebody retuning the ramp later.

    A Wave texture then multiplies that value by 1 +/- NACRE_WEAVE_AMP. Since it
    modulates value rather than colour it is self-masking: worth ~0.002 where the
    robe is dark and ~0.036 inside the band, so the weave appears only where the
    pearl does.

    `strength` lerps the two upper value stops back toward the core, which is how
    the sash and hem band (0.75) keep the same material identity while staying a
    quieter cloth than the robe they trim. The under-robe deliberately does not
    call this at all - see C_ROBE_IN.

    NOTE this is a render-time graph and does NOT survive the FBX export - FBX
    carries a single flat colour per material. mat.diffuse_color is set below so
    Unity and the solid viewport get a representative single value; matching the
    shimmer in-engine is a shader job for whoever builds the prefab.
    """
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]

    # Hue stop 0 is the core colour NORMALISED and value stop 0 is its brightest
    # channel, so hue x value at facing 0 reproduces `core` exactly. Splitting
    # it this way is what lets the band be retinted without ever changing what
    # the robe looks like face-on, which is the one thing that must not move.
    core_v = max(core[0], core[1], core[2], 1e-6)
    core_h = (core[0] / core_v, core[1] / core_v, core[2] / core_v, 1.0)

    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.location = (-1020, 200)
    lw.inputs["Blend"].default_value = blend

    hue = nt.nodes.new("ShaderNodeValToRGB")
    hue.location = (-820, 340)
    hr = hue.color_ramp
    hr.interpolation = "LINEAR"
    # The hue ramp gets the SAME shoulder as the value ramp, and it matters just
    # as much. With this stop at 0.00 the cloth was already half way to cyan at
    # 40 degrees off face-on - the value ramp was correctly holding the front of
    # the garment at its core VALUE while the hue ramp quietly repainted it, and
    # the robe rendered teal with no indigo anywhere (2026-08-01). Pinned here,
    # every surface inside the shoulder is exactly C_ROBE, hue included, and all
    # the colour travel happens inside the band where the pearl actually is.
    hr.elements[0].position = NACRE_FLOOR
    hr.elements[0].color = core_h
    hr.elements[1].position = 1.00
    hr.elements[1].color = NACRE_SILVER_HI
    # Added after the two endpoints are placed - elements.new() re-sorts the
    # list, so grabbing elements[1] afterwards would not be the stop you think.
    # Silver-blue is reached by 0.66 and then held to the rim, so it carries
    # about four fifths of the sweep and the periwinkle leg is a short handoff
    # out of the indigo rather than a colour the cloth sits in.
    hr.elements.new(0.48).color = NACRE_PERI
    hr.elements.new(0.66).color = NACRE_SILVER
    nt.links.new(lw.outputs["Facing"], hue.inputs["Fac"])

    val = nt.nodes.new("ShaderNodeValToRGB")
    val.location = (-820, 60)
    vr = val.color_ramp
    vr.interpolation = "EASE"
    stops = [(p, core_v + strength * (v - core_v)) for p, v in NACRE_V]
    # NOT position 0. The ramp holds this value for everything below it, and that
    # flat shoulder is what keeps the front of the garment at its core colour
    # while the band still has somewhere to travel. See NACRE_FLOOR.
    vr.elements[0].position = NACRE_FLOOR
    vr.elements[0].color = (core_v, core_v, core_v, 1.0)
    vr.elements[1].position = stops[-1][0]
    vr.elements[1].color = (stops[-1][1],) * 3 + (1.0,)
    for p, v in stops[:-1]:
        vr.elements.new(p).color = (v,) * 3 + (1.0,)
    nt.links.new(lw.outputs["Facing"], val.inputs["Fac"])

    # The ceiling. MINIMUM rather than a Clamp node so the graph reads as "the
    # cloth may not exceed this" instead of as an arbitrary range.
    cap = nt.nodes.new("ShaderNodeMath")
    cap.location = (-600, 60)
    cap.operation = 'MINIMUM'
    cap.inputs[1].default_value = NACRE_PEAK
    nt.links.new(val.outputs["Color"], cap.inputs[0])

    # Warp/weft. Object space so the weave is locked to the cloth and does not
    # swim when the camera moves. The mapping squashes Z, so a distorted band
    # comes out several times longer than it is wide and the threads run ALONG
    # the folds rather than dotting across them.
    coord = nt.nodes.new("ShaderNodeTexCoord")
    coord.location = (-1420, -240)
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-1220, -240)
    mapping.inputs["Scale"].default_value = (1.0, 1.0, 0.22)
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.location = (-1020, -240)
    wave.wave_type = 'BANDS'
    # Bands along X, i.e. stripes that run up the figure with the folds. Guarded
    # because bands_direction is a fairly recent property and a missing one
    # should cost the grain its orientation, not crash the build.
    if hasattr(wave, "bands_direction"):
        wave.bands_direction = 'X'
    wave.inputs["Scale"].default_value = NACRE_WEAVE
    wave.inputs["Distortion"].default_value = NACRE_WEAVE_WARP
    if "Detail" in wave.inputs:
        wave.inputs["Detail"].default_value = 2.0
    nt.links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    # MULTIPLY_ADD: wave * 2*amp + (1 - amp), i.e. 1 +/- amp. The three sockets
    # are all literally named "Value" in the RNA - only the UI relabels them
    # Multiplier/Addend - so they have to be reached by index.
    grain = nt.nodes.new("ShaderNodeMath")
    grain.location = (-820, -240)
    grain.operation = 'MULTIPLY_ADD'
    grain.inputs[1].default_value = 2.0 * NACRE_WEAVE_AMP
    grain.inputs[2].default_value = 1.0 - NACRE_WEAVE_AMP
    nt.links.new(wave.outputs["Fac"], grain.inputs[0])

    lit = nt.nodes.new("ShaderNodeMath")
    lit.location = (-420, -80)
    lit.operation = 'MULTIPLY'
    nt.links.new(cap.outputs["Value"], lit.inputs[0])
    nt.links.new(grain.outputs["Value"], lit.inputs[1])

    # Colour x scalar. Vector Math/SCALE rather than a Mix node because the two
    # Mix spellings have swapped names and sockets across 3.x/4.x/5.x, while
    # SCALE has not; a Vector output feeding a Colour input is converted
    # componentwise, which is exactly the multiply wanted here.
    tint = nt.nodes.new("ShaderNodeVectorMath")
    tint.location = (-220, 120)
    tint.operation = 'SCALE'
    nt.links.new(hue.outputs["Color"], tint.inputs[0])
    nt.links.new(lit.outputs["Value"], tint.inputs["Scale"])
    nt.links.new(tint.outputs["Vector"], b.inputs["Base Color"])

    # A QUARTER of the way up the band, not the middle of it: most of the
    # garment's area sits at the core stop, so handing Unity the mid stop would
    # describe a robe far paler than the one that renders.
    rep = core_v + 0.25 * (stops[0][1] - core_v)
    mat.diffuse_color = tuple(c * rep for c in NACRE_SILVER[:3]) + (1.0,)
    return mat


def add_grain_glow(mat, colour, strength, scale=9.0, threshold=0.62,
                   stretch=0.16):
    """Faint light living in the grain of the wood.

    Noise into a ColorRamp with the two stops pinched together, so only the
    brightest filaments of the noise survive: the glow reads as veins running
    through the timber rather than as a uniformly lit stick. Widening that gap
    is the fastest way to ruin it - past about 0.3 the whole shaft lifts and the
    staff turns into a fluorescent tube.

    `stretch` squashes the noise's Z before it is sampled, so a feature comes out
    1/stretch times longer than it is wide. Grain runs ALONG a branch, and
    isotropic noise cannot express that however finely it is tuned - at scale
    7.5 with no stretch the shaft got soft 13 cm splotches, which is a stain, not
    a vein. Fine and long is what reads as filament; the ramp is unchanged.
    """
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    coord.location = (-1240, -200)
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-1040, -200)
    mapping.inputs["Scale"].default_value = (1.0, 1.0, stretch)
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.location = (-820, -200)
    nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    tex.inputs["Scale"].default_value = scale
    if "Detail" in tex.inputs:
        tex.inputs["Detail"].default_value = 6.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-600, -200)
    cr = ramp.color_ramp
    cr.elements[0].position = threshold
    cr.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    cr.elements[1].position = min(0.995, threshold + 0.16)
    cr.elements[1].color = colour
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    if "Emission Color" in b.inputs:
        nt.links.new(ramp.outputs["Color"], b.inputs["Emission Color"])
    if "Emission Strength" in b.inputs:
        b.inputs["Emission Strength"].default_value = strength
    return mat


def gate_facet_emission(mat, peak, stops, blend=0.5):
    """Drive Emission Strength from the facet's angle to the camera.

    This is the whole of "cut the gem", and it is a SHADING fix for what looks
    like a geometry problem. The stone was already an 8-segment flat-shaded lathe
    - 64 planes - and it still rendered as a smooth luminous dome, because
    emission is normal-independent: at a flat GEM_EMIT every facet emits the same
    radiance whichever way it points, and a constant is as constant on 64 planes
    as it is on a sphere. Measured on the shipped stone, hero_34, gem pixels only:
    the whole gem spanned 0.011 in OKLab L (mean 0.755, p95 0.780, p99 0.781).
    That one number IS the "flat near-white lavender area with no internal planes"
    complaint. Recutting the profile with the emission left flat moved it to
    0.758 / 0.780 / 0.781 - i.e. nothing at all, which is the proof that geometry
    cannot fix this on its own.

    Layer Weight's FACING output is the lever, for a reason particular to this
    mesh. The gem is FLAT SHADED, so the shading normal is constant across a
    facet; and it is 9 cm wide seen from 5 m, so the view vector is constant
    across it too. Facing is therefore constant PER FACET: the ramp output is
    piecewise constant, each facet renders as one flat plane at its own level,
    and every facet edge becomes a hard value step instead of a shading gradient.
    Shade-smoothing the gem would destroy this outright - `smooth=False` on the
    revolve in build_staff() is load-bearing now, not cosmetic.

    Which way round the ramp runs is the design. Dark face-on, bright at grazing:

      * these cameras sit just BELOW the gem, so the middle of the projected
        stone is the girdle - which means the darkest, most saturated violet
        lands exactly where "a deep core you can see into" has to be, and it
        lands there at emission ~0, where this material's chroma peaks;
      * the crown bands tilt further away as they climb, so each band steps up a
        level and the planes read as planes;
      * the flat table faces straight up and is therefore the most grazing plane
        of all - it takes the top of the ramp and becomes the stone's hard bright
        cap;
      * the silhouette blazes, and that is the bright facet EDGE.

    So the stone takes its saturation and its brightness from different parts of
    itself, which is the only way to have both under AgX. Measured against the
    shipped stone in the same frame, hero_34: L mean 0.755 -> 0.686, p95 0.780 ->
    0.837, p99 0.781 -> 0.847, chroma 0.1152 -> 0.1430. Brighter where it peaks,
    darker in the middle, 24% more saturated overall.

    `peak` is a real trade and not a free lever. Same frame, hero_34 chroma /
    p95: 7.5 -> 0.1488 / 0.821, 8.5 -> 0.1430 / 0.837, 10.0 -> 0.1351 / 0.855.
    8.5 is the last stop where the FRONT view still holds +13% chroma over the
    shipped stone; past it the flank facets start to white out and the gem is on
    its way back to being a lamp with no inside.

    NOTE, exactly as for add_nacre_band and add_grain_glow, this is a render-time
    graph and does NOT survive the FBX export - FBX carries one flat value per
    material. The recut PROFILE does export, so the exported stone keeps its
    planes and loses their shading; reproducing this in-engine is a shader job
    for whoever builds the prefab.
    """
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    if "Emission Strength" not in b.inputs:
        return mat

    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.location = (-980, -260)
    lw.inputs["Blend"].default_value = blend

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-780, -260)
    cr = ramp.color_ramp
    # LINEAR, not EASE: the ramp is being sampled at a handful of discrete facet
    # angles, so its shape between the stops is never seen and an ease would only
    # move the stops around. The stops themselves are the curve.
    cr.interpolation = "LINEAR"
    # A new ColorRamp arrives with two stops. Rebuild rather than edit, so the
    # stop list here is the whole truth about the ramp.
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = stops[0][0]
    cr.elements[0].color = (stops[0][1], stops[0][1], stops[0][1], 1.0)
    for pos, val in stops[1:]:
        cr.elements.new(pos).color = (val, val, val, 1.0)

    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = 'MULTIPLY'
    mul.location = (-540, -260)
    mul.inputs[1].default_value = peak

    nt.links.new(lw.outputs["Facing"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mul.inputs[0])
    nt.links.new(mul.outputs["Value"], b.inputs["Emission Strength"])
    return mat


# Sheen is what separates silk from painted plastic, and it is also the one
# input on this material that can erase everything else. Two failures are
# recorded here because they look identical and have different causes:
#
#   * sheen 0.80, roughness default (older) - a bright white veil, robe rendered
#     pale lavender.
#   * sheen 0.45, ROUGHNESS 0.55 (tried 2026-08-01) - same veil, in cyan. Sheen
#     roughness is the WIDTH of the fibre lobe: near 0.25 it stays a grazing rim
#     and reads as fibre, but by 0.55 it has spread across the whole surface and
#     become a second, tinted diffuse. The robe came back slate-teal with the
#     indigo base and the entire nacre ramp invisible underneath it - the base
#     colour was doing nothing at all. If the cloth ever looks washed out, check
#     this number before touching the ramp.
#
# The genuine fix for the wet patent-vinyl read that sheen 0.60 / coat 0.35 gave
# the skirt is the SPECULAR width, not the sheen width: base roughness 0.42 (was
# 0.30) turns the highlight into a long soft streak following the drape, the
# coat drops to 0.12 so the oil-on-water layer is a suggestion and not a
# varnish, and specular 0.45 stops the cloth behaving like a polished surface.
M_ROBE    = make_material("MageRobe",    C_ROBE,    0.0, 0.420, sheen=0.38,
                          sheen_tint=(0.72, 0.86, 1.00, 1.0),
                          sheen_roughness=0.26, coat=0.12,
                          coat_roughness=0.22, specular=0.45,
                          film_thickness=FILM_T, film_ior=FILM_IOR)
add_nacre_band(M_ROBE, C_ROBE)
# Identical silk, quieter nacre, for the round masses - see NACRE_STR_QUIET.
# A separate material and not a separate colour: everything except the band
# strength is shared with M_ROBE, so the hat cannot drift into looking like a
# different fabric from the robe under it.
M_ROBE_Q  = make_material("MageRobeQuiet", C_ROBE, 0.0, 0.420, sheen=0.38,
                          sheen_tint=(0.72, 0.86, 1.00, 1.0),
                          sheen_roughness=0.26, coat=0.12,
                          coat_roughness=0.22, specular=0.45,
                          film_thickness=FILM_T, film_ior=FILM_IOR)
add_nacre_band(M_ROBE_Q, C_ROBE, strength=NACRE_STR_QUIET)
# The BRIM, and nothing else. d24 made it far and away the largest surface on the
# model, and the first render of it came back with its lit flank at a rendered
# mean of 0.423 against the beard's 0.475 IN THE SAME FRAME - the brightest large
# mass in the picture, and the exact inversion of what the NACRE_STR_QUIET note
# above says the hat is for. None of that was albedo: C_ROBE is 0.011, so every
# one of those levels came off the specular stack, which a broad, steeply BENT
# surface fires all at once where a shallow disc never did.
#
# So this caps the LOBE and not the colour. Base colour is C_ROBE unchanged, byte
# for byte the same silk as the robe, which is what stops the hat drifting into
# looking like a different fabric. What is gone is coat (a second sharper
# specular layer that always glints on a curved surface), thin film, the nacre
# band, and most of the specular level. The sheen STAYS: sheen is a grazing-angle
# lobe, so it lights the rim of the warp and nothing else - form drawn on the
# edges, where a silhouette change wants it, instead of a bright plateau in the
# middle. It also reads as what the brief asks the cloth to be: heavy soaked
# felt, not silk.
#
# The numbers below are set by the PEAK, and measured through an EMISSIVE OBJECT
# MASK rather than through a difference against a control build. Both halves of
# that sentence were bought expensively.
#
# Attempt 1 reported this surface at a rendered mean of 0.117-0.175 and three
# verifiers still called it a broad glossy sweep - a mean over a large dark disc
# averages a highlight away, and the eye does not. But re-measuring the same
# difference mask by percentile gave p99 0.57 / max 0.95, and bracketing the
# material across roughness 0.64-0.95 and sheen 0.16-0.34 moved those two numbers
# by less than 0.01. That is because a difference mask is not the brim: it also
# contains every pixel whose SHADOW or occlusion changed, including lit silver
# piping down on the robe. Masked properly - brim emissive green, everything else
# untouched - the real figures are p99 0.24-0.28 and max 0.26-0.35.
#
# What survives from all that is the direction, not the magnitude: roughness 0.95
# with sheen roughness 0.75 is the flattest of the brackets on BOTH p99 and max in
# all three views, it puts the brim's brightest 1% at or below the gem's mean, and
# a wide diffuse falloff is what stops the surface reading as vinyl or a painted
# car panel (3/3 verifiers). Sheen stays non-zero because it is the only thing
# drawing form on a 0.011 albedo.
M_BRIM    = make_material("MageBrimFelt", C_ROBE, 0.0, 0.950, sheen=0.16,
                          sheen_tint=(0.72, 0.86, 1.00, 1.0),
                          sheen_roughness=0.75, specular=0.02)
# The brim's DARK side: the hanging outer skirt and the whole underside, one
# surface (see BRIM_DARK_FROM). It is not M_ROBE_IN, and the reason is a bug in
# M_ROBE_IN rather than a difference of taste.
#
# M_ROBE_IN is built as `make_material(..., C_ROBE_IN, 0.0, 0.880, sheen=0.08)`
# with NO `specular=` argument, so its Specular IOR Level keeps make_material's
# Blender default of 0.5 - a full dielectric lobe. Its albedo is 0.0010, so
# essentially one hundred per cent of what it renders is specular reflection of
# the rim lights, and measured in the control (run-308) the strip of it that IS
# visible - the flipped wing, the only underside any camera reaches - came back
# at p50 0.150 against the brim topside's 0.248. Eleven times less albedo, and
# only 1.65x darker. That material is not near-black; it is a black mirror, and
# it is asset-fact 6 exactly: capping the colour has no authority over the lobe.
#
# So this one caps the lobe. specular 0.0, sheen 0.0, roughness 1.0, albedo
# C_ROBE_IN - nothing left that can return a highlight, which is the whole
# specification of "matte". M_ROBE_IN is left alone: it also lines the sleeves,
# the under-robe and the collar, and repairing it there is a robe change, not a
# hat change.
#
# d24 attempt 5. The skirt built above was near-black by ALBEDO as well as by
# lobe, and that turned out to be one step too far: at C_ROBE_IN it rendered a
# spread (p95-p05) of 0.044 / 0.005 / 0.123 across hero_34 / front /
# icon_full_184. **In front - the view where the skirt is largest at 20,193 px -
# five thousandths of tonal range over the whole surface.** Beside it in the same
# frame the hem spans 0.304, the crown 0.245 and the lit shelf 0.187. 2/3
# verifiers called it a flat cut-out panel that "sells dark but loses cloth", and
# they were reading the number.
#
# The fix is NOT more geometry. Bracketed over four albedos with the mesh
# untouched (run-332), the skirt's spread goes 0.005 -> 0.029 -> 0.076 -> 0.139
# in front. **A fifteen-fold increase in internal tonal range without moving one
# vertex** - because the fold arc already rotates the surface normal 23 degrees
# at the front and 55 across the sag lobe, and Lambert was resolving all of it
# into AgX's toe where every value crushes to the same black. The tonal life was
# always in the geometry; the albedo was too low to develop it.
#
# 11x, and the ceiling is set by the hem rather than by taste. The rolled hem
# reads only because it is brighter than the surface inboard of it (the finding
# from attempt 4, now an asset fact), so lifting the skirt spends that contrast:
# hem p50 minus skirt p50 goes +0.092 -> +0.076 -> +0.031 at 11x and INVERTS to
# -0.039 at 24x, where the roll dies and takes the one thing 3/3 verifiers
# praised with it. 11x is the last rung that keeps the sign on every view while
# giving the surface most of its available range. The hem's lit crest is still
# +0.24 clear of the skirt's p95 there, which is what actually draws the line.
#
# It also puts the skirt in a value band of its own at 184, which is the other
# half of the same instruction. The shoulder/collar band beneath it runs p05
# 0.058 (the open-collar void and the satchel shadow, the two things verifiers
# named) to p50 0.181 (lit cloth). At C_ROBE_IN the skirt sat at 0.009 - below
# the void, so the eye groups them; at 24x it sits at 0.137, up against the lit
# cloth. 11x lands at 0.078, between the two and touching neither.
#
# Scaled from C_ROBE_IN rather than written out, so the HUE is provably the
# lining's to the last digit. Hue and value are not independent in this rig -
# retinting without rescaling is how a surface silently drifts warm - and this
# constant only ever wants to move in value.
#
# 11x -> 5x (attempt 6). 11x was chosen when the skirt was a smooth bend and the
# ONLY thing that could vary its tone was the albedo, so it was pushed to the
# last rung the hem relationship tolerated. That surface then scored 145 against
# attempt 4's 198: the panel got the tonal range and still called it "the same
# solid panel quality, just repositioned", because range delivered as one smooth
# ramp is not what cloth looks like. With BRIM_FOLD_LOBES the tone now comes from
# fold flanks turning into and away from the key, which is a GEOMETRIC source and
# needs far less albedo under it - so the lift can go back down toward the dark
# recess attempt 4 was rewarded for.
#
# 5x is the minimum that still clears the AgX tonal-range floor (~0.005 albedo,
# below which a surface has no range whatever its geometry does - the fact this
# design contributed). Bracketed with the lobes in place at 1 / 3 / 5 / 8: at 1x
# the far hanging mass collapses back to a featureless void and the folds only
# read where they catch light; at 8x the recess greys out and the brim starts
# flattening the way attempt 5 did. 5x also restores a healthy margin on the hem
# - hem p50 minus skirt p50 was +0.031 at 11x, one third of what attempt 4 had,
# and around +0.07 here.
BRIM_IN_LIFT = 5.0
C_BRIM_IN = tuple(c * BRIM_IN_LIFT for c in C_ROBE_IN[:3]) + (1.0,)
M_BRIM_IN = make_material("MageBrimUnder", C_BRIM_IN, 0.0, 1.000, specular=0.0)
M_ROBE_D  = make_material("MageRobeDeep", C_ROBE_D, 0.0, 0.480, sheen=0.32,
                          sheen_tint=(0.72, 0.86, 1.00, 1.0),
                          sheen_roughness=0.26, coat=0.10,
                          coat_roughness=0.22, specular=0.40,
                          film_thickness=380.0, film_ior=FILM_IOR)
add_nacre_band(M_ROBE_D, C_ROBE_D, strength=NACRE_STR_DEEP)
# The lining is rule 4's job - something for the gem to glow against - and it
# gets NO nacre at all. It has to stay a clear notch below the outer robe or the
# two converge, the layered-robe read collapses into one mass, and the face void
# stops functioning as a void. It also lines the sleeves and the under-brim, so
# whatever happens here happens to every dark recess on the model at once.
M_ROBE_IN = make_material("MageRobeLining", C_ROBE_IN, 0.0, 0.880, sheen=0.08)
# Roughness was 0.062 / 0.260 and went up a notch as part of d37 - but only a
# notch, and for one specific job: spreading the handful of near-white specular
# CORES, not damping the trim. Bracketed in the same frame (run-262), from a
# 0.20-albedo base:
#     rough 0.062 -> silver mean 0.181, px>0.85 = 134
#     rough 0.14  -> silver mean 0.188, px>0.85 = 104
#     rough 0.22  -> silver mean 0.201, px>0.85 =  59
# so roughness buys peak at the cost of mean, and 0.18 is where that trade stops
# being worth it. DO NOT reach further for it: taken alone to 0.50 the trim's mean
# goes 0.338 -> 0.472 and the pixels above 0.50 go 8005 -> 13460. On a mirror,
# roughness does not dim a highlight, it SMEARS it into a plateau, and a plateau is
# the "bright metal flattens to a blob" failure rule 3 exists to prevent.
#
# Two arguments below are dead and are kept only so nobody re-derives them:
#   * anisotropic does NOTHING here. Setting it to 0.0 gives a byte-identical
#     render. This EEVEE path ignores the socket.
#   * specular (Specular IOR Level) does NOTHING at metallic=1.0 - it drives the
#     dielectric lobe, and a full metal has none. 0.90 -> 0.10 is also identical.
# The only two live levers on a full metal here are its base colour and its
# roughness. Everything else has to be geometry or light.
M_SILVER  = make_material("MageSilver",  C_SILVER,  1.0, 0.180, anisotropic=0.55,
                          specular=0.90)
M_SILVER_D = make_material("MageSilverDark", C_SILVER_D, 1.0, 0.400,
                           anisotropic=0.35)
# Same silver, same hue, LIGHTER and ROUGHER, for the studs / plates / buckles.
# Split out of M_SILVER for the same reason M_ROBE_Q is split out of M_ROBE: one
# parameter has to differ for a class of parts and nothing else may drift.
#
# The roughness is the interesting half and it runs OPPOSITE to the rule that
# governs M_SILVER. On a long run, roughness smears a highlight into a plateau and
# is an anti-lever. On a small isolated boss the highlight is a single speck, and
# smearing it is exactly what is wanted - it becomes a soft sheen over the whole
# little body, which is what makes a 300-pixel object read as worked metal instead
# of as a dark bead with a glint on it. Roughness is an anti-lever on runs and a
# pro-lever on fittings, and the deciding variable is the element's pixel COUNT.
M_SILVER_B = make_material("MageSilverBoss", C_SILVER_B, 1.0, 0.400,
                           anisotropic=0.55, specular=0.90)
# The hem band, which had its own distinct fault: it is swept along a SCALLOPED
# path, so as the hem waves in and out the tube's surface turns toward and away
# from the key and the specular streak switches on and off. At attempt 1's values
# that read as a patchy skirt edge - measured, 97 of 282 image columns had the band
# sitting at or below cloth value in front, and 93 of 251 in hero_34.
#
# Neither lever fixes that alone, which is why this is a separate material and not
# a tweak. Albedo alone (x0.30, roughness left at 0.18) lifts the dead segments but
# leaves the on/off pattern: per-column peak CoV 0.616 vs 0.682. Roughness alone
# (0.45 at the runs' albedo) evens it beautifully, CoV 0.454, but flattens the line
# so far that the hem loses its edge at 184 px - icon p99 0.440 -> 0.314, which
# trades a patchy hem for an absent one. Together at 0.30 / 0.32: CoV 0.469, dead
# columns 97 -> 50 in front and 93 -> 20 in hero_34, and the icon line gets
# BRIGHTER (p99 0.440 -> 0.476) rather than dimmer.
M_SILVER_H = make_material("MageSilverHem", C_SILVER_H, 1.0, 0.320,
                           anisotropic=0.55, specular=0.90)
# The wrought arm. Two materials, and the important number in both is METALLIC.
#
# The first version of this was C_PROS at 0.30 with metallic 1.0 and roughness 0.43
# and it rendered as dark rubber. The base colour was not the problem: a fully
# metallic surface has NO diffuse term, so in a rig with five small area lights and
# a 0.03 world it only shows where a highlight happens to land, and everywhere else
# it is whatever the dark world reflects - which is nothing. The rig comment up in
# build_rig() already says this about the knight; the same trap caught this.
#
# So both of these are deliberately part dielectric. METALLIC 0.55 IS THE LOAD-
# BEARING NUMBER AND IT HAS NOT MOVED: about 45% of the response is Lambertian, so
# the arm holds a value across its whole surface instead of only on the streaks,
# and the remaining 55% still gives real silver specular on top. That is what makes
# it read as hammered, unpolished silver rather than dark rubber, and it is the
# thing not to undo.
#
# What DID move in d37 is the albedo, from 0.560/0.578/0.620. The old comment here
# said the arm sits "at roughly beard value", and it did - measured 0.465 mean
# against the beard's 0.395, i.e. it had quietly overtaken the beard and was the
# second-brightest mass on the figure after nothing at all. The ordering the design
# wants is gem, then beard, then metal, so the arm comes down to ~0.32 mean: still
# unmistakably the lightest metal on the model and still a clear step above the
# robe trim, but no longer competing with the face.
#
# Coat is gone (was 0.14). A coat is a second, sharper specular layer stacked on
# top of one that is already there, and on a stack of curved lames there is no
# setting of it that does not put a glint on every crest. Roughness 0.300 -> 0.400
# for the same reason: it is a broad plate, so its highlight is a plateau, and the
# plateau is what read as near-white.
#
# Hue is half-cooled rather than neutral. Neutral is not neutral under this key:
# darkened at the old hue the arm came back at B-R = +0.047 against a robe at
# +0.065 and read warm. Half-way to the trim's cool gives +0.068, robe parity. The
# arm's job is still to be light rather than to be a colour - colour is the gem's.
#
# Second pass. The first cut took the arm down 26% while the trim around it went
# down 45-60%, deliberately, to protect the paragraph above - and the result was
# that the arm became the loudest thing left on the model: the brightest, largest
# pale mass on the body, pulling focus below the waist. Two things follow.
#
# It comes down again, to ~0.25 mean against the beard's 0.394 and the trim's
# 0.13-0.19, so it sits cleanly between them instead of on top of everything.
#
# And the roughness comes DOWN with it - 0.400 -> 0.240 - which looks like the
# wrong direction and is not. Cut on albedo alone the arm went matte: it held a
# pale value while every silver run around it stayed specular, so it stopped
# reading as the same metal family and started reading as bone. Base colour and
# roughness are the only two live levers on this rig, and here they are pulled in
# OPPOSITE directions on purpose - albedo down for less mass, roughness down for
# more mirror. Measured, the pair moves the mean 0.344 -> 0.254 while leaving p99
# at 0.79: less pale area, same specular character. Darker AND shinier is a real
# combination and it is what "wrought" needs here.
C_PROS     = (0.160, 0.196, 0.223, 1.0)
M_PROS     = make_material("MageProsthetic", C_PROS, 0.55, 0.240,
                           anisotropic=0.24)
# The drawn edge, the collar, and every band that has to survive downscaling. One
# clear step brighter than the plate faces so the plate boundaries read as OUTLINE
# rather than as more of the same metal.
#
# d37: was 0.815/0.838/0.880 with coat 0.20, and the "one clear step" was not
# happening - lip and plate rendered at 0.471 and 0.465 mean, indistinguishable,
# because both were riding their own specular rather than their albedo. Bringing
# both down on albedo and taking the coat off restores a real step (0.37 vs 0.34)
# while removing 0.10 of peak from each. Same half-cool as C_PROS so the arm reads
# as one material.
# Down and sharper alongside C_PROS, same reasoning, and the step it holds over the
# plate faces survives the second cut: 0.273 vs 0.254 mean.
C_PROS_HI  = (0.260, 0.317, 0.361, 1.0)
M_PROS_HI  = make_material("MageProstheticEdge", C_PROS_HI, 0.62, 0.170,
                           anisotropic=0.30)
M_VOID    = make_material("MageVoid",    C_VOID,    0.0, 1.000)
M_WOOD    = make_material("MageStaffWood", C_WOOD,  0.0, 0.700, specular=0.50)
add_grain_glow(M_WOOD, C_WOOD_VEIN, WOOD_VEIN_EMIT, scale=40.0)
M_WOOD_L  = make_material("MageStaffWoodPale", (0.058, 0.058, 0.098, 1.0),
                          0.0, 0.620)   # same cooling as C_WOOD, same luminance
add_grain_glow(M_WOOD_L, C_WOOD_VEIN_L, WOOD_VEIN_EMIT_L, scale=54.0)
M_LEATHER = make_material("MageLeather", (0.048, 0.034, 0.026, 1.0), 0.0, 0.820)
# Cold weathered limestone. NOT a mid value, and not a neutral one - it is the
# darkest large surface on the model after the robe itself, and it is tinted
# blue in the ALBEDO rather than in the render. Both of those are corrections,
# and both were argued for from measurements rather than from taste.
#
# "Fully matte" has to mean BOTH numbers. Roughness alone does not bound a
# dielectric specular lobe, and a rounded rock face aimed at the key light will
# throw a highlight no albedo ceiling can touch - which is precisely how a
# surface darker than the robe ends up reading as the brightest thing in frame.
# Specular IOR Level goes to 0.02 for that reason, not for realism.
#
# WHY SO DARK. The first build of this block reasoned "the model has no mid
# value, so give it one" and landed at 0.205 albedo. Three independent verifiers
# then said, unprompted and unanimously, that the block was the brightest object
# in the frame and that the eye reached it before the gem - which inverts the one
# thing the whole palette exists to serve. The render agrees: masked to stone
# pixels only, in hero_34, that build measured p50 0.340 / mean 0.352 against the
# BEARD's p50 0.323 / mean 0.298. It was not merely competing with the beard, it
# was beating it, over four times the area.
#
# So the value comes from a bracket, not from a target. Five builds, one run,
# identical crop and lighting, measured through a stone-only mask:
#
#     albedo lum   0.116   0.098   0.087   0.073   0.059
#     stone p50    0.230   0.203   0.187   0.163   0.138
#     stone p90    0.319   0.287   0.266   0.238   0.204   <- lit top facets
#
# with the beard at p50 0.323 and the robe's lit side at 0.079 in the same frame.
# Converted to L* (perceptual value, ~10 units per Munsell step) the brief's
# "clearly below the beard, only a step or two above the robe" is a window: the
# robe is L* 6, the beard L* 35. This value is L* 17 - one full step above the
# robe and nearly two below the beard - and its brightest broad facet, 0.238,
# still sits under the beard's MEDIAN. The block now reads as heavy mass sitting
# in shadow with only its top catching the key, which is what it is.
#
# WHY BLUE IN THE ALBEDO. The old value was near-neutral (0.205/0.211/0.227) and
# rendered WARM: bone, sandstone, a prop from a different model in a wholly cold
# figure. That is the warm key (1.00, 0.84, 0.62) doing exactly what the note on
# C_WOOD describes - a neutral lit by a warm light is a warm object. Measured, the
# old block rendered B-R = +0.024 while the robe beside it renders B-R = +0.075.
# Pre-cooling the albedo to a 1.67:1 B:R ratio brings the RENDERED block to
# B-R = +0.072, i.e. the same hue offset as the robe, so the stone finally belongs
# to the palette. It still reads desaturated, because the floor and the robe
# around it are far bluer again - "cold, desaturated blue-grey" is a relative
# statement and this is the relation that produces it.
#
# This is the one number to turn, in either direction. Note that turning it here
# is the ONLY way to bracket it: C_STONE is consumed on the next line, ~1900
# lines above the variant hook, so a preview `vars` override of C_STONE does
# nothing at all. Bracket it with a `patch` that sets M_STONE's Base Color.
C_STONE   = (0.060, 0.074, 0.100, 1.0)
M_STONE   = make_material("MageGatestone", C_STONE, 0.0, 0.960, specular=0.02)
# The bore's interior (rule 4). Its own material rather than the same stone in
# shadow: a hole that is merely unlit still catches the fill and the two rims,
# and then it is a dimple. This is what makes it a HOLE.
M_STONE_IN = make_material("MageGatestoneBore", (0.026, 0.028, 0.036, 1.0),
                           0.0, 1.000, specular=0.0)
# Parchment is the one warm, light thing on the model besides the hands. Kept
# well below the beard's value so it reads as a detail, not a second focal point.
M_PARCH   = make_material("MageParchment", (0.205, 0.178, 0.138, 1.0), 0.0, 0.880)
# The sheen tint is warmed with C_HAIR, because it is the beard's colour too: at
# (0.78, 0.80, 1.00) it was a second, independent blue specification sitting on
# top of a blue albedo. It is RESCALED, not just re-hued - the warm ratio is
# multiplied down so the tint's own Rec709 luma stays at the old 0.810, since
# swapping a cool tint for a warm one otherwise brightens the lobe (the same
# mint->bone coupling that moved a band 8% lighter for free).
#
# Measured on its own, though, this socket is nearly powerless: warming the tint
# with the albedo left alone moved the beard's rendered B-R by only -0.005 of the
# -0.109 the change needed, i.e. ~5%. Do NOT reach for sheen_tint to recolour a
# surface - the albedo is where essentially all of it lives.
M_HAIR    = make_material("MageHair",    C_HAIR,    0.0, 0.640, sheen=0.40,
                          sheen_tint=(0.850, 0.808, 0.714, 1.0))
M_SKIN    = make_material("MageSkin",    C_SKIN,    0.0, 0.700)
# The free hand is GLOVED, and that is a direct consequence of plating the other
# one. There used to be two pale flesh blobs at the same height on opposite sides
# of the figure, splitting the warm-accent budget between them and with the beard;
# with the staff hand gone to silver the survivor was the only flesh left on the
# model and it pulled far harder than it had any business doing - a featureless
# pale paddle coming out of a black sleeve. Gloved in the robe's own deep silk it
# still reads as a hand (the sheen catches the rim lights and the digits keep their
# shape) but it stops competing, and the beard is left owning the pale-warm role
# outright. Kept a stop above C_ROBE so the hand does not dissolve into the sleeve.
M_GLOVE   = make_material("MageGlove", (0.042, 0.046, 0.082, 1.0), 0.0, 0.520,
                          sheen=0.34, sheen_tint=(0.62, 0.66, 1.00, 1.0),
                          coat=0.18)

# The gem is the only light source on the model and the hero's whole colour
# identity. Transmission + a low-weight coat give it depth without the white
# specular veil that turned the knight's rubies into pink plastic.
M_GEM     = make_material("MageGem", C_GEM_CORE, 0.0, 0.020,
                          emission=C_GEM_EM, emission_strength=GEM_EMIT_RIM,
                          transmission=0.85, coat=0.60)
# The emission strength set above is immediately overwritten by a link. It is
# still passed, because it is what the socket falls back to if the graph is ever
# unplugged, and a gem that quietly drops to 0 would look like a broken build.
gate_facet_emission(M_GEM, GEM_EMIT_RIM, GEM_FACET_RAMP)
# The FBX carries one flat colour per material and takes it from here, so the
# exported stone keeps the value it had before the base colour was halved. The
# darkening is a render-time move that only pays off next to the facet gate, and
# the gate does not export - shipping C_GEM_CORE to Unity would just be a dimmer
# gem with none of the compensation.
M_GEM.diffuse_color = C_GEM
# The hat stone repeats the motif at a whisper. Deliberately much weaker: two
# equally bright violets and the eye has nowhere to land.
M_GEM_S   = make_material("MageGemSmall", C_GEM, 0.0, 0.120,
                          emission=C_GEM_EM, emission_strength=0.25,
                          transmission=0.30, coat=0.25)
M_EYE     = make_material("MageEyeGlint", C_EYE, 0.0, 0.300,
                          emission=C_EYE, emission_strength=EYE_EMIT)

# ==============================================================================
#  MESH PLUMBING
# ==============================================================================

PARTS = []      # every exportable mesh, in build order
EMPTIES = []    # attach points for Unity
CURRENT_SIDE = ""


def set_side(tag):
    global CURRENT_SIDE
    CURRENT_SIDE = tag


def _finish(name, bm, mat, coll, smooth=True):
    """Turn a bmesh into a linked object. Normals are recalculated outward
    because the builders below wind rings in whichever order was convenient, and
    inverted normals only show up later as black facets."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    if mat is not None:
        ob.data.materials.append(mat)
    coll.objects.link(ob)
    ob["side"] = CURRENT_SIDE
    if coll is COL_MAGE:
        PARTS.append(ob)
    return ob


def bevel(ob, width=0.005, segments=2, angle=40.0, clamp=True):
    m = ob.modifiers.new("Bevel", 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = radians(angle)
    m.use_clamp_overlap = clamp
    m.miter_outer = 'MITER_ARC'      # rounded corners; sharp miters read as cubes
    return m


def subsurf(ob, levels=1):
    m = ob.modifiers.new("Subsurf", 'SUBSURF')
    m.levels = levels
    m.render_levels = levels
    return m


def solidify(ob, thickness, offset=-1.0, rim=True, lining=None):
    """Give an open sheet thickness. `rim` is what closes the boundary and makes
    the result manifold - without it every solidified sheet fails the audit.

    `lining` is a second material for the INNER surface the modifier generates.
    This is how the robe and the sleeves get a near-black interior (rule 4)
    without a second object shadowing the first: solidify can offset the material
    index of the faces it creates, so one mesh carries both. The alternative -
    a separate lining object nested a few millimetres inside - doubles the part
    count and gives the levitation check something new to argue about.
    """
    m = ob.modifiers.new("Solidify", 'SOLIDIFY')
    m.thickness = thickness
    m.offset = offset
    m.use_rim = rim
    m.use_rim_only = False
    if lining is not None:
        ob.data.materials.append(lining)
        m.material_offset = 1
        m.material_offset_rim = 1
    return m


# ------------------------------------------------------------------------------
#  Generators. `revolve` for anything with an axis of symmetry, `loft` for
#  anything shaped by a stack of cross-sections, `sweep` for anything that
#  follows a path.
# ------------------------------------------------------------------------------

def revolve(name, profile, segments=28, mat=None, coll=None,
            origin=(0, 0, 0), rot=None, scale=(1, 1, 1), smooth=True,
            close_profile=False, radial_fn=None, shape_fn=None):
    """Lathe a 2D (radius, z) profile around local +Z.

    A profile entry with radius 0 becomes a pole (a fan of triangles) rather than
    a degenerate ring, which is what makes caps and dome tops come out clean.

    `close_profile` bridges the last ring back to the FIRST ring, reusing the
    same vertices. Shell bands (the sash, the hat brim, the sleeves) trace a
    closed 2D loop but the loft does not wrap on its own. Appending a duplicate
    first point instead looks closed and leaves two coincident open loops - still
    non-manifold, and the audit keeps failing while the render looks fine.

    `shape_fn(theta, radius, z) -> (x, y, z)` replaces the circular placement of
    each vertex. It exists so a band that wraps the torso can be lathed - which
    is the only generator here that closes a 2D loop correctly - while still
    landing on body_shape()'s elliptical section rather than on a circle. Purely
    a deformation of the ring, so winding and manifoldness are unaffected.
    """
    coll = coll or COL_MAGE
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if abs(r) < 1e-6:
            rings.append([bm.verts.new((0.0, 0.0, z))])
        else:
            ring = []
            for i in range(segments):
                a = 2.0 * pi * i / segments
                rr = r
                if radial_fn is not None:
                    # Fade the modulation out as the profile collapses, so poles
                    # and caps stay clean.
                    rr += radial_fn(a) * min(1.0, r / 0.030)
                if shape_fn is not None:
                    ring.append(bm.verts.new(tuple(shape_fn(a, rr, z))))
                else:
                    ring.append(bm.verts.new((rr * cos(a), rr * sin(a), z)))
            rings.append(ring)

    for a_ring, b_ring in zip(rings, rings[1:]):
        if len(a_ring) == 1 and len(b_ring) == 1:
            continue
        if len(a_ring) == 1:
            for i in range(segments):
                bm.faces.new((a_ring[0], b_ring[i], b_ring[(i + 1) % segments]))
        elif len(b_ring) == 1:
            for i in range(segments):
                bm.faces.new((a_ring[i], a_ring[(i + 1) % segments], b_ring[0]))
        else:
            for i in range(segments):
                j = (i + 1) % segments
                bm.faces.new((a_ring[i], a_ring[j], b_ring[j], b_ring[i]))

    if close_profile and len(rings) > 2 \
            and len(rings[0]) == segments and len(rings[-1]) == segments:
        a_ring, b_ring = rings[-1], rings[0]
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((a_ring[i], a_ring[j], b_ring[j], b_ring[i]))

    ob = _finish(name, bm, mat, coll, smooth)
    ob.location = origin
    if rot:
        ob.rotation_euler = rot
    ob.scale = scale
    return ob


def loft(name, rings, mat=None, coll=None, closed=True,
         cap_start=False, cap_end=False, smooth=True):
    """Skin a stack of vertex rings. Every ring must have the same length.

    `closed` wraps the ring back on itself (tubes, the robe body); False leaves
    it open (sheets: the outer robe, the mantle, the collar - anything that is
    solidified afterwards).
    """
    coll = coll or COL_MAGE
    bm = bmesh.new()
    vrings = [[bm.verts.new(tuple(p)) for p in ring] for ring in rings]
    n = len(vrings[0])
    span = n if closed else n - 1
    for a_ring, b_ring in zip(vrings, vrings[1:]):
        for i in range(span):
            j = (i + 1) % n
            bm.faces.new((a_ring[i], a_ring[j], b_ring[j], b_ring[i]))
    if cap_start:
        bm.faces.new(vrings[0][::-1])
    if cap_end:
        bm.faces.new(vrings[-1])
    return _finish(name, bm, mat, coll, smooth)


def sweep(name, points, radius, mat, segs=12, coll=None, taper=None):
    """Sweep a circle along a polyline using a rotation-minimizing frame.

    The obvious implementation - cross the tangent with a fixed world up - fails
    whenever the path passes near vertical: the fallback up-vector swaps between
    consecutive samples, the ring flips 90 degrees and the sweep detonates into a
    spike. The staff and the hat crown are both near-vertical, so this matters
    here more than anywhere. Parallel-transporting the reference vector removes
    the failure mode entirely.
    """
    pts = [Vector(p) for p in points]
    n = len(pts)
    tans = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        tans.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))

    seed = Vector((0, 0, 1))
    if abs(tans[0].dot(seed)) > 0.9:
        seed = Vector((0, 1, 0))
    ref = (seed - tans[0] * seed.dot(tans[0])).normalized()

    rings = []
    for i, p in enumerate(pts):
        if i > 0:
            ref = tans[i - 1].rotation_difference(tans[i]) @ ref
            ref = ref - tans[i] * ref.dot(tans[i])
            ref = ref.normalized() if ref.length > 1e-9 else ref
        up2 = tans[i].cross(ref).normalized()
        r = radius * (taper[i] if taper else 1.0)
        rings.append([p + ref * (r * cos(2 * pi * k / segs))
                        + up2 * (r * sin(2 * pi * k / segs))
                      for k in range(segs)])
    return loft(name, rings, mat=mat, closed=True, cap_start=True,
                cap_end=True, coll=coll)


def frames_along(points):
    """Rotation-minimizing frames along a polyline: [(p, tangent, u, v), ...].

    Factored out of sweep() so that anything following a path can share the one
    correct implementation. The failure it avoids is documented on sweep(): a
    fixed world-up reference flips on near-vertical paths and detonates the sweep
    into a spike, which is exactly what the staff and the hat crown are.
    """
    pts = [Vector(p) for p in points]
    n = len(pts)
    tans = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        tans.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))

    seed = Vector((0, 0, 1))
    if abs(tans[0].dot(seed)) > 0.9:
        seed = Vector((0, 1, 0))
    ref = (seed - tans[0] * seed.dot(tans[0])).normalized()

    out = []
    for i, p in enumerate(pts):
        if i > 0:
            ref = tans[i - 1].rotation_difference(tans[i]) @ ref
            ref = ref - tans[i] * ref.dot(tans[i])
            ref = ref.normalized() if ref.length > 1e-9 else ref
        out.append((p, tans[i], ref, tans[i].cross(ref).normalized()))
    return out


def sweep_fn(name, points, ring_fn, mat, segs=18, coll=None, closed_ends=True,
             smooth=True):
    """Sweep an ARBITRARY cross-section along a path.

    `ring_fn(t, angle)` returns the (u, v) offset in the frame plane, so the
    section can be elliptical, twisted, fluted or all three. This is what lets
    the sleeves be flattened ovals that follow the bend of the arm and the staff
    carry a helical ridge, neither of which a circular sweep can express.

    `closed_ends=False` leaves the tube open at both ends, ready for solidify()
    to give it a wall thickness and a real cloth edge - a sleeve capped with a
    flat disc reads as a bucket, which is precisely what the first one did.
    """
    frames = frames_along(points)
    rings = []
    for i, (p, _tan, u, v) in enumerate(frames):
        t = i / max(1, len(frames) - 1)
        ring = []
        for k in range(segs):
            a = 2.0 * pi * k / segs
            off = ring_fn(t, a)
            # A third component displaces along the TANGENT, which is what lets a
            # cuff or a hem edge wave along the path instead of being cut off by
            # a flat plane.
            ring.append(p + u * off[0] + v * off[1]
                        + (_tan * off[2] if len(off) > 2 else Vector((0, 0, 0))))
        rings.append(ring)
    return loft(name, rings, mat=mat, closed=True, cap_start=closed_ends,
                cap_end=closed_ends, coll=coll, smooth=smooth)


def catmull(pts, per_span=6):
    """Catmull-Rom through the given points. Used to turn the half-dozen control
    points of the staff and the hat crown into a smooth spine - a sweep over the
    raw control points reads as a series of straight segments with kinks."""
    P = [Vector(p) for p in pts]
    ext = [P[0] * 2.0 - P[1]] + P + [P[-1] * 2.0 - P[-2]]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for k in range(per_span):
            t = k / per_span
            t2, t3 = t * t, t * t * t
            out.append(((p1 * 2.0)
                        + (p2 - p0) * t
                        + (p0 * 2.0 - p1 * 5.0 + p2 * 4.0 - p3) * t2
                        + (p1 * 3.0 - p0 - p2 * 3.0 + p3) * t3) * 0.5)
    out.append(P[-1])
    return out


def swept_taper(name, spine, radii, mat, segs=16, per_span=6, coll=None,
                knot=0.0, knot_freq=1.0):
    """Sweep a tapering circle along a smoothed spine.

    The radii are smoothed through the SAME Catmull-Rom parameterisation as the
    spine (by riding along as an x coordinate) so radius and position stay in
    step; interpolating them separately puts the widest point of the staff in the
    wrong place.
    """
    pts = catmull(spine, per_span)
    rr = catmull([(r, 0.0, 0.0) for r in radii], per_span)
    rmax = max(radii)
    taper = []
    for i, v in enumerate(rr):
        t = i / max(1, len(rr) - 1)
        # Catmull-Rom can overshoot below zero at a sharp taper; clamp it.
        r = max(0.004, v.x)
        if knot:
            r *= 1.0 + knot * sin(knot_freq * t * 2.0 * pi) * 0.5 \
                     + knot * 0.4 * sin(knot_freq * 2.6 * t * 2.0 * pi) * 0.5
        taper.append(r / rmax)
    ob = sweep(name, pts, rmax, mat, segs=segs, coll=coll, taper=taper)
    # The spine samples and the ABSOLUTE radius at each one come back with the
    # object. Anything that has to sit on this surface later - the staff's silver
    # bands - then uses the same numbers the sweep used, instead of re-deriving
    # them from STAFF_RADII and drifting out of step the moment the knot function
    # or the taper changes.
    return ob, pts, [t * rmax for t in taper]


def add_sphere(name, loc, radius=0.1, scale=(1, 1, 1), rot=(0, 0, 0),
               mat=None, u=24, v=12, coll=None, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=radius)
    ob = _finish(name, bm, mat, coll or COL_MAGE, smooth)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return ob


def add_gem(name, loc, radius=0.02, subdiv=1, mat=None, rot=(0, 0, 0),
            scale=(1, 1, 1), coll=None):
    """Faceted icosphere, deliberately FLAT shaded. Gems are the one place the
    "no visible cubes / always shade smooth" rule inverts: facets are how a cut
    stone reads, and a smooth-shaded gem is just a shiny ball."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    ob = _finish(name, bm, mat, coll or COL_MAGE, smooth=False)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return ob


def add_torus(name, loc, major, minor, rot=(0, 0, 0), mat=None,
              mseg=28, nseg=10, coll=None, scale=(1, 1, 1)):
    bm = bmesh.new()
    for i in range(mseg):
        a = 2 * pi * i / mseg
        cx, cy = major * cos(a), major * sin(a)
        for j in range(nseg):
            b = 2 * pi * j / nseg
            bm.verts.new((cx + minor * cos(b) * cos(a),
                          cy + minor * cos(b) * sin(a),
                          minor * sin(b)))
    bm.verts.ensure_lookup_table()
    for i in range(mseg):
        for j in range(nseg):
            i2, j2 = (i + 1) % mseg, (j + 1) % nseg
            bm.faces.new((bm.verts[i * nseg + j],  bm.verts[i * nseg + j2],
                          bm.verts[i2 * nseg + j2], bm.verts[i2 * nseg + j]))
    ob = _finish(name, bm, mat, coll or COL_MAGE, True)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return ob


def capsule(name, p0, p1, r0, r1, mat=None, segs=16, cap0=True, cap1=True,
            shaft_rings=3, coll=None, cap_steps=4, scale=(1, 1, 1)):
    """Tapered capsule between two world points - the limb and finger primitive.

    Built as a single lathed surface (not a cylinder plus two spheres) so there
    is no interpenetration crease where the caps meet the shaft.
    """
    p0, p1 = Vector(p0), Vector(p1)
    axis = p1 - p0
    length = axis.length
    profile = []
    if cap0:
        for k in range(cap_steps, 0, -1):
            a = 0.5 * pi * k / cap_steps
            profile.append((r0 * cos(a), -r0 * sin(a)))
    for k in range(shaft_rings + 1):
        t = k / shaft_rings
        profile.append((r0 + (r1 - r0) * t, length * t))
    if cap1:
        for k in range(1, cap_steps + 1):
            a = 0.5 * pi * k / cap_steps
            profile.append((r1 * cos(a), length + r1 * sin(a)))

    ob = revolve(name, profile, segments=segs, mat=mat, coll=coll)
    ob.location = p0
    ob.rotation_euler = axis.to_track_quat('Z', 'Y').to_euler()
    ob.scale = scale
    return ob


def look_at_euler(from_p, to_p):
    """Euler aiming a camera or light at a point. Tracks -Z, not +Z: cameras look
    down their local -Z axis and area lights emit along it too."""
    return (Vector(to_p) - Vector(from_p)).to_track_quat('-Z', 'Y').to_euler()


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def table_lookup(table, x, smooth=True):
    """Interpolate a sorted [(key, v1, v2, ...), ...] table at x.

    smoothstep rather than linear on purpose: the robe silhouette is read as one
    continuous curve, and linear interpolation between table rows leaves a
    visible crease at every row boundary.
    """
    if x <= table[0][0]:
        return tuple(table[0][1:])
    if x >= table[-1][0]:
        return tuple(table[-1][1:])
    for a, b in zip(table, table[1:]):
        if a[0] <= x <= b[0]:
            u = (x - a[0]) / (b[0] - a[0])
            if smooth:
                u = smoothstep(u)
            return tuple(lerp(av, bv, u) for av, bv in zip(a[1:], b[1:]))
    return tuple(table[-1][1:])


# ==============================================================================
#  ROBE SURFACE
#
#  One parametric surface sampled by everything that lies on the body: the robe
#  itself, the under-robe, the mantle, the collar and every piece of silver trim.
#  Conforming them all to the same function is what stops the trim floating off
#  the cloth the moment the folds are retuned.
# ==============================================================================


def robe_fold(theta, z, amp):
    """Fold displacement at (theta, z).

    Periodic in 2*pi ONLY while FOLD_LOBES is an integer - the modulation term is
    itself 2*pi periodic, so the whole expression wraps cleanly and the loft seam
    closes. A fractional lobe count tears a seam up the back of the robe.
    """
    ph = FOLD_SKEW * sin(theta + FOLD_PHASE) + FOLD_TWIST * z
    s = abs(sin(FOLD_LOBES * theta + ph))
    main = s ** FOLD_POWER - FOLD_MEAN
    s2 = abs(sin(FOLD_LOBES2 * theta + FOLD_TWIST2 * z + 2.1))
    fine = (s2 ** FOLD_POWER - FOLD_MEAN) * FOLD_FINE
    return amp * (main + fine)


def robe_radius(theta, z, offset=0.0):
    r, amp = table_lookup(ROBE_TABLE, z)
    return r + robe_fold(theta, z, amp) + offset


def body_shape(theta, r, z):
    """Turn a radius into a point on the body's cross-section.

    Everything that lies on the body goes through here - the robe, the
    under-robe, the collar, every piece of trim. Conforming them all to one
    function is what stops the trim floating off the cloth when BODY_DEPTH is
    retuned, and it is the same discipline the knight's torso_point() enforces.
    """
    d = table_lookup(BODY_DEPTH, z)[0]
    c, s = cos(theta), sin(theta)
    return Vector((r * math.copysign(abs(c) ** BODY_POWER, c),
                   r * d * math.copysign(abs(s) ** BODY_POWER, s),
                   z))


def robe_point(theta, z, offset=0.0):
    return body_shape(theta, robe_radius(theta, z, offset), z)


def robe_open_half(z):
    return table_lookup(ROBE_OPEN, z)[0]


def robe_z_samples(step=0.042):
    """Dense z list through ROBE_TABLE. Extra rows cost nothing and are what
    stops the cloth chording across its own curvature between table rows."""
    zs = []
    for a, b in zip(ROBE_TABLE, ROBE_TABLE[1:]):
        n = max(1, int(math.ceil((b[0] - a[0]) / step)))
        for k in range(n):
            zs.append(lerp(a[0], b[0], k / n))
    zs.append(ROBE_TABLE[-1][0])
    return zs


def build_underrobe():
    """The near-black garment seen through the open front (rule 4).

    Kept exactly UNDER_INSET inside the robe surface using the SAME fold
    function, so the two shells stay parallel everywhere. Give it a different
    fold amplitude instead and the peaks of one punch through the other.
    """
    zs = robe_z_samples(0.060)
    rings = [[robe_point(2 * pi * i / 40, z, -UNDER_INSET) for i in range(40)]
             for z in zs]
    ob = loft("Underrobe", rings, mat=M_ROBE_IN, closed=True,
              cap_start=True, cap_end=True)
    return ob


def build_robe():
    """The outer robe: an open sheet wrapped from one front edge, round the back,
    to the other, then solidified. Modelling the opening as a real gap rather
    than as a dark panel laid on a closed body is what lets the silver piping run
    along an actual edge."""
    zs = robe_z_samples(0.036)
    # 112, not 84. Cusped valleys are narrow by construction, and at the old
    # sampling rate each one spanned about three quads - the loft chorded
    # straight across them and gave back exactly the smooth sheet the cusps
    # were introduced to avoid.
    n_th = 112
    rings = []
    for z in zs:
        oh = robe_open_half(z)
        a0 = THETA_FRONT + oh
        a1 = THETA_FRONT + 2.0 * pi - oh
        rings.append([robe_point(lerp(a0, a1, i / (n_th - 1)), z)
                      for i in range(n_th)])
    ob = loft("Robe", rings, mat=M_ROBE, closed=False)
    solidify(ob, ROBE_THICK, lining=M_ROBE_IN)
    bevel(ob, width=0.004, segments=2)
    return ob


def build_robe_trim():
    """Silver piping down both front edges and along the hem (rule 3).

    Swept from the robe surface itself, so it follows the folds. A trim ring
    generated as a plain circle sits proud of the fold crests and sunk in the
    valleys - the same mistake as the knight's gold heel disc.
    """
    zs = robe_z_samples(0.030)
    for tag, sgn in (("R", 1.0), ("L", -1.0)):
        pts = [robe_point(THETA_FRONT + sgn * robe_open_half(z), z, 0.004)
               for z in zs]
        sweep("Robe_Piping_" + tag, pts, TRIM_R, M_SILVER, segs=8)

    # Fastenings down ONE lapel only - the right. On both edges they read as a
    # buttoned coat; on one they read as a robe that is not done up, which is
    # what "worn loose, never straightened" means.
    for i in range(LAPEL_STUDS):
        z = lerp(1.140, 1.512, i / (LAPEL_STUDS - 1))
        th = THETA_FRONT + robe_open_half(z) + 0.085
        c = robe_point(th, z, 0.010)
        add_sphere("Robe_Stud%d" % i, c, 0.0125, scale=(1.0, 1.0, 0.62),
                   mat=M_SILVER_B, u=12, v=8,
                   rot=look_at_euler(c, Vector((0.0, 0.0, z))))

    # Hem BORDER: a deep band of darker cloth round the bottom of the skirt with
    # the silver piping along its top edge. A single piped line at the hem is a
    # trim; a band is tailoring, and it gives the bottom of the robe some weight
    # to sit on instead of just stopping.
    z0, z1 = ROBE_TABLE[0][0] + 0.006, ROBE_TABLE[0][0] + HEM_BAND
    rows, n = 4, 92
    rings = []
    for i in range(rows + 1):
        z = lerp(z0, z1, i / rows)
        oh = robe_open_half(z)
        rings.append([robe_point(lerp(THETA_FRONT + oh,
                                      THETA_FRONT + 2 * pi - oh, j / (n - 1)),
                                 z, 0.005) for j in range(n)])
    band = loft("Robe_HemBorder", rings, mat=M_ROBE_D, closed=False)
    solidify(band, 0.009)
    bevel(band, width=0.003, segments=2)

    # M_SILVER_H, not M_SILVER: this run is swept along the SCALLOPED hem and needs
    # its own roughness to stay a continuous line round the waves. See the material.
    sweep("Robe_HemBand", rings[-1][::2], TRIM_R * 1.1, M_SILVER_H, segs=8)


def build_sash():
    """Wrapped waist sash. An elliptical cross-section swept round the body: its
    inner edge sits inside the robe surface, which is what makes it touch rather
    than hover.

    The band goes through body_shape() like the robe, the collar and every piece
    of trim do. Lathed as a plain circle of radius SASH_R it only touched the
    robe at the two SIDES: the torso is 0.78 as deep as it is wide at the waist,
    so at the front and the back the band stood a full 3 cm proud of the cloth
    and the waist read as a bowl he was standing in rather than as a wrap. That
    also swallowed the buckle plate below, which was already conformed - the
    plate sat 4 cm behind the band's front face and never appeared in a render.
    """
    def sash_point(theta, r, z):
        # revolve() puts the object at SASH_Z, so the profile's z is a local
        # offset. Sample body_shape at the true world height - the section gets
        # deeper towards the hip, and the band is 10 cm tall - then hand back the
        # local z so the origin still adds SASH_Z.
        p = body_shape(theta, r, SASH_Z + z)
        return (p.x, p.y, z)

    prof = [(SASH_R + SASH_D * cos(2 * pi * i / 16),
             SASH_H * sin(2 * pi * i / 16)) for i in range(16)]
    revolve("Sash", prof, segments=40, mat=M_ROBE_D, origin=(0, 0, SASH_Z),
            close_profile=True, shape_fn=sash_point)

    # Buckle plate at the front of the sash. Gives the waist a focal point and
    # breaks up what is otherwise a plain band of cloth right across the middle
    # of the figure.
    bp = body_shape(THETA_FRONT, SASH_R + SASH_D * 0.55, SASH_Z)
    add_sphere("Sash_Plate", bp, 0.052, scale=(1.00, 0.30, 0.68),
               mat=M_SILVER_B, u=20, v=12)
    add_sphere("Sash_PlateBoss", bp + Vector((0.0, -0.016, 0.0)), 0.020,
               scale=(1.0, 0.45, 1.0), mat=M_SILVER_D, u=14, v=10)

    # Knot and two hanging tails, at his left front so they do not collide with
    # the staff hand.
    th = THETA_FRONT + 0.55
    knot_c = body_shape(th, SASH_R, SASH_Z)
    add_sphere("Sash_Knot", knot_c, 0.040, scale=(1.0, 0.75, 0.85),
               mat=M_ROBE_D, u=18, v=10)
    # Outward from where the knot actually landed, not from the circle it used to
    # sit on - on an elliptical section those two directions differ most at the
    # front, which is exactly where the knot is.
    knot_out = Vector((knot_c.x, knot_c.y, 0.0)).normalized()
    for i, (dx, dz, ln) in enumerate(((-0.030, -0.010, 0.290),
                                      (0.028, -0.004, 0.215))):
        out = knot_out * 0.012
        p0 = knot_c + out + Vector((dx, 0.0, dz))
        p1 = p0 + Vector((dx * 0.6, -0.030, -ln))
        # Scaled flat in local Y so the tail reads as a ribbon of cloth rather
        # than a sausage. capsule() aims local Z along the axis, so local Y is a
        # genuine lateral direction.
        capsule("Sash_Tail%d" % i, p0, p1, 0.030, 0.020, mat=M_ROBE_D,
                scale=(1.0, 0.34, 1.0))


def build_belt_kit():
    """A pouch and a rolled scroll hung from the sash.

    The waist was the emptiest band of the silhouette: below the beard and above
    the skirt there was nothing but a plain wrapped sash straight across the
    figure. These give it something to break, and they read at icon size as two
    small dark masses interrupting the waistline.

    Both hang from STRAPS that overlap the sash, and the pouch and scroll in turn
    overlap their straps. Nothing here is anchored to the robe, so if the sash
    ever moves the whole kit moves with it - and, more to the point, every piece
    is touching the piece above it, which is what keeps them all legal.
    """
    # -- pouch, on his right front quarter (clear of the staff) ---------------
    th = THETA_FRONT - 0.72
    anchor = body_shape(th, SASH_R + 0.006, SASH_Z - 0.020)
    radial = Vector((anchor.x, anchor.y, 0.0)).normalized()

    # A bag, not a gourd. The first profile ran 0.030 -> 0.068 -> 0.026 over a
    # 17 cm drop: a narrow neck, a fat belly and a POINT at the bottom, which is
    # the silhouette of an aubergine and read as exactly that hanging off his
    # belt. A leather belt pouch is shorter than it is wide at the waist, keeps
    # most of its width down to the base, and ends in a rounded bottom seam.
    spine = [anchor + radial * 0.018 + Vector((0, 0, -0.012)),
             anchor + radial * 0.042 + Vector((0, 0, -0.052)),
             anchor + radial * 0.048 + Vector((0, 0, -0.100)),
             anchor + radial * 0.044 + Vector((0, 0, -0.132))]
    prof = [0.046, 0.068, 0.070, 0.054]
    pts = catmull(spine, 6)
    rp = catmull([(r, 0.0, 0.0) for r in prof], 6)

    def bag(t, a):
        i = min(len(rp) - 1, int(t * (len(rp) - 1)))
        r = max(0.006, rp[i].x)
        # Flattened against the hip and slightly gathered - a leather bag with
        # something in it, not a ball.
        return (r * cos(a), r * 0.66 * sin(a))

    sweep_fn("Pouch", pts, bag, M_LEATHER, segs=20)

    # Flap over the mouth of the bag, and the strap holding it to the sash.
    # Wider than the bag's mouth on purpose - a flap that does not overhang is
    # not a flap, it is a lump, and it was one.
    add_sphere("Pouch_Flap", pts[3], 0.064, scale=(1.0, 0.70, 0.40),
               mat=M_LEATHER, u=18, v=10)
    sweep("Pouch_Strap",
          [anchor + radial * 0.004 + Vector((0, 0, 0.052)),
           anchor + radial * 0.020,
           pts[3]],
          0.013, M_LEATHER, segs=8, taper=[1.0, 0.95, 0.85])
    add_sphere("Pouch_Stud", pts[4] + radial * 0.040, 0.013,
               scale=(1.0, 1.0, 0.6), mat=M_SILVER_B, u=12, v=8,
               rot=look_at_euler(pts[4] + radial * 0.040, pts[4]))

    # -- scroll, on his left hip ----------------------------------------------
    th2 = THETA_FRONT + 0.98
    a2 = body_shape(th2, SASH_R + 0.004, SASH_Z - 0.016)
    rad2 = Vector((a2.x, a2.y, 0.0)).normalized()
    top = a2 + rad2 * 0.044 + Vector((0.0, 0.0, -0.048))
    bot = top + rad2 * 0.012 + Vector((0.0, 0.0, -0.150))
    capsule("Scroll", top, bot, 0.026, 0.024, mat=M_PARCH, segs=16)
    # End caps, so it reads as a rolled sheet rather than a stick.
    for tag, p in (("Top", top), ("Bot", bot)):
        add_torus("Scroll_Cap" + tag, p, 0.024, 0.007, mat=M_LEATHER,
                  rot=(bot - top).to_track_quat('Z', 'Y').to_euler())
    sweep("Scroll_Cord",
          [a2 + rad2 * 0.002 + Vector((0, 0, 0.046)),
           a2 + rad2 * 0.026 + Vector((0, 0, -0.004)),
           top + rad2 * 0.004],
          0.008, M_LEATHER, segs=7)


def build_yoke():
    """A tailoring seam over each shoulder, in place of the old shoulder mantle.

    The mantle is gone. It was a separate garment whose hem was a hard edge
    running horizontally through exactly the height where the sleeves flare, so
    it sliced visibly through both of them; and three rendered variants of it -
    hugging, absent, long - were indistinguishable from one another, which is a
    fairly direct statement that it was not doing anything.

    What replaces it does the job the mantle was supposed to do (give the
    shoulder a line, per rule 3) using the robe's own surface: a piped seam
    running from the front opening, up over the shoulder, and down the back.
    """
    for tag, sgn in (("R", -1.0), ("L", 1.0)):
        pts = []
        n = 26
        for i in range(n):
            t = i / (n - 1)
            # Sweeps from the front edge of the opening, over the shoulder, to
            # the back. THETA_FRONT + sgn * angle walks round the body.
            th = THETA_FRONT + sgn * lerp(robe_open_half(1.44), pi * YOKE_END, t)
            # Rises over the shoulder, then keeps FALLING down the back rather
            # than returning to the height it started at. The two sides finish
            # within a centimetre of the spine, so they read as one tailored V
            # across the back instead of two floating dashes.
            z = (1.395 + 0.117 * sin(pi * t) ** 0.7
                 - YOKE_FALL * smoothstep(max(0.0, (t - 0.55) / 0.45)))
            pts.append(robe_point(th, z, 0.006))
        sweep("Yoke_Seam_" + tag, pts, TRIM_R * 0.78, M_SILVER, segs=8)


def build_shoulders():
    """A rounded deltoid over each shoulder joint.

    Without it the sleeve tube exits the robe as a hard elliptical intersection
    line - the "cone rammed into a cylinder" read from the first side render.
    The cap overlaps both surfaces and turns that junction into a form.
    """
    for tag, sgn in (("R", -1.0), ("L", 1.0)):
        set_side(tag)
        # Quiet silk: a sphere spends most of its projected area past the nacre
        # band's knee, so at full strength these read as separate rubber pads
        # rather than as the same cloth as the skirt. See NACRE_STR_QUIET.
        add_sphere("Shoulder_" + tag,
                   (sgn * 0.240, -0.010, 1.458), 0.106,
                   scale=(1.00, 0.74, 0.82), mat=M_ROBE_Q, u=24, v=14)
    set_side("")


def build_collar():
    """Standing collar rising behind the neck. Frames the beard and throws the
    face further into shadow.

    Its bottom ring is sampled straight off the robe surface, so it starts flush
    on the cloth. Started at the neck-hole radius instead it hangs 4 cm clear of
    the robe and trips the levitation check.
    """
    n_th = 72
    a0 = THETA_FRONT + COLLAR_OPEN
    a1 = THETA_FRONT + 2.0 * pi - COLLAR_OPEN
    rows = 8
    z0 = 1.548
    rings = []
    for i in range(rows + 1):
        v = i / rows
        z = lerp(z0, COLLAR_TOP, v)
        ring = []
        for j in range(n_th):
            tj = j / (n_th - 1)
            th = lerp(a0, a1, tj)
            # Radius is taken at z0 and flared outward, NOT at z: above the neck
            # opening the robe table collapses and the collar would funnel inward
            # into the head.
            #
            # The flare ROLLS OVER rather than growing monotonically - it peaks
            # around three-quarters height and comes back in at the lip. Growing
            # it all the way to the top is what made the first collar a funnel, a
            # smooth cone opening straight at the camera. A rolled edge is what
            # cloth actually does when it stands up.
            roll = sin(v * pi * 0.82) ** 1.3
            # Deeper at the back, tapering away toward the front opening, so it
            # frames the beard instead of enclosing it.
            back = 0.35 + 0.65 * sin(pi * tj) ** 0.6
            # Close on the neck as it rises. smoothstep, not a straight lerp: a
            # linear taper from the shoulder shelf to the throat is a 45 degree
            # cone, which is an upside-down lampshade. The S-curve leaves the
            # cloth lying flat where it meets the robe, does its turning in the
            # middle, and stands near-vertical at the lip.
            r = lerp(robe_radius(th, z0), COLLAR_NECK_R, smoothstep(v)) \
                + COLLAR_FLARE * roll * back
            ring.append(body_shape(th, r, z))
        rings.append(ring)
    ob = loft("Collar", rings, mat=M_ROBE, closed=False)
    solidify(ob, 0.013, lining=M_ROBE_IN)
    bevel(ob, width=0.0035, segments=2)

    edge = [rings[-1][j] for j in range(0, n_th, 2)]
    sweep("Collar_Trim", edge, TRIM_R * 0.85, M_SILVER, segs=8)
    return ob


# ==============================================================================
#  ARMS
# ==============================================================================


def build_sleeve(tag, shoulder, elbow, wrist, end_frac, flare):
    """Bell sleeve as an open swept tube that FOLLOWS THE ARM, then solidified.

    Three things changed from the first version, all of them visible in the
    shoulder close-up that prompted the rebuild:

      * It follows shoulder -> elbow -> cuff instead of a straight shoulder ->
        wrist axis, so it bends where the arm bends rather than cutting across
        the crook of the elbow.
      * It is OPEN at both ends and gets its thickness from solidify(), so the
        cuff is a real cloth edge with a lining behind it. The old one was a
        closed lathe with a flat mouth and read as a metal bucket.
      * The mouth waves along the arm axis (the third component of the ring
        function) instead of being cut off by a plane.

    The tube also starts well inside the body, not at the shoulder joint, so its
    open end is buried in the robe rather than showing as a hole in the armpit.
    """
    shoulder, elbow, wrist = Vector(shoulder), Vector(elbow), Vector(wrist)
    root = Vector((shoulder.x * SLEEVE_ROOT, shoulder.y, shoulder.z + 0.012))
    cuff = elbow.lerp(wrist, end_frac)
    spine = catmull([root, shoulder, shoulder.lerp(elbow, 0.55), elbow, cuff], 5)

    def ring(t, a):
        r = SLEEVE_R0 + (flare - SLEEVE_R0) * (t ** 1.8)
        m = 1.0 + SLEEVE_RIPPLE * sin(5.0 * a + 2.4 * t)
        # t**6 keeps the wave entirely at the mouth; applied evenly it makes the
        # whole sleeve wobble like a concertina.
        w = SLEEVE_MOUTH * (t ** 6) * sin(3.0 * a + 0.7)
        return (r * cos(a) * m, r * sin(a) * m, w)

    ob = sweep_fn("Sleeve_" + tag, spine, ring, M_ROBE, segs=32,
                  closed_ends=False)
    solidify(ob, SLEEVE_WALL, lining=M_ROBE_IN)
    bevel(ob, width=0.004, segments=2)

    # Silver cuff band, straddling the OUTER surface just back from the lip.
    #
    # Swept along the sleeve's OWN cross-section, not added as a plain torus. The
    # section ripples by SLEEVE_RIPPLE of its radius - about a centimetre at the
    # bell's mouth - so a true circle of the mean radius is buried at every crest
    # and stands proud at every trough, and the band rendered as a row of dashes
    # rather than a ring. Trim that dashes is worse than no trim: rule 3 is about
    # giving the eye a line it can follow.
    frames = frames_along(spine)
    fi = int(len(frames) * 0.90)
    p, tan, u, v = frames[fi]
    tc = fi / max(1, len(frames) - 1)
    n_band = 40
    band = []
    for k in range(n_band + 1):   # +1 brings the loop back onto its first point
        du, dv, dw = ring(tc, 2.0 * pi * k / n_band)
        band.append(p + u * du + v * dv + tan * dw)
    sweep("Sleeve_Cuff_" + tag, band, 0.011, M_SILVER, segs=10)
    return ob


def build_forearm(tag, elbow, wrist):
    """Under-sleeve forearm, near-black. Only the hand is skin - it is the only
    bare flesh on the model and stays that way.

    Stops BEHIND the palm rather than at the wrist - see FOREARM_END."""
    elbow, wrist = Vector(elbow), Vector(wrist)
    return capsule("Forearm_" + tag, elbow, elbow.lerp(wrist, FOREARM_END),
                   0.044, FOREARM_R1, mat=M_ROBE_IN)


def armour_shell(name, frames, hl_head, hl_lip, depth, lift, mat,
                 segs=16, end_taper=0.80, bev=0.032):
    """One plate of the prosthetic: an elongated rounded shell along `frames`.

    `frames` is [(centre, out, along), ...] - a point on the plate's MID-surface,
    the unit normal pointing away from the limb, and the unit direction the plate
    is SHORT in (down the limb, lip end positive). A superellipse section is swept
    along that list, so what comes out is a lozenge: thin radially, elongated down
    the limb, rounded at every end. There is no box in it to rescue (rule 5), and
    it still gets the bevel + subsurf + smooth-shade treatment because the section
    corners are tight enough to catch a facet without them.

    Three details that are load-bearing rather than decorative:

      * the section is ASYMMETRIC. `hl_lip` is longer than `hl_head` and `lift`
        raises that end off the mid-surface, so a stack of these reads as
        overlapping lames instead of as a row of separate rings;
      * `end_taper` shrinks the section toward both ends of the sweep, finishing
        the plate in a lens rather than in a flat wall. Never to zero: a collapsed
        ring gives a degenerate cap that the bevel then folds inside out;
      * closed and capped, because the audit fails any mesh with a boundary edge
        and an open shell also draws a black rim at grazing angles.
    """
    rings = []
    n = len(frames)
    for i, (c, out, along) in enumerate(frames):
        u = i / max(1, n - 1)
        f = end_taper + (1.0 - end_taper) * sin(pi * (0.06 + 0.88 * u)) ** 0.45
        ring = []
        for k in range(segs):
            th = 2.0 * pi * k / segs
            s, co = sin(th), cos(th)
            # 0.62 rather than 1.0 squares the section off radially, which gives
            # the plate a face for the light to sit on. A plain ellipse here is a
            # tube, and a row of tubes is a caterpillar.
            r = f * (lift * (0.5 + 0.5 * s)
                     + depth * math.copysign(abs(co) ** 0.62, co))
            a = f * (hl_lip if s >= 0.0 else hl_head) \
                  * math.copysign(abs(s) ** 0.85, s)
            ring.append(c + out * r + along * a)
        rings.append(ring)
    ob = loft(name, rings, mat=mat, closed=True, cap_start=True, cap_end=True)
    bevel(ob, width=bev, segments=2)
    subsurf(ob, 1)
    return ob


def build_pros_vambrace(tag, elbow, wrist):
    """The forearm half of the wrought-silver arm - see the PROS_ block above.

    A near-black core, one bright collar band where the cloth stops, four silver
    lames ringed round it with a bright band drawn along every lip, and a
    near-black gasket showing in every joint.

    The core is doing real work and is not just filler: it is the gap-lining. It
    is what shows through the joints and through the wrap's opening, and together
    with the bands it is the reason the stack reads as outlined structure when it
    downscales instead of fusing into one smooth metal tube (rules 3 and 4).
    """
    elbow, wrist = Vector(elbow), Vector(wrist)
    span = (wrist - elbow).length
    ax = (wrist - elbow).normalized()
    # Body-side reference vector, so the opening in the wrap can be aimed away
    # from the cameras by angle alone - see PROS_PHI0.
    e1 = Vector((1.0, 0.0, 0.0))
    e1 = (e1 - ax * e1.dot(ax)).normalized()
    e2 = ax.cross(e1).normalized()

    s0, s1 = span * PROS_T0, span * PROS_T1
    pitch = (s1 - s0) / (PROS_LAMES - 1)

    def mid_r(s):
        """Lame mid-surface radius `s` metres down the arm from the elbow.

        Extrapolates past both ends deliberately: the core and the gaskets read
        off the SAME law as the lames, so no amount of re-tuning the taper can
        leave one of them floating off the others."""
        return lerp(PROS_R0, PROS_R1, (s - s0) / (s1 - s0))

    def arc(centre, r, along, n=26):
        """Frames for one wrap of the limb at radius `r`."""
        out = []
        for i in range(n):
            a = PROS_PHI0 + PROS_SPAN * i / (n - 1)
            d = e1 * cos(a) + e2 * sin(a)
            out.append((centre + d * r, d, along))
        return out

    # The core runs back under the last of the flesh forearm and forward into the
    # fist, so there is no station along the limb where the silver has nothing
    # dark behind it. Its far cap stops well short of the shaft.
    a0, a1 = span * PROS_COLLAR - 0.014, s1 + 0.035
    capsule("Pros_Core_" + tag, elbow + ax * a0, elbow + ax * a1,
            mid_r(a0) - PROS_CORE_IN, mid_r(a1) - PROS_CORE_IN,
            mat=M_VOID, segs=20)

    # The collar. Where the cloth stops the metal starts, and it starts with one
    # hard bright ring rather than with a plate edge fading out under a wavy cuff.
    # This is the whole reveal: without it the rolled-back sleeve just looks short.
    sc = span * PROS_COLLAR
    armour_shell("Pros_Collar_" + tag, arc(elbow + ax * sc, mid_r(sc) + 0.0032, ax),
                 0.0085, 0.0085, 0.0062, 0.0, M_PROS_HI, bev=0.010)

    for k in range(PROS_LAMES):
        s = s0 + pitch * k
        f = arc(elbow + ax * s, mid_r(s), ax)
        armour_shell("Pros_Lame_%s%d" % (tag, k), f,
                     PROS_HL_HEAD, PROS_HL_LIP, PROS_D, PROS_LIFT, M_PROS)
        # The drawn line, and it is a BAND now, not a hairline. Half-sunk into the
        # lip's bevel so it sits on the plate rather than hovering over it, and
        # wide enough to stay continuous when the render is scaled down - at 1.8 mm
        # it broke into a handful of speculars and the plate boundaries stopped
        # existing, which is the failure rule 3 is specifically about.
        edge = [(p + out * (PROS_LIFT * 0.92 + PROS_D * 0.62)
                   + al * (PROS_HL_LIP * 0.86), out, al)
                for (p, out, al) in f]
        armour_shell("Pros_LameEdge_%s%d" % (tag, k), edge,
                     PROS_EDGE_HL, PROS_EDGE_HL, PROS_EDGE_R, 0.0, M_PROS_HI,
                     segs=12, bev=0.008)

    # Gaskets. Each sits in the slot between two lames, proud enough of the lower
    # one to be seen and far enough under the upper one's lip to stay a recess.
    # Without them the joint is silver meeting silver and the segmentation
    # disappears the moment the render is scaled down.
    for k in range(PROS_LAMES - 1):
        s = s0 + pitch * (k + 0.5)
        f = arc(elbow + ax * s, mid_r(s) + PROS_GAP_R, ax)
        armour_shell("Pros_Gasket_%s%d" % (tag, k), f,
                     0.0060, 0.0060, 0.0035, 0.0, M_VOID,
                     segs=12, bev=0.008)


def _rot_about(axis, angle):
    return Matrix.Rotation(angle, 3, axis)


def build_palm(name, centre, across, thick, along, size, mat=None):
    """A flattened rounded block - the palm.

    A sphere was the first attempt and it reads as an egg with sausages attached,
    because a hand's defining feature is that it is FLAT: wide across the
    knuckles, thin front to back. The superellipse power squares the section off
    just enough to give the back of the hand a plane for light to sit on.

    `mat` defaults to skin. The staff hand passes M_VOID: over there this block is
    not flesh at all, it is the near-black core the knuckle tiles sit on and what
    shows in the gap between them.
    """
    rings = []
    rows = 8
    for i in range(rows + 1):
        t = i / rows
        # Rounds off at both the wrist and the knuckle end rather than stopping
        # in a flat disc.
        s = sin(pi * (0.11 + 0.78 * t)) ** 0.42
        # Wider at the knuckles than at the wrist.
        w = size[0] * s * lerp(0.82, 1.0, t)
        h = size[1] * s
        off = (t - 0.5) * size[2]
        ring = []
        for k in range(22):
            a = 2 * pi * k / 22
            c, sn = cos(a), sin(a)
            du = w * math.copysign(abs(c) ** 0.68, c)
            dv = h * math.copysign(abs(sn) ** 0.68, sn)
            ring.append(centre + across * du + thick * dv + along * off)
        rings.append(ring)
    ob = loft(name, rings, mat=mat or M_SKIN, closed=True,
              cap_start=True, cap_end=True)
    return ob


def build_digit(name, pts, r0, r1, knuckles=3.0, flat=0.86, mat=None):
    """A finger: tapered, slightly flattened, and bulged at the knuckles.

    The bulges are the whole point. A smooth tapered tube is a sausage; three
    swellings along its length are what make it read as jointed at the size the
    game actually shows the hands at.

    The staff hand builds its digits one PHALANX at a time - three short calls
    with knuckles=1.0, so each gets a single swelling in its own middle and the
    joints fall in the waists between them. `mat` is how those come out as plate
    rather than as skin.
    """
    def ring(t, a):
        r = lerp(r0, r1, t) * (1.0 + FINGER_KNUCKLE * sin(pi * t * knuckles) ** 2)
        return (r * cos(a), r * flat * sin(a))
    return sweep_fn(name, pts, ring, mat or M_SKIN, segs=10)


def build_grip_hand(tag, centre, axis, out_dir, shaft_r):
    """The staff hand: wrought silver, fused shut on the shaft.

    The framing is unchanged from the flesh hand this replaces - fingers are swept
    along arcs measured around the SHAFT axis, so they wrap the staff instead of
    being parked near it, and `out_dir` still points from the shaft back toward
    the wrist. What changed is what they are made of and how far they close.

    Every curl radius here is a couple of millimetres tighter than the flesh hand
    used, which is the whole point: the shells bite into the wood along their
    entire length and there is no daylight anywhere between a finger and the
    shaft. This grip closed once and there is nothing in it that could open.
    """
    axis = Vector(axis).normalized()
    out_dir = (Vector(out_dir) - axis * Vector(out_dir).dot(axis)).normalized()
    side = axis.cross(out_dir).normalized()
    # Everything about this hand is measured toward the CAMERA side of the shaft.
    # The digits used to sweep the other way, round the back, and all that reached
    # the lens was four tips poking past the far edge of the wood - which every
    # reader of the render called rivets, banding or a bound cord, never a hand.
    # `fwd` is the direction they wrap now: out of the page, across the near face.
    fwd = -side
    centre = Vector(centre)

    # Back of the hand faces outward; the palm plate wraps the shaft. Near-black
    # rather than skin - here the block is the core the knuckle tiles sit on, and
    # what shows in the gap between them and around their ends. `fwd` as its long
    # axis so the block's wide knuckle end points where the fingers actually go.
    palm_c = centre + out_dir * (shaft_r + 0.030)
    build_palm("Palm_" + tag, palm_c, axis, out_dir, fwd,
               (0.062, 0.026, 0.052), mat=M_VOID)

    # Knuckle guard: two tiles across the back of the fist, carrying the forearm's
    # taper on to the knuckles. STRAIGHT tiles, not rings - a ring at this station
    # would have to pass through the shaft, which is the same wall that stops the
    # lame stack at PROS_T1.
    for j, (soff, r_out, half) in enumerate(((-0.009, 0.0315, 0.052),
                                             ( 0.016, 0.0292, 0.046))):
        n = 20
        f = []
        for i in range(n):
            u = lerp(-half, half, i / (n - 1))
            q = u / half
            # Bowed, so the tile follows the back of the hand down to the index
            # and little-finger knuckles instead of standing off it at the ends.
            # `slope` is d(bow)/du, which is what tilts the plate's normal with
            # it - without that the shell twists off its own surface at the tips.
            bow = r_out * (1.0 - 0.32 * q * q)
            slope = -0.64 * r_out * q / half
            nrm = (out_dir - axis * slope).normalized()
            f.append((palm_c + fwd * soff + out_dir * bow + axis * u,
                      nrm, fwd))
        armour_shell("Pros_Knuckle_%s%d" % (tag, j), f,
                     PROS_HL_HEAD, PROS_HL_LIP, PROS_D, PROS_LIFT, M_PROS,
                     end_taper=0.34)
        edge = [(p + nrm * (PROS_LIFT * 0.92 + PROS_D * 0.62)
                   + al * (PROS_HL_LIP * 0.86), nrm, al)
                for (p, nrm, al) in f]
        armour_shell("Pros_KnuckleEdge_%s%d" % (tag, j), edge,
                     PROS_EDGE_HL, PROS_EDGE_HL, PROS_EDGE_R, 0.0, M_PROS_HI,
                     segs=12, end_taper=0.34, bev=0.008)

    for k in range(4):
        # Index nearest the top of the grip, little finger lowest, and the outer
        # two shorter - a hand where all four fingers are the same length reads as
        # a mitten. Spaced 36 mm and built fat: four SLIM digits at this scale
        # average into a ribbed band, four fat ones read as four knuckles.
        z_off = (1.5 - k) * 0.036
        length = (0.94, 1.04, 1.00, 0.88)[k]
        base = centre + axis * z_off
        # NEGATIVE sweep: out of `out_dir` (which points back at the wrist) round
        # through `fwd` and on to the far side. The middle of every finger now
        # crosses the near face of the shaft where the camera can see it, and the
        # tips come far enough round to break the staff's outline in silhouette -
        # which is what stops the staff reading as a stick standing beside him.
        a0, a1 = radians(-12.0), radians(-12.0 - 122.0 * length)
        # Three phalanges per finger, each its own shell. The cuts are not even
        # thirds: a real proximal phalanx is the longest of the three, and that
        # unevenness is most of what stops the finger reading as a segmented hose.
        cuts = (0.0, 0.44, 0.76, 1.0)
        for j in range(3):
            n = 6
            pts = []
            for i in range(n):
                # Each shell starts slightly before its own cut and ends slightly
                # after it, so consecutive shells interpenetrate at the joints.
                # Butt-jointed they showed shaft through the seam three times down
                # every finger, and a gap in this hand is the one thing the whole
                # idea cannot survive.
                t = lerp(cuts[j] - (0.035 if j else 0.0),
                         cuts[j + 1] + (0.035 if j < 2 else 0.0), i / (n - 1))
                a = lerp(a0, a1, t)
                # Tighter than the flesh hand's 0.013 -> 0.004: with the shell's
                # radial half-thickness at ~0.8 of its radius this buries the
                # inner face well inside the nominal grip radius, which is past
                # the wound cord and into the wood at every ridge and valley.
                rr = shaft_r + lerp(0.009, 0.002, t)
                pts.append(base + (_rot_about(axis, a) @ out_dir) * rr)
            build_digit("Finger_%s%d%s" % (tag, k, "abc"[j]), pts,
                        lerp(0.0186, 0.0132, cuts[j]),
                        lerp(0.0186, 0.0124, cuts[j + 1]),
                        knuckles=1.0, flat=0.80, mat=M_PROS)

    # Thumb, and it crosses the FRONT of the fist rather than hiding behind it: it
    # rides up and over the backs of the fingers at a larger radius than they use,
    # so from the camera it is one unbroken diagonal bar laid across four rungs.
    # That diagonal is most of what says "hand" at a glance - four parallel digits
    # on their own are a grille. Two shells, not three: a thumb has two phalanges,
    # and giving it three is the tell that it was drawn from the other fingers.
    def _tp(deg, up, extra):
        return (centre + axis * up
                + (_rot_about(axis, radians(deg)) @ out_dir) * (shaft_r + extra))

    tp = catmull([_tp(-20.0, -0.062, 0.020), _tp(-40.0, -0.030, 0.025),
                  _tp(-60.0,  0.006, 0.027), _tp(-78.0,  0.038, 0.024)], 5)
    # The slice overlaps by two samples for the same reason the fingers do.
    build_digit("Thumb_%s0" % tag, tp[:10], 0.0205, 0.0160,
                knuckles=1.0, flat=0.82, mat=M_PROS)
    build_digit("Thumb_%s1" % tag, tp[8:], 0.0160, 0.0118,
                knuckles=1.0, flat=0.82, mat=M_PROS)


def build_open_hand(tag, wrist, fwd, up):
    """Relaxed open hand, fingers slightly curled. His left, held forward - the
    natural place for a future cast VFX attach point.

    GLOVED, not bare, and that changed the moment the other hand went to silver:
    see M_GLOVE. Left as skin it was the only flesh left anywhere on the figure,
    which turned a supporting detail into the second thing the eye went to."""
    wrist = Vector(wrist)
    fwd = Vector(fwd).normalized()
    up = (Vector(up) - fwd * Vector(up).dot(fwd)).normalized()
    side = fwd.cross(up).normalized()

    palm_c = wrist + fwd * 0.046
    build_palm("Palm_" + tag, palm_c, side, up, fwd, (0.060, 0.023, 0.056),
               mat=M_GLOVE)

    for k in range(4):
        off = (k - 1.5) * 0.025
        length = (0.90, 1.02, 1.00, 0.86)[k]
        # Curl PER FINGER, increasing toward the little finger. One shared curl
        # value put every fingertip on the same line, so the four staggered
        # lengths above cancelled out into a flat fan and the hand read as a
        # rubber glove. A relaxed hand curls progressively across the palm, and
        # it is that arc of fingertips - not the individual digits - that says
        # "hand" at the size this is actually seen.
        curl = (0.022, 0.030, 0.041, 0.053)[k]
        base = palm_c + side * off + fwd * 0.034
        n = 7
        pts = []
        for i in range(n):
            t = i / (n - 1)
            # Curl: fingers drop toward the palm as they extend, and splay very
            # slightly. A relaxed open hand is never a flat fan.
            pts.append(base + fwd * (0.068 * length * t)
                            - up * (curl * t * t)
                            + side * (off * 0.26 * t))
        build_digit("Finger_%s%d" % (tag, k), pts, 0.0145, 0.0098, mat=M_GLOVE)

    t0 = palm_c + side * 0.044 - fwd * 0.006
    pts = [t0,
           t0 + fwd * 0.024 + side * 0.014 - up * 0.006,
           t0 + fwd * 0.046 + side * 0.024 - up * 0.016,
           t0 + fwd * 0.062 + side * 0.030 - up * 0.026]
    build_digit("Thumb_" + tag, pts, 0.0175, 0.0115, knuckles=2.0, mat=M_GLOVE)


def build_arms():
    set_side("R")
    build_sleeve("R", SHOULDER_R, ELBOW_R, WRIST_R, SLEEVE_END_R,
                 SLEEVE_FLARE_R)
    build_forearm("R", ELBOW_R, WRIST_R)
    # Everything below mid-forearm on this side is wrought silver. The flesh
    # forearm above still gets built: from the cuff down to PROS_T0 it is the
    # near-black stump the plate emerges from, and below that it is buried inside
    # the prosthetic's own core.
    build_pros_vambrace("R", ELBOW_R, WRIST_R)
    # The grip is taken from the staff spine, not from a hand-authored point, so
    # re-posing the staff carries the hand with it.
    tan = (Vector(STAFF_SPINE[4]) - Vector(STAFF_SPINE[2])).normalized()
    # Out-direction read off the WRIST rather than written out again. The whole
    # point of swinging WRIST_R forward was to bring the hand round to the camera
    # side of the shaft; a hardcoded (1, 0.15, 0) would have left the palm parked
    # where the wrist used to be and torn the hand off the arm.
    build_grip_hand("R", GRIP_C, tan, WRIST_R - GRIP_C, GRIP_R)

    set_side("L")
    build_sleeve("L", SHOULDER_L, ELBOW_L, WRIST_L, SLEEVE_END_L,
                 SLEEVE_FLARE_L)
    build_forearm("L", ELBOW_L, WRIST_L)
    build_open_hand("L", WRIST_L, Vector((-0.25, -1.0, 0.10)),
                    Vector((0.0, 0.0, 1.0)))
    set_side("")


# ==============================================================================
#  HEAD, BEARD, HAT
# ==============================================================================


def build_head():
    """Void sphere. There is no face: the brim shadow and this near-black
    material ARE the face (rule 4). A modelled face under a brim reads as a
    smudge at any size the game actually shows him at."""
    add_sphere("Head", (0.0, 0.0, Z_HEAD), HEAD_R, scale=HEAD_SCALE,
               mat=M_VOID, u=28, v=16)
    capsule("Neck", (0.0, 0.0, Z_NECK_BASE), (0.0, -0.008, Z_NECK_TOP),
            0.064, 0.056, mat=M_VOID)
    if EYES_ON:
        build_eyes()


def build_eyes():
    """Two angular slits seated into the front of the head sphere.

    Flat-shaded icosahedra, not smooth ellipsoids: the knight's model records
    that a soft round emitter reads as a cartoon eye however saturated it is.
    Each is placed just INSIDE the head's surface so roughly half of it
    protrudes - enough to be seen, and enough to intersect the head, which is
    what keeps it off the levitation list.
    """
    for tag, sgn in (("R", -1.0), ("L", 1.0)):
        set_side(tag)
        # Solve the head ellipsoid for the surface depth at this x and z, then
        # sit a little inside it. Hardcoding y here would silently detach the
        # eyes the next time the head moves - and the head has moved once
        # already.
        ry = HEAD_R * HEAD_SCALE[1]
        rz = HEAD_R * HEAD_SCALE[2]
        k = 1.0 - (EYE_X / (HEAD_R * HEAD_SCALE[0])) ** 2 \
                - ((EYE_Z - Z_HEAD) / rz) ** 2
        y_surf = -ry * math.sqrt(max(0.02, k))
        add_gem("Eye_" + tag, (sgn * EYE_X, y_surf + 0.0032, EYE_Z),
                radius=1.0, subdiv=0, mat=M_EYE, scale=EYE_SCALE,
                rot=(0.0, 0.0, sgn * EYE_CANT))
    set_side("")


def build_beard():
    """Long beard, hanging from inside the head down over the chest.

    Built as FIVE separate tapered locks, not one lofted mass. Chosen 2026-08-01
    from three rendered options and the difference is not subtle: a single mass -
    with or without its cross-section carved into ridges - reads as a bib from
    the front and as a hood at three-quarters, because a continuous silhouette
    edge is the one thing hair never has. Carving the ridges into one surface was
    also tried and the subsurf rounded them straight back out.

    Every lock starts at BEARD_TABLE's first row, which is INSIDE the head
    sphere. That overlap is what keeps all five off the levitation list.
    """
    t = BEARD_TABLE

    def sample(v):
        """(z, y, half_width, half_depth) at parameter v down the beard."""
        i = v * (len(t) - 1)
        k = min(len(t) - 2, int(i))
        u = i - k
        a, b = t[k], t[k + 1]
        return [a[j] + (b[j] - a[j]) * u for j in range(4)]

    #                x offset, width scale, length scale
    for i, (dx, wsc, lsc) in enumerate(BEARD_LOCKS):
        pts, tap = [], []
        rows = 12
        for r in range(rows + 1):
            v = (r / rows) * lsc
            z, y, hw, hd = sample(v)
            # Locks converge slightly as they fall, the way real hair does, and
            # alternate depths so they overlap rather than sitting in a flat row.
            pts.append(Vector((dx * (1.0 - 0.30 * v),
                               y - 0.009 * (i % 2),
                               z)))
            tap.append(max(0.05, (hw * wsc) / t[0][2]
                               * (1.0 - BEARD_TAPER_FALL * v)))
        sweep("Beard_Lock%d" % i, pts, t[0][2] * BEARD_LOCK_R, M_HAIR, segs=12,
              taper=tap)


def hat_xf(p):
    """Apply the hat's cock to a world point.

    Every hat part goes through this. Rotating the crown but not the brim, or
    the brim but not the band, is the obvious way to get a hat that comes apart,
    and it would pass the audit because all the pieces would still be touching
    SOMETHING.
    """
    return HAT_PIVOT + Matrix.Rotation(HAT_TILT, 3, 'Y') @ (Vector(p) - HAT_PIVOT)


def brim_quad(vals, a):
    """Interpolate four azimuth anchors (+X, +Y, -X, -Y) smoothly and cyclically.

    A 4-point DFT rather than a table lookup. It returns each anchor EXACTLY at
    its own azimuth, which is what makes the four numbers in BRIM_REACH and
    BRIM_BEND directly tunable, and it is infinitely differentiable in between,
    which a table is not - on a surface this large an interpolation crease shows
    up as a ridge running down the felt.
    """
    l, b, r, f = vals
    return (0.25 * (l + b + r + f)
            + 0.50 * (l - r) * cos(a)
            + 0.50 * (b - f) * sin(a)
            + 0.25 * (l - b + r - f) * cos(2.0 * a))


def _wrap_pi(x):
    """Signed angular distance, so a lobe centred near 0 or 2*pi does not tear."""
    return (x + pi) % (2.0 * pi) - pi


def brim_reach(a):
    """Outer radius of the brim at azimuth a, in metres, before it is folded.

    Anchors + a 3-lobe and a 5-lobe hand-warp + one dent. Three superposed
    frequencies with incommensurate periods, because ANY single harmonic - at
    any amplitude - still traces an ellipse-like closed curve, and "it is just an
    ellipse" is precisely what this outline was rejected for.
    """
    r = (brim_quad(BRIM_REACH, a)
         + BRIM_WAVE3 * sin(3.0 * a + BRIM_WAVE3_PH)
         + BRIM_WAVE5 * sin(5.0 * a + BRIM_WAVE5_PH))
    return r - BRIM_DENT * math.exp(-(_wrap_pi(a - BRIM_DENT_A)
                                      / BRIM_DENT_W) ** 2)


def brim_fold(a):
    """Degrees of arc the brim turns through at azimuth a. Positive folds down.

    A residual slouch from the four anchors, plus two LOCALISED events - the sag
    and the flip-back - plus a ripple between them. The locality is the entire
    point: a smooth low-order function of azimuth applied to a disc is a tilt, and
    a tilt has no silhouette events in it at all.
    """
    v = (brim_quad(BRIM_TILT, a)
         + BRIM_SAG * math.exp(-(_wrap_pi(a - BRIM_SAG_A) / BRIM_SAG_W) ** 2)
         + BRIM_FLIP * math.exp(-(_wrap_pi(a - BRIM_FLIP_A)
                                  / BRIM_FLIP_W) ** 2))
    # The drape: same Gaussian form, alternating sign, so the hanging cloth
    # breaks into folds that each have a lit face and a shadowed one. See
    # BRIM_FOLD_LOBES - the sign alternation is the mechanism, not decoration.
    for amp, az, w in BRIM_FOLD_LOBES:
        v += amp * math.exp(-(_wrap_pi(a - radians(az)) / radians(w)) ** 2)
    return v


def brim_rz(a, u, zl):
    """Map one profile sample onto the warped brim. Returns (radius, z, angle).

    The fold is a real ARC, not a vertical displacement: beyond the fold line the
    radial axis is bent through brim_fold(a) degrees, and the profile's own z is
    carried along that arc's NORMAL. Four things follow, all of them the reason
    it is done this way rather than by pushing verts down:

      * the shell stays exactly as thick through a 130 degree fold as it is on
        the flat, so the edge thickness is proportional everywhere;
      * an angle past -90 rolls the edge back OVER itself with no special case -
        which is the whole of the flip-back, and the reason it is expressed as an
        angle rather than as a height;
      * the fold line moves outward as the fold sharpens, so a hard crease stays
        local and does not eat the span;
      * the surface never creases where it is not meant to, because an arc is C1
        with the flat it springs from.
    """
    R = brim_reach(a)
    phi = brim_fold(a)
    knee = R * lerp(BRIM_KNEE_F, BRIM_FOLD_F,
                    min(1.0, abs(phi) / BRIM_FOLD_REF))
    # The inner rows keep a fixed reach. Swinging them with the azimuth would
    # walk the anchor ring out of the head sphere on the wide side.
    r_flat = u * lerp(BRIM_NOM, R, smoothstep(u / 0.50))
    s = r_flat - knee
    k = radians(phi) / max(0.05, R - knee)
    if s <= 0.0 or abs(k) < 1e-6:
        return (r_flat, zl, 0.0)
    ang = k * s
    rr = knee + sin(ang) / k
    dz = -(1.0 - cos(ang)) / k
    return (rr + zl * sin(ang), dz + zl * cos(ang), ang)


def brim_point(a, u, zl):
    rr, zz, _ang = brim_rz(a, u, zl)
    return (rr * cos(a), rr * sin(a), zz)


def build_hat():
    """Brim + crown + band, the whole assembly cocked over to his left.

    The chain that keeps this off the levitation list is: the brim's inner ring
    sits inside the head sphere, and the crown's lower wall sits inside the
    brim's inner ring. Change BRIM_PROFILE[0] or HAT_TILT and check the audit.
    """
    # M_BRIM, not M_ROBE_Q: once the brim is bent this hard it presents broad
    # surfaces to the key instead of the shallow near-edge-on disc M_ROBE_Q was
    # damped for, and it came back brighter than the beard. See M_BRIM.
    #
    # 120 segments, not 52: the flip-back lobe turns 130 degrees over ~76 degrees
    # of azimuth, so the fold line itself sweeps in and out fast. A feature
    # narrower than the sample spacing is below Nyquist and deepening it only
    # aliases harder - and this change is entirely made of such features.
    segs = 120
    brim = revolve("Hat_Brim", BRIM_PROFILE, segments=segs, mat=M_BRIM,
                   origin=hat_xf((0.0, 0.0, Z_BRIM)), close_profile=True,
                   shape_fn=brim_point)
    brim.rotation_euler = (0.0, HAT_TILT, 0.0)

    # Under the brim is a RECESS. Rule 4 lists it, and so does the doc, by name.
    # One lathe is one material, so the return half of the profile - the run back
    # from the lip toward the head, which is the surface directly over the face -
    # is switched to the lining slot instead. Left as silk it catches the fill and
    # lifts the very shadow the hat exists to cast, which is the hat's first job.
    #
    # Selected by WHICH SIDE OF THE SHELL a face is on, never by its world normal.
    # The normal test this replaces is correct only for a shallow brim, and it is
    # the direct cause of the "flat hard-edged blade with a straight leading edge"
    # and "separate dark plank" that 3/3 verifiers saw on the fold lobes. Once a
    # fold passes ~105 degrees the TOP surface's normal tilts past the threshold
    # and turns near-black halfway across itself; past 90 the underside comes back
    # up and turns silk. Rendered with the lining slot painted red, the sag lobe's
    # upper surface was a solid red field with a hard straight boundary through it
    # and a jagged per-face staircase at the tip where the test aliased. A fold
    # angle must not be able to change which side of a piece of cloth you are
    # looking at.
    #
    # revolve() emits `segments` faces per profile band, in profile order, with
    # close_profile appending one last band - so band = index // segments, and
    # bands from BRIM_UNDER_FROM on are the return run plus the inner wall. Guarded
    # by the face count, because that mapping is the one thing here that depends on
    # how revolve() happens to loop.
    #
    # d24 attempt 4: the boundary moves from BRIM_UNDER_FROM to BRIM_DARK_FROM,
    # which is INBOARD of the lip rather than on it. Measured, the underside was
    # 5.2 / 0.0 / 5.5 per cent of visible hat pixels in hero_34 / front /
    # icon_full_184 - the fold has turned the topside to face both cameras and
    # swung the lining out of sight - so the near-black surface has to start
    # before the edge or it is not in the picture. See BRIM_DARK_FROM for the
    # numbers and the geometry.
    me = brim.data
    lining_idx = len(me.materials)
    me.materials.append(M_BRIM_IN)
    if len(me.polygons) == len(BRIM_PROFILE) * segs:
        for i, p in enumerate(me.polygons):
            if i // segs >= BRIM_DARK_FROM:
                p.material_index = lining_idx
    else:                                    # generator changed: fail visibly
        raise RuntimeError("Hat_Brim face count %d != %d bands x %d segments"
                           % (len(me.polygons), len(BRIM_PROFILE), segs))

    # Subsurf carries the 120-segment warp across the felt without faceting it.
    # No bevel any more: the lip it existed to round is now buried inside the
    # rolled hem, and beveling a shell this thick pulled the two surfaces together
    # at the tips - which is half of where the knife-edge read came from.
    subsurf(brim, 1)

    # THE ROLLED HEM. A real bead of cloth run right round the outer edge, built
    # as a lathe of its own circular section pushed through the SAME brim_rz(), so
    # it inherits every fold, warp and dent by construction and the asymmetry is
    # untouched. Two things it buys, both of them 3/3 verifier requests:
    #
    #   * the outermost thing on the brim is now a 34 mm ROUND tube at every
    #     azimuth, so neither wingtip can taper to a knife edge;
    #   * its section is in METRES, not in the profile's normalised u, so the hem
    #     stays one physical thickness while the reach swings 0.39 - 0.76 m. A
    #     bead written into the profile would have been half as thick at the dent
    #     as at the widest point, which is not how a hem works.
    #
    # It is the brim's own material, and deliberately no brighter: this is a FORM,
    # carried by thickness in the silhouette, not a value. That is the difference
    # between it and the silver wire that was dropped.
    def hem_shape(a, dr, dz):
        rr, zz, ang = brim_rz(a, BRIM_HEM_U, BRIM_HEM_Z)
        return (((rr + dr * cos(ang) + dz * sin(ang)) * cos(a)),
                ((rr + dr * cos(ang) + dz * sin(ang)) * sin(a)),
                zz - dr * sin(ang) + dz * cos(ang))

    # Section points offset by half a step so none lands at radius 0, which
    # revolve() would read as a pole and fan into triangles.
    sec = [(BRIM_HEM_R * cos(pi * (2 * i + 1) / 14.0),
            BRIM_HEM_R * sin(pi * (2 * i + 1) / 14.0)) for i in range(14)]
    hem = revolve("Hat_BrimHem", sec, segments=segs, mat=M_BRIM,
                  origin=hat_xf((0.0, 0.0, Z_BRIM)), rot=(0.0, HAT_TILT, 0.0),
                  close_profile=True, shape_fn=hem_shape)
    subsurf(hem, 1)

    # THERE IS NO EDGE WIRE, and that is a finding rather than an omission.
    # Attempt 1 couched a 3 mm tarnished-silver wire along this edge. Measured, it
    # lifted 94 px in icon_full_184 - 0.28% of the frame - and all three verifiers
    # independently reported it as absent from every view. The bracket that says
    # it cannot be fixed by widening is in the same run: 4.8 mm and 7.5 mm both
    # stopped being a line and became a band, which is the failure that has
    # already sunk two changes on this asset for stealing the gem's job.
    #
    # icon_full_184 resolves ~48 px/m. A one-pixel plateau there is a 21 mm
    # stroke, and a 21 mm silver band around a 1 m brim is an area, not a line.
    # The standing fact is that a sub-pixel plateau cannot be brightened into
    # legibility - so this element cannot do the job at this scale and is gone
    # rather than kept as decoration. The brim's outline is drawn by the
    # background it sits against, which needs no help.

    # Crown as a shaped sweep rather than a circular one, so the felt has an oval
    # section and a crease running up one side.
    spine = catmull([hat_xf(p) for p in HAT_SPINE], 7)
    rr = catmull([(r, 0.0, 0.0) for r in HAT_RADII], 7)

    def ring(t, a):
        i = min(len(rr) - 1, int(t * (len(rr) - 1)))
        r = max(0.004, rr[i].x)
        # Oval, plus a single crease. Both fade out toward the tip, where the
        # cone is too thin for either to read as anything but a kink.
        fade = 1.0 - smoothstep((t - 0.55) / 0.45)
        m = 1.0 + fade * (HAT_OVAL * cos(2.0 * a)
                          - HAT_CREASE * (0.5 + 0.5 * cos(a - 0.9)) ** 3.0)
        return (r * m * cos(a), r * m * sin(a))

    # M_BRIM, not M_ROBE_Q, and this is the one place d24 reaches past the brim.
    # Two measurements forced it. First, with the brim taken to a matte felt the
    # crown was left the only glossy silk on the hat, so the two halves of one
    # garment read as two fabrics from a metre away. Second, and the reason it is
    # worth the extra line: masked per-object, the CROWN is p99 0.493 in `front`
    # against the gem's 0.215, where the brim is 0.278 - so the "broad glossy
    # sweep near the head competing with the gem" that three verifiers reported
    # is here, on the cone, not on the thing that got bigger. The deltoids keep
    # M_ROBE_Q; they are robe, not hat.
    sweep_fn("Hat_Crown", spine, ring, M_BRIM, segs=30)

    # Dark dome closing the crown just above the head, so the underside of the
    # hat is black rather than lit blue.
    add_sphere("Hat_Void", hat_xf((0.0, 0.010, 1.929)), 0.104,
               scale=(1.0, 1.0, 0.55), mat=M_VOID, u=24, v=10,
               rot=(0.0, HAT_TILT, 0.0))

    band = add_torus("Hat_Band", hat_xf((0.0, 0.006, HATBAND_Z)),
                     HATBAND_R, HATBAND_MINOR, mat=M_ROBE_D)
    band.rotation_euler = (0.0, HAT_TILT, 0.0)

    # Silver buckle plate on the band, front centre, with a small violet stone.
    # Repeats the staff's motif at a whisper and gives the hat an accent that
    # survives to icon size.
    plate_c = hat_xf((0.0, -HATBAND_R - 0.004, HATBAND_Z))
    add_sphere("Hat_Buckle", plate_c, 0.030, scale=(1.0, 0.42, 0.78),
               mat=M_SILVER_B, u=16, v=10, rot=(0.0, HAT_TILT, 0.0))
    add_gem("Hat_Stone", plate_c + Vector((0.0, -0.012, 0.0)), 0.017,
            subdiv=1, mat=M_GEM_S, scale=(1.0, 0.75, 1.0))


# ==============================================================================
#  STAFF
# ==============================================================================


def staff_radius_at(t):
    """Shaft radius a fraction t along the staff, knots included.

    One function, used by the shaft itself, the bands, the wound grip and the
    tendrils, so all four agree about where the surface is. The bands were a
    floating hoop the first time precisely because they did not.
    """
    rr = catmull([(r, 0.0, 0.0) for r in STAFF_RADII], 7)
    i = max(0, min(len(rr) - 1, int(t * (len(rr) - 1))))
    u = i / max(1, len(rr) - 1)
    r = max(0.004, rr[i].x)
    return r * (1.0 + STAFF_KNOT * sin(STAFF_KNOT_F * u * 2.0 * pi) * 0.5
                    + STAFF_KNOT * 0.4 * sin(STAFF_KNOT_F * 2.6 * u * 2.0 * pi) * 0.5)


def build_staff():
    """Blackwood shaft with three ridges winding up it, a wound leather grip,
    and five wooden tendrils curling in to hold the stone.

    Planted point-down. The base ring sits at z = STAFF_SPINE[0].z, a hair above
    the floor for the same bevel reason as the robe hem.

    The previous version was a smooth tapered tube with three metal hoops and
    five identical claws, and read - accurately - as a broom handle with a
    bauble. Everything below exists to give the eye something to travel along.
    """
    spine = catmull(STAFF_SPINE, 7)

    def ring(t, a):
        r = staff_radius_at(t)
        # Three ridges, rotating STAFF_TWIST radians over the length. The cosine
        # is raised to a power so the valleys between ridges are narrow and
        # cusped; a plain cosine gives a gently wavy tube that still reads as
        # turned rather than grown. STAFF_LOBES must stay an integer or the
        # section stops being 2*pi periodic and the sweep tears open.
        f = (0.5 + 0.5 * cos(STAFF_LOBES * a + STAFF_TWIST * t)) ** 1.7
        r *= 1.0 + STAFF_RIDGE * (f - 0.34)
        return (r * cos(a), r * sin(a))

    sweep_fn("Staff_Shaft", spine, ring, M_WOOD, segs=STAFF_SEGS)

    frames = frames_along(spine)

    def at(t):
        """Frame at t, interpolated BETWEEN spine samples.

        Snapping to the nearest frame index caps the axial resolution of
        everything that follows this path at the spine's own sample count. The
        grip spans 0.24 of a 50-sample spine, so it had twelve distinct heights
        available: a 36-turn winding collapsed onto twelve of them and came out
        as twelve fat rings with a ladder's rungs, and adding samples to the
        helix could not fix it because the helix was already right - the path it
        was sampling was a staircase.
        """
        x = min(max(t, 0.0), 1.0) * (len(frames) - 1)
        i = min(len(frames) - 2, int(x))
        f = x - i
        p0, t0, u0, _v0 = frames[i]
        p1, t1, u1, _v1 = frames[i + 1]
        tan = t0.lerp(t1, f)
        tan = tan.normalized() if tan.length > 1e-9 else t0
        # Re-orthogonalise: lerping two unit vectors does not keep them
        # perpendicular, and a frame that is not orthonormal shears the sweep.
        u = u0.lerp(u1, f)
        u = u - tan * u.dot(tan)
        u = u.normalized() if u.length > 1e-9 else u0
        return p0.lerp(p1, f), tan, u, tan.cross(u).normalized()

    # -- leather cord wound round the grip ------------------------------------
    # A real helix of cord, not a texture and not a plain cylinder. It is the
    # cheapest large gain in apparent complexity on the whole model: ~90 samples
    # of one swept tube, and it instantly explains where the hand goes.
    #
    # Sample count is per TURN, not a fixed total. At a flat 132 for 19 turns
    # this got 6.9 samples per revolution: each turn came out as a seven-sided
    # polygon whose chords cut back inside the shaft, so all that showed was the
    # outer arc of each chord and the winding read as a row of separate staples.
    # Under-sampling a helix does not make it coarse, it makes it a different
    # object.
    pts = []
    n = GRIP_TURNS * 16 + 1
    for i in range(n):
        t = lerp(GRIP_T0, GRIP_T1, i / (n - 1))
        p, _tan, u, v = at(t)
        # Sits ON the shaft surface, so the cord half-sinks into the wood the way
        # a tight winding does.
        rr = staff_radius_at(t) + GRIP_CORD_R * 0.35
        a = GRIP_TURNS * 2.0 * pi * (i / (n - 1))
        pts.append(p + u * (rr * cos(a)) + v * (rr * sin(a)))
    sweep("Staff_Wrap", pts, GRIP_CORD_R, M_LEATHER, segs=7)

    # Silver ferrules pinning each end of the winding.
    for tag, t in (("Lo", GRIP_T0 - 0.012), ("Hi", GRIP_T1 + 0.012)):
        p, tan, _u, _v = at(t)
        add_torus("Staff_GripRing" + tag, p, staff_radius_at(t) + 0.002, 0.0105,
                  mat=M_SILVER, rot=tan.to_track_quat('Z', 'Y').to_euler())

    # -- one plain band low down, and the shod ferrule ------------------------
    p, tan, _u, _v = at(0.13)
    add_torus("Staff_Band0", p, staff_radius_at(0.13) + 0.002, 0.0105,
              mat=M_SILVER, rot=tan.to_track_quat('Z', 'Y').to_euler())

    p0, tan0, _u, _v = at(0.0)
    # Radii must clear the shaft or the ferrule generates entirely inside it and
    # simply never appears.
    revolve("Staff_Ferrule", [(0.0, -0.004), (0.028, 0.004), (0.050, 0.032),
                              (0.049, 0.078), (0.044, 0.088), (0.0, 0.078)],
            segments=22, mat=M_SILVER_D, origin=p0,
            rot=tan0.to_track_quat('Z', 'Y').to_euler())

    # -- the setting: tendrils of the same wood -------------------------------
    ps, tans, us, vs = at(TENDRIL_SPLIT)
    binding_r = staff_radius_at(TENDRIL_SPLIT)
    add_torus("Staff_Binding", ps, binding_r + 0.003, 0.013, mat=M_SILVER,
              rot=tans.to_track_quat('Z', 'Y').to_euler())

    for i in range(TENDRILS):
        a = 2.0 * pi * i / TENDRILS + radians(18.0)
        d = Vector((cos(a), sin(a), 0.0))
        # Each tendril is slightly different - length, how far it bows out, how
        # high it reaches. Five identical claws is the look this is escaping.
        wob = 1.0 + 0.16 * sin(2.7 * i + 1.1)
        # Bows out PAST the girdle (the stone's widest line, at radius GEM_R)
        # before closing back over it. Bowing out to less than GEM_R and then
        # "inward" is geometrically the wrong way round and produces a claw that
        # never actually passes over the stone it is supposed to be holding.
        bow = 0.104 * wob
        top = GEM_C.z + 0.030
        base = ps + d * (binding_r * 0.6)
        pts = [base,
               base + d * bow * 0.55 + Vector((0, 0, 0.040)),
               base + d * bow + Vector((0, 0, 0.080 * wob)),
               # Closes over the girdle and bites in. A tendril that stops short
               # of the gem is both a levitating part and, worse, visibly not
               # holding it.
               Vector((GEM_C.x, GEM_C.y, top)) + d * (GEM_R * 0.72)]
        sweep("Staff_Tendril%d" % i, pts, 0.033 * wob, M_WOOD_L, segs=10,
              taper=[1.0, 0.82, 0.62, 0.34])

    # -- the seat the stone sits in -------------------------------------------
    # A silver cup whose inner wall hugs the pavilion and whose rim stands a
    # little proud of the girdle. It is proper jewellery construction, and it is
    # also what makes the gem legal under rule 1: driven point-first into the
    # shaft, the stone's nearest neighbouring SURFACE was 5.5 mm away - measuring
    # from a vertex buried inside the shaft out to the shaft's skin. Being deeply
    # embedded in something is not the same as touching it, and the levitation
    # check is right to say so.
    #
    # The rim stays LOW - 0.09, about 6 mm proud of a 92 mm stone. Raising it to
    # 0.26 so a band of silver showed round the base of the crown was tried on
    # 2026-08-01 and rejected on the render: C_SILVER is a mirror at roughness
    # 0.062, and a mirror in a world this dark reflects darkness. Enlarging it
    # did not add metal, it added a black band between the stone and the claws,
    # with a few brighter glints on it - the crest came out darker and the gem
    # looked cut off from the cage holding it. Silver here works as GLINTS on a
    # small area, not as an area of value. If this ever needs revisiting the
    # lever is the material, not the size.
    seat = [(0.00, -0.82), (0.55, -0.44), (0.92, -0.12), (1.08, 0.02),
            (1.05,  0.09), (0.88, -0.10), (0.52, -0.40), (0.00, -0.74)]
    # M_SILVER_B, not M_SILVER. The cradle is a small isolated piece of jewellery,
    # not a run, so it belongs to the fittings class - and the cut that suited the
    # runs took it to 0.116 mean, at which the staff head read at icon size as a
    # purple lump with no visible setting. Most of the value it has now is not this
    # material at all: it is the GemSpillDown light in the rig finally letting the
    # claws CATCH the stone they are holding, which took the seat from 0.116 to
    # 0.392 mean in front. The albedo only has to be enough to catch it.
    revolve("Staff_Seat", [(r * GEM_R, z * GEM_R) for r, z in seat],
            segments=GEM_FACETS * 2, mat=M_SILVER_B, origin=GEM_C)

    # -- the stone ------------------------------------------------------------
    # smooth=False is LOAD-BEARING, not a style choice. M_GEM's emission is
    # driven by Layer Weight Facing (gate_facet_emission), and the only reason
    # that produces flat planes with hard edges rather than a soft gradient is
    # that the shading normal is constant across each face. Shade this smooth and
    # the cut disappears while the mesh stays exactly as it is.
    revolve("Staff_Gem", [(r * GEM_R, z * GEM_R) for r, z in GEM_PROFILE],
            segments=GEM_FACETS, mat=M_GEM, origin=GEM_C, smooth=False)


def build_gatestone():
    """The broken lintel block of the Weeping Gate, still on the staff's point.

    ONE mesh, genus 1: an outer skin, a bore through it, and two rims bridging
    them. Built by hand rather than with loft() because loft() skins a stack of
    rings and would have to cap the ends, which is the one thing this shape must
    not do - the hole is the point.

    Shape: the intersection of nine non-parallel fracture planes (GS_PLANES),
    wedge-sectioned in z, with ONE of those planes left flat and dressed to
    carry the inscription. Rescued per rule 7 - bevel, subsurf, shade smooth -
    and then warped by a displace so it weathers instead of looking machined.

    The bore is coaxial with the shaft by construction: its centre at every
    height is read off STAFF_SPINE rather than written out again, so the block
    cannot drift off the staff if the staff is ever re-planted. It is also
    narrower than the shaft at the bottom, so the two genuinely intersect and
    the block is held rather than hovering (rule 1, and the audit's rule-1
    check, which measures surface distance and is not fooled by "nearly").
    """
    set_side("")

    P0, P1 = Vector(STAFF_SPINE[0]), Vector(STAFF_SPINE[1])

    def axis_at(z):
        f = (z - P0.z) / (P1.z - P0.z)
        return Vector((lerp(P0.x, P1.x, f), lerp(P0.y, P1.y, f), z))

    seat = axis_at(0.15)
    e_out = Vector((seat.x, seat.y, 0.0)).normalized()   # away from the figure
    e_side = Vector((-e_out.y, e_out.x, 0.0))

    def direction(phi):
        a = phi + GS_ROT
        return e_out * cos(a) + e_side * sin(a)

    def lift(phi):
        """1 at the inner lip, 0 at the outboard end."""
        return 0.5 + 0.5 * cos(phi - GS_INNER_A)

    def z_bot(phi):
        L = lift(phi)
        return (GS_Z_FLOOR + GS_LIFT * L
                + (0.010 * cos(2.0 * phi + 1.4) + 0.006 * cos(3.0 * phi - 0.6))
                * (0.30 + 0.70 * L))

    def z_top(phi, r=None):
        """Top surface, `r` metres out from the bore axis along `phi`.

        The minimum of GS_TOP_PLANES, so the top is part of the same half-space
        intersection the flanks are and the creases between planes are real
        edges rather than a shading gradient. `r` defaults to the OUTER rim;
        the bore rim passes its own, much smaller radius, which is what tilts
        the mouth instead of leaving it a level ring.
        """
        a = phi + GS_ROT
        if r is None:
            r, _which = surface_r(phi, 1.0)
        u, v = r * cos(a), r * sin(a)
        return min(z0 - s * (cos(radians(az)) * u + sin(radians(az)) * v)
                   for z0, az, s in GS_TOP_PLANES)

    def bore_r(z):
        f = min(1.0, max(0.0, (z - GS_Z_FLOOR) / GS_BORE_SPAN))
        return lerp(GS_BORE_LO, GS_BORE_HI, f)

    def surface_r(phi, t):
        """Nearest fracture plane at (phi, t), and which one it was."""
        best, which = 1e9, -1
        for i, (a, d0, d1) in enumerate(GS_PLANES):
            c = cos(phi - a)
            if c <= 0.06:
                continue
            r = lerp(d0, d1, t) / c
            if r < best:
                best, which = r, i
        return best, which

    a_d, ad0, ad1 = GS_PLANES[GS_DRESSED]

    def glyph_cut(s, w):
        """Depth of the incision at face-local (s, w).

        Distance to the nearest stroke, run through a rounded valley profile.
        A weathered cut has no sharp arris left, and a hard-edged trench at this
        sample spacing would simply be chorded flat by the subsurf anyway - the
        groove is 26 mm across and the columns here are ~4 mm, six samples, so
        the shape it can actually represent is this one.
        """
        best = 1e9
        for (s0, w0), (s1, w1) in GS_GLYPHS:
            dx, dy = s1 - s0, w1 - w0
            span = dx * dx + dy * dy
            f = 0.0 if span < 1e-12 else ((s - s0) * dx + (w - w0) * dy) / span
            f = min(1.0, max(0.0, f))
            best = min(best, math.hypot(s - (s0 + dx * f), w - (w0 + dy * f)))
        if best >= GS_GLYPH_W:
            return 0.0
        return GS_GLYPH_D * (1.0 - smoothstep(best / GS_GLYPH_W))

    def fracture(phi, t):
        """Chipping. Integer harmonics only, or the section stops being 2*pi
        periodic and the skin tears open up one side - the same constraint the
        robe's fold function is under. Biased inward so it can only ever move
        the block AWAY from the cloth."""
        a0, a1, a2 = GS_FRAC
        return (a0 * sin(3.0 * phi + 2.1 + 1.7 * t)
                + a1 * sin(5.0 * phi - 0.7 + 2.9 * t)
                + a2 * sin(7.0 * phi + 1.3 - 2.2 * t) - GS_FRAC_BIAS)

    # -- column angles, dense over the carved face ----------------------------
    steps = 1024
    cum = [0.0]
    for j in range(steps):
        d = 2.0 * pi * j / steps - GS_FINE_C
        d = (d + pi) % (2.0 * pi) - pi
        cum.append(cum[-1] + 1.0 + GS_FINE_GAIN * math.exp(-(d / GS_FINE_W) ** 2))
    phis, j = [], 0
    for i in range(GS_SEGS):
        want = cum[-1] * i / GS_SEGS
        while j < steps and cum[j + 1] < want:
            j += 1
        phis.append(2.0 * pi * j / steps)

    # -- skin -----------------------------------------------------------------
    bm = bmesh.new()
    outer, inner = [], []
    clearance = 1e9
    for phi in phis:
        zb, zt = z_bot(phi), z_top(phi)
        # The bore's rim rides the same fracture planes as the outer rim, at the
        # bore's own radius, so the top cap is a TILTED quad rather than a level
        # one. One pass is exact enough: bore_r moves 10 mm over 276 mm of z, so
        # seeding it with the outer rim's height costs well under a millimetre.
        zt_i = z_top(phi, bore_r(zt))
        co, ci = [], []
        for k in range(GS_LEVELS + 1):
            t = k / GS_LEVELS
            z = lerp(zb, zt, t)
            zi = lerp(zb, zt_i, t)
            r, _which = surface_r(phi, t)
            # How completely the dressed plane owns this column. Used as a mask
            # rather than an equality test on `which`: a hard switch at the
            # crease puts a one-column step in the surface, and the inscription
            # is supposed to run off the fracture, not fall off a cliff.
            c = cos(phi - a_d)
            mask = 0.0
            if c > 0.06:
                mask = 1.0 - smoothstep((lerp(ad0, ad1, t) / c - r) / 0.003)
            if mask > 0.0:
                r -= glyph_cut(r * sin(phi - a_d), z) * mask / max(c, 0.5)
            r += fracture(phi, t) * (1.0 - mask)
            d = direction(phi)
            p = axis_at(z) + d * r
            co.append(bm.verts.new(p))
            ci.append(bm.verts.new(axis_at(zi) + d * bore_r(zi)))
            clearance = min(clearance, math.hypot(p.x, p.y)
                            - robe_radius(math.atan2(p.y, p.x), z))
        outer.append(co)
        inner.append(ci)

    n = len(phis)
    for i in range(n):
        h = (i + 1) % n
        for k in range(GS_LEVELS):
            bm.faces.new((outer[i][k], outer[i][k + 1],
                          outer[h][k + 1], outer[h][k]))
            bm.faces.new((inner[i][k], inner[h][k],
                          inner[h][k + 1], inner[i][k + 1]))
        top = GS_LEVELS
        bm.faces.new((outer[i][top], inner[i][top],
                      inner[h][top], outer[h][top]))
        bm.faces.new((outer[i][0], outer[h][0], inner[h][0], inner[i][0]))

    ob = _finish("Gatestone", bm, M_STONE, COL_MAGE)

    # Bore interior gets the near-black material. Selected by position rather
    # than by face index: the face order out of bmesh is an implementation
    # detail and a builder edit that reorders it would silently paint the
    # outside of the rock black.
    ob.data.materials.append(M_STONE_IN)
    for poly in ob.data.polygons:
        c = poly.center
        a = axis_at(c.z)
        if math.hypot(c.x - a.x, c.y - a.y) < bore_r(c.z) + 0.010:
            poly.material_index = 1

    bevel(ob, width=GS_BEVEL, segments=3, angle=25.0)
    subsurf(ob, 1)
    # Weathering. A displace rather than more harmonics in surface_r() because
    # the harmonics are periodic in phi by necessity and periodic weathering is
    # exactly the "regular repetition reads as machinery" failure.
    try:
        tex = bpy.data.textures.new("GatestoneRock", type='CLOUDS')
        tex.noise_scale = GS_WARP_SCALE
        tex.noise_depth = 3
        warp = ob.modifiers.new("Warp", 'DISPLACE')
        warp.texture = tex
        warp.strength = GS_WARP
        warp.mid_level = 0.5
        warp.texture_coords = 'LOCAL'
    except Exception as exc:                     # pragma: no cover
        print("Gatestone: displace warp skipped (%s)" % exc)

    print("Gatestone: %d columns x %d levels, clearance to robe %.4f m"
          % (len(phis), GS_LEVELS + 1, clearance))
    return ob


# ==============================================================================
#  ASSEMBLY
# ==============================================================================


def add_empty(name, loc, size=0.05):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = size
    e.location = loc
    COL_MAGE.objects.link(e)
    EMPTIES.append(e)
    return e


def build_mage():
    build_underrobe()
    build_robe()
    build_robe_trim()
    build_sash()
    build_belt_kit()
    build_collar()
    build_shoulders()
    build_arms()
    build_yoke()
    build_head()
    build_beard()
    build_hat()
    build_staff()
    # After the staff: the block reads the shaft's own spine for its bore.
    build_gatestone()

    add_empty("Attach_StaffGem", GEM_C)
    add_empty("Attach_CastHand", WRIST_L + Vector((-0.05, -0.10, 0.0)))
    # Taken from the last spine point, not from Z_HAT_TIP: the crown's apex and
    # its tip are no longer the same place now that the point curls over.
    add_empty("Attach_HatTip", HAT_SPINE[-1])
    add_empty("Attach_Ground", (0.0, 0.0, 0.0), size=0.25)


# --- variant hook -------------------------------------------------------------
# A runner (_tools/preview.py) pre-seeds VARIANT in this namespace before exec'ing
# the file. Entries are applied after every default above is set and before
# anything is built, so a variant can override any tuning constant, any material,
# or any builder function.
#
# This block cannot be moved into a shared helper and imported. globals() here
# resolves to the CALLING module's namespace - which is precisely what the hook
# needs and precisely what an imported function could not give it. A DRY cleanup
# that extracts this silently breaks name resolution for every variant.
#
# RENDER_DIR rides in here too, deliberately: it is assigned unconditionally at
# the top of the file, so a plain namespace seed would be clobbered. Applying it
# here - after that assignment, before render_view() reads it - is what makes
# previews land in the run directory instead of _mage000/.
_v = globals().get("VARIANT", {})
globals().update({k: v for k, v in _v.items() if not k.startswith("_")})
if _v.get("_patch"):
    # Structural variants arrive as SOURCE, not as function objects. A function
    # defined in the runner carries the runner's __globals__ and cannot see
    # revolve(), M_SILVER, or any other helper here - it would fail at call time,
    # deep in the build, for a reason that looks nothing like its cause.
    exec(_v["_patch"], globals())
# ------------------------------------------------------------------------------

build_mage()
print("Mage built: %d meshes, %d empties" % (len(PARTS), len(EMPTIES)))


# ==============================================================================
#  PREVIEW RIG
#
#  Cold gothic ambience, warm key - the same art direction as the knight, so the
#  two heroes can be compared in the same light. The rig lives in its own
#  collection and is never exported.
# ==============================================================================


def build_rig():
    world = bpy.data.worlds.new("MageWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.030, 0.034, 0.052, 1.0)
    bg.inputs[1].default_value = 0.85
    SCENE.world = world

    def area(name, loc, target, energy, color, size):
        d = bpy.data.lights.new(name, type='AREA')
        d.energy = energy
        d.color = color
        d.size = size
        o = bpy.data.objects.new(name, d)
        o.location = loc
        o.rotation_euler = look_at_euler(loc, target)
        COL_RIG.objects.link(o)
        return o

    # Roughly a THIRD of the knight's energies, and that is not a mistake. His
    # model is almost entirely metallic=1.0, which has no diffuse response and
    # only picks up light where a highlight lands. This one is almost entirely
    # dielectric cloth, which answers the same light Lambertian across its whole
    # surface. Lit at the knight's levels a robe with a base value of 0.024
    # renders as pale lavender, and "midnight blue" is gone.
    aim = (0.0, 0.0, 1.30)
    area("Key",   (-2.15, -2.60, 3.05), aim, 118, (1.00, 0.84, 0.62), 2.2)
    area("Fill",  ( 2.40, -2.00, 1.35), aim,  24, (0.58, 0.72, 1.00), 2.6)
    area("RimL",  ( 1.85,  2.20, 2.50), aim,  92, (0.44, 0.62, 1.00), 1.4)
    area("RimR",  (-2.00,  1.95, 2.10), aim,  66, (0.46, 0.66, 1.00), 1.4)
    # Low violet bounce, standing in for the gem's own spill onto the robe.
    # Without it the gem is the only violet in frame and reads as a sticker.
    area("GemSpill", (-1.30, -1.20, 2.15), (-0.30, 0.00, 1.55), 22,
         (0.62, 0.30, 1.00), 1.8)

    # The gem's own spill, and it has to be a LIGHT because the emitter does not
    # emit. Measured: taking GEM_EMIT from 0.10 to 35 - a 350x change that renders
    # the stone pure white - moves the chroma of the shaft from 0.0369 to 0.0369
    # and of the hat brim from 0.0348 to 0.0349. EEVEE's ray-traced GI does not
    # carry this emitter onto its neighbours at all, so no amount of emission will
    # ever make the one light source on this character light anything. If that is
    # wanted, and it is - it is the character's whole premise - it must be a lamp.
    #
    # Three things about this lamp, each of which was a failed version first:
    #
    # SPOT, AIMED DOWN, not a point light at the stone. A point light at GEM_C
    # lights the stone's own facets, and that is fatal: at 18 W the gem's chroma
    # collapsed from 0.1345 to 0.0568, i.e. the spill washed out the exact thing it
    # was added to show off. Everything worth lighting is BELOW the gem, so the
    # cone points down and the stone sits behind it.
    #
    # SHADOWS OFF. With them on this light does literally nothing at any energy -
    # 8, 25 and 60 W all rendered identical to no light at all - because it is
    # sitting inside Staff_Seat, which is a closed revolve, so every ray is blocked
    # by the cup it lives in. An emitter modelled as a lamp inside its own geometry
    # must be shadowless or it is simply switched off.
    #
    # A WIDE CONE, AND 16 W RATHER THAN THE 25 THAT LOOKED BEST ON ITS OWN. It has
    # to reach the hat brim, which is ~0.9 m away and the furthest thing meant to
    # catch it; at 150 deg the brim's chroma goes 0.0437 -> 0.0619 at icon size,
    # the claws 0.0555 -> 0.0659, the upper shaft 0.0438 -> 0.0455. Narrowing to
    # 110 deg loses the brim again, so the cone stays wide and the ENERGY is what
    # gives way - because a wide cone also washes the beard, and the beard is the
    # only thing on the model that can still out-peak the gem. 25 W lifts the
    # beard's brightest pixel to 0.698 against the gem's 0.704, a margin of six
    # thousandths, which is not a margin. 16 W puts it at 0.668 and costs only 4%
    # of the brim spill. Aiming the cone off the head was tried at +-25 deg on both
    # axes and does not work: the cone is 150 deg, so the head is inside it either
    # way and only the far edge moves.
    #
    # Like GemSpill above it, this is preview-rig only and does not export.
    glow = bpy.data.lights.new("GemSpillDown", type='SPOT')
    glow.energy = 16.0
    glow.color = (0.62, 0.26, 1.00)
    glow.spot_size = radians(150.0)
    glow.spot_blend = 0.65
    glow.shadow_soft_size = 0.055
    if hasattr(glow, "use_shadow"):
        glow.use_shadow = False
    glow_ob = bpy.data.objects.new("GemSpillDown", glow)
    # Just below the girdle, so the cone clears the crown of the stone.
    glow_ob.location = GEM_C + Vector((0.0, 0.0, -0.020))
    COL_RIG.objects.link(glow_ob)      # default rotation already aims down -Z

    floor_mat = make_material("RigFloor", (0.020, 0.023, 0.033, 1.0), 0.0, 0.42)
    revolve("Ground", [(0.0, 0.0), (16.0, 0.0)], segments=64, mat=floor_mat,
            coll=COL_RIG, origin=(0.0, 0.0, -0.004))

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 62
    cam = bpy.data.objects.new("Cam", cam_data)
    COL_RIG.objects.link(cam)
    SCENE.camera = cam

    r = SCENE.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y = 900, 1300
    r.resolution_percentage = 100
    r.film_transparent = False
    ee = SCENE.eevee
    for attr, val in (("taa_render_samples", BASE_SAMPLES), ("use_raytracing", True),
                      ("use_shadows", True), ("use_volumetric_shadows", True)):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except Exception:
                pass
    # KNOWN, and not fixed here: the gem renders with a fine regular weave over
    # its whole crown - a stable one-pixel checkerboard swinging about 6% in
    # value, clearest in the `gem` close-up. It is not the geometry (the stone is
    # an 8-segment flat-shaded lathe, 64 facets; the cells are one pixel) and it
    # is not the material. Ruled out by rendering on 2026-08-01, both with no
    # visible change:
    #   * ray_tracing_options.resolution_scale = '1' (half-res refraction)
    #   * ray_tracing_options.denoise_temporal = False (temporal reprojection,
    #     which cannot converge on a single still)
    # It is invisible at figure scale and it does not touch the FBX - node graphs
    # and render settings do not export - so it is a preview-rig curiosity, not
    # an asset defect. Next things to try would be taa_render_samples well above
    # 96, or render.dither_intensity, or Cycles for the close-up only.
    # The view-transform enums are populated from OCIO and are NOT introspectable
    # here (bl_rna reports a single NONE item), so membership testing gives false
    # negatives. Assign, then read back and print - a silent failure leaves the
    # render on Standard, which clips every highlight to white.
    for vt in ('AgX', 'Filmic', 'Standard'):
        try:
            SCENE.view_settings.view_transform = vt
            break
        except Exception:
            continue
    for lk in ('AgX - Medium High Contrast', 'Medium High Contrast', 'None'):
        try:
            SCENE.view_settings.look = lk
            break
        except Exception:
            continue
    SCENE.view_settings.exposure = 0.0
    print("view transform = %r  look = %r" % (SCENE.view_settings.view_transform,
                                              SCENE.view_settings.look))
    return cam


def set_rig_yaw(deg):
    """Rotate the whole light rig about world Z, in degrees.

    The orbit stimulus (_tools/orbit.py) needs the lighting to follow each camera
    bearing, or a back bearing renders an unlit silhouette and the comparison becomes
    about lighting rather than about the model. The key/fill/rim/spill relationship is
    tuned art direction, so the RIG is rotated as a unit rather than the key being
    moved - the relationship survives, only the raking direction changes.

    No-ops when nothing has asked for a yaw, so every existing named view renders
    exactly as before.
    """
    if deg is None:
        return
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    for ob in COL_RIG.objects:
        if ob.type != 'LIGHT':
            continue
        if "_rig0" not in ob:
            # Remember the authored position once, so repeated yaws compose from the
            # original rather than accumulating drift across a multi-cell render.
            ob["_rig0"] = list(ob.location)
            ob["_rot0"] = list(ob.rotation_euler)
        x0, y0, z0 = ob["_rig0"]
        ob.location = (x0 * ca - y0 * sa, x0 * sa + y0 * ca, z0)
        r0 = ob["_rot0"]
        ob.rotation_euler = (r0[0], r0[1], r0[2] + a)


def render_mask(name, cam_loc, target, res, lens):
    """Write `<name>_mask.png`: a cheap RGBA silhouette of the figure alone.

    WHY THIS EXISTS. measure.py used to derive the figure mask by comparing pixels to
    the median of the four corner patches. That is only valid on an empty backdrop, and
    this rig stands the model on a ground disc with `film_transparent = False`, so the
    floor counted as figure: real renders measured 55.18% "figure coverage" with 45.2%
    of the mask sitting in the bottom third of frame. Every silhouette number computed
    from it was compressed toward a constant.

    Hiding the ground changes bounce light, so this pass is NOT a substitute for the
    real render and must never be used for photometry. It supplies a BOOLEAN GEOMETRIC
    MASK only - which bounce light cannot affect - and every value, contrast and colour
    statistic is still measured inside that mask on the real, ground-lit image.

    Cheap on purpose: quarter resolution and the floor sample count. A silhouette does
    not need samples, and this runs once per judged view.
    """
    r = SCENE.render
    ground = bpy.data.objects.get("Ground")
    prev = (r.film_transparent, r.image_settings.color_mode,
            r.resolution_x, r.resolution_y, r.filepath,
            getattr(SCENE.eevee, "taa_render_samples", None),
            ground.hide_render if ground else None)
    try:
        if ground:
            ground.hide_render = True
        r.film_transparent = True
        r.image_settings.color_mode = 'RGBA'
        r.resolution_x, r.resolution_y = max(64, res[0] // 4), max(64, res[1] // 4)
        if hasattr(SCENE.eevee, "taa_render_samples"):
            SCENE.eevee.taa_render_samples = 8
        r.filepath = os.path.join(RENDER_DIR, name + "_mask.png")
        bpy.ops.render.render(write_still=True)
    finally:
        # Restore unconditionally. A half-restored scene would silently render every
        # later view transparent, which is the kind of failure that costs a whole wave.
        if ground:
            ground.hide_render = prev[6]
        (r.film_transparent, r.image_settings.color_mode,
         r.resolution_x, r.resolution_y, r.filepath) = prev[:5]
        if prev[5] is not None and hasattr(SCENE.eevee, "taa_render_samples"):
            SCENE.eevee.taa_render_samples = prev[5]


def render_view(name, cam_loc, target=(0, 0, 1.30), res=(900, 1300), lens=62,
                samples=None, rig_yaw=None, mask=False):
    # A preview run renders a cheap subset rather than all of them. RENDER_ONLY
    # unset (the normal case) means "render everything", so a plain
    # `blender -b -P blender_evilMage000.py -- render` is unaffected.
    only = globals().get("RENDER_ONLY")
    if only is not None and name not in only:
        return
    set_rig_yaw(rig_yaw)
    cam = SCENE.camera
    cam.location = cam_loc
    cam.rotation_euler = look_at_euler(cam_loc, target)
    cam.data.lens = lens
    SCENE.render.resolution_x, SCENE.render.resolution_y = res
    # ALWAYS set the sample count, never inherit it. A view that names no count
    # falls back to BASE_SAMPLES rather than to whatever the previous view left on
    # the scene - see the note on BASE_SAMPLES. SAMPLE_SCALE now applies to every
    # view, which is what --samples always claimed to do.
    scale = globals().get("SAMPLE_SCALE", 1.0)
    want = samples if samples else globals().get("BASE_SAMPLES", 96)
    if hasattr(SCENE.eevee, "taa_render_samples"):
        SCENE.eevee.taa_render_samples = max(16, int(want * scale))
    os.makedirs(RENDER_DIR, exist_ok=True)
    SCENE.render.filepath = os.path.join(RENDER_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    # Print the sample count with every view. Cheap, and it is the only way to tell
    # from the outside whether a view rendered at the quality you think it did -
    # which was exactly the bug BASE_SAMPLES fixes.
    print("rendered %s  (%dx%d, %d samples)"
          % (SCENE.render.filepath, res[0], res[1],
             getattr(SCENE.eevee, "taa_render_samples", -1)))
    # Optional companion silhouette. Rendered AFTER the real image so a failure here
    # cannot cost the view itself.
    if mask:
        render_mask(name, cam_loc, target, res, lens)


def export_fbx():
    for ob in bpy.data.objects:
        ob.select_set(False)
    for ob in PARTS + EMPTIES:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = PARTS[0]
    bpy.ops.export_scene.fbx(
        filepath=FBX_PATH,
        use_selection=True,
        object_types={'MESH', 'EMPTY'},
        add_leaf_bones=False,
        mesh_smooth_type='FACE',
        # These two are what land him facing +Z in Unity given he faces -Y here.
        axis_forward='-Z',
        axis_up='Y',
        global_scale=1.0,
    )
    print("Exported:", FBX_PATH)


CAM = build_rig()

if DO_SAVE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print("Saved:", BLEND_PATH)

if DO_RENDER:
    # Distances are set so a ~2.5 m figure (gem included) fills the frame at
    # these focal lengths. Closer and the gem or the hem gets cropped.
    render_view("poster", (-2.05, -6.10, 1.05), target=(0.0, 0.0, 1.32),
                res=(1400, 1950), lens=80, samples=320)
    render_view("hero_34", (-3.25, -4.05, 1.85), target=(0, 0, 1.28),
                samples=160)
    render_view("front", (0.0, -5.60, 1.28), lens=70)
    render_view("side", (5.60, -0.15, 1.28), lens=70)
    render_view("back", (0.30, 5.60, 1.32), lens=70)
    render_view("back34", (3.70, 3.90, 1.75), target=(0, 0, 1.25))
    # Aimed BELOW the brim, not at it. Pointed at the hat this view fills the
    # frame with felt and crops the beard off the bottom, which makes it useless
    # for judging the one thing under there worth looking at.
    render_view("head", (-0.86, -1.72, 2.02), target=(0.0, -0.10, 1.66),
                res=(820, 820), lens=72)
    # Close-ups. Everything below exists because it is a place where two surfaces
    # meet and a full-body render is too small to show whether they meet
    # correctly. The knight learned this the expensive way - see its _audit/
    # folder - so the mage gets the close-ups as first-class views.
    render_view("gem", (-1.05, -1.35, 2.62), target=(-0.34, -0.02, 2.42),
                res=(760, 760), lens=90)
    render_view("shoulder", (-1.30, -1.05, 1.85), target=(-0.20, -0.06, 1.44),
                res=(760, 760), lens=85)
    # Aimed at the GRIP, not at the middle of the figure. The first framing put
    # the sash in the centre of the frame and the hand behind the staff at the
    # edge, which is not a check of anything.
    render_view("hands", (-0.78, -0.90, 1.26), target=(-0.35, -0.10, 1.09),
                res=(760, 760), lens=85)
    render_view("hand_left", (0.10, -1.05, 1.34), target=(0.24, -0.26, 1.14),
                res=(760, 760), lens=85)
    render_view("hem", (-0.90, -1.55, 0.55), target=(-0.10, -0.10, 0.22),
                res=(760, 760), lens=80)
    # Rule 2, the standing test: if he stops reading as hat + robe + staff here,
    # a change has regressed the silhouette regardless of how good the detail is.
    # Bust crop, ~1.05 m of coverage centred on the hat and beard. The first
    # framing was pulled much further back and spent most of the 184 px on empty
    # background, which makes the legibility test easier than the real icon and
    # therefore useless.
    render_view("icon_184", (-1.20, -1.35, 2.05), target=(-0.10, 0.0, 1.85),
                res=(184, 184), lens=62)
    render_view("icon_full_184", (-3.25, -4.05, 1.85), target=(0, 0, 1.30),
                res=(184, 184), lens=52)

    # ORBIT CELLS - the judged stimulus. Generated by _tools/orbit.py from a per-wave
    # seed and delivered through the variant hook as EXTRA_VIEWS, so a plain CLI run
    # renders nothing extra and every named view above is untouched. Additive on
    # purpose: the old views keep working while the new stimulus is proven.
    #
    # Every cell carries its own rig_yaw so the lighting follows the bearing. The
    # camera distance and aim height are per-ASSET constants, never fitted to the
    # candidate: fitting each build to the frame would hide a change in proportion,
    # which is the single thing most worth judging.
    #
    # This block, set_rig_yaw() and render_mask() were PORTED from main's
    # blender_mage000.py on 2026-08-10. This file's ancestor (branch model/mage000)
    # carries the accepted geometry but branched before the v4 orbit harness landed,
    # so it could not render the judged stimulus at all - every wave would have died
    # with "no .png was produced". Do not assume a script inherited from an older
    # accepted branch is v4-ready just because it conforms; conformance is the hook
    # marker, orbit-readiness is these three pieces.
    for _spec in (globals().get("EXTRA_VIEWS") or []):
        render_view(_spec["name"], tuple(_spec["cam_loc"]),
                    target=tuple(_spec.get("target", (0, 0, 1.30))),
                    res=tuple(_spec.get("res", (900, 1300))),
                    lens=_spec.get("lens", 62),
                    samples=_spec.get("samples"),
                    rig_yaw=_spec.get("rig_yaw"),
                    mask=_spec.get("mask", True))

if DO_EXPORT:
    export_fbx()
