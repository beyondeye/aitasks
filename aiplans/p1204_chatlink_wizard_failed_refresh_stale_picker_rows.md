---
Task: t1204_chatlink_wizard_failed_refresh_stale_picker_rows.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t1204 — Flag stale picker rows when a wizard allowlist *refresh* fails

## Context

Follow-up to t1186_4 (chatlink wizard live Discord allowlist pickers), raised
and confirmed during that task's implementation review and dispositioned as a
follow-up.

`AllowlistScreen._apply_fetch` (`.aitask-scripts/chatlink/wizard.py:740`)
treats a failed fetch as advisory and returns early:

```python
if result is None:
    status.update("! fetch failed — enter ids manually above "
                  "(Next still works)")
    return
```

That is right for a **first** fetch — the picker was never revealed, so manual
entry is genuinely all that is on offer. It is wrong for a **refresh**: rows
already visible from a prior successful fetch (or restored from the
Back-survivable cache by `_restore_cache`) stay rendered, ticked and selectable
while the status line says the fetch failed. `_commit_state` then re-caches
them with provenance on Back/Next, so a later re-entry presents them again with
no notice at all.

This is a **staleness and clarity** defect, not a wrong-context authorization
leak: `_fetch_key` is unchanged and `_pending_key` is adopted only on success,
so the cache-key revalidation and picker-origin removal in `_restore_cache`
still hold. The rows always belong to the current context — they may simply be
out of date (a member who has since left, a deleted role).

**Chosen option (confirmed with the user): retain the rows, but declare them
stale — loudly, per dimension, and persistently.** Discarding an operator's
multi-select over a transient network blip is the worse trade; the fix is to
make "these are the earlier fetch" impossible to miss and to make that marking
survive a Back excursion, so `_commit_state` never silently re-presents stale
rows as current.

### What "a failed fetch" actually is (established during plan review)

The task text frames the bug around `result is None`, but that is **not** the
production failure shape. `allowlist_fetch.AllowlistFetchResult` is documented
as *"Outcome of one member/role fetch run (always returned, never raised)"*
(`allowlist_fetch.py:51`), and `_run_async` reports every real-world failure as
a **per-stage error string on a returned result**:

| Failure | Reported as | Rows |
|---|---|---|
| connection timed out (`allowlist_fetch.py:114`) | `members_error` **and** `roles_error` | none |
| connection failed / token rejected (`:118`) | `members_error` **and** `roles_error` | none |
| member fetch timeout / failure (`:140`, `:143`) | `members_error` only | roles only |
| role fetch timeout / failure (`:151`, `:154`) | `roles_error` only | members only |

