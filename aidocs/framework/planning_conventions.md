# Planning Conventions

Rules for writing or reviewing implementation plans.

> **Future refactor note:** These rules are candidates for promotion into the
> task-workflow planning procedure (`.claude/skills/task-workflow/planning.md`)
> so they fire at the moment plans are authored, not as a side document. Until
> that refactor lands, treat this file as the canonical reference and read it
> before drafting or splitting a plan.

## Refactor duplicates before adding to them

When an implementation plan would edit the same list, set, or configuration in
three or more separate files (e.g., adding one value to `DEFAULT_TUI_NAMES`,
`_DEFAULT_TUI_NAMES`, `KNOWN_TUIS`, and `project_config.yaml`), propose a
single-source-of-truth extraction before accepting the duplicated edit.

Duplicated state is the mechanism that produces drift bugs (stale config
masking new code defaults). Also evaluate replace-vs-merge semantics for
config overrides over code defaults — merge/additive semantics prevent future
drift when framework features are added.

## Plan split: in-scope sibling children, not deferred follow-ups

When splitting a complex parent task into children, default to all phases as
siblings (in scope), plus a trailing retrospective-evaluation child that
depends on the others. Do NOT mark later phases as "out-of-scope follow-up
tasks" when the parent has scoped them.

When committing to a design choice under partial information ("we'll know if
this is the right shape once we benchmark"), proactively propose the
retrospective-evaluation child — it documents outcomes and files standalone
follow-ups only if the collected data justifies them. The retrospective child
is bounded by the parent (a *child*, not a deferred top-level task), even
though its outputs may include new top-level tasks.

Applies to both architectural refactors and exploratory work whose right-
next-step depends on what the first step shows.

## Dead code goes into the sibling refactor task — never a vague follow-up

When a child-task plan would leave a function / global / branch / file
unreachable after the change lands, do NOT write "leave it for a future
cleanup" or "follow-up child" without naming the actual sibling. Identify the
right sibling task (whose explicit scope is `cleanup / refactor / migrate /
remove`) and drop a one-line note into that sibling's task file under
`## Notes for sibling tasks` (include file path + line range, so the future
implementer doesn't re-trace).

If no sibling fits, surface a NEW task creation as part of the current plan.
Do not bury cleanup intent in a `# DEPRECATED` comment alone — the
load-bearing signal is the task-file note that surfaces in `aitask_ls.sh`-
driven workflows.

## Gate plans on in-flight related tasks instead of forking ahead

When a planned task **mirrors, clones, or extends** rendering / data presented
by another task that is currently `Implementing` or `Editing`, do NOT propose
implementing the new task in parallel.

Add a "Sequencing — wait for tN to land" section to the plan, mark the new
task `depends: [N]` (or `Postponed`), externalize and commit the plan now (so
the design isn't lost), but exit via the "Approve and stop here" Step 6
checkpoint.

Forking ahead produces diverging UI / data — the new task ships an extension
that doesn't include the in-flight task's new fields. During planning, scan
`aitasks/t<id>_*.md` for `status: Implementing` and check for meaningful
overlap (mirrors / clones / extends, not just file proximity).

## No fallback-read workarounds for sync/desync root causes

For local-vs-remote desync symptoms, do NOT extend resolver helpers like
`resolve_task_file` / `resolve_plan_file` with `git show <remote_ref>:...`
fallback tiers. Such tiers hide the desync, bloat resolver chains, and
silently mask stale local state.

The right fix is to make desync **visible and resolvable** — best-effort
`warn` at script entry points (telling the user "you are out of sync"), and
integration with the dedicated syncer TUI + monitor / minimonitor / switcher
surfaces. Workarounds that read from `origin` behind the user's back are not
acceptable as "deeper fixes."

## Audit-only tasks with zero findings produce audit-only plans

When a follow-up audit task ("grep the codebase for the same class of bug")
finds zero additional occurrences beyond the single known case, do NOT propose
a regression-prevention test, AST scanner, or lint rule as the durable
deliverable. The audit itself is the deliverable: document method + findings +
"no code changes." A one-off bug with a known mechanism is not evidence of an
ongoing pattern.

If a second occurrence ever appears, reconsider then — note this trigger in
"Out of scope", don't pre-build the infrastructure. (Aligned with the
system-prompt rule "Don't add features, refactor, or introduce abstractions
beyond what the task requires.")

## Planning procedures run read-only — split design from creation

A procedure dispatched from the planning phase (`task-workflow/planning.md` §6.1,
reached via `EnterPlanMode`) must NOT create tasks, write files, or commit —
plan mode is read-only. When a planning-phase procedure needs to mutate state,
split it into two:

- A **design** part that runs during planning: explore, decide, record the
  decomposition in the plan, and return a flag (e.g. `cross_repo_planned: true`).
- A **creation** part that runs **after plan approval**, hooked at
  `task-workflow/SKILL.md` Step 7 (the single funnel for every "Start
  implementation" path) and gated on the threaded flag. It does the actual
  `aitask_create.sh` / commit work, then ends at its own child checkpoint.

Deferring creation to post-approval also gives the user a real approval gate
before any task is created ("Approve and stop here" cleanly defers creation to a
later pick). The landed single-repo and cross-repo decomposition flows
(`planning-cross-repo.md` design + `cross-repo-child-assignment.md` creation) are
the reference pattern.

## User-facing features: docs are a plan deliverable; reuse export/import

When planning a feature with a user-visible UI surface in any aitasks TUI:

- **Documentation is a first-class child task, not a verification afterthought.**
  Add a dedicated docs child under `website/content/docs/tuis/` — the affected
  per-TUI page, and `tuis/_index.md` when the feature spans multiple TUIs —
  created **before** the manual-verification sibling. Don't fold docs into a
  verification step or assume they happen organically.
- **Mirror the existing export/import path instead of inventing a parallel one.**
  Any "save user data to disk + reload it" subsystem must route through
  `export_all_configs` / `import_all_configs` in
  `.aitask-scripts/lib/config_utils.py` (the settings TUI's
  `action_export_configs` / `action_import_configs` backing) — extend them by
  parameter / selector rather than building a fresh export helper with its own
  format.
