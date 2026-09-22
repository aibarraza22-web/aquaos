# AquaOS run report: valley_city_2027_shortage_heatwave_7d

> **SYNTHETIC:** this run uses synthetic or assumed inputs (see *Assumptions and provenance*). Its numbers describe a model system, not a real utility.

- Scenario hash: `979445918e7213bca6dc58416318f9dcd021c60a03e9165610a4f54f47139df6`
- Seed: 20270712; AquaOS 0.1.0, code fingerprint `ee13a47d80a86963`
- Period: 2027-07-12T00:00:00-07:00 to 2027-07-19T00:00:00-07:00 (7 days, 15-minute steps)
- Description: Heat-wave week in July 2027 under the 2027-2028 Operating Guidelines (AZ -760 kaf); ASSUMED 25% M&I cut.

## Key results

| KPI | Value |
|---|---|
| Water delivered | 243,024 m³ (197.0 af; avg 9.17 MGD) |
| Pumping energy | 115,068 kWh |
| Energy intensity | 0.473 kWh/m³ delivered |
| Peak pumping demand | 1,202 kW |
| Minimum pressure at a demand node | 41.3 psi |
| Node-hours below 40 psi (service) | 0.0 |
| Node-hours below 20 psi (minimum) | 0.0 |
| Unmet demand | 0 m³ (0.0 node-hours below 95% of requested) |
| Mass-balance closure error | -0.069% |

Hydraulics: PDD (full demand at 30 psi, none below 5 psi). Energy is pump electricity only (treatment-process energy is added in Phase 4). Costs need tariffs (Phase 2).

## Supply layer

- Shortage condition: **cy2027_2028_operating_guidelines**. Arizona reduction 760,000 af/yr [PRIMARY].
- If CAP absorbed all of it, the CAP-wide cut would be about 45% of normal supply [derived; context only].
- City CAP subcontract 6,000 af/yr, M&I reduction fraction 25% [ASSUMPTION], so the delivery entitlement is 4,500 af/yr.
- Treatment plant setting 0.229 m³/s. CAP water treated this run 110.2 af vs a monthly-shaped pro-rata share of 112.2 af.
- Groundwater (phoenix AMA label): pumped 31.4 af. Remaining annual allowance 900.0 af; pro-rata for this run 36.4 af.
- Recovery wells: recovered 34.6 af of stored water. Credit balance at end 4,983.6 af (credit fraction 0.95 [PRIMARY]).
- Reclaimed water delivered to the industrial user: 16.6 af.
- Maximum well drawdown (Theis, with interference): 5.37 m. Pumped volume changed 0.96% in the last drawdown iteration.

## Pressure by zone (demand junctions)

| zone | nodes | min_psi | p05_psi | median_psi | max_psi | node_hours_below_min | node_hours_below_service | node_hours_above_max |
|---|---|---|---|---|---|---|---|---|
| 1 | 74 | 42.7 | 46.5 | 63.6 | 84.6 | 0.0 | 0.0 | 0.0 |
| 2 | 75 | 41.3 | 50.0 | 66.4 | 87.3 | 0.0 | 0.0 | 0.0 |
| 3 | 74 | 46.4 | 50.0 | 66.4 | 86.2 | 0.0 | 0.0 | 0.0 |
| 4 | 72 | 44.2 | 49.6 | 64.5 | 85.8 | 0.0 | 0.0 | 0.0 |
| reclaimed | 1 | 48.3 | 48.6 | 50.5 | 52.6 | 0.0 | 0.0 | 0.0 |

Thresholds are configurable engineering choices (`report:` in the scenario), not regulatory citations.

## Storage tanks

