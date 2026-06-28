---
priority: low
effort: low
depends: []
issue_type: test
status: Ready
labels: [installer, upgrade, github-api, reliability]
anchor: 1075
created_at: 2026-06-28 10:09
updated_at: 2026-06-28 10:09
---

## Origin

Risk-mitigation ("after") follow-up for t1075, created at Step 8d after implementation landed.

## Risk addressed

**code-health sync-drift (inlined resolver vs lib)** — Inlined duplication of `github_latest_tag_version` in `install.sh` (it cannot source `.aitask-scripts/lib/github_release.sh` on the `curl | bash` path because the lib is not on disk until extraction). · severity: low

t1075 added `resolve_latest_version_gittags()` to `install.sh` as a copy of `github_latest_tag_version()` in `.aitask-scripts/lib/github_release.sh`, guarded only by a "Mirrors … keep in sync" comment. The two share the same `git ls-remote | sed -E | grep -E | sort -t. | tail -1` pipeline; if one is edited without the other (e.g. a sort-key or sed change), version resolution silently diverges between the standalone installer and the rest of the framework.

## Goal

Add a drift-guard test that drives the **same stubbed `git ls-remote` output** through BOTH functions and asserts identical output:

- Source `install.sh --source-only` to get `resolve_latest_version_gittags` and source `.aitask-scripts/lib/github_release.sh` to get `github_latest_tag_version` (guard the lib's double-source sentinel if needed).
- Stub `git ls-remote` once with a fixture that exercises numeric-vs-lexical ordering (e.g. tags `v0.9.0`, `v0.10.0`, `v0.2.1`) and assert both return `0.10.0`.
- Add a second fixture (e.g. a 4-part / pre-release-ish tag, or an empty result) to lock in identical edge-case behavior.

Suggested home: extend `tests/test_install_tarball_download.sh` (already sources `install.sh --source-only` and stubs `git`) or `tests/test_github_release.sh`. Run with `bash tests/<file>.sh`.
