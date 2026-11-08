---
Task: t2235_contribution_issues_opened_by_external_authors_are_invisible.md
Base branch: main
Output branch: main
---

# t2235 — Make external-author contribution issues visible (GitHub)

## Context

`/aitask-contribute` creates GitHub issues with `gh issue create --label contribution`.
GitHub **silently drops** labels supplied by authors without push access, `gh` exits 0,
and `github_create_issue` never reads the label back — so an external contributor gets
an unlabeled issue and no warning. Every consumer then filters on that label:

- `github_list_contribution_issues` (`.aitask-scripts/aitask_contribution_check.sh:117-121`)
  uses `gh issue list --label contribution`; it is shared by the overlap check
  (`main`, `:754`) and by `aitask_contribution_review.sh cmd_list_issues` (`:525`).
- `.github/workflows/contribution-check.yml` and its template
  `seed/ci/github/contribution-check.yml` trigger only on `issues: [labeled]` with
  `github.event.label.name == 'contribution'`.

A second, compounding delivery defect, verified during planning: `install.sh:1929` runs
`rm -rf "$INSTALL_DIR/seed"` after every install or upgrade (since t92/t938, before the CI
templates existed). `setup_contribution_check` (`aitask_setup.sh:4845`) returns
immediately when `seed/ci` is missing. So in a normally installed project `ait setup`
**never** creates the `contribution` label or installs any CI workflow; only checkouts
that carry `seed/` (like this repo) get them.

Goal: an open issue carrying the `<!-- aitask-contribute-metadata` marker is visible
regardless of who opened it (listing, overlap check, workflow trigger), the contributor
is told when the label was dropped, and the workflow template actually reaches installed
projects through `ait setup`. Scope is GitHub plus template delivery for all platforms.
The GitLab label-visibility question is a spawned follow-up (see Risk).

Work runs on the current branch (`main`, profile `fast`). None of the target files —
including `aitask_setup.sh`, which another session committed in `56a501846` — has
uncommitted changes (re-checked with `git status --short` during planning). **Re-check
just before editing**: if any target is dirty again, stop and ask before touching it.

## Implementation steps

### 1. Listing: paginate open issues, filter before limiting
`.aitask-scripts/aitask_contribution_check.sh` — rewrite `github_list_contribution_issues`
to scan **all** open issues through the REST API and apply `ARG_LIMIT` **after**
filtering. This replaces both the label-filtered query and the "N most recent" cap:

```bash
github_list_contribution_issues() {
    # Labels from authors without push access are silently dropped by GitHub,
    # so a contribution issue is one that carries the label OR the metadata
    # marker. Scan every open issue (paginated) and limit only AFTER filtering,
    # so newer ordinary issues cannot crowd an older contribution out.
    local path="repos/{owner}/{repo}/issues?state=open&per_page=100"
    [[ -n "$ARG_REPO" ]] && path="repos/$ARG_REPO/issues?state=open&per_page=100"
    local pages
    pages=$(gh api --paginate "$path") || return 1
    printf '%s\n' "$pages" | jq -s --argjson limit "$ARG_LIMIT" '
        [ (add // [])[]
          | select(.pull_request == null)
          | select(any(.labels[]?; .name == "contribution")
                   or ((.body // "") | contains("<!-- aitask-contribute-metadata")))
          | {number, title, body: (.body // ""),
             labels: [.labels[]? | {name}], url: .html_url} ]
        | unique_by(.number) | sort_by(-.number) | .[:$limit]'
}
```

- `gh api --paginate` writes one JSON array per page, and `jq -s 'add'` concatenates
  them. Pull requests (which the issues endpoint also returns) are dropped. The output
  shape `{number,title,body,labels:[{name}],url}` matches the old `gh issue list
  --json` shape, so `main` and `cmd_list_issues` are unchanged.
- The `{owner}/{repo}` placeholder resolves from the current repo, as the old no-`-R`
  call did.
