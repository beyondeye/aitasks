---
Task: t2076_daemon_routed_codex_pane_conversation_mapping.md
Base branch: main
Output branch: main
---

# t2076: Attribute a daemon-routed codex conversation to its pane

## Context

A codex TUI started by hand without `-c tui.alternate_screen=never` is routed through the shared app-server daemon. The framework then cannot tell which conversation belongs to which pane:

- the TUI holds no rollout, so `codex_session_for_pid` returns `MISS_NO_MATCH`;
- the daemon holds every routed rollout, so membership proves nothing;
- since t2047 the hook records nothing for these sessions.

Such an agent can only be re-picked. This task adds positive, pane-specific evidence, so the freeze records each daemon-routed pane's **current** session and a restore resumes it. The realistic target is a bare `codex`: no `-m`, no `AITASK_AGENT_STRING`, no prior store record.

### Evidence design (chosen by user, hardened over three review rounds)

Session X is attributed to a pane only when **all** of these hold.

1. **Claim (pane title).**
   - Codex ≥0.160 has a `[tui] terminal_title` item, `thread-id`, and `ait setup` seeds it into the project config.
   - The last segment of `#{pane_title}`, split on the measured separator, must be exactly one UUID.
   - A config-layer check is a cheap **pre-filter** only: every readable layer that defines `terminal_title` must end in `project-name, thread-id`.
   - **Neither the title nor the config binds by itself.** Config can be edited after launch, and a title can be overwritten.
2. **Current-conversation tie (binding).** X must be the **current main conversation of the live TUI process incarnation**, according to codex's own log store (`$CODEX_HOME/logs_*.sqlite`, rows `process_uuid = pid:<pid>:<uuid>`). Precisely:
   - **Incarnation binding (unconditional).** Use only rows of the one `process_uuid` that belongs to the live process. If Step 0 finds the live process's uuid exposed anywhere (M15), bind by exact uuid. Otherwise bind by time: keep rows with `ts + ts_nanos·1e-9 ≥` the process start time (`/proc/<pid>/stat` starttime / `CLK_TCK` + `/proc/stat` btime). Then require **exactly one** distinct `process_uuid` among them, and require that uuid to have **no** row before the start time. Otherwise decline. An earlier incarnation with the same numeric pid contributes nothing.
   - **Current, not historical.** Classify each row's `thread_id` as main or subagent from that thread's rollout `session_meta` (M16 measures the field). A thread that cannot be classified means decline. The current main conversation is the `thread_id` of the incarnation's **most recent main-thread row**, by `(ts, ts_nanos, id)`. X must **equal** it. Membership in history is never enough.
   - **Transition guard (runtime evidence, never timing).** Between a switch from X to Y (`/new`, `/resume`, any conversation change) and Y's first log row, the latest main row still says X. A stale or forged title naming X would then pass clauses 1–3. Waiting a bounded time T for Y to log does **not** close this window. Neither does a settle-and-recheck delay: both are timing bounds, not evidence, and both are rejected. Attribution therefore also requires a runtime signal that is observable **at the freeze instant** and shows no transition is unresolved, so the freeze declines anywhere inside the window. M18 searches for such a signal. Candidates:
     - the daemon releasing X's rollout no later than the switch becomes observable anywhere;
     - a per-incarnation log row written synchronously at the switch, with or without a `thread_id`;
     - a `loaded-threads.json` or fd/socket change on the TUI or daemon at the switch.

     The signal is proven only by running the probe **continuously across real transitions**, with the title forced to name X from before the switch until after Y's first row (M14). **No such signal → the design stops.**
3. **Corroboration (daemon).** The verified daemon (pid file + `processIdentity` + argv, as in hook §5b forms b/c) holds X's rollout open.
4. **Model.** When argv names no model and the record has no codex label, take the model from the last `turn_context.model` in X's rollout (measured: every turn writes it). Resolve it through the existing exact `AGENT_STRING:` registry match. An unmappable model means no capture, never a wrong launcher.

If Step 0 cannot establish clause 2 — current-thread evidence bound to the live incarnation — **the work stops**. The evidence is reported, and the user is offered closure or re-scoping.

Rejected alternatives:
- sock_diag: no per-connection thread query exists.
- Seeding `alternate_screen="never"`: it avoids daemon routing rather than attributing it.

