---
title: "aitasks"
linkTitle: "aitasks"
---

{{< blocks/cover title="" image_anchor="top" height="med" color="primary" >}}
<div class="mx-auto">
  <img src="imgs/logo_with_text.webp" alt="aitasks logo" style="max-width: 300px; margin-bottom: 1rem;">
  <p class="lead mt-2">AI-powered task management for code agents</p>
  <a class="btn btn-lg btn-primary me-3 mb-4" href="docs/">
    Documentation
  </a>
  <a class="btn btn-lg btn-secondary me-3 mb-4" href="https://github.com/beyondeye/aitasks">
    GitHub
  </a>
</div>
{{< /blocks/cover >}}

{{% blocks/section color="white" type="row" %}}

{{% blocks/feature icon="fa-file-text" title="File-Based Tasks" %}}
Tasks are plain Markdown files with YAML frontmatter. Version-controlled, human-readable, and tool-friendly. No external database or service needed.
{{% /blocks/feature %}}

{{% blocks/feature icon="fa-robot" title="Code Agent Integration" %}}
Purpose-built agent skills that guide task implementation, issue management, repository exploration, documentation, and code review workflows.
{{% /blocks/feature %}}

{{% blocks/feature icon="fa-code-branch" title="Parallel Development" %}}
Git worktrees, atomic task locking, and branch management enable multiple developers (or AI agents) to work on different tasks simultaneously without conflicts.
{{% /blocks/feature %}}

{{% /blocks/section %}}

{{% blocks/section color="dark" %}}
## Latest Releases

<div class="row justify-content-center">
<div class="col-lg-8">

- **[v0.15.0: One-step startup with `ait ide`, Live monitor TUI for agent panes, and Minimonitor side panel](blog/v0150-one-step-startup-with-ait-ide-live-monitor-tui-for-agent-panes-minimonitor/)** -- Apr 12, 2026
- **[v0.14.0: Browse Your Completed Tasks, Process Monitoring and Hard Kill, and Unified Launch Dialog with tmux Support](blog/v0140-browse-your-completed-tasks-process-monitoring-and-hard-kill-unified-launc/)** -- Mar 29, 2026
- **[v0.13.0: Diff Viewer TUI, Brainstorm Engine & TUI, and Standalone QA Skill](blog/v0130-diff-viewer-tui-brainstorm-engine-tui-standalone-qa-skill/)** -- Mar 23, 2026

[All releases &rarr;](blog/)

</div>
</div>

{{% /blocks/section %}}

{{% blocks/section color="light" %}}
## Quick Install

Run these commands in your project directory:

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
ait setup
```

See the [Installation guide](docs/installation/) for detailed setup instructions.
{{% /blocks/section %}}
