---
Task: t2369_enforce_doc_review_after_feedback.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2369 — Enforce the documentation review after feedback (Step 8)

## Context

In t2258_10 the user had to add a preamble by hand to forwarded shadow concerns,
asking the coding agent to verify them and to write fixes under the doc guide.
The shared Step 8 **Need more changes** loop applies feedback and re-asks, but it
never audits the resulting documentation against the guide's page-type and
reader-level rules. A revision can satisfy a concern's wording while putting
detail on the wrong page, or reach **Commit changes** with a review of an earlier
draft.

Outcome: on any task that changes documentation, Step 8 reviews the task-owned
doc pages against the configured guide before every approval prompt, checks the
factual claims the task introduced, applies feedback (forwarded concerns and
typed feedback alike) under the guide's rules, and refuses to commit a doc
revision whose review evidence is missing or stale. The human commit approval
stays exactly as it is.

Decisions taken with the user during planning:

1. **Helper record.** Each review result is bound to the task-owned path, the
   exact page contents reviewed and the effective guide. Before committing, the
   current set is checked for edits, new pages and renames; anything changed is
   re-reviewed and the approval prompt is shown again.
2. **Shadow preamble → follow-up task.** `DEFAULT_PREAMBLE` in
   `.aitask-scripts/monitor/concern_parser.py` is not touched here.
3. **Gate reuse, verified.** A `docs_updated` result is reused only when the
   applied page is byte-identical to the bytes the review evaluated and the
   guide is unchanged. The actual reader-test status and unresolved findings are
   carried. An old gate pass alone proves nothing; Step 8 reviews every page
   whose evidence is missing or stale.

Plan review round 1 (four blocking concerns, all verified and adopted): evidence
is taken from a frozen copy of the bytes evaluated, not from a hash computed
after the review; a deleted page gets its own recorded outcome; guide resolution
is tri-state and the reviewed scope is compared at commit time; the review
verifies the factual claims the task changed and tracks the implementation files
they rest on.

Plan review round 2 (three blocking concerns, all verified and adopted): the
guide and the review procedure are frozen by a `begin` call before the reviewer
reads either, and one key covers the whole call; a `claims_pending` page exposes
its prior verdict and is finished by a claim-only update that needs no snapshot,
so a resumed session can complete it; a deleted page's prior version is resolved
by the helper from `HEAD`, the deleting commit's parent, or a recorded snapshot.

Plan review round 3 (user direction, adopted): the early Step 8 freshness check
stays, and a second, final check runs immediately before the code commit — after
the plan update, attribution and file selection — comparing the documentation
paths and revisions about to be committed with the review shown at approval. A
changed page, deletion, guide or claim source stops the commit, refreshes the
affected review and asks for approval again. Committing from an immutable review
snapshot is left to t2374.

Plan review round 4 (two blocking concerns, both verified and adopted): the
guarded commit has an explicit failure branch that keeps the non-zero status and
prints its own marker, so a blocked, crashed or missing guard can never read as
success; and each evidence-writing path states where its key comes from —
`begin` opens every round that judges against the guide (full review and
deletion outcome), while the claim-only and disposition updates judge nothing
against the guide, take no key and need no frozen copies.

Plan review round 5 (one blocking concern, verified and adopted): attended Codex
commits the reviewed change through `aitask_gate.sh commit-approved`, not
`git commit`, so the final guard is also specified immediately before that call,
checked against the approval-bound `artifacts` and `deleted` paths. That
helper's own `COMMIT:` / `COMMIT_REFUSED:` handling is kept as it is.

Plan review round 6 (two blocking concerns, both verified and adopted): the
`git commit` form splits its documentation paths into present and deleted with
the same two flags as the Codex form, so a reviewed deletion commits; and on the
Codex path the guard first asks the receipt store, through a new read-only
`aitask_gate.sh commit-outcome` verb, whether this receipt already has a commit —
an interrupted run is then completed by `commit-approved` (`duplicate`) even if
the guide drifted since, instead of being reported as "nothing committed".

Plan review round 7 (one blocking concern, verified and adopted): that exception
is for `applied` only — a commit already on its bound branch. A `prepared`
receipt has a commit object that never landed, and `commit-approved` would
rebuild it on the current tip and move the branch, so it goes through the normal
guard like a receipt with no commit.

Single task, no children. Current-branch mode (profile `fast`).

## Design

### The review record (new helper)

`./.aitask-scripts/aitask_doc_review.sh` (thin bash wrapper) →
`.aitask-scripts/lib/doc_review_record.py`. State lives under
`.aitask-gates/<task_id>/doc_review/` (already gitignored runtime state; root
overridable with `AIT_DOC_REVIEW_DIR` for tests):

- `record.json` — written with `lib/atomic_write.py` under an `fcntl.flock` on
  a sibling lock file (read-modify-write, so atomic rename alone is not enough);
- `snapshots/<sha256>` — frozen, content-addressed copies of reviewed text.

Record shape (`format: 1`):

- `reader_budget_left`;
- `keys` — one entry per review key issued by `begin`: the sha256 of the frozen
  guide copy (or `none`) and of the frozen review-procedure copy;
- `presented` — the scope shown at the last approval prompt: guide state,
  review key, sorted path list;
- one entry per repo-relative path, of kind `page` or `deleted`:
  - `page`: `page_sha256`, `review_key`, `level`, `prose`, `reader`, `claims`
    (`ok` | `findings:N` | `not-run`), `basis` (list of `{path, sha256}` — the
    implementation files the verified claims rest on), `unresolved` (list of
    `{finding, disposition}`), `source` (`step8` | `gate:<run-id>`),
    `reviewed_at`;
  - `deleted`: `review_key`, `prior` (where the removed page's last version was
    read from), `facts` (list of `{fact, disposition}` — where each fact of the
    removed page now lives, or why it was dropped), `reviewed_at`.

**Guide resolution is tri-state**, done by the helper itself (it does not use
`aitask_resolve_config_path.sh`, whose contract prints the same empty line for
"no guide" and "could not run"):

| Line | Meaning |
|---|---|
| `GUIDE:ok\|<path>` | `doc_update.guide` (or the seeded default) names a readable file |
| `GUIDE:none` | the config was read successfully and neither the key nor the default names a file |
| `GUIDE:error\|<reason>` | the config could not be read or parsed, PyYAML is missing, or the guide file exists but is unreadable |

The helper resolves against its own repository root (like the existing
resolver), so in worktree mode the procedure invokes the main checkout's copy
from the work directory: pages and the record are relative to the current
directory, the guide to the main root. `--guide-root <dir>` is a test seam.

**Review key** = sha256 over (a) the guide file's bytes, or the literal `none`
for `GUIDE:none`, and (b) the bytes of
`.claude/skills/aitask-docs-review/SKILL.md` (the procedure that produced the
verdict). Content hashes only, never stat. There is no key under `GUIDE:error`.

Verbs (all exit 0; status in output lines, like `aitask_change_surface.sh`):

