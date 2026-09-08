---
Task: t1741_fix_ledger_block_awk_body_truncates_task_file.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1741 — Fix the ledger-block append seam truncating task files

## Context

`ait_ledger_append_section` (`.aitask-scripts/lib/ledger_block.sh`) is the shared
marker-block append seam behind both `## Inbox` (`ait note`) and `## Gate Runs`
(`ait gate append`). It has **two independent defects**, and together they
destroyed a live 11 KB task file (`t1705_5`) while reporting `NOTE_APPENDED:`.

**Defect 1 — the unconditional swap.** All three write paths do
`producer … > "$tmp"; mv "$tmp" "$file"` with no status check, and the two awk
paths then `return 0` unconditionally, masking even `mv`'s own failure. Any
producer failure is published over the target. Verified, three distinct shapes:

| producer failure | today's outcome |
|---|---|
| awk exits non-zero, empty `$tmp` (BSD awk on a multiline `-v`) | target truncated to 0 bytes, `return 0` |
| `cat "$file"` fails inside the EOF brace group | group status is the **last** command's, so it is `0`; `$tmp` holds only the appended block → **the whole task file's original content is replaced by a lone marker**, `return 0` |
| `mv` itself fails | awk paths `return 0` regardless; `$tmp` is left behind in `aitasks/` on every path |

**Defect 2 — caller data reaches awk through `-v`.** `awk -v` runs escape
processing on the assigned value and rejects a literal newline:

- **BSD awk (macOS)** — a multiline body makes awk exit 2 with **empty** output.
  Combined with Defect 1 the task file is truncated to 0 bytes and committed.
  This is the reported incident.
- **GNU awk (this box, verified)** — multiline is accepted, but backslashes are
  silently rewritten: `-v body='C:\temp'` yields `C:<TAB>emp`, `\\` → `\`,
  `\n` → a newline. So the note body is corrupted **on every platform**, just
  less visibly. Verified: `ENVIRON["…"]` reproduces the value byte-for-byte.

Intended outcome: the seam either writes the block correctly or leaves the
target byte-for-byte untouched and returns non-zero; note/gate bodies round-trip
verbatim; a failed append becomes a typed error at each caller's CLI boundary.

**Out of scope (verified, no change needed):** the Python twin
`lib/ledger_block.py` is already correct — `atomic_write()` only calls
`os.replace` after a successful write, and a failure propagates as an exception.

## Changes

### 1. `.aitask-scripts/lib/ledger_block.sh` — one guarded swap helper

Add, above `ait_ledger_append_section`, the only sanctioned tempfile→target swap
in the file:

```bash
# _ait_ledger_swap_tmp <producer_status> <tmp> <file>
#
# Fails closed: on any producer failure the target is left byte-for-byte
# untouched, the tempfile is removed, and the status is non-zero. The three
# write paths below used to `mv` unconditionally — BSD awk rejects a newline in
# a `-v` assignment, exits 2 with EMPTY output, and that emptiness was published
# over an 11KB task file while the function still returned 0 (t1741).
_ait_ledger_swap_tmp() {
    local st="$1" tmp="$2" file="$3" why=""

    # Test-only fault injection through a documented seam. The three callers are
    # separate PROCESSES, so their failure contracts cannot be driven by
    # shadowing a command in the test shell; this is how tests reach them.
    # Placed here so the real guard below still runs — the forced failure
    # exercises tempfile cleanup and the untouched target, not just the return.
    # Never set in normal operation. Mirrors AIT_NOTE_FAIL_AFTER_APPEND.
    [[ -z "${AIT_LEDGER_FAIL_APPEND:-}" ]] || st=99

    if [[ "$st" -ne 0 ]]; then
        why="block producer exited $st"
    elif [[ ! -s "$tmp" ]]; then
        # Unreachable on success: every path reprints the whole input plus at
        # least a marker line, so an empty result IS a producer that failed
        # without saying so (the BSD-awk shape).
        why="block producer wrote an empty file"
    fi
    if [[ -n "$why" ]]; then
        rm -f "$tmp"
        warn "ait_ledger_append_section: $why — '$file' left unchanged"
        return 1
    fi
    if ! mv "$tmp" "$file"; then
        rm -f "$tmp"
        warn "ait_ledger_append_section: could not replace '$file' — left unchanged"
        return 1
    fi
    return 0
}
```

Every write path then ends in the same shape — **absorbing capture** (`local
st=0` declared first, so errexit in a sourced caller cannot abort past the
guard), then the helper:

```bash
        local st=0
        <producer> > "$tmp" || st=$?
        _ait_ledger_swap_tmp "$st" "$tmp" "$file" || return 1
        return 0
