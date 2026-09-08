---
Task: t1745_fix_failed_verification_t1737_item1.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1745 — Fix the drifted fixture copy list in `tests/test_desync_state.py`

## Context

`bash tests/run_all_python_tests.sh` reports `PYTHON SUITE: FAILED
(runner=pytest, exit=1)` on exactly **one** test out of 7035 passing:

```
FAILED tests/test_desync_state.py::DesyncStateTests::
       test_changelog_warns_for_data_desync_and_ignores_bad_helper_output
E  stderr=…/.aitask-scripts/lib/task_utils.sh: line 31:
        …/.aitask-scripts/lib/stale_lock.sh: No such file or directory
```

Reproduced locally (`~/.aitask/venv/bin/python -m pytest tests/test_desync_state.py`
→ `1 failed, 1 passed`), with the identical stderr.

**Root cause.** t1725_1 (`42ee07791`) added
`source "${SCRIPT_DIR}/lib/stale_lock.sh"` at `.aitask-scripts/lib/task_utils.sh:31`
and correctly extended the **shared** shell scaffold
(`tests/lib/test_scaffold.sh:59`). But `tests/test_desync_state.py` builds its
synthetic project from its **own private copy list** at line 60, which was not
extended — so the fixture cannot source what `task_utils.sh` now requires at
startup. This is the "source-on-startup ↔ test-scaffold rule" in
`aidocs/framework/shell_conventions.md`. It is platform-agnostic (fails
identically on macOS) and independent of t1729.

The fixture's own comment (lines 53–58) already warns that the list is separate
and "must be extended by hand whenever that chain grows". **The warning was
there and was not acted on** — which is why this plan replaces the list rather
than patching it.

**Sweep result (whole suite).** `tests/test_desync_state.py` is the *only*
fixture carrying a private copy list over `task_utils.sh`'s startup chain:

| surface | status |
|---|---|
| all shell tests that copy `task_utils.sh` | go through `tests/lib/test_scaffold.sh` — already correct |
| `tests/test_settings_commit_on_save.py` | symlinks the real `lib/` — immune by construction |
| `tests/test_backlog_view_is_single_sourced.py`, `tests/test_mark_glyphs_single_source.py` | copy Python surfaces for static scanning; no shell source chain |
| `tests/test_desync_state.py` | **the defect** |

Symlinking `lib/` (the `test_settings_commit_on_save.py` pattern) is **not** an
option here: `test_desync_state.py:260–264` deliberately **overwrites**
`lib/desync_state.py` with a bad stub, which through a symlink would corrupt the
real repository.

**Intended outcome.** The suite goes green, and the per-fixture copy list — the
recurring hazard — is replaced by a closure derived from the scripts themselves,
so the next growth of the startup chain cannot silently break a Python fixture.

## Design validation (performed read-only during planning)

Rooted at `.aitask-scripts/aitask_changelog.sh` and walked transitively, the
derivation yields:

```
archive_utils.sh, data_symlinks.sh, python_resolve.sh, stale_lock.sh,
task_utils.sh, terminal_compat.sh, yaml_utils.sh
```

— exactly the six hand-maintained names **plus** the missing `stale_lock.sh`,
with no extras. Two lazy sources are correctly excluded: `task_utils.sh:1088`
(`task_automerge.sh`, inside `_ait_load_automerge()`) and
`terminal_compat.sh:204` (`tmux_exec.sh`, inside a tmux helper).

Three source spellings appear in the tree and must all be recognised:
`${SCRIPT_DIR}/lib/…`, `$(dirname "${BASH_SOURCE[0]}")/…`, and
`$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/…`.

## Scope of the derivation (both review findings, verified)

The walk is **transitive**, so whatever convention it relies on binds every file
in the closure — today four: `task_utils.sh`, `archive_utils.sh`,
`python_resolve.sh`, `data_symlinks.sh`.

Two things were checked directly and shaped the design:

- **Bash attaches no meaning to indentation.** Probed: `    source "…/dep.sh"`
  at top level of a script → the sourced file **ran**. So column 0 is a
  *convention*, not a semantic.
- **Inferring the semantic instead is worse.** A prototype that classified by
  lexical function-body depth was tested against ordinary bash and **falsely
  flagged a top-level conditional source** —
  `if [[ -r … ]]; then source "${SCRIPT_DIR}/lib/opt.sh"; fi` — which is
  idiomatic (optional libs are exactly what gets conditionally sourced) and is
  semantically a startup source. A bespoke shell-depth parser therefore converts
  a legitimate future edit into a suite-wide failure unrelated to the behavior
  under test. **Rejected.**

