---
Task: t1355_add_release_docs_gap_skill.md
Worktree: (none — current branch)
Branch: main
Base branch: main
Output branch: main
---

# p1355 — Add `aitask-docs-gap` release docs-gap skill

## Context

`aitask-changelog` summarizes what shipped since the last release, and the
`docs_updated` gate keeps docs current per-task — but only for tasks where the
gate was active. There is no retroactive batch check: releases can land with
shipped features missing from the framework website (`website/content/docs/`).
This task adds a **static skill** `aitask-docs-gap` (same shape as
`aitask-changelog`: single `SKILL.md`, no profile variants, no `.j2`) that
analyzes all tasks landed since the last `v*` tag, classifies each as
documented / gap / not doc-relevant using the configured doc-update guide, and
creates **exactly one** `documentation` task with one delimited `## Gap:`
section per finding. It never creates children (pick-time decomposition can
split it later) and never edits docs itself.

## Key reused seams (no parallel logic)

- **Release scope:** `./.aitask-scripts/aitask_changelog.sh --gather` — emits
  `BASE_TAG: vX.Y.Z`, then per-task sections
  `=== TASK tNN ===` / `ISSUE_TYPE:` / `TITLE:` / `PLAN_FILE:` / `NOTES:` (+body)
  / `COMMITS:` (+one-line `<short-hash> <subject>` per commit) / `=== END ===`.
  Degenerate outputs: `No commits found since <tag>` (exit 0) and
  `COMMITS_ONLY:` + raw commit list (commits exist, none task-tagged).
  Note the real emission order is ISSUE_TYPE, TITLE, PLAN_FILE, NOTES, COMMITS
  (the script's help text shows a stale order — parse by `KEY:` prefix, not
  position).
- **Doc-relevance spec:** `./.aitask-scripts/aitask_resolve_config_path.sh
  doc_update.guide aitasks/metadata/doc_update_guide.md` (always exits 0,
  prints one line; empty line → use the fallback arg). The guide holds the
  change-kind→doc-area map, writing conventions, and pass/skip semantics.
- **Changed-file surface:** same pattern as `aitask-gate-docs-updated` Step 2 —
  `git show --name-only --format= <sha>` over each task's commit hashes (taken
  directly from the section's `COMMITS:` lines; no re-grep of git log needed).
  Ignore `aitasks/`, `aiplans/`, `.aitask-data/` paths.
- **Task creation:** `./.aitask-scripts/aitask_create.sh --batch --commit
  --type documentation --desc-file -` heredoc, mirroring
  `task-workflow/task-creation-batch.md` parent creation; task-ID readback via
  `./ait git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'`.
- **Label vocabulary:** `./.aitask-scripts/aitask_labels.sh classify "<csv>"`
  before creation (as in aitask-explore Step 3a) so new labels are confirmed.
- **Skill ending:** Satisfaction Feedback Procedure
  (`.claude/skills/task-workflow/satisfaction-feedback.md`) with
  `skill_name = "docs-gap"`, same as aitask-changelog's Step 9.

## Files to create / edit

### 1. `.claude/skills/aitask-docs-gap/SKILL.md` (new, source of truth)

Frontmatter: `name: aitask-docs-gap`, `description: Analyze tasks landed since
the last release and create one documentation task covering website docs gaps.`
Include a `## Usage` section (`/aitask-docs-gap [from_tag]`) — the wrapper
generator derives Codex/OpenCode wrapper text from `description` +
`## Usage`/`## Arguments`.

Workflow steps:

- **Step 0 — Remote-sync preflight** (copied from `aitask-changelog` Step 0):
  best-effort `git fetch origin` (`FETCH_FAILED` → warn and continue);
  `git rev-list --count main..origin/main` > 0 → AskUserQuestion (header
  "Sync"): "Pull and continue" (`git pull --rebase origin main`) / "Skip sync
  (analysis may be incomplete)" / "Abort".
- **Step 1 — Gather release scope:** run
  `./.aitask-scripts/aitask_changelog.sh --gather` (append
  `--from-tag <tag>` when the optional argument was given). Parse `BASE_TAG:`
  and the task sections. Degenerate cases:
  - `No commits found since <tag>` → display "No commits since <tag> — nothing
    to analyze." and end.
  - `COMMITS_ONLY:` → display the untagged commit list, report that no
    task-tagged commits exist so per-task doc-gap analysis cannot run, and end
    (create nothing).
