---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [tmux]
anchor: 1705
followup_kind: risk_mitigation
created_at: 2026-09-18 08:07
updated_at: 2026-09-18 08:07
---

## Origin

Risk-mitigation ("after") follow-up for t1828, created at Step 8d after implementation landed.

## Risk addressed

> `spawn_session_detached --create-only` gains a new exit-44 refusal on the
> frozen-agent restore path (`agent_restore.py`), for configs that restored
> before. · severity: medium (residual — pinned by a stub-tmux test row this task
> adds; live confirmation deferred to the mitigation)

Addresses: the new exit-44 refusal on the frozen-agent restore path.

## Goal

Confirm against a **real tmux server** what t1828's suite only proves against a
stub. `tests/test_ide_session_override.sh` installs a fake `tmux` on `PATH` and
asserts on its call log; that pins the framework's own logic but says nothing
about how a real tmux behaves, and the refusal path it covers is one a user hits
during frozen-agent restore.

Everything below runs against a **scratch project**, never this repo.

## Verification Steps

- [ ] Create a scratch project: `mkdir -p /tmp/t1828chk/aitasks/metadata` and write
      `tmux:\n  default_session: a.b\n` to its `project_config.yaml`.
- [ ] Confirm tmux really does refuse the name, so the premise holds:
      `tmux new-session -d -s a.b` then `tmux has-session -t =a.b`. Record what
      happens — this is the behavior the whole task is predicated on.
- [ ] `cd /tmp/t1828chk && ait ide` — warns with the `illegal_tmux_name` sentinel
      and the "cannot address" wording, and attaches to `aitasks`, not `a.b`.
- [ ] `tmux ls` shows **no** session named `a.b` created by the framework.
- [ ] `bash .aitask-scripts/lib/tmux_bootstrap.sh --create-only /tmp/t1828chk`
      exits **44**, prints
      `BOOTSTRAP_FAILED:default_session_unreadable:illegal_tmux_name`, and creates
      nothing.
- [ ] Ensure mode — `bash .aitask-scripts/lib/tmux_bootstrap.sh /tmp/t1828chk` —
      exits 0 and creates `aitasks`.
- [ ] TUI switcher: open it with a stale entry for the scratch project and trigger
      the bootstrap; the notice reads "holds `.` or `:`, which tmux reads as target
      separators", not the "single-line plain or quoted value" or "not valid YAML"
      wording.
- [ ] Frozen-agent restore end-to-end: with the scratch project registered, attempt
      a restore and confirm it reports the refusal reason rather than producing an
      unreachable session.
- [ ] Control — change the scratch config to `default_session: my_proj-2` and
      confirm `ait ide` uses that name with no warning. This is what proves the
      refusal is narrow and the earlier steps were not just "everything fails".
- [ ] macOS only (t1828's `LC_ALL=C tr` fix, commit `41112cc71`): write an invalid
      UTF-8 byte on a comment line of the scratch config
      (`printf 'tmux:\n  default_session: ok\n# \377\n'`) and confirm the reader
      reports `encoding` rather than silently returning `ok`.
- [ ] Clean up: kill any sessions created and `rm -rf /tmp/t1828chk`.

## Notes

Read `.claude/skills/task-workflow-fast-/manual-verification.md` — this task
dispatches to the Pass/Fail/Skip/Defer checklist loop, not the plan+implement
flow. A failed check spawns its own follow-up under that follow-up's issue type;
this task records its outcome with an `ait:` commit.

Live-tmux work has an environment precondition worth checking first: run it from a
plain terminal, not from inside a tmux session, and check whether an `ait` socket
server is already alive before creating sessions.
