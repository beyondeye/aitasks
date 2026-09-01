---
Task: t1657_6_documentation_website_and_aidocs.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_1_*.md, aitasks/t1657/t1657_2_*.md, aitasks/t1657/t1657_3_*.md, aitasks/t1657/t1657_4_*.md, aitasks/t1657/t1657_5_*.md
Base branch: main
Output branch: main
---

# p1657_6 — Documentation: website reference, workflow guide, aidocs contracts

## Goal

Document what actually shipped. Lands last for that reason. Follow
`aidocs/framework/documentation_conventions.md` — **current-state only**, no
version history in doc bodies, genericize passages naming specific coding agents.

## Main steps

### 1. `website/content/docs/commands/note.md` (new)

`ait note` is a new top-level dispatcher command, so it gets a **full CLI
reference page**, not a mention. Match the house shape of `commands/lock.md`:

- frontmatter: `title: "Note"`, `linkTitle: "Note"`, `weight: 37` (between `lock`
  36 and `gates` 38), `depth: [intermediate]`, a `description:` line;
- a `## ait note` heading, a usage block, a **flags table** for
  `<target-task-id>`, `--from`, `--text`, `--file`, and the `read` verb
  (`--by`, `--ids`, `--mode`).

Must document — these are what a scripting user actually needs:

- **the output contract**: `NOTE_APPENDED:<note-id>|<path>`,
  `NOTE_TARGET_MISSING:`, `NOTE_SELF:`, `NOTE_ERROR:`, plus the `LIVE_*` reason
  codes — the way `lock.md` documents exit codes 0/1/13/14;
- **which result is authoritative**: the CLI reports the durable write and
  nothing else; live outcomes come from the agent adapter; `LIVE_NONE:<reason>`
  after a successful append is a **success**;
- **the `base` provenance contract**: which repository is queried (the code repo
  root, never the task-file path or `.aitask-data`), that capture happens before
  the append, and what `none` / `unknown` mean;
- **that `from=` is a claim**, and what `from_verified=` does and does not prove.

### 2. `website/content/docs/commands/_index.md`

Rows in the **Task Management** table for `ait note` and the read side.
**Hand-maintained — a page not listed here is effectively invisible.**

### 3. `website/content/docs/workflows/task-notes.md` (new)

End-to-end: when to note vs. spawn a task, both lanes, what happens when live
delivery is unavailable, the trust posture. Add its entry to the manually
maintained `workflows/_index.md` under **Tasks**.

### 4. Cross-links

From `commands/lock.md` and `concepts/locks` — live-endpoint resolution reads the
lock record.

### 5. `aidocs/framework/task_note_mailbox.md` (new)

- the entry format and the `> | ` body sentinel, and **why**: the injection
  surface is new (the gate ledger's bodies are fixed labels, so its format never
  had to resist injection);
- the **section-ordering invariant** — `## Inbox` precedes `## Gate Runs`,
  because both gate-append paths are EOF-anchored;
- the merge contract for concurrent cross-PC appends;
- the note-id scheme and why uniqueness is checked under the lock rather than
  merely improbable;
- the trust posture, and the read-receipt decision (a note consumed on one PC
  does not resurface on another);
- the known constraint that `aitask_update.sh --desc-file` replaces the body and
  would drop the section — a **pre-existing hazard `## Gate Runs` already
  shares**, not one introduced here.

### 6. `aidocs/framework/live_endpoint_resolution.md` (new)

**Its own document, because the boundary outlives notes.**

- the resolver contract and output shapes;
- the **full degradation table** — every reason code, its trigger, its guaranteed
  durable outcome;
- the generic/adapter split, and **why** the adapter is a skill procedure rather
  than a script;
- how to add an adapter for a new agent runtime, and the current Codex state
  (`codex queue` exists; `codex agents` has no machine-readable listing);
- the standing rule that **tmux is discovery, never transport**, with the reason.

## Verification

- `cd website && hugo build --gc --minify` builds clean
- **every new cross-reference resolves.** `hugo build` does **not** fail a dead
  `#fragment`, and `--minify` unquotes `id=` attributes — check anchor targets by
  hand against the rendered ids, never infer them from the build exit code
- the new pages appear in the rendered nav via their `_index.md` rows
- grep the docs for any surviving claim that live delivery is unconditional, or
  that a note is anything other than advisory

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9.

## Risk

### Code-health risk: **low**

- Docs-only; no runtime surface touched.

### Goal-achievement risk: **low**

- Lands last, so it documents shipped behaviour rather than intent.
- Residual: a dead anchor passes `hugo build` silently · severity: low ·
  → mitigation: the by-hand anchor check named in Verification
