---
Task: t1869_support_cross_repo_task_notes.md
Base branch: main
Output branch: main
---

# t1869 — Cross-repository task notes (`ait note --project`)

## Context

`ait note` is the durable, advisory channel for handing context to an existing
task. Today both its targets and its `--from` senders are local-only. The only
way to write a `<project>#<id>` sender is the `--migrate` path, which stays
unverified by design. Cross-repo task identity and routing already exist through
the logical-project registry (`ait projects`, `ait create --project`). This task
adds **additive** `--project <name>` routing to `ait note` and `ait note read`.
Every existing local invocation keeps its behaviour, byte for byte.

### Findings that shape the design
- **No schema change is needed.** `lib/note_inbox.py:210-220` already accepts
  an ordinary (non-migrated) note with `from=<project>#t<id>`, marker name
  `t<id>`, and optional `from_verified=yes`. The merger shares the same
  `validate_block`. Old checkouts will therefore read and merge the new notes
  unchanged. This task only extends the writer.
- **The resolver** (`aitask_project_resolve.sh`) prints exactly one line:
  `RESOLVED:<path>`, `NOT_FOUND:<name>` or `STALE:<name>:<path>`. It resolves
  through three tiers: tmux scan, then registry, then env. It has no
  "ambiguous" code; `list` prints `PROJECT:<name>:<path>:<status>`.
- **`aitask_create.sh --project`** (2440-2512) sets the pattern: strip the
  flag, resolve, then `cd "$root"` and run that repo's own script.
- **The sender proof is portable across repos on one host.** The lock lives
  on the source repo's `aitask-locks` branch. `lock_anchor_is_self` compares
  it against the current session's anchor (the tmux pane process or
  `AIT_AGENT_PID`). A child process in the target repo, started from the
  same session, has the same anchor. So the proof can genuinely run inside
  the target helper against the source repo's lock.
- **Hazard:** provenance uses `${AIT_DIR:-…}` (`aitask_note.sh:317`). An
  inherited `AIT_DIR` would record the wrong repository, so delegation must
  unset it.

## Design

### Grammar (all additions)
```
ait note <id> --project <target-proj> --from <id> [--from-project <src-proj>]
         (--text … | --file …) [--with-live]
ait note read <id> --project <target-proj> --by <id> --ids <csv> [--mode …]
```
- `--project` names where the **target** task lives. A command without it
  runs the existing local path unchanged, because routing happens before any
  local parsing.
- `--from-project` is optional on the caller side. It only selects among
  several registry names for the calling repo, and it must resolve back to
  the calling repo.
- `--project` is refused together with `--migrate`
  (`NOTE_ERROR:project-not-valid-with-migrate`). Migration stays separate.
- **An option-aware pre-scan decides routing** (second review, finding 1).
  Routing is triggered only by `--project` appearing **in option
  position**, never by the token appearing anywhere in argv. The scan walks
  argv exactly like the real parsers:
  - it skips the first positional (the target id; after `read`, the read
    target);
  - for every value-taking option it consumes the next token as that
    option's value **without inspecting it**. Write options: `--from`,
    `--text`, `--file`, `--claimed-from`, `--claimed-at`, `--base`,
    `--base-branch`, `--project`, `--from-project`. Read options: `--by`,
    `--ids`, `--mode`, `--project`.
  - Flags without a value (`--with-live`, `--migrate`) are single tokens.

  So `--text --project`, `--file --project` (a file literally named
  `--project`), `--text --from-project` and `--ids --project` stay what
  they are today: a body, a path, an id. A local call carrying them runs
  the local path byte for byte, and a routed call forwards them as values.
  Anything the scan doesn't recognize (an unknown option) makes it stop
  and leave routing off. The existing local parser then reports
  `unknown-option` exactly as it does today, so the scan never
  reclassifies an error either.
- **Options are counted before anything is resolved** (review finding 1).
  The routing pre-scan counts every `--project` and `--from-project` and
  requires each one to have a value. A second occurrence is refused before
  any resolution or delegation, for both write and `read`
  (`NOTE_ERROR:duplicate-option:--project` /
  `READ_ERROR:duplicate-option:--project`). A missing value gives
  `…:missing-value:--project`. There is no last-one-wins path, so a
  repeated flag can never mutate an unintended repository. The target
  helper's own parser counts `--from-project` the same way.

### Typed outcomes per verb (review finding 2)
Route failures use the **verb's own** outcome family, so a caller parsing
`read` output never sees a `NOTE_*` line:
- write: `NOTE_ERROR:<reason>`, with exactly one line on stdout, as today;
- read: `READ_ERROR:<reason>`, the same one-line contract as the receipt
  path. A `READ_ERROR` means no receipt was written and the note stays
  unread.

The reasons are shared: `bad-project-name:<n>`, `project-not-found:<n>`,
`project-stale:<n>`, `project-ambiguous:<n>`,
`project-resolution-incomplete:<tier>`, `project-is-local:<n>`,
`project-incompatible:<n>`, `duplicate-option:<flag>`,
`missing-value:<flag>`.

