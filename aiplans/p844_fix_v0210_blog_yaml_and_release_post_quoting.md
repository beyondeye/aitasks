---
Task: t844_fix_v0210_blog_yaml_and_release_post_quoting.md
Worktree: (none — fast profile, working on current branch)
Branch: main (current)
Base branch: main
---

# Plan — Fix v0.21.0 blog YAML and prevent recurrence in `new_release_post.sh`

## Context

The blog page `/blog/v0210` does not render correctly on the Hugo/Docsy
website. Root cause: the YAML frontmatter in
`website/content/blog/v0210-profile-aware-skill-templating-brainstorm-auto-apply-dag-navigation-and-op.md`
contains an unescaped inner `"experiment"` quote inside the double-quoted
`description:` value (line 5). YAML terminates the string early at the first
inner quote — confirmed by `yaml.safe_load`:

```
YAML ERROR: expected <block end>, but found '<scalar>'
in line 5, column 141: ...brainstorm TUI graduating from "experiment" to a real...
```

Upstream cause: `website/new_release_post.sh` interpolates the title and the
first paragraph of `CHANGELOG_HUMANIZED.md` directly into a heredoc as
`description: "$DESCRIPTION"` / `title: "$TITLE"` (auto-mode, lines 275–296)
without escaping inner double quotes or backslashes. `generate_description()`
(lines 244–265) and `generate_title()` (lines 215–242) both produce values
that may contain `"` characters whenever the humanized changelog phrases use
quoted words. Any future release whose first humanized paragraph contains
`"quoted"` will repeat this bug.

Scan of the 10 most recent posts shows only v0210 is currently broken.

## Files to modify

1. **`website/content/blog/v0210-profile-aware-skill-templating-brainstorm-auto-apply-dag-navigation-and-op.md`**
   - Line 5: backslash-escape the two inner double quotes around
     `experiment` inside the `description:` value.

2. **`website/new_release_post.sh`**
   - Add a small helper `yaml_escape_dq` (escape `\` then `"` in that order)
     and apply it to both `$TITLE` and `$DESCRIPTION` immediately before the
     auto-mode heredoc (lines 275–285).
   - Apply also to the landing-page entry built by `update_landing_page`
     (line 56) — the title flows into a markdown link there, where `"` is
     less catastrophic but a stray `\` could confuse downstream parsers.
     Keep it tight: just title escaping for the link is enough.

3. **Smoke check after writing the blog file** (auto mode only):
   - After `} > "$OUTPUT_FILE"` (line 296), parse the frontmatter with a tiny
     Python one-liner and `die` with a clear message if it does not load.
     This prevents the next silently-broken release post.

The scaffold-mode heredoc (lines 306–337) uses static `TODO_…` placeholders
that never carry user data, so no change is needed there.

## Implementation steps

### Step 1 — Patch the live blog post

Edit
`website/content/blog/v0210-profile-aware-skill-templating-brainstorm-auto-apply-dag-navigation-and-op.md`
line 5, replacing the unescaped inner quotes:

```diff
- description: "v0.21.0 is a big one — a foundational refactor of how skills are authored and dispatched, the brainstorm TUI graduating from "experiment" to a real DAG-driven planning workflow, first-class cross-repo project plumbing, and a fresh mobile-companion bridge."
+ description: "v0.21.0 is a big one — a foundational refactor of how skills are authored and dispatched, the brainstorm TUI graduating from \"experiment\" to a real DAG-driven planning workflow, first-class cross-repo project plumbing, and a fresh mobile-companion bridge."
```

Verify locally:

```bash
python3 -c "
import yaml
with open('website/content/blog/v0210-profile-aware-skill-templating-brainstorm-auto-apply-dag-navigation-and-op.md') as f:
    fm = f.read().split('---', 2)[1]
