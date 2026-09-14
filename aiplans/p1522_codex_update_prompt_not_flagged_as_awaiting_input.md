---
Task: t1522_codex_update_prompt_not_flagged_as_awaiting_input.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1522 — Codex update-available prompt not flagged as awaiting input

## Context

`ait monitor` / `ait minimonitor` do not flag a followed Codex pane parked on the
startup **update-available prompt** as awaiting input. The task asks for a
bottom-anchored `codex` prompt pattern plus unit tests.

**Measured during planning (live, codex-cli 0.154.0, npm-managed via
`CODEX_MANAGED_BY_NPM=1`, private tmux socket, captured with the monitor's own
`capture-pane -p -e -S -200`):** the dialog is an **inline pre-TUI screen
(`alternate_on=0`) rendered TOP-aligned**. Its bottom hint line sits at row
-15 / -21 / -41 at 80x24 / 120x30 / 120x50, followed by 14 / 20 / 40 blank rows.
`_prompt_detection_text` (`monitor_core.py:186`) takes the last 6 lines with no
blank-trimming, so the detection window is **entirely blank** on every real pane.
A pattern alone would pass its unit test and be dead in production — the same
failure t1540 found for `claude_trust_folder`. The committed
`CODEX_UPDATE_PROMPT_RAW` fixture looks bottom-anchored only because its capture
was trimmed of trailing blank rows. Wording and row structure are identical to
the 0.146.0 fixture (header, release-notes line, three numbered options with the
`›` glyph on the selected one, blank row, hint).

**Global trim rejected, by measurement:** patching the shared window to drop
trailing blank rows makes 10 currently-green tests fail (8 in
`test_review_loop.py` — `ClaudePermissionBoundaryTests` geometry + t1557
`TypedAmendCannotFlipTheReportedKindTests`; 2 in
`test_minimonitor_concern_smoke.py`). Claude's dialogs carry trailing blank
rows, so a global trim would change which kind production reports for Claude.

**Approach:** a per-pattern opt-in. `PromptPattern` gains a defaulted
`skip_trailing_blank_rows: bool = False`; `classify_content` matches a pattern
that sets it against the last 6 rows *after dropping trailing blank rows*. Every
existing pattern keeps the byte-identical shared window. On the live captures
that trimmed window is exactly the measured dialog tail (blank, three option
rows, blank, hint).

Working on the current branch (profile `fast`).

## Implementation steps

1. **`.aitask-scripts/monitor/prompt_patterns.py`**
   - `PromptPattern`: add `skip_trailing_blank_rows: bool = False` with a comment:
     pre-TUI inline screens render top-aligned, so their bottom element sits
     above blank rows; per-pattern because a global trim was measured to change
     Claude's kind selection (t1522). All 4 existing constructions pass two
     positional args, so the default is compatible (`tests/test_pane_state_probe.py:120,124`,
     `tests/test_review_loop.py:1348,1374`).
   - Append to the `codex` group:
     ```python
     PromptPattern("codex_update_prompt",
                   re.compile(r"(?m)^[ \t]*(?:›[ \t]*)?3\. Skip until next version[ \t]*\n"
                              r"[ \t]*\n"
                              r"[ \t]*Press enter to continue[ \t]*$"),
                   skip_trailing_blank_rows=True),
     ```
     Comment block, matching the file's style: measured distances (above); why it
     anchors on the **last option row + hint** — option 1's label embeds the
     install command, which varies by install method, while option 3 is stable
     and is the row adjacent to the hint; a bare hint is generic prose and is
     shared with the Codex sign-in onboarding screen, whose last option differs
     (scope control); both rows must hold nothing but their label, with exactly
     the measured one blank row between them; `›` is the only accepted marker (it
     moves with selection); KNOWN LIMIT: a verbatim reproduction is
     indistinguishable (rule 3). Also state which consumer gains coverage: the
     followed-pane window via the opt-in; the review loop already classified this
     pane `SHADOW_DIALOG` structurally and now also matches it in its whole-tail
     negative half (same verdict).

