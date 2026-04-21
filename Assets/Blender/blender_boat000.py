import bpy
import bmesh
import math
from mathutils import Vector, Matrix

def bake_rotation_on_mesh(obj, rotation_euler):
    """Apply a rotation to an object's mesh data directly, leaving its location and
    rotation transform untouched. Works around Blender 4.5's transform_apply
    clobbering the object location even when only rotation=True is requested.

    shape_keys=True ensures any attached blendshape data is rotated along with
    the basis mesh — otherwise the shape key deltas stay in the un-rotated frame
    and the blendshape morphs toward nonsense positions."""
    rx, ry, rz = rotation_euler
    mat = Matrix.Rotation(rz, 4, 'Z') @ Matrix.Rotation(ry, 4, 'Y') @ Matrix.Rotation(rx, 4, 'X')
    obj.data.transform(mat, shape_keys=True)

# -- Paths ---------------------------------------------------------------------
BLEND_DST = r"C:\Users\LachlanB\TD\Assets\Blender\boat000.blend"
FBX_PATH  = r"C:\Users\LachlanB\TD\Assets\Models\boat000.fbx"

# -- Empty scene ---------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)

# -- Materials -----------------------------------------------------------------
def make_material(name, rgba, metallic=0.0, smoothness=0.2):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = 1.0 - smoothness
    return mat

mat_wood = make_material("BoatWood", (0.10, 0.07, 0.06, 1.0), 0.0, 0.2)
mat_sail = make_material("BoatSail", (0.42, 0.06, 0.08, 1.0), 0.0, 0.2)
mat_iron = make_material("BoatIron", (0.18, 0.18, 0.20, 1.0), 0.3, 0.4)
# A slightly paler, drier wood for damaged plank ends — gives the loose / torn
# planks a visible edge against the near-black hull.
mat_wood_pale = make_material("BoatWoodPale", (0.24, 0.18, 0.14, 1.0), 0.0, 0.15)
# Off-white bone material for the skull figurehead so it pops against the hull.
mat_bone = make_material("BoatBone", (0.80, 0.76, 0.70, 1.0), 0.0, 0.3)

def make_emissive_material(name, rgba, strength=3.0):
    """Principled BSDF with non-zero emission strength. Blender's FBX exporter
    writes this as the FBX EmissiveColor + EmissiveFactor which Unity's URP
    importer picks up on the imported material. Used for glowing cabin windows
    and the stern lantern so the boat reads as inhabited at night / indoors."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.5
    # In Blender 4.x the emission inputs are named "Emission Color" and
    # "Emission Strength" (renamed from "Emission" in 3.x). Guard by name so
    # this doesn't hard-crash on a minor API change.
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = rgba
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = strength
    return mat

# Warm amber cabin-window glow — reads as candlelight from within.
mat_glow = make_emissive_material("CabinGlow", (1.0, 0.55, 0.2, 1.0), strength=3.0)

# -- Helpers -------------------------------------------------------------------
def select_only(obj):
    for o in bpy.data.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def bevel_subsurf(obj, bevel_offset=0.08, bevel_segs=2, subsurf_levels=2):
    select_only(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bevel(offset=bevel_offset, segments=bevel_segs)
    bpy.ops.object.mode_set(mode='OBJECT')
    mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
    mod.levels = subsurf_levels
    mod.render_levels = subsurf_levels
    bpy.ops.object.modifier_apply(modifier="Subsurf")
    bpy.ops.object.shade_smooth()

def add_ripple_shapekeys(obj, amplitude, wavelength, weight_along_local_x=False):
    """Bake TWO quadrature-phase sine wave shape keys: 'Ripple' (phase 0) and 'Ripple_Q' (phase pi/2).
    At runtime the animator drives these with cos(t) and sin(t) so their sum is a traveling wave
    sin(x+t) instead of a static-shape pulse.

    Wave phase travels along local Y; displacement is along local Z (the plane normal).
    If weight_along_local_x: weight = x_norm so the -X edge is anchored (flag pole side)."""
    if not obj.data.shape_keys:
        obj.shape_key_add(name='Basis')
    sk0 = obj.shape_key_add(name='Ripple')
    sk1 = obj.shape_key_add(name='Ripple_Q')
    xs = [v.co.x for v in obj.data.vertices]
    x_min, x_max = min(xs), max(xs)
    x_range = max(0.001, x_max - x_min)
    for i, v in enumerate(obj.data.vertices):
        phase = (v.co.y / wavelength) * 2.0 * math.pi
        w = (v.co.x - x_min) / x_range if weight_along_local_x else 1.0
        # sk0 = sin(phase) * w, sk1 = cos(phase) * w. Paired with sin(t)/cos(t) weights these
        # sum to sin(phase + t) * w — a wave that travels along local Y.
        disp0 = amplitude * math.sin(phase) * w
        disp1 = amplitude * math.cos(phase) * w
        sk0.data[i].co = v.co + Vector((0.0, 0.0, disp0))
        sk1.data[i].co = v.co + Vector((0.0, 0.0, disp1))

def add_dummy_armature(name, mesh_obj):
    """Add a single-bone armature, parent the mesh to it, weight all verts to the bone.
    This causes Unity's FBX importer to create a SkinnedMeshRenderer."""
    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm = bpy.context.active_object
    arm.name = name
    bone = arm.data.bones[0]
    # Default bone is named "Bone"
    vg = mesh_obj.vertex_groups.new(name=bone.name)
    vg.add(list(range(len(mesh_obj.data.vertices))), 1.0, 'REPLACE')
    mesh_obj.parent = arm
    mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = arm
    return arm

