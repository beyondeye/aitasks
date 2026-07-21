---
Task: t1186_4_allowlist_picker_ui.md
Parent Task: aitasks/t1186_chatlink_wizard_allowlist_live_pickers.md
Sibling Tasks: aitasks/t1186/t1186_5_manual_verification_chatlink_wizard_allowlist_live_pickers.md
Archived Sibling Plans: aiplans/archived/p1186/p1186_1_authorization_modes.md, aiplans/archived/p1186/p1186_2_discord_fetch_surface.md, aiplans/archived/p1186/p1186_3_wizard_step_reorder.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-07-21 12:31
---

# p1186_4 — Allowlist picker UI (mode selectors + SelectionList pickers + validation)

## Context

Final implementation slice of t1186 ("chatlink wizard allowlist live pickers").
The reporter's complaint: the wizard forces you to hand-type Discord snowflake
IDs for who may open a bug report, with no way to see the channel's members,
and no explicit control over the deny-by-default posture.

Three siblings have landed the substrate; **this task is the only consumer**:

- **t1186_1** — `ChatlinkConfig` now carries six authorization keys
  (`user_authorization_mode`, `role_authorization_mode`, `allowed_user_ids`,
  `denied_user_ids`, `allowed_role_ids`, `denied_role_ids`) and
  `policy.effective_posture(cfg) -> Posture(kind, degenerate_dimensions)`
  classifies `deny_all` / `open_members` / `restricted`
  (`.aitask-scripts/chatlink/policy.py:113-139`, `config.py:44-48, 80-89`).
  `preflight._authorization_results()` (`preflight.py:157-226`) is the existing
  renderer of that posture — its copy is the wording precedent, and its
  `authorization_<dim>_ignored` rows (`:205-225`) are the precedent for
  surfacing a populated-but-inactive list.
- **t1186_2** — `allowlist_fetch.run_allowlist_fetch(token, workspace_id,
  conversation_id, thread_id, *, timeout, connector)` returns an
  `AllowlistFetchResult` with ready-made `(id, label)` pairs, per-stage
  sanitized `members_error` / `roles_error`, and `members_truncated`
  (`allowlist_fetch.py:83-171`). Plus headless `dedupe_ids` /
  `invalid_snowflakes` (`:67-80`).
- **t1186_3** — `_STEPS` (`wizard.py:723-724`) now orders intake → token →
  live check → **allowlist** → deny/repo → ceilings → summary, numbering is
  derived, and `make_step()` (`:694-700`) dispatches seams off the class
  attribute `needs_seams`.

The wizard is the **only** surface still stuck on the old model: `initial_state`
(`wizard.py:104-129`) and `build_edits` (`:132-151`) know only
`allowed_user_ids` / `allowed_role_ids`, and `AllowlistScreen` (`:272-304`) is
two bare `Input`s with zero validation. Outcome of this task: the allowlist step
becomes a real authorization step — per-dimension mode selectors, live
Discord-backed multi-select pickers, manual entry preserved on every failure
path, and config-time ID validation.

## Pinned screen state model (from the task file — implement exactly)

`AllowlistScreen` owns four working lists (`allowed_user_ids`,
`denied_user_ids`, `allowed_role_ids`, `denied_role_ids`) plus the two modes.
Each ID `Input` always displays/edits exactly the **active-mode** list of its
dimension and relabels with the mode.

- **Mode toggle**: parse the Input into the OUTGOING mode's list, then load the
  Input from the INCOMING mode's list. Both lists survive round-trip toggling;
  nothing is ever cleared.
- **Fetched SelectionLists**: selected-state is recomputed from the newly active
  list on every toggle; the selection-change handler reads the dimension's mode
  **at event time** so a selection can never write to an inactive list.
- **Filtering** only narrows visible rows; it never mutates selection or lists.
- `_accept()` parses both Inputs into their active lists and writes all four
  lists + both modes into the shared wizard state.

## Verified framework facts (drive steps 3–5)

Established by reading current source during planning — the design depends on
these, so they are recorded rather than assumed:

- `SelectionList._make_selection` calls `_select(value)` for every option with
  `initial_state=True`, which calls `_message_changed()` → **`post_message`**.
  `post_message` *queues*; the handler runs after the calling method returns.
  **A synchronous "am I rebuilding" boolean is therefore not a valid guard.**
- `SelectionList.clear_options()` clears `_selected` **without** posting.
- `MessagePump.prevent(*types)` pushes onto a **ContextVar** stack consulted at
  the post site, so it suppresses messages a *different* widget posts inside the
  block. This is the mechanism Textual's own `_apply_to_all` uses.
- `SelectedChanged` carries only `selection_list`; `.selected` is read live at
  handler time, so it always reflects current widget state.
- `_WizardStep._on_back` (`wizard.py:225-227`) dismisses with `BACK` **without**
  calling `_accept()`, and `make_step()` builds a **fresh screen instance** on
  every visit — so anything not written into the shared `state` dict is lost on
  Back.
- `_WizardStep.on_input_submitted` (`:218-219`) routes Enter from **any** Input
  to `_accept()`.
