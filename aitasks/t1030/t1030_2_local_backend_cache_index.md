---
priority: medium
effort: high
depends: [t1030_1]
issue_type: feature
status: Ready
labels: [task_attachments]
anchor: 1030
created_at: 2026-06-28 12:08
updated_at: 2026-06-28 12:08
---

Implement the **local attachment backend**, the **universal local cache**, the **`index.json` refcount ledger**, and the **backend adapter seam** — making `ait attach add/get/rm` fully functional over the `.aitask-data` worktree. Depends on the scaffold from t1030_1.

Design spec: `aidocs/task_attachments_design.md` §2 (content addressing), §4 (storage layout), §5 (adapter interface + universal cache), §8 (lifecycle add/fetch). Generalizability target: `aidocs/unified_artifact_design.md` §5 — keep the contract/naming so t1076_1 can promote `attachment_backend` → `artifact_backend` by rename+widen, not re-plumb.

## Context
Second of three children of t1030. Builds the storage core on the t1030_1 primitives (`attachment_sha256`, `attachment_shard_path`, `attachment_cache_path`, `read_yaml_mappings`). The adapter seam is built **here, upfront** (not deferred to a later refactor) so the design is clean from the start and t1076_1's generalization is a rename. Establishes the `index.json` schema and backend contract that t1030_3 (archive/gc/fold) and the S3/GDrive follow-ups consume.

## Key Files to Modify / Create
- **`.aitask-scripts/lib/attachment_backend.sh`** (NEW): the dispatcher contract. `case "$ATTACHMENT_BACKEND" in local) ... ;; *) die ;; esac` routing to per-backend modules, with a `# BACKEND-EXTENSION-POINT` marker (mirror the platform-extensible pattern in `aidocs/gitremoteproviderintegration.md`). Public functions: `attachment_backend_put <hash> <file>`, `attachment_backend_get <hash> <dest>`, `attachment_backend_head <hash>`, `attachment_backend_delete <hash>`, `attachment_backend_list`. Name/shape per design §5 so t1076_1 widens to `artifact_backend`.
- **`.aitask-scripts/lib/attachment_backends/local.sh`** (NEW): local impl over `.aitask-data/attachments/<2>/<62>` (resolve the data worktree via `task_utils.sh` `_ait_detect_data_worktree`/`task_git`). `put` = idempotent copy into the sharded path; `get` = copy to dest; `head` = test -f; `delete` = rm; `list` = enumerate shard dirs.
- **`.aitask-scripts/lib/attachment_index.py`** (NEW): JSON ledger ops (JSON manipulation in bash is fragile; use Python via `lib/python_resolve.sh` `resolve_python`, consistent with `gate_orchestrator.py`). Schema: `{ "<sha256:hash>": { "refs": ["1030","42_2"], "name":..., "mime":..., "size":..., "backend":"local", "added_at":... } }`. Subcommands: `incref <hash> <task_id> [meta k=v...]`, `decref <hash> <task_id>`, `refs <hash>`, `zero-refcount` (list GC candidates), `rebind <old_task> <new_task>` (for fold; used by t1030_3). Atomic write (temp + rename). This is the file t1030_3 extends.
- **`.aitask-scripts/lib/attachment_cache.sh`** (NEW): universal cache resolver. `attachment_resolve <hash>` → resolution order: (1) cache hit → print path; (2) `attachment_backend_head` + `get` → populate `attachment_cache_path` → print path; (3) miss in both → **loud error, never a silent placeholder** (design §5). For the `local` backend, short-circuit by symlinking the cache entry to `.aitask-data/attachments/<2>/<62>`.
- **`.aitask-scripts/lib/yaml_utils.sh`**: add `append_yaml_mapping <file> <field> <k=v...>` and `remove_yaml_mapping <file> <field> <match-key> <match-val>` to mutate the `attachments:` block. Frontmatter mutation of a list-of-mappings is fiddly in bash — a small Python frontmatter patcher (e.g. extend `attachment_index.py` or a sibling `lib/frontmatter_patch.py`) is acceptable and probably cleaner; pick one and note the choice. Must preserve the rest of the frontmatter/body untouched and keep `updated_at` current.
- **`.aitask-scripts/aitask_attach.sh`**: implement `cmd_add`, `cmd_get`, `cmd_remove` (replace t1030_1 stubs):
  - `add <task> <file> [--backend local] [--name <display>]`: stat size → enforce size cap (default 25 MB; design §10 Q3) → detect mime (`file --mime-type -b`) → `attachment_sha256` → `attachment_backend_put` → populate cache → `append_yaml_mapping` into the task's `attachments:` → `attachment_index.py incref` → **single `./ait git` commit** of blob + `index.json` + task `.md` together (design §4: the three never drift).
  - `get <task> <name-or-hash> [--out <path>]`: resolve name→hash from frontmatter, `attachment_cache.sh` resolve, **verify bytes match hash**, copy to `--out` or stdout.
  - `rm <task> <name-or-hash>`: `remove_yaml_mapping` from frontmatter + `attachment_index.py decref` (do NOT delete the blob — GC is t1030_3), commit.
