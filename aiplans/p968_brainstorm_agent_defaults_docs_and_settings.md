---
Task: t968_brainstorm_agent_defaults_docs_and_settings.md
Base branch: main
plan_verified: []
---

# Plan: t968 — Brainstorm agent-defaults docs + settings-TUI gap

## Context

`ait brainstorm` spawns a code agent per **node operation**, and the
per-operation defaults (agent binary + model + launch mode) live in a scattered,
undocumented set of places. t968 (a `documentation` task) asks to (1) document
that agent-control surface on the brainstorm website docs page t929_3 created,
and (2) close a small settings-TUI gap where some agent-type rows render without
helper text.

**Important drift found vs. the task's "verified" section.** The task was
authored 2026-06-10; the brainstorm design has changed since. Re-verified against
live code today:

- `_WIZARD_OP_TO_AGENT_TYPE` now lives in
  `.aitask-scripts/brainstorm/constants.py:60` (not `brainstorm_app.py:167`) and
  maps **6** design ops → 6 agent types: `explore→explorer`,
  `compare→comparator`, `synthesize→synthesizer`,
  `module_decompose→module_decomposer`, `module_merge→module_merger`,
  `module_sync→module_syncer`. Plus `initializer` (bootstrap/init) = **7** agent
  types total — matching `BRAINSTORM_AGENT_TYPES` (`brainstorm_crew.py:48`).
- The `detail`/`patch` ops and their `detailer`/`patcher` agent types were
  **removed** (confirmed by the historical comment at `brainstorm_app.py:3288`
  "(removed) patcher op…"). The task's "8 node ops + bootstrap → 9 types" and its
  list of "6 types that already have descriptions (… detailer, patcher …)" are
  therefore **stale**.
- `aitasks/metadata/codeagent_config.json` still carries orphaned
  `brainstorm-detailer` and `brainstorm-patcher` keys (lines 13–14) that map to
  no live op and are absent from `BRAINSTORM_AGENT_TYPES`. No live code, seed
  config, or docs reference them (only archived plans + the historical comment).

**Scope decision (explicit, correcting the stale AC).** Because the settings
"Agent Defaults" tab renders one editable agent-string row for **every**
`brainstorm-*` key in the config `defaults` (the loop at
`settings_app.py:2110` iterates `all_keys` unfiltered), the two stale keys
render as **dead orphan rows** for ops that no longer exist — actively
misleading, which contradicts the task's "understand it" goal. The cleanest
low-blast-radius consolidation (the deliverable-3 invitation) is to **remove the
two stale keys** so config matches the live 7-type set, rather than write helper
text for dead types. After that removal, exactly the 3 `module_*` types lack
descriptions — which is precisely the gap the task's deliverable 2 names. The
two changes are complementary: together they leave the tab with no orphan rows
and every rendered row described.

## Deliverable 1 — Documentation (primary)

t929_3 already created the docs page set under
`website/content/docs/tuis/brainstorm/` (`_index.md`, `how-to.md`,
`reference.md`). `reference.md` already has an **"Operations and agents"** table
(lines 132–145) with the correct current 6-op→agent mapping. What is missing is
the **agent model-defaults / agent-control** surface.

**Edit `website/content/docs/tuis/brainstorm/reference.md`:** add a new
`### Agent model defaults` subsection immediately after the existing
"Operations and agents" section (before "Module decompose modes"). Cover, all
verified against code:

- **Where defaults live:** `aitasks/metadata/codeagent_config.json` under
  `defaults`, keyed `brainstorm-<type>` → `"<agent>/<model>"`, with a paired
  optional `brainstorm-<type>-launch-mode` key. Enumerate **all 7** live agent
  types — the **6 design-op agents** (cross-reference the existing op→agent
  table rather than re-tabulating: explorer, comparator, synthesizer, module
  decomposer/merger/syncer) **plus the `initializer` (bootstrap) agent**, which
  is *not* in that table because it runs at session init — it reformats an
  imported markdown draft (`ait brainstorm init --proposal-file`) into the
  first graph node and has its own configurable `brainstorm-initializer`
  default. Calling `initializer` out explicitly is required so the agent-control
  surface is fully documented (concern 2).
