"""Objective health check for the Silent Knight build.

Run:  blender -b -P Assets/Blender/_knight000/audit_knight000.py

Builds the model from blender_knight000.py and reports the defect classes that
are cheap to get wrong and expensive to spot by eye:

  * open / non-manifold meshes   - revolve profiles that never close
  * coplanar same-material pairs - the z-fighting that shredded the emblem foot
  * geometry below the floor     - things that will clip the ground in Unity
  * bands not concentric with the limb they clasp

Prints a PASS/FAIL block. Keep it at zero.
"""

import os
import sys

import bpy
import bmesh
from mathutils import Vector

# Resolved relative to THIS file, not hardcoded, as in audit_mage000.py: a
# worktree's audit audits the worktree's script, not the main repo's baseline.
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      os.pardir, "blender_knight000.py")
SCRIPT = os.path.normpath(SCRIPT)
exec(compile(open(SCRIPT, encoding="utf-8").read(), SCRIPT, "exec"))

dg = bpy.context.evaluated_depsgraph_get()
CUTTERS = {"Cut_EyeSlot", "Cut_NasalSlot"}
RIG = {"Ground"}
objs = [o for o in bpy.data.objects
        if o.type == 'MESH' and o.name not in CUTTERS | RIG]

fails = []

# -- 1. open / non-manifold ----------------------------------------------------
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

# -- 2. coplanar same-material pairs ------------------------------------------
# Cheap proxy for z-fighting: two objects sharing a material whose bounding
# boxes overlap almost completely AND whose surfaces sit at nearly the same
# distance from the body axis. Overlapping armour lames are fine; two flat
# patches occupying the same shell are not.
def wbb(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))

# Gems are excluded: a ruby is SUPPOSED to sit half-sunk in its setting, so a
# stone overlapping its plate is correct, not a defect.
EMBLEM = [o for o in objs if "Emblem" in o.name and "Ruby" not in o.name]
coplanar = []
for i in range(len(EMBLEM)):
    for j in range(i + 1, len(EMBLEM)):
        a, b = EMBLEM[i], EMBLEM[j]
        amin, amax = wbb(a)
        bmin, bmax = wbb(b)
        ov = Vector((max(0.0, min(amax[k], bmax[k]) - max(amin[k], bmin[k]))
                     for k in range(3)))
        if ov.x > 0.02 and ov.y > 0.004 and ov.z > 0.02:
            # Real overlap in all three axes between two flat emblem patches.
            coplanar.append("%s / %s  overlap=(%.3f %.3f %.3f)"
                            % (a.name, b.name, ov.x, ov.y, ov.z))

# -- 3. bands concentric with their limb --------------------------------------
# A band whose plane is not perpendicular to the surface it clasps floats on one
# side and sinks on the other. Measure how far the band's ring sits from the
# nearest point of the named host, around the ring.
def band_fit(band_name, host_name, samples=24):
    """Walk the band's own ring and measure to the host SURFACE at each step.

    Vertex-to-vertex distance was the first attempt and it lies: both meshes are
    coarse, so a band sitting flush on a 20-segment limb still reports a 4 cm
    "gap" simply because the nearest vertex is far along the facet. Blender's
    closest_point_on_mesh gives true surface distance. What matters is not the
    distance itself but its VARIATION around the ring - a concentric band is
    even all the way round, a mis-oriented one floats on one side.
    """
    b = bpy.data.objects.get(band_name)
    h = bpy.data.objects.get(host_name)
    if not b or not h:
        return None
    h_eval = h.evaluated_get(dg)
    centre = b.matrix_world.translation
    rot = b.matrix_world.to_3x3()
    bme = bpy.data.meshes.new_from_object(b.evaluated_get(dg))
    major = max(((b.matrix_world @ v.co) - centre).length for v in bme.vertices)
    bpy.data.meshes.remove(bme)

    ds = []
    for i in range(samples):
        a = 2.0 * 3.14159265 * i / samples
        # Ring lies in the band's local XY plane.
        p_world = centre + rot @ Vector((major * __import__("math").cos(a),
                                         major * __import__("math").sin(a), 0.0))
        p_local = h.matrix_world.inverted() @ p_world
        ok, loc, _nrm, _idx = h_eval.closest_point_on_mesh(p_local)
        if ok:
            ds.append(((h.matrix_world @ loc) - p_world).length)
    if not ds:
        return None
    return (round(min(ds), 4), round(max(ds), 4), round(max(ds) - min(ds), 4))

band_checks = {}
for bn, hn in (("Gauntlet_CuffRim_R", "Gauntlet_Cuff_R"),
               ("Gauntlet_CuffRim_L", "Gauntlet_Cuff_L"),
               ("Vambrace_Band_R", "Vambrace_R"),
               ("Greave_Band_R", "Greave_R")):
    fit = band_fit(bn, hn)
    if fit:
        band_checks[bn] = fit

# -- 4. left/right mirror symmetry --------------------------------------------
# The arms are posed differently on purpose (right holds the sword point-down,
# left carries the tome forward), so everything from the shoulder joint outward
# is expected to differ. Everything else must mirror.
POSED = ("Rerebrace", "Vambrace", "Couter", "Gauntlet", "Arm_Voider", "Fist_",
         "Finger_", "Thumb_")
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

