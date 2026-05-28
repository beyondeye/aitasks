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

# Plan: aitask-create interactive cross-repo support (t832_10)

See parent plan §t832 and pending sibling plan
`aiplans/p832/p832_5_parallel_cross_repo_planning_procedure.md` for
the upstream metadata-only trigger contract.

## Goal

Teach `aitask-create` interactive mode to capture cross-repo intent
at task-creation time:

- Ask early whether the new task involves a second (cross-repo)
  project; pick from the registered registry.
- Persist that choice as `xdeprepo:` (and optional `xdeps:`) in the
  task frontmatter via the existing `aitask_create.sh --batch
  --xdeprepo` / `--xdeps` surface (already shipped in t832_3).
- Make dependency selection, labels, and (optionally) file/task
  references in the description aware of the chosen cross-repo
  project.

Result: a freshly-created task already declares its cross-repo
relationship, so when the user later runs `/aitask-pick <id>`, the
metadata-only trigger inside `parallel-cross-repo-planning.md`
(landed in t832_5) fires automatically and the user is prompted to
proceed with paired planning.

## Architectural decisions (locked during t832_5 planning)

1. **Trigger source is `xdeprepo` metadata only** — no body-text
   scanning, no registered-project-name matching anywhere in the
   trigger path. This task's job is to populate the metadata via
   UI, NOT to add fallback heuristics elsewhere.
2. **Rollout order:** t832_5 → t832_10 (this task) → t832_11
   (aitask-explore cross-repo follow-up; opened after this
   stabilises).
3. **Cross-repo is scalar:** exactly one `xdeprepo` per task. No
   N-way prompts.

## Implementation steps

### Step 1 — Add a "cross-repo?" question in `aitask-create` interactive

`.claude/skills/aitask-create/SKILL.md` — insert a new **Step 1b**
between the current Step 1 (parent task selection) and Step 2
(draft creation):

```markdown
### Step 1b: Cross-Repo Mode (Optional)

After parent selection (Step 1), ask whether the new task
coordinates with a second (cross-repo) aitasks project.

- `AskUserQuestion`:
  - Question: "Does this task coordinate work in a second
    (cross-repo) aitasks project?"
  - Header: "Cross-repo"
  - Options:
    - "No, single-repo task (default)" — skip to Step 2.
    - "Yes, cross-repo task" — proceed to project picker.

**Project picker (only on "Yes"):**

- Enumerate registered projects:
  ```bash
  ./.aitask-scripts/aitask_project_resolve.sh --list
  ```
  Parse each `PROJECT:<name>:<root>:<status>` line; skip
  `status=STALE` and `status=NOT_FOUND` (display a one-line warning
  for each skipped entry).
- `AskUserQuestion` with the resolved candidates as options. On
  selection, store `<xdeprepo_name>` for use in Steps 3c / 3d /
  description prompts.
- If no resolvable projects remain: display "No usable registered
  cross-repo projects found. Continuing in single-repo mode." and
  fall through to Step 2.
```

The actual `aitask_project_resolve.sh --list` subcommand may not
exist yet — confirm during exploration; if absent, either add a
minimal `--list` subcommand to that helper or read the registry
directly via the existing resolver script's machinery. Whichever
path is chosen, encapsulate the enumeration in the helper script
(per the `feedback_archive_encapsulation` pattern) — do NOT
hand-parse `~/.config/aitasks/projects.yaml` from `SKILL.md`.

### Step 2 — Thread `xdeprepo` mode through dependency selection (Step 3c)

In current `SKILL.md` Step 3c, dependencies are gathered from local
active tasks. In cross-repo mode, also list cross-repo active tasks
and let the user select any mix.

Insert (in cross-repo mode only) before the existing local listing:

```bash
./.aitask-scripts/aitask_query_files.sh --project <xdeprepo_name> active-children-all
```

(use the closest existing subcommand — likely a combination of the
existing `--project` re-exec path with a listing that covers both
parents and children. Confirm exact subcommand during exploration.)

Present a unified `AskUserQuestion multiSelect: true` with two
visually grouped sections — local tasks first, cross-repo tasks
second (prefixed with `[<xdeprepo_name>] ` for clarity). On submit,
partition selections by section and assemble:

- `--deps "<local_ids_csv>"` (existing behaviour).
- `--xdeps "<cross_ids_csv>" --xdeprepo "<xdeprepo_name>"` when any
  cross-repo task was selected.

In single-repo mode this behaviour is unchanged.

### Step 3 — Labels union (Step 3d)

