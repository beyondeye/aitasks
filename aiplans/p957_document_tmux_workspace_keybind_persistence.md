---
Task: t957_document_tmux_workspace_keybind_persistence.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t957 — Document tmux workspace keybind persistence

## Context

t943 hardened the framework's own tmux server-creation chokepoint
(`spawn_session_detached` → `ait_tmux_new_session_persistent` in
`.aitask-scripts/lib/terminal_compat.sh`): when `ait ide` (or a TUI-switcher
bootstrap) creates the shared tmux server, it now lands in a persistent
systemd-user service under `session.slice`, so it survives a Wayland
compositor restart / `app.slice` teardown.

That fix only covers **framework-created** servers. If a user starts the
`ait` tmux server from their **own** compositor keybind / autostart launcher
(e.g. an Omarchy/uwsm `tmux-spawn` keybind that runs `tmux new-session`
directly — the exact origin of the 2026-06-07 incident server), the server
inherits the transient `app.slice` scope and dies with the compositor,
taking every session inside it down at once.

Right now this gap is recorded only in a code comment in
`terminal_compat.sh` (the only Omarchy/uwsm mention anywhere in the repo).
There is **no** user-facing guidance. This task closes that documentation gap.

## Goal

Add a user-facing troubleshooting/docs note explaining that a self-launched
workspace server should be placed in a persistent slice
(`systemd-run --user --slice=session.slice -- tmux new-session …`) so it
survives the same teardown the framework already protects its own server
from, with an Omarchy/uwsm cross-reference callout.

## Approach

Add **one new section** to the existing terminal/tmux page —
`website/content/docs/installation/terminal-setup.md` — which already
documents `ait ide`, the shared single tmux server, and tmux session
lifecycle. This is the natural home; no new page is created (so no
`_index.md` page-list edit is needed).

Rejected homes:
- `installation/known-issues.md` — scoped to *code-agent* integration
  caveats, not environment/desktop lifecycle.
- `installation/linux.md` — package-install only.
- A new page — overkill for a single section; would need an `_index.md`
  bullet.

### File to modify

`website/content/docs/installation/terminal-setup.md`

Insert a new top-level section **between** the "One gotcha: `ait ide` is one
view of a shared session" section (ends ~line 70) and `## Minimal /
non-tmux workflow` (~line 72). Proposed section:

```markdown
## Surviving a compositor restart on Linux/Wayland

All `ait`-managed sessions for a project share **one** tmux server, so if that
server is torn down, every session inside it is lost at once. On Linux desktops
that launch graphical apps through transient systemd user scopes — most Wayland
compositors (Hyprland, Sway) and session managers such as uwsm — that can
happen when your graphical session restarts.

When you start the server with [`ait ide`](#recommended-workflow--ait-ide), the
framework already guards against this: it spawns the server inside a persistent
systemd-user service under `session.slice`, which survives a compositor restart,
an `app.slice` teardown, or a logout *of the graphical session*, and ends only
at full logout. No action is needed on your part.

The gap is a server you start **yourself** — for example from a compositor
keybind or autostart entry that runs `tmux new-session …` directly. That server
inherits your graphical session's transient `app.slice` scope; when the
compositor restarts (or that scope is otherwise torn down), the scope dies as a
unit and takes the tmux server — and all its sessions — with it.

To give a self-launched server the same survival guarantee, wrap the tmux
invocation in a persistent systemd-user service under `session.slice`:

```bash
systemd-run --user --slice=session.slice \
    --property=Type=forking --property=KillMode=none --collect \
    -- tmux new-session -d -s aitasks -c /path/to/your/project -n monitor 'ait monitor'
```

`--slice=session.slice` is the load-bearing flag — it moves the server out of
the transient `app.slice` scope into a unit that survives compositor /
`app.slice` teardown and ends only at full logout. `--property=Type=forking`
matches tmux's double-fork so systemd tracks the daemon, and
`--property=KillMode=none` keeps systemd from signalling the server when the
launching command returns (tmux owns its own lifecycle via `kill-server`). Run
it once, then attach as usual with `ait ide` or `tmux attach -t aitasks`.

> **Omarchy / uwsm users:** uwsm launches apps into `app.slice`, so a
> `tmux-spawn` keybind that runs `tmux` directly inherits that scope and dies
> with the compositor. Point the keybind at the `systemd-run --user
> --slice=session.slice` form above — or simply start your session with
> `ait ide`, which already does this — so the server persists across compositor
> restarts.
```

Notes on conventions:
- Current-state-only prose (no `t943` / version-history references in the doc
  body, per documentation conventions).
- The flags mirror the framework's own invocation in
  `terminal_compat.sh:168` (`--slice=session.slice`, `Type=forking`,
  `KillMode=none`, `--collect`); `--unit`/`--quiet` are dropped from the
  example for readability.
- The Omarchy/uwsm callout is the "cross-reference the omarchy guidance"
  requirement; it names a real public distro/session-manager (not the
  author's repos), consistent with the existing code comment.

## Verification

- `cd website && hugo build --gc --minify` (or `./serve.sh`) builds cleanly
  with no broken-anchor warnings; the new `#recommended-workflow--ait-ide`
  in-page link resolves (it targets the existing `## Recommended workflow —
  ait ide` heading).
- Visually confirm the new section renders between the gotcha section and the
  "Minimal / non-tmux workflow" section, and the nested ```bash fence renders
  as a code block.
- No `_index.md` or sidebar edit required (section added to an existing page,
  not a new page).

See **Step 9 (Post-Implementation)** of the task-workflow for cleanup,
archival, and merge.

## Risk

### Code-health risk: low
- None identified. Single additive section in one existing Markdown doc; no
  code, scripts, or templates touched; no behavior change.

### Goal-achievement risk: low
- None identified. The note directly delivers the task's requirement
  (persistent-slice guidance for a self-launched server + Omarchy/uwsm
  cross-reference); the systemd-run flags are copied from the framework's own
  validated invocation.

_Risk-Mitigation Follow-up (Part 1, design-in-planning) ran: no before/after
mitigation tasks proposed — both dimensions are `low` with no open risks._
