---
Task: t1159_2_auto_recheck_loop.md
Parent Task: aitasks/t1159_shadow_review_loop_automation.md
Sibling Tasks: aitasks/t1159/t1159_3_spinoff_triage_arm.md, aitasks/t1159/t1159_4_docs_and_integration.md, aitasks/t1159/t1159_5_manual_verification_shadow_review_loop_automation.md
Archived Sibling Plans: aiplans/archived/p1159/p1159_*_*.md
Worktree: . (current directory — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/fable5 @ 2026-08-12 17:13
---

# Plan — t1159_2: Minimonitor auto-recheck loop

Parent design: `aiplans/p1159_shadow_review_loop_automation.md`. Depends on
t1159_1 (**landed 2026-08-11**, archived plan
`aiplans/archived/p1159/p1159_1_round_metadata_concern_block.md` — read its
"Notes for sibling tasks" before consuming the parser API).

## Pinned decisions (user-confirmed at parent planning — do not reopen)

- Minimonitor-orchestrated. The loop drives only the **shadow** pane; the
  followed pane is never written. Forwarding stays clipboard-only.
- Arm/disarm via `L`; loop state lives in-process (no new pane options).
- Phase pre-selects recheck **wording** only; it never gates firing
  (advisory-only contract — t1311/t1420 scar; `tests/test_shadow_phase_advisory.sh`
  negative-control pattern).
- Arming refuses visibly on **agent capability** gaps, both sides: followed
  agent without live prompt tiers (t1467), shadow agent without a readiness
  detector.

## Verification pass — findings against `main` (2026-08-12)

All seams re-verified against the live tree (t1159_1, t1453, t1486 landed since
this plan was written). Corrections to the plan as originally written:

1. **Line drift in `minimonitor_app.py`** (all structure intact): `BINDINGS`
   328-347 (`L` confirmed free; minimonitor has **no `check_action`** at all);
   `__init__` 349 (state body 361-436; `_shadow_feedback_stale` tri-state at
   426, `_shadow_freshness_tick` at 432, `_last_concern_block_payload` at 413);
   `_maybe_offer_concerns` 2314-2405 — agent-gone return 2328-2330
   (`_find_own_agent_snapshot()`, line 726), shadow-gone return 2331-2337
   (sets `_shadow_feedback_stale = None`, clears the stale banner),
   `_restamp_shadow_phase(shadow_pane, snap)` at 2351 (unthrottled),
   `text = await capture_shadow_text(shadow_pane)` at 2352, staleness throttle
   at 2343-2346 (`% 2 == 1`, so it fires on the first tick a shadow is
   present), t1159_1 dedup at 2381-2392; `_set_shadow_stale_banner` 2139-2149
   (id `#mini-shadow-stale`, CSS 260-266, `$error` background, mounted in
   `compose` at 441 with `""`); key-hints Static 444-454 (id `#mini-key-hints`);
   `action_pick_concerns` 2201-2299 (already passes
   `block_meta=parse_block_meta(text)` at 2297).
2. **`live_tiers_available` / `agent_key_from_command` live in
   `.aitask-scripts/lib/workflow_phase.py`** (lines 148 / 135), not
   `prompt_patterns.py`. minimonitor already imports the `workflow_phase`
   module (line 48). `PHASES = ("PLAN", "IMPLEMENT", "POSTIMPL", "UNKNOWN")`
   (`workflow_phase.py:52`); `PhaseSignal` is a frozen dataclass (line 163).
3. **Modal detection:** `screen_stack` is unused in the monitor package; the
   package convention is `isinstance(self.screen, ModalScreen)`
   (`minimonitor_app.py:1272-1273`). `_service_review_loop` computes
   `modal_open` that way.
4. **The shadow pane has no `PaneSnapshot`** — `find_shadow_pane_async`
   (`monitor_core.py:429-439`) returns a bare pane-id string via the
   `@aitask_shadow_target` reverse lookup; shadow panes are excluded from
   agent discovery. There is **no existing way to read the shadow's
   `current_command`**, so resolving the shadow's agent needs a new seam
   (step 4 below): extend `shadow_query_args()` (`monitor_core.py:377-383`)
   with a third `#{pane_current_command}` field — zero new tmux traffic, and
   `match_shadow_pane` (327-353) already tolerates ≥2 fields (reads only
   `parts[0]`/`parts[1]`).
5. **No captured-widget fixture files exist** — t1420/t1474 prompt-pattern
   tests pin widget text as **inline string literals**
   (`tests/test_prompt_detection.py:199-330`), not files under
   `tests/fixtures/`. The shadow-readiness fixtures follow that practice:
   inline literals in `tests/test_review_loop.py`, captured live in the
   pre-phase.
6. **`prompt_patterns.py` has no empty-composer pattern** for any agent — all
   5 claude patterns anchor on dialog footers/options. The positive
   empty-composer detector is genuinely new, pinned from the pre-phase
   captures.
7. **`_loop_banner_text` does not exist anywhere** — the existing DOM-free
   seam is the *recorded attribute* pattern: `_set_shadow_stale_banner` stores
   `self._shadow_stale_banner_text` before `query_one(...).update(...)` under
   `contextlib.suppress`. The new banner mirrors that: `_set_loop_banner(text)`
   records `self._loop_banner_text` (assertable without a DOM).
8. **Stamp passivity confirmed structurally** (`aitask_shadow_capture.sh:344-355`):
   `shadow_stamp_analyzed_at` stamps only when the process runs *inside a
   shadow pane* capturing its own bound followed agent. The monitor's per-tick
   `capture_shadow_text` (monitor pane, stdin path never reached) can never
   restamp — passive observation cannot clear the staleness that arms the
   loop; only the shadow's own refetch does. This is the structural basis of
   the edge contract.
9. **`send_keys` seam verified unchanged** (`monitor_core.py:2458-2472`):
   `send_keys(pane_id, keys, literal=False)`, `-l` when literal, `--`
   separator pinned by `tests/test_monitor_tmux_injection.sh` (fake-argv test,
   no real tmux). `compute_shadow_staleness` (507) returns
   `(stale, analyzed_at)` tuple; minimonitor consumes it in
   `_update_shadow_freshness` (2169-2199).
10. **Test harness verified** (`tests/test_minimonitor_concern_action.py`):
    `_FakeMon` (142) records `tmux_run`/`tmux_run_async` argv; `_mk_app` (160)
    uses `MiniMonitorApp.__new__` + `spy_notify`/`spy_pushed` lambdas;
    `AutoOfferTests` (717) drives `asyncio.run(app._maybe_offer_concerns())`
    directly, stubbing `mm.capture_shadow_text` at module level (`_stub_capture`,
    126) and `_find_own_agent_snapshot`. `_FakeMon` needs a `send_keys`
    recorder added for the fire-path tests.
    `tests/test_minimonitor_concern_smoke.py` boots a real tmux server on a
    per-PID private socket (not in the runner's serial carve-out) — the live
    injection smoke extends it.
11. **`aidocs/framework/shadow_agent.md` has no review-loop section** —
    confirmed; step 6 adds it.

## Coordination — t1493 (task file updated externally, 2026-08-12 — live evidence)

**The injected recheck currently produces no block at all — a livelock for
this loop.** Verified live (Codex shadow of a Claude pane): free-text
"refetch and recheck" rounds re-enter the skill but answer in **prose only**
(no fences), because `SKILL.md.j2` Step 3 has no routing entry for a
re-review ask. Consequences: `expected_round` never advances
(`parse_block_meta` finds no new block), the picker re-presents round 1's
concerns as current, and the loop fires round after round with no visible
change (bounded only by the cooldown). **t1493**
(`shadow_recheck_rounds_leave_stale_concerns_in_picker`, bug/high, anchor
1159, `depends: [t1159_1]`) owns the fix (routing entry + per-round
"always re-emit the block" producer rule + consumer-side block-age check).
Obligations on this child:

- **Align `compose_recheck_prompt`'s wording with t1493's routing trigger**
  (step 3) so the injected line deterministically hits the re-review route —
  read t1493's landed routing entry at implementation time and embed its
  trigger phrase; if t1493's producer half has not landed yet, surface at
  review that the loop's happy path is unreachable until it does (its
  producer half should land before, or together with, this child).
- The same live session confirms the arm-time capability check is **not a
  corner case**: the shadow really was Codex (`gpt-5.6-terra`) while
  `SHADOW_READY_DETECTORS` ships claude-only. The refusal message must name
  the shadow's agent (the plan's wording already does: "shadow agent '<a>'
  has no readiness detection yet") — keep that property test-pinned.

## Plan-review hardening (user concerns, 2026-08-12 — all verified valid)

### Round 4

9. *(medium, arm baseline)* Resetting the baseline on re-arm without seeding
   it leaves the first comparison against None: a fresh arm with
   `pending_work=False` followed by a complete sub-tick agent response
   classifies `unknown`, then `none` forever — the first automated episode
   wedges. **Addressed**: `action_toggle_review_loop` **seeds the baseline
   from the arm-time snapshot** (the same snapshot the arm refusals already
   require, so it is always available) — arming is never baseline-less
   (step 5; fresh-arm-then-sub-tick-response test pinned).
10. *(medium, bounded capture)* The classifier compares captured text, but
    the production tick capture is `-S -<capture_lines>`
    (`monitor_core.py:2086-2093`) with minimonitor's `capture_lines=30` — a
    long revision can scroll entirely past the retained window and settle to
    an **identical captured tail**, yielding neither a work signal nor a
    staleness edge (the same bounded compare drives `_last_change_time`).
    **Addressed** three ways: (a) a durable scrollback-growth signal —
    `#{history_size}` added to the discovery pane format → `TmuxPaneInfo`;
    a positive inter-tick delta classifies `work` before any content
    comparison (zero extra tmux traffic; validated in the pre-phase, since
    in-place TUI repaints may not grow history — if falsified there, the
    signal is dropped and the limitation documented instead); (b) classifier
    fixtures are **production-depth-shaped** (truncated to the app's capture
    window, not full transcripts); (c) the residual gap — a fully sub-tick
    revision with an identical bounded tail *and* no history growth — is
    explicitly documented in the module docstring and shadow_agent.md
    (steps 2b, 4, 5; pre-phase measurement + depth-shaped tests).

### Round 3

7. *(high, native plan prompt)* `classify_followed_change` anchored
   exclusively on `workflow_phase.current_question_block`, whose docstring
   pins it to the AskUserQuestion **header chip only** ("it occurs exactly
   once, only in that widget"). The ExitPlanMode plan-approval dialog is a
   *native* prompt kind with no chip, so in the feature's **primary flow**
   (plan review) both captures yield an unlocatable block → `unknown` → the
   latch never opens. **Addressed**: the classifier now takes the tick's
   `awaiting_input_kind` (and the previous tick's) and dispatches per kind —
   chip anchor for question-widget kinds; a per-kind top boundary pattern
   (`NATIVE_DIALOG_BOUNDARIES`, pinned from the pre-phase revised-plan
   fixture, maintained in-place like the readiness patterns) for
   `claude_plan_approval`; a **kind change between ticks classifies as
   `work`** (a different dialog = progression); kinds with no strategy →
   `unknown` (steps 2b, 5; selection-only plan-dialog changes tested against
   the real revised-plan capture).
8. *(high, baseline retention)* Resetting `_loop_prev_content` on any absent
   snapshot loses the baseline exactly across an indeterminate
   capture-failure tick; if the agent responds during that gap, the next
   capture compares against None → `unknown`, then `none` forever —
   `work_seen` wedged. **Addressed**: the baseline (content + kind +
   pane_id) is **preserved while agent presence is indeterminate** (None)
   and reset only on verified departure, pane identity replacement
   (`pane_id` change), or disarm/re-arm (step 5; old prompt → failed capture
   during work → new prompt test-pinned).

### Round 2

4. *(high, fire reservation)* Returning a `'fire'` permission while staying
   WAITING leaves a window where a second overlapping refresh obtains a second
   permission before the first delivery confirms — and overlapping refreshes
   are a **documented reality** in minimonitor (`_refresh_data` runs from
   `set_interval`; `capture_all_async` returns None exactly when "a newer
   overlapping refresh superseded this one", minimonitor_app.py:609-615,
   t1111_4), so both could inject a recheck. **Addressed**: the controller
   reserves delivery **synchronously inside `tick()`** — a granted permission
   transitions to a DELIVERING state and issues a generation token before any
   await can interleave; ticks during DELIVERING return `'none'`;
   `confirm_fire(token)` / `abort_fire(token)` consume only the live
   reservation (stale tokens no-op); `disarm()` bumps the generation, retiring
   any outstanding token, and the fire path re-validates its token after its
   await, before sending (steps 1, 5; interleaved-tick, overlapping-service,
   and stale-token tests pinned).
5. *(high, agent presence)* Mapping `_find_own_agent_snapshot() is None`
   straight to `agent_present=False` disarms on a transient capture failure:
   `commit_snapshots` **drops panes whose content capture failed**, and the
   discovery-facts seam exists precisely because "treating that as a departed
   agent" is wrong (monitor_core.py:1305-1366 — `last_discovered_agents()`
   includes capture-failed panes; `last_enumerated_sessions()` distinguishes
   "enumerated and gone" from "could not see"). **Addressed**: agent presence
   becomes tri-state, derived from discovery-level liveness — snapshot present
   → True; snapshot absent but the own `(session, window)` still in
   `last_discovered_agents()` (capture failed), or the session not in
   `last_enumerated_sessions()` (indeterminate) → None (pause); session
   enumerated and the agent verifiably absent → False (disarm). Both paths
   test-pinned (steps 1, 5).
6. *(medium, work latch)* A sampled `awaiting_input is False` misses a
   complete sub-tick work episode (True → True across one 3s tick with
   materially new output), permanently blocking the loop; and initializing
   the latch True at arm lets a selection-only redraw trigger a first
   redundant review. **Addressed**: the latch is fed by a normalized
   **change classifier** `classify_followed_change(prev, curr, awaiting)` →
   `work | selection_only | none | unknown`, anchored on
   `workflow_phase.current_question_block` (line 304 — the same structural
   anchor t1420's currency rule uses): content change while not at a
   recognized prompt → `work`; with both ticks at a prompt, a change in the
   content **above** the current question block → `work` (a sub-tick episode
   grows the scrollback above the new prompt), a change confined to the block
   → `selection_only`; unlocatable block / no previous capture → `unknown`
   (conservative — never satisfies the latch). Arming initializes
   `work_seen = (stale is True at arm)` — an already-pending episode is
   covered by the explicit user action of arming, while a fresh arm requires
   classified work, so an arm-time selection redraw cannot fire (steps 1, 2b,
   5; sub-tick-episode and arm-then-navigate tests pinned).

### Round 1

1. *(high, delivery)* Two independent `send_keys` calls with only a generic
   notify: a failed prompt write followed by Enter submits pre-existing
   composer text or activates a newly appeared dialog; a failed Enter after a
   successful write strands injected text while the controller sits FIRED; the
   tick-time readiness is stale by delivery time. **Addressed**: pre-send
   revalidation on a fresh capture, ordered sends with the Enter gated on the
   prompt write's return value, visible auto-disarm + recovery message on
   either partial failure, and a confirm/abort fire API so the controller
   never records an unconfirmed fire (steps 1, 5; both failure orders +
   changed-pre-send-capture test-pinned).
2. *(high, lookup)* `find_shadow_pane_async` deliberately collapses query
   failure and verified absence into `None` (fail-open for readers —
   `find_shadow_pane_status`'s docstring, t1216_4, says exactly why a
   *decision* must not consume that view). Auto-disarm on a transient tmux
   timeout would silently destroy the user's armed loop. **Addressed**:
   `find_shadow_pane_info_async` returns an `ok` discriminator mirroring
   `find_shadow_pane_status`; `shadow_present` becomes tri-state — disarm
   only on positively verified absence, pause (state and streak preserved) on
   indeterminate (steps 1, 4, 5; nonzero-rc and timeout paths test-pinned).
3. *(medium, trigger semantics)* `_last_change_time` advances on any captured
   content difference, so navigating the selection of an AskUserQuestion /
   plan-approval widget flips staleness True while `awaiting_input` stays True
   — a redundant review fires though nothing substantive changed.
   **Addressed**: a **work-observed latch** — after a confirmed fire, a new
   episode additionally requires `awaiting_input is False` to have been
   positively observed (agent actually worked) since that fire; arming
   initializes the latch satisfied so the first round never waits for it.
   Selection-only redraws keep the prompt pattern matched (`awaiting_input`
   True throughout), so the latch blocks exactly the redundant refire.
   Semantics documented in the safety contract (steps 1, 6; the
   selection-only-redraw scenario is test-pinned with its positive control).

## Pre-phase (risk mitigations)

1. **[live_trigger_positive_control]** (confirmed inline mitigation): before
   wiring the loop, drive a real Claude pane through the monitor capture path
   (`capture-pane -p -e` + `strip_ansi` + `classify_content`) and confirm live
   that (a) `awaiting_input` asserts at an AskUserQuestion widget and at the
   ExitPlanMode approval dialog, and (b) `_shadow_feedback_stale` flips True
   after a followed-pane change (t1475 never ran — these inputs are
   implementation-reported, not confirmed). In the same session, capture the
   **shadow-readiness fixtures**: shadow at rest (empty composer), streaming
   output, parked at a dialog, holding typed composer text. Also capture the
   **followed-pane classifier fixtures** (hardening 7): the plan-approval
   dialog over a revised plan in **two selection states** (same dialog, moved
   selection — pins the `NATIVE_DIALOG_BOUNDARIES` top-boundary pattern and
   the selection-only classification) and an AskUserQuestion in two selection
   states. **Measure `#{history_size}` behavior** in the same session
   (hardening 10): confirm selection navigation does NOT grow it and a plan
   revision DOES — this decides whether the classifier's history-growth rule
   ships or the bounded-capture limitation is documented instead. Pin all
   fixtures as inline string literals in `tests/test_review_loop.py` (the
   `test_prompt_detection.py` practice — finding 5), **shaped to the
   production capture depth** (the last `capture_lines` window minimonitor
   actually sees, default 30 — not full transcripts); they pin
   `shadow_prompt_ready` and `classify_followed_change`.

## Steps

1. **New pure module `.aitask-scripts/monitor/review_loop.py`** (no tmux, no
   Textual, no I/O — testable like `concern_parser.py`):

   ```python
   DEBOUNCE_TICKS = 3        # ~9s at the 3s tick; only positive evidence counts
   COOLDOWN_SECONDS = 45.0   # min gap between fires, across episodes
   DISARMED, WAITING, DELIVERING, FIRED = (
       "disarmed", "waiting", "delivering", "fired")

   class ReviewLoopController:
       """Decides fire/hold/disarm for the shadow auto-recheck (t1159).

       EDGE-driven: firing a recheck makes the shadow re-read the followed
       pane, which re-stamps @aitask_shadow_analyzed_at and CLEARS the very
       staleness that triggered it (structural: only the shadow's own capture
       stamps — aitask_shadow_capture.sh:344-355). After a fire the controller
       stays FIRED until it positively observes stale == False (the shadow
       acted), then re-arms. Level-driven logic would fire forever or never.
       """
       def arm(self, *, pending_work: bool) -> None: ...
           # -> WAITING; work_seen = pending_work (app passes `stale is True`
           # at the arm tick — hardening 6).
       def tick(self, *, agent_present, shadow_present, awaiting_input,
                stale, work_signal, shadow_ready, modal_open, now) -> str:
           # 'none' | 'fire' | 'auto_disarm'
           # DISARMED: inert.
           # agent_present is a TRI-STATE (hardening 5):
           #   False (discovery-verified absent) -> disarm(), 'auto_disarm';
           #   None (pane discovered but snapshot missing — capture failed —
           #   or discovery indeterminate) -> pause: no advance, no reset,
           #   no fire, no disarm.
           # shadow_present is a TRI-STATE (hardening 2): same contract.
           # modal_open: pause — reset streak, never fire, never disarm.
           # work_signal in ('work','selection_only','none','unknown')
           #   (hardening 6): 'work' -> work_seen = True; all others leave
           #   work_seen unchanged.
           # DELIVERING: 'none' — a delivery is in flight; no second
           #   permission can be granted (hardening 4). Absence/disarm rules
           #   above still apply and retire the reservation.
           # FIRED: stale is False -> WAITING; None preserves; never fire.
           # WAITING: streak += 1 iff awaiting_input is True and stale is True,
           #          else streak = 0 (t1446 AUTO_CLOSE pattern).
           # 'fire' iff streak >= DEBOUNCE_TICKS and now - fired_at >= COOLDOWN
           #          and shadow_ready is True and work_seen
           #          — granting it SYNCHRONOUSLY enters DELIVERING and
           #          issues self._delivery_token (generation int) BEFORE the
           #          caller can hit an await (hardening 4); hold otherwise,
           #          streak kept.
       def delivery_valid(self, token) -> bool: ...
           # True iff `token` is the live reservation (state DELIVERING and
           # generation unchanged) — the fire path re-checks after its await,
           # before sending.
       def confirm_fire(self, token, now) -> bool: ...
           # live token -> FIRED, cooldown stamp, work_seen cleared, True.
           # stale token (superseded / disarmed meanwhile) -> no-op, False.
       def abort_fire(self, token) -> bool: ...
           # live token -> back to WAITING, streak preserved (retry next
           # ready tick). stale token -> no-op, False.
       def disarm(self) -> None: ...
           # -> DISARMED; bumps the generation, retiring any outstanding
           # delivery token (supersession completeness — a stale
           # confirm/abort can never resurrect state).
   ```
   Fire-condition detail: when the debounced trigger is satisfied but
   `shadow_ready` is not True, **hold** — keep the streak satisfied (do not
   reset), surface "waiting for shadow to settle" via the banner, and fire on
   the first ready tick. `rounds_fired` is display-only (never the shadow's
   round number).

   **Delivery reservation (hardenings 1+4):** `'fire'` is a *reservation
   made synchronously inside `tick()`* — asyncio interleaving can only happen
   at awaits, so entering DELIVERING and issuing the token before `tick()`
   returns closes the double-permission window that minimonitor's documented
   overlapping refreshes (t1111_4) would otherwise exploit. The outcome calls
   consume only the live reservation; a transport failure calls `disarm()`
   (which retires the token) and notifies visibly. The controller therefore
   never records a fire that was not actually delivered, and never permits
   two concurrent deliveries.

   **Work-observed latch (hardenings 3+6):** `work_seen` is set only by a
   `work_signal == 'work'` classification (step 2b) and cleared on each
   confirmed fire; `arm(pending_work=stale is True)` covers the
   armed-into-a-pending-episode case via the explicit user action while
   keeping a fresh arm immune to selection-only redraws. A sub-tick work
   episode still classifies as `'work'` (scrollback above the new prompt
   grew), so the latch can never wedge the loop after a fast agent response.

2. **Shadow readiness — positive prompt detection**, same module:
   - `shadow_prompt_ready(text: str, agent: str, hash_stable: bool) -> bool | None`
     requiring **all three**: (a) positive — the tail shows that agent's
     **empty** input composer (pattern pinned from the pre-phase fixtures; no
     typed text after the prompt char; genuinely new — no such pattern exists
     in `prompt_patterns.py`, finding 6); (b) negative — no dialog/prompt
     pattern from `prompt_patterns.PROMPT_PATTERNS_BY_AGENT[agent]` matches
     the tail (a dialog is a different interaction — Enter there answers it);
     (c) `hash_stable` (capture hash unchanged ≥2 consecutive ticks, computed
     by the caller from the per-tick shadow capture). Unknown agent / failed
     capture / any condition indeterminate ⇒ not-ready (`False`/`None`, never
     `True`). Hash stability alone is **never** sufficient.
   - `SHADOW_READY_DETECTORS: dict[str, ...]` — per-agent dispatch, initially
     `{"claude": ...}` only. The shadow's agent is independently selectable
     (`E` → any configured codeagent), so a Claude followed pane can
     legitimately have a Codex/OpenCode shadow; without a detector the loop
     must refuse at arm time, not hold forever.
   - Composer patterns are version-sensitive: maintain in-place (t1474
     practice), pin against the pre-phase fixtures.

2b. **Followed-pane change classifier** (hardenings 6+7), same module:
   ```python
   def classify_followed_change(prev_content: str | None, prev_kind: str,
                                curr_content: str, curr_kind: str,
                                awaiting_input: bool, agent: str,
                                prev_history_size: int | None = None,
                                curr_history_size: int | None = None) -> str:
       # -> 'work' | 'selection_only' | 'none' | 'unknown'
   ```
   - **History growth first (hardening 10):** both history sizes known and
     `curr > prev` → `'work'` — scrollback grew, even if the bounded
     captured tail settled identical. `None` on either side, or a shrink
     (clear-history / pane recycle), contributes nothing (fall through).
     Ships only if the pre-phase measurement confirms selection navigation
     does NOT grow history while a plan revision does; otherwise dropped and
     the limitation documented.
   - `prev_content is None` → `'unknown'` (no baseline yet).
   - `prev_content == curr_content` → `'none'`.
   - changed while `awaiting_input` is not True → `'work'` (output produced
     outside a recognized prompt).
   - changed while at a prompt, **`prev_kind != curr_kind`** → `'work'` — a
     different dialog kind is progression, decided before any boundary work
     (hardening 7).
   - changed while at a prompt, same kind — dispatch on the kind:
     - kind in `workflow_phase.QUESTION_WIDGET_KINDS[agent]` (chip-rendering
       question widgets): anchor both captures with
       `workflow_phase.current_question_block(lines)` (`workflow_phase.py:304`
       — the t1420 currency anchor; reuse, do not re-derive). Block located
       in both: content **above** the block differs → `'work'` (a sub-tick
       episode collapses the answered widget into scrollback and grows it);
       difference confined to the block → `'selection_only'`; unlocatable in
       either → `'unknown'`.
     - kind with an entry in `NATIVE_DIALOG_BOUNDARIES: dict[(agent, kind),
       re.Pattern]` — initially `("claude", <plan-approval kind>)` only,
       pattern = the dialog's **top boundary line**, pinned from the
       pre-phase revised-plan fixture and maintained in-place like the
       readiness patterns (t1474 practice). Locate the boundary
       bottom-up in both captures; found in both → same above-boundary
       comparison as the chip path; not found → `'unknown'`.
     - any other kind → `'unknown'` (no strategy — conservative).
   - `'unknown'` never satisfies the latch (conservative), and never resets
     anything — tri-state discipline.
   Pure (imports only `workflow_phase` + `re`); the caller feeds it the
   followed pane's `snap.content` / `snap.awaiting_input_kind` from
   consecutive ticks (already captured — no new tmux traffic).

3. **Prompt composer**, same module:
   ```python
   def compose_recheck_prompt(phase: str | None, expected_round: int | None) -> str
   ```
   Total over all inputs: PLAN → "…run the next plan-challenge review round";
   IMPLEMENT/POSTIMPL → "…impl-challenge…"; None/UNKNOWN/garbage → generic
   "run the next review round". When `expected_round` is not None, weave in
   `recheck round <N>` (mechanically anchored round — producers honor it per
   t1159_1). Single line, no `\n` (injection is single-line literal).
   **t1493 alignment (coordination note above):** the wording must contain
   the routing trigger t1493's `SKILL.md.j2` Step-3 re-review entry matches,
   so the injected line deterministically re-enters the review sub-procedure
   and re-emits the block — read the landed entry at implementation time; if
   t1493's producer half has not landed, surface at review that the loop's
   happy path depends on it.

4. **Shadow-agent resolution seam — `.aitask-scripts/monitor/monitor_core.py`**
   (finding 4: the shadow pane is a bare id; its agent is not readable today):
   - Extend `shadow_query_args()` (377-383) to
     `#{pane_id}\t#{@aitask_shadow_target}\t#{pane_current_command}`.
     `match_shadow_pane` (327-353) is untouched and keeps working (reads only
     fields 0-1; `len < 2` guard unchanged).
   - New pure `match_shadow_pane_info(list_output, followed_pane_id) ->
     tuple[str, str] | None` — same selection logic (newest `%N` wins),
     returning `(pane_id, current_command)`; a 2-field line (old format /
     stub) yields command `""`. Re-implement `match_shadow_pane` as
     `info[0] if info else None` so the two can never drift.
   - New `async find_shadow_pane_info_async(monitor, followed_pane_id) ->
     tuple[bool, str | None, str]` beside `find_shadow_pane_async` (429-439),
     same `tmux_run_async` + timeout shape but returning `(ok, pane, command)`
     — the `ok` discriminator mirrors `find_shadow_pane_status` (386-412,
     t1216_4): `ok=False` for no monitor / nonzero rc / timeout (query
     unanswerable), `(True, None, "")` for verified "no shadow". The review
     loop is a *decision* consumer (auto-disarm destroys armed state), so it
     must not consume the fail-open collapsed view (hardening 2). Existing
     helpers keep their signatures.
   - The shadow's agent key is then
     `workflow_phase.agent_key_from_command(command)` — the same canonicalizer
     used for the followed agent (one shared canonicalizer; unrecognized ⇒
     `""` ⇒ not in `SHADOW_READY_DETECTORS` ⇒ arm-refusal / auto-disarm).
   - **`TmuxPaneInfo` gains `history_size: int | None = None`** (hardening
     10), parsed from `#{history_size}` appended to **both** discovery
     list-panes formats (the sync and async sites currently listing
     `#{pane_id} #{pane_pid} #{pane_current_command} …`) — zero extra tmux
     round trips; a missing/unparsable field stays None (older stub lines in
     tests keep working).

5. **Minimonitor wiring** — `.aitask-scripts/monitor/minimonitor_app.py`:
   - `__init__` (state body 361-436): `self._review_loop =
     ReviewLoopController()`, shadow-capture hash ring for stability (last
     hash + consecutive-stable count), `self._loop_banner_text = ""` seam.
   - `BINDINGS` (328-347): `Binding("L", "toggle_review_loop",
     "Auto-recheck loop", show=False)` (`L` verified free; minimonitor has no
     `check_action` — no relabel hazard).
   - `action_toggle_review_loop`: armed → disarm + notify. Else per-action
     refusals in order: no own-window agent snapshot
     (`_find_own_agent_snapshot()`, 726) → warning;
     `workflow_phase.live_tiers_available(workflow_phase.agent_key_from_command(
     snap.pane.current_command))` False → "Auto-recheck unavailable for
     '<agent>' — no prompt detection yet (t1467)"; no shadow pane (via
     `find_shadow_pane_info_async`) → "press 'e' to launch one"; shadow
     agent's key not in `SHADOW_READY_DETECTORS` → "auto-recheck unavailable:
     shadow agent '<a>' has no readiness detection yet". Then arm + banner +
     notify.
   - `_service_review_loop(snap, shadow_ok, shadow_pane, shadow_command)`
     called from **all three** branches of `_maybe_offer_concerns`
     (2314-2405): agent-gone early return (2328-2330) →
     `(None, True, None, "")`; shadow-gone early return (2331-2337) → the
     lookup's actual `(ok, pane, command)`; main path after
     `_restamp_shadow_phase` (2351) → the resolved values.
     `_maybe_offer_concerns` switches its lookup to
     `find_shadow_pane_info_async` (same query, richer return); the concern
     *offer* path keeps today's fail-open behavior (any falsy pane → return),
     only the loop service discriminates. Controller inputs:
     - `agent_present` **tri-state via discovery liveness** (hardening 5):
       snapshot present → True; snapshot absent → consult
       `self._monitor.last_discovered_agents()` /
       `last_enumerated_sessions()` with the own identity
       `(self._session, self._own_window_name)`: still discovered (capture
       failed) or session unenumerated → None; session enumerated and agent
       absent → False. Small helper `_derive_agent_presence(snap)` so the
       rule is unit-testable.
     - `shadow_present = None if not shadow_ok else bool(shadow_pane)`
       (hardening 2).
     - `stale=self._shadow_feedback_stale` (cached tri-state, refreshed every
       other tick at 2343-2346 — no new tmux traffic).
     - `work_signal=classify_followed_change(prev_content, prev_kind,
       snap.content, snap.awaiting_input_kind, snap.awaiting_input, agent)`
       (hardenings 6+7); the service keeps a **baseline**
       `self._loop_baseline = (content, kind, pane_id, history_size)` from
       the last successful snapshot, updated after classification.
       **Baseline retention (hardening 8):** the baseline is *preserved*
       across indeterminate ticks (`agent_present` None — capture failed but
       the agent is still discovered) so a response produced during the gap
       still classifies as `'work'` against the pre-gap prompt; it resets
       only on verified departure and on pane identity replacement
       (`snap.pane.pane_id != baseline.pane_id`). **Arm-time seeding
       (hardening 9):** `action_toggle_review_loop` seeds the baseline from
       the arm-time snapshot (always present — the arm refusals require it),
       so a fresh arm followed by a complete sub-tick response still
       classifies `'work'` on the first tick.
     - `shadow_ready` from the readiness dispatch over the tick's
       `capture_shadow_text` result + hash ring.
     - `modal_open=isinstance(self.screen, ModalScreen)` (package convention,
       finding 3), `now=time.monotonic()`.
     Per-tick re-resolve of the shadow agent from `shadow_command`;
     unsupported swap → auto-disarm (visible). On a `'fire'` reservation the
     service reads `controller._delivery_token` (returned by the granting
     `tick`), awaits `_fire_shadow_recheck(..., token)` and routes its
     outcome to `confirm_fire(token, now)` / `abort_fire(token)` /
     `disarm()`; stale-token outcomes no-op by contract (hardening 4).
     `action_toggle_review_loop` arms with
     `controller.arm(pending_work=(self._shadow_feedback_stale is True))`.
   - `_fire_shadow_recheck(shadow_pane, snap, tick_capture, token)`
     (hardenings 1+4 — verified two-step delivery; returns
     `'sent' | 'not_ready' | 'failed'`):
     1. **Pre-send revalidation:** fresh `capture_shadow_text(shadow_pane)`
        immediately before delivery; **after this await, first re-check
        `controller.delivery_valid(token)`** — a disarm/supersession during
        the capture aborts with no sends. Then re-run `shadow_prompt_ready`
        on the fresh capture with
        `hash_stable = (hash(fresh) == hash(tick_capture))` — the fresh
        capture must both be ready *and* match the tick capture the decision
        was made on. Anything else (changed content, new dialog, failed
        capture) → **no send at all**, return `'not_ready'` → `abort_fire`
        (streak preserved, banner "waiting for shadow to settle").
     2. `expected_round` from `parse_block_meta(fresh capture)`
        (`concern_parser.py:485`; +1; None → no expected round — never guess,
        per t1159_1 sibling notes); `prompt = compose_recheck_prompt(phase,
        expected_round)` with `phase` from
        `self._phase_for_snap(snap, info).phase` (969-978) when resolvable,
        else None.
     3. **Ordered sends, Enter gated on the write:**
        `if not self._monitor.send_keys(shadow_pane, prompt, literal=True)` →
        return `'failed'` — **Enter is never sent after a failed prompt
        write** (it would submit pre-existing composer text or answer a
        dialog). The service then `disarm()`s and notifies visibly.
        `if not send_keys(shadow_pane, "Enter")` → return `'failed'` with the
        leftover-text recovery message: "recheck text left in the shadow
        composer — submit or clear it there manually"; service `disarm()`s
        and notifies that message (severity warning). Both sends
        `monitor_core.py:2458-2472`, `--` separator seam.
     4. `'sent'` → service calls `confirm_fire(now)`, updates the banner.
     **The function receives no followed pane id** — structurally incapable
     of writing the followed pane.
   - Banner `#mini-loop-status`: `_set_loop_banner(text)` copying
     `_set_shadow_stale_banner` (2139-2149) — records
     `self._loop_banner_text` then best-effort `query_one().update()`; CSS
     block after 266 (`$warning` background to distinguish from the `$error`
     stale banner; `height: auto` so empty ⇒ 0 rows); mounted in `compose`
     beside 441. States: `⟳ auto-recheck ARMED` / `⟳ waiting for shadow to
     settle` / `⟳ recheck #N sent — waiting for shadow` / "" when disarmed.
   - Key-hints Static (444-454): add `L:auto-recheck loop`.

6. **`aidocs/framework/shadow_agent.md`**: add the "Review-loop automation"
   section with the safety contract now (t1159_4 does the full docs sweep):
   (1) followed pane never written (structural: `_fire_shadow_recheck` has no
   followed pane id; negative test); (2) opt-in + permanently visible banner;
   (3) edge-driven once per episode + 45s cooldown; (4) positive-evidence
   debounce (3 ticks); (5) never inject into a busy shadow — `shadow_ready is
   True` = three-part positive readiness (agent-specific empty-composer AND no
   dialog-pattern match AND hash stability ≥2 ticks; hash alone never
   sufficient), hold otherwise; (6) auto-disarm on **positively verified**
   shadow/agent disappearance (visible) — verified via the tmux lookup's
   status discriminator and the discovery-facts liveness seam respectively;
   an indeterminate lookup, an unenumerated session, or a snapshot missing
   for a still-discovered pane (capture failure) pauses, never disarms;
   pause on modal; (7) single-line literal injection only; (8) phase never
   gates firing; (9) delivery is a serialized, verified two-step — at most
   one delivery is ever in flight (synchronous reservation + generation
   token; overlapping refresh ticks cannot double-fire), readiness is
   revalidated on a fresh capture immediately before sending with the token
   re-checked after the await, Enter is never sent after a failed prompt
   write, and either partial failure auto-disarms visibly naming any leftover
   composer text; (10) a new episode requires positively **classified** agent
   work since the previous fire (content growth outside the current question
   block, or output while not at a prompt) — widget selection-only redraws
   never refire the loop, and a sub-tick work episode still counts. Also
   document the **bounded-capture residual** (hardening 10): the trigger and
   the work latch both read a `capture_lines`-bounded tail, so a fully
   sub-tick revision whose settled tail is identical and (if the rule
   shipped) grows no history is invisible — the loop simply does not fire
   for it; the manual "refetch and recheck" path remains available.

## Coordination note — concern status line goes to a new sibling (user decision, 2026-08-12)

At plan review the user requested an **always-shown minimonitor concern status
line**: concern round + review date/time (from `parse_block_meta` of the tick's
shadow capture) plus a stale/fresh glyph (from `_shadow_feedback_stale`).
Decided routing: **a new t1159 sibling task** (create post-approval as a child
of t1159, depending on t1159_2 so the minimonitor compose/CSS edits serialize;
data dependencies — round metadata t1159_1, staleness t1104 — are already
landed). Not in this plan's scope; this plan's banner work must not foreclose
it (the loop banner stays a separate transient `#mini-loop-status` widget; the
always-on line will be its own widget). Cross-reference t1448, which keys the
full monitor's badge currency off the same `(round, reviewed_at)` metadata —
the sibling's task body must link both directions (t1448 ↔ new sibling).

## Verification

- **New `tests/test_review_loop.py`** (pure): debounce exactly 3 positive
  ticks; `False`/`None` resets; `'fire'` permission + `confirm_fire` → FIRED;
  no second permission while FIRED even with `stale True` forever (edge
  contract); `stale False` re-arms, `None` does not; cooldown blocks an
  immediate second episode; modal pause (no fire, no disarm, streak reset);
  shadow-busy hold (trigger satisfied + ready False/None → no fire, streak
  preserved, fires on first ready tick); **reservation API (hardening 4)**:
  a granted `'fire'` enters DELIVERING synchronously — an interleaved second
  `tick()` between reservation and outcome returns `'none'` and grants no
  second permission; `abort_fire(token)` returns to WAITING with streak
  preserved and the next ready tick re-permits; `confirm_fire(token, now)`
  stamps cooldown and clears `work_seen`; stale tokens (after `disarm()` or
  supersession) no-op and return False; `delivery_valid` flips False the
  moment the reservation is retired; **work latch (hardening 6)**:
  selection-only-redraw scenario — after a confirmed fire, every tick has
  `awaiting_input` True and `work_signal='selection_only'` while `stale`
  flips True → no second permission ever; sub-tick episode positive control —
  one `work_signal='work'` tick (never any `awaiting_input False` sample)
  then the same sequence → permission granted; arm-then-navigate —
  `arm(pending_work=False)` then `selection_only` ticks → no first fire;
  `arm(pending_work=True)` → first fire permitted without further work;
  **fresh-arm sub-tick episode (hardening 9)** — arm at prompt A
  (`pending_work=False`, baseline seeded from the arm snapshot), next tick
  already shows prompt B → classified work against A, latch opens;
  `'unknown'`/`'none'` leave the latch unchanged;
  **`classify_followed_change`**: no baseline → unknown; identical → none;
  change while not awaiting → work; kind change between ticks → work;
  chip-widget path — above-block growth → work, block-confined diff →
  selection_only, unlocatable chip → unknown; **native plan-approval path
  (hardening 7)** — the two real revised-plan selection states →
  selection_only, growth above the dialog boundary → work, boundary
  unlocatable → unknown; **history-growth rule (hardening 10, if it ships)**
  — identical bounded tails + `curr_history_size > prev` → work; None on
  either side or a shrink → falls through to the content rules; kind with no
  strategy → unknown (all fixture-driven, reusing the pre-phase widget
  captures at production capture depth);
  **presence tri-states**: `shadow_present=None` (query failure) and
  `agent_present=None` (capture-failed/indeterminate) pause — streak, latch
  and armed state preserved, no disarm, and a following `True` tick continues
  the episode; `False` on either → auto_disarm (retiring any in-flight
  delivery token); DISARMED inert; `shadow_prompt_ready` against
  the pre-phase inline fixtures (at-rest → True;
  streaming/at-dialog/typed-text/failed-capture → not True; unknown agent →
  not True; hash-unstable → not True); `compose_recheck_prompt` totality
  (every `workflow_phase.PHASES` value + None + garbage, with/without round →
  non-empty single line, no newline, round named when given).
- **`tests/test_minimonitor_concern_action.py`** (extend; `_FakeMon` gains a
  `send_keys` recorder): `match_shadow_pane_info` cases in
  `MatchShadowPaneTests` (3-field format; 2-field back-compat → command `""`;
  newest-wins preserved; `match_shadow_pane` unchanged results);
  `find_shadow_pane_info_async` status paths — nonzero rc and timeout →
  `(False, None, "")`, verified absence → `(True, None, "")`; arm refusals
  both sides (followed w/o live tiers; claude followed + codex shadow →
  visible refusal **whose message names the shadow's agent** — the t1493
  live session proves this configuration is not a corner case — controller
  DISARMED); mid-loop shadow-agent swap → auto-disarm; **lookup-failure resilience** — armed loop + `ok=False` tick →
  still armed, no disarm notify; verified absence → visible auto-disarm;
  **agent-presence derivation (hardening 5)** — `_derive_agent_presence`:
  snapshot present → True; absent but `(session, window)` in the fake
  monitor's `last_discovered_agents()` → None (armed loop survives the
  capture-failure tick); session enumerated, agent gone from discovery →
  False (visible auto-disarm); session unenumerated → None; **baseline
  retention (hardening 8)** — prompt A tick, then a capture-failure tick
  (agent still discovered), then a revised-prompt tick → classified `work`
  against the pre-gap baseline, latch opens; pane-id replacement resets the
  baseline (next tick → unknown, no false work); **overlapping
  service calls (hardening 4)** — two concurrent `_service_review_loop`
  invocations with a fire-ready state → exactly one delivery (one send pair),
  the second sees DELIVERING; disarm during the fire's capture await →
  `delivery_valid` False → zero sends; fire
  path — exactly two `send_keys` calls, both targeting the shadow pane id,
  literal prompt then Enter, followed pane id in **no** send call; recheck
  text carries round from the previous block meta (and no round when meta is
  None); **delivery failures, both orders** — prompt write fails → exactly
  one send call (no Enter), visible disarm notify; prompt succeeds + Enter
  fails → both calls made, disarm notify carries the leftover-composer
  recovery text; **pre-send revalidation** — ready at tick, changed/busy
  fresh capture at fire time → zero send calls, controller still WAITING
  (abort path), fires cleanly on the next ready tick; `_loop_banner_text`
  seam transitions; **advisory negative control** — force a wrong phase and
  UNKNOWN through the controller + `_fire_shadow_recheck`: fires in every
  case, nothing refused (complements `tests/test_shadow_phase_advisory.sh`;
  a loop that gates on phase must fail this).
- Live smoke: extend `tests/test_minimonitor_concern_smoke.py` (real tmux on
  the per-PID private socket): a real pane receives the injected recheck line
  verbatim (capture-pane after `_fire_shadow_recheck`).
- `bash tests/run_all_python_tests.sh` — final stderr verdict line only
  (`set -o pipefail` / `${PIPESTATUS[0]}` if piping).
- Reference **Step 9 (Post-Implementation)** of the task-workflow skill for
  cleanup, archival, and merge.

## Risk

### Code-health risk: medium
- New behavior class: minimonitor writes keys into a live (shadow) pane from a
  timer tick · severity: medium · → mitigation: inline pre-phase
  live_trigger_positive_control (trigger inputs proven live before wiring) +
  edge-driven controller + send-target negative test (fire path names the
  followed pane in no send call)
- Partial delivery (two-send sequence) can strand or wrongly submit composer
  text; tick-time readiness is stale at delivery; overlapping refresh ticks
  could double-deliver · severity: medium · → mitigation: pre-send
  revalidation on a fresh capture + Enter gated on the prompt write's return
  + visible disarm with recovery text + synchronous DELIVERING reservation
  with a generation token, both failure orders and the overlap interleavings
  test-pinned (plan-review hardenings 1 and 4)
- The `shadow_query_args()` format gains a third field consumed by two pure
  matchers and three lookup helpers; a drift between `match_shadow_pane` and
  `match_shadow_pane_info` would desynchronize pane vs agent resolution ·
  severity: low · → mitigation: `match_shadow_pane` re-implemented on top of
  `match_shadow_pane_info` (cannot drift), 2-field back-compat pinned in
  `MatchShadowPaneTests`
- `_maybe_offer_concerns` is a documented-races surface gaining a per-tick
  service call in all three branches · severity: medium · → mitigation:
  `_service_review_loop` is a pure-input dispatcher (controller decides;
  inputs snapshotted before any await per the established pattern), and the
  three-branch coverage is test-pinned

### Goal-achievement risk: medium
- Trigger inputs (`awaiting_input` on real widgets, staleness stamp timing)
  are implementation-reported, not live-confirmed (t1475 unrun) — loop could
  misfire or never fire · severity: medium · → mitigation: inline pre-phase
  live_trigger_positive_control
- The loop's happy path depends on t1493's producer routing fix — until it
  lands, an injected recheck re-enters the skill as prose, no block is
  emitted, the round never advances, and the picker shows stale concerns as
  current (verified live) · severity: high · → mitigation: t1493 owns the
  fix (its producer half lands before or with this child); this plan aligns
  `compose_recheck_prompt` with its routing trigger and surfaces the
  dependency at review if unlanded (coordination note)
- Staleness advances on any content diff, so widget selection-only redraws
  could fire redundant reviews (including immediately after arming); a
  transient tmux lookup failure or a followed-pane capture failure could
  silently destroy an armed loop; a sampled work latch could wedge after a
  sub-tick agent response · severity: medium · → mitigation:
  classifier-driven work latch anchored on `current_question_block` +
  native-dialog boundaries, arm-time baseline seeding, and a
  pre-phase-validated `#{history_size}` growth signal with the residual
  documented (selection-redraw, arm-then-navigate, sub-tick-episode,
  capture-gap, and bounded-tail scenarios test-pinned at production capture
  depth) + tri-state shadow **and** agent presence with disarm only on
  verified absence (plan-review hardenings 2, 3, 5, 6, 7, 8, 9, 10)
- The empty-composer readiness pattern is version-sensitive LLM-UI text with
  no existing in-repo precedent (finding 6) — a Claude Code UI update could
  silently break readiness and stall the loop in "waiting for shadow to
  settle" · severity: medium · → mitigation: patterns maintained in-place
  (t1474 practice), pinned against captured fixtures; the hold state is
  visible in the banner (never a silent stall); t1159_5's live checklist
  observes a real round-2 fire

### Planned mitigations
- timing: pre-phase | name: live_trigger_positive_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement (trigger inputs unverified live) | desc: Positive control — confirm awaiting_input + staleness assert on a live Claude pane before wiring the loop, and capture the shadow-readiness fixtures pinning shadow_prompt_ready
