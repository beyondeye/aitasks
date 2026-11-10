---
title: "/aitask-docs-review"
linkTitle: "/aitask-docs-review"
weight: 18
description: "Review documentation pages against your project's doc-update guide: reader level, prose, and a fresh-reader test for beginner pages"
maturity: [experimental]
depth: [intermediate]
---

`/aitask-docs-review` checks documentation pages against your project's doc-update guide and reports what a reader would stumble on. It answers three questions for each page:

- **Level:** does the page fit the reader level it declares in its frontmatter?
- **Prose:** does it follow the guide's writing rules?
- **Fresh reader:** can someone new to the project answer their own questions from this page alone?

The skill carries no rules of its own. It reads them from the guide that your project configures as `doc_update.guide` in `aitasks/metadata/project_config.yaml` (by default `aitasks/metadata/doc_update_guide.md`), so you change what it checks by editing that guide.

**Usage:**
```
/aitask-docs-review <page>...                 # Review pages and report; edits nothing
/aitask-docs-review <page>... --budget 1      # Allow at most one fresh-reader test
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## When it runs

The [`docs_updated` gate]({{< relref "/docs/skills/aitask-gate-docs-updated" >}}) runs it on every documentation change it proposes, before it asks you to confirm. The gate first writes each proposed page as a complete draft, and the review reads those drafts. What you approve is therefore the text that was reviewed. If you ask for changes, the changed pages are reviewed again before the gate asks you a second time.

You can also run it yourself on any page. Run that way, it only reports; it edits a page only when you ask it to.

## The fresh-reader test

For pages at the guide's beginner level, the skill writes 5 to 10 questions a newcomer would bring to the page. It gives them to a separate agent that sees only the page text and the guide's description of that reader. That agent answers, then lists every term it had to guess, every detail it did not need, anything ambiguous and anything that contradicts the rest of the page. Wrong or guessed answers point at what the page fails to explain.

Code agents that cannot start a separate agent run the same questions as a self-review checklist, and the report says so.

These tests take time and tokens, so each gate run allows three in total, counted across every review and re-review in that run. Pages with the most changed lines are tested first. Pages left over are listed when the gate asks you to confirm, and you can choose to test them too. Autonomous execution profiles never go past the three.

## Reading the report

Each page gets a `level=`, `prose=` and `reader=` result, its findings, and a list of unresolved problems for you to decide on. The `reader=` result says whether and how the fresh-reader test ran:

| `reader=` | Meaning |
|-----------|---------|
| `subagent` | A separate agent ran the test. |
| `self-review` | No separate agent was available, so the self-review checklist ran. |
| `not-run(not-beginner)` | The page is written for readers past the beginner level. |
| `not-run(untagged)` | The page declares no level. This is also reported as a level finding, since every page must declare one. |
| `not-run(cap)` | The run's three tests were already used. |
| `not-run(no-level-model)` | The guide has no reader levels, so only the prose check ran. |

A guide has reader levels when it contains a `## Reader levels` section that names the frontmatter field holding a page's level, the beginner level, and a one-sentence description of each level's reader. The generic guide that `ait setup` installs has no such section, so in a new project the review checks prose only until you add one.

## Availability

This skill is available in Claude Code. Codex CLI and OpenCode wrappers are not available yet.

## Related

- [`/aitask-gate-docs-updated`]({{< relref "/docs/skills/aitask-gate-docs-updated" >}}): the gate that drafts doc updates and runs this review
- [`/aitask-docs-gap`]({{< relref "/docs/skills/aitask-docs-gap" >}}): finds missing documentation for a release
