---
Task: t2247_fix_contribution_token_header_and_bitbucket_scan.md
Base branch: main
Output branch: main
---

# t2247 — Fail closed on a missing GitLab token; retire the Bitbucket contribution check

## Context

Spawned from t2241 (Step 8b upstream defects). The task names two defects:

1. **GitLab auth computed inside the curl argument.** In
   `curl --header "$(_gitlab_token_header)"`, `die` exits only the command
   substitution, so curl runs with an empty header. The request then fails as
   unauthenticated, with no clear error, or on a public project succeeds
   anonymously. t2241 fixed only `_gitlab_rest_all_pages`. This is reachable when
   glab is authenticated but `GITLAB_TOKEN` is unset (`gitlab_check_cli` accepts
   that) and either `--repo` is given (the REST branch) or
   `gitlab_has_overlap_comment` runs (it is REST-only).
2. **Bitbucket scheduled scan** (single unpaginated page; comments on
   non-contribution issues).

**Premise correction for (2), verified 2026-11-08.** Atlassian's Bitbucket Cloud
changelog entry of 20 August 2026, "Removal of native Bitbucket Cloud Issue
tracker", states that "the API endpoints that support Issue Tracker are now
fully removed"; the Community sunset announcement says Issues and Wikis are
removed from the app and the API. Bitbucket Server/Data Center never had native
issues. Every `api.bitbucket.org/2.0/repositories/…/issues` call in the
contribution check therefore targets a removed API, and paginating or filtering
it cannot produce a working scan. A pipeline installed today is also silently
green: in its `sh` step, `ISSUES=$(curl -sf … | jq -r …)` takes jq's exit
status, so a failing curl yields an empty list and the job succeeds having
checked nothing.

Revised outcome:
- **GitLab:** every REST call site fails closed with the helper's clear error
  before curl runs. The glab-only setup keeps a working idempotency lookup.
- **Bitbucket, contribution-check area only:** stop shipping and installing a
  pipeline that cannot work. Any Bitbucket run of the check or review script
  fails immediately with a clear "issue tracker removed" message. `ait setup`
  tells existing users that an installed pipeline is dead and should be removed.
  Docs say what is true now.
- **Out of scope, spun into a separate task:** the rest of the framework's
  Bitbucket-issue surface, and any replacement integration (for example Jira,
  where Atlassian migrates issues). That surface is `aitask_contribute.sh`
  issue creation, `aitask_issue_import.sh`, `aitask_issue_update.sh`, the board
  "BB" issue indicator, and the issue-related doc pages. Bitbucket pull requests
  are unaffected.

## Implementation

### 1. `.aitask-scripts/aitask_contribution_check.sh` — GitLab auth computed once

Apply this pattern to every inline site: `gitlab_fetch_issue`,
`gitlab_post_comment`, `gitlab_add_label` (one `hdr` shared by both curls), and
`gitlab_list_repo_labels`:

```bash
local hdr
hdr=$(_gitlab_token_header) || return 1
curl -sf --header "$hdr" ...
```

The helper's `die` text still reaches stderr, so the failure names
`GITLAB_TOKEN`. Callers already handle a non-zero return:
`target_json=$(source_fetch_issue …) || die`, `source_list_repo_labels … || echo ""`,
and `source_has_overlap_comment … 2>/dev/null`.

**`gitlab_has_overlap_comment`** gets the same glab branch every sibling has:
`if _gitlab_has_glab && [[ -z "$ARG_REPO" ]]` →
`glab api "projects/:id/issues/$issue_num/notes?per_page=100"`. Otherwise
`hdr=…|| return 1` + curl. Without the branch the fix regresses glab-only
setups. Today the empty header can still read notes anonymously on a public
project. After the fix the REST-only lookup would always fail, and `main()`
treats a failed lookup as "no comment yet", so it would post again on every
run.

### 2. `aitask_contribution_check.sh` — Bitbucket backend retired

- Add one helper:
  ```bash
  _bitbucket_issues_removed() {
      die "Bitbucket Cloud removed its native issue tracker and its API on 2026-08-20, so contribution checks cannot run on Bitbucket. Remove the 'contribution-check' custom pipeline from bitbucket-pipelines.yml."
  }
  ```
- Delete `_bitbucket_api_base`, `_bitbucket_repo_slug`, `_bitbucket_auth`, and
  every `bitbucket_*` backend function (`check_cli`, `fetch_issue`,
  `list_contribution_issues`, `post_comment`, `add_label`, `list_repo_labels`,
  `has_overlap_comment`). Each dispatcher's `bitbucket)` arm calls
  `_bitbucket_issues_removed`. `source_has_overlap_comment` keeps its
  `*) return 1` default.
