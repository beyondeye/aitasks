---
Task: t1782_fix_docs_readme_stale_links.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1782 — Fix stale links in docs/README.md

## Context

`docs/README.md` is a hand-maintained index into `website/content/docs/`. It is
not part of the Hugo build, so neither `hugo build` nor `website/check_links.py`
ever sees it. Its links went dead with nothing failing. Resolving every relative
link against the tree (done during planning) shows **5 dead links**, not the 2 the
task names:

- `board/_index.md`, `board/how-to.md`, `board/reference.md` — moved to `tuis/board/`
- `workflows/terminal-setup.md` — moved to `installation/terminal-setup.md`
- `skills/aitask-pick.md` — now the directory `skills/aitask-pick/_index.md`

It also lists about 40 of the site's ~130 pages. Whole sections are missing
(`concepts/`, `tuis/`), as are most command pages.

**User decision (this planning session):** rewrite the table as a **section index**,
one row per top-level page and section. Section landing pages already list their own
pages, so the index does not go stale when a page is added. The per-page rows,
including the `/aitask-note` row t1657_6 added, are dropped on purpose. Add a guard
test, because the site's link checker cannot reach this file.

The root `README.md` was checked too. Its only relative link (`LICENSE`) resolves, so
the guard covers `docs/README.md` only.

## Implementation

Order matters: the guard is written first and run against the current README to
watch it fail (the red proof), then the README is fixed. Nothing is committed in
between.

### 1. New guard test: `tests/test_docs_readme_links.sh`

Self-contained bash test, following the `tests/test_docs_vocabulary_coverage.sh`
shape: `#!/usr/bin/env bash`, `set -e`, `SCRIPT_DIR`/`PROJECT_DIR`, source
`tests/lib/asserts.sh`, `PASS/FAIL/TOTAL`, `CLEANUP_DIRS` + `trap cleanup EXIT`,
`Results:` footer, `[[ "$FAIL" -eq 0 ]] || exit 1`. Test bodies run in the main
shell (no `( … )` subshells), so the file-backed counters are not needed.

A header comment states what the file checks and what it does **not**:
- It checks **inline** Markdown links (`[text](target)`) only. Reference-style
  definitions (`[x]: path`) and HTML `<a href>` are not seen. That gap is deferred
  to a named follow-up (see **Deferred, with owners**), and the comment names that
  task.
- `#fragment` anchors are stripped and not validated.
- Subsection pages (for example `tuis/board/*`) are not required to be listed.

Checker function `check_readme <root>`. It is the single place the follow-up
extends. It prints lines, and its exit status is non-zero on any finding:

- Extract every inline-link target from `<root>/docs/README.md`
  (`grep -oE '\]\([^)]+\)'`, strip the `](` and `)` wrapper). Skip targets with a
  URL scheme (`^[a-zA-Z][a-zA-Z0-9+.-]*:`) and strip any `#fragment`.
- Print `LINKS:<n>`. **`n == 0` is a failure** (a tripwire: a changed link syntax,
  or bare paths in place of links, must not pass by checking nothing).
- For each target, test `-e "<root>/docs/<target>"`. Otherwise print
  `DEAD:<target>`.
- Completeness: the expected set is every `<root>/website/content/docs/*.md`
  except the root `_index.md`, plus every `<root>/website/content/docs/*/_index.md`.
  Each must appear as an extracted target `../website/content/docs/<rel>`.
  Otherwise print `MISSING:<rel>`. The set is derived from the tree, never
  hard-coded, so a README whose rows are bare paths instead of links fails twice:
  `LINKS:0` and one `MISSING:` per expected page.

Tests:
1. **Live repo is clean** — `check_readme "$PROJECT_DIR"` exits 0, and its output
   has no `DEAD:` and no `MISSING:`.
2. **Fixture baseline is clean** — fixture = temp dir with a copy of the real
   `docs/README.md`, plus an empty file for every top-level page and section the
   real tree has (built from the same globs). It must pass. This proves the
   fixture has the shape the controls assume, so a control that fails for an
   unrelated reason cannot pass as a real detection.
3. **Control, dead link** — delete `concepts/_index.md` from the fixture tree:
   exit non-zero, output contains `DEAD:../website/content/docs/concepts/_index.md`.
4. **Control, missing section** — add `newsection/_index.md` to the fixture tree:
   exit non-zero, output contains `MISSING:newsection/_index.md`.
5. **Control, missing top-level page** — add `new-page.md`: exit non-zero,
   output contains `MISSING:new-page.md`.
6. **Control, bare paths instead of links** — a README whose table cells hold
   the same targets as bare paths (not Markdown links): exit non-zero, output
   contains `LINKS:0` and `MISSING:concepts/_index.md`. This is the failure the
   plan review raised.

Each control uses a fresh fixture, so one mutation cannot leak into another
control.

