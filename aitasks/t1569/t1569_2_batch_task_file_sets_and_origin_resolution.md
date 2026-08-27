---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [scheduling, planning, backlog]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1569
created_at: 2026-08-27 11:27
updated_at: 2026-08-27 23:44
---

Batch task->file-set derivation, a commit index, and pure origin resolution.
Slice 2 of 6 for t1569 — read the parent task and
`aiplans/p1569_background_work_roadmap_trail_for_followup_backlog.md` first.

**Parallel with t1569_1** (disjoint files). Deliberately no sibling dependency.

## Context

t1569 needs, for ~260 backlog candidates, "which files did this task's origin
touch". The canonical seam already exists and must be **reused, not forked**
(CLAUDE.md "Reusable Helpers": prefer extending the existing helper with a flag).

Measured on this repo:

| approach | cost |
|---|---|
| `aitask_revert_analyze.sh --task-files <id>`, per task | **0.53 s/call** -> ~115 s for 216 follow-ups |
| one `git log --all --format=... --name-only` pass + bucketing | **~1.0 s** for the entire map (9680 pairs) |

**115x.** Byte-identical output was verified for t1626, t1555 (a parent whose work
landed under child ids) and t1275.

## Scope

### 1. Batch mode on `aitask_revert_analyze.sh`

**One** `git log --all --format='...%H...%ct...%s' --name-only` pass emitting:

- `task_id -> paths`, children-inclusive, with the same `(tNN)` matching
  semantics as `--task-files`;
- `path -> [(sha, committed_at, task_ids)]` — the commit index;
- the tracked-path set from one `git ls-files`.

**Carry `%ct` from the start.** t1569_5's premise-drift needs commit timestamps.
If this ships without them, t1569_5 must re-shell git per path and the 115x win
is lost — the most likely mechanical rework in the whole tree.

### 2. `UNKNOWN_HISTORY` — a first-class third state, not an empty set

Today a task id with no recognised reachable commit produces **nothing**:
`cmd_task_files()` warns `No commits found for task <id>` on stderr and returns 0
with empty stdout. An absent map entry is byte-indistinguishable from "this task
touched no files" — a **false no-conflict**. Live on this repo:

- **7 of the 86** `exact`-quality follow-ups resolve to an origin with an empty
  file set;
- **41 of 260** candidates have an empty origin-derived set;
- **all 4** non-candidate `Implementing` tasks have zero reachable commits;
- among the 37 dual-signal tasks, t1206's *topic root* has an empty file set.

Emit exactly one of, per queried id:

- `FILES` — matched, with paths;
- `NO_FILES` — id matched, and the commits genuinely touched nothing;
- `UNKNOWN_HISTORY` — the id was never matched at all (never landed, landed under
  a differently labelled subject, rebased away, or reachable only from a ref this
  scan does not walk).

t1569_3 maps `UNKNOWN_HISTORY` to `UNCHECKABLE`, never `CLEAR`.

### 3. Pure origin resolver — `lib/followup_origin.py`

Mirror `lib/followup_backfill_classify.py`'s contract: **pure, no writes, no git,
no subprocess**.

```
resolve(metadata) -> (origins, quality)   # quality in exact | topic | unknown
  verifies:  -> exact     (the verification cases only)
  anchor:    -> topic     (a topic ROOT, never an exact origin)
  neither    -> unknown
```

Rules that are load-bearing, not stylistic:

- It must **never** report `anchor` as `exact`. `anchor` is a topic-group key
  that "always points at the root and never chains" — a different thing from a
  direct causal origin. `--followup-of` at creation only *derives* `anchor`.
- It must **not** consult `followup_kind`. Classification (is this a follow-up,
  of what category) and origin (which task caused it) are separate concerns;
  `followup_kind` is already settled and is not an input here.
- Parse frontmatter with `lib/task_yaml.parse_frontmatter` — **not**
  `stats_data.parse_frontmatter` (they live side by side and are not
  interchangeable; see `stats_data.py:394`).

Live coverage over the 229 follow-ups, **mutually exclusive**:
`exact` **86**, `topic` **130**, `unknown` **13**. (Raw signals are `verifies` 86
and `anchor` 167 with a 37-task overlap — do not quote 167 as the topic count.)

## Key files to modify

- `.aitask-scripts/aitask_revert_analyze.sh` — add the batch mode alongside
  `--task-files` (which stays as the oracle). Relevant existing functions:
  `build_search_ids()` L113-128, `collect_commit_hashes()` L135-146,
  `cmd_task_files()` L324-356.
- New `.aitask-scripts/lib/followup_origin.py`.
- New `tests/test_followup_origin.py`.
- New/extended bash test for the batch mode.

## Reference files for patterns

- `.aitask-scripts/lib/followup_backfill_classify.py` — the pure-module contract
  and its 5-field tab-separated CLI protocol.
- `.aitask-scripts/lib/task_yaml.py` L134-161 — `parse_frontmatter`, and the
  `^\d+_\d+$`-stays-a-string loader (PyYAML would turn `85_2` into `852`).
- `tests/test_change_surface.sh` — the canonical synthetic-git-repo bash fixture
  scaffold (note its comment at L36-44 about creating `FIXTURE_ROOT` in the
  parent shell, not a subshell).
- `tests/test_followup_backfill_classify.py` — `sys.path.insert` import
  bootstrap for a `lib/` module.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — read **only** the last
  line; piping discards the status (use `set -o pipefail` or `${PIPESTATUS[0]}`).
- `python3 -m unittest tests.test_followup_origin -v`
- `shellcheck .aitask-scripts/aitask_revert_analyze.sh`

Required acceptance:

1. **Whole-corpus byte-equality oracle.** For **every** task id in the corpus,
   the batch mode's paths must equal `--task-files`' paths exactly — not a
   three-id spot-check. ~2 minutes of CPU, run once, and it is the only real
   proof. Cover multi-task subjects (`(t100, t101)`), reverts and merges.
2. `FILES` / `NO_FILES` / `UNKNOWN_HISTORY` each fixture-tested, including a task
   whose commits exist only under a child id, and a task with no commit at all.
3. Resolver truth table with an explicit **`anchor`-is-never-`exact` negative
   control**.
4. A live-corpus coverage assertion on *shape* (exact + topic + unknown == total
   follow-ups; no double counting), never on frozen counts.
5. Record the measured perf and coverage numbers in the Final Implementation
   Notes.
