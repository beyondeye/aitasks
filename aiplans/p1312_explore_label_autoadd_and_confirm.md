---
Task: t1312_explore_label_autoadd_and_confirm.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1312 — Label auto-add + profile-gated confirmation for `/aitask-explore`

## Context

`/aitask-explore` has become the main way tasks get created, but the label
vocabulary never grows with it. `aitask_create.sh --batch --labels "a,b"` writes
labels straight into task frontmatter and **never touches**
`aitasks/metadata/labels.txt` — `add_label_to_file()` is dead code
(`aitask_create.sh:1089`, zero call sites; the interactive fzf path inlines the
same pipeline at `:1218-1223`). Every label an explore-created task invents is
invisible to `/aitask-pick`'s filter, the board, and
`chatlink/payload_guard.py:89-92`, which treats `labels.txt` as a **strict
allowlist** and rejects chat payloads carrying unknown labels.

The skill never mentions labels (no default, no `labels.txt` read, no
confirmation), and the 95-entry vocabulary already shows drift: typos
(`aitakspickrem`, `brainstom_modules`, `sanboxing`) and mixed separators
(`aitask-create` vs `aitask_explore`).

**Outcome:** explore-proposed labels are user-confirmed (gated by a new
execution-profile key), new labels are sanitized into `labels.txt`, and the file
lands in the same commit as the task — on both the create and update paths.

## Decisions taken (user-confirmed)

| Decision | Choice |
|---|---|
| Profile key shape | **enum** `explore_label_confirm: ask \| auto \| existing_only` |
| New-label handling in prompt | **Suggest near-duplicates** (normalized match) |
| `aitask_update.sh --labels` (replace-all) | **Also auto-adds** to labels.txt |
| Confirm-block scope | **explore only**; follow-up task for wrap/pr-import macro |
| `remote` (headless) value | `existing_only` |
| Matcher location | New helper `aitask_labels.sh` (deterministic, unit-testable) |
| `sanitize_label` semantics | **Replace invalid chars with `_`** (`"UI Stuff"`→`ui_stuff`), unifying with the import mapper (`aitask_pr_import.sh:141`); collapse `__`, trim edge `_` |
| Collation | **Pin `LC_ALL=C sort`** in all writers + commit the one-time ~20-line reorder of `labels.txt` in this task |
| All-invalid CSV (`--labels ",,!!!"`) | **Warn + drop**: exit 0, stderr warning, `labels: []`, `labels.txt` untouched |
| `set_last_used_labels` in batch | **Not called — documented deviation** (agent-driven creates must not clobber the human fzf affordance; avoids a Python subprocess per batch create). Task AC updated to record this. |

---

## Part A — Shared label seam in `lib/task_utils.sh`

Insert after `format_yaml_list` (`lib/task_utils.sh:414-421`). All current copies
are deleted (see "Mandatory deletions") — otherwise later definitions shadow the
lib and the change silently does nothing.

**Path resolution — lazy, override-honoring:**

```bash
labels_file_path() {
    if [[ -n "${LABELS_FILE:-}" ]]; then printf '%s' "$LABELS_FILE"
    else printf '%s' "${TASK_DIR:-aitasks}/metadata/labels.txt"; fi
}
```

Lazy because `aitask_create.sh` sets `TASK_DIR` at `:15`, *after* sourcing the
lib at `:11`, and `tests/test_last_used_labels.sh:22-31` exports a temp
`TASK_DIR` pre-source. The four per-script `LABELS_FILE=` lines
(`create.sh:1049`, `update.sh:14`, `pr_import.sh:11`, `issue_import.sh:10`)
**stay but become `"${TASK_DIR}/metadata/labels.txt"`** — they must stay because
create.sh stages by variable five times (`:798,:834,:1912,:2048,:2080`) as
`task_git add "$LABELS_FILE" 2>/dev/null || true`; deleting the assignment under
`set -e` (no `-u`) would expand to `task_git add ""` and the `|| true` would
swallow it — labels.txt silently stops being committed.

