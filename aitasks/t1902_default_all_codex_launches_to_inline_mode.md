---
priority: medium
effort: low
depends: [1900]
issue_type: enhancement
status: Ready
labels: [codex, codeagent]
gates: [risk_evaluated]
anchor: 1892
created_at: 2026-10-06 10:29
updated_at: 2026-10-06 10:29
---

## Origin

User-requested follow-up to t1900, raised during its shadow review. t1900 adds
`-c tui.alternate_screen=never` only to Codex `invoke shadow` launches. The user
wants inline mode to be the default whenever the framework launches Codex.
This is a deliberate expansion of t1900's shadow-only scope.

## Goal

Make `-c tui.alternate_screen=never` a shared default for every supported Codex
launch through `ait codeagent`, including fresh skill launches, `batch-review`,
`raw`, and `raw --resume-session`. Keep launches of other agent types unchanged.
Inline mode preserves tmux scrollback for capture, review, and copy-mode use.

## Implementation guidance

- In `.aitask-scripts/aitask_codeagent.sh`, move the inline-mode setting into
  `CODEX_TUI_OVERRIDES` beside `tui.animations=false`, so all Codex command-builder
  arms receive it. Remove the redundant `CODEX_SHADOW_OVERRIDES` array and the
  shadow-only conditional. Preserve argument quoting, model selection, trailing
  skill prompts, passthrough arguments, and resume positional ordering.
- Audit framework Codex spawn/restore call sites for any launch path that bypasses
  these shared defaults. Prefer the existing command builder over duplicating
  the setting in additional launchers.
- Update `tests/test_codeagent.sh`: its t1900 negative assertions for non-shadow
  Codex operations and raw resume must become positive assertions. Keep checks
  that other agents do not receive Codex-specific settings and that prompts and
  passthrough arguments retain their positions.
- Update comments and `aidocs/framework/shadow_agent.md` plus the shadow skill's
  Capture-window contract to describe the broader default. Correct the claim
  that shadows can never be frozen: discovery exclusion covers Freeze-All, but
  direct `aitask_frozen.sh freeze <pane_id>` bypasses discovery. With the shared
  override, resumed Codex sessions should retain inline mode without needing a
  shadow-specific restoration exception.
- Check monitor consumers now that ordinary Codex panes retain history too:
  `monitor_core.capture_raw_tail`, `lib/pane_state_probe.py`, prompt detection,
  idle/freshness classification, and the review loop. Reuse t1900's historical
  dialog handling and fixtures where applicable; do not assume retained startup
  or answered-dialog text describes the current interaction.
- Retain the config-form override rather than unconditionally introducing
  `--no-alt-screen`: t1900 measured the config override on 0.160.0 and found it
  tolerated by older 0.153.4/0.156.1 builds.

## Acceptance criteria

1. Every supported Codex operation's generated argv includes
   `-c tui.alternate_screen=never`, including normal raw launch and raw resume.
2. Claude Code and OpenCode command construction is unchanged.
3. Launcher tests and relevant readiness/prompt-detection tests pass; shellcheck
   is clean. Verify skill rendering if shared skill documentation changes.
4. A representative non-shadow Codex launch runs with `alternate_on=0` and
   growing tmux history. A resumed Codex launch also retains inline mode.
5. Monitor readiness and awaiting-input detection reflect the current interaction
   after startup or answered dialogs move into history. Copy-mode scrolling does
   not alter captured content or freshness solely because the viewport moved.

Use prompt-free isolated startup probes where possible; distinguish startup
measurements from checks that need a real session or human interaction. Record
any unperformed live checks explicitly and carry them in a manual-verification
follow-up when needed.