# -- Hull (shaped galleon) -----------------------------------------------------
# Coordinate convention used by this script — matches Unity (because our FBX
# export with bake_space_transform=True passes Blender axes through 1:1):
#    +X = starboard (ship's right)      -X = port (ship's left)
#    +Y = up                             -Y = down
#    +Z = bow (ship's forward)           -Z = stern
#
# The hull is built by lofting between cross-section ribs along the Z (fore-aft)
# axis. Each rib has 5 vertices forming a shallow U: keel (bottom centre), chine
# port + starboard (widest point under water), rail port + starboard (top of hull).
#
# Shaping rules encoded in the section table:
#   * Sheer   — deck_y rises at bow and stern (hull is taller at the ends).
#   * Bow     — final rib collapses to a point at X=0, producing a vertical cutwater.
#   * Stern   — first rib has finite width; a pentagon cap closes the transom.
#   * Keel    — chine_width narrows toward the ends so the underwater body tapers
#               in as well as the deck line.
#
# Row format: (z, keel_y, deck_y, half_width_keel, half_width_deck)
# z is the fore-aft position of the rib (stern at -1.10, bow at +1.10).
_SECTIONS = [
    (-1.10,  0.05,  0.70,  0.12,  0.32),   # stern transom (flat back face)
    (-0.95, -0.02,  0.62,  0.25,  0.40),
    (-0.60, -0.10,  0.55,  0.30,  0.42),
    (-0.20, -0.12,  0.52,  0.32,  0.42),
    ( 0.00, -0.12,  0.50,  0.32,  0.42),   # midship — widest beam
    ( 0.20, -0.12,  0.52,  0.32,  0.42),
    ( 0.60, -0.10,  0.55,  0.25,  0.38),
    ( 0.90, -0.05,  0.60,  0.10,  0.20),
    ( 1.10,  0.10,  0.68,  0.00,  0.00),   # bow cutwater (collapsed to a point)
]

def build_hull():
    """Construct the shaped hull mesh using bmesh. Returns the created Object."""
    mesh = bpy.data.meshes.new("HullMesh")
    obj = bpy.data.objects.new("Hull", mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()

    # Build one rib of 5 verts per section.
    # Rib layout (looking from above, bow toward +Z):
    #   keel (0, ky, z), chine_port (-hw_k, ky, z), rail_port (-hw_d, dy, z),
    #   rail_stbd (+hw_d, dy, z), chine_stbd (+hw_k, ky, z).
    ribs = []
    for (z, ky, dy, hw_k, hw_d) in _SECTIONS:
        keel = bm.verts.new(( 0.0,  ky, z))
        cp   = bm.verts.new((-hw_k, ky, z))
        rp   = bm.verts.new((-hw_d, dy, z))
        rs   = bm.verts.new(( hw_d, dy, z))
        cs   = bm.verts.new(( hw_k, ky, z))
        ribs.append((keel, cp, rp, rs, cs))

    # Bridge adjacent ribs with 5 quads: 2 side panels per flank, plus the deck top.
    # Winding chosen so normals point outward; a final recalc_face_normals pass cleans up.
    for i in range(len(ribs) - 1):
        ak, acp, arp, ars, acs = ribs[i]
        bk, bcp, brp, brs, bcs = ribs[i + 1]
        bm.faces.new([ak,  acp, bcp, bk])     # bottom port    (keel → chine_p)
        bm.faces.new([acp, arp, brp, bcp])    # side port      (chine_p → rail_p)
        bm.faces.new([arp, ars, brs, brp])    # deck top       (rail_p → rail_s)
        bm.faces.new([ars, acs, bcs, brs])    # side starboard (rail_s → chine_s)
        bm.faces.new([acs, ak,  bk,  bcs])    # bottom stbd    (chine_s → keel)

    # Stern transom: fill the first rib with a pentagon. The last (bow) rib is a
    # degenerate 0-width line, so bridging handles it naturally — no cap needed.
    sk, scp, srp, srs, scs = ribs[0]
    bm.faces.new([sk, scs, srs, srp, scp])

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    # Select so subsequent edit-mode ops target this hull.
    for o in bpy.context.scene.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj

hull = build_hull()
# Light bevel + one subdivision smooths the faceted rib geometry into flowing
# planks without losing the stern transom's corners.
bevel_subsurf(hull, bevel_offset=0.02, bevel_segs=1, subsurf_levels=1)
hull.data.materials.append(mat_wood)

def hull_half_width_at(y, z):
    """Sample the hull's half-width at (y, z) using the _SECTIONS table. Used by
    surface-hugging features (strakes, chain trim, damage backings) so they sit
    flush against the tapered hull instead of floating where the hull narrows.

    Returns the pre-bevel hull half-width; callers typically add a small outward
    offset to avoid z-fighting with the hull surface."""
    for i in range(len(_SECTIONS) - 1):
        za, zb = _SECTIONS[i][0], _SECTIONS[i + 1][0]
        if za <= z <= zb:
            t = (z - za) / (zb - za) if zb != za else 0.0
            ky   = _SECTIONS[i][1] + t * (_SECTIONS[i + 1][1] - _SECTIONS[i][1])
            dy   = _SECTIONS[i][2] + t * (_SECTIONS[i + 1][2] - _SECTIONS[i][2])
            hw_k = _SECTIONS[i][3] + t * (_SECTIONS[i + 1][3] - _SECTIONS[i][3])
            hw_d = _SECTIONS[i][4] + t * (_SECTIONS[i + 1][4] - _SECTIONS[i][4])
            if dy > ky:
                u = max(0.0, min(1.0, (y - ky) / (dy - ky)))
                return hw_k + u * (hw_d - hw_k)
            return hw_k
    return 0.0

# -- Strakes (horizontal planks running the length of the hull) ---------------
# Two reinforcing planks per side — a waterline strake low on the hull and a
# heavier "wale" just below deck. Implemented as thin tapered boxes rather than
# true hull-conforming strips; at the TD camera distance they read as planking.
def make_contour_strake(name, y, length_half, thickness=0.014, height=0.028,
                         offset=0.002, z_samples=56):
    """Build a strake that follows the hull's curved contour. Sample the hull
    half-width at regular Z steps; emit a small box segment at each hull X.
    Without this the strake sits at a fixed X and floats off the hull where the
    hull tapers toward the bow/stern."""
    out_parts = {"L": [], "R": []}
    # March along Z in small steps. Each segment is a narrow box placed at the
    # local hull X, oriented along Z. Segments are joined per side at the end.
    step = (2.0 * length_half) / z_samples
    for i in range(z_samples):
        z_mid = -length_half + (i + 0.5) * step
        hw = hull_half_width_at(y, z_mid)
        if hw < 0.02:   # skip where the hull has effectively collapsed to a line
            continue
        for side_tag, side_sign in (("L", -1.0), ("R", +1.0)):
            x_mid = (hw + offset) * side_sign
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x_mid, y, z_mid))
            s = bpy.context.active_object
            s.name = f"{name}_{side_tag}_Seg{i}"
            s.scale = (thickness, height, step * 1.05)   # 1.05 overlap avoids visible gaps
            bpy.ops.object.transform_apply(scale=True)
            s.data.materials.append(mat_wood)
            out_parts[side_tag].append(s)
    # Join each side into a single mesh so the hierarchy stays tidy.
    joined = []
    for side_tag in ("L", "R"):
        parts = out_parts[side_tag]
        if not parts:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        for p in parts:
            p.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.join()
        j = bpy.context.active_object
        j.name = f"{name}_{side_tag}"
        bpy.ops.object.shade_smooth()
        joined.append(j)
    return joined

