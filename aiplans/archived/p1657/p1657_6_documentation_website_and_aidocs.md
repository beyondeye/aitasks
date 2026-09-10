---
Task: t1657_6_documentation_website_and_aidocs.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_7_manual_verification_task_note_mailbox.md
Archived Sibling Plans: aiplans/archived/p1657/p1657_1_promote_ledger_block_substrate.md, aiplans/archived/p1657/p1657_2_inbox_format_and_ait_note_writer.md, aiplans/archived/p1657/p1657_3_read_receipts_and_pick_surfacing.md, aiplans/archived/p1657/p1657_4_live_endpoint_resolution_infrastructure.md, aiplans/archived/p1657/p1657_5_aitask_note_skill_and_discoverability.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-09 19:16
---

# p1657_6 — Documentation: website reference, workflow guide, aidocs contracts

## Context

t1657_1..t1657_5 shipped the task-note mailbox: an `## Inbox` section, the
`ait note` writer, read receipts and pick-time surfacing, live-endpoint
resolution, and the `/aitask-note` skill. **None of it is documented.** Today
`ait --help` advertises `note  Send a durable note to another task's inbox` and
`/aitask-note` is `user-invocable: true`, with zero reference pages behind
either — a runnable, discoverable surface with no documentation is the widest
exposure gap, which is why `commands/note.md` is written first.

This plan was re-verified against the shipped code on 2026-09-09. The original
was authored 2026-09-01, before t1657_4 and t1657_5 landed, and several of its
concrete claims no longer hold.

### What verification changed

| # | Finding | Effect on the plan |
|---|---|---|
| 1 | `workflows/_index.md` uses **bullet lists**, not tables (`- [Title](slug/) — Description.`). The old plan said "add its entry to the table". | Step 4 adds a bullet, not a row. |
| 2 | `/aitask-note` shipped as a user-invocable skill with **no** `skills/` page and no row in the two hand-maintained skill indexes. Flagged by a note from t1657_5 as a judgement call. | **User approved including it** — new Step 5. |
| 3 | `--with-live` (t1657_5) and the whole `--migrate` family exist; the old flags table listed neither. | Step 1's flags table covers both. |
| 4 | The adapter is `.aitask-scripts/live_delivery/claudecode.md`, **not** under `.claude/skills/`. `aitask_skill_render.sh` is a reachability dep-walker, so an unreferenced `.md` in a skill dir is never rendered. | Step 7 documents the real path and the reason. |
| 5 | The degradation table is **8 codes**, not 7: seven resolver-layer `LIVE_NONE` reasons plus adapter-layer `no_session_match`. Plus `LIVE_ERROR:resolver_unavailable`, minted by the *writer*, never the resolver. | Step 7 splits the table by layer and names who mints each code. |
| 6 | **The by-hand anchor check is superseded.** `website/check_links.py` resolves `#fragment` targets in generated HTML and reports `missing-anchor`; it handles minified unquoted `id=` (its own control case is "unquoted + relative + fragment"). The old plan said anchors "must be checked by hand, never inferred from the build exit code". | Verification runs the tool as the gate. |
| 7 | The stale "7-touchpoint checklist" count is **already fixed** — t1717 is archived and `aitasks_extension_points.md:335` now reads "5-touchpoint checklist" with a contract test. | Out of scope; touch nothing. |
| 8 | The v0.35.0 blog post's live-delivery sentence is **already conditioned** ("*if* an agent is holding the task live on your machine right now"). It is not the unconditional-delivery claim the task's verification bullet hunts for. | No edit; the grep records it as reviewed. |
| 9 | The CHANGELOG now covers all five shipped children, not two. | No changelog work needed. |

Follow `aidocs/framework/documentation_conventions.md` for the website pages:
**current-state only**, no version history, genericized agent-set prose. That
rule governs *user-facing* prose only — `aidocs/framework/` docs deliberately
carry decision history and rejected alternatives (see `task_premise_staleness.md`).

---

## Main steps

### 1. `website/content/docs/commands/note.md` (new)

Weight **37** is free, exactly between `lock.md` (36) and `gates.md` (38).
Match the house shape of `commands/lock.md`.

```yaml
---
title: "Note"
linkTitle: "Note"
weight: 37
description: "ait note command for sending durable advisory context to an existing task"
depth: [intermediate]
---
```

**The heading skeleton is fixed, because other pages link into it.** Use exactly
these headings, in this order — the anchors are consumed by Step 2 and Step 3,
so a different wording silently breaks those links until the link-check catches
it. Headings carry no punctuation, so the Hugo-generated anchor is a plain
lowercase-hyphenated slug with no guessing required:

| Heading | Anchor |
|---|---|
| `## ait note` | `#ait-note` |
| `### Sending a note` | `#sending-a-note` |
| `### Reading acknowledgement receipts` | `#reading-acknowledgement-receipts` |
| `### Output` | `#output` |
| `### Provenance` | `#provenance` |
| `### Migration` | `#migration` |

