---
Task: t1884_agent_string_fallback_rejected_by_parser.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1884 — Make AGENT_STRING_FALLBACK parseable; register claude-opus-5-5[1m]

## Context

`aitask_resolve_detected_agent.sh` emits `AGENT_STRING_FALLBACK:<agent>/<raw cli_id>`
for an unregistered model id, e.g. `claudecode/claude-opus-5-5[1m]`. All three
`parse_agent_string` copies accept only `^([a-z]+)/([a-z0-9_]+)$`:
- `lib/agent_string.sh:50`
- `aitask_usage_update.sh:82`
- `aitask_verified_update.sh:87`

A raw cli_id always contains `-`, so every fallback string is rejected. As a result:
- `ait codeagent coauthor` dies, and the Step 8 commit loses its code-agent trailer.
- `implemented_with` gets a string that no later consumer can parse.
- Usage and verified updates die on a format error.

The 1M-context Opus 5.5 id, `claude-opus-5-5[1m]`, is not in the registry. A session
running on it therefore always takes the fallback path.

## Approach

Normalise the fallback into the parser's grammar, inside a **reserved `unregistered_`
namespace**, so a fallback can never equal a registered name. Plain normalisation would
collide: `opus5-5` would become `opus5_5`, which is registered as Opus 5.5.

The reservation is enforced **at every writer of registry names**. It is not enforced by
rejecting names at consumer time. So a name that is validly registered is never refused,
and a fallback can never resolve to a registered row. There are three writers:
- `aitask_add_model.sh add-json`
- `aitask_opencode_models.sh`, the OpenCode discovery writer
- the agent-authored JSON write in the `aitask-refresh-code-models` skill

### 1. `.aitask-scripts/aitask_resolve_detected_agent.sh`
Add `fallback_model_name()` and use it at both fallback sites (lines 76 and 97). The
function applies these rules in order:
1. Lowercase the id.
2. Turn each run of characters outside `[a-z0-9]` into a single `_`.
3. Trim leading and trailing `_`.
4. Use `unknown` if nothing is left.
5. Prefix the result with `unregistered_`.

With these rules, `claude-opus-5-5[1m]` becomes `claudecode/unregistered_claude_opus_5_5_1m`,
and `opus5-5` becomes `claudecode/unregistered_opus5_5`. The output format does not change:
one line, `AGENT_STRING_FALLBACK:<agent>/<name>`, exit 0. The header comment will document
the reserved namespace.

### 2. Reserve the namespace at every registry writer
- **`aitask_add_model.sh` `validate_name`:** refuse names that start with `unregistered_`.
  The message will say the prefix is reserved for resolver fallbacks.
- **`aitask_opencode_models.sh`: refuse, never rename.** `convert_to_model_name` copies
  the provider text into the name unchanged. Any renamed name that stays inside the
  `[a-z0-9_]` grammar could therefore also be produced by some real provider. For example,
  `opencode_unregistered_foo` would also be the name derived from
  `opencode/unregistered-foo`, and `oc_reserved_*` would also come from an `oc/...`
  provider. A rename would bring back duplicate names, and `merge_with_existing` and the
  update scripts both select rows by name. Skipping or deleting rows would drop a valid
  provider and destroy verified scores and usage history. So the writer **fails closed
  before writing** and never alters the registry to enforce the reservation:
  - Add a guard after discovery and before `merge_with_existing`, in both the dry-run and
    the write path. It collects every discovered model and every existing row in
    `models_opencode.json` whose name starts with `unregistered_`.
  - If there are any, the script calls `die` before any write, and neither
    `models_opencode.json` nor `seed/` is modified. The message lists each conflicting
    `name (cli_id)`, explains that the prefix is reserved for resolver fallbacks
    (`aitask_resolve_detected_agent.sh`), and says how to fix it: rename or remove the
    listed row in `models_opencode.json` by hand, carrying its `verified` and
    `verifiedstats` over to the new name.
  - No skip, no rename, no deletion. Otherwise the script behaves exactly as before.
  - The prefix lives in one constant, with a comment pointing to the resolver.
  - Out of scope, noted as a follow-up to suggest: `convert_to_model_name` was already
    non-injective before this task. `a_b/c` and `a/b-c` both become `a_b_c`, and this
    change does not affect that.
