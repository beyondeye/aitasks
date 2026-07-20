---
title: "Shadow Agent"
linkTitle: "Shadow Agent"
weight: 83
description: "Launch an advisory companion agent that reads a running agent's output, explains it, helps with prompts and plans, reviews the implementation, diagnoses failures, and spawns skill-learning sessions"
depth: [intermediate]
---

When you have a coding agent working a task, it is not always easy to follow what it is doing — its output can be dense, a plan it produced may assume background you don't have, or it may pause on a question whose context has scrolled away. The **shadow agent** is an advisory companion you launch beside the agent you are watching (the *followed agent*). It reads that agent's terminal output and helps you reason about it, in plain terms, on demand.

The shadow is **read-only and advisory by design**. It explains and suggests; it never types into the followed agent's pane. You remain the one who answers prompts and approves plans — the shadow just makes you a better-informed driver.

## Launching a shadow

You launch a shadow from the [minimonitor](../../tuis/minimonitor/) sidebar that sits next to each running agent: focus the agent's card and press **e**. By default the shadow opens as a new pane in the **same tmux window** as the followed agent, so the two sit side by side. (You can configure it to open in a separate window instead — see [Configuration](#configuration).)

The shadow is a companion pane, like minimonitor itself: it never appears in the agent list, and it closes automatically when the agent it shadows exits.

