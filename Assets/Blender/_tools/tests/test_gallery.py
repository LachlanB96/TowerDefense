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

import http.client
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
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
    assert not [n for n in names if n.endswith((".js", ".js.part"))]


# ------------------------------------------------------------------ the bundle


def test_bundle_builds_from_v4_ts(tmp_path):
    serve = _load_serve()
    assert serve.build_bundle(str(tmp_path)) is None
    bundle = tmp_path / "v4.js"
    text = bundle.read_text(encoding="utf-8")
    assert "window.__gf = S" in text          # the suite's own debugging seam
    assert "interface " not in text           # types stripped
    assert sorted(os.listdir(tmp_path)) == ["v4.js"]   # no .part left behind
    # and nothing was written beside the sources
    assert not [n for n in os.listdir(GALLERY) if n.endswith((".js", ".js.part"))]


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
    serve.GALLERY = str(src)                  # build_bundle reads it at call time
    dest = tmp_path / "root"
    dest.mkdir()
    (dest / "v4.js").write_text("// last week's bundle\n", encoding="utf-8")
    error = serve.build_bundle(str(dest))
    assert error and error.startswith("bun build failed")
    assert "Unexpected" in error              # bun's own message comes through
    assert os.listdir(dest) == []


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
    nowhere = str(tmp_path / "no-bun-here" / "bun.exe")
    with Served(root, GLOOMFELL_BUN=nowhere) as srv:
        assert srv.request("GET", "/v4.js")[0] == 404
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