Under `## ait note`: intro, then a fenced `bash` usage block with aligned `#`
comments. `### Sending a note` and `### Reading acknowledgement receipts` each
carry **two tables** as `lock.md` does — `| Command | Description |` for the
invocation shape, then `| Option | Description |` for its flags (`--from`,
`--text`, `--file`, `--with-live`; and `--by`, `--ids`, `--mode`).
`### Migration` covers `--migrate`, `--claimed-from`, `--claimed-at`, `--base`,
`--base-branch`.

**`lock.md` documents exit codes in a dedicated `| Exit | Meaning |` table.
`ait note`'s analogue is the stdout contract**, because it exits only 0/1 — so
the page's centrepiece is `### Output`, with one table per lane. **Each table
names the layer that mints its codes** (writer / resolver / adapter) and carries
each code as a **backticked token in its own cell** — the same declared shape
Step 7's table uses, because that attribution and that shape are what the
post-phase guard compares against:

- durable: `NOTE_APPENDED:<note-id>|<path>`,
  `NOTE_APPENDED_UNCOMMITTED:<note-id>|<path>|<reason>`,
  `NOTE_TARGET_MISSING:<id>`, `NOTE_SELF:<id>`, `NOTE_ERROR:<reason>`;
- live (only with `--with-live`, and only after `NOTE_APPENDED:`):
  `LIVE_PANE:<%pane>|<session>:<@win>.<%pane>|<pid>|agent=<family>`,
  `LIVE_NONE:<reason>`, `LIVE_ERROR:<reason>`;
- `read`: `READ_RECORDED:<receipt-id>|<path>|<n-ids>`,
  `READ_RECORDED_UNPUSHED:`, `READ_NOOP:<task-id>`, `READ_TARGET_MISSING:<id>`,
  `READ_ERROR:<reason>`, `READ_ERROR:rollback-failed:<receipt-id>`.

Four contracts stated explicitly, because they are what a scripting user gets
wrong:

- **Exactly one line, always** — without `--with-live`. With it, a second line
  follows *only* after `NOTE_APPENDED:`; every other durable outcome
  short-circuits the live lane and still prints one line.
- **The durable result is authoritative, and the exit status follows it alone.**
  A `LIVE_NONE:` or `LIVE_ERROR:` after `NOTE_APPENDED:` is a **success with
  live delivery unavailable, exit 0** — never a partial failure, never a reason
  to resend. `NOTE_APPENDED_UNCOMMITTED:` is id-bearing and **terminal**: the
  note exists, so a retry duplicates it.
- **`base` provenance** — captured from the **code repo root** (`AIT_DIR`, else
  `$SCRIPT_DIR/..`), never the task-file path, because `aitasks/` is a symlink
  into `.aitask-data` and resolving there records the wrong sha. Captured
  **before** the append and commit. Stored as a **full** object id (`rev-parse
  HEAD`, never `--short`) — presentation may abbreviate, storage never does.
  Sentinels: `base=none` (no repository at all, forces `dirty=unknown`),
  `base=unknown` (repo exists, HEAD unresolvable on an unborn branch — `dirty`
  is still *measured*). `base_mergebase` appears only when HEAD's branch differs
  from the repo's discovered primary branch.
- **`from=` is a claim.** `from_verified=yes` is written only when the writing
  session provably held the *sender's* lock (host + pid + start-time token +
  token kind all matching). It is **never written as `no`** — absence means
  "not proven", never disproof. It proves nothing about the note's content, and
  nothing at read time.

Also document: body limit **8192 bytes**, NUL rejected, CR stripped; `--from`
accepts `349`/`t349`/`1657_2`/`t1657_2` but is **local-only** (a cross-repo
`proj#357` is rejected); `--by` must equal the target task id; `--mode` defaults
to `explicit`. And the read-side asymmetry, which is a deliberate design point:
**a note is kept on commit failure, a receipt is rolled back** — a note body is
irreplaceable and a retry would duplicate it, whereas receipt bookkeeping is
reconstructible and an uncommitted receipt would hide a note locally with
nothing durable to show for it. Hence there is no `READ_RECORDED_UNCOMMITTED`.

Ends with `**Next:** [Gates]({{< relref "/docs/commands/gates" >}})`.

### 2. `website/content/docs/commands/_index.md`

Two rows appended to the **Task Management** table, directly after the
`ait lock` row (its current last row). Table links use the relative
pretty-path form, not relref:

```markdown
| [`ait note`](note/) | Send durable advisory context to a task that already exists |
| [`ait note read`](note/#reading-acknowledgement-receipts) | Record a read receipt so acknowledged notes stop surfacing |
```

Plus two lines in the `## Usage Examples` bash block, matching its style.

**This index is hand-maintained — a page not listed here is effectively
invisible.**

