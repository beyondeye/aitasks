---
Task: t1555_1_verification_staleness_check_helper.md
Parent Task: aitasks/t1555_implement_manual_verification_staleness_precheck.md
Sibling Tasks: aitasks/t1555/t1555_2_*.md, aitasks/t1555/t1555_3_*.md, aitasks/t1555/t1555_4_*.md
Branch: main
Base branch: main
Output branch: main
---

# t1555_1 — Verification staleness check helper + `verification_baseline:` field

## Context

A manual-verification checklist is authored once and then sits `Ready` — median
20 days, p90 89 days. If the code it describes changes meanwhile, the
Pass/Fail/Skip/Defer loop walks the user through verifying items that may no
longer describe reality, and today **nothing on that path detects it**.

t1538 designed an **advisory** pre-check for this
(`aidocs/framework/manual_verification_staleness.md` — the source of truth). It is
deliberately tiny, gated behind one precondition: it runs only when a task carries
**both** a curated `file_references:` list **and** a persisted
`verification_baseline:`. That precondition is what keeps the feature a guardrail
rather than a task-state subsystem — no sentinel, no presence tracking in the
shared writer, no fold rule, no lazy baseline derivation.

This is **slice 1 of 4** and owns the whole deterministic seam: the check helper,
the new frontmatter field (with its cross-task setter contract, which slices 2 and
3 both call), and carry-over inheritance. Nothing consumes the helper yet —
slice 3 inserts the procedure step that calls it.

## Scope guard (from the parent task, restated because it is easy to violate)

Do **not** add presence tracking to `file_references`, do **not** add
`--file-refs-none` / `--file-refs-clear`, and do **not** modify
`union_file_references()` or `aitask_fold_mark.sh`. Those are deliberately
deferred. `git diff --stat` at the end must show no change to any of them.

---

## 1. New helper — `.aitask-scripts/aitask_verification_stale.sh`

Read-only; sources `lib/terminal_compat.sh` (die/warn) and `lib/task_utils.sh`
(`get_file_references`, and `read_yaml_field` transitively via `lib/yaml_utils.sh`).
Structural template: `aitask_remote_drift_check.sh` (fixed protocol tokens +
variable evidence lines, always exit 0). Verdict-line shape:
`aitask_plan_verified.sh decide`.

### Interface

```
aitask_verification_stale.sh check <task_file>
```

Output (fixed lines first and last, evidence lines in between):

```
BASELINE:<sha>|<YYYY-MM-DD HH:MM>      or  BASELINE:NONE
FILES:<n>
CHANGED:<path>|<n_commits>|<task_ids>        0+
DELETED:<path>|<culprit_task>|<subject>      0+
UNKNOWN:<path>|<reason>                      0+
DISPLAY:<one-line human summary>
DECISION:<FRESH|ASK_STALE|SKIP>
```

**Exit status.** Every *content* state exits 0 — that is the "always exits 0"
contract. CLI misuse still dies: a missing verb or a `<task_file>` that does not
exist is a caller bug, and silently emitting `SKIP` for a typo'd path is exactly
the "silent skip masks a broken implementation" hazard the design doc names.
(Same split as `aitask_plan_verified.sh`: `decide` dies on bad args.)

### Ordered evaluation (normative — implement in this order)

```
1. not a git repo, or no HEAD                 -> SKIP
2. file_references: empty/absent              -> SKIP   (precondition)
3. verification_baseline: absent              -> SKIP   (precondition)
4. baseline not an ancestor of HEAD           -> SKIP   (history rewritten)
5. classify each curated path
6. any CHANGED / DELETED / UNKNOWN            -> ASK_STALE
7. otherwise                                  -> FRESH
```

`SKIP` is fail-open and silent — "cannot tell" must never render as "stale"
(mirrors `code_digest` in `lib/gate_ledger.py`). Steps 2/3 are the common case for
every existing task; that is intended.

**`UNKNOWN` drives the verdict — it is not advisory.** A curated path that cannot
be checked means the check covers *less scope than it claims*, so `FRESH` would be
a false all-clear. `UNKNOWN:` raises `ASK_STALE` exactly like a change does, and
`DISPLAY:` names the causes separately because the remedies differ (amend the
checklist vs repair `file_references:`).

### Classification — existence is probed, not inferred

`git log -- <path>` reports history but says nothing about current existence, so a
history-only implementation handles modification and **silently misses deletion**.
Two probes against the committed trees (never the dirty worktree):

| at baseline | at HEAD | result |
|---|---|---|
| yes | yes | `git log --format='%h\|%ad\|%s' <baseline>..HEAD -- <path>` → `CHANGED:` or nothing |
| yes | no  | `DELETED:` — culprit from `git log --diff-filter=D -M -n1 --format='%s' <baseline>..HEAD -- <path>` |
| no  | —   | `UNKNOWN:<path>\|absent_at_baseline` |

Probes: `git cat-file -e "<baseline>:<path>"` and `git cat-file -e "HEAD:<path>"`,
stderr discarded.

