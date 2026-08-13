---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [verification, backend]
gates: [risk_evaluated]
anchor: 635
followup_kind: risk_mitigation
created_at: 2026-08-10 15:17
updated_at: 2026-08-13 23:07
---

## Origin

Risk-mitigation ("after") follow-up for t1416, created at Step 8d after implementation landed.

## Risk addressed

**Goal-achievement — a ratified ledger-only surface can still disagree with the
enforcing decision.** From t1416's plan `## Risk` section:

> **Deliberate narrowing:** the monitor / minimonitor compact gate column stays
> ledger-only (no registry passed; `(mtime_ns, size)` cache key; cross-project
> cwd), so that one badge can still disagree with the enforcing decision. The
> two surfaces t1409's risk actually named — board and `ait ls` — are both
> fixed · severity: low

## Background

t1416 decided the ledger-only / re-validated split per surface. Three surfaces
now re-validate a code-bound human-gate signature (`gate_orchestrator.unlocked`,
`gate_ledger.read_task_gate_state` as used by the board, and `deps-unblock`).
Two were **ratified ledger-only** and registered in the drift guard
`tests/test_gate_ledger_only_surfaces.py`. This task revisits one of them.

`monitor_core.GateSummaryCache.summary_for` (`.aitask-scripts/monitor/monitor_core.py`)
calls `gate_ledger.read_task_gate_state(info.task_file_abs)` with **no
registry**, so it cannot classify a human gate at all and is ledger-only by
construction. Three things make it harder than the board was:

1. **The cache key.** The summary is cached on the *task file*'s
   `(st_mtime_ns, st_size)`. A code change does not touch the task file, so a
   digest-sensitive verdict would need the digest in the key — recomputed on
   every 3s tick to *check* the key, which undoes the t1111_1 optimization that
   removed the per-tick `clear()` (pinned by `tests/test_monitor_gate_cache.py`
   and `tests/test_monitor_gate_summary.py`, which count disk reads exactly).
2. **Cross-project mode.** `gate_ledger.resolve_signal_target` produces a
   **cwd-relative** witness path (`.aitask-gates/<task-id>/<gate>.signed`), while
   the monitor watches sessions from other project roots. A wrong cwd makes the
   witness read `absent` → accepted, so it fails safe today, but any fix must
   resolve the witness against the *watched project's* root, not the process cwd.
3. **Minimonitor differs from the full monitor.** Minimonitor clears the gate
   cache every refresh (`minimonitor_app.py`), the full monitor does not — so
   the two lanes have different invalidation shapes and must be decided together.

## Goal

Decide, with measurements rather than assertion, whether the monitor's compact
gate column should re-validate — and either implement it or re-ratify it with the
numbers attached.

Options to weigh:

- **Extend the cache key with the digest.** Simplest, but pays a `code_digest()`
  (~5 ms) per tick to test the key even when nothing is signed, and re-reads
  every visible task's ledger on every code change during active development.
- **Two-level key: only witness-carrying tasks become digest-sensitive.** The
  no-git pre-filter (`_has_stamped_witness`) is a cheap `os.path.exists`, so a
  task without a witness could keep today's mtime-only key while a signed one
  gains the digest. Preserves t1111_1 for the common case.
- **Re-ratify.** If the measured cost is not worth a badge that is already
  advisory (the monitor never archives anything), record the numbers in the
  drift-guard registry entry and in `aidocs/gates/gate-guarded-archival.md`, and
  close.

Whichever is chosen, the cross-project witness-path question (2) must be answered
explicitly — it is a correctness question independent of the cost one.

## Verification

- `tests/test_monitor_gate_cache.py` and `tests/test_monitor_gate_summary.py`
  must stay green, INCLUDING their exact disk-read counts — if the counts must
  change, say so and re-pin them deliberately rather than relaxing to
  `assertLessEqual`.
- If implementing: a two-refresh test in the shape of
  `tests/test_board_gate_digest_budget.py::DigestInvalidationTest` — mutate code
  between ticks, assert the column flips to `N stale` and flips back on
  re-signing (`gate_ledger.compact_gate_summary` already renders the `stale`
  segment; it is inert only because `stale_signed` is never populated here).
- If implementing: a cross-project case where the watched task lives under a
  different root than the process cwd, asserting the witness resolves against the
  watched root.
- If re-ratifying: update the reason in `LEDGER_ONLY_CONSUMERS`
  (`tests/test_gate_ledger_only_surfaces.py`) and the split table in
  `aidocs/gates/gate-guarded-archival.md` with the measured numbers, so the next
  reader inherits evidence instead of a judgement call.
