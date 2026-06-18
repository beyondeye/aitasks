---
Task: t1025_1_project_group_data_model_and_cli.md
Parent Task: aitasks/t1025_design_project_group_grouping_and_tui_navigation.md
Sibling Tasks: aitasks/t1025/t1025_2_tui_navigation_switcher_and_stats.md, aitasks/t1025/t1025_3_settings_tui_project_group_editor.md, aitasks/t1025/t1025_4_project_group_docs_and_terminology.md, aitasks/t1025/t1025_5_manual_verification_project_group.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-18 12:45
---

# Plan: project-group data model, bootstrap, read/write API + `ait projects group` CLI (t1025_1)

## Context

First child of t1025. Introduces the `project-group` concept **at the data layer
only** (no TUI changes) so children 2 (TUI nav) and 3 (settings editor) build on a
stable model. `project-group` = the agreed umbrella term grouping connected repos.
The per-user registry `~/.config/aitasks/projects.yaml` is the operational source
of truth; each repo's `project_config.yaml` `project.project_group` is the
**bootstrap seed only** (used to fill the registry when first registering, never
re-consulted to override a registry decision). See parent plan `aiplans/p1025_*.md`.

This plan was **verified against the current codebase** and revised after a plan
review that surfaced six real defects (group-clear fallback, registry-group not
reaching discovery, field-dropping write paths, Python-writer gap, live/registry
name mismatch, and slug-policy ambiguity). The resolutions are folded in below.

## Core design decisions (resolve the review concerns)

- **D1 — Tri-state group resolution with an explicit "ungrouped" sentinel.**
  A repo's effective group resolves as: **registry value wins** → else (registry
  field truly absent) **bootstrap from repo config** → else **None (ungrouped)**.
  To make `group unset` actually clear a repo whose *config* declares a group, the
  registry stores a tri-state, encoded by a reserved sentinel token `-`
  (a single hyphen — rejected by the slug validator, so unambiguous vs real
  slugs):
  - registry field = `<slug>` → that group, authoritative.
  - registry field = `-` (sentinel) → **explicitly ungrouped; do NOT fall back to
    config.** This is what `group unset` writes.
  - registry field **absent/empty** → fall back to repo config, else None.
  `group sync` and add-bootstrap only fill when the field is absent/empty — they
  never overwrite a real value or the `-` sentinel.

- **D2 — Registry group must reach discovery.** `_read_registry_index()`
  (`agent_launch_utils.py:370-389`) currently returns `(name, path, status)` and
  **drops** the group; discovery consumes that triple at `:498`. Change it to
  return `(name, path, status, project_group)` and build a **path-keyed lookup**
  `{realpath(path): (group, name, status)}` for discovery to consult.

- **D3 — Path-keyed live↔registry matching (not name-keyed).** Live sessions use
  `project_root.name` (basename, `:493`) while registry rows use config
  `project.name` (`:503`); these can differ. Group resolution for a **live**
  session looks up the registry lookup by **normalized real path** of its
  `project_root`, not by name. Only if no registry row matches does it read the
  session's own `project_config.yaml`.

