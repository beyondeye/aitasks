---
Task: t2335_1_store_direction_records_format_4.md
Parent Task: aitasks/t2335_sitrep_work_directions.md
Sibling Tasks: aitasks/t2335/t2335_2_refresh_direction_freshness.md, aitasks/t2335/t2335_3_trails_highlight_and_critical_path_overlay.md, aitasks/t2335/t2335_4_skill_directions_code.md, aitasks/t2335/t2335_5_tui_directions_tab.md, aitasks/t2335/t2335_6_manual_verification_work_directions.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2335_1: sitrep store, direction records, format 4

## Context

The sitrep store groups items only by a free `theme` slug with situation text. The parent task (t2335) promotes that theme to a first-class **direction** record (title, rank, trails, next step, summary, digest, freshness). This child is the store layer: the format-4 grammar of `todo.md`, the writer verbs, the membership read, and the "theme" to "direction" rename. Children 2 (refresh), 4 (skill `>d`) and 5 (TUI tab) build on the record contract defined here.

Context files: parent `aitasks/t2335_sitrep_work_directions.md`; pending siblings `aitasks/t2335/t2335_{2,3,4,5,6}_*.md`; no archived sibling plans yet.

## Decisions confirmed with the user (2026-11-24)

1. **Digest is a baseline written with the summary.** `direction-set` records `digest` together with `summary`. `direction-freshness --batch` writes only `freshness`, `checked_at` and `drift`. This follows t2335_2's wording and deviates from the t2335_1 text, which listed `digest` among the refresh-written fields.
2. **This child does the whole wording rename**: skill template, goldens, website pages, TUI label and aidocs say "direction". Children 4 and 5 only add `>d` and the tab.
3. **`crashed-agents` is a derived direction**: reserved slug, members derived on read, may carry a record and a rank. New context input may not name it.

## Review concerns (all five verified against the code, all addressed)

| Concern | Verified how | Addressed in |
|---|---|---|
| Old writer's `restore` can roll format 4 back | `cmd_restore` at the base commit: `--if-damaged` treats any file its parser rejects as damaged, then installs a `.bak` that verifies. After the first migrating write the `.bak` is format 3, so it verifies. The TUI runs its own checkout's writer (`model.SCRIPTS_DIR`), so a TUI in an older worktree reaches this | "Mixed-version safety" |
| A refresh can publish `current` over changed store inputs | The direction rev covers the block only; membership and member state live in items | "Freshness guard" |
| Opaque digest cannot support specific drift reasons | A hash names no baseline members, statuses or trail versions | "Baseline evidence" |
| `direction-rank` silently clears a rank added meanwhile | Adding B at rank 2 leaves A's rev unchanged | `--expect-ranked` |
| Dry run expected only line 2 to differ | The live store has no theme blocks or keys, so it never exercises the migration of those | "Migration check" |
| Summary and baseline can come from different reads | t2335_4: "the summary is written together with the digest read at that moment", after the confirmation. A task closing in between leaves prose saying open and a baseline saying closed | "Summary evidence rule" |
| A truncated or replaced baseline passes a presence check | The plan only tested that the file exists | "Baseline evidence", integrity |
| A large direction can never save a summary | `retain` refuses more than 64 KiB (`MAX_RETAIN_BYTES`); a direction has no member limit | "Baseline evidence", size |
| Assignments commit before a check that can still refuse; `upsert-context` has no rev guard | `cmd_upsert_context` takes exactly one argument and the core parser gives it no `--expect-rev` | "Proposal save sequence", `direction-assign` |
| "Split the direction" is no recovery for `crashed-agents` | Its members are derived and the skill may not reassign recovery items. Closed members also pile up in every direction, because items are never deleted | "Baseline evidence", size |
| More causes than the reason limit | The grammar put one member id per reason; 17 closures did not fit in 16 | drift grammar, `aggregate_drift` |
| `direction-assign` refused items with no context | `op_add` takes the context only when given (`… if args.input else None`), so contextless items are valid, and they are exactly the unassigned items `>d` must group | `direction-assign`, minimal context |
| A legal long trail handle breaks a drift line | `artifact_manifest.HANDLE_RE` allows 132 characters; the sample key stopped at 60 | drift grammar, key limit and omission |

## Format 4 grammar

A direction block in Part 1, under `### Situation`. Blocks render sorted by slug. Every block has the heading plus exactly nine header lines in this order, then the situation text (may be empty), then one blank line.

```
#### sitrep | rev=14
- title: Sitrep work directions
- rank: 1
- trails: art:trail-sitrep-1, art:trail-x
- next: t2335_2
- summary: Store format landed; skill and TUI children open.
- digest: 0123456789abcdef
- freshness: stale
- checked_at: 2026-11-20T10:00:00Z
- drift: member_added:1:c9, member_closed:17:c3+c5+c8
Harvest is next; refresh waits on it.
```

An empty value renders as the bare key (`- title:`). Because the header is always nine lines, situation text can never be read as a header field.