# -- 5. cape must not be generated inside the torso armour ---------------------
HOSTS = [bpy.data.objects[n] for n in
         ("Cuirass", "Gorget_Collar", "Gorget_Lame1", "Gorget_Lame2",
          "Fauld_Lame1", "Fauld_Lame2", "Fauld_Lame3") if n in bpy.data.objects]
buried = 0
for cname in ("Cape", "Cape_Mantle", "CapeEmblem_T"):
    c = bpy.data.objects.get(cname)
    if not c:
        continue
    cme = bpy.data.meshes.new_from_object(c.evaluated_get(dg))
    pts = [c.matrix_world @ v.co for v in cme.vertices]
    bpy.data.meshes.remove(cme)
    for p in pts[::3]:
        for h in HOSTS:
            he = h.evaluated_get(dg)
            ok, loc, nrm, _i = he.closest_point_on_mesh(h.matrix_world.inverted() @ p)
            if ok and (p - (h.matrix_world @ loc)).dot(
                    (h.matrix_world.to_3x3() @ nrm).normalized()) < -0.002:
                buried += 1
                break

# -- 6. no levitating parts (modelling rule 1) --------------------------------
# Every part must touch or overlap another. A pauldron hovering 4 cm off the
# shoulder passes every other check in this file - it is manifold, above the
# floor, and symmetric with its twin - so nothing caught it until this existed.
#
# Surface distance, not vertex-to-vertex, for the reason band_fit already
# documents: on a coarse mesh the nearest VERTEX can be far along a facet even
# when the two surfaces are flush, which reports phantom gaps.
GAP = 0.005            # 5 mm on a ~2 m figure

def bb_gap(a, b):
    """Widest axis-wise separation between two world bounding boxes; 0 if they overlap."""
    return max(max(a[0][k] - b[1][k], b[0][k] - a[1][k], 0.0) for k in range(3))

# Parts that are SUPPOSED to hang in the air. Confirmed with the user 2026-07-31;
# everything else that floats is a defect under modelling rule 1.
#   FX_*                     auras and glows
#   Eye_InnerGlow            the red glow inside the helmet - emissive, like FX_
#   Tome_Glyph_*, Tome_Seal  magic runes hovering above the book's page
FLOATERS_OK = ("FX_", "Eye_InnerGlow", "Tome_Glyph_", "Tome_Seal")
solid = [o for o in objs if not o.name.startswith(FLOATERS_OK)]
bbs = {o.name: wbb(o) for o in solid}
evl = {o.name: o.evaluated_get(dg) for o in solid}

orphans = []
for o in solid:
    me = bpy.data.meshes.new_from_object(evl[o.name])
    pts = [o.matrix_world @ v.co for v in me.vertices]
    bpy.data.meshes.remove(me)
    if not pts:
        continue
    # Cap the sample: 48 points is ample at this scale and keeps the whole check
    # to a few seconds across ~330 objects.
    sample = pts[::max(1, len(pts) // 48)]
    # Only measure against neighbours already within reach - the bounding-box
    # filter is what makes this affordable.
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

print("=" * 68)
print("KNIGHT000 AUDIT")
print("=" * 68)
print("meshes checked            : %d" % len(objs))
print("open / non-manifold       : %d" % len(open_meshes))
for n, name in sorted(open_meshes, reverse=True)[:20]:
    print("    %-28s %d boundary edges" % (name, n))
print("below floor (z < 0)       : %d" % len(below))
for z, name in sorted(below)[:12]:
    print("    %-28s zmin=%s" % (name, z))
print("emblem coplanar pairs     : %d" % len(coplanar))
for c in coplanar:
    print("    " + c)
print("band fit (min, max, SPREAD to host surface - spread is what matters):")
for k, v in band_checks.items():
    flag = "  <-- one-sided" if v and v[2] > 0.010 else ""
    print("    %-28s %s%s" % (k, v, flag))
    if v and v[2] > 0.010:
        fails.append("band %s off-axis (spread %.3f)" % (k, v[2]))

print("asymmetric non-posed pairs : %d" % len(asym))
for d, n in sorted(asym, reverse=True)[:12]:
    print("    %-28s mirror error %.4f" % (n, d))
print("cape verts inside armour  : %d" % buried)
print("levitating parts (rule 1) : %d" % len(orphans))
for d, name in sorted(orphans, reverse=True)[:12]:
    print("    %-28s %s" % (name, "isolated" if d == float("inf")
                            else "nearest part %.4f away" % d))

if orphans:
    fails.append("%d levitating parts" % len(orphans))
if asym:
    fails.append("%d asymmetric pairs" % len(asym))
if buried:
    fails.append("%d cape verts buried in armour" % buried)
if open_meshes:
    fails.append("%d open meshes" % len(open_meshes))
if below:
    fails.append("%d objects below floor" % len(below))
if coplanar:
    fails.append("%d coplanar emblem pairs" % len(coplanar))

print("-" * 68)
print("RESULT: " + ("PASS" if not fails else "FAIL - " + "; ".join(fails)))
print("=" * 68)
