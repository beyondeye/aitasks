---
Task: t1030_4_manual_verification_task_attachments.md
Parent Task: aitasks/t1030_task_attachments_support.md
Sibling Tasks: aitasks/t1030/t1030_1_frontmatter_cli_scaffold.md, aitasks/t1030/t1030_2_local_backend_cache_index.md, aitasks/t1030/t1030_3_archive_gc_fold_rebind.md
Archived Sibling Plans: aiplans/archived/p1030/p1030_1_frontmatter_cli_scaffold.md, aiplans/archived/p1030/p1030_2_local_backend_cache_index.md, aiplans/archived/p1030/p1030_3_archive_gc_fold_rebind.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# Auto-Verification — t1030_4 Task attachments manual verification

## Strategy

Autonomous auto-verification (manual-verification.md Step 1.5). The repo runs in
separate-data-branch mode (`aitasks/` / `aiplans/` are symlinks to
`.aitask-data/`), so live `ait attach add/rm/gc/fold` on real tasks would create
commits on the shared data branch (blast radius). The implemented behavior is
covered end-to-end by six dedicated test suites that exercise the real
`aitask_attach.sh` CLI and `lib/attachment_*` in **isolated temp repos** — these
are the side-effect-free proof of behavior. Item 13 (loud-failure path) was
exercised live in an isolated scratch dir.

Test suites run (all green):
- `tests/test_attach_scaffold.sh` — 39/39
- `tests/test_attach_local_backend.sh` — 28/28
- `tests/test_attach_meta.sh` — 42/42
- `tests/test_attachment_meta_lib.sh` — 11/11
- `tests/test_attach_archive_gc.sh` — 15/15
- `tests/test_attach_fold_rebind.sh` — 20/20

## Storage-model divergence (applies to items 4, 5, 8, 9, 11)

The checklist was authored against the early design (single global `index.json`
ledger + blobs at `attachments/<first2>/<remaining62>`, and decref-on-archive).
The **shipped** design (t1030_2/t1030_3) replaced these:

- **Per-blob meta files** at `attachments/meta/<2>/<62>.json` are the canonical
  refcount ledger — there is **no** `index.json` (`test_attach_local_backend`:
  "no global index.json exists").
- Blobs live at `attachments/blobs/<2>/<62>` (local backend).
- **Archiving never decrefs** — an archived task is a real referrer (browsable
  history); blobs are kept indefinitely. The `attachments_gc_grace` knob only
  governs blobs left unreferenced by `ait attach rm` or task deletion (see the
  `project_config.yaml` table in task-workflow `SKILL.md`).

Each affected item's *safety-critical intent* (content-addressed storage,
single atomic commit, blob retention, retention-safe GC, fold survival) is
fully satisfied; only the stale `index.json` / decref-on-archive wording differs.

## Execution Log

### Item 1 — `ait attach ls`
- Item text: ls prints entries (name, short-hash, size, backend); none → "No attachments."
- Approach: CLI behavior via test suite
- Action run: `bash tests/test_attach_scaffold.sh`
- Output (trimmed): asserts name, short hash (first 12 hex `9f86d081884c`), backend `local`, and "No attachments." for empty — 39/39 pass
- Verdict: pass

### Item 2 — unimplemented-verb not-yet notice
- Item text: `ait attach <add|get|rm|gc>` (pre-storage state) print not-yet notice rather than erroring obscurely
- Approach: CLI behavior via test suite + code read
- Action run: `bash tests/test_attach_scaffold.sh`; read `aitask_attach.sh`
- Output (trimmed): **Premise superseded** — add/get/rm/gc are now FUNCTIONAL (t1030_2/3). The graceful not-yet-notice behavior is verified for the one remaining stub verb `move` ("attach move stub exits non-zero", "explains it is not yet available"; help "marks unimplemented verbs").
- Verdict: pass (intent — graceful notice for unimplemented verbs — holds for `move`)

### Item 3 — `ait attach add … --name`
- Item text: add succeeds; sha256 hashed; under 25 MB cap; mime detected
- Approach: CLI behavior via test suite
- Action run: `bash tests/test_attach_local_backend.sh`
- Output (trimmed): add succeeds; mime via `file --mime-type`; "oversize add rejected per project_config cap"; "small add passes under the default 25 MB cap" — 28/28 pass
- Verdict: pass

### Item 4 — post-add storage + frontmatter + refcount
- Item text: blob at `.aitask-data/attachments/<first2>/<remaining62>`; frontmatter gains `attachments:`; index.json refcount 1
- Approach: CLI behavior via test suite
- Action run: `bash tests/test_attach_local_backend.sh`
- Output (trimmed): "blob stored under blobs/<2>/<62>", "per-blob meta written (no global index)", "no global index.json exists"; ls shows the attachment; meta refs = single task
- Verdict: pass — see storage-model divergence (blob path is `attachments/blobs/<2>/<62>`; refcount in per-blob meta, not index.json)

