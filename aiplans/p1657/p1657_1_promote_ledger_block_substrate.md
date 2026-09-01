---
Task: t1657_1_promote_ledger_block_substrate.md
Parent Task: aitasks/t1657_task_note_mailbox_with_live_delivery.md
Sibling Tasks: aitasks/t1657/t1657_2_inbox_format_and_ait_note_writer.md, aitasks/t1657/t1657_3_read_receipts_and_pick_surfacing.md, aitasks/t1657/t1657_4_live_endpoint_resolution_infrastructure.md, aitasks/t1657/t1657_5_aitask_note_skill_and_discoverability.md, aitasks/t1657/t1657_6_documentation_website_and_aidocs.md, aitasks/t1657/t1657_7_manual_verification_task_note_mailbox.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-01 15:10
---

# p1657_1 — Promote the ledger-block substrate to a shared seam

## Context

t1657 gives tasks a durable mailbox: an append-only `## Inbox` section on the
task file, written by `ait note`. Its shape mirrors the existing `## Gate Runs`
ledger almost exactly — marker-first blockquotes, section ensure-and-append under
a per-task lock, state derived back-to-front, and a cross-PC union in
`aitask_merge.py`. Measured overlap is ~180 lines of genuinely generic code
across bash and Python.

This child moves that substrate behind one seam **before** t1657_2 consumes it,
so the second consumer is built ON the seam rather than beside it. This repo has
already watched that drift — `aitask-audit-wrappers` exists because per-agent
fanout diverged exactly that way.

**Zero behaviour change. Ships nothing user-visible.**

---

## Verification pass (2026-09-01, this session)

The plan was re-verified against the current tree. Every file path, symbol and
line number it names is accurate:

| plan claim | verified |
|---|---|
| `gate_ledger.py` `MARKER_RE` :106, `build_block` :447, `append_block` :483 | exact |
| `iso_now` :204, `_atomic_write` :498, `parse_gate_run_blocks` :216 | exact |
| gate-specific set stays put; registry half from `_frontmatter_text` :519 | exact |
| `aitask_gate.sh` lock fns :131–176, `_gate_append_locked` :336 | exact (plan said 334) |
| `aitask_merge.py` `_split_gate_section` :453, `_union_gate_runs` :484 | exact (plan said 485) |
| `tests/test_merge_union_characterization.py` | absent — pre-phase is genuinely new |

Four findings change the plan. They are the substance of this revision.

### F1 — The acceptance rule collides with a documented framework rule

`gate_ledger.py` is **stdlib-only today**: zero sibling imports, and
`aitask_merge.py:42` documents that in a comment
(`import gate_ledger  # noqa: E402 -- stdlib-only`). Two tests bare-`cp` it into
synthetic projects as a *leaf lib*:

- `tests/test_gate_guarded_archival.sh:131`
- `tests/test_create_manual_verification_gates.sh:206`

The moment `gate_ledger.py` gains `import ledger_block`, both break — the exact
t1488 failure whose remedy (`copy_py_closure_from`) is already in
`tests/lib/test_scaffold.sh` and documents that incident in its own docstring.

Symmetrically, `lib/ledger_block.sh` sourced at startup by `aitask_gate.sh`
triggers `aidocs/framework/shell_conventions.md`: *"System libs added to the
source-on-startup chain must also be added to
`tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` in the same PR."*
`stale_lock.sh` is already listed there with a comment naming `aitask_gate.sh`.

So "no test may be edited" is unimplementable as literally written.
**Resolution (user-confirmed): split the rule and pre-declare the edits.**

### F2 — The re-export contract is measured, not hypothetical

Eight moving symbols have references from **outside** `gate_ledger.py`:

| symbol | refs | notable call site |
|---|---|---|
| `has_gate_markers` | 8 | pinned public by `tests/test_gate_ledger_public_api.py` |
| `parse_gate_run_blocks` | 7 | `aitask_merge.py`, `test_gate_ledger_python_parser.py` |
| `SECTION_HEADER` / `SECTION_COMMENT` | 3 each | `_union_gate_runs` rebuilds the section from them |
| `iso_now` | 2 | `gate_orchestrator.py:359` |
| `GateRun` | 2 | `test_gate_stale_signed_unit.py:35` |
| `build_block` | 1 | `test_aitask_merge.py:301` |
| `_atomic_write` | 1 | `gate_registry_sync.py:519` — a **private** name used externally |

Every one must still resolve as `gate_ledger.<name>` after the move.

### F3 — `_gate_append_locked` is not a pure formatter

It also contains the `AIT_GATES_BACKEND=python` delegation, the gate-specific
`k=v` vocabulary, auto-attempt via `_gate_run_state`, and `gate_icon`. Only a
narrower slice is generic. The seam boundary must be drawn deliberately.

### F4 — Body rendering is per-consumer, not shared

The gate ledger's body lines are fixed labels (`> Verifier: …`, `> Result: …`).
t1657_2's `## Inbox` uses a **`> | ` sentinel** as its injection defence
(arbitrary user text must never be able to forge a `^>\s*\*\*` marker). These
are different renderings of the same envelope, so **body rendering stays with
each consumer**; the seam owns the envelope.

### F5 — "header, comment, namespace, sort key" is an insufficient section spec

The union hardcodes gate semantics in **three** places, and none transfers to an
Inbox whose marker carries `id=` / `at=` and neither `run=` nor `attempt=`:

| site | today | on an Inbox block |
|---|---|---|
| Guard 1 (`:498`) | `_ISO_RUN_RE.match(fields["run"])` | no `run` → **every** block fails → union always bails |
| Guard 2b (`:507`) | identity `(name, run, attempt)` | → `("t349","","")` for every note from t349 → **two notes collide as one identity** → false ambiguous-winner |
| ordering (`:521`) | `(run, name, attempt_int, text)` | all-empty `run`/`attempt` → degenerates to `(name, text)`, not chronological |

A section spec must therefore carry **five** things: parser namespace,
**validation predicate**, **identity key**, **ordering key**, and **collision
behaviour**. Ordering is also not merely a different field name — `attempt` sorts
*numerically* via `_attempt_int`, so the ordering key is a per-spec callable, not
a tuple of field names.

### F6 — `build_block` cannot move wholesale: it would invert the dependency

`build_block` (`:447`) is not a pure renderer. It calls `next_attempt(text, gate)`
(`:461`), tests `TERMINAL_STATUSES` (`:460`), reads `ICONS` (`:463`), and
hardcodes the `gate:` namespace in its marker f-string. Moving it into the seam
would drag three gate-specific symbols with it — `ledger_block` → `gate_ledger`,
a reverse dependency. Stripping them instead risks changing what the Python
backend emits.

Note also that `build_block` does **not** iterate `MARKER_KEYS`: it hardcodes
`run`/`status`/`attempt` and then loops `("duration", "type")`. `MARKER_KEYS` is
consumed only by the parse side. So "`MARKER_KEYS` becomes caller-supplied" is
true for **parse**, not for **build**.

---

## Pre-phase (risk mitigations)

**Runs before any production edit.**

### `characterize_merge_union`

New `tests/test_merge_union_characterization.py` pinning `aitask_merge.py`'s
*current* behaviour, so the extraction's blast radius is measured rather than
assumed:

1. **happy union** of two divergent `## Gate Runs` ledgers → resolved, blocks
   ordered by `(run, name, attempt-as-int, text)`;
2. **negative controls, one per guard — each must produce conflict markers, not
   a union.** A happy-path-only test would not detect the regression this
   mitigation exists to prevent:
   - stray prose under the ledger header → `_section_is_clean` false;
   - a block whose `run=` is not valid ISO → `_ISO_RUN_RE` fails;
   - two distinct blocks for one `(name, run, attempt)` → ambiguous winner;
   - genuinely divergent prose heads → head conflict, **ledger still unioned**;
