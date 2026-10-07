---
Task: t1902_default_all_codex_launches_to_inline_mode.md
Base branch: main
Output branch: main
---

# t1902 — Default every framework Codex launch to inline mode

## Context

t1900 added `-c tui.alternate_screen=never` to Codex **shadow** launches only
(`CODEX_SHADOW_OVERRIDES` in `aitask_codeagent.sh`). codex-cli 0.160.0 otherwise
runs on the alternate screen, where tmux keeps no scrollback, so ordinary Codex
agent panes lose history for capture, review and copy mode. The user wants
inline mode as the default for every framework Codex launch. Other agents are
unchanged. The `-c` config form stays (t1900 measured it tolerated on
0.153.4 / 0.156.1; `--no-alt-screen` is a hard clap error on older builds).

Settled during planning:

- **Only two Codex argv builders exist.** `aitask_codeagent.sh` (every
  `invoke` op, plus restore, which goes through `invoke raw --resume-session` via
  `agent_restore.build_resume_argv`) and **`aitask_skillrun.sh`** (`ait skillrun`).
  skillrun's codex arm builds `codex -m <id> "<prompt>"` directly, so it bypasses
  even the t1797 animation override. No other framework file spawns `codex`.
- **Freeze claim is wrong.** `agent_freeze.freeze_pane(pane_id)` (behind
  `aitask_frozen.sh freeze <pane>`) never checks `@aitask_shadow_target`; only
  `discover_panes` / Freeze-All exclude shadows. With the shared override, a
  shadow that is frozen directly and restored through `invoke raw
  --resume-session` keeps inline mode anyway.
- **Monitor consumers.** Before 0.160, Codex ran inline by default, and the
  followed-pane detectors were measured on inline Codex (t1467 on 0.146, t1522 on
  0.154). The followed-pane classifier (`classify_content`) reads a bottom
  6-line window, so history above it is never scanned. `classify_followed_change`
  treats `history_size` growth as WORK. That is the inline-pane design already
  used for Claude Code. The review loop's whole-tail sweep already discards
  historical Codex dialog text through `_codex_dialog_is_historical` (t1900). That
  rule is keyed on `agent="codex"`, not on "shadow". `_codex_cmdline_argv` /
  `_argv_model` find `-m` anywhere in argv, so an extra `-c` pair is harmless.
  No code change is needed in those consumers. Comments that say "shadows only"
  get reworded, and the classifier gets new pins (step 5).
- The 0.160 update-dialog wording gap belongs to **t1904**. It is not touched here.

## Implementation steps

1. **Move the shared array into `lib/agent_string.sh`.** It is already sourced by
   both builders, so neither builder duplicates the setting.
   - Add the following after `SUPPORTED_AGENTS`:
     ```bash
     # Codex TUI overrides carried by every framework Codex launch
     # (aitask_codeagent.sh and aitask_skillrun.sh).
     #  * tui.animations=false (t1797): ... (move the existing comment)
     #  * tui.alternate_screen=never (t1900, t1902): ... (reworded t1900 comment:
     #    0.160 defaults to the alternate screen, no scrollback; config form
     #    rather than --no-alt-screen; every Codex launch, including
     #    `codex resume`, so a restored pane keeps inline mode too)
     # shellcheck disable=SC2034  # Read by callers after sourcing this lib.
     CODEX_TUI_OVERRIDES=(-c tui.animations=false -c tui.alternate_screen=never)
     ```
   - Add `CODEX_TUI_OVERRIDES` to the lib's "Provides:" header list.

2. **`.aitask-scripts/aitask_codeagent.sh`**
   - Delete the local `CODEX_TUI_OVERRIDES=` definition and the whole
     `CODEX_SHADOW_OVERRIDES` block (comment and array). Leave a one-line pointer
     comment saying the overrides come from `lib/agent_string.sh`, and update the
     "Constants come from lib/agent_string.sh" header comment to list it.
   - In the codex `*)` skill arm, collapse back to
     `CMD=("$binary" "${CODEX_TUI_OVERRIDES[@]}" "$model_flag" "$cli_id" "$prompt")`.
     That removes the shadow conditional. The prompt stays last.
   - The `batch-review|raw` arm and the resume branch keep their current shape.
     The array now carries both pairs, so `resume <sid>` still leads and the
     passthrough args stay last.

3. **`.aitask-scripts/aitask_skillrun.sh`**: change the codex arm to
   `CMD=("$binary" "${CODEX_TUI_OVERRIDES[@]}" "$model_flag" "$cli_id" "$codex_prompt")`
   and add a comment pointing to the shared array. Update the header usage
   comment's codex line (`exec codex <codex tui overrides> -m <cli_id> ...`).