### Implementation details worth pinning

- **Repo root, not cwd.** Bind `repo_root=$(git rev-parse --show-toplevel)` once
  and pass `-C "$repo_root"` to *every* git call. `git log -- <path>` pathspecs are
  **cwd-relative** while `<rev>:<path>` is root-relative; curated paths are
  root-relative, so mixing the two silently mis-resolves from any subdirectory.
- **Curated paths are pathspecs, and git globs them — pass `:(literal)`.**
  `git log -- <path>` matches a *pathspec*, and a pathspec containing `*`, `?` or
  `[...]` is fnmatch-globbed. All three are legal POSIX filename characters, so a
  task curated for the literal file `docs/a[bc].md` picks up every commit touching
  `docs/ab.md` — the helper then reports `ASK_STALE` for a file nothing touched
  (violating its own FRESH contract) and, when the file *did* change, inflates
  `n_commits` and attributes the neighbour's task id to it. Both history queries
  (the `CHANGED:` log and the `DELETED:` culprit lookup) therefore pass
  `":(literal)$p"`. Consistent with existing practice — `:(exclude)` magic is
  already used in `aitask_change_surface.sh` and `lib/gate_ledger.py`, so no new
  git version floor. Bonus: it also neutralises a curated path that itself begins
  with `:`, which git would otherwise read as pathspec magic.
  The `git cat-file -e "<rev>:<path>"` probes need **no** such guard — that form
  is an exact tree-path lookup, not a pathspec. Root-relativity stays a separate
  property, supplied by `-C "$repo_root"`.
- **Range suffixes are stripped** (`path:N`, `path:N-M`, `path:N-M^N-M`) — v1
  compares whole files. Strip with a bash regex mirroring `validate_file_ref`'s
  grammar, then **dedupe**: two ranges of one file are one path to check, and
  `FILES:<n>` counts distinct stripped paths so it always equals the number of
  paths actually probed.
- **Emitted-path form (the consumer contract):** every evidence line carries the
  **stripped, then encoded** path — never the raw entry — so `lib/a.sh:3-9` reports
  as `CHANGED:lib/a.sh|…`. The single exception is `invalid_reference`, whose
  stripped form is empty by definition and would emit a pathless `UNKNOWN:|…`; that
  line carries the **raw entry, encoded by the same rule**. Encoding the exception
  matters as much as the general case: it is the one line whose payload did not pass
  through the strip regex, so it is the one most likely to carry an odd character.
  Stated here because slice 3 renders these paths back to the user and repairs
  `file_references:` from them.
- **An entry that strips to an empty path** → `UNKNOWN:<raw>|invalid_reference`.
  This is a required guard, not polish: `git cat-file -e "<sha>:"` resolves to the
  **root tree and exits 0**, so an empty path would otherwise read as "present".
- **Every emitted path is delimiter-encoded.** `validate_file_ref`'s grammar is
  `^[^:]+(:…)?$`, which **accepts** `|` (verified), and `|` is legal in a POSIX
  filename — so `docs/a|b.md` would split a `CHANGED:<path>|<n>|<ids>` record in the
  wrong place. Encode on emit, in this order:

  ```bash
  enc="${path//%/%25}"; enc="${enc//|/%7C}"     # % first, then |
  ```

  Decoding reverses it (`%7C` → `|`, then `%25` → `%`). Encoding `%` first is what
  makes it lossless: a real filename containing the literal text `%7C` round-trips
  as `%257C` and is never confused with an encoded delimiter (verified both ways).
  Two sequences, one rule, applied to the path field of **every** evidence line —
  so slice 3 has a single decode step and no per-record special case.

  **This replaces the reject-`|`-paths guard** an earlier draft carried. A guard
  emitting `UNKNOWN:docs/a|b.md|delimiter_in_path` reproduces the very ambiguity it
  exists to prevent, and a safe placeholder would withhold the exact entry slice 3
  needs for its `--remove-file-ref "<bad_path>"` repair. With encoding, a `|` path
  is simply checked like any other — strictly more capable and one special case
  fewer.
- **The `DELETED:` subject is sanitized, not encoded**: `subject="${subject//|/ }"`.
  A commit subject may legitimately contain `|`, which would break
  `DELETED:<path>|<culprit>|<subject>` for a perfectly valid curated file. Sanitize
  rather than encode because the subject is human display text, not an identity key
  to be round-tripped — unlike the path, nothing reads it back. `%s` is
  single-line, so newlines cannot occur.
- **Reason vocabulary** (closed, documented in the header):
  `absent_at_baseline | invalid_reference`. No reason contains `|`, no emitted path
  contains an unencoded `|`, and the subject is sanitized — so every record is
  unambiguously left-to-right splittable. That is the parse contract slice 3 gets,
  and it is stated in the helper header.
