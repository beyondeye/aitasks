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

Feedback collection is controlled by the `enableFeedbackQuestions` field in [execution profiles]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}}). It defaults to `true` (enabled); set to `false` to suppress the prompt. Disabling it skips only the rating and the verified-score update — the run is still counted in usage stats. The shipped `fast` and `remote` profiles disable it.

## Score Scale

| Range | Label | Meaning |
|-------|-------|---------|
| **0** | Not verified | Untested or unknown quality |
| **1--49** | Partially verified | Works but with known issues |
| **50--79** | Verified | Works well for most cases |
| **80--100** | Highly verified | Extensively tested, recommended |

## Time Windows

Scores are stored in time-windowed buckets so recent performance is visible alongside the historical average:

| Bucket | Period key | Description |
|--------|-----------|-------------|
| `all_time` | (none) | Cumulative across all ratings |
| `month` | `YYYY-MM` | Calendar month of the latest recorded run |
| `prev_month` | `YYYY-MM` | The calendar month before it |
| `week` | `YYYY-Www` | ISO 8601 week of the latest recorded run |

Each bucket tracks `runs` (number of ratings) and `score_sum` (sum of mapped scores). The score shown for a model and operation is the rounded `all_time` average once it has a rating. Before the first rating, the shown score is the model's `verified` value in its model list, a fixed starting score that ratings never change.

The buckets roll over only when the next run for that model and skill is recorded. A model that has not been used for months still holds its old buckets, so every reader checks the `period` against today. A bucket counts as this month, the previous month or this week only when its period is that month or week, and a `month` bucket from last month that has not rolled over yet counts as the previous month. "Recent" means this month plus the previous month.

## Provider-Specific vs All-Providers

The same LLM can be available through different providers (e.g., `openai/gpt-5.4` and `opencode/gpt-5.4`). Verified scores are stored per provider, but consumers can aggregate them across providers to show a single cross-provider view:

1. Strip the `provider/` prefix from each model's CLI ID to get the normalized model name
2. Group entries with the same normalized name across all `models_*.json` files
3. Sum `runs` and `score_sum` from matching buckets across the group
4. For `month`, `prev_month` and `week`, first resolve each provider's buckets against today (see [Time Windows](#time-windows)), then sum them

This aggregation is performed at read time -- no duplicate values are stored. `ait settings` and `ait stats` both implement this aggregation.

## Where Scores Appear

- **[Settings TUI]({{< relref "/docs/tuis/settings" >}})** -- The Agent Defaults tab shows verified score context next to each model (`[96 (9 runs, 2 this mo)]`). In the model picker, the per-agent lists show each model's score for the selected operation; the two top lists rank models by recent usage instead. The Models tab shows per-operation scores with run counts and all-providers summaries. The `batch-review` operation reads the scores that `/aitask-review` records under `review`
- **[`ait stats`]({{< relref "/docs/skills/aitask-stats" >}})** -- Prints verified model score rankings per skill with all-providers aggregation and time-windowed display
- **[`ait stats-tui`]({{< relref "/docs/tuis/stats" >}})** -- Renders verified score ranking bar charts per skill alongside the other stats panes

## Storage

The ratings and usage counts are kept on the `aitask-stats` git branch, in one `<agent>.json` file per code agent. The model lists in `aitasks/metadata/models_<agent>.json` hold each model's definition and its starting `verified` scores. See the [usage and score counters]({{< relref "/docs/tuis/settings/reference#usage-and-score-counters" >}}) for the file layout and the [model entry schema]({{< relref "/docs/tuis/settings/reference#model-entry-schema" >}}) for the model list.

Recording a rating or a run writes a commit to `aitask-stats` and pushes it. No working copy is involved, so a write never touches your task files. When the repository has a remote, each write first reads the remote branch and builds on it. When the remote cannot be reached, the write fails: the skill shows that the score or run was not recorded and carries on.

The local copy of the branch is updated by `./ait sync`, by the sync that runs when you pick a task, and by every write. The screens that show scores (`ait settings`, `ait stats`, `ait stats-tui`, the model picker and `ait codeagent list-models`) read the local copy only and never contact the remote. A score recorded on another machine therefore shows up after the next sync.

If a write prints `stats recorded locally only`, the counts were recorded on this machine but not pushed. This happens after a move of older counters (below) that was made without access to the remote and has not been published yet. Running `ait setup` publishes it once the move checks out against the remote's task data. If setup reports `Stats migration refused: …marker_not_in_source`, the remote does not contain the moved files, and nothing is published or repaired automatically. Do not reset or delete the local `aitask-stats` branch in that case: the counts held on it exist nowhere else.

### Moving older counters

A project set up with an older aitasks version keeps its counters inside `models_<agent>.json`. `ait setup` and `ait upgrade` move them onto the branch, once per code agent, and remove them from `models_<agent>.json`. Until an agent's counters have moved, the screens add the counters still in `models_<agent>.json` to the ones on the branch, so the numbers shown do not change.

Setup prints one line per agent:

| Line | Meaning |
|---|---|
| `Stats migrated: <agent>\|<commit>\|<runs>` | The counters were moved. |
| `Code-agent stats are already on the aitask-stats branch` | Every agent was moved earlier, or has no model list. |
| `Stats migration deferred: …` | Nothing was changed for that agent, for example because the remote could not be reached. The next `ait setup` or `ait upgrade` tries again. |
| `Stats migration refused: …` | The move stopped without changing that agent's counters. The message above it says why. |
| `Stats migration: discarded counters …` | An older aitasks version wrote counters into `models_<agent>.json` after the move. Those runs are dropped, not moved. |

The move never stops setup or upgrade. To turn it off, set `AIT_STATS_MIGRATE=0`. To see what it would do without changing anything, run `./.aitask-scripts/aitask_model_stats.py migrate --dry-run` from the project root. It prints one `MIGRATE_PLAN:` line per agent.