4. **Launcher tests**
   - `tests/test_codeagent.sh`
     - Test 11e's prefix becomes
       `codex -c tui.animations=false -c tui.alternate_screen=never -m gpt-5.4`.
       Rename/reword its header: every Codex launch carries both overrides
       before the model flag.
     - Rewrite **Test 11f** as positive. Every op (`pick explain qa shadow learn
       work-report trail discuss explore batch-review raw`) and
       `raw --resume-session <sid>` contain `tui.alternate_screen=never`. The
       composer prompt or passthrough arg is still last (reuse
       `dry_run_last_arg`). For resume, `codex resume <sid> -c` leads.
     - Keep the negative-agent loop, extended so claudecode/opencode
       pick **and** shadow carry neither `tui.animations` nor
       `tui.alternate_screen`.
   - `tests/test_codeagent_resume_session.sh:94,101`: update the two expected
     prefixes to include `-c tui.alternate_screen=never` before `-m`.
   - `tests/test_skillrun_codex.sh`: replace `codex -m gpt-5.4` with the
     overrides-prefixed form. Add one assertion that a claudecode skillrun
     carries no `tui.` override. Reword the header comment.
   - Negative control (manual, not committed): temporarily drop
     `-c tui.alternate_screen=never` from the lib array, and confirm that 11e,
     11f, resume_session and skillrun fail. Then restore it with the Edit tool,
     not `git restore`.

5. **Followed-pane classifier pins** (`tests/test_review_loop.py`, beside
   `CodexHistoricalDialogTests`): add `CodexInlineFollowedPaneTests`. These run
   through the production `mc.classify_content(..., pp.all_patterns(),
   PaneCategory.AGENT, "codex")`:
   - `CODEX_0160_INLINE_DISMISSED_UPDATE_RAW` → `awaiting_input` False.
   - Composed pre-0.160 inline history (`CODEX_UPDATE_PROMPT_RAW + "\n" +
     CODEX_AT_REST_RAW`) → `awaiting_input` False, while `CODEX_UPDATE_PROMPT_RAW`
     alone → `codex_update_prompt`. This pins the history-vs-current rule.
   - Historical update + live `CODEX_PERMISSION_RAW` at the bottom → awaiting
     with the same kind `CODEX_PERMISSION_RAW` alone reports, so a live dialog
     is still found below retained text.
   - Two identical inline at-rest captures with equal `history_size` →
     `classify_followed_change` returns `NO_CHANGE`. The same pair with
     `curr_history_size` larger → `WORK`. This pins the documented inline
     semantics now that Codex panes report history.

6. **Comments / docs (current state only)**
   - `monitor/monitor_core.py` `capture_raw_tail` docstring: "inline pane
     (Claude Code, and every framework-launched Codex pane, launched with
     `tui.alternate_screen=never`)".
   - `lib/pane_state_probe.py` `_CAPTURE_LINES` comment: "(Claude Code,
     framework-launched Codex)".
   - `monitor/review_loop.py`: `_codex_dialog_is_historical` docstring says "the
     framework launch mode for every Codex pane", not "the shadow launch mode".
     `_ordered_state` says "an idle pane", not "an idle shadow".
   - `tests/test_review_loop.py` `CodexHistoricalDialogTests` docstring and the
     `tests/review_loop_fixtures.py` 0.160 provenance comment: the fixture was
     captured from a shadow, but every Codex launch now uses this mode. Keep the
     provenance and add one clause.
   - `aidocs/framework/shadow_agent.md`, "Codex shadows launch inline"
     paragraph: rewrite as "Codex panes launch inline". It covers every
     framework Codex launch (`CODEX_TUI_OVERRIDES` in `lib/agent_string.sh`, used
     by `aitask_codeagent.sh` and `aitask_skillrun.sh`), including
     `invoke raw --resume-session`. It corrects the freeze claim: Freeze-All
     skips shadows through discovery, but `aitask_frozen.sh freeze <pane_id>`
     calls `freeze_pane` directly and does not, and a shadow restored that way
     keeps inline mode because the restore arm carries the shared override.
     Also fix the "Codex shadows" wording in the `-S -15` recipe paragraph and
     the historical-dialog paragraph (~L725) if they say shadow-only.
   - `.claude/skills/aitask-shadow/concern-format.md` Capture-window contract
     bullet: "Codex panes are therefore launched inline by the framework (...)
     — shadows included".
   - `aidocs/framework/monitor_idle_and_prompt_detection.md` ~L158: name the
     array's new home and say it also carries `tui.alternate_screen=never`.
     Followed Codex panes are inline, so the bottom-window classifier and
     history-growth WORK signal apply as for Claude Code.
   - `website/content/docs/installation/known-issues.md`: the animations bullet
     names `ait codeagent invoke` and `ait skillrun`. Add one bullet saying both
     also pass `-c tui.alternate_screen=never`, so Codex runs inline and tmux
     keeps the pane's scrollback for copy mode and captures. Run
     `python3 check_links.py --build` in `website/`.
   - Run `./.aitask-scripts/aitask_skill_verify.sh` (concern-format.md is in a
     skill dir). Regenerate goldens only if it reports drift.

