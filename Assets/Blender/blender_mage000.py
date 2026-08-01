"""
Gloomfell - THE MAGE  (hero type code `mage000`)

Procedural build of the second hero. Nothing here inherits from the imported
`char_mage.fbx` in Assets/Models - that is an asset-pack placeholder and is not
this character.

Design source: Obsidian/TD/Heroes/Mage.md
  - broad-brimmed wizard hat, face lost in its shadow
  - long pale beard, the only thing that escapes the shadow
  - midnight-blue silk robe worn LOOSELY: open front, bell sleeves, flared hem
  - silver trim on every edge          - near-black under-robe and linings
  - gnarled blackwood staff planted point-down, taller than he is
  - a large violet gem crested on top in a silver claw setting

Modelling rules this is built around (see .claude/skills/blender-model-mode):
  1. NOTHING LEVITATES. Every part touches or overlaps another. The audit in
     _mage000/audit_mage000.py fails the build if one does not. Several numbers
     below look arbitrary and are not - they are what makes two surfaces meet.
     The comments say so where that is the case.
  2. SILHOUETTE FIRST. Hat + flared robe + staff-with-gem must name him at
     184x184 with every interior detail gone.
  3. TRIM DRAWS THE FORM. Silver piping outlines the hem, the front opening, the
     cuffs, the mantle and the hat band, so the internal lines survive
     downscaling. Blue-on-blue alone flattens to a blob.
  4. DARK RECESSES. Face void, robe opening, sleeve interiors and under-brim all
     use a near-black material, so the gem has something to glow against.
  5-9. Rounded forms only. Everything here is a lathe, a loft or a swept tube.
     There is not a single cube in this file, which is the easiest way to obey
     "never visible cubes".

Run headless:   blender -b -P Assets/Blender/blender_mage000.py -- save export render
Preview:        python Assets/Blender/_tools/preview.py mage000 --variants v.json

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
from math import radians, sin, cos, pi
from mathutils import Vector, Matrix

# -- Paths ---------------------------------------------------------------------
BLEND_PATH = r"C:\Users\LachlanB\TD\Assets\Blender\mage000.blend"
FBX_PATH   = r"C:\Users\LachlanB\TD\Assets\Models\mage000.fbx"
RENDER_DIR = r"C:\Users\LachlanB\TD\Assets\Blender\_mage000"


def _flag(name, default=False):
    """Flags come from either of the two ways this file gets run:
    headless   -> blender -b -P blender_mage000.py -- save export render
    in-session -> set the name in the namespace before exec'ing the file
    """
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return globals().get(name, default) or name.replace("DO_", "").lower() in argv


DO_RENDER = _flag("DO_RENDER")
DO_EXPORT = _flag("DO_EXPORT")
DO_SAVE   = _flag("DO_SAVE")

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
WRIST_R    = Vector((-0.438, -0.109, 1.090))

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
# Brim cross-section, (radius, z relative to Z_BRIM), traced out along the top
# and back along the underside. close_profile wraps it into a manifold shell.
# The first entry is deliberately INSIDE the head sphere - that intersection is
# the whole reason the hat is not a levitating part.
BRIM_PROFILE = [
    (0.082,  0.014),
    (0.140,  0.000),
    (0.200, -0.020),
    (0.262, -0.048),
    (0.318, -0.096),
    (0.348, -0.142),      # outer edge, drooping
    (0.343, -0.160),      # rolled under
    (0.300, -0.122),
    (0.235, -0.076),
    (0.170, -0.040),
    (0.096, -0.010),
]
BRIM_WAVE = 0.028         # the brim is cloth, not a dinner plate. At 0.012 it
                          # still read as a rigid disc.

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
GRIP_T0, GRIP_T1 = 0.36, 0.60
GRIP_TURNS  = 36          # over the 0.55 m of shaft between GRIP_T0 and GRIP_T1.
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
GEM_PROFILE = [
    (0.00, -0.78),        # pavilion point, in units of GEM_R
    (0.52, -0.46),
    (0.86, -0.16),
    (1.00,  0.00),        # girdle - the widest line
    (0.95,  0.20),
    (0.80,  0.52),
    (0.52,  0.86),
    (0.26,  1.06),
    (0.00,  1.16),        # table
]
GEM_FACETS    = 8

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
# The robe's base colour is a three-stop fresnel ramp, not a single value.
# C_ROBE is what faces you; C_ROBE_EDGE is the extreme grazing angle.
C_ROBE      = (0.008, 0.011, 0.046, 1.0)
C_ROBE_MID  = (0.038, 0.030, 0.150, 1.0)
C_ROBE_EDGE = (0.175, 0.310, 0.470, 1.0)
# The hem band, sash and hatband run the same shift a stop darker, so they stay
# readable as a separate, deeper cloth instead of merging with the robe.
C_ROBE_D      = (0.005, 0.007, 0.028, 1.0)
C_ROBE_D_MID  = (0.024, 0.019, 0.096, 1.0)
C_ROBE_D_EDGE = (0.120, 0.215, 0.330, 1.0)
# How fast the ramp turns. Lower = the bright edge is confined to a narrower
# rim, which keeps the overall figure dark; at 0.5 the whole robe lifts and the
# point of a dark base is lost.
PEARL_BLEND = 0.30
# Thin-film interference - a soap-bubble layer over the silk. This is the actual
# iridescence: the fresnel ramp alone shifts colour with angle, but thin film
# shifts the HIGHLIGHT's hue too, which is what stops the shimmer reading as a
# simple two-tone gradient. ~430 nm lands the break in the violet/cyan band we
# want; ~550 nm swings it green and fights the gem.
FILM_T   = 430.0
FILM_IOR = 1.92

C_ROBE_IN  = (0.003, 0.004, 0.014, 1.0)
# Silver as a cold mirror. At roughness 0.06 it is mostly reflecting the dark
# world rather than generating its own value, which is precisely what makes it
# read as precious metal instead of grey paint - a rough silver has to be lit to
# look like anything, and this one does not.
C_SILVER   = (0.925, 0.945, 0.985, 1.0)
C_SILVER_D = (0.400, 0.435, 0.520, 1.0)
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
C_HAIR     = (0.252, 0.262, 0.298, 1.0)   # pale, but GREY rather than white. The
                                          # beard is a broad, fully-lit surface
                                          # right under the key, so it renders
                                          # far lighter than its base value
                                          # suggests - at 0.46 it was the
                                          # brightest thing in frame and pulled
                                          # the eye off the gem entirely.
C_SKIN     = (0.268, 0.192, 0.158, 1.0)   # weathered and old. Brighter than
                                          # this and the hands are the lightest
                                          # thing on the model after the beard,
                                          # and the eye goes to them instead of
                                          # to the gem.
C_GEM      = (0.098, 0.008, 0.360, 1.0)
C_GEM_EM   = (0.430, 0.055, 1.000, 1.0)
GEM_EMIT   = 0.10         # AgX desaturates bright emitters toward WHITE, so
                          # cranking this makes the gem paler, not more violet.
                          # At 2.2 it rendered as a pale pink egg. There is a
                          # second reason to keep it low that only appeared once
                          # the stone was faceted: emission lights every facet
                          # equally, so a strong emitter erases the facet-to-
                          # facet contrast that makes a cut stone read as cut at
                          # all, and the gem goes back to being a flat purple
                          # blob. The glow has to come from saturated colour and
                          # specular against a dark setting, not from intensity.

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


def add_pearl_shift(mat, core, mid, edge, blend=PEARL_BLEND, interp="EASE"):
    """Shot silk: drive Base Color from a viewing-angle ramp.

    This is what makes silk shimmer rather than just look shiny. The cloth
    changes HUE as it turns away from the camera, so every fold reads as a
    different colour instead of the same blue at a different brightness - which
    is exactly what a fold in real silk does, and what no amount of specular
    will fake. Layer Weight's Fresnel output is ~0 face-on, ~1 at grazing.

    Three stops, not two: a straight core-to-edge blend passes through the
    midpoint of the two colours, and the midpoint of near-black and cyan is a
    muddy slate. The mid stop is what keeps the transition through violet.

    NOTE this is a render-time material and does NOT survive the FBX export -
    FBX carries a single flat colour per material. mat.diffuse_color is set to
    the mid stop so Unity and the solid viewport get the most representative
    single value; matching the shimmer in-engine is a shader job for whoever
    builds the prefab.
    """
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.location = (-620, 180)
    lw.inputs["Blend"].default_value = blend
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-420, 180)
    cr = ramp.color_ramp
    cr.interpolation = interp
    cr.elements[0].position = 0.0
    cr.elements[0].color = core
    cr.elements[1].position = 1.0
    cr.elements[1].color = edge
    cr.elements.new(0.55).color = mid
    nt.links.new(lw.outputs["Fresnel"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    mat.diffuse_color = mid
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


# Sheen is what separates silk from painted plastic. It is also the single
# easiest thing to overdo: at 0.80 it laid a bright white fresnel over the whole
# garment and a robe with a base value of 0.03 rendered as pale lavender. Sheen
# gives the material its FIBRE, it is not the lighting - keep it low and let the
# base colour stay dark.
M_ROBE    = make_material("MageRobe",    C_ROBE,    0.0, 0.300, sheen=0.38,
                          sheen_tint=(0.60, 0.55, 1.00, 1.0), coat=0.30,
                          coat_roughness=0.10, specular=0.70,
                          film_thickness=FILM_T, film_ior=FILM_IOR)
add_pearl_shift(M_ROBE, C_ROBE, C_ROBE_MID, C_ROBE_EDGE)
M_ROBE_D  = make_material("MageRobeDeep", C_ROBE_D, 0.0, 0.360, sheen=0.36,
                          coat=0.24, film_thickness=380.0, film_ior=FILM_IOR)
add_pearl_shift(M_ROBE_D, C_ROBE_D, C_ROBE_D_MID, C_ROBE_D_EDGE)
# The lining stays matt and dark. It is rule 4's job - something for the gem to
# glow against - and a second shimmering silk in the robe's opening would take
# that away.
M_ROBE_IN = make_material("MageRobeLining", C_ROBE_IN, 0.0, 0.780, sheen=0.14)
M_SILVER  = make_material("MageSilver",  C_SILVER,  1.0, 0.062, anisotropic=0.55,
                          specular=0.90)
M_SILVER_D = make_material("MageSilverDark", C_SILVER_D, 1.0, 0.260,
                           anisotropic=0.35)
M_VOID    = make_material("MageVoid",    C_VOID,    0.0, 1.000)
M_WOOD    = make_material("MageStaffWood", C_WOOD,  0.0, 0.700, specular=0.50)
add_grain_glow(M_WOOD, C_WOOD_VEIN, WOOD_VEIN_EMIT, scale=40.0)
M_WOOD_L  = make_material("MageStaffWoodPale", (0.058, 0.058, 0.098, 1.0),
                          0.0, 0.620)   # same cooling as C_WOOD, same luminance
add_grain_glow(M_WOOD_L, C_WOOD_VEIN_L, WOOD_VEIN_EMIT_L, scale=54.0)
M_LEATHER = make_material("MageLeather", (0.048, 0.034, 0.026, 1.0), 0.0, 0.820)
# Parchment is the one warm, light thing on the model besides the hands. Kept
# well below the beard's value so it reads as a detail, not a second focal point.
M_PARCH   = make_material("MageParchment", (0.205, 0.178, 0.138, 1.0), 0.0, 0.880)
M_HAIR    = make_material("MageHair",    C_HAIR,    0.0, 0.640, sheen=0.40,
                          sheen_tint=(0.78, 0.80, 1.00, 1.0))
M_SKIN    = make_material("MageSkin",    C_SKIN,    0.0, 0.700)

# The gem is the only light source on the model and the hero's whole colour
# identity. Transmission + a low-weight coat give it depth without the white
# specular veil that turned the knight's rubies into pink plastic.
M_GEM     = make_material("MageGem", C_GEM, 0.0, 0.032,
                          emission=C_GEM_EM, emission_strength=GEM_EMIT,
                          transmission=0.68, coat=0.60)
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
                   mat=M_SILVER, u=12, v=8,
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

    sweep("Robe_HemBand", rings[-1][::2], TRIM_R * 1.1, M_SILVER, segs=8)


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
               mat=M_SILVER, u=20, v=12)
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
               scale=(1.0, 1.0, 0.6), mat=M_SILVER, u=12, v=8,
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
        add_sphere("Shoulder_" + tag,
                   (sgn * 0.240, -0.010, 1.458), 0.106,
                   scale=(1.00, 0.74, 0.82), mat=M_ROBE, u=24, v=14)
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


def _rot_about(axis, angle):
    return Matrix.Rotation(angle, 3, axis)


def build_palm(name, centre, across, thick, along, size):
    """A flattened rounded block - the palm.

    A sphere was the first attempt and it reads as an egg with sausages attached,
    because a hand's defining feature is that it is FLAT: wide across the
    knuckles, thin front to back. The superellipse power squares the section off
    just enough to give the back of the hand a plane for light to sit on.
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
    ob = loft(name, rings, mat=M_SKIN, closed=True,
              cap_start=True, cap_end=True)
    return ob


