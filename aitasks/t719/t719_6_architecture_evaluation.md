---
priority: low
effort: low
depends: [t719_5]
issue_type: documentation
status: Ready
labels: [performance, monitor, tui, documentation]
created_at: 2026-04-30 10:33
updated_at: 2026-04-30 10:33
---

## Context

Final child of t719. With `_1`–`_5` archived, take stock of the *real*
benchmark numbers (`t719_2`'s `bench_monitor_refresh.py`), the *real*
qualitative feel from the manual-verification pass (`t719_5`), and the
investigation findings from `t719_4` (whether or not pipe-pane shipped).
Document the outcomes, re-evaluate the design choices made under partial
information (notably the single-client serialization choice — see the
parent plan's "Serialization design note"), and propose 1–3 concrete
follow-up tasks if any improvement direction looks worth pursuing.

**No code changes in this child.** Pure synthesis + documentation + task
creation. Sibling auto-dep on `t719_5` makes this the last child to be
picked.

## Key Files to Modify

- **MODIFY** `aidocs/python_tui_performance.md` — append a new section
  "Phase 1 outcomes & next directions".

## Reference Files for Patterns

- `aiplans/archived/p719/p719_1_*.md` through `p719_5_*.md` —
  "Final Implementation Notes" sections record what each child actually
  did vs. planned. These are the primary input.
- `aidocs/benchmarks/bench_monitor_refresh.py` — re-run on a representative
  session (5, 10, 20 panes) to get fresh numbers for the doc section.
- `aidocs/python_tui_performance.md:131-146` — the existing
  "Recommendations" section sets the framing the new section should chain to.
- `aiplans/p719_monitor_tmux_control_mode_refactor.md` — parent plan,
  particularly the "Serialization design note" — the trade-off baseline
  to evaluate against.

## Implementation Plan

### 1. Gather inputs

```bash
# Re-run benchmark at three pane counts, three modes (subprocess, control,
# pipe-pane if shipped):
for N in 5 10 20; do
    python3 aidocs/benchmarks/bench_monitor_refresh.py --panes "$N" --iterations 50 \
        | tee /tmp/t719_6_bench_${N}.txt
done

# Read the archived plan files:
ls aiplans/archived/p719/
```

### 2. Draft the doc section

Append to `aidocs/python_tui_performance.md` under a new heading
`## Phase 1 outcomes & next directions`. Required content (pulled from
the inputs):

- **Final benchmark numbers table** (median ms, p95 ms, fork count per
  tick) for N ∈ {5, 10, 20}, three modes (subprocess / control / pipe-pane
  if shipped).
- **Did the ≥5× target hit?** Concrete answer with conditions noted.
- **Qualitative feel notes** from `t719_5`'s checklist: what felt better,
  what didn't change, what regressed (if anything).
- **Re-evaluation of the single-client serialization choice.** Read the
  parent plan's "Serialization design note", then answer:
  - Is serialization still the right shape, given the measured numbers
    at N=20?
  - Did the manual-verification pass surface any user-visible latency
    that traces back to serialization?
  - If `t719_4` shipped, does pipe-pane make this question moot?
- **1–3 concrete follow-up directions**, each:
  - Title.
  - One-paragraph hypothesis.
  - Expected payoff (rough order of magnitude).
  - Estimated complexity (low/medium/high).
  - Recommendation (pursue / defer / skip).

  Candidate directions to consider (non-exhaustive — pick those the
  numbers actually justify):
  - Control-client *pool* (2–3 clients, round-robin).
  - Per-pane subscription via `pipe-pane` if not yet shipped.
  - Cache-based "skip capture if pane width/height/pid unchanged"
    heuristic.
  - Folding `display-message` aux calls into the control client.
  - Raising the asyncio buffer further for very wide panes (≥ 8 MiB).
  - Replacing the entire polling loop with `tmux subscribe-event`
    (tmux 3.4+).

### 3. File follow-up tasks

For each follow-up direction recommended in the doc, file a separate
top-level task (NOT a child of t719 — t719 will be archived shortly):

```bash
./.aitask-scripts/aitask_create.sh --batch --commit \
    --name "<slug>" \
    --priority medium \
    --effort <low|medium|high> \
    --type performance \
    --labels "performance,monitor,tui" \
    --desc-file - <<'EOF'
## Context
Follow-up to t719 architecture evaluation (see
aidocs/python_tui_performance.md "Phase 1 outcomes & next directions").

## Hypothesis
<one paragraph from the doc>

## Approach
<rough sketch — leave detailed planning for the implementer>

## Verification
<how we know it worked>
EOF
```

Reference each newly-created task ID back in the doc section so future
readers can navigate to the work in flight.

### 4. Commit

```bash
git add aidocs/python_tui_performance.md
git commit -m "documentation: t719 Phase 1 outcomes and follow-up directions (t719_6)"

# The new follow-up task files were already committed by aitask_create.sh.
```

## Verification Steps

- `aidocs/python_tui_performance.md` builds in `hugo build` (the file is
  surfaced via the website's docs sync). Run from `website/` with
  `hugo build --gc --minify` and confirm exit 0.
- Each newly-created follow-up task file passes `aitask_ls.sh` parsing
  (frontmatter valid, dependencies resolve).
- The doc's recommended-direction count matches the number of follow-up
  task files created (1–3, no orphans).
- `git diff --stat` shows changes only in `aidocs/python_tui_performance.md`
  and any new `aitasks/t<new>_*.md` files. No edits to monitor code.

## Out of Bounds

- No code changes in this child.
- No re-running of `_1`–`_5`'s test suites; trust their archival commits.
- No predictions about future tmux upstream changes.
- Do NOT silently roll the follow-ups into `t719`'s closure — they must
  be standalone tasks the user can prioritize independently.

## Step 9 — Post-Implementation

Standard archival per `task-workflow/SKILL.md` Step 9. With `_6` done
and the parent's `children_to_implement` empty, the parent t719 also
archives automatically (the archive script handles this).
