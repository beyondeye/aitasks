---
Task: t1231_3_artifact_documentation.md
Parent Task: aitasks/t1231_configurable_git_branch_artifact_backend.md
Sibling Tasks: aitasks/t1231/t1231_1_gitbranch_artifact_backend.md, aitasks/t1231/t1231_2_artifacts_settings_tab.md
Archived Sibling Plans: aiplans/archived/p1231/p1231_1_*.md, aiplans/archived/p1231/p1231_2_*.md
Base branch: main
plan_verified: []
---

# t1231_3 — Artifact documentation

## Context — the gap, verified

`grep -rn "ait artifact\|ait attach" website/content/docs/` returns **zero real
hits**. The single match is `installation/terminal-setup.md:78,108`, which is
`tmux -L ait attach -t aitasks` — a tmux socket name, unrelated.

There is no `commands/artifact.md`, no `concepts/artifacts.md`, and
`commands/_index.md` does not list `ait artifact` or `ait attach` in any of its
category tables — even though `.aitask-scripts/aitask_artifact.sh` (687 lines)
and `aitask_attach.sh` (636 lines) have shipped, with two backends already
present (`lib/artifact_backends/{local,dir}.sh`). The only mentions anywhere in
the site are two blog posts (`blog/v0280-…`, `blog/v0270-…`).

So this task does two things at once: it writes the **missing baseline
documentation** for a shipped feature, and it documents the `gitbranch` backend
(t1231_1) and the Artifacts settings tab (t1231_2).

Read the sibling plans before writing — `aiplans/archived/p1231/p1231_1_*.md`
carries the authoritative `gitbranch` semantics (rules R1–R4), and
`p1231_2_*.md` the settings-tab shape and its key binding.

## Implementation steps

### 1. New concept page — `website/content/docs/concepts/artifacts.md`

Frontmatter shape from `concepts/git-branching-model.md:1-7`:

```yaml
---
title: "Artifacts"
linkTitle: "Artifacts"
weight: <fits the Data model group>
description: "<one line>"
depth: [advanced]
---
```

Content, sourced from `aidocs/unified_artifact_design.md` §4b, §5, §6, §7:

- The resolution chain: stable `art:<id>` handle → manifest
  (`current` / `versions` / `backend`) → backend → local cache
  (`~/.cache/ait/artifacts/<hash>`).
- The **hash-first invariant**: a backend swap or a version repoint touches only
  the manifest, never a task file. This is the property the whole model turns on.
- Why a task file carries only the handle, and the manifest carries the mutable
  state.
- The **backend table** — `local`, `dir`, `gitbranch` — with when to pick each.
  This table is the drift-guard target in step 5, so give each backend name its
  own literal table cell.

**Must state the `gitbranch` operating rules a user can actually trip over:**

- writes require a **reachable remote** (publish is push-gated — a blob is not
  "stored" until it is pushed, so a handle never points at bytes only one machine
  has);
- the branch must be one the store owns — pointing at an **existing ordinary
  branch is refused**, and reserved names (`main`, `master`, `aitask-data`,
  `aitask-locks`, `aitask-ids`) are rejected outright;
- renaming the configured branch needs **`ait artifact gitbranch-migrate`**, not
  `ait artifact move` (a same-backend move is a no-op — say so, because the
  wrong instinct is the natural one).

### 2. New command page — `website/content/docs/commands/artifact.md`

Frontmatter shape from `commands/lock.md:1-7` (`weight` in the 30s alongside the
other command pages, `depth: [intermediate]`).

Verb reference: `create`, `update`, `move`, `rm`, `ls`, `get`, `versions`,
`gitbranch-migrate`. Plus the `artifacts:` config block and a pointer to the
Artifacts settings tab. Cross-reference `ait attach` in one line (attachments
remain local-only this cycle — do not write a full attach page here).

Verify every documented flag against the live `aitask_artifact.sh` help output
rather than from the design doc; the doc is the intent, the script is the truth.

### 3. Hand-maintained lists — all manual, nothing derives them

- **`website/content/docs/commands/_index.md`** — a row in the category table
  (Tools section is the natural home) **and** an entry in the
  `## Usage Examples` fenced bash block, which also enumerates commands by hand.
  This section uses **relative** links (`sync/`, `lock/`).
- **`website/content/docs/concepts/_index.md`** — a bullet under the
  **Data model** heading. This section uses the
  `{{< relref "/docs/concepts/..." >}}` **shortcode** form. The two sections
  differ — match the one you are editing.
- **`website/content/docs/concepts/git-branching-model.md:13-18`** — add an
  `aitask-artifacts` row to the branch table (currently `main` / `aitask-data` /
  `aitask-locks` / `aitask-ids`), marked **optional** (it exists only when the
  `gitbranch` backend is configured).

