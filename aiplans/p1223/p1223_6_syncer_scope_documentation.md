---
Task: t1223_6_syncer_scope_documentation.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_7_manual_verification_expand_syncer_scope_version_and_settings.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_1_tabbed_syncer_shell.md, aiplans/archived/p1223/p1223_2_framework_version_and_upgrade_command_model.md, aiplans/archived/p1223/p1223_3_version_tab_upgrade_action_and_handoff.md, aiplans/archived/p1223/p1223_4_cross_repo_settings_seam.md, aiplans/archived/p1223/p1223_5_settings_tab_and_push_action.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-28 19:16
---

# p1223_6 — Syncer scope documentation

> Verified against the as-built code on 2026-07-28. This plan replaces the
> pre-implementation draft; every claim below was checked at the cited line.
> Parent design: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.

## Context

`ait syncer` shipped as a git-desync TUI. Children t1223_1…t1223_5 turned it into
a three-tab cross-repo **sync console** — Branches, Versions, Settings — with a
repo-mutating upgrade action and a cross-repo settings push.
`website/content/docs/tuis/syncer/_index.md` still describes only the original
git view, so the two most consequential actions in the TUI are undocumented.

Documentation is a first-class deliverable here (`planning_conventions.md`), and
it lands **before** the manual-verification sibling t1223_7 so the verifier has
a documented contract to check against.

## Verification of the existing plan (what changed)

The draft plan's steps all still hold. Five things the as-built does that the
draft did not anticipate, and which the page must therefore cover:

1. **The refusal has a force override.** The draft said "refused, not warned".
   True by default — but `UpgradeRefusalScreen` offers a `Force…` button that
   leads to a *separate* destructive confirmation after a fresh re-probe
   (`syncer_app.py:1456-1485`, `upgrade_screens.py:305-410`). Hiding a
   destructive escape hatch would be worse than softening the message, so the
   page documents both: refusal is the default, force is a second, explicitly
   destructive step.
2. **Versions and Settings are not on the 60s poll.** They lazy-load on first
   activation of their tab and refresh only on `c` (`syncer_app.py:964-986`);
   Settings also self-reloads after a push (`:1994`). The current page's
   "refreshes automatically every 60 seconds" is Branches-only.
3. **A stale marker `*`** appears on the version cells, but the two columns have
   *different* conditions (`:199, 1306-1312`) — see the per-cell table below.
4. **Arrow-key tab navigation** (t1266): ←/→ switch tabs from anywhere, ↓ from
   the tab bar enters the list, ↑ on row 0 returns to the bar (`:990-1044`).
   There is no per-tab hotkey.
5. **Key assignments** are `U` upgrade, `c` re-check *and* reload, `p` push
   setting (shared with git-push, resolved per tab) (`:687-723`).

Everything else in the draft — the shared `Latest` resolution, `ait upgrade` +
`ait setup` in a spawned shell, the self-upgrade exit, "never reports success",
the layer prompt, masking, per-repo model rejection, the uncommitted-destination
note, the three-tier chain with no `seed` tier — is confirmed as-built.

## Files to change

| File | Change |
|---|---|
| `website/content/docs/tuis/syncer/_index.md` | The rewrite. Extend the existing section order; do not restructure. |
| `website/content/docs/tuis/_index.md` (line 23) | Syncer blurb still says "tracks remote desync state … pull, push, sync" — widen to the sync console. |
| `website/content/docs/commands/sync.md` (~line 106, "See also") | Blurb implies the syncer is git-only; add a clause naming the other two tabs. |

No other cross-reference needs changing: the remaining `syncer` hits in
`website/content/` are PyPy routing, TUI-classification lists, the switcher key,
brainstorm's unrelated "module syncer", and a dated blog post.

## Page plan

Keep the current section order (Purpose / Launching / Layout / Polling / Mouse /
Actions / Failure handling / switcher / autostart / Relationship / Configuration)
and insert two new sections after **Actions**.

**1. Intro + Purpose** — reframe around per-repo *state* (branch desync,
framework version, agreed settings) acting on the highlighted repo. Keep the
cross-repo framing from t1138.

**2. Layout** — three tabs. Document each tab's columns:
- Branches: Project? · Branch · Status · Ahead · Behind · Fetched/Last refresh (unchanged)
- Versions: Project · Installed · Latest · Status · State (`syncer_app.py:822-826`)
- Settings: `≠` · Operation · one column per repo (`:836-842`)

Add tab navigation: ←/→ anywhere, ↓ enters the list, ↑ on the first row leaves it.

**3. Polling** — say explicitly that the automatic tick drives **Branches only**;
Versions and Settings load on first visit and refresh on `c`.

**4. Framework versions** (new section)
- Installed read from each repo's `.aitask-scripts/VERSION`
  (`framework_version.py:43`); `Latest` resolved **once per refresh** and shared
  across every row (`syncer_app.py:1233-1239`).