```

Update the function's header comment to state the new return contract: `0` on a
completed append, non-zero with the target untouched otherwise.

### 2. Same file — no caller data through `awk -v`

Both awk invocations lose `-v` entirely and read every caller-supplied value
from the environment, scoped to the command with a `VAR=val awk …` prefix.
`ENVIRON` is POSIX (gawk, BSD one-true-awk, mawk, busybox awk), performs no
escape processing, and carries newlines. Uniform rule, so it cannot drift back:
**nothing from the caller reaches awk via `-v`** — marker, body, header, comment
and the two derived regexes all move to `ENVIRON`.

```bash
        local st=0
        AIT_LB_ANCHOR="$anchor_re" AIT_LB_HDR="$header" AIT_LB_CMT="$comment" \
        AIT_LB_MK="$marker" AIT_LB_BODY="$body" \
        awk '
            BEGIN {
                anchor = ENVIRON["AIT_LB_ANCHOR"]; hdr = ENVIRON["AIT_LB_HDR"]
                cmt    = ENVIRON["AIT_LB_CMT"];    mk  = ENVIRON["AIT_LB_MK"]
                body   = ENVIRON["AIT_LB_BODY"]
            }
            $0 ~ anchor && !done {
                print hdr; print cmt; print "";
                print mk;
                if (body != "") { print ">"; print body }
                print "";
                done = 1
            }
            { print }
        ' "$file" > "$tmp" || st=$?
        _ait_ledger_swap_tmp "$st" "$tmp" "$file" || return 1
        return 0
```

and the `section_end` branch equivalently (`AIT_LB_HDRRE`, `AIT_LB_MK`,
`AIT_LB_BODY`). The awk program bodies are otherwise unchanged, so the emitted
bytes are identical for every input the old code handled correctly.

### 3. Same file — the EOF branch needs **per-producer** guards, not a group status

The current brace group returns only its **last** command's status, so a failing
`cat "$file"` is masked by the `echo`s that follow it and `$tmp` — non-empty,
because it holds the appended block — passes the `-s` check. The obvious repair
is a subshell with `set -e`, and it **does not work**: bash suppresses errexit
for a compound command on the left of `||`, and an explicit `set -e` inside the
subshell does not restore it. Measured:

```
( set -e; cat missing; echo MARKER ) > out || st=$?   # st=0, out contains "MARKER"
( cat missing || exit 90; echo MARKER ) > out || st=$? # st=90, out empty  ← correct
```

So guard each producer explicitly. Collapse the six `echo`s into one pre-built
suffix string so there are exactly two guarded commands, and keep the emitted
bytes identical to today's:

The branch also carries one unguarded **read** of the source, and it must fail
closed for the same reason. `if [[ -n "$(tail -c1 "$file")" ]]` cannot tell "the
last byte is a newline" from "tail failed": both give an empty capture. Measured
with a stubbed failing `tail`, the code silently decides the file already ends
with a newline and renames that guess over the target. The cost is narrower than
losing content — the appended block still starts on its own line because the
suffix opens with `\n`, so only the blank line before the section header is lost
— but a swallowed read failure ahead of a swap is precisely what this change
exists to remove. Capture it **declare-first**: `local last=$(…)` returns
`local`'s status, not the command's (measured: the inline form reports 0 for a
`tail` that exited 3), so the failure must be absorbed on a separate line. No
tempfile exists yet at this point, so the guard just warns and returns.

```bash
    # Build the appended tail first, so the producer below is two guarded
    # commands rather than six unguarded ones. Byte-for-byte the same output.
    local suffix="" last_byte="" st_tail=0
    # Ensure a trailing newline before appending. A tail that FAILS is
    # indistinguishable from a file already ending in one, so treat it as a
    # producer failure rather than guessing over the target.
    last_byte="$(tail -c1 "$file" 2>/dev/null)" || st_tail=$?
    if [[ "$st_tail" -ne 0 ]]; then
        warn "ait_ledger_append_section: could not read the final byte of '$file' — left unchanged"
        return 1
    fi
    if [[ -n "$last_byte" ]]; then suffix=$'\n'; fi
    if [[ $have_section -eq 0 ]]; then
        suffix="${suffix}"$'\n'"${header}"$'\n'"${comment}"$'\n'
    fi
    suffix="${suffix}"$'\n'"${marker}"$'\n'
    if [[ -n "$body" ]]; then
        suffix="${suffix}>"$'\n'"${body}"$'\n'
    fi

    local st=0
    (
        # No `set -e` here — see above; it is suppressed on the left of `||`.
        cat "$file"          || exit 90
        printf '%s' "$suffix" || exit 91
    ) > "$tmp" || st=$?
    _ait_ledger_swap_tmp "$st" "$tmp" "$file" || return 1
    return 0
