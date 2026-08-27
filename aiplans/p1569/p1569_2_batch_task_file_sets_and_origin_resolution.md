---
Task: t1569_2_batch_task_file_sets_and_origin_resolution.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_1_*.md, aitasks/t1569/t1569_3_*.md, aitasks/t1569/t1569_4_*.md, aitasks/t1569/t1569_5_*.md, aitasks/t1569/t1569_6_*.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_*_*.md
Base branch: main
Output branch: main
---

# t1569_2 — Batch task→file-set derivation, history index, origin resolution

Parallel with t1569_1 (disjoint files).

## Step 1 — Batch mode on `aitask_revert_analyze.sh`

Add a subcommand alongside `--task-files` (which **stays** — it is the oracle).

One pass, all history, all refs:

```bash
git log --all --format='C|%H|%ct|%s' --name-only
```

Bucket by the task id in the commit subject. Measured on this repo: 0.72 s for
the raw stream, ~1.0 s including bucketing, producing 9680 `(task_id, path)`
pairs across 2261 commits. Compare with 0.53 s **per call** for `--task-files`.

Emit three products:

```
TASKFILES:<task_id>|<path>
COMMIT:<path>|<sha>|<committed_at>|<task_ids csv>
TRACKED:<path>
STATUS:<task_id>|<FILES|NO_FILES|UNKNOWN_HISTORY>
```

- `TRACKED:` comes from one `git ls-files`.
- **`%ct` is not optional.** t1569_5's premise-drift needs commit timestamps; if
  they are missing it must re-shell git per path and the 115x win is lost. This
  is the single most likely mechanical rework in the tree — carry them now.

### Matching semantics — must equal `--task-files` exactly

`--task-files` uses `git log --all --fixed-strings --grep="(t<id>)"` per id, with
`build_search_ids()` (L113-128) expanding a parent into itself plus its children.
The batch form builds the raw `id → paths` map once and aggregates
`parent = own ∪ children` at query time. Verified equivalent for t1626, t1555 (a
parent whose work landed only under child ids) and t1275 — but see Step 4 for the
real oracle.

Watch: a subject carrying two ids (`(t100, t101)`), reverts, and merge commits.
Whatever `--task-files` does with them, the batch form must do identically.

## Step 2 — `UNKNOWN_HISTORY`

`cmd_task_files()` (L324-356) currently warns `No commits found for task <id>` on
**stderr** and returns 0 with **empty stdout**. So an absent map entry is
byte-indistinguishable from "this task touched no files" — a false no-conflict.

Live incidence on this repo:

- 7 of the 86 `exact`-quality follow-ups resolve to an origin with an empty set;
- 41 of 260 candidates have an empty origin-derived set;
- all 4 non-candidate `Implementing` tasks have zero reachable commits;
- t1206's *topic root* has an empty set.

So `STATUS:` is mandatory and three-valued:

| value | meaning |
|---|---|
| `FILES` | id matched; paths follow |
| `NO_FILES` | id matched, and its commits genuinely touched nothing |
| `UNKNOWN_HISTORY` | the id was never matched at all |

`UNKNOWN_HISTORY` covers: never landed; landed under a differently-labelled
subject; rebased away; reachable only from a ref this scan does not walk.
t1569_3 maps it to `UNCHECKABLE`, never `CLEAR`.

Emit `STATUS:` for **every queried id**, so a consumer never has to infer state
from absence.

## Step 3 — `lib/followup_origin.py`

Pure module. No writes, no git, no subprocess — the contract
`lib/followup_backfill_classify.py` states in its docstring (L8-10).

```python
def resolve(metadata):
    """-> (origins: list[str], quality: str)   quality in exact|topic|unknown"""
```

Precedence, and it is load-bearing:

1. `verifies:` present → `exact`, origins = its ids. This is an exact
   relationship **only** for the verification cases, which is precisely where the
   field is written.
2. else `anchor:` present → `topic`, origins = `[anchor]`. **Never `exact`.**
   `anchor` is a topic-group key that "always points at the root and never
   chains"; `--followup-of` at creation merely *derives* it.
3. else → `unknown`, origins = `[]`.

Two rules that are correctness, not style:

- **Do not consult `followup_kind`.** Classification (is this a follow-up, of
  what category) and origin (which task caused it) are separate concerns.
  `followup_kind` is settled and is not an input here.
- Parse with `task_yaml.parse_frontmatter`, **not**
  `stats_data.parse_frontmatter` — they live side by side and are not
  interchangeable (`stats_data.py:394`). `task_yaml` also normalises task ids to
  `t`-prefixed form and pins `^\d+_\d+$` as a string, so `85_2` does not become
  the integer `852`.

Expose a small CLI for the shell side, following the 5-field tab-separated shape
of `followup_backfill_classify.py`'s `main()`.

## Step 4 — The acceptance oracle

**Byte-equality against `--task-files` for every task id in the corpus** — not a
spot-check. Roughly 2 minutes of CPU, run once, and it is the only real proof
that the batch bucketing reproduces parent/child inclusion, multi-id subjects,
reverts and merges.

```bash
for id in $(all corpus ids); do
  diff <(./.aitask-scripts/aitask_revert_analyze.sh --task-files "$id" | cut -d'|' -f2 | sort -u) \
       <(batch_map_paths_for "$id" | sort -u) || echo "MISMATCH:$id"
done
```

Record the result and the measured timings in the Final Implementation Notes.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests    # read ONLY the last line
python3 -m unittest tests.test_followup_origin -v
shellcheck .aitask-scripts/aitask_revert_analyze.sh
./.aitask-scripts/aitask_revert_analyze.sh --task-files 1555   # unchanged output
```

Piping the runner discards its status — use `set -o pipefail` or check
`${PIPESTATUS[0]}`.

Required tests:

1. Whole-corpus byte-equality oracle (Step 4).
2. `FILES` / `NO_FILES` / `UNKNOWN_HISTORY` each fixture-tested in a synthetic
   repo — including a task whose commits exist **only** under a child id, and a
   task with no commit at all.
3. Resolver truth table with an explicit **`anchor`-is-never-`exact`** negative
   control, and a case carrying **both** `verifies:` and `anchor:` asserting
   `exact` wins.
4. A case proving `followup_kind` is not read (same metadata, different
   `followup_kind`, identical result).
5. A live-corpus coverage assertion on **shape** — exact + topic + unknown equals
   the follow-up total, with no double counting — never on frozen counts. Today's
   values are 86 / 130 / 13 of 229; the raw signal counts (`verifies` 86,
   `anchor` 167) overlap on 37 tasks and must not be summed.
6. Timing regression: the batch mode over the whole corpus stays well under the
   ~115 s the per-call form would take.

Fixture scaffold: `tests/test_change_surface.sh` — note its L36-44 comment about
creating `FIXTURE_ROOT` in the **parent** shell, since `fx="$(new_repo)"` runs in
a subshell and a `CLEANUP_DIRS+=(…)` inside would be lost.
