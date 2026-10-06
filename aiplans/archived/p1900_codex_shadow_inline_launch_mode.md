---
Task: t1900_codex_shadow_inline_launch_mode.md
Base branch: main
Output branch: main
---

# t1900 — Launch Codex shadows in inline (non-alternate-screen) mode

## Context

codex-cli 0.160.0 runs its TUI on the **alternate screen** by default (0.154 and
earlier ran inline). tmux keeps no scrollback for an alternate-screen pane, so
`aitask_shadow_capture.sh --deep` (`-S -400`) and minimonitor's deeper retry see
only the visible rows of a **Codex shadow**. Concern blocks that scrolled off parse
truncated, and scrolling the Codex view changes what `c` offers. The fix is a
launch-mode change, scoped to `invoke shadow` with a Codex agent only.

## Measurements (done during planning, 2026-10-06, isolated tmux socket)

| launch (0.160.0) | alternate_on | history_size |
|---|---|---|
| `codex -c tui.animations=false` | 1 | 0 |
| `… -c tui.alternate_screen=never` | **0** | 11 (growing) |
| `… -c tui.alternate_screen=always` | 1 | 0 |

- Value vocabulary, from the clap/serde error for a bad value:
  `unknown variant 'bogus', expected one of 'auto', 'always', 'never' in 'tui.alternate_screen'`
  (exit 1). So the key exists on 0.160 and `never` disables the alt screen.
- 0.153.4 and 0.156.1 launched normally with `-c tui.alternate_screen=never`
  (alternate_on=0). Older builds accept it. 0.154.0 is not installed here. The
  existing t1797 measurement says unknown `-c tui.*` keys are ignored on 0.154.0.
- **Decision: use `-c tui.alternate_screen=never`, not `--no-alt-screen`.** The
  config form needs no version gate. The flag would be a hard clap error on a
  codex older than 0.160.

## Settled planning questions

- **Restored/resumed shadows:** not applicable. Shadow panes carry
  `@aitask_shadow_target` and are excluded from `TmuxMonitor.discover_panes()`
  (`monitor_core.py` `TmuxPaneInfo.shadow_target` comment). Freeze-All uses that
  discovery (`agent_freeze._agent_panes_for`), and the monitor's freeze acts on
  discovered panes. So a shadow is never frozen, and never restored through
  `invoke raw --resume-session`. No change to the `batch-review|raw` arm. This is
  recorded in a comment beside the new override.