### Two halves
1. **Caller side** (the source repo's `aitask_note.sh`, a new
   `note_xrepo_route`). It is dispatched in `main()` and `note_read_main`
   only when the option-aware pre-scan finds `--project` in option position
   (never on a raw argv match). It does only routing, and
   every failure happens before any mutation. Each failure is reported in
   the verb's own family (`NOTE_ERROR:` for a write, `READ_ERROR:` for a
   read), shown below in the write form:
   - First, count the options: duplicate or value-less `--project` and
     `--from-project` are refused before anything else runs.
   - Validate the name against the portable charset `^[a-z0-9_-]+$`, the
     same prefix as `_XREPO_TASK_RE`. Failure gives
     `NOTE_ERROR:bad-project-name:<n>`.
   - Resolve the target project (see ambiguity rules below). Failures:
     `NOTE_ERROR:project-not-found:<n>`, `project-stale:<n>`,
     `project-ambiguous:<n>`, `project-is-local:<n>` (it resolves to this
     same repo root).
   - Check compatibility **for each verb**. The target's
     `.aitask-scripts/aitask_note.sh` must be executable.
     - For a **write**, its `--help` must advertise `--from-project`,
       because that is the one new argument the write delegates.
     - For a **read**, its `--help` must advertise the receipt verb (the
       `read <task-id> --by` usage line), and nothing else is required. The
       read delegates only the existing `read` grammar, so a target that
       predates this task but has the receipt verb is fully usable.
     - A missing capability gives `…:project-incompatible:<n>` in the
       verb's own family. An older installation never receives an argument
       it would misparse.
   - For writes only, resolve the source identity:
     - With `--from-project`, the name must resolve (same rule) to this
       repo's root; otherwise `NOTE_ERROR:from-project-mismatch:<n>`.
     - Without it, do a reverse lookup over the **explicit name bindings**:
       registry entries (from the complete enumeration, which fails closed)
       and `AITASKS_PROJECT_*` env vars whose canonical path is this repo's
       root. Keep only the names whose forward `note_project_resolve` lands
       here unambiguously.
     - tmux-derived names (a session name or basename) are **not**
       auto-selected, since they are incidental rather than declared
       identities. They are still accepted through an explicit
       `--from-project` that passes the forward check.
     - Zero matches gives `NOTE_ERROR:source-unregistered`. More than one
       distinct name gives `NOTE_ERROR:source-ambiguous:<a,b>`, with a hint
       to pass `--from-project`. No name is ever invented.
   - Absolutize a `--file <path>` against the caller's cwd, because the
     delegate runs in another directory. `-` (stdin) passes through as is.
   - Delegate with
     `cd "$root" && env -u AIT_DIR -u TASK_DIR -u PLAN_DIR -u ARCHIVED_DIR -u ARCHIVED_PLAN_DIR "$root/.aitask-scripts/aitask_note.sh" <target> --from <id> --from-project <src> …`.
     `read` gets `read <id> --by … --ids … --mode …`. Stdin and stderr pass
     through.
   - Rewrite the path field of id-bearing lines to absolute (`$root/<path>`):
     `NOTE_APPENDED`, `NOTE_APPENDED_UNCOMMITTED`, `READ_RECORDED`,
     `READ_RECORDED_UNPUSHED`. This mirrors `create --project`'s path
     prefixing, so a foreign path can't be mistaken for a local one. All
     other lines, including `LIVE_*`, pass through verbatim. The delegate's
     exit status is returned unchanged.
2. **Target side** (the same script, running in the target repo). The new
   `--from-project <src>` option exists on the write path only. It is also
   the capability token the caller probes for.
   - It is refused together with `--migrate`.
   - It re-validates the name, then resolves it in this process with the same
     resolve and ambiguity rules → `src_root`. If `src_root` is this repo, the
     result is `NOTE_ERROR:from-project-is-target:<n>`.
   - The source task must exist:
     `(cd "$src_root" && TASK_DIR=aitasks resolve_task_file <from>)`.
     Otherwise `NOTE_ERROR:source-task-missing:<src>#t<id>`, and nothing is
     mutated.
   - The stored sender is `from=<src>#t<id>` with marker name `t<id>`. The
     local `NOTE_SELF` check is skipped, because equal numbers in two
     projects are different tasks.
   - **The proof** is `note_sender_is_self_in "$src_root" <from>`.
     `lock_record_read` gains an optional second arg `<project-root>`, which
     runs **that repo's own** `aitask_lock.sh --check` with `cwd=<root>`.
     The default (no arg) is byte-identical to today, and
     `aitask_live_endpoint.sh` is untouched. `from_verified=yes` is written
     only on proof; otherwise the field is omitted, never written as `no`.
     This is not a trusted flag: a direct caller passing `--from-project`
     still has to hold the lock through its own session anchor.
   - Everything after that is unchanged, and it all runs in the target repo:
     ledger lock, append, path-scoped `task_git` commit, best-effort push,
     the `NOTE_APPENDED_UNCOMMITTED` terminal contract, and the durable-first
     `--with-live`, where the live resolver runs in the target repo on this
     host.
   - **Provenance** (`base`, `dirty`, …) is captured from the target checkout
     (`AIT_DIR` is unset, so the default is the target root). It records
     which recipient tree the note was written against, and a recipient's
     staleness check can compare it with its own history. A source-repo SHA
     would not resolve there. The docs state that the sender's own tree is
     not recorded.
   - `read --project` needs no target-side change: `--by` is still the target
     task's own id, and validation, rollback and output are unchanged.

