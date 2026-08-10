"""Serve the preview gallery. Start once, leave running.

    python Assets/Blender/_tools/serve.py

Then open http://localhost:8777/ and leave the tab open on a second monitor.

Nearly a stock http.server: the gallery is view-only except for ONE write
endpoint, POST /signal, which appends the user's star/cross reactions to
<asset>/user-signals.jsonl. That file is calibration ground truth for the
modelling pipeline (the orchestrator stamps reactions into attempt rows; the
supervisor reports panel-vs-user agreement at finish) — it never gates a
verdict and it is never control.json, which stays the supervisor's file alone.
index.html lives in source control under _tools/ and is copied into the
previews root on start so that relative image paths just work.
"""

import functools
import http.server
import json
import os
import re
import shutil
import socketserver
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEW_ROOT = os.path.join(os.path.dirname(HERE), "_previews~")
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


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass          # a 1 Hz poll would otherwise flood the console

    def end_headers(self):
        # The manifest changes several times within a run; never let it cache.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

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
    os.makedirs(PREVIEW_ROOT, exist_ok=True)
    # Both pages live in source control under _tools/gallery/ and are copied into the
    # previews root at startup so their relative image paths resolve. live.html is a
    # SEPARATE page on purpose: index.html hands the whole page to iteration-log.json
    # whenever that file exists ("owns the page when present", per its own header), so
    # a live pane bolted into it would be invisible on any asset with a log.
    for page in ("index.html", "live.html", "v4.html"):
        src = os.path.join(HERE, "gallery", page)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(PREVIEW_ROOT, page))
    handler = functools.partial(QuietHandler, directory=PREVIEW_ROOT)
    with Server(("127.0.0.1", PORT), handler) as httpd:
        print("gallery: http://localhost:%d/      live: http://localhost:%d/live.html"
              % (PORT, PORT))
        httpd.serve_forever()


if __name__ == "__main__":
    main()
