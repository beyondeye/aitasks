---
title: "About"
linkTitle: "About"
weight: 30
menu:
  main:
    weight: 30
---

{{< blocks/cover title="About aitasks" height="min" color="primary" >}}
<p class="lead mt-2">The story behind the framework</p>
{{< /blocks/cover >}}

{{% blocks/section color="white" %}}
## How **aitasks** Started

**aitasks** began in February 2026 as a tool born out of professional work as an Android developer. The problem was clear: AI coding agents like Claude Code had become capable enough to handle real development tasks, but the bottleneck had shifted to **intent transfer** — getting structured, contextual instructions to the agent fast enough that the human didn't become the slowdown.

Existing approaches fell into two extremes: heavyweight spec-driven systems that demanded upfront formality, and ad-hoc prompt engineering that didn't scale across tasks. **aitasks** carved out a middle path — **"Light Spec" task files** that start as raw intent and get iteratively refined by the AI agent itself before implementation begins.

Inspired by [Conductor](https://github.com/gemini-cli-extensions/conductor)'s repository-centric model and [Beads](https://github.com/steveyegge/beads)' task-based workflow, **aitasks** combined these ideas with Claude Code's skill system to create a framework where tasks, plans, and workflow automation all live inside the project repository — no external services, no databases, no daemons.
{{% /blocks/section %}}

{{% blocks/lead color="light" %}}
**Our approach:** Tasks are living documents, not rigid specifications. Start with raw intent. Let the AI refine context iteratively. Ship when the spec and the code converge.
{{% /blocks/lead %}}

{{% blocks/section color="white" type="row" %}}

{{% blocks/feature icon="fa-star" title="Open Source" %}}
<p>
<a href="https://github.com/beyondeye/aitasks/stargazers">
  <img src="https://img.shields.io/github/stars/beyondeye/aitasks?style=social" alt="GitHub Stars">
</a>
</p>
<p>
<a href="https://github.com/beyondeye/aitasks">
  <img src="https://img.shields.io/github/last-commit/beyondeye/aitasks" alt="Last Commit">
</a>
</p>
<p>
<a href="https://github.com/beyondeye/aitasks/releases">
  <img src="https://img.shields.io/github/v/release/beyondeye/aitasks" alt="Latest Release">
</a>
</p>
{{% /blocks/feature %}}

<!-- Update these stats at each release -->
{{% blocks/feature icon="fa-code" title="By the Numbers" %}}
**6 releases** since February 2026<br>
**17 Claude Code skills** built-in<br>
**5 platforms** fully supported<br>
**28+ CLI scripts** in the framework
{{% /blocks/feature %}}

{{% blocks/feature icon="fa-users" title="Community" url="https://github.com/beyondeye/aitasks/issues" url_text="Open an Issue" %}}
Contributions welcome. Whether it's a bug report, feature request, or pull request — the project is built in the open and developed with the same tools it provides.
{{% /blocks/feature %}}

{{% /blocks/section %}}

{{% blocks/section color="dark" %}}
## Created By

<div class="row justify-content-center">
<div class="col-lg-8">
<div class="d-flex align-items-center mb-3" style="gap: 1.5rem;">
  <img src="https://github.com/beyondeye.png" alt="Dario Elyasy"
       style="width: 80px; height: 80px; border-radius: 50%;">
  <div>
    <h3 class="mb-1">Dario Elyasy</h3>
    <p class="mb-0">
      <a href="https://github.com/beyondeye" class="text-light me-3">
        <i class="fab fa-github"></i> beyondeye
      </a>
      <a href="https://x.com/DElyasy72333" class="text-light">
        <i class="fab fa-twitter"></i> DElyasy72333
      </a>
    </p>
  </div>
</div>

**aitasks** is built and maintained by Dario Elyasy. The framework grew out of real production use — every feature was driven by the need to ship code faster with AI coding agents.

</div>
</div>
{{% /blocks/section %}}

{{% blocks/section color="light" %}}
## License

<div class="row justify-content-center">
<div class="col-lg-8">

**aitasks** is released under the **Apache License 2.0** with a **[Commons Clause](https://commonsclause.com/)** restriction.

| You can | You cannot |
|---------|------------|
| Use, copy, and modify freely | Sell aitasks itself as a standalone product |
| Use **aitasks** to power your commercial products | Offer a paid hosted aitasks service |
| Use with explicit patent protection from contributors | |
| Distribute and sublicense | |

See the full [LICENSE](https://github.com/beyondeye/aitasks/blob/main/LICENSE) on GitHub.

</div>
</div>
{{% /blocks/section %}}

{{% blocks/section color="white" type="row" %}}

{{% blocks/feature icon="fa-code-branch" title="GitHub" url="https://github.com/beyondeye/aitasks" url_text="Repository" %}}
Source code, releases, and issue tracker.
{{% /blocks/feature %}}

{{% blocks/feature icon="fa-book" title="Documentation" url="../docs/" url_text="Read the Docs" %}}
Installation guides, command reference, and workflow tutorials.
{{% /blocks/feature %}}

{{% blocks/feature icon="fa-tags" title="Release Notes" url="../blog/" url_text="All Releases" %}}
Changelog and release announcements for every version.
{{% /blocks/feature %}}

{{% /blocks/section %}}