| tank | min_level_m | max_level_m | start_level_m | end_level_m | design_min_m | design_max_m | hours_at_min | hours_at_max |
|---|---|---|---|---|---|---|---|---|
| T1 | 2.50 | 6.50 | 6.50 | 4.03 | 1.00 | 10.00 | 0.00 | 0.00 |
| T2 | 2.65 | 9.03 | 6.50 | 4.86 | 1.00 | 10.00 | 0.00 | 0.00 |
| T3 | 3.89 | 9.04 | 6.50 | 4.32 | 1.00 | 10.00 | 0.00 | 0.00 |
| T4 | 2.07 | 8.97 | 6.50 | 5.53 | 1.00 | 10.00 | 0.00 | 0.00 |
| CLEARWELL | 1.93 | 5.20 | 3.50 | 2.64 | 0.50 | 5.50 | 0.00 | 0.00 |
| RCL_TANK | 4.00 | 6.99 | 4.50 | 6.05 | 1.00 | 8.00 | 0.00 | 0.00 |

## Pump energy

| pump | kind | kwh | volume_m3 | kwh_per_m3 | peak_kw | run_hours |
|---|---|---|---|---|---|---|
| HS1 | high_service | 23375.34 | 135024.72 | 0.17 | 142.20 | 164.50 |
| HS2 | high_service | 246.23 | 1299.20 | 0.19 | 141.31 | 1.75 |
| B2_1 | booster | 13251.54 | 112264.61 | 0.12 | 86.22 | 154.50 |
| B2_2 | booster | 0.00 | 0.00 | nan | 0.00 | 0.00 |
| B3_1 | booster | 8485.67 | 84645.52 | 0.10 | 54.84 | 157.50 |
| B3_2 | booster | 66.85 | 527.86 | 0.13 | 53.76 | 1.25 |
| B4_1 | booster | 4091.81 | 43880.16 | 0.09 | 27.44 | 155.75 |
| B4_2 | booster | 691.18 | 6704.75 | 0.10 | 27.44 | 25.50 |
| GW2_1 | well | 16105.72 | 19436.97 | 0.83 | 125.18 | 130.00 |
| GW2_2 | well | 2983.92 | 3644.71 | 0.82 | 125.57 | 24.00 |
| GW2_3 | well | 2459.30 | 3019.72 | 0.81 | 125.48 | 19.75 |
| GW3_1 | well | 9931.85 | 10739.50 | 0.92 | 140.35 | 71.25 |
| GW3_2 | well | 1679.10 | 1840.51 | 0.91 | 140.47 | 12.00 |
| RW1 | recovery_well | 14097.48 | 21797.49 | 0.65 | 87.91 | 161.25 |
| RW2 | recovery_well | 13485.33 | 20849.80 | 0.65 | 87.88 | 154.25 |
| RCL_P1 | reclaimed | 4117.10 | 20435.72 | 0.20 | 36.47 | 114.00 |
| RCL_P2 | reclaimed | 0.00 | 0.00 | nan | 0.00 | 0.00 |

Wire-to-water efficiency: 75% for booster and high-service pumps, 65% for wells [SYNTHETIC].

## Mass balance

- Maximum instantaneous continuity residual: 1.38e-06 m³/s (2.39e-06 of peak demand).
- Sources 237,680 m³ = demand 243,024 m³ + storage change -5,182 m³ (closure error -0.069%).
- Tank volume consistency (level-derived vs integrated inflow, relative to throughput): T1 0.61%, T2 0.96%, T3 0.23%, T4 0.12%, CLEARWELL 3.10%, RCL_TANK 0.63%. At 15-minute reporting, pump switches between report steps are not sampled; errors of a few percent are resolution effects (they vanish at 5-minute steps).

## Assumptions and provenance

