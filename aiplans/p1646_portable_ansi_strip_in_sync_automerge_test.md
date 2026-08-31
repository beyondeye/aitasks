---
Task: t1646_portable_ansi_strip_in_sync_automerge_test.md
Base branch: main
Output branch: main
---

# t1646 — Portable ANSI strip in the sync auto-merge test

## Context

`tests/test_sync_branch_mode_automerge.sh:334` strips the ANSI colour wrapper
from `ait sync`'s stdout with

```bash
int_clean=$(printf '%s' "$int_out" | sed 's/\x1b\[[0-9;]*m//g')
```

`\xNN` is a **GNU sed extension**. BSD sed (macOS) does not recognise it and
matches the literal characters `x`, `1`, `b` instead, so on macOS the
substitution never fires and `$int_clean` is the *un-stripped* string. There is
no error — the caller just gets colour codes it believes were removed.

This is the same class of defect t1641 fixed at `tests/test_task_lock.sh:592`;
t1641 documented the `\xNN` row in `aidocs/framework/sed_macos_issues.md` and
fixed only its own site, because its scope was the lock CLI. This task closes
the remaining site, re-runs the class sweep that guide mandates, and — per the
confirmed risk mitigations — replaces that manual sweep with an enforced guard.

### What the empirical check found (correcting the task record)

The task file asserts that on macOS "whatever `$int_clean` is asserted against
fails against correct code". **That is not true at this site.** Verified by
capturing the real bytes of `$int_out` from a live run of Test 5b:

```
^[[0;34mFetching from remote...^[[0m
^[[0;34mPulling 2 new commits (rebase)...^[[0m
  - aitasks/t2_body.md
  - aitasks/t2_body.md

^[[0;34mOpening each conflicted file in true for resolution...^[[0m

^[[0;34mEditing: aitasks/t2_body.md^[[0m
```

All three assertions at lines 336–342 tolerate the wrapper:

| assertion | behaviour on the un-stripped string |
|---|---|
| `grep -c 'Auto-merged'` == 0 | still `0` — negative assertion, unaffected |
| `grep -cE 'RESOLVED\|PARTIAL:'` == 0 | still `0` — same |
| `assert_contains "Editing: aitasks/t2_body.md"` | still **passes** — the ESC codes sit *outside* the phrase, so the substring match succeeds |

So the site does **not** fail on macOS today. What it does is silently disable
the strip, leaving a live trap: assertion 3 passes for the wrong reason, and any
future tightening to an exact `assert_eq` — precisely the tightening
`test_task_lock.sh:592`'s own comment warns about — would then fail on macOS
against correct code.

The BSD behaviour and the fix were both confirmed by emulating what BSD sed
actually sees (`s/x1b\[[0-9;]*m//g`) against the captured bytes: it strips
nothing, while `sed $'s/\033\[[0-9;]*m//g'` strips cleanly.

### Sweep result

The guide-mandated sweep returns three hits; a widened sweep (`\x[0-9a-fA-F]{2}`
anywhere in `*.sh`, plus every `sed …[0-9;]*m` expression) confirms no fourth:

- `tests/test_task_lock.sh:592` — the explanatory NOTE comment (already fixed at :598)
- `tests/test_sync_branch_mode_automerge.sh:334` — **the site this task fixes**
- `tests/test_init_data.sh:617` — already portable (builds `$esc` separately)

Every other `\xNN` hit is inside a Python heredoc or bash `$'…'` ANSI-C quoting,
where `\xNN` is interpreted by Python/bash and is correct. The mandated grep also
false-positives on the word "par**sed**" (`tests/test_applink_content.sh:124`);
the guard below fixes that by anchoring `sed` to a word boundary.

## Implementation

### 1. Fix the strip — `tests/test_sync_branch_mode_automerge.sh`

Introduce a single named helper next to `setup_branch_mode_repos()` so the strip
expression has **one** definition shared by the real call site and its
portability control (rather than two copies that can drift):

```bash
# Portable ANSI strip.
# NOTE: $'\033[' — NOT 's/\x1b\[…' . GNU sed understands \x1b; BSD sed (macOS)
# does not — it matches a literal x, 1, b, so that form silently no-ops and the
# colour wrapper survives. The $'…' quoting makes BASH emit the literal ESC
# byte, so sed never has to interpret an escape.
# See aidocs/framework/sed_macos_issues.md.
strip_ansi() { sed $'s/\033\[[0-9;]*m//g'; }
```

Then line 334 becomes:

```bash
int_clean=$(printf '%s' "$int_out" | strip_ansi)
```

### Post-phase (risk mitigations)

Three confirmed mitigations, all inline (see `### Planned mitigations`).

#### P1 — `esc_strip_portability_control` — prove the transform, without coupling to colour