- Status cell values: `up_to_date` / `behind` / `ahead` / `unknown`
  (`framework_version.py:128`).
- **The `*` stale marker, per cell** — document the two columns separately;
  they do not share a condition (`syncer_app.py:1306-1312`):

  | Cell | `*` appears when | Never marked by |
  |---|---|---|
  | **Installed** | that repo's upgrade is in flight — the value shown is the last one actually *read*, never the version requested | fetch being off |
  | **Latest** | the shared value was not confirmed by the most recent refresh — fetch is off (`f`, no network call at all) or the lookup failed — or that row's upgrade is in flight | — |

  `—` means never resolved. A failed lookup keeps the last known value and marks
  it; the failure *reason* is not surfaced in the table, so do not imply it is.
- **Upgrade (`U`)** — uppercase on purpose. Choose `latest release` or a pinned
  `X.Y[.Z]`. For another repo the syncer opens a new tmux window named
  `upgrade-<project>`, rooted in that repo, running
  `./ait upgrade <version> && ./ait setup` (`framework_version.py:203-221`,
  `syncer_app.py:1497-1543`). Explain *why* a shell: neither command takes a
  target-directory flag, which is also why `ait setup` can still prompt there.
- **Refusal on an active target** — the action is *refused*, not warned, when the
  target's tmux session holds a framework TUI window or an `agent-` / `create-` /
  `brainstorm-` companion window; the dialog names the windows to close. A
  `Force…` button re-probes and, if still busy, raises a separate destructive
  confirmation — that is the only path that launches anyway.
- **What is actually inspected — four cases, documented separately.** The check
  is not uniform across targets, and a reader must not assume every upgrade was
  gated by a fail-closed inspection (`syncer_app.py:1371-1389`,
  `framework_version.py:162-200`):

  | Target | What happens | Outcome |
  |---|---|---|
  | Repo with a **live tmux session**, no framework windows found | session's windows enumerated and classified | proceeds to confirmation |
  | Repo with a live session holding framework/companion windows | classified `busy` | **refused**, names the windows |
  | Repo with a live session whose window enumeration or TUI-name classifier fails | reported `unknown` | **refused** — fail-closed |
  | Repo known only from the **cross-repo registry** (`~/.config/aitasks/projects.yaml`, no live session) | short-circuits: **no enumeration, no classification is performed at all** | proceeds to confirmation |

  Say the last row plainly. The syncer then creates that repo's configured tmux
  session to run the upgrade in. "Fail-closed" is a property of the live-session
  path only.
- **Declared bound** — even on the live-session path, detection sees only the
  windows of the *target's own tmux session*. An `ait` command in an unrelated
  terminal, a detached process, or another machine sharing the checkout is
  invisible. State it plainly; do not imply coverage the code lacks.
- **Self-upgrade** — upgrading the repo the syncer runs from is never
  force-gated. It shows what is live as an *advisory*, then on confirm the
  syncer **exits** and its launcher runs the upgrade in the vacated window
  (`aitask_syncer.sh:23-109`). Explain why: the upgrade replaces the very
  framework files the running TUI shells out to. Requires having been launched
  via `ait syncer`.
- **Result reporting** — State reads `upgrading…` while the pane is alive and
  `re-check needed` once it is gone; there is deliberately no "succeeded" state
  (`syncer_app.py:190-196, 507-513`). Press `c` to read the new version.
- If tmux is unavailable, the cross-repo spawn is refused with a message to run
  `ait upgrade` in that repo from a shell.

**5. Cross-repo settings** (new section)
- v1 syncs **the default code agent per operation** — say that this is currently
  the only synced setting. Rows are the union of every repo's `defaults` keys
  across both config layers, minus `*-launch-mode` keys
  (`cross_repo_settings.py:239-305`).
- Cell rendering: bare value = project layer, `value (local)`, `value (default)`
  for the built-in, `conflict` when the layers and the resolver disagree,
  `unavailable` when a repo's config could not be read (`syncer_app.py:332-348`).
  `≠` marks a divergent row, computed over readable repos only.
- **Resolution model — separate the stored tiers from the invocation override.**
  Do not present them as one flat chain; the distinction is what makes the
  provenance markers mean anything (`aitask_codeagent.sh:48-85`):
  - **Stored tiers, highest first** — `codeagent_config.local.json` (per-user,
    gitignored) → `codeagent_config.json` (per-project, git-tracked) → the
    built-in default. These three are what the matrix reports, and they are the
    only persistent state; the `(local)` / bare / `(default)` markers name which
    one answered.
  - **`--agent-string` is a per-invocation override on `ait codeagent`**, not a
    layer: it wins for that single call, is written nowhere, and changes nothing
    a later command or another repo sees.
  - Confirmed: it **cannot** influence the matrix. `ait syncer` accepts no such
    flag (only `--interval` / `--no-fetch`, `syncer_app.py:2358-2380`), and the
    matrix read resolves each repo with `OPT_AGENT_STRING`,
    `DEFAULT_AGENT_STRING`, `METADATA_DIR` and `TASK_DIR` scrubbed from the
    environment (`cross_repo_settings.py:48-53, 124-132`), so an override
    exported in the launching shell cannot leak into what is displayed or pushed.
  - **`seed/` is not a tier either** — it is a setup-time copy source `ait setup`
    copies into `aitasks/metadata/`; an installed project has none at its root,
    and there is no `(seed)` marker.
