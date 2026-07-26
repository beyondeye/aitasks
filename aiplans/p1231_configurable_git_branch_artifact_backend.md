---
Task: t1231_configurable_git_branch_artifact_backend.md
Base branch: main
plan_verified: []
---

# t1231 — Configurable git-branch artifact backend

## Context

`ait artifact`'s zero-config `local` backend writes blobs into the
`.aitask-data` worktree (`attachments/blobs/<2>/<62>`) and commits them with
`task_git` — so every artifact lands on the **aitask-data branch**, the same
branch that carries every task and plan file. The target is implicit and not
configurable.

`aidocs/unified_artifact_design.md` §7 already names this as the problem:
*"`local` … bloats that branch for large HTML — which is exactly why shareable
plans should target a remote backend."* But the only shipped alternative is
`dir`, which needs an out-of-band mount every teammate must replicate. There is
no option that keeps blobs **in git** (so they travel with a clone, need no
mount, and need no credentials) while keeping them **off the task-data branch**.

`aitask-trail` (t1210) stores implementation trails through `ait artifact`,
which makes a well-defined default git target more pressing.

Secondary: the artifact feature has **no website documentation at all** — zero
hits for `ait artifact` / `ait attach` under `website/content/docs/`, and no row
in `commands/_index.md`. Only two blog posts mention it.

**Outcome:** a `gitbranch` artifact backend that stores blobs on a dedicated,
configurable orphan branch (default `aitask-artifacts`) via git plumbing only —
no second worktree, so blobs never materialize in any checkout — plus a settings
tab to configure it and the missing baseline docs.

## Decisions (confirmed with the user)

| # | Decision | Rationale |
|---|---|---|
| 1 | **Worktree-free plumbing branch** — `hash-object -w` / `mktree` / `commit-tree` / CAS push + `update-ref`, reads via `cat-file`. | Blobs live only in the object store + `~/.cache/ait/artifacts`. A second worktree would materialize every blob on disk, moving the bloat rather than removing it. Precedent: `aitask_lock.sh:102-112`, `aitask_claim_id.sh` — both worktree-free orphan branches. |
| 2 | **New adapter `gitbranch`**, not a `branch:` key on `local`. | `local` stays byte-identical (the "default config unchanged" AC holds for free), and it matches how the sibling backends t1089 (`s3`) / t1090 (`gdrive`) are specified. |
| 3 | **Lazy branch init on first write.** | No settings pane mutates git today except the profile "Save & Commit" button; keeping the artifacts pane a pure config editor avoids inventing network/retry UX inside the TUI. |
| 4 | **Fail-closed on a branch switch that would strand blobs**, with an explicit migration verb as the remedy. | Split-store ("read old, write new") was rejected: it makes resolution permanently dual-homed. See §"Store identity" for how fail-closed is made *correct* — the naive version of this guard does not work. |

### The simplification exploration found

`aitask_artifact.sh` guards blob-staging with `[[ "$backend" == "local" ]]` at
**seven** sites (L282, L308, L361, L366, L437, L530, L553). For a non-`local`
backend they already do the right thing: stage manifest + task file only, skip
the blob, and warn that cross-backend orphan reaping is t1135. `artifact_cache.sh`
L51/L96 likewise fall through to the generic `head`+`get` / copy-warm path.

**So `gitbranch` requires no changes to `aitask_artifact.sh`'s transaction,
rollback, or commit-path logic** — it slots in exactly where `dir` does. The only
CLI-layer additions are the store-identity guard and the migration verb below.

### Explicit scope exclusion

`ait attach` is **not** in scope. `aitask_attach.sh:225` hard-rejects any backend
but `local`, and `cmd_gc` L599 hard-codes `export ARTIFACT_BACKEND="local"` with
a comment asserting every stored blob is local. Extending attachments to
non-local backends is its own body of work (add path, gc blocking set, per-blob
meta ledger relpaths). Disposition: **documented-only exclusion in v1, follow-up
task created at decomposition time** (see Planned mitigations).

---

## Correctness model (the four load-bearing rules)

These were tightened during review; each one has a named test in t1231_1.

### R1 — The remote is the store of record; publish is push-gated

When a remote is configured, the store tip is **`refs/remotes/origin/<branch>`**.
The local `refs/heads/<branch>` is a mirror, never the authority.