# Waterline strake just above the waterline. Main wale higher up under deck.
# Both now follow the hull curvature instead of sitting on a fixed X.
strakes  = make_contour_strake("Waterline", y=0.05, length_half=0.92)
strakes += make_contour_strake("MainWale",  y=0.34, length_half=1.00)

# -- Gunport frames (iron trim around the cannon openings in the hull) --------
# Small iron-material squares bolted to the hull side, framing each cannon as it
# passes through. They sit a hair outside the hull (X=+/-0.44 vs hull 0.42) so
# they visibly frame the opening rather than clipping inside the planks.
def make_gunport(name, x_side):
    # Sample the hull's X at the gunport's (y=0.44, z=0) so the frame sits flush
    # on the hull's deck-level edge — 0.410 at midship after hull taper.
    hw_here = hull_half_width_at(0.44, 0.0)
    bpy.ops.mesh.primitive_cube_add(size=1,
                                     location=((hw_here + 0.012) * x_side, 0.44, 0.0))
    g = bpy.context.active_object
    g.name = name
    # Scale: thin along X (perpendicular to hull side — surface trim thickness),
    # 0.18 along Y (tall enough to frame the cannon vertically), 0.18 along Z
    # (wide enough fore-aft to frame the cannon barrel).
    g.scale = (0.025, 0.18, 0.18)
    bpy.ops.object.transform_apply(scale=True)
    bevel_subsurf(g, bevel_offset=0.012, bevel_segs=1, subsurf_levels=1)
    g.data.materials.append(mat_iron)
    return g

gunport_l = make_gunport("GunportFrame_L", -1)
gunport_r = make_gunport("GunportFrame_R", +1)

# -- Masts ---------------------------------------------------------------------
# Blender's primitive_cylinder_add creates a cylinder aligned with its local Z
# axis. In our Unity-aligned convention Z is FORE-AFT, so we rotate the cylinder
# -90° about X to bring its long axis onto +Y (up) before applying the transform.
def make_mast(name, z, height):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=height,
                                        location=(0, 0.5 + height/2, z))
    m = bpy.context.active_object
    m.name = name
    # Rotate vertices directly so the cylinder's long axis goes from Blender +Z
    # (default) to +Y (up). Preserves the object's location; transform_apply would not.
    bake_rotation_on_mesh(m, (-math.pi/2, 0, 0))
    bevel_subsurf(m, bevel_offset=0.01, bevel_segs=1, subsurf_levels=1)
    m.data.materials.append(mat_wood)
    return m

# MastFore at Z=+0.45 (toward bow), MastMain at Z=-0.25 (toward stern — main
# mast is traditionally slightly aft of amidships on a small galleon).
mast_fore = make_mast("MastFore",  0.45, 1.4)
mast_main = make_mast("MastMain", -0.25, 1.7)

