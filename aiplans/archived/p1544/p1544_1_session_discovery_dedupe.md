---
Task: t1544_1_session_discovery_dedupe.md
Parent Task: aitasks/t1544_stats_backlog_and_net_flow_by_category.md
Sibling Tasks: aitasks/t1544/t1544_2_task_category_axis_module.md, aitasks/t1544/t1544_3_backlog_flow_collection.md, aitasks/t1544/t1544_4_cli_backlog_sections_and_csv.md, aitasks/t1544/t1544_5_stats_tui_backlog_panes.md, aitasks/t1544/t1544_6_backlog_stats_documentation.md, aitasks/t1544/t1544_7_manual_verification_stats_backlog.md, aitasks/t1544/t1544_8_backlog_stats_retrospective.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-18 10:11
---

# p1544_1 — Session-discovery dedupe

## Goal

Make session discovery return **one record per repository** for the
registry-inclusive consumers, so `merge_stats_data` can no longer be handed the
same `StatsData` object twice. This is a pre-existing bug affecting every
existing stats counter; t1544_3's "a multi-project run does not double-count"
test is untestable without it.

The verification pass below found the same duplicate also **breaks the TUI
switcher outright** (a livelocked cycle ring), so this task fixes two surfaces,
not one.

## Verification pass (2026-08-17) — corrections to the original plan

Re-verified against live source before implementation. Five instructions were
wrong or incomplete; each correction is evidence-backed and is the single
rationale for its point (later sections reference, never restate, these).

1. **The dedupe must be gated on `include_registered=True`.** The original plan
   said "prefer the assembler — the doubling is not stats-specific". The *fix*
   does belong in the assembler, but must not touch the no-flag path.
   `discover_aitasks_sessions()` (no flag) feeds `monitor_core.py:1805`
   (`{s.session: s.project_root}`), `monitor_core.py:1968`
   (`sorted(s.session …)`), `aitask_projects.sh:282` and
   `aitask_project_resolve.sh:124` — all **session-name oriented**. Two live
   tmux sessions at one repo have distinct session names and are both real;
   collapsing them would delete a live session from monitor's map. All
   `include_registered=True` consumers (`stats_app`, `tui_switcher` ×2,
   `syncer_app`) key identity on `AitasksSession.key`. The flag is already
   exactly the project-oriented vs session-oriented boundary.

2. **Keep the `live_names` name-based skip — do not replace it.** The original
   plan said to make the skip path-based "instead of" name-based. That breaks a
   deliberately pinned test:
   `test_discover_include_registered.py::test_live_entry_dedupes_stale_registered_with_same_project_name`
   puts the live repo at `tmp/shared` and the registry ghost at
   `tmp/no_such_dir` — **different paths, same name**. A key-only dedupe returns
   2 and it fails. It exists for t826_10 ("no STALE ghosts beside live rows").
   The key dedupe is purely **additive**.

3. **`discover_stats_sessions` needs no change.** The original plan listed it as
   a key file needing its own dedupe. Once the assembler is fixed that is a
   duplicated invariant with two places to drift, and it would fix one of four
   consumers. Its real job — dropping `is_stale` — is orthogonal and correct.

4. **The named test-fixture model was wrong.**
   `tests/test_stats_include_registered.py` monkeypatches
   `stats_app.discover_aitasks_sessions` wholesale and never reaches the
   assembler, so it cannot host a characterization test for it. Use
   `tests/test_discover_include_registered.py`'s fixtures
   (`_make_fake_project` / `_make_registry` / `AITASKS_PROJECTS_INDEX`).

5. **There are three duplicate sources, not two** (§"The bug"), and the dedupe
   must reuse `AitasksSession.key`, which already does `os.path.realpath` with
   an `OSError` fallback — no second normalization.

## The bug — three duplicate sources

`AitasksSession.key` is `realpath(project_root)` and is the identity every
registry-inclusive consumer caches, labels and cycles on. Three inputs produce
two records for one repo:

1. **Two live tmux sessions** whose panes walk up to the same project root —
   nothing dedupes live-vs-live.
2. **A registry row whose `name` differs from `project_root.name`** at a path
   that is also live. The skip compares `name`, so it misses this.
   `_build_registry_group_lookup`'s docstring (t1025_1 D3) confirms the
   name≠basename case occurs in practice.
3. **Two registry rows pointing at the same path** under different names.

### Damage, per surface (measured, not inferred)

