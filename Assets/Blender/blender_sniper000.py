"""
sniper000 — BTDB2-style Sniper Monkey character.

Visual brief (from BTDB2 base tier):
  - Brown fur, tan face/hands/feet, brown eyes
  - Green camo beret with a large yellow circular emblem
  - Grey M24-style bolt-action rifle, scope with a lime-green lens

Project rules (CLAUDE.md): characters must read as rounded armour, never
visible cubes — every primitive gets shade-smooth + subsurf where it makes
sense. Cubes are only acceptable for hard rifle parts where corners read
as "machined steel".
"""

import bpy
import math
import os
import sys
from mathutils import Vector

# ── Paths ─────────────────────────────────────────────────────────────────────
# Worked out from this file's own path (the name its code was compiled under, which
# `blender -P`, build_one.py and exec(compile(src, PATH, "exec")) all set), so they
# hold wherever the repo lives. A copy run from a worktree under .claude/worktrees/
# still writes into the main checkout (CLAUDE.md, "Asset pipeline").
_REPO = os.path.abspath(os.path.join(os.path.dirname(sys._getframe().f_code.co_filename), "..", ".."))
_REPO = _REPO.split(os.sep + os.path.join(".claude", "worktrees") + os.sep)[0]
BLEND_PATH = os.path.join(_REPO, "Assets", "Blender", "sniper000.blend")
FBX_PATH   = os.path.join(_REPO, "Assets", "Models", "sniper000.fbx")

# ══════════════════════════════════════════════════════════════════════════════
#  CLEAR SCENE
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves):
    for block in list(coll):
        if block.users == 0:
            coll.remove(block)

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def make_mat(name, base, *, metallic=0.0, roughness=0.7, emission=None, emission_strength=0.0):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return m

