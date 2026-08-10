"""
Gloomfell - THE GOOD DOCTOR  (hero type code `plague000`)

Procedural build of the third hero. BLOCKOUT STAGE - proportions, silhouette,
palette and cameras are in place; surface detail is deliberately absent and is
the modelling pipeline's job.

Design source: Obsidian/TD/Heroes/Good Doctor.md
  - short, wide, HUNCHED FORWARD under the weight on his back
  - a long down-curved beaked mask, brass-ringed, two blank glass lenses
  - a waxed canvas hood, open at the front, NO BRIM (the brim is the mage's)
  - a copper still strapped to his back: boiler, firebox, swan-neck condenser
    over the right shoulder, stub chimney over the left
  - a censer on a chain in his right hand, swinging low and off the vertical
  - a glass flask in his left
  - bilious green as the only accent, emitted from firebox / censer / flask

This hero exists to be DIFFERENT IN MASS AND MATERIAL from the other two, not
merely differently dressed. The knight is steel and gold and upright; the mage is
silk and silver and upright; this one is copper, brass, glass and tarred leather,
and he leans. If a change makes him taller, more symmetric or more vertical, it
is moving him toward the other two and is probably wrong.

Modelling rules this is built around (shared with knight000 / mage000):
  1. NOTHING LEVITATES. Every part touches or overlaps another. There is no audit
     script for this asset yet, so that is currently true by construction rather
     than by measurement - see "Known gaps" in the design doc. Numbers below that
     look arbitrary usually are not; they are what makes two surfaces meet, and
     the comments say so where that is the case.
  2. SILHOUETTE FIRST. Beak + back-mounted still + swinging censer must name him
     at 184x184 with every interior detail gone.
  3. TRIM DRAWS THE FORM. Brass rings, strap edges and copper bands outline the
     masses so the internal lines survive downscaling. Black-on-black flattens.
  4. DARK RECESSES. Hood interior, coat lining, beak underside and the firebox
     surround are near-black, so the green has something to glow against.
  5-9. Rounded forms only. Everything here is a lathe, a loft or a swept tube.
     There is not a single cube in this file.

Run headless:   blender -b -P Assets/Blender/blender_plague000.py -- save export render
Preview:        python Assets/Blender/_tools/preview.py plague000 --variants v.json

Conventions (shared with blender_knight000.py / blender_mage000.py):
  * He faces -Y (Blender's front orthographic view). So:
        forward = -Y     back = +Y     his right = -X     his left = +X
    With the export axes at the bottom of the file this lands facing +Z in Unity.
  * Z-up, origin on the ground between the feet. ~1.64 to the crown of the hood,
    ~2.04 to the chimney cowl, which is the tallest point on the model.
  * Modifiers are left LIVE, never applied: they survive into the FBX (the
    exporter evaluates the depsgraph), they keep the .blend editable, and
    bpy.ops.mesh.bevel needs a 3D-viewport context that does not exist under
    `blender -b`. Everything is built with bmesh.ops + modifiers instead, both of
    which are entirely context-free.
"""

import bpy
import bmesh
import math
import os
from math import radians, sin, cos, pi
from mathutils import Vector, Matrix

# -- Paths ---------------------------------------------------------------------
BLEND_PATH = r"C:\Users\LachlanB\TD\Assets\Blender\plague000.blend"
FBX_PATH   = r"C:\Users\LachlanB\TD\Assets\Models\plague000.fbx"
RENDER_DIR = r"C:\Users\LachlanB\TD\Assets\Blender\_plague000"


