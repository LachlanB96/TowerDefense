import bpy
import math
from mathutils import Vector

# ── Paths ─────────────────────────────────────────────────────────────────────
BLEND_SRC = r"C:\Users\LachlanB\TD\Assets\Blender\tack000.blend"
BLEND_DST = r"C:\Users\LachlanB\TD\Assets\Blender\tack010.blend"
FBX_PATH  = r"C:\Users\LachlanB\TD\Assets\Models\tack010.fbx"

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

# SkyMetal — replaces the gray Metal bands
sky_metal = bpy.data.materials.new(name="SkyMetal")
sky_metal.use_nodes = True
bsdf = sky_metal.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.55, 0.78, 0.92, 1.0)
bsdf.inputs["Metallic"].default_value = 0.85
bsdf.inputs["Roughness"].default_value = 0.25

# SkyTack — replaces the silver Tack material on heads/shafts/tips
sky_tack = bpy.data.materials.new(name="SkyTack")
sky_tack.use_nodes = True
bsdf = sky_tack.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.60, 0.82, 0.95, 1.0)
bsdf.inputs["Metallic"].default_value = 0.9
bsdf.inputs["Roughness"].default_value = 0.20

# AirPuff — projectile material (soft translucent white)
air_puff_mat = bpy.data.materials.new(name="AirPuff")
air_puff_mat.use_nodes = True
bsdf = air_puff_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.85, 0.92, 1.0, 1.0)
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Roughness"].default_value = 0.8
bsdf.inputs["Alpha"].default_value = 0.6
air_puff_mat.blend_method = 'BLEND' if hasattr(air_puff_mat, 'blend_method') else 'OPAQUE'

# AirSymbol — emissive cyan for the wind emblem
air_symbol_mat = bpy.data.materials.new(name="AirSymbol")
air_symbol_mat.use_nodes = True
bsdf = air_symbol_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.4, 0.85, 1.0, 1.0)
bsdf.inputs["Emission Color"].default_value = (0.3, 0.75, 1.0, 1.0)
bsdf.inputs["Emission Strength"].default_value = 2.5
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
            slot.material = sky_metal
        elif slot.material.name == "Tack":
            slot.material = sky_tack

# ══════════════════════════════════════════════════════════════════════════════
#  CREATE AIR/WIND SYMBOL ON TOP (three curved swoosh lines)
# ══════════════════════════════════════════════════════════════════════════════
symbol_scale = tower_radius * 0.35
thickness = 0.04 * symbol_scale / 0.15

def make_swoosh(name, y_offset, length_factor=1.0, rotation_z=0.0):
    """Create a single curved wind swoosh line."""
    num_pts = 12
    verts = []
    half_width = 0.03 * symbol_scale / 0.15

    for i in range(num_pts):
        t = i / (num_pts - 1)
        x = (t - 0.5) * 0.4 * length_factor * symbol_scale / 0.15
        # Gentle S-curve
        z_curve = math.sin(t * math.pi) * 0.06 * symbol_scale / 0.15
        # Taper width at ends
        w = half_width * math.sin(t * math.pi)
        w = max(w, half_width * 0.2)
        verts.append((x, y_offset + w, z_curve))
        verts.append((x, y_offset - w, z_curve))

    faces = []
    for i in range(num_pts - 1):
        v0 = i * 2
        faces.append((v0, v0 + 2, v0 + 3, v0 + 1))

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (0, 0, top_z)
    obj.rotation_euler = (0, 0, rotation_z)

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Solidify for 3D thickness
    mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod.thickness = thickness
    mod.offset = 0
    bpy.ops.object.modifier_apply(modifier="Solidify")

    bpy.ops.object.shade_smooth()
    obj.data.materials.append(air_symbol_mat)
    return obj

# Three horizontal swoosh lines stacked vertically
s1 = make_swoosh("AirSymbol_Top",    0.06 * symbol_scale / 0.15, length_factor=0.7)
s2 = make_swoosh("AirSymbol_Mid",    0.0,                        length_factor=1.0)
s3 = make_swoosh("AirSymbol_Bot",   -0.06 * symbol_scale / 0.15, length_factor=0.7)

# Duplicate rotated 90 degrees so visible from all sides
s4 = make_swoosh("AirSymbol_Top_B",  0.06 * symbol_scale / 0.15, length_factor=0.7, rotation_z=math.pi/2)
s5 = make_swoosh("AirSymbol_Mid_B",  0.0,                        length_factor=1.0, rotation_z=math.pi/2)
s6 = make_swoosh("AirSymbol_Bot_B", -0.06 * symbol_scale / 0.15, length_factor=0.7, rotation_z=math.pi/2)

print(f"Air symbol placed at Z={top_z:.4f}")

# ══════════════════════════════════════════════════════════════════════════════
#  ANIMATED AIR PUFFS (shoot animation)
# ══════════════════════════════════════════════════════════════════════════════
PUFF_RADIUS    = max(tower_radius * 0.25, 0.08)
FLY_DISTANCE   = tower_radius * 6
CENTER_Z       = center.z

disks = []
for i in range(NUM_DISKS):
    angle = i * (2 * math.pi / NUM_DISKS)

    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=PUFF_RADIUS, segments=12, ring_count=8,
        location=(center.x, center.y, CENTER_Z))
    puff = bpy.context.active_object
    puff.name = f"Disk_{i:02d}"

    # Squash into a cloud-like puff
    puff.scale = (1.0, 1.0, 0.6)
    bpy.ops.object.transform_apply(scale=True)

    bpy.ops.object.shade_smooth()

    puff.data.materials.clear()
    puff.data.materials.append(air_puff_mat)

    ex = center.x + math.cos(angle) * FLY_DISTANCE
    ey = center.y + math.sin(angle) * FLY_DISTANCE

    # Frame 0: hidden at center
    puff.location = (center.x, center.y, CENTER_Z)
    puff.scale = (0.01, 0.01, 0.01)
    puff.keyframe_insert(data_path="location", frame=0)
    puff.keyframe_insert(data_path="scale",    frame=0)

    # Frame 1: appear and expand
    puff.scale = (0.8, 0.8, 0.8)
    puff.keyframe_insert(data_path="location", frame=1)
    puff.keyframe_insert(data_path="scale",    frame=1)

    # Frame 6: expand while flying
    mid_x = center.x + math.cos(angle) * FLY_DISTANCE * 0.5
    mid_y = center.y + math.sin(angle) * FLY_DISTANCE * 0.5
    puff.location = (mid_x, mid_y, CENTER_Z)
    puff.scale = (1.3, 1.3, 1.3)
    puff.keyframe_insert(data_path="location", frame=ANIM_FRAMES // 2)
    puff.keyframe_insert(data_path="scale",    frame=ANIM_FRAMES // 2)

    # Frame 10: at destination, expanding and dissipating
    puff.location = (ex, ey, CENTER_Z)
    puff.keyframe_insert(data_path="location", frame=ANIM_FRAMES - 2)

    # Frame 12: vanish (puff dissipates)
    puff.scale = (1.8, 1.8, 1.8)
    puff.keyframe_insert(data_path="scale", frame=ANIM_FRAMES)

    if puff.animation_data and puff.animation_data.action:
        puff.animation_data.action.name = f"Tack010Shoot_{i:02d}"
        for fc in puff.animation_data.action.fcurves:
            for kf in fc.keyframe_points:
                kf.interpolation = 'LINEAR'

    disks.append(puff)

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

print("Done!")
