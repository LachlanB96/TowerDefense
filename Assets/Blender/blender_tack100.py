import bpy
import math
from mathutils import Vector

# ── Paths ─────────────────────────────────────────────────────────────────────
BLEND_SRC = r"C:\Users\LachlanB\TD\Assets\Blender\tack000.blend"
BLEND_DST = r"C:\Users\LachlanB\TD\Assets\Blender\tack100.blend"
FBX_PATH  = r"C:\Users\LachlanB\TD\Assets\Models\tack100.fbx"
DISK_FBX  = r"C:\Users\LachlanB\TD\Assets\Models\red_disk.fbx"

NUM_DISKS   = 8
ANIM_FRAMES = 12
FPS         = 24

# ── Open tack000 as base ─────────────────────────────────────────────────────
bpy.ops.wm.open_mainfile(filepath=BLEND_SRC)

# ── Remove old disk objects and animation data ───────────────────────────────
for obj in list(bpy.data.objects):
    if obj.name.startswith("Disk_"):
        bpy.data.objects.remove(obj, do_unlink=True)

for obj in bpy.data.objects:
    if obj.animation_data:
        obj.animation_data_clear()

# ── Calculate tower bounds ────────────────────────────────────────────────────
mesh_objects = [o for o in bpy.data.objects if o.type == 'MESH']
min_co = Vector((1e9, 1e9, 1e9))
max_co = Vector((-1e9, -1e9, -1e9))
for obj in mesh_objects:
    for corner in obj.bound_box:
        wc = obj.matrix_world @ Vector(corner)
        min_co = Vector([min(min_co[i], wc[i]) for i in range(3)])
        max_co = Vector([max(max_co[i], wc[i]) for i in range(3)])

center = (min_co + max_co) / 2
tower_radius = max(max_co.x - min_co.x, max_co.y - min_co.y) / 2
print(f"Tower center={center[:]}  radius={tower_radius:.4f}")

# Find TopCap surface Z for flame placement
top_cap = bpy.data.objects.get("TopCap")
if top_cap:
    top_z = max(v.co.z for v in top_cap.data.vertices)
else:
    top_z = max_co.z
print(f"TopCap surface Z = {top_z:.4f}")

# ══════════════════════════════════════════════════════════════════════════════
#  NEW MATERIALS
# ══════════════════════════════════════════════════════════════════════════════

# RedMetal — replaces the gray Metal bands
red_metal = bpy.data.materials.new(name="RedMetal")
red_metal.use_nodes = True
bsdf = red_metal.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.80, 0.08, 0.04, 1.0)
bsdf.inputs["Metallic"].default_value = 0.95
bsdf.inputs["Roughness"].default_value = 0.25

# RedTack — replaces the silver Tack material on heads/shafts/tips
red_tack = bpy.data.materials.new(name="RedTack")
red_tack.use_nodes = True
bsdf = red_tack.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.72, 0.12, 0.08, 1.0)
bsdf.inputs["Metallic"].default_value = 1.0
bsdf.inputs["Roughness"].default_value = 0.20

# RedDisk — projectile material (red metallic disks)
red_disk_mat = bpy.data.materials.new(name="RedDisk")
red_disk_mat.use_nodes = True
bsdf = red_disk_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.85, 0.10, 0.06, 1.0)
bsdf.inputs["Metallic"].default_value = 0.95
bsdf.inputs["Roughness"].default_value = 0.20

# FlameSymbol — emissive orange for the flame emblem
flame_mat = bpy.data.materials.new(name="FlameSymbol")
flame_mat.use_nodes = True
bsdf = flame_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (1.0, 0.35, 0.0, 1.0)
bsdf.inputs["Emission Color"].default_value = (1.0, 0.25, 0.0, 1.0)
bsdf.inputs["Emission Strength"].default_value = 3.0
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Roughness"].default_value = 0.40

# ══════════════════════════════════════════════════════════════════════════════
#  SWAP MATERIALS ON EXISTING TOWER PARTS
# ══════════════════════════════════════════════════════════════════════════════
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    for slot in obj.material_slots:
        if slot.material is None:
            continue
        if slot.material.name == "Metal":
            slot.material = red_metal
        elif slot.material.name == "Tack":
            slot.material = red_tack

# ══════════════════════════════════════════════════════════════════════════════
#  CREATE FLAME SYMBOL ON TOP
# ══════════════════════════════════════════════════════════════════════════════
# Convex flame / teardrop outline (X, Z in local space)
flame_raw = [
    ( 0.00, -0.02),
    ( 0.14,  0.02),
    ( 0.19,  0.10),
    ( 0.17,  0.18),
    ( 0.13,  0.25),
    ( 0.07,  0.34),
    ( 0.00,  0.44),     # tip
    (-0.07,  0.34),
    (-0.13,  0.25),
    (-0.17,  0.18),
    (-0.19,  0.10),
    (-0.14,  0.02),
]

flame_height_target = tower_radius * 0.40
flame_raw_height = 0.46  # 0.44 - (-0.02)
flame_scale = flame_height_target / flame_raw_height
flame_thickness = 0.05 * flame_scale

