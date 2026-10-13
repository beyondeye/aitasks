---
Task: t1966_repair_legacy_folded_layouts_requirements_after_ledgers.md
Base branch: main
Output branch: main
---

# t1966 — Repair legacy folded layouts: requirements that sit after the ledgers

## Context

The pre-t1962 fold script added `## Merged from t<N>` sections *after* the
primary's own `## Inbox` / `## Gate Runs`. Two readers treat everything from the
**first** framework header onward as ledger:

- `plan_paths.cut_task_framework_sections`, which is the single choke point for
  task-declared text (trail_gather, shadow_scope, parallel_admission_collect,
  and the drift-check test). The legacy requirements are therefore invisible to
  overlap and scope checks.
- `aitask_fold_content.sh` `split_fw`. On a re-fold it routes those
  requirements into the inert `## Folded History`.

A second shape exists too. `gate_ledger` appends new runs at EOF, so in a legacy
file live gate blocks can sit *under* `## Folded Tasks` or `## Merged from`. A
reader that only skips framework sections would count their `Log:` paths as
declared.

**Approach (one shared partition, two users).** Replace "truncate at the first
framework header" with a **stable partition** of the body, owned in Python:

- **framework** = every `## Inbox` / `## Gate Runs` / `## Folded History` section
  (its header up to the next `##` heading), **plus every live ledger marker
  block wherever it sits**. Block extent uses `ledger_block`'s own grammar.
- **declared** = everything else, in file order.

`cut_task_framework_sections` returns the declared part. This fixes every
declared-text consumer in place for legacy files, with no file rewrite. The
fold script uses the same partition for the primary and for each folded body,
so a fold writes the canonical layout:

> declared → `## Merged from` → `## Folded Tasks` → `## Folded History` → ledgers

That is Option A, with the reader fix underneath it.

**Option B (migration) is deliberately not done.** The reader fix makes legacy
files correct for every declared-text consumer, and the next fold canonicalizes
them. A one-shot rewrite would touch active task files on the shared data
branch while other sessions are running, and readers would see no gain. A scan
of the 150 active ledger-carrying tasks here found no legacy layout.

Ledger inertness is unchanged, and the partition has to keep two invariants.
Both come from the review, and both were reproduced with the real parsers.

- **Header spacing is the union of today's two matchers.** The fold script's
  awk accepts `##[ \t]+Name[ \t]*`. The Python cut accepts only the exact
  `## Name`, so today it already reads `##  Folded History` / `##\tInbox`
  bodies as declared (reproduced). The shared matcher accepts the awk spacing,
  which keeps fold behaviour and closes that reader gap.
- **Record boundaries survive.** `parse_blocks` stops a block only at a marker
  of its *own* namespace, a `##` header, or a non-`>` non-blank line. Removing
  the declared prose or heading between a gate block and a note block makes the
  gate block absorb the note marker and body into `raw_body_lines`
  (reproduced). So framework runs that were not adjacent in the body are joined
  with a block-terminating separator line. Parsed records, meaning their full
  contents (marker, fields, body lines) and their order, are identical to the
  whole body's. Only `line_number` shifts.

### Pre-phase (risk mitigations)

1. [characterize_active_corpus_declared_text] **Before editing anything**:
   - Write a scratchpad script. It imports `plan_paths` from a directory that
     holds `git show HEAD:` copies of `plan_paths.py`, `gate_ledger.py`,
     `note_inbox.py` and `ledger_block.py`.
   - For every `aitasks/**/t*.md` outside `aitasks/archived/`, plus every
     unbundled `aitasks/archived/**/t*.md`, it emits
     `<path>\t<" ".join(extract(task_body_text(raw)))>` into
     `baseline.tsv`.
   - After step 2 (`plan_paths.py`), re-run the same script against the working
     tree lib into `after.tsv`, then `diff baseline.tsv after.tsv`.
   - **Expected: no difference.** Explain every differing row in the Final
     Implementation Notes as a legacy layout (now correctly declared) or as a
     preamble marker block, CRLF header or spaced/tabbed header (an intended change). Stop and
     re-plan on any unexplained row.

## Implementation steps

### 1. `.aitask-scripts/lib/ledger_block.py` — `marker_block_mask(lines)`

Add a public function next to `parse_blocks`. It returns, for each line from
`str.splitlines(keepends=True)`, whether the line belongs to a live marker block
of **any** namespace (`_ANY_MARKER_RE`). The extent is exactly `parse_blocks`'
rule:

- the block starts at its marker line;
- it continues through `>`-prefixed lines and blank lines;
- it stops at the next marker, the next `SECTION_HEADER_RE` (`^##\s+`) line, or
  the first other line.

```python
def marker_block_mask(lines) -> list[bool]:
    mask = [False] * len(lines)
    idx = 0
    while idx < len(lines):
        if not _ANY_MARKER_RE.match(lines[idx]):
            idx += 1
            continue
        mask[idx] = True
        idx += 1
        while idx < len(lines):
            nxt = lines[idx]
            if _ANY_MARKER_RE.match(nxt) or SECTION_HEADER_RE.match(nxt):
                break
            if nxt.startswith(">") or not nxt.strip():
                mask[idx] = True
                idx += 1
                continue
            break
    return mask
```

Its docstring names the purpose (t1966: ledger records that EOF appends left
under a non-ledger heading) and the parity with `parse_blocks`.

### 2. `.aitask-scripts/lib/plan_paths.py` — partition, not truncation

- Add `split_task_framework_sections(body) -> tuple[str, str]` (declared,
  framework):
  - Split with `body.splitlines(keepends=True)`, the parsers' own line split,
    and compute `ledger_block.marker_block_mask` (lazy import, like the
    existing lazy `gate_ledger` / `note_inbox` imports).
  - **Header matcher (spacing-tolerant).** Take the names from the same three
    owning-module constants (`FOLDED_HISTORY_HEADER`,
    `note_inbox.SECTION_HEADER`, `gate_ledger.SECTION_HEADER`) by stripping
    their `## ` prefix, and assert that each constant starts with `## `. Build
    `^##[ \t]+(?:Inbox|Gate Runs|Folded History)[ \t]*\Z`. This is exactly the
    fold script's former `FRAMEWORK_HEADER_ERE`, so no heading either matcher
    accepted today becomes declared. Match it against each line's content
    without its terminator: `(line.splitlines() or [""])[0]`.
  - Walk the lines:
    - a framework header line → `in_section = True`;
    - otherwise any `ledger_block.SECTION_HEADER_RE` line →
      `in_section = False`;
    - a line goes to framework iff `in_section or mask[i]`, else to declared.
  - **Run separator (record boundaries).** Framework lines form maximal runs of
    consecutive framework lines. When a run follows an earlier one, and the
    lines between them went to declared, emit the module constant
    `FRAMEWORK_RUN_SEPARATOR = "<!-- ledger records below were separated by
    task text in the source -->\n"` between the two runs. Add a `"\n"` first
    if the previous run's last line has no terminator.
    - An HTML comment is non-blank and not `>`-prefixed, so `parse_blocks`
      ends any open block there.
    - It is not a `##` header, so it does not end the framework section in a
      later re-split.
    - Ledger sections already carry `<!-- … -->` lines, and the board merger's
      `_section_is_clean` allows them.
    - A canonical body has a single framework run, so its framework part stays
      byte-identical to today's tail.
    - A line equal to the separator is itself classed as framework (a third
      condition beside `in_section` and the mask). So a later re-split of a
      folded tail is a fixed point. Without that, the separator would be
      hoisted into declared text on the next fold. The in-memory prototype
      against the real parsers confirmed this on the gate→prose→note and
      note→prose→gate fixtures: records were equal, the re-split declared
      nothing, and the framework part was unchanged.
  - Return `(declared, framework)`. The declared part is the original declared
    lines in order. The framework part is the original framework lines in
    order, plus separators.
- `cut_task_framework_sections(body)` becomes
  `return split_task_framework_sections(body)[0]`. Rewrite its docstring and the
  `FOLDED_HISTORY_HEADER` comment to describe the partition. Cover:
  - sections are skipped, not truncated, so a legacy `## Merged from` after the
    ledgers is declared again;
  - live marker blocks are framework wherever they sit;
  - note bodies still cannot fake a header, because of the `> | ` prefix;
  - CRLF header lines are now recognized, matching the parsers'
    `splitlines`.
- Keep the module docstring's references; adjust any "cut at the first header"
  wording.

### 3. `.aitask-scripts/aitask_fold_content.sh` — use the shared partition

