---
Task: t2365_keep_codex_headless_prerenders_in_sync.md
Base branch: main
Output branch: main
---

# t2365 — Keep Codex headless prerenders in sync across install / upgrade / setup

## Context

A consumer (thinking_app t327) hit `DIRTY_TREE:2` after a framework upgrade: the tracked
`.agents/skills/aitask-pickrem-remote-codex-/SKILL.md` and `…pickweb-remote-codex-/SKILL.md`
had gained the tool-mapping pointer, and `materialize-active.md` plus the whole
`task-workflow-remote-codex-/` were untracked. Root cause, verified by code reading:

1. **Upgrade never delivers the Codex prerenders.** `install.sh install_codex_staging`
   (install.sh:938) copies the release's `codex_skills/` only into the staging dir
   `aitasks/metadata/codex_skills/`. Nothing on the upgrade route writes `.agents/skills/`
   (including `codex_tool_mapping.md`). Claude differs: `install_skills` copies `skills/`
   straight into `.claude/skills/`.
2. **The refresh dirties tracked files after the commit.** install.sh:1995-2004 runs
   `refresh_codex_rendered_entries` after `commit_installed_files` ("Rendered dirs are
   gitignored, so this commits nothing" is false for the `!`-re-included remote dirs).
3. **Setup delivers only part of the set.** `setup_codex_cli` copies `aitask-*/SKILL.md`
   only: never `materialize-active.md`, never `task-workflow-remote-codex-/`.
4. **The committed set is incomplete and stale.** Measured in a clean clone of `HEAD`
   (5ac9ad49d) with `seed/profiles/*` provisioned, `aitask_skill_verify.sh` reports 6
   `PRERENDER_FAIL`:
   - missing `ait-git-remote-{claude,codex,opencode}` `SKILL.md` (a closure member that
     is gitignored);
   - missing `.claude|.opencode/skills/task-workflow-remote-/task-data-push.md` (t1912_3
     source, never re-rendered for those two agents);
   - stale `.claude|.opencode/skills/task-workflow-remote-/{SKILL,planning,cross-repo-child-assignment}.md`.
     t1154 tracks the OpenCode part of this drift.

   The ignored or uncommitted local renders hide every one of these in a working checkout.

**Goal (scope as revised):** a *clean* install (+ setup) and a *clean* upgrade converge on
the current release's exact headless file list, Codex tool mapping included. Every
pre-existing change to a listed path is preserved and reported, including files hidden
by the old ignore rules and paths reached through linked ancestors. The release runs the
existing freshness check in a clean Git checkout provisioned with the shipped seed
profiles before packaging, and the same holds for the local release fixture. **Out of
scope:** automatic recovery of already-dirty checkouts, and OpenCode working-tree
delivery (staging only, unchanged).

## Design

- **One exact manifest per release.** The tarball carries `seed/headless_prerenders.txt`:
  every tracked file under the committed headless prerender dirs for all three agents,
  plus `.agents/skills/codex_tool_mapping.md`. It is generated in the release checkout
  only after the freshness check passes there. Install stores it at
  `aitasks/metadata/headless_prerenders.txt`, and setup reads it there. Consumer steps act
  on exactly these paths, never on the contents of the never-pruned staging dirs.
- **Ignore-independent protection snapshot.** Each manifest path is classified directly,
  before anything is written.
  - *Clean* means every ancestor below the project root is absent or a real directory
    (not a symlink, not a non-directory), and the path is either tracked (index == HEAD,
    worktree == index, a regular file) or neither tracked nor present.
  - Anything else is protected: modified, staged, deleted, untracked, *ignored* on disk, a
    symlink or directory where a file should be, a **linked or non-directory ancestor**,
    or a failed probe (unverified).
  - Protected paths are never written, are unioned into the run's dirty baseline (the
    existing commit subtraction then excludes and lists them), and are reported with
    their reason.
- **No reconciliation (strict mode).** In a project whose framework is tracked
  (`.aitask-scripts/VERSION` in the index), protected stays protected, even when its bytes
  equal the release. The upgrade baseline stays strict.
- **Bootstrap ownership rule.** Bootstrap means VERSION is not in the index: a fresh
  install, before the first framework commit. There the existing setup baseline is empty
  (commit-all), and the installer's own output is untracked. Strict mode would exclude
  that output from the first setup commit. Skipping protection would sweep local edits in.
  So a manifest path is **owned by the framework**, and committable, only when all of
  these hold at snapshot time:
  - no linked or non-directory ancestor;
  - it is a regular file;
  - it is not in the index (nothing staged);
  - it is not ignored;
  - its SHA-256 equals the manifest's recorded hash for that path;
  - its executable bit matches the manifest's recorded Git mode (`100755` ⇔ `-x`,
    `100644` ⇔ not `-x`). The hash cannot see a `chmod +x`, but `git add` stages it as
    `100755`, so bytes alone would let the first setup commit adopt a local mode change.

  Anything else is protected even in bootstrap: divergent bytes, any staged entry (even
  one with equal bytes), ignored, linked, non-file, or a hash that cannot be computed
  (unverified). An absent path is clean. Each mode is chosen per run from the same
  `_version_tracked` probe its committer uses. A failed probe makes every manifest path
  protected.
