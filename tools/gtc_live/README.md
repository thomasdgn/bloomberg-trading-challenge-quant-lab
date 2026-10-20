# GTC Live Operations (research / decision support only)

This isolated package supplements, but **does not change**, `src/`, any existing trading signal, optimizer, exports, data files or challenge orders. All outputs are advisory. It does not connect to TMSG, submit trades, scrape Bloomberg, or silently fill missing data.

## Source of truth
Use only **confirmed executed fills and cash** exported / transcribed from TMSG. Pending orders are not holdings; reserved buying power is not investable cash. All filenames containing positions, fills, cash or Bloomberg licensed data belong in `outputs/gtc_live/` (ignored by .gitignore; confirm before using). Never commit real holdings.

Each workflow is blocked if required files, calendar conventions, currency conversion, WLS membership or prices cannot be verified. Sample data under tests are synthetic.

The modules are developed in separate, reviewable commits. CLI usage, input schemas, and examples are described in `docs/gtc_live_operations.md`.

**No investment return, rank, or top-1 finish is guaranteed.** Historical validation cannot replace live evaluation.
