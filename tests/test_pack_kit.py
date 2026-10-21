"""The pack swap kit: Rafiq must adapt to a pack that differs from the synthetic one.

Builds altered packs (renamed files, columns and values, new IDs, renumbered and reworded policies,
a different named owner), then checks the compatibility report and runs the pack-independent tests
on them in a separate process.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app import config
from app.data import pack

ROOT = Path(__file__).resolve().parent.parent
# "slow": builds whole packs and re-runs the suite in subprocesses. Run before every push
# (python -m pytest -q); skipped in the Render build to keep deploys to a few minutes.
pytestmark = [pytest.mark.skipif(not config.IS_REFERENCE_PACK, reason="builds packs from the synthetic pack"), pytest.mark.slow]


def _run(*args, env=None):
    e = {**os.environ, "LLM_PROVIDER": "offline", **(env or {})}
    e.pop("DATABASE_URL", None)
    e.pop("RAFIQ_DATA_DIR", None)
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=e, capture_output=True, text=True, timeout=300)


@pytest.fixture(scope="module")
def altered(tmp_path_factory):
    d = tmp_path_factory.mktemp("packs") / "altered"
    r = _run("tools/make_test_pack.py", str(d))
    assert r.returncode == 0, r.stderr
    return d


def test_journey_map_parser_reproduces_built_in_journeys():
    for jt, built in config.BUILTIN_STEPS.items():
        parsed = {s["code"]: s for s in config.STEPS[jt]}
        assert list(parsed) == [s["code"] for s in built]
        for b in built:
            p = parsed[b["code"]]
            for k in ("day", "grace", "applies", "prereqs", "esc", "role"):
                assert p[k] == b[k], (jt, b["code"], k)
    assert config.ESCALATION_CONTACTS == config.BUILTIN_CONTACTS


def test_scenario_parser_reads_the_synthetic_scenarios():
    from app import scenarios
    sc = scenarios.parse((ROOT / "data" / "scenarios.md").read_text(encoding="utf-8"), pack.employees)
    assert [s["id"] for s in sc] == [f"S{i:02d}" for i in range(1, 15)] + [f"H{i:02d}" for i in range(1, 21)]
    assert sc[0]["employee_id"] == "EMP-1001" and "laptop" in sc[0]["prompt"]


def test_report_on_the_synthetic_pack_has_no_blockers():
    r = _run("tools/ingest.py", "data")
    assert r.returncode in (0, 1), r.stdout[-2000:]
    assert "0 blockers" in r.stdout


def test_altered_pack_loads_and_rules_resolve_by_meaning(altered):
    r = _run("tools/ingest.py", str(altered))
    assert r.returncode in (0, 1), r.stdout[-3000:]
    out = r.stdout
    assert "0 blockers" in out and "0 not found" in out
    assert "| POL-IT-001 §5.1 | ICT-POL-07 §4.1 | matched by meaning" in out      # loan-device rule: renamed, renumbered, reworded
    assert "| POL-PRV-001 §5.1 | POL-PRV-001 §15.1 | matched by meaning" in out   # what a manager sees: renumbered, reworded
    assert "IT Service Delivery Manager → Grace Tan" in out
    assert "housing allowance by grade" in out                                      # changed figure: quoted, not stated


def test_pack_independent_tests_pass_on_the_altered_pack(altered):
    r = _run("-m", "pytest", "-q", "tests/test_any_pack.py", env={"RAFIQ_PACK": str(altered)})
    assert r.returncode == 0, r.stdout[-3000:]


def test_without_scenarios_demo_accounts_come_from_the_journeys(tmp_path):
    d = tmp_path / "noscen"
    assert _run("tools/make_test_pack.py", str(d), "--no-scenarios").returncode == 0
    r = _run("-m", "pytest", "-q", "tests/test_any_pack.py", env={"RAFIQ_PACK": str(d)})
    assert r.returncode == 0, r.stdout[-3000:]
    r = _run("tools/ingest.py", str(d))
    assert "demo accounts chosen" in r.stdout and "no scenario table" in r.stdout


def test_missing_mapping_is_a_clear_blocker(altered, tmp_path):
    import shutil
    d = tmp_path / "nomap"
    shutil.copytree(altered, d)
    (d / "mapping.json").unlink()
    r = _run("tools/ingest.py", str(d))
    assert r.returncode == 2
    assert "file not found" in r.stdout or "required column 'employee_id' missing" in r.stdout
    # and the app refuses to start on it with the same explanation, rather than running on bad data
    r = _run("-c", "import app.main", env={"RAFIQ_PACK": str(d)})
    assert r.returncode != 0 and "tools/ingest.py" in r.stderr


def test_mapping_file_is_valid_json(altered):
    m = json.loads((altered / "mapping.json").read_text())
    assert m["columns"]["employees"]["staff_id"] == "employee_id"