**Rich return = module globals, never stdout.** Both update.sh consumers run
inside command substitution (`new_labels=$(process_label_operations …)` at
`:1901`; `$(interactive_update_labels …)` at `:1577`), so stdout is taken and
subshell state evaporates. Use the repo's existing global idiom
(`SELECTED_LABELS`, `UPDATED_DESCRIPTION`), declared at source time so `set -u`
callers are safe:

```bash
AIT_LABELS_NORMALIZED=""   # normalized CSV, safe for frontmatter
AIT_LABELS_ADDED=()        # labels newly appended this call
AIT_LABELS_DROPPED=()      # tokens that sanitized to nothing
```

Guard every expansion with `(( ${#arr[@]} > 0 ))` (bash 4.2/4.3 errors on empty
`${arr[*]}` under `set -u`). **Never call these helpers via `$( )`** — state it
in the function comment; that is the one way to misuse the API.

**Functions:**

- `sanitize_label` — `tr '[:upper:]' '[:lower:]' | sed -e 's/[^a-z0-9_-]/_/g' -e 's/__*/_/g' -e 's/^_//' -e 's/_$//'`
- `ensure_labels_file` / `get_existing_labels` — as today but via
  `labels_file_path`; `get_existing_labels` ends `return 0` (a trailing
  `[[ -s ]] && sort` returns 1 on empty file and aborts `set -e` callers).
- `add_label_to_file <label>` — `grep -qFx --` guard (labels may start with
  `-`), then **temp-file + `mv`** (atomic for readers) with `LC_ALL=C sort -u`;
  appends to `AIT_LABELS_ADDED`; **always returns 0** (`update.sh:874`/`:1371`
  call it bare under `set -e`).
- `normalize_labels_csv <csv>` — **pure**: split on `,`, trim, sanitize, drop
  empties, order-preserving dedupe; stdout = normalized CSV; stderr =
  `DROPPED:<tokens>` when any token died.
- `add_labels_csv_to_file <csv>` — resets the globals, runs
  `normalize_labels_csv` (stdout/stderr split via the two-call idiom already
  used at `create.sh:1980-1982`), fills `AIT_LABELS_NORMALIZED` /
  `AIT_LABELS_DROPPED`, then `add_label_to_file` per token **in the same shell**
  so `AIT_LABELS_ADDED` survives.

**Mandatory deletions (shadowing):** create.sh `:1069-1098` (all four helpers);
update.sh `:793-814`; pr_import.sh `:56-68`; issue_import.sh `:51-63`. Also
collapse the byte-copied inline "add new label" blocks (`create.sh:1214-1223` →
`sanitize_label` + `add_label_to_file`; `pr_import.sh:1197-1203`,
`issue_import.sh:979-986` likewise). Post-check:
`grep -n 'add_label_to_file()\|sanitize_label()\|ensure_labels_file()\|get_existing_labels()' .aitask-scripts/*.sh`
must return zero hits.

**One-time reorder:** commit `LC_ALL=C sort -u`'d `labels.txt` (~20 lines move)
via `./ait git` in this task, so the collation pin doesn't produce a mystery
diff later.

## Part B — Batch auto-add in `aitask_create.sh`

`run_batch_mode()` at `:1925`; validation ends with `sanitize_name` at `:1998`;
`BATCH_COMMIT` branch opens at `:2004`. Two hooks:

**B1 — Normalize (after `:1999`, before the branch — covers parent `:2066`,
child `:2035`, draft `:2093`):** rewrite `BATCH_LABELS` to
`normalize_labels_csv` output; `warn` dropped tokens. Pure — no file write, so
an abandoned draft never dirties `labels.txt`. Sanitize-and-rewrite is required
by the AC ("frontmatter and labels.txt agree") and verified safe: **no scripted
caller passes spaced/uppercase labels** (checked every `--labels` site:
`aitask_create_manual_verification.sh:114`, `aitask_verification_followup.sh:211`,
the import mappers pre-sanitize, chatlink pre-validates; only agent-filled skill
placeholders are uncontrolled — exactly the input we want corrected). Bonus: it
fixes the `[ui,  backend]` double-space artifact of `format_yaml_list` without
touching that function.