- Remove `FRAMEWORK_HEADER_ERE` and the awk `split_fw`. Add
  `split_fw <decl_file> <tail_file>`, which reads the body on stdin:
  - **Fast path, no Python:** the text contains none of the substrings
    `Inbox`, `Gate Runs`, `Folded History` or `**`. It then cannot hold a
    framework header (with any spacing) or a marker, so the whole text is
    declared. The check matches the header **names**, not `## Name`, so it is
    a strict superset of the spacing-tolerant matcher. The parity test pins it
    for every module header and every spacing variant (see Tests).
  - **Otherwise:** `[[ -n "$PY" ]] || die …` (same message style as
    `neutralize_markers`). Then run a `$PY -c` snippet: insert the lib dir, call
    `plan_paths.split_task_framework_sections`, and write both parts to the two
    files with `surrogateescape`, as `neutralize_markers` does.
- Replace the single-file `out_file` with a `work_dir=$(mktemp -d …)`, using
  `trap 'rm -rf "$work_dir"' EXIT`. Output buffering stays as is: `cat` the
  output only at the end.
- Primary: pipe `$primary_body` into `split_fw "$work_dir/p_decl"
  "$work_dir/p_tail"`. Read the two variables from those files. The rest of the
  primary flow (`split_history` before/after, Folded History injection,
  primary tail last) is unchanged.
- Each folded file: `extract_body "$f" | split_fw "$work_dir/f_decl"
  "$work_dir/f_tail"`. Then:
  - `neutralize_markers < f_decl` under `## Merged from`;
  - `tail=$(shift_headings < f_tail | neutralize_markers)` for the history
    entry.

  `set -euo pipefail` already makes a failing `split_fw` abort with empty
  stdout.
- Update the header comment. The declared/framework split is now
  `plan_paths.split_task_framework_sections`, so a legacy body's sections after
  the ledgers are hoisted back into declared text, and EOF-appended ledger
  blocks stay with the ledgers.

### 4. Docs and consumer docstrings

- `.claude/skills/task-workflow/task-fold-content.md`: state that the
  declared/ledger split is the declared-text reader's own partition
  (`plan_paths.split_task_framework_sections`). Legacy bodies whose
  `## Merged from` sections follow their ledgers are rewritten into the
  canonical order. Python is needed when a body names a framework header or
  contains `**`. Write current-state prose only. This file exists only in
  `.claude/`, so no other agent tree needs a port.
- `.aitask-scripts/lib/trail_gather.py:829`, and any other docstring found by
  `grep -rn "first \`## Inbox\`\|cut at the first" .aitask-scripts/lib`: change
  "cut at the first `## Inbox` / `## Gate Runs`" to "framework sections and
  ledger blocks removed".

### 5. Tests

- `tests/test_ledger_block_neutralize.py` (or the closest ledger_block test
  module): `marker_block_mask` parity with `parse_blocks`. Use a corpus that
  mixes gate and note blocks, blank lines inside blocks, a block ended by `##`,
  a block ended by prose, and a neutralized `> | **` line. The masked marker
  lines must equal the union of the `parse_blocks(...).line_number` values for
  both namespaces. Every masked non-marker line must be `>`-prefixed or blank.
- `tests/test_plan_paths.py` `TaskBodyTests`. All existing cases must still
  pass unchanged. New cases:
  - legacy: `keep a/b.py\n## Inbox\n> | x/y.py\n## Merged from t3: old\nsrc/older.py\n`
    → extract == `["a/b.py", "src/older.py"]`;
  - an EOF gate block under a displaced `## Folded Tasks` (its `> Log:
    logs/z.md` field) is **not** declared;
  - a live marker block in the preamble is not declared;
  - **Record-content invariant** (helper `records(text)` = the list of
    `(name, icon, fields, body_fields, raw_marker, raw_body_lines)` from
    `gate_ledger.parse_gate_run_blocks` and from `note_inbox.parse`):
    `records(framework) == records(body)` on each fixture below. It also
    checks that `split_task_framework_sections(framework)` is a fixed point
    (a re-split moves nothing to declared). Fixtures:
    - gate block, then declared prose, then note block;
    - note block, then declared prose, then gate block;
    - `## Gate Runs` with a gate block, then a removed `## Merged from t3`
      heading with text, then an EOF gate block and a note block, both
      mixed-namespace and same-namespace;
    - a canonical body (one framework run), whose framework part is
      byte-identical to the old tail (no separator).
  - the declared part of every fixture has no live markers;
  - **heading spacing**: `##  Folded History`, `##\tFolded History`,
    `##  Inbox`, `##\tGate Runs` and `## Inbox \t` headers, each followed by a
    historical path (`old/hist.py`), are **not** declared. `## Inbox zero` and
    `### Inbox` stay declared (the existing case);
  - a CRLF `## Inbox\r\n` header is recognized.
