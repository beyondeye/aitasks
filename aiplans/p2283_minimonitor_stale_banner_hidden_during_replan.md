---
Task: t2283_minimonitor_stale_banner_hidden_during_replan.md
Base branch: main
Output branch: main
---

# t2283 — Stale-feedback banner hidden during a re-plan

## Context

The minimonitor's red `⚠ shadow feedback is stale` banner stays hidden for the
whole time the followed agent works through shadow feedback during a **re-plan
that follows an already-approved plan**. It shows up only once the revised plan's
approval dialog is back on screen.

The root cause is verified in the task. t1573's phase-retire gate
(`MiniMonitorApp._feedback_phase_retired`) suppresses the warning whenever the
current phase is KNOWN and differs from the origin phase bound at first sighting.
The block is bound as PLAN from the native `claude_plan_approval` dialog. Once the
agent starts working, `workflow_phase.compose` falls back to the **ledger half**.
The task's `## Gate Runs` still holds the earlier `plan_approved pass`, so the
ledger half reads IMPLEMENT, and the warning is retired. That ledger state was
already there when the feedback was bound, so it is not evidence that the agent
moved on.

The fix is to let a **ledger-sourced** phase retire the warning only when the
ledger **content** has changed since the bind. A **live/screen-sourced** phase
keeps today's rule.

Verified facts this design relies on:
- `PhaseSignal.source` ∈ `workflow-prompt`, `native-prompt`, `ledger`, `none`
  (`.aitask-scripts/lib/workflow_phase.py:61`). `none` is emitted only with an
  UNKNOWN phase.
- The ledger is append-only. `gate-recording.md` appends a new block on every
  approval, so a re-approval appends a second `plan_approved` row: the ledger
  CONTENT changes even though the ledger PHASE stays IMPLEMENT.
- All three shipped profiles (`default`, `fast`, `remote`) set
  `record_gates: true`. A non-recording profile has an empty ledger, so its
  ledger phase is UNKNOWN and it can never ledger-retire. Its behaviour is
  unchanged.
- The Tier A anchors (`WORKFLOW_PROMPTS`) and the Tier B native table map no
  prompt a re-plan shows to IMPLEMENT (Tier B maps only
  `claude_plan_approval` → PLAN). Other AskUserQuestions during a re-plan, such
  as the risk-mitigation prompt, fall back to the ledger. They are therefore
  covered by the new rule.

## Implementation

### 1. `.aitask-scripts/monitor/monitor_core.py` — ledger content identity

- `import hashlib`.
- Add a module-level helper near `GateSummaryCache`:
  ```python
  def _ledger_content_identity(text: str) -> str:
      """Digest of the gate-run blocks themselves (t2283) — not file mtime/size,
      so notes / status / frontmatter edits leave it unchanged. An empty ledger
      has a real identity (the digest of nothing), distinct from None."""
      h = hashlib.sha256()
      for run in gate_ledger.parse_gate_run_blocks(text or ""):
          h.update(run.raw_marker.encode("utf-8", "surrogatepass")); h.update(b"\n")
          for line in run.raw_body_lines:
              h.update(line.encode("utf-8", "surrogatepass")); h.update(b"\n")
          h.update(b"\x00")   # block separator
      return h.hexdigest()
  ```
- `GateSummaryCache`:
  - The `_cache` value grows a 5th element:
    `(identity, summary, phase, recording, ledger_id)`. Update the type comment
    and annotation.
  - `_entry_for` returns a 4-tuple `(summary, phase, recording, ledger_id)`.
    `_EMPTY` (no info / no abs path / stat miss) carries `None`. The id is
    computed on cache miss, from the same `info.body` the phase uses, inside a
    `try` → `None` on any exception. It shares the existing mtime-gated cache
    entry, so a tick with an unchanged file pays no extra parse.
  - New public method
    `ledger_identity_for(info) -> str | None: return self._entry_for(info)[3]`,
    with a docstring that says `None` = underivable and must never be read as
    "changed".
  - The existing `summary_for` / `ledger_phase_for` / `phase_for` indexing
    (`[0]`, `[1]`, `[2]`) is unchanged.
  - Extend the class docstring with one line about the t2283 ledger identity.

### 2. `.aitask-scripts/monitor/minimonitor_app.py` — retire only on new evidence

