---
Task: t826_brainstorm_cross_repo_project_references.md
Base branch: main
plan_verified: []
---

# Parent Plan: Cross-Repo Project References (t826) — restructured as a multi-child task

## Context

When a task in one aitasks project needs to coordinate with a sister project
(create a sister task, reference a spec file, point to a related task), today
the only mechanism is the **sibling-directory path** (`../aitasks/`,
`../aitasks_mobile/`). That works on the author's PC but breaks on other
machines, on cloud runners, and on CI. Plan-readers also can't tell *which
logical project* is meant without checking the on-disk layout.

A second, distinct pain point — surfaced during this brainstorm — is that
**`ait ide`'s multi-project TUI switcher can only see projects whose tmux
sessions are already running**. To see project X in the switcher I have to
first `cd` into project X and run `ait ide` to spin up its tmux session. A
persistent registry of "every project ever opened" would let the switcher
surface inactive projects too, and auto-spawn their tmux session on
selection. (`ait monitor` is intentionally out of scope for this change —
its multi-project view stays scoped to currently-live tmux sessions.)

The framework already has **partial** infrastructure:
`.aitask-scripts/aitask_ide.sh:109` sets `tmux set-environment -g
AITASKS_PROJECT_<session>=<root>`, and `discover_aitasks_sessions()` in
`.aitask-scripts/lib/agent_launch_utils.py:255` enumerates live sessions into
`AitasksSession(session, project_root, project_name)`. **Missing**: a
persistent registry (closing tmux loses the map), explicit project identity
in `project_config.yaml`, a logical-name resolver helper, consumer-side
flags (notably `aitask_create.sh --project <name>`), inactive-project
surfacing in the TUI switcher, and user-facing documentation of the new
multi-project workflow.

t826 was originally a single brainstorm task; we now restructure it as a
**parent coordinating multiple sibling implementation tasks**. The parent
remains open as a holding pen so further multi-project pain points can be
added as additional siblings as they surface.

## Brainstorm decisions (locked)

| Question | Decision |
|---|---|
| Where does the canonical project registry live? | **Per-project + per-user index.** `project_config.yaml.project = { name, git_remote }` is per-repo source of truth; `~/.config/aitasks/projects.yaml` is the per-user index, auto-populated by `ait ide`. |
| Cross-repo task ID notation in plans/commits | **`aitasks#835_3`** (hash-separated, no `t` prefix — preferred). `aitasks#t835_3` (with `t`) is **also accepted** for symmetry with intra-repo file names. Tooling pattern: `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$`. Docs, examples, and tooling output default to the no-`t` form. |
| Single-task vs split | **Split into siblings.** Registry + `ait projects` + `aitask_create.sh --project` lands as t826_1; TUI/monitor inactive-project surfacing as t826_2; documentation as t826_3. |

## Architecture shared by all children

### Per-project identity — `project_config.yaml` schema addition

Add an optional top-level `project:` block:

```yaml
project:
  name: aitasks            # canonical logical name (registry key)
  git_remote: https://github.com/beyondeye/aitasks.git
```

If `project.name` is omitted, fall back to `tmux.default_session`, then to the
repo directory basename. Existing repos keep working without editing.
`git_remote` is optional; resolver auto-detects via `git remote get-url
origin` if missing.

### Per-user index — `~/.config/aitasks/projects.yaml`

```yaml
projects:
  - name: aitasks
    path: /home/ddt/Work/aitasks
    git_remote: https://github.com/beyondeye/aitasks.git
    last_opened: 2026-05-25T14:30:00Z
  - name: aitasks_mobile
    path: /home/ddt/Work/aitasks_mobile
    git_remote: https://github.com/beyondeye/aitasks_mobile.git
    last_opened: 2026-05-25T09:12:00Z
```

- File path: `${XDG_CONFIG_HOME:-$HOME/.config}/aitasks/projects.yaml`.
- Per-user, not git-tracked, no secrets.
- Atomic write (tempfile + `mv`).
- Upsert by `name`; resolver validates `path` exists before returning.

### Resolution semantics (used by t826_1 + t826_2)

Resolution order (first match wins):
1. **Live tmux scan** — `discover_aitasks_sessions()` match by session name or
   `project_config.yaml.project.name`. Authoritative because session is in scope.
2. **Per-user index** — `~/.config/aitasks/projects.yaml`, match by `name`,
   verify `path` exists.
3. **`AITASKS_PROJECT_<name>` tmux env var** — legacy fallback.

Outputs: `RESOLVED:<root>` / `NOT_FOUND:<name>` / `STALE:<name>:<path>`.

### Cross-repo notation — `aitasks#835_3` (preferred) / `aitasks#t835_3` (also OK)

A writing convention for plans and commit messages. Both forms are valid:
- **Preferred (default in docs / examples / tooling output):** `aitasks#835_3`
  — terser, mirrors GitHub `org/repo#123` issue refs where the `#` already
  signals "task/issue id".
