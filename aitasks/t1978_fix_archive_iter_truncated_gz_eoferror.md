---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [trails, cross_repo]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1957
followup_kind: upstream_defect
created_at: 2026-10-13 18:36
updated_at: 2026-10-13 19:20
---

## Origin

Spawned from t1957_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/archive_iter.py:_iter_single_archive (gz branch) — a truncated .tar.gz raises EOFError, which the except clause (TarError/OSError/SubprocessError) does not catch, so every best-effort caller (board, stats, codebrowser, trail_gather, dep_resolution) crashes instead of skipping the bundle; t1957_3 catches it only on the opt-in errors path to keep the default path unchanged`
- `thinking_app#art:trail-build-test-speed / art:trail-localization-programme and thinking_backend#art:trail-new-prod-and-dev-servers — stored trails at schema_version 1.0.0 are rejected by the 1.1.0 schema in both repos, so they render as error cards and keep every cross-repo scan from this host partial (data in other repos; needs a refresh there)`

## Diagnostic context

t1957_3 added an opt-in `errors=` status channel to `lib/archive_iter.py` so
`trail_links` can tell "no archived record" from "could not read". Probing the
existing best-effort path (no `errors` list) with corrupt bundles showed:

- garbage `.tar.gz` → 0 records, silent (ok for best-effort);
- **truncated `.tar.gz` → `EOFError: Compressed file ended before the
  end-of-stream marker was reached` escapes the generator** (gzip raises
  `EOFError`, which is neither `tarfile.TarError` nor `OSError`, and tarfile does
  not convert it);
- garbage / truncated `.tar.zst` → 0 records, silent.

t1957_3 deliberately left the default path unchanged — it catches `EOFError`
only when the caller passes `errors=` (see the `except EOFError` branch with
`if errors is None: raise`). So a truncated gz bundle under `aitasks/archived/_bN/`
still crashes every best-effort caller.

The second bullet is data, not code: running `scan_linked_trails` from this host
reports `partial` for thinking_app and thinking_backend because three of their
stored trails carry `schema_version: 1.0.0` (verified for
`art:trail-build-test-speed`: `$.schema_version const: expected '1.1.0', got
'1.0.0'`) and both repos ship the 1.1.0 schema. Their own boards show the same
error cards.

## Suggested fix

1. In `_iter_single_archive`, treat `EOFError` like the other read failures on
   the best-effort path too (skip the bundle), i.e. drop the
   `if errors is None: raise` branch, and add a default-path test with a
   truncated `.tar.gz` (the opt-in test `test_truncated_tar_gz_is_reported`
   in `tests/test_archive_iter_consolidated.py` already builds the fixture).
2. For the stale trails: refresh them in their own repos (`/aitask-trail`
   refresh in thinking_app / thinking_backend), or decide whether
   `SCHEMA_NORMALIZATION_LOCK` (`lib/trail_gather.py`) should let 1.0.0
   documents load. Track this part in those repos if preferred
   (`ait create --batch --project <name>`).
