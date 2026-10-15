---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [trails, skills]
gates: [risk_evaluated]
anchor: 1989
followup_kind: upstream_defect
created_at: 2026-10-16 00:06
updated_at: 2026-10-16 00:06
---

## Origin

Spawned from t2011 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/archive_utils.sh:142 — _extract_from_archive records its temp dir in _AIT_ARCHIVE_TMPDIR, but resolve_task_file is always called inside $( ), so the variable is set only in the subshell and the EXIT-trap cleanup never sees it: every bundled-task resolve by ait attach/artifact (and any other $(resolve_task_file) caller) leaks one mktemp dir holding the extracted task file (measured: one dir per bundled resolve in the step-0 probe)`
- `.aitask-scripts/lib/archive_utils.sh:117 — sourcing archive_utils.sh (via task_utils.sh) runs a bare 'trap _ait_archive_cleanup EXIT', replacing any EXIT trap the caller set first; tests that trap 'rm -rf $TMP' before sourcing task_utils.sh leak their fixture dir (fixed locally in test_attach_local_backend.sh and test_artifact_cli.sh; still present in test_label_vocabulary_lib.sh, test_last_used_labels.sh, test_userconfig_writer_collision.sh, test_xdeps_parser.sh by static scan)`
- `.aitask-scripts/aitask_attach.sh:406 / aitask_artifact.sh:623 — rm on a bundled owner refuses correctly (no mutation, pinned by L6) but with the misleading 'could not read the git status of /tmp/… — refusing to start a transaction whose paths cannot be verified' instead of naming the archive bundle; a clear refusal (e.g. task_file_is_active / bundle check before the lock) is a separate change`

## Diagnostic context

From t2011's Final Implementation Notes:

- **Step-0 probe.** A scratch legacy-mode repo with t26 packed into
  `aitasks/archived/_b0/old0.tar.zst` after it got an attachment and an
  artifact while active. `ait attach ls/get` and `ait artifact ls/get` worked
  on the bundled owner. `ait attach rm 26 p.bin` and
  `ait artifact rm 26 art:t26-report` both exited 1 with
  `fatal: … is outside repository`, then
  `Error: ait … rm: could not read the git status of /tmp/…/t26_packed.md — refusing to start a transaction whose paths cannot be verified`.
  The lookup had succeeded. Neither command committed anything or changed the
  ledger. With `TMPDIR` pointed at a probe dir, six `tmp.*` extraction dirs were
  left behind, one per bundled-owner resolve.
- **Leak measurement for `tests/test_attach_local_backend.sh`.** The HEAD
  version left 2 entries in `TMPDIR`: the shared `ait-test-cwd-<uid>` and the
  fixture `$TMP`, whose `trap 'rm -rf "$TMP"' EXIT` had been replaced by
  `_ait_archive_cleanup` when `task_utils.sh` was sourced. With t2011's new
  bundled cases it left 8 `tmp.*` dirs + the cwd. t2011 fixed both edited test
  files locally: it re-arms the trap after sourcing and sets
  `export TMPDIR="$TMP/tmpdir"`. After that, only the intentional cwd is left.
- **Why the trap does not fire.** Bash resets traps inside command
  substitution, so `_AIT_ARCHIVE_TMPDIR=$(mktemp -d)` (set inside
  `_extract_from_archive`, called from `resolve_task_file`) never reaches the
  parent shell. The parent's `_ait_archive_cleanup` sees an empty variable.

## Suggested fix

Leak:
- Make the extraction temp dir known to the parent shell. One option is to
  create `_AIT_ARCHIVE_TMPDIR` eagerly, at source time or lazily in the parent
  before the `$( )`.
- Another is to give `resolve_task_file` a non-subshell variant that sets a
  result variable, mirroring `_AIT_EXTRACT_RESULT`.

Trap:
- Chain the archive cleanup onto any existing EXIT trap rather than replacing
  it (cf. `txn_chain_exit_trap` in `lib/txn_snapshot.sh`).
- Then drop the local re-arms in `test_attach_local_backend.sh` and
  `test_artifact_cli.sh`, and re-measure the four listed tests.

rm message:
- Check `task_file_is_active` (or the bundle tier) in `cmd_remove` of both
  CLIs, and refuse with a message naming the bundle.
- Keep the L6 pins (no mutation) and update their message assertion.
