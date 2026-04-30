---
Task: t719_6_architecture_evaluation.md
Parent Task: aitasks/t719_monitor_tmux_control_mode_refactor.md
Sibling Tasks: aitasks/t719/t719_1_*.md, aitasks/t719/t719_2_*.md, aitasks/t719/t719_3_*.md, aitasks/t719/t719_4_*.md, aitasks/t719/t719_5_*.md
Archived Sibling Plans: aiplans/archived/p719/p719_*_*.md
Worktree: aiwork/t719_6_architecture_evaluation
Branch: aitask/t719_6_architecture_evaluation
Base branch: main
---

# Plan — t719_6: Architecture evaluation

## Goal

With `_1`–`_5` archived, take stock of real numbers and real user feel,
write up an evaluation in `aidocs/python_tui_performance.md`, and file
1–3 follow-up tasks if any improvement direction is justified by the data.
**No code changes** in this child.

## Files to modify

- `aidocs/python_tui_performance.md` — append a new section "Phase 1
  outcomes & next directions".

## Files to create (conditional, 1–3)

- `aitasks/t<new>_<slug>.md` per recommended follow-up direction (filed
  via `aitask_create.sh --batch --commit`, NOT as children of t719).

## Step 1 — Gather inputs

```bash
# Re-run benchmark at three pane counts:
for N in 5 10 20; do
    python3 aidocs/benchmarks/bench_monitor_refresh.py --panes "$N" --iterations 50 \
        | tee /tmp/t719_6_bench_${N}.txt
done

# Read archived plans for actual outcomes:
ls aiplans/archived/p719/
for f in aiplans/archived/p719/p719_*.md; do
    echo "=== $f ==="
    awk '/^## Final Implementation Notes/,/^## /{print}' "$f"
done

# Read the manual-verification result from t719_5 (look in the archived
# task file's body and any structured result transcript).
cat aitasks/archived/t719/t719_5_*.md
```

## Step 2 — Draft the doc section

Append to `aidocs/python_tui_performance.md`:

```markdown
## Phase 1 outcomes & next directions

### Benchmark numbers

| Mode        | N=5 median (ms) | N=5 p95 | N=10 median | N=10 p95 | N=20 median | N=20 p95 | Forks/tick |
|-------------|-----------------|---------|-------------|----------|-------------|----------|------------|
| subprocess  | …               | …       | …           | …        | …           | …        | …          |
| control     | …               | …       | …           | …        | …           | …        | 0          |
| pipe-pane*  | …               | …       | …           | …        | …           | …        | 0          |

\* pipe-pane row included only if `t719_4` Phase 4b shipped.

### Did the ≥5× target hit?

… concrete answer, with conditions …

### Qualitative feel (from t719_5 manual verification)

- What felt better.
- What didn't change.
- Any regressions and how they were resolved.

### Re-evaluation of the single-client serialization choice

The parent plan deliberately accepted serialization through one
control client (FIFO `deque[Future]` + `asyncio.Lock`). With real numbers
at N=20:

- Is the linear-scaling ceiling visible in the benchmark?
- Did manual verification surface any user-visible latency tied to
  serialization?
- If pipe-pane shipped: serialization is no longer on the hot path —
  what scenarios still depend on it?

### Follow-up directions

For each direction we recommend pursuing:

1. **\<title\>** (filed as t\<N\>) — one-paragraph hypothesis. Expected
   payoff: \<rough order\>. Complexity: \<low/medium/high\>.
   Recommendation: pursue / defer / skip.
```

## Step 3 — File follow-up tasks (1–3, conditional)

For each direction the doc recommends pursuing, run:

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
    --name "<slug>" \
    --priority medium \
    --effort <low|medium|high> \
    --type performance \
    --labels "performance,monitor,tui" \
    --desc-file - <<'EOF'
## Context
Follow-up to t719 architecture evaluation
(`aidocs/python_tui_performance.md` § "Phase 1 outcomes & next directions").

## Hypothesis
<paragraph from the doc>

## Approach
<rough sketch — detailed planning happens at pick time>

## Verification
<how we'll know it worked>
EOF
```

Then update the doc section to reference each newly-created task ID.

## Step 4 — Commit

```bash
git add aidocs/python_tui_performance.md
git commit -m "documentation: t719 Phase 1 outcomes and follow-up directions (t719_6)"
```

The new follow-up task files were already committed by `aitask_create.sh`
under the `aitask-data` branch.

## Verification

- `cd website && hugo build --gc --minify` exits 0 — the doc addition
  doesn't break the website build.
- Each new follow-up task file shows up in `./ait ls` and parses cleanly
  (`aitask_ls.sh` does not warn).
- The doc's recommended-direction count exactly matches the number of new
  follow-up task files. No orphaned references in either direction.
- `git diff --stat` shows: only `aidocs/python_tui_performance.md` plus
  any new `aitasks/t<new>_*.md` files. No edits to monitor source code.

## Step 9 — Post-Implementation

Standard archival per `task-workflow/SKILL.md` Step 9. With `_6` Done
and the parent's `children_to_implement` empty, parent t719 archives
automatically — the archive script handles parent rollup.

## Notes

- **No code changes.** If during evaluation we find an actual bug (not a
  performance gap), file a separate `bug` task; do not fix in `_6`.
- **Trust archived commits.** Don't re-run `_1`–`_5`'s test suites
  beyond what the benchmark already exercises.
