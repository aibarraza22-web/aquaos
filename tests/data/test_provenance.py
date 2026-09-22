import datetime as dt

import pytest

from aquaos.data.provenance import Provenance, assumption, require_provenance, synthetic


def test_primary_requires_url_and_date():
    with pytest.raises(ValueError):
        Provenance(title="x", kind="primary")
    p = Provenance(title="x", kind="primary", source_url="https://e.gov", retrieved=dt.date(2026, 9, 22))
    assert not p.synthetic
    assert p.label == "PRIMARY"


def test_synthetic_and_assumption_need_explanation():
    with pytest.raises(ValueError):
        Provenance(title="x", kind="synthetic")
    with pytest.raises(ValueError):
        Provenance(title="x", kind="derived")
    assert synthetic("s", "made up").synthetic
    assert assumption("a", "because").label == "SYNTHETIC"


def test_synthetic_propagates_through_parents():
    real = Provenance(title="r", kind="primary", source_url="https://e.gov", retrieved=dt.date(2026, 1, 1))
    derived_real = Provenance(title="d", kind="derived", derivation="mean", parents=(real,))
    assert not derived_real.synthetic
    derived_mixed = Provenance(title="d2", kind="derived", derivation="sum", parents=(real, synthetic("s", "x")))
    assert derived_mixed.synthetic
    assert {p.title for p in derived_mixed.flatten()} == {"d2", "r", "s"}


def test_require_provenance_gate():
    class NoProv:
        pass

    class WithProv:
        provenance = synthetic("s", "x")

    with pytest.raises(ValueError, match="refusing"):
        require_provenance(NoProv())
    assert require_provenance(WithProv()).synthetic


def test_summary_mentions_label_and_source():
    p = Provenance(title="t", kind="primary", source_url="https://e.gov", retrieved=dt.date(2026, 9, 22))
    s = p.summary()
    assert "[PRIMARY]" in s and "https://e.gov" in s and "2026-09-22" in s