# -- Sails (skinned mesh + Ripple shape key) ----------------------------------
def make_sail(name, mast_obj, width, height, y_offset, amplitude=0.10, wavelength=0.7):
    # Build flat in XY plane at origin; plane normal is +Z.
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    sail = bpy.context.active_object
    sail.name = name
    # width becomes the fore-aft sail dimension (along Z after rotation),
    # height becomes vertical (Y).
    sail.scale = (width, height, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    # Subdivide for shape-key resolution.
    select_only(sail)
    bpy.ops.object.mode_set(mode='EDIT')
    for _ in range(3):
        bpy.ops.mesh.subdivide()
    bpy.ops.object.mode_set(mode='OBJECT')
    # Shape keys BEFORE rotation — the ripple displacement is baked along the
    # plane's initial +Z normal and rides the rotation with the geometry.
    add_ripple_shapekeys(sail, amplitude=amplitude, wavelength=wavelength)
    # Rotate the mesh +90° around Y so the plane ends up in the YZ-plane with
    # normal +X (facing port/starboard). Direct mesh.transform preserves the
    # object's location assignment below.
    bake_rotation_on_mesh(sail, (0, math.pi/2, 0))
    # Position on mast: same Z as the mast (fore-aft), Y shifted by y_offset.
    sail.location = (0, mast_obj.location.y + y_offset, mast_obj.location.z)
    sail.data.materials.append(mat_sail)
    bpy.ops.object.shade_smooth()
    # Dummy armature so Unity imports as SkinnedMeshRenderer.
    add_dummy_armature(name + "_Armature", sail)
    return sail

# Amplitude 0.10: at the old value (0.04) the sail ripple was ~4cm on a 60-100cm
# sail and read as static in play. 10cm is visibly billowing without deflating
# the sail shape.
sail_fore = make_sail("SailFore", mast_fore, width=0.6,  height=1.0, y_offset=0.0, amplitude=0.10, wavelength=0.7)
sail_main = make_sail("SailMain", mast_main, width=0.75, height=1.2, y_offset=0.1, amplitude=0.10, wavelength=0.7)

# -- Flag (skinned mesh + Ripple shape keys, anchored at mast edge) -----------
# Flag is authored flat in XY (just like sails), then rotated around Y so it
# stands vertical in the YZ-plane with normal along +X. The `weight_along_local_x`
# anchor applied BEFORE rotation pins the original -X edge (pre-rotation) — which
# after R_y(+90°) ends up as the +Z edge — so the flag's "mast" edge in the
# rotated frame sits at local +Z. We offset the flag's origin -0.13 along Z from
# the mast so that anchor edge lands right at the mast.
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
flag = bpy.context.active_object
flag.name = "Flag"
flag.scale = (0.25, 0.15, 1.0)
bpy.ops.object.transform_apply(scale=True)
select_only(flag)
bpy.ops.object.mode_set(mode='EDIT')
for _ in range(2):
    bpy.ops.mesh.subdivide()
bpy.ops.object.mode_set(mode='OBJECT')
add_ripple_shapekeys(flag, amplitude=0.18, wavelength=0.4, weight_along_local_x=True)
bake_rotation_on_mesh(flag, (0, math.pi/2, 0))
flag.location = (0, mast_main.location.y + 0.85, mast_main.location.z - 0.13)
flag.data.materials.append(mat_sail)
bpy.ops.object.shade_smooth()
add_dummy_armature("Flag_Armature", flag)

# -- Cannons (rigid, fixed angles) --------------------------------------------
# Each cannon is a single mesh made of 6 joined primitives so the silhouette
# reads as a cast-bronze gun rather than a pipe:
#   * tapered barrel (thicker at the breech, thinner at the muzzle)
#   * muzzle lip (torus at the outer end)
#   * 2 reinforcement rings (toruses along the barrel)
#   * breech hemisphere (rounded back end, partly buried in the barrel)
#   * cascabel (small ball knob behind the breech)
#
# Geometry lives in the boat's local frame where +X is starboard, Y is up and Z
# is fore-aft. The barrel axis runs along ±X so the breech sits inside the hull
# and the muzzle pokes out through the gunport.
#
# For port (-X) the barrel is mirrored via a -90° Y-rotation instead of +90°, so
# the breech ends up on the inner (centerline) side for both sides symmetrically.
def make_cannon(name, port_side):
    """Build a detailed cannon and return the joined mesh object.

    port_side: -1 for port (-X hull side), +1 for starboard (+X).
    """
    sign = 1.0 if port_side > 0 else -1.0
    base_x = 0.42 * sign          # cannon centre at the hull edge
    inner_x = base_x - 0.175 * sign   # breech end of barrel (toward centerline)
    outer_x = base_x + 0.175 * sign   # muzzle end of barrel
    cy = 0.45                     # shared Y height for every part

    parts = []

    # Barrel — frustum with radius1 at -Z (→ inner end after rotation) and
    # radius2 at +Z (→ outer end). For port we flip the Y-rotation sign so the
    # larger radius (breech) still lands on the inner side.
    bpy.ops.mesh.primitive_cone_add(radius1=0.070, radius2=0.055, depth=0.35,
                                     vertices=24, location=(base_x, cy, 0.0))
    barrel = bpy.context.active_object
    bake_rotation_on_mesh(barrel, (0, (math.pi / 2) * sign, 0))
    parts.append(barrel)

    # Muzzle lip — a thin torus around the outer end of the barrel.
    bpy.ops.mesh.primitive_torus_add(major_radius=0.062, minor_radius=0.012,
                                     major_segments=20, minor_segments=8,
                                     location=(outer_x, cy, 0.0))
    muzzle = bpy.context.active_object
    # Default torus lies in XY-plane (normal +Z); rotate so its normal aligns
    # with the barrel axis (±X). Sign doesn't matter for a symmetric torus.
    bake_rotation_on_mesh(muzzle, (0, math.pi / 2, 0))
    parts.append(muzzle)

    # Reinforcement rings — at 35% and 70% of barrel length measured from breech.
    for ring_t in (0.35, 0.70):
        rx = inner_x + (outer_x - inner_x) * ring_t
        # Barrel radius at this t lerps from breech (0.070) to muzzle (0.055);
        # the ring sits a little proud (≈0.010) so it casts a clear shadow line.
        barrel_r = 0.070 + (0.055 - 0.070) * ring_t
        bpy.ops.mesh.primitive_torus_add(major_radius=barrel_r + 0.010,
                                         minor_radius=0.008,
                                         major_segments=18, minor_segments=6,
                                         location=(rx, cy, 0.0))
        ring = bpy.context.active_object
        bake_rotation_on_mesh(ring, (0, math.pi / 2, 0))
        parts.append(ring)

    # Breech hemisphere — full UV sphere centred at the inner barrel face; half
    # lives inside the barrel, half sticks out as the rounded breech.
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.070, segments=16, ring_count=8,
                                          location=(inner_x, cy, 0.0))
    parts.append(bpy.context.active_object)

    # Cascabel — small decorative knob sticking out further inward past the breech.
    # Offset has to clear the breech sphere (radius 0.070) plus the cascabel radius
    # (0.030), so 0.105 from inner_x ensures the knob pokes out behind the breech
    # dome instead of hiding inside it.
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.030, segments=14, ring_count=7,
                                          location=(inner_x - 0.105 * sign, cy, 0.0))
    parts.append(bpy.context.active_object)

    # Cascabel neck — short cylinder connecting the cascabel to the breech so the
    # knob doesn't look like it's floating. Cylinder default is along Z; rotate to
    # align with the barrel (±X) the same way the barrel is rotated.
    bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=0.06, vertices=10,
                                         location=(inner_x - 0.065 * sign, cy, 0.0))
    neck = bpy.context.active_object
    bake_rotation_on_mesh(neck, (0, (math.pi / 2) * sign, 0))
    parts.append(neck)

    # Join all parts into one mesh so Unity sees a single CannonPort_L/R object.
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    c = bpy.context.active_object
    c.name = name

    # One shared iron material; the join concatenates slots from each primitive
    # so clear them all first to avoid ending up with 5 duplicate iron slots.
    c.data.materials.clear()
    c.data.materials.append(mat_iron)
    bpy.ops.object.shade_smooth()
    return c

cannon_l = make_cannon("CannonPort_L", port_side=-1)  # port
cannon_r = make_cannon("CannonPort_R", port_side=+1)  # starboard

