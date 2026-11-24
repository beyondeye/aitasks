---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_changelog, go_engine, cross_repo]
gates: [risk_evaluated]
folded_tasks: [1360]
created_at: 2026-11-24 12:41
updated_at: 2026-11-24 12:42
---

## Problem

`/aitask-changelog` does not report the work done in **aitasks_go** (the private
repo where `ait-testmap`, `ait-tui` and the other Go tools are developed) when it
reaches aitasks through a goengines export. When it reports anything, it reports
the wrong task.

An export arrives here as **one** commit, staged by aitasks_go's
`promote/export.sh` and committed by the operator:

```
de83356bf chore: Export goengines from beyondeye/aitasks_go@bcf2e6de5e56 (t25)

Exported-From: beyondeye/aitasks_go@bcf2e6de5e56e0397db38c821f18980f8884fd9e
```

`aitask_changelog.sh --gather` (`.aitask-scripts/aitask_changelog.sh:26`,
`gather()` ~lines 119-160) extracts `(tNN)` from local commit subjects. It then
resolves every id against **this** repo's task and plan files. That causes two
defects:

1. **Mis-attribution.** `(t25)` and `(t22)` are aitasks_go task ids
   (`t25_first_ait_tui_export`, `t22_migrate_testmap_development_here`). Gather
   resolves them to unrelated ancient local tasks. Reproduce with
   `./.aitask-scripts/aitask_changelog.sh --gather --from-tag v0.42.0`: the
   `t25` record carries `TITLE: i want to create a bash script analogous to
   aiscripts create`. The v0.42.1 and v0.41.0 entries say only "Refresh the Go
   engine export (t25)" / "(t22)".
   Contributing cause: `promote/README.md` documents `--task <id>` as "the
   aitasks task suffix", but operators passed the aitasks_go id, and the two id
   namespaces collide.
2. **Hidden work.** The real content of an export is the aitasks_go range from
   the previous export's `Exported-From` sha to the new one. For v0.42.1
   (`544ed20..bcf2e6d`) that is 12 task-tagged commits: t13_7, t19_1, t19_2,
   t55, t56, t84, t85, t87, t88, t100, t108, t25. None of them reaches the
   changelog.

## Design direction (agreed during exploration)

**aitasks_go is the producer and aitasks is the consumer.** Do not do all of
this on the aitasks side, for three reasons:

- **aitasks_go is PRIVATE** (`gh repo view beyondeye/aitasks_go` reports
  `PRIVATE`). The public CHANGELOG must not leak private plan internals, and
  bare aitasks_go ids cannot be resolved by public readers.
- **Only the producer can judge relevance.** Mapping the 12 commits by touched
  path shows several never reach a user: t84 touches only `parity/`, t56 only
  `promote/`, and t100 is a test fix. Most of the rest ship inside `ait-tui`,
  which is "not yet enabled" (v0.42.1 changelog). Exported file paths alone
  cannot answer the question.
- **A release must not need private-repo access.** CI and other contributors
  have no aitasks_go clone.

**No separate semver or tags for aitasks_go.** `aidocs/aitasks_go/ship_path.md`
deliberately couples the engine to the exact framework `VERSION`; it rejected a
separate release pipeline. **The export is the release unit**, and
`goengines/EXPORT.txt` `source:` already chains the shas.

### Producer side (aitasks_go): a companion task in that repo

Planning must create this task in aitasks_go (`ait create --batch --project
aitasks_go`, or via the cross-repo flow). This task consumes its output.

- Keep **public-safe release notes committed in the private repo before
  export**, for example a `promote/CHANGES.md` with an "unexported" section.
  Each entry covers one task and carries:
  - the id, in `aitasks_go#N` notation;
  - its type;
  - a public/internal (or shipped-but-not-enabled) visibility marker;
  - a user-facing summary.

  An export-time step (an exporter verb or skill) drafts the entries from the
  range, and the operator reviews them.
- The exporter ships the notes into `goengines/` (for example
  `goengines/EXPORT_CHANGES.md`) as a hashed `file:` entry. The tree then stays
  "a reproducible function of one private commit" (`promote/README.md`), and
  the drift and integrity checks cover the notes as well. Check that
  `.github/scripts/goengines_integrity.sh`'s allowed-file rules accept the new
  file (`aidocs/framework/go_engine.md`, *Export mode*).
