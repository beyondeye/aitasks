---
Task: t1223_5_settings_tab_and_push_action.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_6_*.md, aitasks/t1223/t1223_7_*.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_*_*.md
Worktree: (none — profile 'fast': current branch)
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-28 12:23
---

# p1223_5 — Settings tab and push action — verified 2026-07-28

> Execution view for `aitasks/t1223/t1223_5_settings_tab_and_push_action.md`.
> Parent design, contract **D**: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.
> This plan **revises** the pre-existing p1223_5, which was written before
> t1223_4 (`790b28f2a`, HEAD) and t1266 landed.

## Context

`ait syncer` is now a tabbed cross-repo console: Branches (t1223_1), Versions +
upgrade (t1223_3), and an empty **Settings** placeholder pane. t1223_4 landed the
headless seam `.aitask-scripts/lib/cross_repo_settings.py` that reads, diffs and
validates the default code agent per operation across repos.

This child is the **UI**: it fills `TabPane(id="tab_settings")` with a
repo × operation matrix showing divergence at a glance, and adds a push action
that brings repos into agreement. It **renders and routes** — every value
decision stays in `cross_repo_settings`.

---

## Verification findings — the pre-existing plan drifted

Re-read against live source at `790b28f2a`. Six findings; four change the spec.

| Claim in the old plan / task file | Reality |
|---|---|
| marker table includes `(seed)` | **No `seed` tier.** t1223_4 dropped it (amended in the parent plan, the task file, and pinned by `test_seed_config_does_not_influence_anything`). Provenance is `local` / `project` / `builtin` / `conflict`. Required test 1 loses its `seed` case. |
| `tui_conventions.md` carries a "render-level verification rule (assert `render().plain`, prefer `markup=False`)" | **Not in that file.** No such rule anywhere in `aidocs/framework/`. The convention exists only as practice in `tests/test_syncer_rows.py` (`detail_text()`, `version_cells()`, `#upgrade_text`). Followed as practice; the doc gap is noted for t1223_6. |
| `syncer_app.py:90-105` / `:149-156` / `:426-430` / `:240-260` | All shifted (file is now **1698** lines): `RowSpec` **178-193**, `build_labels` **237-244**, `check_action` **705-729**, `coalesce_request` **401-421**. Behavior intact. |
| "`diff_across_repos(diff)` in a thread worker … catch `DestConfigUnreadable` per repo" | **Not achievable as written** — see finding 1. |
| "default to the highlighted **cell**'s effective value" | **Unreachable by keyboard** — see finding 2. |
| `TAB_LIST_IDS` / `_active_list` unchanged | Both must change — see finding 3. |

### 1. `diff_across_repos` fails globally, not per repo *(user-confirmed)*

The task file's binding note says to catch `DestConfigUnreadable` **per repo**,
"letting it propagate would blank the whole tab because one repo is broken". But
`diff_across_repos` reads every root's layers in one un-guarded loop
(`cross_repo_settings.py:294-295`), so **one corrupt repo aborts the entire call**
and returns no matrix at all. Its own docstring says callers wanting per-repo
degradation must loop `read_operation_defaults` themselves.

**Decision (user-confirmed): two-phase, syncer-side only.** The happy path calls
`diff_across_repos(roots)` exactly once. Only when it raises do we sweep
`read_operation_defaults` per root to identify the offender(s), render those
columns `unavailable`, and re-call with the good roots. The double subprocess
fan-out is paid **only** in the rare broken case, and `cross_repo_settings.py` —
which landed one commit ago and whose value logic this child must not touch — is
left alone.

Note the sweep is cheap for a *broken* root: the layer read raises before
`_collect` spawns anything.

### 2. The cell cursor is unreachable — the source value needs an explicit step *(AC deviation, user-confirmed)*

t1266 binds `left`/`right` **App-level with `priority=True`** and
`action_prev_tab` / `action_next_tab` switch tabs "regardless of what holds
focus" (`syncer_app.py:529-530, 797-803`). `check_action` keeps them active
whenever no screen is pushed (`:715-716`). Independently,
`tui_conventions.md:182` instructs DataTables to use `cursor_type="row"` *so that
they do not consume ←/→*. A `cursor_type="cell"` settings table therefore could
never move its cursor horizontally by keyboard, and "the highlighted cell" cannot
be the source of the push.

**Decision (user-confirmed):** `cursor_type="row"` (rows = operations, matching
both existing tables), and the source value becomes an **explicit RadioSet step**
listing each repo with its effective value for that operation, first repo (always
the cwd repo — `discover_syncer_sessions` guarantees it is first) preselected.
This is also the better shape: it makes the source a visible choice rather than
one implied by cursor position. The task file's step 1 is updated in the same
commit.

### 3. `TAB_LIST_IDS` and `_active_list` are waiting for this task

`syncer_app.py:147-153` says verbatim: *"`tab_settings` is deliberately absent:
its pane is a non-focusable Static placeholder until t1223_5 … When t1223_5 lands
a focusable Settings pane, add its list id here."* `_active_list`'s docstring
(`:688-703`) and `action_nav_down`'s no-op branch (`:757-760`) both name the
Settings placeholder as the designed "no list" case. All three need updating, and
**two existing tests must invert rather than be deleted**:
`test_versions_pane_holds_the_table_and_settings_the_placeholder` (`:713`) and
`test_down_on_the_settings_placeholder_is_a_noop` (`:914`).

### 4. Every impure seam must be patched in `booted()` — this bit t1223_3 already

`test_branch_actions_inert_on_other_tabs_negative_control` (`:1069`),
`test_version_actions_are_inert_off_the_versions_tab` (`:1253`) and
`test_tab_switching_wraps_at_both_ends` (`:893`) **all activate `tab_settings`**
for unrelated assertions. A lazy load fired from tab activation would make the
existing suite shell out `resolve_agent_string` against the developer's real
registered repos. `booted()` must gain `diff_across_repos`,
`read_operation_defaults`, `plan_push` and `apply_push`, imported into
`syncer_app`'s namespace so `mock.patch.object` reaches them.

### 5. The push must not commit the destination

