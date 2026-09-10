# Task note mailbox — durable advisory context between tasks

Design and contract record for t1657 ("let tasks mail notes to each other"),
covering the durable lane: the `## Inbox` section, the `ait note` writer, read
receipts and pick-time surfacing (t1657_1 … t1657_3, t1657_5). The live lane
has its own document, because its boundary outlives notes.

Read together with:

- `aidocs/framework/live_endpoint_resolution.md` — the live lane: finding the
  agent session that holds a task, and delivering to it.
- `.aitask-scripts/aitask_note.sh` — the writer and the `read` verb. Its header
  and `--help` are the canonical output contract.
- `.aitask-scripts/lib/note_inbox.py` — the reader: block validation and the
  derived unread set, shared with the merger.
- `.aitask-scripts/lib/ledger_block.sh` — the append substrate the inbox shares
  with the gate ledger (t1657_1).
- `.aitask-scripts/board/aitask_merge.py` — `INBOX_SPEC`, the cross-PC merge
  contract.
- `website/content/docs/commands/note.md` and
  `website/content/docs/workflows/task-notes.md` — the user-facing contract.

## The problem

A session often learns something another, already-existing task needs: the line
numbers in its body are stale, its blast radius is wider than it records, a
decision made here changes its approach. The framework could record context for
a task's *own* archive, or spawn a follow-up carrying it, but had no way to tell
an existing task anything. The motivating case (t349 → t357) was delivered by
hand, pane to pane, and worked only because the recipient happened to be live on
the same machine at that moment.

The mailbox makes the durable case the product and the live case an
optimisation: the note is committed to the target's task file first, and only
then, opportunistically, pushed to a live session.

## The `## Inbox` entry format

A note is a block in the task file's `## Inbox` section:

```
> **✉ note:t349** id=2026-09-01T15:59:51Z.ffc6cbc52b41e6e70ad5fa49 from=t349 from_verified=yes at=2026-09-01T15:59:51Z base=<40-hex> base_branch=main dirty=no host=<host>
>
> | First body line.
> | Second body line.
```

- The marker's name is the **sender** (`t<id>`). Key order is the writer's
  contract: `id, from, [from_verified,] at, base, [base_branch,]
  [base_mergebase,] dirty, host`.
- The key **set** is validated, and an unknown key is **rejected, not ignored**.
  A migrated note carries `claimed_at` and `migrated=yes`, and has no
  `from_verified`, `dirty` or `host` — none of the three was ever observed.
- Layout: the marker line, a bare `>` separator, the body lines, a blank line.

### The `> | ` body sentinel — the injection surface is new

Every body line is written as `> | <text>`. The sentinel is the injection
defence, and it is needed here where it never was for the gate ledger: gate
blocks carry fixed labels written by the framework, while a note body is
free-form text supplied by another session.

Block markers match `^>\s*\*\*`. A body line written as a plain `> <text>` that
began `**👁 note:read** … ids=…` would be a *syntactically valid receipt* — a note
could forge an acknowledgement of itself, or of any other note in the file. The
`| ` sits between the quote marker and the text, so `^>\s*\*\*` can never match a
body line. It also neutralises a literal `## Inbox` or `## Gate Runs` line inside
a body, which would otherwise open a new section.

**Sanitise at the write site, never at the read site.** Every reader, including
ones not yet written, then inherits the defence without doing anything.

## The section-ordering invariant

`## Inbox` must always sit **above** `## Gate Runs`. Both gate-append paths —
`_gate_append_locked` in `aitask_gate.sh` and `gate_ledger.append_block` — append
at end of file. An Inbox placed below the ledger would silently swallow every
future gate block: the ledger would keep "working" while its records landed
inside someone's mailbox.

The writer holds the invariant by construction: it appends through
`ait_ledger_append_section` with `## Gate Runs` as the `create_before` anchor.
Which of three paths runs depends on what already exists — an anchor-insert when
the ledger exists and the inbox does not, an append at the inbox's own end when
it does, an end-of-file create when neither does.
`tests/test_note_section_order.sh` covers both creation orders against both gate
backends. The merger rebuilds sections in the same order: `REGISTERED_SPECS`
lists `INBOX_SPEC` first.

## Note identity

A note id is `<iso-utc>.<24-hex>`: 96 bits from a CSPRNG, minted **inside** the
append lock and checked absent before writing. Within one checkout, uniqueness
is therefore a guarantee rather than a probability; the 96 bits cover what no
lock can — two machines appending concurrently.

