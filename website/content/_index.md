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

- **[v0.16.1: Claude Opus 4.7 is now the default, Fuzzy file search in the codebrowser, and Structured brainstorming](blog/v0161-claude-opus-4-7-is-now-the-default-fuzzy-file-search-in-the-codebrowser-st/)** -- Apr 18, 2026
- **[v0.16.0: Interactive agent launch mode, File references on tasks, and Plan verification tracking](blog/v0160-interactive-agent-launch-mode-file-references-on-tasks-plan-verification-t/)** -- Apr 15, 2026
- **[v0.15.1: Scroll back through your agent's output, `ait ide` from a fresh shell just works, TUI switcher, and  now documented](blog/v0151-scroll-back-through-your-agent-s-output-ait-ide-from-a-fresh-shell-just-wo/)** -- Apr 13, 2026

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