- **Delivery does not depend on setup.** Scope decision (user, 2026-11-26): install.sh
  writes the manifest's `.agents/skills/` files on **fresh install and on every
  upgrade**, whether or not the project ever set up Codex, just as Claude's prerenders
  already ride `install_skills`. **Installer copy changes are limited to Codex**
  (user, 2026-11-27): `install_skills` (Claude) is unchanged. It keeps copying the
  release's `skills/`, newly including `ait-git-remote-`, with today's semantics. A clean consumer checkout can therefore load
  both Codex remote skills and their referenced files with no prior `ait setup` and no
  local renderer. Codex *configuration* (`.codex/config.toml`, the SessionStart hook,
  `.codex/instructions.md`, the question server, the `aitask-*` wrappers) stays opt-in
  behind `setup_codex_cli`'s consent prompt. A project without Codex gains inert
  `.agents/skills/` files.
- **The refresh never touches shipped paths.** It skips the dirs of manifest paths, and it
  never closure-renders an entry whose profile has shipped dirs.
- **One release-verify entry point** used by CI and the local fixture alike, so the two
  cannot diverge.

## Implementation steps

0. **Prerequisite: fold t1154 and land the remote prerenders (separate commits, before
   anything else).**
   - Right after plan approval (the fold writes, so it cannot run in plan mode), run the
     Ad-Hoc Fold Procedure for t1154: `aitask_fold_content.sh` piped to
     `aitask_update.sh --desc-file -`, then `aitask_fold_mark.sh --commit-mode fresh 2365
     1154`.
   - **Render in a scratch clone, not in the shared tree.** Nothing is written or staged
     in the shared checkout until the comparison below passes.
     1. `git clone` the shared repo's `HEAD` into the scratchpad. Provision
        `aitasks/metadata/profiles/` there from `seed/profiles/` (`mkdir -p` + `cp`), and
        add the three `!…/ait-git-remote-…/` negations to the clone's `.gitignore`.
     2. In the clone only, run `aitask_skill_render.sh aitask-pickrem` and
        `aitask_skill_render.sh aitask-pickweb` with `--profile remote`, for each agent
        (claude, codex, opencode). These are exactly the renders whose closure the
        verifier checks, so no other variant is touched.
     3. **Early render comparison (in the clone):** take the landing set `L` = `git -C
        <clone> status --porcelain --untracked-files=all` restricted to the 12 headless
        dirs (11 files in the dry run), with the clone's bytes `B(p)`. Any change outside
        those dirs (other than `.gitignore` and the untracked `aitasks/`) means the render
        reached further than expected: **stop and ask**. The full verifier is **not** run
        yet, because it can pass only once 0b is also present (see the 0b gate).
   - **Compare against the shared tree, read-only, working copy *and* index:**
     - **Working copy.** For every `p` in `L`, the shared tree's file must be byte-equal to
       `HEAD`'s version (or absent, when `p` is new in `L`) or byte-equal to `B(p)`.
     - **Index.** For every `p` in `L`, nothing may be staged: for a tracked `p`, `git diff
       --cached --quiet -- p` exits 0 (index == `HEAD`). For a new `p`, `git ls-files
       --error-unmatch -- p` fails (not in the index). A staged version, even one equal to
       `B(p)`, means another session put it there: **stop**. A path-scoped commit takes
       the working copy and would silently replace it.
     - **Outside `L`.** Every other path under the 12 dirs is clean, staged or not
       (`git status --porcelain --untracked-files=all -- <dirs>` ⊆ `L`, and `git diff
       --cached --name-only -- <dirs>` is empty).
     - **`.gitignore`.** It is clean in both the working copy and the index.
     - Any violation means a foreign edit or staged change: **stop and ask**, with nothing
       written.
   - **Only then write:** copy `B(p)` into the shared tree for each `p` in `L` whose bytes
     differ, and apply the same `.gitignore` edit. Immediately before staging, re-run the
     index check (another session may have staged something meanwhile). Then commit those
     paths plus `.gitignore` by name, using `git add` for the untracked ones:
     `chore: Commit missing and stale remote prerenders for all agents (t2365)`. Run
     `git show --stat` on the new sha to confirm that exactly `L` plus `.gitignore` landed.
   - **0b. Make the parity stage independent of non-shipped profiles** (separate commit,
     `test: Pin the profiles the runtime-vs-rendered parity fixtures encode (t2365)`).
     - Measured in the dry-run clone: after the 11-file landing, the verifier still fails
       with seed profiles, at its final stage, `tests/test_skill_parity_runtime_vs_rendered.sh`.
       That test reads `PROFILES_DIR=$PROJECT_DIR/aitasks/metadata/profiles` (line 74), and
       its frozen fixtures encode this repo's live `fast` profile
       (`manual_verification_followup_mode: ask`), while the shipped seed says `never`. With
       the live profiles copied in, the verifier exits 0.
     - Add `tests/fixtures/skills/profiles/{default,fast,remote}.yaml`: exact copies of the
       live profiles the fixtures were frozen against, with a header comment naming that
       purpose. Point `PROFILES_DIR` there, so the test is identical in a working repo, in
       CI and in a clean release checkout.
     - Apply 0b in the **same scratch clone** first, on top of the step-3 render. Then run
       the full **existing** verifier there with seed profiles
       (`AIT_PYTHON=~/.aitask/venv/bin/python ./.aitask-scripts/aitask_skill_verify.sh`).
       It must report 0 failures; this was the dry-run result. Only then write 0b into the
       shared tree, with the same working-copy + index preconditions as above for
       `tests/test_skill_parity_runtime_vs_rendered.sh` and the three new fixture files,
       and commit by name.
     - Confirm `bash tests/test_skill_parity_runtime_vs_rendered.sh` passes in the shared
       tree.
   - **Gate (existing verifier, before any new tooling exists):** `git clone` the commit
     that carries both prerequisites fresh into the scratchpad, provision the seed profiles
     the same way, and run the existing `aitask_skill_verify.sh`. It must report 0
     failures. Step 2's `release.yml` change is not made until this passes. The new `aitask_release_verify.sh`
     and manifest entry points are exercised later, on a clean clone, once they exist (see
     Verification).

