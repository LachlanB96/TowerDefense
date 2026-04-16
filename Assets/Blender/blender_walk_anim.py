import bpy
import math

# ── Clean scene ──────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
for obj in bpy.data.objects:
    bpy.data.objects.remove(obj, do_unlink=True)

# ── Import GLB ────────────────────────────────────────────────────────────────
GLB_PATH = r"C:\Users\LachlanB\TD\Assets\Meshes\9_23_2025.glb"
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

# Find the mesh object
mesh_obj = None
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mesh_obj = obj
        break

if mesh_obj is None:
    raise RuntimeError("No mesh found in GLB")

print(f"Mesh: {mesh_obj.name}, bounds: {mesh_obj.dimensions}")

# Centre origin to geometry
bpy.ops.object.select_all(action='DESELECT')
mesh_obj.select_set(True)
bpy.context.view_layer.objects.active = mesh_obj
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

# Move to world origin
mesh_obj.location = (0, 0, 0)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

dims = mesh_obj.dimensions        # (W, D, H) – Z is up in Blender
W, D, H = dims.x, dims.y, dims.z
print(f"Dims W={W:.3f} D={D:.3f} H={H:.3f}")

# ── Build armature ────────────────────────────────────────────────────────────
bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
arm_obj = bpy.context.object
arm_obj.name = "DinoArmature"
arm = arm_obj.data
arm.name = "DinoArmature"

# Remove default bone
for b in arm.edit_bones:
    arm.edit_bones.remove(b)

def add_bone(name, head, tail, parent=None):
    b = arm.edit_bones.new(name)
    b.head = head
    b.tail = tail
    if parent:
        b.parent = arm.edit_bones[parent]
        b.use_connect = False
    return b

# Bone positions relative to mesh centre (which is at world origin after applying)
# The dinosaur stands with Z up in Blender, depth along Y
hip_z    = H * 0.30
spine_z  = H * 0.60
neck_z   = H * 0.78
head_z   = H * 1.00
foot_z   = 0.0
knee_z   = H * 0.18
hip_y    = D * 0.05   # slightly towards back

add_bone("Root",      (0,  0,       0),        (0,  0,       H*0.12))
add_bone("Hip",       (0,  hip_y,   hip_z),    (0,  hip_y,   spine_z),  "Root")
add_bone("Spine",     (0,  hip_y,   spine_z),  (0,  hip_y,   neck_z),   "Hip")
add_bone("Neck",      (0,  hip_y,   neck_z),   (0,  hip_y-D*0.1, head_z), "Spine")
add_bone("Head",      (0,  hip_y-D*0.1, head_z), (0, hip_y-D*0.2, H*1.15), "Neck")

leg_x = W * 0.25
add_bone("UpperLeg_L", ( leg_x, hip_y, hip_z),    ( leg_x, hip_y+D*0.1, knee_z), "Hip")
add_bone("LowerLeg_L", ( leg_x, hip_y+D*0.1, knee_z), ( leg_x, hip_y+D*0.05, foot_z), "UpperLeg_L")
add_bone("UpperLeg_R", (-leg_x, hip_y, hip_z),    (-leg_x, hip_y+D*0.1, knee_z), "Hip")
add_bone("LowerLeg_R", (-leg_x, hip_y+D*0.1, knee_z), (-leg_x, hip_y+D*0.05, foot_z), "UpperLeg_R")

arm_x = W * 0.40
arm_z = H * 0.65
add_bone("UpperArm_L", ( arm_x, hip_y, arm_z), ( arm_x+W*0.2, hip_y+D*0.15, arm_z-H*0.12), "Spine")
add_bone("UpperArm_R", (-arm_x, hip_y, arm_z), (-arm_x-W*0.2, hip_y+D*0.15, arm_z-H*0.12), "Spine")

# Tail
add_bone("Tail1", (0, hip_y+D*0.15, hip_z*0.8), (0, hip_y+D*0.40, hip_z*0.5), "Hip")
add_bone("Tail2", (0, hip_y+D*0.40, hip_z*0.5), (0, hip_y+D*0.65, hip_z*0.2), "Tail1")

bpy.ops.object.mode_set(mode='OBJECT')