`tui_conventions.md:149-158`: *"Never call `git commit` or `./ait git push` from
inside a TUI event handler for a config change."* Project-level files are
read-only at runtime **except** for an explicit user-initiated publish action —
which this is. So the write is allowed; **committing it is not**. The destination
is left with an uncommitted config change, and on a repo whose `aitasks/` is a
symlink onto an `aitask-data` branch that change is invisible to `git status` in
its main checkout (t1223_4's sibling note). The layer prompt and the summary say
so.

### 6. `t1267` is waiting on exactly this change

`aitasks/t1267_syncer_settings_tab_nav_coordination.md` is t1266's "after"
risk-mitigation and names t1223_5 directly. It says verbatim: *"If t1223_5 has
already landed by the time this task is picked, replace step 1 with the actual
fix: extend `TAB_LIST_IDS` / the fall-through conditions and add a test asserting
the Settings pane's focusable widgets still receive their arrow keys (mirroring
`test_arrows_in_an_upgrade_modal_do_not_switch_tabs`)."*

This plan does the `TAB_LIST_IDS` half (finding 3). Adding that arrow test for the
settings modals (test 18) makes **this task satisfy t1267's substantive scope**.
No fall-through change is needed for the modals themselves: they are *pushed
screens*, and `check_action`'s blanket `len(self.screen_stack) <= 1` gate
(`:715-716`) already disables every nav action there — pinned by
`test_nav_actions_inert_only_while_a_screen_is_pushed` (`:1002`). A bidirectional
coordination note goes into both task files; **t1267 is not closed here** — it
stays for the user to verify and dispose of.

### 7. The settings row set is rebuilt on every refresh

Branches and Versions build `_rows_by_key` / `_version_rows_by_key` once in
`__init__` and never reassign. The settings matrix is data-derived, so its rows
**are** rebuilt on each apply. p1223_3 finding 11 created `UpgradeTarget`
explicitly as "the forward guard if the row set ever becomes rebuildable" — this
is that change, so the push flow captures a frozen target and its mid-flow
mutation test is load-bearing rather than theoretical.

---

## Steps

### 1. Matrix model — pure, unit-tested

In `.aitask-scripts/syncer/syncer_app.py`, next to `VersionRow` (`:266`):

```python
@dataclass(frozen=True)
class SettingsRow:
    """One Settings-tab row = one operation across every repo column.

    ``row_key`` is opaque and positional (``s0``, ``s1``, …), recovered through
    ``_settings_rows_by_key`` exactly like RowSpec/VersionRow. Unlike those two,
    this row set is REBUILT on every refresh — nothing may hold a row across a
    modal (see PushTarget).
    """
    row_key: str
    operation: str
    cells: tuple[str, ...]   # rendered text, one per repo column, in column order
    sources: tuple[str | None, ...]  # effective value where it is a LEGAL push
                                     # source, else None — same column order
    divergent: bool

    @property
    def has_source(self) -> bool:
        return any(s is not None for s in self.sources)


def build_settings_matrix(
    diff: dict[str, dict[str, OperationValue]],
    session_keys: list[str],
    unreadable: frozenset[str] = frozenset(),
) -> list[SettingsRow]:
```

Cell text — the amended marker table (**no `seed` row**):

| provenance | cell |
|---|---|
| `local` | `<value> (local)` |
| `project` | `<value>` |
| `builtin` | `<value> (default)` |
| `conflict` | `conflict` — **the literal, never a value** |
| repo in `unreadable` | `unavailable` |

`effective is None` always classifies as `conflict` upstream, so a non-conflict
cell always has a value.

**Divergence** = more than one distinct `effective` among the **readable** repos,
**or** any readable cell is `conflict`. Unreadable columns are excluded from the
comparison (their agreement is unknowable; flagging every row on one broken repo
would be noise) — stated, not implied.

**Source eligibility** — `sources[i]` is the repo's `effective` value **only when
it can truthfully be copied**, i.e. the repo is readable **and**
`provenance != conflict` **and** `effective is not None`; otherwise `None`.
Deriving it here, in the pure model, keeps the rule in one tested place instead of
re-deriving it inside the push flow.

This is load-bearing, not defensive. `plan_push` does
`_AGENT_STRING_RE.match(value or "")` (`cross_repo_settings.py:342`), so passing a
`None` or unusable source does **not** raise — it returns
`rejected(malformed_agent_string)` for **every** destination, which reads to the
user as *"the value you chose is malformed"* rather than *"there was no value to
push"*. A `conflict` cell is equally unusable: the contract's whole point is that
the repo's layers and its resolver disagree, so its effective value is not a
coherent thing to propagate ("never a guess").

Rendered as a leading one-character `Δ` column holding `≠` on divergent rows and
`""` otherwise. Deliberately plain text, no Rich styling: every cell stays
`str(get_cell(...))`-assertable, which is the repo's render-level verification
practice.

### 2. Table

Replace the `Static(..., id="settings_placeholder")` in
`TabPane("Settings", id="tab_settings")` (`:624-627`) with:

```python
settings = DataTable(id="settings", cursor_type="row", zebra_stripes=True)
settings.add_column("Δ", key="diverge")
settings.add_column("Operation", key="operation")
for idx, sess in enumerate(self.sessions):
    settings.add_column(labels.get(sess.key, sess.project_name), key=f"c{idx}")
```

Columns are known at `__init__` (the session list is). Column keys are **opaque
and positional** (`c0`, `c1`, …) with `_settings_col_keys[idx] -> session.key`,
mirroring the row-key rule. Add `#settings { height: auto; max-height: 20; }` to
`CSS`. Add `"tab_settings": "settings"` to `TAB_LIST_IDS`, and update
`_active_list`'s docstring plus `action_nav_down`'s comment (keep the
`not in TAB_LIST_IDS` guard as defensive, noting no current tab reaches it).

### 3. Lazy, coalesced data load

Mirror the Versions triple exactly: `_settings_loaded`, `_settings_gen`,
`_settings_active`, `_pending_settings = PENDING_UNSET`; `_request_settings()`
reusing the **existing pure** `coalesce_request` (`:401`); apply callback gated on
`gen == self._settings_gen` with `_finish_settings()` unconditional. Triggered
from `on_tabbed_content_tab_activated` (`:731`) on first `tab_settings`
activation — a user who never opens the tab pays no subprocess.

Finding 1: the seam aborts globally, so the per-repo degradation is a
**bounded shrink-and-retry loop**, not a single fallback. A repo can also break
*between* the probe sweep and the re-read, so one extra attempt is not enough —
but the loop must terminate, and a raced failure must never be paid for by repos
that are provably fine.

