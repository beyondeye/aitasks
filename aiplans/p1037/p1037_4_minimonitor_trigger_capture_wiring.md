---
Task: t1037_4_minimonitor_trigger_capture_wiring.md
Parent Task: aitasks/t1037_minimonitor_shadow_concern_picker.md
Sibling Tasks: aitasks/t1037/t1037_5_manual_verification_minimonitor_shadow_concern_picker.md
Archived Sibling Plans: aiplans/archived/p1037/p1037_1_concern_format_spec_and_parser.md, aiplans/archived/p1037/p1037_2_shadow_skill_emit_concern_block.md, aiplans/archived/p1037/p1037_3_concern_picker_modal.md, aiplans/archived/p1037/p1037_6_richer_concern_block_body_framing.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-22 10:47
---

# Plan: Minimonitor trigger + capture wiring + auto-offer (t1037_4)

## Context

Closes the t1037 loop inside the **minimonitor TUI**: a hotkey that captures the
shadow pane bound to the followed code-agent, parses its concerns (t1037_1
parser), opens the picker modal (t1037_3), and on confirm copies the selected
concerns to the clipboard with a preamble. Plus a proactive auto-offer when a
fresh concerns block appears on the shadow pane.

Siblings t1037_1 (parser), t1037_2 (shadow emit), t1037_3 (modal), t1037_6
(richer framing) all landed and are archived. This child + t1037_5 (manual
verification) are the only ones left.

**This plan was re-verified against the live codebase (verify path).** Two of the
original task's stated assumptions were wrong and are corrected below — they
change the implementation, so they are called out explicitly rather than silently
adjusted.

### Verified facts (current code)

- **Parser** `monitor/concern_parser.py`: `parse_concerns(capture_text: str) -> list[Concern]`,
  `has_concern_block(text: str) -> bool`, `build_clipboard_payload(concerns, preamble=DEFAULT_PREAMBLE) -> str`.
  `Concern = NamedTuple(priority, region, body)`. **Requires wrap-joined,
  escape-free input** (`tmux capture-pane -J`, no `-e`) — the "capture-join
  contract" in `aidocs/framework/shadow_concern_format.md`. The capture path
  (this task) owns the join.
- **Modal** `monitor/monitor_shared.py`: `ConcernPickerModal(concerns: list[Concern], narrow: bool = False)`.
  Dismisses with the **selected** `list[Concern]` on confirm (Enter/OK), the full
  list on `A` (copy-all), and `None` on Esc/Cancel. It is pure-UI: its docstring
  explicitly states the **caller** runs `build_clipboard_payload` + `copy_to_clipboard`.
- **`minimonitor_app.py`**: key `c` is **free**; `_find_own_agent_snapshot() ->
  PaneSnapshot | None` exists (`snap.pane.pane_id`); `self._monitor.tmux_run([...])`
  is the Python gateway entry (already used by `action_launch_shadow` to
  `set-option` `@aitask_shadow_target`); `copy_to_clipboard` is the inherited
  Textual App method; refresh loop is `_refresh_data` via `set_interval(self._refresh_seconds≈3s)`.
- **`monitor_core.py`**: `SHADOW_TARGET_OPTION = "@aitask_shadow_target"`,
  `is_shadow_target(value) -> bool`.

### Correction 1 — reverse shadow-pane lookup CANNOT scan snapshots

The original task said *"minimonitor already reads `@aitask_shadow_target` per
pane during discovery (parts[8]); add a reverse lookup helper"* — implying a scan
of `self._snapshots`. **That is wrong.** `monitor_core._parse_list_panes` reads
`parts[8]` only to **drop** shadow panes (`if is_shadow_target(parts[8]):
continue`). Shadow panes never enter `self._snapshots`, and the target value is
**not stored** on any `PaneSnapshot`. So the lookup must issue a **fresh
gateway tmux query**, not a snapshot scan.

### Correction 2 — no existing capture path feeds the parser correctly

