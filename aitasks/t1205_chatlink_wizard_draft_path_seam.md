---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [chatlink, tui]
anchor: 1190
created_at: 2026-07-21 17:30
updated_at: 2026-07-21 17:30
boardidx: 30
---

## Problem

t1190 added the resumable wizard draft (`chatlink/wizard_draft.py`), whose
path always resolves through `paths.sessions_dir()`. `ChatlinkApp` accepts a
custom `sessions_dir=` injection that controls the session-table store root
(`chatlink_app.py:158`), but the wizard draft ignores it: `start_wizard()`
calls `load_draft()` / `save_draft()` / `clear_draft()` without a `path`, so
an embedded or test app using a custom session store still reads/writes the
DEFAULT project draft and can see resume state unrelated to its table root.
(The t1190 TUI tests dodge this only because they monkeypatch
`paths.project_root`.)

Review finding from t1190 Step 8 (verified: CONFIRMED, disposition: follow-up).

## Goal

Thread the app's resolved sessions dir into the wizard draft path — either
pass it through `WizardSeams` (a narrow `draft_path` seam, resolved in
`resolve_seams` to `wizard_draft.draft_path()` by default) or derive it from
the app's `sessions_dir` in `action_wizard`. Keep `wizard_draft`'s explicit
`path=` kwargs as the injection surface; update `start_wizard` call sites and
the `SummaryScreen._do_save` clear to use the seam.

## Acceptance criteria

- A `ChatlinkApp(sessions_dir=<custom>)` instance reads/writes its wizard
  draft under that custom root, not the default `paths.sessions_dir()`.
- Default construction behaves exactly as today.
- A Pilot or headless test constructs the app with a custom sessions dir and
  proves draft isolation.
