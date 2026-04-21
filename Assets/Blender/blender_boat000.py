import bpy
import bmesh
import math
from mathutils import Vector

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
# The hull is built by lofting between cross-section ribs along the +X (bow) axis.
# Each rib has 5 vertices forming a shallow U: keel (bottom centre), chine port +
# starboard (widest point under water), rail port + starboard (top edge of hull).
#
# Shaping rules embedded in the section table:
#   * Sheer   — deck_y rises at bow and stern (hull is taller at the ends).
#   * Bow     — final rib collapses to a point at Z=0, producing a vertical cutwater.
#   * Stern   — first rib has finite width; a pentagon cap closes the transom.
#   * Keel    — chine_width narrows toward the ends so the underwater body tapers
#               in as well as the deck line.
#
# Row format: (x, keel_y, deck_y, half_width_keel, half_width_deck)
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

    # Build one rib of 5 verts per section. Rib layout (left-to-right when viewed
    # from above, +Z starboard): keel, chine_port, rail_port, rail_stbd, chine_stbd.
    ribs = []
    for (x, ky, dy, hw_k, hw_d) in _SECTIONS:
        keel = bm.verts.new((x, ky, 0.0))
        cp   = bm.verts.new((x, ky, -hw_k))
        rp   = bm.verts.new((x, dy, -hw_d))
        rs   = bm.verts.new((x, dy,  hw_d))
        cs   = bm.verts.new((x, ky,  hw_k))
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

# -- Strakes (horizontal planks running the length of the hull) ---------------
# Two reinforcing planks per side — a waterline strake low on the hull and a
# heavier "wale" just below deck. Implemented as thin tapered boxes rather than
# true hull-conforming strips; at the TD camera distance they read as planking.
def make_strake(name, y, half_width, length_half, thickness=0.020, height=0.035):
    out = []
    for side, z in (("L", -half_width), ("R", +half_width)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, y, z))
        s = bpy.context.active_object
        s.name = f"{name}_{side}"
        s.scale = (length_half, height, thickness)
        bpy.ops.object.transform_apply(scale=True)
        # Light bevel so the plank edge catches light, but skip subsurf — we want
        # the silhouette of a distinct plank, not a rounded cushion.
        select_only(s)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.bevel(offset=0.006, segments=1)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.shade_smooth()
        s.data.materials.append(mat_wood)
        out.append(s)
    return out

# Waterline strake sits just above the waterline at y=0.05. Main wale rides
# higher at y=0.34, just under deck level. Both are 0.43 out from centerline so
# they sit flush with the midship hull edge (hw_deck=0.42) and pop a tiny bit
# proud of the hull everywhere else — reads as a proud plank edge.
strakes  = make_strake("Waterline", y=0.05, half_width=0.43, length_half=0.92)
strakes += make_strake("MainWale",  y=0.34, half_width=0.435, length_half=1.00)

# -- Gunport frames (iron trim around the cannon openings in the hull) --------
# Small iron-material squares bolted to the hull side, framing each cannon as it
# passes through. They sit a hair outside the hull (Z=+/-0.44 vs hull 0.42) so
# they visibly frame the opening rather than clipping inside the planks.
def make_gunport(name, z_side):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, 0.44, 0.44 * z_side))
    g = bpy.context.active_object
    g.name = name
    # Wider and taller than the cannon barrel (0.12 dia) so the frame is visible
    # around the cannon; thin along Z (into the hull) so it reads as surface trim.
    g.scale = (0.18, 0.18, 0.025)
    bpy.ops.object.transform_apply(scale=True)
    bevel_subsurf(g, bevel_offset=0.012, bevel_segs=1, subsurf_levels=1)
    g.data.materials.append(mat_iron)
    return g

gunport_l = make_gunport("GunportFrame_L", -1)
gunport_r = make_gunport("GunportFrame_R", +1)

# -- Masts ---------------------------------------------------------------------
def make_mast(name, x, height):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=height, location=(x, 0.5 + height/2, 0))
    m = bpy.context.active_object
    m.name = name
    bevel_subsurf(m, bevel_offset=0.01, bevel_segs=1, subsurf_levels=1)
    m.data.materials.append(mat_wood)
    return m

