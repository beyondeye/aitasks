---
Task: t1099_fix_session_name_collision_default_session_fallback.md
Base branch: main
plan_verified: []
---

# t1099 — Fix session-name collision when repos share the default session fallback

## Context

`_read_default_session()` in `.aitask-scripts/lib/agent_launch_utils.py:555`
returns the literal `"aitasks"` for any registered repo that does **not** set
`tmux.default_session`. When `discover_aitasks_sessions(include_registered=True)`
synthesizes registry entries, every such repo gets `session="aitasks"`. The two
registry-inclusive consumers — the **stats TUI** and the **TUI switcher** — plus
the **shared ring/group helpers** they both call, key *identity* on
`AitasksSession.session`. So two colliding repos:

- share one `_session_cache` slot in stats → **one repo's stats bleed onto the
  other**;
- produce duplicate `_SessionItem` / session-row entries that both render as
  "selected";
- become unreachable by left/right and `[`/`]` cycling — `cross_group_step()`
  and `advance_group_selection()` always match the *first* colliding entry.

The tmux session name is inherently **not** a unique identity (unconfigured repos
legitimately share it; two live repos can share a basename). The fix is to route
all *identity* through a truly-unique key — `project_root` — while keeping
`session` purely as the tmux **label/target**. Root cause and consumers were
confirmed by grep across the tree: only `stats_app.py` and `tui_switcher.py` pass
`include_registered=True`; `monitor_core.py`, `aitask_projects.sh`, and
`aitask_project_resolve.sh` use the live-only default (unique tmux names) and are
**unaffected** — so they are out of scope.

## Design — one unique identity key at the shared sink

Introduce a single stable identity, `AitasksSession.key` = `realpath(project_root)`,
and make the shared helpers + both registry-inclusive consumers key identity on it.
`session` stays the tmux label/target; `project_name` stays for display. This is a
structural fix at the shared seam — it makes the colliding-identity path impossible
rather than patching each consumer.

### 1. `agent_launch_utils.py` — the seam

- **`AitasksSession`**: add a computed property
  ```python
  @property
  def key(self) -> str:
      """Stable unique identity, independent of the tmux session name.
      The tmux `session` is NOT unique across discovered repos (unconfigured
      repos all fall back to `aitasks`); `project_root` is. Used for
      caching/selection/cycling; `session` stays the tmux label/target."""
      try:
          return os.path.realpath(self.project_root)
      except OSError:
          return str(self.project_root)
  ```
  (Frozen dataclass permits properties; `os` already imported.)
- **`CrossGroupRingEntry`**: add a `key: str` field alongside `session` (identity vs
  tmux label). Update the docstring to note `session` is the label/target, `key` the
  match identity.
- **`cross_group_ring()`**: emit `CrossGroupRingEntry(session=s.session, group=tag, key=s.key)`.
- **`cross_group_step()`**: rename param `current_session` → `current_key`, match
  `e.key == current_key`.
- **`default_selected_group()`**: rename param `selected_session_name` → `selected_key`,
  match `s.key == selected_key`. (The `__all__` sentinel matches nothing → falls back
  to first group, unchanged.)
- **`advance_group_selection()`**: rename param `selected_session` → `selected_key`
  and `fallback_session` → `fallback_key`; build `members = [s.key for s in group_members(...)]`;
  return `GroupCycleSelection(selected_group=…, repoint_key=…)`.
- **`GroupCycleSelection`**: rename field `repoint_session` → `repoint_key`.
- `group_sessions` / `group_members` / `_session_in_group` are unchanged (they return
  `AitasksSession` objects; callers read `.key`/`.session` as needed).