**Resolution: enforce the convention, do not infer intent.** The derivation
recognises exactly one shape — an *unconditional* `source` of a lib, written at
**column 0**, in one of the three spellings above — and that shape is documented
at every scanned site and pinned by a format-contract test. No depth parser, no
escape hatch.

**What this deliberately does not buy.** A startup source written *indented*
(inside a top-level `if`, say) is outside the recognised shape and will not be
picked up. That case is handled by documentation, not code: the contract says a
lib needed at startup is sourced unconditionally at column 0, and anything that
genuinely must be conditional is also added to the fixture's explicit extras
list. This is the narrow, honest claim — the derivation removes the drift class
for the conventional case, which is exactly the case that broke in t1725_1.

## Implementation

### 1. New shared helper — `tests/lib/shell_startup_closure.py`

The Python counterpart to `tests/lib/test_scaffold.sh`. Module docstring states
the problem, names t1725_1/t1745 as the precedent, and documents the recognised
shape and what falls outside it.

```python
#: A startup lib source: column 0, unconditional, one of three spellings.
STARTUP_SOURCE_RE = re.compile(
    r'^source[ \t]+"(?:'
    r'\$\{?SCRIPT_DIR\}?/lib/'
    r'|\$\(dirname "\$\{BASH_SOURCE\[0\]\}"\)/'
    r'|\$\(cd "\$\(dirname "\$\{BASH_SOURCE\[0\]\}"\)" && pwd\)/'
    r')(?P<name>[A-Za-z0-9_]+\.sh)"[ \t]*$',
    re.M,
)

#: Loose shape used only by the contract test: any column-0 source/. line.
COLUMN0_SOURCE_RE = re.compile(r'^(?:source|\.)[ \t]+\S', re.M)

def startup_sources(path: Path) -> list[str]: ...
def startup_closure(lib_dir: Path, roots: Iterable[Path]) -> list[str]: ...
def copy_startup_closure(src_lib, dst_lib, roots) -> list[str]: ...
def nonconforming_column0_sources(path: Path) -> list[tuple[int, str]]:
    """Column-0 source lines that do NOT match the recognised shape."""
```

- Transitive walk with a `seen` set (terminates on cycles).
- A referenced name missing under `lib_dir` raises, so a typo cannot degrade
  into a silent omission.
- **Raises on an empty closure**, naming the roots: a regex that stops matching
  must fail loudly, not copy nothing — an empty result would otherwise
  reproduce the very bug being fixed.
- `nonconforming_column0_sources` is a plain line filter, not a parser: it
  reports column-0 `source` lines outside the recognised shape (e.g. a
  variable path such as `source "$some_dir/x.sh"`). It is used **only** by the
  contract test in step 3 — never to classify, and it never raises during a
  fixture build.

### 2. `tests/test_desync_state.py` — derive instead of enumerate

Replace the hardcoded list in `copy_changelog()` (lines 53–61). The long
"keep this in step by hand" comment is replaced by a short one pointing at the
helper; `desync_state.py` stays an explicit extra because it is a Python helper
shelled out to, not part of the shell source chain.

```python
def copy_changelog(project: Path) -> Path:
    script_dir = project / ".aitask-scripts"
    lib_dir = script_dir / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    changelog = script_dir / "aitask_changelog.sh"
    shutil.copy2(CHANGELOG_SRC, changelog)
    # The startup source chain is DERIVED from the scripts themselves
    # (tests/lib/shell_startup_closure.py) — never hand-listed. A hand list
    # here missed stale_lock.sh when it joined task_utils.sh in t1725_1 (t1745).
    copy_startup_closure(LIB_SRC, lib_dir, roots=[changelog])
    # Not part of the shell chain: task_utils.sh shells out to this helper.
    shutil.copy2(HELPER_SRC, lib_dir / "desync_state.py")
    return changelog
```

### 3. New test — `tests/test_shell_startup_closure.py`

**(a) Helper behavior**, against a **synthetic** mini-tree (never the real repo),
so the assertions cannot drift with the framework:

- direct + transitive resolution across all three recognised spellings;
- **negative control:** an indented `source` is excluded while an otherwise
  identical column-0 line is included — pins the recognised shape in both
  directions;
- a cyclic chain terminates;
- an empty closure **raises** rather than returning `[]`;
- `copy_startup_closure` puts exactly the returned names on disk (asserting the
  count, not merely that the call succeeded).

**(b) Format contract**, against the **real** tree — this is what replaces the
rejected parser:

- for every file the closure scans, `nonconforming_column0_sources()` is empty
  — i.e. every column-0 `source` line uses a recognised spelling. Measured
  during planning: **0 hits**, so this starts green. It catches the one hole a
  pure-regex derivation would otherwise have (a variable-path startup source
  such as `terminal_compat.sh:204`'s `$_tc_lib_dir/tmux_exec.sh`, were that
  written at column 0) and it needs no depth analysis;
