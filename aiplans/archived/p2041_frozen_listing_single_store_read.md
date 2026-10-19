---
Task: t2041_frozen_listing_single_store_read.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2041 — One store read per frozen listing pass

## Context

`agent_reopen._frozen_records()` (`.aitask-scripts/lib/agent_reopen.py:244`) runs
`store list --state frozen` and then `frozen_ops.store_show(<id>)` for every
record. Each `store_show` spawns `aitask_agent_sessions.sh show` (bash + Python),
which reloads the whole global JSON store. Since t2039, `ait ide` runs this
across all projects for `gone --all-roots` and again for `companions --all-roots`,
so 100 frozen records cost about 202 store subprocesses before attach. Goal: one
store read per `gone` / `companions` / `reopen --root` listing pass. The
contracts stay the same: an unreadable store is still `*_ERROR:*|store unreadable`,
the `frozen_ops.store` swap seam still covers the new read, and `reopen_one`
keeps its fresh per-record re-read under the lease.

## Approach

Add a batch read to the store wrapper, `list --full`. It is the same verb, uses
the same filters and the same validated `load()`, and prints one
`RECORD:<json>` line per record. Wrap it as `frozen_ops.store_records(...)`,
which calls `store(...)` by module-global lookup, so the existing test swap
redirects it. `_frozen_records` then builds the full records from that single
read. This also keeps `agent_frozen_ops` from importing `agent_sessions`, which
its docstring forbids. The data still comes from `agent_sessions.load()`, so it
gets the same parsing and validation that `list` / `show` use.

Out of scope (the optional item, deferred per minimal-scope rule): sharing one
classification between `ait ide`'s offer and its top-up.

## Steps

1. **`.aitask-scripts/lib/agent_sessions.py` — `main()`, `list` branch (~l.2358):**
   when `"--full" in rest`, print the matching records as
   `"RECORD:" + json.dumps(vars(rec), sort_keys=True)` instead of the `SESSION:` line. Keep the
   same filter and the same sort. `json.dumps` escapes newlines, so a record is
   always exactly one line, and a root that contains `\n` survives intact.
   (`show`'s `key:value` protocol truncates such a root.) `import json` if not
   already imported.

2. **`.aitask-scripts/aitask_agent_sessions.sh`:** `cmd_list` already forwards
   `"$@"`, so only the doc changes. Update the usage/header lines to
   `list [--state <s>] [--root <r>] [--full]` with a one-line note that
   `--full` prints one `RECORD:<json>` per record (a batch `show`, used by the
   reopen listing, t2041).

3. **`.aitask-scripts/lib/agent_frozen_ops.py`:** add next to `store_show`:
   ```python
   def store_records(*filters: str) -> list[dict[str, str]] | None:
       """``list <filters> --full`` as full records (``store_show``'s shape, one
       read for all); None when the store could not be read or the batch did
       not parse. A batch that cannot be parsed is never a partial listing."""
       rc, out = store("list", *filters, "--full")
       if rc != 0:
           return None
       records = []
       for line in out.splitlines():
           if not line.startswith("RECORD:"):
               continue            # folded stderr noise, never a record
           try:
               raw = json.loads(line[len("RECORD:"):])
           except ValueError:
               return None
           if not isinstance(raw, dict):
               return None
           records.append({str(k): str(v) for k, v in raw.items()})
       return records
   ```
   (`import json`.) Mention `store_records` alongside `store_show` in the
   module's seam-rule docstring paragraph.

4. **`.aitask-scripts/lib/agent_reopen.py` — `_frozen_records`:** replace the
   list-then-show loop:
   ```python
   records = frozen_ops.store_records("--state", "frozen", *scope)
   if records is None:
       return None
   return [r for r in records
           if agent_sessions.valid_id(r.get("id"))
           and r.get("state") == agent_sessions.STATE_FROZEN]
   ```
   `reopen_one` is unchanged: its pre-lease and under-lease `store_show` reads
   stay per-record. Update the one docstring/comment that mentions the
   per-record listing, if there is one.

5. **Tests:**
   - `tests/test_agent_reopen.py`: teach the fake `Store` the `--full` form.
     It returns `RECORD:` + `json.dumps(r)` rows under the same filters and
     `list_rc`, and adds a `list_garbage` knob that emits a non-JSON `RECORD:`
     line. Update the two call-shape asserts (l.354, l.809) to include
     `"--full"`. New tests:
     - `gone_all_roots()` and `companions(None)` over N=5 records, with every
       record tracked in the companions case: exactly one `list` call and zero
       `show` calls each.
     - `reopen_all(ROOT)` over N records: one `list`, and every `show` happens
       inside `reopen_one`. The calls before the first `lease-take` are
       `list` followed by a single `show`, which pins that only the listing pass
       was batched and the per-record reads remain.
     - Unreadable store (`list_rc`) and an unparseable batch (`list_garbage`)
       both yield `GONE_ERROR:*|store unreadable` (CLI `gone --all-roots` and
       `--root`), `COMPANION_ERROR:*|store unreadable`, and
       `REOPEN_FAILED:*|store unreadable`. None of them yields an empty listing.
     - A root containing a newline now reaches `GONE_ERROR:<id>|root_unprintable`
       through the fake store without patching `_classified`.
   - `tests/test_agent_frozen_ops.py`: add `"store_records"` to
     `PROMISED_CALLABLES`. Add late-binding tests: the swapped store sees
     `("list", "--state", "frozen", "--full")`, noise lines are skipped, a
     non-zero rc gives None, and a bad JSON line gives None.
   - `tests/test_agent_sessions.py` (`CliPersistenceTests`): a CLI round trip.
     `list --full` prints one parseable `RECORD:` per record. Its values,
     stringified, equal `show`'s `key:value` fields (a parity check on a normal
     record), and the `--state` / `--root` filters apply.

