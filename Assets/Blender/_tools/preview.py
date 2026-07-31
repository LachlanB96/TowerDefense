"""Render N variants of a Blender asset in parallel and write a manifest.

    python Assets/Blender/_tools/preview.py knight000
    python Assets/Blender/_tools/preview.py knight000 --variants helmets.json
    python Assets/Blender/_tools/preview.py knight000 --all-views

Runs in SYSTEM Python, not inside Blender. One `blender -b` process per variant:
asset scripts build into bpy.context.scene at module scope and create named
collections, so two builds in one process would collide. Processes are
independent, so three variants cost roughly one build of wall clock.

The manifest is rewritten as each variant lands, not once at the end, so the
gallery fills in column by column instead of staying blank for the whole run.
"""

import argparse
import concurrent.futures
import datetime
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)                    # Assets/Blender
PREVIEW_ROOT = os.path.join(BLENDER_DIR, "_previews~")  # tilde: Unity skips it
BUILD_ONE = os.path.join(HERE, "build_one.py")

BLENDER = os.environ.get(
    "GLOOMFELL_BLENDER",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
)

# What a comparison actually needs: a hero angle, a clean front, and the
# legibility check. The full ten-view set is opt-in via --all-views.
DEFAULT_VIEWS = ["hero_34", "front", "icon_184"]

MAX_JOBS = 4          # each job is a whole Blender; beyond 4 they fight for cores
STDERR_TAIL_LINES = 20

# SAFETY INTERLOCK, not a style marker. Do not relax this into a "warn and
# continue", and do not match on something softer like the word "VARIANT".
#
# A preview exec's the target asset script whole, in-process, inside Blender.
# Eight of the nine blender_*.py scripts in this repo write their real output
# UNCONDITIONALLY at module scope, with no DO_SAVE / DO_EXPORT flag anywhere in
# the file to switch off: seven call both bpy.ops.wm.save_as_mainfile() and
# bpy.ops.export_scene.fbx(), and blender_walk_anim.py exports the FBX. So
# build_one.py's DO_SAVE = False seeding is inert against them: previewing one
# would rebuild the asset from scratch and overwrite the real .blend and .fbx,
# silently, with no undo, over whatever uncommitted work was in them.
#
# The hook block is the only thing a script gains by opting in, and adopting it
# is also when its save/export get put behind flags, so the marker's presence is
# the cheapest reliable proof that a script is safe to drive. Same string in
# build_one.py - keep the two identical.
HOOK_MARKER = "# --- variant hook ---"


def has_variant_hook(script_path):
    """True if `script_path` carries the harness opt-in marker.

    Unreadable counts as "no": refusing is the safe answer, and every caller
    names the offending path in its own message anyway.
    """
    try:
        with open(script_path, encoding="utf-8") as fh:
            return HOOK_MARKER in fh.read()
    except OSError:
        return False


def require_variant_hook(script_path):
    """Refuse, before any Blender starts, to preview a non-conforming script.

    See HOOK_MARKER for why this is a hard stop rather than a warning.
    """
    if has_variant_hook(script_path):
        return
    raise SystemExit(
        "Refusing to preview %s\n"
        "\n"
        "It does not contain the %r block, so it has not opted into the\n"
        "preview harness. Scripts without the hook save and export\n"
        "unconditionally at module scope: running a preview would rebuild the\n"
        "asset and OVERWRITE the real .blend and .fbx. There is no undo.\n"
        "\n"
        "To opt the script in, copy the hook block from\n"
        "Assets/Blender/_tools/_selftest_asset.py to just above its top-level\n"
        "build call, and put its save/export behind DO_SAVE / DO_EXPORT.\n"
        "See CLAUDE.md, \"Preview harness\"."
        % (script_path, HOOK_MARKER)
    )


def audit_target_scripts(audit_script, asset_name):
    """Every asset script an audit script looks like it will exec.

    Audit scripts name their target as a literal path and exec it (see
    _knight000/audit_knight000.py), so reading the source is how we find out
    what one will run. A regex is cruder than importing the module and asking
    it, but importing it means RUNNING it, which is the exact thing being
    gated. Both the convention-implied script and anything else the file
    mentions are included, because --audit must not become a side door around
    require_variant_hook().
    """
    targets = set()
    conventional = os.path.join(BLENDER_DIR, "blender_%s.py" % asset_name)
    if os.path.exists(conventional):
        targets.add(conventional)
    try:
        with open(audit_script, encoding="utf-8") as fh:
            src = fh.read()
    except OSError:
        return sorted(targets)
    for name in re.findall(r"blender_[A-Za-z0-9_]+\.py", src):
        path = os.path.join(BLENDER_DIR, name)
        if os.path.exists(path):
            targets.add(path)
    return sorted(targets)


