---
Task: t1962_fold_content_carries_folded_ledgers_into_primary.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1962 — Fold content: keep folded ledgers inert and out of declared text; strip stdin frontmatter safely

## Context

`aitask_fold_content.sh` builds the merged body that callers pipe into
`aitask_update.sh --desc-file -` (a full body replacement, confirmed at
`aitask_update.sh:1966-2039`). There are two defects from downstream (thinking_app t295),
plus related ones found while tracing the consumers:

1. **Folded ledgers leak into the primary's ledgers.** Folded bodies are emitted
   verbatim (line 111). The parsers are **not section-scoped**:
   `ledger_block.parse_blocks` (behind `gate_ledger.parse_gate_run_blocks` and
   `note_inbox.parse`) matches any `^>\s*\*\*<icon> <ns>:<name>\*\*` line
   anywhere in the file. The folded task's gate runs and notes/receipts
   therefore become the primary's. The bare-heading readers
   (`aitask_query_files.sh inflight`, `note_inbox.has_section`) match too.
2. **`--primary-stdin` keeps frontmatter** (line 82), so piping a whole task
   file duplicates it into the body.
3. **Declared-text pollution.** Every declared-text consumer goes through the
   single choke point `plan_paths.cut_task_framework_sections`. That includes
   `task_body_text` → trail_gather, shadow_scope and parallel_admission_collect.
   It cuts the body at the first `## Inbox` / `## Gate Runs`. If folded history
   stays before the cut, merely demoted, the paths in its note bodies and gate
   logs (`src/unrelated.py`, `logs/old_review.md`) become task-declared files
   and cause false overlaps. *(User review finding.)*
4. **The primary's own ledger sections are not terminal after a fold.** Merged
   sections are appended after them. The cut then hides the merged
   requirements, and `gate_ledger`'s EOF append (which assumes `## Gate Runs`
   is terminal) lands new runs under `## Folded Tasks`.

