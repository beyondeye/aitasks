---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t1657_1]
issue_type: feature
status: Implementing
labels: [framework, ait_dispatcher, bash_scripts, task_metadata, whitelists]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1657
implemented_with: claudecode/opus5
created_at: 2026-09-01 12:35
updated_at: 2026-09-01 18:48
---

# Durable lane: the `## Inbox` format and the `ait note` writer

Built **on** the t1657_1 seam — do not reimplement block parse/build/append or
the append lock here.

## Context

Parent plan: `aiplans/p1657_task_note_mailbox_with_live_delivery.md`. Read its
Design section in full; the entry format, the injection defence, the id scheme
and the `base` provenance algorithm are all specified there and are load-bearing.

This is the product: a task can finally be told something even when nobody is
working on it. Live delivery (t1657_4) is an optimisation layered on top.

## The entry format

```markdown
## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t349** id=<iso>.<24-hex> from=t349 from_verified=yes at=<iso> base=<full-oid> base_branch=main dirty=no host=<host>
>
> | body line one
> | body line two

> **👁 note:read** id=<iso>.<24-hex> by=t357 at=<iso> mode=explicit ids=<id>,<id>
```

### Three properties that are NOT decoration

1. **`> | ` body sentinel — the injection defence.** The gate ledger's body lines
   are fixed labels (`Verifier:`, `Result:`) built from controlled values, so its
   format has never had to resist injection. `ait note` is the FIRST writer to put
   arbitrary text inside a marker-parsed block. Markers match `^>\s*\*\*`; a body
   line emitted as plain `> <text>` beginning `**👁 note:read** … ids=…` IS a
   syntactically valid receipt, letting a note forge an acknowledgement. The pipe
   sentinel sits between quote marker and text so `^>\s*\*\*` can never match a
   body line. It also neutralizes `## Inbox` / `## Gate Runs` inside a body.
   **Sanitize at the write site**, never at the read site.

2. **96-bit id, minted under the lock and uniqueness-checked.** `<iso>.<24-hex>`
   from a CSPRNG. A 4-hex suffix gives only 65 536 values/second, which *reduces*
   but does not remove same-second collision — and since `ids=` is the
   *association* key, a collision makes a receipt acknowledge the wrong entry.
   Mint inside the per-task append lock and verify absent from the section before
   writing: within a checkout uniqueness is then a guarantee, and the 96 bits
   cover the case no lock can (two PCs appending concurrently).

3. **`base` provenance — the obvious implementation is wrong.** This repo has two
   live HEADs and `aitasks/` is a **symlink into the data worktree**
   (`aitasks -> .aitask-data/aitasks`). Resolving git context from the task
   file's own path records the **aitask-data** SHA — a confident, wrong answer to
   the only question `base` exists to answer. Pinned algorithm:
   - queried from the **code repository root** (`AIT_DIR`), never from the task
     file path, `aitasks/`, or `.aitask-data`;
   - **captured before** the append and its commit;
   - `base=<full-oid>`, `base_branch=<abbrev-ref>`, and
     `base_mergebase=<full-oid>` **only** when HEAD is off the primary branch and
     a merge base exists. **Full object id, never abbreviated** —
     `git rev-parse HEAD`, not `--short`; width from
     `git rev-parse --show-object-format`, not hardcoded. `core.abbrev` is unset,
     so git auto-scales abbreviation to current repo size (9 hex at 21 665
     objects here); a prefix frozen into a durable note stays that width while
     the repo grows and can later become ambiguous — breaking the exact-tree
     promise for exactly the oldest notes. Storage is exact; **presentation may
     abbreviate**;
   - degraded cases get explicit sentinels — `base=none` (no repo),
     `base=unknown` (HEAD unresolvable) — never empty or invented, because a
     missing field reads as "fine" to a parser;
   - **`dirty` is computed against the code repo too.** In the data worktree it
     would read `yes` almost always (task files are perpetually written), making
     the field noise exactly where it must carry the moment-relative warning.

