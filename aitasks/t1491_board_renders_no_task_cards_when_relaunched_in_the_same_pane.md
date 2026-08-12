---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [tui, board]
anchor: 1449
followup_kind: upstream_defect
created_at: 2026-08-12 09:37
updated_at: 2026-08-12 09:37
---

## Problem

Relaunching `ait board` in the same shell / tmux pane after quitting it with `q`
renders the column headers with **correct task counts** but **zero task cards** —
every column body shows `(empty)`.

The first launch in a fresh shell always renders correctly. Since the header
counts are right, task loading and column assignment are working; only the card
widgets fail to appear. This looks like a card-mount / teardown-state defect
(stale app or widget state surviving the first app's exit within the process's
shell session), not a data problem.

Found incidentally while running the t1490 manual-verification checklist for
t1486. It is **unrelated to t1486's markup change** — the pre-t1486 board fails
differently (a hard `MarkupError` crash), and the empty-card behaviour reproduces
on the fixed code.

## Reproduction (3/3, three independent tmux sessions)

Against an isolated fixture project (copy of `ait` + `.aitask-scripts/` + a
synthetic `aitasks/` with 8 tasks split 6 / 2 across the `now` / `next` columns):

```
tmux -L <sock> new-session -d -s b -x 200 -y 50 -c <fixture>
tmux -L <sock> send-keys -t b "./ait board" Enter     # renders all 8 cards  ✔
tmux -L <sock> send-keys -t b q                        # quit
tmux -L <sock> send-keys -t b "./ait board" Enter     # headers Now (6) / Next (2), NO cards  ✘
```

## Observations

- Reproduced 3/3 across three separate tmux sessions on the same fixture.
- **Control:** a first launch in a brand-new tmux session on the very same
  fixture renders all cards correctly — so it is the relaunch, not the data.
- A terminal resize (`resize-window`) does **not** repair the render.
- No output on stdout or stderr; no traceback, no warning.

## Acceptance criteria

- [ ] Root-cause why the second in-shell launch mounts no task cards while the
      column headers still report the correct counts.
- [ ] Fix so a relaunch in the same shell / pane renders identically to a first
      launch.
- [ ] Add a regression pin that actually exercises the relaunch path (a live
      tmux fixture that launches, quits, and relaunches in the same pane, then
      asserts card presence — a single-launch test cannot fail on this bug).

## References

- Found during t1490 (manual verification of t1486).
- Full evidence: `aiplans/p1490_manual_verification_auto.md`, "Upstream defects
  identified".
