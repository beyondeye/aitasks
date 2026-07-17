---
title: "/aitask-create"
linkTitle: "/aitask-create"
weight: 40
description: "Create a new task file interactively via code agent prompts"
maturity: [stable]
depth: [intermediate]
---

Create a new task file with automatic numbering and proper metadata via interactive code agent prompts.

**Usage:**
```
/aitask-create
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

The skill guides you through task creation using interactive prompts:

1. **Parent selection** — Choose standalone or child of existing task
2. **Task number** — Auto-determined from active, archived, and compressed tasks
3. **Metadata** — Priority, effort, dependencies (with sibling dependency prompt for child tasks)
4. **Task name** — Free text with auto-sanitization
5. **Definition** — Iterative content collection with file reference insertion via Glob search
6. **Create & commit** — Writes task file with YAML frontmatter and commits to git

## Batch Mode

For non-interactive task creation (e.g., scripting or automation), use the underlying script directly with `--batch`:

```bash
./.aitask-scripts/aitask_create.sh --batch --name "task_name" --desc "description" --commit
```

Run `./.aitask-scripts/aitask_create.sh --help` for the full list of flags.

**File references and auto-merge:**

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
    --name "fix_login" --desc "..." \
    --file-ref "lib/login.py:42-68" \
    --auto-merge
```

- `--file-ref PATH[:N[-M][^N[-M]...]]` (repeatable) attaches a structured pointer to source lines in the new task's `file_references` frontmatter.
- `--auto-merge` folds any `Ready`/`Editing` task that already references the same path into the new one. The default (`--no-auto-merge`) warns and skips instead.

**Declared gates and manual-verification tasks:**

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
    --name "add_settings_screen" --desc "..." \
    --gates "risk_evaluated,build_verified"
```

- `--gates GATES` (comma-separated names from `aitasks/metadata/gates.yaml`) declares the verification gates the task must satisfy before it can archive. Execution profiles with `default_gates` inject this flag automatically on every task the workflow creates.
- **`--type manual_verification` tasks keep only the gates they can reach.** A manual-verification task runs a human checklist instead of the plan/implement/review steps, so gates recorded during planning or review (`risk_evaluated`, `plan_approved`, `review_approved`, `docs_updated`) can never be satisfied and would block archival forever. The script keeps only the post-verification machine gates (`build_verified`, `tests_pass`, `lint`) and drops everything else with a notice — whether the gates came from a profile's `default_gates` or an explicit `--gates`. This also applies when finalizing a draft.

See the [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}) workflow guide for the full walkthrough, including the interactive codebrowser `n` flow.

## Workflows

For workflow guides, see [Capturing Ideas](../../workflows/capturing-ideas/) and [Follow-Up Tasks](../../workflows/follow-up-tasks/).
