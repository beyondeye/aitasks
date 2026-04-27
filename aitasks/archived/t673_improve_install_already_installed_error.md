---
priority: high
effort: low
depends: []
issue_type: bug
status: Done
labels: [install_scripts, installation]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-27 15:36
updated_at: 2026-04-27 16:10
completed_at: 2026-04-27 16:10
---

## Problem

When a user re-runs the documented one-liner from the website on a project that already has aitasks installed, `install.sh` dies with:

```
[ait] Error: aitasks already installed in <DIR> (found ait or .aitask-scripts/). Use --force to overwrite.
```

The error message tells the user to "use --force", but for the curl-pipe invocation that the website documents (`curl -fsSL .../install.sh | bash`) it gives no hint that they need the `bash -s --` plumbing to actually pass `--force` through. The documented fresh-install-with-force form (`bash -s -- --force`) only appears once, deep in `installation/_index.md:31` — it's not in `getting-started.md:18`, top-level `_index.md:42`, `installation/_index.md:17`, or `windows-wsl.md:44`.

The user also has no hint that for an existing install they should be running `ait upgrade latest` (the actual recommended path documented at `installation/_index.md:22-26`), not re-running the curl bootstrap at all.

When running the script locally (`bash install.sh` in a TTY), there is also no interactive overwrite confirmation — it just dies fatally even though stdin is a terminal and a Y/N prompt would be possible.

## Goals

1. Improve the `die()` message at `install.sh:95` so it spells out **both** recovery paths:
   - For an existing install, use `ait upgrade latest` (the recommended path).
   - For a re-bootstrap via curl-pipe, use `curl -fsSL <url> | bash -s -- --force`.
   - For a re-bootstrap via local file, use `bash install.sh --force`.
2. **Optionally (TTY only):** when `[[ -t 0 ]]` is true and an existing install is detected, prompt the user interactively — "Existing aitasks install found. Overwrite framework files? [y/N]" — and treat "y" as setting `FORCE=true` for the rest of the run. Skip the prompt entirely when piped (stdin is the script). The `confirm_install()` function (`install.sh:100-140`) already has the `[[ -t 0 ]]` gate pattern to model on.
3. Decide and document a consistent stance for the website:
   - Either add a `--force` / `ait upgrade latest` callout right next to the bare `curl … | bash` snippet in `getting-started.md` and the other entry-point pages, OR
   - Lean on the improved error message + `ait upgrade latest` recommendation as the discoverable path and keep the install snippet bare. (Recommended: improve the error first; update docs to cross-link only if still a friction point.)

## Acceptance criteria

- Running `bash install.sh` (no `--force`) on an existing install in a TTY shows a y/N overwrite prompt; "y" continues with `FORCE=true`, "n" or empty exits cleanly with a non-error message.
- Running `curl … | bash` (non-TTY) on an existing install dies with an updated message that names `ait upgrade latest`, `bash -s -- --force`, and `bash install.sh --force` as the three recovery options.
- The `--force` flag itself behaves identically to today (no behavior change to forced installs).
- No regression in the existing `confirm_install()` git-root / install-here prompts.

## Out of scope

- Changing what `--force` does (merge semantics, etc.).
- Adding new package-manager install methods (covered by t623).
- Manual-verification checklist tasks for the upgrade flow (covered by t638).

## Files likely to touch

- `install.sh` (`check_existing_install`, possibly `confirm_install` for the TTY prompt, line 95 die message).
- Optionally `website/content/docs/getting-started.md`, `website/content/docs/installation/_index.md`, `website/content/_index.md`, `website/content/docs/installation/windows-wsl.md` for cross-references.