7. **Step 9 (Post-Implementation)**: current-branch workflow. Commit the code as
   `enhancement: Default all Codex launches to inline mode (t1902)`, commit the
   plan via `aitask_task_commit.sh`, then archive.

### Post-phase (risk mitigations)

1. [live_inline_followed_probe] Run this on an isolated tmux socket
   (`tmux -L t1902probe`). Use an isolated `CODEX_HOME` in the scratchpad, made
   from copies of `~/.codex/config.toml` and `auth.json`. Never write to the
   real `~/.codex`.
   - **Non-shadow launch.** Take the argv from `aitask_codeagent.sh
     --agent-string codex/<model> --dry-run invoke raw` (no prompt, so no model
     turn). Boot it. Record `#{alternate_on}`=0 and `history_size`. Send the
     local `/status` command and confirm that `history_size` grows.
   - **At rest.** Take 5 samples over about 10 s. `capture-pane -p -e -S -15`
     (stripped) and `history_size` must stay constant.
   - **Copy mode.** Enter `copy-mode` and scroll up (`send -X page-up`). The
     capture and `history_size` must be identical to the pre-scroll capture.
     Exit copy mode.
   - **Resume.** Copy one rollout file from `~/.codex/sessions/...` into the
     isolated `CODEX_HOME/sessions/` at the same relative path. Launch the
     `--resume-session <sid> --dry-run invoke raw` argv with that `CODEX_HOME`,
     and confirm `alternate_on`=0 with growing history. Kill the socket.
   - Record results in Final Implementation Notes. Anything not performed (a
     real model turn, a real answered permission dialog in a followed pane) goes
     to a manual-verification follow-up at Step 8c.

## Verification

- `bash tests/test_codeagent.sh`, `bash tests/test_codeagent_resume_session.sh`,
  `bash tests/test_skillrun_codex.sh`: all pass.
- `shellcheck .aitask-scripts/aitask_codeagent.sh .aitask-scripts/aitask_skillrun.sh .aitask-scripts/lib/agent_string.sh`
  is clean.
- `bash tests/run_all_python_tests.sh --test-dir` scoped to
  `test_review_loop.py`, `test_agent_sessions_transcripts.py`,
  `test_minimonitor_concern_action.py`, then the full suite. Read only the
  last-line verdict.
- `./.aitask-scripts/aitask_skill_verify.sh` and
  `bash tests/test_skill_render_aitask_shadow.sh` pass.
- `website/`: `python3 check_links.py --build` passes.
- The live probe above covers acceptance 4 and the copy-mode half of 5.

## Risk

