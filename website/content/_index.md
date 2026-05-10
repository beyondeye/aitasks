---
title: "aitasks"
linkTitle: "aitasks"
---

{{< blocks/cover title="" image_anchor="top" height="auto" color="primary" >}}
{{< split-hero
    title="aitasks"
    lead="A full agentic IDE in your terminal."
    description="Kanban board, code browser, agent monitoring, and AI-enhanced git workflows — all in one tmux session. Press `j` to hop between TUIs without leaving the terminal."
    image="imgs/home/board.svg"
    image_alt="aitasks kanban board with three columns of task cards"
    cta_primary_text="Documentation"
    cta_primary_href="docs/"
    cta_secondary_text="⭐ Star on GitHub"
    cta_secondary_href="https://github.com/beyondeye/aitasks"
>}}{{< /split-hero >}}
{{< /blocks/cover >}}

{{% blocks/section color="white" type="row" %}}

{{% blocks/feature icon="fa-terminal" title="Agentic IDE in your terminal" url="#take-the-tour" %}}
Kanban Board, Code Browser, Monitor, Brainstorm, and Settings — all in one tmux session via `ait ide`. Press `j` to hop between TUIs without ever leaving the terminal.
{{% /blocks/feature %}}

{{% blocks/feature icon="fa-brain" title="Long-term memory for agents" url="/docs/concepts/agent-memory/" %}}
Archived tasks and plans become queryable context for future work. The Code Browser annotates each line back to the task and plan that introduced it — your repo remembers *why*, not just *what*.
{{% /blocks/feature %}}

{{% blocks/feature icon="fa-code-branch" title="Tight git coupling, AI-enhanced" url="/docs/workflows/#git" %}}
PR import/close, issue tracker integration, contribution flow, changelog generation, and AI-assisted reverts — all rooted in git commits and task metadata.
{{% /blocks/feature %}}

{{% /blocks/section %}}

{{% blocks/section color="light" %}}
## ⚡ Quick Install

Pick your platform:

| Platform | Install command |
|----------|-----------------|
| **macOS** | `brew install beyondeye/aitasks/aitasks` |
| **Arch / Manjaro** (AUR) | `yay -S aitasks` |
| **Debian / Ubuntu / WSL** | `.deb` from [Releases](https://github.com/beyondeye/aitasks/releases/latest), then `sudo apt install ./aitasks_*.deb` |
| **Fedora / RHEL / Rocky / Alma** | `.rpm` from [Releases](https://github.com/beyondeye/aitasks/releases/latest), then `sudo dnf install ./aitasks-*.noarch.rpm` |
| **Other (any POSIX)** | `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh \| bash` |

After installing, run `ait setup` in your project (the git repository root). See the [Installation guide]({{< relref "/docs/installation" >}}) for per-platform walkthroughs and detailed setup instructions.
{{% /blocks/section %}}

{{< blocks/section color="white" >}}
<div class="text-center mb-4">
<h2 id="take-the-tour">🎛️ Take the tour</h2>
<p>Five TUIs share a single tmux session. Click any of them to dive in.</p>
</div>
<div class="tour-mosaic">
{{< tour-tile href="/docs/tuis/board/" src="imgs/home/board.svg" alt="Kanban board" caption="Board" >}}
{{< tour-tile href="/docs/tuis/codebrowser/" src="imgs/home/codebrowser.svg" alt="Code browser" caption="Code Browser" >}}
{{< tour-tile href="/docs/tuis/monitor/" src="imgs/home/monitor.svg" alt="Monitor TUI" caption="Monitor" >}}
{{< tour-tile href="/docs/tuis/settings/" src="imgs/home/settings.svg" alt="Settings TUI" caption="Settings" >}}
{{< tour-tile href="/docs/tuis/stats/" src="imgs/home/statistics.svg" alt="Statistics TUI" caption="Stats" >}}
</div>
<div class="text-center mt-4">
<a href="/docs/tuis/">See all TUIs &rarr;</a>
</div>
{{< /blocks/section >}}

{{% blocks/section color="white" %}}
## 🧩 Task decomposition & parallelism

{{< static-img src="imgs/home/child_tasks.svg" alt="Parent task decomposed into child subtasks" caption="A parent task automatically broken into well-scoped child subtasks." >}}

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

{{< static-img src="imgs/home/codebrowser.svg" alt="Code browser annotated with task history" caption="Code browser annotates each line back to the originating task and plan." >}}

Reviews aren't a checklist — they're a workflow. **aitasks** treats review guides, QA, and code explanations as first-class citizens with traceability back to the originating task.

- Per-language review guides, automatically suggested for changed files
- Batched multi-file reviews that produce follow-up tasks, not just comments
- QA workflow that turns review findings into testable child tasks
- Code explanations that trace each line back to the task and commit that introduced it

See [Code review]({{< relref "/docs/workflows/code-review" >}}) and [QA testing]({{< relref "/docs/workflows/qa-testing" >}}).
{{% /blocks/section %}}

{{% blocks/section color="light" %}}
## 🤖 Multi-agent support with verified scores

{{< static-img src="imgs/home/monitor.svg" alt="Monitor TUI showing live agent panes" caption="Watch multiple agents work side-by-side in the monitor TUI." >}}

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

- **[v0.20.1 Release](blog/v0201/)** -- May 10, 2026
- **[v0.20.0: Install via your distro's package manager, A dedicated syncer TUI, and Opt-in PyPy fast-path](blog/v0200-install-via-your-distro-s-package-manager-a-dedicated-syncer-tui-opt-in-py/)** -- May 6, 2026
- **[v0.19.2: Python wrappers that actually stay inside the venv, Warnings before you build on stale main, and Source-tree setup gets the starter tmux config too](blog/v0192-python-wrappers-that-actually-stay-inside-the-venv-warnings-before-you-bui/)** -- Apr 29, 2026

[All releases &rarr;](blog/)

</div>
</div>

{{% /blocks/section %}}
