---
Task: t1221_harden_codex_skill_launch_composer.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1221 — Harden Codex skill-launch composer

## Context

`build_invoke_command` converts argv into a single text prompt for skill-launch
operations. That representation cannot preserve an argument containing
whitespace: Claude Code and OpenCode use `${args[*]}`, while Codex reaches the
same result through `build_skill_prompt` and `"$*"`. The existing guard covers
only `work-report` and `trail`, leaving `pick`, `explain`, `qa`, `shadow`, and
`learn` vulnerable to silent argument-boundary changes. The Codex dispatch has
a second fail-open path: an operation accepted by `SUPPORTED_OPERATIONS` but
omitted from the nested composer case produces an empty prompt.

Repository call-site and test scans found no caller relying on embedded
whitespace for these skill-launch operations. Passthrough operations
(`batch-review`, `raw`) preserve argv and must remain outside the guard;
`explore` has no composed arguments.

## Implementation

1. Update `.aitask-scripts/aitask_codeagent.sh` in
   `build_invoke_command`:
   - Replace the `work-report|trail` condition with an explicit case covering
     every argument-bearing text-composed skill operation:
     `pick|explain|qa|shadow|learn|work-report|trail`.
   - Keep validation before per-agent dispatch and model command construction,
     and use a neutral local variable name because the guard is no longer
     work-report-specific.
   - Preserve the existing diagnostic contract: name the operation, state that
     whitespace cannot preserve slash-command argument boundaries, and include
     the rejected argument.
   - Add a wildcard arm to the nested Codex skill-composer case that calls
     `die "operation not wired into the codex composer: $operation"`. This
     makes additions to `SUPPORTED_OPERATIONS` fail at composition time until
     their Codex prompt mapping is wired.

2. Extend `tests/test_codeagent.sh` with focused regression coverage:
   - Iterate over `pick`, `explain`, `qa`, `shadow`, `learn`, `work-report`, and
     `trail`, asserting that a single whitespace-bearing argv element is
     rejected before a `DRY_RUN:` command can be emitted.
   - Assert that a normal whitespace-free skill argument still composes, and
     that a passthrough operation such as `raw` still accepts a
     whitespace-bearing argv element unchanged.
   - Create a temporary copy of `aitask_codeagent.sh`, add a test-only operation
     to its `SUPPORTED_OPERATIONS`, and invoke that operation under an explicit
     Codex agent string. Assert a nonzero exit, the exact "not wired" diagnostic,
     and absence of `DRY_RUN:`. This dynamically pins the otherwise unreachable
     wildcard arm without altering production operation metadata.

3. Verify the change:
   - Run `bash -n .aitask-scripts/aitask_codeagent.sh` and
     `bash -n tests/test_codeagent.sh`.
   - Run `bash tests/test_codeagent.sh` for the generalized contract and Codex
     composer regression.
   - Run the existing operation-specific suites
     `tests/test_codeagent_work_report.sh`, `tests/test_codeagent_trail.sh`,
     `tests/test_shadow_spawn_config.sh`, and
     `tests/test_shadow_spawn_learner.sh` to confirm current skill launch shapes
     remain intact.

4. After explicit user review, commit only the script and test as
   `bug: Harden Codex skill launch composition (t1221)`, then update this plan's
   Final Implementation Notes. Run the declared gate orchestration and archive
   t1221 through Step 9; profile `fast` works directly on `main`, so no task
   branch merge is required.

## Risk

### Code-health risk: low
None identified. The behavior change is a centralized fail-closed validation
on an already-lossy boundary, with passthrough argv operations excluded and
operation-specific regression suites retained.

### Goal-achievement risk: low
None identified. Dynamic mutation of a temporary script copy exercises the
future-operation omission path directly, while the operation loop covers every
current argument-bearing skill composer.

## Verification

- `bash -n .aitask-scripts/aitask_codeagent.sh`
- `bash -n tests/test_codeagent.sh`
- `bash tests/test_codeagent.sh`
- `bash tests/test_codeagent_work_report.sh`
- `bash tests/test_codeagent_trail.sh`
- `bash tests/test_shadow_spawn_config.sh`
- `bash tests/test_shadow_spawn_learner.sh`

