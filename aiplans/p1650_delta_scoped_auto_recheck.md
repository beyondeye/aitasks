---
Task: t1650_delta_scoped_auto_recheck.md
Topic anchor: t1636 (shadow concern impact-vector model) — grouping only, not a dependency
Parent spec: aiplans/p1636_shadow_concern_impact_vector_model.md (the t1636_5 section is binding)
Branch: main
Base branch: main
Output branch: main
---

# p1650 — Delta-scoped auto-recheck (convergence by construction)

## Context

`review_loop.compose_recheck_prompt` (`.aitask-scripts/monitor/review_loop.py:1242`)
injects "re-run the review sub-procedure **end to end**" on every auto-recheck
round. Each round is therefore a fresh unbounded search over an ill-defined
concern space, not a delta check against round N−1 — and stronger shadow models
find *more* each round. Reviews have been observed not to converge after 10.

This task makes recheck rounds **delta-scoped**: the producer verifies the prior
round's concerns against a durable, identity-bound record, and hunts new concerns
only where the improve side touches an obligation dimension. Convergence comes
from **scope**, never from relabeling a concern's disposition. When the record
cannot be consulted, the round **fails safe to a full review** and can never
certify a clean round.

Formerly `t1636_5`; parked as a standalone task on 2026-08-31 at the plan
checkpoint, work not started. Its prerequisites (t1636_3, t1636_4) have landed
and archived, so nothing blocks it. The parent plan's t1636_5 section remains the
binding spec; this plan sequences it.

## Verification pass — 2026-08-31

Re-checked against the tree after siblings _1.._4 landed. **Line numbers below were
current on 2026-08-31 and will drift — re-verify before implementing.** The approach
holds. Four corrections and two simplifications, folded into the steps below:

1. **Line drift.** `format_block_meta` is now `monitor_shared.py:3383` (was 2914 —
   t1636_4 inserted the trade-profile helpers). The t1448 pair contract is
   `concern_parser.py:266-274` (was 219). `_META_LINE` is at 261. The two clean-round
   literals are **unchanged** at `monitor_app.py:3099` and `minimonitor_app.py:4245`;
   the fire path is `_write_shadow_prompt`, `minimonitor_app.py:4040-4056`.
2. **The toast is a THIRD site, not covered by `format_block_meta`.**
   `minimonitor_app.py:4441` builds its own `f" (round {meta.round})"`. The task's
   AC requires the toast to carry the scope, so it needs its own edit.
   `monitor_app.py` has no analogous toast.
3. **Website docs are out of scope.** The old step 6 hedged "website shadow-agent.md
   *if* it describes the recheck loop". `t1636_7` is the dedicated website-docs child
   and explicitly claims that page (and explicitly leaves
   `aidocs/framework/shadow_agent.md` to this task). Removed.
4. **Archival pruning needs no new wiring.** `aitask_archive.sh:207` calls
   `aitask_shadow_rejected.sh prune`, which sweeps **every regular file** under
   `.aitask-shadow/<task_id>/` and rmdirs it — so `prior_round.md` is pruned for
   free. What is owed is a *test* pinning it, not code. The mutex is per-file
   (`<store_file>.lockd`), so the record's lock is distinct from the rejected
   store's — no contention.
5. **Simplification — one identity token, and it closes an injection surface.**
   The old design passed `--round N --reviewed-at TS --digest D` to `read`. But the
   *shadow agent* is the caller that re-invokes `read` using values it read out of a
   prompt, and `reviewed_at` is verbatim agent-authored text — a shell-argument
   surface built from untrusted content. `_last_block_region` returns everything
   between the fences **including the `Round:` header**, so a digest over that region
   already binds round + reviewed_at + every item, in one safe-charset token. `read`
   therefore takes **`--digest D` only**, validated `^[0-9a-f]{8,64}$`. Round and
   reviewed_at are still *stored* in the record (the producer needs them for
   "Unresolved from round N−1" prose) — they are just not match keys on a command
   line. This satisfies "identity-bound per the t1448 pair contract" more strongly
   than the pair did.
