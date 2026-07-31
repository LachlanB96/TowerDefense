"""
Gloomfell - THE SILENT KNIGHT  (hero type code `knight000`)

Procedural rebuild of the hero model. Supersedes `char_knight2.blend`, whose
balloon-limb silhouette was flagged in the Steam store-page spec as reading like
"a chrome blob with a red skirt, not a Templar" at capsule scale.

Design source: Obsidian/TD/Heroes/Silent Knight.md
  - shiny silver plate, no skin visible          - gold trim (spoils of slain monsters)
  - chest emblem: gold T with rubies set in      - right hand: the Golden Sword (elven gift)
  - left hand: The Templar's Book                - barbute helmet, red glow from within
  - golden plume on the crown                    - vivid slightly-dark-blue cape, gold T

Legibility rules this rebuild is built around (the reason it exists):
  1. SILHOUETTE FIRST. Spiked pauldrons, a swept plume and a flaring cape have to
     name the character at 184x184 (Steam app icon) with all interior detail lost.
  2. GOLD DRAWS THE FORM. Bright steel alone flattens to a blob under any key
     light. Every plate boundary is outlined in gold trim, so the internal lines
     survive downscaling the way an inked drawing does.
  3. DARK RECESSES. Mail voiders, plate undersides and the helmet interior use a
     near-black material. Without them the red eye glow has nothing to glow against.

Run headless:   blender -b -P Assets/Blender/blender_knight000.py
Run in-session: exec(compile(open(PATH).read(), PATH, "exec"))

Conventions:
  * The knight faces -Y (Blender's front orthographic view). So:
        forward = -Y     back = +Y     his right = -X     his left = +X
    With the FBX export axes below this lands facing +Z in Unity.
  * Z-up, origin between the feet, ~1.98 units to the crown / ~2.2 to the plume tip.
  * Modifiers are left LIVE rather than applied. They survive into the FBX (the
    exporter evaluates the depsgraph), they keep the .blend editable, and - the
    real reason - `bpy.ops.mesh.bevel` and friends need a 3D-viewport context and
    are unreliable under `blender -b`. Everything here is built with bmesh.ops
    and modifiers, both of which are entirely context-free.
"""

import bpy
import bmesh
import math
import os
from math import radians, sin, cos, pi
from mathutils import Vector, Matrix, Euler

# -- Paths ---------------------------------------------------------------------
BLEND_PATH = r"C:\Users\LachlanB\TD\Assets\Blender\knight000.blend"
FBX_PATH   = r"C:\Users\LachlanB\TD\Assets\Models\knight000.fbx"
RENDER_DIR = r"C:\Users\LachlanB\TD\Assets\Blender\_knight000"

# Toggles. The showcase renders are slow-ish, so callers driving this
# interactively over MCP flip them from outside before exec'ing the file.
def _flag(name, default=False):
    """Flags come from either of the two ways this file gets run:
    headless   -> blender -b -P blender_knight000.py -- save export render
    in-session -> set the name in the namespace before exec'ing the file
    """
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return globals().get(name, default) or name.replace("DO_", "").lower() in argv


DO_RENDER = _flag("DO_RENDER")
DO_EXPORT = _flag("DO_EXPORT")
DO_SAVE   = _flag("DO_SAVE")
DO_GLARE  = _flag("DO_GLARE")   # see add_glare() for why this is opt-in

# ==============================================================================
#  SKELETON - every joint position in one table
#
#  Posing is done by moving these, not by hand-tuning rotations on each part.
#  Limb segments are built as tapered capsules between two of these points, so a
#  pose change propagates through the whole build.
# ==============================================================================

Z_GROUND      = 0.00
Z_ANKLE       = 0.16
Z_KNEE        = 0.60
Z_HIP         = 1.02
Z_WAIST       = 1.16
Z_CHEST       = 1.44
Z_SHOULDER    = 1.50
Z_NECK        = 1.60
Z_HELM_BOTTOM = 1.62
Z_CROWN       = 1.98

# Torso half-widths driving the cuirass loft.
W_WAIST = 0.195
W_CHEST = 0.300

# Legs: a slight A-stance. Feet planted wide enough to read as immovable, which
# is the whole point of a static hero.
HIP_R,   HIP_L   = Vector((-0.150, 0.000, Z_HIP)),   Vector(( 0.150, 0.000, Z_HIP))
KNEE_R,  KNEE_L  = Vector((-0.180,-0.015, Z_KNEE)),  Vector(( 0.180,-0.015, Z_KNEE))
ANKLE_R, ANKLE_L = Vector((-0.195,-0.030, Z_ANKLE)), Vector(( 0.195,-0.030, Z_ANKLE))

# Right arm (his right, -X) holds the Golden Sword point-down. The elbow is only
# slightly bent so the arm + blade form one long unbroken diagonal - the strongest
# line in the silhouette.
SHOULDER_R = Vector((-0.285, 0.000, Z_SHOULDER))
ELBOW_R    = Vector((-0.375,-0.050, 1.190))
# The wrist sits ~78 mm back up the forearm from the sword grip, leaving room
# for an actual hand. Originally these two points were 16 mm apart, so the whole
# fist was generated INSIDE the vambrace cuff and never saw daylight - the
# "potato" in the close-ups was the cuff, with the hand buried in it.
WRIST_R    = Vector((-0.388,-0.105, 1.055))

# Left arm (+X) is bent up and forward, palm flat, carrying the open tome.
SHOULDER_L = Vector(( 0.285, 0.000, Z_SHOULDER))
ELBOW_L    = Vector(( 0.360,-0.020, 1.185))
WRIST_L    = Vector(( 0.300,-0.270, 1.155))

# ==============================================================================
#  SCENE RESET
# ==============================================================================
# read_homefile rather than read_factory_settings: identical result for our
# purposes (empty scene, factory startup) and it does not touch user prefs.
bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)

SCENE = bpy.context.scene
COL_KNIGHT = bpy.data.collections.new("Knight")
COL_FX     = bpy.data.collections.new("FX")
COL_RIG    = bpy.data.collections.new("PreviewRig")
for c in (COL_KNIGHT, COL_FX, COL_RIG):
    SCENE.collection.children.link(c)

# ==============================================================================
#  MATERIALS
#
#  Value separation matters more than hue here. Steel sits at a mid value so the
#  gold (bright) and the void (black) both have somewhere to go; a brighter steel
#  is what turned the last knight into a chrome blob.
# ==============================================================================

def make_material(name, rgba, metallic=0.0, roughness=0.5,
                  emission=None, emission_strength=0.0,
                  transmission=0.0, coat=0.0, sheen=0.0, anisotropic=0.0):
    """Principled BSDF wrapper. Socket names are the Blender 4.x/5.x spelling
    ("Emission Color", not "Emission"); guarded by `in` so a rename downstream
    degrades to a missing highlight rather than a hard crash mid-build."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    if anisotropic and "Anisotropic" in b.inputs:
        b.inputs["Anisotropic"].default_value = anisotropic
    if transmission and "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = transmission
    if coat and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
    if sheen and "Sheen Weight" in b.inputs:
        b.inputs["Sheen Weight"].default_value = sheen
    if emission is not None:
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = emission
        if "Emission Strength" in b.inputs:
            b.inputs["Emission Strength"].default_value = emission_strength
    # Viewport colour, so the solid-shaded viewport is still readable while working.
    mat.diffuse_color = rgba
    mat.metallic = metallic
    mat.roughness = roughness
    return mat

# Steel is deliberately DARK. A physically "correct" bright polished steel
# (base ~0.55, roughness ~0.2) is what produced the chrome blob: every plate
# clips to white under any usable key light and the whole figure loses its
# internal drawing. Sitting the metal down at ~0.25 with mid roughness keeps the
# gold reading as the brightest thing on the model, which is what draws the form.
# THREE steels, not one. A single mid-grey metal is what made the armour read
# as featureless: with every plate, lame and rim the same value there is no
# internal contrast for the eye to follow. Now the base plates are darker and
# slightly rougher, the overlapping lames and rolled edges are brighter and
# more polished, and recesses go near-black. Anisotropy gives the highlight a
# stretched, forged character rather than a plastic ball of specular.
M_STEEL   = make_material("KnightSteel",      (0.205, 0.230, 0.278, 1.0), 1.0,
                          0.340, anisotropic=0.55)
M_STEEL_L = make_material("KnightSteelBright", (0.360, 0.395, 0.460, 1.0), 1.0,
                          0.170, anisotropic=0.40)
M_STEEL_D = make_material("KnightSteelDark",  (0.055, 0.062, 0.080, 1.0), 1.0,
                          0.520)
M_GOLD    = make_material("KnightGold",      (0.900, 0.590, 0.145, 1.0), 1.0, 0.240)
M_GOLD_D  = make_material("KnightGoldDeep",  (0.470, 0.270, 0.048, 1.0), 1.0, 0.380)
M_MAIL    = make_material("KnightMail",      (0.055, 0.062, 0.078, 1.0), 1.0, 0.680)
M_LEATHER = make_material("KnightLeather",   (0.075, 0.052, 0.038, 1.0), 0.0, 0.780)
M_VOID    = make_material("KnightVoid",      (0.004, 0.004, 0.006, 1.0), 0.0, 1.000)

# Rubies. A touch of self-emission keeps them lit even when they fall into the
# cuirass's own shadow - otherwise "bedazzled with rubies" reads as black dots.
# Low coat weight on purpose: a full clearcoat put a white specular veil over
# every stone and they all read as pale pink cabochons instead of dark red.
M_RUBY    = make_material("KnightRuby", (0.185, 0.006, 0.022, 1.0), 0.0, 0.120,
                          emission=(0.800, 0.025, 0.038, 1.0), emission_strength=0.35,
                          transmission=0.25, coat=0.35)

# Cape: "vivid slightly-dark blue". Sheen fakes the nap of heavy wool so it does
# not read as painted metal next to the actual metal.
M_CAPE    = make_material("KnightCape",      (0.038, 0.070, 0.330, 1.0), 0.0, 0.640, sheen=0.55)
M_CAPE_IN = make_material("KnightCapeLining",(0.013, 0.024, 0.105, 1.0), 0.0, 0.720, sheen=0.35)

# Emission strengths are tuned for a render with NO bloom pass. Anything above
# ~15 just clips to white and the red is lost - the glow has to come from a
# saturated colour against a dark interior, not from raw intensity.
# AgX desaturates bright emitters toward white, so cranking strength makes the
# eyes PALER, not redder. Low strength + a fully saturated colour against the
# black helmet interior is what keeps them burning red.
M_EYE     = make_material("KnightEyeGlow", (1.0, 0.02, 0.01, 1.0), 0.0, 0.4,
                          emission=(1.0, 0.025, 0.008, 1.0), emission_strength=3.0)
M_EYE_CORE = make_material("KnightEyeCore", (1.0, 0.20, 0.06, 1.0), 0.0, 0.3,
                           emission=(1.0, 0.30, 0.08, 1.0), emission_strength=7.0)
M_EYE_DIM = make_material("KnightEyeWash", (0.35, 0.02, 0.01, 1.0), 0.0, 0.7,
                          emission=(1.0, 0.09, 0.035, 1.0), emission_strength=1.4)
M_PAGE    = make_material("TomePage",      (0.620, 0.585, 0.495, 1.0), 0.0, 0.820)
M_PAGEGLOW= make_material("TomeGlow",      (1.0, 0.22, 0.09, 1.0), 0.0, 0.5,
                          emission=(1.0, 0.24, 0.08, 1.0), emission_strength=5.0)
# Metallic gold with only a whisper of emission. As a bright emitter the glyphs
# came out cream-white under AgX and read as plastic tags floating over his hand.
M_RUNE    = make_material("TomeRune",      (0.92, 0.58, 0.13, 1.0), 1.0, 0.28,
                          emission=(1.0, 0.34, 0.05, 1.0), emission_strength=0.35)
M_AURA    = make_material("KnightAura",    (1.0, 0.08, 0.04, 1.0), 0.0, 0.5,
                          emission=(1.0, 0.09, 0.04, 1.0), emission_strength=3.5)

# ==============================================================================
#  MESH PLUMBING
# ==============================================================================

PARTS = []   # every exportable mesh, in build order

# Stamped onto each object as it is created. Bone assignment needs to know which
# side a part belongs to, and the NAME cannot be trusted for it: lame suffixes
# produce names like "Finger_R0_L0", so looking for a trailing "_L"/"_R" finds
# the wrong token. Builders set this around their per-side calls.
CURRENT_SIDE = ""


def set_side(tag):
    global CURRENT_SIDE
    CURRENT_SIDE = tag


def _finish(name, bm, mat, coll, smooth=True):
    """Turn a bmesh into a linked object. Normals are recalculated outward
    because several builders below construct rings in whichever winding order
    was convenient, and inverted normals only show up later as black facets."""
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
    # FX ships too, as its own export group, so the game can switch the aura on
    # and off. Only the preview rig and the boolean cutters stay behind.
    if coll in (COL_KNIGHT, COL_FX):
        PARTS.append(ob)
    return ob


def bevel(ob, width=0.005, segments=2, angle=40.0, clamp=True):
    m = ob.modifiers.new("Bevel", 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = radians(angle)
    m.use_clamp_overlap = clamp
    m.miter_outer = 'MITER_ARC'   # rounded corners; sharp miters read as cubes
    return m


def subsurf(ob, levels=1):
    m = ob.modifiers.new("Subsurf", 'SUBSURF')
    m.levels = levels
    m.render_levels = levels
    return m


def solidify(ob, thickness, offset=-1.0, rim=True):
    m = ob.modifiers.new("Solidify", 'SOLIDIFY')
    m.thickness = thickness
    m.offset = offset
    m.use_rim = rim
    m.use_rim_only = False
    return m


def displace_noise(ob, strength, noise_scale, texture_name):
    """Fine surface break-up for the mail voiders.

    Kept deliberately gentle (large noise scale, small strength). Cranked up it
    does not read as chainmail - random high-frequency noise on a dark surface
    just reads as dirt or damage, which is worse than a plain dark padding.
    """
    tex = bpy.data.textures.new(texture_name, type='CLOUDS')
    tex.noise_scale = noise_scale
    tex.noise_depth = 1
    m = ob.modifiers.new("Displace", 'DISPLACE')
    m.texture = tex
    m.strength = strength
    m.mid_level = 0.5
    m.texture_coords = 'LOCAL'
    return m


# ------------------------------------------------------------------------------
#  Two generators do almost all the work here: `revolve` for anything with an
#  axis of symmetry, `loft` for anything shaped by a stack of cross-sections.
# ------------------------------------------------------------------------------

def revolve(name, profile, segments=24, mat=None, coll=None,
            origin=(0, 0, 0), rot=None, scale=(1, 1, 1), smooth=True,
            close_profile=False, radial_fn=None):
    """Lathe a 2D (radius, z) profile around local +Z.

    A profile entry with radius 0 becomes a pole (a fan of triangles) rather
    than a degenerate ring, which is what makes capsule caps and dome tops come
    out clean. Open ends are left open - cap them by ending the profile at r=0.

    `close_profile` wraps the last profile point back to the first. Shell bands
    (fauld lames, the belt, gorget lames, sabaton cuffs) trace out-and-back
    cross-sections that are closed loops in 2D, but the loft does not wrap on
    its own - which left every one of them with an open ring of boundary edges
    along the top seam.
    """
    coll = coll or COL_KNIGHT
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
                    # Fade the modulation out as the profile collapses, so
                    # capsule caps and poles stay clean.
                    rr += radial_fn(a) * min(1.0, r / 0.030)
                ring.append(bm.verts.new((rr * cos(a), rr * sin(a), z)))
            rings.append(ring)

    for a_ring, b_ring in zip(rings, rings[1:]):
        if len(a_ring) == 1 and len(b_ring) == 1:
            continue
        if len(a_ring) == 1:                                  # bottom pole fan
            for i in range(segments):
                bm.faces.new((a_ring[0], b_ring[i], b_ring[(i + 1) % segments]))
        elif len(b_ring) == 1:                                # top pole fan
            for i in range(segments):
                bm.faces.new((a_ring[i], a_ring[(i + 1) % segments], b_ring[0]))
        else:
            for i in range(segments):
                j = (i + 1) % segments
                bm.faces.new((a_ring[i], a_ring[j], b_ring[j], b_ring[i]))

    # Bridge the last ring back to the first, reusing the SAME vertices. An
    # earlier version appended a duplicate profile point instead, which looked
    # closed but left two coincident open loops - still non-manifold, and the
    # audit rightly kept failing.
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

    `closed` wraps the ring back on itself (tubes, torsos); False leaves it open
    (sheets: the cape, pauldron lames, tassets - anything later solidified).
    """
    coll = coll or COL_KNIGHT
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


# ------------------------------------------------------------------------------
#  Primitives
# ------------------------------------------------------------------------------

def add_sphere(name, loc, radius=0.1, scale=(1, 1, 1), rot=(0, 0, 0),
               mat=None, u=24, v=12, coll=None, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=radius)
    ob = _finish(name, bm, mat, coll or COL_KNIGHT, smooth)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return ob


def add_gem(name, loc, radius=0.02, subdiv=1, mat=None, rot=(0, 0, 0),
            scale=(1, 1, 1), coll=None):
    """Faceted icosphere, deliberately flat-shaded. Gems are the one place the
    "no visible cubes" rule inverts: facets are how a cut stone reads."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    ob = _finish(name, bm, mat, coll or COL_KNIGHT, smooth=False)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return ob


def add_cyl(name, loc, r1, r2, depth, rot=(0, 0, 0), mat=None, segs=20,
            caps=True, coll=None, scale=(1, 1, 1), smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=segs,
                          radius1=r1, radius2=r2, depth=depth)
    ob = _finish(name, bm, mat, coll or COL_KNIGHT, smooth)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return ob


def add_box(name, loc, scale=(1, 1, 1), rot=(0, 0, 0), mat=None, coll=None,
            smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    ob = _finish(name, bm, mat, coll or COL_KNIGHT, smooth)
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
    ob = _finish(name, bm, mat, coll or COL_KNIGHT, True)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return ob


def capsule(name, p0, p1, r0, r1, mat=None, segs=18, cap0=True, cap1=True,
            shaft_rings=3, coll=None, cap_steps=4):
    """Tapered capsule between two world-space points - the limb primitive.

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
    return ob


def look_at_euler(from_p, to_p):
    """Euler aiming a camera or a light at a point.

    Tracks -Z, not +Z: cameras look down their local -Z axis and area/spot lights
    emit along it too. Meshes that need +Z aiming (spikes, bands, limbs) call
    to_track_quat('Z', 'Y') directly instead.
    """
    return (Vector(to_p) - Vector(from_p)).to_track_quat('-Z', 'Y').to_euler()


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_v(a, b, t):
    return Vector(a).lerp(Vector(b), t)


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


# ==============================================================================
#  TORSO SURFACE
#
#  One parametric body surface, sampled by everything that sits on the chest:
#  the cuirass itself, the overlapping plackart, the gold trim and the Templar
#  emblem. Conforming them all to the same function is what stops the emblem
#  floating off the chest the way it did on char_knight2.
# ==============================================================================

