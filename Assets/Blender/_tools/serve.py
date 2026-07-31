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
