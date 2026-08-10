"""Map an asset script's module-level tunables, and refuse the ones that cannot be swept.

    python Assets/Blender/_tools/genes.py mage000                 # human-readable map
    python Assets/Blender/_tools/genes.py mage000 --json out.json  # machine map
    python Assets/Blender/_tools/genes.py mage000 --check Z_HAT_TIP,ROBE_FLARE

Runs in SYSTEM Python. Never imports the asset script - it only parses it - so it is
safe to run against a script that would save and export at module scope.

WHY THIS EXISTS
---------------
`preview.py --variants` overrides module globals by seeding VARIANT and letting the
`# --- variant hook ---` block do `globals().update(...)`. That block sits near the
BOTTOM of the file, after every default has been assigned. So an override lands after
module-level arithmetic has already run.

That is fine for an independent constant and silently wrong for a derived one:

    Z_HAT_TIP = 1.94                     # line 402
    HAT_SPINE = curve_to(Z_HAT_TIP)      # line 563   <-- computed at import
    ...
    globals().update(VARIANT)            # line 2998  <-- too late for HAT_SPINE

Sweep Z_HAT_TIP and the hat tip moves while its spine does not. The render is broken
but NOT pixel-identical, so the identical-pair check in measure.py passes it and a
judge scores a corrupted build. Measured on blender_mage000.py: 182 ALLCAPS module
globals, 18 of them derived, and all 18 computed above the hook.

The failure mode this module chooses is ABSENCE, not misclassification: a caller
should refuse any gene that is not present in the map, so a name this parser fails to
see is friction (a refused sweep) rather than a corrupted judgement. That is the whole
design trade - see `check()`.

A derived gene is not un-sweepable in principle; it is un-sweepable *through `vars`*.
The escape hatch is `patch`, which runs as source inside the hook and can recompute
whatever it likes. `check()` says so in its refusal message rather than dead-ending.
"""

import argparse
import ast
import difflib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)                      # Assets/Blender
HOOK_MARKER = "# --- variant hook ---"

# Only ALLCAPS module-level names are treated as tunables. This matches the
# convention the asset scripts already follow and keeps helper functions, classes and
# loop temporaries out of the map.
def _is_tunable(name):
    return name.isupper() and not name.startswith("_")


