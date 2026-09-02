---
Task: t1657_2_inbox_format_and_ait_note_writer.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_3_read_receipts_and_pick_surfacing.md, aitasks/t1657/t1657_4_live_endpoint_resolution_infrastructure.md, aitasks/t1657/t1657_5_aitask_note_skill_and_discoverability.md, aitasks/t1657/t1657_6_documentation_website_and_aidocs.md, aitasks/t1657/t1657_7_manual_verification_task_note_mailbox.md
Archived Sibling Plans: aiplans/archived/p1657/p1657_1_promote_ledger_block_substrate.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-02 09:19
---

# p1657_2 — Durable lane: `## Inbox` format and the `ait note` writer

## Context

t1657 gives tasks a durable mailbox so a task can be told something even when
nobody is working on it. t1657_1 landed the shared seam
(`lib/ledger_block.sh` / `lib/ledger_block.py`, and the multi-section union in
`.aitask-scripts/board/aitask_merge.py`). **This child is the product**: the `## Inbox` entry
format and the `ait note` writer, built *on* that seam.

This plan was re-verified against the tree on 2026-09-01. Every seam API it
names exists as documented. Two findings came from the verification pass
(F1, F3), five from the first plan review (F5–F9), four from the second
(F10–F13), two from the third (F14–F15), one from the fourth (F16) and one from
the fifth (F17); all fifteen changed the plan.

---

## Verification pass (2026-09-01, this session)

| plan claim | verified |
|---|---|
| `ait_ledger_append_section <file> <hdr> <cmt> <marker> <body> [create_before] [append_at]` | exact — `lib/ledger_block.sh:133` |
| `ait_ledger_lock_acquire <ns> <key> <reclaim_label> <fail_label>` — **two** labels | exact — `:51` |
| `ait_ledger_marker <ns> <name> <icon> [k=v ...]` → `> **<icon> <ns>:<name>** k=v …` | exact — `:106` |
| `append_to_section` / `render_block` / `parse_blocks` / `atomic_write` | exact — `lib/ledger_block.py` |
| `SectionSpec` (6 fields), `GATE_SPEC`, `REGISTERED_SPECS` | exact — `.aitask-scripts/board/aitask_merge.py:461/500/517` |
| `aitask_gate_record.sh` as the shape model | exact — 91 lines |
| 5 whitelist touchpoints | all present |
| `note` free as an `ait` verb; `show_usage` "Task Management" block | free; block at `ait:40` |
| dogfood target (t357 note in the parent task file) | present, below the `---` |
| `aitask_note.sh`, `tests/test_note_append.sh` | absent — genuinely new |
| **`resolve_task_file` at `lib/task_utils.sh:1184`** | **stale — it is `:1362`** (F2) |

### F1 — The plan omitted the merge-union registration entirely

t1657_1's "Notes for sibling tasks" assigns it to **this** task by name:

> **t1657_2 registers the second spec.** Add a `SectionSpec` to
> `REGISTERED_SPECS` … **ahead of** `GATE_SPEC` … identity `(id,)` — **not**
> `(name, …)`, since one sender sends many notes — and order by `(at, id)`.

And two tests in `tests/test_merge_union_characterization.py` carry docstrings
naming this task as their owner: `test_divergent_foreign_section_conflicts_the_whole_body`
("Update this test THERE") and `test_one_sided_foreign_section_conflicts_the_whole_body`
("the common concurrent-append case for t1657_2 … Update in t1657_2").

The previous revision of this plan had **no step for any of it**. Without the
registration `## Inbox` stays an *unregistered* section, so it lives in the
merge driver's prose head — and the measured consequence is that **one PC
appending a note while the other does not conflicts the entire task-file body**.
That is the single most common concurrent case for a mailbox, and it directly
violates the parent's non-negotiable that task data is a multi-writer branch
whose entry format must be merge-friendly. New **step 8**.

### F3 — `pin_section_order` covered only one of the two creation orders

`ait_ledger_append_section` has **three** paths, and which one runs depends on
what already exists in the file:

| situation | path taken |
|---|---|
| Gate Runs exists, no Inbox | anchor-insert (`create_before`) — `:150` |
| Inbox exists | `append_at="section_end"` — `:167` |
| neither exists | EOF create — `:194` |

The mitigation as previously written ("append a note, **then** a gate block")
exercises only the *third* path: the Inbox is created at EOF because its anchor
is absent, and the ordering then holds by arrival order rather than by
`create_before`. The reverse order — **gate block first, then a note** — is the
one that actually exercises the anchor-insert branch the whole design rests on.
Both orders are now pinned, on both backends.

### F5–F9 — Review findings (raised at plan review, all verified, all addressed)

- **F5 (path).** There is **no top-level `board/`** in this repo; the live module
  is `.aitask-scripts/board/aitask_merge.py` (tests reach it by putting that
  directory on `sys.path`, then `from aitask_merge import merge_body`). The
  previous revision wrote the seam plan's shorthand `board/aitask_merge.py`,
  which as a literal path would create an unused module and leave the Inbox
  unregistered. Corrected throughout — step 8 and Verification now name the full
  path.
- **F6 (commit boundary).** The lock is released before `task_git commit`, so an
  index race or commit failure can leave a note appended-but-uncommitted. The
  previous revision's only failure outcome was `NOTE_ERROR:<reason>`, which
  carries **no id** — so a caller cannot tell "nothing happened" from "it is on
  disk", and a retry duplicates the note. Fixed with an id-bearing outcome in
  §2/§CLI, reusing the framework's existing `*_UNCOMMITTED` convention
  (`aitask_gate.sh:1060,1081`).
- **F7 (validation).** Validating only that `at=` is ISO-shaped contradicts the
  task's "parsers reject, never repair" rule: a block with a malformed or
  missing `id` would be accepted and unioned. Full structural contract now in
  §8.
- **F8 (sender proof).** `from_verified=yes` had a stated rule and no mechanism —
  and the note append lock is keyed on the **target**, so it proves nothing
  about the claimed sender. Concrete algorithm now in §5, reusing
  `lock_anchor_is_self`.
- **F9 (collision test).** A CSPRNG stubbed to one fixed value can never yield a
  distinct suffix, so the planned re-mint assertion would hang rather than pass.
  Split into a scripted collide-then-unique sequence for the *recovery* path and
  a permanently-fixed generator for the *bound* — see Verification.

### F10–F13 — Second review round (all verified, all addressed)

