---
Task: t1025_design_project_group_grouping_and_tui_navigation.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: project-group grouping + two-axis TUI navigation (t1025)

## Context

When a user registers many repos in `~/.config/aitasks/projects.yaml` that
belong to several distinct logical products, TUI project navigation degrades:
the TUI switcher and stats TUI cycle **one flat left/right ring** built from
`discover_aitasks_sessions(include_registered=True)` (live tmux sessions +
registered repos, undifferentiated). There is **no grouping layer anywhere** —
the registry is a flat list of `name/path/git_remote/last_opened`, and cross-repo
coordination today is task-level only (`xdeprepo`/`xdeps`).

This task introduces a **`project-group`** (the agreed umbrella term — composes
with the load-bearing, immovable `project`=repo meaning; no collision with
`umbrella`, which is taken in the brainstorm domain) and reworks TUI navigation
into two axes:

- **left/right** browses the **selected group's repos + any active out-of-group
  repo** (so a user juggling several product-groups can still jump to any repo
  with a live tmux session).
- a **dedicated group-cycle key** (`[` / `]`) switches *which* project-group is
  selected.

**Decided design (user):**
- **Membership store:** central per-user registry is the operational source of
  truth, **initialized from each repo's `project_config.yaml` `project_group`
  field when missing** (one-way bootstrap — not a live cache, so no
  cache-coherence guard needed). A **settings-TUI editor** lets the user edit
  per-user group membership directly.
- **Navigation:** dedicated `[` / `]` group-cycle key; left/right = group repos +
  active out-of-group repos.
- **Shape:** split into child tasks (this parent becomes a parent-of-children).

This plan is a **decomposition blueprint**. Child tasks + their individual plans
are created after this plan is approved (plan mode is read-only); risk evaluation
is performed per-child during each child's own planning, as is standard for a
parent-split task.

## Decomposition

Dependency order: **1 → {2, 3} → 4 → 5(manual-verify)**. Children 2/3 depend on
child 1's model + read/write API; child 4 (docs) follows the behavior; child 5
verifies live flows. Testability-first: child 1 extracts the pure
group-derivation function so child 2 consumes a tested headless unit.

---

### Child 1 — Data model, bootstrap, read/write API + `ait projects` group CLI

**Goal:** Add `project_group` as a per-repo concept, store it per-entry in the
registry, bootstrap it from per-repo config when absent, and expose read/write +
a pure derivation function. No TUI changes.

**Key changes:**
- **Per-repo declaration:** add optional `project.project_group` to
  `seed/project_config.yaml` (documented, commented) so a repo can declare its
  default group. This is the *bootstrap seed*, not the operational store.
- **Registry per-entry field:** extend `~/.config/aitasks/projects.yaml` entries
  with an optional `project_group:` field. This is the operational source of
  truth for navigation.
- **Naming contract (resolves serialization concern — High):** a
  `project_group` value MUST be a **slug** matching `^[a-z0-9][a-z0-9_-]*$` (the
  same character class the existing `project.name` already obeys). This sidesteps
  the registry's quoting gap entirely: `build_registry_yaml`
  (`aitask_projects.sh:179-194`) emits **raw unquoted scalars** and reads
  pipe-separated fields with `IFS='|'`, so a value containing `:`, `#`, `|`,
  quotes, or leading whitespace would corrupt the file or misparse. Enforce the
  slug at **every write entry point** (CLI `group set`, settings editor, and the
  bootstrap reader) with a shared validator: reject with a clear error, or
  normalize (lowercase, spaces→`-`, strip illegal chars) and confirm. No
  escaping strategy is introduced — the slug constraint is the contract.
  Pipe-collision is structurally impossible once `|` is rejected.
- **Single-authority reader:** extend `_parse_registry_records()`
  (`.aitask-scripts/lib/agent_launch_utils.py:294-367`) from a 4-field to a
  5-field tuple `(name, path, git_remote, last_opened, project_group)`; update
  `_read_registry_index()`, the `AitasksSession` dataclass
  (`agent_launch_utils.py:96-119`), and `build_registry_yaml`'s pipe record (add
  a 5th `|`-field). **Mirror byte-for-byte** in the bash awk reader
  (`index_lookup_path` in `aitask_project_resolve.sh:150-195`) and
  `list_registry_entries` / `--list-registry` output, and update
  `tests/test_registry_reader_parity.sh` so parity holds. (Derive-don't-duplicate
  via a guard: keep the field list co-located; the parity test is the guard.)
- **Group resolution during discovery (resolves live-session concern — High):**
  add a resolved `project_group: str | None` to `AitasksSession` and populate it
  for **every** session in `discover_aitasks_sessions()` — not just registered
  rows. Today the live branch (`:490-494`) builds sessions from pane-cwd with no
  registry consult, and the registry merge (`:496-507`) skips already-live names,
  so a live repo (registered or not) never gets a group. Fix: resolve each
  session's group in priority order — (1) registry `project_group` for that
  `project_name`, else (2) read the repo's own
  `aitasks/metadata/project_config.yaml` `project.project_group` directly (the
  `project_root` is already in hand), else (3) `None` (ungrouped). This makes
  "default selected group = attached session's group" robust for live,
  registered, and unregistered repos alike. Add a small cached config reader
  alongside `_read_default_session()` (`:392-432`).
