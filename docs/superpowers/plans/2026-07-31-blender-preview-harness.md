# Blender Preview Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a harness that renders N variants of a Blender asset in parallel and shows them, numbered and auto-refreshing, in a browser tab — so model changes are visible as they happen and alternatives can be compared side by side.

**Architecture:** A system-Python runner (`preview.py`) spawns one headless `blender -b` process per variant, each running an in-Blender bootstrap (`build_one.py`) that seeds a `VARIANT` dict into a namespace and `exec`s the asset script. Renders and an incrementally-rewritten `manifest.json` land in a per-run directory served by a stock `http.server`; a single static `index.html` polls the manifest and re-renders.

**Tech Stack:** Python 3.13 (stdlib only — `subprocess`, `json`, `argparse`, `concurrent.futures`, `http.server`), Blender 5.1 headless, vanilla HTML/CSS/JS (no build step, no dependencies).

## Global Constraints

- **Blender executable:** `C:\Program Files\Blender Foundation\Blender 5.1\blender.exe`. Overridable via the `GLOOMFELL_BLENDER` environment variable. Never hard-code a different path.
- **Headless CLI only.** Never drive a build through the Blender MCP tools. MCP froze Blender permanently on 2026-07-30 and `TaskStop` cannot interrupt a blocked Blender thread.
- **Scene reset idiom:** `bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)`. Never `read_factory_settings`, which is blocked in the MCP sandbox.
- **Stdlib only.** No pip installs, no npm, no CDN links. The gallery must work offline from `file://`-adjacent local serving.
- **Preview builds are non-destructive.** `DO_SAVE` and `DO_EXPORT` stay false for every variant build. `knight000.blend` and `knight000.fbx` must never be written by a preview run.
- **Preview output goes to `Assets/Blender/_previews~/`** — trailing tilde mandatory, so Unity skips the directory instead of importing every scratch PNG.
- **Comment style:** this repo wants human-readable comments explaining *why* and flagging gotchas. Match the density of `blender_knight000.py`.
- **Line endings:** the repo is CRLF-on-checkout. Write files normally; do not add `.gitattributes` entries.

---

### Task 1: In-Blender bootstrap + a fast self-test asset

The bootstrap is the piece everything else depends on, so it gets its own test asset: a red cube that builds and renders in about a second. Every later task tests against this instead of the 15-second knight.

**Files:**
- Create: `Assets/Blender/_tools/_selftest_asset.py`
- Create: `Assets/Blender/_tools/build_one.py`
- Test: `Assets/Blender/_tools/selftest.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - CLI contract: `blender -b -P _tools/build_one.py -- --script <path> --variant <json-path> --out <dir>`
  - Writes `<out>/_build.json` — `{"ok": true}` on success, `{"ok": false, "error": "<traceback>"}` on failure. **Task 2 reads this file**; it does not rely on Blender's exit code, which is unreliable for `sys.exit` inside a `-P` script.
  - The **variant hook block** (the 6 lines under `# --- variant hook ---`), copied verbatim into any asset script that opts in. Task 4 copies it into `blender_knight000.py`.
  - Variant JSON shape: a flat dict of globals to override, optionally with a `_patch` key holding Python source.

- [ ] **Step 1: Write the failing test**

Create `Assets/Blender/_tools/selftest.py`. Plain Python, no pytest — the repo has no test framework and this must not introduce one.

