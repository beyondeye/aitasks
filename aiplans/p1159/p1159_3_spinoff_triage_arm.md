---
Task: t1159_3_spinoff_triage_arm.md
Parent Task: aitasks/t1159_shadow_review_loop_automation.md
Sibling Tasks: aitasks/t1159/t1159_4_docs_and_integration.md, aitasks/t1159/t1159_5_manual_verification_shadow_review_loop_automation.md, aitasks/t1159/t1159_6_minimonitor_concern_status_line.md, aitasks/t1159/t1159_7_refactor_review_loop_post_review_accretion.md
Archived Sibling Plans: aiplans/archived/p1159/p1159_*_*.md
Worktree: . (current directory — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-13 12:28
---

# Plan — t1159_3: Picker spin-off triage arm

Parent design: `aiplans/p1159_shadow_review_loop_automation.md`. Depends on
t1159_1 (**landed 2026-08-11**) for `block_meta` keyword ordering; t1159_2
(**landed 2026-08-13**) is independent of this child.

## Context

Shadow reviews surface secondary concerns that either bloat the plan (the user
iterates until it is "complete" but no longer steerable) or get lost — the
folded-t1017 steerability requirement of t1159. The picker already has per-row
tri-state from t1427 (`_ConcernRow`: none ☐ / forward ☑ / rejected ✗; bulk keys
removed by design). This child adds the fourth mutually-exclusive state
**spinoff** (`»`, key `t`), routing a concern to "park as its own task" — so the
user controls what enters the plan versus what gets tracked separately.

## Pinned decisions (user-confirmed at parent planning — do not reopen)

- Picker creates tasks directly, as **drafts** (no `--commit`): offline-safe in
  a TUI worker, reversible, anti-bloat. Drafts land in `aitasks/new/` with **no
  ids** until finalization — report **draft paths**, never ids.
- Provenance: `--followup-of <task_id>` (the **reviewed** task from the picker
  context) + `--followup-kind review_finding`.
- Collision-safe naming via a per-batch cross-process nonce
  (`uuid.uuid4().hex[:8]`) + 1-based index.
- Post-creation store write: `aitask_shadow_rejected.sh add <task_id>
  --producer spinoff` (suppresses the now-tracked concern next round; the t1427
  store is used exactly as designed — task-scoped, no layout change).

## Verification pass — findings against `main` (2026-08-13)

Every seam re-verified against the live tree. All structures are intact; line
numbers drifted (t1159_2, t1453, t1493, t1495 landed since this plan was
written). **Use these, not the originals:**

| seam | plan said | actual |
|---|---|---|
| `ConcernPickResult` | 1868-1883 | **2005-2019** |
| `_CONCERN_MARKS` | ~1911 | **2048-2052** |
| `_NARROW_PREFIX_COLS` | — | **2057** (= 8) |
| `_ConcernRow` / its `on_key` | 1923-2099 | **2060-2234** / **2204** |
| `ConcernPickerModal` | — | **2513** |
| `_CONCERN_HELP_FULL` / `_COMPACT` | — | **2265-2275** |
| `_context_line()` | 2495-2503 | **2666-2682** |
| `_result()` | 2607-2612 | **2797-2802** |
| `apply_concern_pick_result` | 665-705 | **691-731** |
| `_run_rejected_cmd` | ~620-645 | **629-671** |
| `_persist_concern_dispositions` | 707-736 | **733-762** |
| `rejection_outcome_message` | 738-760 | **764-786** |
| `get_draft_filename()` | 601-607 | **604-609** |

**Five substantive corrections** to the plan as originally written:

1. **RESOLVED — the plan's flagged uncertainty about `--followup-of` /
   `--followup-kind` on the draft path.** Both **do** flow through it.
   `resolve_anchor` is called at `aitask_create.sh:2054`, *before* the
   `if [[ "$BATCH_COMMIT" == true ]]` split, and `create_draft_file`'s renderer
   emits `anchor: $RESOLVED_ANCHOR` (`:710-712`) and
   `followup_kind: $BATCH_FOLLOWUP_KIND` (`:713-716`). `--followup-kind` is
   validated pre-write at `:2037`. **Drop the plan's contingency** ("if
   `--followup-of` resolution fails, record the anchor in the description
   prose") — replaced by the precise failure contract in item 2.
2. **`--followup-of` CAN fail the whole creation, in exactly one narrow case.**
   Its branch calls `normalize_anchor_id` (`lib/task_utils.sh:885-903`), which
   `die`s on a malformed id **or** a `STATUS:NOT_FOUND`. Archived tasks are
   **not** a failure — `task-status` resolves them (probed live: archived
   `1159_1` → `STATUS:Done`). Only an id matching no task at all dies. The
   *anchor value* resolution beyond that is fail-open (missing file ⇒ parent id
   for `N_M`, else the id). So: no preflight and no prose fallback — the generic
   per-concern nonzero-rc path handles it, and because the store write follows
   success only, a failed concern is **not** suppressed and returns next round.
3. **The AST-guard step (original step 6) is wrong as written and must be
   inverted.** `EXPECTED_ACCESSES` is matched **exactly and bidirectionally**
   (`assertEqual(got, expected)`,
   `tests/test_concern_body_display_contract.py:472-475`); a declared row with
   no observed access fails as "declared reads that vanished" (`:444-445`,
   `:459-461`). The spin-off description builder calls
   `concern_parser.concern_marker_line(c)` — already registered FORWARD at
   `("concern_parser.py", "concern_marker_line", "c")` (`:113-114`) — so it
   performs **no direct `.body` read** and needs **no new row**. Adding one
   would turn the guard red. The correct action: **register nothing**, and let
   the unmodified guard's continued pass be the assertion that the builder
   routed through the canonical renderer instead of reading `.body` itself.
4. **A third `ConcernPickResult` construction site the plan missed.** With
   `spun_off` declared **no-default**, all four must be amended in one commit:
   `monitor_shared.py:2798` (prod), `tests/test_concern_picker_modal.py:284`,
   `tests/test_minimonitor_concern_action.py:241`, and — **new to this plan** —
   `tests/test_monitor_concern_action.py:277-282` (`_pick_result` helper).
5. **The name cap is `sanitize_name`'s `cut -c1-60`, and it truncates from the
   RIGHT** (`aitask_create.sh:1447-1451`) — it would eat the nonce and index,
   which is precisely the collision the suffix-preserving rule exists to
   prevent. It also **deletes** every character outside `[a-z0-9_]`
   (`tr -cd`), rather than replacing them: a real region like
   `authoring-conv.md:103` becomes `authoringconvmd103`. **The budget must
   therefore be computed against the post-sanitization length**, not the raw
   region.

6. **The store's mutex is per-task and NOT producer-scoped, so a second worker
   self-contends** (`aitask_shadow_rejected.sh:40-45`, `:138-183`, `:458` — one
   `LOCK_DIR` via `lib/registry_lock.sh`; exit **3 `LOCK_BUSY`** means
   **nothing was written**, `:73`). `_persist_concern_dispositions`' docstring
   (**733-739**) already records the rule: its two subcommands are sequential
   because "issuing them together would just make one of them report
   `LOCK_BUSY` against ourselves". A separate `group="shadow-spinoff"` worker
   would reintroduce exactly that for any **mixed** confirmation (some rejected
   + some spun off) — and it loses **worse** than the rejection case: by then
   the draft is already on disk, so a lost store write means the concern is not
   suppressed, the shadow raises it again next round, and a re-spin creates a
   **second draft**. The per-batch nonce cannot dedupe them — it is *designed*
   to make each batch's paths distinct. Fixed structurally in step 4 (one
   serialized worker) and step 5 (one batched `add`), with the residual
   partial-failure made explicit rather than swallowed.
