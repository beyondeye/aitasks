---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [shadow, aitask_monitormini, aitask_monitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/opus5
created_at: 2026-08-05 17:17
updated_at: 2026-08-05 23:48
completed_at: 2026-08-05 23:48
---

Substrate spike for t1427 (reject shadow concerns; suppress next round): the
durable per-task rejection store and its single writer/reader helper. Parent
plan `aiplans/p1427_reject_shadow_concerns_suppress_next_round.md` is binding —
read its "Architecture" section first.

## Context

The concern picker (monitor/minimonitor `c`) will gain a reject action
(t1427_2) and the shadow's four concern producers will consult the store before
emitting their block (t1427_3). This child builds what both depend on: the
store, the helper, its locking/atomicity, gitignore installation, archive-time
pruning, and whitelist registration.

## Store

`.aitask-shadow/<task_id>/rejected.md` — bare task id (no `t` prefix, matching
`.aitask-gates/`), repo-root-relative, lazy `mkdir -p` by the writer,
git-ignored, never committed. One entry block per rejection:

```markdown
### r<N> | <ISO-8601 UTC> | producer: <name|unknown>
- [<priority> | <region>] <body>
```

`r<N>` monotonic (max+1). The canonical marker line is stored verbatim.

## Key files

- NEW `.aitask-scripts/aitask_shadow_rejected.sh` — subcommands below.
- `.aitask-scripts/aitask_setup.sh` — new `setup_shadow_store_gitignore()`
  modeled on `setup_gate_logs_gitignore` (~line 1956: `grep -qxF` idempotence,
  rationale comment, best-effort auto-commit), called right after it (~3719).
- `.gitignore` (repo root) — add the `.aitask-shadow/` line + comment directly.
- `.aitask-scripts/aitask_archive.sh` — in `archive_parent` and
  `archive_child`, after `release_lock`, call
  `"$SCRIPT_DIR/aitask_shadow_rejected.sh" prune "$task_num" 2>/dev/null || true`.
- NEW `tests/test_shadow_rejected.sh` — self-contained bash test.

## Helper contract

Sources `terminal_compat.sh`, `task_utils.sh`, `lib/registry_lock.sh`,
`lib/atomic_write.sh`. Task-id validation identical to
`aitask_shadow_context.sh` (strip leading `t`, `^[0-9]+(_[0-9]+)?$`, die on
malformed — the one hard error). Exit codes copy `aitask_agent_marks.sh`:
0 ok, 2 usage, 3 LOCK_BUSY (nothing written), 4 error.

- `add <task_id> [--producer <name>]` — canonical marker lines on stdin (each
  must match the `- [` marker shape; producer sanitized at the write site: no
  `|` or newline). Locked read-modify-write. Output `ADDED:<n>`.
- `list <task_id> [--machine]` — no lock (atomic rename gives whole-old-or-new
  reads). Default prints the store file verbatim; `--machine` emits
  `REJECTED:<id>|<ts>|<producer>|<marker line>` per entry (marker line LAST —
  it contains `|`; consumers parse with `split('|', 3)`). `NO_REJECTIONS`
  sentinel when empty/missing. All resolution outcomes exit 0.
- `remove <task_id> <id>...` — locked RMW; `REMOVED:<csv>` / `NOT_FOUND:<csv>`.
  TUI-invoked only (not a user-facing CLI).
- `prune <task_id>` — deletes the task's store dir with an own-root realpath
  prefix check (`aitask_explain_cleanup.sh` pattern). LOCK-COORDINATED: the
  lock dir (`rejected.md.lockd`) lives inside the pruned dir, so prune
  (1) acquires the same registry lock — busy → exit 3, deleting nothing;
  (2) removes store content but NOT the held `.lockd`; (3) releases the lock;
  (4) finishes with plain `rmdir` (never `rm -rf`) so a concurrent waiter's
  fresh lock survives. Post-prune `add` recreating the dir is accepted;
  re-pruned later.

Concurrency: every mutation holds
`registry_lock_acquire "<store>.lockd" <timeout>` and lands through
`ait_atomic_render` (every fallible renderer command `|| return 1` — renderers
must not rely on `set -e`). Never an open-coded mktemp-then-mv.

## Reference patterns

- `.aitask-scripts/aitask_agent_marks.sh:45-83` — lock-or-busy wrapper, exit
  codes, lock dir derived from data path.
- `.aitask-scripts/aitask_gate_pass.sh:91-107` — `ait_atomic_render` renderer
  shape (explicit if, not `[[ … ]] && echo` as last command).
- `.aitask-scripts/aitask_explain_cleanup.sh:57-92` — own-root prefix check +
  marker-file guard layers.

## Whitelist

Producers (t1427_3) reference the helper from SKILL.md files, so register:
`./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_shadow_rejected.sh`
(covers all 5 touchpoints; verify with `audit-helper-whitelist` first).

## Verification

- `bash tests/test_shadow_rejected.sh`: add/list/remove round-trip; machine
  protocol with `|`-laden bodies; malformed-id refusal; LOCK_BUSY path;
  [contended_append_negative_control] two-writer contention test — two
  concurrent `add`s, both entries land with distinct ids (no lost update), and
  the test provably exits 1 when lock acquisition is bypassed; prune own-root
  refusal (negative control); prune-vs-add lock coordination (prune returns
  LOCK_BUSY and deletes nothing while an add holds the lock). Each regression
  proven able to exit 1.
- `shellcheck .aitask-scripts/aitask_shadow_rejected.sh` clean.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T16:06:40Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-05T20:47:13Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-05T20:47:47Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:3ecc7dada5db6426

> **✅ gate:risk_evaluated** run=2026-08-05T20:47:47Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1427_1/risk_evaluated_2026-08-05T20:47:47Z-risk_evaluated-a1.log`