- `tests/test_fold_content.sh`:
  - `setup_project` replaces the bare `ledger_block.py` copy with
    `copy_lib_py_closure "$PWD" plan_paths`, which pulls in `gate_ledger`,
    `note_inbox` and `ledger_block` (closure, not a hand list).
  - **`test_legacy_folded_source_requirements_declared`** (the task's
    fixture): a folded source whose `## Inbox` (a note naming
    `src/unrelated.py`) is followed by `## Merged from t3: older` naming
    `src/older.py`. After the fold:
    - `src/older.py` ∈ `extract(task_body_text(out))`;
    - `src/unrelated.py` ∉ it;
    - `note_inbox.parse(out)` and `gate_ledger.parse_gate_run_blocks(out)`
      count only the primary's records;
    - the `## Merged from t3` heading precedes `## Folded Tasks`.
  - **`test_legacy_primary_canonicalized`**: a primary laid out as
    `declared / ## Gate Runs (attempt 1) / ## Merged from t3 (src/older.py) /
    ## Folded Tasks / EOF gate block (attempt 2, Log: logs/late.md)`. After
    folding another task:
    - `src/older.py` is declared and `logs/late.md` is not;
    - the gate and note records parsed from the output equal those parsed
      from the input primary in **full content** (`raw_marker`,
      `raw_body_lines`, fields) and order, compared through `py_lib`.
      `derive_gate_runs` therefore reports the attempt-2 status;
    - `## Gate Runs` comes after every `## Merged from` / `## Folded Tasks`
      line, and no non-framework `## ` heading follows it.
  - **`test_legacy_mixed_namespace_boundaries`**: a primary with a gate
    block, then declared prose, then a note block, and the mirror case of a
    folded source. Records in the output keep their full contents. In
    particular, no gate block's `raw_body_lines` holds a `note:` marker.
  - `test_framework_header_parity`: keep it (its folded body has no `**`, so
    it pins the fast-path substrings for every module header). Extend its
    loop: for each module header, also try the `##  <name>` and
    `##\t<name>` variants, each with a historical path. Each variant must be
    routed to `## Folded History` and cut from declared text. Update its
    comment to name the precheck.
- **Red proof (never stash):** extract the HEAD versions of `plan_paths.py`
  and `aitask_fold_content.sh` with `git show HEAD:<path>` into the scratchpad.
  Run the new legacy assertions against them and confirm they fail. Then
  confirm they pass on the working tree.

## Verification

- `python3 -m pytest tests/test_plan_paths.py tests/test_ledger_block_neutralize.py tests/test_trail_gather.py tests/test_parallel_admission_collect.py`
  (or `unittest`)
- `bash tests/test_fold_content.sh`, `bash tests/test_fold_mark.sh`,
  `bash tests/test_auto_merge_file_ref.sh`, `bash tests/test_shadow_scope.sh`,
  `bash tests/test_remote_drift_check.sh`
- `bash tests/run_all_python_tests.sh`, reading only the final verdict line,
  with `set -o pipefail` if piped
- `shellcheck .aitask-scripts/aitask_fold_content.sh`

## Step 9 (Post-Implementation)

Current-branch mode: no merge. Commit code (`bug: … (t1966)`) and the plan
separately, then archive via `aitask_archive.sh 1966`.

## Risk

### Code-health risk: low
- (Review finding, addressed in-plan) The partition could have narrowed header recognition below the awk matcher's `##[ \t]+` spacing, or merged ledger records across a removed separator. Both are fixed by the spacing-tolerant matcher and `FRAMEWORK_RUN_SEPARATOR`, and pinned by the spacing and record-content fixtures. · severity: low · → mitigation: none
- The partition replaces the single declared-text choke point used by trail_gather, shadow_scope and parallel_admission_collect. Preamble marker-block removal and CRLF header recognition could silently change declared text for canonical tasks. · severity: low (residual — addressed by inline pre-phase characterize_active_corpus_declared_text) · → mitigation: inline pre-phase characterize_active_corpus_declared_text
- `aitask_fold_content.sh` now needs Python for any body that names a framework header (not only bodies containing `**`). The fold pipeline (`aitask_fold_mark.sh`) already requires Python, and plain bodies keep the no-Python fast path. · severity: low · → mitigation: none

