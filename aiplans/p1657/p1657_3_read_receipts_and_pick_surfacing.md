---
Task: t1657_3_read_receipts_and_pick_surfacing.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_4_live_endpoint_resolution_infrastructure.md, aitasks/t1657/t1657_5_aitask_note_skill_and_discoverability.md, aitasks/t1657/t1657_6_documentation_website_and_aidocs.md, aitasks/t1657/t1657_7_manual_verification_task_note_mailbox.md
Archived Sibling Plans: aiplans/archived/p1657/p1657_1_promote_ledger_block_substrate.md, aiplans/archived/p1657/p1657_2_inbox_format_and_ait_note_writer.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-03 23:58
---

# p1657_3 — Reading: read receipts and pick-time surfacing

## Context

`ait note` (t1657_2) can write a durable, attributed entry into any task's
`## Inbox`. Nothing reads it. This child closes the loop: unread notes are shown
when a task is picked, and a returning session is not re-shown what it already
consumed.

It costs **no new read path** — every pick entry point already reads the task
file when it resolves and summarises a task.

**Verified against the tree on 2026-09-03** (this plan was authored at parent
decomposition and had no prior verification). §"What the verification changed"
records the corrections.

## Read state is derived, not stored

Unread = entries whose `id` appears in **no** `note:read` receipt's `ids=` list.
Set-union semantics: order-free, same-second-safe, merge-friendly, and needs
**no** frontmatter field. Mirrors the `## Gate Runs` precedent — derive current
state from an append-only log rather than mutating a stored value.

Writer and reader share **one** parse (`lib/ledger_block.py:parse_blocks`); do
not add a second.

## What the verification changed

1. **`from_verified` is missing from the planned output tuple.** The
   presentation rule requires rendering `from=` as *claimed* and
   `from_verified=yes` as the only verified variant — but
   `INBOX_UNREAD:<id>|<from>|<at>|<base>|<dirty>` carries no such field, so a
   consumer could only get it by parsing the task file a second time, which the
   one-parse rule forbids. The tuple gains the field (§2).

2. **"Three trees, not one" is wrong for the template.**
   `lib/agent_skills_paths.sh:79 agent_authoring_template()` returns
   `.claude/skills/<skill>/SKILL.md.j2` unconditionally; `.agents/skills/` and
   `.opencode/skills/` hold only *stubs* that render from that same file. There
   is **one** template per skill and **no port** — and therefore no follow-up
   tasks for the other agent trees. What is genuinely multi-fold is the
   *goldens* (§6).

3. **Every code-agent pick entry point is in scope** — `aitask-pick`,
   `task-workflow` Step 3, **and** the two self-contained workflows
   `aitask-pickrem` / `aitask-pickweb`. Notes exist for code agents, and
   pickrem/pickweb are code-agent entry points that bypass Step 3 entirely; a
   task picked there would otherwise never surface its inbox. `aitask-resume`
   needs no work — it hands off to Step 3 and is covered for free. §7 carries
   the per-surface contract, including the one asymmetry the environment forces.