**Invariant restored:** the merged body reads as
*declared text* → `## Folded History` (folded tasks' inert ledger history) →
the primary's own `## Inbox` / `## Gate Runs`. `## Folded History` becomes a
**third framework section** that the declared-text cut excludes.

## Changes

### 1. `.aitask-scripts/lib/plan_paths.py`

- Add the module constant `FOLDED_HISTORY_HEADER = "## Folded History"`. Its
  comment names its producer, `aitask_fold_content.sh`, and says why it is cut:
  the reference-only ledger history of folded tasks, whose paths are not this
  task's declarations.
- Add it to the `headers` tuple in `cut_task_framework_sections`, and update
  the docstring. All three declared-text consumers inherit the change, and no
  other cut site exists (grep confirmed).

### 2. `.aitask-scripts/aitask_fold_content.sh`

- **`extract_body`**: read stdin when called with no file argument (`"${1:--}"`).
- **`is_task_frontmatter`** (new awk predicate over stdin). It strips only a
  *recognizable, closed* task frontmatter block, and fails toward preserving
  text. It returns true only when all of these hold:
  - line 1 is exactly `---`;
  - a closing `---` line exists later;
  - every line between the delimiters is blank, `key: …`
    (`^[A-Za-z_][A-Za-z0-9_]*:([ \t]|$)`), indented, `- …`, or a YAML comment
    (`^#`), so a commented task file is still recognized;
  - at least one of them is a core task key (`^(status|priority|effort|issue_type):`).

  `--primary-stdin` reads stdin into `primary_raw`. If the predicate holds, it
  passes the text through `extract_body`; otherwise it keeps the text verbatim.
  So `---\nKeep this requirement.\n` and `---\nNote: x\n---\ntext` survive
  unchanged.
- **The framework-header ERE** `^##[ \t]+(Inbox|Gate Runs|Folded History)[ \t]*$`
  is defined once in the script, with a comment tying it to
  `plan_paths.cut_task_framework_sections`. An awk helper
  `split_fw <head|tail>` splits any body at the first matching line.
- **Primary**: `primary_decl` is emitted first, as today. `primary_tail` is
  emitted last.
- **Each folded body**:
  - Split it the same way.
  - The *declared* part goes under `## Merged from t<N>: <name>`, as today.
  - The *tail* (that task's own Inbox / Gate Runs / earlier Folded History) is
    collected as an entry for the new history section:
    ```
    ### t<N>: <name>

    <tail with every heading shifted down two levels (## Inbox → #### Inbox, capped at ######)>
    ```
  - Both parts pass through `neutralize_markers`. This inserts the existing
    `> | ` sentinel (the `note_render_body` convention in `aitask_note.sh`)
    into any line matching the any-namespace marker grammar
    `^>[ \t]*\*\*[^ \t]+[ \t]+[A-Za-z0-9_]+:[A-Za-z0-9_]+\*\*`. The markers are
    then inert to every parser, wherever they sit. Ordinary prose such as
    `> **Note:** …` does not match and is untouched.
- **Emitting `## Folded History`**, only when at least one folded tail is
  non-empty:
  - If `primary_tail` already has a `## Folded History` section (from an
    earlier fold), the new entries are injected at the end of that section.
    This uses awk over `primary_tail`, with the entries passed via `ENVIRON`
    rather than `-v`, so backslashes survive.
  - Otherwise the script emits `## Folded History`, a one-line reference-only
    note, and the entries, after `## Folded Tasks` and before
    `primary_tail`.
- When no ledger sections and no stdin frontmatter are present, the output is
  **byte-identical** to today (the existing tests pin this).
- Update the header comment and usage text.

### 3. `.claude/skills/task-workflow/task-fold-content.md`

Document the output structure (declared → merged → Folded Tasks → Folded History
→ primary ledgers), that `## Folded History` is excluded from declared text, and
that stdin strips only a recognizable task frontmatter block. It is a plain
`.md`; there is no `.j2` and no goldens.

### 4. Tests

**`tests/test_plan_paths.py` (`TaskBodyTests`)**
- `"## Folded History"` cuts the text.
- Extend `test_the_headers_are_the_owning_modules_constants` with
  `plan_paths.FOLDED_HISTORY_HEADER`.

**`tests/test_fold_content.sh`**

Fixtures:
- t13 is a folded task with a declared `src/required.py`, a `> **Note:** keep`
  line, an `## Inbox` holding a real-shaped `✉ note:t5` block (body line
  `> | see src/unrelated.py`) plus a `note:read` receipt, and a `## Gate Runs`
  holding `✅` and `❌` `gate:plan_approved` blocks (body `> Log: logs/old_review.md`).

Cases:
- `test_folded_ledgers_inert`:
  - no bare `## Gate Runs` / `## Inbox` line (the shell readers' EREs);
  - `#### Gate Runs` sits under `### t13: other` inside `## Folded History`;
  - the output contains `> | **✅ gate:plan_approved**`;
  - the real parsers report 0 gate runs and 0 note blocks (python with
    `sys.path` → `$PROJECT_DIR/.aitask-scripts/lib`);
  - `> **Note:** keep` survives verbatim.
- `test_folded_history_excluded_from_declared_text`:
  `plan_paths.extract(plan_paths.task_body_text(out))` contains
  `src/required.py` and contains neither `src/unrelated.py` nor
  `logs/old_review.md`.
- `test_primary_ledger_stays_terminal`: the primary has a body plus its own
  `## Inbox` and a one-run `## Gate Runs`. The order is Merged from <
  Folded Tasks < Folded History < Inbox < Gate Runs. The parser sees exactly 1
  gate run (the primary's), and the declared text includes the merged
  `src/required.py`.
- `test_refold_reuses_folded_history`: the primary already carries a
  `## Folded History` with a `### t9` entry. After folding t13 there is exactly
  one `## Folded History`, holding both entries, still before the primary's
  ledgers.
- `test_stdin_whole_task_file`: piping `cat` of the primary task file to
  `--primary-stdin` gives output equal to the positional form, with no
  `priority:` line.
- `test_stdin_commented_frontmatter`: the primary task file's frontmatter
  carries an unindented `# Metadata annotation` comment before
  `priority: medium` / `effort: low` / `status: Ready`. The stdin output
  equals the positional output and contains neither the comment nor
  `priority:`.
- `test_stdin_leading_rule_preserved`:
  - `---\nKeep this requirement.\n` is preserved in full;
  - `---\nNote: x\n---\nKeep y\n` is preserved in full (closed, but no core
    key);
  - in both cases the output starts with the stdin text.

### Post-phase (risk mitigations)

- **pin_framework_header_parity**: add `test_framework_header_parity` to
  `tests/test_fold_content.sh`. It reads `note_inbox.SECTION_HEADER`,
  `gate_ledger.SECTION_HEADER` and `plan_paths.FOLDED_HISTORY_HEADER` via
  python. For each header, it builds a body `x\n<header>\ny\n` with a folded
  file whose tail starts at that header, and asserts the script routed the
  tail into `## Folded History`, which proves the script's ERE recognizes
  every cut header. A header added on one side only then fails the test.

**Negative controls** (run by hand, not committed): each new case is run
against `git show HEAD:.aitask-scripts/aitask_fold_content.sh` (plus the
HEAD `plan_paths.py` for the declared-text case) and must fail.

## Verification

- `bash tests/test_fold_content.sh`
- `python3 -m pytest tests/test_plan_paths.py`, or unittest if pytest is absent
- `bash tests/test_auto_merge_file_ref.sh` and `bash tests/test_fold_mark.sh`
  (adjacent consumers)
- `bash tests/run_all_python_tests.sh --test-dir tests` is optional. Parallel
  admission, trail_gather and shadow_scope tests exercise `task_body_text`; run
  the matching `tests/test_*parallel_admission*`, `test_trail_gather*` and
  `test_shadow_scope*` modules.
- `shellcheck .aitask-scripts/aitask_fold_content.sh`

## Post-implementation

Step 9: commit the code (`bug: … (t1962)`), commit the plan, and archive.

## Risk

### Code-health risk: low
- A new framework-section header (`## Folded History`) extends a vocabulary
  that the bash script and `plan_paths.py` both encode · severity: low ·
  → mitigation: inline post-phase pin_framework_header_parity

### Planned mitigations
- timing: post-phase | name: pin_framework_header_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: framework-header vocabulary drift between aitask_fold_content.sh and plan_paths.py | desc: parity test proving the script's framework ERE recognizes every plan_paths cut header

### Goal-achievement risk: low
None identified. The real `gate_ledger`, `note_inbox` and `plan_paths`
functions check each defect against the merged output.
