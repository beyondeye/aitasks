---
Task: t1223_4_cross_repo_settings_seam.md
Parent Task: aitasks/t1223_expand_syncer_scope_version_and_settings_sync.md
Sibling Tasks: aitasks/t1223/t1223_1_*.md, aitasks/t1223/t1223_2_*.md, aitasks/t1223/t1223_3_*.md, aitasks/t1223/t1223_5_*.md, aitasks/t1223/t1223_6_*.md
Archived Sibling Plans: aiplans/archived/p1223/p1223_*_*.md
Worktree: (none — profile 'fast': current branch)
Branch: main
Base branch: main
---

# p1223_4 — Cross-repo settings seam (headless)

> The task file `aitasks/t1223/t1223_4_cross_repo_settings_seam.md` carries the
> full API, the inline config schemas, and the binding contract text. This plan
> is the execution view. Parent design:
> `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md` (contracts
> **D** and **E**).

## Goal

Create the framework's first **path-parameterized settings writer**, by extending
the shared `config_utils` persistence API rather than forking it, plus a module
that reads / diffs / validates the default code agent per operation across repos.

## Steps

### Part 1 — `config_utils` (contract E)

1. Add an atomic JSON writer (temp in the same directory + `os.replace`,
   mirroring `gate_ledger.py:358-370` / `attachment_meta.py:65-72`) and route
   **all** `import_all_configs` writes through it.
2. Extend the signature with keyword-only `bundle=None, merge=False`:
   - `bundle=` / `input_path=` mutually exclusive, exactly one required
     (`ValueError`);
   - `merge=True` requires `overwrite=True` (`ValueError`);
   - `selected_files` filters `bundle=` identically;
   - **fail closed**: in merge mode read the target first; an existing but
     unreadable/invalid-JSON target raises and writes **nothing**;
   - **type conflicts rejected**, not clobbered — a dict-vs-non-dict mismatch at
     the same path raises with a named reason instead of letting `deep_merge`
     drop a subtree;
   - project vs local chosen by the **filename in the bundle**;
   - the existing path-traversal guard (`config_utils.py:411-413`) applies to
     `bundle=` too;
   - **non-merge path behavior stays bit-for-bit unchanged.**

### Part 2 — `lib/cross_repo_settings.py` (contract D)

3. `read_operation_defaults(root)` — per operation return `effective`
   (**ground truth** from `resolve_agent_string(root, op)`, an independent path),
   `project_value`, `local_value`, and derived `provenance` ∈
   `{local, project, seed, builtin}`. When the layer-derived effective disagrees
   with `resolve_agent_string`, provenance is `conflict` — never a guess. Exclude
   `*-launch-mode` keys.
4. `diff_across_repos(roots)` → `{operation: {repo_key: OperationValue}}` keyed on
   `os.path.realpath`.
5. `plan_push(value, dest_root, operation, layer)` → typed outcome
   `ok | noop | masked(masking_value) | rejected(reason)`, with distinct reasons
   `model_not_in_dest_catalog` / `malformed_agent_string` /
   `dest_config_unreadable`. Validate the model against the destination's own
   `models_<agent>.json` via `agent_model_picker.load_all_models(dest_root)` —
   catalogs are per-repo.
6. `apply_push(..., clear_mask=False)` — writes via
   `import_all_configs(bundle=..., merge=True, overwrite=True)`. With
   `clear_mask=True` it also removes the local override for that operation,
   dropping an emptied `defaults` and an emptied local file, exactly mirroring
   `settings_app._handle_agent_pick:2299-2306`.

## Verification

- `python3 tests/test_cross_repo_settings.py` passes.
- `python3 tests/test_config_utils.py` and `python3 tests/test_config_utils_shortcuts.py` pass **unchanged** — this is the legacy-behavior proof.
- Passing both `bundle=` and `input_path=`, or neither, raises `ValueError`; `merge=True` with `overwrite=False` raises `ValueError`.
- Exact target-file diff: pushing one operation into a destination holding ten leaves the other nine byte-identical in value.
- Negative control: an unrelated top-level key in the destination survives the merge verbatim, and the test fails if merge mode is replaced by a whole-file write.
- Fail closed: a destination containing invalid JSON causes a raise and the file is byte-identical before and after.
- Type conflict: a bundle dict against a destination scalar at the same path raises with the named reason and leaves the file unchanged.
- Atomicity: with `os.replace` monkeypatched to raise, the original file is intact and no `.tmp` residue remains.
- `selected_files` filters a `bundle=` import the same way it filters a path import.
- A bundle filename containing a path separator raises `ValueError`.
- Provenance truth table: project-only, local-only, both (local wins), seed-only and nowhere resolve to `project`, `local`, `local`, `seed` and `builtin` respectively.
- With `resolve_agent_string` stubbed to disagree with the layers, provenance is `conflict` and no value is guessed.
- `*-launch-mode` keys are excluded from the operation set.
- `plan_push` returns `noop` when the destination's effective value already matches.
- `plan_push` returns `masked` with the masking value when the layer is project and a local override exists, and `ok` for the same case with the local layer.
- Each `rejected` reason fires for its own cause and only its own cause.
- `apply_push(layer='project', clear_mask=True)` removes the local key, drops an emptied `defaults`, deletes an emptied local file, and leaves other local keys intact.
- `diff_across_repos` groups by operation across three fixture roots and flags divergence correctly.

## Out of scope

Any UI (t1223_5) and any setting other than the default code agent per operation.
