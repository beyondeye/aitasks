---
title: "QA and Testing Workflow"
linkTitle: "QA and Testing"
weight: 75
description: "Systematic test coverage analysis and follow-up task creation"
---

Automated tests should be part of every implementation — when you run [`/aitask-pick`](../../skills/aitask-pick/), the implementation step naturally includes writing tests alongside the feature code. But real-world constraints mean test coverage gaps are common:

- **LLM context limits** may prevent full test coverage during implementation, especially for complex tasks that consume most of the available context with source code and plan content
- **Test requirements discovered later** — edge cases, integration scenarios, and failure modes often become apparent only after the feature is used or reviewed
- **Incremental test strategy** — some teams prefer a quick implementation pass followed by a dedicated test-hardening round

[`/aitask-qa`](../../skills/aitask-qa/) exists to systematically identify and fill these gaps. It analyzes what was built, discovers existing tests, runs them, identifies coverage holes, and proposes a test plan — optionally creating a follow-up task to implement the missing tests.

## The QA Cycle

After completing an implementation task with [`/aitask-pick`](../../skills/aitask-pick/):

1. **Run [`/aitask-qa`](../../skills/aitask-qa/)** — Pass the task ID (e.g., `/aitask-qa 42`) or select interactively from recently archived tasks. Choose a QA tier based on how thorough you want the analysis to be
2. **Review the analysis** — The skill detects commits, categorizes changes, maps source files to test files, and identifies gaps
3. **Run tests** — Existing tests are executed and results summarized with a health score
4. **Review test proposals** — Generated proposals target the specific gaps identified in the analysis, with regression hints for bug fixes
5. **Create follow-up task** — Optionally create a test task pre-filled with the test plan, ready to be picked up in a fresh context

## Walkthrough: QA After Adding a CLI Command

You've just finished task t195 — adding a new `ait lock` command to `.aitask-scripts/`. The implementation included basic happy-path tests, but you want to verify coverage is adequate.

**1. Launch the skill**

```
/aitask-qa 195
```

**2. Select the tier**

Choose "Standard" — you want full gap analysis but don't need exhaustive edge case brainstorming for a utility command.

**3. Change analysis**

The skill finds 3 commits tagged `(t195)`, categorizes the changes:
- Source: `aitask_lock.sh` (new), `task_utils.sh` (modified)
- Tests: `test_task_lock.sh` (new)
- Config: none

**4. Test discovery**

The skill scans `tests/` and finds `test_task_lock.sh` covers `aitask_lock.sh`, but `task_utils.sh` modifications (new helper functions added for lock support) have no dedicated test coverage.

**5. Test execution**

All existing tests pass. The health score shows 70/100 — tests pass but coverage has gaps.

**6. Test plan proposal**

The skill proposes:
- Unit tests for the new helper functions in `task_utils.sh`
- Integration test for lock acquisition with concurrent access
- Error path test for lock file corruption

**7. Create follow-up task**

Select "Create follow-up test task" — a new task t210 is created with the test plan pre-filled, labels set to `testing,qa`, and dependencies pointing back to t195.

Pick up t210 later with `/aitask-pick 210` to implement the proposed tests in a fresh context with full LLM capacity.

## Choosing a Tier

| Tier | Time | Best For |
|------|------|----------|
| **Quick** | ~1 min | Fast smoke test — run existing tests, check if anything is broken |
| **Standard** | ~5 min | Regular workflow — full gap analysis with test proposals |
| **Exhaustive** | ~10 min | Critical code paths — adds verification gate (re-runs tests for evidence), edge case brainstorming (concurrency, resource exhaustion, malformed input) |

**Rule of thumb:** Use Quick for confidence checks during development, Standard after implementing any task, and Exhaustive before releases or for security-sensitive changes.

## Configuration

### Test and Lint Commands

Configure in `aitasks/metadata/project_config.yaml`:

```yaml
test_command: "bash tests/test_*.sh"
lint_command: "shellcheck .aitask-scripts/aitask_*.sh"
```

When not configured, the skill auto-detects test files matching common patterns (`tests/test_*.sh`, `test_*.py`, `*.spec.ts`).

See [Build Verification](../../skills/aitask-pick/build-verification/) for the full configuration reference including `verify_build`.

### Profile Keys

Pre-configure QA behavior in execution profiles (`aitasks/metadata/profiles/`):

```yaml
qa_mode: ask          # or: create_task, implement, plan_only
qa_run_tests: true    # or: false to skip test execution
qa_tier: standard     # or: quick, exhaustive
```

See [Execution Profiles](../../skills/aitask-pick/execution-profiles/) for the full profile schema.

## When to Run QA

- **After implementing a feature** — Standard tier to catch coverage gaps while context is fresh
- **After fixing a bug** — Standard or Exhaustive tier to ensure regression tests exist (the skill generates specific regression hints for `issue_type: bug`)
- **Periodic test audits** — Pick recently archived tasks and run Standard analysis to identify accumulated test debt
- **Before releases** — Exhaustive tier on critical tasks to build confidence with verification evidence

## Tips

- **Start with Quick** for a fast confidence check — if tests pass and you're satisfied, you're done
- **Use Standard as the default** after any implementation — it balances thoroughness with speed
- **Reserve Exhaustive for critical paths** — the edge case brainstorming and verification gate add value for security, data integrity, and high-traffic code paths
- **Batch QA sessions** — Run `/aitask-qa` on multiple recently archived tasks in sequence to catch accumulated test debt across a sprint
- **Configure `test_command`** in `project_config.yaml` early — auto-detection works but explicit configuration is more reliable and faster