- **Step 2 — Resolve and read the doc-update spec:** resolver call above;
  empty output → use `aitasks/metadata/doc_update_guide.md`; unreadable file →
  report and abort. Read the guide; it is the change-kind→doc-area map and the
  relevance semantics. Analysis-only reminder: this skill never edits docs.
- **Step 3 — Changed-file surface per task:** for each `=== TASK tNN ===`
  section, extract short hashes from its `COMMITS:` block and run
  `git show --name-only --format= <sha>` per hash; drop `aitasks/`, `aiplans/`,
  `.aitask-data/` paths. Also compute the release-window docs surface once:
  `git diff --name-only <BASE_TAG>..HEAD -- website/content/docs/ aidocs/`
  (used for "already updated in the same window" checks).
- **Step 4 — Classify each task** (documented / gap / not doc-relevant):
  - Skip inherently non-doc-relevant tasks per the guide (`test`; internal
    `chore`/`refactor` with no user-facing surface).
  - Map each task's changed files through the guide's change-kind→doc-area map
    (TUI → `docs/tuis/<name>.md`, skill → `docs/skills/`, `ait` subcommand →
    `docs/commands/`, workflow behavior → `docs/workflows/<name>.md`, concept →
    `docs/concepts/<name>.md`, framework-internal → `aidocs/` = not a website
    gap). Respect the guide's TUI-list caveat (omit diffviewer).
  - **Documented:** the mapped page(s) were touched in the release window (by
    this task's own commits or any other window commit), or reading the mapped
    page shows the shipped behavior is already covered.
  - **Gap:** doc-relevant surface shipped and the mapped page is missing or
    silent about it. Use `PLAN_FILE:`/`NOTES:` for what shipped.
- **Step 5 — Confirm findings (t1150 visibility rule):** if no gaps → display
  "Docs are complete for this release (N tasks analyzed: X documented, Y not
  doc-relevant)." and go to Step 7 (create nothing). Otherwise AskUserQuestion
  (header "Doc gaps") with the per-gap findings summary carried **inside the
  question text** (never only in same-turn prose): "Create documentation task
  (Recommended)" / "Let me choose which gaps" (second multiSelect question, one
  option per gap) / "No task — end". Include a task-metadata note: priority
  `medium`, effort scaled by confirmed gap count (1–2 → `low`, 3–5 → `medium`,
  >5 → `high`).
- **Step 6 — Create the single documentation task:** classify labels
  (`aitask_labels.sh classify "docs,web_site"` → confirm NEAR/NEW per the
  explore pattern), then:
  ```bash
  ./.aitask-scripts/aitask_create.sh --batch --commit \
    --name "docs_gaps_since_<sanitized_base_tag>" \
    --priority medium --effort <derived> \
    --type documentation --labels "<confirmed_csv>" \
    --desc-file - <<'TASK_DESC'
  ...
  TASK_DESC
  ```
  Description layout: a short intro naming the release window
  (`<BASE_TAG>..HEAD`), then **one `## Gap: <feature> (tNN)` section per
  confirmed gap**, each containing: target doc page(s), what shipped (1–3
  sentences from plan/notes), what to write, and source pointers (archived plan
  path + commit hashes). Read back the new task ID and display it. Never create
  child tasks.
- **Step 7 — Satisfaction feedback:** Execute the Satisfaction Feedback
  Procedure (see `.claude/skills/task-workflow/satisfaction-feedback.md`) with
  `skill_name = "docs-gap"`.

`## Notes` section: complementary to `aitask-changelog` (release summary) and
to the `docs_updated` gate (per-task, forward-looking); this skill is the
retroactive batch complement and is analysis-only.

### 2. Cross-agent wrapper stubs (required by the parity guard — see AC note)