- The effective fetch token is `state["token"] or seams.token_reader()`
  (`:432`), and `TokenScreen._accept` (`:388`) **reassigns** `state["token"]` on
  every forward pass — so the token, like the intake ids, can change across a
  Back excursion.

## Pinned invariant (drives steps 3–4)

> **At every moment, each picker's selected set is exactly
> `active_list ∩ visible_rows`, and the Input is the single source of truth for
> the active list.**

Without this, "a visible row is unselected" is ambiguous — it could mean *the
user deselected it* or *the user typed it after the last rebuild and the picker
never caught up* — and the write-back would silently drop the typed id. Steps 3
and 4 maintain the invariant on all four mutation paths (typing, selecting,
filtering, mode toggle); the write-back logic is only sound because of it.

## Steps

### 1. Seam plumbing (+ one shared base-class hook)

- `wizard.py`: add `allowlist_fetch_runner: Callable | None = None` to
  `WizardSeams` (`:75-86`); `resolve_seams()` (`:89-101`) defaults it to
  `allowlist_fetch.run_allowlist_fetch`. Extend the module import (`:51-52`) to
  `from . import allowlist_fetch, config, config_write, live_check, paths,
  policy, preflight, preflight_render`. (No new import burden: `live_check`
  already pulls `chat.model`; the guard tests only assert the *headless* modules
  stay Textual-free — one-directional.)
- `_WizardStep`: add a `_before_back()` no-op hook, called by `_on_back`
  (`:225-227`) immediately before `self.dismiss(BACK)`. Keeping `_on_back`
  itself intact preserves its `@on(Button.Pressed, "#btn_wiz_back")`
  registration (overriding a decorated handler in a subclass would drop it).
  Default is a no-op, so the other six screens are behaviourally unchanged.
- `chatlink_app.py`: add `allowlist_fetch_runner=None` to `__init__`
  (`:109-112`), store it beside `self._live_runner` (`:129`), and pass it into
  `WizardSeams` in `action_wizard` (`:167-175`).

### 2. State round-trip (six keys)

- `initial_state()` (`:104-129`): add `user_authorization_mode` /
  `role_authorization_mode` (from `cfg.<same>`, already defaulted to
  `config.DEFAULT_AUTHORIZATION_MODE`) and `denied_user_ids` /
  `denied_role_ids` (`list(cfg.<same>)`).
- `build_edits()` (`:132-151`): emit all six. Plain lists / plain strings — no
  `DELETE` sentinel (unlike `repo_name`, an empty list is a meaningful value and
  the inactive list must be preserved verbatim, never cleared).
- **Transient fetch cache — keyed to its inputs.** `AllowlistScreen` stashes its
  fetch results in the shared state dict so Back does not force a 30s refetch.
  The cache is **not** a bare row list: rows fetched against one Discord context
  must never be shown after the operator edits that context on an earlier step.
  Store

  ```python
  state["_fetched"] = {
      "key": <fetch key>,
      "members": [...], "roles": [...],
      # provenance: ids currently in this dimension's lists that came from
      # THIS picker — the set that must not survive a context change.
      "origin_user": [...], "origin_role": [...],
  }
  ```

  with `<fetch key> = (provider, workspace_id, conversation_id, thread_id,
  token_fingerprint)` — every argument `run_allowlist_fetch` actually receives.
  `token_fingerprint = sha256(effective_token.encode()).hexdigest()[:12]`: a
  one-way digest, computed only at fetch time, never rendered — and strictly
  less sensitive than the raw `state["token"]` already sitting in the same dict.
  Pin with a test that the raw token never appears in the cache key.

  `build_edits` enumerates its keys explicitly (never `**state`), so
  underscore-prefixed keys can never reach the config file; document that in its
  docstring and pin it with a test.

### 3. `AllowlistScreen` rebuild

`needs_seams = True`; `step_name = "Who may open a bug report"` (no `Step N/7`
literal — numbering is derived). New imports: `SelectionList` from
`textual.widgets`, `Selection` from `textual.widgets.selection_list`.

Class-level dimension table (single source; the two dimensions are otherwise
identical code paths):

```python
#: (dim key, mode state key, mode field id, input id, label id, list id, noun)
_DIMENSIONS = (
    ("user", "user_authorization_mode", "wiz_user_mode", "wiz_user_ids",
     "wiz_user_ids_label", "wiz_member_list", "user"),
    ("role", "role_authorization_mode", "wiz_role_mode", "wiz_role_ids",
     "wiz_role_ids_label", "wiz_role_list", "role"),
)
```

`__init__` seeds working state from `self.state`:
`self._working = {"allowed_user_ids": [...], "denied_user_ids": [...],
"allowed_role_ids": [...], "denied_role_ids": [...]}`,
`self._modes = {"user": ..., "role": ...}`,
`self._visible = {"user": [], "role": []}`,
`self._echo = {"user": set(), "role": set()}`,
`self._fetch_running = False`, `self._fetch_gen = 0`,
`self._warned_signature = None`.

**Cache revalidation** (`__init__`): recompute the current fetch key and adopt
`state["_fetched"]` **only** on an exact match. On a mismatch, discard both the
rows *and* the ids that came from those rows:

```python
self._fetched = {"user": [], "role": []}
removed = {}
for dim in ("user", "role"):
    origin = set(stale.get(f"origin_{dim}", ()))
    for key in (f"allowed_{dim}_ids", f"denied_{dim}_ids"):
        gone = [i for i in self._working[key] if i in origin]
        if gone:
            removed.setdefault(dim, []).extend(gone)
            self._working[key] = [i for i in self._working[key]
                                  if i not in origin]
```

**Why removal, not retention.** A picker-selected id is scoped to the context it
was fetched from — Discord **role ids are guild-scoped**, so a role chosen under
the old `workspace_id` is not stale-but-plausible, it is meaningless; a member id
is global but its channel membership is not. `invalid_snowflakes` cannot catch
either (both are well-formed), and no later check can. So carrying them forward
would let a wrong authorization be saved with nothing able to detect it.

Removal is also the **fail-closed** direction, and it composes with an existing
guard: if stripping them empties an allowlist, step 5's posture check classifies
the result `deny_all` and warns on Next. The failure mode of removing too much is
therefore loud; the failure mode of keeping too much is silent.

**Manually typed ids are kept** — they are the operator's own assertion, not a
click on a row that no longer exists. Provenance is recorded at commit time (see
`_commit_state`), so the two are distinguishable. In the ambiguous case (an id
both typed *and* present in the fetched set) the id counts as picker-origin and
is removed — over-removing is the fail-closed side, and the notice names it so
it can be re-added in one keystroke.

**The notice names every removed id** (pending, rendered on mount, and it
persists until the operator acts — it is not a transient flash):

```
intake channel or token changed — discarded the fetched rows and removed
2 id(s) selected from the previous context: 111, 222.
Manually typed ids were kept. Press "Fetch from Discord" to reload.
```

with the shorter "…previously fetched rows discarded." form when nothing was
removed. This is what makes the discard a reviewed state rather than a silent
mutation, and it is required, not cosmetic — pinned by a test.

Helper: `_active_key(dim, mode) -> f"{'allowed' if mode == 'allowlist' else 'denied'}_{dim}_ids"`.

`body()` per dimension: a `CycleField("<noun> authorization mode",
list(config.AUTHORIZATION_MODES), mode, mode_state_key, id=mode_field_id)`, a
`Label` (id `wiz_<dim>_ids_label`) reading `"Allowed user ids (comma/space
separated):"` / `"Denied ..."`, the `Input` prefilled from the active list, and
a `Static` (id `wiz_<dim>_inactive`) that renders the **inactive-list
disclosure** when that list is non-empty (see step 6 for the wording; empty
string otherwise). Then the shared picker block:
`Button("Fetch from Discord", id="btn_wiz_fetch", disabled=provider != "discord")`,
a status `Static` (`#wiz_fetch_status`, `markup=False`), a filter `Input`
(`#wiz_fetch_filter`), and the two `SelectionList[str]`s. Picker widgets start
with `display = False` (revealed once results exist — including results restored
from the transient cache on re-entry); give the lists a fixed CSS height (~8
rows) since the dialog already has `max-height: 90%` + `overflow-y: auto`
(`_WizardStep.DEFAULT_CSS`, `:162-176`).

**Mode toggle** — `@on(CycleField.Changed)`, dispatch on `event.field.id`:

```python
outgoing, incoming = self._modes[dim], event.value
if incoming == outgoing:
    return
self._working[self._active_key(dim, outgoing)] = \
    allowlist_fetch.dedupe_ids(self._parse_ids(self._input_value(input_id)))
self._modes[dim] = incoming
self.query_one(f"#{input_id}", Input).value = \
    ", ".join(self._working[self._active_key(dim, incoming)])
self.query_one(f"#{label_id}", Label).update(<relabelled text>)
self._render_inactive(dim)
self._rebuild_list(dim)      # recompute selected-state from the new active list
```

**`_rebuild_list(dim)`** — the *single* place options are (re)built; used by
fetch, filter, and mode toggle. Two independent guards, because the framework
posts selection messages asynchronously:

```python
self._sync_active(dim)          # Input → _working, FIRST (see below)
sl = self.query_one(f"#{list_id}", SelectionList)
active = self._working[self._active_key(dim, self._modes[dim])]
pat = self._input_value("wiz_fetch_filter").casefold()
visible = [(i, name) for i, name in self._fetched[dim]
           if not pat or pat in name.casefold() or pat in i]
self._visible[dim] = [i for i, _ in visible]
selected = {i for i, _ in visible if i in active}
self._echo[dim] = selected                  # durable: what a rebuild echo looks like
with sl.prevent(SelectionList.SelectedChanged):   # suppress at the post site
    sl.clear_options()
    sl.add_options(Selection(f"{name} ({i})", value=i,
                             initial_state=i in active) for i, name in visible)
```

- `prevent` stops the echo **at the post site** (ContextVar-scoped, so it covers
  the messages `SelectionList` posts inside the block — verified above).
