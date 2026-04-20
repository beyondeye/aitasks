---
title: "/aitask-qa"
linkTitle: "/aitask-qa"
weight: 75
description: "Run QA analysis on any task — discover tests, run them, identify gaps, and create follow-up test tasks"
---

Run QA analysis on any task — discover tests, run them, identify gaps, and create follow-up test tasks. This skill works with both active and archived tasks, making it useful for reviewing test coverage at any point in the task lifecycle.

**Usage:**
```
/aitask-qa              # Interactive: select from recently archived tasks
/aitask-qa 42           # Analyze a specific parent task
/aitask-qa 16_2         # Analyze a specific child task
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.
>
> This skill is **read-only** — it never modifies task status or claims ownership. It analyzes changes, runs tests, and optionally creates follow-up tasks for additional test coverage.

## Step-by-Step

1. **Profile selection** — Loads an execution profile to pre-answer QA questions. See [Execution Profiles](aitask-pick/execution-profiles/) for the profile schema
2. **Task selection** — Select a task by ID or interactively from recently archived/active tasks. Supports both parent and child tasks
3. **QA tier selection** — Choose analysis depth: Quick, Standard, or Exhaustive (see [Three Tiers](#three-tiers) below)
4. **Change analysis** [Standard, Exhaustive] — Detects commits associated with the task, categorizes changed files into source code, test files, and config/docs
5. **Test discovery** [Standard, Exhaustive] — Scans for existing tests (bash `test_*.sh`, python `test_*.py`, TypeScript `*.spec.ts`, etc.), maps source files to test files, and identifies coverage gaps
6. **Test execution** [All tiers] — Runs discovered tests using configured commands or auto-detection, presents PASS/FAIL summary. Includes a health score [Standard, Exhaustive] and verification gate [Exhaustive]
7. **Test plan proposal** [Standard, Exhaustive] — Generates test proposals (unit, integration, edge cases) with regression test hints for bug-fix tasks. For Exhaustive tier, includes edge case brainstorming (concurrency, resource exhaustion, platform quirks, malformed input)
8. **Follow-up task creation** (optional) — Creates a follow-up test task as a sibling (for child tasks) or standalone task, pre-filled with the test plan
9. **Satisfaction feedback** — Optional prompt to record how well the QA analysis served your needs. Controlled by `enableFeedbackQuestions`; see [Verified Scores](../verified-scores/)

## Three Tiers

The tier system controls analysis depth, letting you balance thoroughness against time:

| Tier | Steps | Use Case |
|------|-------|----------|
| **Quick** | Test execution only (step 6) | Fast smoke test — just run existing tests and report results |
| **Standard** | Full analysis (steps 4--7) | Regular workflow — change analysis, gap detection, test proposals |
| **Exhaustive** | Full analysis + verification gate + edge cases | Critical paths — deep verification with evidence table and edge case brainstorming |

## Key Capabilities

- **Works with archived tasks** — Analyze any completed task, not just active ones. Select interactively from recently archived tasks or pass a task ID directly
- **Commit-aware analysis** — Detects commits using the `(t<N>)` pattern in commit messages, then categorizes changes to focus test proposals on modified code
- **Auto-detection** — When `test_command` is not configured, the skill auto-detects test files matching common patterns (`tests/test_*.sh`, `test_*.py`, `*.spec.ts`)
- **Tiered depth** — Quick tier for fast smoke tests, Standard for regular gap analysis, Exhaustive for critical-path verification with evidence tables
- **Regression hints** — For bug-fix tasks (`issue_type: bug`), generates specific regression test suggestions following the red-green verification cycle
- **Follow-up task integration** — Creates well-structured follow-up test tasks using the standard task creation pipeline, with proper dependencies and labels

## Configuration

### Profile Keys

These profile keys control `/aitask-qa` behavior when set in a profile YAML file (`aitasks/metadata/profiles/`):

| Key | Values | Description |
|-----|--------|-------------|
| `qa_mode` | `"ask"`, `"create_task"`, `"implement"`, `"plan_only"` | What to do with test proposals — prompt interactively, auto-create a follow-up task, implement tests in the current session, or export the plan to a file |
| `qa_run_tests` | `true`, `false` | Whether to run discovered tests. Set to `false` to skip test execution entirely |
| `qa_tier` | `"quick"`, `"standard"`, `"exhaustive"` | Pre-select the analysis tier without prompting |

### Project Config Keys

These keys in `aitasks/metadata/project_config.yaml` configure test and lint commands:

| Key | Type | Description |
|-----|------|-------------|
| `test_command` | string or list | Shell command(s) for running project tests. If not set, the skill auto-detects test files |
| `lint_command` | string or list | Shell command(s) for linting project code. If not set, linting is skipped |

See [Build Verification](aitask-pick/build-verification/) for details on `test_command`, `lint_command`, and `verify_build`.

## Workflows

For a workflow guide covering QA analysis patterns and when to use each tier, see [QA and Testing](../../workflows/qa-testing/).