- **Consumers that assume no scrollback:**
  - `monitor_core.capture_raw_tail`: the review loop's readiness/state detectors.
    The detectors were measured on inline codex (0.146 / 0.154), and the
    composer scan is bottom-up. On an inline pane the tail is `lines` history
    rows plus the visible pane, so it is only slightly wider. No behaviour change.
    The docstring's claim "every supported agent CLI runs on the alternate
    screen" is false (Claude Code is alt=0 with history, and Codex shadows now
    are too). Reword it.
  - `lib/pane_state_probe.py` `_CAPTURE_LINES` comment: same false claim. Reword
    it. 200 lines is harmless either way because the classifier uses a bottom
    window.
  - `compute_block_age_staleness` / `parse_block_meta` / `concern_parser`: all of
    them key on the **last** block in the capture ("last block wins"). Deeper
    history only helps them. No change.
  - `monitor/prompt_patterns.py` codex patterns: measured on the inline renderer
    already. No change to the patterns.
  - **`review_loop._ordered_state`: a real defect, which this task fixes (review
    finding, blocking).** It sweeps every codex prompt pattern over the WHOLE
    captured tail before it consults the composer. On an inline pane, dismissed
    dialog text stays in scrollback: t1522 measured this on 0.154 ("the
    dismissed dialog's text stays in scrollback above the next inline screen"),
    and the `CODEX_EXEC_APPROVAL_LATER_RAW` fixture shows a dismissed trust
    screen kept in history. Reproduced during planning:
    `shadow_state(CODEX_UPDATE_PROMPT_RAW + CODEX_AT_REST_RAW, "codex")` returns
    `dialog`, and `shadow_prompt_ready(..., hash_stable=True)` returns `False`.
    The at-rest composer alone returns `ready`. An idle shadow produces no
    output that would push the stale rows out. Every `dialog` re-arms
    `_apply_shadow_settle_latch`, and the latch releases only on `READY`. So
    the armed loop never rechecks: the HOLD is not self-recovering.

## Implementation steps

1. **`.aitask-scripts/aitask_codeagent.sh`**
   - Below `CODEX_TUI_OVERRIDES`, add:
     ```bash
     # Codex shadow launch mode (t1900). codex-cli 0.160.0 runs its TUI on the
     # alternate screen by default, where tmux keeps no scrollback, so the
     # shadow-pane captures (`aitask_shadow_capture.sh --deep`, minimonitor's
     # deeper concern retry) saw only the visible rows. `never` restores inline
     # mode (measured on 0.160.0: alternate_on 1→0, history_size grows; the
     # vocabulary is auto|always|never and a bad value is a hard error). The
     # `-c` form rather than 0.160's `--no-alt-screen` flag because an unknown
     # flag is a hard clap error on older builds, while 0.153.4 / 0.156.1 were
     # measured to launch normally with this override. Shadow launches ONLY:
     # every other Codex launch keeps Codex's default. Shadows are never frozen
     # (excluded from discover_panes), so the `invoke raw --resume-session`
     # restore arm never relaunches one and does not carry it.
     CODEX_SHADOW_OVERRIDES=(-c tui.alternate_screen=never)
     ```
   - In the `codex)` skill-composer arm (`*)` branch), replace the single
     `CMD=(... "$prompt")` with:
     ```bash
     CMD=("$binary" "${CODEX_TUI_OVERRIDES[@]}" "$model_flag" "$cli_id")
     if [[ "$operation" == "shadow" ]]; then
         CMD+=("${CODEX_SHADOW_OVERRIDES[@]}")
     fi
     CMD+=("$prompt")
     ```
     The override goes after the model so the existing Test 11e prefix assertion
     (`codex -c tui.animations=false -m gpt-5.4`) still holds, and the prompt
     stays the last argv element. No empty-array expansion is used, so this is
     bash-3.2 safe under `set -u`.

2. **`tests/test_codeagent.sh`**: add **Test 11f** after Test 11e. Reuse
   `dry_run_last_arg`.
   - `codex/gpt5_4 invoke shadow probe`: contains
     `-m gpt-5.4 -c tui.alternate_screen=never`, and the last arg still contains
     `$aitask-shadow`.
   - Codex negative matrix: `pick explain qa learn work-report trail discuss
     explore batch-review raw`, plus `raw --resume-session <sid>`. None contains
     `tui.alternate_screen`.
   - Other agents: `claudecode/opus5` and `opencode/<active>` `invoke shadow probe`
     still dry-run and carry no `tui.alternate_screen`.
   - Negative control: temporarily remove the `if` block and confirm that 11f fails
     (manual, not committed).

3. **Measure the dismissed-dialog state on the 0.160 inline renderer** (do this
   before step 4; the result becomes a fixture).
   - The 3-option update dialog appears only for package-manager installs. This
     machine's mise install shows an un-patterned notice box instead (seen during
     planning on 0.153.4/0.156.1). Simulate an npm install in an isolated
     environment:
     - set `CODEX_HOME=<scratchpad>/codex_home`, a copy of `~/.codex/config.toml`
       and `auth.json`;
     - write a `version.json` that claims a newer `latest_version` with a
       current `last_checked_at`;
     - set `CODEX_MANAGED_BY_NPM=1`;
     - launch `codex -c tui.animations=false -c tui.alternate_screen=never` in
       an isolated tmux socket (`tmux -L t1900probe`).
   - Capture `capture-pane -p -e -S -15` (exactly what `capture_raw_tail` reads)
     with the dialog live. Dismiss it with "2. Skip", which proceeds without
     installing, then capture again with the TUI at rest. Record
     `alternate_on` / `history_size` both times. Kill the socket. The real
     `~/.codex` is never touched.
   - Store the at-rest capture as `CODEX_0160_INLINE_DISMISSED_UPDATE_RAW` in
     `tests/review_loop_fixtures.py`, with a provenance comment (version,
     geometry, date, method).
   - **If the simulation does not produce the dialog** (env var or cache format
     differs on 0.160), say so in the fixture comment and the Final Notes.
     Fall back to the composed fixture in step 4, which is grounded in the
     measured 0.154 inline shape (t1522 + `CODEX_EXEC_APPROVAL_LATER_RAW`). The
     code fix does not depend on this outcome: older Codex builds run inline
     anyway and already retain the rows.