def audit_hook_refusal(audit_script, asset_name):
    """None if running `audit_script` is safe, else the reason it is not.

    run_audit() spawns Blender on the audit script DIRECTLY, bypassing
    build_one.py, so neither of the other two interlocks covers it.
    audit_knight000.py is safe today - it execs the knight with nothing seeded
    and no `--` argv, so the knight's own _flag() returns False for save and
    export - but the same file for a less careful asset is the identical
    footgun. Callers phrase the refusal themselves: it is fatal for --audit at
    the start of a run, and a red badge in the manifest afterwards.
    """
    bad = [os.path.basename(p) for p in audit_target_scripts(audit_script, asset_name)
           if not has_variant_hook(p)]
    if not bad:
        return None
    return ("%s execs %s, which %s no %r block and so would save and export "
            "over the real asset."
            % (os.path.basename(audit_script), ", ".join(bad),
               "have" if len(bad) > 1 else "has", HOOK_MARKER))


def resolve_asset(asset):
    """Accept either a bare name (knight000) or an explicit script path."""
    if os.path.exists(asset):
        path = os.path.abspath(asset)
        name = os.path.splitext(os.path.basename(path))[0]
        # Tab-completion makes `preview.py Assets/Blender/blender_knight000.py`
        # at least as likely as the bare name, and both must land in the same
        # _previews~/knight000/. A separate "blender_knight000" directory would
        # get its own run counter and its own latest.json, and - being the
        # newest - would head assets.json, so the gallery would follow it and
        # show a single run with no history.
        if name.startswith("blender_"):
            name = name[len("blender_"):]
        return path, name
    path = os.path.join(BLENDER_DIR, "blender_%s.py" % asset)
    if not os.path.exists(path):
        raise SystemExit(
            "No asset script for %r.\nExpected %s, or pass an explicit path."
            % (asset, path)
        )
    return path, asset


def next_run_dir(root, asset_name):
    """Allocate _previews~/<asset>/run-NNN/, NNN monotonic per asset."""
    base = os.path.join(root, asset_name)
    os.makedirs(base, exist_ok=True)
    used = [int(d[4:]) for d in os.listdir(base)
            if d.startswith("run-") and d[4:].isdigit()]
    n = max(used) + 1 if used else 1
    path = os.path.join(base, "run-%03d" % n)
    os.makedirs(path, exist_ok=True)
    return path, n, base


def compute_diffs(variants):
    """Return, per variant, only the vars whose value is not shared by all.

    This is what the gallery captions each column with, so a visual difference
    always has its cause sitting next to it.
    """
    keys = set()
    for v in variants:
        keys |= set(v.get("vars", {}))
    differing = set()
    for k in keys:
        seen = [json.dumps(v.get("vars", {}).get(k), sort_keys=True) for v in variants]
        if len(set(seen)) > 1:
            differing.add(k)
    out = []
    for v in variants:
        d = {k: val for k, val in v.get("vars", {}).items() if k in differing}
        if v.get("patch"):
            d["_patch"] = "(replaces a builder)"
        out.append(d)
    return out


def _atomic_json(target, data):
    """Temp file + replace: the gallery polls once a second and would otherwise
    occasionally read a half-written file.

    On Windows, os.replace onto a file something else has open can raise
    PermissionError [WinError 5]: CPython's open() doesn't request
    FILE_SHARE_DELETE, so the gallery's HTTP server mid-read of latest.json is
    enough to collide. Task 3's gallery polls latest.json once a second on
    this exact machine, so that window is open continuously during every run.
    Retry a few times with a short backoff rather than letting one collision
    abort the whole build; if it's still locked after all attempts, something
    is genuinely wrong and the error should propagate, not be swallowed.
    """
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            os.replace(tmp, target)
            return
        except PermissionError:
            if attempt == attempts:
                raise
            time.sleep(0.05)


def write_manifest(run_dir, asset_base, manifest):
    """Write the run manifest and mirror it to latest.json."""
    _atomic_json(os.path.join(run_dir, "manifest.json"), manifest)
    _atomic_json(os.path.join(asset_base, "latest.json"), manifest)