### 4. Settings docs — fix the pre-existing staleness in the same pass

`website/content/docs/tuis/settings/`:

- `reference.md:14-26` — the global keyboard-shortcut table.
- `reference.md:54-62` — the `## Tabs` table (Tab | Shortcut | Editable | Description).
- `reference.md:75-88` — the `## Configuration Files` table.
- `how-to.md:15` — the mouse-support line, which hardcodes `a / b / c / t / m / p`.

**All of these are already stale**: they omit the shipped Shortcuts tab and its
`s` key. Fix that while adding the Artifacts row — appending a ninth row to a
table that is already wrong just entrenches the error. Take the current truth
from `settings_app.py`'s `_TAB_SWITCH_ACTIONS` and `BINDINGS`, not from the
existing tables.

The Configuration Files table also needs `project_config.yaml`'s `artifacts:`
block noted as TUI-editable once t1231_2 lands.

### 5. Drift guard — the part that stops this gap reopening

Extend **`tests/test_website_doc_lists.sh`** — the only website drift test (from
t1162_5) — with a third check, in the style of its existing Tests 1 and 2:
containment assertions (extra doc rows allowed) plus a tripwire so the grep
cannot vacuously pass.

- Parse every `ARTIFACT_BACKEND` `case` arm out of
  `.aitask-scripts/lib/artifact_backend.sh` (the dispatcher around L44-50),
  excluding the `*)` catch-all and the `# BACKEND-EXTENSION-POINT` comment line.
- For each backend name, assert the literal table cell `| \`<name>\` |` appears
  in `website/content/docs/concepts/artifacts.md`
  (`assert_contains`, as Test 1 does for codeagent operations).
- **Tripwire:** assert the parsed arm count is `> 0`, so a parsing change that
  yields an empty list fails loudly instead of passing vacuously.

This is what stops **t1089** (`s3`) and **t1090** (`gdrive`) from silently
re-opening the documentation gap when they land.

### 6. Non-website files

- **`seed/project_config.yaml:189-225`** — the `artifacts:` block is present but
  fully commented. Extend it with the `gitbranch` example, matching the existing
  block's commenting style and its "SECRETS NEVER GO HERE" framing. Note that
  `gitbranch` needs no secret and no mount — that is its selling point against
  `dir`.
  **The live `aitasks/metadata/project_config.yaml` has no `artifacts:` section
  and stays that way** — `local` remains this repo's default.
- **`aidocs/unified_artifact_design.md` §5 / §6** — register `gitbranch` in the
  backend narrative (§5's backend table, §6's "the first configured backend is
  `dir`" passage) so the design doc does not go stale against the code.

## Reference files for patterns

- `website/content/docs/concepts/git-branching-model.md` — frontmatter shape,
  the branch table to extend, and the closest tonal match for the concept page.
- `website/content/docs/commands/lock.md`, `commands/sync.md` — command-page
  frontmatter and structure.
- `tests/test_website_doc_lists.sh` — the guard style: sources
  `tests/lib/asserts.sh`, `assert_contains` on literal table cells, tripwires
  guarding the parse.
- `aidocs/framework/documentation_conventions.md` — **mandatory.**
  Current-state-only (no version history in doc bodies), the "delete X / integrate
  into Y means redirect cross-refs now" rule, and genericize any passage naming
  the supported coding agents.
- `aidocs/unified_artifact_design.md` §4b, §5, §6, §7 — the authoritative source
  for the concept page's content.

## Verification

- `cd website && hugo build --gc --minify` — succeeds with no broken `relref`.
- `bash tests/test_website_doc_lists.sh` — passes with the new third check.
  **Then prove the guard bites:** remove the `gitbranch` row from
  `concepts/artifacts.md`, re-run, confirm it exits 1, restore. (Restore by
  undoing the edit, **not** `git checkout --` — that would wipe other uncommitted
  work in the same file.)
- `grep -rn "ait artifact" website/content/docs/` now returns the two new pages
  plus the `_index.md` rows.
- Cross-check the settings tables against `settings_app.py`'s live
  `_TAB_SWITCH_ACTIONS` and `BINDINGS` — every tab present, every key correct,
  including the Shortcuts row that was missing before.
- `cd website && ./serve.sh` — read both new pages rendered, confirm sidebar
  placement and weights put them where a reader would look for them.

## Out of scope

A full `ait attach` command page. Attachments remain local-only this cycle
(t1258 tracks extending them); a one-line cross-reference from the artifact pages
is sufficient here.

## Post-implementation

Per `task-workflow` Step 9 — merge approval, `ait gates run 1231_3`, archival.
This is the final child, so archiving it archives the parent t1231 too.
