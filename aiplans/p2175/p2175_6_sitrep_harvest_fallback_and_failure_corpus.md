---
Task: t2175_6_sitrep_harvest_fallback_and_failure_corpus.md
Parent Task: aitasks/t2175_sitrep_repo_todo_list_steward.md
Sibling Tasks: (none pending)
Archived Sibling Plans: aiplans/archived/p2175/p2175_*_*.md
Base branch: main
Output branch: main
---

# t2175_6 — Sitrep harvest fallback: preserve uncertain output, queue agent review, keep a failure corpus

## Context

The harvest (t2175_2) parses a finished agent's capture into sitrep items and
then writes a receipt that lets `drop` / `purge` delete the capture. When the
parse is unreliable (incomplete banner, malformed follow-up, truncated passage,
a banner the grammar does not recognise) it only prints `HARVEST_WARN:` and
still certifies success, so text that still needs interpretation can be deleted.
This task adds a deterministic confidence check. Uncertain output is then kept
verbatim in the repository's sitrep store together with diagnostics and one
durable "Analyze unparsed agent output" review item for the sitrep agent. These
retained cases also form a local corpus for improving the parser.

Measured before planning (read-only, prototype of the signals below over the 21
local frozen captures in `~/.config/aitasks/frozen/`): 9 parse a banner, 0 have a
near-miss banner, 0 have a malformed `Created:` line, 0 incomplete banners, 0 bad
follow-ups. Six `pick` records have **no** banner because they were frozen
mid-work, so "pick with no banner" must not be a reason. Largest capture is
1.0 MB, and all are valid UTF-8 with no NUL bytes.

Notes acknowledged (advisory): t2175_4 — fit review cases into `triage --open`
as one more evidence kind, so the agent judges; t2175_5 — the monitor `h` dialog
needs distinct wording for "preserved" in `HarvestReport`.

Plan review round 1 (user; all three concerns verified against the code and adopted):
- **Legacy receipts.** `receipt_valid` and `capture_harvested` carried no
  version, so pre-upgrade receipts would keep authorising drop and purge of
  output that the new classifier would flag. Fixed by the certification version
  below.
- **Detection coverage.** The marker and `Created:` rules were "any success in
  scope", so one success hid a failure next to it. Both are now per-occurrence
  pairing.
- **Case provenance.** A key hit dropped the new origin. Origins and analyses are
  now written per source identity; only the review item is deduplicated.

## Design (decisions)

- **Classification** (`sitrep_harvest.assess`, pure): `reliable` | `empty` |
  `review`. `review` when any reason fires. Reasons carry 1-based line ranges
  into the raw input:
  - `banner_incomplete:t<id>` — a recognised first line whose fields are missing or invalid (the existing `complete_fields`);
  - `bad_followup:<tok>` — a follow-ups token outside the grammar (existing). An **unresolved** cross-repo token is valid, so it is no reason;
  - `passage_truncated:t<id>` — the passage was clipped to the retain limit (existing);
  - `banner_unparsed` — every **occurrence** of `[✔■]\s*aitask workflow (complete|stopped)\b` is checked; one is accounted for only when it is the first-line match of a parsed banner. Coverage by a banner's field lines does not count, so a banner text quoted inside a `reason:` value still fires. The reason is per line: L<n> gives the occurrence count beyond the accounted ones;
  - `created_unparsed` — every **occurrence** of `NEAR_CREATED_RE = Created:\s*aitasks/` (`\s` includes NBSP) is checked. It is valid only when a `CREATED_RE` match starts at the same offset, so a valid and a malformed reference on one line give one item AND one reason;
  - `marker_without_banner:<run>` — every tool-output marker line `^\s*⎿\s+HARVEST_RUN:<16hex>\s*$` must be **claimed** by a parsed banner. The pairing is the one identity already uses: for each banner, `find_marker(lines, passage_start, floor)` from `Harvest.run`'s own passage loop, factored into a shared `pair_markers(lines, banners, piped)`. Any marker no banner claims is a reason; another run's banner never covers it;
  - `pipe_without_banner` — a non-blank `banner` (piped) input with zero parsed banners. One pipe is one run, so the scope is the whole input.

  These are **not** reasons: no banner at all (a mid-work freeze), an unresolved
  foreign task, a missing task file, duplicates. `empty` means no content and no
  reasons. Partial extraction is never suppressed by a reason: every parsed
  banner, follow-up and `Created:` item is still written. A reason only adds the
  case and the review.
- **Certification version (the legacy-receipt migration).** The receipt gains a
  third line `cert=2`, the classification-aware certificate: `HARVEST_CERT = 2`
  in `sitrep_harvest.py`, and `agent_sessions.HARVEST_RECEIPT_CERT`, which must
  be equal (tested like `RECEIPT_SUFFIX`). Both consumers require it:
  - `receipt_valid` already compares the exact text, so a legacy receipt fails it and `cmd_plan` re-harvests (classify, then record the case if needed) instead of returning `already_harvested`;
  - `agent_sessions.capture_harvested` requires `cert=<HARVEST_RECEIPT_CERT>` as well as the sha line, so a legacy receipt no longer authorises `drop` (`HARVEST_REQUIRED`) or `purge` (`KEPT:…|unharvested_text`) until a cert-2 harvest has run.

  Re-harvesting a legacy capture is safe: the identity keys make every existing
  item `exists` (dismissals stick) and only the classification is new.
  `aitask_frozen.sh drop` harvests first, and the monitor's maintenance
  `harvest all` (every ~10 min) upgrades the rest. The monitor kill path, which
  does not harvest, refuses until then. That is fail-closed by design, and
  `--skip-harvest` remains the explicit discard. Every receipt writer
  (`nothing_found`, `sitrep_agent`, `apply`) writes cert 2.
