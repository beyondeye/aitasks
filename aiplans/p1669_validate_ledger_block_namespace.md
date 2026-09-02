---
Task: t1669_validate_ledger_block_namespace.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1669 — Validate the ledger-block namespace before interpolating it into a regex

## Context

`.aitask-scripts/lib/ledger_block.py` (introduced by t1657_1) is the generic
marker-block ledger substrate. Two of its functions build a regex by
interpolating the caller-supplied `namespace` straight into a pattern:

```python
def build_marker_re(namespace: str) -> re.Pattern:
    return re.compile(rf"^>\s*\*\*(\S+)\s+{namespace}:({_NAME_CHARS})\*\*(.*)$")
```

The module **declares** the intended charset — `_NAMESPACE_CHARS =
r"[A-Za-z0-9_]+"` at `ledger_block.py:48` — and never applies it. The constant
has exactly one occurrence in the file: its own definition. A constant that
reads as a validation rule but is dead is worse than none, because it tells the
next author the input is already constrained.

Reproduced against the shipped module before planning:

| namespace | observed |
|---|---|
| `....` | `parse_blocks(gate_text, "....")` → `['tests_pass']` — a wildcard namespace silently cross-parses **another ledger's** blocks |
| `note(` | `re.PatternError: missing ), unterminated subpattern at position 21` |
| `note\|gate` | no match, but the alternation re-partitions the pattern, so a match on the second branch would hand the record factory `icon=None` |
| `""` | no match — inert, but still an invalid identifier accepted silently |

The silent wildcard case is the dangerous one: a consumer parsing another
ledger's blocks as its own would union, dedup and order records under the wrong
`SectionSpec`.

**Not live today.** The only namespaces in the tree are `gate`
(`gate_ledger.NAMESPACE`) and the `note` literal from t1657_2 / the multisection
test — both plain identifiers. This is a latent-defect fix on a new public API,
so the intended outcome is a *contract*, not a behaviour change: every current
call site keeps working byte-for-byte, and an out-of-charset namespace now fails
closed with a `ValueError` instead of silently mis-parsing or crashing inside
`re`.

**Why not `re.escape()`** (the task states this and I agree): escaping would make
a nonsense namespace *work* rather than be rejected. A namespace is a marker
identifier, not arbitrary text — the charset is a real contract. Fail closed.

## Call surface (verified)

`namespace` reaches a regex only through the two builders; everything else
delegates:

- `build_marker_re(namespace)` — `ledger_block.py:62`
- `build_marker_search_re(namespace)` — `ledger_block.py:68`
- `has_markers(text, namespace, search_re=None)` → calls `build_marker_search_re` when no precompiled pattern is passed (`:115`)
- `parse_blocks(text, namespace, factory, marker_re=None)` → calls `build_marker_re` when no precompiled pattern is passed (`:131`)
- `render_block(namespace, ...)` — interpolates into *output text*, not a regex (`:184`)

**The optional-pattern route is a hole in "validate at the builders".** When
`has_markers` / `parse_blocks` are handed a precompiled pattern, `namespace` is
never read — so validating only inside the builders would leave two *public*
entry points accepting `"...."` and `"note("` silently, while the module claims
the charset is a contract. The fix therefore validates the argument at **every**
public entry point that takes one, not just at the builders (see step 2b).

Callers: `lib/gate_ledger.py:129-130` (precompiles both from `NAMESPACE = "gate"`
at import time), `board/aitask_merge.py:593-594` (`parse_blocks(sec,
spec.namespace)` with `spec.namespace` from `GATE_SPEC`), and
`tests/test_ledger_block_multisection.py` (`"note"`). All valid — **no call site
changes**.

The shell twin `lib/ledger_block.sh` builds no regex from a namespace (only
marker-line assembly and an awk section append), so it is out of scope.

## Implementation

### 1. `.aitask-scripts/lib/ledger_block.py` — add the validator

Immediately after the charset constants (`:48-49`), add:

```python
#: A namespace is a marker *identifier*, not arbitrary text, and it is
#: interpolated into a regex by the two builders below. `\A`/`\Z` rather than
#: `^`/`$` so a trailing newline cannot slip through.
_NAMESPACE_RE = re.compile(rf"\A{_NAMESPACE_CHARS}\Z")


def _checked_namespace(namespace: str) -> str:
    """Return ``namespace`` if it is a legal marker identifier, else raise.

    Rejecting rather than ``re.escape``-ing is deliberate: escaping would make a
    nonsense namespace *work*, and a wildcard like ``....`` would then silently
    cross-parse another ledger's blocks. Fail closed.
    """
    if not _NAMESPACE_RE.match(namespace):
        raise ValueError(
            f"ledger namespace must match {_NAMESPACE_CHARS}, got {namespace!r}")
    return namespace
```

`re` is already imported at `:44`; the constants must move above the `KV_RE`
block only insofar as `_NAMESPACE_RE` follows `_NAMESPACE_CHARS` — no reordering
of existing lines.

### 2. Apply it at the two builders

```python
def build_marker_re(namespace: str) -> re.Pattern:
    """Full marker matcher for ``namespace``: groups are (icon, name, tail)."""
    return re.compile(
        rf"^>\s*\*\*(\S+)\s+{_checked_namespace(namespace)}:({_NAME_CHARS})\*\*(.*)$")


def build_marker_search_re(namespace: str) -> re.Pattern:
    """Cheap multiline prefilter for ``namespace`` markers anywhere in a text."""
    return re.compile(
        rf"(?m)^>\s*\*\*\S+\s+{_checked_namespace(namespace)}:{_NAME_CHARS}\*\*")
```

This covers `has_markers` and `parse_blocks` on their no-precompiled-pattern
paths — the path `aitask_merge.py` takes. It does **not** cover their
precompiled-pattern paths; step 2b does.

### 2b. Close the precompiled-pattern hole

`namespace` is a required positional on both functions and means the same thing
whether or not a pattern is supplied, so validate it unconditionally at the top:

```python
def has_markers(text: str, namespace: str, search_re: re.Pattern | None = None) -> bool:
    _checked_namespace(namespace)
    pattern = search_re if search_re is not None else build_marker_search_re(namespace)
    return bool(pattern.search(text))


def parse_blocks(text: str, namespace: str, factory=LedgerBlock,
                 marker_re: re.Pattern | None = None) -> list:
    _checked_namespace(namespace)
    pattern = marker_re if marker_re is not None else build_marker_re(namespace)
```

On the no-pattern path the builder re-validates — two `re.match` calls against a
≤8-character string per call, which is not worth an intervening private
`_build_*_unchecked` helper. Keeping the builders self-guarding matters more:
they are public and `gate_ledger.py:129-130` calls them directly.

Every in-tree caller of the precompiled route passes a valid namespace —
`gate_ledger.py:227` (`has_markers(text, NAMESPACE, search_re=MARKER_SEARCH_RE)`)
and `:242` (`parse_blocks(text, NAMESPACE, factory=GateRun, marker_re=MARKER_RE)`),
both with `NAMESPACE = "gate"` — so nothing breaks.

Record the resulting contract in the module docstring, one paragraph after the
"What deliberately does NOT live here" block, so the next author does not have to
infer it from the code:

> **Namespace contract.** A namespace is a marker *identifier* matching
> ``_NAMESPACE_CHARS``, validated at every public entry point that takes one —
> including ``has_markers`` / ``parse_blocks`` when a precompiled pattern makes
> the argument otherwise unused. Out-of-charset input raises ``ValueError``
> rather than being escaped: a wildcard namespace would otherwise silently
> cross-parse another ledger's blocks.

### 3. Also guard the write side: `render_block`

**This is one step beyond the task's literal acceptance criteria** ("both
builders"), so calling it out explicitly rather than folding it in silently.
`render_block` interpolates the namespace into the emitted marker line. A
namespace the builders reject but `render_block` accepts produces a block that
**no reader can ever match** — a silent append that is unreadable by
construction. One line closes the asymmetry:

```python
    marker = f"> **{icon} {_checked_namespace(namespace)}:{name}**"
```

No current caller is affected (`gate`, `note`). Say the word at approval and I
drop this step — the rest of the plan stands on its own.

`_NAME_CHARS` is deliberately **not** given the same treatment: the record name
is a fixed pattern in the regex, not a caller-supplied input. The task says to
revisit only if that changes.