- Module-level constant:
  `_LIVE_PHASE_SOURCES = frozenset({"workflow-prompt", "native-prompt"})`, with
  a comment explaining that only these are this tick's observation and that
  everything else (ledger, none, an unrecognised value) must bring new ledger
  evidence.
- Binding (around line 1664): the type becomes
  `tuple[str, int, str, str | None] | None` =
  `(shadow_pane, block_key, origin_phase, ledger_id_at_bind)`. Extend the comment.
- Extract `_task_info_for_pane(snap)` from `_phase_signal_for_pane` (task-id →
  info resolution, `None` on any failure). `_phase_signal_for_pane` keeps its
  behaviour and uses it.
- New `_phase_evidence_for_pane(snap) -> tuple[PhaseSignal | None, str | None]`:
  - `info = self._task_info_for_pane(snap)`.
  - **If `info is None` → `return None, None` BEFORE any composition.** This
    preserves `_phase_signal_for_pane`'s unresolved-task early return.
    `GateSummaryCache.phase_for(None, …)` composes over `_EMPTY`, and
    `workflow_phase.compose`'s live tiers still return PLAN/`native-prompt` from
    the screen alone. Composing for an unresolved task would therefore let a
    differing live phase retire feedback bound in IMPLEMENT, which breaks AC6
    and changes existing behaviour. A `None` signal is an UNKNOWN phase, which
    neither binds nor retires.
  - signal = `self._phase_for_snap(snap, info)`, inside a `try` → `None`;
  - ledger_id = `self._gate_cache.ledger_identity_for(info)` inside
    `contextlib.suppress(Exception)` → `None`. This fails safe for fake caches
    in other tests that lack the method.
- `_feedback_phase_retired`:
  ```python
  key = ...; if key is None: return False
  signal, ledger_id = self._phase_evidence_for_pane(snap)
  phase = getattr(signal, "phase", UNKNOWN); source = getattr(signal, "source", NO_SOURCE)
  known = ...
  bound = ...
  if bound is None or bound[0] != shadow_pane or bound[1] != key:
      self._shadow_feedback_phase = (shadow_pane, key, phase, ledger_id) if known else None
      return False
  if not known or phase == bound[2]:
      return False
  if source in _LIVE_PHASE_SOURCES:
      return True                     # a live observation — unchanged t1573 rule
  # Ledger-derived (or unattributed) phase: it must be NEW evidence.
  return (ledger_id is not None and bound[3] is not None
          and ledger_id != bound[3])
  ```
  Rewrite the docstring predicate block to show the two branches. Add the
  re-plan rationale: the t1573 "a flap is cheap" assumption fails because, after
  an approved plan, the flap is systematic and covers the exact window in which
  the banner matters. Keep the four recovery bullets; they still hold, because
  the rule is still derived every tick with no latch.
- Leave line 6363 (`self._shadow_feedback_phase = None`) as it is.

### 3. Tests

**`tests/test_minimonitor_concern_action.py`**
- `_install_phase` gains two one-cell lists: `app._source = ["workflow-prompt"]`
  and `app._ledger = ["L0"]`. The fake `phase_for` returns
  `PhaseSignal(phase=app._phase[0], source=app._source[0])`. Add
  `ledger_identity_for=lambda info: app._ledger[0]`. The default is a live
  source, so every existing t1573 test keeps its meaning (a live
  known→known move retires) and passes unchanged. Update the docstring.
