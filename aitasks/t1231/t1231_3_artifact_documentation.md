---
priority: medium
effort: medium
depends: [t1231_2]
issue_type: documentation
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-07-26 22:58
updated_at: 2026-07-26 22:58
---

Write the **baseline user-facing documentation for the artifact feature** — which
currently has **none** — and document the `gitbranch` backend (t1231_1) and the
Artifacts settings tab (t1231_2).

**Full design + rationale: `aiplans/archived/p1231_configurable_git_branch_artifact_backend.md`
(parent plan, §t1231_3).**

## Context — the gap, verified

`grep -rn "ait artifact\|ait attach" website/content/docs/` returns **zero real
hits**. The only match is `installation/terminal-setup.md:78,108`, which is
`tmux -L ait attach -t aitasks` (a tmux socket name, unrelated).

There is no `commands/artifact.md`, no `concepts/artifacts.md`, and
`commands/_index.md` does not list `ait artifact` or `ait attach` in any of its
tables — even though `.aitask-scripts/aitask_artifact.sh` (687 lines) and
`aitask_attach.sh` (636 lines) have shipped, with two backends already present.
The only mentions anywhere are two blog posts (`blog/v0280-…`, `blog/v0270-…`).

## Key files to modify

### New pages

- **`website/content/docs/concepts/artifacts.md`** — the concept: the stable
  `art:<id>` handle → manifest (`current` / `versions` / `backend`) → backend
  chain; the hash-first invariant (a backend swap never rewrites a task file);
  the universal local cache (`~/.cache/ait/artifacts/<hash>`); and the backend
  table (`local`, `dir`, `gitbranch`) with when to pick each.

  **Must state the `gitbranch` operating rules a user can trip over:** a
  reachable remote is required for writes (publish is push-gated), the branch
  must be one the store owns — an existing ordinary branch is refused — and a
  branch rename needs `ait artifact gitbranch-migrate`, **not**
  `ait artifact move`.

  Frontmatter shape from `concepts/git-branching-model.md:1-7`:
  `title` / `linkTitle` / `weight` / `description` / `depth: [advanced]`.

- **`website/content/docs/commands/artifact.md`** — verb reference for
  `create` / `update` / `move` / `rm` / `ls` / `get` / `versions` /
  `gitbranch-migrate`, plus the `artifacts:` config block and a pointer to the
  settings tab. Frontmatter shape from `commands/lock.md:1-7`
  (`weight` in the 30s, `depth: [intermediate]`).

### Hand-maintained lists (all manual — nothing derives them)

- `website/content/docs/commands/_index.md` — a row in the category table (Tools
  section) **and** an entry in the `## Usage Examples` fenced bash block. This
  section uses **relative** links (`sync/`, `lock/`).
- `website/content/docs/concepts/_index.md` — a bullet under **Data model**.
  This section uses the `{{< relref "/docs/concepts/..." >}}` **shortcode** form.
  Match the section you are editing; the two differ.
- `website/content/docs/concepts/git-branching-model.md:13-18` — add the
  `aitask-artifacts` row to the branch table (`main` / `aitask-data` /
  `aitask-locks` / `aitask-ids`), marked **optional**.

### Settings docs — fix the pre-existing staleness in the same pass

- `website/content/docs/tuis/settings/reference.md`:
  - L14-26 global keyboard-shortcut table,
  - L54-62 the `## Tabs` table (Tab | Shortcut | Editable | Description),
  - L75-88 the `## Configuration Files` table.

  **All three are already stale** — they omit the shipped Shortcuts tab and its
  `s` key. Fix that while adding the Artifacts row, rather than appending a ninth
  row to a table that is already wrong.
- `website/content/docs/tuis/settings/how-to.md:15` — the mouse-support line
  hardcodes `a / b / c / t / m / p`.

### Non-website

- `seed/project_config.yaml:189-225` — the `artifacts:` block is present but
  fully commented; extend it with the `gitbranch` example. **The live
  `aitasks/metadata/project_config.yaml` has no `artifacts:` section and stays
  that way** — `local` remains the default for this repo.
- `aidocs/unified_artifact_design.md` §5 / §6 — register `gitbranch` in the
  backend narrative so the design doc does not go stale against the code.

## Drift guard (the part that stops this gap reopening)

Extend `tests/test_website_doc_lists.sh` — the **only** website drift test — with
a third check, in the style of its existing Tests 1 and 2 (containment
assertions, extra doc rows allowed, plus a tripwire so the grep cannot vacuously
pass):

