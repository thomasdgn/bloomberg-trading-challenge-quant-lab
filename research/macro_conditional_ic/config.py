"""Choices fixed before any IC is partitioned by a macro label."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs" / "macro_conditional_ic"
PREPARED = OUTPUT / "prepared"
PROTOCOL = ROOT / "docs/macro_engine/PROTOCOLE_IC_CONDITIONNEL.md"
SNAPSHOT = ROOT / "docs/macro_engine/INPUTS_IC_CONDITIONNEL.json"
MDE_TABLE = ROOT / "docs/macro_engine/MDE_IC_CONDITIONNEL.csv"
TAG = "protocol-ic-v1.0"
CORE_COMMIT = "1bda3897678168b1a980d44c3cddde892f417158"
CORE_FILES = (
    "src/elastic_net_transversal.py",
    "src/tail_model_v1.py",
    "src/combined_signal_v1.py",
    "src/validate_elastic_net.py",
)
PANEL = (
    Path(r"C:\Users\degar\Desktop\Code\Bloomberg Challenge")
    / "bloomberg-trading-challenge-quant-lab/outputs/audit_2026-10-10"
    / "main_snapshot/data/processed/features_weekly_v1.csv.gz"
)
PANEL_SHA256 = "62f13e8cd8ed1ac5a38bf1808ff8b25b026e7922f2860c002ed4276346686ece"
LEGACY_PREDICTIONS = PANEL.parent / "elastic_net_predictions_v1.csv.gz"
LEGACY_IC_OFFSETS = PANEL.parent / "validation/offset_ic.csv"
LABEL_DIRECTORY = ROOT / "outputs/macro_engine/2026-10-16_H_strict"
HORIZON_WEEKS = 5
OFFSETS = tuple(range(HORIZON_WEEKS))
SCORES = ("elastic_net", "combined")
SCORE_COLUMNS = {"elastic_net": "predicted_excess_return", "combined": "combined_score"}
ABLATIONS = ("with_news", "without_news")
FAMILY_ALPHA = 0.05
POWER = 0.80
UNIQUE_LABELS = 11
HYPOTHESES = len(SCORES) * UNIQUE_LABELS * len(OFFSETS)
BLOCK_LENGTH = 2  # Consecutive five-week observations: ten calendar weeks.
MIN_BLOCKS_PER_GROUP = 20  # Nonoverlapping five-week outcomes in EACH group.
BOOTSTRAP_REPLICATES = 100_000
BOOTSTRAP_SEED = 20261018
BOOTSTRAP_BATCH = 2_000
MIN_VALID_BOOTSTRAP_FRACTION = 0.99
CONSISTENT_OFFSETS = 4
DATA_FILENAME = "predictions_5w.parquet"
IC_FILENAME = "unconditional_ic.csv"
PREPARED_MANIFEST = "prepared_manifest.json"