7. **Count-and-directory reporting does not satisfy the pinned "report draft
   paths" decision.** `aitasks/new/` is a shared drop directory and
   `get_draft_filename` is only minute-precision, so "N concern(s) parked as
   drafts in `aitasks/new/`" leaves the user unable to identify *which* files
   this confirmation produced — exactly the case concurrent work makes common.
   Step 5 now surfaces the full paths plus the batch nonce as a selector.
   (`ConcernBlockInspectModal` is **not** the surface for this: it is
   specifically the raw *concern-block* view, `markup=False`, from t1293 —
   reusing it for a path list would misuse a named surface.)

8. **Nothing guards the confirmation's *effects*, and the duplicate window is
   wider than the in-flight one.** Three verified facts compound:
   - The only existing guard, `_concern_pick_busy`, is **monitor-only**
     (`monitor_app.py:621`, acquired `:2973`) and its docstring scopes it to
     "stops a second `c` over the **open picker** stacking another one". It is
     released at `:3124` — **one line before** `apply_concern_pick_result` at
     `:3125` — so it never covers the worker.
   - **Minimonitor has no such guard at all** (`_on_concerns_picked`,
     `:2857-2867`: "this app holds no pick guard to release").
   - The picker shows `concerns` **unfiltered** (`minimonitor_app.py:2843`);
     `rejected_entries` feeds only the `R` view, and t1427's suppression is
     applied **producer-side at the next shadow round**, not by the picker.

   So a user can re-open the picker — during the worker, or any time after it
   on an unchanged block — and spin the same concern off again. The per-batch
   nonce **cannot** dedupe that; it exists to make batches distinct. Rejections
   never needed a guard because a repeated `add` is harmless; a repeated
   spin-off writes a **second file**. Fixed at both layers: a mixin-owned
   in-flight effect guard (step 4) and a store-based pre-creation skip
   (step 5).

Confirmed unchanged and load-bearing:

- **`»` (U+00BB) is East-Asian-Width *Ambiguous* = width 1**, the same class as
  the existing `☐` / `☑` / `✗`, so the `_NARROW_PREFIX_COLS = 8` budget
  (mark 1 + 2 spaces + `HIGH` 4 + 1 separator) is unaffected — which is exactly
  what the contract comment at `:2044-2047` requires of any new mark.
- **`t` follows a proven precedent.** It is App-bound in `monitor_app.py:496`
  (`scroll_preview_tail`) — but so is `r` (`:490`, `refresh`), and t1427
  shipped `r` in `_ConcernRow.on_key` with `prevent_default()`/`stop()`
  without incident. `ConcernPickerModal` is a `ModalScreen` and rows are
  focused on mount.
- **Both TUIs are covered for free**: `apply_concern_pick_result` is called
  from `minimonitor_app.py:2865` and `monitor_app.py:3125`, so the mixin change
  reaches both with no per-app edit.
- `--silent` prints **exactly one line**, the created path
  (`aitask_create.sh:2185-2189`); the draft branch is `:2175-2183`.
