---
title: "Review guides"
linkTitle: "Review guides"
weight: 50
description: "Structured prompts that drive batched, repeatable code review."
depth: [intermediate]
---

## What it is

A **review guide** is a markdown file in `aireviewguides/` that captures a single concern a reviewer cares about — a security check, a portability rule, a stylistic convention, a project-specific invariant. Each guide carries a YAML frontmatter block (name, review type, language environment, files matched, similarity links to related guides) and a body of structured instructions the agent applies during review. Guides are organized into language-keyed subdirectories (`aireviewguides/python/`, `aireviewguides/bash/`, ...) so reviews can target only the guides relevant to the changed files.

## Why it exists

Ad-hoc code review depends on whoever happens to look at a PR and what they happen to remember that day. Review guides make the criteria explicit, reusable, and version-controlled: every reviewer (human or agent) applies the same checks, new lessons can be captured by adding or refining a guide, and similar guides can be classified, merged, or split as the catalog grows.

## How to use

The schema and authoring rules are documented in the [Review guide format reference]({{< relref "/docs/development/review-guide-format" >}}). Run a guided review with [`/aitask-review`]({{< relref "/docs/skills/aitask-review" >}}); manage the catalog with [`/aitask-reviewguide-classify`]({{< relref "/docs/skills/aitask-reviewguide-classify" >}}), [`/aitask-reviewguide-merge`]({{< relref "/docs/skills/aitask-reviewguide-merge" >}}), and [`/aitask-reviewguide-import`]({{< relref "/docs/skills/aitask-reviewguide-import" >}}).

## See also

- [Code review workflow]({{< relref "/docs/workflows/code-review" >}}) — end-to-end review process
- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — review findings become follow-up tasks

---

**Next:** [Execution profiles]({{< relref "/docs/concepts/execution-profiles" >}})
