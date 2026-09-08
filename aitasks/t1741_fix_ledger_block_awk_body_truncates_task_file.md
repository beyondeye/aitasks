---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [python, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-08 14:54
updated_at: 2026-09-08 16:11
---

## Origin

Spawned from t1738 during Step 8b review. Hit for real while t1738 was executing
its own plan's `note_shared_surface_to_t1705_5` post-phase step.

## Upstream defect

- `.aitask-scripts/lib/ledger_block.sh:227` — `ait_ledger_append_section` passes
  the block body through `awk -v body="$body"`. BSD awk (macOS) rejects a newline
  inside a `-v` assignment, exits 2 with EMPTY output, and the
  `mv "$tmp" "$file"` on the very next line is unconditional — so a multiline
  `ait note` body TRUNCATES THE TARGET TASK FILE TO 0 BYTES, and the function
  still `return 0`s so the caller reports success.
- `.aitask-scripts/lib/ledger_block.sh:246` — the identical `awk -v body=` +
  unconditional `mv` pair in the `section_end` branch, so the defect fires
  whether or not the target already carries an `## Inbox` section.

## What actually happened

`./ait note 1705_5 --from 1738 --with-live --file - <<EOF ... EOF` with a
~40-line body:

    awk: newline in string > | t1738 has landed... at source line 1   (x3)
    NOTE_APPENDED:2026-09-08T10:47:20Z.b35ccc951179742a3be9b984|aitasks/t1705/t1705_5_restore_and_repick_flows.md
    LIVE_NONE:unlocked

`aitasks/t1705/t1705_5_restore_and_repick_flows.md` went from 11228 bytes to 0,
and the truncation was **committed** by the note writer itself:

    ccd525c9f ait: Record note ... for t1705_5
     aitasks/t1705/t1705_5_restore_and_repick_flows.md | 212 ----------------------
     1 file changed, 212 deletions(-)

The note body was not written either — the file was simply emptied. Recovered
with `./ait git show e6d90dd90:<path> > <path>` and committed as `8d47a8e3b`;
the note was then re-sent with a single-line body and landed correctly.

## Reproduction (macOS, `awk version 20200816`)

    printf 'line A\nline B\n' > victim.txt
    body=$'> | first\n> | second'
    awk -v body="$body" '{ print } END { print body }' victim.txt > out.txt
    # awk: newline in string ... ; exit 2 ; out.txt is 0 bytes

GNU awk accepts a multiline `-v`, so this is the macOS-only portability class
covered by `aidocs/framework/sed_macos_issues.md`. It has gone unnoticed because
every note previously sent in this repo happens to carry a single-line body
(`grep -rh '^> | ' aitasks/` — each is one long line).

## Blast radius

`ait_ledger_append_section` is the shared append seam (t1657_1), used by the note
mailbox and the gate ledger. Any caller that passes a multiline `<body>` on macOS
destroys the target task file. `ait note`'s own documented interface advertises
multiline bodies (`--file -` with a heredoc, in CLAUDE.md and the
`/aitask-note` skill), so the documented happy path is the one that loses data.

## Suggested fix

Two independent defects; fix both, and the second one matters more.

1. **Stop the unconditional `mv`.** Both sites do `awk ... > "$tmp"; mv "$tmp"
   "$file"; return 0` with no status check. Guard every tempfile swap on the
   producer's exit status (and ideally on a non-empty result), and return
   non-zero so the caller can report a real failure instead of `NOTE_APPENDED:`.
   This alone converts silent data loss into a visible error, and it protects
   against every future producer failure, not just this one.
2. **Stop passing the body through `-v`.** Feed it to awk on stdin / via a
   tempfile read in `BEGIN` (or build the block with the plain shell `printf`
   path the EOF branch already uses), so newlines are data rather than syntax.

## Verification

- A regression test that appends a genuinely multiline body through
  `ait_ledger_append_section` on **both** branches (target with an anchor header
  and no section → the `:227` create-before path; target with an existing
  section → the `:246` `section_end` path) and asserts the pre-existing content
  survives byte-for-byte.
- A negative-control test that forces the producer to fail and asserts the
  target file is left untouched and the function returns non-zero.
- `bash tests/test_note_*.sh` (whatever t1657 shipped) must stay green.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-08T13:11:21Z status=pass attempt=1 type=human
