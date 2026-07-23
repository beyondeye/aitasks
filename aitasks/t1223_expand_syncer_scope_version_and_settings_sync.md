---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [tui, project_groups, ait_settings, auto-update]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1223_1, t1223_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-23 17:09
updated_at: 2026-07-23 18:30
---

## Goal

Expand `ait syncer` from a **git-commit sync** TUI into a general **cross-repo
sync console**. Two new capabilities on top of the existing branch-desync view:

1. **Framework version view + upgrade.** Show the installed aitasks framework
   version of every discovered cross-repo project, and allow upgrading a repo to
   `latest` or a pinned version from the TUI — by spawning a new shell
   (tmux window/pane) that runs `ait upgrade <version>` followed by `ait setup`
   in that repo's root.
2. **Cross-repo settings alignment.** Make it easy to bring a setting to a
   matching value across repos. **v1 scope: the default code agent per operation**
   (`codeagent_config.json` → `.defaults.<operation>`). Other settings are
   explicitly out of scope for v1 but the seam must be built so they can be added.

This is a complex change and is expected to be **split into child tasks** during
planning.

## Current state (verified 2026-07-23, live source)

### Syncer is already cross-repo — build on it, do not reinvent

`t1138` (archived, Done 2026-07-09) already made the syncer multi-repo:

- `.aitask-scripts/syncer/syncer_app.py:119-146` — `discover_syncer_sessions()`
  calls `discover_aitasks_sessions(include_registered=True)`
  (`.aitask-scripts/lib/agent_launch_utils.py:707`), merging live tmux sessions
  with the per-user registry `~/.config/aitasks/projects.yaml`, dropping STALE
  rows and always putting the cwd repo first.
- `syncer_app.py:90-105` `RowSpec` (one row = one `(repo, ref)` pair, opaque
  positional `row_key`); `:107-117` `ActionTarget(root, branch, label)`;
  `:263-311` `resolve_action_target()` resolves the highlighted row to a repo
  root (`root=None` = legacy CWD-relative single-repo mode).
- `syncer_app.py:357` — `self.multi_repo = len(self.sessions) >= 2` gates the
  Project column and multi-repo behavior; single-repo UX is unchanged.
- `syncer_app.py:187-208` `least_recent_fetch_key()` — the round-robin
  "fetch one repo per tick" scheduler that keeps N-repo polling bounded.
- `syncer_app.py:240-260` `coalesce_request()` + `_refresh_gen`/`_refresh_active`
  /`_pending_fetch` — generation-guard + single pending slot so at most one
  worker runs and the latest request wins.

### UI shape — no tabs today

`syncer_app.py:384-401` `compose()` yields exactly: `Header` → one `DataTable`
(`#branches`, columns Project?/Branch/Status/Ahead/Behind/Fetched) →
`VerticalScroll(#detail_scroll)` with a `Static(#detail)` → `Footer`.
Modals are pushed on top (`SyncFailureScreen`, `SyncConflictScreen`,
`AgentCommandScreen`, TUI switcher, shortcuts editor). There is **no
`TabbedContent` in this TUI**; in-repo precedent for tabs exists in
`.aitask-scripts/settings/settings_app.py` and
`.aitask-scripts/brainstorm/brainstorm_app.py` (+ `brainstorm/nav_mixin.py`).

`BINDINGS` (`syncer_app.py:338-348`): `r` refresh, `s` sync (data), `u` pull,
`p` push, `a` agent-resolve (hidden), `f` fetch toggle, `q` quit, plus
`TuiSwitcherMixin.SWITCHER_BINDINGS` (`j`) and
`ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS` (`?`). Row gating via
`check_action` (`:426-430`) + `action_allowed_for_ref` (`:178-184`).

### Version reading — trivial and already path-safe

- `<root>/.aitask-scripts/VERSION` is the **single source of truth** (one-line
  semver; this repo currently `0.28.0`). Read it for any repo root directly.
  A stray root-level `VERSION` is a pre-v0.3.0 legacy that `install.sh:1257-1258`
  deletes on every install.
- `ait --version` (`ait:15-22` `show_version`) resolves `$AIT_DIR` from
  `BASH_SOURCE`, **not** `$PWD`, so `<root>/ait --version` is also safe.
  Note the global shim `packaging/shim/ait:9-16` walks up from `$PWD` and is
  **not** directory-parameterizable.
- "Latest" resolution already exists: `.aitask-scripts/lib/github_release.sh`
  — `github_latest_release_version` (`:36-76`, GitHub REST, honors
  `GH_TOKEN`/`GITHUB_TOKEN`), `github_latest_tag_version` (`:91-99`,
  `git ls-remote --tags` fallback used on 403/429 rate-limit),
  `github_resolve_latest_version` (`:101-123`), `github_ratelimit_reset_minutes`.
