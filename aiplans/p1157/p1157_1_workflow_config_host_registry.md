---
Task: t1157_1_workflow_config_host_registry.md
Parent Task: aitasks/t1157_chatlink_multi_workflow_remote_explore.md
Sibling Tasks: aitasks/t1157/t1157_2_*.md … t1157_9_*.md
Archived Sibling Plans: aiplans/archived/p1157/p1157_*_*.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t1157_1 — Workflow configuration and host registry

## Changes

1. Add Textual-free workflow definitions in `chatlink/config.py`. A checked-in
   project config uses `workflows:` entries with `id`, `type`, `trigger`,
   `enabled`, authorization lists, and `active_budget_s`, `synthesis_budget_s`,
   and `retention_s`. Parse current singleton keys as one implicit
   `bug_intake` workflow so legacy installations keep their current effective
   configuration.
2. Add a per-machine host registry in `chatlink/paths.py` at the existing
   per-user configuration root. It stores enabled logical project names and
   Discord connection metadata; the token remains a separate 0600 file. Use
   `aitask_project_resolve.sh`/the project registry for paths, never a raw
   sibling path in project config.
3. Aggregate enabled project configs into a `ChatlinkHostConfig`. Reject
   duplicate project-local workflow ids, duplicate message-trigger refs across
   the host, stale/missing projects, and invalid budget partitions. Allow one
   Discord connection across many guild refs. A legacy token is only a
   read-only fallback with an explicit migration warning.
4. Add a global host state/lock path and structured aggregate preflight rows.
   Keep `config.py`, `paths.py`, and `preflight.py` importable without Textual
   or Discord SDK imports.
5. Update the seed config/install merge behavior and tests without dropping
   unknown keys or exposing secrets.

## Verification

- Add legacy, versioned, malformed, duplicate-trigger, multi-project, stale
  project, and token-permission fixtures.
- Run `bash tests/test_chatlink_config.sh` and
  `bash tests/test_chatlink_preflight.sh`.

## Step 9 reference

Commit code separately from this plan, record final compatibility decisions,
then continue with t1157_2.
