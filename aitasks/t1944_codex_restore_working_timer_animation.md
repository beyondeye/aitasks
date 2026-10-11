---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [monitor, codex, codeagent, ait_setup]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1797
created_at: 2026-10-11 14:34
updated_at: 2026-10-11 14:36
---

## Symptom

In a framework-launched Codex pane, the `Working (Ns • esc to interrupt)` row
shows no animation, and the elapsed counter updates only every few seconds, at
an irregular interval. `ait monitor` / `ait minimonitor` flag a pane idle after
5 s with no content change, so they often read a working Codex agent as
**idle**.

## Root cause (traced in codex-cli 0.160.0 source, tag `rust-v0.160.0`)

Codex did not remove the animations upstream. **Our own t1797 override turns them
off:** `CODEX_TUI_OVERRIDES=(-c tui.animations=false -c tui.alternate_screen=never)`
in `.aitask-scripts/lib/agent_string.sh`, plus `[tui] animations = false` in
`seed/codex_config.seed.toml` and this repo's `.codex/config.toml`.

`codex-rs/tui/src/status_indicator_widget.rs`, `impl Renderable for StatusIndicator`:

- `render()` calls `frame_requester.schedule_frame_in(..)` only when
  `row.animations_enabled || timer.display_started_at.is_some()`. The interval
  is 32 ms when animations (and progress/shimmer) are on, otherwise 1000 ms.
- With animations **off** and no `display_started_at` (the normal turn), it
  schedules **no frame at all**. The elapsed counter is recomputed only when
  something unrelated triggers a redraw, such as streamed output or other
  widgets. That explains the irregular "every ~5 s" update.
- `bottom_pane/mod.rs` (~l.2202) hands the status row
  `animations_enabled: self.animations_enabled && self.effects.shimmer`. Steady
  1 s ticks therefore need **`tui.animations` AND `tui.effects.shimmer`** on.
- 0.154.0 had the same no-frame branch, so the bug started with t1797
  (2026-09-14). It is not a Codex regression.

With animations on, the activity bullet `•` is a colour shimmer in truecolor
terminals, which `strip_ansi` absorbs. It blinks `•`/`◦` only without truecolor,
which is legitimate activity. The `(Ns …)` counter therefore becomes a steady
1 s visible change while the agent works: exactly what idle detection needs.

## Finer-grained knob that exists now

`codex-rs/config/src/tui_effects.rs` (0.160.0) defines
`TuiEffects { starfield, shimmer, welcome, effort, progress, title }`. Each
defaults to true and sits under the `tui.animations` master switch.
`codex-rs/config/src/key_aliases.rs` maps the legacy `tui.whimsy` to
`tui.effects.starfield`. The t1797 problem, the Braille composer starfield
(`bottom_pane/chat_composer/sparkle.rs`, gated on
`animations && effects.starfield && model ~ astra`), needs only
`effects.starfield=false`.

The t1797 rationale comment in `agent_string.sh` says "`tui.animations` is
preferred over `tui.whimsy` because it is narrower". **That is backwards:**
whimsy/starfield is the narrow switch, and animations is the master switch that
also kills the status-row frame scheduling.

## Proposed fix (planner to confirm by live measurement)

1. Change `CODEX_TUI_OVERRIDES` so framework launches keep animations on and
   disable only the starfield. Candidate:
   `-c tui.animations=true -c tui.effects.starfield=false` (+ `tui.alternate_screen=never`).
   The explicit `animations=true` matters: a `-c` outranks the already-seeded
   `[tui] animations = false` in existing projects' `.codex/config.toml`, which
   would otherwise keep the bug for framework launches.
   - Consider also `-c tui.effects.welcome=false`. The empty-state artwork
     (`empty_state_animation.rs`) animates on a fresh session with no prompt.
     Measure whether it keeps a fresh pane from ever reading idle.
   - **Older-build compatibility:** on 0.154 the starfield key was `tui.whimsy`.
     Measure whether 0.160 honours the `tui.whimsy` alias for **`-c`** overrides
     (the alias normalisation is in the config-layer merge, so it is unverified
     for the CLI layer). Measure too whether older builds silently ignore
     `tui.effects.*`. Pick one key or both on evidence. Update the comment block
     in `agent_string.sh` accordingly, including correcting the "narrower" claim.
2. Seed (`seed/codex_config.seed.toml`): replace `[tui] animations = false` with
   the starfield-only form, e.g. `[tui.effects] starfield = false`, and rewrite
   the comment. Update this repo's `.codex/config.toml` the same way.
3. `aitask_setup.sh` `merge_codex_settings` is add-only (`deep_merge` never
   overwrites). Projects already seeded by t1797 keep `animations = false`,
   which still breaks **hand-launched** Codex sessions. Decide a migration: for
   example, rewrite a framework-seeded `animations = false` (indistinguishable
   from a user-set one once serialised, which is a design point to resolve), or
   document it as a known issue. It must not clobber a deliberate user value
   without a recorded rule.
4. Tests that pin the old argv or seed and must change:
   `tests/test_codeagent.sh` (CODEX_OVERRIDE_PREFIX, 11e/11f, the
   `tui.animations` not-contains asserts), `tests/test_codeagent_resume_session.sh`,
   `tests/test_skillrun_codex.sh`, `tests/test_agent_sessions_transcripts.py`
   (~l.462), `tests/test_codex_config_tui_seed.sh`. Docstrings and comments sit
   in `tests/test_idle_compare_modes.py` (~l.126),
   `tests/test_minimonitor_concern_smoke.py` (~l.1285),
   `tests/review_loop_fixtures.py` (~l.163-170, ~l.298) and
   `tests/test_review_loop.py` (~l.604). The t1797 live fixtures
   (`CODEX_0154_NOANIM_AT_REST_RAW` / `_TICK2_RAW`) were captured with
   animations off. Decide whether a fresh 0.160 at-rest capture under the new
   overrides is needed for the review-loop shadow readiness tests.
5. Docs: `aidocs/framework/monitor_idle_and_prompt_detection.md` (the "Visible-glyph
   animation: the Codex composer starfield" section, which also states the
   wrong whimsy/animations gating), `aidocs/framework/shadow_agent.md` (~l.250),
   and `website/content/docs/installation/known-issues.md` (~l.31-34).
   Afterwards run `website/check_links.py --build`.

## Verification (live, in tmux)

On the installed codex-cli (0.160.0), with the new overrides:
- **Working:** during a multi-second turn, the captured pane's stripped text
  changes at least every ~1 s (the elapsed counter), so `ait minimonitor` never
  shows IDLE while the agent works.
- **At rest:** an idle composer is byte-stable after `strip_ansi` and reaches
  IDLE. Include a starfield-eligible model (`\bastra\b`, e.g. `gpt-6-astra`)
  to prove the starfield stays off, and a fresh no-prompt session for the
  welcome artwork.
- **Control:** the old `-c tui.animations=false` reproduces the irregular
  counter.
- Shadow review loop: a Codex shadow at rest still settles (review-loop
  readiness and `_loop_shadow_hash_streak`).

## Related

- t1797 (archived): the change that introduced the override.
- t1805 (Postponed, `codex_braille_detector_defense`): a detector-side Braille
  defence for panes the framework did not launch. It is complementary, not
  merged here. Its body assumes `tui.animations` is the key, so send it a note
  if this task changes the launch-side key.
- t1902 (archived): added `tui.alternate_screen=never` to the same array. Keep it.
