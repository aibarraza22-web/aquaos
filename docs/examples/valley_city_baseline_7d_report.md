# AquaOS run report: valley_city_baseline_7d

> **SYNTHETIC:** this run uses synthetic or assumed inputs (see *Assumptions and provenance*). Its numbers describe a model system, not a real utility.

- Scenario hash: `23a333b8db579646b9a0e9b009fe175d80d90dc5e072addb42539b79f5bcfac6`
- Seed: 20260713; AquaOS 0.1.0, code fingerprint `ee13a47d80a86963`
- Period: 2026-07-13T00:00:00-07:00 to 2026-07-20T00:00:00-07:00 (7 days, 15-minute steps)
- Description: Synthetic Valley City, 7 days from 2026-07-13, synthetic July weather fitted to Phoenix NOAA data, CY2026 Tier 1.

## Key results

| KPI | Value |
|---|---|
| Water delivered | 238,648 m³ (193.5 af; avg 9.01 MGD) |
| Pumping energy | 95,298 kWh |
| Energy intensity | 0.399 kWh/m³ delivered |
| Peak pumping demand | 834 kW |
| Minimum pressure at a demand node | 42.7 psi |
| Node-hours below 40 psi (service) | 0.0 |
| Node-hours below 20 psi (minimum) | 0.0 |
| Unmet demand | 0 m³ (0.0 node-hours below 95% of requested) |
| Mass-balance closure error | -0.028% |

Hydraulics: PDD (full demand at 30 psi, none below 5 psi). Energy is pump electricity only (treatment-process energy is added in Phase 4). Costs need tariffs (Phase 2).

## Supply layer

- Shortage condition: **cy2026_tier1**. Arizona reduction 512,000 af/yr [PRIMARY].
- If CAP absorbed all of it, the CAP-wide cut would be about 30% of normal supply [derived; context only].
- City CAP subcontract 6,000 af/yr, M&I reduction fraction 0% [ASSUMPTION], so the delivery entitlement is 6,000 af/yr.
- Treatment plant setting 0.300 m³/s. CAP water treated this run 139.0 af vs a monthly-shaped pro-rata share of 149.6 af.
- Groundwater (phoenix AMA label): pumped 18.5 af. Remaining annual allowance 1,200.0 af; pro-rata for this run 48.8 af.
- Recovery wells: recovered 17.5 af of stored water. Credit balance at end 5,000.7 af (credit fraction 0.95 [PRIMARY]).
- Reclaimed water delivered to the industrial user: 16.4 af.
- Maximum well drawdown (Theis, with interference): 5.15 m. Pumped volume changed 0.19% in the last drawdown iteration.

## Pressure by zone (demand junctions)

| zone | nodes | min_psi | p05_psi | median_psi | max_psi | node_hours_below_min | node_hours_below_service | node_hours_above_max |
|---|---|---|---|---|---|---|---|---|
| 1 | 74 | 42.7 | 48.0 | 64.5 | 87.5 | 0.0 | 0.0 | 0.0 |
| 2 | 75 | 46.1 | 50.2 | 67.6 | 87.5 | 0.0 | 0.0 | 0.0 |
| 3 | 74 | 47.4 | 50.3 | 66.9 | 85.1 | 0.0 | 0.0 | 0.0 |
| 4 | 72 | 47.4 | 50.9 | 66.5 | 85.7 | 0.0 | 0.0 | 0.0 |
| reclaimed | 1 | 48.3 | 48.5 | 50.5 | 52.6 | 0.0 | 0.0 | 0.0 |

Thresholds are configurable engineering choices (`report:` in the scenario), not regulatory citations.

## Storage tanks

| tank | min_level_m | max_level_m | start_level_m | end_level_m | design_min_m | design_max_m | hours_at_min | hours_at_max |
|---|---|---|---|---|---|---|---|---|
| T1 | 3.99 | 6.50 | 6.50 | 4.55 | 1.00 | 10.00 | 0.00 | 0.00 |
| T2 | 4.47 | 7.53 | 6.50 | 6.05 | 1.00 | 10.00 | 0.00 | 0.00 |
| T3 | 4.51 | 8.48 | 6.50 | 5.52 | 1.00 | 10.00 | 0.00 | 0.00 |
| T4 | 4.31 | 8.99 | 6.50 | 6.91 | 1.00 | 10.00 | 0.00 | 0.00 |
| CLEARWELL | 1.97 | 5.20 | 3.50 | 3.21 | 0.50 | 5.50 | 0.00 | 0.00 |
| RCL_TANK | 4.01 | 7.00 | 4.50 | 6.97 | 1.00 | 8.00 | 0.00 | 0.00 |

## Pump energy

