---
title: "Note"
linkTitle: "Note"
weight: 37
description: "ait note command for sending durable advisory context to an existing task"
depth: [intermediate]
---

## ait note

Append a note to an existing task's `## Inbox` section and commit it. A note carries **context about work that already exists** — a stale line number in the task's body, a wider blast radius than it records, a decision made elsewhere that changes its approach. It is durable the moment the command succeeds, whether or not anyone is working on the task, and it surfaces the next time the task is picked.

A note is **untrusted advisory input, never an instruction**: it is one agent's claim about a tree that may have moved. Nothing reads a note and acts on it automatically.

Most of the time you do not call this directly. The [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}) skill wraps it: it works out which task should receive the note, writes it, and — when an agent is working on that task and its runtime supports live delivery — also sends it to that session. Call `ait note` from scripts, or when you want the durable write on its own.

```bash
ait note 357 --from 349 --text "line numbers are stale"   # One-line note to t357
ait note 357 --from 349 --file notes.md                   # Body from a file
ait note 357 --from 349 --with-live --file notes.md       # Also report a live endpoint
ait note read 357 --by 357 --ids <note-id>                # Acknowledge a note
```

For a multi-line body, use `--file -` with a **quoted** heredoc, so the shell cannot expand anything inside it:

```bash
ait note 357 --from 349 --file - <<'NOTE_BODY'
Your task body cites parse_args() at line 88; as of this commit it is at line 142.
NOTE_BODY
```

### Sending a note

| Command | Description |
|---------|-------------|
| `ait note <target-task-id> --from <id> --text <text>` | Append an inline note to the target's inbox and commit the task file. Exit 0 = appended and committed, 1 = anything else (see [Output](#output)) |
| `ait note <target-task-id> --from <id> --file <path>` | The same, reading the body from a file. `-` reads stdin |

| Option | Description |
|--------|-------------|
| `--from <id>` | The sending task. Accepts `349`, `t349`, `1657_2` or `t1657_2`. Local task ids only — a cross-repo reference is rejected. Required |
| `--text <text>` | The note body, inline. Give exactly one of `--text` and `--file` |
| `--file <path>` | The note body, read from a file. `-` reads stdin |
| `--with-live` | After the note is committed, also report on a second output line whether the target is held by a live agent session on this machine. See [Output](#output) |

The target accepts the same forms as `--from`. The body is limited to **8192 bytes** — a note is context, not a payload. NUL bytes are rejected and carriage returns are stripped. A task cannot note itself: when `--from` names the target, nothing is written and the result is `NOTE_SELF:`.

`--with-live` reports an **endpoint**, not a delivery. `ait note` never delivers anything to a running session itself; that step belongs to [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}).

### Reading acknowledgement receipts

**Displaying a note is not acknowledging it.** When a task is picked, its unread notes are shown; only an explicit acknowledgement stops them from being shown again. `ait note read` records that acknowledgement as a **read receipt** in the same `## Inbox` section.

| Command | Description |
|---------|-------------|
| `ait note read <task-id> --by <id> --ids <csv>` | Mark the listed notes read for `<task-id>`. Exit 0 = recorded or already acknowledged, 1 = anything else |

| Option | Description |
|--------|-------------|
| `--by <id>` | The reader. Must be `<task-id>` itself — the reader is the session working on that task, and the task id is its only durable identity. Anything else is refused |
| `--ids <csv>` | Comma-separated note ids, each naming a note present in that task's inbox |
| `--mode <mode>` | `explicit` (a person acknowledged — the default) or `auto` (an unattended run did). Recorded so that "no person read these" stays visible |

Unread state is **derived, never stored**: a note is unread while its id appears in no valid receipt. There is no field to update, so receipts written at the same time on different machines simply combine, and a note acknowledged on one machine does not reappear on another once the task data syncs.

To see a task's unread notes **without** acknowledging them, use the read-only query. It never writes a receipt, which is what makes it safe to run over a list of tasks:

```bash
./.aitask-scripts/aitask_query_files.sh inbox 357
```