### Resolution rule: every supported tier, with conflicts failing closed
`note_project_resolve <name>` returns `root`, or a typed reason. It keeps
**every tier the existing resolver supports**: the live tmux session, the
persistent registry, and the `AITASKS_PROJECT_<name>` env override. So a CI
caller using the documented env override can send a cross-repo note, just as
it can `ait create --project`. The one difference from the named resolve is
that a mutating cross-repo write never **silently** picks one tier over
another (review findings 3 and 5).

- **New additive resolver mode: `aitask_project_resolve.sh candidates
  <name>`** (in `aitask_project_resolve.sh`, the canonical owner of
  resolution rules, not re-implemented in note). It enumerates **every**
  match in **every** tier. The existing named resolve stops at the first
  hit and cannot report a conflict. Output:
  - `CANDIDATE:<tier>:<RESOLVED|STALE>:<path>`, zero or more lines, where
    `<tier>` is `tmux`, `registry` or `env`;
  - a final status line: `CANDIDATES_COMPLETE`, or
    `CANDIDATES_INCOMPLETE:<tier>` when a tier could not be enumerated.

  The tiers are enumerated as follows:
  - **registry:** one Python run imports `agent_launch_utils` and
    enumerates the registry through the Python registry authority behind
    `--list-registry` (every entry with that name). An import error, an
    exception or missing Python yields `CANDIDATES_INCOMPLETE:registry`.
    A missing registry **file** is a definite answer (no registry
    candidates), not an incomplete one.
  - **tmux: a status-bearing query, not `discover_aitasks_sessions()`**
    (third review). That function folds every tmux failure into emptiness:
    a failed `list-sessions` becomes no sessions (`:1234-1235`), a failed
    `list-panes` becomes no pane paths (`:1243`), and a failed
    `show-environment` fallback becomes no root (`_read_registry_entry`,
    `:483-485`). The gateway's `TmuxClient.run()` also drops stderr, so "no
    server" and "query failed" are indistinguishable. A caught exception
    would therefore miss exactly the failures that matter. So:
    - **Gateway (`lib/tmux_exec.py`):** add
      `TmuxClient.run_checked(args, timeout) -> TmuxResult(outcome, rc,
      stdout, stderr)`, with `outcome` ∈ `ok | no_tmux | no_server |
      failed`:
      - `no_tmux` is a `FileNotFoundError` on the binary;
      - `no_server` is rc≠0 with tmux's "no server running" message or an
        "error connecting to … (No such file or directory)" socket-absent
        message;
      - `failed` is everything else: a timeout, an `OSError`, any other
        rc≠0, including a stale socket's "Connection refused". Those fail
        closed.
      - It is an addition: `run()`, `run_async()` and every existing caller
        are untouched. It stays in the sanctioned gateway, so
        `tests/test_no_raw_tmux.sh` holds.
    - **`agent_launch_utils.py`:** factor the discovery body so that one
      implementation runs with a pluggable per-command runner, and add
      `discover_aitasks_sessions_checked() -> (sessions, complete: bool)`.
      The existing `discover_aitasks_sessions()` keeps its current runner
      and its output is byte-identical (pinned by the existing
      `test_discover_default_unchanged.py`, `test_discover_async_parity.py`,
      `test_discover_include_registered.py` and
      `test_discover_session_dedupe.py`). In the checked variant:
      - `list-sessions`: `ok` gives the parsed sessions; `no_tmux` or
        `no_server` gives a **definite** empty (no live session can
        exist); `failed` gives incomplete.
      - per-session `list-panes`: `ok` gives paths; a "can't find session"
        rc (the session vanished after listing) means the session is gone
        and is skipped; anything else gives incomplete.
      - `show-environment -g AITASKS_PROJECT_<s>` fallback: `ok` is parsed;
        rc≠0 with tmux's "unknown variable" message is a definite absence;
        anything else gives incomplete.
      - The tmux stderr message patterns are measured against the installed
        tmux into a pinned table during implementation, not guessed (per
        the "measure lexical rules" convention).
    - The resolver's `candidates` mode uses the checked variant and matches
      every `project_name` or `session` equal to the name, not only the
      first. `complete=False` gives `CANDIDATES_INCOMPLETE:tmux`. A Python
      import failure gives the same, because the named resolve's tmux tier
      also needs Python and a conflict cannot be ruled out.
  - **env:** read in bash (`AITASKS_PROJECT_<name>`), so it can never be
    incomplete.
  - The existing named resolve, `list`, and their output are untouched.
  - The test seam `AIT_PROJECT_RESOLVE_ENUM_FAIL=<tier>` forces the
    incomplete branch.
