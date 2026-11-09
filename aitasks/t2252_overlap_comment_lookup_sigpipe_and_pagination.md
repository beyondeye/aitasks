---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git-integration, contribution]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2235
followup_kind: review_finding
implemented_with: claudecode/opus5_5
created_at: 2026-11-08 22:36
updated_at: 2026-11-09 15:49
---

## Origin

Raised in t2247's Step 8 review and verified there. Both defects predate t2247.

## Defects

Both make the overlap-comment idempotency lookup return "no existing analysis" when there is one. `main()` (`.aitask-scripts/aitask_contribution_check.sh`) treats any non-zero `source_has_overlap_comment` as "absent", so each one makes the check post a **duplicate** analysis comment on every run.

1. **SIGPIPE false negative.** `gitlab_has_overlap_comment` (`echo "$notes" | grep -qF "<!-- overlap-results"`) and `github_has_overlap_comment` (`echo "$comments" | grep -qF …`) run under `set -o pipefail`. When the marker comes early and the body exceeds the pipe buffer, `grep -q` exits first and `echo` dies with SIGPIPE, so the pipeline returns 141. Reproduced in t2247: a 400 KB notes body with the marker first gives `pipeline rc=141`, while `[[ "$notes" == *"<!-- overlap-results"* ]]` gives 0. Fix: replace both pipelines with a shell substring test.
2. **Notes pagination.** The GitLab lookup reads only the first page of notes (`…/issues/<iid>/notes?per_page=100`), on both the glab branch (added by t2247) and the REST branch. An analysis comment behind 100 newer notes is missed. GitLab returns notes newest-first by default (seen in t2247's live capture from GitLab CE 19.4.5), so the analysis comment, which is posted early, is the one that falls off page 1. Fix: paginate. Use `glab api --paginate` (glab 1.126 prints one JSON array per page; read it with `jq -s 'add'`). REST should follow the `_gitlab_rest_all_pages` shape (header once, repeated-page check, page cap). Check whether `gh … --json comments` on the GitHub side is complete for long threads.

Related sites with the same first-page-only read: `review_gitlab_fetch_comments` (`.aitask-scripts/aitask_contribution_review.sh`, `notes?per_page=100`) and `gitlab_list_repo_labels` (`labels?per_page=100`). Fix them in the same pass, or say why not.

## Tests

Extend `tests/lib/glab_contribution_stub.sh`. Its notes fixture is a real GitLab CE 19.4.5 capture, so keep that shape and do not hand-edit it. Add knobs to serve:
- (a) a large notes response with the marker first (SIGPIPE case);
- (b) more than 100 notes with the marker on page 2, on both the glab and curl paths.

Add a pre-fix control showing each new test fails against the current code. The GitHub side needs the same two cases through `tests/lib/gh_contribution_stub.sh`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-09T13:49:54Z status=pass attempt=1 type=human
