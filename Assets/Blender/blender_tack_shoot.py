import bpy
import math
from mathutils import Vector

# ── Paths ─────────────────────────────────────────────────────────────────────
BLEND_PATH = r"C:\Users\LachlanB\TD\Assets\Blender\tack000.blend"
SHOOT_FBX  = r"C:\Users\LachlanB\TD\Assets\Models\tack_shoot.fbx"
DISK_FBX   = r"C:\Users\LachlanB\TD\Assets\Models\wood_disk.fbx"

NUM_DISKS   = 8
ANIM_FRAMES = 12
FPS         = 24

# ── Open tack shooter model ──────────────────────────────────────────────────
bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)

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

# ── Sizing ────────────────────────────────────────────────────────────────────
DISK_RADIUS    = max(tower_radius * 0.22, 0.06)
DISK_THICKNESS = DISK_RADIUS * 0.35
FLY_DISTANCE   = tower_radius * 6
CENTER_Z       = center.z

# ── Remove old disks if re-running ────────────────────────────────────────────
for obj in list(bpy.data.objects):
    if obj.name.startswith("Disk_"):
        bpy.data.objects.remove(obj, do_unlink=True)

# ── Wood material ─────────────────────────────────────────────────────────────
wood_mat = bpy.data.materials.get("WoodDisk")
if wood_mat is None:
    wood_mat = bpy.data.materials.new(name="WoodDisk")
    wood_mat.use_nodes = True
bsdf = wood_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.76, 0.60, 0.42, 1.0)
bsdf.inputs["Roughness"].default_value = 0.8

# ── Create & animate 8 wooden disks ──────────────────────────────────────────
disks = []
for i in range(NUM_DISKS):
    angle = i * (2 * math.pi / NUM_DISKS)

    bpy.ops.mesh.primitive_cylinder_add(
        radius=DISK_RADIUS, depth=DISK_THICKNESS,
        location=(center.x, center.y, CENTER_Z))
    disk = bpy.context.active_object
    disk.name = f"Disk_{i:02d}"

    # Orient so flat face points in fly direction
    disk.rotation_euler = (math.pi / 2, 0, angle)
    bpy.ops.object.transform_apply(rotation=True)

    disk.data.materials.clear()
    disk.data.materials.append(wood_mat)

    # End position
    ex = center.x + math.cos(angle) * FLY_DISTANCE
    ey = center.y + math.sin(angle) * FLY_DISTANCE

    # Frame 0: hidden at center (scale ~0)
    disk.location = (center.x, center.y, CENTER_Z)
    disk.scale = (0.01, 0.01, 0.01)
    disk.keyframe_insert(data_path="location", frame=0)
    disk.keyframe_insert(data_path="scale",    frame=0)

    # Frame 1: appear at full scale
    disk.scale = (1, 1, 1)
    disk.keyframe_insert(data_path="location", frame=1)
    disk.keyframe_insert(data_path="scale",    frame=1)

    # Frame 10: at destination
    disk.location = (ex, ey, CENTER_Z)
    disk.keyframe_insert(data_path="location", frame=ANIM_FRAMES - 2)

    # Frame 12: shrink and vanish
    disk.scale = (0.01, 0.01, 0.01)
    disk.keyframe_insert(data_path="scale", frame=ANIM_FRAMES)

    if disk.animation_data and disk.animation_data.action:
        disk.animation_data.action.name = f"TackShoot_{i:02d}"

    disks.append(disk)

# ── Linear interpolation for snappy movement ─────────────────────────────────
for disk in disks:
    if disk.animation_data and disk.animation_data.action:
        for fc in disk.animation_data.action.fcurves:
            for kf in fc.keyframe_points:
                kf.interpolation = 'LINEAR'

# ── Scene frame range ─────────────────────────────────────────────────────────
bpy.context.scene.frame_start = 0
bpy.context.scene.frame_end   = ANIM_FRAMES
bpy.context.scene.render.fps  = FPS

# ── Save blend file ──────────────────────────────────────────────────────────
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
print(f"Saved: {BLEND_PATH}")

# ── Export tower + disks + animation ──────────────────────────────────────────
bpy.ops.export_scene.fbx(
    filepath=SHOOT_FBX,
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
print(f"Exported tower+animation: {SHOOT_FBX}")

# ── Export single disk for projectile ─────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
d0 = bpy.data.objects.get("Disk_00")
if d0:
    d0.select_set(True)
    bpy.context.view_layer.objects.active = d0
    orig_loc = d0.location.copy()
    orig_scl = d0.scale.copy()
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
    print(f"Exported disk projectile: {DISK_FBX}")
    d0.location = orig_loc
    d0.scale    = orig_scl

print("Done!")
