---
Task: t1687_2_concepts_attachments_and_attach_command.md
Parent Task: aitasks/t1687_concepts_docs_gap_sweep.md
Sibling Tasks: aitasks/t1687/t1687_1_concepts_gates_page.md, aitasks/t1687/t1687_3_concepts_task_notes_and_cross_repo.md, aitasks/t1687/t1687_4_concepts_trails_and_shadow_agent.md, aitasks/t1687/t1687_5_concepts_index_regroup_and_link_verification.md
Archived Sibling Plans: aiplans/archived/p1687/p1687_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-22 17:27
---

# t1687_2 — Attachments concept page and `ait attach` reference

## Context

Attachments are the worst-documented shipped surface on the site: `ait attach`
is a real subcommand (`.aitask-scripts/aitask_attach.sh`, 755 lines) but the only
website coverage is two rows in `development/task-format.md`. This task adds a
concept page (`concepts/attachments.md`, weight 55, *Data model*) and a command
reference (`commands/attach.md`, weight 34, `depth: [intermediate]`), and wires
them in. Almost all new prose; no duplication risk.

## Verification findings (2026-09-22, against the code)

- **Shipped verbs:** `ls` (alias `list`), `add`, `get`, `rm` (alias `remove`),
  `gc`, `help`. **`move` is a stub** — it dies with "not yet available — backend
  move arrives with a remote-backend task". Document `move` as *not available*
  (one sentence), never as a working verb. `decref-deleted` is internal
  (board hard-delete) — mention in one line as internal, no section.
- **`add` accepts only `--backend local`**; any other value dies. The concept
  page therefore describes the `backend` field and the content-addressed
  naming as backend-agnostic, but states that attachments are stored in the
  **local** backend today. Do not promise S3/GCS (current-state-only prose).
- **Storage:** `.aitask-data/attachments/blobs/<2>/<62>` (blob),
  `attachments/meta/<2>/<62>.json` (per-blob ledger: `hash`, `refs`, `mime`,
  `size`, `backend`, and `orphaned_at` once refs empty), global lock
  `attachments/.attach.lock`. Per-machine cache `~/.cache/ait/artifacts/<hash>`.
- **Frontmatter entry:** `hash`, `name`, `mime`, `size`, `added_at`
  (`YYYY-MM-DD HH:MM`, not ISO), `backend`. `name`/`added_at` live only in the
  task file (same bytes can have different names on two tasks).
- **add:** size cap `attachment_max_size_mb` (project_config, default 25);
  rejects a duplicate hash *or* duplicate name on the same task (`--name` to
  disambiguate); `--name` defaults to the file's basename; commits blob + meta
  + task file as one `ait:` commit.
- **get / rm resolution (`_attach_resolve_ref`):** exact match only — the
  full `sha256:<64hex>`, the full unprefixed 64-hex, or the exact name (hash
  match wins). **No prefix matching:** the 12-hex value `ls` prints is an
  abbreviation and does NOT resolve. `get` verifies the bytes hash back;
  writes to stdout, or `--out <path>`.
- **Backend today:** each task entry records `backend`, `add` accepts only
  `local`, `move` is a stub. So there is no shipped way to change an
  attachment's backend, and no current guarantee about what such a change
  would touch — do not claim "a backend change never rewrites task files".
- **rm:** decrefs and removes the frontmatter entry; does **not** delete the
  blob; stamps `orphaned_at` when refs empty.
- **gc:** takes no args; reclaims only blobs with empty refs, not listed by any
  active/archived non-Folded task, not referenced by any artifact manifest
  version, and — **when the meta carries an `orphaned_at` stamp** — orphaned
  longer than `attachments_gc_grace` (default `30d`). A zero-ref blob with no
  `orphaned_at` (e.g. one orphaned before the stamp existed) is treated as
  infinitely old and reclaimed on the next `gc`. `rm` and board hard-delete
  always stamp it. A malformed manifest aborts the sweep before anything is
  deleted.