- **F10 (sender id form).** Measured, and worse than "can resolve the wrong
  path" — it silently resolves **nothing**:

  | call | result |
  |---|---|
  | `aitask_lock.sh --check 1669` | `task_id: 1669` |
  | `aitask_lock.sh --check t1669` | **empty** |
  | `resolve_task_file 1657_2` | the path |
  | `resolve_task_file t1657_2` | `Error: No task file found` |

  The stored form is t-prefixed (`from=t349`), so feeding it straight to
  `--check` returns empty, which §5 reads as "no lock record" and **omits**
  `from_verified`. Fail-closed, so not a hole — but `from_verified=yes` would
  then be written *essentially never*, and a test suite covering only the
  negative cases would pass on a dead feature. New §0 pins one canonical form.
- **F11 (primary branch).** §3 said "when HEAD is off the primary branch" without
  saying how to find it. `detect_primary_branch()` already exists at
  `lib/git_utils.sh:20` and handles `origin/HEAD` → `main` → `master` → `main`.
  Reuse it; hardcoding `main` would compute the wrong merge base (or none) in a
  master-default repo. It has a Python twin (`lib/desync_state.py`) the file's
  own comment says to keep in sync — this task only reads, so no twin edit.
- **F12 (recovery scope).** `NOTE_APPENDED_UNCOMMITTED` said a later commit of
  `aitasks/` picks the note up. That is a **blanket path**, and the parent's
  non-negotiable is path-scoped commits only — a blanket recovery would sweep
  another session's uncommitted task-file edits into this note's commit. The
  outcome now carries a `<path>`-scoped recovery command (§2b).
- **F13 (dogfood provenance).** Verified: the t357 note records
  `aitasks main 451dd3af7 / aitask-data eab147468` — **9-hex abbreviations**,
  violating the full-oid invariant — and a date-level timestamp only. Both
  abbreviations still resolve uniquely today
  (`451dd3af789cd4aff06f38465e16357f815e28b4`,
  `eab147468776e9a0b362e8578ac29a319c3d6c1a`), so expansion is possible now and
  may not be later. **Additional wrinkle the review did not name:** the sender is
  **cross-repo** (`t357` in `thinking_app`), and `#` is not in `_NAME_CHARS`
  (`ledger_block.py:49`), so `note:thinking_app#357` is not a legal marker name
  at all. Full migration mapping in §7.

### F14–F15 — Third review round (both verified; both gaps the F10/F13 fixes introduced)

- **F14 (cross-repo sender has no writer).** Correct, and self-inflicted: §7's
  dogfood entry claims `from=thinking_app#357`, while §0's `note_id_normalize()`
  accepts only local ids and §5's proof helpers are defined over that form. No
  path could emit the specified record, so the step as written forced either a
  hand-edit of a section whose comment forbids exactly that, or a silent
  provenance downgrade. Fixed by a dedicated, explicitly-scoped `--migrate`
  path (**§0b**) that omits `from_verified` structurally rather than by policy.
- **F15 (provenance unvalidated).** Also correct: §8's "full structural"
  validator covered `id` / `at` / sender / receipt fields and **not** `base`,
  `base_branch`, `base_mergebase`, `dirty`, `host`. A block carrying an
  abbreviated `base` would therefore pass merge validation and union — the exact
  ambiguity §3 exists to prevent, arriving by the one route writer-side tests
  cannot see (a block written on another PC). Rules and malformed-provenance
  merge cases added to §8.

### F16 — Fourth review round (verified; a gap the F15 fix introduced)

- **F16 (degraded `dirty`).** Correct, and self-inflicted again: F15's table made
  `dirty` unconditionally `yes|no` on every ordinary note, while §3 has always
  permitted `base=none` for a no-repository writer. In that case `no` fabricates
  a clean-state claim, `yes` is equally unsupported, and omission was rejected —
  so the contract was unsatisfiable. Fixed with `dirty=unknown`, using §3's own
  sentinel convention rather than a second one. **Measured** that the trigger is
  `base=none` alone: on an unborn branch (`base=unknown`) `git rev-parse HEAD`
  fails but `git status --porcelain` still reports, so `dirty` is observable and
  `unknown` there would be a false disclaimer.

### F17 — Fifth review round (verified; a gap the F12 fix introduced)

- **F17 (recovery output channel).** Correct, and self-inflicted: F12 added a
  path-scoped recovery command to the `_UNCOMMITTED` outcome but never assigned
  it a channel. On stdout it would make a field-position-parsed record
  multi-line; omitted, the outcome promises guidance it never gives. The
  framework already resolves this exact tension — `warn()` → stderr
  (`lib/terminal_compat.sh:21`), status word → stdout, and
  `materialize-active`'s `MATERIALIZED_UNCOMMITTED` emits **both**
  (`aitask_gate.sh:1081`). Adopted verbatim: one structured line on stdout, the
  hint as a `warn`. `<reason>` is sanitized at the write site for the same
  guarantee — it sits inside a `|`-delimited single line.

### F18–F20 — Implementation review (all CONFIRMED by measurement, all fixed)

Raised against the shipped code, not the design. Each was reproduced before
being fixed.

- **F18 (migration inputs unvalidated).** The `--migrate` path checked only that
  `--claimed-at` / `--base` were non-empty, then wrote them verbatim. Measured:
  `--base 451dd3af7` produced a **committed** Inbox block that
  `INBOX_SPEC.validate` then rejected (`valid=False`) — a local migration
  becoming a cross-PC conflict source, with the block already in git. The writer
  now mirrors the merger's rules *before* the append: full oid or a permitted
  sentinel, date-shaped `claimed_at`, `base_branch` iff the base is real. The
  asymmetry was the defect: whatever the writer commits, every other PC
  re-validates.
- **F19 (no argument matrix).** Option parsing was last-one-wins with no arity
  checks. Measured: `--text a --file b.txt` emitted the file body and silently
  dropped the inline text; `--migrate --from X` silently ignored a sender the
  caller believed was attributed. Now: exactly one body source, no duplicate
  flags, and the two modes mutually exclusive. Duplicate checks run **before**
  the arity rule, so `--text a --text b` names the duplicate rather than the
  arity violation.
- **F20 (unknown keys accepted).** `_validate_inbox_provenance` special-cased
  only `migrated=yes` and otherwise permitted arbitrary keys. Measured:
  `migrated=no`, `claimed_at=garbage` on an ordinary note, and `bogus=1` all
  unioned. Each variant now has an exact allowed key set, and `migrated` is
  keyed on **presence** rather than `== "yes"` — a block claiming the variant
  without satisfying it is malformed, not an ordinary note.

### F21 — Silent-exit sweep (CONFIRMED and fixed, plus one found by sweeping)

- **F21a (valueless flag).** Every value-taking option ran `shift 2`
  unconditionally. Measured: `ait note 700 --from` exited **1 with empty
  stdout** — `shift 2` fails with one argument left and `set -e` tears the
  script down. That breaks the file's own "exactly ONE line on stdout, always"
  contract and leaves a caller unable to tell malformed input from a died
  process. Each flag now checks for its value first.