`result is None` happens only when the runner breaks that never-raises contract
(the wizard's worker `work()` catches `Exception` and substitutes `None`) — the
shape the *tests* inject via `wiz_fetch["raise"]`, not the shape production
produces. Three consequences drive the design:

1. **Classification must cover result-object failures**, or the fix is theatre:
   a real Discord outage takes the `result is not None` path.
2. **Members and roles fail independently** (stage 1 vs stage 2), so staleness
   is **per dimension**, not per screen. The existing `app10` test already
   exercises members-ok / roles-failed. A screen-wide flag would either brand
   freshly-fetched rows stale or present stale rows as fresh.
3. **A run in which every stage failed produced nothing** — and today the code
   does not recognise that. On the first live fetch during an outage or with a
   rejected token (the top three rows of the table above, which `return result`
   with both errors set and zero rows), `_apply_fetch` still adopts
   `_pending_key`, assigns `_fetched = {[], []}` and calls `_reveal_picker()`.
   `_commit_state` then caches that empty state **as a successful fetch**, so a
   Back→forward round trip hits the matching-key branch of `_restore_cache`,
   which returns `""` — two empty picker boxes and a blank status line, with no
   record that anything failed. The same shape on a *refresh* wipes the
   operator's visible rows and destroys the `origin_*` provenance.

## Requirements

From the task's Verification section:

1. Successful fetch → failing refresh: rows retained **and** a notice naming
   them as the earlier fetch.
2. The first-fetch failure path still degrades to manual entry and still
   advances (existing assertions must stay green).
3. `_commit_state` must not silently re-cache rows the UI has declared stale.

Plus, from the review above: a fetch that produced nothing must never be cached
or revealed as though it had succeeded (requirement 3 in spirit — the cache
must not launder a failure into a clean empty result).

## Implementation

All production changes are in `.aitask-scripts/chatlink/wizard.py`, class
`AllowlistScreen`. The design reuses the existing per-dimension seams — the new
state is one dict shaped exactly like `_fetched` / `_visible` / `_echo`.

### 1. Module-level notice helper

Next to the other module-level privates (`_LIST_KEYS`, `_DIMENSIONS`,
`_ID_SPLIT_RE`), add the shared copy used by both `_restore_cache` and
`_apply_fetch`. Keep the `!` prefix convention of the other status lines, and
`f"{dim.key}s"` for the noun (the idiom `_summary_lines` already uses):

```python
_STALE_BORDER_TITLE = "! previous fetch — may be out of date"


def _stale_line(dim_keys) -> str:
    """Status copy qualifying rows that predate a failed refresh.

    Deliberately distinct from the manual-entry failure copy — that one
    offers manual entry INSTEAD of rows; this one qualifies rows the
    operator can still see and tick.
    """
    return ('! showing the EARLIER fetch for: '
            f'{", ".join(f"{k}s" for k in dim_keys)} — those rows may be out '
            'of date (a member may have left, a role may have been deleted). '
            'Press "Fetch from Discord" to retry.')
```

### 2. `_stale` per-dimension flags (`__init__`, ~line 448)

Add alongside the sibling per-dimension dicts, **before** the
`self._notice = self._restore_cache()` line (which may set it):

```python
self._stale: dict[str, bool] = {dim.key: False for dim in _DIMENSIONS}
```

### 3. `_restore_cache` (~line 464) — adopt the flags with the rows

In the matching-key branch, adopt the staleness and return the notice instead
of `""`:

```python
if token and cached.get("key") == _fetch_key(self.state, token):
    self._fetch_key = cached["key"]
    for dim, rows in (("user", cached["members"]),
                      ("role", cached["roles"])):
        self._fetched[dim] = [tuple(row) for row in rows]
    stale = cached.get("stale") or {}
    self._stale = {dim.key: bool(stale.get(dim.key)) for dim in _DIMENSIONS}
    marked = [k for k, on in self._stale.items() if on]
    return _stale_line(marked) if marked else ""
```

`.get("stale")` matches the tolerant accessor style already used for
`cached.get(f"origin_{dim.key}", ())`. The returned string lands in
`self._notice`, which `body()` already renders into `#wiz_fetch_status`.

### 4. `_render_stale()` / `_hide_picker()` helpers (~line 563)

Add `_render_stale` and call it at the end of `_reveal_picker` — which already
runs on `on_mount` re-entry and after every applied fetch — so one call site
keeps both surfaces in sync. Add `_hide_picker` as `_reveal_picker`'s inverse,
needed by the produced-nothing branch in §5:

```python
def _render_stale(self) -> None:
    """Mark/unmark each picker as predating a failed refresh."""
    for dim in _DIMENSIONS:
        picker = self.query_one(f"#{dim.list_id}", SelectionList)
        picker.set_class(self._stale[dim.key], "stale")
        picker.border_title = (_STALE_BORDER_TITLE
                               if self._stale[dim.key] else "")

def _hide_picker(self) -> None:
    """Inverse of :meth:`_reveal_picker` — back to manual entry only."""
    self.query_one("#wiz_fetch_filter", Input).display = False
    for dim in _DIMENSIONS:
        self.query_one(f"#{dim.list_id}", SelectionList).display = False
    self._render_stale()

### 5. `_apply_fetch` (~line 740) — classify per stage, then decide once

The whole method is restructured around one idea: **normalise both failure
shapes into a per-stage table, then let two derived lists (`usable`, `kept`)
drive every decision.** No nested special cases.

```python
def _apply_fetch(self, gen: int, result) -> None:
    if gen != self._fetch_gen or not self.is_attached:
        return  # superseded run, or the screen was already dismissed
    self._fetch_running = False
    status = self.query_one("#wiz_fetch_status", Static)
    # Normalise both failure shapes to one per-stage table. A returned
    # result reports production failures (no connection, rejected token,
    # missing permission) as per-stage error strings; a raised one arrives
    # as None because the worker swallowed it. An errored stage always
    # carries zero rows, so an error means "this run produced nothing
    # usable for this dimension" either way.
    if result is None:
        errors = {dim.key: "fetch failed" for dim in _DIMENSIONS}
        rows = {dim.key: [] for dim in _DIMENSIONS}
    else:
        errors = {"user": result.members_error, "role": result.roles_error}
        rows = {"user": list(result.members), "role": list(result.roles)}

    usable: list[str] = []          # dimensions THIS run answered for
    kept: list[str] = []            # failed stages whose old rows we keep
    for dim in _DIMENSIONS:
        if not errors[dim.key]:
            self._fetched[dim.key] = rows[dim.key]
            self._stale[dim.key] = False
            usable.append(dim.key)
        elif self._fetched[dim.key]:
            # This stage failed but the dimension already had rows: keep
            # them (a live fetch plus a multi-select is expensive to redo)
            # and mark them — never present them as current.
            self._stale[dim.key] = True
            kept.append(dim.key)
        else:
            self._stale[dim.key] = False   # nothing to be stale about

    lines = []
    if result is None:
        lines.append("! fetch failed")
    else:
        if result.members_error:
            lines.append(f"! members: {result.members_error}")
        if result.roles_error:
            lines.append(f"! roles: {result.roles_error}")
        if result.members_truncated:
            lines.append(f"showing the first {allowlist_fetch.MAX_MEMBERS} "
                         "members — use the filter to narrow")

    if not usable and not kept:
        # The run answered for no dimension and left nothing to qualify.
        # Drop all the way back to the manual-entry-only state: an empty
        # picker cached as a successful fetch comes back after a
        # Back/forward round trip with no notice at all (_restore_cache's
        # matching-key branch returns "" and on_mount re-reveals).
        # Clearing _fetch_key is not enough on its own — _commit_state
        # early-returns on a None key WITHOUT deleting an entry a previous
        # commit already wrote, and _restore_cache deletes only on a key
        # MISmatch, so the entry has to be dropped here.
        self._fetch_key = None
        self.state.pop("_fetched", None)
        self._hide_picker()
        lines.append("enter ids manually above — Next still works")
        status.update("\n".join(lines))
        return

    if kept:
        lines.append(_stale_line(kept))
    if not lines:
        lines.append(f"fetched {len(result.members)} member(s) and "
                     f"{len(result.roles)} role(s)")
    lines.append("manual entry always works — the id boxes stay editable")
    status.update("\n".join(lines))
    self._fetch_key = self._pending_key
    self._reveal_picker()
```

Why this covers each shape:

| Situation | `usable` / `kept` | Outcome |
|---|---|---|
| first fetch, all stages ok | both / — | reveal, nothing stale (today's behaviour) |
| first fetch, roles failed (`app10`) | `[user]` / — | reveal members, roles stay empty, **not** stale |
| first fetch, runner raised (`app11`) | — / — | manual entry, no reveal, `_fetch_key` stays `None` |
| **first fetch, connection failed / token rejected** | — / — | **same manual-entry shape** — no empty cache |
| refresh, roles failed | `[user]` / `[role]` | members refreshed, role rows kept + marked stale |
| refresh, all stages failed | — / both | both kept + marked stale |
| refresh after a legitimately empty fetch | — / — | manual entry; pickers hidden, key + cache cleared |

Other invariants preserved:

- The `elif` reads `self._fetched[dim.key]` **before** any overwrite — the
  overwrite only happens in the non-error branch, so each dimension reads its
  own pre-fetch rows exactly once.
- After the produced-nothing branch, `_fetch_key is None` **and**
  `state["_fetched"]` is gone, so `_commit_state`'s existing
  `if self._fetch_key is None: return` guard keeps the failure out of the cache
  and there is no leftover entry for `_restore_cache` to resurrect. Reaching
  that branch requires every dimension's `_fetched` to be empty (`kept` empty),
  so the dropped cache entry is always the empty one — a cache holding real
  rows would have produced a non-empty `kept` and taken the stale path instead.
- The operator's ids in `_working` are **not** touched by that branch. The
  picker-origin removal in `_restore_cache` is specifically about a *changed*
  Discord context, where a fetched id becomes meaningless; here the context is
  unchanged, so the ids remain valid assertions and stay in the Inputs.
- Within one `AllowlistScreen` instance the intake context cannot change (it is
  edited on earlier screens), so `_pending_key == _fetch_key` on every refresh
  and the assignment is a no-op there.

**User-visible copy change:** the manual-entry failure message becomes two
lines — the diagnostic (`! fetch failed`, or the per-stage `! members: …` /
`! roles: …`) followed by `enter ids manually above — Next still works`. This
replaces the single-line `"! fetch failed — enter ids manually above (Next
still works)"`, and is strictly more informative on the production path, which
previously lost the manual-entry hint entirely. `app11`'s existing substring
assertion (`"fetch failed" in status`) stays green.

