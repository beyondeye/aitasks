# Cross-Repo Project References

Authoring-reference for the cross-repo project registry and resolver
introduced by t826_1. Read this when:

- Designing a feature that needs to reach into a sibling aitasks project
  (create a task there, reference a file/spec, coordinate work).
- Writing a plan, commit message, or task description that mentions a
  cross-repo project's task ID.
- Modifying the resolver / registry / `ait projects` / `aitask_create.sh
  --project` surfaces.

## Why

Cross-repo coordination tasks used to hardcode sibling paths like
`../aitasks/`. That broke whenever the sibling layout on disk differed
(another machine, a cloud agent, a re-clone into a fresh dir). The
registry replaces the implicit "wherever-on-disk" assumption with an
explicit logical name that the resolver maps to a path at call time.

## Project identity

Each aitasks project declares its logical identity in
`aitasks/metadata/project_config.yaml`:

```yaml
project:
  name: aitasks
  git_remote: https://github.com/beyondeye/aitasks.git
```

| Field        | Required | Notes |
|--------------|----------|-------|
| `name`       | No (default: directory basename) | Logical key. Lowercase, `[a-z0-9_-]`. Must be unique across the user's registered projects. |
| `git_remote` | No       | Canonical clone URL. Used for display today; reserved for future auto-clone-on-`NOT_FOUND`. |

`ait projects add` reads this block; if `project.name` is absent it falls
back to `basename(project_root)`.

## Registry file

Per-user index at `~/.config/aitasks/projects.yaml` (override with the
`AITASKS_PROJECTS_INDEX` env var). Flat list of entries:

```yaml
projects:
  - name: aitasks
    path: /home/ddt/Work/aitasks
    git_remote: https://github.com/beyondeye/aitasks.git
    last_opened: 2026-05-25
  - name: aitasks_mobile
    path: /home/ddt/Work/aitasks_mobile
    last_opened: 2026-05-25
```

Managed by `ait projects add` (atomic write, idempotent). The file is
**gitignored** (per-user, machine-specific). Edit by hand at your own
risk — `ait projects add` is the canonical interface.

## Resolver

`./.aitask-scripts/aitask_project_resolve.sh <name>` is the internal
resolver. The user-facing entry point is `ait projects resolve <name>`,
which re-emits the resolver's output verbatim.

**Resolution order:**

1. **Live tmux scan** — `discover_aitasks_sessions()` in
   `.aitask-scripts/lib/agent_launch_utils.py:255` enumerates currently
   live tmux sessions. Matches `<name>` against `project_name` (basename
   of the project root) first, then `session`. This step already covers
   the tmux global env var `AITASKS_PROJECT_<sess>` set by `ait ide` —
   `discover_aitasks_sessions()` falls back to it internally.
2. **Per-user index** — `~/.config/aitasks/projects.yaml` (above).
3. **Process env var** — `AITASKS_PROJECT_<name>` set in the calling
   shell environment. Useful as a manual override for non-tmux contexts
   (CI, remote agents). This is the *process* env var, not the tmux
   global with the same shape (the tmux global is consumed by step 1).

**Output protocol** (always exit 0, exactly one line on stdout):

| Line                      | Meaning |
|---------------------------|---------|
| `RESOLVED:<absolute-path>`| Project found; path is a valid aitasks project root. |
| `NOT_FOUND:<name>`        | No registered project matched. |
| `STALE:<name>:<path>`     | Registered, but `<path>` no longer contains `aitasks/metadata/project_config.yaml`. |

Consumers parse on the prefix and treat unknown prefixes as failure.

## Consumers

**`ait projects exec <name> -- <cmd>`** — resolves `<name>`, `cd`s into
the root, then `exec`s `<cmd>`. Errors on `NOT_FOUND` / `STALE`.

**`ait create --batch --project <name> ...`** (`aitask_create.sh
--project`) — re-execs the sibling project's own `aitask_create.sh`
with `--project <name>` stripped from argv. Requires `--batch`. Cannot
be combined with `--parent` (cross-project parent linkage is out of
scope for v1).

```bash
# From inside aitasks_mobile, spawn a coordination task in aitasks:
ait create --batch --project aitasks \
    --name fix_shared_protocol --type bug --priority high \
    --desc "Bump applink wire version after mobile change X" --commit
```

## Cross-repo task ID notation

When a task or plan needs to point at another project's task, use:

```
aitasks#835_3            # preferred
aitasks#t835_3           # accepted; the `t` prefix is tolerated
```

Pattern: `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$`

- The part before `#` is a registry key (matches `project.name` from the
  sibling's `project_config.yaml`).
- The part after `#` is a parent ID (`835`) or a parent-child pair
  (`835_3`). Tooling parses both, matching the in-project convention.

Tooling that consumes this notation is out of scope for t826_1 (the
notation is documented; parsers come in later siblings). Use it in
plans / commit messages / task descriptions so the convention spreads
ahead of the tooling.

## Cross-repo file path notation

For pointing at a file inside a registered cross-repo project, use:

```
aitasks_mobile:Sources/Login.kt
```

Pattern: `^([a-z0-9_-]+):([^:].*)$`

- The part before `:` is the registry key (same project namespace as
  the `#` task notation above).
- The part after `:` is the file path relative to the project root.

The colon separator is unambiguous because POSIX file paths cannot
contain `:` and project names cannot contain `:` either. The
`aitask_create.sh` interactive flow emits this notation when a user
picks a file from the cross-repo project via the "Add cross-repo
file reference" menu item.

Like the `#` task notation, this is authoring-only — downstream
tooling that resolves the path lives in follow-up tasks.

## Failure modes & escalation

| Resolver output | Recommended caller behavior |
|-----------------|-----------------------------|
| `RESOLVED:` | Proceed. |
| `NOT_FOUND:` | Show a `cd /path/to/<name> && ait projects add` hint. Never auto-clone (out of scope; the user picked the name explicitly and is the source of truth). |
| `STALE:` | Show the stale path; suggest running `ait projects add` from the project's current location. |

## What is NOT in scope (planned for follow-ups)

- Cross-project parent linkage (`--project X --parent Y`).
- Auto-clone from `git_remote` on `NOT_FOUND`.

## See also

- User-facing workflow guide:
  `website/content/docs/workflows/multi_project.md` — the registry,
  `ait projects`, cross-repo task creation, and notation, written for end
  users.
- User-facing workflow guide:
  `website/content/docs/workflows/cross_project_dependencies.md` — cross-repo
  dependencies (`xdeps`/`xdeprepo`), `--project` data retrieval and mutation,
  board surfacing, and paired cross-repo planning, written for end users.
