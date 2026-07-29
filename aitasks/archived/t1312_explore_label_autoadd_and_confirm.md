---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [1321]
issue_type: enhancement
status: Done
labels: [aitask_explore, aitask-create, execution_profiles, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1321, 1336, 1337]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-07-29 09:15
updated_at: 2026-07-29 18:40
completed_at: 2026-07-29 18:40
---

Extend `/aitask-explore` so the labels it puts on newly created tasks are
confirmed by the user and actually land in `aitasks/metadata/labels.txt`
(committed), instead of being invented ad hoc and silently lost.

## Problem

`/aitask-explore` has become the main way tasks get created in this repo, but
the label vocabulary never grows with it:

1. **Batch creation never writes `labels.txt`.** `add_label_to_file()` exists at
   `.aitask-scripts/aitask_create.sh:1089` but is only reachable from the
   *interactive* fzf path (re-inlined at `:1219`). The `--batch` dispatch
   (`:2037` parent, `:2067` child) passes `BATCH_LABELS` straight into the task
   frontmatter with no vocabulary write. So every new label an explore-created
   task uses is absent from `labels.txt` — and therefore missing from
   `/aitask-pick`'s label filter, the board, and future suggestion lists.
2. **The commit path is already in place.** `task_git add "$LABELS_FILE"` runs
   at `.aitask-scripts/aitask_create.sh:2048` (parent), `:2080` (child) and
   `:1912`. Once batch mode *writes* the label, committing it is free — no new
   commit logic needed on the create side.
3. **`/aitask-explore` never mentions labels.** `.claude/skills/aitask-explore/SKILL.md.j2`
   only lists `labels: "<l>"` as a Batch Task Creation parameter (`:225`) and
   offers "Change the title, priority, effort, labels, or description" (`:192`).
   There is no labels default in the Step 1 table, no read of `labels.txt`, and
   no confirmation prompt — the agent invents labels freely.
4. **The vocabulary is already drifting.** `aitasks/metadata/labels.txt` (95
   entries) contains typos (`aitakspickrem`, `brainstom_modules`,
   `brainstorm_synthetize`, `skill_optiomizations`, `sanboxing`, `modelvrapper`)
   and mixed separators (`aitask-create`, `aitask-redesign`, `task-archive`,
   `git-integration`, `auto-update` vs `aitask_explore`, `task_workflow`,
   `web_site`). Blind auto-append would accelerate this.

Related gaps found while exploring (in scope, see AC):

5. **`aitask_update.sh` writes but does not stage.** `--add-label` reaches
   `add_label_to_file` via `process_label_operations`
   (`.aitask-scripts/aitask_update.sh:874`), but the commit at `:2016` (batch)
   and `:1662` (interactive) stages only the task file. `labels.txt` is left
   dirty in the worktree for an unrelated commit to sweep up. Note
   `--labels` (replace-all) does **not** auto-add at all.
6. **`sanitize_label` is triplicated and unshared.** Defined at
   `.aitask-scripts/aitask_create.sh:1069`, re-inlined verbatim at
   `.aitask-scripts/aitask_update.sh:1368`, and nothing lives in
   `.aitask-scripts/lib/task_utils.sh`.
7. **Batch also skips `set_last_used_labels`** (`aitask_create.sh:2309` —
   interactive path only), so batch-created labels never feed the ">> Use labels
   from previous task" affordance either.

## Goal

1. Batch task creation auto-adds any new label to `labels.txt` (sanitized,
   deduped) and the existing `task_git add` makes it part of the task-creation
   commit.
2. `/aitask-explore` asks the user to confirm the labels before creating the
   task, in an interactive way, **gated by a new execution-profile key** so
   headless/remote profiles skip the prompt entirely.
3. The updated `labels.txt` is reliably committed on both the create and update
   paths.

## Acceptance Criteria

### A. Shared seam
- [ ] `sanitize_label()` and `add_label_to_file()` live in
      `.aitask-scripts/lib/task_utils.sh` as the single canonical
      implementation; `aitask_create.sh` and `aitask_update.sh` call it instead
      of carrying their own copies (including the inline copy at
      `aitask_update.sh:1368` and the inline block at `aitask_create.sh:1219`).
      `LABELS_FILE` resolution stays consistent for both callers.