```

Verified that this also catches a write failure on a full filesystem: both
`cat … > /dev/full` and `printf … > /dev/full` return non-zero and are caught.

### 4. `.aitask-scripts/aitask_note.sh` — two typed failure translations

`_note_append_inner` (~L484) — nothing landed and the target is untouched, so
this is the id-less pre-append half of the contract, exactly like the
neighbouring collision exhaustion; mirror its release-then-retrap spelling:

```bash
    if ! ait_ledger_append_section "$file" "$NOTE_SECTION_HEADER" \
            "$NOTE_SECTION_COMMENT" "$marker" "$body" \
            "$NOTE_ANCHOR_HEADER" "section_end"; then
        ait_ledger_lock_release || true
        trap note_cleanup_body EXIT
        note_die "append-write-failed"
    fi
```

`_note_read_inner` (~L660) — no receipt was written, so the note stays unread,
which is the documented fail-safe direction. Match that function's direct
spelling:

```bash
    ait_ledger_append_section … "section_end" || note_read_die "append-write-failed"
```

Both reasons pass through `note_sanitize_field`, and both wrappers surface the
inner subshell's first stdout line, so the one-line/disjoint-class contract holds
(`NOTE_ERROR:append-write-failed` / `READ_ERROR:append-write-failed`).

### 5. `.aitask-scripts/aitask_gate.sh` — mirror the existing python spelling

`_gate_append_locked` (~L381) must not echo the block as if it had been written.
The python branch six lines above already uses `|| die "python gate_ledger
append failed"`; use the same shape so the two backends fail identically and no
call site (`cmd_append` L300, `cmd_begin_procedure` L1239) needs to change — the
`EXIT` trap releases the gate lock either way:

```bash
    ait_ledger_append_section "$file" "## Gate Runs" "…" "$marker" "$body" "" "eof" \
        || die "gate ledger append failed for $gate (task file left unchanged)"
```

### 6. New `tests/test_ledger_block_append_integrity.sh`

Two halves in one file, because "the fail-closed contract of the append seam and
its three callers" is one unit. Groups A–C source the real
`terminal_compat.sh` + `stale_lock.sh` + `ledger_block.sh` and call the seam
in-process (it takes no lock), following `tests/test_ledger_lock_exit_trap.sh`.
Group D builds the small fixture repo from `tests/test_note_section_order.sh`
and drives the real CLIs. Every assertion stays in the main shell, so the
file-backed counters are not needed.

**Group A — byte fidelity, both awk branches.** Append a body that is genuinely
multiline **and** contains `C:\temp`, `\\` and a literal `\n`, once through the
`create_before` anchor-insert path (target has `## Gate Runs`, no `## Inbox`) and
once through the `section_end` path (target already has `## Inbox`). Assert the
pre-existing content survives byte-for-byte and every body line reappears
verbatim. **Discriminating here:** pre-fix, GNU awk rewrites `C:\temp` to
`C:<TAB>emp` and both cases fail; on macOS the same cases fail by truncation.