| pump | kind | kwh | volume_m3 | kwh_per_m3 | peak_kw | run_hours |
|---|---|---|---|---|---|---|
| HS1 | high_service | 23268.64 | 132400.84 | 0.18 | 142.20 | 164.50 |
| HS2 | high_service | 7412.33 | 38984.37 | 0.19 | 141.69 | 52.75 |
| B2_1 | booster | 14173.69 | 122673.97 | 0.12 | 86.22 | 164.75 |
| B2_2 | booster | 0.00 | 0.00 | nan | 0.00 | 0.00 |
| B3_1 | booster | 8886.17 | 89088.67 | 0.10 | 54.60 | 165.00 |
| B3_2 | booster | 0.00 | 0.00 | nan | 0.00 | 0.00 |
| B4_1 | booster | 4283.40 | 45342.89 | 0.09 | 26.93 | 162.00 |
| B4_2 | booster | 0.00 | 0.00 | nan | 0.00 | 0.00 |
| GW2_1 | well | 17760.04 | 21364.53 | 0.83 | 124.96 | 143.50 |
| GW2_2 | well | 0.00 | 0.00 | nan | 0.00 | 0.00 |
| GW2_3 | well | 0.00 | 0.00 | nan | 0.00 | 0.00 |
| GW3_1 | well | 1359.64 | 1472.07 | 0.92 | 140.33 | 9.75 |
| GW3_2 | well | 0.00 | 0.00 | nan | 0.00 | 0.00 |
| RW1 | recovery_well | 14073.74 | 21624.81 | 0.65 | 87.92 | 161.25 |
| RW2 | recovery_well | 0.00 | 0.00 | nan | 0.00 | 0.00 |
| RCL_P1 | reclaimed | 4080.81 | 20253.69 | 0.20 | 36.47 | 113.00 |
| RCL_P2 | reclaimed | 0.00 | 0.00 | nan | 0.00 | 0.00 |

Wire-to-water efficiency: 75% for booster and high-service pumps, 65% for wells [SYNTHETIC].

## Mass balance

- Maximum instantaneous continuity residual: 1.39e-06 m³/s (2.48e-06 of peak demand).
- Sources 236,165 m³ = demand 238,648 m³ + storage change -2,417 m³ (closure error -0.028%).
- Tank volume consistency (level-derived vs integrated inflow, relative to throughput): T1 0.42%, T2 0.16%, T3 0.36%, T4 0.22%, CLEARWELL 0.47%, RCL_TANK 1.12%. At 15-minute reporting, pump switches between report steps are not sampled; errors of a few percent are resolution effects (they vanish at 5-minute steps).

## Assumptions and provenance

- [DERIVED] CAP normal supply implied by the CY2026 Tier 1 statement; source: https://www.cap-az.com/water/water-supply/colorado-river-operations-2/; derivation: 512,000 af / 0.30 (CAP states the Tier 1 cut is 30% of CAP's normal supply; 30% is rounded, so this is approximate)
- [DERIVED] Phoenix monthly weather-generator statistics; derivation: aquaos.core.demand.temperature.fit_climate: monthly means, anomaly SD, lag-1 autocorrelation, max/min anomaly correlation from GHCN-Daily 2019-2025; diurnal shape = mean min-max-normalized hourly cycle Jun-Aug 2023
- [PRIMARY] A.R.S. 45-852.01(C): long-term storage credit for stored water; source: https://www.azleg.gov/ars/45/00852-01.htm; retrieved 2026-09-22 — "The director shall credit ninety-five percent of the recoverable amount of stored water that meets the requirements of subsection B". Exceptions exist (e.g. 50% for some effluent storage; 100% in listed cases). Scenarios storing effluent must override this value.
- [PRIMARY] CAP: Arizona is taking Tier 1 reductions for 2026; source: https://www.cap-az.com/water/water-supply/colorado-river-operations-2/; retrieved 2026-09-22 — Page text: "This represents a 512,000 acre-foot reduction to Arizona's Colorado River water supply, constituting 30% of CAP's normal supply ... Nearly all the reductions within Arizona have been taken by Central Arizona Project (CAP) water users."
- [PRIMARY] NOAA GHCN-Daily TMAX/TMIN, Phoenix Sky Harbor (USW00023183), 2019-2025; source: https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00023183&startDate=2019-01-01&endDate=2025-12-31&dataTypes=TMAX%2CTMIN&format=csv&units=metric&includeStationName=true; retrieved 2026-09-22
- [PRIMARY] NOAA Global Hourly (ISD) temperature, Phoenix Sky Harbor (72278023183), Jun-Aug 2023; source: https://www.ncei.noaa.gov/access/services/data/v1?dataset=global-hourly&stations=72278023183&startDate=2023-06-01&endDate=2023-08-31&dataTypes=TMP&format=csv; retrieved 2026-09-22
- [SYNTHETIC] AMA-style groundwater budget (phoenix AMA label); derivation: Scenario input: allowance 2500.0 af/yr, pumped to date 1300.0 af. Not an ADWR determination.
- [SYNTHETIC] CAP M&I subcontract = 6000.0 af/yr — Valley City is synthetic; the subcontract volume is a scenario input.
- [SYNTHETIC] CAP delivery to city under 'cy2026_tier1'; derivation: contract x (1 - mi_reduction_fraction), shaped by monthly delivery factors
- [SYNTHETIC] M&I subcontract reduction fraction = 0.0 — Share of the city's CAP subcontract cut under the chosen shortage condition. Depends on CAP priority pools and intrastate agreements; not published per subcontractor in the sources used.
- [SYNTHETIC] Nodal demand time series; derivation: aquaos.core.demand.model.build_demand: diurnal x temperature response x AR(1) noise; coefficients from scenario demand classes
- [SYNTHETIC] Recharge credit balance; derivation: Scenario input: starting balance 5000.0 af (synthetic utility)
- [SYNTHETIC] Synthetic hourly temperature (AR(1) weather generator); derivation: Monthly AR(1) daily max/min anomalies + fitted diurnal shape; statistics from parent record
- [SYNTHETIC] Valley City synthetic network; derivation: aquaos.core.network.valley_city.build_valley_city from scenario generator parameters and seed

## Network validation warnings

- 16 junction(s) have no zone tag; zone-level reporting will group them as 'untagged'

See `docs/limitations.md` for model simplifications.
