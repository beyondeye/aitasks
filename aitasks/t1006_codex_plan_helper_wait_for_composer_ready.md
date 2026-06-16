---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [codex, codeagent]
created_at: 2026-06-16 10:44
updated_at: 2026-06-16 10:44
---

## Summary

`ait board` cannot launch the `aitask-pick` (or any forced-plan-mode) skill via
Codex: the spawned Codex window exits/"crashes" ~2-3s after launch without ever
running the skill. Root-caused to the Codex plan-mode launch helper sending
keystrokes blindly before Codex's composer is ready.

## Repro

1. From `ait board`, open a task's detail dialog and choose "Pick" with an agent
   string of `codex/gpt5_5` (any codex model).
2. The agent-command dialog shows:
   ```
   python3 <abs>/.aitask-scripts/aitask_codex_plan_invoke.py --prompt \$aitask-pick\ 5 -- codex -m gpt-5.5
   ```
3. The board launches it in a tmux window. Codex appears for ~2-3s then exits;
   the `aitask-pick` skill never runs.
4. Launching `codex` directly from the CLI works normally.

## Root cause

`aitask_codex_plan_invoke.py` (in `.aitask-scripts/`, the framework source of
truth) does a **blind fixed sleep** then types the prompt and hands off:

```python
time.sleep(max(args.startup_delay, 0))   # default 2s (AITASK_CODEX_PLAN_STARTUP_DELAY)
_sync_child_size(child)
child.sendline(f"/plan {args.prompt}")    # typed regardless of what's on screen
child.interact()
```

It never `expect()`s a "composer ready" marker. Codex (codex-cli 0.140.0) shows
**pre-composer startup gates** before the composer exists — confirmed via a PTY
repro, the very first screen is the directory-trust gate:

```
You are in /home/ddt/Work/aitasks_go
Do you trust the contents of this directory? ...
  1. Yes, continue
  2. No, quit
Press enter to continue
```

After the 2s sleep the helper types `/plan <prompt>` + Enter into this trust
gate (not the composer). The Enter/stray text dismisses or quits the gate, so
the prompt never reaches a live session — manifesting as "exits/crashes after
2-3s without running codex." The same fragility applies to the auto-update
progress screen and onboarding screens.

## Why direct CLI works but the board does not

Codex trust is per-exact-directory in `~/.codex/config.toml`
(`[projects."<path>"] trust_level = "trusted"`), NOT inherited from parent dirs.
On this machine `/home/ddt/Work/aitasks` is trusted but
`/home/ddt/Work/aitasks_go` is NOT. Manual `codex` launches happen in the
trusted original repo (composer opens immediately), while the board launches
codex with cwd = the project root (`TmuxLaunchConfig.cwd = self._project_root`),
i.e. the untrusted `aitasks_go` → trust gate appears → blind keystrokes break.

## Fix direction

1. **Primary (robust):** Replace the blind `startup-delay` sleep with
   `child.expect(...)` on a Codex composer-ready marker before `sendline`, with a
   generous timeout that tolerates auto-update/onboarding. Keep `startup-delay`
   only as a fallback/diagnostic. This makes the launch robust against ALL
   pre-composer gates (trust, update, onboarding), not just the trust prompt.
2. **Optional hardening:** Pre-trust the launch cwd so the trust gate never
   appears for scripted launches — e.g. pass a Codex config override
   `-c 'projects."<cwd>".trust_level="trusted"'` (Codex supports `-c key=value`),
   or ensure the launch cwd is a trusted project. Decide whether auto-trusting a
   scripted launch dir is acceptable policy.
3. **Immediate workaround (no code, for the reporter):** add
   `[projects."/home/ddt/Work/aitasks_go"] trust_level = "trusted"` to
   `~/.codex/config.toml`.

## Notes / answered side-questions

- **Why the helper is invoked by absolute path:** `aitask_codeagent.sh` builds
  `"$SCRIPT_DIR/aitask_codex_plan_invoke.py"` (and `aitask_skillrun.sh` likewise)
  because the command is re-executed by tmux in a fresh window/shell whose cwd
  may differ from where it was built — a relative path would not resolve.
  Alternatives (an `ait`-subcommand wrapper or a `python -m` module) are possible
  but the absolute path is the robust choice for cross-cwd re-exec. NOT the bug.
- Affected callsites: `aitask_codeagent.sh` (~L468) and `aitask_skillrun.sh`
  (~L244) both route forced-plan-mode codex skills through this helper
  (policy in `lib/codex_plan_policy.sh`).
- Prior related (archived) work: t866 investigate_codex_forced_plan_mode,
  t871 follow-up, t870 remove_orphaned_codex_interactive_prereqs.

## Manual verification (inline)

- [ ] From `ait board`, Pick a task with `codex/<model>` in an UNTRUSTED dir and
      confirm Codex reaches the composer and the `aitask-pick` skill prompt is
      submitted (no exit-after-2s).
- [ ] Confirm the fix also survives a Codex auto-update on launch.
- [ ] Confirm a normal (already-trusted dir) codex pick launch still works.
