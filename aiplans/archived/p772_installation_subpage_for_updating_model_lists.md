---
Task: t772_installation_subpage_for_updating_model_lists.md
Base branch: main
plan_verified: []
---

# Plan: t772 — Installation subpage for updating model lists

## Context

A new aitasks user looking for "how do I refresh the supported-models list?" lands on the website's **Installation** section first, but the relevant skill pages (`/aitask-refresh-code-models`, `/aitask-add-model`) live under **Skills** and are not cross-linked from Installation. This task adds a navigational/orientation subpage under Installation that points users to the existing skill docs and explains where the model files live and how to commit changes.

The page is intentionally a short pointer page — it does not re-document the skills.

## Critical files

- **New:** `website/content/docs/installation/updating-model-lists.md` (Hugo/Docsy markdown)
- **Edit:** `website/content/docs/installation/_index.md` — add the new page to the "Setup topics" bullet list

## Existing assets to cross-link

- `website/content/docs/skills/aitask-refresh-code-models.md` — full refresh skill reference
- `website/content/docs/skills/aitask-add-model.md` — single-model registration skill reference
- `website/content/docs/skills/verified-scores.md` — `verified` scores context
- `website/content/docs/tuis/settings/_index.md` — Settings TUI (Models tab)

## Weight slot

Existing weights in `website/content/docs/installation/`: `_index 10`, `macos 22`, `linux 24`, `windows-wsl 26`, `terminal-setup 40`, `git-remotes 50`, `pypy 60`, `known-issues 70`. Slot the new page at **`weight: 65`** — after the platform install / setup-topic guides, before "Known Agent Issues".

## New page outline

`website/content/docs/installation/updating-model-lists.md`:

```markdown
---
title: "Updating Model Lists"
linkTitle: "Updating Model Lists"
weight: 65
description: "Refresh the supported AI code-agent model lists used by ait codeagent, the Settings TUI, and verified-score stats"
---

Brief lead-in: why a project keeps local model lists, what drives the need to refresh them.

## Why refresh

Vendors release new coding-capable models periodically. The local
`aitasks/metadata/models_<agent>.json` files drive:

- [`ait codeagent`]({{< relref "/docs/commands/codeagent" >}}) — model selection per skill/operation
- [Settings TUI]({{< relref "/docs/tuis/settings" >}}) — Agent Defaults and Models tabs
- [Verified scores]({{< relref "/docs/skills/verified-scores" >}}) — per-skill, per-model satisfaction ratings

Refreshing periodically keeps these surfaces accurate when vendors add, rename, or deprecate models.

## One-shot refresh of all agents

The [`/aitask-refresh-code-models`]({{< relref "/docs/skills/aitask-refresh-code-models" >}}) skill
walks through all four agents:

- **claudecode**, **codex**, **geminicli** — discovered via web research (`WebSearch` + `WebFetch` against vendor docs).
- **opencode** — discovered via CLI (`bash .aitask-scripts/aitask_opencode_models.sh`), because the available OpenCode models depend on which providers the user has connected locally.

The skill preserves existing `verified` scores and never auto-removes models — deprecated entries are flagged for explicit approval. Run it from the project root:

\`\`\`
/aitask-refresh-code-models
\`\`\`

## OpenCode-only quick path

When you only need to refresh the OpenCode list (e.g., after connecting a new provider locally), call the helper directly:

\`\`\`bash
bash .aitask-scripts/aitask_opencode_models.sh            # discover + update
bash .aitask-scripts/aitask_opencode_models.sh --dry-run  # show diff only
bash .aitask-scripts/aitask_opencode_models.sh --sync-seed
\`\`\`

The helper preserves `verified` scores and the `unavailable` status marker on models the local CLI cannot currently see.

## Adding a single known model

When you already know a model's `cli_id` (e.g., a vendor just announced one specific variant), skip web research and use [`/aitask-add-model`]({{< relref "/docs/skills/aitask-add-model" >}}):

\`\`\`
/aitask-add-model --agent claudecode --name opus4_7_1m --cli-id 'claude-opus-4-7[1m]' --notes "1M context"
\`\`\`

Add `--promote --promote-ops <ops>` to also set the new model as the default for the specified ops. See the skill page for the full flag list and the manual-review file list emitted after a promote.

## Where the files live

| File | Purpose | Branch |
|------|---------|--------|
| `aitasks/metadata/models_<agent>.json` | Runtime model list — read by `ait codeagent`, Settings TUI, stats | Task-data branch (committed via `./ait git`) |
| `seed/models_<agent>.json` | Template for new projects bootstrapped with `ait setup` | Source-repo branch (committed via plain `git`); only present in the framework source repo |

`<agent>` is one of: `claudecode`, `codex`, `geminicli`, `opencode`.

## Commit conventions

The two file locations live on different branches, so they need separate commits:

- **Metadata** (`aitasks/metadata/...`) — `./ait git add` + `./ait git commit` (see [Git Operations on Task/Plan Files]({{< relref "/docs/concepts/git-branching-model" >}})).
- **Seed** (`seed/...`) — plain `git add` + `git commit`. Seed files exist only in the framework source repo and never need `./ait git`.

Both `/aitask-refresh-code-models` and `/aitask-add-model` handle this split automatically; the convention matters only if you are editing the JSON files by hand.

## Related

- [`/aitask-refresh-code-models`]({{< relref "/docs/skills/aitask-refresh-code-models" >}}) — full refresh skill reference
- [`/aitask-add-model`]({{< relref "/docs/skills/aitask-add-model" >}}) — single-model registration
- [Settings TUI]({{< relref "/docs/tuis/settings" >}}) — Models tab (read-only view of the lists)
- [Verified scores]({{< relref "/docs/skills/verified-scores" >}}) — how ratings accumulate
- [`ait codeagent`]({{< relref "/docs/commands/codeagent" >}}) — model picker that consumes these files
```