- `--producer` takes arbitrary values, sanitized at the write site
  (`aitask_shadow_rejected.sh:267-271`: `|` → space, newlines stripped,
  trimmed, empty ⇒ `unknown`). `spinoff` is safe.
- `Concern.priority` ∈ {high, medium, low} — feeds `--priority` directly.
- `ait_atomic_render` (`lib/atomic_write.sh:159-174`) resolves and commits over
  an existing path **silently** — the basis of the collision hazard.
- **Concurrent-session note:** `aitask_create.sh` currently carries uncommitted
  t1496 changes, but they are confined to *child*-creation locking
  (`acquire_child_lock` / `release_child_lock` / `finalize_draft`'s child
  branch). This task creates **parentless** drafts and needs **no edit** to
  that file. Stage only this task's files at commit time.

## Pre-phase (risk mitigations)

1. **[characterize_picker_help_budget]** Before adding `t` to either help
   string, add a characterization test to `tests/test_concern_picker_modal.py`
   that renders the picker at the **xnarrow** tier (24 cols, the
   `_PICKER_MIN_COLS` floor) and pins, on the **composited strip**, that the
   compact help line is present and the concern rows are not evicted. Then,
   after step 3 lands, re-assert the same at the same width with the fourth key
   present. `_CONCERN_HELP_COMPACT` is already tuned to ~50 columns and its
   comment (`:2270-2275`) records that the full line wraps to five rows and
   evicts the buttons there — a fourth key spends budget that is documented as
   already scarce. If it no longer fits, shorten the compact token (e.g.
   `t task`) rather than widening the modal. Same shape and rationale as
   t1159_1's `narrow_width_context_budget`.

2. **[pin_real_create_draft_contract]** Add a shell test that runs the **real**
   `aitask_create.sh` once, in a tmpdir repo, with the exact argv this feature
   emits (`--batch --silent --name … --desc-file - --priority … --labels …
   --followup-of <id> --followup-kind review_finding`, no `--commit`), and
   asserts the created draft carries `anchor:`, `followup_kind: review_finding`,
   `draft: true`, and that **stdout is exactly one line** — the draft path.
   Every Python test in this task spies `_run_create_cmd`, so **no test would
   ever execute the real script**: without this, a flag-contract drift in
   `aitask_create.sh` leaves the whole suite green and the feature dead on
   disk. Include the negative control: `--followup-of` naming a nonexistent id
   exits nonzero (the item-2 failure contract).

## Steps

1. **`monitor_shared.py` — row state**
   - `_CONCERN_MARKS` (**2048-2052**): add `"spinoff": "[bold cyan]»[/]"`.
     Single-width, so the `_NARROW_PREFIX_COLS` contract stated on the dict
     stays true; extend that comment to name the fourth mark.
   - `_ConcernRow` (**2060-2234**): fourth mutually-exclusive state
     `"spinoff"`; `toggle_spinoff()` beside `toggle_forward`/`toggle_reject`;
     property `spun_off`; `t` in `on_key` (**2204**) with
     `prevent_default()`/`stop()` exactly like `space`/`r`. Update the
     tri-state docstring (**2064-2069**) to quad-state.
   - `set_state` (**2161-2171**) already re-classes only on a real change and
     drives the `rejected` CSS class; leave that rule intact (spinoff needs no
     dim class — the cyan `»` is the signal).

2. **`ConcernPickResult`** (**2005-2019**): add `spun_off: list["Concern"]`
   **with no default**. Amend **all four** construction sites (correction 4) in
   the same commit, and update the "Three independent output channels"
   docstring to four.
   `_result()` (**2797-2802**) gains
   `spun_off=self._concerns_in_state("spinoff")` — `_concerns_in_state`
   (**2794-2795**) already sorts by `original_index`, so input order is free.

3. **Modal text**: `_CONCERN_HELP_FULL` / `_CONCERN_HELP_COMPACT`
   (**2265-2275**) gain a spin-off key (`\[t] spin off` / `t task`);
   `_context_line()` (**2666-2682**) wording → "forward, reject, or spin off"
   on **both** return shapes, keeping `meta_suffix` last. Update the
   "Per-row actions only (t1427_2)" paragraph (**2526-2531**).

