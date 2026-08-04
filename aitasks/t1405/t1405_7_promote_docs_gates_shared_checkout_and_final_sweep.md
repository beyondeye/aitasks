---
priority: high
effort: high
depends: [t1405_6]
issue_type: documentation
status: Ready
labels: [documentation, docs]
gates: [risk_evaluated]
anchor: 1405
created_at: 2026-08-04 13:47
updated_at: 2026-08-04 13:47
---

## Context

Seventh and final child of t1405. Promotes the last three clusters (~22
memories) and then runs the **store-wide acceptance sweep** that closes the
whole task.

Read first:
1. `aiplans/p1405_triage_agent_memory_store_into_aidocs.md` — the parent plan.
   It owns the per-memory decision gate, the store-concurrency rules, the
   journal schema, the size-ceiling ladder and the full acceptance script.
   Binding here; do not re-derive.
2. `aiplans/archived/p1405/p1405_1_*.md` — the frozen manifest, the pinned 148
   baseline, and the named post-freeze arrivals.
3. The archived plans of t1405_2..t1405_6 — their journals carry the
   `doc#heading` destinations this child needs for the wikilink rewrite.

The store is outside the repo, so its deletions and `MEMORY.md` rewrite appear
in no git diff — say so in the Final Implementation Notes.

## Part A — promotions

### -> `aidocs/framework/documentation_conventions.md` (~9)

Document the current implementation / skill source of truth, not the archived
design plan (which drifts); prefer a cross-referenced convention doc over an
AST/source-scanning guard whose reach is narrower than the drift it claims to
prevent; when documenting a guard, marker or precedence chain, enumerate the
cases — a one-line summary silently over-claims; after changing approach
mid-task, re-grep every doc and comment already edited, because earlier edits go
stale silently; user-facing docs use generic placeholder project names, never the
author's actual repos; never use "sister repo" wording — say "cross-repo" or
"linked repo/project", and scrub it on touch; artifacts generated FOR users
follow generic installed/configurable conventions, never framework-internal ones;
`website/content/docs/workflows/_index.md` is a hand-curated page list, so a new
workflow page needs a hand-added bullet; operational chat-platform setup steps
belong in `aidocs/chat/`.

Note this doc's preamble currently scopes it to **user-facing** prose. If these
additions widen that scope, update the preamble in the same edit rather than
leaving it contradicted.

### -> `aidocs/gates/` (4)

The directory already exists — extend the right file there rather than minting a
new one. Converting a planning-time pseudo-gate to a framework gate: the gate is
only the verify-time checker, so declaration must keep the planning-time producer
alive; conversions keep the legacy inline procedure as a sentinel-gated fallback,
whose removal is a separate follow-up; the `risk_evaluated` gate needs H3
`### Code-health risk` subsections and has `max_retries 0`, so recovery means
invoking `aitask_gate_risk.sh` directly; `docs_updated` runs an agent doc-update
procedure, NOT a heuristic "do docs need updating?" checker.

### -> NEW `aidocs/framework/concurrent_agent_sessions.md` (9)

Git/worktree hazards of running parallel agent sessions in one shared checkout.
The five `project_concurrent_*` memories **MERGE** into one coherent doc — the
shared `aitask-data` branch has concurrent writers and can sweep your uncommitted
edits into another session's commit; a concurrent session may leave unrelated
work pre-staged in the main-branch index, so stage your own paths explicitly; a
concurrently-edited file can gain another session's hunks between your diff check
and your `git add`, so verify staged CONTENT not just the path; a concurrent
session can rewrite a commit and drop your paths, leaving a task archived Done
with content absent from main; a concurrent agent may `git stash` your unstaged
edits mid-flight, so isolate implementation in an `aiwork/` worktree.

Plus: main HEAD advances mid-session, so re-read source before finalizing a long
plan; a `cp -a` copy of an ait-managed project keeps absolute `.git/worktrees`
gitdir pointers, so commits in the copy land in and push from the ORIGINAL repo;
`ait git push` and `task_sync` can exit 0 having done nothing on divergence; in a
shared checkout `git revert` undoes the working tree too, so reverting a commit
that swept in another session's uncommitted edits deletes those edits (use
`reset --mixed`).

This doc is framework-level, not operator-level: the framework spawns parallel
agents by design. Add it to `aidocs/framework/README.md`'s
**entrypoint-advertised** list and give it a trigger in `CLAUDE.md` **and** all
three out-of-marker appendices, or `tests/test_aidocs_pointer_parity.sh` fails.

## Part B — the final store sweep

1. **Account for every manifest memory.** Diff the executed dispositions against
   the `ruled` column across all seven child journals. Every manifest entry must
   carry an explicit user ruling; anything unruled is **reported, not guessed
   at**. Post-freeze arrivals are listed separately as out of scope.
2. **Rewrite dangling `[[wikilinks]]`.** 140 of 149 files carried wikilinks with
   82 distinct targets, so mass deletion strands links that recall follows.
   Replace each link to a promoted/merged memory with its journalled
   `doc#heading` destination — the exact absorbing section, never a bare
   filename — and clear the 3 links already dangling before the task started.
   Then verify every rewritten destination **resolves** (file exists AND the
   heading is present).
3. **Regenerate `MEMORY.md` from disk truth** (`ls *.md`), never from a
   remembered list: one line per surviving file, no orphans in either direction.
   For the <=10 KB criterion follow the parent plan's **three-step ladder** —
   measure, then hook-compaction (deletes nothing, overrides no ruling), then an
   explicit user choice between amending the ceiling and re-ruling. A KEEP ruling
   is never overridden to hit a size target, and the task does not end silently
   over; an approved override is recorded as
   `.aitask-memtriage/size_override_approved`.
4. **Run the acceptance script.** Write the parent plan's assertion script
   verbatim to `.aitask-memtriage/t1405_accept.sh`. It must exit non-zero on any
   mismatch — printing a diagnostic and returning 0 is the exact failure this
   task is guarding against.

**Prove the checker can fail before trusting it**, one mutation per run, driven
through the `T1405_STORE` / `T1405_JOURNAL` / `T1405_REPO` env overrides against
throwaway fixture copies. Never copy the repo — every mutation lands in the
fixture store or fixture journal, so the `cp -a` worktree-pointer hazard never
arises. Six runs: a clean baseline that must exit 0, then one each for a deleted
index line, a stranded wikilink, a journal row left `state=ruled`, a corrupted
PROMOTE excerpt, and a missing journal row. Each must exit 1 **naming that
specific mutation** — a negative control that passes means the check is wrong,
not the store.

## Key files

- `aidocs/framework/documentation_conventions.md`, `aidocs/gates/*`,
  `aidocs/framework/concurrent_agent_sessions.md` (NEW),
  `aidocs/framework/README.md`, `CLAUDE.md`, `AGENTS.md`,
  `.codex/instructions.md`, `.opencode/instructions.md`
- `.aitask-memtriage/t1405_7.tsv`, `.aitask-memtriage/t1405_accept.sh`

## Verification

- `bash .aitask-memtriage/t1405_accept.sh` prints `t1405 ACCEPTANCE: PASSED` and
  exits 0, with all six negative-control runs having exited 1 as specified.
- `bash tests/test_aidocs_pointer_parity.sh` and
  `bash tests/test_agent_instructions.sh` both pass.
- `./ait setup` then `git diff --stat AGENTS.md .codex/instructions.md
  .opencode/instructions.md` — the appendices survive regeneration.