## Verification

- `python3 tests/test_agent_reopen.py`, `python3 tests/test_agent_frozen_ops.py`,
  `python3 tests/test_agent_sessions.py`
- `bash tests/test_ide_frozen_offer.sh`, `bash tests/test_frozen_reopen_live.sh`,
  `bash tests/test_ide_frozen_all_projects_live.sh` (these use the real wrapper,
  so they cover `--full` end to end)
- `shellcheck .aitask-scripts/aitask_agent_sessions.sh`
- Measurement: a scratchpad fixture store with 100 frozen records across a few
  roots (`AITASKS_AGENT_SESSIONS_FILE`, isolated `TMUX_TMPDIR`). Time
  `./.aitask-scripts/aitask_frozen.sh gone --all-roots` **before** editing
  (taken first, on the unmodified tree, with no stash) and after. Record both
  numbers in Final Implementation Notes.
- Step 9 (Post-Implementation): commit code and the plan, then archive per the workflow.

## Risk

### Code-health risk: low
- `store_records` dicts carry raw values, while `store_show` strips them, so the
  listing's records could differ from a `show` read for a field with
  surrounding whitespace · severity: low · → mitigation: none needed (covered by
  the Step 5 `list --full` vs `show` parity test; raw values are the more
  correct ones)

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Implemented as planned.
  - `agent_sessions.py` `list` takes `--full` and prints one `RECORD:<json>` per record, with the same filters and sort.
  - The wrapper documents the flag; its `cmd_list` already forwards args, so no logic changed there.
  - `agent_frozen_ops.store_records(*filters)` parses the batch into `store_show`'s shape (str values). It returns None on a non-zero rc or on any unparseable / non-object `RECORD:` line, and skips noise lines.
  - `agent_reopen._frozen_records` builds the listing from that single read. `reopen_one` keeps both of its per-record `store_show` reads (pre-lease and under-lease).
- **Measurement:** 100 frozen records across 5 roots, fixture store via `AITASKS_AGENT_SESSIONS_FILE`, isolated `TMUX_TMPDIR` with no server.
  - Before: `aitask_frozen.sh gone --all-roots` 5.94s / 6.02s, `companions --all-roots` 5.91s / 6.00s.
  - After: 0.17s / 0.16s and 0.17s / 0.15s.
  - Output line counts are identical (106 / 2).
- **Tests:**
  - New `TestSingleStoreRead` in `tests/test_agent_reopen.py`:
    - `gone --all-roots`, `gone --root` and `companions --all-roots` make 1 `list` call and 0 `show` calls over N=5 records.
    - `reopen_all` makes 1 `list`; its call order starts list, show, lease-take, show, and it makes 2 shows per record.
    - An unreadable store and an unparseable batch are both `*|store unreadable` on every verb.
    - A root containing a newline now reaches `root_unprintable` through the store.
  - Red proof: with the old `_frozen_records` patched back in-process, 6 of the 7 new tests fail. The unreadable-store test passes on both, as intended, because it pins a preserved contract.
  - `tests/test_agent_frozen_ops.py` adds `store_records` to the promised surface, plus late-binding, refusal, bad-batch and empty-store tests.
  - `tests/test_agent_sessions.py` adds a CLI round trip: `list --full` matches `show` field for field, and the filters apply.