yaml.safe_load(fm)
print('OK')
"
```

### Step 2 — Add an escaping helper in `new_release_post.sh`

Add near the other helpers (e.g. just above `generate_description()`, around
line 244):

```bash
# Escape backslashes and double quotes for safe interpolation inside a
# YAML double-quoted scalar. Order matters: backslashes first.
yaml_escape_dq() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    printf '%s' "$s"
}
```

### Step 3 — Apply the helper in the auto-mode heredoc

In the auto-mode block (around line 270–296):

```bash
if [[ "$AUTO_MODE" == true ]]; then
    TITLE=$(generate_title)
    DESCRIPTION=$(generate_description)

    # Escape for safe interpolation into double-quoted YAML scalars below.
    TITLE_YAML=$(yaml_escape_dq "$TITLE")
    DESCRIPTION_YAML=$(yaml_escape_dq "$DESCRIPTION")

    {
        cat << FRONTMATTER
---
date: $RELEASE_DATE
title: "$TITLE_YAML"
linkTitle: "v$VERSION"
description: "$DESCRIPTION_YAML"
author: "aitasks team"
---

FRONTMATTER
        ...
    } > "$OUTPUT_FILE"
```

`update_landing_page "$TITLE" …` keeps the unescaped `$TITLE` because the
landing page consumes it as plain markdown link text, not as a YAML scalar.

### Step 4 — Add a frontmatter smoke check

After the auto-mode `} > "$OUTPUT_FILE"` and before
`info "Created blog post: …"` (around line 297):

```bash
# Smoke check: ensure the generated frontmatter parses as YAML.
if ! python3 - "$OUTPUT_FILE" <<'PY'
import sys, yaml
path = sys.argv[1]
with open(path) as f:
    content = f.read()
parts = content.split("---", 2)
if len(parts) < 3:
    sys.exit("frontmatter delimiters missing")
yaml.safe_load(parts[1])
PY
then
    die "Generated blog post has invalid YAML frontmatter: $OUTPUT_FILE"
fi
```

`die` is already provided via the framework's `terminal_compat.sh` (sourced
through `./ait`) — verify it's available in this script's source chain; if
not, fall back to `echo "ERROR: …" >&2; exit 1`.

## Verification

1. **Static YAML parse** — Step 1's Python one-liner exits without error.
2. **Hugo build** — `cd website && hugo build --gc --minify` completes
   without complaint about the v0210 post, and the rendered page under
   `public/blog/v0210-…/index.html` has the correct title and description.
3. **Local dev server** — `cd website && ./serve.sh` renders
   `http://localhost:1313/blog/v0210-…/` with the correct title and the
   description containing the (now-rendered) `"experiment"` text.
4. **Generator regression check** — Run the script in auto mode against a
   synthetic `CHANGELOG_HUMANIZED.md` whose first paragraph contains a
   `"quoted"` word (and ideally a stray `\`). The resulting blog file's
   frontmatter parses as YAML and contains the escaped values.

Suggested one-shot manual harness (not added to the repo):

```bash
tmp=$(mktemp -d)
cp website/new_release_post.sh "$tmp/"
# craft a small CHANGELOG_HUMANIZED.md with a quoted word, then invoke
# the script with AUTO_MODE=true and a fake VERSION to confirm frontmatter
# parses.
```

## Step 9 — Post-Implementation

Per task-workflow Step 9: working on the current branch (fast profile), so no
worktree cleanup or branch merge is needed. Run `aitask_archive.sh 844`,
which moves task/plan files to archived and commits the archival. Then
`./ait git push`.

## Notes

- All edits are localized to `website/`. No framework code, no skills, no
  scripts under `.aitask-scripts/` are touched.
- The fix is intentionally minimal: escape on output, parse-check on output.
  No structural refactor of `new_release_post.sh`.
- An alternative would be to switch the frontmatter to YAML *block* scalars
  (`description: |-` with the value on the next line). That avoids the
  quoting issue entirely but changes the on-disk shape of every blog post
  going forward — out of scope here; revisit only if escaping proves
  insufficient (e.g., descriptions starting to contain newlines).