## Edit to `_index.md` (Setup topics list)

Insert one bullet under the existing "Setup topics" section in `website/content/docs/installation/_index.md`. Existing block (current state):

```markdown
- [Terminal Setup]({{< relref "terminal-setup" >}}) — terminal emulator + tmux, `ait ide` workflow.
- [Git Remotes]({{< relref "git-remotes" >}}) — auth for GitHub / GitLab / Bitbucket (required for locking, sync, issues).
- [Known Agent Issues]({{< relref "known-issues" >}}) — current Claude Code / Gemini CLI / Codex CLI / OpenCode caveats.
- [PyPy Runtime]({{< relref "pypy" >}}) — optional faster runtime for long-running TUIs.
```

Add one bullet (after the PyPy bullet, before Known Issues — to mirror the weight order 60 → 65 → 70):

```markdown
- [Updating Model Lists]({{< relref "updating-model-lists" >}}) — refresh the supported model lists used by `ait codeagent` and the Settings TUI.
```

Result:

```markdown
- [Terminal Setup]({{< relref "terminal-setup" >}}) — terminal emulator + tmux, `ait ide` workflow.
- [Git Remotes]({{< relref "git-remotes" >}}) — auth for GitHub / GitLab / Bitbucket (required for locking, sync, issues).
- [PyPy Runtime]({{< relref "pypy" >}}) — optional faster runtime for long-running TUIs.
- [Updating Model Lists]({{< relref "updating-model-lists" >}}) — refresh the supported model lists used by `ait codeagent` and the Settings TUI.
- [Known Agent Issues]({{< relref "known-issues" >}}) — current Claude Code / Gemini CLI / Codex CLI / OpenCode caveats.
```

(I will also reorder the existing four bullets to match weight order: terminal-setup 40, git-remotes 50, pypy 60, then the new updating-model-lists 65, then known-issues 70.)

## Implementation steps

1. Create `website/content/docs/installation/updating-model-lists.md` with the content above. Triple-check that:
   - `{{< relref ... >}}` paths resolve (full `/docs/...` form for cross-section refs; bare slugs for same-directory).
   - No "previously…" / version-history prose (per CLAUDE.md "Documentation Writing").
   - Verbs match semantics: "refresh", "update" — not `ait setup` / `ait upgrade`.
   - No duplication of skill-page content — page is navigational.
2. Edit `website/content/docs/installation/_index.md` to insert the new bullet under "Setup topics" in weight order.

## Verification

1. Build the site locally and visually inspect the new page renders and is discoverable from the Installation index:

   ```bash
   cd website && ./serve.sh
   ```

   - Navigate to **Installation** in the sidebar — confirm "Updating Model Lists" appears between "PyPy Runtime" and "Known Issues".
   - Open the new page — confirm headings render, code blocks are formatted, and the related-link footer renders.
   - Click each `{{< relref >}}` link (refresh-code-models, add-model, settings TUI, verified-scores, codeagent, git-branching-model) — confirm none 404.
   - Open the Installation `_index.md` — confirm the new "Updating Model Lists" bullet appears in the Setup topics list in the right position.

2. Build the production site (optional — sanity check for broken cross-refs):

   ```bash
   cd website && hugo build --gc --minify
   ```

   Watch for `WARN` lines about unresolved `relref` calls.

3. (Skipped: no shell/Python code changes, so no shellcheck or test scripts apply.)

## Step 9 reminder

After implementation review approval, follow Step 9 of the shared task-workflow (`./.aitask-scripts/aitask_archive.sh 772`).

## Final Implementation Notes

- **Actual work done:**
  - Created `website/content/docs/installation/updating-model-lists.md` with `weight: 65`, six sections (Why refresh / One-shot refresh / OpenCode-only quick path / Adding a single known model / Where the files live / Commit conventions) plus a Related links footer. Page is purely navigational — cross-links to `/aitask-refresh-code-models`, `/aitask-add-model`, Settings TUI, verified-scores, `ait codeagent`, and the git-branching-model concept page.
  - Edited `website/content/docs/installation/_index.md` "Setup topics" list: inserted the new bullet between PyPy and Known Issues, and reordered the existing four bullets to match weight order (terminal-setup 40 → git-remotes 50 → pypy 60 → updating-model-lists 65 → known-issues 70).
- **Deviations from plan:** None. Implemented exactly as planned. The reorder of pre-existing bullets to match weight order was already part of the plan (noted under "Edit to `_index.md`").
- **Issues encountered:** None.
- **Key decisions:**
  - Weight 65 was chosen to slot the page between PyPy (60) and Known Issues (70), per the task description "after the platform guides".
  - The page is intentionally short and pointer-only — does not re-document the skills, per CLAUDE.md "redirect cross-refs now, defer content migration" guidance.
  - Used full `/docs/...` relref paths for cross-section refs and bare slug `updating-model-lists` for the same-directory ref in `_index.md`, matching the surrounding style.
- **Upstream defects identified:** None.

### Build verification

```
cd website && hugo build --gc --minify --quiet 2>&1 | grep -i "WARN\|ERROR\|REF_NOT_FOUND"
```

Empty output — no broken `relref` calls, no Hugo warnings/errors.
