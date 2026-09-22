import shutil

import pytest
import yaml
from pydantic import ValidationError

from aquaos.core.scenario import Scenario, dump_scenario, load_scenario
from tests.conftest import SCENARIOS


def test_load_baseline_and_defaults():
    s = load_scenario(SCENARIOS / "valley_city_baseline_7d.yaml")
    assert s.supply.cap.shortage_condition == "cy2026_tier1"
    assert s.time.duration_s == 7 * 86400
    assert s.network.valley_city.zones == 4
    assert s.hydraulics.demand_model == "PDD"


def test_extends_merges_deeply():
    base = load_scenario(SCENARIOS / "valley_city_baseline_7d.yaml")
    hw = load_scenario(SCENARIOS / "valley_city_heatwave_7d.yaml")
    assert hw.demand.heat_wave is not None and base.demand.heat_wave is None
    assert hw.supply == base.supply  # untouched sections inherited
    s27 = load_scenario(SCENARIOS / "valley_city_2027_shortage_heatwave_7d.yaml")
    assert s27.supply.cap.mi_reduction_fraction == 0.25
    assert s27.supply.cap.contract_af_per_year == base.supply.cap.contract_af_per_year
    assert s27.demand.heat_wave == hw.demand.heat_wave


def test_hash_is_stable_and_sensitive(tmp_path):
    p = SCENARIOS / "valley_city_baseline_7d.yaml"
    h1 = load_scenario(p).scenario_hash()
    assert h1 == load_scenario(p).scenario_hash()
    assert load_scenario(p, overrides={"seed": 1}).scenario_hash() != h1
    assert load_scenario(p, overrides={"supply": {"cap": {"mi_reduction_fraction": 0.1}}}).scenario_hash() != h1


def test_hash_covers_referenced_file_content(tmp_path):
    params = tmp_path / "shortage.yaml"
    shutil.copy(SCENARIOS.parent / "params" / "colorado_river_shortage.yaml", params)
    over = {"supply": {"cap": {"shortage_params": str(params)}}}
    s = load_scenario(SCENARIOS / "valley_city_baseline_7d.yaml", overrides=over)
    h1 = s.scenario_hash()
    params.write_text(params.read_text().replace("512000", "512001"))
    assert s.scenario_hash() != h1


def test_policy_fields_are_required(tmp_path):
    raw = yaml.safe_load((SCENARIOS / "valley_city_baseline_7d.yaml").read_text())
    del raw["supply"]["cap"]["shortage_condition"]
    with pytest.raises(ValidationError):
        Scenario.model_validate(raw)


def test_rejects_unknown_fields_and_bad_values(tmp_path):
    raw = yaml.safe_load((SCENARIOS / "valley_city_baseline_7d.yaml").read_text())
    with pytest.raises(ValidationError):
        Scenario.model_validate({**raw, "bogus": 1})
    raw["time"]["report_step_s"] = 1000
    with pytest.raises(ValidationError):
        Scenario.model_validate(raw)


def test_circular_extends(tmp_path):
    (tmp_path / "a.yaml").write_text("extends: b.yaml\nname: a\n")
    (tmp_path / "b.yaml").write_text("extends: a.yaml\nname: b\n")
    with pytest.raises(ValueError, match="circular"):
        load_scenario(tmp_path / "a.yaml")


def test_dump_roundtrip():
    s = load_scenario(SCENARIOS / "valley_city_heatwave_7d.yaml")
    again = Scenario.model_validate(yaml.safe_load(dump_scenario(s)))
    assert again.canonical_json() == s.canonical_json()
