---
title: "Framework Development Skills"
linkTitle: "Skills"
weight: 80
description: "Code-agent skills used to develop the aitasks framework itself, not by end users"
---

This subsection documents skills that exist in `.claude/skills/` but are oriented toward people developing the aitasks framework — adding new skills, registering new code-agent models, auditing skill wrappers across agent trees. End users adopting the framework via the install tarball typically do not invoke them.

These pages live under `development/` (rather than the user-facing [Skills overview]({{< relref "/docs/skills" >}})) so the user-facing skill table stays focused on day-to-day workflows.

## Pure framework-development skills

These skills exist solely to support framework development. End users adopting aitasks via the install tarball typically do not invoke them.

| Skill | Description |
|-------|-------------|
| [`/aitask-audit-wrappers`](aitask-audit-wrappers/) | Audit and port aitask skill wrappers across all four code-agent trees, plus helper-script whitelist coverage |

## Useful for framework development *and* normal use

These skills live under [Skills]({{< relref "/docs/skills" >}}) (their canonical location) but are surfaced here too because they support framework-development workflows — registering new code-agent models, refreshing model registries, generating release changelogs.

| Skill | Description |
|-------|-------------|
| [`/aitask-add-model`]({{< relref "/docs/skills/aitask-add-model" >}}) | Register a known code-agent model in `models_<agent>.json` and optionally promote it to default |
| [`/aitask-refresh-code-models`]({{< relref "/docs/skills/aitask-refresh-code-models" >}}) | Research latest AI code agent models and update model configuration files |
| [`/aitask-changelog`]({{< relref "/docs/skills/aitask-changelog" >}}) | Generate changelog entries from commits and archived plans |

## See also

- User-facing skills: [Skills overview]({{< relref "/docs/skills" >}})
- Framework architecture: [Development Guide]({{< relref "/docs/development" >}})
- Skill authoring conventions: see "WORKING ON SKILLS / CUSTOM COMMANDS" in [CLAUDE.md](https://github.com/dario-bs/aitasks/blob/main/CLAUDE.md)
