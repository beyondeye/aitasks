---
name: aitask-docs-gap
description: Analyze tasks landed since the last release and create one documentation task covering website docs gaps.
---

## Usage

```
/aitask-docs-gap [from_tag]
```

- `from_tag` (optional) — analyze tasks landed since this `v*` tag instead of
  the latest one (passed through as `--from-tag` to the gather script).

This skill is **analysis-only**: it never edits documentation itself. It
classifies each task landed in the release window as documented / gap / not
doc-relevant against the project's configured doc-update guide, then creates
**one single** `documentation` task with a clearly delimited section per gap.
It never creates child tasks — the created task can be split into siblings at
pick time via the normal task-workflow decomposition.

## Workflow

### Step 0: Sync with Remote

Before gathering release data, ensure the local `main` reflects the full remote history. The gather script reads local refs only — tasks merged on remote since the last local pull will silently be missing from the analysis otherwise.

Run a best-effort fetch:

```bash
git fetch origin --quiet 2>&1 || echo "FETCH_FAILED"
```

If fetch failed (output contains `FETCH_FAILED`), warn the user — "Could not fetch from origin; the analysis may not reflect the latest remote state." — and proceed to Step 1.

Otherwise, check whether local `main` is behind `origin/main`:

```bash
git rev-list --count main..origin/main 2>/dev/null
```

If the count is `0`, proceed to Step 1 silently.

If the count is greater than `0`, use `AskUserQuestion`:
- Question: "Local main is N commits behind origin/main. The analysis will miss those tasks unless you sync first. How to proceed?"
- Header: "Sync"
- Options:
  - "Pull and continue" (description: "Run `git pull --rebase origin main` and proceed")
  - "Skip sync (analysis may be incomplete)" (description: "Continue with local-only history")
  - "Abort" (description: "Exit without making changes")

If "Pull and continue":
```bash
git pull --rebase origin main
```
On failure (conflicts), inform the user: "Rebase failed. Resolve conflicts manually, then re-run `/aitask-docs-gap`." End the workflow.

If "Skip sync": proceed to Step 1.

If "Abort": end the workflow.

### Step 1: Gather Release Scope

Reuse the changelog gather step unchanged — do not build parallel gathering logic:

```bash
./.aitask-scripts/aitask_changelog.sh --gather
```

If a `from_tag` argument was provided, append `--from-tag <from_tag>`.

Parse the output by `KEY:` prefix (not by field position — the emission order is `ISSUE_TYPE`, `TITLE`, `PLAN_FILE`, `NOTES`, `COMMITS`):
- The base tag from the `BASE_TAG:` line
- Each task section (`=== TASK tNN ===` to `=== END ===`) containing:
  - `ISSUE_TYPE:` — task type (feature, bug, enhancement, chore, documentation, performance, refactor, style, test)
  - `TITLE:` — human-readable task name
  - `PLAN_FILE:` — path to the archived plan file (may be empty)
  - `NOTES:` — "Final Implementation Notes" from the plan (may be empty)
  - `COMMITS:` — one `<short-hash> <subject>` line per source-code commit

**Degenerate cases:**
- Output is `No commits found since <tag>` → display "No commits since \<tag\> — nothing to analyze." and end the workflow.
- Output contains `COMMITS_ONLY:` (commits exist but none are task-tagged) → display the raw commit list, inform the user: "No task-tagged commits found since the last release — per-task doc-gap analysis cannot run. No task will be created." and proceed directly to Step 7 (create nothing).

### Step 2: Resolve the Doc-Update Spec

Resolve the project's configured doc-update guide (the same seam the `docs_updated` gate uses):

```bash
./.aitask-scripts/aitask_resolve_config_path.sh doc_update.guide aitasks/metadata/doc_update_guide.md
```

The resolver always exits 0 and prints exactly one line. If the line is empty, use the fallback `aitasks/metadata/doc_update_guide.md`. If the resolved file is unreadable, display "No doc-update guide found — cannot classify doc relevance. Configure `doc_update.guide` in `aitasks/metadata/project_config.yaml`." and end the workflow.

Read the guide. It provides:
- The change-kind → doc-area map (which code changes map to which documentation area)
- The doc landscape (which surfaces are user-facing website docs vs internal design docs)
- Relevance semantics (which change kinds carry no doc obligation)

Do not hardcode a change-kind map in this skill — the guide is the single source of truth.

### Step 3: Derive the Changed-File Surface Per Task

The gather output does not include file lists; derive them from each task's commits. For each `=== TASK tNN ===` section, extract the short hashes from its `COMMITS:` block and run:

```bash
git show --name-only --format= <sha>
```

for each hash. Ignore task/plan data paths: `aitasks/`, `aiplans/`, `.aitask-data/`.

Also compute the release-window documentation surface once (used in Step 4 for "already updated in this window" checks):

