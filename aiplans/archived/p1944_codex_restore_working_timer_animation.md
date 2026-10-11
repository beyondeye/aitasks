---
Task: t1944_codex_restore_working_timer_animation.md
Base branch: main
Output branch: main
---

# t1944 — Restore the Codex working-timer tick (narrow the t1797 override to the starfield)

## Context

Framework Codex launches carry `-c tui.animations=false` (t1797). In codex-cli
0.160.x, `tui.animations` is the **master** switch: with it off,
`StatusIndicator::render` (`codex-rs/tui/src/status_indicator_widget.rs`)
schedules no frame during a normal turn. So `Working (Ns • esc to interrupt)`
repaints only when something unrelated redraws, and `ait monitor` /
`ait minimonitor` read a working Codex pane as idle after 5 s. The narrow switch
for the t1797 problem (the Braille composer starfield) is
`tui.effects.starfield`, whose legacy alias is `tui.whimsy`.

### Evidence gathered during planning (codex source at `rust-v0.160.1` = the installed build, plus live tmux probes)

Probe: a private tmux server (`-L t1944probe`) with `window-style fg/bg` and
truecolor, which t1797 found necessary for the starfield to draw. The probe
samples `capture-pane -p` every 100 ms. Both starfield positive controls drew
44–50 Braille dots, so the at-rest samples below are usable.

| Build | Overrides (+ `alternate_screen=never`) | Result |
|---|---|---|
| 0.160.1 working turn (`sleep 20`) | `animations=false` (current) | **19.9 s gap**: no capture change from 4 s to 24 s (reads IDLE) |
| 0.160.1 working turn | `animations=true` + starfield off | change every 0.92–1.03 s, counter 0s→25s |
| 0.154.0 working turn | final set | change every ≤1.03 s |
| 0.160.1 astra at rest | `animations=true` (control) | starfield, 44 dots; self-stops after its 15 s `IDLE_TIMEOUT` |
| 0.160.1 astra at rest | `+ tui.effects.starfield=false` | 1 change / 24 s, 0 dots |
| 0.160.1 astra at rest | `+ tui.whimsy=false` | 1 change / 24 s, 0 dots (the alias works for `-c`) |
| 0.154.0 astra at rest | `animations=true` (control) | 159 changes / 24 s, perpetual |
| 0.154.0 astra at rest | `+ tui.effects.starfield=false` | **still animates** (key unknown there, silently ignored) |
| 0.154.0 astra at rest | `+ tui.whimsy=false` | 1 change / 24 s, 0 dots |
| 0.160.1 after a turn, astra, final set | — | turn ends at ~24 s, then byte-stable for 21 s, 0 dots |
| 0.160.1 fresh session, final set | `welcome` on vs `welcome=false` | identical: settles within ~1 s |

- Source: `-c` pairs become the `SessionFlags` layer, merged through
  `merge_toml_values` → `normalize_key_aliases`, so `tui.whimsy` normalises to
  `tui.effects.starfield`. If both keys are in one layer, the canonical key wins
  (`or_insert`). No new startup warning appeared for either key; the three F2
  warnings were there before.
- The welcome artwork (`empty_state_animation`) is bounded by source:
  `SPIN_DURATION` is 10.8 s. Measured, it makes no idle difference, so
  `tui.effects.welcome=false` is **not** added.
