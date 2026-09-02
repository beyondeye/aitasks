---
title: "Parallel Admission"
linkTitle: "Parallel Admission"
weight: 16
description: "See which other in-flight tasks touch the same files, before implementation starts"
depth: [advanced]
---

When several agents work one repository, the collision is usually discovered
after the time has been lost. The framework already has ownership locks (which
stop two agents claiming the *same* task) and a remote-drift check (which
compares your plan against commits already pushed to the base branch). Neither
answers the question that actually costs you a morning: *is another task, right
now, planning to edit the files I am about to edit?*

The **parallel-admission preflight** asks that question once, at the
planning→implementation boundary, immediately after the remote-drift check.

## It is advisory, and that is the design

**No verdict ever stops the workflow on its own.** Every stop is a choice you
make at the prompt.

That is not timidity about a new feature. The evidence the check reasons over is
extracted from your plan's prose — and a path that a plan merely *runs* inside a
fenced command block looks exactly like one it declares it will edit. A real
example, measured on this repository: two in-flight tasks both wrote

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist my_new_helper
```

in their plans. Neither *edits* that script — both merely run it — yet it was
reported as their only conflict, while the five files they genuinely both edit
were rated too commonly-touched to flag.

A signal of that shape is worth showing you. It is not worth letting it cancel
your work. A future hard-stop mode is gated on tasks *declaring* the files they
intend to edit, rather than having them guessed from prose.

## The four verdicts

| Verdict | Meaning | What happens |
|---|---|---|
| `CLEAR` | no known conflict **at check time** | proceed |
| `CLEAR_CAVEATED` | no known conflict, but some evidence could not be verified | a visible note, or a confirmation under `confirm` |
| `CONFLICT` | another in-flight task declares one of your files | the tasks and files are named, and you choose |
| `UNCHECKABLE` | the evidence was not good enough to answer | the reason and its remedy are named, and you choose |

**`CLEAR` means "no known conflict at check time", never "safe to run in
parallel".** The check observes; it does not reserve. Another agent can claim an
overlapping file the instant after it passes.

`UNCHECKABLE` is never silently treated as `CLEAR` — and neither is a checker
that crashes, times out, or returns something unparseable. Missing evidence is
reported as missing.

## Configuration

One profile key, in `aitasks/metadata/profiles/<name>.yaml`:

```yaml
parallel_admission: warn    # confirm | warn | off
```

| Value | Behaviour |
|---|---|
| `confirm` | every non-`CLEAR` verdict asks before continuing |
| `warn` | the default **when the key is absent**: `CONFLICT` and `UNCHECKABLE` ask; `CLEAR_CAVEATED` is a visible note |
| `"off"` | the step does nothing at all |

Quote `"off"`. YAML reads a bare `off` as the boolean false — the framework
accepts both, but the quoted form says what it means.

There is deliberately **no `block` value**: nothing here blocks, and a value
named for a behaviour the step does not have would be a lie.

### Why all three shipped profiles ship `"off"`

`default`, `fast` and `remote` each opt out explicitly. This is an opt-out, not
a change of default — omit the key and you get `warn`.

The reason is availability, measured on 2026-09-02: **9 of 16 in-flight tasks
carried no plan file (56%)**, and an in-flight task's file surface is read from
its plan **only** — there is no fallback to the task body, unlike the candidate's
own surface. So **108 of 122** live candidates came back `UNCHECKABLE`. Enabled
by default that is a prompt on roughly nine picks in ten, with nothing actionable
to say — the fastest way to teach people to dismiss it.

Set `parallel_admission: warn` (or `confirm`) in your own profile to opt in.
Headless profiles should keep `"off"` regardless, since the other values prompt.

## When `UNCHECKABLE` keeps appearing

Every `UNCHECKABLE` names its cause and a remedy. The common ones are about
*other* tasks, not yours:

| Cause | Remedy |
|---|---|
| an in-flight task has no plan | plan it, or release its lock with `ait lock --unlock <id>` |
| an in-flight task's plan is stale — none of its paths exist | refresh or release that plan |
| the lock ref could not be read | check the network and re-run |
| **your own** plan declares no resolvable paths | add concrete repository paths to it |

The last row is the one worth acting on directly: a plan that names no real files
cannot be compared against anything.

## Related

- [Resource Admission](../resource-admission/) — the *other* question asked at
  this boundary: can this host afford to start? The two are distinct and neither
  is folded into the other. Correctness runs before capacity.
- [Execution Profiles](../execution-profiles/) — the full profile key reference.
- [Parallel Development](../../../workflows/parallel-development/) — running
  several agents against one repository.