BACK_FLAT = 0.90          # the spine side is flatter than the chest side
THETA_FRONT = -pi / 2.0   # front centreline (the knight faces -Y)
THETA_BACK = pi / 2.0

#                z,     half-width, half-depth, keel (central ridge depth)
TORSO_TABLE = [
    # Keel halved from its original values. A 44 mm central ridge bowed anything
    # laid on it - the Templar T followed the curve and read as warped. Reducing
    # keel_scale for the emblem alone does NOT work: the keel is what holds the
    # surface out, so a flatter emblem sinks into the plackart beneath it.
    (1.020, 0.208, 0.152, 0.008),   # hip flare, hidden under the fauld
    (1.100, 0.198, 0.144, 0.013),
    (1.160, 0.192, 0.140, 0.017),   # waist - the narrowest point
    (1.240, 0.228, 0.162, 0.021),
    (1.320, 0.266, 0.182, 0.022),
    (1.400, 0.294, 0.196, 0.018),
    (1.460, 0.302, 0.197, 0.011),   # full chest
    (1.520, 0.282, 0.184, 0.005),
    (1.570, 0.243, 0.163, 0.000),   # shoulder shelf
    (1.605, 0.186, 0.130, 0.000),   # neck opening
]


def torso_profile(z):
    """(half_width, half_depth, keel) at height z, smoothstep-blended between
    table rows so plates laid across a row boundary do not kink."""
    if z <= TORSO_TABLE[0][0]:
        return TORSO_TABLE[0][1:]
    if z >= TORSO_TABLE[-1][0]:
        return TORSO_TABLE[-1][1:]
    for (z0, w0, d0, k0), (z1, w1, d1, k1) in zip(TORSO_TABLE, TORSO_TABLE[1:]):
        if z0 <= z <= z1:
            t = smoothstep((z - z0) / (z1 - z0))
            return (lerp(w0, w1, t), lerp(d0, d1, t), lerp(k0, k1, t))
    return TORSO_TABLE[-1][1:]


def torso_point(theta, z, offset=0.0, keel_scale=1.0):
    """Point on the torso shell. `offset` pushes out along the (approximate)
    surface normal - how every overlaid plate gets its stand-off."""
    hw, hd, keel = torso_profile(z)
    x = hw * cos(theta)
    y = hd * sin(theta)
    if y > 0:
        y *= BACK_FLAT
    else:
        # Narrow vertical keel down the breast - the "tapul" of a real cuirass.
        # Power 4 keeps it a ridge rather than a general bulge.
        y -= keel * keel_scale * max(0.0, -sin(theta)) ** 4
    if abs(offset) > 1e-9:
        n = Vector((x / max(hw, 1e-6), y / max(hd, 1e-6), 0.0))
        if n.length > 1e-9:
            n.normalize()
        x += n.x * offset
        y += n.y * offset
    return Vector((x, y, z))


def theta_span_for_width(z, half_width, offset=0.0):
    """Convert a desired half-width in world X into a half-angle at height z,
    so plate sizes can be specified in centimetres instead of radians."""
    hw = torso_profile(z)[0] + offset
    return math.asin(max(-1.0, min(1.0, half_width / max(hw, 1e-6))))