**Fetch memoization is read-only.** A per-process memo (same shape as
`_ait_detect_data_worktree`) serves `head` / `get` / `list`, where one refresh per
process is enough. It must **never** serve a CAS iteration: every pass of the
`put` / `delete` loop begins with an unconditional `git fetch origin <branch>`
that also invalidates the memo. A lease rejection means the tip we observed was
stale *by definition*, so a retry against a memoized tip would rebuild the same
losing commit and lose again on every iteration until the budget is exhausted —
a livelock that only appears under real contention. The forced refresh is the
fix, and the concurrent-writer test below asserts the winner's tip was actually
observed (the loser's final commit has the winner's commit as its parent), not
merely that both blobs ended up present.

`put` therefore orders **push first, local ref second**:

1. build the new commit,
2. `git push --force-with-lease=refs/heads/<branch>:<observed-tip> origin <commit>:refs/heads/<branch>`,
3. only on success, `git update-ref refs/heads/<branch> <commit> <observed-tip>`.

A push that fails or is lease-rejected **does not return success** — a
lease rejection re-enters the CAS loop; exhaustion or a hard failure `die`s. This
reverses the earlier warn-and-continue idea, which was unsound: the very next
step of the artifact transaction commits a manifest on `aitask-data`, so a
locally-only blob would publish a handle that a second clone can resolve but
cannot `get`. (It was also inconsistent with `artifact_store`'s own post-`put`
lost-put `head` check at `artifact_cache.sh:87-109`.)

If the push succeeds and the local `update-ref` fails, the store is still
correct — a later fetch repairs the mirror.

**No remote configured** (single-user / offline repo): `refs/heads/<branch>` is
the authority, no push is attempted, and this is stated in the backend header and
the docs. Making push mandatory is what forces the offline-workflow follow-up in
Planned mitigations.

### R2 — First write bootstraps a root commit through the same CAS loop

There is no separate init step. The CAS loop branches on a **three-state store
probe**, `_artifact_gitbranch_probe`, re-evaluated on **every** iteration (a
branch can appear mid-loop):