- `self._echo[dim]` is the **timing-independent** backstop: even if a message
  escaped, the handler below compares the live selection against the set the
  rebuild intended and treats an exact match as a no-op echo. This is correct
  regardless of when the message is delivered, and it is also trivially safe if
  a real user action happens to reproduce that set (the resulting state is
  identical to what would be written).

**Selection write-back** — `@on(SelectionList.SelectedChanged)`:

```python
dim = <from event.selection_list.id>
live = set(event.selection_list.selected)
if live == self._echo[dim]:
    return                                    # rebuild echo, not a user action
key = self._active_key(dim, self._modes[dim])  # mode read AT EVENT TIME
visible = set(self._visible[dim])
typed = self._parse_ids(self._input_value(input_id))
preserved = [i for i in typed if i not in visible]  # manual ids + hidden-selected
new = allowlist_fetch.dedupe_ids(
    preserved + [i for i in self._visible[dim] if i in live])
self._echo[dim] = live
self._working[key] = new
self.query_one(f"#{input_id}", Input).value = ", ".join(new)
self._warned_signature = None                  # posture may have changed
```

> `preserved` is computed against the **visible** set (not the whole fetched
> set) so filtering a selected row out of view cannot silently drop its id.

**Typing must keep the invariant** — `_rebuild_list` running `_sync_active`
first is *necessary but not sufficient*: the operator can type an id **after**
the last rebuild and click a row with no rebuild in between, so the picker would
still show that id's row unselected and the write-back would drop it. Maintain
the invariant continuously instead, via `@on(Input.Changed, "#wiz_user_ids")` /
`"#wiz_role_ids"`:

```python
def _sync_active(self, dim) -> None:
    """Input → _working for the dimension's ACTIVE list (single writer)."""
    self._working[self._active_key(dim, self._modes[dim])] = \
        allowlist_fetch.dedupe_ids(self._parse_ids(self._input_value(input_id)))

def _sync_selection_from_input(self, dim) -> None:
    """Reconcile the picker's ticks with the Input. Idempotent by design."""
    self._sync_active(dim)
    active = set(self._working[self._active_key(dim, self._modes[dim])])
    sl = self.query_one(f"#{list_id}", SelectionList)
    target = {i for i in self._visible[dim] if i in active}
    current = set(sl.selected)
    if target == current:
        return
    with sl.prevent(SelectionList.SelectedChanged):
        for i in target - current:
            sl.select(i)
        for i in current - target:
            sl.deselect(i)
    self._echo[dim] = target
```

This is a diff against the existing options (no `clear_options` / re-add), so it
costs O(changed rows) and causes no scroll or highlight churn on each keystroke.
Because it computes a *target* and diffs, it is idempotent — the `Input.Changed`
that Textual posts when the mode toggle assigns `Input.value` programmatically
is a harmless no-op, so no suppression flag is needed there.

With the invariant held, "a visible row is unselected" unambiguously means *the
operator deselected it*, which is exactly what the write-back's
`preserved = typed ids not in visible` relies on.

**Filter** — `@on(Input.Changed, "#wiz_fetch_filter")` → `_rebuild_list` for
both dimensions. Filtering changes only `_visible` and which option rows exist;
it never writes an Input, and its `_sync_active` call is a no-op re-parse of
unchanged text.

**Enter in the filter field** — override `on_input_submitted` so only the real
field Inputs advance the step:

```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    if event.input.id == "wiz_fetch_filter":
        event.stop()          # narrowing rows must never advance the wizard
        return
    super().on_input_submitted(event)
```

**Back must not discard picker work** — override the new `_before_back()` hook
to persist working state *without validation*:

```python
def _before_back(self) -> None:
    self._commit_state()      # same writer _accept() uses, minus validation
```

Safe because nothing reaches disk before `SummaryScreen._do_save()` and the step
chain is linear: `SummaryScreen` is reachable **only** by passing forward
through `AllowlistScreen._accept()`, so validation is still enforced on every
path that can save. `_commit_state()` writes all four lists + both modes, and —
only when a fetch actually succeeded (no `_fetch_key` ⇒ no cache entry) — stores
the cache so re-entry restores the pickers without a refetch, for the same
context only. It computes provenance at that moment, from the fetched sets:

```python
fetched_ids = {dim: {i for i, _name in self._fetched[dim]}
               for dim in ("user", "role")}
state["_fetched"] = {
    "key": self._fetch_key,
    "members": self._fetched["user"], "roles": self._fetched["role"],
    **{f"origin_{dim}": sorted(
           (set(self._working[f"allowed_{dim}_ids"])
            | set(self._working[f"denied_{dim}_ids"])) & fetched_ids[dim])
       for dim in ("user", "role")},
}
```

### 4. Fetch worker

`@on(Button.Pressed, "#btn_wiz_fetch")`, copying `LiveCheckScreen`'s worker
pattern verbatim (`wizard.py:428-472`):

- Guard `self._fetch_running` and `provider != "discord"`.
- `token = self.state["token"] or self.seams.token_reader()`; if falsy →
  `self._error("no token to fetch with — enter one on the token step "
  "(manual entry still works)")` and return.
- Bump `self._fetch_gen`, capture `gen`, snapshot runner + ids into locals,
  compute `self._pending_key` (the step-2 fetch key, from those same snapshotted
  values), render `"… fetching members and roles (up to 30s)"` from
  `allowlist_fetch.FETCH_TIMEOUT_S`.
