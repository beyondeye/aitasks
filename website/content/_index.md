---
title: "aitasks"
linkTitle: "aitasks"
---

{{< blocks/cover title="" image_anchor="top" height="med" color="primary" >}}
<div class="mx-auto">
  <img src="imgs/logo_with_text.webp" alt="aitasks logo" style="max-width: 300px; margin-bottom: 1rem;">
  <p class="lead mt-2">AI-powered task management for Claude Code</p>
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

{{% blocks/feature icon="fa-robot" title="Claude Code Integration" %}}
Purpose-built slash commands (`/aitask-pick`, `/aitask-explore`, `/aitask-review`) that guide Claude Code through task selection, planning, implementation, and review workflows.
{{% /blocks/feature %}}

{{% blocks/feature icon="fa-code-branch" title="Parallel Development" %}}
Git worktrees, atomic task locking, and branch management enable multiple developers (or AI agents) to work on different tasks simultaneously without conflicts.
{{% /blocks/feature %}}

{{% /blocks/section %}}

{{% blocks/section color="dark" %}}
## Latest Releases

<div class="row justify-content-center">
<div class="col-lg-8">

- **[v0.7.0: Run Tasks from Anywhere, Claude Code Web Support, and Full macOS Compatibility](blog/v070-run-tasks-from-anywhere-claude-code-web-support-full-macos-compatibility/)** -- Feb 25, 2026
- **[v0.6.0: Code Explanations, Wrap Skill, and Auto-Refresh Board](blog/v060-explain-wrap-file-select-autorefresh/)** -- Feb 22, 2026
- **[v0.5.0: Code Review, Multi-Platform Support, and Documentation Site](blog/v050-code-review-multi-platform-docs-site/)** -- Feb 20, 2026

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
