---
Task: t1724_drift_check_two_dot_diff_inflates_overlap.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1724 — Drift check's two-dot `git diff` inflates OVERLAP

## Context

`aitask_remote_drift_check.sh` is the post-plan guard that warns "the remote
moved under you, and it touched files your plan references". Its `OVERLAP:`
verdict is the **strong** half of that check — always treated as strong
regardless of the `warn` / `strong-only` setting, and the branch that interrupts
the user immediately before implementation.

Line 211 computes the remote-changed file set with a **two-dot** `git diff`:

```bash
remote_files=$(git diff --name-only "${BASE_BRANCH}..origin/${BASE_BRANCH}" 2>/dev/null) || remote_files=""
```

Two dots mean different things in `git log` and `git diff`. In `git log`, `A..B`
is a commit range. In `git diff` it is just `git diff A B` — an
endpoint-to-endpoint comparison — so the line reports every file that *differs
between the two tips*, **including files changed only by the user's own local
commits**. The correct form for "what the remote changed" is three-dot
(`A...B`), which diffs from the merge base.

Re-confirmed live during planning, at a tree state with 3 remote-only commits:
122 files under the two-dot form against 23 under three-dot. The task file
records an independent earlier measurement (78 vs 9).

Both are **dated observations, not verification targets.** `main` advanced later
in the same session (to 0 remote-only / 13 local-only commits), at which point
the helper short-circuits to `UP_TO_DATE` and never reaches line 211 at all — so
no live-repo measurement is a reproducible check on this fix. Verification rests
entirely on Test 15, which invokes the real helper against a fixture built to
have the divergent shape.

The `AHEAD:<n>` count is derived separately with `git rev-list --count`, where
two-dot *is* a commit range — so that value was always correct. The symptom is a
mismatch between a correct commit count and an inflated file list, which is what
makes the bug hard to spot by eye. The outcome is the "cry wolf" failure the
script's own `FETCH_FAILED` note warns about: a guard that fires on the user's
own landed work trains the user to click past it, and the real overlap goes past
with it.

**Intended outcome:** `OVERLAP:` names only files the remote actually changed.

## Scope of the framework-wide sweep (already executed)

Scope item 2 of the task — "check for the same two-dot-in-`git diff` confusion
elsewhere" — was run during planning over `*.sh`, `*.py`, `*.md`, `*.j2`:

| site | verdict |
|---|---|
| `.aitask-scripts/aitask_remote_drift_check.sh:211` | **the bug** — endpoints are divergent branch tips |
| `.aitask-scripts/aitask_revert_analyze.sh:244` (`<hash>^..<hash>`) | safe — `<hash>^` is an ancestor of `<hash>`, so two-dot ≡ three-dot |
| `.claude/skills/aitask-qa/change-analysis.md:43,47` (`<first>^..<last>`) | safe — same ancestor shape |
| `.claude/skills/aitask-shadow/impl-challenge.md:102` (+ its three goldens) | safe — same ancestor shape |
| `.claude/skills/aitask-docs-gap/SKILL.md:115` (`<BASE_TAG>..HEAD`) | safe — a release tag on the same line of history is an ancestor of `HEAD` |

**Only one site is wrong.** Every other two-dot `git diff` in the framework has
an ancestor on the left, where the two forms are identical by definition. No new
source-scan guard test is added for this: a grep-shaped guard cannot tell an
ancestor pair from a divergent one, so it would flag all five safe sites. The
distinction is recorded as a comment at the fixed site instead.

## Implementation

### Pre-phase (risk mitigations)

1. `[mutant_control_before_fix]` **Before applying the step-1 edit**, add Test 15
   (step 3) to `tests/test_remote_drift_check.sh` and run
   `bash tests/test_remote_drift_check.sh` against the **still-unfixed** script.
   Record the output: `15c` must FAIL (the two-dot form reports
   `OVERLAP:tests/test_archive.sh`) while `15a`, `15b` and `15d` PASS. If `15c`
   passes here, the fixture is not discriminating — fix the fixture before
   touching line 211, because a test that was never red proves nothing about an
   operator swap. Only then proceed to step 1.