- **Note-side decision**, given the candidates, with paths compared
  canonically (`cd … && pwd -P`):
  - Any `CANDIDATES_INCOMPLETE:<tier>` gives
    `project-resolution-incomplete:<tier>`. It fails closed and is never
    read as "zero candidates in that tier, so unambiguous". This
    generalizes finding 3 to every tier.
  - No candidates at all gives `project-not-found:<n>`.
  - More than one distinct canonical path across all candidates (duplicate
    registry entries, two live sessions matching, or tiers disagreeing)
    gives `project-ambiguous:<n>`. The distinct paths go to stderr so the
    user can fix the registration.
  - Exactly one distinct path, but STALE, gives `project-stale:<n>`.
  - Exactly one distinct path, RESOLVED, gives that path as the root.
    Several tiers agreeing on the same path is fine.
  - The resolver script or the candidates mode being missing or
    unparseable (an older framework) gives
    `project-resolution-incomplete:resolver`.
- **Test seams:** `AIT_PROJECT_RESOLVE_SH` (resolver path) and
  `AIT_PROJECT_RESOLVE_ENUM_FAIL`. Neither is set in normal operation.
- The same function serves the target (caller side), the `--from-project`
  forward check (both sides), and the target helper's resolution of the
  source project.

### Surfacing
`aitask_query_files.sh inbox` already passes `from` through raw, so a note
shows as `proj#t7` and is never mistaken for a local `t7`. The shared display
wording in task-workflow Check 6, the pick Step 0b and the rendered variants
gets one line: "a `<project>#t<id>` sender is a task in another repository."
The display procedure itself does not change.

## Implementation steps

### Pre-phase (risk mitigations)
1. [baseline_note_suites] Before any edit, run `tests/test_note_append.sh`,
   `test_note_read_receipts.sh`, `test_note_with_live_composition.sh`,
   `test_note_section_order.sh`, `test_note_doc_contract.sh`,
   `test_live_endpoint_degradation.sh`, `test_inbox_surfacing_render.sh` and
   `python3 tests/test_inbox_union_roundtrip.py`. Record their PASS counts in
   the plan. Treat every pre-existing failure as baseline, so the post-change
   run can separate regressions from noise.

   **Baseline recorded (2026-09-23, before any edit) — all green:**
   test_note_append 121/121 · test_note_read_receipts 74/74 ·
   test_note_section_order 20/20 · test_note_doc_contract 7/7 ·
   test_inbox_surfacing_render 48/48 · test_note_with_live_composition ALL
   PASSED · test_live_endpoint_degradation ALL PASSED ·
   test_inbox_union_roundtrip rc=0 · test_project_resolve 6/6 ·
   test_project_resolve_list 6/6 · test_agent_instructions all passed ·
   pytest test_tmux_exec 46 · test_discover_default_unchanged 4 ·
   test_discover_async_parity 1 · test_discover_include_registered 13 ·
   test_discover_session_dedupe 1.

### Main steps
0a. **`lib/tmux_exec.py` + `lib/agent_launch_utils.py`:** add
   `TmuxClient.run_checked` and `discover_aitasks_sessions_checked()` as
   described under "Resolution rule". Read `aidocs/framework/tmux_gateway.md`
   first. Tests:
   - `tests/test_tmux_exec.py`: `run_checked` classification, using
     fake-binary and stubbed subprocess outcomes for each of `ok`,
     `no_tmux`, `no_server`, `failed` (timeout, other rc, connection
     refused);
   - a new `tests/test_discover_checked.py`: the per-command dispositions
     above;
   - the existing discovery tests must stay green, unchanged.
0. **`aitask_project_resolve.sh`:** add the additive `candidates <name>`
   mode described in "Resolution rule". Update the header comment and
   `--help`. Add cases to `tests/test_project_resolve.sh`:
   - every tier listed;
   - duplicate registry names listed separately;
   - two matching tmux sessions (through a stubbed checked-discovery under
     an import-path seam, the same way the existing resolver tests stub it;
     reuse their pattern);
   - **a tmux query failure is distinct from an empty server**: a stub
     runner whose `list-sessions` returns `failed` gives
     `CANDIDATES_INCOMPLETE:tmux`, even with a valid registry candidate.
     `no_server` and `no_tmux` give `CANDIDATES_COMPLETE` with the registry
     candidate. A `list-panes` failure and a `show-environment` failure
     (not "unknown variable") each give `CANDIDATES_INCOMPLETE:tmux`. A
     vanished session and an unset variable stay complete.
   - `CANDIDATES_INCOMPLETE:<tier>` under `AIT_PROJECT_RESOLVE_ENUM_FAIL`;
   - a missing registry file is `CANDIDATES_COMPLETE` with no registry
     candidates;
   - byte-identical named-resolve and `list` output before and after.

   Document the mode in `aidocs/framework/cross_repo_references.md`
   Resolver.
1. **`lib/lock_record.sh`:** add an optional `<project-root>` argument to
   `lock_record_read`. When it is given, run
   `(cd "$root" && "$root/.aitask-scripts/aitask_lock.sh" --check "$bare")`.
   Update the header comment.