3. **a body carrying `## Gate Runs` *and* a foreign `## Inbox`** (F5). This is
   existing behaviour and must be pinned before it can be changed: today
   `_split_gate_section` finds only `## Gate Runs`, so `## Inbox` lands in the
   **head** — a divergent Inbox therefore produces a head conflict while the
   gate ledger still unions. That is the baseline t1657_2 will deliberately
   change, and it is invisible unless captured now.

Record the observed outputs as the baseline. Nothing below may change them.

### `characterize_build_block`

F6 says `build_block` splits into a generic renderer and a gate wrapper. Pin its
**byte-exact** current output first, as a matrix — this is what makes "the
wrapper preserves public behaviour" falsifiable rather than asserted:

- every status in `VALID_STATUSES` (covers `ICONS` selection and the `"⚠"`
  fallback for an unknown status);
- `attempt` supplied explicitly **vs** auto-computed via `next_attempt` for each
  terminal status, against a `text` already holding prior terminal markers
  (pins the +1 ordinal), **and** omitted entirely for `running`/`pending`;
- `run` supplied vs generated (assert shape, not value);
- each `BODY_KEYS` entry present/absent, including backtick wrapping for
  `verifier`/`log` and the `>\n` separator line before the body;
- `duration`/`type` present/absent.

Run the same matrix through `append_block` to pin section-creation-at-EOF and
the blank-line layout.

### `pin_reexport_surface`

New guard asserting the F2 table executably. Today's coverage of these eight
names is real but **incidental and scattered** across six unrelated test files;
nothing states the contract. Written **before** the move, so it passes pre- and
post-refactor — a characterization, not a new expectation.

**The eight names do not re-export the same way, so the guard must not assert one
uniform thing.** F6 makes `build_block` a wrapper *by design*; an
`is`-identity assertion over it would be false by construction and would push the
implementation toward the very design F6 rejects. Three classes, asserted
differently:

| class | names | assertion |
|---|---|---|
| **alias** — moved verbatim | `iso_now`, `_atomic_write` | `gate_ledger.<n> is ledger_block.<n>` |
| **wrapper** — namespace- or gate-bound | `build_block`, `append_block`, `parse_gate_run_blocks`, `has_gate_markers` | callable on `gate_ledger`; `inspect.signature` unchanged from today; behaviour equal to the frozen characterization fixtures. **Never** an identity assertion |
| **value** — gate-specific constants | `SECTION_HEADER`, `SECTION_COMMENT` | exact string equality with today's literals |

`GateRun` joins **alias** if it is aliased to a generalized `LedgerBlock`, and
**value** (a `dataclasses.fields` comparison) if it stays defined in
`gate_ledger`. The plan permits either; the guard asserts whichever the
implementation chose, and records which in a comment.

Why `parse_gate_run_blocks` and `has_gate_markers` are wrappers, not aliases:
`MARKER_RE` and `MARKER_SEARCH_RE` bake `gate:` into the pattern (`:106`–`:107`),
so the seam's versions take the namespace as a parameter and `gate_ledger`'s keep
their current single-argument signature by binding it.

---

## Main steps

### 1. `lib/ledger_block.py` (new)

Extract from `lib/gate_ledger.py`, parameterized on **block namespace** and
**section header**:

- `iso_now()`, `_atomic_write()` — move verbatim.
- **parse** — from `parse_gate_run_blocks()`. `MARKER_RE` (:106) hardcodes
  `gate:`; take the namespace as a parameter and build the pattern from it.
  `MARKER_SEARCH_RE`, `KV_RE`, `BODY_FIELD_RE` follow.
