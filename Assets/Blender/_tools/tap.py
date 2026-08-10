"""Watch the previews root and publish a small live.json for the live page.

    python Assets/Blender/_tools/tap.py mage000              # follow one asset
    python Assets/Blender/_tools/tap.py mage000 knight000    # follow the fleet
    python Assets/Blender/_tools/tap.py mage000 --once       # one snapshot, then exit

One process follows the whole fleet (modev4 runs several assets at once); the
supervisor restarts it when the active-asset set changes. Each asset publishes
to its own <asset>/live.json exactly as before.

Runs in SYSTEM Python as its OWN PROCESS, deliberately.

WHY A SEPARATE PROCESS
----------------------
`serve.py` is a single-threaded `socketserver.TCPServer`. Anything that blocks inside a
handler blocks the whole gallery - that is not hypothetical, an unredirected startup
`print` once left the port listening while every request hung. So the tap never runs
inside the server: it writes a small file, and the server serves that file like any
other static asset. A crash here costs the live pane and nothing else.

WHAT IT SURFACES
----------------
Every run directory, including the ones no attempt ever claimed. Measured on this
project: 403 run directories against 84 logged attempts, so roughly four out of five
renders were paid for and never seen by anyone. The log's own note explains why
self-reporting failed - "a modeller renders many intermediates and the newest run at any
moment is usually not the attempt" - which is why attribution now comes from
`preview.py --tag`, stamped into manifest.json at render time, rather than from a
promise to report afterwards.

Discarded intermediates are the point, not a side effect: they are what the user asked
to be able to watch.

DELIBERATELY NOT HERE
---------------------
Judge reasoning. A judge's verdict may be shown once it lands; its in-progress thinking
must not be, because a live window into a judge invites steering it, and the blind
comparison is the one instrument on this project with a passing calibration probe behind
it. Watch the maker, not the referee.
"""

import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)
PREVIEW_ROOT = os.path.join(BLENDER_DIR, "_previews~")

RUN_RE = re.compile(r"^run-(\d+)$")
IDLE_S = 5.0          # quiet cadence
BUSY_S = 1.0          # cadence while a run is still being written
KEEP_RUNS = 60        # newest N runs published; the page is a strip, not an archive


def _read_json(path):
    """Best-effort read of a file another process may be rewriting.

    preview.py rewrites manifest.json as each variant lands, so a read can land
    mid-write. A partial read is normal and transient - return None and pick it up on
    the next tick rather than crashing the tap or showing an error to the user.
    """
    try:
        with open(path, encoding="utf-8") as fh:      # utf-8: Windows defaults to cp1252
            return json.load(fh)
    except (OSError, ValueError):
        return None


def scan(root, asset, keep=KEEP_RUNS):
    """Build the live payload for one asset from whatever is on disk right now."""
    adir = os.path.join(root, asset)
    if not os.path.isdir(adir):
        return {"asset": asset, "error": "no such asset directory", "runs": []}

    runs = []
    for name in os.listdir(adir):
        m = RUN_RE.match(name)
        if not m:
            continue
        rdir = os.path.join(adir, name)
        man = _read_json(os.path.join(rdir, "manifest.json")) or {}
        variants = []
        for v in (man.get("variants") or []):
            vdir = os.path.join(rdir, "v%d" % v.get("n", 1))
            shots = []
            if os.path.isdir(vdir):
                # The mask companions are diagnostic, not something to look at.
                shots = sorted(f for f in os.listdir(vdir)
                               if f.endswith(".png") and not f.endswith("_mask.png"))
            variants.append({
                "n": v.get("n"),
                "label": v.get("label"),
                "exit": v.get("exit"),
                "secs": v.get("secs"),
                "shots": ["%s/v%d/%s" % (name, v.get("n", 1), s) for s in shots],
            })
        runs.append({
            "run": int(m.group(1)),
            "dir": name,
            "started": man.get("started"),
            "done": man.get("done"),
            # Attribution and stimulus, stamped at render time by preview.py. A run with
            # no tag is an intermediate nobody claimed - show it anyway, flagged.
            "tag": man.get("tag"),
            "seed": man.get("seed"),
            "audit": man.get("audit"),
            "claimed": bool(man.get("tag")),
            "variants": variants,
        })

    runs.sort(key=lambda r: -r["run"])
    return {
        "asset": asset,
        "root": os.path.abspath(root),
        "stamped": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_runs": len(runs),
        "unclaimed_runs": sum(1 for r in runs if not r["claimed"]),
        "runs": runs[:keep],
    }


def publish(payload, out_path):
    """Atomic-ish write, with retries for the Windows sharing-violation case.

    os.replace onto a path a reader holds open raises WinError 5 on Windows. The reader
    (serve.py) opens, reads and closes quickly, so a short retry loop is enough; failing
    to publish one tick is harmless because the next tick republishes everything.
    """
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    for _ in range(10):
        try:
            os.replace(tmp, out_path)
            return True
        except OSError:
            time.sleep(0.05)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("assets", nargs="+")
    ap.add_argument("--root", help="previews root (default: the repo's _previews~)")
    ap.add_argument("--once", action="store_true", help="one snapshot, then exit")
    ap.add_argument("--keep", type=int, default=KEEP_RUNS)
    a = ap.parse_args()

    root = os.path.abspath(a.root) if a.root else PREVIEW_ROOT

    def out_path(asset):
        return os.path.join(root, asset, "live.json")

    if a.once:
        for asset in a.assets:
            p = scan(root, asset, a.keep)
            publish(p, out_path(asset))
            print("%s  %d runs (%d unclaimed) -> %s"
                  % (asset, p["total_runs"], p.get("unclaimed_runs", 0),
                     out_path(asset)))
        return 0

    print("tapping %s   (ctrl-c to stop)" % ", ".join(a.assets))
    last = {}
    while True:
        busy = False
        for asset in a.assets:
            p = scan(root, asset, a.keep)
            # Cheap change detection: only republish when something actually moved,
            # so the page's poll is nearly always a 304-shaped no-op from the
            # browser's cache.
            key = json.dumps(p["runs"], separators=(",", ":"))
            if key != last.get(asset):
                publish(p, out_path(asset))
                last[asset] = key
            busy = busy or any(not r["done"] for r in p["runs"][:3])
        time.sleep(BUSY_S if busy else IDLE_S)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