6. **Simplification — reuse `concern_block_signature`** (`concern_parser.py:855`)
   instead of a new `-J`-shaped digest. Writer and reader only ever compare strings
   the *writer* produced, so cross-capture-mode exactness is irrelevant; its
   normalization (ANSI-strip → whitespace-collapse → sha256[:16]) is total over any
   input. Add one docstring note recording the `-J` use.

## Steps

### Pre-phase (risk mitigations)

- **`characterize_meta_line_grammar`** — before touching `_META_LINE`, add
  characterization tests to `tests/test_concern_parser.py` pinning current
  behavior over every legacy header shape (`Round: 2`, `Round: 2 @ ts`,
  `Round: 0`, zero-padded, 10-digit, trailing whitespace) across all four
  consumers: `parse_block_meta`, `parse_reviewed_at_epoch`,
  `is_metadata_only_block`, `has_invalid_round_header`. They must pass on the
  **unmodified** grammar first — that is what makes them a baseline rather than a
  restatement of the new code. Addresses the code-health risk below.

### 1. `_META_LINE` scope extension (`concern_parser.py`)

- Grammar gains an optional trailing group before the terminal `\s*$`:
  `(?:\|\s*scope:\s*(?P<scope>\w{1,16}))?`. The `at` group is lazy (`.*?`), so the
  scope group must be anchored after it — a leak into `at` would make
  `parse_reviewed_at_epoch`'s strict round-trip return `None` and silently break
  freshness.
- **Bounded-permissive `\w{1,16}`, not a closed `delta` class** — deliberate, and the
  opposite of the closed dimension vocabulary. An unknown scope token must degrade to
  *unscoped* while **keeping round and reviewed_at**, because that pair is the t1448
  freshness key and the auto-offer dedup key; failing the whole line over an
  unrecognized scope would sacrifice load-bearing information to police a label. The
  consumer side is where it is closed: **only `meta.scope.lower() == "delta"` selects
  delta wording**; anything else renders exactly as today.
- `BlockMeta.scope: str = ""` appended **with a default**, preserving two-arg
  construction (`tests/test_concern_picker_modal.py` constructs `BlockMeta(2, "…")`).
- Document in the field docstring that whole-tuple length / equality / unpacking is
  **not** backward compatible, and that the t1448 key stays the `(round, reviewed_at)`
  **attribute pair** — assert attribute access at the dedup call sites, never
  whole-tuple equality.
- Tests: every legacy shape parses with `scope == ""`; a scoped header-only block
  still certifies via `is_metadata_only_block` (required — a clean delta round emits
  exactly `Round: N @ ts | scope: delta` between the fences) and keeps
  `has_invalid_round_header` False; `parse_reviewed_at_epoch` returns the same epoch
  scoped and unscoped; an unknown token keeps round/reviewed_at and yields plain
  wording.

### 2. Centralized scope-aware labeling (`monitor_shared.py`)

- New `clean_round_msg(meta) -> str`: `delta` → `"Clean delta review (round N) — prior
  concerns resolved, no new obligation concerns"`; otherwise today's
  `"Clean review (round N) — no concerns"`.
- Replace **both** duplicated literals — `monitor_app.py:3099`,
  `minimonitor_app.py:4245` — with calls. This is the deduplication half of the step,
  not just a feature.
- `format_block_meta` (`:3383`) appends the scope to its suffix
  (`  ·  round 3, 14:03:27Z, delta`), which carries it to the picker context line
  (`monitor_shared.py:4001`).
- **Third site (correction 2):** `minimonitor_app.py:4441`'s auto-offer toast builds
  its own round suffix and does **not** route through `format_block_meta`. Give it the
  scope too — reuse `format_block_meta` there if the surrounding format allows,
  otherwise mirror it explicitly.
- Per-surface tests: both apps' metadata-only messages, the picker context line, and
  the toast each show scoped wording for a `scope: delta` block and unchanged wording
  for a scopeless one.

