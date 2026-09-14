---
Task: t1797_codex_idle_starfield_animation_defeats_idle_detection.md
Base branch: main
Output branch: main
---

# t1797 — Codex idle starfield animation defeats idle detection

## Context

codex-cli 0.154.0 draws an animated Braille "starfield" (U+2800–U+28FF) around
and *inside* the idle composer line. Because the glyphs are visible characters,
`strip_ansi` keeps them, and that breaks two detectors:

- the monitor idle timer (`classify_content` → `_apply_bookkeeping`) sees a new
  `compare_value` on every tick, so an idle Codex pane never reads IDLE;
- the review-loop shadow readiness (`review_loop._codex_state` plus the
  minimonitor raw-tail hash streak) flaps between ready and busy and never
  reaches hash stability, so the `L` auto-recheck loop never fires.

The task measured a kill switch: `codex -c tui.animations=false`, which gives
a byte-stable plain composer. Layer-3 decision (user, at planning): ship
**layers 1 + 2** now and spawn the detector-side Braille defense as a
risk-mitigation "after" follow-up.

Probe facts gathered during planning:
- Codex 0.154.0 accepts an unknown `-c tui.zz_bogus_key=false` with output
  identical to the control run, so the flag cannot break a Codex build that
  lacks the key.
- `codex resume --help` lists `-c`.
- Every framework Codex spawn goes through `aitask_codeagent.sh`: shadows via
  `resolve_dry_run_command` (minimonitor/monitor), restore via
  `agent_restore.py` → `invoke raw --resume-session`, and the syncer via `raw`.
- The repo root is `trusted` in `~/.codex/config.toml`, so it can serve as the
  project-local probe directory.

## Implementation

### 1. Launch-side flag (`.aitask-scripts/aitask_codeagent.sh`)

- Add a top-level array near the other constants:
  `CODEX_TUI_OVERRIDES=(-c tui.animations=false)`. Its comment should say:
  t1797; Braille starfield in 0.154.0; the flag is preferred over
  `tui.whimsy` because it is narrower; unknown keys are tolerated (measured),
  so older Codex builds are unaffected.
- In the `codex)` branch of the CMD builder (~L539-570), rebuild every argv
  with the overrides placed right after the binary. The one exception is
  resume, where they go after `resume <sid>` so the leading-positional
  contract, and the existing `"codex resume sess_9"` assertion, hold:
  - `batch-review|raw` without resume:
    `CMD=("$binary" "${CODEX_TUI_OVERRIDES[@]}" "$model_flag" "$cli_id")`
    followed by `CMD+=("${args[@]}")`.
  - `batch-review|raw` with resume:
    `CMD=("$binary" resume "$OPT_RESUME_SESSION" "${CODEX_TUI_OVERRIDES[@]}" "$model_flag" "$cli_id")`.
  - Skill launches:
    `CMD=("$binary" "${CODEX_TUI_OVERRIDES[@]}" "$model_flag" "$cli_id" "$prompt")`.
- Leave the claudecode and opencode branches unchanged.
- **Argv-consumer audit (done at planning — clean):**
  - `lib/agent_launch_utils.py:269` passes the whole `DRY_RUN:` command
    string through.
  - `chatlink/preflight.py:parse_dry_run_argv` only parses the
    `explore-relay` argv, which is Claude Code-only; the Codex branch refuses
    that operation.
  - `tests/test_codex_model_detect.sh` is a live `codex exec` harness, not an
    argv parser.
  - No positional `--model` reader exists under `lib/` or `monitor/`.
  - During implementation, re-grep once for a new reader added since then.
    Nothing else is expected.

### 2. Per-project config (layer 2)

- `seed/codex_config.seed.toml`: add a commented block
  `[tui]` / `animations = false` (t1797 rationale; the `-c` flag remains the
  deterministic path for framework spawns). This block covers hand launches
  inside a trusted project.