2. **`aitask_note.sh`:**
   - add `note_project_resolve`, `note_source_project` (the reverse lookup)
     and `note_xrepo_route` (caller-side routing, path rewriting and exit
     passthrough);
   - dispatch at the top of `main()` and `note_read_main` when `--project`
     is present, before the existing parsers run;
   - add the `--from-project` write option, which is counted, refused with
     `--migrate` and refused without `--from`;
   - add a `note_sender_is_self_in` wrapper around the existing
     `note_sender_is_self` logic, with an optional root;
   - extend `show_help` with the new grammar, the new `NOTE_ERROR` reasons
     and a cross-repo example. The help must contain the literal
     `--from-project` token, because that is the capability probe.
   - Test seam: `AIT_PROJECT_RESOLVE_SH` (the resolver, defaulting to
     `$SCRIPT_DIR/aitask_project_resolve.sh`). Resolution goes only through
     the resolver's new `candidates` mode, never through `list` or a single
     named resolve.
   - Add a `note_route_die <verb> <reason>` helper, which prints the
     `NOTE_ERROR:` or `READ_ERROR:` line, so no routing failure can use the
     wrong family.
3. **`ait`:** update the `note` help line to mention `--project`.
4. **Skill: `.claude/skills/aitask-note/SKILL.md`** (a static skill, not
   `.j2`):
   - "Note, or a new task?": add the cross-repo case. A note is the right
     tool when direct edits in a foreign repo would be too intrusive. If the
     content is work, create a task there instead (`ait create --batch
     --project`).
   - Step 1: add a "target in another repository" branch. It needs an
     explicit `--project <name>` and an explicit id, because Related Task
     Discovery is local-only and never runs across repos. Validate with
     `./ait projects resolve <name>` and
     `./ait projects exec <name> ./.aitask-scripts/aitask_query_files.sh resolve <id>`.
     Source identity comes from the registry; use `--from-project` only
     when the error asks for it.
   - Step 2: show the `--project` command and the new failure reasons.
   - Step 4: say that cross-repo provenance may be unverified and is still
     only a claim; that a durable append is success whatever the live lane
     says; and that the note must be reported without claiming it was read.
   - Headless: an explicit target plus `--project` asks nothing. Local
     callers don't change.
5. **Wrappers:** update `.agents/skills/aitask-note/SKILL.md`'s own
   `## Arguments` prose. `.opencode/commands/aitask-note.md` and
   `.opencode/skills/aitask-note/SKILL.md` only include or point, so check
   them and edit only if they restate the grammar.
6. **`seed/aitasks_agent_instructions.seed.md` "Sending Notes to Other
   Tasks":** add a cross-repo bullet with a `--project` example, the
   source-identity rule and the provenance caveat. Then regenerate
   `AGENTS.md` and its mirrors through the repo's own assembly path (the
   one T25-T27 check), and extend T44 in `tests/test_agent_instructions.sh`
   to pin `--project` and "another repository".
7. **Call sites:** task-workflow Check 6 and pick Step 0b (the
   `.claude/skills/*` sources plus `.md.j2` where applicable) get one
   sentence each on how a `<project>#t<id>` sender is displayed. Then
   regenerate the goldens (`aitask_skill_verify.sh` plus the golden
   regeneration step) in the same commit.
8. **Docs:**
   - `website/content/docs/commands/note.md`: the new grammar for write and
     `read`, the target/source resolution rules, the failure table, absolute
     paths in id-bearing lines, provenance meaning, and an example. Replace
     line 41's "a cross-repo reference is rejected" with the current
     behaviour.
   - `website/content/docs/skills/aitask-note.md` and
     `website/content/docs/workflows/task-notes.md`: agent and workflow
     usage, plus a statement that a note is a structured Inbox modification,
     not a side channel, and changes nothing about requirements, state or
     authority.
   - `website/content/docs/workflows/multi_project.md`: a short "Sending a
     note to a sibling project's task" subsection linking to `note.md`, so
     the rules aren't duplicated.
   - `aidocs/framework/task_note_mailbox.md`: replace the "`--from` is
     local-only" constraint with the cross-repo contract (qualified sender,
     proof across repos, target-checkout provenance, no schema change).
   - `aidocs/framework/cross_repo_references.md` Consumers: add `note
     --project`.
   - `aidocs/framework/live_endpoint_resolution.md`: one line saying the
     live lane runs in the target repo on this host and cross-host delivery
     stays out of scope.
   - Use `relref` for internal links.
