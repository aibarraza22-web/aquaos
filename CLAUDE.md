# AquaOS Arizona — project guide for Claude

AquaOS is an open water-infrastructure operating system for the desert Southwest. It models, optimizes, and stress-tests
Arizona water systems under uncertain futures: Colorado River shortage, CAP pumping energy, groundwater limits,
extreme heat coinciding with grid peaks, alternative supplies, and new large users (fabs, data centers).

Keep this file current. Update the phase checklist at each milestone and rewrite the status section at the end of each phase.

## Non-negotiables

1. **No invented numbers presented as real.** Every dataset or parameter set carries a provenance record
   (source URL, retrieval date, license, units, `synthetic: bool`). Synthetic values are labeled `SYNTHETIC` in code,
   YAML, reports, and the dashboard, and are listed in `docs/data_gaps.md`.
2. **Current values only from primary sources.** Tariffs, shortage tiers, CAP energy, and AMA rules come from the
   source document, never from memory. If a source can't be fetched, use a labeled synthetic stand-in and log the gap.
3. **Policy is scenario input, never code.** Shortage tier, tier reduction tables, groundwater budgets, tariffs,
   and cost assumptions live in `scenarios/*.yaml` or `data/` parameter files, not in Python constants.
4. **Reproducible.** Scenarios are YAML. Runs are seeded. Results are stored under the scenario hash
   (sha256 of the canonical, fully resolved scenario plus the AquaOS version).
5. **Plug-in ready.** A utility must be able to supply its own EPANET `.inp`, SCADA/historian CSV exports, and tariffs
   through config alone. The synthetic "Valley City" network goes through the same `.inp` loading path as any real network.
6. **Optimizer safety.** A regression test must re-simulate every optimizer schedule in WNTR and assert that no
   hydraulic constraint is violated. Never skip or weaken this test.
7. **No control of real equipment, ever.** Shadow mode only recommends and logs.
8. **Honest limitations.** `docs/limitations.md` records everything that is synthetic, simplified, or unvalidated.
   Every result carries its assumptions (scenario hash, provenance, synthetic flags).
9. **No savings claim without the rule-based baseline,** reported with confidence intervals across ≥50 stochastic scenarios.

## Architecture

| Area | Choice |
|---|---|
| Language | Python 3.11+, type hints everywhere, `mypy` + `ruff` |
| Hydraulics | WNTR 1.5 (`EpanetSimulator` for demand-driven runs, `WNTRSimulator` for pressure-dependent demand in stress tests) |
| Optimization | Pyomo 6.10 + HiGHS (`highspy`; use the `appsi_highs` / `highs` solver interfaces) |
| Data | pandas, xarray (gridded climate), DuckDB (local results and cache index), Parquet |
| API | FastAPI; multi-tenant-ready (tenant id on every resource, no global state) |
| Web | React + TypeScript + Vite, MapLibre GL for the map |
| Config | pydantic v2 models validate the scenario YAML |

### Layout (proposed; pending approval, see Phase 1 plan)

```
aquaos/            Python package (namespaced so `data`/`core` don't collide on sys.path)
  core/            network (build/load .inp), demand, supply layer, simulation runner, reporting
  optimize/        MILP scheduling, MPC, robust variant, long-horizon planner, rule-based baseline
  reliability/     Monte Carlo stress tests, criticality, investment ranking
  treatment/       treatment surrogates, second-law benchmark
  data/            connectors, provenance, offline cache
  api/             FastAPI app
web/               React + TS dashboard
scenarios/         YAML scenarios (the only place policy or tariff choices are made)
tests/             pytest; mirrors the aquaos/ tree
docs/              data_gaps.md, limitations.md, experimental_hypotheses.md, pilot_playbook.md
```

## Conventions

- **Units:** SI internally, matching WNTR (m, m³/s, m of head, W, J). Convert to US customary (psi, gpm, MGD,
  acre-feet, kWh) only at report, API, and UI boundaries, using `aquaos.core.units`. Column and field names carry units
  (`flow_m3s`, `pressure_psi`).
- **Time:** tz-aware timestamps; the canonical zone is `America/Phoenix` (no DST). Hydraulic timestep is
  configurable (default 1 h hydraulic, 15 min report is a Phase 2 option).
