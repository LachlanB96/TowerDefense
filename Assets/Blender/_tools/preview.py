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
import contextlib
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)                    # Assets/Blender
PREVIEW_ROOT = os.path.join(BLENDER_DIR, "_previews~")  # tilde: Unity skips it
BUILD_ONE = os.path.join(HERE, "build_one.py")

BLENDER = os.environ.get(
    "GLOOMFELL_BLENDER",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
)

# ESCAPE HATCH FOR THE OPENGL DRIVER FAULT. Unset by default, which leaves Blender on
# its own default backend (OpenGL here). Set GLOOMFELL_GPU_BACKEND=vulkan to render
# EEVEE through Vulkan instead - it does not load nvoglv64.dll at all, which is the DLL
# that faulted on 2026-08-11 (EXCEPTION_ACCESS_VIOLATION, in Blender's own crash file).
#
# MEASURED before offering it, on this asset, same two orbit cells, warm:
#   opengl  7.8-8.1 s      vulkan  14.2-14.4 s      -> Vulkan is ~1.8x slower
#   pixels differ on 2.3% of the frame, max delta 24/255, mean |d| ~1.0
#
# That second line is why this is NOT the default: it is well above the 1-2/255
# shader-rounding signature, so switching backends MOVES THE BASELINE. Every stored
# champion and every past verdict was rendered under OpenGL, and a cross-backend
# comparison measures the backend as well as the model. If you switch, re-render the
# champion first and treat it as a new baseline era - the same discipline as a bake.
#
# Order of remedies, cheapest first: update the GPU driver (the fault is IN the driver,
# and OpenGL on Windows ships as part of it - there is no separate GL package); then
# RENDER_SLOTS=1, already the default below; then this.
GPU_BACKEND = os.environ.get("GLOOMFELL_GPU_BACKEND", "").strip().lower()
BACKEND_ARGS = ["--gpu-backend", GPU_BACKEND] if GPU_BACKEND in ("opengl", "vulkan") else []

# What a comparison actually needs: a hero angle, a clean front, and the
# legibility check. The full ten-view set is opt-in via --all-views.
DEFAULT_VIEWS = ["hero_34", "front", "icon_184"]

MAX_JOBS = 4          # each job is a whole Blender; beyond 4 they fight for cores
STDERR_TAIL_LINES = 20

# Machine-wide cap on concurrent Blender builds, across every process that
# calls this module. Several modeller agents may run preview.py at once, and
# each call can itself spawn up to MAX_JOBS Blenders - without a cap the box
# thrashes and every render finishes slower than if they had queued.
#
# This lives here rather than in the agents' instructions on purpose: it is a
# machine-resource constraint, and an instruction is something an agent can
# forget while a semaphore is not.
# Default lowered 3 -> 2 on 2026-08-02 after the user's machine froze for about a
# minute mid-session. EEVEE is GPU-resident and this rig renders with raytracing,
# shadows and volumetric shadows on, so each slot is a live GPU context - and Unity
# and the browser gallery are holding their own at the same time. Three concurrent
# raytraced contexts is enough to trip Windows TDR, which resets the display driver
# and looks exactly like a freeze. A render is only ~7 s, so serialising costs a few
# seconds of wall-clock against the many minutes a modeller spends thinking; the
# throughput was never worth the risk of taking the desktop down.
#
# Set GLOOMFELL_RENDER_SLOTS=1 if it ever recurs, or 3+ on a machine with headroom.
#
# 2026-08-11: IT RECURRED, AND THE DEFAULT IS NOW 1. Blender's own crash report
# (%TEMP%\blender.crash.txt) records EXCEPTION_ACCESS_VIOLATION in nvoglv64.dll - the
# NVIDIA OpenGL driver - during a four-maker fleet run. Note Windows logged NOTHING:
# no Application error, no TDR event, no driver reset. Blender catches the fault and
# writes its own file, so the event log is not where this shows up. Look for
# blender.crash.txt before concluding a wave died of anything else.
#
# The measurements say serialising is nearly free here, because concurrency was never
# where the time went. Per cell on this rig: ~5.2 s Blender startup + model build,
# ~6.9 s for the first render (shader compilation), then only ~1.3 s per extra
# view+mask. A 6-view cell is ~18.7 s and an 8-cell wave ~150 s. Sample count barely
# registers - x0.5 and x0.25 timed identically - so turning quality DOWN buys nothing
# and costs fidelity. The GPU is not short of memory either: peak VRAM over idle is
# ~200 MB against 16 GB, and peak host RSS is ~877 MB per Blender.
#
# So the trade is: one live GPU context instead of two, for roughly one extra minute
# per wave, against a driver fault that takes the whole desktop with it. Raise it back
# with GLOOMFELL_RENDER_SLOTS=2 on a machine that proves stable.
RENDER_SLOTS = int(os.environ.get("GLOOMFELL_RENDER_SLOTS", "1"))


