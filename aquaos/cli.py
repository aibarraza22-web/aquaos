"""AquaOS command-line interface."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import warnings
from pathlib import Path


def _cmd_run(args: argparse.Namespace) -> int:
    from aquaos.core.report import write_report
    from aquaos.core.scenario import load_scenario
    from aquaos.core.sim.runner import run_scenario
    from aquaos.core.store import ResultsStore

    scn = load_scenario(args.scenario)
    store = ResultsStore(args.out)
    h = scn.scenario_hash()
    run_dir = store.run_dir(h)
    run = run_scenario(scn, workdir=run_dir / "epanet")
    store.save(run)
    report = write_report(run, run_dir)
    k = run.kpis()
    print(f"{scn.name}  hash={h[:16]}  synthetic={run.synthetic}")
    print(f"  energy {k['energy_kwh']:,.0f} kWh  peak {k['peak_kw']:,.0f} kW  "
          f"min pressure {k['min_pressure_psi']:.1f} psi  closure {k['mass_balance_closure_rel']:.3%}")
    print(f"  report: {report}")
    return 0


def _cmd_hash(args: argparse.Namespace) -> int:
    from aquaos.core.scenario import load_scenario

    print(load_scenario(args.scenario).scenario_hash())
    return 0


def _cmd_validate_inp(args: argparse.Namespace) -> int:
    from aquaos.core.network.loader import load_inp, validate_network

    ln = load_inp(args.inp)
    rep = validate_network(ln.wn)
    print(ln.wn.describe())
    for e in rep.errors:
        print(f"ERROR: {e}")
    for w in rep.warnings:
        print(f"warning: {w}")
    return 0 if rep.ok else 1


def _cmd_build_network(args: argparse.Namespace) -> int:
    from aquaos.core.scenario import load_scenario
    from aquaos.core.sim.runner import build_network

    scn = load_scenario(args.scenario)
    out = Path(args.out)
    ln, _ = build_network(scn, out.parent)
    if ln.path and ln.path.resolve() != out.resolve():
        out.write_bytes(ln.path.read_bytes())
    print(f"wrote {out}")
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    from aquaos.data.connectors import noaa, usbr

    if args.dataset == "usbr-24mo":
        proj = usbr.fetch_lake_mead(refresh=args.refresh)
        print(proj.study)
        print(proj.data.to_string())
    elif args.dataset in ("noaa-hourly", "noaa-daily"):
        start, end = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
        fn = noaa.fetch_hourly if args.dataset == "noaa-hourly" else noaa.fetch_daily
        station = args.station or (noaa.PHX_ISD if args.dataset == "noaa-hourly" else noaa.PHX_GHCND)
        rec = fn(station, start, end)
        print(rec.provenance.summary())
        print(rec.data.describe().to_string())
    return 0


def main(argv: list[str] | None = None) -> int:
    warnings.filterwarnings("ignore", category=UserWarning, module="wntr")
    p = argparse.ArgumentParser(prog="aquaos", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a scenario and write a report")
    r.add_argument("scenario")
    r.add_argument("--out", default="runs")
    r.set_defaults(fn=_cmd_run)

    h = sub.add_parser("hash", help="print a scenario's canonical hash")
    h.add_argument("scenario")
    h.set_defaults(fn=_cmd_hash)

    v = sub.add_parser("validate-inp", help="load and validate an EPANET .inp file")
    v.add_argument("inp")
    v.set_defaults(fn=_cmd_validate_inp)

    b = sub.add_parser("build-network", help="write the scenario's network as an EPANET .inp")
    b.add_argument("scenario")
    b.add_argument("--out", required=True)
    b.set_defaults(fn=_cmd_build_network)

    f = sub.add_parser("fetch", help="download and cache a public dataset")
    f.add_argument("dataset", choices=["usbr-24mo", "noaa-hourly", "noaa-daily"])
    f.add_argument("--start")
    f.add_argument("--end")
    f.add_argument("--station")
    f.add_argument("--refresh", action="store_true")
    f.set_defaults(fn=_cmd_fetch)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