4. **`apply_concern_pick_result`** (`ShadowRejectionsMixin`, **691-731**) —
   restructured so a spinoff-only result still dispatches, and so **every
   store-touching effect of one confirmation runs in ONE worker** (correction
   6). Forwarding (the clipboard write, **707-712**) is untouched and stays
   synchronous.

   ```python
   if not (result.rejected or result.unrejected or result.spun_off):
       return

   if not task_id:
       # Visible refusal naming exactly what was skipped — never a silent
       # drop. Rejections-only keeps today's wording verbatim.
       self.notify(_no_task_id_msg(result), severity="warning")
       return

   # In-flight EFFECT guard (correction 8), keyed by task id — the store and
   # --followup-of are both task-keyed, so two panes on different tasks may
   # proceed in parallel while two confirmations on the same task may not.
   if task_id in self._concern_effects_inflight():
       self.notify(
           f"Concern effects for t{task_id} are still running — wait for "
           "them to finish before confirming again",
           severity="warning",
       )
       return
   self._concern_effects_inflight().add(task_id)

   # ONE worker, not two. The rejection store takes a single per-task mutex
   # that is NOT producer-scoped, and `_persist_concern_dispositions` is
   # already sequential for that exact reason. A second concurrent writer
   # would report LOCK_BUSY against ourselves — and lose worse here, because
   # the draft is on disk before the store write is attempted.
   self.run_worker(
       self._apply_concern_side_effects(result, task_id),
       exclusive=False, exit_on_error=False, group="shadow-concern-effects",
   )
   ```

   ```python
   async def _apply_concern_side_effects(self, result, task_id: str) -> None:
       """Serialize every store-touching effect of one confirmation."""
       try:
           if result.rejected or result.unrejected:
               await self._persist_concern_dispositions(result, task_id)
           if result.spun_off:
               await self._spawn_concern_tasks(result.spun_off, task_id)
       finally:
           # MUST be `finally`: the worker runs with exit_on_error=False, so a
           # raise is swallowed, and a leaked guard would wedge every later
           # confirmation for this task. `_on_inspect_closed`
           # (monitor_app.py:3127-3134) exists only because one release path
           # was missed once — do not repeat it.
           self._concern_effects_inflight().discard(task_id)
   ```

   **The guard belongs to the mixin, not to the apps** — it is lazily created
   so neither app has to initialize it:

   ```python
   def _concern_effects_inflight(self) -> set[str]:
       """Task ids whose confirmation effects are still running (t1159_3)."""
       inflight = getattr(self, "_concern_effects_inflight_set", None)
       if inflight is None:
           inflight = set()
           self._concern_effects_inflight_set = inflight
       return inflight
   ```

   App-owned is exactly how the existing gap arose: `_concern_pick_busy` lives
   in `monitor_app` and minimonitor never grew an equivalent. Putting this on
   `ShadowRejectionsMixin` — the seam both apps already route through, and for
   the same reason `apply_concern_pick_result` lives there — makes the gap
   structurally impossible rather than a rule to remember in two places.
   `_concern_pick_busy` is **left exactly as it is**: it guards modal
   stacking, a different question, and narrowing or widening it here would
   change monitor behavior this task has no mandate over.

   `_no_task_id_msg` composes from the non-empty sets: rejections only →
   `"Rejections not persisted — no task id for this pane"` (**byte-identical to
   today**, `:720-723`); spin-off only → `"Spin-off skipped — no task id for
   this pane"`; both → `"Rejections not persisted, spin-off skipped — no task
   id for this pane"`. The existing assertions
   (`test_minimonitor_concern_action.py:598-599`,
   `test_monitor_concern_action.py:680-681`) check the lowercased substrings
   `"no task id"` and `"not persisted"`, so all three forms keep them where
   rejections are involved.

5. **`_spawn_concern_tasks` + the `_run_create_cmd` subprocess seam**
   - Add `_CREATE_SH = _SCRIPT_DIR / "aitask_create.sh"` beside `_REJECTED_SH`
     (**286**) and a `_CREATE_CMD_TIMEOUT` beside `_REJECTED_CMD_TIMEOUT`
     (**291**).
   - `_run_create_cmd(args, stdin_text)` — extract beside `_run_rejected_cmd`
     (**629-671**), copying its contract verbatim: stdin-fed, total (never
     raises), kill-then-reap on timeout, returns `(rc, out)`. Tests override it,
     so no bash runs in the Python suites.
   - **Pre-creation skip against the store** (correction 8, the layer the
     in-flight guard does not reach). First thing in the worker, re-read the
     store with the existing `_fetch_rejected_entries(task_id)` (**673-689**)
     and drop any concern whose `concern_marker_line(c)` already appears as an
     entry's `marker_line` **with `producer == "spinoff"`**. Re-read inside the
     worker rather than reusing the picker-open `entries`: those are stale by
     exactly the batch being guarded against. Byte-for-byte equality is the
     sound comparison here — `concern_marker_line`'s docstring
     (`concern_parser.py:748-751`) already pins that store entries and fresh
     concerns must agree byte-for-byte, which is the same contract t1427's
     suppression relies on. Filtering on `producer` matters: a concern that was
     *rejected* (producer `picker`) has not been spun off and must still be
     creatable. Report skips distinctly: `"N concern(s) already spun off —
     skipped"`. This is **fail-open by construction** — `_fetch_rejected_entries`
     returns `[]` for every non-success outcome, so an unreadable store creates
     anyway rather than silently dropping the user's request.
   - Naming, per correction 5. Compute against the **post-sanitization** length:
     normalize the region the way `sanitize_name` will (lowercase, drop every
     character outside `[a-z0-9_]`, collapse runs of `_`, strip leading/trailing
     `_`; empty ⇒ `concern`), then truncate **the region segment only** to
     `60 - len("shadow_") - 1 - 8 - 1 - len(str(i))` characters, and assemble
     `shadow_<region>_<nonce>_<i>` with `nonce = uuid.uuid4().hex[:8]` computed
     **once per batch** and `i` 1-based. The nonce and index are never
     truncated — that is the whole point, since `cut -c1-60` cuts the tail.
   - Argv per concern: `--batch --silent --name <name> --desc-file -
     --priority <c.priority> --labels shadow-concern --followup-of <task_id>
     --followup-kind review_finding`. No `--commit`.
   - Stdin description:
     `Spun off from a shadow review concern on t<task_id>.\n\n<concern_marker_line(c)>\n`
     — via `concern_marker_line`, the canonical FORWARD renderer (correction 3).
   - Collect the single stdout line per success as a draft **path**, keeping
     each path paired with its concern (the pairing is what makes the batched
     store write below correct).
   - **Report the paths, not a count** (correction 7). The notify lists every
     created draft path, one per line, and names the batch nonce as a selector
     so the set stays identifiable while other sessions write into the same
     directory:

     ```
     2 concern(s) parked as drafts — finalize with 'ait create':
       aitasks/new/draft_20260813_1042_shadow_pickermodal_a1b2c3d4_1.md
       aitasks/new/draft_20260813_1042_shadow_parsermod_a1b2c3d4_2.md
     (this batch: ls aitasks/new/*a1b2c3d4*)
     ```

     Paths are `escape()`d — they reach a markup-enabled surface and a region
     is producer-derived text. Cap the inline listing at a small N (list the
     first few, then `… and K more`), with the nonce selector always present
     so nothing is unrecoverable.
   - **One batched store write for the whole successful set**, mirroring
     `_persist_concern_dispositions` (**740-746**) exactly: a single
     `_run_rejected_cmd(["add", task_id, "--producer", "spinoff"], stdin)`
     with `concern_marker_line(c) + "\n"` per successfully-created concern.
     One mutex acquisition instead of N, and one partial-failure surface
     instead of N. Reuse `rejection_outcome_message` (**764-786**) for the
     exit-code vocabulary.
   - **Partial-failure contract — make it visible, never swallow it.** The
     outcomes are exhaustive and separately reported:
     - *all concerns skipped by the store check* → no create, no store write,
       no success claim: only the "already spun off — skipped" message. An
       empty successful set must never reach the batched `add` as a no-op
       call.
     - *create failed* → nothing on disk, nothing written to the store, the
       concern returns next round. Report the count and the helper's first
       line; do **not** claim success.
     - *created + store add succeeded* → the success notify above.
     - *created + store add failed* (e.g. `LOCK_BUSY` from a genuinely
       concurrent other TUI) → the drafts **exist but are not suppressed**.
       Warn distinctly, list the paths, and say so plainly: `"N draft(s)
       created but NOT suppressed (<reason>) — the same concern(s) will be
       raised again next round; spinning them off again would create duplicate
       drafts."` This is the one state a user must not misread, and it is
       reachable even after serialization, so it gets its own message rather
       than being folded into the success or the failure path.

