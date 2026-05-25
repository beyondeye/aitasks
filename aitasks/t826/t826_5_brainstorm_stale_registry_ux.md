---
priority: medium
effort: medium
depends: [t826_4]
issue_type: feature
status: Ready
labels: [brainstorming, cross_repo, tui_switcher, aitask_projects]
created_at: 2026-05-25 19:05
updated_at: 2026-05-25 19:05
---

## Context

Spun off during t826_2 (TUI switcher surfaces inactive projects).
t826_2 silently excludes STALE registry entries (path missing the
`aitasks/metadata/project_config.yaml` marker) from the switcher's
Session row, matching how the rest of the resolver already filters
them. That's the safe minimum, but it leaves the user blind: a
project that was moved, renamed, or deleted on disk just disappears
from the switcher with no signal, and the registry entry sits stale
forever.

This brainstorm task scopes the UX for surfacing and resolving
stale registry entries. **No implementation in this round — design
first.**

## Goals

1. **Detection trigger** — where does the staleness check fire?
   Every switcher render (cheap, but adds latency)? On a background
   timer? Only on-demand via `ait projects doctor`? Some hybrid
   (e.g., cache freshness with a TTL)?

2. **Surface in switcher** — should STALE entries appear in the
   Session: row with a visual marker (e.g., `?` or red)? Or hide
   them from the switcher entirely and surface only in
   `ait projects list`? Trade-off: visibility vs. clutter for users
   who've registered many projects.

3. **`ait projects` verbs to add** — minimum probably:
   - `ait projects prune` — delete every STALE entry, with
     `--dry-run` and per-entry confirm.
   - `ait projects update <name> <new_path>` — repoint a known
     entry whose path moved.
   - `ait projects remove <name>` — drop an entry explicitly
     (carried over from t826_1's out-of-scope list).
   - `ait projects doctor` (optional) — interactive scan that
     offers prune/update/keep for each STALE entry.

4. **Auto-clone from `git_remote`** — for entries with a recorded
   `git_remote`, should `doctor` (or a `--clone` flag) offer to
   re-clone the project into the original path? Useful for cloud
   agents that lose `/home/<user>/Work/...` between runs. Risk:
   nudges users to re-create stale paths instead of repointing.

5. **Switcher behavior when a selected entry turns out to be
   STALE between `ait projects list` and a `tmux new-session` call**
   — race condition (path was valid at switcher mount, deleted by
   the time the user hits Enter). Should the bootstrap helper
   propagate a clear error to the switcher overlay
   (e.g. `BOOTSTRAP_FAILED:stale_path`) and the switcher should
   offer prune/repoint inline?

## Open Questions

- Is the staleness check expensive enough to need caching, or is a
  bare `os.path.isfile` per registry entry on every switcher render
  fine? (Probably the latter — registries will have <20 entries
  in practice.)
- Should `last_opened` factor in? E.g., entries not opened in N
  months auto-prune candidates?
- Where does the cloud-agent / per-machine path-divergence problem
  fit? (Same registry on two PCs with different home paths.) Is
  that this task's concern or a separate per-machine override
  brainstorm?

## Out of Scope

- Implementation of any of the above — this round produces a
  design decision + a list of follow-up child implementation
  tasks under t826 (or a new parent if the scope grows).
- Cross-repo *merge* coordination, CI/pipelines (carried over
  from parent brainstorm t826).

## References

- Parent brainstorm: `aitasks/t826_brainstorm_cross_repo_project_references.md`
- Sibling t826_1 archive plan:
  `aiplans/archived/p826/p826_1_registry_resolver_projects_cmd_and_create_flag.md`
  (the LIVE / OK / STALE status semantics it ships).
- Sibling t826_2 (this brainstorm's origin):
  `aitasks/t826/t826_2_tui_switcher_show_inactive_projects.md`
  ("Out of Scope" section explains why staleness UX is deferred).
- Authoring-side aidoc: `aidocs/cross_repo_references.md` (registry
  schema + resolver semantics).