def tube_along(name, points, radius, mat, segs=10, coll=None, taper=None):
    """Sweep a circle along a polyline using a rotation-minimizing frame.

    The obvious implementation - cross the tangent with a fixed world up - fails
    badly whenever a path passes near vertical: the fallback up-vector swaps
    between consecutive samples, the ring flips 90 degrees, and the sweep
    explodes into a spike. That is exactly what happened to the near-vertical
    gold edging beside the helmet's nasal slot. Parallel-transporting the
    reference vector from one sample to the next removes the failure mode
    entirely and also stops long sweeps (the cape hem, the comb) from twisting.
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
        side = ref
        up2 = tans[i].cross(side).normalized()
        r = radius * (taper[i] if taper else 1.0)
        rings.append([p + side * (r * cos(2 * pi * k / segs))
                        + up2 * (r * sin(2 * pi * k / segs))
                      for k in range(segs)])
    return loft(name, rings, mat=mat, closed=True, cap_start=True,
                cap_end=True, coll=coll)


def surface_plate(name, theta_c, half_width, z_lo, z_hi, offset, thickness,
                  mat, seg_t=14, seg_z=6, taper_top=1.0, taper_bot=1.0,
                  bulge=0.0, coll=None, keel_scale=1.0):
    """A curved plate lying on the torso surface, sized in world half-width.

    taper_* scale the half-width at the top / bottom edge (shield-shaped plates);
    `bulge` adds extra stand-off at the centre so a plate can dome outward.
    """
    rings = []
    for i in range(seg_z + 1):
        tz = i / seg_z
        z = lerp(z_lo, z_hi, tz)
        sc = lerp(taper_bot, taper_top, tz)
        dth = theta_span_for_width(z, half_width * sc, offset)
        ring = []
        for j in range(seg_t + 1):
            tt = j / seg_t
            th = theta_c + lerp(-dth, dth, tt)
            d = bulge * sin(pi * tt) * sin(pi * tz) if bulge else 0.0
            ring.append(torso_point(th, z, offset + d, keel_scale))
        rings.append(ring)
    ob = loft(name, rings, mat=mat, closed=False, coll=coll)
    solidify(ob, thickness)
    bevel(ob, width=0.0035, segments=2)
    return ob


def densify_rows(rows, max_step):
    """Subdivide a (position, half-width) control list so no span is longer
    than `max_step`.

    Essential for any patch laid onto a curved shell. A stepped outline written
    as bare control points produces long quad bands that CHORD across the
    curvature - the emblem stem spanned 40% of the cape in a single band and
    disappeared inside the cloth. Extra rows cost nothing and make the patch
    follow the surface.
    """
    out = []
    for a, b in zip(rows, rows[1:]):
        n = max(1, int(math.ceil(abs(b[0] - a[0]) / max_step)))
        for k in range(n):
            t = k / n
            out.append((lerp(a[0], b[0], t), lerp(a[1], b[1], t)))
    out.append(rows[-1])
    return out


def surface_plate_rows(name, theta_c, rows, offset, thickness, mat,
                       seg_t=20, bulge=0.0, coll=None, keel_scale=1.0):
    """Curved torso plate whose half-width is specified PER ROW: [(z, hw), ...].

    Exists so a whole Templar T can be one continuous surface. Assembling it
    from three overlapping rectangles put the stem and the foot at the same
    offset over the same z range - two coplanar gold faces competing for the
    same pixels, which is what shredded the bottom of the emblem into a
    sawtooth. Two rows at nearly the same z with different widths give a clean
    stepped outline instead.
    """
    rows = densify_rows(rows, 0.018)
    rings = []
    n = max(1, len(rows) - 1)
    for i, (z, hw) in enumerate(rows):
        dth = theta_span_for_width(z, hw, offset)
        ring = []
        for j in range(seg_t + 1):
            tt = j / seg_t
            th = theta_c + lerp(-dth, dth, tt)
            d = bulge * sin(pi * tt) * sin(pi * (i / n)) if bulge else 0.0
            ring.append(torso_point(th, z, offset + d, keel_scale))
        rings.append(ring)
    ob = loft(name, rings, mat=mat, closed=False, coll=coll)
    solidify(ob, thickness)
    bevel(ob, width=0.0035, segments=2)
    return ob


def trim_arc(name, theta_c, half_width, z, offset, radius, mat,
             arc_seg=24, sag=0.0):
    """A gold piping bead following the torso at constant height, optionally
    sagging (or arching) at the centre. The workhorse for rule 2 up top:
    outline every plate boundary in gold."""
    pts = []
    dth = theta_span_for_width(z, half_width, offset)
    for i in range(arc_seg + 1):
        t = i / arc_seg
        th = theta_c + lerp(-dth, dth, t)
        zz = z - sag * sin(pi * t)
        pts.append(torso_point(th, zz, offset))
    return tube_along(name, pts, radius, mat)


def trim_vertical(name, theta, z_lo, z_hi, offset, radius, mat, seg=12):
    pts = [torso_point(theta, lerp(z_lo, z_hi, i / seg), offset)
           for i in range(seg + 1)]
    return tube_along(name, pts, radius, mat)


# ==============================================================================
#  CUIRASS
# ==============================================================================

def build_cuirass():
    seg = 32
    rings = [[torso_point(2 * pi * i / seg - pi / 2.0, z) for i in range(seg)]
             for (z, _w, _d, _k) in TORSO_TABLE]
    body = loft("Cuirass", rings, mat=M_STEEL, closed=True,
                cap_start=True, cap_end=True)
    bevel(body, width=0.006, segments=2)
    subsurf(body, 1)

    # Plackart: the second belly plate every 15th-century harness has. Its top
    # edge is the strongest horizontal line on the chest, so it gets a gold rim.
    surface_plate("Plackart", THETA_FRONT, 0.185, 1.055, 1.315,
                  offset=0.012, thickness=0.016, mat=M_STEEL,
                  taper_top=0.95, taper_bot=1.02, bulge=0.010, seg_t=18)
    # Arches UP at the centre (negative sag) so it frames the foot of the
    # Templar T instead of cutting across it.
    # Split into two arcs that stop short of the emblem stem. As one continuous
    # arc it ran straight across the T, putting gold trim on top of gold emblem
    # and turning the join into a smear.
    for sgn in (-1, 1):
        pts = []
        for i in range(13):
            t = i / 12.0
            x = lerp(0.058, 0.190, t)
            th = THETA_FRONT + sgn * theta_span_for_width(1.302, x, 0.020)
            pts.append(torso_point(th, 1.302 + 0.020 * (1.0 - t) ** 1.3, 0.020))
        tube_along("Plackart_Rim_%s" % ("L" if sgn > 0 else "R"), pts,
                   0.010, M_GOLD)

    # Upper breast reinforce, tucked behind the emblem. No gold rim on this one:
    # the chest was carrying seven stacked horizontal gold lines and they were
    # competing with the emblem instead of supporting it.
    surface_plate("BreastPlate_Upper", THETA_FRONT, 0.215, 1.330, 1.520,
                  offset=0.010, thickness=0.014, mat=M_STEEL,
                  taper_top=0.92, taper_bot=1.0, bulge=0.008, seg_t=18)

    # Cuirass fluting, fanning up and outward from the waist either side of the
    # emblem. Same job as the pauldron ribs and the shin ridge: the breastplate
    # is a lofted barrel with no internal line of its own, so in a clay render
    # it is a can. Offset 0.020 puts these ON TOP of the plackart and breast
    # reinforce (whose outer faces sit at 0.010-0.012) but well under the
    # emblem at 0.050.
    # NO fluting on the breastplate, deliberately.
    #
    # The pauldrons and the limbs needed ribs because they were bare lathed
    # surfaces. The chest is different: it already carries the plackart step,
    # the breast reinforce step, the arming rivets, the belt and the emblem, so
    # it passes the clay test without help. Two attempts at chest ribs (long and
    # heavy, then short and thin) both read as claw marks raked across him -
    # surface tubes on an already-busy panel catch shadow along their undersides
    # and turn into slashes. If this area ever does need more form, deepen the
    # keel in TORSO_TABLE rather than laying tubes on top of it.

    # Raised gold spine down the back plate, so the turnaround has something to
    # look at and the back still reads when the cape swings clear.
    trim_vertical("Spine_Trim", THETA_BACK, 1.100, 1.560, offset=0.010,
                  radius=0.0095, mat=M_GOLD_D)

    # Arming rivets around the arm openings.
    for side in (-1, 1):
        for k in range(5):
            th = (pi if side < 0 else 0.0) + side * lerp(-0.55, 0.55, k / 4.0)
            p = torso_point(th, lerp(1.480, 1.560, abs(k - 2) / 2.0), 0.006)
            add_gem("Rivet_Arm_%d_%d" % (side, k), p, radius=0.011,
                    subdiv=1, mat=M_GOLD)


# ==============================================================================
#  GORGET, NECK AND CAPE MOUNT
# ==============================================================================

def build_gorget():
    # Dark mail column filling the neck opening. Without something black here
    # the helmet appears to float on a bright steel stalk.
    neck = revolve("Neck_Mail", [(0.000, 1.540), (0.108, 1.550), (0.112, 1.640),
                                 (0.108, 1.700), (0.000, 1.712)],
                   segments=20, mat=M_MAIL)
    neck.scale = (1.0, 0.92, 1.0)
    displace_noise(neck, 0.004, 0.10, "MailNoiseNeck")
    subsurf(neck, 1)

    lame1 = revolve("Gorget_Lame1", [(0.150, 1.545), (0.176, 1.565),
                                     (0.170, 1.590), (0.150, 1.594)],
                    segments=28, mat=M_STEEL, close_profile=True)
    lame1.scale = (1.0, 0.88, 1.0)
    bevel(lame1, 0.005, 2)

    lame2 = revolve("Gorget_Lame2", [(0.132, 1.588), (0.156, 1.612),
                                     (0.150, 1.640), (0.130, 1.644)],
                    segments=28, mat=M_STEEL, close_profile=True)
    lame2.scale = (1.0, 0.88, 1.0)
    bevel(lame2, 0.005, 2)

    collar = revolve("Gorget_Collar", [(0.118, 1.636), (0.128, 1.672),
                                       (0.146, 1.712), (0.140, 1.716),
                                       (0.120, 1.686), (0.110, 1.646)],
                     segments=28, mat=M_STEEL, close_profile=True)
    collar.scale = (1.0, 0.90, 1.0)
    bevel(collar, 0.004, 2)

    # Only the collar lip gets gold. Ringing all three lames stacked three more
    # horizontal gold lines directly under the chin.
    for z, r in ((1.714, 0.144),):
        t = add_torus("Gorget_Rim_%.3f" % z, (0, 0, z), r, 0.0075, mat=M_GOLD)
        t.scale = (1.0, 0.89, 1.0)

    # Cape clasps: a gold boss on each collarbone with a chain slung between.
    for side, tag in ((-1, "R"), (1, "L")):
        p = torso_point((pi if side < 0 else 0.0) + side * -0.62, 1.545, 0.020)
        add_sphere("CapeClasp_%s" % tag, p, radius=0.036,
                   scale=(1.0, 0.62, 1.0), mat=M_GOLD, u=20, v=10)
        add_gem("CapeClaspGem_%s" % tag, p + Vector((0, -0.020, 0)),
                radius=0.014, subdiv=1, mat=M_RUBY)
        add_torus("CapeClaspRing_%s" % tag, p + Vector((0, -0.004, 0)),
                  0.040, 0.006, rot=(radians(90), 0, 0), mat=M_GOLD_D)

    # Chain across the CHEST. The clasps above use `pi + 0.62` / `-0.62`, both of
    # which have sin(theta) < 0 and therefore sit on the front; `pi - 0.62` and
    # `+0.62` are their mirror images on the spine, which is where an earlier
    # version of this hung the chain.
    th_a, th_b = pi + 0.62, -0.62
    a = torso_point(th_a, 1.545, 0.030)
    b = torso_point(th_b, 1.545, 0.030)
    links = 13
    for i in range(links):
        t = i / (links - 1.0)
        p = a.lerp(b, t)
        p.z -= 0.055 * sin(pi * t)          # catenary-ish droop
        p.y = torso_point(lerp(th_a, th_b, t), p.z, 0.030).y
        add_torus("CapeChain_%02d" % i, p, 0.0165, 0.0052,
                  rot=(radians(90), 0, radians(28 if i % 2 else -28)),
                  mat=M_GOLD, mseg=14, nseg=7)


# ==============================================================================
#  FAULD, TASSETS AND BELT
# ==============================================================================

def build_fauld():
    # Overlapping horizontal lames flaring as they descend - the bell that stops
    # the legs reading as stilts.
    lames = [(1.108, 1.036, 0.212, 0.238),
             (1.048, 0.976, 0.226, 0.252),
             (0.988, 0.912, 0.238, 0.266)]
    for i, (z_hi, z_lo, r_hi, r_lo) in enumerate(lames):
        ob = revolve("Fauld_Lame%d" % (i + 1),
                     [(r_hi, z_hi), (r_lo, z_lo), (r_lo - 0.014, z_lo - 0.006),
                      (r_hi - 0.016, z_hi - 0.004)],
                     segments=30, mat=M_STEEL, close_profile=True)
        ob.scale = (1.0, 0.80, 1.0)
        bevel(ob, 0.005, 2)
        # Gold on the top and bottom lame only - rimming all three turned the
        # skirt into a stack of hoops.
        if i != 1:
            rim = add_torus("Fauld_Rim%d" % (i + 1), (0, 0, z_lo), r_lo - 0.004,
                            0.0075, mat=M_GOLD)
            rim.scale = (1.0, 0.80, 1.0)

    skirt = revolve("Mail_Skirt", [(0.232, 0.930), (0.244, 0.870),
                                   (0.248, 0.836), (0.240, 0.828)],
                    segments=26, mat=M_MAIL, close_profile=True)
    skirt.scale = (1.0, 0.80, 1.0)
    displace_noise(skirt, 0.004, 0.10, "MailNoiseSkirt")
    subsurf(skirt, 1)


def build_tassets():
    """The two big thigh plates. Deliberately oversized: at icon scale these and
    the pauldrons are the two shapes that say 'knight'."""
    def tasset_ring(side, z, grow):
        g = (0.930 - z) / 0.240                   # 0 at the belt, 1 at the hem
        half = lerp(0.115, 0.134, smoothstep(g)) + grow
        depth = lerp(0.105, 0.120, g) + grow
        out = lerp(0.0, 0.030, g) * side          # splays outward at the hem
        cx = side * 0.175
        ring = []
        for j in range(15):
            a = lerp(-1.25, 1.25, j / 14.0)
            ring.append(Vector((cx + out + half * sin(a),
                                -depth * cos(a) - 0.012,
                                z + 0.012 * (1.0 - cos(a)))))
        return ring

    for side, tag in ((-1, "R"), (1, "L")):
        # THREE overlapping lames, each stepping 7 mm further out and carrying
        # its own gold rim. As one continuous curved rectangle 24 cm tall this
        # was the largest completely undetailed panel left on the model.
        for li, (ztop, zbot) in enumerate(((0.930, 0.852),
                                           (0.866, 0.780),
                                           (0.794, 0.690))):
            grow = 0.007 * li
            rings = [tasset_ring(side, lerp(ztop, zbot, i / 3.0), grow)
                     for i in range(4)]
            ob = loft("Tasset%d_%s" % (li, tag), rings, mat=M_STEEL, closed=False)
            solidify(ob, 0.014)
            bevel(ob, 0.004, 2)
            tube_along("Tasset%d_Trim_%s" % (li, tag), rings[-1], 0.0072, M_GOLD)

        # Sits on the middle lame's outer face (y ~ -0.132 there), half-sunk.
        studp = Vector((side * 0.199, -0.138, 0.800))
        add_sphere("Tasset_Stud_%s" % tag, studp, 0.026,
                   scale=(1.0, 0.45, 1.0), mat=M_GOLD, u=16, v=8)
        add_gem("Tasset_Gem_%s" % tag, studp + Vector((0, -0.014, 0)),
                0.012, 1, mat=M_RUBY)


def build_belt():
    belt = revolve("Belt", [(0.206, 1.148), (0.222, 1.132), (0.222, 1.086),
                            (0.206, 1.070)], segments=30, mat=M_LEATHER,
                   close_profile=True)
    belt.scale = (1.0, 0.80, 1.0)
    bevel(belt, 0.004, 2)
    for z in (1.148, 1.070):
        r = add_torus("Belt_Rim_%.3f" % z, (0, 0, z), 0.210, 0.0065, mat=M_GOLD_D)
        r.scale = (1.0, 0.80, 1.0)

    buckle = add_box("Belt_Buckle", (0.0, -0.196, 1.109),
                     scale=(0.105, 0.030, 0.086), mat=M_GOLD)
    bevel(buckle, 0.013, 4)
    add_gem("Belt_Gem", (0.0, -0.216, 1.109), 0.026, 1, mat=M_RUBY,
            rot=(0, radians(31), 0))

    # Trophies: gold-capped monster fangs on short chains at his left hip.
    # "Trimmed with the finest gold stolen from the monsters he has slain" -
    # this is the one place that line is literal.
    hip = Vector((0.205, -0.055, 1.075))
    for i, (dx, dz, ln) in enumerate(((-0.028, -0.052, 0.062),
                                      (0.004, -0.070, 0.078),
                                      (0.030, -0.048, 0.055))):
        top = hip + Vector((dx * 0.4, 0.0, 0.0))
        tip = hip + Vector((dx, 0.010, dz - ln))
        for k in range(3):
            add_torus("Trophy_Link_%d_%d" % (i, k),
                      top.lerp(tip, 0.06 + 0.10 * k), 0.010, 0.0034,
                      rot=(radians(90), 0, 0), mat=M_GOLD_D, mseg=12, nseg=6)
        fang_top = top.lerp(tip, 0.34)
        capsule("Trophy_Fang_%d" % i, fang_top, tip, 0.017, 0.000,
                mat=M_PAGE, segs=10, cap1=False)
        add_torus("Trophy_FangCap_%d" % i, fang_top + Vector((0, 0, -0.006)),
                  0.016, 0.006, mat=M_GOLD, mseg=14, nseg=7)


# ==============================================================================
#  THE TEMPLAR EMBLEM - gold T with rubies set into it
# ==============================================================================

def build_emblem():
    # Crossbar and stem are separate curved plates so each hugs the chest at its
    # own height; a single flat T would lift off the keel at the centre.
    # Stand-off has to clear the plackart AND its rim, measured against the
    # emblem's INNER face, not its outer one: surface_plate solidifies inward,
    # so a plate at offset 0.036 with 0.020 of thickness reaches back to 0.016
    # and buries itself in the plackart (0.012..0.028) - which is what made the
    # stem look like it was melting into the belly.
    # keel_scale 0.40 below: the breastplate has a 44 mm central keel ridge, and
    # a plate conformed to ALL of it comes out visibly bowed - the crossbar ends
    # curve away and the stem bulges, which reads as a warped T. Following only
    # 40% of the keel keeps it recognisably flat while still sitting on the
    # chest. OFF is raised to keep clearance over the keel it no longer follows.
    OFF, EMB_T = 0.050, 0.014
    # One continuous surface: crossbar, stem and flared foot as a single
    # stepped outline. The near-duplicate z pairs (1.392/1.400 etc.) are the
    # vertical walls of the step; the bevel rounds them.
    surface_plate_rows("Emblem_T", THETA_FRONT, [
        (1.168, 0.090),      # splayed foot
        (1.232, 0.070),
        (1.252, 0.048),
        (1.392, 0.048),      # stem
        (1.400, 0.155),      # step out to the crossbar
        (1.476, 0.155),
    ], offset=OFF, thickness=EMB_T, mat=M_GOLD, seg_t=20, bulge=0.0)

    # Half-sunk into the plate's OUTER face (surface_plate leaves that at
    # `offset`), so the stones sit in the gold rather than hovering over it.
    for i, x in enumerate((-0.112, 0.0, 0.112)):
        th = THETA_FRONT + theta_span_for_width(1.437, x, OFF + 0.008)
        add_gem("Emblem_Ruby_Bar%d" % i, torso_point(th, 1.437, OFF + 0.008),
                0.021, 1, mat=M_RUBY, rot=(0, radians(37), radians(20 * i)))
    for i, z in enumerate((1.330, 1.250)):
        add_gem("Emblem_Ruby_Stem%d" % i, torso_point(THETA_FRONT, z, OFF + 0.008),
                0.019, 1, mat=M_RUBY, rot=(0, radians(29), radians(15 + 30 * i)))


# ==============================================================================
#  LIMB PLUMBING
# ==============================================================================

def limb(name, p0, p1, profile, mat=None, segs=18, cap0=True, cap1=True,
         coll=None, cap_steps=4, ridge_dir=None, ridge_h=0.011, ridge_w=0.40,
         flutes=0, flute_h=0.0022):
    """Lathed limb segment between two points with a variable radius.

    `profile` is [(t, radius), ...] with t running 0..1 from p0 to p1 - which is
    how the calf gets its bulge and the thigh its taper. A plain two-entry
    profile is just a tapered capsule.
    """
    p0, p1 = Vector(p0), Vector(p1)
    axis = p1 - p0
    length = axis.length
    r_first, r_last = profile[0][1], profile[-1][1]
    prof = []
    if cap0:
        for k in range(cap_steps, 0, -1):
            a = 0.5 * pi * k / cap_steps
            prof.append((r_first * cos(a), -r_first * sin(a)))
    for t, r in profile:
        prof.append((r, length * t))
    if cap1:
        for k in range(1, cap_steps + 1):
            a = 0.5 * pi * k / cap_steps
            prof.append((r_last * cos(a), length + r_last * sin(a)))
    # Ridge and fluting are modulations of the limb's OWN cross-section, not
    # separate objects laid on top. A thin swept tube riding the surface reads
    # as a wire stuck to the armour - which is exactly what the shin ridge and
    # the arm ribs looked like in close-up. A gaussian swell in the radius reads
    # as a ridge forged into the plate: no seam, and nothing protruding.
    quat = axis.to_track_quat('Z', 'Y')
    a0 = 0.0
    if ridge_dir is not None:
        d_local = quat.inverted() @ Vector(ridge_dir)
        a0 = math.atan2(d_local.y, d_local.x)

    def radial(a):
        v = 0.0
        if ridge_dir is not None:
            d = (a - a0 + pi) % (2.0 * pi) - pi
            v += ridge_h * math.exp(-(d / ridge_w) ** 2)
        if flutes:
            v += flute_h * cos(flutes * a)
        return v

    ob = revolve(name, prof, segments=segs, mat=mat, coll=coll,
                 radial_fn=(radial if (ridge_dir is not None or flutes) else None))
    ob.location = p0
    ob.rotation_euler = quat.to_euler()
    return ob


def profile_radius(profile, t):
    """Radius of a limb `profile` ([(t, r), ...]) at parameter t."""
    for (ta, ra), (tb, rb) in zip(profile, profile[1:]):
        if ta <= t <= tb:
            return lerp(ra, rb, (t - ta) / max(1e-6, tb - ta))
    return profile[0][1] if t < profile[0][0] else profile[-1][1]


def plate_lame(name, p0, p1, profile, t0, t1, mat, grow_lo=0.010, grow_hi=0.003,
               segs=22, steps=4):
    """A short armour plate lapping over a limb between t0 and t1.

    Two jobs at once. Visually it breaks a lathed limb into distinct overlapping
    plates instead of one continuous tube. Structurally the flare at its LOWER
    edge (grow_lo > grow_hi) means it laps OVER whatever sits below it, so when
    the joint bends the plates slide past one another instead of opening a gap.

    Built as a closed shell - outer wall out, inner wall back - so it stays
    manifold.
    """
    p0, p1 = Vector(p0), Vector(p1)
    axis = p1 - p0
    length = axis.length
    outer, inner = [], []
    for i in range(steps + 1):
        f = i / steps
        t = lerp(t0, t1, f)
        r = profile_radius(profile, t)
        outer.append((r + lerp(grow_lo, grow_hi, f), length * t))
        inner.append((r - 0.004, length * t))
    ob = revolve(name, outer + list(reversed(inner)), segments=segs, mat=mat,
                 close_profile=True)
    ob.location = p0
    ob.rotation_euler = axis.to_track_quat('Z', 'Y').to_euler()
    bevel(ob, 0.003, 2)
    return ob


def limb_rivets(name, p0, p1, side_dir, profile, mat, count=3,
                t0=0.24, t1=0.76, r=0.0085, lift=0.003):
    """A line of rivets down one side of a limb, riding its surface.

    Rolled edges and rivet lines are what stop a lathed tube reading as pipe.
    Real plate is riveted at every strap and lame boundary, and at game
    distance the rivet line is the detail that says "forged" rather than "cast".
    """
    p0, p1 = Vector(p0), Vector(p1)
    axis = p1 - p0
    n = axis.normalized()
    d = Vector(side_dir)
    d = d - n * d.dot(n)
    if d.length < 1e-6:
        return
    d.normalize()
    for k in range(count):
        t = t0 if count == 1 else lerp(t0, t1, k / (count - 1.0))
        p = p0 + axis * t + d * (profile_radius(profile, t) + lift)
        add_gem("%s%d" % (name, k), p, r, 1, mat=mat)


def limb_ridge(name, p0, p1, side_dir, profile, mat, rib_r=0.010,
               t0=0.06, t1=0.94, samples=7, lift=0.004):
    """Raised rib running along one side of a limb, riding its surface.

    Limbs built as lathed tubes are smooth cylinders and carry no internal line
    at all - in a clay render the legs and arms read as pipes with bracelets on
    them. A shin ridge or an outer arm rib gives each segment its own drawing,
    the same job the fluting does on the pauldrons.
    """
    p0, p1 = Vector(p0), Vector(p1)
    axis = p1 - p0
    n = axis.normalized()
    d = Vector(side_dir)
    d = d - n * d.dot(n)
    if d.length < 1e-6:
        return None
    d.normalize()

    pts, taper = [], []
    for i in range(samples):
        t = lerp(t0, t1, i / (samples - 1.0))
        pts.append(p0 + axis * t + d * (profile_radius(profile, t) + lift))
        taper.append(0.32 + 0.68 * sin(pi * (i / (samples - 1.0))) ** 0.65)
    return tube_along(name, pts, rib_r, mat, segs=8, taper=taper)


def band(name, p_at, along, radius, thickness, mat, segs=22, scale=(1, 1, 1)):
    """Gold band clasping a limb, oriented across the limb's axis. Every plate
    junction on the arms and legs gets one - they are the joints in the drawing."""
    ob = add_torus(name, p_at, radius, thickness, mat=mat, mseg=segs, nseg=9)
    ob.rotation_euler = Vector(along).to_track_quat('Z', 'Y').to_euler()
    ob.scale = scale
    return ob


def superellipse_ring(cx, cy, cz, w, h, axis='Y', n=18, power=0.62, crest=0.0):
    """Rounded-rectangle cross-section. `power` below 1 squares it off; used for
    sabatons and gauntlet cuffs, where a pure ellipse reads as a slipper."""
    pts = []
    for i in range(n):
        a = 2 * pi * i / n
        c, s = cos(a), sin(a)
        u = w * math.copysign(abs(c) ** power, c)
        v = h * math.copysign(abs(s) ** power, s)
        # Instep crest: a raised ridge along the top of the section. Integrated
        # into the section rather than laid on as a tube, same reasoning as the
        # shin ridge.
        if crest and s > 0.0:
            v += crest * (s ** 3)
        if axis == 'Y':
            pts.append(Vector((cx + u, cy, cz + v)))
        elif axis == 'Z':
            pts.append(Vector((cx + u, cy + v, cz)))
        else:
            pts.append(Vector((cx, cy + u, cz + v)))
    return pts


# ==============================================================================
#  PAULDRONS
#
#  Widest thing on the model and therefore the thing that names him at icon
#  size. Built in a per-shoulder frame: `alpha` runs from the top of the shoulder
#  down, `beta` runs around the arm (90 deg = the outer face, 270 deg = the neck
#  side, where the haute-piece stands up).
# ==============================================================================

def pauldron_frame(side):
    """Per-shoulder frame. MUST mirror across X between the two sides.

    B was originally just U.cross(A), which is NOT mirror-symmetric: for the
    right shoulder it comes out outward-and-down (correct), but for the left it
    comes out INWARD-and-up. Everything positioned by a beta angle - the spike,
    the rondel and its ruby, the haute-piece - therefore landed somewhere
    different on each side. Most visibly the left haute-piece was flung outward
    and down off the shoulder, where it read as a fourth limb.
    """
    C = Vector((side * 0.250, 0.000, 1.498))
    U = Vector((side * 0.36, 0.0, 0.93)).normalized()   # up and outward
    A = Vector((0.0, 1.0, 0.0))                         # toward the back
    B = U.cross(A).normalized() * -side                 # outer and downward
    return C, U, A, B


def p_point(C, U, A, B, R, alpha, beta, grow=0.0):
    d = (cos(alpha) * U) + sin(alpha) * (cos(beta) * A + sin(beta) * B)
    return C + Vector((d.x * (R[0] + grow),
                       d.y * (R[1] + grow),
                       d.z * (R[2] + grow)))


def build_pauldron(side, tag):
    C, U, A, B = pauldron_frame(side)
    # Flatter over the crown and a touch wider than the original (0.168, 0.150,
    # 0.140). A near-spherical cop is exactly what read as a balloon with a
    # spike in it once the gold trim was taken away.
    R = (0.174, 0.158, 0.122)

    def shell(name, a0, a1, grow, mat, rows=5, cols=44, flare=0.0):
        rings = []
        for i in range(rows + 1):
            t = i / rows
            a = lerp(a0, a1, t)
            g = grow + flare * t
            rings.append([p_point(C, U, A, B, R, a, 2 * pi * j / cols,
                              g + 0.0050 * cos(5.0 * (2 * pi * j / cols))
                              * sin(min(a, pi * 0.5)))
                          for j in range(cols)])
        ob = loft(name, rings, mat=mat, closed=True,
                  cap_start=(a0 < 0.15), cap_end=False)
        solidify(ob, 0.016)
        bevel(ob, 0.005, 2)
        return ob, rings

    # Main cop, flaring at its rim so it is a bell rather than a ball.
    _, cop_rings = shell("Pauldron_Cop_%s" % tag, radians(3), radians(96),
                         0.0, M_STEEL, rows=6, flare=0.022)
    tube_along("Pauldron_CopRim_%s" % tag, cop_rings[-1] + [cop_rings[-1][0]],
               0.0095, M_GOLD)

    # Two skirt lames stepping outward and down.
    for k, (a0, a1, g) in enumerate(((radians(92), radians(116), 0.020),
                                     (radians(112), radians(137), 0.040))):
        _, rr = shell("Pauldron_Lame%d_%s" % (k + 1, tag), a0, a1, g,
                      M_STEEL_L, rows=3, flare=0.016)
        tube_along("Pauldron_LameRim%d_%s" % (k + 1, tag), rr[-1] + [rr[-1][0]],
                   0.0080, M_GOLD if k else M_GOLD_D)

    # Fluting is folded into the cop shell above (a cosine on the radius),
    # not laid on as separate swept tubes. As tubes they read as wires
    # glued to the shoulder.

    # Haute-piece: the flange that stands up on the neck side to catch a blade
    # sliding toward the throat. Reads as an aggressive upward hook in profile.
    inner, outer = [], []
    for j in range(13):
        b = radians(lerp(207, 333, j / 12.0))
        edge = 1.0 - abs(j / 12.0 - 0.5) * 2.0        # tallest in the middle
        inner.append(p_point(C, U, A, B, R, radians(64), b, 0.004))
        # Kept low deliberately: taller flanges crowded right up beside the
        # helmet and read as a second pair of horns next to the face.
        outer.append(p_point(C, U, A, B, R, radians(50 - 10 * edge), b,
                             0.020 + 0.030 * edge))
    hp = loft("Pauldron_Haute_%s" % tag, [inner, outer], mat=M_STEEL,
              closed=False)
    solidify(hp, 0.014)
    bevel(hp, 0.005, 2)
    tube_along("Pauldron_HauteRim_%s" % tag, outer, 0.0075, M_GOLD)

    # Outward spike on the shoulder crown. Pure silhouette work.
    #
    # The tip is given as an explicit world offset rather than as a second
    # (alpha, beta) sample. Sampling the frame at a SMALLER alpha for the tip
    # made the spike lean inboard as it rose, and from the side it looked like a
    # horn growing out of the helmet.
    base = p_point(C, U, A, B, R, radians(31), radians(86), 0.010)
    tip = base + Vector((side * 0.135, -0.025, 0.205))
    limb("Pauldron_Spike_%s" % tag, base, tip, [(0.0, 0.036), (0.55, 0.020),
                                                (1.0, 0.000)],
         mat=M_GOLD, segs=14, cap1=False)
    add_torus("Pauldron_SpikeCollar_%s" % tag, base, 0.038, 0.010,
              rot=(tip - base).to_track_quat('Z', 'Y').to_euler(),
              mat=M_GOLD_D, mseg=16, nseg=8)

    # Rondel: a gold disc with a ruby over the joint, where a real harness has
    # the besagew strap.
    rp = p_point(C, U, A, B, R, radians(72), radians(150), 0.022)
    disc = add_cyl("Pauldron_Rondel_%s" % tag, rp, 0.046, 0.046, 0.014,
                   mat=M_GOLD, segs=20)
    disc.rotation_euler = (rp - C).to_track_quat('Z', 'Y').to_euler()
    bevel(disc, 0.005, 3)
    add_gem("Pauldron_RondelGem_%s" % tag,
            rp + (rp - C).normalized() * 0.014, 0.017, 1, mat=M_RUBY)


# ==============================================================================
#  ARMS
# ==============================================================================

def build_arm(side, tag):
    sh = SHOULDER_R if side < 0 else SHOULDER_L
    el = ELBOW_R if side < 0 else ELBOW_L
    wr = WRIST_R if side < 0 else WRIST_L

    # Dark mail sleeve under the plate, showing at the armpit and inner elbow -
    # the fix for "floating plates with nothing behind them".
    voider = limb("Arm_Voider_%s" % tag, sh + Vector((0, 0, 0.03)),
                  wr, [(0.0, 0.070), (0.5, 0.058), (1.0, 0.050)],
                  mat=M_MAIL, segs=16)
    displace_noise(voider, 0.003, 0.09, "MailNoiseArm%s" % tag)

    # Rerebrace (upper arm) and vambrace (forearm), each slightly barrelled.
    rere_a, rere_b = sh + (el - sh) * 0.10, el - (el - sh) * 0.06
    rere_prof = [(0.0, 0.076), (0.45, 0.081), (1.0, 0.068)]
    limb("Rerebrace_%s" % tag, rere_a, rere_b, rere_prof, mat=M_STEEL,
         segs=28, ridge_dir=Vector((side, 0, 0)), ridge_h=0.009, ridge_w=0.40,
         flutes=8, flute_h=0.0018)
    vamb_a, vamb_b = el + (wr - el) * 0.16, wr
    vamb_prof = [(0.0, 0.070), (0.4, 0.072), (1.0, 0.058)]
    limb("Vambrace_%s" % tag, vamb_a, vamb_b, vamb_prof, mat=M_STEEL,
         segs=28, ridge_dir=Vector((side, -0.35, 0)), ridge_h=0.009,
         ridge_w=0.38, flutes=8, flute_h=0.0018)
    # Lapping plates. The rerebrace's lower plate laps down toward the elbow
    # and the vambrace's upper plate laps up to meet it, so the pair overlaps
    # across the joint instead of two tube ends butting together.
    plate_lame("Rerebrace_Lame_%s" % tag, rere_a, rere_b, rere_prof,
               0.54, 1.02, M_STEEL_L)
    plate_lame("Vambrace_Lame_%s" % tag, vamb_a, vamb_b, vamb_prof,
               -0.02, 0.40, M_STEEL_L, grow_lo=0.003, grow_hi=0.010)


    # Rolled edges at every plate boundary, and rivet lines down the outer ribs.
    band("Rerebrace_RollTop_%s" % tag, rere_a, rere_b - rere_a,
         profile_radius(rere_prof, 0.0) + 0.004, 0.0055, M_STEEL_L)
    band("Rerebrace_RollBot_%s" % tag, rere_b, rere_b - rere_a,
         profile_radius(rere_prof, 1.0) + 0.004, 0.0055, M_STEEL_L)
    band("Vambrace_RollTop_%s" % tag, vamb_a, vamb_b - vamb_a,
         profile_radius(vamb_prof, 0.0) + 0.004, 0.0055, M_STEEL_L)
    band("Vambrace_RollBot_%s" % tag, vamb_b, vamb_b - vamb_a,
         profile_radius(vamb_prof, 1.0) + 0.004, 0.0055, M_STEEL_L)
    # lift clears the rib the rivets sit on, otherwise they are buried in it.
    limb_rivets("Rerebrace_Rivet_%s" % tag, rere_a, rere_b, Vector((side, 0, 0)),
                rere_prof, M_GOLD_D, count=3, t0=0.26, t1=0.74, r=0.0058,
                lift=0.005)
    limb_rivets("Vambrace_Rivet_%s" % tag, vamb_a, vamb_b,
                Vector((side, -0.35, 0)), vamb_prof, M_GOLD_D,
                count=3, t0=0.26, t1=0.76, r=0.0055, lift=0.005)

    # One band per plate boundary, no more. Five rings per arm read as bangles.
    band("Rerebrace_Band_%s" % tag, sh.lerp(el, 0.20), el - sh, 0.082, 0.0075, M_GOLD)
    band("Vambrace_Band_%s" % tag, el.lerp(wr, 0.22), wr - el, 0.074, 0.0075, M_GOLD)

    # Couter: elbow cop plus the fan wing that makes an elbow read as armour
    # rather than as a knuckle.
    cop = add_sphere("Couter_%s" % tag, el, 0.084, scale=(1.0, 1.0, 0.86),
                     mat=M_STEEL, u=20, v=12)
    bevel(cop, 0.004, 2)
    out = Vector((side, 0.0, -0.20)).normalized()
    fan_in, fan_out = [], []
    for j in range(9):
        t = j / 8.0
        ang = lerp(-1.15, 1.15, t)
        axis_d = (wr - el).normalized()
        swing = (out * cos(ang) + axis_d * sin(ang) * 0.55).normalized()
        fan_in.append(el + swing * 0.062)
        fan_out.append(el + swing * (0.125 - 0.030 * abs(ang)))
    fan = loft("Couter_Fan_%s" % tag, [fan_in, fan_out], mat=M_STEEL,
               closed=False)
    solidify(fan, 0.013)
    bevel(fan, 0.004, 2)
    tube_along("Couter_FanRim_%s" % tag, fan_out, 0.0072, M_GOLD)
    add_gem("Couter_Gem_%s" % tag, el + out * 0.086, 0.016, 1, mat=M_RUBY)


# ==============================================================================
#  GAUNTLETS
# ==============================================================================

def oriented_box(name, centre, size, fwd, up, mat, bevel_w=0.005, segs=3,
                 coll=None):
    """Rounded box aligned to an arbitrary frame: local Y along `fwd`, local Z
    along `up`. The workhorse for armour lames, which are plates, not tubes."""
    f = Vector(fwd).normalized()
    u = Vector(up)
    u = (u - f * u.dot(f))
    u = u.normalized() if u.length > 1e-9 else Vector((0, 0, 1))
    s = f.cross(u).normalized()
    ob = add_box(name, centre, scale=size, mat=mat, coll=coll)
    # Columns are the images of local X/Y/Z. s = f x u makes (s, f, u)
    # right-handed, so to_euler() is a true rotation and not a mirror.
    ob.rotation_euler = Matrix((s, f, u)).transposed().to_euler()
    bevel(ob, bevel_w, segs)
    return ob


def finger_plates(name, pts, widths, thicks, mat, up_dir):
    """A finger built as overlapping LAMES, not as beads.

    The first version chained capsules with a knuckle sphere at each joint
    scaled to 1.12x the segment radius. Every joint bulged and the hand read as
    a string of pearls. Real gauntlet fingers are stacked plates: flat-topped,
    wider than they are thick, each overlapping the next.

    `up_dir` is the plate normal and is passed in EXPLICITLY. The second version
    derived it as radial-from-an-axis, which is correct for fingers wrapping a
    grip cylinder but degenerate for an open flat hand: there the radial vector
    comes out parallel to the finger itself, oriented_box's orthogonalisation
    collapses to zero, and every lame silently fell back to world Z - standing
    the plates on edge as a row of jagged teeth.
    """
    made = []
    for i in range(len(pts) - 1):
        a, b = Vector(pts[i]), Vector(pts[i + 1])
        d = b - a
        if d.length < 1e-6:
            continue
        mid = (a + b) * 0.5
        # 1.14 overlap so consecutive plates tuck under one another rather than
        # leaving a gap at every joint.
        made.append(oriented_box("%s_Lame%d" % (name, i), mid,
                                 (widths[i], d.length * 1.14, thicks[i]),
                                 d, up_dir, mat, bevel_w=thicks[i] * 0.42))
    return made


def build_gauntlet_sword(side, tag, grip_c, grip_dir, hand_out):
    """Right hand, closed around the sword grip."""
    wr = WRIST_R
    fwd = (grip_c - wr).normalized() if (grip_c - wr).length > 1e-4 \
        else Vector((0, -1, 0))

    # Cuff: a long, gently flaring bracer up the forearm. The previous version
    # was 55 mm long and swelled to an 80 mm radius, which is a ball - it was
    # literally the blob that swallowed the whole hand.
    fore = (wr - ELBOW_R).normalized()
    cuff_a = wr - fore * 0.078
    cuff_b = wr + fore * 0.030      # reaches down to meet the metacarpal plate
    cuff = limb("Gauntlet_Cuff_%s" % tag, cuff_a, cuff_b,
                [(0.0, 0.048), (0.55, 0.054), (1.0, 0.058)],
                mat=M_STEEL, segs=18)
    bevel(cuff, 0.004, 2)
    # Rim at the HAND end of the cuff, not the elbow end. Cuff and fist are
    # naturally similar widths, so without a break at the wrist the forearm and
    # the hand fuse into one continuous smooth mass with no articulation.
    #
    # Aligned to the CUFF's own axis too: the cuff cants toward the grip, and
    # orienting the ring to the forearm left it 18 mm proud on one side.
    band("Gauntlet_CuffRim_%s" % tag, cuff_b, cuff_b - cuff_a, 0.061, 0.0090,
         M_GOLD)

    across = grip_dir.cross(hand_out).normalized()

    def gp(phi_deg, radius, along):
        """Point on a cylinder around the grip. Building the fist by sweeping an
        angle guarantees every lame hugs the grip; placing them by hand-written
        offsets is what let them drift inside the cuff and disappear."""
        a = radians(phi_deg)
        return (grip_c + grip_dir * along
                + hand_out * (radius * cos(a)) + across * (radius * sin(a)))

    def wrap_lame(name, phi_a, phi_b, rad, along, width, thick, mat, steps=5):
        """A CURVED lame hugging the grip: lofted along the wrap arc with a
        rounded, tapered cross-section.

        These were oriented boxes before. Four fingers of three boxes each
        produced a 4x3 grid of rectangles on a rectangular core - the hand read
        as a radiator, not a fist. Curved plates with rounded ends read as
        articulated fingers closed round a grip.
        """
        rings = []
        for i in range(steps + 1):
            t = i / steps
            a = radians(lerp(phi_a, phi_b, t))
            rdir = hand_out * cos(a) + across * sin(a)
            centre = grip_c + grip_dir * along + rdir * rad
            w = width * (0.72 + 0.28 * sin(pi * t))
            h = thick * (0.62 + 0.38 * sin(pi * t))
            ring = []
            for k in range(10):
                ang = 2 * pi * k / 10
                cs, sn = cos(ang), sin(ang)
                ring.append(centre
                            + grip_dir * (w * math.copysign(abs(cs) ** 0.6, cs))
                            + rdir * (h * math.copysign(abs(sn) ** 0.6, sn)))
            rings.append(ring)
        ob = loft(name, rings, mat=mat, closed=True, cap_start=True,
                  cap_end=True)
        bevel(ob, thick * 0.30, 2)
        return ob

    # Rounded fist mass, lofted around the grip axis - not a box. Tapered at
    # both ends so it reads as a closed hand rather than a block.
    core_rings = []
    for (al, r_out, r_ac) in ((-0.052, 0.022, 0.020), (-0.034, 0.037, 0.033),
                              (-0.010, 0.043, 0.038), (0.016, 0.042, 0.037),
                              (0.038, 0.034, 0.030), (0.054, 0.019, 0.017)):
        ring = []
        for k in range(20):
            a = 2 * pi * k / 20
            ring.append(grip_c + grip_dir * al
                        + hand_out * (r_out * cos(a)) + across * (r_ac * sin(a)))
        core_rings.append(ring)
    loft("Fist_Core_%s" % tag, core_rings, mat=M_STEEL, closed=True,
         cap_start=True, cap_end=True)

    # Back-of-hand plate spanning all four knuckles.
    oriented_box("Gauntlet_Back_%s" % tag, gp(0, 0.046, 0.002),
                 (0.048, 0.086, 0.015), grip_dir, hand_out, M_STEEL_L,
                 bevel_w=0.007, segs=4)
    for k in range(4):
        along = lerp(-0.034, 0.034, k / 3.0)
        b = add_sphere("Knuckle_Dome_%s%d" % (tag, k), gp(34, 0.049, along),
                       0.012, scale=(1.0, 1.0, 0.5), mat=M_GOLD, u=12, v=8)
        b.rotation_euler = (gp(34, 0.049, along) - gp(34, 0.0, along)
                            ).to_track_quat('Z', 'Y').to_euler()

    # Four fingers, three curved lames each, sweeping round the grip.
    for k in range(4):
        along = lerp(-0.034, 0.034, k / 3.0)
        for i, (pa, pb, rad) in enumerate(((22, 70, 0.050),
                                           (72, 120, 0.051),
                                           (122, 168, 0.047))):
            wrap_lame("Finger_%s%d_L%d" % (tag, k, i), pa, pb, rad, along,
                      0.0105, 0.011, M_STEEL_L)

    # Thumb crossing the open side toward the pommel.
    for i, (pa, pb, rad) in enumerate(((300, 258, 0.050), (256, 214, 0.047))):
        wrap_lame("Thumb_%s_L%d" % (tag, i), pa, pb, rad, 0.044 - 0.016 * i,
                  0.014, 0.013, M_STEEL_L)


def build_gauntlet_book(side, tag, palm_c, palm_fwd, palm_up):
    """Left hand, open and flat, carrying the tome on the palm."""
    wr = WRIST_L
    cuff_a = wr - (wr - ELBOW_L).normalized() * 0.045
    cuff_b = wr + palm_fwd * 0.030
    cuff = limb("Gauntlet_Cuff_%s" % tag, cuff_a, cuff_b,
                [(0.0, 0.060), (0.45, 0.078), (1.0, 0.064)],
                mat=M_STEEL, segs=18)
    bevel(cuff, 0.004, 2)
    band("Gauntlet_CuffRim_%s" % tag, cuff_a, cuff_b - cuff_a, 0.066, 0.0085,
         M_GOLD)

    across = palm_fwd.cross(palm_up).normalized()

    # Flat plated palm. Its top face is the surface the tome physically rests
    # on, so BOOK_C is derived from it rather than guessed.
    # Raised 4 mm and lengthened to 0.104 so its top face and front edge both
    # meet the first finger lame. Previously the palm ended at fwd 0.046 with
    # its top at +0.008 while the fingers began at 0.050 and +0.016 - a visible
    # gap in both axes, which is why the fingers looked detached from the hand.
    oriented_box("Gauntlet_Back_%s" % tag, palm_c + palm_up * 0.004,
                 (0.108, 0.104, 0.026), palm_fwd, palm_up, M_STEEL,
                 bevel_w=0.009, segs=4)

    # Fingers RIDE THE UNDERSIDE OF THE TILTED COVER rather than lying flat.
    # BOOK_C sits 0.030 above the palm and the cover's inner face starts at
    # -0.020 in book space, so the surface the fingers must follow is
    # 0.010 + b*TILT; subtract half a lame thickness to get the plate centre.
    def under_cover(b):
        return 0.010 + b * TILT - 0.007

    for k in range(4):
        lat = lerp(-0.042, 0.042, k / 3.0)
        # Stop just inside the cover edge (0.126, not 0.138). Poking past it,
        # separated by visible slots and squared off at the ends, the four lames
        # read as a row of metal teeth clamped on the book.
        bs = (0.042, 0.090, 0.124)
        pts = [palm_c + across * (lat * (1.0 + 0.14 * i))
               + palm_fwd * bs[i] + palm_up * under_cover(bs[i])
               for i in range(3)]
        # Lames slightly WIDER than the 28 mm spacing so they overlap and close
        # the slots between fingers.
        finger_plates("Finger_%s%d" % (tag, k), pts,
                      [0.030, 0.028], [0.015, 0.013], M_STEEL, palm_up)

    # Thumb comes UP over the near half and rests on it - the detail that makes
    # the tome look carried rather than balanced.
    tb = palm_c - across * 0.055
    finger_plates("Thumb_%s" % tag,
                  [tb + palm_fwd * (-0.004) + palm_up * 0.008,
                   tb + across * 0.008 + palm_fwd * (-0.034) + palm_up * 0.030,
                   tb + across * 0.016 + palm_fwd * (-0.060) + palm_up * 0.044],
                  [0.026, 0.023], [0.016, 0.014], M_STEEL, palm_up)


# ==============================================================================
#  LEGS AND SABATONS
# ==============================================================================

def build_leg(side, tag):
    hip = HIP_R if side < 0 else HIP_L
    knee = KNEE_R if side < 0 else KNEE_L
    ankle = ANKLE_R if side < 0 else ANKLE_L

    mail = limb("Leg_Mail_%s" % tag, hip + Vector((0, 0, 0.04)), ankle,
                [(0.0, 0.098), (0.5, 0.080), (1.0, 0.062)],
                mat=M_MAIL, segs=16)
    displace_noise(mail, 0.003, 0.09, "MailNoiseLeg%s" % tag)

    # Cuisse (thigh) - barrelled at the top where the muscle would be.
    cuisse_a = hip + Vector((0, 0, 0.02))
    cuisse_b = knee + (hip - knee) * 0.10
    cuisse_prof = [(0.0, 0.108), (0.35, 0.113), (1.0, 0.092)]
    limb("Cuisse_%s" % tag, cuisse_a, cuisse_b, cuisse_prof, mat=M_STEEL,
         segs=30, ridge_dir=Vector((side * 0.45, -1, 0)), ridge_h=0.010,
         ridge_w=0.38, flutes=8, flute_h=0.0020)
    # Greave (shin) with a calf bulge, then a hard taper into the ankle.
    greave_a = knee - (knee - ankle) * 0.02
    greave_prof = [(0.0, 0.098), (0.28, 0.105), (0.72, 0.082), (1.0, 0.068)]
    limb("Greave_%s" % tag, greave_a, ankle, greave_prof, mat=M_STEEL,
         segs=30, ridge_dir=Vector((0, -1, 0)), ridge_h=0.012, ridge_w=0.34,
         flutes=8, flute_h=0.0020)

    plate_lame("Cuisse_Lame_%s" % tag, cuisse_a, cuisse_b, cuisse_prof,
               0.52, 1.02, M_STEEL_L)
    plate_lame("Greave_Lame_%s" % tag, greave_a, ankle, greave_prof,
               -0.02, 0.34, M_STEEL_L, grow_lo=0.003, grow_hi=0.011)
    plate_lame("Greave_LameLow_%s" % tag, greave_a, ankle, greave_prof,
               0.58, 0.94, M_STEEL_L, grow_lo=0.010, grow_hi=0.004)

    band("Greave_Roll_%s" % tag, greave_a, ankle - greave_a,
         profile_radius(greave_prof, 0.0) + 0.004, 0.0055, M_STEEL_L)
    limb_rivets("Greave_Rivet_%s" % tag, greave_a, ankle, Vector((0, -1, 0)),
                greave_prof, M_GOLD_D, count=4, t0=0.20, t1=0.78, r=0.0058,
                lift=0.006)
    limb_rivets("Cuisse_Rivet_%s" % tag, cuisse_a, cuisse_b,
                Vector((side * 0.55, -1, 0)), cuisse_prof, M_GOLD_D,
                count=2, t0=0.40, t1=0.72, r=0.0058, lift=0.005)
    limb_rivets("Cuisse_LowRivet_%s" % tag, cuisse_a, cuisse_b,
                Vector((side * 0.45, -1, 0)), cuisse_prof, M_GOLD_D,
                count=3, t0=0.60, t1=0.95, r=0.0055, lift=0.005)
    band("Cuisse_Band_%s" % tag, hip.lerp(knee, 0.30), knee - hip, 0.112, 0.0080, M_GOLD_D)
    band("Greave_Band_%s" % tag, knee.lerp(ankle, 0.18), ankle - knee, 0.099, 0.0085, M_GOLD)
    band("Greave_Cuff_%s" % tag, knee.lerp(ankle, 0.94), ankle - knee, 0.062, 0.0080, M_GOLD)

    # Poleyn: knee cop with a side wing.
    cop = add_sphere("Poleyn_%s" % tag, knee, 0.100, scale=(1.0, 1.05, 0.88),
                     mat=M_STEEL, u=20, v=12)
    bevel(cop, 0.004, 2)
    add_sphere("Poleyn_Point_%s" % tag, knee + Vector((0, -0.074, 0.004)),
               0.030, scale=(1.1, 1.3, 0.6), mat=M_STEEL, u=14, v=8)
    out = Vector((side, 0.0, 0.0))
    wing_in, wing_out = [], []
    for j in range(9):
        t = j / 8.0
        ang = lerp(-1.2, 1.2, t)
        swing = (out * cos(ang) + Vector((0, -1, 0)) * sin(ang) * 0.7).normalized()
        wing_in.append(knee + swing * 0.070)
        # Bigger than before (0.140): the wing is the only thing that breaks the
        # leg's silhouette at the knee, and at the old size it stayed inside it.
        wing_out.append(knee + swing * (0.168 - 0.040 * abs(ang)))
    wing = loft("Poleyn_Wing_%s" % tag, [wing_in, wing_out], mat=M_STEEL,
                closed=False)
    solidify(wing, 0.016)
    bevel(wing, 0.004, 2)
    tube_along("Poleyn_WingRim_%s" % tag, wing_out, 0.0075, M_GOLD)
    add_gem("Poleyn_Gem_%s" % tag, knee + Vector((0, -0.100, 0.010)),
            0.017, 1, mat=M_RUBY)


def build_sabaton(side, tag):
    ankle = ANKLE_R if side < 0 else ANKLE_L
    yaw = radians(11) * -side           # toes splayed outward

    # Centre heights are set so (centre_z - half_height) never goes negative -
    # the sole used to dip 5 mm through the floor plane, which would clip the
    # ground in Unity.
    #        y,      half-width, half-height, centre z
    ribs = [(0.082, 0.058, 0.052, 0.062),
            (0.030, 0.076, 0.064, 0.070),
            (-0.048, 0.080, 0.062, 0.067),
            (-0.120, 0.073, 0.052, 0.057),
            (-0.184, 0.058, 0.039, 0.046),
            (-0.232, 0.036, 0.026, 0.037),
            (-0.262, 0.010, 0.008, 0.032)]
    # power 0.58, not 0.66: squarer section. A rounder foot reads as a slipper.
    rings = [superellipse_ring(0.0, y, cz, w, h, axis='Y', n=22, power=0.58,
                               crest=0.011 * max(0.0, 1.0 - abs(y + 0.05) / 0.20))
             for (y, w, h, cz) in ribs]
    foot = loft("Sabaton_%s" % tag, rings, mat=M_STEEL, closed=True,
                cap_start=True, cap_end=True)
    foot.location = (ankle.x, ankle.y, 0.0)
    foot.rotation_euler = (0, 0, yaw)
    bevel(foot, 0.006, 2)
    subsurf(foot, 1)

    # Overlapping toe lames. Each is a partial ring lifted clear of the shell,
    # which is what gives the foot its ribbed, articulated read.
    # Centre heights track the rib table above (both were raised 8 mm to clear
    # the floor); the 1.05 scale lifts each lame proud of the shell so it reads
    # as an overlapping plate instead of a decal painted on the boot.
    for k, (y0, y1, w, h, cz) in enumerate(((0.010, -0.046, 0.084, 0.068, 0.064),
                                            (-0.052, -0.112, 0.080, 0.060, 0.061),
                                            (-0.118, -0.176, 0.070, 0.049, 0.054))):
        w, h = w * 1.05, h * 1.05
        arcs = []
        for (yy, ww, hh, zz) in ((y0, w, h, cz), (y1, w * 0.94, h * 0.9, cz - 0.004)):
            full = superellipse_ring(0.0, yy, zz, ww, hh, axis='Y', n=24, power=0.58)
            # keep only the upper span of the ring - the lame is a cap, not a tube
            arcs.append([full[i % 24] for i in range(3, 10)])
        lame = loft("Sabaton_Lame%d_%s" % (k, tag), arcs, mat=M_STEEL_L,
                    closed=False)
        lame.location = (ankle.x, ankle.y, 0.0)
        lame.rotation_euler = (0, 0, yaw)
        solidify(lame, 0.010)
        bevel(lame, 0.004, 2)

        # Gold piping on each lame's leading edge. This is the foot's gold now:
        # it follows the form instead of sitting on it, which a heel disc and a
        # toe bead emphatically did not.
        rotm = Matrix.Rotation(yaw, 3, 'Z')
        base = Vector((ankle.x, ankle.y, 0.0))
        tube_along("Sabaton_LameTrim%d_%s" % (k, tag),
                   [base + rotm @ p for p in arcs[1]], 0.0055, M_GOLD, segs=8)

    # No gold heel disc and no gold toe bead. Both were bare primitives parked
    # near the foot rather than shaped to it, and they read exactly as reported:
    # golden balls stuck on at odd spots. The lame piping above replaces them -
    # gold that follows the form instead of sitting on top of it.
    #
    # A rectangular sole slab was tried here too and was just as wrong - it
    # protruded past the heel and both sides and read as a plank underfoot. The
    # foot's own lofted shell already gives it a bottom edge.

    # Ankle lame bridging greave to foot. Without it the thin shin visibly
    # floated inside a much wider boot.
    cuff = revolve("Sabaton_Cuff_%s" % tag,
                   [(0.072, 0.212), (0.086, 0.176), (0.094, 0.132),
                    (0.086, 0.116), (0.078, 0.150), (0.066, 0.208)],
                   segments=20, mat=M_STEEL, close_profile=True)
    cuff.location = (ankle.x, ankle.y - 0.008, 0.0)
    bevel(cuff, 0.004, 2)
    band("Sabaton_CuffRim_%s" % tag, (ankle.x, ankle.y - 0.008, 0.208),
         (0, 0, 1), 0.070, 0.0072, M_GOLD)


# ==============================================================================
#  HELMET - Italian barbute, T-shaped face opening, nothing behind it but glow
# ==============================================================================

# Cutters live here: hidden, never exported, but still evaluated by the boolean
# modifiers that reference them. Excluding the collection from the view layer
# instead would drop them out of the depsgraph and silently undo the cut.
COL_CUT = bpy.data.collections.new("Cutters")
SCENE.collection.children.link(COL_CUT)

HELM_CY = -0.006        # the skull sits a touch forward of the neck axis
EYE_Z = 1.824


def build_helmet():
    #      rx,    ry,     z
    prof = [(0.150, 0.160, 1.606),
            (0.156, 0.168, 1.652),
            (0.158, 0.171, 1.706),
            (0.155, 0.168, 1.764),
            (0.147, 0.159, 1.820),
            (0.133, 0.144, 1.872),
            (0.110, 0.119, 1.920),
            (0.074, 0.081, 1.960),
            (0.032, 0.035, 1.984),
            (0.000, 0.000, 1.992)]
    seg = 34
    rings = []
    for (rx, ry, z) in prof:
        if rx < 1e-6:
            rings.append([Vector((0, HELM_CY, z))] * seg)
        else:
            rings.append([Vector((rx * cos(2 * pi * i / seg),
                                  HELM_CY + ry * sin(2 * pi * i / seg), z))
                          for i in range(seg)])
    helm = loft("Helmet", rings, mat=M_STEEL, closed=True, cap_start=True)

    # T-shaped face opening: horizontal eye slot over a vertical nasal gap.
    eye_cut = add_box("Cut_EyeSlot", (0.0, -0.140, EYE_Z),
                      scale=(0.246, 0.320, 0.056), mat=None, coll=COL_CUT)
    nose_cut = add_box("Cut_NasalSlot", (0.0, -0.140, 1.726),
                       scale=(0.064, 0.320, 0.160), mat=None, coll=COL_CUT)
    for c in (eye_cut, nose_cut):
        c.display_type = 'WIRE'
        c.hide_render = True
        m = helm.modifiers.new("Cut_" + c.name, 'BOOLEAN')
        m.operation = 'DIFFERENCE'
        m.solver = 'EXACT'
        m.object = c
    bevel(helm, 0.004, 2, angle=32)

    # The dark inside. Everything that makes the aperture read as a hole rather
    # than as a painted stripe is this object.
    void = add_sphere("Helmet_Void", (0.0, HELM_CY, 1.790), 1.0,
                      scale=(0.139, 0.150, 0.172), mat=M_VOID, u=24, v=14)
    void.name = "Helmet_Void"

    # Eyes. Small, saturated and angled down toward the nasal gap. Big pale
    # ovals read as cartoon eyes; the glow has to look like something burning
    # deep in an empty helmet.
    # Set well forward in the aperture (0.138 rather than 0.122) and a little
    # high. The game camera looks down at ~50 degrees and the brow ridge
    # overhangs the slot, so deeply recessed eyes are shaded out at exactly the
    # angle the player actually sees - and they are his strongest identifier.
    # Angular SLITS, not ellipsoids. A soft round glow reads as a cartoon eye
    # however red it is; a hard-edged wedge canted down toward the nasal gap
    # reads as a scowl. The Y-rotation drops each slit's inner end.
    for side, tag in ((-1, "R"), (1, "L")):
        # A tapered, faceted WEDGE - deep at the nose end, drawn to a point
        # outboard. A flat box reads as a rectangle painted on the visor, which
        # is why the eyes looked like stickers rather than something burning.
        rings = []
        for (dx, hw, hh) in ((0.032, 0.0032, 0.0072),
                             (0.013, 0.0050, 0.0098),
                             (-0.011, 0.0042, 0.0072),
                             (-0.032, 0.0008, 0.0012)):
            rings.append([Vector((dx * -side,
                                  hw * sin(2 * pi * k / 8),
                                  hh * cos(2 * pi * k / 8))) for k in range(8)])
        e = loft("Eye_%s" % tag, rings, mat=M_EYE, closed=True,
                 cap_start=True, cap_end=True, smooth=False)
        e.location = Vector((side * 0.050, HELM_CY - 0.138, EYE_Z + 0.004))
        e.rotation_euler = (0, radians(-30 * side), 0)
        # White-hot core at the deep end, so the glow has a centre.
        add_gem("Eye_Core_%s" % tag,
                Vector((side * 0.036, HELM_CY - 0.140, EYE_Z - 0.001)),
                0.0055, 1, mat=M_EYE_CORE)
    # A much dimmer wash further back in the skull so the slot has depth behind
    # the pupils instead of going flat black either side of them.
    add_sphere("Eye_InnerGlow", (0.0, HELM_CY - 0.052, EYE_Z + 0.002), 1.0,
               scale=(0.072, 0.030, 0.018), mat=M_EYE_DIM, u=16, v=10)

    build_helmet_trim()


def helm_surface(theta, z, offset=0.0):
    """Point on the helmet shell, for laying trim onto it. Radii are lerped from
    the same table the shell was lofted from."""
    tbl = [(1.606, 0.150, 0.160), (1.652, 0.156, 0.168), (1.706, 0.158, 0.171),
           (1.764, 0.155, 0.168), (1.820, 0.147, 0.159), (1.872, 0.133, 0.144),
           (1.920, 0.110, 0.119), (1.960, 0.074, 0.081), (1.992, 0.0, 0.0)]
    z = max(tbl[0][0], min(tbl[-1][0], z))
    rx = ry = 0.0
    for (z0, x0, y0), (z1, x1, y1) in zip(tbl, tbl[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            rx, ry = lerp(x0, x1, t), lerp(y0, y1, t)
            break
    return Vector(((rx + offset) * cos(theta),
                   HELM_CY + (ry + offset) * sin(theta), z))


def build_helmet_trim():
    # Brow: a gold band dipping to a V over the nasal gap. This one shape does
    # more for the character's expression than anything else on the model.
    brow = []
    for i in range(19):
        t = i / 18.0
        th = lerp(radians(-90 - 58), radians(-90 + 58), t)
        dip = 0.056 * (1.0 - abs(t - 0.5) * 2.0) ** 1.5
        brow.append(helm_surface(th, 1.878 - dip, 0.006))
    tube_along("Helmet_Brow", brow, 0.0080, M_GOLD,
               taper=[0.70 + 0.42 * (1 - abs(i / 18.0 - 0.5) * 2) for i in range(19)])

    # Gold edging down both sides of the nasal slot. Kept thin and stopped above
    # the chin: heavier bars turned the face into a birdcage.
    for side in (-1, 1):
        pts = [helm_surface(radians(-90) + side * math.asin(0.036 / 0.15),
                            z, 0.005)
               for z in (1.702, 1.734, 1.766, 1.798)]
        tube_along("Helmet_NasalEdge_%d" % side, pts, 0.0055, M_GOLD_D)

    # Crown circlet at the helmet base - the "king" note.
    circ = add_torus("Helmet_Circlet", (0, HELM_CY, 1.644), 0.156, 0.0105,
                     mat=M_GOLD, mseg=32, nseg=10)
    circ.scale = (1.0, 1.075, 1.0)
    # Generated as MIRRORED PAIRS about the front centreline. Stepping a fixed
    # offset round the circle put the two rubies at 22 and 202 degrees - nowhere
    # near symmetric, which is exactly what reads as "the rubies round his neck
    # are not symmetrical".
    for k, (off_deg, ruby) in enumerate(((22.5, True), (67.5, False),
                                         (112.5, False), (157.5, True))):
        for sgn in (-1, 1):
            th = THETA_FRONT + sgn * radians(off_deg)
            add_gem("Helmet_CircletGem_%d_%s" % (k, "L" if sgn > 0 else "R"),
                    helm_surface(th, 1.644, 0.016), 0.014, 1,
                    mat=M_RUBY if ruby else M_GOLD)

    # Medial comb, brow over the crown to the nape. Sampled off the real helmet
    # profile rather than off an idealised ellipse: the helmet is flat-sided low
    # down, so an elliptical path sank inside the shell and the front of the
    # comb surfaced through the face opening as a gold spur.
    comb = [helm_surface(THETA_FRONT, z, 0.010) for z in (1.884, 1.922, 1.952)]
    comb += [Vector((0.0, HELM_CY - 0.018, 1.990)),
             Vector((0.0, HELM_CY + 0.018, 1.988))]
    comb += [helm_surface(THETA_BACK, z, 0.010)
             for z in (1.952, 1.918, 1.868, 1.808, 1.742, 1.686)]
    # Built as a standing FIN rooted in the shell, not as a swept tube. A tube
    # of constant radius laid over a curved dome reads as a wire bent round the
    # helmet; a fin reads as a ridge forged into it.
    nc = len(comb) - 1
    centre = Vector((0.0, HELM_CY, 1.790))
    base, top = [], []
    for i, p in enumerate(comb):
        nrm = p - centre
        nrm.x = 0.0
        nrm.normalize()
        root = p - nrm * 0.010                       # back onto the shell
        h = 0.004 + 0.030 * sin(pi * i / nc) ** 0.6
        base.append(root - nrm * 0.010)              # buried, so no seam shows
        top.append(root + nrm * h)
    fin = loft("Helmet_Comb", [base, top], mat=M_STEEL, closed=False)
    solidify(fin, 0.017)
    bevel(fin, 0.004, 2)
    tube_along("Helmet_CombGold", top, 0.0048, M_GOLD_D,
               taper=[0.35 + 0.65 * sin(pi * i / nc) for i in range(nc + 1)])

    # No dome flutes. Swept tubes on the crown read as scratches; the helmet
    # already carries the comb, brow, circlet, rivets and rondels.

    # Rivets around the helmet's lower edge, just above the circlet.
    for k, off_deg in enumerate((18.0, 54.0, 90.0, 126.0, 162.0)):
        for sgn in (-1, 1):
            th = THETA_FRONT + sgn * radians(off_deg)
            add_gem("Helmet_Rivet_%d_%s" % (k, "L" if sgn > 0 else "R"),
                    helm_surface(th, 1.680, 0.005), 0.0060, 1, mat=M_GOLD_D)

    # Cheek rondels over the (imaginary) pivot rivets.
    for side, tag in ((-1, "R"), (1, "L")):
        p = helm_surface(0.0 if side > 0 else pi, 1.742, 0.004)
        d = add_cyl("Helmet_Rondel_%s" % tag, p, 0.032, 0.032, 0.012,
                    rot=(0, radians(90), 0), mat=M_GOLD, segs=16)
        bevel(d, 0.004, 3)
        add_gem("Helmet_RondelGem_%s" % tag, p + Vector((side * 0.008, 0, 0)),
                0.013, 1, mat=M_RUBY)


# ==============================================================================
#  PLUME - golden horsehair crest
# ==============================================================================

def build_plume():
    socket = revolve("Plume_Socket", [(0.030, 1.958), (0.042, 1.982),
                                      (0.046, 2.002), (0.034, 2.004),
                                      (0.030, 1.986)], segments=18, mat=M_GOLD,
                   close_profile=True)
    bevel(socket, 0.004, 2)

    # Built from flat CLUMPS, not round strands. Nineteen tapering tubes read
    # as combed hair - a ponytail hanging off the back of the helmet. A horsehair
    # crest is a thin fin standing in the sagittal plane, so each clump is a
    # blade: thin across X, deep perpendicular to its own arc, tapering to a point.
    clumps = 9
    X = Vector((1.0, 0.0, 0.0))
    for i in range(clumps):
        u = i / (clumps - 1.0)
        lateral = lerp(-0.052, 0.052, u)
        # Centre clumps longest - that is what makes a crest read as a crest
        # rather than as a fan.
        length = 1.0 - 0.24 * (abs(u - 0.5) * 2.0) ** 1.4
        curl = 1.0 + 0.16 * sin(u * 7.3)          # per-clump variation
        steps = 12
        path = [Vector((
            lateral * (0.55 + 0.55 * (k / steps)),
            HELM_CY + 0.015 + 0.470 * length * ((k / steps) ** 1.02),
            1.995 + 0.215 * sin(pi * (k / steps) * 0.78)
            - 0.445 * length * curl * ((k / steps) ** 2.25)))
            for k in range(steps + 1)]

        rings = []
        for k, p in enumerate(path):
            t = k / steps
            tan = (path[min(k + 1, steps)] - path[max(k - 1, 0)]).normalized()
            nrm = tan.cross(X).normalized()       # in-plane, across the arc
            w = 0.052 * (1.0 - 0.94 * t ** 1.25) + 0.003
            thin = 0.0125 * (1.0 - 0.55 * t)
            rings.append([p + X * thin + nrm * w, p - X * thin + nrm * w,
                          p - X * thin - nrm * w, p + X * thin - nrm * w])
        cl = loft("Plume_Clump_%02d" % i, rings,
                  mat=M_GOLD if i % 3 == 0 else M_GOLD_D,
                  closed=True, cap_start=True, cap_end=True)
        bevel(cl, 0.004, 2)


# ==============================================================================
#  CAPE - vivid slightly-dark blue, gold Templar T on the back
# ==============================================================================

# Dense enough to be smooth WITHOUT a subdivision modifier. That is deliberate:
# Catmull-Clark pulls fold crests inward by a good fraction of the fold
# amplitude, and the gold emblem - which is generated from the analytic surface,
# not from the subdivided mesh - ended up floating off the cloth as a result.
# Raised to 28x64 so the sharp fold valleys below actually resolve.
CAPE_ROWS, CAPE_COLS = 28, 64


def cape_point(u, v):
    """Parametric cape. u runs edge-to-edge, v runs shoulder-to-hem.

    Three things are happening at once: the sheet widens and falls back as it
    descends, the whole thing sways to his left as if caught by wind, and a
    standing-wave fold pattern is layered across u so it is cloth and not a cone.
    """
    s = (u - 0.5) * 2.0                       # -1 .. 1
    ev = smoothstep(v)
    # Hem sits ~0.15 clear of the ground. The fold and tear terms below subtract
    # up to 0.145 from this, and at the old value of 0.042 the deepest tatters
    # ended at z = -0.12 - straight through the floor plane.
    z = lerp(1.585, 0.190, v ** 0.92)
    half = lerp(0.205, 0.455, v ** 0.72)
    # ybase starts at 0.150, not 0.100. The backplate's rear surface at the
    # collar sits at y = 0.135, so the old top ring was generated 35 mm INSIDE
    # the cuirass and the cape appeared to erupt out of the armour.
    ybase = lerp(0.150, 0.440, v ** 0.98)
    # Hard clamp against the torso's OWN rear surface. The cuirass is deepest at
    # the chest (z ~1.50, back face at y = 0.177), deeper than at the collar it
    # hangs from, so any straight interpolation from the top dips back inside
    # over the shoulder blades - which is what made the cape look like it was
    # erupting out of the backplate partway down.
    ybase = max(ybase, torso_profile(z)[1] * BACK_FLAT + 0.024)
    # Wrap is much gentler at the top for the same reason: at 0.150 it dragged
    # the cape's top corners forward to y = 0.008, straight through his chest.
    wrap = lerp(0.055, -0.115, ev)            # edges forward at the top
    sway = 0.150 * (v ** 1.8)                 # blown to his left

    k = 1.30
    x = sway + half * (sin(s * k) / sin(k))
    y = ybase - wrap * ((1.0 - cos(s * k)) / (1.0 - cos(k)))

    # Folds. Two frequencies beating against each other, amplitude ramping to
    # the hem, phase drifting with v so ridges run diagonally. A single sine at
    # low amplitude is what made the first version read as a paper cone.
    # ~3.7 fold cycles across the width. At two cycles any single camera angle
    # saw less than one wave and the cloth read as a smooth cone.
    # The sin() term varies the fold SPACING. Evenly pitched folds read as
    # corrugated metal; real cloth gathers unevenly.
    ph = 7.4 * pi * u + 0.90 + 1.9 * v + 0.55 * sin(2.1 * pi * u + 0.7)

    # CREASED profile, not a plain sine. Heavy cloth hangs in broad rounded
    # ridges separated by narrow sharp valleys; a sine is symmetric and rounded
    # at both extremes, which is precisely why the cape still read as a smooth
    # sheet. |sin|^0.45 has flat-topped maxima and cusped minima - subtracting
    # its mean gives shallow broad ridges and deep narrow creases.
    ridge = abs(sin(ph)) ** 0.45
    f1 = (ridge - 0.70) * 1.6
    f2 = sin(3.1 * pi * u - 0.5 + 0.8 * v)      # broad secondary undulation

    # Gather wrinkles radiating from where the cloth is pinned at the shoulders,
    # fading out by mid-back. Real capes bunch at the attachment.
    gather = sin(13.0 * pi * u + 0.3) * math.exp(-((v - 0.11) / 0.20) ** 2)

    # Ramps to ZERO at the collar. A constant term here meant folds existed even
    # on the top ring, and a fold swinging forward there put the cloth back
    # inside the backplate however far out ybase was pushed.
    amp = 0.135 * (v ** 1.3)
    # Flatten the drape across the whole panel the emblem is embroidered on. A
    # fold running through the T bows its crossbar away from the camera and the
    # cross stops reading as a cross - it came out looking like a 7.
    #
    # Quartic exponents rather than a gaussian: that gives a genuinely FLAT
    # plateau over the emblem with a fast falloff outside it, instead of a soft
    # bump that still left half-amplitude folds running through the stem.
    # GAUSSIAN, not a quartic plateau. The quartic gave a genuinely flat panel
    # with a hard boundary, and that boundary was visible as a warp in the
    # middle of the cape exactly where the emblem sits. A wide soft gaussian
    # eases the folds down over the emblem with no edge to see.
    flat = math.exp(-((u - 0.5) / 0.40) ** 2 - ((v - 0.52) / 0.58) ** 2)
    amp *= 1.0 - 0.80 * flat
    y += amp * (0.82 * f1 + 0.42 * f2) + 0.012 * gather
    # The x and z terms matter more than they look: a fold displaced only in y
    # is invisible from directly behind and invisible in silhouette. These are
    # what make the drape read from every angle.
    x += amp * 0.58 * cos(ph)
    z += 0.060 * f1 * (v ** 1.3)

    # Clearance bump: the fauld flares to y=+0.20 at the hips and used to punch
    # straight through the cloth. Push the cape back over that band only, with a
    # gaussian in z so it stays a smooth drape rather than a crease.
    hip = math.exp(-((z - 1.00) / 0.24) ** 2)
    y += 0.135 * hip * max(0.0, 1.0 - abs(x) / 0.44)
    return Vector((x, y, z))


def cape_normal(u, v):
    du = cape_point(min(1.0, u + 0.01), v) - cape_point(max(0.0, u - 0.01), v)
    dv = cape_point(u, min(1.0, v + 0.01)) - cape_point(u, max(0.0, v - 0.01))
    n = du.cross(dv)
    if n.length < 1e-9:
        return Vector((0, 1, 0))
    n.normalize()
    return n if n.y > 0 else -n               # always the outward (back) face


def build_cape():
    rings = []
    for i in range(CAPE_ROWS + 1):
        v = i / CAPE_ROWS
        ring = []
        for j in range(CAPE_COLS + 1):
            u = j / CAPE_COLS
            p = cape_point(u, v)
            if i == CAPE_ROWS:
                # Torn hem. Roughly five points along the bottom edge - the
                # grim note that stops the cape looking freshly tailored.
                p.z -= 0.085 * (0.5 + 0.5 * sin(9.0 * pi * u + 0.4)) ** 1.7
                # 0.055 of clearance, not 0.014: a 9 degree torso pitch swings
                # a 1.2 m hem down by ~47 mm, so a hem that only just clears
                # the ground at rest goes through it the moment he moves.
                p.z = max(p.z, 0.055)
            ring.append(p)
        rings.append(ring)
    cape = loft("Cape", rings, mat=M_CAPE, closed=False)
    cape.data.materials.append(M_CAPE_IN)
    sol = solidify(cape, 0.013, offset=0.0)
    sol.material_offset = 1          # dark lining on the inside face
    sol.material_offset_rim = 1

    # Gold hem all the way round: down one edge, along the torn hem, back up.
    # The corner samples come from the tattered ring itself, not from a fresh
    # cape_point(0, 1) call - the tear offset is applied only to the built ring,
    # so mixing the two put a step at each bottom corner and the swept tube
    # doubled back on itself into a little scroll.
    edge = [cape_point(0.0, i / 10.0) for i in range(10)]
    edge += [rings[CAPE_ROWS][j] for j in range(CAPE_COLS + 1)]
    edge += [cape_point(1.0, 1.0 - i / 10.0) for i in range(1, 11)]
    tube_along("Cape_Hem", edge, 0.0105, M_GOLD)

    build_cape_emblem()

    # Shoulder mantle: a short second layer over the top of the cape, so the
    # shoulders have a defined cap rather than the cape sprouting from nowhere.
    mrings = []
    for i in range(5):
        v = lerp(0.0, 0.165, i / 4.0)
        mrings.append([cape_point(j / 22.0, v) + cape_normal(j / 22.0, v) * 0.022
                       for j in range(23)])
    mantle = loft("Cape_Mantle", mrings, mat=M_CAPE, closed=False)
    solidify(mantle, 0.014)
    # No gold on the mantle edge: it drew a hard horizontal band right across
    # the cape at shoulder-blade height that read as a seam, not a garment.


def cape_u_for_x(x, v):
    """Invert the cape's cross-section: which u lands at world x on row v.

    Needed because the emblem must keep its proportions in WORLD space. Laying
    it out in cloth coordinates looked correct on a flat sheet, but the cape
    both sways to his left and widens as it falls, so a u-parameterised T came
    out sheared - the stem drifted sideways under the crossbar and the whole
    mark read as a 7 rather than a cross.
    """
    k = 1.30
    half = lerp(0.198, 0.455, v ** 0.72)
    sway = 0.150 * (v ** 1.8)
    r = ((x - sway) / max(half, 1e-6)) * sin(k)
    s = math.asin(max(-1.0, min(1.0, r))) / k
    return max(0.0, min(1.0, 0.5 + s * 0.5))


def build_cape_emblem():
    """Gold T embroidered on the back, as ONE continuous stepped patch.

    Same reasoning as the breastplate emblem: three overlapping rectangles put
    coplanar gold on coplanar gold and the foot z-fought itself into a sawtooth.
    Rows are (v, half-width-in-world-X); v runs shoulders-to-hem.
    """
    rows = [
        (0.245, 0.190),      # crossbar
        (0.300, 0.190),
        (0.307, 0.043),      # step in to the stem
        (0.700, 0.043),
        (0.737, 0.068),      # splayed foot
        (0.770, 0.090),
    ]
    rings = []
    for (v, xh) in densify_rows(rows, 0.022):
        ring = []
        for j in range(29):
            x = lerp(-xh, xh, j / 28.0)
            u = cape_u_for_x(x, v)
            ring.append(cape_point(u, v) + cape_normal(u, v) * 0.017)
        rings.append(ring)
    ob = loft("CapeEmblem_T", rings, mat=M_GOLD, closed=False)
    # Thin: a thicker slab reads as a fin standing off the cloth whenever the
    # cape is seen at a grazing angle.
    solidify(ob, 0.007)


# ==============================================================================
#  THE GOLDEN SWORD - elven gift, point-down, glowing inscription in the fuller
# ==============================================================================

M_TOME = make_material("TomeLeather", (0.150, 0.022, 0.030, 1.0), 0.0, 0.560)

GRIP_C = Vector((-0.395, -0.130, 0.980))
SWORD_UP = Vector((0.108, -0.070, 0.990)).normalized()      # tip -> pommel
SWORD_W = SWORD_UP.cross(Vector((0, -1, 0))).normalized()   # edge-to-edge
SWORD_N = SWORD_W.cross(SWORD_UP).normalized()              # blade flat normal

# Hexagonal, fullered cross-section: widest at the edge, dipping at the centre
# so the blade catches two separate highlights instead of one flat one.
BLADE_XSEC = [(1.00, 0.00), (0.74, 0.55), (0.34, 0.98), (0.00, 0.52),
              (-0.34, 0.98), (-0.74, 0.55), (-1.00, 0.00),
              (-0.74, -0.55), (-0.34, -0.98), (0.00, -0.52),
              (0.34, -0.98), (0.74, -0.55)]


def sw(s, a=0.0, b=0.0):
    """Sword-space to world. s along the blade axis, a across the edges,
    b out of the flat."""
    return GRIP_C + SWORD_UP * s + SWORD_W * a + SWORD_N * b


def build_sword():
    #      s,      half-width, half-thickness
    tbl = [(-0.095, 0.053, 0.0135),
           (-0.250, 0.051, 0.0130),
           (-0.420, 0.048, 0.0122),
           (-0.580, 0.043, 0.0112),
           (-0.720, 0.037, 0.0100),
           (-0.830, 0.029, 0.0086),
           (-0.910, 0.020, 0.0068),
           (-0.955, 0.011, 0.0044),
           (-0.980, 0.004, 0.0018)]
    rings = [[sw(s, hw * a, ht * b) for (a, b) in BLADE_XSEC]
             for (s, hw, ht) in tbl]
    blade = loft("Sword_Blade", rings, mat=M_GOLD, closed=True,
                 cap_start=True, cap_end=True)
    bevel(blade, 0.0025, 2)

    # Darkened inlay sunk into the fuller, giving the blade an internal line so
    # it is not one flat gold plane, and giving the inscription something to sit
    # on. Built as a flat lofted beam following the same taper as the blade.
    for face in (1, -1):
        strip = []
        for (s, hw, ht) in tbl[:-2]:
            w, d = hw * 0.30, ht * 0.44
            strip.append([sw(s, -w, face * d), sw(s, w, face * d),
                          sw(s, w, face * (d + 0.0035)),
                          sw(s, -w, face * (d + 0.0035))])
        inlay = loft("Sword_Fuller_%d" % face, strip, mat=M_GOLD_D,
                     closed=True, cap_start=True, cap_end=True)
        bevel(inlay, 0.0012, 2)

    # Elven inscription down the fuller. The lore says the sword was a gift from
    # the elves; this is the only place that shows. Slim vertical strokes, not
    # dots - round glyphs at this size read as polka dots on the blade.
    for i in range(9):
        s = -0.165 - 0.062 * i
        for face in (1, -1):
            g = add_box("Sword_Rune_%d_%d" % (i, face),
                        sw(s, 0.0, face * 0.0105),
                        scale=(0.0038, 0.026 if i % 3 else 0.015, 0.0022),
                        mat=M_RUNE)
            g.rotation_euler = Matrix((SWORD_W, SWORD_UP,
                                       SWORD_N)).transposed().to_euler()

    # Cross-guard: quillons sweeping down toward the blade, leaf finials.
    guard = []
    for i in range(13):
        t = i / 12.0
        a = lerp(-0.165, 0.165, t)
        droop = -0.055 * (abs(t - 0.5) * 2.0) ** 1.8
        guard.append(sw(-0.082 + droop, a, 0.0))
    tube_along("Sword_Guard", guard, 0.021, M_GOLD, segs=10,
               taper=[0.55 + 0.62 * (1.0 - abs(i / 12.0 - 0.5) * 2.0) ** 0.6
                      for i in range(13)])
    for side in (-1, 1):
        leaf = add_sphere("Sword_GuardLeaf_%d" % side,
                          sw(-0.137, side * 0.170, 0.0), 1.0,
                          scale=(0.030, 0.014, 0.024), mat=M_GOLD, u=12, v=8)
        leaf.rotation_euler = SWORD_UP.to_track_quat('Z', 'Y').to_euler()
    # Langets: two small tongues clasping the top of the blade.
    for face in (1, -1):
        lg = add_sphere("Sword_Langet_%d" % face, sw(-0.135, 0.0, face * 0.014),
                        1.0, scale=(0.026, 0.050, 0.008), mat=M_GOLD, u=10, v=6)
        lg.rotation_euler = SWORD_N.to_track_quat('Z', 'Y').to_euler()
    add_gem("Sword_GuardGem", sw(-0.082, 0.0, -0.024), 0.019, 1, mat=M_RUBY)
    add_gem("Sword_GuardGemBack", sw(-0.082, 0.0, 0.024), 0.019, 1, mat=M_RUBY)

    # Grip: dark leather core under a gold wire wrap.
    limb("Sword_Grip", sw(-0.068), sw(0.098),
         [(0.0, 0.0235), (0.5, 0.0265), (1.0, 0.0225)],
         mat=M_LEATHER, segs=16)
    for i in range(13):
        s = lerp(-0.052, 0.086, i / 12.0)
        r = add_torus("Sword_Wire_%02d" % i, sw(s), 0.0262, 0.0042,
                      mat=M_GOLD, mseg=14, nseg=6)
        r.rotation_euler = (SWORD_UP + SWORD_W * 0.16).to_track_quat('Z', 'Y').to_euler()

    # Faceted pommel - deliberately low-poly and flat-shaded so it cuts.
    pom = revolve("Sword_Pommel",
                  [(0.000, 0.000), (0.021, 0.010), (0.034, 0.026),
                   (0.036, 0.044), (0.026, 0.060), (0.010, 0.068),
                   (0.000, 0.070)],
                  segments=8, mat=M_GOLD, smooth=False)
    pom.location = sw(0.098)
    pom.rotation_euler = SWORD_UP.to_track_quat('Z', 'Y').to_euler()
    for face in (1, -1):
        add_gem("Sword_PommelGem_%d" % face, sw(0.130, 0.0, face * 0.026),
                0.016, 1, mat=M_RUBY)


# ==============================================================================
#  THE TEMPLAR'S BOOK - open tome on the left palm, runes circling above it
# ==============================================================================

PALM_FWD = (WRIST_L - ELBOW_L).normalized()
PALM_UP = (Vector((0, 0, 1)) - PALM_FWD * Vector((0, 0, 1)).dot(PALM_FWD)).normalized()
PALM_C = WRIST_L + PALM_FWD * 0.078
SPINE_DIR = PALM_UP.cross(PALM_FWD).normalized()
# Derived so the cover's lowest point (spine side, c = -0.020 in book space)
# lands on top of the finger lames rather than hovering above them: palm plate
# top sits at +0.008, finger lames at +0.013, cover underside at BOOK_C - 0.017.
BOOK_C = PALM_C + PALM_UP * 0.030
# 22 degrees. 17 read as a flat tablet; 30 lifted the outer edges 60 mm clear
# of a flat hand, so the fingers could not reach the cover and the book looked
# like it was hovering over a comb.
TILT = math.tan(radians(22))        # how far the open halves lift at the edge


def bpt(a, b, c, side=1):
    """Book-space to world: a along the spine, b out from the spine (signed by
    `side`), c off the page plane. The `b * TILT` term is the open-book V."""
    return BOOK_C + SPINE_DIR * a + PALM_FWD * (side * b) + PALM_UP * (c + b * TILT)


def _book_ring(a_half, b, c_lo, c_hi, side, n=14, power=0.55):
    """Rounded-rectangle cross-section of the book at distance b from the spine,
    lying in the (spine, page-normal) plane."""
    ac = 0.0
    aw = a_half
    ch = (c_hi - c_lo) * 0.5
    cc = (c_hi + c_lo) * 0.5
    pts = []
    for i in range(n):
        ang = 2 * pi * i / n
        cs, sn = cos(ang), sin(ang)
        pts.append(bpt(ac + aw * math.copysign(abs(cs) ** power, cs), b,
                       cc + ch * math.copysign(abs(sn) ** power, sn), side))
    return pts


def build_book():
    for side, tag in ((1, "F"), (-1, "B")):
        # Cover board: overhangs the pages on all sides, as a real binding does.
        cov = loft("Tome_Cover_%s" % tag,
                   [_book_ring(0.140, b, -0.020, -0.003, side)
                    for b in (0.005, 0.038, 0.088, 0.126, 0.136)],
                   mat=M_TOME, closed=True, cap_start=True, cap_end=True)
        bevel(cov, 0.004, 2)

        # Page block, fanning thicker toward the outer edge.
        pages = loft("Tome_Pages_%s" % tag,
                     [_book_ring(0.126, 0.008, -0.003, 0.016, side),
                      _book_ring(0.128, 0.042, -0.003, 0.028, side),
                      _book_ring(0.126, 0.080, -0.003, 0.036, side),
                      _book_ring(0.119, 0.110, -0.003, 0.038, side),
                      _book_ring(0.102, 0.124, 0.003, 0.028, side)],
                     mat=M_PAGE, closed=True, cap_start=True, cap_end=True)
        bevel(pages, 0.002, 2)

        # Gold edging and corner bosses.
        tube_along("Tome_CoverEdge_%s" % tag,
                   [bpt(a, 0.132, -0.012, side) for a in
                    (-0.135, -0.06, 0.0, 0.06, 0.135)], 0.0058, M_GOLD)
        for a in (-0.130, 0.130):
            add_sphere("Tome_Boss_%s_%+.0f" % (tag, a * 1000),
                       bpt(a, 0.122, -0.014, side), 0.018,
                       scale=(1, 1, 0.6), mat=M_GOLD, u=12, v=8)

    # The gutter: a slot of red light between the two halves. This is the "magic
    # book written by old knights who never died" doing its one visible thing.
    # Raised clear of the page blocks: at the original height it was sandwiched
    # between them and the light never reached the camera.
    glow = add_box("Tome_Gutter", (0, 0, 0), scale=(0.030, 0.250, 0.022),
                   mat=M_PAGEGLOW)
    glow.location = BOOK_C + PALM_UP * 0.020
    # Basis order matters: SPINE_DIR is PALM_UP x PALM_FWD, so (SPINE, FWD, UP)
    # is LEFT-handed and to_euler() on it yields a mirrored rotation. (FWD,
    # SPINE, UP) is the right-handed ordering.
    glow.rotation_euler = Matrix((PALM_FWD, SPINE_DIR,
                                  PALM_UP)).transposed().to_euler()

    # No gold T on the tome. It was specified for the back cover, but with the
    # book open and tilted the patch landed INSIDE the page block and surfaced
    # through the top of the leaves. The Templar mark is already carried by the
    # breastplate, the cape and the floating glyphs; a fourth is clutter.
    #
    # Loose leaves instead, so the pages are not one smooth cream pillow.
    for side, tag in ((1, "F"), (-1, "B")):
        for i, (b, aw, lift) in enumerate(((0.052, 0.118, 0.0035),
                                           (0.086, 0.110, 0.0060),
                                           (0.114, 0.098, 0.0080))):
            leaf = loft("Tome_Leaf_%s%d" % (tag, i),
                        [_book_ring(aw, b - 0.026, -0.002 + lift,
                                    0.016 + lift + 0.010 * i, side),
                         _book_ring(aw * 0.97, b + 0.020, -0.002 + lift,
                                    0.014 + lift + 0.010 * i, side)],
                        mat=M_PAGE, closed=True, cap_start=True, cap_end=True)
            bevel(leaf, 0.0015, 2)

    # Clasp chain and seal hanging off the spine.
    anchor = bpt(0.131, 0.012, -0.026)
    drop = anchor + Vector((0.010, 0.0, -0.150))
    for k in range(6):
        add_torus("Tome_ChainLink_%d" % k, anchor.lerp(drop, 0.10 + 0.145 * k),
                  0.0105, 0.0034, rot=(radians(90), 0, radians(35 * (k % 2))),
                  mat=M_GOLD_D, mseg=12, nseg=6)
    seal = add_cyl("Tome_Seal", drop, 0.026, 0.026, 0.010,
                   rot=(radians(6), 0, 0), mat=M_GOLD, segs=18)
    bevel(seal, 0.004, 3)
    add_gem("Tome_SealGem", drop + Vector((0, 0, 0.008)), 0.012, 1, mat=M_RUBY)

    # Runes rising off the open pages. These were wire tori in the first pass
    # and read as a wireframe glitch floating over his hand; little Templar
    # crosses spiralling upward say the same thing and are legible.
    for k in range(3):
        ang = 2.1 * k + 0.5                       # tight ascending spiral
        t = k / 2.0
        h = 0.120 + 0.135 * t      # clear of the page surface, not lying on it
        rad = 0.125 * (1.0 - 0.28 * t)
        p = (BOOK_C + PALM_UP * h + SPINE_DIR * (rad * cos(ang))
             + PALM_FWD * (rad * 0.8 * sin(ang)))
        sz = 0.068 * (1.0 - 0.26 * t)
        for tag, sc in (("bar", (sz, 0.0090, sz * 0.30)),
                        ("stem", (sz * 0.28, 0.0090, sz * 1.15))):
            g = add_box("Tome_Glyph_%d_%s" % (k, tag),
                        p + PALM_UP * (0.0 if tag == "bar" else -sz * 0.42),
                        scale=sc, rot=(0, 0, ang), mat=M_RUNE)
            bevel(g, 0.0012, 2)


# ==============================================================================
#  FX - separately collected so the game can toggle any of it
# ==============================================================================

EMPTIES = []


def add_empty(name, loc, size=0.05):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'PLAIN_AXES'
    e.empty_display_size = size
    e.location = loc
    COL_KNIGHT.objects.link(e)
    EMPTIES.append(e)
    return e


def build_fx():
    # Kept deliberately faint. At full strength the ground ring was the
    # brightest object in frame and read as a glowing hula hoop.
    ring = add_torus("FX_AuraRing", (0, 0, 0.008), 0.440, 0.0055,
                     mat=M_AURA, mseg=48, nseg=6, coll=COL_FX)
    ring.scale = (1.0, 1.0, 0.4)
    for k in range(6):
        ang = 2 * pi * k / 6 + 0.3
        add_box("FX_AuraGlyph_%d" % k,
                (0.500 * cos(ang), 0.500 * sin(ang), 0.008),
                scale=(0.048, 0.011, 0.005), rot=(0, 0, ang + pi / 2),
                mat=M_AURA, coll=COL_FX)
    # Embers drifting off him. Poster garnish; hidden by default in-game.
    for k in range(9):
        ang = 2.399 * k                      # golden-angle scatter
        rad = 0.26 + 0.30 * ((k * 7) % 11) / 11.0
        h = 0.15 + 1.45 * ((k * 5) % 13) / 13.0
        add_sphere("FX_Ember_%02d" % k,
                   (rad * cos(ang), rad * sin(ang) + 0.12, h),
                   0.004 + 0.005 * ((k * 3) % 5) / 5.0,
                   mat=M_AURA, u=8, v=6, coll=COL_FX)


# ==============================================================================
#  ASSEMBLE
# ==============================================================================

def build_knight():
    build_cuirass()
    build_gorget()
    build_fauld()
    build_tassets()
    build_belt()
    build_emblem()
    for side, tag in ((-1, "R"), (1, "L")):
        set_side(tag)
        build_pauldron(side, tag)
        build_arm(side, tag)
        build_leg(side, tag)
        build_sabaton(side, tag)
    set_side("")
    build_helmet()
    build_plume()
    build_cape()
    build_sword()
    build_book()

    # Back of the hand faces OUTWARD (-X), the natural orientation for an arm
    # hanging at the side. Facing it along -SWORD_N pointed the knuckles
    # backwards and put the palm toward the camera.
    hand_out = (SWORD_W * -1.0).normalized()
    set_side("R")
    build_gauntlet_sword(-1, "R", GRIP_C, SWORD_UP, hand_out)
    set_side("L")
    build_gauntlet_book(1, "L", PALM_C, PALM_FWD, PALM_UP)
    set_side("")

    build_fx()

    add_empty("Attach_SwordHand", GRIP_C)
    add_empty("Attach_BookHand", BOOK_C)
    add_empty("Attach_EyeGlow", (0.0, HELM_CY - 0.120, EYE_Z))
    add_empty("Attach_PlumeTip", (0.0, HELM_CY + 0.340, 1.720))
    add_empty("Attach_Ground", (0.0, 0.0, 0.0), size=0.25)


# --- variant hook -------------------------------------------------------------
# A runner (_tools/preview.py) pre-seeds VARIANT in this namespace before
# exec'ing the file. Entries are applied after every default above is set and
# before anything is built, so a variant can override any tuning constant, any
# material, or any builder function.
#
# This block cannot be moved into a shared helper and imported. globals() here
# resolves to the CALLING module's namespace - which is precisely what the hook
# needs and precisely what an imported function could not give it. A DRY cleanup
# that extracts this silently breaks name resolution for every variant.
#
# RENDER_DIR rides in here too, deliberately: line 48 assigns it unconditionally,
# so a plain namespace seed would be clobbered. Applying it here — after that
# assignment, before render_view() reads it — is what makes previews land in the
# run directory instead of _knight000/.
_v = globals().get("VARIANT", {})
globals().update({k: v for k, v in _v.items() if not k.startswith("_")})
if _v.get("_patch"):
    # Structural variants arrive as SOURCE, not as function objects. A function
    # defined in the runner carries the runner's __globals__ and cannot see
    # revolve(), M_GOLD, or any other helper here — it would fail at call time,
    # deep in the build, for a reason that looks nothing like its cause.
    # exec'ing the source binds it to this namespace instead.
    exec(_v["_patch"], globals())
# ------------------------------------------------------------------------------

build_knight()
print("Knight built: %d meshes, %d empties" % (len(PARTS), len(EMPTIES)))


# ==============================================================================
#  PREVIEW / KEY-ART RIG
#
#  Follows the store-page art direction: cold gothic ambience, warm key. The rig
#  is in its own collection and is never exported.
# ==============================================================================

def build_rig():
    world = bpy.data.worlds.new("KnightWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.030, 0.036, 0.055, 1.0)
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

    aim = (0.0, 0.0, 1.15)
    area("Key",   (-2.05, -2.45, 2.85), aim, 300, (1.00, 0.84, 0.62), 2.2)
    area("Fill",  ( 2.30, -1.90, 1.25), aim,  70, (0.58, 0.72, 1.00), 2.6)
    area("RimL",  ( 1.75,  2.10, 2.30), aim, 230, (0.42, 0.62, 1.00), 1.4)
    area("RimR",  (-1.90,  1.85, 1.95), aim, 170, (0.46, 0.66, 1.00), 1.4)
    area("Under", ( 0.00, -1.30, 0.05), (0, 0, 0.7), 22, (1.00, 0.42, 0.24), 1.6)
    # Cold wrap from front-left, low. Without it the front-facing side of the
    # cape falls entirely outside the warm key and reads as a shapeless dark
    # slab next to the lit armour.
    area("CapeWrap", (-3.10, -2.20, 0.95), (-0.35, 0.30, 0.85), 130,
         (0.42, 0.58, 1.00), 3.0)

    # Floor. Never exported (it lives in the rig collection) but it is what
    # stops the hero renders looking like a model floating in a void: it catches
    # the aura ring, grounds the sabatons with a contact shadow, and gives the
    # cape something to reflect into.
    floor_mat = make_material("RigFloor", (0.020, 0.024, 0.034, 1.0), 0.0, 0.42)
    add_cyl("Ground", (0.0, 0.0, -0.004), 16.0, 16.0, 0.008,
            mat=floor_mat, segs=64, coll=COL_RIG)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 62
    cam = bpy.data.objects.new("Cam", cam_data)
    COL_RIG.objects.link(cam)
    SCENE.camera = cam

    r = SCENE.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y = 900, 1250
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
    # The look/view-transform enums are populated from OCIO and are NOT
    # introspectable here (bl_rna reports a single NONE item), so membership
    # testing gives false negatives. Assign, then read back and print - a silent
    # failure leaves the render on Standard, which clips every highlight to white.
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

    if DO_GLARE:
        add_glare()
    return cam


def add_glare():
    """Optional compositor bloom on top of the render.

    Off by default and firewalled in a try/except on purpose. Blender 5.x moved
    the scene compositor from `scene.node_tree` to `scene.compositing_node_group`
    AND converted the Glare node's settings from RNA properties to input sockets,
    so nothing about this block is stable across versions - and a failure here
    would otherwise take the whole model build down with it. The model is lit to
    look right without bloom; this is garnish.
    """
    try:
        ng = bpy.data.node_groups.new("KnightComp", "CompositorNodeTree")
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        out = ng.nodes.new("NodeGroupOutput")
        for sock, val in (("Threshold", 0.85), ("Strength", 0.55), ("Size", 8)):
            if sock in gl.inputs:
                gl.inputs[sock].default_value = val
        ng.links.new(rl.outputs[0], gl.inputs[0])
        ng.links.new(gl.outputs[0], out.inputs[0])
        SCENE.compositing_node_group = ng
        SCENE.use_nodes = True
    except Exception as exc:      # noqa: BLE001 - deliberately swallow everything
        print("glare setup skipped:", exc)


def render_view(name, cam_loc, target=(0, 0, 1.05), res=(900, 1250), lens=62,
                samples=None):
    # A preview run renders a cheap subset rather than all ten views. RENDER_ONLY
    # unset (the normal case) means "render everything", so a plain
    # `blender -b -P blender_knight000.py -- render` is unaffected.
    only = globals().get("RENDER_ONLY")
    if only is not None and name not in only:
        return
    cam = SCENE.camera
    cam.location = cam_loc
    cam.rotation_euler = look_at_euler(cam_loc, target)
    cam.data.lens = lens
    SCENE.render.resolution_x, SCENE.render.resolution_y = res
    # SAMPLE_SCALE lets a preview run trade noise for speed. Views that pass no
    # explicit count skip this assignment entirely and inherit whatever the
    # previous render_view() call left set - exactly like the original
    # unconditional-samples code before RENDER_ONLY/SAMPLE_SCALE existed. Call
    # order matters: "poster" (320) and "hero_34" (160) set explicit counts
    # below, and every view after inherits from whichever ran last.
    scale = globals().get("SAMPLE_SCALE", 1.0)
    if samples and hasattr(SCENE.eevee, "taa_render_samples"):
        SCENE.eevee.taa_render_samples = max(16, int(samples * scale))
    os.makedirs(RENDER_DIR, exist_ok=True)
    SCENE.render.filepath = os.path.join(RENDER_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", SCENE.render.filepath)




# ==============================================================================
#  ARMATURE
#
#  Plate armour is the easy case for skinning: every plate is RIGID, so each
#  mesh is weighted 100% to exactly one bone and nothing stretches. The only
#  part that needs graded weights is the cape, which is one continuous sheet and
#  gets a four-bone chain blended by height.
#
#  Bone assignment is by object-name prefix plus the side stamped on each object
#  at build time (see CURRENT_SIDE). Names like "Finger_R0_L0" mean the side
#  cannot be recovered by looking for a trailing "_L"/"_R", which is why it is
#  recorded explicitly rather than parsed.
# ==============================================================================

CAPE_BONE_V = (0.0, 0.26, 0.52, 0.78, 1.0)      # cape chain sample points


def _cape_bone_points():
    return [cape_point(0.5, v) for v in CAPE_BONE_V]


def bone_table():
    """[(name, head, tail, parent), ...] - built from the same skeleton
    constants the geometry was generated from, so bones land inside plates."""
    t = [
        ("Root",  (0.0, 0.0, 0.0),   (0.0, 0.0, 0.20), None),
        ("Hips",  (0.0, 0.0, 1.010), (0.0, 0.0, 1.170), "Root"),
        ("Spine", (0.0, 0.0, 1.170), (0.0, 0.0, 1.380), "Hips"),
        ("Chest", (0.0, 0.0, 1.380), (0.0, 0.0, 1.575), "Spine"),
        ("Neck",  (0.0, 0.0, 1.575), (0.0, 0.0, 1.690), "Chest"),
        ("Head",  (0.0, 0.0, 1.690), (0.0, 0.0, 1.985), "Neck"),
    ]
    for tag, sh, el, wr, hip, knee, ankle in (
            ("R", SHOULDER_R, ELBOW_R, WRIST_R, HIP_R, KNEE_R, ANKLE_R),
            ("L", SHOULDER_L, ELBOW_L, WRIST_L, HIP_L, KNEE_L, ANKLE_L)):
        s = -1.0 if tag == "R" else 1.0
        t.append(("Clavicle_" + tag, (s * 0.045, 0.0, 1.545), tuple(sh), "Chest"))
        t.append(("UpperArm_" + tag, tuple(sh), tuple(el), "Clavicle_" + tag))
        t.append(("LowerArm_" + tag, tuple(el), tuple(wr), "UpperArm_" + tag))
        t.append(("Thigh_" + tag, tuple(hip), tuple(knee), "Hips"))
        t.append(("Shin_" + tag, tuple(knee), tuple(ankle), "Thigh_" + tag))
        t.append(("Foot_" + tag, tuple(ankle),
                  (ankle.x, ankle.y - 0.20, 0.045), "Shin_" + tag))
    t.append(("Hand_R", tuple(WRIST_R), tuple(GRIP_C), "LowerArm_R"))
    t.append(("Hand_L", tuple(WRIST_L), tuple(PALM_C), "LowerArm_L"))
    # Props get their own bones so a swing or a cast can animate them
    # independently of the hand that holds them.
    t.append(("Sword", tuple(GRIP_C), tuple(GRIP_C + SWORD_UP * 0.22), "Hand_R"))
    t.append(("Book", tuple(BOOK_C), tuple(BOOK_C + PALM_FWD * 0.16), "Hand_L"))

    pts = _cape_bone_points()
    for i in range(4):
        t.append(("Cape%d" % (i + 1), tuple(pts[i]), tuple(pts[i + 1]),
                  "Chest" if i == 0 else "Cape%d" % i))
    return t


def build_armature():
    arm_data = bpy.data.armatures.new("KnightRig")
    arm_obj = bpy.data.objects.new("KnightRig", arm_data)
    COL_KNIGHT.objects.link(arm_obj)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    for (name, head, tail, parent) in bone_table():
        b = eb.new(name)
        b.head, b.tail = head, tail
        b.use_connect = False
        if parent:
            b.parent = eb[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj


# ------------------------------------------------------------------------------
#  Which bone drives which part
# ------------------------------------------------------------------------------

_BONE_PREFIX = (
    # (prefix tuple, bone template - {s} is replaced by the object's side)
    (("Helmet", "Eye_", "Plume"), "Head"),
    (("Neck_Mail", "Gorget"), "Neck"),
    (("Cuirass", "Plackart", "BreastPlate", "Emblem_", "CapeClasp", "CapeChain",
      "Rivet_Arm", "Spine_Trim"), "Chest"),
    (("Belt", "Fauld", "Mail_Skirt", "Trophy", "Tasset"), "Hips"),
    (("Pauldron",), "Clavicle_{s}"),
    (("Rerebrace", "Arm_Voider", "Couter"), "UpperArm_{s}"),
    (("Vambrace",), "LowerArm_{s}"),
    (("Gauntlet", "Fist_", "Finger_", "Thumb_", "Knuckle_Dome"), "Hand_{s}"),
    (("Sword_",), "Sword"),
    (("Tome_",), "Book"),
    (("Cuisse", "Poleyn", "Leg_Mail"), "Thigh_{s}"),
    (("Greave", "Sabaton_Cuff"), "Shin_{s}"),
    (("Sabaton",), "Foot_{s}"),
    (("FX_",), "Root"),
)

CAPE_MARKER = "__CAPE__"


def bone_of(ob):
    """CAPE_MARKER, or a list of (bone_name, weight).

    Almost everything is rigid plate and returns a single bone at weight 1.0.
    The tassets are the exception: they hang from the belt, so weighting them
    entirely to Hips leaves them standing still while the thigh swings forward
    and strands the leg outside its own armour. Graded down the three lames -
    top stays with the hips, hem follows the leg - they swing with the stride
    while staying anchored at the belt.
    """
    name = ob.name
    if name.startswith("Cape"):
        # CapeClasp / CapeChain are chest jewellery, not cloth - they are caught
        # by the Chest rule below; everything else starting with Cape is cloth.
        if not name.startswith(("CapeClasp", "CapeChain")):
            return CAPE_MARKER
    side = ob.get("side") or "R"
    if name.startswith("Tasset"):
        thigh = "Thigh_%s" % side
        if name.startswith("Tasset0"):
            return [("Hips", 1.0)]
        if name.startswith("Tasset1"):
            return [("Hips", 0.55), (thigh, 0.45)]
        if name.startswith("Tasset2"):
            return [("Hips", 0.25), (thigh, 0.75)]
        return [("Hips", 0.5), (thigh, 0.5)]        # stud, gem
    for prefixes, template in _BONE_PREFIX:
        if name.startswith(prefixes):
            return [(template.format(s=side) if "{s}" in template else template,
                     1.0)]
    return [("Chest", 1.0)]


def cape_weights(co):
    """Graded weights down the cape's four-bone chain, blended by height."""
    zs = [p.z for p in _cape_bone_points()]
    z = co.z
    if z >= zs[0]:
        return [("Cape1", 1.0)]
    for i in range(4):
        hi, lo = zs[i], zs[i + 1]
        if lo <= z <= hi:
            t = (hi - z) / max(1e-6, hi - lo)
            a = "Cape%d" % (i + 1)
            if i == 3:
                return [(a, 1.0)]
            b = "Cape%d" % (i + 2)
            # Blend only over the lower half of each segment so each bone still
            # has full authority over its own span.
            w = max(0.0, (t - 0.5) * 2.0)
            return [(a, 1.0 - w * 0.5), (b, w * 0.5)]
    return [("Cape4", 1.0)]