Work happens on the current branch with no worktree. The worktree is shared and dirty with another session's goengines and test edits, so every commit names its paths.

## Pre-phase (risk mitigations)

### Step 0 — `daemon_title_feasibility_probe`: go/no-go spike, before any code

Setup:
- codex 0.163.0 in an isolated tmux (`-L t2076probe`);
- a throwaway `CODEX_HOME` (a copied `auth.json`) and a scratch project with a trusted `.codex/config.toml`;
- real turns, with every pane started as a **bare** `codex`;
- a scratchpad prototype, `probe_attrib.py`, implements clauses 1–3 exactly as Implementation §1 specifies, so its verdicts preview the real reader.

Keep the raw outputs (ps/fd listings, title samples, daemon.pid, log rows with uuid/ts, `session_meta` and `turn_context` lines) for the Final Implementation Notes.

| # | Measurement | Pass criterion (pre-registered) |
|---|---|---|
| M0 | fds of a daemon-routed TUI after one turn | Record any thread-named file it holds. **If found → stop and re-plan around it** |
| M1 | Default title, nothing configured | Record the default items and the separator. Seed = defaults + `"thread-id"`, ending `project-name, thread-id` |
| M2 | One pane, seeded, one turn | Daemon-routed. Last title segment = its id. Also record the title before the first turn |
| M3 | Panes A and B, one turn each | Each pane's last segment is its own id; the daemon holds both rollouts |
| M4 | `/new` in A, one turn | Last segment = new id, held by the daemon |
| M5 | A's thread renamed to a long name containing B's UUID | Full id survives as the last segment; the probe yields A |
| M6 | Exit A's TUI | The daemon closes A's rollout fd. Record the delay. Also record whether the daemon still holds X after `/new` away from X (feeds M17) |
| M7 | Bare codex started in a pane whose stale title ends in a daemon-held id | Codex rewrites the title before any turn |
| M8 | In-process `codex resume <idA> -m <model>` + `CODEX_TUI_OVERRIDES`, with the daemon alive | Succeeds and holds A's rollout. No thread-writer-lock refusal |
| M9 | codex 0.153.4 and 0.155.1 with the seeded key | No hard config error |
| M10 | **Forged title, parser-valid**, naming B (A never handled B): A's config passes; codex's `!` escape prints `\033]2;<x>⟨sep⟩<proj>⟨sep⟩<B>\007`. Sample `#{pane_title}` every 20 ms for 10 s and run the probe on **every** sample | **Any** sample attributed to B → stop |
| M11 | Layer precedence: a user list without `thread-id` + the seeded project layer | Record the winner. The pre-filter declines regardless |
| M12 | Log rows: during M3/M4, the TUI incarnation's rows (bound per clause 2), plus the daemon pid's rows | Usable iff each TUI writes rows of its own; their `thread_id`s include its current id and **never** the other pane's id. Record subagent ids and timing |
| M13 | **Launch-before-setup:** A is started unseeded with a list ending in `thread-title`; A's thread is renamed `…⟨sep⟩<proj>⟨sep⟩<B>`; then the seeded project config is written while A lives. Run the probe | Must decline. Any B attribution → stop |
| M14 | **Transitions under a forged previous-thread title:** in A, run (i) `/new` with no turn, (ii) `/resume` of an older thread, (iii) switching back, (iv) `/new` followed by a turn. For each, start a forcer **before** the switch that rewrites A's title every 5 ms to a parser-valid title naming the **previous** daemon-held thread X. Run the full probe (clauses 1–3 + the M18 guard) every 20 ms from 2 s before the switch until 10 s after Y's first log row (or 30 s if none). Repeat each transition ≥5 times. Also record the same run with the genuine title, no forcer | Every sample **after the switch keystroke** must decline. Samples before it may accept X, which is still current. **Any accept after the keystroke → stop.** Record each transition's lag until Y's first row, for information only: it is not a pass criterion |
| M15 | **Process uuid exposure:** search the live TUI's environ, its open fds, its `codex-arg0*` temp dir, and its first log rows for its own `process_uuid` | If found: bind by exact uuid. If not: time-binding, as in clause 2 |
| M16 | **Main vs subagent:** spawn a subagent in A (a prompt that delegates); record `session_meta` (`source`, `thread_source`, `originator`) for the main and subagent rollouts, and whether subagent rows carry the TUI pid | Usable iff the field distinguishes them in all observed cases. If it does not → stop |
| M18 | **Transition-guard signal search:** during M14's transitions, record at ≤5 ms resolution:<br>• whether and when the daemon closes X's rollout fd;<br>• every incarnation log row (including `thread_id IS NULL`) with its `ts`;<br>• `app-server-daemon/loaded-threads.json` contents;<br>• fd and socket changes on the TUI and the daemon.<br>Align them to the switch keystroke | A signal qualifies only if it is observable no later than the switch is observable anywhere, and if, used as the guard (decline while it shows an unresolved switch), M14 has **zero** accepts after the keystroke. Choose the single simplest qualifying signal. If none qualifies → **stop** |
| M17 | **Previously visited thread control:** after M14, A's history holds X (old) and Y (current); the daemon still holds X if M6 says so. Forge a parser-valid title naming **X**, sampled as in M10. Repeat with a title naming A's **subagent** thread | Every sample declines. Any attribution of X or the subagent → stop |

