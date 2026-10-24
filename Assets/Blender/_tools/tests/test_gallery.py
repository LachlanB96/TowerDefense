"""The suite's page script and how serve.py builds and serves it.

    python -m pytest Assets/Blender/_tools/tests/test_gallery.py

The page script is TypeScript (gallery/v4.ts). serve.py bundles it with Bun into
the previews root as v4.js at every start, and redirects the old pages (/,
/index.html, /live.html) into the suite. These tests start serve.py against a
pytest tmp_path as its previews root (GLOOMFELL_PREVIEW_ROOT), never the real
one, on a port the OS hands out. Windows hands those out from 49152 up, so
they never land on 8777 (the live gallery) or 8778/8779 (selftest.py's).
Nothing here runs Blender.
"""

import functools
import http.client
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time

import pytest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY = os.path.join(TOOLS, "gallery")
SERVE = os.path.join(TOOLS, "serve.py")
RESERVED_PORTS = {8777, 8778, 8779}
# A Chromium for the tests that need the page to run. Headless, with a profile
# of its own under tmp_path, so it never opens a window or touches a browser
# that's already running. GLOOMFELL_BROWSER points at another chrome/msedge.
BROWSERS = [os.environ.get("GLOOMFELL_BROWSER") or "",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]


def _load_serve():
    """serve.py as a module, loaded from its path so nothing goes on sys.path.

    Importing it only sets constants; the server starts in main().
    """
    spec = importlib.util.spec_from_file_location("gallery_serve", SERVE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert port not in RESERVED_PORTS
    return port


class Served:
    """serve.py running against `root` on a free port; .output once it has stopped."""

    def __init__(self, root, **env):
        self.root = str(root)
        self.port = _free_port()
        self.env = dict(os.environ, GLOOMFELL_PREVIEW_ROOT=self.root,
                        GLOOMFELL_GALLERY_PORT=str(self.port))
        self.env.pop("GLOOMFELL_BUN", None)     # only a test that means to set it does
        self.env.update(env)
        self.output = ""

    def __enter__(self):
        self.proc = subprocess.Popen([sys.executable, SERVE], env=self.env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     encoding="utf-8", errors="replace")
        deadline = time.time() + 30
        while True:
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.5).close()
                return self
            except OSError:
                if self.proc.poll() is not None or time.time() > deadline:
                    self.__exit__(None, None, None)
                    pytest.fail("serve.py never came up:\n" + self.output)
                time.sleep(0.05)

    def __exit__(self, *exc):
        self.proc.terminate()
        try:
            self.output, _ = self.proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.output, _ = self.proc.communicate(timeout=5)

    def request(self, method, path, body=None):
        """One request, redirects NOT followed. Returns (status, headers, body bytes)."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            headers = {"Content-Type": "application/json"} if body is not None else {}
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            return resp.status, resp.msg, resp.read()
        finally:
            conn.close()

    def rendered(self, route, profile):
        """The DOM after the page has run for 6 s of virtual time at `route`."""
        browser = next((b for b in BROWSERS if b and os.path.isfile(b)), None)
        if not browser:
            pytest.skip("no Edge or Chrome to run the page in (set GLOOMFELL_BROWSER)")
        r = subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-first-run",
             "--no-default-browser-check", "--disable-extensions",
             "--user-data-dir=" + str(profile), "--virtual-time-budget=6000",
             "--dump-dom", "http://127.0.0.1:%d%s" % (self.port, route)],
            capture_output=True, encoding="utf-8", errors="replace", timeout=120)
        return r.stdout


# ------------------------------------------------------------------ the source


def test_page_loads_the_bundle_and_has_no_inline_script():
    """The page's only script is the bundle, loaded as a module after its DOM."""
    with open(os.path.join(GALLERY, "v4.html"), encoding="utf-8") as fh:
        page = fh.read()
    assert page.count("<script") == 1
    tag = '<script type="module" src="v4.js"></script>'
    assert tag in page
    # after the DOM it reads: the last dialog closes before the script loads
    assert page.index("</dialog>", page.index('id="shortcuts"')) < page.index(tag)


def test_gallery_holds_sources_only():
    """The stubs are gone and no build output sits beside the sources."""
    names = set(os.listdir(GALLERY))
    assert {"v4.html", "v4.ts"} <= names
    assert not names & {"index.html", "live.html", "index.html.meta"}
    assert not _build_output_in(GALLERY)