The parser needs wrap-joined, escape-free text. Neither existing path qualifies:
`aitask_shadow_capture.sh` is escape-free but omits `-J`; `monitor_core._capture_args`
has `-e` (escapes) and no `-J`. Resolution: **add `-J` to `aitask_shadow_capture.sh`**
and reuse it (option (a)). This is exactly what `shadow_concern_format.md`
prescribes ("if it routes through `aitask_shadow_capture.sh`, that helper must
join wrapped lines"), keeps a single cleaning path shared with the shadow skill
(parent constraint: "reuse the same path the shadow skill uses"), and the `-J`
addition only joins soft-wrapped rows — benign/improving for the shadow skill's
prose reading, its only other consumer.

## tmux gateway compliance (MANDATORY)

Every tmux interaction routes through the gateway — Python `self._monitor.tmux_run([...])`,
shell `ait_tmux ...`. Never raw `tmux`; `tests/test_no_raw_tmux.sh` enforces it.
Touchpoints here:
- reverse lookup → `self._monitor.tmux_run(["list-panes", ...])` (Python gateway);
- `-J` capture → added to `aitask_shadow_capture.sh`, which already calls
  `ait_tmux capture-pane ...` (just add the flag).
Run `bash tests/test_no_raw_tmux.sh` in verification.

## Concurrency & failure discipline (applies to §2–§5)

**Never block the Textual event loop on the picker/auto-offer paths.** The
touchpoints that run inside the async picker action or the refresh loop — the
`list-panes` query and the `aitask_shadow_capture.sh` shell-out — MUST be **async
with a hard timeout** and total exception handling. (The one exception is the
duplicate-launch guard inside `action_launch_shadow`, which is an existing **sync**
action already issuing sync `tmux_run` calls on a one-shot keypress — it uses a
sync lookup; see §1b/§2.) A stalled tmux or a blocked helper must never hang the
app. Concretely:
- The capture and the query run via `asyncio.create_subprocess_exec(...)` wrapped
  in `asyncio.wait_for(..., timeout=_SHADOW_CAPTURE_TIMEOUT)` (a small module
  constant, e.g. 3s). Prefer the monitor's existing async gateway entry
  (`tmux_run`'s async sibling / `run_async`) for the `list-panes` query so it
  stays gateway-routed.
- `action_pick_concerns` becomes an **async action** (Textual supports `async
  def action_*`) so it can `await` the capture without blocking.
- **Failure degradation, by caller:**
  - **Hotkey path:** timeout / nonzero exit / exception → `notify("Could not read
    the shadow pane", severity="warning")` and return. No crash, no clipboard write.
  - **Auto-offer path (refresh tick):** any failure → **silently skip this tick**
    (no toast, no error spam), do not update the de-dup hash, try again next tick.
- A single private async helper centralizes this so both callers share identical
  timeout + error semantics.

## Implementation

### 1. Add `-J` to the shared capture helper

`.aitask-scripts/aitask_shadow_capture.sh`, `shadow_capture_pane()` (~line 73-77):
add `-J` to the `ait_tmux capture-pane` invocation. Update the adjacent comment
(lines 23-26) noting `-J` joins soft-wrapped rows (required by the concern parser;
harmless for prose). Keep `-e` omitted (escape-free output).

### 1b. Guard against duplicate shadows for the same followed pane

Root-cause fix for "multiple bound shadow panes" (concern 3): `action_launch_shadow`
does not currently prevent a second shadow on the same followed agent. Add a guard
at the top of `action_launch_shadow` (after resolving `followed_pane`): if
`self._find_shadow_pane_for_sync(followed_pane)` already returns a pane, **refuse**
— `notify("A shadow is already running for this agent", severity="warning")` and
return without spawning. `action_launch_shadow` stays **sync** and uses the **sync**
lookup (§2) — consistent with the sync `tmux_run` calls it already makes; no async
conversion of the existing action. One shadow per followed agent is the design
intent (`@aitask_shadow_target` is the lifecycle binding, `shadow_agent.md`),
making the picker's lookup unambiguous by construction rather than relying on a
fragile tie-break.

### 2. Reverse shadow-pane lookup (one pure matcher, sync + async readers)

In `minimonitor_app.py`, one pure matcher with two thin tmux readers so each caller
uses the right concurrency model (resolves the async/sync mismatch):
- `match_shadow_pane(list_output: str, followed_pane_id: str) -> str | None`
  (pure, module-level, unit-tested without tmux): parse `pane_id\t target` lines,
  return the `pane_id` whose `@aitask_shadow_target` equals `followed_pane_id`
  (empty target ⇒ not a shadow, via `is_shadow_target`).
  - **Multiple-match tie-break (defense-in-depth behind §1b):** if more than one
    pane matches (e.g. an orphaned live shadow that escaped cleanup), pick the
    **newest** deterministically — the largest numeric pane id (`%N` ids increase
    monotonically with creation) — and have the caller `notify` that multiple
    shadows were found. `list-panes -a` lists only live panes, so dead/stale
    panes never appear.
- Shared query argv: `["list-panes", "-a", "-F", "#{pane_id}\t#{@aitask_shadow_target}"]`.
- `_find_shadow_pane_for_sync(followed_pane_id) -> str | None`: **sync** `tmux_run`
  of the query → `match_shadow_pane`. Used **only** by the sync duplicate-launch
  guard (§1b). Returns `None` on `rc != 0` / no match.
- `async _find_shadow_pane_for(followed_pane_id) -> str | None`: **async** gateway
  entry (`run_async`) for the same query under the shared timeout (see Concurrency
  discipline) → `match_shadow_pane`. Used by the async picker action (§4) and the
  refresh-tick auto-offer (§5). Returns `None` on `rc != 0`, timeout, or no match.

### 3. Shared capture helper (async, timeout, used by action + auto-offer)

`_capture_shadow_text(shadow_pane: str) -> str | None`: async; run
`./.aitask-scripts/aitask_shadow_capture.sh <shadow_pane>` (now `-J`-joined,
escape-free) via `asyncio.create_subprocess_exec` under `asyncio.wait_for(...,
_SHADOW_CAPTURE_TIMEOUT)`. Return the cleaned stdout, or **`None`** on timeout /
nonzero exit / exception (callers branch on `None` per the discipline above).
Single capture path for both action and auto-offer so cleaning never diverges.
Resolve the script path relative to the repo root the same way other minimonitor
subprocess calls do.

### 4. Binding + `action_pick_concerns` (async)

- Add `Binding("c", "action_pick_concerns", "Concerns", show=False)` to BINDINGS
  (~142-156).
- `async def action_pick_concerns`:
  1. `snap = self._find_own_agent_snapshot()`; if `None` → `notify(..., severity="warning")` + return.
  2. `shadow_pane = await self._find_shadow_pane_for(snap.pane.pane_id)`; if `None` →
     `notify("No shadow agent running — press 'e' to launch one", severity="warning")` + return.
  3. `text = await self._capture_shadow_text(shadow_pane)`; if `text is None`
     (capture failed/timed out) → `notify("Could not read the shadow pane", severity="warning")` + return.
  4. `concerns = parse_concerns(text)`; if `not concerns` →
     `notify("No concerns detected on the shadow pane")` + return (do **not** open modal).
  5. `self.push_screen(ConcernPickerModal(concerns, narrow=True), callback=self._on_concerns_picked)`.
- `_on_concerns_picked(selected: list[Concern] | None)`: if falsy (None/empty) →
  return (no clipboard write). Else
  `payload = build_clipboard_payload(selected)`, `self.copy_to_clipboard(payload)`,
  `self.notify("Concerns copied to clipboard.")`.

### 5. Auto-offer (immediate, de-duped on the parsed block) in the refresh tick

Per project memory the offer must fire **immediately** when a fresh concern block
is detected, with the hotkey as the backstop — not the only trigger. In
`_refresh_data` (after the existing capture work), when a shadow pane exists:
- `await` resolve (`_find_shadow_pane_for`) + `await _capture_shadow_text` under
  the shared timeout; on any failure **skip this tick silently** and do **not**
  touch the de-dup hash (per the discipline above).
- **Strict trigger (concern 2):** gate on `has_concern_block(text)` — the parser's
  strict predicate (requires a *closing* fence + ≥1 concern). Do **not** trigger on
  `parse_concerns` alone: it is intentionally forgiving (EOF-tolerant) and would
  fire mid-stream while the shadow is still emitting an unclosed block. Only when
  `has_concern_block` is true do we proceed. (The hotkey path in §4 keeps forgiving
  `parse_concerns` — that's an explicit user request to look *now*, matching the
  parser's documented split: strict for the auto-offer, forgiving for the action.)
- **De-dupe on the parsed concerns, not the raw pane (concern 2).** After the
  strict trigger passes, `concerns = parse_concerns(text)` and keep
  `self._last_concern_block_hash: dict[str, str]` keyed by shadow `pane_id`. Hash
  the **canonical parsed form** — e.g. `build_clipboard_payload(concerns)` or a
  stable digest of the `(priority, region, body)` tuples — so unrelated pane churn
  (new output, prompt text, cursor movement) around an unchanged block does **not**
  re-fire the hint. Only when the parsed-block hash differs from the last seen for
  this pane, emit a one-line non-gating hint
  (`notify("Shadow raised concerns — press 'c' to pick", severity="information")`)
  and store the new hash.
- Guard cost: only runs when a shadow pane is resolved (no shadow ⇒ no extra
  capture/query). If continuous detection still proves noisy in live use (tracked
  by the t1037_5 manual-verification sibling), the documented fallback is lazy
  hotkey-only — leave a short `# NOTE:` to that effect. Implement the immediate
  offer now.

### 6. Tests

Tests must prove the **integration** holds, not just the mocked control flow
(concern 4). Three layers:

**(a) `tests/test_minimonitor_concern_action.py` (new)** — action/auto-offer logic,
mock-based, following `tests/test_multi_session_minimonitor.sh`'s pattern
(`MiniMonitorApp.__new__`, `FakeMon`, `SimpleNamespace` snapshots, stub
`notify`/`push_screen`; drive async actions via `asyncio.run`):
- **Pure matcher:** `match_shadow_pane` returns the bound shadow pane for a given
  followed pane; `None` when no target matches and when the target field is empty;
  with **multiple** matching panes returns the newest (largest `%N`).
- **Happy path:** stub `_capture_shadow_text` (async) to return a known concern
  block + a `FakeMon` whose async query returns list-panes output binding a shadow
  to the followed pane; spy `push_screen`. Drive `action_pick_concerns`: assert the
  modal is pushed with the parsed concerns. Invoke the captured callback with a
  selected subset + a `copy_to_clipboard` spy → assert the payload (preamble +
  selected items) reaches the spy.
- **No side effect before confirm:** clipboard spy untouched until the callback fires.
- **No shadow pane / empty parse:** notifies, pushes nothing, writes nothing.
- **Failure degrades safely (concern 1):** make `_capture_shadow_text` return
  `None` (simulated timeout/nonzero) → hotkey path notifies a warning, pushes
  nothing, does not raise; auto-offer path skips silently (no notify) and leaves
  the de-dup hash unchanged.
- **Duplicate-shadow guard (concern 3):** with a `FakeMon` whose **sync** query
  reports an existing shadow for the followed pane, `action_launch_shadow` (sync)
  refuses via `_find_shadow_pane_for_sync` (notifies, spawns nothing — spy the
  launch call). Asserts the guard uses the sync reader (no `await` trap).
- **Auto-offer strict trigger (concern 2):** an **unclosed** block (opening fence,
  no closing fence) ⇒ `has_concern_block` false ⇒ **no** hint, hash untouched;
  the same block once **closed** ⇒ one hint.
- **Auto-offer de-dup on parsed block (concern 2):** a closed block with
  *different surrounding pane text* across two ticks ⇒ exactly **one** hint;
  changing a concern body ⇒ a second hint.

**(b) `tests/test_shadow_capture_join.sh` (new, skip-capable)** — proves the real
script path and that `-J` was actually added (concern 4), per the
"test the real entry point" guidance:
- If `tmux` is unavailable, print `SKIP` and exit 0.
- Start a throwaway tmux session in a narrow pane, print a single logical line
  longer than the pane width (forcing a soft wrap), then capture it via
  `./.aitask-scripts/aitask_shadow_capture.sh <pane>` and assert the long line
  comes back **un-split** (no mid-word break) — i.e. `-J` joined it. A capture
  without `-J` would fail this. Tear down the session.

**(c) Static + smoke (cheap regression guards):**
- `bash tests/test_no_raw_tmux.sh` still passes.
- `shellcheck .aitask-scripts/aitask_shadow_capture.sh`.
- Import smoke of `monitor.minimonitor_app`.

## Risk

### Code-health risk: medium
- Auto-offer + lookup hook the ~3s `_refresh_data` hot path with per-tick shadow
  capture/query (subprocess) when a shadow exists — **UI-hang risk** if tmux
  stalls · severity: high if unhandled · → mitigation: in-task — all tmux
  touchpoints are async with a hard `_SHADOW_CAPTURE_TIMEOUT`; failures degrade
  (warn on hotkey, silent-skip on auto-offer); guarded to fire only when a shadow
  is resolved; explicitly tested (failure-degrades-safely test). Residual: low.
- Auto-offer hint spam from hashing raw pane text · severity: medium · →
  mitigation: in-task — de-dup hashes the **parsed concern block**, not the whole
  capture; tested (de-dup-on-parsed-block test). Residual: low.
- Multiple shadows bound to one followed pane → stale/ambiguous match · severity:
  medium · → mitigation: in-task — duplicate-launch guard in `action_launch_shadow`
  (root cause) + newest-wins tie-break in the matcher (defense-in-depth); both
  tested. Residual: low.
- `-J` added to the shared `aitask_shadow_capture.sh` (other consumer: the shadow
  skill) · severity: low · → mitigation: in-task (`-J` only joins soft-wrap,
  benign for prose; `-e`-omission preserved; behavioral `-J` test).

### Goal-achievement risk: low
- All dependencies (parser, modal, `copy_to_clipboard`, `tmux_run`,
  `_find_own_agent_snapshot`, `@aitask_shadow_target` set by `action_launch_shadow`)
  verified present in current code; reverse-lookup mechanism corrected to a fresh
  query. Live end-to-end is owned by the existing t1037_5 manual-verification
  sibling · severity: low · → mitigation: none needed (covered by t1037_5).

No separate before/after mitigation task is warranted — the listed risks are
handled in-task (async/timeout discipline, guards, the integration + behavioral
`-J` + failure-degradation tests) and by the already-existing t1037_5 sibling.

## Verification

- `python3 -c "import sys; sys.path.insert(0,'.aitask-scripts'); import monitor.minimonitor_app"` imports cleanly.
- `python3 tests/test_minimonitor_concern_action.py` passes (incl. failure-degrades,
  duplicate-guard, and parsed-block de-dup cases).
- `bash tests/test_shadow_capture_join.sh` passes (or `SKIP` where tmux absent) —
  proves `-J` is live.
- `bash tests/test_no_raw_tmux.sh` still passes (gateway compliance).
- `shellcheck .aitask-scripts/aitask_shadow_capture.sh`.
- Live e2e (shadow emits a real block → `c` opens modal → confirm copies payload;
  auto-offer fires once per new block; tmux-stall does not hang the UI) → deferred
  to the t1037_5 manual-verification sibling.

## Final Implementation Notes

- **Actual work done:** All of §1–§6 landed as planned.
  - `aitask_shadow_capture.sh`: added `-J` to the `ait_tmux capture-pane` call
    (option (a)) + comment. Verified live: a 62-char line in a 20-col pane comes
    back contiguous through the script.
  - `monitor_core.py`: added public `tmux_run_async` (thin alias of the internal
    `_tmux_async`) so the async picker/auto-offer paths get a gateway-routed,
    event-loop-safe tmux call symmetric with the sync `tmux_run`.
  - `minimonitor_app.py`: module-level pure `match_shadow_pane` (+ `_pane_id_sort_key`
    newest-wins tie-break); `_shadow_query_args` shared by `_find_shadow_pane_for_sync`
    (guard) and async `_find_shadow_pane_for` (picker/auto-offer); async
    `_capture_shadow_text` (subprocess of the shadow capture script under
    `asyncio.wait_for(_SHADOW_CAPTURE_TIMEOUT=3s)`, → `None` on any failure); `c`
    binding + async `action_pick_concerns` + `_on_concerns_picked`; duplicate-shadow
    guard at the top of `action_launch_shadow`; strict, parsed-block-de-duped
    `_maybe_offer_concerns` wired at the end of `_refresh_data`; `c:concerns`
    key-hint line.
- **Deviations from plan:**
  - **Reverse-lookup correction (was wrong in the task AC):** the followed agent's
    shadow is resolved by a **fresh `list-panes -a` gateway query**, not a snapshot
    scan — `monitor_core._parse_list_panes` filters shadow panes out of
    `self._snapshots` and never stores `@aitask_shadow_target`. The pure matcher
    keys on that target value.
  - **Test file:** instead of a new `tests/test_shadow_capture_join.sh`, the live
    `-J` behavioral test was **added to the existing `tests/test_shadow_capture.sh`**
    (cohesion — that is THE shadow-capture test). The Python action/auto-offer
    tests live in the new `tests/test_minimonitor_concern_action.py`.
  - **De-dup field name:** stored as `self._last_concern_block_payload`
    (the canonical clipboard payload string, exact-compared) rather than a separate
    hash — simpler and exact; no `hashlib`.
- **Issues encountered:** the live `-J` test initially captured an empty pane —
  a race (the pane exists before its `printf` emits output). Fixed by polling the
  capture until non-empty. Test runs on an isolated `-L ait_jtest_$$` socket and
  skips when tmux is unavailable.
- **Key decisions:** capture path = option (a) (reuse `aitask_shadow_capture.sh`
  with `-J`) per the parent constraint + `shadow_concern_format.md`; auto-offer
  uses strict `has_concern_block` as the trigger and forgiving `parse_concerns`
  for the hotkey, matching the parser's documented split; `action_launch_shadow`
  stays sync (uses the sync reader) — no async conversion of an existing action.
- **Upstream defects identified:** None.
- **Notes for sibling tasks (t1037_5 manual verification):** live e2e is owed here
  — launch `ait minimonitor` beside an agent, `e` to spawn a shadow, have it emit a
  concern block, then verify (a) the auto-offer hint fires once per new block, (b)
  `c` opens the picker, (c) confirm copies the preamble+selected concerns to the
  clipboard, and (d) a stalled/again-pressed path never hangs the UI. The
  duplicate-shadow guard means a second `e` on the same agent is refused.

See parent t1037 and **Step 9 (Post-Implementation)** for archival/merge.
