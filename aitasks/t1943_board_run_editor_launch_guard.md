---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [board, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1911
followup_kind: upstream_defect
created_at: 2026-10-09 16:34
updated_at: 2026-10-09 16:36
---

## Origin

Spawned from t1936 during Step 8b review.

## Upstream defect

- .aitask-scripts/board/aitask_board.py:5037 — `run_editor` has the same defect as t1936's codebrowser action: `subprocess.call([editor, path])` inside `with self.suspend():` with no OSError guard (a missing $EDITOR ends the board and leaves the terminal suspended), `$EDITOR` with arguments treated as one executable, no SuspendNotSupported handling, and `@work(exclusive=True)` in the default group

## Diagnostic context

t1936 fixed the identical pattern in codebrowser (`CodeBrowserApp.action_open_in_editor`, commit 33b54e172). Textual 8.2.7's `App.suspend` resumes the driver after its yield with no `finally`, so an OSError escaping the `with` block leaves the terminal suspended, and the worker's exit_on_error then ends the app. `$EDITOR="code -w"` / `"emacsclient -t"` is passed as one argv[0] and fails the same way. In review, an unconditional `shlex.split` was found to regress unquoted executable paths with spaces (`EDITOR='/opt/my editor/bin/ed'`), so t1936 resolves whole-value-first: `shutil.which(editor)` → single argv, otherwise `shlex.split` (POSIX only; Windows keeps single argv).

Check the board's other default-group exclusive workers before choosing a group: `run_editor` being exclusive in the default group cancels whatever else the board runs there (e.g. the post-edit `load_tasks`/refresh path is fine, but any in-flight default-group worker would be cancelled by `E`).

## Suggested fix

Mirror codebrowser's `action_open_in_editor` after t1936: own worker group, whole-executable-first then `shlex.split` `$EDITOR`, catch `OSError` inside the suspend block and `SuspendNotSupported` around it, notify after resume, and skip the reload on a failed launch. Reuse the real-`App.suspend` fake-driver test pattern from `tests/test_codebrowser_open_in_editor.py`.
