import bpy
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

def add_ripple_shapekey(obj, amplitude, wavelength, weight_along_local_x=False):
    """Bake a sine wave into a shape key 'Ripple'.
    Wave phase travels along local Y; displacement is along local Z (the plane normal).
    If weight_along_local_x: weight = (x_norm) so the +X edge is anchored."""
    if not obj.data.shape_keys:
        obj.shape_key_add(name='Basis')
    sk = obj.shape_key_add(name='Ripple')
    xs = [v.co.x for v in obj.data.vertices]
    x_min, x_max = min(xs), max(xs)
    x_range = max(0.001, x_max - x_min)
    for i, v in enumerate(obj.data.vertices):
        phase = (v.co.y / wavelength) * 2.0 * math.pi
        disp = amplitude * math.sin(phase)
        if weight_along_local_x:
            # Anchor at -X edge (mast side); free at +X edge
            w = (v.co.x - x_min) / x_range
            disp *= w
        sk.data[i].co = v.co + Vector((0.0, 0.0, disp))

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

# -- Hull ----------------------------------------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.2, 0))
hull = bpy.context.active_object
hull.name = "Hull"
hull.scale = (1.1, 0.5, 0.45)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bevel_subsurf(hull, bevel_offset=0.18, bevel_segs=3, subsurf_levels=2)
hull.data.materials.append(mat_wood)

# -- DeckRail (thin band on top of hull) --------------------------------------
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.5, 0))
rail = bpy.context.active_object
rail.name = "DeckRail"
rail.scale = (1.05, 0.06, 0.42)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bevel_subsurf(rail, bevel_offset=0.03, bevel_segs=2, subsurf_levels=1)
rail.data.materials.append(mat_wood)

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
def make_sail(name, mast_obj, width, height, y_offset, amplitude=0.04, wavelength=0.7):
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
    # Shape key BEFORE rotation (so wave is in plane-normal direction)
    add_ripple_shapekey(sail, amplitude=amplitude, wavelength=wavelength)
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

sail_fore = make_sail("SailFore", mast_fore, width=0.6, height=1.0, y_offset=0.0, amplitude=0.04, wavelength=0.7)
sail_main = make_sail("SailMain", mast_main, width=0.75, height=1.2, y_offset=0.1, amplitude=0.04, wavelength=0.7)

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
add_ripple_shapekey(flag, amplitude=0.10, wavelength=0.4, weight_along_local_x=True)
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

# Parent every visible part under Turret (which sits under Boat)
for child in [hull, rail, mast_fore, mast_main, sail_fore, sail_main, flag, cannon_l, cannon_r]:
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