- **Bootstrap (init-if-missing):** when a registry entry has no `project_group`,
  read it from that repo's `project_config.yaml` `project.project_group`. Wire
  into `ait projects add` (`aitask_projects.sh:267-306`, alongside the existing
  `project.name` read) and expose a one-shot backfill path (e.g. `ait projects
  group sync`) for already registered repos. Bootstrap writes the resolved value
  into the registry once; thereafter the registry value wins. (Discovery-time
  resolution above is the read-path fallback that does **not** require bootstrap
  to have run.)
- **CLI surface:** add `ait projects group` sub-verbs to `aitask_projects.sh`
  (dispatch table at `:641-685`), consistent with existing verbs:
  `group list` (show groups → member repos), `group set <name> <group>`,
  `group unset <name>`. Registry mutation goes through the existing
  Python-authority writer (no parallel bash writer).
- **Pure derivation unit (testability-first):** add a pure function
  `group_sessions(sessions, selected_group) -> ordered_ring` operating over
  `AitasksSession` objects that **already carry a resolved `project_group`** (per
  the discovery change above), so it is pure and trivially testable. Ring rule:
  `[sessions where project_group == selected_group] + [out-of-group sessions
  where is_live]`. **Stale handling (resolves stale concern):** stale in-group
  rows (`is_stale`) stay in the ring (so the user can see/repair them, preserving
  the existing switcher repair-modal behavior), flagged stale; stale out-of-group
  rows are excluded from the ring (not active, not in group) but still appear in
  group-membership listings (settings editor / `group list`) so they can be
  reassigned or repaired. Also returns the ordered list of known groups for
  `[`/`]` cycling (ungrouped repos collect under a synthetic "(ungrouped)" group
  that is also cyclable). Lives in the model layer so child 2 imports a tested
  function rather than re-deriving.

**Tests:** registry 5-field parse + round-trip (name-only entries still survive);
reader parity (`test_registry_reader_parity.sh`); **slug validator** accepts
`a-z0-9_-`, rejects/normalizes `:`, `#`, `|`, spaces, quotes, leading space, and
uppercase; bootstrap-from-config when registry field absent + registry-wins when
present; **discovery-time group resolution** for a live registered repo, a live
**unregistered** repo (group from its own config), and an ungrouped repo;
`group set/unset/list` CLI (extend `tests/test_projects_cmd.sh`); `group_sessions`
derivation incl. the **live-but-out-of-group** repo, a **stale in-group** repo
(kept) vs **stale out-of-group** (dropped), and the no-groups (all-flat) fallback.

---

### Child 2 — TUI navigation: switcher + stats two-axis browsing

**Goal:** Wire the two-axis model into the TUI switcher and stats TUI using
child 1's `group_sessions` + group list.

**Key changes:**
- **TUI switcher** (`.aitask-scripts/lib/tui_switcher.py`): change `_cycle_session`
  (`:849-875`) to cycle the **derived ring** (selected group's repos + active
  out-of-group repos) instead of the flat `_all_sessions`. Add a selected-group
  state var + `[` / `]` bindings (near `:435-436`) → `action_prev_group` /
  `action_next_group` that re-derive the ring and re-render. Render group context
  (header/label) in the session row. Default selected group = the attached
  session's group.
- **stats TUI** (`.aitask-scripts/stats/stats_app.py`): mirror in `_cycle_session`
  (`:487-513`) and `_build_session_items` (`:317-325`); add `[`/`]` bindings
  alongside the existing left/right (`:153-154`), guarded by pane id like the
  current arrows. **"All sessions" aggregate (resolves stats concern):** the
  existing `ALL_SESSIONS_KEY` aggregate is **not** a group member — keep it as a
  fixed ring member appended **after** the grouped+active entries, reachable by
  left/right, and **unaffected by `[`/`]`** (group switching never hides it). It
  is layered on top of the pure `group_sessions()` output by the stats ring
  builder, not returned by the pure function.
- **Default selected group:** on mount, set the selected group to the **attached
  session's resolved `project_group`** (falls back to "(ungrouped)" /
  first-group when the attached session has none).
- **Conventions doc:** update `aidocs/framework/tui_conventions.md:156-189` to
  document the new two-axis model (left/right = group + active out-of-group + (in
  stats) the All-sessions aggregate; `[`/`]` = group switch). Keep this with the
  code change so the documented convention never lags the binding.
- **Monitor/minimonitor override (explicit requirement — resolves concern):** the
  `_switcher_selected_session` overrides in `.aitask-scripts/monitor/monitor_app.py:885-899`
  and `.aitask-scripts/monitor/minimonitor_app.py:761-777` preselect a session
  that may belong to a different group than the attached one. The switcher MUST
  set its **selected group to follow the preselected session's group** on open,
  so the preselected repo is guaranteed to be inside the rendered ring (otherwise
  the switcher would open focused on a repo outside the current ring). Add a test
  for the cross-group preselection case.