- **F21b (lock exhaustion) — not reported; found by sweeping the surface for the
  same shape.** Lock exhaustion produced the identical `rc=1` / empty-stdout
  signature, because the seam's `ait_ledger_lock_acquire` calls `die`. `die`
  cannot be caught in-process, so the locked append now runs in a **subshell**
  whose status is inspected and converted to
  `NOTE_ERROR:lock-unavailable:<key>`. The seam's diagnostic still reaches
  stderr, and an inner typed error (collision exhaustion) still wins over the
  generic one.

  That subshell needs **two cleanup scopes**: its EXIT trap must not remove the
  id/handoff files, because it fires exactly when the parent still needs them —
  the first version of this fix broke the happy path that way.

### F22 — Post-append failure window (CONFIRMED; plus a masking defect found proving it)

Both introduced by the F21b subshell fix — a reminder that a fix to one
failure-reporting path can open another.

- **F22a (id published too late).** `_note_append_inner` wrote the handoff id
  **after** `ait_ledger_lock_release_checked`, which genuinely can `die`:
  `stale_lock_release` returns 1 on a retained lock or a retained guard. The
  parent then saw a bare failed subshell for a note **already on disk** and
  reported `NOTE_ERROR:lock-unavailable` — a pre-append error for an appended
  note, so a caller retries and duplicates it. That is precisely the
  disjointness F6 established. The id is now published the instant the append
  lands, and **the id file is the witness**: non-empty means the note exists
  whatever failed afterwards, and the outcome becomes
  `NOTE_APPENDED_UNCOMMITTED:<id>|<path>|lock-release-failed`.
- **F22b (the trap masked it) — found while proving F22a, and worse.** The EXIT
  trap installed inside the locked section chained as
  `note_cleanup_body; ait_ledger_lock_exit_trap`. That seam trap reads `$?` on
  entry *precisely* to preserve the dying command's status — so running any
  command in front of it resets `$?` to that command's own status. **Measured:**
  a death inside the locked section exited 0 and the wrapper emitted
  `NOTE_APPENDED` for a wedged lock — a failure reported as success, which is
  strictly worse than the wrong-error-code F22a describes. The trap now captures
  the status first and restores it with a throwaway subshell before delegating.

Injected through a documented `AIT_NOTE_FAIL_AFTER_APPEND` seam: forcing a real
release failure from outside is not deterministic, and an untested blocking path
is worth less than an injected one. Reverting the trap order fails **5**
assertions, so the guard discriminates rather than decorates.

### F4 — Concurrent session on the seam (no edit collision)

**t1669** ("Validate the ledger-block namespace before interpolating it into a
regex") is `Implementing` **right now** under a live session (pid 2320448,
`/aitask-pick 1669`). It edits `build_marker_re` / `build_marker_search_re` in
`lib/ledger_block.py` — a file **this task does not touch**. Namespace `note` is
a plain identifier and stays valid under its fix, so the two are non-breaking in
either landing order. Stated so it is a checked fact rather than a surprise.

---

## Main steps

### 0. One canonical task-id representation (F10)

Two forms exist in the tree and they are **not** interchangeable — measured in
F10 above. Pin all three roles explicitly; this is the first thing the writer
does, before any helper call.

| role | form | example |
|---|---|---|
| **CLI input** (`<target>`, `--from`) | liberal — accept both | `349`, `t349`, `1657_2`, `t1657_2` |
| **lookup** — every helper call | **bare** | `349`, `1657_2` |
| **stored** — marker name and `from=` | **`t`-prefixed** | `t349`, `t1657_2` |

- One `note_id_normalize()` strips a single leading `t` and validates the rest
  against `^[0-9]+(_[0-9]+)?$`; a value that fails is `NOTE_ERROR:bad-task-id`
  (never silently passed through to a helper that answers "empty").
- One `note_id_render()` produces the stored `t`-prefixed form. Apply
  normalize **once** at the boundary; every internal call takes the bare form,
  every written field takes the rendered one.
- Storing the `t`-prefixed form is deliberate: it is the entry format the task
  pins, it makes the marker self-describing, and `t1657_2` matches
  `_NAME_CHARS` (`[A-Za-z0-9_]+`) so it is a legal marker name.

**`--from` is local-only.** `note_id_normalize()` accepts nothing else, and the
sender-proof helpers (§5) are defined over the normalized local form. A
cross-repo sender cannot be proven from here by construction, so it must not
travel the normal send path at all.

### 0b. The migration path — the only writer of an external sender (F14)

§7's dogfood entry claims `from=thinking_app#357`, which §0 forbids on `--from`.
Without a dedicated path the implementation would have to hand-edit a section
whose own comment says *"Do not edit by hand; use `./ait note`"*, or silently
downgrade the provenance. So give it one narrow, explicit verb:

```
ait note <target> --migrate --claimed-from <ref> --claimed-at <date> \
                  --base <oid> [--base-branch <b>] --file <body>
```

- `--claimed-from <ref>` accepts a local id **or** a cross-repo reference,
  validated against the canonical pattern
  `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$`
  (`aidocs/framework/cross_repo_references.md:151`; the `t` after `#` is
  tolerated). Stored verbatim in `from=`; the **marker name** is the `t<id>`
  part, since `#` is not a legal name char.
- **`from_verified` is omitted structurally, not by policy** — this path never
  calls the §5 proof, so there is no branch that could write it.
- `migrated=yes` always.
- Provenance is **supplied, never captured**: `--base` / `--base-branch` take
  the historical values, and no `dirty` / `host` is written, because neither was
  ever observed. Capturing today's HEAD would misrepresent exactly the
  stale-context claim the entry exists to record.
- `--claimed-at` records the original's own (date-level) timestamp; `at=` and
  `id=` are this entry's, minted now.

**Scope:** this is a migration verb for content that predates the mailbox, not
general cross-repo messaging — which stays out of scope beside cross-host live
delivery. It is exercised by §7 and pinned by a test asserting the exact emitted
record.

### 1. Register the `## Inbox` section with the bash seam

Section constants (mirroring `gate_ledger.SECTION_HEADER` / `SECTION_COMMENT`):

```
## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->
```

Appends use `create_before="## Gate Runs"` and `append_at="section_end"`, so the
Inbox always lands **above** the gate ledger. This is the load-bearing
invariant: both gate-append paths (`_gate_append_locked`,
`gate_ledger.append_block`) append at EOF, so an Inbox placed *after* would
silently capture every future gate block.

### 2. `.aitask-scripts/aitask_note.sh` (new)

