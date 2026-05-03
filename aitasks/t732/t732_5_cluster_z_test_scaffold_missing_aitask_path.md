---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, bash_scripts, test_infrastructure]
created_at: 2026-05-03 16:31
updated_at: 2026-05-03 16:31
---

## Context

Child 5 of t732. **Cluster Z is the highest-leverage child**: 4 of the 13 failing tests share a single root cause discovered during t732 planning that was NOT in the original cluster split.

## Single root cause across 4 failing tests

`lib/aitask_path.sh` was added by **t695_3** (commit `709380a5`, Apr 28) and is now sourced unconditionally early in `./ait` (line 7) and in many helper scripts (line ~15). 55 test files build a fake `.aitask-scripts/lib/` and copy only the libs they think they need; **none of them copy `aitask_path.sh`**. The 4 tests below happen to invoke `./ait` or scripts that source `aitask_path.sh` — they crash. The other 51 currently pass only because they happen to dodge those code paths (a latent time-bomb).

## Failing tests (verified on `main` @ `74c59788` today)

All four fail with the same first-line error pattern:

### tests/test_task_push.sh (13 passed / 5 failed / 18 total)
```
./ait: line 7: /tmp/ait_push_test_XXXXXX/local/.aitask-scripts/lib/aitask_path.sh: No such file or directory
```

### tests/test_brainstorm_cli.sh (silent exit after Test 1)
```
.aitask-scripts/aitask_brainstorm_init.sh: line 15: /tmp/tmp.XXXXXX/.aitask-scripts/lib/aitask_path.sh: No such file or directory
```

### tests/test_explain_context.sh (silent exit)
```
./.aitask-scripts/aitask_explain_context.sh: line 11: /tmp/explain_ctx_XXXXXX/repo/.aitask-scripts/lib/aitask_path.sh: No such file or directory
```

### tests/test_migrate_archives.sh (silent exit after Test 11)
```
./ait: line 7: /tmp/tmp.XXXXXX/.aitask-scripts/lib/aitask_path.sh: No such file or directory
```

## Root cause hypothesis

CONFIRMED — not a hypothesis. All four tests scaffold a fake `.aitask-scripts/lib/` and miss copying `aitask_path.sh`. To inventory, run:

```bash
for t in tests/test_*.sh; do
  if grep -q ".aitask-scripts/lib/" "$t"; then
    if ! grep -q "aitask_path" "$t"; then
      echo "$t"
    fi
  fi
done
```

That returns 55 tests today. The 4 failing ones are the subset that also invoke `./ait` or a script that sources `aitask_path.sh` (`aitask_brainstorm_init.sh`, `aitask_explain_context.sh`, `aitask_migrate_archives.sh`, `./ait git ...`).

## Two implementation strategies

### Strategy 1 — Mechanical patch (4 tests only)

Add one `cp` line to each of the 4 failing tests, in their scaffold/setup helper:

```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh" "$repo_dir/.aitask-scripts/lib/"
```

Pros: minimal diff, no refactor risk.
Cons: leaves 51 other tests with the same time bomb. The next script that learns to source `aitask_path.sh` will surface the same bug class again.

### Strategy 2 — Extract `tests/lib/test_scaffold.sh` helper (RECOMMENDED)

Per CLAUDE.md "Single source of truth for cross-script constants": consolidate the fake-`.aitask-scripts/lib/` bootstrap into a helper sourced by every test that needs it.

Sketch:
```bash
# tests/lib/test_scaffold.sh
setup_fake_aitask_repo() {
  local repo_dir="$1"
  mkdir -p "$repo_dir/.aitask-scripts/lib"
  # Always copy the "system" libs that ./ait and most helpers source unconditionally:
  cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh" "$repo_dir/.aitask-scripts/lib/"
  cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$repo_dir/.aitask-scripts/lib/"
  # Caller adds their script-specific files on top
}
```

Then port the 55 affected tests onto the helper. Tests would become shorter and time-bomb-free.

Pros: inoculates 51 currently-passing tests against the next regression of this class; reduces duplication; aligns with CLAUDE.md guidance.
Cons: larger diff (touches 55 files); mechanical port risk if some tests have idiosyncratic scaffolding the helper doesn't cover.

## Recommendation

Take **Strategy 2**, but stage it: write the helper and convert the 4 failing tests first (proving the helper works). Convert the remaining 51 in a second commit (idempotent — they should still pass). If the second commit is large, split into t732_5_1 (extract helper, fix the 4) and t732_5_2 (port remaining 51).

**Do NOT mark the 51-port as "out of scope follow-up"** — per the CLAUDE.md "Plan split: in-scope children, not deferred follow-ups" feedback memory, complete the helper convergence as part of t732_5 (or split into siblings as above).

## Key files to modify

- `tests/lib/test_scaffold.sh` (new) — the helper
- The 4 failing tests, then the other 51 (port to the helper)
- The list of 55 tests is reproducible via the inventory grep above

## Verification

- All 4 originally-failing tests pass: `bash tests/test_task_push.sh && bash tests/test_brainstorm_cli.sh && bash tests/test_explain_context.sh && bash tests/test_migrate_archives.sh`.
- All 51 currently-passing tests in the affected set still pass after the helper port (run them all):
  ```bash
  for t in $(grep -l ".aitask-scripts/lib/" tests/test_*.sh); do
    bash "$t" >/dev/null 2>&1 || echo "REGRESSION: $t"
  done
  ```
- No new fail prints from the loop above.
