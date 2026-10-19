---
Task: t1231_3_artifact_documentation.md
Parent Task: aitasks/t1231_configurable_git_branch_artifact_backend.md
Sibling Tasks: aitasks/t1231/t1231_1_gitbranch_artifact_backend.md, aitasks/t1231/t1231_2_artifacts_settings_tab.md, aitasks/t1231/t1231_4_manual_verification_configurable_git_branch_artifact_backend.md
Archived Sibling Plans: aiplans/archived/p1231/p1231_1_*.md, aiplans/archived/p1231/p1231_2_*.md
Base branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-19 15:49
Output branch: main
---

# t1231_3: Artifact documentation

## Context

`ait artifact` has shipped three backends: `local`, `dir`, and `gitbranch`
(t1231_1, 3d9e4371d). It also has an **Artifacts** settings tab on key `k`
(t1231_2, 7b357af39). The website still has **no page** for the feature: there is no
`concepts/artifacts.md` and no `commands/artifact.md`, and `commands/_index.md`
does not list `ait artifact`. This task writes the baseline docs, documents
`gitbranch` and the settings tab, and fixes the stale settings tables. It also adds
a drift guard so a future backend (`s3` t1089, `gdrive` t1090) cannot ship
undocumented.

### Verification findings (2026-10-19, against HEAD 7b357af39)

The July plan's structure holds. These premises changed and are corrected below:

1. **Attachments docs now exist** (t1687_2): `concepts/attachments.md`
   (weight 55, the last bullet in the Data model list) and `commands/attach.md`
   (weight 34). Both have a row in the Tools table and a usage line. They are the
   closest models for structure and tone. **Only `ait artifact` is left to do.**
2. **The concept page has a newer, stricter contract.**
   `aidocs/framework/documentation_conventions.md` "Concept pages" requires
   `## What it is` / `## Why it exists` / `## How to use` / `## See also` plus a
   **Next:** footer, with no `###` deep-dives, and leaves validation and failure
   rules to the reference page. So the concept page **states** the three gitbranch
   rules a user can trip over, one sentence each. The command page **owns** the
   detailed behaviour: guard messages, retirement, UNKNOWN exit 75, and resume.
3. **The Next: chain follows the `concepts/_index.md` order** (t1687_5). Inserting
   Artifacts after Attachments means retargeting `attachments.md`'s footer from
   Execution profiles to Artifacts. `artifacts.md` gets its own footer pointing
   to Execution profiles.
4. **gitbranch behaviour that actually shipped** (t1231_1 final notes and inbox note;
   checked against `aitask_artifact.sh` / `gitbranch.sh`):
   - Store identity lives in `artifacts/gitbranch_store.json` on the data branch.
     It is written by the first gitbranch write.
   - The store is created lazily. `init-store gitbranch` creates it eagerly and
     also **publishes** a store that so far exists only locally.
   - Writes need `origin` when one is configured. A push whose outcome cannot be
     confirmed exits **75 (UNKNOWN)**. With no `origin`, the local branch is the
     store of record.
   - The guard needs no network on a cache hit, so an offline warm `get` works.
     `rm` and `ls` never touch the store.
   - An existing non-store branch is refused (`OCCUPIED`). Reserved names: `main`,
     `master`, `aitask-data`, `aitask-locks`, `aitask-ids`, `HEAD`. Branch names
     must match `[A-Za-z0-9][A-Za-z0-9._/-]*`.
   - `gitbranch-migrate --from X --to Y` copies every blob and keeps the store id.
     It **retires** X permanently (X stays readable but refuses writes). It prints
     `MIGRATED:<id>:<to>` or `ALREADY_MIGRATED:<id>:<to>`, and on failure prints
     the retained effects plus `Resume with:`. Afterwards it warns you to set
     `artifacts.backends.gitbranch.branch: Y`; until you do, every gitbranch op
     refuses. `move --to gitbranch` from gitbranch is a same-backend no-op.
5. **The CLI has a 9th verb, `init-store`**, plus a dirty-path preflight (t1698):
   create, update, move and rm refuse when a non-blob path they would stage is
   dirty, and roll back from a snapshot. The command page documents both.
   `artifact_max_size_mb` (default 25) caps create and update. `rm` sweeps orphan
   blobs only on `local`; on any other backend it warns.
6. **Settings staleness is wider than the task says.** In addition to
   `reference.md`'s three tables and `how-to.md:15`, the `_index.md` "Navigating"
   table also omits `t` and `k`, and `_index.md` has no Artifacts section. From
   `settings_app.py`: tab bar order (`compose()` L2207-2226) is Agent Defaults a,
   Board b, Project Config c, Project Groups g, Tmux t, Artifacts k, Models m,
   (Execution) Profiles p, Shortcuts s. `BINDINGS` L2069-2117 adds global `j`
   (TUI switcher) and `?` (shortcut editor; on a Profiles field it toggles the
   field description instead, L2563).