### 1. Fix the diff form — `.aitask-scripts/aitask_remote_drift_check.sh:209-211`

Replace the two-dot form with three-dot and record *why*, so the next reader does
not "simplify" it back:

```bash
# --- Files touched by remote-only commits ---
# THREE dots, deliberately. In `git diff` (unlike `git log`) `A..B` is plain
# `git diff A B` -- an endpoint-to-endpoint comparison that also reports files
# changed only by the user's OWN local commits. `A...B` diffs from the merge
# base, which is what "files the remote changed" actually means. Inflating
# OVERLAP -- the strong half of this check -- with the user's landed work is the
# cry-wolf failure that trains the user to click past a real hit (t1724).
# (The AHEAD count above uses `git rev-list`, where two dots ARE a commit range
# and are correct.)
remote_files=""
remote_files=$(git diff --name-only "${BASE_BRANCH}...origin/${BASE_BRANCH}" 2>/dev/null) || remote_files=""
```

No other line changes. The output protocol, exit codes, and the `AHEAD` /
`UP_TO_DATE` / `NO_OVERLAP` branches are untouched.

### 2. Correct the doc that quotes the old form — `aidocs/framework/plan_path_reference_extraction_findings.md:18`

The line reads:

> Its output is intersected with `git diff --name-only <base>..origin/<base>` by
> exact full-line match (`grep -Fxf`).

Change `<base>..origin/<base>` to `<base>...origin/<base>`. This is the only
document that names the diff form; nothing else in `aidocs/`, the skills, or the
website describes it. (The stale extractor snippet earlier in that same file —
it quotes the pre-`lib/plan_paths.py` `grep -oE` pipeline — is a separate
pre-existing staleness and is **out of scope here**; touching it would widen this
bug fix into a doc refresh.)

### 3. Regression test — new Test 15 in `tests/test_remote_drift_check.sh`

Appended before the `# Summary` block, following the file's existing fixture
idiom (`make_branch_mode_pair`, `register_cleanup`, `mark_branch_mode`,
`write_plan_file`, top-level `assert_*` — this file does **not** run bodies in
subshells, so no file-backed counters are needed).

The fixture must reproduce the real shape: a file that exists on **both** sides
and is modified **only locally**, while the remote independently modifies a
different plan-referenced file.

```bash
# ============================================================
# Test 15: local-only commits must not inflate OVERLAP (t1724)
# ============================================================
#
# The bug: line 211 used `git diff BASE..origin/BASE`, which in `git diff` is a
# plain tip-to-tip comparison, so a file the USER changed locally was reported
# as remote drift. The three-dot form diffs from the merge base.
#
# Both plan-referenced files are load-bearing here:
#   - .aitask-scripts/aitask_archive.sh -- changed on the REMOTE only. It is the
#     POSITIVE CONTROL: it must still be reported, so the test cannot pass by
#     the overlap set having gone empty.
#   - tests/test_archive.sh            -- changed LOCALLY only. It must NOT be
#     reported. Without this local-only commit the fixture passes under BOTH
#     diff forms and proves nothing.

echo "--- Test 15: local-only commits do not inflate OVERLAP ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"

# Both sides share tests/test_archive.sh at a common base commit.
(
    cd "$root/local"
    mkdir -p tests
    echo "baseline" > tests/test_archive.sh
    git add tests/test_archive.sh
    git commit --quiet -m "add shared test file"
    git push --quiet origin "$default_branch"
)

# Another PC pushes a change to a DIFFERENT plan-referenced file.
git clone --quiet "$root/origin.git" "$root/other" 2>/dev/null
(
    cd "$root/other"
    git config user.email "other@example.com"
    git config user.name  "Other"
    mkdir -p .aitask-scripts
    echo "patched" > .aitask-scripts/aitask_archive.sh
    git add .aitask-scripts/aitask_archive.sh
    git commit --quiet -m "patch archive script"
    git push --quiet origin "$default_branch"
)

# The user's OWN local commit touches the shared file. Never pushed.
(
    cd "$root/local"
    echo "local edit" >> tests/test_archive.sh
    git add tests/test_archive.sh
    git commit --quiet -m "local-only change to the shared test file"
)

mark_branch_mode "$root/local"
plan_path="$root/local/plan.md"
write_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan_path" 2>&1)
assert_contains "15a: remote-only commit count is unaffected" "AHEAD:1" "$result"
assert_contains "15b: positive control -- remote-changed planned file still overlaps" \
    "OVERLAP:.aitask-scripts/aitask_archive.sh" "$result"
assert_not_contains "15c: locally-changed planned file is NOT reported as remote drift" \
    "OVERLAP:tests/test_archive.sh" "$result"
assert_not_contains "15d: no NO_OVERLAP when there is overlap" "NO_OVERLAP" "$result"
```

