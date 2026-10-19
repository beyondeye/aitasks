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
