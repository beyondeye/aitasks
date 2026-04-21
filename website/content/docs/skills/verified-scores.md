---
title: "Verified Scores"
linkTitle: "Verified Scores"
weight: 110
description: "How skill satisfaction ratings accumulate into verified model scores"
depth: [advanced]
---

Verified scores track how well each LLM model performs for each skill operation. After a skill completes, users rate the result on a 1--5 scale; these ratings accumulate into per-model, per-operation scores that help choose the best model for a given task.

## How Scores Are Collected

At the end of each skill run, the workflow prompts:

> _How well did this skill work? (Rate 1--5, helps improve model selection)_

The raw rating maps to a 20--100 internal scale (1 &rarr; 20, 2 &rarr; 40, 3 &rarr; 60, 4 &rarr; 80, 5 &rarr; 100). Each rating updates the running average for the current model and operation.

**Skills that collect feedback:** `/aitask-pick`, `/aitask-explore`, `/aitask-explain`, `/aitask-changelog`, `/aitask-wrap`, `/aitask-refresh-code-models`, `/aitask-reviewguide-classify`, `/aitask-reviewguide-merge`, `/aitask-reviewguide-import`, `/aitask-web-merge`.

Feedback collection is controlled by the `enableFeedbackQuestions` field in [execution profiles]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}}). It defaults to `true` (enabled); set to `false` to suppress the prompt.

## Score Scale

| Range | Label | Meaning |
|-------|-------|---------|
| **0** | Not verified | Untested or unknown quality |
| **1--49** | Partially verified | Works but with known issues |
| **50--79** | Verified | Works well for most cases |
| **80--100** | Highly verified | Extensively tested, recommended |

## Time Windows

Scores are stored in three time-windowed buckets so recent performance is visible alongside the historical average:

| Bucket | Period key | Description |
|--------|-----------|-------------|
| `all_time` | (none) | Cumulative across all ratings |
| `month` | `YYYY-MM` | Current calendar month; resets when the month changes |
| `week` | `YYYY-Www` | Current ISO 8601 week; resets when the week changes |

Each bucket tracks `runs` (number of ratings) and `score_sum` (sum of mapped scores). The all-time average is also stored in the flat `verified` field for backward compatibility.

## Provider-Specific vs All-Providers

The same LLM can be available through different providers (e.g., `openai/gpt-5.4` and `opencode/gpt-5.4`). Verified scores are stored per provider, but consumers can aggregate them across providers to show a single cross-provider view:

1. Strip the `provider/` prefix from each model's CLI ID to get the normalized model name
2. Group entries with the same normalized name across all `models_*.json` files
3. Sum `runs` and `score_sum` from matching buckets across the group
4. For `month` and `week`, only aggregate entries with the same period value

This aggregation is performed at read time -- no duplicate values are stored. `ait settings` and `ait stats` both implement this aggregation.

## Where Scores Appear

- **[Settings TUI]({{< relref "/docs/tuis/settings" >}})** -- The Agent Defaults tab shows verified score context next to each model (`[96 (9 runs, 2 this mo)]`). The model picker opens with a Top Verified list. The Models tab shows per-operation scores with run counts and all-providers summaries
- **[`ait stats`]({{< relref "/docs/skills/aitask-stats" >}})** -- Prints verified model score rankings per skill with all-providers aggregation and time-windowed display
- **[`ait stats-tui`]({{< relref "/docs/tuis/stats" >}})** -- Renders verified score ranking bar charts per skill alongside the other stats panes

## Storage

Scores are stored in `aitasks/metadata/models_<agent>.json` alongside model definitions. See the [model entry schema]({{< relref "/docs/tuis/settings/reference#model-entry-schema" >}}) for the full `verifiedstats` structure.
