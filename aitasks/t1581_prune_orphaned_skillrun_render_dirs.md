---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [skills, execution_profiles, python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1560
followup_kind: upstream_defect
created_at: 2026-08-24 12:30
updated_at: 2026-08-24 12:41
---

## Origin

Spawned from t1578 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_command_screen.py:93-108` — `_prune_stale_skillrun_overrides()`
  prunes only `aitasks/metadata/profiles/local/_skillrun_*.yaml`. The **rendered skill
  directories** those ephemeral profiles produce
  (`.claude/skills/<skill>-_skillrun_<unique>-/`, plus the `.agents/` and `.opencode/`
  equivalents) are never pruned, so orphaned render trees accumulate indefinitely.

## Reproduction

Observed on this workspace on 2026-08-24:

```
2026-05-25  .claude/skills/aitask-pick-_skillrun_416236_1779701547729-
2026-05-25  .claude/skills/task-workflow-_skillrun_416236_1779701547729-
```

Both are **3 months old**. Their originating profile
(`profiles/local/_skillrun_416236_1779701547729.yaml`) was pruned long ago — the YAML
cleanup works correctly and no `_skillrun_*.yaml` remains on disk. The asymmetry is the
defect: the profile is ephemeral, the render tree it produced is permanent.

## Why it matters

- **Stale skill text lingers.** The orphaned copies were rendered from a much older
  canonical source. `task-workflow-_skillrun_416236_1779701547729-/plan-externalization.md`
  still predates the entire `<branch-flags>` section and refers to "Gemini CLI" — wording
  removed from the canonical file since.
- **Invisible to git.** Rendered dirs are gitignored (`.gitignore:52-54`), so they never
  appear in `git status` and no review surface catches the accumulation.
- **They pollute repo-wide scans.** During t1578 a recursive
  `grep -rl … .claude .agents .opencode` propagation check returned an unstable count
  precisely because of these dirs, forcing the verification to be rebuilt on
  `git ls-files`. Any future audit that greps the skill trees hits the same trap.
- **Unbounded growth.** Nothing caps the count; every interrupted skillrun can leave
  another full skill closure behind.

## Suggested fix

Extend the cleanup so the render dirs share the profile's lifecycle. Options, roughly in
order of preference:

1. Have `_prune_stale_skillrun_overrides()` (or a sibling helper) also remove
   `<agent_skill_root>/*-_skillrun_<unique>-/` directories, driven by the same age
   threshold (`_SKILLRUN_PRUNE_AGE_SECONDS`). Reuse `agent_skills_paths.sh` /
   its Python equivalent to enumerate the three agent roots rather than hardcoding them.
2. Prune any `*-_skillrun_*-` dir whose originating profile YAML no longer exists — a
   stronger invariant than age, since the profile is what makes the render meaningful.

Note that `aitask_skill_rerender.sh` deliberately **skips** these dirs (its per-profile
walk only matches `-<profile_name>-` for real profiles), so re-rendering will never
refresh or remove them — cleanup has to be explicit.

Add a regression test that seeds an orphaned `*-_skillrun_*-` dir plus an aged profile
YAML and asserts both are gone after the prune.