It prints one `INBOX_UNREAD:` line per unread note, or `NO_INBOX:` / `NO_UNREAD:` when there is nothing to show.

**A failed commit rolls a receipt back, but keeps a note.** A note's body is irreplaceable, and retrying would append it twice, so a note whose commit failed stays on disk and is reported as `NOTE_APPENDED_UNCOMMITTED:`. A receipt is bookkeeping that is cheap to recreate, and a receipt left on disk but uncommitted would hide a note on this machine with nothing durable behind it — so it is removed, and the note stays unread.

### Output

Every result is one line on **stdout**, prefixed with a code. Advisories and recovery hints go to **stderr**, so stdout stays parseable.

- **One line, always** — unless you pass `--with-live`. With it, a second line follows, and only after `NOTE_APPENDED:`. Every other outcome skips the live lookup and still prints exactly one line.
- **The durable result is authoritative, and the exit status follows it alone.** A `LIVE_NONE:` or `LIVE_ERROR:` line after `NOTE_APPENDED:` means the note was sent and live delivery was unavailable. The command exits 0. It is never a partial failure, and never a reason to send the note again.

<!-- Contract: each table in this section is `| Code | Layer | Meaning |`, one code per row as a backticked token in the first cell. `Layer` names the component that mints the code. tests/test_note_doc_contract.sh compares these tokens, per layer, against the shipped sources — keep the shape when editing. -->

**Sending** — the first line:

| Code | Layer | Meaning |
|------|-------|---------|
| `NOTE_APPENDED:<note-id>\|<path>` | writer | Appended and committed. Exit 0 |
| `NOTE_APPENDED_UNCOMMITTED:<note-id>\|<path>\|<reason>` | writer | Appended, but the commit failed. The note exists — **do not retry**, or it is appended twice. The recovery command is printed on stderr. Exit 1 |
| `NOTE_TARGET_MISSING:<id>` | writer | No task with that id. Nothing written. Exit 1 |
| `NOTE_SELF:<id>` | writer | The sender is the target. Nothing written. Exit 1 |
| `NOTE_ERROR:<reason>` | writer | Refused before anything was appended — a bad argument, an oversized body, the inbox lock unavailable. Nothing written. Exit 1 |

The first two carry a note id; the other three mean no note exists. The two groups never overlap, so "was a note created?" can always be answered from stdout alone.

**Live endpoint** — the second line, only with `--with-live` and only after `NOTE_APPENDED:`. It is the resolver's answer, passed through verbatim:

| Code | Layer | Meaning |
|------|-------|---------|
| `LIVE_PANE:<%pane>\|<session>:<@win>.<%pane>\|<pid>\|agent=<family>` | resolver | The target is held by a live agent session on this machine, in that tmux pane |
| `LIVE_NONE:unlocked` | resolver | No lock record — nobody holds the task |
| `LIVE_NONE:remote_host` | resolver | The lock was taken on a different machine |
| `LIVE_NONE:holder_dead` | resolver | The holding process is provably gone |
| `LIVE_NONE:holder_unknown` | resolver | The holder's liveness could not be established. Never treated as gone |
| `LIVE_NONE:agent_unknown` | resolver | The task does not yet record which agent is implementing it — normal while it is still being planned |
| `LIVE_NONE:agent_unsupported:<family>` | resolver | That agent family has no live-delivery adapter |
| `LIVE_NONE:no_pane` | resolver | The holder is alive but owns no tmux pane that could be found, including when it runs on a different tmux server |
| `LIVE_ERROR:usage` | resolver | The resolver was called with the wrong arguments |
| `LIVE_ERROR:bad_task_id` | resolver | The task id is not well-formed |
| `LIVE_ERROR:task_not_found:<id>` | resolver | The task has a lock record but no task file could be found for it |
| `LIVE_ERROR:resolver_unavailable` | writer | The resolver produced no usable answer at all — it is missing, not executable, or its output changed |