### 3. Round-record helper (new `.aitask-scripts/aitask_shadow_round_record.sh`)

Modeled on `aitask_shadow_rejected.sh` **including its write discipline**:
`lib/registry_lock.sh` mutex around the RMW, landing write through
`lib/atomic_write.sh` `ait_atomic_render` ("Never an open-coded mktemp-then-mv"),
`LOCK_BUSY` exit 3 with nothing written, same exit-code vocabulary (0 / 2 / 3 / 4),
same `resolve_task_id` normalization, same own-root guard on `prune`.

- `write <task_id> --round N --reviewed-at TS --digest D` — items on stdin. Refuses
  empty input, any line not beginning `- [`, and any fence (`===CONCERNS===` /
  `===END-CONCERNS===`): the store's `read` output is fed back into the shadow's
  context, so a fence in it could forge a block. Stores round / reviewed_at / digest
  plus the items.
- `read <task_id> --digest D` — **digest is the only match key** (correction 5),
  validated `^[0-9a-f]{8,64}$` (a malformed digest is a usage error, exit 2, not a
  mismatch). Prints the record only on an exact match; the single line `NO_RECORD`
  when absent; `IDENTITY_MISMATCH` with a non-zero exit otherwise.
- Record at `.aitask-shadow/<task_id>/prior_round.md` — **one file plus
  verify-on-read**; per-identity files would accumulate unboundedly.
- `prune` needs no wiring (correction 4) — pinned by a test instead, see the
  post-phase.
- `shellcheck` clean.

### 4. Fire-path record write (`minimonitor_app.py`)

- **Placement is load-bearing: the record write goes at the very top of
  `_write_shadow_prompt`, BEFORE `fresh = await capture_raw_tail(...)`.** Everything
  from that line onward — the pre-send revalidation, the delivery-token re-check, the
  settle latch — was hardened on the premise that readiness is revalidated
  *immediately* before sending; inserting a subprocess await inside that window would
  widen exactly the gap those guards close. Placing it above leaves the existing
  sequence byte-for-byte unchanged and adds the new await outside the tightened
  region. (Writing a record for a round that the revalidation then vetoes is
  harmless: the next real fire overwrites it, and a leftover record whose digest does
  not match the next prompt simply mismatches → fail-safe full review.)
- Hoist the `task_id` resolution — it currently lives inside the
  `contextlib.suppress(Exception)` block that exists only for `phase` (`:4042-4049`) —
  so the record write can use it. No task id → no record (fail-safe).
- Compute the digest with `concern_block_signature(tick_text)` (correction 6).
  `tick_text` is the authoritative `-J` capture from `capture_shadow_text`
  (`monitor_core.py:584`) — the same text the prompt's `parse_block_meta` reads, so
  record and prompt agree by construction.
- `block_head_truncated(tick_text)` or no complete block (`concern_block_signature`
  returns `None`) → **write no record**.
- Invoke the helper via `asyncio.create_subprocess_exec` with a bounded timeout,
  mirroring the `_BOARD_COLUMN_SH` pattern at `minimonitor_app.py:2746` including its
  kill-then-reap on timeout. Timeout, `LOCK_BUSY`, or any non-zero exit → proceed
  with **no record named**: a slower round, never a frozen UI, never a false clean.
- `compose_recheck_prompt` (`review_loop.py:1242`) gains an optional record-identity
  argument and states the delta contract instead of "end to end". Still **one line**,
  still opening with the verbatim `refetch and recheck[ round N]` routing trigger
  (t1493) — that prefix is what re-enters the producers' Step 3. With a record:
  names the prior round, its timestamp, and the digest. Without: the tail states
  delta scoping is unavailable and requests a full re-review. Keep the existing
  `" ".join(text.split())` newline guarantee.

### 5. Producers' re-review entry (four docs, two-placement discipline)