- `main()` and `parse_args` keep accepting `--platform bitbucket` and
  auto-detection, so a Bitbucket run reaches `source_check_cli` and gets the
  message, not "Unknown platform". Update `show_help`: remove the Bitbucket
  env-var line, and note that Bitbucket is not supported because its issue
  tracker was removed.
- Update the header comment line ("Supports GitHub …, GitLab …, and Bitbucket").

### 3. `.aitask-scripts/aitask_contribution_review.sh`

- `review_gitlab_fetch_comments` (REST branch): the auth-once pattern.
  `cmd_fetch` already maps a failure to `[]`.
- Delete `review_bitbucket_fetch_comments`. Its dispatcher arm calls
  `_bitbucket_issues_removed`, which is sourced from the check script. Every
  review subcommand already runs `source_check_cli` first, so a Bitbucket
  review fails with the same message. Help text: same edit as the check script.

### 4. CI template and `ait setup`

- Delete `.aitask-scripts/ci_templates/bitbucket/contribution-check-pipeline.yml`
  (and its now-empty directory).
- `aitask_setup.sh`, contribution-workflow installer (≈ line 4810), in the
  `bitbucket)` arm: install nothing. Print
  `info "Bitbucket Cloud has no issue tracker (removed 2026-08-20) — no contribution-check pipeline is installed."`
  When `$project_dir/bitbucket-pipelines.yml` exists and contains
  `aitask_contribution_check.sh` (`grep -qF`), also `warn` that its
  `contribution-check` custom pipeline can no longer work (the job reports
  success while checking nothing) and should be removed by hand. Never edit the
  file; the "existing CI configuration is never edited" contract holds. Then
  `return` before the template lookup.
- Grep `aitask_setup.sh` and `install.sh`/packaging for any other reference to
  `ci_templates/bitbucket` (release tarball manifests, file lists) and drop it.

### 5. Tests

**`tests/lib/glab_contribution_stub.sh`** (additive; existing callers keep
working): curl logs its `--header` value to `curl_auth`. Both curl and
`glab api` serve `…/issues/<iid>/notes` from a notes fixture, matched before the
`*/issues/*` case. Issue #100 carries an `<!-- overlap-results` note, #101 has
none. Build the notes fixture from a **real capture** of the REST notes
response (see Verification); do not invent its shape.

**`tests/test_contribution_check.sh`** — new top-level tests after Test 32 (no
subshell bodies, so the counters need no opt-in):
- *GitLab auth fails closed:* with `ARG_REPO=o/r` and `GITLAB_TOKEN=""`, each
  of `gitlab_fetch_issue`, `gitlab_post_comment`, `gitlab_add_label`,
  `gitlab_list_repo_labels` and `gitlab_has_overlap_comment` returns non-zero,
  its stderr names `GITLAB_TOKEN`, and `curl_calls` stays empty. Positive
  control: with the token set, every `curl_auth` line is
  `PRIVATE-TOKEN: test-token`.
- *glab-only overlap lookup:* with `ARG_REPO=""` and `GITLAB_TOKEN=""`,
  `gitlab_has_overlap_comment 100` → 0 and `… 101` → 1, through
  `glab api …/notes`, with no curl call.
- *glab-only `main` posts once:* `main 100 --platform gitlab --silent` (no
  `--repo`, no token, glab stub) sees the existing note, reports "already
  exists", and makes no `glab issue note` call.
- *Bitbucket retired:* `main 42 --platform bitbucket` exits non-zero, stderr
  contains `removed its native issue tracker`, and a curl-recording stub on
  PATH logs no call. Plus a static check that no `bitbucket_*` /
  `_bitbucket_auth` function remains (`declare -F`).

**`tests/test_contribution_review.sh`:** `review_gitlab_fetch_comments`
(`ARG_REPO` set, no token) returns non-zero with no curl call. A Bitbucket
review subcommand fails with the removal message.

**`tests/test_setup_contribution_workflow.sh` case (h)**, Bitbucket half:
- an absent `bitbucket-pipelines.yml` is **not** created, and the output
  contains `no contribution-check pipeline is installed`;
- an existing file without the check is byte-identical and gets no dead-pipeline
  warning;
- an existing file referencing `aitask_contribution_check.sh` is byte-identical
  and the output contains the dead-pipeline warning.
The GitLab half stays unchanged.

### 6. Docs

`website/content/docs/workflows/contribute-and-manage/contribution-flow.md`:
- the "Bitbucket Pipelines" CI subsection becomes a short note: Bitbucket Cloud
  no longer has an issue tracker, so the contribution check and its pipeline
  are not available on Bitbucket. Remove an existing `contribution-check`
  custom pipeline by hand;
- Manual Setup: remove the Bitbucket bullet and its YAML example;
- the label sentence ("GitHub/GitLab only — Bitbucket has no label support"):
  drop the Bitbucket clause;
- Platform matrix: change the Bitbucket column to "Not available (issue tracker
  removed)" on the contribution-check rows, and remove the token row's Bitbucket
  variables.

