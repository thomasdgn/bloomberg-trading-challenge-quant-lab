# GTC Live Operations — Guide capitaine

> Status (20 October 2026): REVIEW / ADVISORY ONLY. Isolated branch. **No orders**; no production pipeline changes; no main changes; no private TMSG positions in Git.

## Why this exists

The 4-week signal on main is anchored to 16 October for a 13 November exit. Existing Bloomberg benchmark exports on main stop at 7 October, and the shared FX table has one date (14 October). Yahoo price refresh **does not** refresh WLS. Do not rely on old benchmark data for real-time attribution, or label a proposed allocation as executed.

The existing macro engine, Bloomberg Watch and endgame-risk branches are **not imported** here. They can be reviewed separately; the macro IC experiment showed no detected effect at its prespecified resolution and cannot justify a new live trading signal.

## Input rules

Keep real inputs inside `outputs/gtc_live/` and confirm `git check-ignore outputs/gtc_live/portfolio.json` before creating them. The whole `/outputs/` directory is ignored. Do not move live positions, fills, account identifiers, terminal screenshots, secret keys or licensed Bloomberg data into `tools/`, `docs/` or tests.

Inputs are small local JSON objects, not API credentials. Every read is explicit and every failed gate exits with code 2. `status: PASS` means only **that the supplied fields satisfy these checks**; it does *not* mean Bloomberg or TMSG verified them, that an order will fill, or that a trade is recommended.

### Snapshot (executed holdings, not intended allocation)

```json
{
  "as_of_date": "2026-10-20",
  "cash_usd": 800,
  "instruments": [
    {
      "id": "SYNTHETIC UN Equity",
      "wls_member": true,
      "instrument_type": "EQUITY",
      "membership_asof": "2026-10-20",
      "price_asof": "2026-10-20",
      "currency": "USD",
      "price_local": 100,
      "price_unit_multiplier": 1,
      "usd_per_unit": 1
    }
  ],
  "positions": [{"id": "SYNTHETIC UN Equity", "quantity": 2}],
  "pending_orders": []
}
```

**This example is wholly fictitious**; do not treat `SYNTHETIC UN Equity` as an actual WLS member. `instruments` must contain every held and intended ticker, with operator-verified WLS membership, equity instrument type, market price and currency unit. `quantity` is the executed holding quantity. Cash is the reconciled USD balance. Pending orders use `order_id, status (OPEN/PARTIAL), id, side (BUY/SELL), remaining_quantity`; pending buys additionally require `limit_price_local`. Never include filled orders in the pending list or double-count their shares.

All non-USD instruments additionally require `fx_asof`. `usd_per_unit` is USD per major **one** local currency unit. A price quoted in GBp needs `price_unit_multiplier=0.01`; USD prices need `usd_per_unit=1`. Prices and FX cannot be assumed to be synchronized just because they are in one CSV. Maximum quote age is four calendar days; membership maximum age seven calendar days (these are protective gate defaults, not exchange calendars). If your verified market schedule needs other tolerances, document the reason before changing code.

### Candidate orders (never transmitted)

Use a local document with `{"snapshot": {...}, "proposals": [...]}`. A proposal is `{"client_id": "intent-1", "id": "VERIFIED UN Equity", "side": "BUY", "quantity": 5, "limit_price_local": 12.3}` (SELL proposals need no limit). A duplicated client ID, an unverified ticker, repeated pending buy, unfinanced purchase or a possible weight above 20% blocks. Existing positions above an internal **18% warning** are reported; 20% is a hard cap. Buys reserve the worse of current mark and limit, with an illustrative 20-bp buffer; this is not the competition's official fee model.

The gate does not net hypothetical proceeds from future sells against buying power. It does not estimate impact, low liquidity, cross-market opening hours or unsettled currency flows; those still require a human check.

### Freshness manifest (required for combined session gate)

```json
{
  "as_of_date": "2026-10-20",
  "sources": {
    "prices": {"verified": false, "observed_date": "2026-10-20", "provenance": ""},
    "wls_benchmark": {"verified": false, "observed_date": "2026-10-20", "provenance": ""},
    "fx": {"verified": false, "observed_date": "2026-10-20", "provenance": ""},
    "wls_membership": {"verified": false, "observed_date": "2026-10-20", "provenance": ""}
  }
}
```

**Never set `verified` to true unless the source and timestamp really were checked.** For local files, optional `path` and `sha256` entries are checked when `--file-root` is supplied to the standalone `freshness` command. Paths must stay beneath that input root. Because an operator can lie or make a mistake, true means attestation, not cryptographic or external certification.

### Daily session (recommended workflow)

`session.json` contains `snapshot` (as above), `feed_manifest` (the freshness document above) and `proposals` (list, possibly empty). Both input dates must agree, and **all** gates must pass. Review the proposed orders manually in TMSG. No action is sent to Bloomberg. Never change an `OPEN` order to `FILLED` until TMSG confirms the fill and cash.