`impl-challenge.md`, `plan-challenge.md`, `plan-assumptions.md`,
`plan-diagnose-errors.md` — a bolded pre-emit directive **and** a rules-list entry in
each, matching how the rejection-suppression rule is stated (the placement-aware
guard depends on both copies).

- **Reader contract**, three outcomes, mirroring the rejection store's: an
  identity-matching record / the single line `NO_RECORD` / **anything else** (non-zero
  exit, `IDENTITY_MISMATCH`, empty, unrecognized) = "could not consult".
- **Delta contract:** re-emit unresolved or regressed prior concerns as **ordinary
  items** whose body opens `Unresolved from round <N-1>: …` / `Regressed: …` — so the
  block is never metadata-only while anything actionable is outstanding
  (`is_metadata_only_block` would otherwise certify a false clean). Name resolved ones
  in prose. Hunt new concerns only where the improve side touches an obligation
  dimension.
- **Never relabel for control flow.** A concern's disposition is its true rubric
  disposition — "informational is never a parking slot"
  (`impl-review-angles.md:238`). Convergence comes from scope, so an incidentally
  noticed non-obligation finding is still emitted, with its true disposition.
- Emit `| scope: delta` in the round header of a delta round.
- **Fail-safe:** could-not-consult / mismatch / `NO_RECORD` on round > 1 → full
  review, say delta scoping was skipped, emit **no** scope token, and never emit a
  metadata-only block on the strength of unverifiable prior-round claims.
- Clean (delta) = record consulted **and** all prior actionable resolved **and** the
  scoped search found nothing new.
- Guard: `TestProducerDeltaRecheckRule` in `tests/test_concern_parser.py`, mirroring
  `TestProducerRejectionSuppressionRule` — same `_producers()` discovery, the
  `test_producer_set_is_the_known_set` guard, and a **negative control on synthetic
  text** (never a mutate-and-restore of a repo file — this worktree is shared with
  concurrent sessions) proving the predicate is placement-aware, with one case
  targeting the fail-safe sentence specifically.

### 6. Docs

- `.claude/skills/aitask-shadow/concern-format.md` — the scope token in the "Round
  header" section (its "four consumer roles" bullet gains the delta scoping), and a
  new "## Delta-scoped recheck rounds" section beside "## Rejected-concern
  suppression" carrying the record, the digest-only reader contract as a three-outcome
  table, and the fail-safe rule. Follow the t1123 discipline for examples.
- `aidocs/framework/shadow_agent.md` — "## Review-loop automation (auto-recheck)"
  (`:564`) and "### The round header" (`:875`).
- **Website docs belong to t1636_7** (correction 3) — do not touch
  `website/content/docs/`. Note that t1636_7 was unblocked from this task when it was
  parked, so if t1636_7 has already landed, re-check whether its prose now needs a
  follow-up pass for the delta loop.

### Post-phase (risk mitigations)

- **`assert_prune_sweeps_the_round_record`** — extend
  `tests/test_archive_shadow_prune.sh` to seed a `prior_round.md` alongside
  `rejected.md` and assert archival sweeps **both**. The store gains a second file and
  the existing test only knows about the first; without this, a future prune narrowed
  to `rejected.md` would leak one record per archived task, silently. Addresses the
  code-health risk below.

## Verification (binding — from the parent plan)

- **Helper** (`tests/test_shadow_round_record.sh`, mirroring
  `tests/test_shadow_rejected.sh`): malformed record; fence-bearing / non-item /
  empty input refused; a failed or partial write leaves no record
  (`ait_atomic_render` refusal paths); concurrent writer → `LOCK_BUSY` (exit 3) with
  nothing written; identity fields round-tripped exactly; digest mismatch → non-zero
  and **no record content on stdout**; a malformed `--digest` argument → exit 2, not a
  mismatch.
- **Delivery** (`tests/test_minimonitor_concern_action.py`): the record is written
  with the digest of the very block the prompt names; a head-truncated capture writes
  **no** record; helper timeout / `LOCK_BUSY` still fires with no record named and
  never blocks the event loop (a fail-safe path, not an error); **ordering** — assert
  the record write precedes the pre-send revalidation capture, not a call count.