6. **AST guard — assert, do not register** (correction 3). Make no edit to
   `tests/test_concern_body_display_contract.py`; its unmodified pass is the
   proof that the description builder went through `concern_marker_line`.

## Verification

- **Modal** (`tests/test_concern_picker_modal.py`, real `run_test` + `pilot.press`):
  `t` toggles spinoff (glyph `»`); mutual exclusivity across **all four** states
  (each of space/`r`/`t` clears the other two); `spun_off` carries original
  input order; an all-empty result stays distinct from `None` (cancel); both
  help strings name the key; plus the pre-phase narrow-width characterization
  and its post-change re-assertion.
- **Flow** (`tests/test_minimonitor_concern_action.py`, extending `_mk_app`
  with a `_run_create_cmd` spy alongside the existing `_run_rejected_cmd` one —
  `run_worker` is already driven to completion via `asyncio.run`):
  `_run_create_cmd` called once per concern with `--batch --silent
  --desc-file -` plus `--followup-of` / `--followup-kind review_finding` in
  argv and the canonical marker line on stdin; **spinoff-only result still
  dispatches** (the step-4 restructure); no task id → warning and **zero**
  subprocesses, with the message asserted for all three set-combinations
  (rejections-only byte-identical to today); store
  `add --producer spinoff` follows success **only** — a nonzero create rc
  writes nothing — and is **one batched call**, not one per concern.
- **Serialization (correction 6):** a **mixed** confirmation (forward +
  reject + spinoff in one confirm) issues **exactly one** `run_worker` call,
  and the recorded store argv sequence is strictly ordered —
  `add --producer picker` completes before `add --producer spinoff` begins,
  never interleaved. Negative control: assert the code path does not take two
  `run_worker` calls, since the harness's `run_worker` runs each coroutine to
  completion synchronously and would therefore mask real concurrency — so the
  guard must be the **call count and argv order**, not wall-clock overlap.
- **Forced lock-busy recovery (correction 6):** extend `_mk_app` with
  `create_rc` / `create_out` beside the existing `rejected_rc` / `rejected_out`
  (the LOCK_BUSY pattern at `test_minimonitor_concern_action.py:611-613` is the
  template). Drive *create succeeds, store `add` returns `(3, "LOCK_BUSY")`*:
  the draft paths are still reported, the notify carries the distinct
  **"created but NOT suppressed"** wording and the duplicate warning, severity
  is `warning`, and — negative control — the rejection half of a mixed
  confirmation still reports its own outcome independently. Repeat for
  `(4, …)` to confirm the message is driven by `rejection_outcome_message`
  rather than hardcoded to LOCK_BUSY.
- **Path reporting (correction 7):** the success notify contains each created
  draft **path** and the batch nonce; assert **no task id** appears (the drafts
  have none — the anti-regression for the pinned decision), and that two drafts
  from one confirmation are both listed.
