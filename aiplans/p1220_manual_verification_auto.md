---
Task: t1220_pickn_retirement_reference_sweep_verify.md
Base branch: main
Output branch: main
Working directory: /home/ddt/Work/aitasks
plan_verified: []
---

# t1220 — pickn retirement reference sweep (autonomous manual verification)

Auto-verification of the `manual_verification` checklist, run with
`strategy = "autonomous"` (whole checklist, Step 1.5). This file is the
retroactive record of what was actually executed.

## Fixture

The checklist requires "a real, already-installed project (not this framework
repo), installed BEFORE this change, that still carries the retired surfaces".

- `/home/ddt/Work/aitasks_go` — framework **0.27.0**, carrying all 8 retired
  paths from `retired_skills_manifest.txt`. `aitasks_mobile` is an equivalent
  second candidate (also 0.27.0, same 8 paths); `thinking_app` /
  `thinking_backend` are already 0.29.0 and were unusable as fixtures.
- Two **scratch copies** were used rather than the live project:
  `<scratch>/copy1` (clean upgrade) and `<scratch>/copy2` (preservation case,
  as the checklist's "second copy of the project" requires).
- The upgrade exercised is the **real** path: `ait upgrade` → resolve latest
  release (v0.29.0, the tag containing `0d9a3572b`) → download `install.sh`
  from GitHub → tarball install → `prune_retired_skills` → framework commit.

**Fabricated state (`ait`-generated closures did not exist).** Neither real
project had any `aitask-pickn-<profile>-` / `task-workflown-<profile>-`
rendered closure, so checklist items 5, 8 and 10 would have been vacuous. Three
realistic closures were created in both copies by copying the live
`aitask-pick-fast-` / `task-workflow-fast-` / `aitask-pick-fast-codex-` render
dirs:

- `.claude/skills/aitask-pickn-fast-`
- `.claude/skills/task-workflown-fast-`
- `.agents/skills/aitask-pickn-fast-codex-` (exercises the
  `<stem>-<profile>-<agent>-` form)

That absence is itself a finding: **in practice an upgraded project has no
pickn closures to leave behind** — see "Observations".

## Execution Log

### Item 1 — upgrade a pre-change installed project
- Approach: CLI invocation on a real-project copy.
- Action: `cp -a /home/ddt/Work/aitasks_go <scratch>/copy1` … `./ait upgrade`.
- Output: `0.27.0` → `0.29.0`; `Removed 8 retired skill path(s)`,
  `Kept 3 retired path(s)`; installer exit **0**.
- Verdict: **pass**

### Item 2 — `/aitask-pickn` gone from every agent's skill listing
- Approach: TUI interaction (detached tmux session per agent, driving `/`
  completion), not filesystem inspection.
- Actions / output:
  - **OpenCode 1.18.7** — `/aitask-pick` → `aitask-pick`, `aitask-pickweb`,
    `aitask-pickrem`; typing `/aitask-pickn` → **"No matching items"**.
  - **Claude Code 2.1.220** — `/aitask-pickn` matched no `aitask-pickn`
    command. (Before item 10 ran, the *fabricated* closure surfaced as
    `/aitask-pickn-fast`; after `--prune-rendered` the pickn family is absent
    entirely — re-checked and confirmed.)
  - **Codex CLI 0.144.6** — bare `/` lists only built-ins (`/model`, `/fast`,
    `/ide`, …); Codex exposes no aitask slash commands in this version, and its
    real discovery surface `.agents/skills/` no longer contains
    `aitask-pickn`.
- Verdict: **pass**

### Item 3 — `/aitask-pick` still resolves and renders in all three agents
- Approach: TUI interaction + CLI invocation.
- Actions / output:
  - Listed in Claude Code and OpenCode `/` completion; present at
    `.agents/skills/aitask-pick` for Codex.
  - `aitask_skill_resolve_profile.sh pick` → `fast`;
    `aitask_skill_render.sh aitask-pick --profile fast --agent {claude,codex,opencode}`
    → exit **0** each, producing `aitask-pick-fast-` /
    `aitask-pick-fast-codex-` / `.opencode/skills/aitask-pick-fast-`.
  - Negative control: rendering the retired stem fails —
    `skill_render: template not found: …/.claude/skills/aitask-pickn/SKILL.md.j2`
    (exit 1). The authoring template is genuinely gone, so the live render
    succeeding is not a false positive.
- Verdict: **pass**

### Item 4 — no authoring/wrapper dir left in any of the six roots
- Approach: file inspection over all roots in the manifest.
- Output: 8 paths PRUNED (`.claude/skills/aitask-pickn`,
  `.claude/skills/task-workflown`, `.agents/skills/aitask-pickn`,
  `.opencode/skills/aitask-pickn`, `.opencode/commands/aitask-pickn.md`,
  `aitasks/metadata/codex_skills/aitask-pickn`,
  `aitasks/metadata/opencode_skills/aitask-pickn`,
  `aitasks/metadata/opencode_commands/aitask-pickn.md`). Zero authoring or
  wrapper directories remain; the only surviving matches are the three
  rendered closures (trailing `-`).
- Verdict: **pass**

### Item 5 — rendered closures reported KEPT and still present
- Approach: parse installer output + file inspection.
- Output: all three closures reported
  `KEPT:<path>:rendered-closure-not-verifiable` and still on disk after the
  upgrade. An upgrade never deletes a closure.
- Verdict: **pass**

### Item 6 — deletions are in the upgrade's git commit
- Approach: git inspection on both branches (copy2 is authoritative here; see
  "Deviations").
- Output: `36f5777 ait: Update aitasks framework to v0.29.0` deletes 31
  pickn/workflown paths (copy1's equivalent `54f0901` deletes 33 — copy2 keeps
  the hand-edited wrapper by design); the `aitask-data` commit
  `9bd7a63` carries the staging deletions. Tracked pickn/workflown paths
  afterwards: **0** on `aitask-data`, and on `main` only the 2 deliberately
  preserved copy2 paths. Other checkouts therefore see the removal.
- Verdict: **pass**

### Item 7 — `ait settings` project tab has no `pickn` row, and saving does not resurrect it
- Approach: TUI interaction, then a headless drive of the real save path when
  synthetic key/mouse events would not activate the button.
- Output:
  - TUI (`./ait settings` → `c`): `default_profiles` renders
    `explore, fold, pick, pickrem, pickweb, pr-import, qa, revert, review` —
    **no `pickn` row**.
  - Headless (`SettingsApp.run_test()` against copy1's real config, the same
    harness pattern as `tests/test_settings_default_profiles_unknown_keys.py`):
    no `pickn` row rendered, `pickn` absent from `VALID_PROFILE_SKILLS`, and
    the app's own `save_project_settings()` left the map byte-identical with
    no `pickn` anywhere in the saved YAML.
- Verdict: **pass**

### Item 8 — preservation case (the important one)
- Approach: second copy, hand-edited before upgrading.
- Actions: appended a comment line to BOTH
  `.claude/skills/aitask-pickn/SKILL.md` (retired wrapper) and
  `.claude/skills/aitask-pickn-fast-/SKILL.md` (rendered closure); kept
  pre-upgrade copies; ran `./ait upgrade`.
- Output: upgrade exit **0**; `Removed 7` (not 8) — the edited wrapper was
  preserved as `KEPT:.claude/skills/aitask-pickn:unrecognized-content`; both
  files `diff`-identical to their pre-upgrade copies; the closing warning
  named all four kept paths with `rm -rf <path>` cleanup lines.
- Verdict: **pass**

### Item 9 — live neighbour check
- Approach: per-file `git hash-object` snapshots taken before and after.
- Output: `.claude/skills/aitask-pick/` and `.claude/skills/task-workflow/`
  present; no live neighbour appears in the PRUNED list; the *generated*
  render dirs (`aitask-pick-default-`, `aitask-pick-fast-`,
  `task-workflow-default-`, `task-workflow-fast-`,
  `aitask-pick-fast-codex-`, `task-workflow-fast-codex-`) are **byte-identical**
  pre/post. `task-workflow-remote-` changed — expected and benign: `remote`
  variants are git-tracked and shipped, and the change is purely additive
  (28 → 29 files, gaining `gate-cli.md`), with no file removed.
- Verdict: **pass**

### Item 10 — explicit `--prune-rendered`
- Approach: CLI invocation.
- Action: `./.aitask-scripts/aitask_prune_retired_skills.sh --prune-rendered`
- Output: exit 0, exactly three lines —
  `PRUNED:.claude/skills/aitask-pickn-fast-`,
  `PRUNED:.claude/skills/task-workflown-fast-`,
  `PRUNED:.agents/skills/aitask-pickn-fast-codex-`. All seven
  `aitask-pick-*-` / `task-workflow-*-` neighbours survive. The prefix-glob
  hazard (retiring a stem that prefixes a live skill) does not fire.
- Verdict: **pass**

## Observations

1. **No real project had a pickn closure.** Both 0.27.0 fixtures
   (`aitasks_go`, `aitasks_mobile`) had zero `aitask-pickn-<profile>-` /
   `task-workflown-<profile>-` directories. So a real upgrade leaves nothing
   pickn-discoverable at all, and the KEPT-closure path — while correct — is
   unlikely to be hit in the field for this particular retirement.
2. **A rendered closure is a discoverable slash command.** With the fabricated
   closure in place, Claude Code listed `/aitask-pickn-fast` after the upgrade.
   This is by design (upgrades never delete closures) and the KEPT warning
   gives the exact `rm -rf`, but it means "no discoverable pickn command" is
   only fully true once the user acts on the warning or runs
   `--prune-rendered`. Worth knowing for the next retirement of a stem that
   *does* have closures in the wild.
3. **Codex CLI has no slash surface for aitask skills**, so "check `/`
   completion in each" is not literally applicable there; `.agents/skills/`
   is the surface that matters and it was verified.

## Deviations

- **Scratch copies instead of the live projects.** The checklist says "take a
  project … and run `ait upgrade`". Upgrading the user's real `aitasks_go`
  would have been an unrequested mutation, so both runs used `cp -a` copies.
- **Fixture leak into the real repo, contained and repaired.** `cp -a`
  preserved `.git/worktrees/-aitask-data/gitdir` with an **absolute** path back
  to `/home/ddt/Work/aitasks_go`, so copy1's framework-data commit landed on
  (and was pushed to) the real project's `aitask-data` branch
  (`24052ec` → `331659c`). No file was deleted there. The syncer's next
  auto-commit (`2dde752`) restored the content — its tree is **byte-identical**
  to `24052ec` — and the local branch was fast-forwarded to match `origin`.
  End state: `aitasks_go` back at 0.27.0 with all 8 retired surfaces intact and
  a clean data worktree. copy2's worktree pointers were rewritten into the
  scratch dir before its run, and containment was re-verified afterwards.
  *Lesson for future fixtures: strip or re-point `.git/worktrees/*/gitdir`
  before running anything that commits inside a `cp -a` copy of an
  `ait`-managed project.*
- **Item 7 driven headlessly.** Neither `Tab`/`Enter` navigation nor synthetic
  SGR mouse clicks activated the "Save Project Config" button through tmux, so
  the save contract was verified through the app's own
  `save_project_settings()` under `run_test()` — the same real code path the
  button invokes.

## Cleanup

- tmux sessions `av_oc`, `av_cx`, `av_st`, `av_cc`, `av_cc2` — killed.
- Scratch tree `<scratchpad>/av1220/` (copy1, copy2, snapshots, logs) — removed.
- `/home/ddt/Work/aitasks_go` — restored (see Deviations); verified 0.27.0,
  8 retired surfaces present, data worktree clean and in sync with `origin`.