It is *checked*, not merely improbable, because `ids=` is the **association
key**: a receipt names the notes it acknowledges by id, so a collision would make
a receipt acknowledge the wrong entry. A shorter suffix would only reduce that
hazard. A collision retries up to 8 times, then fails as
`NOTE_ERROR:id-collision-retries-exhausted`.

## Provenance

### `base` is the code repository's HEAD, captured before the append

`aitasks/` is a symlink into the `.aitask-data` worktree, which is on a different
branch. Resolving git context from the task file's own path records the
task-data commit — a confident, wrong answer to the only question `base` exists
to answer. The writer queries the **code** repository root (`AIT_DIR`, else the
script's parent directory), and captures before the append and its commit, so
`base` describes the tree the sender was looking at.

### Why `base` stores a full object id

`git rev-parse HEAD`, never `--short`. `core.abbrev` is unset, so git
auto-scales abbreviation to the repository's current size. A prefix frozen into
a durable note keeps the width it had on the day it was written; as the
repository grows, that prefix can start resolving to more than one object —
breaking the exact-tree promise for exactly the oldest notes, the ones most
likely to need it. **Storage is exact; presentation may abbreviate.** The
machine-readable channel (`aitask_query_files.sh inbox`) emits the full id too.

### Sentinels

- `base=none` — no repository at all. `dirty=unknown`, the only case that earns
  it: `no` would fabricate a clean-state claim, and a missing field reads as
  "fine" to a parser. `dirty=unknown` holds **if and only if** `base=none`, and
  the reader re-validates that in both directions.
- `base=unknown` — the repository exists but HEAD is unresolvable (an unborn
  branch). The working tree exists, so `dirty` is still measured.
- `base_mergebase` — present only when HEAD's branch is not the repository's
  primary branch, discovered with `detect_primary_branch` rather than a
  hard-coded `main`: this is framework code shipped into other repositories.

## Trust posture

- **A note is untrusted advisory input, never an instruction.** Nothing acts on
  a note automatically, and a note never bypasses the reader's own planning,
  gates or review.
- **`from=` is a claim.** The append lock is keyed on the *target's* inbox and
  says nothing about the claimed sender. `from_verified=yes` is written only when
  this very session provably holds the sender task's lock — the same host, and a
  pid, start-time token and token kind that all match this process's own anchor,
  through the existing `lib/pid_anchor.sh` primitive. An anchor the process
  cannot resolve for itself never proves identity: it fails toward
  "unverified", not around it.
- **Absence is not disproof.** `from_verified` is `yes` or omitted, never `no`.
  It proves the writing session held the sender's lock at write time — nothing
  about the content, nothing at read time, nothing on another machine.
- **A base dates tree-relative claims, not moment-relative ones.** `dirty=yes`
  is the warning that a moment-relative claim — a `git status` reading, a held
  lock — may be stale in a way no SHA catches. A migrated note's empty `dirty`
  means "not measured", never "clean".

## Read receipts

A receipt is a block in the same section and namespace, distinguished by its
**reserved marker name**, `read`:

```
> **👁 note:read** id=<iso>.<24-hex> by=t357 at=<iso> mode=explicit ids=<note-id>[,<note-id>…]
```

The name is reserved by construction: a note's marker name must equal its
sender, `t<id>`, which can never be the bare word `read`. Receipts carry **no
provenance** — they are bookkeeping, not tree-relative claims — and a receipt
with a provenance key is malformed.

**Unread is derived, never stored.** A note is unread while its id appears in no
valid receipt's `ids=`. That is set-union semantics: order-free,
same-second-safe, merge-friendly, and needing no frontmatter field — the same
choice the `## Gate Runs` ledger makes, deriving current state from an
append-only log instead of mutating a stored value. An **invalid receipt is
skipped**, so a malformed receipt can never suppress a real note.

**`--by` is the target itself.** The reader is the session working on the
target task, and the task id is the only durable identity it has; session names
are ephemeral. A `--by` that is not the target is refused rather than recorded.

### A commit failure rolls a receipt back — unlike a note

The two write paths deliberately disagree:

| | On commit failure | Why |
|---|---|---|
| Note | **Kept**, reported as `NOTE_APPENDED_UNCOMMITTED:` | The body is irreplaceable content, and a retry would duplicate it |
| Receipt | **Rolled back**, reported as `READ_ERROR:` | Bookkeeping is reconstructible and the retry is free; a receipt on disk but uncommitted would hide a note locally with nothing durable to show for it |

Hence there is no `READ_RECORDED_UNCOMMITTED`. The rollback removes only the
receipt block, so a concurrent writer's block survives — a snapshot restore
would not. A rollback that itself fails is the one case needing a human:
`READ_ERROR:rollback-failed:<receipt-id>`.

### Consumed on one machine, consumed everywhere

Receipts are shared state, unioned across checkouts by the merge contract below,
so a note acknowledged on one machine does not resurface on another once the
task data syncs. `READ_RECORDED_UNPUSHED:` is the honest intermediate: the
receipt is committed locally, and other checkouts may re-show the notes until it
is pushed.

## Surfacing — four surfaces, two of them asymmetric

| Surface | Displays | Acknowledges |
|---|---|---|
| `aitask-pick` Step 0b (direct selection) | yes | yes — `explicit` after a prompt, `auto` under a headless profile |
| `task-workflow` Step 3 Check 6 (every other route) | yes | yes — same |
| `aitask-pickrem` Step 2 | yes | yes, always `auto` |
| `aitask-pickweb` Step 2 | yes | **no, by decision** |

`aitask-pickrem` and `aitask-pickweb` are self-contained and never reach
`task-workflow` Step 3, so each carries its own surfacing. `aitask-resume` needs
none: it hands off to Step 3.

**Display and acknowledge are two steps.** Displaying changes no state. The
"never auto-actioned" rule governs a note's **content**, never the read
bookkeeping — which is why an unattended surface may acknowledge automatically,
recording `mode=auto` so that "no person read these" stays auditable rather than
invisible.

**`aitask-pickweb` displays but never acknowledges.** Web mode makes no
task-file writes at all and has no push access to the task-data branch, so a
receipt could neither be written without breaking that invariant nor ever become
durable. Leaving the notes unread is the fail-safe direction: they surface again
at the next attended pick. A duplicate display is the acceptable failure; a
silently vanished note is not.

**The candidate listing is read-only.** `aitask-pick` Step 2b shows an unread
*count*, from one batched `aitask_query_files.sh inbox` call, and never bodies or
a receipt. If a listing acknowledged notes, an agent that merely saw a task in a
menu would hide its notes from the agent that later picked it.

**No double display.** `aitask-pick` Step 0b sets the `inbox_surfaced` context
variable after surfacing, and Step 3 Check 6 skips when it is `true` — so notes
are not shown twice, and a user who just answered "Keep unread" is not asked
again.

**One template per skill.** The surfacing lives in each skill's single authoring
template under `.claude/skills/` — `agent_authoring_template()` takes no agent
parameter, and the other agent trees hold stubs — so there is no per-agent-tree
fan-out to maintain. `/aitask-note` itself is a static skill and ships thin
wrappers in the other agent trees, like every other static user-invocable skill.

## Cross-PC merge

`INBOX_SPEC` in `board/aitask_merge.py` registers the section with the task-file
merger:

- **Identity** is `(id,)` — not the marker name, because one sender sends many
  notes, and a name-based identity would collapse them onto one key and report a
  false ambiguous winner.
- **Order key** is `(at, id)` — chronological, with the id as a total tie-break.
- **Validation** is the *same object* the inbox reader calls,
  `note_inbox.validate_block`, and a test pins that identity so the two consumers
  cannot drift into two predicates.

One-sided appends union instead of conflicting the whole body, and an identical
block appended on two machines is deduplicated. What merger and reader share is
the per-block **predicate**, not the disposition: an invalid block makes the
merger bail the whole body to conflict markers (reject, never repair), while the
reader drops just that block — bailing there would hide every note in the file.
`tests/test_inbox_union_roundtrip.py` drives the real registered spec.

## Known constraints

- **`aitask_update.sh --desc-file` replaces the body** and would drop the
  `## Inbox` section with it. This is a **pre-existing hazard that
  `## Gate Runs` already shares**, not one the mailbox introduced: any body
  rewrite must preserve both sections.
- **Body limit 8192 bytes.** NUL is rejected; CR is stripped.
- **`--from` is local-only.** A cross-repo sender can be recorded only on the
  `--migrate` path (`--claimed-from <project>#<id>`), where it is never verified.