- **Push (`p`, multi-repo only)** — the key is absent with a single repo. Flow:
  pick a source (only repos holding a usable value; `conflict` / `unavailable`
  are excluded) → pick destinations (every other repo, *including* conflicted
  ones) → **choose the layer**. The layer prompt is always asked and has **no
  default**: project = git-tracked and shared with that repo's team, local =
  gitignored and personal to that checkout.
- **Masking** — because local wins, a project write into a repo whose local layer
  sets that operation would have no effect. Document the three offered choices
  and what each leaves on disk: *Skip* (nothing written), *Write local* (its
  local layer set instead), *Clear + project* (local override removed, project
  written). Note the write order is project-first-then-clear, so a failed clear
  leaves the effective value unchanged and a retry converges.
- **Rejection** — a value whose model is absent from the destination's
  `models_<agent>.json` is refused with a reason; models are per-repo.
- **Not committed** — the push writes files but commits nothing. On a destination
  using a separate `aitask-data` branch, `aitasks/metadata/` is a symlink into
  `.aitask-data/` (gitignored in the main checkout, tracked on the data branch),
  so `git diff` there shows nothing — say so, or users will think it did not
  land. Point at `ait git` in the destination.

**6. Keys table** — one row per key with its tab scope, plus a note that Branches
keys (`s`/`u`/`p`/`r`/`f`/`a`) are inert on the other tabs and that `q`, `j` and
`?` work everywhere. Keep the existing "every shortcut can be rebound / press
`?`" note.

**7. Extending the synced set** — short subsection: the operation rows are
data-derived from each repo's `codeagent_config.json`, so there is no list to
edit; syncing a *different* setting means extending
`.aitask-scripts/lib/cross_repo_settings.py` (`read`/`diff`/`plan_push`/
`apply_push`). Keeps the next person from re-deriving it.

**8. Mouse support** — extend to cover clicking a tab and rows in the new tables.

## Style constraints

- Current-state-only: no version history or "now also supports…" prose
  (`documentation_conventions.md`).
- `ait upgrade` = move to a newer version; `ait setup` = reinstall/repair
  (CLAUDE.md). Both appear on this page and must be used per those semantics.
- No specific coding agent named where generic phrasing works.
- Every `{{< relref >}}` must resolve — the Hugo build fails on a broken one.

## Verification

```bash
cd website && hugo build --gc --minify          # node_modules already present
grep -rn "syncer" website/content/ | grep -v "tuis/syncer"   # no stale cross-refs
```

Manual checklist:
- No version-history prose in the body.
- `ait upgrade` vs `ait setup` used per CLAUDE.md.
- All five otherwise-misunderstood behaviors documented: the active-target
  refusal (with its force override), the declared detection bound, the
  self-upgrade exit, the "result unknown" reporting, and the layer prompt with
  masking.
- **No over-claimed safety.** The page must not read as though every upgrade is
  gated by a fail-closed inspection: the registry-only case (no inspection at
  all) is stated as its own row, `*` is described per column, and
  `--agent-string` is named as an invocation override rather than a stored tier.
- Every key, column value and file path cited was checked against the as-built
  code, not the parent plan.

## Out of scope

Behavior changes. If a claim cannot be substantiated in the code, the **code** is
the source of truth — file the discrepancy for t1223_7 rather than quietly
editing the page to match.

## Risk

### Code-health risk: low
- Documentation-only change to three markdown files; no runtime code path is
  touched and the Hugo build is a hard gate on broken cross-references. · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- The page asserts safety behavior a reader will act on. The specific hazard is
  **over-claiming**: summarising the activity gate as uniformly fail-closed hides
  that a registry-only target is never inspected, and flattening `--agent-string`
  into the stored tiers teaches a wrong persistence model. Both are corrected
  above with per-case tables; every claim is pinned to a cited line and t1223_7
  re-verifies against the live TUI. · severity: medium · → mitigation: TBD
- The as-built diverges from the draft plan in five places (§"Verification of the
  existing plan"); a rewrite following the draft alone would have documented a
  refusal with no escape hatch and a poll cadence that does not apply to two of
  the three tabs. · severity: medium · → mitigation: TBD