Probed directly against the real helpers with two live sessions (`sess_a`,
`sess_b`) at `/tmp/repo_one` plus a second repo `/tmp/repo_two`:

- **Stats** — `merge_stats_data` sums the same `StatsData` twice (every counter
  doubles); `multi_session = len(sessions) >= 2` flips true for a single repo;
  `session_breakdown` emits a row per duplicate.
- **TUI switcher — broken, not merely doubled.** `cross_group_step` locates the
  current entry by *first* `key` match, so with a duplicate pair the ring
  **livelocks**: six right-steps from `repo_one` returned
  `['sess_b','sess_b','sess_b','sess_b','sess_b','sess_b']` and **`repo_two` was
  never reachable**. Both duplicate rows also satisfy
  `selected = s.key == self._selected_key`, so **two rows render as selected at
  once**, and `_selected_entry()` (first match) means opening the switcher from
  `sess_b` silently operates on `sess_a`.
- **Labels** — `disambiguate_labels` cannot honour its documented unique-label
  contract because its escalation fallback (`compact_root`) is identical for
  both records; stats' `{s.key: lbl}` map collapses last-wins.

## Switcher semantics — the decision this task makes

Concern raised in review: does collapsing two live sessions at one repo remove a
real, independently-selectable switcher target? **Measured answer: no — that
target is already unreachable**, per the livelock above. The dedupe removes a
phantom row and *restores* cross-repo cycling.