Shape it on `aitask_gate_record.sh` — read that first. **One difference from
that model:** `aitask_gate_record.sh` is best-effort and always exits 0; `ait
note` is **authoritative** and reports failure (`NOTE_ERROR:<reason>`, non-zero).

Order of operations:

1. `resolve_task_file "$target"` (`lib/task_utils.sh:1362`); missing →
   `NOTE_TARGET_MISSING:<id>`.
2. Refuse self-addressed → `NOTE_SELF:<id>`.
3. **Capture provenance BEFORE the append** (§3).
4. `ait_ledger_lock_acquire note "$key" "<reclaim label>" "<fail label>"` —
   **two distinct labels**, or the reclaim warning silently changes wording.
5. Mint the id and verify it is absent from the section (§4).
6. Build the marker via `ait_ledger_marker`; render the body (§5); append via
   `ait_ledger_append_section`.
7. Release the lock, then `task_git add -- "$file"`, path-scoped commit,
   best-effort `task_push` — exactly as `aitask_gate_record.sh` does.
8. Print `NOTE_APPENDED:<note-id>|<path>` — note-id leads; it is the join key.

**The lock does not span the commit, and the failure outcome must carry the id
(F6).** Holding the note lock across `task_git commit` would not help: the
contention is on the repo-global `.git/index.lock`, not on the per-task key, so
spanning it only lengthens the window in which a second `ait note` to the same
task exhausts its 20×0.3s acquire budget. What actually has to be right is the
**reporting**: once the append has landed, the note is durable on disk and owns
an id, so a commit failure must never be reported as `NOTE_ERROR:` — that reads
as "nothing happened", and the caller's retry then appends a *second* note.

Emit instead, reusing the framework's existing convention for exactly this state
(`aitask_gate.sh:1060,1081` — `MATERIALIZED_UNCOMMITTED` / `NOOP_UNCOMMITTED`):

```
NOTE_APPENDED_UNCOMMITTED:<note-id>|<path>|<reason>
```

Non-zero exit (the write is not fully persisted), but **id-bearing and
explicitly do-not-retry**: the note is in the working tree.
`NOTE_ERROR:<reason>` is reserved for failures **before** the append lands,
where no note and no id exist — the two are disjoint, so "was a note created?"
is always answerable from the output alone.

**The recovery must stay path-scoped (F12).** Do not tell the caller a later
commit of `aitasks/` picks it up: task data is a shared multi-writer branch, and
a blanket add would sweep another session's uncommitted task-file edits into
this note's commit — the exact thing the parent's non-negotiable forbids. Emit
the scoped command, naming only the returned `<path>`:

```
./ait git add -- <path> && ./ait git commit -m "ait: Record note <note-id> for t<target>" -- <path>
```

Both halves are `--`-scoped to the one file, so recovery commits the note and
nothing else.

**The hint goes on stderr; stdout stays exactly one line (F17).** stdout is the
machine channel — `NOTE_APPENDED_UNCOMMITTED:<id>|<path>|<reason>` is parsed by
field position, so printing a two-line recovery command after it turns a
structured result into something no caller can read, while dropping the hint
loses the guidance the outcome promises. Neither trade is necessary: the
framework already splits these channels, and this is the same shape.
`materialize-active` is the working precedent — `warn()` writes to stderr
(`lib/terminal_compat.sh:21`) while the status word goes to stdout via `echo`,
and its `MATERIALIZED_UNCOMMITTED` path emits **both** (`aitask_gate.sh:1081`).
So: the recovery command is a `warn`, and the one structured line is the only
thing on stdout.

`<reason>` is part of that guarantee, not separate from it: it is interpolated
into a `|`-delimited single line, so **sanitize it at the write site** — collapse
newlines to spaces and replace `|` — or a reason carrying either character
splits the record or forges a field. Same rule as §5's body sentinel, same
reason: the write site is the only place that can enforce it.

### 2b. CLI contract — durable only, and authoritative

```
NOTE_APPENDED:<note-id>|<path>                        # appended + committed
NOTE_APPENDED_UNCOMMITTED:<note-id>|<path>|<reason>   # appended, commit failed (F6)
NOTE_TARGET_MISSING:<id>
NOTE_SELF:<id>                                        # refuse self-addressed
NOTE_ERROR:<reason>                                   # failed BEFORE the append
```

Usage: `ait note <target-task-id> --from <id> [--text ... | --file ...]`

The first two are **id-bearing and terminal** — the note exists; do not retry.
The last three mean no note and no id exist. The two sets are disjoint, so "was
a note created?" is answerable from the output alone, which is what makes a
caller's retry policy safe.

**Exactly one of these lines reaches stdout, always (F17).** Every advisory —
the F12 recovery command, any git noise, the `_UNCOMMITTED` explanation — goes
to **stderr** via `warn`, per the `materialize-active` precedent. A caller may
therefore treat stdout as a single parseable record without buffering or
filtering, which is the whole point of a structured contract.

The CLI emits **no** live-delivery outcome — a shell process cannot observe one
(`SendMessage` / `ListAgents` are model-facing tools with no CLI). `LIVE_QUEUED`
/ `LIVE_NONE` are reported separately by the t1657_4 adapter.

### 3. `base` provenance — the obvious implementation is wrong

`aitasks/` is a **symlink into the data worktree** (`aitasks -> .aitask-data/aitasks`),
so resolving git context from the task file's own path records the
**aitask-data** SHA — a confident, wrong answer to the only question `base`
exists to answer.

- query from the **code repo root** (`AIT_DIR`) — never the task-file path,
  `aitasks/`, or `.aitask-data`;
- capture **before** the append and its commit;
- `base=<full-oid>`, `base_branch=<abbrev-ref>`; `base_mergebase=<full-oid>`
  **only** when HEAD is off the primary branch and a merge base exists.
  **Discover the primary branch with `detect_primary_branch()`
  (`lib/git_utils.sh:20`) — never hardcode `main` (F11).** It resolves
  `origin/HEAD`, then falls back `main` → `master` → `main`, so a master-default
  or remote-default repo gets the right merge base instead of none. This is
  framework code shipped into other people's repos, so the default matters.
  **Full object id, never abbreviated** — `git rev-parse HEAD`, not `--short`,
  width from `git rev-parse --show-object-format`, not hardcoded. `core.abbrev`
  is unset, so git auto-scales abbreviation to repo size; a prefix frozen into a
  durable note keeps that width as the repo grows and can later resolve to more
  than one object — defeating the exact-tree promise for exactly the oldest
  notes. **Storage is exact; presentation may abbreviate.**
- sentinels, never empty or invented: `base=none` (no repo), `base=unknown`
  (HEAD unresolvable);
