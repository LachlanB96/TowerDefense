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
        _rc, stderr = run_build_one({}, tmp)
        status_path = os.path.join(tmp, "_build.json")
        check("_build.json written", os.path.exists(status_path))
        if os.path.exists(status_path):
            with open(status_path, encoding="utf-8") as fh:
                status = json.load(fh)
            check("build reported ok", status.get("ok") is True,
                  str(status.get("error", ""))[:400])
        check("front.png rendered", os.path.exists(os.path.join(tmp, "front.png")))
        # run_build_one's stderr was captured but never inspected until now, so
        # a regression like the Material.use_nodes DeprecationWarning could
        # only ever be caught by an out-of-band manual run. A clean build
        # should be silent on stderr; assert it rather than just discarding it.
        check("stderr has no Warning/Error noise",
              "Warning" not in stderr and "Error" not in stderr,
              stderr[:400])
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

    Asserting only `ok is True` is not enough to catch every way this can
    break: if the hook were written `exec(_v["_patch"], dict(globals()))` (a
    plausible "defensive copy" mistake), the patched build_asset() would be
    defined into that throwaway copy, never replace the real one, and the
    ORIGINAL unpatched build_asset() would run instead. Nothing would raise,
    ok would still be True, and this test would pass while the mechanism is
    silently broken - only the narrower "helper extracted to another module"
    mistake would still be caught, via NameError. So build an unpatched
    baseline and byte-diff the patched render against it, the same technique
    test_variant_overrides_a_constant already uses: the patch moves the cube
    to z=1.5, which only shows up in the render if the patch actually replaced
    the function the real exec runs.
    """
    print("test_patch_can_call_script_helpers")
    baseline = tempfile.mkdtemp(prefix="gf_selftest_patch_base_")
    patched = tempfile.mkdtemp(prefix="gf_selftest_patch_")
    try:
        patch = (
            "def build_asset():\n"
            "    # calls a helper defined in the asset script, not in the runner\n"
            "    add_cube_at(0.0, 0.0, 1.5)\n"
        )
        run_build_one({}, baseline)
        run_build_one({"_patch": patch}, patched)

        status_path = os.path.join(patched, "_build.json")
        ok = False
        detail = "no _build.json"
        if os.path.exists(status_path):
            with open(status_path, encoding="utf-8") as fh:
                status = json.load(fh)
            ok = status.get("ok") is True
            detail = str(status.get("error", ""))[:400]
        check("_patch replaced the builder and ran", ok, detail)

        a = os.path.join(baseline, "front.png")
        b = os.path.join(patched, "front.png")
        check("both builds rendered", os.path.exists(a) and os.path.exists(b))
        if os.path.exists(a) and os.path.exists(b):
            check("patched render differs from unpatched baseline",
                  open(a, "rb").read() != open(b, "rb").read(),
                  "identical bytes - build_asset() ran unpatched; the patch "
                  "was defined somewhere the real exec never reached")
    finally:
        shutil.rmtree(baseline, ignore_errors=True)
        shutil.rmtree(patched, ignore_errors=True)


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


TESTS = [
    test_bootstrap_renders,
    test_variant_overrides_a_constant,
    test_patch_can_call_script_helpers,
    test_broken_variant_reports_error,
    test_runner_produces_manifest,
    test_one_broken_variant_does_not_block_siblings,
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
