---
Task: t1866_register_codex_gpt6_models_and_promote_sol_default.md
Base branch: main
Output branch: main
---

# t1866 — Register Codex GPT-6 Sol/Luna, promote Sol for shadow/discuss

## Context

Codex CLI shipped GPT-6 Sol (`gpt-6-sol`) and GPT-6 Luna (`gpt-6-luna`). They
need registry entries, and Sol takes over the `shadow` / `discuss` defaults
from `codex/gpt5_6_terra` (metadata config) and from `claudecode/opus5` (seed
config, per the requester's explicit instruction). Terra stays registered.
OpenCode is out of scope (t1867).

**Concurrency (re-verified after review).** t1865 (opus5_5 promotion, live
pid 1509436) was editing three of the same files. It has since **committed**
them — data branch `af1ea3f98`, main `ff667f89e` + `915cb836c` — and all six
of my target paths are clean vs HEAD. t1865 has recorded `review_approved`;
its only remaining work (Step 9 archival) touches task/plan files, not these.
The handoff is therefore "t1865 committed first", enforced below as an
explicit precondition plus write- and commit-time guards, not assumed.

Target paths:
- main: `seed/models_codex.json`, `seed/codeagent_config.json`,
  `website/content/docs/commands/codeagent.md`, `tests/lib/codeagent_defaults.sh`
- data (`aitask-data` branch, `.aitask-data` worktree):
  `aitasks/metadata/models_codex.json`, `aitasks/metadata/codeagent_config.json`

## Steps

1. **Handoff barrier (precondition).** Immediately before any write:
   `git status --porcelain -- <main paths>` and
   `./ait git status --porcelain -- <data paths>` must both be empty. If any
   path is dirty, a concurrent session is mid-edit: **stop and wait** (poll
   with Monitor until clean / its commit lands), or ask the user — never
   write over it. Then record `sha256sum` of all six files + `HEAD` of both
   branches as the base snapshot, and build the **expected** after-state of
   each file in scratchpad from those base copies (apply the same helper
   commands with `AITASK_REPO_ROOT` pointed at a scratch copy, plus the two
   hand edits).

2. **Register models** in the real tree via `.aitask-scripts/aitask_add_model.sh`
   (dry-runs already reviewed; each call appends to both models_codex.json files):
   - `add-json --agent codex --name gpt6_sol --cli-id gpt-6-sol --notes "Flagship GPT-6 model for the most demanding coding, agentic, and research work"`
   - `add-json --agent codex --name gpt6_luna --cli-id gpt-6-luna --notes "Fast and affordable GPT-6 model for clear, repeatable coding tasks and high-volume workflows"`

3. **Promote Sol**: `promote-config --agent codex --name gpt6_sol --ops shadow,discuss`
   (dry-run showed exactly 4 value changes). Do NOT run
   `promote-default-agent-string` (claudecode-only).

4. **Hand edits**: codeagent.md `shadow`/`discuss` rows → `codex/gpt6_sol`;
   `tests/lib/codeagent_defaults.sh:107` comment
   "defaults.shadow is codex/gpt5_6_terra today" → `codex/gpt6_sol`.

5. **Write guard.** Each of the six files must now byte-equal its expected
   after-state from step 1 (`cmp`). Any mismatch means an interleaved foreign
   write → stop, report, do not commit.

6. **Commits — plain path-scoped, only my paths** (no foreign hunks exist once
   step 5 passes; re-run the step-5 `cmp` immediately before each commit):
   - main: `git commit -o -m "enhancement: Register Codex GPT-6 Sol/Luna and promote Sol for shadow/discuss (t1866)" -- <4 main paths>`
     (body notes the seed behaviour change: fresh projects now default
     shadow/discuss to codex/gpt6_sol).
   - data: `./.aitask-scripts/aitask_task_commit.sh -m "ait: Register Codex GPT-6 models and promote Sol for shadow/discuss (t1866)" aitasks/metadata/models_codex.json aitasks/metadata/codeagent_config.json`
     — the framework's path-scoped `commit -o` helper for the aitask-data
     branch; expect `COMMITTED:2:…`, any `SKIPPED`/`REFUSED`/`FAILED` is a failure.

## Verification — against committed revisions, not live files

- Record `M=$(git rev-parse HEAD)` and `D=$(./ait git rev-parse HEAD)` right
  after the commits; confirm `./ait git rev-parse --abbrev-ref HEAD` = `aitask-data`
  and each commit's `--name-only` list is exactly my paths.
- `./ait git show $D:aitasks/metadata/models_codex.json | jq -r '.models[].name'`
  includes `gpt6_sol`, `gpt6_luna`; `…$D:aitasks/metadata/codeagent_config.json | jq -r '.defaults.shadow,.defaults.discuss'` → `codex/gpt6_sol` ×2; other defaults equal `$D^`'s.
- Same for `git show $M:seed/models_codex.json` / `$M:seed/codeagent_config.json`, and
  `git show $M:website/…/codeagent.md | grep gpt6_sol` (2 rows).
- Post-commit: `git status --porcelain` / `./ait git status --porcelain` for my
  paths empty (nothing left only in the worktree).
- Behaviour: `./.aitask-scripts/aitask_codeagent.sh resolve shadow|discuss` →
  `AGENT_STRING:codex/gpt6_sol`, `CLI_ID:gpt-6-sol`.
- Tests: `bash tests/test_add_model.sh`, `tests/test_codeagent_discuss.sh`,
  `tests/test_shadow_spawn_learner.sh`, `tests/test_codeagent.sh`;
  `bash tests/run_all_python_tests.sh` (last-line verdict);
  `cd website && python3 check_links.py --build`.

## Step 9

Post-implementation per task-workflow Step 9 (current-branch mode: no merge;
archive task + plan).

## Risk

### Code-health risk: low
- Concurrent t1865 session edited the same files; interleaved read-modify-write could lose a hunk or a commit could sweep foreign hunks · severity: medium · → mitigation: inline pre-phase handoff-barrier (step 1) + write guard (step 5) + commit-time re-check (step 6)
- Seed change alters shadow/discuss defaults for freshly seeded projects (needs codex CLI) · severity: low · → mitigation: explicit requester decision; called out in commit body

### Goal-achievement risk: low
- Data-branch edits could remain only in the dirty worktree or land on the wrong ref while live-file checks pass · severity: medium · → mitigation: inline post-phase committed-revision verification (Verification section)
- Model notes text written by analogy with the 5.6 tiers, not from a vendor description · severity: low · → mitigation: TBD (flagged in final summary)

## Final Implementation Notes
- **Actual work done:** Registered `codex/gpt6_sol` (`gpt-6-sol`) and `codex/gpt6_luna` (`gpt-6-luna`) in `aitasks/metadata/models_codex.json` + `seed/models_codex.json` via `aitask_add_model.sh add-json`; promoted `codex/gpt6_sol` for `shadow`/`discuss` in both `aitasks/metadata/codeagent_config.json` (from terra) and `seed/codeagent_config.json` (from `claudecode/opus5`) via `promote-config`; updated the two default rows in `website/content/docs/commands/codeagent.md` and the stale comment in `tests/lib/codeagent_defaults.sh`.
- **Deviations from plan:** `tests/test_codeagent_discuss.sh` added to the main commit. Its Test 1 / Test 4 claudecode cases relied on the *seeded* `discuss` default being a claudecode model; the seed flip made 3 assertions fail. The claudecode cases now pin `--agent-string claudecode/opus5` (as Tests 2/3 already pin codex/opencode), and a new Test 1a keeps the agent-agnostic "invoke carries the resolved default cli_id" contract on an unpinned call. The original temp-index commit technique was dropped after review: t1865 had committed its hunks in the shared files before implementation, so a handoff barrier + write guard + plain path-scoped commits suffice.
- **Issues encountered:** Review flagged that a temp index isolates commit content but not concurrent read-modify-write; resolved with the step-1 barrier (clean status + sha256 snapshot, re-checked immediately before writing) and a byte-exact `cmp` write guard against an expected state built in a scratch copy with `AITASK_REPO_ROOT`.
- **Key decisions:** Model notes follow the existing 5.6 Sol (flagship) / Luna (fast, affordable) tier wording — not taken from a vendor description.
- **Upstream defects identified:** None
