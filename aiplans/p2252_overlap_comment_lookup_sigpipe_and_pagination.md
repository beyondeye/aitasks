---
Task: t2252_overlap_comment_lookup_sigpipe_and_pagination.md
Base branch: main
Output branch: main
---

# t2252 — overlap-comment lookup: SIGPIPE false negative + notes pagination

## Context

`main()` in `.aitask-scripts/aitask_contribution_check.sh` posts the overlap
analysis unless `source_has_overlap_comment` returns 0. Any false non-zero
therefore posts a **duplicate** analysis comment. Two pre-existing defects (from
t2247's review) cause one:

1. **SIGPIPE.** `github_has_overlap_comment` / `gitlab_has_overlap_comment` end in
   `echo "$x" | grep -qF "<!-- overlap-results"` under `pipefail`. Reproduced in
   this session: a 400 KB body with the marker first gives `rc=141` on 5/5 runs.
   `[[ "$x" == *"<!-- overlap-results"* ]]` takes ~16 ms per 1 MB.
2. **First page only.** The GitLab lookup reads `notes?per_page=100` once, on both
   the glab and REST paths. GitLab lists notes newest first, so the early analysis
   comment is the one that falls off.

Findings from exploration, all read from real code:

- **GitHub is complete.** In gh v2.102.1 source, `--json comments` queries
  `comments(first: 100){…pageInfo{hasNextPage,endCursor}}`
  (`api/query_builder.go`), and `preloadIssueComments`
  (`pkg/cmd/issue/view/http.go`) loops until `!HasNextPage`.
- **`review_gitlab_fetch_comments` glab branch has never returned a comment.**
  In glab v1.126.0 (`internal/commands/issuable/view/issuable_view.go`),
  `issue view -F json` prints notes only with `--comments`. Even then it prints
  one page (default 20), under a Go field `Notes` that has no json tag, so
  `jq '[.notes[] …]'` fails and the callers fall back to `[]`. The REST branch
  reads only the first 100 notes.
- **`gitlab_list_repo_labels` reads one page:** 30 labels on glab
  (`glab label list` has `-P --per-page (30)`), 100 on REST.
- **`_gitlab_rest_all_pages` repeat check keys on `.[0].iid`.** Notes and labels
  have only `id`.
- **`_gitlab_rest_all_pages` already prints a page only after validating it**
  (array check, repeat check). On failure, everything it printed is therefore a
  page that was read whole.
- **Pagination makes two review defects reachable:**
  - `cmd_fetch` passes comments through `--argjson` (Linux 128 KB single-argument
    cap).
  - `parse_overlap_from_comments` takes the `last` analysis as current; on
    GitLab, newest first, that is the oldest one.
- **CI callers:**
  - The GitHub workflow runs the check once per issue event.
  - The GitLab job's trigger mode runs it once.
  - The GitLab scheduled scan runs it per issue with `|| true`.
- **Stub consumers:** `tests/test_contribution_check.sh`,
  `tests/test_contribution_review.sh`, and `tests/test_gitlab_contribution_job.py`
  (curl `*/issues` route only, kept byte-identical).
- **Docs:** `website/content/docs/workflows/contribute-and-manage/contribution-flow.md:82`
  says the check is idempotent. It needs the incomplete-read outcome. t2249 just
  committed this file (`47b007e54`), and it is clean now.

### Lookup verdict (reviewer concern 1)

A lookup that pages can fail after page 1. The pre-fix code never requested
page 2, so a page-1 marker always counted. Treating a later-page failure as
"absent" would introduce a **new** duplicate path. The lookup therefore returns
a three-way verdict:

| rc | meaning | `main()` |
|---|---|---|
| 0 | a comment that was **read** carries the marker, even if a later page failed | skip ("already exists") |
| 1 | **every** comment was read and none carries it | post |
| 2 | the read was incomplete and the part read has none — **unknown** | post nothing, warn, exit non-zero |

This covers every failure: a later page, a repeated page, a non-array page, the
page cap, a total failure, a failed `gh issue view`, or a missing token.

- **Before:** all of these read as absence and posted.
- **After:** they post nothing. The run reports a failure, so a re-run decides:
  - the GitHub workflow run and the GitLab trigger job go red;
  - the scheduled scan logs it and continues (`|| true`).

The review fetch follows the same rule. It keeps the comments it did read, warns,
and never drops a page-1 analysis because page 2 failed.

**Out of scope:** `gh label list --limit 200` has the same cap class. Its worst
case is an auto-label that is not applied, never a duplicate. Mentioned in the
final notes only.

Work on the current branch (`main`); no worktree.

## Implementation

### 0. Start the live harness (background) and take a baseline
- Start `docker.io/gitlab/gitlab-ce:19.4.5-ce.0` (image already cached) in the
  background, with t2248's settings:
  - container `t2252-gitlab` on `127.0.0.1:8929`, `external_url 'http://localhost:8929'`;
  - 2 Puma workers, Sidekiq concurrency 5;
  - Prometheus, KAS and registry off.

  Readiness: poll `/users/sign_in` for 200, about 9 min. Secrets go in mode-600
  files in the scratchpad and are never echoed.
- Record `git rev-parse HEAD` as `<start>`. Run the three stub consumers on the
  unchanged tree and record their pass counts.

### 1. `.aitask-scripts/aitask_contribution_check.sh`
1. **`_gitlab_rest_all_pages`:**
   - Use `?` as the separator when `path` has no query.
   - Key the repeat check on `.[0] | (.iid // .id) // empty`.
   - Change the warnings to "GitLab listing …", keeping "repeats page" and `$path`.
   - Update the header to say: on failure the printed pages are whole pages read
     before it; a caller may use them only as positive evidence, never as a
     complete list. The issues listing keeps discarding them.
2. **New `_gitlab_issue_notes <iid>`.** It prints ONE JSON array of notes in
   GitLab order and returns 0 only when complete.
   - glab: `glab api --paginate "projects/:id/issues/<iid>/notes?per_page=100"`.
   - REST: `_gitlab_rest_all_pages "projects/<pid>/issues/<iid>/notes"`.
   - In both cases `pages=$(…) || complete=1`.
   - Pages go via stdin into
     `jq -c 'if type=="array" then .[] else error(…) end' 2>/dev/null || complete=1`.
     That gives one note per line from each value that parsed whole as an array.
     It reads glab's per-page output and the merged form alike.
   - The notes are re-slurped with `jq -s .` (empty input gives `[]`), then
     `return "$complete"`.
3. **New `_overlap_lookup_verdict <bodies> <complete>`.** It holds the
   substring test `[[ "$1" == *"<!-- overlap-results"* ]] && return 0`, then
   returns 1 if complete and 2 otherwise. Comment: why it is not `| grep -q`
   (SIGPIPE).
4. **`gitlab_has_overlap_comment`:**
   `notes=$(_gitlab_issue_notes …) || complete=false`; `bodies` from
   `jq -r '.[].body // empty'`; then `_overlap_lookup_verdict`.
5. **`github_has_overlap_comment`:** the same verdict over
   `gh issue view … --json comments --jq '.comments[].body'`. A gh failure gives
   `complete=false`. One-line comment that gh pages through every comment itself.
6. **New `_post_overlap_comment_once`.** It replaces both copies of the
   lookup-then-post block in `main()`, the no-fingerprint branch and the normal
   branch.

   **Errexit is off inside it.** It is called in a conditional context, so
   `set -e` does not apply to its body or to anything it calls. The inline
   original sat in an `else` body, where errexit applied, so a failed post
   exited the script. A probe in this session: the draft shape returns rc=0 and
   prints "Posted complete"; the old code exits 22; the explicit check returns
   rc=1. Every failure that matters is therefore checked explicitly:
   - The lookup runs **without** `2>/dev/null`, so the REST, glab or helper
     reason shows on stderr: `source_has_overlap_comment "$ARG_ISSUE" || lookup_rc=$?`.
   - rc 0 → info "already exists"; then `return 0`.
   - rc 1 → `if ! source_post_comment "$ARG_ISSUE" "$OVERLAP_COMMENT"; then warn "Failed to post the overlap analysis comment to issue #N."; return 2; fi`.
     "Posted …" is printed only after that check; then `return 0`.
   - Any other rc → warn: "Could not read every comment on issue #N, so it is
     unknown whether it already has an overlap analysis. Not posting, to avoid a
     duplicate; re-run the check." Then `return 1`.
   - The silent-mode `[[ … ]] && info` lines are followed by an explicit
     `return 0`, so a false test is never the helper's status.

   In `main()`:
   - **No-fingerprint branch:** `_post_overlap_comment_once || return 1`.
   - **Normal branch:** `local post_rc=0; _post_overlap_comment_once || post_rc=$?`.
     - `post_rc` = 2 (post failed) → `return 1` at once, with no labels and no
       completion line, as the old errexit exit did.
     - `post_rc` = 1 (unknown) → still apply labels; they are independent of the
       comment and are never duplicated. Then `return 1` before the
       "Overlap analysis complete" success line.
   - The script's exit status is 1 in both failure cases. Previously a failed
     post exited with the post command's own status.
7. **`gitlab_list_repo_labels`:**
   - glab: `glab api --paginate "projects/:id/labels?per_page=100"`.
   - REST: `_gitlab_rest_all_pages "projects/<pid>/labels"`.
   - Both: `jq -rs 'add // [] | .[].name'`. Labels stay all-or-nothing; the caller
     already maps failure to "no labels".

### 2. `.aitask-scripts/aitask_contribution_review.sh`
1. **`review_gitlab_fetch_comments`:**
   - Call `_gitlab_issue_notes`.
   - Print `jq '[sort_by(.created_at, .id)[] | {author: .author.username, body, createdAt: .created_at}]'`.
     Oldest first, as on GitHub, so `last` is the newest analysis.
   - Return 1 when the notes were incomplete, still having printed what was read.
   - Comment: the glab `issue view` finding.
2. **New `_review_comments <n>`.** It wraps `review_fetch_comments`. On non-zero
   it warns "Could not read every comment on issue #N; continuing with the
   comments that could be read". It keeps the output when
   `jq -e 'type=="array"'` passes, else `[]`.
   - `cmd_fetch` and `cmd_find_related` use it in place of the
     `… 2>/dev/null || echo "[]"` fallback.
3. **`cmd_fetch`:** replace `--argjson comments` with
   `printf '%s\n%s\n' "$issue_json" "$comments_json" | jq -s '.[0] + {comments: .[1]}'`.

### 3. `tests/lib/glab_contribution_stub.sh`
Leave the captured notes heredoc and the `*/issues` routes untouched.
- **Install-time variants,** derived by jq from the capture's two notes. Nothing
  is hand-written; ids are renumbered newest first:
  - `notes_100.large.json`: the analysis first, then 40 thanks notes of ~20 KB.
  - `notes_100.paged.json`: 150 notes, the analysis at index 120 (page 2).
  - `notes_100.long.json`: 150 notes, the analysis at index 10 (page 1).
  - `labels.json`: `[{id:1,name:"contribution"},{id:2,name:"area:scripts"}]`.
  - `labels.many.json`: 150 labels, `area:scripts` at index 120.
  - Label objects carry only the fields the code reads. They are not a capture;
    the live check covers the real shape.
- **Knobs:**
  - `GLAB_STUB_NOTES=<variant>` and `GLAB_STUB_LABELS=<variant>` select the
    fixture.
  - `GLAB_STUB_API_FAIL_PAGE=<n>`: `glab api --paginate` on notes or labels
    prints pages 1..n-1 in concat format (nothing in merged format), then
    exits 1.
  - `GLAB_STUB_NOTE_FAIL=1`: `glab issue note` exits 1. The stub always drains
    stdin into `note_body` first, as the real `-m -` reads it.
  - `GLAB_STUB_CURL_POST_FAIL=1`: a curl call carrying `--data` (the note POST)
    exits 22. `--data-urlencode` (the label PUT) is not affected.
- **curl:** the notes and labels routes return the `page`/`per_page` slice
  (default 20). The existing FAIL_PAGE, REPEAT_PAGE and REQUIRE_TOKEN knobs apply.
- **glab `api`:**
  - The path is the first non-flag argument.
  - notes and labels: page 1 only without `--paginate`. With `--paginate`, merged
    by default, or one array per page under `GLAB_STUB_PAGINATE_FORMAT=concat`.
  - The issues branch is unchanged.
- **glab `label list`:** model glab's real first page of 30 (`-P` honoured).
- **Header:** document the knobs. Correct the paginate note: concat is what a
  live glab 1.126 prints (t2248).

### 4. `tests/lib/gh_contribution_stub.sh`
- **New `_gh_stub_comments` heredoc.** It is a real `gh issue view --json comments`
  capture (gh 2.102.1, this repo's issue #8: its analysis comment and one owner
  comment), anonymised and re-pointed at `o/r` #100. Key set and types are kept;
  ids, urls, logins and table rows are replaced.
- **Install-time files:**
  - `comments_100.json`: the capture.
  - `comments_100.large.json`: the analysis first, then 40 owner comments of
    ~20 KB.
  - `comments_100.many.json`: 150 comments, the analysis at index 110.
  - `no_comments.json`: `{"comments":[]}`.
- **`gh issue view`:**
  - When `--json` lists `comments`, serve `comments_<n>[.<GH_STUB_COMMENTS>].json`,
    falling back to `no_comments.json`.
  - Apply `--jq` with `jq -r`.
  - `GH_STUB_VIEW_FAIL=1` exits 1 with no output.
  - Otherwise serve `issue<n>.json` if present, else `issue100.json`.
    Install `issue14.json`, the plain issue without metadata, for the
    no-fingerprint branch.
- **`gh issue comment`:** log to `comment_calls`. `GH_STUB_COMMENT_FAIL=1` logs
  the call, then exits 1.
- So that a separate `bash script …` process sees the stub, the install exports
  `GH_STUB_DIR`. Tests run `export -f gh _gh_stub_log` before such a run and
  `export -fn` afterwards.
- **Header:** document the knobs.

### 5. Tests
- New check tests go after Test 37, in `T2241_DIR` plus a fresh gh stub dir.
- New review tests go after Test 30, in `T2247_DIR` plus a fresh gh stub.
- Before each `main`, reset `ARG_DRY_RUN` and `ARG_SILENT`.
- "No POST" means: `comment_calls` is empty (gh); no `issue note` appears in
  `glab_calls`; and no `curl_calls` line ends in `/notes` (that is the POST URL).

#### Assertion classes and their `<start>` expectations (reviewer concern 2)

| class | meaning | on `<start>` | after |
|---|---|---|---|
| **D** | defect or new-policy demonstration | red | green |
| **C** | pre-existing assertion whose command contract this task changes | red, by construction | green |
| **S** | supporting check: fixture self-test, or an outcome the old code already had | green | green |
| **P** | pin of behaviour the old code already got right and the change must keep | green | green |

The acceptance rule for step 6: the failing set on `<start>` equals D ∪ C
**exactly**, matched by description. Every other assertion, pre-existing ones
included, is green on both.

**Changed pre-existing assertions (C):**

| where | change | purpose kept |
|---|---|---|
| check Test 33 loop | expected rc per call: `gitlab_has_overlap_comment 100` without a token → `2` (unknown, not absence); the other four stay `1` | fails closed, names `GITLAB_TOKEN`, sends no request |
| check Test 35 (`:497`) | `"api projects/:id/issues/100/notes"` → `"api --paginate projects/:id/issues/100/notes"` | the glab-only lookup is routed through glab; the "no REST request" line beside it is unchanged |

Review Test 29 stays unchanged and green: `review_gitlab_fetch_comments` still
returns 1 without a token.

**New — `tests/test_contribution_check.sh`:**

| test | assertion | class |
|---|---|---|
| 38 GH SIGPIPE (`large`) | old pipeline on the fixture's `--jq` stream → 141 | S |
| | `github_has_overlap_comment 100` → 0 | D |
| | non-dry `main` says "already exists" / no POST | D / D |
| | `main` exits 0 | S |
| 39 GH long thread (`many`) | analysis index ≥ 100 | S |
| | lookup → 0; `#101` → 1 (gh paginates itself; source cited in a comment) | P / P |
| 40 GH failed read (`GH_STUB_VIEW_FAIL=1`) | lookup → 2 | D |
| | `main`: no POST / exits 1 / warns "Not posting" | D / D / D |
| 41 GL SIGPIPE (`large`) | old pipeline on `jq -r '.[].body'` → 141 | S |
| | REST lookup → 0 / glab lookup → 0 | D / D |
| 42 GL pagination (`paged`) | REST `page=1` and non-paginated `glab api` lack the marker | S / S |
| | REST lookup → 0 / `curl_calls` has `notes?per_page=100&page=2` | D / D |
| | glab lookup → 0 / `glab_calls` has `api --paginate projects/:id/issues/100/notes` / concat format → 0 | D / D / D |
| 43 GL incomplete reads | `long` + REST `FAIL_PAGE=2` → 0 (page-1 marker kept) | P |
| | `long` + glab `API_FAIL_PAGE=2` concat → 0 | P |
| | `long` + glab `API_FAIL_PAGE=2` merged → rc ≠ 1 (never absence) | P |
| | `paged` + REST `FAIL_PAGE=2` → 2 | D |
| | `paged` + `REPEAT_PAGE` → 2 after exactly 2 requests | D |
| | REST `FAIL_PAGE=1` → 2 / glab `API_FAIL` → 2 / `paged` + glab `API_FAIL_PAGE=2` concat → 2 | D / D / D |
| 44 GL `main()` outcomes | `paged`, REST and glab: "already exists" / no POST | D / D |
| | `paged`, REST and glab: exits 0 | S |
| | page-1 marker + later-page failure (`long` + REST `FAIL_PAGE=2`; `long` + glab `API_FAIL_PAGE=2`, concat and merged): no POST | P |
| | `paged` + later-page failure, REST and glab: no POST / exits 1 / warns "Not posting" | D / D / D |
| 45 GL labels (`many`) | REST page 1 and `glab label list -F json` lack `area:scripts` | S / S |
| | REST includes it / requests `page=2` / glab includes it / via `api --paginate projects/:id/labels` | D / D / D / D |
| | `REPEAT_PAGE` → non-zero | D |
| 46 a failed POST propagates, run as the **real script process** (`bash "$PROJECT_DIR/.aitask-scripts/aitask_contribution_check.sh" …`) for production `set -euo pipefail` semantics. The lookup reads absent: fingerprint branch on `#101`, no-fingerprint branch on `#14`. Platforms: GitHub (`GH_STUB_COMMENT_FAIL=1`), GitLab REST (`--repo o/r`, `GLAB_STUB_CURL_POST_FAIL=1`), GitLab glab (no `--repo`, `GLAB_STUB_NOTE_FAIL=1`). That is 6 runs | each: exits non-zero / output lacks "Posted overlap analysis comment" / output lacks "Overlap analysis complete" | P / P / P |
| | each: the POST was attempted (`comment_calls`, a `curl_calls` line ending `/notes`, or `issue note` in `glab_calls`), so the failure is the post's own | S |
| | positive control, the same 6 runs without the knob: exit 0 and "Posted overlap analysis comment" present, so "lacks Posted" cannot pass vacuously | S |

Test 46's rows are P, not D. On `<start>` the inline post sat in an `else` body
under errexit, so the old script already exited non-zero with no "Posted". They
pin that behaviour, and they would have caught the draft helper that swallowed
the failure.

**New — `tests/test_contribution_review.sh`:**

| test | assertion | class |
|---|---|---|
| 31 every page (`paged`) | REST length 150 / glab length 150 / glab output has the marker | D / D / D |
| | glab via `api --paginate`, no `issue view` | D |
| 32 oldest first (`twice`, written by jq from the capture: newer analysis id 3 `30:7`, thanks id 2, older id 1 `10:8`, single-line markers as `format_overlap_comment` emits) | REST and glab `parse_overlap_from_comments` yield `OVERLAP:30:7` and no `OVERLAP:10` | D |
| 33 `cmd_fetch` > 128 KB (`large`) | GL REST / GL glab / GH: exit 0 and `.comments \| length` = 41 | D / D / D |
| 34 incomplete read keeps what was read (`long` + REST `FAIL_PAGE=2`) | output still holds the analysis (`parse_overlap_from_comments` ≠ `NO_BOT_COMMENT`) | P |
| | `review_gitlab_fetch_comments` → 1 | D |
| | `cmd_fetch` warns "Could not read every comment" on stderr and still exits 0 | D |

### 6. Pre-fix control (one-off; the evidence goes into Final Implementation Notes)
- First check that
  `git diff <start> HEAD -- .aitask-scripts/aitask_contribution_*.sh` is empty.
- Build the baseline tree in the scratchpad: `git archive <start> .aitask-scripts`
  plus copies of the new `tests/lib/*` and the two test files.
- Run both files and extract the failing descriptions. Compare them to the
  D ∪ C list above and paste both lists.
- Any mismatch is investigated, never waved through: a D that is green on the
  baseline, or a P or S that is red.

### 7. Live GitLab CE check (user-requested; scripts in the scratchpad)
1. **Seed:**
   - Seed a root token with `gitlab-rails runner` (`set_token`, `--env-file`).
   - Create user `maint` and its token; create public project `maint/aitask-ct`.
   - Issue #1 (metadata body): run the new check once, which posts the real
     analysis, then post 149 thanks notes after it.
   - Create 150 filler labels plus `area:scripts`, named so it sorts past page 1.
     Check that live.
   - Issue #2: post one ~400 KB note, then run the check. Newest first, the
     analysis then leads the stream: the live SIGPIPE shape.
   - Give `maint` a glab config (`--insecure-storage`, `api_protocol http`) and a
     scratch checkout whose origin is the local project.
2. **Live self-checks:**
   - REST `notes?per_page=100&page=1` of #1 lacks the marker (newest-first order,
     live).
   - Count the arrays in raw `glab api --paginate …/notes?per_page=100` output
     and save it as evidence.
   - REST page 1 and `glab label list -F json` lack `area:scripts`.
