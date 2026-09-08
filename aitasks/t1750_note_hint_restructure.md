---
priority: low
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-08 22:19
updated_at: 2026-09-08 22:19
---

## Origin

Risk-mitigation ("after") follow-up for t1728, created at Step 8d after implementation landed.

## Risk addressed

addresses: code-health "allowlist leaves aitask_note.sh unguarded for the new pattern"

From t1728's plan `## Risk` section, verbatim:

> - The `AIT_GIT_ALLOWLIST` entry leaves `aitask_note.sh` unguarded for the new
>   pattern — a documented hole that only closes if its two multi-line hint
>   strings are restructured · severity: low · → mitigation: note_hint_restructure

## Goal

t1728 extended `tests/test_no_unscoped_task_commit.sh` with a second pattern for
the `./ait git commit` seam. That pattern matches against the **quote-stripped**
logical line, so recovery-hint prose inside message strings is correctly ignored
— for three of the five prose occurrences in the tree.

The two exceptions are in `aitask_note.sh` (around lines 709 and 1082 — re-derive,
they drift). Both are *continuation physical lines* of multi-line `warn` strings:

```
    warn "note recorded but not committed. Recover with:
  ./ait git add -- $file && ./ait git commit -m \"ait: Record note $NOTE_ID for t${target_bare}\" -- $file"
```

Only `\`-continuations are reassembled by the scanner, so the second physical
line carries unbalanced quoting and the **fail-closed** rule reports it. Relaxing
fail-closed is not an option — `tests/.../aitask_unbalanced_quote.sh` exists
precisely to prove a real unscoped command can hide behind a multi-line message.

So t1728 suppressed them with a second, seam-specific `AIT_GIT_ALLOWLIST`
holding `.aitask-scripts/aitask_note.sh`. That entry is narrow (the file stays
fully guarded for `task_git commit`, which is how it actually commits task data)
but it is still a hole: a genuinely unscoped `./ait git commit` added to
`aitask_note.sh` later would not be caught.

**This task closes it.** Restructure those two `warn` strings so each hint's
`./ait git commit` text sits on a single logical line with balanced quoting —
e.g. build the message in a variable across `printf`/`\`-continued lines, or move
the command onto the first physical line of the string. Then:

1. delete the `.aitask-scripts/aitask_note.sh` entry from `AIT_GIT_ALLOWLIST`;
2. update the detection-scope paragraph in the test header, which currently
   states the hole and why it exists;
3. update the corresponding sentence in `aidocs/framework/shell_conventions.md`,
   which says the guard "carries a second, seam-specific allowlist holding one
   file whose hints span multiple physical lines".

Both hints are **user-facing recovery instructions that people copy-paste**, and
both are already correctly path-scoped (`-- $file`). Preserve their text
semantics exactly — this is a re-layout, not a rewording.

## Verification

- `bash tests/test_no_unscoped_task_commit.sh` passes with the allowlist entry
  removed (the real-tree scan must stay clean).
- Re-add a deliberately unscoped `./ait git commit` to `aitask_note.sh`
  temporarily and confirm the guard now flags it — the whole point of removing
  the entry. Remove the probe afterwards.
- `bash tests/test_note_append.sh`, `bash tests/test_note_read_receipts.sh`,
  `bash tests/test_note_section_order.sh`,
  `bash tests/test_note_with_live_composition.sh` all still pass — several of
  them assert on `warn` output.
- Confirm the two hints still render as valid, copy-pasteable commands in the
  actual terminal output, not just in source.
