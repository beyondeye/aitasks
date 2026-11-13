---
title: "Known Agent Issues"
linkTitle: "Known Issues"
weight: 70
description: "Known integration caveats for ai code agents used with aitasks"
depth: [intermediate]
---

This page tracks current workflow issues by code agent. Issues are grouped by agent below.

## Claude Code

#### Medium-effort models can miss workflow steps

In strict multi-step `aitask-*` workflows, medium-effort models may skip required checkpoints or finalization steps.

Use stronger reasoning/model settings when you need reliable workflow compliance. If the agent stops mid-workflow before a final step (for example, the satisfaction-rating prompt), nudge it to *"continue the workflow"* or *"finish the workflow"* to complete the remaining steps.

## Codex CLI

#### Interactive checkpoints

`ait setup` registers a small question server, `aitask_questions`, in the generated Codex config (`.codex/config.toml`) and installs the Python package it needs. The interactive workflow checkpoints — task confirmation, plan approval, commit review — are asked through it and appear as a form in the Codex pane. Restart Codex after running `ait setup`: Codex loads the server only when it starts.

- **A form you do not answer is never an answer.** After five minutes the form closes, the agent says which question is waiting and ends its turn. Type your answer at the ordinary prompt and the workflow continues with the next question. Nothing is defaulted and no work that depends on the answer starts in the meantime.
- **Esc postpones a form.** The question stays open and can be answered at the prompt in the same way.
- **Questions survive a restart.** Answers already given are kept; a new Codex session picks the open question up again.
- **Multi-select questions are paged.** Each page takes a line such as `{"selected":["t12","t15"],"action":"next"}`; the form lists the ids on the page and the actions it accepts.
- **Approvals are checked, not assumed.** In a Codex session the plan approval, the commit review and the merge approval are recorded only together with the answered question they came from. If the plan file is rewritten after you approved it, or the task's plan was approved in another agent, Codex asks you to approve it again when the task is resumed.
- **The reviewed change is committed for you.** After you approve the review, the commit is built from the files as they were when the question was asked. An edit made after that stays in your working tree, uncommitted.
- **A commit hook that rewrites files stops the reviewed commit.** A `pre-commit` hook may check the change and reject it. If the hook reformats or re-stages files, nothing is committed: apply the hook's changes yourself and approve the review again.
- **A merge approval is for one revision.** The merge lands exactly the commits you approved. If the task branch gains a commit after you approve, the merge is refused and Codex asks again.
- **A task with an open approval is not archived.** While a plan, review or merge question of the task is unanswered, declined or no longer current, archiving is refused until the question is settled.
- **Notes added to an approved plan ask again.** Ticking a plan's checkboxes keeps its approval. Any text added to the plan after approval means Codex asks you to approve the plan again if the task is resumed before its review. Archiving a finished task accepts only the closing notes the workflow adds at the end of the plan.
- **A question waiting at the prompt is flagged.** `ait monitor` and `ait minimonitor` show the pane as awaiting input both while a form is open and after it has fallen back to the prompt, until you answer or cancel it or the session ends. For a Codex you started by hand rather than through `ait`, the monitor cannot tell which of your hand-started Codex panes in the project holds the question, so it marks each of them `ASKED?` instead of `PROMPT`, and counts them as `asked?` rather than `awaiting`, until the question is answered.

If the server cannot start, Codex lists it as failed under `/mcp` and the agent asks its questions in plain text instead. Run `ait setup` again to repair it.