def _build_output_in(folder):
    return [n for n in os.listdir(folder) if n.endswith((".js", ".js.map", ".js.part"))]


# ------------------------------------------------------------------ the bundle


def test_bundle_builds_from_v4_ts(tmp_path):
    serve = _load_serve()
    assert serve.build_bundle(str(tmp_path)) is None
    bundle = tmp_path / "v4.js"
    text = bundle.read_text(encoding="utf-8")
    assert "window.__gf = S" in text          # the suite's own debugging seam
    assert "interface " not in text           # types stripped
    # just the bundle and its map: the build folder is gone
    assert sorted(os.listdir(tmp_path)) == ["v4.js", "v4.js.map"]
    # and nothing was written beside the sources (bun 1.4.3 does that with a
    # source map unless it runs from the build folder)
    assert not _build_output_in(GALLERY)


def test_bundle_links_a_source_map_of_v4_ts(tmp_path):
    assert _load_serve().build_bundle(str(tmp_path)) is None
    text = (tmp_path / "v4.js").read_text(encoding="utf-8")
    assert text.rstrip().endswith("//# sourceMappingURL=v4.js.map")
    smap = json.loads((tmp_path / "v4.js.map").read_text(encoding="utf-8"))
    # named by its place under _tools/, not by a path out of the previews root
    assert smap["sources"] == ["gallery/v4.ts"]
    with open(os.path.join(GALLERY, "v4.ts"), encoding="utf-8") as fh:
        assert smap["sourcesContent"] == [fh.read()]   # devtools need nothing else
    assert smap["mappings"]


