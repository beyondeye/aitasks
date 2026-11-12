---
title: "Skillrun"
linkTitle: "Skillrun"
weight: 46
description: "ait skillrun command for launching a code agent with a profile-aware aitask skill"
depth: [advanced]
---

## ait skillrun

`ait skillrun` starts a code agent that runs an aitask skill's slash command as
its first prompt, under the execution profile you choose. It is how you start a
profile-aware skill from the shell instead of from inside an agent session.

```bash
ait skillrun pick --profile fast 42           # /aitask-pick 42 under the fast profile
ait skillrun pick --profile fast --dry-run 42 # print the launch command only
```

| Argument | Description |
|----------|-------------|
| `<skill>` | The skill's short name, without the `aitask-` prefix: `pick` for `/aitask-pick`, `explore` for `/aitask-explore` |
| `--profile <name>` | The execution profile to run the skill under. Without it, the profile is resolved as described in [Resolution Order]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}}#resolution-order) |
| `--agent-string <agent>/<model>` | The code agent and model to launch. The default comes from `$AIT_AGENT_STRING`, else `$DEFAULT_AGENT_STRING` |
| `--profile-override <yaml\|->` | Merge an ad-hoc YAML (a file path, or `-` for standard input) on top of the resolved profile |
| `--dry-run` | Print the launch command without starting the agent |
| `-h`, `--help` | Show usage |
| further arguments, or everything after `--` | Passed on to the skill, for example the task number `42` |

With `--profile-override`, and without `--dry-run`, the merged YAML is written to
`aitasks/metadata/profiles/local/_skillrun_<unique>.yaml` (gitignored) and the
agent receives `--profile _skillrun_<unique>`; the file is deleted when the
agent exits. With `--dry-run`, the merged YAML is printed to standard error
instead, and no profile file is written. The launch dialog's one-shot save in the TUIs uses the same
mechanism; see
[Editing the profile in a launch dialog]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}}#editing-the-profile-in-a-launch-dialog).

How a profile-aware skill turns the chosen profile into the instructions it
follows is in [Skill Templating and Dispatch]({{< relref "/docs/development/skill-templating" >}}).
