"""Run the preview harness's tests (Assets/Blender/_tools/tests) with pytest.

    python Assets/Blender/_tools/selftest.py [name]

The tests moved to pytest on 2026-10-24 (they're part of check.ps1 now); this keeps the
old command working. `name` picks tests whose name contains it, as it always did.
It starts Blender, so run it through warden-run (CLAUDE.md, "Preview harness").
"""

import os
import sys

# See tests/conftest.py: no __pycache__ under Assets/, or Unity gives it .meta files.
sys.dont_write_bytecode = True

import pytest  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    args = [os.path.join(HERE, "tests"), "-p", "no:cacheprovider", "-q"]
    if len(sys.argv) > 1:
        args += ["-k", sys.argv[1]]
    sys.exit(pytest.main(args))