- **Lifecycle:** archive never decrefs (archived task is a real referrer);
  fold rebinds refs to the primary; board hard-delete decrefs.
- **Dirty-path refusal:** every mutating verb refuses to start if the task
  file or a meta JSON it would commit has uncommitted changes; blobs are
  exempt. A failed transaction restores the pre-transaction bytes.
- Pre-phase note to t1231_3 **already landed** (two unread `from=t1687` notes
  in its inbox, 2026-09-10 and 2026-09-20) — do not re-send.
- t1687_5 owns the `**Next:**` reading chain; t1687_1 ended its page at
  `## See also` with no footer. Do the same here (the parent's
  `framework-session.md` shape minus the footer).
- Weights 55 (concepts) and 34 (commands) are free.
- `commands/_index.md` Tools table and usage block are relative-link style;
  `task-format.md:60` (`attachments` row), `:78` (nested-fields section) and
  `:98-99` (`ait artifact` / `ait attach` literals) are as the task describes.

## Pre-phase (risk mitigations)

### record_page_ownership_notes

Verified already satisfied — the ownership note is in t1231_3's inbox. No
action.

## Implementation

### 1. `website/content/docs/concepts/attachments.md` (NEW)

```yaml
---
title: "Attachments"
linkTitle: "Attachments"
weight: 55
description: "Content-addressed files attached to a task — identified by their hash, never by a path."
depth: [intermediate]
---
```

Sections:
- `## What it is` — an attachment is a file whose identity is its SHA-256
  (`sha256:…`); the name is a label. Short example of the frontmatter block.
  - `### Identity is the hash` — why never a path/URL: moving or deleting the
    source file cannot break the reference, free dedup, verification on
    fetch, the blob's storage path and cache key are derived from the hash.
    Same bytes attached to two tasks = one blob, two names. (No backend-
    migration claims — see verification findings.)
  - `### The attachments: block` — six fields, which are per-task
    (`name`, `added_at`) vs blob-intrinsic; never hand-edited.
  - `### Where blobs live` — text-fence ASCII tree of
    `.aitask-data/attachments/{blobs,meta}/<2>/<62>`; the per-machine cache;
    `backend` field records where the canonical copy lives; `local` (the
    `.aitask-data` branch) is the only backend `ait attach add` accepts, and
    there is no command to move an attachment to another backend.
  - `### One commit per change` — blob + meta + task file committed together
    under one lock; the dirty-path refusal and why (whole-path staging would
    absorb your edit); rollback on failure.
  - `### Reference counting and gc` — per-blob `refs` ledger; `rm` never
    deletes the blob; archive keeps refs; fold rebinds; board delete releases;
    `gc` is opt-in and honours the grace window and artifact manifests.
- `## Why it exists` — attachments must stay retrievable after the source file
  moves/deletes (the bytes are copied into git, keyed by hash); identical
  files are stored once; per-blob ledger avoids a global write hotspot on the
  shared data branch.
- `## How to use` — 3-4 line bash block (`add`/`ls`/`get`) + defer to the
  command page via relref.
- `## See also` — `commands/attach`, `development/task-format`
  (`#nested-fields-artifacts-and-attachments`), `concepts/tasks`,
  `concepts/folded-tasks`. All relref with full `/docs/...` paths.
  No `---`/`**Next:**` footer (t1687_5 owns the chain).

### 2. `website/content/docs/commands/attach.md` (NEW)

Frontmatter shaped on `lock.md`: `title: "Attach"`, `linkTitle: "Attach"`,
`weight: 34`, `description: "ait attach — manage a task's content-addressed file attachments"`,
`depth: [intermediate]`.

Body:
- Lead (crew.md pattern) linking the concept page by relref.
- `## ait attach` — synopsis bash block + verb table (`ls`, `add`, `get`, `rm`,
  `gc`, `help`), `<task>` accepts `16` / `16_2` / `t16_2`.
