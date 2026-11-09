---
Task: t2249_gitlab_stale_ci_job_hint.md
Base branch: main
Output branch: main
---

# t2249 — Warn when an existing `.gitlab-ci.yml` carries the pre-t2241 contribution-check job

## Context

`ait setup` writes the GitLab contribution-check job only when `.gitlab-ci.yml`
is absent and never edits an existing file. Before t2241, the shipped job's
scheduled scan (a) queried `labels=contribution`, missing contributions from
non-members whose labels GitLab silently drops, and (b) computed its cutoff with
`date -u -d '6 hours ago'` / `date -u -v-6H`, which BusyBox `date` on
`alpine:latest` rejects. A project that copied that job keeps a broken scan, and
today setup reports it green: `success "Contribution check job already present in
.gitlab-ci.yml"` (`.aitask-scripts/aitask_setup.sh`, `_install_contribution_ci_workflow`,
non-github branch, the `grep -q "contribution-check"` hit).

Both earlier shipped GitLab templates (`39c812ef2:seed/ci/gitlab/contribution-check-job.yml`
and `94817522f:.aitask-scripts/ci_templates/gitlab/contribution-check-job.yml`)
carry both markers verbatim; they differ only in a 2-line header comment. The
current template carries neither.

Goal: when an existing `.gitlab-ci.yml` has a `contribution-check:` job whose
body still carries either marker, warn instead of reporting success — naming the
effects, the template path and the docs' Manual Setup section — and still never
modify the file.

## Implementation steps

### 1. `.aitask-scripts/aitask_setup.sh` — stale-job detector

Add a helper next to `_contribution_workflow_state`:

```bash
# Prints the effects of a pre-t2241 GitLab contribution-check job found in
# <ci_file>, one per line (nothing when the job is current or absent). Only the
# top-level contribution-check job body is read — from that key up to the next
# top-level key — so the same strings in another job never match. The key is
# recognised in every ordinary spelling YAML reads as the same key: bare,
# 'single-' or "double-quoted", and with spaces before the colon.
_gitlab_contribution_job_stale_effects() {
    local ci_file="$1" line body="" in_job=0
    local re_key="^(contribution-check[[:space:]]*:([[:space:]]|\$)|'contribution-check'[[:space:]]*:|\"contribution-check\"[[:space:]]*:)"
    local re_top='^[^[:space:]#]'
    [[ -r "$ci_file" ]] || return 0
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ $re_key ]]; then in_job=1
        elif [[ "$in_job" == 1 && "$line" =~ $re_top ]]; then in_job=0
        fi
        [[ "$in_job" == 1 ]] && body+="$line"$'\n'
    done < "$ci_file"
    [[ -n "$body" ]] || return 0
    if grep -qF 'labels=contribution&updated_after' <<<"$body"; then
        echo "its scheduled scan filters on the 'contribution' label, so it misses contributions from non-members (GitLab silently drops their labels)"
    fi
    if grep -qF "date -u -d '6 hours ago'" <<<"$body"; then
        echo "it computes the 6-hour cutoff with GNU/BSD date, which BusyBox date on alpine:latest rejects"
    fi
}
```

The helper only reads the file. Join the effects for the message with `; `.

**Key spellings, measured** (PyYAML `safe_load` vs. the matcher above,
probe run while planning):

| line | YAML key | `/^contribution-check:/` (first draft) | `re_key` |
|---|---|---|---|
| `contribution-check:` | contribution-check | hit | hit |
| `'contribution-check':` | contribution-check | **miss** | hit |
| `"contribution-check":` | contribution-check | **miss** | hit |
| `contribution-check :` | contribution-check | **miss** | hit |
| `contribution-check: # c` | contribution-check | hit | hit |
| `contribution-checks:` | contribution-checks | no | no |
| `contribution-check-old:` | contribution-check-old | no | no |

Renamed jobs, non-top-level placement and `extends:` from a hidden template
stay out of scope (see Risk).

