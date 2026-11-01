---
Task: t2175_1_sitrep_todo_format_locked_writer_backup.md
Parent Task: aitasks/t2175_sitrep_repo_todo_list_steward.md
Sibling Tasks: aitasks/t2175/t2175_2_*.md, aitasks/t2175/t2175_3_*.md, aitasks/t2175/t2175_4_*.md, aitasks/t2175/t2175_5_*.md
Archived Sibling Plans: aiplans/archived/p2175/p2175_*_*.md
Base branch: main
Output branch: main
---

# t2175_1 — Sitrep `todo.md` format, locked writer, rolling backup

## Context

Sitrep (t2175, renamed from "compass") is a per-repo advisory steward that keeps
ONE persisted todo list so finished agent windows can be closed without losing
their follow-up information. Every later child builds on the store defined here:
harvest (t2175_2) adds items, stub context entries and retained source passages;
refresh (t2175_3) re-checks item state; the skill (t2175_4) writes situation
text, agent-derived items, dismissals and Q&A. The list is a **source of truth**
(dismissals, agent-derived items and Q&A are not rebuildable), so it needs a
single locked writer, atomic writes, backups and a crash-safe recovery path —
modelled on `.aitask-scripts/aitask_shadow_rejected.sh` and
`.aitask-scripts/aitask_scratchpad_store.sh`.

## Decisions taken in this task

- **One physical `todo.md`** (Part 1 + Part 2) plus a separate **`qa.md`** dated
  log. An item and its stub context entry are created in ONE atomic rename (two
  files would leave an item-without-context crash window) and the agent reads
  one file verbatim. "Per-section writes" = record-level verbs under the mutex:
  each verb re-reads the file under the lock, changes only its target
  record(s), re-renders the rest unchanged (render∘parse is the identity on
  writer output — tested). No verb accepts a whole-section replacement.
- **Stale writes are refused, not merged (per-item revision, CAS).** Every item
  carries `rev=<N>`, bumped on every change to that item. Refresh-style batch
  writes and any single-item write that passes `--expect-rev` are applied only
  when the item's current `rev` equals the one the caller observed; otherwise
  the line reports `STALE:` and the item is untouched. Batch (refresh) writes
  additionally never change a `dismissed` item and never set `dismissed` —
  dismissal is a user decision. This closes the read → user-dismisses →
  stale-refresh-overwrites race.
- **Ids are never reused, including across recovery.** The `next_id`
  high-water mark lives in its own file `next_id`, written atomically BEFORE the
  `todo.md` rename that uses the id (a crash between them leaves a harmless
  gap). Allocation is `max(next_id file, 1 + highest c<N> token found by regex
  in every store file — todo.md, its .bak, qa.md, its .bak, recovered/*)`; the
  regex scan works on unparseable files, so restoring an older backup, losing
  the counter file, or a Q&A entry naming an item the backup lacks can never
  hand out that id again.
- **Durable source pointers.** Agent captures under
  `~/.config/aitasks/frozen/<id>/` are deleted by `lib/agent_sessions.py`'s
  `remove_captures` — on `drop`, and also from `upsert` (re-registration) and
  `freeze_abort` — so a pointer into them is not durable. The store therefore
  owns retained copies: `sources/<sha256[:16]>.txt` (content-addressed,
  immutable, written by the `retain` verb). A `capture:` source MUST point into
  `sources/` with a line range inside the retained file; `file:` sources must be
  repo-relative (no absolute / `~` paths). The writer rejects anything else
  (exit 2) and checks the retained file exists under the lock. Retention and
  pointer rewriting at harvest time are handed to t2175_2 (step 0 adds this and
  an acceptance check — passage still readable after `aitask_frozen.sh drop` —
  to its task body).
- **Recovery never removes the live pathname.** `restore` copies the damaged
  file into `recovered/` (new name, atomic), then installs the verified backup
  over the live name with one atomic rename.