### 3. Cross-links

- `commands/lock.md` — its `**Next:**` currently points at `issue-integration`,
  skipping weight 37/38. Retarget it to the new page and let `note.md` point on
  to `gates`, keeping the chain contiguous. Add one in-body sentence in the
  lock record's context noting that live-endpoint resolution reads the lock
  record (host, pid, start-time token), linking to `note/`.
- `website/content/docs/concepts/locks.md` — one sentence + link, same reason.

Prose/cross-section links use `{{< relref "/docs/..." >}}`; index tables and
bullet lists use relative slugs with a trailing slash. That split is the house
convention, and relref is what fails the build if a page moves.

### 4. `website/content/docs/workflows/task-notes.md` (new)

Weight **61**, placing it directly after `follow-up-tasks.md` (60), which is its
closest neighbour conceptually.

Covers: **note vs. spawn a task** (a note carries context about work that
already exists; if the content *is* work, create a task — a note never replaces
follow-up creation); both lanes (durable always, live opportunistic); the four
surfacing surfaces and their asymmetries; what happens when live delivery is
unavailable; and the trust posture.

The surfacing story is four surfaces, two of them deliberately asymmetric:

| Surface | Displays | Acknowledges |
|---|---|---|
| `aitask-pick` Step 0b | yes | yes (`explicit`, or `auto` when headless) |
| `task-workflow` Step 3 Check 6 (the universal route) | yes | yes |
| `aitask-pickrem` Step 2 | yes | yes, always `auto` |
| `aitask-pickweb` Step 2 | yes | **no, by decision** |

Two points to write up carefully rather than as gaps:

- **`pickweb` displays but never acknowledges.** Web mode makes no task-file
  writes and has no push access to the task-data branch, so a receipt there
  could neither be written without breaking that invariant nor ever become
  durable. Leaving the notes unread is the fail-safe direction — they surface
  again at the next attended pick. A duplicate display is the acceptable
  failure; a silently vanished note is not.
- **The candidate listing is read-only.** `aitask-pick` Step 2b shows an unread
  *count* only, never bodies, and never records a receipt — otherwise an agent
  that merely saw a task in a menu would hide that task's notes from whoever
  picked it later.

Plus: **displaying is not acknowledging** (two separate steps; displaying
changes no state), and `mode=auto` vs `explicit` exists so "no human read these"
stays auditable rather than invisible.

Bullet added to `workflows/_index.md` under `## Tasks`:

```markdown
- [Task Notes](task-notes/) — Send durable advisory context to a task that already exists, with opportunistic live delivery.
```

### 5. `/aitask-note` skill page (user-approved scope addition)

`website/content/docs/skills/aitask-note.md`, weight **46** (just after
`/aitask-wrap` at 45). Skill pages carry `maturity` in addition to `depth` —
both are real Hugo taxonomies:

```yaml
---
title: "/aitask-note"
linkTitle: "/aitask-note"
weight: 46
description: "Send a durable note to an existing aitask — context that task needs which is not itself work"
maturity: [stable]
depth: [intermediate]
---
```

Follow `aitask-wrap.md`'s skeleton: intro paragraph, `**Usage:**` block, the
run-from-project-root note, `## Step-by-Step`, `## Key Capabilities`,
`## When to Use` (comparison table against `/aitask-create` and
`/aitask-explore` — the note-vs-task call), `## Workflows` pointing at
`../../workflows/task-notes/`, `## Related`.

Content: the skill is **the single composition point** binding writer →
resolver → adapter, so callers invoke the skill and never the pieces. It
resolves the recipient when none is named, and carries the judgement calls the
raw CLI cannot: note vs. task, hedging what a SHA cannot date (a base commit
dates *tree-relative* claims like line numbers, but not *moment-relative* ones
like a `git status` reading), and the receiving posture. Mention the three
trigger points that offer it — `task-workflow` Step 8e, `aitask-qa` Step 6,
`aitask-review` Step 3 — all one-line **offers**, never automatic.

Two hand-maintained indexes, both currently clean in the working tree:

- `website/content/docs/skills/_index.md` — a row in the **Task Management**
  table (relative slug, backticked skill name, no trailing period).
- `docs/README.md` — a row in the skills block of its single table:
  `| [/aitask-note](../website/content/docs/skills/aitask-note.md) | `skills/aitask-note.md` | Send durable context to a task that already exists |`

`docs/README.md` carries two pre-existing broken paths (`skills/aitask-pick.md`,
now a directory; `workflows/terminal-setup.md`, now under `installation/`).
**Out of scope** — that file is not part of the Hugo build, so `check_links.py`
does not cover it. Report them at Step 8e rather than fixing them here.

### 6. `aidocs/framework/task_note_mailbox.md` (new)