- The kept set is "labeled `contribution` OR has the marker". That keeps labeled issues
  without metadata (`list-issues` shows them as `HAS_METADATA:false`) and excludes plain
  issues. The marker substring is the one `parse_contribute_metadata`
  (`lib/task_utils.sh:3997`) matches.
- Page JSON goes through stdin, never `--argjson`, because Linux caps a single argument
  at 128 KB.
- `--limit` help text (`:40`) becomes "Max contribution issues to return (default: 50);
  on GitHub all open issues are scanned and the limit applies after filtering".
- Cost: one request per 100 open issues, per check run. That is acceptable for the
  per-issue workflow and the interactive listing.

### 2. Workflow: trigger on `issues.opened`, gate concurrency on the job
Edit the template (it moves in step 3, to
`.aitask-scripts/ci_templates/github/contribution-check.yml`): update its header comment
and bump `actions/checkout@v5` → `@v6` (this repo's own workflow already uses v6). Then make
`.github/workflows/contribution-check.yml` **byte-identical** to it.

```yaml
on:
  issues:
    types: [opened, labeled]

permissions: { issues: write, contents: read }   # unchanged

jobs:
  check-contribution:
    if: >-
      (github.event.action == 'labeled' && github.event.label.name == 'contribution') ||
      (github.event.action == 'opened' &&
       contains(github.event.issue.body, 'aitask-contribute-metadata') &&
       !contains(github.event.issue.labels.*.name, 'contribution'))
    concurrency:
      group: contribution-check-${{ github.event.issue.number }}
      cancel-in-progress: false
    runs-on: ubuntu-latest
    steps:
      - checkout / install jq (unchanged)
      - name: Label unlabeled contribution issue
        if: github.event.action == 'opened'
        run: |
          gh issue edit "${{ github.event.issue.number }}" -R "${{ github.repository }}" \
            --add-label contribution \
            || echo "::warning::could not apply the 'contribution' label"
        env: { GH_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
      - Check for overlapping contributions (unchanged)
```

- **No workflow-level `concurrency`.** The group sits on the gated job, so an ineligible
  event (any other label, an opened issue without metadata) is skipped by `if:` and
  never enters the group or takes a pending slot.
- Inside the group, the only events are eligible checks of the same issue. If a newer
  eligible run replaces a pending one, that is harmless: each run reads the issue's
  current state, and the overlap-comment idempotency stops a second post.
- An issue opened **with** the label emits `opened` and `labeled`. The `opened` branch
  skips it, so it runs once.
- The auto-label uses `GITHUB_TOKEN`, which fires no new workflow events, so the `opened`
  run does the check itself.
- `github.event.issue.body` appears **only** inside `if:` and is never interpolated into
  `run:`, so there is no script injection.

### 3. Template delivery: persistent location that survives `install.sh`
- `git mv seed/ci .aitask-scripts/ci_templates` (moving all three templates: github,
  gitlab, bitbucket). This follows the `gates_reference.yaml` precedent: a canonical file
  under `.aitask-scripts/` that installed projects keep after `seed/` is deleted. It
  ships in the tarball, since `release.yml:182` packages `.aitask-scripts/` whole.
- `aitask_setup.sh setup_contribution_check`: `seed_ci_dir` →
  `ci_template_dir="$project_dir/.aitask-scripts/ci_templates"`. When it is missing,
  `warn` "CI templates not found at … — run `ait setup` to repair the install"
  (repair → `ait setup`, per the CLI verb rule), not a silent return. Rename the
  parameter in `_install_contribution_ci_workflow` to match.
- Effect, stated in docs: installed projects now get the label and the platform workflow
  from `ait setup` on all three platforms (GitLab and Bitbucket included, which were
  previously skipped silently).
- Grep for other `seed/ci` references and update them (planning found only the docs and
  `aitask_setup.sh:4847`).

### 4. Contributor side: verify the label after creation
`.aitask-scripts/aitask_contribute.sh` `github_create_issue` (`:191-212`):

- After the labeled create succeeds, extract the URL
  (`grep -Eo 'https://[^[:space:]]+/issues/[0-9]+' | tail -1`) and read back
  `gh issue view "$url" -R "$repo" --json labels --jq '.labels[].name'`.
  - Has `contribution`: silent.
  - Label missing: `warn "GitHub did not apply the 'contribution' label to $url — labels from authors without push access to $repo are silently dropped. The issue was created; maintainers' tooling finds it by its aitask-contribute-metadata block, and the contribution-check workflow labels it when installed."`
  - Read-back fails or no URL: `warn "Could not verify that the 'contribution' label was applied to <url|the new issue>."`
  - In every case still `echo "$result"` and `return 0`. The issue exists and callers need
    its URL, so the case is reported, not failed.
- Fallback path (labeled create exited non-zero): replace the "label may not exist" text
  with one naming both causes (the label is missing on the repo, or you lack permission to
  set labels). When the unlabeled retry succeeds, add the same "created unlabeled — found
  by its metadata" sentence, so the fallback no longer reads as a clean success.
- `--no-label` path: unchanged, no warning.

### 5. Tests
- **`tests/test_contribution_check.sh`**: add a `gh` function stub that models GitHub
  pagination: `gh api` returns only page 1 unless `--paginate` is passed, then
  writes page 1 and page 2 as consecutive arrays.
  - Page 1: 100 newer ordinary issues plus one PR entry (`pull_request` set, with the marker).
  - Page 2: older #15 (labeled + metadata, the control), #14 (plain), #12 (labeled, no
    metadata), and #100 / #101 (unlabeled + metadata sharing file, dir, area and change
    type, so they score 8). `issue view 100` returns #100.
  - With `ARG_REPO=o/r` and `ARG_LIMIT=50`, `github_list_contribution_issues` returns
    exactly `101,100,15,12`: no ordinary issues, no PR, no #14, no duplicates. This is the
    crowding case the old `--limit` scan failed.
  - `ARG_LIMIT=2` → `101,100`, showing the limit applies after filtering.
  - `main 100 --platform github --repo o/r --dry-run --silent` → output contains `#101`
    with score `8` / `high`, and `#15`.
  - Assert that `gh api` failing makes the function return non-zero.