In `_install_contribution_ci_workflow`, inside the existing
`if grep -q "contribution-check" "$dest_file"` branch, for `platform == gitlab`
only: compute the effects; when non-empty, emit

```
warn "The contribution-check job in .gitlab-ci.yml predates the current template: <effects joined by '; '>. Setup does not edit an existing CI configuration — re-copy the job from .aitask-scripts/ci_templates/gitlab/contribution-check-job.yml (see Manual Setup in website/content/docs/workflows/contribute-and-manage/contribution-flow.md)."
```

and `return` **instead of** the green "already present" success line (a
green success over a broken scan is the very defect). Otherwise keep the success
line unchanged. No write path is touched; Bitbucket behaviour unchanged.

Effects are reported per marker present, so the shipped old job names both; a
hand-edited job with only one marker names only that one.

### 2. Test fixtures — byte-exact earlier GitLab jobs

Add `tests/fixtures/contribution_workflow_history/gitlab/1_39c812ef2.yml` and
`2_94817522f.yml` via `git show <c>:<path> > <fixture>` (byte-exact, so the test
never depends on clone depth). The GitHub loop globs `"$FIXTURE_DIR"/*.yml` and
does not descend into `gitlab/`. Add a short paragraph to the fixtures
`README.md` describing the `gitlab/` subdir (outgoing GitLab jobs whose scan
setup must flag; markers, not hashes, so no hash list to update).

### 3. `tests/test_setup_contribution_workflow.sh` — new case (i)

After case (h), with origin set to `https://gitlab.com/o/r.git`; for each case
copy the input to `.gitlab-ci.yml`, keep a `cp` "before", `run_setup`, then
`cmp -s` for byte-identity (counted like the existing (h) checks):

- **(i1) every earlier shipped job warns** — loop over `gitlab/*.yml` fixtures
  (assert ≥1 fixture found, so an empty glob cannot pass): output contains
  `predates the current template`, both effect phrases (`'contribution' label`,
  `BusyBox date`), the template path and `Manual Setup`; does not contain
  `already present`; file byte-identical.
- **(i2) the old job merged into a larger file** — `stages: [build, test]`, a
  `build:` job, then the oldest fixture's job, then another top-level job after
  it: warns; byte-identical. (Proves the block scoping reads past column-0
  comments/other keys correctly.)
- **(i2b) quoted / spaced key spellings warn** — the oldest fixture with its
  `contribution-check:` line rewritten (via `sed` into a scratch copy) to
  `'contribution-check':`, `"contribution-check":` and `contribution-check :`:
  each warns with both effects, does not contain `already present`, and the file
  stays byte-identical.
- **(i2c) each marker on its own warns** — two hand-built jobs derived from the
  oldest fixture: *label-only* (keeps `labels=contribution&updated_after`, cutoff
  line replaced with the current `jq` cutoff) and *date-only* (keeps
  `date -u -d '6 hours ago'`, URL with `labels=contribution&` removed). Each
  asserts `predates the current template` plus **its own** effect phrase, and
  `assert_not_contains` the other effect's phrase, and byte-identity — so
  detection that required both markers, or dropped either one, fails here.
  Fixture sanity: assert each derived job really lacks the other marker
  (`grep -cF` = 0) so a `sed` that matched nothing cannot pass as a red test.
- **(i3) the current template job does not warn** — current
  `ci_templates/gitlab/contribution-check-job.yml` as `.gitlab-ci.yml`: contains
  `already present`, not `predates`; byte-identical.
- **(i4) markers outside the job do not warn** — a file with the current job plus
  an unrelated top-level job whose script contains `date -u -d '6 hours ago'`:
  no `predates`; byte-identical.
- **(h) unrelated `.gitlab-ci.yml`** — add `assert_not_contains ... "predates the
  current template"` to the existing (h) unrelated-file run (already
  byte-identity-checked).

Update the header comment's case list with (i). The file runs no subshell test
bodies, so no `assert_counters_init` change is needed.

### 4. Docs — `website/content/docs/workflows/contribute-and-manage/contribution-flow.md`

