---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [codexcli, codeagent]
gates: [risk_evaluated]
anchor: 1171
created_at: 2026-07-20 12:20
updated_at: 2026-07-20 12:20
---

## Origin

Risk-mitigation ("after") follow-up for t1171, created at Step 8d after
implementation landed.

## Risk addressed

- addresses: goal-achievement residual + no-CI-coverage
- `Residual: the behavior this task exists to restore (Codex reaching default mode *and* the step-2 render succeeding) is not provable by dry-run tests · severity: low`
- `Shell tests are not run by CI, so a regression here is caught only by manual verification · severity: low`

## Goal

t1171 removed the `/plan` injection from Codex skill launches. Its automated
verification asserts the **command shape** — every operation on both dry-run
surfaces emits a plain `codex -m <model> "<prompt>"` with no helper and no
`/plan` token. That is necessary but not sufficient: it cannot show that Codex
actually lands in default mode at runtime, nor that the behavior the change
exists to restore (dynamic skill rendering) now works.

`.github/workflows/` contains zero references to `tests/`, so the shell tests
never run in CI. This live check is the only thing standing between a broken
Codex launch path and a silent regression.

Verify by hand, in a real tmux session:

1. Run `ait codeagent invoke pick <N>` with a `codex/...` agent string.
   Confirm the Codex TUI starts in **default mode** — the composer shows no
   plan-mode indicator and the session is not read-only.
2. Confirm the skill stub's **step 2** (`aitask_skill_render.sh … --agent codex`)
   completes and actually writes its rendered variant to
   `.agents/skills/aitask-pick-<profile>-codex-/SKILL.md`. This is the failure
   plan mode caused (the render path calls `lib/skill_template.py` `_atomic_write()`,
   which needs write access) and is the core reason t1171 exists. Check the
   file's mtime to confirm it was written by this run, not left over.
3. Confirm the stub's **step 3** then reads that rendered path successfully and
   the skill proceeds.
4. Confirm an interactive checkpoint (task confirmation or plan approval) still
   surfaces via `request_user_input` in default mode — the
   `default_mode_request_user_input` flag in `.codex/config.toml` is what makes
   removing plan mode safe, so this is the load-bearing assumption.
5. Repeat step 1 for `ait skillrun <skill> --agent-string codex/<model>` (the
   second launch surface) outside `--dry-run`.
6. Run `ait setup` in a clean environment and confirm it completes with
   `pexpect` no longer in the dependency list (t1171 removed it; the plan-mode
   PTY helper was its only consumer).

Record the outcome. If any step fails, the t1171 change needs revisiting —
reference `aiplans/archived/` for its plan.