- **`dirty` from the code repo too** — in the data worktree it would read `yes`
  almost always, making the field noise exactly where it must carry the
  moment-relative warning. It takes the same sentinel treatment as `base`:
  **`dirty=unknown` when and only when `base=none`** (no repository ⇒ nothing to
  measure). On an unborn branch (`base=unknown`) `git status` still works, so
  `dirty` is measured normally there — see §8 (F16).

### 4. Note identity

`id = <iso-utc>.<24-hex>`, 96 bits from a CSPRNG. Minted **inside** the append
lock and verified absent from the section before writing: within a checkout
uniqueness is then a guarantee, and the 96 bits cover the case no lock can (two
PCs appending concurrently). A 4-hex suffix (65 536/second) would only *reduce*
the hazard — and since `ids=` is the *association* key, a collision makes a
receipt acknowledge the wrong entry.

### 5. Write-site hardening

- **Every body line is emitted as `> | <line>`.** Markers match `^>\s*\*\*`; the
  pipe sentinel sits between quote marker and text so a body line can never be
  parsed as one. A body containing `**👁 note:read** … ids=…` is therefore inert
  text rather than a forged acknowledgement, and `## Inbox` / `## Gate Runs`
  inside a body are neutralized. **Sanitize at the write site, never the read
  site.**
- Reject NUL; strip CR; normalize line endings; **bound the body at 8 KiB** and
  say so in the error and the `--help`.
- `from=` is a **claim**. Write `from_verified=yes` **only** when the process
  provably holds the lock on the claimed sender task; otherwise **omit** the
  field — never `no`, so absence and disproof stay distinct.
- Parsers **reject, never repair** a non-conforming block.

**Sender proof — the concrete check (F8).** The note append lock is keyed
`note_<target>`; it protects the *target's* Inbox and says nothing about the
claimed sender, so `--from` is unauthenticated unless proven separately. Do not
invent a mechanism — `lib/pid_anchor.sh` already has the right primitive, with
the right fail-closed semantics. Read the **sender's** lock
(`aitask_lock.sh --check <from>`) and require **all** of:

1. a lock record exists for `<from>`;
2. its `hostname` equals this host;
3. `lock_anchor_is_self "$pid" "$pid_starttime" "$pid_starttime_kind"`
   (`lib/pid_anchor.sh:224`) returns 0 — all three of pid, start-time token and
   token *kind* must match, which is what makes a recycled PID fail.

Any other outcome — no lock, different host, a different live session, or an
own-anchor this process cannot resolve — **omits** the field. That last case is
the important one and comes free with the helper: "a session that cannot name
its own process has no basis to assert that someone else's recorded process is
it", so an unverifiable anchor fails *toward* the gate rather than around it.

### 6. Dispatcher + whitelist

- `ait` — a `note)` case beside `gate)`, plus a `show_usage` line in the
  **Task Management** block (`ait:40`).
- 5 whitelist touchpoints per `aidocs/framework/aitasks_extension_points.md`:
  `.claude/settings.local.json`, `.codex/rules/default.rules`,
  `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
  `seed/opencode_config.seed.json`.

### 7. Dogfood — with an explicit migration mapping (F13)

Migrate the hand-appended t357 note in
`aitasks/t1657_task_note_mailbox_with_live_delivery.md` (below the `---`, headed
`## Note from t357 (thinking_app)`) into a real `## Inbox` entry. It is the first
genuine inbox entry and it predates the mailbox — so its provenance is *claimed*,
not *observed*, and the entry must not pretend otherwise.

| field | value | why |
|---|---|---|
| marker name | `t357` | `#` is not a legal marker name char (§0) |
| `from=` | `thinking_app#357` | the real cross-repo sender; legal as a `k=v` value |
| `from_verified` | **omitted** | no lock on another project's task can be held here — and the note is historical |
| body | the original prose, verbatim, through the `> \| ` sentinel | it contains `##` headings and a markdown table; §5 must neutralize them |
| `id=` | newly minted at migration | there was no id; it is this entry's identity, not the note's |
| `at=` | migration time | when this *entry* was written |
| `claimed_at=2026-09-01` | from the note's own heading | date-level only — the original's own precision, not invented |
| `base=` | `451dd3af789cd4aff06f38465e16357f815e28b4` | the note's `451dd3af7`, **expanded** — storage is exact (§3) |
| `base_branch=main` | from the heading | |
| `migrated=yes` | | marks provenance as claimed, so a reader never mistakes it for an observed live send |

**Expand, do not copy.** The heading's `451dd3af7` / `eab147468` are 9-hex
abbreviations; both still resolve uniquely today (verified), and `git rev-parse`
turns each into a full oid. Copying them verbatim would ship the very
ambiguity §3 exists to prevent, in the oldest entry in the tree. If either ever
fails to resolve uniquely, write `base=unknown` — never a short value, and never
a guess.

The `aitask-data` hash (`eab147468…`) has **no field**: `base` is defined as the
*code* repo (§3). Keep it in the migrated body text, where it reads as part of
the original claim rather than as framework-recorded provenance.

Delete the old prose block and its `---` separator in the same commit, so the
note exists in exactly one place.

### 8. Register `## Inbox` in the cross-PC merge union  *(new — F1)*

**`.aitask-scripts/board/aitask_merge.py`** (F5 — there is no top-level
`board/`; tests put that directory on `sys.path` and then
`from aitask_merge import merge_body`). Add an `INBOX_SPEC` to
`REGISTERED_SPECS` **ahead of** `GATE_SPEC` (registration order is rebuild
order, and the Inbox renders above the ledger):

| field | value |
|---|---|
| `header` / `comment` | the §1 constants |
| `namespace` | `note` |
| `validate` | the **full structural contract** below — not merely an ISO-shaped `at=` |
| `identity` | `(fields["id"],)` — **not** `(name, …)`: one sender sends many notes |
| `order_key` | `(fields["at"], fields["id"])` — chronological, then the id as a total tie-break |
| `on_collision` | `conflict` |

**The validation contract (F7).** The task requires parsers to *reject, never
repair* a non-conforming block, and `identity` is `(id,)` — so a block with a
missing `id` would key on `("",)` and two unrelated malformed blocks would
collide as one entry. Validating only `at=` would let that through. `validate`
returns False — bailing the whole body to conflict markers, which is the
fail-closed answer — unless **all** hold:

- **every block**: `id` matches `^<iso>\.[0-9a-f]{24}$` and `at` matches the ISO
  pattern;
- **a note** (`block.name != "read"`): `from` is present and either local
  (`t<digits>[_<digits>]`) or cross-repo (`<project>#<id>`), and the marker name
  agrees with it — `block.name == fields["from"]` for a local sender, and
  `block.name == "t" + <id part>` for a cross-repo one, since `#` cannot appear
  in a marker name (F10/§0). A disagreement is a malformed block, not a merge
  input. A present `from_verified` is exactly `yes` (never `no` — §5 omits it);
