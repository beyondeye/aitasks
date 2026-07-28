---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [reporting]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-28 18:05
updated_at: 2026-07-28 18:05
---

## Origin

Risk-mitigation ("after") follow-up for t1235, created at Step 8d after implementation landed.

## Risk addressed

Code-health — two `parse_frontmatter` functions co-located in `lib/`. From t1235's plan:

> After the move `lib/` holds two different functions named `parse_frontmatter`
> (`stats_data`'s lightweight string-map parser and `task_yaml`'s YAML-backed
> one) side by side in one flat, bare-name module directory. They are not
> interchangeable, and nothing prevents a future consumer importing the wrong one ·
> severity: medium

## Goal

Give the base layer one unambiguous frontmatter parser, or two names that cannot
be confused for each other.

`.aitask-scripts/lib/` is a flat, bare-name module directory — consumers write
`from task_yaml import parse_frontmatter` or `from stats_data import
parse_frontmatter` and nothing at the call site says which semantics they got:

- `lib/task_yaml.py:parse_frontmatter` — the YAML-backed parser. Returns typed
  values (lists, ints, bools) and is the canonical task-frontmatter reader.
- `lib/stats_data.py:parse_frontmatter` — a lightweight line scanner. Every value
  stays a **string**; used by the stats aggregation path. t1235 added a docstring
  note flagging the collision, which is a mitigation of last resort, not a fix.

Decide between (and implement) one of:

1. **Rename** the stats one to something scope-honest (e.g.
   `parse_frontmatter_strings` / `scan_frontmatter_flat`), keeping both.
2. **Consolidate** onto `task_yaml.parse_frontmatter` if the stats path can
   tolerate typed values and the parse cost over the whole archive.

Option 2 needs measuring before it is chosen: `collect_stats` parses every
archived task file, so swapping a line scanner for a YAML parse could be a real
regression in `ait stats` / `ait stats-tui` startup. Benchmark before committing
to it; if the cost is material, take option 1.

## Key files

- `.aitask-scripts/lib/stats_data.py` — `parse_frontmatter` (~line 249) and its
  callers inside the same module
- `.aitask-scripts/lib/task_yaml.py` — the YAML-backed parser
- `.aitask-scripts/aitask_stats.py` — re-exports `parse_frontmatter` in its
  `__all__`; `tests/test_stats_data.sh` asserts that re-export by name
- `tests/test_stats_data.sh` — asserts `aitask_stats` exposes `parse_frontmatter`

## Verification

- `bash tests/test_stats_data.sh`
- `bash tests/test_stats_verified_rankings.sh`
- `bash tests/run_all_python_tests.sh`
- `./ait stats` output unchanged (diff the text report before/after)
- If option 2 is taken: time `ait stats` before and after over the real archive
  and record the delta in the plan
