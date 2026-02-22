---
Task: t178_add_html_css_environment_detection.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

The `aitask_review_detect_env.sh` script auto-detects project environments to rank review guides. A new `html_css_style_guide.md` review guide exists at `aireviewguides/html-css/` with `environment: [html-css]`, and `html-css` is already registered in `reviewenvironments.txt`, but the detection script has no logic to identify HTML/CSS projects. This task adds that detection logic and corresponding tests.

## Plan

### 1. Add HTML/CSS detection to `aiscripts/aitask_review_detect_env.sh`

**File extensions (test_file_extensions, ~line 200)** — Add cases before the closing `esac`:
```bash
html|htm)           add_score "html-css" "$weight" ;;
css|scss|sass|less) add_score "html-css" "$weight" ;;
```

**Directory patterns (test_directory_patterns, ~line 279)** — Add a new flag `found_html_css_dir` and pattern block:
- Match `templates/*.html`, `templates/**/*.html` (template engines)
- Match `public/*.html`, `public/**/*.html` (static sites)
- Match `static/*.html`, `static/**/*.html`
- Match `styles/*`, `css/*`, `stylesheets/*` directories

No changes needed for:
- `test_project_root_files` — HTML/CSS has no strong project-root marker file
- `test_shebang_lines` — HTML/CSS files don't use shebangs

### 2. Add tests to `tests/test_detect_env.sh`

Insert a new `HTML / CSS` test section before the cross-environment tests. Tests:
1. `.html` file extension detection
2. `.htm` file extension detection
3. `.css` file extension detection
4. `.scss` file extension detection (preprocessor)
5. `.sass` file extension detection
6. `.less` file extension detection
7. `templates/` directory pattern
8. `public/` directory pattern
9. Combined extensions for higher score (multiple .html + .css files >= 3)
10. Isolation: `.html` files alone should not trigger python, java, etc.

### Verification
1. `bash -n aiscripts/aitask_review_detect_env.sh` — syntax check
2. `bash tests/test_detect_env.sh` — all tests pass (existing + new)
3. `shellcheck aiscripts/aitask_review_detect_env.sh` — no new warnings
4. Manual smoke test with html/css files

## Final Implementation Notes
- **Actual work done:** Added HTML/CSS environment detection via file extensions (.html, .htm, .css, .scss, .sass, .less) and directory patterns (templates/, public/, static/, styles/, css/, stylesheets/). Added 27 new test cases covering all extensions, directory patterns, combined scoring, and isolation.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** No root file detection for html-css (no strong marker like Cargo.toml). CSS preprocessor extensions (.scss, .sass, .less) all map to `html-css` since the review guide covers both HTML and CSS. Directory patterns use the same `found_html_css_dir` flag to prevent double-scoring.