- `def work()` is **pure** (no widget access): calls the runner in `try/except`
  → `result` or `None`, then
  `self.app.call_from_thread(self._apply_fetch, gen, result)`.
- `_apply_fetch(gen, result)` early-returns on `gen != self._fetch_gen or not
  self.is_attached`. On `None` → advisory status line, picker stays hidden,
  manual entry unaffected. Otherwise store `self._fetched["user"] =
  result.members`, `self._fetched["role"] = result.roles`, adopt
  `self._fetch_key = self._pending_key` (the key snapshotted when *this* run
  started, never recomputed from possibly-changed state), reveal the picker
  widgets, `_rebuild_list` both dims, and compose the status line from
  `members_error` / `roles_error` (sanitized strings passed through as-is) plus
  a `f"showing first {allowlist_fetch.MAX_MEMBERS} members"` note when
  `result.members_truncated`.

A failed fetch **never** blocks Next.

### 5. `_accept()` — validation + posture warning

1. Parse both Inputs into their active working lists.
2. `dedupe_ids` **all four** lists (inactive ones too — cheap and idempotent).
3. If `state["provider"] == "discord"`: `bad = invalid_snowflakes(active_user +
   active_role)`. Non-empty → `self._error(f"not valid Discord ids: {', '.join(bad)}")`
   and **return without advancing** (hard block; a typo'd id would otherwise
   silently never match). Non-Discord providers: dedupe only.

   > **Explicit scope decision:** validation covers only the two **active**
   > lists — the ones the Inputs currently display. A preserved inactive list
   > may legitimately carry ids the user cannot see or fix on this screen, and
   > hard-blocking on an invisible field is unactionable. Switching the mode
   > brings that list into view and into validation, and step 6's disclosure
   > makes a non-empty inactive list visible either way.

4. **Posture warning keyed to the exact configuration warned about.** A bare
   one-shot boolean is wrong: warn on `deny_all`, then switch both dimensions to
   `denylist` with empty denied lists, and a second Next would silently accept
   `open_members` — a *different* risky posture the user never saw. Instead
   compute a signature of the values that determine the posture and require the
   confirming press to match it exactly:

```python
signature = (self._modes["user"], self._modes["role"],
             tuple(self._working["allowed_user_ids"]),
             tuple(self._working["allowed_role_ids"]),
             tuple(self._working["denied_user_ids"]),
             tuple(self._working["denied_role_ids"]))
posture = policy.effective_posture(config.ChatlinkConfig(
    user_authorization_mode=self._modes["user"],
    role_authorization_mode=self._modes["role"],
    allowed_user_ids=self._working["allowed_user_ids"],
    allowed_role_ids=self._working["allowed_role_ids"],
    denied_user_ids=self._working["denied_user_ids"],
    denied_role_ids=self._working["denied_role_ids"]))
if posture.kind != "restricted" and self._warned_signature != signature:
    self._warned_signature = signature
    self._error(<copy for posture.kind / degenerate_dimensions>)
    return
```

   Any edit to a mode, an Input, or a selection changes the signature, so the
   warning re-arms automatically (the selection handler additionally clears
   `_warned_signature` eagerly). Copy mirrors `preflight._authorization_results`
   (`:165-190`):
   - `deny_all` with `degenerate_dimensions == ("users", "roles")` →
     `"both allowlists empty — deny-by-default: nobody will be able to open a
     bug report. Press Next again to keep this."`
   - `deny_all` with a single degenerate dimension →
     `"denylist has no effect — the empty <dim> allowlist denies everyone.
     Press Next again to keep this."`
   - `open_members` → `"open access: any channel member will be able to open a
     bug report. Press Next again to keep this."`
   - `restricted` → advance silently.

5. `_commit_state()` (all four lists + both modes + the transient fetch cache
   into `self.state`), then `dismiss(NEXT)`.

### 6. Summary + inactive-list disclosure

`SummaryScreen._summary_text()` (`:543-565`): replace the single concatenated
`allowlist:` line (`:551, 556`) with one line per dimension, and **disclose a
non-empty inactive list** — the wizard preserves it (merge-never-drop), so a
Save that silently carries ids the operator never reviewed, and which a later
mode switch would activate, must not be invisible:

```
users: allowlist: 111, 222   (denied_user_ids kept but ignored: 333)
roles: denylist: (none)
```

The active list is `denied_*` when the mode is `denylist`, else `allowed_*`; the
parenthetical is omitted when the inactive list is empty. `AllowlistScreen`
renders the same disclosure inline per dimension (`#wiz_<dim>_inactive`, via
`_render_inactive(dim)`, refreshed on every mode toggle) so the operator sees it
where they can act on it. Wording echoes preflight's existing
`"<key> is set but ignored"` rows (`:219-225`).

### 7. Tests — `tests/test_chatlink_tui.sh`

Add an `allowlist_fetch_runner` spy alongside `wiz_spy_live` (same shape as
`wiz_spy_live` / `make_wizard_app`, `:249-278`), returning a canned
`AllowlistFetchResult`, with a `threading.Event` block mode for the mid-run
test. Cases:

- spy **not** called before pressing Fetch; called with the entered
  token / workspace / conversation ids after.
- results populate both SelectionLists with `"{name} ({id})"` labels.
- toggling a selection rewrites the corresponding Input.
- manually-typed ids not in the fetched set survive fetch + selection.
- fetch failure (runner raises, and a `members_error`-only result) degrades to
  manual entry and still advances.
- invalid snowflake blocks advance with the bad token named; dedupe on accept.
- posture warnings: `deny_all` both-dimensions, one **mixed degenerate** posture
  (`denylist` roles + empty `allowlist` users), and `open_members`.
- **REQUIRED state-model tests:**
  1. *mode-toggle-after-selection* — fetch, select entries, toggle that
     dimension's mode; the selection landed only in the previously active list
     and the Input now shows the other list.
  2. *filter-after-toggle* — filter, toggle; no selection or list mutation from
     filtering.
  3. *toggle round-trip* — allowed→denied→allowed preserves both lists exactly.
  4. *Back/Next retention* — leave and re-enter the screen; all four lists +
     both modes retained and re-displayed.
- **Review-driven additions:**
  - *rebuild never writes back* — after `await pilot.pause()` (so any queued
    message is drained), assert fetch, filter, and mode-toggle rebuilds each
    left `_working` and both Inputs byte-identical. This is the explicit proof
    that async `SelectedChanged` echoes cannot masquerade as user actions.
  - *posture warning re-arms* — warn on `deny_all`, then flip both modes to
    `denylist` (now `open_members`) and press Next: it must warn **again**, not
    advance. Plus the negative: press Next twice on the *same* posture and it
    advances.
  - *Back before Next preserves picker work* — fetch, select, press **Back**,
    return: all four lists, both modes, and the fetched picker rows are intact
    and the spy was **not** called a second time (transient cache reused).
  - *stale context drops picker-origin ids, keeps typed ones* — fetch, select a
    member **and** a role, and additionally type an id that is **not** in the
    fetched set; press **Back** to the intake step, change `workspace_id`, come
    forward. Assert: pickers empty; both picker-selected ids **gone** from their
    Inputs and from `_working` (both the allowed and denied list of that
    dimension); the typed id **retained**; and the notice **names the two
    removed ids** — proving the drop is a reviewed state, not a silent mutation.
    Repeat for a changed token (`state["token"]` reassigned on the token step)
    to prove the fingerprint is part of the key.
  - *removal is fail-closed and surfaced* — in the scenario above, when stripping
    the picker-origin ids empties the allowlists, pressing Next must raise the
    `deny_all` posture warning rather than advance. This pins the composition of
    the two guards.
  - *ambiguous id counts as picker-origin* — an id both typed and present in the
    fetched set is removed on context change and named in the notice.
  - *transient keys never reach the config* — `build_edits(state)` output has no
    `_fetched` key, a saved config file contains none, and the cache key holds
    a fingerprint rather than the raw token string.
  - *typed id present in the fetched set* (the invariant): type an id that IS
    among the fetched rows, then Fetch — its row starts **selected**; then
    select a different row and assert the typed id survives in the Input and
    `_working`. Then the no-intervening-rebuild variant: fetch **first**, type
    the id, click another row without any rebuild between — it must still
    survive. (Both fail against a design that syncs only at rebuild time.)
  - *deselect still removes* — the negative control for the above: clicking a
    selected visible row removes exactly that id from the Input.
  - *Enter in the filter field does not advance* — type in `#wiz_fetch_filter`,
    press Enter: still on `AllowlistScreen`, no inline error.
  - *inactive-list disclosure* — with `denied_user_ids` non-empty under
    `allowlist` mode, both the screen's `#wiz_user_inactive` and the summary
    name the ignored key and its ids.
- end-to-end: saved config round-trips both modes + all four lists.

Existing assertions to re-check: the `Step 2/7` / `Step 4/7` title checks
(`:332, 373`) are unchanged (no screen added/removed); the empty-allowlist
warning check (`:406-409`) keeps passing because the `deny_all` copy retains the
`deny-by-default` substring.

## Verification

```bash
bash tests/test_chatlink_tui.sh      # new suites + all existing
bash tests/test_chatlink_wizard.sh
bash tests/test_chatlink_config.sh
bash tests/test_chatlink_preflight.sh
```

Live picker behavior (real Discord fetch, unchunked member cache, visibility
exclusion, filter over a large guild) is delegated to the aggregate
manual-verification sibling **t1186_5**.

Post-implementation per task-workflow Step 9; archive via
`./.aitask-scripts/aitask_archive.sh 1186_4` (last implementation child — the
MV sibling t1186_5 follows).

## Risk

Re-authored across three rounds of plan review. Every code-health risk
identified so far is now addressed *in design* rather than left to reviewer
vigilance; the smaller risks introduced by those fixes are listed. The user
declined mitigation tasks for the earlier, strictly-higher risk profile; that
decision is carried forward, so no mitigations subsection is recorded below and
the Step 7 / Step 8d mitigation creators correctly find nothing to create.