`write_plan_file` (line 116) already references both
`.aitask-scripts/aitask_archive.sh` and `tests/test_archive.sh`, so no new plan
fixture is needed.

**Pre-fix behavior of this test:** 15c fails (two-dot reports
`tests/test_archive.sh` as differing between the tips). 15a, 15b, 15d pass under
both forms — which is exactly why 15b is present as the positive control.

### Post-phase (risk mitigations)

1. `[document_two_dot_diff_footgun]` Add a short subsection to
   `aidocs/framework/shell_conventions.md` recording the foot-gun: in `git diff`,
   `A..B` is **not** a commit range — it is plain `git diff A B` — so it reports
   the user's own local commits too; use `A...B` (merge-base) whenever the two
   endpoints can diverge. State the discriminator explicitly: two-dot is safe
   **only** when the left side is an ancestor of the right (`<hash>^..<hash>`,
   `<tag>..HEAD`), which is why `aitask_revert_analyze.sh`, `change-analysis.md`,
   `impl-challenge.md` and `aitask-docs-gap/SKILL.md` are correct as written, and
   why no grep-shaped guard test is added (it could not tell those apart from the
   real bug). Cite t1724. Then re-run `shellcheck .aitask-scripts/aitask_*.sh` —
   unchanged, doc-only — and confirm no website page duplicates the guidance
   (`aidocs/` is agent-facing; nothing under `website/content/` covers it, so
   `check_links.py` is not implicated).

## Verification

1. **The mutant fails, the fix passes** — the red half is the
   `[mutant_control_before_fix]` pre-phase above (Test 15 added first, run
   against the unfixed script, `15c` observed failing). Here, confirm the green
   half: after step 1's edit, all four of `15a`–`15d` pass. A regression test for
   an operator swap is worthless until it has been seen red.
2. `bash tests/test_remote_drift_check.sh` — full file green, `ALL TESTS PASSED`,
   exit 0. Tests 4, 5, 13 and 14 are the existing OVERLAP/NO_OVERLAP coverage and
   must be unchanged.
3. `shellcheck .aitask-scripts/aitask_remote_drift_check.sh` — clean.
4. No golden regeneration is required: no `.md.j2`, skill surface, or closure
   procedure is touched. The three `impl-challenge-*.md` goldens appeared in the
   sweep as *safe* sites and are not edited.

## Risk

### Code-health risk: low

- The corrected form reports the *net* merge-base→remote diff, so a remote that
  touches a file and reverts it within the same push is not reported. This is a
  pre-existing property of `git diff` shared by the form being replaced — the
  change neither introduces nor widens it — and the blast radius is one operator
  on one line with no protocol change. · severity: low · → mitigation: none
  needed; noted here as provenance for the chosen form.
- Recurrence: the sweep found four *safe* two-dot `git diff` sites that are
  textually indistinguishable from the bug, so nothing mechanical stops a future
  author from reintroducing the divergent-endpoint form (or from "fixing" a safe
  ancestor site). · severity: low (residual — addressed by inline post-phase
  `document_two_dot_diff_footgun`) · → mitigation: inline post-phase
  `document_two_dot_diff_footgun`