`aitask_skill_verify.sh` runs `aitask_audit_wrappers.sh parity` unconditionally
over every `.claude/skills/aitask-*` dir, so the three wrapper surfaces must
exist in the same commit:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper agents aitask-docs-gap
./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper opencode-skill aitask-docs-gap
./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper opencode-command aitask-docs-gap
```

Produces `.agents/skills/aitask-docs-gap/SKILL.md`,
`.opencode/skills/aitask-docs-gap/SKILL.md`,
`.opencode/commands/aitask-docs-gap.md` (pointer stubs; canonical body stays in
`.claude/`). All three must be git-tracked (`tests/test_opencode_setup.sh`
derives counts from `git ls-files`).

**Explicit AC deviation:** the task's AC says "suggest separate follow-up tasks
porting the skill to Codex CLI and OpenCode". For a static skill the ports ARE
these auto-generated pointer stubs, and the parity guard makes deferring them
impossible (verify would fail). So: generate wrappers in-task, create **no**
porting follow-ups, and update the task file's AC bullet accordingly during
implementation (no silent deviation).

### 3. `.claude/skills/task-workflow/satisfaction-feedback.md` (1-line edit + goldens)

Line 4 enumerates the standalone skills that call the procedure — add
`aitask-docs-gap`. This is a goldened closure procedure: regenerate the
affected renders/goldens in the same commit per
`aidocs/framework/skill_authoring_conventions.md` ("Regenerate goldens after
any `.md.j2` or closure edit") — goldens at
`tests/golden/procs/task-workflow/satisfaction-feedback-{default,fast,remote}.md`
plus the tracked rendered variants. Prose-only change → cross-agent rendered
copies update via the rerender driver (one call per profile).

### 4. Website docs

- **New page** `website/content/docs/skills/aitask-docs-gap.md` — mirror the
  `aitask-changelog.md` page shape: frontmatter (`title`/`linkTitle`
  `"/aitask-docs-gap"`, `weight` adjacent to changelog's 60, `description`,
  `maturity: [experimental]`, `depth: [intermediate]`), intro paragraph,
  `**Usage:**` block, `## Step-by-Step`, `## Key Features`, `## Workflows`
  cross-link to `../../workflows/releases/`. Follow the doc guide's writing
  conventions (current-state-only, generic project names, no agent-set
  enumeration).
- **Hand-curated lists** (all edited by hand):
  - `website/content/docs/skills/_index.md` — row in the "Configuration &
    Reporting" table.
  - `website/content/docs/development/skills/_index.md` — entry alongside
    `aitask-changelog`.
  - `docs/README.md` skill table — one row.
- **`website/content/docs/workflows/releases.md`** — add a short mention of
  running `/aitask-docs-gap` alongside `/aitask-changelog` at release time.
  No new workflows page → no `workflows/_index.md` bullet needed.

### 5. Task file AC update

Edit `aitasks/t1355_add_release_docs_gap_skill.md` AC bullet on porting
follow-ups to reflect the wrapper-stub reality (committed via `./ait git`).

## Out of scope

- No new helper script (no whitelist/touchpoint edits, no shellcheck surface).
- No `seed/`, `install.sh`, `release.yml` changes — skill shipping is
  glob-driven.
- No edits to `aitask_changelog.sh`, the gate verifier, or the doc guide.

## Verification

1. `./.aitask-scripts/aitask_skill_verify.sh` — must pass (wrapper parity for
   the new skill + golden checks for the satisfaction-feedback edit).
2. `bash tests/run_all_python_tests.sh --test-dir tests` is NOT needed (no
   Python touched); instead run `bash tests/test_opencode_setup.sh` if quick,
   to confirm the tracked-wrapper count assertion still passes.
3. Website build: `cd website && hugo build --gc --minify` (if Hugo available
   locally) to validate the new page + index edits.
4. Smoke the skill's data path manually (not the full skill):
   `./.aitask-scripts/aitask_changelog.sh --gather | head -40` and
   `./.aitask-scripts/aitask_resolve_config_path.sh doc_update.guide aitasks/metadata/doc_update_guide.md`
   to confirm the parse contract on live data.
5. Commit format: `feature: Add aitask-docs-gap release docs-gap skill (t1355)`
   for code; `ait:` commits for task/plan files. Then Step 9
   (post-implementation): gates run (`risk_evaluated` recorded), archival.

## Risk

### Code-health risk: low
None identified. (Additive skill + docs; the only shared-surface edit is one
prose line in a goldened procedure, and the plan pins golden regeneration in
the same commit with `aitask_skill_verify.sh` as the guard.)

### Goal-achievement risk: low
None identified. (All AC bullets are addressed; the one AC deviation — wrapper
stubs now instead of porting follow-ups — is forced by the parity guard and
made explicit, with the task AC updated in-task.)