4. **`.aitask-scripts/monitor/review_loop.py`: tell historical dialog text
   apart from the current interaction (codex only).**
   - Rule: a dialog-pattern match is **historical** when a **non-option
     composer-glyph row** (`_CODEX_COMPOSER_RE` matches and
     `_CODEX_OPTION_ROW_RE` does not) appears on a line **below the match's
     last line**. Such a row is either the live composer or an echoed user
     message. Either one proves the TUI drew transcript or composer after the
     dialog text, so that dialog is no longer on screen as the current
     interaction. A real, live Codex dialog replaces the composer in the bottom
     pane: below its matched text there are only option rows (`› N.`), blank
     rows and the footer. Every measured live fixture has this shape
     (`CODEX_PERMISSION_RAW`, `_WITH_RUNNING_RAW`, `CODEX_QUESTION_RAW`,
     `CODEX_UPDATE_PROMPT_RAW`, `CODEX_EXEC_APPROVAL_*`).
   - Mechanics:
     - Give `_ordered_state` an optional
       `dialog_is_historical(plain, match) -> bool` parameter. The default is
       `None`, so the behaviour for claude/opencode stays byte-identical.
     - In the negative half, iterate `pattern.regex.finditer(plain)`. Return
       `SHADOW_DIALOG` on the first match that is **not** historical. A pane
       with a historical update dialog AND a live permission dialog therefore
       still reads `dialog`.
     - `_codex_state` passes a predicate built from the two codex regexes. It
       computes the match's end line, then scans the following lines.
     - `_composer_state` threads it through. Its signature gains a keyword
       argument with a default, and the existing positional/keyword callers
       (negative-control tests) keep working.
   - Scope note in a comment: Claude Code is also inline (alt=0, with history),
     but no retained-dialog state has been measured for it, so it is not
     changed here. OpenCode's composer is a box, so the glyph-row rule does not
     transfer.
   - The followed-pane classifier (`prompt_patterns` bottom window,
     `skip_trailing_blank_rows`) is not touched. t1522 measured that it already
     clears on dismissal.

5. **Tests for step 4** (`tests/test_review_loop.py`, beside
   `CodexShadowReadinessTests` / `CodexDetectorNegativeControlTests`):
   - The 0.160 measured fixture (or the composed `UPDATE_PROMPT + AT_REST` one)
     gives `ready`, and `shadow_prompt_ready(..., True)` gives `True`.
   - Historical update + typed composer gives `busy`, not `dialog`. The typed
     text still blocks injection.
   - Historical update + live `CODEX_PERMISSION_RAW` / `CODEX_QUESTION_RAW` at
     the bottom gives `dialog`. Real dialogs are preserved.
   - Regression matrix: every existing codex fixture keeps its current verdict
     (dialog×6, ready×3, busy×3, working×1, as listed during planning).
   - Negative control: with the predicate forced to `lambda *_: False`, the
     dismissed fixture reads `dialog` again. This proves the new test detects
     the bug.
   - **Recovery through the latch** (`tests/test_minimonitor_concern_action.py`,
     reusing the existing `_apply_shadow_settle_latch` helper at ~L2322 and the
     `_loop_now` clock seam):
     - feed the live update-dialog capture (latch armed);
     - then feed the dismissed capture repeatedly while the clock advances past
       `SHADOW_SETTLE_SECONDS`;
     - assert that readiness becomes `True` after the deadline and stays `False`
       before it.
     This pins the claim that the automatic recheck recovers.

