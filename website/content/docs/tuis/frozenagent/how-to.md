---
title: "How-To Guides"
linkTitle: "How-To"
weight: 20
description: "Reading, copying and reviving a frozen code agent"
maturity: [experimental]
depth: [intermediate]
---

## Read a frozen agent's summary

The pane a frozen agent left behind is already the viewer — you do not need to
launch anything. Move to that tmux window and the captured output is there, in
the place the agent's own output used to be.

1. Press **G** to jump to the bottom, where an agent's closing summary is.
2. If the colours look wrong or you want to copy plain text, press **r** to
   switch to the stripped view.
3. Press **m** to render the capture as Markdown when the agent's output was
   markdown to begin with — a plan, a report, a task list.

To find a frozen agent whose window you have lost, run `ait frozenagent` with no
arguments: it lists every frozen record on the machine, including ones from other
projects. Press **Enter** on a row to read it.

## Copy a spawned-task list out of a frozen transcript

This is the common case: the agent finished, spawned four follow-up tasks, and
you want their numbers.

1. Press **/**, type part of the line you are looking for (`Created task`, for
   example), and press **Enter**. Press **n** to walk through the hits.
2. With the cursor on the first line you want, hold **shift** and press **↓**
   until the range covers the block.
3. Press **y**.

The text goes to your system clipboard, and inside tmux it also lands in a tmux
paste buffer that is forwarded to every attached client — so the copy works even
from a pane that is not currently visible. You can also just drag with the mouse
instead of steps 2–3.

## Bring an agent back

Two routes, and the cheaper one is usually not the obvious one:

- **R — restore** relaunches the agent with its recorded session. Use it when the
  agent's context is the thing you want back: a long investigation, a
  half-finished conversation.
- **p — re-pick** starts the task over with a fresh agent. Use it when the task
  file already says everything that matters. It is usually cheaper than replaying
  a long transcript.

Each route needs one thing the other does not, and the record may carry only one
of them:

- **Re-pick needs a task id.** Without one the viewer refuses and points you the
  other way: `This record has no task id — restore instead`.
- **Restore needs a recorded session id.** When the agent's session was never
  captured there is nothing to resume, so the restore never starts and the record
  is left untouched. The viewer reports this as
  `restore did not start — run 'ait frozenagent' or reconcile`, because the
  coordinator runs detached and cannot report its own reason back. Re-pick is the
  way back here, and is the reason it exists.

Neither asks for confirmation, because neither can leave you with nothing: if the
attempt fails, the viewer comes back and the capture is intact. Watch the header:
it reads `dispatching…` while the attempt is in flight, then settles.

**A successful, verified restore or re-pick does delete the capture.** Once the
resumed agent identifies itself, the transcript has served its purpose and the
record drops it — that is the `restored` outcome. If you want to keep any of the
captured output, copy it out with **y** *before* pressing **R** or **p**.

`restored, unverified — capture kept` is a **success**. It means the new agent is
running but nothing positively confirmed it resumed the same session, so the
capture is deliberately kept rather than deleted. You lose nothing; you simply
still have the transcript. Agents whose CLI does not report a session on startup
reach this outcome every time.

If the attempt fails, the viewer comes back and the capture is intact —
`restore failed: <reason> — capture kept`.

## Remove a frozen record

Press **k**, then confirm at
`Remove the frozen record and its capture? This cannot be undone.`

Dropping deletes the retained capture along with the record, and closes the
stand-in pane. It is the only action that discards the record *and* its
transcript while leaving you nothing running.

It is not, however, the only way the capture goes away: a **verified** restore or
re-pick deletes it too, once the resumed agent has identified itself. The capture
survives only a failed restore or a liveness-only one. So if the transcript is
what you want to keep, copy it out with **y** first — choosing **R** or **p** is
not a way to preserve it.

What the capture retains is the **tail** of the pane's scrollback, not
necessarily everything the agent ever printed: a freeze reaches back
`frozen.capture_max_lines` lines (50000 by default), so a longer-running pane can
have earlier output already out of reach before it is frozen.