def _flag(name, default=False):
    """Flags come from either of the two ways this file gets run:
    headless   -> blender -b -P blender_plague000.py -- save export render
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
# ALWAYS set per view rather than inherited - see render_view(). A view that
# silently inherits the previous view's sample count makes pixel measurements
# across runs with different view sets non-comparable, and modellers are asked to
# measure from rendered pixels.
BASE_SAMPLES = 96

# ==============================================================================
#  SKELETON + TUNABLES
#
#  Every value the shape depends on lives here as a module-level global, which is
#  what makes the file drivable by _tools/preview.py: a variant can override any
#  of them without touching the source.
# ==============================================================================

Z_GROUND   = 0.008        # not 0.0: solidify and bevel both nudge boundary verts
                          # downward. 8 mm is invisible at 1.7 m and leaves margin.
Z_ANKLE    = 0.105
Z_KNEE     = 0.430
Z_HIP      = 0.845
Z_WAIST    = 0.965
Z_CHEST    = 1.225
Z_SHOULDER = 1.305
Z_NECK     = 1.395
Z_HEAD     = 1.505        # head centre
Z_CROWN    = 1.640        # top of the hood - the tallest point ON HIM. The
                          # chimney goes higher, but the chimney is cargo.

# The forward lean. This is load-bearing and not a pose note: it is what sells the
# weight of the pack and it is most of what distinguishes his silhouette from two
# upright heroes. Applied as a y-offset that grows with height above the hip, so
# the legs stay planted and everything above the belt pitches forward together.
#
# The exponent matters as much as the coefficient. At 1.0 the lean is a straight
# shear and reads as a figure leaning against a wall; above ~1.5 the whole
# curvature lands in the shoulders and he reads as a hunchback rather than as
# someone carrying something. 1.4 puts the bend across the whole back.
LEAN_K   = 0.240
LEAN_POW = 1.400

HEAD_R     = 0.098
HEAD_SCALE = (1.00, 1.05, 1.08)

# -- Body cross-section --------------------------------------------------------
# ELLIPTICAL, not circular. A torso as deep as it is wide has no shoulder - it is
# a cone, and the arms read as tubes rammed into its side. This is the mage's
# hardest-won structural lesson and it transfers unchanged.
BODY_DEPTH = 0.800

# (z, radius across X, fold amplitude). The coat is a heavy waxed bell: widest at
# the hem where it pools, pinched at the waist under the pack straps, and swelling
# again across the chest.
COAT_TABLE = [
    (0.008, 0.396, 0.026),
    (0.160, 0.416, 0.030),    # the pool. Wider than the hem itself, so the cloth
                              # reads as resting ON the ground, not cut off by it.
    (0.340, 0.374, 0.026),
    (0.600, 0.340, 0.022),
    (0.845, 0.312, 0.018),
    (0.965, 0.300, 0.015),    # waist, under the strap
    (1.100, 0.318, 0.013),
    (1.225, 0.336, 0.011),    # chest
    (1.305, 0.330, 0.009),    # shoulder
    (1.395, 0.212, 0.007),    # neck
]

# Fold parameters. Cusped, not sinusoidal: heavy waxed canvas hangs in broad flat
# ridges separated by narrow valleys, and a sine is symmetric and rounded at both
# extremes so it reads as a smooth sheet. The second harmonic at a different pitch
# is what stops evenly-pitched folds reading as corrugated metal.
FOLD_LOBES  = 9
FOLD_POWER  = 0.340
FOLD_MEAN   = 0.520
FOLD_SKEW   = 0.300
FOLD_PHASE  = 0.700
FOLD_TWIST  = 0.550
FOLD_LOBES2 = 17
FOLD_TWIST2 = -0.900
FOLD_FINE   = 0.380

THETA_FRONT = -pi / 2.0   # front centreline: he faces -Y
THETA_BACK  = pi / 2.0

# -- The beak ------------------------------------------------------------------
# Silhouette feature 1. Points FORWARD (-Y), into the axis neither other hero
# uses, and curves DOWN over its length - a straight cone reads as a party hat on
# its side. Offsets are relative to the head centre.
BEAK_SPINE = [
    (0.000, -0.062,  0.008),
    (0.000, -0.148, -0.004),
    (0.000, -0.222, -0.040),
    (0.000, -0.270, -0.098),
    (0.000, -0.286, -0.152),
]
BEAK_RADII = [0.064, 0.052, 0.040, 0.025, 0.009]

# -- Goggles -------------------------------------------------------------------
GOG_X    = 0.052          # half-separation
GOG_Y    = -0.074         # forward of the head centre
GOG_Z    = 0.032          # above it
GOG_R    = 0.036          # lens radius (the brass rim is built around this)

# -- The still -----------------------------------------------------------------
# Silhouette feature 2. Y_STILL is the one number that decides whether the pack
# reads as strapped ON or floating BEHIND: the coat's back surface at chest height
# sits at y = lean(1.225) + 0.336*BODY_DEPTH = 0.207, and the boiler at 0.285 with
# a max radius of 0.212 spans y 0.073..0.497. The overlap is deliberate.
Y_STILL   = 0.285
Z_BOILER  = 1.150         # boiler centre
Z_FIREBOX = 0.880         # firebox centre, slung under it

CHIMNEY_SPINE = [
    (0.020, 0.278, 1.392),
    (0.062, 0.252, 1.600),
    (0.104, 0.214, 1.800),
    (0.136, 0.186, 1.950),
    (0.150, 0.172, 2.040),
]
CHIMNEY_RADII = [0.052, 0.046, 0.042, 0.039, 0.037]

# The swan neck. Leaves the boiler top, arcs over his RIGHT shoulder (-X) and
# comes down to a spout on the right of the chest. Opposite side from the chimney
# on purpose: one thing over each shoulder is what makes the pack read as a rig
# rather than as a lump.
SWAN_SPINE = [
    (-0.048, 0.282, 1.386),
    (-0.162, 0.278, 1.462),
    (-0.256, 0.198, 1.438),
    (-0.292, 0.058, 1.336),
    (-0.272, -0.086, 1.218),
    (-0.226, -0.158, 1.118),
]
SWAN_RADII = [0.031, 0.028, 0.026, 0.024, 0.023, 0.022]

COIL_CENTRE = (-0.196, 0.300, 1.045)
COIL_TURNS  = 3.0
COIL_R      = 0.074
COIL_ADV    = 0.030       # per turn, along +X
COIL_TUBE   = 0.016

# -- Hands and the censer ------------------------------------------------------
HAND_R_POS = Vector((-0.316, -0.176, 0.858))   # right hand, hanging, holds chain
HAND_L_POS = Vector(( 0.262, -0.238, 1.062))   # left hand, up, holds the flask

# Silhouette feature 3. The censer hangs OUT and FORWARD of the hand, not below
# it: a plumb-vertical chain reads as a dropped object, and the whole point of
# this hero's signature is a pendulum caught mid-arc. It also puts an asymmetric
# mass down near the feet, where both other heroes are empty.
CENSER_POS = Vector((-0.402, -0.362, 0.424))
CENSER_R   = 0.076

# -- Palette knobs -------------------------------------------------------------
# Emission strengths are LOW on purpose. Above ~0.5 the AgX view transform
# desaturates emitters toward white, so cranking the green makes it paler, not
# sicker - the knight's rubies learned this at 0.9 and read as pink plastic.
# The firebox is the exception: it sits inside a near-black shroud, and a recess
# that dark can carry far more before it blows out.
GLOW_EMIT = 0.340         # censer seams, vial rack
FIRE_EMIT = 1.500         # firebox grate, deep in shadow
TONIC_EMIT = 0.300        # the flask
LENS_EMIT = 0.220         # the fog behind the goggles

# ==============================================================================
#  SCENE
# ==============================================================================

# read_homefile rather than read_factory_settings: identical result for our
# purposes and read_factory_settings is blocked inside the MCP sandbox.
bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)

SCENE = bpy.context.scene
COL_HERO = bpy.data.collections.new("GoodDoctor")
COL_RIG  = bpy.data.collections.new("PreviewRig")
for c in (COL_HERO, COL_RIG):
    bpy.context.collection.children.link(c)


# ==============================================================================
#  MATERIALS
#
#  make_material() is lifted verbatim from blender_mage000.py. Socket-name
#  guarding and the thin-film pairing rule in it are both load-bearing.
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

# ==============================================================================
#  PALETTE - "copper and contagion"
#
#  The governing idea, inherited from the mage's palette work: richness comes
#  from angle-dependent metal and saturated recesses, NOT from raising base
#  values. Every dielectric base colour here is deliberately low. The one thing
#  this figure cannot spare is contrast against its green, and a coat lifted to
#  "readable" grey spends exactly that.
#
#  The metals do the drawing. Copper and brass are the trim that keeps the
#  internal lines alive at 184x184 (rule 3), which on this hero means the boiler
#  bands, the beak ring, the goggle rims and the censer - not piping on the coat.
# ==============================================================================

# Tarred waxed leather: the coat, the beak, the straps, the boots. Base value
# 0.030 looks impossibly dark written down and renders correctly - it is a
# saturated black-brown that only shows its colour where the key rakes across it.
C_LEATHER    = (0.030, 0.026, 0.023, 1.0)
# One step up for anything that must separate FROM the coat while still being
# leather: strap edges, the beak ring's seat, cuffs. Value, not hue, does the
# separating - a browner strap on a black coat reads as a stain.
C_LEATHER_HI = (0.056, 0.047, 0.040, 1.0)
# Rule 4. Hood interior, coat lining, beak underside, firebox shroud.
C_DARK       = (0.010, 0.011, 0.010, 1.0)
# Ash-grey waxed canvas: the hood and the apron. The only mid-value on the model,
# and it is what stops the whole figure reading as one black mass.
C_CANVAS     = (0.098, 0.094, 0.082, 1.0)

# Copper: warm like the knight's gold and unmistakably NOT it. Gold is wealth;
# this is equipment. Hammered, so roughness is high for a metal and anisotropy
# gives it a forged streak rather than a mirror.
C_COPPER     = (0.560, 0.235, 0.110, 1.0)
C_COPPER_D   = (0.230, 0.105, 0.052, 1.0)   # shadowed / older copper
C_BRASS      = (0.640, 0.470, 0.170, 1.0)   # rings, rims, fittings
C_IRON       = (0.048, 0.050, 0.052, 1.0)   # firebox, chain, buckles
# Verdigris. Dielectric, not metal - patina is a crust, and rendering it metallic
# is what makes fake-aged copper look like green chrome. It also quietly bridges
# the copper to the green accent so the accent does not read as a sticker.
C_VERDI      = (0.075, 0.230, 0.175, 1.0)

C_GLASS      = (0.600, 0.720, 0.620, 1.0)   # lenses, flask, vials
C_TONIC      = (0.220, 0.720, 0.180, 1.0)   # whatever is in the flask
C_GLOW       = (0.320, 1.000, 0.260, 1.0)   # THE accent. Every VFX inherits it.
C_BONE       = (0.300, 0.290, 0.250, 1.0)   # bandage, cord, paper labels


M_LEATHER = make_material("DocLeather", C_LEATHER, 0.0, 0.580,
                          sheen=0.12, specular=0.35)
M_LEATHER_HI = make_material("DocLeatherHi", C_LEATHER_HI, 0.0, 0.440,
                             sheen=0.10, coat=0.12)
M_DARK    = make_material("DocDark", C_DARK, 0.0, 0.860)
M_CANVAS  = make_material("DocCanvas", C_CANVAS, 0.0, 0.760, sheen=0.28)

# Roughness 0.30 with anisotropy 0.45: at this roughness it mostly reflects the
# dark world rather than generating its own value, which is what reads as beaten
# metal instead of orange paint.
M_COPPER  = make_material("DocCopper", C_COPPER, 1.0, 0.300,
                          anisotropic=0.450, anisotropic_rotation=0.15)
M_COPPER_D = make_material("DocCopperDark", C_COPPER_D, 1.0, 0.520,
                           anisotropic=0.300)
M_BRASS   = make_material("DocBrass", C_BRASS, 1.0, 0.220, anisotropic=0.350)
M_IRON    = make_material("DocIron", C_IRON, 1.0, 0.460)
M_VERDI   = make_material("DocVerdigris", C_VERDI, 0.0, 0.720)

# Transmission plus a coat gives glass depth without the white specular veil that
# turned the knight's rubies into pink plastic.
M_GLASS   = make_material("DocGlass", C_GLASS, 0.0, 0.060,
                          transmission=0.920, coat=0.400)
# The lenses are the face. Faint green fog BEHIND flat glass - emission low, so
# they read as something reflecting rather than something shining. The knight
# took the glow and the mage took the void; this is the third answer.
M_LENS    = make_material("DocLens", C_GLASS, 0.0, 0.055,
                          emission=C_GLOW, emission_strength=LENS_EMIT,
                          transmission=0.760, coat=0.550)
M_TONIC   = make_material("DocTonic", C_TONIC, 0.0, 0.120,
                          emission=C_TONIC, emission_strength=TONIC_EMIT,
                          transmission=0.500, coat=0.300)
# The brightest green on the model, and the only one allowed to be. Three equally
# bright greens and the eye has nowhere to land.
M_FIRE    = make_material("DocFirebox", C_GLOW, 0.0, 0.300,
                          emission=C_GLOW, emission_strength=FIRE_EMIT)
M_GLOW    = make_material("DocGlow", C_GLOW, 0.0, 0.300,
                          emission=C_GLOW, emission_strength=GLOW_EMIT)
M_BONE    = make_material("DocBone", C_BONE, 0.0, 0.800, sheen=0.20)

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
    if coll is COL_HERO:
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
    coll = coll or COL_HERO
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
    coll = coll or COL_HERO
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
    ob = _finish(name, bm, mat, coll or COL_HERO, smooth)
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
    ob = _finish(name, bm, mat, coll or COL_HERO, smooth=False)
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
    ob = _finish(name, bm, mat, coll or COL_HERO, True)
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
#  BODY SURFACE
#
#  One parametric surface sampled by everything that lies on the body: the coat,
#  the apron, the belt, the pack straps and the vial bandolier. Conforming them
#  all to the same function is what stops the straps floating off the coat the
#  moment the folds or the lean are retuned - and with no audit script for this
#  asset yet, that discipline is the only thing standing in for one.
# ==============================================================================


def lean_y(z):
    """Forward pitch of everything above the hip. See LEAN_K / LEAN_POW.

    Returns 0 at and below the hip, so the legs stay planted while the whole
    upper body - coat, pack, arms, head - pitches forward together. Anything
    placed by hand in world space MUST add this, or it will hang off the front of
    him at chest height and sink into his back at the waist.
    """
    d = max(0.0, z - Z_HIP)
    return -LEAN_K * (d ** LEAN_POW)


def coat_fold(theta, z, amp):
    """Fold displacement at (theta, z).

    Periodic in 2*pi ONLY while FOLD_LOBES is an integer - the modulation term is
    itself 2*pi periodic, so the whole expression wraps cleanly and the loft seam
    closes. A fractional lobe count tears a seam up the back of the coat.
    """
    ph = FOLD_SKEW * sin(theta + FOLD_PHASE) + FOLD_TWIST * z
    s = abs(sin(FOLD_LOBES * theta + ph))
    main = s ** FOLD_POWER - FOLD_MEAN
    s2 = abs(sin(FOLD_LOBES2 * theta + FOLD_TWIST2 * z + 2.1))
    fine = (s2 ** FOLD_POWER - FOLD_MEAN) * FOLD_FINE
    return amp * (main + fine)


def coat_radius(theta, z, offset=0.0):
    r, amp = table_lookup(COAT_TABLE, z)
    return r + coat_fold(theta, z, amp) + offset


def body_shape(theta, r, z):
    """Turn a radius into a point on the body's cross-section.

    Elliptical (BODY_DEPTH) and pitched forward (lean_y). Everything that lies on
    the body goes through here.
    """
    return Vector((r * cos(theta),
                   r * sin(theta) * BODY_DEPTH + lean_y(z),
                   z))


def coat_point(theta, z, offset=0.0):
    return body_shape(theta, coat_radius(theta, z, offset), z)


def coat_z_samples(step=0.030):
    zs, z = [], Z_GROUND
    top = COAT_TABLE[-1][0]
    while z < top - 1e-6:
        zs.append(z)
        z += step
    zs.append(top)
    return zs


def ring_on(name, centre, axis, major, minor, mat, scale=(1, 1, 1), mseg=24):
    """A torus whose hole points along `axis`.

    add_torus() builds in the local XY plane with its normal on +Z, so the axis
    has to be rotated in. Every band on this model - the beak's brass ring, the
    boiler hoops, the cuffs, the censer seam - is one of these, and hand-writing
    the euler for each was where the first pass put two of them on edge.
    """
    rot = Vector(axis).normalized().to_track_quat('Z', 'Y').to_euler()
    return add_torus(name, centre, major, minor, rot=rot, mat=mat,
                     scale=scale, mseg=mseg)


# ==============================================================================
#  BUILDERS
# ==============================================================================

COAT_SEGS  = 44
APRON_SEGS = 22
HOOD_SEGS  = 30

# (z, radius, extra y pushed BACKWARD). The cowl bulges back at the crown, which
# is what makes it read as cloth hung off the head rather than as a helmet.
HOOD_TABLE = [
    (1.330, 0.236, 0.048),
    (1.395, 0.198, 0.038),
    (1.462, 0.178, 0.026),
    (1.530, 0.168, 0.014),
    (1.592, 0.150, 0.004),
    (1.640, 0.104, -0.012),
    (1.656, 0.046, -0.020),
]
HOOD_OPEN = 0.680   # radians of half-gap at the front. The goggles sit ~30 deg
                    # off the centreline and the hood edge lands at ~39 deg, so
                    # the face stays visible through the opening. Widening the
                    # hood without widening this buries the lenses.

HEAD_C = Vector((0.0, 0.0, Z_HEAD))   # y filled in by build_head via lean_y


def build_boots():
    for tag, x in (("L", 0.115), ("R", -0.115)):
        set_side(tag)
        prof = [(0.000, 0.008), (0.052, 0.010), (0.078, 0.030), (0.086, 0.070),
                (0.090, 0.120), (0.088, 0.170), (0.078, 0.215), (0.072, 0.262),
                (0.074, 0.300), (0.068, 0.330), (0.000, 0.336)]
        ob = revolve("Boot_" + tag, prof, segments=24, mat=M_LEATHER,
                     origin=(x, -0.012, 0.0))
        bevel(ob, 0.004)
        subsurf(ob, 1)
        # The toe. Centred INSIDE the boot shaft (50 mm off an 82 mm radius) so
        # it merges rather than sits against it - a toe parked at the surface
        # reads as a ball glued to the front, which is the same mistake the
        # knight's gold heel disc made.
        add_sphere("BootToe_" + tag, (x, -0.062, 0.050), 0.058,
                   scale=(0.86, 1.30, 0.62), mat=M_LEATHER)
        ring_on("BootBuckle_" + tag, (x, -0.012, 0.246), (0, 0, 1),
                0.080, 0.011, M_BRASS, mseg=20)
    set_side("")


def build_legs():
    # Overlap both ends deliberately: 30 mm into the boot shaft at the bottom,
    # 40 mm past the hip into the coat at the top.
    for tag, x in (("L", 0.115), ("R", -0.115)):
        set_side(tag)
        capsule("Leg_" + tag, (x, -0.010, 0.300),
                (x * 0.62, lean_y(Z_HIP + 0.04), Z_HIP + 0.040),
                0.072, 0.098, mat=M_DARK, segs=16)
    set_side("")


def build_coat():
    zs = coat_z_samples()
    rings = [[coat_point(2.0 * pi * i / COAT_SEGS, z) for i in range(COAT_SEGS)]
             for z in zs]
    ob = loft("Coat", rings, mat=M_LEATHER, closed=True)
    # rim=True is what closes the open top and bottom and makes this manifold.
    # The lining material is how the neck opening and the hem read near-black
    # (rule 4) without a second nested object for the levitation check to argue
    # about.
    solidify(ob, 0.016, lining=M_DARK)
    subsurf(ob, 1)
    return ob


def build_apron():
    """The one mid-value mass on the figure. Without it he is a black blob with
    metal on it - the canvas is what gives the eye a middle step between the
    tarred leather and the copper."""
    zs = [z for z in coat_z_samples(0.034) if 0.215 <= z <= 1.205]
    rings = []
    for z in zs:
        # Widens as it falls: a constant-width apron reads as a tabard.
        half = 0.950 * lerp(0.720, 1.000, smoothstep((1.205 - z) / 0.990))
        ring = []
        for k in range(APRON_SEGS):
            t = 2.0 * k / (APRON_SEGS - 1) - 1.0
            # offset 0.004: the apron's own solidify runs INWARD by 12 mm, so its
            # back face lands 8 mm inside the coat surface. That overlap is the
            # whole point - at a larger offset it hovers.
            ring.append(coat_point(THETA_FRONT + half * t, z, 0.004))
        rings.append(ring)
    ob = loft("Apron", rings, mat=M_CANVAS, closed=False)
    solidify(ob, 0.012, lining=M_DARK)
    subsurf(ob, 1)
    return ob


def build_belt():
    zs   = [0.928, 0.950, 0.988, 1.006]
    offs = [0.004, 0.020, 0.020, 0.004]
    rings = [[coat_point(2.0 * pi * i / COAT_SEGS, z, o)
              for i in range(COAT_SEGS)] for z, o in zip(zs, offs)]
    ob = loft("Belt", rings, mat=M_LEATHER_HI, closed=True)
    solidify(ob, 0.010, lining=M_DARK)
    # A plain buckle plate on the front, seated into the band.
    add_sphere("BeltBuckle", coat_point(THETA_FRONT, 0.968, 0.012), 0.044,
               scale=(1.00, 0.42, 0.78), mat=M_BRASS)
    return ob


def build_arms():
    sh_z = Z_SHOULDER - 0.020
    for tag, sgn in (("L", 1.0), ("R", -1.0)):
        set_side(tag)
        sh = Vector((sgn * 0.268, lean_y(sh_z) + 0.012, sh_z))
        if sgn < 0:
            # His right arm hangs, and carries the censer chain.
            spine = [sh,
                     Vector((-0.320, lean_y(1.10) - 0.020, 1.100)),
                     Vector((-0.332, -0.104, 0.980)),
                     HAND_R_POS + Vector((0.0, 0.0, 0.062))]
            radii = [0.088, 0.074, 0.062, 0.055]
            hand = HAND_R_POS
        else:
            # His left is bent up across the chest, holding the flask. The two
            # arms are deliberately different - a symmetric pair of hanging arms
            # is what makes a static hero read as a mannequin.
            spine = [sh,
                     Vector((0.314, lean_y(1.14) - 0.030, 1.140)),
                     Vector((0.292, -0.166, 1.092)),
                     HAND_L_POS + Vector((0.0, 0.020, 0.010))]
            radii = [0.088, 0.076, 0.064, 0.056]
            hand = HAND_L_POS
        swept_taper("Sleeve_" + tag, spine, radii, M_LEATHER, segs=16)
        # Mitts, not hands: this is a blockout and digits are the pipeline's job.
        add_sphere("Mitt_" + tag, hand, 0.062, scale=(0.90, 1.15, 1.00),
                   mat=M_LEATHER_HI)
        cuff_axis = (hand - spine[-2])
        ring_on("Cuff_" + tag, hand + cuff_axis.normalized() * -0.052,
                cuff_axis, 0.060, 0.013, M_BRASS, mseg=20)
    set_side("")


def build_head():
    global HEAD_C
    HEAD_C = Vector((0.0, lean_y(Z_HEAD), Z_HEAD))
    add_sphere("Head", HEAD_C, HEAD_R, scale=HEAD_SCALE, mat=M_DARK)
    # Neck, overlapping the coat's neck opening at the bottom and the head above.
    capsule("Neck", (0.0, lean_y(Z_NECK - 0.06), Z_NECK - 0.060),
            (0.0, lean_y(Z_HEAD - 0.03), Z_HEAD - 0.030),
            0.072, 0.062, mat=M_DARK, segs=16)


def build_mask():
    """Silhouette feature 1. The beak points FORWARD, into the axis neither other
    hero uses, and curves DOWN over its length - a straight cone reads as a party
    hat on its side."""
    add_sphere("Mask", HEAD_C + Vector((0.0, -0.012, 0.004)), 0.104,
               scale=(1.00, 1.06, 1.05), mat=M_LEATHER)
    spine = [HEAD_C + Vector(p) for p in BEAK_SPINE]
    swept_taper("Beak", spine, BEAK_RADII, M_LEATHER, segs=18)
    # The brass ring where the beak leaves the mask. Rule 3 - it is what stops the
    # beak dissolving into the mask at icon size, both being the same near-black.
    ring_on("BeakRing", HEAD_C + Vector((0.0, -0.070, 0.004)), (0.0, -1.0, 0.10),
            0.062, 0.011, M_BRASS, mseg=22)
    # Breather canister slung under the beak's root - the filter he breathes
    # through, and the reason the mask reads as apparatus rather than costume.
    capsule("Filter", HEAD_C + Vector((0.0, -0.118, -0.056)),
            HEAD_C + Vector((0.0, -0.176, -0.070)),
            0.034, 0.028, mat=M_COPPER, segs=14)


def build_goggles():
    for tag, sgn in (("L", 1.0), ("R", -1.0)):
        set_side(tag)
        c = HEAD_C + Vector((sgn * GOG_X, GOG_Y, GOG_Z))
        # Flattened along Y so it reads as a disc of glass set into the mask,
        # not as an insect eye. Seated INSIDE the mask ellipsoid so it protrudes
        # rather than floats.
        add_sphere("Lens_" + tag, c, GOG_R, scale=(1.00, 0.45, 1.00),
                   mat=M_LENS)
        ring_on("GogRim_" + tag, c + Vector((0.0, 0.004, 0.0)),
                (0.0, -1.0, 0.10), GOG_R + 0.008, 0.010, M_BRASS, mseg=20)
    set_side("")


def build_hood():
    """A cowl, open at the front. Explicitly NOT a brim - the broad brim is the
    mage's silhouette and taking it here would collapse the two heroes into one
    read at icon size."""
    rings = []
    for z, r, yb in HOOD_TABLE:
        cy = lean_y(z) + yb
        ring = []
        for k in range(HOOD_SEGS):
            t = k / (HOOD_SEGS - 1)
            th = THETA_FRONT + HOOD_OPEN + t * (2.0 * pi - 2.0 * HOOD_OPEN)
            ring.append(Vector((r * cos(th), r * sin(th) * 0.92 + cy, z)))
        rings.append(ring)
    ob = loft("Hood", rings, mat=M_CANVAS, closed=False)
    solidify(ob, 0.014, lining=M_DARK)
    subsurf(ob, 1)
    return ob


def build_still():
    """Silhouette feature 2: the reason he is wide, asymmetric and back-heavy.

    One thing over EACH shoulder - chimney left, condenser right - is what makes
    the pack read as a rig he assembled rather than as a lump on his back.
    """
    # -- Boiler. Flattened in Y so it sits against the back instead of balling
    #    out behind him.
    boiler = [(0.000, 0.942), (0.096, 0.946), (0.158, 0.984), (0.196, 1.052),
              (0.212, 1.130), (0.206, 1.208), (0.176, 1.286), (0.124, 1.352),
              (0.070, 1.386), (0.000, 1.396)]
    ob = revolve("Boiler", boiler, segments=28, mat=M_COPPER,
                 origin=(0.0, Y_STILL, 0.0), scale=(1.00, 0.86, 1.00))
    bevel(ob, 0.005)
    for i, (z, r) in enumerate(((1.020, 0.192), (1.130, 0.212), (1.244, 0.196))):
        ring_on("BoilerHoop%d" % i, (0.0, Y_STILL, z), (0, 0, 1),
                r + 0.006, 0.013, M_BRASS, scale=(1.00, 0.86, 1.00), mseg=26)
    # Patina in the shadow under the boiler's belly, where copper actually rots.
    ring_on("Patina", (0.0, Y_STILL, 0.986), (0, 0, 1), 0.164, 0.016, M_VERDI,
            scale=(1.00, 0.86, 1.00), mseg=24)

    # -- Firebox, slung under the boiler and overlapping it by 20 mm.
    fbox = [(0.000, 0.760), (0.084, 0.764), (0.128, 0.800), (0.140, 0.860),
            (0.136, 0.916), (0.112, 0.948), (0.060, 0.960), (0.000, 0.962)]
    revolve("Firebox", fbox, segments=24, mat=M_IRON,
            origin=(0.0, Y_STILL, 0.0), scale=(1.00, 0.86, 1.00))
    # The grate. The brightest green on the model and the only one allowed to be
    # - it is the source the other greens are spill from. It can carry
    # FIRE_EMIT=1.5 without blowing out only because it sits inside a near-black
    # iron shroud; the same value on an exposed surface reads as white.
    add_sphere("Grate", (0.0, Y_STILL + 0.114, 0.858), 0.052,
               scale=(1.00, 0.30, 0.62), mat=M_FIRE)
    ring_on("GrateShroud", (0.0, Y_STILL + 0.118, 0.858), (0, 1, 0),
            0.062, 0.017, M_DARK, mseg=20)

    # -- Chimney over his LEFT shoulder.
    swept_taper("Chimney", [Vector(p) for p in CHIMNEY_SPINE], CHIMNEY_RADII,
                M_COPPER, segs=16)
    # Hollow flared cowl: down the outside, back up the inside, closed by a pole
    # at each end. A cone capped with a disc reads as a nail head.
    cowl = [(0.000, 2.012), (0.040, 2.016), (0.046, 2.046), (0.074, 2.084),
            (0.066, 2.086), (0.040, 2.056), (0.034, 2.030), (0.000, 2.026)]
    revolve("ChimneyCowl", cowl, segments=22, mat=M_COPPER_D,
            origin=(0.150, 0.172, 0.0))

    # -- Swan neck over his RIGHT shoulder, ending in a spout at the chest.
    swept_taper("SwanNeck", [Vector(p) for p in SWAN_SPINE], SWAN_RADII,
                M_COPPER, segs=14)
    capsule("Spout", (-0.226, -0.158, 1.118), (-0.204, -0.198, 1.078),
            0.024, 0.014, mat=M_BRASS, segs=14)
    add_sphere("Drip", (-0.202, -0.202, 1.070), 0.016, mat=M_GLOW)

    # -- Condenser coil on the pack's right flank. A helix, not a stack of rings:
    #    the whole read is "a tube that goes round and round".
    pts, n = [], int(COIL_TURNS * 18)
    for i in range(n + 1):
        t = COIL_TURNS * i / n
        pts.append((COIL_CENTRE[0] + COIL_ADV * t,
                    COIL_CENTRE[1] + COIL_R * cos(2.0 * pi * t),
                    COIL_CENTRE[2] + COIL_R * sin(2.0 * pi * t)))
    sweep("Condenser", pts, COIL_TUBE, M_COPPER_D, segs=10)

    # -- Shoulder straps. Routed ON the coat surface via coat_point() rather than
    #    written as world coordinates: at x=+-0.16 in world space they sank
    #    entirely inside the coat, because the coat is a 0.33 m bell and a strap
    #    drawn straight over the shoulder is nowhere near its surface.
    for tag, sgn in (("L", 1.0), ("R", -1.0)):
        set_side(tag)
        th_b, th_f = 0.951 * sgn, -0.951 * sgn
        spine = [coat_point(th_b, 1.140, 0.006),
                 coat_point(th_b, 1.290, 0.008),
                 coat_point(0.600 * sgn, 1.372, 0.008),
                 coat_point(0.000 if sgn > 0 else pi, 1.392, 0.008),
                 coat_point(-0.600 * sgn, 1.372, 0.008),
                 coat_point(th_f, 1.290, 0.008),
                 coat_point(th_f, 1.140, 0.006),
                 coat_point(th_f, 0.988, 0.006)]
        pts = catmull(spine, 6)

        def ring(_t, a, _w=0.046, _th=0.012):
            return (_w * cos(a), _th * sin(a))

        sweep_fn("Strap_" + tag, pts, ring, M_LEATHER_HI, segs=14)
    set_side("")


def build_censer():
    """Silhouette feature 3, and the first hero signature object that is not
    planted in the ground. It hangs OUT and FORWARD of the hand, not below it: a
    plumb-vertical chain reads as a dropped object, where the whole idea is a
    pendulum caught mid-arc."""
    top = CENSER_POS + Vector((0.0, 0.0, 0.100))
    spine = [HAND_R_POS + Vector((-0.006, -0.020, -0.038)),
             HAND_R_POS + Vector((-0.030, -0.086, -0.150)),
             CENSER_POS + Vector((-0.006, 0.010, 0.210)),
             top]
    swept_taper("Chain", spine, [0.009, 0.008, 0.008, 0.007], M_IRON, segs=8)
    for i, t in enumerate((0.30, 0.58, 0.84)):
        p = spine[0].lerp(top, t)
        ring_on("ChainLink%d" % i, p, (top - spine[0]), 0.017, 0.005, M_IRON,
                mseg=14)
    body = [(0.000, -0.076), (0.038, -0.072), (0.062, -0.048), (0.074, -0.012),
            (0.076, 0.006), (0.070, 0.030), (0.054, 0.052), (0.032, 0.068),
            (0.018, 0.082), (0.024, 0.092), (0.010, 0.102), (0.000, 0.104)]
    ob = revolve("Censer", body, segments=24, mat=M_BRASS, origin=CENSER_POS)
    bevel(ob, 0.004)
    # The seam the smoke leaves by. Quieter than the firebox on purpose - three
    # equally bright greens and the eye has nowhere to land.
    ring_on("CenserSeam", CENSER_POS + Vector((0.0, 0.0, 0.006)), (0, 0, 1),
            0.078, 0.008, M_GLOW, mseg=24)
    ring_on("CenserBail", CENSER_POS + Vector((0.0, 0.0, 0.100)), (0, 1, 0),
            0.016, 0.005, M_IRON, mseg=14)


def build_flask():
    pos = HAND_L_POS + Vector((0.018, -0.052, 0.052))
    glass = [(0.000, -0.062), (0.036, -0.056), (0.058, -0.028), (0.062, 0.006),
             (0.050, 0.038), (0.028, 0.058), (0.020, 0.078), (0.022, 0.092),
             (0.000, 0.094)]
    revolve("Flask", glass, segments=22, mat=M_GLASS, origin=pos)
    # The tonic sits INSIDE the glass, filling it to just under the shoulder.
    tonic = [(0.000, -0.052), (0.030, -0.046), (0.046, -0.022), (0.050, 0.004),
             (0.000, 0.008)]
    revolve("Tonic", tonic, segments=20, mat=M_TONIC, origin=pos)
    ring_on("FlaskCollar", pos + Vector((0.0, 0.0, 0.080)), (0, 0, 1),
            0.024, 0.007, M_BRASS, mseg=16)


def build_vials():
    """A bandolier from his left shoulder to his right hip. Placed on the coat
    surface for the same reason the straps are."""
    n = 11
    pts = []
    for i in range(n):
        t = i / (n - 1)
        th = lerp(0.750, -2.050, t)
        z = lerp(1.325, 0.965, t)
        pts.append(coat_point(th, z, 0.006))

    def ring(_t, a, _w=0.034, _th=0.010):
        return (_w * cos(a), _th * sin(a))

    sweep_fn("Bandolier", catmull(pts, 5), ring, M_LEATHER_HI, segs=12)
    for i in range(5):
        t = 0.16 + 0.17 * i
        th = lerp(0.750, -2.050, t)
        z = lerp(1.325, 0.965, t)
        base = coat_point(th, z, 0.004)
        out = Vector((cos(th), sin(th) * BODY_DEPTH, 0.0)).normalized()
        # Seated 6 mm INTO the strap and standing 34 mm proud of it.
        capsule("Vial%d" % i, base - out * 0.006, base + out * 0.034,
                0.014, 0.012, mat=M_GLASS, segs=10)
        add_sphere("VialTonic%d" % i, base + out * 0.008, 0.010,
                   scale=(1.0, 1.0, 1.6), mat=M_TONIC)


def add_empty(name, loc, size=0.05):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = size
    e.location = loc
    COL_HERO.objects.link(e)
    EMPTIES.append(e)
    return e


def build_doctor():
    build_boots()
    build_legs()
    build_coat()
    build_apron()
    build_belt()
    build_arms()
    build_head()
    build_mask()
    build_goggles()
    build_hood()
    build_still()
    build_censer()
    build_flask()
    build_vials()

    add_empty("Attach_Censer", CENSER_POS)
    add_empty("Attach_BeakTip", HEAD_C + Vector(BEAK_SPINE[-1]))
    add_empty("Attach_Chimney", (0.150, 0.172, 2.086))
    add_empty("Attach_Flask", HAND_L_POS)
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
# previews land in the run directory instead of _plague000/.
_v = globals().get("VARIANT", {})
globals().update({k: v for k, v in _v.items() if not k.startswith("_")})
if _v.get("_patch"):
    # Structural variants arrive as SOURCE, not as function objects. A function
    # defined in the runner carries the runner's __globals__ and cannot see
    # revolve(), M_BRASS, or any other helper here - it would fail at call time,
    # deep in the build, for a reason that looks nothing like its cause.
    exec(_v["_patch"], globals())
# ------------------------------------------------------------------------------

build_doctor()
print("Good Doctor built: %d meshes, %d empties" % (len(PARTS), len(EMPTIES)))


# ==============================================================================
#  PREVIEW RIG
#
#  Same cold-ambience / warm-key art direction as the knight and the mage, so all
#  three heroes can be compared in the same light. The rig lives in its own
#  collection and is never exported.
# ==============================================================================


def build_rig():
    world = bpy.data.worlds.new("DoctorWorld")
    # Guarded rather than set unconditionally: in Blender 5.x a new world already
    # arrives with a node tree, and assigning use_nodes only touches a property
    # slated for removal in 6.0 and trips a DeprecationWarning for no gain.
    if not getattr(world, "node_tree", None):
        world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    # Greyer and less blue than the mage's world. His accent is violet, which sits
    # happily on a blue ambient; green on blue drifts toward teal and stops
    # reading as sickness.
    bg.inputs[0].default_value = (0.026, 0.030, 0.034, 1.0)
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

    # Between the knight's levels and the mage's, and that is not a fudge: this
    # model is genuinely half and half. The copper and brass are metallic and only
    # answer where a highlight lands, while the coat is a dielectric at base value
    # 0.030 that answers Lambertian everywhere. Lit at the mage's cloth levels the
    # metal goes dead; lit at the knight's the leather turns to grey felt.
    aim = (0.0, 0.0, 1.00)
    area("Key",   (-1.95, -2.35, 2.60), aim, 145, (1.00, 0.86, 0.66), 2.0)
    area("Fill",  ( 2.20, -1.85, 1.15), aim,  30, (0.62, 0.74, 1.00), 2.4)
    area("RimL",  ( 1.70,  2.00, 2.15), aim, 110, (0.50, 0.66, 1.00), 1.3)
    area("RimR",  (-1.85,  1.80, 1.85), aim,  82, (0.52, 0.70, 1.00), 1.3)
    # Green bounce off the ground, standing in for the firebox's own spill. Placed
    # LOW and BEHIND, where the grate actually is. Without it the green appears
    # only on the emitters themselves and reads as decals rather than as light.
    area("FireSpill", (0.30, 1.55, 0.55), (0.0, 0.35, 1.00), 26,
         (0.36, 1.00, 0.30), 1.6)
    # Warm kicker low at the front to keep the copper alive below the belt, where
    # the key does not reach past the pack.
    area("CopperKick", (-1.15, -1.70, 0.42), (0.0, -0.20, 0.70), 20,
         (1.00, 0.62, 0.34), 1.4)

    floor_mat = make_material("RigFloor", (0.019, 0.021, 0.024, 1.0), 0.0, 0.44)
    revolve("Ground", [(0.0, 0.0), (16.0, 0.0)], segments=64, mat=floor_mat,
            coll=COL_RIG, origin=(0.0, 0.0, -0.004))

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 62
    cam = bpy.data.objects.new("Cam", cam_data)
    COL_RIG.objects.link(cam)
    SCENE.camera = cam

    # The EEVEE enum was renamed twice across 4.x/5.x ('BLENDER_EEVEE_NEXT' in
    # 4.2-4.5, back to 'BLENDER_EEVEE' in 5.x). Assigning the wrong one is a hard
    # TypeError, so try them in order the same way the view transform is handled
    # below. Blender 5.1 accepts the second.
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            SCENE.render.engine = eng
            break
        except Exception:
            continue
    SCENE.render.film_transparent = False
    SCENE.render.image_settings.file_format = 'PNG'
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
    # Distances are set so a ~2.05 m envelope (the chimney cowl, not the crown of
    # his head, is the top of this model) fills the frame at these focal lengths.
    # He is much shorter than the mage and the cameras are correspondingly closer;
    # reusing the mage's numbers leaves him a small figure in a large empty frame.
    render_view("poster", (-1.75, -5.05, 0.85), target=(0.0, 0.0, 1.00),
                res=(1400, 1950), lens=80, samples=320)
    render_view("hero_34", (-2.55, -3.15, 1.42), target=(0, 0, 0.98),
                samples=160)
    render_view("front", (0.0, -4.40, 0.98), target=(0, 0, 0.98), lens=70)
    render_view("side", (4.40, -0.10, 0.98), target=(0, 0, 0.98), lens=70)
    # The back is a first-class view on this hero, not an afterthought: the whole
    # still lives back there and half the silhouette brief is only checkable here.
    render_view("back", (0.25, 4.40, 1.02), target=(0, 0, 1.00), lens=70)
    render_view("back34", (2.95, 3.05, 1.35), target=(0, 0, 0.98))
    # Aimed at the beak and the lenses, which is the whole face. Pointed at the
    # hood instead it fills the frame with canvas.
    render_view("head", (-0.72, -1.42, 1.72), target=(0.0, -0.14, 1.47),
                res=(820, 820), lens=72)
    # Close-ups. Every one of these is a place where two surfaces meet and the
    # full-body render is too small to show whether they meet correctly. With no
    # audit script for this asset yet, these renders ARE the levitation check -
    # treat a suspicious gap here as a defect, not as a lighting artefact.
    render_view("still", (0.95, 1.55, 1.55), target=(0.05, 0.28, 1.20),
                res=(760, 760), lens=85)
    render_view("censer", (-0.86, -1.05, 0.62), target=(-0.40, -0.34, 0.44),
                res=(760, 760), lens=85)
    render_view("hands", (0.0, -1.35, 1.05), target=(0.0, -0.21, 0.96),
                res=(760, 760), lens=80)
    render_view("hem", (-0.75, -1.35, 0.42), target=(-0.05, -0.10, 0.16),
                res=(760, 760), lens=80)
    # Rule 2, the standing test: if he stops reading as beak + pack + censer here,
    # a change has regressed the silhouette regardless of how good the detail is.
    # Bust crop - the beak, the lenses, the hood and the chimney leaving frame.
    render_view("icon_184", (-0.95, -1.30, 1.68), target=(-0.05, -0.06, 1.45),
                res=(184, 184), lens=62)
    render_view("icon_full_184", (-2.55, -3.15, 1.42), target=(0, 0, 0.98),
                res=(184, 184), lens=58)

if DO_EXPORT:
    export_fbx()