In "Automatic Setup", GitLab/Bitbucket paragraph, add one current-state
sentence: when `.gitlab-ci.yml` already has a `contribution-check:` job copied
from an earlier template (its scheduled scan filters on the `contribution`
label, or computes its cutoff with `date`), setup warns that it predates the
current template and leaves it unchanged — re-copy the job (see
[Manual Setup](#manual-setup)).

## Verification

- `bash tests/test_setup_contribution_workflow.sh` — all PASS.
- Pre-fix control: run the new (i1) assertions against `HEAD`'s setup (stash-free:
  temporarily point the scratch copy at `git show HEAD:.aitask-scripts/aitask_setup.sh`)
  and confirm (i1)/(i2)/(i2b)/(i2c) fail — i.e. the test detects the missing
  warning.
- Mutant controls for the new cases (scratch copy only, never the tree):
  (1) revert `re_key` to `^contribution-check:` → (i2b) fails, others pass;
  (2) require both markers (`&&`) → (i2c) fails; (3) drop the date check →
  (i2c) date-only fails.
- `shellcheck .aitask-scripts/aitask_setup.sh` — no new findings.
- `cd website && python3 check_links.py --build`.

## Step 9

Post-implementation: commit code (`enhancement: ... (t2249)`), plan via
`./ait git`, then archival per task-workflow Step 9.

## Risk

### Code-health risk: low
- None identified. (Additive warn path inside an existing read-only branch; no write path, no shared helper changed; Bitbucket/GitHub branches untouched.)

### Goal-achievement risk: low
- A job copied under another name, re-indented under a non-top-level key, or pulled in via `extends:` from a hidden `.contribution-check` template is not inspected, so it would not warn · severity: low · → mitigation: none (accepted — the task scopes detection to the `contribution-check:` job, and widening it to the whole file would flag markers in unrelated jobs). Quoted/spaced spellings of the same key are **in** scope and covered by `re_key` + (i2b).

## Final Implementation Notes

- **Actual work done:** all four plan steps landed as designed. `_gitlab_contribution_job_stale_effects` in `.aitask-scripts/aitask_setup.sh` reads only the top-level `contribution-check` job (bare, quoted and spaced key spellings) and prints one effect per marker found. In `_install_contribution_ci_workflow` the GitLab "already present" branch now warns when it gets any effects and returns without touching the file. Two byte-exact fixtures went into `tests/fixtures/contribution_workflow_history/gitlab/`, plus a README paragraph, test case (i) and one docs paragraph.
- **Deviations from plan:** (1) the helper strips a trailing CR from each line, and (i1) adds a CRLF copy of the oldest job, the same Windows `core.autocrlf` case the GitHub path covers. (2) Effect wording is "only lists issues labeled 'contribution' … (GitLab silently drops the labels they set)" and "GNU/BSD date options that BusyBox date on alpine:latest rejects". (3) (i4) puts marker-carrying jobs both before and after the current job, which checks the scoping in both directions. (4) The `fixture_has` guards check that every derived input really contains or lacks each marker.
- **Issues encountered:** t2246's live session had an uncommitted 42-line hunk in `aitask_setup.sh`. Following the shared-file gate, all work was built and verified in an isolated `git archive` copy of HEAD. The four clean files were copied in after a per-file clean-vs-HEAD check, and the `aitask_setup.sh` patch was applied only after t2246 committed (`eaa6af1ab`; its hunk confirmed in HEAD, file clean and unstaged).
- **Key decisions:** the warning replaces the green "already present" success (it does not add to it), because a success line over a broken scan is the defect itself. Detection keys on the outdated scan's marker strings rather than hashes, so it covers hand-merged copies of the job and needs no hash list. Each effect is reported per marker present. Comments are stripped quote-aware with the rule YAML and sh share, instead of being parsed per context (Change Requests 1-2).
- **Upstream defects identified:** None
- **Verification (exact):** isolated copy: 137/137. Real tree: 141/141 (4 more from reachable git history). Pre-fix control (HEAD setup): 52 failures, all in (i). Mutants: bare-key-only gave 18 failures, all in (i2b). Both-markers-required gave 5, (i2c) label-only. No date check gave 12, date effect plus date-only. No block scoping gave 2, (i4). Shellcheck: no new findings against HEAD. `check_links.py --build`: SWEEP PASSED. `tests/test_gitlab_contribution_job.py`: 8 passed. `test_setup_git.sh` and `test_contribution_check.sh` pass.

## Post-Review Changes

### Change Request 1 (2026-11-09)
- **Requested by user:** comment-only lines were appended to the job body and searched for markers. A comment in the current job, or a commented-out old job after it, produced false "outdated job" warnings (CONFIRMED with PyYAML-equal inputs). Exclude comment-only lines and add regression cases.
- **Changes made:** `_gitlab_contribution_job_stale_effects` skips lines matching `^[[:space:]]*#` when building the job body. These are YAML comments outside the script, and shell comments inside its literal block, so they never run. Added test case (i5): a YAML-comment note and a script-block shell-comment note inside the current job, and the oldest shipped job commented out after the current one. Both expect no warning and a byte-identical file, and `fixture_has` guards confirm each input carries the markers. A marker in a trailing comment on a code line still warns (the conservative direction; not requested).
- **Verification:** reproduced both false positives before the fix (both effects for the commented-out job, the date effect for the in-job note); both silent after it. Real tree 151/151, isolated copy 147/147. Mutant (comment lines counted again): exactly the 4 (i5) checks fail. Shellcheck: no new findings.
- **Files affected:** `.aitask-scripts/aitask_setup.sh`, `tests/test_setup_contribution_workflow.sh`.

### Change Request 2 (2026-11-09)
- **Requested by user:** trailing comments on code lines still reached the body. `image: alpine:latest # old cutoff: date -u -d '6 hours ago'` (PyYAML-equal to the template) produced the date warning (CONFIRMED by reproduction). Detection must not describe the active job from a comment; add YAML-equivalent regression coverage.
- **Changes made:** new `_gitlab_ci_strip_comment` in `aitask_setup.sh` replaces the comment-only-line skip. It drops each job line's comment from the first word-initial `#` (line start or after whitespace) outside `'…'` / `"…"` quotes, the rule both YAML and sh use. Backslash escapes are kept (`\ #`, and `\"` inside double quotes), and so are in-word `#` (`$#`, `${#x}`, `a#b`). If a quote is still open at end of line (a YAML plain scalar such as `it's`, or a string continuing on the next line), the line is cut at the first word-initial `#` instead. Backslashes are written `"\\"` so shellcheck stays at no new findings. Tests (i6): the reviewer's image trailing comment (YAML-equal, verified), a trailing shell comment after `PAGE=1` carrying the label filter, a comment after an apostrophe plain scalar (PyYAML reads `NOTE` as `"it's the current job"`), all expecting no warning. A positive control expects the old job to still warn with both effects when its live marker lines start with a quoted word-initial `#` and an in-word `${#PAGE}`.
- **Verification:** stripper probe table (11 inputs, all as intended). Real tree 169/169, isolated copy 165/165, pre-fix control 58 failures. Mutants, each failing only its own case: quotes ignored, 6 checks, (i6) quoted-hash. No stripping, 8 checks, (i5)/(i6) comment cases. No unterminated-quote fallback, 2 checks, (i6) apostrophe. `#` anywhere ends the line, 1 check, the (i6) date effect. The first mutant batch was discarded: `/tmp` hit "Disk quota exceeded" partway through (other runs' leftovers), and those logs carried write errors. Every accepted log was then checked for quota/write errors (0).
- **Residual (accepted):** a string quoted across lines in a hand-edited job can be misread (quote state is per line), giving a missed or, in contrived inputs, a spurious warning. Shipped jobs have no such lines, and setup still never modifies the file.
- **Files affected:** `.aitask-scripts/aitask_setup.sh`, `tests/test_setup_contribution_workflow.sh`.