mast_fore = make_mast("MastFore", 0.45, 1.4)
mast_main = make_mast("MastMain", -0.25, 1.7)

# -- Sails (skinned mesh + Ripple shape key) ----------------------------------
def make_sail(name, mast_obj, width, height, y_offset, amplitude=0.10, wavelength=0.7):
    # Build flat in XY plane at origin; normal is +Z
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    sail = bpy.context.active_object
    sail.name = name
    sail.scale = (width, height, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    # Subdivide for shape-key resolution
    select_only(sail)
    bpy.ops.object.mode_set(mode='EDIT')
    for _ in range(3):
        bpy.ops.mesh.subdivide()
    bpy.ops.object.mode_set(mode='OBJECT')
    # Shape keys BEFORE rotation (so wave is in plane-normal direction)
    add_ripple_shapekeys(sail, amplitude=amplitude, wavelength=wavelength)
    # Rotate so the plane is vertical (normal becomes -Y, billowing toward viewer)
    sail.rotation_euler = (math.pi/2, 0, 0)
    bpy.ops.object.transform_apply(rotation=True)
    # Position on mast
    sail.location = (mast_obj.location.x, mast_obj.location.y + y_offset, 0)
    sail.data.materials.append(mat_sail)
    bpy.ops.object.shade_smooth()
    # Dummy armature so Unity imports as SkinnedMeshRenderer
    add_dummy_armature(name + "_Armature", sail)
    return sail

# Amplitude bumped from 0.04 to 0.10: at the old value the sail ripple was ~4cm on a
# 60-100cm sail, which read as "static" in play. 10cm is visibly billowing without
# looking like the sail is deflating.
sail_fore = make_sail("SailFore", mast_fore, width=0.6, height=1.0, y_offset=0.0, amplitude=0.10, wavelength=0.7)
sail_main = make_sail("SailMain", mast_main, width=0.75, height=1.2, y_offset=0.1, amplitude=0.10, wavelength=0.7)

# -- Flag (skinned mesh + Ripple shape key, anchored at -X edge) --------------
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
flag.rotation_euler = (math.pi/2, 0, 0)
bpy.ops.object.transform_apply(rotation=True)
# Place at top of MastMain, offset so the -X edge is at the mast
flag.location = (mast_main.location.x + 0.13, mast_main.location.y + 0.85, 0)
flag.data.materials.append(mat_sail)
bpy.ops.object.shade_smooth()
add_dummy_armature("Flag_Armature", flag)

# -- Cannons (rigid, fixed angles) --------------------------------------------
# Default cylinder has its long axis along +Z. The boat's lateral axis is also +Z
# (cube hull was scaled along X/Y/Z = length/height/width). So no rotation needed --
# cannons are placed at z = +/-0.42 with their barrels naturally pointing +/-Z.
def make_cannon(name, port_side):
    """port_side: -1 for port (negative Z), +1 for starboard"""
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.35, location=(0.0, 0.45, 0.42 * port_side))
    c = bpy.context.active_object
    c.name = name
    bevel_subsurf(c, bevel_offset=0.015, bevel_segs=1, subsurf_levels=1)
    c.data.materials.append(mat_iron)
    return c

cannon_l = make_cannon("CannonPort_L", port_side=-1)  # port
cannon_r = make_cannon("CannonPort_R", port_side=+1)  # starboard

# -- Turret empty + parenting -------------------------------------------------
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
turret = bpy.context.active_object
turret.name = "Turret"

# Top-level "Boat" empty
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
boat_root = bpy.context.active_object
boat_root.name = "Boat"

# Parent every visible part under Turret (which sits under Boat). Strakes are a
# list of 4 thin boxes (Waterline_L/R + MainWale_L/R) — flattened into the loop.
hull_parts = [hull] + strakes + [gunport_l, gunport_r, mast_fore, mast_main,
                                 sail_fore, sail_main, flag, cannon_l, cannon_r]
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
