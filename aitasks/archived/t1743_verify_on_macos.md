---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Done
labels: [python, testing]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: risk_mitigation
created_at: 2026-09-08 16:49
updated_at: 2026-09-08 17:07
completed_at: 2026-09-08 17:07
---

## Origin

Risk-mitigation ("after") follow-up for t1741, created at Step 8d after implementation landed.

## Risk addressed

The headline defect (BSD awk rejecting a newline in `-v`) **cannot be executed
on this Linux box** — GNU awk accepts it. The fix's macOS behaviour is argued
from POSIX `ENVIRON` support, not measured here. · severity: medium

## Goal

Run t1741's regression coverage on a macOS box (BSD `awk version 20200816` or
similar) and confirm the multiline body now round-trips instead of truncating.

Checklist:

- [ ] `bash tests/test_ledger_block_append_integrity.sh` — expect 69 passed, 0 failed.
- [ ] `bash tests/test_note_append.sh` — expect 121 passed, 0 failed.
      Cases `2k1`–`2k4` are the ones that pin the body's byte fidelity.
- [ ] Send a real multiline note in a throwaway fixture (never a live task):
      `./ait note <id> --from <id> --file -` with a heredoc body of several
      lines including a backslash. Confirm `NOTE_APPENDED:`, that the target's
      prior content is intact, and that each line landed verbatim as `> | …`.
- [ ] Confirm the defect's precondition still exists on that box, so a green
      suite is not green for an unrelated reason:

          printf 'x\n' > /tmp/v.txt
          body=$'a\nb'
          awk -v body="$body" '{print} END{print body}' /tmp/v.txt; echo "rc=$?"

      Expect `awk: newline in string …` and a non-zero rc. If this SUCCEEDS,
      the box does not have the affected awk and the verification is
      inconclusive — record that rather than passing the task.

## Context

t1741 replaced every `awk -v` assignment in
`.aitask-scripts/lib/ledger_block.sh` with `ENVIRON` reads, and routed all
three write paths through a guarded tempfile swap that leaves the target
byte-for-byte untouched on any producer failure. `ENVIRON` is POSIX and is
supported by BSD one-true-awk, but that was reasoned from the standard, not
executed — this task closes that gap.

## Verification Checklist

- [x] `bash tests/test_ledger_block_append_integrity.sh` — expect 69 passed, 0 failed. — PASS 2026-09-08 17:06 auto: 69 passed, 0 failed (of 69), exit 0 on macOS 15.7.3 / BSD awk 20200816
- [x] `bash tests/test_note_append.sh` — expect 121 passed, 0 failed. Cases `2k1`-`2k4` pin the body's byte fidelity. — PASS 2026-09-08 17:06 auto: 121 passed, 0 failed (of 121), exit 0; cases 2k1-2k4 present in the file and included in the pass count
- [x] Send a real multiline note in a throwaway fixture (never a live task) via `./ait note <id> --from <id> --file -` with a heredoc body of several lines including a backslash; confirm `NOTE_APPENDED:`, prior content intact, each line verbatim as `> | ...`. — PASS 2026-09-08 17:06 auto: two multiline notes sent via ./ait note in a throwaway fixture repo (t900/t901, copied dispatcher, AIT_DIR-isolated); NOTE_APPENDED both times, all 6 body lines verbatim as '> | ' including C:\temp\new, a literal \\ pair, a real TAB and a trailing backslash; prior task content and the first note intact after the second append (the awk/existing-Inbox path)
- [x] Confirm the defect's precondition still exists on this box (BSD awk rejects a newline in `-v`), so a green suite is not green for an unrelated reason. — PASS 2026-09-08 17:06 auto: awk -v body=$'a\nb' fails with 'awk: newline in string a b... at source line 1', rc=2 -- the defect's precondition is live on this box