- `### ls` — columns `NAME HASH SIZE BACKEND`; state explicitly that the HASH
  column is **abbreviated to 12 hex digits for display and cannot be passed to
  `get`/`rm`** — use the name, or the full hash from the task file's
  `attachments:` block. "No attachments." when empty; dies on an entry with an
  invalid hash.
- `### add` — `--name`, `--backend` (only `local` accepted), size cap
  (`attachment_max_size_mb`, default 25 MB), duplicate hash/name refusal,
  single commit.
- `### get` — `<name-or-hash>` is an exact name, the full `sha256:<64hex>`,
  or the full 64-hex without prefix; no prefix/abbreviated match. Hash
  verified; stdout or `--out`.
- `### rm` — same resolution as `get`; detaches; blob kept until gc; stamps
  `orphaned_at` when the last reference goes.
- `### gc` — conditions for reclaim; grace counts from the `orphaned_at`
  stamp, and a zero-ref blob **without** that stamp is reclaimed on the next
  run; `attachments_gc_grace` (default `30d`); fail-closed on a malformed
  manifest; output line `gc: swept N …, retained M …`.
- `### Uncommitted changes` — the refusal rule and remedy.
- `### Not available` — `move` is listed in help but not implemented;
  `decref-deleted` is internal to `ait board` deletion.
- Configuration table: `attachment_max_size_mb`, `attachments_gc_grace`
  (in `aitasks/metadata/project_config.yaml`).

### 3. `website/content/docs/commands/_index.md`

- Tools table row (relative link):
  ``| [`ait attach`](attach/) | Manage a task's content-addressed file attachments (see [Attachments](../concepts/attachments/)) |``
- Usage block, next to the `ait note` lines:
  `ait attach add 357 screenshot.png      # Attach a file to task 357`

### 4. `website/content/docs/development/task-format.md`

- `:60` `attachments` row: append `See [Attachments]({{< relref "/docs/concepts/attachments" >}}).`
- `:78` nested-fields section: add a one-line pointer to the concept page
  (relref).
