---
title: "Shadow Agent"
linkTitle: "Shadow agent"
weight: 125
description: "How a companion agent knows which agent it follows, and what keeps it advisory."
depth: [intermediate]
---

## What it is

A **shadow** is a second coding agent bound to the agent you are watching. What
it can do for you and how to drive it are covered in the
[Shadow Agent workflow]({{< relref "/docs/workflows/shadow-agent" >}}); this
page covers how the shadow knows *which* agent it follows, and what keeps it
from acting on that agent.

### The binding is a pane option

When a shadow is spawned, the framework stamps a tmux pane option on the
**shadow's** pane: `@aitask_shadow_target`, whose value is the pane id of the
followed agent. That one option does three jobs:

- it tells monitor and minimonitor that this pane is a companion, so it is left
  out of the agent list;
- it names the pane the shadow's capture reads;
- it lets the cleanup that runs when the followed agent's pane dies find and
  close every shadow bound to it.

Pane options die with the pane, so a recycled pane id can never inherit a stale
binding — the same mechanism the framework uses to join a pane to its agent
record (see
[Identity versus location]({{< relref "/docs/concepts/framework-session" >}}#identity-versus-location)).

If the stamp cannot be written, the new pane is killed rather than left
running. An unstamped shadow is indistinguishable from a real agent: it would be
listed as one, targeted by agent commands, and never cleaned up.

### The capture reads the binding, not a typed id

A pane id that passes through a model can come back mangled, and the dangerous
case is a mangled id that happens to name a *different live* pane: the capture
then succeeds and the shadow advises on the wrong agent's work. So in the
normal flow the capture is given no id at all. It reads the binding off the
shadow's own pane, accepts it only when that pane is on the same tmux server the
framework drives, and waits briefly for the stamp on a just-spawned shadow. If
no binding appears, it fails rather than guessing.

### Reading a copy, not sharing a session

The shadow is built as **capture → context-fetch → skill**. It reads a cleaned
text capture of the followed pane, fetches that agent's task and plan files by
task id when a request needs them, and reasons over both. It is never attached
to the followed agent's session. Two consequences: it can re-read the screen
whenever you ask, and what it knows is only as current as its last capture.

### What keeps it advisory

Two separate facts keep the shadow advisory, and neither should be read as the
other:

- **The framework's own path is read-only.** Capture reads the pane and
  context-fetch reads files. When you forward the shadow's concerns, it is
  monitor or minimonitor that opens a picker and, only after you confirm, copies
  your choices to the clipboard. Nothing the framework runs on the shadow's
  behalf types into the followed pane.
- **The shadow is instructed not to drive the followed pane.** The shadow is an
  ordinary coding agent with its usual tools; no sandbox makes a write to that
  pane impossible. Never sending keystrokes or answers is a rule in the
  shadow's own skill — the contract it is built to honour, not an isolation
  boundary.

What the contract means for you day to day is in
[Advisory only]({{< relref "/docs/workflows/shadow-agent" >}}#advisory-only).

## Why it exists

A companion agent has to know whom it follows without you restating it on
every request, and without trusting a model's copy of an identifier. A binding
stored on the shadow's own pane, read by the capture itself and gone the moment
the pane is, provides both.

## How to use

Press **e** on an agent in [minimonitor]({{< relref "/docs/tuis/minimonitor" >}})
or [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) — **E** first picks the
code agent and model. The per-TUI steps are in
[How to launch a shadow agent]({{< relref "/docs/tuis/minimonitor/how-to" >}}#how-to-launch-a-shadow-agent)
(minimonitor) and
[How to launch a shadow agent]({{< relref "/docs/tuis/monitor/how-to" >}}#how-to-launch-a-shadow-agent)
(monitor).

## See also

- [Shadow Agent]({{< relref "/docs/workflows/shadow-agent" >}}) — launching a shadow and everything it can do
- [Minimonitor]({{< relref "/docs/tuis/minimonitor" >}}) — the companion sidebar that launches and reads shadows
- [Monitor]({{< relref "/docs/tuis/monitor" >}}) — launching from the agent list, and the shadow preview column
- [Framework session]({{< relref "/docs/concepts/framework-session" >}}) — the pane-option join between a pane and its agent record

---

**Next:** [Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}})