def write_asset_index(root):
    """List asset dirs, most-recently-built first, at <root>/assets.json.

    The gallery needs this because it cannot scrape a directory listing from the
    root: http.server serves index.html when one is present, so GET / returns
    the gallery page itself.
    """
    entries = []
    for name in os.listdir(root):
        latest = os.path.join(root, name, "latest.json")
        if os.path.exists(latest):
            entries.append((os.path.getmtime(latest), name))
    entries.sort(reverse=True)
    _atomic_json(os.path.join(root, "assets.json"), [n for _, n in entries])


def run_audit(asset_name):
    """Run <asset>'s audit script, if it has one, and return its verdict line.

    Convention: Assets/Blender/_<asset>/audit_<asset>.py, which is where
    audit_knight000.py already lives. Assets without one simply return None.
    """
    script = os.path.join(BLENDER_DIR, "_%s" % asset_name, "audit_%s.py" % asset_name)
    if not os.path.exists(script):
        return None
    # Second half of the interlock. run() refuses up front too, but this path
    # spawns Blender on the audit script itself - not via build_one.py - so it
    # needs its own gate rather than inheriting anyone else's.
    refusal = audit_hook_refusal(script, asset_name)
    if refusal:
        # "FAIL" is what the gallery colours the badge red on, so the refusal
        # is as visible as a genuine audit failure rather than blending in.
        return "FAIL - audit skipped: " + refusal
    try:
        proc = subprocess.run([BLENDER, "-b", "-P", script],
                              capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return "audit timed out"
    lines = [l for l in (proc.stdout or "").splitlines()
             if "PASS" in l or "FAIL" in l]
    return lines[-1].strip() if lines else "audit produced no verdict"


def build_variant(script, spec, out_dir, views, sample_scale, timeout):
    """Run one Blender process. Returns the finished variant record fields."""
    os.makedirs(out_dir, exist_ok=True)

    payload = dict(spec.get("vars", {}))
    if spec.get("patch"):
        payload["_patch"] = spec["patch"]
    if views is not None:
        payload["RENDER_ONLY"] = list(views)
    payload["SAMPLE_SCALE"] = sample_scale

    vpath = os.path.join(out_dir, "_variant.json")
    with open(vpath, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    started = time.time()
    try:
        proc = subprocess.run(
            [BLENDER, "-b", "-P", BUILD_ONE, "--",
             "--script", script, "--variant", vpath, "--out", out_dir],
            capture_output=True, text=True, timeout=timeout,
        )
        code, err = proc.returncode, proc.stderr or ""
    except subprocess.TimeoutExpired:
        # A wedged Blender must not strand the whole run.
        code, err = "timeout", "killed after %ss" % timeout

    # build_one writes this even when the build raises; it is AUTHORITATIVE
    # over the exit code, which Blender does not report reliably for a -P
    # script (build_one.py says so outright). That has to cut both ways: a
    # build that finished and rendered but hit a nonzero exit on the way out
    # (teardown noise, not a real failure) must be upgraded back to success,
    # not just downgraded when it lies about being fine.
    status_path = os.path.join(out_dir, "_build.json")
    if os.path.exists(status_path):
        try:
            with open(status_path, encoding="utf-8") as fh:
                status = json.load(fh)
            if status.get("ok"):
                code = 0
            else:
                err = status.get("error", err)
                code = code or 1
        except (OSError, ValueError) as exc:
            # _build.json IS the success signal here; failing to parse it
            # must count as a failure, not silently fall through as ok.
            code = code or 1
            err = err or "unreadable _build.json: %r" % exc
    elif code == 0:
        # Blender exited clean without the bootstrap finishing: it died early.
        code, err = 1, err or "build_one.py never wrote _build.json"

    renders = sorted(
        f for f in os.listdir(out_dir)
        if f.endswith(".png")
    ) if os.path.isdir(out_dir) else []

    if code == 0 and not renders:
        # A build that produced no image is not a success, whatever the exit
        # code and _build.json say. The realistic cause is a view name that no
        # render_view() call in the script actually uses - a typo in --views,
        # or DEFAULT_VIEWS (knight-shaped names) meeting an asset that names
        # its views differently. RENDER_ONLY then matches nothing, the build
        # "succeeds", and the gallery shows a column with a label, a diff and a
        # duration but no pictures, which reads as a gallery bug rather than as
        # the caller's typo. Route it to the red-card path instead.
        #
        # Appended AFTER any existing stderr, not prepended: stderr_tail keeps
        # only the LAST STDERR_TAIL_LINES lines, so a message put first would
        # be the first thing trimmed away.
        code = 1
        err = (err.rstrip() + "\n\nno .png was produced, so this build is "
               "recorded as a failure.\nRequested views: %s\nCheck those "
               "against the render_view() names in %s."
               % (", ".join(views) if views else "(all views)",
                  os.path.basename(script))).strip()

    tail = "\n".join(err.strip().splitlines()[-STDERR_TAIL_LINES:])
    return {
        "exit": code,
        "seconds": round(time.time() - started, 1),
        "renders": [os.path.basename(out_dir) + "/" + r for r in renders],
        "stderr_tail": "" if code == 0 else tail,
    }


def run(asset, variants=None, views=None, sample_scale=0.5, timeout=180,
        jobs=MAX_JOBS, root=None, all_views=False, audit=False):
    """Build every variant in parallel. Returns the completed manifest."""
    script, asset_name = resolve_asset(asset)
    # Before anything: no Blender launched, no run directory allocated, nothing
    # on disk touched. See HOOK_MARKER.
    require_variant_hook(script)
    if audit:
        # Checked here as well as inside run_audit() so that --audit fails
        # before a 15 s build rather than after it.
        refusal = audit_hook_refusal(
            os.path.join(BLENDER_DIR, "_%s" % asset_name, "audit_%s.py" % asset_name),
            asset_name)
        if refusal:
            raise SystemExit("Refusing to run --audit: " + refusal)
    variants = variants or [{"label": "default"}]
    if all_views:
        views = None
    elif views is None:
        views = DEFAULT_VIEWS

    root = root or PREVIEW_ROOT
    run_dir, run_n, asset_base = next_run_dir(root, asset_name)
    diffs = compute_diffs(variants)

    manifest = {
        "asset": asset_name,
        "run": run_n,
        "started": datetime.datetime.now().isoformat(timespec="seconds"),
        "done": False,
        "audit": None,
        "variants": [
            {
                "n": i + 1,
                "label": v.get("label", "v%d" % (i + 1)),
                "diff": diffs[i],
                "renders": [],
                "exit": None,          # null == still building
                "seconds": None,
                "stderr_tail": "",
            }
            for i, v in enumerate(variants)
        ],
    }
    write_manifest(run_dir, asset_base, manifest)
    write_asset_index(root)
    print("run %d -> %s" % (run_n, run_dir))

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(jobs, len(variants))) as pool:
        futures = {}
        for i, spec in enumerate(variants):
            out_dir = os.path.join(run_dir, "v%d" % (i + 1))
            futures[pool.submit(build_variant, script, spec, out_dir,
                                views, sample_scale, timeout)] = i
        for fut in concurrent.futures.as_completed(futures):
            i = futures[fut]
            try:
                manifest["variants"][i].update(fut.result())
            except Exception as exc:                        # noqa: BLE001
                manifest["variants"][i].update(
                    {"exit": 1, "stderr_tail": "runner error: %r" % exc})
            v = manifest["variants"][i]
            print("  v%d %-16s exit=%s %ss" % (v["n"], v["label"], v["exit"], v["seconds"]))
            # Rewritten on every completion so the gallery fills in as it goes.
            write_manifest(run_dir, asset_base, manifest)

    if audit:
        # Run level, not per variant - see the schema note above.
        manifest["audit"] = run_audit(asset_name)
        print("  audit: %s" % manifest["audit"])

    manifest["done"] = True
    write_manifest(run_dir, asset_base, manifest)
    return manifest


def load_variants(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise SystemExit("%s must contain a JSON list of variant objects." % path)
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("asset", help="asset name (knight000) or script path")
    ap.add_argument("--variants", help="JSON file: list of {label, vars, patch}")
    ap.add_argument("--views", help="comma-separated view names to render")
    ap.add_argument("--all-views", action="store_true",
                    help="render the asset's full view set, not the cheap subset")
    ap.add_argument("--samples", type=float, default=0.5,
                    help="sample-count multiplier (default 0.5)")
    ap.add_argument("--jobs", type=int, default=MAX_JOBS)
    ap.add_argument("--audit", action="store_true",
                    help="also run _<asset>/audit_<asset>.py and record its verdict")
    a = ap.parse_args()

    if not os.path.exists(BLENDER):
        raise SystemExit("Blender not found at %s (set GLOOMFELL_BLENDER)" % BLENDER)

    manifest = run(
        asset=a.asset,
        variants=load_variants(a.variants) if a.variants else None,
        views=a.views.split(",") if a.views else None,
        all_views=a.all_views,
        sample_scale=a.samples,
        jobs=a.jobs,
        audit=a.audit,
    )
    failed = [v for v in manifest["variants"] if v["exit"] != 0]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