- **One-time store initialization separates "never created" from "lost".**
  The first mutation of ANY verb (`add`, `qa`, `retain`, `situation`, …) runs
  `init` under the lock before doing its own work: it writes the empty
  generation of BOTH data files and their backups — `qa.md`, `qa.md.bak`,
  `todo.md`, `todo.md.bak` (each only if missing) — and LAST the marker
  `store.init` (`format=1`). Data is only ever written after `store.init`
  exists, so:
  - `store.init` absent and no post-init artifact (`next_id`, `sources/`,
    `recovered/`) present ⇒ the store was never initialized or init was
    interrupted; it holds no data, and `init` (re)creates whatever is missing;
  - `store.init` present (or any post-init artifact present) and `todo.md` or
    `qa.md` missing ⇒ previously established data disappeared ⇒ **damaged**:
    the verbs that touch that file refuse with exit 4 and point to
    `restore todo|qa`; verbs on the other, intact file keep working. Because
    init wrote a `.bak` for both files, `restore` always has something to
    install (at worst the empty initial generation, which it reports).
- **`qa.md` gets the same contract as `todo.md`:** strict parse under the lock
  before every append (unparseable ⇒ exit 4, nothing written), `qa.md.bak`
  rolled before the atomic replace, `restore qa` for recovery.
- **Bash entry + Python format core.** `aitask_sitrep_todo.sh` owns argument
  and root validation, the `registry_lock.sh` mutex, backups, the id counter and
  `ait_atomic_render`; `lib/sitrep_todo.py` (stdlib only) is a pure
  parse/validate/mutate/render transformer. Same split as
  `aitask_explain_context.sh` + `aitask_explain_format_context.py`.
