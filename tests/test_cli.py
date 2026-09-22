import os

import wntr

from aquaos.cli import main
from aquaos.core.scenario import load_scenario
from tests.conftest import SCENARIOS

NET3 = os.path.join(os.path.dirname(wntr.__file__), "library", "networks", "Net3.inp")


def test_hash_and_validate(capsys):
    assert main(["hash", str(SCENARIOS / "valley_city_baseline_7d.yaml")]) == 0
    out = capsys.readouterr().out.strip()
    assert out == load_scenario(SCENARIOS / "valley_city_baseline_7d.yaml").scenario_hash()
    assert main(["validate-inp", NET3]) == 0


def test_build_network_and_run(tmp_path, capsys):
    inp = tmp_path / "vc.inp"
    assert main(["build-network", str(SCENARIOS / "valley_city_baseline_7d.yaml"), "--out", str(inp)]) == 0
    assert inp.exists() and "[TAGS]" in inp.read_text()
    assert main(["validate-inp", str(inp)]) == 0
    scn = tmp_path / "one_day.yaml"
    scn.write_text(f"extends: {SCENARIOS / 'valley_city_baseline_7d.yaml'}\nname: one_day\n"
                   "time:\n  duration_days: 1\n")
    assert main(["run", str(scn), "--out", str(tmp_path / "runs")]) == 0
    assert "report:" in capsys.readouterr().out
    assert list((tmp_path / "runs").glob("*/report.md"))
