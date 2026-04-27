---
Task: t676_agent_initializer_output_parsing_failed_created_at.md
Base branch: main
plan_verified: []
---

# Plan: Initializer-bootstrap output rejected because `created_at` is missing (t676)

## Context

In `ait brainstorm` session 635 the user ran the `initializer_bootstrap` agent
(used to import an initial proposal from a file). The agent finished and wrote
its output, but the dashboard banner reported:

> initializer apply failed: initializer node YAML invalid: ['Missing required field: created_at']

The cause is a long-standing prompt/schema disagreement plus a fragile importer:

- The prompt template `.aitask-scripts/brainstorm/templates/initializer.md`
  lists required output fields at lines 27-34 and again in the Phase 3
  walkthrough at lines 107-115. Both lists **omit `created_at`**. The agent
  followed instructions correctly.
- The schema `.aitask-scripts/brainstorm/brainstorm_schemas.py:13-16` lists
  `created_at` as a member of `NODE_REQUIRED_FIELDS`, so `validate_node()`
  rejects the agent's dict.
- The companion server-side path `create_node()` in
  `.aitask-scripts/brainstorm/brainstorm_dag.py:38` already auto-fills
  `created_at = datetime.now().strftime("%Y-%m-%d %H:%M")` when nodes are
  created internally. The initializer apply path does NOT — at line 375 of
  `brainstorm_session.py` it hands the agent's dict directly to
  `validate_node()`.

The user wants both fixes:
1. The agent should be told to write `created_at`.
2. The importer should not crash on a missing `created_at` — it's a system-
   generable timestamp; an LLM forgetting it shouldn't poison the apply.

## Approach

Two small, local changes to the brainstorm package.

### Part 1 — Importer: auto-fill system-generable fields before validation

In `apply_initializer_output()` at `.aitask-scripts/brainstorm/brainstorm_session.py:336-388`,
insert a defensive fill step between the YAML parse (line 362) and
`validate_node` (line 375).

Two fields are defensible to default:

- `created_at` — fill with `datetime.now().strftime("%Y-%m-%d %H:%M")` (the
  same format used by `create_node()` in `brainstorm_dag.py:38` and by
  `br_session.yaml`).
- `created_by_group` — fill with `"bootstrap"`. The initializer is the only
  call site that produces `n000_init`, and the prompt template documents the
  group as the constant `bootstrap` (line 33).

The other `NODE_REQUIRED_FIELDS` (`node_id`, `parents`, `description`,
`proposal_file`) carry semantic content the agent must produce — defaulting
those would mask real failures, so leave them alone.

Inserted block (right after the `if not isinstance(node_data, dict)` check at
line 374, before `validate_node`):

```python
# Auto-fill system-generable fields the agent may forget. created_at is a
# wall-clock timestamp meaningful at apply-time; created_by_group is the
# bootstrap constant. The remaining NODE_REQUIRED_FIELDS carry semantic
# content the agent must supply, so we still let validate_node reject those.
if not node_data.get("created_at"):
    node_data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
if not node_data.get("created_by_group"):
    node_data["created_by_group"] = "bootstrap"
```

