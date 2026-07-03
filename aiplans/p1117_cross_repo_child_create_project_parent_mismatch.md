---
Task: t1117_cross_repo_child_create_project_parent_mismatch.md
Worktree: .
Branch: main
Base branch: main
---

# Plan: Support Cross-Repo Child Creation

## Summary

Make `aitask_create.sh --project <name> --parent <id> --batch ...` work by
routing child creation into the target repo, while preserving a caller-usable
`--silent` contract and verifying real target-repo update/commit behavior.

## Implementation

- Update `.aitask-scripts/aitask_create.sh` so the cross-repo redirect allows
  `--parent` and preserves it in the forwarded argv.
- Track `--silent` during the redirect pre-parse. For project-routed silent
  calls, run the target script from the resolved root, capture stdout, preserve
  stderr and exit code, and translate the target-relative created path to an
  absolute path under the target root.
- Keep non-silent project-routed calls as direct `exec` into the target script.
- Update `aidocs/framework/cross_repo_references.md` and cross-repo assignment
  procedure copies to document that project-routed silent create output is an
  absolute target path.
- Replace the old `--project + --parent` rejection test with coverage for
  forwarding, real target child creation, committed update back-fill, and clean
  target/caller git state.

## Verification

- `bash -n .aitask-scripts/aitask_create.sh`
- `bash -n tests/test_create_project_flag.sh`
- `bash tests/test_create_project_flag.sh`
- `bash tests/test_update_cross_repo.sh`
- `bash tests/test_aitask_update_xdeps.sh`
- `bash tests/test_create_silent_stdout.sh`
- `bash tests/test_parallel_child_create.sh`

## Risk

### Code-health risk: low

- The behavior change is localized to create-side project routing. The target
  repo's existing child creation path remains authoritative. · severity: low ·
  -> mitigation: None

### Goal-achievement risk: low

- The implementation covers the documented child-create command, the silent
  stdout ambiguity, real committed update back-fill, and target git cleanliness.
  · severity: low · -> mitigation: None

## Final Implementation Notes

- **Actual work done:** Allowed `aitask_create.sh --project ... --parent ...`
  and made project-routed `--silent` output return an absolute target path.
  Added real cross-repo child creation/update tests and refreshed the related
  docs/procedure wording.
- **Deviations from plan:** None.
- **Issues encountered:** The parent `children_to_implement` assertion initially
  expected `100_1`; the framework stores child IDs as `t100_1`, so the test was
  corrected to match existing behavior.
- **Key decisions:** Only project-routed create silent output is normalized to
  an absolute path. Non-silent create and update output keep their existing
  behavior.
- **Upstream defects identified:** None