def build_digit(name, pts, r0, r1, knuckles=3.0, flat=0.86):
    """A finger: tapered, slightly flattened, and bulged at the knuckles.

    The bulges are the whole point. A smooth tapered tube is a sausage; three
    swellings along its length are what make it read as jointed at the size the
    game actually shows the hands at.
    """
    def ring(t, a):
        r = lerp(r0, r1, t) * (1.0 + FINGER_KNUCKLE * sin(pi * t * knuckles) ** 2)
        return (r * cos(a), r * flat * sin(a))
    return sweep_fn(name, pts, ring, M_SKIN, segs=10)


def build_grip_hand(tag, centre, axis, out_dir, shaft_r):
    """A fist closed around a cylinder of radius `shaft_r`.

    Fingers are swept along arcs measured around the shaft axis, so they wrap the
    staff instead of being parked near it. `out_dir` points from the shaft back
    toward the wrist.
    """
    axis = Vector(axis).normalized()
    out_dir = (Vector(out_dir) - axis * Vector(out_dir).dot(axis)).normalized()
    side = axis.cross(out_dir).normalized()
    centre = Vector(centre)

    # Back of the hand faces outward; the palm plate wraps the shaft.
    palm_c = centre + out_dir * (shaft_r + 0.030)
    build_palm("Palm_" + tag, palm_c, axis, out_dir, side,
               (0.062, 0.026, 0.052))

    for k in range(4):
        # Index nearest the top of the grip, little finger lowest, and the
        # outer two shorter - a hand where all four fingers are the same length
        # reads as a mitten.
        z_off = (1.42 - k) * 0.027
        length = (0.94, 1.03, 1.00, 0.88)[k]
        base = centre + axis * z_off
        a0, a1 = radians(16.0), radians(16.0 + 150.0 * length)
        n = 7
        pts = []
        for i in range(n):
            t = i / (n - 1)
            a = lerp(a0, a1, t)
            # The fingertip tucks in toward the shaft as it curls. These offsets
            # are smaller than the finger radius on purpose, so the finger
            # surface bites into the shaft rather than hovering beside it.
            rr = shaft_r + lerp(0.013, 0.004, t)
            pts.append(base + (_rot_about(axis, a) @ out_dir) * rr)
        build_digit("Finger_%s%d" % (tag, k), pts, 0.0145, 0.0098)

    # Thumb lies ALONG the shaft across the backs of the fingers, which is how a
    # hand actually holds a staff. Wrapped round with the fingers it interlocks
    # with them and reads as a fifth finger.
    t0 = centre + axis * (-0.058) + out_dir * (shaft_r + 0.020)
    pts = [t0,
           t0 + axis * 0.030 + (_rot_about(axis, radians(-26.0)) @ out_dir) * 0.008,
           t0 + axis * 0.058 + (_rot_about(axis, radians(-44.0)) @ out_dir) * 0.012,
           t0 + axis * 0.080 + (_rot_about(axis, radians(-56.0)) @ out_dir) * 0.010]
    build_digit("Thumb_" + tag, pts, 0.0175, 0.0115, knuckles=2.0)