This is current-state prose only (`aidocs/framework/documentation_conventions.md`),
and the docs pages owned by the follow-up task are left alone. Run
`python3 check_links.py --build` in `website/`.

### 7. Separate task (created after plan approval, before implementation)

`aitask_create.sh --batch`, issue_type `chore`, labels
`git-integration, contribution`, depends `[]`: "Retire Bitbucket native-issue
support across the framework". Its body:
- the Atlassian evidence (changelog entry + Community sunset);
- the inventory: `aitask_contribute.sh` (`bitbucket_create_issue` …),
  `aitask_issue_import.sh`, `aitask_issue_update.sh`, `lib/task_utils.sh` /
  `lib/repo_fetch.sh` Bitbucket issue helpers if any, the board "BB" issue
  indicator (`board_widgets.py`, `tests/test_textual_markup_structure.py`), the
  `aitask-contribute` / `aitask-contribution-review` skills, and the
  issue-related website pages (`commands/issue-integration.md`,
  `workflows/issue-tracker.md`, `skills/aitask-contribute.md`,
  `contribute-and-manage/_index.md`, `development/task-format.md`,
  `tuis/board/*`);
- the boundary: Bitbucket PRs (`aitask_pr_import.sh` / `aitask_pr_close.sh`) and
  remote auth stay;
- that a replacement (Jira Cloud) integration is a design decision for its own
  task, not part of the retirement.

## Verification

- `bash tests/test_contribution_check.sh`, `bash tests/test_contribution_review.sh`,
  `bash tests/test_setup_contribution_workflow.sh`, `bash tests/test_contribute.sh`;
  `python3 -m pytest tests/test_gitlab_contribution_job.py tests/test_contribution_workflow_contract.py`
  — all pass.
- **Pre-fix controls** in a helper-only baseline worktree of HEAD: copy only the
  new and changed tests and stub in; never stash, never restore the shared
  tree. The GitLab auth and glab-only lookup tests fail there (curl is called
  with an empty header; the lookup always fails), and so do the Bitbucket and
  setup expectations.
- **Live GitLab check (local CE harness, t2248 recipe; images
  `gitlab/gitlab-ce:19.4.5-ce.0` present):** boot the container, then create a
  project with issues #1 (with a note containing `<!-- overlap-results`) and #2.
  With glab logged in (`--insecure-storage`) and `GITLAB_TOKEN` unset:
  (a) `gitlab_has_overlap_comment` via glab returns 0 for #1 and 1 for #2;
  (b) with `--repo`, `gitlab_fetch_issue` fails with the `GITLAB_TOKEN` message
  and the CE log shows no request.
  Capture the real `…/notes` JSON as the stub fixture source. If the harness
  cannot boot in this session, say so, keep the stub fixture shaped only by the
  documented REST notes fields the code reads (`.body`), and record it as not
  live-verified.
- `shellcheck .aitask-scripts/aitask_contribution_check.sh .aitask-scripts/aitask_contribution_review.sh .aitask-scripts/aitask_setup.sh`.
- `grep -rn '"$(_gitlab_token_header)"\|_bitbucket_auth\|ci_templates/bitbucket' .aitask-scripts/ tests/`
  → no hits.

## Post-implementation

Step 9: commit code (`bug: … (t2247)`), commit the plan via `./ait git`, archive.

## Risk

### Code-health risk: low
- `gitlab_has_overlap_comment` gains a glab branch, which changes which client answers the idempotency lookup in glab-only setups. It is localized, follows the sibling functions' shape, and is stub-tested and live-checked · severity: low · → mitigation: none
- Deleting the Bitbucket backend leaves `--platform bitbucket` accepted but failing. That is intended, so the message is reachable, and a test covers it · severity: low · → mitigation: none

### Goal-achievement risk: low
- The rest of the framework still calls the removed Bitbucket issue API until the separate retirement task lands. That is deliberately out of scope, with an inventory handed to that task · severity: low · → mitigation: none

## Post-Review Changes

### Change Request 1 (2026-11-08 22:40)
- **Requested by user:** three verified review concerns.
  1. (blocking) The deleted Bitbucket template was missing from `.aitask-scripts/retired_scripts_manifest.txt`, so upgraded projects (install.sh extracts additively) would keep it.
  2. (follow-up) The notes lookup reads only the first 100 notes.
  3. (follow-up) `echo | grep -qF` under pipefail returns 141 on a large body.
