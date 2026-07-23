---
priority: medium
effort: high
depends: [t1223_3]
issue_type: feature
status: Ready
labels: [ait_settings, project_groups]
gates: [risk_evaluated]
anchor: 1223
created_at: 2026-07-23 18:32
updated_at: 2026-07-23 18:32
---

## Context

Fourth child of t1223 and the **headless seam for cross-repo settings** — no
Textual. It does two things: extends the shared `config_utils` persistence API so
it can merge partial config into an arbitrary repo's metadata dir, and adds a
module that reads/diffs/validates the default code agent per operation across
repos. t1223_5 consumes it.

There is currently **no path-parameterized settings writer anywhere in the
framework** (`aitask_codeagent.sh` is read-only: `resolve`/`list-models`/`check`/
`invoke`; `settings_app.ConfigManager` is cwd-bound). This child creates it.

Parent plan: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.
**Contracts D and E are binding** and are restated inline below.

## Key files to modify

- `.aitask-scripts/lib/config_utils.py` — atomic writer + `import_all_configs`
  extension.
- **New:** `.aitask-scripts/lib/cross_repo_settings.py`
- **New:** `tests/test_cross_repo_settings.py`
- `tests/test_config_utils.py` — must pass **unchanged** (regression proof).

## Reference files for patterns

- `.aitask-scripts/lib/config_utils.py:63-80` (`deep_merge`), `:91-121`
  (`load_layered_config` — note the layer order), `:124-147` (`_save_json` /
  `save_project_config` / `save_local_config`), `:258-321` (`export_all_configs`),
  `:373-459` (`import_all_configs`, incl. the path-traversal guard at `:411-413`).
- `.aitask-scripts/lib/gate_ledger.py:358-370` and
  `.aitask-scripts/lib/attachment_meta.py:65-72` — the house atomic-write pattern
  (temp in the same dir + `os.replace`). Reuse the shape; do not invent a third.
- `.aitask-scripts/settings/settings_app.py:2281-2310` — `_handle_agent_pick`:
  **the existing masked-override semantic**. A project-layer write deletes the
  matching key from the local layer, dropping `defaults` (and the file) when it
  becomes empty. Reuse this behavior; do not reinvent it.
- `.aitask-scripts/settings/settings_app.py:485-493` — `save_codeagent` (deletes
  an emptied local file).
- `.aitask-scripts/lib/agent_launch_utils.py:232-251` — `resolve_agent_string`,
  the **independent ground truth** for a repo's effective agent per operation.
- `.aitask-scripts/lib/agent_model_picker.py:44-56` — `load_all_models(project_root)`,
  already root-parameterized; use it for destination validation.
- `.aitask-scripts/lib/agent_string.sh:26` (`DEFAULT_AGENT_STRING`), `:48-66`
  (`parse_agent_string`, `SUPPORTED_AGENTS=(claudecode codex opencode)`).
- `aidocs/framework/model_reference_locations.md:55-68` — the authoritative
  resolution order.

## Data shapes (inline, do not go looking)

`aitasks/metadata/codeagent_config.json` — one top-level key, a flat map:

```json
{ "defaults": { "pick": "claudecode/opus4_8", "explore": "claudecode/opus4_8",
                "shadow": "codex/gpt5_6_terra", "work-report": "claudecode/sonnet4_6" } }
```

`brainstorm-<type>-launch-mode` keys live in the same map but hold
`headless|interactive`, **not** agent strings — exclude them from the agent
matrix. `models_<agent>.json` is `{"models": [{"name": ..., "cli_id": ...}, ...]}`;
the model half of an agent string is a `name`, not a `cli_id`.

Resolution order (most specific first): `codeagent_config.local.json` →
`codeagent_config.json` → `seed/codeagent_config.json` → `DEFAULT_AGENT_STRING`.
**Local wins** — this is why contract D exists.

## Part 1 — `config_utils` extension (contract E, binding)

Add an atomic JSON writer (temp in the same directory + `os.replace`) and route
**all** `import_all_configs` writes through it, so a concurrent reader never sees
a partial file and a failed write leaves the original intact.

Extend the signature:

```python
def import_all_configs(input_path=None, metadata_dir=..., overwrite=False,
                       selected_files=None, *, bundle=None, merge=False) -> list[str]:
```

Binding semantics:
- `bundle=` and `input_path=` are **mutually exclusive**; exactly one required —
  `ValueError` otherwise.
- `merge=True` **requires** `overwrite=True` — `ValueError` otherwise (merging
  into a file you refuse to overwrite is incoherent).
- `selected_files` filters `bundle=` identically to `input_path=`.
- **Fail closed on a bad destination:** in merge mode read the target first; if it
  exists but is unreadable or invalid JSON, **raise and write nothing**. A
  malformed destination is never replaced.
- **Type conflicts are rejected, not clobbered:** if the bundle holds a dict where
  the destination holds a non-dict at the same path (or the reverse), raise with a
  named reason rather than letting `deep_merge`'s override-wins rule silently drop
  a subtree.
