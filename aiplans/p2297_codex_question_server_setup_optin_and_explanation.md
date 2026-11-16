---
Task: t2297_codex_question_server_setup_optin_and_explanation.md
Base branch: main
Output branch: main
---

# t2297 — Codex question server: explicit, explained opt-in in `ait setup`

## Context

`ait setup` registers the `aitask_questions` MCP server as a silent part of
"Install Codex CLI skills and config? [Y/n]". The seed table
`[mcp_servers.aitask_questions]` is merged into `.codex/config.toml`, and
`main()` pip-installs `mcp` whenever that registration exists. There is no
separate choice, no flag, and no removal path except hand-editing. This change
makes the server its own explained choice. Two more requests from plan review
are folded in. First, Codex entry points (stubs **and** directly invocable
rendered variants) must load `codex_tool_mapping.md`. Second, the opt-out must
be reliable: a failed rewrite must never leave a registration and still install
`mcp`, and the removal flag must work even when Codex setup is skipped.

**User decisions (2026-11-16):**
- The interactive prompt defaults to **Yes** (`[Y/n]`).
- With no terminal and no flag, an unregistered project **gets the server**
  (today's behaviour), unless a decline is recorded.
- An existing registration is the remembered "yes". A plain re-run keeps it,
  revalidates `mcp`, and prints one hint line naming the removal flag.
- An explicit decline is **remembered as a project setting** and honoured by
  later interactive and unattended runs. `--with-codex-questions` overrides it.
- `default_mode_request_user_input = true` stays in the seed.

**Design choice.** Keep the table in the single seed
(`seed/codex_config.seed.toml`) and filter it out at merge time when the server
is not wanted. A separate seed file would not be enough: `install.sh`
overwrites `aitasks/metadata/codex_config.seed.toml` on upgrade, but
`ensure_agent_config_seeds` never replaces an existing copy, so an older
metadata seed would still re-add the table. Filtering in the merge covers every
seed copy.

## Behaviour matrix

"Codex setup runs" means Codex is installed and the user accepted
"Install Codex CLI skills and config?".

| Flag | Codex setup runs? | Registered now? | Decline recorded? | Action |
|---|---|---|---|---|
| `--with-codex-questions` | yes | any | any | register; clear the decline (`true`) |
| `--with-codex-questions` | no | any | any | info: no effect without Codex setup |
| `--no-codex-questions` | yes | yes | any | unregister (merge in `remove` mode); record the decline |
| `--no-codex-questions` | yes | no | any | skip (seed merged without the table); record the decline |
| `--no-codex-questions` | **no** | yes | any | **standalone removal**: drop the table from the existing config, touch nothing else; record the decline |
| `--no-codex-questions` | **no** | no | any | record the decline only |
| none | yes | yes | no | keep the registration; hint `ait setup --no-codex-questions` |
| none | yes | yes | yes | keep the registration (never silently removed); warn about the mismatch, naming both flags |
| none | yes | no | yes | skip, no prompt (TTY or not); print one "declined for this project" line |
| none | yes | no | no | explanation, then the `[Y/n]` prompt on a TTY (n → skip and record the decline), or register when there is no terminal |
| none | no | — | — | nothing (today's behaviour) |

- Passing both flags → `die`. Either flag with `--hooks-only` → `die`. Both
  checks sit next to the existing `--yes` check, before any side effect.
- Unregistering never uninstalls `mcp`, because the venv is per-user and shared
  across projects. The message says so.

## Implementation steps

### 1. `.aitask-scripts/aitask_setup.sh`: flags, prompt and decision

a. **Flags in `main()`**: `--with-codex-questions` and `--no-codex-questions`
   set the global `CODEX_QUESTIONS_FLAG` (`1` / `0`, initialized to `""` beside
   `INSTALL_DEV=0`), plus the two `die` checks above. Functions read it as
   `${CODEX_QUESTIONS_FLAG:-}`, so tests that source the file stay `set -u`
   safe.

b. **`questions_server_registered [config]`**: an optional path argument, with
   today's default. The grep stays identical to the gate guard
   (`aitask_gate.sh:242`).

c. **`_setup_stdin_is_tty()`** returns `[[ -t 0 ]]`. This is the test seam,
   now used by **both** Codex prompts (the existing skills prompt and the new
   one).

d. **`explain_codex_questions_server()`**: a few plain `info` lines:
   - It shows workflow questions (task confirmation, plan approval, commit
     review) as forms in Codex. A form left unanswered closes after 5 minutes,
     and you answer at the ordinary prompt to continue.
   - It installs `mcp` into the framework venv and registers the server in
     `.codex/config.toml`, a project file that setup commits.
   - Restart Codex after setup.
   - In Codex sessions it also enforces approvals: plan approval, the reviewed
     commit, the merge and archival are checked against the answered question.
   - Without it, Codex asks in plain text and approval enforcement is off.

e. **`resolve_codex_questions_action <dest_config>`** implements the matrix
   rows where Codex setup runs. It sets the global `CODEX_QUESTIONS_ACTION`
   (`register|skip|unregister`) instead of echoing, so the prompt is never
   captured by `$( )`.

f. **`setup_codex_cli`**:
   - Replace the three question-server intro lines with: "The aitask_questions
     question server is a separate choice, asked next."
   - The skills prompt uses `_setup_stdin_is_tty`.
   - **Decline branch**: call `codex_questions_without_codex_setup` (step 2c).
   - After acceptance, call `resolve_codex_questions_action`, only when the
     seed exists.
   - The config step calls `apply_codex_config` (step 2b) with mode
     `keep|omit|remove` for `register|skip|unregister`.
   - Still never calls pip or `setup_questions_deps` (test 3e).

g. **`setup_code_agents`**: in the `_is_agent_installed codex` check, the
   else branch calls `codex_questions_without_codex_setup`.

h. **`main()` deps gate**: replace `if questions_server_registered` with
   `if questions_deps_wanted`. The new function returns true only when the
   server is registered **and** this run did not request an opt-out:
   `CODEX_QUESTIONS_ACTION` is not `skip` or `unregister`, and
   `CODEX_QUESTIONS_OPTOUT_FAILED` is not `1`. When it is false only because
   an opt-out failed, it prints a warning: "registration still present after a
   failed removal — `mcp` not installed this run; remove the
   `[mcp_servers.aitask_questions]` table by hand or re-run setup". A plain
   re-run with a registration still revalidates and repairs as before.

i. **`usage()`**: add both flags. Document the remembered yes (the
   registration) and the remembered no (the project setting), that the
   removal flag works without the Codex setup, and the default with no
   terminal.

### 2. Validated config publish (failure-safe opt-out)

a. **`merge_codex_settings <seed> <dest> [keep|omit|remove]`**:
   - It now **returns non-zero on failure**: no python, no TOML parser, a
     parse error, empty output, or an unknown mode. Today it warns and returns
     0. Its only production caller is `setup_codex_cli`; the tests call it and
     ignore the status.
   - Python `drop_questions(d)` deletes `mcp_servers.aitask_questions`, and
     `mcp_servers` too when that leaves it empty. `omit` drops it from the seed;
     `remove` drops it from the seed and from the existing config, with a
     stderr note.
   - `/dev/null` is accepted as the seed: an empty TOML, so `remove` with that
     seed is a remove-only rewrite. The t1944 retirement rule cannot fire,
     because it requires seed markers.

b. **New `apply_codex_config <seed|/dev/null> <dest> <mode>`**, the only
   writer of `.codex/config.toml` for these paths:
   1. Build the candidate in a temp file in the destination directory, so the
      later `mv` is atomic: start from `cp <dest>` when it exists, otherwise
      `cp <seed>`.
   2. Run `merge_codex_settings <seed> <tmp> <mode>`, except for fresh + `keep`,
      where a pure seed copy needs no merge and keeps its comments. A failure
      → discard the temp file and return 1, with `<dest>` untouched.
   3. **Validate** the candidate with one Python check (`tomllib`/`tomli`).
      It must parse, and its registration state must equal the intent: present
      for `keep`, absent for `omit`/`remove`. For a remove-only rewrite (seed
      `/dev/null`), the parsed candidate must also equal the parsed original
      minus the table, which proves unrelated config was preserved. A
      validation failure → discard, return 1, `<dest>` untouched.
   4. Publish with `mv`, and return 0.
   - Callers report distinct outcomes:
     - **register** failure: warn "not registered".
     - **skip / unregister** failure: set `CODEX_QUESTIONS_OPTOUT_FAILED=1` and
       warn that the opt-out failed, the registration may remain, and `mcp` is
       not installed this run.
     - **Fresh decline** failure: no `.codex/config.toml` is published at all.
       It fails closed (no registration), with a warning to re-run setup.
     - Success: "Removed …" / "Registered …" / "Not registered".

c. **New `codex_questions_without_codex_setup`**, for when Codex is not
   installed or its prompt was declined:
   - Flag `0`: record the decline, set `CODEX_QUESTIONS_ACTION=unregister`. If
     `.codex/config.toml` registers the server, run
     `apply_codex_config /dev/null <dest> remove`, which removes the table and
     validates that everything else is unchanged. On failure set
     `CODEX_QUESTIONS_OPTOUT_FAILED=1`.
   - Flag `1`: info "no effect without the Codex setup".
   - No flag: nothing.

### 3. Remembered decline (inline post-phase `remember_codex_questions_decline`)
- **Setting:** a top-level key in `aitasks/metadata/project_config.yaml`,
  `codex_questions_server: false`. Absent or `true` means no recorded decline.
- **`codex_questions_declined`**: grep
  `^codex_questions_server:[[:space:]]*false[[:space:]]*(#.*)?$`.
- **`record_codex_questions_decision false|true`**:
  - If the key line exists, rewrite it with `sed_inplace`.
  - Otherwise, for `false` only, append a comment line plus the key. `true`
    with no key writes nothing.
  - A missing file → warn "decline not recorded; setup will ask again".
  - On a write, set `CODEX_QUESTIONS_DECISION_WRITTEN=1` and call
    `_note_metadata_write "aitasks/metadata/project_config.yaml"` (existing
    file, never `new`).
- **Commit:** `commit_setup_metadata_writes` runs before `setup_code_agents`,
  so in `main()` right after `setup_code_agents`: if
  `CODEX_QUESTIONS_DECISION_WRITTEN` is `1`, run
  `_flush_metadata_batch 0 "aitasks/metadata/project_config.yaml"` (the same
  call as `aitask_setup.sh:3091`). The functions themselves never commit.
- **Seed and docs:** a comment-only documentation block in
  `seed/project_config.yaml`; a row in the "Project Config Keys" table of
  `website/content/docs/tuis/settings/reference.md`.

### 4. Seed: `seed/codex_config.seed.toml`
Keep the table. Comment: it is registered only on opt-in (prompt or
`--with-codex-questions`), setup strips it otherwise, and
`--no-codex-questions` removes it.

### 5. Codex entry points load `codex_tool_mapping.md`

**Gap.** All 22 plain Codex wrappers point at
`.agents/skills/codex_tool_mapping.md`. None of the 15 profile-aware stubs do,
and neither do the rendered `-codex-` variants. Those variants are directly
invocable skills (Codex discovers `.agents/skills/*/SKILL.md`), so a session
entering either way never learns that `AskUserQuestion` maps to the
`aitask_questions` server or what the fallback is. `stub-skill-pattern.md`
rule 5 already says per-agent mapping lives in prereq files that the entry
point reads.

0. **Single source for the pointer.** Add a new snippet file,
   `.aitask-scripts/skill_templates/codex_entry_prereq.md`, holding one
   paragraph:
   > **Tool mapping first.** Read **`.agents/skills/codex_tool_mapping.md`**
   > before anything else in this skill and apply it for the whole run,
   > including every file this skill tells you to read.

   Three places read this file and none retypes it:
   - the stub generator (5a);
   - the renderer injection (5b);
   - the refresh fallback (5b′).

   The idempotence check everywhere is `grep -qF` on the mapping path line.
   Document the file in `skill_templates/README.md`.

a. **Stubs.** In `aitask_audit_wrappers.sh` `render_agents_skill()`,
   templated branch, emit the snippet's contents (`cat` of the file) after the
   frontmatter and before "This is a profile-aware skill stub…", in the same
   position as the OpenCode `@` includes.
   - Regenerate the 12 template-matching stubs with
     `apply-wrapper agents <skill>`, and diff each against HEAD; the only
     change must be the paragraph.
   - Insert it by hand in the 3 customized stubs (`aitask-pickrem` and
     `aitask-pickweb` have the pre-rendered wording, `aitask-shadow` has
     `user-invocable: true`).

b. **Rendered variants: one injection point, no duplicated content.** In
   `.aitask-scripts/lib/skill_template.py`:
   - Add `AGENT_ENTRY_PREREQS = {"codex": ".agents/skills/codex_tool_mapping.md"}`.
   - In `walk_closure`, for the **entry-point** plan item only (`src` is the
     entry template), after reference rewriting, insert a short pointer
     paragraph right after the frontmatter: "**Tool mapping first.** Read
     **`<prereq>`** before anything else and apply it for the whole run…".
   - It is inserted after `discover_refs`/rewrite, so the path is never
     rewritten or walked as a closure dependency.
   - `render_skill()` (the legacy single-template path used by goldens and
     Test 1b agent-invariance) is **unchanged**, so goldens and invariance
     stay byte-identical.
   - The paragraph comes from the 5.0 snippet file (`AGENT_ENTRY_PREREQS`
     maps the agent to that file).
   - `aitask_skill_render.sh` always runs `walk-write`, whose content-diff
     check rewrites a variant whenever its parent stub dispatches. A
     **directly invoked** old variant never reaches the renderer, which 5b′
     closes.
   - Regenerate the committed headless prerenders
     (`.agents/skills/aitask-pickrem-remote-codex-/`,
     `.agents/skills/aitask-pickweb-remote-codex-/`) in the same commit, and
     confirm `aitask_skill_verify.sh` (walk-verify) is clean.

b′. **Refresh existing rendered Codex entry points on setup and upgrade**
   (closes the direct-invocation bypass). New function
   `refresh_codex_rendered_entries` in `aitask_setup.sh`:
   - **Scan.** Scan `.agents/skills/` for directories ending in `-codex-` that
     contain a `SKILL.md`. Match each against the templated skills (those with
     `.claude/skills/<skill>/SKILL.md.j2`), taking the **longest** `<skill>-`
     prefix (so `aitask-pickrem-…` never resolves to `aitask-pick`). The middle
     segment is the profile.
   - **Skip.** Leave a directory untouched when there is no template (an
     orphan), the name is not a Codex directory, or it sits under another
     agent's root.
   - **Refresh.** Run
     `aitask_skill_render.sh <skill> --profile <profile> --agent codex` for each
     match. This reuses the same per-file atomic overwrite as
     `aitask_skill_rerender.sh`, which keeps open sessions safe, and never
     `rm -rf`.
   - **Fallback.** If the render fails (no python or minijinja, an unknown
     profile, a template error) and the entry `SKILL.md` lacks the pointer,
     insert the 5.0 snippet right after the frontmatter with a pure-bash/awk
     insertion. That needs no Python, so it also works at upgrade time on a
     machine whose venv is broken. The insertion is idempotent, and a later
     real render replaces it with identical renderer output.
   - **Report.** Print one line, `CODEX_ENTRIES: refreshed=<n> patched=<m>
     skipped=<k>`. The function never fails the caller: it warns and returns 0.
   - **Callers:**
     - `ait setup`, in `setup_code_agents` right after the Codex block. It runs
       whether or not Codex setup ran, because rendered variants already on
       disk stay invocable either way.
     - `install.sh`, which `ait upgrade` runs and which never runs setup: right
       after it sources `aitask_setup.sh --source-only` (next to
       `install_global_shim`), as
       `declare -F refresh_codex_rendered_entries >/dev/null && refresh_codex_rendered_entries || true`.
       That is the existing guard pattern for pairing a newer installer with
       an older tarball.
   - **Commits:** the refresh commits nothing. Rendered `*-/` directories are
     gitignored, and the committed remote prerenders are regenerated in this
     change, so they already match.

c. **Mapping text** (`.agents/skills/codex_tool_mapping.md`), small edits:
   - "the `aitask_questions` MCP server that `ait setup` registers" → "…
     registers when the user accepts it".
   - In "If the server is not available": add that this includes a project
     whose setup declined the server, and that `ait setup --with-codex-questions`
     registers it.
   - The fallback rule itself is unchanged and is the guidance both entry
     paths reuse.

d. **Docs**:
   - `aidocs/framework/stub-skill-pattern.md`: in §3b, the Codex stub carries
     the mapping-first paragraph (the counterpart of the OpenCode `@` includes
     in §3d). Add a sentence on `AGENT_ENTRY_PREREQS` injection for rendered
     entry points.
   - Check `skill_authoring_conventions.md` and
     `.claude/skills/aitask-audit-wrappers/SKILL.md` for a stub-body
     description to keep in sync.

e. **Scope**: Codex only. The OpenCode stubs already include their mapping;
   whether OpenCode's rendered variants need the same injection (one table
   entry) is offered as a separate follow-up task at the end.

### 6. Docs (current-state prose only)
- `installation/_index.md` ("Optional: Codex CLI support"): the server is
  asked separately (default yes), with what it installs and the restart note.
- `commands/setup-install.md` step 7: the separate prompt, both flags, the
  default with no terminal, the remembered yes and no, removal without the
  Codex setup, and that `mcp` stays in the shared venv.
- `installation/known-issues.md` ("Interactive checkpoints"): the server is
  registered when accepted. Without it, questions come in plain text and
  approvals are not enforced; `--with-codex-questions` adds it.
- `aidocs/codeagents/codex_questions.md`: the Registration and Dependency
  rows; "Gate enforcement → Scope" notes that opting out switches enforcement
  off.
- `cd website && python3 check_links.py --build`

### 7. Tests

**`tests/test_setup_questions_server.sh`** (existing Groups 1–4 kept; header
updated):
- **G5, merge modes**:
  - `omit`: seed keys merged, no table;
  - `remove`: table gone, the user's other server and scalar kept, stderr
    note printed;
  - `remove` of the last server: no `mcp_servers` left;
  - `omit` on a registered config keeps it;
  - `/dev/null` + `remove`: parsed result equals the original minus the table.
- **G6, `setup_codex_cli` end-to-end** (fixture shaped like
  `make_codex_fixture`):
  - non-TTY, no flag → registered;
  - flag `0`, fresh → valid config, no table;
  - flag `0`, registered → removed;
  - no flag, registered → kept, with the hint;
  - flag `1` → registered and the decline cleared;
  - TTY seam: `n` → skipped and decline recorded; an empty line → registered;
    the explanation text is shown.
- **G7, failure paths** (concern 1). Make the merge fail: point `VENV_DIR` at
  a fake venv whose python exits 1, and put a failing `python3` first on
  `PATH`.
  - **Fresh decline**: `.codex/config.toml` is not published (or not
    registered), `CODEX_QUESTIONS_OPTOUT_FAILED=1`, `questions_deps_wanted`
    is false, and the output says the opt-out failed.
  - **Existing-registration removal**: config byte-identical to before, the
    same flag set, deps not wanted, and a distinct "failed" message (not
    "Removed").
  - **Validation failure**: a merge stub that emits a still-registered config
    in `remove` mode → rejected, `<dest>` untouched.
- **G8, removal without Codex setup** (concern 3). Stub `_is_agent_installed`
  and drive the extracted Codex block of `setup_code_agents`, plus
  `setup_codex_cli` with the skills prompt answered `n` through the TTY seam.
  - Codex not installed + flag `0` + a registered config with unrelated keys:
    table removed, everything else parsed-equal, decline recorded.
  - Skills declined + flag `0`: the same.
  - Flag `1` on both paths: no change, and the "no effect" note.
- **G9, remembered decline**:
  - a recorded decline makes a later non-TTY run, and a TTY run, skip without
    prompting;
  - flag `1` clears it;
  - a missing `project_config.yaml` warns and does not abort;
  - registered + declined is kept, with the mismatch warning;
  - exactly one `codex_questions_server:` line after repeated writes.
- **G10, flag parsing**: both flags, or a flag with `--hooks-only`, exits
  non-zero with its message. Run under a scratch `HOME` with `AITASKS_HOME`
  unset; the `die` precedes every side effect.

**New `tests/test_codex_entrypoints_tool_mapping.sh`** (concern 2):
- **Stubs**: every `.agents/skills/<name>/SKILL.md` with a
  `.claude/skills/<name>/` source and not a rendered variant references the
  mapping path, and the mapping file exists. The count of profile-aware stubs
  checked must equal the count of `.claude/skills/*/SKILL.md.j2` that have a
  Codex stub.
- **Rendered variants (the reachable direct-entry path)**: for every templated
  skill with a Codex stub, run `skill_template.py walk-check`, or an in-memory
  `walk_closure(write=False)` via a small python snippet, for the `fast`
  profile and agent `codex`. Assert the entry item's content carries the
  pointer right after the frontmatter. Assert agent `claude` gets no
  injection. Assert the committed `-remote-codex-` prerenders on disk carry it.
- **Template pin**: `render-wrapper agents aitask-pick` places the paragraph
  before "This is a profile-aware skill stub".
- **Fallback reachable**: the mapping still has the "If the server is not
  available" passage, and it names `--with-codex-questions`.
- **Negative controls**: a scratch stub with the paragraph stripped is
  flagged, and a rendered entry with the injection removed is flagged by the
  same checker functions.
- **Single source**: the stub generator output, the renderer injection and
  the fallback insertion each contain the snippet file's text verbatim.
- **Refresh, render path** (R1). Build a scratch copy of the framework
  (`.aitask-scripts/`, `.claude/skills/`, `aitasks/metadata/profiles/`) and
  plant a pre-change `.agents/skills/aitask-pick-fast-codex-/SKILL.md` with
  no pointer. Run the scratch `refresh_codex_rendered_entries` **without
  invoking the parent stub**. Assert the pointer is present and the file
  equals a fresh walk render. Skip with a message when no python with
  minijinja is available.
- **Refresh, fallback path** (R2). Force the render to fail (an unknown
  profile directory, or `AIT_PYTHON` set to a failing interpreter). Assert
  the pointer is inserted once, right after the frontmatter, with the
  frontmatter byte-identical. A second run leaves exactly one pointer.
- **Refresh scope** (R3): orphan `-codex-` directories, non-Codex rendered
  directories and Claude rendered directories are untouched, and
  `aitask-pickrem-<p>-codex-` resolves to `aitask-pickrem`.
- **Upgrade fixture** (R4), following the
  `tests/test_upgrade_prunes_retired_scripts.sh` recipe:
  1. Build a tarball from the working tree (`git ls-files -co
     --exclude-standard`, with `.claude/skills` → `skills/`).
  2. Install it with `install.sh --local-tarball <tgz> --dir <scratch>
     --no-testmap` under a scratch `HOME`, with `AITASKS_HOME` unset and
     `AIT_TESTMAP_FETCH=0`.
  3. Plant a pre-change rendered `.agents/skills/aitask-pick-fast-codex-/SKILL.md`
     without the pointer.
  4. Run the **upgrade** path, `install.sh --force --local-tarball <tgz>
     --dir <scratch>`.
  5. Assert the planted variant now carries the pointer, without the stub
     ever having been invoked. Under the scratch `HOME` there is no venv, so
     this exercises the fallback through `install.sh`, the route
     `ait upgrade` takes.
- **Wiring** (R5): `declare -f setup_code_agents` contains
  `refresh_codex_rendered_entries`, and `install.sh` contains the guarded
  call after the `--source-only` source line.

**Re-run unchanged suites:**
- `tests/test_setup_agent_config_seeds.sh`
- `tests/test_session_hook_install.sh`
- `tests/test_codex_config_tui_seed.sh`
- `tests/test_gate_codex_approvals.sh`
- `tests/test_skill_dispatch_contract.sh`
- `tests/test_audit_wrappers_render_opencode_command.sh`
- all `tests/test_skill_render_*.sh` (goldens and Test 1b must stay green
  untouched)
- `./.aitask-scripts/aitask_skill_verify.sh`
- grep `tests/` for `usage()` text pins and run any that match.

**Full install flow** (extension-points rule for setup helpers touching
`project_config.yaml`): build a local tarball, then
`bash install.sh --dir <scratch> --local-tarball <tgz>` into a scratch git repo,
using the recipe from `tests/test_install_create_data_dirs.sh`. Source the
scratch `aitask_setup.sh` under a scratch `HOME`, run the decline path, and grep
the scratch `project_config.yaml` and `.codex/config.toml`.

**Lint:** `shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/aitask_audit_wrappers.sh`

### Post-phase (risk mitigations)
1. [remember_codex_questions_decline] Implement §3 (the
   `codex_questions_server: false` project setting, its reader and writer,
   the matrix rows that honour it, and the post-`setup_code_agents` commit),
   and verify it with test group G9 plus the full install flow in §7. It is
   kept as its own step because it was confirmed as an inline mitigation; its
   content is specified in §3.

## Step 9 (Post-Implementation)
Commit the code with `enhancement: … (t2297)`, and the plan through
`aitask_task_commit.sh`. Then archive through the standard Step 9 flow. At
Step 8e, offer a follow-up task for the OpenCode rendered-variant mapping
injection.

## Risk

### Code-health risk: medium
- The new `remove` / `omit` modes of the shared `merge_codex_settings` rewrite a committed `.codex/config.toml`, and a bug could drop a user's other MCP servers or leave the TOML invalid · severity: medium · → mitigation: none (covered in plan: `apply_codex_config` builds and validates a temp candidate before an atomic publish; a remove-only rewrite proves parsed equality minus the table; G5/G7 pin both)
- The post-phase writes a new key into the user-owned, committed `project_config.yaml` · severity: low · → mitigation: none (G9 single-line rewrite test, plus `_note_metadata_write` refusing untracked content)
- `setup_codex_cli` gains a second prompt and a TTY seam shared with the skills prompt · severity: low · → mitigation: none (the non-TTY defaults are unchanged; the existing suites are re-run)
- `refresh_codex_rendered_entries` runs on every setup and upgrade and rewrites existing rendered Codex entry files. A bad prefix parse could re-render the wrong skill, and a broken fallback insertion could corrupt the frontmatter · severity: low · → mitigation: none (covered in plan: longest-prefix match plus template-existence skip; R1–R3 pin render, fallback idempotence and scope; R4 exercises the real upgrade route; the function never fails its caller)
- The renderer injection touches `walk_closure` for every Codex entry point, and the stub regeneration rewrites 12 files · severity: low · → mitigation: none (`render_skill` and the goldens are untouched; stubs are diffed against HEAD; the committed prerenders are regenerated and walk-verified)

### Goal-achievement risk: low
- A decline is not remembered. A later interactive run asks again (default Y), and a non-interactive run registers, so a team member who declined can see the server come back after someone else's setup run · severity: low (residual — addressed by inline post-phase remember_codex_questions_decline) · → mitigation: inline post-phase remember_codex_questions_decline

### Planned mitigations
- name: remember_codex_questions_decline · timing: inline post-phase · inline_risk: low · added_complexity: medium · addresses: decline not remembered (goal-achievement) · plan step: §3 (remembered decline)

## Post-Review Changes

### Change Request 1 (2026-11-17 00:30)
- **Requested by user:** three confirmed defects. (1) Removal re-serialized through `toml_serialize`, which never escaped strings, so a config with `args = ['say "hello"']` produced invalid TOML; validation then refused the removal and the server stayed registered. (2) `apply_codex_config` published with `mv -f`, replacing a symlinked `.codex/config.toml` with a regular file while the backing file stayed registered. (3) `record_codex_questions_decision` rewrote `project_config.yaml` with `cat tmp > cfg`, truncating it in place.
- **Changes made:**
  - A remove-only rewrite first tries `_codex_config_text_remove`, a byte-preserving text cut of the `aitask_questions` table and its subtables. It finds headers by parsing each `[`-line with tomllib, keeps the comments that belong to the next table, drops the seed's own `# aitask_questions` comment paragraph, and collapses surplus blank lines. Only if that fails does it fall back to the re-serializing merge. Both candidates must parse to the original minus the table, with an empty `[mcp_servers]` normalized to absent.
  - The `merge_codex_settings` Python moved into a quoted heredoc, and its serializer became a real TOML emitter: escaped strings, quoted non-bare keys, and booleans, floats and dates kept inside arrays and inline tables. Plain values serialize byte-identically to before.
  - `apply_codex_config` now stages and publishes through `lib/atomic_write.sh` (`ait_atomic_resolve`, `ait_atomic_tmp`, `ait_atomic_commit`). A symlinked config is updated through the link, the link stays a link, and the file mode is kept.
  - `record_codex_questions_decision` uses `ait_atomic_render` with a guarded renderer.
  - The refresh fallback insertion also publishes through `ait_atomic_render`, and its awk renderer exits 1 when it inserted nothing.
  - New tests. G11: a standalone removal with quoted, escaped and dotted values is byte-exact; values survive the merge path and a double keep-merge; a dotted-key registration falls back to the merge; the seed comment block is dropped. G12: removal and merge through symlinks; `project_config.yaml` through a symlink keeps its mode and is published by rename (new inode); a failed render leaves it intact. Pre-fix mutants (`mv` unresolved, in-place truncation, no escaping, no text cut) each fail G11/G12.
- **Files affected:** `.aitask-scripts/aitask_setup.sh`, `tests/test_setup_questions_server.sh`
