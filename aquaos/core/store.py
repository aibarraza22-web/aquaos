"""DuckDB results store. Runs are keyed by scenario hash. Time series go to Parquet next to the database."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import duckdb
import pandas as pd

import aquaos
from aquaos.core.sim.runner import RunResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    scenario_hash VARCHAR PRIMARY KEY,
    scenario_name VARCHAR,
    created_at TIMESTAMP,
    aquaos_version VARCHAR,
    code_fingerprint VARCHAR,
    seed BIGINT,
    synthetic BOOLEAN,
    scenario_json VARCHAR,
    provenance_json VARCHAR,
    supply_json VARCHAR
);
CREATE TABLE IF NOT EXISTS kpis (
    scenario_hash VARCHAR,
    kpi VARCHAR,
    value DOUBLE,
    PRIMARY KEY (scenario_hash, kpi)
);
"""


class ResultsStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "aquaos.duckdb"
        with self._connect() as con:
            con.execute(SCHEMA)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    def run_dir(self, scenario_hash: str) -> Path:
        return self.root / scenario_hash[:16]

    def save(self, run: RunResult) -> Path:
        d = self.run_dir(run.scenario_hash)
        d.mkdir(parents=True, exist_ok=True)
        res = run.results
        frames = {
            "pressure_m": res.node["pressure"],
            "head_m": res.node["head"],
            "demand_m3s": res.node["demand"],
            "flow_m3s": res.link["flowrate"],
            "pump_power_kw": run.power_kw,
            "temperature_c": run.temperature.at(run.index).to_frame("temp_c"),
            "drawdown_m": run.drawdown_m,
        }
        for name, df in frames.items():
            out = df.copy()
            out.index = run.index[: len(out)]
            out.index.name = "time"
            out.columns = [str(c) for c in out.columns]
            out.to_parquet(d / f"{name}.parquet")
        with self._connect() as con:
            con.execute("DELETE FROM runs WHERE scenario_hash = ?", [run.scenario_hash])
            con.execute("DELETE FROM kpis WHERE scenario_hash = ?", [run.scenario_hash])
            con.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [run.scenario_hash, run.scenario.name, dt.datetime.now(dt.UTC).replace(tzinfo=None),
                 aquaos.__version__, aquaos.code_fingerprint(), run.scenario.seed, run.synthetic,
                 run.scenario.canonical_json(), run.provenance.model_dump_json(),
                 json.dumps(run.supply, default=str)],
            )
            con.executemany("INSERT INTO kpis VALUES (?, ?, ?)",
                            [[run.scenario_hash, k, float(v)] for k, v in run.kpis().items()])
        return d

    def kpis(self, scenario_hash: str | None = None) -> pd.DataFrame:
        with self._connect() as con:
            q = ("SELECT r.scenario_name, k.* FROM kpis k JOIN runs r USING (scenario_hash)"
                 + (" WHERE scenario_hash = ?" if scenario_hash else ""))
            return con.execute(q, [scenario_hash] if scenario_hash else []).df()

    def has(self, scenario_hash: str, same_code: bool = True) -> bool:
        """True if this scenario was stored (by default only if the stored run came from the current code)."""
        q = "SELECT count(*) FROM runs WHERE scenario_hash = ?"
        args = [scenario_hash]
        if same_code:
            q += " AND code_fingerprint = ?"
            args.append(aquaos.code_fingerprint())
        with self._connect() as con:
            row = con.execute(q, args).fetchone()
        return bool(row and row[0])

    def timeseries(self, scenario_hash: str, name: str) -> pd.DataFrame:
        return pd.read_parquet(self.run_dir(scenario_hash) / f"{name}.parquet")
