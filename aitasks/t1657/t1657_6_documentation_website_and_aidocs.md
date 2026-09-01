---
priority: medium
effort: medium
depends: [t1657_3, t1657_5]
issue_type: documentation
status: Ready
labels: [documentation, web_site, framework]
gates: [risk_evaluated]
anchor: 1657
created_at: 2026-09-01 12:37
updated_at: 2026-09-01 12:37
---

# Documentation: website CLI reference, workflow guide, and aidocs contracts

## Context

Parent plan: `aiplans/p1657_task_note_mailbox_with_live_delivery.md`.
Lands after t1657_1..t1657_5 so it documents what actually shipped, not what was
planned. Follow `aidocs/framework/documentation_conventions.md` — **current-state
only**, no version history in doc bodies, and genericize any passage that names
the supported coding agents.

## Website — `ait note` gets a full CLI reference page, not a mention

It is a new top-level dispatcher command, so document it the way `ait lock` and
`ait gates` are.

### `website/content/docs/commands/note.md` (new)

Match the house shape of `website/content/docs/commands/lock.md`:

- frontmatter: `title: "Note"`, `linkTitle: "Note"`, `weight: 37` (between
  `lock` 36 and `gates` 38), `depth: [intermediate]`, a `description:` line;
- a `## ait note` heading, a usage block, and a **flags table** covering
  `<target-task-id>`, `--from`, `--text`, `--file`, and the `read` verb
  (`--by`, `--ids`, `--mode`).

It must document, because these are the parts a scripting user actually needs:

- **the structured output contract** — `NOTE_APPENDED:<note-id>|<path>`,
  `NOTE_TARGET_MISSING:`, `NOTE_SELF:`, `NOTE_ERROR:` — and the `LIVE_*` reason
  codes, the same way `lock.md` documents its exit codes 0/1/13/14;
- **which result is authoritative** — the CLI reports the durable write and
  nothing else; live outcomes come from the agent adapter; and
  `LIVE_NONE:<reason>` after a successful append is a **success**, not a partial
  failure;
- **the `base` provenance contract** — which repository is queried (the code repo
  root, never the task-file path or `.aitask-data`), that capture happens before
  the append, that `base` / `base_mergebase` are **full object ids** (storage is
  exact, presentation may abbreviate) and why, and what the `none` / `unknown`
  sentinels mean — so a reader knows exactly what tree a note's claims can be
  checked against;
- **that `from=` is a claim**, and precisely what `from_verified=` does and does
  not prove.

### `website/content/docs/commands/_index.md`

Add rows to the **Task Management** table — one for `ait note`, one for the read
side. **This index is hand-maintained; a page not listed here is effectively
invisible.**

### `website/content/docs/workflows/task-notes.md` (new)

The end-to-end story: when to note vs. spawn a task, both lanes, what happens
when live delivery is unavailable, and the trust posture. Add its entry to the
manually maintained `website/content/docs/workflows/_index.md` under **Tasks**.

### Cross-links

From `commands/lock.md` and `concepts/locks`, since live-endpoint resolution
reads the lock record.

## Internal — `aidocs/`

### `aidocs/framework/task_note_mailbox.md` (new)

- the `## Inbox` entry format and the `> | ` body sentinel (**why** it exists:
  the injection surface, which is new — the gate ledger's bodies are fixed
  labels, so its format never had to resist injection);
- the **section-ordering invariant** — `## Inbox` must precede `## Gate Runs`,
  because both gate-append paths are EOF-anchored and an Inbox placed after would
  silently swallow every future gate block;
- the merge contract for concurrent cross-PC appends;
- the note-id scheme and why uniqueness is checked under the lock rather than
  merely improbable;
- why `base` stores a **full** object id: `core.abbrev` is unset, so git
  auto-scales abbreviation to current repo size, and a prefix frozen into a
  durable note can become ambiguous as the repository grows — breaking the
  exact-tree promise for exactly the oldest notes;
- the trust posture;
- the known constraint that `aitask_update.sh --desc-file` replaces the body and
  would drop the section — a **pre-existing hazard `## Gate Runs` already
  shares**, not one introduced here.

### `aidocs/framework/live_endpoint_resolution.md` (new)

**Its own document, because the boundary outlives notes.** The primitive is
"find the live agent implementing task X"; notes are only its first consumer.

- the resolver contract and its output shapes;
- the **full degradation table** — every reason code, its trigger, and its
  guaranteed durable outcome;
- the generic/adapter split, and **why** the adapter is a skill procedure rather
  than a script (`SendMessage`/`ListAgents` are model-facing tools with no CLI);
- how to add an adapter for a new agent runtime, and the current state of the
  Codex path (`codex queue` exists; `codex agents` has no machine-readable
  listing, so there is nothing to resolve against);
- the standing rule that **tmux is discovery, never transport**, with the reason:
  `send-keys` injects into whatever UI state a pane is in, carries no agent
  identity or message framing, and offers no queued/received semantics.

## Verification

- `cd website && hugo build --gc --minify` builds clean.
- **Every new cross-reference resolves.** `hugo build` does **not** fail a dead
  `#fragment`, and `--minify` unquotes `id=` attributes — so anchor targets must
  be checked by hand against the rendered ids, not assumed from the build exit
  code.
- The new pages appear in the rendered nav via their `_index.md` rows.
- No stale claim survives: grep the docs for any statement that live delivery is
  unconditional, or that a note is anything other than advisory.