An earlier draft asserted that `$int_out` *does* carry an ANSI wrapper. That
couples this conflict-resolution test to `ait sync`'s **presentation policy**:
it would fail if colouring were legitimately dropped, even with the functional
stdout contract intact. Instead, prove the transform against a **synthetic**
string — non-vacuous by construction and presentation-independent:

```bash
# Portability control for strip_ansi, independent of whether `ait sync` colours
# its output: with the non-portable \x1b form this probe comes back untouched
# on BSD sed, so this assertion is what actually pins the platform behaviour.
assert_eq "strip_ansi removes ESC sequences (BSD/GNU portability control)" \
    "Editing: x" "$(printf '%s' $'\033[0;34mEditing: x\033[0m' | strip_ansi)"
```

plus a cheap integration sanity check after the real strip (harmless if the
output is ever uncoloured, because the probe above carries the real guard duty):

```bash
assert_eq "No ESC survives into int_clean" \
    "0" "$(printf '%s' "$int_clean" | grep -c $'\033' || true)"
```

Test 5b's count rises from 15 to **17**.

#### P2 — `sed_hex_escape_guard_test` — enforce the class, new file `tests/test_no_sed_hex_escape.sh`

Replaces the manual doc-mandated sweep with a repo-wide guard, modelled
structurally on `tests/test_no_raw_tmux.sh` (header-documented detection scope,
real-tree scan, then negative controls proving the guard can fail).

**Two-stage scan** — stage 1 is a fast per-file `grep` for candidates; stage 2
re-tests each candidate precisely. Both stages validated against the live tree.

```bash
PATTERN='(^|[^A-Za-z0-9_])(sed|awk|tr)[[:space:]][^|]*\\x[0-9a-fA-F]{2}'
```

Stage 2 applies two suppressions:

1. **Pure-comment lines** — trim leading whitespace, skip if the line starts `#`.
2. **Bash ANSI-C quoting, scoped to the segment.** A line-wide
   `grep -v "\$'[^']*\\x"` is **wrong**: it drops the whole line, so
   `printf '%s' $'\x1b'; sed 's/\x1b//' input` — a genuinely unsafe command
   sharing a line with an unrelated valid ANSI-C escape — is silently missed
   (verified). Instead, **blank each `$'…'` segment** (inside which `\xNN` is
   expanded by *bash* and is safe) and re-test the residue:

   ```bash
   scrub_ansic() {
     local s=$1 pre rest post
     while [[ $s == *\$\'*\'* ]]; do
       pre=${s%%\$\'*}; rest=${s#*\$\'}; post=${rest#*\'}
       s="$pre $post"          # a SPACE, never $'' — that would re-match and loop forever
     done
     printf '%s' "$s"
   }
   ```

`scan_files()` reads NUL-separated paths on stdin, so Test 1 feeds it
`git ls-files -z '*.sh'` (521 tracked scripts; naturally excludes
`website/node_modules`) while negative controls feed it `find` over a temp dir.

**Self-scan hazard — the guard must not flag its own fixtures.** Once this file
is tracked it is included in Test 1's scan, and a heredoc fixture containing the
literal `sed 's/\x1b//'` *does* match the pattern (verified). Rather than
allowlisting the file — which would blind the guard to a real defect introduced
there later — **build the fixtures at runtime from a split token** so the
forbidden sequence never appears contiguously in the source:

```bash
# This file is itself scanned by Test 1, so it must never contain the forbidden
# literal. Fixtures assemble it at runtime instead.
X='x'; BAD="\\${X}1b"        # -> \x1b
printf "%s\n" "sed 's/${BAD}//'" > "$TMP/rogue.sh"
```

Verified: the source above scans clean, and the file it generates is flagged.

Tests:

- **Test 1** — the real tree is clean. Failure message points at
  `aidocs/framework/sed_macos_issues.md` and the `$'…'` fix.
- **Test 2 (self-scan)** — scanning *this file* yields zero hits, so the
  no-literal invariant is pinned rather than assumed, and someone inlining a
  literal gets an immediate, legible failure instead of a puzzling Test 1 break.
- **Negative controls** — all nine validated already:
  `sed 's/\x1b//'` → flagged; `sed $'s/\x1b//'` and `sed $'s/\033…'` → clean;
  the **mixed** `printf '%s' $'\x1b'; sed 's/\x1b//' input` → **flagged**;
  two ANSI-C segments then an unsafe `sed` → flagged; `awk` and `tr` variants →
  flagged (neither GNU nor BSD `tr` understands `\xNN`); a `#`-comment → clean;
  the `par`**`sed`** false positive → clean.
- Header documents the known boundary: a trailing comment on a code line, and a
  `\xNN` separated from its `sed` by a pipe, are not detected.

Flat structure like `test_no_raw_tmux.sh`, so no `assert_counters_init` /
`assert_counters_load` is needed (that opt-in is only for `( … )` subshell
bodies — CLAUDE.md / t1207).

#### P3 — `correct_task_record` — fix the task file's defect claim