9. **Tests: new `tests/test_note_cross_repo.sh`.**
   - **Fixture (review finding 4):** SRC and TGT are both built with
     `tests/lib/sync_fixture.sh::setup_repo`. That gives the **production
     topology**: a bare remote, a clone with a real `.aitask-data` worktree
     on the orphan `aitask-data` branch, `aitasks/` and `aiplans/`
     symlinks, and each repo's **own** copied `.aitask-scripts`, `ait` and
     an initialized `aitask-locks` branch. So `task_git` runs in branch
     mode, not legacy mode.
   - Each repo also gets `.aitask-data/aitasks/metadata/project_config.yaml`
     (committed on its data branch) so the resolver treats it as a valid
     root, plus a same-numbered task `t700` in both repos.
   - Isolation: a private `AITASKS_PROJECTS_INDEX`, `AITASKS_LOCK_DIR` and
     the fixture's `AITASKS_TMUX_SOCKET`, with unique project names so the
     tmux tier cannot match.
   - A legacy-mode pair (plain clones, the `test_note_append.sh` shape) is
     kept for one smoke case only, to prove routing does not depend on
     branch mode. The incompatible-target case uses a third stub repo
     whose `aitask_note.sh` help lacks the probed tokens.

   Cases:
   - **Target-data-branch placement.** The write lands only in TGT's task.
     The new commit is on TGT's `aitask-data` branch (checked with
     `git -C TGT/.aitask-data log -1 -- aitasks/t700_*.md`, whose subject is
     `ait: Record note <id> for t700`) and is pushed to TGT's remote
     `aitask-data`. TGT's `main` does not move, and SRC's `aitask-data`,
     `main` and same-numbered `t700` are all unchanged. The receipt test
     makes the same branch assertions.
   - The stored `from=srcproj#t700`, marker `t700`, and
     `note_inbox.py unread` plus `aitask_query_files.sh inbox` in TGT show
     `srcproj#t700`. `validate_block` accepts the block.
   - Verified vs unverified: with SRC's t700 locked by this session
     (`AIT_AGENT_PID` anchor), `from_verified=yes`; unlocked, the field is
     absent and never `no`.
   - **Write failures**, each with no mutation (TGT byte-identical, no new
     commit on either branch of either repo) and a single `NOTE_ERROR:`
     line:
     - unknown target, stale target, ambiguous target (a duplicate
       registry name with two paths; registry and env disagreeing);
     - **an incomplete tier while a conflicting candidate would be there**
       (`AIT_PROJECT_RESOLVE_ENUM_FAIL=registry`, and separately `=tmux`)
       gives `project-resolution-incomplete:<tier>`, never a
       resolve-and-send (the fail-closed pin);
     - unregistered source, ambiguous source, `--from-project` mismatch;
     - missing source task, missing target task, `project-is-local`;
     - `--project` with `--migrate`;
     - **`--project A --project B`** gives `duplicate-option:--project`,
       and neither A nor B is touched, even when both are valid registered
       projects. The same applies to a repeated `--from-project`, and to
       `--project` with no value.
     - an incompatible write target (a stub whose help lacks
       `--from-project`).
   - **Read failures** each print one `READ_ERROR:` line, never a `NOTE_*`
     line, and write no receipt: duplicate `--project`, unregistered,
     ambiguous, registry unavailable, and an incompatible target (a stub
     with no `read` verb).
   - **Read against a pre-t1869 helper succeeds:** a stub whose help has the
     `read <task-id> --by` line but no `--from-project`, and which records
     its argv, is invoked with the plain `read` grammar. The route does not
     refuse it (the pin for finding 2).
   - `AIT_DIR` set in the caller env does not leak: `base` equals TGT's
     HEAD.
   - `--file <relative>` resolves against the caller's cwd.
   - Commit failure on the target (git index lock in TGT) returns
     `NOTE_APPENDED_UNCOMMITTED` with an absolute path and a non-zero exit.
   - `read --project`: `READ_RECORDED` with an absolute path; rollback
     under `AIT_NOTE_READ_FAIL_COMMIT` gives `READ_ERROR` with no receipt
     left; `--by` mismatch is refused.
   - `--with-live` with no holder gives `NOTE_APPENDED:` followed by
     `LIVE_NONE:unlocked` and exit 0. With an `AIT_LIVE_ENDPOINT_SH` stub,
     the verbatim pass-through happens only after the append.
   - **Literal option tokens as values** (second review, finding 1):
     - in SRC, `ait note 700 --from 701 --text --project` appends a
       local note whose body is `--project` (one `NOTE_APPENDED:` line with
       a relative path, `from=t701`);
     - the same with `--file --project`, where a file named `--project`
       exists in cwd, reads that file;
     - `--text --from-project` is local too;
     - routed, `ait note 700 --project tgt --from 700 --text --project`
       lands in TGT with body `--project`;
     - `read 700 --by 700 --ids --project` stays on the local path and
       fails exactly as it does today (`READ_ERROR:bad-note-id:--project`),
       not as a route error;
     - an unknown option before `--project` gives the unchanged local
       `unknown-option` error.
   - A local invocation without `--project`, run against the same fixture,
     prints exactly one line and records `from=t701`, same as before.

   The file uses `assert_counters_init` and `assert_counters_load` if any
   body runs in a subshell.
10. **Existing tests:** extend `test_note_append.sh` with two local pins:
    `--from-project` together with `--migrate` is refused, and so is
    `--project` together with `--migrate`. Both check for the typed
    `NOTE_ERROR` and that nothing was mutated.

### Post-phase
None.

## Verification
- `bash tests/test_note_cross_repo.sh`, then every suite from the pre-phase
  baseline; compare against the baseline.
- `bash tests/test_agent_instructions.sh`,
  `./.aitask-scripts/aitask_skill_verify.sh`, and the golden tests.
- `shellcheck .aitask-scripts/aitask_note.sh .aitask-scripts/lib/lock_record.sh`
- `cd website && hugo build --gc --minify && python3 check_links.py --build`
- Manual smoke test against a real registered sibling project, only if one
  is registered here; otherwise the fixture covers it.

## Step 9 reference
Current-branch mode (fast profile): commit the code and the plan separately
in Step 8, then run the `risk_evaluated` gate and archive with
`aitask_archive.sh 1869` in Step 9.

## Risk

### Code-health risk: medium
- `aitask_note.sh` is a heavily contracted script ("one line, always",
  id-bearing terminal outcomes, trap/subshell discipline). Adding routing
  there could perturb the local path. · severity: medium (residual: the
  inline pre-phase baseline_note_suites catches regressions, but does not
  prevent them) · → mitigation: inline pre-phase baseline_note_suites