6. **Comment/doc wording fixes**
   - `monitor/monitor_core.py` `capture_raw_tail` docstring: replace the
     "Every supported agent CLI runs on the alternate screen" sentence. On an
     alternate-screen pane there is no scrollback and the capture is the whole
     visible pane. On an inline pane (Claude Code, and Codex shadows since t1900)
     it is up to `lines` history rows **plus** the whole visible pane. In both
     cases it reaches the bottom of the visible pane, never just `lines` rows.
     Keep the two "consequences" paragraphs.
   - `lib/pane_state_probe.py` `_CAPTURE_LINES` comment: the same correction in
     one or two lines.
   - `.claude/skills/aitask-shadow/concern-format.md` "Capture-window contract":
     add a bullet. A capture depth only reaches older rows if the shadow pane
     keeps scrollback. An alternate-screen pane has `history_size=0`, so any depth
     returns the visible rows only. Codex shadows are therefore launched inline
     (`-c tui.alternate_screen=never`, t1900), and their capture window is the
     pane's history plus the visible rows.
   - `aidocs/framework/shadow_agent.md`:
     - In "Spawn path and binding", add a short paragraph on the Codex shadow
       launch mode (why, scope = shadow only, not carried by the resume arm
       because shadows are never frozen).
     - In "Recipe: measuring a new agent's readiness surfaces", fix the
       "`-S -15` is not a 15-line window" paragraph. Not every agent runs on the
       alternate screen: on an inline pane the capture is up to 15 history rows
       plus the visible pane.
     - In "Review-loop automation", add a short "historical dialog text"
       paragraph. It states the step-4 rule, why it exists (inline scrollback
       keeps dismissed dialog rows, and the HOLD did not self-recover because
       the latch needs READY), its codex-only scope, and the Claude non-coverage
       note.
   - Run `./.aitask-scripts/aitask_skill_verify.sh`, because concern-format.md
     lives in a skill directory.

7. **Step 9 (Post-Implementation)**: current-branch workflow. Commit code as
   `bug: … (t1900)`, then the plan via `aitask_task_commit.sh`, then archive.

### Post-phase (risk mitigations)

- **live_inline_probe**: launch the real `invoke shadow` command for a codex agent
  in an isolated tmux socket. Take the argv from
  `aitask_codeagent.sh --agent-string codex/<model> --dry-run invoke shadow %0`.
  Confirm `#{alternate_on}`=0 and that `#{history_size}` grows, then kill the
  socket. Do not let it submit a prompt to the model: it only needs to boot, so
  kill it within seconds. If the composer auto-submits the `$aitask-shadow`
  prompt, kill the pane at once.

## Verification

- `bash tests/test_codeagent.sh` passes, including the new Test 11f.
- `shellcheck .aitask-scripts/aitask_codeagent.sh` is clean.
- `bash tests/test_skill_render_aitask_shadow.sh` and
  `./.aitask-scripts/aitask_skill_verify.sh` pass.
- The new and existing review-loop tests pass: `tests/test_review_loop.py` and
  `tests/test_minimonitor_concern_action.py`, plus the full Python suite via
  `bash tests/run_all_python_tests.sh`. Read only the last-line verdict.
- Live (user / manual-verification follow-up): the task's three live checks.
  - alt=0 with a growing history;
  - after a block taller than the pane, `c` offers the full concern list;
  - copy-mode scrolling does not change the list.
  Plus a fourth: an armed review loop on an inline Codex shadow that showed (and
  dismissed) a startup dialog still auto-rechecks.

## Risk