4. **Headless auto-acknowledge is kept**, after the shared-state objection ("an
   unattended run acknowledging a note burns it for the human it was addressed
   to") was put and declined. `mode=auto` is the audit trail.

Also confirmed: the `## Inbox` note on this task from the t1657_2 session is
**stale in its first half** — t1681 landed (`7c92412ef`) and
`aitask_note.sh:363` already carries the chained-with-status trap spelling. Its
second half (the receipt key set) is live and is honored below.

## Main steps

### 1. Derivation: `.aitask-scripts/lib/note_inbox.py` (new)

Built on `ledger_block.parse_blocks(text, "note")` — the t1657_1 seam — so the
reader cannot drift from the writer.

**The receipt schema is shared, not re-derived.** `parse_blocks` recognizes
block *shape* only. Validation currently lives entirely in
`board/aitask_merge.py:_validate_inbox`, which runs **only inside
`merge_body`** — so nothing validates an `## Inbox` on any read path. A reader
that trusted block shape alone would let a malformed local receipt
(`mode=sideways`, a stray `base=`, an unknown key) still carry `ids=` and hide a
real note, with no merge ever involved to reject it. That is precisely the
silently-vanished-note failure, arriving through the one route the merger cannot
see.

So this step is an **extraction, not a new implementation**:

- Move the note/receipt schema wholesale from `aitask_merge.py` into
  `lib/note_inbox.py`: `RECEIPT_NAME = "read"`, the key sets
  (`NOTE_KEYS_REQUIRED/OPTIONAL`, `MIGRATED_KEYS_*`, `RECEIPT_KEYS_*`), the
  identity/provenance regexes (`_NOTE_ID_RE`, `_LOCAL_TASK_RE`,
  `_XREPO_TASK_RE`, `_FULL_OID_RE`, `_BASE_SENTINELS`, `_ISO_DATE_RE`),
  `_keys_allowed`, `_validate_inbox_provenance` and `_validate_inbox` — exported
  as `validate_block(b) -> bool`. `aitask_merge.py` then sets
  `INBOX_SPEC.validate = note_inbox.validate_block`. `board/` → `lib/` is the
  existing import direction (`aitask_merge.py:38-50`), so this adds no
  inversion.
- **`_ISO_RUN_RE` is the one piece that cannot simply move**: line 446 is shared
  with `GATE_SPEC.validate` (line 504) as well as `_validate_inbox` (line 625).
  Promote it to `ledger_block.py` as `ISO_INSTANT_RE`, beside `iso_now()` which
  produces exactly that format, and import it from both consumers. One constant
  for one value set.
- **Make it a pure move.** No logic edits in the same commit.
  `test_inbox_union_roundtrip.py` and `test_merge_union_characterization.py`
  drive the real registered `INBOX_SPEC`; a pure move leaves both green with
  **zero test edits**. Needing to touch a test means the move was not pure.
- **The shared piece is the per-block predicate, not the bail policy** — the two
  callers dispose of a bad block differently, and must:
  - *merger*: "reject, never repair" — one bad block bails the whole body.
  - *reader*: **per-block**. Bailing the body here would hide every note in the
    file, the exact opposite of fail-safe. A malformed **receipt** is discarded,
    so its `ids=` count for nothing and the note it referenced stays **unread**.
    A malformed **note** is not rendered as a trustworthy claim but is reported
    (§2 `INBOX_MALFORMED`) — never silently dropped, or the operator cannot tell
    a hidden note from an absent one.
- `unread(text) -> list[LedgerBlock]` — notes that pass `validate_block` and
  whose `id` is in no **valid** receipt's `ids=` set, in file order.
- Importable module **and** a thin CLI (`unread <file>...`) so bash can call it
  through `lib/python_resolve.sh:resolve_python`, the convention
  `aitask_gate.sh:155 delegate_python` already uses.

### 2. `aitask_query_files.sh inbox <task-id> [<task-id>...]`

Follow the `cmd_inflight` shape (line 512, verified). All subcommands exit 0;
status is conveyed by output lines, never exit codes:

```
INBOX_UNREAD:<task-id>|<id>|<from>|<from_verified>|<at>|<base>|<dirty>
INBOX_MALFORMED:<task-id>|<line>|<name>   # block failed validate_block
NO_INBOX:<task-id>          # no ## Inbox section
NO_UNREAD:<task-id>         # section present, everything acknowledged
```

- `<base>` carries the **full object id** as stored — a machine-readable channel
  must never abbreviate. Only human-facing display may.
- `<from_verified>` is `yes` or empty. Empty means *not proven*, **never
  disproof**.
- **Accepts many ids in one call**, answering in one Python process. `aitask-pick`
  Step 2b summarises up to 15 tasks; a per-task invocation would put 15
  interpreter starts on every pick. The task-id prefix is what makes the batched
  output attributable.
- **This subcommand is strictly read-only.** It never appends a receipt. That is
  what makes it safe to call over a candidate list (§4).
- `INBOX_MALFORMED` is how a rejected block stays visible. A discarded receipt
  makes a note keep re-surfacing, and a discarded note is one nobody sees;
  without this line either is indistinguishable from "there was nothing there".
  Callers render it as a warning — it is diagnostic, never a note.
- Add to `show_help` and the header usage comment.

### 3. `ait note read` — the receipt writer

`ait note read <task-id> --by <id> --ids <csv> [--mode auto|explicit]`

**Receipt identity — one convention, enforced in source.** `--by` is **always
the target task's own id** (`t<N>` or `t<N>_<M>`): the reader is the session
working on that task, and the task id is the only durable identity available —
session names are ephemeral, which is the parent task's whole premise. Rather
than leaving this to each call site to remember, the writer **rejects** a `--by`
that does not equal the target: `READ_ERROR:by-must-be-target:<value>`. A
receipt naming its own task is legal — the writer refuses self-addressed
*notes*, not receipts. `--by` stays required (the merger requires the field, and
an explicit value keeps a receipt self-describing when quoted out of context),
but it can no longer carry an invented or unstable value.

**The append is conditional, and the decision is made inside the lock.** The
caller's unread query runs *outside* the append lock, so between query and
acquisition another session on this checkout can acknowledge the same notes — and
a plain retry after a transport failure re-sends the same ids. An unconditional
append would then write a second receipt covering ids already acknowledged.
Set-union derivation keeps the *derived state* right, but the file accumulates
redundant receipts and "re-run appends nothing" becomes untrue.

So `_note_append_inner`, already holding the lock, does the subtraction there —
the same in-lock re-read shape it uses for the id-collision check:

1. Re-parse the file's `## Inbox` and collect the ids covered by every **valid**
   receipt (`validate_block`, §1 — an invalid receipt covers nothing, so it must
   not suppress a real acknowledgement).
2. `remaining = requested − already_acknowledged`.
3. Every requested id must name a note present in this file; otherwise
   `READ_ERROR:unknown-note-id:<id>` and **no** append. The caller just displayed
   these from the same file, so an unknown id is a caller bug, not a sync gap.
   (This constrains only the *write* path — the merger still accepts a
   well-formed receipt whose note has not reached that checkout yet.)
4. `remaining` empty → release and return the typed no-op `READ_NOOP:<task-id>`.
   Nothing appended, nothing to retry.
5. Otherwise append **one** receipt whose `ids=` is exactly `remaining` — not the
   originally requested set, or the receipt would re-assert acknowledgements it
   did not make.

**Cross-checkout duplicates stay possible and stay accepted.** The append lock is
per-checkout; two PCs acknowledging the same note concurrently will produce two
receipts with overlapping `ids=`, and no local lock can prevent that. Set-union
makes it harmless. That case is out of scope for this subtraction and is verified
separately (§A) — do not confuse the two.

Implementation:

- Dispatch on `$1 == "read"` **before** target resolution in `main()`
  (`aitask_note.sh:455`): `note_id_normalize "read"` would otherwise fail with
  `bad-task-id:read`.
- Reuse `note_append_locked` / `_note_append_inner` unchanged, including the
  chained trap spelling at line 363 — `ait_note_rc=$?` **first**, then
  `ait_ledger_lock_exit_trap "$ait_note_rc"`. Since t1681 the seam detects a
  chained trap that drops the status and refuses to report success, so this is
  the correct form rather than merely the working one.
- Marker: `> **👁 note:read** id=<minted> by=t<id> at=<iso> mode=<m> ids=<csv>`.
  Exactly the key set the merger enforces
  (`aitask_merge.py:547 _RECEIPT_KEYS_REQUIRED`), and **no provenance keys** —
  `base` / `base_branch` / `base_mergebase` / `dirty` / `host` are rejected on a
  receipt. Adding a key without adding it to the merger's sets bails the
  cross-PC union to conflict markers (`test_inbox_union_roundtrip.py`).
- Single-line stdout contract, disjoint classes, so "is this note acknowledged?"
  is answerable from stdout alone:
  - *durable — a committed receipt exists:*
    `READ_RECORDED:<receipt-id>|<path>|<n-ids>` ·
    `READ_RECORDED_UNPUSHED:<receipt-id>|<path>|<n-ids>`
  - *no receipt needed:* `READ_NOOP:<task-id>`
  - *no receipt, note stays unread:* `READ_TARGET_MISSING:<id>` ·
    `READ_ERROR:<reason>`
  - *the one state needing a human:* `READ_ERROR:rollback-failed:<receipt-id>`

  `<n-ids>` is the size of `remaining`, not of the request — without it a caller
  cannot distinguish a full acknowledgement from a partial one, and the
  difference is exactly what the in-lock subtraction produces.

  **There is deliberately no `READ_RECORDED_UNCOMMITTED`.** See the transaction
  below: on this path that state is not merely degraded, it is the precise state
  that hides a note without durability.
- Extend `show_help`.

**Commit failure is a rollback, not a degraded success — and this is where the
read path deliberately diverges from the write path.**

An uncommitted receipt is the worst of both worlds: the in-lock subtraction above
now *sees* it, so the note is hidden locally and returns `READ_NOOP` on retry,
while nothing about it is durable — and if the working tree is later cleaned, the
note vanishes from view with no record that it was ever acknowledged. That is a
silently-vanished note, the one failure this child exists to prevent.

The asymmetry with `ait note` (write) is justified, not an inconsistency, and
should be commented as such at both sites:

| | on commit failure | why |
|---|---|---|
| note (write) | **keep**, report `NOTE_APPENDED_UNCOMMITTED` | the body is irreplaceable content; a retry would duplicate it |
| receipt (read) | **roll back**, report `READ_ERROR` | bookkeeping is reconstructible, and the retry is free and idempotent by construction |

The transaction:

- **The commit runs inside the lock on this path.** The write path deliberately
  releases first (`aitask_note.sh` persistence comment: contention is on the
  repo-global `.git/index.lock`, so spanning it only lengthens the window for a
  second `ait note`). A rollback cannot be done outside it, so the read path
  accepts the longer hold. The cost is bounded and worth stating: a concurrent
  `ait note` to this same task can exhaust its acquire budget and get
  `NOTE_ERROR:lock-unavailable` during a receipt commit. `ait note read` runs
  once per pick, so this is rare by construction.
- **Roll back by removing our own block by id — never by restoring a snapshot.**
  The task file is a shared multi-writer surface; between our append and the
  rollback another writer may legitimately have appended to it, and restoring
  pre-append content would silently destroy their work. Delete exactly the block
  whose `id=` is our minted receipt id, through the same
  `lib/ledger_block.py` seam, and leave every other block untouched.
- **A failed rollback is its own terminal state**, never swallowed: report
  `READ_ERROR:rollback-failed:<receipt-id>`, warn on stderr with the path-scoped
  recovery command, and leave the receipt in place. This is the one outcome that
  needs a human; reporting a plain `READ_ERROR` would say "nothing happened"
  while a note stays hidden.
- **Local commit succeeded, push failed → `READ_RECORDED_UNPUSHED`, not an
  error.** The receipt is durable in this repo and the local acknowledgement is
  correct; what is not yet true is that other checkouts know. Warn on stderr that
  they may re-show these notes until the data branch syncs — the accepted
  duplicate-display failure, stated rather than silent. (The write path treats
  push as silently best-effort; here the distinction is load-bearing enough to
  type.)

### 4. Display and acknowledgement are TWO SEPARATE STEPS

The crux of this child, and the easiest thing to get wrong.

"Never auto-actioned" governs the note's **content** — nothing in a note may
trigger work on its own. It does **not** govern read bookkeeping.

1. **Display** unread entries. **Displaying changes no state.**
2. **Acknowledge**, as its own step, only for the task that was actually
   **selected**.
3. **Fail-safe toward re-showing.** If the receipt append **or its commit**
   fails, entries stay unread and surface again next pick. A duplicate display is
   the acceptable failure; a silently vanished note is not. This holds without
   exception because commit failure rolls the receipt back (§3) — there is no
   half-state in which a note is hidden by a receipt that was never committed.
   The only surviving degraded case is **committed locally, not yet pushed**
   (`READ_RECORDED_UNPUSHED`): read here, unread on other checkouts until the
   data branch syncs, which is the re-show side and therefore safe.

#### Candidate listings are read-only indicators — never an acknowledgement

**A candidate list must never consume a receipt.** `aitask-pick` Step 2b/2c
summarises up to 15 tasks the user has *not* chosen. If displaying that list
acknowledged their notes, an agent that merely saw a task in a menu would hide
that task's notes from the agent that later picks it — the exact
silently-vanished-note failure this whole child exists to prevent.

The rule, stated in every listing site:

- **In a listing, run only `aitask_query_files.sh inbox` (read-only) and render
  a bare count** — e.g. "2 unread notes" beside the existing follow-up /
  approved-plan markers, where it belongs for the same reason: it changes which
  task a human picks.
- **Never render note bodies and never call `ait note read` from a listing.**
- Full content display *and* the acknowledgement step run only after a specific
  task is selected/entered (Step 0b, Step 2d→3, task-workflow Step 3, and the
  pickrem/pickweb Step 2 sites in §7).

This is a testable invariant, not a convention — see Verification.

### 5. Presentation — the trust posture is part of the feature

- attribute the sender, rendering `from=` as **claimed**; `from_verified=yes` is
  the only verified variant, and its absence is not disproof;
- show `base` / `at` / `dirty` so staleness is judgeable. **Display may
  abbreviate `base`**; the stored and emitted value stays the full object id, so
  abbreviating is a rendering choice, never a truncated record. `dirty=yes`
  warns that a *moment-relative* claim may already be stale in a way no SHA
  catches;
- never auto-action content; a note never bypasses the recipient's own planning,
  gates or review.

### 6. Skill edits

- `.claude/skills/aitask-pick/SKILL.md.j2` — a `surface_inbox(indent)` macro
  co-located with the existing `confirm_task_selection` macro (the convention at
  line 12), called from **Step 0b** Format 1 and Format 2; the acknowledgement
  branch inside it gates on `profile.headless` (interactive →
  `AskUserQuestion` "Acknowledge these N notes?"; headless → auto-ack with
  `mode=auto`). Plus the **read-only** batched count in Step 2b summaries and 2c
  option descriptions, per §4.
- `.claude/skills/task-workflow/SKILL.md` — **Step 3**, covering every skill that
  hands off there (`aitask-pick`, `aitask-resume`, explore, review, …). Same
  `profile.headless` gate.
- `.claude/skills/aitask-pickrem/SKILL.md.j2` and
  `.claude/skills/aitask-pickweb/SKILL.md.j2` — see §7.

### 7. The self-contained headless entry points

Both resolve exactly **one** task by id at their "Step 2: Resolve Task File"
(no candidate list at all), so §4's listing hazard does not arise there and the
insertion point is unambiguous: the end of Step 2, right after the selected-task
summary. Neither template references `profile.headless` — both are
unconditionally non-interactive by construction — so neither needs a Jinja gate.

They are **not** symmetric, and the asymmetry is forced by the environment
rather than chosen:

| | display notes | append receipt |
|---|---|---|
| `aitask-pickrem` | yes | yes, `--mode auto` |
| `aitask-pickweb` | yes | **no — impossible** |

- **`aitask-pickrem`** already uses `./ait git` and `aitask_pick_own.sh`
  (lines 86/139/349/489), so it can commit a receipt exactly as `aitask-pick`
  does. Add the display block plus an unconditional
  `ait note read <task-id> --by t<task-id> --ids <csv> --mode auto`.
- **`aitask-pickweb`** declares, as load-bearing invariants (lines 15/17/351):
  *"NO status updates"*, *"NO `./ait git`"*, and *"NO calls to
  `aitask_pick_own.sh`, `aitask_update.sh`, `aitask_archive.sh`, `./ait git`"*.
  It has no push access to the `aitask-data` branch and makes **no task-file
  writes whatsoever**. A receipt there could neither be written without breaking
  that invariant nor ever become durable. So pickweb **displays and does not
  acknowledge** — notes stay unread and surface again on the next attended pick.
  That is the fail-safe direction §4 already mandates, and it is the correct
  outcome rather than a gap: state it explicitly in the template and in the docs
  child (t1657_6) so it reads as a decision, not an omission.

### Post-phase (risk mitigations)

`pure_move_characterization` runs **first**, immediately after §1 lands and
before anything is built on the extracted module. The other two run after §7,
before the goldens are regenerated — a golden refresh taken before they land
would bake in whatever drifted.

- **`pure_move_characterization`** — with the schema extraction in place and
  **no other change**, run `tests/test_inbox_union_roundtrip.py` and
  `tests/test_merge_union_characterization.py` unedited. Both must pass. Editing
  either to make it pass falsifies "pure move" and means the extraction changed
  merge behavior — stop and reconcile rather than adjusting the test. Then
  confirm the guard is live by mutating one extracted predicate (e.g. drop
  `mode` from `RECEIPT_KEYS_REQUIRED`) and checking the suite **fails**.
- **`listing_readonly_invariant`** — add the §C before/after byte-comparison
  test over a batched `inbox` query across N candidate task files. Then inject
  the mutant (a `note read` call on the listing path), confirm the test
  **fails**, and remove it. A check that cannot fail is not a check.
- **`cross_surface_render_assertions`** — add the §D per-entry-point render
  assertions, each paired with its negative control (the interactive branch
  absent under `remote`; `note read` absent entirely from `aitask-pickweb`), so
  a block that drifts to the wrong step or the wrong profile fails rather than
  surviving a golden refresh.

## Goldens

Regenerated with **`skill_template.py` stdout** — not by copying a rendered
variant, which is not byte-equal:

```bash
source .aitask-scripts/lib/python_resolve.sh && PYTHON="$(require_ait_python)"
for p in default fast remote; do
  for s in aitask-pick aitask-pickrem aitask-pickweb; do
    "$PYTHON" .aitask-scripts/lib/skill_template.py \
      .claude/skills/$s/SKILL.md.j2 aitasks/metadata/profiles/$p.yaml claude \
      > tests/golden/skills/$s/SKILL-$p-claude.md
  done
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/SKILL.md aitasks/metadata/profiles/$p.yaml claude \
    > tests/golden/procs/task-workflow/SKILL-$p.md
done
```

**Review the diff rather than rubber-stamping it** — the intended diff should
match exactly what changed; an unrelated diff is a regression. See "Regenerate
goldens after any `.md.j2` or closure edit" in
`aidocs/framework/skill_authoring_conventions.md`.

## Verification

### A. Acknowledgement lifecycle — one test per transition

New `tests/test_note_read_receipts.sh`, alongside `test_note_append.sh`:

1. first display → shown, still unread
2. deferred acknowledgement → shown again on the next query
3. acknowledgement → receipt appended, `mode=explicit`, exact key set
4. returning session → not shown
5. **injected receipt-append failure → still unread** — through the documented
   seam `AIT_NOTE_FAIL_AFTER_APPEND` (`aitask_note.sh:402`), plus a
   lock-unavailable case for the genuine pre-append direction

**Commit-failure transaction.** Inject a commit failure (a held
`.git/index.lock`, or a documented seam mirroring `AIT_NOTE_FAIL_AFTER_APPEND`)
and assert the whole contract, not just the exit status:

- outcome is `READ_ERROR`, **not** any `READ_RECORDED*`;
- **the next local `inbox` query reports the note `INBOX_UNREAD`** — the
  assertion that actually pins the fail-safe rule, and the one a rollback bug
  breaks while the exit status still looks right;
- a subsequent `note read` for the same ids **appends** (it must not return
  `READ_NOOP`);
- the receipt block count is back to its pre-call value, and `git status` shows
  the task file unmodified.

**Rollback must not damage a concurrent writer** — the case a snapshot restore
would fail: append a *second* writer's block to the same file after our receipt
lands but before the rollback, then force the commit failure. Our receipt is
gone; **their block is intact**. Assert their block explicitly, not just our
receipt's absence.

**Rollback failure is surfaced, never swallowed** — make the removal itself fail
and assert `READ_ERROR:rollback-failed:<receipt-id>` plus the stderr recovery
hint, with the receipt still on disk. This is the state that must reach a human.

**Push failure is durable-but-unsynced, not an error** — commit succeeds, push
fails: outcome is `READ_RECORDED_UNPUSHED`, the receipt is committed, and the
local `inbox` reports `NO_UNREAD`.

**Malformed receipts, driven through the real `unread` query** — not through the
merger, which is the point: these must be rejected on a purely local read path
where no merge ever runs. For each of a receipt carrying provenance (`base=`),
an out-of-vocabulary `mode=sideways`, an unknown key, a non-`t<N>` `by=`, and a
malformed `ids=` member:

- the referenced note is still reported `INBOX_UNREAD` — **the note stays
  visible**;
- the bad block is reported `INBOX_MALFORMED` — it does not vanish silently;
- the rest of the section still parses (per-block rejection, **not** the
  merger's bail-the-body).

Plus the mirror case: a malformed **note** block is reported `INBOX_MALFORMED`
and is not rendered as a trustworthy claim, while valid sibling notes in the
same section are still returned.

**Same-checkout idempotency — the in-lock subtraction.** These exercise the
writer directly, not the derived state, because the derivation would look correct
even while the file accumulated duplicates:

- plain retry — `note read` twice with identical ids: second call returns
  `READ_NOOP`, and the **receipt-block count in the file is unchanged** (count
  blocks, do not merely re-check `NO_UNREAD`);
- partial overlap — acknowledge {A}, then call with {A,B}: exactly one new
  receipt whose `ids=` is `B` alone, and `READ_RECORDED:…|1`;
- the query→lock window — acknowledge {A} from a second process *after* the
  unread query but before the acknowledging call, then acknowledge {A}: the
  outcome is `READ_NOOP`, not a duplicate;
- an **invalid** receipt covering {A} must **not** suppress a real
  acknowledgement of {A} — it covers nothing, so the append proceeds;
- unknown id → `READ_ERROR:unknown-note-id`, file byte-identical afterwards.

**Cross-checkout duplication is accepted, and tested as such** — a separate case,
never folded into the above: two receipts with overlapping `ids=` authored as if
by two PCs must union cleanly and leave the note read exactly once in the derived
state. The local subtraction is explicitly *not* expected to prevent this.

**Shared-contract guard.** One test asserts `aitask_merge.INBOX_SPEC.validate is
note_inbox.validate_block` — object identity, so the two can never drift into
separate copies. A second feeds the same malformed corpus to both the merger and
the reader and asserts they agree on *validity* while differing only in
disposition (merger bails the body; reader rejects the block).

### B. Receipt identity

- `--by` equal to the target → recorded.
- `--by` naming any **other** task → `READ_ERROR:by-must-be-target`, and **no**
  receipt on disk (assert the file is unchanged, not merely that the exit was
  non-zero).
- `--by` omitted → pre-append error, no receipt.
- A grep-based call-site check: every `ait note read` invocation in
  `.claude/skills/**` passes `--by` bound to the same task id it passes as the
  target. This is what stops the four call sites drifting.

### C. Listings are read-only

- Batch/attribution: one `inbox` call over three task ids returns each id's own
  `NO_INBOX` / `NO_UNREAD` / `INBOX_UNREAD` lines and never cross-attributes.
- **The invariant test:** run the batched `inbox` query over N candidate task
  files, then assert **zero** receipts were appended to any of them (byte-compare
  each file before/after). This must be able to fail — introduce the mutant
  (a `note read` call inside the listing path) and confirm it does.
- Render-level: the rendered `aitask-pick` Step 2b/2c region contains no
  `ait note read` for any of the three profiles.

### D. Headless entry points — behavior, not just rendering

Goldens are render-level and can pass while a self-contained workflow omits or
misplaces the runtime behavior, so this splits by what is mechanically decidable:

- **Mechanism (automated).** Drive the real helpers against a fixture task for
  each headless shape: `ait note read … --mode auto` appends **exactly one**
  receipt with `mode=auto`; re-running it over the same ids returns `READ_NOOP`,
  leaves the receipt-block count unchanged, and keeps `inbox` reporting
  `NO_UNREAD` (§A carries the full idempotency matrix — this is the headless
  instance of it). This is the machinery all three headless surfaces invoke.
- **Per-entry-point render assertions (automated), each with its negative
  control** — a golden diff alone would not catch a block landing in the wrong
  step:
  - `aitask-pick` @ `remote`: auto-ack branch present **and** the interactive
    `AskUserQuestion` acknowledgement absent; the reverse for `default`/`fast`.
  - `task-workflow` @ `remote`: same pair at Step 3.
  - `aitask-pickrem`: `note read … --mode auto` present, inside Step 2, and no
    `AskUserQuestion` anywhere in the added block.
  - `aitask-pickweb`: the display block present **and** `note read` absent
    entirely — the negative control that pickweb never writes.
- **Live agent behavior (manual).** Whether an agent actually performs the
  procedure unprompted is not mechanically decidable from a markdown template;
  that is what `manual_verification` is for. Extend **t1657_7**'s checklist —
  which already carries the generic headless item — with one item per entry
  point: pick a note-bearing task under `remote`, under `aitask-pickrem`, and
  under `aitask-pickweb`, and confirm notes are displayed, that exactly one
  `mode=auto` receipt exists afterwards for the first two, and that **none**
  exists for pickweb (so its notes still surface on the next attended pick).

### E. Suite

- `bash tests/test_inbox_union_roundtrip.py` (the `RECEIPT_NAME` import must not
  move the merger's behavior)
- `bash tests/test_skill_render_aitask_pick.sh`
- `bash tests/test_skill_render_aitask_pickrem.sh`
- `bash tests/test_skill_render_aitask_pickweb.sh`
- `bash tests/test_skill_render_task_workflow.sh`
- `./.aitask-scripts/aitask_skill_verify.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests`
- end-to-end: `ait note <target> --from … --text …`, then pick the target twice
  with an acknowledgement in between, and confirm it surfaces **exactly once**.
  This task's own live inbox note is the natural fixture.

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9. Two coordination items:

- **t1657_6 (docs)** must record the pickweb display-only asymmetry as a
  decision, alongside the cross-PC receipt-model decision.
- **t1657_7 (manual verification)** gains the per-entry-point items in §D.

## Risk

### Code-health risk: **medium**

- Four skill surfaces now carry near-identical inbox blocks, which can drift
  independently · severity: medium · → mitigation: inline post-phase
  `cross_surface_render_assertions` — the §D render assertions pin each
  surface's block by content and position, so a drifting or misplaced copy fails
  rather than passing on a golden refresh
- Goldens across four templates and three profiles drift independently ·
  severity: low · → mitigation: the four `test_skill_render_*` suites +
  `aitask_skill_verify.sh`
- The read path holds the note lock across its git commit, diverging from the
  write path's deliberate release-then-commit; a concurrent `ait note` to the
  same task can exhaust its acquire budget during that window · severity: low ·
  → mitigation: bounded by construction (`ait note read` runs once per pick) and
  documented as a stated tradeoff at both sites rather than as an oversight
- Extracting the whole note/receipt schema out of `aitask_merge.py` — a
  load-bearing multi-writer merge path — is a substrate promotion, not a
  one-symbol move; a subtle behavior change there corrupts task data on merge ·
  severity: high · → mitigation: inline post-phase `pure_move_characterization`
- Promoting `_ISO_RUN_RE` to `ledger_block.ISO_INSTANT_RE` changes a constant
  `GATE_SPEC` also depends on · severity: medium · → mitigation: covered by the
  same post-phase — the gate half of `test_merge_union_characterization.py` must
  stay green with no edits

### Goal-achievement risk: **medium**

- The acknowledgement model is specified per-transition and each transition has
  a test, so "surfaces exactly once" is falsifiable rather than asserted.
- A listing site could silently consume receipts, hiding notes from the agent
  that actually picks the task · severity: high · → mitigation: inline
  post-phase `listing_readonly_invariant` — §C's before/after byte-comparison
  with a forced-failure mutant, so the invariant is executable rather than
  documented
- A malformed receipt on a purely local read path could hide a real note before
  any merge rejects it · severity: high · → mitigation: the shared
  `validate_block` contract (§1), the malformed-receipt corpus driven through
  the real `unread` query, and the object-identity guard (§A)
- The unread query runs outside the append lock, so a retry or a concurrent
  same-checkout acknowledgement could write a redundant receipt · severity:
  medium · → mitigation: the in-lock subtraction and `READ_NOOP` (§3), verified
  by the §A idempotency matrix — which counts receipt blocks rather than
  re-checking derived state, since set-union would mask the duplication
- An uncommitted receipt would hide a note locally with nothing durable to show
  for it — the subtraction makes it permanent via `READ_NOOP` · severity: high ·
  → mitigation: the §3 commit-failure rollback, asserted in §A by the *next
  local query reporting the note unread* rather than by an exit status
- `aitask-pickweb` deliberately never acknowledges · severity: low ·
  → mitigation: it fails toward re-showing, is asserted by a negative control in
  §D, and is recorded as a decision in `aidocs/` (t1657_6)
- Residual: the receipt model assumes a note consumed on one PC should not
  resurface on another · severity: low · → mitigation: recorded as a decision in
  `aidocs/` (t1657_6)

### Planned mitigations
- timing: post-phase | name: pure_move_characterization | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: schema extraction silently changing merge behavior on a multi-writer data path | desc: run the two merge characterization suites unedited against the extracted module, then mutate an extracted predicate to prove the guard can fail
- timing: post-phase | name: listing_readonly_invariant | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: a listing site silently consuming receipts | desc: byte-compare candidate task files before/after a batched inbox query, with a forced-failure mutant proving the check can fail
- timing: post-phase | name: cross_surface_render_assertions | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: four near-identical inbox blocks drifting across surfaces | desc: per-entry-point render assertions pinning each surface's block by content and position, each with its negative control