Edit `aitasks/t1646_portable_ansi_strip_in_sync_automerge_test.md`'s
`## Upstream defect` section so the record states the verified impact — the
strip silently no-ops on macOS, leaving a latent trap; the three assertions at
this site tolerate the wrapper and do **not** currently fail — and repeat it in
the Final Implementation Notes, so the false claim does not reach the archive.

## Verification

1. `bash tests/test_sync_branch_mode_automerge.sh` → **17 passed, 0 failed**
   (15 before; P1 adds 2). Baseline before the change is 15/15 — on Linux both
   sed forms behave identically, which is exactly why checks 2–4 matter.
2. **Byte-level proof the fix is real** (platform-independent ground truth; no
   macOS box here) — against the captured `$int_out`:
   `sed 's/x1b\[[0-9;]*m//g'` (what BSD sed sees) leaves `^[[0;34m…` intact,
   while `sed $'s/\033\[[0-9;]*m//g'` removes it.
3. `bash tests/test_no_sed_hex_escape.sh` → all pass, **run after
   `./ait git add`/`git add` so the file is tracked** and Test 1 actually scans
   it. Running it only while untracked is the trap that hides a self-flag.
4. Confirm the guard **can** fail: temporarily restore the `\x1b` form at line
   334 and check Test 1 flags exactly that line (it does today — the guard
   currently reports one hit against the unfixed tree, which is the live
   positive control).
5. `shellcheck tests/test_sync_branch_mode_automerge.sh tests/test_no_sed_hex_escape.sh`
   — no new findings.
6. `bash tests/run_all_python_tests.sh` is **not** required — no Python touched.

## Risk

### Code-health risk: low

One helper plus two assertions in one existing test file, and one new guard
test. No production code, no callers, no shared helper outside the test file.
The change strictly reduces a known portability defect class, and P2 converts
the manual sweep into an enforced invariant.

- The ESC-survival assertion is vacuous on its own — it passes trivially if the
  output is ever uncoloured · severity: low · → mitigation: inline post-phase
  `esc_strip_portability_control` (the synthetic probe carries the guard duty,
  so the vacuity is harmless and no presentation coupling is introduced)
- The guard would flag its own negative-control fixtures once tracked, and the
  failure would only appear *after* the commit that verified clean · severity:
  high · → mitigation: inline post-phase `sed_hex_escape_guard_test`
  (runtime-encoded fixtures + a self-scan test + verify-after-`git add`)
- A line-wide ANSI-C suppression would silently miss an unsafe command sharing
  a line with a valid `$'…\xNN'` escape · severity: high · → mitigation: inline
  post-phase `sed_hex_escape_guard_test` (segment-scoped scrubbing, with the
  mixed line as an explicit negative control)
- **Pre-existing, not introduced by this plan:** the `\xNN`-in-sed class recurs
  because the sweep that catches it is manual — two occurrences so far (t1641,
  t1646) · severity: medium · → mitigation: inline post-phase
  `sed_hex_escape_guard_test`
- The guard is regex-based and so has a known false-negative boundary (trailing
  comments; `\xNN` separated from its `sed` by a pipe) · severity: low · →
  mitigation: documented in the file header, per the "a guard that overclaims is
  worse than one with a known boundary" convention `test_no_raw_tmux.sh` sets

### Goal-achievement risk: low

The task's own `## Suggested fix` is exactly what step 1 implements, and the fix
has been empirically validated against real captured bytes. The guard's
detection pattern, its two suppressions, and its self-scan safety were all
validated against the live tree before being written into this plan.

- The task record's `## Upstream defect` claim ("… whatever `$int_clean` is
  asserted against fails against correct code") is false at this site: all three
  assertions tolerate the wrapper, so nothing observable is failing on macOS
  today. If the goal was "fix a failing macOS test", this delivers latent-trap
  removal and class closure rather than a behaviour fix · severity: low · →
  mitigation: inline post-phase `correct_task_record`

### Planned mitigations

- timing: post-phase | name: esc_strip_portability_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — silent-no-op strip is unguarded | desc: prove the strip against a synthetic ANSI probe (presentation-independent) plus a cheap ESC-survival check on the real output
- timing: post-phase | name: sed_hex_escape_guard_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: code-health — the \xNN-in-sed class recurs because the sweep is manual; plus the guard's own self-scan and line-wide-suppression hazards | desc: add tests/test_no_sed_hex_escape.sh, a repo-wide two-stage guard modelled on test_no_raw_tmux.sh, with segment-scoped ANSI-C suppression, runtime-encoded fixtures, a self-scan test and nine negative controls
- timing: post-phase | name: correct_task_record | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the task record overstates the defect's impact | desc: correct the task file's ## Upstream defect claim to the empirically verified impact and repeat it in the Final Implementation Notes

## Step 9 (Post-Implementation)

Standard: commit, merge to `main` (current-branch mode — nothing is forked),
archive `t1646` and this plan.