**B2 — Vocabulary write (just inside `if [[ "$BATCH_COMMIT" == true ]]` at
`:2004`, above the parent/child split):** `add_labels_csv_to_file
"$BATCH_LABELS"`; report additions with `info … >&2`. The existing
`task_git add "$LABELS_FILE"` at `:2048` (child) and `:2080` (parent) then
carries the file **in the same task-creation commit** — no commit-side change.

> `>&2` is load-bearing: `info()` writes to **stdout**
> (`lib/terminal_compat.sh:19`), and `--silent` promises exactly one stdout line
> that `create.sh:2172` and `aitask_verification_followup.sh:221` parse.

**Draft path — defer write to finalize, normalize at draft:** `aitasks/new/` is
gitignored and uncommitted; writing at draft time would leak abandoned drafts'
labels into the worktree permanently. B1 already normalizes draft frontmatter;
add `_register_task_labels <filepath>` (greps `^labels:`, `parse_yaml_list`,
`add_labels_csv_to_file`) called in both `finalize_draft` branches after
`enforce_manual_verification_gate_invariant` (before the existing adds at
`:798` / `:834`). `finalize_all_drafts` loops through it for free. Document in
`--help` (~`:95`): drafts register vocabulary at finalize.

**Not done, by decision:** `set_last_used_labels` stays interactive-only
(`:2309`) — recorded as a documented deviation in the task AC.

## Part C — New profile key `explore_label_confirm`

Values: `ask` (default when absent) · `auto` · `existing_only`.

**`profile_editor.py` — the complete registration surface (verified: exactly
three structures; a key missing from the groups is silently dropped by
`collect_profile_values` at `:686/:701-702`):**

1. `PROFILE_SCHEMA:47-85` → `"explore_label_confirm": ("enum", ["ask", "auto", "existing_only"]),`
2. `PROFILE_FIELD_INFO:105-365` → 2-tuple modelled on `qa_mode` (`:342-350`)
3. `PROFILE_FIELD_GROUPS:388` → `("Exploration", ["explore_auto_continue", "explore_label_confirm"])`

No downstream edits — `settings/settings_app.py:109-110` derives everything.

**All six profile files get an explicit value:** `ask` in
`seed/profiles/{default,fast}.yaml` + live counterparts; `existing_only` in
`seed/profiles/remote.yaml` + live (`headless: true` at `:3` — absent would mean
`ask` and emit a prompt in a headless run). No seed↔live sync test exists (they
are already drifted for fast.yaml) — both copies are hand-edited.

## Part D — Label confirmation step in the explore skill

### D1. New helper `.aitask-scripts/aitask_labels.sh`

- `list` → `LABEL:<name>` per vocabulary line.
- `classify <csv>` → per proposed label:
  `EXISTING:<label>` · `NEAR:<sanitized>:<existing1>,<existing2>` (match after
  stripping to `[a-z0-9]`, so `aitask-create` ≡ `aitask_create`) ·
  `NEW:<sanitized>` · `INVALID:<original>`.

Reuses the Part A seam. Whitelist entries in the **five** files enforced by
`tests/test_skill_verify.sh:266-278` (`.claude/settings.local.json`,
`.codex/rules/default.rules`, `seed/claude_settings.local.json`,
`seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`).
Cross-link: update postponed **t858** to reuse `aitask_labels.sh list` instead
of its proposed parallel `aitask_query_files.sh labels` emitter.

### D2. New Step 3a in `.claude/skills/aitask-explore/SKILL.md.j2`

Between the Step 3 metadata confirmation (ends `:206`) and **Create the task**
(`:217`), feeding the confirmed CSV into `labels:` at `:225`. minijinja runs
`undefined_behavior="strict"` (`skill_template.py:112-120`) — every read
guarded:

```jinja
{% if profile.explore_label_confirm is defined and profile.explore_label_confirm == "auto" %}
  display proposed labels; auto-add via creation; no prompt
{% elif profile.explore_label_confirm is defined and profile.explore_label_confirm == "existing_only" %}
  keep EXISTING + NEAR→existing substitutions; REPORT dropped labels; no prompt
{% else %}
  ask arm (also the absent-key default)
{% endif %}
```

**Ask arm:** run `classify`; one `AskUserQuestion` whose **question text carries
the classification** (visibility rule — same-turn prose may not render).
Options: "Accept as proposed" / "Use the suggested existing labels" (only when
≥1 `NEAR:`) / "Edit labels" (free text via Other). The skill never writes
`labels.txt` — Part B's create-side hook keeps vocabulary + task atomic.

## Part E — `aitask_update.sh`: normalization, vocabulary, staging

**Subshell fact (drives the whole design):** the vocabulary write cannot live in
`process_label_operations` (`:874`, captured at `:1901`) or
`interactive_update_labels` (`:1371`, captured at `:1577`) — writes/globals
there die with the subshell. Both functions become **pure frontmatter-list
math**; writes move to the non-subshell callers.

**Batch path:**

1. **Normalize inputs at entry** so frontmatter and vocabulary agree (user
   concern: `--labels "UI Stuff, Foo!"` must not leave raw frontmatter beside
   sanitized vocabulary): before `process_label_operations` runs, rewrite
   `BATCH_LABELS` (when `BATCH_LABELS_SET`) via `normalize_labels_csv` and each
   `BATCH_ADD_LABELS` element via `sanitize_label` (warn + drop empties).
   `--remove-label` args are matched verbatim against current frontmatter
   (removal of legacy raw labels must keep working) and never unregister from
   `labels.txt` (consistent with documented behavior).
2. **Vocabulary write after `:1901`**, gated: only when `BATCH_LABELS_SET` or
   `BATCH_ADD_LABELS` non-empty — a bare `--status Done` (every gate
   transition/board move) must never touch `labels.txt`. Set local
   `_stage_labels=true` when `AIT_LABELS_ADDED` non-empty.
3. **Staging at `:2016`**: `[[ "$_stage_labels" == true ]] && task_git add
   "$LABELS_FILE" 2>/dev/null || true` before the commit.

**Interactive path:** delete the inline sanitize+write at `:1367-1372` (keep
`sanitize_label` for the display name); after the `:1577` substitution run
`add_labels_csv_to_file "$new_labels"`, set `new_labels="$AIT_LABELS_NORMALIZED"`,
and flip a **script-level** `LABELS_VOCAB_DIRTY=true` (initialized `false` near
`:14` — the menu loops, a global is sticky-OR). Stage at `:1662` on that flag.
Known cosmetic regression (note in commit message): a label minted mid-session
no longer reappears in the same session's fzf picker (the write is deferred);
it is still in `labels_array` and echoed.

`task_git`, never plain `git` — `labels.txt` is data-branch tracked and
`task_git` runs `git -C .aitask-data` (`task_utils.sh:181-189`).

## Part F — Docs, goldens, tests

**Docs — five sites (per the task AC):**

1. `website/content/docs/concepts/execution-profiles.md` — **required by AC**:
   add `explore_label_confirm` to the key discussion (the example-key list at
   `:11` and/or its reference section).
2. `website/content/docs/skills/aitask-pick/execution-profiles.md:36` — row
   after `explore_auto_continue` (this is the actual key table).
3. `website/content/docs/tuis/settings/reference.md:129-133` — `### Exploration`
   table row.
4. `website/content/docs/skills/aitask-explore.md:42` — extend the
   **Profile key:** line.
5. `.claude/skills/task-workflow/profiles.md:24-47` — new row, **plus the
   missing `explore_auto_continue` row** (genuinely absent today; deliberate
   1-line inclusion). Editing this file touches the committed
   `task-workflow-remote-` prerender → run
   `./.aitask-scripts/aitask_skill_rerender.sh remote` and commit.