7. **Existing cross-reference sites.** Earlier notes ask for these to be linked
   once the page exists, and they are verified in the tree:
   - the bare `` `ait artifact` `` at `development/task-format.md:98`;
   - the same at `skills/aitask-trail.md:85`;
   - `workflows/implementation-trails.md:131` ("stored as a versioned artifact");
   - the See also list in `concepts/implementation-trails.md`.
8. **Weights.** Command pages use non-grid weights (34, 36, 37, 38, 42). I use
   **33** for `commands/artifact.md`, just before Attach. For the concept page I
   use **57**, between Attachments (55) and Execution profiles (60), so the
   sidebar order matches the `_index.md` order. No existing weight changes.

9. **Plan-review corrections (2026-10-19)**:
   - The drift-guard parser now accepts the unquoted extension-point arm form, and
     is cross-checked against `lib/artifact_backends/*.sh`. Probed: the live file
     gives `local dir gitbranch`; adding either form of an `s3` arm adds `s3`.
   - The gitbranch origin rule is now qualified for the no-origin mode
     (`gitbranch.sh` header R1: "Without a remote, refs/heads/<branch> is
     authoritative").
   - The create option defaults were corrected to match `cmd_create`.

## Implementation steps

### 1. NEW `website/content/docs/concepts/artifacts.md` (~60-80 lines)

Frontmatter: `title: "Artifacts"`, `linkTitle: "Artifacts"`, `weight: 57`,
`description: "Versioned task outputs behind a stable art:<id> handle — new versions and backend moves never rewrite the task file."`,
`depth: [advanced]`.

- **What it is**:
  - An artifact is a versioned output (HTML plan, trail, report, mockup) owned by
    one task.
  - The task's `artifacts:` frontmatter records only a stable `art:<id>` handle
    (plus kind and name).
  - A manifest holds the mutable state: `current`, the `versions` list, and
    `backend`.
  - Every version is an immutable, SHA-256-addressed blob, resolved through a local
    cache (`~/.cache/ait/artifacts/<hash>`) and hash-verified.
  - One plain chain line: handle → manifest → backend → cache.
  - The **backend table** gives each name its own literal cell (the drift-guard
    target):

    | Backend | Where blobs live | Pick it when |
    |---|---|---|
    | `local` | Committed on the task data branch (default, zero-config) | Getting started, small artifacts, offline work |
    | `dir` | A mounted directory shared by the team (absolute path, initialized once) | A team share/NAS everyone mounts at the same path |
    | `gitbranch` | A dedicated branch (default `aitask-artifacts`), pushed to `origin` when the repository has one | Blobs in git without bloating the task data branch, no mount, no secrets |

  - Then three one-sentence gitbranch rules:
    - when the repository has an `origin`, a write succeeds only once it has been
      pushed there, so `origin` must be reachable (publish is push-gated); in a
      repository with no `origin`, the local branch is the store and nothing is
      pushed;
    - the branch must be one the store owns, so an existing ordinary branch or a
      reserved name is refused;
    - renaming the branch needs `ait artifact gitbranch-migrate`, not
      `ait artifact move`.
  - Link to the command page for the details.
- **Why it exists**: large or evolving outputs need a home that is versioned and
  shareable, without churning task files. The point is the hash-first invariant: a
  new version or a backend move touches only the manifest, never a task file. It
  also lets you keep big blobs off the data branch.
- **How to use**: 3-4 example commands (`create`, `update`, `get`, `ls`). Note that
  `/aitask-trail` stores trails as artifacts. Choose the backend in `ait settings`
  → Artifacts (`k`) or in `artifacts:` in `project_config.yaml`.
- **See also**:
  - `commands/artifact` (relref);
  - `concepts/attachments` (the immutable single-version sibling);
  - `development/task-format#nested-fields-artifacts-and-attachments`;
  - `concepts/git-branching-model` (the optional `aitask-artifacts` branch);
  - `tuis/settings`;
  - `workflows/implementation-trails#where-a-trail-is-stored`.
- `---` + `**Next:** [Execution profiles]({{< relref "/docs/concepts/execution-profiles" >}})`.

All relrefs use the full `/docs/...` path (several slugs collide).

### 2. NEW `website/content/docs/commands/artifact.md`

Frontmatter: `title: "Artifact"`, `linkTitle: "Artifact"`, `weight: 33`,
`description: "ait artifact — create, version, fetch and move a task's handle-addressed artifacts"`,
`depth: [intermediate]`. Structure mirrors `commands/attach.md`:

- An intro paragraph with a link to the concept page.
- `## ait artifact`: an examples bash block and a verb table (create, update, move,
  rm, ls, get, versions, init-store, gitbranch-migrate, help). Every signature
  is copied from `show_help` (verified above).
- One `###` per verb, each with the behaviour as coded:
  - **create**: an option table with one default each, as `cmd_create` codes them:
    - `--kind` is required (`[a-z][a-z0-9_]{0,31}`);
    - `--handle` is optional (`art:[a-z0-9][a-z0-9._-]{0,127}`). Without it the
      handle is derived as `art:t<task>-<kind without underscores>` (child `_` → `.`);
    - `--name` is an optional label. When omitted, the frontmatter entry carries
      no `name`;
    - `--backend` is optional. Without it, create uses `artifacts.default_backend`,
      or `local` when that is unset.

    It refuses an archived task and anything over the size cap, and prints
    `HANDLE:<handle>`.
  - **update**: a new version that repoints `current`. It never touches the task
    file, and identical bytes do nothing.
  - **move**: copies every version to a registered backend, verifies, then
    repoints. Source blobs stay. A same-backend move does nothing. It resumes on
    re-run.
  - **rm**: removes the frontmatter ref. When nothing else references the
    artifact, the manifest is deleted and orphan blobs are swept on `local` only.
    It refuses a bundled owner. A stale reference is still removable.
  - **ls**: both column layouts (per-task and global), with the HASH column
    abbreviated.
  - **get**: stdout or `--out`, plus `--version <sha256:…>`. Bytes are
    hash-verified, and a warm cache works offline.
  - **versions**: oldest first, `*` marks current.
  - **init-store**: `dir` needs it, run with the share mounted. For `gitbranch` it
    is optional and eager, and also publishes a store that exists only locally.
    For `local` it prints "needs no initialization".
  - **gitbranch-migrate**: covers everything in finding 4: retirement, the
    MIGRATED/ALREADY_MIGRATED output, `Resume with:`, then setting the config
    branch.
- `### The gitbranch backend`:
  - lazy creation and the store record file;
  - with an `origin`: a write succeeds only after the push is accepted; an
    unreachable `origin` fails the write; an unconfirmable push exits 75
    (UNKNOWN). Offline writes are not supported;
  - with no `origin`: the local branch is the store of record and nothing is
    pushed. A store created before `origin` was added is published by the next
    write or by `init-store gitbranch`;
  - branch-name rules and the refused existing branch;
  - the rename → migrate rule;
  - an offline cache-hit `get` works; `rm` and `ls` never touch the store.
- `### Uncommitted changes`: the dirty-path preflight plus snapshot rollback
  (attach.md's wording, adapted).
- `## Configuration`: the `artifacts:` YAML example (gitbranch), a key table
  (`artifacts.default_backend`, `artifacts.backends.dir.path`,
  `artifacts.backends.gitbranch.branch`, `artifact_max_size_mb`), and a pointer to
  `ait settings` → **Artifacts** (`k`). Note that `dir` has no row in the tab and
  that saving from the tab drops the file's comments. Add the one-line
  `ait attach` cross-reference (attachments are always `local`).

### 3. Hand-maintained lists and cross-references

- `commands/_index.md`:
  - a Tools-table row
    `| [`ait artifact`](artifact/) | Create, version, fetch and move task artifacts (see [Artifacts](../concepts/artifacts/)) |`,
    placed just before the `ait attach` row (relative-link style);
  - a usage line `ait artifact ls 357   # List task 357's artifacts`, next to the
    `ait attach` line.
- `concepts/_index.md`: a Data model bullet after Attachments (shortcode style):
  `- **[Artifacts]({{< relref "/docs/concepts/artifacts" >}})** — Versioned task outputs behind a stable handle; new versions and backend moves never rewrite the task file.`
- `concepts/attachments.md`: the footer **Next:** → Artifacts.
- `concepts/git-branching-model.md`: a table row
  `| `aitask-artifacts` (optional) | Artifact blobs, only when the `gitbranch` artifact backend is configured; the name is configurable. Written without a worktree. |`,
  plus a See also bullet to `concepts/artifacts`.
- Cross-reference links (finding 7):
  - `development/task-format.md:98`: link `` `ait artifact` `` to
    `{{< relref "/docs/commands/artifact" >}}`;
  - `skills/aitask-trail.md:85`: the same;
  - `workflows/implementation-trails.md:131`: link "versioned artifact" to
    `/docs/concepts/artifacts`;
  - `concepts/implementation-trails.md`: a See also bullet for Artifacts.

### 4. Settings docs: rebuild from `settings_app.py`

- `tuis/settings/reference.md`:
  - **Global table**: tab keys in tab-bar order a, b, c, g, t, k, m, p, s, then
    e, i, r, `j` (TUI switcher), `?` (shortcut editor; see Within Tabs), q.
  - **Within Tabs**: add rows for Artifacts (Enter edits the branch, ←/→ cycles
    the backend). Leave the existing rows alone.
  - **`## Tabs` table**: nine rows in tab-bar order, adding Tmux's position,
    Artifacts (`k`, Yes, "`artifacts:` block of `project_config.yaml` — default
    backend and gitbranch branch"), and Shortcuts (`s`, Yes, "keyboard shortcuts
    of every TUI").
  - **Configuration Files**: `project_config.yaml` →
    "Yes (Project Config, Tmux, Artifacts)", with the description extended to cover
    the `artifacts:` backend registry. Add an `aitasks/metadata/userconfig.yaml`
    row: User, "Yes (Shortcuts)", `shortcuts:` overrides.
- `tuis/settings/how-to.md:15`: `a` / `b` / `c` / `g` / `t` / `k` / `m` / `p` /
  `s`. Add a short `## Configure Artifact Storage` how-to: press `k`, cycle the
  backend, edit the branch (validated before the dialog closes), then Save. The
  branch-change note names `gitbranch-migrate`.
- `tuis/settings/_index.md`:
  - a `### Artifacts (k)` section after Project Groups: what the two rows edit;
    `dir` is not configurable in the tab; selecting gitbranch pre-fills
    `aitask-artifacts`; Save validates through the registry and commits; Save
    drops comments; link to the concept page;
  - the Navigating table gains `t` and `k`.

### 5. Drift guard: `tests/test_website_doc_lists.sh` Test 3

- Add the header-comment item 3, the constants `ARTIFACT_BACKEND_SH` and
  `ARTIFACTS_DOC`, and two `assert_file_exists` preconditions.
- Parse the arms of `_artifact_backend_call`, accepting **both** dispatch forms:
  the quoted form in use today (`dir)   "artifact_dir_${op}" "$@" ;;`) and the
  unquoted form the file's own `BACKEND-EXTENSION-POINT (dispatch)` comment tells
  contributors to write (`name) artifact_name_${op} "$@" ;;`). Use a bash
  `[[ =~ ]]` loop over the dispatcher file. Avoid sed backreferences: they are
  not portable to BSD sed ERE.
  ```bash
  arm_re='^[[:space:]]*([a-z][a-z0-9_]*)\)[[:space:]]+"?artifact_[a-z0-9_]+_\$\{op\}'
  ```
  `[1]` is the backend name. A line starting with `#` (the extension-point
  comment) and the `*)` catch-all both fail the leading `[a-z]` anchor.
- **Tripwires** (a parse that misses an arm must fail, not just "be non-empty"):
  - `assert_contains_re` that the parsed list is non-empty, plus a count `> 0`
    via `assert_exit_zero_rc`, as Test 2 does;
  - **independent cross-check**: the sorted parsed set must equal the sorted
    basenames of `.aitask-scripts/lib/artifact_backends/*.sh` (today `dir`,
    `gitbranch`, `local`). Every backend is a module file plus an arm, so an arm
    the regex cannot read, or a module with no arm, makes the sets differ.
    `assert_eq` on the two newline-joined lists.
- For each name: `assert_contains "concepts/artifacts.md documents backend '<n>'" "| \`<n>\` |" "$doc_body"`.
- No subshells, so the file-backed counters are not needed.

### 6. Non-website files

- `seed/project_config.yaml` (artifacts block, ~L313-354): add a `gitbranch`
  paragraph in the same comment style:
  - a dedicated branch, no mount and no secret. When the repository has an
    `origin`, every write is pushed there and needs it reachable; without one,
    the local branch is the store;
  - lazy creation, or eager via `ait artifact init-store gitbranch`;
  - the branch must be unused or already a store; reserved names are rejected;
  - renaming needs `ait artifact gitbranch-migrate --from <old> --to <new>`.

  Also add a commented gitbranch example. The commented `dir` example stays. The
  live `aitasks/metadata/project_config.yaml` is not touched.
- `aidocs/unified_artifact_design.md`:
  - **§5**: replace the "same backend table as t1030" sentence's implicit list with
    the implemented set (local, dir, gitbranch; s3/gdrive pending).
  - **§6**: "the first configured backend is `dir`" → name both configured
    backends. Add a short `gitbranch` paragraph (orphan branch, plumbing only,
    push-gated, `gitbranch_store.json` identity, `gitbranch-migrate`). Point to
    `lib/artifact_backends/gitbranch.sh` and the archived p1231_1 plan.
  - **§3**: CLI verb list → add `move`, `init-store` and `gitbranch-migrate`.

### Post-phase (risk mitigations)

1. [claim_audit] Build a claim → code-anchor table for every behavioural statement
   on `commands/artifact.md`, `concepts/artifacts.md`, the settings `## Tabs`,
   Global and Configuration Files tables, and the seed gitbranch paragraph. Each
   row cites the backing line: `show_help`, the `cmd_*` / `_artifact_*_txn`
   message, `gitbranch.sh`, `artifact_registry.py check_ref_name`, `BINDINGS` /
   `compose()`. Correct or delete any claim with no backing line. Record the table
   in the plan's Final Implementation Notes.
2. [next_chain_walk] Run a script that starts at `concepts/tasks.md`, follows each
   `**Next:**` relref, and asserts the visited order equals the
   `concepts/_index.md` bullet order exactly once, ending at `agent-memory`. Then,
   right before committing, run `git diff HEAD --stat` on the shared list files
   (`commands/_index.md`, `concepts/_index.md`, `tuis/settings/*.md`,
   `concepts/attachments.md`, `concepts/git-branching-model.md`). Confirm that only
   this task's hunks are present (commit only named paths).

## Verification

- `cd website && hugo build --gc --minify` succeeds.
- `cd website && python3 check_links.py --build` passes (mandatory after editing
  `website/content/`).
- `bash tests/test_website_doc_lists.sh` passes, with Test 3 listing local, dir and
  gitbranch.
- **Red proof, isolated**: copy the test, `tests/lib/asserts.sh`, the codeagent and
  skills inputs, `lib/artifact_backend.sh` and the new `concepts/artifacts.md` into
  a scratch tree with the same layout. Delete the `gitbranch` row there, run, and
  confirm exit 1 with the gitbranch assertion failing. Then, in fresh scratch
  copies, run three more mutants, each of which must exit 1 naming `s3`:
  - (a) a **quoted** `s3) "artifact_s3_${op}" "$@" ;;` arm plus an
    `artifact_backends/s3.sh` module, with no doc row;
  - (b) the same with the **unquoted** `s3) artifact_s3_${op} "$@" ;;` form (the
    extension-point pattern), with no doc row;
  - (c) an `s3.sh` module with no dispatch arm, which the cross-check catches.

  Control: the unmutated scratch copy exits 0. Never mutate the shared worktree.
- `grep -rn "ait artifact" website/content/docs/` shows the two new pages, the
  `_index.md` rows and the linked call sites.
- Walk the concepts **Next:** chain from `tasks.md`. It must visit Attachments →
  Artifacts → Execution profiles, in `_index.md` order.
- Cross-check every settings-table key against `BINDINGS` / `_TAB_SWITCH_ACTIONS`.
- `python3 check_link_relevance.py` (offered, not a gate) for the new links.
- `./serve.sh` (manual): sidebar placement of both pages.

## Step 9 (Post-Implementation)

Merge approval, `ait gates run 1231_3`, archival per task-workflow Step 9.
t1231_4 (manual verification) is still pending, so the parent stays active.

## Risk

### Code-health risk: low
- Docs plus one containment assertion block in an existing test. The only shared
  code-adjacent files are the seed comment block and the design doc. None
  identified beyond that.

### Goal-achievement risk: low
- Behavioural claims on the new pages could misstate the shipped CLI or gitbranch
  semantics. The design doc and the task body both predate t1231_1's change
  requests, so a reader would trust wrong rules · severity: low (residual —
  addressed by inline post-phase claim_audit) · → mitigation: inline post-phase claim_audit
- Concurrent sessions may edit the same hand-maintained lists (`commands/_index.md`,
  `concepts/_index.md`, settings `reference.md`), and the Next: chain could break
  · severity: low (residual — addressed by inline post-phase next_chain_walk)
  · → mitigation: inline post-phase next_chain_walk

### Planned mitigations
- timing: post-phase | name: claim_audit | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: misstated CLI/gitbranch behaviour | desc: claim → code-anchor table for every behavioural statement on the new/edited pages
- timing: post-phase | name: next_chain_walk | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: concurrent list edits / broken Next chain | desc: scripted Next-chain walk vs _index order + pre-commit diff of shared list files