- **Store:** `${AITASK_SITREP_DIR:-.aitask-sitrep}/` (repo-root-relative,
  gitignored, never committed; an absolute override lets t2175_2 target another
  repo's store). Files: `todo.md`, `todo.md.bak`, `qa.md`, `qa.md.bak`,
  `store.init`, `next_id`, `sources/`, `recovered/`, lock dir `.lockd/` (one
  mutex for the whole store). No `prune` verb — the store is per repo, not per task.
- **Whitelist touchpoints deferred to t2175_4** (the first SKILL.md closure that
  invokes the helper, per `aidocs/framework/aitasks_extension_points.md`);
  siblings 2/3 call it from scripts. No `ait` dispatcher entry.

## The format (`todo.md`, format version 1)

```
<!-- GENERATED FILE - DO NOT EDIT MANUALLY. Machine-written by .aitask-scripts/aitask_sitrep_todo.sh in a strict format; a manual edit makes the store unreadable (recover with: aitask_sitrep_todo.sh restore todo). -->
<!-- aitask-sitrep todo format=1 -->
# Sitrep todo

## Part 1: Todo

### Situation

#### sitrep
Harvest parser is next; refresh waits on it.

### Pick now

- c4 | rev=3 | kind=task | state=open | group=now | checked_at=2026-11-01T10:02:11Z | ref=t2175_2 | derived=script | outcome= | Harvest parser for finished agents

### Next

### Waiting

### Recently done

### Dismissed

## Part 2: Context

### c4
- background: Second sitrep child; turns finished-agent output into items.
- origin: agent=agent-pick-2175 task=t2175 commit=c17a850 date=2026-11-01
- theme: sitrep
- sources:
  - task: aitasks/t2175/t2175_2_sitrep_harvest_parser_for_finished_agents.md
  - capture: sources/3f9a0c1d2e4b5a67.txt#L1-L60
- related: c2, c5
```

Grammar (enforced by the Python core; anything else ⇒ parse error, exit 4):

- **Line 1: generated-file banner**, a fixed constant (`GENERATED_BANNER` in
  `lib/sitrep_todo.py`, used by renderer and parser alike), required
  byte-exact, so anyone opening the file sees first that it is machine-written
  and must not be edited by hand. **Line 2:** `<!-- aitask-sitrep todo format=1 -->`.
- **Item line** — fixed field order, every field always present, title LAST
  (the only field that may contain `|`):
  `- c<N> | rev=<N> | kind=<task|action|question|watch> | state=<open|done|dismissed|unknown> | group=<now|next|waiting> | checked_at=<ISO-UTC|never> | ref=<ref or empty> | derived=<script|agent> | outcome=<text or empty> | <title>`.
  `ref`: `t<N>[_<M>]`, `<project>#t?<N>[_<M>]` (cross-repo) or empty. The
  heading an item sits under is a pure render of `(state, group)`:
  `done`→Recently done, `dismissed`→Dismissed, else `group`. Items sort by id.
- **Situation**: `#### <theme>` (`[a-z0-9][a-z0-9_-]*`) + free text, ≤1200 bytes,
  no lines starting with `#`.
- **Context entry** `### c<N>` (must name an existing item), CLOSED key set in
  fixed order: `background` (required, ≤400 chars), `origin` (required,
  `key=value` tokens, keys ⊂ {agent, task, commit, date, skill, pane}), `theme`
  (optional), `sources` (optional list of `<type>: <pointer>`, type ⊂ {task,
  plan, trail, capture, commit, artifact, file, url}; `capture` =
  `sources/<16hex>.txt#L<a>[-L<b>]` only; `task`/`plan`/`file` repo-relative),
  `related` (optional `c<N>` list). Any other key is rejected; keys in the
  denied set {status, state, next, todo, count, counts, progress, summary,
  overlap, eta, blocked, done} get a specific message ("status belongs in
  Part 1 / is derived from the sources"). Whole entry ≤2000 bytes.
- Values sanitized at the write site: newline/CR rejected, `|` rejected in every
  field but the title (exit 2).

`qa.md`: the same line-1 banner (naming `qa.md` and `restore qa`), line 2
`<!-- aitask-sitrep qa format=1 -->`, then entries `## <ISO-UTC> | items: c4,c5`
+ free body (≤4000 bytes; a body line starting with `## ` is rejected so it
cannot forge an entry boundary; `items` must name ids that exist or existed —
i.e. below the allocation high-water mark).

`sources/<16hex>.txt`: the raw retained passage, named by the first 16 hex of
its sha256; never rewritten (a re-`retain` of identical content is a no-op, a
hash collision with different content is exit 4).

## Implementation steps

0. **Rename the feature "compass" → "sitrep" in the task family** (user
   decision, 2026-11-01), right after plan approval and BEFORE the plan is
   externalized, so the plan file is created under the new name:
   - `./.aitask-scripts/aitask_update.sh --batch <id> --name <new> --remove-label compass --add-label sitrep`
     for t2175 (`sitrep_repo_todo_list_steward`), t2175_1
     (`sitrep_todo_format_locked_writer_backup`), t2175_2
     (`sitrep_harvest_parser_for_finished_agents`), t2175_3
     (`sitrep_deterministic_refresh_of_todo_part1`), t2175_4
     (`sitrep_skill_and_window_with_minimonitor`), t2175_5
     (`sitrep_monitor_key_harvest_and_close`); confirm t2175_1 keeps its
     `Implementing` status, assignment and lock.
   - Body text of all six: `Compass`/`compass` → `Sitrep`/`sitrep`
     (`.aitask-compass/` → `.aitask-sitrep/`, `aitask-compass` skill →
     `aitask-sitrep`, `aidocs/framework/compass.md` → `sitrep.md`) via
     `aitask_update.sh --desc-file`. "harvest" stays as the verb.
   - Additionally hand the durable-pointer work to its owners in their bodies:
     **t2175_2** — "Retain every passage a context entry points at with
     `aitask_sitrep_todo.sh retain` BEFORE writing the item, and point
     `capture:` sources at the returned `sources/…#L…`; never at
     `~/.config/aitasks/frozen/` (deleted by drop, upsert re-registration and
     freeze_abort). Acceptance: after `aitask_frozen.sh drop <id>`,
     `aitask_sitrep_todo.sh check-sources` reports `SOURCE_OK` for every
     harvested pointer and `context c<N>` + the retained file still show the
     passage." **t2175_3** — "Read items with `list --machine` and write results
     with `set-state --batch` carrying the observed `rev`; a `STALE:` line means
     someone changed the item since — re-read it next tick, never retry blind;
     never write dismissed items."
   - Drop the now-unused `compass` line from `aitasks/metadata/labels.txt`.
   - Commit with `./.aitask-scripts/aitask_task_commit.sh -m "ait: Rename compass feature to sitrep (t2175)" <every renamed/old path + labels.txt>`.

1. **`.aitask-scripts/lib/sitrep_todo.py`** — dataclasses `Item` (with `rev`),
   `ContextEntry`, `TodoStore`, `QaEntry`, `QaLog`; strict `parse_todo`,
   `parse_qa` (raise `FormatError` with line number); deterministic
   `render_todo`, `render_qa`; validators raising `RequestError`;
   `max_id_token(text)` (regex `\bc([1-9][0-9]*)\b`, works on any text). CLI
   `python3 sitrep_todo.py <op> …` with ops: `check-context` / `check-batch` /
   `check-qa` (stdin, pre-lock validation), `add`, `update`, `set-state`
   (single, `--expect-rev`), `set-state-batch` (stdin lines
   `<id>|<rev>|<state>|<checked_at>|<outcome>`; validation all-or-nothing,
   per-line CAS outcome), `situation`, `upsert-context`, `qa-append`,
   `list-machine`, `get-context`, `check-sources`, `verify` (parse-only). The
   wrapper passes the allocated id for `add`. Mutating ops write the new file to
   stdout and result lines to a result file the wrapper passes. Exit codes: 0
   ok, 2 RequestError, 4 FormatError.
2. **`.aitask-scripts/aitask_sitrep_todo.sh`** — header comment documents the
   format, verbs, exit codes, concurrency, recovery, and names the contract
   fixture. Shadow-helper structure: `usage`, `err_usage`, `validate_root`
   (`..` refused, exit 2, before any FS access), `store_paths_for`,
   `lock_or_busy` (mkdir / writability / symlink checks ⇒ exit 4,
   `registry_lock_acquire` failure ⇒ `LOCK_BUSY` exit 3). Sources
   `lib/terminal_compat.sh`, `lib/registry_lock.sh`, `lib/atomic_write.sh`,
   `lib/python_resolve.sh` (all in the scaffold baseline); NOT `task_utils.sh`
   (EXIT-trap clash). Lock timeout 10s (`AITASK_SITREP_LOCK_TIMEOUT`). Test seam
   `AITASK_SITREP_PAUSE_FIFO` with points `init:after_qa`,
   `write:after_backup`, `write:after_counter`, `restore:after_preserve`
   (scratchpad pattern).
   Verbs and results:
   - `add --kind K --title T [--ref R] [--group G] [--state open|unknown] [--derived script|agent] [--checked-at TS] [--context-file -]` ⇒ `ADDED:c<N>`, or `EXISTS:c<N>` (nothing written) when a non-empty `ref` exists in ANY state (re-harvest idempotent, dismissals stick)
   - `update <id> [--title] [--group] [--ref] [--kind] [--expect-rev N]` ⇒ `UPDATED:c<N>|<rev>` / `STALE:c<N>|<rev>`
   - `set-state <id> <state> [--checked-at TS|now] [--outcome T] [--expect-rev N]` ⇒ `STATE:c<N>|<state>|<rev>` / `STALE:c<N>|<rev>`
   - `set-state --batch` (stdin) ⇒ per line `STATE:` / `STALE:c<N>|<rev>` / `KEPT:c<N>|dismissed`
   - `dismiss <id> [--outcome reason] [--expect-rev N]` ⇒ `STATE:c<N>|dismissed|<rev>`
   - `situation <theme>` (stdin; empty removes) ⇒ `SITUATION:<theme>|set|removed`
   - `upsert-context <id>` (stdin) ⇒ `CONTEXT:c<N>|created|replaced`
   - `retain` (stdin passage, ≤64 KiB) ⇒ `RETAINED:sources/<hex>.txt#L1-L<n>`
   - `qa [--items c4,c5]` (stdin) ⇒ `QA:<timestamp>`
   - `read [todo|context|qa]` (raw, no lock, works on a corrupt file), `list --machine` ⇒ `ITEM:c<N>|<rev>|kind|state|group|checked_at|ref|derived|outcome|title` (title LAST) or `NO_ITEMS`, `context <id>`, `check-sources` ⇒ `SOURCE_OK:c<N>|<ptr>` / `SOURCE_MISSING:c<N>|<ptr>`, `path`
   - `restore todo|qa` ⇒ `RESTORED:<file>|recovered/<name>` or `RESTORED:<file>|no-damaged-copy`
   **Mutation sequence (todo):** validate args + stdin pre-lock (exit 2, nothing
   locked/written) → lock → `init` when `store.init` is absent and no
   post-init artifact exists (see Decisions) → damaged check for the file this
   verb touches (established but missing ⇒ exit 4) → parse (FormatError ⇒
   exit 4, nothing written, backups untouched) → for
   `add`: allocate id (rule above) and atomically write `next_id` → render the
   new text → roll `todo.md.bak` ← current (`ait_atomic_render`) → atomic
   replace `todo.md` → release. `qa` follows the same sequence on `qa.md` /
   `qa.md.bak`. Unknown id ⇒ `NOT_FOUND:c<N>` exit 2.
   **Restore sequence:** lock → `verify` the `.bak` (missing or unparseable ⇒
   exit 4, nothing changed) → if the live file exists, copy it to
   `recovered/<file>.<UTC-ts>.<pid>` (temp + rename; the live file is never
   moved or removed) → atomically replace the live file with the `.bak`
   content → for todo, rewrite `next_id` to the full allocation max so later
   adds stay above every id ever seen → release. An interrupted restore leaves
   either the damaged original or the restored file in place, never neither.
3. **Gitignore rule** in `.aitask-scripts/aitask_setup.sh`:
   `setup_sitrep_store_gitignore()` cloned from `setup_scratchpad_gitignore()`
   (comment `# Sitrep todo store (per-repo, local-only; not rebuildable)`, rule
   `.aitask-sitrep/`), called in `main()` right after
   `setup_scratchpad_gitignore`; the same rule/comment in
   `upgrade_store_gitignore_rules()` after the scratchpad entry (t2177 parity);
   the rule in this repo's `.gitignore` after the scratchpad block. `seed/` has
   no store-gitignore surface (only `aitask_scripts_gitignore.seed`).
4. **Existing gitignore tests** — `tests/test_setup_git.sh`: add
   `setup_sitrep_store_gitignore|.aitask-sitrep/` to the 27b HELPERS list,
   `.aitask-sitrep/` to `STORE_RULES` (27g2), the helper to `UPGRADE_COVERED`
   and the 27h count `6`→`7` with the new `-e`.
   `tests/test_install_upgrade_dirty_baseline.sh`: add `.aitask-sitrep/` to
   `UPGRADE_RULES`.
5. **`tests/test_sitrep_todo.sh`** (bash, `tests/lib/asserts.sh`, file-backed
   counters if any body runs in a subshell; scratch `AITASK_SITREP_DIR`):
   - round trip + banner: every verb's output file starts with the banner;
     `read` matches a golden; each verb leaves every other record
     byte-identical; a file with the banner removed is refused (exit 4);
   - concurrent writers: 12 background `add`s ⇒ 12 distinct ids, all present;
     concurrent `set-state` + `upsert-context` on different items both survive;
   - **same-item refresh race:** `list --machine` (rev r) → `dismiss c1` →
     `set-state --batch` with `c1|r|done|…` ⇒ `STALE:c1|r+1`, c1 still
     dismissed; batch with the fresh rev on a dismissed item ⇒ `KEPT:`; single
     `set-state --expect-rev` stale ⇒ `STALE`, nothing written; mixed batch
     applies the fresh lines and reports the stale ones;
   - crash mid-write: writer parked at `write:after_backup` and at
     `write:after_counter`, `kill -9` ⇒ `todo.md` whole old generation, next
     writer steals the dead-PID lock and succeeds, the id reserved by the
     killed writer is skipped (gap), stray `.todo.md.XXXXXX` ignored;
   - lock busy vs unusable: live holder + `AITASK_SITREP_LOCK_TIMEOUT=1` ⇒ exit 3
     `LOCK_BUSY`, nothing written; root a regular file / read-only dir / lock
     path a symlink ⇒ exit 4 immediately, not `LOCK_BUSY`;
   - backup + restore: after two writes `.bak` == previous generation; corrupt
     `todo.md` ⇒ mutations exit 4, files untouched; `restore todo` ⇒ live file =
     old `.bak`, damaged copy in `recovered/`; `.bak` corrupt ⇒ restore exit 4;
     **interrupted restore** (kill -9 at `restore:after_preserve`) ⇒ `todo.md`
     is still the damaged original, the next mutation still exits 4, a second
     `restore` succeeds; **deleted `todo.md` with `.bak` present** ⇒ `add`
     exits 4 (not an empty store), `restore todo` recovers;
   - **first use and initialization:** on a fresh root each of these flows
     succeeds with no exit 4 — `add`→`qa`, `qa`→`add`, `retain`→`add`,
     `retain`→`qa`, `situation`→`qa`; after the first verb `store.init`,
     both data files and both backups exist and carry the banner; an `init`
     killed at `init:after_qa` (marker not yet written) is completed by the
     next verb; **genuinely lost established data still refuses:** after
     `add`+`qa`, deleting `qa.md` ⇒ `qa` exit 4 while `add`/`list` keep working,
     `restore qa` recovers; deleting `todo.md` ⇒ `add` exit 4, `qa` keeps
     working; deleting `store.init` AND `todo.md` while `next_id` exists ⇒
     still damaged (exit 4), never re-initialized over the lost data;
   - **ids across recovery:** add c1..c5, `qa --items c5`, corrupt `todo.md`,
     `restore todo` (backup lacks c5), `add` ⇒ `ADDED:c6`; same again with the
     `next_id` file also deleted ⇒ still above every id in todo/qa/recovered;
   - **qa contract:** appends dated entries in order; `## ` body line ⇒ exit 2;
     corrupt `qa.md` ⇒ `qa` exit 4 while todo verbs keep working; writer
     killed at `write:after_backup` during `qa` ⇒ `qa.md` holds every earlier
     entry; `restore qa` recovers from `qa.md.bak`;
   - **sources:** `retain` is idempotent (same pointer twice, one file);
     `upsert-context` with `capture: ~/.config/aitasks/frozen/x/capture.txt#L1-L2`
     or an absolute `file:` ⇒ exit 2; a `capture:` pointer to a missing
     retained file or a range past its end ⇒ exit 2; `check-sources` reports
     `SOURCE_OK` / `SOURCE_MISSING` (after deleting a retained file);
   - schema rejection: context entry with `status:` / `count:` / `next:` /
     unknown key / over-size / missing background ⇒ exit 2, nothing locked or
     written; `|` or newline in fields ⇒ exit 2;
   - idempotency: `add --ref t42` twice ⇒ `EXISTS:`, also after `dismiss`;
   - `..` root ⇒ exit 2 before any filesystem access.
6. **`tests/test_sitrep_todo_format.py`** (unittest) — render∘parse identity,
   every grammar rejection with its line number, banner required,
   heading-from-(state, group), rev bump rules, `max_id_token` on garbage text,
   empty store.
7. `shellcheck .aitask-scripts/aitask_sitrep_todo.sh`; send the t2175_4 note
   (whitelist touchpoints owed there; verb list; skill writes Q&A via `qa`, not
   by editing files).

### Post-phase (risk mitigations)

1. [sitrep_contract_fixture] Commit `tests/fixtures/sitrep/todo_v1.md`,
   `qa_v1.md` and one retained `sources/<hex>.txt` — a writer-produced store
   with every kind, state and group, a situation block, a context entry using
   every key and source type, and a cross-repo `ref`. A test case in
   `tests/test_sitrep_todo.sh` copies it into a scratch root and asserts:
   `read` returns it byte-identical; `list --machine`, `context c<N>` and
   `check-sources` print pinned expected lines; a no-op-equivalent write
   (`update <id> --title <same title>`) leaves it byte-identical. Name the
   fixture as the consumer contract in the helper's and `sitrep_todo.py`'s
   header comments ("a format change edits this fixture and bumps `format=`"),
   and point t2175_2 / t2175_3 at it in the step-0 body additions.

## Verification

- `bash tests/test_sitrep_todo.sh`
- `python3 -m unittest tests.test_sitrep_todo_format` and the Python suite
  (`bash tests/run_all_python_tests.sh`, last line verdict)
- `bash tests/test_setup_git.sh` and `bash tests/test_install_upgrade_dirty_baseline.sh`
- `shellcheck .aitask-scripts/aitask_sitrep_todo.sh`
- Manual smoke in a scratch dir: `add` two items with context, `retain` a
  passage, `set-state`, `situation`, `qa`, then `read` and eyeball the files.

## Post-implementation

Step 9 of the task workflow (commit, archive t2175_1, push via `./ait git`).

## Risk

### Code-health risk: medium
- A Python failure (traceback, partial stdout) inside the locked section could commit a truncated file if the renderer status is not propagated · severity: medium · → mitigation: none (by design: renderer `|| return 1` guards, `ait_atomic_render` empty refusal, crash tests in step 5)
- Strict parser turns a hand-edited or future-format file into "store unusable" (exit 4) · severity: low · → mitigation: none (intended fail-closed; line-1 banner warns; `restore` + `format=` header)
- Recovery and id allocation span several files (`todo.md`, `.bak`, `next_id`, `recovered/`, `qa.md`) — more moving parts than the shadow store · severity: medium · → mitigation: none (each crash point has a pause-seam test in step 5; the allocation rule is a max over all of them, so any single lost file is survivable)
- Setup/upgrade gitignore wiring and its pinned parity tests change together · severity: low · → mitigation: none (27b/27g2/27h/27i/K tests catch drift)

### Goal-achievement risk: low
- The format is fixed before its three consumers (harvest t2175_2, refresh t2175_3, skill t2175_4) exist; a missing field would force a format=2 migration · severity: low (residual — addressed by inline post-phase sitrep_contract_fixture) · → mitigation: inline post-phase sitrep_contract_fixture
- Durable retention is enforced by the writer but performed by harvest (t2175_2); if harvest skips `retain`, items lose their passage on drop · severity: low (residual — the writer rejects non-retained capture pointers, and t2175_2's body carries the drop acceptance check) · → mitigation: none
- "Per-section writes" is delivered as record-level verbs under one mutex rather than physically separate files · severity: low · → mitigation: none (the task leaves one-vs-two files to this task)

### Planned mitigations
- timing: post-phase | name: sitrep_contract_fixture | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — format fixed before its consumers exist | desc: golden v1 fixture + pinned list/context/check-sources output as the consumer contract, referenced from t2175_2/t2175_3

## Post-Review Changes

### Change Request 1 (2026-11-01 17:10)
- **Requested by user:** verify and address four review findings: (1) revs
  restored from an older backup could coincide with a rev an outstanding
  refresh had observed, so a stale batch result applied to a different item
  state; (2) `$`-anchored value regexes accepted a trailing LF (timestamps,
  themes), writing an unparseable item; (3) an unreadable data file read as
  empty (`read` exit 0, no output); (4) `store_state` read all four data files
  on every mutation even when the marker settled it.
- **Changes made:** (1) revs are now store-wide stamps that are never reused:
  allocated from a `next_rev` high-water mark (written before the rename) plus
  a scan of every store file, and pinned to the maximum by `restore`; an
  (id, rev) token names one item state forever. (2) every value regex ends in
  `\Z`; CR/LF in argument values (ref, timestamp, id, theme) is refused, never
  stripped; and every rendered file is parsed back before it reaches the
  wrapper, so a value that slips past validation becomes exit 2, not a corrupt
  write. (3) `_read_tolerant` replaces the lenient reader: only a missing file
  is absent, any other I/O error is exit 4 (read, id/rev scans, state check).
  (4) content is inspected only when no decisive artifact (marker, counters,
  sources/, recovered/) establishes the store.
- **Files affected:** `.aitask-scripts/lib/sitrep_todo.py`,
  `.aitask-scripts/aitask_sitrep_todo.sh`, `tests/test_sitrep_todo.sh`
  (Test 6 rewritten for store-wide revs, new 6b refresh-across-restore, 14b
  trailing newline, 14c unreadable file), `tests/test_sitrep_todo_format.py`,
  `tests/fixtures/sitrep/` (regenerated: revs changed, `next_rev` added).
- **Verification:** bash 218/218, Python 35/35; mutants (per-item rev,
  lenient reads, `$` anchors + no parse-back) each turn both suites red.

## Final Implementation Notes
- **Actual work done:** Step 0 renamed the t2175 family compass → sitrep
  (six task files, label, bodies) and handed durable-pointer / stale-write
  duties to t2175_2 / t2175_3 in their bodies (commit `ait: Rename compass
  feature to sitrep (t2175)`). New `.aitask-scripts/aitask_sitrep_todo.sh`
  (locked writer: validation, `registry_lock.sh` mutex, init, backups,
  counters, atomic commit, restore, test seams) and
  `.aitask-scripts/lib/sitrep_todo.py` (strict parse / validate / mutate /
  render core; render∘parse identity enforced by a canonical check). Gitignore
  rule `.aitask-sitrep/` via `setup_sitrep_store_gitignore()` + the
  `upgrade_store_gitignore_rules()` entry + this repo's `.gitignore`; parity
  tests extended (`tests/test_setup_git.sh` 27b/27g2/27h, the "all nine"
  comment; `tests/test_install_upgrade_dirty_baseline.sh` UPGRADE_RULES).
  Tests: `tests/test_sitrep_todo.sh` (218 assertions), 
  `tests/test_sitrep_todo_format.py` (35), contract fixture
  `tests/fixtures/sitrep/` (store/ + pinned `expected_*.txt`).
- **Deviations from plan:** `read` takes `all|todo|context|qa` (`todo` = Part
  1, `all` the default); `list` accepts `--machine` but needs no flag; extra
  result lines `CONTEXT:…|unchanged`, `SITUATION:…|absent`, per-line
  `NOT_FOUND:c<N>` in batches; the qa header may carry `items: -`. Added
  under-lock sweep of dead writers' staging temps (`.<name>.XXXXXX`) — none
  can belong to a live writer while the mutex is held. `related:` must name
  ids below the allocation mark (a forward reference inflated the id scan —
  found when generating the fixture). Review round 1 (see Post-Review
  Changes): store-wide revs (`next_rev`), `\Z` anchors + CR/LF refusal +
  parse-back of every rendered file, strict I/O in reads, no content reads in
  `store_state` once established.
- **Issues encountered:** Python `$` matching before a final newline
  (review finding); the related-id inflation above; a `rm -rf "$VAR"` in a
  mutant runner was blocked by the safety check — mutants now run in fresh
  `mktemp -d` dirs instead.
- **Key decisions:** one physical `todo.md` + separate `qa.md`; record-level
  verbs + per-item CAS instead of section writes; store-wide never-reused
  revs and ids (high-water counters + structural scans over every store file
  incl. backups and `recovered/`); `store.init` written LAST so "never
  created" and "lost" are distinguishable; `capture:` only into the store's
  own content-addressed `sources/`; the strict parser + line-1 banner make
  hand edits fail closed (`restore`). Whitelist touchpoints deferred to
  t2175_4 (first SKILL.md closure caller).
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - Contract = `tests/fixtures/sitrep/` + the helper's header. A format change
    edits the fixture and bumps `format=`.
  - t2175_2 (harvest): `retain` every passage first, point `capture:` at the
    returned `sources/<hex>.txt#L…`; `add --ref` is idempotent (`EXISTS:` in
    any state, so dismissals stick); `add … --context-file -` writes item +
    stub context atomically; to target another repo's store set
    `AITASK_SITREP_DIR` to its absolute `.aitask-sitrep` path. `related:` may
    only name existing ids — add items first, then `upsert-context`.
  - t2175_3 (refresh): `list --machine` → `set-state --batch` lines
    `<id>|<observed rev>|<state>|<checked_at>|<outcome>`; `STALE:` = changed
    since read (re-read next tick), `KEPT:` = dismissed (never written);
    revs are store-wide stamps, compare for equality only. Every stamp of
    `checked_at` changes the rev.
  - t2175_4 (skill): owes the 5 whitelist touchpoints for
    `aitask_sitrep_todo.sh`; Q&A only via `qa`, dismissals via `dismiss`,
    never by editing files (the parser refuses hand edits).
  - Test seams: `AITASK_SITREP_PAUSE_FIFO` (init:after_qa,
    write:after_counter, write:after_backup, restore:after_preserve),
    `AITASK_SITREP_NOW`, `AITASK_SITREP_LOCK_TIMEOUT`.