### 6. `_commit_state` (~line 769) — the flags ride with the rows

Add `"stale": dict(self._stale)` to the `self.state["_fetched"]` dict, with a
comment tying it to requirement 3: the rows *are* still cached (that is the
point of the chosen option), but never as *current* — the marking travels with
them so `_restore_cache` re-renders the notice and the border on re-entry.

### 7. CSS (`DEFAULT_CSS`, ~line 433)

```css
AllowlistScreen SelectionList.stale { border: round $warning; }
```

One extra class selector over the base `AllowlistScreen SelectionList` rule, so
it wins. **Verified empirically** on the pinned Textual 8.2.7: the resolved
`styles.border_top` goes from `('round', Color(1, 120, 212))` to
`('round', Color(254, 166, 43))`.

### 8. Docstrings

Extend the `AllowlistScreen` class docstring — which currently ends "…and a
failed fetch never blocks Next" — with the refresh case and the per-stage
classification, so all three failure shapes are documented together.

## Verification

Extend `tests/test_chatlink_tui.sh` in the t1186_4 allowlist-picker section,
reusing the existing `wiz_spy_fetch` seam (its `raise` switch and `canned()`
results) and the `goto_allowlist()` walker. Run the new blocks at
`size=(110, 80)` so both pickers sit inside the viewport for the screenshot
assertion.