def skin_parts(arm_obj):
    """Give every source part a vertex group and an armature modifier, so the
    authoring .blend itself is posable rather than only the exported merge."""
    for ob in PARTS:
        bn = bone_of(ob)
        ob.parent = arm_obj
        m = ob.modifiers.new("Armature", 'ARMATURE')
        m.object = arm_obj
        idx = list(range(len(ob.data.vertices)))
        groups = {}

        def grp(gname):
            if gname not in groups:
                groups[gname] = ob.vertex_groups.new(name=gname)
            return groups[gname]

        if bn == CAPE_MARKER:
            for i in idx:
                for name, w in cape_weights(ob.matrix_world @ ob.data.vertices[i].co):
                    grp(name).add([i], w, 'REPLACE')
        else:
            for name, w in bn:
                grp(name).add(idx, w, 'REPLACE')




# ==============================================================================
#  ANIMATION
#
#  Four clips authored here rather than left to Unity, because they are also the
#  test that the rig deforms correctly: a walk exercises every leg joint, the
#  swing exercises the whole right arm chain and the sword bone, the cast
#  exercises the left arm and the book bone. If a plate clips, these show it.
#
#  Bones point head->tail along their own local Y, so for a limb bone hanging
#  downward local X is the swing axis (forward/back) and local Z is the splay.
# ==============================================================================

