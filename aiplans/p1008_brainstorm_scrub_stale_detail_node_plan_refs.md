---
Task: t1008_brainstorm_scrub_stale_detail_node_plan_refs.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: Scrub stale "Detail" / node-plan references from brainstorm

## Context

Plans were removed from the brainstorm engine at the node level (t891 —
brainstorm is now grep-clean of the `br_plans` / `plan_file` literals, and
`finalize` exports the HEAD node's *proposal* directly to `aiplans/`). There is
no longer a **"Detail" operation** — the op registry is only `explore`,
`compare`, `synthesize`, `finalize`, `module_decompose`/`merge`/`sync`,
`freeze`.

The t891 cleanup removed the literal tokens but left three **prose / help-text**
references that wrongly imply a node-level plan-derivation step (via a
non-existent "Detail" op) still exists. These actively mislead readers — they
misled an exploration session into citing a "Detail → derive a plan" stage that
does not exist. The corrected first-operation flow on a blank-initialized
session is **Explore → Compare → Synthesize → Finalize** (no Detail, no
node-plan stage).

This task removes the three stale references and leaves the legitimate plan
references (finalize→aiplans export; module_sync's *linked external task* plan)
untouched.

## Changes

### 1. `.aitask-scripts/brainstorm/brainstorm_app.py` — `explore` op `produces` list

Line 275, inside the `"explore"` op's `"produces"` list. Remove the entire
dangling clause:

```python
            "A new proposal markdown.",
            "No plan — use Detail later to derive a plan from this proposal.",   # ← DELETE this line
        ],
```

The op already correctly states it produces "A new proposal markdown." — just
drop the `"No plan — use Detail later ..."` entry. No other line in the dict
changes.

### 2. `.aitask-scripts/brainstorm/templates/explorer.md` — Input contract (line 13)

Remove input item 4 ("Baseline node's plan path") and renumber the trailing
items:

```
3. The baseline node's proposal Markdown path (full architectural narrative)
4. Baseline node's plan path (if one exists)        ← DELETE
5. Reference files: local file paths and cached URL paths
6. Active dimensions from br_graph_state.yaml
```

becomes:

```
3. The baseline node's proposal Markdown path (full architectural narrative)
4. Reference files: local file paths and cached URL paths
5. Active dimensions from br_graph_state.yaml
```

### 3. `.aitask-scripts/brainstorm/templates/explorer.md` — Phase 1 instructions (line 129)

Remove the baseline-plan read step:

```
- Read the baseline node proposal Markdown file (path provided in input)
- If a baseline plan exists, read it for additional context        ← DELETE
- Read the reference files listed in the baseline node's `reference_files` field
```

## Out of scope (deliberately NOT changed)

- **Legitimate plan references kept:**
  - `finalize` op help + proposal → `aiplans/` export (`brainstorm_app.py`,
    `brainstorm_cli.py`) — the real proposal-to-plan handoff.
  - `module_sync` / `_resolve_linked_plan_path` (`brainstorm_crew.py` ~L815,
    ~L937) + `module_syncer.md` "Linked Task Plan" — reads the **linked external
    task's** `aiplans/` plan as sync context, not a brainstorm node plan.
  - `module_decomposer.md` "## Decomposition Plan" — a user-supplied steering
    section name, unrelated to node plans.
- **`compare`-op "plans" negation left as-is** (`brainstorm_app.py` compare op
  help + `comparator.md:15` "do not read proposals, plans, or codebase files").
  These are *negations* telling the agent what NOT to read; they are harmless
  and removing "plans" would be cosmetic only. Decision: keep, to hold blast
  radius to the genuinely-misleading references.
- Website / user-facing brainstorm docs — covered separately (t929_3 / doc
  tasks).

## Verification

1. **No stale Detail-operation reference remains** (UI "node detail" /
   "operation detail" screens are unrelated and must stay):
   ```bash
   grep -rin 'use Detail\|derive a plan' .aitask-scripts/brainstorm/*.py \
     .aitask-scripts/brainstorm/templates/*.md
   ```
   Expect: no matches.

2. **Explorer template no longer references a node plan:**
   ```bash
   grep -n 'plan' .aitask-scripts/brainstorm/templates/explorer.md
   ```
   Expect: no matches (the only two were lines 13 and 129).

3. **Explorer Input items renumbered correctly** — read lines 9–15 of
   `explorer.md`; items run 1–5 with no gap.

4. **Brainstorm module imports cleanly** (no syntax slip in the edited dict):
   ```bash
   .venv-pypy/bin/python -c "import sys; sys.path.insert(0,'.aitask-scripts'); import brainstorm.brainstorm_app" \
     || python3 -c "import sys; sys.path.insert(0,'.aitask-scripts'); import ast; ast.parse(open('.aitask-scripts/brainstorm/brainstorm_app.py').read())"
   ```
   (At minimum, `ast.parse` must succeed — the edit only removes a list element.)

5. **Legitimate references untouched:**
   ```bash
   grep -rin 'aiplans\|Linked Task Plan\|Decomposition Plan' \
     .aitask-scripts/brainstorm/templates/*.md .aitask-scripts/brainstorm/*.py | head
   ```
   Expect: finalize/aiplans, module_syncer "Linked Task Plan", and
   module_decomposer "Decomposition Plan" still present.

6. **Skill/template surface sanity** (template change, no skill `.j2` goldens
   expected, but run to be safe):
   ```bash
   ./.aitask-scripts/aitask_skill_verify.sh
   ```

## Step 9 (Post-Implementation)

Per task-workflow: review → commit (chore type) → archive t1008. Profile 'fast'
works on the current branch (no worktree/merge step). Commit message:
`chore: Scrub stale Detail/node-plan refs from brainstorm (t1008)`.

## Risk

Two dimensions assessed separately.

- **Code-health risk: low.** The change deletes three documentation/help-text
  lines (one Python list element, two markdown lines) and renumbers a markdown
  list. No control flow, no data structures, no public interfaces. The Python
  edit removes one string element from a display-only `produces` list consumed
  by the operation-help modal; nothing parses its contents. The template edits
  touch agent-facing prose describing inputs that no longer exist, so they
  *increase* doc/runtime fidelity.

- **Goal-achievement risk: low.** The goal — remove the misleading Detail/
  node-plan references — is fully and unambiguously met by the three edits, and
  is mechanically verifiable by grep (Verification 1–2). The only judgment call
  (whether to also soften the `compare`-op "plans" negation) is explicitly
  resolved in-plan as "leave as-is", so there is no open scope ambiguity.

No mitigations planned (before/after) — the change is too small and self-
verifying to warrant follow-up tasks.