- **build** — split, **do not move** (F6). The seam gets a *pure envelope
  renderer* that resolves nothing:

  ```python
  render_block(namespace, name, icon, marker_kv, body_lines) -> str
  ```

  `marker_kv` is an already-ordered sequence of `(key, value)` pairs;
  `body_lines` are already-rendered `>`-prefixed strings. It performs no
  defaulting, no attempt arithmetic, no icon lookup and no label mapping — so it
  imports nothing from `gate_ledger` and the dependency stays one-way.

  `gate_ledger.build_block(text, gate, status, fields)` **keeps its exact current
  signature and behaviour** as a thin compatibility wrapper: it resolves `run`
  (via `iso_now`), `attempt` (via `next_attempt` + `TERMINAL_STATUSES`), `icon`
  (via `ICONS`), and the `BODY_KEYS` label/backtick rendering, then delegates.
  `next_attempt`, `TERMINAL_STATUSES` and `ICONS` **stay in `gate_ledger`**.

  Parity is proved against the `characterize_build_block` baseline, byte for
  byte, and must also hold with `AIT_GATES_BACKEND=python` set and unset.
- **section ensure-and-append** — from `append_block()` (:483), today
  **EOF-hardcoded**. Grows a **section-order** argument so a section can be
  inserted *before* a named one. This is the capability t1657_2 needs to land
  `## Inbox` above `## Gate Runs`. `gate_ledger.append_block` likewise stays a
  wrapper that passes the gate section's order and preserves today's
  EOF placement exactly.

Keep `GateRun` as the parsed record (or generalize to `LedgerBlock` and alias).

**Re-export contract (F2):** `gate_ledger.py` re-exports every moved name it
previously exposed — including `_atomic_write`, whose sole external consumer is
`gate_registry_sync.py:519`. Gate call sites stay untouched.

### 2. `lib/ledger_block.sh` (new)

- **per-task append lock** — from `acquire_gate_lock` / `release_gate_lock` /
  `release_gate_lock_checked` / `_gate_lock_exit_trap` (`aitask_gate.sh`:131–176),
  generalized over a key namespace (`gate_<key>` → `<ns>_<key>`) on top of the
  already-generic `lib/stale_lock.sh`.

  **The failure message is caller-labelled, not generic.**
  `tests/test_gate_lock_characterization.sh:192` pins the literal
  `Failed to acquire gate append lock for ${ID2} after 20 attempts` — the word
  *gate* is inside the pinned string. Take the label as a parameter and have
  `aitask_gate.sh` pass `gate append lock`; a generic "ledger append lock" would
  fail Test 2a.

- **envelope formatter** — the generic slice of `_gate_append_locked` only
  (F3/F4): marker-line assembly, section ensure-or-insert, and the tmp+`mv`
  write. The `k=v` vocabulary, auto-attempt, `gate_icon` and the
  `AIT_GATES_BACKEND` delegation stay in `aitask_gate.sh`; body **rendering**
  stays with each consumer.

Follow `aidocs/framework/shell_conventions.md`: `#!/usr/bin/env bash`,
`set -euo pipefail`, idempotent source guard (`_AIT_LEDGER_BLOCK_LOADED`) as in
`lib/pid_anchor.sh`.

### 3. `board/aitask_merge.py`

Generalize `_split_gate_section` (:453) and `_union_gate_runs` (:484) into an
**ordered append-only multi-section** union driven by a list of section specs.

**The spec carries five fields, not four** (F5) — the three hardcoded gate
semantics each become a spec member:

| field | gate spec (must reproduce today exactly) |
|---|---|
| `header` / `comment` | `SECTION_HEADER`, `SECTION_COMMENT` |
| `namespace` | `gate` |
| `validate(block)` | `_ISO_RUN_RE.match(fields["run"])` — bail whole union if any block fails |
| `identity(block)` | `(name, fields["run"], fields["attempt"])` |
| `order_key(text, block)` | `(fields["run"], name, _attempt_int(block), text)` — a **callable**, because `attempt` sorts numerically |
| `on_collision` | bail to conflict markers (append-only contract violation) |

Structure:

- the head is everything before the **first registered** header, not before
  `## Gate Runs` specifically;
