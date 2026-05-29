---
Task: t832_10_aitask_create_interactive_cross_repo.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md
Worktree: aiwork/t832_10_aitask_create_interactive_cross_repo
Branch: aitask/t832_10_aitask_create_interactive_cross_repo
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-28 17:27
---

# Plan: `xdeprepo` + cross-repo refs in `aitask_create.sh` interactive mode (t832_10)

## Scope (rescoped 2026-05-28)

This task is narrowly scoped to **the `ait create` interactive (fzf)
bash flow**. It adds:

1. **`xdeprepo` declaration** — picking a registered sibling project
   sets the new task's `xdeprepo:` frontmatter field.
2. **Cross-repo archived task references** — when a project has been
   picked, the existing "Add archived task reference" menu gains a
   second variant that lists archived tasks from the cross-repo
   project and inserts them inline in the description using the
   documented `<project>#<id>` notation.
3. **Cross-repo file references** — when a project has been picked,
   the existing "Add file reference" menu gains a second variant
   that runs the fzf file walker rooted in the cross-repo project
   and inserts the path inline using `<project>:<relative/path>`
   notation.

The companion changes to the `aitask-create` AI skill (`SKILL.md`)
are **deferred to a separate non-sibling follow-up task** to be
created after this lands. Cross-repo `xdeps:` (actual cross-repo
dependencies) remain batch-only — interactive collection of `xdeps`
is out of scope.

## Goal

When a user runs `ait create` (no flags, interactive mode), the
fzf-driven flow:

- Offers a fzf prompt to declare the task as cross-repo by picking
  a registered sibling project.
- If a project is picked, gates two additional sub-menu items on
  the file/task reference loop:
  - "Add cross-repo archived task reference (from `<name>`)" →
    inserts `<name>#<id>` inline in the description.
  - "Add cross-repo file reference (from `<name>`)" → opens fzf
    rooted at the cross-repo project's path, inserts
    `<name>:<relative/path>` inline in the description.
- Writes `xdeprepo: <name>` to the draft frontmatter.

Result: a draft with `xdeprepo: <name>` and a description body
that may contain cross-repo task / file references in the
documented notation. No `xdeps:` line is written by the interactive
flow.

## Architectural decisions (locked)

1. **Trigger source is `xdeprepo` metadata only.** Interactive flow
   populates it via the project picker.
2. **`xdeprepo` is scalar:** exactly one cross-repo project per
   task. fzf single-select.
3. **`xdeps:` collection in interactive mode is out of scope.**
   Users who need explicit cross-repo deps continue to use
   `--batch --xdeps <csv> --xdeprepo <name>`.
4. **Validator must allow `xdeprepo` alone** (intent-only). The
   only remaining failure case is `xdeps` without `xdeprepo`.
   Load-bearing for the metadata-only trigger contract.
5. **Cross-repo references are inline-only.** Following the
   precedent of the local "Add archived task reference" flow
   (which is deliberately NOT added to `file_references:`),
   cross-repo task refs AND cross-repo file refs stay in the
   description body only — they do NOT pollute the
   `file_references:` frontmatter field. Downstream consumers
   (`aitask_explain_context.sh`, etc.) are not yet cross-repo
   aware; keeping refs inline avoids leaking unresolvable
   project-prefixed entries into a structured field.
6. **Notation:** uses the conventions already documented in
   `aidocs/cross_repo_references.md`:
   - Task IDs: `<project>#<id>` (e.g., `aitasks_mobile#42_3`).
   - File paths (new in this task): `<project>:<relative/path>`.
     The colon separator is unambiguous because file paths cannot
     contain `:` and project names cannot contain `:`. Document the
     file form in `aidocs/cross_repo_references.md` in the same PR.
7. **The `aitask-create` AI skill is out of scope.** Follow-up
   non-sibling top-level task.

## Implementation steps

### Step 1 — Add `list` subcommand to `aitask_project_resolve.sh`

Emit one line per registered project for machine consumption by the
fzf prompts:

    PROJECT:<name>:<path>:<status>

where `<status>` ∈ {`RESOLVED`, `STALE`}. Iterate the per-user
registry via the existing `index_lookup_path`-style awk parser;
classify each entry by calling the existing
`path_is_aitasks_project` predicate.

No whitelisting needed: called from `aitask_create.sh`, not from a
skill. (Per "whitelist only skill-invoked helpers".)

### Step 2 — Add `select_xdeprepo()` helper in `aitask_create.sh`

Mirror the existing `select_priority` / `select_effort` /
`select_status` helpers. Enumerate via `aitask_project_resolve.sh
list`, build fzf options:

```
None (single-repo)
<resolved_name_1>
<resolved_name_2>
…
```

