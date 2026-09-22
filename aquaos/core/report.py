"""Markdown run report. Every report carries its assumptions: scenario hash, provenance tree, synthetic flags."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import aquaos
from aquaos.core.sim.runner import RunResult
from aquaos.core.units import m3_to_af, m3s_to_mgd
from aquaos.data.provenance import Provenance, require_provenance

BANNER = ("> **SYNTHETIC:** this run uses synthetic or assumed inputs (see *Assumptions and provenance*). "
          "Its numbers describe a model system, not a real utility.")


def _table(df: pd.DataFrame, floatfmt: str = ".2f") -> str:
    df = df.reset_index()
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(format(v, floatfmt))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _prov_lines(p: Provenance) -> list[str]:
    out = []
    for q in p.flatten():
        if q.title.startswith("AquaOS run"):
            continue
        out.append(f"- {q.summary()}" + (f" — {q.notes.strip()}" if q.notes else ""))
    return sorted(set(out))


def render_markdown(run: RunResult) -> str:
    prov = require_provenance(run, "run result")
    scn = run.scenario
    k = run.kpis()
    mb = run.mass_balance
    lines = [f"# AquaOS run report: {scn.name}", ""]
    if prov.synthetic:
        lines += [BANNER, ""]
    lines += [
        f"- Scenario hash: `{run.scenario_hash}`",
        f"- Seed: {scn.seed}; AquaOS {aquaos.__version__}, code fingerprint `{aquaos.code_fingerprint()[:16]}`",
        f"- Period: {run.index[0].isoformat()} to {run.index[-1].isoformat()} "
        f"({scn.time.duration_days:g} days, {scn.time.report_step_s // 60}-minute steps)",
        f"- Description: {scn.description}",
        "",
        "## Key results",
        "",
        "| KPI | Value |",
        "|---|---|",
        f"| Water delivered | {k['demand_m3']:,.0f} m³ ({m3_to_af(k['demand_m3']):,.1f} af; "
        f"avg {m3s_to_mgd(k['demand_m3'] / scn.time.duration_s):.2f} MGD) |",
        f"| Pumping energy | {k['energy_kwh']:,.0f} kWh |",
        f"| Energy intensity | {k['kwh_per_m3_delivered']:.3f} kWh/m³ delivered |",
        f"| Peak pumping demand | {k['peak_kw']:,.0f} kW |",
        f"| Minimum pressure at a demand node | {k['min_pressure_psi']:.1f} psi |",
        f"| Node-hours below {scn.report.service_pressure_psi:g} psi (service) | "
        f"{k['node_hours_below_service']:,.1f} |",
        f"| Node-hours below {scn.report.min_pressure_psi:g} psi (minimum) | {k['node_hours_below_min']:,.1f} |",
        f"| Unmet demand | {k['unmet_demand_m3']:,.0f} m³ ({k['unmet_demand_node_hours']:,.1f} node-hours below "
        f"95% of requested) |",
        f"| Mass-balance closure error | {mb.closure_error_rel:.3%} |",
        "",
        f"Hydraulics: {scn.hydraulics.demand_model} (full demand at {scn.hydraulics.required_pressure_psi:g} psi, "
        f"none below {scn.hydraulics.minimum_pressure_psi:g} psi). "
        "Energy is pump electricity only (treatment-process energy is added in Phase 4). Costs need tariffs "
        "(Phase 2).",
        "",
        "## Supply layer",
        "",
    ]
    s = run.supply
    if run.cap is not None:
        c = run.cap
        lines += [
            f"- Shortage condition: **{c.condition}**. Arizona reduction {c.az_reduction.value:,.0f} af/yr "
            f"[{c.az_reduction.provenance.label}].",
            f"- If CAP absorbed all of it, the CAP-wide cut would be about {c.implied_cap_wide_cut_fraction:.0%} of "
            f"normal supply [derived; context only].",
            f"- City CAP subcontract {c.contract_af:,.0f} af/yr, M&I reduction fraction "
            f"{c.mi_reduction_fraction:.0%} [ASSUMPTION], so the delivery entitlement is {c.delivered_af:,.0f} "
            f"af/yr.",
            f"- Treatment plant setting {float(s['cap_wtp_setting_m3s']):.3f} m³/s. CAP water treated this run "
            f"{float(s['cap_delivered_af']):.1f} af vs a monthly-shaped pro-rata share of "
            f"{float(s['cap_pro_rata_af']):.1f} af"
            + (" — **exceeds pro-rata**" if s["cap_exceeds_pro_rata"] else "") + ".",
        ]
    lines += [
        f"- Groundwater ({run.groundwater.ama} AMA label): pumped {float(s['groundwater_pumped_af']):.1f} af. "
        f"Remaining annual allowance {float(s['groundwater_remaining_before_af']):,.1f} af; pro-rata for this run "
        f"{float(s['groundwater_pro_rata_af']):.1f} af"
        + (" — **exceeds remaining allowance**" if s["groundwater_exceeds_remaining_allowance"] else "")
        + (" — exceeds pro-rata" if s["groundwater_exceeds_pro_rata"] else "") + ".",
        f"- Recovery wells: recovered {float(s['recovered_af']):.1f} af of stored water. Credit balance at end "
        f"{float(s['credit_balance_end_af']):,.1f} af (credit fraction {run.ledger.credit_fraction.value} "
        f"[{run.ledger.credit_fraction.provenance.label}])"
        + (" — **credits overdrawn**" if s["credits_overdrawn"] else "") + ".",
    ]
    if "reclaimed_delivered_af" in s:
        lines.append(f"- Reclaimed water delivered to the industrial user: {float(s['reclaimed_delivered_af']):.1f} "
                     f"af.")
    if run.drawdown_m.shape[1]:
        lines.append(f"- Maximum well drawdown (Theis, with interference): {run.drawdown_m.max().max():.2f} m. "
                     f"Pumped volume changed {run.drawdown_iteration_change:.2%} in the last drawdown iteration.")
    lines += [
        "",
        "## Pressure by zone (demand junctions)",
        "",
        _table(run.pressure, ".1f"),
        "",
        "Thresholds are configurable engineering choices (`report:` in the scenario), not regulatory citations.",
        "",
        "## Storage tanks",
        "",
        _table(run.tanks, ".2f"),
        "",
        "## Pump energy",
        "",
        _table(run.energy, ".2f"),
        "",
        f"Wire-to-water efficiency: {scn.energy.pump_efficiency:.0%} for booster and high-service pumps, "
        f"{scn.energy.well_pump_efficiency:.0%} for wells [SYNTHETIC].",
        "",
        "## Mass balance",
        "",
        f"- Maximum instantaneous continuity residual: {mb.max_abs_residual_m3s:.2e} m³/s "
        f"({mb.max_rel_residual:.2e} of peak demand).",
        f"- Sources {mb.total_source_m3:,.0f} m³ = demand {mb.total_demand_m3:,.0f} m³ + storage change "
        f"{mb.storage_change_m3:,.0f} m³ (closure error {mb.closure_error_rel:.3%}).",
        "- Tank volume consistency (level-derived vs integrated inflow, relative to throughput): "
        + ", ".join(f"{t} {v:.2%}" for t, v in mb.tank_volume_error_rel.items())
        + f". At {scn.time.report_step_s // 60}-minute reporting, pump switches between report steps are not "
        "sampled; errors of a few percent are resolution effects (they vanish at 5-minute steps).",
        "",
        "## Assumptions and provenance",
        "",
        *_prov_lines(prov),
        "",
    ]
    if run.validation_warnings:
        lines += ["## Network validation warnings", "", *[f"- {w}" for w in run.validation_warnings], ""]
    lines += ["See `docs/limitations.md` for model simplifications.", ""]
    return "\n".join(lines)


def write_report(run: RunResult, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "report.md"
    path.write_text(render_markdown(run))
    return path