- **Re-entrancy, in BOTH TUIs (correction 8)** — the guard tests must run
  against `MiniMonitorApp` *and* `MonitorApp` harnesses, since the whole point
  is that the two apps previously differed:
  - confirming again **while effects are in flight** → the second confirmation
    is refused with the visible message, `run_worker` is called **once**, and
    **zero** additional `_run_create_cmd` calls are made. Drive this by making
    the seam await a gate the test controls, so the guard is observed while
    genuinely held — the harness otherwise runs each worker to completion
    synchronously and the window would never exist to test;
  - after completion the guard is **released** — a later confirmation on the
    same task is accepted and does create (proves a guard, not a wedge);
  - **guard release on a raising worker** — force `_run_create_cmd` to raise;
    the next confirmation is still accepted. This is the `finally` negative
    control, and it fails against an implementation that releases on the
    success path only;
  - two **different** task ids confirm concurrently → both proceed (the key is
    per-task, not global).
- **Store-based skip (correction 8):** a concern whose marker line is already
  in the store with producer `spinoff` → **no** create subprocess, counted in
  the "already spun off — skipped" message; positive control — the same marker
  line with producer `picker` (rejected, never spun off) → **still created**;
  fail-open control — an unreadable store (`_fetch_rejected_entries` → `[]`)
  → created anyway, never silently skipped.
- **Collision:** two same-region concerns in one confirmation → distinct names
  and distinct paths, both created; two distinct confirmations with the clock
  frozen to an identical minute (`get_draft_filename` is minute-precision) →
  distinct paths via distinct nonces, the first batch's drafts intact. Plus an
  over-long region: the assembled name is ≤60 chars **and still ends with**
  `_<nonce>_<i>` after `sanitize_name`.
- **Monitor parity:** `tests/test_monitor_concern_action.py` — its
  `_pick_result` helper amended; the full monitor's spin-off path dispatches
  identically through the shared mixin.
- Both pre-phase mitigations above.
- `bash tests/run_all_python_tests.sh` — read **only** the final stderr verdict
  line (`set -o pipefail` or `${PIPESTATUS[0]}` if piping).
- Live behavior is already covered by **t1159_5**, whose
  `verifies: [t1159_1, t1159_2, t1159_3, t1159_4]` includes this child — no new
  manual-verification task is needed.
- Reference **Step 9 (Post-Implementation)** of the task-workflow skill for
  cleanup, archival, and merge.

## Risk

Levels below are the **reassessed** ones, taken against the plan as augmented
with the two confirmed inline pre-phases (per `risk-evaluation.md`'s
reassessment note) **and** with the plan-review rounds' corrections 6, 7 and 8
folded in. Both dimensions stay `medium`: the mitigations close the
display-budget and real-script-contract gaps and the serialization fix is
structural rather than an invariant to remember, but the no-default field
fan-out and the new non-idempotent effect class are inherent to the change.

### Code-health risk: medium
- `ConcernPickResult` gains a no-default field with four construction sites
  across three test files plus production; a missed site is a `TypeError` on a
  modal-dismiss callback path · severity: medium · → mitigation: all four sites
  (correction 4) amended in the same commit — a no-default field makes a missed
  site a loud construction failure, never a silent wrong default
- A new **effect class** lands in a mixin shared by both TUIs: the picker now
  *creates files* via subprocess, where it previously only wrote the rejection
  store. The effect is non-idempotent — a repeated run creates duplicate drafts,
  and `ait_atomic_render` overwrites an existing path silently · severity:
  medium · → mitigation: per-batch nonce + 1-based index (step 5), pinned by the
  same-minute frozen-clock and two-same-region collision tests
- `_CONCERN_HELP_COMPACT` is documented as already at its column budget at the
  24-col tier; a fourth key can evict the rows or buttons · severity: medium ·
  → mitigation: inline pre-phase characterize_picker_help_budget
- Two concurrent workers would self-contend on the store's per-task,
  non-producer-scoped mutex; the loser writes nothing while the draft is
  already on disk, so the concern returns next round and a re-spin duplicates
  it · severity: high · → mitigation: structural — one serialized worker
  (step 4) and one batched `add` (step 5), pinned by the mixed-confirmation
  call-count/argv-order test
- The only existing guard is app-owned, monitor-only, and scoped to "modal
  open"; a new effect guard added the same way would repeat the gap that left
  minimonitor unguarded · severity: medium · → mitigation: the guard is
  **mixin-owned and lazily initialized** (step 4), so neither app can omit it,
  with the re-entrancy tests run against **both** TUIs
- The `t` key is App-bound in the full monitor, so the row handler must consume
  it · severity: low · → mitigation: the proven `r` precedent (t1427) plus the
  mutual-exclusivity tests

### Goal-achievement risk: medium
- Draft naming must survive `sanitize_name`'s right-truncation **and** its
  deletion of non-`[a-z0-9_]` characters; a naive region pass-through both
  mis-budgets and can drop the nonce/index, silently overwriting a prior draft ·
  severity: high · → mitigation: the post-sanitization budget rule in step 5,
  pinned by the over-long-region test asserting the name is ≤60 chars and still
  ends with `_<nonce>_<i>`
- Every Python test stubs the subprocess seam, so no test exercises the real
  `aitask_create.sh` flag contract — a drift there leaves the suite green and
  the feature dead on disk · severity: medium · → mitigation: inline pre-phase
  pin_real_create_draft_contract
- Drafts carry no ids, and a count-plus-directory notify cannot identify which
  files a given confirmation produced in a shared, minute-stamped drop
  directory — defeating the pinned "report draft paths" decision · severity:
  medium · → mitigation: per-path listing plus the batch-nonce selector
  (step 5), pinned by the path-reporting test asserting paths and never ids