### Code-health risk: medium

- **Cross-context authorization ids.** The Back-survivable fetch cache could
  carry ids selected under a previous Discord context into a new one — and
  because role ids are **guild-scoped**, such an id is meaningless rather than
  merely stale, with no downstream check able to catch it (`invalid_snowflakes`
  passes any well-formed snowflake). Addressed: the cache is keyed on every
  argument the fetch receives (intake tuple + token fingerprint), and on a key
  mismatch the picker-origin ids — tracked by provenance recorded at commit time
  — are removed from both of that dimension's lists and **named in the notice**,
  while manually typed ids are kept. Removal is the fail-closed side and its
  degenerate result is caught by the step-5 posture warning. · severity: low ·
  → mitigation: TBD
- **Input/picker divergence.** If the picker's ticks lag the Input, a
  visible-but-unselected row is ambiguous and the write-back silently drops a
  manually typed id. Addressed by the pinned invariant (selected set ≡ active ∩
  visible) maintained on all four mutation paths, with the
  no-intervening-rebuild case tested explicitly. · severity: low ·
  → mitigation: TBD
- **Shared base-class hook.** `_WizardStep._before_back()` touches the contract
  all seven wizard screens inherit. Mitigated by shape: the base method is a
  no-op and `_on_back` keeps its `@on` registration, so the other six screens
  are unchanged. · severity: low · → mitigation: TBD
- **Transient key in the shared state dict.** `_fetched` lives in the same dict
  `build_edits` reads, and its key embeds a token-derived fingerprint.
  `build_edits` enumerates keys explicitly (never `**state`), so leakage is
  structurally impossible; pinned by tests asserting no `_fetched` key in the
  output or a saved config, and that the key holds a digest, never the token. ·
  severity: low · → mitigation: TBD
- **Stale-mode write-back.** Addressed: the selection handler reads
  `self._modes[dim]` at event time, and required test 1 pins it. Residual risk
  is a future edit hoisting that read. · severity: low · → mitigation: TBD
- **Async rebuild echo.** Confirmed real (`_make_selection` → `_select` →
  `post_message`). Addressed with two independent mechanisms — `prevent` at the
  post site and the timing-independent `_echo[dim]` set comparison — plus a
  drain-then-assert test. · severity: low · → mitigation: TBD
- **Overall shape.** `AllowlistScreen` remains a non-trivial state machine
  (four lists, two modes, four mutation paths, a keyed cache) inside a Textual
  screen, so it is only testable through Pilot — and three review rounds have
  now each found a real state-model defect in it, which is itself evidence that
  the shape is the residual risk. Blast radius is otherwise contained: `wizard.py`
  (one screen + three module functions + one base hook) and one
  `chatlink_app.py` init param. · severity: medium · → mitigation: TBD

### Goal-achievement risk: low

- **Snowflake validation scoped to active lists only** is a deliberate,
  documented refinement of the task file's unqualified wording; step 6's
  disclosure keeps the inactive list visible. If the intent was all four lists,
  the fix is a one-line change to the `invalid_snowflakes(...)` argument. ·
  severity: low · → mitigation: TBD
- **Back-commits-without-validation** is a new behaviour for this screen (the
  other six discard on Back). Justified by the cost of redoing a live fetch, and
  safe because `SummaryScreen` is only reachable through `_accept()`. ·
  severity: low · → mitigation: TBD
- Approach, screen state model, and required tests are pinned by the task file
  and were re-verified against the three landed siblings; real-Discord behavior
  is out of scope here and already owned by the existing MV sibling t1186_5. ·
  severity: low · → mitigation: TBD

## Post-Review Changes

### Change Request 1 (2026-07-21 13:05)

- **Requested by user:** Reviewing the implementation, flagged that
  `AllowlistScreen._apply_fetch` returns early on a `None` result without
  clearing or hiding picker rows that are already visible from a prior
  successful fetch (or restored from the Back-survivable cache). A failed
  *refresh* therefore shows "fetch failed" while the earlier rows stay
  rendered, ticked, and selectable, and `_commit_state` re-caches them.
  Verified CONFIRMED; disposition: **follow-up**, not an in-task fix.
- **Verification performed:** Reproduced directly against the built screen —
  after a successful fetch + selection and a failing refresh, the status line
  read `! fetch failed …` while `option_count == 1`, `display is True`, and
  `_commit_state` re-cached the row with provenance.
- **Scoping note (what is NOT wrong):** the retained rows always belong to the
  *current* context — `_fetch_key` is unchanged and `_pending_key` is adopted
  only on success — so the cache-key revalidation and picker-origin removal in
  `_restore_cache` are unaffected. This is a staleness/clarity defect, not a
  wrong-context authorization leak, which is why deferring it is safe.
- **Changes made:** No code change (per the follow-up disposition). Created
  **t1204** (`chatlink_wizard_failed_refresh_stale_picker_rows`, bug, medium/
  low, anchored to topic root 1149) carrying the confirmed reproduction, the
  severity scoping above, two candidate fixes (clear-on-failed-refresh vs.
  label-the-retained-rows), and the verification plan reusing this task's
  `wiz_spy_fetch` seam.
