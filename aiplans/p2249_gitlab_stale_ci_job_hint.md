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
