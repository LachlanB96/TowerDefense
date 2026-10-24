"""pytest glue for the preview harness tests (test_harness.py and friends).

The harness tests predate pytest: each one makes several `check(label, cond)` calls
and reports every failure instead of stopping at the first, which is what you want
when one change breaks five contract fields at once. This keeps that, and turns it
into a pytest result: a test fails if any of its checks failed.
"""

import os
import sys

import pytest

# Unity imports every file under Assets/ that isn't hidden, and __pycache__ isn't, so
# compiled bytecode would grow .meta files beside the tests. Nothing here needs it.
sys.dont_write_bytecode = True


def pytest_collection_modifyitems(session, config, items):
    """Run test_harness.py's tests in the order of its TESTS list.

    The order is part of the contract: the gallery server tests read the manifests the
    runner tests leave under the previews root. Tests not in a TESTS list keep their place
    after the listed ones.
    """
    def rank(item):
        order = getattr(item.module, "TESTS", None)
        fn = getattr(item, "function", None)
        if order and fn in order:
            return (0, order.index(fn))
        return (1, 0)

    items.sort(key=rank)


@pytest.fixture(scope="session", autouse=True)
def blender_present():
    """Fail the run up front when Blender isn't there, rather than every test one by one."""
    sys.path.insert(0, os.path.dirname(__file__))
    import test_harness
    if not os.path.exists(test_harness.BLENDER):
        pytest.exit("Blender not found at %s. Set GLOOMFELL_BLENDER to override." % test_harness.BLENDER,
                    returncode=2)


@pytest.fixture(autouse=True)
def soft_checks(request):
    """Fail the test if any check() it made failed (they're collected in _failures)."""
    failures = getattr(request.module, "_failures", None)
    if failures is None:
        yield
        return
    before = len(failures)
    yield
    failed = failures[before:]
    if failed:
        pytest.fail("failed checks: " + "; ".join(failed), pytrace=False)