3. **New code, REST and glab:**
   - `main` on #1 and #2 says "already exists", and the note counts are unchanged.
   - Labels include `area:scripts`.
   - Review `fetch 1`: 150 comments, oldest first.
   - Review `find-related 1`: no `NO_BOT_COMMENT`.
4. **Baseline code** (run last, since it posts): #1 posts a duplicate
   (pagination), #2 posts one (SIGPIPE), and the labels miss `area:scripts`.
   Record the note-count deltas.
5. **Not live-verifiable:** what `glab api --paginate` prints when a later page
   fails. Both possible behaviours are safe and stub-tested: partial pages give a
   positive or unknown verdict; no output gives unknown.
6. **Teardown:** `podman rm -f -v t2252-gitlab` (0 containers and volumes left);
   shred the tokens; delete the glab config and checkout; keep the image.

### 8. Docs
Gate first: `git diff HEAD -- …/contribution-flow.md` must be empty, since
another session edits this area. Then extend `contribution-flow.md:82`: the
check reads every comment on the issue. When it cannot, it posts nothing and
the run reports a failure, so a re-run decides; an incomplete read never posts
a duplicate. Then run `cd website && python3 check_links.py --build`.

## Verification
- `bash tests/test_contribution_check.sh` and `bash tests/test_contribution_review.sh`:
  0 failures. Pass counts equal the baseline plus the new assertions.