- **Changes made:**
  1. Regenerated the manifest with its header recipe, run against a scratch copy of the index with the deletion staged (the recipe reads `git ls-files`). It gained exactly `FILE .aitask-scripts/ci_templates/bitbucket/contribution-check-pipeline.yml` and `SHA c955db589c2f0c66b3b602cc2102eef069d90204`; t2247 was added to its "Retired by" line. Verified in an isolated worktree with the deletion staged:
     - `test_retired_scripts_manifest.sh` 27/27 and `test_prune_retired_skills.sh` 88/88.
     - `test_upgrade_prunes_retired_scripts.sh` 107/107 in 4 consecutive runs. Two earlier runs failed: one with empty output and rc=1, one with 63 failures and git "not a git repository / filesystem boundary" errors in /tmp fixtures, under load ~12 from concurrent sessions. That did not reproduce, and a pristine-HEAD control passed 3/3.
     - Direct pruner check: with the new manifest a pristine template copy is PRUNED and an edited copy is KEPT (`unrecognized-content`); with the HEAD manifest a pristine copy stays.
  2–3. Confirmed (SIGPIPE reproduced: rc=141 vs substring test 0) and pre-existing. Created follow-up t2252, which also covers the GitHub lookup with the same pipeline and the other first-page-only reads.
- **Files affected:** `.aitask-scripts/retired_scripts_manifest.txt`

## Final Implementation Notes
- **Actual work done:**
  - GitLab: every REST site in `aitask_contribution_check.sh` (`fetch_issue`, `post_comment`, `add_label`, `list_repo_labels`, `has_overlap_comment`) and `review_gitlab_fetch_comments` builds the header once (`hdr=$(_gitlab_token_header) || return 1`). `gitlab_has_overlap_comment` gained the glab branch (`glab api projects/:id/issues/<iid>/notes`).
  - Bitbucket contribution check retired: every `bitbucket_*` / `_bitbucket_*` backend was removed from the check and review scripts, and each dispatcher arm calls `_bitbucket_issues_removed` (a clear die). Help text and the platform error messages now drop bitbucket.
  - The CI template was deleted and recorded in `retired_scripts_manifest.txt`.
  - `ait setup`: no Bitbucket install; the label message is updated; a warning fires when an existing `bitbucket-pipelines.yml` still runs the check.
  - Docs (`contribution-flow.md`): Bitbucket section, Manual Setup, matrix, `--platform` / `--limit` rows.
  - Tests: check Tests 33–37, review Tests 29–30, setup case (h) Bitbucket half. The glab stub now logs headers (`curl_auth`), serves notes and labels, and has the `GLAB_STUB_CURL_REQUIRE_TOKEN` knob.
- **Deviations from plan:**
  - The Bitbucket scope was replaced at plan review: the original pagination/BBQL plan was rejected, because Atlassian removed the issue tracker API on 2026-08-20. The approved plan reflects that.
  - Added the `retired_scripts_manifest.txt` entry at code review (missed in the plan).
- **Issues encountered:**
  - Test globals leaked from Test 31 (`ARG_DRY_RUN` / `ARG_SILENT`), which would have made the "posts nothing" assertion vacuous. Test 36 now resets them.
  - `git rm` staged the template deletion in the shared index; it was unstaged at once and is committed by path.
  - An exported `GIT_INDEX_FILE` leaks into tests' scratch repos, so the staged-deletion verification moved to an isolated worktree.
  - `test_upgrade_prunes_retired_scripts.sh` failed in 2 early runs (empty output / git-discovery errors in /tmp fixtures, under load from concurrent sessions). It did not reproduce: 4/4 passes after that, and the pristine-HEAD control passed 3/3.
- **Key decisions:**
  - Keep `--platform bitbucket` accepted, so the removal message is reachable instead of "Unknown platform".
  - Never edit an existing `bitbucket-pipelines.yml`; only warn.
  - The stub's notes fixture is a sanitized real GitLab CE 19.4.5 capture.
  - **Live check** (local GitLab CE 19.4.5, private project, glab logged in, `GITLAB_TOKEN` unset):
    - new code, glab-only: `has_overlap #1`=0 and `#2`=1, with 0 REST requests;
    - new code, `--repo` without a token: fails with the `GITLAB_TOKEN` message, 0 requests;
    - HEAD: an empty-header request each time, and the glab-only lookup failed on #1 (duplicate-post path);
    - new code with the token: works.
  - **Pre-fix controls** (HEAD + new tests): 18/5/3 failures in check/review/setup, all for the intended reasons.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_contribution_check.sh:451,469 — `echo "$x" | grep -qF "<!-- overlap-results"` under pipefail returns 141 (SIGPIPE) on a large body with an early marker, so main() posts a duplicate analysis (already filed as t2252)`
  - `.aitask-scripts/aitask_contribution_check.sh:458,466 — overlap-comment notes lookup reads only the first 100 notes (glab and REST), missing an older analysis comment (already filed as t2252)`
  - `.aitask-scripts/aitask_contribute.sh, aitask_issue_import.sh, aitask_issue_update.sh — still call the removed Bitbucket Cloud issue API (already filed as t2251)`