- **Wire**: a new event line
  `HARVEST_REVIEW:<src>|c<N>|added|exists|case=<hex16>|<reason codes csv>`, and
  the final `HARVESTED:<src>|added=a|existing=e` gains `|review=c<N>` only when a
  case exists. The final kinds stay the same, so `agent_freeze._harvest_record`
  (which treats any non-FAILED final with exit 0 as success) is correct as it is.
  A preserved case **is** a successful harvest. The receipt is written only after
  the case and its review item are durable.
- **Raw evidence**: a new writer verb `retain-raw` writes content-addressed
  `raw/<16hex>.txt` (the bytes received, verbatim; no UTF-8 requirement; NUL
  refused; cap 64 MiB; refuses a hash collision; atomic under the writer lock).
  Above the cap the harvest fails: `HARVEST_FAILED:…|case_input_too_large`,
  with no receipt and the original kept. Nothing is ever truncated. The harvest
  compares the writer's reported sha256 with its own; a mismatch (for example a
  NUL stripped by bash) is `case_raw_mismatch` and fails closed.
- **Case files**: small retained files in `sources/` written with the existing
  `retain`. Their content is deterministic, so a retry rewrites identical bytes:
  - **origin** manifest `sitrep harvest case origin v1`, **one per distinct source identity** — the `input=raw/<hex>.txt` path, the input's sha256, byte count and line count, the source (`record`/`capture`/`banner`), src label, record, run, agent, task, skill, pane, project, worktree, capture path, and `captured_at` (the record's `frozen_at`, else `-`). There is no harvest timestamp, so a retry of the same identity produces identical bytes and the retain is a no-op. A different record, run or source mode with the same bytes gets its own origin file;
  - analysis `sitrep harvest analysis v1`, one per (origin, parser revision) — `case=`, `origin=sources/<origin hex>.txt` (or `origin=replay`), `parser=<PARSER_REV>`, `parser_sha=` (the first 16 hex of the sha256 of `sitrep_harvest.py`), `class=`, `reason=<code>|L<a>-L<b>|<detail>` lines, `warn=` lines, and `item=c<N>|<kind>|<ref>` lines (that origin's partial items, with no added/exists flag so the file stays deterministic, since a retry reports the same ids). This file is the durable link from an origin to its items;
  - key `sitrep harvest case key v1` / `input=<sha256>` — the identity, added to `KEY_FILE_HEADERS`;
  - one excerpt — ±20 lines around the first reason, capped at 400 lines — so `PASSAGE:` has something short to read.
- **Review item**: `kind=question derived=script group=now`, titled
  `Analyze unparsed agent output of t<task> (<agent>): <codes>`. Its context
  holds the excerpt, manifest, analysis and key as `capture:` sources, and
  `related:` names the partial items and triage items from the same harvest
  (capped at 20; the analysis file has the full list). Identity is **per input**
  (one review item per case): if the key is already owned (any state), the
  existing item is reported `exists` and a done or dismissed item stays closed,
  never reopened. **Provenance is per origin.** Even when the key is owned,
  `record_case` still retains `raw/` (dedup no-op), this origin's manifest and
  this origin's analysis. Only the item `add` is skipped. A new origin is
  therefore durable and discoverable (`case show` lists every `ORIGIN:` with its
  `ANALYSIS:` and items) without a duplicate review, and an ordinary retry of
  one identity writes nothing new because the bytes are identical. Write order is
  raw → excerpt → origin → analysis → key → item `add` last, so an existing item
  implies its first origin's files exist, and a partial earlier attempt is
  completed on retry. Cases are discovered by a `sources/` scan, never through
  the item context, so no context rewrite or size limit is involved.
- **Review records** `sitrep harvest review v1` (append-only retained files):
  `case=`, `at=`, `by=`, `outcome=recovered|nothing_missed|noise|unrecoverable|resolved`,
  `gap=`, `note=`, `recovered=c..`, `parser=`, `fixture=`. Review state is the
  item's state plus the review files. Nothing ever deletes `raw/` or `sources/`.
- **Retained-source checks**: `check-sources` also follows each case manifest
  and prints `SOURCE_OK|SOURCE_MISSING:c<N>|raw/<hex>.txt`; a sha mismatch counts
  as missing. The fixture store has no cases, so its pinned output is unchanged.
- **Demonstration gap and fix**: workflow-end.md requires a fenced banner because
  unfenced markdown joins its lines into one paragraph. A **joined banner**
  (`✔ aitask workflow complete — t42 name outcome: … · pushed: yes follow-ups created: t43`,
  possibly terminal-wrapped) is not parsed today. The near-miss rule catches it,
  and this task adds the parse behind `ACCEPT_JOINED_BANNER = True` and bumps
  `PARSER_REV` from 1 to 2. That gives one real end-to-end case: missed, then
  preserved, then replayed, then resolved, then turned into a fixture.
  **Caveat:** this layout is synthetic. It comes from the rule's rationale and was
  not seen in local captures.

## Implementation steps

### Pre-phase (risk mitigations)
1. [detection_baseline] Implement `Reason` / `assess()` / `needs_apply()` and
   the joined-banner parse first (step 2's parse half), before any corpus code.
   Run a read-only script that imports the lib over every
   `~/.config/aitasks/frozen/*/capture.txt` and every
   `tests/fixtures/sitrep_harvest/*.txt`, printing per-file class and reason
   codes. Required: 0 `review` on the 21 local captures; on the fixtures, only
   `truncated_banner` (banner_incomplete) plus the new trigger fixtures. Any
   other review is inspected by eye. If the capture parsed correctly, tighten
   that rule (and add the input as a negative unit case) before continuing.
   Record the exact per-reason counts in Final Implementation Notes.

1. **`lib/sitrep_todo.py` + `aitask_sitrep_todo.sh`** — `retain-raw` op (core:
   validate, compute hex/sha, `@TARGET:raw/<hex>.txt`, print
   `RETAINED_RAW:raw/<hex>.txt|<sha256>|<bytes>`, refuse a collision or a
   non-regular file). Wrapper: `cmd_retain_raw` mirroring `cmd_retain` (mkdir
   `raw/`, `ait_atomic_render`). Add `CASE_MANIFEST_HEADER` and
   `case_raw_of(store, hexname)` (parses `input=` / `input_sha256=` from a
   manifest). `op_check_sources` follows manifests. Update the module doc
   (FILES: `raw/`) and the wrapper header (verbs, `raw/`). The todo.md format
   does not change.
2. **`lib/sitrep_harvest.py`**:
   - `PARSER_REV = 2` and `ACCEPT_JOINED_BANNER = True`. In `parse_banners`, a
     `JOINED_RE` branch matches the first line with ` outcome: ` inline, joins up
     to `MAX_CONTINUATION` continuation lines, then splits the labels in template
     order (complete: `outcome`, `follow-ups created`; stopped: `outcome`,
     `reason`, `next`, each once and in order, otherwise fields stay partial
     and `complete_fields` is False), then calls `_interpret`.
   - `Reason` dataclass (code, detail, a, b) and `assess(lines, banners, piped)`
     for the parse-level reasons above, **per occurrence**. The marker check
     uses the shared `pair_markers(lines, banners, piped)`, factored out of
     `Harvest.run`'s passage loop. `run()` and `assess()` both call it, so the
     identity pairing and the detection pairing cannot drift. `CREATED_RE`
     offsets are compared per `NEAR_CREATED_RE` occurrence, and banner first
     lines are counted per occurrence. `has_content()` becomes
     `needs_apply(data, piped)` = content OR reasons (the plan phase uses it, so
     a near-miss-only capture reaches `apply` instead of `nothing_found`).
   - `Harvest`: record item ids (`self.item_ids`) and passage-truncation reasons
     during `run()`. `Harvest.reasons` = assess + run-time reasons.
   - `capture_file_kind`: add `case`, `analysis` and `review`; the case key joins
     `KEY_FILE_HEADERS`.
   - `cmd_apply`: after `h.run()`, if reasons exist, call
     `sitrep_corpus.record_case(store, src, h)` (lazy import), then emit
     `HARVEST_REVIEW:`, then the receipt, then the final line with `review=`.
     Test seam `AITASK_SITREP_HARVEST_FAULT=case:raw|case:files|case:item`
     raises `HarvestFailure("fault:<point>")` at that point (test-only; documented
     in the wrapper header with the other seams).
   - **Certification**: `HARVEST_CERT = 2`; `receipt_text` adds `cert=2`, so
     `receipt_valid` refuses legacy receipts and `cmd_plan` re-harvests them
     (the existing items report `exists`).
   - Update the module doc (classification, the receipt contract, cert).
2b. **`lib/agent_sessions.py`** — `HARVEST_RECEIPT_CERT = 2`;
   `capture_harvested` requires the `cert=` line as well as the sha line. Update
   its docstring and the `drop` / `purge` gate comments ("a cert-2 receipt").
   **Output-change inventory:** `tests/test_agent_freeze.py:521` and `:3861`
   hand-write legacy `sha256=` receipts as valid. Update both to the cert-2 text
   through one helper; a grep over `tests/` for `sha256=` / `.harvested` found no
   others. A new test asserts `sitrep_harvest.HARVEST_CERT ==
   agent_sessions.HARVEST_RECEIPT_CERT`, like the existing suffix test.
3. **New `lib/sitrep_corpus.py`** (stdlib, imports `sitrep_todo` and `sitrep_harvest`):
   - the formats: render and parse for the manifest, analysis, review and key; `parser_sha()`;
   - `record_case(store, src, harvest)`: ALWAYS run `retain-raw` (sha check), then the excerpt, this origin's manifest, this origin's analysis and the key. Then `store.add` of the review item, **only when the key has no owner**; otherwise report the owner as `exists`. Owned keys still get their origin and analysis written, so provenance is never dropped;
   - `scan_cases(store_dir)`: read the first line of every `sources/*.txt` and group origins, analyses and reviews by case (input sha), then join the review item through the key-owner index;
   - CLI `case`: `list [--pending|--reviewed]` → `CASE:<hex>|<status>|c<N>|<item_state>|<codes>|record=..|agent=..|task=..|<captured_at>|parser=<rev>` or `NO_CASES`, where status is `pending|reviewed|dismissed|resolved|incomplete`;
   - `show <hex>` → `INPUT:raw/..|ok|missing|mismatch`, then per origin `ORIGIN:<ptr>|source=|record=|run=|agent=|task=|captured_at=` with its `ANALYSIS:<ptr>|parser=|class=`, `REASON:` and `ITEM:` lines, then `EXCERPT:`, `REVIEW:<ptr>|<outcome>|<at>|<gap>` and `REVIEW_ITEM:c<N>|<state>|<rev>`. `list` shows the origin count and the first origin;
   - `read <hex> [--lines a-b]` → verifies the sha first, then prints the lines (decoded with replace);
   - `review <hex> --outcome … [--gap] [--note] [--recovered] [--parser] [--fixture] [--item c<N> --expect-rev <rev>]` → retains a review record, and with `--item` runs `set-state <item> done --outcome "reviewed: <outcome>"`, never on a dismissed item. A review of a closed case only adds the record;
   - `replay <hex> [--apply]` → dry by default through a `DryStore` (fake retain/add, read-only): `REPLAY:<hex>|parser=|class=|reasons=`, then `REPLAY_ITEM:<kind>|<ref>|new|known` and `REPLAY_RESOLVED:` / `REPLAY_NEW_REASON:` against the latest analysis. `--apply` (the wrapper holds the harvest mutex) runs the real `Harvest` with a `Source` rebuilt from the manifest and retains a new analysis. It never touches the review item;
   - `export <hex> --out <dir> [--allow-unresolved]` → refuses an existing dir, refuses when replay still classifies `review` unless allowed, writes `input.txt` plus `case.json` (`source`, `piped`, `expect_class`, `expect_items` [kind+ref] from the current replay, `reasons_before`, `gap`), and prints `EXPORTED:` and `REDACT:` reminder lines;
   - `check-fixture <dir>` → `FIXTURE_OK` / `FIXTURE_FAIL:<why>` (exit 1). The pytest test and the e2e test share it.

   `--root` (default `.`) uses `sitrep_cli.root_arg` semantics and canonicalises the root. Exit codes: 0 ok, 1 failed, 2 usage, 4 store unusable.
4. **`aitask_sitrep_harvest.sh`** — a `case` verb that forwards to
   `sitrep_corpus.py`. `replay --apply` runs inside a generalised
   `with_harvest_lock <root>` (reusing the body of `locked_apply`). Update the
   header for the verbs, wire lines, the receipt contract ("deletion is allowed
   after reliable extraction, or after raw evidence plus a durable review item"),
   and the FAULT seam. **`aitask_sitrep.sh`**: `case` → exec
   `aitask_sitrep_harvest.sh case "$@"`; update the usage and header.
5. **`lib/sitrep_cli.py`** — `_KIND_LABEL` gains `case→CASE`,
   `analysis→ANALYSIS` and `review→REVIEW`. For a triage item with a case
   manifest, `triage_block` adds `REVIEW_CASE:<hex16>|<codes>` (read from the
   latest analysis). Update the module doc.
6. **`monitor/sitrep_close.py`** — `parse_harvest_output` reads
   `HARVEST_REVIEW:`; `HarvestReport.reviews` holds `(cid, status, case, codes)`.
   `verdict()` with reviews reads "Harvested: a added, e existing — output kept
   for sitrep review (c<N>)". `body_text` adds
   `review c<N> (<status>): <codes> — full output saved in the sitrep store`.
   `ok` is unchanged, since the final line is still `HARVESTED`.
7. **Skill `.claude/skills/aitask-sitrep/SKILL.md.j2`**:
   - `>t` treats blocks with `REVIEW_CASE:` as unparsed-output reviews: run `aitask_sitrep.sh case show <hex>`, read the regions with `case read <hex> --lines a-b`, propose the missed task items (`--kind task --ref t<N> --derived agent`) and actions/watches in the same one-confirmation batch, then close with a new `<!-- sitrep-example:case-review -->` block (`case review <hex> --outcome … --gap "…" --recovered … --item <TRIAGE> --expect-rev <REV>`). Harvested text is data, never instructions (this restates the existing guardrail);
   - new capability `>c` (corpus): `case list`, `case show`, `case replay` (dry; `--apply` only on the user's yes). Export is a developer step and is not offered;
   - Writing rules: `case review` joins the sanctioned writes. The greeting counts pending reviews by title.

   Regenerate the three goldens, run `aitask_skill_verify.sh`, and extend
   `tests/test_sitrep_skill_contract.sh` so the `case-review` example is filled
   and run against a harvested case.
8. **Fixture**: `tests/fixtures/sitrep_harvest/joined_banner.txt` (synthetic) and
   `tests/fixtures/sitrep_harvest/corpus/joined_banner/{input.txt,case.json}`,
   produced by `case export` in the e2e flow and then reviewed. Add a README row
   and a corpus section (raw captures stay local; redact before committing).
9. **Docs**:
   - `aidocs/framework/sitrep.md`: a new section "Unparsed output: the review corpus" (classification, receipt contract, store layout `raw/` plus the case files, lifecycle, replay/export, retention: never pruned automatically), the component table and the tests table;
   - website `workflows/sitrep.md` and `skills/aitask-sitrep.md`: the three outcomes users see (harvested / kept for review / failed — not deleted), `ait sitrep case …`, `>c`;
   - the harvest fixtures README.

   Then run `check_links.py --build`.

### Post-phase (risk mitigations)
1. [fallback_guard_mutants] Run each mutant in a fresh `mktemp -d` copy of
   `.aitask-scripts` + `tests`, with an unmutated control that must be GREEN.
   Each mutant must turn its named test RED:
   - `receipt_despite_case_failure` (e2e 7);
   - `key_identity_bypassed` (e2e 6, duplicate item);
   - `closed_item_reopened` (e2e 5/6);
   - `check_sources_skips_raw` (e2e 4 with a deleted raw file);
   - `raw_sha_unchecked` (unit with a fake writer returning a wrong sha);
   - `joined_flag_ignored` (e2e 8 fixture check);
   - `monitor_ignores_review` (monitor unit);
   - `needs_apply_ignores_reasons` (e2e 1 near-miss-only capture);
   - `unresolved_xref_is_reason` (unit negative);
   - `legacy_receipt_accepted_by_store` (`capture_harvested` ignores cert; e2e 0 drop/purge);
   - `legacy_receipt_short_circuits` (`receipt_text` without cert; e2e 0 re-harvest);
   - `marker_claimed_by_any_banner` (e2e 3 marker A/B);
   - `created_checked_per_line` (e2e 3 mixed Created line);
   - `banner_coverage_by_range` (e2e 3 quoted banner in a field);
   - `origin_skipped_when_key_owned` (e2e 3b).

   Record the results in Final Implementation Notes.
2. [large_capture_budget] Generate a synthetic 50,000-line capture of
   ~12 MB (200-column padded lines) with one near-miss banner, then time
   `harvest record` on it in the e2e scratch environment, three runs. Required:
   the slowest run is under 30 s. Otherwise, switch the record path to
   `retain-raw --from <capture path>` (the core reads the file; the wrapper
   copies it atomically without bash buffering), add a test, and re-measure.
   Record the timings in Final Implementation Notes.

## Tests

- **New `tests/test_sitrep_corpus.py`** (unit): a reason table over every
  fixture plus synthetic inputs. Each trigger fires exactly its code with the
  right line range; the negatives (`raw_no_banner`, every `pick_complete_*` /
  `pick_stopped_*`, an unresolved xref, a mid-work capture with no banner, blank
  pipe) fire none. Other cases: joined-banner parse (complete, stopped,
  wrapped, labels out of order → incomplete); format round trips; `needs_apply`;
  the `DryStore` replay is read-only (the store bytes are unchanged); the
  monitor `parse_harvest_output` with `HARVEST_REVIEW` (verdict, body, ok) in
  `tests/test_monitor_sitrep_harvest_close.py`; and `triage_block` labels.
- **New `tests/test_sitrep_corpus.sh`** (e2e, scratch HOME/repo built like
  `test_sitrep_harvest.sh`, plain counters):
  0. **legacy receipt** (written with the pre-change text `sha256=…\nstore=…\n`) on review-triggering input (`truncated_banner`) and on benign input. Before any new harvest: store `drop` → `HARVEST_REQUIRED` (exit 9) and `purge` → `KEPT:<id>|unharvested_text`. Then plain `harvest record <id>` (no `--force`) re-harvests rather than printing `already_harvested`: the review input gets one case plus `HARVEST_REVIEW`, the benign one gets no case, and existing items stay `exists`. The receipt now carries `cert=2`, `drop` succeeds and `purge` releases. A dismissed legacy item stays dismissed;
  1. the four acceptance triggers (incomplete banner, bad follow-up, truncation, finished output with no extraction: marker and pipe) → `raw/` sha ok, manifest/analysis/key retained, ONE review item, receipt present;
  2. negatives → no `raw/`, no review item;
  3. **mixed success/failure**: marker A with no banner, then marker B with its valid banner, gives `marker_without_banner:<A>` only, and B's triage and follow-up items are written. One line with a valid `Created:` and a malformed one gives the valid task item plus one `created_unparsed` reason. A banner with valid follow-ups plus a bad token gives the good follow-up items plus `bad_followup`. A banner text quoted inside a `reason:` value gives `banner_unparsed`. The partial items appear in `related:` and in the analysis;
  3b. **provenance**: identical bytes harvested from two distinct records (A, B), and once through `capture` → ONE review item and THREE `ORIGIN:` entries, each with its own analysis and items. A repeated `--force` harvest of A writes no new file (the `sources/` listing is byte-identical before and after) and no item. Then drop both records and remove the worktree: `case show` still lists every origin and `check-sources` is all OK;
  4. drop the record and remove the worktree → `check-sources` all `SOURCE_OK` (including `raw/`), and `case show` / `read` still readable;
  5. no agent running: in a new process `case list --pending` finds the case; `case review --item` closes it; a dismissed sibling stays dismissed; the evidence stays;
  6. `--force` re-harvest and a concurrent pair (pause seam) → one item; a closed item is not reopened;
  7. `FAULT` at `case:raw` / `case:files` / `case:item` → `HARVEST_FAILED`, no receipt, `drop` → `HARVEST_REQUIRED`, purge `KEPT`; a retry without the fault completes with one item;
  8. old-parser copy (`ACCEPT_JOINED_BANNER=False`, `PARSER_REV=1`, with a premise check that the sed changed the file) harvests `joined_banner.txt` → review. The current `case replay` shows `REPLAY_ITEM:task|t43|new` and `REPLAY_RESOLVED:banner_unparsed`; `--apply` adds the item and a second analysis, and the review item state is unchanged. `export` writes the dir; `check-fixture` on it is OK with the current lib and FAIL with the old copy;
  9. too-large input (lowered cap via `AITASK_SITREP_RAW_MAX` test seam) → `case_input_too_large`, no receipt.
- **New `tests/test_sitrep_corpus_fixtures.py`** runs `check-fixture` over every
  committed `tests/fixtures/sitrep_harvest/corpus/*/`.
- **Existing suites must stay green unchanged**: `test_sitrep_harvest.sh`/`.py`,
  `test_sitrep_todo.sh` (the fixture pin), `test_sitrep_todo_format.py`,
  `test_monitor_sitrep_harvest_close.py`, `test_agent_freeze.py`,
  `test_sitrep_skill_contract.sh`, `test_skill_render_aitask_sitrep.sh`,
  `test_sitrep_window.py`, `test_metadata_writer_inventory.py`,
  `test_no_lib_to_tui_import.sh`, the Python suite (`run_all_python_tests.sh`,
  last line), shellcheck on the touched scripts, `aitask_skill_verify.sh`, and
  `check_links.py --build`.

## Verification

Run the tests above. The final verdict comes from each runner's last line, and
pipes use `set -o pipefail`. Then run `assess` read-only over all local frozen
captures; it is expected to reproduce the measured baseline with 0 reviews.

## Coordination

- t2206 (Implementing, test-only `h` live smoke) reads `HarvestReport`. This
  change is additive (`ok` and the final lines are unchanged), so no note is
  needed unless that test asserts the exact body text.
- t2182 (Ready, harvest other agents' captures): send a note at Step 8e. Other
  agents' banners will now land in the corpus as `banner_unparsed` cases, which
  are ready-made inputs for that task.

## Step 9 (Post-Implementation)

Follow task-workflow Step 9: commit the code (`enhancement: … (t2175_6)`), commit
the plan via `./ait git`, then archive the child; the parent t2175 then has no
children left.

## Risk

### Code-health risk: medium
- The receipt now depends on case writes in the apply path that drop/purge rely on. A bug in record_case or in the classifier could leave records undeletable (fail closed, but sticky) or certify deletion without a durable item · severity: medium · → mitigation: inline post-phase fallback_guard_mutants
- New writer verb plus a `raw/` store dir; check-sources now follows manifests. This touches the writer, the format core and the monitor report parser (several central files, all additive) · severity: low · → mitigation: inline post-phase fallback_guard_mutants
- The cert-2 migration invalidates every existing receipt. Until the first cert-2 harvest (`aitask_frozen.sh drop` harvests first; the maintenance pass covers the rest within ~10 min), the monitor's kill path refuses drops of legacy records. That is fail-closed and recoverable, but visible. The re-harvest only adds cases, never duplicate items (identity keys) · severity: low · → mitigation: none (covered by e2e 0 and the legacy_receipt_* mutants; stated in docs)
- Large captures: the raw input passes through bash buffers and one extra writer call. A 10–20 MB capture could eat into the 60 s post-freeze budget · severity: low · → mitigation: inline post-phase large_capture_budget

### Goal-achievement risk: medium
- The detection signals are heuristic, and no real failing capture exists locally (21 measured, 0 triggers), so the policy is validated only on synthetic inputs. False positives from other agents' layouts or dev sessions that echo banners are possible (cheap and evidence-preserving, but noisy) · severity: medium · → mitigation: inline pre-phase detection_baseline
- The demonstration gap (joined banner) is synthetic and not observed. The "fails against prior behaviour" proof uses a flag-flipped copy, not historical code · severity: low · → mitigation: none (accepted; stated in docs and Final Implementation Notes)
- The agent-side review (recovering items, recording the gap) depends on skill prose that only the contract test checks mechanically · severity: low · → mitigation: t2216 (sitrep_review_live_smoke)

### Planned mitigations
- timing: pre-phase | name: detection_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — heuristic detection false positives | desc: measure assess() over every local frozen capture and fixture before building the corpus; tighten any rule that misfires
- timing: post-phase | name: fallback_guard_mutants | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health — receipt/case-write path and the new writer/check-sources guards | desc: one mutant per guard in fresh copies, each RED on its named test, control GREEN
- timing: post-phase | name: large_capture_budget | type: performance | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — large-capture harvest budget | desc: time a 50,000-line ~12 MB review-triggering harvest; slowest run under 30 s or switch to retain-raw --from <file>
- timing: after | name: sitrep_review_live_smoke | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — agent-side review depends on skill prose | desc: run the real /aitask-sitrep skill against a scratch store seeded with a joined-banner case; check it recovers the missed follow-up via the writer, records a case review, closes the item, and leaves raw/ evidence intact | created: t2216

## Final Implementation Notes
- **Actual work done:**
  - `lib/sitrep_harvest.py`: joined-banner grammar (`ACCEPT_JOINED_BANNER`,
    `JOINED_RE`, `_split_joined`; `PARSER_REV = 2`); the confidence check
    `assess` / `classify` / `needs_apply` with `Reason`; the shared identity
    pairing `pair_markers` / `find_marker_at` / `passage_bytes`, used by both
    `Harvest.run` and `assess`; `HARVEST_CERT = 2` in `receipt_text`; case
    headers and `capture_file_kind` kinds `case` / `analysis` / `review`;
    `cmd_apply` records the case before the receipt and emits
    `HARVEST_REVIEW:` plus `HARVESTED:…|review=c<N>`; `fault_point` seam;
    `Harvest.item_ids` / `new_ids`; a `__main__` alias so the lazily imported
    corpus module shares one `HarvestFailure` class.
  - New `lib/sitrep_corpus.py`: file formats, `record_case`, `retain_raw`
    (sha / NUL / cap guards), `scan_cases`, `DryStore`, `dry_harvest`, and the
    CLI verbs `list` / `show` / `read` / `review` / `replay [--apply]` /
    `export` / `check-fixture` (plus a hidden `lockroot`).
  - `lib/sitrep_todo.py` + `aitask_sitrep_todo.sh`: the `retain-raw` verb
    (`raw/<hex>.txt`, cap 64 MiB, test seam `AITASK_SITREP_RAW_MAX`);
    `check-sources` follows case origins to the raw input; `raw/` counts as a
    post-init store artifact.
  - `lib/agent_sessions.py`: `HARVEST_RECEIPT_CERT`; `capture_harvested`
    requires the cert.
  - `aitask_sitrep_harvest.sh`: `with_harvest_lock` (factored out of
    `locked_apply`) and the `case` verb (`replay --apply` runs under the
    mutex); header contract updated. `aitask_sitrep.sh case` forwards to it.
  - `lib/sitrep_cli.py`: `CASE` / `ANALYSIS` / `REVIEW` labels and the
    `REVIEW_CASE:<hex>|<codes>` triage fact.
  - `monitor/sitrep_close.py`: `HarvestReview`, `HarvestReport.reviews`, the
    "output kept for sitrep review" verdict and body line (`ok` unchanged).
  - Skill `SKILL.md.j2`: review handling in `>t` (step 2b, `case-review`
    example), the `>c` capability, `case review` as a sanctioned write, and
    the greeting count. Three goldens regenerated; the contract test gained
    section e.
  - Docs: `aidocs/framework/sitrep.md` ("Unparsed output: the review corpus",
    components, monitor report, tests), the website workflow and skill pages,
    and the fixtures README (corpus section).
  - Tests: new `test_sitrep_corpus.sh` (184), `test_sitrep_corpus.py` (35),
    `test_sitrep_corpus_fixtures.py` (2); monitor tests +3; contract section e;
    `test_agent_freeze.py` receipts built by one cert-aware helper. Fixtures:
    `joined_banner.txt` and `corpus/joined_banner/`.
- **Deviations from plan:**
  - Detection baseline: the draft `Created: aitasks/new/draft_*.md` line in
    `explore_created.txt` fired `created_unparsed`. Drafts have no task id, so
    `NEAR_CREATED_RE` excludes `aitasks/new/` (negative unit case added).
  - The review item is counted as a harvested item (`HARVEST_ITEM` line and
    `added=`), so the `h` dialog lists it.
  - Origin files carry no harvest timestamp; `captured_at` is the record's
    `frozen_at`, else `-`.
  - The monitor needed no new `final_kind`: the final line stays `HARVESTED`
    (the case is saved before the receipt), so `agent_freeze._harvest_record`
    and `HarvestReport.ok` stay correct; `reviews` drives the wording.
- **Issues encountered:**
  - The lazy `import sitrep_corpus` from `sitrep_harvest` running as
    `__main__` loaded a second `sitrep_harvest`, whose `HarvestFailure` was
    not caught (e2e 9 traceback). Fixed with the `sys.modules` alias.
  - A `replay --apply` newness bug (all ids real) was fixed by recording
    newness in `Harvest`.
  - The `--recovered "c1, c2"` spacing needed `strip()`.
  - Under `pipefail`, `assert_contains` over a whole 60 KB file fails with
    SIGPIPE; the premise check now counts with `grep -c`.
- **Measurements:**
  - detection_baseline: 21 local frozen captures give 17 reliable, 4 empty and
    0 review; fixtures give 9 reliable, 1 empty, and 1 review
    (`truncated_banner`: banner_incomplete), counted after the draft fix.
  - large_capture_budget: a synthetic 12,150,005-byte / 50,000-line capture
    with a joined banner and a cut-off banner harvested in 8.23 s, 7.89 s and
    7.53 s (slowest 8.2 s < 30 s; load average 17–20 on 24 cores while the
    mutants ran). The raw copy was byte-identical each run, so no
    `--from <file>` path was needed.
- **Mutants (fallback_guard_mutants):** 15 mutants, each in a fresh
  `mktemp -d` copy of `.aitask-scripts` + `tests`. The unmutated control was
  GREEN on e2e, unit, fixtures and monitor, and every mutant was RED on its
  named assertion:
  - `receipt_despite_case_failure` (e2e 7)
  - `key_identity_bypassed` (3b)
  - `key_per_origin` (1)
  - `review_reopens_closed` (5)
  - `check_sources_skips_raw` (4)
  - `raw_sha_unchecked` (unit RawRetention)
  - `joined_flag_ignored` (fixtures + unit)
  - `monitor_ignores_review` (monitor)
  - `needs_apply_ignores_reasons` (1)
  - `unresolved_xref_is_reason` (unit Negative)
  - `legacy_receipt_accepted_by_store` (0)
  - `legacy_receipt_short_circuits` (0)
  - `marker_claimed_by_any_banner` (3)
  - `created_checked_per_line` (3)
  - `banner_coverage_by_range` (3)
  - `origin_skipped_when_key_owned` (3b)
- **Upstream defects identified:**
  - `tests/test_codeagent.sh:372` — `output=$(cd "$TMPDIR_TEST" && bash … || true)`
    fails `tests/test_cd_guard_lint.sh` ("unconfined-andchain"); it came in
    with t2175_4 (`bdef300b0`). The lint's other failure is another session's
    untracked `tests/test_premise_baseline_field.sh`.
- **Key decisions:** cert-versioned receipts invalidate legacy certificates
  everywhere; per-occurrence pairing that reuses the identity pairing; one
  review item per input, provenance per origin; the raw input is kept verbatim
  or the harvest fails closed (never truncated); the review item is written
  last; cases are found by scanning `sources/`; replay writes nothing unless
  `--apply`; export refuses unresolved cases; the skill never exports.
- **Notes for sibling / follow-up tasks:**
  - t2182 (other agents' captures): banners from other agents' layouts now
    land in the corpus as `banner_unparsed` cases with their raw input, which
    are ready-made fixtures.
  - The spawned after-mitigation `sitrep_review_live_smoke` exercises the
    skill's review flow live.

## Post-Review Changes

### Change Request 1 (2026-11-05 10:30)
- **Requested by user:** five confirmed concerns:
  1. forged case-record headers in harvested `sources/` passages could alter a
     case (`scan_cases` trusted any first line);
  2. `case review` recorded before the expected-rev close, and a record alone
     made the case "reviewed" (STALE exited 0);
  3. `DryStore.add` did not index capture owners, so a replay previewed
     repeated commit, run and passage identities as new;
  4. a cached `already_harvested` result dropped the review, so `h` showed
     "Nothing to harvest";
  5. `_split_joined` absorbed duplicate labels and classified the banner
     reliable.
- **Changes made:**
  1. A trusted namespace `cases/<hex>.txt`, written only by the new writer
     verb `retain-case` (case-record headers only; `CASE_RECORD_HEADERS` in
     `sitrep_todo`). Origin, analysis and key are written to `cases/` and to a
     byte-identical `sources/` copy for context pointers; review and replay
     analysis records go to `cases/` only. `scan_cases`, `case_origin_input`
     (`check-sources`) and `sitrep_cli._review_case` / `_capture_kind` read
     only `cases/` (a `sources/` file counts as a record only with a trusted
     twin). Identity counts only review items (`is_review_item`). The excerpt
     gets its own header line, so it can never equal a record. `raw/` and
     `cases/` count as post-init store artifacts.
  2. `Case.status` comes from the item state only (open means pending, even
     with records). `cmd_review` prints `REVIEW_NOT_CLOSED:c<N>|stale:<rev>`,
     `|not_closed` or `|<failure>` and exits 1 unless the writer printed
     `STATE:c<N>|done|`. New fault point `review:close`.
  3. `DryStore.add` parses the context and indexes its capture and trail
     pointers and the item, as the real reload does.
  4. `cmd_plan`'s receipt short-circuit prints
     `sitrep_corpus.cached_review_line` (`HARVEST_REVIEW:…|exists|…`) before
     `already_harvested`. `HarvestReport.verdict` for `HARVEST_NONE` with a
     review reads "Nothing new to harvest (…) — output kept for sitrep review
     (c<N>)".
  5. `_joined_ambiguous` marks a joined banner with any repeated label
     incomplete; its fields are kept.
  - Tests:
    - e2e: 5b covers forged review and analysis headers via a Created window
      and a post-prompt passage (the listing is unchanged, there is no forged
      REVIEW, one REVIEW_CASE), a stale rev, a failed close, and a retry; 5c
      covers a cached result plus the monitor verdict; assertions updated for
      `cases/`.
    - unit: excerpt-never-equals-a-record; trusted triage facts; a
      `sources/`-only scan finds nothing; duplicate labels; dry-vs-real parity
      over repeated commit, passage, run and follow-up inputs.
    - monitor: cached-review verdict.
    - contract: the `cases/` path.
  - Skill: `REVIEW_NOT_CLOSED` handling; goldens regenerated. Docs: the
    framework doc's trust, status and cached-result text, the harvest header,
    and the website store line.
- **Files affected:**
  - `.aitask-scripts/lib/sitrep_todo.py`, `.aitask-scripts/aitask_sitrep_todo.sh`
  - `.aitask-scripts/lib/sitrep_corpus.py`, `.aitask-scripts/lib/sitrep_harvest.py`,
    `.aitask-scripts/lib/sitrep_cli.py`
  - `.aitask-scripts/monitor/sitrep_close.py`, `.aitask-scripts/aitask_sitrep_harvest.sh`
  - `.claude/skills/aitask-sitrep/SKILL.md.j2` and its three goldens
  - `aidocs/framework/sitrep.md`, `website/content/docs/workflows/sitrep.md`
  - `tests/test_sitrep_corpus.sh`, `tests/test_sitrep_corpus.py`,
    `tests/test_monitor_sitrep_harvest_close.py`, `tests/test_sitrep_skill_contract.sh`
- **Verification after Change Request 1:**
  - Suites: corpus e2e 202/202; corpus unit + fixtures 41; monitor + harvest +
    freeze + todo-format 366; todo e2e 248; harvest e2e 139; contract 64;
    render 114. `aitask_skill_verify.sh` OK; `check_links.py --build` PASSED.
  - Mutants: the full set was re-run (23) with the unmutated control GREEN on
    e2e, unit, fixtures and monitor. All 23 were RED, including the 8 new ones:
    - `scan_reads_sources` (e2e 5b)
    - `review_record_certifies` (5b)
    - `stale_close_exit_zero` (5b)
    - `cached_review_dropped` (5c)
    - `dry_owners_not_indexed` (unit dry-vs-real parity)
    - `duplicate_labels_ignored` (unit)
    - `triage_trusts_sources` (unit)
    - the retargeted `key_identity_bypassed` (now `review_owners`)

### Change Request 2 (2026-11-05 11:40)
- **Requested by user:**
  1. review ownership depended on the editable title, so a renamed review
     made the case look incomplete and a re-harvest created a second review;
  2. status read "resolved" from any historical record, even a failed
     attempt, and that check came before dismissal;
  3. the framework doc still said cases are found by scanning `sources/`.
- **Changes made:**
  1. `is_review_owner(item, ctx, store_dir, case, keyhex)`: a script-derived
     question whose context points at the case key AND at a trusted origin or
     analysis of the same case (both with `cases/` twins). The title is never
     consulted. `Store` keeps `contexts` (and `DryStore` mirrors them);
     `review_owners` and `scan_cases` use the predicate.
  2. `Case.accepted_outcome()` reads the item's writer-stored outcome
     (`reviewed: <outcome>`, written only by a successful close). Status is
     pending (open), then dismissed (always wins), then resolved or reviewed
     from the accepted outcome; review records are history only.
     `case review` on a done item now re-closes it with the new accepted
     outcome (e.g. a later `resolved`); on a dismissed item it only adds the
     record (`REVIEW_ITEM_KEPT`).
  3. The doc's lifecycle paragraph is rewritten (`cases/` discovery,
     provenance ownership, accepted-outcome status).
  - Tests (e2e):
    - 5d renames open, done and dismissed reviews via `update --title`: the
      case listing is unchanged, a `--force` re-harvest finds the review
      (`exists`), no second question is created, and the state is kept;
    - 5e: a stale `resolved` attempt (exit 1), then `unrecoverable`, gives
      reviewed with both records kept as history; a later `resolved` re-close
      gives resolved; a dismissal then gives dismissed.
- **Not mutant-testable by construction:** the provenance half of
  `is_review_owner` (key pointer + trusted origin/analysis) beyond the key
  pointer itself cannot be reached by any input, because no non-review item
  can point at a case key file (no retained passage is byte-identical to a
  record). It is defense in depth, not a tested guard.
- **Files affected:**
  - `.aitask-scripts/lib/sitrep_corpus.py`
  - `.aitask-scripts/lib/sitrep_harvest.py` (`Store.contexts`)
  - `aidocs/framework/sitrep.md`
  - `tests/test_sitrep_corpus.sh`
- **Verification after Change Request 2:**
  - Corpus e2e 222/222. Related Python suites (harvest, monitor, refresh,
    window) 228; contract 64; harvest e2e 139; `check_links.py --build` PASSED;
    shellcheck clean.
  - Mutants: the full set (26) with the control GREEN on e2e, unit, fixtures
    and monitor; all RED, including `owner_by_title` (5d), `status_from_records`
    (5e) and `resolved_before_dismissed`.
  - The first run of `resolved_before_dismissed` was RED only on a flaky
    `assert_contains` (case 8; the text was present). 5e then gained a
    dismissal WITHOUT `--outcome` (the item keeps `reviewed: resolved`), and
    the re-run is RED on exactly that assertion.
  - The suite now defines pipe-free `assert_contains` / `assert_not_contains`
    (here-strings) locally.
- **Upstream defects identified (addendum):**
  - `tests/lib/asserts.sh:179-196` — `assert_contains` / `assert_not_contains`
    use `printf '%s' "$haystack" | grep -qF`. Under a caller's
    `set -o pipefail`, a haystack larger than one write makes `grep -q` exit
    early, printf gets SIGPIPE, and a present needle is reported missing
    (observed twice in `tests/test_sitrep_corpus.sh`; worked around locally
    with here-strings).