- **a receipt** (`block.name == "read"`): `by` present and task-id shaped, `mode`
  in `{auto, explicit}`, and `ids` a non-empty comma-separated list of values
  each matching the same id pattern. Receipts carry **no** provenance fields —
  they are not tree-relative claims — and a receipt bearing one is malformed.

**Provenance fields are validated too (F15).** Checking only `id`/`at`/sender
would let a block carrying `base=451dd3af7` — an abbreviation — pass merge
validation and union, which is precisely what §3's full-oid invariant and the
task's "reject, never repair" rule forbid. Validating this only on writer output
is not enough: the merge driver consumes blocks written by *another PC*, which
is the case an abbreviation would actually arrive from. On a **note**:

| field | rule |
|---|---|
| `base` | **required**; a full object id, or exactly the sentinel `none` / `unknown` |
| `base_branch` | required **iff** `base` is a real oid; **forbidden** when it is a sentinel (no repo / no HEAD ⇒ no branch) |
| `base_mergebase` | optional; when present must be a full oid **and** `base` must be a real oid |
| `dirty` | `yes` \| `no` \| `unknown`, and **`unknown` iff `base=none`** (F16) |
| `host` | present, non-empty, no whitespace |

**`dirty` needs a degraded value, and exactly one case earns it (F16).**
Requiring `yes`/`no` unconditionally is unsatisfiable when `base=none`: there is
no repository, so `no` fabricates a clean-state claim and `yes` is equally
unsupported. Use the sentinel form §3 already established for `base` rather than
permitting absence — a missing field reads as "fine" (or as an old writer) to a
parser, which is the same argument that made `base=none` a sentinel instead of
an empty value.

The trigger is `base=none` **only**, not both sentinels. Measured: on an unborn
branch (`base=unknown`) `git rev-parse HEAD` fails while `git status --porcelain`
still reports correctly — so dirtiness *is* observable there and `unknown` would
be a false disclaimer. The `iff` makes it fail closed in both directions:
`yes`/`no` alongside `base=none` is a fabricated observation, and `unknown`
alongside a real `base` is a refusal to measure something measurable. Both are
malformed.

**Full object id** means `^[0-9a-f]{40}$` or `^[0-9a-f]{64}$`, and — when the
merging repo's format is resolvable — the width matching
`git rev-parse --show-object-format`. The two-width form is the floor rather
than the whole rule so the merger still validates inside a fixture or a
format-less context; it degrades to *weaker but never absent*, never to
accepting a short value. The writer pins the exact width at the write site (§3),
which stays the stronger check.

**A `migrated=yes` block takes the migration variant** (§0b): `base` still must
be a full oid or a sentinel — the dogfood expands it — plus `claimed_at`; and
`dirty`, `host` and `from_verified` are **forbidden**, because none of the three
was ever observed. Writing `dirty=no` on a historical note would be a fabricated
observation, so its absence is the contract, not an omission.

The receipt half is authored **here** because notes and receipts share one
section and one namespace, so a spec that rejected receipts would break the
moment **t1657_3** ships them. It is inert until then (no receipts exist yet) —
t1657_3 exercises it. Say so in a comment on the spec, so the next reader does
not mistake unexercised rules for dead ones.

Then update the two characterization tests whose docstrings name this task —
`test_divergent_foreign_section_conflicts_the_whole_body` and
`test_one_sided_foreign_section_conflicts_the_whole_body` in
`tests/test_merge_union_characterization.py`. They pin a **limitation**, not a
requirement; registering the section is what fixes it. Rewrite them to assert
the union (resolved, both notes present, no conflict markers) and update the
docstrings to record that the limitation is gone. `tests/test_ledger_block_multisection.py`
already drives exactly this spec shape synthetically — it is the working
reference.

## Post-phase (risk mitigations)

### `pin_section_order`

Assert `## Inbox` stays above `## Gate Runs` in **both creation orders** (F3) —
they take different code paths in `ait_ledger_append_section`:

1. **gate block first, then a note** — exercises the `create_before`
   anchor-insert branch;
2. **note first, then a gate block** — exercises EOF creation for both.

Run each against **both** gate backends (bash `_gate_append_locked` and
`AIT_GATES_BACKEND=python`) — each has its own EOF-append path, so one backend
passing proves nothing about the other.

### `union_inbox_roundtrip`

Drive the **real registered** `INBOX_SPEC` (not the synthetic one) through
`aitask_merge.merge_body`:

- one-sided append (one PC has the note, the other does not) → **resolved**,
  note preserved — the case F1 measured as conflicting today;
- both sides append different notes → unioned in `(at, id)` order;
- two **distinct** blocks sharing one `id` → conflict (append-only violation);
- a body carrying `## Inbox` **and** `## Gate Runs` with only one divergent →
  the other still unions.

## Verification

- `bash tests/test_note_append.sh` — format, ids, self-send refusal, missing target
- **injection round-trip**: a body containing a literal `**👁 note:read** … ids=…`
  line, a `## Gate Runs` line and an `## Inbox` line must round-trip as inert
  text — parsing afterwards yields **one** entry, **zero** receipts, unchanged
  section boundary; plus NUL / CR / oversized-body rejection
- **forced-collision, two fixtures (F9)** — a plain parallel-write test would
  essentially never collide, so the generator is stubbed; but a generator fixed
  to *one* value can never yield a distinct suffix, so it tests the bound, not
  the recovery. Both, separately:
  - **recovery**: a **scripted sequence** — first call returns an id already
    present in the section, second returns a fresh one. Assert the in-lock
    uniqueness check re-mints, the entry lands **once**, and the returned
    `NOTE_APPENDED:` id is the second value;
  - **bound**: a permanently-fixed generator. Assert the writer stops after the
    retry bound (**8**) and exits with `NOTE_ERROR:id-collision-retries-exhausted`
    having appended **nothing** — it must terminate, not spin
- **commit-boundary (F6)**: force `task_git commit` to fail (unwritable index)
  and assert the output is `NOTE_APPENDED_UNCOMMITTED:<id>|<path>|<reason>` with
  a non-zero exit — id-bearing, and that the note is present on disk exactly
  once. Assert `NOTE_ERROR:` is **never** emitted once the append has landed
- **output channels (F17)**: capture stdout and stderr **separately** on every
  outcome. Assert stdout is **exactly one line** in all five cases (`wc -l` = 1,
  and it matches the contract regex), that the path-scoped recovery command
  appears on **stderr** and never on stdout, and that stdout survives
  `2>/dev/null` as a complete parseable record. Include a `<reason>` containing a
  newline and a `|` and assert the emitted line is still one field-correct
  record — sanitized at the write site