- **Also accepted:** `aitasks#t835_3` — useful when copy-pasting from an
  intra-repo filename like `t835_3_foo.md` without stripping the prefix.

Tooling pattern: `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$` (the `t` is
optional). No parser shipped in this round — humans (and grep / future
tooling) can recognize both. Documented in `aidocs/cross_repo_references.md`
(authored in t826_1) and surfaced in user-facing workflow docs (t826_3),
both of which state the no-`t` form as the recommended default.

---

## Child task breakdown

### t826_1 — Registry, resolver, `ait projects` subcommand, `--project` flag

**Surface:**

- New helper `.aitask-scripts/aitask_project_resolve.sh` (internal — NOT a new
  `ait` subcommand, per CLAUDE.md feedback `ait_subcommands_user_facing_only`).
- New dispatcher `.aitask-scripts/aitask_projects.sh` exposed as `ait projects`:
  - `ait projects list` — one line per registry entry: `<name>\t<path>\t<git_remote>\t<last_opened>\t<status>` (LIVE / OK / STALE).
  - `ait projects add [<path>]` — register the project at `<path>` (default cwd). Requires `aitasks/metadata/project_config.yaml` present.
  - `ait projects resolve <name>` — convenience wrapper around the internal resolver; prints just `<root>` on success or exits 1.
  - `ait projects exec <name> -- <cmd> [args...]` — resolve, `cd` into root, exec the command. No `remove`/`prune` verb in this round.
- `ait` dispatcher: add `projects)` case around line 190 and add `projects`
  to the no-update-check exemption on line 169.
- `seed/project_config.yaml`: add commented `project:` template block.
- `aitasks/metadata/project_config.yaml`: populate `project: { name: aitasks, git_remote: ... }`.
- `.aitask-scripts/aitask_ide.sh`: after the existing `tmux set-environment` at
  line 109, call `"$SCRIPTS_DIR/aitask_projects.sh" add "$(pwd)" >/dev/null 2>&1 || true`.
- `.aitask-scripts/aitask_create.sh`: add `--project <name>` flag (batch-mode
  only). On set: resolve via the helper, `cd` into the resolved root, `exec`
  the script there with remaining args. Mutually exclusive with `--parent`
  (no cross-project parent linkage in this round). Refuse without `--batch`
  with a clear error.
- New `aidocs/cross_repo_references.md`: authoring convention for the
  cross-repo task ID notation (preferred `aitasks#835_3`, accepted
  `aitasks#t835_3`), registry overview, resolver semantics. Add a short
  "Cross-Repo Coordination" pointer in `CLAUDE.md` (Project-Specific Notes
  area).
- Tests: `tests/test_project_resolve.sh`, `tests/test_projects_cmd.sh`,
  `tests/test_create_project_flag.sh`. Use the existing `test_scaffold.sh`
  fake-repo helper.
- Whitelisting: `aitask_project_resolve.sh` is invoked only by other scripts
  (not directly by any SKILL.md) — does **not** need to enter the
  7-touchpoint helper-script whitelist (per memory
  `feedback_whitelist_only_for_skill_invoked_helpers`). `aitask_projects.sh`
  IS a user-facing `ait` subcommand, also no skill-whitelist requirement.
