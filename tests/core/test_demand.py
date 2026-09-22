
import numpy as np
import pandas as pd
import pytest

from aquaos.core.demand import model as D
from aquaos.core.demand.temperature import TemperatureSeries
from aquaos.core.network.valley_city import RECLAIMED_USER_NODE, build_valley_city
from aquaos.core.rng import stream
from aquaos.core.scenario import DemandConfig, ValleyCityConfig
from aquaos.core.units import SECONDS_PER_DAY
from aquaos.data.provenance import synthetic


@pytest.fixture(scope="module")
def net():
    return build_valley_city(ValleyCityConfig(), DemandConfig(), 110, 800, 0.1, 0.2, 15, 0.3, stream(1, "net")).wn


def flat_temp(value: float, days: int = 10) -> TemperatureSeries:
    idx = pd.date_range("2026-07-09", periods=24 * days, freq="h", tz="America/Phoenix")
    return TemperatureSeries(pd.Series(value, index=idx), synthetic("flat", "constant"))


def test_allocation_conserves_totals(net):
    cfg = DemandConfig()
    allocs = D.allocate(net, cfg, seed=1, reclaimed_node=RECLAIMED_USER_NODE)
    by = {}
    for a in allocs:
        by[a.demand_class] = by.get(a.demand_class, 0) + a.q_ref_m3s * SECONDS_PER_DAY
    res = cfg.population * cfg.residential_m3_per_capita_day
    assert by["residential"] == pytest.approx(res)
    assert by["commercial"] == pytest.approx(res * cfg.commercial_fraction_of_residential)
    assert by["fab"] == pytest.approx(3000) and by["reclaimed_industrial"] == pytest.approx(2500)
    assert any(a.node == RECLAIMED_USER_NODE for a in allocs)


def test_allocation_errors(net):
    with pytest.raises(ValueError, match="reclaimed"):
        D.allocate(net, DemandConfig(), seed=1, reclaimed_node=None)
    cfg = DemandConfig.model_validate({"large_users": [{"name": "x", "demand_class": "fab",
                                                       "avg_m3_per_day": 10, "zone": 9}]})
    with pytest.raises(ValueError, match="zone:9"):
        D.allocate(net, cfg, seed=1)


def test_temperature_response_is_monotone():
    cls = DemandConfig().classes["residential"]
    idx = pd.date_range("2026-07-13", periods=96, freq="15min", tz="America/Phoenix")
    cool = D.class_multiplier(cls, idx, flat_temp(25)).mean()
    hot = D.class_multiplier(cls, idx, flat_temp(40)).mean()
    hotter = D.class_multiplier(cls, idx, flat_temp(45)).mean()
    assert cool == pytest.approx(1.0, rel=0.01)  # below t_ref: diurnal mean only
    assert hot == pytest.approx(1 + cls.temp_coef_per_c * 10, rel=0.01)
    assert hotter > hot


def test_build_demand_mean_and_reproducibility(net):
    cfg = DemandConfig()
    allocs = D.allocate(net, cfg, seed=1, reclaimed_node=RECLAIMED_USER_NODE)
    idx = pd.date_range("2026-07-13", periods=7 * 96 + 1, freq="15min", tz="America/Phoenix")
    a = D.build_demand(allocs, cfg, flat_temp(25), idx, seed=1)
    b = D.build_demand(allocs, cfg, flat_temp(25), idx, seed=1)
    c = D.build_demand(allocs, cfg, flat_temp(25), idx, seed=2)
    assert a.data.equals(b.data) and not a.data.equals(c.data)
    expected = sum(x.q_ref_m3s for x in allocs)
    assert a.data.sum(axis=1).mean() == pytest.approx(expected, rel=0.03)
    assert (a.data >= 0).all().all() and a.provenance.synthetic


def test_apply_to_network(net):
    cfg = DemandConfig()
    allocs = D.allocate(net, cfg, seed=1, reclaimed_node=RECLAIMED_USER_NODE)
    idx = pd.date_range("2026-07-13", periods=97, freq="15min", tz="America/Phoenix")
    ds = D.build_demand(allocs, cfg, flat_temp(35), idx, seed=1)
    D.apply_to_network(net, ds, 900)
    node = ds.data.columns[0]
    j = net.get_node(node)
    ts = j.demand_timeseries_list[0]
    assert ts.base_value == pytest.approx(ds.data[node].mean())
    pat = np.array(net.get_pattern(ts.pattern_name).multipliers)
    assert np.allclose(pat * ts.base_value, ds.data[node].to_numpy())
