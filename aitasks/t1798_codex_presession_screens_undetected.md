---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitor, codex]
gates: [risk_evaluated]
anchor: 1159
followup_kind: upstream_defect
created_at: 2026-09-14 13:40
updated_at: 2026-09-14 13:40
---

## Origin

Spawned from t1522 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py:676 — capture_raw_tail's docstring states every supported agent CLI runs on the alternate screen with no scrollback, so the capture is the whole visible pane; Codex's pre-TUI screens (update prompt, sign-in onboarding, directory-trust) were measured at alternate_on=0 with scrollback, so that premise does not hold for them`
- `.aitask-scripts/monitor/prompt_patterns.py:217 — Codex's sign-in onboarding and directory-trust screens are awaiting-input screens (same "press enter to continue" hint over different options, top-aligned pre-TUI) that no pattern matches, so a followed Codex pane parked on either reads idle`

## Diagnostic context

Measured live during t1522 on codex-cli 0.154.0 (npm-managed via
`CODEX_MANAGED_BY_NPM=1`), on a private tmux socket, captured with the
monitor's own `capture-pane -p -e -S -200` args and classified through
`TmuxMonitor._finalize_capture`:

- The update-available prompt, the sign-in onboarding screen (reached with no
  auth) and the directory-trust screen (reached with a dummy API key in a
  throwaway `CODEX_HOME`) are all **inline pre-TUI screens** (`alternate_on=0`,
  `history_size` 3-4) rendered **top-aligned**, with a run of blank rows below
  their bottom hint (14 / 20 / 40 rows at 80x24 / 120x30 / 120x50 for the
  update prompt).
- t1522 made the update prompt detectable (`codex_update_prompt`) via the new
  per-pattern `PromptPattern.skip_trailing_blank_rows` opt-in, which matches a
  pattern against the last 6 rows after dropping trailing blank rows. A global
  trim was rejected: it breaks Claude's kind-by-pane-height contract.
- The sign-in and directory-trust screens both end with the same bottom hint
  over different options, and report **no kind** — a followed Codex pane
  blocked on either reads idle. They are also what Codex advances to after the
  update prompt is dismissed, so their trimmed windows were observed directly.
- `capture_raw_tail`'s docstring premise (every agent runs on the alternate
  screen; the capture is the whole visible pane) is therefore false for these
  screens.

t1522's archived plan (`p1522_codex_update_prompt_not_flagged_as_awaiting_input.md`)
records the probe method and the full probe script (Appendix A), which can be
adapted to capture these two screens. Describe the screens in prose only —
never paste their option blocks into a task, plan or doc (rule 3 of
`aidocs/framework/monitor_idle_and_prompt_detection.md`).

## Suggested fix

Scope the `capture_raw_tail` docstring's alternate-screen claim to the agents'
main TUIs and name the pre-TUI exception. Add `codex` patterns for the sign-in
and directory-trust screens using `skip_trailing_blank_rows`, each anchored on
that screen's last option row plus the hint (measure live first), with negative
controls proving neither claims `codex_update_prompt` and vice versa, and a
live check that each kind clears when the screen is dismissed.