- `tests/test_gitlab_contribution_job.py` passes under the framework Python, as on
  the baseline.
- `shellcheck` on both scripts and both stubs: no new warnings.
- Step 6 sets match D ∪ C exactly; step 7 results as listed; `check_links.py`
  is clean.
- Commit only the named paths:
  `bug: Read every page and drop the SIGPIPE-prone grep in the overlap lookup (t2252)`.
- Step 9 (Post-Implementation): review, plan notes, archival.

## Risk

### Code-health risk: low
- The stubs are shared by three test files, including the CI-job Python test ·
  severity: low · → mitigation: none (Step 0 baseline + Verification; `*/issues` routes byte-identical)
- `_gitlab_rest_all_pages` also serves the production issue listing · severity:
  low · → mitigation: none (`iid` stays first in the key; that caller still discards partial output; Tests 27-30 re-run)
- `main()`'s post path is restructured into one helper used by both branches,
  called in a conditional context where errexit is off. A failed post could
  otherwise be swallowed · severity: low (residual) · → mitigation: none (explicit status checks with distinct return codes; Test 46 drives a failed POST through both branches on GitHub, GitLab REST and glab as a real script process, with positive controls; Tests 38/40/44 cover the three lookup verdicts)

### Goal-achievement risk: low
- Behaviour change: an incomplete lookup now fails the run instead of posting.
  The GitHub workflow and GitLab trigger jobs go red until a re-run · severity:
  low · → mitigation: none (deliberate, per review; warned, documented in contribution-flow.md, scheduled scan unaffected)