### Code-health risk: medium
- Step 4 narrows the review loop's dialog veto, which is a safety check: a
  false "not a dialog" lets the loop type a prompt plus Enter into a live
  dialog. The rule is confined to codex. It only drops a match when a
  non-option `›` row sits below it, which no measured live dialog has. Every
  existing dialog fixture is pinned by the regression matrix, plus a
  mixed historical+live case, plus a negative control. · severity: medium ·
  → mitigation: covered in-plan by step 5 (fixture matrix + negative control)
- The `review_loop` / `_composer_state` signature changes could break the
  negative-control tests that call `_composer_state` directly. The new
  parameter is keyword-only with a `None` default. · severity: low ·
  → mitigation: covered in-plan by step 5 (existing tests run unchanged)

### Goal-achievement risk: low
- Inline mode on 0.160 is measured to keep history, but it has not been measured
  with a real plan-review block. Codex's inline history insertion could render
  the block differently than the 0.154 renderer did (wrapping or chrome
  interleaving). · severity: low · → mitigation: inline post-phase live_inline_probe

### Planned mitigations
- timing: post-phase | name: live_inline_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement (inline mode unmeasured through the real launcher) | desc: Boot the real `invoke shadow` codex argv in an isolated tmux socket; assert alternate_on=0 and growing history_size

## Final Implementation Notes
- **Actual work done:**
  - `aitask_codeagent.sh`: added `CODEX_SHADOW_OVERRIDES=(-c tui.alternate_screen=never)`. It is appended after the model flag in the Codex skill-composer arm, for `operation == shadow` only.
  - `review_loop.py`: added `_codex_dialog_is_historical`, wired through `_ordered_state` / `_composer_state` as a keyword argument that defaults to `None`, so Claude and OpenCode are byte-identical.
  - Two measured 0.160 inline fixtures.
  - Tests: Test 11f (launcher); `CodexHistoricalDialogTests` (6 tests, including a regression matrix over all 14 codex fixtures and negative controls); an end-to-end settle-latch recovery test with a negative control.
  - Wording fixes in `capture_raw_tail`, `pane_state_probe._CAPTURE_LINES`, `concern-format.md` and `shadow_agent.md` (spawn-path paragraph, historical-dialog paragraph, `-S -15` recipe).
- **Deviations from plan:**
  - The step-3 measurement found that 0.160 rewords the update dialog's hint to `enter continue · esc skip`. On 0.160 the dismissed capture therefore already read `ready`, because no pattern matches the retained rows.
  - The rule was kept anyway, as planned. Pre-0.160 inline builds still match, and `test_a_pattern_for_the_0160_wording_would_not_wedge_it` pins that a future pattern for the new wording cannot reintroduce the hang.
  - live_inline_probe dropped only the trailing composer prompt from the real dry-run argv, so no model turn ran. A local `/status` grew the history from 10 to 15 with alternate_on=0.
- **Issues encountered:**
  - A mise install never shows the 3-option update dialog. It was forced through an isolated `CODEX_HOME`, with `version.json` claiming 0.161.0 and `CODEX_MANAGED_BY_NPM=1`.
  - The dismissed rows stayed in the `-S -15` window (history_size 3→13).
- **Key decisions:**
  - Use the `-c` config form over `--no-alt-screen`, so no version gate is needed.
  - The historical-dialog rule is codex-only, with Claude left unmeasured.
  - The resume arm is unchanged, because shadows are excluded from discovery and so are never frozen.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/prompt_patterns.py:290-293` — `codex_update_prompt` matches only the pre-0.160 wording (`Press enter to continue`). codex-cli 0.160.0 renders `enter continue · esc skip`, so the startup update dialog is no longer pattern-detected on followed panes. The review loop still classifies it as `dialog` structurally, through the option row.

## Post-phase (risk mitigations) — outcome
- live_inline_probe: done. The real `invoke shadow` codex argv booted inline (alternate_on=0, history 10→15).
