# AquaOS Arizona

An open water-infrastructure operating system for the desert Southwest. AquaOS models, optimizes and
stress-tests Arizona water systems under Colorado River shortage, groundwater limits, and extreme heat.

**Status:** Phase 1 (digital twin core) complete. See `CLAUDE.md` for goals, architecture, conventions and the
phase checklist, `docs/limitations.md` for what is synthetic or simplified, and `docs/data_gaps.md` for data
sources.

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

aquaos run scenarios/valley_city_baseline_7d.yaml      # 7-day run, report under runs/<hash>/report.md
aquaos run scenarios/valley_city_heatwave_7d.yaml
aquaos run scenarios/valley_city_2027_shortage_heatwave_7d.yaml

aquaos validate-inp path/to/your_network.inp            # any EPANET network
aquaos build-network scenarios/valley_city_baseline_7d.yaml --out valley_city.inp
aquaos fetch usbr-24mo                                   # cache the latest Reclamation 24-Month Study
aquaos fetch noaa-hourly --start 2023-07-01 --end 2023-07-31

pytest --cov=aquaos/core                                 # tests (offline; fixtures are committed)
```

Example reports: `docs/examples/`.

## Using your own network

Set `network.source: inp` and `network.inp_path` in a scenario. Optional EPANET `[TAGS]` let AquaOS report by
pressure zone and identify assets:

```
[TAGS]
NODE  J-101   zone:2
LINK  WELL-7  kind:well,zone:2
```

Link kinds: `well`, `recovery_well`, `high_service`, `booster`, `reclaimed`, `treatment_plant`, `intertie`.

## Data rules

Every dataset carries a provenance record. Anything synthetic is labeled `SYNTHETIC` in code, YAML and
reports. Policy inputs (shortage condition, CAP contract, groundwater allowance) are scenario inputs, never
Python constants.