```python
@work(thread=True, exclusive=True, group="syncer-settings")
def _settings_worker(self, gen: int) -> None:
    good = list(self.sessions)
    unreadable: dict[str, str] = {}
    diff: dict = {}
    unattributed: str | None = None
    # BOUND: each round either removes >=1 session or spends the single
    # non-attributable retry, so at most len(sessions)+2 diff attempts.
    for _ in range(len(self.sessions) + 2):
        if not good:
            break                      # every repo genuinely unreadable
        try:
            diff = diff_across_repos([s.project_root for s in good])
            unattributed = None
            break
        except DestConfigUnreadable as exc:
            still_good, newly_bad = [], False
            for s in good:
                try:
                    read_operation_defaults(s.project_root)
                    still_good.append(s)
                except DestConfigUnreadable as probe_exc:
                    unreadable[s.key] = str(probe_exc)
                    newly_bad = True
            if not newly_bad:
                # The sweep blamed nobody (the fault healed, or it is not
                # attributable to a single repo). Spend exactly one retry.
                if unattributed is not None:
                    diff = {}
                    break
                unattributed = str(exc)
                continue
            good = still_good
            unattributed = None
    self.call_from_thread(
        self._apply_settings, gen, diff, unreadable, unattributed
    )
```

Two properties this buys, both tested:

- **A raced corruption costs only the repo that raced.** Repos that passed the
  probe keep their columns; the newly-broken one is the only column that turns
  `unavailable`. The earlier draft's blanket
  `{s.key: str(exc) for s in self.sessions}` erased provably-good columns — the
  exact per-repo-degradation promise the AC makes.
- **A non-attributable failure is never mislabelled.** If the sweep finds no
  offender, no repo is marked `unavailable` (we did not establish that). The
  worker returns an `unattributed` reason and `_apply_settings` surfaces it as a
  tab-level notice — "settings could not be read; press `c` to retry" — rather
  than inventing per-repo blame.

### 4. Bindings and gating

```python
SETTINGS_TAB_ACTIONS = ("push_setting", "reload_settings")
```
— a sibling tuple to `BRANCH_TAB_ACTIONS` / `VERSION_TAB_ACTIONS`, gated in
`check_action` in the same shape (`False` off `tab_settings`, so the footer drops
the key entirely). Fail-closed for free: `_active_tab()` degrades to
`tab_branches`.

```python
Binding("P", "push_setting", "Push setting"),   # uppercase like U: writes another repo
Binding("c", "reload_settings", "Reload"),      # duplicate key with recheck_version
```

`c` is deliberately shared with the Versions tab's `recheck_version`: the tab
gate makes exactly one live at a time, Textual falls through on a `False`
`check_action`, and `on_tabbed_content_tab_activated` already calls
`refresh_bindings()` so the footer relabels. Pinned by a rendered-`FooterKey`
test, since `check_action` alone never relabels. Both `show=True`
(`tui_conventions.md:338`), with `P` placed adjacent to `p` per the
uppercase-sibling ordering rule.

**`push_setting` needs a second, row-level gate.** The tab gate alone leaves `P`
live in states where no frozen target can be built: before the lazy load's first
apply (the tab is active but the table has zero rows), when every repo configures
no agent operation (`diff == {}` ⇒ zero rows), and on a row where no repo has a
usable source (every cell `conflict` or `unavailable`). It follows the same
tri-state discipline the Branches tab already uses:

```python
if action == "push_setting":
    if not self.multi_repo:
        return False        # nothing to push to — drop the key from the footer
    row = self._selected_settings_row()
    if row is None or not row.has_source:
        return None         # dimmed: right tab, not applicable to this row/state
```

`False` = not part of this configuration's vocabulary (mirrors the tab gate);
`None` = dimmed, same tab, non-applicable row (mirrors `action_allowed_for_ref`,
`:726-728`). The check is pure in-memory — it reads the already-applied matrix
and does no I/O — so it is safe on every `refresh_bindings()`.

**`action_push_setting` re-checks the same condition itself** and returns after a
`notify(...)` when it does not hold. `check_action` gates the *binding*, not the
method: the existing suite calls `app.action_upgrade()` directly
(`test_syncer_rows.py:1396`), so the settings tests will call
`app.action_push_setting()` the same way and would otherwise walk straight into
an undefined flow. The notice names the reason — "no repo has a usable value for
`<operation>` (unreadable or conflicting)" vs "settings not loaded yet".

`reload_settings` stays available in every state, including single-repo.

### 5. Push flow — capture, plan, prompt, apply, summarize

