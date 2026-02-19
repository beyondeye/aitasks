---
priority: medium
effort: medium
depends: [t176_1]
issue_type: feature
status: Done
labels: [web_site]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-19 11:04
updated_at: 2026-02-19 12:33
completed_at: 2026-02-19 12:33
---

## Context
This is the third child task of t176 (Create Web Site). After the Hugo site scaffold is set up (t176_1), this task builds the landing/home page with Docsy block shortcodes and customizes the site branding. This task can run in parallel with t176_2 and t176_4.

**GitHub repo:** https://github.com/beyondeye/aitasks
**Owner GitHub:** https://github.com/beyondeye
**Owner X/Twitter:** DElyasy72333
**Target site URL:** https://beyondeye.github.io/aitasks/

## Key Files to Create/Modify

1. **`website/content/_index.md`** — Full landing page with Docsy blocks (hero, features, quick install)
2. **`website/assets/scss/_variables_project.scss`** — Brand color overrides
3. **`website/content/about/_index.md`** — About page with project/author info (if not created by t176_2)

## Reference Files for Patterns

- `website/content/_index.md` — placeholder created in t176_1 that we're expanding
- `website/assets/scss/_variables_project.scss` — empty placeholder from t176_1
- `README.md` — project description text to adapt for the landing page
- Docsy example site landing pages at https://www.docsy.dev/docs/adding-content/shortcodes/

## Implementation Plan

### Step 1: Build landing page with Docsy shortcodes

Replace `website/content/_index.md` with a full landing page using Docsy's block shortcodes:

```markdown
---
title: "aitasks"
linkTitle: "aitasks"
---

{{< blocks/cover title="aitasks" image_anchor="top" height="med" color="primary" >}}
<div class="mx-auto">
  <p class="lead mt-4">AI-powered task management for Claude Code</p>
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

{{% blocks/section color="light" %}}
## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
```

Then run `ait setup` in your project directory to initialize.

See the [documentation](docs/) for detailed setup and usage guides.
{{% /blocks/section %}}
```

### Step 2: Customize brand colors

Edit `website/assets/scss/_variables_project.scss`:
```scss
// Brand colors for aitasks
$primary: #7C3AED;  // Purple - developer tool feel
$secondary: #1E40AF;  // Deep blue accent
```

### Step 3: Create/update About page

Create `website/content/about/_index.md` (if not already created by t176_2):
```markdown
---
title: "About aitasks"
linkTitle: "About"
weight: 30
menu:
  main:
    weight: 30
---

## About aitasks

aitasks is an AI-powered task management framework designed for Claude Code. It provides a file-based, version-controlled approach to managing development tasks, with deep integration into Claude Code's slash command system.

## Author

- **GitHub:** [beyondeye](https://github.com/beyondeye)
- **X/Twitter:** [@DElyasy72333](https://x.com/DElyasy72333)

## License

aitasks is licensed under the [MIT License with Commons Clause](https://github.com/beyondeye/aitasks/blob/main/LICENSE).

## Links

- [GitHub Repository](https://github.com/beyondeye/aitasks)
- [Documentation](../docs/)
- [Changelog](https://github.com/beyondeye/aitasks/blob/main/CHANGELOG.md)
```

### Step 4: Verify
```bash
cd website
hugo server
```
Check landing page renders with hero, feature cards, and quick install section.

## Verification Steps

1. Landing page shows hero section with title and CTA buttons
2. Three feature cards render correctly below the hero
3. Quick install section shows the curl command in a code block
4. About page accessible from navigation
5. Brand colors (purple primary) are applied throughout the site
6. No SCSS compilation errors
