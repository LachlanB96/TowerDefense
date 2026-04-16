import bpy
import math

# ── Paths ─────────────────────────────────────────────────────────────────────
BLEND_PATH = r"C:\Users\LachlanB\TD\Assets\Blender\sniper000.blend"
FBX_PATH   = r"C:\Users\LachlanB\TD\Assets\Models\sniper000.fbx"

# ── Clear scene ──────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for block in bpy.data.meshes:
    if block.users == 0:
        bpy.data.meshes.remove(block)
for block in bpy.data.materials:
    if block.users == 0:
        bpy.data.materials.remove(block)

# ══════════════════════════════════════════════════════════════════════════════
#  MATERIALS - matching tack000 theme
# ══════════════════════════════════════════════════════════════════════════════

# Wood - warm tan/brown (same as tack body)
wood_mat = bpy.data.materials.new(name="Wood")
wood_mat.use_nodes = True
bsdf = wood_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.76, 0.60, 0.42, 1.0)
bsdf.inputs["Roughness"].default_value = 0.75
bsdf.inputs["Metallic"].default_value = 0.0

# Metal - gray metallic bands (same as tack metal)
metal_mat = bpy.data.materials.new(name="Metal")
metal_mat.use_nodes = True
bsdf = metal_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.35, 0.35, 0.38, 1.0)
bsdf.inputs["Metallic"].default_value = 0.9
bsdf.inputs["Roughness"].default_value = 0.3

# DarkWood - darker brown for barrel stock
dark_wood_mat = bpy.data.materials.new(name="DarkWood")
dark_wood_mat.use_nodes = True
bsdf = dark_wood_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.40, 0.26, 0.15, 1.0)
bsdf.inputs["Roughness"].default_value = 0.65
bsdf.inputs["Metallic"].default_value = 0.0

# GunMetal - dark metallic for barrel
gun_metal_mat = bpy.data.materials.new(name="GunMetal")
gun_metal_mat.use_nodes = True
bsdf = gun_metal_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.18, 0.18, 0.22, 1.0)
bsdf.inputs["Metallic"].default_value = 0.95
bsdf.inputs["Roughness"].default_value = 0.25

# ScopeLens - blue-tinted glass for the scope lens
lens_mat = bpy.data.materials.new(name="ScopeLens")
lens_mat.use_nodes = True
bsdf = lens_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.2, 0.5, 0.9, 1.0)
bsdf.inputs["Metallic"].default_value = 0.8
bsdf.inputs["Roughness"].default_value = 0.1
bsdf.inputs["Emission Color"].default_value = (0.1, 0.3, 0.6, 1.0)
bsdf.inputs["Emission Strength"].default_value = 0.5

# ══════════════════════════════════════════════════════════════════════════════
#  BASE PLATFORM
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.55, depth=0.15, vertices=16,
    location=(0, 0, 0.075))
base = bpy.context.active_object
base.name = "SniperBase"
bpy.ops.object.shade_smooth()
base.data.materials.append(wood_mat)

# ══════════════════════════════════════════════════════════════════════════════
#  BODY - tall cylinder
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.38, depth=0.70, vertices=16,
    location=(0, 0, 0.50))
body = bpy.context.active_object
body.name = "SniperBody"
bpy.ops.object.shade_smooth()
body.data.materials.append(wood_mat)

# ══════════════════════════════════════════════════════════════════════════════
#  TOP CAP
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.42, depth=0.08, vertices=16,
    location=(0, 0, 0.89))
top_cap = bpy.context.active_object
top_cap.name = "TopCap"
bpy.ops.object.shade_smooth()
top_cap.data.materials.append(wood_mat)

# ══════════════════════════════════════════════════════════════════════════════
#  METAL BANDS
# ══════════════════════════════════════════════════════════════════════════════
band_positions = [0.28, 0.55, 0.75]
for i, z in enumerate(band_positions):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.40, minor_radius=0.025,
        major_segments=24, minor_segments=8,
        location=(0, 0, z))
    band = bpy.context.active_object
    band.name = f"MetalBand_{i}"
    bpy.ops.object.shade_smooth()
    band.data.materials.append(metal_mat)

# ══════════════════════════════════════════════════════════════════════════════
#  TURRET BASE
# ══════════════════════════════════════════════════════════════════════════════
TURRET_Z = 0.93
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.15, depth=0.10, vertices=12,
    location=(0, 0, TURRET_Z + 0.05))
turret_base = bpy.context.active_object
turret_base.name = "SniperTurret"
bpy.ops.object.shade_smooth()
turret_base.data.materials.append(metal_mat)