- [ ] `shellcheck .aitask-scripts/aitask_*.sh` stays clean.

### B. Batch auto-add (`aitask_create.sh`)
- [ ] `--batch --labels "a,b"` sanitizes each label and adds any not already
      present to `aitasks/metadata/labels.txt`, before the `task_git add
      "$LABELS_FILE"` at `:2048` / `:2080`, so the new labels land **in the
      task-creation commit** (parent *and* child paths).
- [x] Labels rejected by sanitization (empty after stripping) do not silently
      end up in frontmatter — **decided: warn and drop** (exit 0, stderr
      warning, label absent). Frontmatter and `labels.txt` agree.
- [x] **Added at review:** control characters (newline / CR / tab) are folded to
      `_` by `sanitize_label` before the line-oriented stages, folded across the
      whole CSV before `normalize_labels_csv` splits, and refused outright at the
      `add_label_to_file` write site. Without this, `--add-label $'alpha\nbeta'`
      emitted a two-physical-line `labels: [...]` inline list (YAML-folded to the
      space-bearing label `alpha beta`) while registering only `alpha`.
- [x] **Documented deviation:** batch mode does **not** call
      `set_last_used_labels`. That helper backs the human ">> Use labels from
      previous task" fzf affordance; agent-driven batch creates must not
      clobber it, and it would add a Python subprocess to every batch create.
- [x] Draft mode (`aitasks/new/`, no `--commit`): **no vocabulary write until
      finalize.** Drafts are gitignored, so writing at draft time would leak an
      abandoned draft's labels into the worktree permanently. `--labels` is
      still normalized at draft time so the draft's frontmatter is canonical;
      `_register_task_labels` runs in both `finalize_draft` branches. Tested in
      `tests/test_label_autoadd.sh`.