- **sender proof (F8)**: `from_verified=yes` appears only for a sender task
  locked by this very session; assert it is **absent** for an unlocked sender, a
  sender locked on another host, a sender locked by a different live session,
  and an unresolvable own anchor. Assert the field is never written as `no`
- **id form (F10)**: a matrix over {parent `349`, child `1657_2`} × {bare,
  `t`-prefixed} × {`<target>`, `--from`}. Assert every cell resolves the same
  task, the stored marker name and `from=` are `t`-prefixed in all of them, and
  — the case that would otherwise ship dead — **`from_verified=yes` is actually
  written** for a `t`-prefixed `--from` whose task this session holds. A
  malformed id yields `NOTE_ERROR:bad-task-id`, never an empty helper answer
- **primary branch (F11)**: a fixture repo whose default branch is **`master`**
  (plus one with `origin/HEAD` set) — assert `base_mergebase` is computed
  against the detected primary, not against a hardcoded `main`, alongside the
  existing off-primary case
- **recovery scope (F12)**: an uncommitted note **beside unrelated uncommitted
  task-data changes** — run the printed recovery command and assert the commit
  contains **only** `<path>`, leaving the unrelated changes uncommitted
- **dogfood provenance (F13)**: assert the migrated entry carries a full-length
  `base` oid (not `451dd3af7`), `migrated=yes`, `claimed_at` distinct from `at`,
  no `from_verified`, `from=thinking_app#357` with marker name `t357`, and that
  the original prose block and its `---` separator are gone
- **migration path (F14)**: pin the **exact emitted record** for
  `--migrate --claimed-from thinking_app#357` — marker name `t357`, `from=` the
  full reference, `migrated=yes`, and `from_verified` / `dirty` / `host` all
  **absent**. Assert `--claimed-from` rejects a malformed reference, and that
  plain `--from` still rejects any cross-repo value (the narrow scope holds)
- **degraded provenance (F16)**: a writer with **no repository** emits
  `base=none` **and** `dirty=unknown` — assert both, and that `dirty=no` never
  appears there. Merge cases: `dirty=unknown` beside a real `base`, and
  `dirty=no` beside `base=none`, must each bail to conflict markers. Separately
  assert an **unborn-branch** writer emits `base=unknown` with a *measured*
  `dirty` (not `unknown`)
- **provenance validation (F15)**: malformed-provenance **merge** cases, not
  writer-output checks — a remote block with an abbreviated `base=451dd3af7`, a
  `base_branch` present beside `base=none`, a `base_mergebase` without a real
  `base`, `dirty=maybe`, a missing `host`, and a receipt carrying `base=` must
  each bail the body to conflict markers. Plus the positive: a full 40-hex
  `base` unions, and a `migrated=yes` block validates **without** `dirty`/`host`
- **Inbox validation (F7)**: one negative merge test per required structural
  field — malformed / missing `id`, non-ISO `at`, a note whose `name` disagrees
  with `from=`, `from_verified=no`, and a receipt missing `ids=` / carrying an
  out-of-vocabulary `mode` — each must bail the body to conflict markers rather
  than union
- **`base` provenance**: equals the code-repo HEAD and **not** `.aitask-data`'s;
  `dirty` reflects the code tree; off-primary HEAD emits `base_mergebase=`;
  degraded cases emit `none` / `unknown`
- **abbreviated `base` is rejected**: `base` / `base_mergebase` must be full
  object ids of the width from `git rev-parse --show-object-format`
  (40 sha1 / 64 sha256) — a short value must **fail** the test, not be tolerated
- **concurrency**: parallel `ait note` calls to one task; every entry survives,
  none renumbered
- both post-phase mitigations green
- `tests/test_merge_union_characterization.py`, `tests/test_aitask_merge.py`,
  `tests/test_ledger_block_multisection.py` green
- `shellcheck .aitask-scripts/aitask_note.sh`
- `bash tests/run_all_python_tests.sh` green

## Final Implementation Notes

- **Actual work done:** As planned, all eight main steps plus both inline
  post-phases. New `.aitask-scripts/aitask_note.sh` (~560 lines); `INBOX_SPEC`
  registered ahead of `GATE_SPEC` in `.aitask-scripts/board/aitask_merge.py`;
  `ait` verb + 5 whitelist touchpoints; new `tests/test_note_append.sh` (110
  assertions), `tests/test_note_section_order.sh` (20), and
  `tests/test_inbox_union_roundtrip.py` (39). The t357 dogfood migrated into
  t1657's Inbox in one path-scoped commit that also deleted the old prose block.

- **Deviations from plan:**
  - Touched **two more tests** in `test_merge_union_characterization.py` than
    t1657_1's handoff named. Its shared `_INBOX_*` fixtures used placeholder ids
    (`.aa`) and no provenance, so registering the spec made them invalid and
    they would have bailed the union. Updated the fixtures to the real format and
    corrected two prose claims that stopped being true. The other four tests in
    the file pass unmodified.
  - Added a `--migrate` verb (§0b) that the first plan revision did not have. It
    was forced by F14: the dogfood claims a cross-repo sender, which `--from`
    forbids by construction, so without it the step required hand-editing a
    section whose own comment forbids exactly that.

- **Issues encountered — five failure-reporting defects, each fix opening the next:**
  - The NUL guard `[[ "$b" != *$'\0'* ]]` rejected **every** body: `$'\0'` is the
    empty string, so the pattern degenerates to `**`. The real fix was deeper
    than the typo — a bash variable cannot hold a NUL at all, so the check had to
    move to the source bytes before the body reaches a variable.
  - The collision seam had to become the **whole id**, not the suffix: an id is
    `<iso>.<suffix>`, so a suffix-only override can never force a collision and
    the re-mint would have shipped untested.
  - F18–F20, F21, F22 are recorded above. The chain is worth reading as one
    story: each was a case where a failure was reported as the wrong thing, and
    the last (F22b) was a failure reported as **success**.
  - **F22b is the one to remember.** `ait_ledger_lock_exit_trap` reads `$?` on
    entry, so chaining any command in front of it destroys the status it exists
    to preserve. A death inside the locked section exited 0 and the writer
    emitted `NOTE_APPENDED` for a wedged lock. Filed upstream as **t1681**.

