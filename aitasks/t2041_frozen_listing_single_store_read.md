---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Implementing
labels: [frozen, ait_ide]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2039
followup_kind: review_finding
implemented_with: claudecode/opus5_5
created_at: 2026-10-16 12:51
updated_at: 2026-10-19 13:16
---

## Context

Review finding on t2039 (confirmed, follow-up disposition — it does not block
t2039).

`agent_reopen._frozen_records()` (`.aitask-scripts/lib/agent_reopen.py`) lists
the store once, then calls `frozen_ops.store_show(<id>)` for every frozen record.
Each `store_show` is a separate `aitask_agent_sessions.sh show` subprocess (shell
wrapper + Python), and each one reloads the whole global JSON store
(`~/.config/aitasks/agent_sessions.json`).

Since t2039, every `ait ide` start runs this over ALL projects, twice:
`gone --all-roots` (the offer listing) and `companions --all-roots` (the
companion top-up) — the second even when every viewer is already tracked. With
100 frozen records that is about 202 store subprocesses before `ait ide`
attaches, plus the tmux probes. Before t2039 the cost was per project and once.
R/P add a third pass (the re-classification `gone --all-roots`).

## Wanted

One store read per `gone` / `companions` / `reopen --root` invocation:

- reuse the validated reader `agent_sessions.load()` (the same parsing and
  validation `list` / `show` use), or add an equivalent batch read verb to the
  store wrapper, and build the full records from that one read;
- keep the error contract: a store that cannot be read is still
  `GONE_ERROR:*|store unreadable` / `COMPANION_ERROR:*|store unreadable` /
  `REOPEN_FAILED:*|store unreadable`, never an empty listing;
- keep the shared-module seam rule (tests swap `agent_frozen_ops.store` in place;
  `tests/test_agent_frozen_ops.py` enforces it) — whatever replaces the per-record
  `store_show` must stay swappable the same way;
- `reopen_one` re-reads its record UNDER THE LEASE on purpose
  (`store_show` after `lease-take`); that read must stay a fresh per-record read —
  only the listing pass is batched.

Optionally: let `ait ide` reuse one classification for both the offer and the
top-up when no action changed anything in between (only if it stays simple).

## Verification

- `python3 tests/test_agent_reopen.py`: a test that counts store calls for
  `gone --all-roots` and `companions --all-roots` over N records (one list/batch
  read, not N `show` calls), and the unreadable-store cases.
- `bash tests/test_ide_frozen_offer.sh`, `bash tests/test_frozen_reopen_live.sh`,
  `bash tests/test_ide_frozen_all_projects_live.sh`.
- Measure `aitask_frozen.sh gone --all-roots` wall time on a fixture store with
  ~100 frozen records before and after.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-19T10:16:29Z status=pass attempt=1 type=human