Modals live in a new `.aitask-scripts/syncer/settings_screens.py`, shaped exactly
after `syncer/upgrade_screens.py`: shared `_DIALOG_CSS`, `Binding("escape",
"cancel", show=False)`, `Cancel` focused on mount, body `Static` carrying an
explicit `id` (Textual's `Label` subclasses `Static`, so an id-less
`query_one(Static)` resolves to the title — p1223_3's issue). They declare no
`_shortcuts_scope`, so — like `upgrade_screens.py` — no `KNOWN_BINDING_SOURCES`
entry is needed.

**Step 0 — capture** (finding 7). `action_push_setting` resolves the highlighted
row **once** into a frozen record; nothing downstream re-reads the table or
`_settings_rows_by_key`:

```python
@dataclass(frozen=True)
class PushTarget:
    operation: str
    repos: tuple[tuple[str, str], ...]   # (session_key, label) — EVERY repo, column order
    sources: tuple[str | None, ...]      # eligible source value per repo, else None
```

**Source and destination eligibility are different questions, so the target
carries every repo plus a parallel eligibility tuple** rather than a pre-filtered
list:

- **Source** options = repos where `sources[i] is not None`.
- **Destination** options = every repo **except the chosen source** (below).

A `conflict` repo is *not* a legal source (its layers and resolver disagree, so
its effective value is not a coherent thing to copy) but it **is** a perfectly
legal destination — arguably the one most worth pushing to, since a coherent
write is what resolves the conflict. An `unavailable` repo also stays selectable
as a destination: `plan_push` answers it with the truthful, distinct
`rejected(dest_config_unreadable)`, which tells the user *why*, whereas silently
omitting it would not. Filtering destinations by source-eligibility would get
both of these wrong.

**Step 1 — source** · `SettingsSourceScreen(operation, options)` → `str | None`
(session key). RadioSet listing each **eligible** repo with its effective value;
the **first eligible** entry is preselected — which is the cwd repo when it is
eligible, and the next one when it is not. Preselecting position 0 blindly would
offer a value that cannot be copied whenever the cwd repo is the corrupt or
conflicted one.

**Step 2 — destinations** · `SettingsDestinationsScreen(...)` →
`tuple[str, ...] | None`. `SelectionList[str]` (precedent:
`stats/modals/pane_selector.py` — space toggles, Enter saves). Empty selection
dismisses `None`. Multi-select is safe here: this writes one config key, not
framework files.

**The list is built after the source is chosen, with the source key removed** —
the AC says destinations are "the **other** repos". This is a construction-time
exclusion, not a filter applied later:

```python
def on_source(source_key: str | None) -> None:
    if source_key is None:
        return
    dests = [(k, lbl) for k, lbl in target.repos if k != source_key]
    self.push_screen(SettingsDestinationsScreen(target.operation, dests), on_dests)
```

Letting the source through would put a guaranteed self-targeted `noop` — pushing
a repo's own value into itself — in the middle of the result summary, which reads
as a defect rather than an outcome. `self.multi_repo` (≥2 repos) guarantees the
remaining list is non-empty, so there is no empty-destination state to design
for. Nothing downstream re-derives the destination set, so the source cannot
re-enter it later.

**Step 3 — layer, always asked, no default** · `SettingsLayerScreen(...)` →
`"project" | "local" | None`. Cancel focused; neither layer button is the
default. Option text states project = git-tracked/shared, local =
gitignored/personal, and that **nothing is committed** (finding 5).

**Step 4 — plan all, off the UI thread.** `plan_push` shells
`resolve_agent_string` (10 s timeout each), so a `@work(thread=True,
group="syncer-settings-push")` worker calls it once per destination and returns a
decision list.

**Each destination's `plan_push` gets its own exception boundary**, symmetrical
with the apply phase:

```python
for dest in destinations:
    try:
        outcome = plan_push(value, dest.root, operation, layer)
    except Exception as exc:                 # planning must not kill the worker
        decisions.append((dest, "planning_failed", f"could not be planned: {exc}"))
        continue
```

Without it, one unexpected exception (an `OSError` the seam does not convert, a
`ValueError` from a future validation path) terminates the whole worker: Textual
reports a worker crash, the result screen never opens, and every destination
after the failing one is silently never considered — the user sees nothing and
cannot tell which writes happened. `planning_failed` is a first-class outcome
that appears in the same summary as every other, and no write is attempted for
that destination.

Branch on `PushOutcome.kind` using the module's constants:

- `ok` → queue an apply.
- `noop` → record "already matches"; **no write**.
- `rejected` → record the destination **and `outcome.reason`**; no write for it,
  siblings unaffected.
- `masked` → queue for the prompt in step 5, carrying `outcome.masking_value`.

**Step 5 — drain the masked queue, one modal at a time**, on the UI thread.
`SettingsMaskedScreen(dest_label, operation, masking_value)` →
`"cancel" | "local" | "clear"`, **no default**. Its body states the masking value
verbatim: *"repo B's local layer sets `<masking_value>` for `<op>`; a project
write would have no effect."* Resolutions map to: nothing · `apply_push(...,
layer='local')` · `apply_push(..., layer='project', clear_mask=True)`.

**Step 6 — apply, off the UI thread**, per destination, each independently
guarded so one failure cannot abort the rest:

```python
try:
    apply_push(value, root, operation, layer, clear_mask=clear)
    outcome = "applied"
except PushPartialError as exc:                 # RuntimeError — before Exception
    outcome = (f"partial — project written, local override still "
               f"{exc.masking_value!r}; retry to finish")
except Exception as exc:                        # incl. DestConfigUnreadable (a ValueError)
    outcome = f"failed: {exc}"
```

`PushPartialError` is neither success nor plain failure: the destination's
*effective* value is unchanged, and a retry converges because the project write
is idempotent and `plan_push` still reports `masked`.

**Step 7 — summarize and refresh.** `SettingsPushResultScreen` lists **every**
destination with its outcome (applied / already-matches / rejected-with-reason /
cancelled / partial-retry / **planning-failed** / failed) — a single "done" is
not enough when destinations diverge — and notes that nothing was committed. Then
`_request_settings(explicit=True)`.

`apply_push` gives **per-destination** atomicity only; a multi-destination push
failing partway leaves earlier destinations applied. That bound is declared, and
the per-destination summary is its honest surface.

---

## Verification

```bash
python3 tests/test_syncer_rows.py          # note: python3, not bash
bash    tests/test_shortcuts_registry_coverage.sh
python3 tests/test_shortcut_scopes.py
python3 tests/test_cross_repo_settings.py  # MUST pass unchanged (no seam edits)
bash    tests/run_all_python_tests.sh
```

Baseline before any edit: `test_syncer_rows.py` = **147 executed** (97 defined;
`VersionsTabTests` / `UpgradeActionTests` re-run `TabbedShellTests`' 25). Any
post-change failure among them is a regression.

`booted()` gains patches for `diff_across_repos`, `read_operation_defaults`,
`plan_push`, `apply_push`, and `Seams` gains `diff`, `unreadable_roots`,
`plan_outcomes` and an `applies` call log (finding 4).

**Pure** (`SettingsMatrixTests`):
1. One marker per provenance; a `conflict` cell renders the **literal** `conflict`
   and never a value. **No `seed` case** — amended contract.
2. Divergence: all-equal not flagged; one differing repo flagged; a `conflict`
   cell flags the row; an `unreadable` column is excluded from the comparison.
3. Row keys `s0…sN` positional, lookup map round-trips, cells ordered by column.
4. An unreadable repo renders `unavailable` in every row.
4b. **Source eligibility** — `sources[i]` is the effective value for `local` /
    `project` / `builtin`, and **`None`** for `conflict`, for an unreadable repo,
    and for `effective is None`. A row where every column is conflict/unreadable
    has `has_source is False`; a mixed row keeps only the eligible entries, in
    column order.

**App-level** (`SettingsTabTests(TabbedShellTests)`):
5. **Render-level** — `#settings` cell text for a fixture matrix equals the
   expected strings **including provenance suffixes** (a `settings_cells()`
   helper mirroring `version_cells`).
