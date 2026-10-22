---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [syncer, git, tui]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2126
followup_kind: upstream_defect
created_at: 2026-10-22 23:27
updated_at: 2026-10-23 00:01
---

## Origin

Spawned from t2126 during Step 8b review.

## Upstream defect

- .aitask-scripts/syncer/sync_failure_screen.py:75-79 — `SyncFailureScreen` renders the failed command's stderr through console markup, so git's `[rejected]` (and any bracketed text in a path) is swallowed from the "Output (tail)" shown to the user (reproduced: ` ! [rejected]        main -> main` renders as ` !         main -> main`).

## Diagnostic context

`SyncFailureScreen.compose` builds its body as one f-string with `[b]…[/b]` markup and interpolates `ctx.ref_name`, `ctx.command`, `ctx.status` and `ctx.stderr_tail` into it verbatim, then hands it to `Static` with markup on. Git output routinely contains square brackets — every rejected push line is ` ! [rejected] …` / ` ! [remote rejected] …`, and a path or ref may contain `[...]` — so those spans are parsed as style tags and dropped from what the user reads. Reproduced with a minimal host App: the tail ` ! [rejected]        main -> main (fetch first)` rendered as ` !         main -> main (fetch first)`, and `'/x/[bold]y.git'` as `'/x/y.git'`.

t2126 added a sibling modal (`MainConflictScreen`, same file) that avoids this by building its body with `rich.text.Text.assemble` (labels styled as tuples, values as plain strings), pinned by a render test that asserts `[rejected]` survives.

## Suggested fix

Build the `SyncFailureScreen` body with `Text.assemble` (or escape every interpolated value with `rich.markup.escape`), and add a render test in `tests/test_syncer_rows.py` asserting a `[rejected]` tail and a bracketed command render verbatim.
