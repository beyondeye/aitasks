---
Task: t1692_converge_gate_lock_exit_trap_onto_seam.md
Branch: main
Base branch: main
Output branch: main
---

# t1692 — Converge the gate lock's EXIT trap onto the guarded seam

## Context

t1681 hardened `ait_ledger_lock_exit_trap` (`.aitask-scripts/lib/ledger_block.sh:144`).
It now takes an optional explicit status (validated against 0-255). In the no-arg form it
detects that it was chained behind another command in the EXIT trap. In that case it
warns and exits 1 instead of reporting the section that died as a success.

`.aitask-scripts/aitask_gate.sh:147` still has a private `_gate_lock_exit_trap`. It is a
byte-for-byte copy of the seam as it was before t1681. It is installed bare at three
sites (`:294` cmd_append, `:973` cmd_materialize_active, `:1227` cmd_begin_procedure). It
works today but has no guard, so the next person who adds cleanup in front of it at one
of those sites brings back the defect t1681 closed.

**Confirmed equivalence:** `release_gate_lock()` (`:137`) is literally
`ait_ledger_lock_release`. That is the same call the seam trap makes at
`ledger_block.sh:168`, against the same `_AIT_LEDGER_LOCK_DIR`/`_TOKEN` globals that
`acquire_gate_lock → ait_ledger_lock_acquire` set. The release/flip-0-to-1/exit
arithmetic is identical. For a bare install (first command) the only addition is the
`_ait_ledger_exit_trap_is_first` check, which returns "first" and changes nothing. So the
gate's behaviour stays unchanged at all three sites.

**Wrapping is not an option:** keeping `_gate_lock_exit_trap() { ait_ledger_lock_exit_trap; }`
would hide the guard. `_ait_ledger_exit_trap_is_first` inspects `trap -p EXIT`, and that
string would only name `_gate_lock_exit_trap`, which does not contain the seam's name. The
guard would silently report "no complaint". The sites must name the seam directly.

