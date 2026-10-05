---
title: "Shadow Agent"
linkTitle: "Shadow agent"
weight: 125
description: "A second coding agent you open beside a working agent, to explain what it is doing and help you make its decisions — advice only."
depth: [intermediate]
---

## What it is

A **shadow agent** is a second coding agent that you open beside an agent you
are watching (the *followed agent*). It reads what the followed agent shows on
screen, looks up that agent's task and plan when it needs them, and answers your
questions about them in plain words.

A shadow is an adviser, not a second worker. It explains, suggests and reviews,
but it never types into the followed agent's terminal: you still answer every
prompt and approve every plan yourself.

## Why it exists

A coding agent at work produces a lot of dense output. Its plan may assume
background you do not have, a question it asks may refer to something that has
already scrolled away, and whether the code it wrote matches its plan is hard to
judge while it keeps working. Stopping the agent to ask would interrupt it.

A shadow gives you a second opinion on the side. You can ask it what the agent
is doing, what a question on screen means, whether a plan holds up, or whether
the finished code does what the plan promised — without interrupting the agent
you are watching.

## How to use

Press **e** on an agent in [minimonitor]({{< relref "/docs/tuis/minimonitor" >}})
(the small status sidebar beside each running agent) or in
[`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) (the dashboard of all your
agents) — **E** first lets you choose the code agent and model. The shadow opens
next to the agent, tells you what it can do, and waits for you to ask in your
own words. Common uses:

- explain what the agent is doing right now;
- help you decide how to answer a question the agent is waiting on;
- explain a plan, or challenge it, before you approve it;
- review the code once the agent has implemented the task;
- diagnose an error the agent hit in one of the framework's skills or scripts.

When the shadow raises concerns, press **c** in minimonitor or monitor to pick
the ones to pass on. They are copied to your clipboard for you to paste into the
agent, never sent to it directly. The shadow closes by itself when the agent it
follows exits.

Step-by-step guides:
[How to launch a shadow agent]({{< relref "/docs/tuis/minimonitor/how-to" >}}#how-to-launch-a-shadow-agent)
(minimonitor) and
[How to launch a shadow agent]({{< relref "/docs/tuis/monitor/how-to" >}}#how-to-launch-a-shadow-agent)
(monitor).

## See also

- [Shadow Agent]({{< relref "/docs/workflows/shadow-agent" >}}) — everything a shadow can do, how to configure it, and what keeps it advisory
- [Minimonitor]({{< relref "/docs/tuis/minimonitor" >}}) — the companion sidebar that launches and reads shadows
- [Monitor]({{< relref "/docs/tuis/monitor" >}}) — launching from the agent list, and the shadow preview column

---

**Next:** [Task lifecycle]({{< relref "/docs/concepts/task-lifecycle" >}})