In cross-repo mode, read both `aitasks/metadata/labels.txt` (local)
and the cross-repo project's labels via:

```bash
./.aitask-scripts/aitask_query_files.sh --project <xdeprepo_name> labels
```

(again, exact subcommand TBD — extend if needed). Deduplicate and
sort; present as a single multiSelect list. Selected labels go into
the local task's `labels:`. The cross-planning procedure landed in
t832_5 will mirror them onto the counterpart task at spawn time.

### Step 4 — Task references during description authoring (optional polish)

When the user is composing the task description, recognise
`aitasks#N_M` notation (regex `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$`
from `aidocs/cross_repo_references.md`). On match, offer to resolve
into a link by re-reading the referenced task's title via
`aitask_query_files.sh --project <name> task-file <id>`.

This is **polish, not load-bearing**. Gate it behind an explicit
profile or skip entirely on first pass if it inflates scope. The
trigger contract does NOT depend on it (per architectural
decision 1).

### Step 5 — File references in description (cross-repo file picker)

If the user invokes the file picker to add a `--file-ref` while in
cross-repo mode, `.claude/skills/user-file-select/SKILL.md` needs a
`--project <name>` option to list files from the cross-repo project.

This is a separate skill and may not fit cleanly inside t832_10. If
the planning conversation suggests scope creep, split into a
follow-up:

- `t832_10` ships Steps 1–3 above.
- `t832_12` (new follow-up) ports `user-file-select` for
  `--project`.

Confirm the cut during plan review.

### Step 6 — Final batch call

The existing batch invocation in `aitask-create` ultimately reaches
this shape:

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --name "<n>" --priority <p> --effort <e> --type <t> \
  --labels "<l>" --deps "<l_csv>" --commit \
  --desc-file <draft>
```

In cross-repo mode, append:

```bash
  --xdeps "<x_csv>" --xdeprepo "<xdeprepo_name>"
