---
Task: t826_1_registry_resolver_projects_cmd_and_create_flag.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_2_tui_switcher_show_inactive_projects.md, aitasks/t826/t826_3_website_docs_multi_project_workflow.md, aitasks/t826/t826_4_manual_verification_brainstorm_cross_repo_project_references.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-25 17:37
---

# Plan: t826_1 — Cross-repo project registry, resolver, `ait projects`, `aitask_create.sh --project`

## Context

This is the first of three implementation children under the t826
brainstorm "easier cross-repo references". The pain point: when a task in
`aitasks_mobile` needs to spawn a coordination task in the sister `aitasks`
repo, plans today hard-code `../aitasks/`, which is brittle (depends on
sibling-directory layout, breaks on other machines / cloud agents,
reviewers can't tell which logical project is meant).

This child lands the foundation that the other two consume:
- Per-project identity stored in `project_config.yaml`.
- Per-user persistent registry at `~/.config/aitasks/projects.yaml`.
- An internal resolver script (`aitask_project_resolve.sh`).
- A user-facing `ait projects` subcommand (`list` / `add` / `resolve` / `exec`).
- A `--project <name>` batch flag on `aitask_create.sh` for cross-repo task spawning.
- An authoring-side aidoc that documents the registry schema, resolver semantics, and the `aitasks#835_3` cross-repo task-ID notation.

Sibling t826_2 will then add inactive-project visibility to the TUI
switcher; t826_3 documents the user-facing workflow on the website.

## Verify-path notes (what changed from the inline task plan)

This is the **verify** path under profile `fast`: the inline plan in the
task description is still valid. Three small refinements surfaced during
verification:

1. **`aitask_ide.sh` hook site.** The task description says "after the
   existing `tmux set-environment` call (line 109)". The cleaner site is
   *inside* `set_project_registry()` (lines 108–110), which has three call
   sites (127, 136, 149) — placing the `aitask_projects.sh add` call there
   auto-covers all three. The variable name in `aitask_ide.sh` is
   `SCRIPT_DIR` (singular, defined at line 4), not `SCRIPTS_DIR`.

2. **Resolver step 3 (env-var fallback) framing.** Today
   `agent_launch_utils.py::discover_aitasks_sessions()` already consults
   the tmux global env var `AITASKS_PROJECT_<sess>` via
   `_read_registry_entry()` (lib/agent_launch_utils.py:224). So the
   resolver's "live-tmux scan" step already covers the tmux-global path.
   Step 3 of the resolver is therefore best read as a **process env-var**
   fallback (`os.environ['AITASKS_PROJECT_<name>']` or shell
   `${AITASKS_PROJECT_<name>}`) — useful as a manual override in non-tmux
   contexts (CI, remote agents).

3. **`tests/lib/test_scaffold.sh` baseline confirmed.** Current baseline
   libs: `aitask_path.sh`, `terminal_compat.sh`, `python_resolve.sh`,
   `yaml_utils.sh`. This task adds no new system lib, so
   `setup_fake_aitask_repo()` needs no update.

No new clarifying questions for the user: the inline plan in the task
file is comprehensive and the verification confirmed its assumptions.

## Implementation Plan

(The full plan lives in
`aitasks/t826/t826_1_registry_resolver_projects_cmd_and_create_flag.md`
under "## Implementation Plan". This file lists each step with the
verification-derived refinements folded in.)

1. **Schema** — Add commented `project: { name, git_remote }` template
   block to `seed/project_config.yaml`; populate it in
   `aitasks/metadata/project_config.yaml` with `name: aitasks` and the
   project's `git_remote`.

2. **Resolver** — Create `.aitask-scripts/aitask_project_resolve.sh`
   (internal helper, not whitelisted, invoked only by other scripts).
   - Argument: `<name>`.
   - Output: `RESOLVED:<root>` / `NOT_FOUND:<name>` / `STALE:<name>:<path>`.
   - Resolution order:
     1. Live tmux scan — shell out to `python3 -c "from
        .aitask-scripts.lib.agent_launch_utils import
        discover_aitasks_sessions; ..."` (reuse the existing function;
        prefer match on `project_name` then `session`).
     2. Per-user index `~/.config/aitasks/projects.yaml` — flat list
        parsed with grep/awk (no PyYAML dep).
     3. Process env var `AITASKS_PROJECT_<name>` (manual override).
   - STALE means: index points at a path that no longer contains
     `aitasks/metadata/project_config.yaml`.

3. **`ait projects` dispatcher** — Create
   `.aitask-scripts/aitask_projects.sh` with four verbs:
   - `list` — emit one row per registered project, annotated `LIVE`
     (matched by tmux scan), `OK` (filesystem still valid), or `STALE`.
   - `add [<path>]` — default path is `$(pwd)`. Reads
     `aitasks/metadata/project_config.yaml` for `project.name` /
     `project.git_remote`; falls back to directory basename for the name.
     Atomic write (mktemp + mv) to `~/.config/aitasks/projects.yaml`.
     Idempotent: replaces an existing entry with the same name.
   - `resolve <name>` — re-emits the resolver output verbatim.
   - `exec <name> -- <cmd...>` — resolves then `cd <root> && exec
     <cmd...>`. Errors out on `NOT_FOUND` / `STALE`.

4. **Wire `ait` dispatcher** — Add `projects` to the no-update-check
   exemption (currently line 169 of `ait`) and add a `projects)` case
   right after the alphabetically-near existing cases (around line
   190 — the precise insertion point can be anywhere in the case block;
   align with neighboring entries). Both wirings shell out to
   `aitask_projects.sh`.

5. **`aitask_ide.sh` auto-populate** — Inside `set_project_registry()`
   (lines 108–110 of `.aitask-scripts/aitask_ide.sh`), after the existing
   `tmux set-environment` call, add:
   ```bash
   "$SCRIPT_DIR/aitask_projects.sh" add "$(pwd)" >/dev/null 2>&1 || true
   ```
   This makes every `ait ide` (which calls the function from each of
   lines 127, 136, 149) implicitly register the project.

6. **`aitask_create.sh --project`** — Extend the `parse_args()` switch
   (around line 143 of `.aitask-scripts/aitask_create.sh`, beside
   `--parent|-P`) with `--project <name>`. Then:
   - Reject if `--batch` is not set.
   - Reject if combined with `--parent`.
   - Resolve via `aitask_project_resolve.sh <name>`.
   - On `RESOLVED:<root>`: drop `--project <name>` from `argv`, `cd
     <root>`, then `exec "$root/.aitask-scripts/aitask_create.sh"
     "${remaining_argv[@]}"`.
   - On `NOT_FOUND` / `STALE`: print the resolver output to stderr and
     exit non-zero.

7. **Docs** —
   - Create `aidocs/cross_repo_references.md` with: registry schema,
     resolver order, output protocol, the `aitasks#835_3` task-ID
     notation (preferred without `t`; accepted with `t`; regex
     `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$`).
   - Add a short "Cross-Repo Coordination" pointer under
     `CLAUDE.md`'s "Project-Specific Notes" section linking to the
     new aidoc and to `ait projects --help`.

8. **Tests** — Create three bash test scripts under `tests/`, each
   self-contained (use `setup_fake_aitask_repo()` from
   `tests/lib/test_scaffold.sh`):
   - `tests/test_project_resolve.sh` — matrix: resolve-by-live-session
     (mock tmux), resolve-by-index, NOT_FOUND, STALE, fallback through
     process env var.
   - `tests/test_projects_cmd.sh` — smoke round-trip of
     `list`/`add`/`resolve`/`exec`.
   - `tests/test_create_project_flag.sh` — `--batch --project <name>`
     creates the task in the resolved root; rejects `--project` without
     `--batch`; rejects `--project` with `--parent`.

9. **Lint** — `shellcheck` over the new and modified scripts:
   `aitask_project_resolve.sh`, `aitask_projects.sh`, `aitask_create.sh`,
   `aitask_ide.sh`, `ait`.

## Key Files

**Created:**
- `.aitask-scripts/aitask_project_resolve.sh`
- `.aitask-scripts/aitask_projects.sh`
- `aidocs/cross_repo_references.md`
- `tests/test_project_resolve.sh`
- `tests/test_projects_cmd.sh`
- `tests/test_create_project_flag.sh`

**Modified:**
- `seed/project_config.yaml` — add `project:` template block.
- `aitasks/metadata/project_config.yaml` — populate `project:` block.
- `ait` — exemption line + `projects)` dispatcher case.
- `.aitask-scripts/aitask_ide.sh` — hook in `set_project_registry()`.
- `.aitask-scripts/aitask_create.sh` — `--project` flag handling.
- `CLAUDE.md` — short Cross-Repo Coordination pointer.

## Reused Code

- `.aitask-scripts/lib/agent_launch_utils.py`:
  - `discover_aitasks_sessions()` (lines 255-316) — already implements
    live-tmux enumeration with per-pane cwd walk-up AND tmux-global env
    fallback via `_read_registry_entry()` (lines 224-252). The resolver
    invokes this directly via `python3 -c`.
- `.aitask-scripts/aitask_query_files.sh` — canonical `KEY:value` stdout
  convention to follow for the new helpers.
- `.aitask-scripts/lib/python_resolve.sh` — `require_ait_python` /
  `require_modern_python` for invoking Python from the resolver.
- `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` — used by all
  three new tests.

## Verification

- All three new test scripts pass:
  ```bash
  bash tests/test_project_resolve.sh && \
    bash tests/test_projects_cmd.sh && \
    bash tests/test_create_project_flag.sh
  ```
- Clean shellcheck:
  ```bash
  shellcheck .aitask-scripts/aitask_project_resolve.sh \
             .aitask-scripts/aitask_projects.sh \
             .aitask-scripts/aitask_create.sh \
             .aitask-scripts/aitask_ide.sh \
             ait
  ```
- Manual end-to-end on the workstation:
  1. `cd /home/ddt/Work/aitasks && ait projects add` — entry in
     `~/.config/aitasks/projects.yaml` with `name: aitasks`.
  2. `cd /home/ddt/Work/aitasks_mobile && ait projects add` — second entry.
  3. `ait projects list` — both listed with statuses.
  4. `ait projects resolve aitasks` — prints `/home/ddt/Work/aitasks`.
  5. `ait projects exec aitasks -- pwd` — prints the resolved root.
  6. From `aitasks_mobile`: `ait create --batch --project aitasks --name
     cross_repo_test --type chore --priority low --effort low --commit`
     lands the task in `/home/ddt/Work/aitasks/aitasks/`. Clean up
     the test task afterwards.

## Out of scope (carried forward)

- Adding `project:` block to sister
  `aitasks_mobile/aitasks/metadata/project_config.yaml` (user does this in
  the sister repo).
- Parser/tooling for the `aitasks#835_3` notation (notation is
  *documented* here, but consumers come later).
- Cross-project parent linkage (`--project X --parent Y`).
- Auto-clone from `git_remote` on `NOT_FOUND`.
- `ait projects remove` / `ait projects prune`.

## Step 9 reference

After implementation and review, follow the shared workflow's Step 9.
No worktree to clean (profile `fast` works on the current branch).