def test_bundle_parses_as_javascript(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node isn't on PATH")
    assert _load_serve().build_bundle(str(tmp_path)) is None
    r = subprocess.run([node, "--check", str(tmp_path / "v4.js")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_failed_build_is_reported_and_leaves_nothing(tmp_path):
    """A bundle that doesn't build comes back as bun's error, and the old bundle goes."""
    serve = _load_serve()
    src = tmp_path / "src"
    src.mkdir()
    (src / "v4.ts").write_text("const broken: number = ;\n", encoding="utf-8")
    dest = tmp_path / "root"
    dest.mkdir()
    (dest / "v4.js").write_text("// last week's bundle\n", encoding="utf-8")
    (dest / "v4.js.map").write_text("{}", encoding="utf-8")
    error = serve.build_bundle(str(dest), str(src))
    assert error and error.startswith("bun build failed")
    assert "Unexpected" in error              # bun's own message comes through
    assert os.listdir(dest) == []
    assert os.listdir(src) == ["v4.ts"]


# ------------------------------------------------------------------ the server


def test_served_page_gets_a_fresh_v4_js(tmp_path):
    (tmp_path / "v4.js").write_text("// stale bundle from an earlier start\n", encoding="utf-8")
    with Served(tmp_path) as srv:
        status, _, page = srv.request("GET", "/v4.html")
        assert status == 200
        assert b'<script type="module" src="v4.js"></script>' in page
        assert b"page script not built" not in page
        status, headers, js = srv.request("GET", "/v4.js")
        assert status == 200
        # module scripts are refused unless served as JavaScript
        assert headers.get("Content-Type", "").startswith("text/javascript")
        assert headers.get("Cache-Control") == "no-store"
        assert b"stale bundle" not in js and b"window.__gf = S" in js
        assert js == (tmp_path / "v4.js").read_bytes()
        status, headers, smap = srv.request("GET", "/v4.js.map")
        assert status == 200
        assert headers.get("Content-Type") == "application/json"
        assert json.loads(smap)["sources"] == ["gallery/v4.ts"]
    assert "script:  v4.js, bundled from gallery/v4.ts" in srv.output
    # the stubs aren't copied into a fresh root any more
    assert not {"index.html", "live.html"} & set(os.listdir(tmp_path))


# Every old URL and where it now lands. The stubs read ?asset= with
# URLSearchParams.get() and wrote it into the hash with encodeURIComponent(),
# so '+' is a space and !'()* stay as they are; an empty asset means no route.
REDIRECTS = [
    ("/", "/v4.html"),
    ("/?asset=knight000", "/v4.html#/a/knight000"),
    ("/index.html", "/v4.html"),
    ("/index.html?asset=mage000", "/v4.html#/a/mage000"),
    ("/index.html?asset=a+b%2Fc", "/v4.html#/a/a%20b%2Fc"),
    ("/index.html?asset=x%27(y)*!", "/v4.html#/a/x'(y)*!"),
    ("/index.html?other=1&asset=mage000&asset=second", "/v4.html#/a/mage000"),
    ("/live.html", "/v4.html"),
    ("/live.html?asset=", "/v4.html"),
    ("/live.html?asset=mage000", "/v4.html#/a/mage000/live"),
]


def test_old_pages_redirect_into_the_suite(tmp_path):
    with Served(tmp_path) as srv:
        for path, where in REDIRECTS:
            for method in ("GET", "HEAD"):
                status, headers, body = srv.request(method, path)
                assert (status, headers.get("Location")) == (302, where), (method, path)
                assert headers.get("Cache-Control") == "no-store", (method, path)
                assert body == b""
        # anything else is still a plain file request
        assert srv.request("GET", "/v4.html")[0] == 200
        assert srv.request("GET", "/nothing-here.html")[0] == 404


def test_missing_bun_is_reported_and_no_stale_bundle_is_served(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "v4.js").write_text("// stale bundle from an earlier start\n", encoding="utf-8")
    (root / "v4.js.map").write_text("{}", encoding="utf-8")
    nowhere = str(tmp_path / "no-bun-here" / "bun.exe")
    with Served(root, GLOOMFELL_BUN=nowhere) as srv:
        assert srv.request("GET", "/v4.js")[0] == 404
        assert srv.request("GET", "/v4.js.map")[0] == 404
        status, _, page = srv.request("GET", "/v4.html")
        assert status == 200
        assert b'role="alert">page script not built: bun not found at' in page
        # the data doors still work without the page (tmp_path, never the live root)
        assert srv.request("POST", "/chat", body=b'{"text": "still here"}')[0] == 204
    assert "!! PAGE SCRIPT NOT BUILT" in srv.output
    assert "bun not found at " + nowhere in srv.output
    assert "script:  NOT BUILT, see above" in srv.output


def test_console_never_chokes_on_what_it_reports(tmp_path):
    """A redirected stdout on Windows is cp1252; what serve.py reports may not fit it.

    Bun's errors quote v4.ts source lines, which are full of characters like the
    arrows; here a bun path with one stands in for them.
    """
    root = tmp_path / "root"
    root.mkdir()
    nowhere = str(tmp_path / "bün→here" / "bun.exe")
    with Served(root, GLOOMFELL_BUN=nowhere, PYTHONIOENCODING="cp1252") as srv:
        status, _, page = srv.request("GET", "/v4.html")
        assert status == 200
        assert "bün→here".encode("utf-8") in page   # the page itself is UTF-8
    assert "bun not found at " in srv.output
    assert "suite:   http://localhost:%d/v4.html" % srv.port in srv.output


# ------------------------------------------------------------------ the page


def _manifest(run, chips):
    """A preview.py manifest with one variant carrying `chips`."""
    return {"asset": "chiptest", "run": run, "started": "2026-10-24T10:00:00", "done": True,
            "tag": None, "seed": 1, "audit": None,
            "variants": [{"n": 1, "label": "baseline", "diff": {}, "renders": [], "exit": 0,
                          "seconds": 1.5, "stderr_tail": "", "clauses": [], "sheet": None,
                          "chips": chips}]}


def test_compare_tab_shows_chip_names_with_details(tmp_path):
    """chips.py writes {chip, detail} objects into manifests; the Compare tab shows
    the name with the detail as its tooltip, in the current run and in history,
    and a plain-string chip still shows as itself."""
    root = tmp_path / "root"
    asset = root / "chiptest"
    (asset / "run-002").mkdir(parents=True)
    latest = _manifest(3, [{"chip": "INV-4 detached", "detail": "cape left the body",
                            "blocks_auto": True}, "inert"])
    (asset / "latest.json").write_text(json.dumps(latest), encoding="utf-8")
    older = _manifest(2, [{"chip": "INV-2 lean", "detail": "leans 9 degrees"}])
    (asset / "run-002" / "manifest.json").write_text(json.dumps(older), encoding="utf-8")
    with Served(root) as srv:
        dom = srv.rendered("/v4.html#/a/chiptest/compare", tmp_path / "profile")
    assert 'id="cmp-head"' in dom, "the Compare tab never rendered:\n" + dom[-2000:]
    assert '<span class="chip amber" title="cape left the body">INV-4 detached</span>' in dom
    assert '<span class="chip amber">inert</span>' in dom
    assert '<span class="chip amber" title="leans 9 degrees">INV-2 lean</span>' in dom
    assert "[object Object]" not in dom


# ------------------------------------------------------- rebuilds while serving
# These drive serve.py's Suite in-process against a gallery of their own: a
# copy of the real v4.html and a tiny v4.ts they can edit and break.

BROKEN_TS = "const broken: number = ;\n"


def _ts(marker):
    return "const marker: string = '%s';\nconsole.log(marker);\nexport {};\n" % marker


def _gallery(tmp_path, ts):
    src, root = tmp_path / "src", tmp_path / "root"
    src.mkdir()
    root.mkdir()
    shutil.copyfile(os.path.join(GALLERY, "v4.html"), src / "v4.html")
    (src / "v4.ts").write_text(ts, encoding="utf-8", newline="")
    return src, root


def _edit(path, text):
    """Rewrite a source with a clearly later mtime, whatever the clock's resolution."""
    later = os.stat(path).st_mtime_ns + 2_000_000_000
    path.write_text(text, encoding="utf-8", newline="")   # exactly these bytes, no CRLF
    os.utime(path, ns=(later, later))


def _count_builds(serve, monkeypatch, delay=0.0):
    """Every build_bundle call the Suite makes, optionally slowed to widen a race."""
    calls = []
    real = serve.build_bundle

    def counted(*args, **kwargs):
        calls.append(args)
        time.sleep(delay)
        return real(*args, **kwargs)

    monkeypatch.setattr(serve, "build_bundle", counted)
    return calls


def _text(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def test_v4_js_is_rebuilt_when_v4_ts_changes(tmp_path, monkeypatch, capsys):
    serve = _load_serve()
    src, root = _gallery(tmp_path, _ts("marker-alpha"))
    builds = _count_builds(serve, monkeypatch)
    suite = serve.Suite(str(root), str(src))
    assert suite.start() is None
    assert "marker-alpha" in _text(root / "v4.js")
    suite.refresh()
    suite.refresh()
    assert len(builds) == 1                   # nothing changed, nothing rebuilt
    _edit(src / "v4.ts", _ts("marker-beta"))
    suite.refresh()
    assert len(builds) == 2
    js = _text(root / "v4.js")
    assert "marker-beta" in js and "marker-alpha" not in js
    assert json.loads(_text(root / "v4.js.map"))["sourcesContent"] == [_ts("marker-beta")]
    assert "script:  v4.js rebuilt: gallery/v4.ts changed" in capsys.readouterr().out


def test_failed_rebuild_keeps_the_last_good_bundle(tmp_path, monkeypatch, capsys):
    serve = _load_serve()
    src, root = _gallery(tmp_path, _ts("marker-alpha"))
    builds = _count_builds(serve, monkeypatch)
    suite = serve.Suite(str(root), str(src))
    assert suite.start() is None
    _edit(src / "v4.ts", BROKEN_TS)
    suite.refresh()
    assert "marker-alpha" in _text(root / "v4.js")          # still the last good build
    assert (root / "v4.js.map").exists()
    page = _text(root / "v4.html")
    assert 'role="alert">page script not rebuilt: bun build failed' in page
    assert "This is the last good build" in page
    out = capsys.readouterr().out
    assert "!! PAGE SCRIPT NOT REBUILT: still serving the last good build" in out
    assert "Unexpected" in out                # bun's own message, in the log
    # the broken source isn't tried again on every request, only once it changes
    tried = len(builds)
    suite.refresh()
    suite.refresh()
    assert len(builds) == tried
    _edit(src / "v4.ts", _ts("marker-gamma"))
    suite.refresh()
    assert "marker-gamma" in _text(root / "v4.js")
    assert "page script not" not in _text(root / "v4.html")   # the banner goes with the fix


def test_a_failed_start_recovers_when_v4_ts_is_fixed(tmp_path, monkeypatch):
    serve = _load_serve()
    src, root = _gallery(tmp_path, BROKEN_TS)
    suite = serve.Suite(str(root), str(src))
    assert suite.start().startswith("bun build failed")
    assert not (root / "v4.js").exists()
    assert 'role="alert">page script not built:' in _text(root / "v4.html")
    _edit(src / "v4.ts", _ts("marker-alpha"))
    suite.refresh()
    assert "marker-alpha" in _text(root / "v4.js")
    assert "page script not" not in _text(root / "v4.html")


def test_a_burst_of_requests_after_an_edit_rebuilds_once(tmp_path, monkeypatch):
    serve = _load_serve()
    src, root = _gallery(tmp_path, _ts("marker-alpha"))
    builds = _count_builds(serve, monkeypatch, delay=0.3)   # a slow build: a wide race
    suite = serve.Suite(str(root), str(src))
    assert suite.start() is None
    _edit(src / "v4.ts", _ts("marker-beta"))
    gate = threading.Barrier(8)

    def request():
        gate.wait()
        suite.refresh()

    threads = [threading.Thread(target=request) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert len(builds) == 2                   # the start, and one rebuild for all eight
    assert "marker-beta" in _text(root / "v4.js")


def test_v4_html_is_copied_again_when_it_changes(tmp_path, monkeypatch, capsys):
    serve = _load_serve()
    src, root = _gallery(tmp_path, _ts("marker-alpha"))
    builds = _count_builds(serve, monkeypatch)
    suite = serve.Suite(str(root), str(src))
    assert suite.start() is None
    _edit(src / "v4.html", _text(src / "v4.html") + "<!-- edited -->\n")
    suite.refresh()
    assert _text(root / "v4.html").endswith("<!-- edited -->\n")
    assert len(builds) == 1                   # the page alone: no rebuild
    assert "page:    v4.html copied again: it changed" in capsys.readouterr().out


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        assert resp.status == 200, (path, resp.status)
        return resp.read()
    finally:
        conn.close()


def test_requests_for_the_page_bring_it_up_to_date(tmp_path):
    """Over HTTP: a request for v4.js or v4.html picks up an edit; others don't look."""
    serve = _load_serve()
    src, root = _gallery(tmp_path, _ts("marker-alpha"))
    suite = serve.Suite(str(root), str(src))
    assert suite.start() is None
    port = _free_port()
    httpd = serve.Server(("127.0.0.1", port),
                         functools.partial(serve.QuietHandler, directory=str(root)))
    httpd.suite = suite
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        assert b"marker-alpha" in _get(port, "/v4.js")
        _edit(src / "v4.ts", _ts("marker-beta"))
        assert b"marker-beta" in _get(port, "/v4.js")
        _edit(src / "v4.html", _text(src / "v4.html") + "<!-- edited -->\n")
        assert _get(port, "/v4.html").endswith(b"<!-- edited -->\n")
        # the 1 Hz JSON polls never touch the sources
        (root / "assets.json").write_text("[]", encoding="utf-8")
        _edit(src / "v4.ts", _ts("marker-gamma"))
        _get(port, "/assets.json")
        assert "marker-beta" in _text(root / "v4.js")
        assert b"marker-gamma" in _get(port, "/v4.js.map")
    finally:
        httpd.shutdown()
        httpd.server_close()


# ------------------------------------------------------------------ old copies


def test_stale_page_copies_are_removed_at_startup(tmp_path):
    """Starts before 2026-10-24 copied index.html and live.html into the root;
    serve.py deletes those two, at the top of its own root, and nothing else."""
    root = tmp_path / "root"
    (root / "mage000").mkdir(parents=True)
    for name in ("index.html", "live.html", "keep.html", "index.htm"):
        (root / name).write_text("<p>old</p>", encoding="utf-8")
    for name in ("index.html", "live.html"):
        (root / "mage000" / name).write_text("<p>an asset's own</p>", encoding="utf-8")
    (root / "live.html.bak").mkdir()          # a folder by a similar name stays too
    neighbour = tmp_path / "index.html"       # outside the root: not this server's
    neighbour.write_text("<p>not ours</p>", encoding="utf-8")
    with Served(root) as srv:
        assert srv.request("GET", "/index.html")[0] == 302   # still a redirect
    top = set(os.listdir(root))
    assert not top & {"index.html", "live.html"}
    assert {"keep.html", "index.htm", "mage000", "live.html.bak"} <= top
    assert sorted(os.listdir(root / "mage000")) == ["index.html", "live.html"]
    assert neighbour.exists()
    assert "removed: index.html, live.html" in srv.output


def test_a_root_without_old_copies_says_nothing_about_them(tmp_path):
    with Served(tmp_path) as srv:
        pass
    assert "removed:" not in srv.output
