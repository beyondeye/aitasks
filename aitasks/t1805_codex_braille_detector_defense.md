---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Postponed
labels: [monitor, codex, shadow, review_loop]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 1797
followup_kind: risk_mitigation
created_at: 2026-09-14 16:49
updated_at: 2026-09-14 17:19
---

## Origin

Risk-mitigation ("after") follow-up for t1797, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — silent tui.animations rename / hand-launched Codex panes keep the starfield

- Codex silently ignores unknown `-c` keys, so a future rename of
  `tui.animations` would bring the bug back with no error. Codex panes
  launched outside the framework stay affected. · severity: medium
  · → mitigation: codex_braille_detector_defense

## Goal

t1797 disabled the Codex composer "starfield" at launch:
`CODEX_TUI_OVERRIDES=(-c tui.animations=false)` in `aitask_codeagent.sh`, plus
`[tui] animations = false` in the Codex seed. This follow-up adds a
**Codex-scoped detector-side defense**, so the monitor and the review loop stay
correct when the flag does not apply. That happens for a Codex pane started by
hand outside a trusted project, for a project that explicitly sets
`animations = true`, or after a Codex release renames or removes the key
(unknown `-c tui.*` keys are ignored silently).

Scope — only when the pane's resolved agent key is `codex`:
- `monitor_core.classify_content`: drop the starfield glyphs from the compare
  value.
- `review_loop._codex_state`: drop them from the composer line before
  `_CODEX_COMPOSER_RE` and the dim-strip test. Today a dot directly after `›`
  breaks the regex, and trailing non-dim dots read as typed text.
- `minimonitor_app`: compare Braille-normalised tails for a Codex shadow, both
  in the raw-tail hash streak (`_loop_shadow_hash_streak`) and in
  `_fire_shadow_recheck`'s fresh-equals-tick byte check.

Upstream gating (`codex-rs/tui/src/bottom_pane/chat_composer/sparkle.rs` at
`rust-v0.154.0`, `enabled_foreground`): the stars draw only when all of these
hold: whimsy, animations, a model matching `\bastra\b`, truecolor, and known
terminal default colours. The dots come from
`DOTS = ["⠁","⠂","⠄","⠈","⠐","⠠","⡀","⢀"]`. Consider normalising only that
8-glyph set rather than the whole U+2800–U+28FF block.

It must ship with negative controls:
- a real visible-text change in a Codex pane still resets idle;
- a Braille spinner in a NON-Codex pane, or with an unresolved agent key,
  still counts as activity;
- the Codex working line (`• Working`) is unaffected.

The characterization tests t1797 pinned are expected to flip. Rewrite each into
its positive form:
- `test_review_loop.Codex0154ComposerTests.test_starfield_ticks_differ_after_strip`
- `test_idle_compare_modes._check_codex_starfield_never_reaches_idle`
- `test_minimonitor_concern_smoke.test_codex_starfield_shadow_never_fires`

The live-captured fixtures are `tests/review_loop_fixtures.py`
`CODEX_0154_STARFIELD_RAW_1/_2` and `CODEX_0154_NOANIM_AT_REST_RAW` /
`_TICK2_RAW`.