- **`tests/test_contribution_review.sh`**: drive `cmd_list_issues` through the real
  `source_list_contribution_issues` (`CHECK_PLATFORM=github`) with the same stub.
  Expect `@@@ISSUE:100@@@` with `HAS_METADATA:true`, `@@@ISSUE:12@@@` with
  `HAS_METADATA:false`, and never `@@@ISSUE:14@@@`.
- **`tests/test_contribute.sh`**: source `aitask_contribute.sh` in a subshell with a `gh`
  stub, capturing stdout and stderr separately:
  - label dropped → URL on stdout, `silently dropped` on stderr;
  - control (label kept) → URL, no warning;
  - fallback (labeled create exits 1) → URL plus the permission/missing-label warning;
  - `no_label=true` → no `issue view` call, no warning.
- **New `tests/test_contribution_workflow_contract.py`** (PyYAML; YAML 1.1 parses the
  `on:` key as `True`, so read `doc.get("on", doc.get(True))`). For **both** workflow
  files:
  - byte equality;
  - `issues.types == ["opened", "labeled"]`;
  - no top-level `concurrency`; `jobs.check-contribution.concurrency` has a group
    containing `github.event.issue.number` and `cancel-in-progress: false`;
  - `${{ github.event.issue.body` never appears.
  - Focused assertions on the shipped job `if:` text (whitespace-normalised), each
    eligibility clause present: `github.event.action == 'labeled' &&
    github.event.label.name == 'contribution'`; `github.event.action == 'opened'`;
    `contains(github.event.issue.body, 'aitask-contribute-metadata')`;
    `!contains(github.event.issue.labels.*.name, 'contribution')`.
  - The label step's `if:` is `github.event.action == 'opened'`.
  - No bespoke expression evaluator or scheduler simulation. Real eligibility and
    queueing behaviour belong to the live manual verification (Step 8c).
