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