def build_open_hand(tag, wrist, fwd, up):
    """Relaxed open hand, fingers slightly curled. His left, held forward - the
    natural place for a future cast VFX attach point."""
    wrist = Vector(wrist)
    fwd = Vector(fwd).normalized()
    up = (Vector(up) - fwd * Vector(up).dot(fwd)).normalized()
    side = fwd.cross(up).normalized()

    palm_c = wrist + fwd * 0.046
    build_palm("Palm_" + tag, palm_c, side, up, fwd, (0.060, 0.023, 0.056))

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
        build_digit("Finger_%s%d" % (tag, k), pts, 0.0145, 0.0098)

    t0 = palm_c + side * 0.044 - fwd * 0.006
    pts = [t0,
           t0 + fwd * 0.024 + side * 0.014 - up * 0.006,
           t0 + fwd * 0.046 + side * 0.024 - up * 0.016,
           t0 + fwd * 0.062 + side * 0.030 - up * 0.026]
    build_digit("Thumb_" + tag, pts, 0.0175, 0.0115, knuckles=2.0)


def build_arms():
    set_side("R")
    build_sleeve("R", SHOULDER_R, ELBOW_R, WRIST_R, SLEEVE_END_R,
                 SLEEVE_FLARE_R)
    build_forearm("R", ELBOW_R, WRIST_R)
    # The grip is taken from the staff spine, not from a hand-authored point, so
    # re-posing the staff carries the hand with it.
    tan = (Vector(STAFF_SPINE[4]) - Vector(STAFF_SPINE[2])).normalized()
    build_grip_hand("R", GRIP_C, tan, Vector((1.0, 0.15, 0.0)), GRIP_R)

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