Plus the Notes section of the explore `.j2` (`:280`).

**Goldens** (no `--update-goldens` flag exists; same commit as the template
edit):

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/aitask-explore/SKILL.md.j2 \
    "aitasks/metadata/profiles/$profile.yaml" claude \
    > "tests/golden/skills/aitask-explore/SKILL-${profile}-claude.md"
done
```

**Render tests** — extend `tests/test_skill_render_aitask_explore.sh`:

- Per-profile arm assertions: ask arm renders for default/fast; `remote` render
  has **no** label AskUserQuestion and **does** contain the `existing_only` arm.
- **`auto` arm coverage** (user concern — no committed profile exercises it):
  write a scratch profile YAML (`explore_label_confirm: auto` + minimal keys)
  into the test's temp dir, render the template against it directly, assert the
  auto arm renders, no label AskUserQuestion appears, and the
  proposed-labels-retained text is present. (Same direct-`$RENDER` mechanism
  Test 1 already uses; the scratch file never enters `aitasks/metadata/`.)
- Test 1b (agent invariance) and Test 3 (no Jinja leak) must still pass — no
  `{% if agent %}` gates.

**Shell tests** (fixture: `tests/test_anchor_create.sh` `setup_project`
`:82-118`; assertions `tests/lib/asserts.sh`; committed-file idiom
`git show --name-only --pretty=format: HEAD`):

*`tests/test_label_vocabulary_lib.sh`* (unit; temp `TASK_DIR` exported before
sourcing, per `test_last_used_labels.sh:19-31`): lazy path resolution;
caller-set `LABELS_FILE` wins; `sanitize_label` cases (`"UI Stuff"`→`ui_stuff`,
`"!!!"`→`""`); `normalize_labels_csv` split/trim/dedupe + `DROPPED:` channel;
rich return reports exactly the newly-added set; bare `add_label_to_file` on a
present label doesn't abort `set -e`; empty input total no-op;
`get_existing_labels` exit 0 on empty file; **collation determinism** (file
matches an `LC_ALL=C` golden under both `LC_ALL=C` and `en_US.UTF-8`);
**chatlink byte-identity pin**: every non-comment line of the live
`aitasks/metadata/labels.txt` is a `sanitize_label` fixed point (guards the
gateway's byte-identical-creation contract against non-canonical hand edits).

*`tests/test_label_autoadd.sh`* (integration, create side): new label in
`labels.txt` **and** in the creation commit — parent AND child paths (child is
what a parent-only fix would miss); frontmatter ⊆ vocabulary; pre-existing label
not duplicated and `labels.txt` absent from that commit; `--labels ""` total
no-op (guards `test_create_manual_verification_gates.sh` usage);
`--labels "UI Stuff, Backend"` → frontmatter `[ui_stuff, backend]` agreeing with
vocabulary; **all-junk `--labels ",,!!!"` → exit 0, stderr warn, `labels: []`,
vocabulary untouched** (pins the warn+drop policy); draft writes nothing /
finalize registers + commits; **`--silent` stdout stays exactly one line**
(the easiest regression: a bare `info` breaks `create.sh:2172` and
`aitask_verification_followup.sh:221`).

*`tests/test_update_label_staging.sh`*: `--add-label` new → in vocabulary, in
the commit, worktree clean after; `--labels` replace-all new → same;
`--labels "UI Stuff, Foo!"` → frontmatter and vocabulary agree (normalized);
pre-existing label → `labels.txt` absent from commit; **bare `--status Done` on
a labeled task never touches `labels.txt`** (guards the every-update blast
radius); `--remove-label` doesn't unregister.

**Negative controls** (repo rule: each guarded regression must make the suite
exit 1): for each test family apply the listed one-line mutation (delete the B2
hook; skip the B1 rewrite; unguard the staging line; drop `LC_ALL=C`; un-`>&2`
the info), run the file, confirm exit 1, undo **the mutation only** (no
`git checkout` — shared checkout).

**Verified non-breakage of existing tests:** `test_draft_finalize.sh:146-154`
(`"ui,backend"` → `[ui, backend]`, passes), `test_create_manual_verification_gates.sh`
(`--labels ""` no-op), `test_chatlink_flow.sh:316` (spy script, unaffected),
`test_parallel_child_create.sh` (idempotent seed), `test_archive_no_overbroad_add.sh`
(path-scoped porcelain asserts). Shellcheck bar: no **new** findings vs today's
info-level baseline.

## Chatlink trust boundary — verified analysis (why no decoupling is needed)

The "task creation becomes implicit authority to widen remote payload
acceptance" concern was checked against the actual code. Four findings:

1. **The guard was authored FOR a machine-growable vocabulary.** The
   `payload_guard.py` module docstring (lines 11-13) states its own design
   rationale: *"labels ⊆ aitasks/metadata/labels.txt (`aitask_create.sh`
   auto-adds unknown labels rather than rejecting — so subset enforcement MUST
   happen here)"*. The gateway subset check IS the intended trust boundary
   ("remote may only use locally-known labels"), designed under the assumption
   that local creation auto-adds. Amusingly, that assumption is **false today**
   (batch create adds nothing) — this task makes the guard's documented
   contract true, it does not invert it.
2. **The widening authority already exists today.**
   `aitask_update.sh --batch N --add-label foo` reaches `add_label_to_file` at
   `:874` right now, **unsanitized**. Any local agent can already grow the
   allowlist. This task extends the writer set (update → create) while
   *narrowing* what machine-minted entries can look like (charset-restricted
   to `[a-z0-9_-]` by B1).
3. **Accepted labels are inert downstream — demonstrated per consumer.** A
   remote label must byte-match an existing `labels.txt` line (membership check
   unchanged; remote still cannot mint). Consumers treat labels as data:
   `aitask_ls.sh` parses via `parse_yaml_list` and string-compares for
   filtering (`:316`, `:447`); `aitask_stats_legacy.sh:227` parses and groups;
   the board reads YAML frontmatter; chatlink's own schema + guard reject
   control chars and own size limits. No consumer evals, executes, or
   interpolates a label into a command line unquoted. Post-B1, every
   machine-minted vocabulary entry is `[a-z0-9_-]` — it cannot escape a YAML
   scalar, a quoted shell word, or an `-F` string match.
4. **One real corner, closed with a test.** The gateway contract says accepted
   payloads are created *byte-identical*; B1 would rewrite a label only if
   `labels.txt` contained a non-canonical entry (e.g. hand-edited uppercase).
   All 95 current entries are already `sanitize_label` fixed points, and the
   one-time `LC_ALL=C` reorder keeps the file canonical. **Add a test** (in
   `tests/test_label_vocabulary_lib.sh`): every non-comment line of the live
   `labels.txt` is a `sanitize_label` fixed point — pinning the byte-identity
   property the chatlink gateway relies on.

**Documentation:** record this analysis where the boundary lives — a short
"vocabulary growth and the chatlink allowlist" note in `aidocs/chat/` (per
CLAUDE.md, chat platform docs live there), cross-referenced from the
`payload_guard.py` docstring (whose auto-add claim becomes accurate with this
task).

## Follow-up tasks to create (post-implementation)

1. **Shared label-confirm macro** (user-requested): extract
   `_label_confirm_block.j2` and wire `aitask-wrap` + `aitask-pr-import`,
   aligning their divergent label prose. Distinct from t1313.
2. **Optional chatlink allowlist curation** (hardening, not a boundary fix —
   see the verified analysis above): if stricter remote-label policy is ever
   wanted, introduce a separate curated chatlink allowlist or a
   `# chatlink-allowed` marker convention. Deferring this does **not** leave a
   boundary change unaddressed: the membership check, its designed semantics,
   and label inertness are unchanged by this task.

