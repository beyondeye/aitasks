---
Task: t926_audit_scripts_for_macos_compat_6_26.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t926 — Periodic macOS Compatibility Audit (June 2026)

## Context

This is a **periodic** audit (not a bug fix) of the aitasks framework's bash and
Python scripts for macOS/BSD compatibility. Prior audits (t186, t209, t211, t213,
t658, t931, t932, t934) progressively absorbed the known footgun classes
(GNU-only `sed`/`awk`/`grep`, `date -d`, `mktemp --suffix`, `base64 -d`,
`#!/bin/bash` shebangs, `wc -l` whitespace). The task asks to: (1) re-audit all
bash + Python scripts, (2) re-run the full test suite on macOS, and (3) **create
follow-up tasks to fix any issues found** — fixes are NOT applied inline.

Environment confirmed: Darwin arm64, bash 5.3 (brew), BSD awk (`20200816`), BSD sed.
Inventory: 94 top-level + 111 total `.sh` in `.aitask-scripts/`, 113 `.py`,
177 bash tests in `tests/`.

**Plan re-verified after remote pull** (brought in t923_5 — consolidated test
asserts into the new `tests/lib/asserts.sh`, touching ~30 test files; plus the
t931/t932 fixes already in baseline). Re-ran the full static sweep against the
pulled tree: results **identical** — still clean. The new `tests/lib/asserts.sh`
is portability-aware (explicitly trims BSD `wc -l` leading-space padding). Test
count 176→177; production `.sh`/`.py` counts unchanged.

## Findings so far (static sweep — completed during planning)

The static sweep against every footgun class in
`aidocs/framework/sed_macos_issues.md` is **essentially clean**:

- GNU-only `sed` BRE quantifiers (`\?`/`\+`/`\|` outside `-E`): **none**.
- gawk-only 3-arg `match(str,re,arr)`: **none** (hits were a comment, a 2-arg
  `match()` + `substr()`, and Python `would_match()` — all false positives).
- `grep -P`/`-oP`: **none** (only a comment in `test_sed_compat.sh`).
- `date -d`: all 5 production-script hits are **guarded** with a
  `date --version` / `date -d "1 hour ago"` probe and a BSD `date -j`/`-v`
  fallback (`aitask_verified_update.sh`, `aitask_usage_update.sh`,
  `aitask_explain_context.sh`, `aitask_plan_verified.sh`,
  `lib/verified_update_lib.sh`). Correct.
- `base64 -d`: only inside the Linux branch of `lib/repo_fetch.sh`'s
  `_rf_base64_decode` (Darwin branch uses `-D`). Correct.
- `mktemp --suffix`, `sed \U`/`\L`: **none** (only comments).
- `#!/bin/bash`: the `test_find_files.sh` hits are inside heredoc **test
  fixtures** (`cat > src/*.sh << 'FILEEOF'`), not the test's own shebang. Not a bug.
- Python: no GNU-only shell-outs (`readlink -f`, `stat -c`, etc. — none).

Two **borderline** test-only cases (functionally portable today via fallback,
candidate cleanup only): `tests/test_fold_mark.sh:204` and
`tests/test_fold_file_refs_union.sh:162` use bare `sed -i 's/...' file
2>/dev/null || { sed -i.bak ...; }` — works on macOS via the `sed -i.bak`
fallback but is fragile. Will note, not block on.

## Implementation Steps

This is an audit; the "implementation" is running the dynamic half (test suite)
and turning findings into follow-up tasks + a documentation record.

### Step 1 — Run the full bash test suite on macOS
Run all 176 tests in `tests/*.sh` via a capture loop, recording per-test
PASS/FAIL and saving output for failures to a temp dir. Each test is
self-contained and prints its own PASS/FAIL summary; capture exit code + tail of
output. (Run sequentially to avoid git-worktree/lock contention between tests.)

### Step 2 — Triage failures
For each failing test, categorize the root cause:
- **(a) macOS/BSD portability** — a GNU-ism in the script-under-test or the test
  itself (the actionable findings).
