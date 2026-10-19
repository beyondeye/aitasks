---
Task: t1231/t1231_4_manual_verification_configurable_git_branch_artifact_backend.md
Parent Task: aitasks/t1231_configurable_git_branch_artifact_backend.md
Sibling Tasks: aitasks/t1231/t1231_*.md
Archived Sibling Plans: aiplans/archived/p1231/p1231_*_*.md
Base branch: main
---

# t1231_4 — gitbranch artifact backend, Artifacts settings tab and docs (autonomous)

Strategy: **autonomous**. 22 items: 21 `pass`, 1 `fail` (item 20 → follow-up
t2068). Nothing in this repository was mutated except the checklist, this
plan, and t2068.

## Fixtures

All backend and TUI work ran in throwaway projects under the session
scratchpad (`av1231_4/`), never in this repository:

- **A / B** — bare `remote.git` + two clones in **branch mode** (real orphan
  `aitask-data` branch checked out as `.aitask-data` worktree, `aitasks/` and
  `aiplans/` symlinks, a copy of `.aitask-scripts` + `ait`). Config:
  `artifacts: {default_backend: gitbranch, backends: {gitbranch: {branch: aitask-artifacts}}}`.
  Each clone ran with its own `XDG_CACHE_HOME`, so B could never hit A's
  resolver cache.
- **C** — same shape, no artifacts yet (needed so the R4 record guard does not
  pre-empt the OCCUPIED / reserved / unreachable paths).
- **D** — same shape, `project_config.yaml` with **no** `artifacts:` block plus
  unrelated nested keys and a comment; metadata copied from this repo so
  `ait settings` boots. The TUI ran in `tmux -L av1231` (isolated server),
  driven with `send-keys` and SGR mouse sequences
  (`\e[<0;X;YM` / `\e[<0;X;Ym`).
- **repocopy** — `git archive HEAD tests website/content .aitask-scripts seed ait`
  for the drift-guard red proof (item 21), so the shared dirty worktree was
  never edited.

## Execution Log

### Item 1
- Item text: Two-machine round trip (create on A, get on B).
- Approach: CLI, two clones.
- Action run: A `ait artifact create 5 payload.txt --kind report`; first B
  `get` → `no manifest for art:t5-report` (A's data commit was local, ahead 1 —
  by design: the blob branch is push-gated, the data branch follows the normal
  `ait git push` flow). A `ait git push`; B `ait git pull`; B `get --out`.
- Output (trimmed): `Wrote …/fromB.txt`; `cmp` identical, sha256 `0417529…`.
- Verdict: pass

### Item 2
- Approach: git inspection.
- Action run: `git log --stat aitask-artifacts`; `git log --name-status -1 aitask-data`;
  `git log --name-only aitask-data -- 'blobs/*' 'attachments/blobs/*'`.
- Output (trimmed): artifacts branch = one commit, `.ait-artifact-store` + `blobs/04/…`;
  data commit = `aitasks/t5_demo.md`, `artifacts/manifests/t5-report.json`,
  `artifacts/gitbranch_store.json` (R3 store record — part of the design, not a
  blob). Zero blob paths in data-branch history.
- Verdict: pass

### Item 3
- Action run: `git diff --cached --name-only` in main and `.aitask-data`; `git status --porcelain`.
- Output (trimmed): both indexes empty; only dirty path a fixture-copied `.pyc`.
- Verdict: pass

### Item 4
- Action run: `git worktree list`; `find` for `blobs/` / `.ait-artifact-store` in the tree.
- Output (trimmed): only main + the pre-existing `.aitask-data`; no blob files.
- Verdict: pass

### Item 5
- Action run: set `branch: aitask-artifacts-v2`; `get` with warm and cold caches.
- Output (trimmed): both exit 1 — `… store bfc32964… on branch 'aitask-artifacts' … migrate the store with: ait artifact gitbranch-migrate --from aitask-artifacts --to aitask-artifacts-v2`. No `ait artifact move`.
- Verdict: pass

### Item 6
- Action run: `ait artifact gitbranch-migrate --from aitask-artifacts --to aitask-artifacts-v2`;
  cold-cache `get`; tree/blob hash comparison of the old branch.
