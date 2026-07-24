---
priority: medium
effort: high
depends: [t1210_2]
issue_type: feature
status: Implementing
labels: [claudeskills, codeagent, task-planning]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
created_at: 2026-07-22 16:16
updated_at: 2026-07-24 11:06
---

## Context

**T3** of the Implementation Trails decomposition (RFC §14 in
`aidocs/implementation_trail_design.md`; parent t1210). The user-facing
`/aitask-trail` skill: create + refresh flows, read-only analysis, one
confirmed artifact write. RFC §3 (journeys J1–J6), §7 (analysis steps 3–6),
§8.3 (targeted refresh) are the spec.

## Key files to create/modify

- `.claude/skills/aitask-trail/` (new) — Claude Code source of truth
  (stub + `.md.j2` per the profile-aware pattern).
- Codeagent operation registration for `trail` — **including `.defaults`
  entries in BOTH seed and live `codeagent_config.json`** (omitting them
  silently falls back to the heavy default model).
- Helper whitelist coverage for `aitask_trail_gather.sh` and the
  `ait artifact` calls the skill issues.

## Reference files for patterns

- `aidocs/framework/skill_authoring_conventions.md` +
  `aidocs/framework/stub-skill-pattern.md` — MANDATORY reading before editing
  anything under `.claude/skills/`; regenerate goldens in the same commit.
- `aidocs/implementation_trail_design.md` §3 invocation matrix (PINNED arg
  surface: bare invocation, `<task_id>`, `--topics <r1>,<r2>`,
  `--refresh <handle>`, `--show <handle>`), §5 (create/update CLI calls with
  explicit `--handle art:trail-<slug>`; parse the `HANDLE:` line), §8.3
  (stale-base re-read guard before write).
- `.aitask-scripts/aitask_artifact.sh` — the only artifact write path; the
  skill never touches manifests/blobs directly.
- Cross-agent porting: source of truth is Claude Code; suggest separate
  follow-up tasks for other agent trees per CLAUDE.md (do not port here).

## Implementation plan

1. Skill flow (create): resolve scope/owner (explicit owner question for
   multi-topic/ad-hoc — J4), run gatherer snapshot, agent analysis per RFC §7
   (classification, waves, narrative fields all required — the trail must
   never be a bare ranked list), render full proposal, AskUserQuestion
   confirm, then single `ait artifact create ... --kind implementation_trail
   --handle art:trail-<slug>`; handle collision → re-prompt slug.
2. Skill flow (refresh): load current version (`ait artifact get`), run
   `drift`, targeted re-analysis of drifted waves/entries only, diff-style
   summary, confirm, re-read manifest current (stale-base guard), then
   `ait artifact update`.
3. Scope expansion mid-analysis is propose-and-confirm, never silent (RFC §7
   step 3). No task metadata mutations anywhere in the skill.
4. Latency rule: no I/O before the first AskUserQuestion beyond what the
   opening question needs; auto-detect scope from a free-text argument when
   given.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` clean; goldens regenerated in the
  same commit.
- Dry-run test for the `trail` codeagent operation resolving the configured
  default model (construction-spy style, per the t1162_2 pattern).
- End-to-end smoke on a throwaway task: create → `ait artifact ls <task>`
  shows the handle; refresh after a member status change produces v2
  (`ait artifact versions`).
