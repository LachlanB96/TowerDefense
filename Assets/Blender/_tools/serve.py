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
as v4.js with Bun, so the served script is never older than its source. The
bundle is build output: it is never written under _tools/ and never committed.
The old pages (/, /index.html, /live.html) are redirects into the suite.
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


def build_bundle(dest_dir):
    """Bundle gallery/v4.ts into <dest_dir>/v4.js. Returns None, or what went wrong.

    A bundle left by an earlier start is deleted when this build fails: a page
    that says its script is missing beats one that quietly runs an old script.
    """
    out = os.path.join(dest_dir, BUNDLE)
    part = out + ".part"     # built beside it and swapped in, so no request sees half a file
    bun = find_bun()
    error = None
    if not os.path.isfile(bun):
        error = ("bun not found at %s. Restore it with: npm ci --prefix \"%s\" "
                 "(or point GLOOMFELL_BUN at a bun.exe)" % (bun, TS_DIR))
    else:
        try:
            r = subprocess.run(
                [bun, "build", os.path.join(GALLERY, "v4.ts"), "--outfile", part,
                 "--target", "browser", "--format", "esm"],
                cwd=GALLERY, capture_output=True, encoding="utf-8", errors="replace",
                timeout=120, env=dict(os.environ, NO_COLOR="1"),
                # no console window flashing up when serve.py itself has none
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode != 0 or not os.path.isfile(part):
                error = "bun build failed (exit %d):\n%s" % (
                    r.returncode, (r.stderr.strip() or r.stdout.strip() or "(no output)"))
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = "bun build could not run: %s" % exc
    if error:
        for stale in (part, out):
            if os.path.exists(stale):
                os.remove(stale)
        return error
    _replace(part, out)
    return None


def install_page(dest_dir, bundle_error):
    """Copy v4.html into the previews root, with a banner when its script didn't build.

    Without its script the page is an empty frame, and whoever is looking at it may
    never see this server's console, so the page says what happened too.
    """
    src, dst = os.path.join(GALLERY, "v4.html"), os.path.join(dest_dir, "v4.html")
    if not bundle_error:
        shutil.copyfile(src, dst)
        return
    with open(src, encoding="utf-8", newline="") as fh:
        page = fh.read()
    banner = ('<div class="banner on" role="alert">page script not built: %s. '
              'Fix it and restart serve.py; its console has the details.</div>\n'
              % html.escape(bundle_error.splitlines()[0]))
    with open(dst, "w", encoding="utf-8", newline="") as fh:
        fh.write(page.replace('<div id="net"', banner + '<div id="net"', 1))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    # Pinned rather than left to mimetypes, which reads the Windows registry:
    # where some installer has set .js to text/plain, the browser would refuse
    # the page's script, because module scripts get a strict MIME check.
    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map,
                          **{".js": "text/javascript"})

    def log_message(self, fmt, *args):
        pass          # a 1 Hz poll would otherwise flood the console

    def end_headers(self):
        # The manifest changes several times within a run; never let it cache.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if not self._redirect_legacy():
            super().do_GET()

    def do_HEAD(self):
        if not self._redirect_legacy():
            super().do_HEAD()

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
    # relative image paths resolve. Rebuilt on every start, never served from
    # under _tools/, so what the browser runs always matches v4.ts.
    bundle_error = build_bundle(PREVIEW_ROOT)
    install_page(PREVIEW_ROOT, bundle_error)
    # flush: stdout is normally redirected to a file; without it these lines
    # sit in the block buffer for the life of the process
    if bundle_error:
        # Loud, and on stdout beside the banner, which is where people look.
        # The server still starts: the data files and the POST doors work
        # without the page, and the pipeline reads and writes through them.
        print("!! PAGE SCRIPT NOT BUILT: the suite will load as an empty frame", flush=True)
        for line in bundle_error.splitlines():
            print("!!   " + line, flush=True)
        print("!! Fix that and restart serve.py.", flush=True)
    handler = functools.partial(QuietHandler, directory=PREVIEW_ROOT)
    with Server(("127.0.0.1", PORT), handler) as httpd:
        print("suite:   http://localhost:%d/v4.html   (/, /index.html, /live.html redirect here)" % PORT,
              flush=True)
        print("root:    %s" % PREVIEW_ROOT, flush=True)
        print("script:  %s" % ("NOT BUILT, see above" if bundle_error
                               else "%s, bundled from gallery/v4.ts" % BUNDLE), flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
