---
Task: t1433_extract_delimited_record_protocol.md
Worktree: (current-branch mode — no worktree)
Branch: main
Base branch: main
Output branch: main
---

# t1433 — Extract the delimited-record protocol into `lib/record_protocol.py`

## Context

Three `lib/` modules emit the same `|`-delimited, newline-terminated line
protocol, and each carries its own private copy of the safety policy that makes
that protocol decodable. `lib/work_report_gather.py:96-115` and
`lib/trail_gather.py:160-181` carry a **byte-identical** six-symbol block;
`lib/board_columns.py` carries a third partial copy (`_RECORD_BREAKING:119`,
`_has_record_breaking:209`, plus its own `_line_safe`/`_field_safe` pair).

t1377_1 created the third copy rather than importing the second, on the
reasoning that folding it in would widen that task's approved de-dup scope. The
real objection was **ownership** — a `|`-delimited protocol predicate does not
belong in a board-column module, and `trail_gather.py` should not import from a
board module to get it. That argues for a neutral home, not a third copy.

The reserved-character set is fixed by the wire protocol, so drift is unlikely;
the failure mode is what matters. A protocol change would have to find three
sites, and a missed one lets a record-breaking character into a `|`-delimited
stream where **no reader can distinguish it from a separator**.
`aidocs/framework/planning_conventions.md:11` ("Refactor duplicates before
adding to them") is the standing rule this satisfies.

Outcome: one dependency-free `lib/record_protocol.py` owns the policy; all three
modules import it; the sanitizer pair keeps the load-bearing last-field /
middle-field asymmetry explicit in its names.

## Premise correction (AC deviation — on record)

The task description states, under *"Consider also folding in"*:

> The gatherers' single `_free_text` is equivalent to `_line_safe`.

**This is false, and the difference is observable.**

| | source | `"a\r\nb"` → |
|---|---|---|
| `_free_text` (both gatherers) | `.replace("\r\n"," ").replace("\r"," ").replace("\n"," ")` | `"a b"` (one space) |
| `_line_safe` (`board_columns`) | `.replace("\r"," ").replace("\n"," ")` | `"a  b"` (two spaces) |

Both are *safe* (no CR/LF survives), but they are not the same function. Both
behaviours are currently **pinned**: `tests/test_trail_gather.py:775` asserts
one space, `tests/test_board_columns_seam.py:484` asserts two.

**Decision (confirmed with the user, 2026-08-05):** unify on the CRLF-collapsing
policy (`_free_text`'s). A CRLF sequence is one line break and should become one
space; the two-space result is an accident of ordering, and the only affected
input — a CRLF inside a board column *title* — is pathological and purely
cosmetic. This is a deliberate, documented output flip, not a silent one. The
pre-phase `correct_task_premise` step below fixes the task's AC before any code
is written.

## Design — `lib/record_protocol.py`

A new module with **zero imports** (like `lib/board_ordering.py`), so it adds
nothing to the board's startup path — `board_columns.py` is imported by
`board/aitask_board.py` at module scope, and `lib/` is already on `sys.path` in
every consumer (the board inserts it at `aitask_board.py:15`, `trail_gather.py`
at `:122-125`, and `work_report_gather.py` / `board_columns.py` run with `lib/`
as `sys.path[0]`). A plain `from record_protocol import …` works in all four.

Surface:

```python
RECORD_BREAKING = ("|", "\r", "\n")
INVALID_ENUM = "invalid"
UNKNOWN_ENUM = "unknown"

def has_record_breaking(value: str) -> bool
def sanitize_last_field(value: str) -> str    # CR/LF only — '|' SURVIVES
def sanitize_middle_field(value: str) -> str  # CR/LF and '|'
def enum_field(value) -> str                  # absent -> unknown, unsafe -> invalid
```

**No `__all__`, and the docstring says why.** These names are generic
(`enum_field`, `sanitize_last_field`) and an `__all__` would advertise them as a
stable public API — a compatibility commitment this task has no mandate to make.
It is an internal deduplication: the module is a shared implementation detail of
the three `lib/` line protocols, with no compatibility policy and no promise to
callers outside `lib/`. `lib/board_ordering.py` — the dependency-free precedent
this module follows — likewise has no `__all__`. (`board_columns.py` has one
because it *is* a declared seam with headless callers; this module is not.)

The two sanitizer names carry the asymmetry the old `_free_text` /
`_line_safe` / `_field_safe` spelling buried: a `|` is legal in the **last**
field (consumers split with a fixed `maxsplit`, so titles and paths may contain
one) and illegal in a **middle** field. That asymmetry is load-bearing and was a
real defect caught during t1377_1 review; the module docstring says so.

**What deliberately does NOT move:**

- `_die` and the per-module stderr prefixes (`work_report_gather:` /
  `trail_gather:`). The task names this explicitly: a library path must not
  `sys.exit` inside a TUI, and the prefixes are pinned by characterization
  tests. `record_protocol` raises/returns only.
- `trail_gather._csv_entry` — it adds a *fourth* reserved character (`,`) for a
  csv-within-a-field encoding only `trail_gather` uses. It stays put and is
  rewired to consume the shared `has_record_breaking` / `INVALID_ENUM`.

**Call-site style:** direct import of the shared names, call sites renamed (no
`import … as _free_text` aliases). This follows the t1377_1 precedent —
`work_report_gather.py:58-66` imports `board_columns`' names directly and its
comment argues against re-exporting, because that "would just re-create a second
name for the same thing."

## Implementation

### Pre-phase (risk mitigations)

1. `[correct_task_premise]` Rewrite the *"Consider also folding in"* paragraph
   of `aitasks/t1433_extract_delimited_record_protocol.md` so the AC states the
   real relationship (`_free_text` collapses CRLF to one space, `_line_safe`
   leaves two) and records the confirmed unify-on-collapse decision plus the one
   assertion that flips. Commit before any code is written:
   ```bash
   ./ait git add aitasks/t1433_extract_delimited_record_protocol.md
   ./ait git commit -m "ait: Correct t1433 free_text/line_safe equivalence claim"
   ```
   Done: `git show --stat HEAD` names the task file and the paragraph no longer
   contains the word "equivalent".

2. `[baseline_capture]` Before touching any source, capture **two** independent
   baselines. Suite verdicts alone are not sufficient — a second semantic change
   whose expectation is edited alongside the permitted CRLF assertion would keep
   every pass count identical. So the load-bearing half is a byte-level capture
   of the actual protocol output.

   (a) Suite verdicts:
   ```bash
   ~/.aitask/venv/bin/python -m pytest tests/test_board_columns_seam.py \
     tests/test_work_report_columns_characterization.py tests/test_trail_gather.py -q
   bash tests/test_work_report_gather.sh   2>&1 | tail -3
   bash tests/test_board_column_cli.sh     2>&1 | tail -3
   bash tests/test_no_lib_to_tui_import.sh 2>&1 | tail -3
   ```
   Verified green at plan time — 116 passed / 103 / 68 / 13.

   (b) **Protocol-output capture.** Write a throwaway harness at
   `<scratchpad>/capture_protocol_output.sh` that drives all three real CLIs and
   dumps `exit / stdout / stderr` for each into one capture file.

   **Two fixture trees, not one — the success and fatal cases are mutually
   exclusive.** A `|`-bearing column id is rejected *for the whole config*:
   `board_columns.column_records_at:309-313` loops over every record and raises
   `ColumnIdError` on the first bad id rather than skipping that column, and
   `work_report_gather.load_columns` turns that into `_die(EXIT_INFRA)`. So a
   config carrying an unsafe id makes **every** invocation of both consumers
   fail closed, and no success-path output could be captured from it. The
   name-less `project_config.yaml` does the same to `trail_gather`
   (`local_project_name:225`). The harness therefore builds two independent
   trees and never mutates either mid-run — no ordering hazard, order-independent
   and re-runnable:

   - **`fixture_ok/`** — safe column *ids*, valid `project.name`;
     record-breaking values confined to the fields that are *sanitized* rather
     than *refused*.
   - **`fixture_fatal/`** — a `|`-bearing column id and a `project_config.yaml`
     with no `project.name`. Used only for the refusal invocations.

   Each tree is `aitasks/{metadata,archived}` + `aiplans/` +
   `board_config.json` + `project_config.yaml` + two task files, and serves all
   three CLIs: `work_report_gather` honours `TASK_DIR`
   (`tests/test_work_report_gather.sh:57-63`), `board_column` takes `--root`,
   `trail_gather` is cwd-relative.

   | tree | CLI invocation | seeded field | exercises |
   |---|---|---|---|
   | ok | `aitask_board_column.sh list-columns --root …` | title `A\|B\r\nC`, colour `#FF\|00\r00` | `sanitize_last_field`, `sanitize_middle_field` |
   | ok | `aitask_work_report_gather.sh --list-columns` and `--columns … --now <pinned>` | title with `\|` and CRLF, task path with `\|`, unsafe `status`/`priority`/`effort` | `sanitize_last_field`, `enum_field` |
   | ok | `aitask_trail_gather.sh snapshot --scope task …` | unsafe `status`/`priority`/`effort`/`boardcol`, a label containing `,`, a path with `\|` | `enum_field`, `_csv_entry`, `sanitize_last_field` |
   | fatal | the same board-column and work-report invocations | `\|`-bearing column id | `has_record_breaking` → `ColumnIdError` / `EXIT_INFRA` **and** the `work_report_gather:` stderr prefix |
   | fatal | the same trail invocation | `project_config.yaml` with no `project.name` | `_die(EXIT_INFRA)` **and** the `trail_gather:` stderr prefix |

   **The capture must be deterministic or the diff is noise.** Two requirements:
   both trees are built at *fixed* scratchpad paths (wiped and rebuilt at the
   top of each run — `mktemp -d` would make every `TASK:` path line differ
   between before and after), and `work_report_gather` is always called with a
   pinned `--now YYYY-MM-DD`, since its `VELOCITY_MODEL:` window is derived from
   today's date.

   Done: `<scratchpad>/protocol.before.txt` exists, contains a non-empty record
   for every row above (three zero exits from `fixture_ok`, three non-zero from
   `fixture_fatal`), and re-running the harness immediately reproduces it
   byte-for-byte — verify that self-diff before trusting it as a baseline. Keep
   the harness; the post-phase re-runs the identical script.

---

### Step 1 — Create `.aitask-scripts/lib/record_protocol.py`

New file, no imports. Docstring covers: why the module exists (three copies,
t1377_1's ownership argument), the dependency-free constraint and the board
startup path, the last-vs-middle asymmetry and why `|` must survive the last
field, why `_die` / the module prefixes stayed behind, and the t1433 CRLF
unification. Fold in the two reasoning paragraphs currently living in
`board_columns._line_safe` / `_field_safe` — "sanitize at the write site,
because a delimited encoding is undecidable on read" and "a bad *colour*
degrades, a bad *id* stays fatal".

```python
RECORD_BREAKING = ("|", "\r", "\n")
INVALID_ENUM = "invalid"
UNKNOWN_ENUM = "unknown"

# No __all__ — see the Design section: this is an internal shared
# implementation detail, not a public API with a compatibility policy.


def has_record_breaking(value: str) -> bool:
    return any(ch in value for ch in RECORD_BREAKING)


def sanitize_last_field(value: str) -> str:
    return value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def sanitize_middle_field(value: str) -> str:
    return sanitize_last_field(value).replace("|", "")


def enum_field(value) -> str:
    if value is None or value == "":
        return UNKNOWN_ENUM
    text = str(value)
    return INVALID_ENUM if has_record_breaking(text) else text
```

### Step 2 — Rewire `lib/work_report_gather.py`

Delete `_RECORD_BREAKING` / `INVALID_ENUM` / `UNKNOWN_ENUM` (`:96-98`) and
`_has_record_breaking` / `_free_text` / `_enum_field` (`:101-115`); keep the
`# --- Delimiter safety ---` prose block, retargeted to name the shared module.
Keep `_die` (`:118-120`) untouched.

Import only what is used (no constants are referenced outside the deleted
helpers):

```python
from record_protocol import enum_field, has_record_breaking, sanitize_last_field
```

Rename call sites: `_enum_field` → `enum_field` (`:201, 209, 210`);
`_free_text` → `sanitize_last_field` (`:401, 414, 526, 590, 598`);
`_has_record_breaking` → `has_record_breaking` (`:405, 453`).

### Step 3 — Rewire `lib/trail_gather.py`

Delete `:160-162` and `:167-181`; keep the `# --- Delimiter safety ---` header,
retargeted. Keep `_csv_entry` (`:184-190`) and `_die` (`:193-195`) untouched.

```python
from record_protocol import (  # noqa: E402
    INVALID_ENUM, enum_field, has_record_breaking, sanitize_last_field,
)
```

(`INVALID_ENUM` is needed by `_csv_entry`; `UNKNOWN_ENUM` is not referenced.)

Rename call sites: `_has_record_breaking` (`:188, 464`); `_free_text`
(`:200, 494, 894`); `_enum_field` (`:476, 479, 489-492`).

### Step 4 — Rewire `lib/board_columns.py`

Delete `_RECORD_BREAKING` (`:119`), `_has_record_breaking` (`:209-210`),
`_line_safe` (`:539-547`) and `_field_safe` (`:550-559`), their reasoning having
moved into `record_protocol`'s docstring in Step 1.

```python
from record_protocol import (
    has_record_breaking, sanitize_last_field, sanitize_middle_field,
)
```

Rename call sites: `has_record_breaking(rec.id)` (`:310`);
`sanitize_middle_field(rec.color or '')` and `sanitize_last_field(rec.title)`
(`:593-594`). `__all__` (`:79-88`) is unchanged — these were private and stay
unexported.

### Step 5 — Update the four test references

- `tests/test_board_columns_seam.py:472` — `bc._field_safe` →
  `bc.sanitize_middle_field`.
- `tests/test_board_columns_seam.py:482-485` — `bc._line_safe` /
  `bc._field_safe` → the new names, **and flip** the CRLF assertion from
  `"a  b"` to `"a b"`, with an inline note recording that t1433 unified the two
  last-field policies on CRLF-collapse and that this is the single intended
  behaviour change in the task. Reaching the functions through `bc.` (rather
  than importing `record_protocol` in the test) is deliberate: it also proves
  `board_columns` actually imports them.
- `tests/test_trail_gather.py:775` — `trail_gather._free_text` →
  `trail_gather.sanitize_last_field` (assertion value unchanged — this is the
  policy that won).

### Step 5b — Pin the flip at the *writer* boundary, not just the function

`bc.sanitize_last_field("Col|One")` proves the function; it does not prove the
CLI still emits the title **last** and runs it through that sanitizer.
`tests/test_board_column_cli.sh:95-103` already proves half of this end-to-end —
the fixture title `Col|One` plus a `cut -d'|' -f3-` decode pin title-last and
`|`-survival through the real `aitask_board_column.sh`. But that file contains
**no CR/LF case at all** (verified by grep), so the exact half t1433 flips is
unpinned at the boundary where it is observable.

Add a `list-columns` case to `tests/test_board_column_cli.sh` using a title that
carries **both** reserved characters — JSON `"title": "A|B\r\nC"` — plus a
colour carrying `|` and CR, and decode with the documented fixed max-split
contract:

```bash
line="$(printf '%s\n' "$out" | grep '^COLUMN:crlf|')"
recovered="$(printf '%s' "${line#COLUMN:}" | cut -d'|' -f3-)"
assert_eq "title keeps its pipe and collapses CRLF to ONE space" "A|B C" "$recovered"
assert_eq "record is still exactly one line" "1" \
    "$(printf '%s\n' "$out" | grep -c '^COLUMN:crlf|')"
```

plus an assertion that the middle colour field carries neither `|` nor CR. This
is the only place the flip is asserted against real CLI bytes rather than a
function call, and it is what makes the protocol-output capture in the
pre/post-phases interpretable.

### Step 6 — New: `tests/test_record_protocol.py`

Unit-pin the extracted policy directly, in the spirit of
`tests/test_board_ordering.py`:

- `has_record_breaking` fires on **each** of `|`, `\r`, `\n` individually
  (weakest-surface: assert per character via `subTest`, not on one string
  containing all three) and is false for a clean value.
- `sanitize_last_field` **preserves** `|` (the asymmetry) and collapses `\r\n`,
  bare `\r` and bare `\n` each to exactly one space.
- `sanitize_middle_field` strips `|` *and* CR/LF, and agrees with
  `sanitize_last_field` on every input containing no `|`.
- `enum_field`: `None` / `""` → `unknown`; a record-breaking value → `invalid`;
  a clean value → `str(value)` unchanged; a clean non-string is stringified.
- **The zero-import property, asserted structurally:** parse
  `lib/record_protocol.py` with `ast` and require zero `Import` / `ImportFrom`
  nodes. This is the constraint the task states ("dependency-free, like
  `lib/board_ordering.py`", because the module sits on the board's module-scope
  startup path) and it is otherwise unenforced by anything.

### Step 7 — New: fail-closed characterization for `trail_gather`

The task requires the `trail_gather` equivalent of
`tests/test_work_report_columns_characterization.py`, and none exists — no test
anywhere asserts `trail_gather`'s `EXIT_INFRA` (3) or its `trail_gather: `
stderr prefix (verified by grep over `test_trail_gather.py`,
`test_trail_skill_contract.sh`, `test_codeagent_trail.sh`).

Add it as a new section in `tests/test_trail_gather.py` rather than a new file,
so it reuses the existing `SyntheticRepo` fixture instead of forking it. Hoist
`run_wrapper` from `WrapperIntegrationTests` (`:876-880`) up to
`TrailGatherCase`, and add a **sibling** class — not a subclass, for the reason
the work-report characterization spells out at its `UnorderedPopulatedTests`
(subclassing silently re-runs the base's tests under a second name):

- Trigger: overwrite the fixture's `aitasks/metadata/project_config.yaml` with a
  body carrying no `project.name`, which reaches
  `trail_gather.local_project_name` → `_die(..., EXIT_INFRA)` (`:225`)
  deterministically through the real `.sh` entry point.
- Pin: `returncode == 3`; stderr starts with `trail_gather: `; stdout carries no
  protocol lines (a fatal path must not emit a partial stream).
- **Negative control**, mirroring
  `test_work_report_columns_characterization.py:180-191`: assert stderr does
  **not** contain `record_protocol:` and is non-empty. Without it the prefix
  assertion could pass vacuously if a future extraction let the shared module
  own the message — precisely the regression this refactor could introduce.
- **Positive control**: the same fixture with a valid `project.name` exits 0.

---

### Post-phase (risk mitigations)

1. `[differential_verification]` Two comparisons, the second load-bearing.

   (a) **Protocol-output diff — the actual proof.** Re-run the *identical*
   `capture_protocol_output.sh` from the pre-phase and diff:
   ```bash
   bash <scratchpad>/capture_protocol_output.sh > <scratchpad>/protocol.after.txt
   diff <scratchpad>/protocol.before.txt <scratchpad>/protocol.after.txt
   ```
   The permitted diff is **exactly** the `COLUMN:` line(s) whose title contained
   CRLF, changing from two spaces to one — nothing else. Every other line, every
   exit code and both stderr prefixes must be byte-identical. Assert this
   explicitly rather than eyeballing: the diff's changed-line count must be the
   number of CRLF-bearing title records, and the removed/added pair must differ
   only in that whitespace run. Any other delta means the extraction was not
   behaviour-preserving — stop and fix, do **not** re-baseline.

   Why this and not pass counts: a second semantic change could pass a
   verdict-only check if its expectation were edited alongside the permitted
   CRLF assertion. A capture taken before any source edit cannot be edited into
   agreement after the fact.

   (b) Suite verdicts, as a coarse backstop — re-run the `baseline_capture` (a)
   set plus the two new suites; every pre-existing count must match the baseline
   (`test_board_column_cli.sh` grows by Step 5b, the python set by Steps 6–7).
   Then the full gate:
   ```bash
   bash tests/run_all_python_tests.sh          # read ONLY the last line
   ```
   Done: the protocol diff contains only the CRLF title lines, and the last line
   reads `PYTHON SUITE: PASSED`.

2. `[prove_new_guards_can_fail]` Before committing, confirm each new or changed
   regression guard actually discriminates — **one mutation at a time**,
   restored immediately by undoing the edit (never `git checkout`), with
   `find . -name __pycache__ -prune -exec rm -rf {} +` between mutations so a
   stale `.pyc` cannot make a control fail (or pass) for the wrong reason:
   1. Drop the `.replace("\r\n", " ")` term from
      `record_protocol.sanitize_last_field` → `tests/test_record_protocol.py`,
      `tests/test_trail_gather.py:775` **and Step 5b's CLI case in
      `tests/test_board_column_cli.sh`** must each exit 1. The third is the one
      that matters: it proves the writer-boundary guard, not just the function
      guard, is live. Restore.
   2. Drop the `.replace("|", "")` term from
      `record_protocol.sanitize_middle_field` →
      `tests/test_board_columns_seam.py`'s asymmetry test **and** Step 5b's
      colour assertion must exit 1. Restore.
   3. Change `trail_gather._die`'s prefix to `record_protocol: ` → Step 7's
      negative control must exit 1. Restore.
   4. Reorder `board_columns`' `list-columns` emit to put the title in the
      middle field → Step 5b's max-split decode must exit 1. This is the
      writer-boundary property no function-level test can see. Restore.
   Done: each of the four mutations produced a **named** failing test id (assert
   on the id, not merely on a nonzero exit), and the suite is green again after
   every restore.

## Verification

| What | Command | Expected |
|---|---|---|
| **Protocol bytes unchanged but for the flip** | `diff <scratchpad>/protocol.{before,after}.txt` | only the CRLF-title `COLUMN:` lines differ (two spaces → one) |
| New module unit pins | `~/.aitask/venv/bin/python -m pytest tests/test_record_protocol.py -q` | all pass |
| Consumers, behavioural | `~/.aitask/venv/bin/python -m pytest tests/test_board_columns_seam.py tests/test_work_report_columns_characterization.py tests/test_trail_gather.py -q` | ≥116 passed (grows by Step 7) |
| work-report CLI protocol | `bash tests/test_work_report_gather.sh 2>&1 \| tail -3` | `103/103 passed` |
| board-column CLI protocol (incl. the new CRLF+pipe writer case) | `bash tests/test_board_column_cli.sh 2>&1 \| tail -3` | `>68` passed, 0 failed |
| Layering guard | `bash tests/test_no_lib_to_tui_import.sh 2>&1 \| tail -3` | `13 passed, 0 failed` |
| Full Python gate | `bash tests/run_all_python_tests.sh` | last line `PYTHON SUITE: PASSED` |
| Board startup path still imports | `~/.aitask/venv/bin/python -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); import board_columns; print(board_columns.column_records_at('/nonexistent'))"` | prints the stock 3 columns, no ImportError |

Post-implementation cleanup, merge and archival follow **Step 9** of the shared
task workflow (current-branch mode: no worktree to remove; merge target `main`
per the header above).

## Risk

Levels below are the **post-inline reassessment** — i.e. they describe the plan
as it now stands, with the four confirmed mitigation phases included.

### Code-health risk: medium

- A deliberate output flip on a live `|`-delimited protocol: `board_columns`'
  `list-columns` renders a CRLF-bearing column title with one space instead of
  two. Bounded (cosmetic, pathological input, single pinned assertion) and
  user-confirmed, but it *is* a behaviour change on a fail-closed path ·
  severity: medium · → mitigation: inline pre-phase `baseline_capture`, inline
  post-phase `differential_verification` (byte-level protocol capture, not
  suite verdicts), plus Step 5b's writer-boundary CLI case
- Three modules on protocol paths take mechanical call-site renames across ~25
  sites; a missed rename in a rarely-exercised branch surfaces as a runtime
  `NameError` rather than a wrong value · severity: low · → mitigation: inline
  post-phase `differential_verification`
- The sanitizers could stay correct while the *writer* stops applying them or
  reorders its fields — a function-level test cannot see either · severity:
  medium · → mitigation: Step 5b (real-CLI CRLF+pipe case decoded by the
  documented max-split rule), proven discriminating by mutations 1, 2 and 4 of
  inline post-phase `prove_new_guards_can_fail`
- The new module joins the board's module-scope startup path, so any import
  added to it later silently becomes a board startup cost · severity: low · →
  mitigation: none (covered by Step 6's zero-import AST assertion)
- Generic exported names (`enum_field`, `sanitize_last_field`) could be read as
  a public API and acquire outside callers with no compatibility policy ·
  severity: low · → mitigation: none (covered by Step 1 — no `__all__`, and an
  explicit "internal shared implementation detail" docstring)

The level stays `medium` after inlining: the mitigations make the flip
impossible to *miss*, not impossible to *have* — the behaviour change on a
fail-closed protocol path is still real.

### Goal-achievement risk: low

- The task's stated premise (`_free_text` ≡ `_line_safe`) is false; building to
  it verbatim would produce either a silent regression or a preserved
  near-duplicate · severity: medium · → mitigation: inline pre-phase
  `correct_task_premise`
- `trail_gather`'s fail-closed protocol behaviour is currently unpinned, so
  "preserve it exactly" is unverifiable as stated · severity: medium · →
  mitigation: Step 7's characterization, proven discriminating by inline
  post-phase `prove_new_guards_can_fail`
- Scope completeness: a fourth copy of the policy would leave the drift hazard
  standing · severity: low · → mitigation: none needed — a repo-wide scan for
  `_RECORD_BREAKING` and for inline `replace("\r"…)` across
  `.aitask-scripts/**.py` returns exactly the three known modules (verified at
  plan time)

### Planned mitigations
- timing: pre-phase | name: correct_task_premise | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the task's stated `_free_text` ≡ `_line_safe` premise is false | desc: Correct the task description's equivalence claim and record the confirmed CRLF-collapse decision before any code is written
- timing: pre-phase | name: baseline_capture | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — CRLF output flip and ~25 mechanical call-site renames | desc: Capture both the six guard suites' verdicts and a deterministic byte-level protocol dump of all three real CLIs over two fixture trees (success and fail-closed, which cannot coexist in one config), before any source edit
- timing: post-phase | name: differential_verification | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — CRLF output flip and ~25 mechanical call-site renames | desc: Re-run the identical capture harness and diff the protocol bytes, permitting only the CRLF title lines; suite verdicts are the coarse backstop
- timing: post-phase | name: prove_new_guards_can_fail | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — trail_gather's fail-closed behaviour is unpinned, so preservation is unverifiable; code-health — the writer could stop applying the sanitizers or reorder its fields | desc: Four one-at-a-time source mutations proving each new guard turns a named test red, each restored with __pycache__ purged