### Code-health risk: low
- The shared array moves to `lib/agent_string.sh`, away from the two builders
  that expand it. The shell does **not** enforce its presence: under
  `set -u`, `"${UNDECLARED[@]}"` expands to nothing and exits 0 (reproduced on
  bash 5.3.15). So if the definition disappeared while the lib's functions
  stayed available, both builders would silently omit the overrides. The
  protection is the step-4 launcher assertions. 11e/11f, resume_session and
  skillrun each assert the exact override-prefixed argv for both builders. The
  step-4 negative control shows they fail when the flag is removed. No runtime
  guard is added. · severity: low · → mitigation: none (covered in-plan by
  step 4's assertions)

### Goal-achievement risk: low
- Followed-pane monitor signals (bottom-window prompt detection, idle compare,
  history-growth WORK) were measured on inline Codex ≤0.154. They were never
  measured on the 0.160 inline renderer for a *followed* (non-shadow) pane over
  time: at-rest stability, copy-mode invariance, resume. A 0.160 inline redraw
  that scrolls rows into history while idle would read as perpetual WORK.
  · severity: low (residual — addressed by inline post-phase
  live_inline_followed_probe) · → mitigation: inline post-phase live_inline_followed_probe
- A real model turn and a real answered permission dialog in a followed inline
  pane need a human-driven session. · severity: low · → mitigation: none (Step
  8c manual-verification follow-up)

### Planned mitigations
- timing: post-phase | name: live_inline_followed_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement (0.160 inline followed-pane signals unmeasured) | desc: Isolated-socket boot of the real non-shadow and resume Codex argv; assert alternate_on=0, history growth, at-rest stability, copy-mode capture invariance

## Post-phase (risk mitigations) — outcome
- live_inline_followed_probe: done (codex-cli 0.160.0, `tmux -L t1902probe`, 120x40, isolated `CODEX_HOME`).
  - Non-shadow `invoke raw` argv (`codex -c tui.animations=false -c tui.alternate_screen=never -m gpt-5.6-terra`): alternate_on=0; history_size 0 at boot.
  - At rest: 5 samples over 10 s, `capture-pane -p -S -15` byte-identical and history_size constant.
  - After the local `/status`: history_size 0→8. Then 3 samples were again identical.
  - Copy mode (`page-up`, scroll_position 8): the `-p -e -S -15` capture is byte-identical to the pre-scroll one and history_size is unchanged.
  - The live capture through production classifiers: `classify_content` reads not awaiting, and `shadow_state` reads `ready`.
  - Resume: `codex resume <sid> -c … -c tui.alternate_screen=never -m …`, using a rollout copied into the isolated CODEX_HOME.
    - It booted inline (alternate_on=0, history 3) into Codex's working-directory choice dialog.
    - After answering "Use current directory", the transcript replayed into history (history 35, alternate_on=0) with no model turn, and the review loop read `ready`.

## Final Implementation Notes
- **Actual work done:**
  - `CODEX_TUI_OVERRIDES` moved to `lib/agent_string.sh` and now carries both `-c tui.animations=false` and `-c tui.alternate_screen=never`.
  - `aitask_codeagent.sh` lost its local array, `CODEX_SHADOW_OVERRIDES` and the shadow-only conditional. Every Codex arm (skill composers, batch-review/raw, `--resume-session`) now carries both overrides.
  - `aitask_skillrun.sh`'s codex arm now expands the shared array. Before this it carried no override at all.
  - Launcher tests:
    - Test 11e covers the full prefix.
    - Test 11f is rewritten as positive (every op and raw resume carry the inline override; passthrough/prompt stays last; resume stays leading).
    - The negative-agent loop now checks pick and shadow for both keys.
    - The resume_session prefixes and the skillrun assertions are updated (plus a claudecode no-override check).
  - New `CodexInlineFollowedPaneTests` in test_review_loop.py, with a negative control (widening the detection window makes retained history read as awaiting).
  - Docs and comments reworded from "shadows only" to "every framework Codex launch": capture_raw_tail, `_CAPTURE_LINES`, review_loop docstrings, the fixture provenance, concern-format.md, shadow_agent.md (including the freeze correction), monitor_idle_and_prompt_detection.md, and a new "Scrollback in Codex panes" section in the website known-issues page.
- **Deviations from plan:**
  - The negative control showed that 11e/11f, resume_session and skillrun fail once the flag is removed. The flag was then restored with Edit.
  - The probe's resume check met Codex 0.160's "Working directory · resume" choice dialog. It was answered with "Use current directory" and no model turn ran.
- **Issues encountered:**
  - A concurrent session implementing t1904 edits review_loop.py, review_loop_fixtures.py and test_review_loop.py in the same checkout. One docstring hunk overlaps.
  - The commit is therefore built from a temp index as HEAD plus the t1902 hunks only, and that exact tree was verified in an isolated worktree against a HEAD control. The t1904 session was notified.
- **Key decisions:**
  - One shared array in the sourced lib instead of per-launcher copies.
  - Presence of the array is enforced by the launcher assertions, not by `set -u`, which does not catch an undeclared array expansion.
  - `ait setup` does not seed `alternate_screen` into the project's `.codex/config.toml`. Only framework launches are covered.
- **Upstream defects identified:**
  - `tests/test_codeagent_resume_session.sh:107-112` — pins `opencode/openai_gpt_5_2`, which the registry now marks unavailable. The three opencode assertions fail (exit 1, "Model … is unavailable") whatever the code under test does. This is the same class t1871 fixed in test_codeagent.sh by deriving the model from the registry.
  - `.aitask-scripts/monitor/prompt_patterns.py:236 — codex-cli 0.160 "Working directory · resume" choice dialog (shown by `codex resume <sid>` when the cwd differs) is not pattern-detected for followed panes`. Measured: `classify_content` reads not-awaiting on the live dialog, though the review loop reads `dialog` structurally. This is the same class as t1798 (unpatterned Codex pre-session screens).
