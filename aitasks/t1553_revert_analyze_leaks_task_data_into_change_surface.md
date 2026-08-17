---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [backend]
gates: [risk_evaluated]
anchor: 1538
followup_kind: upstream_defect
created_at: 2026-08-17 18:48
updated_at: 2026-08-17 18:48
---

`aitask_revert_analyze.sh` reports task-metadata edits as part of a task's **code**
change surface, because its commit lookup searches `git log --all` — which in this
repo spans the separate `aitask-data` branch, whose `ait:`-prefixed commits carry
the same `(tNN)` / `(tNN_M)` tag.

Surfaced while designing t1538 (see
`aidocs/framework/manual_verification_staleness.md`), which needs a trustworthy
"files this task changed" answer.

## Reproduction (verified)

```
$ ./.aitask-scripts/aitask_revert_analyze.sh --task-files 1223_4
FILE|.aitask-scripts/lib/agent_launch_utils.py|12|2
FILE|.aitask-scripts/lib/agent_model_picker.py|9|21
FILE|.aitask-scripts/lib/config_utils.py|343|34
FILE|.aitask-scripts/lib/cross_repo_settings.py|428|0
FILE|.aitask-scripts/settings/settings_app.py|26|20
FILE|aitasks/t1223/t1223_5_settings_tab_and_push_action.md|18|0   <-- task metadata
FILE|aitasks/t1223/t1223_6_syncer_scope_documentation.md|13|2     <-- task metadata
FILE|tests/test_cross_repo_settings.py|826|0
```

The two `aitasks/` entries are frontmatter/description edits committed to the
`aitask-data` branch, not code the task changed.

A related symptom on the same root cause: a commit reachable only from
`aitask-data` is **not an ancestor of HEAD**, so any consumer that treats a
returned commit as a point in the code history can compute a nonsense range. Live
case: for t1362 the origin set includes `749f9e597`
(`ait: Amend contract D — drop the seed resolution tier (t1223_4)`), unreachable
from HEAD; `git rev-list 749f9e597..HEAD` is the **entire** 2199-commit history.

## Where

- `.aitask-scripts/aitask_revert_analyze.sh:132` — `git log --all --format="%H" --fixed-strings --grep="(t${sid})"`
- `.aitask-scripts/aitask_revert_analyze.sh:207` — same pattern with `%H|%as|%s`

## Precedent — the sibling helper already answers this correctly

`.aitask-scripts/aitask_change_surface.sh` excludes `aitasks/**`, `aiplans/**` and
`.aitask-data/**` via its `EXCLUDES` (pinned against
`lib/gate_ledger.py::_DIGEST_EXCLUDES` by `tests/test_change_surface.sh`). So the
framework already has a settled answer for "what counts as a task's code change
surface" — these two helpers currently disagree about the same question.

## Suggested fix

Decide and document the intended semantics, then make them consistent:

1. **Filter task-data paths** out of `--task-files` / `--task-areas` output, reusing
   the `EXCLUDES` set rather than a second literal list (one canonical site).
2. **Restrict commit discovery to HEAD-reachable commits** (e.g. drop `--all`, or
   filter with `git merge-base --is-ancestor <c> HEAD`), so a returned commit is
   always a usable point in the code history.

Consider whether `--task-commits` should still *list* the administrative commits
(useful for a full revert) while `--task-files` reports only code — if so, make that
split explicit in the `--help` text and the output contract rather than implicit.

## Verification

- `--task-files 1223_4` no longer lists `aitasks/**` paths.
- A task whose only commits are on `aitask-data` yields an empty/clearly-empty
  result rather than unreachable SHAs.
- Existing behaviour for ordinary code tasks is unchanged (regression-check a
  multi-child parent such as `--task-files 623`, which currently returns 24 files).
- Check the other consumers of these subcommands before changing the contract:
  `grep -rn "task-files\|task-commits" .aitask-scripts/ .claude/skills/`.