Decision rules (pre-registered):

- **Go** only if all of these hold:
  - M0 negative;
  - M2–M5, M8, M12, M16 and M18 pass;
  - M14 has zero accepts after the keystroke;
  - M9 shows no hard error;
  - M10, M13 and M17 produce **zero** wrong attributions.
- **Stop and report**, proposing closure or re-scoping:
  - M12, M16 or M18 fails, or M14 has any accept after the keystroke: no usable current-thread evidence;
  - M10, M13 or M17 attributes anything wrong;
  - any other unexpected failure.
  Never treat historical membership as binding, and never improvise another source.
- **M0 positive** → stop and re-plan around the fd.
- **M9 fails** → opt-in variant: the same reader, no seed or setup change, and a report to the user first.
- **M6 fails** → go only if M7 passes.

**Step 0 checkpoint (NON-SKIPPABLE, before any code).** Present the Step 0 report to the user via `AskUserQuestion`:
- every measurement's raw evidence;
- the go or stop verdict under the rules above;
- on go, the concrete M18 guard signal and its exact decline rule, which become `codex_transition_unresolved()` in §1.

The options are: "Proceed with this guard", "Stop: record findings and close/re-scope", "Revise". No code is written until "Proceed" is chosen. On "Stop", the measurements go into the plan's Final Implementation Notes, and the task is handled as the user directs.

## Implementation

This section assumes "go". The binding mode (exact uuid vs time) follows M15.

### 1. `.aitask-scripts/lib/agent_sessions.py`

- **Extract the fd scan** into `_codex_rollouts_held(pid, proc_root) -> dict[str, list[Path]] | None`. Today's rules stay exact; `codex_session_for_pid` uses it with no behaviour change.
- **`_codex_home_for(pid, proc_root, home)`**: read the TUI's `CODEX_HOME` via `process_environ_value`. `""` → `home/.codex`. None → None, reported as `MISS_NO_PROCESS`.
- **`_process_start_epoch(pid, proc_root) -> float | None`**: stat field 22 / `os.sysconf("SC_CLK_TCK")` + `btime` from `{proc_root}/stat`. Returns None on any failure.
- **`codex_daemon_pid(codex_home, *, proc_root) -> int`**: verify the daemon (`daemon.pid` JSON, `bootId` vs `{proc_root}/sys/kernel/random/boot_id`, `startTicks` vs stat field 22, argv `codex app-server … --managed-daemon`). Same rules as hook §5b b/c, cross-referenced.
- **`codex_title_thread_id(title) -> str`**: the last separator segment if it is exactly a UUID, else `""`.
- **`codex_title_config_prefilter(pid, codex_home, *, proc_root, etc_root="/etc") -> bool`**: the config-layer pre-filter of clause 1. The docstring says it is never binding.
  - Layers: every `terminal_title` key at any depth in `/etc/codex/{config,managed_config}.toml`, `$CODEX_HOME/{config,managed_config}.toml` and every `.codex/config.toml` from `/proc/<pid>/cwd` up to `/`, plus argv `-c`/`--config` overrides.
  - It needs at least one definition, and every definition must end in the pair. `-c tui=…` or any read/parse failure → False.
