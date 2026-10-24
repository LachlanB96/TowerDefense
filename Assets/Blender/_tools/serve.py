"""Serve the preview gallery. Start once, leave running.

    python Assets/Blender/_tools/serve.py

Then open http://localhost:8777/v4.html and leave the tab open on a second monitor.

Nearly a stock http.server: the gallery is view-only except for ONE write
endpoint, POST /signal, which appends the user's star/cross reactions to
<asset>/user-signals.jsonl. That file is calibration ground truth for the
modelling pipeline (the orchestrator stamps reactions into attempt rows; the
supervisor reports panel-vs-user agreement at finish) — it never gates a
verdict and it is never control.json, which stays the supervisor's file alone.

The suite lives in source control under _tools/gallery/: the page (v4.html)
and its script (v4.ts, TypeScript). Every start copies the page into the
previews root, so relative image paths just work, and bundles the script there
as v4.js with Bun, with a linked source map (v4.js.map) for devtools. A request
for the page or its script redoes either when its source has changed since, so
an edit needs a reload, not a restart. The bundle is build output: it is never
written under _tools/ and never committed. The old pages (/, /index.html,
/live.html) are redirects into the suite, and the copies of them that earlier
starts left in the previews root are deleted at startup.
"""

import functools
import html
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
GALLERY = os.path.join(HERE, "gallery")
# Overridable so a second instance can serve scratch fixtures on another port
# without touching the live previews root (suite verification, spec 2026-08-12).
PREVIEW_ROOT = (os.environ.get("GLOOMFELL_PREVIEW_ROOT")
                or os.path.join(os.path.dirname(HERE), "_previews~"))
PORT = int(os.environ.get("GLOOMFELL_GALLERY_PORT", "8777"))

ASSET_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")   # path-traversal guard
MARKS = {"star", "cross", "clear"}
# Directives are INSTRUCTIONS, not taste data, so they get their own file and
# endpoint — an instruction must never arrive through the same door as a
# status signal. The orchestrator reads user-directives.jsonl at the top of
# every cycle and acknowledges each one in the iteration log.
DIRECTIVES = {"rework", "revert", "resurrect", "withdraw"}
# /chat is the user's one free-text door (modev4's mission-control page).
# Replies (feed.jsonl) are written by the supervisor process directly, never
# through HTTP, so everything in chat.jsonl is user-authored by construction.

# The old pages, now redirects into the suite: path -> the suite tab it maps
# ?asset=<name> onto. index.html (the v1-v3 gallery, also what / served) and
# live.html (v3's live view) were stub files doing this in the browser until
# 2026-10-24; with the stubs gone, / would otherwise be a directory listing.
LEGACY_PAGES = {"/": "", "/index.html": "", "/live.html": "/live"}
# The copies of those stubs that every start before then left in the previews
# root. The redirects make them unreachable, so they're only clutter that looks
# current; remove_stale_pages() deletes these two names and nothing else.
STALE_PAGES = ("index.html", "live.html")

# The page script is TypeScript, and browsers run JavaScript, so it is bundled
# at every start with the Bun the megaproject pins in ~/AI/.typescript (its
# `npm ci` restores it). The repo sits at <megaproject>/GloomFell, so that is
# <repo>/../.typescript. A worktree (<repo>/.claude/worktrees/<name>) finds it
# through the .typescript junction beside it, or else through the main
# checkout, worked out the way the Blender scripts work out _REPO.
# GLOOMFELL_BUN points at another bun.exe.
_REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
_MAIN_REPO = _REPO.split(os.sep + os.path.join(".claude", "worktrees") + os.sep)[0]
TS_DIR = os.path.join(os.path.dirname(_MAIN_REPO), ".typescript")
_BUN_IN_TS = os.path.join("node_modules", "@oven", "bun-windows-x64", "bin", "bun.exe")
BUNDLE = "v4.js"
SOURCE_MAP = BUNDLE + ".map"     # linked from the bundle, so devtools show v4.ts


def find_bun():
    """The bun.exe to bundle with: GLOOMFELL_BUN, else the megaproject's pinned copy.

    Returns a path even when nothing is there, so the error can say where it looked.
    """
    override = os.environ.get("GLOOMFELL_BUN")
    if override:
        return override
    candidates = [os.path.join(os.path.dirname(_REPO), ".typescript", _BUN_IN_TS),
                  os.path.join(TS_DIR, _BUN_IN_TS)]
    return next((c for c in candidates if os.path.isfile(c)), candidates[0])


def _replace(src, dst):
    """os.replace, retried briefly: on Windows it fails while a request thread
    has the old bundle open (see preview.py's _atomic_json)."""
    for attempt in range(1, 4):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 3:
                raise
            time.sleep(0.05)


