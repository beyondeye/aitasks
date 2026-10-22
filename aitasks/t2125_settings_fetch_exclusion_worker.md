---
priority: low
effort: low
depends: []
issue_type: performance
status: Implementing
labels: [task_attachments]
assigned_to: dario-e@beyond-eye.com
anchor: 1065
followup_kind: review_finding
created_at: 2026-10-22 12:46
updated_at: 2026-10-22 12:54
---

## Context

Review finding on t2099 (verified CONFIRMED, disposition: follow-up).
t2099 made the Settings TUI's Artifacts-tab save re-apply the routine-fetch
exclusion for the gitbranch artifact store:
`SettingsApp.save_artifacts_settings` → `_apply_fetch_exclusion` →
`_run_fetch_exclusion` (`.aitask-scripts/settings/settings_app.py`), which runs
`aitask_artifact.sh fetch-exclusion apply` through `subprocess.run(..., timeout=30)`
**synchronously on the Textual event loop**.

That CLI takes a repository-wide lock (`lib/artifact_fetch_exclusion.sh`
`afx_with_lock`, `AFX_LOCK_TIMEOUT` = 10s). While another apply holds it, such
as an `ait sync` guard or a concurrent CLI run, the save handler blocks for up
to 10s. A slow child can block it for the full 30s subprocess timeout. During
that time the TUI neither processes input nor repaints.

## Scope

- Run the fetch-exclusion CLI in a Textual worker (thread worker), not in the
  event handler. The config save itself stays synchronous, as it is today.
- Marshal the result toasts back to the UI thread (`call_from_thread`). Keep
  the current messages: a warning naming
  `ait artifact fetch-exclusion apply` on failure, and an info toast on
  `FETCH_EXCLUSION:CHANGED`. Stderr text stays `escape()`d.
- Read `aidocs/framework/tui_conventions.md` and
  `aidocs/framework/testing_conventions.md` first. A `@work` worker that is
  still in flight at `run_test` block exit fails the enclosing test, so the
  tests must await the worker.
- Track and cancel the worker on app exit. Two quick saves must not race to
  toast stale results; newest-wins is enough.

## Verification

- `tests/test_settings_artifacts_tab.py::FetchExclusionTests` keeps passing,
  adapted to await the worker.
- A new test: a seam that blocks, for example on an `Event`, does not block the
  save handler. The save returns, the UI stays responsive (a key press is
  processed), and the toast arrives once the seam is released.