- **`codex_rollout_kind(path) -> str`**: `"main"` / `"subagent"` / `""` from `session_meta`, per M16's measured field.
- **`codex_current_main_thread(pid, codex_home, *, proc_root, home) -> str`**: clause 2, exactly.
  1. Open the newest `logs_*.sqlite` read-only (URI `mode=ro`, short timeout). Check the schema has the `ts`, `ts_nanos`, `thread_id` and `process_uuid` columns.
  2. Select rows `WHERE process_uuid LIKE ? ESCAPE '\'` with the pattern `pid:<int>:%`.
  3. Bind the incarnation: by exact uuid (if M15 found one), or else by time — start epoch, exactly one uuid after it, and no row of that uuid before it.
  4. Walk the incarnation's non-null `thread_id` rows newest first. Locate each thread's rollout (daemon-held fds first, then the session store by id). Classify it:
     - `""` → return `""`;
     - `"subagent"` → skip;
     - the first `"main"` → return it.
  5. Return `""` on any failure.
- **`codex_daemon_session_for_pane(pid, pane_title, *, proc_root="/proc", home=None, etc_root="/etc") -> (sid, path, miss)`**. Verification happens here, as in `codex_session_for_pid`:
  1. Check the TUI is codex (`NOT_CODEX` / `NO_PROCESS`). If it holds its own rollout, return that in-process answer unchanged.
  2. Run the pre-filter.
  3. Extract the title id.
  4. **`id == codex_current_main_thread(...)`** (binding).
  4b. **`not codex_transition_unresolved(...)`**. This is the M18 guard, whose exact rule is fixed at the Step 0 checkpoint. If it cannot be evaluated, it reports "unresolved", so the freeze declines.
  5. The verified daemon holds the id's rollout.
  6. Return `(sid, rollout_path, "")`.

  Any failure → `MISS_NO_MATCH`, which keeps its t2046 meaning, so it still clears.
- **`codex_rollout_model(path, *, max_bytes=8 << 20) -> str`**: the last `turn_context.model`, read by a bounded backward scan. `""` on miss, cap or error.
- Update the `codex_session_for_pid` docstring paragraph ("re-picked, not resumed").

### 2. `.aitask-scripts/lib/agent_frozen_ops.py`

`pane_title(pane_id) -> str`: one gateway call, `display-message -p -t <pane> '#{pane_title}'`, returning `""` on failure. It is kept out of `PANE_FACT_FORMAT` because titles can contain tabs.

### 3. `.aitask-scripts/lib/agent_freeze.py`

- `_observe_codex_session(pane_pid, root, stored, pane_id="")`:
  - on `MISS_NO_MATCH` with a pane id, call `codex_daemon_session_for_pane(pid, frozen_ops.pane_title(pane_id))`;
  - model order: argv `-m`, then the stored codex label (both unchanged), then **new** `_codex_agent_string(codex_rollout_model(transcript), root)`, on both routes;
  - an unmappable rollout model → `""` (no capture), with `unnameable_model` False.
- Pass `facts["pane_id"]` through `_capture_codex_session` and `_resolve_record`'s unstamped observation.
- Keep the members of `_CODEX_DISPROVING_MISSES` and `_CODEX_FD_DISPROOFS`. Update their comments: `MISS_NO_MATCH` = "no own rollout and no current-thread-bound, daemon-corroborated title claim". The t2046 rules are unchanged (acceptance bullet 2).
- `_backfill_agent_string` is unchanged.

### 4. Hook and comments

`aitask_session_hook.sh` has no behaviour change. Update its DAEMON ROUTING note and the `lib/agent_string.sh` `alternate_screen` comment.

### 5. Seed and setup merge

- `seed/codex_config.seed.toml`: add `[tui] terminal_title = [<M1 defaults>, "thread-id"]` with a t2076 comment. Mirror it in this repo's `.codex/config.toml`.
- `merge_codex_settings`: add a `terminal_title` rule before `deep_merge` (t1944 style):

  | Existing list | Action |
  |---|---|
  | absent | seed list |
  | custom, not ending in the pair | keep its items in order, drop any `thread-id`, append `project-name` (if not already last) and `thread-id` |
  | `[]` | opt-out: untouched, plus an `[ait]` note |
  | already conforming | no-op |

  Also print an `[ait]` note for a non-conforming list in `~/.codex/config.toml`.