```python
"""Self-test for the Blender preview harness.

Run:  python Assets/Blender/_tools/selftest.py

Exercises the harness against `_selftest_asset.py` (a red cube that builds in
about a second) rather than a real character, so the whole thing runs in a few
seconds and does not depend on any asset staying still.

Exit code 0 = all passed. Any failure prints a diff-style report and exits 1.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = os.environ.get(
    "GLOOMFELL_BLENDER",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
)
ASSET = os.path.join(HERE, "_selftest_asset.py")
BUILD_ONE = os.path.join(HERE, "build_one.py")

_failures = []


def check(label, cond, detail=""):
    if cond:
        print("  PASS  " + label)
    else:
        print("  FAIL  " + label + ("\n        " + detail if detail else ""))
        _failures.append(label)


def run_build_one(variant, out):
    """Invoke the in-Blender bootstrap once. Returns (returncode, stderr)."""
    os.makedirs(out, exist_ok=True)
    vpath = os.path.join(out, "_variant.json")
    with open(vpath, "w", encoding="utf-8") as fh:
        json.dump(variant, fh)
    proc = subprocess.run(
        [BLENDER, "-b", "-P", BUILD_ONE, "--",
         "--script", ASSET, "--variant", vpath, "--out", out],
        capture_output=True, text=True, timeout=180,
    )
    return proc.returncode, proc.stderr


def test_bootstrap_renders():
    print("test_bootstrap_renders")
    tmp = tempfile.mkdtemp(prefix="gf_selftest_")
    try:
        run_build_one({}, tmp)
        status_path = os.path.join(tmp, "_build.json")
        check("_build.json written", os.path.exists(status_path))
        if os.path.exists(status_path):
            with open(status_path, encoding="utf-8") as fh:
                status = json.load(fh)
            check("build reported ok", status.get("ok") is True,
                  str(status.get("error", ""))[:400])
        check("front.png rendered", os.path.exists(os.path.join(tmp, "front.png")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_variant_overrides_a_constant():
    """A VARIANT key must beat the script's own default assignment."""
    print("test_variant_overrides_a_constant")
    big = tempfile.mkdtemp(prefix="gf_selftest_big_")
    small = tempfile.mkdtemp(prefix="gf_selftest_small_")
    try:
        run_build_one({"CUBE_SIZE": 2.0}, big)
        run_build_one({"CUBE_SIZE": 0.5}, small)
        a = os.path.join(big, "front.png")
        b = os.path.join(small, "front.png")
        check("both variants rendered", os.path.exists(a) and os.path.exists(b))
        if os.path.exists(a) and os.path.exists(b):
            check("CUBE_SIZE changed the image",
                  open(a, "rb").read() != open(b, "rb").read(),
                  "identical bytes - the override did not reach the build")
    finally:
        shutil.rmtree(big, ignore_errors=True)
        shutil.rmtree(small, ignore_errors=True)


def test_patch_can_call_script_helpers():
    """_patch source must bind to the SCRIPT's globals, not the runner's.

    This is the failure mode the hook exists to prevent: a replacement builder
    that cannot see the script's own helpers dies deep in the build with an
    error that looks nothing like its cause.
    """
    print("test_patch_can_call_script_helpers")
    tmp = tempfile.mkdtemp(prefix="gf_selftest_patch_")
    try:
        patch = (
            "def build_asset():\n"
            "    # calls a helper defined in the asset script, not in the runner\n"
            "    add_cube_at(0.0, 0.0, 1.5)\n"
        )
        run_build_one({"_patch": patch}, tmp)
        status_path = os.path.join(tmp, "_build.json")
        ok = False
        if os.path.exists(status_path):
            with open(status_path, encoding="utf-8") as fh:
                status = json.load(fh)
            ok = status.get("ok") is True
            detail = str(status.get("error", ""))[:400]
        else:
            detail = "no _build.json"
        check("_patch replaced the builder and ran", ok, detail)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_broken_variant_reports_error():
    """A build that raises must report cleanly, not vanish."""
    print("test_broken_variant_reports_error")
    tmp = tempfile.mkdtemp(prefix="gf_selftest_broken_")
    try:
        run_build_one({"_patch": "raise RuntimeError('deliberate selftest failure')"}, tmp)
        status_path = os.path.join(tmp, "_build.json")
        check("_build.json written even on failure", os.path.exists(status_path))
        if os.path.exists(status_path):
            with open(status_path, encoding="utf-8") as fh:
                status = json.load(fh)
            check("ok is False", status.get("ok") is False)
            check("traceback captured",
                  "deliberate selftest failure" in str(status.get("error", "")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


TESTS = [
    test_bootstrap_renders,
    test_variant_overrides_a_constant,
    test_patch_can_call_script_helpers,
    test_broken_variant_reports_error,
]


def main():
    if not os.path.exists(BLENDER):
        print("Blender not found at " + BLENDER)
        print("Set GLOOMFELL_BLENDER to override.")
        return 2
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for fn in TESTS:
        if only and only not in fn.__name__:
            continue
        fn()
    print()
    if _failures:
        print("FAILED: " + ", ".join(_failures))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python Assets/Blender/_tools/selftest.py
```

Expected: every test FAILs — `_build.json written` fails because neither `build_one.py` nor `_selftest_asset.py` exists yet, so Blender exits without writing anything.

- [ ] **Step 3: Write the self-test asset**

Create `Assets/Blender/_tools/_selftest_asset.py`. This doubles as the **reference example** of a conforming asset script — it is the shortest complete statement of the convention.

```python
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
    mat.use_nodes = True
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
```

- [ ] **Step 4: Write the bootstrap**

Create `Assets/Blender/_tools/build_one.py`.

