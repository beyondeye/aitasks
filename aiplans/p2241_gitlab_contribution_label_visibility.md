---
Task: t2241_gitlab_contribution_label_visibility.md
Base branch: main
Output branch: main
---

# t2241 — GitLab: find contribution issues whose label was silently dropped

## Context

t2235 fixed GitHub: labels supplied by authors without push access are silently
dropped, so contribution issues are now found by the `contribution` label **or**
the `<!-- aitask-contribute-metadata` block. This task checks whether GitLab
behaves the same way and, if it does, ports the fix to the GitLab listing, the
GitLab CI job, and `gitlab_create_issue`.

## Step 1 — Evidence (DONE during planning): the behaviour is CONFIRMED

GitLab drops labels from non-members **silently**: the issue is created, the
labels are ignored, and no error is returned. Source was read at gitlab-org/gitlab
`master` = `a8f1a2df276bdcf7f0e612492ab5412f16de62fe` (2026-11-08):

- `app/services/issuable/callbacks/labels.rb` `after_initialize`:
  `return unless has_permission?(:"set_#{issuable.to_ability_name}_metadata")`.
  This returns early without raising, so the label params are never applied.
- `app/policies/issue_policy.rb:170`: `rule { ~persisted & can?(:set_new_issue_metadata) }.policy { enable :set_issue_metadata }`.
  The comment there reads "guest members need to be able to set issue metadata" (gitlab#300100).
- `config/authz/roles/guest.yml` grants `set_new_issue_metadata` /
  `set_new_work_item_metadata`. `config/authz/roles/public_authenticated.yml`
  (an authenticated non-member of a public project) grants `create_issue` and
  `create_work_item` but **no** `*_metadata` permission. `public_anonymous.yml`
  grants none either.
- The docs agree. The permissions page (footnote on "Edit issues, including
  metadata") says "Guest users can only set metadata when creating an issue".
  gitlab#537672 says "only members were allowed to associate metadata when
  creating issues". gitlab-ce#22666 reports the symptom: the issue is created
  and the labels are dropped with no error.

So an external contributor who is **not a project member** files an unlabeled
issue, and `glab issue create` exits 0. The label-filtered listing (glab and
REST) and the CI scheduled scan never see that issue. Members, from Guest up,
keep their label. This evidence is copied into the archived plan.

The mechanism was proved from source. The plan does not test it against a live
GitLab project, because no non-member account or test project is available.
That check is proposed below as a manual-verification follow-up.

## Step 2 — `.aitask-scripts/aitask_contribution_check.sh` (GitLab listing)

Replace `gitlab_list_contribution_issues` (currently lines 247-269) with the
t2235 design. Add two helpers next to it:

1. `_gitlab_select_contribution_issues`. It reads one **or more** JSON arrays of
   raw GitLab REST issues on stdin and normalises them to the shape
   `github_list_contribution_issues` returns (the shape the main loop consumes):
   ```bash
   jq -s --argjson limit "$ARG_LIMIT" '
       [ (add // [])[]
         | select(any(.labels[]?; . == "contribution")
                  or ((.description // "") | contains("<!-- aitask-contribute-metadata")))
         | {number: .iid, title, body: (.description // ""),
            labels: [.labels[]? | {name: .}], url: .web_url} ]
       | unique_by(.number) | sort_by(-.number) | .[:$limit]'
   ```
   The GitLab issues endpoint never returns merge requests, so there is no PR
   filter. Pages always arrive on stdin, never through `--argjson` (the
   128 KB argument limit).
2. `_gitlab_rest_all_pages <projects/...?query>`. This is the curl path. It
   computes the token header **once** (`hdr=$(_gitlab_token_header) || return 1`,
   which fails closed when `GITLAB_TOKEN` is missing). It then loops
   `&per_page=100&page=$page` and prints each page body. It stops when a page
   holds fewer than 100 items. If any page fails with curl `-f`, or a page is
   not a JSON array (`jq -e 'type == "array"'`), it returns 1. It has a hard
   cap of 1000 pages, after which it warns and returns 1, so a server that
   ignores `page` cannot loop forever. The caller captures everything first
   (`pages=$(...) || return 1`), so a failure part-way returns no partial list.
3. `gitlab_list_contribution_issues`:
   - glab path (`_gitlab_has_glab && [[ -z "$ARG_REPO" ]]`, unchanged
     selection): `pages=$(glab api --paginate "projects/:id/issues?state=opened&per_page=100") || return 1`.
     glab 1.126 documents `--paginate` JSON output as one merged array. Older
     glab printed consecutive arrays. `jq -s 'add'` handles both, and both are
     tested.
   - curl path: `pages=$(_gitlab_rest_all_pages "projects/$project_id/issues?state=opened") || return 1`.
   - then `printf '%s\n' "$pages" | _gitlab_select_contribution_issues`.
   - Add a comment block citing the GitLab permission evidence from Step 1. It
     replaces the old `--label contribution --all` path, which also listed
     **closed** issues.

`aitask_contribution_review.sh list-issues` and the overlap check both go
through `source_list_contribution_issues`, so both are fixed by this change.

## Step 3 — `.aitask-scripts/aitask_contribute.sh` (`gitlab_create_issue`)

This mirrors `github_create_issue` / `_github_verify_contribution_label`
(lines 191-243):
- When `glab issue create ... -l contribution` succeeds, call
  `_gitlab_verify_contribution_label "$repo" "$result"`, then echo the result
  and return 0.
- New `_gitlab_verify_contribution_label <repo> <create output>`:
  - It takes the URL from the create output with
    `grep -Eo 'https://[^[:space:]]+/-/issues/[0-9]+' | tail -1` and the iid
    with `${url##*/}`.
  - It reads the labels with
    `glab issue view "$iid" -R "$repo" -F json | jq -r '.labels[]?'`.
  - If the URL or the view is missing, it warns "Could not verify that the
    'contribution' label was applied…".
  - If the label is absent, it warns: "GitLab did not apply the 'contribution'
    label to $url — labels from authors who are not members of $repo are
    silently dropped. The issue was created; maintainers' tooling finds it by
    its aitask-contribute-metadata block."
  - It always returns 0.
- Fallback branch: use the GitHub wording ("…you lack permission to set labels
  there. Creating the issue without it."). Capture the exit code. On success,
  warn "The issue was created unlabeled. Maintainers' tooling still finds it by
  its aitask-contribute-metadata block."
- `--no-label` stays unchanged and never reads the label back.

## Step 4 — `.aitask-scripts/ci_templates/gitlab/contribution-check-job.yml`

**The six-hour cutoff is broken in the job's own runtime. This is inherited, and
it is fixed here.** The job runs `alpine:latest`, and `before_script` installs
`bash curl jq git` but no coreutils, so `date` is BusyBox. The BusyBox
`coreutils/date.c` usage (mirror/busybox master, read during planning) lists
only `@seconds_since_1970`, `hh:mm[:ss]`, `[YYYY.]MM.DD-hh:mm[:ss]`,
`YYYY-MM-DD hh:mm[:ss]` and `[[[[[YY]YY]MM]DD]hh]mm[.ss]` as TIME formats, and it
has no `-v` option. Both `date -u -d '6 hours ago'` and `date -u -v-6H`
therefore fail. With errexit on, the job dies. Without it, `SINCE` is empty.
Either way, no discovery request is ever sent.

Replace the `date` call with jq, which the job already installs.
`now`/`strftime` exist since jq 1.5, and `strftime` on a number uses gmtime,
which is UTC whatever `TZ` is (probed with jq 1.8.2 under `TZ=Asia/Tokyo`).
Validate the result and fail closed:
```sh
SINCE=$(jq -nr 'now - 21600 | strftime("%Y-%m-%dT%H:%M:%SZ")') \
  || { echo "ERROR: could not compute the 6-hour cutoff" >&2; exit 1; }
case "$SINCE" in
  [0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z) ;;
  *) echo "ERROR: invalid cutoff '$SINCE'" >&2; exit 1 ;;
esac
```
The script must stay **POSIX sh**. Alpine has no bash when the GitLab runner
detects the job shell, so `script:` runs under BusyBox ash. Use only `[ ]`,
`case`, `$(( ))` and `while :`, with no bashisms.

Scheduled mode: drop `labels=contribution` and replace the single
`per_page=50` request with a paginated loop. The loop keeps only contribution
issues, because the check script posts a "no fingerprint" comment on any issue
it is pointed at, so feeding it every updated issue would spam them:
```sh
PAGE=1; IIDS=""
while :; do
  BODY=$(curl -sf --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
    "$API_BASE/projects/$PROJECT_ID/issues?state=opened&updated_after=$SINCE&per_page=100&page=$PAGE") \
    || { echo "ERROR: could not list issues (page $PAGE)" >&2; exit 1; }
  IIDS="$IIDS $(printf '%s' "$BODY" | jq -r '.[]
    | select(any(.labels[]?; . == "contribution")
             or ((.description // "") | contains("<!-- aitask-contribute-metadata")))
    | .iid')" || exit 1
  [ "$(printf '%s' "$BODY" | jq 'length')" -lt 100 ] && break
  PAGE=$((PAGE + 1))
done
for iid in $IIDS; do ... (unchanged loop) ... done
```
Update the header comment: the scheduled scan covers issues updated in the last
6 hours that carry the label **or** the metadata block, because GitLab drops
labels supplied by non-members. Trigger mode stays unchanged. `ait setup`
writes this template only when no `.gitlab-ci.yml` exists, and that is
unchanged too. Existing installs are covered by the proposed mitigation below.

## Step 5 — Tests (reuse the t2235 stub pattern)

1. **New `tests/lib/glab_contribution_stub.sh`**.
   `glab_contribution_stub_install <dir>` writes fixtures and **executables**
   `glab` and `curl` into `<dir>/bin`. They are executables rather than
   functions because the CI-job test runs a separate shell. The caller prepends
   that directory to `PATH`.
   - Fixture `all.json` uses the raw GitLab REST shape (`iid`, `title`,
     `description`, `labels` as strings, `web_url`, `updated_at`), newest first.
     - #200-#299 are 100 newer ordinary issues.
     - #101 and #100 are **unlabeled** and carry metadata touching the same file
       (pairwise score 8).
     - #15 is labeled, with metadata on another file (score 5, control).
     - #14 is plain.
     - #12 is labeled, with no metadata.
     - Page 1 therefore holds no contribution.
   - The `curl` stub models the REST server. It parses `labels=`, `page=`,
     `per_page=` and `updated_after=`. **`labels=contribution` is applied on the
     server side**, so pre-fix code sees only #15 and #12. It also serves
     `/issues/<iid>` and logs argv to `curl_calls`. Knobs:
     - `GLAB_STUB_CURL_FAIL_PAGE=<n>`: exit 22 on page n.
   - The `glab` stub handles these commands:
     - `auth status` exits 0.
     - `api [--paginate] <endpoint>` returns page 1, or every page as one merged
       array.
     - `issue list --label contribution` returns labeled issues only, which
       models the old path.
     - `issue view <n> -F json` returns the issue.
     - Every call is logged to `glab_calls`.
   - glab knobs:
     - `GLAB_STUB_PAGINATE_FORMAT=concat` prints consecutive arrays instead.
     - `GLAB_STUB_API_FAIL=1` makes `glab api` fail.
2. **`tests/test_contribution_check.sh`**: add Tests 27-33 at top level. Like
   the existing tests they use no subshells, so the counters opt-in is not
   needed.
   - 27, curl path (`ARG_REPO=o/r`, `GITLAB_TOKEN=t`): the listing is
     `101,100,15,12`. The output keeps the `{number,title,body,labels:[{name}],url}`
     shape. `curl_calls` contains `page=2` and no `labels=`.
   - 28, glab path (`ARG_REPO=""`): same result, `glab_calls` has
     `api --paginate`, and there is no `issue list`.
   - 28b: the concat page format gives the same result.
   - 29: `ARG_LIMIT=2` gives `101,100` on both paths, so the limit applies after
     filtering.
   - 30: each of these returns non-zero with empty stdout, i.e. fails closed:
     - a page-2 curl failure;
     - a `glab api` failure;
     - unset `GITLAB_TOKEN`.
   - 31: `main 100 --platform gitlab --repo o/r --dry-run --silent` reports
     `[#101]` at `| 8 (high) |` and `[#15]` at `| 5 (likely) |`.
   - 32, fixture self-test: page 1 holds no contribution, and the stub's
     server-side `labels=contribution` returns exactly `15,12`. This shows the
     fixture reproduces the drop.
3. **`tests/test_contribution_review.sh`**: add Test 21c. It runs
   `cmd_list_issues` with `CHECK_PLATFORM=gitlab` through the stub. #100 and
   #101 are listed with `HAS_METADATA:true`, #12 is listed with
   `HAS_METADATA:false`, and #14 is not listed.
4. **`tests/test_contribute.sh`**: add Tests 44-47 for `gitlab_create_issue`,
   with a function `glab` stub in a subshell (the same shape as `_t2235_create`).
   The cases are dropped, kept, fallback, viewfail, and `--no-label` (no view
   call, no warning).
5. **New `tests/test_gitlab_contribution_job.py`** (unittest + PyYAML, as in
   `test_contribution_workflow_contract.py`). It loads the template and takes
   `contribution-check.script[0]`. It installs the stub through
   `bash -c '. tests/lib/glab_contribution_stub.sh; glab_contribution_stub_install "$d"'`.
   It runs the script in a scratch directory whose fake
   `.aitask-scripts/aitask_contribution_check.sh` records argv. The environment
   is `PATH=<d>/bin:…`, `GITLAB_TOKEN`, `CI_PROJECT_PATH=o/r`,
   `CI_API_V4_URL=https://gitlab.example/api/v4`, with no `ISSUE_IID`. The
   assertions:
   - the checked iids are exactly {101, 100, 15, 12};
   - every curl call carries `updated_after=` and none carries `labels=`;
   - a page-2 failure exits non-zero;
   - a structural assertion: the scheduled query has no `labels=contribution`
     and the jq predicate contains both clauses.
   - **Runtime parity for the cutoff, so a host with GNU date cannot hide the
     bug.**
     - Put a `date` stub first in `PATH` that models BusyBox. It exits 1 for
       any `-d` value that is not `@<digits>`, and for `-v`, and logs its argv.
     - The scheduled run must still succeed with that stub in place.
     - Every curl call must carry an `updated_after=` value that matches the ISO
       pattern and lies within 21600±120 s before the test's own `time.time()`.
     - Run the script under `sh`, and under `dash` when it is installed (it is
       not installed here, so that leg is skipped with a reason). Also run it
       under `bash --posix`, so bashisms are caught.
     - **Pre-fix control:** the shipped template, with its
       `date -d '6 hours ago'` line, must fail under the same stub, either with
       a non-zero exit or with no `updated_after=` value. This proves the stub
       models the defect.
   - The last line of verification is manual. Docker is not usable on this
     host (permission denied on the socket), so the real Alpine runtime cannot
     be run here. The step to run inside a real Alpine image goes into the
     `gitlab_contribution_live_verification` follow-up:
     `docker run --rm alpine:latest sh -c 'apk add -q jq && jq -nr "now - 21600 | strftime(\"%Y-%m-%dT%H:%M:%SZ\")"'`.

**Pre-fix controls.** In a scratch baseline worktree of HEAD (`git worktree add`
under the scratchpad, with no stash and no restore), copy in only the new
tests and the stub, then run them. The new GitLab assertions in 27/28/29/31,
21c, 44 and the job test must **FAIL** there, while the fixture self-tests and
the `kept`/`--no-label` controls pass. Record the per-assertion outcome in the
plan's Final Implementation Notes.

## Step 6 — Docs: `website/content/docs/workflows/contribute-and-manage/contribution-flow.md`

The docs describe the current state only.
- Line ~49: GitLab also drops labels, from authors who are not project members.
  The listing scans all open issues on GitHub **and GitLab**.
- Lines ~102-112: generalise "GitHub silently drops…" to cover GitLab, and add
  that `glab issue list --label contribution` / `labels=contribution` miss these
  issues too.
- "GitLab CI" section: the scheduled scan picks up recently updated issues that
  carry the label or the metadata block.
- Support matrix row "Contribution issue discovery": change GitLab to "Label or
  metadata (scans all open issues)".
- Run `cd website && python3 check_links.py --build`.

## Verification

- `bash tests/test_contribution_check.sh`, `bash tests/test_contribution_review.sh`,
  `bash tests/test_contribute.sh`. All must PASS, and the GitHub Tests 20-26
  must be unchanged.
- `bash tests/run_all_python_tests.sh --test-dir` on the new job test, plus
  `python3 -m unittest tests.test_gitlab_contribution_job tests.test_contribution_workflow_contract`.
- The pre-fix control run described in Step 5 above.
- `shellcheck .aitask-scripts/aitask_contribution_check.sh .aitask-scripts/aitask_contribute.sh tests/lib/glab_contribution_stub.sh`.
- `bash tests/test_setup_contribution_workflow.sh`, since setup installs the
  GitLab template.
- `cd website && python3 check_links.py --build`.

## Risk

### Code-health risk: medium
- The listing is rewritten on two transports (glab, curl), and the contribution predicate now lives in three places: the GitHub jq, the GitLab jq, and the CI-job jq. A later change to the marker could update one copy and miss the others. The job test's structural assertion on both predicate clauses limits this, but it is still duplication · severity: medium · → mitigation: TBD
- Scanning every open issue costs about N/100 API calls per overlap check on large GitLab projects. This is the same cost GitHub already pays, and the 1000-page cap fails closed · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- The CI job's runtime is Alpine with BusyBox ash and BusyBox date, not the test host. The inherited `date -d '6 hours ago'` cutoff fails there, which is now fixed with jq. A BusyBox-modelling `date` stub, a POSIX-shell run and a pre-fix control cover this on the host. Only the live run proves it in the real image · severity: medium · → mitigation: gitlab_contribution_live_verification
- The drop was proved from GitLab source and docs but not on a live GitLab. The output of glab's `:id` placeholder and `--paginate` is taken from `glab api --help` (1.126) and the stubs, not from a real server · severity: medium · → mitigation: gitlab_contribution_live_verification
- Existing GitLab installs keep their copied `.gitlab-ci.yml` job, which `ait setup` never edits, so their scheduled scan still filters on the label until the job is copied again · severity: medium · → mitigation: gitlab_stale_ci_job_hint

### Planned mitigations
- timing: after | name: gitlab_contribution_live_verification | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: the drop and the glab --paginate/:id behaviour were not tested on a live GitLab | desc: Using a non-member account on a GitLab test project, file via /aitask-contribute; confirm the dropped-label warning, that both the glab and curl listing paths find the issue, and that the scheduled CI job (alpine runtime) computes a valid 6-hour cutoff and checks it
- timing: after | name: gitlab_stale_ci_job_hint | type: enhancement | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: existing installs keep the label-filtered scheduled scan | desc: ait setup warns when an existing .gitlab-ci.yml still contains the old labels=contribution contribution-check scheduled scan and says to copy the template again

## Step 9 (Post-Implementation)

Work happens on the current branch (profile `fast`). Code and the plan are
committed separately (`bug: … (t2241)` and `ait: Update plan for t2241`), then
the task is archived through the standard Step 9 flow.

## Post-Review Changes

### Change Request 1 (2026-11-08 16:05)
- **Requested by user:** The scheduled-scan loop in `contribution-check-job.yml` had no page cap or progress check. Unlike `_gitlab_rest_all_pages`, it could run until the CI timeout if a server or proxy kept returning a full page (PLAUSIBLE, low).
- **Changes made:** The job loop now has `MAX_PAGES=1000`, matching the helper, and fails closed when it reaches the cap. Both the job loop and `_gitlab_rest_all_pages` gained a progress check: a page whose first iid equals the previous page's first iid means `page` is being ignored, so they fail at once instead of at the cap. The stub gained `GLAB_STUB_CURL_REPEAT_PAGE=1`, which ignores `page=`. New tests:
  - the helper returns 1 with no partial list after exactly 2 requests;
  - the job exits non-zero with "repeats page 1" after 2 curl calls and checks nothing;
  - a structural assertion on the job's page cap.
- **Files affected:** `.aitask-scripts/ci_templates/gitlab/contribution-check-job.yml`, `.aitask-scripts/aitask_contribution_check.sh`, `tests/lib/glab_contribution_stub.sh`, `tests/test_contribution_check.sh`, `tests/test_gitlab_contribution_job.py`

## Final Implementation Notes
- **Actual work done:** Implemented as planned.
  - The GitLab listing in `aitask_contribution_check.sh` is now a paginated scan of all open issues on both the glab path (`glab api --paginate projects/:id/issues?state=opened&per_page=100`) and the curl path (`_gitlab_rest_all_pages`). It keeps issues with the label OR the metadata block, through `_gitlab_select_contribution_issues`, and applies the limit after filtering.
  - `gitlab_create_issue` reads the label back through `_gitlab_verify_contribution_label`. The fallback branch uses the GitHub wording plus the "created unlabeled" notice.
  - The CI job's scheduled scan computes its cutoff with jq, paginates with a 1000-page cap and a repeated-page check, filters on label OR metadata, and fails closed.
  - The website doc is updated.
- **Deviations from plan:**
  - Plan-review concern: BusyBox `date` cannot compute the cutoff on `alpine:latest`. The job now uses jq instead, and a BusyBox-modelling `date` stub, POSIX-shell runs and a legacy-cutoff control cover it.
  - Post-review CR1: the page cap and repeated-page check described above.
  - `dash` is not installed on this host, so the job test drops that leg. It runs `sh`, which is bash in POSIX mode here, and `bash --posix`.
  - Fixture URLs use `gitlab.example`.
- **Issues encountered:**
  - The pre-fix control in a scratch worktree of HEAD (helper-only copy of the new tests and stub, removed afterwards) gave these results:
    - `test_contribution_check.sh` 19 failed / 94 passed, the failures being every GitLab listing, limit, fail-closed and overlap assertion;
    - `test_contribution_review.sh` 2 failed (unlabeled #100 and #101 not listed);
    - `test_contribute.sh` 5 failed (dropped and viewfail warnings, read-back, fallback wording);
    - the job test 5 of 6 failed (scheduled set `['15','12']`, cutoff called date, listing failure exited 0, structure).
  - The controls passed on the baseline: fixture self-test 32, the kept/no-label cases, trigger mode and the legacy-cutoff stub control.
  - The baseline also showed that the old curl path ran with an empty token header when `GITLAB_TOKEN` was unset: `die` inside `$(…)` only exits the subshell. The new helper computes the header once with `|| return 1`.
- **Key decisions:**
  - The stub models GitLab server-side, applying `labels=` filtering on the server, so pre-fix code reproduces the bug.
  - glab `--paginate` output is parsed with `jq -s add`, which accepts one merged array (glab 1.126) or one array per page.
  - The CI job checks only label-or-metadata issues, because the check script comments on any issue it is given.
  - Evidence for the GitLab drop comes from gitlab-org/gitlab `a8f1a2df276b` (Issuable::Callbacks::Labels, issue_policy.rb, and the role YAMLs guest vs public_authenticated). It is recorded in Step 1.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_contribution_check.sh:185-215 — every remaining GitLab curl call (fetch_issue, post_comment, add_label, list_repo_labels, has_overlap_comment) still passes "$(_gitlab_token_header)" inline, so a missing GITLAB_TOKEN sends an empty header instead of failing (die only exits the command substitution)`
  - `.aitask-scripts/ci_templates/bitbucket/contribution-check-pipeline.yml:30-33 — scheduled scan fetches one unpaginated page (pagelen=50) of open issues and runs the check script on every one, so non-contribution issues get a "no fingerprint" comment and older contributions beyond 50 are missed`
