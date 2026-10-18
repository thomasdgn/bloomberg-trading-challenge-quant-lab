"""Re-run the audited base backtest natively, unchanged, on the hash-checked snapshot.

Run with the audit environment: <audit>/env/Scripts/python.exe run_base.py
The snapshot's own src package is imported; nothing in src/ is modified or patched.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

REPO = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO))
from research.macro_filter_backtest import config as cfg  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_snapshot() -> dict:
    observed = {name: sha256(cfg.SNAPSHOT / name) for name in cfg.SNAPSHOT_INPUT_SHA256}
    if observed != cfg.SNAPSHOT_INPUT_SHA256:
        raise ValueError(f"Snapshot inputs differ from the audit: {observed}")
    audit = {
        "periods.csv": sha256(cfg.AUDIT_PERIODS),
        "metrics.json": sha256(cfg.AUDIT_METRICS),
        "reproduce_backtest.py": sha256(cfg.AUDIT_HARNESS),
    }
    if audit != cfg.AUDIT_FILE_SHA256:
        raise ValueError(f"Audit files changed: {audit}")
    metrics = json.loads(cfg.AUDIT_METRICS.read_text(encoding="utf-8"))
    code = {
        str(path.relative_to(cfg.SNAPSHOT)): sha256(path)
        for path in sorted((cfg.SNAPSHOT / "src").glob("*.py"))
    }
    if code != metrics["code_sha256"]:
        raise ValueError("Snapshot src differs from the code hashed by the audit harness.")
    for name, digest in metrics["inputs_sha256"].items():
        if cfg.SNAPSHOT_INPUT_SHA256[name] != digest:
            raise ValueError(f"Audit metrics disagree on {name}.")
    return {"inputs_sha256": observed, "audit_sha256": audit, "code_sha256": code}


def main() -> None:
    if cfg.BASE_RUN.exists():
        raise FileExistsError(f"{cfg.BASE_RUN} exists; no silent overwrite.")
    provenance = verify_snapshot()
    os.chdir(cfg.SNAPSHOT)
    sys.path.insert(0, str(cfg.SNAPSHOT))
    import pandas as pd
    import sklearn

    from src import backtest_execution_v2 as bt
    from src.elastic_net_transversal import FEATURES, ElasticNetConfig
    from src.trading_config import load_execution_profile

    if Path(bt.__file__).resolve().parents[1] != cfg.SNAPSHOT.resolve():
        raise RuntimeError("Imported src is not the audited snapshot.")
    profile = load_execution_profile(cfg.PROFILE)
    if profile.total_cost_bps != cfg.COST_BPS:
        raise ValueError("Cost profile differs from the protocol.")
    panel = pd.read_csv("data/processed/features_weekly_v1.csv.gz", parse_dates=["date"])
    config = ElasticNetConfig()
    periods, holdings = bt.run_backtest(panel, FEATURES, profile, config)
    cfg.BASE_RUN.mkdir(parents=True)
    periods.to_csv(cfg.BASE_RUN / "periods.csv", index=False)
    holdings.to_csv(cfg.BASE_RUN / "holdings.csv", index=False)
    manifest = {
        **provenance,
        "snapshot": str(cfg.SNAPSHOT),
        "audit_commit": cfg.AUDIT_COMMIT,
        "profile": cfg.PROFILE,
        "total_cost_bps": profile.total_cost_bps,
        "model_config": config.__dict__,
        "python": sys.version.split()[0],
        "versions": {"pandas": pd.__version__, "scikit-learn": sklearn.__version__},
        "periods_sha256": sha256(cfg.BASE_RUN / "periods.csv"),
        "holdings_sha256": sha256(cfg.BASE_RUN / "holdings.csv"),
    }
    (cfg.BASE_RUN / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Base re-run: {len(periods)} periods written to {cfg.BASE_RUN}", flush=True)


if __name__ == "__main__":
    main()