- `:98-99`: link **only** `ait attach` →
  `[`ait attach`]({{< relref "/docs/commands/attach" >}})`.
  **Leave `ait artifact` unlinked** (t1231_3's decision). Do not touch
  `skills/aitask-trail.md:85`.

## Post-phase (risk mitigations)

### link_relevance_triage (shared with t1687_5)

- Confirm `commands/attach.md` is reachable from `commands/_index.md`.
- `grep -n 'ait artifact' website/content/docs/development/task-format.md website/content/docs/skills/aitask-trail.md`
  — neither hit carries a relref or relative link.
- Run `python3 check_link_relevance.py` (report only) and triage new links.

### attach_claims_factcheck

Before Step 8 review, re-read both new pages claim by claim and check each
behavioural statement (verbs, flags, defaults, refusals, output lines, gc
conditions, lifecycle) against `.aitask-scripts/aitask_attach.sh` and
`./ait attach --help` — **not** against `aidocs/` (the design doc's §11
"decref on archive" is stale; the code never decrefs on archive). Remove or
correct anything that describes unshipped behaviour (`move`, non-local
backends, backend-migration guarantees). Explicitly re-check three items:
(a) no page implies the 12-hex `ls` value is accepted by `get`/`rm`
(`_attach_resolve_ref` is exact-match only); (b) no "backend change never
rewrites task files" claim; (c) the gc grace rule is stated as conditional on
`orphaned_at`, with the missing-stamp case reclaimed immediately.

## Verification

```bash
cd website && set -o pipefail && hugo build --gc --minify
cd website && python3 check_links.py --build
```

## Risk

### Code-health risk: low
- Re-linking the protected `ait artifact` literal at `task-format.md:98` or `skills/aitask-trail.md:85`, pre-empting t1231_3's retarget decision · severity: low · → mitigation: inline post-phase link_relevance_triage

### Goal-achievement risk: low
(Reassessed after inlining attach_claims_factcheck: was medium.)
- Pages describe design-doc behaviour that is not shipped (`move`, remote backends, backend-migration guarantees, stale aidocs claims such as decref-on-archive), or misstate shipped edge cases (abbreviated `ls` hash not resolvable by `get`/`rm`; gc grace skipped when `orphaned_at` is absent) · severity: medium · → mitigation: inline post-phase attach_claims_factcheck
- Page-ownership collision with t1231_3 (artifacts pages) · severity: low · → mitigation: inline pre-phase record_page_ownership_notes

### Planned mitigations
- timing: pre-phase | name: record_page_ownership_notes | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: page-ownership collision with t1231_3 | desc: ensure the ownership note reached t1231_3 (verified already landed)
- timing: post-phase | name: link_relevance_triage | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: protected ait artifact literal re-linked | desc: grep the protected literals, confirm reachability, run check_link_relevance.py
- timing: post-phase | name: attach_claims_factcheck | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: unshipped behaviour documented as shipped | desc: check every claim on both pages against aitask_attach.sh and ait attach --help

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge. `risk_evaluated` is in the active gate
set and is recorded by the Step-9 orchestrator.

## Upstream defect noted during verification

- `ait:51` — the dispatcher help line still reads
  "Manage task file attachments (ls; add/get/rm/move/gc pending)", but
  add/get/rm/gc are shipped; only `move` is pending. (Out of scope — docs task;
  record in Final Implementation Notes.)

## Final Implementation Notes
- **Actual work done:** New `website/content/docs/concepts/attachments.md`
  (weight 55, `depth: [intermediate]`, ends at `## See also`, no `**Next:**`
  footer) — angle: the hash is the identity; covers the six-field
  `attachments:` block (per-task vs blob fields), storage layout (ASCII tree),
  the one-commit rule and dirty-path refusal, and the reference lifecycle
  (add / rm / archive / fold / board delete / gc). New
  `website/content/docs/commands/attach.md` (weight 34) — verb table, one
  section per shipped verb (`ls`, `add`, `get`, `rm`, `gc`), "Uncommitted
  changes", "Not available" (`move`, internal `decref-deleted`), and a
  configuration table (`attachment_max_size_mb`, `attachments_gc_grace`).
  `commands/_index.md`: Tools row + usage line (relative links).
  `development/task-format.md`: concept relref on the `attachments` row, a
  pointer paragraph after the nested-fields block, and a relref on
  `ait attach` only.
- **Deviations from plan:** None. The pre-phase note was not re-sent (already
  in t1231_3's inbox).
- **Issues encountered:** Plan review (before approval) caught three
  misstatements drafted from the design doc: the 12-hex `ls` hash is display
  only (`_attach_resolve_ref` is exact-match); "a backend change never
  rewrites task files" is an unshipped guarantee; the gc grace window applies
  only when `orphaned_at` is recorded. All three are stated correctly on the
  pages.
- **Key decisions:** Documented against `aitask_attach.sh`, not `aidocs/`
  (the design doc's §11 still says "decref on archive"; the code never does).
  `move` gets one sentence as unavailable rather than a section.
- **Upstream defects identified:**
  - `ait:51` — the dispatcher help line reads "Manage task file attachments (ls; add/get/rm/move/gc pending)", but add/get/rm/gc are shipped; only `move` is pending.
  - `aidocs/task_attachments_design.md:396-397` — the §11 decomposition still lists "decref on archive" for the archive-integration child, contradicting §8's resolved "archiving never decrefs" (t1030_3). Internal design doc is stale.
- **Notes for sibling tasks:**
  - `check_links.py --build` and `hugo build` both pass; `check_link_relevance.py`
    reported nothing for the new links.
  - The `**Next:**` insertion point for this page (weight 55, between
    review-guides 50 and execution-profiles 60)
    is left to t1687_5.
  - `task-format.md:59` (the `artifacts` row) still contains the
    `#nested-fields-...` anchor link; `ait artifact` itself remains unlinked.
