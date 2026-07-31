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
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = os.environ.get(
    "GLOOMFELL_BLENDER",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
)
ASSET = os.path.join(HERE, "_selftest_asset.py")
# What preview.resolve_asset() derives ASSET's name as - used below to find
# where on disk a run's manifest/latest.json landed, since preview.run() only
# returns the manifest dict, not its path. Derived independently rather than by
# calling resolve_asset(), so that a bug in resolve_asset() shows up as a
# missing file here instead of cancelling itself out. (resolve_asset also
# strips a leading "blender_"; this name has no such prefix, so the two agree.)
ASSET_NAME = os.path.splitext(os.path.basename(ASSET))[0]
BUILD_ONE = os.path.join(HERE, "build_one.py")
SERVE = os.path.join(HERE, "serve.py")
# serve.py hardcodes its previews root relative to itself (no env override for
# that, only for PORT), so this must match Assets/Blender/_previews~ exactly -
# see serve.py's own PREVIEW_ROOT computation.
PREVIEW_ROOT = os.path.join(os.path.dirname(HERE), "_previews~")

_failures = []


def check(label, cond, detail=""):
    if cond:
        print("  PASS  " + label)
    else:
        print("  FAIL  " + label + ("\n        " + detail if detail else ""))
        _failures.append(label)