def build_hat():
    """Brim + crown + band, the whole assembly cocked over to his left.

    The chain that keeps this off the levitation list is: the brim's inner ring
    sits inside the head sphere, and the crown's lower wall sits inside the
    brim's inner ring. Change BRIM_PROFILE[0] or HAT_TILT and check the audit.
    """
    brim = revolve("Hat_Brim", BRIM_PROFILE, segments=52, mat=M_ROBE,
                   origin=hat_xf((0.0, 0.0, Z_BRIM)), close_profile=True,
                   radial_fn=lambda a: BRIM_WAVE * sin(3.0 * a))
    brim.rotation_euler = (0.0, HAT_TILT, 0.0)

    # Under the brim is a RECESS. Rule 4 lists it, and so does the doc, by name.
    # One lathe is one material, so the return half of the profile - the run back
    # from the outer roll toward the head, which is the surface directly over the
    # face - is switched to the lining slot instead. Left as silk it catches the
    # fill and lifts the very shadow the hat exists to cast, which is the hat's
    # first job in the brief. Hat_Void below only covers the inner 10 cm; the
    # brim reaches 35.
    me = brim.data
    lining_idx = len(me.materials)
    me.materials.append(M_ROBE_IN)
    # Which way the lathe winds - and so the sign of every normal - depends on
    # the direction the profile runs, so deduce it from the polygon at the very
    # top of the brim rather than assuming it.
    facing = 1.0 if max(me.polygons, key=lambda p: p.center.z).normal.z > 0 \
        else -1.0
    for p in me.polygons:
        # The outer roll is near-vertical and stays silk, which is what keeps the
        # rim reading as the edge of a felt hat rather than as a painted band.
        if p.normal.z * facing < -0.25:
            p.material_index = lining_idx

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

    sweep_fn("Hat_Crown", spine, ring, M_ROBE, segs=30)

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
               mat=M_SILVER, u=16, v=10, rot=(0.0, HAT_TILT, 0.0))
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
    revolve("Staff_Seat", [(r * GEM_R, z * GEM_R) for r, z in seat],
            segments=GEM_FACETS * 2, mat=M_SILVER, origin=GEM_C)

    # -- the stone ------------------------------------------------------------
    revolve("Staff_Gem", [(r * GEM_R, z * GEM_R) for r, z in GEM_PROFILE],
            segments=GEM_FACETS, mat=M_GEM, origin=GEM_C, smooth=False)


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
    for attr, val in (("taa_render_samples", 96), ("use_raytracing", True),
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


def render_view(name, cam_loc, target=(0, 0, 1.30), res=(900, 1300), lens=62,
                samples=None):
    # A preview run renders a cheap subset rather than all of them. RENDER_ONLY
    # unset (the normal case) means "render everything", so a plain
    # `blender -b -P blender_mage000.py -- render` is unaffected.
    only = globals().get("RENDER_ONLY")
    if only is not None and name not in only:
        return
    cam = SCENE.camera
    cam.location = cam_loc
    cam.rotation_euler = look_at_euler(cam_loc, target)
    cam.data.lens = lens
    SCENE.render.resolution_x, SCENE.render.resolution_y = res
    scale = globals().get("SAMPLE_SCALE", 1.0)
    if samples and hasattr(SCENE.eevee, "taa_render_samples"):
        SCENE.eevee.taa_render_samples = max(16, int(samples * scale))
    os.makedirs(RENDER_DIR, exist_ok=True)
    SCENE.render.filepath = os.path.join(RENDER_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", SCENE.render.filepath)


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

if DO_EXPORT:
    export_fbx()