- Project vs local target is chosen by the **filename inside the bundle**
  (`codeagent_config.json` vs `codeagent_config.local.json`) — no new layer arg.
- The existing path-traversal guard applies to `bundle=` too.
- **Non-merge, path-based behavior is bit-for-bit unchanged.**

## Part 2 — `cross_repo_settings.py` (contract D, binding)

```python
AGENT_OPERATIONS_EXCLUDE_SUFFIX = "-launch-mode"

def read_operation_defaults(root) -> dict[str, OperationValue]:
    """Per operation: effective, project_value, local_value, provenance.

    `effective` is GROUND TRUTH from resolve_agent_string(root, op) — an
    independent path, not our own merge. `provenance` in
    {'local','project','seed','builtin'} is derived from the raw layers.
    If the derived effective disagrees with resolve_agent_string, provenance
    is 'conflict' and the caller must render it as such — never guess."""

def diff_across_repos(roots) -> dict[str, dict[str, OperationValue]]:
    """{operation: {repo_key: OperationValue}}; repo_key = os.path.realpath."""

def plan_push(value, dest_root, operation, layer) -> PushOutcome:
    """layer in {'project','local'}. Typed outcome, never a bare bool:
       ok | noop | masked(masking_value) | rejected(reason)"""

def apply_push(value, dest_root, operation, layer, clear_mask=False) -> None:
    """Writes via import_all_configs(bundle=..., merge=True, overwrite=True).
    clear_mask=True additionally removes the local override for `operation`,
    mirroring settings_app._handle_agent_pick:2299-2306."""
```

Outcome rules:
- `noop` — the destination's **effective** value already equals `value`.
- `masked` — `layer == 'project'` **and** the destination has a local override for
  that operation. Carries the masking value so the UI can show it.
- `rejected(reason)` — distinct reasons, each separately tested:
  `model_not_in_dest_catalog` (model absent from the destination's
  `models_<agent>.json`), `malformed_agent_string` (fails `parse_agent_string`
  shape / unsupported agent), `dest_config_unreadable` (invalid or unreadable
  destination config).

## Verification steps

```bash
python3 tests/test_cross_repo_settings.py
python3 tests/test_config_utils.py          # MUST pass unchanged
python3 tests/test_config_utils_shortcuts.py
```

Required tests — all against **fixture repo roots** under `tempfile.mkdtemp()`,
never cwd:

**config_utils (contract E)**
1. `bundle=` + `input_path=` together ⇒ `ValueError`; neither ⇒ `ValueError`.
2. `merge=True, overwrite=False` ⇒ `ValueError`.
3. **Exact target-file diff** — push one operation into a destination with 10
   operations: re-read the file and assert **only that key changed** and the other
   9 are byte-identical in value.
4. **Unrelated-key negative control** — the destination has an unrelated
   top-level key (e.g. `"custom": {...}`); after the merge it survives verbatim.
   *This test must fail if merge mode is replaced by whole-file write.*
5. **Fail closed** — destination contains invalid JSON: the call raises **and the
   file is byte-identical afterwards** (read bytes before/after).
6. **Type conflict** — bundle has `{"defaults": {...}}` where the destination has
   `"defaults": "oops"` ⇒ raises with the named reason; file unchanged.
7. **Atomicity** — monkeypatch `os.replace` to raise: the original file is intact
   and no `.tmp` residue remains.
8. `selected_files` filters `bundle=` the same as `input_path=`.
9. Path traversal in a `bundle=` filename (`../evil.json`) ⇒ `ValueError`.
10. Legacy regression: existing non-merge path behavior unchanged (the untouched
    `tests/test_config_utils.py` passing is the proof).

**cross_repo_settings (contract D)**
11. Provenance truth table: value only in project ⇒ `project`; only in local ⇒
    `local`; in both ⇒ `local` (and effective equals the local value); in neither
    but in `seed/` ⇒ `seed`; nowhere ⇒ `builtin`.
12. `conflict` — stub `resolve_agent_string` to return something the layers do not
    imply; assert provenance is `conflict` and no guess is made.
13. `-launch-mode` keys are excluded from the operation set.
14. `noop` when the destination effective already matches.
15. **`masked`** — destination has a local override; `plan_push(..., layer='project')`
    ⇒ `masked` carrying the masking value. With `layer='local'` ⇒ `ok`.
16. Each `rejected` reason fires for its own cause and **only** its own cause.
17. `apply_push(..., layer='project', clear_mask=True)` removes the local key,
    drops an emptied `defaults`, deletes an emptied local file, and leaves other
    local keys intact — matching `_handle_agent_pick`.
18. `diff_across_repos` groups by operation across ≥3 fixture roots and flags
    divergence correctly.

## Notes for sibling tasks

- t1223_5 must render `provenance`/`conflict`, never re-derive the effective
  value itself.
- `plan_push` returning `masked` is **not** an error — the UI resolves it via the
  three-way prompt and then calls `apply_push` with the chosen layer/`clear_mask`.