| Verb | Output |
|---|---|
| `status <task_id> [--mark-presented\|--against-presented] -- <path>...` | `RECORD:ok\|missing\|unreadable`, the `GUIDE:` line, `REVIEW_KEY:<k>` (the key of the effective guide and procedure as they are now), one `PAGE:<state>\|<path>` per path, for each `current` **and each `claims_pending`** page a `RESULT:<path>\|level=…\|prose=…\|reader=…\|claims=…\|unresolved=<n>\|source=…\|evidence=<sha>` line with its `FINDING:<path>\|<disposition>\|<finding>` and `BASIS:<path>\|<same\|changed\|missing>\|<basis path>` lines, for each `deleted_current` path its `FACT:<path>\|<disposition>\|<fact>` lines, `DROPPED:<path>` for record entries not in the given set, `OPEN_FINDINGS:<n>`, `BUDGET_LEFT:<n>`, `SCOPE:same\|changed\|never_presented` (only with `--against-presented`), and last `SET:current\|stale\|empty\|unverifiable` |
| `begin <task_id>` | freezes the guide and `.claude/skills/aitask-docs-review/SKILL.md` into `snapshots/`, records the key, and prints the `GUIDE:` line, `GUIDE_COPY:<file>` (absent for `GUIDE:none`), `PROCEDURE_COPY:<file>`, `REVIEW_KEY:<k>`. `GUIDE:error` → `BEGIN_REFUSED:<reason>`, no key |
| `snapshot <task_id> [--from <file>] -- <path>` | freezes the live page (or `<file>`, e.g. a gate `.draft`) into `snapshots/<sha>`; prints `SNAPSHOT:<sha>\|<snapshot file>\|<path>` |
| `digest -- <file>...` | `SHA:<sha>\|<file>` (for basis files, read before the claim check) |
| `stamp <task_id> --review-key <k> --snapshot <sha> --level <v> --prose <v> --reader <v> --claims <v> [--basis <sha>:<path>]... [--unresolved-file <json>] [--source <s>] -- <path>` | `STAMPED:<path>` or `STAMP_REFUSED:<reason>\|<path>` |
| `stamp-claims <task_id> --claims <v> [--basis <sha>:<path>]... [--add-unresolved-file <json>] -- <path>` | claim-only update of an existing `page` entry (no key argument); same output |
| `dispose <task_id> --unresolved-file <json> -- <path>` | replaces the dispositions of an existing entry's findings; same output |
| `prior <task_id> -- <path>` | where a removed page's last version can be read: `PRIOR:head\|HEAD:<path>`, `PRIOR:commit_parent\|<sha>^:<path>` with `DELETED_BY:<sha>\|<subject>`, `PRIOR:snapshot\|<snapshot file>`, or `PRIOR:none` |
| `stamp-deleted <task_id> --review-key <k> --prior <spec> --facts-file <json> -- <path>` | `STAMPED:<path>` or `STAMP_REFUSED:<reason>\|<path>` |
| `budget <task_id> [--spend <n>\|--grant <n>]` | `BUDGET_LEFT:<n>` or `BUDGET_REFUSED:<left>` |
| `guard <task_id> [--committing <path>]... [--committing-deleted <path>]... [--receipt <session_id>:<receipt_id>] -- <path>...` | with `--receipt`, first a `RECEIPT_OUTCOME:none\|prepared\|applied\|unknown[\|<commit>]` line; then everything `status --against-presented` prints, one `COMMIT_PATH:presented\|unpresented\|mismatch\|<path>` per `--committing` / `--committing-deleted` path, and last `GUARD:clean` or `GUARD:blocked\|<first reason>`. **The one decision verb: exit 0 only for `GUARD:clean`, exit 1 otherwise** (the exit-code convention of `gate-cli.md`), so a commit can be chained behind it |

Field text is percent-encoded (`%0D %0A %7C %25`).

Page states:

| State | Condition | Needs |
|---|---|---|
| `current` | `page` entry, live bytes hash to `page_sha256`, key matches, `claims` is `ok` or `findings:N`, every basis file still hashes as recorded | nothing |
| `changed` | `page` entry, live bytes differ | full review |
| `rekeyed` | live bytes match, key differs (guide or procedure changed) | full review |
| `claims_pending` | bytes and key match, but `claims=not-run` or a basis file changed or vanished | claim check only |
| `unreviewed` | file exists, no `page` entry | full review |
| `deleted_current` | file absent, `deleted` entry with matching key | nothing |
| `deleted_unreviewed` | file absent, and no `deleted` entry, or its key differs, or the entry is of kind `page` | deletion outcome |
| `unreadable` | exists but is not a readable regular file, or the path is unsafe | stop and report |

A page that reappears after a `deleted` stamp has a file and no `page` entry, so
it reads `unreviewed`: continued absence is checked on every `status`.

Rules that make the verdict trustworthy:

- `SET:current` needs `RECORD:ok`, a `GUIDE:ok` or `GUIDE:none` line, at least
  one path, and every path `current` or `deleted_current`. Zero paths →
  `SET:empty`. `GUIDE:error`, an unparseable record, an unknown `format` or an
  `unreadable` page → `SET:unverifiable`, which is never treated as clean
  (absent ≠ unreadable; no skip-malformed reading). Everything else →
  `SET:stale`.
- **The evidence is the bytes evaluated.** `snapshot` copies the text once into
  a content-addressed file; the reviewer reads that file for its final pass and
  for the fresh-reader test. `stamp --snapshot <sha>` re-hashes the snapshot
  file (refusing `snapshot_missing` / `snapshot_tampered`) and records `<sha>`
  as `page_sha256`. A draft or page edited after the snapshot was taken cannot
  inherit the verdict: its bytes no longer hash to `<sha>`, so `status` reads
  `changed`.
- **The guide evidence is the copy the reviewer read.** `begin` freezes the
  guide and the review procedure before the reviewer reads either, and the key
  is computed from those frozen copies. The reviewer reads `GUIDE_COPY` and
  follows `PROCEDURE_COPY`; one key covers the whole call. The two verbs that
  record a judgement made against the guide — `stamp` and `stamp-deleted` —
  take `--review-key <k>` and refuse unless (a) `<k>` is a key `begin` recorded
  and its frozen copies exist and still hash to it (`unknown_key`,
  `key_copy_missing`, `key_copy_tampered`), and (b) the effective guide and
  procedure, hashed again at that moment, still give `<k>` (`guide_changed`).
  So a review made under guide A cannot be stamped once the guide is B, whenever
  the change happened.
- Each `--basis <sha>:<path>` is re-hashed and refused (`basis_changed`) when
  the file no longer matches what was verified.
- **Where each evidence write gets its key:**

  | Write | Judges against the guide? | Key | Needs `snapshots/`? |
  |---|---|---|---|
  | `stamp` (full page review) | yes | `--review-key` from this round's `begin` | yes: the key's copies and the page snapshot |
  | `stamp-deleted` (deletion outcome) | yes (which page owns each fact) | `--review-key` from this round's `begin` | yes: the key's copies |
  | `stamp-claims` (claim check) | no (claims against the implementation) | none passed; the entry keeps its `review_key` | no |
  | `dispose` (dispositions) | no | none passed; the entry keeps its `review_key` | no |

- **Claim-only refresh needs no `begin`, no key and no snapshot.** `stamp-claims`
  requires an existing `page` entry whose `page_sha256` equals the hash of the
  live page, and whose `review_key` equals the effective key computed from the
  live guide and procedure at that moment (refusing `no_entry`, `page_changed`,
  `guide_changed` — the last is the `rekeyed` state, which needs a full review,
  not a claim update). It replaces `claims` and `basis`, may append findings,
  and keeps `level`, `prose`, `reader`, `unresolved`, `source`, `review_key` and
  the evidence hash as they are. `dispose` has the same preconditions and
  requires the same findings, in the same order, with only the dispositions
  changed. Both read everything they need from `record.json` and the live tree,
  so a fresh session with no memory of the review — and with the whole
  `snapshots/` directory gone, key copies included — can finish a
  `claims_pending` page from what `status` prints.
- **A deletion-only round needs `begin` and nothing else.** `begin` works from a
  fresh state (no record, no `snapshots/`): it creates both, freezes the guide
  and procedure, and issues the key `stamp-deleted` then verifies. No page is
  reviewed to obtain it.
- **A removed page's prior version is resolved, not assumed.** `prior` checks,
  in order: the path in `HEAD` (an uncommitted deletion); the most recent commit
  that deleted the path (`git log -1 --diff-filter=D --no-renames -- <path>`),
  whose parent holds the last version (a deletion or rename committed earlier —
  the resume case); a snapshot recorded for the path (a page created and removed
  within the task); otherwise `PRIOR:none`. `stamp-deleted` takes the spec the
  caller read from, recomputes it and refuses `prior_mismatch`; it refuses
  `still_exists` when the path names a file, and requires at least one fact line
  with a non-empty disposition. With `PRIOR:none` the one allowed outcome is the
  stated fact that the page never had a committed or reviewed version.
- `stamp` validates `level` / `prose` / `reader` against the docs-review report
  values (the six `reader=` values included) and requires a non-empty `finding`
  and `disposition` per unresolved item. Disposition `open` is allowed in the
  record and counted in `OPEN_FINDINGS`.
