---
priority: medium
effort: medium
depends: [t832_1]
issue_type: feature
status: Ready
labels: [cross_repo, aitask_update]
created_at: 2026-05-26 18:29
updated_at: 2026-05-26 18:30
---

## Context

Part of t832 brainstorm decomposition. Adds `--project <name>` to
`aitask_update.sh` — the mirror of `aitask_create.sh --project` shipped
by t826_1. Without this, the parallel-planning procedure (t832_5)
cannot wire **symmetric** cross-edges (both sides have `xdeps:`
pointing at each other), because of the chicken-and-egg ID dependency:

1. Create local children L1..Ln first (regular `aitask_create.sh`).
2. Create cross-repo children S1..Sn with `aitask_create.sh --project B
   --xdeps L1,L2 --xdeprepo A` (now-known local IDs go into cross-repo at create).
3. **Update local children** to add `xdeps: [S1, S2] xdeprepo: B`
   (now-known cross-repo IDs).

Step 3 is where this child earns its keep. It also enables administrative
cross-repo updates (label/priority/status changes from outside the owning
repo) and xdeps maintenance.

## Key Files to Modify

- `.aitask-scripts/aitask_update.sh` — add `--project <name>` argv-prefix
  parsing to `main()` before the subcommand/flag dispatch. Copy the
  pattern from `aitask_create.sh:1693-1753`:
  - Parse `--project <name>` out of argv.
  - Resolve via `aitask_project_resolve.sh`; die-with-hint on STALE/NOT_FOUND.
  - On success: `cd "$root"; exec "$root/.aitask-scripts/aitask_update.sh" "${forwarded[@]}"`.

## Required guardrails (unlike create)

- **`--project` requires `--batch`** (mirror create's restriction at line 1730).
- **Lock check:** refuse the cross-repo update if the cross-repo task is
  locked by a *different* host/email. Fail with a clear "cross-repo task
  t<N> is locked by <owner>@<hostname>; cannot update from this host".
  The local flow can mutate the file but cannot acquire the cross-repo
  task's lock cleanly; silently overwriting a lock-held task corrupts the
  multi-PC reclaim signal. Use `aitask_lock.sh --check <N>` (re-exec'd
  in cross-repo context) to read the lock state.
- **Status transitions:** allow cross-repo updates ONLY for the
  administrative subset:
  - `--xdeps`, `--xdeprepo`, `--labels`, `--add-label`, `--remove-label`
  - `--priority`, `--effort`
  - `--deps`
  - `--status Postponed`, `--status Ready`, `--status Editing`
  - `--assigned-to`
  - `--boardcol`, `--boardidx`
  
  Refuse cross-repo `--status Implementing` and `--status Done` — those
  always go through the cross-repo project's own `/aitask-pick` workflow
  (which handles lock acquisition, plan externalization, and archival in
  one place). This guardrail keeps cross-repo update **administrative**,
  not workflow-bypassing.

## Reference Files for Patterns

- `.aitask-scripts/aitask_create.sh:1693-1753` — the canonical re-exec
  pattern for `--project`. Copy verbatim with the appropriate
  `aitask_update.sh` substitutions.
- `.aitask-scripts/aitask_lock.sh --check <N>` — lock state probe; should
  emit `hostname:` and `owner:` lines that can be parsed.

## Implementation Plan

1. Add `--project` argv-prefix parsing in `main()` mirroring create.
2. Enforce `--batch` requirement.
3. Enforce status-transition allowlist BEFORE re-exec (parse `--status`
   from forwarded argv; reject `Implementing` / `Done` with a clear hint
   pointing at `/aitask-pick`).
4. Resolve, re-exec the cross-repo helper.
5. Inside the re-exec'd target, add a lock-check step before the actual
   update: read `aitask_lock.sh --check` output, compare hostname/owner
   against the local user. If mismatch, die with the lock-held message.
6. Update `show_help()` to document `--project` and its restrictions.

## Verification Steps

- New test file: `tests/test_update_cross_repo.sh`
  - Two fake projects A and B with registered registry.
  - **Success cases:**
    - Update a task in B from A via `--project B --batch --priority high` → succeeds, B's task is modified, A's PWD unchanged.
    - Update `--xdeps "1,2" --xdeprepo A` cross-repo → succeeds.
    - Update `--status Postponed` cross-repo → succeeds.
  - **Refusal cases:**
    - `--project B` without `--batch` → die with hint.
    - `--project B --status Implementing` → die with "go through /aitask-pick" hint.
    - `--project B --status Done` → die with "go through /aitask-pick" hint.
    - B's target task is locked by a different host → die with "locked by ..." message.
- `shellcheck .aitask-scripts/aitask_update.sh` clean.
- Manual: from `aitasks`, run
  `./.aitask-scripts/aitask_update.sh --project aitasks_mobile --batch <id> --add-label test`
  and confirm the label lands cross-repo without affecting local PWD.

## Notes for sibling tasks

- t832_5 (parallel-planning procedure) consumes this for symmetric
  cross-edge wiring. The full flag list (`--xdeps`, `--xdeprepo`, etc.)
  must work via `--project`.
- The lock-check pattern here may be useful in future cross-repo helpers
  (e.g., cross-repo fold) if those ever land.

## Out of scope

- **Cross-repo archive** — split-brain risk; archival is naturally bound
  to the owning repo's pick workflow. Use `cd <cross-repo-root> &&
  /aitask-pick` instead.
- **Cross-repo `--fold`** — folding requires reading both task bodies
  and a primary task to fold into; cross-repo folding semantics are
  unsettled. Defer until t832_6 dogfooding reveals real need.

See parent plan §t832_7 for the full design context.