See [How to Launch a Shadow Agent](../../tuis/minimonitor/how-to/#how-to-launch-a-shadow-agent) for the minimonitor keybinding details.

## What happens once it is running

When the shadow starts, it greets you with a short summary of what it can do, then waits for you to tell it — in your own words — what you'd like. There is no mode to pick up front: you just describe what you want, and it routes to the right capability.

Two things are worth knowing:

- **It reads the followed agent's current screen, and can re-read it any time.** The agent keeps working after you launch the shadow, so its state changes. Ask the shadow to refetch whenever you want it to look at the latest output.
- **It offers help proactively.** Each time it reads the screen, the shadow glances at what is visibly there and, if something obviously useful applies, it offers it without being asked — for example, if the agent is paused on a question, it offers to help you decide; if a plan is on screen awaiting approval, it offers to explain or pressure-test it. These are suggestions you can take or ignore; they never restrict what you can ask for.
- **Some actions are on request only.** The shadow does not proactively diagnose errors or spawn learner agents. Ask for those actions explicitly when you want them.

## What the shadow can do

All of the following are served in a single flow — you reach them just by asking.

### Explain what the agent is doing

Ask "what is this agent doing right now?" (or about a specific error or message) and the shadow reads the current screen and explains, in plain terms, what is happening, what the agent is waiting on, or what a message means.

### Help you answer a prompt

When the followed agent is paused on a question — including one shown without the underlying task or plan visible — the shadow can fetch the relevant task and plan in the background, lay out what each option means and its trade-offs, and **suggest** an answer with its reasoning. You type the answer into the agent yourself; the shadow never does.

### Interrogate a plan

Before you approve a plan an agent has produced, the shadow can examine it for you in four distinct ways:

- **Explain it to a non-expert** — beyond a plain-terms summary, it identifies the technical subjects the plan rests on and offers, for each one you choose, a short introduction and why the plan relies on it, then walks through the plan in plain language.
- **Challenge it** — acting as a constructive adversary, it actively looks for where the plan could fail (regressions, missed edge cases, a wrong-shaped approach, blast radius, verification gaps, unstated dependencies) and gives you a prioritized list, separating problems that should block approval from improvements you could accept as follow-ups.
- **Question it (Socratic)** — instead of telling you what's wrong, it asks open-ended questions that lead you to examine the plan's own reasoning and trade-offs, a few at a time.
- **Surface its assumptions** — it enumerates what the plan quietly takes for granted (about the environment, the data, other code's behavior, sequencing, and scope) and highlights the assumptions that are both load-bearing and unverified — the ones most likely to make a plan silently go wrong.

Ask for one of these specifically, or ask broadly ("review this plan") and the shadow runs several and presents a combined result.

### Review the implementation

Once an agent has *implemented* a task — not just planned it — the shadow can adversarially review the **code that was actually written**. This is the implementation-side companion to challenging a plan. It reads the task and plan (what was supposed to be built), discovers the real change — the task's commits, or the uncommitted working-tree diff when the agent has not committed yet — and the plan's own *Final Implementation Notes*, then reviews at one of four **effort tiers**:

- **Quick** — a reduced, hunk-only scan of the diff: only correctness bugs visible from the changed lines themselves (plus obvious duplication and dead code), at most 4 findings, no verification pass. A fast sanity check; it runs only when you explicitly ask for it.
- **Default** — one full-context adversarial pass over the diff, the plan, its risks, and the Final Implementation Notes, along three axes: **implementation flaws** (bugs, missed cases, incorrect logic, or regressions in the code as actually written); **risks left unmitigated** (risks the plan flagged that the landed code does not address — already-handled risks are not re-flagged); and **unjustified deviations from the plan** (divergences the Final Implementation Notes do not explain). No findings cap.
- **Advanced** — the recommended systematic review. Ten targeted review angles run in sequence — a line-by-line diff scan, a removed-behavior audit (what invariant did each deleted line enforce, and where is it re-established?), caller/callee tracing across files, five cleanup angles (reuse, simplification, efficiency, altitude, project-convention violations), and the two plan axes above — followed by a verification pass that re-reads the code and grades every candidate finding **CONFIRMED**, **PLAUSIBLE**, or **REFUTED**; only the first two are reported. Tuned for precision: at most 8 findings, each one a maintainer would act on.
- **Deep** — the widest net. Adds language-pitfall and wrapper/delegation-correctness angles, biases verification toward recall (realistic-but-unconfirmed triggers are kept, not dismissed), and finishes with a gap-sweep pass hunting only for defects the earlier angles missed. Up to 15 findings.

Every finding states the problem, why it bites, and a severity, plus a **disposition**: `blocking` (should be addressed before the change is accepted) or `follow-up` (real, but sensible as a separate task). Findings are listed blocking-first, and in the Advanced and Deep tiers each finding also carries its verification verdict. A tier's findings cap never drops a blocking finding, and anything a cap omits is disclosed rather than silently cut.

Name a tier in your ask — "quick review of the implementation", "advanced review", "deep review". An unqualified "adversarial review" runs the Default tier; a generic "review the implementation" makes the shadow ask which tier you want, recommending Advanced. You can also narrow the focus in free text ("just check the callers", "only plan deviations") at any tier.

If the plan shows the implementation phase has not finished yet (no *Final Implementation Notes*), the shadow warns you it is probably too early to review and lets you stop or proceed against the partial state.

### Diagnose skill or helper errors

When the followed agent appears stuck on tool-call errors, tracebacks, shell errors, or repeated retries, ask the shadow to diagnose what is going wrong. It reads the captured screen, decides whether the visible signals are genuine failures rather than benign error-shaped text, and attributes each error cluster to the likely workflow skill or `aitask_*.sh` helper.

For real issues, the shadow presents candidate concerns and emits the same structured concern block used by plan review. You choose which concerns are worth acting on. For selected concerns, the shadow can offer to launch [`/aitask-explore`](../../skills/aitask-explore/) with a seed prompt that names the likely file and includes the captured error excerpt, so the bug becomes its own scoped fix-task. It never auto-launches that follow-up and never types into the followed pane.

### Learn a skill from the followed workflow

When the followed agent has just performed a workflow you want to reuse, ask the shadow to learn a skill from it. The shadow does not run the learning flow itself, because that would occupy the companion you are using for advice. Instead, it confirms the action and opens a dedicated learner agent in a new tmux window running [`/aitask-learn-skill`](../../skills/aitask-learn-skill/):

```text
/aitask-learn-skill <followed_pane_id>
```

The learner captures the followed pane read-only, walks you through selecting which part of the workflow to learn, asks how to generalize concrete details, and writes a static skill. The learner appears as a normal `agent-learn*` window in `ait monitor`; you close it when the learning session is done. The shadow remains available in its own pane.

### Forward concerns to the followed agent

When the shadow interrogates a plan, reviews an implementation, or diagnoses genuine skill/helper errors, alongside its human-readable findings it can emit a structured, machine-parseable **concern block** — a fenced list (`===AITASK-CONCERNS===` … `===END-CONCERNS===`) of `- [priority | region] body` items, where `priority` is `high`, `medium`, or `low` and `region` names the plan area, skill, or helper the concern targets. Implementation-review concerns are ordered blocking-first and carry their disposition (and, in the Advanced and Deep tiers, the verification verdict) inside the body text. The block is additive: the shadow still prints its normal prose; the block is an extra copy meant for pick-and-forward.

From [minimonitor](../../tuis/minimonitor/) you can then **selectively forward** these concerns to the followed agent without retyping them. Press **c** to open a checklist of the shadow's concerns, tick the ones you want, and minimonitor copies them — with a short preamble — to your clipboard for you to paste into the agent. When a fresh concern block appears, minimonitor also proactively hints that the shadow raised concerns. This keeps the advisory-only contract intact: the concerns land on *your* clipboard, and you decide what to paste. See [How to pick shadow concerns](../../tuis/minimonitor/how-to/#how-to-pick-shadow-concerns).

## Advisory only

The shadow is read-only with respect to the followed agent. It never sends keystrokes or answers into the agent's pane — not even an answer it just suggested. Everything it produces goes to you, and you decide what to do with it. This is the core contract of the shadow: it informs your decisions without ever making them for you.

## Configuration

Two settings control the shadow, both editable in [`ait settings`](../../tuis/settings/):

- **Placement** — `tmux.shadow_same_window` (Tmux tab). `true` (the default) splits the shadow into the followed agent's window; `false` opens it in its own window.
- **Agent and model** — the `shadow` row on the Agent Defaults tab selects which coding agent and model the shadow runs as. You can run the shadow as a lighter, faster model than the agent it watches.

---

**Next:** [Explain](../explain/) — use code evolution history to rebuild understanding of why code exists.
