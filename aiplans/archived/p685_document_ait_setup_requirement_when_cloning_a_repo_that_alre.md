---
Task: t685_document_ait_setup_requirement_when_cloning_a_repo_that_alre.md
Base branch: main
plan_verified: []
---

# Plan: Document `ait setup` requirement when cloning a repo that already uses aitasks

## Context

When a user clones a repository that already has aitasks installed in
data-branch mode, the framework appears "empty" until `./ait setup` is run:
`aitasks/` exists but contains only `metadata/`, `ait board` shows no tasks,
and `./ait git-health` reports "legacy mode". The remote `aitask-data` branch
is present but no local worktree is checked out.

The website docs cover three install paths today (curl one-liner, `ait upgrade`,
and global-shim auto-bootstrap in a fresh project), but **not** the case of
cloning an existing aitasks-enabled repo. Users hit this failure mode and
search for the symptoms above before they realize `./ait setup` is the answer.
Issue: https://github.com/beyondeye/aitasks/issues/11.

The `aitask_setup.sh` script already handles this case correctly — line 1029
fetches an existing remote `aitask-data` branch, line 1056 creates the
`.aitask-data/` worktree, symlinks are wired, and `userconfig.yaml` is
seeded later. Nothing needs to change in code; only docs.

## Approach

Add a single H2 section **"Cloning a Repo That Already Uses aitasks"** to
`website/content/docs/installation/_index.md`, placed immediately after the
"Quick Install" section and before "Platform Support". This is the
discoverability-optimal location: users searching for the symptoms land on
the install page, where the new section is visible without scrolling past
unrelated material.

No changes to `getting-started.md` — it targets the fresh-install audience
who run the curl one-liner, and it already links to the Installation guide
where the cloning path lives.

## File to modify

- `website/content/docs/installation/_index.md` — insert one new H2 section
  between current line 47 (end of "Already have the global ait shim?" block,
  after "Agent caveats" line) and line 49 ("## Platform Support").

## New section content (draft)

```markdown
## Cloning a Repo That Already Uses aitasks

If you `git clone` a repository that already has aitasks installed in
data-branch mode (the default for projects bootstrapped with current
versions), the working tree will look "empty" until you run setup:

```bash
cd /path/to/cloned-repo    # the git repository root
./ait setup
```

> **Use `./ait`, not `ait`.** On a fresh clone the global `ait` shim
> at `~/.local/bin/ait` may not be installed yet, or may not be on
> PATH. The project-local `./ait` dispatcher is always present in the
> repo root.

`./ait setup` detects the existing remote `aitask-data` branch and:

1. Fetches the `aitask-data` branch from the remote.
2. Creates the `.aitask-data/` git worktree checked out at that branch.
3. Replaces the empty `aitasks/` and `aiplans/` directories with symlinks
   into the worktree, so task and plan files appear in the usual places.
4. Initializes per-user state (`aitasks/metadata/userconfig.yaml`, etc.).

### Symptoms before running setup

If you see any of these on a fresh clone, run `./ait setup`:

- `aitasks/` exists but contains only an empty `metadata/` subdirectory —
  no task files visible.
- `ait board` (or `./ait board`) shows no tasks.
- `./ait git-health` reports:
  `Mode: legacy (no separate .aitask-data worktree) — nothing to check.`
- `git branch -a` shows a remote `aitask-data` branch that is not checked
  out anywhere locally.

For background on why task data lives on a separate branch, see
[Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}).
```

(Implementation will use a fenced code block inside the markdown file —
the nested triple-backticks above are illustrative; actual file uses
the standard four-backticks-or-tildes-around-three pattern that Hugo
handles, matching existing `installation/_index.md` style.)

## Notes on documentation conventions (per CLAUDE.md)

- "Cloning a repo" is current state (a supported install path), not
  historical correction — no version history language.
- Verb choice: this is a first-time per-clone setup, not a repair —
  `./ait setup` is correct (the framework's own `setup` verb), and we
  do **not** mention `ait upgrade` here.
- The existing `installation/_index.md` already uses `./ait` in command
  examples (e.g., the global-shim section uses `ait setup` because the
  shim is assumed installed; we explicitly use `./ait setup` here and
  call out why).

## Verification

1. Render the site locally:
   ```bash
   cd website && ./serve.sh
   ```
2. Open `http://localhost:1313/docs/installation/` and confirm:
   - The new "Cloning a Repo That Already Uses aitasks" H2 appears in
     the page TOC and renders below "Quick Install".
   - The cross-reference link to `git-branching-model` resolves (no
     broken-relref warning in the Hugo console).
   - The fenced code blocks render correctly (the `cd` + `./ait setup`
     block, and the symptoms list).
3. Confirm no Hugo build warnings:
   ```bash
   cd website && hugo build --gc --minify 2>&1 | grep -iE "warn|error" || echo OK
   ```
4. Spot-check that no other pages still imply "clone + work" without
   running setup:
   ```bash
   grep -rn "git clone" website/content/docs/ | grep -v setup
   ```
   (Expected: no results, or only results unrelated to the aitasks-repo
   clone scenario.)

## Out of scope

- Code changes to `aitask_setup.sh` — already correct.
- Changes to `getting-started.md` — that page targets the curl-installer
  audience; the link to `installation/` covers cross-discovery.
- A new top-level page — one section in `installation/_index.md` is the
  right size for this content; a new page would be over-structured.
- Localization / translation files — the website does not have
  per-language content directories.

## Final Implementation Notes

- **Actual work done:** Added a single H2 section "Cloning a Repo That
  Already Uses aitasks" to `website/content/docs/installation/_index.md`,
  inserted between the "Quick Install" block (after the "Agent caveats"
  paragraph) and "Platform Support". The section has the planned 4-bullet
  what-setup-does list, the symptoms subsection (H3), the `./ait` vs `ait`
  callout, and the cross-reference to the `git-branching-model` concepts
  page via `relref`. Total +38 lines, no other files touched.
- **Deviations from plan:** None. The draft content in the plan was used
  almost verbatim; only the markdown nesting note (illustrative
  triple-backticks) was naturally resolved at write time.
- **Issues encountered:** None. Hugo build was clean (only the
  pre-existing `.Site.AllPages` deprecation warning, unrelated to this
  change). The cross-reference to `/docs/concepts/git-branching-model`
  resolved as expected (rendered link present, no Hugo warning).
- **Key decisions:**
  - Chose `installation/_index.md` over `getting-started.md` because
    cloning targets a different audience than the curl-installer
    fresh-install path. `getting-started.md` already links to the
    installation guide for cross-discovery.
  - Used `./ait setup` (not `ait setup`) and called out the reason
    inline, since the global shim may be missing on a fresh clone.
  - Kept the section size to one H2 + one H3 — adding a new dedicated
    page would have been over-structured for ~40 lines of content.
- **Upstream defects identified:** None.

