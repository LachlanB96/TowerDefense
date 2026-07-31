"""A deliberately tiny conforming asset: one coloured cube.

Exists so the preview harness has something to test against that builds in
about a second. It is also the reference example of what "conforming" means:

  1. Every tunable value is a module-level global, set before the build runs.
  2. A single top-level build call.
  3. The variant hook block sits immediately before that call.
  4. render_view() honours RENDER_ONLY.

Any blender_*.py that follows those four rules can be driven by _tools/preview.py.
"""

import os

import bpy

# Trap: read_factory_settings is blocked inside the MCP sandbox. read_homefile
# with factory startup gives the same empty scene and works everywhere.
bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)

SCENE = bpy.context.scene

# -- Tunables. A VARIANT dict overrides any of these. --------------------------
RENDER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest_out")
CUBE_SIZE = 1.0
CUBE_COLOR = (0.80, 0.10, 0.10, 1.0)
DO_RENDER = True


def add_cube_at(x, y, z):
    """A helper _patch source is expected to be able to reach. See selftest."""
    bpy.ops.mesh.primitive_cube_add(size=CUBE_SIZE, location=(x, y, z))
    ob = bpy.context.active_object
    mat = bpy.data.materials.new("SelftestMat")
    # In Blender 5.1, bpy.data.materials.new() already returns a material with
    # use_nodes == True and a populated node_tree (Principled BSDF + Material
    # Output) - node-based shading is no longer optional. Explicitly assigning
    # mat.use_nodes = True here is a no-op that only serves to touch a property
    # slated for removal in 6.0 and trip a DeprecationWarning, so it is
    # deliberately not set.
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = CUBE_COLOR
    ob.data.materials.append(mat)
    return ob


def build_asset():
    add_cube_at(0.0, 0.0, 0.0)


def build_rig():
    bpy.ops.object.camera_add(location=(3.0, -3.0, 2.2),
                              rotation=(1.10, 0.0, 0.785))
    SCENE.camera = bpy.context.active_object
    bpy.ops.object.light_add(type='SUN', location=(2.0, -2.0, 4.0))


def render_view(name, res=(160, 160), samples=32):
    # RENDER_ONLY lets a preview run render a cheap subset. None means "all".
    only = globals().get("RENDER_ONLY")
    if only is not None and name not in only:
        return
    scale = globals().get("SAMPLE_SCALE", 1.0)
    if hasattr(SCENE.eevee, "taa_render_samples"):
        SCENE.eevee.taa_render_samples = max(8, int(samples * scale))
    SCENE.render.resolution_x, SCENE.render.resolution_y = res
    os.makedirs(RENDER_DIR, exist_ok=True)
    SCENE.render.filepath = os.path.join(RENDER_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", SCENE.render.filepath)


# --- variant hook -------------------------------------------------------------
# Copy this block verbatim into any script that opts in. It goes AFTER every
# default is set and BEFORE anything is built.
#
# Why copy-paste rather than import: globals() below resolves to the CALLING
# module's own namespace - this script's globals, which is exactly what the
# hook needs (VARIANT overrides must land as THIS script's globals, and
# _patch must exec against those same globals so it can see this script's
# own helpers). If this block lived in an importable helper function instead,
# calling that helper would make globals() resolve to the HELPER module's
# namespace, not the asset script's - so VARIANT overrides and _patch would
# silently land somewhere the real build never reads from. Do not "clean this
# up" into a shared function; it would break name resolution, not simplify it.
_v = globals().get("VARIANT", {})
globals().update({k: v for k, v in _v.items() if not k.startswith("_")})
if _v.get("_patch"):
    exec(_v["_patch"], globals())
# ------------------------------------------------------------------------------

build_asset()
build_rig()

if DO_RENDER:
    render_view("front")
    render_view("side")
    render_view("icon_184", res=(184, 184))