**Block A — first fetch, all stages failed (the production outage shape):**

Set `wiz_fetch["result"] = canned(members=[], roles=[],
members_error="connection failed (OSError)", roles_error="connection failed
(OSError)")` and press Fetch on a fresh screen. Assert:

- neither picker is revealed, and `scr._fetch_key is None`;
- the status carries `"! members: connection failed (OSError)"` and
  `"enter ids manually above"`;
- Next still advances to `DenyRepoScreen` (requirement 2);
- **Back → forward returns to a screen with no cached picker state** —
  `_fetch_key is None`, pickers hidden, `"_fetched" not in app.…state`. This is
  the direct regression test for the empty-cache defect.

**Block A2 — produced-nothing refresh after a legitimately empty fetch:**

This is the only route by which a produced-nothing run can find `_fetch_key`
already set, and it must not leave a cached empty fetch behind.

- `wiz_fetch["result"] = canned(members=[], roles=[])` (both stages succeed,
  no rows) → press Fetch → assert the pickers reveal empty, the status reads
  `"fetched 0 member(s) and 0 role(s)"`, and `scr._fetch_key is not None`;
- Back → forward, so `_commit_state` actually writes `state["_fetched"]` and
  `_restore_cache` adopts it → assert re-entry still shows the empty pickers;
- switch to the all-stages-failed result → press Fetch → assert the pickers are
  **hidden**, `scr._fetch_key is None`, `"_fetched" not in scr.state`, and the
  status carries the per-stage errors plus `"enter ids manually above"`;
- Back → forward once more → assert the pickers stay hidden and `_fetch_key`
  stays `None`. Without the cache pop this re-entry resurrects the empty rows
  with a blank status line.

**Block B — refresh, partial failure (per-dimension marking):**

- successful fetch → tick `ALICE` and `MODS` → assert neither picker is stale
  (baseline that makes the flip meaningful);
- set `wiz_fetch["result"] = canned(roles=[], roles_error="role fetch failed
  (Forbidden)")` and press Fetch → assert:
  - the **role** picker retains its 2 rows, carries the `stale` class and
    `border_title`, and `_working["allowed_role_ids"] == [MODS]`;
  - the **member** picker is refreshed and **not** stale;
  - the status carries both `"! roles: role fetch failed (Forbidden)"` and
    `"showing the EARLIER fetch for: roles"`.
- **Render-level proof:** assert the two pickers' resolved `styles.border_top`
  differ (proves CSS specificity took effect, not merely that the class
  attribute was set), and that the border title actually renders:
  ```python
  # Textual's SVG export writes spaces as non-breaking spaces, so normalise
  # the entity and the literal codepoint before matching.
  svg = (app.export_screenshot()
         .replace("&#160;", " ").replace(" ", " "))
  check("the stale border title actually renders",
        "previous fetch" in svg and "may be out of date" in svg)
  ```
  Verified empirically that without this normalisation a raw substring match
  silently fails even though the title is visibly on screen.