- `_section_is_clean`, validation, full-text dedup and the identity/collision
  guard apply **per section**; a bail in *any* registered section drops the
  whole body to conflict markers, exactly as today;
- an **unregistered** `##` section stays in the head or tail verbatim — it must
  never be silently absorbed or reordered;
- section output order follows the registered order, so a body's sections are
  rebuilt in a canonical sequence;
- head comparison stays "heads equal ignoring trailing blank lines → resolved".

**Zero behaviour change means the gate spec remains the only registered
section.** t1657_2 registers the second and owns the resulting change to the F5
case-3 baseline.

**Proving the parameterization actually works** (this is new-code coverage, not
characterization — the second spec does not exist in production yet): a seam
test drives the generalized union with a **synthetic second spec** whose three
semantics all differ from the gate spec — validated on `at=` rather than `run=`,
identity `(id,)` rather than `(name, run, attempt)`, ordered by `(at, id)`. It
covers concurrent appends to that section, two divergent blocks sharing one `id`
(→ collision → conflict), and a body carrying both sections at once with only
one of them divergent. Without this, "the seam supports t1657_2" is a claim the
task never tests.

### 4. Re-point the gate paths

`aitask_gate.sh` sources the new `.sh`; `gate_ledger.py` imports the new `.py`.
**Nothing gate-specific moves**: `next_attempt`, `live_run`, `derive_status`,
`derive_gate_runs`, `compact_gate_summary`, `abbreviate_gate_summary`,
`format_status`, and the whole registry / `effective_gates` / active-gates /
digest half (from `_frontmatter_text` :519 onward) stay put. Promoting those
would be speculative abstraction.

### 5. Test-harness dependency plumbing (pre-declared — see Acceptance)

- `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` — add `ledger_block.sh`,
  beside the existing `stale_lock.sh` entry, with the same style of comment.
- `tests/test_gate_guarded_archival.sh:131` and
  `tests/test_create_manual_verification_gates.sh:206` — replace the bare
  `cp …/gate_ledger.py` with `copy_py_closure_from`, so the closure is **derived**
  and a future import cannot silently break these fixtures again.

Also update the now-untrue `stdlib-only` comment at `aitask_merge.py:42`.

## Post-phase (risk mitigations)

### `spec_matrix_seam_parity`

New `tests/test_ledger_block_multisection.py` — the seam test described at the
end of step 3. It runs **after** the extraction (it exercises code that does not
exist before it) and is the only evidence that the five-field spec is genuinely
parameterized rather than gate-shaped with renamed fields. Green here plus green
on the three frozen pre-phase files is the task's completion condition.

---

## Acceptance

**The rule, split (user-confirmed).** The proof of "zero behaviour change" is
that no *existing* test's meaning changes. Three categories, pre-declared:

1. **FORBIDDEN — this is the proof.** No edit to any assertion, expected value,
   fixture body, golden file, or test logic in any **pre-existing** file under
   `tests/`. Any such edit is a red flag that the refactor changed behaviour, not
   a licence to adjust the test.
2. **PERMITTED — dependency plumbing only, and only these three files**, exactly
   as enumerated in step 5 (`tests/lib/test_scaffold.sh`,
   `tests/test_gate_guarded_archival.sh:131`,
   `tests/test_create_manual_verification_gates.sh:206`). No assertion in those
   files may change — only which support files a fixture copies.
3. **NEW FILES, authored and then frozen.** The pre-phase necessarily *is*
   assertion logic, so it is expressly allowed, under one discipline:

   | file | authored | frozen |
   |---|---|---|
   | `tests/test_merge_union_characterization.py` | pre-phase | before step 1 |
   | `tests/test_gate_ledger_build_characterization.py` | pre-phase | before step 1 |
   | `tests/test_ledger_block_reexport.py` | pre-phase | before step 1 |
   | `tests/test_ledger_block_multisection.py` | with step 3 | on completion |

   **Frozen** means: the three pre-phase files must be green *before the first
   production edit* and must not be touched again. If one goes red during the
   refactor, the production change is wrong — that is the entire point, and
   editing the test to restore green voids the proof. The step-3 seam test is
   new-code coverage rather than a characterization, so it is written alongside
   the code it tests, and frozen once it passes.

