---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-05 16:07
updated_at: 2026-08-05 16:09
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
(also strips `|`, for middle fields). The gatherers' single `_free_text` is
equivalent to `_line_safe`. If the shared module exposes both, name them so the
last-field-vs-middle-field distinction is explicit — that asymmetry is load
bearing and was a real defect caught during t1377_1 review.

## Why it matters

The reserved-character set is fixed by the wire protocol, so drift is unlikely —
but the failure mode is silent: a protocol change would need to find three sites,
and a missed one lets a record-breaking character through into a `|`-delimited
stream where no reader can distinguish it from a separator.
`aidocs/framework/planning_conventions.md:11` ("Refactor duplicates before adding
to them") is the standing rule this satisfies.