# ── Parent mesh to armature with automatic weights ────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
mesh_obj.select_set(True)
arm_obj.select_set(True)
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.parent_set(type='ARMATURE_AUTO')

print("Auto-weight done")

# ── Walk cycle animation ───────────────────────────────────────────────────────
bpy.context.view_layer.objects.active = arm_obj
arm_obj.select_set(True)
bpy.ops.object.mode_set(mode='POSE')

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end   = 24
fps = 24
scene.render.fps  = fps

def pose_bone(bone_name):
    return arm_obj.pose.bones.get(bone_name)

def key_rot(bone_name, frame, x_deg=0, y_deg=0, z_deg=0):
    pb = pose_bone(bone_name)
    if pb is None:
        return
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (math.radians(x_deg), math.radians(y_deg), math.radians(z_deg))
    pb.keyframe_insert(data_path="rotation_euler", frame=frame)

def key_loc(bone_name, frame, x=0, y=0, z=0):
    pb = pose_bone(bone_name)
    if pb is None:
        return
    pb.location = (x, y, z)
    pb.keyframe_insert(data_path="location", frame=frame)

# ── Keyframes: 4 poses over 24-frame cycle ────────────────────────────────────
# Frame  1 : left foot forward, right foot back
# Frame  7 : mid-stride, body lowest
# Frame 13 : right foot forward, left foot back
# Frame 19 : mid-stride, body lowest
# Frame 25 = frame 1 (loop)

leg_swing    = 22   # degrees upper leg swing
knee_bend    = 28   # degrees lower leg bend
body_bob     = 0.012
spine_sway   = 4
arm_swing    = 18
tail_swing   = 12

for frame, l_upper, l_lower, r_upper, r_lower, bob, sway, tail in [
    # fr  LU       LL       RU        RL     bob    sway  tail
    ( 1,  -leg_swing, knee_bend,  leg_swing, -knee_bend*0.3,  0,    -spine_sway, -tail_swing),
    ( 7,  0,          knee_bend*0.3, 0,      knee_bend*0.3,  -body_bob, 0,       0),
    (13,  leg_swing, -knee_bend*0.3, -leg_swing, knee_bend, 0,     spine_sway,  tail_swing),
    (19,  0,          knee_bend*0.3, 0,      knee_bend*0.3,  -body_bob, 0,       0),
    (25,  -leg_swing, knee_bend,  leg_swing, -knee_bend*0.3,  0,    -spine_sway, -tail_swing),
]:
    key_rot("UpperLeg_L", frame,  l_upper, 0, 0)
    key_rot("LowerLeg_L", frame,  l_lower, 0, 0)
    key_rot("UpperLeg_R", frame,  r_upper, 0, 0)
    key_rot("LowerLeg_R", frame,  r_lower, 0, 0)
    key_loc("Hip",        frame,  0, 0, bob)
    key_rot("Spine",      frame,  0, 0, sway)
    key_rot("Tail1",      frame,  0, 0, tail)
    key_rot("Tail2",      frame,  0, 0, tail * 0.6)
    # Arms swing opposite to legs
    key_rot("UpperArm_L", frame,  r_upper * 0.6, 0, 0)
    key_rot("UpperArm_R", frame,  l_upper * 0.6, 0, 0)

# Set all curves to cyclic
for action in bpy.data.actions:
    for fcurve in action.fcurves:
        mod = fcurve.modifiers.new(type='CYCLES')
        mod.mode_before = 'REPEAT'
        mod.mode_after  = 'REPEAT'

bpy.ops.object.mode_set(mode='OBJECT')

# ── Export FBX ────────────────────────────────────────────────────────────────
OUT = r"C:\Users\LachlanB\TD\Assets\Models\dino_walk.fbx"
bpy.ops.export_scene.fbx(
    filepath=OUT,
    use_selection=False,
    object_types={'ARMATURE', 'MESH'},
    bake_anim=True,
    bake_anim_use_all_actions=True,
    bake_anim_step=1,
    bake_anim_simplify_factor=0.0,
    add_leaf_bones=False,
    primary_bone_axis='Y',
    secondary_bone_axis='X',
    axis_forward='-Z',
    axis_up='Y',
    global_scale=1.0,
)
print(f"Exported to {OUT}")