- **New `tests/test_setup_contribution_workflow.sh`**: covers the post-phase P1 helper
  and the **real entry point in an installed layout**. Build a scratch project with
  `copy_framework_tree "$PROJECT_DIR/.aitask-scripts" <proj>/.aitask-scripts` and **no
  `seed/`**, `git init`, `origin=https://github.com/o/r.git`, a `gh` stub on `PATH` (for
  `auth status` / `label list`), and a scratch `HOME` with `AITASKS_HOME` unset. Then
  run `bash -c 'source <proj>/.aitask-scripts/aitask_setup.sh --source-only; setup_contribution_check'`
  from `<proj>` with stdin not a tty:
  - (a) no file → `.github/workflows/contribution-check.yml` installed, equal to the
    template;
  - (b) each previously shipped version, from `git show <c>:<path>` over both the old
    `seed/ci/…` and new paths → refreshed;
  - (c) a customized file → byte-unchanged, warning on stderr;
  - (d) a current file → unchanged, "up to date";
  - (e) hash-list completeness: every historical version whose content differs from the
    working-tree template has its sha256 in the list (in a shallow clone, only reachable
    commits are checked).
  - A further case runs with `ci_templates/` removed → the repair warning, nothing installed.
- **Pre-fix controls**: run the new cases against HEAD's scripts, copied into a scratch
  dir with `git show HEAD:<path>` (no stash, no restore).
  - The listing crowding case, the review case and the label-drop case must go red.
  - The installed-layout entry-point case (a) must go red, since HEAD needs `seed/ci`.
  - The contract test must go red against HEAD's workflow YAML.

### 6. Docs
`website/content/docs/workflows/contribute-and-manage/contribution-flow.md`:
- GitHub Actions trigger (`:150`) → "`issues.opened` (body carries
  `aitask-contribute-metadata`, not yet labeled — the run also applies the `contribution`
  label) or `issues.labeled` with the `contribution` label".
- Add a note: GitHub drops labels from authors without push access, so contribution issues
  are identified by their metadata block (all open issues are scanned), and the label is
  a convenience the workflow adds.
- Manual Setup (`:171-176`): template paths → `.aitask-scripts/ci_templates/…`.
- Automatic Setup: `ait setup` installs the workflow. It updates an installed GitHub
  workflow that is an unmodified earlier template, and leaves a locally modified one
  alone with a warning (merge it by hand).
- Matrix rows (`:185-186`): GitHub filtering → "Label or metadata (scans all open
  issues)"; triggers → `issues.opened` / `issues.labeled`.
- Current-state wording only. Run `python3 check_links.py --build` (in `website/`).

### 7. Lint and run
Run `shellcheck` on `aitask_contribute.sh`, `aitask_contribution_check.sh`,
`aitask_contribution_review.sh` and `aitask_setup.sh`. Then run the four bash test files,
plus `bash tests/run_all_python_tests.sh --test-dir <dir holding the new .py>` (or a
direct run of that module).

### Post-phase (risk mitigations)

1. [refresh_installed_contribution_workflow] In `aitask_setup.sh`
   `_install_contribution_ci_workflow`, make `ait setup` refresh an installed GitHub
   workflow that is an unmodified earlier template.
   - Add `_CONTRIBUTION_WORKFLOW_SHIPPED_SHA256=( … )` next to the function, holding the
     sha256 of each **previously shipped** template version:
     `39c812ef2` `77832b69…89d3`, `e98f58128` `efc62383…a7a4`,
     `197f7b8fd` `d45bc661…0e19`, `5b853d0ee` `dd024196…98ab`. The full 64-hex values
     go in the code. A comment says a future template edit must append the outgoing
     version's hash, and that test (e) enforces it.
   - Add `_contribution_workflow_state <dest> <src>`, which prints `current` / `stale` /
     `customized`:
     - `cmp -s` → `current`;
     - else lazily `source "$SCRIPT_DIR/lib/artifact_utils.sh"` and
       `hex=$(artifact_sha256 "$dest" 2>/dev/null) || hex=""` (strip `sha256:`);
     - a listed hex → `stale`; anything else, **including an empty hex** →
       `customized`. A hashing failure never overwrites.
   - Replace the GitHub idempotency block:
     - `current` → `success "…already installed (up to date)"`, return.
     - `customized` → `warn` that the workflow was left unchanged because it differs from
       every shipped template, and that the current template also runs on
       `issues.opened` (merge from `.aitask-scripts/ci_templates/github/contribution-check.yml`);
       return.
     - `stale` → `refresh=1`, then the existing `[Y/n]` prompt (worded "Update…") and the
       `cp`, ending with "Updated … — commit .github/workflows/contribution-check.yml".
   - GitLab/Bitbucket append paths are unchanged.
   - Covered by `tests/test_setup_contribution_workflow.sh` (b)–(e) above.