def _tidy_map(path, src_dir):
    """Name each source in the map by its path under _tools/ (gallery/v4.ts).

    Bun writes them relative to the build folder, which climbs out of the previews
    root and spells out where the checkout lives. The map carries the source text
    itself (sourcesContent), so the name is all devtools uses it for: the tree it
    files the source under.
    """
    with open(path, encoding="utf-8") as fh:
        smap = json.load(fh)
    base, build_dir = os.path.dirname(os.path.abspath(src_dir)), os.path.dirname(path)
    names = []
    for s in smap.get("sources") or []:
        full = os.path.normpath(os.path.join(build_dir, s))
        try:
            names.append(os.path.relpath(full, base).replace(os.sep, "/"))
        except ValueError:                    # another drive: no relative path exists
            names.append(os.path.basename(full))
    smap["sources"] = names
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(smap, fh, separators=(",", ":"))


def build_bundle(dest_dir, src_dir=None, keep_last_good=False):
    """Bundle <src_dir>/v4.ts (gallery/ by default) into <dest_dir>/v4.js, with a
    linked source map beside it, v4.js.map. Returns None, or what went wrong.

    When the build fails, keep_last_good=False (a start) deletes the bundle and map
    an earlier start left: a page that says its script is missing beats one that
    quietly runs an old script. keep_last_good=True (a rebuild after an edit) leaves
    the last good build this server made in place.
    """
    src_dir = src_dir or GALLERY
    out, map_out = os.path.join(dest_dir, BUNDLE), os.path.join(dest_dir, SOURCE_MAP)
    bun = find_bun()
    error = None
    if not os.path.isfile(bun):
        error = ("bun not found at %s. Restore it with: npm ci --prefix \"%s\" "
                 "(or point GLOOMFELL_BUN at a bun.exe)" % (bun, TS_DIR))
    else:
        # Bun builds into a folder of its own in the previews root, run from inside
        # it: with a source map, bun 1.4.3 ignores --outfile's folder and writes
        # into its working directory (it once put v4.js and v4.js.map in
        # _tools/gallery/). The finished files are then swapped in, so no request
        # ever sees half a file. The folder never holds a latest.json, so
        # preview.py's assets.json never lists it.
        work = None
        try:
            work = tempfile.mkdtemp(prefix="_suite-build-", dir=dest_dir)
            r = subprocess.run(
                [bun, "build", os.path.join(src_dir, "v4.ts"), "--outdir", work,
                 "--target", "browser", "--format", "esm", "--sourcemap=linked"],
                cwd=work, capture_output=True, encoding="utf-8", errors="replace",
                timeout=120, env=dict(os.environ, NO_COLOR="1"),
                # no console window flashing up when serve.py itself has none
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            built, built_map = os.path.join(work, BUNDLE), os.path.join(work, SOURCE_MAP)
            if r.returncode != 0 or not (os.path.isfile(built) and os.path.isfile(built_map)):
                error = "bun build failed (exit %d):\n%s" % (
                    r.returncode, (r.stderr.strip() or r.stdout.strip() or "(no output)"))
            else:
                _tidy_map(built_map, src_dir)
                _replace(built_map, map_out)  # map first: v4.js never names a map that isn't there
                _replace(built, out)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            error = "bun build could not run: %s" % exc
        finally:
            if work:
                shutil.rmtree(work, ignore_errors=True)
    if error and not keep_last_good:
        for stale in (out, map_out):
            if os.path.exists(stale):
                os.remove(stale)
    return error


def install_page(dest_dir, banner=None, src_dir=None):
    """Copy v4.html into the previews root, with `banner` across its top if given.

    The banner says what's wrong with the page's script. Without the script the
    page is an empty frame (or an old one), and whoever is looking at it may never
    see this server's console. Swapped in like the bundle, so no request sees half
    a page.
    """
    src = os.path.join(src_dir or GALLERY, "v4.html")
    dst = os.path.join(dest_dir, "v4.html")
    with open(src, encoding="utf-8", newline="") as fh:
        page = fh.read()
    if banner:
        page = page.replace('<div id="net"', '<div class="banner on" role="alert">%s</div>\n'
                            '<div id="net"' % html.escape(banner, quote=False), 1)
    part = dst + ".part"
    with open(part, "w", encoding="utf-8", newline="") as fh:
        fh.write(page)
    _replace(part, dst)


def remove_stale_pages(root):
    """Delete the old pages' copies from the top of `root`. Returns the names removed.

    Only index.html and live.html, only as files directly in the previews root
    this server serves: an asset folder's own files are never touched.
    """
    removed = []
    for name in STALE_PAGES:
        path = os.path.join(root, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
                removed.append(name)
            except OSError as exc:
                _say("could not remove the stale %s: %s" % (path, exc))
    return removed


def _sig(path):
    """What a cheap look says about a file: (mtime_ns, size), or None when it's gone."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size


def _say(*lines):
    # flush: stdout is normally redirected to a file; without it these lines
    # sit in the block buffer for the life of the process
    for line in lines:
        print(line, flush=True)


class Suite:
    """The page and its script in a previews root, kept in step with their sources.

    start() builds both once. refresh() runs before every request for v4.html,
    v4.js or v4.js.map and redoes whatever changed since this server last built
    (or tried to build) it: v4.ts, or the bun it builds with, means a rebuild;
    v4.html means a fresh copy. When nothing changed that's a few stat calls.
    "Changed" rather than "newer": a checkout or copy can give a file an older
    time. One lock, and a second look inside it, mean a burst of requests after
    an edit costs one rebuild, not one each; a source that failed to build isn't
    tried again until it changes again.
    """
    PATHS = {"/v4.html", "/" + BUNDLE, "/" + SOURCE_MAP}

    def __init__(self, root, src_dir=None):
        self.root = root
        self.src = src_dir or GALLERY
        self.lock = threading.Lock()
        self.script_key = None    # v4.ts and bun, as the bundle was last built (or tried) from
        self.page_key = None      # v4.html, as last copied
        self.built = False        # the root holds a bundle this server built
        self.banner = None        # what the page says about its script, when something's wrong

    def _keys(self):
        return ((_sig(os.path.join(self.src, "v4.ts")), _sig(find_bun())),
                _sig(os.path.join(self.src, "v4.html")))

    def start(self):
        """Build the bundle and copy the page. Returns None, or why the build failed."""
        with self.lock:
            script_key, page_key = self._keys()
            error = self._build(script_key, keep_last_good=False)
            self._copy(page_key)
            return error

    def refresh(self):
        if self._keys() == (self.script_key, self.page_key):
            return
        with self.lock:
            script_key, page_key = self._keys()   # another request may have done it meanwhile
            banner = self.banner
            if script_key != self.script_key:
                if self._build(script_key, keep_last_good=self.built) is None:
                    _say("script:  %s rebuilt: gallery/v4.ts changed" % BUNDLE)
            if page_key != self.page_key:
                _say("page:    v4.html copied again: it changed")
            if page_key != self.page_key or self.banner != banner:
                self._copy(page_key)

    def _build(self, script_key, keep_last_good):
        error = build_bundle(self.root, self.src, keep_last_good)
        self.script_key = script_key
        if error is None:
            self.built, self.banner = True, None
            return None
        first = error.splitlines()[0]
        if keep_last_good:
            self.banner = ("page script not rebuilt: %s. This is the last good build; fix it "
                           "and reload. serve.py's console has the details." % first)
            headline = "PAGE SCRIPT NOT REBUILT: still serving the last good build"
        else:
            self.built = False
            self.banner = ("page script not built: %s. Fix it and reload; serve.py's console "
                           "has the details." % first)
            headline = "PAGE SCRIPT NOT BUILT: the suite will load as an empty frame"
        _say("!! " + headline, *["!!   " + line for line in error.splitlines()])
        _say("!! Fix that and reload the page: serve.py rebuilds when v4.ts or bun changes.")
        return error

    def _copy(self, page_key):
        install_page(self.root, self.banner, self.src)
        self.page_key = page_key


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    # Pinned rather than left to mimetypes, which reads the Windows registry:
    # where some installer has set .js to text/plain, the browser would refuse
    # the page's script, because module scripts get a strict MIME check. A
    # source map is JSON; mimetypes doesn't know .map at all.
    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map,
                          **{".js": "text/javascript", ".map": "application/json"})

    def log_message(self, fmt, *args):
        pass          # a 1 Hz poll would otherwise flood the console

    def end_headers(self):
        # The manifest changes several times within a run; never let it cache.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if not self._redirect_legacy():
            self._refresh_suite()
            super().do_GET()

    def do_HEAD(self):
        if not self._redirect_legacy():
            self._refresh_suite()
            super().do_HEAD()

    def _refresh_suite(self):
        """Bring the page and its script up to date before serving either of them."""
        suite = getattr(self.server, "suite", None)
        if suite is None or urllib.parse.urlsplit(self.path).path not in Suite.PATHS:
            return
        try:
            suite.refresh()
        except Exception as exc:     # a rebuild gone wrong must not take the request with it
            _say("!! bringing the page up to date failed: %r" % (exc,))

    def _redirect_legacy(self):
        """Send an old page's URL into the suite, as its stub file used to.

        ?asset=<name> becomes the suite's #/a/<name> route (#/a/<name>/live from
        live.html), read like URLSearchParams.get() and encoded like
        encodeURIComponent(), which is what the stubs used. 302, not 301, and
        no-store like every response, so no browser keeps the redirect.
        """
        url = urllib.parse.urlsplit(self.path)
        tab = LEGACY_PAGES.get(url.path)
        if tab is None:
            return False
        asset = (urllib.parse.parse_qs(url.query).get("asset") or [""])[0]
        where = "/v4.html"
        if asset:
            where += "#/a/" + urllib.parse.quote(asset, safe="!'()*") + tab
        self.send_response(302)
        self.send_header("Location", where)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def do_POST(self):
        if self.path == "/chat":
            return self._post_chat()
        route = {"/signal": ("mark", MARKS, "user-signals.jsonl"),
                 "/directive": ("directive", DIRECTIVES, "user-directives.jsonl")}.get(self.path)
        if not route:
            self.send_error(404)
            return
        field, allowed, fname = route
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 65536)
            body = json.loads(self.rfile.read(n))
            asset = body["asset"]
            value = body[field]
            if not ASSET_RE.match(asset) or value not in allowed:
                raise ValueError("bad asset or %s" % field)
            rec = {
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "asset": asset,
                "attempt": str(body.get("attempt", ""))[:64],
                "design": str(body.get("design", ""))[:64],
                "run": str(body.get("run", ""))[:64],
                field: value,
                "note": str(body.get("note", ""))[:500],
            }
        except (KeyError, ValueError, json.JSONDecodeError):
            self.send_error(400)
            return
        path = os.path.join(PREVIEW_ROOT, asset, fname)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Append-only JSONL: one line per click, never rewritten, so a crash can
        # lose at most the line being written and the pipeline can tail it.
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.send_response(204)
        self.end_headers()

    def _post_chat(self):
        """Append one user chat line to the fleet-level chat.jsonl.

        The file is append-only JSONL like the signal files: a crash loses at
        most the line being written, and the supervisor can tail it. Everything
        in this file is user-authored by construction - the supervisor never
        writes here, so provenance is the file name.
        """
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 65536)
            body = json.loads(self.rfile.read(n))
            text = str(body["text"]).strip()
            if not text:
                raise ValueError("empty text")
            rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "from": "user",
                   "text": text[:2000]}
            asset = body.get("asset")
            if asset:
                if not ASSET_RE.match(asset):
                    raise ValueError("bad asset")
                rec["asset"] = asset
        except (KeyError, ValueError, json.JSONDecodeError):
            self.send_error(400)
            return
        os.makedirs(PREVIEW_ROOT, exist_ok=True)
        with open(os.path.join(PREVIEW_ROOT, "chat.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.send_response(204)
        self.end_headers()


class Server(socketserver.ThreadingTCPServer):
    """Threaded, so one slow or stalled request cannot freeze the whole gallery.

    The single-threaded TCPServer this replaced was fine while the page fetched a
    manifest now and then. The live pane polls once a second and the run strip pulls
    many images per view, and on a single thread one request that blocks - a large
    PNG still being written, a reader holding a file open - stalls every other one.

    daemon_threads so ctrl-c actually exits instead of waiting on open connections.
    """
    daemon_threads = True
    allow_reuse_address = True


def main():
    # stdout is usually a file or a pipe, which on Windows means cp1252. Bun's
    # errors quote v4.ts lines (full of characters like the arrows) and a path
    # can hold anything; neither may kill the server at startup.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    os.makedirs(PREVIEW_ROOT, exist_ok=True)
    # The page and its bundled script go into the previews root so the page's
    # relative image paths resolve: built now, and again whenever a request for
    # either finds its source changed. Never served from under _tools/, so what
    # the browser runs always matches v4.ts. A build that fails says so loudly
    # on stdout (beside the banner below, which is where people look) and on
    # the page, and the server still starts: the data files and the POST doors
    # work without the page, and the pipeline reads and writes through them.
    removed = remove_stale_pages(PREVIEW_ROOT)
    if removed:
        _say("removed: %s (copies of the old pages, which redirect now)" % ", ".join(removed))
    suite = Suite(PREVIEW_ROOT)
    bundle_error = suite.start()
    handler = functools.partial(QuietHandler, directory=PREVIEW_ROOT)
    with Server(("127.0.0.1", PORT), handler) as httpd:
        httpd.suite = suite
        _say("suite:   http://localhost:%d/v4.html   (/, /index.html, /live.html redirect here)" % PORT,
             "root:    %s" % PREVIEW_ROOT,
             "script:  %s" % ("NOT BUILT, see above" if bundle_error
                              else "%s, bundled from gallery/v4.ts" % BUNDLE))
        httpd.serve_forever()


if __name__ == "__main__":
    main()
