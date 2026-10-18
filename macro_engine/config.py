"""Frozen specification parameters and user-approved decisions D001 and D002."""

from dataclasses import dataclass
from pathlib import Path

SPEC_VERSION = "1.0"
SPEC_SHA256 = "6b3e47b7d1119c2edb4e07dd6b79d19e371e889aac8a3781a15e1cb5fb44fce5"
QUERY_DATE = "2026-10-16"
CALENDAR = "NYSE"
HORIZON_WEEKS = 4
QUANT_LAB_STRATEGY = "final_four_week"
QUANT_LAB_TARGET = "future_excess_return_4w"
LEGACY_QUANT_LAB_TARGET = "future_excess_return_5w"
# D001: the 365-calendar-day embargo makes SPEC 7.3.3 redundant for analogue
# selection at the approved four-week horizon. Do not approximate weeks as 20
# NYSE sessions. Future conditional-IC work reads quant-lab's target column
# directly; macro_engine never recomputes forward investment returns.
EMBARGO_CALENDAR_DAYS = 365
MIN_HISTORY_SESSIONS = 1260
ANALOGUE_COUNT = 5
EPISODE_GAP_SESSIONS = 20
EPISODE_SEPARATION_MONTHS = 12
SENSITIVITY_SEPARATIONS_MONTHS = (6, 12, 24)
DISTANCE_QUANTILE = 0.05
SENSITIVITY_QUANTILES = (0.025, 0.05, 0.10)
REGIME_PERCENTILES = (0.20, 0.80)
VOLATILITY_WINDOW_SESSIONS = 20
ANNUALIZATION_SESSIONS = 252
RATE_CHANGE_SESSIONS = 126
DOLLAR_CHANGE_SESSIONS = 252
CPI_CHANGE_MONTHS = 12
UNEMPLOYMENT_CHANGE_MONTHS = 3
OIL_CHANGE_MONTHS = 12
SAMPLE_VARIABLES = {
    "H": ("CPIAUCNS", "UNRATE", "DGS2", "T10Y2Y", "BAA10Y", "SP500", "DCOILWTICO", "GPR", "EPU"),
    "R": (
        "CPIAUCNS",
        "UNRATE",
        "DGS2",
        "T10Y2Y",
        "BAA10Y",
        "SP500",
        "DCOILWTICO",
        "GPR",
        "EPU",
        "DTWEXBGS",
    ),
}
TRUNCATION_TEST_DATES = (
    "1990-08-15",
    "2001-09-17",
    "2008-09-15",
    "2020-03-16",
    "2022-02-24",
    "2026-10-16",
)
WEIGHT_TOLERANCE = 1e-12
CONTRIBUTION_TOLERANCE = 1e-9
CPI_FALLBACK_DAYS = 15
UNEMPLOYMENT_FALLBACK_DAYS = 7
NEWS_PUBLICATION_DELAY_DAYS = 10
DAILY_PUBLICATION_DELAY_BUSINESS_DAYS = 1
OIL_ADDITIONAL_BUSINESS_DAYS = 1

MODULE_ROOT = Path(__file__).resolve().parent
CACHE_ROOT = MODULE_ROOT / "cache"
REGISTRY_FILENAME = "source_registry.csv"
MANIFEST_FILENAME = "run_manifest.json"
REGISTRY_SCHEMA_VERSION = 1
FRED_API_KEY_ENV = "FRED_API_KEY"
FRED_API_BASE = "https://api.stlouisfed.org/fred"
FRED_GRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_OBSERVATION_LIMIT = 100_000
FRED_VINTAGE_LIMIT = 10_000
FRED_REALTIME_START = "1776-07-04"
FRED_MISSING_VALUE = "."
HTTP_TIMEOUT_SECONDS = 45
HTTP_USER_AGENT = "quant-lab-macro-engine/1.0 (research data collection)"
GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"
GPR_SOURCE_PAGE = "https://www.matteoiacoviello.com/gpr.htm"
GPR_COLUMN = "GPR"
GPR_START_DATE = "1985-01-01"
EPU_URL = "https://www.policyuncertainty.com/media/US_Policy_Uncertainty_Data.xlsx"
EPU_SOURCE_PAGE = "https://www.policyuncertainty.com/us_monthly.html"
EPU_START_DATE = "1985-01-01"
YAHOO_SP500_TICKER = "^GSPC"
YAHOO_HISTORY_PERIOD = "max"
YAHOO_AUTO_ADJUST = False
YAHOO_REPAIR = False
BLOOMBERG_DATE_COLUMN = "date"
BLOOMBERG_PRICE_COLUMN = "PX_LAST"
PARQUET_COMPRESSION = "zstd"
CSV_DATE_FORMAT = "%Y-%m-%d"
REQUIREMENT_PACKAGES = (
    "numpy",
    "pandas",
    "scikit-learn",
    "pyarrow",
    "requests",
    "openpyxl",
    "pandas-market-calendars",
    "plotly",
    "pytest",
    "ruff",
    "yfinance",
    "xlrd",
)