- **Surfaces:** both apps' metadata-only messages, the picker context line, and the
  minimonitor toast show scoped wording for a `scope: delta` block and unchanged
  wording without one.
- **End-to-end invariant:** an unavailable, mismatched, or missing record forces a
  full review and can **never** certify a clean round. Negative control: a
  producer-doc mutation dropping the fail-safe sentence trips
  `TestProducerDeltaRecheckRule`.
- `bash tests/run_all_python_tests.sh --test-dir tests` — **read only the last line**.
- `bash tests/test_shadow_round_record.sh`, `bash tests/test_archive_shadow_prune.sh`,
  `bash tests/test_concern_parser.py` via the runner.
- `./.aitask-scripts/aitask_skill_verify.sh` for the producer-doc changes;
  `shellcheck .aitask-scripts/aitask_shadow_round_record.sh`.

## Risk

Assessed 2026-08-31 against the tree as it stood then. Re-run the risk evaluation
when this task is eventually picked — the levels below describe that tree.

### Code-health risk: medium

- `_META_LINE` is the grammar four independent consumers key off
  (`parse_block_meta`, `parse_reviewed_at_epoch`, `is_metadata_only_block`,
  `has_invalid_round_header`). A regression there is **silent**: a header stops
  parsing, the round is lost, and the t1448 freshness key plus the auto-offer dedup
  degrade with no error anywhere · severity: medium · → mitigation: inline pre-phase
  characterize_meta_line_grammar
- The shadow store gains a second file while archival pruning and its test know only
  about `rejected.md`; a future narrowing of `prune` would leak one record per
  archived task, unnoticed · severity: low · → mitigation: inline post-phase
  assert_prune_sweeps_the_round_record
- A new subprocess `await` on the recheck fire path, adjacent to the pre-send
  revalidation / delivery-token / settle-latch guards that were hardened on a tight
  capture-to-send window · severity: medium · → mitigation: settled in the plan —
  Step 4 pins the write **above** `capture_raw_tail`, leaving the guarded sequence
  unchanged, and the ordering is asserted in Verification. No follow-up needed.
- Blast radius: 3 Python modules, 4 producer docs, 2 framework docs, 1 new shell
  helper. Bounded by the fact that the parser change is a single optional
  non-capturing group with a defaulted NamedTuple field, the helper mirrors an
  existing well-tested one, and Step 2 **removes** duplication rather than adding it ·
  severity: low · → mitigation: none — accepted

### Goal-achievement risk: medium

- Convergence is enforced by **producer prose an LLM must honor**, not by code. The
  machine substrate (record, scope token, fail-safe) is fully verifiable; that rounds
  actually converge is not directly assertable in a test · severity: medium · →
  mitigation: none new — `t1636_6` was the aggregate manual-verification child for
  this surface, but this task was stripped from it when it was parked, so **this task
  now owes its own manual verification** when it lands
- The digest-only `read` key (correction 5) is a **deliberate deviation** from the
  task file's stated `--round N --reviewed-at TS --digest D`. It is strictly stronger
  (the digest covers the header, hence both fields, plus content) and removes an
  injection surface, but it is a deviation and is stated here rather than made
  silently · severity: low · → mitigation: none — accepted, documented above

### Planned mitigations

- timing: pre-phase | name: characterize_meta_line_grammar | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — silent `_META_LINE` grammar regression | desc: characterization tests pinning current header-grammar behavior across all four consumers, passing before the grammar edit
- timing: post-phase | name: assert_prune_sweeps_the_round_record | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — second store file unknown to archival pruning | desc: extend `tests/test_archive_shadow_prune.sh` to seed `prior_round.md` and assert archival sweeps both store files

**Reassessment (post-inline).** Both confirmed mitigations are test-only, separable
additions that change no production behavior, so the augmented plan's levels are
unchanged: code-health stays **medium** and goal-achievement stays **medium**.

## Post-Implementation

Standard Step 9.