```bash
git diff --name-only <BASE_TAG>..HEAD -- website/content/docs/ aidocs/
```

### Step 4: Classify Each Task

Classify every task as **documented**, **gap**, or **not doc-relevant**:

1. **Not doc-relevant by kind:** skip tasks whose change carries no doc obligation per the guide (e.g. `test` tasks, purely internal `chore`/`refactor` work with no user-facing surface). Changes mapping only to internal design docs (`aidocs/`) are not website gaps.
2. **Map the surface:** run each task's changed files through the guide's change-kind → doc-area map to determine the mapped website page(s). Respect the guide's caveats (e.g. which TUIs are documented).
3. **Documented:** the mapped page(s) were touched in the release window (by the task's own commits or any other commit in the window — another task may have covered the same doc area), **or** reading the mapped page shows the shipped behavior is already covered.
4. **Gap:** a doc-relevant surface shipped and the mapped page is missing or silent about it. Use the task's `PLAN_FILE:` / `NOTES:` content to understand what shipped and what the docs should say.

When a mapped page's coverage is unclear from the window diff alone, read the page — classification should reflect actual page content, not just churn.

### Step 5: Confirm Findings

**If no gaps were found:** display "Docs are complete for this release (\<N\> tasks analyzed: \<X\> documented, \<Y\> not doc-relevant)." and proceed to Step 7 — create nothing.

**Otherwise**, present the findings via `AskUserQuestion`. The per-gap findings summary MUST be carried inside the question text itself (one short line per gap: task id, feature, target doc page) — never only in same-turn prose before the widget:
- Question: "Found \<G\> doc gap(s) since \<BASE_TAG\>: \<one line per gap\>. Create a single documentation task capturing them? (priority medium; effort scaled by gap count)"
- Header: "Doc gaps"
- Options:
  - "Create documentation task (Recommended)" (description: "Create one task with a delimited section per gap listed above")
  - "Let me choose which gaps" (description: "Select a subset of the gaps to include")
  - "No task — end" (description: "Report only; create nothing")

If "Let me choose which gaps": use a second `AskUserQuestion` with `multiSelect: true`, one option per gap (label = `t<NN> <short feature>`, description = target doc page). The selected gaps form the confirmed set; if none are selected, treat as "No task — end".

If "No task — end": proceed to Step 7 without creating anything.

Derive the new task's `effort` from the confirmed gap count: 1–2 → `low`, 3–5 → `medium`, more than 5 → `high`.

### Step 6: Create the Documentation Task

First classify the proposed labels so new vocabulary is confirmed before it lands in `aitasks/metadata/labels.txt`:

```bash
./.aitask-scripts/aitask_labels.sh classify "docs,web_site"
```

Parse the output lines: `EXISTING:` labels pass through; for `NEAR:<label>:<candidates>` or `NEW:` lines, confirm with the user via `AskUserQuestion` (header: "Labels") whether to use the near-match, keep the new label, or drop it. `INVALID:` labels are dropped.

Then create the single task (sanitize the base tag for the name: `v0.1.2` → `v0_1_2`):

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
  --name "docs_gaps_since_<sanitized_base_tag>" \
  --priority medium \
  --effort <derived_effort> \
  --type documentation \
  --labels "<confirmed_csv>" \
  --desc-file - <<'TASK_DESC'
<description>
TASK_DESC
```

Description layout — one clearly delimited section per confirmed gap so pick-time decomposition can split it cleanly into siblings:

```markdown
Documentation gaps found by /aitask-docs-gap for the release window <BASE_TAG>..HEAD.
Each section below is self-contained and can become its own child task at
decomposition time.

## Gap: <feature name> (tNN)

- **Target doc page(s):** <website/content/docs/... path(s)>
- **What shipped:** <1-3 sentences from the task's plan/notes>
- **What to write:** <what the page needs to say>
- **Sources:** <archived plan path>; commits: <short hashes>
```

Never create child tasks here.

Read back the created task ID and display it to the user:

```bash
./ait git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
```

### Step 7: Satisfaction Feedback

Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/satisfaction-feedback.md`) with `skill_name` = `"docs-gap"`.

## Notes

- Complementary to `/aitask-changelog` (release summary) and to the `docs_updated` gate (per-task, forward-looking doc enforcement). This skill is the retroactive batch complement for releases where the gate was not active per-task.
- Release scope comes from `.aitask-scripts/aitask_changelog.sh --gather` — no parallel gathering logic. Task IDs are detected from parenthesized `(tNN)` / `(tNN_MM)` patterns in commit messages.
- Doc relevance comes from the guide resolved via `doc_update.guide` in `aitasks/metadata/project_config.yaml` (fallback: `aitasks/metadata/doc_update_guide.md`) — no hardcoded change-kind map in this skill.
- The skill never edits documentation: writing the docs is the created task's job (or the `docs_updated` gate's job going forward).