- **Randomness:** only through `numpy.random.Generator` objects derived from the scenario seed. No global RNG.
- **Synthetic labeling:** any object that holds data exposes `.provenance`. Report and plot builders refuse to render
  data that lacks provenance.
- **Tests:** pytest, ≥80% coverage on `aquaos/core` and `aquaos/optimize`. Put slow Monte Carlo tests behind
  `@pytest.mark.slow`.
- **Commits:** one commit per working milestone, with a clear message. Never commit `.venv/`, the cache, or run outputs.

## Environment notes (discovered 2026-09-22)

- Python 3.11.15 and Node 22. All core libraries install cleanly and pass a functional smoke test: WNTR (both
  simulators, bundled Net1/Net3), Pyomo with HiGHS (MILP solves to optimal), DuckDB, FastAPI, and the maplibre-gl/vite npm packages.
- **The cloud session's egress policy blocks every candidate data host** (usbr.gov, USGS, EIA, SRP, APS, ADWR, CAP,
  PRISM, NOAA, EPA; WebFetch is blocked as well). Only package registries are reachable. Connectors must therefore
  be built against recorded fixtures and fail gracefully. Real data must be fetched once in an environment where these hosts are allowed.
  See `docs/data_gaps.md`.

## Phase checklist

### Phase 0 — Setup
- [x] Read brief, verify library installs, smoke test
- [x] CLAUDE.md, `docs/data_gaps.md`
- [ ] Phase 1 plan approved

### Phase 1 — Digital twin core
- [ ] Repo scaffolding: pyproject, ruff/mypy, pytest-cov, GitHub Actions CI
- [ ] Provenance model + offline cache + dataset registry (`aquaos/data`)
- [ ] Scenario schema (pydantic), canonical hashing, seeded RNG, DuckDB results store
- [ ] `.inp` loader + network validation (works on WNTR bundled Net3 as an external-network check)
- [ ] Valley City generator: CAP turnout + WTP, wells, recharge/recovery, 4 pressure zones w/ pumps & tanks, reclaimed line to industrial user; exported as `.inp`
- [ ] Rule-based tank-level controls (also the Phase 2 baseline)
- [ ] Demand: customer classes, diurnal patterns, temperature dependency, heat-wave generator (all SYNTHETIC-labeled)
- [ ] Supply layer: CAP allocation by shortage tier, AMA-style groundwater budget + drawdown, recharge credit ledger
- [ ] 7-day simulation runner + pressure/tank/energy report
- [ ] Tests: mass balance, pressure bounds, tank bounds, reproducibility, supply-layer invariants; ≥80% coverage on core
- [ ] `docs/limitations.md` initial version; update CLAUDE.md

### Phase 2 — Water-energy optimizer
- [ ] Tariff model (TOU, demand charges) from primary tariff sheets
- [ ] Pump and source scheduling MILP (cost + demand charge + carbon)
- [ ] Rolling-horizon MPC with forecast uncertainty
- [ ] Robust / scenario-based variant (heat wave, price spike)
- [ ] Long-horizon seasonal source planner (CAP / GW / recharge recovery / reclaimed)
- [ ] Rule-based baseline comparison, ≥50 scenarios, CIs
- [ ] WNTR re-simulation regression test (non-negotiable)

### Phase 3 — Reliability and resilience
- [ ] Monte Carlo: pipe breaks, pump/well failures, outage in heat wave, sustained shortage, chemical supply disruption, combinations
- [ ] Asset criticality ranking; service-level metrics
- [ ] Investment ranking by resilience per dollar (labeled cost assumptions)

### Phase 4 — Treatment and process control
- [ ] Surrogates: conventional SWTP, brackish RO, advanced purification
- [ ] Minimum separation work benchmark and second-law efficiency
- [ ] Treatment energy + RO recovery setpoints in the optimizer (tariffs, brine limits)
- [ ] `docs/experimental_hypotheses.md`

### Phase 5 — Dashboard and pilot readiness
- [ ] Dashboard: map, scenario builder, schedule vs baseline, resilience heatmap, KPIs
- [ ] Shadow mode: historian CSV ingest, next-day recommendations, operator-action log
- [ ] `docs/pilot_playbook.md`

## Status

Phase 0 is complete, and the Phase 1 plan is awaiting approval.
