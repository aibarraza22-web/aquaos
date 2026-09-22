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
   and cost assumptions live in `scenarios/*.yaml` or `params/` files, not in Python constants.
4. **Reproducible.** Scenarios are YAML. Runs are seeded. Results are stored under the scenario hash
   (sha256 of the canonical, fully resolved scenario, the AquaOS version, and the contents of every referenced
   input file), together with a fingerprint of the code.
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
| Hydraulics | WNTR 1.5 `EpanetSimulator` (EPANET 2.2, pressure-dependent demand by default); `WNTRSimulator` available for Phase 3 |
| Optimization | Pyomo 6.10 + HiGHS (`highspy`; use the `appsi_highs` / `highs` solver interfaces) |
| Data | pandas, xarray (gridded climate), DuckDB (local results and cache index), Parquet |
| API | FastAPI; multi-tenant-ready (tenant id on every resource, no global state) |
| Web | React + TypeScript + Vite, MapLibre GL for the map |
| Config | pydantic v2 models validate the scenario YAML |

### Layout (approved 2026-09-22)

```
aquaos/            Python package (namespaced so `data`/`core` don't collide on sys.path)
  core/            network (build/load .inp), demand, supply layer, simulation runner, reporting
  optimize/        MILP scheduling, MPC, robust variant, long-horizon planner, rule-based baseline
  reliability/     Monte Carlo stress tests, criticality, investment ranking
  treatment/       treatment surrogates, second-law benchmark
  data/            connectors, provenance, offline cache
  api/             FastAPI app
web/               React + TS dashboard
scenarios/         YAML scenarios (the only place policy or tariff choices are made); `extends:` for inheritance
params/            provenance-tagged parameter files from primary sources (shortage, credits, climate fit)
tests/             pytest; mirrors the aquaos/ tree
docs/              data_gaps.md, limitations.md, experimental_hypotheses.md, pilot_playbook.md
```

## Conventions

- **Units:** SI internally, matching WNTR (m, m³/s, m of head, W, J). Convert to US customary (psi, gpm, MGD,
  acre-feet, kWh) only at report, API, and UI boundaries, using `aquaos.core.units`. Column and field names carry units
  (`flow_m3s`, `pressure_psi`).
- **Time:** tz-aware timestamps; the canonical zone is `America/Phoenix` (no DST). The default hydraulic and
  report step is 15 minutes. Use 5 minutes where switching detail matters (strict storage checks, demand charges).
- **Randomness:** only through `numpy.random.Generator` objects derived from the scenario seed. No global RNG.
- **Synthetic labeling:** any object that holds data exposes `.provenance`. Report and plot builders refuse to render
  data that lacks provenance.
- **Tests:** pytest, ≥80% coverage on `aquaos/core` and `aquaos/optimize`. Put slow Monte Carlo tests behind
  `@pytest.mark.slow`.
- **Commits:** one commit per working milestone, with a clear message. Never commit `.venv/`, the cache, or run outputs.
- **Network metadata:** zones and asset roles live in EPANET `[TAGS]` (`zone:2`, `kind:well,zone:2`). Use commas:
  `;` starts an EPANET comment. Match controls by action target (`controls_targeting`), never by name, because
  simple controls read from an `.inp` are renamed.
- **Every network goes through `.inp`.** Valley City is written to `.inp` and loaded back like a utility network.
- **Hydraulics:** pressure-dependent demand (EPANET 2.2) by default. Pumps start in the state their rule implies.
- **Runs record** the scenario hash (inputs, including referenced file contents) and a code fingerprint
  (`aquaos.code_fingerprint()`).
- **Data connectors** download through `DataCache` (offline-first; `AQUAOS_OFFLINE=1` forbids network). Tests run
  offline against committed fixtures in `tests/fixtures/`.

## Environment notes

- Python 3.11 and Node 22. WNTR 1.5, Pyomo 6.10, HiGHS (highspy 1.15), DuckDB 1.5 and FastAPI all install and work.
- Network access was widened on 2026-09-22. Reclamation, CAP, NOAA, azleg.gov, USGS, APS, PRISM and EPA are
  reachable. **ADWR and SRP block automated clients** (HTTP 403), and **EIA needs an API key**. See
  `docs/data_gaps.md`.
- usbr.gov rejects the bare user-agent `Mozilla/5.0`. `aquaos.data.cache.USER_AGENT` works.
- Key primary-source facts in use (verified 2026-09-22): CY2026 Tier 1 = 512,000 af Arizona reduction (CAP).
  The Post-2026 ROD was issued 2026-08-21, and the 2027-2028 Operating Guidelines apportion Arizona 2.04 maf, a
  760,000 af reduction. The latest 24-Month Study is July 2026. A.R.S. 45-852.01(C) sets the base storage credit
  at 95%.

## Phase checklist

### Phase 0 — Setup
- [x] Read brief, verify library installs, smoke test
- [x] CLAUDE.md, `docs/data_gaps.md`
- [x] Phase 1 plan approved (2026-09-22)

### Phase 1 — Digital twin core (complete 2026-09-22)
- [x] Repo scaffolding: pyproject, ruff/mypy (clean), pytest-cov, GitHub Actions CI
- [x] Provenance model + offline cache; NOAA and Reclamation 24-Month Study connectors (`aquaos/data`)
- [x] Scenario schema (pydantic), `extends`, canonical hashing (covers referenced files), seeded RNG streams,
      DuckDB results store + Parquet time series, code fingerprint
- [x] `.inp` loader + validation (tested on WNTR's bundled Net3); zone/asset tags survive round trips
- [x] Valley City generator: CAP turnout + WTP (FCV) + clearwell, 4 zones with booster stations and tanks, 5 wells,
      2 recovery wells, reclaimed line to industrial user, closed interties; exported as `.inp`
- [x] Rule-based tank-level controls with lead/lag + clearwell and booster suction guards (Phase 2 baseline)
- [x] Demand: 5 customer classes, diurnal patterns, temperature response, AR(1) noise; weather generator fitted to
      NOAA Phoenix data; heat-wave generator (peak + warm-night deltas)
- [x] Supply layer: CAP allocation by shortage condition (primary-sourced) x M&I share (assumption); AMA-style
      budget; Theis drawdown with interference, fed back into hydraulics; recharge credit ledger (95% per statute)
- [x] 7-day runner + Markdown report (pressure by zone, tanks, energy, supply, mass balance, provenance); CLI
- [x] 74 tests: mass balance (continuity, closure, per-tank storage incl. strict 5-min check), pressure bounds,
      tank bounds, reproducibility, supply invariants, external .inp path, report/store; 97% coverage on core
- [x] `docs/limitations.md`, `docs/data_gaps.md`, example reports in `docs/examples/`

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

**Phase 1 is complete.** Three scenarios run end to end (baseline, heat wave, and 2027 shortage plus heat wave),
with no pressure violations or unmet demand. In the shortage scenario, CAP deliveries fall about 21% and
groundwater plus recovered water nearly doubles. Energy intensity rises from 0.40 to 0.47 kWh/m³ because well
lift replaces CAP water. That is the water-energy trade-off Phase 2 will optimize.

Before Phase 2:
- Get SRP/APS TOU tariff sheets (SRP needs a manual download) and an EIA API key for carbon intensity.
- Decide whether to raise the default hydraulic step resolution for demand-charge accuracy (see limitations).
