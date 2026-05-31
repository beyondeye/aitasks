---
title: "Multi-Project Workflow"
linkTitle: "Multi-Project"
weight: 48
description: "Coordinate work across linked projects with the project registry, ait projects, and cross-repo task creation"
depth: [advanced]
---

When you run more than one aitasks project — say a `frontend` app and the `backend` service it talks to — work in one often needs to reach into the other: file a coordination task there, point at one of its files, or run a command inside it. The multi-project layer replaces brittle `../some-repo/` disk paths with **logical project names** that resolve to wherever each project currently lives.

## Why logical project names

Cross-repo coordination used to hardcode sibling paths like `../backend/`. That breaks the moment the on-disk layout differs — a teammate's machine, a cloud agent, or a fresh re-clone into a different directory. A per-user registry maps a logical name (`backend`) to a path, and every cross-repo command resolves the name at call time instead of trusting a hardcoded path.

## Per-project identity

Each aitasks project declares its logical identity in `aitasks/metadata/project_config.yaml`:

```yaml
project:
  name: backend
  git_remote: https://example.com/acme/backend.git
```

| Field | Required | Notes |
|---|---|---|
| `name` | No — defaults to the directory basename | Logical key. Lowercase `[a-z0-9_-]`, unique across your registered projects. |
| `git_remote` | No | Canonical clone URL. Shown in listings; reserved for future auto-clone. |

`ait projects add` reads this block; if `name` is omitted it falls back to the project directory's basename.

## The project registry

Registered projects live in a per-user index at `~/.config/aitasks/projects.yaml` (override the location with the `AITASKS_PROJECTS_INDEX` environment variable). It is a flat list:

```yaml
projects:
  - name: frontend
    path: /home/you/work/frontend
    git_remote: https://example.com/acme/frontend.git
    last_opened: 2026-05-31
  - name: backend
    path: /home/you/work/backend
    last_opened: 2026-05-31
```

The file is **gitignored** — it is per-user and machine-specific. Manage it with `ait projects add` rather than editing it by hand.

### How a name resolves to a path

When a command needs the path for a logical name, the resolver tries three sources in order:

1. **Live tmux scan** — currently running project sessions (matched by project name, then session name).
2. **Per-user index** — the `projects.yaml` registry above.
3. **Process environment** — an `AITASKS_PROJECT_<name>` variable set in the calling shell, useful as a manual override in non-tmux contexts (CI, remote agents).

Resolution reports one of three states, which surface throughout the tooling:

| State | Meaning |
|---|---|
| `RESOLVED` (listed as **LIVE** / **OK**) | The name maps to a valid aitasks project on disk. |
| `NOT_FOUND` | No registered project matched the name. |
| `STALE` | The name is registered, but its path no longer holds an aitasks project (moved or deleted). |

## The `ait projects` command

`ait projects` manages the registry and resolves names:

| Verb | What it does |
|---|---|
| `ait projects list` | List every registered project with its status (LIVE / OK / STALE). |
| `ait projects add [<path>]` | Register the project at `<path>` (default: current directory). Idempotent — re-running refreshes the entry. |
| `ait projects resolve <name>` | Print the resolver result for `<name>`: `RESOLVED:<path>`, `NOT_FOUND:<name>`, or `STALE:<name>:<path>`. |
| `ait projects exec <name> -- <command>` | Resolve `<name>`, `cd` into its root, then run `<command>` there. |
| `ait projects remove <name> [--force]` | Drop an entry from the registry. Prompts for confirmation unless `--force`. |
| `ait projects update <name> <new_path>` | Repoint a moved project to a new on-disk root (refreshes `last_opened`, keeps `git_remote`). |
| `ait projects prune [--dry-run] [--yes]` | Drop every STALE entry at once. Prompts per entry unless `--yes`; `--dry-run` lists matches without changing anything. |
| `ait projects doctor [--clone]` | Walk every STALE entry interactively, offering prune / update / clone / keep / skip-all per entry. Cloning is opt-in via `--clone` and only offered when the entry has a `git_remote`. |

A few examples:

```bash
# Register the project in the current directory, then confirm it is listed
cd /home/you/work/backend
ait projects add
ait projects list

# Run a one-off command inside a sibling project without leaving this one
ait projects exec backend -- ./.aitask-scripts/aitask_ls.sh -v 5

# Clean up after a project moves or is deleted
ait projects update backend /home/you/work/services/backend
ait projects prune --dry-run
```

## Creating a task in a sibling project

`ait create --batch --project <name>` creates a task in another registered project without leaving the one you are in. It resolves `<name>`, then runs that project's own task creation so the new task is numbered and committed in the sibling repo.

```bash
# From inside `frontend`, file a coordination task in `backend`
ait create --batch --project backend \
    --name bump_shared_protocol --type bug --priority high \
    --desc "Bump the shared wire protocol version after the frontend change" \
    --commit
```

Two constraints:

- `--project` requires `--batch` (non-interactive creation).
- `--project` cannot be combined with `--parent` — a task in a sibling project cannot be made a child of a task in this one.

## Referring to cross-project tasks and files

When a plan, commit message, or task description needs to point at another project's task or file, write the reference with the project's logical name:

```text
backend#835_3             # task 835_3 in the `backend` project (preferred)
backend#t835_3            # the leading `t` is also accepted
backend:src/protocol.rs   # a file inside the `backend` project
```

- For tasks: `<project>#<id>`, where `<id>` is a parent (`835`) or a parent-child pair (`835_3`). The `t` prefix is optional.
- For files: `<project>:<path>`, where `<path>` is relative to the project root.

Writing references this way keeps them unambiguous and machine-resolvable, instead of a disk path that only works on one machine.

Once names resolve, see [Cross-Project Dependencies]({{< relref "/docs/workflows/cross_project_dependencies" >}}) to block tasks on another project's work, read and update its tasks with `--project`, surface cross-repo links on the board, and plan a change that spans two repos.

## Switching between projects

The `ait` TUI's project switcher lists registered projects even when their tmux session is not currently running. Selecting an inactive project spawns its tmux session and teleports you into it. A project whose path has gone stale is shown dimmed with a `(stale)` marker; selecting it offers to prune the entry or repoint it to the project's new location.

`ait monitor` is intentionally **unchanged** — its multi-project view stays scoped to live tmux sessions only. Registered-but-inactive projects appear in the switcher, not in the monitor.

## Recipe: register a linked project and spawn a task in it

```bash
# 1. Make sure the linked project declares its identity
#    (aitasks/metadata/project_config.yaml → project.name: backend)

# 2. Register it from its own directory
cd /home/you/work/backend
ait projects add

# 3. Back in your current project, confirm the name resolves
ait projects list
ait projects resolve backend        # → RESOLVED:/home/you/work/backend

# 4. File a coordination task in the linked project
ait create --batch --project backend \
    --name add_pagination_endpoint --type feature --priority medium \
    --desc "Add the paginated list endpoint the new frontend screen needs" \
    --commit
```