# -- Superstructure & decoration ----------------------------------------------
# Everything below adds detail on top of the bare hull: raised decks, stairs,
# enclosed cabins (with glowing windows in the stern gallery), a ship's wheel,
# yardarms, bowsprit + jib, rudder, railings, torn plank damage, a skull
# figurehead, a bell, a stern lantern, and iron chain trim.
#
# Each piece appends itself to `extras`; they all get parented to Turret at the
# end alongside the original hull parts.
extras = []

# --- Raised decks (poop aft, forecastle forward) -----------------------------
def make_raised_deck(name, z_center, length_z, width_x, y_top=0.80, thickness=0.04):
    """Flat plank-style raised deck platform. Thin box beveled for plank feel."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, y_top - thickness / 2, z_center))
    d = bpy.context.active_object
    d.name = name
    d.scale = (width_x, thickness, length_z)
    bpy.ops.object.transform_apply(scale=True)
    select_only(d)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bevel(offset=0.008, segments=1)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.shade_smooth()
    d.data.materials.append(mat_wood)
    return d

# Poop: from z = -1.05 (stern) to z = -0.50 — covers the aft third.
poop_deck = make_raised_deck("PoopDeck", z_center=-0.775, length_z=0.55, width_x=0.56)
# Forecastle: shorter because the bow tapers in sharply.
forecastle = make_raised_deck("Forecastle", z_center=+0.725, length_z=0.45, width_x=0.40)
extras += [poop_deck, forecastle]

# --- Cabin bulkhead walls (facing main deck, under each raised deck) ---------
def make_cabin_wall(name, x_size, z_pos, y_bottom=0.50, y_top=0.76, thickness=0.03):
    y_center = (y_top + y_bottom) * 0.5
    y_height = y_top - y_bottom
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, y_center, z_pos))
    w = bpy.context.active_object
    w.name = name
    w.scale = (x_size, y_height, thickness)
    bpy.ops.object.transform_apply(scale=True)
    w.data.materials.append(mat_wood)
    return w

poop_front_wall = make_cabin_wall("PoopFrontWall", x_size=0.56, z_pos=-0.50)
forecastle_rear_wall = make_cabin_wall("ForecastleRearWall", x_size=0.40, z_pos=+0.50)
extras += [poop_front_wall, forecastle_rear_wall]

# --- Stern gallery windows (emissive, on the outside of the transom) ---------
# Three small panes giving the captain's quarters a warm amber glow visible from
# behind the boat. Positioned at y between main deck (0.50) and poop deck (0.80).
def make_stern_window(x, y=0.62, z=-1.11, size_x=0.09, size_y=0.10):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    w = bpy.context.active_object
    tag = 'M' if abs(x) < 0.01 else ('L' if x < 0 else 'R')
    w.name = f"SternWindow_{tag}"
    # Thin along Z — reads as a pane sitting flush against the transom.
    w.scale = (size_x, size_y, 0.012)
    bpy.ops.object.transform_apply(scale=True)
    w.data.materials.append(mat_glow)
    return w

stern_windows = [make_stern_window(x) for x in (-0.18, 0.0, +0.18)]
extras += stern_windows

# Small side-cabin windows on the forecastle front wall, also emissive. Gives the
# bow-cabin a matching lit look so the boat reads as inhabited end-to-end.
def make_side_window(x, y=0.62, z=0.51, size_x=0.06, size_y=0.08):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    w = bpy.context.active_object
    w.name = f"ForecastleWindow_{'L' if x < 0 else 'R'}"
    w.scale = (size_x, size_y, 0.012)
    bpy.ops.object.transform_apply(scale=True)
    w.data.materials.append(mat_glow)
    return w

fore_windows = [make_side_window(-0.10), make_side_window(+0.10)]
extras += fore_windows

# --- Stairs (main deck up to each raised deck) -------------------------------
def make_stairs(name, z_base, z_step, y_top=0.80, step_count=3, width=0.18):
    """Series of rising cuboid steps from y=0.50 (main deck) to y_top."""
    parts = []
    y_main = 0.50
    rise_per = (y_top - y_main) / step_count
    run_per = z_step / step_count
    for i in range(step_count):
        step_y = y_main + rise_per * (i + 0.5)
        step_z = z_base + run_per * (i + 0.5)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, step_y, step_z))
        s = bpy.context.active_object
        s.name = f"{name}_Step{i}"
        s.scale = (width, rise_per + 0.02, abs(run_per) + 0.02)
        bpy.ops.object.transform_apply(scale=True)
        s.data.materials.append(mat_wood)
        parts.append(s)
    return parts

extras += make_stairs("PoopStairs", z_base=-0.48, z_step=-0.22)
extras += make_stairs("ForecastleStairs", z_base=+0.48, z_step=+0.22)

# --- Ship's wheel (spoked wheel on a post, mounted on the poop deck) ---------
def make_ships_wheel():
    """Rim torus + hub sphere + 6 spokes + 6 handles + vertical mounting post.
    Axle along X so the helmsman faces forward. All joined into one mesh."""
    parts = []
    wheel_x, wheel_y, wheel_z = 0.0, 0.95, -0.55
    rim_r = 0.09
    # Rim (torus in XY-plane by default → rotate so normal is +X).
    bpy.ops.mesh.primitive_torus_add(major_radius=rim_r, minor_radius=0.010,
                                     major_segments=24, minor_segments=6,
                                     location=(wheel_x, wheel_y, wheel_z))
    rim = bpy.context.active_object; rim.name = "_WheelRim"
    bake_rotation_on_mesh(rim, (0, math.pi / 2, 0))
    parts.append(rim)
    # Hub
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, segments=12, ring_count=6,
                                         location=(wheel_x, wheel_y, wheel_z))
    hub = bpy.context.active_object; hub.name = "_WheelHub"
    parts.append(hub)
    # 6 spokes radiating outward in the YZ-plane + handle on each spoke end.
    for i in range(6):
        a = i * math.pi / 3
        dy, dz = math.cos(a) * rim_r * 0.5, math.sin(a) * rim_r * 0.5
        bpy.ops.mesh.primitive_cylinder_add(radius=0.006, depth=rim_r * 0.95,
                                            vertices=8,
                                            location=(wheel_x, wheel_y + dy, wheel_z + dz))
        sp = bpy.context.active_object; sp.name = f"_WheelSpoke{i}"
        # Default cylinder along Z; rotate so its long axis points radially
        # outward in the wheel plane (YZ-plane, at angle a).
        bake_rotation_on_mesh(sp, (math.pi / 2 - a, 0, 0))
        parts.append(sp)
        # Handle sticks out along ±X at the outer rim.
        hx = wheel_x
        hy = wheel_y + math.cos(a) * rim_r
        hz = wheel_z + math.sin(a) * rim_r
        bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=0.05, vertices=10,
                                            location=(hx, hy, hz))
        handle = bpy.context.active_object; handle.name = f"_WheelHandle{i}"
        bake_rotation_on_mesh(handle, (0, math.pi / 2, 0))
        parts.append(handle)
    # Mounting post down to the poop deck.
    post_h = (wheel_y - rim_r - 0.01) - 0.80
    bpy.ops.mesh.primitive_cylinder_add(radius=0.020, depth=max(post_h, 0.02), vertices=12,
                                        location=(0.0, 0.80 + max(post_h, 0.02) / 2, wheel_z))
    post = bpy.context.active_object; post.name = "_WheelPost"
    parts.append(post)
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    w = bpy.context.active_object
    w.name = "ShipsWheel"
    w.data.materials.clear()
    w.data.materials.append(mat_wood)
    bpy.ops.object.shade_smooth()
    return w

extras += [make_ships_wheel()]

# --- Crow's nest (ring platform + wall, high up on MastMain) -----------------
def make_crows_nest(mast_z=-0.25, y_nest=2.05, outer_r=0.14, inner_r=0.05,
                    floor_thickness=0.02, wall_h=0.08):
    """Bmesh-built annular floor (so the mast pokes through) plus an open-top
    cylindrical wall above it."""
    parts = []
    mesh = bpy.data.meshes.new("CrowsNestFloor")
    floor = bpy.data.objects.new("_CrowsNestFloor", mesh)
    bpy.context.collection.objects.link(floor)
    bm = bmesh.new()
    segs = 24
    top_o = []; bot_o = []; top_i = []; bot_i = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        cx, cz = math.cos(a), math.sin(a)
        top_o.append(bm.verts.new((cx * outer_r,  floor_thickness / 2, cz * outer_r)))
        bot_o.append(bm.verts.new((cx * outer_r, -floor_thickness / 2, cz * outer_r)))
        top_i.append(bm.verts.new((cx * inner_r,  floor_thickness / 2, cz * inner_r)))
        bot_i.append(bm.verts.new((cx * inner_r, -floor_thickness / 2, cz * inner_r)))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new([top_o[i], top_o[j], top_i[j], top_i[i]])  # top annulus
        bm.faces.new([bot_o[j], bot_o[i], bot_i[i], bot_i[j]])  # bottom
        bm.faces.new([bot_o[i], bot_o[j], top_o[j], top_o[i]])  # outer wall
        bm.faces.new([bot_i[j], bot_i[i], top_i[i], top_i[j]])  # inner wall
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    floor.location = (0.0, y_nest, mast_z)
    parts.append(floor)
    bpy.ops.mesh.primitive_cylinder_add(radius=outer_r, depth=wall_h, vertices=24,
                                        location=(0.0, y_nest + wall_h / 2 + floor_thickness / 2, mast_z),
                                        end_fill_type='NOTHING')
    wall = bpy.context.active_object; wall.name = "_CrowsNestWall"
    parts.append(wall)
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    n = bpy.context.active_object
    n.name = "CrowsNest"
    n.data.materials.clear()
    n.data.materials.append(mat_wood)
    bpy.ops.object.shade_smooth()
    return n

extras += [make_crows_nest()]

# --- Yardarms (horizontal spars on masts, at the top of each sail) -----------
def make_yardarm(name, mast_z, y_height, length=0.70):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.020, depth=length, vertices=12,
                                        location=(0.0, y_height, mast_z))
    y = bpy.context.active_object
    y.name = name
    # Default cylinder along Z; rotate to align with +X (port-starboard).
    bake_rotation_on_mesh(y, (0, math.pi / 2, 0))
    bpy.ops.object.shade_smooth()
    y.data.materials.append(mat_wood)
    return y

yard_fore = make_yardarm("YardFore", mast_z=+0.45, y_height=1.70, length=0.72)
yard_main = make_yardarm("YardMain", mast_z=-0.25, y_height=2.07, length=0.88)
extras += [yard_fore, yard_main]

# --- Bowsprit + triangular jib sail ------------------------------------------
def make_bowsprit():
    """Angled spar projecting forward and up from the bow. Tilted ~20° above
    horizontal via R_x, so its +Z end points skyward."""
    length = 0.55
    bpy.ops.mesh.primitive_cylinder_add(radius=0.022, depth=length, vertices=12,
                                        location=(0.0, 0.78, 1.28))
    b = bpy.context.active_object
    b.name = "Bowsprit"
    # Cylinder long axis starts along Z; rotating by -20° about X tilts the +Z
    # end UP toward +Y (forward+up) without touching X.
    bake_rotation_on_mesh(b, (-math.radians(20), 0, 0))
    b.data.materials.append(mat_wood)
    bpy.ops.object.shade_smooth()
    return b

bowsprit = make_bowsprit()
extras += [bowsprit]

def make_jib():
    """Simple triangular sail between bowsprit tip, bowsprit base, and MastFore top.
    Flat plane in the YZ-plane (normal ±X). Uses mat_sail — deep crimson."""
    mesh = bpy.data.meshes.new("JibMesh")
    obj = bpy.data.objects.new("Jib", mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    tip   = (0, 0.78 + math.sin(math.radians(20)) * 0.275, 1.28 + math.cos(math.radians(20)) * 0.275)
    base  = (0, 0.78, 1.03)
    mtop  = (0, 1.80, 0.50)
    for p in (tip, base, mtop):
        bm.verts.new(p)
    bm.faces.new(list(bm.verts))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    obj.data.materials.append(mat_sail)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    return obj

extras += [make_jib()]

# --- Rudder (flat plank hanging off the stern transom) -----------------------
def make_rudder():
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, -0.08, -1.20))
    r = bpy.context.active_object
    r.name = "Rudder"
    r.scale = (0.04, 0.32, 0.14)
    bpy.ops.object.transform_apply(scale=True)
    select_only(r)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bevel(offset=0.008, segments=1)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.shade_smooth()
    r.data.materials.append(mat_wood)
    return r

extras += [make_rudder()]

# --- Deck railings (gunwale-top rails, with a gap at midship for gunports) ---
def make_railing_segment(name, x_side, z_start, z_end, y_top=0.65, post_every=0.18):
    """Top rail bar + posts at regular intervals; one pair per side, fore and aft
    of the gunports. Leaves the midship region clear so the cannons aren't boxed in."""
    parts = []
    mid_z = (z_start + z_end) * 0.5
    length_z = abs(z_end - z_start)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x_side, y_top, mid_z))
    top = bpy.context.active_object; top.name = f"{name}_TopRail"
    top.scale = (0.022, 0.022, length_z)
    bpy.ops.object.transform_apply(scale=True)
    parts.append(top)
    n_posts = max(2, int(length_z / post_every))
    for i in range(n_posts + 1):
        t = i / max(1, n_posts)
        zp = z_start + (z_end - z_start) * t
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x_side, 0.57, zp))
        post = bpy.context.active_object; post.name = f"{name}_Post{i}"
        post.scale = (0.022, 0.16, 0.022)
        bpy.ops.object.transform_apply(scale=True)
        parts.append(post)
    for p in parts:
        p.data.materials.append(mat_wood)
    return parts

