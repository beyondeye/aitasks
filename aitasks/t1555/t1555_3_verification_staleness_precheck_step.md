---
priority: medium
effort: medium
depends: [t1555_2]
issue_type: feature
status: Ready
labels: [verification, task-workflow]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-08-17 19:00
updated_at: 2026-08-17 19:00
---


Wire the staleness pre-check into the manual-verification procedure, per
`aidocs/framework/manual_verification_staleness.md` (read it first — it is the
source of truth). Slice 3 of 3. Depends on t1549 (helper + field) and t1550
(seeding).

## Placement — both bounds are load-bearing

Insert a new step in `.claude/skills/task-workflow/manual-verification.md`
**between step 1 (pre-loop check — ensure the task has a checklist) and step 1.5
(the autonomous-verification offer)**:

- It must run **before** 1.5, because that step can dispatch autonomous
  verification, which would otherwise work through stale items unattended.
- It must run **after** 1, because step 1's seed path can create the checklist
  mid-step (so a check placed earlier would see no checklist).

Number it `### 1.3` in that file's scheme (its steps run 1, 1.5, 2, 3, 4, 5).

## Behaviour

Run `./.aitask-scripts/aitask_verification_stale.sh check <task_file>` and
dispatch on `DECISION`:

- `SKIP` / `FRESH` → continue silently to 1.5. (`SKIP` is the common case for
  existing tasks — do not warn.)
- `ASK_STALE` → print the `DISPLAY:` line **verbatim**, then `AskUserQuestion`,
  mirroring the `ASK_STALE` prompt shape in `planning.md`:
  - "Amend the checklist" — show the evidence beside the current checklist and
    propose edits; user accepts / edits / rejects per item.
  - "Proceed unchanged" — staleness noted, judged immaterial.
  - "Abort" — Task Abort Procedure; baseline untouched.

  **`ASK_STALE` has two distinct causes and the prompt must not blur them.**
  `CHANGED:` / `DELETED:` lines mean the code moved under the checklist — the
  remedy is amending items. `UNKNOWN:` lines mean a curated path could not be
  checked at all (typically a hand-edited or stale `file_references:` entry) — the
  remedy is fixing the scope list, and on that path "Amend the checklist" should
  offer to correct `file_references:` rather than only the item text. Surface the
  `UNKNOWN:` paths explicitly; never let an uncheckable scope entry pass as a
  clean run.

Advisory only: it must **never** block archival, and nothing is rewritten without
the user accepting it.

## The review transaction — ordering is load-bearing

On the amend path the baseline advance happens **only after** the user's final
accept/edit decision, and it is written **together with every other mutation the
amend produced**.

Advancing first and then failing — or the user abandoning the edit — would
permanently dismiss the very change the user was brought in to review, and with
the baseline already at HEAD **no later pick would ever raise it again**. That is
a silent, unrecoverable loss of the signal the feature exists to produce.

The amend path can produce **three** mutations, all targeting the same file:

| Mutation | Location | When |
|---|---|---|
| checklist item text | body | items are stale |
| `file_references:` | frontmatter | an `UNKNOWN:` path needs the scope list repaired |
| `verification_baseline:` | frontmatter | always, on accept |

Because it is one file, compose them into a **single** `ait_atomic_render` pass
from `lib/atomic_write.sh`. If the frontmatter fields are written through
`aitask_update.sh` instead, pass **all the flags in one invocation** so it is one
atomic re-emit, not several.

**Scope repair must REMOVE the bad entry — appending is not a repair.**
`--file-ref` appends (with exact-string dedup); it never displaces an existing
entry. So `--file-ref <replacement> --verification-baseline …` alone leaves the
bogus reference in place: the next check still emits `UNKNOWN:` and `ASK_STALE`
while the baseline has already advanced — precisely the forbidden state above,
reached by following an incomplete example. Use the updater's exact-match removal:

```bash
./.aitask-scripts/aitask_update.sh --batch <task_id> \
    --remove-file-ref "<bad_path>" \
    [--file-ref "<replacement_path>"] \
    --verification-baseline "<sha> @ <YYYY-MM-DD HH:MM>"
```

`process_file_references_operations` in `aitask_update.sh` handles both arrays in
one pass (append first, then exact-string removal — so removal wins if the same
string is both added and removed), and the whole invocation is a single atomic
re-emit of the frontmatter. Dropping the reference entirely (no replacement) is a
legitimate repair; so is replacing it with the path the file moved to.

**Invariant, however the writes are decomposed: the baseline may advance only
after every other mutation has durably succeeded.** If separate writes are used,
the baseline advance is strictly last and is skipped when any earlier write
failed. That confines every failure to "scope and/or items updated, baseline not
advanced" — which re-prompts next pick and is idempotent. The forbidden state is
the mirror: a baseline at HEAD over an invalid scope list or half-applied items,
silently unreviewable forever.

**Rule: decide → write everything → advance the baseline last → commit.** Never
advance → edit.

"Proceed unchanged" advances the baseline immediately (there is no edit to pair it
with). Advancing on dismissal is what stops the prompt re-firing on every later
pick; omitting it is the single easiest way to make this feature worse than
nothing.

Amendment is a direct edit of the item text — `seed` refuses when a checklist
section already exists, and v1 adds **no** `amend` verb. The audit trail is the
task file's git history plus the advanced baseline.

## Tests

- **Transaction (item amend):** a failure injected between the decision and the
  write leaves the task file **byte-identical** — neither the items nor the
  baseline advanced (follow the `tests/test_atomic_task_file_writes.sh` shape).
- **Transaction (scope repair):** on the `UNKNOWN:` path, inject a failure
  **between the `file_references:` repair and the baseline advance**. Assert the
  baseline is **not** advanced, and that a re-run still returns `ASK_STALE` — i.e.
  the task remains re-promptable. Then assert the forbidden state never occurs:
  there must be no outcome where the baseline sits at HEAD over a
  `file_references:` list that still contains the uncheckable path. This is the
  case that a single atomic write makes impossible and that a naive
  write-scope-then-advance sequence silently produces.
- **Ordering guard:** with the baseline advance stubbed to fail, the scope and item
  edits still land (proving the advance is genuinely last, not interleaved).
- **Successful repair (the positive case the others do not cover):** start from a
  task whose `file_references:` contains one valid path and one bogus path, so the
  check returns `ASK_STALE` with an `UNKNOWN:` line. Repair it via
  `--remove-file-ref <bad>` (optionally with a `--file-ref <replacement>`) plus the
  baseline advance in one invocation, then assert:
  1. the bogus entry is **gone** from `file_references:` — not merely joined by a
     replacement;
  2. the valid entry (and any replacement) survives;
  3. a clean re-run returns **`FRESH`** with **no** `UNKNOWN:` line.

  Without (1) and (3) the suite would pass an implementation that only appends,
  which advances the baseline over a still-broken scope list.
- **No re-fire:** after "Proceed unchanged", a re-run of the check returns
  `FRESH`.
- **Ordering:** the check runs before the 1.5 autonomous offer (a stale checklist
  must not reach autonomous verification unprompted).

## Acceptance

- Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.
- Rerender the per-profile variants — one call per profile, e.g.
  `./.aitask-scripts/aitask_skill_rerender.sh <profile>` — and regenerate the
  affected goldens **in the same commit** (see
  `aidocs/framework/skill_authoring_conventions.md`).
- Suggest separate tasks to port the change to the Codex CLI and OpenCode skill
  trees (per CLAUDE.md: Claude Code version first).