- **Layered resolution:** hardcoded resource defaults
  (`BRAINSTORM_AGENT_TYPES` — `max_parallel`, `launch_mode`) ← project
  `codeagent_config.json` ← per-user `codeagent_config.local.json` (gitignored).
  Note that the agent string/model is **bound at session-init time** (crew
  `--add-type` registration), so **changing a model takes effect on a new
  session**, not the current one.
- **Launch mode:** a per-type default (`interactive`), overridable via the
  `brainstorm-<type>-launch-mode` config key, and **selectable per operation**
  in the operation wizard (a launch-mode field on the wizard form).
- **How to change it:** via the Settings TUI **"Agent Defaults"** tab — pick the
  agent/model and the paired launch mode, with separate **project** and **user**
  (local override) layers. Cross-link to the Settings page
  (`{{< relref "/docs/tuis/settings" >}}`), consistent with the page's existing
  "Next: Settings" footer.

**Conventions** (`aidocs/framework/documentation_conventions.md`): current-state
only (no "this used to be detail/patch" history); genericize agent names — use
`<agent>/<model>` placeholders, not `claudecode/opus4_8`; generic placeholder
project names; no "sister" terminology. **No `_index.md` index bullet needed** —
this edits an existing child page, not a new page; the Docsy sidebar auto-builds.

## Deliverable 2 — Settings-TUI gap (two parts: descriptions + structural filter)

**(2a) Add the missing `OPERATION_DESCRIPTIONS` entries** in
`.aitask-scripts/settings/settings_app.py` (currently ~lines 117–133). Add 6
entries matching the wording style of the existing 4 brainstorm entries — one
agent-string description + one `-launch-mode` description for each of the 3
`module_*` types:

- `brainstorm-module_decomposer` — "Model for forking module subgraph roots from a proposal in brainstorming sessions" (style-aligned to existing entries)
- `brainstorm-module_merger` — "Model for merging a module subgraph up into an ancestor"
- `brainstorm-module_syncer` — "Model for pulling a linked module's as-implemented design back into the graph"
- the three matching `…-launch-mode` entries, mirroring the existing
  `"Default launch mode (headless | interactive) for the <type> brainstorm agent type"` template.

(Exact wording finalized against `_DESIGN_OPS`/`_OPERATION_HELP` in
`constants.py` during implementation so the descriptions track the canonical
op summaries.)

**(2b) Structural filter — make `BRAINSTORM_AGENT_TYPES` the single source of
which brainstorm rows render (concern 1).** Today `_populate_agent_tab`
(`settings_app.py:2056`) builds `all_keys` as the **union of project + local**
`defaults`, and the agent-string render loop (`:2110`) renders a row for **every**
key with **no** `BRAINSTORM_AGENT_TYPES` filter (only the launch-mode emission at
`:2175` filters). So removing the stale keys from the *project* config alone does
**not** guarantee the orphan rows disappear — a stale `brainstorm-detailer` /
`brainstorm-patcher` (or any removed type) in `codeagent_config.local.json` or an
imported user config would still render a dead, misleading row.

Add a guard at the top of the loop (right after the existing `-launch-mode`
skip), parallel to the launch-mode filter already at `:2175`:

```python
# Skip orphaned brainstorm agent types no longer in BRAINSTORM_AGENT_TYPES
# (a removed op can leave a stale key in either config layer) — they would
# otherwise render as dead orphan rows for ops that no longer exist.
if key.startswith("brainstorm-") and \
        key[len("brainstorm-"):] not in BRAINSTORM_AGENT_TYPES:
    continue
```

This makes the rendered brainstorm set structurally equal to
`BRAINSTORM_AGENT_TYPES` regardless of which layer holds a stale key — the
robust fix (preferred over relying on a clean local layer). Non-brainstorm keys
(`pick`, `explain`, `qa`, `raw`, `explore`, `shadow`) are untouched. (Note: the
existing `-launch-mode` skip at `:2112` already drops orphan launch-mode keys,
and the safety-net loop at `:2183` only emits for `BRAINSTORM_AGENT_TYPES`, so
no orphan launch-mode rows survive either.)

