---
Task: t1630_ls_filter_by_board_column.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1630 — `ait ls --boardcol`: filter tasks by board column

## Context

There is no way to ask `ait ls` for the tasks in a board column. Answering
"what's in `now`?" means hand-rolling a `sed`/`grep` sweep over every task
file's frontmatter. `aitask_ls.sh` does not read `boardcol` at all, and the
field is undocumented in its `--help` METADATA FORMAT list.

The column rule is already owned once, in `.aitask-scripts/lib/board_columns.py`
(`_column_of`), and already **duplicated once** in
`lib/work_report_gather.py:194-196`. A bash-side third copy is the thing to
avoid. This change adds the filter by *reusing* the seam and folds the existing
duplicate back onto it, so the rule ends up with exactly one implementation.

## Decisions

**D1 — Route the bash side through the Python seam; no bash-local `boardcol`
read, and therefore no drift guard.** The task permits a bash-local read "if
genuinely unavoidable for performance". Measured on this repo, it is not:

| | |
|---|---|
| `aitask_ls.sh 5` (today) | **4.99 s** |
| full-tree Python frontmatter scan (`aitask_work_report_gather.sh --list-columns`) | **0.22 s** |
| `aitask_board_column.sh list-columns` | **0.06 s** |

One lazy subprocess — spawned **only** when `--boardcol` is supplied — costs ~4%
of a run that already takes 5 s. It buys exact parity with the board, including
the case bash cannot get right without re-deriving YAML scalar typing: a
**non-string** `boardcol` must match no column. That case is reachable in
practice, not theoretical — `generate_col_id()` happily mints ids like `no`,
`on`, `y`, `off` from titles "No"/"On"/"Yes"/"Off", and PyYAML parses
`boardcol: no` as the boolean `False`.

**D2 — `--boardcol unordered` selects the Unsorted / Inbox lane, which is
*two* on-disk states: no `boardcol` field **and** an explicit
`boardcol: unordered`.** Both are reachable and both must match — this is the
board's own semantics, not a convenience:

- `column_of` maps a missing field to `UNORDERED_ID` **and** returns an explicit
  `"unordered"` unchanged, so the board draws both in the same lane.
- `move_task_to_column` (`board_columns.py:769`) writes
  `metadata["boardcol"] = col_id` unconditionally — moving a card *to* the
  Unsorted lane in `ait board` stamps an explicit `boardcol: unordered`. So does
  `ait update --boardcol unordered`, which `tests/test_boardcol_update.sh`
  already pins as a legal target.
- It is not hypothetical: **4 tasks in this repo carry an explicit
  `boardcol: unordered`** today (`t386`, `t417`, `t423`, `t456`).

Matching only the absent-field state would split one board lane in half and
silently omit those four. `--help`, the website docs and the test all state the
two-state rule explicitly, and the test asserts **both** states in one hit count
plus a negative on a columned task.

**D3 — An unknown column id is refused, naming the configured ids.** Reuse
`normalize_board_column()` (`lib/task_utils.sh:1002`), the validator
`ait update --boardcol` already uses. No second validator.

**D4 — Do NOT surface the column in the `-v` line.** Deliberate omission, not
an oversight:
- The `-v` shape is a documented parsing contract for `aitask-pick` Step 2a and
  is frozen in the rendered goldens for pick / pickrem / pickweb / resume across
  every profile × agent. A new optional segment means editing the `.j2`
  templates and regenerating that whole golden set — a large cross-cutting
  change for display sugar.
- It would also make the Python scan unconditional on every `-v` run, killing
  the laziness that makes D1 free. `ait ls -v` runs on every `/aitask-pick`.
- The stated problem ("what's in `now`?") is fully answered by the filter.

## Changes

### 1. `.aitask-scripts/lib/board_columns.py` — promote the rule, add a reader verb