- `glab api --paginate` output for notes and labels, and its later-page-failure
  output, were not observed live before · severity: low · → mitigation: none (shape-agnostic parsing; both failure behaviours safe and stub-tested; Step 7 live check)
- Test 39 and the P rows cannot go red before the fix, by design · severity:
  low · → mitigation: none (classified up front in the table; step 6 checks them as green)

## Post-Review Changes

### Change Request 1 (2026-11-09 17:49)
- **Requested by user (three confirmed review findings):**
  1. [high] `_gitlab_issue_notes` judged completeness by jq's exit status. jq
     carries on past a non-array value and exits 0 when a later page parses
     (`[]`, `{"message":…}`, `[]` → rc 0), and exits 0 on empty input, so a
     malformed or empty glab response read as a complete, empty thread → verdict 1
     → a POST.
  2. [medium] The two SIGPIPE fixture self-tests required exactly 141. Where
     SIGPIPE is inherited ignored, echo fails with EPIPE (status 1) instead:
     242 passed / 2 failed.
  3. [low] `contribution-flow.md` said an incomplete read fails the run. A
     page-1 analysis plus a later-page failure deliberately succeeds.
- **Changes made:**
  1. `_gitlab_issue_notes` tags every response value (`{page:[…]}` /
     `{bad:true}`). It is complete only when its fetch succeeded, jq parsed to
     the end, at least one value came back and every value is a page. Notes of
     the pages that parsed are still returned as positive evidence. New stub knob
     `GLAB_STUB_API_RAW=<file>` (glab notes route prints it verbatim, exit 0).
     New check Test 47 (mixed and empty responses → 2; analysis page then error
     object → 0; `main()` on mixed and empty: no POST, exit 1). New review Test
     35 (error object after a page: returns 1, keeps the page's notes).
  2. `_t2252_old_pipeline` now reports `"<pipeline> <echo> <grep>"`. Each
     self-test became two assertions: the stream carries the marker (independent
     substring check), and the old pipeline matched (grep 0) but failed because
     its writer broke (echo 141 SIGPIPE, or 1 EPIPE under an inherited ignore).
     A non-interactive shell cannot reset an inherited ignore (`trap - PIPE`
     probe: still 1), and `env --default-signal` is GNU-only, so the control
     accepts both.
  3. Doc sentence qualified: an analysis among the comments that were read still
     counts and the check skips re-posting. Only when none of them is an
     analysis does it post nothing and fail.
- **Evidence:**
  - Default SIGPIPE: check 253/253, review 106/106.
  - SIGPIPE inherited ignored (Python `SIG_IGN` + `restore_signals=False`):
    253/253 and 106/106 (before: 242/2).
  - Pre-review mutant (the old `_gitlab_issue_notes` swapped into a copy of the
    tree): exactly the 6 new Test 47 rows fail. "Analysis page, then error
    object → found" and review Test 35 are green there.
  - `<start>` baseline: the D set grows by the 7 Test 47 rows. "Analysis page,
    then error object → found" is red there, because the old jq failure
    discarded the marker it had read. It also grows by the 2 review Test 35
    rows. The 4 SIGPIPE self-tests are green on `<start>`.
  - `test_gitlab_contribution_job.py` OK; shellcheck has no new codes;
    `check_links.py` reports `SWEEP: PASSED`.
- **Files affected:** `.aitask-scripts/aitask_contribution_check.sh`,
  `tests/lib/glab_contribution_stub.sh`, `tests/test_contribution_check.sh`,
  `tests/test_contribution_review.sh`,
  `website/content/docs/workflows/contribute-and-manage/contribution-flow.md`.

## Final Implementation Notes

- **Actual work done:**
  - **Lookup.** Both overlap lookups return the three-way verdict through
    `_overlap_lookup_verdict`, which uses a shell substring test and no
    `echo | grep -q`.
  - **GitLab reads.** GitLab notes are read in full on the glab path
    (`glab api --paginate`) and the REST path (`_gitlab_rest_all_pages`, now
    path-agnostic: `?`/`&` separator, `iid // id` repeat key, "GitLab listing"
    wording). New helper `_gitlab_issue_notes` returns every note and marks
    whether the read was complete.
  - **Post.** `main()` posts through `_post_overlap_comment_once`, which checks
    the post status explicitly (rc 0 ok, 1 unknown and nothing posted, 2 post
    failed).
  - **Labels.** `gitlab_list_repo_labels` reads every page on both paths.
  - **Review.** The review fetch uses `_gitlab_issue_notes`, sorts oldest first,
    keeps the comments it did read when a page fails (`_review_comments` warns),
    and merges the comments into the issue JSON through stdin, not `--argjson`.
  - **Docs.** `contribution-flow.md` describes the incomplete-read outcome.
  - **Stubs.**
    - glab stub: notes/labels variants derived by jq from the captures, page
      slicing, and the knobs `GLAB_STUB_NOTES`, `GLAB_STUB_LABELS`,
      `GLAB_STUB_API_FAIL_PAGE`, `GLAB_STUB_API_RAW`, `GLAB_STUB_NOTE_FAIL`,
      `GLAB_STUB_CURL_POST_FAIL` and `GLAB_STUB_CURL_FAIL_PATH`. It also models
      `glab label list` (30 per page).
    - gh stub: an anonymised real `gh issue view --json comments` capture with
      large/many variants, per-issue views, the knobs `GH_STUB_COMMENTS`,
      `GH_STUB_VIEW_FAIL` and `GH_STUB_COMMENT_FAIL`, a `comment_calls` log,
      and an exported `GH_STUB_DIR`.
  - **Tests.** Check Tests 38-47 and review Tests 31-35. The two contract-change
    edits are Test 33 (the lookup without a token returns 2) and Test 35 (`:497`,
    `api --paginate`).
- **Deviations from plan:**
  - `GLAB_STUB_CURL_FAIL_PATH` (glob) was added. The REST `main()` tests list
    issues through the same paged helper, so a bare `FAIL_PAGE=2` would have
    killed that listing before the lookup.
  - Review Test 33 runs the review script as a separate process. Sourced under
    the test file's `set +e`, the old `--argjson` crash would not abort
    `cmd_fetch`.
  - Review Test 32 asserts the exact `parse_overlap_from_comments` output with
    `assert_eq`. A not-contains check would pass vacuously on the old glab path,
    which returned no comments.
  - Change Request 1 (see Post-Review Changes) added per-value notes validation,
    two-representation SIGPIPE controls, the qualified doc sentence, check
    Test 47 and review Test 35.
  - **Classification correction (step 6):** review Test 33 "gitlab glab: fetch
    exits 0" is S, not D. The old glab path never read a note, so `--argjson`
    only saw `[]`. The glab D row there is "keeps all 41 comments".
- **Issues encountered:**
  - The first SIGPIPE probe put the marker and 400 KB on one line, so grep had
    to read the whole line and no early exit happened. Python's `subprocess`
    resets SIGPIPE unless `restore_signals=False`.
  - For live glab, `--api-protocol http` must be passed to `glab auth login`
    itself; a later `config set` does not fix a login that already failed.
  - A baseline duplicate posted live on #1 linked #2, and GitLab added a newer
    "mentioned in" system note there. The old pipeline still returned 141 on #2.
  - A podman volume from 2026-11-08 was left from before this session. It was
    not created here and was left in place.
- **Key decisions:**
  - Unknown means no post plus a non-zero exit. The GitHub workflow and GitLab
    trigger job go red; the scheduled scan carries on (`|| true`).
  - On unknown, labels are still applied, since they are never duplicated. A
    failed post stops before labels, as the old errexit exit did.
  - GitHub keeps `gh issue view --json comments`, because gh 2.102.1 pages
    through comments itself (`preloadIssueComments`).
  - Labels stay all-or-nothing.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_contribution_check.sh:181 — github_list_repo_labels reads only the first 200 repository labels (gh label list --limit 200); an auto-applicable area:/scope: label past them is never applied (no duplicate risk)`

### Closure evidence

**SIGPIPE reproduction (bash, default SIGPIPE: 141 on 5/5 runs; inherited-ignored: 1 with "echo: write error: Broken pipe"):**

```bash
set -o pipefail
x=$(head -c 400000 /dev/zero | tr '\0' x)
body="<!-- overlap-results"$'\n'"$x"
echo "$body" | grep -qF "<!-- overlap-results"
echo "rc=$? pipestatus=${PIPESTATUS[*]}"   # rc=141 pipestatus=141 0
```

**Test runs:**
- **`<start>` = 6958840a742a99bd26dbde1aa4574413b269e833:** check 155/155,
  review 87/87, `test_gitlab_contribution_job.py` 8 OK.
- **After the change:** check 253/253 and review 106/106 under default and
  under inherited-ignored SIGPIPE; the Python test 8 OK; shellcheck has no new
  codes; `check_links.py --build` reports `SWEEP: PASSED`.

**Pre-fix control.** The new tests ran against `git archive <start>
.aitask-scripts`. Failing descriptions:

```text
== tests/test_contribution_check.sh (Results: 209 passed, 44 failed, 253 total) ==
no token: 'gitlab_has_overlap_comment 100' returns 2 (unknown, not absence)
glab-only: notes read via glab api, every page
github lookup finds the analysis in a long thread
github main sees the existing analysis in a long thread
github main posts nothing on a long thread
github lookup with a failed comment read returns 2
github main posts nothing after a failed comment read
github main exits 1 after a failed comment read
github main says why it did not post
gitlab REST lookup finds the analysis in a long thread
gitlab glab lookup finds the analysis in a long thread
gitlab REST lookup finds the analysis on page 2
gitlab REST lookup requested notes page 2
gitlab glab lookup finds the analysis on page 2
gitlab glab lookup paginates the notes
gitlab glab lookup reads one-array-per-page output
REST: analysis on page 2, page 2 fails -> unknown
REST: a repeated notes page -> unknown
REST: the repeated notes page is detected on the second request
REST: notes page 1 fails -> unknown
glab: notes api failure -> unknown
glab: analysis on page 2, page 2 fails -> unknown
rest: main sees the analysis on notes page 2
rest: main posts nothing on a complete 150-note thread
glab: main sees the analysis on notes page 2
glab: main posts nothing on a complete 150-note thread
rest: notes page-2 failure, nothing found: main posts nothing
rest: notes page-2 failure, nothing found: main exits 1
rest: notes page-2 failure, nothing found: main says why
glab: notes page-2 failure, nothing found: main posts nothing
glab: notes page-2 failure, nothing found: main exits 1
glab: notes page-2 failure, nothing found: main says why
REST label listing includes a label past page 1
REST label listing requested page 2
REST: a repeated label page fails the listing
glab label listing includes a label past page 1
glab label listing paginates
glab: page, error object, page (exit 0) -> unknown, not absence
glab: no output at all (exit 0) -> unknown, not absence
glab: an analysis page, then an error object -> found
glab (mixed response): main posts nothing
glab (mixed response): main exits 1
glab (empty response): main posts nothing
glab (empty response): main exits 1
== tests/test_contribution_review.sh (Results: 90 passed, 16 failed, 106 total) ==
REST: review reads every note of a 150-note thread
glab: review reads every note of a 150-note thread
glab: review comments include the analysis
glab: review notes read via api --paginate
glab: review notes not read via glab issue view
rest: exactly the newest analysis's overlaps are used
glab: exactly the newest analysis's overlaps are used
gitlab REST: fetch exits 0 on an 800 KB thread
gitlab REST: fetch keeps all 41 comments
gitlab glab: fetch keeps all 41 comments
github: fetch exits 0 on an 800 KB thread
github: fetch keeps all 41 comments
REST: review reports a failed notes page 2 (returns 1)
REST: fetch warns that the comments are incomplete
glab: an error object in the notes response is reported (returns 1)
glab: the notes of the page before it are kept
```

**Pre-review mutant control.** The pre-review `_gitlab_issue_notes` was swapped
into a copy of the tree. Check: 247 passed, 6 failed. Every failure is a Test 47
row: the two lookup verdicts, and "main posts nothing" / "main exits 1" for the
mixed and empty responses. Review: 106/106.

**Live GitLab CE 19.4.5 check** (`gitlab/gitlab-ce:19.4.5-ce.0` on 127.0.0.1:8929;
project `maint/aitask-ct`). Issue #1 has the analysis posted by the new check,
then 149 replies (151 notes with a system note). The project has 150 `aa-label-*`
fillers plus `area:scripts` and `contribution`. Issue #2 has a 400 KB note, then
the analysis. Every run's duplicates were deleted after the run. Report:

```text
glab auth status (scratch config)                                        ok
== live self-checks ==
#1 REST notes page 1 (per_page=100) has the analysis                     false
#1 REST notes page 2 has the analysis                                    true
raw glab api --paginate notes: arrays / per-array lengths                2 / [100,51]
#2 REST notes: analysis is the first (newest) note                       false
#2 pre-t2252 echo | grep -q pipeline rc                                  141
REST labels page 1 (per_page=100) has area:scripts                       false
glab label list -F json: count / has area:scripts                        [30,false]
== new code (/home/ddt/Work/aitasks) ==
REST check #1: rc / duplicates posted (then removed) / message           0 / 0 / already exists
glab check #1: rc / duplicates posted (then removed) / message           0 / 0 / already exists
REST check #2: rc / duplicates posted (then removed) / message           0 / 0 / already exists
glab check #2: rc / duplicates posted (then removed) / message           0 / 0 / already exists
REST labels: count / has area:scripts                                    152 / yes
glab labels: count / has area:scripts                                    152 / yes
REST review fetch #1: comments / first is the analysis / sorted oldest first [151,true,true]
glab review fetch #1: comments / first is the analysis / sorted oldest first [151,true,true]
REST review find-related #1: NO_BOT_COMMENT?                             0
glab review find-related #1: NO_BOT_COMMENT?                             0
== baseline code (/tmp/claude-1000/-home-ddt-Work-aitasks/c4bd17f7-be75-4752-9828-e668b99c7842/scratchpad/baseline.ocCE) ==
REST check #1: rc / duplicates posted (then removed) / message           0 / 1 / Posted overlap
glab check #1: rc / duplicates posted (then removed) / message           0 / 1 / Posted overlap
REST check #2: rc / duplicates posted (then removed) / message           0 / 1 / Posted overlap
glab check #2: rc / duplicates posted (then removed) / message           0 / 1 / Posted overlap
REST labels: count / has area:scripts                                    100 / no
glab labels: count / has area:scripts                                    30 / no
REST review fetch #1: comments / first is the analysis / sorted oldest first [100,false,false]
glab review fetch #1: comments / first is the analysis / sorted oldest first [0,false,true]
REST review find-related #1: NO_BOT_COMMENT?                             1
glab review find-related #1: NO_BOT_COMMENT?                             1
```

Seed script:

```bash
#!/usr/bin/env bash
# t2252 live seed: user maint, project maint/aitask-ct, issue #1 with the analysis
# posted by the NEW check then 149 replies, labels past page 1, issue #2 with a
# ~400 KB note followed by the analysis. Tokens stay in mode-600 files.
set -euo pipefail
L="$(cd "$(dirname "$0")" && pwd)"
REPO=/home/ddt/Work/aitasks
API=http://localhost:8929/api/v4
umask 077
root=(-H @"$L/secrets/root_hdr")

# --- user + token ---
uid=$(curl -sf "${root[@]}" "$API/users?username=maint" | jq -r '.[0].id // empty')
if [[ -z "$uid" ]]; then
    pw=$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)
    uid=$(curl -sf "${root[@]}" -X POST "$API/users" \
        --data-urlencode "email=maint@example.test" --data-urlencode "username=maint" \
        --data-urlencode "name=maint" --data-urlencode "password=${pw}Aa1!" \
        --data "skip_confirmation=true" | jq -r .id)