- **`tests/test_attach_local_backend.sh`**, **`tests/test_attach_index.sh`** (NEW).

## Reference Files for Patterns
- `aidocs/task_attachments_design.md` §4–§5, §8; `aidocs/unified_artifact_design.md` §5.
- `aidocs/gitremoteproviderintegration.md` — dispatcher + `# *-EXTENSION-POINT` markers.
- `.aitask-scripts/lib/task_utils.sh` `task_git()` (~lines 168–176), `_ait_detect_data_worktree()` (~lines 35–42) — data-branch commits.
- `.aitask-scripts/lib/python_resolve.sh` `resolve_python()`; `.aitask-scripts/lib/gate_orchestrator.py` (Python helper precedent, `hashlib.sha256`).
- `tests/lib/test_scaffold.sh` (`setup_fake_aitask_repo`) — build a fixture data-branch repo; `tests/lib/asserts.sh`.

## Implementation Plan
1. Write `attachment_backend.sh` (dispatcher) + `attachment_backends/local.sh` (impl). Unit-test the contract round-trip first: `put → head → get → verify hash`, plus `delete`/`list`.
2. Write `attachment_index.py` with atomic read-modify-write; unit-test incref/decref/refs/zero-refcount/rebind.
3. Write `attachment_cache.sh`; test cache-hit, cache-miss-then-backend, and miss-both-loud-error.
4. Add frontmatter mutation helpers (append/remove mapping).
5. Wire `cmd_add/cmd_get/cmd_remove` in `aitask_attach.sh`; ensure the add path commits the trio atomically via `./ait git`.
6. e2e tests in a fixture: add a PNG → `ls` shows it → `get --out` round-trips identical bytes → `rm` decrefs → inspect `.aitask-data/attachments/<2>/<62>`, `index.json`, and the task frontmatter; assert exactly one commit per `add`.

## Verification Steps
- `shellcheck` clean on all new/modified `.sh`; `attachment_index.py` runs under the resolved Python.
- `bash tests/test_attach_local_backend.sh` and `bash tests/test_attach_index.sh` — all PASS.
- Backend round-trip verified (`put→head→get→verify hash`); cache hit/miss per §5; size-cap rejection; single-commit invariant for `add`.

## Notes for sibling tasks
- **`index.json` schema is defined here** — t1030_3 (decref-on-archive, gc, fold rebind) and t1076_1 (manifest generalization) build directly on it. Keep `refs` as the refcount source of truth.
- The `attachment_backend_*` contract + `# BACKEND-EXTENSION-POINT` marker is what the S3/GDrive follow-ups and t1076_1 extend. Do not bake `local`-only assumptions into the dispatcher or cache layer.
- Decisions to record in Final Implementation Notes: where frontmatter mutation lives (bash vs Python), exact `index.json` schema, and the size-cap default/config location.