- **`aitask-refresh-code-models` skill (Claude version):** add one rule to Step 6: never
  give a new model entry a name starting with `unregistered_` (reserved for resolver
  fallbacks). Suggest a follow-up aitask to port this rule to the Codex and OpenCode
  copies of the skill.
- **Invariant test:** a new test checks that no `name` in any shipped
  `aitasks/metadata/models_*.json` or `seed/models_*.json` starts with `unregistered_`.
  This catches a hand edit or skill edit in this repository.

### 3. Stats scripts: no prefix rejection, clearer hint, agent-specific
The stats scripts do **not** reject by prefix. A fallback name has no registry row, so
the existing `ensure_model_exists` refuses it, which is correct: there is no row to count
against. Its error message currently offers no way to fix the problem.
- Add `model_registration_hint <agent>` to the shared `lib/verified_update_lib.sh`, which
  both scripts already source. It returns:
  - `claudecode` or `codex`: "register it with /aitask-add-model"
  - `opencode`: "run /aitask-refresh-code-models — OpenCode models are CLI-discovered,
    /aitask-add-model does not accept opencode"
- Both scripts' `ensure_model_exists` messages append the hint. The two
  `ensure_model_exists` functions take a new `agent` argument, or the scripts read
  `PARSED_AGENT` directly, whichever matches their style.

### 4. Register the model
Run `aitask_add_model.sh add-json --agent claudecode --name opus5_5_1m --cli-id
'claude-opus-5-5[1m]' --notes "..."`. It should write both
`aitasks/metadata/models_claudecode.json` (data branch) and
`seed/models_claudecode.json` (main). I will run `git diff` in both trees to confirm.
This only registers the model. It is not promoted to default.

### 5. Documentation
- **`lib/agent_freeze.py`, around line 282:** change the docstring rationale to: "a
  fallback is a reserved `unregistered_*` name that names no registered model". The code,
  which refuses fallbacks by prefix, stays the same.
- **`.claude/skills/task-workflow/model-self-detection.md`:** in the
  `AGENT_STRING_FALLBACK` bullet, say that `<value>` is
  `<agent>/unregistered_<normalised cli_id>`. It parses but never matches a registered
  model. Give the agent-specific registration route: `/aitask-add-model` for claudecode
  and codex, `/aitask-refresh-code-models` for opencode.
  - Check whether the file is a `.j2` source or has rendered copies. Run
    `aitask_skill_verify.sh` and regenerate goldens as needed.
  - If the `.agents/`, `.opencode/` and `-remote-` variants are plain copies, give them
    the same edit. Otherwise, suggest a follow-up aitask.

### 6. Tests
- **`tests/test_resolve_detected_agent.sh`:**
  - Existing expectation becomes `claudecode/unregistered_unknown_model`.
  - Exact match: `claude-opus-5-5[1m]` gives `AGENT_STRING:claudecode/opus5_5_1m`.
  - Normalisation: a 1M-style id, an opencode provider id, uppercase letters and dots,
    and an all-punctuation id that gives `unregistered_unknown`.
  - **Collision:** `--cli-id opus5-5` gives `…/unregistered_opus5_5`, never `…/opus5_5`.
  - **Round-trip:** each fallback must pass `parse_agent_string` after sourcing
    `lib/agent_string.sh`. Run this in a subshell and use the file-backed counters there.
  - `aitask_codeagent.sh coauthor <fallback>` prints a trailer that contains the
    `unregistered_` name and not the Opus 5.5 label.
  - **Invariant:** no `unregistered_*` name appears in any shipped `models_*.json`.