(STALE entries are skipped with a one-line warn to stderr.)

Echo the chosen project name to stdout (empty for "None").

### Step 3 — Wire `select_xdeprepo()` into `main()`

In `main()`, after `select_dependencies` (current line ~1911) and
before `get_task_name`, call `select_xdeprepo` and store the
result in a local `xdeprepo` variable. If the registry is empty,
the helper short-circuits to "None" without showing the prompt.

### Step 4 — Cross-repo task references in `get_task_definition()`

Modify the reference loop (around line 1188) to gate two extra
menu items on a non-empty `xdeprepo` argument passed in from
`main()`:

- Pass `xdeprepo` into `get_task_definition` as a new argument.
- When non-empty, extend the menu options string to include:
  - "Add cross-repo archived task reference (from `<name>`)"
  - "Add cross-repo file reference (from `<name>`)"

#### Step 4a — `select_cross_repo_archived_task_ref(xdeprepo)`

Mirror of `select_archived_task_ref` (line 1088) using
`aitask_query_files.sh --project <xdeprepo> recent-archived 999`.
For each `RECENT_ARCHIVED:<path>|<completed_at>|<issue_type>|<task_name>`
line, parse the task ID out of the basename (e.g.,
`t832/t832_1_foo.md` → `832_1`) and present in the fzf list as:

    832_1    [<completed_at>] <task_name> (<issue_type>)

On selection, emit the cross-repo notation:
`<xdeprepo>#<id>` (e.g., `aitasks_mobile#42_3`).

That string is what gets appended inline to `task_desc` — the
same insertion path as the existing archived-task-ref code.

#### Step 4b — Cross-repo file picker

Resolve the cross-repo project root once via
`aitask_project_resolve.sh <xdeprepo>` → `RESOLVED:<root>`. Then
run the fzf walker rooted in that path:

```bash
cd "<root>" && fzf --prompt="Select file from <xdeprepo>: " \
    --height=20 --preview 'head -50 {}' \
    --walker=file,hidden --walker-skip=.git,node_modules,build < /dev/tty
```