| Field | Grammar | Written by |
|---|---|---|
| slug (heading) | `[a-z0-9][a-z0-9_-]*` (today's `THEME_RE`) | identity, never changes |
| `rev` (heading) | positive int, store-wide stamp from `next_rev` | every change to the block |
| `title` | one line, at most 120 chars, may be empty | `direction-set` |
| `rank` | positive int or empty; ranked directions hold exactly 1..k | `direction-rank`, `direction-remove` (compaction) |
| `trails` | 0 to 8 unique `art:trail-[a-z0-9._-]{1,122}` (the `art:trail-` subset of `artifact_manifest.HANDLE_RE`, at most 132 chars), `, `-joined, caller's order | `direction-set` |
| `next` | empty, `t<N>[_<M>]`, `<project>#<N>[_<M>]` or `c<N>` | `direction-set` |
| `summary` | one line, at most 400 chars | `direction-set` |
| `digest` | empty or 16 hex: the name of the retained baseline `baselines/<digest>.txt` | `direction-set` |
| `freshness` | `current` / `stale` / `unknown` | `direction-freshness --batch`; reset by `direction-set` |
| `checked_at` | `never` or timestamp | same |
| `drift` | 0 to 32 reasons, one per code: `code`, `code:<count>` or `code:<count>:<k1>[+<k2>[+<k3>]]` | same |

**Drift reasons are aggregated per cause code**, so the number of causes never hits a limit.
- `code` is `[a-z][a-z0-9_]{0,31}` and appears at most once. `count` is how many causes share it. The sample is up to three keys in sorted order (members by number, the rest by bytes).
- A key is `[A-Za-z0-9._:#@/=-]{1,132}`. 132 is the longest legal artifact handle, so a legal trail handle always fits.
- The count is the overflow indication: `member_closed:17:c3+c5+c8` says seventeen members closed and names three.
- `aggregate_drift(pairs)` in the core turns `(code, key)` pairs into this form, keeping the codes in first-seen order. Child 2 calls it; the batch verb accepts only the aggregated form.
- **A key that does not fit the key grammar is left out of the sample, never cut and never a reason to fail.** The count still includes it, and the sample takes the next fitting keys. When no key fits, the reason is the count-only form `code:<count>`.
- 32 codes is far above child 2's vocabulary (13 today). More than 32 is a request error (exit 2), not a silent cut.

Invariants the parser enforces (a violation is a `FormatError`, exit 4):

- `summary` and `digest` are both empty or both set.
- `freshness=current` needs a digest and no drift; `stale` needs at least one reason; a freshness other than `unknown` needs a real `checked_at`.
- Ranks are unique and dense (1..k).
- A block with no situation text and no agent field (title, rank, trails, next, summary) does not exist; commits prune it. An empty theme block in an older file is dropped by the migration.

**Rev.** One rev per direction, taken from the existing store-wide `next_rev` counter (`Revs`). It covers the whole block: header and situation text. It does not cover membership (see "Freshness guard"). `max_rev_token` also scans the heading position `^#### <slug> \| rev=N$`, so a restore or a lost counter can never re-issue a direction rev. Situation text cannot start with `#`, so the position cannot be forged.

**Context key.** Format 4 writes `- direction: <slug>`; formats 1-3 are read with `- theme:`. Input to `add`, `upsert-context` and `recovery-apply` accepts only `direction`. `context c<N>` prints `direction:` whatever the file's format, so read-modify-write works on a store that is not upgraded yet.

**Old formats.** Formats 1-3 are still read and rendered byte-identically. The first changing write upgrades the file: every block gets a header with a fresh rev (sorted slug order), `theme:` becomes `direction:`. A file with `format=` below 4 that holds a `| rev=` heading or a `direction:` key is refused, naming format 4. A format-4 file holding `theme:` or a bare `#### slug` heading is refused.

## Mixed-version safety

Older checkouts (a task worktree cut before this change, a monitor or TUI started from one) run the old writer against the same store. Their ordinary verbs already fail closed on format 4 (exit 4, nothing written). Their `restore` is the hazard. Two guards:

1. **The migrating write never leaves an older-format backup behind a format-4 live file.**
   - On the write that upgrades the file, `todo.md.bak` becomes the format-4 rendering of the *previous* generation: same items, contexts and situation text, and the same stamped revs as the live file for every block the write did not change.
   - The pre-migration bytes are first copied to `recovered/todo.md.format<N>.<timestamp>.<pid>`, so no representation is lost.
   - An old writer's `restore` (both forms) then fails its own `.bak` verification and stops with exit 4, changing nothing. The same holds for every later generation, whose `.bak` is format 4 by the normal roll.
   - Mechanism: `_commit_todo` re-loads the on-disk generation, stamps it, renders it to a new `--out-bak` temp and prints `@BAK_MIGRATED`. `mutate()` in the wrapper, when that temp is non-empty, preserves the live file into `recovered/` and commits the temp as `.bak` instead of copying the live file. Order stays: counters, backup, live rename. A crash after the backup leaves a format-3 live file and a format-4 `.bak` with the same content.
2. **This writer refuses to restore over a newer format.** For the next bump, where this code is the old writer: `restore` (plain and `--if-damaged`) exits 4 and changes nothing when line 2 of the live file is a well-formed header with a format above the supported one. The message says the store was written by a newer aitasks and to update the checkout. Every other verb's refusal carries the same message (`NewerFormatError`, still exit 4). A new read op `newer-format <kind> <file>` gives the wrapper the answer.

**Rollout.** No flag day: the first changing write by a new writer upgrades the store. After that, older checkouts read it as unusable and write nothing until they are updated; a monitor or sitrep TUI started before the upgrade needs a restart. This goes into `aidocs/framework/sitrep.md` ("The store") and the wrapper header.

## Freshness guard

A refresh verdict depends on store-side inputs the direction rev does not cover: which items are members, and each member's state and ref.

- `direction_stamp(store, slug)`: 16 hex of sha256 over the sorted `c<N>@<item rev>` of the direction's members. An item's rev already changes with every change to the item or its context, so the stamp moves on a member added, removed, re-pointed or changed in any field.
- `directions` prints the stamp; an in-process reader calls the helper on its snapshot.
- Every `direction-freshness --batch` line carries the stamp the verdict was computed from. Under the writer lock the line applies only when both the rev and the stamp still match; otherwise `STALE:<slug>|<rev>|<stamp>` with the current values.
- Inputs outside the store (task files, trail artifacts) cannot be checked under the store lock. That is the same limit item refresh has today, and it is stated in the doc.
- `direction-set` needs no stamp: it can only reset freshness to `unknown`. A baseline computed from inputs that moved before the write makes the next refresh read `stale`, which is the safe direction.

## Baseline evidence

A hash alone can say "changed", never "what changed". So the baseline is the snapshot itself, and the digest is its address.

**Where it lives.** A new verb `retain-baseline` writes `baselines/<16 hex>.txt` (content-addressed, immutable, never pruned; the `retain-case` pattern: its own namespace, only records with the right first line). `digest` is that 16-hex name. `baselines/` joins the post-init artifacts `store_state` looks at.

**Snapshot grammar** (the store owns the envelope and the store-side lines; child 2 owns the values of the others):

```
sitrep direction baseline v1
direction: sitrep
member: c1|open|t2335_2
member: c6|open|push:main@1a2b3c4d5e6f
task: t2335_2|Implementing
trail: art:trail-sitrep-1|v3:current
next: t2335_2|valid
```

- Line 1 fixed, line 2 the slug, then input lines `<kind>: <key>|<value>`.
- Kinds in the order `member`, `task`, `trail`, `next`; within a kind sorted by key, keys unique; at most one `next` line; final newline, no blank lines.
- Keys: `c<N>`; a task ref; a trail handle; the `next` grammar. A member value is `<state>|<ref>`. The other values are opaque to the store: `[A-Za-z0-9._:#@/+=,-]{0,120}`.
- One input per line keyed by a stable id, so every specific drift reason is a line-level difference between baseline and current snapshot.
- **Only pending members are listed**: the members in state `open` or `unknown`. Items are never deleted, so closed members pile up in every direction; listing them would make every snapshot grow with history. Nothing is lost for the comparison: a baseline line whose item is still a member but now closed is "closed", one whose item no longer names the direction is "removed", a new line is "added" or "reopened".

**Size.** `MAX_BASELINE_BYTES = 256 KiB` (about 4000 pending members at 60 bytes for a member and its task). A snapshot is never truncated or sampled.
- Above the limit `retain-baseline` exits 2 naming the size and the limit; nothing is written and the direction's record, with its previous summary and baseline, is untouched.
- **The supported oversized outcome, for every direction**: it keeps its membership, title, rank and situation text; no new summary can be saved; refresh reports `unknown` with the reason `baseline_too_large`, which the batch verb stores like any `unknown` line. It is never `current`.
- For an ordinary direction the skill may then propose a split. For `crashed-agents` there is no split (membership is derived, recovery items cannot be reassigned), so the outcome above is the final one until the pending recovery items shrink.

**Integrity.** One helper, `baseline_status(store_dir, digest, slug)`, returns `ok`, `missing`, `not_regular`, `hash_mismatch` (sha256 of the bytes does not start with the name), `bad_grammar` or `wrong_direction`. Everything that trusts a baseline calls it:
- `direction-set` with a summary: anything but `ok` is exit 2, nothing written.
- `direction-freshness --batch`: on a record with a digest, a `current` or `stale` line is answered `KEPT:<slug>|baseline_<status>` unless the baseline is `ok`; `unknown` always applies. A record with no digest takes `stale` (never summarised) but not `current` (`KEPT:<slug>|no_baseline`).
- `check-sources`: `SOURCE_OK:<slug>|baselines/<hex>.txt`, `SOURCE_MISSING:` or `SOURCE_INVALID:<slug>|baselines/<hex>.txt|<status>`.
- Child 2's refresh uses the same helper and reports `unknown` with `baseline_unreadable` (note).

**Reason contract for child 2** (in the "Directions" doc section):
- A digest mismatch with no classified line difference is `inputs_changed`. This covers a task status change that is none of completed, archived or deleted (Ready to Implementing), which t2335_2's list has no reason for.
- An unusable baseline is `unknown` with `baseline_unreadable`, and an oversized snapshot `unknown` with `baseline_too_large`; never `stale` with a guessed reason.
- Reasons go through `aggregate_drift`; one per cause code, the count carrying the overflow.
- The store validates the reason grammar and "stale needs a reason"; the vocabulary stays child 2's.

## Proposal save sequence

The baseline must be the evidence the summary prose was written from, and a refused save must leave a state the skill can name. This binds t2335_1, t2335_2 and t2335_4.

1. **One read.** When the proposal is drafted, child 2's digest read builds the snapshot for each *proposed* member set and retains it (`retain-baseline`). Each summary is drafted from its snapshot. A baseline is never captured again at write time.
2. **One confirmation.**
3. **Recheck before the first write.** Child 4 re-runs child 2's digest read for every direction in the proposal. Any digest that differs means the evidence moved during the confirmation: nothing has been written yet, so the proposal is re-read, revised and confirmed again. This is the check that catches inputs outside the store, such as a task that closed. Child 2 should offer it as one verb, so it is enforced in code and not in skill prose.
4. **The writes, in this order, each one atomic:**
   - a. `direction-assign --batch`: all membership changes of the proposal in one all-or-nothing write, guarded by each item's rev.
   - b. `direction-set` per direction, with `--expect-rev` (the rev printed by step a when the assignment touched the block).
   - c. `direction-rank --expect-ranked`.
5. **The store checks its side under the lock** in step b. `direction-set` with a summary compares the baseline's store-side lines with the store as it is now:
   - the `direction:` line is this slug;
   - the `member:` lines are exactly the current pending members, each with its current state and ref;
   - the `trail:` keys are the record's trails and the `next:` key is the record's `next`, after this call's own `--trails` / `--next`;
   - any difference: `EVIDENCE_CHANGED:<slug>|<kind>|<key>` per difference, nothing written.
6. **A refusal, and what is already saved.** Nothing is rolled back, because every state below is valid on its own:

   | Refused step | Already saved | State of the store |
   |---|---|---|
   | a (`STALE:` / `NOT_FOUND:` on any line) | nothing | unchanged |
   | b for direction X | all assignments; the records set before X | X has its new members and its previous record or none; its freshness is `unknown`, because an assignment resets it |
   | c | all assignments and records | the previous order stands |

   The skill stops at the first refusal, reports which writes landed and which did not (quoting the result lines), re-reads `directions`, revises only what is left, confirms and resumes. It never retries blind.
7. **What slips past the recheck and the store check** is still safe: the baseline is the older evidence, so the next refresh reads `stale`, never `current`.

The sibling task texts currently contradict rules 1 and 4 (step 9 below fixes them).

## Membership and `crashed-agents`

- Members of a direction are the items whose context names its slug. Nothing is stored in the block.
- `RECOVERY_DIRECTION = "crashed-agents"` moves into `lib/sitrep_todo.py`. Its members are the `recover:` items whose context names no direction (an explicit direction still wins, as today).
- New context input naming `crashed-agents` is refused (exit 2). The parser tolerates it in an existing file, so no old store becomes unreadable.
- A direction "is known" when it has a block or at least one member. `crashed-agents` can have a block, a title, a rank and situation text like any other.
- Removing situation text (`situation <slug>` with empty input) clears only the text. The record stays; the block is pruned only when nothing agent-written is left. Members keep their `direction:` key, and the direction stays listed from its members with no record.

## Verbs (wrapper header is the wire contract)

Exit codes are the existing ones (0 / 2 / 3 / 4).

- `directions [<slug>]` (read, no lock). Ranked directions first by rank, then unranked by slug:
  - `DIRECTION:<slug>|<rev>|<stamp>|<rank>|<freshness>|<checked_at>|<digest>|<next>|<trails>|<open>|<members>|<title>`; `rev` and `rank` are `-` when absent; title last (may contain `|`).
  - `DIRECTION_SUMMARY:<slug>|<summary>` when set; `DIRECTION_DRIFT:<slug>|<code>|<count>|<sample>` per reason; `DIRECTION_MEMBER:<slug>|c<N>|<state>|<kind>|<ref>` per member.
  - Full listing only: `NO_DIRECTIONS` when there is none, and always a last line `UNASSIGNED:<n>|c1,c2` for the items in state `open` or `unknown` that are in no direction.
  - `directions <slug>` for an unknown slug: `NOT_FOUND:<slug>`, exit 2.
- `direction-assign --batch`: stdin has one `<id>|<rev>|<slug or ->` per line (`-` leaves the item in no direction). It changes only the context's `direction:` key. All or nothing.
  - Any line that cannot apply: `STALE:c<N>|<rev>`, `NOT_FOUND:c<N>` or `KEPT:c<N>|recovery` (a `recover:` item: its context is the detector's and it belongs to `crashed-agents`); then nothing is written.
  - A duplicate id, an invalid slug or the reserved slug is exit 2.
  - **An ordinary item with no context entry** (valid: `add` takes a context only when given) gets the minimal entry that can carry the key, under the same rev check: the fixed background `No context was recorded for this item; this entry holds its direction.`, `origin: date=<today>` and the `direction:` line.
  - A line that changes nothing is an unchanged result: it keeps the item's rev, and clearing (`-`) an item that is in no direction creates no context entry.
  - Success: `ASSIGNED:c<N>|<slug or ->|<item rev>` per line, then `DIRECTION:<slug>|updated|<rev>` for each direction with a block that gained or lost a member.
  - **A membership write resets freshness**: each such block goes to `unknown` / `never` / no drift with a fresh rev. `add` and `upsert-context` do the same when they change an item's direction.
- `upsert-context <id> [--expect-rev N]`: the optional rev guard it lacked (`STALE:c<N>|<rev>`), so no write to an existing item is unguarded.
- `direction-set <slug> --expect-rev absent|<rev> [--title T] [--trails a,b] [--next R] [--summary-file - --digest H]`
  - Summary on stdin, one line; empty stdin clears summary and digest. A non-empty summary needs `--digest` naming a baseline that is `ok` and matches the store (rule 5 above).
  - Results: `DIRECTION:<slug>|created|<rev>`, `|updated|<rev>`, `|unchanged|<rev>`, `STALE:<slug>|<rev>`, `ABSENT:<slug>`, `EVIDENCE_CHANGED:<slug>|<kind>|<key>`.
  - A change to summary, digest, trails or next resets freshness to `unknown` / `never` / no drift. The agent can never write `current`.
  - `--next c<N>` must name an existing item.
- `direction-rank --expect-ranked <a,b,c or -> [--clear]`: stdin has one `<slug>|<rev or absent>` per line, in rank order. All or nothing.
  - `--expect-ranked` is required: the full ranked order the caller saw (`-` for none). When the current order differs: `STALE_ORDER:<current order or ->`, nothing written. This is what protects a rank added by another session from being cleared by omission.
  - Any rev mismatch: `STALE:<slug>|<rev>` / `ABSENT:<slug>` lines, nothing written.
  - Duplicate or unknown slug, or empty stdin without `--clear`: exit 2.
  - Success: `RANKED:<slug>|<rank>|<rev>` per named direction, `UNRANKED:<slug>|<rev>` per direction that lost its rank. A known slug without a block gets one.
- `direction-freshness --batch`: stdin lines `<slug>|<rev>|<stamp>|<freshness>|<checked_at>|<drift>`.
  - Per line: `FRESHNESS:<slug>|<freshness>|<rev>`, `STALE:<slug>|<rev>|<stamp>`, `NOT_FOUND:<slug>` (no block), `KEPT:<slug>|no_baseline`, `KEPT:<slug>|baseline_<status>`.
  - Sets only the three refresh fields; an equal line writes nothing and keeps the rev.
- `retain-baseline`: stdin snapshot (grammar and size above) → `RETAINED_BASELINE:baselines/<hex>.txt|<hex>`; a grammar or size refusal is exit 2.
- `direction-remove <slug> --expect-rev <rev>`: deletes the block (record and text), compacts the ranks.
  - `DIRECTION_REMOVED:<slug>|<members still naming it>`, plus `RANKED:` lines for shifted directions; `STALE:` / `ABSENT:`.
  - Not in the task's verb list. Added because child 4 lets the user drop a direction, and without it that takes three clearing writes.
- `situation <direction>`: wire lines unchanged (`SITUATION:<slug>|set|removed|absent`); it now bumps the block's rev.
- `restore`: refuses a newer-format live file (above).

## Implementation steps

1. **`lib/sitrep_todo.py`**
   - Constants: `TODO_FORMAT_VERSION = 4`, `TODO_READ_FORMATS = (1, 2, 3, 4)`, `DIRECTION_FORMAT = 4`, `RECOVERY_DIRECTION`, the limits, `DIRECTION_RE` (replaces `THEME_RE`), `TRAIL_HANDLE_RE`, `DIGEST_RE`, drift regexes, the heading regex.
   - Model: new `Direction` dataclass (fields above plus `situation: list`), `header_lines()`, `is_empty()`. `TodoStore.directions` replaces `TodoStore.situations`. `ContextEntry.theme` becomes `.direction`; `body_lines(fmt=TODO_FORMAT_VERSION)` picks the key name.
   - `render_todo`: heading and header by `store.format`.
   - `parse_todo`: collect raw block lines per slug, then split header (first nine lines, strict key order) from text; `_check_direction_values`, `_check_ranks`; format gating both ways; `NewerFormatError` from `_todo_format`. `_parse_context_body(lines, fmt)`.
   - `max_rev_token`: add the heading position.
   - `_commit_todo`: prune empty blocks; when upgrading, build the migrated previous generation into `--out-bak` (see "Mixed-version safety") and copy its revs to unchanged blocks; then render and parse back as today.
   - Read helpers for children: `item_direction(store, item)`, `direction_members(store)`, `known_directions(store)`, `unassigned_items(store)`, `direction_stamp(store, slug)`.
   - Baselines: `BASELINE_HEADER`, `MAX_BASELINE_BYTES`, `parse_baseline(text)` (strict, canonical), `baseline_status(...)`, `baseline_differences(store, slug, record, baseline)` for rule 5; `store_state` counts `baselines/`.
   - Drift: the aggregated reason grammar, `aggregate_drift(pairs)`.
   - One helper for "a membership write resets freshness", called by `op_add`, `op_upsert_context` and `op_direction_assign`.
   - Ops: `op_directions`, `op_direction_assign`, `op_direction_set`, `op_direction_rank`, `op_direction_freshness_batch`, `op_direction_remove`, `op_retain_baseline`, `op_newer_format`; `op_situation` on the new model; `--expect-rev` on `op_upsert_context`; `op_check_sources` adds baselines; argparse entries; `validate_context_input` refuses the reserved slug.
   - Module docstring: format 4, the rev rule, the stamp, the rename, the mixed-version rule.
2. **`aitask_sitrep_todo.sh`**
   - Header (files, FORMAT paragraph, verb table, results, the rollout note) and `usage()`.
   - `mutate()`: pass `--out-bak`, handle the migrated backup and the `recovered/` copy.
   - `cmd_restore`: the newer-format refusal, before the `--if-damaged` decision.
   - `cmd_direction_assign` / `_set` / `_rank` / `_freshness` / `_remove` following `cmd_recovery_apply` (precheck, then `mutate todo …`); `cmd_upsert_context` accepts `--expect-rev`; `cmd_retain_baseline` following `cmd_retain_case`; `directions` through `cmd_readonly`; dispatch entries.
3. **TUI consumers** (must read a format-4 store; the tab is child 5)
   - `sitrep_tui_requests.py`: `RECOVERY_THEME` removed in favour of `st.RECOVERY_DIRECTION`; `item_theme` becomes `item_direction` delegating to `st.item_direction`; template `>w {direction}`.
   - `sitrep_tui_actions.py`: call site and docstring.
   - `sitrep_tui_app.py`: details label `Direction`; `_render_situation` reads `store.directions[slug].situation` and skips blocks with no text; docstring.
4. **Consumer audit** (no code change expected; confirm by running their suites): `sitrep_cli.py`, `sitrep_harvest.py`, `sitrep_refresh.py`, `sitrep_corpus.py` (`DryStore`), `sitrep_crash.py`, `sitrep_tui_model.py`, `frozen_sitrep.py`, `monitor/sitrep_close.py`. They use items, contexts' sources and `body_lines()` only; none reads the situation blocks or the theme key.
5. **Fixtures** `tests/fixtures/sitrep/`
   - Copy today's `store/` to `store_v3/` and `expected_list.txt` to `expected_list_v3.txt`.
   - Rebuild `store/` through the real writer from a copy of `store_v3` with `AITASK_SITREP_NOW` pinned: `upsert-context c7` without a direction (a derived `crashed-agents` member), `retain-baseline` for the sitrep members, `direction-set sitrep` (full record), `direction-set crashed-agents` (title only), `direction-rank`, `direction-freshness --batch` (sitrep stale, two reasons). `board` stays a text-only block.
   - Refresh `expected_list.txt`, `expected_context_c1.txt`, `expected_check_sources.txt`; add `expected_directions.txt`. The exact commands go into the plan's Final Implementation Notes.
6. **Tests**
   - `tests/test_sitrep_todo_format.py`
     - Format-4 round trip; header order and count refusals with line numbers; each invariant; v3 fixture round trips as v3; gating both ways; rev scan sees direction revs; `item_direction` cases incl. the reserved slug; `direction_stamp` moves on each kind of member change; fix the `format=3` pins.
     - **Migration check**: one helper compares two parsed stores field by field: every item, every context value (old `theme` equals new `direction`), the situation text per slug. Run over the `store_v1`, `store_v2` and `store_v3` fixtures, for the upgraded live file against the original plus the write's own change, and for the migrated `.bak` against the original with no change.
   - `tests/test_sitrep_todo.sh`
     - Test 16 on the new fixture plus `directions`; 16b / 16d rewritten against the upgraded shape; new 16e (v3 read as-is, no-op byte-identical, upgrade stamps headers and renames the key).
     - **Mixed version**: after the migrating write on each older fixture, `.bak` line 2 is `format=4`, `.bak` verifies, and `recovered/` holds a byte-identical copy of the pre-migration file. A writer killed at `write:after_backup` during the migration leaves a store the next verb reads and completes. A live file with `format=5` and a valid `.bak`: `restore todo`, `restore todo --if-damaged` and a mutation each exit 4 with both files byte-identical.
     - `direction-set`: create / update / unchanged / stale / absent / freshness reset / summary without digest.
     - `direction-assign --batch`: only the `direction:` key changes (every other context line byte-identical); one stale line among several leaves `todo.md` byte-identical; **a mixed batch** of one item with a context and one without assigns both, the second getting exactly the three minimal lines and a new rev; a stale rev on the contextless item writes nothing; clearing a contextless unassigned item is unchanged, creates no entry and leaves the file byte-identical; a `recover:` item is `KEPT:…|recovery` and nothing is written; the reserved slug is exit 2; a block that gains or loses a member goes to `unknown` with a new rev, and the same through `upsert-context`. `upsert-context --expect-rev` with a stale rev writes nothing.
     - **A refusal after the first assignment** (rule 6): assign two items into a direction that has a saved `current` record, change one member's state, then `direction-set` with the pre-change baseline. It answers `EVIDENCE_CHANGED`; the assignment stays; `directions` shows the new members, the previous summary and freshness `unknown`. A fresh baseline then saves with the rev step a printed, and `direction-rank --expect-ranked` still applies.
     - **Oversized `crashed-agents`**: with a block and a rank, an over-limit snapshot is refused by `retain-baseline`; an `unknown` batch line with `baseline_too_large` applies; `directions` shows the derived members and the rank unchanged, and a `current` line is still `KEPT`.
     - **More causes than reasons fit**: `aggregate_drift` over 20 member closures plus two other causes gives three reasons, `member_closed:20:c1+c2+c3` among them; the `stale` batch line persists; `directions` prints the count 20. A repeated code, a sample of four keys and a count below the sample size each exit 2.
     - **A legal long trail handle**: a 132-character handle is accepted by `direction-set --trails`, by a baseline `trail:` line and as a drift sample key (`trail_unreadable:1:<handle>` persists and round-trips); 133 characters is refused by all three. `aggregate_drift` with one over-long composite key and one fitting key gives count 2 and the fitting key; with only over-long keys it gives the count-only form, and that line persists as `stale`. A unit test pins that every handle `TRAIL_HANDLE_RE` accepts also matches `artifact_manifest.HANDLE_RE`.
     - **A change during confirmation** (rule 5): retain the baseline, then before `direction-set` change the store in one of four ways (a member's `set-state`, a member's ref via `update`, an item moved in, a member moved out). Each gives `EVIDENCE_CHANGED` naming the line, with `todo.md` byte-identical. Also a baseline for another slug, and trail / next keys that differ from the record. The control with no change saves.
     - **Baseline integrity**: with a saved record, replace the file at the right path with different valid-looking bytes, truncate it, replace it by a symlink, delete it. Each time `direction-set` exits 2, a `current` and a `stale` batch line are `KEPT:<slug>|baseline_<status>`, an `unknown` line applies, and `check-sources` prints `SOURCE_INVALID` or `SOURCE_MISSING`.
     - **Baseline size and grammar**: a generated snapshot of exactly `MAX_BASELINE_BYTES` is retained; one byte more exits 2 naming size and limit, creates no file and leaves the record byte-identical; then a smaller snapshot for a reduced member set saves (the split outcome). Unsorted, duplicate-key, blank-line, wrong-header and missing-newline inputs each exit 2.
     - `direction-rank`: atomic; duplicates; unknown slug; a stale rev leaves the file byte-identical; dense ranks; **the intervening rank addition** (A ranked, another call ranks A then B, the original request with `--expect-ranked A` gets `STALE_ORDER:A,B` and B keeps rank 2), the same for `--clear`, and the control without the intervening call.
     - `direction-freshness --batch`: agent fields byte-identical before and after; `NOT_FOUND`; idempotent; `KEPT:…|no_baseline` for `current` on a record with no digest; **the intervening input change**, three cases between the snapshot and the batch (an item moved into the direction by `upsert-context`, a member's `set-state`, a member moved out), each `STALE` with the file byte-identical, and the control with no change applies.
     - Situation removal keeps the record; `direction-remove` compaction; reserved slug refused in context input; `situation` and the existing verbs unchanged on a format-4 store.
   - Rename-only edits: `test_sitrep_tui_requests.py`, `test_sitrep_tui_app.py` (helper writes `- direction:`, label `Direction`, plus a boot on a store with full records: the situation pane shows text and no header lines), `test_sitrep_refresh.sh:648`, `test_sitrep_skill_contract.sh` (`SX_DIRECTION`), `test_skill_render_aitask_sitrep.sh:110`.
7. **Skill** (read `aidocs/framework/skill_authoring_conventions.md` and `stub-skill-pattern.md` first)
   - `.claude/skills/aitask-sitrep/SKILL.md.j2`: every "theme" becomes "direction" (`>w [<direction>]`, the `crashed-agents` sentence, the `- direction: <DIRECTION>` examples, the context key list). The `>w <direction>` known-direction check reads `directions` instead of raw `read context`. No `>d` yet.
   - Regenerate the three goldens with the documented command; run `./.aitask-scripts/aitask_skill_verify.sh`. The `.agents` / `.opencode` stubs carry no template text and stay as they are.
8. **Docs** (read `documentation_conventions.md` and the doc guide first)
   - `aidocs/framework/sitrep.md`: "The store" for format 4 and the rollout rule; new "Directions" section (grammar table, invariants, rev and stamp, membership, `crashed-agents`, baseline evidence and the reason contract, verbs, what each later child may rely on); rename in "Actions" and "The skill"; tests table row.
   - Website wording only: `skills/aitask-sitrep.md`, `tuis/sitrep/reference.md`, `tuis/sitrep/how-to.md` ("work area" and "theme" become "direction"); the store-files table in `reference.md` gains `baselines/` if it lists the other directories. Then `python3 check_links.py --build` in `website/`.
9. **Sibling task texts** (task data, committed with `aitask_task_commit.sh`; neither task is claimed)
   - `aitasks/t2335/t2335_2_refresh_direction_freshness.md`: replace "recorded when the agent writes the summary (child 4 calls a `digest` read at write time)" with the one-read rule; the digest read takes a proposed member set, lists pending members only and retains through `retain-baseline`; add the recheck verb, `inputs_changed`, `baseline_unreadable`, `baseline_too_large`, `aggregate_drift` in place of one reason per member, the batch stamp; tests gain "a task closes during the confirmation: not saved" and "closes after the save: `stale`, never `current`".
   - `aitasks/t2335/t2335_4_skill_directions_code.md`: replace "The summary is written together with the digest read at that moment" and "direction assignments (`upsert-context`)" with the save sequence (rules 1 to 6): the recheck before the first write, `direction-assign --batch`, the partial-progress report; add the oversized outcome (no reassignment of recovery items) and `--expect-ranked`.
   - Both point at the "Directions" section of `aidocs/framework/sitrep.md` as the contract. Check each diff shows only these lines.

### Post-phase (risk mitigations)

1. [real_store_upgrade_dry_run] Copy this repo's live `.aitask-sitrep/` (`todo.md`, `qa.md`, `next_id`, `next_rev`, `store.init`, `sources/`) into the scratchpad; the live store is only read. With `AITASK_SITREP_DIR` pointing at the copy:
   - `list` and `read` before any write equal the live store's output (format 3 still reads byte-identically).
   - Run one changing write (`situation dryrun` with one line of text). Then `verify todo` prints `VERIFIED:todo` for both `todo.md` and `todo.md.bak`, line 2 of both is `format=4`, and `list` output equals the output before the write.
   - Run the step 6 migration-check helper on the copy: upgraded file against the original plus the `dryrun` block, migrated `.bak` against the original. The live copy has no theme blocks or keys, so the populated cases are the `store_v1` / `v2` / `v3` runs of step 6; say so in the notes.
   - Record the commands and their output in the Final Implementation Notes.
2. [stale_process_fail_closed_check] Extract the base commit's writer (`git archive 72bdd15db .aitask-scripts/aitask_sitrep_todo.sh .aitask-scripts/lib`) into the scratchpad. Build two format-4 stores from `store_v3` with the new writer: one after exactly one migrating write, one after two writes.
   - Old reader in process: `load_todo_for_read` raises on both stores.
   - Old writer, each of `list`, `add`, `situation`, `set-state --batch`, `restore todo`, `restore todo --if-damaged`, on both stores: exit 4, and `todo.md`, `todo.md.bak`, `next_id`, `next_rev` are byte-identical before and after.
   - Negative control proving the hazard was real: the same old `restore todo --if-damaged` against a format-4 live file with a hand-placed format-3 `.bak` does install the backup.
   - New writer on those stores: `restore todo --if-damaged` answers `RESTORE_NOT_NEEDED:todo.md`.
   - Record the commands and their output in the Final Implementation Notes.

## Concurrent work in this checkout

Another session (t2350, frozen-agent reverse index) has uncommitted edits in this working tree, seen during planning on 2026-11-24. Four of its files are also edited by this plan: `sitrep_tui/sitrep_tui_app.py`, `sitrep_tui/sitrep_tui_actions.py`, `aidocs/framework/sitrep.md` and `website/content/docs/tuis/sitrep/reference.md`. It also edits `lib/frozen_sitrep.py` (step 4 only reads it).

- Steps 1, 2, 5 and 6 touch none of those files and go first.
- Before the first edit of each shared file (steps 3 and 8), re-run `git status` on it. If t2350's edits are still uncommitted there, stop and ask; do not edit on top of them, stash, restore or commit them.
- Commits name their paths, so nothing of the other session rides along.
- The workflow's parallel-admission preflight runs after plan approval and may change this order.

## Rename surfaces

| Surface | Renamed by |
|---|---|
| Core and wrapper: identifiers, verb argument, errors, context key | this child |
| `sitrep_cli.py`, harvest, refresh, corpus, crash | audited: no "theme" token |
| TUI: `RECOVERY_THEME`, `item_theme`, `{theme}`, the details label | this child |
| TUI: Directions tab, `>d` request row | child 5 (new text only) |
| Skill template, goldens: existing wording | this child |
| Skill: `>d`, pick advice, questions | child 4 (new text only) |
| Tests and fixtures | this child |
| `aidocs/framework/sitrep.md`, website skill and TUI pages | this child |

After this child, `grep -ni theme` over the sitrep surfaces matches only the old-format fixtures, the tests that read them, and the one statement that formats 1-3 are read with `theme:`.

## Notes to send after implementation (workflow Step 8e)

The binding text is in the two sibling task files (step 9) and the doc section; the notes say what landed and where.

- t2335_2: the snapshot grammar and `retain-baseline`; `baseline_status`; `aggregate_drift`; the batch line with the stamp and its result lines; `NOT_FOUND` for a direction with no block; the `KEPT:` answers.
- t2335_4: the rename is done; the verbs incl. `direction-assign`; `EVIDENCE_CHANGED`; the oversized outcome; `--expect-ranked`; `direction-remove`.
- t2335_5: the rename is done; the read helpers in `sitrep_todo`; `RECOVERY_DIRECTION` moved.

## Verification

- Before editing: run the sitrep suites once for a baseline.
- `bash tests/test_sitrep_todo.sh`; `python3 tests/test_sitrep_todo_format.py`.
- Consumers: `test_sitrep_tui_app.py`, `_actions.py`, `_requests.py`, `_trails.py`, `_trails_actions.py`, `test_sitrep_harvest.{sh,py}`, `test_sitrep_refresh.{sh,py}`, `test_monitor_sitrep_refresh.py`, `test_sitrep_crash.{sh,py}`, `test_sitrep_corpus.{sh,py}`, `test_sitrep_corpus_fixtures.py`, `test_frozen_sitrep.py`, `test_monitor_frozen_sitrep_badge.py`, `test_monitor_sitrep_harvest_close.py`, `test_sitrep_window.py`.
- Skill: `test_skill_render_aitask_sitrep.sh`, `test_sitrep_skill_contract.sh`, `aitask_skill_verify.sh`.
- `shellcheck .aitask-scripts/aitask_sitrep_todo.sh`; `python3 check_links.py --build`.
- Then workflow Step 9 (post-implementation: review, commit, archival).

## Risk

### Code-health risk: medium
- The store is a source of truth with a strict parser; a render/parse mismatch in the new grammar would make stores unreadable (exit 4). Bounded by the canonical check, the parse-back in `_commit_text` (a bad result is refused, nothing written) and round-trip tests over four fixture generations · severity: low (residual: also checked on a copy of the real store by inline post-phase real_store_upgrade_dry_run) · → mitigation: inline post-phase real_store_upgrade_dry_run
- Older code reaching an upgraded store: long-running processes holding the old parser stay degraded until restarted, and an old writer's `restore` could have rolled format 4 back to the format-3 backup · severity: low (residual: the migrating write leaves no older-format backup, and the old writer's verbs are run against upgraded stores by inline post-phase stale_process_fail_closed_check) · → mitigation: inline post-phase stale_process_fail_closed_check
- The migrating write now touches three files in the locked sequence (`recovered/` copy, migrated `.bak`, live rename). A fault between them must leave a readable store · severity: medium · → mitigation: none (the kill-at-`write:after_backup` test in step 6)
- `ContextEntry.body_lines()` gains a format parameter and `situations` is replaced; eight modules import the core. A missed consumer would fail at runtime · severity: low · → mitigation: none (step 4 audit plus their suites)

### Goal-achievement risk: medium
- The record contract is fixed before children 2, 4 and 5 are planned; a field or verb may turn out wrong for them. The digest decision already deviates from this task's text, and the stamp, the store-owned snapshot envelope, the one-read rule and `--expect-ranked` add to what they must follow · severity: medium · → mitigation: none (user-confirmed decisions, the "Directions" doc section, the corrected sibling task texts, notes)
- The store can only check the store-side lines of a baseline. A task that closes during the confirmation is caught only by child 2's recheck, which does not exist yet · severity: low (rule 7: the worst case is a summary shown `stale`, never a wrong `current`) · → mitigation: none (specified in t2335_2 and t2335_4 by step 9)
- The task has grown through three review rounds (five more verbs, the baseline namespace, the migrated backup). It is one coherent store contract, but a large change for one child · severity: medium · → mitigation: none (the steps are ordered so the core, the wrapper and each test group land and pass in turn)
- The skill says "direction" before `>d` exists, so for a while a direction is only situation text plus membership · severity: low · → mitigation: none (accepted with decision 2)

### Planned mitigations
- timing: post-phase | name: real_store_upgrade_dry_run | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: a render/parse mismatch making real stores unreadable | desc: upgrade a scratch copy of the live store with the new writer and compare parsed items, contexts and situation text across the migration
- timing: post-phase | name: stale_process_fail_closed_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: older readers and writers reaching an upgraded store | desc: run the base commit's reader and writer verbs (incl. both restore forms) against upgraded stores; each must exit 4 and change no byte

## Final Implementation Notes

- **Actual work done:** All nine plan steps and both post-phase checks.
  - `lib/sitrep_todo.py`: format 4 (the `Direction` record, the `direction` context key, the heading rev), the read helpers (`item_direction`, `direction_members`, `pending_members`, `known_directions`, `unassigned_items`, `direction_stamp`), the baseline grammar (`parse_baseline`, `load_baseline`, `baseline_status`, `baseline_differences`), `aggregate_drift`, `NewerFormatError`, the migrated backup in `_commit_todo`, and the ops `directions`, `direction-assign-batch`, `direction-set`, `direction-rank`, `direction-freshness-batch`, `direction-remove`, `retain-baseline`, `newer-format`; `--expect-rev` on `upsert-context`.
  - `aitask_sitrep_todo.sh`: the header contract, `mutate()` installs the migrated backup and keeps the pre-upgrade bytes under `recovered/`, `restore` refuses a newer-format file, the new verbs.
  - TUI: `sitrep_tui_requests.item_direction` delegates to the store, the details label is `Direction`, the situation pane shows the text of blocks that have text.
  - Skill template and its three goldens, `aidocs/framework/sitrep.md` (new "Directions" section), three website pages: "theme" and "work area" became "direction".
  - Fixtures: `store/` is format 4 (built by `tests/fixtures/sitrep/build_store.sh`, deterministic), `store_v3/` is the previous `store/`.
  - Tests: `tests/test_sitrep_todo.sh` 367 to 660 assertions, `tests/test_sitrep_todo_format.py` 50 to 83 tests, one new TUI test.
  - Sibling task texts t2335_2 and t2335_4 corrected (step 9).
- **Deviations from plan:**
  - `baseline_status` has a seventh status, `unreadable`, for a file that exists and cannot be read.
  - `retain-baseline` over a file at the same name whose bytes do not hash to that name replaces it with the right bytes. The plan did not say what a re-retain does to a damaged baseline; without this a damaged file could never be repaired.
  - The context size limit is measured in the format-1 spelling of the entry (`theme:`), so an entry that fitted before the upgrade still fits after the key gets four characters longer. Not in the plan; without it a store with one entry at the limit could never be upgraded.
  - Membership resets are done in one place, `_commit_todo`, by comparing the membership as loaded with the membership being written, not per verb. `recovery-apply` creating a recovery item therefore also resets a `crashed-agents` block.
  - `add` and `upsert-context` reset freshness silently; only `direction-assign` prints the `DIRECTION:<slug>|updated|<rev>` lines, because the other two have existing consumers of their output.
  - The fixture build commands are a script in the repository (`tests/fixtures/sitrep/build_store.sh`), not only notes here.
  - The website reference page also got one bullet on the format change (older checkouts, restart), beyond the planned wording swap.
  - The `<open>` field of the `DIRECTION:` line is named `<pending>` in the wrapper header: it counts members in state `open` or `unknown`.
- **Issues encountered:**
  - **The live store was upgraded during implementation.** This task ran on the current branch in the user's checkout. About two minutes after the new core was installed, the monitor's maintenance pass ran it and upgraded `.aitask-sitrep/todo.md` to format 4 (pre-upgrade bytes kept as `recovered/todo.md.format3.20261125T080854Z.3053395`). The store verified afterwards, with all 194 items present. A store change by uncommitted code was not foreseen in the plan. For a later format bump, implement in a worktree or point `AITASK_SITREP_DIR` handling away from the live store first.
  - Two existing tests used behaviour that changed on purpose: a `- theme:` context line (now `- direction:`), and `format=9` as a stand-in for a damaged `qa.md` (now read as a newer format and refused by `restore`; the test corrupts with `format=x` and a new assertion covers the refusal).
  - Test 3 pinned item revs 4; a `situation` write now takes a rev for its block, so they are 5.
  - `$( )` strips the final newline of a snapshot; the test helper `retain_snapshot` puts it back.
- **Key decisions:**
  - The rev of a block read from formats 1-3 is 0; `--expect-rev absent` matches such a block, and `directions` prints `-` for it.
  - On the upgrading write, an unchanged block gets the same rev in the live file and in the migrated backup; a changed block gets two different ones.
  - `direction-rank` checks unknown slugs (exit 2) before the `--expect-ranked` comparison.
  - `direction-freshness` checks the baseline for `current` and `stale` only on records that have a digest; `stale` on a record with none (never summarised) applies.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - The contract is `aidocs/framework/sitrep.md`, "Directions". The wire lines are in the header of `aitask_sitrep_todo.sh`.
  - t2335_2: take the stamp (`st.direction_stamp`) from a snapshot loaded AFTER the pass's item batch is written, because item refresh bumps member revs and so moves the stamp. On a store not yet upgraded every block has rev 0 and a batch line cannot match; the first changing write upgrades it. Build reasons with `st.aggregate_drift`. The snapshot must end with a newline and list pending members only.
  - t2335_4: `direction-assign --batch` prints `DIRECTION:<slug>|updated|<rev>` for a block it touched; use that rev for the following `direction-set`. An item's rev changes when it is assigned.
  - t2335_5: `app.store.directions[slug]` is a `Direction` (`rank`, `title`, `freshness`, `drift` as `(code, count, [keys])`, `situation`). `st.known_directions(store)` gives rank order. `RECOVERY_THEME` is gone; use `st.RECOVERY_DIRECTION`.
  - Extending the fixture: edit and re-run `tests/fixtures/sitrep/build_store.sh <writer> tests/fixtures/sitrep/store_v3 tests/fixtures/sitrep/store`, then regenerate the four `expected_*.txt` files with `list --machine`, `context c1`, `check-sources` and `directions`.

### Post-phase evidence: real_store_upgrade_dry_run

Run on 2026-11-25 against a scratch copy. The live store had already been upgraded (see above), so the copy was built from its preserved format-3 file plus the live `qa.md`, counters, `store.init` and `sources/`.

```
source: .aitask-sitrep/recovered/todo.md.format3.20261125T080854Z.3053395 (<!-- aitask-sitrep todo format=3 -->)
$ aitask_sitrep_todo.sh read | cmp - original.md      -> READ_BEFORE: byte-identical to the format-3 file
$ aitask_sitrep_todo.sh list | wc -l                  -> 194
$ printf 'Dry run of the format upgrade.\n' | aitask_sitrep_todo.sh situation dryrun
SITUATION:dryrun|set
$ sitrep_todo.py verify todo store/todo.md            -> VERIFIED:todo
$ sitrep_todo.py verify todo store/todo.md.bak        -> VERIFIED:todo
line 2 of both                                        -> <!-- aitask-sitrep todo format=4 -->
$ list before vs after                                -> LIST: identical before and after
$ ls store/recovered                                  -> todo.md.format3.20261125T082145Z.3621976 (byte-identical to original.md)
$ assert_same_content(original, live, added_directions=("dryrun",)); assert_same_content(original, backup)
MIGRATION_CHECK: ok -- 194 items, 194 contexts, 0 direction keys, 0 situation blocks in the original; live has ['dryrun'], backup has []
$ diff <(sed 2d original.md) <(sed 2d store/todo.md)  -> only the new "#### dryrun | rev=1330274" block (heading, nine header lines, the text, a blank line)
```

The real store has no situation blocks and no direction keys, so it does not exercise their migration. Those cases are covered by `Migration.test_every_older_fixture_keeps_its_content` over `store_v1`, `store_v2` and `store_v3`, which asserts that each fixture has both.

### Post-phase evidence: stale_process_fail_closed_check

The base commit's writer and `lib/` were extracted with `git archive 72bdd15db .aitask-scripts/aitask_sitrep_todo.sh .aitask-scripts/lib`. Stores `one` and `two` are `store_v3` after one and after two changing writes by the new writer; both have a format-4 live file and a format-4 backup.

```
== store 'one' and store 'two' (identical results)
OLD READER in process: load_todo_for_read -> FormatError "unsupported or missing format header '<!-- aitask-sitrep todo format=4 -->'"
old writer: list                         exit 4  files unchanged
old writer: add --kind task --title x    exit 4  files unchanged
old writer: situation sitrep             exit 4  files unchanged
old writer: set-state --batch            exit 4  files unchanged
old writer: restore todo                 exit 4  files unchanged  | Error: cannot restore todo.md: its backup is missing or unreadable
old writer: restore todo --if-damaged    exit 4  files unchanged  | Error: cannot restore todo.md: its backup is missing or unreadable
new writer: restore todo --if-damaged -> RESTORE_NOT_NEEDED:todo.md
== negative control: format-4 live file + a hand-placed format-3 backup
old writer: restore todo --if-damaged    exit 0 | RESTORED:todo.md|recovered/todo.md.20261125T082204Z.3643392 | live is now format=3
```

"files unchanged" compares sha256 of `todo.md`, `todo.md.bak`, `next_id`, `next_rev`, `qa.md` and the number of files in `recovered/` before and after each verb. The negative control shows the rollback the migrated backup prevents.

## Post-Review Changes

### Change Request 1 (2026-11-25 10:50)
- **Requested by user:** four review concerns, each confirmed against the code. (1) A format-5 file with CR LF line endings was still treated as damaged and rolled back by both `restore` forms. (2) `direction-set --next core#42` crashed with a ValueError: the item-id check used a `c` prefix, not the `c<N>` grammar. (3) The t2335_4 text equated a direction dropped from a proposal with `direction-remove`, which deletes the saved summary and leaves items assigned. (4) `directions` rebuilt the membership map inside every `direction_stamp` call.
- **Changes made:**
  - `newer_format` normalizes CR LF and CR and ignores line 1; `parse_todo` asks it first, before the final-newline and banner checks; the qa branch of `newer-format` does the same.
  - The `--next` item check matches `^c[1-9][0-9]*$` before converting.
  - t2335_4 and the "Saving a proposal" doc section: a direction left out of a proposal is not written; `direction-remove` only on an explicit request.
  - `direction_stamp(store, slug, members=None)`; `directions` and `direction-freshness --batch` pass the member list they already have.
  - Tests: both restore forms preserve a CRLF newer-format `todo.md` and `qa.md` byte for byte; unit cases for CR LF, CR and a reworded banner; `--next core#42` and `--next c1`; the stamp with a given member list. `tests/test_sitrep_todo.sh` is now 675 assertions.
- **Files affected:** `.aitask-scripts/lib/sitrep_todo.py`, `tests/test_sitrep_todo.sh`, `tests/test_sitrep_todo_format.py`, `aidocs/framework/sitrep.md`, `aitasks/t2335/t2335_4_skill_directions_code.md`

### Change Request 2 (2026-11-25 11:05)
- **Requested by user:** "a dropped direction stays untouched" was not true for its rank: `direction-rank` replaces the whole order, so a proposal that names only the directions it edits unranks the others (and deletes a rank-only block). Confirmed. The writer keeps its full-replacement contract; the guide and the sibling task must tell dropped edits apart from a change to the saved order.
- **Changes made:** the "Saving a proposal" section of `aidocs/framework/sitrep.md`, the t2335_4 task text and the `direction-rank` entry of the wrapper header now say the rank input is always the complete order to save (every currently ranked direction in its place, plus the new ones), and a ranked direction is left out only on an explicit request to unrank it. No code change. The existing test "--clear unranks everything (c held nothing else: its block is gone)" already pins the `UNRANKED:<slug>|-` behaviour.
- **Files affected:** `aidocs/framework/sitrep.md`, `.aitask-scripts/aitask_sitrep_todo.sh` (header comment), `aitasks/t2335/t2335_4_skill_directions_code.md`
