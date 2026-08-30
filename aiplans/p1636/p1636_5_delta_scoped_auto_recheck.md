---
Task: t1636_5_delta_scoped_auto_recheck.md
Parent Task: aitasks/t1636_shadow_concern_impact_vector_model.md
Sibling Tasks: aitasks/t1636/t1636_1_concern_dimension_vocabulary_module.md, aitasks/t1636/t1636_2_concern_parser_impact_trailer.md, aitasks/t1636/t1636_3_producers_emit_impact_trailer.md, aitasks/t1636/t1636_4_picker_trade_profile_rendering.md
Archived Sibling Plans: aiplans/archived/p1636/p1636_*_*.md
Branch: main
Base branch: main
Output branch: main
---

# p1636_5 — Delta-scoped auto-recheck (convergence by construction)

Makes shadow recheck rounds delta-scoped: verify prior concerns' status, hunt
only new obligation-touching concerns, with a durable identity-bound record of
the prior round and fail-safe full review when it cannot be consulted. Depends
on t1636_3 (extends the producers' re-review entry) AND t1636_4 (both edit
`monitor_shared.py`). The parent plan's t1636_5 section is the binding spec —
re-read it before implementing; this plan sequences it.

## Steps

1. **`_META_LINE` scope extension** (`concern_parser.py`):
   - grammar: `Round: <N> @ <ts>` gains optional trailing `| scope: <token>`
     as a separate named group (`(?:\|\s*scope:\s*(?P<scope>\w{1,16}))?`
     before the terminal `\s*$`) — the scope must never leak into the `at`
     group (`.*?` is lazy; anchor the scope group so `parse_reviewed_at_epoch`
     input is unchanged);
   - `BlockMeta.scope: str = ""` appended with default;
   - **two-field compatibility contract** (tests): every legacy header shape
     (with and without `@ <ts>`) parses to unchanged `round`/`reviewed_at`
     with `scope == ""`; `BlockMeta(3, "…")` two-arg construction preserved;
     `parse_reviewed_at_epoch` on scoped headers returns the same epoch as
     unscoped (a leak would silently return None — a freshness regression);
     the t1448 freshness key stays the `(round, reviewed_at)` attribute pair
     at the dedup call sites (assert attribute access, not whole-tuple
     equality); document in the field docstring that whole-tuple
     length/equality/unpacking is NOT backward compatible.

2. **Centralized scope-aware labeling** (`monitor_shared.py`):
   - `clean_round_msg(meta) -> str`: scope `delta` → "Clean delta review
     (round N) — prior concerns resolved, no new obligation concerns";
     scopeless → today's "Clean review (round N) — no concerns";
   - replace BOTH duplicated literals (`monitor_app.py:3099`,
     `minimonitor_app.py:4245`) with calls;
   - `format_block_meta` (line 2914) appends the scope to its suffix
     (`round 3, 14:03:27Z, delta`) so the picker context line and auto-offer
     toasts carry it;
   - per-surface tests: both apps' metadata-only messages, picker context
     line, toast — each shows the scoped wording for a `scope: delta` block.