- Existing "update available" hints: `ait:120-182` `check_for_updates()` with a
  24h cache at `~/.aitask/update_check` (background-refreshed, and `ait upgrade`
  clears it at `aitask_upgrade.sh:155`); `aitask_setup.sh:1833-1855`
  `check_latest_version()` at end of setup.

### Upgrade / setup — the real friction

- `.aitask-scripts/aitask_upgrade.sh` — `ait upgrade [latest|VERSION]`.
  Version pinning **is** supported (`:83-89` validates `^[0-9]+\.[0-9]+(\.[0-9]+)?$`,
  leading `v` stripped). Fully **non-interactive** (no prompts).
  It downloads the tagged `install.sh` (`:94-105`) and runs
  `AIT_TARGET_VERSION=<v> bash install.sh --force --dir "$AIT_DIR"` (`:152`).
  **There is no `--dir`/target flag** — `$AIT_DIR` is derived from the script's
  own location (`:7-8`). So a cross-repo upgrade must be invoked as
  `<root>/ait upgrade <v>` (or `ait projects exec <name> -- ./ait upgrade <v>`).
- `.aitask-scripts/aitask_setup.sh` — flags: `--with-pypy`, `--with-chat`,
  `--source-only`, `--` (parsed at `:3515-3527`). Also **no `--dir`**; operates
  on `$SCRIPT_DIR/..`. Every one of its ~33 prompts is gated by `[[ -t 0 ]]`, so
  it is fully non-interactive when stdin is not a TTY — but when spawned in a
  fresh tmux shell stdin *is* a TTY, which is exactly what makes the
  "spawn a visible shell" approach right: the user can answer anything it asks.
- Spawn seam already exists and is repo-root-aware:
  `agent_launch_utils.launch_in_tmux(command, TmuxLaunchConfig)` (`:1188`) with
  `TmuxLaunchConfig.cwd` (`:89-95`) passing tmux `-c <cwd>`; plus
  `unique_window_name` (`:1296`), `resolve_pane_id_by_pid` (`:1254`).
  All raw tmux must go through `lib/tmux_exec.py` (see
  `aidocs/framework/tmux_gateway.md`; `tests/test_no_raw_tmux.sh` enforces it).
  The syncer already does a comparable spawn in `_launch_resolution_agent`
  (`syncer_app.py:909-948`) via `lib/agent_command_screen.py:156`.

### Cross-repo settings — no foundation exists yet

- **There is no path-parameterized settings *writer* anywhere in the framework.**
  Read-side exceptions only:
  - `.aitask-scripts/lib/config_utils.py:175-217` `resolve_config_path(..., root=None)`
    (its CLI wrapper `aitask_resolve_config_path.sh:22` hardcodes `REPO_ROOT`).
  - `.aitask-scripts/lib/agent_model_picker.py:44-56` `load_all_models(project_root=None)`.
  - `.aitask-scripts/lib/agent_launch_utils.py:232-251`
    `resolve_agent_string(project_root, operation)` — shells
    `<project_root>/.aitask-scripts/aitask_codeagent.sh resolve <op>` with
    `cwd=project_root` and parses `AGENT_STRING:<value>`. **This is the ready-made
    cross-repo read for v1.**
  - Everything else (`settings_app.ConfigManager` at `settings_app.py:412-541`,
    `config_utils.metadata_dir()/task_dir()` at `:36-50`) is bound to cwd /
    `TASK_DIR`.
- Nearest existing cross-repo mechanism: the manual Export/Import `.aitcfg.json`
  bundle — `settings_app.py:156-160` `EXPORT_CATEGORIES`, `ExportScreen`/
  `ImportScreen`, backed by `config_utils.export_all_configs` /
  `import_all_configs` (`:258-459`). It is file-mediated and two-step, not a live
  A→B write.

### The v1 setting target

`aitasks/metadata/codeagent_config.json` — single top-level `defaults` key, a
flat map `operation -> "<agent>/<model>"`:

```json
{ "defaults": {
    "pick": "claudecode/opus4_8", "explain": "claudecode/sonnet4_6",
    "batch-review": "claudecode/sonnet4_6", "qa": "claudecode/sonnet4_6",
    "raw": "claudecode/sonnet4_6", "explore": "claudecode/opus4_8",
    "shadow": "codex/gpt5_6_terra",
    "brainstorm-explorer": "claudecode/opus4_8",
    "brainstorm-comparator": "claudecode/sonnet4_6",
    "brainstorm-synthesizer": "claudecode/opus4_8",
    "work-report": "claudecode/sonnet4_6" } }
```

