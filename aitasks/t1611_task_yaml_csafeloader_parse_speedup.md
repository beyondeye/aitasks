---
priority: medium
effort: low
depends: [1527]
issue_type: performance
status: Ready
labels: [performance, task_yaml, board, aitask_ls]
created_at: 2026-08-25 18:24
updated_at: 2026-08-25 18:24
---

Route `task_yaml.parse_frontmatter` through libyaml's `CSafeLoader` when it is
available, falling back to the pure-Python `SafeLoader` when it is not.

## Why

`task_yaml.parse_frontmatter` is the single frontmatter parser for the board,
the minimonitor, the merge tool, the codebrowser, the diffviewer and the
report/trail gatherers. It uses PyYAML's **pure-Python** `SafeLoader`, which
costs ~0.55 ms per task file.

t1527 made that cost visible. Its `deps-blocking-scan` resolves every local
`depends:` entry through one decision core, which means actually reading the
tasks — 566 `parse_frontmatter` calls on this repo. Measured with `cProfile`:
**91 % of the scan's 0.360 s is PyYAML**, and it is the whole of t1527's
measured **+0.324 s (+6.7 %)** regression on `ait ls`:

| phase | cost |
|---|---|
| `deps-blocking-scan` subprocess | 0.360 s |
| bash row lookups | 0.104 s |
| removed: old batch + `grep -lE` | −0.065 s |
| removed: ~250 per-dep `grep` forks | ~−0.080 s |
| net | **+0.32 s** |

A ~5x parse win would take the scan to ~0.1 s and put `ait ls` back at or below
its pre-t1527 cost — and would speed up every other surface that reads task
files, including board refresh.

## The check already done

`CSafeLoader` **does** honour `_TaskSafeLoader`'s custom implicit resolver — the
one that keeps `423_6` a string instead of letting YAML 1.1's underscore
digit-separator coerce it to the integer `4236`. Verified during t1527:

```
doc = "priority: high\ndepends: [423_6, 12, t9_1]\nstatus: Done\n"
CSafeLoader   -> {'priority': 'high', 'depends': ['423_6', 12, 't9_1'], 'status': 'Done'}
pure-python   -> {'priority': 'high', 'depends': ['423_6', 12, 't9_1'], 'status': 'Done'}
```

That is the single most dangerous difference and it is clear. It is **not**
sufficient on its own — see Verification.

## Scope

1. `_TaskSafeLoader` derives from `yaml.CSafeLoader` when `hasattr(yaml,
   "CSafeLoader")`, else from `yaml.SafeLoader`. The implicit-resolver
   installation is unchanged and must be applied to whichever base is chosen.
2. libyaml is **not** guaranteed present (it is a compiled extension). The
   fallback is not optional, and both paths must be exercised by the tests —
   a fallback that is never run is not a fallback.
3. Nothing else changes: no call site, no output shape, no serializer.
   `_FlowListDumper` is out of scope (writing is not the hot path).

## Verification

- **Whole-corpus equality, the decisive test:** parse **every** task file in
  `aitasks/` (active and archived-loose) under both loaders and assert the
  resulting metadata dicts are equal. A resolver regression here would
  mis-parse every child task id repo-wide and nothing would raise, so the
  test must compare values, not merely that parsing succeeded.
- Both loader paths must be covered: force the fallback (patch
  `hasattr(yaml, "CSafeLoader")` / the selected base) and re-run the same
  corpus comparison, so the no-libyaml machine is tested on a libyaml machine.
- A negative control: mutate the implicit-resolver installation and confirm the
  corpus test fails, naming `423_6`-style ids.
- Error-shape check: a malformed frontmatter file must still raise the same
  exception class the callers already catch (the board's `gate_registry` /
  `Task` construction paths swallow by class).
- Re-measure `ait ls` A/B against HEAD, interleaved, and record the median in
  the plan — the point of this task is a number.
- `bash tests/run_all_python_tests.sh` stays green.

## Related

- **t1527** — introduced the regression this repays, and its plan
  (`aiplans/archived/p1527_*.md` once archived) records the full profile and
  why the change was kept out of that task: `task_yaml` is a base-layer module
  and deserves its own review and its own negative control.
