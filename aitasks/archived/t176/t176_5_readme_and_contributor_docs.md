---
priority: low
effort: low
depends: [t176_2, t176_4]
issue_type: documentation
status: Done
labels: [web_site]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-19 11:05
updated_at: 2026-02-19 15:14
completed_at: 2026-02-19 15:14
---

## Context
This is the fifth and final child task of t176 (Create Web Site). After content migration (t176_2) and the GitHub Actions workflow (t176_4) are in place, this task updates the project README with links to the live documentation site and creates a contributor guide for the Hugo website.

**GitHub repo:** https://github.com/beyondeye/aitasks
**Live site URL:** https://beyondeye.github.io/aitasks/

## Key Files to Create/Modify

1. **Modify `README.md`** — Add documentation website badge and link
2. **Create `website/README.md`** — Contributor guide for the Hugo website

## Reference Files for Patterns

- `README.md` — existing README to add badge/link to
- `website/hugo.toml` — created in t176_1, referenced in contributor docs
- `.github/workflows/hugo.yml` — created in t176_4, referenced in contributor docs

## Implementation Plan

### Step 1: Update README.md

Add near the top of `README.md` (after the title or in a badges section):
```markdown
[![Documentation](https://img.shields.io/badge/docs-website-blue)](https://beyondeye.github.io/aitasks/)
```

In the documentation section of README.md, add a link to the live site:
```markdown
**Documentation website:** https://beyondeye.github.io/aitasks/
```

### Step 2: Create website/README.md

Create a contributor guide at `website/README.md`:
```markdown
# aitasks Website

This directory contains the Hugo/Docsy website for aitasks.

## Prerequisites
- Hugo extended edition >= 0.155.3
- Go >= 1.23
- Dart Sass >= 1.97.3

## Local Development
\`\`\`bash
cd website
hugo server
\`\`\`
The site will be available at http://localhost:1313/aitasks/

## Adding Content
- Documentation pages go in `content/docs/`
- Each page needs Docsy frontmatter (title, linkTitle, weight, description)
- See existing pages for examples

## Deployment
Automatic on push to `main` via GitHub Actions. See `.github/workflows/hugo.yml`.
The site is deployed to https://beyondeye.github.io/aitasks/
```

### Step 3: Verify
1. README.md badge renders correctly on GitHub
2. `website/README.md` is accurate and references correct paths

## Verification Steps

1. `README.md` has the documentation badge near the top
2. Badge link points to `https://beyondeye.github.io/aitasks/`
3. `website/README.md` exists with accurate prerequisites and instructions
4. No broken markdown in either file
