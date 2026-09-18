---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [trails, python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1794
followup_kind: upstream_defect
created_at: 2026-09-18 10:51
updated_at: 2026-09-18 10:52
---

## Origin

Found while working t1828 (unrelated change), immediately after merging t1826.
Filed as an upstream defect: t1826 is already archived and nobody owns this.

## Upstream defect

- `tests/test_cd_guard_lint.sh:269 — "helper: cwd is the per-user dir" compares a string-constructed path against canonicalized `pwd` output, so it fails on any host whose TMPDIR ends with a slash (macOS default)`

## Symptom

`bash tests/test_cd_guard_lint.sh` → **91 passed, 1 failed, 92 total** on macOS.

```
FAIL: helper: cwd is the per-user dir
  expected output containing '/var/folders/.../T//ait_cd_guard_yK4ka3/htmp/ait-test-cwd-501'
  got                        '/var/folders/.../T/ait_cd_guard_yK4ka3/htmp/ait-test-cwd-501'
```

Note the `T//` in the **expected** value and `T/` in the actual. That is the
whole bug.

## Root cause

Verified, not inferred — reproduced standalone:

1. macOS sets `TMPDIR` **with a trailing slash**: `/var/folders/fm/…/T/`.
   (Linux normally has `TMPDIR` unset, so `mktemp` gets the `/tmp` fallback and
   there is no doubled slash — which is why this shipped green in CI.)
2. `tests/test_cd_guard_lint.sh:43` builds the temp root as
   ```bash
   TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_cd_guard_XXXXXX")"
   ```
   BSD `mktemp` echoes back the path it was given, doubled slash included, so
   `$TMP` literally contains `…/T//ait_cd_guard_XXXXXX`.
3. `:263` derives `H_TMP="$TMP/htmp"`, inheriting the `//`.
4. `:266` runs the helper and captures **`pwd`**, which is canonical — the
   kernel/shell collapses `//` to `/`.
5. `:269` asserts the captured output *contains* the constructed
   `"$H_TMP/ait-test-cwd-$(id -u)"`. Constructed (doubled) never appears inside
   canonical (collapsed), so `assert_contains` fails.

Standalone reproduction:

```
$ TMP_DEMO="$(mktemp -d "${TMPDIR:-/tmp}/ait_demo_XXXXXX")"
$ echo "$TMP_DEMO/htmp/x"                                  # constructed
/var/folders/fm/…/T//ait_demo_R8BUFs/htmp/x
$ (mkdir -p "$TMP_DEMO/htmp/x"; cd "$TMP_DEMO/htmp/x"; pwd) # resolved
/var/folders/fm/…/T/ait_demo_R8BUFs/htmp/x
```

## This is a test bug, not a cd-guard bug

`enter_scratch_cwd` does exactly the right thing — it lands in the per-user
scratch dir; only the assertion's *spelling* of that path is wrong. The scanner
itself is fine: `--check` over the live tree passes, and the other 91 assertions
pass. So the impact is a permanently red suite file on macOS (noise that trains
people to ignore it), **not** a missed `cd` violation.

Confirmed pre-existing and unrelated to the change that found it: checked out
`origin/main` in a throwaway worktree with none of t1828's commits and got the
identical `91 passed, 1 failed`.

## Suggested fix

Compare canonical against canonical. Either normalize the expectation at the
point of construction —

```bash
TMP="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/ait_cd_guard_XXXXXX")" && pwd)"
```

— which fixes every later derivation in the file at once, or normalize just this
assertion's expected value. The first is preferable: `$TMP` feeds many other
paths in this file, and any future assertion comparing one against `pwd` output
would hit the same trap.

## Worth checking while in there

- **120 test files** use the same `mktemp -d "${TMPDIR:-/tmp}/…"` shape, so the
  doubled-slash `$TMP` is repo-wide. A grep for the *comparison* pattern
  (`assert_*` against `$(pwd)` / helper `pwd` output) currently matches **only**
  `tests/test_cd_guard_lint.sh`, so the failure is confined to this one file
  today — but the latent trap is broad. Consider whether
  `tests/lib/scratch_cwd.sh` or `tests/lib/asserts.sh` should offer a
  canonicalizing helper so the next such assertion cannot repeat it.
- This is the second macOS-only defect in this area in as many tasks: t1828 fixed
  `_tmux_bootstrap_default_session_scan` passing `LC_ALL=C` to awk but not to the
  `tr` feeding it (BSD `tr` aborts on invalid UTF-8), which had 12 tests red on
  macOS. Both shipped green on Linux. Worth asking whether the suite gets a macOS
  run anywhere before release.

## Verification

- `bash tests/test_cd_guard_lint.sh` → 92 passed, 0 failed on macOS.
- Still passes on a host where `TMPDIR` is unset or has no trailing slash — set
  `TMPDIR=/tmp/` explicitly to prove the fix covers the trailing-slash case
  rather than accidentally depending on its absence.
- `python3 tests/lib/cd_guard_scan.py --check tests/*.sh` is unchanged.
