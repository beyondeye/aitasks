---
title: "aitasks"
linkTitle: "aitasks"
---

{{< blocks/cover title="" image_anchor="top" height="med" color="primary" >}}
<div class="mx-auto">
  <img src="imgs/logo_with_text.webp" alt="aitasks logo" style="max-width: 300px; margin-bottom: 1rem;">
  <p class="lead mt-2">A full agentic IDE in your terminal.</p>
  <p>Kanban board, code browser, agent monitoring, and AI-enhanced git workflows.</p>
  <a class="btn btn-lg btn-primary me-3 mb-4" href="docs/">
    Documentation
  </a>
  <a class="btn btn-lg btn-secondary me-3 mb-4" href="https://github.com/beyondeye/aitasks">
    ⭐ Star on GitHub to support us!
  </a>
</div>
{{< /blocks/cover >}}

{{% blocks/section color="white" type="row" %}}

{{% blocks/feature icon="fa-terminal" title="Agentic IDE in your terminal" %}}
Kanban Board, Code Browser, Monitor, Brainstorm, and Settings — all in one tmux session via `ait ide`. Press `j` to hop between TUIs without ever leaving the terminal.
{{% /blocks/feature %}}

{{% blocks/feature icon="fa-brain" title="Long-term memory for agents" %}}
Archived tasks and plans become queryable context for future work. The Code Browser annotates each line back to the task and plan that introduced it — your repo remembers *why*, not just *what*.
{{% /blocks/feature %}}

{{% blocks/feature icon="fa-code-branch" title="Tight git coupling, AI-enhanced" %}}
PR import/close, issue tracker integration, contribution flow, changelog generation, and AI-assisted reverts — all rooted in git commits and task metadata.
{{% /blocks/feature %}}

{{% /blocks/section %}}

{{% blocks/section color="light" %}}
## ⚡ Quick Install

Run these commands in your project directory:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
ait setup
```

See the [Installation guide]({{< relref "/docs/installation" >}}) for detailed setup instructions.
{{% /blocks/section %}}

{{% blocks/section color="white" %}}
## 🧩 Task decomposition & parallelism

Complex tasks rarely fit a single context window. **aitasks** breaks them into child tasks, propagates sibling context, and runs them in isolated git worktrees so multiple agents can work side by side without stepping on each other.

- Auto-explode complex tasks into well-scoped child tasks during planning
- Sibling context propagation — each child sees what came before
- Git worktrees + atomic locks for true parallel agent work
- Plan verification tracking so picked-up work resumes safely

See [Task decomposition]({{< relref "/docs/workflows/task-decomposition" >}}) and [Parallel development]({{< relref "/docs/workflows/parallel-development" >}}).
{{% /blocks/section %}}

{{% blocks/lead color="light" %}}
**Tasks are living documents, not rigid specifications.** Start with raw intent. Let the AI refine context iteratively. Ship when the spec and the code converge.
{{% /blocks/lead %}}

{{% blocks/section color="white" %}}
## 🔍 AI-enhanced code review

Reviews aren't a checklist — they're a workflow. **aitasks** treats review guides, QA, and code explanations as first-class citizens with traceability back to the originating task.

- Per-language review guides, automatically suggested for changed files
- Batched multi-file reviews that produce follow-up tasks, not just comments
- QA workflow that turns review findings into testable child tasks
- Code explanations that trace each line back to the task and commit that introduced it

See [Code review]({{< relref "/docs/workflows/code-review" >}}) and [QA testing]({{< relref "/docs/workflows/qa-testing" >}}).
{{% /blocks/section %}}

{{% blocks/section color="light" %}}
## 🤖 Multi-agent support with verified scores

One framework, many code agents. **aitasks** unifies Claude Code, Gemini CLI, Codex CLI, and OpenCode under a single `codeagent` wrapper, then accumulates per-model and per-operation success scores from real user feedback.

- Drop-in support for Claude Code, Gemini CLI, Codex CLI, OpenCode
- Per-operation scoring (planning, implementation, review) instead of generic benchmarks
- Verified scores accumulate from your team's actual usage, not synthetic tests
- Switch agents per-task without rewriting workflows

See [`codeagent` command]({{< relref "/docs/commands/codeagent" >}}) and [Verified scores]({{< relref "/docs/skills/verified-scores" >}}).
{{% /blocks/section %}}

{{% blocks/section color="white" type="row" %}}

{{% blocks/feature icon="fab fa-linux" title="Linux" url="docs/installation/" %}}
Arch, Ubuntu, Fedora, and others.
{{% /blocks/feature %}}

{{% blocks/feature icon="fab fa-apple" title="macOS" url="docs/installation/" %}}
Tested on recent versions.
{{% /blocks/feature %}}

{{% blocks/feature icon="fab fa-windows" title="Windows" url="docs/installation/windows-wsl/" %}}
Supported via WSL.
{{% /blocks/feature %}}

{{% /blocks/section %}}

{{% blocks/section color="dark" %}}
## 📦 Latest Releases

<div class="row justify-content-center">
<div class="col-lg-8">

- **[v0.18.2: Multi-session stats in the TUI, Monitor and minimonitor handle cross-session agents correctly, and Agent crews that recover instead of erroring out](blog/v0182-multi-session-stats-in-the-tui-monitor-and-minimonitor-handle-cross-sessio/)** -- Apr 26, 2026
- **[v0.18.1: Triage manual-verification checklists in batches, Filter the board by issue type, and `ait upgrade` actually upgrades branch-mode setups now](blog/v0181-triage-manual-verification-checklists-in-batches-filter-the-board-by-issue/)** -- Apr 26, 2026
- **[v0.18.0: Your monitor and minimonitor now see every project at once, The TUI switcher teleports across sessions, and `ait install` is now `ait upgrade`](blog/v0180-your-monitor-and-minimonitor-now-see-every-project-at-once-the-tui-switche/)** -- Apr 24, 2026

[All releases &rarr;](blog/)

</div>
</div>

{{% /blocks/section %}}
