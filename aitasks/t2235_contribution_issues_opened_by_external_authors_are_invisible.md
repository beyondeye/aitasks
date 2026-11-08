---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [git-integration, contribution]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
issue: https://github.com/beyondeye/aitasks/issues/16
implemented_with: claudecode/opus5_5
created_at: 2026-11-08 09:49
updated_at: 2026-11-08 12:25
---

Issue created: 2026-10-22 03:35:52

## Contribution issues opened by external authors are invisible to list-issues, overlap checks, and contribution-check.yml

## Summary

Contribution issues opened by external authors are invisible to the review and overlap tooling. The documented no-fork `/aitask-contribute` flow creates issues through `.aitask-scripts/aitask_contribute.sh`, which asks GitHub to apply the `contribution` label in the create request. GitHub silently drops labels for users without push access, and the script never reads the label back, so it reports success with an unlabeled issue. Every later consumer of contribution issues filters on that label: `aitask_contribution_review.sh list-issues`, the overlap check in `aitask_contribution_check.sh`, and the `contribution-check.yml` workflow, which only reacts to `issues.labeled`. As a result the contributor gets no warning and the maintainer's primary discovery path never shows the issue.

## Impact

<!-- report:impact -->
Any external contributor using the advertised no-fork contribution flow, and every downstream project that installed the workflow through `ait setup`, is affected. The issue is created successfully but the overlap analysis never runs, `list-issues` does not show it, and the review skill reports that there are no open contribution issues. The contribution silently stalls with no error shown to either side. The problem is latent in this repository today only because all current issues were authored by the owner (the sole open contribution issue, #15, is a maintainer-created labeled control case), but it is directly reachable by the first non-collaborator who uses the documented flow.
<!-- /report:impact -->

## Expected behavior

<!-- report:expected -->
An open issue whose body carries the `aitask-contribute-metadata` marker must be visible regardless of who created it: `list-issues` should list it with `HAS_METADATA:true`, the overlap check should scan it and report overlapping issues, and opening the issue should trigger the contribution-check workflow (or the label should be applied by a token that is allowed to apply it). This is the contract stated in `website/content/docs/workflows/contribute-and-manage/contribution-flow.md:47` ("a workflow runs automatically on new contribution issues") and `website/content/docs/skills/aitask-contribution-review.md:22` (the listing shows open issues that carry `aitask-contribute-metadata`).
<!-- /report:expected -->

## Actual behavior

<!-- report:actual -->
The issue is created without the `contribution` label and nothing warns the contributor. `aitask_contribution_review.sh list-issues` prints `NO_ISSUES` or omits the unlabeled metadata issue because it asks GitHub for `--label contribution`. `aitask_contribution_check.sh` never sees the issue in its scan, so an unlabeled metadata issue that overlaps another contribution is not reported. `.github/workflows/contribution-check.yml` never runs because its only trigger is `issues: types: [labeled]` and its job condition requires `github.event.label.name == 'contribution'`.
<!-- /report:actual -->

## Minimal reproduction

<!-- report:reproduction -->
1. Check out `beyondeye/aitasks` main at `4dbd3cd51f09be770e92f58f403e1570bbc24538` (current at the time of writing).
2. Put a deterministic `gh` stub on `PATH` that models the documented GitHub rule "Only users with push access can set labels for new issues. Labels are silently dropped otherwise." The stub ignores `--label contribution` for an external-author `gh issue create`, and implements `gh issue list --label contribution` by filtering on the stored labels. Seed its state with: labeled contribution issue #15 (control), plain issue #14 without metadata, and unlabeled metadata-bearing contribution issues #100 and #101 that touch the same file.
3. Run `source .aitask-scripts/aitask_contribute.sh` and call `github_create_issue beyondeye/aitasks "[Contribution] external test" "$metadata_body" false`. The call returns the new issue URL and emits no warning, while the created issue has no labels.
4. Run `bash .aitask-scripts/aitask_contribution_review.sh list-issues --platform github --repo beyondeye/aitasks --limit 50`. Issue #100 is absent (and plain issue #14 is not enumerated at all).
5. Run `bash .aitask-scripts/aitask_contribution_check.sh 100 --platform github --repo beyondeye/aitasks --dry-run --silent`. Overlapping issue #101 and its score of `8 (high)` are absent; only labeled #15 is reported with `5 (likely)`.
6. Inspect `.github/workflows/contribution-check.yml`; the only trigger is `types: [labeled]`, so an unlabeled `issues.opened` event runs nothing.
<!-- /report:reproduction -->

The reproduction is a deterministic assertion test (no network, no real GitHub writes). On current main it reports 7 passed / 5 failed / 12 total: two failures in the `list-issues` assertions, two in the overlap assertions, one in the workflow-trigger assertion. The same pass/fail lines were produced by three consecutive runs by the reporter and independently by two reviewers in separate worktrees.

## Root cause

<!-- report:root_cause -->
Three label-dependent components combine into one visibility gap. First, `.aitask-scripts/aitask_contribute.sh:202-211` (`github_create_issue`) calls `gh issue create ... --label "contribution"` and only warns and retries without the label when that command exits non-zero (`:209-211`). GitHub silently drops labels supplied by authors without push access, and `gh issue create` performs no label-permission preflight, so the common external-author path exits 0 with an unlabeled issue and never reaches the warning; the fallback path also creates an unlabeled issue. Second, `.github/workflows/contribution-check.yml:5,13` subscribes only to `issues.labeled` and requires `github.event.label.name == 'contribution'`; the same template is shipped to downstream repositories from `seed/ci/github/contribution-check.yml:10,18` by `ait setup`. Third, `.aitask-scripts/aitask_contribution_check.sh:120` lists candidates with `gh issue list --state open --label contribution`, and `.aitask-scripts/aitask_contribution_review.sh:526` (`cmd_list_issues`) reuses that same listing; `.claude/skills/aitask-contribution-review/SKILL.md:25-26` then turns a `NO_ISSUES` result into "No open contribution issues found." The Bitbucket backend already scans all open issues and filters by metadata, so metadata-based identification is the existing design rather than a new semantic.
<!-- /report:root_cause -->

## Suggested fix direction

- In `github_list_contribution_issues` (`aitask_contribution_check.sh`), drop the server-side `--label contribution` filter and rely on the existing metadata detection. The review command already emits `HAS_METADATA:true|false` per issue, and the check loop skips issues without a fingerprint. Because removal of the label filter makes the `--limit 50` cap newly relevant, consider a search query or pagination for busy repositories.
- Make the workflow also trigger on `issues.opened` and run when the body contains the `aitask-contribute-metadata` marker. Gate the opened branch so maintainer-created issues that arrive already labeled do not run twice (GitHub emits both `opened` and `labeled` for those), for example by skipping when the issue already has the `contribution` label; optionally add the label with `gh issue edit --add-label contribution`, noting that a `GITHUB_TOKEN`-generated label event does not re-trigger workflows, so the opened run must perform the check itself. Apply the same change to `seed/ci/github/contribution-check.yml`.
- After `gh issue create`, read the created issue back and verify the label was applied; if it is missing, emit a permission-aware warning instead of the current "label may not exist" text, and do not treat the unlabeled fallback as a clean success.
- Add regression coverage: a `gh` stub returning both labeled and unlabeled metadata issues for `tests/test_contribution_review.sh` and `tests/test_contribution_check.sh`, an assertion in `tests/test_contribute.sh` that a silently dropped label is surfaced, and a configuration assertion that the workflow listens for opened issues.

## Environment

- `beyondeye/aitasks` main at `4dbd3cd51f09be770e92f58f403e1570bbc24538` (issue #15 reports framework 0.32.0)
- GitHub.com; `gh` 2.96.0
- Reproduced on Windows 11 with Git Bash; the affected code is POSIX shell and the workflow is platform-independent
- Confirmed with two independent red receipts from separate worktrees on current main (implementer and reviewer runs)

## Related work

I checked open issues and pull requests before filing. #15 is the labeled control case that proves the workflow fires on the label event, and #14 is an unrelated documentation issue. There is no open PR, no remote fix branch, and no duplicate report for this visibility gap.


<!-- oss-candidate:0aa9e05e0066a637d3807aa8 -->

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T10:25:55Z status=pass attempt=1 type=human
