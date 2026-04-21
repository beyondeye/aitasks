---
title: "Commit Attribution"
linkTitle: "Commit Attribution"
weight: 20
description: "How task-workflow composes contributor and code-agent coauthor trailers"
depth: [advanced]
---

When a task implementation is committed, the workflow can attach two kinds of attribution:

- an imported contributor trailer when the task carries `contributor` and `contributor_email` metadata
- a code-agent trailer for the agent recorded in `implemented_with`

This applies to the shared Step 8 commit flow used by `/aitask-pick` and other skills that route through the shared task workflow. The same composition rules are also used by direct-commit variants such as `/aitask-pickrem`, `/aitask-pickweb`, and `/aitask-wrap`.

## Commit Format

The commit subject always stays:

```text
<issue_type>: <description> (t<task_id>)
```

Optional attribution blocks are appended below the subject.

For a PR-imported task:

```text
feature: Add dark mode support (t42)

Based on PR: https://github.com/owner/repo/pull/15

Co-Authored-By: octocat <12345+octocat@users.noreply.github.com>
Co-Authored-By: Codex/GPT5.4 <codex@aitasks.io>
```

For an issue-imported task that carries contributor metadata but no `pull_request` URL:

```text
feature: Add portable sed helper (t142)

Co-Authored-By: contributor-name <contributor@example.com>
Co-Authored-By: Codex/GPT5.4 <codex@aitasks.io>
```

If the task has no contributor metadata, the imported-contributor block is omitted entirely.

## Contributor Metadata Sources

Contributor attribution is not limited to pull requests. The workflow uses imported task metadata:

- PR-imported tasks can provide `pull_request`, `contributor`, and `contributor_email`
- issue-imported tasks can also provide `contributor` and `contributor_email`, for example when `ait issue-import` imports an issue created via `/aitask-contribute`

If a `pull_request` URL is present, the commit message includes a `Based on PR:` line ahead of the contributor trailer. Otherwise, the contributor block is just the `Co-Authored-By` line.

## Code-Agent Trailer Source

The code-agent trailer is resolved from the task's `implemented_with` metadata:

```yaml
implemented_with: codex/gpt5_4
```

The workflow runs:

```bash
ait codeagent coauthor "codex/gpt5_4"
```

That command returns machine-readable fields including:

- `AGENT_COAUTHOR_NAME`
- `AGENT_COAUTHOR_EMAIL`
- `AGENT_COAUTHOR_TRAILER`

The workflow appends `AGENT_COAUTHOR_TRAILER` directly to the final commit message.

## Coauthor Email Domain

The email domain for code-agent trailers comes from the project-level file `aitasks/metadata/project_config.yaml`:

```yaml
codeagent_coauthor_domain: aitasks.io
```

The resolver generates agent-specific emails such as:

- `codex@aitasks.io`
- `claudecode@aitasks.io`
- `geminicli@aitasks.io`
- `opencode@aitasks.io`

`ait setup` seeds this field with `aitasks.io`, and teams can change it to any domain they want to use for custom code-agent attribution.

## Failure Behavior

- If contributor attribution is available, it is always kept.
- If `implemented_with` is missing, no code-agent trailer is added.
- If `ait codeagent coauthor` fails, only the code-agent trailer is skipped. The commit still proceeds with the normal subject line and any contributor attribution that was already available.

## Claude Code Note

Claude Code now follows the same resolver-based path as the other supported agents. The shared resolver trailer is the only agent coauthor trailer that should be added to the commit message; the workflow should not append an additional hardcoded Claude trailer on top of it.