2. **`.aitask-scripts/monitor/monitor_core.py`**
   - `_prompt_detection_text(s, *, skip_trailing_blank_rows=False)`: the default
     path stays byte-identical (including `return s` when there are ≤6 lines);
     the opt-in pops trailing whitespace-only lines, then returns
     `"\n".join(lines[-_PROMPT_DETECTION_TAIL_LINES:])`.
   - `classify_content`: compute the trimmed text lazily, only once a pattern
     with the flag is reached; each pattern searches its own window;
     first-match-wins order unchanged. Update the docstring. `pane_state_probe`
     (sync sweep) and the applink pusher inherit this through `_classify_one` /
     the snapshot, with no change of their own. `awaiting_input_kind` is an
     open wire string, so no protocol bump.

3. **`.aitask-scripts/monitor/review_loop.py`** — add
   `("codex", "codex_update_prompt")` to `DELIBERATELY_UNANCHORED_KINDS`. Reason:
   a pre-TUI startup gate shown before the session has done any work; only one
   selection state has been captured, so no selection-stable boundary is
   measured, and UNKNOWN (no recheck) is the conservative answer (t1522).
   Without an entry, `test_every_armed_agent_kind_resolves` fails.

4. **`tests/test_prompt_detection.py`** (script-style checks, registered in `main()`):
   - `_check_codex_update_prompt_detected`: the stripped fixture on a `codex`
     pane; the fixture followed by 14 / 20 / 40 blank rows (the three measured
     geometries); option 2 or option 3 selected (the `›` moved); and an
     unresolved `node` pane (Codex's npm launcher) — all report
     `codex_update_prompt`. Bodies are derived from `fx.CODEX_UPDATE_PROMPT_RAW`
     rather than retyped (`import review_loop_fixtures as fx`, the idiom
     `tests/test_minimonitor_concern_action.py:1780` uses; works under both the
     script runner and pytest).
   - `_check_update_prompt_trim_is_load_bearing_and_per_pattern`: the same
     pattern copied via `dataclasses.replace(..., skip_trailing_blank_rows=False)`
     does **not** match the realistic tail, which proves the opt-in is needed.
     And a Claude help-bar body followed by ≥6 blank rows still reports no kind,
     which pins that the trim did not leak into the shared window.
   - `_check_codex_update_prompt_negative_controls` (codex pane, kind must not be
     `codex_update_prompt`): hint alone on its own line; hint inline in prose;
     bulleted hint; blockquoted option + hint; the option label quoted in prose
     above the hint; option row with trailing commentary; option row and hint
     with no blank row, and with two blank rows; a synthetic sign-in onboarding
     tail (same hint, different last option); the update prompt followed by >6
     lines of later output (scrollback); the permission footer still reports
     `codex_permission`.
   - `_check_codex_update_prompt_known_false_positive`: a verbatim reproduction
     still matches (pinned, like `_check_trust_pattern_known_false_positive`).
   - Extend `_check_cross_agent_negative_control` with `claude` / `opencode`
     panes showing the update-prompt body. Extend the characterization matrix
     body list and flips (`claude`→"", `opencode`→""). Add the name to
     `_check_all_patterns_flattens_per_agent_groups`, and add a docstring item.

5. **`tests/test_review_loop.py`**
   - Replace `test_the_unpatterned_update_prompt_is_a_dialog_not_typed_text` with
     `test_the_update_prompt_is_a_dialog_with_or_without_its_pattern`: exactly
     `{codex_update_prompt}` among the codex patterns matches the fixture, and
     `_codex_state` is `SHADOW_DIALOG`; with the codex list emptied (try/finally)
     it is **still** `SHADOW_DIALOG`, so the structural proof t1509 needed is
     kept, not lost.
   - `ConservativeDefaultSurvivesTests`: add
     `test_codex_update_prompt_is_unanchored_and_unknown` (mirrors the palette
     test; its reason contains `t1522`).

6. **`tests/test_minimonitor_concern_action.py`** — rename
   `test_the_unpatterned_update_prompt_arms_the_latch_too` →
   `test_the_update_prompt_arms_the_latch_too`, and fix its docstring (the latch
   arms from the verdict, and the verdict is structural with or without the
   pattern). The assertions are unchanged.

7. **`tests/review_loop_fixtures.py`** — update the provenance paragraph: the
   pattern now matches `CODEX_UPDATE_PROMPT_RAW`; the structural exclusion is
   still pinned with the pattern list disabled; the fixture was trimmed of
   trailing blank rows, and live the dialog is top-aligned (t1522 distances), so
   it does not represent followed-pane window geometry.

8. **`tests/test_workflow_phase_prompt_drift.sh`** — add `codex_update_prompt` to
   the `generic` leak list (a startup gate carries no workflow phase).

9. **`aidocs/framework/monitor_idle_and_prompt_detection.md`** — fix the stale
   codex inventory (it lists only `codex_yes_proceed`; it should list
   `codex_question`, `codex_permission`, `codex_yes_proceed`,
   `codex_update_prompt`). Under "Bottom-anchor it", add the pre-TUI
   top-aligned case and the `skip_trailing_blank_rows` opt-in, with why it is
   per-pattern (the measured global-trim regression), and note that it is the
   tool for `claude_trust_folder`'s geometry half too (its wording half is still
   separate). Describe the dialog in prose only, never as an option block.