- Even after serialization, a genuinely concurrent other TUI can still fail the
  store write **after** the draft exists, leaving a created-but-unsuppressed
  concern that silently invites a duplicate · severity: medium · → mitigation:
  the third, distinctly-worded partial-failure outcome (step 5), pinned by the
  forced lock-busy recovery test
- The picker lists concerns unfiltered and suppression only lands producer-side
  at the **next** shadow round, so re-confirming an unchanged block re-spins an
  already-parked concern into a second draft — a window the in-flight guard
  alone does not close · severity: high · → mitigation: the store-based
  pre-creation skip (step 5), with its producer-scoped positive control and
  fail-open control
- **ACCEPTED, not mitigated (user decision at implementation review):** both
  duplicate guards are single-process — the in-flight set is in-memory, and the
  store check is an unlocked `list` separated from the `add` by a subprocess —
  so two *separate* monitor processes on one task can both read "not yet spun
  off" and each create a draft · severity: medium · → mitigation: **none;
  documented acceptance** in `_spawn_concern_tasks`' docstring. It cannot be
  closed with the house mutex: `lib/registry_lock.sh` records the acquiring
  shell's `$$`, releases on an EXIT trap, and steals a dead-PID holder on
  sight, so it serializes one bash process's critical section and cannot span
  the awaits. The alternatives were an atomic claim verb on
  `aitask_shadow_rejected.sh` (which must write the store *before* the draft
  exists, trading a duplicate draft for a possible suppressed-but-uncreated
  concern) or relaxing invariants that file marks "do NOT relax". Accepted
  because reaching it needs two monitor processes confirming the same concern
  within a sub-second window, and the damage is one extra **unfinalized**
  draft — reported with its path, owned by no task id, removable with `rm`,
  with no loss and a store that still converges

### Planned mitigations
- timing: pre-phase | name: characterize_picker_help_budget | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health (shared picker modal / narrow-width display budget) | desc: Characterize the picker's compact help line and rows on the composited strip at the 24-col xnarrow tier before adding the t key, then re-assert with the fourth key present
- timing: pre-phase | name: pin_real_create_draft_contract | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement (no test exercises the real aitask_create.sh flag contract) | desc: Shell test running the real aitask_create.sh once in a tmpdir with this feature's exact argv, asserting anchor/followup_kind/draft frontmatter and single-line stdout, plus a nonexistent --followup-of negative control

## Post-Review Changes

### Change Request 1 (2026-08-13 12:05) — plan review, both CONFIRMED

- **Requested by user (via review):**
  1. *(high, mixed picker actions)* A confirmation that both rejects and spins
     off launched two non-exclusive workers, each calling the same rejection-store
     writer; one can return `LOCK_BUSY`, and when the spin-off draft was already
     created but its store `add` failed, the concern returns next round and the
     user can create a duplicate draft.
  2. *(high, draft-path reporting)* The pinned contract requires reporting draft
     paths, but the plan only collected stdout paths and notified a count plus a
     location — leaving the user unable to identify the drafts a given
     confirmation produced, especially during concurrent work.
- **Changes made:** Both verified against the source before changing anything.
  (1) Confirmed the store mutex is a single per-task `LOCK_DIR` via
  `lib/registry_lock.sh`, **not** producer-scoped, and that exit 3 means nothing
  was written — and that `_persist_concern_dispositions`' own docstring already
  records why its two subcommands are sequential. Fixed **structurally**: one
  `_apply_concern_side_effects` worker awaits rejections then spin-offs, and the
  spin-off store write became a **single batched `add`** mirroring the rejection
  path. The residual (a genuinely concurrent *other* TUI) gets its own
  "created but NOT suppressed" wording naming the duplicate hazard.
  (2) The notify now lists every draft path plus the batch nonce as a selector
  (`ls aitasks/new/*<nonce>*`), capped with `… and K more`.
  `ConcernBlockInspectModal` was rejected as the surface — it is specifically
  the raw *concern-block* view (t1293).
- **Files affected:** `.aitask-scripts/monitor/monitor_shared.py`,
  `tests/test_minimonitor_concern_action.py`,
  `tests/test_monitor_concern_action.py`.

### Change Request 2 (2026-08-13 12:20) — plan review, CONFIRMED

- **Requested by user (via review):** the picker guard is released on modal
  dismissal while the non-exclusive draft-creation worker is still running, and
  minimonitor has no equivalent guard at all; reopening the picker and spinning
  off the same concern starts a distinct-nonce batch and creates duplicate
  drafts. Hold a per-pane/task in-flight effect guard until completion and test
  repeated confirmation in both TUIs.
- **Changes made:** Verified and found **wider** than reported:
  `_concern_pick_busy` is monitor-only, is scoped by its own docstring to modal
  stacking, and is released one line *before* `apply_concern_pick_result`;
  minimonitor has none; **and** the picker lists concerns unfiltered while
  suppression only lands producer-side at the next shadow round — so the
  duplicate window does not close when the worker finishes. Fixed at both
  layers: a **mixin-owned, lazily-initialized** in-flight guard keyed by task id
  (mixin-owned precisely because app-ownership is how the original gap arose),
  released in a `finally`; plus a **store-based pre-creation skip** filtered on
  `producer == "spinoff"`. `_concern_pick_busy` was left untouched — it answers
  a different question. Tests run against **both** TUIs.