`datetime` is already imported at module level (it's used at line 367).

### Part 2 — Initializer prompt template: document `created_at`

Update `.aitask-scripts/brainstorm/templates/initializer.md` so the prompt and
schema agree:

- Required-fields list (lines 27-34): add a bullet
  `` `created_at: "YYYY-MM-DD HH:MM"`: timestamp of the node's creation. ``
- Phase 3 walkthrough (lines 107-115): add the `created_at` bullet alongside
  the other Phase-3 generated fields.

Part 1's auto-fill makes a future drift harmless, but keeping the prompt in
sync removes the trap entirely so the agent does not silently rely on the
auto-fill.

## Files modified

- `.aitask-scripts/brainstorm/brainstorm_session.py` — ~5-line defensive fill
  block in `apply_initializer_output()`.
- `.aitask-scripts/brainstorm/templates/initializer.md` — add `created_at` to
  the two required-fields lists.
- `tests/test_brainstorm_session.py` — new test class (see Verification).

## Files NOT modified

- `.aitask-scripts/brainstorm/brainstorm_schemas.py` — `created_at` stays a
  required field. Auto-filling at apply-time keeps the schema strict while
  making the agent path robust.
- Existing crew worktree `.aitask-crews/crew-brainstorm-635/` — fix is
  forward-only. After the fix lands, the user can re-run
  `ait brainstorm apply-initializer 635` and the missing `created_at` will be
  filled in.

## Verification

### Automated

Extend `tests/test_brainstorm_session.py` with `ApplyInitializerDefaultsTests`:

- Seed a worktree with a complete `initializer_bootstrap_output.md` whose
  NODE_YAML omits `created_at`. Call
  `apply_initializer_output("42")`. Assert it does NOT raise, that
  `br_nodes/n000_init.yaml` is written, and that the on-disk YAML contains a
  `created_at` matching `\d{4}-\d{2}-\d{2} \d{2}:\d{2}`.
- Same setup but omit `created_by_group` → assert auto-fills to `"bootstrap"`.
- Negative: omit `description` (a non-system-generable required field) →
  assert it still raises `ValueError` mentioning "description".

The seeded NODE_YAML must satisfy the rest of `validate_node`'s checks
(`node_id: n000_init`, `parents: []`, `proposal_file:
br_proposals/n000_init.md` so the `node_id in proposal_file` check passes,
plus a valid PROPOSAL block with at least one section so
`validate_sections` is happy).

Run:
```bash
python -m unittest tests.test_brainstorm_session
python -m unittest tests.test_brainstorm_dag
```

### Manual

Re-run on the stuck session 635:
```bash
ait brainstorm apply-initializer 635
```
Should succeed and write
`.aitask-crews/crew-brainstorm-635/br_nodes/n000_init.yaml` with a populated
`created_at`.

## Step 9 — Post-Implementation

Standard cleanup, commit, archive per task-workflow Step 9. No worktree to
remove (working on current branch per `fast` profile).

## Final Implementation Notes

- **Actual work done:**
  - Part 1 (importer auto-fill) — `apply_initializer_output()` in
    `.aitask-scripts/brainstorm/brainstorm_session.py` now auto-fills
    `created_at` (current `YYYY-MM-DD HH:MM`) and `created_by_group`
    (`"bootstrap"`) when the agent's NODE_YAML omits them, before
    `validate_node()` runs. Other required fields still raise.
  - Part 2 (initializer prompt) — `.aitask-scripts/brainstorm/templates/initializer.md`
    now lists `created_at` in both the required-fields list (output
    section) and the Phase 3 walkthrough.
  - Part 3 (companion-agent prompts) — extended scope per user request:
    `.aitask-scripts/brainstorm/templates/explorer.md` and
    `.aitask-scripts/brainstorm/templates/synthesizer.md` had the same
    gap (NODE_YAML lists omitting `created_at`). Both now include
    `created_at` in the required-fields list and the relevant Phase
    walkthrough. Audit of the remaining templates: `patcher.md` emits a
    different delimiter (`METADATA_START/_END`) and copies the parent's
    YAML (which carries `created_at`) in NO_IMPACT mode; `detailer.md`
    emits a plan markdown with no NODE_YAML; `comparator.md` is
    read-only — none of these three are affected.
  - Tests — added `ApplyInitializerDefaultsTests` (4 tests) to
    `tests/test_brainstorm_session.py` covering: missing `created_at`
    auto-fill, missing `created_by_group` defaulting to `"bootstrap"`,
    provided values preserved (no clobber), and missing `description`
    still raising. All 11 tests in the file pass; `tests.test_brainstorm_dag`
    (24 tests) also pass.

- **Deviations from plan:** Scope expanded mid-review to also patch the
  explorer and synthesizer prompts. The runtime auto-fill is still
  scoped to `apply_initializer_output` only — there is currently no
  apply function for explorer/synthesizer outputs, so adding parallel
  auto-fill code would have been speculative.

- **Issues encountered:** None. Tests pass on first run.

- **Key decisions:**
  - Auto-fill only the two genuinely system-generable fields
    (`created_at`, `created_by_group`). Other `NODE_REQUIRED_FIELDS`
    (`node_id`, `parents`, `description`, `proposal_file`) carry
    semantic content the agent must supply — defaulting them would
    mask real errors.
  - Left `created_at` in `NODE_REQUIRED_FIELDS`. Auto-filling at
    apply-time keeps the schema strict (so other code paths that may
    bypass `apply_initializer_output` still get a clear error) while
    making the agent path robust.
  - Did not extract the auto-fill into a shared helper — premature,
    since only one apply function exists today.

- **Upstream defects identified:** None. The bug is local to the
  brainstorm initializer apply path.