**Decision (explicit, and pinned by tests below):** in every
`include_registered=True` surface the unit of selection is the **repository**,
not the tmux session. This is already the documented t1099 model — `_selected_key`
is the repo key and `_session` is *derived* from it ("the OPERATING session name
… of the selected entry"). One row per repo is therefore the intended semantics,
and the surviving record is the first live one for that repo.

**Accepted consequence:** a second tmux session rooted at the same repo is not a
separate switcher row. It remains fully reachable through tmux itself and
through `ait monitor`, whose no-flag path is untouched by correction 1. Making
two sessions on one repo independently selectable would be a *new feature* with
a different identity model, not a bug fix — out of scope here.

**User-confirmed after review (2026-08-18).** This scope was challenged twice in
review and explicitly decided by the user against two alternatives: deduping in
`discover_stats_sessions` only (zero switcher blast radius, but leaves the ring
livelock and the syncer duplicate unfixed), and deduping everything *except*
live-vs-live (preserves two live rows, but leaves stats doubling for exactly the
duplicate source t1544_3's test targets). The assembler + `include_registered`
scoping was chosen. Do not re-narrow this during implementation without raising
it again.

## Pre-phase (risk mitigations)

1. `[characterize_session_discovery]` **Before** touching
   `_assemble_aitasks_sessions`, add `tests/test_discover_session_dedupe.py`
   with **only** the characterization checks, green against unmodified source.
   It calls `_assemble_aitasks_sessions` **directly**, building the `live_roots`
   tuples the tmux scan would have produced — routing through
   `discover_aitasks_sessions` would pin the `_TMUX` swap, the `subprocess.run`
   fake and the `_walk_up_to_aitasks` patch, plumbing that can redden for
   unrelated reasons (and already covered by
   `test_discover_include_registered.py`, `test_discover_default_unchanged.py`,
   `test_discover_async_parity.py`). Duplicate source 1 is not expressible
   through a tmux fake at all.

   Cases: single live root; live + registered with distinct names; a `STALE`
   registry row (pin that the **assembler keeps it** and the stats predicate
   **drops it**); the `sort(key=session)` ordering; **stability of that sort on
   a session-name tie** (live before registered); and the no-flag call keeping
   **both** live sessions.

   Every check sets `AITASKS_PROJECTS_INDEX`, including live-only ones —
   `_build_registry_group_lookup()` runs unconditionally and would otherwise
   read the developer's real `~/.config/aitasks/projects.yaml`.

   **These must pass unchanged after the edit.** A diff touching one of them in
   the implementation commit is a red flag.

2. `[characterize_switcher_ring]` Pin the switcher ring's **current broken**
   behaviour in `tests/test_switcher_ring_dedupe.py`, using pure helpers
   (`cross_group_ring` / `cross_group_step` — no Textual app): with a duplicate
   pair present, assert the ring has 3 entries, that stepping right repeatedly
   from the duplicated repo never yields the second repo, and that two entries
   share a key. This is a *characterization of the defect*, so it is the one
   pre-phase check that is expected to be **rewritten** in step 6 — it exists so
   the fix is provable rather than asserted, and it is labelled as such in the
   file so a later reader does not mistake it for a desired invariant.

3. `[baseline_live_session_lists]` Capture the **live machine's** session lists
   and compute the prediction the post-phase will be checked against. This is
   the "before" half of the smoke and it **must run here**, before any edit —
   a post-phase step cannot observe pre-change state.

   **There are two distinct lists, not four surfaces.** Verified:
   `monitor_app.py:948` and `minimonitor_app.py:837`/`1009` both reach
   `get_session_to_project_mapping()` → `monitor_core.py:1779` →
   `discover_aitasks_sessions()` with **no flag**; `aitask_board.py` contains no
   `discover_aitasks_sessions` call at all (it only imports `TuiSwitcherMixin`),
   so "the board session list" *is* the `j` switcher overlay. Capture both:

   ```bash
   python3 - <<'EOF'
   import sys; sys.path.insert(0,'.aitask-scripts/lib')
   from collections import Counter
   from agent_launch_utils import discover_aitasks_sessions
   def dump(tag, s):
       print(f"== {tag} ==")
       for x in s: print(x.key, x.session, x.project_name, x.is_live, x.is_stale)
       print("duplicate keys:",
             [k for k, n in Counter(x.key for x in s).items() if n > 1])
   dump("NO-FLAG (monitor / minimonitor) - must be UNCHANGED", 
        discover_aitasks_sessions())
   dump("include_registered=True (j switcher, all hosts) - may SHRINK",
        discover_aitasks_sessions(include_registered=True))
   EOF
   ```

   Read-only: it calls the discovery helper and prints. Then record, in the
   plan's Final Implementation Notes **before** the edit:

   - **List A — no-flag** (monitor's and minimonitor's own session enumeration).
     The fix is gated on `include_registered=True` (correction 1), so the
     prediction is **byte-identical, including any duplicate keys**: two live
     sessions at one repo must still appear as two entries here. Any change at
     all is a regression.
   - **List B — registry-inclusive** (the `j` switcher, from any of the three
     hosts). Record its `duplicate keys` set and the **predicted** after-list:
     for each duplicated key exactly the *first* record survives; every
     non-duplicated row unchanged in name and relative order.

   Do not compare List A against List B or against one shared prediction — they
   are different queries and legitimately differ (A omits inactive registered
   repos and retains live duplicates; B is the opposite on both counts).

## Implementation steps

1. **Pre-phase commit** — add both characterization files, no production change.
   Run them green. If a check is red, the characterization is wrong, not the
   code. **Also run pre-phase item 3 now** and write the captured lists,
   `DUPLICATE KEYS` and the predicted after-list into the Final Implementation
   Notes. Once step 3 lands, that baseline is unrecoverable.

2. **Add the four duplicate-input checks** to `test_discover_session_dedupe.py`,
   still with no production change. They must be **RED** (`2 != 1`) while the
   characterization checks stay green. This is the failing-test baseline.

3. **Add `_dedupe_sessions_by_key`** immediately before
   `_assemble_aitasks_sessions` in `.aitask-scripts/lib/agent_launch_utils.py`:
   a first-wins filter over `AitasksSession.key` returning survivors in input
   order. No `is_live` branch — every live record is appended before any
   registered one, so "first wins" **is** "live wins" structurally. Its
   docstring names the three duplicate sources and the per-surface damage.

4. **Call it inside the `if include_registered:` block**, after the registered
   rows are appended and **before** `found.sort(...)`:
   ```python
   found = _dedupe_sessions_by_key(found)
   ```
   with a comment recording correction 1's reason for not applying it to the
   no-flag path. Leave the `live_names` skip in place (correction 2).

5. **Update the docstrings** — `_assemble_aitasks_sessions` gains a paragraph on
   why the two dedupe layers are not redundant; `discover_aitasks_sessions`'
   "deduped on `project_name`" clause is corrected to describe both layers and
   the `include_registered` scoping.

6. **Rewrite `test_switcher_ring_dedupe.py` to the post-fix invariants** — one
   ring entry per repo, all keys distinct, and a full traversal reaching **every**
   repo (the livelock is gone). Assert the traversal positively (visit every repo
   key in `N` steps), not merely that the ring shrank.

7. **Re-run** → duplicate-input checks green, and the
   `test_discover_session_dedupe.py` characterization checks **unchanged**.

8. **Negative control** — comment out `found = _dedupe_sessions_by_key(found)`:
   exactly the four duplicate checks plus the rewritten switcher-ring checks
   must fail, and the discovery characterization checks must still pass (every
   characterization input has pairwise-distinct realpaths, so the filter is a
   no-op on them). Restore. Then a sharper control: change `key = session.key`
   to `key = str(session.project_root)` — that must fail **only** the symlink
   check, proving it pins the realpath normalization and not string equality.

9. **Add the assembler→stats seam check** to
   `tests/test_stats_include_registered.py` (it already imports `stats_app`, so
   the Textual dependency stays confined): run the **real** assembler, feed its
   output to the real `discover_stats_sessions`, assert the STALE row is
   dropped. Keeps the two halves of the layered contract from drifting.

10. **Ordering is provably untouched for non-duplicates.** `found` is still built
    in today's order; the filter only removes; `list.sort` is stable so
    session-name ties keep insertion order (live before registered). Only inputs
    containing a duplicate key change at all — record this in the Final
    Implementation Notes.

## Post-phase (risk mitigations)

1. `[tui_discovery_smoke_after_dedupe]` **After-only.** Every pre-change
   observation lives in pre-phase item 3; this step only compares against what
   was recorded there. Nothing here re-derives a "before" state.

   **The acceptance criterion is the recorded prediction, not "identical".** A
   bare "same count, same names, same order" cannot distinguish an intended
   removal from a regression, because this fix *is* expected to remove rows in
   some environments.

   1. **Check the two lists against their own baselines** — never against each
      other, and never against one shared prediction.

      **List A — no-flag (`ait monitor`, `ait minimonitor`).** Their session
      enumeration must be **byte-identical** to the List A baseline, duplicate
      live sessions included. This path is not on the change's code path at all,
      so the bar is "unchanged", not "as predicted"; *any* difference is a
      regression. This is the check that catches a dedupe accidentally applied
      to the no-flag path.

      **List B — registry-inclusive (the `j` switcher, from `ait board`,
      `ait monitor` and `ait minimonitor` — all three render the same overlay).**
      Must match the **predicted after-list** from pre-phase item 3. A row
      vanishing whose key was *not* in the recorded duplicate set is a
      regression and blocks the task.

      Note for t1544_7: its checklist (lines 25-29) lists board / monitor /
      minimonitor / switcher as four equivalent "session list" checks. Reword
      them to this A/B split when carrying the checks over — as written, a
      correct change can falsely fail them.

   2. **Duplicated-fixture switcher check (also after-only).** If the recorded
      `DUPLICATE KEYS` was empty (likely — every registered repo currently has
      `name == basename`, which the task file notes is luck, not a guarantee),
      step 1 reduces to "identical" and observes nothing this fix changes. Run
      the switcher against a **disposable** registry instead.

      **Do not touch `~/.config/aitasks/projects.yaml`, and do not use
      `ait projects add` here** — both mutate the user's real registry, and a
      leftover duplicate row would silently change every later discovery. Use
      the `AITASKS_PROJECTS_INDEX` override (honored by `_parse_registry_records`
      at `agent_launch_utils.py:508` and by the bash side), which needs no
      backup because it never writes to the real file:

      ```bash
      FIX=$(mktemp -d)                      # disposable; nothing outside it is touched
      mkdir -p "$FIX/repo_one/aitasks/metadata"
      printf 'project:\n  name: fixture_one\n' \
        > "$FIX/repo_one/aitasks/metadata/project_config.yaml"
      cat > "$FIX/projects.yaml" <<EOF
      projects:
        - name: fixture_one
          path: $FIX/repo_one
        - name: fixture_alias
          path: $FIX/repo_one
      EOF
      # Two registry rows at one path = duplicate source 3, with no tmux setup.
      AITASKS_PROJECTS_INDEX="$FIX/projects.yaml" ait board    # then press j
      rm -rf "$FIX"                         # cleanup: the only state created
      ```

      Expected **after** the fix: the fixture repo renders **once** and
      left/right cycling moves freely to the other repos. The matching
      pre-fix behaviour (two rows, trapped ring) is **not** reproduced by hand
      — `characterize_switcher_ring` pins it in pre-phase and the step-8
      negative control re-demonstrates it on demand, which is a stronger and
      repeatable record than a one-off manual observation.

      Verify `AITASKS_PROJECTS_INDEX` actually took effect before trusting the
      result: the switcher must list `fixture_one` and must **not** list your
      real registered projects. If it does list them, the override did not
      apply — stop and fix that rather than recording a false pass.

   Record the observed lists in the Final Implementation Notes beside the
   prediction, and carry the same checks onto t1544_7's checklist (already
   seeded at lines 25-29).

## Files

- `.aitask-scripts/lib/agent_launch_utils.py` — new `_dedupe_sessions_by_key`;
  one gated call in `_assemble_aitasks_sessions`; two docstring updates.
- `tests/test_discover_session_dedupe.py` — **new**; characterization +
  duplicate-input checks. Script-style `assert_eq` with a `ScriptChecksTest`
  unittest wrapper (t1211). Fixtures **copied**, not cross-imported: there is no
  `tests/conftest.py` or `tests/__init__.py` and no test module in this repo
  imports another.
- `tests/test_switcher_ring_dedupe.py` — **new**; ring/selection invariants over
  the pure helpers.
- `tests/test_stats_include_registered.py` — add the assembler→stats seam check.
- `.aitask-scripts/stats/stats_app.py` — **verified to need no change.**
- `.aitask-scripts/lib/tui_switcher.py` — **verified to need no change**; its
  first-match resolution becomes correct once keys are unique.

## Verification

```bash
python3 tests/test_discover_session_dedupe.py
python3 tests/test_switcher_ring_dedupe.py
python3 tests/test_discover_include_registered.py # name skip survived
python3 tests/test_discover_default_unchanged.py  # no-flag call unchanged
python3 tests/test_discover_async_parity.py       # sync/async parity
python3 tests/test_session_key_collision.py
python3 tests/test_stats_include_registered.py
bash tests/run_all_python_tests.sh --test-dir tests
```

Read only the last line of the suite run (`PYTHON SUITE: PASSED|FAILED
(runner=…, exit=N)`); do not pipe it without `set -o pipefail`.

Then the post-phase smoke, and: with two live tmux sessions rooted at the same
repo, the stats TUI shows that repo **once** with undoubled totals, and the
switcher cycles freely to every other repo.

**Note on `test_discover_async_parity.py`:** its fixture contains duplicate
source #2 live today — registry row `name: pane_alias` at `pane_root`, with
`pane_sess` live at the same root (basename `pane_proj`). It emits 5 records
including a duplicate-key pair and passes only because
`by_session = {s.session: s …}` collapses the two rows both carrying
`session="aitasks"`, last-wins landing on the stale one. After the fix it emits
4; `by_session["aitasks"]` is still the stale row and there is no `len()`
assertion, so **it passes unchanged** — and stops silently exercising the bug.

## Risk

### Code-health risk: medium

- `_assemble_aitasks_sessions` is the shared session-discovery helper behind
  every aitasks TUI, and a wrong dedupe removes a session silently rather than
  failing loudly. The parent rated this **high** on a five-surface blast radius;
  correction 1 narrows it — gating on `include_registered=True` excludes
  `ait monitor` and both shell resolvers **by construction**, leaving three
  consumers that already key on `.key` · severity: medium · → mitigation: inline
  pre-phase characterize_session_discovery, inline pre-phase
  baseline_live_session_lists, inline post-phase tui_discovery_smoke_after_dedupe
- The switcher's selection and cycling semantics change from "one row per
  discovered record" to "one row per repo". Measurement shows the collapsed rows
  are already unreachable (§"Damage, per surface"), so this is a fix — but it is
  a *behavioural* fix to a surface this task was not scoped to touch, and it is
  only safe because it is pinned before and after · severity: medium ·
  → mitigation: inline pre-phase characterize_switcher_ring, inline post-phase
  tui_discovery_smoke_after_dedupe
- Two dedupe layers coexist (name skip + key dedupe) and a future reader may
  delete one as redundant; deleting the name skip reintroduces t826_10's STALE
  ghosts (correction 2) · severity: medium · → mitigation: inline pre-phase
  characterize_session_discovery, plus the step-5 docstring paragraph
- Where a deduped record's label was sourced from the registry `name` rather
  than the directory basename, the rendered label can change. In stats the
  outcome is *order-dependent* — `{s.key: lbl}` is last-wins over a
  session-name sort, so it may already resolve to the live record's basename —
  which makes the change hard to predict per-environment · severity: low ·
  → mitigation: t1568

  User-confirmed after review (2026-08-18): deferring this to the spawned
  follow-up was chosen over preserving the alias inside this task, which would
  have turned the dedupe from a first-wins **filter** into a field **merge**.
  Keep the filter shape.

### Goal-achievement risk: low

- The approach is verified against live source: three duplicate sources
  enumerated, both assembler call sites known (sync + async, parity pinned),
  every consumer of both discovery modes enumerated, per-surface damage measured
  by probe rather than inferred, and the negative control specified with the
  exact mutation and the exact set of checks it must redden · severity: low ·
  → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_session_discovery | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared session-discovery helper feeds every TUI | desc: characterization test pinning `_assemble_aitasks_sessions`'s current non-duplicate output before the dedupe edit
- timing: pre-phase | name: characterize_switcher_ring | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — switcher selection/cycling semantics change | desc: pin the switcher ring's current livelocked behaviour over the pure ring helpers, then rewrite to the post-fix invariants so the fix is provable
- timing: pre-phase | name: baseline_live_session_lists | type: manual_verification | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared session-discovery helper feeds every TUI | desc: capture BOTH discovery lists (no-flag for monitor/minimonitor, include_registered for the j switcher), record duplicate keys and the predicted after-list — the "before" half of the smoke, which cannot run in a post-phase
- timing: post-phase | name: tui_discovery_smoke_after_dedupe | type: manual_verification | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared session-discovery helper feeds every TUI | desc: after-only check of the no-flag list as byte-identical and the registry-inclusive switcher list as matching its prediction, plus a disposable-registry switcher fixture (AITASKS_PROJECTS_INDEX, never the real registry) when the machine has no natural duplicate; reword t1544_7's four-surface checklist to the same A/B split
- timing: after | name: registry_alias_label_decision | type: enhancement | priority: low | effort: low | inline_risk: medium | added_complexity: low | addresses: code-health — a deduped aliased registry row can change the surviving record's rendered label | desc: decide whether the record surviving a key-dedupe should adopt the registry `name` instead of `project_root.name`, and implement the chosen semantics | created: t1568

`characterize_session_discovery` and `tui_discovery_smoke_after_dedupe` are
inherited from the parent's decomposition-time confirmation, dispositioned
**inline** because a decomposed parent reaches neither the Step 7 nor the Step 8d
spawn hook. `registry_alias_label_decision` was surfaced by this verification
pass and confirmed as a spawned `after` task. `characterize_switcher_ring` and
the strengthened smoke were added in response to review.

`baseline_live_session_lists` is **not a new mitigation** — it is the "before"
half of the already-confirmed `tui_discovery_smoke_after_dedupe`, split out
into pre-phase because a post-phase step runs after the production change has
landed and therefore cannot observe pre-change state. The smoke is now
strictly after-only. Splitting it also removed the plan's only destructive
instruction: the duplicated-registry fixture now runs against a disposable
`AITASKS_PROJECTS_INDEX` and never writes to `~/.config/aitasks/projects.yaml`.

**Post-confirmation reassessment (one pass):** the review added one inline
pre-phase (a bounded, independently-verifiable pure-helper test) and tightened
an existing post-phase; neither adds meaningful scope, and the newly confirmed
`after` mitigation is spawned. The switcher finding adds a second affected
surface but also converts an unmeasured fear into a measured, pinned fix — these
offset, so code-health stays **medium**. Goal-achievement stays **low**.

## Notes for sibling tasks

**t1544_3 must record this:** session uniqueness is guaranteed by the
**assembler** (`_assemble_aitasks_sessions`), and **only for
`include_registered=True`**. `discover_stats_sessions` adds no dedupe of its own
— it only filters `is_stale`. A multi-project double-count test should target
the assembler's registry-inclusive path, not the stats wrapper.

`disambiguate_labels` needed no change: its "guaranteed-unique" contract was
violated by duplicate-root *input*, and removing the duplicate at source
restores it.

## Final Implementation Notes

### Pre-phase baseline (captured 2026-08-18, before any edit)

Machine: `omg16`. Captured per pre-phase item 3.

**List A — no-flag (`ait monitor` / `ait minimonitor`)** — 3 entries:

| key | session | project_name | live | stale |
|---|---|---|---|---|
| `/home/ddt/Work/aitasks` | `aitasks` | aitasks | yes | no |
| `/home/ddt/Work/thinking_backend` | `thinking_back` | thinking_backend | yes | no |
| `/home/ddt/Work/thinking_app` | `thinkingapp` | thinking_app | yes | no |

duplicate keys: **none**

**List B — `include_registered=True` (the `j` switcher)** — 7 entries:

| key | session | project_name | live | stale |
|---|---|---|---|---|
| `/home/ddt/Work/aitasks` | `aitasks` | aitasks | yes | no |
| `/home/ddt/Work/aitasks_go` | `aitasks_go` | aitasks_go | no | no |
| `/home/ddt/Work/aitasks_mobile` | `aitasks_mob` | aitasks_mobile | no | no |
| `/home/ddt/Work/teamim` | `teamim` | teamim | no | no |
| `/home/ddt/Work/thinking_backend` | `thinking_back` | thinking_backend | yes | no |
| `/home/ddt/Work/thinking_app` | `thinkingapp` | thinking_app | yes | no |
| `/home/ddt/Work/timexchange` | `timeu` | timexchange | no | no |

duplicate keys: **none**

### Prediction

Both lists have an empty duplicate-key set, so the predicted after-list is
**byte-identical to the baseline for both A and B** — no row is removed on this
machine. Every registered repo here has `name == basename`, which is exactly the
"luck, not a guarantee" case the task file calls out.

**Consequence, per post-phase item 2:** the surface comparison in post-phase
item 1 is therefore *vacuous* on this machine — it observes nothing this change
does. The disposable-registry switcher fixture is **mandatory**, not optional,
and is the only manual evidence that the fix works.

### Post-phase results (2026-08-18, after the fix)

**List A — no-flag:** 3 entries, **byte-identical** to baseline. ✅
**List B — registry-inclusive:** 7 entries, **matches the prediction** exactly;
duplicate keys still `[]`. ✅

Both comparisons are *vacuous on this machine*, exactly as predicted — there
was no natural duplicate to remove. The real evidence is the fixture below.

**Disposable-registry fixture (mandatory here).** Ran against a `mktemp -d`
registry via `AITASKS_PROJECTS_INDEX`; `~/.config/aitasks/projects.yaml` was
never read or written, and the fixture was `rm -rf`'d. Override confirmed
effective (the real registered repos were absent from the result).

Registry: `fixture_one` → `repo_one`, `fixture_alias` → `repo_one` (duplicate
source 3), `fixture_two` → `repo_two`.

| check | result |
|---|---|
| `fixture_alias` present | **False** (deduped) ✅ |
| `fixture_one` present | True ✅ |
| duplicate keys | `[]` ✅ |
| ring entries / distinct keys | 5 / 5 ✅ |
| full right-cycle reaches all repos | **True (5/5)** ✅ |
| `repo_one`, `repo_two` reachable | both True ✅ |

Note: the fixture result carries 5 rows, not 2 — `AITASKS_PROJECTS_INDEX`
overrides the *registry* only, so the machine's 3 live tmux sessions are still
discovered. That does not weaken the check; the alias row is the controlled
variable and it is gone.

### Live TUI verification (performed 2026-08-18)

The post-phase smoke is an **inline** mitigation of this task, so the live
checks were run here rather than deferred. Each TUI was launched in a new
*window* of an existing tmux session — a window does not change the session
list, so discovery was unperturbed (verified: 3 sessions before and after, and
every launched window was removed afterwards).

| check | surface | result |
|---|---|---|
| List A count | `ait monitor` (launched) | header `tmux Monitor — 3 sessions` ✅ matches baseline |
| List A count | `ait minimonitor` | `multi: 3s` ✅ matches baseline |
| List B rows | `ait monitor` → `j` | `aitasks · aitasks_go · aitasks_mob` in the selected group ✅ matches prediction |
| ring traversal | `ait monitor` → `j` → `Right`×8 | crosses all 3 groups and wraps — not trapped ✅ |
| List B rows | `ait board` → `j` | byte-identical overlay to monitor's ✅ confirms board has no separate session list |

**Live duplicate fixture (the discriminating check).** With
`AITASKS_PROJECTS_INDEX` pointed at a disposable registry carrying
`fixture_one` and `fixture_alias` at the *same* path, `ait monitor` → `j`
rendered:

```
Session: ▶ aitasks (aitasks)   aitasks (fixture_one)   aitasks (fixture_two)
         thinking_back   thinkingapp
```

`fixture_alias` is **absent** — the duplicate collapsed in a real UI. The three
colliding `aitasks` session names each escalate to a distinct
`aitasks (<project>)` label, i.e. `disambiguate_labels`' unique-label contract
is visibly restored. `ait board` → `j` rendered the identical overlay.

**Live negative control.** With `_dedupe_sessions_by_key` disabled and the same
fixture, the overlay grew a sixth row — `aitasks (fixture_alias)` — proving the
live check discriminates rather than passing vacuously. The source was restored
immediately and re-verified (0 mutation markers; 38/38 and 10/10 green).

**Two live checks not obtained, with their standing evidence:**

- *`ait minimonitor` launched by me* — `aitask_minimonitor.sh:64` refuses to
  start when it finds a monitor marker on a pane in scope ("A monitor is
  already running in this window"). The `multi: 3s` reading above therefore
  came from an already-running minimonitor rather than one I started. That is
  adequate for List A (whose criterion is *unchanged*, so pre- and post-fix
  readings must agree) but is not proof of post-fix code.
- *The ring trap seen inside a live TUI* — Textual renders selection with
  colour attributes my capture could not isolate, so selection movement was not
  observable in the pane text. The trap and its removal are pinned
  deterministically instead by `tests/test_switcher_ring_dedupe.py` and its
  negative control (with the dedupe disabled, 3 right-steps visit 1 repo
  instead of 3).

t1544_7's checklist was reworded in this change to the A/B split; its previous
four-surface wording could have failed a correct change.

### Actual work done

- `_dedupe_sessions_by_key()` added to `agent_launch_utils.py` — a first-wins
  filter over `AitasksSession.key`, called from `_assemble_aitasks_sessions`
  **inside the `if include_registered:` block only**.
- Two docstrings corrected (`_assemble_aitasks_sessions`, and
  `discover_aitasks_sessions`' stale "deduped on `project_name`" clause).
- `tests/test_discover_session_dedupe.py` (new, 38 checks),
  `tests/test_switcher_ring_dedupe.py` (new, 10 checks), and an
  assembler→stats seam check appended to `tests/test_stats_include_registered.py`.
- `stats_app.py` and `tui_switcher.py`: **unchanged**, as the plan predicted.

### Deviations from plan

1. **Switcher-ring test is driven by assembler output, not hand-built session
   lists.** The plan said "using pure helpers". While writing it I found that
   `cross_group_ring` / `cross_group_step` are pure and *unchanged* by this
   task — they remain duplicate-fragile by construction. A hand-built duplicate
   list would therefore livelock identically before and after the fix, proving
   nothing. The invariant this task actually establishes is one level up
   (*discovery never hands the ring duplicates*), so the ring is fed
   `_assemble_aitasks_sessions` output. Still no Textual app is mounted.
2. **Negative-control expectation widened.** The plan predicted the mutation
   would redden "the four duplicate checks plus the rewritten switcher-ring
   checks". Measured: 8 assertions across those four checks, and 8 across the
   ring file. Both characterization sets stayed green, which is the property
   that mattered.

### Issues encountered

- The first commit attempt used `git commit -o -- <paths> -m <msg>`; `-m` after
  `--` is parsed as a pathspec. Corrected to `-F <file>` before `--`.
- The working tree carried 16 unrelated pre-existing modifications (in-flight
  `task-workflow` / worktree-helper work). Every commit here was made
  path-scoped with `git commit -o -- <paths>` so none of it was swept in.

### Key decisions

- **Dedupe gated on `include_registered=True`** — user-confirmed after review,
  against two narrower alternatives. The no-flag path feeds `ait monitor`'s
  `{session: project_root}` map and its session-name list, where two live
  sessions on one repo are both real.
- **The `live_names` name skip was kept**, not replaced. It is the only thing
  that drops a STALE ghost sharing a name with a live repo at a *different*
  path (pinned by t826_10's test, which still passes).
- **The dedupe stays a filter, never a field merge** — user-confirmed. The
  registry-alias label question is deferred to the spawned follow-up.

### Upstream defects identified

- `.aitask-scripts/lib/agent_launch_utils.py:1052-1100` — `cross_group_ring` /
  `cross_group_step` locate the current entry by *first* `.key` match, so any
  caller that hands them two entries sharing a key gets a livelocked ring with
  other repos unreachable. t1544_1 removes the only known producer of such
  input (discovery), but the helpers remain duplicate-fragile by construction
  and would break again for any future duplicate source. A defensive guard or
  documented precondition there is worth a separate task.

### Notes for sibling tasks

**t1544_3:** session uniqueness is guaranteed by the **assembler**
(`_assemble_aitasks_sessions`) and **only for `include_registered=True`**.
`discover_stats_sessions` adds no dedupe of its own — it only filters
`is_stale`. Target the assembler's registry-inclusive path in the
"no double-count" test, not the stats wrapper.

`disambiguate_labels` needed no change: its unique-label contract was violated
by duplicate-root *input*, and removing the duplicate at source restores it.
