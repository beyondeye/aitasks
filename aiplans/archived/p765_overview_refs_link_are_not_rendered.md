---
Task: t765_overview_refs_link_are_not_rendered.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Render "See also" references as clickable links in overview.md

## Context

`website/content/docs/overview.md` has six "See also:" lines (lines 32, 42, 52, 63, 73, 84). Each line uses bare Hugo `{{< relref "/path" >}}` shortcodes inside a comma-separated list, e.g.:

```
See also: {{< relref "/docs/concepts/ide-model" >}}, {{< relref "/docs/installation/terminal-setup" >}}, {{< relref "/docs/tuis" >}}.
```

`relref` resolves to a URL string — it does **not** wrap it in an anchor. So in the rendered page these "See also" lists appear as raw URLs instead of clickable links.

Other docs in the site already use the correct pattern (e.g. `website/content/docs/skills/aitask-fold.md:43`, `website/content/docs/workflows/task-decomposition.md:31`, `website/content/docs/workflows/parallel-development.md:36`):

```
[Link Label]({{< relref "/path" >}})
```

The fix is to wrap every `{{< relref "..." >}}` in `overview.md` with a markdown link using the target page's `linkTitle` as label.

## Files to modify

- `website/content/docs/overview.md` — lines 32, 42, 52, 63, 73, 84

No other files require changes.

## Implementation

Replace each "See also:" line with the wrapped-link form. Use the target page `linkTitle` for each label (read from each target page's frontmatter):

- Line 32 (Section 1 — Agentic IDE):
  ```
  See also: [The IDE model]({{< relref "/docs/concepts/ide-model" >}}), [Terminal Setup]({{< relref "/docs/installation/terminal-setup" >}}), [TUIs]({{< relref "/docs/tuis" >}}).
  ```

- Line 42 (Section 2 — Long-term memory):
  ```
  See also: [Agent memory]({{< relref "/docs/concepts/agent-memory" >}}), [/aitask-explain]({{< relref "/docs/skills/aitask-explain" >}}).
  ```

- Line 52 (Section 3 — Tight git coupling):
  ```
  See also: [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}), [PR Import]({{< relref "/docs/workflows/pr-workflow" >}}), [Issue Tracker]({{< relref "/docs/workflows/issue-tracker" >}}), [Revert Changes]({{< relref "/docs/workflows/revert-changes" >}}).
  ```

- Line 63 (Section 4 — Task decomposition):
  ```
  See also: [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}}), [Task Decomposition]({{< relref "/docs/workflows/task-decomposition" >}}), [Parallel Development]({{< relref "/docs/workflows/parallel-development" >}}).
  ```

- Line 73 (Section 5 — AI-enhanced code review):
  ```
  See also: [Review guides]({{< relref "/docs/concepts/review-guides" >}}), [Code Review]({{< relref "/docs/workflows/code-review" >}}), [QA and Testing]({{< relref "/docs/workflows/qa-testing" >}}).
  ```

- Line 84 (Section 6 — Multi-agent support):
  ```
  See also: [Agent attribution]({{< relref "/docs/concepts/agent-attribution" >}}), [Verified scores]({{< relref "/docs/concepts/verified-scores" >}}), [Code Agent]({{< relref "/docs/commands/codeagent" >}}), [Verified Scores]({{< relref "/docs/skills/verified-scores" >}}).
  ```

## Verification

1. Build the website locally:
   ```bash
   cd website && hugo build --gc --minify
   ```
   Should complete without `relref` errors.

2. Run the dev server and visit the Overview page:
   ```bash
   cd website && ./serve.sh
   ```
   Confirm each "See also" line on `/docs/overview/` renders the references as clickable links with the chosen labels, and each link navigates to the correct target page.

3. Spot-check that no other content on the page regressed (each of the 6 sections still has its description text intact).

## Post-Implementation

Follow Step 9 of the task-workflow:
- Commit changes to `website/content/docs/overview.md` with subject `documentation: Render overview "See also" refs as clickable links (t765)`.
- Commit the plan file via `./ait git`.
- Archive via `./.aitask-scripts/aitask_archive.sh 765`.

## Final Implementation Notes

- **Actual work done:** Wrapped each of the six `{{< relref "..." >}}` shortcodes in `website/content/docs/overview.md` (lines 32, 42, 52, 63, 73, 84) with a markdown link `[Label]({{< relref "..." >}})`. Labels are the target page `linkTitle` values resolved from each target file's frontmatter.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Used each target page's `linkTitle` as the label (matches the convention in `skills/aitask-fold.md`, `workflows/task-decomposition.md`, `workflows/parallel-development.md`).
- **Verification performed:** `hugo build --gc --minify` ran in `website/` with no errors and produced 190 pages. Did not run the dev server (build success is sufficient to confirm shortcodes resolve).
- **Upstream defects identified:** None.

## Post-Review Changes

### Change Request 1 (2026-05-12)
- **Requested by user:** During Step 8 review, user redirected to a separate concern: restructure `website/content/docs/installation/` so OS-specific pages (macOS, Linux distros, Windows/WSL) are grouped together with all Linux distros (arch-aur, debian-apt, fedora-dnf) merged into a single Linux page using subsections, and remaining topics (terminal-setup, known-issues, git-remotes, pypy) grouped separately. Also requested updating any links to the per-distro pages.
- **Decision:** This is a substantial restructure unrelated to t765's overview.md scope. Surfaced as a separate aitask rather than expanding t765's scope. t765's overview.md changes were not critiqued and remain accepted as-is.
- **Files affected (in t765):** none beyond original implementation.