extras += make_railing_segment("Rail_L_Fore", x_side=-0.40, z_start=0.15, z_end=0.50)
extras += make_railing_segment("Rail_R_Fore", x_side=+0.40, z_start=0.15, z_end=0.50)
extras += make_railing_segment("Rail_L_Aft",  x_side=-0.40, z_start=-0.50, z_end=-0.15)
extras += make_railing_segment("Rail_R_Aft",  x_side=+0.40, z_start=-0.50, z_end=-0.15)

# --- Hull damage: missing planks (boolean-cut holes with dark backing) -------
# Each damage position becomes a real plank-shaped HOLE in the hull mesh via a
# boolean DIFFERENCE modifier against a hidden cutter cube. A slightly smaller,
# very-dark backing plate sits just inside the hull surface behind each hole so
# the viewer sees "weathered recess" rather than "empty transparency".
mat_wood_dark = make_material("BoatWoodDark", (0.04, 0.025, 0.02, 1.0), 0.0, 0.05)

def cut_damage_hole(name, side_sign, y_center, z_center, size_y, size_z):
    """Cut a plank-shaped hole through the hull at the given hull-side position
    and return the dark backing plate that fills the recess behind it.

    side_sign: -1 for port, +1 for starboard. The actual hull X at (y_center,
    z_center) is sampled so the cutter and backing sit at the correct depth even
    where the hull tapers (bow/stern)."""
    hw = hull_half_width_at(y_center, z_center)
    # Cutter sits straddling the hull surface so it punches cleanly through both
    # inner and outer hull faces. Centre it ON the hull surface.
    cutter_x = hw * side_sign

    # 1. Cutter: axis-aligned box punching through the hull. X-thickness 0.14 is
    # larger than the hull wall so the cut goes all the way through.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cutter_x, y_center, z_center))
    cutter = bpy.context.active_object
    cutter.name = f"_Cutter_{name}"
    cutter.scale = (0.14, size_y, size_z)
    bpy.ops.object.transform_apply(scale=True)

    # 2. Attach boolean modifier to the hull and apply immediately. EXACT solver
    # is slower than FAST but handles the hull's subdivided-quad topology cleanly.
    mod = hull.modifiers.new(name=f"Cut_{name}", type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    mod.solver = 'EXACT'
    select_only(hull)
    bpy.ops.object.modifier_apply(modifier=f"Cut_{name}")

    # 3. Remove the cutter itself — it's not a visible part of the boat.
    bpy.data.objects.remove(cutter, do_unlink=True)

    # 4. Backing plate: slightly smaller than the hole so its edges don't poke
    # through the hull, set back 0.025 from the hull surface (INWARD) to read
    # as a proper recess rather than a protruding rectangle.
    backing_x = (hw - 0.025) * side_sign
    bpy.ops.mesh.primitive_cube_add(size=1, location=(backing_x, y_center, z_center))
    back = bpy.context.active_object
    back.name = f"Damage_Recess_{name}"
    back.scale = (0.015, size_y * 0.92, size_z * 0.92)
    bpy.ops.object.transform_apply(scale=True)
    back.data.materials.append(mat_wood_dark)
    return back

# 4 missing-plank holes at varied positions + sizes for a weathered look.
# side_sign picks port (-1) / starboard (+1); the X position is sampled from the
# actual hull contour so holes sit flush even near the tapered bow/stern.
extras += [
    cut_damage_hole("L1", -1, y_center=0.22, z_center=-0.35, size_y=0.09, size_z=0.26),
    cut_damage_hole("L2", -1, y_center=0.12, z_center=+0.15, size_y=0.06, size_z=0.18),
    cut_damage_hole("R1", +1, y_center=0.24, z_center=-0.20, size_y=0.07, size_z=0.22),
    cut_damage_hole("R2", +1, y_center=0.18, z_center=+0.60, size_y=0.05, size_z=0.16),
]

# --- Figurehead (skull at the prow) ------------------------------------------
def make_figurehead_skull():
    """Cranium UV sphere + a blocky jaw wedge (bone material), plus two small
    dark spheres embedded as eye sockets (iron material). Positioned forward of
    and just below the cutwater tip so it reads as a carved prow decoration."""
    x_c, y_c, z_c = 0.0, 0.45, 1.18
    # Cranium
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07, segments=16, ring_count=10,
                                         location=(x_c, y_c, z_c))
    cranium = bpy.context.active_object; cranium.name = "_Skull_Cranium"
    # Jaw
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x_c, y_c - 0.055, z_c + 0.025))
    jaw = bpy.context.active_object; jaw.name = "_Skull_Jaw"
    jaw.scale = (0.10, 0.035, 0.08)
    bpy.ops.object.transform_apply(scale=True)
    # Eye-socket spheres (iron)
    eye_objs = []
    for dx, label in ((-0.025, "L"), (+0.025, "R")):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, segments=10, ring_count=5,
                                             location=(x_c + dx, y_c + 0.01, z_c + 0.055))
        eye = bpy.context.active_object; eye.name = f"_Skull_Eye{label}"
        eye_objs.append(eye)
    # Join bone parts (cranium + jaw)
    bpy.ops.object.select_all(action='DESELECT')
    cranium.select_set(True); jaw.select_set(True)
    bpy.context.view_layer.objects.active = cranium
    bpy.ops.object.join()
    skull = bpy.context.active_object
    skull.name = "Figurehead_Skull"
    skull.data.materials.clear()
    skull.data.materials.append(mat_bone)
    bpy.ops.object.shade_smooth()
    # Join eye spheres (iron)
    bpy.ops.object.select_all(action='DESELECT')
    for e in eye_objs:
        e.select_set(True)
    bpy.context.view_layer.objects.active = eye_objs[0]
    bpy.ops.object.join()
    eyes = bpy.context.active_object
    eyes.name = "Figurehead_SkullEyes"
    eyes.data.materials.clear()
    eyes.data.materials.append(mat_iron)
    return skull, eyes