### 4. `tests/test_ledger_block_namespace_validation.py` — new test module

Standalone `unittest` module (no fixture repo, no tmux, no chdir — safe in the
parallel lane), importing the seam directly:

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                ".aitask-scripts", "lib"))
import ledger_block
```

Cases:

Cases — the rejection and acceptance sets are each driven over **all five**
public entry points (`build_marker_re`, `build_marker_search_re`, `has_markers`,
`parse_blocks`, `render_block`) from one table, so no entry point can be
forgotten:

- **Reject** each of: `"...."`, `"note("`, `""`, `"note|gate"`, plus `"gate\n"`
  (pins the `\A`/`\Z` choice — `^`/`$` would accept it) and `"ga te"`. Assert
  `ValueError` via `assertRaises` and, per the guard-message rule, `assertIn`
  both the charset literal and `repr(namespace)` in `str(cm.exception)` —
  matched with `assertIn`, not `assertRaisesRegex`, because the message itself
  contains regex metacharacters.
- **Accept** `"gate"` and `"note"` at all five: the builders return a compiled
  pattern, `has_markers` / `parse_blocks` read the text, `render_block` emits its
  marker unchanged.
- **The precompiled-pattern route is validated too** — the case the hole in 2b
  is about. With `valid = build_marker_re("gate")`:
  - `parse_blocks(text, "....", marker_re=valid)` **raises** `ValueError`, and
    likewise `has_markers(text, "....", search_re=<valid search pattern>)`. This
    is the assertion that fails if the guard is put only in the builders.
  - `parse_blocks(text, "gate", marker_re=valid)` still returns the gate record,
    and `has_markers(text, "gate", search_re=…)` is still `True` — the positive
    control for `gate_ledger`'s module-level precompilation route, so a future
    edit cannot "fix" the case above by breaking the supported one.
- **The defect itself, as a negative control**: build the gate marker text from
  `render_block("gate", ...)`, assert `parse_blocks(text, "gate")` still finds it,
  and assert `parse_blocks(text, "....")` now raises `ValueError` where it
  previously returned the gate record. Without this the suite would pass against
  a validator that is defined but never wired into `parse_blocks`.

## Verification

```bash
# The new module, and the two suites that exercise the seam
bash tests/run_all_python_tests.sh --test-dir tests 2>&1 | tail -5   # note PIPESTATUS
python3 -m pytest tests/test_ledger_block_namespace_validation.py \
                  tests/test_ledger_block_multisection.py \
                  tests/test_ledger_block_reexport.py \
                  tests/test_gate_ledger_build_characterization.py -v
```

Read the **last** line of the runner output for the verdict
(`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); piping discards the exit
status, so check `${PIPESTATUS[0]}` or use `set -o pipefail`.

Plus the gate shell suites, which drive the ledger end to end through
`aitask_gate.sh`:

```bash
bash tests/test_gate_guarded_archival.sh
bash tests/test_create_manual_verification_gates.sh
```

Expected: everything green and unchanged — `gate` and `note` are valid
namespaces, so this fix is behaviour-preserving for every existing path.

## Risk

### Code-health risk: low
- The validator is applied at five public entry points in a single ~90-line
  module with no call-site changes anywhere else; the blast radius is one file
  plus one new test. · severity: low · → mitigation: none needed
- Turning a silently-wrong result into a raised `ValueError` is a behaviour
  change for out-of-charset input. Every namespace in the tree (`gate`, `note`)
  is in-charset and every non-test call site precompiles at import time, so a
  regression would surface immediately at import rather than at runtime.
  · severity: low · → mitigation: the full python suite + both gate shell suites
  in Verification above
- Validating `namespace` on the precompiled-pattern route adds one `re.match`
  per `parse_blocks` / `has_markers` call where the argument was previously
  unread. Both are called per task-file section during a merge, not in a loop
  over records, so the cost is not measurable. · severity: low ·
  → mitigation: none needed

### Goal-achievement risk: low
- None identified. The defect was reproduced against the shipped module before
  planning, the fix is the one the task specifies, and the negative-control test
  case fails if the validator is defined but not wired in.

## Step 9 (Post-Implementation)

