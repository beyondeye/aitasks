---
Task: t1981_5_relations_consumption.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-08 12:37
---

# t1981_5 — Relations consumption: related-work check, Step 8e, /aitask-note

## Context

This task builds the consumer side of `aidocs/framework/task_relations.md` D8: pull by default, push narrowly. It is the reason the store (t1981_1) and the analysis (t1981_3) exist.

Two constraints from the design are load-bearing:
- **Over-notification is a defect.** Every pushed note is a commit and a push race.
- **Incomplete is never empty.** An incomplete, unverifiable or disabled analysis must never be presented as "no affected targets".

## Verification findings (2026-11-08, against HEAD 620039d7b)

- **Check numbering.** t1663_4 landed the premise check as Step 3 **Check 7** (620039d7b). Check 7 writes nothing before the Step 4 claim. The related-work check therefore becomes **Check 8**, and it must not write task data before the claim either. Its only write is the local `pull.jsonl` ledger under `<git-common-dir>/aitask-relations/`, which is runtime state, not task data.
- **Verbs t1981_3 ships.** `analysis-state <id> [--expect-plan <sha>]`, `analyze <id> --now --wait <s> [--over-cap]`, `stamp`, `plan-digest` and `ledgers --export` all exist (`lib/relations_cli.py`). `ledgers --export` already reads `pull.jsonl` and `notify.jsonl` from `rw.state_dir(root)`.
  - Exit codes and markers: `analyze --now --wait` exits 3 on `WAIT_TIMEOUT:` and on `CAP_REACHED:`. `ANALYZED:t<id>|<outcome>` exits 3 when the outcome starts with `FAILED` / `CAP_REACHED` / `BLOCKED`.
- **`relations_expected_plan` has no producer yet.** t1981_4 sets it (the Step 7 `stamp` call and the Re-entry `plan-digest`), and t1981_4 is pending behind t1981_2. Until it lands, Step 8e omits `--expect-plan` and reads `incomplete:unverifiable(no_expected_identity)`, which the design requires. This task adds the Context Requirements row, so the variable has a declared home. It also notes t1981_4 that the row exists.
- **The static fallback does not exist yet.** `aitask_relation_candidates.sh` (t1981_2) is absent. t1981_2's plan fixes its call shape as `aitask_relation_candidates.sh <id> --fallback-push --changed-file <f>` emitting `UNCONFIRMED:` rows. Step 8e probes for the script and reports "unavailable" when it is absent.
- **The store API this builds on.** `Store.relations(task, snap)` returns `Rel` (with `from_`, `to`, `other`, `type`, `description`, `basis`, `record_task`, `direction`, `freshness`, `pending_push`).
  - `TaskIndex.lookup()` gives `status`, `created_at` and `text`, plus `location` (`active` / `archived`).
  - `archived_reason` and `completed_at` are not parsed. This task reads them from `entry.text` with the same `parse_frontmatter`.
- **Times use different formats.** A record's `run.at` is ISO UTC. Task `completed_at` / `created_at` / `plan_approved_at` and the lock's `locked_at` are local `YYYY-MM-DD HH:MM`. One parser normalises everything to aware UTC (naive means local time).
- **Inbox query.** `aitask_query_files.sh inbox` reports **unread** notes only. A note that was already acknowledged still "covers" a relation. So the "covered by note" mark uses `lib/note_inbox.py` `parse()` / `validate_block()` directly: the same validated parser the query uses, over every non-receipt block.
- **Task data in worktree mode.** `aitasks/` and `aiplans/` are untracked symlinks into `.aitask-data`, so a task worktree has no task data. Step 8e therefore runs the helpers from the main repository root and passes `--rev aitask/<task_name>` in worktree mode. Current-branch mode uses `HEAD`.
- **`aitask-qa` and `aitask-review`** already route note offers through `/aitask-note` (`SKILL.md.j2` lines 75 and 171). With no target, `/aitask-note` now reads the store first, so no change to them is needed (D8).
- **Pick-time cost.** With analysis disabled and no local store branch, `ait relations show --no-fetch` takes 0.45 s. The new verb takes a fast path: when the project is disabled it reads with `no_fetch`. No pick ever pays a network fetch in a disabled project.
- **Goldens.** `SKILL.md` and `planning.md` are Jinja-bearing and profile-varying, so their `tests/golden/procs/task-workflow/*-{default,fast,remote}.md` goldens change, as do the committed remote prerenders (`.agents/skills/task-workflow-remote-codex-/…` and siblings). The new procedure file carries no Jinja and so needs no golden.