Match the house style of `aidocs/framework/task_premise_staleness.md`: thesis-
style H1, an opening frame naming the originating task, a "Read together with:"
cross-reference block, then the design with its reasons and the evidence.

- **The `## Inbox` entry format** — `> **✉ note:t<sender>** id=… from=…
  [from_verified=yes] at=… base=… [base_branch=…] [base_mergebase=…] dirty=…
  host=…`, then a bare `>` separator, then `> | ` body lines, then a blank line.
  Key **order is the caller's contract**; the key *set* is validated and unknown
  keys are **rejected, not ignored**.
- **The `> | ` sentinel and why it exists — the injection surface, which is
  new.** Markers match `^>\s*\*\*`. A body line emitted as a plain
  `> **👁 note:read** … ids=…` would be a *syntactically valid receipt*, letting
  a note forge an acknowledgement of itself. The `| ` sits between the quote
  marker and the text so `^>\s*\*\*` can never match a body line, and it also
  neutralizes a literal `## Inbox` / `## Gate Runs` inside a body. **Sanitize at
  the write site, never the read site.** The gate ledger never needed this — its
  bodies are fixed labels.
- **The section-ordering invariant** — `## Inbox` must precede `## Gate Runs`,
  because both gate-append paths are EOF-anchored, so an Inbox placed after
  would silently swallow every future gate block: the ledger would keep
  "working" while its records landed inside someone's mailbox.
- **Receipts** — a separate block in the same section and namespace,
  discriminated by the reserved marker name `read` (a note's marker name must
  equal its sender `t<id>`, which can never be the bare word `read`). Receipts
  carry **no provenance** — bookkeeping, not a tree-relative claim. **Unread is
  derived, never stored**: a note is unread while its id appears in no valid
  receipt's `ids=`. That is set-union semantics — order-free, same-second-safe,
  merge-friendly, needing no frontmatter field. An invalid receipt is skipped,
  so a malformed receipt can never suppress a real note.
- **The merge contract** for concurrent cross-PC appends (identity `id`,
  order key `at`), and the two recorded decisions: a note consumed on one PC
  does not resurface on another (receipts are shared state, unioned across
  checkouts); and a commit failure **rolls a receipt back** while a note is
  **kept**.
- **The note-id scheme** — `<iso-utc>.<24-hex>`, 96 bits from a CSPRNG, minted
  inside the append lock and verified absent before writing. Uniqueness is
  *checked*, not merely improbable, because `ids=` is the association key: a
  collision makes a receipt acknowledge the wrong entry.
- **Why `base` stores a full object id** — `core.abbrev` is unset, so git
  auto-scales abbreviation to current repo size; a prefix frozen into a durable
  note keeps its width as the repository grows, breaking the exact-tree promise
  for exactly the oldest notes.
- **The trust posture**, and the known constraint that
  `aitask_update.sh --desc-file` replaces the body and would drop the section —
  a **pre-existing hazard `## Gate Runs` already shares**, not one introduced
  here.

### 7. `aidocs/framework/live_endpoint_resolution.md` (new)

**Its own document, because the boundary outlives notes.** The primitive is
"find the live agent implementing task X"; notes are only its first consumer.

- **Contract**: exactly one stdout line, always —
  `LIVE_PANE:…` exit 0, `LIVE_NONE:<reason>` exit 0, `LIVE_ERROR:<reason>` exit
  2. `LIVE_NONE` exits 0 because "there is no live endpoint" **is** a successful
  resolution; `LIVE_ERROR` is deliberately disjoint so "no endpoint" and "the
  resolver broke" can never be confused. Usage errors print help to **stderr**
  and still emit one stdout line; `-h`/`--help` is the single documented
  exception, because that invocation is addressed to a human.
- **The full degradation table, as a markdown table with a `Layer` column**
  (`resolver` / `adapter` / `writer`) and the code as a **backticked token in
  its own cell**. That shape is the contract the post-phase guard reads — it is
  declared here rather than left to the writer's taste, so the guard never has
  to infer intent from prose. Contents — resolver: `unlocked`,
  `remote_host`, `holder_dead`, `holder_unknown`, `agent_unknown`,
  `agent_unsupported:<family>`, `no_pane`; adapter: `no_session_match`. Plus
  `LIVE_ERROR:` = `usage`, `bad_task_id`, `task_not_found:<id>`, and
  `resolver_unavailable` — which the **writer** mints, never the resolver, when
  no parseable `LIVE_*` line comes back. Two rows carry reasons that are easy to
  get wrong: `holder_unknown` covers a legacy lock with **no `pid:` field at
  all** and is never collapsed into `holder_dead`; `agent_unknown` is the
  legitimate Step-4-lock → Step-7-attribution window, not an error.
- **Resolution order**, and the socket boundary stated honestly: only the
  gateway socket is searched, so an agent on another tmux server reads as
  `no_pane`.