Asking is necessary but not sufficient for reliable compliance: see [Reasoning effort and workflow compliance](#reasoning-effort-and-workflow-compliance) below.

> `ait codeagent invoke` launches every Codex skill in Codex's default mode.

#### Composer animation and idle detection

With some models (currently the Astra family, such as `gpt-6-astra`), Codex animates a field of twinkling dots around the idle input box. The dots are visible characters, so `ait monitor` and `ait minimonitor` would never see such a pane go idle, and a shadow agent would never read as ready for an automatic recheck. The framework therefore turns off that one effect, and only that one:

- `ait codeagent invoke` and `ait skillrun` pass `-c tui.whimsy=false -c tui.effects.starfield=false` to every Codex launch, including shadow agents and restored sessions. Both keys are passed because older Codex versions recognize only `tui.whimsy` and newer ones use `tui.effects.starfield`. A command-line override takes precedence over every config file, so framework-launched Codex panes never draw the dots.
- The same launches also pass `-c tui.animations=true`. `tui.animations` is Codex's switch for all of its TUI animations: with it off, the `Working (Ns • esc to interrupt)` timer stops updating while the agent works, so the monitor would read a working Codex pane as idle.
- `ait setup` adds `whimsy = false` under `[tui]` and `starfield = false` under `[tui.effects]` to `.codex/config.toml`, each only when the project config does not already set it, so an explicit project value is kept. The two keys mean the same thing, so if your project sets one of them (for example `whimsy = true` to keep the dots), setup gives the other one the same value. Codex reads a project's `.codex/config.toml` only when the project is trusted.
- If `.codex/config.toml` sets `animations = false` under `[tui]`, has no `whimsy` key, and has no `[tui.effects]` table (not even one for an unrelated effect such as `welcome`), `ait setup` removes that line and prints a notice, but only in a run where it also adds the two keys above. Because of that, this happens at most once: an `animations = false` you add back afterwards is kept.

If you start Codex by hand outside a trusted project, pass `-c tui.whimsy=false -c tui.effects.starfield=false`, or set the same keys in `~/.codex/config.toml`. Avoid `animations = false` unless you accept that the working timer stops updating. A desktop "reduce motion" accessibility setting has the same effect on Codex, so the monitor can misread working Codex panes on a host that has it on.

#### Scrollback in Codex panes

Recent Codex versions draw their interface on the terminal's alternate screen, where tmux keeps no scrollback. A pane in that mode loses its earlier output for tmux copy mode and for shadow-agent and monitor captures. `ait codeagent invoke` and `ait skillrun` therefore pass `-c tui.alternate_screen=never` to every Codex launch, including shadow agents and restored sessions, so framework-launched Codex panes run inline and keep their scrollback. If you start Codex by hand and want the same behavior, pass the same option.

#### Reasoning effort and workflow compliance

Set Codex's reasoning effort to **at least `high`** when running the `aitask-*` workflow. At lower effort, Codex may silently skip required non-skippable workflow steps and treat the archive as the end of the workflow even when the interactive prompts are available. Raising the effort to `high` resolves most of these compliance problems.

Some skipped prompts are *not* compliance failures: execution profiles such as `fast` deliberately pre-answer prompts like task confirmation, email, and worktree creation. Those skips are expected — the caveat here is only about steps no profile pre-answers.

**Workaround:** even at `high` effort, Codex may occasionally stop mid-workflow before a final step (for example, the satisfaction-rating prompt). If it does, prompt it to *"continue the workflow"* or *"finish the workflow"* so it completes the remaining steps. This is not unique to Codex (see [Medium-effort models can miss workflow steps](#medium-effort-models-can-miss-workflow-steps)).

#### Model self-identification is unreliable

Codex CLI models cannot reliably self-report their model ID when prompted. The framework falls back to reading the configured model from `~/.codex/config.toml`, but this may not reflect the actual model if it was overridden at invocation time via CLI flags.

**Workaround:** Launch Codex CLI via [`ait codeagent invoke`](../../commands/codeagent/) instead of calling `codex` directly. The wrapper sets the `AITASK_AGENT_STRING` environment variable with the correct agent string, ensuring accurate `implemented_with` metadata.

## OpenCode

#### Plan mode may skip task locking

When OpenCode runs in plan mode, interactive skills (`aitask-pick`, `aitask-explore`, `aitask-review`, `aitask-fold`) may skip the task locking step because plan mode restricts the agent to read-only tools.

**Recommendation:** Use OpenCode in regular mode (not plan mode) for interactive skills that acquire task locks. These skills have their own internal planning phases.

#### Shallow implementation plans

OpenCode may produce high-level overviews instead of detailed step-by-step implementation plans during the task-workflow planning phase. The `opencode_planmode_prereqs.md` file contains explicit instructions to mitigate this, but results may vary by model.

**Workaround:** If the agent produces a shallow plan, prompt it directly: *"Please make a detailed plan of which files will be edited with which changes."* This usually triggers the agent to expand the plan with specific file paths, exact modifications, and code snippets.

## References

- Codex CLI docs: [Codex CLI overview](https://developers.openai.com/codex/cli) and [approval modes](https://developers.openai.com/codex/cli/features#approval-modes)
- aitasks Codex mapping note: [`.agents/skills/codex_tool_mapping.md`](https://github.com/beyondeye/aitasks/blob/main/.agents/skills/codex_tool_mapping.md)
- OpenCode plan mode prereqs: [`.opencode/skills/opencode_planmode_prereqs.md`](https://github.com/beyondeye/aitasks/blob/main/.opencode/skills/opencode_planmode_prereqs.md)
- [`ait codeagent`](../../commands/codeagent/) — unified agent wrapper with `AITASK_AGENT_STRING` support

---

**Next:** [Git Remotes]({{< relref "git-remotes" >}})