def key(arm, frame, rots=None, locs=None):
    for bn, r in (rots or {}).items():
        pb = arm.pose.bones.get(bn)
        if not pb:
            continue
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = [radians(a) for a in r]
        pb.keyframe_insert("rotation_euler", frame=frame)
    for bn, l in (locs or {}).items():
        pb = arm.pose.bones.get(bn)
        if not pb:
            continue
        pb.location = l
        pb.keyframe_insert("location", frame=frame)


def new_action(arm, name):
    if not arm.animation_data:
        arm.animation_data_create()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True          # survive save/reload with no user
    arm.animation_data.action = act
    return act


def clear_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)


def key_all_rest(arm, frame=1):
    """Key EVERY bone at rest on the action's first frame.

    Without this an action only constrains the bones it explicitly animates, and
    every other bone keeps whatever pose it happened to be in - so BookCast
    inherited the sword arm mid-swing from SwordSwing. That leaks into the baked
    FBX takes as well as the viewport, so each clip has to be self-contained.
    Real keys inserted afterwards at the same frame simply overwrite these.
    """
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
        pb.keyframe_insert("rotation_euler", frame=frame)
        pb.keyframe_insert("location", frame=frame)


def anim_idle(arm):
    new_action(arm, "Idle")
    clear_pose(arm)
    key_all_rest(arm, 1)
    for f, sway in ((1, 0.0), (36, 1.6), (72, 0.0)):
        key(arm, f,
            rots={"Chest": (sway * 0.5, 0, 0), "Neck": (-sway * 0.3, 0, 0),
                  "Cape1": (sway * 0.8, 0, 0), "Cape2": (sway * 1.1, 0, 0),
                  "Cape3": (sway * 1.3, 0, 0), "Cape4": (sway * 1.5, 0, 0)},
            )


