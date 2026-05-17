---
Task: t777_20_profile_modification_invalidation.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_20 — Profile-modification eager invalidation

## Scope

Belt-and-suspenders on top of t777_2's lazy "skip-if-fresh" mtime check. When a profile YAML is saved through any framework TUI (settings, AgentCommandScreen edit-modal via t777_17), eagerly delete all `<agent>/skills/*-<profile>/` directories so the next render is forced fresh.

Lazy mtime check (already in t777_2) covers the "user edits profile YAML by hand outside the framework" case. Eager invalidation (this child) covers the "user edits through a framework TUI" case and surfaces stale-render bugs immediately.

## Step Order

1. **Write `aitask_skill_invalidate.sh`** — args `<profile_name>`; iterate 4 agents; `find <root> -maxdepth 1 -type d -name "*-<profile>" -delete` (or rm -rf in a loop with logging). Idempotent. Emits `INVALIDATED:<count> directories for profile '<name>'`.
2. **Add `invalidate` subcommand** under `skill)` case in `./ait` (existing case from t777_2 + t777_4).
3. **Hook into `ProfileEditScreen`** (extracted in t777_16): after the save callback writes the profile YAML, shell out to `./.aitask-scripts/aitask_skill_invalidate.sh <profile_name>` via `subprocess.run([...], check=False)`. Log failures to TUI notification area but don't error the save.
4. **5-touchpoint whitelist** for `aitask_skill_invalidate.sh`.

## Critical Files

- `.aitask-scripts/aitask_skill_invalidate.sh` (new)
- `./ait` (modify — extend `skill)` case)
- `.aitask-scripts/lib/profile_editor.py` (modify — from t777_16; add invalidation hook in save callback)
- 5 whitelist files

## Pitfalls

- **Per-run overrides don't invalidate** — `AgentCommandScreen` per-run edits (t777_17) write to `/tmp/ait-run-override-<pid>.yaml`, not the project profile YAML. These are one-shot and MUST NOT trigger invalidation (that would defeat the cache for other concurrent users of the unchanged base profile).
- **Concurrent agent sessions** — if an agent is mid-execution reading a per-profile SKILL.md when invalidation deletes the directory, the agent may fail. Document the limitation in CLAUDE.md (also flagged in parent plan): "do not modify profiles via TUI while agent sessions are actively running skills."
- **Glob safety** — `*-<profile>` would match any hyphenated authoring directory whose tail matches the profile name. Most profile names are unique enough (`default`, `fast`, `remote`, user-defined). Verify before delete (use a sentinel-file check inside the dir if needed: only delete if `.generated` marker is present — coordinate with t777_3's gitignore strategy).

## Verification

See task description Verification Steps. End-to-end: edit a profile in `ait settings`, save, observe deletion + next wrapper invocation re-renders.

## Notes for parent plan

This child is INSERTED into the parent plan AFTER initial approval (user-requested addition during planning). Update `aiplans/p777_modular_pick_skill.md` "Children" section to add t777_20 and update t777_19 (retrospective) to depend on it.