## Risk

### Code-health risk: medium

- Rewriting `BATCH_LABELS`/update inputs changes emitted frontmatter for
  non-canonical input · severity: medium · → mitigation: t1321
  (`characterize_batch_label_frontmatter`)
- Lib seam must preserve lazy `TASK_DIR` resolution and the `$LABELS_FILE`
  staging-by-variable contract, else labels.txt silently stops committing ·
  severity: medium · → mitigation: none (pinned by the lib unit test +
  committed-file assertions)
- Shadowing: undeleted local copies make the lib dead code · severity: low ·
  → mitigation: none (grep post-check + negative controls)
- Whole-file `sort -u` rewrite on the data branch = merge-conflict surface,
  and concurrent writers can last-writer-wins a label away (atomic `mv` fixes
  torn reads, not lost updates; a registry lock would drop labels instead —
  worse) · severity: medium · → mitigation: `labels_txt_concurrent_append`

### Goal-achievement risk: medium

- Normalization matching misses the typo class that dominates actual drift
  (`brainstom_modules`, `skill_optiomizations`) · severity: medium ·
  → mitigation: `label_fuzzy_match_typos`
- `existing_only` on headless remote silently drops proposed labels if the
  drop report isn't surfaced · severity: low · → mitigation: none (the arm is
  specified to report drops; render test pins the arm)