```python
"""Runs INSIDE Blender. Seeds a namespace and execs a conforming asset script.

    blender -b -P _tools/build_one.py -- \
        --script Assets/Blender/blender_knight000.py \
        --variant path/to/variant.json \
        --out    path/to/out/dir

Why a bootstrap rather than running the asset script directly: the asset script
has no way to receive a variant dict from the command line, and we do not want
to teach every script an argument parser. Pre-seeding a namespace and exec'ing
is the pattern _knight000/audit_knight000.py already uses.
"""

import argparse
import json
import os
import sys
import traceback


def parse_args():
    # Blender swallows everything before "--"; our flags live after it.
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True, help="asset script to exec")
    ap.add_argument("--variant", required=True, help="JSON file of overrides")
    ap.add_argument("--out", required=True, help="render output directory")
    return ap.parse_args(argv)


def main():
    a = parse_args()
    os.makedirs(a.out, exist_ok=True)
    status_path = os.path.join(a.out, "_build.json")

    with open(a.variant, encoding="utf-8") as fh:
        variant = dict(json.load(fh))

    # RENDER_DIR rides in VARIANT, not just in the seeded namespace. Asset
    # scripts assign RENDER_DIR themselves near the top of the file, which would
    # clobber a plain seed; VARIANT is applied at the hook, after that
    # assignment and before any render call reads it.
    variant["RENDER_DIR"] = a.out
    variant.setdefault("DO_RENDER", True)

    # Previews are strictly non-destructive: never touch the real .blend or FBX.
    variant["DO_SAVE"] = False
    variant["DO_EXPORT"] = False

    ns = {
        "__name__": "__main__",
        "__file__": a.script,
        "VARIANT": variant,
        # Seeded as well as passed via VARIANT so that scripts using the
        # _flag() idiom (which reads globals() at import time, before the hook
        # runs) also see the right values.
        "RENDER_DIR": a.out,
        "DO_RENDER": True,
        "DO_SAVE": False,
        "DO_EXPORT": False,
    }

    with open(a.script, encoding="utf-8") as fh:
        src = fh.read()

    try:
        exec(compile(src, a.script, "exec"), ns)
    except Exception:
        # Written rather than raised: Blender's exit code for an exception in a
        # -P script is not reliable enough to be the only channel, and the
        # runner needs the traceback text regardless.
        with open(status_path, "w", encoding="utf-8") as fh:
            json.dump({"ok": False, "error": traceback.format_exc()}, fh, indent=2)
        traceback.print_exc()
        return 3

    with open(status_path, "w", encoding="utf-8") as fh:
        json.dump({"ok": True}, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
python Assets/Blender/_tools/selftest.py
```

Expected: PASS on all four tests in `test_bootstrap_renders`, `test_variant_overrides_a_constant`, `test_patch_can_call_script_helpers`, `test_broken_variant_reports_error`.

If `test_variant_overrides_a_constant` reports "identical bytes", the hook is running in the wrong place — check that it sits after the tunables and before `build_asset()`.

- [ ] **Step 6: Commit**

```bash
git add Assets/Blender/_tools/build_one.py Assets/Blender/_tools/_selftest_asset.py Assets/Blender/_tools/selftest.py
git commit -m "preview harness: in-blender bootstrap + selftest asset"
```

---

### Task 2: The parallel runner

**Files:**
- Create: `Assets/Blender/_tools/preview.py`
- Modify: `Assets/Blender/_tools/selftest.py` (append two tests + register them in `TESTS`)

**Interfaces:**
- Consumes: `build_one.py`'s CLI contract and its `_build.json` output (Task 1).
- Produces:
  - Python API: `run(asset, variants, views=None, sample_scale=0.5, timeout=180, jobs=4) -> dict` returning the manifest.
  - CLI: `python _tools/preview.py <asset> [--variants <json>] [--views a,b,c] [--all-views] [--jobs N]`
  - `manifest.json` at `_previews~/<asset>/run-NNN/manifest.json`, in the schema below. **Task 3 renders exactly this file.**
  - `_previews~/<asset>/latest.json` — a copy of the newest run's manifest, so the gallery has one fixed URL to poll.
  - `_previews~/assets.json` — asset names, most-recently-built first. **Task 3 reads this to find which asset to show.** It exists because the gallery cannot scrape a directory listing from the root: `SimpleHTTPRequestHandler` serves `index.html` when one is present, so `GET /` returns the gallery page rather than a listing.

Manifest schema (Task 3 depends on every field here):

```json
{
  "asset": "knight000",
  "run": 14,
  "started": "2026-07-31T14:22:03",
  "done": false,
  "audit": null,
  "variants": [
    {
      "n": 1,
      "label": "barbute",
      "diff": {"PLUME_LEN": 0.34},
      "renders": ["v1/hero_34.png", "v1/front.png"],
      "exit": 0,
      "seconds": 14.8,
      "stderr_tail": ""
    }
  ]
}
```

`exit` is `null` while building, an integer once finished, or the string `"timeout"`.

**Deviation from the spec, deliberate:** the spec put `audit` on each variant card. It belongs at run level instead. `audit_knight000.py` `exec`s the asset script directly with no `VARIANT` seeding, so it can only ever audit the baseline build — a per-variant badge would be the same verdict repeated N times, which reads as N independent checks and is worse than one honest one. The gallery shows it in the header. Making it genuinely per-variant would mean teaching the audit script the variant protocol, which is not worth it until a variant actually breaks manifold-ness.

- [ ] **Step 1: Write the failing tests**

Append to `Assets/Blender/_tools/selftest.py`, above the `TESTS = [...]` list:

```python
def test_runner_produces_manifest():
    """Three variants, run in parallel, all recorded in one manifest."""
    print("test_runner_produces_manifest")
    sys.path.insert(0, HERE)
    import preview

    manifest = preview.run(
        asset=ASSET,                     # explicit path, not a name
        variants=[
            {"label": "small", "vars": {"CUBE_SIZE": 0.5}},
            {"label": "big", "vars": {"CUBE_SIZE": 2.0}},
            {"label": "blue", "vars": {"CUBE_COLOR": [0.1, 0.2, 0.9, 1.0]}},
        ],
        views=["front"],
        root=tempfile.mkdtemp(prefix="gf_runner_"),
    )
    check("three variants recorded", len(manifest["variants"]) == 3,
          "got %d" % len(manifest["variants"]))
    check("run marked done", manifest.get("done") is True)
    check("all exited zero",
          all(v["exit"] == 0 for v in manifest["variants"]),
          str([v["exit"] for v in manifest["variants"]]))
    check("every variant has a render",
          all(v["renders"] for v in manifest["variants"]))
    check("variants numbered from 1",
          [v["n"] for v in manifest["variants"]] == [1, 2, 3])
    # diff must isolate only what differs, so the gallery can caption it
    diffs = [set(v["diff"]) for v in manifest["variants"]]
    check("diff holds only differing keys",
          all(d <= {"CUBE_SIZE", "CUBE_COLOR"} for d in diffs), str(diffs))


def test_one_broken_variant_does_not_block_siblings():
    print("test_one_broken_variant_does_not_block_siblings")
    sys.path.insert(0, HERE)
    import preview

    manifest = preview.run(
        asset=ASSET,
        variants=[
            {"label": "fine", "vars": {"CUBE_SIZE": 1.0}},
            {"label": "broken", "patch": "raise RuntimeError('deliberate')"},
            {"label": "also fine", "vars": {"CUBE_SIZE": 1.5}},
        ],
        views=["front"],
        root=tempfile.mkdtemp(prefix="gf_runner_broken_"),
    )
    good = [v for v in manifest["variants"] if v["label"] != "broken"]
    bad = [v for v in manifest["variants"] if v["label"] == "broken"][0]
    check("siblings still rendered", all(v["renders"] for v in good))
    check("siblings exited zero", all(v["exit"] == 0 for v in good))
    check("broken variant nonzero exit", bad["exit"] != 0, str(bad["exit"]))
    check("broken variant captured traceback",
          "deliberate" in bad["stderr_tail"], bad["stderr_tail"][:200])
```

And extend the registration list:

```python
TESTS = [
    test_bootstrap_renders,
    test_variant_overrides_a_constant,
    test_patch_can_call_script_helpers,
    test_broken_variant_reports_error,
    test_runner_produces_manifest,
    test_one_broken_variant_does_not_block_siblings,
]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python Assets/Blender/_tools/selftest.py test_runner
```

Expected: `ModuleNotFoundError: No module named 'preview'`.

- [ ] **Step 3: Write the runner**

Create `Assets/Blender/_tools/preview.py`.

```python
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


def resolve_asset(asset):
    """Accept either a bare name (knight000) or an explicit script path."""
    if os.path.exists(asset):
        return os.path.abspath(asset), os.path.splitext(os.path.basename(asset))[0]
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
    occasionally read a half-written file."""
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, target)


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

    # build_one writes this even when the build raises; prefer it over the exit
    # code, which Blender does not report reliably for a -P script.
    status_path = os.path.join(out_dir, "_build.json")
    if os.path.exists(status_path):
        try:
            with open(status_path, encoding="utf-8") as fh:
                status = json.load(fh)
            if not status.get("ok"):
                err = status.get("error", err)
                code = code or 1
        except (OSError, ValueError):
            pass
    elif code == 0:
        # Blender exited clean without the bootstrap finishing: it died early.
        code, err = 1, err or "build_one.py never wrote _build.json"

    renders = sorted(
        f for f in os.listdir(out_dir)
        if f.endswith(".png")
    ) if os.path.isdir(out_dir) else []

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
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python Assets/Blender/_tools/selftest.py
```

Expected: all six tests PASS. If `test_one_broken_variant_does_not_block_siblings` hangs, the `ThreadPoolExecutor` is not the problem — check that `subprocess.run` has `timeout=` set.

- [ ] **Step 5: Commit**

```bash
git add Assets/Blender/_tools/preview.py Assets/Blender/_tools/selftest.py
git commit -m "preview harness: parallel variant runner + manifest"
```

---

### Task 3: The gallery

**Files:**
- Create: `Assets/Blender/_tools/gallery/index.html`
- Create: `Assets/Blender/_tools/serve.py`

**Interfaces:**
- Consumes: `latest.json` and per-run `manifest.json` from Task 2, in the schema documented there.
- Produces: a static page served at `http://localhost:8777/`, and `serve.py`, which is what gets started as a long-running background task.

The page is served from the previews root so image paths resolve relatively. `serve.py` is a thin wrapper that also copies `index.html` into the previews root on start — that keeps `index.html` in source control under `_tools/` while still being served alongside the images, without needing a second route.

- [ ] **Step 1: Write the server**

Create `Assets/Blender/_tools/serve.py`.

