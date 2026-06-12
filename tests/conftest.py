import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow (skipped by default)")


def pytest_collection_modifyitems(config, items):
    run_slow = os.environ.get("NAPPE_SLOW", "") in ("1", "true", "yes")
    skip_slow = pytest.mark.skip(reason="set NAPPE_SLOW=1 to run")
    for item in items:
        if "slow" in item.keywords and not run_slow:
            item.add_marker(skip_slow)