- Output (trimmed): `MIGRATED:bfc329643a0e43b32c27f06bafc85178:aitask-artifacts-v2`;
  `get` byte-identical; v2 marker carries the same `store_id`; record now names
  v2. Old branch: `blobs` tree and marker blob hashes **unchanged**; its only
  change is the designed retirement fence commit (`.ait-artifact-retired`,
  `retired_to: aitask-artifacts-v2`). The item's "old branch is untouched" is
  read as "old store content untouched" — the fence is the specified cutover
  (p1231_1 R2 `RETIRED`). Pointing config back at the old branch refuses the
  write (rename guard) and rolls back.
- Verdict: pass

### Item 7
- Action run (C): pushed `scratch-feature`; `branch: scratch-feature`; `create`, then `init-store gitbranch`.
- Output (trimmed): both exit 1 — `… already exists and is not an aitask artifact store … pick an unused branch name`; local and remote tips `8530f67` before = after; no `artifacts/` written.
- Verdict: pass

### Item 8
- Action run (C): `branch: main`; `create`.
- Output (trimmed): `must not be the reserved branch 'main' (reserved: main, master, aitask-data, aitask-locks, aitask-ids)` at activation; exit 1; main tip unchanged.
  (`artifact_registry.py default-backend` alone answers `gitbranch` rc 0 — it
  checks the default's name only; the branch rule fires in activation /
  `backend-env`.)
- Verdict: pass

### Item 9
- Action run (C): moved `C.git` away; `create --backend gitbranch`; moved it back.
- Output (trimmed): exit 1, `cannot reach origin to read branch 'aitask-artifacts' (and the repository exists.) — the remote is the store of record …`; rolled back; data HEAD unchanged, no manifest, no local store ref.
  Cosmetic: the parenthetical is a clipped tail of git's stderr.
- Verdict: pass

### Item 10
- Action run: the five suites, sequentially.
- Output (trimmed): 294/294, 152/152, 251/251, 98/98, 112/112; all exit 0.
- Verdict: pass

### Item 11
- Approach: TUI via tmux (D).
- Action run: `./ait settings`, `k`.
- Output (trimmed): `Artifact Storage` header, two hint lines, `default_backend: ◀ local | dir | gitbranch ▶`, `gitbranch branch: (not set)`, Save/Revert buttons, footer `a/b/c/g/k/m/p/s/t`.
  Cosmetic: the two long hint lines are clipped at the right edge (160 cols) rather than wrapped.
- Verdict: pass

### Item 12
- Action run: Shortcuts tab → filter → scope editor → rebind `switch_tab_artifacts` to `z` → save (`userconfig.yaml` gained `shortcuts.settings.switch_tab_artifacts: z`) → restart TUI.
- Output (trimmed): title `(Z) Artifacts`, hint `a/b/c/g/z/m/p/s/t`, `z` opens the tab, old `k` inert. (The editor states rebinds apply after restart.)
- Verdict: pass

### Item 13
- Output (trimmed): D has no `artifacts:` block; selector offers `local | dir | gitbranch`.
- Verdict: pass

### Item 14
- Action run: branch row → Enter → `bad..name`, `main`, `aitask-data` → Escape.
- Output (trimmed): each keeps the dialog open with an inline error (`is not a valid git branch name`, `must not be the reserved branch 'main'` / `'aitask-data'`); config sha256 unchanged, no commit.
  Cosmetic: long error lines clip at the dialog edge.
  Incidental finding before this item: an Enter that landed on the Save button with **no edits** still rewrote and committed `project_config.yaml` (comment dropped — documented, t1260 — and `yes` normalised to `true`). The baseline for this item was taken after that save.
- Verdict: pass

### Item 15
- Action run: click `default_backend`, Right ×2 (branch prefilled `aitask-artifacts`), click Save.
- Output (trimmed): toasts `ait: Update project_config.yaml`, `Artifact settings saved`; file gained `artifacts: {backends: {gitbranch: {branch: aitask-artifacts}}, default_backend: gitbranch}`; `artifact_registry.py --config … default-backend` → `gitbranch` rc 0; `backend-env gitbranch` → `ARTIFACT_GITBRANCH_BRANCH=aitask-artifacts`. `ait artifact create` in D then created the store.
- Verdict: pass

