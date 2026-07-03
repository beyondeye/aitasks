---
title: "/aitask-learn-skill"
linkTitle: "/aitask-learn-skill"
weight: 105
description: "Learn a new static skill from a pane, file, URL, or repository source"
maturity: [experimental]
depth: [advanced]
---

Learn a reusable code-agent skill from source material. The source can be a tmux
pane showing a workflow an agent just performed, a local file, a generic URL, a
repository file, or a repository directory. The skill reads the source, asks what
part of the material should become reusable, generalizes concrete details when
needed, and writes a static `SKILL.md`.

**Usage:**

```text
/aitask-learn-skill %5
/aitask-learn-skill ./notes/deploy.md
/aitask-learn-skill https://example.com/how-to/deploy
/aitask-learn-skill https://github.com/org/repo/blob/main/docs/deploy.md
/aitask-learn-skill https://github.com/org/repo/tree/main/docs/skills
```

In Codex CLI, use `$aitask-learn-skill` with the same argument shape.

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

1. **Resolve the source** - If you pass an argument, the skill uses it directly. If not, it asks whether to learn from a tmux pane, local file, URL, or repository file/directory.
2. **Classify the source** - Pane ids match `%N`; local paths can be absolute, `~`, or `./`; GitHub, GitLab, and Bitbucket file and directory URLs are recognized separately from generic URLs.
3. **Acquire the content** - Local files are read directly. Repository files and directories use the repository fetch helper with raw URL fallback. Generic URLs are fetched as page text.
4. **Capture panes read-only** - For a tmux pane source, the skill calls `aitask_shadow_capture.sh` and never sends input to the pane. It starts with a larger capture window and asks before pulling more scrollback if the workflow appears truncated.
5. **Select what to learn** - If the source contains several distinct procedures, the skill asks which part or parts should become the new skill.
6. **Generalize concrete details** - If the material contains hard-coded task ids, paths, ports, or project-specific names, the skill asks which should become parameters and which should stay literal.
7. **Name and write the skill** - It asks for a skill name and one-line description, then writes `.claude/skills/<name>/SKILL.md`. Long sub-flows may be split into sibling markdown files that the generated skill reads and follows.
8. **Verify and optionally wrap** - The generated static skill is checked with `aitask_skill_verify.sh`. If the project has Codex or OpenCode skill trees, the skill can also emit thin wrappers so the new command is invokable from those agents.
9. **Optionally commit** - The generated skill files are source code, so commits use plain `git`, not `./ait git`.

## Source Types

### Tmux pane

Use a pane id such as `%5` when the procedure you want to capture is visible in a
running agent's terminal history:

```text
/aitask-learn-skill %5
```

The pane path is read-only. The skill captures cleaned scrollback, checks whether
the start of the workflow is present, and can deepen the capture in increments
until the workflow start is included, scrollback is exhausted, or you say the
capture is enough.

### Local file

Use a path when you already have notes, a runbook, or a draft procedure in the
repository:

```text
/aitask-learn-skill ./notes/release-checklist.md
```

### URL or repository source

Generic URLs are fetched as page text. GitHub, GitLab, and Bitbucket files are
fetched through the repository helper. Repository directory URLs list markdown
files first, then ask which ones to use as source material.

```text
/aitask-learn-skill https://example.com/runbooks/release
/aitask-learn-skill https://github.com/org/repo/tree/main/docs/runbooks
```

## Generated Skill Shape

Generated skills are static by default. They use normal skill frontmatter
(`name`, `description`, `user-invocable: true`) and a focused procedure that
preserves the important commands, flags, file paths, and verification steps from
the source. Profile-aware `.j2` skills, template goldens, and framework-internal
stub machinery are not part of the default generated output.

The generator applies the configured learn-skill authoring guide when one is set,
falling back to the generic guide installed by `ait setup` and then to normal
skill-writing judgment if no guide is available.

## Shadow Integration

When you are using the [Shadow Agent](../../workflows/shadow-agent/), you can ask
it to learn a skill from what the followed agent just did. The shadow confirms the
action, then opens a dedicated learner agent in a new tmux window running
`/aitask-learn-skill <followed_pane_id>`. The shadow remains available for
advice, and neither the shadow nor the learner writes to the followed pane.

## Related

- [Shadow Agent](../../workflows/shadow-agent/) - Learn from a followed agent's workflow while keeping the shadow advisory-only.
- [Code Agent Skills](..) - Skill invocation conventions across supported agents.
- [Framework Development Skills](../../development/skills/) - Framework-maintenance skills and wrapper auditing.