`from=` is a **claim**, not authentication. `from_verified=yes` is written ONLY
when the writing process provably holds the lock on the claimed sender task, and
is otherwise **absent** — never `no`, so absence and disproof are not conflated.

## Key files

- NEW `.aitask-scripts/aitask_note.sh` — same shape as
  `.aitask-scripts/aitask_gate_record.sh` (read it first): append via the seam,
  then `task_git add -- "$file"`, path-scoped commit, best-effort `task_push`.
  Uses the seam's append lock with key `note_<id>`. Resolve the target with
  `resolve_task_file` (`lib/task_utils.sh:1184`).
- `ait` — dispatcher case for `note`, plus `show_usage` entry under Task Management.
- Section registration so `## Inbox` is inserted **before** `## Gate Runs`
  (Finding 2 of the parent plan — `_gate_append_locked` and
  `gate_ledger.append_block` both append at EOF, so an Inbox placed after would
  silently swallow every future gate block).

## CLI contract — durable only, and authoritative

```
NOTE_APPENDED:<note-id>|<path>     # note-id leads: it is the join key
NOTE_TARGET_MISSING:<id>
NOTE_SELF:<id>                     # refuse self-addressed
NOTE_ERROR:<reason>
```

The CLI emits **no** live-delivery outcome — a shell process cannot observe one
(`SendMessage`/`ListAgents` are model-facing tools with no CLI). `LIVE_QUEUED` /
`LIVE_NONE` are reported separately by the t1657_4 adapter.

Usage: `ait note <target-task-id> --from <id> [--text ... | --file ...]`

Write-site normalization: reject NUL, strip CR, normalize line endings, bound
body size (document the limit).

## Whitelist — 5 touchpoints for the new helper

Per `aidocs/framework/aitasks_extension_points.md`:
`.claude/settings.local.json`, `.codex/rules/default.rules`,
`seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
`seed/opencode_config.seed.json`.

## Dogfood

Migrate the hand-appended note from t357 currently sitting in
`aitasks/t1657_task_note_mailbox_with_live_delivery.md` (below the `---`
separator, headed `## Note from t357 (thinking_app)`) into a real `## Inbox`
entry. It is the first genuine inbox entry and it predates the mailbox.

## Post-phase (risk mitigation: pin_section_order)

Append a note, **then** append a gate block; assert the gate block lands under
`## Gate Runs` and the note stays above it. Run against **both** gate backends
(bash `_gate_append_locked` and `AIT_GATES_BACKEND=python`) — each has its own
EOF-append path, so one backend passing proves nothing about the other.

## Verification

- `bash tests/test_note_append.sh` — format, ids, self-send refusal, missing target.
- **Injection round-trip**: a body containing a literal `**👁 note:read** … ids=…`
  line, a `## Gate Runs` line and a `## Inbox` line must round-trip as inert text
  — parsing afterwards yields **one** entry, **zero** receipts, unchanged section
  boundary. Plus NUL / CR / oversized-body rejection.
- **Forced-collision test**: stub the CSPRNG to a fixed value so two writers mint
  the same suffix *deterministically* (a plain parallel-write test would
  essentially never collide); assert the in-lock uniqueness check re-mints.
- **`base` provenance**: assert `base` equals the code-repo HEAD and NOT
  `.aitask-data`'s; `dirty` reflects the code tree; off-primary HEAD emits
  `base_mergebase=`; degraded cases emit `none` / `unknown`.
- **Reject abbreviated `base`**: assert `base` and `base_mergebase` are full
  object ids of the width reported by `git rev-parse --show-object-format`
  (40 sha1 / 64 sha256) — a short value must fail the test, not merely be
  tolerated.
- **Concurrency**: parallel `ait note` calls to one task; every entry survives,
  none renumbered.
- `shellcheck .aitask-scripts/aitask_note.sh`

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T15:48:17Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-02T06:11:27Z status=pass attempt=1 type=human
