---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [brainstorming, ait_monitor, aitask_create]
children_to_implement: [t826_3]
created_at: 2026-05-25 14:28
updated_at: 2026-05-31 12:26
boardidx: 50
---

Brainstorm and refine: easier cross-repo references when an aitasks project's task needs to reach into a sister aitasks project (create a task there, reference a file/spec, coordinate work across both).

## Pain (real-world example)

Today, when a task in `aitasks_mobile` needs to spawn a coordination task in the sister `aitasks` repo (e.g. t13_2 just did this — added `name=` to the applink QR URL spec and created a sister task under t822), the plan has to refer to the sister project by its **disk path** (`../aitasks/`). That works on the author's machine but is brittle:

- It assumes a specific sibling-directory layout on disk.
- Re-runs on a different machine (or in CI / cloud) break.
- Reviewers reading the task plan can't tell *which* logical project is meant — only its path.
- Cross-repo task IDs in Final Implementation Notes (e.g. "see sister t822_5") have no way to point back to the actual repo URL or to a resolvable path.

## What we already have (worth reusing, not reinventing)

- **`ait` IDE TUI switcher** — knows about projects the user has opened, one tmux session per project.
- **`ait monitor`** TUI — currently has the most integration for multi-repo views (which projects are active, their statuses).
- **Tmux session naming convention** — one session per project, matching the project's directory name (e.g. `aitasks`, `aitasks_mobile`).
- **Per-project `.aitask-data/` symlinks** and `./ait` wrapper — each project already knows its own repo root and git remote.

So the missing piece is a *registry* and a *lookup skill* — not a new TUI.

## Idea seeds (to chew on, not commit to)

### Seed A — Live tmux scan + project resolver skill

A new skill (working name: `aitask-projects` or `ait-projects`) that:
1. Enumerates currently active tmux sessions (`tmux ls -F "#S"`).
2. For each session, reads the associated project's repo root from a side-channel (per-session env var set by `ait`, or by inspecting `tmux display-message -t <session> -p '#{session_path}'`).
3. Returns a map: `{ session_name → { repo_root, git_remote, branch } }`.
4. Other skills (aitask-contribute, aitask-create with cross-repo intent, etc.) can resolve loose names like "sister project aitasks" or "the aitasks repo" without the user typing a path.

**Open question:** what's the canonical mapping — is the tmux session name always equal to the project's directory basename, or do we need an explicit registration step inside `ait` when a project is opened?

### Seed B — Persistent project registry

Survives across tmux session lifetimes. A per-user file (e.g. `~/.config/aitasks/projects.yaml` or `~/.aitask-projects.json`) recording every aitasks project ever opened with `ait`:

```yaml
projects:
  - name: aitasks
    path: /home/ddt/Work/aitasks
    git_remote: https://github.com/beyondeye/aitasks.git
    last_opened: 2026-05-25
    tmux_session: aitasks       # optional, if currently active
  - name: aitasks_mobile
    path: /home/ddt/Work/aitasks_mobile
    git_remote: https://github.com/beyondeye/aitasks_mobile.git
    last_opened: 2026-05-25
    tmux_session: aitasks_mob
```

Populated automatically by `ait` (or `ait setup` / first task pick) on a new project, refreshed on every open. Skills consult this file when a tmux scan doesn't find a live session for the named project.

### Seed C — Loose references in task plans

Plans / commit messages should reference sister projects by a **logical name** (the registry key), not by `../path/`. Examples:

```
# instead of:
(cd ../aitasks && ./.aitask-scripts/aitask_create.sh ...)

# we'd write:
ait projects exec aitasks -- ./.aitask-scripts/aitask_create.sh ...
# OR
aitask_create_in --project aitasks --parent 822 --name ...
```

The resolver fills in the actual path at call time, using the registry from Seed B (falling back to Seed A's tmux scan).

### Seed D — Cross-repo task ID syntax

Right now t13_2's plan references the sister task as "t822_5". Within this repo that's ambiguous (there's no t822 here). A normalized form could be:

```
[aitasks]t822_5
[aitasks_mobile]t13_2
```

so the project namespace is explicit. Tooling (`aitask_query_files.sh`, `aitask_issue_update.sh`, etc.) becomes project-aware.

## Brainstorm goals

1. **Decide the canonical project identity** — directory basename, git remote, explicit registry key, or a combo.
2. **Decide where the registry lives** and who writes to it (`ait`, skills, both).
3. **Decide the failure modes** — what happens if a referenced project isn't in the registry / isn't checked out / has moved on disk? Auto-clone from `git_remote`? Prompt? Fail loudly?
4. **Decide the surface** — new skill(s), CLI subcommand(s), or extensions to existing skills (`aitask-contribute`, `aitask-create`'s batch mode, `aitask-pick` when picking work that references a sister task)?
5. **Decide what to do about already-open PRs / running TUIs** — should the resolver bias toward live tmux sessions when they exist? Yes, probably (they're an authoritative "this project is currently in scope" signal).

## Out of scope (separate brainstorms if needed)

- Cross-repo *merge* coordination (e.g. atomic landing of paired changes in two repos). This task is just about *references and task creation*, not about transactional commits.
- Cross-repo CI / pipelines.

## Cross-references

- Origin of this brainstorm: pain felt during `aitasks_mobile/aitasks/archived/t13/t13_2_sister_qr_add_hostname_field.md` (the sister task was `t822_5`, but the plan had to spell out `../aitasks/` everywhere).
- Likely consumers once landed: `aitask-contribute`, `aitask-create --batch` (cross-repo flavor), `aitask-pick` (when picking work that references a sister task).

## Next steps

1. Refine the seeds above in a brainstorm session (likely using `aitask-explore` or a dedicated brainstorm pass).
2. Pick a concrete solution shape.
3. Spawn child implementation tasks (registry file format, `ait projects` subcommand, resolver-aware version of `aitask_create.sh`, skill updates).
4. Update the relevant aidocs in this repo so other code agents know how to reference sister projects without disk paths.