def _literal(node):
    """The assigned value if it is a plain literal, else None.

    Used only to report a current value and to decide whether a range can be guessed.
    A non-literal value is not a problem by itself - `M_ROBE = make_material(...)` is a
    perfectly good gene to leave alone - it just cannot be swept numerically.
    """
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def _names_in(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _numeric_range(value):
    """A conservative sweep range for a scalar, or None.

    Deliberately NOT clever. A range is a starting bracket for a human or an agent to
    override, not a claim about what the model can take. +-40% around the current value
    keeps a sweep inside the neighbourhood the script was authored in; anything wider
    should be stated explicitly by whoever wants it.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value == 0:
        return None                       # no scale to work from; caller must supply one
    lo, hi = sorted((value * 0.6, value * 1.4))
    return [round(lo, 6), round(hi, 6)]


def script_path(asset):
    """Resolve an asset name to its script, the same way preview.py does.

    Resolved relative to THIS file, never to cwd, so running the main repo's copy from
    inside a worktree maps the main repo's script - matching preview.py's behaviour
    rather than quietly disagreeing with it.
    """
    if os.path.sep in asset or asset.endswith(".py"):
        return os.path.abspath(asset)
    return os.path.join(BLENDER_DIR, "blender_%s.py" % asset)


def build_map(path):
    """Parse one asset script into a gene map. Never executes it."""
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    lines = src.splitlines()

    hook_line = next((i + 1 for i, l in enumerate(lines) if HOOK_MARKER in l), None)

    tree = ast.parse(src, filename=path)
    genes = {}
    seen = []                              # assignment order, for derived-from lookups

    for node in tree.body:                 # module scope only - nested defs are not genes
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets
                   if isinstance(t, ast.Name) and _is_tunable(t.id)]
        if not targets:
            continue

        refs = _names_in(node.value)
        # Derived == reads a gene assigned EARLIER at module scope. Order matters:
        # a name that appears later cannot have contributed to this value.
        derived_from = sorted(r for r in refs if r in seen)
        value = _literal(node.value)

        for name in targets:
            genes[name] = {
                "line": node.lineno,
                "derived_from": derived_from,
                "current": value,
                "literal": value is not None,
                "range": _numeric_range(value),
                # A gene assigned below the hook is overwritten by the script AFTER the
                # hook applies, so seeding it through `vars` has no effect at all. Rare,
                # but it fails silently in the opposite direction to a derived gene.
                "below_hook": bool(hook_line and node.lineno > hook_line),
            }
            seen.append(name)

    # Which genes feed which - the reverse index, so a refusal can say what it breaks.
    for name, g in genes.items():
        g["feeds"] = sorted(k for k, v in genes.items() if name in v["derived_from"])

    return {
        "script": os.path.abspath(path),
        "hook_line": hook_line,
        "conforming": hook_line is not None,
        "count": len(genes),
        "derived_count": sum(1 for g in genes.values() if g["derived_from"]),
        "genes": genes,
    }


def check(gene_map, names):
    """Decide whether these genes may be swept through `vars`.

    Returns (ok, problems). `problems` is a list of human-readable refusals; each one
    names the mechanism and points at the escape hatch, because a refusal a caller
    cannot act on just gets worked around.
    """
    problems = []
    for name in names:
        g = gene_map["genes"].get(name)
        if g is None:
            # Suggest real names. Observed cost of not doing this: a refused row forces a
            # separate query against 182 tunables, and the cheap way out under pressure
            # is a hand-written `patch`, which bypasses this check entirely.
            near = difflib.get_close_matches(name, list(gene_map["genes"]), 5, 0.4)
            problems.append(
                "%s: not in the gene map. Refusing rather than guessing - if this is a "
                "real module-level tunable the parser missed it, and a sweep that "
                "half-applies is worse than one that does not run.%s"
                % (name, ("  Did you mean: %s?" % ", ".join(near)) if near else
                   "  Run `genes.py <asset> --find <substring>` to list candidates."))
            continue
        if g["derived_from"]:
            problems.append(
                "%s (line %d) is derived from %s, which are computed before the variant "
                "hook at line %s. Overriding it through `vars` leaves %s stale and "
                "renders a broken-but-not-identical build. Use `patch` to recompute, or "
                "sweep the parent instead."
                % (name, g["line"], ", ".join(g["derived_from"]), gene_map["hook_line"],
                   ", ".join(g["feeds"]) or "its dependents"))
            continue
        if g["feeds"]:
            problems.append(
                "%s (line %d) FEEDS %s, which are computed before the hook and will keep "
                "their old values. Use a `patch` that reassigns %s after overriding this - "
                "seeding the dependent through `vars` instead does not help, it is derived "
                "and would be refused for the same reason."
                % (name, g["line"], ", ".join(g["feeds"]), ", ".join(g["feeds"])))
            continue
        if g["below_hook"]:
            problems.append(
                "%s (line %d) is assigned BELOW the hook at line %s, so the script "
                "overwrites any seeded value. Seeding it does nothing."
                % (name, g["line"], gene_map["hook_line"]))
    return (not problems), problems


def _report(m):
    out = ["gene map: %s" % m["script"],
           "  hook line %s%s" % (m["hook_line"],
                                 "" if m["conforming"] else "   *** NOT CONFORMING ***"),
           "  %d module tunables, %d derived" % (m["count"], m["derived_count"]),
           ""]
    derived = [(g["line"], n, g) for n, g in m["genes"].items() if g["derived_from"]]
    if derived:
        out.append("DERIVED - these cannot be swept through `vars`:")
        for line, n, g in sorted(derived):
            out.append("  line %-5d %-22s <- %s" % (line, n, ", ".join(g["derived_from"])))
        out.append("")
    feeders = [(g["line"], n, g) for n, g in m["genes"].items()
               if g["feeds"] and not g["derived_from"]]
    if feeders:
        out.append("FEEDERS - sweeping these leaves their dependents stale:")
        for line, n, g in sorted(feeders):
            out.append("  line %-5d %-22s -> %s" % (line, n, ", ".join(g["feeds"])))
        out.append("")
    free = [(g["line"], n, g) for n, g in m["genes"].items()
            if not g["feeds"] and not g["derived_from"] and g["range"]]
    out.append("SWEEPABLE SCALARS: %d (showing 12)" % len(free))
    for line, n, g in sorted(free)[:12]:
        out.append("  line %-5d %-22s %-10s range %s" % (line, n, g["current"], g["range"]))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("asset", help="asset name (mage000) or a path to the script")
    ap.add_argument("--json", help="write the machine-readable map here")
    ap.add_argument("--check", help="comma-separated gene names to validate for sweeping")
    ap.add_argument("--find", help="list genes whose name contains this substring")
    a = ap.parse_args()

    path = script_path(a.asset)
    if not os.path.exists(path):
        print("no such script: %s" % path, file=sys.stderr)
        return 2

    m = build_map(path)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:   # utf-8: Windows defaults cp1252
            json.dump(m, fh, indent=2)

    if a.find:
        hits = [(g["line"], n, g) for n, g in m["genes"].items()
                if a.find.lower() in n.lower()]
        for line, n, g in sorted(hits):
            flag = ("DERIVED" if g["derived_from"] else
                    "FEEDER" if g["feeds"] else "free")
            print("  line %-5d %-24s %-8s %-10s %s"
                  % (line, n, flag, g["current"], g["range"] or ""))
        if not hits:
            print("  no gene name contains %r" % a.find)
        return 0

    if a.check:
        ok, problems = check(m, [n.strip() for n in a.check.split(",") if n.strip()])
        print("SWEEPABLE" if ok else "REFUSED")
        for p in problems:
            print("  - %s" % p)
        return 0 if ok else 1

    print(_report(m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