- Rename `_column_of` → **`column_of`** and add it to `__all__`. It is now a
  genuine cross-module seam (two importers), not a module-private helper. Only
  two internal call sites (`:527` in `column_indices`, `:577` in `task_column`).
  No alias is kept — the old name was private, so there is no external contract.
- Add a `columns-of` subcommand to `main()`, alongside `list-columns`:

  ```
  columns-of --root R [--task-dir D]
      -> COLOF:<col_id>|<task path relative to R>   (one per task file)
      -> SCAN_OK                                     (terminal marker)
  ```

  - Globs **both levels** — `t*.md` and `t*/t*.md` — deliberately **wider**
    than `aitask_ls.sh`'s own `t*_*.md` / `t*_*_*.md`, so a map miss is
    structurally impossible. Children carry no `boardcol` today and the board
    does not render them; they resolve to `unordered`, which is the honest
    answer for `--all-levels` / `--children`.
  - Does **not** apply `_eligible()`. That predicate answers "does the board
    draw this card"; `ait ls` lists files the board would not draw, and every
    listed file needs a map row.
  - Unreadable / unparseable file → `{}` metadata → `column_of({})` →
    `unordered` (board parity: `Task.load()` swallows the failure).
  - `col_id` is FIRST because it can never contain `|` (ids are validated);
    the path is last, mirroring the "title LAST" rule in `list-columns`.
  - `SCAN_OK` is emitted last and only after the final row — same fail-closed
    contract as `aitask_gate.sh deps-blocking-scan`.
- `.aitask-scripts/aitask_board_column.sh` — add `columns-of` to the header
  comment's subcommand list. The script body is a bare `exec`; no code change.

### 2. `.aitask-scripts/lib/work_report_gather.py` — fold the duplicate away

At `:194-196`, replace the inline re-derivation

```python
col_raw = metadata.get("boardcol", UNORDERED_ID)
col_id = col_raw if isinstance(col_raw, str) else ""
```

with `col_id = column_of(metadata)`, adding `column_of` to the existing
`from board_columns import …` at `:76`. Drop the now-redundant comment. After
this the rule exists in exactly one place.

### 3. `.aitask-scripts/aitask_ls.sh` — the filter

Mirrors the `--type` filter end to end.

1. **Flag** — `BOARDCOL_FILTER=""` beside the other filter globals; a
   `--boardcol) BOARDCOL_FILTER="$2"; shift 2 ;;` arm in the parse loop.
2. **Validation** — one call to `normalize_board_column "$BOARDCOL_FILTER"`,
   placed **after** the `[ ! -d "$TASK_DIR" ]` check (not with the other
   value validations): the validator shells out to `list-columns --root .`,
   which reports `unsupported_layout` for a missing task dir — a worse message
   than the existing "Directory 'aitasks' not found".
3. **Lazy column map** — `build_boardcol_map`, placed immediately after
   `build_dep_blocking_map` and called **only** when `BOARDCOL_FILTER` is
   non-empty. Deliberately the same shape as its neighbour, for the same
   reasons documented there:
   - two parallel **indexed** arrays + linear scan (bash 3.2 has no `declare -A`;
     a `${var#*"$key"}` substring scan measured 15 s for 451 lookups);
   - the terminal `SCAN_OK` line required as the **exact final line** — its
     absence is its own state, never "no columns";
   - keys are squeezed with `${path//\/\///}` exactly as `parse_task_metadata`
     does for `current_task_file` (Mode 3 yields `aitasks//t9/t9_1_x.md`).

   Failure handling differs from the dep scan on purpose: the dep scan can
   degrade to "Blocked [unverified]", but a *filter* has no honest degraded
   mode — returning nothing is indistinguishable from an empty column, which is
   the exact defect D3 exists to prevent. So a failed scan **dies**.