- **The target string is `<session>:@<window_id>.<%pane>`, not window_index** —
  measured, pane `%2` renders as `aitasks:@2.%2` while its `window_index` is 3.
  The index produces a target that looks right and joins to nothing. The adapter
  joins on the **pane id alone**, treating the prefix as display context.
- **The generic/adapter split, and why the adapter is a procedure not a script**
  — `ListAgents`/`SendMessage` are model-facing tools with no CLI surface, so
  the pane↔session join can only happen agent-side.
- **How to add an adapter: a data change, not a code change.** One row in
  `.aitask-scripts/live_delivery/agents.txt` plus one procedure file beside it.
  The resolver holds no agent literal of its own. Three refusals worth stating,
  each a real check: column 2 is a **bare filename** resolved inside the
  delivery directory (a `/` or `..` is refused, not followed); the file must be
  a readable **regular** file (`-f` *and* `-r` — `-r` alone is true for a
  directory); and a row failing either yields `agent_unsupported`, **not**
  `LIVE_PANE`, because `LIVE_PANE` is a promise the caller acts on and breaking
  it one layer later leaves them with nothing to deliver through.
- **Current state**: `claudecode` is the only family that resolves. Codex and
  OpenCode are **absent by decision, not omission** — `codex queue` exists, but
  `codex agents` is an interactive TUI with no machine-readable listing, so
  nothing could map a session to a pane.
- **tmux is discovery, never transport** — `send-keys` injects into whatever UI
  state a pane happens to be in, carries no agent identity or message framing,
  and offers no queued/received semantics. Document it the way the test does:
  `tests/test_live_endpoint_no_sendkeys.sh` pins an **allowlist** of the tmux
  verbs the resolver may issue (`list-panes`), not merely "no send-keys".
- **The adapter's own output contract**, in a second table using the same
  declared shape (a `Layer` column, the code a backticked token in its own
  cell), so both codes the adapter mints are documented and machine-comparable
  rather than only the degradation one:
  `LIVE_QUEUED:<session>|<note-id>` and `LIVE_NONE:<reason>`.
  **`LIVE_QUEUED` means enqueued, never read** — `success: true` from the send
  means queued, so a note is never reported as delivered, received, or
  acknowledged. And `no_session_match` must be reported with what was searched
  for (the pane id, and how many listed rows carried a tmux column): a bare
  reason code is indistinguishable from "that session ended", and if no row
  carries the join key at all, the listing's rendering has changed — a
  framework bug, not a dead session.
- **Ordering is the composition's property, not the resolver's.** The resolver
  neither appends notes nor calls `SendMessage`, so durable-first ordering is
  owned by `/aitask-note` (t1657_5) and pinned by
  `tests/test_note_with_live_composition.sh`.

### Post-phase (risk mitigations)

**`note_doc_contract_drift_guard`** — runs after steps 1–7, before Verification.

Add `tests/test_note_doc_contract.sh` asserting that the structured output codes
documented in the new pages agree with the shipped sources — the two `--help`
texts **and** the adapter procedures — **in both directions**: a code documented
but no longer emitted, and a code emitted but undocumented. Precedent:
`tests/test_touchpoint_count_contract.sh`, which pins a doc's count the same way.

- **Three sources of truth, one per layer** (read them, never hardcode a copy).
  Two `--help` texts alone would leave the adapter layer unguarded: the
  documented degradation table includes `LIVE_NONE:no_session_match`, which no
  `--help` emits, so a flat exemption for it would let the adapter change while
  the guard stayed green and the table went wrong — the whole failure this guard
  exists to prevent.

  | Layer | Source | Codes it owns |
  |---|---|---|
  | writer | `./.aitask-scripts/aitask_note.sh --help` | `NOTE_*`, `READ_*`, and `LIVE_ERROR:resolver_unavailable` |
  | resolver | `./.aitask-scripts/aitask_live_endpoint.sh --help` | the seven resolver-layer `LIVE_NONE` reasons, and `LIVE_ERROR:` `usage` / `bad_task_id` / `task_not_found` |
  | adapter | every procedure named in `.aitask-scripts/live_delivery/agents.txt` (today `claudecode.md`) | `LIVE_QUEUED`, `LIVE_NONE:no_session_match` |

  **Ownership is exclusive, and restatement is not ownership.** Each token
  belongs to exactly one layer — the one that *mints* it. `aitask_note.sh
  --help` restates the seven resolver `LIVE_NONE` reasons as a convenience for
  its readers; those restatements are **resolver-owned**, so the writer's
  extraction must not claim them or the per-layer equality double-counts and
  fails spuriously. Extract the writer's set from its `NOTE_*` / `READ_*` /
  `read:` output blocks plus the one reason it mints, not from every `LIVE_`
  string in the file.

  **Iterate the manifest, do not hardcode `claudecode.md`** — the manifest is
  what decides which adapters exist, and `tests/test_live_endpoint_no_sendkeys.sh`
  already walks `agents.txt` the same way (it greps each adapter for
  `no_session_match`). Reuse that walk rather than writing a second one.