- the real closure contains `stale_lock.sh` — the direct regression pin for this
  bug.

Both are pure line filters over text; neither can misread a conditional, a
brace group, a `case`, or any other bash construct, because neither models them.

### Post-phase (risk mitigations)

Placed after step 3; both are inline, name-labeled, and cross-referenced from
`## Risk` below.

- **`pin_startup_source_contract`** — the step 3(b) format-contract test plus
  the step 3(a) negative control. Together they pin the recognised shape from
  both sides: conforming lines are found, non-conforming column-0 lines are
  reported.
- **`document_startup_source_contract`** — the contract is written **once**
  canonically and pointed at from every scanned site, rather than restated:
  - extend the existing `source-on-startup ↔ test-scaffold` bullet in
    `aidocs/framework/shell_conventions.md` (line ~118, which today covers only
    the shell scaffold) with the Python counterpart and the recognised shape: a
    lib needed at startup is sourced **unconditionally, at column 0**, in one of
    the three spellings; a lazy/conditional source stays indented and, if it is
    nevertheless required at startup, must also be added to the consuming
    fixture's explicit extras;
  - a one-line pointer comment above the startup `source` block in **each of the
    four files the closure scans today** — `lib/task_utils.sh`,
    `lib/archive_utils.sh`, `lib/python_resolve.sh`, `lib/data_symlinks.sh` —
    naming `tests/lib/shell_startup_closure.py`. Comments only; no code change.
    (Covering all four is the review finding: the walk is transitive, so
    documenting only `task_utils.sh` would leave three scanned files silent.)

## Verification

1. The previously failing test, in isolation:
   `~/.aitask/venv/bin/python -m pytest tests/test_desync_state.py -q` → 2 passed.
2. The new helper's own tests:
   `~/.aitask/venv/bin/python -m pytest tests/test_shell_startup_closure.py -q`.
3. **Negative control that the fix is load-bearing** — temporarily neuter the
   derivation (make `STARTUP_SOURCE_RE` fail to match `stale_lock.sh`) and
   confirm `tests/test_desync_state.py` fails again with the same
   `stale_lock.sh: No such file or directory`, then revert. Proves the test is
   routed through the changed code and is not passing for another reason.
4. **Contract test actually fails when violated** — temporarily rewrite
   `lib/archive_utils.sh:22` to a variable path
   (`source "$_au_dir/terminal_compat.sh"`, still column 0) and confirm the
   step 3(b) test reports it by file and line, then revert. Exercises the
   contract on a real scanned file other than `task_utils.sh`.
5. Full suite, exit status preserved (never piped away):
   `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -20`
   → last line `PYTHON SUITE: PASSED (runner=…, exit=0)`. Record which lane ran
   (pytest+xdist parallel vs. serial unittest) — t1737's item asks for it, and
   t1729 was verified on the serial lane only.
6. Confirm the derived closure is the six pre-existing names plus
   `stale_lock.sh`, so the change is a superset of the hand list, not a
   different set.

Step 9 (Post-Implementation) handles cleanup, archival, and merge.

## Risk

### Code-health risk: low
- The derivation recognises only an unconditional column-0 source, so a startup
  source written indented (inside a top-level `if`) is not picked up and would
  fail the fixture at boot with the original cryptic error. This is a
  *deliberately narrowed* claim rather than a defect — inferring the semantic
  instead was prototyped and rejected for falsely flagging that same idiom ·
  severity: low · → mitigation: inline post-phase pin_startup_source_contract, inline post-phase document_startup_source_contract
- The contract now spans four production lib files and a doc, so the change
  reaches beyond `tests/` — comment-only there, but a wider surface than the
  original one-line fix · severity: low · → mitigation: none (accepted — the
  review established that documenting only `task_utils.sh` leaves the three
  other scanned files silent, which is the defect class itself)

### Goal-achievement risk: low
- The task's headline acceptance is a green **whole** suite; if this box carries
  an unrelated failure, that acceptance cannot be met by this fix alone (t1737
  measured exactly one failure out of 7035, so this is unlikely) · severity: low
  · → mitigation: none (verification step 5 measures it directly and reports
  honestly rather than assuming)

### Planned mitigations
- timing: post-phase | name: pin_startup_source_contract | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — recognised shape drifting unnoticed | desc: format-contract test that every column-0 source line in every scanned file uses a recognised spelling, plus a negative control that an indented line is excluded and a column-0 one included
- timing: post-phase | name: document_startup_source_contract | type: documentation | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — recognised shape drifting unnoticed | desc: extend the source-on-startup bullet in aidocs/framework/shell_conventions.md with the Python counterpart and the recognised shape, plus a one-line pointer comment above the startup source block in each of the four scanned lib files