**Group B — producer failure, all three branches.** Force the producer to fail in
the exact BSD-awk shape (non-zero exit, empty tempfile) by shadowing it with a
shell function inside a subshell — verified to work — so the guard is driven, not
asserted:

```bash
rc=0; ( awk() { return 2; }; ait_ledger_append_section … ) 2>/dev/null || rc=$?
```

`cat() { return 2; }` for the EOF branch. Assert per branch: `rc` non-zero, the
target `cmp`-identical to a saved copy of its pre-call bytes (not merely
non-empty), and no `.aitask_ledger.*.tmp` left in the directory. **Discriminating:**
pre-fix the awk branches truncate to 0 bytes and return 0, and the EOF branch
replaces the file's whole content with a lone marker block and returns 0.

A fourth case in this group covers the EOF branch's **source read**:
`tail() { return 3; }` against a target whose last byte is **not** a newline.
Same three assertions. **Discriminating:** pre-fix the swallowed failure is
written over the target (the block lands without its preceding blank line) and
the function returns 0.

**Group C — rename failure, all three branches.** Separately from B, stub
`mv() { return 1; }` so the producer succeeds and only the swap fails. Same three
assertions. **Discriminating:** pre-fix the awk branches return 0 despite the
failed rename, and all three leave `$tmp` behind in the task directory.

**Group D — positive control + the three CLI failure contracts.** Positive
control first, so B and C cannot pass by the guard rejecting everything: an
ordinary single-line body appends through each branch and returns 0 — and for the
EOF branch, against **both** a target ending in a newline and one that does not,
pinning the emitted blank-line structure the new final-byte guard sits on. Then, in the
fixture repo, with the documented seam exported:

| command | asserted |
|---|---|
| `AIT_LEDGER_FAIL_APPEND=1 ait note <t> --from <t> --text …` | stdout is exactly one line, `NOTE_ERROR:append-write-failed`; non-zero exit; task file `cmp`-identical to before; no new commit |
| `AIT_LEDGER_FAIL_APPEND=1 ait note read <t> --by t<t> --ids <id>` | stdout is exactly `READ_ERROR:append-write-failed`; the note is still **unread** on a follow-up `inbox` query |
| `AIT_LEDGER_FAIL_APPEND=1 ait gate append <t> <gate> pass` | non-zero exit; stdout contains **no** `> **` marker line; task file `cmp`-identical to before |

Sequencing: write the tests, run them against the unfixed library and record the
red, then apply changes 1–5 and land tests + fix in **one** commit — the red
window must never reach a commit.

## Verification

1. `bash tests/test_ledger_block_append_integrity.sh` — red before the fix on the
   named cases, green after. Record which cases were red.
2. Regression, all green: `bash tests/test_note_append.sh`,
   `tests/test_note_read_receipts.sh`, `tests/test_note_section_order.sh`,
   `tests/test_note_with_live_composition.sh`,
   `tests/test_ledger_lock_exit_trap.sh`, `tests/test_gate_ledger.sh`.
3. Python side unchanged and still green:
   `bash tests/run_all_python_tests.sh tests/test_ledger_block_multisection.py`
   and the `test_gate_ledger*.py` modules (read the **last** line for the
   verdict; do not pipe without `pipefail`).
4. `shellcheck .aitask-scripts/lib/ledger_block.sh .aitask-scripts/aitask_note.sh
   .aitask-scripts/aitask_gate.sh`.
5. Live end-to-end (inline post-phase mitigation below), in a throwaway fixture
   repo — never a real task.
6. Confirm `AIT_LEDGER_FAIL_APPEND` appears nowhere outside the library's seam
   and the tests (`grep -rn AIT_LEDGER_FAIL_APPEND`).
7. Step 9 (Post-Implementation) handles cleanup, archival and merge.

## Risk