fi
if [[ ! -s "$L/secrets/maint_token" ]]; then
    curl -sf "${root[@]}" -X POST "$API/users/$uid/personal_access_tokens" \
        --data "name=t2252" --data "scopes[]=api" --data "expires_at=$(date -u -d '+2 days' +%F)" \
        | jq -r .token > "$L/secrets/maint_token"
fi
printf 'PRIVATE-TOKEN: %s\n' "$(cat "$L/secrets/maint_token")" > "$L/secrets/maint_hdr"
m=(-H @"$L/secrets/maint_hdr")

# --- project ---
pid=$(curl -sf "${m[@]}" "$API/projects/maint%2Faitask-ct" 2>/dev/null | jq -r '.id // empty' || true)
if [[ -z "$pid" ]]; then
    pid=$(curl -sf "${m[@]}" -X POST "$API/projects" --data "name=aitask-ct" --data "visibility=public" | jq -r .id)
fi
echo "PROJECT:$pid"
P="$API/projects/$pid"

meta=$(bash -c '. "$1/tests/lib/glab_contribution_stub.sh"; _glab_stub_metadata .aitask-scripts/aitask_contribute.sh' _ "$REPO")
mk_issue() {  # mk_issue <title> -> iid
    jq -n --arg t "$1" --arg d "$meta" '{title: $t, description: $d}' > "$L/issue.json"
    curl -sf "${m[@]}" -H 'Content-Type: application/json' -X POST "$P/issues" --data @"$L/issue.json" | jq -r .iid
}
note() {  # note <iid> <body-file>
    jq -n --rawfile b "$2" '{body: $b}' > "$L/note.json"
    curl -sf "${m[@]}" -H 'Content-Type: application/json' -X POST "$P/issues/$1/notes" --data @"$L/note.json" >/dev/null
}
check_rest() {  # check_rest <iid> — the NEW check over REST, as the CI job runs it
    CI_API_V4_URL="$API" GITLAB_TOKEN="$(cat "$L/secrets/maint_token")" \
        bash "$REPO/.aitask-scripts/aitask_contribution_check.sh" "$1" --platform gitlab --repo maint/aitask-ct
}