6. **Lazy-load negative control** — staying on Branches makes **zero**
   `diff_across_repos` calls; activating `tab_settings` makes exactly **one**.
7. Per-tab gating — `SETTINGS_TAB_ACTIONS` `False` on `tab_branches` /
   `tab_versions`, `True` on `tab_settings`; and `False` on an app with no
   running query (fail-closed).
8. **Duplicate `c`** — the rendered `FooterKey` advertises `recheck_version` on
   Versions and `reload_settings` on Settings.
9. `ok` → `apply_push` called **once** with the chosen layer; `noop` →
   `apply_push` **not called**.
10. **`masked` three-way routing**, spy-asserted: cancel ⇒ no `apply_push`;
    local ⇒ `apply_push(layer='local', clear_mask=False)`; clear+project ⇒
    `apply_push(layer='project', clear_mask=True)`.
11. `rejected` surfaces its **specific reason string**, skips `apply_push` for
    that destination, and a sibling `ok` destination still applies.
12. A destination whose `apply_push` raises is reported by name and the remaining
    destinations still process.
12b. **A destination whose `plan_push` raises** is reported as `planning_failed`,
    no write is attempted for it, the remaining destinations are still planned
    and applied, and the summary screen still opens. Negative control: without
    the per-destination planning boundary the worker dies, no summary appears,
    and later destinations are never considered.
13. `PushPartialError` is reported as "retry to finish" — **not** success, not
    plain failure — and names the masking value.
14. **Per-repo unreadable** — one corrupt repo renders `unavailable` in its column
    while every other repo's cells still render.
14b. **Raced corruption costs only the racer** (at-bound) — the first
    `diff_across_repos` raises, the probe sweep blames repo B, and the *retry*
    raises again with the sweep now blaming repo C: repo A's cells still render,
    B and C read `unavailable`, and the loop terminates. Negative control: the
    earlier blanket-wipe fallback marks A `unavailable` too and fails this test.
14c. **Non-attributable failure blames nobody** (over-bound) — every
    `diff_across_repos` raises while every probe passes: **no** repo is marked
    `unavailable`, the worker returns the `unattributed` reason, the tab surfaces
    the retry notice, and the loop terminates within the stated
    `len(sessions) + 2` attempts (asserted on the call count, so an unbounded
    loop fails rather than hangs).
15. **Single-repo** — with `<2` repos the table renders the one repo's values and
    `push_setting` is `False`.
15b. **Push gating by row state** — `push_setting` is `None` (dimmed, not
    `False`) before the first load completes, on a zero-operation matrix, and on
    a row whose every column is conflict/unreadable; `True` on a row with at
    least one eligible source. And `action_push_setting()` **called directly**
    in each of those states notifies and pushes **no** screen (the tests invoke
    actions directly, bypassing `check_action`).
15c. **Source picker excludes unusable columns** — on a row where the cwd/first
    repo is `conflict` and repo B is `local`, the picker offers **only** B and
    preselects it; `apply_push` is called with B's value. Negative control:
    preselecting index 0 pushes `None`, which `plan_push` turns into
    `rejected(malformed_agent_string)` for every destination — the test asserts
    that reason is **absent**.
15d. **The source repo is not a destination** — with 3 repos and repo B chosen as
    source, the destination `SelectionList` contains exactly A and C and **no**
    entry for B; driving the flow to completion, neither `plan_push` nor
    `apply_push` is ever called with B as `dest_root`, and the summary carries no
    row for B. Negative control: including the source yields a self-targeted
    `noop` row for B, which the test asserts is absent.
15e. **A conflicted / unavailable repo is still a legal destination** — a repo
    ineligible as a *source* appears in the destination list, and pushing to an
    unreadable one surfaces `dest_config_unreadable` rather than being silently
    omitted (pins that destinations are **not** filtered by source-eligibility).
16. **Captured target survives mid-flow mutation** — start a push on operation A,
    then, while a modal is open, move the cursor **and** rebuild
    `_settings_rows_by_key` to point elsewhere; the applied write must still
    target A.
17. **Existing tests inverted, not deleted** —
    `test_versions_pane_holds_the_table_and_settings_the_placeholder` asserts
    `#settings` is a `DataTable` and `#settings_placeholder` is gone;
    `test_down_on_the_settings_placeholder_is_a_noop` becomes "↓ from the bar
    enters the settings table".
18. **Settings modals keep their arrow keys** (closes t1267's substantive scope,
    finding 6) — with `SettingsSourceScreen` / `SettingsDestinationsScreen`
    pushed, ↑/↓ move the RadioSet highlight and the `SelectionList` cursor and
    ←/→ do **not** switch tabs. Mirrors
    `test_arrows_in_an_upgrade_modal_do_not_switch_tabs` (`:958`).

**Prove the suite can fail** — run each mutation individually and confirm a
non-zero exit, then restore by undoing **only** the mutation (never
`git checkout --`, which destroyed an implementation in t1223_3):

| # | Mutation | Must fail |
|---|---|---|
| M1 | drop the `SETTINGS_TAB_ACTIONS` gate | 7 |
| M2 | render the layer value for a `conflict` cell | 1 |
| M3 | make divergence ignore `conflict` cells | 2 |
| M4 | call `apply_push` on `noop` | 9 |
| M5 | route `masked` straight to a project write | 10 |
| M6 | abort the destination loop on the first exception | 11, 12 |
| M7 | remove the shrink-and-retry loop (let `DestConfigUnreadable` propagate) | 14 |
| M7b | restore the blanket `{s.key: … for s in self.sessions}` wipe | 14b |
| M7c | mark every repo unreadable when the sweep blames nobody | 14c |
| M8 | re-resolve the operation from the table in the apply callback | 16 |
| M9 | make the settings load eager | 6 |
| M10 | report `PushPartialError` as success | 13 |
| M11 | treat `conflict` / unreadable cells as eligible sources | 4b, 15c |
| M11b | leave the source repo in the destination list | 15d |
| M11c | filter destinations by source-eligibility | 15e |
| M12 | gate `push_setting` on `multi_repo` alone | 15b |
| M13 | drop the per-destination `plan_push` exception boundary | 12b |

Manual / live coverage: **t1223_7**.