### Goal-achievement risk: low

- A regression test for an operator swap can pass vacuously: drop the local-only
  commit and the fixture is green under both forms, and a fix that emptied the
  overlap set entirely would also look green. · severity: low (residual —
  addressed by inline pre-phase `mutant_control_before_fix`, plus the `15b`
  positive control pinned in step 3) · → mitigation: inline pre-phase
  `mutant_control_before_fix`

### Planned mitigations
- timing: pre-phase | name: mutant_control_before_fix | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — regression test could pass vacuously | desc: Run Test 15 against the unfixed script and require 15c to fail before the one-line fix is applied.
- timing: post-phase | name: document_two_dot_diff_footgun | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — recurrence of the two-dot/three-dot confusion | desc: Record the git diff two-dot foot-gun and the ancestor-vs-divergent discriminator in aidocs/framework/shell_conventions.md.

## Post-implementation

Step 9 (Post-Implementation) handles cleanup, archival, and merge.

---

## Final Implementation Notes

All plan steps executed as approved. Files changed (four, exactly as planned):

| file | change |
|---|---|
| `.aitask-scripts/aitask_remote_drift_check.sh` | `..` → `...` on the remote-changed-file diff, plus the explanatory comment block |
| `tests/test_remote_drift_check.sh` | new Test 15 (`15a`–`15d`) |
| `aidocs/framework/plan_path_reference_extraction_findings.md` | corrected the quoted diff form |
| `aidocs/framework/shell_conventions.md` | `[document_two_dot_diff_footgun]` post-phase |

**Pre-phase `[mutant_control_before_fix]` — satisfied, observed red.** Test 15 was
added *first* and run against the still-unfixed script. `15c` failed with exactly
the bug's signature, while `15a`, `15b` and `15d` passed:

```
FAIL: 15c: locally-changed planned file is NOT reported as remote drift
  (expected output NOT containing 'OVERLAP:tests/test_archive.sh', got 'AHEAD:1
   OVERLAP:.aitask-scripts/aitask_archive.sh
   OVERLAP:tests/test_archive.sh')
Results: 45 passed, 1 failed (of 46 total)
```

The fixture is therefore discriminating: the local-only commit is what the
assertion turns on, and `15b` (the remote-only positive control) held throughout,
so the test cannot pass by the overlap set going empty.

**After the fix:** `Results: 46 passed, 0 failed (of 46 total) / ALL TESTS PASSED`.
Tests 4, 5, 13 and 14 — the pre-existing OVERLAP/NO_OVERLAP coverage — unchanged.

**Verification results:**

1. Mutant red → fix green: done, transcript above.
2. `bash tests/test_remote_drift_check.sh` → 46/46, `ALL TESTS PASSED`.
3. `shellcheck .aitask-scripts/aitask_remote_drift_check.sh` → **7 findings before
   the change, 7 after** (compared against `git show HEAD:` of the same file). All
   are pre-existing `SC1091` *info* notices about `source`d libs not passed as
   input, on lines this change does not touch. No new findings. Worth recording
   because the command exits non-zero on those info notices, so "clean" would have
   been the wrong word for a passing result.
4. No golden regeneration: `git status` shows exactly the four files above — no
   `.md.j2`, skill surface, or closure procedure. The three `impl-challenge-*.md`
   goldens were classified *safe* by the sweep and are untouched.

**Deviations from the plan:** one, cosmetic. The post-phase called for "a short
subsection" in `shell_conventions.md`; that file is a flat bullet list with no
`##` headings, so the guidance was written as a two-paragraph bullet in the
existing style rather than as a new heading. Content is as specified, including
the ancestor-vs-divergent discriminator, the four safe sites named so they are
not "fixed" later, and the reason no scan guard is added.