1. **`.aitask-scripts/aitask_release_verify.sh [<checkout>]`** (new, default `.`): the clean
   release-input check.
   - Refuses unless `<checkout>` is a Git work tree (`git rev-parse
     --is-inside-work-tree`), since the wrapper parity check needs Git metadata.
   - Provisions `aitasks/metadata/profiles/*.yaml` from `seed/profiles/` **only when
     `aitasks` does not exist at all**. An existing `aitasks` (real data, or the data-branch
     symlink) means it refuses: this tool never writes into a working repository's data.
   - Runs `./.aitask-scripts/aitask_skill_verify.sh` unchanged, honouring `AIT_PYTHON`, and
     exits with its status.
   - With `--manifest <out>`, after a passing verify, runs `aitask_headless_manifest.sh`
     into `<out>`.

2. **Release workflow** (`.github/workflows/release.yml`, `release` job, before "Build
   skills directory", enabled only after the Step 0 gate passed):
   - `actions/setup-python@v5` (3.12), then `python -m pip install 'minijinja>=2.0,<3'
     pyyaml` (the spec from `AIT_PIP_SPECS_CPYTHON_EXTRA`).
   - `AIT_PYTHON=python ./.aitask-scripts/aitask_release_verify.sh . --manifest
     seed/headless_prerenders.txt` runs in the `actions/checkout` Git checkout. The
     provisioned `aitasks/` is not in the tarball's path list, and the verifier writes
     nothing, so packaging is unaffected.

3. **`aitask_headless_manifest.sh` and `lib/headless_prerenders.sh`.**
   - The lib (sourceable, no side effects) provides `ait_headless_prerender_dirs`, which
     prints the 12 committed dirs (9 existing + 3 `ait-git-remote-`), and
     `ait_headless_extra_files`, which prints `.agents/skills/codex_tool_mapping.md`.
   - The script prints the sorted union of `git ls-files -- <dirs>` and the extras, one
     `<sha256> <mode> <path>` line each, where `<mode>` is the index mode from `git
     ls-files -s` (`100644` / `100755`). A symlink (`120000`) or submodule entry is
     refused, because the release ships regular files only. Readers parse it with
     `read -r hash mode path`. The hash is computed with an
     `engine_sha256`-style stdin hash (sha256sum, else `shasum -a 256`, validated as 64
     hex).
   - It fails non-zero when an extra file is untracked, a dir has no tracked file, a
     listed path is dirty against `HEAD` (`git status --porcelain -- <paths>` is
     non-empty, so the hash would not describe the release), or a hash cannot be computed.

4. **Consumer-side helpers in `aitask_setup.sh`.**
   - `ait_manifest_changes <project_dir> <manifest> <strict|bootstrap>` prints
     `path<TAB>reason` for every path that is protected under that mode (the Design
     rules). Bootstrap adds the reasons `divergent` (an untracked file whose hash differs
     from the manifest) and `mode` (its executable bit differs from the manifest mode). It considers only the Codex paths, those under `.agents/skills/`.
     `.claude/skills/` keeps `install_skills`' existing behaviour, and `.opencode/skills/`
     payloads are only staged, so neither is classified or baselined by this step. Reasons: `modified`, `staged`, `deleted`, `untracked`,
     `ignored`, `not-a-file`, `linked-ancestor`, `non-dir-ancestor`, `unverified`.
     - The ancestor walk checks each component from the first below the project root to
       the file's parent with `[[ -L ]]` and `[[ -e && ! -d ]]`. It runs **first**, so a
       missing file under a linked skill dir is never classified "absent, clean".
     - `ignored` is detected with `git check-ignore -q`.
   - `_ait_prerender_negation_rules` is built from `ait_headless_prerender_dirs` and used by
     `setup_data_branch` Step 7's `skill_block` (aitask_setup.sh:2327) instead of literals.
   - `upgrade_prerender_gitignore_rules` is write-only and never fatal. It adds missing
     negations via `_ait_add_gitignore_rules` only when `_ait_gitignore_has_skill_block`
     finds the block.
   - `sync_codex_headless_prerenders <project_dir> <manifest> <protected>`:
     - For each unprotected manifest path under `.agents/skills/`, re-check its ancestors
       immediately before writing (time-of-check to time-of-use). Then copy from
       `aitasks/metadata/codex_skills/<rest>` when missing or different, creating missing
       parents with `mkdir` (never `-p` through a link: each created component is
       re-checked) and writing atomically via `lib/atomic_write.sh`.
     - **Resolve the framework-managed data root first, using the existing layout rules.**
       New `ait_resolve_data_root <project_dir>` prints the real data root `R`, or fails:
       - `aitasks` is a real directory (not a symlink) → legacy layout, `R=aitasks`;
       - `aitasks` is a symlink whose `readlink` is exactly `$(ait_data_link_target
         aitasks)` (`.aitask-data/aitasks`, lib/data_symlinks.sh: the same single form
         install.sh's `ensure_data_root` and `ait_link_worktree_data` accept) → branch
         mode. Resolve and verify the data dir `D` with the **existing identity checks**
         in `lib/data_symlinks.sh`, never with `--is-inside-work-tree`, which is true for
         any directory inside the primary repo:
         1. Topology from `ait_linked_worktree_roots <project_dir>`:
            - `1` (primary checkout) → `.aitask-data` must be a real directory, and
              `D = ait_canon_path(<project>/.aitask-data)`;
            - `0` (a task checkout linked by `aitask_init_data.sh --link-worktree`) →
              `.aitask-data` must be a symlink whose canonical target equals
              `ait_canon_path("$AIT_WT_MAIN_ROOT/.aitask-data")`. That is exactly
              `ait_link_worktree_data`'s preflight identity rule, factored out into a
              shared `ait_data_dir_for_checkout <dir>` that both now call, so the two
              cannot drift;
            - `2` (indeterminate) → fail.
         2. `D` must be **the primary's data worktree**, not an ordinary directory:
            - `ait_canon_path(git -C D rev-parse --show-toplevel) == D` (its own
              worktree root);
            - its canonical `--git-common-dir` equals the primary's (same repository);
            - `D != AIT_WT_MAIN_ROOT`;
            - its checked-out branch is `aitask-data`, the branch named in
              `AIT_DATA_BRANCH_SPEC` (lib/data_symlinks.sh:276). Add an
              `AIT_DATA_BRANCH_NAME` constant there and use it, rather than a new literal.
         3. `D/aitasks` must be a real directory. Then `R = D/aitasks`.
       - anything else (another link target, a dangling link, a `.aitask-data` symlink to
         a foreign or ordinary directory, a non-worktree, the wrong branch, an
         indeterminate topology) → fail. Then every Codex source is refused, reported once
         as `staging-unverified (data root: <which check>)`, and no destination is
         touched.

       The intended `aitasks` link is accepted by that rule, not by the no-link check;
       the no-link check applies only **beneath `R`** (`metadata/`, `codex_skills/`, its
       subdirs, the file). The manifest copy `aitasks/metadata/headless_prerenders.txt`
       that setup reads is resolved the same way.
     - **The source is verified before publishing.** The staging source must exist, be a
       regular file with no linked ancestor beneath `R`, and its SHA-256 must equal the
       manifest hash. Otherwise the path is not written, the destination stays
       byte-unchanged (mode too), and the path is reported as `staging-missing` /
       `staging-mismatch` / `staging-unverified`. Staging is a persistent, editable dir:
       a stale or locally edited copy must never reach a clean installed file or a
       commit.
     - Each written file gets the manifest mode (`chmod 755` / `644` on the temp file
       before the atomic `mv`).
     - No-op only when the manifest is absent (an older tarball or staging). A missing
       `.agents/skills/` is created, component by component, with the ancestor checks, so
       delivery never depends on Codex having been set up.
     - Prints the summary `Codex headless prerenders (CODEX_PRERENDERS): installed=N
       unchanged=M preserved=K`.
   - `report_preserved_headless_paths <protected>` prints one capped warning list,
     `<path> (<reason>)`, plus "left as is and not committed — review and commit it
     yourself".

5. **install.sh wiring.**
   - Before `snapshot_pre_install_dirty` (install.sh:1832), read the manifest from the
     tarball with `tar -xzOf "$tarball_path" seed/headless_prerenders.txt`. If it is
     missing (an older tarball), behave as today.
   - Classify with an install-local copy of the classifier and of the stdin hash (install.sh
     cannot source setup yet), marked `NOTE: duplicated in aitask_setup.sh
     ait_manifest_changes` like `_install_framework_paths`. The mode comes from
     `_install_version_tracked`:
     - `0` → strict;
     - `1` → bootstrap;
     - `2` → every manifest path protected (unverified).

     Store the result in `AIT_INSTALL_PROTECTED_HEADLESS` and union it into
     `AIT_INSTALL_DIRTY_BASELINE`, unless that baseline is unverified (the commit already
     refuses then). In bootstrap mode install.sh commits nothing anyway; the
     classification only decides what may be written.
   - `install_skills` is **not** changed (Codex-only scope).
   - New `install_seed_headless_manifest` stores the manifest in
     `aitasks/metadata/headless_prerenders.txt`.
   - The manifest read and the classification run on **every**
     install, fresh or existing: a fresh install into a repo with hidden local files must
     preserve them too.
   - With `declare -F` guards, after `upgrade_store_gitignore_rules` and before
     `commit_installed_files`:
     - `upgrade_prerender_gitignore_rules` for EXISTING_INSTALL only (a fresh project gets
       the whole block from setup);
     - then `sync_codex_headless_prerenders` and `report_preserved_headless_paths` on
       **every** install, fresh or existing.

     On a fresh install `commit_installed_files` commits nothing (VERSION is not tracked
     yet), so the delivered files sit in the working tree exactly like the fresh
     `.claude/skills/` prerenders, ready for the user's first commit or for setup's.
   - Rewrite the refresh call-site comment (1995-1999).

6. **Setup wiring.**
   - `snapshot_pre_setup_dirty` classifies against `aitasks/metadata/headless_prerenders.txt`
     when it exists. The classification runs **before** the bootstrap early return,
     right after the repo check, so bootstrap is never unprotected. Its mode comes from
     the same `_ait_framework_version_tracked` result (`0` strict, `1` bootstrap, `2`
     all-protected).
     - Store the result in `AIT_SETUP_PROTECTED_HEADLESS`, and union it into
       `AIT_SETUP_DIRTY_BASELINE` in every mode, unless that baseline is unverified.
     - In bootstrap the baseline is otherwise still empty, so the existing commit-all
       behaviour for the other framework paths is unchanged. Only protected manifest paths
       are excluded, and pristine installer output is committed by the first setup
       commit.
   - `setup_codex_cli`: its wrapper loop skips rendered dirs (`*-`). With a manifest, its
     `codex_tool_mapping.md` copy is removed because the sync owns it; without one, it
     keeps today's copy.
   - `setup_codex_agent` calls the sync after `setup_codex_cli` and before the refresh,
     whether or not the Codex CLI is found.
   - `main()`: `upgrade_prerender_gitignore_rules` goes immediately before
     `setup_data_gitignore_symlink_safe` (the t1711/t1959 rule), and
     `report_preserved_headless_paths` goes just before `commit_framework_files`.

7. **`refresh_codex_rendered_entries`** (aitask_setup.sh:4922). With the manifest present,
   both passes skip shipped `.agents/skills/<dir>` names, and pass 1 skips a render whose
   profile has shipped dirs (pass 2 then pointer-patches that entry only). Update the
   header comment.

8. **Tests**: new `tests/test_headless_prerender_delivery.sh` (self-contained, scratch
   `HOME`, `tests/lib/asserts.sh`).
   - **Fixture source.** The release input is a `git clone` of a fixture commit,
     provisioned by `aitask_release_verify.sh` and never `git archive`. The tarball is
     built like `tests/test_install_upgrade_dirty_baseline.sh` does, plus `codex_skills/`
     from tracked `.agents/skills/*/` and the mapping (as `release.yml` does), plus the
     generated manifest.
   - **RV1 release verify.**
     - A clone of `HEAD` passes, and the manifest is written.
     - A clone without git metadata (copied tree) is refused.
     - A checkout with an existing `aitasks` is refused, with nothing written.
     - Negative control: a clone whose commit drops `ait-git-remote-codex-/SKILL.md`
       fails with "(missing)", and no manifest is produced.
   - **M1 manifest.** It lists every remote closure target (from `walk_closure`), the
     mapping and the 3 `ait-git-remote-` files. It is sorted, all tracked, with no
     duplicates, each hash equals the SHA-256 of `git show HEAD:<path>`, and each mode
     equals its `git ls-files -s` mode. On a
     checkout with one listed path dirtied, the script refuses.
   - **C1 classifier.**
     - One fixture per reason: clean-tracked, clean-absent, modified, staged, deleted,
       untracked, ignored, symlinked file, directory-at-file, **missing file under a
       symlinked skill dir**, **symlinked `.agents/skills`**, and a regular file where a
       parent dir should be.
     - Both modes: each fixture is classified in strict and in bootstrap mode, and the
       bootstrap-only `divergent` / owned-pristine cases are included.
     - The install.sh copy agrees with `ait_manifest_changes` on every fixture in both
       modes, hash function included (parity).
   - **I0 fresh install delivers without setup.** Run a fresh `install.sh` into an empty
     repo, and assert immediately, with no setup and no renderer reachable (scratch `HOME`,
     no venv):
     - every delivered Codex manifest path (`.agents/skills/`, including
       `codex_tool_mapping.md`) exists, byte-equal to the release;
     - no `.codex/config.toml`, `.codex/instructions.md` or Codex hook was created
       (configuration stays opt-in);
     - `.opencode/skills/` was not written.

     Then make one plain user commit (`git add -A && git commit`) and `git clone` it:
     every delivered path is present in the clone.
   - **B1 bootstrap ownership: pristine output is committed.** After a fresh install (VERSION
     untracked), a full setup bootstrap snapshot (`snapshot_pre_setup_dirty`) protects
     none of the delivered paths. `commit_framework_files` then commits every delivered
     path, and the first setup commit holds them byte-equal to the release.
   - **B2 bootstrap ownership: divergent and staged changes are preserved.** After a fresh
     install, before setup:
     - (a) edit one delivered `.agents/` file (divergent);
     - (b) `git add` a delivered file *unchanged* (staged, equal bytes);
     - (c) add an untracked file under a manifest path that a user `.gitignore` rule
       ignores;
     - (d) replace a delivered skill dir with a symlink;
     - (e) `chmod +x` one delivered `100644` file with its bytes unchanged (mode-only).

     After setup's snapshot and commit, each one is unchanged on disk (bytes and mode) and
     in the index, absent from the first setup commit, and reported with its reason
     (`divergent`, `staged`, `ignored`, `linked-ancestor`, `mode`). For (e), `git ls-files
     -s` shows no `100755` entry for the path. Every other delivered path is committed.
   - **SV1 staged-source integrity.** In a clean, converged consumer:
     - (a) edit one file under `aitasks/metadata/codex_skills/`, and (b) delete another
       one there.
     - Run setup's sync, then `commit_framework_files`. Then run an upgrade whose staging
       copy of one file was tampered with between `install_codex_staging` and the sync,
       via a test hook in the fixture tarball's setup copy.
     - Each affected destination is byte- and mode-unchanged and absent from any commit.
       Each is reported `staging-mismatch` / `staging-missing`. Every other delivered path
       still converges.
   - **DB1 task-data branch mode.** Build a consumer with a real data branch: an
     `aitask-data` branch, a `.aitask-data` worktree and `aitasks -> .aitask-data/aitasks`,
     set up through the framework's own writer (`aitask_init_data.sh` /
     `ait_ensure_data_symlinks`, as `tests/test_install_upgrade_dirty_baseline.sh` and
     `tests/test_init_data.sh` build theirs).
     - Run a clean upgrade (`install.sh --force`). The staging and the manifest land on the
       data branch, and every verified `.agents/skills/` manifest
       path is delivered and **committed in the main repo's upgrade commit**, byte- and
       mode-equal to the release. Both trees are clean, and a repeat upgrade makes no
       commit.
     - Run the same with setup: the sync resolves `R=.aitask-data/aitasks` and converges.
     - **Positive: a linked task checkout.** `git worktree add aiwork/<t>` +
       `aitask_init_data.sh --link-worktree aiwork/<t>` (the framework's own linker),
       then setup's Codex part run **inside that checkout** (`setup_codex_agent`, the
       sync, `commit_framework_files` with `_is_agent_installed` stubbed). The resolver
       accepts the symlinked `.aitask-data` (`R` = the primary's
       `.aitask-data/aitasks`), and the verified `.agents/skills/` set is delivered and
       committed on the task branch.
     - Negative controls, each reporting `staging-unverified (data root: …)`, leaving every
       `.agents/skills/` destination byte-unchanged and committing nothing from it:
       - `aitasks` repointed to another directory;
       - a dangling `aitasks` target;
       - in the primary, `.aitask-data` replaced by a symlink;
       - in a linked checkout, `.aitask-data` symlinked to **an ordinary directory inside
         the primary repo** (carrying a fake `aitasks/metadata/codex_skills/`): rejected
         by the own-toplevel check, proving `--is-inside-work-tree` was not relied on;
       - in a linked checkout, `.aitask-data` symlinked to **another repository's** data
         worktree: rejected by the common-dir check;
       - a data worktree on a branch other than the data branch.
     - A symlink **beneath** `R` (`codex_skills/<dir>` → elsewhere) refuses only that dir's
       files.
   - **S1 strict baseline intact.** In a tracked project, an untracked manifest file whose
     bytes equal the release hash is still protected (`untracked`) by both install and
     setup. It is not written and not committed. There is no reconciliation outside
     bootstrap.
   - **I1 clean install converges.** A fresh `install.sh` is followed by setup's Codex part
     (`--source-only`, `snapshot_pre_setup_dirty`, `setup_codex_agent` with
     `_is_agent_installed` stubbed, `upgrade_prerender_gitignore_rules`,
     `commit_framework_files`).
     - Every *delivered* Codex manifest path (those under
       `.agents/skills/`) is in `HEAD`, byte-equal to the release, and the tree is clean.
     - Repeating setup makes no commit.
   - **U1 clean upgrade converges.** Start from a clean consumer, with Codex set up,
     committed at a pre-refresh state: stale tracked remote entries, closure and
     `ait-git-remote-*` absent, the old mapping, and the block without the new negations.
     Then run `install.sh --force`.
     - Every delivered manifest path is in `HEAD`, byte-equal to the release, and the tree
       is clean.
     - The consumer's `.opencode/skills/` is byte-unchanged; its payload only lands in
       staging.
     - A repeat upgrade makes no commit, a following setup makes no commit, and the bytes
       equal I1's.
   - **U1b upgrade of a project that never set up Codex.** Start from a clean consumer with
     no `.agents/` at all. After `install.sh --force`:
     - every delivered `.agents/skills/` manifest path is created and committed in the
       upgrade commit;
     - no Codex configuration appears;
     - a repeat upgrade makes no commit.
   - **U2 fresh clone.** Every delivered manifest path exists in a `git clone` of the
     upgraded fixture, with no renderer and no setup. All-agent completeness, `.opencode/`
     included, is covered by RV1 and M1 on the release input, not by the consumer tests.
   - **P1 preservation.** Each case below is byte-unchanged on disk, absent from
     `git show --stat` of the upgrade commit, and named with its reason:
     - a tracked edit;
     - ignored local renders of `ait-git-remote-codex-` and `ait-git-remote-` with
       differing bytes;
     - a symlinked `.agents/skills/task-workflow-remote-codex-` with a missing file
       beneath it: the link's target directory is byte-unchanged and contains no new
       file;
   - **R1 refresh scope.** A shipped dir with its pointer stripped is left byte-identical.
     The on-demand `aitask-pick-remote-codex-` entry gets the pointer, and
     `task-workflow-remote-codex-/` is unchanged.
   - **G1 gitignore.** The block gains exactly the missing negations and a second run adds
     nothing. A file with no block is untouched. The repo `.gitignore` agrees with
     `_ait_prerender_negation_rules` (parity).
   - **W1 wiring.**
     - In install.sh, the manifest read and the classification come before extraction.
     - The sync comes after sourcing and before `commit_installed_files`, and is not
       gated on `EXISTING_INSTALL`.
     - `release.yml` calls `aitask_release_verify.sh … --manifest` before "Create release
       tarball".
     - Adjust `R5` in `tests/test_codex_entrypoints_tool_mapping.sh` if the lines it greps
       move.

9. **Docs**: `aidocs/framework/skill_authoring_conventions.md:21-23`. Say that the release
   runs `aitask_release_verify.sh` (a clean Git checkout with the seed profiles), so a
   closure file that is rendered but not committed, or is stale, blocks the release, and
   that consumers receive exactly the `seed/headless_prerenders.txt` list. Name the local
   equivalent (`git clone` + the same script).

10. **Step 9 (Post-Implementation)**: current-branch workflow, so no merge. Archive via
    `aitask_archive.sh 2365`, which also deletes the folded t1154. Push via
    `./ait git push`.

### Post-phase (risk mitigations)

1. [adversarial_baseline_cases] Add three P1 cases, each asserting both the on-disk state
   and that the path is absent from the upgrade commit:
   - (a) a tracked manifest file the user deleted is **not** recreated and its deletion is
     not committed;
   - (b) the source path of a staged rename under a shipped dir is preserved;
   - (c) a destination that is a symlink or directory where a file ships is preserved and
     reported, never followed or replaced.

   All of these are Codex (`.agents/skills/`) paths.

## Verification

- `bash tests/test_headless_prerender_delivery.sh` passes.
- **Clean release input, locally**:
  1. Step 0's commit uses the *existing* verifier only (seed profiles provisioned by
     hand), as Step 0's gate describes.
  2. Once Steps 1-3 exist, before the Step 8 commit: build the would-be commit inside a
     scratch clone (overlay the change's files and commit them **in the clone only**).
     Then run `AIT_PYTHON=~/.aitask/venv/bin/python ./.aitask-scripts/aitask_release_verify.sh
     . --manifest <scratch>/m.txt` there. It must report 0 failures and write a manifest
     that equals M1's expectation.
  3. After the real commit: repeat step 2 on a fresh clone of the real commit.
- Pre-fix control: run U1 and P1 with the pre-change `install.sh` and `aitask_setup.sh`
  (`git show` copies in a scratch framework copy, via an `INSTALL_SH`-style override). U1
  must go red (dirty tree, incomplete set). P1's ignored-render and linked-dir cases must
  go red. Record the table in the plan notes.
- Regression: `tests/test_codex_entrypoints_tool_mapping.sh`,
  `tests/test_install_upgrade_dirty_baseline.sh`, `tests/test_release_tarball.sh`,
  `tests/test_skill_verify.sh`, `tests/test_skill_render_aitask_pickrem.sh`,
  `tests/test_skill_render_aitask_pickweb.sh`, `tests/test_setup_git.sh`,
  `tests/test_gitignore_data_symlinks.sh`, `tests/test_seed_manifest_drift.sh`.
- `shellcheck` on every new or changed shell file.

## Risk

### Code-health risk: medium
- The protection snapshot feeds the installer's and setup's dirty baselines for the Codex paths. A misclassified path (including through linked ancestors) would overwrite or commit a consumer's change · severity: medium (residual: bounded by inline post-phase adversarial_baseline_cases, the C1 ancestor fixtures and the write-time ancestor re-check) · → mitigation: inline post-phase adversarial_baseline_cases
- A data-root rule that is too strict would refuse every Codex source on a supported layout (branch mode), and one too loose would read staging through a foreign link · severity: medium (residual: the accepted forms are exactly the canonical `ait_data_link_target` layout, and DB1 covers the positive case plus three negative controls) · → mitigation: none
- The classifier exists twice (install.sh pre-extraction, setup), following the `_install_framework_paths` duplication pattern · severity: low · → mitigation: none (C1 parity)
- Refresh scope narrows; a stale on-demand remote variant keeps its body until its stub re-renders it · severity: low · → mitigation: none
- The release gains a Python + render dependency before packaging; a CI dependency hiccup blocks a release · severity: low · → mitigation: none (the spec is pinned to the setup spec; it fails loudly)

- The bootstrap ownership rule lets setup commit untracked files on hash equality; a wrong mode choice or hash check would sweep a local file into the first commit · severity: medium (residual: bounded by B1/B2/S1, mode taken from the committer's own VERSION probe, any failure → protected) · → mitigation: inline post-phase adversarial_baseline_cases

### Goal-achievement risk: low
- Always-deliver adds inert `.agents/skills/` files (and, on upgrade, commits them) in projects that never use Codex; a user may read that as unwanted · severity: low · → mitigation: none (explicit scope decision; config stays opt-in; reported in the upgrade summary line)
- An already-dirty checkout is preserved and reported, not converged (intended scope) · severity: low · → mitigation: none
- Step 0 lands files left uncommitted in the shared tree; a foreign hand edit among them would be overwritten or committed under this task · severity: low · → mitigation: none (rendering happens in a scratch clone of committed sources, and the shared tree is written only after its current bytes are proven to be HEAD's or the render's)

### Planned mitigations
- timing: post-phase | name: adversarial_baseline_cases | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — protection classifier / baseline feed | desc: Add deleted-file, staged-rename and symlink/dir-destination cases to the preservation tests
- timing: after | name: prune_retired_codex_staging | type: bug | priority: low | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — stale staging dirs (advisory: the exact manifest already stops them being installed) | desc: Make install_codex_staging mirror the tarball's rendered dirs so aitasks/metadata/codex_skills/ does not accumulate retired prerenders