**Commit hygiene:** a concurrent session holds uncommitted changes in
`.aitask-scripts/monitor/*`, `.claude/skills/aitask-shadow/*`,
`aidocs/framework/shadow_agent.md` and `.claude/settings.local.json`; none
overlap this task's paths. Stage only the explicit paths below and verify the
staged **content**, not just the path list.

---

## Risk

### Code-health risk: medium
- `syncer_app.py` is already 1698 lines and load-bearing for daily git sync; this
  adds a third table, a third worker group, a multi-modal write flow and new
  gating. · severity: medium · → mitigation: modals split into
  `syncer/settings_screens.py`, the matrix model kept pure (tests 1–4), a
  separate worker group so the Branches tick is untouched, and t1223_1/t1223_3's
  regression tests left intact; structural follow-up
  `unify_syncer_tab_worker_triples` (**t1298**)
- New impure seams (`diff_across_repos`, `plan_push`, `apply_push`) are reachable
  from three existing tests that already activate `tab_settings` for unrelated
  assertions; an unpatched seam makes the whole suite shell out to the
  developer's real registered repos. · severity: medium · → mitigation: finding
  4 — `booted()` patches all four, with test 6 as the zero-call negative control
- This is the first table in the TUI whose row set is **rebuilt at runtime**, so
  the `_rows_by_key`-is-immutable assumption every other flow relies on no longer
  holds. · severity: medium · → mitigation: frozen `PushTarget` captured at
  action start, with test 16 (cursor **and** row-map both repointed mid-flow)
  and mutation M8
- `P` is live in states where no frozen target exists (before the first lazy
  apply, on a zero-operation matrix, on an all-conflict row), and the suite
  invokes actions directly, bypassing `check_action` — so the binding gate alone
  does not make the action safe. · severity: medium · → mitigation: a row-level
  tri-state gate (`False` for single-repo, `None` for a non-applicable row) plus
  a self-guard inside `action_push_setting`; test 15b drives both the gate and
  the direct call, M12 is the negative control
- The duplicate `c` binding relies on Textual's per-action `check_action`
  fall-through plus `refresh_bindings()` for the footer label. · severity: low ·
  → mitigation: test 8 asserts the rendered `FooterKey`, not `check_action`
- Two existing tests assert the placeholder and the non-focusable pane; deleting
  rather than inverting them would silently drop coverage. · severity: low · →
  mitigation: both named in the plan and rewritten in place (test 17)

### Goal-achievement risk: medium
- The per-repo degradation the AC requires is **not** what the seam provides —
  `diff_across_repos` aborts globally — so it is delivered by a syncer-side
  two-phase fallback. If that is wrong, one corrupt repo blanks the whole tab,
  the exact failure the AC forbids. · severity: medium · → mitigation:
  user-confirmed design, delivered as a **bounded shrink-and-retry loop** so a
  repo that breaks during the probe/re-read window costs only its own column and
  a failure the sweep cannot attribute blames no repo at all; pinned by tests 14
  / 14b / 14c with M7 / M7b / M7c as the negative controls and the attempt count
  asserted against the stated `len(sessions) + 2` bound; layering follow-up
  `cross_repo_settings_skip_unreadable` (**t1297**)
- The push spans up to four modals and two thread workers; an outcome lost
  between phases would report success for a write that never happened, and an
  unhandled exception in either worker drops the summary screen entirely so the
  user cannot tell which destinations were written. · severity: medium · →
  mitigation: the plan-all → prompt → apply → summarize shape carries one outcome
  record per destination end-to-end, with a per-destination exception boundary in
  **both** the planning and the apply phase; tests 9–13 cover every branch, M6 /
  M10 / M13 are the negative controls
- An unusable cell (`conflict`, or an unreadable repo) offered as a push source
  would be pushed as `None`, which `plan_push` reports as
  `rejected(malformed_agent_string)` — blaming the value the user picked rather
  than saying no value existed, for every destination at once. · severity:
  medium · → mitigation: eligibility derived once in the pure model
  (`SettingsRow.sources`), the picker offering only eligible repos and
  preselecting the first eligible one, and `P` gated off rows with no source;
  tests 4b / 15b / 15c, mutations M11 / M12. The dual of the same trap is the
  destination list: the source repo is removed at construction time (the AC's
  "the **other** repos"), since leaving it in guarantees a self-targeted `noop`
  row that reads as a defect — while repos ineligible as *sources* deliberately
  stay selectable as destinations; tests 15d / 15e, mutations M11b / M11c
- `apply_push` gives per-destination atomicity only, so a multi-destination push
  failing partway leaves earlier destinations applied. · severity: low · →
  mitigation: declared bound; the per-destination summary is the honest surface,
  as t1223_4's sibling notes specify
- The AC's "highlighted cell" source default is unreachable under the row cursor
  t1266 forces. · severity: low · → mitigation: user-confirmed AC deviation
  (explicit source-repo step), written back into the task file in the same commit
- The push writes another repo's git-tracked project layer and, by TUI
  convention, must not commit it — so the change is uncommitted, and invisible to
  `git status` in a destination whose `aitasks/` is a symlink onto an
  `aitask-data` branch. · severity: low · → mitigation: stated in the layer
  prompt and the result summary; the user-facing documentation is owned by
  t1223_6

### Planned mitigations
- timing: after | created: t1297 | name: cross_repo_settings_skip_unreadable | type: enhancement | priority: medium | effort: low | addresses: goal-achievement risk 1 (per-repo degradation implemented in the syncer rather than the seam) | desc: Add diff_across_repos(roots, *, skip_unreadable=True) -> (matrix, unreadable) to cross_repo_settings and delete the syncer-side two-phase fallback.
- timing: after | created: t1298 | name: unify_syncer_tab_worker_triples | type: refactor | priority: low | effort: medium | addresses: code-health risk 1 (syncer_app.py growth; three hand-copied worker triples) | desc: Extract the per-tab _gen/_active/_pending triple and its request/apply/finish quartet into one shared helper so a further tab adds no new copy.
- timing: after | created: t1299 | name: document_render_level_verification_rule | type: documentation | priority: low | effort: low | addresses: verified doc gap — two task files cite a render-level verification rule that does not exist in aidocs/framework | desc: Add the render-level TUI verification rule (assert widget.render().plain, prefer markup=False) to aidocs/framework/tui_conventions.md.

---

## Files