- **The checked set is a rule, not a list.** Enumerating "which codes to
  compare" is what lets coverage drift out of step with the promise — state it
  once, as a **set equality per layer**, and let the sources decide the members:

  > For each layer L in {writer, resolver, adapter}, let `source(L)` be the
  > token set extracted from L's source, and `docs(L)` the token set the pages
  > attribute to L. Assert **`source(L) == docs(L)`** — an extra on either side
  > fails, naming the layer and the token.

  `docs(L)` is the union across **both** pages, so a token documented on either
  `commands/note.md` or `aidocs/framework/live_endpoint_resolution.md` counts
  as documented, and neither page has to carry codes that do not belong on it.
  This is what makes `resolver_unavailable` — writer-minted, but detailed in the
  aidocs degradation table — compared rather than skipped, without special-casing
  it.

- **Compare at the reason-token level, not the code prefix.** `LIVE_ERROR` as a
  bare prefix is not a member; `LIVE_ERROR:usage`, `LIVE_ERROR:bad_task_id`,
  `LIVE_ERROR:task_not_found` and `LIVE_ERROR:resolver_unavailable` are. The
  same for `LIVE_NONE:<reason>` and `agent_unsupported:<family>` — compare the
  reason, treating a `:<placeholder>` suffix as part of the token's shape rather
  than a distinct member. A prefix-level comparison is exactly what would let a
  renamed reason pass.
- **Extract against a declared format, do not parse prose for intent.** The
  pages must carry each code as a backticked token in a table cell; the guard
  greps for that fixed shape only. A bespoke parser guessing at meaning produces
  false positives that break unrelated doc edits — so the *format* is the
  contract, and the page states it in an HTML comment at the table.
- **Prove both directions on every layer — six mutants, not two.** The equality
  is asserted per layer, so a guard that only works for one layer looks
  identical to one that works for all three. Build the guard uncommitted and
  watch each half go red before committing guard and pages together: for each of
  writer / resolver / adapter, (a) remove that layer's token from the page and
  (b) add a fake token to a stub source for that layer. Both must fail, naming
  the layer. The adapter rows matter most — that layer was unguarded in two
  earlier drafts of this plan precisely because nothing forced it to fail.
  Route each mutant through the real entry point (`bash
  tests/test_note_doc_contract.sh`), and confirm the mutation actually landed
  before trusting a red.
- **State what the guard does not buy**, in the test header, so nobody reads it
  as broader than it is. It compares **reason-token sets, per layer**, so it
  catches a token added, removed or renamed in any of the three layers, and a
  token documented under the wrong layer. It does **not** verify
  that the surrounding prose describes each code correctly, that exit statuses
  are right, or that the `LIVE_PANE` field layout still matches — those stay
  covered by Verification step 6 (re-reading `--help`) and by the behavioural
  suites `tests/test_live_endpoint_degradation.sh` and
  `tests/test_note_with_live_composition.sh`.
- Follow `tests/lib/asserts.sh` conventions; if any test body runs inside a
  `( … )` subshell, opt into the file-backed counters
  (`assert_counters_init` / `assert_counters_load`), or the file reports zero
  failures and exits 0 no matter what failed.

---

## Verification

1. `cd website && hugo build --gc --minify` builds clean.
2. `cd website && python3 check_links.py --build` exits 0. **This is the gate
   for anchors too** — it resolves every same-site link in the *generated* HTML,
   validates `#fragment` targets against real element ids (reporting
   `missing-anchor`), and copes with `--minify`'s unquoted `id=`. It renders
   into a private temp dir, so it never touches the gitignored `website/public/`.
   CI runs the same check after the release build, so a dead link blocks deploy.
3. `cd website && python3 check_link_relevance.py` — the advisory report
   (user-approved). It never fails the build; triage its hits for this change's
   new links and fix any genuinely off-target one.
4. The new pages appear in the rendered nav via their `_index.md` entries, and
   the `lock → note → gates` Next chain is contiguous.
5. No stale claim survives: grep `website/content/` for any statement that live
   delivery is unconditional, or that a note is anything other than advisory.
   Record the v0.35.0 blog sentence as **reviewed and already conditioned** —
   the only pre-existing prose on the subject.
6. Spot-check the reference page against the source of truth rather than from
   memory: `./ait note --help` and `./.aitask-scripts/aitask_live_endpoint.sh
   --help` are the authoritative texts for Steps 1 and 7.
7. `bash tests/test_note_doc_contract.sh` passes (the inline post-phase guard),
   and each of its two directions was observed failing before the pages were
   committed.

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9. At Step 8e, report the
two pre-existing broken paths in `docs/README.md` to their owning task rather
than fixing them here.

## Risk

