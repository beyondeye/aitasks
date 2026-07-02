---
Task: t1002_fix_failed_verification_t822_4_item2.md
Worktree: (none — working on current branch, profile 'fast')
Branch: (current)
Base branch: main
---

# Plan: Fix shellcheck warnings on aitask_applink.sh (t1002)

## Context

t822_4 (manual verification) item #2 asserted that
`shellcheck .aitask-scripts/aitask_applink.sh` should report **no warnings**;
it failed, spawning this bug task. The task narrative attributes the failure to
"an offending change from t822_2".

**Diagnosis (corrected):** The failure is *not* a code regression from t822_2.
`aitask_applink.sh` emits only three **`SC1091` (info)** diagnostics —
"Not following: lib/… was not specified as input" — one for each sourced lib:

```
.aitask-scripts/lib/aitask_path.sh
.aitask-scripts/lib/python_resolve.sh
.aitask-scripts/lib/terminal_compat.sh
```

Verified across git history: the file produced *exactly these three SC1091 info
lines and nothing else* at every commit that touched it — `68d803caf` (t822_2,
the "offending" commit), `e12e508bc` (t822_7), and `fcd270363` (t822_8). There
was never a genuine `SC2xxx` warning. SC1091 is the standard, benign artifact of
shellcheck being unable to follow `source` targets when a script is linted in
isolation, and it fires on **many** sibling scripts (e.g. `aitask_setup.sh`,
`aitask_diffviewer.sh`, `aitask_brainstorm_init.sh`, `aitask_gate_lint.sh`).
`shellcheck` exits non-zero (1) on info-level findings, so the naive
"reports no warnings" check failed.

**Established convention:** Several scripts already silence exactly this on their
`source` lines with `# shellcheck disable=SC1091`
(`aitask_usage_update.sh`, `aitask_add_model.sh`, `aitask_verified_update.sh`,
`aitask_migrate_archives.sh`), and `lib/tmux_exec.sh:36` uses the combined form
`# shellcheck source=terminal_compat.sh disable=SC1091`. The fix is to apply that
same combined directive to this file.

## Change

**File:** `.aitask-scripts/aitask_applink.sh` (lines 5, 7, 9)

Append `disable=SC1091` to each existing `# shellcheck source=` directive,
matching the `lib/tmux_exec.sh` pattern exactly:

```bash
# shellcheck source=lib/aitask_path.sh disable=SC1091
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh disable=SC1091
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"
```

No executable code changes; comment-directive only. Zero behavior change.

## Scope boundary

Only `aitask_applink.sh` is touched (the file named by the verification item).
The identical benign SC1091 on other sibling scripts is a broader lint-hygiene
gap, not part of this task — noted for a possible follow-up, not fixed here.

## Verification

1. `shellcheck .aitask-scripts/aitask_applink.sh` → **no output, exit 0**
   (previously 3× SC1091 info, exit 1).
2. `bash -n .aitask-scripts/aitask_applink.sh` → syntax still valid.
3. `bash tests/test_applink_smoke.sh` → still passes (guards against any
   accidental regression to the sourcing block).

## Step 9 (Post-Implementation)

Standard archival via `./.aitask-scripts/aitask_archive.sh 1002`. This task is
risk-gated (`risk_evaluated`); the Step 9 orchestrator records that gate. No
worktree to clean up (current-branch profile).

## Risk

### Code-health risk: low
- None identified. Change is three comment-only shellcheck directives following
  an established in-repo convention (`lib/tmux_exec.sh`); no executable code,
  no behavior change, blast radius = one file.

### Goal-achievement risk: low
- None identified. The directive directly and demonstrably satisfies the
  verification item ("reports no warnings"); verification is objective
  (`shellcheck` exit 0 / empty output).

## Final Implementation Notes

- **Actual work done:** Appended `disable=SC1091` to the three existing
  `# shellcheck source=` directives (lines 5/7/9) in
  `.aitask-scripts/aitask_applink.sh`, matching the combined-directive pattern
  in `lib/tmux_exec.sh:36`. Comment-only; no executable code changed.
- **Deviations from plan:** None. Applied exactly as planned.
- **Issues encountered:** The task narrative pointed at "an offending change
  from t822_2", but diagnosis showed no such regression — the file only ever
  produced the benign, universal `SC1091` info diagnostics (verified identical
  at commits 68d803caf, e12e508bc, fcd270363). The scope decision (fix the
  file's directives rather than hunt a non-existent code bug) was made explicit
  in the approved plan's Context section.
- **Key decisions:** Used the in-repo `# shellcheck source=… disable=SC1091`
  convention over a repo-wide `.shellcheckrc` (which would suppress SC1091
  globally / surface lib-file warnings) to keep blast radius to one file.
  Broader observation (not a defect): the same benign SC1091 fires on many
  sibling scripts (`aitask_setup.sh`, `aitask_diffviewer.sh`,
  `aitask_brainstorm_init.sh`, `aitask_gate_lint.sh`, …), so the aggregate
  lint preset `shellcheck .aitask-scripts/aitask_*.sh` is still noisy — a
  possible lint-hygiene follow-up, out of scope for this task.
- **Verification results:** `shellcheck .aitask-scripts/aitask_applink.sh` →
  no output, exit 0 (was 3× SC1091, exit 1); `bash -n` → valid;
  `bash tests/test_applink_smoke.sh` → 2/2 passed.
- **Upstream defects identified:** None