- `.aitask-scripts/syncer/syncer_app.py` — `SettingsRow` + `build_settings_matrix`,
  the `#settings` table replacing the placeholder, `SETTINGS_TAB_ACTIONS` +
  gating, `TAB_LIST_IDS` / `_active_list` / `action_nav_down` updates, the lazy
  `syncer-settings` worker with the two-phase fallback, `PushTarget`, and the
  `action_push_setting` → source → destinations → layer → plan → masked → apply →
  summary chain.
- **New:** `.aitask-scripts/syncer/settings_screens.py` — five Cancel-focused
  modals.
- `tests/test_syncer_rows.py` — extended `booted()` / `Seams`, `SettingsMatrixTests`,
  `SettingsTabTests`, and the two inverted placeholder tests.
- `aitasks/t1223/t1223_5_settings_tab_and_push_action.md` — the two AC deviations
  (findings 1 and 2), the corrected `python3` verification command, and the
  bidirectional t1267 coordination note.
- `aitasks/t1267_syncer_settings_tab_nav_coordination.md` — the reverse pointer
  recording that this task landed the `TAB_LIST_IDS` fix and the arrow test
  (finding 6). **Not closed** — left for the user to verify and dispose of.

Task/plan files are committed with `./ait git`, separately from code.

## Post-Review Changes

### Change Request 1 (2026-07-28 14:05)

- **Requested by user:** Three UX defects in the push dialogs. (a) The lists only
  responded to ↑/↓ *after clicking into them*. (b) Enter should act as the OK
  button and advance one step. (c) Esc should go back one step in the dialog
  series rather than abandoning the push.

- **Verified:** (a) CONFIRMED and root-caused — every dialog focused the Cancel
  Button on mount (inherited from `upgrade_screens`, where a single destructive
  confirm makes that right), so the arrows landed on a widget that ignores them.
  (b) and (c) were simply not implemented: Esc dismissed `None`, which aborted
  the whole flow from any step.