- parse every `ARTIFACT_BACKEND` `case` arm out of
  `.aitask-scripts/lib/artifact_backend.sh` (the dispatcher at L44-50);
- assert each backend name appears as a literal table cell
  (`| \`<name>\` |`) in `website/content/docs/concepts/artifacts.md`;
- tripwire: assert the parsed arm count is `> 0`.

This is what stops t1089 (`s3`) and t1090 (`gdrive`) from silently re-opening the
documentation gap when they land.

## Reference files for patterns

- `website/content/docs/concepts/git-branching-model.md` — frontmatter + the
  branch table to extend; the closest tonal match for the concept page.
- `website/content/docs/commands/lock.md` and `commands/sync.md` — command-page
  frontmatter and structure.
- `tests/test_website_doc_lists.sh` (from t1162_5) — the guard style: sources
  `tests/lib/asserts.sh`, `assert_contains` on literal table cells, tripwires.
- `aidocs/framework/documentation_conventions.md` — **mandatory.**
  Current-state-only (no version history in doc bodies), genericize any passage
  that names the supported coding agents.
- `aidocs/unified_artifact_design.md` §4b, §5, §6, §7 — the authoritative source
  for the concept page's content.

## Verification steps

- `cd website && hugo build --gc --minify` — succeeds with no broken `relref`.
- `bash tests/test_website_doc_lists.sh` — passes with the new third check;
  confirm it **fails** if the `gitbranch` row is removed from
  `concepts/artifacts.md` (prove the guard bites).
- `grep -rn "ait artifact" website/content/docs/` now returns the new pages plus
  the `_index.md` rows.
- Read the rendered pages in `./serve.sh` and confirm the sidebar placement and
  weights put them where a reader would look.

## Out of scope

Documenting `ait attach` beyond a cross-reference — attachments remain
local-only in this cycle and their own doc page is not required here.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1687** id=2026-09-10T18:36:24Z.8e3fd156668b59f583ee94b3 from=t1687 at=2026-09-10T18:36:24Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the overlapping
> | task, not an agent working on it, so it is unverified. Advisory only —
> | tree-relative claims are dated by this note's base SHA; `~` line numbers are
> | approximate. Verify before acting.
> | 
> | 1. PAGE COLLISION WITH t1687 (Concepts gap sweep). Its gap table lists
> |    Artifacts and Attachments concept pages, and its scope step 5 owns the
> |    decision on `ait artifact` / `ait attach` command pages (a t1707 note in its
> |    inbox confirms that). Both tasks would create concepts/artifacts.md and
> |    commands/artifact.md and edit the same concepts/_index.md and
> |    commands/_index.md sections. As of this sweep (moment-relative) t1687 is
> |    `Implementing` with no plan or content commits. A matching note went to
> |    t1687; no owner has been decided. Two workable splits: t1687 writes base
> |    pages for local/dir (each backend name in its own literal table cell so your
> |    drift guard still fits) and you add gitbranch; or t1687 hands artifacts to
> |    you outright.
> | 
> | 2. STALE CLAIMS IN THE BODY:
> |    - "Zero real `ait artifact` / `ait attach` hits on the site" is no longer
> |      true: skills/aitask-trail.md:85 and development/task-format.md ~59-60 and
> |      ~98-99 mention them, unlinked since t1707 removed two dead-end links. Those
> |      are the call sites to link back from once commands/artifact.md exists.
> |    - t1698 (7e533f422) changed transaction behaviour: the artifact command now
> |      refuses when a non-blob path it will stage is already dirty
> |      (aitask_artifact.sh ~84) and rolls back from a snapshot. The command page
> |      should document that.
> |    - Script sizes are now 813 / 755 lines; the seed `artifacts:` block is at
> |      seed/project_config.yaml ~313-349; the parent plan is
> |      aiplans/p1231_configurable_git_branch_artifact_backend.md (not archived).
> |    - Sibling t1231_2's settings-binding references moved to settings_app.py
> |      ~1631-1673 (its suggested `k` key is still unbound).
> |    Still accurate: the settings reference tables lack the Shortcuts tab / `s`
> |    key; tuis/settings/how-to.md:15 omits `g` and `s`; test_website_doc_lists.sh
> |    Tests 1-2 exist.
> | 
> | 3. tuis/settings/reference.md is also named by t369_7, in a different section
> |    (Profile Schema > Planning) — and t369_7 documents a field reverted in t407,
> |    so it is likely to be closed.
