# Limitations

This file is honest about what is synthetic, simplified, or unvalidated. It is updated every phase. Every run
report links here and lists its own provenance tree.

## What is synthetic (Phase 1)

| Item | Status | Where |
|---|---|---|
| Valley City network: layout, elevations, pipes, tanks, pumps, curves | SYNTHETIC | `aquaos/core/network/valley_city.py`, `ValleyCityConfig` defaults |
| Population (40,000), per-capita use (0.45 m³/d), commercial share, fab (3,000 m³/d), data center (800 m³/d), reclaimed user (2,500 m³/d) | SYNTHETIC | `DemandConfig` defaults, scenarios |
| Diurnal patterns and temperature coefficients per customer class | SYNTHETIC, uncalibrated | `_default_classes()` |
| Weather-generator temperatures | SYNTHETIC; statistics derived from NOAA Phoenix Sky Harbor observations | `params/phoenix_climate.yaml` |
| Heat-wave perturbation (+4 °C peak, +5 °C night) | SYNTHETIC scenario choice | `scenarios/valley_city_heatwave_7d.yaml` |
| City CAP subcontract (6,000 af/yr) | SYNTHETIC | scenarios |
| Share of an Arizona shortage borne by the city's M&I subcontract | ASSUMPTION | `mi_reduction_fraction` in scenarios |
| Groundwater allowance, pumped-to-date, aquifer T/S, depth to water, regional decline | SYNTHETIC; not an ADWR determination | scenarios, `AquiferConfig` |
| Recharge credit balance and annual recharge | SYNTHETIC | scenarios |
| Pump wire-to-water efficiencies (75% / 65% wells) | SYNTHETIC | `EnergyConfig` |

What *is* sourced: the Arizona shortage reductions (CY2026 Tier 1: 512,000 af; 2027–2028 Operating Guidelines:
760,000 af), the 95% long-term storage credit rule (A.R.S. 45-852.01(C)), and the Phoenix climate statistics
(NOAA). See `params/` for provenance.

## Modeling simplifications

- **Hydraulics.** EPANET 2.2 extended-period simulation at 15-minute steps. Pressure-dependent demand (full demand
  at 30 psi, none below 5 psi) is the default. There is no transient (surge) analysis and no water quality yet.
- **Treatment plant.** Modeled as a flow-control valve with a constant setting for the whole run (the tightest
  daily CAP limit in the run window) plus clearwell level controls. Treatment-process energy, chemicals and
  recovery are not modeled until Phase 4.
- **CAP delivery.** Annual entitlement shaped by synthetic monthly factors. CAP's real ordering, scheduling,
  priority pools and excess-water pools are not modeled. The chain from an Arizona-wide reduction to a city's cut
  is an explicit assumption.
- **Groundwater.** Theis solution (confined, homogeneous, isotropic, infinite aquifer) with superposition in time
  and between wells, a flat regional water table, and a linear regional decline. Assumes static conditions at
  the start of each run (no antecedent drawdown). Well losses, partial penetration, unconfined behaviour,
  boundaries and subsidence are ignored. Drawdown feeds back into hydraulics through fixed-point iteration
  (2 iterations; the change in the last iteration is reported).
- **AMA rules.** An annual allowance with a pro-rata check stands in for Assured Water Supply accounting.
  Real AWS determinations, extinguishment credits, replenishment (CAGRD) obligations, and AMA management-plan
  conservation requirements are not modeled.
- **Recharge and recovery.** A credit ledger only. The mound under the recharge site is a fixed head offset, and
  the recovery-well location rules (area of impact, 1-mile rules) are not modeled.
- **Demand.** Temperature response acts on an EWMA of daily maxima (or hourly temperature for data-center
  cooling), so warm nights barely move residential demand. The heat-wave demand increase is therefore modest:
  about 1.5% over the week in `valley_city_heatwave_7d`. This is an uncalibrated modeling choice, not a finding.
- **Energy.** Electrical power = ρgQH/η with a constant efficiency per pump. There are no VFDs, pump efficiency
  curves, motor losses or power factor. There is no cost yet: tariffs come in Phase 2.
- **Time resolution.** The default 15-minute step does not sample pump switches that happen between report
  steps (rules are evaluated every 90 s). The effect on the Phase 1 scenarios: per-tank storage consistency up to
  about 3% (it vanishes at 5-minute steps), energy about 0.5% lower and the peak-kW snapshot up to about 13%
  different than at 5 minutes. Peak demand charges in Phase 2 should use 5-minute (or finer) runs.
- **Controls.** Rule-based tank-level controls with lead/lag setpoints and suction guards (clearwell and
  booster suction tank). This is the Phase 2 baseline. It is reasonable, but it has not been tuned against any
  real utility.

## Unvalidated

Nothing in Phase 1 has been validated against a real utility's SCADA or historian data. The mass-balance, pressure
and tank-bound tests check internal consistency and physical plausibility, not agreement with reality.
