---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-05 16:07
updated_at: 2026-08-05 17:40
---

## Origin

Surfaced during t1377_1 (headless board-column seam), and **t1377_1 made it
worse**: it added a third copy of `_has_record_breaking` rather than extracting
the shared block, on the reasoning that folding it in would widen that task's
approved de-dup scope. On review that reasoning did not hold — importing the
predicate would have been a one-line change with identical semantics. The real
objection was *ownership* (a `|`-delimited protocol predicate does not belong in
a board-column module, and `trail_gather.py` should not import from a board
module to get it), which argues for a neutral home, not a third copy.

## The duplication

`lib/work_report_gather.py:96-115` and `lib/trail_gather.py:160-181` carry a
**byte-identical** six-symbol block. `trail_gather` even labels it
`# --- Delimiter safety (parity with work_report_gather's pinned policy) ---`,
which is the same manual-sync-obligation comment style that
`DEFAULT_COLUMNS` carried before t1377_1 removed it.

| Symbol | work_report_gather | trail_gather | board_columns |
|---|---|---|---|
| `_RECORD_BREAKING = ("\|", "\r", "\n")` | `:96` | `:160` | `:119` |
| `INVALID_ENUM = "invalid"` | `:97` | `:161` | — |
| `UNKNOWN_ENUM = "unknown"` | `:98` | `:162` | — |
| `_has_record_breaking()` | `:101` | `:167` | `:209` |
| `_free_text()` | `:105` | `:171` | — (has `_line_safe`/`_field_safe`) |
| `_enum_field()` | `:110` | `:176` | — |

Verify with `diff <(sed -n '96,115p' …/work_report_gather.py) <(sed -n '163,181p' …/trail_gather.py)`
— the only difference is the comment header.

## Goal

Extract the delimited-record protocol into **one** dependency-free `lib/` module
(suggested `lib/record_protocol.py`), and have all three consumers import it.

Constraints:

- **Dependency-free, like `lib/board_ordering.py`.** `board_columns.py` is
  imported by `board/aitask_board.py` at module scope, so anything it imports is
  on the board's startup path. The new module must import nothing but stdlib.
- **`tests/test_no_lib_to_tui_import.sh` still applies** — the new module lives
  in `lib/` and must not reach into any TUI package.
- **Preserve the fail-closed CLI behaviour exactly.** Both gatherers exit
  `EXIT_INFRA` (3) via their own `_die()` with a module-specific stderr prefix
  (`work_report_gather: …`). The extracted helpers must keep raising/returning as
  they do now; **do not** move `_die` or the prefixes into the shared module —
  that difference is deliberate (a library path must not `sys.exit` inside a TUI).
- `tests/test_work_report_columns_characterization.py` already pins
  `--list-columns` stdout, exit 3 and the `work_report_gather:` prefix, and has a
  negative control on that prefix. Run it before and after — it is the existing
  guard that this refactor is behaviour-preserving. Add the equivalent for
  `trail_gather`'s protocol output if none exists.

## Consider also folding in

`board_columns.py` splits the sanitizer in two — `_line_safe` (CR/LF only, for
the **last** field, since titles may legitimately contain `|`) and `_field_safe`
(also strips `|`, for middle fields). The shared module must expose both, named
so the last-field-vs-middle-field distinction is explicit — that asymmetry is
load bearing and was a real defect caught during t1377_1 review.

**Correction (t1433 planning).** An earlier revision of this section claimed the
gatherers' single `_free_text` is *equivalent* to `_line_safe`. It is not, and
the difference is observable:

| | source | `"a\r\nb"` → |
|---|---|---|
| `_free_text` (both gatherers) | `.replace("\r\n"," ").replace("\r"," ").replace("\n"," ")` | `"a b"` (one space) |
| `_line_safe` (`board_columns`) | `.replace("\r"," ").replace("\n"," ")` | `"a  b"` (two spaces) |

Both are *safe* (no CR/LF survives) but they are not the same function, and both
behaviours are currently pinned — `tests/test_trail_gather.py:775` asserts one
space, `tests/test_board_columns_seam.py:484` asserts two.

**Decision (confirmed with the user, 2026-08-05):** the shared last-field
sanitizer unifies on the CRLF-collapsing policy (`_free_text`'s). A CRLF is one
line break and should become one space; the two-space result is an accident of
replacement ordering, and the only affected input — a CRLF inside a board column
*title* — is pathological and purely cosmetic.

This makes **one intended behaviour change** in this task: `aitask_board_column.sh
list-columns` renders a CRLF-bearing title with one space instead of two.
Exactly one existing assertion flips —
`tests/test_board_columns_seam.py:484` — and no other output may change. The
"preserve the fail-closed CLI behaviour exactly" constraint above is otherwise
unmodified.

## Scope split (t1433 implementation, 2026-08-05)

**This task lands two of the three consumers, not three.** At implementation
time a concurrent session held 292 lines of uncommitted work in
`.aitask-scripts/lib/trail_gather.py` (+124) and `tests/test_trail_gather.py`
(+186) — two of the files the Goal above names. Their hunks did not overlap the
symbols this task moves, but committing those files would have swept another
session's in-flight work into this task's commit. Splitting was an explicit user
decision.

Landed here: `lib/record_protocol.py`, plus the rewiring of
`lib/work_report_gather.py` and `lib/board_columns.py` and their tests.

Deferred to **t1436** (`depends: [1433]`): the `lib/trail_gather.py` rewiring,
the `tests/test_trail_gather.py:775` reference update, and the
`trail_gather` fail-closed characterization this task's constraints asked for
("Add the equivalent for `trail_gather`'s protocol output if none exists" — none
does). Until t1436 lands, the duplication is **two copies, not three**: the
shared module plus `trail_gather.py`'s private block.

## Why it matters

The reserved-character set is fixed by the wire protocol, so drift is unlikely —
but the failure mode is silent: a protocol change would need to find three sites,
and a missed one lets a record-breaking character through into a `|`-delimited
stream where no reader can distinguish it from a separator.
`aidocs/framework/planning_conventions.md:11` ("Refactor duplicates before adding
to them") is the standing rule this satisfies.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T14:40:06Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-05T15:18:57Z status=pass attempt=1 type=human