- `.codex/config.toml` (this repo's tracked config): add the same `[tui]`
  block. Do not re-sync its other pre-existing drift from the seed — that is
  out of scope.
- `merge_codex_settings` (`aitask_setup.sh:2714`) needs **no code change**:
  its generic `deep_merge` already adds a missing `[tui]` table, adds a
  missing key into an existing `[tui]` (e.g. a user's `pet = "disabled"`), and
  never overwrites an explicit user `animations = true`. Pin all of that with
  tests (step 3c).
- **Live probe — does Codex honour `[tui]` from the project-local config?**
  Only the `-c` path was measured. After editing `.codex/config.toml`:
  - **Probe isolation (applies to 2 and 2b).** Every probe runs on a
    **per-run** tmux server that nobody else can reach, set up the same way
    `test_minimonitor_concern_smoke.py` does it:
    - `probe_dir=$(mktemp -d <scratchpad>/t1797tmux.XXXXXX)`, and run every
      command with `TMUX_TMPDIR="$probe_dir" tmux -L t1797probe_$$ …`. The
      socket then lives in a directory created by this run, under a name that
      carries this run's PID.
    - Before starting, `has-session` must fail, meaning the server is not
      already running. If it succeeds, stop instead of reusing it.
    - Teardown targets only that server: `TMUX_TMPDIR="$probe_dir" tmux -L
      t1797probe_$$ kill-server`, then `rm -rf "$probe_dir"`.

    Never use a fixed socket name, and never touch the default server.
  - Run at 120x30 with cwd = repo root.
  - Launch plain `codex` (no `-c`). Take 4 samples at 1 s with
    `capture-pane -p -e`, then check for U+2800–U+28FF and for tail stability,
    both raw and stripped.
  - Negative control: `codex -c tui.animations=true` in a second window must
    show Braille. This proves the probe can see the animation.
  - Tear down only this run's server, as the isolation rule above describes.
  - If the project layer is **not** honoured, keep the seed block (harmless)
    but record in the doc that only the `-c` path is sanctioned, and say so in
    the Final Implementation Notes.
  - Keep the raw captures in the scratchpad; they feed step 3d.

### 2b. Live resume smoke (the real `codex resume <sid>` path)

Dry-run strings cannot prove that a real `codex resume <sid>` accepts `-c`
after the session positional, or that the restored TUI honours it. Use its
own per-run isolated server, following the step-2 isolation rule (a fresh
`mktemp -d` `TMUX_TMPDIR`, socket name `t1797resume_$$`, and refuse to reuse
an existing server), with cwd = repo root:

1. Launch through the real launcher:
   `./ait codeagent --agent-string codex/gpt5_6_terra invoke raw`.
   Send one harmless marker prompt: "Reply with exactly: t1797-resume-marker.
   Do not run any commands." Wait for the reply, then exit Codex. This costs
   one short model turn.
2. Resolve the session id the way production does:
   `agent_sessions.newest_transcript_for(<repo root>, "codex")`. Confirm the
   resolved rollout contains `t1797-resume-marker`. This guards against a
   concurrent Codex session in the repo root. If the newest match is a
   different session, pick the rollout that holds the marker.
3. Resume through the real launcher:
   `./ait codeagent --agent-string codex/gpt5_6_terra invoke raw --resume-session <sid>`.
   Accept only when all three hold:
   - the pane's Codex process argv (`ps -o args=`) carries
     `resume <sid> -c tui.animations=false`;
   - the restored transcript shows the marker exchange, i.e. the resume
     really restored that session;
   - 4 samples of the idle composer at 1 s contain no U+2800–U+28FF and are
     raw-byte-identical.
4. Negative control: `codex resume <sid> -c tui.animations=true` in another
   window shows Braille. This proves the result in step 3 comes from the
   flag, not from the session or the project config.
5. Tear down only this run's server (`kill-server` under its own
   `TMUX_TMPDIR` and `-L` name), then `rm -rf` its temporary directory. If
   step 3 fails because
   Codex rejects `-c` after the session positional, move the overrides before
   the subcommand (`codex -c tui.animations=false resume <sid> …`), update the
   3b assertion to the new order, and re-run 2b.

Record the outcome, with the argv and sample evidence, in the Final
Implementation Notes.

### 3. Tests

- **a. `tests/test_codeagent.sh`**, new "Test 11e":
  - For codex/gpt5_4 `--dry-run invoke` of each of pick, explain, qa,
    explore, shadow, learn, work-report, trail, batch-review and raw, assert
    the output contains `-c tui.animations=false`.
  - For the skill operations, also assert the prompt is still the last token.
  - Negative control: the claudecode and opencode dry-runs must not contain
    `tui.animations`.
- **b. `tests/test_codeagent_resume_session.sh`**: assert
  `codex resume sess_9 -c tui.animations=false` (the flag comes after
  `resume <sid>` and before the model flag). The existing contiguity
  assertion stays.
- **c. New `tests/test_codex_config_tui_seed.sh`**, modelled on Group D of
  `tests/test_session_hook_install.sh` (same sourcing of the `aitask_setup.sh`
  functions):
  1. The seed parses, and `tui.animations is False`.
  2. An existing config with `[tui] pet = "disabled"` → after the merge,
     `animations` is false and `pet` is preserved.
  3. An existing config with `[tui] animations = true` → the user value is
     kept.
  4. A config with no `[tui]` at all → the table is added.
  5. Three merges are idempotent.
- **d. Fixtures from the step-2 probe** (`tests/review_loop_fixtures.py`):
  - Add `CODEX_0154_NOANIM_AT_REST_RAW` plus a second-tick twin, and two
    consecutive `CODEX_0154_STARFIELD_RAW_{1,2}` ticks. All are trimmed to the
    last 15 lines exactly as `capture_raw_tail` reads them.
  - Document the provenance in the fixture docstring. Note that the existing
    `CODEX_*` fixtures are 0.146.0 and pre-date the animation.
  - In `tests/test_review_loop.py`:
    - `_codex_state(NOANIM) == SHADOW_READY`, and
      `shadow_prompt_ready(NOANIM, "codex", True) is True`.
    - The two no-anim ticks are raw-equal. Hash stability depends on this.
    - **Characterization:** the two starfield ticks differ after
      `strip_ansi`, and both carry Braille. This pins the failure mechanism;
      the L3 follow-up will flip it.
- **e. `tests/test_idle_compare_modes.py`**: add
  `_check_codex_noanim_ticks_reach_idle` (the two no-anim ticks → `is_idle`).
  Add a characterization check that the starfield ticks do not reach idle.
  The existing `_check_visible_text_change_resets_idle` stays as the
  negative control.
- **f. Real L-recheck path with a Codex shadow**
  (`tests/test_minimonitor_concern_smoke.py`). The parser tests in 3d supply
  `hash_stable=True` by hand. Production also requires the
  `_loop_shadow_hash_streak` to reach 1, and `_fire_shadow_recheck`
  (`minimonitor_app.py` ~L4622) revalidates on a fresh capture that must be
  **byte-equal** to the tick tail. The existing `_arm_and_fire_once` only ever
  uses a Claude-shaped composer stub as the shadow, so neither gate has run
  against a Codex shadow.
  - **Setup.** In `setUpClass`, add a dedicated session
    (`{SESSION}_follow_codex_shadow`). It holds a followed pane (the `codex`
    fake + frame stub) and its own `agent-shadow-codex` window (the `codex`
    fake + frame stub over a separate shadow frame file), bound with
    `@aitask_shadow_target`. A separate session keeps the existing codex
    subtest's newest-match shadow lookup unchanged. The binary really is
    named `codex`, so the app's own two-rung shadow resolution returns
    `codex` and `_codex_state` runs.
  - **Positive.** Paint the shadow with `CODEX_0154_NOANIM_AT_REST_RAW`. Arm
    through the real `action_toggle_review_loop`. Drive the Codex followed
    frames SEL1 → LATER exactly as `_arm_and_fire_once` does, then run the
    real `_service_review_loop` for `DEBOUNCE_TICKS + 3` ticks. Wrap
    `_fire_shadow_recheck` in a spy that calls through. Assert:
    - the streak reached ≥ 1;
    - the real `_fire_shadow_recheck` returned `'sent'` (its fresh-capture
      readiness and byte-equality checks passed);
    - the controller reached FIRED.

    If `_submit_shadow_prompt`'s capture verification cannot pass on a stub
    that does not echo input, add a Codex variant of `_COMPOSER_STUB`. It
    renders the 0.154.0 frame and echoes typed input, and the test then also
    asserts the recheck line lands exactly once, as the Claude case does.
  - **Characterization.** Same flow, but before each service call repaint the
    shadow frame with `CODEX_0154_STARFIELD_RAW_1` / `_2` alternately. Assert
    the streak never reaches 1, `_fire_shadow_recheck` never returns
    `'sent'`, and the controller never reaches FIRED. This is the production
    symptom the task reports; the L3 follow-up flips it.

### 4. Docs

- In `aidocs/framework/monitor_idle_and_prompt_detection.md`, under "What the
  capture actually contains", add a "Visible-glyph animation" note covering:
  - the Codex starfield class, and why `stripped` mode cannot absorb it
    (next to the t715 colour-animation case);
  - the launch-side `-c tui.animations=false` as the sanctioned answer: it
    overrides every config layer. The seed `[tui]` is only a **default added
    when absent** — `merge_codex_settings` keeps an explicit project value —
    so it covers hand launches only in trusted projects that have not set
    `animations` themselves;
  - a warning not to strip Braille globally, because shell spinners (ora-style
    `⠋⠙⠹`) are real activity in non-agent panes;
  - a pointer to the L3 follow-up task.
- Update the `COMPARE_MODE_STRIPPED` comment in `monitor_core.py` with a
  one-line pointer to this doc section.
- Website: `website/content/docs/installation/known-issues.md`, Codex
  section. Next to the paragraph on `default_mode_request_user_input`, add a
  short current-state paragraph saying three things:
  - `ait setup` adds `[tui] animations = false` to `.codex/config.toml`
    **only when the project config does not already set `animations`**. An
    explicit value there is kept, so a project that sets `animations = true`
    keeps the animation for Codex sessions started by hand;
  - `ait codeagent invoke` passes `-c tui.animations=false`, which takes
    precedence over every config file, so framework-launched Codex panes are
    animation-free either way;
  - the reason: the idle-composer animation keeps `ait monitor` /
    `minimonitor` from reading the pane as idle, and blocks shadow readiness.

  `installation/_index.md` only says "created or merged with aitask
  settings", so it needs no change. Run `python3 check_links.py --build` in
  `website/`.
- No skill files change, so there is nothing to port to other agent trees.

### 5. Verification

- `bash tests/test_codeagent.sh`
- `bash tests/test_codeagent_resume_session.sh`
- `bash tests/test_codex_config_tui_seed.sh`
- `bash tests/test_session_hook_install.sh`
- `python3 tests/test_idle_compare_modes.py`
- `python3 tests/test_minimonitor_concern_smoke.py` (live private tmux; covers
  the new Codex-shadow positive and characterization cases, and the existing
  cases still pass)
- `bash tests/run_all_python_tests.sh --test-dir tests` (read only the last
  line; check `PIPESTATUS`)
- `shellcheck .aitask-scripts/aitask_codeagent.sh`
- Live end-to-end check: spawn a Codex shadow from minimonitor (or run
  `ait codeagent --agent-string codex/<model> invoke raw` in an `agent-*`
  window of a private tmux session). The pane must read IDLE after the
  threshold, and the captured argv must carry the flag. The real L path is
  covered by 3f and the real resume path by 2b; both results are recorded in
  the Final Implementation Notes.

### 6. Post-implementation

Step 9 (Post-Implementation): current-branch mode. The commit is
`bug: ... (t1797)`, followed by gate runs and archival. Step 8d creates the
"after" mitigation below.

## Risk

### Code-health risk: low
- The argv change reaches every framework Codex spawn (skills, shadow, restore
  via `invoke raw --resume-session`, syncer). A consumer that parses the
  codeagent argv by position would misread the inserted `-c` pair.
  · severity: medium · → mitigation: none (the in-plan argv-consumer audit in
  step 1 and the dry-run tests in 3a/3b cover it)
- `merge_codex_settings` re-serialises TOML and drops comments. This is a
  pre-existing known loss that is not made worse: the merge already runs
  whenever `.codex/config.toml` exists. · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Codex honouring `[tui]` from the project-local config is unmeasured; only
  the `-c` path was proven. · severity: medium · → mitigation: none (the live
  probe in step 2 decides it, with a documented fallback)
- Two no-animation captures reading `ready` in `review_loop` do not prove the
  production L path: the minimonitor hash streak and the delivery-time
  byte-equality revalidation also gate the fire. · severity: medium
  · → mitigation: none (the real-path Codex-shadow test in step 3f)
- A real `codex resume <sid>` accepting `-c` after the session positional,
  and the restored TUI honouring it, is only asserted in dry-run strings.
  · severity: medium · → mitigation: none (the live resume smoke in step 2b,
  with an ordering fallback)
- The layer-2 seed is a default added when absent, not a guarantee; an
  explicit project `animations = true` survives setup. · severity: low
  · → mitigation: none (the docs in step 4 state the precedence exactly)
- Codex silently ignores unknown `-c` keys, so a future rename of
  `tui.animations` would bring the bug back with no error. Codex panes
  launched outside the framework stay affected. · severity: medium
  · → mitigation: codex_braille_detector_defense

### Planned mitigations
- timing: after | name: codex_braille_detector_defense | type: enhancement | priority: medium | effort: medium | inline_risk: medium | added_complexity: high | addresses: goal-achievement — silent tui.animations rename / hand-launched Codex panes keep the starfield | desc: Codex-scoped detector-side defense — treat U+2800–U+28FF as decoration in classify_content's compare value, _codex_state's composer line and the minimonitor shadow raw-tail hash, only when the resolved agent is codex, with negative controls proving real content changes still reset idle and Braille spinners in non-Codex panes still count as activity

## Final Implementation Notes
- **Actual work done:**
  - **Layer 1.** `CODEX_TUI_OVERRIDES=(-c tui.animations=false)` in
    `aitask_codeagent.sh`. Every Codex argv carries it: the skill composers
    (including explore), batch-review/raw, and — after `resume <sid>` — restores.
  - **Layer 2.** `[tui] animations = false` in `seed/codex_config.seed.toml` and
    in this repo's `.codex/config.toml`. `merge_codex_settings` is unchanged:
    its generic `deep_merge` already adds the key when absent and keeps an
    explicit value.
  - **Tests:**
    - `test_codeagent.sh` Test 11e: every Codex operation carries the flag,
      plus a negative control for Claude Code and OpenCode.
    - `test_codeagent_resume_session.sh`: order assertions for the resume argv.
    - New `test_codex_config_tui_seed.sh`: seed value, add-when-absent, explicit
      value kept, idempotent, no subshells.
    - `CODEX_0154_*` fixtures plus `Codex0154ComposerTests` in
      `test_review_loop.py`.
    - Two idle checks in `test_idle_compare_modes.py`.
    - Two real-path Codex-shadow cases in `test_minimonitor_concern_smoke.py`.
      They add an echoing `_CODEX_COMPOSER_STUB`, a dedicated `codex_shadow`
      session, and a `key=` parameter on `_pane_info` / `_paint` / `_app`.
  - **Docs:** a "Visible-glyph animation" section in
    `monitor_idle_and_prompt_detection.md`, a pointer in the `monitor_core.py`
    compare-mode comment, and a Codex paragraph in the website known-issues
    page.
- **Deviations from plan:**
  1. **The root cause is narrower than the task stated.** Per the upstream
     source (`codex-rs/tui/src/bottom_pane/chat_composer/sparkle.rs` at
     `rust-v0.154.0`, `enabled_foreground`), the starfield draws only when all
     of these hold: `whimsy`, `animations`, a model matching `\bastra\b`,
     truecolor, and known terminal default colours. It is not a property of
     every 0.154.0 session. On this machine it showed only in the
     `gpt-6-astra` shadows (4 of 14 live). The task's kill-switch evidence was
     one launch per arm and therefore weak; the upstream test
     `model_changes_and_disable_setting_control_sparkle` and a deterministic
     probe now establish it.
  2. **The probes needed three things to see the animation at all:**
     `-m gpt-6-astra`; a tmux `window-style` fg/bg, so that a server with no
     real terminal attached can answer the colour queries; and a short
     `TMUX_TMPDIR` (`/tmp/claude-1000/t1797.XXXXXX`), because the scratchpad
     path exceeds the Unix socket path limit. Isolation was unchanged: a
     per-run directory, a PID-suffixed socket, refusal to reuse a server, and
     teardown of only that server.
  3. **Fixture extent.** The fixtures are stored at `capture_raw_tail`'s full
     returned extent (42 rows), not trimmed to 15 lines. That function's
     docstring requires fixtures at production extent.
  4. **Resume smoke (2b).** Session creation and resume went through the real
     launcher (terra). The animation negative control used
     `codex resume <sid> -c tui.animations={true,false} -m gpt-6-astra`
     directly, in the launcher's argv shape, because `models_codex.json` has
     no Astra entry.
- **Issues encountered:**
  - The first four probes showed no Braille even in the `animations=true`
    control. I ruled out `COLORTERM`, pane size, an attached client and idle
    time before the upstream source identified the model and terminal-colour
    gates.
  - Probe v5 used `gpt-6-astra` under identical terminal conditions. The
    control drew 47–54 dots per capture and changed every tick. The
    `-c tui.animations=false` flag and the project config alone each gave 0
    dots and a byte-stable tail, so layer 2 is honoured in a trusted project.
  - Resume smoke:
    - The real launcher's argv was
      `codex resume <sid> -c tui.animations=false -m gpt-5.6-terra`, the
      transcript was restored (marker visible), and the tail was stable.
    - On the same session as Astra, `animations=true` drew 28–35 changing
      dots; `false` gave 0 dots and a stable tail.
    - `newest_transcript_for` returned a different repo-root Codex session;
      the marker scan found the right one.
  - Mistakes caught by the tests:
    - My first Test 11e assumed `--model`; Codex's flag is `-m`.
    - I first missed the skill-launch `CMD` line.
  - The full Python suite reports four failures in
    `test_parallel_admission_collect.py`. They reproduce on a clean detached
    worktree of HEAD (`c52534f14`), so they predate this task (see below).
- **Key decisions:**
  - The overrides go right after the binary, and after `resume <sid>` for
    restores, so `resume` stays the leading positional.
  - `tui.animations` over `tui.whimsy`: it is narrower, and both gate the
    sparkle.
  - Layer 3 is deferred to the risk-mitigation "after" follow-up, per the
    user's decision at planning.
  - Codex tolerates unknown `-c tui.*` keys (measured), so older builds are
    unaffected.
- **Upstream defects identified:**
  - tests/test_parallel_admission_collect.py:500 — fixtures hard-code `locked_at: "2026-08-30 08:00"` while the `col.main(...)` CLI paths use the wall clock, so four tests (ReplayInvariant, ExcludeNoPlanPredicate ×2, ThresholdSweep) fail once the claim ages past the freshness window; reproduced on a clean HEAD worktree
  - tests/test_session_hook_install.sh:122 — Groups A–D assert inside `( … )` subshells without `assert_counters_init`/`assert_counters_load`, so a failure there cannot reach the footer and the file still exits 0 (the t1207 pattern)
  - .aitask-scripts/lib/agent_sessions.py:1659 — `_codex_newest_transcript` returns the newest rollout whose cwd equals the project root, so with several Codex sessions in one repo the restore fallback can resolve a different session than the one being restored (observed live in t1797's resume smoke)