- `lock_record_read` is shared with `aitask_live_endpoint.sh`, so a changed
  signature could shift the live resolver. Kept additive (optional second
  argument, default path unchanged). · severity: low · → mitigation: none
- The tmux gateway and session discovery are shared by the monitor, the
  board and the switcher. The new checked path is additive; the default
  discovery keeps its runner and is pinned by four existing parity tests.
  · severity: medium · → mitigation: none
- `aitask_project_resolve.sh` gains a `candidates` mode. The named resolve
  and `list` are shared by `ait projects` and `create --project`, and are
  kept byte-identical and pinned by tests. · severity: low · → mitigation: none
- The docs and skill surface is wide (seed, `AGENTS.md` mirrors, goldens,
  website), so drift between surfaces is possible. · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Target-checkout provenance (rather than the sender's tree) is a semantic
  choice the reviewer may reject. It is stated explicitly in the plan and
  docs. · severity: medium · → mitigation: none
- The "ambiguous" definition is invented here (the resolver has none):
  duplicate registry names, or tmux/registry disagreement. It could be
  stricter or looser than intended. · severity: low · → mitigation: none
- Failing closed on an incomplete tier means that a machine where the
  Python enumeration cannot run (a broken venv) refuses cross-repo notes,
  even though the named resolve would have fallen through to
  registry or env. This is deliberate: a conflict there cannot be ruled
  out. `ait setup` repairs the venv, and the error names the tier.
  · severity: low · → mitigation: none
- Proof across repos depends on the target child sharing the caller's
  session anchor. The anchor is correct under tmux or `AIT_AGENT_PID`;
  anywhere else it degrades to unverified, which is fail-safe. · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: baseline_note_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: aitask_note.sh local-path regression | desc: Record PASS counts of every note/inbox suite before editing, for a regression-vs-noise comparison

## Implementation progress (2026-09-23)

All steps implemented (pre-phase baseline, 0a, 0, 1-10). Deviations from the
plan as approved:

- **Added a second resolver mode, `bindings <path>`.** The source-identity
  reverse lookup needed a *completeness-bearing* enumeration of declared names
  (registry + `AITASKS_PROJECT_*`); the plan said "from the complete
  enumeration" but only `list` existed, which folds a missing interpreter into
  empty output. `bindings` uses the `--list-registry` exit status as its
  completeness witness (`BINDINGS_INCOMPLETE:registry`).
- **tmux target form in the checked walk.** Measured on tmux 3.7c: `list-panes
  -s -t =<session>` resolves `=<session>` as a WINDOW and falls back to the most
  recent session, so with two sessions every session reports the same panes.
  The checked discovery passes `=<session>:` via a new `pane_target` parameter
  on the shared `_collect_live_roots`; the default discovery keeps the historical
  form byte-for-byte. The colon-less form is used at 8 call sites across
  `agent_launch_utils.py`, `agent_freeze.py` and `monitor/monitor_core.py` —
  a pre-existing defect outside this task (recorded under Upstream defects).
- **Help-text command substitution caught by shellcheck.** `show_help` is an
  unquoted heredoc; a backticked `ait projects resolve` in the new help would
  have executed on every `--help` (including the capability probe). Replaced
  with plain quotes and pinned by test 0c.
- **`tests/test_note_append.sh:326` unlock order** — `aitask_lock.sh 701
  --unlock` is parsed as the bare-id LOCK shortcut, so the old cleanup never
  unlocked. Fixed to `--unlock 701` while adding the §15 pins.
- **Committed pre-renders** (`task-workflow-remote-` under `.claude`,
  `.agents` (codex) and `.opencode`) were refreshed by the render tests with
  exactly the one added sentence; included.

Verification: every suite from the baseline green post-change, plus
test_note_cross_repo 121/121, test_note_append 124/124, test_project_resolve
16/16, test_discover_checked 10, test_tmux_exec 57, test_agent_instructions
156/156, render suites (task_workflow 337, pick 209, pickrem 67, pickweb 86),
test_no_raw_tmux, test_create_project_flag 34, test_projects_cmd 42,
test_registry_reader_parity 30, full Python suite PASSED, `aitask_skill_verify.sh`
OK, shellcheck clean at warning level, `hugo build` + `check_links.py --build`
SWEEP PASSED. Two isolated mutants (raw-argv routing; proof against the wrong
repository) each turned the corresponding pins red.

## Post-Review Changes

### Change Request 1 (2026-09-23 17:10)
- **Requested by user:** (1) registry enumeration reported complete after an
  unreadable registry, because `_parse_registry_records()` folds `OSError`
  into `[]` — both `candidates` and `bindings`; test with a REAL unreadable
  file. (2) Automatic sender selection swallowed forward-resolution failures
  and reported `source-unregistered`. (Finding 1 was also delivered by a peer
  session and as a note on t1869.)
- **Changes made:** `_parse_registry_records_strict()` (raises on any read
  failure; a missing file stays a definite empty) with the permissive reader
  now a thin `except OSError: return []` wrapper — byte-identical for existing
  callers; new `--list-registry-strict` CLI (exit 3, no partial output);
  `candidates` and `bindings` read strictly. `note_source_project` keeps the
  first failure reason of a declared name (`project-ambiguous:` /
  `project-resolution-incomplete:` / `bad-project-name:`), reserving
  `source-unregistered` for "no declared name at all". Tests: chmod-000 and
  directory-at-path registries in `test_project_resolve.sh` (22/22) and
  end-to-end in `test_note_cross_repo.sh` (125/125, incl. the sender-conflict
  outcome); a permissive-reader mutant turns the new pins red.
- **Files affected:** `.aitask-scripts/lib/agent_launch_utils.py`,
  `.aitask-scripts/aitask_project_resolve.sh`, `.aitask-scripts/aitask_note.sh`,
  `tests/test_project_resolve.sh`, `tests/test_note_cross_repo.sh`,
  `aidocs/framework/cross_repo_references.md`.

### Change Request 2 (2026-09-24)
- **Requested by user:** (1) the strict reader's `os.path.lexists()` gate (and
  the `bindings` shell `-e`/`-L` shortcut) read a registry inside an
  unsearchable directory as absent → `CANDIDATES_COMPLETE` / `BINDINGS_COMPLETE`;
  (2) target-side `--from-project` usable standalone, recording any existing
  foreign project as the sender without checking it is the actual caller.
  (Finding 1 was also delivered by the peer session.)