def anim_walk(arm):
    """32-frame loop. Frame 1 and 33 are identical so it cycles cleanly."""
    new_action(arm, "Walk")
    clear_pose(arm)
    key_all_rest(arm, 1)
    # (frame, right-thigh, right-shin, left-thigh, left-shin, hip bob, arm swing)
    #
    # Hip bob is LOWEST at contact (1/17/33, legs spread so the hip-to-ankle
    # vertical is short) and highest at passing (9/25, support leg vertical).
    # It was inverted, which drove the hips DOWN exactly when the support leg
    # was straight - and pushed the planted sabaton through the floor.
    steps = [
        (1,   26, -6, -22, 32, -0.030, -16),
        (9,    2, -2,  -2,  6, -0.008,  -4),
        (17, -22, 32,  26, -6, -0.030,  16),
        (25,  -2,  6,   2, -2, -0.008,   4),
        (33,  26, -6, -22, 32, -0.030, -16),
    ]
    for (f, rt, rs, lt, ls, _bob, sw) in steps:
        key(arm, f,
            rots={
                "Thigh_R": (rt, 0, 0), "Shin_R": (rs, 0, 0),
                "Thigh_L": (lt, 0, 0), "Shin_L": (ls, 0, 0),
                "Foot_R": (-rt * 0.35, 0, 0), "Foot_L": (-lt * 0.35, 0, 0),
                # Torso counter-twist is about local Y. These bones stand
                # upright, so their local Y IS the spine axis; a local-Z
                # rotation leans the whole upper body sideways instead.
                "Hips": (0, -sw * 0.25, 0),
                "Chest": (2.0, sw * 0.30, 0),
                # The sword arm swings much less than the free arm: he is
                # carrying a metre of steel in it.
                "UpperArm_R": (sw * 0.45, 0, 0),
                "UpperArm_L": (-sw * 0.30, 0, 0),
                "Cape1": (-sw * 0.20, 0, 0), "Cape2": (-sw * 0.35, 0, 0),
                "Cape3": (-sw * 0.50, 0, 0), "Cape4": (-sw * 0.65, 0, 0),
            },
            )


