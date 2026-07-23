---
priority: medium
effort: medium
depends: [t1223_5]
issue_type: documentation
status: Ready
labels: [web_site, tui]
gates: [risk_evaluated]
anchor: 1223
created_at: 2026-07-23 18:33
updated_at: 2026-07-23 18:33
---

## Context

Sixth child of t1223. Documentation is a **first-class deliverable** for this
feature, not a verification afterthought (`aidocs/framework/planning_conventions.md`
§"User-facing features: docs are a plan deliverable"). It lands **before** the
manual-verification sibling so the verifier has the documented behavior to check
against.

The syncer stops being "the git desync TUI" and becomes a cross-repo sync console
with three tabs, a repo-mutating upgrade action, and a cross-repo settings push.
Several behaviors are non-obvious and MUST be documented because users will
otherwise assume the wrong thing:

- an upgrade is **refused** when the target repo has live framework processes;
- upgrading the syncer's **own** repo exits the TUI first;
- the version row reports **launched / result unknown**, never success;
- a settings push asks which **layer** to write and can be **masked** by a local
  override;
- activity detection has a **declared bound** — it cannot see `ait` running
  outside the target's tmux session.

Parent plan: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`
(the `## Safety contracts` section is the source of truth for the behavior being
documented — read it, and read the **as-built** code, not the plan alone, since
siblings may have adjusted details).

## Key files to modify

- `website/content/docs/tuis/syncer/_index.md` — the main rewrite.
- `website/content/docs/tuis/_index.md` — update the syncer blurb if its
  one-line description no longer matches.
- `website/content/docs/commands/sync.md` — the "Relationship to `ait sync`"
  framing still holds, but check that nothing there implies the syncer is
  git-only.
- Check for other stale cross-refs:
  `grep -rn "syncer" website/content/ | grep -v tuis/syncer`

## Reference files for patterns

- `website/content/docs/tuis/syncer/_index.md` — the existing page; keep its
  structure (Purpose / Launching / Layout / Polling / Mouse / Actions / Failure
  handling / switcher / autostart / Relationship / Configuration) and extend it
  rather than restructuring.
- `website/content/docs/tuis/settings/` — the in-repo precedent for documenting a
  **tabbed** TUI; mirror how tabs are presented.
- `aidocs/framework/documentation_conventions.md` — **required reading**:
  current-state-only (no version history in doc bodies), no naming of specific
  coding agents where a generic phrasing works, "delete X / integrate into Y
  means redirect cross-refs now".
- CLAUDE.md — `ait setup` vs `ait upgrade` verb semantics; this page will mention
  both and must use each correctly.

## Implementation plan

1. **Reframe the intro and Purpose.** The syncer surfaces per-repo *state* —
   branch desync, framework version, agreed settings — and acts on the
   highlighted repo. Keep the existing cross-repo framing from t1138.

2. **Layout section: three tabs.** Branches (unchanged content, now a tab),
   Versions, Settings. Document each tab's columns.

3. **New "Framework versions" section.**
   - Columns: Project · Installed · Latest · Status · State.
   - `Latest` is resolved once per refresh and shared across repos; with fetch
     off (`f`) no network call is made and the value is marked stale.
   - **Upgrade action**: choose `latest` or a pinned version; the syncer runs
     that repo's own `ait upgrade` followed by `ait setup` in a spawned shell
     rooted in the target repo (they have no `--dir` flag, which is why a shell
     in the repo is used — and why `ait setup` can still prompt you there).
   - **Refusal on an active target** — state plainly that the action is refused,
     not warned, when the target repo has a framework TUI or agent pane running,
     and that the message names the windows to close.
   - **Declared bound** — say explicitly that detection covers the target's tmux
     session only, and cannot see an `ait` command in an unrelated terminal, a
     detached process, or another machine sharing the checkout. Do not imply
     coverage the code does not have.
   - **Self-upgrade** — upgrading the repo the syncer is running from **exits the
     TUI first**, then runs the upgrade in the vacated window. Explain why (the
     upgrade replaces the framework files the running TUI shells out to).
   - **Result reporting** — the State column reads `upgrading…` while the pane
     is alive and `re-check needed` once it is gone. The syncer **never reports
     success it did not observe**; use the re-check key to read the new version.

4. **New "Cross-repo settings" section.**
   - What v1 covers: the **default code agent per operation**. Say that this is
     currently the only synced setting.
   - The matrix: one row per operation, one column per repo, showing the
     **effective** value plus a provenance marker (`(local)` / bare project /
     `(seed)` / `(default)` / `conflict`); divergent rows are highlighted.
   - Push flow: choose a source value → select destinations → **choose the layer**
     (project = git-tracked and shared with that repo's team; local = gitignored
     and personal). Say that the prompt is always asked.
   - **Masking**: because the local layer wins, a project-layer write into a repo
     whose local layer sets that operation would have no effect. Document the
     three choices offered (cancel / write local instead / clear the local
     override and write project) and what each leaves on disk.
   - **Rejection**: a value whose model is not in the destination's
     `models_<agent>.json` is refused with a reason — models are per-repo.
   - Note that a project-layer push leaves an **uncommitted change in the
     destination repo** that the user must commit there.

5. **Keys table.** Add the new keys (upgrade, re-check, push) with their tab
   scope, and state that Branches keys (`s`/`u`/`p`/`r`/`f`) are inert on the
   other tabs. Keep the existing "every shortcut can be rebound / press `?`" note.

6. **"Adding another synced setting"** — a short subsection (or an `aidocs/`
   note linked from here) describing where the setting list lives so the next
   person does not have to re-derive it. Point at the as-built module.

7. **Verify every claim against the as-built code**, not against this task file.
   Run the greps/commands you cite before publishing them
   (`aidocs/framework/planning_conventions.md` and the framework's
   "test verification commands before relying on them" rule).

## Verification steps

```bash
cd website && npm install && hugo build --gc --minify   # must succeed
grep -rn "syncer" website/content/ | grep -v "tuis/syncer"   # no stale cross-refs
```

Manual review checklist:
- Every `{{< relref >}}` resolves (the Hugo build fails on a broken one).
- No version history / changelog prose in the body (current-state-only rule).
- `ait upgrade` vs `ait setup` used per CLAUDE.md verb semantics.
- The refusal, the self-upgrade exit, the "result unknown" reporting, the layer
  prompt, masking, and the declared detection bound are each documented — these
  are the five things a user would otherwise get wrong.
- No specific coding agent is named where generic phrasing works.

## Notes for sibling tasks

- t1223_7 verifies the documented behavior; if verification finds the docs
  describe something the code does not do, the **code** is the source of truth —
  file the discrepancy rather than quietly editing the page.