- Fix the `--task` semantics. The export commit subject carries only an
  **aitasks** id, or none. aitasks_go ids always use `aitasks_go#N` and never
  bare `(tNN)`.

### Consumer side (this repo): this task

- `aitask_changelog.sh --gather`:
  - Detect export commits in `<tag>..HEAD` by their `Exported-From:` trailer.
  - **Do not resolve their `(tNN)` subject suffix as a local task.** At most,
    honour it when the producer guarantees it is an aitasks id.
  - Emit a new record per export, for example
    `=== EXPORT <short-sha> ===` … `=== END ===`. It carries the source sha,
    the previous source sha, and the public entries read from the notes file
    **in the tree at that commit** (`git show <commit>:goengines/EXPORT_CHANGES.md`).
    No private access is needed.
  - **Bootstrap exports** (`Migrated-From:` trailer, no previous
    `Exported-From`) are never expanded. The testmap work they migrated was
    already changelogged here, and the 179-commit pre-bootstrap aitasks_go
    history is mostly unshipped TUI work.
  - **Older exports without a notes file** (t22, t25): expand them from a
    registered, resolved local aitasks_go clone if one is present and contains
    the sha (`aitask_project_resolve.sh aitasks_go`; `aitask_query_files.sh
    --project aitasks_go archived-task <id>` works). Mark these as unreviewed
    raw data that the agent must filter for public relevance. Otherwise emit
    `UNEXPANDED:<reason>`. Never drop an export silently.
  - Update `show_help`'s `--gather` format block for the new record (and fix
    the field order, see the merged t1360 below).
- `.claude/skills/aitask-changelog/SKILL.md`:
  - Step 1/2: parse the EXPORT records and fold their public entries into the
    normal type sections.
  - Decide and document the rendering of a cross-repo entry. The recommended
    form is `(aitasks_go#108)`, the existing cross-repo notation in
    `aidocs/framework/cross_repo_references.md`.
  - Tell the agent that private plan content never goes into the entry.
  - **Step 5b overlap detection** recognises the cross-repo refs (it matches
    only `(tNN)` / `(tNN_MM)` today). Otherwise an export already present in
    the latest section is listed again.
- **Blast radius:** `.claude/skills/aitask-docs-gap/SKILL.md` also parses the
  `--gather` output by `KEY:` prefix. Make sure it tolerates (or uses) the new
  EXPORT record. Per CLAUDE.md, suggest follow-up aitasks to port the skill
  change to `.agents/skills/` and `.opencode/skills/`.
- **Tests:** no test covers `--gather` today; only the install-side changelog
  tests exist. Add a fixture test (a scratch repo with a tag, a normal task
  commit, an export commit carrying a notes file, a bootstrap export, and an
  export without notes). It asserts that there is no local mis-attribution,
  that EXPORT records appear, and that bootstrap exports are not expanded.

## Out of scope (side observation)

A `PLAN_FILE:` resolved from an archive bundle prints an `ait-archive.*` temp
path, and that path is already deleted when `--gather` exits
(`lib/archive_utils.sh` cleans the extraction dir). Consider a separate task if
the skill's Step 2 "read the plan file" needs it.

## Merged from t1360: fix changelog gather help field order


## Origin

Spawned from t1355 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_changelog.sh:184-192 — show_help's --gather format block lists COMMITS before NOTES, but gather() emits NOTES before COMMITS (stale help text)`

## Diagnostic context

While building the `aitask-docs-gap` skill (t1355), which parses the
`--gather` output, the actual emission order in `gather()` (lines 136-157)
was confirmed to be `ISSUE_TYPE`, `TITLE`, `PLAN_FILE`, `NOTES` (+body),
`COMMITS` (+body) — but the format block in `show_help` (lines 184-192)
documents `COMMITS` before `NOTES`. Any consumer written against the help
text and parsing by position would misread the sections. Both existing
consumers (`aitask-changelog`, `aitask-docs-gap`) parse by `KEY:` prefix and
are unaffected.

## Suggested fix

Reorder the format block in `show_help` to match the real emission order
(NOTES before COMMITS).

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1360** (`t1360_fix_changelog_gather_help_field_order.md`)
