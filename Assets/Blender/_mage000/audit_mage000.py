"""Objective health check for the Mage build.

Run:  blender -b -P Assets/Blender/_mage000/audit_mage000.py
Or:   python Assets/Blender/_tools/preview.py mage000 --audit

Builds the model from blender_mage000.py and reports the defect classes that are
cheap to get wrong and expensive to spot by eye:

  * open / non-manifold meshes   - revolve profiles that never close
  * geometry below the floor     - things that will clip the ground in Unity
  * left/right mirror symmetry   - a frame that is not mirror-symmetric puts
                                   paired parts in different places per side
  * levitating parts             - modelling rule 1, the whole point of this file
  * beard buried in the robe     - mage-specific; see below

The first four are the checks every asset gets. They are copied from
_knight000/audit_knight000.py rather than imported, because that one predates
there being two assets. If a THIRD asset needs them, extract a shared module
instead of copying a third time.

Prints a PASS/FAIL block. Keep it at PASS.
"""

import math
import os

import bpy
import bmesh
from mathutils import Vector

# Resolved relative to THIS file, not hardcoded. Modellers run in git worktrees,
# and an absolute main-repo path would make every worktree audit the unchanged
# baseline and print PASS regardless of what the modeller actually built.
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      os.pardir, "blender_mage000.py")
SCRIPT = os.path.normpath(SCRIPT)
exec(compile(open(SCRIPT, encoding="utf-8").read(), SCRIPT, "exec"))

dg = bpy.context.evaluated_depsgraph_get()
RIG = {"Ground"}                     # preview floor, never exported
objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name not in RIG]

fails = []


def wbb(o):
    """World-space bounding box as (min, max)."""
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


# -- 1. open / non-manifold, and 2. below the floor ----------------------------
open_meshes = []
below = []
for o in objs:
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    bm = bmesh.new()
    bm.from_mesh(me)
    n_bound = sum(1 for e in bm.edges if len(e.link_faces) < 2)
    if n_bound:
        open_meshes.append((n_bound, o.name))
    bm.free()
    zmin = min((o.matrix_world @ v.co).z for v in me.vertices) if me.vertices else 0.0
    if zmin < -0.001:
        below.append((round(zmin, 4), o.name))
    bpy.data.meshes.remove(me)

# -- 3. left/right mirror symmetry ---------------------------------------------
# The arms are posed differently on purpose - his right grips the staff, his left
# is held open and forward - so everything from the shoulder outward is expected
# to differ. Everything else must mirror.
#
# Robe_Piping_ is exempt for a different reason: the fold function is
# deliberately NOT mirror-symmetric about the front centreline, because cloth
# whose folds mirror perfectly reads as machined rather than draped. The two
# front edges therefore land on slightly different radii by design.
POSED = ("Sleeve_", "Forearm_", "Palm_", "Finger_", "Thumb_", "Robe_Piping_")
asym = []
for o in sorted(bpy.data.objects, key=lambda x: x.name):
    if o.type != 'MESH' or not o.name.endswith("_R"):
        continue
    if any(o.name.startswith(p) for p in POSED):
        continue
    twin = bpy.data.objects.get(o.name[:-2] + "_L")
    if not twin:
        continue
    a, b = wbb(o), wbb(twin)
    mir_min = Vector((-a[1].x, a[0].y, a[0].z))
    mir_max = Vector((-a[0].x, a[1].y, a[1].z))
    d = max((mir_min - b[0]).length, (mir_max - b[1]).length)
    if d > 0.004:
        asym.append((round(d, 4), o.name))

# -- 4. no levitating parts (modelling rule 1) ---------------------------------
# Every part must touch or overlap another. A pauldron - or here, a hat - hovering
# 4 cm off the body passes every other check in this file: it is manifold, above
# the floor and symmetric with its twin.
#
# Surface distance, not vertex-to-vertex. On a coarse mesh the nearest VERTEX can
# be far along a facet even when two surfaces are flush, which reports phantom
# gaps; closest_point_on_mesh gives true surface distance.
GAP = 0.005            # 5 mm on a ~2.5 m figure


def bb_gap(a, b):
    """Widest axis-wise separation between two world bounding boxes; 0 if they
    overlap. A cheap filter so the O(n^2) surface test only runs on neighbours."""
    return max(max(a[0][k] - b[1][k], b[0][k] - a[1][k], 0.0) for k in range(3))


# Parts that are SUPPOSED to hang in the air. The Mage currently has NONE - the
# gem is held by the claws, which is real contact. Do not add an entry here
# without asking: the tuple is a list of confirmed exceptions, not a way to
# silence the check.
FLOATERS_OK = ()
solid = [o for o in objs if not (FLOATERS_OK and o.name.startswith(FLOATERS_OK))]
bbs = {o.name: wbb(o) for o in solid}
evl = {o.name: o.evaluated_get(dg) for o in solid}

