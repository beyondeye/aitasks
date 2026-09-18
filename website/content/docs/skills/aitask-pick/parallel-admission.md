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

The **parallel-admission preflight** asks that question at the
planning→implementation boundary, immediately after the remote-drift check.

There is a second, opt-in place the same question can be asked: *before the task
is claimed at all*, where you would naturally ask it. That one reads what the
in-flight tasks' **descriptions** say they touch rather than their plans — see
[Pre-claim assessment (opt-in)](#pre-claim-assessment-opt-in) below. Two call
sites, two qualities of evidence, one checker.

## It is advisory, and that is the design

**No verdict ever stops the workflow on its own.** Every stop is a choice you
make at the prompt.

That is not timidity about a new feature. The evidence the check reasons over is
extracted from prose — your plan's, and (for an in-flight task that has no plan
yet) its task description — and a path that a plan merely *runs* inside a fenced
command block looks exactly like one it declares it will edit. A real
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

**Where `CLEAR_CAVEATED` usually comes from.** A task that has been claimed but
not yet planned has no plan file to read, so its surface is derived from its task
**description** instead. That is real evidence, but weaker: descriptions cite
files as background as readily as they name edit targets. So a description-derived
overlap is reported as an advisory note on a `CLEAR_CAVEATED` verdict — never as a
`CONFLICT`:

```
VERDICT:CLEAR_CAVEATED
CAVEAT:inflight:1725|task_declared_overlap:.aitask-scripts/lib/task_utils.sh
DISPLAY:no known conflict; evidence unverified for t1725 (description-derived)
```

Read that as *"an overlap **was** found — t1725's description names
`task_utils.sh`, which your task also touches — but the only evidence for it is a
description, so it is reported as advisory rather than as a `CONFLICT`"*. It is
not an all-clear. A description cites files as background as often as it names
edit targets, so check whether t1725 actually intends to edit that file before
you decide.

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

**It ships off for two measured reasons** (measured 2026-09-17 over 131 live
candidates):

| | |
|---|---|
| verdicts | 0 `CLEAR` · 86 `CLEAR_CAVEATED` · 31 `CONFLICT` · 14 `UNCHECKABLE` |
| how often `warn` would prompt | 45 of 131 picks — **34%**, above the 30% bar set for flipping the default |
| prompt quality | of 6 sampled `CONFLICT` verdicts, **1** was a genuine edit collision |

The quality number is the more important one. The five others named a file that
only *one* side edits and the other merely runs or cites — a test both plans
execute, a guard script one plan mentions in passing. Enabled by default, most
conflict prompts would be about files nobody is going to fight over, which is the
fastest way to teach people to dismiss the prompt that matters.

The remaining `UNCHECKABLE` causes are now narrow: 5 plans whose declared paths
no longer exist, and 9 that declare no usable path at all.

Set `parallel_admission: warn` (or `confirm`) in your own profile to opt in.
Headless profiles should keep `"off"` regardless, since the other values prompt.

## Pre-claim assessment (opt-in)

The preflight runs one plan *later* than the moment you actually want the answer:
by the time it speaks, the task is claimed, locked and planned. The **pre-claim
parallel-safety assessment** answers the same question before any of that —
right after you pick a task, before `aitask-pick` hands off and claims it.

It is off unless you ask for it:

```yaml
parallel_assessment: show   # "off" (default, and when the key is absent) | show | ask
```

| Value | Behaviour |
|---|---|
| `"off"` | nothing happens — no checker call, no reading, no prompt, and no cost on a normal pick |
| `show` | the assessment is displayed; you are prompted only if something is graded as overlapping, or the checker could not be used |
| `ask` | the assessment is displayed and you are always prompted |

What it does: takes the live in-flight population from the checker, reads each
live task's description (and its plan, if it has one), and grades each one
`overlaps` / `adjacent` / `unrelated` / `not assessed` with a concrete reason —
the same file, the same procedure, the same subsystem. The checker's own one-line
verdict is printed beneath it, labelled as the deterministic view.

Two things it will not do. It will never say "safe to run in parallel": when
anything was left unread, or the checker answered with gaps, the recommendation
is **incomplete**, and it names each gap. And it never stops the workflow — the
options are "Pick anyway", "Pick a different task" and "Stop", and nothing has
been claimed yet, so none of them has anything to undo. In a headless profile it
never prompts at all, in either mode.

## When `UNCHECKABLE` keeps appearing

Every `UNCHECKABLE` names its cause and a remedy. The common ones are about
*other* tasks, not yours:

| Cause | Remedy |
|---|---|
| an in-flight task has no plan **and** no path-bearing description | plan it, name its files in its description, or release its lock with `ait lock --unlock <id>` |
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