- **Deviations from plan:** None. The optional item (one classification shared by `ait ide`'s offer and its top-up) is deferred, as the plan stated.
- **Issues encountered:** A concurrent session (t2045, Implementing) holds uncommitted hunks in two files this task also edits: `agent_frozen_ops.py` (`retire_restore_marks`) and `tests/test_agent_frozen_ops.py` (`GuardedClearTests`). This task's commit must carry only its own hunks of those two files.
- **Key decisions:**
  - JSON per line rather than a `key:value` block, so stored values containing a newline or `|` cannot split a record.
  - An unparseable batch fails closed as "store unreadable", never as a partial listing.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/agent_sessions.py:2380` (`show` verb) with `.aitask-scripts/lib/agent_frozen_ops.py:289` (`parse_show`, the parser `store_show` uses) — `show`'s `key:value` line protocol does not round-trip stored values. Each value is stripped and cut at its first `str.splitlines` break, and a later `key:value` line inside another field overrides that key. Restore, reopen and drop all act on that mangled view. For example, a `root` with surrounding whitespace resolves to a different project, and a field holding `\nstate:live` changes the state those actions read. Pre-existing, found during the t2041 review rounds. t2041 only makes the listing agree with that view; it does not fix the protocol.

## Post-Review Changes

### Change Request 1 (2026-10-19 10:45)
- **Requested by user:** The batch listing kept whitespace in eligibility fields, while restore reads through `store_show`, which strips them. A frozen record with `codeagent_session_id: " "` and `task_id: " "` was listed `ok|ok`, yet restore refused it with `no_session` / `no_task_id`. Asked to normalize eligibility inputs consistently, keep path values verbatim, and cover whitespace-only identifiers.
- **Verified:** Reproduced against a real fixture store. The listing (in-process, tmux claims stubbed to none) printed `…|ok|ok`, while `aitask_frozen.sh restore` returned `RESTORE_FAILED:<id>|no_session` and `restore --repick` returned `|no_task_id`.
- **Changes made:**
  - `agent_reopen._frozen_records` passes each batch record through `_as_shown()`. That strips every value as `store_show` does, except `_VERBATIM_FIELDS` (`root`, `transcript_path`, `capture_ansi`, `capture_txt`), which stay as stored.
  - The listing therefore applies the eligibility restore applies, and classifies against the `pane_id` / `window` that `reopen_one` re-reads.
  - Placed in `agent_reopen.py` (owned by this task only), not in `agent_restore`'s blockers. `agent_restore.py` holds uncommitted t2045 hunks, so per the gate-before-edit rule this task does not edit it.
  - `store_records` stays a faithful verbatim reader.
- **Tests:** `test_whitespace_only_identifiers_list_the_eligibility_restore_applies` and `test_listing_normalizes_like_show_except_paths`. The first runs `gone --root` and `agent_restore.restore` (resume and repick) on the same record and checks they agree. Both tests failed before the fix and pass after.
- **Files affected:** `.aitask-scripts/lib/agent_reopen.py`, `tests/test_agent_reopen.py`

### Change Request 2 (2026-10-19 11:10)
- **Requested by user:** `_as_shown` only applied `.strip()`, but `store_show` also splits on line breaks. A record with `codeagent_session_id="\nsession-1"` and `task_id="\n2041"` was listed `ok|ok`, while restore and repick returned `no_session` / `no_task_id`. Asked to align eligibility for values containing line breaks, keep paths verbatim, and extend the coverage.
- **Verified:** Reproduced through the real wrapper. Wider than reported: `store_show` keeps only the text before the first `str.splitlines` break (`\r`, `\x0b`, `\x85`, ` `, … as well as `\n`), and a later `key:value` line in another field overrides that key. For example, `transcript_path="/t\ncodeagent_session_id:"` blanks the session id for restore.
- **Changes made:** Parity now holds by construction rather than by approximation.
  - `agent_frozen_ops.parse_show(out)` is factored out of `store_show` as the one `show` parser.
  - `_as_shown` renders a batch record as `show` prints it (`key:value` per field) and parses it with `parse_show`, then restores `_VERBATIM_FIELDS` to their stored values.
  - `list --full` emits fields in dataclass order (no `sort_keys`), which is `show`'s order, so overrides resolve the same way.
- **Tests:**
  - `test_the_offer_lists_the_eligibility_restore_applies` is subtested over spaces/tab, leading `\n`, `\r`/`\x0b`, ` `/`\x85`, and later-field override. Each case runs `gone --root` and both restore modes and checks they agree. Four of the five subtests failed before this change (the spaces case was fixed in CR1).
  - `test_listing_reads_like_show_except_paths` asserts the listing equals a `store_show` read outside the path fields.
  - `parse_show` is added to the promised surface.
  - The sessions CLI test asserts `--full` key order equals `show`'s.
  - A real-wrapper sweep over the same five cases plus an eligible control: ALL_AGREE.
- **Files affected:** `.aitask-scripts/lib/agent_frozen_ops.py`, `.aitask-scripts/lib/agent_sessions.py`, `.aitask-scripts/lib/agent_reopen.py`, `tests/test_agent_reopen.py`, `tests/test_agent_frozen_ops.py`, `tests/test_agent_sessions.py`