Notes: `brainstorm-<type>-launch-mode` keys live in the same map but hold
`headless|interactive`, not agent strings (`settings_app.py:1804-1820`).
Resolution order (`aidocs/framework/model_reference_locations.md:55-68`):
`codeagent_config.local.json` (gitignored user layer) → `codeagent_config.json`
(project, git-tracked) → `seed/codeagent_config.json` → `DEFAULT_AGENT_STRING`
(`lib/agent_string.sh:26`). Layer merge is `config_utils.load_layered_config`
(`:91-121`) + `deep_merge` (`:63-80`); the TUI's per-key write is
`settings_app._handle_agent_pick` (`:2281-2310`) → `ConfigManager.save_codeagent`
(`:485-493`, deletes an emptied local file). Agent-string validation:
`lib/agent_string.sh:48-66` `parse_agent_string` against
`SUPPORTED_AGENTS=(claudecode codex opencode)`; model names are keys into
`models_<agent>.json`, so **a model valid in repo A may not exist in repo B**.

## Indicative work breakdown (refine in planning)

1. **Tabbed shell.** Introduce `TabbedContent` into `syncer_app.compose()`,
   moving the current table+detail into a "Branches" tab. Keep bindings,
   `check_action` gating, refresh workers, and single-repo degradation intact.
   Route any new keys through `ShortcutsMixin` (scope `"syncer"`) so they get
   remapping and the `?` editor for free.
2. **Version tab (read-only first).** One row per discovered repo: project,
   installed version (from `<root>/.aitask-scripts/VERSION`), latest known
   (shared, cached — one network resolution for all rows), up-to-date/behind
   status. Must not multiply network calls by repo count.
3. **Upgrade action.** Key on a version row → choose `latest` or a pinned
   version → spawn a tmux window rooted at that repo running
   `./ait upgrade <v> && ./ait setup` via `launch_in_tmux(TmuxLaunchConfig(cwd=root))`.
   Refresh the row's version afterwards (or on next tick).
4. **Repo-rooted settings read/write seam.** A path-parameterized helper
   (`get`/`set` a named setting in an arbitrary repo root) covering at least the
   `codeagent_config` layers. Must reuse `config_utils.load_layered_config` /
   `deep_merge` / `save_project_config` rather than forking them, and must be
   testable against fixture repo roots with no live state.
5. **Settings tab.** One column per repo × one row per synced setting key
   (v1: `defaults.<operation>`), highlighting divergence, with an action to
   propagate one repo's value to selected others. Validate the target value is
   legal in the destination repo (`models_<agent>.json` membership) before
   writing; refuse rather than write an unusable value.

## Considerations / open questions for planning

- **Blast radius (first-class).** `ait upgrade` rewrites framework files in
  *another* repo and a settings push mutates another repo's tracked config.
  Both need unambiguous target display + explicit confirmation, and the existing
  aggregate/`All projects` semantics from t1138 (no batch fan-out) should be the
  default posture unless deliberately revisited.
- **Project vs local layer for settings pushes.** Writing
  `codeagent_config.json` (git-tracked, team-shared) vs
  `codeagent_config.local.json` (gitignored, personal) is a real semantic
  choice — decide and make it explicit in the UI, don't guess.
- **Version-tab network cost.** Resolve "latest" once per refresh, shared across
  repos, and reuse `~/.aitask/update_check`-style caching rather than hitting the
  API per repo. Respect the existing `f` fetch-off/offline mode.
- **`ait setup` after upgrade.** Confirm whether it is always needed or only on
  a version change; a spawned interactive shell keeps its `[[ -t 0 ]]` prompts
  answerable, which is preferable to silently non-interactive repair.
- **Tab-aware key gating.** `s`/`u`/`p` must not fire from the version or
  settings tab, and new keys must not fire from Branches. Extend `check_action`
  per tab.
- **Adjacent known defect:** `t1219` (settings drops unknown `default_profiles`
  keys on save, `settings_app.py:233-236,2517-2527`) is a warning about
  rebuild-from-widgets writers — the new settings writer must be merge-based, not
  rebuild-based. Do not fold t1219 in; keep it separate.
- Decomposition should be testability-first: the version reader, the "latest"
  resolver adapter, the upgrade-command construction, and the settings get/set
  seam are all pure/headless units that can be unit-tested before any TUI work.

## Tests

- Version reader against fixture repo roots (present / missing / malformed
  `VERSION`), never against cwd.
- Upgrade command + `TmuxLaunchConfig` construction asserted without spawning
  tmux (construction-spy style, mirroring the existing dry-run/target split).
- Settings get/set seam against fixture roots: read layered value, write project
  layer, write local layer, merge preserves unrelated keys (negative control:
  an unknown key present before the write is still there after).
- Rejection path: pushing an agent string whose model is absent from the
  destination repo's `models_<agent>.json` is refused with a distinct reason.
- TUI render-level: tab presence, per-tab `check_action` gating, and single-repo
  (`< 2` repos) regression — layout and behavior unchanged.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-23T15:28:57Z status=pass attempt=1 type=human
