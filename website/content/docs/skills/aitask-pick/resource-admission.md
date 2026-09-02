---
title: "Resource Admission"
linkTitle: "Resource Admission"
weight: 15
description: "Let the project decide whether the host can afford to start implementing a task"
depth: [advanced]
---

Planning is cheap. Implementation and verification are usually where a project
becomes memory-bound — test workers, emulators, compilers — and an agent that
starts one of those phases on a host that cannot afford it takes the host down
with it.

The **resource-admission hook** is where a project gets a say. `/aitask-pick`
asks it one question, once, immediately before implementation starts: *can this
host afford to begin now?* If the answer is no, the task is **parked** rather
than failed — its approved plan is kept, and the next pick resumes from it.

The framework ships only the seam. What "afford" means — available memory,
pressure stall information, a GPU, a licence server — is yours to define.

## Configuration

One key in `aitasks/metadata/project_config.yaml`:

```yaml
resource_admission_command: "./tools/check_memory.sh"
```

Leave it blank (the default) and the step does nothing at all: no prompt, no
message, no file. It is also editable in `ait settings` → **Project Config**.

Unlike `verify_build` / `test_command` / `lint_command`, this key takes a
**single command**, not a list — a project needing several probes points it at
one wrapper script, which keeps "which refusal wins" from being a question. Two
shapes are **refused** outright, because neither leaves a command to run: a list
whatever its length (`["./probe.sh"]` is rejected just as `[a, b]` is, so the
rule has no length-dependent edge to trip over), and an indented block under the
key. Both are loud — the task is parked with a config error — rather than being
read as "no hook configured".

Everything else on the key line is taken as the command it textually is. That
includes text YAML would call a mapping: `{ make build; }` is a valid shell
group command, so the value is run rather than second-guessed. A value that will
not run is reported as a command error, which also parks the task.
(A scalar whose value happens to contain a comma is still a scalar.)

A command containing a colon-space must be quoted, or YAML reads it as a nested
mapping rather than a command:

```yaml
resource_admission_command: 'sh -c "echo ADMISSION_REASON: low memory; exit 2"'
```

## The exit contract

| Command exit | Meaning | What happens |
|---|---|---|
| `0` | admit | Implementation proceeds |
| `2` | defer | The task is parked with its approved plan |
| anything else | could not decide | The task is parked, and the message says the hook could not be evaluated |

A command that will not parse never ran, so it is reported as an error — never
as a refusal.

**The third row is deliberate.** A host that cannot be probed is exactly the one
that runs out of memory mid-verification, so a broken hook parks the task
instead of waving it through. Fixing or clearing
`resource_admission_command` is always enough to unblock the task.

## Telling the user why

Print an `ADMISSION_REASON:` line and it is shown with the stop:

```bash
#!/usr/bin/env bash
# exit 0 = admit, exit 2 = defer this task
avail_gib=$(awk '/^MemAvailable:/ {printf "%d", $2/1048576}' /proc/meminfo)
if [ "$avail_gib" -lt 8 ]; then
    echo "ADMISSION_REASON: only ${avail_gib} GiB available, need 8"
    exit 2
fi
```

Without that line the last line the command printed is used instead. Everything
the command writes is captured to a log, whose path is reported alongside the
reason.

Two environment variables are available to the command, and nothing else:

| Variable | Value |
|---|---|
| `AIT_RESOURCE_ADMISSION_TASK_ID` | The task being admitted, e.g. `1597` or `1597_2` |
| `AIT_RESOURCE_ADMISSION_PLAN_FILE` | Path to the approved plan file |

## What a park actually does

A refusal is a **defer, not a failure**. The task:

- returns to `Ready` and is unassigned, releasing its lock;
- **keeps its approved plan**, committed, and is marked as having one — it shows
  as `Plan: approved <timestamp>` in `ait ls -v`, and `ait ls --plan-approved`
  lists it;
- leaves **nothing** behind to clean up: the hook is consulted before the task's
  branch and worktree are created, so a refusal strands neither.

Re-pick it when the resource is free. Under a profile with
`plan_preference: use_current` the re-pick goes straight to the drift check and
implementation, with no re-planning; under `default` you are offered the
existing plan with *Use current plan* recommended.

A resumed in-flight task is asked again — a host that had room days ago proves
nothing about now.

## What it does not do

The hook **observes; it does not reserve**. An admit means "no known shortage at
check time" — another agent can claim the memory the instant after. If you run
several agents in parallel, treat it as a guard against the obvious case, not as
an allocator.

It is also not a [gate](../../../commands/gates/): nothing is recorded in the
task's gate ledger, and a parked task is indistinguishable from any other
approved-and-stopped task.

## See also

- [Build, Test, and Lint Configuration](../build-verification/) — the other
  `project_config.yaml` command keys. They are gate-shaped and run *after*
  implementation; this one is an admission decision *before* it, and it cannot
  be listed in `gate_command_exit_contract`.