**Block C — refresh, total failure and cache round-trip:**

- successful fetch → tick `ALICE`; then the all-stages-failed result → assert
  **both** pickers retain their rows and are stale, and
  `_working["allowed_user_ids"] == [ALICE]`. This is the case today's code
  wipes.
- **Back → forward** (mirroring the `app8` back/next dance) → assert the rows
  come back *with* the stale classes and the notice still rendered. The direct
  test of requirement 3: the cache round-trip must not launder the rows back
  into looking current.
- clear the error (`wiz_fetch["result"] = None`), press Fetch → assert both
  markings clear and the normal `"fetched 3 member(s) and 2 role(s)"` line
  returns.
- also cover the raising-runner refresh (`wiz_fetch["raise"] = True`) → both
  dimensions stale, status carries `"! fetch failed"` **and** the EARLIER line.

**Negative controls — existing assertions that must stay green:**

- `app10` (first fetch, roles error, members truncated): unchanged output —
  roles had no prior rows, so nothing is marked stale and the member rows still
  reveal. Add `"showing the EARLIER" not in status` to pin that a *first*-fetch
  stage failure never claims staleness.
- `app11` (first fetch, raising runner): still degrades to manual entry —
  pickers not revealed, `"fetch failed"` shown, Next still advances. Add
  `"EARLIER" not in status`.

Run:

```bash
bash tests/test_chatlink_tui.sh
bash tests/test_chatlink_wizard.sh
```

Before relying on the new checks, confirm the suite can actually fail: flip one
new assertion to its negation and verify the script exits 1.

## Concurrency note (affects staging, not design)

Another session has **uncommitted in-flight t1190 work** (wizard draft/resume)
in both `.aitask-scripts/chatlink/wizard.py` (`SummaryScreen`, `start_wizard`,
new `_ResumeDraftScreen`, plus a new untracked `chatlink/wizard_draft.py`) and
`tests/test_chatlink_tui.sh` (`goto_allowlist` draft hygiene, a drift-guard
check). Those regions do not overlap `AllowlistScreen`.

At commit time: **verify staged content, not just staged paths** — inspect
`git diff --cached` hunk by hunk and extract only the `AllowlistScreen` /
allowlist-test hunks. Never `git add` the whole file blind, and never stash.

## Risk

### Code-health risk: medium
- Concurrent uncommitted t1190 work in both files this task edits — a blind
  `git add <file>` would sweep another session's half-finished wizard-draft
  feature into the t1204 commit · severity: medium · → mitigation: none — no
  task-shaped mitigation exists; handled inline by the hunk-level staging
  discipline in "Concurrency note" above
- `_apply_fetch` grows from ~25 to ~55 lines and now owns failure
  classification, retention and rendering. Mitigated by normalising both
  failure shapes into one per-stage table up front, so every decision reads off
  two derived lists (`usable`, `kept`) instead of nested special cases; the
  situation table above is the contract · severity: low · → mitigation: none
- The reveal/cache decision moves from "did the runner return an object" to
  "did the run produce or retain anything", which changes behaviour on paths
  the current tests do not cover (all-stages-failed first fetch; a
  produced-nothing refresh after an empty success). That branch is now the only
  place that *un*-reveals a picker and mutates `state["_fetched"]` outside
  `_commit_state` / `_restore_cache` — a third writer of the cache key. Pinned
  by blocks A and A2 and by the two negative controls · severity: low ·
  → mitigation: none
- Adding a key to the `state["_fetched"]` dict is additive and read through
  `.get()`; `build_edits` provably excludes underscore-prefixed state (test
  "build_edits omits the transient picker cache") and t1190's
  `DRAFT_STATE_KEYS` drift guard pins drafts to `initial_state` keys, which
  never include `_fetched` · severity: low · → mitigation: n/a

### Goal-achievement risk: low
- Two classification gaps that would have left the production failure paths
  unfixed (result-object failures; all-stages-failed first fetch caching an
  empty picker) were found during plan review and are now closed and pinned by
  blocks A and C · severity: low · → mitigation: none
- Per-dimension staleness and the cache round-trip each map to a named
  assertion; the render-level claims were verified against the pinned Textual
  8.2.7 before being written into the plan · severity: low · → mitigation: n/a

## Step 9 — Post-Implementation

Merge (current-branch profile: no worktree to clean up), run the declared
`risk_evaluated` gate via `./ait gates run 1204`, then archive with
`./.aitask-scripts/aitask_archive.sh 1204`.