## Steps

### Main steps

1. **`lib/relations_consume.py` (new).** This is the deterministic consumer logic. It is read-only except for the two ledgers.
   - **`ChangeSet`** has two modes:
     - **Commits:** `commits_for(root, tid, rev="HEAD")` uses `git log --format=%H%x00%s -z <rev>` and keeps the commits whose **subject** contains the literal `(t<tid>)`. The closing paren stops `(t1981_50)` matching `(t1981_5)`. For each commit it collects:
       - the changed paths, from `git diff-tree -r -M --root --name-status -z --no-commit-id <c>` (both rename endpoints count as changed);
       - the hunk lines, from `git show -U0 -M --format= <c>`: `+`/`-` lines, excluding the `+++`/`---` headers.
     - **Range:** `from_range(root, rng)` does the same over `git diff -M -z --name-status <rng>` / `git diff -U0 -M <rng>`. A range starting with `-` is refused.
     - The `(t<id>)` derivation is cached per id within an invocation, so a landed task's change set is computed once.
   - **`confirm(rel, changeset) -> (status, matched)`** is the one confirmation function, shared by push and pull. Only impact bases count, and `task_ref` never confirms:
     - `path` is confirmed when its `./`-stripped value is in the changed paths;
     - `symbol` is confirmed by an identifier-boundary regex over the hunk lines;
     - `token` is confirmed by a literal substring of the hunk lines.
     - Each match carries its evidence: the commit and the file, for the matched diff evidence.
     - It returns `confirmed_impact` or `unconfirmed_impact`.
   - **`cites_now(target_tid, bases)`** checks the target's current body (`plan_paths.task_body_text`) and current working plan:
     - paths through `plan_paths.find_references` (delimiter-bounded, NFC);
     - symbols by identifier-boundary regex;
     - tokens by substring.
   - **`end_state(index, tid)`** returns one of:
     - `landed(<at>)`: archived, `status: Done`, no `archived_reason`, where `<at>` is `completed_at`, else `updated_at`, else unknown;
     - `dropped(<reason>)`;
     - `implementing`;
     - `plan_holder`: a plan file in the active plan dir, or `plan_approved_at`;
     - `pending`;
     - `other_project`;
     - `unknown`: the index reported errors.
   - **`notify_candidates(store, snap, S, changeset)`** applies D8's push rules in a fixed order. The first failure gives the PULL reason:
     1. type is `affects` or `coordinates_with`, otherwise `type_not_pushed`;
     2. the direction fits, otherwise `reverse_direction`. `affects` needs `from_ == S` and the recipient is `to`; `coordinates_with` takes either end and the recipient is `other`;
     3. the recipient is in this project, otherwise `other_project`;
     4. the recipient is not landed or dropped, otherwise `target_closed`;
     5. at least one confirmed impact basis, otherwise `unconfirmed_impact` (the task-ref-only case included);
     6. the recipient is implementing or a plan holder, otherwise `target_state`;
     7. `cites_now` on a confirmed basis, otherwise `target_moved`.

     **Rule 0, ahead of rule 1:** when `relations_state()` is `disabled`, **every** stored relation becomes PULL `relations_disabled`, whatever its type or evidence. A project that was enabled earlier and then disabled keeps its saved records (`Store.relations` serves them regardless), and those must never become push offers. `host_off` is not disabled: the project still has the layer, only this host's analysis is off.

     The function emits `PUSH` and `PULL` rows and discards nothing.
   - **`related_work(store, snap, T, since, point)`** returns grouped items. Each item carries direction prose, type, `other`, freshness, confirmation (recomputed against L's own `(t<L>)` change set), the other end's state, the archived plan path (via `TaskIndex._find_plan`, for a landed end) and the record `run.at`.
     - **Groups at `point=pick`:**
       - `landed`: the other end landed after `since`, and the edge is incoming (`affects`, `advisory_precedes`, `supersedes`, `informs` with `from = L`) or symmetric (`coordinates_with`, `duplicates`);
       - `dropped`: the other end was archived as superseded or obsolete after `since`;
       - `in_flight`: the other end is Implementing;
       - `own`: an outgoing edge from T;
       - `pending`: everything else.
     - **At `point=review` (Step 8), two groups only:**
       - landed or dropped after `since`, direction-filtered as above;
       - `late`: the record's `run.at` is after `since` and the item is not already listed.

       Each review item is marked `covered_by_note=<id>` when T's `## Inbox` holds a validated note `from=t<other>` with `at` after `since`.
     - **At `point=note`** (the `/aitask-note` sender view), the groups are `in_flight`, `pending` and `own`, with closed ends omitted.
     - **Cap.** At most 8 items, in priority order: `landed` (confirmed first) > `dropped` > `in_flight` > `own` > `pending`. A trailing `MORE:<n>` names the rest.
   - **`plain_summary(relations_state, store_state, analysis_line)`** is the single plain-words renderer for every surface:
     - "relations analysis is disabled in this project — no relation data";
     - "analysis is switched off on this host (AIT_RELATIONS=0) — showing stored data";
     - "the relations store could not be read — related work is unknown, not none";
     - "store data may be stale (last fetched …)";
     - "not analysed yet";
     - "analysed, 0 relations";
     - "analysis queued / running / capped";
     - "analysis failed (<reason>)";
     - "partial coverage" and "stale" suffixes;
     - "another project's task — not checkable here".
   - **Ledgers.** `append_ledger(state_dir, name, row)` writes one JSON line through `O_WRONLY|O_CREAT|O_APPEND` with a single `os.write`, the same pattern as `relations_spool._append`, into `pull.jsonl` / `notify.jsonl`.
     - Every row carries the D13.3 fields: `at`, `host`, `task`, `point` or `run_id`, the relation `{from, to, type, record_task}`, `freshness`, `confirmation` and `outcome`.
     - The Step 8e summary row also carries `analysis_state`, `option`, `record_stage` and the PUSH/PULL counts.
     - Pull rows are skipped only when the project is disabled **and** nothing was shown.
   - **Time parsing.** `parse_time(value)` turns ISO-with-Z or `YYYY-MM-DD HH:MM[:SS]` (naive means local) into aware UTC. Anything unparseable returns None, and the item reads "time unknown" and is **included**, which is the fail-open direction for a display.
2. **Verbs in `lib/relations_cli.py`.** Add the three verbs below to `VERBS` and `USAGE`, and handle them like `analysis-state`: a `ProjectUnresolved` while disabled prints the disabled state lines. Update the header comment in `aitask_relations.sh`.
   - **`related-work <id> --point pick|review|note [--since <ts>] [--log] [--json]`.**
     - **The reference time.** At `pick` it is `plan_approved_at`, else the visible stamp's `approved_at`, else `created_at`. At `review` it is `--since`, else the task lock's `locked_at` (`aitask_lock.sh --check`), else `created_at`. It is reported as `REFERENCE:<iso>|<source>`.
     - **Output.**
       - the D1 state lines (`RELATIONS_STATE:` / `STORE:` / `ANALYSIS:` / `CORRUPT:`);
       - `SUMMARY:<plain words>`;
       - `CHECKED_AT:<iso utc>`;
       - `REFERENCE:`;
       - `ITEM:<group>|<direction>|<type>|<other>|<freshness>|<confirmation>|<end state>|<archived plan or ->[|covered_by_note=<id>]`, with the description on the next line, indented;
       - `MORE:<n>`;
       - `RELATED_WORK:0` when the list is empty, which comes after `SUMMARY:` and never stands alone.
     - Fields are percent-encoded for `%`, `|`, CR and LF (the premise convention).
     - The store is read with `no_fetch` when the project is disabled.
   - **`notify-candidates <S> [--rev <rev> | --diff <range>] [--expect-plan <sha>] [--option <opt>] [--log] [--json]`.**
     - It recomputes the analysis state itself, through the existing `analysis_state()`, rather than trusting a caller string.
     - `--option` takes the closed set `complete` / `disabled` / `wait` / `wait_failed` / `wait_refused_cap` / `fallback` / `fallback_unavailable` / `proceed`. Any other value exits 1.
     - **Output.**
       - the state lines;
       - `ANALYSIS_STATE:<state>`;
       - `RECORD:stage=<n>|<inputs_mismatch or ok>` or `RECORD:none`;
       - `SUMMARY:`;
       - `CHANGESET:<n commits>|<commits:<rev> or diff:<range>>`;
       - `CHANGED_FILE:<p>` lines, which feed the static fallback's `--changed-file`;
       - `RUN_ID:<uuid>`;
       - `PUSH:<to>|<type>|<matched bases>|<description>` with `  EVIDENCE:<kind>:<value>|<commit>|<file>` lines;
       - `PULL:<to>|<type>|<reason>`;
       - and when there are no PUSH rows, `PUSH_NONE:complete` or `PUSH_NONE:incomplete:<state>`. Wording such as "no affected targets" is emitted **only** for `complete`.
     - An empty change set prints `CHANGESET:0|…` with a `WARN:` line. Every relation then becomes PULL `unconfirmed_impact`.
     - **Disabled.** No `PUSH:` row is ever printed. The verb prints `PUSH_NONE:disabled` and `PULL:<to>|<type>|relations_disabled` rows, and still prints `CHANGESET:` / `CHANGED_FILE:` (which the optional static fallback needs), `RUN_ID:` and the summary ledger row (`analysis_state=disabled`).
   - **`notify-outcome <S> --run <id> --to <ref> --type <type|unconfirmed> --outcome sent|declined|not_offered [--note-id <id>]`.** It appends one `notify.jsonl` outcome row. `--type unconfirmed` marks a judged static-fallback row.
3. **The related-work procedure: `.claude/skills/task-workflow/related-work-check.md` (new, no Jinja).**
   - It has two entry sections, `## Pick-time check` and `## Review-time re-check`.
   - Each runs one `related-work` call, displays `SUMMARY:` verbatim, and renders each `ITEM:` with its direction and freshness. Landed items also get their confirmation and archived plan path; review items get "covered by note `<id>`".
   - It states its invariants: display only, never blocks, never writes task data, never prompts, and never sends a note. An unreachable store or an incomplete analysis is "unknown", never "none".
   - The pick entry stores two context variables: `relations_check_at` (from `CHECKED_AT:`) and `related_work` (the displayed items, for planning).
4. **`.claude/skills/task-workflow/SKILL.md`** (source, Jinja-bearing).
   - **Context Requirements rows:**
     - `relations_check_at`;
     - `related_work`;
     - `relations_expected_plan`, documented as set by t1981_4's Step 7 `stamp` call and by Re-entry `plan-digest`, and null until then.
   - **Step 3 Check 8 - Related work (advisory).** It skips under the same condition as Check 7 (only `Ready`, non-`manual_verification`). It runs `related-work-check.md` `## Pick-time check` and continues to Step 4 in every branch. Headless profiles get the same display, since it never prompts anyway.
   - **Step 8.** Immediately before "Show change summary", it runs `## Review-time re-check` with `--since <relations_check_at>` when set. It is display only.
   - **Step 8e.** A new "Relations-derived offers" block comes **before** the existing judgement text, which stays verbatim. It is written as one explicit flow, A → B → C → D. Every option ends in D, so offers and outcome logging run on every path exactly once.
     - **Shared arguments (bound once, reused by every call below).**
       - `EXPECT` = `--expect-plan <relations_expected_plan>` when that variable is set, else empty.
       - `REV` = `--rev aitask/<task_name>` in worktree mode, else empty, which means HEAD.
       - Every call runs from the main repository root.
     - **A. State.** Run `analysis-state <task_id> $EXPECT` and bind `state`.
     - **B. Option.** It is chosen in this order:
       - `state` = `complete` → `option=complete`.
       - `state` = `disabled` → `option=disabled`. Say so in plain words. The static fallback is offered as an optional aid (yes/no) only when `aitask_relation_candidates.sh` exists; a "yes" also sets `fallback_aid=true`. When it is absent, say it is unavailable.
       - `incomplete:*` → state it in plain words, then:
         - interactive with the key `ask` or absent → `AskUserQuestion`: "Run analysis now and wait" / "Static discovery fallback" / "Proceed with what exists";
         - the profile key set to anything else → that value;
         - `headless` with `ask` → `proceed`.
     - **C. Option-specific work (before candidates are computed).**
       - **wait** → `analyze <task_id> --now --wait <job_timeout_s>`.
         - `CAP_REACHED:` interactively needs a second explicit confirmation, then a retry with `--over-cap`. The profile `wait` never over-caps; it records `option=wait_refused_cap` and continues as proceed.
         - `ANALYZED:` with a non-failure outcome → **re-run step A** with the same `$EXPECT`. Then `option=wait`, and the new `state` is what D recomputes and logs, complete or not.
         - `WAIT_TIMEOUT:` / a failure outcome / `BLOCKED_UNRESOLVED` → say so, and set `option=wait_failed` (rows from what exists).
       - **fallback** → probe for `aitask_relation_candidates.sh`. When it is absent, say "static fallback unavailable (t1981_2 has not landed)" and set `option=fallback_unavailable`. When present, set `option=fallback` and `fallback_aid=true`. The fallback itself runs inside D, after the change set exists.
       - **proceed / complete / disabled** → nothing.
     - **D. Compute, offer and log (the single convergence point).**
       1. Run `notify-candidates <task_id> $EXPECT $REV --option <option> --log` **once**. This is the only producer of `RUN_ID:`, the `CHANGED_FILE:` rows, the PUSH/PULL rows and the summary ledger row. The verb recomputes the analysis state itself, so the ledger records the real final state, which after a successful wait is the post-wait state.
       2. When `fallback_aid` is true, write that output's `CHANGED_FILE:` values (decoded) to a scratch file. Run `aitask_relation_candidates.sh <task_id> --fallback-push --changed-file <f>`, and the agent judges each `UNCONFIRMED:` row against the diff. These rows are evidence, not relations. A target the agent finds affected joins the offer list below as a judgement row, logged with `--type unconfirmed`.
       3. **PUSH rows** (none when `option=disabled`: the verb emits no PUSH rows then, and the skill text says so — no relation-derived offer is made from stored records of a disabled project; only judged fallback rows, when the aid was chosen, and the ordinary judgement offer below remain).
          - The agent first checks each stored description against what landed.
          - Then a multi-select `AskUserQuestion`, paginated at 4 options per call and never automatic. Each option is pre-filled with the description and the `EVIDENCE:` lines, and judged fallback rows are included.
          - Each selected row → `/aitask-note <to> --from <task_id>` with that body, hedged as advisory, then `notify-outcome --run <RUN_ID> … --outcome sent --note-id <id>`. Each unselected row → `--outcome declined`.
          - Headless: no offer; every row is recorded `not_offered`.
          - When the output says `PUSH_NONE:incomplete:<state>`, say so. Never word it as "no affected targets".
       4. **PULL rows** are shown as one count line by reason. The exception is `reverse_direction` rows: they are listed by name under "this task's own relations (direction does not push)".
     - **Branch checks (Verification).** A static test reads the source Step 8e and asserts that:
       - each of `complete`, `disabled`, `wait` (success, timeout, cap), `fallback` (present, absent) and `proceed` reaches D;
       - D's `notify-candidates` call carries `$EXPECT` and `$REV`;
       - the fallback call comes after the `notify-candidates` call inside D.
5. **`planning.md`** (source). One bullet in "While in plan mode": when `related_work` is non-empty, read the archived plans of `landed` / `dropped` items and account for them in the plan. Context only, never an instruction.
6. **`profiles.md` and the shipped profiles.**
   - Document `relations_incomplete_action` (`ask` default / `wait` / `fallback` / `proceed`; read only by Step 8e; `wait` never passes `--over-cap`).
   - Set it in `aitasks/metadata/profiles/default.yaml: ask`, `fast.yaml: ask` and `remote.yaml: proceed` (headless).
   - Mirror the key in `seed/` profiles wherever the seed carries the profile files.
7. **`.claude/skills/aitask-note/SKILL.md`.** In Step 1 "No target given", first run `aitask_relations.sh related-work <sender> --point note --log`, but only when a sender exists. Show `SUMMARY:` and the items, and offer them as targets, together with "None — search further".
   - On no pick, run the Related Task Discovery Procedure unchanged.
   - An unreachable store or an incomplete analysis says "unknown" and continues to discovery, never "no related tasks".
   - `related-task-discovery.md` stays untouched (t2192 owns it).
8. **The design doc.** Add `related-work` and `notify-outcome` to the `ait relations` row in D10's surface table, and add a "Consumer API" paragraph under D8 naming:
   - the line protocols;
   - the PULL reason vocabulary (`relations_disabled`, `type_not_pushed`, `reverse_direction`, `other_project`, `target_closed`, `unconfirmed_impact`, `target_state`, `target_moved`);
   - the covered-by-note rule;
   - the worktree `--rev` rule.

   `CLAUDE.md` needs no change, because its `task_relations.md` pointer already covers this.
9. **Goldens and prerenders.** Regenerate `tests/golden/procs/task-workflow/SKILL-*.md` and `planning-*.md` for all three profiles, plus every golden `aitask_skill_verify.sh` reports. Regenerate the committed remote prerenders with the repository's rerender driver. Review the diffs (the intended change only), then run `./.aitask-scripts/aitask_skill_verify.sh` and `bash tests/test_skill_render_task_workflow.sh`.

### Post-phase (risk mitigations)

1. [pick_cost_guard] In `tests/test_relations_consume.py`, add a case that sets the project disabled with no `refs/heads/aitask-relations`. It runs `related-work <id> --point pick` with `orphan_ref_store`'s fetch patched to raise. The case asserts the call succeeds with the disabled `SUMMARY:`, so no fetch was attempted. Then measure `time ./.aitask-scripts/aitask_relations.sh related-work 1981_5 --point pick` on this repository and record the wall time in Final Implementation Notes. If it is above 1.5 s, cut the cost before review, for example by skipping the full index load when there are no records.
2. [protocol_roundtrip_test] Add a table-driven test that renders `ITEM:`, `PUSH:` and `EVIDENCE:` rows whose description and basis values contain `%`, `|`, `\r`, `\n` and `%7C`. It decodes them with the documented order (`%0D`, `%0A`, `%7C`, then `%25`) and asserts a byte-exact round trip, plus exactly one physical line per row.

3. [pick_cost_guard] **Enabled-path timing.** Build a representative enabled scratch project in a throwaway test helper, under the scratchpad and not committed as a suite case:
   - `relations.enabled: true`, a local-only store;
   - one source task carrying 8 relations (mixed types and directions);
   - 4 landed tasks with archived plans and `(t<L>)`-tagged commits;
   - about 2000 commits of filler history, so the `(t<L>)` subject scans walk real history;
   - a few in-flight and pending targets.

   Time `related-work <src> --point pick` and `--point review --since <ts>`, plus `notify-candidates <src>`, 3 runs each, and record the medians in Final Implementation Notes. Optimise only if a median exceeds 2 s, and then only within the invocation: batch the per-id `git log --grep` scans into one history walk. **No persistent cache** is added either way.

## Verification

- **`tests/test_relations_consume.py`** (new). It reuses `tests/test_relations_store.py`'s `Env` / `record()` / `write_task` / `write_plan` / `stamp` helpers. Every scratch repository gets `project.name`, and nothing chdirs. The cases:
  - **Direction:**
    - forward-only "S affects X" → PUSH to X;
    - reverse-only "X affects S", with the shared basis in S's diff → PULL `reverse_direction`, never PUSH. Step 8e lists `reverse_direction` rows separately, under "this task's own relations (direction does not push)", which is the task's wording;
    - `coordinates_with` → PUSH to the other end, whichever end S is.
  - **Disabled with saved relations:** the fixture publishes a valid record carrying a forward `affects` relation whose basis is confirmed by S's diff and cited by an Implementing target, which would PUSH while enabled. It then sets `relations.enabled: false`. Asserted: no `PUSH:` row, `PUSH_NONE:disabled`, the relation appears as `PULL …|relations_disabled`, `CHANGED_FILE:` is still emitted, and a summary ledger row with `analysis_state=disabled` is written. The same fixture with the project re-enabled yields the PUSH, which is the control. A static check also asserts that the Step 8e text makes no PUSH offer under `option=disabled`.
  - **Bases:** a task-ref-only relation → PULL `unconfirmed_impact`; an unrelated landing (the basis is not in the diff) → PULL `unconfirmed_impact`.
  - **Target citation:** a target whose current plan no longer cites the basis → PULL `target_moved`. A target that is neither Implementing nor a plan holder → `target_state`.
  - **Change-set derivation:**
    - from `(t<S>)` subjects on HEAD (current-branch mode);
    - on a side branch `aitask/t<S>_x` via `--rev` (worktree mode);
    - `(t<S>0)` is not matched;
    - a rename counts both paths;
    - `--diff` overrides.
  - **Landed vs dropped:** `landed` excludes the superseded and obsolete `archived_reason` archives, which show as `dropped`.
  - **Pull confirmation** is recomputed from L's own commits.
  - **Review point:** a relation published (`run.at`) after `--since` shows as `late`, and one whose source sent T a note after `since` is marked `covered_by_note`. An acknowledged note counts as covering.
  - **Cap and grouping:** at most 8 items, `MORE:` correct, group priority.
  - **Incomplete states:** `PUSH_NONE:incomplete:<state>` for each `analysis_state()` incomplete outcome, built with t1981_3's fixture approach:
    - pending, failed, missing;
    - unverifiable for no stamp, a stale store, a stamp mismatch and `no_expected_identity`;
    - cross-host `inputs_mismatch`.

    None of them may produce `PUSH_NONE:complete` or the "no affected targets" wording.
  - **Expected identity:** `notify-candidates --expect-plan <sha>` matches the stamp → complete; a newer committed plan versus the visible stamp → `unverifiable(stamp_mismatch)`; no flag → `unverifiable(no_expected_identity)`.
  - **Disabled wording:** `SUMMARY:` for disabled is identical at the three `related-work` points and in `notify-candidates`. A static test asserts that each of the four surfaces (Step 3 Check 8, the Step 8 re-check, Step 8e, `/aitask-note`) tells the agent to display `SUMMARY:` verbatim.
  - **Ledgers:** one JSON line per relation with the D13.3 fields; the summary row carries the state and option; `notify-outcome` rows; `ledgers --export` picks them up host-tagged.
  - **Fast path:** with the project disabled and no store branch, no fetch is attempted.
- The full suite: `bash tests/run_all_python_tests.sh`, reading the last line only.
- `bash tests/test_skill_render_task_workflow.sh`, `./.aitask-scripts/aitask_skill_verify.sh` and `shellcheck .aitask-scripts/aitask_relations.sh`.

## Risk

### Code-health risk: medium
- **The skill edits.** The plan edits task-workflow `SKILL.md` Step 3, Step 8 and Step 8e, and `planning.md`. Those are the most central skill files: every pick and every implementation runs them, and the goldens and remote prerenders for all three profiles regenerate. A mis-placed block could disturb an unrelated path. It is mitigated by display-only, never-ending checks, by reviewed golden diffs and by `aitask_skill_verify.sh` · severity: medium · → mitigation: none (covered by goldens and verify)
- **The new code's surface.** A new ~600-line module and three verbs add surface to `relations_cli.py`. The line protocols are hand-encoded, so an encoding slip could mis-render a description containing `|` · severity: low · → mitigation: inline post-phase protocol_roundtrip_test
- **Pick-time cost.** Every pick pays the `related-work` call. A slow index load or an accidental fetch in a disabled project would tax every session · severity: medium · → mitigation: inline post-phase pick_cost_guard

### Goal-achievement risk: medium
- **Dependencies that have not landed.** t1981_4 provides `relations_expected_plan` and t1981_2 provides the static fallback. Until both land, an enabled Step 8e always reads `unverifiable(no_expected_identity)` and the fallback is "unavailable", so the complete-path push flow is exercised only by fixtures, not end to end in a real session · severity: medium · → mitigation: relations_consumption_live_verification
- **Change-set derivation by subject.** The change set comes from `(t<S>)` subjects. A task whose commits omit the tag (a hand-made commit) gets an empty change set, and every relation is demoted to PULL. That is safe but would otherwise be silent, so the plan prints `WARN:` · severity: low · → mitigation: none (handled by the `WARN:` line)
- **Time-zone comparisons.** Local naive times are compared with UTC record times. A wrong time-zone assumption would shift the "since" windows · severity: low · → mitigation: none (one shared parser, unit-tested)

### Planned mitigations
- timing: post-phase | name: pick_cost_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: pick-time cost | desc: Prove the disabled fast path never fetches; measure related-work on this repo and on an enabled scratch project (8 relations, 4 landed tasks, ~2000 commits); optimise in-invocation only past 2 s, no persistent cache
- timing: post-phase | name: protocol_roundtrip_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: line-protocol encoding slip | desc: Byte-exact encode/decode round trip for ITEM/PUSH/EVIDENCE rows with hostile characters
- timing: after | name: relations_consumption_live_verification | type: manual_verification | priority: medium | effort: medium | inline_risk: high | added_complexity: medium | addresses: unlanded t1981_4/t1981_2 dependencies leave the complete-path flow fixture-only | desc: After t1981_4 and t1981_2 land, verify pick check, Step 8e complete path, PUSH offer, wait and fallback in an enabled scratch project

## Notes to send at Step 8e

These are notes to sibling tasks, sent after this task's own commit:
- **t1981_4:** the `relations_expected_plan` Context Requirements row already exists, and Step 8e consumes it.
- **t1981_9:** the list of changed skill files to port: `SKILL.md`, `planning.md`, `related-work-check.md`, `profiles.md` and `aitask-note`.
- **t1981_8:** the new verbs and the profile key.

## Step 9

Post-implementation per task-workflow Step 9: commit, archive, merge. The ports to the other agent trees are t1981_9.