# --- issue #1: analysis first, then 149 replies ---
i1=$(mk_issue "[Contribution] live A")
echo "ISSUE1:$i1"
check_rest "$i1"
printf 'Thanks!' > "$L/thanks.txt"
for _ in $(seq 149); do note "$i1" "$L/thanks.txt"; done

# --- labels: 150 fillers sorting before area:scripts, plus the real ones ---
for n in $(seq -w 1 150); do
    curl -sf "${m[@]}" -X POST "$P/labels" --data-urlencode "name=aa-label-$n" --data-urlencode "color=#428BCA" >/dev/null
done
for l in "area:scripts" "contribution"; do
    curl -sf "${m[@]}" -X POST "$P/labels" --data-urlencode "name=$l" --data-urlencode "color=#5CB85C" >/dev/null
done

# --- issue #2: a ~400 KB note, then the analysis ---
i2=$(mk_issue "[Contribution] live B")
echo "ISSUE2:$i2"
{ printf 'Build log:\n'; head -c 400000 /dev/zero | tr '\0' 'x'; } > "$L/big.txt"
note "$i2" "$L/big.txt"
check_rest "$i2"

for i in "$i1" "$i2"; do
    echo "NOTES:$i:$(curl -sfI "${m[@]}" "$P/issues/$i/notes?per_page=1" | tr -d '\r' | sed -n 's/^x-total: //Ip')"
