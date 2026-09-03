---
Task: t1703_manual_verification_metadata_writers_commit_own_files_follow.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1703 — manual-verification auto-execution record (t1677 metadata writers)

Autonomous strategy: every item was executed against **live TUIs and CLIs** in
throwaway branch-mode fixtures, never against this repo's own config and never
by re-running t1677's own tests (which would be the same artifact, not
independent ground truth).

## Fixtures

Two persistent scratch projects built from the shape of
`tests/lib/sync_fixture.sh::setup_repo` (bare remote + branch-mode clone with a
real `.aitask-data` worktree, `aitasks`/`aiplans` symlinks, the data-branch
`.gitignore`, a copy of `ait` / `.aitask-scripts/` / `seed/`):

- `…/scratchpad/auto_verify_1703/p1/local` — established project (seeded and
  committed metadata) — items 1-6, 8-11.
- `…/scratchpad/auto_verify_1703/p2/local` — project with **no**
  `board_config.json` and **no** `chatlink_config.yaml` — items 7 and 12.

TUIs were driven in tmux on a dedicated socket (`tmux -L av1703`, `$TMUX`
unset), using SGR mouse clicks for buttons and `send-keys` for text; screens
were read back with `capture-pane` (`-e` when a colour was the only way to read
selection/focus state).

## Execution Log

### Item 1 — settings project-layer save commits, worktree clean
- Approach: live TUI (`ait settings`), Project Config tab.
- Action: edited `verify_build` → `echo build-ok`, clicked **Save Project Config**.
- Output: toasts `ait: Update project_config.yaml` + `Project config saved`;
  commit `dc95ec0` contained only `aitasks/metadata/project_config.yaml`;
  `./ait git status --porcelain` empty.
- Verdict: pass

### Item 2 — board (user-layer) save commits nothing, claims nothing
- Approach: live TUI, Board tab.
- Action: auto-refresh 0 → 5, clicked **Save Board Settings**.
- Output: only toast `Board settings saved`; HEAD unchanged (`dc95ec0`);
  value landed in `board_config.local.json`; worktree clean.
- Verdict: pass

### Item 3 — new project profile committed; new user profile gitignored, not committed
- Approach: live TUI, Execution Profiles → `+ Add new profile`.
- Action: `projprof` (scope=project), then `userprof` (scope=user).
- Output: `projprof.yaml` → commit `b921189` (that file only), now in
  `./ait git ls-files`. `userprof.yaml` → written to `profiles/local/`, matched
  `.gitignore:11`, HEAD unchanged, worktree clean.
- Verdict: pass

### Item 4 — project-profile delete commits, UI drops it without reload
- Approach: live TUI, selected `projprof.yaml`, `X` → **Delete**.
- Output: commit `d1a6f6e`, 1 file / 4 deletions, only
  `profiles/projprof.yaml`; the `Profile:` selector no longer listed it in the
  very next capture, with no reload keystroke; worktree clean.
- Verdict: pass

### Item 5 — import partitions created vs overwritten-untracked
- Approach: live TUI, `i` Import, hand-built bundle
  (`newthing_config.json` new + `untracked_config.json` pre-existing and
  untracked), Overwrite existing = yes.
- Output: commit `e5aff71` contained **only** `newthing_config.json`; the
  overwritten file produced an error toast
  `Config saved but NOT committed (REFUSED:untracked:aitasks/metadata/untracked_config.json). Clear it with: …`
  — reported, not silently dropped.
- Verdict: pass

### Item 6 — every board column gesture commits `board_config.json`
- Approach: live TUI (`ait board`), `e` column manager (delete driven from the
  `^p` palette entry, which is the reachable route for it).
- Output: add `c2f457c`, rename `851748c`, reorder (shift+↑) `073ff47`, merge
  `b5a5e0e`, delete `4c1270a`. Every commit touched only
  `aitasks/metadata/board_config.json`; `./ait git status --porcelain` was
  empty after each gesture; diffs confirmed the intended mutation each time.
- Verdict: pass

### Item 7 — first-ship at board startup creates but does not commit
- Approach: fixture `p2` with no `board_config.json`; launched `ait board`.
- Output: file created (353 bytes), HEAD unchanged (`e5f03a1`), file listed as
  `?? aitasks/metadata/board_config.json`.
- Verdict: pass