@contextlib.contextmanager
def render_slot(timeout):
    """Hold one of RENDER_SLOTS build slots for the duration of the block.

    Implemented with mkdir, which is atomic on every platform we care about, so
    whichever process creates the directory owns that slot. Slots are reclaimed
    by age rather than by checking whether the owning PID is alive: PID liveness
    is platform-specific and a stale slot only costs throughput, never
    correctness.

    The lock lives in the system temp dir, NOT under the previews root
    (changed 2026-08-02). It used to be <root>/.render-slots, which made the
    "machine-wide" cap secretly per---root: a modeller agent that forgot
    --root fell back to its worktree's own _previews~, got a private pool of
    RENDER_SLOTS slots, and silently exited the cap - two such agents plus two
    compliant ones is the 3+-GPU-context TDR freeze the cap exists to prevent.
    A fixed location is what makes the semaphore exclude every process
    regardless of where their output goes.
    """
    slot_dir = os.path.join(tempfile.gettempdir(), "gloomfell-render-slots")
    os.makedirs(slot_dir, exist_ok=True)
    stale_after = timeout + 60
    # Never block a build forever over a scheduling nicety - if the pool stays
    # full past this, run anyway and accept the contention.
    deadline = time.time() + stale_after
    mine = None
    while mine is None and time.time() < deadline:
        for i in range(max(1, RENDER_SLOTS)):
            path = os.path.join(slot_dir, "slot-%d" % i)
            try:
                os.mkdir(path)
                mine = path
                break
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(path) > stale_after:
                        shutil.rmtree(path, ignore_errors=True)
                except OSError:
                    pass
        if mine is None:
            time.sleep(0.5)
    try:
        yield
    finally:
        if mine:
            shutil.rmtree(mine, ignore_errors=True)

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
    """Allocate _previews~/<asset>/run-NNN/, NNN monotonic per asset.

    os.mkdir (no exist_ok) is the atomic claim: with several maker agents
    rendering the same asset concurrently, whoever creates the directory owns
    that number and a loser simply takes the next one. The old makedirs
    (exist_ok=True) body handed two concurrent callers the same directory.
    """
    base = os.path.join(root, asset_name)
    os.makedirs(base, exist_ok=True)
    used = [int(d[4:]) for d in os.listdir(base)
            if d.startswith("run-") and d[4:].isdigit()]
    n = max(used) + 1 if used else 1
    while True:
        path = os.path.join(base, "run-%03d" % n)
        try:
            os.mkdir(path)
            return path, n, base
        except FileExistsError:
            n += 1


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


