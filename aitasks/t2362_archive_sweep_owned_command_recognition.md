---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, shell]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2290
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-25 17:50
updated_at: 2026-11-27 01:39
---

## Origin

Spawned from t2332 during planning. t2332 was scoped down to defect 1
(forwarding `"$@"` through `_ait_archive_exit_chain`) after two plan-review
rounds showed that defect 2 cannot be fixed safely with text-based
recognition. The user decided this at t2332's planning checkpoint. See
`aiplans/archived/p2332_archive_exit_chain_args_and_substring_match.md` once
t2332 is archived.

## Upstream defect

- `.aitask-scripts/lib/archive_utils.sh` — `_ait_archive_wrap_exit_trap`'s
  idempotence check matches `_ait_archive_cleanup` / `_ait_archive_exit_chain`
  as SUBSTRINGS. A caller trap whose quoted data or comment merely names them
  (`rmdir "$d/_ait_archive_cleanup"`, `h # docs; _ait_archive_cleanup`) is
  therefore treated as already wrapped. `ait_archive_rearm_exit_trap` becomes a
  no-op, the sweep is dropped, and bundled extractions leak.
  `_ait_archive_exit_chain`'s trap-text rewrite is also substring-based.

## Why the obvious fix is not safe

The obvious fix is "recognise our command by whole command" (whole text, or the
last command after an unescaped `"; "`, as `_registry_lock_owned_tail` does).
It needs real shell lexing. A miss is much worse than the substring false
positive: the wrap stores the chain as its own caller, overwrites the real
caller text, and the exit recurses until the function-nesting limit, so the
caller's handler never runs. The plan review reproduced these shapes in a
scratch copy:

- a newline separator (`t` on one line, the installed chain on the next) →
  recursion;
- a trailing terminator (`_ait_archive_exit_chain "$@";`) → recursion;
- a comment (`h # docs; _ait_archive_cleanup`) → a false-positive tail match;
  re-arm is skipped and the extraction leaks;
- `_registry_lock_owned_tail` misses `t; <cmd>;`, so registry_lock's exit chain
  drops the prefix from the `trap -p` it shows the caller (this matters to the
  ledger lock's first-command detector).

Today's substring rule is recursion-safe. It fails the benign way (a leak in
rare shapes), which is why t2332 kept it.

## Candidate designs

1. **Caller stack (no text-based ownership).** Every re-arm whose text is not
   byte-exactly what we last installed pushes that text onto a per-shell caller
   stack. A text with no mention of the chain name can reset the stack. A nested
   chain invocation runs the next-older caller, so no spelling can recurse or
   lose a caller. Forward the original `"$@"` to the nested levels.
   Complication: registry_lock's save/restore currently peels the archive layer
   by text and reads `_AIT_ARCHIVE_CALLER_EXIT_TRAP`. It would need an
   archive-owned unwrap/restore API, because otherwise the stack double-runs or
   loses entries across acquire/release (walk the flows: re-source after a
   txn prepend, then acquire → release / die-while-held).
2. **bash's own parser.** Define a throwaway function from the trap text and
   read `declare -f`'s normalised rendering (comments stripped, one command per
   line). It is faithful to the real lexer, but it evals trap text at re-arm
   time (an injection risk on unbalanced braces) and forks on every re-arm.

## Requirements for the fix

- Add expected-result tests for each shape above. Do not add
  twin-vs-twin differential tests: they miss a false positive both twins share.
- Fixtures build their shapes from the actually installed trap text (read back
  with `trap -p EXIT`), so the same fixture runs against the old and the new
  code.
- Add the missing `LEFT == 0` assertion to
  `tests/test_archive_rearm_exit_trap.sh` M-lit. Its flow-a trap-text
  expectation then changes to the archive chain, and the stored caller is
  checked verbatim through `_AIT_ARCHIVE_CALLER_EXIT_TRAP`.
- Keep t2332's regressions green: the P block (positional parameters) and the
  R-term block (re-arm idempotence over the terminator/newline shapes).
- Exercise registry_lock's exit chain while held, with a prefix and a
  terminating `;`, and have the caller inspect `trap -p` to show the prefix
  survives.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-26T23:39:25Z status=pass attempt=1 type=human