- Residual limitation (document it, don't fix it): an OS reduced-motion
  preference (`system_motion.rs`, the freedesktop portal on Linux) suppresses
  everything gated on `tui.animations`, which brings the irregular counter back.

**Decision:** `CODEX_TUI_OVERRIDES=(-c tui.animations=true -c tui.whimsy=false -c tui.effects.starfield=false -c tui.alternate_screen=never)`.
- `animations=true` is explicit: it outranks the `[tui] animations = false`
  that t1797 seeded into existing projects.
- `whimsy` is what turns the starfield off on 0.154.
- `effects.starfield` is the canonical key, kept in case the alias is removed
  upstream.

## Implementation

1. **`.aitask-scripts/lib/agent_string.sh`**: set the array above. Rewrite the
   comment block:
   - `animations` is the master switch. Turning it off stops the status-row
     frame scheduling (t1944), so it stays on.
   - The starfield-only keys: `effects.starfield` (0.160+) and `whimsy` (0.154,
     and the 0.160 alias, measured).
   - 0.154 silently ignores `tui.effects.*` (measured).
   - Correct the backwards "animations is narrower" claim.
   - Note the OS reduced-motion caveat.

   The `tui.alternate_screen` bullet stays unchanged.
2. **`seed/codex_config.seed.toml`**: replace `[tui] animations = false` with
   `[tui]` `whimsy = false` plus `[tui.effects]` `starfield = false`. Rewrite
   the comment: starfield only, never `animations` (t1944), and the precedence
   of the `-c` launch overrides.
3. **`.codex/config.toml`** (this repo): the same `[tui]` / `[tui.effects]`
   replacement, with a one-line comment pointing at the seed.
4. **Migration in `aitask_setup.sh` `merge_codex_settings`** (inside the
   embedded Python, before `deep_merge`). A recorded **one-shot retirement
   rule**:

   > If the existing `[tui]` has `animations = false` and carries neither
   > `whimsy` nor `effects` (the pre-t1944 state that the t1797 seed produced),
   > drop `animations`.

   - It is one-shot by construction: the same merge then adds the seed's
     `whimsy` / `effects` keys, so the condition can never hold again. A user
     who re-adds `animations = false` afterwards keeps it.
   - It never touches `animations = true`, or a project that already has the
     new keys.
   - It prints a notice to stderr naming the removed value and how to keep it
     deliberately: re-add it to the project, or set it in `~/.codex/config.toml`.
   - It only affects hand-launched sessions. Framework launches are already
     covered by the `-c` override.
   - Document the rule in the seed comment and in the docs (steps 6–7).
5. **Tests**:
   - `tests/test_codeagent.sh`: update `CODEX_OVERRIDE_PREFIX` (11e) and the
     11f resume literal to the new four-pair argv. In the negative controls,
     keep the `tui.animations` / `tui.alternate_screen` not-contains asserts and
     add `tui.whimsy` and `tui.effects`.
   - `tests/test_codeagent_resume_session.sh`, `tests/test_skillrun_codex.sh`:
     new argv literals.
   - `tests/test_agent_sessions_transcripts.py` (~l.462): the argv example uses
     the new flags.
   - `tests/test_codex_config_tui_seed.sh`: rewrite it for t1944:
     - Group 0: the seed and the repo config carry `whimsy=false` +
       `effects.starfield=false` and no `animations`.
     - Group 1: a user `[tui] pet` survives and gains the keys.
     - Group 2: explicit `animations = true` is kept.
     - Group 3: no `[tui]` → the table is added.
     - Group 4: idempotent, with exactly one `[tui]` and one `[tui.effects]`
       header.
     - **Group 5 (new): migration.** A t1797-shaped `[tui] animations = false`
       is retired, and the notice is emitted. A `[tui] animations = false` next
       to `pet` is also retired. A config already carrying `whimsy` together
       with `animations = false` is kept: the second-merge case, which proves
       the rule is one-shot.
6. **Live fixtures** (decision: yes, capture fresh ones, because production
   now launches 0.160 with the new overrides):
   - Add `CODEX_0160_ANIM_AT_REST_RAW` / `_TICK2_RAW` to
     `tests/review_loop_fixtures.py`: the astra composer after one short turn,
     two ticks 2 s apart.
   - Add `CODEX_0160_ANIM_WORKING_RAW_1` / `_2`: two ticks ~1.1 s apart during
     a `sleep` turn.
   - Capture them with the same probe setup at 120x40, using the exact
     `capture-pane -p -e -S -15` call that `capture_raw_tail` makes, and the
     `CODEX_TUI_OVERRIDES` argv order. Document them in the module docstring.
   - Tests:
     - `test_review_loop.py`: a new `Codex0160AnimatedComposerTests`. At rest is
       `SHADOW_READY` and byte-identical raw with 0 Braille. Working is not
       ready, and the ticks differ after `strip_ansi`. Add both pairs to
       `test_every_existing_codex_fixture_keeps_its_verdict`.
     - `test_idle_compare_modes.py`: at rest reaches idle, and the working
       ticks do not.
     - `test_minimonitor_concern_smoke.py`: the real-path shadow-fires case
       paints the new 0160 at-rest fixture.
   - Keep the `CODEX_0154_*` fixtures and their starfield characterization
     tests, but correct their docstrings: they were captured with the t1797
     override, and the 0154 at-rest fixture is no longer what framework
     launches carry. Fix the docstrings in `test_review_loop.py` (~l.604) and
     `test_idle_compare_modes.py` (header plus ~l.126).
   - If a 0.160 fixture does **not** classify as `SHADOW_READY`, that is a real
     production finding. Stop and raise it rather than adjusting the parser
     silently.
7. **Docs**:
   - `aidocs/framework/monitor_idle_and_prompt_detection.md`, "Visible-glyph
     animation":
     - fix the gating (`animations` && `effects.starfield`/`whimsy`, astra,
       truecolor, known colours; the 0.160 starfield self-stops after 15 s);
     - the launch-side answer is now the starfield keys;
     - a new short subsection, "Status-row tick needs `tui.animations`", with
       the measurement;
     - the setup default plus the one-shot retirement rule;
     - the reduced-motion caveat;
     - update "unknown keys" to the 0.154 measurement.
   - `website/content/docs/installation/known-issues.md` ("Composer animation
     and idle detection"): rewrite the bullets and the by-hand advice
     (`-c tui.whimsy=false -c tui.effects.starfield=false`). Run
     `cd website && python3 check_links.py --build`.
   - `.aitask-scripts/monitor/monitor_core.py` compare-mode comment: say "the
     starfield is disabled at launch (starfield keys only — t1944)".
   - `aidocs/framework/shadow_agent.md` does not mention animations, so it
     needs no change.
8. **Cross-task note**: send t1805 a note with `./ait note 1805 --from 1944`.
   Its body assumes `tui.animations` is the launch-side key. The key is now
   `tui.whimsy` + `tui.effects.starfield`, and `animations` stays on.
9. **Step 9 (Post-Implementation)**: the task-workflow commit, archival, and
   the `risk_evaluated` gate.

## Verification

- `bash tests/test_codeagent.sh`, `bash tests/test_codeagent_resume_session.sh`,
  `bash tests/test_skillrun_codex.sh`, `bash tests/test_codex_config_tui_seed.sh`.
- `python3 tests/test_idle_compare_modes.py`,
  `bash tests/run_all_python_tests.sh --test-dir` covering review_loop /
  minimonitor smoke / agent_sessions_transcripts (or the whole suite; read the
  final verdict line only).
- `shellcheck .aitask-scripts/lib/agent_string.sh .aitask-scripts/aitask_setup.sh`.
- Live, after the edit:
  - `ait codeagent --agent-string codex/gpt5_5 --dry-run invoke raw` shows the
    new argv.
  - A probe launch with that exact argv gives a working turn with ≤1.1 s
    change gaps.
  - **A hand launch in this repo with no `-c`** (only the updated
    `.codex/config.toml`), `-m gpt-6-astra`: 0 Braille at rest and a 1 s
    counter while working. This proves the project layer works.
- `cd website && python3 check_links.py --build`.

## Risk

### Code-health risk: low
- Setup migration deletes a config value it cannot prove the framework wrote; a project that deliberately set `[tui] animations = false` before t1944 loses it once (announced, re-addable, and then kept). · severity: low · → mitigation: none
- Argv change touches every Codex launch path; covered by the launcher argv tests and a live dry-run + probe. · severity: low · → mitigation: none

### Goal-achievement risk: low
- An OS reduced-motion preference re-suppresses the status tick regardless of our overrides (documented residual). · severity: low · → mitigation: none
- A future Codex release could remove the `whimsy` alias or rename `effects.starfield`; both keys are passed so one rename alone does not regress, and unknown keys are ignored rather than fatal. · severity: low · → mitigation: none

## Post-Review Changes

### Change Request 1 (2026-10-11 17:20)
- **Requested by user:** (1) the seed's `effects.starfield = false` silently cancels a project's `whimsy = true` on 0.160 (canonical key wins), so preserve the effective preference across both spellings and test effective precedence; (2) the retirement guard deletes `animations = false` even when the seed installs no marker, so a re-added value is removed again every run; (3) the working fixtures also differed in a background-terminal line, and the at-rest pair (captured after a typed prompt, past 15 s) cannot show the starfield keys work; (4) the one-shot preservation case had both markers, so neither guard was tested alone.
- **Changes made:** (1) `merge_codex_settings` now mirrors a project-stated starfield preference (canonical first, else `whimsy`) into the seed's missing spelling; Group 2 asserts effective 0.160/0.154 values for `whimsy=true`, `effects.starfield=true` and an opt-out. (2) Retirement additionally requires the seed to carry `whimsy` or `effects`; a marker-less seed retires nothing on two consecutive merges. (3) Re-captured: `CODEX_0160_FRESH_IDLE_*` (fresh session, 1.8–3.3 s after launch, inside the starfield window) with a simultaneous starfield-on control `CODEX_0160_STARFIELD_RAW_*` (21→34 dots); working pair re-captured until the counter (6s→7s) was the only stripped difference, plus a frozen-counter control that must read idle. The after-turn pair is kept as readiness-only evidence. (4) Separate whimsy-only and effects-only (`welcome=false`) one-shot cases. Each guard was mutation-tested in isolation (mirror / seed-marker / whimsy / effects) with guard-specific failures. Docs and seed comment updated.
- **Files affected:** `.aitask-scripts/aitask_setup.sh`, `tests/test_codex_config_tui_seed.sh`, `tests/review_loop_fixtures.py`, `tests/test_review_loop.py`, `tests/test_idle_compare_modes.py`, `aidocs/framework/monitor_idle_and_prompt_detection.md`, `website/content/docs/installation/known-issues.md`, `seed/codex_config.seed.toml`.

### Change Request 2 (2026-10-11 17:35)
- **Requested by user:** the website stated the retirement condition more broadly than implemented (an `[tui.effects]` table with only `welcome`, or a marker-less seed, also prevent removal).
- **Changes made:** rewrote the known-issues bullet with the exact conditions (`animations = false`, no `whimsy`, no `[tui.effects]` table at all, and only in a run that adds the two keys).
- **Files affected:** `website/content/docs/installation/known-issues.md`.

## Final Implementation Notes
- **Actual work done:** `CODEX_TUI_OVERRIDES` is now `-c tui.animations=true -c tui.whimsy=false -c tui.effects.starfield=false -c tui.alternate_screen=never`; seed and this repo's `.codex/config.toml` carry `[tui] whimsy = false` + `[tui.effects] starfield = false`; `merge_codex_settings` gained the one-shot retirement of the t1797 `animations = false` and the two-spelling mirroring; launcher argv tests, the seed/merge test (45 asserts), new live 0.160.1 fixtures and their review-loop / idle / minimonitor-smoke tests; monitor doc, website known-issues, `monitor_core.py` and `aitask_codeagent.sh` comments.
- **Deviations from plan:** `tui.effects.welcome=false` deliberately not added (measured: no idle difference; source bounds it at 10.8 s). Fixture set grew beyond the plan (fresh-idle + starfield control) after review. The seed-marker and two-spelling rules were added at review. Minimonitor smoke paints the after-turn 0.160 at-rest fixture.
- **Issues encountered:** the starfield never draws in a detached tmux without a `window-style` fg/bg (t1797 knew this; rediscovered). Codex 0.154.0 silently ignores `tui.effects.*` — measured by installing it via npm into the scratchpad — hence both keys. The 0.160 starfield control classifies as `dialog` (its `›⠁Ask` composer line misses the composer pattern) where 0.154's classified `busy`; tests assert only "not ready" and t1805 is told.
- **Key decisions:** both starfield keys in the launch argv and the seed (0.154 needs `whimsy`, 0.160 canonical key survives alias removal); explicit `animations=true` to outrank seeded project values; retirement keyed on the absence of both markers so it is one-shot and never fights a later deliberate value; OS reduced-motion documented as an unfixable residual.
- **Upstream defects identified:**
  - tests/test_codeagent_resume_session.sh:107 — opencode cases pin `opencode/openai_gpt_5_2`, which the live registry now marks unavailable, so 3 asserts fail with die's exit 1 instead of the RESUME_UNSUPPORTED exit 2 (reproduced on a clean HEAD worktree; same pinning pattern t1871 fixed in test_codeagent.sh by deriving the model from the fixture registry)
