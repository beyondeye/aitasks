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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1944** id=2026-10-11T16:18:19Z.cf13adf9c0bd9172dab2e809 from=t1944 from_verified=yes at=2026-10-11T16:18:19Z base=828bc0ad5e1bce1d810f992760195746af706ef1 base_branch=main dirty=yes host=omg16
>
> | t1944 (commit 828bc0ad5) changed the launch-side starfield key your body assumes.
> | 
> | - Framework Codex launches no longer pass `-c tui.animations=false`. `tui.animations` is Codex's master switch; off, codex-cli 0.160 stops repainting the `Working (Ns …)` counter, so working panes read idle. Launches now pass `-c tui.animations=true -c tui.whimsy=false -c tui.effects.starfield=false` (CODEX_TUI_OVERRIDES in lib/agent_string.sh). The seed / .codex/config.toml carry `[tui] whimsy = false` + `[tui.effects] starfield = false`.
> | - Measured: 0.154.0 honours only `tui.whimsy` (it silently ignores `tui.effects.*`); 0.160.1 honours both (`whimsy` is an alias of `effects.starfield`, canonical wins). The 0.160 starfield also stops by itself after a 15 s IDLE_TIMEOUT once visible; 0.154's is perpetual.
> | - Detector-relevant: a live 0.160.1 starfield capture (`tests/review_loop_fixtures.py` CODEX_0160_STARFIELD_RAW_1/_2) classifies as SHADOW_DIALOG in `review_loop._codex_state` (the `›⠁Ask Codex…` composer line misses the composer pattern), whereas the 0.154 starfield fixtures classify BUSY. The tests only assert "not READY" for it; your detector-side defence would own pinning that.
> | - A pane with animations ON now ticks its elapsed counter every second while working (visible text change), so a Braille-stripping defence must not also strip/normalise that counter.
