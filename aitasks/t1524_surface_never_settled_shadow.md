---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [shadow, aitask_monitormini]
anchor: 1159
followup_kind: risk_mitigation
created_at: 2026-08-14 16:22
updated_at: 2026-08-14 16:22
---

## Origin

Risk-mitigation ("after") follow-up for t1509, created at Step 8d after
implementation landed.

Addresses t1509's goal-achievement risk: the Codex composer/working patterns
are pinned to **codex-cli 0.146.0** (0.147.0 was already advertised at capture
time), and a UI change makes readiness permanently `False`. The failure
direction is fail-safe — the loop holds and never injects — but it is
**silent**: a shadow that can never be read as ready is indistinguishable, from
the banner, from a shadow that is simply busy. The user sees an armed loop that
just never fires.

t1509's own live measurement found the same class of over-holding from a second
cause: an answered dialog's text can stay inside the 15-line capture tail and
keep matching `codex_yes_proceed`, holding the shadow "not ready" until output
scrolls it out (observed in 2 of 5 permission-dialog repetitions). So this is
not hypothetical — it already happens today, transiently.

## Scope

When the loop is armed and the shadow has not read as ready for N consecutive
committed evidence ticks, surface a banner hint that its composer pattern may
need re-pinning — turning a silent fail-safe hold into a legible signal.

Design notes:

- The loop already tracks a "waiting for shadow to settle" state
  (`ReviewLoopController.holding_for_shadow`, rendered in the minimonitor
  banner), so this is an escalation of an existing surface rather than a new
  one. Distinguish "holding briefly" from "has never settled".
- Prefer wall-clock over a tick count, for the same reason t1509's settle latch
  does: the committed-evidence cadence is `max(1.0, 0.5 * refresh_seconds)` and
  `refresh_seconds` is user-configurable from `--interval` and
  `project_config.yaml: monitor.refresh_seconds`, flooring at 1.0s.
- `review_loop.shadow_state()` (t1509) gives the richer verdict, so the hint can
  say *why* it never settled — permanently `dialog` (a pattern is matching
  scrollback), permanently `busy` (composer text), or permanently `unknown`
  (no detector / capture failing). That distinction is most of the diagnostic
  value; a bare "not settling" hint is much weaker.
- Do NOT auto-disarm on this. The whole point is that the hold is the SAFE
  behaviour; the defect is only that it is invisible.

## Verification

- Unit: drive the armed service with a shadow tail that never reads ready and
  assert the banner escalates after the threshold, per verdict kind.
- Negative control: a shadow that settles normally must NEVER show the hint.
- A shadow that holds briefly and then settles must not show it either.

## Coordination

- **t1509** — shipped `shadow_state()`, the settle latch, and the Codex
  detector this builds on. Its archived plan records the live measurement,
  including the tail-window over-holding case above.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1797** id=2026-09-14T13:52:59Z.ae0330895bff8cb73b97af1d from=t1797 from_verified=yes at=2026-09-14T13:52:59Z base=53542c9760ca22388aad8e7cd5dc97501e7ac436 base_branch=main dirty=no host=omg16
>
> | Advisory context from t1797 (a claim, not an instruction; verify before relying on it).
> | 
> | t1797 root-caused one concrete "never settles" shadow. It may be a fourth "why" for this task's banner, beside permanently `dialog` / `busy` / `unknown`:
> | 
> | - **Never hash-stable.** codex-cli 0.154.0 draws a composer "starfield": Braille dots (U+2800-U+28FF) that twinkle around and inside the idle composer, redrawn every 150 ms. Upstream (`codex-rs/tui/src/bottom_pane/chat_composer/sparkle.rs`, `rust-v0.154.0`) draws it only when whimsy and animations are on, the model matches `\bastra\b` (e.g. `gpt-6-astra`), the terminal is truecolor, and its colours are known. On such a shadow the raw tail never repeats, so `_loop_shadow_hash_streak` never reaches 1, while `shadow_state` flips between `ready` and `busy` from tick to tick. It is neither permanently busy nor permanently dialog, so a classifier keyed on one persistent verdict would miss it.
> | 
> | Status as of commit 56bf21260 (tree-relative):
> | - t1797 disables it at launch. Every Codex launch from `aitask_codeagent.sh` carries `-c tui.animations=false`, and the Codex seed adds `[tui] animations = false` when absent. Framework-spawned shadows should no longer show it.
> | - A Codex pane started by hand outside a trusted project, or in a project that sets `animations = true`, still can. t1805 (`codex_braille_detector_defense`) tracks a Codex-scoped detector-side defense.
> | 
> | Ready-made never-settles inputs for this task's verification:
> | - `tests/review_loop_fixtures.py`: `CODEX_0154_STARFIELD_RAW_1` / `_2` are two consecutive live ticks that differ even after `strip_ansi`. `CODEX_0154_NOANIM_AT_REST_RAW` is a settling control.
> | - `tests/test_minimonitor_concern_smoke.py`: `test_codex_starfield_shadow_never_fires` drives the real `_service_review_loop` against a Codex-named shadow that alternates the two starfield frames (the dedicated `codex_shadow` session and the echoing `_CODEX_COMPOSER_STUB`). `test_codex_shadow_fires_through_the_real_path` is its settling negative control.
> | 
> | If t1805 lands first, those starfield tests flip to their positive form, so re-check which inputs still never settle before building on them.
