import bpy
import math
from mathutils import Vector

FBX_PATH  = r"C:\Users\LachlanB\TD\Assets\Models\dino_walk.fbx"
BLEND_DST = r"C:\Users\LachlanB\TD\Assets\Blender\dino_walk.blend"

# ── Clear scene ───────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ── Import FBX ────────────────────────────────────────────────────────────────
bpy.ops.import_scene.fbx(filepath=FBX_PATH)

armature = None
mesh_obj = None
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        armature = obj
    elif obj.type == 'MESH':
        mesh_obj = obj

print(f"Armature: {armature.name}, Mesh: {mesh_obj.name}")
print(f"Total vertices: {len(mesh_obj.data.vertices)}")

# ── Print bone hierarchy ─────────────────────────────────────────────────────
bone_info = {}
print("\n=== BONE HIERARCHY ===")
for bone in armature.data.bones:
    h = armature.matrix_world @ bone.head_local
    t = armature.matrix_world @ bone.tail_local
    bone_info[bone.name] = (h, t)
    parent = bone.parent.name if bone.parent else "None"
    print(f"  {bone.name}: head=({h.x:.4f},{h.y:.4f},{h.z:.4f}) tail=({t.x:.4f},{t.y:.4f},{t.z:.4f}) parent={parent}")

# ══════════════════════════════════════════════════════════════════════════════
#  FIX MATERIAL
# ══════════════════════════════════════════════════════════════════════════════
mat = mesh_obj.data.materials[0] if mesh_obj.data.materials else bpy.data.materials.new("DinoMat")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (0.85, 0.20, 0.15, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.7
if not mesh_obj.data.materials:
    mesh_obj.data.materials.append(mat)
print("\nMaterial set to red-orange")

# ══════════════════════════════════════════════════════════════════════════════
#  FIX BONE WEIGHTS — Root EXCLUDED from primary assignment
# ══════════════════════════════════════════════════════════════════════════════

def closest_on_segment(p, a, b):
    ab = b - a
    if ab.length < 1e-8:
        return a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.dot(ab)))
    return a + ab * t

def dist_to_bone(p, name):
    h, t = bone_info[name]
    return (p - closest_on_segment(p, h, t)).length

# Clear all existing weights and armature modifiers
mesh_obj.vertex_groups.clear()
for mod in list(mesh_obj.modifiers):
    if mod.type == 'ARMATURE':
        mesh_obj.modifiers.remove(mod)

all_bone_names = [b.name for b in armature.data.bones]
# CRITICAL: exclude Root from the assignment pool
assign_bones = [name for name in all_bone_names if name != 'Root']
print(f"\nAssignment bones (no Root): {assign_bones}")

# Create vertex groups for ALL bones (including Root, but Root gets no weight)
vgroups = {name: mesh_obj.vertex_groups.new(name=name) for name in all_bone_names}

mesh_world = mesh_obj.matrix_world

for v in mesh_obj.data.vertices:
    pos = mesh_world @ v.co

    # Compute distance to every non-Root bone
    dists = [(name, dist_to_bone(pos, name)) for name in assign_bones]
    dists.sort(key=lambda x: x[1])

    n1, d1 = dists[0]
    n2, d2 = dists[1] if len(dists) > 1 else (dists[0][0], dists[0][1])

    if d1 < 1e-8:
        # Vertex is exactly on a bone — full weight
        vgroups[n1].add([v.index], 1.0, 'REPLACE')
    elif d2 > 1e-8 and d1 / d2 < 0.5:
        # Much closer to one bone — full weight to it
        vgroups[n1].add([v.index], 1.0, 'REPLACE')
    else:
        # Blend between 2 closest bones using inverse-distance
        inv1 = 1.0 / (d1 + 1e-8)
        inv2 = 1.0 / (d2 + 1e-8)
        total = inv1 + inv2
        w1 = inv1 / total
        w2 = inv2 / total
        vgroups[n1].add([v.index], w1, 'REPLACE')
        vgroups[n2].add([v.index], w2, 'REPLACE')

# Add armature modifier
mod = mesh_obj.modifiers.new(name='Armature', type='ARMATURE')
mod.object = armature

# Print weight statistics
print("\n=== WEIGHT STATS ===")
for name in all_bone_names:
    vg = vgroups[name]
    count = sum(1 for v in mesh_obj.data.vertices
                for g in v.groups if g.group == vg.index and g.weight > 0.05)
    print(f"  '{name}': {count} verts (weight > 0.05)")

# ══════════════════════════════════════════════════════════════════════════════
#  CREATE WALK ANIMATION
# ══════════════════════════════════════════════════════════════════════════════

# Clear ALL existing animations
for obj in bpy.data.objects:
    if obj.animation_data:
        obj.animation_data_clear()
for action in list(bpy.data.actions):
    bpy.data.actions.remove(action)

bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 24
bpy.context.scene.render.fps = 24

# Select armature and enter pose mode
bpy.ops.object.select_all(action='DESELECT')
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.object.mode_set(mode='POSE')

# Set all bones to XYZ Euler
for pb in armature.pose.bones:
    pb.rotation_mode = 'XYZ'

# Create action
action = bpy.data.actions.new(name="DinoArmatureAction")
action.use_fake_user = True
if armature.animation_data is None:
    armature.animation_data_create()
armature.animation_data.action = action

STRIDE = 30  # degrees — bigger stride for visible movement

def kf(bone_name, frame, ex=0, ey=0, ez=0):
    """Keyframe a bone's rotation. Prints warning if bone not found."""
    pb = armature.pose.bones.get(bone_name)
    if pb is None:
        print(f"  WARNING: bone '{bone_name}' not found in pose!")
        return False
    pb.rotation_euler = (math.radians(ex), math.radians(ey), math.radians(ez))
    pb.keyframe_insert(data_path="rotation_euler", frame=frame)
    return True

print("\n=== CREATING ANIMATION ===")
print("Available pose bones:", [pb.name for pb in armature.pose.bones])

# Walk cycle: 4 key poses across 24 frames (1 second at 24fps)
# Legs: alternating forward/back with knee bend
# Tail: gentle wave sway (Y-axis), Tail2 lags Tail1 by ~quarter cycle
# Head: slight bob, Hip: subtle tilt

for frame, data in [
    # Frame 1: left leg forward, right leg back
    (1,  {"UL_L": -STRIDE, "LL_L": 15,   "UL_R": STRIDE,  "LL_R": -20,
           "T1y": 4,  "T2y": 6,  "Hx": -2, "Headx": 2}),
    # Frame 7: passing position (both legs under body)
    (7,  {"UL_L": 0,       "LL_L": -30,  "UL_R": 0,       "LL_R": -30,
           "T1y": 0,  "T2y": 4,  "Hx": 0,  "Headx": -1}),
    # Frame 13: right leg forward, left leg back
    (13, {"UL_L": STRIDE,  "LL_L": -20,  "UL_R": -STRIDE, "LL_R": 15,
           "T1y": -4, "T2y": 0,  "Hx": -2, "Headx": 2}),
    # Frame 19: passing position
    (19, {"UL_L": 0,       "LL_L": -30,  "UL_R": 0,       "LL_R": -30,
           "T1y": 0,  "T2y": -4, "Hx": 0,  "Headx": -1}),
]:
    kf("UpperLeg_L",  frame, ex=data["UL_L"])
    kf("LowerLeg_L",  frame, ex=data["LL_L"])
    kf("UpperLeg_R",  frame, ex=data["UL_R"])
    kf("LowerLeg_R",  frame, ex=data["LL_R"])
    # Tail: smooth Y-axis sway with wave propagation
    kf("Tail1",       frame, ey=data["T1y"])
    kf("Tail2",       frame, ey=data["T2y"])
    # Body motion
    kf("Hip",         frame, ex=data["Hx"])
    kf("Head",        frame, ex=data["Headx"])

# Loop closure: frame 25 = frame 1
kf("UpperLeg_L",  25, ex=-STRIDE)
kf("LowerLeg_L",  25, ex=15)
kf("UpperLeg_R",  25, ex=STRIDE)
kf("LowerLeg_R",  25, ex=-20)
kf("Tail1",       25, ey=4)
kf("Tail2",       25, ey=6)
kf("Hip",         25, ex=-2)
kf("Head",        25, ex=2)

# Verify fcurves
print(f"\nAction '{action.name}': {len(action.fcurves)} fcurves")
for fc in action.fcurves:
    print(f"  {fc.data_path}[{fc.array_index}]: {len(fc.keyframe_points)} keys")

bpy.ops.object.mode_set(mode='OBJECT')

# Confirm action assignment
print(f"\nActive action: {armature.animation_data.action.name if armature.animation_data and armature.animation_data.action else 'NONE'}")

# ── Save blend ────────────────────────────────────────────────────────────────
bpy.ops.wm.save_as_mainfile(filepath=BLEND_DST)
print(f"\nSaved: {BLEND_DST}")

# ══════════════════════════════════════════════════════════════════════════════
#  EXPORT FBX
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.export_scene.fbx(
    filepath=FBX_PATH,
    use_selection=False,
    object_types={'ARMATURE', 'MESH'},
    bake_anim=True,
    bake_anim_use_all_actions=True,
    bake_anim_step=1,
    bake_anim_simplify_factor=0.0,
    add_leaf_bones=False,
    axis_forward='-Z',
    axis_up='Y',
    global_scale=1.0,
    mesh_smooth_type='FACE',
)
print(f"Exported: {FBX_PATH}")
print("Done!")