- Paths: repo-relative, no leading `/`, no `..` segment, no control bytes.
- The set is whatever the caller passes. The helper never scans the dirty tree,
  so another session's edits cannot enter or invalidate the task's reviewed set.
- `--mark-presented` stores the scope only when the verdict is `SET:current` or
  `SET:empty`. `--against-presented` compares guide state, key and the exact
  path list with it; `SCOPE:changed` covers a path added or removed, a guide
  that changed, appeared or disappeared, and a set that became empty.
- Fresh-reader budget: 3 per task, initialised on first use, cumulative across
  rounds; `--grant` only on the user's explicit choice.
- **`guard` is clean only when all of these hold:** `SCOPE:same` (guide state,
  key and path list equal to what was presented at approval); `SET:current` with
  `OPEN_FINDINGS:0`, or `SET:empty`; and every `--committing` and
  `--committing-deleted` path is in the presented scope (`unpresented`
  otherwise). The two flags are the two things a commit can do to a page, on
  every commit path: `--committing` names a page whose **content** is committed
  and must read `current`; `--committing-deleted` names a page whose **removal**
  is committed and must read `deleted_current`. A path given under the wrong
  flag is a `mismatch`: the commit would add or remove something the review did
  not present that way. Each state is recomputed from
  the live tree at that moment,
  so a page edited, deleted or recreated, a guide that changed, and a claim
  basis file that changed since approval all block. Anything unverifiable
  blocks. It writes nothing.
- **`guard --receipt` recognises a commit that has already landed.** Before
  evaluating anything it runs `aitask_gate.sh commit-outcome <task_id>
  <session_id>:<receipt_id>` (new, read-only — see "Codex commit path"). Only
  `applied` is exempt: the receipt store, which is the authority, holds a commit
  for this receipt that is already on its bound branch. The guard prints
  `RECEIPT_OUTCOME:applied|<commit>` and `GUARD:clean|existing_commit` and exits
  0 **without** judging drift: nothing new can land, and `commit-approved` will
  return `duplicate`. Every other outcome is evaluated normally:
  - `prepared` — a commit object exists but never reached the branch.
    `commit-approved` would build it again on the current tip and move the
    branch, which is a commit landing now, so current drift must block it.
  - `none` — no commit for this receipt.
  - `unknown` (the store could not be read, the verb failed or printed something
    else) — the fail-closed direction: drift blocks, and a store that cannot be
    read makes `commit-approved` refuse anyway.

  The `RECEIPT_OUTCOME:` line is printed in every case, so a blocked guard says
  which of these it was.

### `aitask-docs-review`: the verdict is on a frozen copy

`.claude/skills/aitask-docs-review/SKILL.md` gains two optional arguments that
go together, `--evidence <task_id>` and `--review-key <k>`, and one invariant.
Without them the skill behaves as today. With them the **caller has already run
`begin`** and is following the frozen `PROCEDURE_COPY`, and:

- the guide read in Step 1 is the `GUIDE_COPY` file `begin` printed, never the
  live path and never a second resolution (`GUIDE:none` → the existing no-guide
  path; a `BEGIN_REFUSED` never reaches the skill — the caller stops first);
- `<k>` is the only key the call uses, and it is echoed in the report footer;
- after the last change to a page in this call (Step 3 fixes, and any fact moved
  in from another page), the reviewer runs `snapshot` for it — `--from <draft>`
  with `--caller gate`, the live page otherwise — and makes its final level and
  prose pass, and the fresh-reader test, on the snapshot file. A finding it
  fixes in that pass edits the draft and takes a new snapshot; the pass repeats
  until it changes nothing;
- the page's report line gains `evidence=<sha>` (the snapshot the verdict is
  about).

So a draft the reviewer edits or creates is covered by the same rule as one it
only reads, and nothing downstream hashes a file "after the review".

### New procedure: `.claude/skills/task-workflow/doc-review.md`

"Documentation Review Procedure". No Jinja (profile-invariant). Sections:

**`## Task-owned documentation set`**
1. Read the guide state from the helper (`status` with no paths prints the
   `GUIDE:` line). `GUIDE:error` → show the reason and ask the user (fix and
   retry / abort the review round and return to the prompt with the error shown
   — never continue as if there were no documentation). `GUIDE:none` → the set
   is empty by definition; display "no doc-update guide configured —
   documentation review not run" in the round's output and in the prompt text.
2. `aitask_change_surface.sh list <task_id>` (never raw `git diff`).
   `COMMITTED:` / `TASK:` are in scope, `OTHER:` never. An `UNKNOWN:` path is
   included without asking only when this session itself created or edited it
   during this run (say so); otherwise ask once with the gate's step-2b "Scope"
   question and keep the answer for the rest of the run.
3. Keep the paths that are documentation pages under the doc roots the guide
   names (the guide is the source of truth for the roots; a page is a text
   document a reader reads — images and data files are not pages). Deleted and
   renamed-away pages stay in the set.
4. `DROPPED:` lines from `status` are reported, never ignored: a page reviewed
   earlier that is no longer in the set means the scope changed.

**`## Review round`** — run before every Step 8 approval prompt.
1. Derive the set, then `status`. Pages `current` / `deleted_current` reuse
   their recorded result. **Open the round with `begin` exactly when `status`
   shows a page that needs a full review or a deletion outcome** (`changed`,
   `rekeyed`, `unreviewed`, `deleted_unreviewed`) — before reading the guide for
   either. `BEGIN_REFUSED` → the `GUIDE:error` handling above. One `begin` per
   round; its key `<k>` is used by every `stamp` and `stamp-deleted` of the
   round. A round whose only work is `claims_pending` pages or dispositions runs
   no `begin` at all. A `guide_changed`, `key_copy_missing` or
   `key_copy_tampered` refusal from `stamp` / `stamp-deleted` means the round's
   guide evidence is gone: start the round again from `begin`.
2. **Full review** (`changed`, `rekeyed`, `unreviewed`): read and follow the
   `PROCEDURE_COPY` that `begin` printed — the frozen copy of the review skill —
   with those live paths, `--caller audit`, `--evidence <task_id>`,
   `--review-key <k>`, `--budget <BUDGET_LEFT>`. Reuse a
   page's earlier fresh-reader questions when it is re-tested (kept in
   `.aitask-gates/<task_id>/doc_review/questions/<page path>`).
   `budget --spend` the review's `BUDGET_USED`.
3. **Claim check** (every page under full review, and every `claims_pending`
   page). Scope: the factual claims this task introduced or changed on the page
   — for a new page all of them, otherwise the claims in the task's diff of that
   page (commands, flags, paths, defaults, outputs, described behaviour).
   `digest` the implementation files each claim rests on, verify the claim
   against them (read the code, run a read-only command), and record
   `claims=ok` or `claims=findings:N` with the basis list. A claim found wrong
   is corrected or dropped with the reason; it is never left as a deferred
   finding. A claim with no implementation file to rest on (a design statement)
   is listed with its source instead of a basis. A page under full review
   carries the result into its `stamp`; a `claims_pending` page — its level,
   prose, reader results and findings come from the `RESULT` / `FINDING` /
   `BASIS` lines `status` printed, so this works in a session that never saw the
   original review — is finished with `stamp-claims`, which takes no key and
   needs neither `begin` nor `snapshots/`. A `guide_changed` refusal there means
   the page became `rekeyed` meanwhile: it is a full-review page (step 1's
   `begin` applies). If the claim check edits the page, it is likewise a
   full-review page from then on.
4. **Deletion outcome** (`deleted_unreviewed`), under the round's `begin`: the
   ownership rules are read from `GUIDE_COPY`. Run `prior` and read the page
   from the spec it prints (`git show <spec>` or the snapshot file) — `HEAD` for
   an uncommitted deletion, the deleting commit's parent for a deletion or
   rename an earlier `(t<id>)` commit of this task already made. List its facts
   and record for each where it now lives or why it was dropped
   (`stamp-deleted --review-key <k> --prior <spec>`). A rename is one line: "moved to
   `<new path>`", and the new path is reviewed as a page.