def anim_sword_swing(arm):
    """Wind up, cut across, recover. 30 frames."""
    new_action(arm, "SwordSwing")
    clear_pose(arm)
    key_all_rest(arm, 1)
    key(arm, 1, rots={"UpperArm_R": (0, 0, 0), "LowerArm_R": (0, 0, 0),
                      "Hand_R": (0, 0, 0), "Sword": (0, 0, 0),
                      "Chest": (0, 0, 0), "Clavicle_R": (0, 0, 0)})
    # wind up - blade back and high
    key(arm, 9, rots={"UpperArm_R": (-108, 0, -26), "LowerArm_R": (-46, 0, 0),
                      "Hand_R": (0, -22, 0), "Sword": (0, 0, 0),
                      "Chest": (-6, -18, 0), "Clavicle_R": (-10, 0, -6)})
    # strike - through the arc
    key(arm, 15, rots={"UpperArm_R": (-34, 0, 40), "LowerArm_R": (-10, 0, 0),
                       "Hand_R": (0, 16, 0), "Sword": (0, 0, 0),
                       "Chest": (5, 26, 0), "Clavicle_R": (4, 0, 8)})
    # follow through
    key(arm, 21, rots={"UpperArm_R": (-6, 0, 46), "LowerArm_R": (-4, 0, 0),
                       "Hand_R": (0, 8, 0), "Chest": (3, 20, 0),
                       "Clavicle_R": (2, 0, 5)})
    key(arm, 30, rots={"UpperArm_R": (0, 0, 0), "LowerArm_R": (0, 0, 0),
                       "Hand_R": (0, 0, 0), "Chest": (0, 0, 0),
                       "Clavicle_R": (0, 0, 0)})


