---
title: "/aitask-contribute"
linkTitle: "/aitask-contribute"
weight: 23
description: "Turn local changes into structured contribution issues for the aitasks framework or the current project repo"
---

Use `/aitask-contribute` to turn local changes into a structured contribution issue without going through the usual fork, branch, and pull request flow. You can use it to contribute improvements back to the `aitasks` framework, or to contribute changes to the current project repository when that project uses the aitasks framework.

**Usage:**
```
/aitask-contribute
```

> **Note:** Must be run from the project root directory. Requires the platform CLI installed and authenticated: `gh` for GitHub (default), `glab` for GitLab, or `bkt` for Bitbucket. See [Skills overview](..) for details.

## Step-by-Step

1. **Choose the target** — Pick whether you want to contribute to the `aitasks` framework or to the current project repository
2. **Select the area and files** — Choose the changed area, then select the files you want to include
3. **Review the AI summary** — The skill analyzes the diffs, summarizes what changed, and can split unrelated work into separate contributions
4. **Add the contribution details** — Confirm or edit the proposed title, explain the motivation, choose the scope, and set the suggested merge approach
5. **Preview and create the issue** — Review the final issue body, then create it on GitHub, GitLab, or Bitbucket

## Key Capabilities

- **Works in two places** — Contribute back to the `aitasks` framework, or contribute to the current project repository when that repo uses aitasks

- **Lets you focus the contribution** — Select only the relevant areas and files instead of sending everything at once

- **Useful in project repos too** — In project mode, the skill works from the project's code areas map. If the map is missing, it guides you through generating one first

- **AI helps package the change** — The skill summarizes the diff, proposes titles, suggests scope, and can split unrelated work into separate issues

- **Creates issues on the right platform** — Open contribution issues on GitHub, GitLab, or Bitbucket using the matching CLI tool

- **Preserves contributor attribution** — Imported work keeps contributor metadata so maintainers can carry attribution through the implementation workflow

- **No fork required** — Make the change locally, review the generated issue, and submit it directly

## Workflows

For the end-to-end contribution flow, including how maintainers import and implement contributed work, see [Contribute and Manage Contributions](../../workflows/contribute-and-manage/).
