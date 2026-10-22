---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testmap, install, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-21 15:09
updated_at: 2026-10-22 10:10
---

## Origin

Spawned from t1939 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_engine.sh:home_rollback` (and `home_on_signal`): the `home --migrate` verb does not ignore SIGPIPE. If its stdout reader dies, for example `ait engine home --migrate | head`, a caller that buffers through a pipe and is itself killed, or a `tee` killed by the same process-group signal, the verb finishes the rollback moves and then dies on its first `echo`. `HOME_SKIPPED:` / `HOME_FAILED:rollback|…` / `HOME_STRANDED:` / `HOME_RESTORE:` are then never printed.

## Diagnostic context

- The defect surfaced in t1939's review. `migrate_home_legacy` in `aitask_setup.sh` used to buffer the verb's output in `$( )`. A TERM to setup's whole process group killed setup and its buffer, while the verb handled the TERM and wrote its recovery lines into a pipe with no reader.
- On a signal the verb exits 128+signo **even when its rollback was blocked**, so those lines are the only record of where a stranded entry is and how to restore it.
- t1939 fixed setup's side: the verb now writes straight to setup's own fds, and setup outlives the signal through handler traps (test I13 in `tests/test_aitasks_home.sh`).
- The verb itself is still exposed to a dead reader for any direct caller. `home_rollback` runs `trap '' INT TERM HUP` but leaves PIPE at its default.

## Suggested fix

- Ignore PIPE for the recovery phase alongside INT/TERM/HUP in `home_rollback` and `home_on_signal` (`trap '' PIPE`; the verb is the final process, so nothing inherits it).
- Consider also writing the HOME_FAILED / HOME_STRANDED / HOME_RESTORE block to a durable file under `$AITASKS_HOME`, so a lost stdout cannot lose the restore steps. `ait engine home` could then surface that file.
- Pin this with a case in `tests/test_aitasks_home.sh`: a hook that closes the reader (for example, run the verb as `… | (exit 0)` with a competitor blocking the rollback) and asserts the tree state and the durable record.
