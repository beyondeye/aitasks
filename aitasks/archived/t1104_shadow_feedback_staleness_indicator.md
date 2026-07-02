---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [shadow, aitask_monitormini, tmux]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-01 14:23
updated_at: 2026-07-02 13:36
completed_at: 2026-07-02 13:36
boardidx: 40
---

## Problem

The shadow companion agent (`/aitask-shadow`) gives advisory feedback on a *followed* coding agent by capturing that agent's tmux pane on demand (`aitask_shadow_capture.sh`) and reasoning about the snapshot. Nothing records **which followed-state a given piece of shadow feedback was about**. When the user follows many parallel agents, the followed agent races ahead and the shadow's advice silently becomes stale (about a past state) with **no visible signal** — the user can act on advice that no longer matches what the followed agent is now doing. This happens a lot in parallel-agent workflows.

We want a mechanism — either in how the shadow's output is written, or as new logic in minimonitor — to track whether the shadow's current output is **MORE recent** (current: reflects the followed agent's latest output) or **LESS recent** (stale: the followed agent has already moved past the state the shadow commented on), and surface that to the user.

## What already exists (reuse these — do NOT reinvent)

- **Followed-pane change tracking:** `monitor_core.py` `_finalize_capture()` (`~monitor_core.py:1136-1176`) already maintains `self._last_content[pane_id]` and `self._last_change_time[pane_id]`, updated by plain string-equality compare (ANSI-stripped under `COMPARE_MODE_STRIPPED`, the default). So minimonitor already knows *when the followed agent last produced output*.
- **Shadow<->followed binding:** the pane-scoped tmux user-option `@aitask_shadow_target` (`SHADOW_TARGET_OPTION`, `monitor_core.py:186`), set on the shadow pane at launch (`minimonitor_app.py:1112`), and read every refresh via `_LIST_PANES_FORMAT` (`monitor_core.py:948`) and the reverse-lookup helpers (`_find_shadow_pane_for` / `_sync`).
- **Per-tick shadow capture loop:** `_maybe_offer_concerns()` (`minimonitor_app.py:1241`) already captures the shadow pane each refresh via `_capture_shadow_text()` and de-dups on the parsed concern payload. This is the natural hook for a staleness check.
- **Shadow capture cleaning:** `aitask_shadow_capture.sh` (`shadow_clean` / `shadow_capture_pane`) is the shared normalization path (ANSI-strip, trailing-blank trim, `-J` wrap-join).

## Proposed mechanism (content-signature anchor — recommended)

1. **Anchor stamp:** when the shadow captures the *followed* pane, it stamps a hash/signature of the **normalized** captured content onto its **own** pane as a new pane-option, e.g. `@aitask_shadow_analyzed_sig` (mirrors the `@aitask_shadow_target` pattern). Set it on `$TMUX_PANE` after each capture. This must fire only when the shadow captures its followed pane — NOT when minimonitor captures the shadow pane (distinguish the call sites; a dedicated `--stamp-freshness`-style flag or a separate code path, so minimonitor's `_capture_shadow_text` never mis-stamps).
2. **Compare:** minimonitor re-hashes the followed pane's current normalized content (it already holds `_last_content[followed]`) and compares against the shadow pane's stamped `@aitask_shadow_analyzed_sig`. Match => shadow feedback is **current**; mismatch => followed agent moved on => shadow feedback is **stale**.
3. **Normalization parity:** the hash must be computed over the *same* normalized text on both sides (shadow's `shadow_clean` vs monitor's `_strip_ansi` + compare-mode). Either route both through `aitask_shadow_capture.sh` or factor a shared normalize+hash helper so the two sides cannot drift (a divergence would produce false "stale"). Prefer hashing the ANSI-stripped content so cosmetic redraws (spinners) don't produce false staleness.
4. **Display:** surface a freshness badge on the followed-agent row and/or in the concern auto-offer / concern-picker path — e.g. `✓ current` vs `⧗ stale (agent moved on)`. Wire into the existing refresh tick (`_maybe_offer_concerns` / list rendering). Consider suppressing/annotating the concern auto-offer when the block is stale.

### Alternative considered (timestamp anchor — weaker)

Shadow stamps a wall-clock capture time; minimonitor compares against the followed pane's `_last_change_time`. Rejected as the primary approach: cross-process monotonic clocks aren't comparable (must use wall-clock, with skew risk), and any cosmetic redraw bumps activity => false "stale". The content-signature approach is redraw-robust and reuses the existing compare primitive. (Revisit only if signature parity proves impractical.)

## Blast radius / cautions

- New pane-option must be cleaned up with the shadow pane like `@aitask_shadow_target` (no leak into non-shadow panes; `is_shadow_target` semantics unaffected).
- Keep the shadow **advisory-only** and the check **best-effort** — a capture/hash failure must degrade silently (never block the UI or the concern flow), matching the existing `_SHADOW_CAPTURE_TIMEOUT` / silent-skip conventions.
- Signature stamping added to `aitask_shadow_capture.sh` must not change its default stdout contract (existing callers, incl. minimonitor's `_capture_shadow_text`, must see identical output); gate it behind an explicit flag. All tmux access stays through `lib/tmux_exec.sh` (`tests/test_no_raw_tmux.sh`).
- Update `aidocs/framework/shadow_agent.md` (and, if the concern surface changes, `shadow_concern_format.md`) to document the new pane-option and freshness semantics.

## Acceptance criteria

- The shadow records, per capture, a signature of the followed-pane state it analyzed, stored where minimonitor can read it per refresh.
- Minimonitor computes and displays whether the shadow's latest feedback is current vs stale relative to the followed agent's latest output.
- Signature normalization is shared/parity-guaranteed across the shadow and monitor sides (a unit test pins that identical followed content on both paths yields an equal signature, and a changed followed state yields a different one).
- Freshness check is best-effort: capture/hash failures degrade silently.
- `aitask_shadow_capture.sh` default output contract is unchanged (stamping is opt-in / isolated).
- Docs updated (`shadow_agent.md`).

## Key files

- `.aitask-scripts/aitask_shadow_capture.sh` — add opt-in signature stamping.
- `.aitask-scripts/monitor/monitor_core.py` — new pane-option constant + signature read/compare; reuse `_last_content` / `_strip_ansi`.
- `.aitask-scripts/monitor/minimonitor_app.py` — compute + display freshness in the refresh tick / concern surfaces.
- `.aitask-scripts/monitor/concern_parser.py` — only if freshness is threaded through the concern block.
- `aidocs/framework/shadow_agent.md` (+ `shadow_concern_format.md` if relevant) — docs.

## Cross-agent note

Per repo convention, skill/command source-of-truth is the Claude Code tree; this task is mostly shell + Python (minimonitor/capture), so no per-agent skill port is expected. If any change touches the `/aitask-shadow` SKILL surface, suggest follow-ups for Codex/OpenCode wrappers.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-01T11:57:14Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-02T10:27:41Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-02T10:36:52Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:f660d4f5bdc3e233

> **✅ gate:risk_evaluated** run=2026-07-02T10:36:52Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1104/risk_evaluated_2026-07-02T10:36:52Z-risk_evaluated-a1.log`
