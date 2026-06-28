---
Task: t1030_2_local_backend_cache_index.md
Parent Task: aitasks/t1030_task_attachments_support.md
Sibling Tasks: aitasks/t1030/t1030_1_frontmatter_cli_scaffold.md, aitasks/t1030/t1030_3_archive_gc_fold_rebind.md
Archived Sibling Plans: aiplans/archived/p1030/p1030_1_*.md (after t1030_1 lands — read it first)
Worktree: aiwork/t1030_2_local_backend_cache_index
Branch: aitask/t1030_2_local_backend_cache_index
Base branch: main
---

# Plan — t1030_2 Local backend + cache + index + adapter seam

Make `ait attach add/get/rm` fully functional over `.aitask-data` with a
content-addressed local backend, a universal cache, an `index.json` refcount
ledger, and a **generalizable backend adapter seam**. Builds on t1030_1.

Design: `aidocs/task_attachments_design.md` §2/§4/§5/§8;
generalizability target `aidocs/unified_artifact_design.md` §5.
Full spec in the task file `aitasks/t1030/t1030_2_local_backend_cache_index.md`.

**Before starting:** read t1030_1's archived plan + Final Implementation Notes
for the `read_yaml_mappings` output contract and `attachment_utils.sh` signatures.

## Step 1 — Adapter seam `lib/attachment_backend.sh` (NEW)
- Dispatcher: `case "${ATTACHMENT_BACKEND:-local}" in local) … ;; *) die ;; esac`
  with a `# BACKEND-EXTENSION-POINT` marker (mirror
  `aidocs/gitremoteproviderintegration.md`).
- Public contract (names/shape per design §5 so t1076_1 widens to
  `artifact_backend`): `attachment_backend_put <hash> <file>`,
  `…_get <hash> <dest>`, `…_head <hash>`, `…_delete <hash>`, `…_list`.

## Step 2 — `lib/attachment_backends/local.sh` (NEW)
- Resolve data worktree via `task_utils.sh` `_ait_detect_data_worktree`.
- Blobs at `.aitask-data/attachments/<2>/<62>` (use `attachment_shard_path`).
  `put`=idempotent copy (skip if `head`), `get`=copy to dest, `head`=`test -f`,
  `delete`=`rm`, `list`=enumerate shard dirs.

## Step 3 — `lib/attachment_index.py` (NEW, JSON ledger)
- Run via `lib/python_resolve.sh` `resolve_python` (precedent:
  `gate_orchestrator.py`). Atomic write (temp + `os.replace`).
- Schema: `{ "sha256:<hex>": { refs:[task_id…], name, mime, size, backend,
  added_at } }`.
- Subcommands: `incref <hash> <task> [k=v…]`, `decref <hash> <task>`,
  `refs <hash>`, `zero-refcount`, `rebind <old_task> <new_task>`
  (rebind/zero-refcount consumed by t1030_3).

## Step 4 — `lib/attachment_cache.sh` (NEW)
- `attachment_resolve <hash>`: (1) cache hit → print path; (2)
  `attachment_backend_head`+`get` → populate `attachment_cache_path` → print;
  (3) miss both → **loud error** (design §5, never a silent placeholder).
- `local` backend: short-circuit by symlinking the cache entry to the
  `.aitask-data/attachments/<2>/<62>` blob.

## Step 5 — Frontmatter mutation (`attachments:` list-of-mappings)
- Add `append_yaml_mapping` / `remove_yaml_mapping`. Bash mutation of a block
  list-of-mappings is fiddly — a small Python frontmatter patcher (extend
  `attachment_index.py` or a sibling `lib/frontmatter_patch.py`) is acceptable
  and likely cleaner. **Record the choice** in Final Notes. Preserve the rest of
  the file; bump `updated_at`.

## Step 6 — Wire `aitask_attach.sh` verbs
- `add <task> <file> [--backend local] [--name]`: stat size → enforce cap
  (default **25 MB**, design §10 Q3) → mime (`file --mime-type -b`) →
  `attachment_sha256` → `attachment_backend_put` → cache → `append_yaml_mapping`
  → `attachment_index.py incref` → **single `./ait git` commit** of blob +
  `index.json` + task `.md` (design §4 — the trio never drifts).
- `get <task> <name-or-hash> [--out]`: name→hash, `attachment_resolve`,
  **verify bytes==hash**, copy to `--out`/stdout.
- `rm <task> <name-or-hash>`: `remove_yaml_mapping` + `decref` (blob NOT deleted
  — GC is t1030_3); commit.

## Step 7 — Tests
- `tests/test_attach_local_backend.sh`: backend round-trip `put→head→get→verify`,
  `delete`/`list`; add/get/rm e2e in a fixture data-branch repo; size-cap
  rejection; **assert exactly one commit per `add`**; get verifies identical bytes.
- `tests/test_attach_index.sh`: incref/decref/refs/zero-refcount/rebind; atomic
  write under concurrent-ish calls.

## Verification
- `shellcheck` clean; `attachment_index.py` runs under resolved Python.
- `bash tests/test_attach_local_backend.sh` + `bash tests/test_attach_index.sh` — PASS.
- Manual: `ait attach add` a PNG → `ls` → `get --out` (identical) → `rm`;
  inspect `.aitask-data/attachments/<2>/<62>`, `index.json`, task frontmatter;
  one commit per add.

## Step 9 (Post-Implementation)
Standard per `task-workflow` Step 9. Final Notes MUST record: the `index.json`
schema, where frontmatter mutation lives (bash vs Python), the size-cap
default/config location, and confirmation the `attachment_backend_*` contract +
extension-point marker are `local`-agnostic (t1076_1 + t1089/t1090 depend on it).
