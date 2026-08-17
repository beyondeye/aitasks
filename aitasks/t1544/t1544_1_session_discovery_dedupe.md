---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tui, project_groups, reporting]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1544
created_at: 2026-08-17 22:04
updated_at: 2026-08-17 22:55
---

## Context

First child of t1544 (backlog level + net flow by category in `ait stats`).
Parent plan: `aiplans/archived/p1544_stats_backlog_and_net_flow_by_category.md`
(or `aiplans/p1544_*.md` while the parent is active).

This child fixes a **pre-existing bug** that t1544 did not create but cannot
land without. t1544's acceptance criteria include *"a multi-project run does not
drop or double-count [the new series]"* — and that is untestable today, because
the session-discovery layer can hand the stats TUI the same repository twice.

It is sequenced first because it is independently testable, independently
valuable (it already corrupts every existing stats counter), and because
t1544_3's merge test is meaningless until it lands.

## The bug

`.aitask-scripts/lib/agent_launch_utils.py::_assemble_aitasks_sessions` builds
the session list with **no dedupe among live entries**, and its
registered-vs-live dedupe compares `project_name`, not the path:

```python
    if include_registered:
        live_names = {s.project_name for s in found}
        for name, root, status, group in _read_registry_index():
            if name in live_names:
                continue
            found.append(AitasksSession(...))
```

Meanwhile `AitasksSession.key` is `realpath(project_root)`, and the stats TUI
caches on that key:

```python
    # stats/stats_app.py
    def _stats_for(self, sess):
        cached = self._session_cache.get(sess.key)
        if cached is None:
            cached = collect_stats(date.today(), 1, project_root=sess.project_root)
            self._session_cache[sess.key] = cached
        return cached
```

So two session records with the same `key` cause `_load_data`'s
`merge_stats_data([...])` to receive the **same `StatsData` object twice**, and
every counter doubles.

Reproduced read-only during t1544 planning:

```
_assemble_aitasks_sessions([('aitasks', R), ('aitasks2', R)], include_registered=False)
  -> 2 entries, distinct keys: 1
```

**Two reachable triggers:**

1. **Two live tmux sessions rooted at one repo.** Trivially reachable; nothing
   dedupes them.
2. **Registry name != directory basename.** Live entries set
   `project_name = project_root.name`, but the registry name comes from
   `project.name` in `project_config.yaml`, falling back to the basename
   (`.aitask-scripts/aitask_projects.sh`). Because the registered-vs-live skip
   compares `name`, a repo whose config declares `project: name: acme-main` at
   a directory named `acme` yields a live entry (`acme`) **and** a registered
   entry (`acme-main`) with the same `key`. Every registered repo happens to
   have `name == basename` today — that is luck, not a guarantee.

Related: `disambiguate_labels` in the same module cannot separate the duplicate
rows either — primary, secondary and fallback are all identical — so its
"guaranteed-unique" contract is violated too. Note this in the plan; fixing the
duplicate at the source is what resolves it.

## Blast radius (read this before editing)

`_assemble_aitasks_sessions` is the shared session-discovery helper behind
**every** aitasks TUI — board, monitor, minimonitor, the `j` TUI switcher and
stats — not just stats. A dedupe that is even slightly wrong silently removes a
session from all of them. The parent plan rates this the task family's only
high-severity code-health risk, and attaches the two inline phases below.

### Pre-phase (risk mitigations)

1. `[characterize_session_discovery]` **Before** touching
   `_assemble_aitasks_sessions`, add a characterization test pinning its
   **current** output for the non-duplicate cases:
   - a single live root;
   - a live entry plus a registered entry with **distinct** names;
   - a `STALE` registry row (dropped by `discover_stats_sessions`, kept by the
     assembler — pin what each layer actually does);
   - the `found.sort(key=lambda s: s.session)` ordering.

   Assert on the returned `AitasksSession` list — count, `project_name`,
   `project_root`, `is_live`, `is_stale`, and order. **This test must pass
   unchanged after the dedupe lands**; only a *new* duplicate-input case may be
   added to the file. Without it, "the dedupe changed only the duplicate case"
   is an assertion nobody can check.

### Post-phase (risk mitigations)

1. `[tui_discovery_smoke_after_dedupe]` After the dedupe lands, launch
   `ait board`, `ait monitor`, `ait minimonitor` and the `j` TUI switcher, and
   confirm each still lists **every session it listed before** — same count,
   same names, same order. Record the before/after session lists in this plan's
   Final Implementation Notes. Add the same four checks as items on the
   manual-verification sibling's checklist. The unit test cannot reach the live
   discovery path in four other TUIs; only this can.

## Key files to modify

- `.aitask-scripts/lib/agent_launch_utils.py` — `_assemble_aitasks_sessions`:
  make the registered-vs-live skip **path-based** (compare
  `os.path.realpath(root)` against the live roots) instead of name-based.
- `.aitask-scripts/stats/stats_app.py` — `discover_stats_sessions()`: dedupe the
  returned list on `AitasksSession.key`, **preferring the `is_live=True` entry**
  when both exist. Add a comment naming this task.
- `tests/` — the characterization test (pre-phase) plus the new duplicate-input
  cases.

Decide in the plan whether the live-vs-live dedupe belongs in the assembler (so
every TUI benefits) or only in `discover_stats_sessions` (so only stats changes
behaviour). **Prefer the assembler** — the doubling is not stats-specific — but
state the choice and its blast radius explicitly, and let the characterization
test prove the non-duplicate cases are untouched either way.

## Reference files for patterns

- `.aitask-scripts/lib/agent_launch_utils.py` — `AitasksSession` (the `key`
  property is `realpath(project_root)`), `_build_registry_group_lookup`
  (already does path-keyed lookup via `os.path.realpath` — the same idiom this
  fix needs), `disambiguate_labels`.
- `.aitask-scripts/stats/stats_app.py` — `discover_stats_sessions`,
  `_load_data`, `_stats_for`.
- `.aitask-scripts/aitask_projects.sh` — how a registry row's `name` is derived
  from `project_config.yaml`, falling back to the basename.
- Existing session-discovery tests: `tests/test_stats_include_registered.py`,
  and any `tests/test_*session*` / `tests/test_*discovery*` module — follow the
  closest existing fixture style rather than inventing one.

## Implementation plan

1. Run the **pre-phase** characterization test first; commit it or keep it in
   the same change, but write it before the edit.
2. Make the registered-vs-live skip path-based in `_assemble_aitasks_sessions`.
3. Dedupe live-vs-live on realpath, preferring the live entry.
4. Add the duplicate-input tests: two live roots at one path -> 1 entry; a
   registry row whose name differs from the basename but whose path matches a
   live root -> 1 entry, and it is the live one.
5. Confirm the characterization test still passes **unchanged**.
6. Run the **post-phase** four-TUI smoke and record the before/after lists.

## Verification steps

```bash
bash tests/run_all_python_tests.sh --test-dir tests
ait board          # session list unchanged
ait monitor        # session list unchanged
ait minimonitor    # session list unchanged
# press j in any TUI -> switcher session list unchanged
```

The characterization test passing **unchanged** is the primary signal; the new
duplicate-input tests are the secondary one.

## Notes for sibling tasks

Record in the Final Implementation Notes whether the dedupe landed in the
assembler or only in `discover_stats_sessions` — t1544_3's
"multi-project run does not double-count" test depends on knowing which layer
guarantees uniqueness.