def anim_book_cast(arm):
    """The Templar's Book ultimate: raise the tome, channel, lower. 60 frames."""
    new_action(arm, "BookCast")
    clear_pose(arm)
    key_all_rest(arm, 1)
    key(arm, 1, rots={"UpperArm_L": (0, 0, 0), "LowerArm_L": (0, 0, 0),
                      "Hand_L": (0, 0, 0), "Book": (0, 0, 0),
                      "Chest": (0, 0, 0), "Neck": (0, 0, 0)})
    # lift the tome up and forward, lean back over it
    key(arm, 14, rots={"UpperArm_L": (-40, 0, 6), "LowerArm_L": (-30, 0, 0),
                       "Hand_L": (-12, 0, 0), "Book": (-16, 0, 0),
                       "Chest": (-7, 4, 0), "Neck": (6, 0, 0)})
    # channel - slow rise, book tips open toward the enemy
    key(arm, 34, rots={"UpperArm_L": (-48, 0, 10), "LowerArm_L": (-34, 0, 0),
                       "Hand_L": (-16, 0, 0), "Book": (-26, 0, 0),
                       "Chest": (-9, 5, 0), "Neck": (8, 0, 0)})
    key(arm, 44, rots={"UpperArm_L": (-44, 0, 8), "LowerArm_L": (-31, 0, 0),
                       "Hand_L": (-14, 0, 0), "Book": (-21, 0, 0),
                       "Chest": (-8, 4, 0), "Neck": (7, 0, 0)})
    key(arm, 60, rots={"UpperArm_L": (0, 0, 0), "LowerArm_L": (0, 0, 0),
                       "Hand_L": (0, 0, 0), "Book": (0, 0, 0),
                       "Chest": (0, 0, 0), "Neck": (0, 0, 0)})


def ground_hips(arm, action_name, f0, f1, target=0.006):
    """Key hip height per frame so the lowest sabaton just kisses the floor.

    FK legs plus a hand-authored bob cannot keep a foot planted: the hip-to-ankle
    vertical distance changes with every joint angle, so the correct bob is a
    different number on every frame. The first attempt hand-tuned it and got the
    phase inverted (hips driven DOWN exactly when the support leg was straight),
    which pushed the planted sabaton through the floor. Solving it is both
    simpler and correct.

    NOTE the axis: pose_bone.location is in BONE space, and the Hips bone stands
    upright, so its local Y is world up. Writing the bob into .z moved him
    forwards and backwards instead of up and down.
    """
    arm.animation_data.action = bpy.data.actions[action_name]
    hips = arm.pose.bones["Hips"]
    feet = [o for o in PARTS if o.name.startswith("Sabaton")]
    sc = bpy.context.scene
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        hips.location = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        lo = 1e9
        for o in feet:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
            if me.vertices:
                lo = min(lo, min((o.matrix_world @ v.co).z for v in me.vertices))
            bpy.data.meshes.remove(me)
        hips.location = (0.0, target - lo, 0.0)
        hips.keyframe_insert("location", frame=f)


def build_animations(arm):
    anim_idle(arm)
    anim_walk(arm)
    anim_sword_swing(arm)
    anim_book_cast(arm)
    # Solve hip height on the clips whose legs actually move.
    ground_hips(arm, "Walk", 1, 33)
    ground_hips(arm, "Idle", 1, 72)
    clear_pose(arm)
    arm.animation_data.action = None
    print("actions: %s" % ", ".join(a.name for a in bpy.data.actions))


# ==============================================================================
#  EXPORT
#
#  The .blend keeps every named part with its modifiers live. The FBX gets the
#  evaluated meshes merged per (region, material) - roughly a dozen objects
#  instead of three hundred draw calls - with Sword / Book / Cape kept separate
#  so they can still be animated independently.
# ==============================================================================

def group_of(ob):
    n = ob.name
    if n.startswith("FX_"):
        return "FX"
    if n.startswith("Sword_"):
        return "Sword"
    if n.startswith("Tome_"):
        return "Book"
    if n.startswith("Cape"):
        return "Cape"
    if n.startswith(("Helmet", "Eye_", "Plume")):
        return "Head"
    return "Body"


def bake_merged(arm_obj=None):
    """Evaluate modifiers through the depsgraph and merge by (group, material).

    Deliberately avoids bpy.ops.object.join: join keeps only the ACTIVE object's
    modifier stack and silently discards everyone else's, which would throw away
    every bevel and solidify in the build.

    Carries skin weights across: each source part contributes a contiguous run of
    vertices to the merged mesh, so its bone assignment can be replayed as a
    vertex group on the result. The armature is forced to REST while baking -
    otherwise a posed rig would be baked into the mesh AND applied again by the
    merged object's own armature modifier.
    """
    prev_pose = None
    if arm_obj:
        prev_pose = arm_obj.data.pose_position
        arm_obj.data.pose_position = 'REST'
        bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    col = bpy.data.collections.get("Export") or bpy.data.collections.new("Export")
    if col.name not in SCENE.collection.children:
        SCENE.collection.children.link(col)

    buckets = {}
    for ob in PARTS:
        mat = ob.data.materials[0] if ob.data.materials else None
        key = (group_of(ob), mat.name if mat else "NoMat")
        buckets.setdefault(key, []).append(ob)

    made = []
    for (grp, matname), obs in sorted(buckets.items()):
        bm = bmesh.new()
        runs = []                       # (first_vert, count, bone) per source part
        for ob in obs:
            tmp = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            tmp.transform(ob.matrix_world)
            start = len(bm.verts)
            bm.from_mesh(tmp)
            bm.verts.ensure_lookup_table()
            runs.append((start, len(bm.verts) - start, bone_of(ob)))
            bpy.data.meshes.remove(tmp)
        name = "Knight_%s_%s" % (grp, matname.replace("Knight", "").replace("Tome", ""))
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        mat = bpy.data.materials.get(matname)
        if mat:
            me.materials.append(mat)
        o = bpy.data.objects.new(name, me)
        col.objects.link(o)

        if arm_obj:
            groups = {}

            def grp_for(bn):
                if bn not in groups:
                    groups[bn] = o.vertex_groups.new(name=bn)
                return groups[bn]

            for (start, count, bn) in runs:
                idx = list(range(start, start + count))
                if bn == CAPE_MARKER:
                    for i in idx:
                        for cbn, w in cape_weights(me.vertices[i].co):
                            grp_for(cbn).add([i], w, 'REPLACE')
                else:
                    for cbn, w in bn:
                        grp_for(cbn).add(idx, w, 'REPLACE')
            o.parent = arm_obj
            m = o.modifiers.new("Armature", 'ARMATURE')
            m.object = arm_obj
        made.append(o)

    if arm_obj and prev_pose:
        arm_obj.data.pose_position = prev_pose
    print("merged into %d export meshes" % len(made))
    return made, col


def export_fbx(arm_obj=None):
    made, col = bake_merged(arm_obj)
    for ob in bpy.data.objects:
        ob.select_set(False)
    for ob in made + EMPTIES:
        ob.select_set(True)
    if arm_obj:
        arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj or made[0]
    bpy.ops.export_scene.fbx(
        filepath=FBX_PATH,
        use_selection=True,
        object_types={'MESH', 'EMPTY', 'ARMATURE'},
        # One take per action, so Unity sees Idle / Walk / SwordSwing / BookCast
        # as separate clips on the imported model.
        bake_anim=bool(arm_obj),
        bake_anim_use_all_actions=bool(arm_obj),
        bake_anim_use_nla_strips=False,
        add_leaf_bones=False,
        mesh_smooth_type='FACE',
        axis_forward='-Z',
        axis_up='Y',
        global_scale=1.0,
    )
    print("Exported:", FBX_PATH)


# Rig AFTER the geometry and after the armature/animation helpers are defined.
ARMATURE = build_armature()
skin_parts(ARMATURE)
build_animations(ARMATURE)

CAM = build_rig()

if DO_SAVE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print("Saved:", BLEND_PATH)

if DO_RENDER:
    # Poster plate: low camera looking slightly up so he towers, long lens to
    # keep the proportions honest, high sample count.
    #
    # Only ~18 degrees off axis. Further round (29 was tried) and the Templar T
    # foreshortens across the keel of the breastplate until it reads as a 7 -
    # which is the one thing this character cannot afford to lose in key art.
    render_view("poster", (-1.85, -5.60, 0.95), target=(0.0, 0.0, 1.20),
                res=(1400, 1900), lens=80, samples=320)
    # Distances are set so a ~2.3 m figure fills the frame at these focal
    # lengths; closer than this and the plume or the sabatons get cropped.
    render_view("hero_34", (-2.95, -3.70, 1.65), target=(0, 0, 1.10),
                samples=160)
    render_view("front", (0.0, -5.00, 1.10), lens=70)
    render_view("side", (5.00, -0.15, 1.10), lens=70)
    render_view("back", (0.30, 5.00, 1.15), lens=70)
    # Straight-on back sits right between the two rim lights, so the cape flattens
    # out. This angle rakes across the folds instead.
    render_view("back34", (3.40, 3.60, 1.55), target=(0, 0, 1.05))
    render_view("head", (-0.55, -1.15, 1.95), target=(0, 0, 1.80),
                res=(800, 800), lens=85)
    render_view("head_side", (1.35, -0.25, 1.90), target=(0, -0.02, 1.80),
                res=(800, 800), lens=85)
    # The legibility check the store-page spec demands: if he does not read as a
    # Templar at Steam app-icon size, the silhouette work has failed. Cropped to
    # the bust, which is what an actual 184px app icon would use.
    render_view("icon_184", (-1.30, -1.85, 1.85), target=(0.0, 0.0, 1.50),
                res=(184, 184), lens=62)
    render_view("icon_full_184", (-2.95, -3.70, 1.65), target=(0, 0, 1.10),
                res=(184, 184), lens=48)

if DO_EXPORT:
    export_fbx(ARMATURE)