Standard closure: commit the two files, run the `risk_evaluated` gate (in this
task's active set), then archive `aitasks/t1669_*.md` and
`aiplans/p1669_*.md`. Current-branch mode under profile `fast` — no worktree,
no merge.

## Final Implementation Notes

- **Actual work done:** Added `_NAMESPACE_RE` (anchored with `\A`/`\Z`) and
  `_checked_namespace()` to `.aitask-scripts/lib/ledger_block.py`, and applied
  the guard at **all five** public entry points that take a namespace:
  `build_marker_re`, `build_marker_search_re`, `has_markers`, `parse_blocks`
  and `render_block`. Recorded the resulting contract as a **Namespace
  contract** paragraph in the module docstring. Added
  `tests/test_ledger_block_namespace_validation.py` (11 tests). No call-site
  changes anywhere — `gate` and `note` are both in-charset.

- **Deviations from plan:** None from the approved plan. The plan itself
  deviated from the task's literal acceptance criteria in two places, both
  deliberate and both stated in the plan before approval:
  1. **`render_block` is guarded too** (the task named only "both builders"). It
     interpolates the namespace into the emitted marker line, so a namespace the
     readers reject but the writer accepts produces a block no reader can ever
     match — a silent append that is unreadable by construction.
  2. **`has_markers` / `parse_blocks` validate on their precompiled-pattern
     route**, where `namespace` is otherwise never read. Raised by the user as a
     blocking review concern against the first draft of the plan, which had
     instead planned to *pin the bypass in a test*. That would have locked in
     two public entry points silently accepting `"...."` / `"note("` while the
     module claimed the charset was a contract. Verified before adopting: every
     in-tree caller of that route (`gate_ledger.py:227,242` with
     `NAMESPACE = "gate"`) passes a valid namespace, so nothing breaks.

- **Issues encountered:** None in the implementation. Two things worth
  recording:
  - Splitting `build_marker_re`'s pattern across two adjacent f-strings (to keep
    the line under the width limit after the longer expression) produces a
    byte-identical compiled pattern; confirmed by printing
    `build_marker_re("gate").pattern`.
  - The tree carried unrelated uncommitted work from concurrent sessions
    (`aitask_add_model.sh`, `minimonitor_app.py`, `tui_conventions.md`,
    `test_add_model.sh`, `test_minimonitor_focus_in_click.py`). Only this task's
    two paths were staged; nothing else was touched, stashed or restored.

- **Key decisions:**
  - **Reject, do not `re.escape`.** Escaping would make a nonsense namespace
    *work*; the charset is a real contract and a namespace is a marker
    identifier, not arbitrary text. Fail closed.
  - **Both builders keep their own guard** even though `parse_blocks` /
    `has_markers` now validate first. The double check is two `re.match` calls on
    a ≤8-character string, and the builders are public — `gate_ledger.py:129-130`
    calls them directly at import time — so an intervening
    `_build_*_unchecked` helper would buy nothing and cost a seam.
  - **`_NAME_CHARS` deliberately left alone.** The record name is a fixed pattern
    inside the regex, not a caller-supplied input. Revisit only if that changes.
  - **`\A`/`\Z`, not `^`/`$`**, so `"gate\n"` cannot slip through. Pinned by a
    dedicated case in `BAD_NAMESPACES`.
  - **The test's entry-point table is coverage-asserted.**
    `test_entry_point_table_covers_the_module` reflects over the module and fails
    if a public namespace-taking function is added without an entry, so the
    "every entry point validates" claim cannot silently decay.

- **Verification performed:**
  - `tests/test_ledger_block_namespace_validation.py` — 11/11 pass.
  - `test_ledger_block_multisection` + `test_ledger_block_reexport` +
    `test_gate_ledger_build_characterization` — 40/40 pass.
  - `tests/test_gate_guarded_archival.sh` 31/31;
    `tests/test_create_manual_verification_gates.sh` 42/42.
  - Full suite: `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
  - **Mutation check** (copies in the scratchpad; the real tree was never
    reverted): against the pre-fix module the new suite fails 58 subtests / 4
    errors; against a **builders-only** guard it fails exactly the 16
    precompiled-route subtests and nothing else — the suite discriminates
    precisely on the dimension the review concern was about.

- **Upstream defects identified:** None