## Deliverable 3 — Stale-config cleanup (surfaced drift; the clean consolidation)

**Edit `aitasks/metadata/codeagent_config.json`:** remove the two orphaned keys
`brainstorm-detailer` and `brainstorm-patcher` from `defaults`. This is safe:
`get_agent_types()` (`brainstorm_crew.py`) only requires `brainstorm-<type>`
keys for types **in** `BRAINSTORM_AGENT_TYPES`, which excludes both; no live
code, seed config (`seed/codeagent_config.json` has no brainstorm keys), or docs
reference them.

This cleanup keeps the canonical **shared/project** config honest (no dead data
for the next reader); the structural filter (2b) is what actually *guarantees*
no orphan rows render across **both** layers. The two are complementary — the
cleanup alone is not sufficient (concern 1), and the filter alone would leave
stale data in the committed project config.

This file is on the `aitask-data` branch (symlinked) and is tracked via
`./ait git` — commit it with `./ait git`, staging only this path (concurrent
data-branch writers caveat).

## Files to modify

| File | Change |
|------|--------|
| `website/content/docs/tuis/brainstorm/reference.md` | New `### Agent model defaults` subsection after "Operations and agents"; enumerates all 7 types incl. explicit `initializer` |
| `.aitask-scripts/settings/settings_app.py` | (2a) 6 new `OPERATION_DESCRIPTIONS` entries; (2b) structural `BRAINSTORM_AGENT_TYPES` filter in the agent-string render loop |
| `aitasks/metadata/codeagent_config.json` | Remove orphaned `brainstorm-detailer` / `brainstorm-patcher` keys (commit via `./ait git`) |
| `tests/test_settings_brainstorm_descriptions.py` *(new)* | Guard test: every live type has helper text + no orphan config defaults (see Verification) |

No per-agent skill port is needed (settings TUI is framework Python, not a skill).

## Guard test (concern 3)

Add `tests/test_settings_brainstorm_descriptions.py` (Python `unittest`, mirroring
`tests/test_brainstorm_crew.py`'s import style; runs under the framework venv
`/home/ddt/.aitask/bin/python3`, verified importable in planning). It derives the
expected set from `BRAINSTORM_AGENT_TYPES` rather than hardcoding a copy — a
"derive + guard" invariant that prevents the gap reopening when a future type is
added:

- **`test_every_live_type_has_description`** — for each `t` in
  `BRAINSTORM_AGENT_TYPES`, assert both `brainstorm-{t}` and
  `brainstorm-{t}-launch-mode` are keys in `OPERATION_DESCRIPTIONS`.
- **`test_no_orphan_brainstorm_defaults`** — load
  `aitasks/metadata/codeagent_config.json`; for every `brainstorm-*` key in
  `defaults`, assert its type (suffix-stripped) is in `BRAINSTORM_AGENT_TYPES`
  (catches `detailer`/`patcher` regressions and any future drift).

## Verification

1. **Docs build (Hugo):** `cd website && hugo build --gc --minify` — confirm no
   broken-relref errors from the new Settings cross-link; eyeball the new
   subsection renders under "Operations and agents".
2. **Guard test (primary automated check):**
   `/home/ddt/.aitask/bin/python3 -m pytest tests/test_settings_brainstorm_descriptions.py -q`
   (or run the file directly via `python3 tests/test_settings_brainstorm_descriptions.py`).
   Both tests must pass — this exercises `OPERATION_DESCRIPTIONS` and the
   live-type/config invariants directly (replacing the previously-too-weak
   import smoke). Already confirmed in planning that the import resolves and that
   the 3 `module_*` descriptions are the only ones missing pre-fix.
3. **Settings TUI (manual):** launch `ait settings`, open the **Agent Defaults**
   tab, scroll to the brainstorm section — confirm (a) the 3 `module_*` rows now
   show italic helper text for both the agent-string and launch-mode rows, and
   (b) no `brainstorm-detailer` / `brainstorm-patcher` orphan rows render (7
   brainstorm agent-string rows, all described). Optionally re-confirm (b) is
   robust by temporarily adding a `brainstorm-detailer` key to a local config
   layer and checking the filter still suppresses it.