### Code-health risk: medium
- `ait_ledger_append_section` is the shared append seam for **both** the note
  mailbox and the gate ledger, and the gate ledger writes to every gated task
  file — a regression here corrupts task data rather than failing loudly.
  · severity: medium · → mitigation: inline post-phase live_note_roundtrip
- The EOF branch is restructured (six `echo`s → one pre-built suffix, plus a
  guarded final-byte read), so its output must stay byte-identical rather than
  merely equivalent, on both the trailing-newline and no-trailing-newline
  inputs. · severity: medium · → mitigation: none (Group D's positive control
  covers both input shapes, alongside the existing
  `test_note_section_order.sh` / `test_gate_ledger.sh` suites compare emitted
  structure on all three branches)
- The function gains a non-zero return, which under a sourced caller's `errexit`
  changes control flow at three call sites. · severity: low · → mitigation: none
  (covered by verification step 2 — the existing note/gate suites drive all three)
- A new test-only env seam (`AIT_LEDGER_FAIL_APPEND`) becomes a way to make the
  seam fail in production if ever set. · severity: low · → mitigation: none
  (verification step 6 pins that it is referenced only by the library and tests)

### Goal-achievement risk: medium
- The headline defect (BSD awk rejecting a newline in `-v`) **cannot be executed
  on this Linux box** — GNU awk accepts it. The fix's macOS behaviour is argued
  from POSIX `ENVIRON` support, not measured here. · severity: medium ·
  → mitigation: t1743
- Mitigated in part by design: the GNU-awk backslash corruption, the producer-
  failure control and the rename-failure control are all discriminating on this
  box, so nothing ships on an unexecuted claim. · severity: low · → mitigation: none

**Reassessment after the confirmed inline post-phase:** the augmented plan adds
one bounded end-to-end test to an existing fixture; both levels stay as assessed
above (code-health medium, goal-achievement medium).

### Planned mitigations
- timing: post-phase | name: live_note_roundtrip | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: shared-seam blast radius (code-health) | desc: drive the real `./ait note --file -` CLI in a throwaway fixture with a multiline + backslash body and assert prior bytes intact and body verbatim
- timing: after | name: verify_on_macos | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: high | addresses: unexecutable BSD-awk path (goal-achievement) | desc: run tests/test_ledger_block_append_integrity.sh and the note suite on macOS/BSD awk to confirm the multiline body now round-trips instead of truncating | created: t1743

### Post-phase (risk mitigations)

**live_note_roundtrip** — after changes 1–6 are green, add the end-to-end case to
`tests/test_note_append.sh` (which already owns the real-CLI fixture repo and a
multiline `--text` case at L137): a `--file -` heredoc body containing `C:\temp`,
`\\` and two lines, asserting `NOTE_APPENDED:`, that the task file's pre-note
content is `cmp`-identical, and that each body line appears verbatim as `> | …`.

## Post-Review Changes

### Change Request 1 (2026-09-08 13:35)
- **Requested by user:** The D2 CLI failure test compared only the task-file
  bytes after a failed `ait note` append. The plan's own D2a row also promised
  "no new commit", but the fixture never established a data-repository HEAD, so
  a future regression that committed despite returning
  `NOTE_ERROR:append-write-failed` would still pass.
- **Verified:** valid. The fixture ran `git init` and never committed, so there
  was no HEAD to compare. Probed the real behaviour first: a **successful**
  `ait note` does advance HEAD in this fixture (so the assertion is
  non-vacuous), while `ait gate append` does **not** commit at all
  (`aitask_gate_record.sh` owns persistence) — so a HEAD assertion on D2c would
  be vacuous rather than merely redundant, and is deliberately omitted with a
  comment saying so.
- **Changes made:** `make_cli_task` now commits its task file, giving each case
  a baseline HEAD. D2a asserts `nothing was committed` and D2b asserts
  `no receipt was committed`, both against that baseline. D2d gained the
  matching **positive control** — a successful note MUST advance HEAD — so the
  two "unchanged" assertions cannot pass in a fixture where nothing ever
  commits.
