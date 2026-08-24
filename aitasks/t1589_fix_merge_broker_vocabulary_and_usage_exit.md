---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts]
gates: [risk_evaluated]
anchor: 1560
followup_kind: upstream_defect
created_at: 2026-08-24 22:24
updated_at: 2026-08-24 22:24
---

## Origin

Spawned from t1560_2 during Step 8b review. t1560_2 wired the Step 9 merge
broker into the shared workflow and had to render a branch for every verdict the
broker declares, which is what surfaced both defects. Editing the broker was a
non-goal there (it is **t1560_1**'s surface), so they were recorded for
coordination instead.

## Upstream defect

- `.aitask-scripts/aitask_merge_task.sh:499` — `LOCK_UNAVAILABLE` is declared in
  `_VERDICTS_BEGIN` but `cmd_begin` (110-217) never emits it; only
  `cmd_force_release` does (490, 492). The rendered `begin / LOCK_UNAVAILABLE`
  branch is therefore unreachable, and any coverage test sourcing the vocabulary
  is forced to require a branch for a verdict the verb cannot produce.
- `.aitask-scripts/aitask_merge_task.sh:116` — a flag given without its value
  (`begin --wait-secs` with nothing after it) makes `shift 2` fail under
  `set -euo pipefail`, exiting **1** — which the script header documents as
  "infrastructure failure only (never a verdict)" — instead of the **2** the same
  header specifies for usage errors. The `--expect` flag of `force-release`
  (line 446) has the same shape.

## Diagnostic context

The vocabulary is exported deliberately: the header at
`aitask_merge_task.sh:16-17` says "Run `--list-verdicts` for the full vocabulary
- t1560_2's rendered Step 9 must define a branch for every one", and t1560_1's
plan asked for the export precisely so the coverage test could assert
mechanically rather than by hand transcription.

`tests/test_merge_broker_rendered_verdicts.sh` does exactly that: it parses
`--list-verdicts` and requires one verb-qualified disposition row per token. So
the declaration is load-bearing — a token declared for a verb that cannot emit it
forces a permanently dead branch into the rendered procedure, and the test cannot
distinguish that from a genuine gap.

The exit-status defect matters for the same consumer: the rendered procedure's
"Output contract" section tells the agent that exit 1 means infrastructure
failure with nothing on stdout, and exit 2 means usage error. A caller that
mistypes a flag currently gets the "infrastructure failure" signal and is told to
stop and diagnose, when the real problem is its own command line.

## Suggested fix

For the first: either drop `LOCK_UNAVAILABLE` from `_VERDICTS_BEGIN` (if `begin`
genuinely cannot hit an unavailable lock), or add the emission path that makes it
reachable. Whichever is chosen, `tests/test_merge_broker_rendered_verdicts.sh`
will require the matching row to be added or removed in
`.claude/skills/task-workflow/merge-broker.md` in the same change — the test is
the coupling.

For the second: validate that the flag has a value before `shift 2` (e.g.
`[[ $# -ge 2 ]] || usage_err "--wait-secs needs a value"`), at both call sites.