- New section `# -- 4. retirement needs NEW evidence (t2283)`, with these tests:
  1. `test_a_replan_after_an_approved_plan_keeps_the_warning` (AC1). Origin PLAN
     `native-prompt` L0, then IMPLEMENT `ledger` L0. Over several ticks the
     banner stays `SHADOW_STALE_NARROW` and `_shadow_stale_combined is True`.
  2. `test_negative_control_the_pre_fix_predicate_hides_it` (AC7). The same
     timeline, with `_feedback_phase_retired` swapped for a verbatim test-local
     copy of the pre-fix predicate (`types.MethodType`) that binds 3-tuples and
     ignores source and ledger. It asserts that the banner IS cleared, which
     proves the scenario discriminates.
  3. `test_a_real_reapproval_retires_the_warning` (AC2). The first case, then
     `app._ledger[0] = "L1"`, retires. Then PLAN `native-prompt` (flap back to
     the origin) brings the warning back, so the predicate is still not latched.
  4. `test_first_round_approval_retires` (AC3). Origin PLAN `native-prompt` with
     the empty-ledger identity `"E"`, then IMPLEMENT `ledger` `"L1"`, retires.
  5. `test_review_approval_retires` (AC4). Origin IMPLEMENT `workflow-prompt` L1,
     then POSTIMPL `ledger` L2, retires.
  6. `test_feedback_bound_from_a_ledger_phase` (AC5). Origin IMPLEMENT `ledger`
     L0. POSTIMPL `ledger` L0 does not retire. POSTIMPL `workflow-prompt`
     retires. Back on `ledger` L0 it does not retire, and `ledger` L1 retires.
  7. `test_an_underivable_ledger_identity_never_retires` (AC6), as subtests:
     - bound `None` → current `"L1"`;
     - bound `"L0"` → current `None`;
     - a gate cache that has no `ledger_identity_for` attribute at all
       (rebuild `app._gate_cache` without it).
     Each one has a ledger-sourced differing phase, and the warning stays.
  7b. `test_an_unresolved_task_never_retires_even_on_a_live_phase` (AC6, the
     unresolved-task branch). Bind the warning at IMPLEMENT
     (`workflow-prompt`, L0). Then switch the fake to PLAN/`native-prompt`, a
     live, differing phase that the real `compose` produces from the screen
     alone, and make task resolution fail. Run this as two subtests:
     `get_task_id_for_pane` → `None`, and `get_task_info` → `None`. The fake
     `phase_for` still returns that live signal whatever `info` it is given, so
     the test discriminates: without the early return the warning would retire.
     Assert the warning stays (`combined is True`, banner shown). A third
     subtest uses the **real** `GateSummaryCache` with
     `get_task_info → None` and a snapshot whose `awaiting_input_kind` is
     `claude_plan_approval`. It checks that the real `phase_for(None, …)` really
     does return PLAN/`native-prompt`, so the hazard is pinned against
     production, and that the warning still stays.
  8. `test_an_unattributed_known_phase_needs_ledger_evidence`. With source
     `none` and a known differing phase, the ledger unchanged does not retire;
     a changed ledger retires. This pins the fail-safe treatment of
     unrecognised sources.

**`tests/test_monitor_gate_cache.py`**: new `LedgerIdentityTest`, using the
existing `_task_text` / `_info` idiom:
- identity is a non-empty str and is stable across two calls (no re-read);
- appending a gate block changes it;
- a frontmatter edit (status), a prose or `## Inbox` note edit, or an mtime bump
  leaves it unchanged, even though the file identity changed;
- an empty ledger gives a non-`None` identity that differs from the gated one;
- `info=None` and a missing file give `None`.

### 4. Docs — `aidocs/framework/shadow_agent.md`, "The banner's two suppressions"

Replace the single predicate block with the two-branch form:
- a live (screen) source retires as before;
- a ledger source retires only when the gate-run content differs from what it
  was at bind time;
- an underivable identity never retires.

Add a short paragraph with the re-plan rationale (t2283):
- the ledger keeps the earlier `plan_approved`, so it reads IMPLEMENT for the
  whole re-plan;
- the key is ledger content, not phase, because a re-approval does not change
  the phase;
- non-recording profiles never ledger-retire; they rely on a screen phase or a
  new round, which is the acceptable direction.

The doc stays current-state only, with no version history.

## Verification

- `python3 -m pytest tests/test_minimonitor_concern_action.py tests/test_monitor_gate_cache.py -q`
- Neighbouring suites:
  - `tests/test_monitor_gate_summary.py`
  - `tests/test_gate_ledger_only_surfaces.py`
  - `tests/test_minimonitor_top_chrome_render.py`
  - `tests/test_minimonitor_concern_smoke.py`
  - `tests/test_minimonitor_incremental_list.py`
  - `tests/test_minimonitor_gate_phase_row.py`
  - `tests/test_workflow_phase*.py`
- Red proof against the unfixed code. Create a detached worktree at HEAD in the
  scratchpad (`git worktree add --detach <scratch>/base HEAD`), copy only the
  new test file in, and run the new t2283 tests there. Tests 1 and 7 must fail
  (or error on the missing `ledger_identity_for` for the cache tests). Then
  remove the worktree. No stash or restore in the shared tree.
- Full suite: `bash tests/run_all_python_tests.sh`, last line only, with
  `set -o pipefail`.

## Post-implementation