Then:

- `bash tests/run_all_python_tests.sh` green.
- Every `tests/test_gate_*.sh` green, including
  `tests/test_gate_lock_characterization.sh` (Test 2a pins the lock-failure
  string).
- Both gate backends still agree: run the gate suite with **and** without
  `AIT_GATES_BACKEND=python`.
- `tests/test_aitask_merge.py`, `tests/test_aitask_merge.sh`,
  `tests/test_aitask_merge_boardgroup.sh` green.
- `shellcheck .aitask-scripts/lib/ledger_block.sh .aitask-scripts/aitask_gate.sh`
- The three pre-phase files green and **byte-unchanged** since the pre-phase
  baseline. This is audited with a **content manifest**, not with git.

  **Why not git.** This repo is a shared worktree carrying unrelated uncommitted
  work from concurrent sessions. Measured during planning: three modified test
  files (`test_concern_dimensions.py`, `test_concern_picker_modal.py`,
  `test_fold_mark.sh`), and the *set changed mid-session* — one of them was not
  dirty when the session began. That breaks every git-based form of this audit:

  - `git diff <commit> -- tests/` reports that pre-existing dirt as `M`, so the
    allowlist fails on changes that predate this task — staged or not.
  - `git add -A -- tests/` would additionally **stage another session's work**,
    mutating index state this task does not own.
  - `git diff <commit>.. -- tests/` resolves to `..HEAD` and silently omits
    uncommitted edits entirely (measured: it missed an unstaged edit to a frozen
    file while listing a committed one).

  **Never run `git add`, `git checkout --`, `git restore` or `git stash` against
  `tests/` in this worktree.** They act on paths this task does not own and
  discard other sessions' uncommitted work irrecoverably — `checkout --` restores
  from the index, which for an unstaged edit is HEAD, and the edit is then gone
  from git entirely.

  **Capture the baseline** immediately after the three pre-phase tests are green
  and before the first production edit. `.git/` is never tracked, so the manifest
  lives there — deterministic path, survives a resumed session, cannot be
  committed:

  ```bash
  ait_tests_manifest() {
      find tests -type f \
           -not -path '*/__pycache__/*' -not -name '*.pyc' \
           -not -path '*/.pytest_cache/*' -print0 \
        | LC_ALL=C sort -z | xargs -0 sha256sum
  }
  ait_tests_manifest > .git/p1657_1_tests_baseline.sha256
  ```

  The prunes are required, not cosmetic: 299 of the 1052 files under `tests/`
  are bytecode, and `.pytest_cache/v/cache/lastfailed` is rewritten by every
  run — including the audit's own verification runs, so leaving it in makes the
  audit fail on its own side effect. Verified: ~756 real entries, byte-stable
  across consecutive runs, and it detects an edit, an addition and — unlike a
  commit-relative diff — a **deletion**.

  **At completion**, diff and classify in three parts. A flat allowlist is NOT
  enough: this worktree has other agent sessions *actively editing* `tests/`
  while the task runs, so their files do **not** hash identically at both ends
  (measured: 21 unrelated paths moved during this task — task-workflow goldens,
  a resource-admission feature, a metadata fixture). The audit must therefore
  discriminate rather than simply demand an empty residual:

  ```bash
  ait_tests_manifest | diff .git/p1657_1_tests_baseline.sha256 - \
    | grep -E '^[<>]' | awk '{print $3}' | sort -u
  ```

  1. **The three frozen pre-phase files must not appear at all** —
     `test_merge_union_characterization.py`,
     `test_gate_ledger_build_characterization.py`,
     `test_ledger_block_reexport.py`. This is the proof; a hit here means the
     production change was wrong.
  2. **The four owned paths must appear, with the right kind of change:**

     | change | path | why |
     |---|---|---|
     | modified | `tests/lib/test_scaffold.sh` | step-5 plumbing |
     | modified | `tests/test_gate_guarded_archival.sh` | step-5 plumbing |
     | modified | `tests/test_create_manual_verification_gates.sh` | step-5 plumbing |
     | added (`>` only, never `<`) | `tests/test_ledger_block_multisection.py` | post-phase seam test |

  3. **Every residual path must be attributable to another session**, checked
     rather than assumed: none of them may reference `ledger_block` or `t1657`.

     ```bash
     grep -l 'ledger_block\|t1657' <residual paths>   # must match nothing
     ```
