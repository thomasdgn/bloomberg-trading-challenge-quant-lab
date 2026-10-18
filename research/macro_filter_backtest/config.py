"""Choices fixed by PROTOCOLE_FILTRE_MACRO.md before any filtered result is computed."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs" / "macro_filter_backtest"
BASE_RUN = OUTPUT / "base_run"
PROTOCOL = ROOT / "docs/macro_engine/PROTOCOLE_FILTRE_MACRO.md"
TAG = "protocol-filter-v1.0"

# Frozen audit snapshot (main 440eeff, git archive) and its native harness outputs.
AUDIT_ROOT = Path(
    r"C:\Users\degar\.codex\visualizations\2026\10\16\01a1452a-73d3-7e00-b07a-3a2d4fa52c4c"
    r"\quant_lab_audit"
)
SNAPSHOT = AUDIT_ROOT / "main"
AUDIT_PYTHON = AUDIT_ROOT / "env/Scripts/python.exe"
AUDIT_PERIODS = AUDIT_ROOT / "backtest_main/periods.csv"
AUDIT_METRICS = AUDIT_ROOT / "backtest_main/metrics.json"
AUDIT_HARNESS = AUDIT_ROOT / "reproduce_backtest.py"
AUDIT_COMMIT = "440eeff0bb588ea876217e83d060acc5be4ac06e"
SNAPSHOT_INPUT_SHA256 = {
    "data/bloomberg/data/prices_10y.csv.gz": (
        "3e6d0622430da341dd21499501de4249cb305f2b8f15a73351eaedb3f124a4fe"
    ),
    "data/bloomberg/data/volumes_10y.csv.gz": (
        "64d49355ab39398f500c42a21cb8d44210e21ef75fc9a3469bbb1dbe8e945491"
    ),
    "data/bloomberg/data/benchmark_10y.csv": (
        "28a043bf49cb7e2e9a0951fd835034814c65b5a3f030296dd36918b099322473"
    ),
    "config/execution_profiles.json": (
        "66e5e24c7ef83064a0e077f31f0013e720a0ac3badfed6fbe66b8d01bcf58d0a"
    ),
    # Recomputed by the audit pipeline; not listed in the audit metrics.json.
    "data/processed/features_weekly_v1.csv.gz": (
        "3d113e4c4967458745cc94259c437029db3ecd516e6cc9a32508b053b56614ac"
    ),
}
AUDIT_FILE_SHA256 = {
    "periods.csv": "1556015c89ddb38f074a9bc14a497a8089a5d10dacd8cebfa5c8ff91cdfe0727",
    "metrics.json": "bb502a393bbe2bd0aa2f6f6f439f8b90c49d1cfd741b4989da9096b87857a356",
    "reproduce_backtest.py": "70160c4c2cd56bea905f11383e9329e230d00f0a0b4e0acb556295bb6a72c0e6",
}
PROFILE = "sans_stop"
COST_BPS = 15.0  # commission 10 bp + slippage 5 bp in the audited sans_stop profile.

# Labels: H strict, reference cache D006, both ablations.
LABEL_DIRECTORY = ROOT / "outputs/macro_engine/2026-10-16_H_strict"
LABELS_SHA256 = "456ee3ff2d6ad191714ad43931170d4ff0cb82d02db2982ba6f0d3b7362014bb"
ABLATIONS = ("with_news", "without_news")

HORIZON_WEEKS = 5
OFFSETS = tuple(range(HORIZON_WEEKS))
PERIODS_PER_YEAR = 52 / HORIZON_WEEKS
RETURN, BENCHMARK = "net_return_5w", "benchmark_return_5w"

K_FILTERED = 0.5
K_INITIAL = 1.0  # Previous k before the first period: the unfiltered base.
FILTERS = {
    "F1": ("STRESS_MARCHE",),
    "F2": ("STRESS_MARCHE", "STRESS_CREDIT", "COURBE_INVERSEE"),
    "F3": ("INFLATION_HAUTE", "CHOC_ENERGIE"),
}
VARIANTS = ("base", "F1", "F2", "F3", "T")
PRIMARY = "F1"

PLACEBO_DRAWS = 1_000
PLACEBO_SEED = 20261019
PLACEBO_QUANTILE = 0.95

BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_BLOCK = 2  # Two consecutive five-week periods: ten calendar weeks.
BOOTSTRAP_SEED = 20261020
BOOTSTRAP_LEVEL = 0.95
