---
Task: t1743_verify_on_macos.md
Worktree: current branch
Branch: main
Base branch: main
---

# Plan - t1743: Verify t1741's ledger/note fix on macOS (BSD awk)

Autonomous auto-verification of the `## Verification Checklist`. The plan is a
retroactive record of what was actually run.

## Environment

- macOS 15.7.3 (build 24G419)
- `/usr/bin/awk` → `awk version 20200816` (BSD one-true-awk) — the affected
  implementation named in the task.

## Execution Log

### Item 1 — `bash tests/test_ledger_block_append_integrity.sh`

- Item text: `bash tests/test_ledger_block_append_integrity.sh` — expect 69 passed, 0 failed.
- Approach: CLI invocation.
- Action run: `bash tests/test_ledger_block_append_integrity.sh > /tmp/t1743_ledger.log 2>&1; echo "EXIT=$?"`
  (exit status captured directly, not through a pipe — piping to `tail` would
  discard it, per CLAUDE.md).
- Output (trimmed):
  ```
  EXIT=0
  === ait_ledger_append_section: fail-closed write contract (t1741) ===
  Results: 69 passed, 0 failed (of 69)
  ```
- Verdict: **pass** — matches the expected 69/0 exactly.

### Item 2 — `bash tests/test_note_append.sh`

- Item text: `bash tests/test_note_append.sh` — expect 121 passed, 0 failed. Cases `2k1`-`2k4` pin the body's byte fidelity.
- Approach: CLI invocation + file inspection (to confirm the named cases exist
  in the run, rather than inferring them from the aggregate count).
- Action run: `bash tests/test_note_append.sh > /tmp/t1743_note.log 2>&1; echo "EXIT=$?"`,
  then `grep -n "2k1\|2k2\|2k3\|2k4" tests/test_note_append.sh`.
- Output (trimmed):
  ```
  EXIT=0
  === ait note: durable lane (t1657_2) ===
  Results: 121 passed, 0 failed (of 121)
  ```
  Cases located at `tests/test_note_append.sh:195,197,199,204` —
  `2k1`/`2k2`/`2k3` assert each heredoc line round-trips verbatim under
  `grep -cFx`, and `2k4` asserts no body line contains a TAB (what `C:\temp`
  decays into when passed through `awk -v`).
- Verdict: **pass** — 121/0, and the four byte-fidelity cases are in the file
  and therefore in the pass count.

### Item 3 — real multiline note in a throwaway fixture

- Item text: Send a real multiline note in a throwaway fixture (never a live
  task) via `./ait note <id> --from <id> --file -` with a heredoc body of
  several lines including a backslash; confirm `NOTE_APPENDED:`, prior content
  intact, each line verbatim as `> | ...`.
- Approach: CLI invocation against fabricated test data.
- Fixture: `${TMPDIR}/auto_verify_1743_3/` — a bare remote plus a cloned
  task-data repo with tasks `t900_x.md` / `t901_x.md`, the real `ait`
  dispatcher and `.aitask-scripts/` copied in, a separate code repo for
  provenance reached via `AIT_DIR`, and a private `AITASKS_LOCK_DIR`. No live
  task or repo file was touched.
- Action run (note 1, creates the `## Inbox`):
  ```
  AIT_DIR="$CODE" ./ait note 900 --from 901 --file - <<'EOF'
  first line, windows path C:\temp\new
  second line with a literal \\ pair
  third<TAB>line has a real TAB
  fourth line ending in a backslash \
  EOF
  ```
- Action run (note 2, exercises the **append-into-existing-Inbox** path — the
  one that truncated pre-fix; note 1 alone would not have reached it):
  ```
  AIT_DIR="$CODE" ./ait note 900 --from 901 --file - <<'EOF'
  SECOND note line A, path C:\users\new
  SECOND note line B ending backslash \
  EOF
  ```
- Output (trimmed):
  ```
  NOTE_APPENDED:2026-09-08T14:05:51Z.41af012daad0593ab1709683|aitasks/t900_x.md
  NOTE_APPENDED:2026-09-08T14:06:16Z.1ab4e6a225b9bb1bd79974f7|aitasks/t900_x.md
  ```
  After both appends, under `grep -cFx` (backslashes as data, whole-line match):
  all 6 body lines present verbatim, including `C:\temp\new` undecayed and the
  trailing-backslash line; the deliberate TAB survived as a real TAB; both note
  markers present; frontmatter, `Body for t900.`, `## Existing section` and both
  `pre-existing line` lines intact; file grew 19 → 24 lines, never shrank.
- Verdict: **pass**.

### Item 4 — the defect's precondition is live on this box

- Item text: Confirm the defect's precondition still exists on this box (BSD awk
  rejects a newline in `-v`), so a green suite is not green for an unrelated reason.
- Approach: CLI invocation.
- Action run:
  ```
  printf 'x\n' > v.txt
  body=$'a\nb'
  awk -v body="$body" '{print} END{print body}' v.txt; echo "rc=$?"
  ```
- Output:
  ```
  awk: newline in string a
  b... at source line 1
  rc=2
  ```
- Verdict: **pass** — the box does have the affected awk, so items 1–3 are green
  for the right reason. The verification is conclusive, not vacuous.

## Outcome

All 4 items pass. t1741's `ENVIRON`-based rewrite of
`.aitask-scripts/lib/ledger_block.sh` and its guarded tempfile swap behave on
BSD awk as the standard-based argument predicted: a multiline body with
backslashes round-trips byte-for-byte, and the target file is never truncated.
The risk t1743 was spawned to close — "macOS behaviour argued from POSIX
`ENVIRON`, not measured" — is now measured.

## Cleanup

- `${TMPDIR}/auto_verify_1743_3/` (fixture repos, dispatcher copy, lock base) — removed
- `${TMPDIR}/auto_verify_1743_4/` (awk precondition scratch) — removed
- `/tmp/t1743_ledger.log`, `/tmp/t1743_note.log` (suite logs) — removed
- No tmux sessions were created.