- [DERIVED] CAP normal supply implied by the CY2026 Tier 1 statement; source: https://www.cap-az.com/water/water-supply/colorado-river-operations-2/; derivation: 512,000 af / 0.30 (CAP states the Tier 1 cut is 30% of CAP's normal supply; 30% is rounded, so this is approximate)
- [DERIVED] Phoenix monthly weather-generator statistics; derivation: aquaos.core.demand.temperature.fit_climate: monthly means, anomaly SD, lag-1 autocorrelation, max/min anomaly correlation from GHCN-Daily 2019-2025; diurnal shape = mean min-max-normalized hourly cycle Jun-Aug 2023
- [PRIMARY] A.R.S. 45-852.01(C): long-term storage credit for stored water; source: https://www.azleg.gov/ars/45/00852-01.htm; retrieved 2026-09-22 — "The director shall credit ninety-five percent of the recoverable amount of stored water that meets the requirements of subsection B". Exceptions exist (e.g. 50% for some effluent storage; 100% in listed cases). Scenarios storing effluent must override this value.
- [PRIMARY] Colorado River Guidelines for Coordinated Operations of Lake Powell and Lake Mead, Operating Years 2027 and 2028, Section 5.3.A; source: https://www.usbr.gov/ColoradoRiverBasin/post2026/decision-doc/2027-2028OperatingGuidelines_Final.pdf; doc: 2027-2028 Operating Guidelines (August 2026), Section 5.3.A.1-2; retrieved 2026-09-22 — "Of the 6.25 maf ... 2.04 maf shall be apportioned for use in Arizona ... reflecting reductions of 760,000 af in Arizona". Consultation is triggered if the Most Probable 24-Month Study shows Lake Mead below 1,010 ft within 12 months (Section 5.3.A.4), so deeper actions are possible and should be explored as scenarios.
- [PRIMARY] NOAA GHCN-Daily TMAX/TMIN, Phoenix Sky Harbor (USW00023183), 2019-2025; source: https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00023183&startDate=2019-01-01&endDate=2025-12-31&dataTypes=TMAX%2CTMIN&format=csv&units=metric&includeStationName=true; retrieved 2026-09-22
- [PRIMARY] NOAA Global Hourly (ISD) temperature, Phoenix Sky Harbor (72278023183), Jun-Aug 2023; source: https://www.ncei.noaa.gov/access/services/data/v1?dataset=global-hourly&stations=72278023183&startDate=2023-06-01&endDate=2023-08-31&dataTypes=TMP&format=csv; retrieved 2026-09-22
- [SYNTHETIC] AMA-style groundwater budget (phoenix AMA label); derivation: Scenario input: allowance 2500.0 af/yr, pumped to date 1600.0 af. Not an ADWR determination.
- [SYNTHETIC] CAP M&I subcontract = 6000.0 af/yr — Valley City is synthetic; the subcontract volume is a scenario input.
- [SYNTHETIC] CAP delivery to city under 'cy2027_2028_operating_guidelines'; derivation: contract x (1 - mi_reduction_fraction), shaped by monthly delivery factors
- [SYNTHETIC] Heat-wave perturbation; derivation: +4.0 degC peak / +5.0 degC night, days 1.5..5.5, ramp 1.0 d, applied to parent series
- [SYNTHETIC] M&I subcontract reduction fraction = 0.25 — Share of the city's CAP subcontract cut under the chosen shortage condition. Depends on CAP priority pools and intrastate agreements; not published per subcontractor in the sources used.
- [SYNTHETIC] Nodal demand time series; derivation: aquaos.core.demand.model.build_demand: diurnal x temperature response x AR(1) noise; coefficients from scenario demand classes
- [SYNTHETIC] Recharge credit balance; derivation: Scenario input: starting balance 5000.0 af (synthetic utility)
- [SYNTHETIC] Synthetic hourly temperature (AR(1) weather generator); derivation: Monthly AR(1) daily max/min anomalies + fitted diurnal shape; statistics from parent record
- [SYNTHETIC] Valley City synthetic network; derivation: aquaos.core.network.valley_city.build_valley_city from scenario generator parameters and seed

## Network validation warnings

- 16 junction(s) have no zone tag; zone-level reporting will group them as 'untagged'

See `docs/limitations.md` for model simplifications.
