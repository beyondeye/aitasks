---
priority: medium
effort: low
depends: [t718_2]
issue_type: documentation
status: Done
labels: [documentation, performance, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-30 10:31
updated_at: 2026-04-30 15:21
completed_at: 2026-04-30 15:21
---

## Context

Parent task **t718** (`aitasks/t718_pypy_optional_runtime_for_tui_perf.md`) introduces opt-in PyPy support for long-running Textual TUIs. Siblings t718_1 (infrastructure) and t718_2 (TUI wiring) must be archived before this task — both are sibling dependencies. Once those land, the user-visible surface is:

- `ait setup --with-pypy` installs PyPy 3.11 into `~/.aitask/pypy_venv/`.
- `AIT_USE_PYPY=0/1` env var on TUI invocation (precedence per t718_1's resolver).
- Auto-PyPy when installed: `ait board` / `ait codebrowser` / `ait settings` / `ait stats-tui` / `ait brainstorm` (the 5 fast-path TUIs from t718_2) automatically use PyPy when `~/.aitask/pypy_venv` exists.
- Monitor/minimonitor stay on CPython.

This task documents that surface in two places: the framework-internal CLAUDE.md (so future contributors know which resolver function to use in new launcher scripts) and the user-facing website docs / README (so users discover the opt-in).

## Key Files to Modify

1. **`CLAUDE.md`** — add a short subsection under **Shell Conventions** (or near the existing Python venv discussion if there is one) documenting:
   - `require_ait_python` (CPython, default) vs `require_ait_python_fast` (PyPy if installed, CPython fallback). One-paragraph summary.
   - Which scripts use which: long-running Textual TUIs use `_fast`, all other scripts (CLI helpers, monitor/minimonitor) use the regular function.
   - The `AIT_USE_PYPY` env var precedence table (matches t718_1's plan):

     | `AIT_USE_PYPY` | PyPy installed? | Result |
     |---|---|---|
     | `1` | Yes | PyPy (forced) |
     | `1` | No | error |
     | `0` | (any) | CPython |
     | unset | Yes | PyPy (auto) |
     | unset | No | CPython |

   - Reference back to `aidocs/python_tui_performance.md` for the analysis.

2. **`website/content/docs/`** — add a new page or extend an existing one (likely under `setup/` or `installation/`) documenting:
   - What `--with-pypy` does and why a user would want it (faster board / codebrowser / settings / stats / brainstorm TUIs).
   - Disk cost (~100-150 MB additional in `~/.aitask/`).
   - How to opt out: don't pass `--with-pypy` (default), or `AIT_USE_PYPY=0 ait board` per-invocation, or `rm -rf ~/.aitask/pypy_venv` to permanently disable.
   - Which TUIs are NOT covered (monitor/minimonitor) and why (cross-link to t719's tmux control-mode work if it has shipped, otherwise mention it briefly).

3. **`README.md`** (if it exists at the repo root and mentions setup flags / TUI features) — short bullet under setup options, linking to the website doc.

**Pre-flight:** Before drafting, run:

```bash
ls website/content/docs/
grep -rn "ait setup" website/content/docs/ | head
test -f README.md && grep -n "ait setup\|TUI" README.md | head
```

…to find the natural insertion points instead of guessing. CLAUDE.md's "Documentation Writing" rules apply: state the **current** state (PyPy is opt-in, default off) — do **not** narrate the rollout history.

## Reference Files for Patterns

- Existing CLAUDE.md "Shell Conventions" section — drop the new subsection here, format-matching surrounding entries.
- Existing website setup / installation page (whichever covers `ait setup`) — match heading levels, code-block style, and admonitions.
- `aidocs/python_tui_performance.md` — primary technical reference, link from both CLAUDE.md and the website doc.
- Sibling plan files `aiplans/p718/p718_1_*.md` and `aiplans/p718/p718_2_*.md` for exact behavioral guarantees.

## Implementation Plan

**Step 1 — Locate insertion points** (read-only):
- `grep -n "require_ait_python\|venv" CLAUDE.md` to find the right neighbor section.
- `find website/content/docs -name "*.md" | xargs grep -l "ait setup"` to find the user-facing setup page.

**Step 2 — Draft CLAUDE.md subsection.** Add under existing "Shell Conventions" (or "Python venv" if a sub-area already exists). Keep it under 30 lines including the table.

**Step 3 — Draft website doc.** Either a new page (`website/content/docs/installation/pypy.md` or similar) or a section in the existing setup page. Cross-link from the main install page so users discover it.

**Step 4 — README.md update** (only if README mentions setup flags). One-line bullet pointing to the website doc.

**Step 5 — Cross-link `aidocs/python_tui_performance.md`** from both CLAUDE.md and the website doc — it's the authoritative technical reference and should not be inlined.

**Step 6 — Validate.** Build the website locally per CLAUDE.md (`cd website && hugo build --gc --minify`) to confirm the new page renders without broken cross-links. CLAUDE.md is plain markdown — no build step.

## Verification Steps

1. `cd website && hugo build --gc --minify` succeeds with no warnings on broken cross-links involving the new content.
2. The CLAUDE.md addition keeps the "Shell Conventions" section coherent — no duplicate `require_ait_python` mentions, no contradiction with existing portability guidance.
3. `grep -n "AIT_USE_PYPY\|--with-pypy" CLAUDE.md website/content/docs/ -r` shows both the env var and the flag are documented in at least one user-facing place.
4. README.md (if updated) lints cleanly under any project markdown linter.
5. **No code changes** — `git diff --stat` should show only `.md` files (and possibly the website's content directory). If any `.aitask-scripts/*.sh` is modified, this task has overstepped its scope.

## Notes for sibling tasks

- This task is the *only* place user-facing documentation lives for t718. t718_1 and t718_2 commit code with task-id-suffix commit messages; this task commits docs. Keep the boundary clean.
- If the user later asks "how do I tell whether board is on PyPy?", the answer should already exist in the website doc — surface a small `Diagnostics` subsection: `python -c 'import sys; print(sys.implementation.name)'` from inside `~/.aitask/pypy_venv/bin/python`.