*(Reassessed after the inline post-phase was confirmed — the plan is no longer
docs-only: it now ships one test file.)*

### Code-health risk: **low**

- The inlined guard is a new, self-contained test file that touches no runtime
  surface and no existing test. A bespoke doc-scanner could produce false
  positives that break unrelated doc edits · severity: low · → mitigation:
  inline post-phase `note_doc_contract_drift_guard`, which pins a **declared
  format** (a backticked token in a table cell) rather than parsing prose for
  intent, and states its exemptions explicitly.
- Otherwise additive: 7 new/edited content files plus 4 hand-maintained
  indexes. The only edits to existing prose are two cross-link sentences and
  one retargeted `**Next:**`.

### Goal-achievement risk: **medium**

- **Documenting a contract wrongly is worse than not documenting it** — a reader
  scripting against `ait note` would act on it · severity: medium · →
  mitigation: inline post-phase `note_doc_contract_drift_guard`, plus every
  contract in Steps 1 and 7 being transcribed from the shipped `--help` text and
  Verification step 6 re-checking the pages against those two commands rather
  than against this plan.
- Residual: a dead anchor or an internal link to a real-but-unrelated page ·
  severity: low · → mitigation: Verification steps 2 and 3 — `check_links.py` is
  the hard gate (it covers fragments, which the task body assumed it did not),
  `check_link_relevance.py` the advisory pass.
- Residual: the four hand-maintained indexes are the one place a new page can
  land and stay invisible · severity: low · → mitigation: Verification step 4
  checks the rendered nav, not just the file edits.

### Planned mitigations
- timing: post-phase | name: note_doc_contract_drift_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: goal-achievement — a documented contract drifting from the shipped one | desc: contract test asserting per-layer set equality between the documented reason tokens and the three shipped sources (both --help texts plus the adapter procedures named in agents.txt), in both directions

## Implementation Notes

Deviations from the approved plan, recorded as they land:

1. **Guard sources, resolver layer.** The resolver's `--help` enumerates its
   seven `LIVE_NONE` reasons but none of its `LIVE_ERROR` reasons (`usage`,
   `bad_task_id`, `task_not_found`); those exist only at the resolver's emission
   sites. Extracting from `--help` alone would leave three documented tokens
   outside the comparison — the same gap the review rounds closed for the
   adapter. The guard therefore reads the resolver's **emission sites** (its
   `echo "LIVE_…"` / `printf 'LIVE_PANE:…'` lines), which are the minting truth.
   The writer layer reads the `Output` block of its `show_help` heredoc
   (`NOTE_*` / `READ_*` lines) plus the concrete `LIVE_` reasons it assigns
   outside comments (`resolver_unavailable`). The
   adapter layer reads each manifest-named procedure, scoped to `LIVE_QUEUED`
   and concrete `LIVE_NONE` reasons. Each extraction greps only for the code
   families its layer mints — which is how "restatement is not ownership" is
   made concrete.
2. **`commands/lock.md` record example.** The lock-file YAML example showed only
   `task_id` / `locked_by` / `locked_at` / `hostname`. A session lock also
   carries `pid`, `pid_starttime` and `pid_starttime_kind`, and the new
   cross-link sentence refers to them, so the example gained those fields plus
   one sentence on when they are absent.
3. **`concepts/locks.md` cross-link** landed as a `## See also` bullet — the
   page's established cross-link spot — rather than an in-body sentence.
4. **Link form in new pages.** Every cross-page link in the new website pages
   uses `{{< relref >}}` (build-enforced, per `documentation_conventions.md`),
   including links inside content tables. Relative slugs remain only in the
   hand-maintained `_index.md` tables and lists, matching their existing rows.
5. **Mutant directions.** The plan's two mutants per layer — delete a documented
   token, add a fake token to a stub source — both redden the *same* direction
   ("minted but not documented"), leaving "documented but not minted" never
   exercised. Implemented as one mutant per direction per layer instead:
   (a) delete a documented row from a page copy → *minted but not documented*;
   (b) delete a minted token from a source-stub copy → *documented but not
   minted*. Still six mutants, now covering both directions on every layer.
6. **Manifest walk mirrored, not shared.** `test_live_endpoint_no_sendkeys.sh`
   walks `agents.txt` inline. The guard mirrors that exact expression and cites
   it, rather than refactoring the other test into a shared helper — which would
   widen this docs task into an unrelated test file.

7. **`docs/README.md` defects routed through Step 8b, not a Step 8e note.** The
   plan said to report its pre-existing broken paths via Step 8e. No existing
   task owns that file, so a note would have no recipient; they are listed
   under "Upstream defects identified" below, which is what Step 8b reads.

## Final Implementation Notes