4. **Filter block** in `process_task_file`, with the `--status` / `--labels` /
   `--type` blocks:

   ```bash
   if [[ -n "$BOARDCOL_FILTER" ]]; then
       local task_col
       task_col=$(lookup_boardcol "$current_task_file") \
           || die "board column unknown for '$current_task_file' (not in the column scan) — this is a framework defect; please report it."
       [[ "$task_col" == "$BOARDCOL_FILTER" ]] || return
   fi
   ```

   A map miss is **fatal**, not "excluded": it can only mean the two glob sets
   disagree, and silently shortening the list would hide that. (Structurally
   unreachable given the wider Python globs — this is the assertion that keeps
   it so.)
5. **`--help`** — add `--boardcol COL` under OPTIONS, stating the D2 two-state
   rule verbatim ("`unordered` selects the Unsorted / Inbox lane: tasks with no
   `boardcol:` field **and** tasks with an explicit `boardcol: unordered`") and
   that an unknown id is rejected. Add `boardcol: <column-id>` to the METADATA
   FORMAT block, which currently omits it, with the same absent-⇒-`unordered`
   note.

### 4. Docs — `website/content/docs/commands/task-management.md`

Add a `--boardcol COL` row to the `ait ls` options table (~`:107-111`), an
example line (~`:93-98`), and one prose paragraph covering D2 and D3. The D2
sentence must name **both** states — "`unordered` selects the Unsorted / Inbox
lane: tasks with no `boardcol` field *and* tasks explicitly moved there, which
`ait board` and `ait update --boardcol unordered` record as
`boardcol: unordered`" — since
`website/content/docs/tuis/board/reference.md:380,432` currently describes the
lane as "tasks without this field", which is only half of it. Add the missing
half there too, in the same change.

### 5. Tests — `tests/test_ls_boardcol_filter.sh` (new)

**Scaffolded**, not run against the real tree — modelled on
`tests/test_boardcol_update.sh`'s `setup_project()`, which is the closest prior
art (it already scaffolds `aitask_board_column.sh` plus the Python closure). The
scaffold is what makes the laziness guard possible at all: `aitask_ls.sh` reaches
the column seam through the **absolute** `"$SCRIPT_DIR/aitask_board_column.sh"`,
so only replacing that exact path can observe or block the call. A `PATH` shim
would never fire.

```bash
setup_project() {                       # per-test, in a fresh mktemp -d
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_ls.sh"           .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_board_column.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"      .aitask-scripts/lib/
    copy_lib_py_closure "$PWD" board_columns   # DERIVED, never a hand list
    …fixture task tree + metadata/task_types.txt…
}
```

Borrow `test_boardcol_update.sh`'s **scaffold probe** idea verbatim: a first
test that runs `aitask_board_column.sh list-columns` with stderr captured, so a
missing Python module fails as a named assertion instead of reading as a hang
(t1488). Capture output on every invocation rather than `>/dev/null 2>&1`.

`aitask_gate.sh` is deliberately **not** copied: the dep scan then degrades to
`dep_scan_state=failed` with a stderr warning and the listing still runs, which
is fine here — no fixture task declares `depends:`.

Otherwise it follows `tests/test_ls_display_and_filters.sh`'s conventions: test
bodies in the main shell (so the in-process counters are correct without the
file-backed opt-in) and every positive filter asserted by **hit count**, because
a silent zero-match otherwise reads as a clean pass.

Fixture A — stock columns (no `board_config.json`); fixture B — renamed columns
(`triage` / `doing` / `parked`, no `now`/`next`/`backlog`), which is the case
that catches a hardcoded `DEFAULT_ORDER`.

Cases:
1. `--boardcol now` returns exactly the `now` tasks — **cross-checked against
   `aitask_board_column.sh current-column` per task**, i.e. independent ground
   truth from the seam, not a hand-written expectation.
2. **D2, both states.** The fixture carries one task with **no** `boardcol` key
   and one with an explicit `boardcol: unordered`. `--boardcol unordered`
   returns **exactly 2** and includes both by name; a columned task is asserted
   absent. Then, as a negative control, a task moved into a real column via
   `aitask_board_column.sh move` drops out of the `unordered` hit count.
3. `--boardcol nosuchcol` **exits non-zero** and names the configured ids;
   asserted on the message, not just the status.
4. Fixture B: `--boardcol doing` filters correctly, **and** `--boardcol now`
   is refused there.
5. `boardcol: 42` matches nothing — not `--boardcol 42` (refused: not a
   configured id), not any real column, and specifically **not** `unordered`.
   This is the case a bash-local read gets wrong. Plus the sibling YAML-typing
   case `boardcol: no` in a fixture-B variant that configures a column literally
   named `no` (reachable — `generate_col_id("No")` returns `no`): the task must
   match **nothing**, exactly as the board renders it.
6. Composition: `--boardcol X --status all`, `--boardcol X -l <label>`,
   `--boardcol X --type bug`.
7. All four listing modes: default, `--all-levels`, `--tree`, `--children N`.
   This is what pins the glob agreement — a key mismatch dies loudly here
   rather than silently shortening a list.

**D4 (`-v` shape unchanged) is guarded by an existing test, not a new one.**
`tests/test_ls_display_and_filters.sh` already pins the *entire* verbose bracket
with `assert_eq` for four fixture tasks ("full display line (field order
pinned)"). Adding a segment to the `-v` line breaks it. That file must keep
passing **unmodified** — that is the executable D4 guard, and it is already in
CI. No before/after byte-diff test is written for it.

### Post-phase (risk mitigations)

Run after step 5, before the plan is considered complete.

- **`mode-matrix-key-agreement`** — extend `tests/test_ls_boardcol_filter.sh`
  case 7 into an explicit mode matrix: for each of the four listing modes
  (default, `--all-levels`, `--tree`, `--children N`), run `--boardcol` over a
  fixture containing a columned parent AND a columned child, and assert both a
  non-zero hit count and a **zero exit status**. A key mismatch between the
  Python glob set and `aitask_ls.sh`'s globs then fails as a named test rather
  than as a `die` in someone's listing. Include the negative control that proves
  the assertion can fail: a run whose column map is deliberately truncated (a
  stub `aitask_board_column.sh columns-of` emitting `SCAN_OK` with **one row
  omitted**) must exit non-zero and name the missing path.

- **`hot-path-laziness-guard`** — assert that `ait ls -v 99` *without*
  `--boardcol` never reaches the column seam. **Exact-path tripwire**, since the
  call site is `"$SCRIPT_DIR/aitask_board_column.sh"` and a `PATH` shim can
  never see it: in the scaffolded project, overwrite
  `$PWD/.aitask-scripts/aitask_board_column.sh` with

  ```bash
  #!/usr/bin/env bash
  printf '%s\n' "$*" >> "$AIT_TEST_COLSEAM_SENTINEL"
  exec "$AIT_TEST_REAL_BOARD_COLUMN_SH" "$@"
  ```

  (the real script is copied aside first, so the tripwire still returns correct
  results and the positive control below produces a real listing).
  - `ait ls -v 99` with no `--boardcol` → sentinel file **absent**.
  - **Positive control**, without which the above is vacuous: the same run with
    `--boardcol <col>` → sentinel present and containing **two** lines
    (`list-columns` from `normalize_board_column`, then `columns-of`). This is
    what proves the tripwire is wired to the real call site at all.

  Note this replaces the `-v` byte-diff idea from an earlier draft: copying
  `aitask_ls.sh` to `/tmp` and running it there cannot work — it derives
  `SCRIPT_DIR` from its own path and would source a non-existent
  `/tmp/lib/task_utils.sh`. D4 is guarded by `test_ls_display_and_filters.sh`
  instead (see §5).

## Verification

```bash
shellcheck .aitask-scripts/aitask_ls.sh
bash tests/test_ls_boardcol_filter.sh
bash tests/test_ls_display_and_filters.sh      # unchanged -v contract
bash tests/test_board_column_cli.sh            # new verb, existing four
bash tests/run_all_python_tests.sh --test-dir tests   # board_columns + work_report goldens
```

Live, against this repo (which already has renamed/extra columns —
`tests`, `bug_fixes`, `in_the_works`, `manual_verifications` alongside
`now`/`next`/`backlog`):

```bash
./ait ls --boardcol now -s all 99
./ait ls --boardcol unordered -s all 99
./ait ls --boardcol nope 99          # must FAIL, naming the eight valid ids
./ait ls --boardcol in_the_works -s all 99
```

D2 against live data — this repo has both states, so the two counts must add up:

```bash
./ait ls --boardcol unordered -s all 99 | wc -l            # parents only (Mode 4)
grep -L '^boardcol:'           aitasks/t*_*.md | wc -l     # absent-field parents
grep -l '^boardcol: unordered$' aitasks/t*_*.md | wc -l    # 4 today
```

Cross-check `--boardcol now` against the board's own answer for every hit:

```bash
for f in $(./ait ls --boardcol now -s all 99); do
  n=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
  ./.aitask-scripts/aitask_board_column.sh current-column --root . --task "$n"
done | grep -vc '|now$'      # must print 0
```

`-v` shape unchanged (D4): `bash tests/test_ls_display_and_filters.sh` must pass
with that file **unmodified** — it pins the full verbose bracket with
`assert_eq`. For an extra live diff, take the baseline from a **git worktree of
`HEAD`** (a copied script cannot resolve its own `lib/`, and never `git stash`):

```bash
git worktree add /tmp/ls_base HEAD
# Run HEAD's script FROM the live repo root: SCRIPT_DIR then resolves to
# /tmp/ls_base/.aitask-scripts (correct libs) while TASK_DIR=aitasks stays
# relative to cwd, so both sides read the SAME task tree.
/tmp/ls_base/.aitask-scripts/aitask_ls.sh -v 30 > /tmp/v_before.txt
diff /tmp/v_before.txt <(./ait ls -v 30)    # must be empty
git worktree remove /tmp/ls_base
```

Step 9 (Post-Implementation) handles cleanup, archival and merge.

## Risk

### Code-health risk: medium
- The new `build_boardcol_map` / `lookup_boardcol` pair introduces a second
  path-keyed scan map into `aitask_ls.sh`, and its keys must agree exactly with
  `parse_task_metadata`'s squeezed `current_task_file`. A subtle mismatch turns
  a normal listing into a hard `die` mid-run · severity: medium · → mitigation: inline post-phase `mode-matrix-key-agreement`
- `ait ls` is a hot path (every `/aitask-pick`, the TUIs). Adding a Python
  subprocess dependency to it creates a new failure mode: a broken `ait` venv
  turns `--boardcol` into a hard error. Correct, but new · severity: low · → mitigation: inline post-phase `hot-path-laziness-guard`
- Renaming `_column_of` → `column_of` touches a canonical seam · severity: low ·
  → mitigation: none (two internal call sites; the Python suite covers both)

### Planned mitigations

- name: `mode-matrix-key-agreement` · timing: inline post-phase · inline_risk: low · added_complexity: low · addresses: code-health / path-key mismatch between the Python glob set and `aitask_ls.sh`'s globs
- name: `hot-path-laziness-guard` · timing: inline post-phase · inline_risk: low · added_complexity: low · addresses: code-health / new Python-subprocess dependency on the `ait ls` hot path

### Goal-achievement risk: low
- The task names two explicit decisions and seven verification bullets; the plan
  addresses all of them. The one deviation is suggested-implementation item 5
  (`-v` surfacing), which the task asked to "decide deliberately" — D4 decides
  it, with the reason. `None otherwise identified.`