| State | Meaning | Action |
|---|---|---|
| `ABSENT` | the ref exists neither on `origin` (when configured) nor locally | may be initialized |
| `STORE:<store_id>` | the ref exists and its tip carries a valid `.ait-artifact-store` | normal CAS append (subject to R4's id check) |
| `OCCUPIED` | the ref exists but its tip has **no valid marker** | **fail closed, always** |

- **`ABSENT`** → `tree` = `mktree` seeded with the blob **and** the
  `.ait-artifact-store` marker, `commit=$(git commit-tree $tree)` **with no
  `-p`**, then a **plain (non-force) push** `origin <commit>:refs/heads/<branch>`
  and `git update-ref refs/heads/<branch> <commit> ""` (empty old-value =
  "must not exist").
- **`STORE:<id>`** → `read-tree <tip>` / `commit-tree -p <tip>` / lease push, as above.
- **`OCCUPIED`** → die without mutating anything.

**Ref absence and marker absence are not the same thing.** The reserved-name
validator only blocks five names, so any ordinary feature or release branch is a
legal config value. Treating an existing unmarked ref as "not initialized yet"
would take the `STORE` path and append artifact blob commits onto a live branch —
or take the `ABSENT` path and fail its expected-absent CAS in a confusing way.
Only a ref that does not exist may be initialized:

> `artifacts.backends.gitbranch.branch is 'X', but branch 'X' already exists and
> is not an aitask artifact store (no .ait-artifact-store marker at its tip).
> Refusing to write artifact commits onto an existing branch — pick an unused
> branch name.`

Two concurrent first writers therefore cannot create incompatible roots: the
plain push is rejected as non-fast-forward for the loser, which re-enters the
loop, observes the winner's tip, and rebuilds on top of it. This is exactly the
`aitask_lock.sh:102-113` recipe (`mktree` → `commit-tree` → plain
`push <sha>:refs/heads/<branch>`), extended with a retry.

### R3 — Store identity, not marker existence

The settled registry model is **one instance per adapter**
(`unified_artifact_design.md` §6), so the store identity is project-level, not
per-manifest:

- **On the artifact branch:** `.ait-artifact-store`, committed with the root
  commit — `store_id: <32 hex>`, `branch: <name at init>`, `created_at:`.
- **On the data branch:** `artifacts/gitbranch_store.json` —
  `{"store_id": "...", "branch": "..."}`, committed inside the same path-scoped
  transaction as the first artifact's manifest.

`store_id` is generated once and **survives migration** — it is what makes the
identity stable while the branch coordinate moves.

**The generated id is provisional until the root push wins.** The guard's
absent-record/absent-marker arm is not serialized across clones: two clones each
running a first `ait artifact create` both pass it, and each mints a candidate
`store_id` into its own root commit. Exactly one root push wins (R2). The loser
must therefore treat its candidate as discarded:

1. after the CAS loop settles, **re-read `.ait-artifact-store` from the winning
   tip** and use *that* `store_id` for `artifacts/gitbranch_store.json`;
2. when rebuilding on an existing tip, **never overwrite an existing marker** —
   the rebuild adds only the blob.

So the marker is written exactly once, by whoever creates the root, and every
clone's data-branch record is derived from the branch rather than from its own
local candidate. Without this, the two clones' records diverge permanently and
the R4 guard starts failing on the loser for a store it can actually read.

### R4 — The guard runs on every gitbranch-touching operation

`_artifact_assert_gitbranch_store` in `aitask_artifact.sh`, called immediately
after `artifact_registry_activate` in **create, update, get, rm, list, and both
the source and target legs of move** — not just the write paths:

Its input is the R2 three-state probe, **not** marker presence alone:

| Record | Probe on configured branch | Action |
|---|---|---|
| absent | `ABSENT` | first use — allow; lazy init writes both |
| absent | `STORE:<id>` | adopt `<id>` into the record (fresh clone of an existing store) |
| present | `STORE:<matching id>` | allow |
| present | `ABSENT` | **die** — the store branch is gone or the config points somewhere new |
| present | `STORE:<different id>` | **die** — switched to an unrelated store |
| *any* | `OCCUPIED` | **die** — the branch exists but is not an artifact store (R2) |

The die message names the migration verb, not `ait artifact move`:

> `artifacts.backends.gitbranch.branch is 'Y', but this project's artifact store
> is <store_id> on branch 'X'. Blobs on 'X' will not resolve from 'Y'. Restore
> the branch name, or migrate the store with:
> ait artifact gitbranch-migrate --from X --to Y`

Comparing `store_id` (not marker presence) is what catches the switch to an
already-initialized but unrelated branch.

**Why not `ait artifact move`:** `_artifact_move_txn` short-circuits a
same-backend move as a no-op success, and manifests record only
`backend: gitbranch` with no branch coordinate — so `--to gitbranch` after a
rename does literally nothing while the source adapter already reads the new
branch. The earlier plan promised a repair path that cannot work.

**`ait artifact gitbranch-migrate --from <old> --to <new>`** is the real remedy.

**Target precondition, checked before any mutation**, using the same R2 probe:

| Probe on `<new>` | Action |
|---|---|
| `ABSENT` | allow — migration creates the root commit carrying `<old>`'s `store_id` |
| `STORE:<same id>` | allow — the resume case for an interrupted migration |
| `STORE:<different id>` | **die** — merging two independent stores |
| `OCCUPIED` | **die** — the target is an ordinary branch, not a store |

The last two both die before the first `put`, leaving `<new>`'s tip
byte-unchanged:

> `migration target 'Y' already holds artifact store <other_id>; this project's
> store is <store_id>. Refusing to merge two stores — pick an unused branch name.`

> `migration target 'Y' already exists and is not an aitask artifact store.
> Refusing to write artifact commits onto an existing branch — pick an unused
> branch name.`

Migration body: activate against `<old>`, enumerate every hash in
`artifact_manifest referenced-hashes` whose manifest records `backend:
gitbranch`, `get` each from `<old>` and `put` each to `<new>` (idempotent,
hash-verified, resumable — the same non-destructive shape as
`_artifact_move_txn`), write the marker on `<new>` **carrying the same
`store_id`**, update `artifacts/gitbranch_store.json`, and commit. `<old>` is
left untouched so a failed or aborted migration is recoverable by reverting the
config.

---

## Decomposition — 3 children

### t1231_1 — `gitbranch` artifact backend (the spike)

The risky, self-contained core. No TUI, no docs.

**New file `.aitask-scripts/lib/artifact_backends/gitbranch.sh`** — mirrors
`dir.sh`'s shape (fail-closed accessor → blob path → head/put/get/delete/list).

Config contract (single key; the remote is hard-coded `origin`, matching
`aitask_lock.sh`):

```yaml
artifacts:
  default_backend: gitbranch
  backends:
    gitbranch:
      branch: aitask-artifacts
```

On-branch layout: `blobs/<2hex>/<62hex>` plus the `.ait-artifact-store` marker.

Ops (all against `ARTIFACT_GITBRANCH_BRANCH`, exported by the registry; tip
resolution per **R1**):

- `_artifact_gitbranch_probe` — the R2 three-state classifier
  (`ABSENT` / `STORE:<id>` / `OCCUPIED`); the single seam the CAS loop, the R4
  guard and `gitbranch-migrate` all branch on, so the "existing unmarked branch"
  rule cannot be enforced in one place and forgotten in another
- `head <hash>` — `git cat-file -e <tip>:blobs/<2>/<62>`
- `get <hash> <dest>` — `git cat-file blob <tip>:<path>`; `-` streams to stdout
- `put <hash> <file>` — idempotent (`head` → return 0); `git hash-object -w`;
  then the bounded CAS loop of **R1**/**R2**, with every index operation under
  `GIT_INDEX_FILE=$(mktemp)`; verify with `head` before returning
- `delete <hash>` — same loop with `update-index --force-remove`
- `list` — `git ls-tree -r --name-only <tip> blobs/` → `sha256:<2><62>`

**Invariants to pin with tests:**

1. **`GIT_INDEX_FILE` isolation is mandatory.** The repo has concurrent writers;
   touching the real index would corrupt another session's staged work.
2. **CAS, never blind write** (R1/R2) — both the lease push and the old-value
   `update-ref` take the observed tip.
3. **Push-gated publish** (R1) — no success return without a successful push
   when a remote exists.
4. **Reserved-branch guard.** A new `ref_name` validator in
   `artifact_registry.py` rejects `main`, `master`, `aitask-data`,
   `aitask-locks`, `aitask-ids` (the reserved set from `aitask_web_merge.sh:222`)
   and enforces git ref-name shape. Pointing the blob store at `main` must be
   impossible, not merely discouraged.

**Registry wiring:**
- `artifact_registry.py` L44 `KNOWN_ADAPTERS["gitbranch"] = {"branch": ("ARTIFACT_GITBRANCH_BRANCH", "ref_name")}`,
  the `ref_name` arm in `validate_value` (L97), and the validator list in the
  `# BACKEND-EXTENSION-POINT (registry)` comment.
- **New `adapters` subcommand** — prints `local` + `sorted(KNOWN_ADAPTERS)`,
  i.e. the *available* adapters independent of config. `cmd_list` (L149-154)
  prints only *registered* backends, so on a fresh project `gitbranch` is
  unlistable and could never be selected to create its own first configuration.
  t1231_2's selector needs `adapters`; `list` stays as-is for "what is configured".
- **New `validate-ref <name>` subcommand** — exit 0/1 plus a message, so the
  settings TUI can validate a branch name *before* the backend is registered,
  without re-encoding the regex or the reserved list in Python UI code.
- `artifact_registry.sh` L33 `_AIT_ARTIFACT_REGISTRY_PARAM_VARS+=( ARTIFACT_GITBRANCH_BRANCH )`
  — required so `move` (which activates source then target in one process) does
  not leak params across activations.
- `artifact_backend.sh` — the `source` marker (L36), the `case` arm (L46), and
  the `known:` list in the `*)` die at L47.

**CLI layer (`aitask_artifact.sh`):**
- `_artifact_assert_gitbranch_store` per **R4**, wired into create / update /
  get / rm / list / move (both legs).
- `gitbranch-migrate` verb per **R3**, added to `main`'s dispatch (L672-685) and
  the help text.
- New `backends` subcommand on `lib/artifact_manifest.py` (distinct `backend`
  values across manifests) — needed by the guard and by migrate.

**Tests** — `tests/test_artifact_gitbranch_backend.sh`, modeled on
`tests/test_artifact_dir_backend.sh` (same `write_config()` fixture idiom), plus
a **bare-remote + two-clone** fixture cribbed from `tests/test_task_git.sh:26-40`:

- round-trip put → head → get (file and `-`) → list; idempotent double-put adds
  no second commit
- **first-write bootstrap** creates a parentless root commit carrying blob +
  marker; a second put extends it
- **two concurrent first writers** (both starting from no branch) end with both
  blobs present on one linear history — negative control for R2
- **two-clone concurrent full `ait artifact create`** (both starting from no
  branch): the branch carries exactly one `.ait-artifact-store` marker, and
  **both clones' `artifacts/gitbranch_store.json` converge on that one
  `store_id`** — the R3 provisional-id case. Negative control: assert the loser's
  record does *not* hold the id it originally minted
- **two-clone publish test:** clone A creates an artifact; clone B, which only
  fetches, resolves the handle **and gets its bytes** — the guarantee R1 exists
  to provide. Plus the negative control: with the remote made unwritable, `ait
  artifact create` **fails** and publishes no manifest on `aitask-data`
- **the user's index is untouched** across put/delete (stage an unrelated file
  first, assert `git diff --cached --name-only` is unchanged) — negative control
  for invariant 1
- concurrent-writer CAS on an existing branch: advance the ref behind the
  adapter's back mid-loop, then assert **both** that the retry lands both blobs
  **and** that the retry's commit has the interloper's commit as its parent —
  proving the forced refresh observed the new tip rather than rebuilding on the
  memoized one. A memo that leaked into the CAS loop passes the "both blobs"
  half only by accident, so the parentage assertion is the real oracle
- reserved-branch and malformed ref names die naming the key; `validate-ref`
  agrees with activation (single-sourced rule)
- unregistered / adapterless / missing-`branch` config dies (mirrors the dir tests)
- cross-activation leakage: activating `local` or `dir` clears `ARTIFACT_GITBRANCH_BRANCH`
- **guard matrix (R4)** — all six record×probe states, exercised through `get`
  and `rm` as well as `create`, including the switch to an already-initialized
  unrelated branch (the case marker-existence alone would miss)
- **unmarked existing branch is rejected, not adopted** — point
  `backends.gitbranch.branch` at an ordinary feature branch created in the
  fixture, then assert that **both** `ait artifact create` **and**
  `gitbranch-migrate --to <it>` die naming the branch, and that
  `git rev-parse <branch>` is identical before and after (no commit appended, no
  ref moved). Negative control: the same branch with a valid marker at its tip
  *is* accepted, proving the test discriminates marker validity rather than mere
  branch existence
- **`gitbranch-migrate`** moves every blob, preserves `store_id`, leaves the old
  branch intact, is idempotent on re-run (resume case: target already carries the
  same `store_id`), and lifts the guard
- **migrate target precondition (negative case)** — a target branch already
  carrying a *different* `store_id` dies **before the first `put`**: assert the
  error names both ids and that the target branch tip is byte-unchanged
  afterwards
- no-remote repo: local ref is authoritative, no push attempted, round-trip works

### t1231_2 — Artifacts settings tab (depends: t1231_1)

Ninth tab in `.aitask-scripts/settings/settings_app.py`. The nested-section write
pattern is already established by the Tmux tab — copy it, do not invent.

Six registration touch-points (all verified present):
1. `_TAB_SWITCH_ACTIONS` (L172-181) — `"switch_tab_artifacts": "tab_artifacts"`
2. `BINDINGS` (L1509-1516) — a `Binding(<key>, "switch_tab_artifacts", …, show=False)`.
   Only `k`, `o`, `z` are unbound (`a b c d e f g h i j l m n p q r s t u v w x y ?`
   are all taken; `j` is the TUI switcher, `?` the shortcut editor). **Recommend `k`**;
   re-verify against live `BINDINGS` at implementation time.
3. `action_switch_tab_artifacts()` stub (near L1706-1728)
4. `compose()` (L1573-1603) — `TabPane(self.label("switch_tab_artifacts", "Artifacts"), id="tab_artifacts")` wrapping `VerticalScroll(id="artifacts_content")`
5. `on_mount()` (L1605-1613) — `self._populate_artifacts_tab()`
6. Footer hint derives automatically from `_tab_switch_hint()` — nothing to update.

Pane contents, following `_populate_tmux_tab` / `save_tmux_settings` (L2846-2966):
an `ARTIFACTS_CONFIG_SCHEMA` with `default_backend` (a `CycleField` populated
from **`artifact_registry.py adapters`** — the new subcommand; `list` would omit
`gitbranch` on a fresh project and make it unselectable) and
`backends.gitbranch.branch` (a `ConfigRow`, default `aitask-artifacts`). Save
merges into `data["artifacts"]`, drops the section when it becomes empty, then
`save_project_settings` → `load_all` → repopulate. Selecting `gitbranch` as the
default writes both the `default_backend` and the `backends.gitbranch` entry, so
the config it produces is always self-consistent.

**Validation before persist**, using the Project-Groups modal pattern
(`AssignGroupScreen._accept_new`, L1131-1141) rather than the save-time
`yaml.safe_load` guard: reject bad ref names and reserved branches in the editor
so an invalid value never reaches disk. The rule is single-sourced by shelling
out to `artifact_registry.py validate-ref`, in the `_run_projects_group` style
(`subprocess.run`, never raises, timeout → rc=1) — the regex is not re-encoded
in UI code.

**Known hazard, stated in the pane hint:** `save_yaml_config`
(`lib/config_utils.py:167-172`) is `yaml.safe_dump` — it destroys every comment
in `project_config.yaml`, including the 37-line seeded `artifacts:` documentation
block. Pre-existing behavior for the Project and Tmux tabs, but this is the first
tab whose own seeded comments it would wipe. Decision: accept it (matching
existing behavior) and say so in the section hint; do **not** introduce a
comment-preserving YAML round-tripper as a side effect of this task.

**Tests** — `tests/test_settings_artifacts_tab.py`, combining the two shipped
templates: schema/save assertions from `tests/test_settings_learn_skill_guide.py`
(find the `ConfigRow` by `row_key`, set `raw_value`, call the real
`app.save_project_settings()`, reload with `load_yaml_config`, then blank it and
assert removal) and subprocess-seam stubbing from
`tests/test_settings_project_groups_tab.py` (stub the registry call on the
instance, assert exact argv). Named cases: the selector offers `gitbranch` on a
project with **no** `artifacts:` block (the bootstrap case), an invalid or
reserved branch name produces **zero** writes, and selecting `gitbranch` emits
both config keys.

### t1231_3 — Artifact documentation (depends: t1231_1, t1231_2)

Closes the pre-existing gap. No existing page mentions the feature.

- **New** `website/content/docs/concepts/artifacts.md` — the concept: stable
  `art:<id>` handle → manifest (`current`/`versions`/`backend`) → backend, the
  hash-first invariant, the universal local cache, and the backend table
  (`local`, `dir`, `gitbranch`) with when to pick each. Must state the
  `gitbranch` operating rules users can trip over: a reachable remote is required
  for writes, and a branch rename needs `gitbranch-migrate`. Frontmatter matches
  `concepts/git-branching-model.md` (`title`/`linkTitle`/`weight`/`description`/`depth: [advanced]`).
- **New** `website/content/docs/commands/artifact.md` — verb reference for
  `create/update/move/rm/ls/get/versions/gitbranch-migrate`, plus the `artifacts:`
  config block and the settings tab. Frontmatter matches `commands/lock.md`
  (`weight` in the 30s, `depth: [intermediate]`).
- `commands/_index.md` — a row in the hand-maintained table (Tools section) **and**
  an entry in the `## Usage Examples` bash block; both are manual lists.
- `concepts/_index.md` — a bullet under **Data model**, using the
  `{{< relref >}}` shortcode form that section uses (not the relative-link form
  `commands/_index.md` uses).
- `concepts/git-branching-model.md` L13-18 — add the `aitask-artifacts` row to
  the branch table, marked optional.
- `tuis/settings/reference.md` — the shortcut table (L14-26), the `## Tabs` table
  (L54-62) and the Configuration Files table (L75-88). Both tables are **already
  stale** (they omit the shipped Shortcuts tab / `s` key); fix that in the same
  pass rather than adding a ninth row to a wrong table.
- `tuis/settings/how-to.md:15` — the hardcoded `a / b / c / t / m / p` mouse line.
- `seed/project_config.yaml` L189-225 — extend the commented `artifacts:` block
  with the `gitbranch` example. The live `aitasks/metadata/project_config.yaml`
  has no `artifacts:` section at all and stays that way — `local` remains the
  default.
- `aidocs/unified_artifact_design.md` §5/§6 — register `gitbranch` in the backend
  narrative so the design doc does not go stale.
- **Drift guard** — extend `tests/test_website_doc_lists.sh` (the only website
  drift test) with a third check: every `ARTIFACT_BACKEND` `case` arm in
  `lib/artifact_backend.sh` must appear as a literal table cell in
  `concepts/artifacts.md`, with a tripwire asserting the parsed arm count is > 0.
  This is what stops t1089/t1090 from silently re-opening the docs gap.

## Risk

### Code-health risk: medium

- Git plumbing that writes objects and moves refs from inside an
  errexit-suppressed transaction tree, in a repo with known concurrent writers ·
  severity: medium · → mitigation: covered in-task by t1231_1's index-isolation,
  CAS, and concurrent-first-write negative controls
- A ninth tab in a shipped 3907-line single-file Textual app, whose save path
  destroys the seeded comments in `project_config.yaml` · severity: low · →
  mitigation: settings_yaml_comment_preservation
- Store identity is a second small ledger (branch marker + data-branch record)
  that must stay consistent with the manifests, and its creation is racy across
  clones · severity: medium · → mitigation: covered in-task by the R4 guard
  matrix tests plus the R3 two-clone convergence test

### Goal-achievement risk: medium

- The task says "artifact/attachment blob store", but `ait attach` hard-rejects
  non-local backends, so v1 delivers artifacts only · severity: medium · →
  mitigation: attach_non_local_backend_support
- Push-gated publish (R1) makes a reachable remote a hard requirement for
  `gitbranch` writes, so an offline user cannot create artifacts on this backend ·
  severity: medium · → mitigation: artifact_branch_offline_write_queue

### Planned mitigations

- timing: after | name: attach_non_local_backend_support | type: feature | priority: medium | effort: high | addresses: goal-achievement — v1 delivers artifacts only | desc: Extend `ait attach` (add path, gc blocking set, meta-ledger relpaths) to non-local backends so attachments can also live on the artifact branch.
- timing: after | name: artifact_branch_offline_write_queue | type: enhancement | priority: low | effort: medium | addresses: goal-achievement — push-gated publish blocks offline writes | desc: Let a gitbranch write commit locally while offline and defer publication, with an explicit pending-push state and a re-push path, so an unreachable remote does not block artifact creation outright.
- timing: after | name: settings_yaml_comment_preservation | type: enhancement | priority: medium | effort: medium | addresses: code-health — settings saves erase seeded config comments | desc: Replace save_yaml_config's yaml.safe_dump with a comment-preserving round-tripper so settings saves stop wiping the documentation blocks in project_config.yaml.

**Change from the confirmed set:** `artifact_branch_push_durability` was
confirmed while `put` warned and continued on push failure. Review made push
mandatory (R1), which dissolves that concern and creates the opposite one — an
offline user is now blocked. It is replaced by
`artifact_branch_offline_write_queue`, same timing, same priority. The other two
are unchanged.

**Creation timing:** t1231 is being decomposed, so its Step 8d never runs. All
three are created at decomposition time (immediately after plan approval,
alongside the children) as independent tasks with `depends: [1231]`.

## Verification

- `bash tests/test_artifact_gitbranch_backend.sh` — new; must exit 1 before the
  adapter exists (prove the harness can fail) and 0 after.
- `bash tests/test_artifact_dir_backend.sh`, `bash tests/test_artifact_cli.sh`,
  `bash tests/test_artifact_share_resolution.sh`, `bash tests/test_attach_local_backend.sh`
  — unchanged and still passing (the "default config unchanged → byte-identical"
  AC).
- `python3 tests/test_settings_artifacts_tab.py` plus the existing
  `test_settings_learn_skill_guide.py` / `test_settings_project_groups_tab.py`.
- `bash tests/test_website_doc_lists.sh` — extended guard.
- `shellcheck .aitask-scripts/lib/artifact_backends/gitbranch.sh` and `bash -n`
  on every touched script.
- Manual, two-machine: configure `default_backend: gitbranch`, `ait artifact
  create` a file, confirm `git log aitask-artifacts` has the blob commit, `git
  log aitask-data` has only manifest + task file, `git status` shows a clean
  index; then clone elsewhere and `ait artifact get` the handle. Rename the
  configured branch and confirm `get` **fails closed** naming
  `gitbranch-migrate`, run the migration, confirm `get` works again.

## Post-implementation

Per `task-workflow` Step 9 — merge approval, `ait gates run 1231` (the task
declares `risk_evaluated`), branch/worktree cleanup, archival.