**Inbox note (t1738, advisory):** the BSD-awk tempfile-truncation defect it describes in
`ledger_block.sh` has since been fixed by t1741 (commit `8983db3f8`, "Fail closed on a
ledger-block append instead of truncating the task file"). This task does not touch that
code path, so nothing is folded in.

## Implementation

### 1. `.aitask-scripts/aitask_gate.sh`

- Delete `_gate_lock_exit_trap()` (`:147-153`).
- Expand the comment above `acquire_gate_lock` with a line saying that every section
  holding this lock installs the seam's trap directly. It should say not to wrap the trap
  in a gate-local function, because the seam's chained-trap guard reads `trap -p EXIT` and
  would not see a wrapper. Any cleanup must use the sanctioned chained spelling
  `trap 'rc=$?; cleanup; ait_ledger_lock_exit_trap "$rc"' EXIT` (as in `aitask_note.sh:657`).
- At each of the three sites, replace
  `trap '_gate_lock_exit_trap' EXIT` → `trap 'ait_ledger_lock_exit_trap' EXIT`.
  The existing `trap - EXIT` lines after `release_gate_lock_checked` and inside
  `_materialize_fail` stay unchanged.
- Leave `acquire_gate_lock` / `release_gate_lock` / `release_gate_lock_checked` as they
  are. Their labels and die wording are pinned by the characterization suite and are
  out of scope.

### 2. `tests/test_gate_lock_characterization.sh` — new Test 8 (gate-side guard)

Add it after Test 7, update the header's FLIP CONTRACT / test list with the new test,
and update the runtime note if needed.

**8a. Structural pin: the guard is live at every gate-lock site.**
- `grep -c 'acquire_gate_lock "\$key"' "$GATE"` equals
  `grep -c "trap 'ait_ledger_lock_exit_trap' EXIT" "$GATE"`, and both are ≥ 1. This
  keeps a newly added lock section without the seam trap from passing silently.
- `grep -q '_gate_lock_exit_trap' "$GATE"` finds nothing, so the private copy cannot
  come back.

**8b. Behavioural driver: a chained trap around a real gate-lock section is not reported
as success.** Write the driver to `$TMP/t8_chain.sh`, taking `<key> <mode>`
(`mode` = `chained` | `bare`):
- **Save the arguments first**, `t8_key="${1:?}"; t8_mode="${2:?}"`, and only then run
  `set --`. `set --` is needed so the sourced script's `main` does not see the driver's
  args, but it clears `$1`/`$2` for good. The sourced script also turns on `set -u`, so a
  later `"$1"` would hit an unbound-variable error and exit 1 *before* any lock or trap
  (reproduced in review). That would make the bare control pass vacuously (status 1, no
  warning, no lock dir).
- `. "$GATE" >/dev/null`: sourcing with no args defines every gate function and the
  sourced libs; `main ""` only prints help, which is discarded. This uses the *real*
  `acquire_gate_lock` (namespace `gate`, real labels), not a restatement.
- `declare -F acquire_gate_lock ait_ledger_lock_exit_trap >/dev/null || exit 97`. This is
  a fail-loud precondition, so a future source guard or a die on no args cannot make the
  test pass vacuously.
- `acquire_gate_lock "$t8_key"`, then **prove the section is really held before dying**:
  `[[ -n "$_AIT_LEDGER_LOCK_DIR" && -d "$_AIT_LEDGER_LOCK_DIR" ]] || exit 96`, then
  `printf 'T8_LOCK_HELD:%s\n' "$_AIT_LEDGER_LOCK_DIR" >&2`.
- Install the trap by `t8_mode`. `chained` uses
  `trap 'gate_cleanup; ait_ledger_lock_exit_trap' EXIT` with `gate_cleanup() { :; }` (the
  misuse the task names). `bare` uses `trap 'ait_ledger_lock_exit_trap' EXIT`. Any other
  value runs `exit 95`. Then print `T8_TRAP:$(trap -p EXIT)` to stderr, so the installed
  handler is visible evidence and not an assumption.
- `die "t8 section died"`.

Run it as `( cd "$TMP" && TASK_DIR=aitasks bash "$TMP/t8_chain.sh" "$ID9" chained )` under
the suite's exported `AITASKS_LOCK_DIR`. Add `ID9` (and `ID10` for 8c) to `IDS` so their
lock dirs are cleaned up. The test asserts:
- **the section was reached**: stderr contains `T8_LOCK_HELD:$(lock_dir_for_id "$ID9")`
  (the exact gate-namespace path), `T8_TRAP:` naming the chained handler, and
  `t8 section died` (the death came from the section and not from the preamble). The
  exit status is not 95/96/97.
- exit status `1`, not `0` (the death is not reported as success)
- stderr contains `ran behind another command in the EXIT trap` (the guard *fired*; a
  non-zero exit alone would also come from the die)
- `assert_dir_not_exists` on `lock_dir_for_id "$ID9"` (the seam still released a lock
  that the preceding assertion proved was held)

**8c. Negative control**: the same driver with `"$ID10" bare`. It asserts the same
"section was reached" evidence (`T8_LOCK_HELD:` with the `$ID10` path, `T8_TRAP:` naming the
bare handler, `t8 section died`), exit `1` (the die's status), **no** "ran behind" warning,
and the lock released. This shows that 8b's warning comes from the chaining and not from
the gate path, and the reached-section evidence keeps the control from passing vacuously.

### 3. Lint

`shellcheck -S warning .aitask-scripts/aitask_gate.sh`.

## Verification

- `bash tests/test_gate_lock_characterization.sh`: all green including the new Test 8.
  Test 5 (trap releases the lock on die, die status 1 preserved) is the load-bearing
  check for the three converted sites.
- `bash tests/test_gate_ledger.sh`: green.
- `bash tests/test_ledger_lock_exit_trap.sh`: green (the seam is unchanged).
- `bash tests/test_note_append.sh`: green (the seam's other consumer).
- `bash tests/test_gate_lock_single_winner.sh`: green (production concurrency on the gate lock).
- `shellcheck -S warning .aitask-scripts/aitask_gate.sh`.
- Red proof for 8a: temporarily point one site back at a fake private trap in a scratch
  copy, never in the repo file, and confirm 8a fails. 8b discriminates by construction:
  it asserts that the guard's warning text appears.
- Red proof for the reached-section evidence: run the 8c (bare) driver variant once with
  the old `set --`-before-save ordering in a scratch copy. Confirm it now fails on the
  missing `T8_LOCK_HELD:` / die message, rather than passing as it would have before.

## Step 9 (Post-Implementation)

Current-branch mode: commit code (`refactor: … (t1692)`), then archive per task-workflow Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