- **New pure label helper** (identity is always the key; *labels* are per-surface).
  It **guarantees globally-unique labels** by escalating primary → `primary (secondary)`
  → `primary (fallback)`, where `fallbacks` are caller-supplied globally-unique tokens
  (compact roots):
  ```python
  def disambiguate_labels(primaries, secondaries, fallbacks) -> list[str]:
      """Index-aligned, guaranteed-unique display labels.
      A primary unique among `primaries` renders as-is (unchanged from today).
      A repeated primary escalates to `primary (secondary)`; if that STILL
      collides, to `primary (fallback)`. `fallbacks` must be globally unique
      (e.g. compact project_root), so the final labels are always distinct."""
      from collections import Counter
      pc = Counter(primaries)
      lvl1 = [p if pc[p] == 1 else f"{p} ({s})"
              for p, s in zip(primaries, secondaries)]
      lc = Counter(lvl1)
      return [l if lc[l] == 1 else f"{p} ({f})"
              for l, p, f in zip(lvl1, primaries, fallbacks)]
  ```
  Unit-testable in isolation; each surface picks its own primary/secondary and passes
  a compact-root fallback (below).
- **New shared initial-selection resolver** (so the switcher and stats resolve "which
  repo did we open on?" through **one** tested path, not two):
  ```python
  def resolve_selected_key(sessions, *, provisional_session=None, cwd=None) -> str | None:
      """Identity key of the session a TUI should select on open, resolved by
      UNIQUE context to survive the default-session collision:
        1. if `cwd` is given, `_walk_up_to_aitasks(cwd)` → the entry whose
           realpath(project_root) matches it (the repo the TUI was launched from);
        2. else `.session == provisional_session`, preferring is_live=True;
        3. else the first session-name match; else None."""
  ```
  `cwd=None` skips step 1 (used for an explicit cross-repo preselection, where the
  launch cwd is irrelevant). Returns `None` when nothing resolves, letting each caller
  pick its own safe default.

### Display philosophy (labels are per-surface, identity is not)

The `project_root` key is the **internal** identity everywhere. What the user *sees*
is chosen per surface:
- **Session-name-primary surfaces** — the TUI switcher (and, unaffected, monitor /
  minimonitor which are live-only) — keep the **tmux session name** as the primary
  label because it is meaningful there. The narrow switcher panel keeps the bare
  session label for unique names and appends a **compact** disambiguator *only* when
  session names collide.
- **Project-oriented surface** — the stats TUI — the tmux session name is not
  meaningful, so `session + project` is redundant. Use the **project/repo name** as
  the label, adding a secondary disambiguator only when project names collide.

### 2. `stats/stats_app.py` — key-based identity, session for display

Rename `selected_session` → `selected_key` (holds a `project_root` key or the
`ALL_SESSIONS_KEY="__all__"` sentinel) and route every identity site through the key:

- `_session_cache` keyed on `sess.key` (`_stats_for`).
- `_default_session_selection` → `_default_key_selection`: resolve via the shared
  `resolve_selected_key(self.sessions, provisional_session=attached_tmux_name,
  cwd=Path.cwd())` — so stats opens on the **repo it was launched from** (unique cwd
  context) even when several projects share `session="aitasks"`. When it returns `None`
  (launched outside any repo / ambiguous with no cwd match), default to
  `ALL_SESSIONS_KEY` (the all-projects aggregate) rather than silently picking the first
  colliding project.
- **Labels are project-oriented (not `session + project`).** Build a
  `self._labels: dict[str, str]` once from the discovered sessions:
  `disambiguate_labels(primaries=[s.project_name …], secondaries=[<compact root> …],
  fallbacks=[<compact root> …])` where `<compact root>` = `str(project_root)`
  home-abbreviated (`~`, globally unique). So a normal unique repo shows just its
  **project name** (no redundant session); the session-collision bug case
  (`session="aitasks"` × 2, distinct project names) renders as two distinct project
  rows; and two repos sharing a `project_name` fall through to the unique compact root.
- **Aggregate label is project-oriented:** `ALL_SESSIONS_KEY → "All projects
  (aggregate)"` (the constant name stays; only display text changes). For consistency
  with the project model, the session-panel title (`"Session  ← / → to cycle"`) and the
  `notify(f"Session: …")` / title strings become **"Project"**-worded. (`SessionTotals`
  is a data struct — field names unchanged.)
- `_session_key_to_label(key)`: return `self._labels.get(key, key)`.
- `_SessionItem`: its identity attr holds `sess.key`; construct with `sess.key` and
  the project-oriented label from `self._labels`. (Rename attr `session_key` →
  `identity_key` for honesty; update the ~3 `on_mount`/selection sites.)
- `_load_data`: aggregate check `selected_key == ALL_SESSIONS_KEY`; else pick
  `next(s for s in self.sessions if s.key == self.selected_key, self.sessions[0])`.
  `SessionTotals`/`session_breakdown` keep `session=s.session, project_name=s.project_name`
  (pure display — unchanged).
- `_session_ring` → `[e.key for e in cross_group_ring(...)] + [ALL_SESSIONS_KEY]`.
- `_cycle_session`: append `CrossGroupRingEntry(ALL_SESSIONS_KEY, self._selected_group, ALL_SESSIONS_KEY)`;
  step by `self.selected_key`; branch on `target.key != ALL_SESSIONS_KEY`; commit
  `_apply_session_selection(target.key)`.
- `_apply_session_selection(new_key)` and `_cycle_group` (`advance_group_selection`
  now returns `repoint_key`, `fallback_key=ALL_SESSIONS_KEY`) operate on keys; sidebar
  mirror matches `item.identity_key == new_key`.
- `default_selected_group(self.sessions, self.selected_key)`.

### 3. `lib/tui_switcher.py` — split identity from tmux target (structural)

Today `self._session` is *both* the selection identity and the tmux target/label,
so under collision `_project_root_for_session()`, `_handle_stale_selection()`,
`_ensure_session_live()` all resolve the wrong (first-match) entry. Make the identity
a single source of truth and derive the session name from the selected entry:

- Add `self._selected_key: str`. Make `self._session` a **read-only property**:
  ```python
  @property
  def _session(self) -> str:
      e = self._selected_entry()
      return e.session if e else self._selected_key
  ```
  so `_session` can never disagree with the selected entry (removes the dual-field
  invariant). Add `_selected_entry()` (match `s.key == self._selected_key`) and
  `_selected_project_root()` (its `project_root`, else `Path.cwd()`).
- `__init__`: keep the incoming names as provisional strings —
  `self._provisional_session = selected_session or session`,
  `self._has_preselection = selected_session is not None`, and set
  `self._selected_key = self._provisional_session` provisionally (pre-discovery, no
  entries → property returns it verbatim, preserving legacy single-session behavior).
- **Initial-selection resolution (`_init_multi_state`, and re-run on
  `on_registry_refresh`) — resolve via UNIQUE context, not just the session name.**
  The opening session name is ambiguous under the exact collision (an attached-live
  `aitasks` and a synthesized `aitasks` both match). Resolve `self._selected_key`
  through the **shared `resolve_selected_key`** helper (same path stats uses):
  - **Explicit preselection** (`_has_preselection`, from monitor/minimonitor focusing an
    agent): `resolve_selected_key(self._all_sessions,
    provisional_session=_provisional_session, cwd=None)` — cwd irrelevant for a
    cross-repo preselection; the is_live preference picks the focused live session.
  - **Attached (no preselection):** `resolve_selected_key(self._all_sessions,
    provisional_session=_provisional_session, cwd=Path.cwd())` — the unique
    `_walk_up_to_aitasks(Path.cwd())` root disambiguates the two `aitasks` entries.
  - On `None`, keep the provisional string (legacy single-session behavior).
  Wrap this in `_resolve_initial_key()` so `_init_multi_state` and `on_registry_refresh`
  share it. Membership guards (`any(...)`) compare `.key`; on a refresh miss (selected
  entry pruned) re-resolve via the same helper (attached path).
- Convert the 5 `self._session = …` assignments to set `self._selected_key`
  (init, two fallbacks, `_cycle_session` → `target.key`, `_cycle_group` → `repoint_key`).
- `_cycle_session`: `cross_group_step(entries, self._selected_key, step)`; set
  `_selected_key = target.key`, `_selected_group = target.group`.
- `_cycle_group`: `advance_group_selection(…, self._selected_key, step)`; set
  `_selected_key = target.repoint_key` when non-None.
- `default_selected_group(self._all_sessions, self._selected_key)`.
- Identity lookups switch to the selected entry: `_handle_stale_selection` /
  `_ensure_session_live` use `_selected_entry()`; desync/populate/spawn sites use
  `_selected_project_root()` instead of `_project_root_for_session(self._session)`.
- Render row (`_render_session_row`): `selected = (s.key == self._selected_key)`.
  The displayed label stays **session-name-primary**: compute
  `disambiguate_labels(primaries=[s.session …], secondaries=[s.project_name …],
  fallbacks=[<compact root> …])` across the rendered group members, so a unique session
  renders as the bare name (as today, narrow-panel-friendly), colliding `aitasks` rows
  with distinct repos render compactly as `aitasks (foo)` / `aitasks (bar)`, and the
  pathological both-collide case (same session *and* same project name) still resolves
  to the unique compact root — labels are guaranteed distinct. The `▶ attached` /
  `(stale)` / reverse-selected markup wraps this label unchanged.
- tmux-target reads of `self._session` (spawn/switch-client/window targeting) are
  unchanged — the property yields the selected entry's real session name.
- `_project_root_for_session(session)` stays (a name→root lookup used with real live
  session names) but is no longer the identity path.

### 4. Tests

- **New regression** `tests/test_session_key_collision.py` (Python, self-contained):
  construct ≥2 `AitasksSession` with **identical `session="aitasks"` but distinct
  `project_root`** and assert distinguishability across the whole surface:
  - `.key` differs; `cross_group_ring` yields two entries; `cross_group_step`
    starting from each `key` reaches the *other* (round-trip through both).
  - `disambiguate_labels`: unique primaries pass through verbatim (**no** suffix —
    "render as before"); duplicate primaries get ` (secondary)` on the colliding
    entries only; when primary **and** secondary both collide, labels escalate to the
    unique `fallback` and the full result set is asserted **all-distinct**.
  - **shared `resolve_selected_key`**: with two `aitasks` entries (distinct roots),
    a `cwd` under repoB resolves to repoB's key (not the first); with `cwd=None` +
    provisional `aitasks`, prefers the `is_live` entry; returns `None` when nothing
    matches.
  - **switcher initial selection under collision**: `_all_sessions` = an
    attached-live `aitasks` (repoA) **and** a synthesized `aitasks` (repoB, distinct
    root). Opening with the attached name + patched `Path.cwd()` under repoA resolves
    `_selected_key`/`_selected_project_root()` to repoA — not repoB. A separate case
    with an explicit `selected_session` preselection prefers the `is_live` match.
  - **stats default selection under collision**: two `aitasks` entries (distinct roots);
    `_default_key_selection` with `Path.cwd()` patched under repoB selects repoB's key;
    with cwd outside any repo (helper → `None`) it defaults to `ALL_SESSIONS_KEY`, not
    the first colliding project.
  - **stats** (mount the real `StatsApp` with monkeypatched `discover_stats_sessions`,
    per `test_stats_include_registered.py`): both repos are distinct session rows;
    `_stats_for` caches per-key (no bleed — give each a distinct `project_root` with
    different archive fixtures / patched `collect_stats`); left/right cycling visits
    both then `__all__`.
  - **switcher**: `TuiSwitcherOverlay` with the two colliding entries →
    `_selected_project_root()` returns the correct root for each selection; cycling
    reaches both.
- **Display / label tests** (satisfy the per-surface labeling requirement):
  - **stats, unique entries**: two repos with **distinct** project names (even sharing
    `session="aitasks"`) → each `_SessionItem` label / `_session_key_to_label` is the
    bare **project name**, and asserts the label does **not** contain the redundant
    `session (project)` form.
  - **stats, project-name collision**: two repos with the same project name → labels
    are disambiguated (distinct strings) via the compact-root secondary/fallback.
  - **stats, aggregate label**: `_session_key_to_label(ALL_SESSIONS_KEY)` is the
    project-oriented `"All projects (aggregate)"`.
  - **switcher, unique sessions**: distinct configured session names render as the
    bare session name (unchanged from today).
  - **switcher, session collision**: two `session="aitasks"` rows render as
    `aitasks (foo)` / `aitasks (bar)` — compact, distinguishable — and the
    both-collide case escalates to unique compact-root labels.
- **Update** `tests/test_tui_group_nav.py`: direct helper calls now pass a **key** as
  `current` (fixtures use `project_root=/tmp/<name>`, so keys are distinct); the
  bootstrap test sets `ov._selected_key` instead of `ov._session =` (now read-only).
  `_group_member_names` stays session-name-based (membership display, off the identity
  path) so its assertion is unchanged; pilot assertions on the resulting
  `overlay._session` **name** stay valid.
- `tests/test_discover_include_registered.py` is unchanged — session **names** are
  not altered by this fix (assertions on `.session == "aitasks"` remain correct).
- Run: `bash tests/run_all_python_tests.sh` (plus the new file and
  `test_stats_include_registered.py`, `test_tui_switcher_*`).

## Rejected alternatives

- **Mangle the fallback session name** (e.g. `aitasks-<name>` in `_read_default_session`):
  diverges from bash `aitask_ide.sh::resolve_session` (same `"aitasks"` default),
  misrepresents the tmux name a repo would actually use, and doesn't fix the
  conceptual non-uniqueness. Rejected.
- **Key on `project_name`**: not unique — two live repos can share a basename with
  distinct tmux sessions; keying on it would *merge* two real repos. `project_root`
  is the only truly-unique choice (task's own recommendation).
- **Maintain `self._session` as a mirror of `_selected_key`** instead of a property:
  reintroduces a fragile two-field sync invariant; the property makes disagreement
  impossible.
- **Split into child tasks**: the shared-helper signature change and both consumers
  must land in lockstep (any split leaves a broken intermediate). Kept as one
  cohesive commit.

## Verification

1. `bash tests/run_all_python_tests.sh` — all green, including the new
   `test_session_key_collision.py` and updated `test_tui_group_nav.py`.
2. `python3 -m pytest tests/test_stats_include_registered.py tests/test_tui_group_nav.py -v`.
3. Manual (covered by an optional follow-up MV task, not blocking): register two repos
   with no `tmux.default_session`, open `ait stats` — confirm two distinct
   **project-named** rows (no redundant `session (project)`), each with its own totals,
   and that ←/→ and `[`/`]` reach both; open the TUI switcher and confirm the colliding
   rows show `aitasks (repoA)` / `aitasks (repoB)` and each selects/acts on its own
   project_root, while a uniquely-named session still shows its bare name.
4. `shellcheck` is N/A (Python-only change).

## Post-implementation (Step 9)

Standard: user review (Step 8) → commit `bug: … (t1099)` → merge approval → archive.

## Risk

### Code-health risk: medium
- Cross-cutting identity refactor across 3 files (~35 sites) touching a load-bearing
  navigation seam shared by two TUIs · severity: medium · → mitigation: TBD
- `tui_switcher._session` converted from a mutable attr to a read-only property, plus a
  shared context-based initial-key resolver (`resolve_selected_key`, cwd walk-up /
  is_live preference) used by both TUIs; a missed assignment site, a mis-resolved
  provisional key, or the legacy single-session path could mis-target tmux ·
  severity: medium · → mitigation: covered by the shared-resolver + switcher/stats
  initial-selection + cycling regression tests

### Goal-achievement risk: low
- Approach (unique `project_root` key at the shared sink) is the task's own
  recommendation and directly satisfies every acceptance criterion; the regression
  test reproduces the exact collision · severity: low · → mitigation: TBD