### 6. Tests

**`tests/test_agent_sessions_transcripts.py`.** Extend the `write_proc` fixture with `environ`, `stat` (starttime), `cwd`, `{proc_root}/stat` btime, `boot_id`, a `daemon.pid` writer, config layers under fake roots, and a fake `logs_2.sqlite` with the real schema and controllable rows.

- **Title parse:**
  - an exact last segment → the id;
  - a UUID in an earlier segment → `""`;
  - trailing text after the UUID → `""`;
  - no separator → `""`.
- **Pre-filter:**
  - a seeded project layer → True;
  - no layer → False;
  - a user layer ending in `thread-title` → False;
  - a wrong profile-nested list → False;
  - an unparseable layer → False;
  - a wrong `-c tui.terminal_title` → False;
  - `-c tui={}` → False;
  - other `-c` keys → no effect.
- **Current main thread:**
  - one incarnation, rows A → A;
  - **history:** main rows X, then later Y → Y, and a title naming X is declined end-to-end;
  - **transition window:** the fixture state is a switch from X to Y with no Y row yet (shaped from M18's recorded sequence), and a title naming X → declined by `codex_transition_unresolved`. The same state with the guard stubbed out → accepted. That second case is the red control, showing the fixture really exercises the window;
  - **subagent:** the latest row is a subagent S, an earlier main row is A → A, and a title naming S is declined;
  - an unclassifiable latest thread → `""`;
  - **incarnations:** two `process_uuid`s share the pid; the old one (rows before start) names X, the live one names A → A, and X contributes nothing;
  - two uuids after start → `""`;
  - the only post-start uuid also has rows before start → `""`;
  - `pid:12` vs `pid:123` stay separate;
  - start time unreadable, or the DB missing, locked or lacking a column → `""`.
- **Daemon session:**
  - A→A and B→B through one daemon;
  - forged and stale claims:
    - a B title on A (B never handled by A) → `NO_MATCH`;
    - an X title on A (visited earlier and still daemon-held) → `NO_MATCH`;
    - an S title (subagent) → `NO_MATCH`;
    - a config edited after launch (pre-filter passes, current thread mismatches) → `NO_MATCH`;
    - B's UUID in an earlier segment → A;
  - not daemon-held → `NO_MATCH`;
  - a wrong bootId, wrong startTicks, or an argv without the daemon flag → `NO_MATCH`;
  - an in-process rollout → the in-process answer;
  - `NOT_CODEX`, `NO_PROCESS`, and a custom `CODEX_HOME`.
- **Rollout model:**
  - the last `turn_context` wins;
  - none → `""`;
  - the cap → `""`;
  - malformed lines are skipped.

**`tests/test_agent_freeze.py` `CodexSessionCaptureTests`** (patch `codex_daemon_session_for_pane`, `frozen_ops.pane_title` and `codex_rollout_model`):
- a bare, unrecorded, unstamped launch with a proven claim → the upsert carries the session plus `codex/<rollout model>`;
- an unmappable model → no session;
- `-m` and the stored label outrank the rollout model;
- stamped plus a proven claim → recorded;
- a claim miss → clears (the existing t2046 tests unchanged), and the disproved stamp is not re-sent;
- in-process → no title read.

**`tests/test_codex_config_tui_seed.sh`.**
- Group 0 conforms.
- New group:
  - absent;
  - custom (order kept, `thread-id` moved);
  - `[]` plus the note;
  - already conforming → no-op;
  - idempotent;
  - user-level note.

**Red proofs (recorded).** Each must fail exactly its targets:
- current-thread replaced by history membership → the X/S tests fail;
- transition guard forced to "resolved" → the transition-window test fails;
- incarnation binding removed → the incarnation tests fail;
- the parser accepts any UUID → the earlier-segment tests fail;
- daemon corroboration dropped → not-held fails;
- the rollout model removed → the bare-launch test fails.

### 7. Docs

Update `freeze-and-restore-agents.md` (~l.77) and `concepts/framework-session.md` (~l.92–99), current state only:
- a hand-started daemon-routed Codex agent is restorable when the project keeps the seeded title ending (codex ≥0.160);
- the freeze checks that the pane title's thread id is the live codex process's current conversation and that the daemon holds it, and takes the model from the transcript;
- otherwise the agent is re-pick only.

Then run `python3 check_links.py --build` in `website/`.

## Post-phase (risk mitigations)

### `live_two_pane_freeze_restore_check`

Real code paths, Step 0's throwaway `CODEX_HOME`, an isolated tmux, and a scratch store (`AITASK_SESSIONS_FILE`).

1. Start two **bare** `codex` panes, with no `-m`, `-c`, `AITASK_AGENT_STRING`, record or `@aitask_record`. Give each one turn: "remember ALPHA" / "remember BRAVO".
2. Freeze both through the real engine. Each record must hold its own pane's session: the title id, which is also the incarnation's current main thread and daemon-held. Each must also hold `agent_string = codex/<rollout model>`.
3. Restore both. Both must come back **verified**, and "which word?" must answer ALPHA / BRAVO.
4. Negative controls, through the **real freeze path**, with freezes fired repeatedly while each condition is visible. **Any wrong attribution stops the work as a design failure.**
   - (a) M10: a forged title naming B → re-pick only.
   - (b) M13: launch before the setup edit → re-pick only.
   - (c) M17: a forged title naming A's previously visited X, and one naming its subagent S → re-pick only.
   - (c2) M14 through the **real** freeze path: forcer on X, real `/new` in A, and freezes fired repeatedly from the keystroke until after Y's first row → never X.
   - (d) A pane started in a recycled numeric pid is infeasible to force live. The incarnation fixture covers it, and the notes say so.
   - (e) A stale stamp is cleared.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir <dir>` on the touched modules, then the full suite. Read the last-line verdict, with `set -o pipefail`.
- `tests/test_codex_config_tui_seed.sh`, `test_session_hook.sh`, `test_codeagent_resume_session.sh`, `test_skillrun_codex.sh`.
- `shellcheck` on `aitask_setup.sh` and `aitask_session_hook.sh`; `check_links.py --build`.
- The post-phase live check with every negative control.
- Step 9: commit by path (`enhancement: … (t2076)`), commit the plan via `aitask_task_commit.sh`, then archive.

## Risk

### Code-health risk: medium
- The setup merge rewrites every project's `.codex/config.toml` · severity: medium · → mitigation: none (the step-5 rule and seed tests)
- The freeze capture keeps the t2046 rules but widens recording through the model fallback · severity: medium · → mitigation: none (freeze tests, unchanged t2046 tests, red proofs)
- The binding tie reads codex's internal, retention-trimmed log store, whose schema and semantics may change between versions. A change degrades to decline (re-pick), never to a wrong attribution, because the incarnation, classification and current-row rules all fail closed · severity: medium · → mitigation: none (schema checked on read, version recorded, live check)

### Goal-achievement risk: high
The feature may prove undeliverable. Step 0 stops on no current-thread evidence (M12/M14/M16) or on any wrong attribution (M10/M13/M17), and that outcome is reported, not worked around.
- No runtime signal resolves the switch window: the logs give only eventual evidence, so a title naming the previous thread could be accepted mid-transition · severity: high · → mitigation: inline pre-phase daemon_title_feasibility_probe (M14/M18 stop rules + Step 0 checkpoint)
- No per-process current-thread evidence exists · severity: high · → mitigation: inline pre-phase daemon_title_feasibility_probe
- A forged or stale title, a previously visited or subagent thread, a config edited after launch, or an older pid incarnation produces a wrong attribution · severity: high · → mitigation: inline pre-phase daemon_title_feasibility_probe; inline post-phase live_two_pane_freeze_restore_check
- An in-process resume fails while the daemon holds the thread · severity: high · → mitigation: inline pre-phase daemon_title_feasibility_probe
- An older codex hard-errors on the seeded key · severity: medium · → mitigation: inline pre-phase daemon_title_feasibility_probe
- An end-to-end verified restore of two bare, unrecorded panes is required · severity: medium · → mitigation: inline post-phase live_two_pane_freeze_restore_check

### Planned mitigations
- timing: pre-phase | name: daemon_title_feasibility_probe | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: missing current-thread evidence, forged/stale/historical/subagent claims, incarnation reuse, resume, old codex | desc: Go/no-go spike over M0–M17 on real bare codex, with a probe prototype and pre-registered stop rules
- timing: post-phase | name: live_two_pane_freeze_restore_check | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: end-to-end acceptance plus forgery/history/subagent controls | desc: Two bare, unrecorded, daemon-routed panes go through freeze, a per-record session and model check, and a verified restore; the B/X/subagent/launch-before-setup controls run through the real freeze path, and any wrong attribution stops the work

## Final Implementation Notes

- **Actual work done:** Only Step 0 (`daemon_title_feasibility_probe`) ran. It hit a pre-registered **stop**, and the user chose "Record findings and close". No code, seed, setup, test or doc change was made. Daemon-routed codex stays re-pick only, which the website docs already state.
- **Step 0 evidence** (codex 0.163.0, Linux, isolated tmux `-L t2076probe`, throwaway `CODEX_HOME`, bare `codex`, model `gpt-6-luna`, 2026-10-20):
  - **Daemon routing confirmed.**
    - The daemon `…/ch/packages/app-server-daemon/releases/0.163.0-x86_64-unknown-linux-musl/bin/codex app-server --listen … --managed-daemon` holds the rollout `rollout-2026-10-20T15-42-50-01a15955-fea3-71f1-99f7-2690d3ac65d3.jsonl` and `thread-writer-locks/01a15955-….lock`, plus `/tmp/codex-daemon-1000/<hash>.lock`.
    - The TUI process holds neither.
    - `app-server-daemon/loaded-threads.json` did not exist.
  - **M1: pass.**
    - The default title is `[spinner] <thread-title> | <project-name>`, with separator ` | `; the spinner is joined by a space.
    - Before the first turn the title is just `<project-name>`.
    - During the first turn the spinner appears, followed by a placeholder thread title (the spinner glyph) until the title is generated, then e.g. `Remember ALPHA | proj`.
    - The `[tui] terminal_title` item vocabulary (including `thread-id`) is in the 0.160.0, 0.162.1 and 0.163.0 binaries.
  - **M0: negative.**
    - The daemon-routed TUI holds only sqlite stores (`goals`, `logs_2`, `memories`, `queue`, `state_5`, with their `-shm`/`-wal` files), `/dev/pts`, 10 sockets and anon inodes.
    - No fd target or environ entry contains the thread id.
  - **M12: fail (the deciding result).**
    - The TUI process (`process_uuid pid:4032768:c3b20105-…`) wrote 18 rows to `logs_2.sqlite`. All have `thread_id IS NULL`, and no `feedback_log_body` contains the thread id.
    - All 45 thread-bearing rows belong to the daemon pid.
    - Daemon rows identify clients only by an ordinal `connection_id=N` and `client_name="codex-tui"`, with no peer pid or socket.
    - The TUI's `rpc.request_id=startup-thread-start-<uuid>` is not its `process_uuid`.
    - So nothing in codex's log store ties a TUI process to its conversation.
  - **Not run:** M2–M11 and M13–M18. Each depends on a per-process current-thread tie, and M12 showed none exists, so the rules said stop rather than continue.
  - Raw outputs were captured in the session scratchpad (`m0_fds.txt`, `m12_logs_all.txt`, `daemon.pid.json`). The probe tmux server and daemon were stopped, and the copied credentials deleted.
- **Deviations from plan:** None. The pre-registered rule "M12 fails → stop, report, offer closure or re-scope" was applied as written.
- **Issues encountered:** The throwaway config's first model, `gpt-5.4-mini`, is retired. Codex showed a blocking "no longer available" prompt, so the probe used `gpt-6-luna`.
- **Key decisions:**
  - Title attribution was rejected as unsafe without a per-process tie. A pane title is only a claim: three review rounds showed it can be stale, forged, out of date with the config, or name a previously visited or subagent thread. Daemon membership is not attribution.
  - The only remaining paths need a codex-side change: the daemon recording each client connection's peer (pid or socket inode), the TUI exposing its own current thread id to its process (fd, environ or a file), or the daemon running the hook with the client's environment.
  - A future task should start from a codex release that offers one of these, and should re-measure M0 and M12 first.
- **Upstream defects identified:** None