### Item 8 — chatlink wizard summary states git position and names the commit
- Approach: drove `ait chatlink` → `w` through all 7 steps to a completed save.
- Output: summary showed `config: written` / `token: written`, then
  `committed: ait: Update chatlink_config.yaml` and
  `(the token file stays uncommitted/gitignored)`; commit `c433e4b` held only
  `chatlink_config.yaml`; worktree clean.
- Verdict: pass

### Item 9 — failing pre-commit hook: reported, edit survives, remedy works
- Approach: installed a `pre-commit` hook exiting 1 in the fixture's common git
  dir, then repeated a Settings save, a Settings **new profile** (the
  created-file case), a board **add column**, and a wizard save.
- Output — each reported it and kept the edit:
  - settings save → `Config saved but NOT committed (git commit failed for aitasks/metadata/project_config.yaml). Clear it with: .aitask-scripts/aitask_metadata_commit.sh aitasks/metadata/project_config.yaml`; `test_command: pytest -q` still on disk.
  - settings new profile → same shape, remedy carried **`--allow-new`**.
  - board add column → `Columns saved but NOT committed (git commit failed for aitasks/metadata/board_config.json)` + remedy; `hookcol` still in the file.
  - wizard save → `config saved but NOT committed (git commit failed for aitasks/metadata/chatlink_config.yaml)` + remedy.
  (A wizard save whose content matched HEAD correctly produced `NOCHANGE` and
  the pre-t1677 "review & commit when ready" fallback instead — the failure
  branch was reached by making the written content actually differ.)
- Hook removed, all four remedies pasted **verbatim** from the messages:
  each returned `COMMITTED:1:…` with exit 0, and the worktree went clean.
- Verdict: pass

### Item 10 — `ait sync` no longer reports a committed config as ownerless
- Approach: discriminating pair in fixture `p1`.
- Output: negative control — a hand-edited (ownerless) `board_config.json` made
  `ait sync` print
  `ownerless, NOT auto-committed: aitasks/metadata/board_config.json … Clear it with: ./.aitask-scripts/aitask_metadata_commit.sh …`.
  After a real `ait board` column save committed the same file (`8c4fa76`),
  `ait sync` printed only `Fetching / Pushing 1 commits / Sync complete`
  (exit 0) — no ownerless line, no deferral.
- Verdict: pass

### Item 11 — diffviewer history is per-user; tracked file never rewritten
- Approach: seeded `aiplans/p10_alpha.md`, `p20_beta.md` and a **tracked**
  legacy `diffviewer_history.json`; ran `ait diffviewer` and selected plans.
- Output: `Recent:` initially rendered from the legacy file (read-only
  fallback works); after navigation
  `aitasks/metadata/diffviewer_history.local.json` held the MRU list, while the
  tracked `diffviewer_history.json` was byte-identical (md5 `f2f149ae…`) with
  an unchanged mtime; `./ait git status --porcelain` empty.
- Verdict: pass

### Item 12 — `ait setup` commits only what it wrote
- Approach: fixture `p2`, `chatlink_config.yaml` absent, `board_config.json`
  tracked **and dirty** (a concurrent session's WIP). Ran the real `ait setup`.
- Output: `9b234c5 ait: Update chatlink_config.yaml and 5 more metadata files`
  (chatlink + crew_runner + 4 agent seeds) and `5ae7190` (project_config.yaml).
  `board_config.json` is in neither commit, stayed ` M` with `concurrent_wip`
  intact, and setup printed
  `Pre-existing uncommitted changes on the aitask-data branch — left alone (not committed by setup)`.
- Verdict: pass

## Observation (no defect claimed)

In `ColumnManageScreen`, the **Edit** and **Delete** buttons resolve their
target through `_focused_item()`, which requires the focused widget to still be
a `ColumnManageItem`; clicking the button moves focus to the button, so a
mouse-driven Edit/Delete is a no-op (keyboard `Enter` on the row, and the
`^p` palette's "Delete Column", both work). Unrelated to t1677's commit
behaviour — noted here only because it shaped how item 6 was driven.

## Cleanup

- tmux sessions `s1 s2 b1 b2 b3 b4 c1 c2 c3 d1` on socket `av1703` — killed;
  server left with no sessions.
- Scratch fixtures under
  `…/scratchpad/auto_verify_1703/` (`p1`, `p2`, `bundle.aitcfg.json`,
  `setup.log`) — session scratchpad, removed at the end of the run.
- The failing `pre-commit` hook existed only inside fixture `p1`'s git dir and
  was removed as part of item 9.
- This repository's own `aitasks/`, `aiplans/` and global install
  (`~/.local/bin/ait`, `~/.aitask/`) were left untouched.