done
echo "LABELS:$(curl -sfI "${m[@]}" "$P/labels?per_page=1" | tr -d '\r' | sed -n 's/^x-total: //Ip')"
```

Check script:

```bash
#!/usr/bin/env bash
# t2252 live check against the local GitLab CE: self-checks, the new code on the
# REST and glab paths, then the <start> baseline code (last: it posts).
set -uo pipefail
L="$(cd "$(dirname "$0")" && pwd)"
REPO=/home/ddt/Work/aitasks
B="$(cat "$L/../baseline_dir")"
API=http://localhost:8929/api/v4
P="$API/projects/1"
umask 077
m=(-H @"$L/secrets/maint_hdr")
MARK='<!-- overlap-results'
say() { printf '%-72s %s\n' "$1" "$2"; }
count_notes() { curl -sfI "${m[@]}" "$P/issues/$1/notes?per_page=1" | tr -d '\r' | sed -n 's/^x-total: //Ip'; }

# --- glab config for maint + a checkout whose origin is the local project ---
export GLAB_CONFIG_DIR="$L/glab_maint"
mkdir -p "$GLAB_CONFIG_DIR" "$L/checkout"
if [[ ! -s "$GLAB_CONFIG_DIR/config.yml" ]] || ! glab auth status --hostname localhost:8929 >/dev/null 2>&1; then
    glab auth login --hostname localhost:8929 --stdin --insecure-storage \
        --api-protocol http --git-protocol http < "$L/secrets/maint_token" >/dev/null 2>&1