- **Key decisions:**
  - The writer's provenance validators deliberately **mirror** the merger's
    rules. Whatever the writer commits, every other PC re-validates on merge, so
    a value accepted here and rejected there is worse than either rule alone —
    the block is already in git by then. They must change together.
  - `migrated` is keyed on **presence**, not `== "yes"`. A block claiming the
    variant without satisfying it is malformed, not an ordinary note.
  - `dirty=unknown` **iff** `base=none`, fail-closed in both directions.
    Measured that the trigger is `base=none` alone: on an unborn branch
    `git rev-parse HEAD` fails but `git status` still reports, so `dirty` is
    observable there and the sentinel would be a false disclaimer.
  - The lock does **not** span the git commit. Contention is on the repo-global
    `.git/index.lock`, not the per-task key, so spanning it buys no atomicity and
    only lengthens the window in which a second `ait note` exhausts its budget.
    The id-bearing `NOTE_APPENDED_UNCOMMITTED` outcome is what makes that safe.
  - The subshell needs **two cleanup scopes**: its EXIT trap must not remove the
    handoff files, because it fires exactly when the parent still needs them.

- **Upstream defects identified:** **t1681** — `ait_ledger_lock_exit_trap` has no
  guard or warning against being chained behind another command. The gate ledger
  installs the trap bare and so never hits it, which is why it survived t1657_1's
  review; t1657_3 and t1657_4 both add consumers that will want their own cleanup.

- **Notes for sibling tasks:**
  - **A real note was sent to t1657_3** through `ait note` itself, carrying the
    t1681 trap warning and the receipt key-set contract. It is the first
    genuinely useful use of the mailbox.
  - **t1657_3 owns the receipt half of the validator.** It is authored and tested
    here against synthetic blocks but has no real producer yet: `id`, `by`, `at`,
    `mode` (`auto`|`explicit`), `ids`, and **no** provenance fields. Adding a key
    without also adding it to `_RECEIPT_KEYS_REQUIRED`/`_OPTIONAL` will bail every
    receipt to conflict markers.
  - **t1657_6 (docs)** should cover: the two lanes, the trust posture, the
    `> | ` sentinel as the injection defence, and the pre-existing hazard that
    `aitask_update.sh --desc-file` drops body content (shared with `## Gate Runs`).
  - **t1657_7** was extended to cover `1657_2` in its `verifies:` list — it
    previously excluded the child that is the actual product.


## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9.

## Risk

### Code-health risk: **medium**

- `## Inbox` placed after `## Gate Runs` would silently swallow every future gate
  block — an invariant held by convention, and reached by three different code
  paths depending on which section exists first · severity: high ·
  → mitigation: inline post-phase `pin_section_order`
- First writer to put arbitrary text in a marker-parsed block; a naive body
  emitter creates a forgeable-receipt surface · severity: high ·
  → mitigation: the `> | ` sentinel plus the injection round-trip test
- Registering a second section changes the cross-PC merge driver's head boundary
  for **every** task file, and requires editing two tests t1657_1 froze ·
  severity: medium · → mitigation: inline post-phase `union_inbox_roundtrip`
- An abbreviated or malformed `base` arriving from another PC would pass merge
  validation and union, defeating the full-oid invariant by the one route
  writer-side tests cannot observe (F15) · severity: medium · → mitigation:
  provenance rules in `INBOX_SPEC.validate` (§8) + malformed-provenance merge
  cases
- A required-field rule that no degraded writer can satisfy forces a fabricated
  observation (`dirty=no` with no repository) (F16) · severity: medium ·
  → mitigation: `dirty=unknown` sentinel scoped by an `iff` to `base=none`,
  fail-closed in both directions, with no-repo and unborn-branch tests
- The append and the commit are not one transaction, so a commit failure leaves
  a note durable on disk but unrecorded in git; reporting that as a plain error
  invites a retry that duplicates it (F6) · severity: medium · → mitigation:
  disjoint id-bearing `NOTE_APPENDED_UNCOMMITTED:` outcome (§2b) + forced
  commit-failure test
- `from_verified=yes` is a security-shaped claim on an unauthenticated `--from`
  flag (F8) · severity: medium · → mitigation: `lock_anchor_is_self` three-field
  proof (§5), fail-closed, with four negative tests
- Two task-id forms circulate and the `t`-prefixed one resolves to **nothing**
  on both the lock and task-file paths, so a fail-closed feature can ship dead
  while its negative tests pass (F10) · severity: medium · → mitigation: one
  canonical representation (§0) + a positive `from_verified=yes` assertion
- A blanket-path recovery would commit other sessions' uncommitted task-file
  edits (F12) · severity: medium · → mitigation: `--`-scoped recovery command
  (§2b) + a test with unrelated dirt present
- An advisory printed on stdout would break the structured contract callers
  parse by field position (F17) · severity: medium · → mitigation: one line on
  stdout / advisories via `warn` to stderr, per the `materialize-active`
  precedent, with separate-channel assertions and `<reason>` sanitized at the
  write site
- New body content is dropped by `aitask_update.sh --desc-file` — a pre-existing
  hazard `## Gate Runs` already shares · severity: low · → mitigation: documented
  in `aidocs/` (t1657_6), no code change

### Goal-achievement risk: **medium**

- `INBOX_SPEC`'s semantics (structural `validate`, identity `(id,)`, order
  `(at, id)`) reach production for the first time here; a wrong identity or
  ordering mis-unions notes across PCs **silently** rather than failing loudly ·
  severity: medium · → mitigation: inline post-phase `union_inbox_roundtrip`
- The receipt half of the validation contract (F7) is authored here but only
  exercised once t1657_3 ships receipts, so it ships unproven against real
  producers · severity: low · → mitigation: negative merge tests over synthetic
  receipt blocks now; a spec comment naming t1657_3 as the exerciser
- The migrated dogfood entry's provenance is *claimed*, not observed, and its
  hashes must be expanded while they still resolve (F13) · severity: low ·
  → mitigation: explicit migration mapping (§7) + `migrated=yes` marker
- The dogfood needs a writer the normal send path cannot provide, and an ad-hoc
  one would either hand-edit a machine-owned section or downgrade provenance
  (F14) · severity: medium · → mitigation: scoped `--migrate` path (§0b) that
  omits `from_verified` structurally, pinned by an exact-record test
- The writer half has direct working precedent in `aitask_gate_record.sh` and
  the seam APIs are verified present · severity: low · → mitigation: None needed

### Planned mitigations
- timing: post-phase | name: pin_section_order | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — `## Inbox` after `## Gate Runs` would silently swallow every future gate block | desc: Assert the Inbox stays above the gate ledger in BOTH creation orders (gate-then-note exercises the create_before anchor-insert branch; note-then-gate exercises EOF creation), against both gate backends
- timing: post-phase | name: union_inbox_roundtrip | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — INBOX_SPEC's validate/identity/order semantics reach production for the first time and a wrong one mis-unions silently | desc: Drive the real registered INBOX_SPEC through aitask_merge.merge_body — one-sided append resolves, divergent appends union in (at,id) order, duplicate id conflicts, and a body carrying both sections with only one divergent still unions