- **Changes made:** absence is proven with `os.stat()` — only
  `FileNotFoundError` (then `lstat()` to reject a dangling symlink) means
  absent; every other `OSError` propagates as unreadable. The shell shortcut in
  `bindings` is removed; the strict CLI decides. Caller handoff: the routing
  half passes `AIT_NOTE_XREPO_CALLER=<canonical caller root>`; the target's
  `--from-project` refuses without it (`from-project-requires-project`) and
  requires the resolved sender root to equal it (`from-project-mismatch:`).
  Tests: unsearchable-parent and dangling-symlink registries
  (`test_project_resolve` 25/25), end-to-end unsearchable registry, standalone
  and forged-handoff `--from-project` (`test_note_cross_repo` 131/131). Mutants
  (lexists gate restored; handoff check removed) turn 2 + 5 pins red.
- **Files affected:** `.aitask-scripts/lib/agent_launch_utils.py`,
  `.aitask-scripts/aitask_project_resolve.sh`, `.aitask-scripts/aitask_note.sh`,
  `tests/test_project_resolve.sh`, `tests/test_note_cross_repo.sh`,
  `website/content/docs/commands/note.md`,
  `aidocs/framework/task_note_mailbox.md`, `aidocs/framework/cross_repo_references.md`.

## Final Implementation Notes
- **Actual work done:** Additive `--project <name>` routing for `ait note` and
  `ait note read`. The caller half (option-aware pre-scan, typed per-verb
  refusals, target/source resolution, per-verb capability probe, `--file`
  absolutization, env scrub + `AIT_NOTE_XREPO_CALLER` handoff, absolute-path
  rewrite) runs the TARGET repository's own `aitask_note.sh`; the target half
  (`--from-project`) re-resolves, requires the handoff to match, checks the
  source task exists, stores `from=<src>#t<id>` (marker `t<id>`) and proves
  `from_verified=yes` against the SOURCE repository's own lock. Resolver gained
  `candidates <name>` and `bindings <path>`; the tmux gateway gained
  `TmuxClient.run_checked` + a pinned stderr table; discovery gained
  `discover_aitasks_sessions_checked()` over a shared `_collect_live_roots`;
  the registry gained `_parse_registry_records_strict()` /
  `--list-registry-strict`; `lock_record_read` an optional project root. Skill,
  wrappers, seed + regenerated AGENTS.md mirrors, pick/task-workflow display
  sentence + goldens, website (command, skill, workflow, two concept pages,
  multi-project) and aidocs (mailbox, cross-repo, live-endpoint) updated.
- **Deviations from plan:** added `bindings` mode; checked tmux walk targets
  `=<session>:`; strict registry reader (two review rounds); caller handoff for
  `--from-project`; test_note_append unlock-order fix. See "Implementation
  progress" and "Post-Review Changes" above.
- **Issues encountered:** shellcheck caught a backtick command substitution in
  the unquoted `show_help` heredoc (would have executed on every `--help`,
  including the capability probe) — fixed and pinned (test 0c). `aitask_lock.sh
  <id> --unlock` is the bare-id LOCK shortcut, not an unlock.
- **Key decisions:** provenance (`base`/`dirty`) describes the TARGET checkout;
  every resolution tier is kept (CI env override works) but any conflict or
  unreadable tier fails closed; sender name comes only from declared bindings
  (registry / env), never a tmux session name; the read path probes only the
  existing receipt grammar so pre-t1869 targets still acknowledge.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/agent_launch_utils.py:1300 — list-panes -s -t =<session> (colon-less, the default pane_target of _collect_live_roots) resolves as a WINDOW on tmux 3.7c and falls back to the most recent session, so discover_aitasks_sessions() maps every live session to the same project root when several sessions run; same colon-less target at agent_launch_utils.py:1385,1895, agent_freeze.py:954, monitor/monitor_core.py:2564,2586,2616,2637`