### Goal-achievement risk: low
- Prose placed after a ledger header with no `## ` heading of its own stays ledger-side. It cannot be told apart from ledger body by design, so only headed sections are hoisted. · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_active_corpus_declared_text | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: partition silently changing declared text for canonical tasks | desc: Snapshot extract(task_body_text) over all active/unbundled task files with HEAD plan_paths, diff after the change, explain every row

## Post-Review Changes

### Change Request 1 (2026-10-13 13:05)
- **Requested by user:** Blocking review finding (CONFIRMED). `split_history` emitted an existing `## Folded History` before the rest of the primary's tail. Live records that the partition moved out of the preamble therefore landed after an EOF record appended inside the history section, which reversed their order: `[1 pass, 2 fail]` became `[2 fail, 1 pass]` and `derive_gate_runs` reported `pass`.
- **Changes made:**
  - Added `plan_paths.split_folded_history(framework) -> (history, live)`. History is the inert `## Folded History` text, minus any live blocks inside it. Live is every other section and record, in order, with separators recomputed.
  - Live text that does not open with a `##` header gets a leading separator, so a stray record never reads as part of the preceding section.
  - Separator lines are always dropped and recomputed, so repeated re-folds are stable.
  - The shared `_join_runs` helper now builds both framework parts.
  - `aitask_fold_content.sh`: `split_fw` takes an optional third file. The primary is split into declared / history / live, and the awk `split_history` and `FOLDED_HISTORY_ERE` are removed. Assembly emits history first, then live.
  - Reproduced the bug before the fix, and confirmed `[1, 2] → fail` after it, stable over 3 re-folds with 2 separators each time.
- **Files affected:** `.aitask-scripts/lib/plan_paths.py`, `.aitask-scripts/aitask_fold_content.sh`, `tests/test_fold_content.sh` (`test_live_records_keep_order_across_folded_history`, including the re-fold stability check), `tests/test_plan_paths.py` (`test_folded_history_split_keeps_live_records`), `.claude/skills/task-workflow/task-fold-content.md`.

## Final Implementation Notes
- **Actual work done:**
  - `ledger_block.marker_block_mask` marks the lines of live marker blocks of any namespace, using the same block extent as `parse_blocks`.
  - `plan_paths.split_task_framework_sections` is a partition, not a truncation:
    - Framework is the `## Inbox` / `## Gate Runs` / `## Folded History` sections (any spacing after `##`, CRLF-aware) plus every live record wherever it sits. Everything else is declared.
    - Non-adjacent framework runs are joined by `FRAMEWORK_RUN_SEPARATOR`, which is itself framework, so a re-split is a fixed point.
    - `cut_task_framework_sections` returns its declared part.
  - `plan_paths.split_folded_history` splits a framework part into inert history and live text (order kept, separators recomputed, a leading separator when live opens with a record).
  - `aitask_fold_content.sh` uses both splits through `split_fw` (python only when a body names a framework section or holds `**`). Assembly is declared → merged → Folded Tasks → Folded History → live. The awk split, `split_history` and both EREs are removed.
  - Docs: `task-fold-content.md`, `parallel-assessment.md` (agents now read past ledgers to a trailing `## Merged from`), and the `trail_gather.py` docstring.
- **Deviations from plan:**
  - Plan-review findings were folded into the plan before approval: spacing-tolerant header matcher, run separator, record-content fixtures.
  - The "add a newline before the separator" branch was dropped as unreachable, since only the last line can lack a terminator.
  - Change Request 1 added `split_folded_history`, because `split_history` reordered live records around an existing Folded History.
  - The fold-script half of the red proof against HEAD was not run: a safety check blocked running scripts whose cleanup trap uses `rm`. The reader half (HEAD fails all 3 legacy cases) and the CR1 reproduction (`[2,1] pass` before the fix) are recorded instead.
- **Issues encountered:**
  - Two test fixtures were wrong and were corrected:
    - Prose under `## Inbox` with no heading of its own is ledger by design.
    - The mask parity corpus had a gate block adjacent to a note block, and a single-namespace parse absorbs that note. This is the very adjacency the separator prevents.
  - The corpus diff later showed rows that differed only because other sessions archived or created tasks. A fresh HEAD baseline over the current corpus is identical.
- **Key decisions:**
  - No migration helper (Option B). The reader handles legacy layouts in place, the next fold canonicalizes them, and no active task here has the legacy layout.
  - Header spacing is the union of both former matchers.
  - Live-record content and order are the invariant, checked with the real parsers on full record tuples.
- **Upstream defects identified:** None