- **`tests/test_usage_update.sh` and `tests/test_verified_update.sh`:** use their
  existing isolated `setup_repo` fixtures. Those copy the scripts into a temp repo, so
  `ait_cd_repo_root` resolves to the fixture. The fixture must copy the updated
  `verified_update_lib.sh`.
  - `--agent-string claudecode/unregistered_opus4_6` exits non-zero. The error says
    "not found" and includes `/aitask-add-model`, and it is not "Invalid agent string
    format". The JSON is unchanged.
  - `opencode/unregistered_x` gets the `/aitask-refresh-code-models` hint instead. Add a
    minimal `models_opencode.json` to that fixture.
  - Verified test: `--agent claudecode --cli-id <unregistered>` resolves to the fallback
    and hits the same "not found" message with a hint. If the fixture does not contain the
    resolver script, copy it in.
- **`tests/test_add_model.sh`:** `add-json --name unregistered_foo` is refused.
- **OpenCode writer:** the script runs its checks for the `opencode` binary at top level,
  so the test does not source it. Instead it extracts `process_model` and
  `merge_with_existing` with `sed` into a temporary file, or puts a stub `opencode` on
  `PATH` that prints canned `models --verbose` output. I will pick whichever the script
  structure allows. The test checks that:
  - a discovered `unregistered/foo` makes the run exit non-zero with the reserved-prefix
    message, and `models_opencode.json` is **byte-identical** afterwards (compared with
    `cmp` against a snapshot)
  - an existing `unregistered_bar` row makes the run fail the same way, with the file
    byte-identical, and its `verifiedstats` still present
  - a normal run with no reserved names succeeds and writes as before
  - `opencode/unregistered-foo`, whose name is `opencode_unregistered_foo`, is not
    treated as a conflict

## Verification
- Run the tests listed above, plus `tests/test_verified_update_flags.sh` and
  `tests/test_codeagent.sh`.
- Run `shellcheck` on the changed scripts.
- Manual: the resolver maps `claude-opus-5-5[1m]` to `opus5_5_1m` and `opus5-5` to
  `unregistered_opus5_5`.
- Run `aitask_skill_verify.sh`, since skill files change.

## Commit sequence (Step 8, then Step 9)
`aitasks/` is a symlink into the `.aitask-data` worktree (branch `aitask-data`). `seed/`
and the code live on `main`. These commits are split, in this order, and all land before
archival:
1. **Code commit on main**, using plain `git` with explicit paths only. It contains the
   scripts, `lib/verified_update_lib.sh`, `lib/agent_freeze.py`, the tests,
   `seed/models_claudecode.json`, and the skill docs and goldens.
   - Message: `bug: Make agent-string fallback parseable in a reserved namespace and register opus5_5_1m (t1884)`
   - Check `git show --stat` includes `seed/models_claudecode.json`.
2. **Registry commit on aitask-data:**
   `./.aitask-scripts/aitask_task_commit.sh -m "ait: Register opus5_5_1m model (t1884)" aitasks/metadata/models_claudecode.json`.
   Check it with `./ait git show --stat HEAD`.
3. Commit the plan file through the task-commit helper, as the workflow directs.
4. Only after that, run **Step 9** archival.

Follow-up to suggest: port the refresh-code-models naming rule and the
model-self-detection wording to the Codex and OpenCode skill trees, if they are not plain
copies.

## Risk

### Code-health risk: low
None identified. The OpenCode fail-closed guard is the only new branch in code that is
hard to exercise live. It never modifies the registry, and the plan already includes a
stubbed test with a byte-identity check. The resolver change is
contained, and the grammar consumers rely on stays the same.

### Goal-achievement risk: low
None identified. All reported consumers accept the string, and nothing is misattributed.
Recovery hints are correct for each agent, and the reported model is registered.