4. **Lint:** `shellcheck` is N/A (no shell touched). Hugo build per step 1 covers
   the docs.

## Step 9 (Post-Implementation)

Standard cleanup/archival: working on the current branch (profile `fast`), so no
worktree to remove. Commit code (`reference.md`, `settings_app.py`) via plain
`git`; commit `codeagent_config.json` separately via `./ait git`; then archive
via `aitask_archive.sh 968` and push.

## Risk

### Code-health risk: low
- Docs prose + 6 static dict entries + removal of 2 verified-orphan config keys + one render-loop `continue` guard (filter 2b) parallel to logic already present at `settings_app.py:2175`/`:2183`. The filter is the only behavior change — it narrows the brainstorm rows rendered in one TUI tab to the canonical type set, covered by a new guard test. Blast radius is four isolated files; the config removal was checked against `get_agent_types()`'s required-key set, the seed config, and a repo-wide reference scan. · severity: low · → mitigation: none
- None otherwise identified.

### Goal-achievement risk: low
- The task's stated "verified" facts had drifted (detail/patch ops removed); this plan re-verifies against live code and makes the resulting scope correction explicit, so the delivered docs describe current reality rather than the stale spec. · severity: low · → mitigation: none
- None otherwise identified.

`risk_mitigations_planned = false` — no before/after mitigation tasks warranted.

## Final Implementation Notes

- **Actual work done:** All four deliverables landed as planned. (1) Added an
  `### Agent model defaults` section to
  `website/content/docs/tuis/brainstorm/reference.md` (after "Operations and
  agents"): all 7 agent types incl. explicit `initializer`, the
  `codeagent_config.json` `defaults` layout with `<agent>/<model>` placeholders,
  3-layer resolution, session-init binding, launch-mode override, and a Settings
  cross-link. (2a) Added 6 `OPERATION_DESCRIPTIONS` entries for the 3 `module_*`
  types + launch-mode variants in `settings_app.py`. (2b) Added a structural
  `BRAINSTORM_AGENT_TYPES` filter in the `_populate_agent_tab` render loop so
  orphan brainstorm keys in *either* config layer never render. (3) Removed the
  orphaned `brainstorm-detailer`/`brainstorm-patcher` keys from
  `aitasks/metadata/codeagent_config.json`. (4) Added
  `tests/test_settings_brainstorm_descriptions.py` (2 derive-from-source guard
  cases).
- **Deviations from plan:** None of substance. The plan corrected the task's
  stale "verified" section (the design dropped `detail`/`patch` ops since
  2026-06-10); implementation followed the corrected scope.
- **Issues encountered:** `pytest` is not installed in the framework venv; ran
  the guard test via `python3 tests/...py` (unittest) instead — both cases pass.
  The recursive `grep` for stale-key references initially missed the symlinked
  `aitasks/` tree (grep does not follow symlinks); re-ran against `.aitask-data/`
  and `aitasks/metadata/` explicitly to confirm the keys were truly orphaned.
- **Key decisions:** Chose a structural render-loop filter (robust across both
  config layers) as the *guarantee*, with the project-config key removal as
  complementary cleanup — rather than writing helper text for the dead
  `detailer`/`patcher` types. This addresses the reviewer concern that
  project-only cleanup would not suppress orphan rows sourced from
  `codeagent_config.local.json`.
- **Upstream defects identified:** None. The stale `detailer`/`patcher` config
  drift was a pre-existing artifact but is fully resolved within this task, not
  deferred.

## Verification (executed)

- `python3 tests/test_settings_brainstorm_descriptions.py` → both tests OK.
- `python3 -m py_compile .aitask-scripts/settings/settings_app.py tests/...py` → OK.
- `cd website && hugo build --gc --minify` → 218 pages built, no relref errors
  (only pre-existing Hugo deprecation WARNs).