orphans = []
for o in solid:
    me = bpy.data.meshes.new_from_object(evl[o.name])
    pts = [o.matrix_world @ v.co for v in me.vertices]
    bpy.data.meshes.remove(me)
    if not pts:
        continue
    # Sample cap. Deliberately high enough that a small part is measured in FULL.
    # At 48 (the knight's number, for a model with six times as many objects) the
    # stride landed on a divisor of the torus ring size and only ever sampled the
    # inner and outer equators of a band - never its flanks, which are the parts
    # actually touching the shaft. A band sitting correctly on the staff was
    # reported as levitating 7 mm away. Under-sampling a geometric check produces
    # false positives, so this is a correctness fix, not a speed knob.
    sample = pts[::max(1, len(pts) // 160)]
    near = [h for h in solid
            if h is not o and bb_gap(bbs[o.name], bbs[h.name]) <= GAP * 4]
    best = float("inf")
    for h in near:
        he = evl[h.name]
        inv = h.matrix_world.inverted()
        for p in sample:
            ok, loc, _n, _i = he.closest_point_on_mesh(inv @ p)
            if ok:
                best = min(best, ((h.matrix_world @ loc) - p).length)
            if best <= GAP:
                break                      # touching; stop measuring this part
        if best <= GAP:
            break
    if best > GAP:
        orphans.append((best, o.name))

# -- 5. the beard must lie ON the robe, not inside it --------------------------
# Mage-specific, and the direct analogue of the knight's "cape generated inside
# the armour" check. The beard hangs down the chest, and the chest is the widest
# part of the robe: any straight interpolation of the beard's y values dips it
# back inside the cloth partway down, where it reads as a stain rather than hair.
HOSTS = [bpy.data.objects[n] for n in ("Robe", "Mantle", "Underrobe")
         if n in bpy.data.objects]
buried = 0
# Every lock, not a single "Beard" object - the beard was rebuilt as five
# separate sweeps on 2026-08-01 and a lookup by exact name silently checked
# nothing at all afterwards.
beard_parts = [o for o in objs if o.name.startswith("Beard")]
pts = []
for beard in beard_parts:
    bme = bpy.data.meshes.new_from_object(beard.evaluated_get(dg))
    pts += [beard.matrix_world @ v.co for v in bme.vertices]
    bpy.data.meshes.remove(bme)
if pts and HOSTS:
    # Skip the top of the beard: it is INSIDE the head by design, and the head is
    # not in HOSTS, but the collar sits high enough to catch those verts. Taken
    # from BEARD_TABLE rather than hardcoded - the whole head assembly has been
    # moved vertically once already, and a literal here would silently stop
    # matching the geometry.
    beard_cut = BEARD_TABLE[2][0]
    for p in pts[::2]:
        if p.z > beard_cut:
            continue
        for h in HOSTS:
            he = h.evaluated_get(dg)
            ok, loc, nrm, _i = he.closest_point_on_mesh(h.matrix_world.inverted() @ p)
            # -0.018, not a hair under zero: a beard RESTING on a chest sinks a
            # centimetre or so into the cloth, and that is correct. What this is
            # hunting is the beard disappearing INSIDE the robe partway down,
            # which is a couple of centimetres at least.
            if ok and (p - (h.matrix_world @ loc)).dot(
                    (h.matrix_world.to_3x3() @ nrm).normalized()) < -0.018:
                buried += 1
                break

print("=" * 68)
print("MAGE000 AUDIT")
print("=" * 68)
print("meshes checked            : %d" % len(objs))
print("open / non-manifold       : %d" % len(open_meshes))
for n, name in sorted(open_meshes, reverse=True)[:20]:
    print("    %-28s %d boundary edges" % (name, n))
print("below floor (z < 0)       : %d" % len(below))
for z, name in sorted(below)[:12]:
    print("    %-28s zmin=%s" % (name, z))
print("asymmetric non-posed pairs: %d" % len(asym))
for d, n in sorted(asym, reverse=True)[:12]:
    print("    %-28s mirror error %.4f" % (n, d))
print("beard parts / verts inside robe : %d part(s), %d buried"
      % (len(beard_parts), buried))
print("levitating parts (rule 1) : %d" % len(orphans))
for d, name in sorted(orphans, reverse=True)[:16]:
    print("    %-28s %s" % (name, "isolated" if d == float("inf")
                            else "nearest part %.4f away" % d))

if orphans:
    fails.append("%d levitating parts" % len(orphans))
if open_meshes:
    fails.append("%d open meshes" % len(open_meshes))
if below:
    fails.append("%d objects below floor" % len(below))
if asym:
    fails.append("%d asymmetric pairs" % len(asym))
if buried:
    fails.append("%d beard verts buried in the robe" % buried)

print("-" * 68)
print("RESULT: " + ("PASS" if not fails else "FAIL - " + "; ".join(fails)))
print("=" * 68)
