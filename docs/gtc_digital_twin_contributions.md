# Contribution review — GTC Digital Twin

This document is a **navigational index**, not a claim about hours worked, ownership of another person's code, or historic work outside this branch. GitHub's individual commits, files, diffs and authors remain the source of truth. The connected GitHub identity for feature commits is **Enrique-JaraRon**; one formatting commit is attributed separately to **github-actions[bot]**.

**Review this implementation in [draft PR #11](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/pull/11)**, stacked on [draft PR #10](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/pull/10). Neither PR is merged into `main`.

| Technical contribution | Commit | Files to review |
| --- | --- | --- |
| New isolated simulation package | `112a48d4` | `tools/gtc_twin/__init__.py` |
| Point-in-time eligibility, USD/WLS and long-only cap checks | `2a7e3e33` | `schema.py` |
| Paired, reproducible block-bootstrap and explicit costs | `f6a05199` | `engine.py` |
| Standalone HTML research dashboard | `a0615749` | `report.py` |
| Hash-chained decision/checkpoint/outcome ledger | `ce0f3de8` | `journal.py` |
| Command-line workflow | `2c7dbad8` | `__main__.py` |
| Synthetic scenario fixtures | `67b8d7e0` | `tests/conftest.py` |
| Paired bootstrap/fee/leakage tests | `0928ae50` | `tests/test_engine.py` |
| HTML escaping and report tests | `fa09aaec` | `tests/test_report.py` |
| Journal integrity and chronology tests | `b4855161` | `tests/test_journal.py` |
| One-command fictional demo | `fb744b57` | `demo.py` |
| Reproducibility runbook | `c96bc34b` | `docs/gtc_digital_twin.md` |
| CI tests plus downloadable synthetic review artifact | `0b20dc1b` | `.github/workflows/gtc-digital-twin.yml` |

## How reviewers can assess actual work

1. Open the [Files changed tab](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/pull/11/files) and the [Commits tab](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/pull/11/commits).
2. Run `python -m pytest -q tools/gtc_twin/tests` and inspect the GitHub Actions checks.
3. Run the documented fictional demo and open the locally generated HTML.
4. Inspect each commit's author separately from its committer; automated format-only work is intentionally identified as a bot contribution.
5. **Do not** interpret synthetic simulation wins as predictions, validated alpha or a competition top-1 probability.

The older baseline work is not reassigned or rewritten. For retrospective credit on earlier large contributions, cite their original historical commits/PRs directly rather than inventing additional commits.