## Step 9 (Post-Implementation)
Standard cleanup, commit (`feature: ... (t2235)`), and archival per task-workflow Step 9.
The linked issue (#16) is updated by the issue-update procedure. The spawned "after"
mitigation is created at Step 8d.

## Verification
- `bash tests/test_contribution_check.sh`, `bash tests/test_contribution_review.sh`,
  `bash tests/test_contribute.sh`, `bash tests/test_setup_contribution_workflow.sh` —
  all PASS.
- The new Python contract test passes (structure and clause assertions on both YAML files).
- The pre-fix controls go red against HEAD (see step 5).
- `shellcheck` on the four scripts.
- `cd website && python3 check_links.py --build`.
- Live GitHub behaviour (a real non-collaborator issue, real concurrency queueing) can't
  be tested here. It is a manual-verification candidate offered at Step 8c.

## Risk

### Code-health risk: low
- The shared GitHub listing becomes a paginated REST scan normalised in jq, and both the overlap check and `list-issues` depend on it · severity: low (stub tests cover both consumers, crowding, PR exclusion, the limit-after-filter rule and API failure) · → mitigation: none
- The workflow template ships downstream, and a wrong `if:` or concurrency placement could double-run or drop checks · severity: low (job-level concurrency, so ineligible events never enter the group; a contract test asserts the clause set and the concurrency placement; live behaviour is checked in manual verification) · → mitigation: none
- Moving `seed/ci` → `.aitask-scripts/ci_templates` changes where setup reads templates and starts installing GitLab/Bitbucket jobs that installed projects previously skipped silently · severity: low (same templates, same install code, an entry-point test in the installed layout; GitLab/Bitbucket installs already ask `[Y/n]` interactively) · → mitigation: none
- The post-phase writes to a user's `.github/workflows/` during `ait setup`, and a misclassification would overwrite a customized workflow · severity: low (only a byte-identical or listed-hash match is refreshed, any hashing failure counts as customized, the completeness test guards future edits, setup never commits the file) · → mitigation: none

### Goal-achievement risk: medium
- `ait setup` never overwrites an installed `.github/workflows/contribution-check.yml`, so repos that already have it keep the `labeled`-only trigger · severity: low (residual — addressed by inline post-phase refresh_installed_contribution_workflow; locally modified installs still need a manual merge, and setup warns about them) · → mitigation: inline post-phase refresh_installed_contribution_workflow
- GitLab may drop labels from non-members in the same silent way, and its listing still filters on the label · severity: medium · → mitigation: gitlab_contribution_label_visibility
- Live workflow semantics (event payload labels, `GITHUB_TOKEN` events not re-triggering runs, the real concurrency queue) are checked only structurally here, not by GitHub · severity: low · → mitigation: none (manual-verification candidate at Step 8c)

### Planned mitigations
- timing: post-phase | name: refresh_installed_contribution_workflow | type: feature | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: existing installs keep the labeled-only trigger | desc: ait setup refreshes an installed contribution-check.yml that matches a previously shipped template
- timing: after | name: gitlab_contribution_label_visibility | type: bug | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: GitLab may silently drop non-member labels too | desc: Verify GitLab label-drop behaviour for non-members and, if confirmed, make the GitLab listing and CI job identify contribution issues by metadata
