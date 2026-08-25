---
title: "Build, Test, and Lint Configuration"
linkTitle: "Build Verification"
weight: 10
description: "Configure build verification, test commands, and lint commands"
depth: [advanced]
---

After implementation, the skill can optionally run a build verification command to catch regressions introduced by the task's changes. This is configured via `aitasks/metadata/project_config.yaml` and applies to all three implementation skills: `/aitask-pick`, `/aitask-pickrem`, and `/aitask-pickweb`.

## Configuration

```yaml
# Single command
verify_build: "cargo build"

# Multiple commands (run sequentially, stop on first failure)
verify_build:
  - "npm install"
  - "npm run build"
  - "npm test"
```

An **inline-list item** containing a comma must use the block (`- …`) form
instead: the inline `[a, b]` form splits on every comma, including one inside
quotes. A single scalar command is unaffected —
`test_command: "pytest -k 'a,b'"` is read whole.

If `verify_build` is not set (or the file doesn't exist), the step is skipped entirely.

## How It Works

The `project_config.yaml` file is:
- **Git-tracked** — shared across the team (unlike `userconfig.yaml` which is per-user)
- **Project-specific** — not tied to execution profiles (the same build command applies regardless of which profile you use)
- **Installed from seed** — a template is copied during `ait setup`; edit it to match your project

### Failure Handling

If the build fails, the agent analyzes whether the failure is caused by the task's own changes:
- **Task-related failure:** The agent automatically goes back to fix the errors and re-runs the build. This repeats until the build passes.
- **Pre-existing failure:** The agent logs the build failure details in the plan file's "Final Implementation Notes" and proceeds without attempting to fix unrelated issues.

## Common Examples

| Project Type | `verify_build` |
|-------------|----------------|
| Android (Gradle) | `"JAVA_HOME=/opt/android-studio/jbr ./gradlew assembleDebug"` |
| Rust | `"cargo build"` |
| Node.js | `"npm run build"` |
| Go | `"go build ./..."` |
| Python | `"python -m py_compile main.py"` |
| Shell/scripts | *(leave empty — no build step)* |

## Test and Lint Commands

In addition to build verification, `project_config.yaml` supports `test_command` and `lint_command` keys used by [`/aitask-qa`](../../aitask-qa/) for test execution and linting.

```yaml
# Test command — used by /aitask-qa Step 4
test_command: "bash tests/test_*.sh"

# Lint command — used by /aitask-qa Step 4
lint_command: "shellcheck .aitask-scripts/aitask_*.sh"

# Multiple commands (run sequentially)
test_command:
  - "pytest tests/"
  - "npm test"
```

An **inline-list item** containing a comma must use the block (`- …`) form
instead: the inline `[a, b]` form splits on every comma, including one inside
quotes. A single scalar command is unaffected —
`test_command: "pytest -k 'a,b'"` is read whole.

These are distinct from `verify_build`:
- **`verify_build`** runs automatically after implementation (Step 9 of `/aitask-pick`) to catch build regressions
- **`test_command`** and **`lint_command`** run on demand when `/aitask-qa` analyzes a task's test coverage

### Auto-detection Fallback

When `test_command` is not configured, `/aitask-qa` auto-detects test files matching common patterns:

| Pattern | Language |
|---------|----------|
| `tests/test_*.sh` | Bash |
| `test_*.py` | Python |
| `*.spec.ts`, `*.test.ts` | TypeScript |
| `*_test.go` | Go |

Explicit configuration is recommended for reliable results — auto-detection may miss project-specific test layouts.

### Common Examples

| Project Type | `test_command` | `lint_command` |
|-------------|----------------|----------------|
| Shell/bash | `"bash tests/test_*.sh"` | `"shellcheck .aitask-scripts/*.sh"` |
| Python | `"pytest tests/"` | `"ruff check ."` |
| Node.js | `"npm test"` | `"npm run lint"` |
| Rust | `"cargo test"` | `"cargo clippy"` |
| Go | `"go test ./..."` | `"golangci-lint run"` |

## Reporting "did not run" from a command

Every non-zero exit from these three commands — `verify_build`, `test_command`
and `lint_command` — is treated as a failure by default. That is wrong for a
command that deliberately reports *"I did not run"*: a test runner serialized
behind a host-global lock, for example, exits without running anything when
another agent holds the lock. Recorded as a failure it also holds back every
task that depends on this one, because the `tests_pass` gate blocks dependents.

`gate_command_exit_contract` lists the command keys whose commands speak this
exit contract, so their exit `2` is read as a **skip** instead:

```yaml
test_command: "tools/run-tests.sh"

# test_command's exit 2 now means "did not run", not "failed"
gate_command_exit_contract: [test_command]
```

| Command exit | Key listed | Key not listed |
|---|---|---|
| `0` | pass | pass |
| `1` | fail | fail |
| `2` | **skip** — "evaluated, not applicable" | fail |
| anything else | fail | fail |

Only the documented code `2` qualifies — any other non-zero exit is a failure, so
an unexpected status can never become a skip.

### Where the rule applies

The contract covers **both** ways the framework runs these commands, so a project
gets one answer per command rather than two. What each path does with a skip
differs, because each has a different thing to do with it:

| Where the command runs | An opted-in exit `2` means |
|---|---|
| As a **gate** (`build_verified`, `tests_pass`, `lint`) | The gate is **satisfied** and dependents are released, while staying distinct from `pass` in the ledger history. |
| As the **build-verification step** after implementation (`/aitask-pick`, `/aitask-pickrem`, `/aitask-pickweb`) | The agent **proceeds** — it is not sent back to fix a build that never ran — and says so. On a profile that records gates, it is recorded as a `build_verified` **skip**. |
| In [`/aitask-qa`](../../aitask-qa/) test execution | The component is **N/A** in the health score (its weight is redistributed, not scored 0), and any "all tests pass" claim is reported as *unverified* — neither a pass nor a failure. |

A command that is simply **not configured** is a separate case everywhere: the
step is skipped and nothing is recorded.

**Why it is opt-in, and per key.** Exit `2` is not free to reserve: GNU `make`
exits 2 on a build error and `pytest` exits 2 on interrupt. Reserving it for
every project would turn `verify_build: "make"` failures into green gates. A
project may also want the contract on for `test_command` and off for
`verify_build`, so each key opts in separately.

**Accepted entries** are `verify_build`, `test_command` and `lint_command`.
Anything else is a typo: it is ignored — it never changes a result — and
reported (on the gate-run block's `Note:` line for a gate, and to the agent on
the build-verification path), so a misspelling does not look identical to
"not opted in".

**With a list of commands**, a failure stops the list and a skip does not: any
failure makes the whole run a failure, otherwise any skip makes it a skip,
otherwise it passes.
