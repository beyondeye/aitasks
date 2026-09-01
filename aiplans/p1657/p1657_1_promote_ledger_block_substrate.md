---
Task: t1657_1_promote_ledger_block_substrate.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_2_*.md, aitasks/t1657/t1657_3_*.md, aitasks/t1657/t1657_4_*.md, aitasks/t1657/t1657_5_*.md, aitasks/t1657/t1657_6_*.md
Base branch: main
Output branch: main
---

# p1657_1 — Promote the ledger-block substrate to a shared seam

## Goal

Move the ~180 lines that t1657_2 would otherwise duplicate behind one seam,
**with zero behaviour change**. Ships nothing user-visible.

## Pre-phase (risk mitigations)

### `characterize_merge_union`

**Runs before any production edit.** New `tests/test_merge_union_characterization.py`
pinning `aitask_merge.py`'s current behaviour:

1. happy union of two divergent `## Gate Runs` ledgers → resolved, blocks ordered
   by `(run, name, attempt-as-int, text)`;
2. **negative controls, one per guard — each must produce conflict markers, not a
   union** (a happy-path-only test would not catch the regression this exists to
   prevent):
   - stray prose under the ledger header → `_section_is_clean` false;
   - a block whose `run=` is not valid ISO → `_ISO_RUN_RE` fails;
   - two distinct blocks for one `(name, run, attempt)` → ambiguous winner;
   - genuinely divergent prose heads → head conflict, ledger still unioned.

Record the observed outputs as the baseline. Nothing below may change them.

## Main steps

### 1. `lib/ledger_block.py` (new)

Extract from `lib/gate_ledger.py`, parameterized on **block namespace** and
**section header**:

- `iso_now()`, `_atomic_write()` — move verbatim.
- **parse**: from `parse_gate_run_blocks()`. `MARKER_RE` (line 106) hardcodes
  `gate:` — take the namespace as a parameter and build the pattern from it.
- **build**: from `build_block()` (line 447). `MARKER_KEYS` / `BODY_KEYS` become
  caller-supplied.
- **section ensure-and-append**: from `append_block()` (line 483), today
  EOF-hardcoded. Add a **section-order** parameter so a section can be inserted
  *before* a named one. This is the capability t1657_2 needs for `## Inbox`.

Keep `GateRun` (or a generalized `LedgerBlock`) as the parsed record; if renamed,
alias it so gate call sites are untouched.

### 2. `lib/ledger_block.sh` (new)

- per-task append lock: from `acquire_gate_lock` / `release_gate_lock` /
  `release_gate_lock_checked` / `_gate_lock_exit_trap` (`aitask_gate.sh:131-175`),
  generalized over a key namespace (`gate_<key>` → `<ns>_<key>`) on top of the
  already-generic `lib/stale_lock.sh`.
  **Preserve the failure-message prefix** — `tests/test_gate_lock_characterization.sh`
  pins it.
- marker/body block formatter: from `_gate_append_locked` (`aitask_gate.sh:334-425`).

Follow `aidocs/framework/shell_conventions.md`: `#!/usr/bin/env bash`,
`set -euo pipefail`, idempotent source guard (`_AIT_LEDGER_BLOCK_LOADED`) as in
`lib/pid_anchor.sh`.

### 3. `board/aitask_merge.py`

Generalize `_split_gate_section` (453) and `_union_gate_runs` (485) into an
**ordered append-only multi-section** union over a list of section headers.
Every guard preserved verbatim in behaviour. The head comparison must still be
"heads equal ignoring trailing blank lines → resolved".

### 4. Re-point the gate paths

`aitask_gate.sh` and `lib/gate_ledger.py` call the seam. **Nothing gate-specific
moves**: `next_attempt`, `live_run`, `derive_status`, `derive_gate_runs`,
`compact_gate_summary`, `abbreviate_gate_summary`, `format_status`, and the whole
registry / `effective_gates` / active-gates / digest half stay put.

## Verification

- **No test may be edited to accommodate the refactor.** That rule is the proof.
- `bash tests/run_all_python_tests.sh`
- every `tests/test_gate_*.sh`, incl. `test_gate_lock_characterization.sh`
- gate suite with **and** without `AIT_GATES_BACKEND=python` — both backends must
  still agree
- `shellcheck .aitask-scripts/lib/ledger_block.sh .aitask-scripts/aitask_gate.sh`
- the new characterization test, unchanged from the pre-phase baseline

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9.

## Risk

### Code-health risk: **medium**

- Touches the gate ledger and the cross-PC merge union — both load-bearing — for
  a consumer that does not exist yet · severity: medium · → mitigation: inline
  pre-phase characterize_merge_union
- The bash lock generalization could alter a pinned failure message ·
  severity: low · → mitigation: `test_gate_lock_characterization.sh`

### Goal-achievement risk: **low**

- The seam's shape is dictated by t1657_2's already-designed entry format, so it
  is not speculative; and "zero behaviour change" is falsifiable via the
  no-test-may-be-edited rule.

### Planned mitigations
- timing: pre-phase | name: characterize_merge_union | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — promoting the load-bearing cross-PC ledger union to an ordered-multi-section seam | desc: Pin aitask_merge.py's current union behaviour, including every bail-to-conflict guard, before changing it