def make_flame(name, rotation_z=0.0):
    """Create a solidified flame mesh object."""
    verts = [(x * flame_scale, 0.0, z * flame_scale) for x, z in flame_raw]
    faces = [list(range(len(verts)))]

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (0, 0, top_z)
    obj.rotation_euler = (0, 0, rotation_z)

    # Select and activate for modifier ops
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Solidify for 3D thickness
    mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod.thickness = flame_thickness
    mod.offset = 0  # centered
    bpy.ops.object.modifier_apply(modifier="Solidify")

    # Smooth shading
    bpy.ops.object.shade_smooth()

    obj.data.materials.append(flame_mat)
    return obj

# Two perpendicular flames so the symbol is visible from any angle
flame_a = make_flame("FlameSymbol_A", rotation_z=0.0)
flame_b = make_flame("FlameSymbol_B", rotation_z=math.pi / 2)

print(f"Flame placed at Z={top_z:.4f}, height={flame_height_target:.4f}")

# ══════════════════════════════════════════════════════════════════════════════
#  ANIMATED RED DISKS (shoot animation)
# ══════════════════════════════════════════════════════════════════════════════
DISK_RADIUS    = max(tower_radius * 0.22, 0.06)
DISK_THICKNESS = DISK_RADIUS * 0.35
FLY_DISTANCE   = tower_radius * 6
CENTER_Z       = center.z

disks = []
for i in range(NUM_DISKS):
    angle = i * (2 * math.pi / NUM_DISKS)

    bpy.ops.mesh.primitive_cylinder_add(
        radius=DISK_RADIUS, depth=DISK_THICKNESS,
        location=(center.x, center.y, CENTER_Z))
    disk = bpy.context.active_object
    disk.name = f"Disk_{i:02d}"

    disk.rotation_euler = (math.pi / 2, 0, angle)
    bpy.ops.object.transform_apply(rotation=True)

    disk.data.materials.clear()
    disk.data.materials.append(red_disk_mat)

    ex = center.x + math.cos(angle) * FLY_DISTANCE
    ey = center.y + math.sin(angle) * FLY_DISTANCE

    # Frame 0: hidden at center
    disk.location = (center.x, center.y, CENTER_Z)
    disk.scale = (0.01, 0.01, 0.01)
    disk.keyframe_insert(data_path="location", frame=0)
    disk.keyframe_insert(data_path="scale",    frame=0)

    # Frame 1: appear
    disk.scale = (1, 1, 1)
    disk.keyframe_insert(data_path="location", frame=1)
    disk.keyframe_insert(data_path="scale",    frame=1)

    # Frame 10: at destination
    disk.location = (ex, ey, CENTER_Z)
    disk.keyframe_insert(data_path="location", frame=ANIM_FRAMES - 2)

    # Frame 12: vanish
    disk.scale = (0.01, 0.01, 0.01)
    disk.keyframe_insert(data_path="scale", frame=ANIM_FRAMES)

    if disk.animation_data and disk.animation_data.action:
        disk.animation_data.action.name = f"Tack100Shoot_{i:02d}"
        for fc in disk.animation_data.action.fcurves:
            for kf in fc.keyframe_points:
                kf.interpolation = 'LINEAR'

    disks.append(disk)

# ── Scene settings ────────────────────────────────────────────────────────────
bpy.context.scene.frame_start = 0
bpy.context.scene.frame_end   = ANIM_FRAMES
bpy.context.scene.render.fps  = FPS

# ══════════════════════════════════════════════════════════════════════════════
#  SAVE & EXPORT
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.wm.save_as_mainfile(filepath=BLEND_DST)
print(f"Saved: {BLEND_DST}")

# Export full tower
bpy.ops.export_scene.fbx(
    filepath=FBX_PATH,
    use_selection=False,
    object_types={'ARMATURE', 'MESH'},
    bake_anim=True,
    bake_anim_use_all_actions=False,
    bake_anim_step=1,
    bake_anim_simplify_factor=0.0,
    add_leaf_bones=False,
    axis_forward='-Z',
    axis_up='Y',
    global_scale=1.0,
)
print(f"Exported tower: {FBX_PATH}")

# Export single red disk for projectile prefab
bpy.ops.object.select_all(action='DESELECT')
d0 = bpy.data.objects.get("Disk_00")
if d0:
    d0.select_set(True)
    bpy.context.view_layer.objects.active = d0
    ol, os = d0.location.copy(), d0.scale.copy()
    d0.location = (0, 0, 0)
    d0.scale    = (1, 1, 1)

    bpy.ops.export_scene.fbx(
        filepath=DISK_FBX,
        use_selection=True,
        object_types={'MESH'},
        bake_anim=False,
        add_leaf_bones=False,
        axis_forward='-Z',
        axis_up='Y',
        global_scale=1.0,
    )
    print(f"Exported red disk: {DISK_FBX}")
    d0.location = ol
    d0.scale    = os

print("Done!")