- **Changes made:**
  1. `settings_screens.py` — reshaped into a wizard around a new
     `_WizardScreen` base: `escape` → back, and `enter` → advance bound with
     `priority=True` so it wins over a focused `RadioSet`/`SelectionList`. Every
     choice step now focuses its **choice widget** on mount. Steps 2–3 dismiss a
     `BACK` sentinel (distinct from `None`, which still means "cancel the
     push"). The layer step became a `RadioSet` with **no** option pressed, so
     Enter on an untouched dialog reports "Choose a layer" instead of advancing
     — the no-default contract survives the wizard model. The masked step
     likewise became an unpressed `RadioSet`; its Esc means *skip this
     destination*, since the masked prompts are drained one destination at a
     time after planning and there is no coherent earlier step mid-queue.
  2. `syncer_app.py` — `_pick_source` / `_choose_destinations` / `_choose_layer`
     became mutually recursive on the `BACK` sentinel, each re-pushing the
     previous dialog **with the earlier choice preselected** (source stays
     picked, destination ticks stay ticked). Added `_source_value` so the value
     lookup is a named helper rather than an inline `dict(zip(...))`.
  3. **Measured rather than assumed:** a probe confirmed that in this Textual
     version `↑`/`↓` move a `RadioSet`'s highlight but leave `pressed_index`
     unchanged — **Space** is what commits. Every dialog's hint line therefore
     reads `↑/↓ move · Space select · Enter continue · Esc back`, and the
     measurement is recorded in a comment so a future reader does not "fix" it.
  4. Four keyboard-driven tests (real keypresses, no programmatic `dismiss`):
     focus-on-mount, Enter-advances/Esc-steps-back-with-state-preserved,
     blind-Enter-on-the-layer-step, Enter-with-nothing-ticked. Mutations
     M14–M17 added and each confirmed to fail.

- **Files affected:** `.aitask-scripts/syncer/settings_screens.py`,
  `.aitask-scripts/syncer/syncer_app.py`, `tests/test_syncer_rows.py`.

### Change Request 2 (2026-07-28 14:40)

- **Requested by user:** Why can't the lowercase `p` shortcut open the
  push-settings wizard?

- **Verified:** No blocker. `p` (git-push) is in `BRANCH_TAB_ACTIONS`, so on the
  Settings tab `check_action` returns `False` — a *drop*, not the ref gate's
  `None` *dim* — and Textual falls through to the next binding for that key.
  That is the same mechanism already carrying the shared `c`
  (`recheck_version` / `reload_settings`). The original `P` was a weak analogy
  to `U`: `U` is uppercase because `u` means Pull **on the same tab**, whereas
  `p` is inert on Settings and "push" is the correct verb for both.

- **Changes made:** `Binding("P", "push_setting", …)` → `Binding("p", …)` with
  the rationale rewritten in place. `test_footer_relabels_the_shared_c_key_per_tab`
  widened to `…_shared_keys_per_tab` (both `p` and `c`), plus a new
  **real-keypress** test proving `p` reaches `action_push` on Branches without
  opening the wizard, and opens `SettingsSourceScreen` on Settings without
  calling `action_push`. Mutation M18 (revert to `P`) confirmed to fail it.

- **Files affected:** `.aitask-scripts/syncer/syncer_app.py`,
  `tests/test_syncer_rows.py`.

## Out of scope

Any setting other than the default code agent per operation; **any change to
`cross_repo_settings.py`** (value logic belongs to t1223_4); committing or
pushing the destination's config; user-facing documentation (t1223_6); live
end-to-end verification (t1223_7). No change to the Branches or Versions tabs'
behavior.

## Final Implementation Notes

- **Actual work done:** The planned shape, across three code/test files.
  - **New** `.aitask-scripts/syncer/settings_screens.py` (~440): `BACK` sentinel,
    the `_WizardScreen` base (Enter→advance `priority=True`, Esc→back, inline
    `_error`), and five screens — `SettingsSourceScreen`,
    `SettingsDestinationsScreen`, `SettingsLayerScreen`, `SettingsMaskedScreen`,
    `SettingsPushResultScreen`.
  - `.aitask-scripts/syncer/syncer_app.py` (+~700): `SettingsRow`,
    `settings_cell` / `settings_source` / `build_settings_matrix` (pure),
    `PushTarget` with `source_options` / `destinations_excluding`; the
    `#settings` DataTable replacing the placeholder; `SETTINGS_TAB_ACTIONS` plus
    the tab gate *and* the row-level `push_setting` gate; `TAB_LIST_IDS` entry;
    the lazy `syncer-settings` worker with `_read_settings_matrix`'s bounded
    shrink-and-retry, `_on_settings_error`, `_apply_settings`,
    `_update_settings_table`, `_selected_settings_row`, `_capture_push_target`;
    the `_pick_source` → `_choose_destinations` → `_choose_layer` →
    `_push_plan_worker` / `_plan_each` → `_resolve_masked` →
    `_push_apply_worker` → `_report_pushes` chain. Bindings `p` (Push setting)
    and `c` (Reload), both shared with an existing key.
  - `tests/test_syncer_rows.py` (+~1000): 147 → **211** tests
    (`SettingsMatrixTests`, `PushTargetTests`, `SettingsTabTests`, plus the two
    inverted placeholder tests and the extended `Seams`/`booted()`).

- **Deviations from plan:** Two designed in and user-confirmed before
  implementation (the explicit source step replacing "the highlighted cell", and
  the syncer-side degradation replacing "catch `DestConfigUnreadable` per repo"),
  both written back into the task file. Two more came out of review — see
  Post-Review Changes. One implementation choice: the plan sketched a single
  fallback for a corrupt repo; it shipped as a **bounded shrink-and-retry loop**
  because one extra attempt cannot cover a repo that breaks between the probe
  and the retry.

- **Issues encountered:**
  1. *A mutation hung instead of failing, and that was a real bug in my code.*
     M7 (remove the degradation fallback) made the test sit for the full 600 s
     timeout. Cause: an exception escaping `_settings_worker` never reached
     `_finish_settings`, so `_settings_active` stayed `True`, every later
     request parked in the coalescer's pending slot, and `settle()` waited
     forever — `c` would have been silently dead for the rest of the session.
     This is the exact hazard `_refresh_worker` documents for cancellation
     ("or `_refresh_active` stays stuck true and refreshing halts forever") and
     my worker lacked the house `_on_*_error` guard. Fixed, plus an outer
     boundary on the plan worker so choosing a layer can never end in silence;
     pinned by `test_a_worker_level_failure_still_unsticks_the_refresh_flag`.
     M7 now fails cleanly in 4 s. **A hang is not a pass — the driver was also
     changed to time out at 150 s and report `HANGS (detected)` distinctly,
     because the 600 s hang blocked the remaining eleven mutations.**
  2. *`RadioSet` arrows do not select.* The keyboard work was designed against a
     comment in an existing test; a direct probe showed `↑`/`↓` move the
     highlight but leave `pressed_index` alone, and **Space** commits. The hint
     text says so and the measurement is recorded in a comment.
  3. *Test ordering slip.* New numbered verification items were inserted out of
     order twice (15d/15e before 15c, 18 before 17) and had to be re-ordered.

- **Key decisions:**
  - **Source and destination eligibility are different questions.** A
    `conflict` repo cannot be a source (its layers and resolver disagree, so its
    value is not coherent to copy) but is a legitimate — arguably the most
    valuable — *destination*. `PushTarget` therefore carries every repo plus a
    parallel `sources` tuple instead of one pre-filtered list. An early draft
    filtered once and would have made conflicted repos unfixable.
  - **The source is excluded from destinations at construction time**, not
    filtered later: leaving it in guarantees a self-targeted `noop` row that
    reads as a defect.
  - **`plan_push` does not raise on an unusable value** — it matches
    `value or ""` and returns `malformed_agent_string` for *every* destination,
    blaming the user's choice rather than reporting that none existed. That is
    why eligibility is computed in the pure model and the key is gated off rows
    with no source.
  - **A binding gate is not the action's guard.** `check_action` gates the key;
    the suite (and the board) invoke `action_*` directly, so
    `action_push_setting` re-checks and notifies.
  - **Exception boundaries on every phase, not just the last.** The apply loop's
    per-destination guard is worthless if the preceding planning worker can die
    whole — the summary would never open and later destinations would be
    silently unconsidered.
  - **Blame only what you established.** A degradation failure the probe cannot
    attribute marks *no* repo unreadable; it surfaces as a tab-level notice.
  - **Sharing `p` and `c` beats inventing uppercase variants.** The tab gate's
    `False` (drop) — not the ref gate's `None` (dim) — is what makes Textual
    fall through to the second binding, so the shared keys are pinned by a real
    keypress test rather than by `check_action` alone.
  - **22 falsifiability mutations were run individually**; each made the suite
    exit non-zero, and the tree was restored by reversing the exact edit from an
    in-memory copy — never `git checkout --`, which destroyed an implementation
    in t1223_3 and would here have discarded a concurrent session's work.

- **Upstream defects identified:**
  - `aidocs/framework/tui_conventions.md` — the file contains **no** render-level
    verification rule, despite this task file and p1223_5's predecessor both
    citing "the render-level verification rule (assert `widget.render().plain`,
    prefer `markup=False`)" in it as required reading. The convention exists only
    as practice in `tests/test_syncer_rows.py`. Future planners are pointed at
    something that is not there; covered by the confirmed follow-up
    `document_render_level_verification_rule` (**t1299**).

- **Notes for sibling tasks:**
  - **t1223_6** should document: the Settings tab's provenance markers
    (`(local)` / bare / `(default)` / `conflict` / `unavailable`) and the
    **three-tier** chain with `seed/` as a setup-time source only; the shared
    `p` / `c` keys and their per-tab meaning; the wizard's
    `↑/↓ move · Space select · Enter continue · Esc back` model; that the layer
    is always asked with no default; and — importantly — that a push **writes
    but does not commit** the destination's config, which on a repo whose
    `aitasks/` is a symlink onto an `aitask-data` branch is invisible to
    `git status` in its main checkout.
  - **t1267's substantive scope is satisfied** by this task (`TAB_LIST_IDS`
    entry + `test_arrows_in_a_settings_modal_do_not_switch_tabs`); it is left
    open for verification and disposal, with a note recorded in its file.
  - Any new syncer thread worker must route its failure through an
    `_on_<x>_error` that calls `_finish_<x>()`. Without it the coalescer's
    `_<x>_active` flag sticks and that tab's refresh dies silently for the rest
    of the session.
  - `settings_screens._WizardScreen` is the reusable multi-step-modal pattern
    (Enter/Esc, `BACK` sentinel, caller re-pushes the previous step with the
    earlier choice preselected).