- **Actual work done:** All seven plan steps and the inline post-phase landed.
  New: `website/content/docs/commands/note.md` (CLI reference with the fixed
  heading/anchor skeleton), `website/content/docs/workflows/task-notes.md`,
  `website/content/docs/skills/aitask-note.md` (the user-approved scope
  addition), `aidocs/framework/task_note_mailbox.md`,
  `aidocs/framework/live_endpoint_resolution.md`, and
  `tests/test_note_doc_contract.sh`. Edited: `commands/_index.md` (two Task
  Management rows, two usage lines), `workflows/_index.md` (bullet),
  `skills/_index.md` (row), `docs/README.md` (row), `concepts/locks.md`
  (see-also), `commands/lock.md` (lock-record fields, cross-link, `**Next:**`
  retargeted to note).
- **Deviations from plan:** the seven numbered Implementation Notes above —
  resolver guard source is its emission sites; `lock.md` record example gained
  the `pid` fields; `concepts/locks.md` link as a see-also bullet; relref for
  every link in the new pages; one mutant per direction per layer; manifest walk
  mirrored rather than shared; `docs/README.md` defects routed through Step 8b.
- **Issues encountered:**
  - The stale-claim grep (Verification step 5) caught three sentences in this
    task's **own** new pages stating live delivery unconditionally —
    "delivered to that session straight away", "delivers it live when an agent
    is working on that task", "it delivers the note … and reports
    `LIVE_QUEUED:`". Each dropped the runtime-support condition and said
    *delivered* where the contract is *queued*. All three fixed; the re-grep is
    clean. The class is easy to reintroduce: prose describing the happy path
    drifts toward the unconditional.
  - The resolver's `--help` lists its `LIVE_NONE` reasons but none of its
    `LIVE_ERROR` reasons — found while building the guard (deviation 1).
  - Three plan-review rounds each found the guard's checked set narrower than
    its claimed coverage (the adapter layer, then `LIVE_QUEUED`, then the
    writer-minted `resolver_unavailable`). Resolved structurally, by stating the
    checked set as a per-layer set-equality rule instead of an enumerated list,
    rather than by patching a third instance.
- **Key decisions:** the guard compares reason-token sets per layer, with
  exclusive ownership (restatement is not ownership); the docs format is a
  declared `| Code | Layer | Meaning |` row shape announced by an HTML comment,
  never prose parsing; a probe guard aborts on any empty side so the equality
  cannot pass vacuously. The v0.35.0 blog post is left as-is: its sentence is
  conditioned on locality, though it still says "delivered" and omits that live
  delivery is Claude-Code-only — it is a dated release announcement.
- **Verification results:** `hugo build --gc --minify` clean (248 pages);
  `check_links.py --build` 0 broken, `SWEEP: PASSED` (covers anchors);
  `check_link_relevance.py` no hits in any touched file; the three new pages are
  linked from their section indexes; the `lock → note → gates` Next chain is
  contiguous; the guard passes 7/7; the probe control aborts on an empty source;
  all six mutants go red with the exact expected fail count, assertion and token
  (both directions × three layers); `shellcheck -x` clean.
- **Upstream defects identified:**
  - `docs/README.md:30 — links skills/aitask-pick.md, which is now the directory skills/aitask-pick/_index.md`
  - `docs/README.md:26 — links workflows/terminal-setup.md, which now lives under installation/terminal-setup`
  - `docs/README.md:43-47 — the commands block omits most command pages (lock, gates, sync, explain, codeagent, crew, pr-import, note)`
- **Notes for sibling tasks:** for t1657_7 (manual verification) — the output
  codes its checklist exercises are now documented in
  `website/content/docs/commands/note.md#output`, and the full per-layer
  degradation table in `aidocs/framework/live_endpoint_resolution.md`.
  `tests/test_note_doc_contract.sh` fails if a documented code drifts from the
  shipped writer, resolver or adapter. The `| Code | Layer | Meaning |` row
  shape in those two pages **is** the guard's contract: changing a row's shape,
  not just its text, breaks it.
- **Follow-ups spawned at review:** t1782 (`fix_docs_readme_stale_links`,
  `bug`, `followup_kind: upstream_defect`) carries the three `docs/README.md`
  defects above. An advisory note
  (`2026-09-10T09:45:20Z.fa0102514dce66684a98233f`, `from_verified=yes`) went to
  t1657_7, pointing it at the stale parent-plan lines (76-77, 341, 492) and at the
  pages that document the outputs its checklist verifies. Live delivery was
  `LIVE_NONE:unlocked`, so it surfaces when t1657_7 is picked.
- **Step 9 gate dispatch in current-branch mode:** Step 7's `should-self-record`
  deferred `risk_evaluated` to "the Step-9 orchestrator", but Step 9 invokes
  `ait gates run` only inside its separate-branch (merge) block. On this
  current-branch task it was run explicitly, with Step 9's own capture block,
  before archival — `risk_evaluated: pass`, `archive-ready` → `ALL_PASS` —
  rather than letting the archiver refuse on `GATE_PENDING` first.
