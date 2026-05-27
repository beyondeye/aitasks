---
priority: high
effort: low
depends: []
issue_type: bug
status: Done
labels: [website, changelog]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-27 12:25
updated_at: 2026-05-27 12:49
completed_at: 2026-05-27 12:49
---

## Problem

The blog page `/blog/v0210` does not render correctly on the Hugo/Docsy
website. Root cause: `website/content/blog/v0210-profile-aware-skill-templating-brainstorm-auto-apply-dag-navigation-and-op.md`
has invalid YAML frontmatter at line 5:

```yaml
description: "v0.21.0 is a big one — ... the brainstorm TUI graduating from "experiment" to a real DAG-driven planning workflow, ..."
```

The double-quoted `description:` value contains unescaped inner `"experiment"`
quotes, which terminate the YAML string early. Confirmed via
`yaml.safe_load`: *"expected <block end>, but found '<scalar>'"* at line 5.
Hugo therefore cannot parse the frontmatter, and the page renders incorrectly
(or with missing metadata).

A scan of the most recent ~10 blog posts shows only v0210 is affected today.

## Upstream cause in the generator

`website/new_release_post.sh` builds the blog frontmatter via a heredoc:

```bash
title: "$TITLE"
linkTitle: "v$VERSION"
description: "$DESCRIPTION"
```

`generate_description()` (lines 244-265) interpolates the first paragraph of
`CHANGELOG_HUMANIZED.md` directly as `$DESCRIPTION` without escaping inner
double quotes (or backslashes). `generate_title()` has the same risk. Any
future humanized changelog containing a quoted word will reproduce the bug.

## Fix scope

1. **Patch the live blog post.** In
   `website/content/blog/v0210-profile-aware-skill-templating-brainstorm-auto-apply-dag-navigation-and-op.md`
   line 5, escape the two inner double quotes around `experiment` (e.g.
   `\"experiment\"`) so the YAML parses. Verify with
   `python3 -c "import yaml; yaml.safe_load(open(...).read().split('---',2)[1])"`
   and by serving the website locally.

2. **Fix the generator.** In `website/new_release_post.sh`, escape `\` and
   `"` in `$TITLE` and `$DESCRIPTION` before the heredoc — e.g.
   `safe=${var//\\/\\\\}; safe=${safe//\"/\\\"}` — and emit the escaped
   value in the frontmatter. Mirror the same handling in the scaffold-mode
   heredoc only if its TODO placeholders are ever interpolated from user
   data (currently static strings, so likely no change needed).

3. **(Optional but recommended) Smoke check.** After writing the blog file,
   parse its YAML frontmatter (e.g. with a tiny Python one-liner) and fail
   the script with a clear error if it does not parse. This prevents the
   next silently-broken release post.

## Verification

- `python3 -c "import yaml; yaml.safe_load(open('website/content/blog/v0210-...md').read().split('---',2)[1])"`
  parses without error.
- `cd website && ./serve.sh` renders the v0.21.0 blog page with correct
  title, description, and body.
- A synthetic re-run of `website/new_release_post.sh` with a humanized
  changelog whose first paragraph contains `"quoted"` words produces a
  blog post whose frontmatter still parses as YAML.

## Files of interest

- `website/content/blog/v0210-profile-aware-skill-templating-brainstorm-auto-apply-dag-navigation-and-op.md`
  (line 5)
- `website/new_release_post.sh` (lines 215-242 `generate_title`, 244-265
  `generate_description`, 270-303 auto-mode heredoc)
