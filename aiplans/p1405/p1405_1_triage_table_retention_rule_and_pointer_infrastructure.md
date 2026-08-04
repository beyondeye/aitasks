---
Task: t1405_1_triage_table_retention_rule_and_pointer_infrastructure.md
Parent Task: aitasks/t1405_triage_agent_memory_store_into_aidocs.md
Sibling Tasks: aitasks/t1405/t1405_2_*.md … aitasks/t1405/t1405_7_*.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
Output branch: main
---

# p1405_1 — Triage table, retention rule, and pointer infrastructure

## Context

The spike child of t1405. It freezes the memory-store inventory, classifies every
entry, and builds the scaffolding (`README.md` manifest, retention-rule doc,
entrypoint appendices, parity guard) that t1405_2..t1405_7 write into. Nothing
downstream can start until the manifest and the triage table exist.

**Read `aiplans/p1405_triage_agent_memory_store_into_aidocs.md` first.** It owns
the per-memory decision gate, the store-concurrency rules and the journal
schema, and they are binding here.

Only `aidocs/`, `CLAUDE.md`, `AGENTS.md`, `.codex/`, `.opencode/`, `.gitignore`
and `tests/` changes are committable. The memory store is outside the repo.

## Steps

### 1. Freeze before reading (do this first, in one shell)

```bash
cd ~/.claude/projects/-home-ddt-Work-aitasks/memory
ls -1 *.md | grep -v '^MEMORY.md$' | sed 's/\.md$//' | sort > /tmp/frozen.txt
printf '%s\n' project_t1224_done_unblocks_t1109 > /tmp/arrivals.txt
grep -vxF -f /tmp/arrivals.txt /tmp/frozen.txt | sha256sum
# expect 84db208094ef3b8997b79efc39c0288d3324475dbe8539ede7bfcc5f2c66207d
```

- Digest matches → `project_t1224_done_unblocks_t1109` is the sole arrival.
- Digest differs → more arrived. Bisect by adding candidates to
  `/tmp/arrivals.txt` (newest `mtime` first) until the digest matches, and
  **name every one** in this plan. Do not proceed on an unexplained delta.

Persist `/tmp/frozen.txt` → `.aitask-memtriage/manifest_names.txt` and
`/tmp/arrivals.txt` → `.aitask-memtriage/post_freeze_arrivals.txt`, plus a
`name / bytes / sha256` table in this plan. Add `.aitask-memtriage/` to
`.gitignore` beside the existing `.aitask-*/` entries.

### 2. Read and classify

Read all manifest memories. Emit the triage table into this plan, with the
machine-readable block
`name<TAB>type<TAB>proposed<TAB>owning-child<TAB>target-doc#heading<TAB>reason`.
Every memory gets exactly one owning child. Destinations are `doc#heading`.

The parent plan's per-child cluster lists are the starting proposal — revise
where a memory clearly belongs elsewhere, but never leave one unassigned.

### 3. Verify the DISCARD candidates

`aitask_query_files.sh task-status <id>` (archived resolves to `Done`) and
`archived-task <id>` (searches the `_b*/old*.tar.zst` bundles). **Do not** use
`archived-children` — it does not look inside the bundles.

The task description carries the seven verdicts already established. Re-confirm
them; do not re-derive from scratch.

### 4. Build the scaffolding

- `aidocs/framework/README.md` — manifest with the **entrypoint-advertised** /
  **reachable-only** split.
- `aidocs/framework/agent_memory_conventions.md` — the retention rule plus the
  new-file-vs-new-`##`-section rule.
- `## Specialist rules (aidocs/framework)` appendix appended **after** the
  closing `<<<aitasks` marker in `AGENTS.md`, `.codex/instructions.md`,
  `.opencode/instructions.md`. Never inside the markers; never in the seed.
- `CLAUDE.md` — triggers for the new docs; widen the `testing_conventions.md`
  trigger before t1405_2 lands ~25 general testing rules under it.

### 5. The parity guard

`tests/test_aidocs_pointer_parity.sh` with the three assertions from the task
description, plus a negative control that removes one entrypoint-advertised
doc's pointer from one appendix and must exit 1 **naming that doc**.

Write the negative control as a separate runnable step, not a comment — an
unrun negative control proves nothing.

### 6. Rule on the DISCARD candidates and execute

The parent plan's three-phase gate. Journal to `.aitask-memtriage/t1405_1.tsv`
before mutating; flip `state` to `done` after.

## Verification

```bash
bash tests/test_aidocs_pointer_parity.sh          # passes
bash tests/test_agent_instructions.sh             # T21 marker survival
grep -c "aidocs/framework" AGENTS.md              # no longer 0
./ait setup && git diff --stat AGENTS.md .codex/instructions.md .opencode/instructions.md
```

The last one is the load-bearing check: the appendices must survive `ait setup`
regenerating the marker blocks.

## Risk

### Code-health risk: medium
- Pointers land inside the `>>>aitasks` markers or in the seed and are destroyed
  on the next `ait setup` / dangle in every bootstrapped project · severity:
  high · → mitigation: append after `<<<aitasks` only, and the `./ait setup`
  diff above is a required verification step
- The parity guard's reach is narrower or broader than the drift · severity:
  medium · → mitigation: it checks a two-list manifest, not a blanket rule, and
  ships with a discriminating negative control

### Goal-achievement risk: medium
- The manifest is frozen after further arrivals, making "every memory
  classified" unprovable · severity: high · → mitigation: the pinned
  `sha256 84db2080…` baseline plus explicit bisection of any unexplained delta
- A memory is left unassigned and silently falls between two clusters ·
  severity: high · → mitigation: the machine-readable table assigns exactly one
  owning child per memory, and t1405_7 diffs executed dispositions against it

### Planned mitigations
None as separate tasks — each mitigation is an in-scope step above.