```

When `--xdeps` is empty even in cross-repo mode (e.g., user picked
`<xdeprepo_name>` but selected no cross-repo deps), still pass
`--xdeprepo "<name>"` with an empty `--xdeps ""` only if the
existing validator allows it — otherwise either:

- Pass neither (and rely on the user / planning phase to add
  `xdeprepo:` later via `aitask_update.sh --xdeprepo <name>`), or
- Extend `validate_xdeps_pair` to allow `xdeprepo` without `xdeps`
  for the "intent recorded, no concrete deps yet" case.

The current validator (per `p832_3` notes) enforces both-or-neither.
Discuss in plan review which option is preferred; the cleanest fit
for the t832_5 trigger contract is to allow `xdeprepo` alone (since
intent should propagate even without explicit deps).

## Tests

`tests/test_aitask_create_interactive_cross_repo.sh`:

1. Scaffold two fake projects via
   `tests/lib/test_scaffold.sh::setup_fake_aitask_repo`; register
   both in a temporary `projects.yaml`.
2. Drive `aitask-create` batch entry (interactive mock via env vars
   for AskUserQuestion answers — follow the pattern in any existing
   interactive-flow test) with:
   - cross-repo Yes
   - project = `<B>`
   - 1 local dep + 1 cross-repo dep
   - 2 labels (one local-only, one cross-repo-only)
3. Assert resulting task file has:
   - `xdeprepo: <B>`
   - `xdeps: [<cross_id>]`
   - `depends: [<local_id>]`
   - `labels:` containing both selected labels.
4. **Negative — STALE registry entry:** point `<B>`'s registered
   `root` at a deleted directory; assert the project picker warns
   and offers single-repo fallback.
5. **Negative — NOT_FOUND registry entry:** ditto with a never-
   existed root.
6. **Regression — single-repo flow:** answer "No" to cross-repo
   question; assert resulting task has no `xdeprepo:` / no `xdeps:`
   and matches existing single-repo task expectations.
7. **xdeprepo-alone case** (if the validator change in Step 6
   lands): cross-repo Yes + no cross-repo deps selected → resulting
   task has `xdeprepo: <B>` and no `xdeps:` line.

## Verification

1. `bash tests/test_aitask_create_interactive_cross_repo.sh` —
   all assertions pass.
2. Regression suite: `bash tests/test_xdeps_parser.sh`,
   `test_xdeps_validation.sh`, `test_xdeps_fold_warn.sh`,
   `test_query_files_cross_repo.sh`, `test_create_project_flag.sh`
   — none regress.
3. `./.aitask-scripts/aitask_skill_verify.sh` — PASS.
4. `shellcheck` clean on any touched helper.
5. **Manual smoke (golden path):**
   - Register a synthetic second project locally.
   - Run `ait create` interactively; answer Yes to cross-repo,
     pick the second project, select one cross-repo dep, one
     cross-repo label.
   - Verify the resulting file has the expected frontmatter.
   - Run `/aitask-pick <new_id>`.
   - Confirm the metadata-only trigger in
     `parallel-cross-repo-planning.md` (landed by t832_5) fires
     and the confirmation prompt is presented.

## Dependencies and Sequencing

This task depends on:

- t832_3 (xdeps parser & validation) — already landed; verified.
- t832_1 (cross-repo retrieval `--project`) — already landed;
  verified.
- t832_5 (parallel-cross-repo-planning procedure) — **MUST land
  before this task is meaningful end-to-end.** Without t832_5, this
  task's output (`xdeprepo`-tagged tasks) is recorded but never
  triggers paired planning at pick-time.

Sequencing: implement t832_10 only after t832_5 lands and its
metadata-only trigger is verified to fire on `xdeprepo`-tagged tasks.

## Notes for sibling tasks

- **The validator's xdeprepo-without-xdeps behaviour is potentially
  load-bearing** for both t832_5 (trigger fires on xdeprepo alone)
  and t832_11 (aitask-explore will also want to record xdeprepo
  intent without concrete xdeps). The Step 6 decision should be
  documented in the implementation notes so t832_11 inherits the
  same contract.
- **The `aitask_project_resolve.sh --list` subcommand** (if
  introduced here) is reusable by t832_11 and by `ait board`
  cross-repo display work (t832_8). Encapsulate cleanly.

## Out of scope

- aitask-explore cross-repo integration → t832_11.
- `user-file-select --project` (cross-repo file picker) → possibly
  split into t832_12 (decided in plan review).
- Templating `aitask-create` to `.j2` — orthogonal cleanup task.
- TUI display of `xdeprepo` in `ait board` (t832_8).
- N-way (≥3) cross-repo plans.

## Plan Verification Notes (2026-05-28)

Verified the plan against current `main`. Concrete decisions locked
during verification (these resolve the "TBD" spots in the original
plan body):

- **New helper subcommand for project enumeration:** add
  `aitask_project_resolve.sh list` (no `--` prefix; matches other
  subcommands) emitting `PROJECT:<name>:<path>:<status>` per line
  where status ∈ {`RESOLVED`, `STALE`}. Whitelist via
  `aitask_audit_wrappers.sh apply-helper-whitelist
  aitask_project_resolve.sh` (5 touchpoints).
- **New `labels` subcommand on `aitask_query_files.sh`:** emit
  one `LABEL:<name>` line per non-blank, non-comment line in
  `aitasks/metadata/labels.txt`. Reuses the existing `--project`
  re-exec path, so cross-repo labels just work via
  `aitask_query_files.sh --project <name> labels`.
- **Validator relaxation:** `validate_xdeps_pair` in
  `lib/task_utils.sh` allows `xdeprepo` alone (intent-only). The
  remaining failure case is `xdeps` without `xdeprepo` (xdeps need
  a project). `aitask_create.sh` emits the two YAML lines
  independently so a `--xdeprepo`-only invocation writes only
  `xdeprepo:` to the draft. **This is load-bearing** for the
  metadata-only trigger contract t832_5 will land.
- **Labels prompt is new for ALL tasks (not just cross-repo):** the
  current SKILL.md hardcodes `labels: []`. The simplest cut adds a
  multiSelect labels prompt during Step 3, and in cross-repo mode
  the candidate list is the union of local + cross-repo labels.
- **Defer Steps 4 and 5** per the original plan: notation polish
  and cross-repo file picker stay out of this task.
- **Test surface:** drive batch mode through the CLI (the
  established pattern; `AskUserQuestion` is Claude-driven and not
  shell-testable). New tests: `test_project_resolve_list.sh`,
  `test_query_files_labels.sh`, `test_aitask_create_xdeprepo_alone.sh`.
  Update `test_xdeps_validation.sh` case 2 (only `--xdeprepo` now
  succeeds).
- **Inertness ack:** t832_5 (the trigger consumer) and t832_9 (the
  manual verification of t832_1..8) are still Ready as of plan
  verification. User explicitly chose to ship t832_10 first
  anyway; the captured metadata is harmless until t832_5 lands.

## Final Implementation Notes

(To be filled by the implementing agent during/after execution.)
