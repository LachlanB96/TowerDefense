import bpy
import math
from mathutils import Vector

# ── Paths ─────────────────────────────────────────────────────────────────────
BLEND_SRC = r"C:\Users\LachlanB\TD\Assets\Blender\tack000.blend"
BLEND_DST = r"C:\Users\LachlanB\TD\Assets\Blender\tack001.blend"
FBX_PATH  = r"C:\Users\LachlanB\TD\Assets\Models\tack001.fbx"

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

# Find TopCap surface Z for symbol placement
top_cap = bpy.data.objects.get("TopCap")
if top_cap:
    top_z = max(v.co.z for v in top_cap.data.vertices)
else:
    top_z = max_co.z
print(f"TopCap surface Z = {top_z:.4f}")

# ══════════════════════════════════════════════════════════════════════════════
#  NEW MATERIALS
# ══════════════════════════════════════════════════════════════════════════════

# NatureMetal — replaces the gray Metal bands
nature_metal = bpy.data.materials.new(name="NatureMetal")
nature_metal.use_nodes = True
bsdf = nature_metal.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.25, 0.55, 0.20, 1.0)
bsdf.inputs["Metallic"].default_value = 0.6
bsdf.inputs["Roughness"].default_value = 0.35

# NatureTack — replaces the silver Tack material on heads/shafts/tips
nature_tack = bpy.data.materials.new(name="NatureTack")
nature_tack.use_nodes = True
bsdf = nature_tack.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.30, 0.60, 0.25, 1.0)
bsdf.inputs["Metallic"].default_value = 0.7
bsdf.inputs["Roughness"].default_value = 0.30

# NatureSymbol — emissive green for the tree emblem
nature_symbol_mat = bpy.data.materials.new(name="NatureSymbol")
nature_symbol_mat.use_nodes = True
bsdf = nature_symbol_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.15, 0.7, 0.1, 1.0)
bsdf.inputs["Emission Color"].default_value = (0.1, 0.6, 0.05, 1.0)
bsdf.inputs["Emission Strength"].default_value = 2.0
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Roughness"].default_value = 0.50

# NatureTrunk — brown for tree trunk
nature_trunk_mat = bpy.data.materials.new(name="NatureTrunk")
nature_trunk_mat.use_nodes = True
bsdf = nature_trunk_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.35, 0.2, 0.08, 1.0)
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Roughness"].default_value = 0.8

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
            slot.material = nature_metal
        elif slot.material.name == "Tack":
            slot.material = nature_tack

# ══════════════════════════════════════════════════════════════════════════════
#  CREATE TREE SYMBOL ON TOP
# ══════════════════════════════════════════════════════════════════════════════
symbol_scale = tower_radius * 0.35

# Trunk (small cylinder)
trunk_radius = 0.015 * symbol_scale / 0.15
trunk_height = 0.12 * symbol_scale / 0.15
bpy.ops.mesh.primitive_cylinder_add(
    radius=trunk_radius, depth=trunk_height,
    location=(0, 0, top_z + trunk_height / 2 + 0.001),
    vertices=8)
trunk = bpy.context.active_object
trunk.name = "TreeSymbol_Trunk"
bpy.ops.object.shade_smooth()
trunk.data.materials.append(nature_trunk_mat)

# Canopy layers (three stacked cones getting smaller, like a pine tree)
canopy_configs = [
    ("TreeSymbol_Canopy_Bot", 0.09, 0.07, top_z + trunk_height * 0.4),
    ("TreeSymbol_Canopy_Mid", 0.07, 0.06, top_z + trunk_height * 0.65),
    ("TreeSymbol_Canopy_Top", 0.05, 0.05, top_z + trunk_height * 0.9),
]

for name, radius_factor, height_factor, z_pos in canopy_configs:
    r = radius_factor * symbol_scale / 0.15
    h = height_factor * symbol_scale / 0.15
    bpy.ops.mesh.primitive_cone_add(
        radius1=r, radius2=0, depth=h,
        location=(0, 0, z_pos + h / 2),
        vertices=12)
    cone = bpy.context.active_object
    cone.name = name
    bpy.ops.object.shade_smooth()
    cone.data.materials.append(nature_symbol_mat)

# Duplicate tree symbol rotated for visibility from all angles
# (the cones are already rotationally symmetric, so just add a second trunk+canopy set offset slightly)

print(f"Tree symbol placed at Z={top_z:.4f}")

# ══════════════════════════════════════════════════════════════════════════════
#  LEAF PARTICLES (small spheres around the tower for decoration)
# ══════════════════════════════════════════════════════════════════════════════
import random
random.seed(42)

leaf_mat = bpy.data.materials.new(name="LeafDecor")
leaf_mat.use_nodes = True
bsdf = leaf_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.2, 0.65, 0.15, 1.0)
bsdf.inputs["Roughness"].default_value = 0.6

for i in range(NUM_DISKS):
    angle = i * (2 * math.pi / NUM_DISKS)
    dist = tower_radius * 1.1
    x = center.x + math.cos(angle) * dist
    y = center.y + math.sin(angle) * dist

    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=tower_radius * 0.15, segments=8, ring_count=6,
        location=(x, y, center.z))
    leaf = bpy.context.active_object
    leaf.name = f"Disk_{i:02d}"
    leaf.scale = (1.0, 1.0, 0.7)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()
    leaf.data.materials.clear()
    leaf.data.materials.append(leaf_mat)

# ── Scene settings ────────────────────────────────────────────────────────────
bpy.context.scene.frame_start = 0
bpy.context.scene.frame_end   = ANIM_FRAMES
bpy.context.scene.render.fps  = FPS

# ══════════════════════════════════════════════════════════════════════════════
#  SAVE & EXPORT
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.wm.save_as_mainfile(filepath=BLEND_DST)
print(f"Saved: {BLEND_DST}")

bpy.ops.export_scene.fbx(
    filepath=FBX_PATH,
    use_selection=False,
    object_types={'ARMATURE', 'MESH'},
    bake_anim=False,
    add_leaf_bones=False,
    axis_forward='-Z',
    axis_up='Y',
    global_scale=1.0,
)
print(f"Exported tower: {FBX_PATH}")

print("Done!")