## Commands (from project root, Python 3.14)

```powershell
python -m pytest -q tools/gtc_live/tests
python -m ruff check tools/gtc_live
python -m ruff format --check tools/gtc_live

python -m tools.gtc_live reconcile --input outputs/gtc_live/snapshot.json
python -m tools.gtc_live freshness --input outputs/gtc_live/feeds.json
python -m tools.gtc_live pretrade --input outputs/gtc_live/proposals.json
python -m tools.gtc_live session --input outputs/gtc_live/session.json
python -m tools.gtc_live stress --input outputs/gtc_live/stress.json
python -m tools.gtc_live pnl --input outputs/gtc_live/daily.json
python -m tools.gtc_live filled-pnl --input outputs/gtc_live/fills_day.json
python -m tools.gtc_live horizon --input outputs/gtc_live/horizon.json --calendar outputs/gtc_live/nyse_sessions.json
```

`stress.json` holds `snapshot` and `scenarios`; each named scenario lists a numeric USD % shock as a fraction for **every** held ticker, with none missing. It computes arithmetic marked P&L and assumes zero shock to USD cash. No scenario likelihood, liquidity impact or model-implied alpha is estimated.

`daily.json` holds `start`, `end`, `benchmark_start`, `benchmark_end`. Benchmark entries require `as_of_date`, `verified:true`, `basis:"PRICE_RETURN"`, `level` and `source`. This P&L helper **intentionally rejects** pending orders, changes in held quantities, changes in cash, and mixed return bases. It is a no-trade daily attribution tool, NOT a real-time fill-aware performance engine. On trading days use verified official TMSG performance and reconcile trades before creating a full trade-aware ledger. For dividends and corporate actions, further total-return support is required.

### Trading days: fill-aware simple daily return

For a session with trades use `filled-pnl` instead of the no-trade `pnl` helper. Its JSON input holds `start` and `end` snapshots, `benchmark_start` and `benchmark_end` as above, plus a `fills` list. **The fill list must be obtained from actual confirmed TMSG executions** in ascending UTC time (not from the exported intended orders).

A complete synthetic fill (never use this ID on a real account) is:

```json
{
  "fill_id": "SYNTHETIC_FILL_01",
  "status": "FILLED",
  "executed_at": "2026-10-21T14:35:00+00:00",
  "id": "SYNTHETIC UN Equity",
  "side": "BUY",
  "quantity": 1,
  "execution_price_local": 100,
  "currency": "USD",
  "price_unit_multiplier": 1,
  "usd_per_unit": 1,
  "fee_usd": 1
}
```

For a non-USD execution additionally supply `fx_observed_at` with a timezone and a verified conversion valid *no later than* execution. Every fill requires a real unique execution ID, fee and verified local price. The module recomputes ending quantities and cash independently, refuses implied borrowing or short selling, and checks the sum of position P&L against the difference in NAV. Any discrepancy blocks the report. It reports both simple portfolio return and WLS-relative return, but not intraday time-weighted contributions. It cannot handle external cash flows, splits, dividends, stock lending, trade settlement timing, or corporate actions: manually reconcile these before relying on the output. The official TMSG-relative P&L remains the source of truth.

`horizon.json` contains `{"as_of_date":"2026-10-20"}`; `nyse_sessions.json` is an operator-verified sorted ISO date list covering the decision date through 13 November. The function counts sessions only. It does **not** assume the same forecast horizon as the original 16 October four-week signal, adjust the alpha automatically or submit orders.

## Daily checklist (20 Oct → 13 Nov)

1. Export TMSG **executed** positions and orders with timestamps; reconcile settled cash and all pending/partial fills. An unfilled BUY never becomes a position.
2. Export updated WLS membership, benchmark levels, adjusted/price-return conventions, listing/currency/unit and local FX from Bloomberg. Compare observation timestamps and underlying definitions.
3. Run `session` with empty proposals before research. A blocked output is a **do not trade** signal, not a request to relax limits.
4. Separately check corporate actions, earnings dates, actual fees, overnight gaps, exchange trading hours and the competition rules with the team.
5. If proposing a rebalance, re-run `session` with the candidate intents, inspect concentration and reserve cash; submit manually **only after** discretionary team approval.
6. Archive inputs and output hashes locally to reproduce decisions, with no licensed/private data in GitHub.

## Non-goals and limitations

No scraping, no Bloomberg login/session automation, no live API, no order placement, no aggressive stop algorithm, no statistical claim of an improvement in expected rank. The historic 4w backtest does not validate the full 80/20 live book or correct survivorship, FX and limit-fill biases. The package makes those deficits visible rather than silently bypassing them.

**Next data-dependent milestones:** build a fill-aware official-P&L ingestion contract, independently reconstruct USD active exposures (WLS constituents and FX history needed), implement sector and currency concentration thresholds only after confirming metadata, and validate a remaining-horizon signal with genuine out-of-sample tests. These cannot be fabricated from missing data.