def smooth(obj, subsurf_level=0):
    """Shade smooth, optional subsurf modifier (viewport-applied at export)."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    if subsurf_level > 0:
        ss = obj.modifiers.new("Subsurf", 'SUBSURF')
        ss.levels = subsurf_level
        ss.render_levels = subsurf_level

def add_uv_sphere(name, location, scale, mat, subsurf=1, segments=24, rings=14):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1.0, location=location)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    smooth(o, subsurf)
    return o

def add_cylinder(name, location, radius, depth, mat, *, rotation=(0, 0, 0), vertices=20, subsurf=0):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=depth, vertices=vertices,
        location=location, rotation=rotation)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    smooth(o, subsurf)
    return o

def add_cube(name, location, scale, mat, *, rotation=(0, 0, 0), bevel_width=0.02, bevel_segments=2, subsurf=0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=rotation)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    # bevel for that "rounded armour" feel
    bev = o.modifiers.new("Bevel", 'BEVEL')
    bev.width = bevel_width
    bev.segments = bevel_segments
    smooth(o, subsurf)
    return o

def add_torus(name, location, major, minor, mat, *, rotation=(0, 0, 0), maj_seg=24, min_seg=10):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major, minor_radius=minor,
        major_segments=maj_seg, minor_segments=min_seg,
        location=location, rotation=rotation)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    smooth(o)
    return o

# ══════════════════════════════════════════════════════════════════════════════
#  MATERIALS
# ══════════════════════════════════════════════════════════════════════════════
# Darker, redder fur so it reads clearly distinct from the tan skin under
# Unity's lighting + post-FX. BTDB2 monkey is a chocolate-brown not a tan.
fur_mat       = make_mat("FurBrown",      (0.22, 0.12, 0.06), roughness=0.85)
skin_mat      = make_mat("SkinTan",       (0.94, 0.76, 0.55), roughness=0.65)
eye_white_mat = make_mat("EyeWhite",      (0.96, 0.96, 0.94), roughness=0.30)
pupil_mat     = make_mat("Pupil",         (0.08, 0.05, 0.03), roughness=0.40)

# Beret base — olive green; "camo" mottling is implied through the silhouette.
beret_mat     = make_mat("BeretGreen",    (0.18, 0.30, 0.12), roughness=0.85)
emblem_mat    = make_mat("BeretEmblem",   (0.96, 0.80, 0.10), roughness=0.45, metallic=0.2)
emblem_rim_mat = make_mat("EmblemRim",    (0.55, 0.42, 0.05), roughness=0.5, metallic=0.4)

gun_metal_mat = make_mat("GunMetal",      (0.30, 0.30, 0.33), roughness=0.35, metallic=0.85)
gun_dark_mat  = make_mat("GunDark",       (0.13, 0.13, 0.15), roughness=0.45, metallic=0.70)
scope_lens_mat = make_mat("ScopeLens",    (0.40, 0.95, 0.20), roughness=0.10, metallic=0.7,
                          emission=(0.30, 0.85, 0.15), emission_strength=1.2)

# ══════════════════════════════════════════════════════════════════════════════
#  TORSO  (Z is up; the model faces +Y)
# ══════════════════════════════════════════════════════════════════════════════
TORSO_Z = 0.55
torso = add_uv_sphere(
    "Torso",
    location=(0, 0, TORSO_Z),
    scale=(0.30, 0.26, 0.34),
    mat=fur_mat,
    subsurf=1,
)

# Lighter belly patch — slightly forward, slightly lower than torso centre.
add_uv_sphere(
    "Belly",
    location=(0, 0.08, TORSO_Z - 0.05),
    scale=(0.20, 0.10, 0.18),
    mat=skin_mat,
    subsurf=1,
)

# ══════════════════════════════════════════════════════════════════════════════
#  HEAD
# ══════════════════════════════════════════════════════════════════════════════
HEAD_Z = 1.00
HEAD_R = 0.27

head = add_uv_sphere(
    "Head",
    location=(0, 0, HEAD_Z),
    scale=(HEAD_R, HEAD_R, HEAD_R),
    mat=fur_mat,
    subsurf=2,
)

# Tan face mask — small flattened oval, only the central front of the head.
# Sits just below eye level so the brown fur frames the face.
face = add_uv_sphere(
    "Face",
    location=(0, HEAD_R * 0.78, HEAD_Z - 0.05),
    scale=(0.13, 0.06, 0.10),
    mat=skin_mat,
    subsurf=2,
)

# Muzzle — small ellipsoid protrusion below the eyes.
muzzle = add_uv_sphere(
    "Muzzle",
    location=(0, HEAD_R * 0.95, HEAD_Z - 0.08),
    scale=(0.085, 0.05, 0.060),
    mat=skin_mat,
    subsurf=2,
)

# Nostrils — two tiny dark dots on the muzzle.
for sgn in (-1, 1):
    add_uv_sphere(
        f"Nostril_{'L' if sgn < 0 else 'R'}",
        location=(sgn * 0.025, HEAD_R * 0.85 + 0.05, HEAD_Z - 0.085),
        scale=(0.012, 0.010, 0.012),
        mat=pupil_mat,
        subsurf=1,
    )

# Mouth — short flattened dark slit under the muzzle.
add_uv_sphere(
    "Mouth",
    location=(0, HEAD_R * 0.80, HEAD_Z - 0.13),
    scale=(0.040, 0.012, 0.012),
    mat=pupil_mat,
    subsurf=1,
)

# Ears — flattened spheres on either side of the head.
for sgn in (-1, 1):
    add_uv_sphere(
        f"Ear_{'L' if sgn < 0 else 'R'}",
        location=(sgn * (HEAD_R - 0.02), 0.0, HEAD_Z + 0.02),
        scale=(0.05, 0.07, 0.08),
        mat=fur_mat,
        subsurf=2,
    )
    # Inner ear (tan)
    add_uv_sphere(
        f"EarInner_{'L' if sgn < 0 else 'R'}",
        location=(sgn * (HEAD_R + 0.005), 0.0, HEAD_Z + 0.02),
        scale=(0.025, 0.045, 0.055),
        mat=skin_mat,
        subsurf=2,
    )

# Eyes — whites and pupils. BTDB2 monkeys have small dot pupils on a white sclera.
# Pushed clearly out of the head so they aren't swallowed by fur geometry.
EYE_X = 0.085                    # half-distance between eyes
EYE_Z = HEAD_Z + 0.025
EYE_FWD = HEAD_R * 0.78          # forward distance to centre of eye

for sgn in (-1, 1):
    add_uv_sphere(
        f"EyeWhite_{'L' if sgn < 0 else 'R'}",
        location=(sgn * EYE_X, EYE_FWD, EYE_Z),
        scale=(0.060, 0.045, 0.070),
        mat=eye_white_mat,
        subsurf=2,
    )
    add_uv_sphere(
        f"EyePupil_{'L' if sgn < 0 else 'R'}",
        location=(sgn * EYE_X, EYE_FWD + 0.030, EYE_Z),
        scale=(0.022, 0.018, 0.030),
        mat=pupil_mat,
        subsurf=2,
    )

# Brow ridge — subtle furred line above the eyes for that "stern sniper" vibe.
add_cube(
    "Brow",
    location=(0, HEAD_R * 0.55, EYE_Z + 0.06),
    scale=(0.18, 0.06, 0.025),
    mat=fur_mat,
    bevel_width=0.012,
)

# ══════════════════════════════════════════════════════════════════════════════
#  BERET — green dome with yellow emblem, tilted slightly to one side
# ══════════════════════════════════════════════════════════════════════════════
BERET_TILT = math.radians(-12)   # tip the beret to the monkey's left (-X)

# Crown — flattened sphere (the floppy top of the beret).
beret_crown = add_uv_sphere(
    "BeretCrown",
    location=(0, -0.02, HEAD_Z + 0.20),
    scale=(0.27, 0.27, 0.10),
    mat=beret_mat,
    subsurf=2,
)
beret_crown.rotation_euler = (0, BERET_TILT, 0)

# Brim ring — a torus around the head where the band sits.
beret_brim = add_torus(
    "BeretBrim",
    location=(0, 0, HEAD_Z + 0.13),
    major=0.24, minor=0.025,
    mat=beret_mat,
    rotation=(0, BERET_TILT, 0),
)

# Stem nub on top — tiny cylinder, classic beret detail.
add_cylinder(
    "BeretStem",
    location=(0, -0.02, HEAD_Z + 0.27),
    radius=0.018, depth=0.025,
    mat=beret_mat,
    rotation=(0, BERET_TILT, 0),
)

# Yellow circular emblem on the FRONT of the beret, facing +Y (the camera).
# Cylinder normals run along Y so the disc face is visible from the front.
emblem_y = 0.215
emblem_z = HEAD_Z + 0.18

add_cylinder(
    "EmblemRim",
    location=(0.0, emblem_y, emblem_z),
    radius=0.075, depth=0.012,
    mat=emblem_rim_mat,
    rotation=(math.pi/2, 0, 0),
    vertices=28,
)
add_cylinder(
    "EmblemDisc",
    location=(0.0, emblem_y + 0.008, emblem_z),
    radius=0.062, depth=0.014,
    mat=emblem_mat,
    rotation=(math.pi/2, 0, 0),
    vertices=28,
)
# Centre pip — tiny raised dome facing forward.
add_uv_sphere(
    "EmblemPip",
    location=(0.0, emblem_y + 0.020, emblem_z),
    scale=(0.018, 0.012, 0.018),
    mat=emblem_rim_mat,
    subsurf=1,
)

# ══════════════════════════════════════════════════════════════════════════════
#  ARMS — held forward to grip the rifle (rifle points +Y)
# ══════════════════════════════════════════════════════════════════════════════
SHOULDER_Z = TORSO_Z + 0.18
SHOULDER_X = 0.24

# Both arms are extended forward so the rifle reads clearly. The right arm
# reaches further (supporting the barrel); the left grips the trigger/stock.

# RIGHT ARM ────────────────────────────────────────────────────────────────
add_uv_sphere(
    "RShoulder",
    location=(SHOULDER_X, 0.05, SHOULDER_Z),
    scale=(0.095, 0.095, 0.095),
    mat=fur_mat,
    subsurf=2,
)
add_cylinder(
    "RUpperArm",
    location=(SHOULDER_X - 0.04, 0.22, SHOULDER_Z - 0.04),
    radius=0.065, depth=0.30,
    mat=fur_mat,
    rotation=(math.radians(75), 0, math.radians(-25)),
    vertices=16,
    subsurf=1,
)
add_uv_sphere(
    "RElbow",
    location=(SHOULDER_X - 0.08, 0.35, SHOULDER_Z - 0.07),
    scale=(0.075, 0.075, 0.075),
    mat=fur_mat,
    subsurf=2,
)
add_cylinder(
    "RForearm",
    location=(0.10, 0.50, SHOULDER_Z - 0.08),
    radius=0.060, depth=0.28,
    mat=fur_mat,
    rotation=(math.radians(95), 0, math.radians(25)),
    vertices=16,
    subsurf=1,
)
add_uv_sphere(
    "RHand",
    location=(0.04, 0.62, SHOULDER_Z - 0.10),
    scale=(0.085, 0.090, 0.085),
    mat=skin_mat,
    subsurf=2,
)

# LEFT ARM ─────────────────────────────────────────────────────────────────
add_uv_sphere(
    "LShoulder",
    location=(-SHOULDER_X, 0.05, SHOULDER_Z),
    scale=(0.095, 0.095, 0.095),
    mat=fur_mat,
    subsurf=2,
)
add_cylinder(
    "LUpperArm",
    location=(-SHOULDER_X + 0.05, 0.18, SHOULDER_Z - 0.10),
    radius=0.065, depth=0.26,
    mat=fur_mat,
    rotation=(math.radians(65), 0, math.radians(35)),
    vertices=16,
    subsurf=1,
)
add_uv_sphere(
    "LElbow",
    location=(-0.13, 0.27, SHOULDER_Z - 0.18),
    scale=(0.075, 0.075, 0.075),
    mat=fur_mat,
    subsurf=2,
)
add_cylinder(
    "LForearm",
    location=(-0.08, 0.32, SHOULDER_Z - 0.10),
    radius=0.060, depth=0.24,
    mat=fur_mat,
    rotation=(math.radians(70), 0, math.radians(-25)),
    vertices=16,
    subsurf=1,
)
add_uv_sphere(
    "LHand",
    location=(-0.04, 0.40, SHOULDER_Z - 0.04),
    scale=(0.080, 0.085, 0.080),
    mat=skin_mat,
    subsurf=2,
)

# ══════════════════════════════════════════════════════════════════════════════
#  LEGS — short, stubby, BTD-style
# ══════════════════════════════════════════════════════════════════════════════
HIP_Z = TORSO_Z - 0.30
LEG_X = 0.13
for sgn, label in ((-1, "L"), (1, "R")):
    # Thigh
    add_cylinder(
        f"{label}Thigh",
        location=(sgn * LEG_X, -0.02, HIP_Z - 0.05),
        radius=0.075, depth=0.18,
        mat=fur_mat,
        vertices=16,
        subsurf=1,
    )
    # Knee
    add_uv_sphere(
        f"{label}Knee",
        location=(sgn * LEG_X, -0.02, HIP_Z - 0.14),
        scale=(0.075, 0.075, 0.075),
        mat=fur_mat,
        subsurf=2,
    )
    # Foot — flattened tan oval, pointing slightly outwards.
    add_uv_sphere(
        f"{label}Foot",
        location=(sgn * LEG_X, 0.02, HIP_Z - 0.20),
        scale=(0.085, 0.13, 0.045),
        mat=skin_mat,
        subsurf=2,
    )

# ══════════════════════════════════════════════════════════════════════════════
#  TAIL — curving down and behind, brown with tan tip
# ══════════════════════════════════════════════════════════════════════════════
tail_segments = 7
tail_origin = Vector((0, -0.20, TORSO_Z - 0.05))
for i in range(tail_segments):
    t = i / max(1, tail_segments - 1)
    # Curve back and down.
    px = 0.0
    py = tail_origin.y - 0.05 * i
    pz = tail_origin.z - 0.04 * i + 0.018 * (i * i) * 0.05
    radius = 0.05 - 0.025 * t
    mat = skin_mat if i == tail_segments - 1 else fur_mat
    add_uv_sphere(
        f"TailSeg_{i}",
        location=(px, py, pz),
        scale=(radius, radius, radius),
        mat=mat,
        subsurf=1,
        segments=14, rings=8,
    )

# ══════════════════════════════════════════════════════════════════════════════
#  RIFLE — M24-style bolt action, held horizontally
# ══════════════════════════════════════════════════════════════════════════════
# Frame of reference: rifle long axis runs along +Y (forward).
# Held at chest height between the two hands; scaled chunky for cartoon read.
RIFLE_Y = 0.40
RIFLE_Z = SHOULDER_Z - 0.10
RIFLE_X = 0.0

# Receiver — central block of the rifle.
add_cube(
    "Rifle_Receiver",
    location=(RIFLE_X, RIFLE_Y - 0.08, RIFLE_Z),
    scale=(0.075, 0.26, 0.080),
    mat=gun_metal_mat,
    bevel_width=0.012,
    bevel_segments=2,
)

# Barrel — chunky cylinder forward of the receiver.
add_cylinder(
    "Rifle_Barrel",
    location=(RIFLE_X, RIFLE_Y + 0.36, RIFLE_Z),
    radius=0.030, depth=0.65,
    mat=gun_metal_mat,
    rotation=(math.pi/2, 0, 0),
    vertices=20,
)
# Muzzle flare ring at the front.
add_cylinder(
    "Rifle_Muzzle",
    location=(RIFLE_X, RIFLE_Y + 0.69, RIFLE_Z),
    radius=0.038, depth=0.05,
    mat=gun_dark_mat,
    rotation=(math.pi/2, 0, 0),
    vertices=20,
)

# Forestock — wooden/composite handguard under the front of the barrel.
add_cube(
    "Rifle_Forestock",
    location=(RIFLE_X, RIFLE_Y + 0.20, RIFLE_Z - 0.040),
    scale=(0.075, 0.40, 0.060),
    mat=gun_dark_mat,
    bevel_width=0.018,
    bevel_segments=2,
)

# Stock body — extends back from the receiver toward the shoulder.
add_cube(
    "Rifle_Stock",
    location=(RIFLE_X, RIFLE_Y - 0.36, RIFLE_Z - 0.015),
    scale=(0.075, 0.40, 0.090),
    mat=gun_dark_mat,
    bevel_width=0.020,
    bevel_segments=2,
)
# Butt pad — slightly larger square at the very back.
add_cube(
    "Rifle_Buttpad",
    location=(RIFLE_X, RIFLE_Y - 0.58, RIFLE_Z - 0.015),
    scale=(0.085, 0.030, 0.140),
    mat=gun_dark_mat,
    bevel_width=0.020,
    bevel_segments=2,
)

# Pistol grip — angled cube under the receiver.
add_cube(
    "Rifle_Grip",
    location=(RIFLE_X, RIFLE_Y - 0.20, RIFLE_Z - 0.130),
    scale=(0.060, 0.080, 0.140),
    mat=gun_dark_mat,
    rotation=(math.radians(-12), 0, 0),
    bevel_width=0.018,
    bevel_segments=2,
)

# Magazine — small block protruding from the underside of the receiver.
add_cube(
    "Rifle_Magazine",
    location=(RIFLE_X, RIFLE_Y - 0.08, RIFLE_Z - 0.115),
    scale=(0.065, 0.100, 0.080),
    mat=gun_metal_mat,
    bevel_width=0.012,
    bevel_segments=2,
)

# Trigger guard — torus arc beneath the receiver.
add_torus(
    "Rifle_TriggerGuard",
    location=(RIFLE_X, RIFLE_Y - 0.18, RIFLE_Z - 0.105),
    major=0.040, minor=0.008,
    mat=gun_metal_mat,
    rotation=(0, math.pi/2, 0),
)

# Bolt handle — cylinder protruding right from the receiver.
add_cylinder(
    "Rifle_Bolt",
    location=(RIFLE_X + 0.10, RIFLE_Y - 0.05, RIFLE_Z + 0.020),
    radius=0.014, depth=0.090,
    mat=gun_metal_mat,
    rotation=(0, math.radians(70), 0),
    vertices=12,
)
# Bolt knob.
add_uv_sphere(
    "Rifle_BoltKnob",
    location=(RIFLE_X + 0.145, RIFLE_Y - 0.05, RIFLE_Z + 0.035),
    scale=(0.026, 0.026, 0.026),
    mat=gun_metal_mat,
    subsurf=1,
)

# Scope — sits above the receiver, supported by two ring mounts.
SCOPE_Z = RIFLE_Z + 0.115
SCOPE_Y = RIFLE_Y + 0.04

# Scope tube
add_cylinder(
    "Rifle_ScopeTube",
    location=(RIFLE_X, SCOPE_Y, SCOPE_Z),
    radius=0.038, depth=0.36,
    mat=gun_metal_mat,
    rotation=(math.pi/2, 0, 0),
    vertices=22,
)
# Front objective bell (slightly fatter)
add_cylinder(
    "Rifle_ScopeBell",
    location=(RIFLE_X, SCOPE_Y + 0.20, SCOPE_Z),
    radius=0.050, depth=0.07,
    mat=gun_metal_mat,
    rotation=(math.pi/2, 0, 0),
    vertices=22,
)
# Front lens — lime green emissive disc.
add_cylinder(
    "Rifle_LensFront",
    location=(RIFLE_X, SCOPE_Y + 0.238, SCOPE_Z),
    radius=0.044, depth=0.014,
    mat=scope_lens_mat,
    rotation=(math.pi/2, 0, 0),
    vertices=22,
)
# Rear lens — same colour, smaller.
add_cylinder(
    "Rifle_LensRear",
    location=(RIFLE_X, SCOPE_Y - 0.188, SCOPE_Z),
    radius=0.034, depth=0.012,
    mat=scope_lens_mat,
    rotation=(math.pi/2, 0, 0),
    vertices=22,
)
# Elevation/windage turret on top of the scope.
add_cylinder(
    "Rifle_ScopeTurret",
    location=(RIFLE_X, SCOPE_Y, SCOPE_Z + 0.052),
    radius=0.026, depth=0.050,
    mat=gun_metal_mat,
    vertices=16,
)
# Two scope mount rings (rear + front) clamping the tube to the receiver.
for ring_y in (SCOPE_Y - 0.12, SCOPE_Y + 0.12):
    add_torus(
        f"Rifle_ScopeRing_{ring_y:.2f}",
        location=(RIFLE_X, ring_y, SCOPE_Z),
        major=0.045, minor=0.012,
        mat=gun_dark_mat,
        rotation=(0, math.pi/2, 0),
    )
    add_cube(
        f"Rifle_ScopeMountBlock_{ring_y:.2f}",
        location=(RIFLE_X, ring_y, SCOPE_Z - 0.060),
        scale=(0.035, 0.022, 0.060),
        mat=gun_dark_mat,
        bevel_width=0.006,
    )

# ══════════════════════════════════════════════════════════════════════════════
#  GROUND DISC — small base so the model sits cleanly in the editor
# ══════════════════════════════════════════════════════════════════════════════
add_cylinder(
    "BaseDisc",
    location=(0, 0, 0.005),
    radius=0.30, depth=0.01,
    mat=gun_dark_mat,
    vertices=24,
)

# ══════════════════════════════════════════════════════════════════════════════
#  SAVE & EXPORT
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
print(f"Saved: {BLEND_PATH}")

bpy.ops.export_scene.fbx(
    filepath=FBX_PATH,
    use_selection=False,
    object_types={'MESH'},
    bake_anim=False,
    add_leaf_bones=False,
    axis_forward='-Z',
    axis_up='Y',
    global_scale=1.0,
)
print(f"Exported: {FBX_PATH}")
print("Done!")