- **D4 — Writes reject invalid slugs (no normalization in this child).** The slug
  validator returns valid / invalid+reason. Every **non-interactive write path**
  (CLI `group set`, add/sync bootstrap reading a repo's config) **rejects** an
  invalid slug with a clear message that names the offending value and source
  (e.g. "repo X config project_group 'Foo Bar' is not a valid slug …"). Inline
  normalization is deferred to the future settings UI (child 3), which may
  normalize-then-confirm *before* calling the writer.

- **D5 — Child 3 mutates via the CLI, not a parallel Python writer.** The writer
  stays the single bash authority (`build_registry_yaml` + the `group` verbs).
  Child 3's Python settings TUI **shells out to `ait projects group set/unset/sync`**
  rather than writing YAML directly; it may reuse the Python slug validator for
  pre-flight validation before shelling out. (No Python registry-mutation API is
  introduced in this child — that would duplicate the writer and widen blast
  radius for no current need.)

- **D6 — Validate config groups at READ time too, not just at write.** D4 rejects
  invalid slugs at the write paths (add/sync), but discovery's config fallback
  (step 5, for a **live-unregistered** repo or a registered row that falls back to
  its config) reads `project.project_group` straight from the repo config and would
  otherwise leak an un-validated value into `AitasksSession.project_group`. The
  cached config reader therefore **runs the same slug validator** and treats an
  invalid value as **None (ungrouped)**, emitting a debug/warning line (non-fatal —
  discovery must never crash on a malformed config). The sentinel `-` is **not** a
  valid config value (it is registry-only); an invalid or sentinel config group →
  None. Net: only a valid slug can ever populate `AitasksSession.project_group`.

## Steps

1. **Shared slug validator** — `^[a-z0-9][a-z0-9_-]*$` (must start alnum). Lives in
   `agent_launch_utils.py` (importable by Python; child 3 reuses it). Rejects (does
   not normalize) `:` `#` `|` space quote uppercase leading-space, and the reserved
   sentinel `-` is **not** a valid user slug. Bash write paths call it via a thin
   CLI shim (e.g. `agent_launch_utils.py --validate-slug <s>` → exit 0/1 + reason).
   Rejecting `|` keeps the pipe record structurally safe.

2. **Registry reader 4→5 field** — `_parse_registry_records()`
   (`agent_launch_utils.py:294-367`) returns
   `(name, path, git_remote, last_opened, project_group)`; parse an optional
   `project_group:` line per entry (empty string when absent; the `-` sentinel is
   passed through verbatim). Update **every positional consumer** (Blast radius
   below) — the tuple is positional, so a missed 4-var unpack raises `ValueError`.
   - `build_registry_yaml` (`aitask_projects.sh:179-194`): accept a 5th `|`-field
     and emit `project_group:` when non-empty (conditional-emit, matching the
     existing `git_remote`/`last_opened` style; the `-` sentinel is non-empty so it
     persists).
   - `--list-registry` (`_cli_list_registry`, `agent_launch_utils.py:950-955`):
     emit the 5th pipe field. **This is load-bearing for write-path preservation**
     (D-below) because the whole-line-preserving writers (`cmd_remove`, `prune`)
     only retain the group if `--list-registry` carries it.
   - bash awk reader `index_lookup_path` (`aitask_project_resolve.sh:150-195`):
     resolves only `name`/`path`, so needs no new field to resolve — but extend the
     **parity golden** (`tests/test_registry_reader_parity.sh:83-91`) to include the
     5th field and prove it inert to resolution. **Land parity in THIS child.**

3. **`AitasksSession.project_group`** — add `project_group: str | None = None` to the
   frozen dataclass (`agent_launch_utils.py:96-119`). Defaulted → field-accessor
   consumers (tui_switcher, stats, monitor) unaffected. Update the field-set
   assertion in `tests/test_multi_session_primitives.sh:55`.

4. **`_read_registry_index()` returns group + path lookup (D2/D3)** — change its
   return to `(name, path, status, project_group)` (`:370-389`) and add a helper
   that builds `{os.path.realpath(path): (group, name, status)}`. Update the sole
   consumer (discovery `:498`).

5. **Discovery-time group resolution (D1/D3)** — in `discover_aitasks_sessions()`
   (`:435-510`) populate `project_group` for EVERY session:
   - **live** (`:490-494`): look up the path-keyed registry lookup by
     `realpath(project_root)`; if a row matches use its tri-state value (sentinel
     `-` → None, no fallback); else read the session's own
     `project_config.yaml` `project.project_group`; else None.
   - **registered** (`:496-507`): use the row's tri-state value (sentinel → None);
     if absent/empty, fall back to that root's config; else None.
   - Add a cached config reader beside `_read_default_session()` (`:392-432`, which
     already parses `project_config.yaml`); cache keyed by realpath to avoid
     re-reading across the live + registered passes. The reader **validates** the
     config `project_group` through the slug validator (D6) and returns None +
     debug-warns on an invalid/sentinel value, so invalid config can never leak
     into the session model.

6. **Bootstrap + write paths carry the 5th field (D1/D4 + concern 3)** —
   - `cmd_add` (`:267-306`): read `project.project_group` from the repo config
     (mirroring the existing `project.name` read via `read_project_field`,
     `:109-138`), **validate-or-reject** (D4). On **re-add of an existing project**,
     preserve that entry's **existing registry group** (registry wins) instead of
     clobbering it with config bootstrap; only seed from config when the entry is
     new or its registry group is absent/empty. The re-appended fresh entry must
     emit **5** fields (`:299`).
   - `cmd_update` (`:394-399`): the awk row-rewrite must carry `$5` through
     (`print $1 "|" new_path "|" $3 "|" today "|" $5`) so a path/last update never
     drops the group.
   - `cmd_remove` (`:355`) and `cmd_prune` (`:432`): preserve whole lines already —
     **no field surgery**, so they retain the group once step 2's `--list-registry`
     emits it. `cmd_doctor` mutates only via `cmd_update`/`cmd_remove`, so fixing
     `cmd_update` covers it (its own `:499` 4-field read is display-only).
   - Add a **`group sync`** path that backfills absent/empty registry groups from
     each entry's repo config (never overwriting a real value or the `-` sentinel),
     rejecting invalid config slugs with a clear per-repo message.

7. **`ait projects group` CLI** — extend the dispatch table (`:641-685`; current
   verbs list/add/remove/update/prune/doctor/resolve/exec) with a `group` verb:
   - `group list` — groups → members, including STALE rows (so they can be
     reassigned) and a synthetic "(ungrouped)" bucket.
   - `group set <name> <group>` — validate slug (reject if invalid), write via the
     authority writer.
   - `group unset <name>` — write the `-` sentinel (explicit ungrouped, D1).
   - `group sync` — step-6 backfill.
   All mutations go through `build_registry_yaml`; never direct YAML writes.

8. **Pure `group_sessions(sessions, selected_group)`** — new function in
   `agent_launch_utils.py` (none exists today). Ring = `[members of selected_group]
   + [out-of-group where is_live]`. Stale in-group kept (flagged); stale
   out-of-group dropped from ring but still listed by `group list`. Ungrouped repos
   (registry sentinel `-`, or no group anywhere) under a synthetic cyclable
   "(ungrouped)" group. Returns the ordered group list for `[`/`]`. Pure (no I/O),
   unit-testable, consumed unchanged by t1025_2 / t1025_3.

## Blast radius — verified positional-tuple consumer sites

`_parse_registry_records()` is positional; growing it 4→5 requires updating each
site or Python raises `ValueError`:
- `agent_launch_utils.py:381` (inside `_read_registry_index`) — add `_group` (and
  thread it into the new 4-tuple return, step 4).
- `agent_launch_utils.py:964` (`_cli_resolve_index`) — add `_group`.
- `agent_launch_utils.py:950-955` (`_cli_list_registry`) — unpack + emit 5th field.
- `aitask_project_resolve.sh:90` (`cmd_list`) — `IFS='|' read` add trailing `_group`
  so the remainder isn't folded into `_last`.
- `test_multi_session_primitives.sh:55` — dataclass field-set assertion.
- `tests/test_discover_*.py` — named-arg constructors pass unchanged; add new-field
  assertions where group resolution is exercised.

## New config surface (no key yet — confirmed)

- `seed/project_config.yaml:37-39` (commented `project:` block) — add a commented
  `#   project_group:` line.
- This repo's own `aitasks/metadata/project_config.yaml` — leave unset (ungrouped).

## Verification

- `bash tests/test_registry_reader_parity.sh` — parity holds with the new field
  (golden updated; 5th field inert to resolution).
- `bash tests/test_projects_cmd.sh` — extend with:
  - `group set/unset/list/sync` happy paths.
  - **Group-preservation regression tests** across **add (re-add), update, remove,
    prune, doctor→update** — assert a pre-set registry group survives each mutation
    of an *unrelated* field on the same or another row (concern 3).
  - **`group unset` against a repo whose config declares `project_group`** — assert
    discovery resolves it to ungrouped (sentinel beats config fallback, D1).
  - **Re-add preserves a user-edited registry group** rather than reverting to the
    config bootstrap value (D1).
  - **Invalid slug rejected** on `group set` and on add/sync bootstrap from a config
    with a bad `project_group` (D4).
- New Python unit tests (pattern: `tests/test_discover_include_registered.py` +
  `tests/run_all_python_tests.sh`):
  - slug validator accept/reject table (incl. the `-` sentinel is not a valid slug).
  - discovery group resolution: live-registered (path-keyed match, D3),
    live-UNregistered (group from own config), name≠basename divergence still
    resolves by path, sentinel → ungrouped-no-fallback, ungrouped.
  - **invalid config group at read time → None + warning** (D6), for both a
    live-unregistered repo and a registered row falling back to config; assert the
    bad value never reaches `AitasksSession.project_group`.
  - `group_sessions` ring: live-out-of-group included, stale-in-group kept,
    stale-out-of-group dropped, no-groups flat fallback.
- `bash tests/test_multi_session_primitives.sh` — dataclass field set updated.
- `shellcheck .aitask-scripts/aitask_projects.sh .aitask-scripts/aitask_project_resolve.sh`.

## Step 9
Standard child archival (see parent plan / task-workflow Step 9). Final
Implementation Notes must record the tri-state sentinel contract, the path-keyed
matching rule, and the slug-reject policy for sibling tasks t1025_2/3.

## Risk

### Code-health risk: medium
- `_parse_registry_records()` returns a **positional** tuple unpacked at 4+ sites feeding load-bearing discovery (TUI switcher / monitor / stats); a missed 4→5 site raises `ValueError` at runtime, not at lint. · severity: medium · → mitigation: registry_record_namedtuple
- Multiple bash writers reconstruct registry rows field-by-field (`cmd_add`, `cmd_update`); each must carry the new pipe field or silently drop the group. The whole-line-preserving writers depend on `--list-registry` emitting it. · severity: medium · → mitigation: covered in-task by the group-preservation regression tests across add/update/remove/prune/doctor
- Tri-state sentinel (`-`) is an implicit encoding on top of the pipe format; readers must treat it consistently. · severity: low · → mitigation: covered in-task by the sentinel/fallback unit + cmd tests

### Goal-achievement risk: low
- Scope is the data layer only (child 1 of 5); within scope the plan now covers the group-clear semantics, registry→discovery threading, write-path preservation, name/path matching, and slug policy that the review flagged. Approach matches existing single-reader-authority + config-bootstrap patterns. · severity: low · → mitigation: None

### Planned mitigations
- timing: after | name: registry_record_namedtuple | type: refactor | priority: low | effort: medium | addresses: code-health (positional-tuple unpack footgun) | desc: Convert `_parse_registry_records()` to return a NamedTuple so registry readers reference named fields instead of positional unpacking, removing the missed-unpack-site ValueError class of bug.