- `tests/test_ledger_block_multisection.py` green: the seam accepts a second
  spec whose validation, identity and ordering all differ from the gate spec.

---

## Step 9 (Post-Implementation)

Cleanup, archival and merge per `task-workflow` Step 9.

---

## Risk

### Code-health risk: medium

- Touches the gate ledger and the cross-PC merge union — both load-bearing — for
  a consumer that does not exist yet · severity: medium · → mitigation: inline pre-phase characterize_merge_union
- `build_block`'s gate-specific resolution (`next_attempt`, `TERMINAL_STATUSES`,
  `ICONS`) must be separated from generic rendering without changing a byte of
  what the Python backend emits (F6) · severity: medium · → mitigation: inline pre-phase characterize_build_block
- Eight symbols (one of them private, `_atomic_write`) are referenced across six
  unrelated files; a missed re-export degrades a consumer that no single test
  guards · severity: medium · → mitigation: inline pre-phase pin_reexport_surface
- The bash lock generalization could alter a pinned failure message whose pinned
  text contains the word *gate* · severity: low · → mitigation: `tests/test_gate_lock_characterization.sh` (existing)
- Making `gate_ledger.py` non-leaf breaks two hand-maintained fixture copy lists ·
  severity: low · → mitigation: pre-declared step 5 plumbing (`copy_py_closure_from` derives the closure)

### Goal-achievement risk: medium

- The section spec must carry validation, identity, ordering **and** collision
  behaviour, none of which transfer from the gate spec to an `id=`/`at=` Inbox
  (F5). A four-field spec would look complete, pass every gate test, and leave
  t1657_2 unable to register its section — the exact duplication this task
  exists to prevent · severity: medium · → mitigation: inline post-phase spec_matrix_seam_parity
- The rest of the seam's shape is dictated by t1657_2's already-designed entry
  format (section-order insert, `> | ` body sentinel), so it is not speculative;
  and "zero behaviour change" is falsifiable via the split acceptance rule ·
  severity: low · → mitigation: None needed

### Planned mitigations
- timing: pre-phase | name: characterize_merge_union | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — promoting the load-bearing cross-PC ledger union to an ordered-multi-section seam | desc: Pin aitask_merge.py's current union behaviour, including every bail-to-conflict guard and the Gate-Runs-plus-foreign-Inbox baseline, before changing it
- timing: pre-phase | name: characterize_build_block | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — build_block's auto-attempt and icon selection must split from generic rendering without changing Python-backend output | desc: Pin build_block/append_block byte-exact output as a status x fields matrix before splitting the renderer from the gate wrapper
- timing: pre-phase | name: pin_reexport_surface | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — eight externally-referenced symbols move behind the seam with no single guard stating the re-export contract | desc: Assert every moved name still resolves via gate_ledger.<name>, written before the move so it characterizes rather than expects
- timing: post-phase | name: spec_matrix_seam_parity | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — a section spec that omits validation/identity/ordering/collision would pass every gate test yet not support t1657_2 | desc: Drive the generalized union with a synthetic second spec whose validation, identity and ordering all differ from the gate spec, covering duplicate-id collision and both sections present at once
