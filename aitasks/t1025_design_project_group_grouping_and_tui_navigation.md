---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [tui_switcher, stats_ui, tui, tmux]
children_to_implement: [t1025_4, t1025_5]
created_at: 2026-06-17 23:28
updated_at: 2026-06-19 15:13
boardidx: 10
---

## Goal

Introduce a grouping layer over registered repos so that, when a user has many
registered repos belonging to several distinct logical products, TUI project
navigation stays manageable. Rework the TUI project list to show **grouped
connected repos** under an umbrella, plus a separate navigation axis for jumping
to any repo with an active tmux session — including repos belonging to a
different umbrella than the one currently selected.

This is a **design-heavy feature**: it should likely be brainstormed/planned
before implementation (competing data-model options, a keybinding redesign that
touches a documented convention, and a terminology rollout across docs).

## Terminology (decided)

The umbrella term is **`project-group`** (snake_case `project_group` in config
keys; `--project-group` as a CLI flag form). Rationale captured during
exploration:

- Composes with the existing, load-bearing meaning where `project` = one
  registered repo. `project-group` = "a group of projects/repos" reads
  unambiguously and does not overload `project`.
- No collision: `umbrella` is already used in the brainstorm / module-
  decomposition domain; the bare word `group` appears only in brainstorm
  `GROUP_OPERATIONS`. `project-group` is unused everywhere.
- Self-explanatory, which matters because docs already say "project" pervasively.

Reject single-word coinages (`fleet`, `workspace`, `constellation`) unless a
reviewer makes a strong case — they require readers to learn a new term in docs
that are already "project"-dense.

## Current state (from exploration)

**Flat registry, no grouping anywhere.**
- `~/.config/aitasks/projects.yaml` entries carry only `name`, `path`,
  `git_remote`, `last_opened` (parsed by `_parse_registry_records` in
  `.aitask-scripts/lib/agent_launch_utils.py:294-367`). No `group` / `parent` /
  `umbrella` / `related` field exists in schema, resolver, or `ait projects`
  verbs (`.aitask-scripts/aitask_projects.sh`).
- Per-repo identity lives in `aitasks/metadata/project_config.yaml`
  (`project.name`, `project.git_remote`); seed at `seed/project_config.yaml`.
- Cross-repo coordination today is **task-level only** (`xdeprepo` / `xdeps`
  frontmatter, pairwise) — never project-level grouping.

**TUI navigation is one flat left/right ring.**
- TUI switcher binds `left`/`right` to `_cycle_session`
  (`.aitask-scripts/lib/tui_switcher.py:849-875`); stats TUI does the same
  (`.aitask-scripts/stats/stats_app.py:487-513`). This is the documented
  left/right convention (`aidocs/framework/tui_conventions.md:156-189`).
- The list is built by `discover_aitasks_sessions(include_registered=True)`
  (`.aitask-scripts/lib/agent_launch_utils.py:435-510`), which merges TWO
  sources into one undifferentiated sequence:
  - **Live tmux sessions** (`is_live=True`) — pane-cwd walk-up to a
    `project_config.yaml` marker, on the dedicated `-L ait` socket.
  - **Registered-but-inactive repos** (`is_live=False`) — synthesized from the
    registry.
- `AitasksSession` (`agent_launch_utils.py:97-119`) already carries
  `is_live` / `is_stale`, so the "active repos" axis needs **no new tmux
  machinery** — only a different filter/grouping over the existing list.
- One tmux session per project; exact-match `=<session>` targeting
  (`aidocs/framework/tui_conventions.md:212-235`).

## Design questions to resolve (brainstorm/plan)

1. **Where does the grouping live?** Competing options, each with different
   blast radius — evaluate trade-offs (esp. "what if someone edits one repo's
   config unaware of the group?"):
   - (a) New field in each repo's `aitasks/metadata/project_config.yaml`
     (each repo declares its `project_group`). Distributed; git-tracked per repo.
   - (b) New top-level construct in the per-user `~/.config/aitasks/projects.yaml`
     (a `project_groups:` map of group-name -> [member project names]).
     Centralized, per-user, not shared.
   - (c) Both: repo declares membership, registry caches/derives the grouping.
   Decide single source of truth; avoid duplicating the membership list across
   files without a guard (derive-don't-duplicate).
2. **Two-axis TUI navigation.** Today left/right = one flat ring. Proposed:
   - Left/right cycles repos **within the selected project-group** (the
     grouped/connected set).
   - A separate control (e.g. up/down, or a modifier, or a dedicated key) jumps
     across **all repos with an active tmux session**, regardless of group — so
     a user working on several project-groups in parallel can immediately reach
     any live repo. Define the exact keybindings; respect/extend the documented
     convention rather than silently breaking it.
   - Decide presentation: how the grouped list renders (group headers? a
     two-level list?) and how "active but out-of-group" repos are surfaced.
3. **Scope of TUIs affected.** At minimum the TUI switcher and stats TUI (both
   cycle sessions today). Confirm whether monitor/minimonitor session bars and
   the `_switcher_selected_session` overrides
   (`monitor/monitor_app.py:885-899`, `minimonitor/minimonitor_app.py:761-777`)
   need group-awareness.
4. **`ait projects` CLI surface.** Likely a `project-group`-aware verb/flag
   (e.g. `ait projects group add/list`, or `--project-group` on existing verbs).
   Keep consistent with the existing flat-registry verbs and the registry-reader
   parity contract (single reader authority in `agent_launch_utils.py`, byte-
   parity bash awk reader pinned by `tests/test_registry_reader_parity.sh`).
5. **Terminology rollout.** Decide where `project-group` is introduced in docs
   (`aidocs/framework/cross_repo_references.md`, `tui_conventions.md`, website
   workflows pages) without churning the immovable `project`-named surfaces
   (`ait projects`, `project_config.yaml`, `projects.yaml`, `--project`,
   `AITASKS_PROJECT_*`, `xdeprepo`). Per docs conventions, use invented generic
   example product/repo names, never the author's real repos.

## Acceptance criteria (to refine during planning)

- A `project-group` concept exists with a single, documented source of truth for
  group membership, plus a maintainer guard against drift if any list is
  derived/cached.
- The TUI switcher (and stats TUI, and any other in-scope session-cycling TUI)
  navigates repos grouped by their `project-group`, AND offers a distinct,
  documented control to jump to any repo with a live tmux session across groups.
- `ait projects` exposes group management consistent with existing verbs;
  registry-reader parity tests still pass.
- `aidocs/framework/tui_conventions.md` documents the new keybinding axes;
  cross-repo docs introduce the `project-group` term using generic example names.
- Tests cover: registry/config parsing of group membership; the grouped-vs-active
  list derivation (including a repo that is live but outside the selected group);
  and the registry-reader parity contract remains green.

## Notes

- Skill/command source-of-truth changes (if any) start in the Claude Code
  versions; suggest follow-ups for Codex/OpenCode only if agent-specific surfaces
  are touched.
- `diffviewer` stays out of user-facing TUI lists.
