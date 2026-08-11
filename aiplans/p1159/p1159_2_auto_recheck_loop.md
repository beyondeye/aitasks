---
Task: t1159_2_auto_recheck_loop.md
Parent Task: aitasks/t1159_shadow_review_loop_automation.md
Sibling Tasks: aitasks/t1159/t1159_1_round_metadata_concern_block.md, aitasks/t1159/t1159_3_spinoff_triage_arm.md, aitasks/t1159/t1159_4_docs_and_integration.md
Archived Sibling Plans: aiplans/archived/p1159/p1159_*_*.md
Worktree: . (current directory — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
---

# Plan — t1159_2: Minimonitor auto-recheck loop

Parent design: `aiplans/p1159_shadow_review_loop_automation.md`. Depends on t1159_1 (round metadata: `parse_block_meta` for expected-round derivation; dedup lift makes an automated round 2 visible at all).

## Pinned decisions

- Minimonitor-orchestrated (user-confirmed). The loop drives only the **shadow** pane; the followed pane is never written. Forwarding stays clipboard-only.
- Arm/disarm via `L`; loop state lives in-process (no new pane options).
- Phase pre-selects recheck **wording** only; it never gates firing (advisory-only contract — t1311/t1420 scar; `tests/test_shadow_phase_advisory.sh` negative-control pattern).
- Arming refuses visibly on **agent capability** gaps, both sides: followed agent without live prompt tiers (t1467), shadow agent without a readiness detector.

### Pre-phase (risk mitigations)

- **live_trigger_positive_control** (confirmed inline mitigation): before wiring the loop, drive a real Claude pane through the monitor capture path (`capture-pane -p -e` + `strip_ansi` + `classify_content`) and confirm live that (a) `awaiting_input` asserts at an AskUserQuestion widget and at the ExitPlanMode approval dialog, and (b) `_shadow_feedback_stale` flips True after a followed-pane change (t1475 never ran — these inputs are implementation-reported, not confirmed). In the same session, capture the **shadow-readiness fixtures**: shadow at rest (empty composer), streaming output, parked at a dialog, holding typed composer text. Store them under `tests/fixtures/` (follow existing fixture layout if one exists) — they pin `shadow_prompt_ready`.

## Steps

1. **New pure module `.aitask-scripts/monitor/review_loop.py`** (no tmux, no Textual, no I/O — testable like `concern_parser.py`):

   ```python
   DEBOUNCE_TICKS = 3        # ~9s at the 3s tick; only positive evidence counts
   COOLDOWN_SECONDS = 45.0   # min gap between fires, across episodes
   DISARMED, WAITING, FIRED = "disarmed", "waiting", "fired"

   class ReviewLoopController:
       """Decides fire/hold/disarm for the shadow auto-recheck (t1159).

       EDGE-driven: firing a recheck makes the shadow re-read the followed
       pane, which re-stamps @aitask_shadow_analyzed_at and CLEARS the very
       staleness that triggered it. After a fire the controller stays FIRED
       until it positively observes stale == False (the shadow acted), then
       re-arms. Level-driven logic would fire forever or never.
       """
       def tick(self, *, agent_present, shadow_present, awaiting_input,
                stale, shadow_ready, modal_open, now) -> str:
           # 'none' | 'fire' | 'auto_disarm'
           # DISARMED: inert.
           # absence of agent or shadow -> disarm(), 'auto_disarm'.
           # modal_open: pause — reset streak, never fire, never disarm.
           # FIRED: stale is False -> WAITING; None preserves; never fire.
           # WAITING: streak += 1 iff awaiting_input is True and stale is True,
           #          else streak = 0 (t1446 AUTO_CLOSE pattern).
           # fire iff streak >= DEBOUNCE_TICKS and now - fired_at >= COOLDOWN
           #          and shadow_ready is True   # hold otherwise, streak kept
   ```
   Fire-condition detail (from the review concerns): when the debounced trigger is satisfied but `shadow_ready` is not True, **hold** — keep the streak satisfied (do not reset), surface "waiting for shadow to settle" via the banner, and fire on the first ready tick. `rounds_fired` is display-only (never the shadow's round number).

2. **Shadow readiness — positive prompt detection**, same module:
   - `shadow_prompt_ready(text: str, agent: str, hash_stable: bool) -> bool | None` requiring **all three**: (a) positive — the tail shows that agent's **empty** input composer (pattern pinned from the pre-phase fixtures; no typed text after the prompt char); (b) negative — no dialog/prompt pattern from `prompt_patterns.PROMPT_PATTERNS_BY_AGENT[agent]` matches the tail (a dialog is a different interaction — Enter there answers it); (c) `hash_stable` (capture hash unchanged ≥2 consecutive ticks, computed by the caller from the per-tick shadow capture). Unknown agent / failed capture / any condition indeterminate ⇒ not-ready (`False`/`None`, never `True`). Hash stability alone is **never** sufficient.
   - `SHADOW_READY_DETECTORS: dict[str, ...]` — per-agent dispatch, initially `{"claude": ...}` only. The shadow's agent is independently selectable (`E` → any configured codeagent), so a Claude followed pane can legitimately have a Codex/OpenCode shadow; without a detector the loop must refuse at arm time, not hold forever.
   - Composer patterns are version-sensitive: maintain in-place (t1474 practice), pin against the pre-phase fixtures.

3. **Prompt composer**, same module:
   ```python
   def compose_recheck_prompt(phase: str | None, expected_round: int | None) -> str
   ```
   Total over all inputs: PLAN → "…run the next plan-challenge review round"; IMPLEMENT/POSTIMPL → "…impl-challenge…"; None/UNKNOWN/garbage → generic "run the next review round". When `expected_round` is not None, weave in `recheck round <N>` (mechanically anchored round — producers honor it per t1159_1). Single line, no `\n` (injection is single-line literal).

4. **Minimonitor wiring** — `.aitask-scripts/monitor/minimonitor_app.py`:
   - `__init__` (~line 433): `self._review_loop = ReviewLoopController()`, shadow-capture hash ring for stability, `_loop_banner_text` seam.
   - `BINDINGS` (326-345): `Binding("L", "toggle_review_loop", "Auto-recheck loop", show=False)` (`L` verified free).
   - `action_toggle_review_loop`: armed → disarm + notify. Else per-action refusals in order: no own-window agent snapshot → warning; `live_tiers_available(agent_key_from_command(snap.pane.current_command))` False → "Auto-recheck unavailable for '<agent>' — no prompt detection yet (t1467)"; no shadow pane → "press 'e' to launch one"; shadow pane's agent (its `current_command` → `agent_key_from_command`) not in `SHADOW_READY_DETECTORS` → "auto-recheck unavailable: shadow agent '<a>' has no readiness detection yet". Then arm + banner + notify.
   - `_service_review_loop(snap, shadow_pane)` called from **all three** branches of `_maybe_offer_concerns` (2286-2369): agent-gone early return → `(None, None)`; shadow-gone early return → `(snap, None)`; main path after `_restamp_shadow_phase` (2323) → `(snap, shadow_pane)`. Inputs: `stale=self._shadow_feedback_stale` (cached tri-state, refreshed every other tick — no new tmux traffic), `shadow_ready` from the readiness dispatch over the tick's `capture_shadow_text` result + hash ring, `modal_open=len(self.screen_stack) > 1`, `now=time.monotonic()`. Per-tick re-resolve of the shadow agent; unsupported swap → auto-disarm (visible).
   - `_fire_shadow_recheck(shadow_pane, snap)`: `expected_round` from `parse_block_meta(last shadow capture)` (+1, None before any block); `prompt = compose_recheck_prompt(phase_sig.phase if phase_sig else None, expected_round)`; `self._monitor.send_keys(shadow_pane, prompt, literal=True)` then `send_keys(shadow_pane, "Enter")` (monitor_core.py:2458-2472; `--` separator seam, pinned by `tests/test_monitor_tmux_injection.sh`). Notify success/failure. **The function receives no followed pane id** — structurally incapable of writing the followed pane.
   - Banner `#mini-loop-status`: copy `_set_shadow_stale_banner` (2137-2147) + CSS after 265 (`$warning` background; empty ⇒ 0 rows). States: `⟳ auto-recheck ARMED` / `⟳ waiting for shadow to settle` / `⟳ recheck #N sent — waiting for shadow` / "" when disarmed.
   - Key-hints Static (442-452): add `L:auto-recheck loop`.

5. **`aidocs/framework/shadow_agent.md`**: add the safety contract now (t1159_4 does the full docs sweep):
   (1) followed pane never written (structural: `_fire_shadow_recheck` has no followed pane id; negative test); (2) opt-in + permanently visible banner; (3) edge-driven once per episode + 45s cooldown; (4) positive-evidence debounce (3 ticks); (5) never inject into a busy shadow — `shadow_ready is True` = three-part positive readiness (agent-specific empty-composer AND no dialog-pattern match AND hash stability ≥2 ticks; hash alone never sufficient), hold otherwise; (6) auto-disarm on shadow/agent disappearance (visible), pause on modal; (7) single-line literal injection only; (8) phase never gates firing.

## Verification

- **New `tests/test_review_loop.py`** (pure): debounce exactly 3 positive ticks; `False`/`None` resets; fire → FIRED; no second fire while FIRED even with `stale True` forever (edge contract); `stale False` re-arms, `None` does not; cooldown blocks immediate second episode; modal pause (no fire, no disarm); shadow-busy hold (trigger satisfied + ready False/None → no fire, streak preserved, fires on first ready tick); agent/shadow absence → auto_disarm; DISARMED inert; `shadow_prompt_ready` against the pre-phase fixtures (at-rest → True; streaming/at-dialog/typed-text/failed → not True; unknown agent → not True); `compose_recheck_prompt` totality (every `workflow_phase.PHASES` value + None + garbage, with/without round → non-empty single line, round named when given).
- **`tests/test_minimonitor_concern_action.py`** (extend; `_FakeMon` + `MiniMonitorApp.__new__` + spy notify): arm refusals both sides (followed w/o live tiers; claude followed + codex shadow → visible refusal, controller DISARMED); mid-loop shadow-agent swap → auto-disarm; fire path — exactly two `send_keys` calls, both targeting the shadow pane id, literal prompt then Enter, followed pane id in **no** send call; recheck text carries round from previous block meta; banner seam transitions; **advisory negative control** — force a wrong phase and UNKNOWN through the controller + `_fire_shadow_recheck`: fires in every case, nothing refused (complements `tests/test_shadow_phase_advisory.sh`; a loop that gates on phase must fail this).
- Live smoke: extend `tests/test_minimonitor_concern_smoke.py` (or a sibling shell test modeled on `tests/test_monitor_tmux_injection.sh`): a real tmux pane receives the injected recheck line verbatim.
- `bash tests/run_all_python_tests.sh` — final stderr verdict line only.
- Reference **Step 9 (Post-Implementation)** of the task-workflow skill for cleanup, archival, and merge.