- **Discrimination re-verified** against the pre-fix tree (`git archive HEAD`
  copy): both new assertions are RED pre-fix (the truncating append was in fact
  committed — the incident itself), green post-fix. Suite went 66 -> 69 cases.
- **Files affected:** `tests/test_ledger_block_append_integrity.sh`

## Final Implementation Notes

- **Actual work done:** Implemented all six planned changes. `ledger_block.sh`
  gained `_ait_ledger_swap_tmp` (the single guarded tempfile->target swap, with
  the documented `AIT_LEDGER_FAIL_APPEND` fault seam); both awk branches dropped
  `-v` entirely for `ENVIRON`; the EOF branch gained a guarded final-byte read
  and a subshell with per-producer `|| exit` guards. The three callers translate
  a failed append into a typed error (`NOTE_ERROR:append-write-failed`,
  `READ_ERROR:append-write-failed`, and `die` for the gate ledger). New
  `tests/test_ledger_block_append_integrity.sh` (69 cases) plus the inline
  post-phase end-to-end case in `tests/test_note_append.sh`.

- **Deviations from plan:** None in substance. Two test-level corrections during
  execution:
  1. The `## Risk` code-health "byte-identical output" bullet was pinned with an
     `awk`-based TAB count rather than `grep -cP`; `grep -P` is a GNU extension
     this repo cannot rely on, and this file must run on the very macOS box that
     has the truncating awk.
  2. The inline post-phase case initially sent ONE note and was green pre-fix.
     A first note on a fresh task finds neither `## Inbox` nor the `## Gate Runs`
     anchor, so it is created at EOF by the plain-shell path and never reaches
     awk. It now sends two notes; the second takes the `section_end` awk branch
     and is red pre-fix. Recorded in the test's own comment so it cannot be
     "simplified" back.

- **Issues encountered:**
  - The planned `( set -e; … ) > "$tmp" || st=$?` repair for the EOF branch does
    **not** work: bash suppresses errexit for a compound command on the left of
    `||`, and an explicit `set -e` inside the subshell does not restore it
    (measured — `st` stayed 0 with the content lost). Explicit `|| exit N` per
    producer is required, and a comment in the source says so.
  - `local x="$(cmd)"` returns `local`'s status, not the command's, so the
    final-byte read is captured declare-first.
  - The `tests/run_all_python_tests.sh` invocation with a positional module path
    produced no output for ~15 minutes and was stopped; the ledger/gate Python
    modules were run directly with pytest instead (7 modules, all green). The
    Python half is untouched by this change.

- **Key decisions:**
  - **`ENVIRON` for every caller-supplied value, not just the body.** A uniform
    rule ("nothing from the caller reaches awk via `-v`") cannot drift back the
    way a body-only exception would.
  - **The gate caller `die`s rather than returning.** It mirrors the `|| die`
    already used six lines above for the python backend, so the two backends
    fail identically and no call site (`cmd_append`, `cmd_begin_procedure`)
    needed changing — the EXIT trap releases the gate lock either way.
  - **Discrimination was proved against an isolated `git archive HEAD` copy**,
    never by reverting files in this shared, concurrently-dirty worktree.
    31 red pre-fix -> 69 green post-fix on the new file; 3 red pre-fix on the
    end-to-end case.

- **Upstream defects identified:** None. (The `mv`-masking, the brace-group
  status and the swallowed `tail` failure are all defects of the function this
  task owns, not of a separate script — they are fixed here, not deferred.)

- **Verification performed:**
  - `tests/test_ledger_block_append_integrity.sh` — 69/69.
  - `tests/test_note_append.sh` 121/121, `test_note_read_receipts.sh` 74/74,
    `test_note_section_order.sh` 20/20, `test_note_with_live_composition.sh`
    117/117, `test_ledger_lock_exit_trap.sh` 77/77, `test_gate_ledger.sh` 37/37.
  - 7 ledger/gate Python modules green under pytest.
  - `shellcheck` on the three changed scripts: findings **identical** to HEAD
    (13 pre-existing SC1091), no new codes.
  - `AIT_LEDGER_FAIL_APPEND` referenced only by the library seam and the test.