@dataclass(frozen=True)
class SeriesSpec:
    identifier: str
    variable: str
    provider: str
    frequency: str
    transformation: str
    block: str
    availability_rule: str
    pit_status: str
    use_alfred: bool = False


SERIES = (
    SeriesSpec(
        "CPIAUCNS",
        "Inflation américaine",
        "FRED/ALFRED",
        "monthly",
        "year_on_year_percent_12m",
        "Inflation",
        "ALFRED vintage valid at decision; otherwise month_end + 15 calendar days",
        "PIT_VERIFIED",
        use_alfred=True,
    ),
    SeriesSpec(
        "UNRATE",
        "Chômage américain",
        "FRED/ALFRED",
        "monthly",
        "change_3m_percentage_points",
        "Croissance",
        "ALFRED vintage valid at decision; otherwise month_end + 7 calendar days",
        "PIT_VERIFIED",
        use_alfred=True,
    ),
    SeriesSpec(
        "DGS2",
        "Taux du Trésor à 2 ans",
        "FRED",
        "daily",
        "change_126_sessions_percentage_points",
        "Monétaire et taux",
        "session J + 1 business day",
        "PIT_APPROXIMATED",
    ),
    SeriesSpec(
        "T10Y2Y",
        "Pente de la courbe",
        "FRED",
        "daily",
        "level_percentage_points",
        "Monétaire et taux",
        "session J + 1 business day",
        "PIT_APPROXIMATED",
    ),
    SeriesSpec(
        "BAA10Y",
        "Spread de crédit",
        "FRED",
        "daily",
        "level_percentage_points",
        "Crédit et stress",
        "session J + 1 business day",
        "PIT_APPROXIMATED",
    ),
    SeriesSpec(
        "SP500",
        "Volatilité réalisée S&P 500",
        "Bloomberg; explicit Yahoo fallback",
        "daily",
        "log_return_std_20_sessions_annualized_sqrt_252",
        "Crédit et stress",
        "volatility through session J usable J + 1 business day",
        "PIT_APPROXIMATED",
    ),
    SeriesSpec(
        "DCOILWTICO",
        "Pétrole WTI",
        "FRED",
        "daily_to_month_end",
        "last_monthly_valid_price_log_change_12m",
        "Énergie",
        "first business day of following month + 1 business day",
        "PIT_APPROXIMATED",
    ),
    SeriesSpec(
        "GPR",
        "Risque géopolitique",
        "Caldara/Iacoviello",
        "monthly",
        "log1p",
        "Géopolitique et incertitude",
        "month_end + 10 calendar days",
        "CONTEMPORARY_INPUT_RETRO_METHOD",
    ),
    SeriesSpec(
        "EPU",
        "Incertitude de politique économique US presse",
        "Baker/Bloom/Davis",
        "monthly",
        "log1p",
        "Géopolitique et incertitude",
        "month_end + 10 calendar days",
        "CONTEMPORARY_INPUT_RETRO_METHOD",
    ),
    SeriesSpec(
        "DTWEXBGS",
        "Dollar panier large",
        "FRED",
        "daily",
        "log_change_252_sessions",
        "Dollar",
        "session J + 1 business day; no splicing with DTWEXM",
        "PIT_APPROXIMATED",
    ),
)