### C. Profile-gated label confirmation in `/aitask-explore`
- [ ] New execution-profile key (proposed name `explore_label_confirm`) added to
      the schema table in `.claude/skills/task-workflow/profiles.md`
      (the table at `:24-47`) with type, allowed values, and the step it
      affects. Value shape to decide during planning — e.g. bool, or an enum
      like `ask` (default) / `auto` (accept agent's labels, still auto-add) /
      `existing_only` (never invent a new label).
- [ ] Key added to `seed/profiles/{default,fast,remote}.yaml` and the live
      `aitasks/metadata/profiles/{default,fast,remote}.yaml`, with `remote`
      (which is `headless: true`) set so **no prompt is ever emitted**.
- [ ] Key registered in the settings TUI: `.aitask-scripts/lib/profile_editor.py`
      type map (`:74-85`), help text dict (`:342+`), and the **"Exploration"**
      group (`:388`, currently holding only `explore_auto_continue`).
- [ ] `.claude/skills/aitask-explore/SKILL.md.j2` gains a label step before the
      Step 3 task-creation confirmation, wrapped in a
      `{% if profile.explore_label_confirm is defined and ... %}` gate following
      the `explore_auto_continue` pattern (shared macro
      `.aitask-scripts/skill_templates/_auto_continue_block.j2`, called at
      `.j2:255`). Extract a macro if the same block is later wanted by
      `aitask-wrap` / `aitask-pr-import`; a skill-local block is acceptable for
      this task.
- [ ] The prompt reads `aitasks/metadata/labels.txt`, presents the agent's
      proposed labels split into **existing** vs **new**, and for each new label
      surfaces near-duplicate existing candidates (e.g. separator-normalized
      match: `aitask-create` vs `aitask_create`) so the user can pick the
      existing one instead of minting a variant. Uses `AskUserQuestion` with
      `multiSelect` where appropriate.
- [ ] Per the skill's own visibility rule (`.j2` Step 2/Step 3), the label list
      must be carried **inside the question text**, not in same-turn prose.
- [ ] The `remote` render contains no label AskUserQuestion at all.

### D. Commit hygiene on the update path
- [ ] `aitask_update.sh` stages `labels.txt` alongside the task file at the
      batch commit (`:2016`) and the interactive commit (`:1662`) whenever
      `add_label_to_file` actually appended something, so `--add-label` no
      longer leaves the worktree dirty. Use `task_git` (labels.txt is tracked on
      the data branch — confirmed via `ait git ls-files
      aitasks/metadata/labels.txt`).
- [x] **Decided:** `--labels` (replace-all) *does* auto-add, matching
      `--add-label` and the create side — both ways of naming a label grow the
      vocabulary identically. Recorded in `--help`. `--remove-label` never
      unregisters (also in `--help`), and its arguments stay unsanitized so
      legacy raw labels remain removable.

### E. Docs + tests
- [ ] Website docs updated: `website/content/docs/concepts/execution-profiles.md`,
      `website/content/docs/skills/aitask-explore.md`,
      `website/content/docs/tuis/settings/reference.md`.
- [ ] Notes section of `.claude/skills/aitask-explore/SKILL.md.j2` documents the
      new key alongside the existing `explore_auto_continue` line (`:280`).
- [ ] Goldens regenerated in the same commit:
      `tests/golden/skills/aitask-explore/SKILL-{default,fast,remote}-claude.md`.
- [ ] `tests/test_skill_render_aitask_explore.sh` extended: a Test-2-style
      per-profile assertion that the label-confirm branch fires for
      default/fast and does **not** fire for `remote`, plus the existing
      no-Jinja-leak and agent-invariance tests still pass.
- [ ] New/extended shell test covering batch auto-add: create a task with a
      brand-new label in a fixture repo, assert the label appears in
      `labels.txt` **and** in the task-creation commit (`git show --name-only`),
      and assert a pre-existing label is not duplicated. Prove the test can fail
      (revert the write, suite exits 1).
- [ ] `./.aitask-scripts/aitask_skill_verify.sh` passes.

## Consistency note (not necessarily this task)

Sibling task-creating skills tell different stories about labels and should end
up consistent with whatever rule this task establishes:
- `.claude/skills/aitask-explorechat/SKILL.md:115` — "only labels present in
  `aitasks/metadata/labels.txt` if readable; otherwise none"
- `.claude/skills/aitask-wrap/SKILL.md.j2:345` — "new labels can be used freely"
- `.claude/skills/aitask-review/SKILL.md.j2:189` — hardcodes `"review"`
- `.claude/skills/aitask-pr-import/SKILL.md.j2:175` — infers from affected files

They all route through the same `aitask_create.sh --batch`, so section B fixes
their vocabulary leak for free; only their *prose* rules would need aligning.

## Out of scope / follow-ups

- **Duplication review across create/explore flavors** — requested during
  exploration: the interactive `aitask_create.sh` fzf flow, its `--batch` flow,
  the `/aitask-create` skill, `/aitask-explore`, `/aitask-explorechat`,
  `/aitask-wrap` and `/aitask-pr-import` each re-implement parts of the same
  metadata-gathering logic. Tracked as a separate follow-up task (see the
  follow-up anchored to this task) rather than expanded here.
- **Cleaning up the existing typos / separator drift in `labels.txt`** — a
  separate data-migration concern (it would rewrite labels already referenced by
  task frontmatter).
- **Cross-repo label union** — `t858` (status `Postponed`) already covers
  reading local + cross-repo `labels.txt` for the `/aitask-create` skill and
  proposes an `aitask_query_files.sh labels` subcommand. If that subcommand
  lands first, reuse it here instead of re-reading the file directly.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-29T07:39:57Z status=pass attempt=1 type=human

> **✅ gate:plan_approved** run=2026-07-29T13:39:54Z status=pass attempt=2 type=human

> **✅ gate:review_approved** run=2026-07-29T15:31:25Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-29T15:40:17Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:f021eb3595d44915

> **✅ gate:risk_evaluated** run=2026-07-29T15:40:17Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1312/risk_evaluated_2026-07-29T15:40:17Z-risk_evaluated-a1.log`
