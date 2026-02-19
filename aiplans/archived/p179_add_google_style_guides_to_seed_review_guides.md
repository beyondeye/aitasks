---
Task: t179_add_google_style_guides_to_seed_review_guides.md
Branch: main (no worktree)
---

## Context

8 Google style guide reviewguides were recently imported (commit 51ce6f2) into `aireviewguides/` from the conductor project. These need to be copied to `seed/reviewguides/` so they become part of the default distribution when users run `ait setup`.

## Plan

### Step 1: Create new subdirectories in seed/reviewguides/

Create these directories:
- `seed/reviewguides/cpp/`
- `seed/reviewguides/c-sharp/`
- `seed/reviewguides/dart/`
- `seed/reviewguides/go/`
- `seed/reviewguides/html-css/`
- `seed/reviewguides/javascript/`
- `seed/reviewguides/typescript/`

(python/ already exists)

### Step 2: Copy the 8 style guide files

Copy from `aireviewguides/` to `seed/reviewguides/`:

| Source | Destination |
|--------|-------------|
| `aireviewguides/cpp/cpp_style_guide.md` | `seed/reviewguides/cpp/cpp_style_guide.md` |
| `aireviewguides/c-sharp/csharp_style_guide.md` | `seed/reviewguides/c-sharp/csharp_style_guide.md` |
| `aireviewguides/dart/dart_style_guide.md` | `seed/reviewguides/dart/dart_style_guide.md` |
| `aireviewguides/go/go_style_guide.md` | `seed/reviewguides/go/go_style_guide.md` |
| `aireviewguides/html-css/html_css_style_guide.md` | `seed/reviewguides/html-css/html_css_style_guide.md` |
| `aireviewguides/javascript/javascript_style_guide.md` | `seed/reviewguides/javascript/javascript_style_guide.md` |
| `aireviewguides/python/python_style_guide.md` | `seed/reviewguides/python/python_style_guide.md` |
| `aireviewguides/typescript/typescript_style_guide.md` | `seed/reviewguides/typescript/typescript_style_guide.md` |

### Step 3: Update seed/reviewguides/reviewenvironments.txt

Add `html-css` to the environments list (all other environments are already listed). Keep alphabetical order.

### Step 4: Verify

- Confirm all 8 files exist in seed/reviewguides/
- Confirm reviewenvironments.txt includes html-css
- Compare seed and aireviewguides metadata files to confirm sync

## Final Implementation Notes
- **Actual work done:** Created 7 new subdirectories in seed/reviewguides/ (cpp, c-sharp, dart, go, html-css, javascript, typescript), copied 8 style guide files from aireviewguides/, and added html-css to reviewenvironments.txt
- **Deviations from plan:** None — straightforward copy operation
- **Issues encountered:** The reviewenvironments.txt sort order differs slightly between seed (alphabetical) and aireviewguides (c-sharp after cpp). Both contain the same 18 environments. Kept seed's alphabetical ordering.
- **Key decisions:** Used exact copies of the files from aireviewguides/ without modification