**Tests:** headless test of the switcher/stats ring derivation through the real
entry points (extend `tests/test_multi_session_primitives.sh` /
`test_multi_session_monitor.sh` style); a binding test that `[`/`]` advances the
selected group and left/right stays within ring; the live-but-out-of-group repo
appears in the ring while a different group is selected.

---

### Child 3 — Settings-TUI editor for per-user project-groups

**Goal:** Add an interaction surface in the settings TUI to edit per-user group
membership (consumes child 1's write API).

**Key changes:**
- Add a `project-groups` `TabPane` (or a `ModalScreen` editor following the
  existing `EditVerifyBuildScreen` / `ProfilePickerScreen` pattern in
  `.aitask-scripts/settings/settings_app.py`) listing registered repos with their
  current group, allowing assign/create/rename/clear. Writes go through child 1's
  registry writer + slug validator (no direct YAML poking from the TUI).
- **Edit semantics (resolves rename-semantics concern) — encapsulated in model
  methods so the screen calls one method each (per "encapsulate cleanup in
  model"):**
  - **Assign:** set one repo's `project_group` to an existing or new slug.
  - **Create:** a group exists implicitly once ≥1 repo references its slug; no
    separate group object. Creating a duplicate slug is a no-op merge into the
    existing group.
  - **Clear:** empty/blank group → unset membership (repo becomes "(ungrouped)").
  - **Rename:** read-modify-write the whole registry in **one** atomic pass that
    rewrites `project_group` on **every** member entry from old→new slug
    (reuses the existing `build_registry_yaml` full-file re-serialize round-trip,
    so it is already atomic). Renaming to an existing slug merges the two groups.
  - All names pass the child-1 slug validator (lowercase `[a-z0-9_-]`); illegal
    input is rejected/normalized with a visible message before any write.
- Reuse the keybinding-registry/tab-switch machinery already in `settings_app.py`
  (`:156-` tab-switch map) for the new tab.

**Tests:** model-level tests against a temp registry for assign, create
(duplicate-merge), clear→ungrouped, rename (all members rewritten atomically),
rename-into-existing (merge), and slug rejection of `:`/`#`/`|`/space/uppercase;
a smoke test that the tab/screen mounts.

---

### Child 4 — Terminology + user-facing docs rollout

**Goal:** Introduce `project-group` across docs without churning the immovable
`project`-named surfaces.

**Key changes:**
- `aidocs/framework/cross_repo_references.md`: define `project-group`, the
  registry field, the bootstrap-from-config rule, and the `ait projects group`
  verbs.
- Website workflows pages (e.g. `website/content/docs/workflows/multi_project.md`)
  + the hand-curated `_index.md` bullet list if a new page is added (per the
  "Workflows _index.md is a manual page list" convention). Use **invented generic
  example product/repo names** (e.g. `frontend`/`backend`), never the author's
  real repos.
- Document the two-axis TUI navigation in user-facing TUI docs.

**Tests:** docs only — run `./.aitask-scripts/aitask_skill_verify.sh` if any
skill/template surface is touched (likely none); link-check.

---

### Child 5 — Manual-verification sibling (TUI live flows)

Aggregate `issue_type: manual_verification` task verifying live behavior the unit
tests cannot: switcher `[`/`]` group switch + left/right ring incl. a live
out-of-group repo; stats TUI grouped navigation; settings-TUI group editor
round-trip (edit → registry → re-render). Seeded from children 2 & 3.

## Cross-agent note

All changes are in shell/Python/docs (no `.claude/skills` surface), so no
Codex/OpenCode skill port is required. If any skill stub is touched in child 4,
regenerate goldens in the same commit.

## Risk (parent-level)

- **Code-health risk: medium.** The registry reader is a single-authority,
  parity-pinned surface (Python + bash awk + `--list-registry` + parity test);
  the 4→5-field change must land atomically across all four or
  `test_registry_reader_parity.sh` fails. Mitigated by doing the reader change as
  the first, self-contained part of child 1 with parity tests landing in the same
  child. The registry has **no quoting/escaping** (raw scalars +`|`-separated
  read in `build_registry_yaml`), so the slug naming contract (child 1) is the
  load-bearing mitigation — it makes corrupting characters structurally
  impossible rather than relying on escaping. Group resolution moved into
  discovery (not just `ait projects add` bootstrap) so live/unregistered repos
  resolve a group on the read path. TUI changes repurpose an existing documented
  convention (left/right) — blast radius limited to switcher + stats;
  monitor/minimonitor preselection made an explicit group-following requirement.
- **Goal-achievement risk: low.** All primitives already exist (`is_live`
  per-session discovery, registry reader, settings TUI editor pattern); this is
  additive wiring, not new infrastructure. Per-child risk is evaluated in each
  child's own plan.

## Verification

- Child unit/parity tests above (`bash tests/test_*.sh`,
  `shellcheck .aitask-scripts/aitask_*.sh`).
- End-to-end manual flow covered by child 5.

## Step 9 (Post-Implementation)

This parent is split into children: after approval, create children + write their
plans, revert parent to `Ready`, release the parent lock; the parent archives
automatically when its last child completes (`children_to_implement` empties).