- **Baseline parse:** `sha="${raw%% @ *}"`, `ts="${raw#* @ }"` (ts empty when the
  separator is absent). No shape validation — a malformed sha fails the
  `git merge-base --is-ancestor` probe and falls out as `SKIP`, which is the
  correct fail-open answer. `--is-ancestor` returns 1 (not an ancestor) and 128
  (bad rev); both are SKIP.
- **Task ids** come from commit subjects via the parenthesised `(tNN)` / `(tNN_M)`
  convention, extracted with a bash `[[ =~ ]]` (no fork). Mirrors
  `extract_task_id` in `aitask_revert_analyze.sh:87`; a comment cross-references
  it. *(Not promoted to `lib/task_utils.sh` — that is a shared-lib change this
  slice deliberately does not make.)*
- **bash 3.2 target:** no `mapfile`, no associative arrays. Dedupe with a
  delimited string membership test.
- **Not `issue_type`-scoped.** The normative order has no type check, and the
  consumer (slice 3) only runs on `manual_verification` tasks. The header
  documents that scoping is the caller's responsibility.

### `DISPLAY:` shapes

- `SKIP` — `Staleness check skipped: <reason>.` (`not a git repository`,
  `no file_references: on this task`, `no verification_baseline: on this task`,
  `baseline <sha> is not an ancestor of HEAD (history rewritten)`)
- `FRESH` — `All <n> curated file(s) unchanged since baseline <sha> (<ts>) — checklist looks current.`
- `ASK_STALE` — `Checklist may be stale — baseline <sha> (<ts>), <n> curated file(s): `
  plus `; `-joined segments, each naming its paths:
  `changed since baseline: <paths>` / `deleted since baseline: <paths>` /
  `not present at baseline (fix file_references:): <paths>`, followed by
  ` — amend the checklist for changed/deleted files; repair file_references: for uncheckable paths.`

---

## 2. `verification_baseline:` frontmatter field — additive write support

Value: `<sha> @ <YYYY-MM-DD HH:MM>`. **Cross-task contract** — slices 2 and 3 both
call this, so ship exactly this shape:

```bash
./.aitask-scripts/aitask_update.sh --batch <task_id> \
    --verification-baseline "<sha> @ <YYYY-MM-DD HH:MM>"
```

A single scalar in exactly the stored form; `""` clears it. Reads go through
`read_yaml_field` like any other scalar — it works today with no reader change
(verified: the key regex and value trim handle the embedded `19:00` colon, and the
value is a valid YAML plain scalar, same as the existing `created_at:` emission).

### `.aitask-scripts/aitask_update.sh` — follow the `followup_kind` precedent (t1468_1) exactly

`followup_kind` is the most recent additive scalar and is the closest shape (no
tombstone: clearing removes the key). Mirror it at each site:

| Site | Change |
|---|---|
| globals (~L96) | `BATCH_VERIFICATION_BASELINE=""` / `_SET=false` |
| globals (~L140, and the reset in `parse_yaml_frontmatter` ~L474) | `CURRENT_VERIFICATION_BASELINE=""` |
| `show_help` | new entry beside the "Verifies options" block |
| `parse_args` (~L368) | `--verification-baseline) …_SET=true; shift 2 ;;` |
| `parse_yaml_frontmatter` case (~L574) | `verification_baseline) CURRENT_VERIFICATION_BASELINE="$value" ;;` |
| `write_task_file` | **new positional `${34:-}`**, appended (never inserted — inserting renumbers all 33 reads above), with the same comment rationale the `boardgroup`/`followup_kind` params carry. Conditional emit right after the `verifies:` block. No `_present` companion — no tombstone. |
| **all three** `write_task_file` call sites | L1181 (parent rewrite in `handle_child_task_completion`), L1707 (interactive), L2156 (batch) — pass `"$CURRENT_VERIFICATION_BASELINE"` / `"$new_verification_baseline"` |
| `has_update` list (~L1826) | `[[ "$BATCH_VERIFICATION_BASELINE_SET" == true ]] && has_update=true` |
| batch resolution (~L2058) | `new_verification_baseline` = CURRENT unless the flag was passed |

**The three call sites are the silent-failure surface**: miss one and the field is
dropped without error on that path (see the Risk section — the mitigation targets
exactly this).

No value validation. `--implemented-with` / `--issue` set the precedent, and a
malformed baseline already degrades to a safe `SKIP` in the check.

---

## 3. Carry-over inheritance — `.aitask-scripts/aitask_archive.sh`

`create_carryover_task()` re-seeds deferred items into a **new task with a fresh
`created_at`** — which is precisely why the field exists. Inherit it. Insert after
`new_id` is computed (~L628) and **before** the `task_git add "$new_file"` block so
the rewrite lands in the existing seed commit:

```bash
local orig_baseline
orig_baseline=$(read_yaml_field "$orig_file" "verification_baseline")
if [[ -n "$orig_baseline" ]]; then
    ./.aitask-scripts/aitask_update.sh --batch "$new_id" \
        --verification-baseline "$orig_baseline" --silent >/dev/null
fi
```

Using the setter (rather than a new `aitask_create.sh` flag) keeps the write path
to one writer and needs no second additive change.