```python
"""Serve the preview gallery. Start once, leave running.

    python Assets/Blender/_tools/serve.py

Then open http://localhost:8777/ and leave the tab open on a second monitor.

Deliberately a stock http.server: the gallery is view-only, so there is no
endpoint to write and nothing to maintain. index.html lives in source control
under _tools/ and is copied into the previews root on start so that relative
image paths just work.
"""

import functools
import http.server
import os
import shutil
import socketserver

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEW_ROOT = os.path.join(os.path.dirname(HERE), "_previews~")
PORT = int(os.environ.get("GLOOMFELL_GALLERY_PORT", "8777"))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass          # a 1 Hz poll would otherwise flood the console

    def end_headers(self):
        # The manifest changes several times within a run; never let it cache.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    os.makedirs(PREVIEW_ROOT, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "gallery", "index.html"),
                    os.path.join(PREVIEW_ROOT, "index.html"))
    handler = functools.partial(QuietHandler, directory=PREVIEW_ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print("gallery: http://localhost:%d/" % PORT)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the gallery page**

Create `Assets/Blender/_tools/gallery/index.html`.

```html
<!doctype html>
<meta charset="utf-8">
<title>Gloomfell · preview gallery</title>
<style>
  :root { color-scheme: dark; --bg:#131317; --card:#1c1c22; --line:#2e2e38;
          --dim:#8b8b99; --fg:#e8e8ef; --bad:#c8443c; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font:14px/1.5 "Segoe UI", system-ui, sans-serif; }
  header { position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line);
           padding:12px 20px; display:flex; gap:16px; align-items:baseline; z-index:2; }
  h1 { font-size:15px; margin:0; font-weight:600; letter-spacing:.3px; }
  .dim { color:var(--dim); }
  .cols { display:flex; gap:16px; padding:20px; align-items:flex-start;
          overflow-x:auto; }
  .col { background:var(--card); border:1px solid var(--line); border-radius:8px;
         padding:12px; min-width:220px; flex:0 0 auto; }
  .col h2 { font-size:13px; margin:0 0 2px; }
  .num { display:inline-block; min-width:20px; height:20px; line-height:20px;
         text-align:center; background:var(--fg); color:var(--bg);
         border-radius:4px; font-weight:700; margin-right:6px; }
  .diff { font:11px/1.4 ui-monospace, Consolas, monospace; color:var(--dim);
          margin:6px 0 10px; white-space:pre-wrap; }
  .col img { display:block; width:100%; border-radius:4px; margin-bottom:8px;
             background:#000; cursor:zoom-in; }
  .err { border-color:var(--bad); }
  .err pre { font:11px/1.4 ui-monospace, Consolas, monospace; color:#ffb4ae;
             background:#2a1614; padding:8px; border-radius:4px; margin:0;
             max-height:260px; overflow:auto; white-space:pre-wrap; }
  .pending { color:var(--dim); font-style:italic; padding:24px 0; text-align:center; }
  .badge { font:11px/1 ui-monospace, Consolas, monospace; padding:4px 8px;
           border-radius:4px; margin-left:auto; }
  .badge.ok  { background:#1d3a24; color:#7ee08e; }
  .badge.bad { background:#3a1a17; color:#ffb4ae; }
  details { margin:0 20px 12px; }
  summary { cursor:pointer; color:var(--dim); padding:6px 0; }
  dialog { border:none; background:transparent; max-width:96vw; max-height:96vh; }
  dialog img { max-width:96vw; max-height:96vh; }
  dialog::backdrop { background:#000c; }
</style>

<header>
  <h1 id="title">waiting for a build…</h1>
  <span class="dim" id="sub"></span>
  <span id="audit"></span>
</header>
<div id="live"></div>
<div id="history"></div>
<dialog id="zoom"><img></dialog>

<script>
// Poll latest.json once a second. Re-render whenever the BODY changes, not just
// when the run number does: the manifest is rewritten several times within a
// run as each variant lands, and we want those to appear as they arrive.
let lastBody = null, asset = null;

const q = p => p + (p.includes('?') ? '&' : '?') + 't=' + Date.now();

async function findAsset() {
  // preview.py maintains assets.json, most-recently-built first. We cannot
  // scrape a directory listing instead: http.server serves index.html when one
  // is present, so GET / returns this very page.
  const override = new URLSearchParams(location.search).get('asset');
  if (override) return override;
  const res = await fetch(q('/assets.json'));
  if (!res.ok) return null;
  const list = await res.json();
  return list.length ? list[0] : null;
}

function card(v) {
  const el = document.createElement('div');
  el.className = 'col' + (v.exit !== 0 && v.exit !== null ? ' err' : '');
  const diff = Object.entries(v.diff || {})
      .map(([k, val]) => `${k} = ${JSON.stringify(val)}`).join('\n');
  el.innerHTML = `<h2><span class="num">${v.n}</span>${v.label}</h2>`
    + (diff ? `<div class="diff">${diff}</div>` : '<div class="diff dim">baseline</div>');

  if (v.exit === null) {
    el.insertAdjacentHTML('beforeend', '<div class="pending">building…</div>');
  } else if (v.exit !== 0) {
    el.insertAdjacentHTML('beforeend',
      `<pre>exit ${v.exit}\n\n${(v.stderr_tail || '(no stderr)')
        .replace(/[<&]/g, c => ({'<':'&lt;','&':'&amp;'}[c]))}</pre>`);
  } else {
    for (const r of v.renders) {
      const img = new Image();
      img.src = q(`/${asset}/${v.runDir}/${r}`);
      img.loading = 'lazy';
      img.onclick = () => {
        const d = document.getElementById('zoom');
        d.querySelector('img').src = img.src;
        d.showModal();
      };
      el.appendChild(img);
    }
    if (v.seconds !== null)
      el.insertAdjacentHTML('beforeend', `<div class="diff">${v.seconds}s</div>`);
  }
  return el;
}

function renderRun(m, into) {
  const wrap = document.createElement('div');
  wrap.className = 'cols';
  for (const v of m.variants) {
    v.runDir = 'run-' + String(m.run).padStart(3, '0');
    wrap.appendChild(card(v));
  }
  into.appendChild(wrap);
}

async function loadHistory(current) {
  // Earlier runs, newest first, collapsed. This is the "watch it change" half:
  // the model's history across builds, not just its current state.
  const host = document.getElementById('history');
  host.innerHTML = '';
  for (let n = current - 1; n > 0 && n > current - 12; n--) {
    const dir = 'run-' + String(n).padStart(3, '0');
    const res = await fetch(q(`/${asset}/${dir}/manifest.json`));
    if (!res.ok) continue;
    const m = await res.json();
    const d = document.createElement('details');
    d.innerHTML = `<summary>run ${m.run} · ${m.started} · `
      + `${m.variants.map(v => v.label).join(', ')}</summary>`;
    host.appendChild(d);
    renderRun(m, d);
  }
}

async function tick() {
  try {
    if (!asset) asset = await findAsset();
    if (!asset) return;
    const res = await fetch(q(`/${asset}/latest.json`));
    if (!res.ok) return;
    const body = await res.text();
    if (body === lastBody) return;          // nothing changed; leave the DOM alone
    const wasNewRun = lastBody === null
      || JSON.parse(lastBody).run !== JSON.parse(body).run;
    lastBody = body;
    const m = JSON.parse(body);

    document.getElementById('title').textContent = `${m.asset} · run ${m.run}`;
    const badge = document.getElementById('audit');
    badge.textContent = m.audit || '';
    // Run level, not per variant: the audit script only ever sees the baseline.
    badge.className = m.audit
      ? (m.audit.includes('FAIL') ? 'badge bad' : 'badge ok') : '';
    document.getElementById('sub').textContent =
      m.started + (m.done ? '' : ' · building…');
    const live = document.getElementById('live');
    live.innerHTML = '';
    renderRun(m, live);
    if (wasNewRun) loadHistory(m.run);
  } catch (e) {
    // A half-written manifest or a momentary 404 is expected during a run.
    // Keep the last good render on screen rather than blanking the page.
    console.debug('poll skipped:', e);
  }
}

document.getElementById('zoom').onclick = e => e.currentTarget.close();
tick();
setInterval(tick, 1000);
</script>
```

- [ ] **Step 3: Start the server and verify manually**

```bash
python Assets/Blender/_tools/serve.py
```

Then, in a second shell, generate a run with a deliberate failure so all three card states appear:

```bash
python Assets/Blender/_tools/preview.py Assets/Blender/_tools/_selftest_asset.py --views front
```

Open `http://localhost:8777/`. Expected:
- One column headed `1 default`, showing a rendered cube.
- Re-running `preview.py` updates the page within ~2 s with no manual reload, and the previous run appears collapsed underneath.
- Clicking an image opens it full size; clicking again closes it.

- [ ] **Step 4: Verify the failure and pending states**

Write the variants file into `_previews~/_scratch/`, which is already gitignored and which `write_asset_index()` skips (it has no `latest.json`):

```bash
mkdir -p "Assets/Blender/_previews~/_scratch"
cat > "Assets/Blender/_previews~/_scratch/gallery_check.json" <<'EOF'
[
  {"label": "fine",   "vars": {"CUBE_SIZE": 1.0}},
  {"label": "broken", "patch": "raise RuntimeError('deliberate gallery check')"},
  {"label": "large",  "vars": {"CUBE_SIZE": 2.0}}
]
EOF
python Assets/Blender/_tools/preview.py Assets/Blender/_tools/_selftest_asset.py \
  --variants "Assets/Blender/_previews~/_scratch/gallery_check.json" --views front
```

Expected in the browser: three columns numbered 1/2/3; columns 1 and 3 show cubes of visibly different size; column 2 has a red border and a `<pre>` containing `deliberate gallery check`. Watching during the run, columns show "building…" before they resolve.

- [ ] **Step 5: Commit**

```bash
git add Assets/Blender/_tools/gallery/index.html Assets/Blender/_tools/serve.py
git commit -m "preview harness: auto-refreshing gallery + static server"
```

---

### Task 4: Knight adoption, gitignore, real smoke run

**Files:**
- Modify: `Assets/Blender/blender_knight000.py:2456-2468` (add `RENDER_ONLY` / `SAMPLE_SCALE` guard to `render_view`)
- Modify: `Assets/Blender/blender_knight000.py:2336` (insert the variant hook before `build_knight()`)
- Modify: `.gitignore`
- Modify: `Assets/Blender/_tools/selftest.py` (register the non-destructive check)

**Interfaces:**
- Consumes: the variant hook block and the `RENDER_ONLY` convention from Task 1; `preview.run()` from Task 2.
- Produces: `knight000` as a working asset name for `preview.py`.

- [ ] **Step 1: Add the view guard to `render_view`**

In `Assets/Blender/blender_knight000.py`, the function currently at line 2456 begins:

```python
def render_view(name, cam_loc, target=(0, 0, 1.05), res=(900, 1250), lens=62,
                samples=None):
    cam = SCENE.camera
```

Replace that opening with:

```python
def render_view(name, cam_loc, target=(0, 0, 1.05), res=(900, 1250), lens=62,
                samples=None):
    # A preview run renders a cheap subset rather than all ten views. RENDER_ONLY
    # unset (the normal case) means "render everything", so a plain
    # `blender -b -P blender_knight000.py -- render` is unaffected.
    only = globals().get("RENDER_ONLY")
    if only is not None and name not in only:
        return
    cam = SCENE.camera
```

Then, immediately below, replace the sample line:

```python
    if samples and hasattr(SCENE.eevee, "taa_render_samples"):
        SCENE.eevee.taa_render_samples = samples
```

with:

```python
    # SAMPLE_SCALE lets a preview run trade noise for speed. Views that pass no
    # explicit count fall back to the rig's default of 96 (see build_rig).
    scale = globals().get("SAMPLE_SCALE", 1.0)
    if hasattr(SCENE.eevee, "taa_render_samples"):
        SCENE.eevee.taa_render_samples = max(16, int((samples or 96) * scale))
```

- [ ] **Step 2: Insert the variant hook**

At line 2336 the file reads:

```python
build_knight()
print("Knight built: %d meshes, %d empties" % (len(PARTS), len(EMPTIES)))
```

Replace with:

```python
# --- variant hook -------------------------------------------------------------
# A runner (_tools/preview.py) pre-seeds VARIANT in this namespace before
# exec'ing the file. Entries are applied after every default above is set and
# before anything is built, so a variant can override any tuning constant, any
# material, or any builder function.
#
# This block cannot be moved into a shared helper and imported. globals() here
# resolves to the CALLING module's namespace - which is precisely what the hook
# needs and precisely what an imported function could not give it. A DRY cleanup
# that extracts this silently breaks name resolution for every variant.
#
# RENDER_DIR rides in here too, deliberately: line 48 assigns it unconditionally,
# so a plain namespace seed would be clobbered. Applying it here — after that
# assignment, before render_view() reads it — is what makes previews land in the
# run directory instead of _knight000/.
_v = globals().get("VARIANT", {})
globals().update({k: v for k, v in _v.items() if not k.startswith("_")})
if _v.get("_patch"):
    # Structural variants arrive as SOURCE, not as function objects. A function
    # defined in the runner carries the runner's __globals__ and cannot see
    # revolve(), M_GOLD, or any other helper here — it would fail at call time,
    # deep in the build, for a reason that looks nothing like its cause.
    # exec'ing the source binds it to this namespace instead.
    exec(_v["_patch"], globals())
# ------------------------------------------------------------------------------

build_knight()
print("Knight built: %d meshes, %d empties" % (len(PARTS), len(EMPTIES)))
```

- [ ] **Step 3: Add the gitignore entry**

Append to `.gitignore`:

```gitignore
# Blender preview harness scratch renders. The trailing tilde keeps Unity from
# importing every scratch PNG; the ignore keeps them out of git.
/[Aa]ssets/Blender/_previews~/
```

- [ ] **Step 4: Add the non-destructive check to the self-test**

Append to `Assets/Blender/_tools/selftest.py`, above `TESTS = [...]`:

```python
def test_knight_preview_is_non_destructive():
    """A knight preview run must not touch the real .blend or FBX.

    This is the check worth having: previews and real exports share a script,
    and the failure mode is silent - you only notice when a half-finished
    variant has overwritten the asset Unity is importing.
    """
    print("test_knight_preview_is_non_destructive")
    sys.path.insert(0, HERE)
    import preview

    blend = os.path.join(os.path.dirname(HERE), "knight000.blend")
    fbx = os.path.join(os.path.dirname(HERE), "..", "Models", "knight000.fbx")
    before = {p: (os.path.getmtime(p) if os.path.exists(p) else None)
              for p in (blend, fbx)}

    manifest = preview.run(
        asset="knight000",
        variants=[{"label": "baseline"}],
        views=["icon_184"],
        root=tempfile.mkdtemp(prefix="gf_knight_"),
    )
    v = manifest["variants"][0]
    check("knight variant built", v["exit"] == 0, v["stderr_tail"][:400])
    check("icon rendered", any("icon_184" in r for r in v["renders"]),
          str(v["renders"]))
    for p, was in before.items():
        now = os.path.getmtime(p) if os.path.exists(p) else None
        check("untouched: " + os.path.basename(p), now == was)
```

Register it:

```python
TESTS = [
    test_bootstrap_renders,
    test_variant_overrides_a_constant,
    test_patch_can_call_script_helpers,
    test_broken_variant_reports_error,
    test_runner_produces_manifest,
    test_one_broken_variant_does_not_block_siblings,
    test_knight_preview_is_non_destructive,
]
```

- [ ] **Step 5: Run the full self-test**

```bash
python Assets/Blender/_tools/selftest.py
```

Expected: all seven tests PASS. The knight test is the slow one (~20 s).

- [ ] **Step 6: Verify the normal build path still works**

The harness must not have changed what a plain build does. `RENDER_ONLY` unset means all ten views; `SAMPLE_SCALE` unset means 1.0.

```bash
"/c/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b \
  -P Assets/Blender/blender_knight000.py -- render
```

Expected: ten PNGs refreshed in `Assets/Blender/_knight000/`, including `poster.png`, at their original resolutions. Confirm `poster.png` is ~3 MB as before, not visibly noisier.

- [ ] **Step 7: Real three-variant run**

```bash
cat > "Assets/Blender/_previews~/_scratch/plume.json" <<'EOF'
[
  {"label": "baseline",     "vars": {}},
  {"label": "short plume",  "vars": {"Z_CROWN": 1.92}},
  {"label": "tall plume",   "vars": {"Z_CROWN": 2.08}}
]
EOF
python Assets/Blender/_tools/preview.py knight000 \
  --variants "Assets/Blender/_previews~/_scratch/plume.json"
```

Expected: run completes in roughly 25 s; three columns in the gallery, each with `hero_34`, `front` and `icon_184`; the `diff` caption under columns 2 and 3 reads `Z_CROWN = 1.92` / `Z_CROWN = 2.08`.

- [ ] **Step 8: Verify the audit badge**

`run_audit()` looks for `Assets/Blender/_<asset>/audit_<asset>.py`, which is exactly where `audit_knight000.py` already lives — so the knight is the first asset with a real verdict to show.

```bash
python Assets/Blender/_tools/preview.py knight000 --views icon_184 --audit
```

Expected: the run prints an `audit:` line, and the gallery header shows a green badge carrying the audit's PASS line. If the audit reports FAIL, the badge is red — that is a real finding about the model, not a harness bug, and should be reported rather than worked around.

- [ ] **Step 9: Document the harness in CLAUDE.md**

Add to `CLAUDE.md` under "Asset pipeline", after the existing paragraph about `blender_*.py` scripts:

```markdown
### Preview harness

`Assets/Blender/_tools/` renders variants of an asset in parallel and shows them in a
browser gallery. Start the gallery once and leave it running:

    python Assets/Blender/_tools/serve.py        # http://localhost:8777/

Then, to compare alternatives:

    python Assets/Blender/_tools/preview.py knight000 --variants helmets.json

where `helmets.json` is a list of `{"label": ..., "vars": {...}, "patch": "..."}`.
`vars` overrides any module-level global in the asset script; `patch` is Python
source (not a function object — it must bind to the script's own globals) that can
replace a whole builder such as `build_helmet`. Variants are numbered 1..N in the
gallery, which is how they should be referred to when asking the user to choose.

Preview runs are non-destructive: they never write the `.blend` or the FBX. Output
goes to `_previews~/` — the trailing tilde is what stops Unity importing every
scratch render.

A script is "conforming" (drivable by the harness) if its tunables are module-level
globals, it has a single top-level build call with the variant hook immediately
above it, and its `render_view()` honours `RENDER_ONLY`. `_tools/_selftest_asset.py`
is the shortest complete example. `blender_knight000.py` conforms;
the other `blender_*.py` scripts do not yet and should adopt the hook when next
touched.

Run `python Assets/Blender/_tools/selftest.py` after changing anything in `_tools/`.
```

- [ ] **Step 10: Commit**

```bash
git add Assets/Blender/blender_knight000.py Assets/Blender/_tools/selftest.py .gitignore CLAUDE.md
git commit -m "preview harness: knight000 adopts the variant hook"
```

---

## Notes for the implementer

**Where this can go wrong quietly, in order of likelihood:**

1. **The hook in the wrong place.** It must sit after every default assignment and before the build call. Too early and defaults clobber the variant; too late and the build has already run. `test_variant_overrides_a_constant` is the check — if it reports "identical bytes", this is why.
2. **`_patch` passed as a function instead of source.** JSON cannot carry a function, so this only arises if someone "helpfully" refactors the runner to pass callables. `test_patch_can_call_script_helpers` exists to catch that regression.
3. **`RENDER_DIR` seeded but not in `VARIANT`.** Asset scripts assign it near the top, so the seed alone is clobbered and previews land in `_knight000/`, overwriting the real renders. `build_one.py` forces it into `VARIANT` for this reason — do not "simplify" that away.
4. **Unity importing `_previews~`.** If the tilde is ever dropped, Unity will begin importing every scratch PNG. The symptom is a slow editor and a large `Library/`, which looks nothing like a Blender problem.
