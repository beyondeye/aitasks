---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: []
gates: [risk_evaluated]
anchor: 635
created_at: 2026-08-03 11:23
updated_at: 2026-08-03 11:23
---

## Origin

Risk-mitigation ("after") follow-up for t1370, created at Step 8d after
implementation landed.

## Risk addressed

From t1370's plan `## Risk` → `### Code-health risk: medium`:

> The change makes a previously-inert exit status **load-bearing on the hot
> path** (every pick), and exploration found two latent `set -euo pipefail`
> aborts inside the very function whose status we start trusting. A third,
> unfound one would turn into a warning on every pick. · severity: medium

`addresses`: code-health — a third, unfound `set -euo pipefail` abort.

## Goal

Audit `.aitask-scripts/` for command-substitution assignments whose pipeline
contains a `grep` (or any command that exits non-zero on "no match") and which
therefore abort the whole script under `set -euo pipefail` when the match set is
empty. Fix them, and add a guard test.

### Why this matters

The shape is:

```bash
x=$(cmd | grep 'pattern' | awk '{print $1}')
[[ -z "$x" ]] && return 0        # <-- never reached
```

With `set -euo pipefail`, an empty match makes `grep` exit 1, `pipefail`
propagates it to the assignment, and `set -e` kills the shell **before** the
emptiness guard on the next line. The guard that was written specifically to
handle "nothing found" is dead code, and the empty case — usually the *ordinary*
case — becomes a silent non-zero exit.

t1370 found **two** instances in `cleanup_locks()` alone, plus a third already
confirmed in the same file. The prevalence justifies a sweep rather than
one-at-a-time fixes.

### Known instances

- `.aitask-scripts/aitask_lock.sh:362` — `list_locks()`. Already filed
  separately as **t1378** (found during t1370's Step 8b). If t1378 has landed by
  the time this task runs, verify and move on; do not double-fix.
- (fixed in t1370) `cleanup_locks()` lock-file listing and task-id extraction.

## Suggested approach

1. Enumerate candidates. Start broad, then filter:
   ```bash
   grep -rnE '^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=\$\(.*\|.*grep' .aitask-scripts/
   ```
   Also catch the `$( ... | grep ... )` form inside `local x=` declarations, and
   `grep -c` / `grep -o` variants. Note that `local x=$(...)` **masks** the
   failure (the `local` builtin's own status wins), so those are latent rather
   than active — record them but rank them lower.
2. For each hit, determine whether the enclosing script sets `pipefail` **and**
   whether the call site keeps `set -e` live. Two things suppress it:
   - the assignment is inside an `if`/`while` condition or a `&&`/`||` list;
   - the enclosing **function** is invoked in a condition context (e.g.
     `f || rc=$?`), which disables `set -e` for the entire function body. t1370
     hit this exact trap and reverted to a bare call — see its plan's
     "Deviations from plan".
3. Fix structurally, not with `|| true`: prefer `awk '$N ~ /re/ {print $N}'`
   (exits 0 on no match) or bash parameter expansion, both of which remove the
   failure class instead of masking one instance.
4. Add a guard test. A source-scan guard is acceptable here **only** if it is
   paired with per-case behavioral tests — a regex over source cannot tell a
   live abort from a suppressed one, and a passing scan would over-claim.
5. Prove each new test discriminates: restore the `grep` form and confirm the
   suite exits 1 on the expected assertion, not merely somewhere.

## Verification

- Every fixed site has a test exercising the **empty-match** case, asserting
  exit 0 and the expected "nothing found" output.
- Each such test fails when its fix is reverted (negative control naming the
  expected assertion).
- `shellcheck .aitask-scripts/aitask_*.sh` shows no new findings against the
  pre-change baseline.