def run_build_one(variant, out, script=ASSET):
    """Invoke the in-Blender bootstrap once. Returns (returncode, stderr)."""
    os.makedirs(out, exist_ok=True)
    vpath = os.path.join(out, "_variant.json")
    with open(vpath, "w", encoding="utf-8") as fh:
        json.dump(variant, fh)
    proc = subprocess.run(
        [BLENDER, "-b", "-P", BUILD_ONE, "--",
         "--script", script, "--variant", vpath, "--out", out],
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


def test_non_conforming_script_is_refused():
    """Both interlocks must refuse a script that has not opted into the harness.

    The hazard: preview.py maps a bare name to Assets/Blender/blender_<name>.py
    and build_one.py exec's whatever it is handed, while eight of the nine real
    asset scripts save and/or export UNCONDITIONALLY at module scope. Nothing
    about `preview.py boat000` would look wrong until boat000.blend and
    boat000.fbx had already been rebuilt over the top of whatever was in them.

    Tested against a throwaway script, never a real asset, so this test can
    never itself be the thing that overwrites something. The stand-in writes a
    sentinel file when it runs, which is what turns "refused" from an exit code
    into a fact: if either gate leaked, the sentinel would exist.
    """
    print("test_non_conforming_script_is_refused")
    sys.path.insert(0, HERE)
    import build_one
    import preview

    check("both interlocks use the same marker string",
          preview.HOOK_MARKER == build_one.HOOK_MARKER,
          "%r vs %r" % (preview.HOOK_MARKER, build_one.HOOK_MARKER))

    tmp = tempfile.mkdtemp(prefix="gf_nonconforming_")
    try:
        # Named blender_*.py so it goes through resolve_asset()'s prefix strip
        # as well. Its body is deliberately harmless - a real non-conforming
        # script would be calling save_as_mainfile() on this line.
        script = os.path.join(tmp, "blender_notopted.py")
        sentinel = os.path.join(tmp, "RAN")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write("import os\n"
                     "open(os.path.join(os.path.dirname(os.path.abspath(__file__)),\n"
                     "                  'RAN'), 'w').close()\n")

        # Layer 1: the runner, which must refuse before any Blender launches.
        previews = os.path.join(tmp, "previews")
        msg = ""
        refused = False
        try:
            preview.run(asset=script, root=previews)
        except SystemExit as exc:
            refused, msg = True, str(exc)
        check("preview.run refuses a script with no variant hook", refused)
        check("the refusal names the script and the marker",
              os.path.abspath(script) in msg and preview.HOOK_MARKER in msg,
              msg[:400])
        # Refused before next_run_dir(), so not even a run directory exists.
        check("nothing was allocated on disk for the refused asset",
              not os.path.exists(previews))

        # Layer 2: the bootstrap. Directly invocable, so it cannot assume
        # layer 1 ran at all.
        out = os.path.join(tmp, "out")
        rc, _stderr = run_build_one({}, out, script=script)
        check("build_one exits with its distinct refusal code",
              rc == build_one.EXIT_NOT_CONFORMING,
              "exit %s, wanted %s" % (rc, build_one.EXIT_NOT_CONFORMING))
        status_path = os.path.join(out, "_build.json")
        check("build_one wrote its refusal to _build.json",
              os.path.exists(status_path))
        if os.path.exists(status_path):
            status = _read_json(status_path)
            check("_build.json reports ok False", status.get("ok") is False)
            check("_build.json explains the refusal",
                  "variant hook" in str(status.get("error", "")),
                  str(status.get("error"))[:300])

        check("the non-conforming script never executed",
              not os.path.exists(sentinel))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# Exactly the fields gallery/index.html reads. This is the one seam in the
# harness with two sides written in different languages and no shared schema:
# rename `stderr_tail` or `renders` in preview.py and every Python test still
# passes while the page silently renders blank or wrong cards. Nothing else in
# this suite looks at the manifest's SHAPE, only at its values.
#
# Sourced from index.html: card() reads n, label, diff, exit, stderr_tail,
# renders and seconds; tick() reads asset, run, started, done and audit;
# renderRun()/renderLive() read variants.
GALLERY_VARIANT_FIELDS = {"n", "label", "diff", "renders", "exit", "seconds",
                          "stderr_tail"}
GALLERY_MANIFEST_FIELDS = {"asset", "run", "started", "done", "audit", "variants"}


def _assert_gallery_contract(root, manifest):
    """The manifest.json -> index.html field contract, and its path arithmetic."""
    missing = GALLERY_MANIFEST_FIELDS - set(manifest)
    check("manifest has every top-level field the gallery reads",
          not missing, "missing: " + str(sorted(missing)))

    # Exact set, not a subset: an EXTRA field is a signal too - either the
    # gallery needs teaching about it, or it is a leftover nobody consumes.
    wrong = [(v.get("n"), sorted(set(v) ^ GALLERY_VARIANT_FIELDS))
             for v in manifest["variants"] if set(v) != GALLERY_VARIANT_FIELDS]
    check("every variant carries exactly the gallery's field set",
          not wrong, "variant n / symmetric difference: " + str(wrong))

    # Duplicate the page's own arithmetic rather than trusting it: card() builds
    # each <img> src as /<asset>/run-NNN/<renders entry>, deriving run-NNN from
    # m.run. If the manifest's paths and the files on disk ever drift apart the
    # gallery just shows broken images, which reads as a gallery bug.
    run_dir = os.path.join(root, manifest["asset"], "run-%03d" % manifest["run"])
    broken = [r for v in manifest["variants"] for r in v["renders"]
              if not os.path.exists(os.path.join(run_dir, *r.split("/")))]
    check("every render path in the manifest resolves to a file on disk",
          not broken, str(broken))


def _assert_manifest_on_disk(root, manifest):
    """Task 3's gallery never sees the dict preview.run() returns - it polls
    manifest.json/latest.json/assets.json directly. Asserting only the
    in-memory manifest would keep passing even if write_manifest() were
    deleted entirely, so read back what actually landed on disk."""
    run_dir = os.path.join(root, ASSET_NAME, "run-%03d" % manifest["run"])
    on_disk = _read_json(os.path.join(run_dir, "manifest.json"))
    check("on-disk manifest.json matches the returned manifest",
          on_disk == manifest)

    latest = _read_json(os.path.join(root, ASSET_NAME, "latest.json"))
    check("latest.json mirrors the run's manifest", latest == manifest)

    assets = _read_json(os.path.join(root, "assets.json"))
    check("assets.json lists the built asset", ASSET_NAME in assets,
          str(assets))

    # Checked against what LANDED, not against the returned dict: the gallery
    # only ever sees the file.
    _assert_gallery_contract(root, on_disk)


def test_runner_produces_manifest():
    """Three variants, run in parallel, all recorded in one manifest."""
    print("test_runner_produces_manifest")
    sys.path.insert(0, HERE)
    import preview

    root = tempfile.mkdtemp(prefix="gf_runner_")
    try:
        manifest = preview.run(
            asset=ASSET,                     # explicit path, not a name
            variants=[
                {"label": "small", "vars": {"CUBE_SIZE": 0.5}},
                {"label": "big", "vars": {"CUBE_SIZE": 2.0}},
                {"label": "blue", "vars": {"CUBE_COLOR": [0.1, 0.2, 0.9, 1.0]}},
            ],
            views=["front"],
            root=root,
        )
        check("three variants recorded", len(manifest["variants"]) == 3,
              "got %d" % len(manifest["variants"]))
        check("run marked done", manifest.get("done") is True)
        check("all exited zero",
              all(v["exit"] == 0 for v in manifest["variants"]),
              str([v["exit"] for v in manifest["variants"]]))
        # The EXACT render set, not membership. `any("front" in r ...)` would
        # keep passing if RENDER_ONLY were ignored outright and all three views
        # the asset defines (front, side, icon_184) got rendered - so it would
        # not notice the guard in render_view() disappearing, which is the one
        # thing standing between a "cheap subset" preview and a full-cost one.
        # That guard has already regressed once during this project.
        expected = [["v%d/front.png" % (i + 1)] for i in range(3)]
        got = [v["renders"] for v in manifest["variants"]]
        check("each variant rendered exactly the one requested view",
              got == expected, "%s != %s" % (got, expected))
        check("variants numbered from 1",
              [v["n"] for v in manifest["variants"]] == [1, 2, 3])
        # diff must isolate only what differs, so the gallery can caption it
        diffs = [set(v["diff"]) for v in manifest["variants"]]
        check("diff holds only differing keys",
              all(d <= {"CUBE_SIZE", "CUBE_COLOR"} for d in diffs), str(diffs))
        _assert_manifest_on_disk(root, manifest)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_one_broken_variant_does_not_block_siblings():
    print("test_one_broken_variant_does_not_block_siblings")
    sys.path.insert(0, HERE)
    import preview

    root = tempfile.mkdtemp(prefix="gf_runner_broken_")
    try:
        manifest = preview.run(
            asset=ASSET,
            variants=[
                {"label": "fine", "vars": {"CUBE_SIZE": 1.0}},
                {"label": "broken", "patch": "raise RuntimeError('deliberate')"},
                {"label": "also fine", "vars": {"CUBE_SIZE": 1.5}},
            ],
            views=["front"],
            root=root,
        )
        good = [v for v in manifest["variants"] if v["label"] != "broken"]
        bad = [v for v in manifest["variants"] if v["label"] == "broken"][0]
        check("siblings still rendered", all(v["renders"] for v in good))
        check("siblings exited zero", all(v["exit"] == 0 for v in good))
        check("broken variant nonzero exit", bad["exit"] != 0, str(bad["exit"]))
        check("broken variant captured traceback",
              "deliberate" in bad["stderr_tail"], bad["stderr_tail"][:200])
        # The broken variant's failure must survive the round trip to disk
        # too, not just live in the dict this process happens to hold.
        _assert_manifest_on_disk(root, manifest)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_build_that_renders_nothing_is_a_failure():
    """No image means failure, whatever Blender's exit code claimed.

    DEFAULT_VIEWS is hardcoded to the knight's view names, so the first asset
    that names its views differently - or any typo in --views - makes
    RENDER_ONLY match nothing. The build then genuinely succeeds while
    producing no pictures, and without this the gallery shows a green column
    with a label, a diff and a duration and no images: a result that reads as a
    gallery bug rather than as the caller's typo.
    """
    print("test_build_that_renders_nothing_is_a_failure")
    sys.path.insert(0, HERE)
    import preview

    root = tempfile.mkdtemp(prefix="gf_runner_noviews_")
    try:
        manifest = preview.run(
            asset=ASSET,
            variants=[{"label": "typo"}],
            views=["no_such_view"],
            root=root,
        )
        v = manifest["variants"][0]
        check("a render-nothing build is reported as failed", v["exit"] != 0,
              repr(v["exit"]))
        check("no renders recorded", v["renders"] == [], str(v["renders"]))
        check("the message names the views that were asked for",
              "no_such_view" in v["stderr_tail"], v["stderr_tail"][:300])
        check("the message points at render_view()",
              "render_view()" in v["stderr_tail"], v["stderr_tail"][:300])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_variant_timeout_is_recorded():
    """A wedged Blender is killed, recorded, and does not strand the run.

    The design doc calls the failure path "not optional"; the timeout branch is
    the half of it that nothing exercised. Made deterministic by construction
    rather than by tuning a race:

      * the wedged variant sleeps 600 s, so it cannot finish inside the 15 s
        timeout however fast the machine is;
      * jobs=1 runs the two variants sequentially, so the surviving variant has
        the machine to itself rather than racing its own timeout against a
        sibling for cores. Cube builds are recorded at 3.5-5.0 s even three-up
        in parallel, so 15 s alone is a wide margin;
      * the sleeper is submitted FIRST, which is the stronger claim: a variant
        killed by the timeout does not stop a sibling that had not even started.

    Costs about 20 s of wall clock - the timeout plus one real build. That is
    the price of it not being flaky.
    """
    print("test_variant_timeout_is_recorded")
    sys.path.insert(0, HERE)
    import preview

    root = tempfile.mkdtemp(prefix="gf_runner_timeout_")
    try:
        manifest = preview.run(
            asset=ASSET,
            variants=[
                {"label": "wedged",
                 "patch": "import time\ndef build_asset():\n    time.sleep(600)\n"},
                {"label": "fine", "vars": {"CUBE_SIZE": 1.0}},
            ],
            views=["front"],
            timeout=15,
            jobs=1,
            root=root,
        )
        wedged, fine = manifest["variants"]
        check("wedged variant recorded as a timeout",
              wedged["exit"] == "timeout", repr(wedged["exit"]))
        check("the timeout says how long it waited",
              "killed after" in wedged["stderr_tail"], wedged["stderr_tail"][:200])
        check("wedged variant produced no renders",
              wedged["renders"] == [], str(wedged["renders"]))
        check("sibling still ran after the kill", fine["exit"] == 0,
              fine["stderr_tail"][:400])
        check("sibling rendered", fine["renders"] == ["v2/front.png"],
              str(fine["renders"]))
        # "timeout" is a string where every other exit is an int; it has to
        # survive the JSON round trip the gallery actually reads.
        _assert_manifest_on_disk(root, manifest)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _wait_for_server(base_url, deadline_seconds=10):
    """Poll until the socket accepts connections, or give up.

    A fixed sleep-then-hope would be flaky (Blender-adjacent boxes are slow to
    schedule a fresh python.exe under load) and a hang would be worse; this
    bounds the wait and returns the last connection error for the failure
    message instead of hanging the whole selftest run.
    """
    deadline = time.time() + deadline_seconds
    last_exc = None
    while time.time() < deadline:
        try:
            return urllib.request.urlopen(base_url + "/", timeout=1)
        except (urllib.error.URLError, ConnectionError) as exc:
            last_exc = exc
            time.sleep(0.1)
    raise last_exc or RuntimeError("server never came up")


def test_gallery_server_contract():
    """serve.py's whole job is a contract with gallery/index.html's poller:

    - GET / must return the page itself (proves index.html got copied into
      the previews root and stock http.server is serving it, not a 404).
    - GET /assets.json must be 200 and a JSON list (the page's findAsset()
      parses it with no error handling for "not a list").
    - every response carries Cache-Control: no-store (QuietHandler.end_headers
      - without it the 1 Hz poller could get a cached latest.json and never
        notice a run finished).

    Hermetic: runs on GLOOMFELL_GALLERY_PORT=8778, not the default 8777, so it
    cannot collide with a human's already-open gallery tab. Does not require
    any preview run to already exist - assets.json is real shared scratch
    state under Assets/Blender/_previews~ (a human's manual gallery check may
    be using it too), so if it is missing this writes a throwaway empty list
    and removes it afterwards rather than assuming any asset has ever built.
    """
    print("test_gallery_server_contract")
    port = 8778
    base = "http://127.0.0.1:%d" % port
    env = dict(os.environ, GLOOMFELL_GALLERY_PORT=str(port))

    os.makedirs(PREVIEW_ROOT, exist_ok=True)
    assets_json = os.path.join(PREVIEW_ROOT, "assets.json")
    wrote_placeholder = not os.path.exists(assets_json)
    if wrote_placeholder:
        with open(assets_json, "w", encoding="utf-8") as fh:
            json.dump([], fh)

    proc = subprocess.Popen(
        [sys.executable, SERVE], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        root_resp = _wait_for_server(base)
        root_body = root_resp.read().decode("utf-8")
        check("GET / is 200", root_resp.status == 200)
        check("GET / body contains the gallery page's title marker",
              "<title>Gloomfell · preview gallery</title>" in root_body,
              root_body[:200])
        check("GET / carries Cache-Control: no-store",
              root_resp.headers.get("Cache-Control") == "no-store")

        assets_resp = urllib.request.urlopen(base + "/assets.json", timeout=5)
        check("GET /assets.json is 200", assets_resp.status == 200)
        parsed = json.loads(assets_resp.read().decode("utf-8"))
        check("assets.json parses as a list", isinstance(parsed, list), repr(parsed))
        check("GET /assets.json carries Cache-Control: no-store",
              assets_resp.headers.get("Cache-Control") == "no-store")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        if wrote_placeholder and os.path.exists(assets_json):
            os.remove(assets_json)


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

    root = tempfile.mkdtemp(prefix="gf_knight_")
    try:
        manifest = preview.run(
            asset="knight000",
            variants=[{"label": "baseline"}],
            views=["icon_184"],
            root=root,
        )
        v = manifest["variants"][0]
        check("knight variant built", v["exit"] == 0, v["stderr_tail"][:400])
        # Exact, not `any(...)`: the knight defines TEN views, and a membership
        # check passes just as happily when RENDER_ONLY is ignored and all ten
        # render - which is a ~4x cost regression that would otherwise show up
        # only as "previews got slow". blender_knight000.py's render_view()
        # guard is what this is really asserting.
        check("only the requested view rendered",
              v["renders"] == ["v1/icon_184.png"], str(v["renders"]))
        for p, was in before.items():
            now = os.path.getmtime(p) if os.path.exists(p) else None
            check("untouched: " + os.path.basename(p), now == was)
    finally:
        shutil.rmtree(root, ignore_errors=True)


TESTS = [
    test_bootstrap_renders,
    test_variant_overrides_a_constant,
    test_patch_can_call_script_helpers,
    test_broken_variant_reports_error,
    test_non_conforming_script_is_refused,
    test_runner_produces_manifest,
    test_one_broken_variant_does_not_block_siblings,
    test_build_that_renders_nothing_is_a_failure,
    test_variant_timeout_is_recorded,
    test_gallery_server_contract,
    test_knight_preview_is_non_destructive,
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