**Observation, not a verification target.** The `git status` of this repository
during implementation had `main` at 0 remote-only commits, where the helper
short-circuits to `UP_TO_DATE` and never reaches the fixed line — reconfirming
that no live-repo measurement is a reproducible check on this change, and that
Test 15 is the whole of the proof.

### Canonical notes

- **Actual work done:** Exactly the approved scope — the three-dot fix, the
  Test 15 regression case (added first and observed red), the corrected doc
  reference, and the `document_two_dot_diff_footgun` post-phase. Plus the
  framework-wide sweep, which was executed during planning and is recorded in the
  plan body: one real defect, four look-alike sites that are correct.
- **Deviations from plan:** One, cosmetic — the post-phase guidance went into
  `shell_conventions.md` as a bullet in its flat list rather than as a new
  subsection, because that file has no `##` headings. Content unchanged.
- **Issues encountered:** None. The one-line change behaved as diagnosed, and
  every pre-existing test in the file stayed green.
- **Key decisions:** (1) No source-scan guard test. Four framework sites use
  two-dot `git diff` correctly because their left endpoint is an ancestor, and a
  grep cannot distinguish those from the real bug — it would flag all four. The
  discriminator is documented in prose instead. (2) `shellcheck` on the changed
  script is reported as *unchanged findings* (7 before, 7 after) rather than
  "clean": the command exits non-zero on pre-existing `SC1091` info notices about
  `source`d libs, so a bare pass/fail would have been misleading either way.
  (3) Verification deliberately carries no live-repo measurement — see the
  observation above.
- **Upstream defects identified:**
  - `aidocs/framework/plan_path_reference_extraction_findings.md:12-16 — the
    quoted extraction snippet is stale; it shows the pre-`lib/plan_paths.py`
    `grep -oE … | sed | sort -u` pipeline as "the single implementation today",
    but that grammar moved into `.aitask-scripts/lib/plan_paths.py` and is now
    reached through the lazy bridge, with three other consumers. The document
    therefore misdescribes the current code to anyone reading it as the record of
    how plan paths are extracted. Noticed while correcting the diff form two lines
    below it; deliberately left out of scope here to keep this a bug fix rather
    than a doc refresh.

## Post-Review Changes

### Change Request 1 (2026-09-07 16:40)

- **Requested by user:** At the Step-8b upstream-defect offer, the user chose
  "fit it here" — fix the stale extractor snippet in this task rather than
  spawning a follow-up. This reverses the plan's explicit "out of scope here"
  scoping decision for that one item, by the user's call.
- **Changes made:** Replaced the stale block in
  `aidocs/framework/plan_path_reference_extraction_findings.md` (which presented
  the pre-`lib/plan_paths.py` shell pipeline as "the single implementation
  today") with the current `_EXTENSIONS` / `_TOKEN` grammar from
  `.aitask-scripts/lib/plan_paths.py`, plus three facts the old text omitted or
  got wrong:
  - it is **not** the only extractor — `aitask_change_surface.sh` carries a
    broader, allowlist-free one (t1263), so the findings are scoped to *this*
    grammar;
  - its four consumers are named (drift check via the lazy `plan_paths_sh.sh`
    bridge, `parallel_admission.py`, `parallel_admission_collect.py`,
    `trail_gather.py`), which is why it is centralized;
  - the findings were measured against the replaced pipeline and still
    reproduce, because the regex is byte-identical in meaning; the only
    behavioral delta is codepoint vs locale-collated ordering, which no verdict
    depends on since the intersection is `grep -Fxf`.

  Every claim was checked against source before writing (grammar lines,
  `extract()` docstring, `aitask_change_surface.sh:226`, and the three importing
  modules) rather than carried over from the plan.
- **Files affected:** `aidocs/framework/plan_path_reference_extraction_findings.md`
- **Effect on the canonical bullet:** the defect listed under **Upstream defects
  identified** above is now **fixed in this task**, not deferred. It is left in
  place as the provenance record of how it was found.