- **Files affected:** `.aitask-scripts/monitor/monitor_shared.py`,
  `tests/test_minimonitor_concern_action.py`,
  `tests/test_monitor_concern_action.py`.

### Change Request 3 (2026-08-13 13:05) — implementation review, cross-process TOCTOU

- **Requested by user (via review):** two separate monitor processes can both
  read "no spinoff marker", then each create a draft before either records it.
  Add a task-scoped cross-process transaction lock around check → create → store
  add, or explicitly document acceptance.
- **Investigation:** the race is real — `list` takes **no lock** by design
  (rename-atomic reads) and `add` **appends unconditionally** without deduping,
  so add-first cannot serve as a claim either. Crucially, the house mutex
  **cannot** implement the requested lock: `lib/registry_lock.sh` records the
  acquiring shell's own `$$` (`:64`), installs `trap … EXIT` (`:69`), and steals
  any dead-PID holder on sight — so it serializes one bash process's critical
  section and cannot span the awaits here. The alternatives were an atomic claim
  verb on `aitask_shadow_rejected.sh` (which must write the store *before* the
  draft exists, trading a duplicate draft for a possible suppressed-but-uncreated
  concern) or relaxing invariants that file marks "do NOT relax".
- **Decision (user):** **document acceptance.** Recorded in
  `_spawn_concern_tasks`' docstring as an explicit ACCEPTED LIMITATION with the
  mechanism, why it is not closed, the reachability (two monitor processes, same
  task, same concern, sub-second window) and the damage (one extra *unfinalized*
  draft, reported with its path, removable, no loss, store still converges), and
  as an accepted risk bullet in `## Risk` above.
- **Files affected:** `.aitask-scripts/monitor/monitor_shared.py`,
  `aiplans/p1159/p1159_3_spinoff_triage_arm.md`.

## Final Implementation Notes

- **Actual work done:** Both inline pre-phases landed first and green against the
  pre-change tree (`ConcernHelpLineBudgetTests` at the 24-col tier; the new
  `tests/test_shadow_spinoff_create_contract.sh` driving the **real**
  `aitask_create.sh`). Then: `»` mark + quad-state `_ConcernRow` + `t` key;
  `spun_off` on `ConcernPickResult` with **no default**, amended at all four
  construction sites; help/context text; a single serialized effects worker with
  a mixin-owned in-flight guard; `_run_create_cmd` + `_spawn_concern_tasks` with
  a store-based pre-creation skip, per-batch-nonce naming, one batched store
  write, and an exhaustive partial-failure contract.
- **Deviations from plan:** (1) The AST-guard step was **inverted** per the
  plan's own correction 3 — no row was registered, and the guard's unmodified
  pass is the assertion. (2) Two defects found during implementation and fixed
  beyond the plan: the failure path merges stderr, so `aitask_create.sh`'s
  **coloured** `die` would have rendered raw ANSI in the toast, and taking the
  *first* line reported a preceding label warning instead of the terminal cause
  — both now handled by `_create_failure_reason` and pinned with the real
  captured failure text. (3) The cross-process TOCTOU was documented as accepted
  rather than fixed (CR3).
- **Issues encountered:** A concurrent session (t1468_5) edited the same
  `monitor_shared.py` throughout, with a large **staged** index. Its work was
  committed as `b25bb4893` *between* my tree construction and my `commit-tree`,
  so the first commit — built from `read-tree HEAD` at the older HEAD but
  parented to the newer one — **silently reverted their `monitor_shared.py`
  changes**. Caught by diffing their marker symbols against the committed blob,
  and repaired with `git commit --amend --only -- <file>` using the merged
  worktree content; verified afterwards that my commit touches none of their
  lines and that their symbols are present in HEAD. The overlap was exactly one
  file. Two transient full-suite failures were also investigated rather than
  assumed: `test_trail_gather` was the other session mid-edit (passes on re-run),
  and `test_board_startup_focus_live` was proven **pre-existing** by running it
  in a detached worktree at HEAD with neither session's changes.
- **Key decisions:** effects are serialized **structurally** (one worker) rather
  than by retry; the in-flight guard is **mixin-owned** so neither app can omit
  it, which is the defect that produced the original asymmetry; the name budget
  is computed against the **post-sanitization** length because `sanitize_name`
  truncates from the right and deletes non-`[a-z0-9_]` characters (verified as a
  fixed point against the real bash function); forwarding keeps sole ownership of
  the clipboard so a mixed confirmation cannot clobber the payload.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** `ConcernPickResult` now has **four** fields and
  `spun_off` carries **no default** — any new construction site must supply it.
  The picker's per-row state machine is quad-state; a fifth would need another
  single-width mark and another compact-help token, and
  `ConcernHelpLineBudgetTests` will fail if the 24-col line can no longer carry
  them all. `_run_create_cmd` is a test seam like `_run_rejected_cmd`: no bash
  runs in the Python suites, so any change to the create argv contract must also
  update `tests/test_shadow_spinoff_create_contract.sh`, which is the only test
  that executes the real script. Note that the store's `add` does **not** dedupe
  and `list` takes **no lock** — do not build a claim/CAS on them without
  reading CR3 first. Finally: this file's history shows a concurrent session
  can commit between your `read-tree` and your `commit-tree`; if you build a
  commit with plumbing, re-verify the other party's symbols survive in HEAD.