- Out of scope (note in plan's "Out of scope" section): adding `project:` to
  sister `aitasks_mobile` config (user does manually in sister repo or via
  cross-repo bump task once `ait projects add` is shippable); parser tooling
  for `aitasks#t822_5`; cross-project parent linkage; auto-clone on `NOT_FOUND`.

**Verification:**
- `bash tests/test_project_resolve.sh && bash tests/test_projects_cmd.sh && bash tests/test_create_project_flag.sh`.
- `shellcheck` the new scripts and modified files.
- Manual end-to-end (see Verification section in child plan file).

### t826_2 — TUI switcher shows registered-but-inactive projects

**Depends on t826_1** (needs the per-user index populated).

**Scope note:** `ait monitor` is intentionally **out of scope**. Only the
TUI switcher gains inactive-project visibility in this round.

**Surface:**

- Extend `discover_aitasks_sessions()` in
  `.aitask-scripts/lib/agent_launch_utils.py:255` with a new
  `include_registered=True` flag (default false to preserve current
  behavior; `ait monitor` and any other current callers keep the default).
  When true, also enumerate entries from `~/.config/aitasks/projects.yaml`
  whose `name` is not already covered by a live session, returning them as
  `AitasksSession(session=None, project_root, project_name)`. Add a new
  `is_live` property (True iff `session is not None`).
- Update `.aitask-scripts/lib/tui_switcher.py` (around line 8-13 — the
  multi-session enumeration block) to pass `include_registered=True` and
  render inactive entries plainly (per user's preference: no extra visual
  indicator needed; activity is implied by whether selecting it switches vs
  spawns).
- On selecting an inactive project in the switcher: spawn its tmux session
  via the same path `ait ide` uses (`tmux new-session -d -s <name>` + `cd
  <root>` + window setup), then `tmux switch-client -t <name>`. Reuse
  helpers from `aitask_ide.sh` — factor out the session-bootstrap block into
  a function in `.aitask-scripts/lib/` (e.g. `tmux_bootstrap.sh`) so both
  `ait ide` and the switcher call the same code.
- Do **not** change `ait monitor` (`.aitask-scripts/aitask_monitor.sh` or
  its Python TUI). Monitor stays scoped to live tmux sessions only.
- Tests: extend existing TUI tests or add a smoke test that the
  `include_registered=True` enumeration round-trips through the YAML index.
  Also add a regression test that calling
  `discover_aitasks_sessions()` (default, no flag) yields the same result as
  before (no inactive entries leak into existing callers).
- Manual verification subtask candidate: this child is largely TUI behavior;
  flag as a candidate for a manual-verification sibling at parent-task
  manual-verification checkpoint (Step 6.1).

**Verification:**
- Unit: `discover_aitasks_sessions(include_registered=True)` returns both
  live and registered-only entries with `is_live` set correctly; default
  call unchanged.
- Manual: open switcher with one inactive project in the index; confirm it
  appears; select it; confirm tmux session spawns and switcher teleports.
- Manual (regression): open `ait monitor` with the same registry state;
  confirm monitor still shows only live sessions (no inactive leakage).

### t826_3 — Documentation update for multi-project workflow

**Depends on t826_1 and t826_2** (so docs reflect the shipped surface).

**Surface:**

- Check `website/content/docs/workflows/` for an existing multi-project
  page. If present: update it. If absent: create
  `website/content/docs/workflows/multi_project.md` with appropriate Docsy
  frontmatter (mirror an existing workflow page's structure — e.g.
  `manual-verification.md`).
- Content:
  - Why: cross-repo coordination pain, persistent project registry.
  - The `project:` block in `project_config.yaml` (schema + example).
  - `ait projects` subcommand reference (list/add/resolve/exec).
  - `aitask_create.sh --project <name>` (cross-repo task creation walkthrough).
  - Cross-repo notation: preferred `aitasks#835_3` (no `t`), accepted `aitasks#t835_3` (with `t`); writing convention only.
  - TUI switcher inactive-project behavior (selecting an inactive project
    spawns its tmux session and teleports). Note explicitly that
    `ait monitor` is unchanged — its multi-project view stays scoped to
    live tmux sessions.
  - Recipe: "How to register a sister project and spawn a task there".
- Cross-link from `aidocs/cross_repo_references.md` (authoring-reference
  side) to the user-facing workflow page (per memory
  `feedback_authoring_docs_in_aidocs`: aidocs is design/reference, website
  is user-facing).
- Per CLAUDE.md "Documentation Writing": describe current state only — no
  "previously we…" prose.
- Build verification: `cd website && hugo build --gc --minify` succeeds and
  the new page is reachable from the workflows nav.

**Verification:**
- `cd website && ./serve.sh` and visually inspect the new/updated page.
- `cd website && hugo build --gc --minify` clean build.

---

## Parent-task workflow

Per task-workflow planning.md:

1. After this plan is approved, **create the 3 child tasks** via the Batch
   Task Creation Procedure (mode `child`, parent=826) — each gets the full
   per-child description text above.
2. **Write child plan files** for all 3 children to `aiplans/p826/`
   immediately (the parent plan's child-task sections are extracted into the
   child plan files).
3. **Revert parent t826 status to `Ready`** and clear `assigned_to` —
   `aitask_ls.sh` will show "Has children".
4. **Release parent t826 lock** so only child locks are held during child
   implementation.
5. Commit child task files (by `aitask_create.sh --batch --commit`) and
   child plan files (one batched `./ait git commit`).
6. **Manual-verification sibling checkpoint:** t826_2 is TUI-heavy. At the
   post-creation checkpoint, accept "Yes, but let me choose" and scope the
   manual-verification child to t826_2 only (t826_1 is unit-testable;
   t826_3 verifies via `hugo build`). This adds a t826_4 manual-verification
   child.
7. **Child-task checkpoint** (always interactive, profile-fast does NOT
   bypass): user picks "Start first child" → `/aitask-pick 826_1` or "Stop
   here" → end this session and pick children later.

## Future siblings (parent stays open)

t826 remains a holding pen. Add more multi-project pain points as additional
children with `ait create --batch --parent 826 …` as they surface. Likely
near-term candidates (NOT created in this round):

- Cross-project parent linkage in `aitask_create.sh --project X --parent Y`.
- Parser/tooling for the cross-repo notation (`aitasks#835_3` /
  `aitasks#t835_3`) — auto-linkify in plan rendering, jump-to-sister in TUI.
- `ait projects remove` / pruning of dead entries.
- Auto-clone from `git_remote` when resolver returns `NOT_FOUND`.

## Step 9 reference

After all children land, t826 itself archives automatically when the last
child archives (per `aitask_archive.sh` parent-archive logic).
