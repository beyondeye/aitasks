---
priority: high
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [framework, gates, bash_scripts, python, test_infrastructure]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1657
created_at: 2026-09-01 12:34
updated_at: 2026-09-01 12:56
---

# Promote the ledger-block substrate to a shared seam

**Zero behaviour change.** This child ships nothing user-visible. Its entire
acceptance criterion is that the existing gate and merge test suites stay green
while the primitives that t1657_2 would otherwise duplicate move behind one seam.

## Context

Parent plan: `aiplans/p1657_task_note_mailbox_with_live_delivery.md` (read it —
it carries the full `## Inbox` format design this seam must support).

t1657_2 adds an `## Inbox` ledger to task files whose shape mirrors the existing
`## Gate Runs` ledger: append-only, marker-first blockquotes, state derived
back-to-front. Measured overlap is ~180 lines of genuinely generic code across
bash and Python; the remaining ~90% of `lib/gate_ledger.py` is gate-specific and
must NOT move.

**Why this lands first rather than as a de-duplication follow-up:** a follow-up
means shipping ~180 lines of near-duplicate parse/format/append/lock code and
trusting a later reconciliation. This repo has already watched that drift —
`aitask-audit-wrappers` exists precisely because per-agent fanout diverged that
way. Build the second consumer ON the seam, never beside it.

## Pre-phase (risk mitigation: characterize_merge_union)

**Runs before any production edit.** Pin `aitask_merge.py`'s *current* union
behaviour in a characterization test so the extraction is a change whose blast
radius is measured rather than assumed. Cover:

- the happy union of two divergent `## Gate Runs` ledgers;
- each guard's bail-to-conflict path, individually:
  - unclean section (`_section_is_clean` false — stray prose under the header),
  - a block whose `run=` is not valid ISO (`_ISO_RUN_RE` fails),
  - the ambiguous-winner case (>1 distinct block for one `(name, run, attempt)`),
  - genuinely divergent prose heads.

These are negative controls: each must produce conflict markers, NOT a silent
union. A test that only exercises the happy path would not detect the
regression this mitigation exists to prevent.

## Key files to modify

- `.aitask-scripts/lib/gate_ledger.py` — extract from; keep gate-specific parts.
- `.aitask-scripts/aitask_gate.sh` — re-point at the seam.
- `.aitask-scripts/board/aitask_merge.py` — generalize the union.
- NEW `.aitask-scripts/lib/ledger_block.py`
- NEW `.aitask-scripts/lib/ledger_block.sh`

## What moves (and only this)

**`lib/ledger_block.py`**, parameterized on block namespace and section header:

- `iso_now()`, `_atomic_write()`
- marker-block **parse** — today `parse_gate_run_blocks()`; its `MARKER_RE`
  (`gate_ledger.py:106`) hardcodes `gate:` and must take the namespace as a
  parameter.
- marker-block **build** — today `build_block()` (`gate_ledger.py:447`); its
  `MARKER_KEYS` / `BODY_KEYS` become caller-supplied.
- section ensure-and-append — today `append_block()` (`gate_ledger.py:483`),
  which is **EOF-hardcoded**. It grows a **section-order** argument so a section
  can be inserted *before* a named one. This is what t1657_2 needs so `## Inbox`
  lands above `## Gate Runs`.

**`lib/ledger_block.sh`** (bash twin):

- the per-task append lock — today `acquire_gate_lock` / `release_gate_lock` /
  `release_gate_lock_checked` / `_gate_lock_exit_trap` (`aitask_gate.sh:131-175`),
  generalized over a key namespace (`gate_<key>` → `<ns>_<key>`) on top of the
  already-generic `lib/stale_lock.sh`.
- the marker/body block formatter from `_gate_append_locked`
  (`aitask_gate.sh:334-425`).

**`aitask_merge.py`** — generalize `_union_gate_runs` (line 485) and
`_split_gate_section` (line 453) into an **ordered append-only multi-section**
union. Every existing guard is preserved verbatim in behaviour.

## What must NOT move

Everything gate-specific stays exactly where it is: `next_attempt`, `live_run`,
`derive_status`, `derive_gate_runs`, `compact_gate_summary`,
`abbreviate_gate_summary`, `format_status`, and the entire registry /
`effective_gates` / active-gates / digest half (`gate_ledger.py` from
`_frontmatter_text` onward). Promoting those would be speculative abstraction.

## Reference files for patterns

- `.aitask-scripts/lib/stale_lock.sh` — `ait_lock_dir()`, `stale_lock_acquire()`;
  already generic, the lock wrapper just needs its key namespaced.
- `aidocs/framework/shell_conventions.md` — shebang, `set -euo pipefail`,
  source-on-startup vs test-scaffold rule for the new `.sh` lib.

## Acceptance

- **The full gate + merge test suites pass unchanged. No test may be edited to
  accommodate the refactor** — that rule is the whole proof of "zero behaviour
  change", and it is what makes the claim falsifiable rather than an intention.
- `bash tests/run_all_python_tests.sh` green.
- Every `tests/test_gate_*.sh` green, including
  `tests/test_gate_lock_characterization.sh` (it pins the lock-failure message
  prefix — the generalized lock must keep it).
- Both gate backends still agree: run the gate suite with and without
  `AIT_GATES_BACKEND=python`.
- `shellcheck .aitask-scripts/lib/ledger_block.sh .aitask-scripts/aitask_gate.sh`
