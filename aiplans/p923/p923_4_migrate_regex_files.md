---
Task: t923_4_migrate_regex_files.md
Parent Task: aitasks/t923_consolidate_test_assert_helpers_shared_lib.md
Sibling Tasks: aitasks/t923/t923_1_*.md, aitasks/t923/t923_2_*.md, aitasks/t923/t923_3_*.md, aitasks/t923/t923_5_*.md
Archived Sibling Plans: aiplans/archived/p923/p923_1_*.md, aiplans/archived/p923/p923_3_*.md
Base branch: main
---

# Plan: Migrate regex (`grep -q` / `grep -qE`) files (t923_4)

Depends on 923_1/923_2/923_3. **Read 923_1's plan for the API/recipe and 923_3's
notes for the needle-audit pattern.**

These files' inline `assert_contains` uses plain `grep -q` (case-sensitive
**regex**) or `grep -qE`. Call sites map to the shared **`assert_contains_re` /
`assert_not_contains_re`** (`grep -qE`) — unless a needle audit shows no regex
metacharacters are used (then fixed-string default is equivalent).

## Step 1 — Regenerate the file list + classify the 3 manual files

923_1's bucketing command, REGEX bucket (~27 files: plain `-q`, `-qE`). Plus 3
files the auto-bucketer could not classify (their `assert_contains` grep line
was ambiguous): **`test_add_model.sh`, `test_update_multiline_yaml.sh`,
`test_yaml_utils.sh`** — open each, read the real `assert_contains` body, and
classify by hand (fixed / ci / regex) before migrating.

## Step 2 — Migrate in verified batches

1. `snapshot` baseline.
2. Per file: source `asserts.sh`, delete shared inline defs, keep `PASS/FAIL/TOTAL`.
3. **Needle audit + remap** per call:
   - Needle uses regex metacharacters (`. * [ ] ^ $ \ ( ) | + ?`) as regex →
     `assert_contains_re` / `assert_not_contains_re`.
   - Plain literal needle → fixed-string default is equivalent; may stay on
     `assert_contains`. **Caution:** a literal like `t42.md` under plain `-q`
     was technically regex but almost always intended literally — fixed-string
     is MORE correct there. Only keep `_re` for genuine regex (anchors,
     classes, alternation).
4. `check` — counts MUST match. A delta means a metacharacter mattered → `_re`
   (or a latent test bug; note it).
5. `shellcheck` sample; commit batch (plain `git`).

## Step 3 — Verify

- Standalone counts identical before vs after.
- The 3 manual files correctly classified and migrated.
- No remaining inline regex `assert_contains` defs in migrated files.
- `shellcheck` clean on a sample.

## Final Implementation Notes (fill in)

Classification of the 3 manual files; any genuine-regex needle; latent bugs
surfaced (→ "Upstream defects identified").

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