On selection, compose `<xdeprepo>:<relative/path>` (the path is
already relative to the project root because we `cd`'d into it).
Append inline to `task_desc`.

**NOT added to `all_file_refs`** (consistent with cross-repo
archived task refs and with the existing local archived-task-ref
precedent).

### Step 5 — Plumb `xdeprepo` through `create_draft_file()`

`create_draft_file()` currently consults `BATCH_XDEPS:-` /
`BATCH_XDEPREPO:-` globals to decide whether to emit the YAML
lines. The interactive path never sets these globals, so:

- Add a new positional parameter `local xdeprepo_arg="${17:-}"`
  (one slot after the current last param `verifies` at slot 16,
  if any — confirm exact slot during implementation; insert
  immediately after `verifies`).
- In the YAML-emission block, write `xdeprepo: <value>` when the
  parameter is set, **independently of `xdeps`**.

#### Step 5a — Independent emission of `xdeps:` and `xdeprepo:`

Today the script emits both lines together when `BATCH_XDEPS` is
non-empty. Replace with two independent conditionals in all
**3 emit sites** (`create_draft_file`, `finalize_draft`,
`run_batch_mode`):

    if [[ -n "${xdeps_value:-}" ]]; then
        echo "xdeps: $xdeps_yaml"
    fi
    if [[ -n "${xdeprepo_value:-}" ]]; then
        echo "xdeprepo: $xdeprepo_value"
    fi

### Step 6 — Relax `validate_xdeps_pair` in `lib/task_utils.sh`

Currently both-or-neither. Change to:

- `xdeprepo` alone → OK (intent-only mode).
- `xdeps` alone → still dies.
- Both set → validate as today.

Update the die message:
`die "--xdeps requires --xdeprepo (xdeps without a project context cannot be resolved)."`

### Step 7 — Wire interactive `xdeprepo` into `create_draft_file` call

In `main()`'s call to `create_draft_file` (around line 1948), pass
the interactively-selected `xdeprepo` as the new positional.

### Step 8 — Print `xdeprepo` in the summary block

In the `main()` summary block (around line 1957):

    echo "  Cross-repo:    ${xdeprepo:-None}"

### Step 9 — Document the file-ref notation

Append a short paragraph to `aidocs/cross_repo_references.md`
under "Cross-repo task ID notation" introducing the symmetric
file-path form `<project>:<relative/path>`. Keep it brief
(matches the prose style already there).

### Step 10 — Tests

- **`tests/test_project_resolve_list.sh`** (new): scaffold a fake
  registry with one resolvable and one stale entry; run
  `aitask_project_resolve.sh list`; assert one `RESOLVED` and one
  `STALE` line.

- **`tests/test_xdeps_validation.sh`** (update): change Case 2
  (`--xdeprepo` alone) to expect **success** and assert the draft
  contains `xdeprepo:` without `xdeps:`. Case 1 (`--xdeps` alone)
  still fails — keep that.

- **`tests/test_aitask_create_xdeprepo_alone.sh`** (new): drive
  batch mode (interactive isn't shell-testable) with `--xdeprepo
  <name>` only; assert the draft contains `xdeprepo: <name>` and
  NO `xdeps:` line.

The interactive-only behaviors (the `select_xdeprepo` fzf prompt,
the cross-repo task/file ref menus) are exercised via manual
verification (Step 11). The reusable building blocks (the `list`
subcommand, the validator relaxation, the YAML emission, and the
batch surface) all get automated coverage.

### Step 11 — Manual verification (smoke)

1. Verify the local registry has at least one resolvable cross-repo
   entry: `ait projects list`. Register one if needed.
2. Run `ait create` interactively. Walk through the prompts;
   confirm the new "Cross-repo project" prompt appears after
   dependencies/labels. Pick a registered project.
3. In the file/task reference loop, confirm both new menu items
   appear: "Add cross-repo archived task reference (from
   `<name>`)" and "Add cross-repo file reference (from
   `<name>`)".
4. Select an archived task from the cross-repo project; confirm
   `<name>#<id>` is appended to the description.
5. Select a file from the cross-repo project; confirm
   `<name>:<relative/path>` is appended to the description.
6. Inspect the resulting draft file under `aitasks/new/`:
   - `xdeprepo: <name>` present in frontmatter.
   - NO `xdeps:` line.
   - `file_references:` field (if any) contains ONLY local file
     paths — no cross-repo entries.
   - Description body contains the cross-repo refs in the
     documented notation.
7. Finalize the draft. Confirm the final task file under
   `aitasks/` keeps the same frontmatter.
8. Regression: re-run with "None (single-repo)" — confirm draft
   has NO `xdeprepo:`/`xdeps:` lines and the cross-repo menu items
   are NOT offered.

## Verification

1. `bash tests/test_project_resolve_list.sh` — passes.
2. `bash tests/test_xdeps_validation.sh` — passes with updated
   Case 2.
3. `bash tests/test_aitask_create_xdeprepo_alone.sh` — passes.
4. Regression: `bash tests/test_xdeps_parser.sh`,
   `tests/test_xdeps_fold_warn.sh`,
   `tests/test_query_files_cross_repo.sh`,
   `tests/test_create_project_flag.sh`,
   `tests/test_update_cross_repo.sh` — none regress.
5. `shellcheck .aitask-scripts/aitask_project_resolve.sh
   .aitask-scripts/aitask_create.sh
   .aitask-scripts/lib/task_utils.sh` clean.
6. `./.aitask-scripts/aitask_skill_verify.sh` — PASS (defensive;
   no skills touched).
7. Manual smoke per Step 11.

## Out of scope (this task)

- Any change to `.claude/skills/aitask-create/SKILL.md` or the
  Codex / OpenCode equivalents — deferred follow-up.
- Cross-repo deps (`xdeps:`) selection inside the interactive
  flow — batch-only for now.
- Labels-union or cross-repo label awareness.
- `aitask_query_files.sh labels` subcommand.
- Parsers / consumers for `<project>#<id>` and
  `<project>:<path>` notation in downstream tooling
  (`aitask_explain_context.sh`, board, etc.).
- aitask-explore cross-repo integration → t832_11.
- TUI display of `xdeprepo` in `ait board` → t832_8.
- N-way (≥3) cross-repo plans.

## Follow-up (to be created after this lands)

A new top-level (non-sibling) task to mirror this behaviour into
the `aitask-create` AI skill: cross-repo question, project picker,
cross-repo task/file references, batch-call wiring, plus the
corresponding helper additions and whitelisting.

## Notes for sibling tasks

- The validator's `xdeprepo`-without-`xdeps` allowance landed
  here is load-bearing for t832_5 (its trigger fires on `xdeprepo`
  alone) and the future skill follow-up.
- The `aitask_project_resolve.sh list` subcommand landed here is
  reusable by the skill follow-up and by `ait board` cross-repo
  display (t832_8).
- The `<project>:<path>` file-ref notation introduced here joins
  the existing `<project>#<id>` task-ref notation as the second
  cross-repo authoring convention. Future tooling that parses
  task descriptions can extend the existing regex catalogue in
  `aidocs/cross_repo_references.md`.

## Post-Review Changes

### Change Request 1 (2026-05-29)

- **Requested by user:** Ensure the t832_5 sibling task (which writes
  the cross-repo planning procedure consumed by `/aitask-pick` on
  `xdeprepo`-tagged tasks) knows how to resolve the
  `<project>#<id>` and `<project>:<relative/path>` notations that
  this task introduces into task descriptions.
- **Changes made:** Added a "Cross-repo reference resolution"
  subsection to both `aitasks/t832/t832_5_*.md` (task file, under
  Notes for sibling tasks) and
  `aiplans/p832/p832_5_*.md` (plan file, inside Step 2 — Paired
  exploration). The note specifies:
  - `<project>#<id>` → resolve via `aitask_query_files.sh --project
    <project> task-file <id>` and inline the resolved title into
    the cross-repo subagent's question.
  - `<project>:<relative/path>` → resolve root via
    `aitask_project_resolve.sh <project>`, include the file in the
    cross-repo subagent's reading list.
  - Both resolved during exploration, not during trigger detection
    (the trigger remains `xdeprepo` metadata-only per the
    architectural decision).
- **Files affected:**
  - `aitasks/t832/t832_5_parallel_cross_repo_planning_procedure.md`
  - `aiplans/p832/p832_5_parallel_cross_repo_planning_procedure.md`

## Final Implementation Notes

- **Actual work done:** Implemented per the rescoped plan: added
  `list` subcommand to `aitask_project_resolve.sh`; added
  `select_xdeprepo()` and `select_cross_repo_archived_task_ref()`
  helpers to `aitask_create.sh`; extended `get_task_definition`'s
  reference loop with two new menu items gated on a non-empty
  `xdeprepo`; threaded `xdeprepo` as a new positional through
  `create_draft_file` (slot 17, after `verifies`); split the
  `xdeps:` / `xdeprepo:` YAML emission into independent conditionals
  at all 3 sites in `aitask_create.sh` and the 1 site in
  `aitask_update.sh`; relaxed `validate_xdeps_pair` to allow
  `xdeprepo` alone (intent-only mode); printed the chosen
  cross-repo project in the post-create summary; documented the new
  `<project>:<relative/path>` file-ref notation in
  `aidocs/cross_repo_references.md`. Added three tests
  (`test_project_resolve_list.sh`,
  `test_aitask_create_xdeprepo_alone.sh`, plus updates to
  `test_xdeps_validation.sh` Case 2 and
  `test_aitask_update_xdeps.sh` Cases 1/2/8/9).
- **Deviations from plan:** None of substance. The plan called for
  updating `aitask_create.sh` 3 emit sites; `aitask_update.sh`
  needed a parallel update (1 emit site) to honour the same
  intent-only semantics — surfaced naturally during regression
  runs.
- **Issues encountered:** Initial awk implementation of the `list`
  subcommand used a nested-quoting `system()` call; replaced with
  bash-side classification (cleaner, no quoting hazards). Existing
  `test_aitask_update_xdeps.sh` had cases that asserted the old
  both-or-neither error; updated to assert the new semantics and
  added an inverse-half-clear case (clearing `xdeprepo` while
  `xdeps` remains → fails).
- **Key decisions:**
  - Cross-repo task IDs use the documented `<project>#<id>`
    notation; cross-repo file paths use the new `<project>:<path>`
    notation (added to `aidocs/cross_repo_references.md`).
  - Cross-repo refs are inline-only (not added to `file_references:`)
    — same precedent as the existing local archived-task-ref code.
  - The `select_xdeprepo` helper excludes the current project from
    candidates (a task cannot declare itself cross-repo against its
    own project).
  - `select_xdeprepo` short-circuits when the registry has no
    resolvable entries other than self.
  - Validator relaxed semantics: `xdeprepo` alone OK,
    `xdeps` alone dies, both OK. Mirrored in `aitask_update.sh`.
- **Upstream defects identified:** None.
  - Pre-existing parity test failure
    (`tests/test_skill_parity_runtime_vs_rendered.sh:
    manual-verification-followup.md/default
    key=manual_verification_followup_mode`) confirmed to exist on
    clean `main` — unrelated to this task.
- **Notes for sibling tasks:**
  - t832_5: must resolve the new `<project>#<id>` and
    `<project>:<path>` notations during paired exploration (see
    Post-Review Change 1 above; notes added to t832_5's task and
    plan files).
  - Future skill-side follow-up (the deferred
    `aitask-create` AI skill update) should reuse
    `aitask_project_resolve.sh list` to populate the project
    picker — same helper introduced here. Whitelisting will be
    required at that point since the skill calls it directly.
  - The `<project>:<path>` file-ref notation is symmetric with the
    existing `<project>#<id>` task-ref notation; both live in
    `aidocs/cross_repo_references.md`. Future tooling that parses
    task descriptions can extend the regex catalogue documented
    there.