**Red proof:** run the test before step 2. Test 1 must fail, listing the 5 `DEAD:`
lines above plus `MISSING:` lines for at least `concepts/_index.md` and
`tuis/_index.md`. Tests 2–6 pass either way, because each fixture is built from
its own README and tree.

### 2. Rewrite `docs/README.md` as a section index

- Line 3: current-state wording, with no "has moved" history phrasing: "The
  documentation lives in `website/content/docs/` — the Hugo/Docsy website is the
  single source of truth. Make all updates there."
- Keep the **Live site** line.
- Rename `## Available Documentation` to `## Documentation Sections`. Add one
  sentence saying the index lists top-level pages and sections only, and that each
  section's landing page lists its own pages.
- Two-column table, `Guide | Description`. The `Source File` column is dropped: it
  only repeated the link path. Rows are ordered by Hugo `weight`. Each Guide cell
  is an **inline Markdown link** (the only form the guard extracts), and each
  Description is that page's own frontmatter `description:`, minus the trailing
  period. Write this block **verbatim**:

  ```markdown
  | Guide | Description |
  |-------|-------------|
  | [Overview](../website/content/docs/overview.md) | The challenge aitasks addresses, its core philosophy, and key features |
  | [Getting Started](../website/content/docs/getting-started.md) | First-time setup and your first task workflow |
  | [Installation](../website/content/docs/installation/_index.md) | Install aitasks and configure your development environment |
  | [Concepts](../website/content/docs/concepts/_index.md) | Conceptual reference for the aitasks framework — what each building block is and why it exists |
  | [TUI Applications](../website/content/docs/tuis/_index.md) | Terminal-based user interfaces for task management and code understanding |
  | [Workflow Guides](../website/content/docs/workflows/_index.md) | End-to-end workflow guides for common aitasks operations |
  | [Code Agent Skills](../website/content/docs/skills/_index.md) | Reference for aitasks skills across supported code agents |
  | [Command Reference](../website/content/docs/commands/_index.md) | Complete CLI reference for all ait subcommands |
  | [Development Guide](../website/content/docs/development/_index.md) | Architecture, internals, and release process |
  ```

- A closing pointer line (it points to the guard and does not restate it): "This
  file is outside the Hugo build, so `website/check_links.py` never sees it;
  `tests/test_docs_readme_links.sh` checks its inline links."

### 3. `website/README.md` — one paragraph under "Checking Internal Links"

After the "Run it after editing any page under `content/`…" paragraph, add:
"`docs/README.md` sits outside `content/` and is never rendered, so neither the
build nor `check_links.py` sees it. `tests/test_docs_readme_links.sh` checks its
inline links and that it lists every top-level docs page and section."

No page under `website/content/` changes, so `check_links.py` has nothing new to
check.

## Deferred, with owners

| Deferred item | Owner | Carry forward |
|---|---|---|
| The guard only sees inline `](…)` links. Two forms are **silent bypasses**: reference-style definitions (`[x]: ../path.md`) and HTML `<a href>`. Two forms **fail loudly** as false `DEAD:` findings: inline destinations with a title (`](p "t")`) and angle-bracket destinations (`](<p>)`). (Plan-review concern, disposition `follow-up`.) | New follow-up task, created after the Step 8 commit via `aitask_create.sh --batch`: type `test`, labels `documentation, web_site`, `--deps 1782` (it edits the test file this task creates), with `followup_kind` from `.aitask-scripts/lib/followup_kinds.py` if one fits | Pick one: **restrict and enforce** (an `UNSUPPORTED:<line>` tripwire for each disallowed form; cheapest, and matches "enforce the convention, don't parse for intent") or **extend extraction** to cover the forms. Either way, add one negative control per form using the fresh-fixture pattern, and update the header comment's "not seen" list and the two "inline links" pointer lines (`docs/README.md`, `website/README.md`). The hook point is the single `check_readme` function. |

## Verification

- `bash tests/test_docs_readme_links.sh`, run before step 2: Test 1 fails with the
  5 expected `DEAD:` lines (the red proof). Run after step 2: all tests pass and
  the script exits 0; the live run prints `LINKS:9` (today's count, observed, not
  asserted).
- `shellcheck tests/test_docs_readme_links.sh` is clean.
- An independent cross-check that shares no code with the test: the planning-time
  one-liner (`grep -oE '\]\(\.\./[^)]+\)' docs/README.md | … [ -e ]`) reports
  every row `OK`.
- Commit only the named paths: `docs/README.md`, `tests/test_docs_readme_links.sh`,
  `website/README.md`. The working tree holds other sessions' unrelated changes
  (`task_automerge.sh`, `run_all_python_tests.sh`, …), so `git commit -- <paths>`
  and then `git show --stat` to confirm.

## Step 9 (Post-Implementation)

Current-branch profile (`fast`), so there is no branch to merge. After Step 8
review and commit, create the deferred follow-up task above, run the gate
orchestrator for `risk_evaluated`, then archive via `aitask_archive.sh 1782` and
push.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
