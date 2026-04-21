import bpy
import math
import random
from mathutils import Vector

# ── Paths ─────────────────────────────────────────────────────────────────────
BLEND_DST = r"C:\Users\LachlanB\TD\Assets\Blender\lake.blend"
FBX_PATH  = r"C:\Users\LachlanB\TD\Assets\Models\lake.fbx"

# ── Parameters (hand-tune here, then re-run the script) ──────────────────────
LAKE_RADIUS      = 2.5
BOUNDARY_VERTS   = 32      # polygon count around the rim before noise
BOUNDARY_NOISE   = 0.35    # +/- fraction of radius applied per rim vertex
SUBDIVISIONS     = 4       # extra cuts for bob animation granularity
SEED             = 7

random.seed(SEED)

# ── Start with an empty scene ─────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)

# ── Build the blob ────────────────────────────────────────────────────────────
bpy.ops.mesh.primitive_circle_add(
    vertices=BOUNDARY_VERTS,
    radius=LAKE_RADIUS,
    fill_type='NGON',
)
lake = bpy.context.active_object
lake.name = "Lake"

# Jitter each rim vertex radially to produce an irregular outline.
mesh = lake.data
for v in mesh.vertices:
    d = v.co.length
    if d > 0.01:
        factor = 1.0 + (random.random() - 0.5) * BOUNDARY_NOISE
        v.co.x *= factor
        v.co.y *= factor

# Subdivide the interior so per-vertex bob is smooth at runtime.
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
for _ in range(SUBDIVISIONS):
    bpy.ops.mesh.subdivide()
bpy.ops.object.mode_set(mode='OBJECT')

# ── Material (starting colour; WaterLake component lerps it at runtime) ──────
mat = bpy.data.materials.new(name="LakeWater")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.15, 0.45, 0.75, 1.0)
bsdf.inputs["Roughness"].default_value  = 0.20
bsdf.inputs["Metallic"].default_value   = 0.0
lake.data.materials.clear()
lake.data.materials.append(mat)

bpy.ops.object.shade_smooth()

# ── Save and export ───────────────────────────────────────────────────────────
bpy.ops.wm.save_as_mainfile(filepath=BLEND_DST)
print(f"Saved: {BLEND_DST}")

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
print(f"Exported lake: {FBX_PATH}")
print("Done!")