---

## 4. Sync/merge rule — `.aitask-scripts/board/aitask_merge.py`

Required by `aidocs/framework/aitasks_extension_points.md` layer 4. **A
newer-`updated_at`-wins branch beside `anchor` is the wrong mechanism here** — it
sits inside the both-present section of the loop, and `merge_frontmatter`'s
one-sided-presence branch (L329–334) resolves **first and unconditionally**. Since
`--verification-baseline ""` **removes the key**, a deliberate clear on one
checkout would lose to a stale checkout still carrying the old value: the baseline
**resurrects on sync**, and with it a dismissal the user revoked. The module
documents this exact failure for `boardgroup` (L155–157).

`verification_baseline` is shape-identical to **`followup_kind` (t1468_1)**: a
semantic scalar, not board-owned, with **no tombstone** (clearing removes the key).
Use the mechanism that field already established — add one entry to
`_BASE_AWARE_FIELDS` (L181):

```python
_BASE_AWARE_FIELDS = {
    "boardgroup":            (normalize_group_slug,      False),
    "followup_kind":         (normalize_followup_kind,   True),
    "verification_baseline": (_normalize_opaque_scalar,  True),
}
```

That is all the plumbing needed — `_resolve_base_aware` runs in the **pre-loop**
block (L307), *before* the one-sided branch ever sees the key, and
`aitask_sync.sh` already passes `--base-file` from git's conflicted index (stage 1)
generically for every base-aware field (L241–247). Both flags are load-bearing:

- **base comparison** decides on *who actually edited the field* rather than on
  presence or a task-wide, minute-resolution `updated_at` that an unrelated
  `--status` edit can win;
- **`deletion_aware=True`** makes the winning side's *absence* win. Without it a
  resolved-empty value is handed back as `None`, and `serialize_frontmatter` gates
  on key membership — writing a literal `verification_baseline: null` into the file.

**New normalizer** `_normalize_opaque_scalar` (local to `aitask_merge.py`):
absent / `None` / non-string / blank all compare equal to absent; a real value is
returned **verbatim, not stripped**. Deliberately *not* `normalize_followup_kind`
despite an identical body — that one lives in the follow-up-kind **vocabulary**
module and its contract is about that vocabulary; a baseline has none. A comment
records that a third such field should promote the helper rather than add a fourth
copy.

Accepted behaviour: an add/add conflict has no stage-1 base, so `base_meta is None`
and the field **fails closed to unresolved/PARTIAL**. That is the documented
boardgroup/followup_kind behaviour, and correct — a manual conflict beats a guess.

*Layers deliberately not touched:* board TUI (field is not rendered), fold
(scalar → primary wins; and `aitask_fold_mark.sh` is explicitly out of scope),
`aitask_create.sh` (update-only field, mirroring `--boardgroup`/`--boardidx`),
`_LIST_UNION_FIELDS` / `BOARD_KEYS` / `BOARD_LAYOUT_KEYS`.

## 5. Invocation allowlists — **five** surfaces, not three

The task names three; the repo has five (verified against
`aitask_risk_mitigation_landed.sh`, which appears in all of them). An unwhitelisted
helper stalls slice 3 on a permission prompt:

- `.claude/settings.local.json`
- `seed/claude_settings.local.json`
- `seed/opencode_config.seed.json`
- `.codex/rules/default.rules`
- `seed/codex_rules.default.rules`

## 6. Documentation

`website/content/docs/development/task-format.md` — one `verification_baseline`
row in the "Frontmatter Fields" table, placed after `verifies`.

*Not* added to `CLAUDE.md` / `seed/aitasks_agent_instructions.seed.md`: both carry a
**representative** field list that already omits `file_references`, `verifies` and
the risk fields — the website table is the exhaustive surface. No
`aitasks_extension_points.md` worked example either: this field is `anchor` with a
different name and teaches nothing new.

---

## Tests — `tests/test_verification_stale.sh` (new)

Bash + `tests/lib/asserts.sh`, fixed deterministic timestamps in the style of
`tests/test_risk_mitigation_landed.sh`. Test bodies are functions (not `( … )`
subshells), so the file-backed counters are not needed. Three sections, each with
its own sandbox factory.

**A. Helper** — a real sandbox git repo with real commits; run the helper from
`$PROJECT_DIR` with cwd set to the sandbox so its `git` calls target the fixture.

- *modified* curated file → `ASK_STALE` + `CHANGED:` naming the culprit task
- *deleted* curated file → `ASK_STALE` + `DELETED:`. **Assert `CHANGED:<path>` is
  absent** — that is the executable discriminator: a history-only implementation
  emits `CHANGED:` here (the deletion commit *is* in `baseline..HEAD`) and passes
  the modified case, so this is the assertion that proves the
  `git cat-file -e HEAD:<path>` probe is doing the work.
- *mixed* changed + deleted + untouched → exactly two evidence lines, `FILES:3`,
  `ASK_STALE`