- **Files affected:** `aitasks/t1204_chatlink_wizard_failed_refresh_stale_picker_rows.md`
  (new); this plan file.

## Known limitations (carried into follow-ups)

- **Failed *refresh* leaves the previous rows visible** — see **t1204** above.
  A failed *first* fetch is unaffected: the picker was never revealed, so the
  screen correctly degrades to manual entry only (pinned by the "a raising
  fetch runner degrades to manual entry" test).

## Final Implementation Notes

- **Actual work done:** All seven planned steps landed as designed.
  `wizard.py` gained the `allowlist_fetch_runner` seam, the six-key state
  round-trip (`initial_state` / `build_edits`, with `build_edits` documented as
  explicitly enumerated so transient keys cannot leak), a module-level
  `_Dimension` table + `_active_key` / `_inactive_key` / `_fetch_key` /
  `_authorization_lines` helpers, a rebuilt `AllowlistScreen`, and per-dimension
  summary lines. `chatlink_app.py` gained the one init param.
  `tests/test_chatlink_tui.sh` went from 68 to 132 assertions.

- **Deviations from plan:** One mechanism changed during implementation. The
  plan specified overriding `on_input_submitted` to stop Enter-in-filter from
  advancing. That is **wrong on Textual**: `MessagePump._get_dispatch_methods`
  iterates `self.__class__.__mro__` and yields the naming-convention handler
  from *every* class that defines it, so `_WizardStep.on_input_submitted` ran in
  addition to the override — calling `_accept()` twice per keypress. The second
  call matched the `_warned_signature` the first had just set, so the posture
  warning self-confirmed and the step advanced silently. Replaced with a
  `_WizardStep._submits_on_enter(widget)` predicate hook (default `True`;
  `AllowlistScreen` returns `False` for `#wiz_fetch_filter`), leaving the base
  `on_input_submitted` as the single dispatch point. This is now the second
  base-class hook added by this task, alongside `_before_back()`.

- **Issues encountered:** Two test failures were *correct behaviour* rather
  than bugs, and both became stronger assertions:
  1. Flipping both dimensions to denylist did not reach `open_members`, because
     the config saved earlier in the suite carried a `denied_user_ids` entry
     that was inactive under allowlist mode. That is the inactive list
     round-tripping through a real save + reload; the test now asserts it
     explicitly ("switching to denylist surfaces the preserved denied list").
  2. `app8`'s retention assertions were polluted by config prefill; it now
     starts from an explicit state while deliberately leaving the inactive
     `denied_user_ids` in place, so the stale-context removal is proven to
     reach **both** of a dimension's lists.

- **Key decisions:**
  - *Validation scope* — `invalid_snowflakes` runs on the two **active** lists
    only. Hard-blocking on a value the operator cannot see would be
    unactionable; switching a mode brings the other list into view and into
    validation, and the inactive-list disclosure keeps it visible meanwhile.
  - *Stale-context handling* — on a cache-key mismatch, picker-origin ids
    (tracked by provenance recorded at commit time) are removed from both of a
    dimension's lists and named in the notice, while manually typed ids are
    kept. Removal is fail-closed and its degenerate result is caught by the
    posture warning; retention would have been silent and undetectable, since
    a stale-but-well-formed snowflake passes every downstream check.
  - *Posture warning* — keyed to a signature of both modes plus all four lists,
    not a one-shot boolean, so a *different* risky posture always re-warns.

- **Mutation testing (evidence the new tests are not vacuous):** each guard was
  broken in turn and the suite re-run. Caught: bare one-shot posture flag;
  unkeyed fetch cache; keeping stale picker-origin ids; sync-only-at-rebuild;
  Back discarding work; filter-Enter advancing; no snowflake validation; and
  `preserved` computed against the fetched set instead of the visible set —
  **that last one initially passed**, revealing a genuinely missing case (change
  a visible row's state while another selected id is hidden by the filter),
  which was then added. Two honest caveats recorded rather than glossed:
  - `prevent()` and the `_echo` set-comparison are *individually* redundant —
    removing either alone passes, removing **both** is caught. Deliberate
    defence-in-depth, now empirically characterised.
  - The event-time mode read and the mode-toggle "parking" step are
    **unfalsifiable** in the current design: a mode flip always rebuilds
    synchronously, and `_sync_active` already keeps the outgoing list current.
    Both are the task file's pinned contract and cheap insurance, but no test
    fails without them.

- **Upstream defects identified:** None

- **Notes for sibling tasks:** t1186_5 (aggregate manual verification) should
  exercise, against a real guild: the member/role fetch on an unchunked cache;
  a member without channel visibility being excluded; the filter over a large
  member list (and the `MAX_MEMBERS = 500` truncation notice); and the
  stale-context path — fetch, Back, change the intake channel, forward — which
  must empty the picker and name the removed ids. The `wiz_spy_fetch` seam and
  `canned()` helper in `tests/test_chatlink_tui.sh` are reusable for any further
  picker tests, including a `threading.Event` block mode for mid-run
  navigation. Note the deferred defect in **t1204**: a failed *refresh* still
  shows the previous rows.
