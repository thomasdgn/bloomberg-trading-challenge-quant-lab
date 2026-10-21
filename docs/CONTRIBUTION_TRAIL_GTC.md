# Engineering contribution trail — Bloomberg GTC 2026

This document records **verifiable GitHub contributions**, not unverified claims
about hours worked, lines independently written, or competition performance.
A small number of earlier large commits may represent substantial engineering
effort; a large number of later commits does not necessarily mean more effort.
For attribution always inspect **GitHub's native Author, Commit and PR metadata**.

## Original quantitative foundation already on main (Oct 2026)

The existing Git history identifies the GitHub author **Enrique-JaraRon**
(author display name *Enrique JARA RON*) for the following earlier contributions:

| Date | Existing SHA / link | Recorded commit scope |
| --- | --- | --- |
| 7 Oct | [f7d4b6cd](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/commit/f7d4b6cd) | Initial features pipeline and Elastic Net v1 baseline |
| 8 Oct | [6140e742](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/commit/6140e742) | Elastic Net code-style corrections |
| 8 Oct | [9aefb7e3](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/commit/9aefb7e3) | Alpha models, robust optimization, portfolio backtesting |
| 8 Oct | [PR #5](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/pull/5) | Original Elastic Net branch integrated to main |

These SHA links provide **contemporary original evidence** that the quantitative
foundation was committed before the competition, regardless of how few pushes
contained the work. The commit descriptions alone do not establish exclusive
authorship of every file or idea, nor invalidate teammates' contributions.

## New operational tooling, feature branch (Oct 20)

See [draft PR #10](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/pull/10)
and the branch `feature/gtc-live-ops-audit-20261020`. It isolates confirmed-fill
accounting, cash/order reconciliation, WLS-relative P&L, freshness checks,
active exposure and pre-trade validation, with synthetic regression tests.
Only a dedicated feature branch was pushed; no production trading behavior was
changed. GitHub Actions formatting commits appear under **github-actions[bot]**,
not a student identity.

## Digital Twin decision lab, feature branch (Oct 20–21)

See [draft PR #11](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/pull/11).
The review base is the **live-ops feature branch**, so this PR shows only the
Digital Twin additions rather than mixing in the preceding 49 commits.

Main engineering increments, each independently inspectable in Git's timeline:

1. Strict point-in-time, split-adjusted USD price-return and WLS input validation.
2. Paired HOLD / REBALANCE / DEFENSIVE moving-block bootstrap engine.
3. Offline HTML dashboard with historical uncertainty bands and disclosures.
4. Hash-chained research decision journal and verifiable later observations.
5. One-command **synthetic** end-to-end example for reviewer inspection.
6. CI pipeline with regression tests, static checks and fictional HTML artifact.
7. Sensitivity analysis of execution cost and block-size assumptions.

Read the SHA and exact line changes in the PR's **Commits** and **Files changed**
tabs. These documents are descriptive only: GitHub's recorded author and
commit provenance remain the authoritative source for individual credit.

## Scientific and operational cautions

Neither the Digital Twin nor the live-ops controls assert an ability to achieve
the top world ranking. Bootstrap fractions are **not calibrated odds**, official
TMSG results have not been uploaded, and historical WLS/FX coverage on main
remains stale. No source attribution, benchmark series, real fill or private
account data has been fabricated. Both draft PRs should be reviewed by the
team before any decision to merge.