### Planned mitigations
- timing: before | name: characterize_batch_label_frontmatter | created: t1321 | type: test | priority: medium | effort: low | addresses: code-health — rewriting BATCH_LABELS changes emitted frontmatter | desc: Characterization test pinning the current `--batch --labels` frontmatter output across the parent, child and draft creation paths, so the sanitize-and-rewrite change lands against a known baseline.
- timing: after | name: label_fuzzy_match_typos | type: enhancement | priority: medium | effort: low | addresses: goal-achievement — normalization misses the typo class | desc: Add edit-distance near-matching to `aitask_labels.sh classify` so typo variants (brainstom_modules, skill_optiomizations, sanboxing) are suggested against existing labels, not just separator/case variants.
- timing: after | name: labels_txt_concurrent_append | type: enhancement | priority: low | effort: low | addresses: code-health — whole-file `sort -u` rewrite on the data branch | desc: Make `labels.txt` appends conflict-tolerant (append-only write with dedupe at read time, or a git merge driver) instead of rewriting the whole file on every new label.

> **Sequencing consequence of the confirmed `before` mitigation:** per Step 7,
> `characterize_batch_label_frontmatter` is created as an independent task that
> t1312 **depends on**; t1312 then reverts to `Ready` and this session ends.
> The implementation above does not run in this session — the characterization
> test lands first, then t1312 is re-picked (plan force re-verified).

## Verification

```bash
shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh \
           .aitask-scripts/aitask_labels.sh .aitask-scripts/lib/task_utils.sh

bash tests/test_label_vocabulary_lib.sh
bash tests/test_label_autoadd.sh
bash tests/test_update_label_staging.sh
bash tests/test_draft_finalize.sh
bash tests/test_create_manual_verification_gates.sh
bash tests/test_anchor_create.sh
bash tests/test_create_silent_stdout.sh
bash tests/test_last_used_labels.sh
bash tests/test_parallel_child_create.sh
bash tests/test_aitask_update_xdeps.sh
bash tests/test_skill_render_aitask_explore.sh
bash tests/test_skill_verify.sh          # 5-file whitelist touchpoints

./.aitask-scripts/aitask_skill_verify.sh
bash tests/run_all_python_tests.sh       # read ONLY the last stderr line
```

**Live acceptance** (outermost surface): `/aitask-explore` under `fast` with an
intent yielding one new label + one near-duplicate; confirm the Step 3a prompt
carries the classification in the question text, and
`git show --name-only HEAD` on the creation commit contains both the task file
and `aitasks/metadata/labels.txt`. Re-run with `--profile remote`: no label
prompt. Then Step 9 (Post-Implementation) per task-workflow.
