---
Task: t718_3_documentation_pypy_runtime.md
Parent Task: aitasks/t718_pypy_optional_runtime_for_tui_perf.md
Sibling Tasks: aitasks/t718/t718_1_pypy_infrastructure_setup_resolver.md, aitasks/t718/t718_2_wire_long_running_tuis_to_fast_path.md
Archived Sibling Plans: aiplans/archived/p718/p718_1_*.md, aiplans/archived/p718/p718_2_*.md (after siblings archive)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: t718_3 — Documentation for PyPy runtime

## Context

Final child of parent t718. Depends on **both** t718_1 and t718_2 being
archived (the user-visible surface and the implementation must be final
before docs land). After this task, contributors know which resolver to use
in new launchers (CLAUDE.md), and users know how to opt in (website).

## Files to modify

1. **`CLAUDE.md`** — add a short subsection under "Shell Conventions"
   documenting `require_ait_python` vs `require_ait_python_fast`, which
   scripts use which, and the `AIT_USE_PYPY` precedence table.
2. **`website/content/docs/`** — locate the existing setup page and either
   add a sub-section there or create a sibling page about PyPy.
   Pre-flight grep:
   ```bash
   find website/content/docs -name "*.md" | xargs grep -l "ait setup" 2>/dev/null
   ls website/content/docs/installation/ 2>/dev/null
   ```
3. **`README.md`** (only if it documents `ait setup` flags or TUIs) — short
   bullet linking to the website page.

No `.aitask-scripts/*` edits in this task. `git diff --stat` should show only
`.md` files (and possibly `website/...`). Any code change is a scope
violation.

## CLAUDE.md addition (draft)

Insert under the existing "Shell Conventions" section, near the
`require_ait_python` mention if any. Do **not** narrate rollout history
("previously we used X" — see CLAUDE.md "Documentation Writing" rules).

```markdown
### PyPy fast path for long-running TUIs

The framework supports an opt-in PyPy 3.11 sibling interpreter for
long-running Textual TUIs (`ait board`, `ait codebrowser`, `ait settings`,
`ait stats-tui`, `ait brainstorm`). PyPy's tracing JIT speeds up the TUI's
own code, Textual, and Rich. Short-lived CLI scripts and monitor /
minimonitor stay on CPython (PyPy warmup hurts there, and the
monitor/minimonitor bottleneck is `fork+exec(tmux)`, not Python execution
— see `aidocs/python_tui_performance.md`).

Two resolver functions in `lib/python_resolve.sh`:

- `require_ait_python` — returns CPython. Use this for any new launcher
  unless the script is a long-running TUI.
- `require_ait_python_fast` — returns PyPy if installed and not disabled,
  else falls through to CPython. Use this for new long-running TUIs.

Install PyPy with `ait setup --with-pypy`; the venv lives at
`~/.aitask/pypy_venv` (~100-150 MB). Once installed, fast-path TUIs
auto-route through PyPy. Override per invocation with `AIT_USE_PYPY`:

| `AIT_USE_PYPY` | PyPy installed? | Result |
|----------------|-----------------|--------|
| `1`            | Yes             | PyPy (forced) |
| `1`            | No              | error: install with `ait setup --with-pypy` |
| `0`            | (any)           | CPython (override) |
| unset          | Yes             | PyPy (default once installed) |
| unset          | No              | CPython (current behavior preserved) |
```

## Website doc (draft outline)

Either embed in the existing setup page or create
`website/content/docs/installation/pypy.md`. Either way, the content covers:

1. **What it is** — opt-in PyPy 3.11 sibling interpreter for the long-running TUIs.
2. **Why** — link to `aidocs/python_tui_performance.md`. Don't inline the
   analysis; point at the canonical reference.
3. **How to install** — `ait setup --with-pypy` (one command). Disk cost
   ~100-150 MB. The interactive prompt during `ait setup` is also offered to
   TTY users.
4. **TUIs that use it** — board, codebrowser, settings, stats-tui, brainstorm.
5. **TUIs that don't** — monitor, minimonitor (their bottleneck is OS
   fork+exec; cross-link to t719's tmux control-mode work if shipped).
6. **Disable** — `AIT_USE_PYPY=0 ait board` for a single invocation, or
   `rm -rf ~/.aitask/pypy_venv` to remove permanently.
7. **Diagnostics** — `~/.aitask/pypy_venv/bin/python -c "import sys; print(sys.implementation.name, sys.implementation.version)"` to confirm the venv is healthy.

## README.md (conditional)

If `README.md` already lists `ait setup` flags, add one bullet:

> `ait setup --with-pypy` — install PyPy 3.11 for ~2-5× faster long-running
> TUIs (board, codebrowser, settings, stats-tui, brainstorm). Optional, ~100
> MB. See [PyPy runtime](./website/content/docs/installation/pypy.md) for
> details.

If README.md doesn't already cover setup flags, skip — don't introduce a new
section just for this.

## Implementation steps

1. Read CLAUDE.md "Shell Conventions" section to find the right neighbor for the new subsection. Edit in place.
2. `find website/content/docs -name "*.md" | xargs grep -l "ait setup"` to find the existing setup page. Decide: extend in place vs. new page.
3. Draft the website content following the outline above. Match heading levels and style of neighboring pages (look at the Hugo/Docsy frontmatter and shortcodes used).
4. If README.md mentions `ait setup`, add the bullet.
5. Cross-link `aidocs/python_tui_performance.md` from both places — don't inline the analysis.

## Verification

1. `cd website && hugo build --gc --minify` succeeds with no broken-cross-link warnings involving the new content.
2. `grep -n "AIT_USE_PYPY\|--with-pypy" CLAUDE.md website/content/docs/ -r` shows both the env var and the flag are documented.
3. `git diff --stat` shows only `.md` files and (possibly) `website/content/docs/` files. No `.aitask-scripts/*` edits.
4. Spot-check the rendered website doc by serving locally (`cd website && ./serve.sh`) and viewing the new page in a browser — verify links resolve, code blocks render, and the table is formatted.

## Step 9 (Post-Implementation)

Standard child-task archival per `task-workflow/SKILL.md` Step 9. After this
task archives, the parent t718 will auto-archive (last child completed).