# ══════════════════════════════════════════════════════════════════════════════
#  GUN BARREL
# ══════════════════════════════════════════════════════════════════════════════
barrel_length = 0.80
barrel_z = TURRET_Z + 0.12

bpy.ops.mesh.primitive_cylinder_add(
    radius=0.04, depth=barrel_length, vertices=10,
    location=(0, barrel_length/2 - 0.10, barrel_z),
    rotation=(math.pi/2, 0, 0))
barrel = bpy.context.active_object
barrel.name = "SniperBarrel"
bpy.ops.object.shade_smooth()
barrel.data.materials.append(gun_metal_mat)

# ══════════════════════════════════════════════════════════════════════════════
#  MUZZLE TIP
# ══════════════════════════════════════════════════════════════════════════════
muzzle_y = barrel_length - 0.10
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.055, depth=0.06, vertices=10,
    location=(0, muzzle_y, barrel_z),
    rotation=(math.pi/2, 0, 0))
muzzle = bpy.context.active_object
muzzle.name = "SniperMuzzle"
bpy.ops.object.shade_smooth()
muzzle.data.materials.append(gun_metal_mat)

# ══════════════════════════════════════════════════════════════════════════════
#  STOCK
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.22, barrel_z - 0.02))
stock = bpy.context.active_object
stock.name = "SniperStock"
stock.scale = (0.06, 0.18, 0.07)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()
stock.data.materials.append(dark_wood_mat)

# ══════════════════════════════════════════════════════════════════════════════
#  SCOPE
# ══════════════════════════════════════════════════════════════════════════════
scope_z = barrel_z + 0.08
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.035, depth=0.30, vertices=10,
    location=(0, 0.12, scope_z),
    rotation=(math.pi/2, 0, 0))
scope = bpy.context.active_object
scope.name = "SniperScope"
bpy.ops.object.shade_smooth()
scope.data.materials.append(gun_metal_mat)

# Scope lenses (front + rear)
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.038, depth=0.015, vertices=10,
    location=(0, 0.28, scope_z),
    rotation=(math.pi/2, 0, 0))
lens_front = bpy.context.active_object
lens_front.name = "ScopeLensFront"
bpy.ops.object.shade_smooth()
lens_front.data.materials.append(lens_mat)

bpy.ops.mesh.primitive_cylinder_add(
    radius=0.038, depth=0.015, vertices=10,
    location=(0, -0.03, scope_z),
    rotation=(math.pi/2, 0, 0))
lens_rear = bpy.context.active_object
lens_rear.name = "ScopeLensRear"
bpy.ops.object.shade_smooth()
lens_rear.data.materials.append(lens_mat)

# Scope mount
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.12, barrel_z + 0.04))
mount = bpy.context.active_object
mount.name = "ScopeMount"
mount.scale = (0.025, 0.04, 0.035)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()
mount.data.materials.append(metal_mat)

# ══════════════════════════════════════════════════════════════════════════════
#  CROSSHAIR EMBLEMS on body
# ══════════════════════════════════════════════════════════════════════════════
BODY_RADIUS = 0.38
EMBLEM_Z = 0.50
EMBLEM_OFFSET = BODY_RADIUS + 0.005

for face_angle in [0, math.pi/2, math.pi, 3*math.pi/2]:
    cx = math.cos(face_angle) * EMBLEM_OFFSET
    cy = math.sin(face_angle) * EMBLEM_OFFSET

    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.04, minor_radius=0.008,
        major_segments=16, minor_segments=6,
        location=(cx, cy, EMBLEM_Z),
        rotation=(0, math.pi/2, face_angle))
    ring = bpy.context.active_object
    ring.name = f"Crosshair_Ring_{int(math.degrees(face_angle))}"
    ring.data.materials.append(metal_mat)

    directions = [
        (0, 0, 0.05),
        (0, 0, -0.05),
    ]
    perp_x = -math.sin(face_angle) * 0.05
    perp_y = math.cos(face_angle) * 0.05
    directions.append((perp_x, perp_y, 0))
    directions.append((-perp_x, -perp_y, 0))

    for j, (dx, dy, dz) in enumerate(directions):
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.006, depth=0.06, vertices=6,
            location=(cx + dx, cy + dy, EMBLEM_Z + dz))
        bar = bpy.context.active_object
        bar.name = f"Crosshair_Bar_{int(math.degrees(face_angle))}_{j}"
        if dz == 0:
            bar.rotation_euler = (0, math.pi/2, face_angle)
        bar.data.materials.append(metal_mat)

# ══════════════════════════════════════════════════════════════════════════════
#  SAVE & EXPORT
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
print(f"Saved: {BLEND_PATH}")

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
print(f"Exported: {FBX_PATH}")
print("Done!")
