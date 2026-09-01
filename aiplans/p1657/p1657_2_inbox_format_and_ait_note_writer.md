---
Task: t1657_2_inbox_format_and_ait_note_writer.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_1_*.md, aitasks/t1657/t1657_3_*.md, aitasks/t1657/t1657_4_*.md, aitasks/t1657/t1657_5_*.md, aitasks/t1657/t1657_6_*.md
Base branch: main
Output branch: main
---

# p1657_2 — Durable lane: `## Inbox` format and the `ait note` writer

## Goal

A task can be told something even when nobody is working on it. Built **on** the
t1657_1 seam — no block parse/build/append or lock logic is reimplemented here.

## Main steps

### 1. Register the `## Inbox` section with the seam

Ordered **before** `## Gate Runs`. This is the load-bearing invariant: both
gate-append paths (`_gate_append_locked`, `gate_ledger.append_block`) append at
EOF, so an Inbox placed after would silently capture every future gate block.

### 2. `.aitask-scripts/aitask_note.sh` (new)

Shape it on `aitask_gate_record.sh` — read that first.

```
ait note <target-task-id> --from <id> [--text ... | --file ...]
ait note read <target-task-id> --by <id> --ids <csv> [--mode auto|explicit]   # t1657_3 adds this verb
```

Order of operations:

1. `resolve_task_file "$target"` (`lib/task_utils.sh:1184`); missing → `NOTE_TARGET_MISSING:<id>`.
2. Refuse self-addressed → `NOTE_SELF:<id>`.
3. **Capture provenance BEFORE the append** (see §3).
4. Acquire the seam's append lock, key `note_<id>`.
5. Mint the id and verify it is absent from the section (§4).
6. Build the block; append via the seam.
7. Release the lock, then `task_git add -- "$file"`, path-scoped commit,
   best-effort `task_push` — exactly as `aitask_gate_record.sh` does.
8. Print `NOTE_APPENDED:<note-id>|<path>`.

### 3. `base` provenance — the obvious implementation is wrong

This repo has two live HEADs and `aitasks/` is a **symlink into the data
worktree** (`aitasks -> .aitask-data/aitasks`). Resolving git context from the
task file's own path records the **aitask-data** SHA: a confident wrong answer to
the only question `base` exists to answer.

- query from the **code repo root** (`AIT_DIR`) — never the task-file path,
  `aitasks/`, or `.aitask-data`;
- capture **before** the append and its commit;
- `base=<short-sha>`, `base_branch=<abbrev-ref>`; `base_mergebase=<sha>` **only**
  when HEAD is off the primary branch and a merge base exists;
- sentinels, never empty or invented: `base=none` (no repo), `base=unknown`
  (HEAD unresolvable — unborn branch);
- **`dirty` from the code repo too** — in the data worktree it would read `yes`
  almost always, making the field noise exactly where it must carry the
  moment-relative warning.

### 4. Note identity

`id = <iso-utc>.<24-hex>`, 96 bits from a CSPRNG. Minted **inside** the append
lock and verified absent from the section before writing, so within a checkout
uniqueness is a guarantee; the 96 bits cover concurrent appends from two
checkouts, which no lock can. A 4-hex suffix (65 536/second) would only *reduce*
the hazard — and since `ids=` is the *association* key, a collision makes a
receipt acknowledge the wrong entry.

### 5. Write-site hardening

- **Every body line is emitted as `> | <line>`.** Markers match `^>\s*\*\*`; the
  pipe sentinel guarantees a body line can never be parsed as one, so a body
  containing `**👁 note:read** … ids=…` is inert rather than a forged
  acknowledgement. It also neutralizes `## Inbox` / `## Gate Runs` in a body.
  Sanitize at the **write** site, never the read site.
- Reject NUL; strip CR; normalize line endings; bound body size (document it).
- `from=` is a **claim**. Write `from_verified=yes` **only** when the process
  provably holds the lock on the claimed sender task; otherwise **omit** the
  field — never `no`, so absence and disproof stay distinct.
- Parsers **reject, never repair** a non-conforming block.

### 6. Dispatcher + whitelist

- `ait` — `note)` case plus a `show_usage` line under Task Management.
- 5 whitelist touchpoints per `aidocs/framework/aitasks_extension_points.md`:
  `.claude/settings.local.json`, `.codex/rules/default.rules`,
  `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
  `seed/opencode_config.seed.json`.

### 7. Dogfood

Migrate the hand-appended t357 note in
`aitasks/t1657_task_note_mailbox_with_live_delivery.md` (below the `---`, headed
`## Note from t357 (thinking_app)`) into a real `## Inbox` entry.

## Post-phase (risk mitigations)

### `pin_section_order`

Append a note, **then** a gate block; assert the gate block lands under
`## Gate Runs` and the note stays above it. Run against **both** backends (bash
and `AIT_GATES_BACKEND=python`) — each has its own EOF-append path, so one
passing proves nothing about the other.

## Verification

- `bash tests/test_note_append.sh` — format, ids, self-send, missing target
- **injection round-trip**: body containing a literal receipt marker, a
  `## Gate Runs` line and a `## Inbox` line → **one** entry, **zero** receipts,
  unchanged section boundary; plus NUL / CR / oversized rejection
- **forced-collision**: stub the CSPRNG to a fixed value so two writers mint the
  same suffix deterministically; assert the in-lock check re-mints
- **`base` provenance**: equals code-repo HEAD, not `.aitask-data`'s; `dirty`
  from the code tree; off-primary HEAD emits `base_mergebase=`; degraded cases
  emit `none` / `unknown`
- **concurrency**: parallel `ait note` to one task — all entries survive, none
  renumbered
- `shellcheck .aitask-scripts/aitask_note.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests`

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9.

## Risk

### Code-health risk: **medium**

- `## Inbox` placed after `## Gate Runs` would silently swallow every future gate
  block — an invariant held by convention, not by the type system ·
  severity: high · → mitigation: inline post-phase pin_section_order
- First writer to put arbitrary text in a marker-parsed block; a naive body
  emitter creates a forgeable-receipt surface · severity: high ·
  → mitigation: the `> | ` sentinel plus the injection round-trip test
- New body content is dropped by `aitask_update.sh --desc-file` — a pre-existing
  hazard `## Gate Runs` already shares · severity: low · → mitigation: documented
  in `aidocs/` (t1657_6), no code change

### Goal-achievement risk: **low**

- Direct working precedent in `aitask_gate_record.sh`; no novel mechanism.

### Planned mitigations
- timing: post-phase | name: pin_section_order | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — `## Inbox` after `## Gate Runs` would silently swallow every future gate block | desc: Append a note then a gate block; assert the gate block lands under `## Gate Runs` and the note stays above it