5. The audit caller reports only, so the implementing agent applies the fixes it
   can make under the guide (level, page type, prose; a cut fact moves to its
   owning page and is never deleted). Any page it edits — including a receiving
   page that was not in the set before — joins the set and goes through steps
   2-3 again. Repeat until a pass leaves every page unedited.
6. `stamp` each page with the review's `evidence=<sha>`, the round's key, the
   actual `level` / `prose` / `reader` values, the claim result and basis. A
   `STAMP_REFUSED` page goes back to step 2 (or step 3 for `basis_changed`).
7. Every unresolved finding gets an explicit disposition before the prompt:
   fixed (then it is no longer unresolved), deferred (naming the follow-up task
   or note), or left as is with the reason. No finding may stay `open`; a
   carried-over gate finding gets its disposition through `dispose`.
8. A page newly `reader=not-run(cap)` this round: ask the gate's 4a "Reader"
   question once (interactive only); "Run more" → `budget --grant`, re-review
   those pages. Not asked again for an unchanged page.
9. `status --mark-presented` over the final set, then return the summary block
   for the approval prompt: per page `level=`, `prose=`, `reader=`, `claims=`,
   source (this round / reused / from the `docs_updated` run), each unresolved
   finding with its disposition, each deleted or renamed page with where its
   facts went. An empty set returns no block (the "task with no documentation
   changes" case), unless the guide state line from step 1 of the set section
   has to be shown.

**`## Applying feedback to documentation`** — the rules for **Need more
changes**, for forwarded shadow concerns and typed feedback alike:
- treat each item as a finding to investigate, not an instruction to transcribe;
- verify its factual claims against the implementation before editing;
- proposed wording is advisory unless the user explicitly asks for exact text;
- put a confirmed fix on the page that owns that kind of detail under the
  guide's page-type and reader-level rules, at that page's declared level — not
  on whichever page the concern quoted (so reference detail does not land in a
  how-to);
- a fact that moves is recorded (from → to); a fact found wrong is corrected or
  dropped with the reason;
- when the feedback changes the implementation, revisit the task's documented
  claims about it: the next round's `claims_pending` pages are the ones whose
  recorded basis changed, and the agent also re-checks any task-changed claim
  that describes the changed behaviour without a recorded basis file;
- report one resolution per item: fixed (where), already addressed (evidence),
  incorrect (evidence), or deferred (disposition).

**`## Commit check`** — first action after the user picks **Commit changes**.
Re-derive the set and run `status --against-presented`. Continue to the commit
only on `SCOPE:same` together with `SET:current` and `OPEN_FINDINGS:0`, or with
`SET:empty`. Anything else — an edit, a new or renamed or deleted page, a guide
that changed, appeared or could not be resolved, a set that changed or emptied,
a changed basis file, an unreadable record — commits nothing: say which pages or
which scope fact is stale and why, run `## Review round`, and return to the top
of Step 8 so the approval prompt is issued again with the refreshed results.
This early check stays: it stops before the plan file is consolidated.

**`## Final commit guard`** — the last action before the code commit, after the
plan consolidation, both attribution procedures and the selection of
`<changed_code_files>`. Minutes can pass between the early check and this point,
and the plan update and attribution run in between.
1. Re-derive the documentation set, and pick out the documentation pages among
   `<changed_code_files>` (same doc-root rule as the set). Split them by what
   the pathspec commit will do with each: a page that exists in the working tree
   has its content committed (`--committing`); a tracked page that no longer
   exists has its deletion committed (`--committing-deleted`). `git commit --
   <paths>` takes both from the working tree with no `git add`.
2. Run the commit chained behind the guard, in one command, so that no code
   commit can be created unless the guard succeeded:
   ```bash
   if ./.aitask-scripts/aitask_doc_review.sh guard <task_id> \
        --committing <doc page in the commit that exists>... \
        --committing-deleted <doc page in the commit that was removed>... \
        -- <documentation set>...; then
     git add -- <changed_code_files_git_does_not_track_yet> &&
     git commit -F - -- <changed_code_files> <<'EOF'
     …
     EOF
   else
     rc=$?
     echo "DOC_GUARD_FAILED:$rc"
     exit "$rc"
   fi
   ```
   The `else` branch is load-bearing: a bare `if …; then …; fi` returns 0 when
   the guard fails and no branch runs. `$?` in the `else` is the guard's own
   status, so the whole command fails with it — 1 for `GUARD:blocked`, and
   whatever a crashed or missing helper returned (e.g. 127), which prints no
   `GUARD:` line at all. `DOC_GUARD_FAILED:<rc>` is printed by the command
   itself for exactly that case. The guard comes before the `git add`, so a
   failed guard also stages nothing.
3. **The commit happened only when all three hold:** the command's exit status
   is 0, the output has `GUARD:clean`, and it has git's `[<branch> <sha>]` line.
   Anything else — a non-zero status, `DOC_GUARD_FAILED:`, `GUARD:blocked`, a
   missing `GUARD:clean` — is the failed route: **no code commit, and the
   plan-file commit that follows is not run either**. Show the guard's reason
   and the stale `PAGE:` / `COMMIT_PATH:` lines (or, when the helper printed no
   verdict, its status and stderr), run `## Review round` for the affected
   pages, and return to the top of Step 8: the approval prompt is issued again.
   A helper that keeps failing without a verdict is reported to the user at that
   prompt; it is never worked around by committing unguarded. The consolidated
   plan file stays as written (it is re-consolidated after the next approval).
4. A task with no documentation (`SET:empty`, nothing `--committing`) passes the
   guard and commits as today.
5. **When the agent commits the reviewed change through
   `aitask_gate.sh commit-approved`** (attended Codex — it must not run
   `git commit` for the reviewed change), the guard goes immediately before
   that call instead, in the same `if`/`else` shape:
   ```bash
   if ./.aitask-scripts/aitask_doc_review.sh guard <task_id> \
        --receipt <session_id>:<receipt_id> \
        --committing <doc page among the review question's artifacts>... \
        --committing-deleted <doc page among its deleted paths>... \
        -- <documentation set>...; then
     ./.aitask-scripts/aitask_gate.sh commit-approved <task_id> \
         <session_id>:<receipt_id> <message-file>
   else
     rc=$?
     echo "DOC_GUARD_FAILED:$rc"
     exit "$rc"
   fi
   ```
   The paths checked are the ones the approval bound — the review question's
   `artifacts` and `deleted` lists — because those, with the bytes stored when
   the question was asked, are what `commit-approved` commits. That stored
   snapshot stays the commit input; the guard adds only the question of whether
   the documentation among those paths is the reviewed one.
   - **Success** is the helper's own: `COMMIT:committed|<commit>`,
     `COMMIT:duplicate|<commit>` or `COMMIT:committed_index_not_refreshed|<commit>`
     after `GUARD:clean`, with exit status 0. There is no `[<branch> <sha>]`
     line on this path and its absence means nothing.
   - **`COMMIT_REFUSED:<reason>` (exit 3, no `DOC_GUARD_FAILED:` line)** keeps
     its existing handling unchanged: nothing was committed; show the current
     change and ask for the review again under a new `opening`.
   - **Recovery of an interrupted run.** `--receipt` makes the guard ask the
     receipt store first. If an earlier run already landed the commit for this
     receipt on its branch and the session stopped before the gate was recorded
     (`RECEIPT_OUTCOME:applied`), the guard is `GUARD:clean|existing_commit`
     whatever changed since — including the guide — and `commit-approved`
     returns `COMMIT:duplicate|<the original commit>`. No second commit is
     created, and the gate is then recorded with the same `approval=` as usual.
   - **An interrupted run that never landed** (`RECEIPT_OUTCOME:prepared`: the
     session stopped between creating the commit object and moving the branch)
     gets no exception. With nothing changed since, the guard is clean and
     `commit-approved` finishes the run. With drift, the guard blocks: the
     branch tip stays where it is and the prepared commit object is left
     unreferenced.
   - **`DOC_GUARD_FAILED:<rc>`** therefore means: no commit for this receipt is
     on its branch (`RECEIPT_OUTCOME:none` or `prepared`), or the store could
     not be asked (`unknown`), **and** `commit-approved` was not called in this
     run. Nothing landed, no gate record, no plan commit. With `unknown`, say
     so — an earlier landed commit cannot be ruled out, so run
     `aitask_gate.sh commit-outcome <task_id> <session_id>:<receipt_id>` again
     before asking the user anything. Otherwise refresh the affected review,
     return to the top of Step 8 and ask again under a new `opening` (a new
     receipt; for `prepared` the old claim simply stays unapplied).
   `commit-approved` already refuses (`stale_approval`) when a bound file no
   longer has the bytes that were approved, so on this path the guard and the
   helper together tie the committed bytes to the reviewed ones.

On the `git commit` path the guard and the commit are two processes, so an edit
landing between them is not excluded. That residual window, and committing from
an immutable review snapshot on every path, belong to t2374.

### Step 8 wiring — `.claude/skills/task-workflow/SKILL.md`

- New bullet after the related-work re-check and before "Show change summary":
  execute `doc-review.md` `## Review round`. It runs on every pass through
  Step 8, so the first review and every post-feedback review are covered.
- The approval prompt: when the round returned a summary block, the question
  text carries it (the widget is the only surface the user is sure to read).
- **Commit changes** branch: `## Commit check` becomes its first sub-step, ahead
  of plan externalization. On any non-clean result nothing is committed.
- **Code commit** sub-step: the command block becomes the guarded form of
  `## Final commit guard` (guard → `git add` → `git commit` inside one `if`,
  with the `else` branch that prints `DOC_GUARD_FAILED:` and exits with the
  guard's status). The text states the failed route: no code commit, no plan
  commit, refresh, back to the top of Step 8. It adds one sentence pointing an
  agent that commits the reviewed change through `aitask_gate.sh commit-approved`
  at item 5 of that section. No `{% if agent %}` gate is introduced: both forms
  live in the agent-neutral procedure file. The "skip this commit entirely if there are no code
  changes" rule is unchanged; the plan-file commit that follows runs only after
  a code commit was made or legitimately skipped, never after a blocked guard.
- "Final Implementation Notes" template gains
  `- **Documentation review:**` (per-page results and dispositions, or "No
  documentation changed"), so the evidence outlives `.aitask-gates/`.
- **Need more changes** branch: "Make the requested changes" points at
  `## Applying feedback to documentation` whenever the feedback changes or may
  change a documentation page or the behaviour a task-changed page describes;
  the Change Request entry gains a `- **Concern resolutions:**` line.
- The procedure-gate dispatch keeps skipping a gate already `pass`/`skip`; the
  text gains one sentence saying that this is why the documentation review
  below does not depend on the gate.

### Gate reuse — `.claude/skills/aitask-gate-docs-updated/SKILL.md`

Step 3b runs `begin` before each review call, follows the printed
`PROCEDURE_COPY`, and passes `--evidence <task-id> --review-key <k>`. After the
call, for every page in the report, the gate runs `stamp` under the page's
destination path with the reported `evidence=<sha>` and that `<k>`, `--source
gate:<run-id>`, the review's actual `level` / `prose` / `reader` values,
`--claims not-run`, and its unresolved findings (disposition `open`). The gate
computes no hash of its own. Consequences, all from the existing rules:

- applied page == evaluated snapshot and guide unchanged → Step 8 reads
  `claims_pending`: level, prose and reader results are reused, and only the
  claim check runs;
- a draft changed after its review (Adjust, reconciliation, a moved fact) is
  re-reviewed by the gate's own rule, which takes a new snapshot and re-stamps;
  if anything slips through, the applied bytes do not hash to the evidence and
  Step 8 reads `changed`;
- a `STAMP_REFUSED` is logged in the step-6 sidecar and changes nothing else —
  Step 8 then simply reviews that page.

The gate's budget file and apply table are untouched.

### Codex commit path — `.agents/skills/codex_tool_mapping.md`

"Approval gates" → **The review commit** bullet: the `commit-approved` command
block becomes the guarded form of `doc-review.md` `## Final commit guard`
item 5. The mapping states what is Codex-specific and nothing else:

- the command block itself (with `--receipt`), and one sentence saying that the
  documentation pages among `artifacts` and `deleted` are what the guard's
  `--committing` / `--committing-deleted` arguments name;
- `COMMIT:…` and `COMMIT_REFUSED:` exactly as the bullet already describes them
  (unchanged text);
- **`DOC_GUARD_FAILED:` is delegated, not restated:** "the documentation guard
  stopped before `commit-approved` ran in this call. Do not conclude that the
  receipt is unclaimed or that no commit exists. Read the `RECEIPT_OUTCOME:`
  line and follow `## Final commit guard` item 5 of the workflow's
  `doc-review.md`, which says what to do for `none`, `prepared` and `unknown`."
  The mapping carries no outcome table of its own, so it cannot drift from the
  procedure.

The `review_approved` artifacts rule above the bullet is unchanged.

**New read-only verb** `aitask_gate.sh commit-outcome <task-id>
<session_id>:<receipt_id>` (`aitask_questions/approval.py` verb
`commit-outcome`, beside `check`). It answers one question from the receipt
store — does this receipt already have a review commit? — and changes nothing:

| Line | Meaning |
|---|---|
| `COMMIT_OUTCOME:none` | no question state, no such occurrence in this checkout, or it has no consumption |
| `COMMIT_OUTCOME:prepared\|<commit>` | this receipt is claimed for `t<task>:review_approved` with a recorded commit that is not on its bound branch yet |
| `COMMIT_OUTCOME:applied\|<commit>` | the same, and the commit is an ancestor of the bound branch (the test `commit()` uses for `duplicate`) |
| `COMMIT_OUTCOME:other\|<reason>` | the occurrence is claimed by another consumer or another receipt, or the claim was revoked — `commit-approved` will refuse; the guard treats it as `none` |

It matches the occurrence by session id, checks the project, the consumer key
(`consumer_key(task, "review_approved")`) and the receipt id exactly as
`commit()` does, never creates the state database to say there is none (the
existing `check` rule), always exits 0, and is not scoped to a Codex session
(like `commit-approved`). `commit-approved`, the claim, the store schema and
every existing verb are unchanged.

## Implementation steps

Before editing any existing file: `git status --porcelain -- <file>` must be
empty (this checkout is shared and already dirty — `CLAUDE.md` and several
website pages carry another session's edits). A dirty target → stop and ask.
`CLAUDE.md` is deliberately not edited.

1. **Helper.** Write `.aitask-scripts/lib/doc_review_record.py` and
   `.aitask-scripts/aitask_doc_review.sh` per `aidocs/framework/shell_conventions.md`
   (read it first). The guide resolution reads
   `aitasks/metadata/project_config.yaml` strictly (it does not reuse
   `config_utils.load_yaml_config` if that swallows parse errors — check, and
   keep the candidate order of `resolve_config_path`: configured value, then the
   seeded default). `shellcheck` clean.
2. **Whitelist the helper** at the 5 touchpoints
   (`aidocs/framework/aitasks_extension_points.md` "Adding a new helper script"):
   `.claude/settings.local.json`, `.codex/rules/default.rules`,
   `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
   `seed/opencode_config.seed.json`. Check with
   `aitask_audit_wrappers.sh audit-helper-whitelist aitask_doc_review.sh`.
3. **Helper test** `tests/test_doc_review_record.sh` (private `TMPDIR` via
   `tests/lib/run_tmpdir.sh`; file-backed counters if subshells are used). Cases:
   - page lifecycle: unreviewed → snapshot → stamp → current; page edit →
     `changed`; guide edit → `rekeyed`; review-procedure edit → `rekeyed`; new
     path → `unreviewed`; an unrelated dirty file does not change the verdict;
   - evaluated bytes: snapshot a draft, **edit the draft, then stamp** → the
     entry holds the snapshot's hash, applying the edited draft reads `changed`,
     applying the snapshot bytes reads `claims_pending` (gate source) ; a
     tampered or removed snapshot file → `STAMP_REFUSED`;
   - guide evidence: `begin` under guide A, **guide edited to B before the first
     page snapshot**, stamp with A's key → `STAMP_REFUSED:guide_changed` (the
     round-2 scenario); guide edited after the last snapshot and before `stamp`
     → refused the same way; guide edited to B and back to A → accepted; a key
     never issued by `begin` → `unknown_key`; a tampered `GUIDE_COPY` →
     `key_copy_tampered`; `GUIDE_COPY` holds A's bytes after the live guide
     became B; the key's copies removed → `key_copy_missing`; `begin` under an
     unparseable config → `BEGIN_REFUSED`; `guide_changed`, `unknown_key` and the
     copy refusals from `stamp-deleted` too;
   - deletion-only round **from a fresh state** (no record, no `snapshots/`, no
     page ever reviewed): `begin` → `prior` → `stamp-deleted --review-key <k>` →
     `deleted_current`, `SET:current`, and the record holds no `page` entry; the
     same sequence without `begin` (a made-up key) → `unknown_key`;
   - gate reuse: **old gate stamp + later doc edit → `changed`**; gate stamp +
     guide change → `rekeyed`;
   - deletion: **deletion-only set with no prior record** →
     `deleted_unreviewed`, `SET:stale`; `stamp-deleted` → `deleted_current`,
     `SET:current`; the file reappears → `unreviewed`; `stamp-deleted` on an
     existing file → `STAMP_REFUSED:still_exists`; rename (old
     `deleted_unreviewed`, new `unreviewed`); a `page` entry whose file vanished
     → `deleted_unreviewed`;
   - prior version, one fixture each: uncommitted deletion → `PRIOR:head`;
     **page deleted by an earlier commit, no snapshot, fresh record** →
     `PRIOR:commit_parent|<sha>^:<path>` and `git show` of that spec returns the
     old page; a committed rename → the old path resolves the same way; a page
     created and removed inside the task with a recorded snapshot →
     `PRIOR:snapshot`; none of these → `PRIOR:none`; `stamp-deleted` with a spec
     that is not the one `prior` computes → `STAMP_REFUSED:prior_mismatch`;
   - claims: `--claims not-run` → `claims_pending`; `claims=ok` with a basis →
     `current`; basis file edited → `claims_pending`; basis file removed →
     `claims_pending`; basis edited between `digest` and `stamp` →
     `STAMP_REFUSED:basis_changed`;
   - claim-only refresh across a fresh session: gate-sourced stamp with a
     finding, then **delete the whole `snapshots/` directory (page snapshot and
     key copies) and run no `begin`**, then `status` prints the `RESULT`,
     `FINDING` and `evidence=` of the `claims_pending` page; `stamp-claims`
     (no key argument) → `current` with level, prose, reader, source,
     `review_key`, evidence and the finding unchanged; `dispose` changes only
     the disposition and refuses a different finding list; `stamp-claims` on an
     edited page → `STAMP_REFUSED:page_changed`, with no entry → `no_entry`,
     **after a guide edit → `STAMP_REFUSED:guide_changed`** (the entry is
     `rekeyed`, and a claim update must not refresh it);
   - guide: no config key and no default file → `GUIDE:none`, zero paths →
     `SET:empty`; unparseable config → `GUIDE:error`, `SET:unverifiable`;
     unreadable guide file → `GUIDE:error`; `none` key ≠ any guide key;
   - scope: `--mark-presented` then `--against-presented` → `SCOPE:same`; a
     path added, a path removed, the set emptied, the guide edited, the guide
     removed, each → `SCOPE:changed`; never presented → `never_presented`;
     `--mark-presented` on a stale set stores nothing; `DROPPED:` printed for a
     recorded path left out of the set;
   - record: missing → `RECORD:missing`; corrupt and unknown format →
     `RECORD:unreadable` and `SET:unverifiable`;
   - final guard, in a fixture git repository. The test runs the guarded command
     as one `bash -c` script of the exact shape Step 8 documents (guard →
     `git add` → `git commit` in the `then`, `DOC_GUARD_FAILED` + `exit "$rc"`
     in the `else`), with an untracked file in the commit list so the `git add`
     is exercised, and asserts three things every time: **the status of the
     whole command, `git diff --cached --name-only` (the index), and
     `git rev-list --count HEAD`**.
     - **A tracked page edited after a clean `status --against-presented` and
       before the guard → status 1, `GUARD:blocked`, `DOC_GUARD_FAILED:1`, the
       page reads `changed`, index empty, commit count unchanged**; then
       re-review, re-present, run the same command → status 0, `GUARD:clean`,
       exactly one new commit.
     - Same three assertions for: a presented page deleted, a deleted page
       recreated, the guide edited, a claim basis file edited, a documentation
       page in `--committing` that was never presented
       (`COMMIT_PATH:unpresented`), an open finding, a corrupt record, an
       unparseable config.
     - **No verdict at all:** the helper path does not exist → status 127,
       `DOC_GUARD_FAILED:127`, no `GUARD:` line, index empty, commit count
       unchanged; the helper crashes (a stub that exits 3 before printing a
       verdict, and the real helper with a broken Python library path) →
       non-zero status, `DOC_GUARD_FAILED:`, no commit.
     - **Negative control for the `else` branch:** the same blocked case run
       through the bare `if …; then …; fi` form returns status 0 — recorded as
       the reason the branch exists, so the test fails if someone removes it
       from the documented block and the helper test follows.
     - Positive controls: nothing changed → status 0 and one commit; a
       no-documentation task (`SET:empty` presented) → status 0 and one commit;
       an unrelated file edited → status 0.
     - **The `commit-approved` form**, same `if`/`else` shape, with a stub in
       place of `aitask_gate.sh` that appends one line per invocation (verb and
       arguments) to a log and prints and exits as told. The log is read **per
       verb**: the read-only `commit-outcome` call is expected whenever
       `--receipt` is given; what each blocked case asserts is that **no
       `commit-approved` line was logged**. Guard blocked (tracked page edited
       after presentation, `commit-outcome` → `none`) → status 1,
       `DOC_GUARD_FAILED:1`, the log holds exactly one `commit-outcome` line
       with the task id and receipt and zero `commit-approved` lines, commit
       count unchanged; guard clean + stub prints `COMMIT:committed|<sha>` →
       status 0, one `commit-outcome` line then one `commit-approved` line with
       the task id, receipt and message file; guard clean + stub prints
       `COMMIT_REFUSED:stale_approval` and exits 3 → status 3 and **no**
       `DOC_GUARD_FAILED:` line, so a commit refusal is not mistaken for a
       guard failure; helper missing → 127, the log is empty (neither verb ran).
     - `--committing-deleted`: a presented, absent, `deleted_current` page →
       clean; the path exists again → `COMMIT_PATH:mismatch`, blocked; a path
       given as `--committing` that is absent → `mismatch`, blocked; a deleted
       page never presented → `unpresented`, blocked.
     - **Deletion-only task through the documented `git commit` form:** one
       tracked page removed, `begin` → `prior` → `stamp-deleted` →
       `--mark-presented`, then the guarded block with
       `--committing-deleted <page>` and `git commit -- <page>` → status 0,
       `GUARD:clean`, exactly one new commit, and `git show --stat` of it lists
       that page as deleted. Control: the same page passed as `--committing`
       → `mismatch`, status 1, no commit. A mixed commit (one edited page, one
       deleted page, one code file) → status 0 and one commit holding all three.
     - **Interrupted Codex run, then guide drift** (stubbed store verbs): the
       stub's `commit-outcome` prints `COMMIT_OUTCOME:applied|<sha>`, the guide
       is edited after presentation → `RECEIPT_OUTCOME:applied|<sha>`,
       `GUARD:clean|existing_commit`, status 0, `commit-approved` is called once
       and its `COMMIT:duplicate|<sha>` is the output, commit count unchanged.
       **`prepared|<sha>` with the same drift → `RECEIPT_OUTCOME:prepared|<sha>`,
       `GUARD:blocked`, status 1, `DOC_GUARD_FAILED:1`, `commit-approved` not
       called, and `git rev-parse <branch>` is the same before and after**;
       `prepared` with no drift → clean, `commit-approved` called once. With
       `none` and the same drift → blocked,
       `commit-approved` not called. With `other|conflict`, and with a
       `commit-outcome` that exits non-zero or prints garbage (`unknown`) →
       evaluated normally: drift blocks, no drift is clean. Without `--receipt`
       the helper never calls `commit-outcome` (the stub's log shows it).
     - `guard` leaves `record.json` byte-identical;
   - open finding counted; results, findings and facts round-trip with `|` and a
     newline in the text; enum and unsafe-path refusals; budget init / spend /
     refuse / grant.
4. **Review skill edit** `.claude/skills/aitask-docs-review/SKILL.md`
   (`--evidence` with `--review-key`, reading `GUIDE_COPY`, the frozen-copy
   invariant, `evidence=` in the report). No rule text from the guide is copied
   in.
5. **Procedure file** `.claude/skills/task-workflow/doc-review.md`.
6. **Step 8 edits** in `.claude/skills/task-workflow/SKILL.md` (list above).
7. **Gate edit** in `.claude/skills/aitask-gate-docs-updated/SKILL.md` step 3b.
   **Codex mapping edit** in `.agents/skills/codex_tool_mapping.md` (clean in
   `git status` at planning time; re-check before editing). It is listed by
   `install.sh`, `.github/workflows/release.yml`, `tests/test_agent_instructions.sh`,
   `tests/test_codex_entrypoints_tool_mapping.sh` and
   `aidocs/codeagents/codex_questions.md`: read those five for a pinned copy or
   quoted text of the review-commit bullet and update whatever pins it; add the
   guard to the "Committing a reviewed change" section of
   `aidocs/codeagents/codex_questions.md` in one paragraph.
   **`commit-outcome` verb:** `aitask_questions/approval.py` (parser entry and
   a small read-only function next to `check`) and `aitask_gate.sh`
   (`cmd_commit_outcome`, dispatch line, usage text, the header verb list).
   Both files are clean in `git status` at planning time; re-check. The helper
   calls it as `"$SCRIPT_DIR/aitask_gate.sh"`, overridable with
   `AIT_DOC_REVIEW_GATE_CMD` for tests. `aitask_gate.sh` is already
   whitelisted; no new touchpoint.
8. **Inventories for the new procedure file:** add `doc-review.md` to
   `WRAPPED_FILES_INVARIANT` in `tests/test_skill_render_task_workflow.sh`
   (with a comment) and create `tests/golden/procs/task-workflow/doc-review-default.md`.
   Re-grep a sibling (`grep -rn "resource-admission\.md" tests/ aidocs/ .aitask-scripts/ seed/`)
   at implementation time and add `doc-review.md` wherever a list of procedure
   files turns up that the planning grep did not show.
9. **Regenerate goldens:** `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`
   with the command in `aidocs/framework/skill_authoring_conventions.md`
   ("Regenerate goldens…"; read that doc before editing the skill files).
   Review the diff: it must contain only the Step 8 changes.
10. **Committed rendered variants** (`.claude/skills/task-workflow-remote-/`,
    `.opencode/skills/task-workflow-remote-/`,
    `.agents/skills/task-workflow-remote-codex-/`). The first two are already
    dirty from an earlier, uncommitted re-render (t1912_3's `task-data-push.md`).
    Decision rule: render the `remote` closure from `HEAD` in an isolated
    `git worktree` and compare with the dirty files. If they are identical, the
    existing dirt is exactly the owed catch-up; re-render with
    `aitask_skill_render.sh task-workflow --profile remote --agent <agent>` and
    commit the result, naming the catch-up at review. If they differ (another
    session's work in progress), do not touch those files; record the owed
    re-render as a follow-up and say so at review.
11. **Contract tests.**
    - New `tests/test_doc_review_step8_contract.sh` (static, modelled on
      `tests/test_docs_review_contract.sh`, each check shown able to fail
      against a mutant of the real text): the review round is referenced before
      the approval prompt; the Commit branch starts with the commit check, uses
      `--against-presented`, and its non-clean route commits nothing and returns
      to the top of Step 8; **the code-commit block is the guarded form** — the
      `guard` call precedes both `git add` and `git commit` inside one `if`, the
      block has an `else` branch that prints `DOC_GUARD_FAILED:` and exits with
      the guard's status, it comes after the plan consolidation and both
      attribution procedures, no unguarded `git commit -F -` remains in Step 8,
      and the failed route skips the plan commit and returns to the top of
      Step 8 (the test extracts the fenced block from the rendered `fast` golden
      and checks the command order and the `else` branch, so the helper test's
      command shape and the documented one cannot drift apart); the
      Need-more-changes branch references the feedback rules; `doc-review.md`
      opens a round with `begin` for full reviews **and** deletion outcomes and
      for nothing else, follows `PROCEDURE_COPY`, names `--caller audit`,
      `--evidence`, `--review-key`, `aitask_change_surface.sh list`, the claim
      check and its task-changed scope, `stamp-claims` (without a key) for
      `claims_pending`, `prior` and `stamp-deleted --review-key` for deletions,
      the three-part "the commit happened" rule, the `GUIDE:error` stop, both
      feedback paths, the four
      resolutions, "no finding may stay open"; the human approval prompt and
      its three options are unchanged.
    - Same test file, **Codex path**: in `.agents/skills/codex_tool_mapping.md`
      the review-commit block calls `guard` before `commit-approved` inside one
      `if` with the `DOC_GUARD_FAILED:` / `exit "$rc"` `else` branch; no
      unguarded `commit-approved` invocation remains in that file; the guard's
      arguments are tied to `artifacts` and `deleted`; `COMMIT:committed`,
      `COMMIT:duplicate` and `COMMIT_REFUSED:` handling is still there (needles
      taken from the text as it is before this task, so the check fails if the
      edit drops one); **the mapping's `DOC_GUARD_FAILED:` text points at
      `doc-review.md` `## Final commit guard`, names `RECEIPT_OUTCOME:`, and
      contains none of the phrases that would restate the outcome wrongly —
      `unclaimed`, `no commit exists`, `nothing was committed` — within that
      bullet's guard-failure sentence**; and `doc-review.md` item 5 carries the
      same block, the `applied`-only exception, and one stated action each for
      `none`, `prepared` and `unknown` (with `unknown` resolved through
      `commit-outcome` before the user is asked). Each check has a mutant control (the block with the guard
      line removed, with the `else` branch removed, with the two commands
      swapped, with `--receipt` removed). The `git commit` block is checked for
      both `--committing` and `--committing-deleted`. Run
      `tests/test_codex_entrypoints_tool_mapping.sh` and
      `tests/test_agent_instructions.sh` unchanged as regression.
    - `tests/test_gate_codex_approvals.sh` (it already drives a real receipt
      store and a real `commit-approved`): new cases for `commit-outcome` —
      `none` before any commit and with no state database (and the database is
      not created); `applied|<sha>` after `commit-approved`, with `<sha>` equal
      to the `COMMIT:committed` one; `prepared|<sha>` after the bound branch is
      moved back below that commit; `none` for another task id and `other` for
      another receipt id of a claimed occurrence; the store file is
      byte-identical before and after each call. Then **the round-6 scenario
      end to end with the real store and the real helper**: a review with one
      documentation page is approved, guarded and committed; the gate is not
      recorded (the interrupted session); the guide is edited; the documented
      guarded block runs again with the same receipt → `GUARD:clean|existing_commit`,
      `COMMIT:duplicate|<the original sha>`, `git rev-list --count` unchanged.
      Controls in the same fixture: a *new* receipt after the guide edit, with no
      commit yet → `GUARD:blocked`, nothing committed; and **a prepared receipt
      with the real store** — after a real `commit-approved`, the bound branch
      is moved back below its commit (`commit-outcome` now reads `prepared`),
      the guide is edited, the documented block runs with that receipt →
      `GUARD:blocked`, `commit-approved` not reached, and the branch tip is
      still the moved-back commit (a real `commit-approved` there would have
      rebuilt on the tip and advanced it, which is what the guard prevents).
    - `tests/test_docs_review_contract.sh`: new checks that the review skill
      reads `GUIDE_COPY` and takes its verdict on the snapshot (`--evidence`,
      `evidence=`), and that gate step 3b runs `begin` before the review, stamps
      the reported evidence with `--claims not-run` and computes no hash itself
      (`G_` checks fail against the pinned pre-change gate text like their
      siblings; `S_` checks fail against a mutant). The existing check that the
      skill "resolves the guide via the config resolver" stays true for calls
      without `--evidence`; adjust its needle only if the edit moves the text.
12. **Verify skills:** `./.aitask-scripts/aitask_skill_verify.sh`.
13. **Documentation**, written under `aitasks/metadata/doc_update_guide.md`
    (read it and `aidocs/framework/documentation_conventions.md` first):
    - `website/content/docs/skills/aitask-pick/_index.md` — the "Review cycle"
      bullet says what a user sees: documentation changed by the task is
      reviewed against the guide and its new claims checked before each approval
      prompt, and a doc edit after review is re-reviewed before commit.
    - `website/content/docs/skills/aitask-docs-review.md` — the review step as a
      caller.
    - `website/content/docs/skills/aitask-gate-docs-updated.md` — reviewed drafts
      are recorded so the review step does not repeat them.
    - New `aidocs/framework/doc_review_record.md` — contributor detail: record
      format, key inputs, page states, stamp refusals, the frozen-copy rule, why
      the gate stamps `claims=not-run`. Linked from the helper's header comment.
    - Run `python3 check_links.py --build` in `website/`.

### Post-phase (risk mitigations)

Runs after step 13 and before the Step 8 approval prompt.

1. [dogfood_review_round] Run the new procedure on this task's own change, with
   the real helper and the real guide: derive the task-owned documentation set
   (the three website pages and the new `aidocs/` page), run `## Review round`
   (`aitask-docs-review --caller audit --evidence 2369`, claim check included),
   apply the fixes, stamp, then run `## Commit check`. Then make one further
   edit to one of the pages and confirm `status` reads `changed`, `SET:stale`,
   and that `guard` exits 1 with `GUARD:blocked`; re-review it, and confirm
   `SET:current`, `SCOPE:same` and `GUARD:clean`. Record
   the helper output of each step verbatim in the plan's Final Implementation
   Notes, and show the per-page summary in the Step 8 prompt for this task.

## After the commit

- **Follow-up task** (with the user's confirmation): the shadow concern-picker
  preamble convenience (decision 2), anchored to 2258, carrying the instruction
  text from this task's body and the open question of how a forward is known to
  concern documentation.
- **Step 8d** creates the `after` mitigation below.
- **Step 9 (Post-Implementation)** — archival and push per the shared workflow.
  No branch merge (current-branch mode).

## Out of scope

- `DEFAULT_PREAMBLE` / `build_clipboard_payload` (follow-up task).
- `aitask-pickrem` / `aitask-pickweb` (no interactive review loop).
- Codex/OpenCode wrappers for `aitask-docs-review` (do not exist today; the
  procedure reads the skill by file path, which works from every agent tree).
- Any change to `commit-approved`, the question server, the store schema or an
  existing approval verb — only the read-only `commit-outcome` verb is added.
  OpenCode has no separate review-commit helper and uses the `git commit` form.
- A claim check inside the `docs_updated` gate itself. The gate stamps
  `claims=not-run` and Step 8 performs the check.
- Committing from an immutable review snapshot, and the window between the final
  guard and `git commit` — t2374 (which already depends on this task).

## Verification

- `bash tests/test_doc_review_record.sh`
- `bash tests/test_doc_review_step8_contract.sh`
- `bash tests/test_docs_review_contract.sh`
- `bash tests/test_skill_render_task_workflow.sh`
- `bash tests/test_skill_parity_runtime_vs_rendered.sh`
- `bash tests/test_helper_whitelist_coverage.sh`,
  `bash tests/test_touchpoint_count_contract.sh`
- `bash tests/test_codex_entrypoints_tool_mapping.sh`,
  `bash tests/test_agent_instructions.sh`, `bash tests/test_gate_codex_approvals.sh`
- `shellcheck .aitask-scripts/aitask_gate.sh`, and the other `aitask_gate.sh`
  suites that pin its verb list or usage text (`grep -ln "commit-approved\|approval-check" tests/`)
- `bash tests/test_workflow_end_banner_contract.sh`,
  `bash tests/test_inbox_surfacing_render.sh` (other Step 8/SKILL.md pins)
- `shellcheck .aitask-scripts/aitask_doc_review.sh`
- `./.aitask-scripts/aitask_skill_verify.sh`
- `python3 check_links.py --build` (in `website/`)
- Acceptance walk-through, recorded verbatim in the Final Implementation Notes:
  (a) typed feedback and (b) a forwarded-concern payload each drive
  `## Applying feedback to documentation` and a re-review; (c) an old
  `docs_updated` stamp followed by a doc edit reads `changed`; (d) a task with
  no doc paths presents an empty scope and commits; (e) a deletion-only change
  reaches `SET:current` through `stamp-deleted`; (f) an unparseable config
  blocks the commit path with `SET:unverifiable`; (g) a gate-reviewed page is
  finished by `stamp-claims` from `status` output alone; (h) a page deleted by
  an earlier commit resolves through `prior`; (i) a tracked page edited between
  the early check and the final guard produces no code commit and returns to the
  approval prompt.

## Risk

### Code-health risk: medium
- Step 8 text is rendered into every profile and into the committed remote variants, so a wording mistake changes the commit path of every task · severity: medium · → mitigation: manual_verify_doc_review_loop
- The review round adds work on every Step 8 pass of a doc-changing task, and the doc set and the claim-basis lists depend on agent judgement · severity: medium · → mitigation: inline post-phase dogfood_review_round
- The committed `task-workflow-remote-` variants are already dirty from another session; a re-render could sweep in foreign changes · severity: medium · → mitigation: none (handled by the decision rule in implementation step 10)
- The code-commit command of every task now runs behind `guard`; a helper defect (a crash, a wrong exit status) would block commits for tasks with no documentation at all · severity: medium · → mitigation: none (pinned by the no-documentation and unrelated-edit positive controls in implementation step 3; a blocked guard is recoverable — nothing is committed or staged)
- A new verb is added to the attended-Codex approval code (`approval.py`, `aitask_gate.sh`), which guards real commits; it is read-only, but a mistake in how it matches a receipt could report `applied` for the wrong one and skip the guard · severity: medium · → mitigation: none (it reuses `commit()`'s own match — project, consumer key, receipt id, ancestor test — and the real-store cases in `tests/test_gate_codex_approvals.sh` pin `none` for another task and `other` for another receipt)
- The helper now carries eight page states, eleven verbs, snapshots, issued keys and a presented scope; a state the tests do not pin could report a stale set as current · severity: medium · → mitigation: none (the state table is the test matrix of implementation step 3)

### Goal-achievement risk: medium
- The enforcement is prose the agent follows; the helper proves hashes match, but only static contract tests check that Step 8 calls it · severity: medium · → mitigation: inline post-phase dogfood_review_round; manual_verify_doc_review_loop
- A claim whose implementation file the agent did not list as a basis is not re-flagged when that file changes · severity: medium · → mitigation: none (the feedback rules require re-checking task-changed claims about changed behaviour; stated as a residual limit in `aidocs/framework/doc_review_record.md`)
- A page edited across many rounds can exhaust the fresh-reader budget and end as `reader=not-run(cap)`; visible in the prompt · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: dogfood_review_round | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: judgement-dependent doc set; prose-only enforcement | desc: Run the new review round and commit check with the real helper on this task's own documentation pages and record the transcript in the plan
- timing: after | name: manual_verify_doc_review_loop | type: manual_verification | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: prose-only enforcement; Step 8 wording on the commit path | desc: In a fresh session on a real docs task, forward a shadow concern and type feedback, then check the re-review and the refusal to commit a stale documentation revision