## Final Implementation Notes

- **Actual work done:** Implemented as planned, in three parts plus both inline
  post-phase mitigations.
  1. `tests/lib/shell_startup_closure.py` (new) — derives the transitive startup
     `source` closure from the scripts themselves. `startup_sources()`,
     `startup_closure()`, `copy_startup_closure()`, and
     `nonconforming_column0_sources()` (contract-test support only). Raises on an
     empty closure and on a referenced lib missing under `lib_dir`.
  2. `tests/test_desync_state.py` — `copy_changelog()`'s private seven-name list
     replaced by `copy_startup_closure(LIB_SRC, lib_dir, roots=[changelog])`;
     `desync_state.py` retained as an explicit non-shell extra.
  3. `tests/test_shell_startup_closure.py` (new, 9 tests) — helper behavior on a
     synthetic tree (all three spellings + transitivity, indented-vs-column-0
     negative control, cycle termination, empty-closure raise, missing-lib raise,
     exact copy set, nonconforming reporting) and the real-tree format contract
     plus the `stale_lock.sh` regression pin.
  - Mitigation `pin_startup_source_contract`: the contract test and negative
    control in (3).
  - Mitigation `document_startup_source_contract`: the `source-on-startup`
    bullet in `aidocs/framework/shell_conventions.md` extended with the Python
    counterpart, the recognised shape, and what the derivation does not buy;
    plus a one-line pointer comment in each of the four scanned libs.

- **Deviations from plan:** None in substance. One implementation slip, caught at
  Step 8 review and corrected before commit: the four library comments were first
  written as three-line blocks that **restated** the "unconditional, column 0"
  rule. That reproduced the very duplication class this task removes — a later
  contract change could update the canonical rule and leave four stale copies.
  Reduced to a genuine one-line pointer naming the canonical doc and the scanner,
  as the plan had specified. The rule now has exactly one home.

- **Issues encountered:**
  - Symlinking the fixture's `lib/` (the `test_settings_commit_on_save.py`
    pattern) looked attractive but is unsafe here:
    `test_desync_state.py:260–264` deliberately overwrites `lib/desync_state.py`
    with a bad stub, which through a symlink would corrupt the real repository.
    Ruled out during planning.
  - A first design classified startup vs. lazy sources by lexical function-body
    depth. Probed against ordinary bash and rejected: it falsely flags the
    idiomatic top-level conditional
    `if [[ -r … ]]; then source "${SCRIPT_DIR}/lib/opt.sh"; fi`, which would turn
    a legitimate future edit into a suite-wide failure. Replaced by the
    convention-plus-contract-test design.

- **Key decisions:**
  - **Enforce the convention, never infer intent.** The derivation recognises one
    shape (unconditional, column 0, three spellings); the format-contract test
    keeps that shape honest across every scanned file. Both are plain line
    filters modelling no bash construct, so neither can misread a conditional, a
    brace group or a `case`.
  - **The claim is deliberately narrow.** An *indented* startup source is not
    derived; that case is documented, not coded. Recorded in the plan and in the
    module docstring so the limit is not mistaken for a bug.
  - `nonconforming_column0_sources()` never raises during a fixture build — it
    exists only for the contract test, so a convention break surfaces as one
    focused, named failure rather than as a cryptic fixture boot crash.

- **Verification performed:**
  - `tests/test_desync_state.py` — 10 passed (was 1 failed / 1 passed).
  - `tests/test_shell_startup_closure.py` — 9 passed.
  - **Load-bearing control:** neutering the derivation so it drops
    `stale_lock.sh` reproduced the *original* failure verbatim
    (`…/lib/stale_lock.sh: No such file or directory`) and also failed the new
    regression pin; probe reverted byte-identical.
  - **Contract control:** rewriting `lib/archive_utils.sh:25` to a column-0
    variable path made the contract test fail naming file, line and text —
    on a scanned file other than `task_utils.sh`; reverted.
  - Closure vs. the old hand list: superset — `+stale_lock.sh`, nothing dropped.
  - Shellcheck finding counts byte-identical before/after on all four commented
    libs (comments only).
  - Shell suites over the touched libs: `test_task_push.sh` 346,
    `test_task_git.sh` 105, `test_init_data.sh` 140, `test_zip_old.sh` 72 —
    663 passed, 0 failed.
  - **Full Python suite:** `PYTHON SUITE: PASSED (runner=pytest, exit=0)`,
    exit status 0 (not piped away), 7052 items. **Lane: parallel — pytest +
    xdist, `-n 4 --dist loadfile`** (auto-selected from machine load), with the
    four-module serial carve-out run separately. t1737's item #1 asked which
    lane ran: this is the parallel lane, the one t1729 was never verified on.

- **Upstream defects identified:** None