### Item 16
- Action run: SGR mouse clicks — tab label from the Agent tab, `default_backend` row, Save button, Revert button.
- Output (trimmed): tab switched (`Default Code Agents…` → `Artifact Storage`), row focused (arrows then cycled it), Save saved, Revert reverted.
- Verdict: pass

### Item 17
- Action run: cycle to `local`, click Revert.
- Output (trimmed): pane back to `gitbranch`, toast `Artifact settings reverted`, config sha256 unchanged, no commit. `unrelated_section.keep_me: 42` and `nested.also` survived both saves (comments dropped as documented; `yes` → `true`).
- Verdict: pass

### Item 18
- Approach: `hugo build` into scratch + HTML inspection + source reading (not `serve.sh`).
- Output (trimmed): sidebars — concepts `Attachments(55) › Artifacts(57) › Execution profiles(60)`, commands `Board, Browser & Stats(30) › Artifact(33) › Attach(34)`, both marked active; build exit 0 (no broken relref). Page claims match items 1–9.
  Docs gap noted: neither page says another clone cannot resolve a new artifact until the data-branch commit is pushed (what item 1 hit first).
- Verdict: pass

### Item 19
- Output (trimmed): `concepts/_index.md:22` relref → `/docs/concepts/artifacts/`; `commands/_index.md:83` relative `artifact/` and `../concepts/artifacts/`; all built targets exist; `check_links.py --build` → `SWEEP: PASSED`.
- Verdict: pass

### Item 20
- Approach: compare `reference.md` tables to `SettingsApp.BINDINGS` and the live TUI.
- Output (trimmed): Tabs table and Global table match (nine tabs incl. Shortcuts). **Within Tabs** omits Profiles `w`/`v`/`x` (+ `Tab` switch pane) — rendered live as `(W) Save  Re(V)ert  (X) Delete` and `w/v/x: save/revert/delete` — and Shortcuts `d`/`l` (only in `_index.md`).
- Verdict: fail → follow-up **t2068** (retyped documentation/low, with the observed gaps).

### Item 21
- Action run (repocopy): control → rc 0; delete the `| \`gitbranch\` |` row → `tests/test_website_doc_lists.sh` rc 1 (`FAIL: concepts/artifacts.md documents backend 'gitbranch'`); re-insert the same line at the same index (reversing the edit, no git) → `cmp` byte-identical → rc 0.
- Verdict: pass

### Item 22
- Action run: `cd website && hugo build --gc --minify --destination <scratch>/site`.
- Output (trimmed): exit 0.
- Verdict: pass

## Final Implementation Notes

- **Actual work done:** All 22 checklist items driven autonomously against
  throwaway branch-mode projects (bare remote + clones, isolated caches, an
  isolated tmux server for the settings TUI, a `git archive` copy for the
  drift-guard red proof). 21 pass, 1 fail.
- **Deviations from plan:** Items 18/22 rendered with `hugo build
  --destination <scratch>` instead of `serve.sh` / the default `public/`, and
  item 21 edited a HEAD copy instead of the shared worktree — same checks, no
  side effects on the shared tree.
- **Issues encountered:** Item 1's first `get` on clone B found no manifest
  until A ran `ait git push` — intended (blob branch push-gated, manifest rides
  the data branch), but undocumented on the artifact pages.
- **Upstream defects identified:** None that block. Follow-up t2068 (docs:
  settings reference Within Tabs table misses Profiles `w`/`v`/`x`/`Tab` and
  Shortcuts `d`/`l`).
- **Minor observations, no task created:** (a) the unreachable-origin error
  embeds a clipped git stderr fragment `(and the repository exists.)`;
  (b) long Artifacts-tab hint lines and the branch-dialog error clip instead of
  wrapping; (c) Save with no edits still rewrites + commits
  `project_config.yaml` (drops comments — t1260 — and normalises `yes`→`true`);
  (d) the docs could state that a new artifact is resolvable from another clone
  only after the data branch is pushed.
- **Notes for sibling tasks:** none remain (last child).

## Cleanup

- `tmux -L av1231 kill-server` (isolated server; the user's `ait` server is untouched).
- `rm -rf` the scratchpad `av1231_4/` directory (fixtures A/B/C/D, remotes, caches, repocopy, built site, logs).