fi
git -C "$L/checkout" init -q 2>/dev/null
git -C "$L/checkout" remote remove origin 2>/dev/null
git -C "$L/checkout" remote add origin http://localhost:8929/maint/aitask-ct.git
say "glab auth status (scratch config)" "$(cd "$L/checkout" && glab auth status >/dev/null 2>&1 && echo ok || echo FAIL)"

rest_env=(env CI_API_V4_URL="$API" GITLAB_TOKEN="$(cat "$L/secrets/maint_token")")
run_rest() { "${rest_env[@]}" bash "$1/.aitask-scripts/aitask_contribution_check.sh" "$2" --platform gitlab --repo maint/aitask-ct 2>&1; }
run_glab() { (cd "$L/checkout" && env -u GITLAB_TOKEN bash "$1/.aitask-scripts/aitask_contribution_check.sh" "$2" --platform gitlab 2>&1); }
labels_rest() { "${rest_env[@]}" bash -c '. "$1/.aitask-scripts/aitask_contribution_check.sh"; ARG_REPO=maint/aitask-ct; gitlab_list_repo_labels' _ "$1"; }
labels_glab() { (cd "$L/checkout" && env -u GITLAB_TOKEN bash -c '. "$1/.aitask-scripts/aitask_contribution_check.sh"; ARG_REPO=""; gitlab_list_repo_labels' _ "$1"); }
review_rest() { "${rest_env[@]}" bash "$1/.aitask-scripts/aitask_contribution_review.sh" "$2" 1 --platform gitlab --repo maint/aitask-ct 2>/dev/null; }
review_glab() { (cd "$L/checkout" && env -u GITLAB_TOKEN bash "$1/.aitask-scripts/aitask_contribution_review.sh" "$2" 1 --platform gitlab 2>/dev/null); }
comments_of() { sed -n '/^ISSUE_JSON:/,/^HAS_METADATA:/p' | sed '1s/^ISSUE_JSON://; $d' | jq -c "$@"; }
max_note_id() { curl -sf "${m[@]}" "$P/issues/$1/notes?per_page=1&order_by=created_at&sort=desc" | jq -r '.[0].id'; }
# undo_posts <iid> <max_id_before> — deletes the user notes a run posted, so
# every run starts from the seeded state; prints how many it posted.
undo_posts() {
    local ids
    ids=$(curl -sf "${m[@]}" "$P/issues/$1/notes?per_page=100&order_by=created_at&sort=desc" \
        | jq -r --argjson b "$2" '.[] | select(.id > $b and (.system | not)) | .id')
    for id in $ids; do curl -sf "${m[@]}" -X DELETE "$P/issues/$1/notes/$id" >/dev/null; done
    grep -c . <<< "$ids"
}

echo "== live self-checks =="
say "#1 REST notes page 1 (per_page=100) has the analysis" \
    "$(curl -sf "${m[@]}" "$P/issues/1/notes?per_page=100&page=1" | jq --arg m "$MARK" '[.[].body | contains($m)] | any')"
say "#1 REST notes page 2 has the analysis" \
    "$(curl -sf "${m[@]}" "$P/issues/1/notes?per_page=100&page=2" | jq --arg m "$MARK" '[.[].body | contains($m)] | any')"
(cd "$L/checkout" && glab api --paginate "projects/:id/issues/1/notes?per_page=100") > "$L/glab_paginate_notes_raw.json" 2>"$L/glab_paginate_notes.err"
say "raw glab api --paginate notes: arrays / per-array lengths" \
    "$(jq -s 'length' "$L/glab_paginate_notes_raw.json") / $(jq -sc 'map(length)' "$L/glab_paginate_notes_raw.json")"
say "#2 REST notes: analysis is the first (newest) note" \
    "$(curl -sf "${m[@]}" "$P/issues/2/notes?per_page=100" | jq --arg m "$MARK" '.[0].body | contains($m)')"
b2=$(curl -sf "${m[@]}" "$P/issues/2/notes?per_page=100" | jq -r '.[].body')
(set -o pipefail; echo "$b2" | grep -qF "$MARK"); say "#2 pre-t2252 echo | grep -q pipeline rc" "$?"
say "REST labels page 1 (per_page=100) has area:scripts" \
    "$(curl -sf "${m[@]}" "$P/labels?per_page=100&page=1" | jq '[.[].name] | index("area:scripts") != null')"
say "glab label list -F json: count / has area:scripts" \
    "$(cd "$L/checkout" && glab label list -F json 2>/dev/null | jq -c '[length, ([.[].name] | index("area:scripts") != null)]')"

for side in new baseline; do
    root="$REPO"; [[ "$side" == baseline ]] && root="$B"
    echo "== $side code ($root) =="
    for i in 1 2; do
        for path in REST glab; do
            maxid=$(max_note_id "$i")
            if [[ "$path" == REST ]]; then out=$(run_rest "$root" "$i"); rc=$?; else out=$(run_glab "$root" "$i"); rc=$?; fi
            say "$path check #$i: rc / duplicates posted (then removed) / message" \
                "$rc / $(undo_posts "$i" "$maxid") / $(grep -oE 'already exists|Posted overlap|Not posting' <<< "$out" | head -1)"
        done
    done
    say "REST labels: count / has area:scripts" "$(labels_rest "$root" | grep -c .) / $(labels_rest "$root" | grep -qx 'area:scripts' && echo yes || echo no)"
    say "glab labels: count / has area:scripts" "$(labels_glab "$root" | grep -c .) / $(labels_glab "$root" | grep -qx 'area:scripts' && echo yes || echo no)"
    say "REST review fetch #1: comments / first is the analysis / sorted oldest first" \
        "$(review_rest "$root" fetch | comments_of --arg m "$MARK" '[(.comments | length), (.comments[0].body | contains($m)), (.comments | map(.createdAt) | . == sort)]' 2>/dev/null || echo ERR)"
    say "glab review fetch #1: comments / first is the analysis / sorted oldest first" \
        "$(review_glab "$root" fetch | comments_of --arg m "$MARK" '[(.comments | length), ((.comments[0].body // "") | contains($m)), (.comments | map(.createdAt) | . == sort)]' 2>/dev/null || echo ERR)"
    say "REST review find-related #1: NO_BOT_COMMENT?" "$(review_rest "$root" find-related | grep -c '^NO_BOT_COMMENT$')"
    say "glab review find-related #1: NO_BOT_COMMENT?" "$(review_glab "$root" find-related | grep -c '^NO_BOT_COMMENT$')"
done
```
