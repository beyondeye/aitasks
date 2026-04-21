---
title: "Verified scores"
linkTitle: "Verified scores"
weight: 70
description: "How user satisfaction ratings accumulate into per-model, per-operation reliability scores."
---

## What it is

A **verified score** is a numeric rating attached to a (code agent, model, operation) triple — for example "claudecode/opus4_7 / implementation" or "geminicli/gemini-2.5-pro / code-review". Every time a user completes a skill they are prompted for a 1-5 satisfaction rating; those ratings are stored, time-windowed (all-time / month / week), and aggregated into score buckets:

| Bucket | Range |
|--------|-------|
| Untested | 0 |
| Partial | 1-49 |
| Verified | 50-79 |
| Highly verified | 80-100 |

Scores are surfaced in the [Settings TUI]({{< relref "/docs/tuis/settings" >}}) and on the model entry pages so you can see which agent/model combinations are reliable for which kinds of work in your project.

## Why it exists

The pace of new model releases makes any static "best model" recommendation immediately stale. Verified scores let your own usage history drive that recommendation: each project accumulates evidence about which models reliably plan, implement, and review your kind of code, and the framework surfaces that evidence at the points where you choose a model.

## How to use

The complete schema, score derivation, and CLI tooling are documented on the [Verified scores skill page]({{< relref "/docs/skills/verified-scores" >}}).

## See also

- [Agent attribution]({{< relref "/docs/concepts/agent-attribution" >}}) — how a task records the model that implemented it
- [Settings TUI]({{< relref "/docs/tuis/settings" >}}) — where scores are displayed

---

**Next:** [Agent attribution]({{< relref "/docs/concepts/agent-attribution" >}})