### Post-phase (risk mitigations)

1. [live_update_prompt_probe] After steps 1–9 pass their tests, run a scratchpad
   probe on a **private** tmux socket (`tmux -L t1522verify`; kill only that
   server): a throwaway `CODEX_HOME` whose `version.json` reports
   `latest_version` newer than the installed codex with a current
   `last_checked_at`, `CODEX_MANAGED_BY_NPM=1`, no auth, and **never press
   Enter** (option 1 would run an install). At 80x24, 120x30 and 120x50:
   capture with `TmuxMonitor._capture_args` (the production args), feed the
   capture to `TmuxMonitor._finalize_capture` on a `PaneCategory.AGENT` pane
   with `current_command="codex"`, and assert
   `awaiting_input_kind == "codex_update_prompt"`; then send `Down` once and
   twice (selection only) and re-assert — 9 captures in total. Negative
   control: the same captures with the pattern's opt-in disabled report no
   kind.

   **Dismissal transition (the kind must CLEAR, not only fire).** The opt-in
   discards an arbitrary run of blank rows, so a post-dismissal screen that
   leaves the old option and hint rows as the last non-blank rows would hold the
   pane in awaiting-input state. Prove it does not:
   - **Safe dismissal only.** Move the selection with `Down` to option 2 (Skip)
     or option 3 (Skip until next version). **Before sending Enter, capture and
     assert the `›` row is NOT option 1**; if that guard fails, send nothing,
     kill the private session and abort. Option 3 writes `dismissed_version`, so
     recreate the throwaway `CODEX_HOME` (fresh `version.json`) for every rep.
   - **Sampling:** 0.25 s for 5 s after Enter, each sample through
     `_capture_args` → `_finalize_capture`, recording `awaiting_input_kind`,
     `#{alternate_on}`, and the row shape of the trimmed window.
   - **Ship criterion (blocking) — unauthenticated path, 120x30, two reps: one
     per safe dismissal action (option 2, option 3).** With no auth, Codex
     advances to its inline sign-in onboarding screen (same hint, different
     options). Pre-registered pass rule: within the window the kind stops being
     `codex_update_prompt` and **never reports it again**, and the
     post-dismissal sign-in captures report no `codex_update_prompt`; record
     time-to-clear per rep. **Stop rule:** if either rep keeps reporting
     `codex_update_prompt` after the dialog was dismissed, the opt-in is
     unsound as designed — do **not** ship; record the offending capture's row
     shape in the plan and return to planning.
   - **Best-effort (non-blocking, one time-boxed attempt):** (b) a throwaway
     home holding a **dummy** API key written by
     `printf 'sk-dummy' | CODEX_HOME=<tmp> codex login --with-api-key` (no real
     credential is ever copied; never substitute the user's real `~/.codex`),
     dismissed the same guarded way, to observe the advance towards the main
     TUI; plus one 80x24 repeat of the ship-criterion rep. Run each once; if a
     run is unreliable or cannot get past the dialog without network, record
     that as a measured limit and offer the authenticated-path check as a
     follow-up at Step 8c. A best-effort result never blocks shipping — **but**
     a best-effort run that *does* complete and shows the kind failing to clear
     triggers the stop rule like the ship criterion.

   Record every result (distances, kinds, time-to-clear, `alternate_on`) in
   Final Implementation Notes. Delete the throwaway `CODEX_HOME`s afterwards.

## Verification

- `python3 tests/test_prompt_detection.py`
- `bash tests/test_workflow_phase_prompt_drift.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the final
  `PYTHON SUITE:` line (with `set -o pipefail` if piped).
- `shellcheck` is not applicable (no `.aitask-scripts/*.sh` edits).
- Live end-to-end check: Post-phase step 1 `[live_update_prompt_probe]`.

Post-implementation: Step 9 (Post-Implementation) — current-branch mode, so there
is no merge; the build is verified per `verify_build`, then archival.

## Risk

### Code-health risk: low
- `classify_content` is the per-tick hot path shared by monitor, minimonitor, the sync-sweep holder probe (`lib/pane_state_probe.py`) and applink; a default path that is not byte-identical would silently shift existing kinds · severity: low · → mitigation: none — pinned by the existing characterization matrix, the t1540/t1557 geometry tests, the finalize-offload golden, and step 4's scope-guard check
- Rewriting t1509's premise test could weaken the structural-exclusion proof · severity: low · → mitigation: none — the rewrite asserts `SHADOW_DIALOG` with the codex pattern list disabled

### Goal-achievement risk: low
- The pattern is proven live only with option 1 selected; other selection states are covered by synthetic bodies only, and a future Codex release can change wording or geometry and leave the pattern dead while every unit test stays green (t1540's `claude_trust_folder` lesson) · severity: low (residual — addressed by inline post-phase live_update_prompt_probe for today's version and every selection state; future-release drift stays a documented limit) · → mitigation: inline post-phase live_update_prompt_probe
- Dismissal transition (raised in plan review): because the opt-in skips an arbitrary run of blank rows, a sparse or transient post-dismissal screen could leave the dismissed dialog's option and hint rows as the last non-blank rows and falsely hold the pane in awaiting-input state; no probe so far pressed Enter, so the clearing half was unproven · severity: low (residual — addressed by inline post-phase live_update_prompt_probe's guarded unauthenticated dismissal check, the blocking ship criterion with a pre-registered stop rule; the authenticated main-TUI advance is best-effort and, if unavailable, becomes a Step 8c follow-up) · → mitigation: inline post-phase live_update_prompt_probe
- The sync sweep's `--require-waiting` gate will now read a Codex holder parked on its update prompt as `waiting_codex_update_prompt` and may commit its files on its behalf · severity: low · → mitigation: none — the signal is truthful, and the gate's contract is "parked on a prompt"

### Planned mitigations
- timing: post-phase | name: live_update_prompt_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risks 1 and 2 (pattern proven live only in one selection state; dismissal transition unproven) | desc: Drive the real TmuxMonitor capture+classify path against a live Codex update prompt at three geometries and all three selection states, with an opt-in-disabled negative control, plus a guarded dismissal check (never Enter on option 1) — unauthenticated at 120x30 as the blocking ship criterion, authenticated-dummy-key and 80x24 as best-effort — asserting the kind clears and stays cleared