Step 9: commit the code, tests and docs as
`bug: Retire the stale banner only on new phase evidence (t2283)`, then archive
through the standard workflow.

## Risk

### Code-health risk: low
- `GateSummaryCache._entry_for` changes its internal tuple shape, and that cache
  also serves the full monitor's gate column and phase line · severity: low.
  Only private callers index it, and each is updated in the same change; the
  existing gate-cache tests pin the other fields · → mitigation: none
- A gate cache that lacks `ledger_identity_for` (test fakes, or any other
  duck-typed cache) must not crash the tick · severity: low. The call is wrapped
  in `suppress`, so it falls to `None`, which never retires; test 7 pins this
  · → mitigation: none

### Goal-achievement risk: low
- A ledger write during a re-plan that is not an approval would retire the
  warning early · severity: low. Planning writes no gate rows: the
  `plan_approved` and `risk_evaluated` rows land at Step 7 after approval, and
  `plan_verified` goes to the plan file. Even in that case the result is never
  worse than today · → mitigation: none
- A non-recording profile never ledger-retires, so the warning stays up until a
  screen phase or a new round appears · severity: low. This is the documented,
  intended fail-toward-showing direction · → mitigation: none

## Final Implementation Notes
- **Actual work done:** Implemented as planned.
  - `monitor_core.py`: `_ledger_content_identity()` is a SHA-256 over each gate-run block's `raw_marker` and `raw_body_lines`. `GateSummaryCache` now caches it as a 5th element in the same mtime-gated entry and exposes it as `ledger_identity_for(info)`. `None` covers no info, no path, a stat miss, and an exception.
  - `minimonitor_app.py`: added the `_LIVE_PHASE_SOURCES` allow-list, the 4-tuple binding, `_task_info_for_pane`, `_phase_evidence_for_pane` (early `(None, None)` for an unresolved task), and the two-branch `_feedback_phase_retired`.
  - `tests/test_minimonitor_concern_action.py`: the fixture gained `app._source` (default `workflow-prompt`) and `app._ledger` cells, plus 9 new t2283 tests and a verbatim pre-fix predicate used as the negative control.
  - `tests/test_monitor_gate_cache.py`: the shared setUp moved into a `_GateCacheFixture` base, and `LedgerIdentityTest` adds 6 tests.
  - `aidocs/framework/shadow_agent.md`: documents the two-branch predicate and the rationale.
- **Deviations from plan:** One addition: the plan-review concern about an unresolved task. `GateSummaryCache.phase_for(None, …)` still composes the live tiers and returns PLAN/`native-prompt` from a native plan-approval dialog. `_phase_evidence_for_pane` therefore returns before composing, and `test_an_unresolved_task_never_retires_even_on_a_live_phase` pins this with fake caches and with the real cache plus real `compose`.
- **Issues encountered:**
  - With the old fixture (signals defaulting to source `none`), 6 existing t1573 tests failed after the predicate change. This was expected: `none` now needs ledger evidence. Defaulting the fixture source to a live one restored their original meaning.
  - In the gate-cache parse-failure test, patching `gate_ledger.parse_gate_run_blocks` also broke the unguarded phase derivation. The test now patches `monitor_core._ledger_content_identity` instead.
- **Key decisions:**
  - Live sources are an allow-list, so an unrecognised source fails toward showing the warning.
  - An empty ledger has a real identity, not `None`, so a first-round approval (AC3) still retires the warning.
  - The identity comes from `info.body`, the same source as the ledger phase.
- **Verification:**
  - **Neighbouring suites:** 453 passed.
  - **Baseline red proof** (detached scratch worktree at HEAD, with the tuple-shape precondition removed):
    - Fails on the defect assertion: AC1 ("a ledger state that predates the feedback retired it").
    - Also fail at baseline (old rule retires on an unchanged ledger): re-approval, ledger-origin, underivable and unattributed.
    - Pass at baseline, as regression guards: first-round, review-approval, the unresolved-task test, and the negative control.
  - **Mutant without the unresolved-task early return:** all 3 subtests fail.
  - **Full suite:** 11998 passed, 4 failed and 1 collection error, none caused by this change.
    - `test_aitask_questions_mcp.py` is another session's staged file and needs `anyio`, which is not installed. It causes the collection error and the `test_no_zero_collection` ×2 and `test_collection_parity` failures.
    - `test_board_movement`'s benchmark failed under suite load and passes alone.
- **Upstream defects identified:** None
