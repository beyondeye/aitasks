---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [testing, bash_scripts, test_infrastructure, refactor]
created_at: 2026-05-03 18:53
updated_at: 2026-05-03 18:53
boardidx: 20
---

## Context

Spawned as a follow-up from t732_5 (Cluster Z fix in the t732 triage). t732_5 took the minimal Strategy 1 path: add `cp aitask_path.sh` (and later `cp python_resolve.sh`) directly to the 4 originally-failing tests. **51 other tests scaffold a fake `.aitask-scripts/lib/` without copying these libs**, and remain at risk of the same crash class the moment they invoke `./ait` or a helper that learns to source another lib that's already in tree.

This task converges the test-scaffold pattern behind a single helper (`tests/lib/test_scaffold.sh` with `setup_fake_aitask_repo()`).

## The time-bomb pattern

Several `lib/*.sh` files are sourced unconditionally by `./ait` and most helper scripts:
- `lib/aitask_path.sh` (added by t695_3, Apr 28) — sourced on `./ait` line 7 and many helpers
- `lib/python_resolve.sh` (expanded by t695_2/4, t728, t731) — sourced by `aitask_brainstorm_init.sh` line 17, `aitask_explain_context.sh` line 13, and others
- `lib/terminal_compat.sh` — already widely copied by tests

When a test scaffolds a fake `.aitask-scripts/lib/` but skips a system lib, the next time that test invokes a script that sources the missing lib, it crashes with `No such file or directory`. The 4 t732_5 failures were the first crashes; t732 surfaced the pattern.

## Inventory (today)

```bash
# 60 tests scaffold a fake .aitask-scripts/lib/
grep -l ".aitask-scripts/lib/" tests/test_*.sh | wc -l

# 51 of those still don't copy aitask_path.sh (time-bomb candidates)
files=$(grep -l ".aitask-scripts/lib/" tests/test_*.sh); miss=0
for t in $files; do grep -q "aitask_path" "$t" || miss=$((miss+1)); done
echo "$miss"

# Same query for python_resolve.sh
files=$(grep -l ".aitask-scripts/lib/" tests/test_*.sh); miss=0
for t in $files; do grep -q "python_resolve" "$t" || miss=$((miss+1)); done
echo "$miss"
```

## Proposed approach

### Step 1 — Write the helper

Create `tests/lib/test_scaffold.sh` (alongside the existing `tests/lib/venv_python.sh`):

```bash
#!/usr/bin/env bash
# test_scaffold.sh - Bootstrap a minimal fake .aitask-scripts/ tree.
# Always copies the "system" libs that ./ait and most helpers source unconditionally.
# Caller adds script-specific files on top.

[[ -n "${_AIT_TEST_SCAFFOLD_LOADED:-}" ]] && return
_AIT_TEST_SCAFFOLD_LOADED=1

# REQUIRES: PROJECT_DIR (path to the real aitasks repo root) is set in caller.

setup_fake_aitask_repo() {
  local repo_dir="$1"
  mkdir -p "$repo_dir/.aitask-scripts/lib"
  cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh"   "$repo_dir/.aitask-scripts/lib/"
  cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$repo_dir/.aitask-scripts/lib/"
  cp "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"  "$repo_dir/.aitask-scripts/lib/"
}
```

The helper handles ONLY the always-needed baseline. Tests still copy their domain-specific libs (`task_utils.sh`, `archive_utils.sh`, `agentcrew_utils.sh`, etc.) on top — those vary per test.

### Step 2 — Port the 51 affected tests

Each affected test currently does roughly:

```bash
mkdir -p .aitask-scripts/lib
cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/<task-specific>.sh" .aitask-scripts/lib/
```

Becomes:

```bash
source "$PROJECT_DIR/tests/lib/test_scaffold.sh"
setup_fake_aitask_repo "$PWD"   # or "$repo_dir", whichever the test uses
cp "$PROJECT_DIR/.aitask-scripts/lib/<task-specific>.sh" .aitask-scripts/lib/
```

Stage the port: convert in batches of ~10 tests, run the regression loop after each batch.

### Step 3 — Regression check

After porting, every test that currently passes must still pass:

```bash
PASS=0; FAIL=0; FAILED=()
for t in tests/test_*.sh; do
  if bash "$t" >/dev/null 2>&1; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    FAILED+=("$t")
  fi
done
echo "PASS: $PASS  FAIL: $FAIL"
[[ $FAIL -gt 0 ]] && printf '  %s\n' "${FAILED[@]}"
```

If any port introduces a regression, the helper is missing a baseline lib for that test's scenario — extend it (or, for that one test, add the lib via a `cp` line on top of `setup_fake_aitask_repo`).

### Step 4 — Drift guardrail

Add a CLAUDE.md entry under "Adding a New Helper Script" or a new "Test Authoring" section: any new `lib/*.sh` that becomes a `./ait`-dispatcher source-on-startup dependency should be added to `setup_fake_aitask_repo()` in the same PR.

## Why follow-up, not folded into t732

t732 is a triage parent for "make 13 originally-failing tests pass on `main`". The 51-test convergence is preventive infrastructure that does not address those failures. Per CLAUDE.md "Don't add features, refactor, or introduce abstractions beyond what the task requires", this work is properly scoped as its own task with its own approval gate.

## Verification

- `tests/lib/test_scaffold.sh` exists with `setup_fake_aitask_repo()`.
- All 60 scaffolding tests use the helper (or are deliberately exempted with a comment explaining why).
- Whole-suite regression check (driver loop above) reports 0 failures.
- CLAUDE.md guardrail entry is in place.

## Out of scope

- Porting tests that don't scaffold `.aitask-scripts/lib/` (the helper is for fake-repo scaffolders only).
- Refactoring the helper to discover system libs automatically (a list-driven explicit copy is more debuggable than reflection).
