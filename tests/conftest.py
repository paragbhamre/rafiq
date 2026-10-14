"""Shared test settings. Runs against whichever pack RAFIQ_PACK selects (default: the synthetic pack).

    python -m pytest -q                                   # everything, synthetic pack
    RAFIQ_PACK=packs/official python -m pytest -q tests/test_any_pack.py   # pack-independent checks on another pack
"""
import os
import tempfile

os.environ.setdefault("RAFIQ_RUNTIME_DIR", tempfile.mkdtemp(prefix="rafiq-test-"))
os.environ["LLM_PROVIDER"] = "offline"
os.environ["RAFIQ_DEMO_PASSWORD"] = "test-demo-pass"
os.environ["RAFIQ_ADMIN_PASSWORD"] = "test-admin-pass"


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: pack swap rehearsal (subprocesses); excluded from the Render build")