- *invalid scope*: a hand-edited path absent at the baseline → `UNKNOWN:` **and**
  `DECISION:ASK_STALE`; assert explicitly it is **neither `FRESH` nor `SKIP`**
- *mixed valid + invalid* → `ASK_STALE`, exactly one `UNKNOWN:` line, and
  `DISPLAY:` names the uncheckable path in the "not present at baseline" segment,
  distinctly from a changed one
- **negative control**: all curated files untouched and valid → `FRESH` (a detector
  that cannot say FRESH is the failure mode the design exists to avoid; the two
  invalid-scope cases above are its necessary complement)
- **committed-tree discriminator — dirty worktree**: edit a curated file and leave
  it **uncommitted** → `FRESH`, with **no `CHANGED:` and no `DELETED:` line**. This
  is the only fixture that separates the contract ("probe the committed trees,
  never the dirty worktree") from an implementation built on a working-tree diff:
  every other case commits its edits, so `git diff HEAD` and `git diff <baseline>`
  agree and a worktree-based implementation passes them all. Pair it with a
  **delete-but-don't-commit** variant → still `FRESH`, no `DELETED:`.
- **delimiter encoding** — a curated file genuinely named with a `|`
  (`docs/a|b.md`), committed and then changed:
  - the record reads `CHANGED:docs/a%7Cb.md|<n>|<ids>` — assert the **encoded**
    form, and assert splitting the line on `|` yields exactly the expected field
    count (an unencoded path yields one extra field: that is the executable
    statement of the ambiguity)
  - **decode round-trip**: decoding the emitted path returns the original name
    byte-for-byte
  - `%`-collision case: a file named `lit%7Cnot-a-pipe.md` emits `lit%257C…` and
    decodes back to itself — pins the encode-`%`-first ordering, which is the only
    part of the rule that can silently corrupt a name
  - an `invalid_reference` entry is encoded by the same rule
- **glob-shaped filenames** — three fixtures, because the failure has three
  distinct faces and a plain-pathspec implementation passes every other test in
  this file:
  - curated `docs/a[bc].md` untouched while the glob-matching neighbour
    `docs/ab.md` changes => **`FRESH`**, no evidence lines, and the neighbour's
    task id nowhere in the output (the false-positive / broken-FRESH-contract case)
  - both changed => `ASK_STALE` with `CHANGED:docs/a[bc].md|1|888` exactly: the
    genuine change is detected either way (git matches a literal path before
    globbing), so the discriminator is the **evidence** — an unguarded pathspec
    reads `2` commits and attributes the neighbour's id, sending the user to amend
    a checklist for the wrong change
  - both deleted => the culprit is the file's own deletion commit. **The neighbour
    must be deleted LAST**: the culprit query is `-n1`, so deleting it first makes
    both implementations agree and the fixture proves nothing (this ordering bug
    was caught by the negative control, not by review).
  The fixture helpers `commit_file` / `remove_file` must pass `:(literal)` too —
  `git add` / `git rm` are pathspecs as well, and `git rm -- 'docs/a[bc].md'`
  silently deletes `docs/ab.md`, destroying the fixture's own premise.
- **ranged references** — the fixtures above use bare paths only, so nothing would
  catch a dropped or wrong strip: a literal probe of `path:1-4` returns
  `UNKNOWN:…|absent_at_baseline` and prompts **forever** on a perfectly valid
  scoped reference. Four cases:
  - `lib/a.sh:3-9` on an **unchanged** file → `FRESH` (the discriminator: no strip
    ⇒ `UNKNOWN` + `ASK_STALE`)
  - `lib/a.sh:3-9` on a **changed** file → `ASK_STALE` with `CHANGED:lib/a.sh|…`,
    asserting the emitted path is the **stripped** one, not the raw entry
  - multi-range `lib/a.sh:3-9^20-30` (the grammar's compact form) on an unchanged
    file → `FRESH`
  - **duplicate ranges of one file** (`lib/a.sh:1-4` + `lib/a.sh:20-30`) on a
    changed file → `FILES:1` and **exactly one** evidence line — pins both the
    dedupe and the `FILES:` denominator
- *precondition skips*, one each, asserting no `CHANGED:`/`DELETED:` line: list but
  no baseline; baseline but no list; neither; baseline not an ancestor of HEAD
- **outside any git repository** (normative branch 1, otherwise untested): run the
  helper with cwd in a `mktemp -d` holding a task file with both fields populated →
  **exit 0**, `BASELINE:NONE`, a `DISPLAY:` line, `DECISION:SKIP`, and no evidence
  lines. This is what proves the fixed protocol survives branch 1: under
  `set -euo pipefail` an unguarded `git rev-parse` aborts the script with a
  non-zero exit and **no output at all**, and every other fixture runs inside a
  repo. The fixture must first assert that the temp dir really is outside a repo
  (`git -C "$dir" rev-parse --show-toplevel` fails) and **fail loudly** if not —
  a `$TMPDIR` that happens to sit inside a checkout would make it pass vacuously.
- *baseline advance*: after a simulated "Proceed unchanged" (baseline := HEAD) a
  re-run reports `FRESH` — the prompt does not re-fire

**B. Setter round-trip** — fake aitask repo via
`tests/lib/test_scaffold.sh::setup_fake_aitask_repo`, following
`tests/test_update_risk.sh::setup_project`.

- `--verification-baseline "<sha> @ <ts>"` writes the field; read-back is
  **byte-identical**
- survives an unrelated `--batch <id> --status Done`
- `--verification-baseline ""` clears it
- a task that never had the field does not gain an empty one from an unrelated
  update
- **scope-creep guard**: a task with no `file_references:` still has none after an
  unrelated update (no accidental empty-list materialisation)

**C. Carry-over inheritance** — real create + archive chain, following
`tests/test_archive_carryover_anchor.sh::setup_archive_project`: an MV task with a
`verification_baseline` and a deferred item, archived with
`--with-deferred-carryover`, produces a carry-over file carrying the **same**
baseline verbatim.

**D. `tests/test_aitask_merge.py`** — base-aware cases, mirroring the existing
`boardgroup` / `followup_kind` base-aware tests rather than the `anchor`
newer-wins ones. The clear-vs-stale-carrier pair is the point of the mechanism:

- **clear wins over a stale carrier**: base has `verification_baseline: <v>`, local
  **removed the key**, remote still carries `<v>` unchanged → the key is **absent**
  from the merged result and is not in `unresolved`. Run it **both ways round**
  (local-clears / remote-clears) — an implementation that reads presence instead of
  the base passes one direction and fails the other.
- **the clear must not serialize as `null`**: assert the key is absent from
  `merged` (not `merged[key] is None`), which is what `deletion_aware=True` buys and
  what `serialize_frontmatter`'s key-membership gate requires.
- **stale unrelated edit does not win**: base `<v>`, local `<v>` with a **newer**
  `updated_at` (an unrelated `--status` edit), remote advanced to `<v2>` → `<v2>`
  wins. This is the case a newer-`updated_at`-wins rule would get wrong.
- **advance wins over unchanged**: base `<v>`, local `<v2>`, remote `<v>` → `<v2>`.
- **both advanced differently** → fails closed: key listed in `unresolved`.
- **no base available** (`base_meta=None`) with differing sides → `unresolved`.

### Post-phase (risk mitigations)

Runs after sections A–D above, as part of the same change.

- **`pin_baseline_across_all_write_paths`** — extend section B so the field is
  proven to survive **each** of the three `write_task_file` call sites, not just
  the batch one:
  - *parent rewrite*: a parent task carrying `verification_baseline`, whose **child**
    is set to `--status Done` (this is what reaches `handle_child_task_completion`
    → the parent `write_task_file` at L1181) — assert the parent still carries it;
  - *interactive path* (L1707): assert the field is threaded from
    `CURRENT_VERIFICATION_BASELINE`. Drive it the way the file's existing tests
    drive interactive paths, or — if that path is not scriptable here — assert the
    call site passes the variable by pinning it structurally (`grep` the call site
    argument list), and say so in a comment.
  - *batch path*: already covered by the section-B round-trip.
- **`assert_allowlist_coverage`** — assert `aitask_verification_stale.sh` appears
  in all **five** allowlist files listed in §5. A single loop with a per-file
  assertion so a miss names the offending file.

---

## Verification

```bash
bash tests/test_verification_stale.sh                     # new file — must pass
shellcheck .aitask-scripts/aitask_verification_stale.sh \
           .aitask-scripts/aitask_update.sh \
           .aitask-scripts/aitask_archive.sh              # clean

# regression on every surface touched
bash tests/test_update_risk.sh
bash tests/test_update_multiline_yaml.sh
bash tests/test_followup_kind_roundtrip.sh
bash tests/test_archive_carryover.sh
bash tests/test_archive_carryover_anchor.sh
bash tests/test_aitask_merge.sh
bash tests/test_aitask_merge_boardgroup.sh                # base-aware machinery regression
bash tests/run_all_python_tests.sh --test-dir tests       # covers test_aitask_merge.py
```

Live smoke against this repo (the helper must be silent on every existing task —
all 77 lack both fields):

```bash
./.aitask-scripts/aitask_verification_stale.sh check <some active MV task>   # DECISION:SKIP
```

Scope guard, run last:

```bash
git diff --stat        # no change to union_file_references, aitask_fold_mark.sh,
                       # or file_references emission in aitask_update.sh
```

## Reference — Step 9 (Post-Implementation)

Cleanup, archival and merge follow the shared task-workflow Step 9. Current-branch
mode: no task branch to merge.

## Risk

### Code-health risk: medium
- Threading a 34th positional through `write_task_file` touches **three** call
  sites (`handle_child_task_completion` parent rewrite, interactive, batch); missing
  one drops the field silently on that path, with no error · severity: medium · → mitigation: inline post-phase pin_baseline_across_all_write_paths
- Five allowlist surfaces must stay in sync; a missed one surfaces only as a
  permission stall in slice 3 · severity: low · → mitigation: inline post-phase assert_allowlist_coverage
- The merge rule touches shared sync behaviour; a base-aware field fails closed to
  PARTIAL on an add/add conflict (no stage-1 base), which is the documented and
  intended `boardgroup`/`followup_kind` behaviour but is a user-visible manual
  conflict · severity: low · → mitigation: none (accepted; a guess is worse)

### Goal-achievement risk: low
- `DISPLAY:` wording and `FILES:` duplicate-path semantics are chosen here, not
  pinned by the design; slice 3 consumes them · severity: low · → mitigation: none (slice 3 is the only consumer and lands next)
- Path encoding is a cross-task contract slice 3 must decode; an undecoded render
  would show `a%7Cb.md` to the user. Confined to two sequences, stated in the helper
  header, and exercised by a decode round-trip test · severity: low · → mitigation: none (contract is pinned by test and header)
- Curated paths reach git as pathspecs; `:(literal)` is required on every such
  call site, and a future call site added without it silently re-opens the
  false-`ASK_STALE` bug · severity: low · → mitigation: none (three fixtures cover
  the changed / unchanged / deleted faces, and each was negative-controlled)
- `--diff-filter=D -M` (spec-mandated) does not match a *renamed* file, so its
  culprit reads `unknown` while the `DELETED:` verdict stays correct · severity: low · → mitigation: none (verdict is unaffected; spec-faithful)

### Planned mitigations
- timing: post-phase | name: pin_baseline_across_all_write_paths | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: silent field drop if one of the three write_task_file call sites is missed | desc: extend the setter tests to cover the parent-rewrite and interactive write paths, not only the batch path
- timing: post-phase | name: assert_allowlist_coverage | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: a missed invocation allowlist surfacing only as a permission stall in slice 3 | desc: assert the new helper is present in all five allowlist files, naming the offending file on a miss

---

## Final Implementation Notes

- **Actual work done:** All four scope items landed as planned. New read-only helper
  `.aitask-scripts/aitask_verification_stale.sh` (`check <task_file>`, ~350 lines)
  implementing the normative ordered evaluation, committed-tree existence probes,
  range-strip + dedupe, delimiter-encoded protocol paths, and `:(literal)` pathspecs.
  `verification_baseline:` added to `aitask_update.sh` following the `followup_kind`
  precedent (positional 34, all three `write_task_file` call sites). Carry-over
  inheritance in `aitask_archive.sh::create_carryover_task`. Base-aware merge rule +
  `_normalize_opaque_scalar` in `board/aitask_merge.py`. Five invocation allowlists,
  one website docs row. Tests: `tests/test_verification_stale.sh` (new, 90 assertions
  across sections A–D) and 9 cases appended to `tests/test_aitask_merge.py`.

- **Deviations from plan:**
  - **Merge rule mechanism changed during planning review.** The first draft added a
    newer-`updated_at`-wins branch beside `anchor`. That is wrong here: it sits inside
    the both-present arm, while the one-sided-presence branch resolves first and
    unconditionally — so a deliberate `--verification-baseline ""` clear would lose to a
    stale checkout still carrying the old value and the baseline would **resurrect on
    sync**, silently re-instating a dismissal the user revoked. Replaced with a
    `_BASE_AWARE_FIELDS` entry (`deletion_aware=True`), which is the mechanism
    `followup_kind` already established for this exact shape.
  - **Delimiter guard replaced by encoding.** A draft rejected `|`-containing paths as
    `UNKNOWN:<path>|delimiter_in_path` — a record that is itself ambiguous, i.e. the very
    failure the guard existed to prevent. Replaced with uniform `%`-then-`|` encoding of
    every emitted path, which deletes the special case *and* lets a `|`-named file be
    checked normally.
  - **Five allowlists, not the three named in the task.** `.codex/rules/default.rules`
    and `seed/codex_rules.default.rules` also gate helper invocation.
  - **`tests/test_followup_kind_roundtrip.sh` Part E amended** (see below).
  - Docs: added only the `website/.../task-format.md` row. `CLAUDE.md` and
    `seed/aitasks_agent_instructions.seed.md` carry a *representative* field list that
    already omits `file_references` / `verifies` / the risk fields, so the field does not
    belong there. No `aitasks_extension_points.md` worked example — this field is
    `anchor` with a different name and teaches nothing new.

- **Issues encountered:**
  - **Curated paths are pathspecs and git globs them** (found in review, CONFIRMED by
    reproduction on git 2.55). `git log -- 'docs/a[bc].md'` matches `docs/ab.md`, so an
    untouched literal file reported `ASK_STALE` — a direct violation of the helper's own
    FRESH contract — and when it *had* changed, `n_commits` and `task_ids` were
    contaminated by the neighbour's commit. Fixed with `":(literal)$p"` on both history
    queries. The `cat-file -e "<rev>:<path>"` probes are exact tree lookups, not
    pathspecs, and needed no guard. The false-*negative* direction does **not** occur:
    git matches a literal path before globbing.
  - **The same hazard bit the test fixtures**: `git rm -- 'docs/a[bc].md'` also deleted
    `docs/ab.md`, destroying the fixture's premise. `commit_file` / `remove_file` now
    pass `:(literal)` too.
  - **A negative control caught a vacuous fixture.** The deleted-glob-path fixture
    initially deleted the neighbour *first*; since the culprit query is `-n1`, both
    implementations then agreed and the fixture proved nothing. Reordering so the
    neighbour is deleted **last** made the mutation reach the assertion.
  - **`test_followup_kind_roundtrip.sh` Part E broke** on the appended positional: its
    regex anchored `"$CURRENT_FOLLOWUP_KIND"` to end-of-line, encoding "is **last**"
    rather than "is **forwarded**" — hostile to the append-at-the-end extension pattern
    `aitasks_extension_points.md` prescribes. Loosened to tolerate a trailing line
    continuation, keeping the whole-line anchoring that excludes assignments and the
    invariant call. Verified still non-vacuous: dropping the positional from a call site
    still fails it (`expected '3', got '2'`).

- **Key decisions:**
  - **Exit-status split:** every *content* state exits 0; CLI misuse (missing verb,
    nonexistent task file) dies. Silently emitting `SKIP` for a typo'd path is exactly
    the "silent-skip masks a broken implementation" hazard the design doc names.
  - **`FILES:<n>` counts distinct entries after range-strip**, so it always equals the
    number of paths actually probed.
  - **Dedupe membership is newline-delimited, not `|`-delimited** — a path may legally
    contain `|`, and a `|`-delimited test would false-positive (`a|b` recorded makes a
    bare `a` look seen). A path can never contain a newline.
  - **`DELETED:` subject is sanitized (`|`→space), not encoded** — it is human display
    text, not an identity key anything reads back.
  - **`DISPLAY:` carries raw, unencoded paths** — free-form human text with no internal
    delimiters.
  - **Not `issue_type`-scoped:** the normative order has no type check; scoping is the
    caller's responsibility (documented in the helper header).
  - Task-id extraction kept local rather than promoted to `lib/task_utils.sh` — a
    shared-lib change this slice deliberately does not make.

- **Verification performed:** `tests/test_verification_stale.sh` 90/90;
  `test_followup_kind_roundtrip` 31/31, `test_update_risk` 21/21,
  `test_update_multiline_yaml` 23/23, `test_archive_carryover` 13/13,
  `test_archive_carryover_anchor` 5/5, `test_aitask_merge` 43/43,
  `test_aitask_merge_boardgroup` 18/18; full Python suite
  `PYTHON SUITE: PASSED (runner=pytest, exit=0)` (4937 passed / 2 skipped parallel +
  5 serial). shellcheck introduced no new findings (`aitask_update.sh` had exactly one
  pre-existing SC2034 before and after). Scope guard clean: no change to
  `union_file_references`, `aitask_fold_mark.sh`, or `file_references` emission.
  **Ten negative controls** were run — history-only deletion, identity encoding, no
  range strip, removed carry-over, each of three un-wired `write_task_file` call sites,
  unguarded `git rev-parse`, reverted `:(literal)`, and a loosened `followup_kind`
  guard — each failing on exactly its targeted assertion.

- **Upstream defects identified:** None

- **Notes for sibling tasks:**
  - **The setter contract is live and unchanged from the design:**
    `./.aitask-scripts/aitask_update.sh --batch <task_id> --verification-baseline "<sha> @ <YYYY-MM-DD HH:MM>"`.
    `""` clears it (key removal, no tombstone). Reads go through `read_yaml_field`.
  - **t1555_3 must decode protocol paths.** Every emitted path is `%`-encoded: decode
    `%7C`→`|` then `%25`→`%` (that order). Records split left-to-right on `|`; reason
    tokens never contain `|`; the `DELETED:` subject is pre-sanitized. `DISPLAY:` is
    already raw and needs no decoding — render it verbatim.
  - **`DECISION:SKIP` is fail-open and must stay silent.** `SKIP` and `FRESH` continue
    without any user-visible output; only `ASK_STALE` prompts.
  - **`UNKNOWN:` is not advisory** — it raises `ASK_STALE`, and its remedy differs from a
    changed file's: repair `file_references:` (via `--remove-file-ref`), don't amend the
    checklist. `DISPLAY:` already separates the two causes into named segments, so the
    prompt can quote it verbatim.
  - **The review transaction ordering still stands:** decide → write items and scope →
    advance the baseline **last** → commit. Never advance-then-edit.
  - **t1555_2 (seeding) writes bare paths.** Ranges are stripped and ignored by the
    check; recording them would imply a precision v1 does not have.
  - **If you add a positional to `write_task_file`, give it its own continuation line**
    and update both structural call-site guards
    (`test_followup_kind_roundtrip.sh` Part E, `test_verification_stale.sh` Section B).
