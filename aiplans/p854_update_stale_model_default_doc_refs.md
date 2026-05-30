---
Task: t854_update_stale_model_default_doc_refs.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Plan: Update stale model-default doc references (t854)

## Context

t853 promoted `claudecode/opus4_8` to be the framework default (commit
`80ba0e13`). The `aitask-add-model` skill automatically patched the files it
owns — `lib/agent_string.sh` (`DEFAULT_AGENT_STRING`),
`aitask_codeagent.sh:540` (hardcoded-default help note),
`codeagent_config.json` + seed — all already on `opus4_8` (verified).

But the skill's `emit-manual-review` list deliberately leaves a set of
files **out of scope**: the asof-today tools doc, the website command doc's
defaults table / hardcoded-default line, and default-sensitive test fixtures.
Those still reference the old `opus4_7_1m` default. This task closes that gap.

The authoritative map is `aidocs/model_reference_locations.md` (tags
`needed_for_promote`). New default values:
- agent string: `claudecode/opus4_8` (no `_1m` suffix — 1M context is now the
  model's default)
- cli_id: `claude-opus-4-8` (no `[1m]` suffix)
- model name: `opus4_8`

## Scope decision (what's in vs out)

Per the task and the audit, update **only** `needed_for_promote` locations.
Leave `informational_only` format-illustration examples untouched.

**Reconciliation findings (verified by running the tests):**
- `tests/test_agent_string.sh` — **already passes (12/12); no change needed.**
  Its `opus4_7_1m` references (lines 45-46 parse test, line 93
  `get_cli_model_id`) are incidental fixtures for a *still-registered* model,
  not default assertions. Test 13 (`DEFAULT_AGENT_STRING`) only asserts
  non-empty / contains `/` — value-agnostic. Listed in the task but there is
  no default-value assertion to reconcile.
- `tests/test_brainstorm_crew.py` — **already passes (38/38).** Its
  `FULL_DEFAULTS` is a self-written temp-config fixture asserted against
  itself, so it passes regardless. Still updating the brainstorm fixture
  values to keep them representative of the real config (audit tags them
  `needed_for_promote`).
- `tests/test_codeagent.sh` — **4 genuine failures** in the default-resolution
  assertions; these are the real work.

## Files to modify

### 1. `aidocs/claudecode_tools.md` (line 5)
```
**Model:** Claude Opus 4.7 (`claude-opus-4-7`)
```
→
```
**Model:** Claude Opus 4.8 (`claude-opus-4-8`)
```

### 2. `website/content/docs/commands/codeagent.md` (3 edits)
Only the **defaults table** rows that show the real default, and the
**hardcoded-default** line:
- Line 53: `pick` row `claudecode/opus4_7_1m` → `claudecode/opus4_8`
- Line 55: `explore` row `claudecode/opus4_7_1m` → `claudecode/opus4_8`
- Line 169: `4. **Hardcoded default** -- \`claudecode/opus4_7_1m\`` →
  `claudecode/opus4_8`

**Left as-is (informational_only format examples, per audit + task):**
the `resolve` output example (lines 105-108), the `list-models` example
(line 89, `opus4_6`), the project-config JSON example (line 178), and the
Model Configuration JSON example (line 210). State-current-only rule applies
to the *default-declaring* lines, which are the three above.

### 3. `tests/test_codeagent.sh` (5 edits, Test 5 + Test 11)
- Line 156 comment: `opus4_7_1m (current default)` → `opus4_8 (current default)`
- Line 159: `AGENT_STRING:claudecode/opus4_7_1m` → `AGENT_STRING:claudecode/opus4_8`
  (+ label text `opus4_7_1m` → `opus4_8`)
- Line 161: `MODEL:opus4_7_1m` → `MODEL:opus4_8`
- Line 162: `CLI_ID:claude-opus-4-7\[1m\]` → `CLI_ID:claude-opus-4-8`
  (drop the escaped `\[1m\]` — new cli_id has no bracket suffix)
- Line 211: `claude-opus-4-7` → `claude-opus-4-8`

Lines 143-147 (`list-models` shows opus4_6/opus4_7/opus4_7_1m) stay — those
models are still registered; the assertions are not default-sensitive and
already pass.

### 4. `tests/test_brainstorm_crew.py` (fixtures → representative)
Update the `opus4_7_1m` brainstorm-default fixtures to `opus4_8` so they
mirror the real `codeagent_config.json`:
- Line 378 `brainstorm-explorer` → `claudecode/opus4_8`
- Line 380 `brainstorm-synthesizer` → `claudecode/opus4_8`
- Line 381 `brainstorm-detailer` → `claudecode/opus4_8`
- Line 446 `"pick"` fixture → `claudecode/opus4_8`
- Line 494 assertion `result["explorer"]["agent_string"]` → `claudecode/opus4_8`
  (must match line 378)

(`comparator`/`patcher`/`initializer` = `sonnet4_6` already correct.)

## Doc-writing rule compliance (CLAUDE.md)

State Opus 4.8 positively. No "previously the default was Opus 4.7" /
version-history prose anywhere in the edits.

## Verification

```bash
bash tests/test_codeagent.sh          # expect PASS 87/87 (was 83/87)
bash tests/test_agent_string.sh       # expect unchanged PASS 12/12
python tests/test_brainstorm_crew.py  # expect unchanged OK 38/38
cd website && hugo build --gc --minify  # must succeed
```

Final grep — no `needed_for_promote` location still points at the old default:
```bash
grep -n "opus4_7" aidocs/claudecode_tools.md \
  website/content/docs/commands/codeagent.md   # only informational example lines remain
```

## Step 9 (Post-Implementation)

Working on `main` directly (no worktree). After review/commit: archive via
`./.aitask-scripts/aitask_archive.sh 854`, then `./ait git push`. No linked
issue/PR expected. Changelog/blog announcement is explicitly out of scope
(handled via `/aitask-changelog` at release time per task note).

## Final Implementation Notes

- **Actual work done:** Updated 4 files to the new `claudecode/opus4_8` default
  promoted by t853:
  - `aidocs/claudecode_tools.md:5` — `Claude Opus 4.7 (claude-opus-4-7)` →
    `Claude Opus 4.8 (claude-opus-4-8)`.
  - `website/content/docs/commands/codeagent.md` — defaults-table `pick` &
    `explore` rows (53, 55) and the hardcoded-default line (169) →
    `claudecode/opus4_8`.
  - `tests/test_codeagent.sh` — Test 5 resolve-pick assertions (agent string,
    model, cli_id) and Test 11 dry-run model-flag assertion → opus4_8 /
    `claude-opus-4-8` (dropped the `\[1m\]` cli_id suffix; the new default has
    no bracket suffix since 1M context is the model default).
  - `tests/test_brainstorm_crew.py` — `FULL_DEFAULTS` explorer/synthesizer/
    detailer fixtures, the `pick` ignored-key fixture, and the
    `test_launch_mode_does_not_clobber_agent_string` assertion → opus4_8.
- **Deviations from plan:** None. Scope held exactly to the plan.
- **Issues encountered:** None.
- **Key decisions:**
  - `tests/test_agent_string.sh` was listed in the task but needed **no
    change** — it already passes (12/12). Its `opus4_7_1m` refs are incidental
    parse / `get_cli_model_id` fixtures for a still-registered model; Test 13
    asserts `DEFAULT_AGENT_STRING` is non-empty/contains `/` only (value-
    agnostic). Reconciled, not duplicated.
  - `tests/test_brainstorm_crew.py` already passed (self-written temp-config
    fixtures asserted against themselves). Fixtures were still updated to stay
    representative of the real `codeagent_config.json` (audit tags them
    `needed_for_promote`).
  - Left the `resolve pick` output example (codeagent.md:105-108) and the
    project-config JSON example (line 178) on `opus4_7_1m` per the audit's
    `informational_only` tag and the task's explicit "leave those" instruction.
- **Upstream defects identified:** None. (Note, not a defect: leaving the
  `resolve pick` example on opus4_7_1m while the defaults table two lines up
  reads opus4_8 is a minor in-doc inconsistency, intentionally left per the
  audit scoping. Could be a small future doc-polish task if the project wants
  the format examples to also track the live default — surfaced to the user at
  Step 8 review; not pursued here.)