def warm_render_pipeline(script, spec, views, timeout):
    """Render one throwaway cell so every real cell of a wave starts equally warm.

    WHY THIS EXISTS - measured 2026-08-11, and it silently corrupted verdicts.

    Each cell is its own Blender process, so the state that matters is the machine's:
    the GPU driver's on-disk shader cache. The FIRST concurrency batch of a wave hits
    that cache cold and renders differently from the rest of its own wave. Measured on
    evilMage000 run 19 vs an identical re-render (same wave file, no seed re-derivation,
    same script_sha): cells v1 and v3 - the first two launched at jobs=2 - differed by
    426k-435k pixels at max delta 185-232 of 255, while all six later cells were
    BIT-IDENTICAL. The renderer is otherwise perfectly deterministic, so this is not
    sampling noise.

    It is severe rather than untidy because **cell 1 is always the incumbent baseline**.
    The artefact therefore lands precisely on the reference that every chip measures
    against (`_iou_vs_base`, the inert gate, the INV chips) and that every judge sees as
    the champion. It produced a physically impossible reading in the wild: a clause that
    only SHORTENS blades topping out at z <= 0.76 appeared to brighten the torso band by
    |dL| p50 0.728.

    One cheap render ahead of the pool populates the cache, so the wave's own cells are
    all on the same footing. Cost is a few seconds per wave against the cost of a wave
    whose baseline is wrong, which is every verdict in it.

    Deliberately NOT a fix by re-rendering the whole wave twice and keeping the second:
    that doubles GPU time on every wave forever, where this pays once.
    """
    tmp = tempfile.mkdtemp(prefix="gf_warm_")
    try:
        # One view is enough to compile the shaders; the pixels are thrown away. Keep
        # the same script and the same variant so the warmed shaders are the ones the
        # real cells will use.
        warm_views = list(views)[:1] if views else None
        build_variant(script, spec, tmp, warm_views, 0.05, timeout)
    except Exception as exc:                                # noqa: BLE001
        # A warmup failure must never fail the wave - the wave is still renderable,
        # just possibly cold. Say so rather than dying.
        print("  (warmup skipped: %r)" % exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
    # The slot is taken around the Blender call only - not around the JSON
    # bookkeeping above - so a queued build holds nothing while it waits.
    try:
        with render_slot(timeout):
            proc = subprocess.run(
                [BLENDER] + BACKEND_ARGS + ["-b", "-P", BUILD_ONE, "--",
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
        jobs=MAX_JOBS, root=None, all_views=False, audit=False, tag=None, seed=None,
        wave=None, design=None):
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
        # Who asked for this run, and under which stimulus draw.
        #
        # Attribution used to be self-reported ("report your run directory"), which
        # failed exactly when it mattered: an agent that died after rendering left an
        # unattributable run, and the log's own note records that "the newest run at
        # any moment is usually not the attempt". Measured: 403 run directories against
        # 84 logged attempts. Stamping it here makes it a fact rather than a promise.
        #
        # `seed` is the orbit draw (see _tools/orbit.py). Recording it is what makes a
        # past verdict re-checkable: replay the seed and you reproduce the exact
        # stimulus the judgement was formed against.
        "tag": tag,
        "seed": seed,
        # Hash of the asset script this wave was built from. Cell 1 of a wave is the
        # design's untouched baseline, so it reproduces the ORIGIN inside this wave's own
        # draw - but only while the script itself is unchanged. When it changes, that
        # equivalence quietly stops holding and the ratchet would compare two different
        # models and call the difference progress. Recording the hash makes the moment
        # detectable instead of silent.
        "script_sha": _script_sha(script),
        # The full drawn condition, not just its seed, so a verdict can be replayed
        # without re-deriving anything.
        "wave": wave,
        "variants": [
            {
                "n": i + 1,
                "label": v.get("label", "v%d" % (i + 1)),
                # Which clauses are ON in this cell. Without it, attributability - the
                # entire reason axis.py exists - survives only as an English label.
                "clauses": v.get("_clauses"),
                # Always present, filled in later when a wave produced them. A field
                # that appears only sometimes is one every reader has to guess about.
                "sheet": None,
                "chips": None,
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

    # Warm the shader cache BEFORE the pool, so cell 1 - always the incumbent baseline -
    # is not the one cell rendered cold. See warm_render_pipeline().
    warm_render_pipeline(script, variants[0], views, timeout)

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

    # Contact sheet per cell, and chips against the baseline cell.
    #
    # Both used to be separate manual invocations and both were skipped on the first
    # real run of the loop. That is the whole argument for doing them here: an unrun
    # chip is indistinguishable from a clean one, and handing a judge six loose PNGs
    # instead of one sheet is exactly the mismatched-pair failure the sheet exists to
    # prevent. Neither can fail the run - presentation and measurement must never cost
    # a build that already succeeded.
    if wave:
        sys.path.insert(0, HERE)
        try:
            import orbit as _orbit
            for v in manifest["variants"]:
                vd = os.path.join(run_dir, "v%d" % v["n"])
                if os.path.isdir(vd) and _orbit.sheet(vd, os.path.join(vd, "_sheet.png")):
                    v["sheet"] = "v%d/_sheet.png" % v["n"]
        except Exception as e:
            print("  sheet: skipped (%s)" % e)
        try:
            import chips as _chips
            # axis.py always emits the all-clauses-off cell first, so v1 is the
            # in-wave baseline every other cell is measured against.
            base_dir = os.path.join(run_dir, "v1")
            base = _chips.measure(base_dir)
            for v in manifest["variants"]:
                vd = os.path.join(run_dir, "v%d" % v["n"])
                if v["n"] == 1 or not os.path.isdir(vd):
                    continue
                meas = _chips.measure(vd)
                if "error" not in meas:
                    meas["_iou_vs_base"] = _chips.iou_vs(vd, base_dir)
                    # BOTH halves, or the inert gate is shape-only again. iou_vs asks
                    # "did the outline move"; changed_vs asks "would a judge see
                    # anything". Without this second line every material, colour and
                    # emission design chips `inert` and is bounced before any judge -
                    # which is the bug chips.changed_vs() was written to fix. It was
                    # missed here first time round because the fix was verified through
                    # chips.py's CLI, which sets it, and not through this path, which is
                    # the one the pipeline actually uses.
                    meas["_changed_vs_base"] = _chips.changed_vs(vd, base_dir)
                v["chips"] = _chips.chips(meas, base)
                for c in v["chips"]:
                    print("  v%d [%s] %s" % (v["n"], c["chip"], c["detail"][:88]))

            # Wave-level integrity. A driver fault does not always crash: it can render a
            # garbage frame that exits 0 and yields a believable number. Every cell here
            # is the same model under the same camera, so each view column is a tight
            # distribution and a corrupt frame is a gross outlier against its own column.
            # Loud on purpose - a silent corruption gets believed.
            bad = _chips.frame_integrity(run_dir)
            manifest["integrity"] = bad
            for b in bad:
                print("  !! CORRUPT FRAME %s/%s  mean %.4f vs column median %.4f (%.0f%% off)"
                      % (b["cell"], b["view"], b["mean"], b["column_median"],
                         100 * b["deviation"]))
        except Exception as e:
            print("  chips: skipped (%s)" % e)

    # Open the durable record for this wave, from the manifest, before anything judges
    # it. The first real run of the loop wrote no record at all; an attempt that dies
    # before judging must still leave a line, or an abandoned wave is indistinguishable
    # from one that never happened.
    if wave and design:
        try:
            import record as _rec
            _rec.open_attempt(asset_name, run_n, design, root=root)
            print("  recorded: design %s" % design)
        except Exception as e:
            print("  record: skipped (%s)" % e)

    if audit:
        # Run level, not per variant - see the schema note above.
        manifest["audit"] = run_audit(asset_name)
        print("  audit: %s" % manifest["audit"])

    manifest["done"] = True
    write_manifest(run_dir, asset_base, manifest)
    return manifest


def _script_sha(path):
    """Short sha256 of the asset script, or None if it cannot be read."""
    import hashlib
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:12]
    except OSError:
        return None


def load_variants(path):
    """Read a variants file. Accepts a bare list, or axis.py's {wave, cells} envelope.

    Returns (cells, wave). `wave` carries the orbit draw that produced the EXTRA_VIEWS
    baked into the cells, so the seed no longer has to be re-typed on the command line -
    which was a real hazard: a typo produced a manifest claiming one stimulus while the
    images were rendered under another, silently, and the seed is the only thing that
    makes a verdict replayable.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "cells" in data:
        return data["cells"], data.get("wave")
    if not isinstance(data, list):
        raise SystemExit("%s must contain a JSON list of variant objects, or an "
                         "axis.py {wave, cells} object." % path)
    return data, None


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
    # A modeller agent working in a git worktree has its own _previews~ that the
    # gallery is not watching. --root points its renders back at the real one so
    # the user sees the work as it happens.
    ap.add_argument("--root", help="preview output root (default: the repo's _previews~)")
    ap.add_argument("--tag", help="who is rendering this; stamped into manifest.json "
                                  "so the run is attributable without self-reporting")
    ap.add_argument("--design", help="design id; opens a record line for this wave")
    ap.add_argument("--seed", type=int, help="orbit stimulus seed; stamped into "
                                             "manifest.json so a verdict is replayable")
    a = ap.parse_args()

    if not os.path.exists(BLENDER):
        raise SystemExit("Blender not found at %s (set GLOOMFELL_BLENDER)" % BLENDER)

    cells, wave = load_variants(a.variants) if a.variants else (None, None)
    seed = a.seed
    if wave:
        # The wave file is authoritative: it is what the images were actually rendered
        # under. A --seed that disagrees is a typo, and a typo here is unrecoverable
        # after the fact, so refuse rather than pick one.
        if seed is not None and seed != wave.get("seed"):
            raise SystemExit(
                "--seed %s disagrees with the wave file's seed %s. The wave file is what "
                "the cells were built from; drop --seed, or regenerate the wave."
                % (seed, wave.get("seed")))
        seed = wave.get("seed")

    manifest = run(
        asset=a.asset,
        variants=cells,
        views=a.views.split(",") if a.views else None,
        all_views=a.all_views,
        sample_scale=a.samples,
        jobs=a.jobs,
        audit=a.audit,
        root=os.path.abspath(a.root) if a.root else None,
        tag=a.tag,
        seed=seed,
        wave=wave,
        design=a.design,
    )
    failed = [v for v in manifest["variants"] if v["exit"] != 0]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