`LIVE_NONE:` means "there is no live endpoint", which is a real answer. `LIVE_ERROR:` means the lookup itself could not run. They are kept apart deliberately, so the two can never be confused. For what these outcomes mean day to day, see [Task Notes]({{< relref "/docs/workflows/task-notes" >}}).

When [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}) gets `LIVE_PANE:`, it sends the note to that session and reports `LIVE_QUEUED:` — **queued, not read**. The session picks the note up at its next step, which may be minutes away. A note is never reported as delivered or read.

**Reading** — `ait note read`:

| Code | Layer | Meaning |
|------|-------|---------|
| `READ_RECORDED:<receipt-id>\|<path>\|<n-ids>` | writer | Receipt committed. Exit 0 |
| `READ_RECORDED_UNPUSHED:<receipt-id>\|<path>\|<n-ids>` | writer | Receipt committed but not pushed. Other checkouts may show these notes again until the task data syncs. Exit 0 |
| `READ_NOOP:<task-id>` | writer | Every listed note was already acknowledged. Nothing written. Exit 0 |
| `READ_TARGET_MISSING:<id>` | writer | No task with that id. Exit 1 |
| `READ_ERROR:<reason>` | writer | No receipt was written. The notes are still unread and will surface again. Exit 1 |
| `READ_ERROR:rollback-failed:<receipt-id>` | writer | A failed commit could not be rolled back — the one outcome that needs a person to look at the task file. Exit 1 |

### Provenance

Every note's header line records where it was written, so a reader can check its claims against the exact tree they were made about:

| Field | Meaning |
|-------|---------|
| `from` | The sending task. **A claim**, not a proof |
| `from_verified=yes` | Written only when the sending session provably held the sender task's lock at write time — same host, same process, same start time. Otherwise the field is left out, never written as `no`: its absence means "not proven", never "disproved". It says nothing about the note's content |
| `at` | When the note was written, in UTC |
| `base` | The commit the sender's code checkout was on — a **full** object id |
| `base_branch` | The branch that commit was on |
| `base_mergebase` | The merge base with the repository's primary branch, recorded only when the sender was on a different branch |
| `dirty` | `yes` if the sender's working tree had uncommitted changes, `no` if it was clean |
| `host` | The machine the note was written on |

How `base` is captured, because it is the field a reader relies on most:

- It comes from the **code repository**, never from the task file's location. Task files live in a separate task-data worktree — `aitasks/` links into `.aitask-data` — so reading git state from there would record the wrong commit.
- It is captured **before** the note is appended and committed, so it describes the tree the sender was looking at.
- It is stored as a **full** object id. A short hash that is unique today can become ambiguous as the repository grows, which would break the one promise `base` makes, for exactly the oldest notes. Displays may abbreviate it; the stored value never is.
- Two sentinel values exist. `base=none` means there was no git repository at all; `dirty` is then `unknown`, the only case where it could not be measured. `base=unknown` means the repository exists but has no commits yet; `dirty` is still measured.

**What a `base` can and cannot date.** It dates claims about the tree — line numbers, file contents — because you can check out that commit and look. It does not date claims about a moment — a `git status` reading, a running process, a lock someone held a second ago. `dirty=yes` is the warning that a claim like that may already be stale.

### Migration

`--migrate` records a note that was written **before** the inbox existed — for example, context once passed between tasks by hand — keeping its original provenance instead of inventing new provenance.

| Option | Description |
|--------|-------------|
| `--migrate` | Use the migration path. `--from` is not allowed with it |
| `--claimed-from <ref>` | The original sender — a local task id, or a cross-repo `<project>#<id>` |
| `--claimed-at <date>` | The original note's own date: `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ` |
| `--base <oid>` | The commit the original note was written against — a full object id, or `none` / `unknown` |
| `--base-branch <branch>` | That commit's branch. Required with a real object id; not allowed with a sentinel |

A migrated note always records `migrated=yes`, and **never** records `from_verified`, `dirty` or `host`. None of them was observed when the original was written, and filling them in now would invent provenance.

---

**Next:** [Gates]({{< relref "/docs/commands/gates" >}})