### Item 5 — single atomic commit
- Item text: add produces exactly ONE commit containing blob + index.json + task .md together
- Approach: CLI behavior via test suite
- Action run: `bash tests/test_attach_local_backend.sh`
- Output (trimmed): "exactly one commit per add"; "unrelated staged file NOT in the attach commit" (`_attach_commit` partial-commits explicit paths)
- Verdict: pass — commit holds blob + per-blob meta + task (s/index.json/meta/)

### Item 6 — `ait attach get --out` byte-identical + cold cache
- Item text: get returns byte-identical bytes (sha256 match); cold cache populates `~/.cache/ait/attachments/<hash>` then serves
- Approach: CLI behavior via test suite + code read
- Action run: `bash tests/test_attach_local_backend.sh`; read `attachment_cache.sh`
- Output (trimmed): "get returns identical bytes"; cmd_get re-hashes the resolved bytes and dies on mismatch (design §8); `attachment_resolve` symlinks the blob into `~/.cache/ait/attachments/<hash>` (XDG override honored, $HOME/.cache fallback)
- Verdict: pass

### Item 7 — `ait attach rm`
- Item text: rm removes frontmatter mapping, decrefs to 0, blob NOT deleted
- Approach: CLI behavior via test suite
- Action run: `bash tests/test_attach_local_backend.sh`, `bash tests/test_attach_archive_gc.sh`
- Output (trimmed): "rm decrefs the task -> refs [6]", "blob NOT deleted on rm (gc deferred to t1030_3)", "rm removed the frontmatter entry"; "rm empties refs"
- Verdict: pass

### Item 8 — archive decref + blob retention
- Item text: archiving a task that references an attachment decrefs in index.json and retains the blob (no synchronous deletion)
- Approach: CLI behavior via test suite + design read
- Action run: `bash tests/test_attach_archive_gc.sh`
- Output (trimmed): "archive keeps the sole ref (no decref)", "archived task's blob retained", "shared blob keeps BOTH refs after one task archived"
- Verdict: pass — **DIVERGENCE**: blob retention / no-synchronous-deletion ✓ (the safety-critical clause). The implemented design intentionally does NOT decref on archive (archived task is a real referrer); the checklist's "decrefs in index.json" clause is stale and reflects a superseded design.

### Item 9 — `ait attach gc` orphan sweep + retention
- Item text: gc sweeps zero-refcount orphan (backend_delete + index entry dropped) while RETAINING any hash referenced by a live task
- Approach: CLI behavior via test suite
- Action run: `bash tests/test_attach_archive_gc.sh`
- Output (trimmed): "orphan past grace is swept", "swept blob's meta file removed too", "gc retains archived-referenced blob even past grace", "gc retains shared blob", "live task's frontmatter blocks GC"
- Verdict: pass — s/index entry dropped/per-blob meta file removed/

### Item 10 — `attachments_gc_grace` knob
- Item text: grace blocks too-recent orphan; aging past lets next gc remove it
- Approach: CLI behavior via test suite
- Action run: `bash tests/test_attach_archive_gc.sh`
- Output (trimmed): "fresh orphan within grace is retained", "orphan past grace is swept"
- Verdict: pass

### Item 11 — fold re-bind survives archival
- Item text: folding A (carrying attachment) into B re-binds hash to B in index.json; attachment survives A's deletion at archival (no double-decref)
- Approach: CLI behavior via test suite
- Action run: `bash tests/test_attach_fold_rebind.sh`
- Output (trimmed): "fold rebinds the ref to the primary", "primary frontmatter gains the folded attachment", "folded task file deleted at archival", "blob still referenced by archived primary", "blob survives the folded task's deletion + archival"; dup-hash, name-collision, and transitive-fold variants all covered — 20/20 pass
- Verdict: pass — re-bind recorded in per-blob meta (s/index.json/meta/)

### Item 12 — dedup on second add of same file
- Item text: second add of the SAME file to a different task dedups (same hash, refcount 2, blob written once)
- Approach: CLI behavior via test suite
- Action run: `bash tests/test_attach_local_backend.sh`
- Output (trimmed): "same blob on two tasks -> refs [5,6]"; content-addressed storage + idempotent `attachment_backend_put` ⇒ blob written once
- Verdict: pass

### Item 13 — loud failure on missing blob
- Item text: a hash whose blob is missing from both cache and backend yields a clear error, never a silent placeholder
- Approach: live execution in isolated scratch dir
- Action run: sourced `attachment_{utils,backend,cache}.sh` in a temp dir with `XDG_CACHE_HOME` redirected; called `attachment_resolve` on a valid-format but nonexistent hash
- Output (trimmed): `Error: attachment_resolve: blob not found for sha256:aaaa… (local backend; not in cache or store)`, exit 1 — no placeholder bytes produced. (Harness emitted incidental unbound-var noise from sourcing the local backend without full task_utils; the die path still fired correctly.)
- Verdict: pass

## Cleanup
- Scratch dir `${TMPDIR:-/tmp}/auto_verify_1030_4_*` — removed.
- No tmux sessions created. No real task/plan files mutated other than this task's checklist.