3. **Round-record helper** (new `.aitask-scripts/aitask_shadow_round_record.sh`),
   modeled on `aitask_shadow_rejected.sh` INCLUDING its write discipline:
   - `lib/registry_lock.sh` mutex around the RMW; landing write through
     `lib/atomic_write.sh` `ait_atomic_render` ("Never an open-coded
     mktemp-then-mv"); `LOCK_BUSY` exit 3 with nothing written;
   - `write <task_id>` (items on stdin, `--round N --reviewed-at TS
     --digest D`): items-only — reject any line not beginning `- [` and any
     fence (the store can never become a block); refuse empty input;
   - `read <task_id> --round N --reviewed-at TS --digest D`: prints the
     record ONLY when stored identity matches all three; single line
     `NO_RECORD` when absent; `IDENTITY_MISMATCH` (non-zero) otherwise —
     the reader contract's "anything else" arm;
   - record file `.aitask-shadow/<task_id>/prior_round.md` (one file +
     verify-on-read; per-identity files would accumulate unboundedly);
   - wire archival pruning exactly like the rejected store
     (`test_archive_shadow_prune.sh` names the seam).

4. **Fire-path record write** (`minimonitor_app.py` ~4041-4051):
   - at recheck-fire time, from the authoritative `-J` capture already taken
     for the settle checks: if `block_head_truncated` or no complete block →
     write NO record; else compute digest over the wrap-joined block region
     (sha256 prefix, mirroring `concern_block_signature`'s normalization but
     on the `-J` shape — document the difference) and invoke the helper
     `write` via **asyncio subprocess with a bounded timeout** (pattern:
     the existing `asyncio.create_subprocess_exec` call at ~2746);
   - timeout or `LOCK_BUSY` → proceed with NO record named (fail-safe: slower
     round, never a frozen UI, never a false clean);
   - `compose_recheck_prompt` (`review_loop.py:1242`) gains the record
     identity: "refetch and recheck round N — prior round M @ <ts>, record
     <digest-prefix>: <delta-contract tail>" (still one line, still opening
     with the verbatim "refetch and recheck" routing trigger); no record →
     the tail states delta scoping is unavailable and requests a full
     re-review.

5. **Producers' re-review entry** (all four docs, two-placement discipline,
   extending the t1636_3 rules):
   - read the record via the helper; three outcomes: identity-matching
     record / `NO_RECORD` / anything else = "could not consult";
   - delta contract: re-emit unresolved/regressed prior concerns as ordinary
     items, body opening `Unresolved from round <N-1>: …` / `Regressed: …`;
     name resolved ones in prose; hunt new concerns only where the improve
     side touches an obligation dimension; an incidentally noticed
     non-obligation finding is emitted with its TRUE disposition — never
     suppressed, never relabeled (informational is never a parking slot);
   - emit `| scope: delta` in the round header of a delta round;
   - **fail-safe**: could-not-consult / mismatch / `NO_RECORD` on round > 1 →
     FULL review, state delta scoping was skipped, NO scope token, and never
     a metadata-only block from unverifiable prior-round claims;
   - clean (delta) = record consulted + all prior actionable resolved +
     scoped search found nothing new; previously-reported unchanged
     informational items are suppressed via the record and named in prose;
   - producer-rule guard (`TestProducerDeltaRecheckRule` mirroring the
     existing producer-rule classes) with a negative control covering the
     fail-safe sentence specifically.

6. **Docs**: `concern-format.md` documents the scope token, the round record,
   and the reader contract (t1123 discipline for examples);
   `aidocs/framework/shadow_agent.md` staleness/loop sections updated;
   website shadow-agent.md if it describes the recheck loop.

## Verification (binding — from the parent plan)

- Helper (`tests/test_shadow_round_record.sh`, mirror
  `tests/test_shadow_rejected.sh`): malformed record; fence-bearing/truncated
  input refused; failed/partial write leaves no record (`ait_atomic_render`
  refusal paths); concurrent writer → `LOCK_BUSY` nothing written; identity
  fields round-tripped exactly; identity mismatch → non-zero + no record
  output.
- Delivery (python, minimonitor tests): record written with the identity of
  the very block parsed; prompt names that identity; head-truncated capture →
  no record; helper timeout/LOCK_BUSY at fire time still fires with no record
  named, never blocks the event loop (fail-safe path, not an error).
- Surfaces: both apps + context line + toast show scoped wording.
- End-to-end invariant: unavailable/mismatched/missing record ⇒ full review,
  never a clean certification; negative control: producer-doc mutation
  dropping the fail-safe rule trips the guard.
- `bash tests/run_all_python_tests.sh --test-dir tests` (last line only);
  `./.aitask-scripts/aitask_skill_verify.sh`; `shellcheck` on the new helper.

## Post-Implementation

Standard Step 9.