- **(b) Environmental/preexisting** — missing venv deps (`yaml`/`textual`/`rich`),
  missing CLIs (`codex`/`gemini`), stale hand-curated copy lists, stale
  skill-count expectations — these reproduce on Linux too (per t658). Not macOS
  bugs, but per the user they DO get their own follow-up task(s) in Step 3(b).
Confirm category (a) findings by reading the offending line and matching it to a
documented footgun class.

### Step 3 — Create follow-up tasks for ALL failures found
Two buckets of follow-up tasks, both via the **Batch Task Creation Procedure**
(`aitask_create.sh --batch`):

**(a) macOS/BSD portability follow-ups.** For each distinct macOS-portability
root cause found (grouped by cause, not per-test), create a `bug` task, labels
`[macos, bash_scripts]`, priority matched to impact, with the offending
`file:line` + footgun class + suggested portable fix. If the audit finds **no**
genuine portability bug, create **zero** macOS fix tasks (a clean audit is a
valid outcome) — optionally one low-priority cleanup task for the two borderline
`sed -i` test cases.

**(b) Non-macOS test-failure follow-up(s).** Per the user's instruction, the
environmental/preexisting test failures (missing venv deps, missing CLIs, stale
copy lists / skill-count expectations) are NOT just documented — create a
separate follow-up `bug`/`chore` task (labels `[bash_scripts]`, NOT `macos`)
capturing the failing tests grouped by root cause, so they get fixed too. Group
into one task per coherent root cause (e.g. one for stale hand-curated copy
lists, one for stale skill-count expectations) rather than a single catch-all,
unless the failures share one cause.

### Step 4 — Record the audit in the macOS guide
Append a `## Files Audited in t926` section to
`aidocs/framework/sed_macos_issues.md` (mirroring the `t658` section): platform,
inventory scanned, static-sweep result, test-suite baseline (N PASS / M FAIL),
the macOS-attributable failures (if any) and the follow-up task IDs created, and
an explicit list of the environmental/out-of-scope FAIL buckets.

## Files to Modify
- `aidocs/framework/sed_macos_issues.md` — append the `## Files Audited in t926`
  audit-record section (the only source-tree edit; doc only).
- New task files under `aitasks/` — created by `aitask_create.sh --batch` only if
  genuine portability issues are found.

## Reusability
- Static-sweep commands: the documented greps in
  `aidocs/framework/sed_macos_issues.md` ("After fixing one portability bug,
  sweep for the whole class").
- Portable helpers already in place: `sed_inplace()`, `portable_date()` in
  `.aitask-scripts/lib/terminal_compat.sh`.
- Follow-up task creation: Batch Task Creation Procedure
  (`task-creation-batch.md`).

## Risk

### Code-health risk: low
- Only edit to tracked source is a documentation append; no production code
  changes. New follow-up task files are additive metadata. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The audit could mis-triage an environmental failure as portability (or vice
  versa); mitigated by reading the offending line and matching it to a documented
  footgun class before filing. · severity: low · → mitigation: none needed

No before/after risk-mitigation tasks needed (both axes low).

## Verification
- Static sweep: re-run the documented class greps — expect clean (already
  confirmed during planning).
- Dynamic: the per-test capture loop produces a `N PASS / M FAIL` summary; every
  category-(a) failure must map to a macOS follow-up task ID, and every
  category-(b) failure must map to a non-macOS follow-up task ID (and appear in
  the doc's out-of-scope list).
- Doc: `grep -q '^## Files Audited in t926' aidocs/framework/sed_macos_issues.md`.
- Created follow-up tasks (if any) appear in `ait ls` with `[macos, bash_scripts]`
  labels.

## Step 9 (Post-Implementation)
Commit the doc update (code) and any created task files (`./ait git`), then
archive t926 via `aitask_archive.sh 926`. No branch/worktree to clean up
(working on current branch).