skull, skull_eyes = make_figurehead_skull()
extras += [skull, skull_eyes]

# --- Ship's bell (small belfry aft of the wheel) -----------------------------
def make_bell():
    """A short vertical post + a truncated-cone bell hanging from it."""
    bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=0.14, vertices=10,
                                        location=(0.0, 0.87, -0.40))
    post = bpy.context.active_object; post.name = "_BellPost"
    bpy.ops.mesh.primitive_cone_add(radius1=0.045, radius2=0.025, depth=0.06,
                                    vertices=14, location=(0.0, 0.80, -0.40))
    bell = bpy.context.active_object; bell.name = "_Bell"
    bpy.ops.object.select_all(action='DESELECT')
    post.select_set(True); bell.select_set(True)
    bpy.context.view_layer.objects.active = post
    bpy.ops.object.join()
    b = bpy.context.active_object
    b.name = "ShipsBell"
    b.data.materials.clear()
    b.data.materials.append(mat_iron)
    bpy.ops.object.shade_smooth()
    return b

extras += [make_bell()]

# --- Stern lantern (emissive box on top of the poop rail) --------------------
def make_stern_lantern():
    """Glowing lantern body + iron cap, at the aft-centre of the poop deck."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, 0.92, -1.02))
    body = bpy.context.active_object; body.name = "_LanternBody"
    body.scale = (0.07, 0.10, 0.07)
    bpy.ops.object.transform_apply(scale=True)
    body.data.materials.append(mat_glow)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, 0.99, -1.02))
    cap = bpy.context.active_object; cap.name = "_LanternCap"
    cap.scale = (0.09, 0.015, 0.09)
    bpy.ops.object.transform_apply(scale=True)
    cap.data.materials.append(mat_iron)
    return [body, cap]

extras += make_stern_lantern()

# --- Iron chain trim at the waterline ---------------------------------------
# Follows the hull contour at y≈0 (waterline) — not a straight box. Same segment
# sampling as the strakes so the trim hugs the hull all the way fore and aft.
def make_contour_chain_trim(length_half=0.95, y=0.0, z_samples=48):
    out_parts = {"L": [], "R": []}
    step = (2.0 * length_half) / z_samples
    for i in range(z_samples):
        z_mid = -length_half + (i + 0.5) * step
        hw = hull_half_width_at(y, z_mid)
        if hw < 0.02:
            continue
        for side_tag, side_sign in (("L", -1.0), ("R", +1.0)):
            x_mid = (hw + 0.001) * side_sign
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x_mid, y, z_mid))
            c = bpy.context.active_object
            c.name = f"ChainTrim_{side_tag}_Seg{i}"
            c.scale = (0.012, 0.012, step * 1.02)
            bpy.ops.object.transform_apply(scale=True)
            c.data.materials.append(mat_iron)
            out_parts[side_tag].append(c)
    joined = []
    for side_tag in ("L", "R"):
        parts = out_parts[side_tag]
        if not parts:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        for p in parts:
            p.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.join()
        j = bpy.context.active_object
        j.name = f"ChainTrim_{side_tag}"
        bpy.ops.object.shade_smooth()
        joined.append(j)
    return joined

extras += make_contour_chain_trim()

# -- Turret empty + parenting -------------------------------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
turret = bpy.context.active_object
turret.name = "Turret"

# Top-level "Boat" empty
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
boat_root = bpy.context.active_object
boat_root.name = "Boat"

# Parent every visible part under Turret (which sits under Boat). Strakes and
# `extras` are each lists of multiple pieces (superstructure + decor), flattened
# into the parent loop.
hull_parts = [hull] + strakes + [gunport_l, gunport_r, mast_fore, mast_main,
                                 sail_fore, sail_main, flag, cannon_l, cannon_r] + extras
for child in hull_parts:
    child.parent = turret
turret.parent = boat_root

# Sail/Flag armatures need to live under Turret too so they yaw with the boat
for arm_name in ["SailFore_Armature", "SailMain_Armature", "Flag_Armature"]:
    bpy.data.objects[arm_name].parent = turret

# -- Save and export ----------------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=BLEND_DST)
print(f"Saved: {BLEND_DST}")

# Select everything for export (the FBX exporter ignores `use_selection=False` for armatures sometimes)
for o in bpy.data.objects:
    o.select_set(True)

bpy.ops.export_scene.fbx(
    filepath=FBX_PATH,
    use_selection=False,
    object_types={'MESH', 'ARMATURE', 'EMPTY'},
    bake_anim=False,
    add_leaf_bones=False,
    axis_forward='-Z',
    axis_up='Y',
    global_scale=1.0,
    bake_space_transform=True,
    apply_scale_options='FBX_SCALE_ALL',
)
print(f"Exported boat000: {FBX_PATH}")
print("Done!")
