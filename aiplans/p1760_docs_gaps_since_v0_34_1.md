---
Task: t1760_docs_gaps_since_v0_34_1.md
Branch: main
Base branch: main
Output branch: main
---

# t1760 — Document the `ait upgrade` version-check timeout knob

## Context

`/aitask-docs-gap` found one documentation gap in the `v0.34.1..HEAD` window
(the two other gaps it found are owned by t1657_6 / t1705_9 / t1705_10 and are
explicitly out of scope for this task).

t1244 made the version check reach the network under a **hard time bound**: the
`git ls-remote` fallback used when the GitHub REST API is rate-limited now runs
as a watchdogged background job that kills its whole process tree on expiry,
instead of hanging forever on a remote that blackholes the connection. The bound
is 10 seconds and is overridable through `AIT_GIT_LSREMOTE_TIMEOUT`.

The website's `## ait upgrade` section
(`website/content/docs/commands/setup-install.md:58`) is currently silent about
the version check touching the network at all — no fallback, no bound, no knob.
That is an inconsistency with the sibling git escape-hatch knob
`AIT_GIT_SKIP_STATE_CHECK`, which is documented inline in prose at
`website/content/docs/commands/sync.md:252`. This task closes that
inconsistency; it introduces no new documentation pattern.

## Ground truth (read from the landed code, not from the task description)

- `.aitask-scripts/lib/github_release.sh:45` — `_AIT_GIT_LSREMOTE_TIMEOUT_DEFAULT=10`.
- `.aitask-scripts/lib/github_release.sh:161-166` — `AIT_GIT_LSREMOTE_TIMEOUT`
  is read, then **normalized**: any value that is not a positive integer (empty,
  `0`, negative, non-numeric) falls back to the 10s default. Unit: whole seconds.
- `.aitask-scripts/lib/github_release.sh:148-207` — on expiry the job's process
  tree is killed and the function prints **nothing** and returns 0, so the caller
  sees "no version found", never a hang.
- `install.sh:236-278` — `_install_ls_remote_tags()` is the installer's private
  mirror; same 10s default, same variable, same normalization.

Which paths actually honor the knob:

| path | uses the bounded `git ls-remote`? | what the user sees on expiry |
|---|---|---|
| `ait upgrade latest` (`aitask_upgrade.sh:51-79`) | yes — **only** on the rate-limited branch (rc 2); a plain network failure dies before reaching it | dies with the rate-limit message + its `GH_TOKEN` hint, rather than hanging |
| `ait setup` version check (`aitask_setup.sh:2466`) | yes, via `github_resolve_latest_version` (rc 2 or 4) | silent — no "update available" notice (documented silent-degrade contract) |
| `curl \| bash` installer with no `--version` (`install.sh:357`) | yes — git tags are tried *first*, no REST call | **not silent**: after `[ait] Resolving latest aitasks release...` (`install.sh:356`) it moves on to `[ait] Fetching latest release via the GitHub API...` (`install.sh:380`), and if that REST fallback also resolves nothing it exits 1 with `[ait] Error: Could not find release tarball.` + the releases link (`install.sh:385`) |
| `ait` dispatcher's once-a-day update check (`ait:172`) | **no** — a direct `curl --max-time 5`, no git fallback | unaffected by the knob |

Two things the prose must not get wrong:

- The dispatcher row. The page's existing "**Automatic update check:**"
  paragraph describes exactly that once-a-day check, so a reader could easily
  assume the new knob applies to it. It does not.
- The three honoring paths do **not** share one outcome. Only `ait setup` is
  silent. `ait upgrade` dies with the rate-limit message it was already
  recovering from, and the installer visibly announces its REST fallback and can
  end in a terminal error. "Degrades quietly" is true of exactly one of them, so
  the outcomes must be stated per path.

## Approach

Single file: `website/content/docs/commands/setup-install.md`. Three edits, all
current-state-only prose (`aidocs/framework/documentation_conventions.md`).

### 1. Extend "How it works" step 1 (`setup-install.md:70`)

Point the numbered step at the new prose instead of leaving "queries GitHub API"
as the whole story:

```markdown
1. Resolves the target version (queries the GitHub API for `latest`, with a
   rate-limit-free `git ls-remote` fallback — see **Bounded version lookup**
   below — or validates the provided version number)
```

### 2. Add a "Bounded version lookup" block after the "How it works" list

Inserted between the numbered list (ends `setup-install.md:75`) and
"**Automatic update check:**" (`setup-install.md:77`). Bold-lead paragraph, not
a `###` heading — that matches the local style inside `## ait upgrade`.

```markdown
**Bounded version lookup:**

Resolving `latest` reaches the network. The GitHub REST API is tried first; when
it answers with a rate-limit error, the version is resolved from `git ls-remote`
instead, which is exempt from the REST quota. That git lookup is hard-bounded —
**10 seconds** by default — because a remote that blackholes the connection
instead of refusing it would otherwise stall the command indefinitely. Override
the bound with `AIT_GIT_LSREMOTE_TIMEOUT`, in whole seconds:

```bash
AIT_GIT_LSREMOTE_TIMEOUT=30 ait upgrade latest
```

An empty, zero, negative, or non-numeric value falls back to the 10-second
default. When the bound trips, the lookup yields no version rather than hanging,
and `ait upgrade` stops with the rate-limit message it was recovering from,
including its `GH_TOKEN` hint.

Two other paths use the same bounded lookup and honor the same variable, and
they report an expiry differently:

- The version check at the end of [`ait setup`](#ait-setup) is silent — it
  simply prints no "update available" notice.
- The `curl | bash` installer resolves the latest release from git tags before
  it touches the REST API, so an expiry is visible: after
  `Resolving latest aitasks release...` it announces
  `Fetching latest release via the GitHub API...` and continues there. If that
  fallback cannot resolve a release either, the installer stops with
  `Error: Could not find release tarball.` and a link to the releases page.
```

### 3. Scope the "Automatic update check" paragraph (`setup-install.md:79`)

Add one parenthetical so the daily dispatcher check is not read as covered by
the knob:

```markdown
The `ait` dispatcher checks for new versions once per day (at most) — a direct
API call with its own short timeout, independent of the bounded git lookup
above. When a newer version is available, …
```

(The rest of that paragraph is unchanged.)

### Deliberately not done

- **No cross-reference from `website/content/docs/installation/known-issues.md`.**
  The task said "consider" it. That page is scoped to *per-code-agent* workflow
  caveats ("This page tracks current workflow issues by code agent", grouped
  under `## Claude Code` / `## Codex CLI` / `## OpenCode`); a network-timeout
  knob for `ait upgrade` has no home in that taxonomy and adding one would
  dilute it.
- **No new "environment variables" reference page.** The house treatment for
  these knobs is inline prose at the point of use (`AIT_GIT_SKIP_STATE_CHECK`
  in `sync.md`, `AIT_GATES_REFERENCE` in `gates.md`); a central table is a
  different, larger decision and is not this task's gap.
- **No code changes.** `AIT_GIT_LSREMOTE_TIMEOUT` and its normalization already
  ship; this task only documents them.

## Files

- `website/content/docs/commands/setup-install.md` — the only file modified.

## Verification

1. **Facts match the source** — re-grep the three claims the prose makes, so the
   numbers are not copied from the task description:
   ```bash
   grep -n '_AIT_GIT_LSREMOTE_TIMEOUT_DEFAULT=' .aitask-scripts/lib/github_release.sh
   grep -n 'AIT_GIT_LSREMOTE_TIMEOUT' install.sh
   grep -rn 'AIT_GIT_LSREMOTE_TIMEOUT\|max-time 5' ait
   ```
   Expect: default `10` in the library; the same default mirrored in
   `install.sh`; and **no** hit for the variable in the `ait` dispatcher (which
   is what makes the "independent of the bounded git lookup" claim true).
2. **The quoted installer messages exist verbatim** — the prose promises a
   specific on-screen sequence, and nothing else in this plan checks it:
   ```bash
   grep -n 'Resolving latest aitasks release\|Fetching latest release via the GitHub API\|Could not find release tarball' install.sh
   ```
   Expect three hits, in that order (currently `install.sh:356`, `:380`, `:385`),
   with the third reached via `die` (exit 1). Also re-read
   `install.sh:352-386` to confirm an empty `version` still falls *through* to
   the REST discovery rather than exiting early — that control flow is the whole
   claim of the installer bullet.
3. **Link check** (mandatory after any `website/content/` edit):
   ```bash
   cd website && python3 check_links.py --build
   ```
   Must exit 0. It is the only thing that validates the new `#ait-setup`
   in-page anchor — Hugo builds a dead fragment green.
4. **Render check** — build and read the section back:
   ```bash
   cd website && hugo build --gc --minify
   ```
   Confirm the fenced `bash` block inside the bold-lead paragraph renders as a
   code block and the surrounding prose is not swallowed by it.

## Risk

### Code-health risk: low
- None identified. Documentation-only change to a single page; no shell, Python,
  or skill surface is touched, and nothing depends on this page's content.

### Goal-achievement risk: medium
- The prose could overstate the knob's reach — in particular by implying it
  bounds the `ait` dispatcher's once-a-day update check, which is a plain
  `curl --max-time 5` with no git fallback. · severity: low · → mitigation:
  covered by plan edit 3 (the explicit "independent of the bounded git lookup"
  parenthetical) and by Verification step 1, which asserts the dispatcher
  contains no reference to the variable.
- The task's explicit requirement is to say *what a user sees* when the bound
  trips, and the three honoring paths do not share one outcome — flattening them
  into a single "degrades quietly" claim would be wrong for the installer, which
  announces its REST fallback and can exit 1. Neither the link check nor the
  Hugo build can catch a semantic mismatch like that. · severity: medium ·
  → mitigation: covered by plan edit 2, which states the outcome per path, and
  by Verification step 2, which pins the three quoted installer messages and the
  fall-through control flow to `install.sh`.

No mitigations are proposed as spawned tasks or extra plan phases. Both
identified risks are accuracy risks about this plan's own prose, and each is
already discharged by a specific edit plus a specific verification step above; a
spawned task or an extra phase would only restate work the plan already does.
The goal-achievement level is **medium** rather than low because the per-path
outcome error was real — it was present in the first draft of this plan and
caught in review, not hypothetical.

## Post-implementation

Follow **Step 9 (Post-Implementation)** of the task workflow for commit,
cleanup, and archival. Commit type: `documentation: … (t1760)`.

## Implementation notes (as landed)

All three edits landed in `website/content/docs/commands/setup-install.md` as
planned; no deviations.

Verification results:

1. **Facts match the source** — `_AIT_GIT_LSREMOTE_TIMEOUT_DEFAULT=10`
   (`.aitask-scripts/lib/github_release.sh:45`); the same `10` mirrored at
   `install.sh:243`; and the `ait` dispatcher matched only on `--max-time 5`
   (`ait:172`) with **no** hit for `AIT_GIT_LSREMOTE_TIMEOUT` — which is what
   makes the "independent of the bounded git lookup" parenthetical true.
2. **Installer messages exist verbatim, in order** — `install.sh:356`, `:380`,
   `:385`. Re-read of `install.sh:352-386` confirms the control flow the prose
   claims: on an expiry `version` is empty, so the `if [[ -n "$version" ]]` CDN
   block is skipped entirely and execution falls **through** to
   `info "Fetching latest release via the GitHub API..."`, then `die`s (exit 1)
   only if `github_api_tarball_url` also yields nothing.
3. **Link check** — `python3 check_links.py --build`: `SWEEP: PASSED`,
   29218 resolved, **0 broken**. The new in-page `#ait-setup` target is present
   in the rendered HTML (`id=ait-setup`).
4. **Render check** — `hugo build --gc --minify` clean. The fenced block renders
   as `<div class=highlight><pre><code class=language-bash>` with the following
   paragraph intact, and `curl | bash` inside the list item renders as
   `<code>curl | bash</code>` rather than being read as table syntax.

## Post-Review Changes

### Change Request 1 (2026-09-09 12:31)

- **Requested by user:** Verify two review concerns raised against files that
  appear in the working tree but are outside t1760's scope
  (`website/check_link_relevance.py`, `tests/test_check_link_relevance.py`),
  both flagged `Disposition: follow-up` and explicitly not a reason to block
  t1760.
- **Changes made:** No code change. Both concerns were **verified as valid** and
  are recorded below and in the `Upstream defects identified` bullet, which is
  where Step 8b reads them. Neither touches
  `website/content/docs/commands/setup-install.md`, so t1760's diff is unchanged
  and its four verification steps still stand as recorded above.
- **Files affected:** none (this plan file only).

**Concern 1 — `check_link_relevance.py --report` bypasses its own self-controls.
CONFIRMED.**
`main()` returns 0 at `website/check_link_relevance.py:492` (`if args.report:`)
before `evaluate_controls(result)` at `:518`. Measured: `python3
check_link_relevance.py --report` exits **0** and prints **zero** `control` lines.
That contradicts the contract stated at `website/README.md:208-209` — "exits
non-zero only when one of its own self-controls fails … it prints every control
on every run". So a collapsed extractor or resolver yields an empty
machine-readable report that reads as success. (Note the flag's own `--help`
text says "print records only, no summary or controls", so the two documented
statements also disagree with each other — whichever is intended, one of them is
currently wrong.)

**Concern 2 — `unittest.main()` guard precedes 15 later test methods. CONFIRMED.**
`if __name__ == "__main__": unittest.main()` sits at
`tests/test_check_link_relevance.py:625-626`, with 15 further `def test_*`
methods defined at `:643-792`. Measured: `python3
tests/test_check_link_relevance.py` reports **33 tests, OK**, while `python3 -m
unittest discover -s tests -p test_check_link_relevance.py` reports **48 tests,
OK**. Direct execution therefore gives a false partial green; the repository's
documented entry points (the aggregate runner / pytest) are unaffected.

**Routing.** Both files were created by **t1759**, which has since **committed
and archived** them — commit `a2a1dee72` ("chore: Report internal links whose
target page is off-subject (t1759)"); the task now lives at
`aitasks/archived/t1759_sweep_dead_end_relrefs.md`. **Both defects landed
unfixed** and were re-confirmed against the committed tree: `if args.report:
return 0` still sits at `website/check_link_relevance.py:492` ahead of
`evaluate_controls()` at `:518`, and the `unittest.main()` guard still sits at
`tests/test_check_link_relevance.py:625` ahead of 15 later test methods. t1759
can therefore no longer receive them.

Coverage search over active tasks found **no existing owner**:

- **t1768** (`Implementing`) is t1759's risk-mitigation follow-up and is scoped
  to the relevance *heuristic's precision* — whether the rule is good enough to
  fold into `check_links.py` as a non-blocking warning, and whether coverage
  should widen past backtick-quoted link text. It touches neither the
  report-mode control bypass nor the test entry point.
- **t1159_7** (`Ready`) only *cites* the guard-placement class as precedent
  (t1518 moved a stranded `unittest.main()` in
  `tests/test_minimonitor_concern_action.py`); it owns a different file.
- **t1687** merely references the new script as a tool to run.

Both defects were therefore routed to a **dedicated follow-up task** — see
Post-Review Changes / Change Request 2. They remain out of t1760's scope:
this task must not stage, modify, or commit either file.

### Change Request 2 (2026-09-09 16:35)

- **Requested by user:** The routing record in Change Request 1 had gone stale —
  t1759 has committed and archived, so it can no longer receive the two findings.
  Correct the record, and first check whether any other task already covers all
  or part of them before routing. Three further findings were raised in the same
  pass, all `Disposition: follow-up`.
- **Changes made:** No change to t1760's own diff. The routing paragraph in
  Change Request 1 was rewritten against the current tree; the findings were
  routed as described below.
- **Files affected:** this plan file; `aitasks/t1770_*.md` (new);
  `aitasks/t1725/t1725_3_*.md` (note appended).

**Coverage search (before routing anything).** `t1768` — t1759's own
risk-mitigation follow-up, `Implementing` — is scoped to the relevance
*heuristic's precision*, not to the checker's self-controls or its test entry
point, so it covers neither finding. `t1159_7` cites the guard-placement class
as precedent (t1518, `tests/test_minimonitor_concern_action.py`) but owns a
different file. `t1687` only references the script as a tool. **No active task
covered any part of the two findings**, so a dedicated task was warranted.

**Routed:**

| finding | verdict | routed to |
|---|---|---|
| `--report` returns before `evaluate_controls()` (`check_link_relevance.py:492` vs `:518`) | **CONFIRMED** — rc 0, zero control lines; contradicts `website/README.md:208-209` | **t1770** (new) |
| `unittest.main()` guard at `tests/test_check_link_relevance.py:625` precedes 15 tests | **CONFIRMED** — direct run 33 tests vs discovery 48 | **t1770** (new) |
| `_load_incoming()` uses `HEAD..@{u}` (`aitask_sync.sh:1298`) where endpoints diverge | **CONFIRMED** — violates `aidocs/framework/shell_conventions.md:216-217` | **note to t1725_3** (its owner, active) |
| t1725_3 fails `shellcheck` on unquoted `@{u}` / unused vars | **DID NOT REPRODUCE** — `shellcheck --exclude=SC1091 .aitask-scripts/aitask_sync.sh` exits 0, all `@{u}` quoted | reported in the same note, hedged as moment-relative |

`t1770` (`bug`, medium/low) carries both landed t1759 defects with their measured
evidence, the README-vs-`--help` contract disagreement, the t1518 precedent, and
t1759's inherited "the report never gates" constraint. The note to t1725_3
returned `NOTE_APPENDED:` plus `LIVE_PANE:` — durable and delivered to the live
holder.

**t1760's own diff is unchanged by any of this** and its four verification steps
above still stand. None of these findings touch
`website/content/docs/commands/setup-install.md`.

### Change Request 3 (2026-09-09 16:50)

- **Requested by user:** Verify three further findings, all raised against the
  concurrent task **t1725_3** (open, `Implementing`) and all
  `Disposition: follow-up`.
- **Changes made:** No change to t1760's own diff. All three verified as valid
  and routed to t1725_3 — the task that owns the code — as a second durable
  note (`NOTE_APPENDED:` + `LIVE_PANE:`).
- **Files affected:** this plan file; `aitasks/t1725/t1725_3_*.md` (second note
  appended).

| finding | verdict | evidence |
|---|---|---|
| A legacy lock's `-` PID sentinel breaks the `DEFERRED_FILE` parser | **CONFIRMED** | `aitask_lock.sh:595` (`lpid="${lpid:--}"`) → `LOCK_PID` → `_protect()` (`:422`) → `DEFERRED_FILE` field 8; `_PID_RE = ^[0-9]*$` at `lib/sync_action_runner.py:111`, applied `:186`, does not match `-` (checked directly), so `parse_record` returns `None` |
| `_load_incoming()` still two-dot, and untested for divergence | **CONFIRMED, for the `git diff` site only** | `aitask_sync.sh:1305`, present in committed `152254289`; `tests/test_sync_deferral_and_quarantine.sh` has no local-only-divergence case — the only mention of `_load_incoming` there is a comment at `:718`. **The `rev-list --count` site at `:1419` is correct as written — see the retraction below** |
| `--expect-path` is unusable with a multi-id `--commit-for-task` | **CONFIRMED** | the guard at `aitask_sync.sh:1149-1166` compares each **group's** `paths` against the **single global** `EXPECT_PATHS`, so each group sees the other's paths as `-<path>`, `delta` is non-empty, and `_protect_group_paths "commit_scope_changed"` abandons it — symmetrically, so neither commits |

**Why a note and not a task.** All three are defects in the implementation
**t1725_3 owns**, and that task was **active (`Implementing`)** when they were
raised and routed — which is the durable fact the routing turns on, not whether
a commit had happened yet. It had in fact already made its first code commit
(`152254289`, "bug: Make sync deferrals per-file and the rebase gate tree-state
aware (t1725_3)") shortly before the second note was appended; that does not
change the routing, because an owning task stays the right recipient for as long
as it is open, and **its corrective commits are still pending**. Per CLAUDE.md's
note-vs-task rule, context about work that already exists goes to that work;
spawning tasks here would duplicate whatever its owner does before it closes.

Contrast the two t1759 findings (Change Request 2), which needed a dedicated
task (**t1770**) precisely because their owner was **archived** — no open task
could receive them. That is the discriminating condition: *is there still an
open task that owns this code?* — not *has the code been committed?*

All three defects are present in **committed** code, so they do not depend on
anyone's working tree: `HEAD..@{u}` at `aitask_sync.sh:1305` inside
commit `152254289`; `lpid="${lpid:--}"` at `aitask_lock.sh:596`; and
`_PID_RE = re.compile(r"^[0-9]*$")` at `lib/sync_action_runner.py:111`, applied
at `:186`.

**Line numbers in the delivered notes are tree-relative and have moved.** The
first note cited the lock sentinel at `aitask_lock.sh:595`, read from a dirty
working tree; in committed `HEAD` it is `:596`. The identifiers
(`lpid`, `_PID_RE`, `_load_incoming`) are the stable handles.

**Known blemish in the delivered note:** the first bullet contains a stray
character — "`:-` does not替 a non-empty `-`" (intended: "does not replace").
The surrounding evidence is unaffected and the claim is unambiguous; notes are
append-only, so it was not worth a third note to the recipient purely to fix a
typo.

**t1760's own diff remains unchanged** across all three review rounds. None of
the eight findings raised in review touched
`website/content/docs/commands/setup-install.md`.

### Change Request 4 (2026-09-09 17:26) — retraction

- **Requested by user:** A blocking correction. The plan and the second note to
  t1725_3 both claimed the two-dot defect covered `aitask_sync.sh:1419`'s
  `rev-list --count` as well. **Only the `git diff` site at `:1305` is
  defective.** Correct the plan and append a clarification note, because notes
  are append-only and leaving the advice standing risks causing a new bug in
  someone else's code.
- **Changes made:** No change to t1760's own diff. The claim was retracted
  everywhere it appeared: both restatements in Change Request 3 above, and a
  third note to t1725_3 (`NOTE_APPENDED:` + `LIVE_PANE:`).
- **Files affected:** this plan file; `aitasks/t1725/t1725_3_*.md` (third note).

**The retraction, and why the original claim was wrong.** `..` does not mean the
same thing to the two commands:

- `git diff A..B` compares the two **endpoints**, so it also reports paths only
  the local side touched — the real defect at `:1305`.
- `git rev-list A..B` means "commits reachable from B but not A" — exactly the
  remote-ahead count `:1419` wants. Three dots there is the **symmetric
  difference**, which would additionally count local-only commits and turn
  correct code into a bug.

Measured on a synthetic divergent history (one local-only commit, one
remote-only commit):

| command | result |
|---|---|
| `git diff --name-only HEAD..upstream` | `local_only.txt`, `remote_only.txt` |
| `git diff --name-only HEAD...upstream` | `remote_only.txt` |
| `git rev-list --count HEAD..upstream` | `1` — correct remote-ahead count |
| `git rev-list --count HEAD...upstream` | `2` — counts both sides |

`aidocs/framework/shell_conventions.md:216-217` states the three-dot rule for
`git diff`; reading it as a blanket rule for every two-dot range is the mistake
that produced the bad advice. **A convention keyed to one command must not be
generalized to another whose range operator has different semantics.**

**Process note.** The first note hedged this correctly ("a count of commits is a
different question from a set of changed paths — worth a look, not necessarily
the same fix"); the second note dropped the hedge and asserted the site was
wrong "too". Escalating a hedged observation into a flat claim on restatement is
what made this actionable-and-wrong rather than merely speculative.

### Change Request 5 (2026-09-09 17:34) — no action required

- **Requested by user:** Verify three findings, all `Disposition: follow-up`,
  all against active t1725_3.
- **Changes made:** **None.** All three are re-confirmations of findings already
  delivered to t1725_3, carrying no new information and needing no new routing:
  the `-` PID sentinel vs `_PID_RE` (note 2), `_load_incoming()`'s two-dot
  `git diff` (notes 1–3), and the per-group `--expect-path` comparison against
  the global set (note 2). Re-sending them would only add noise to a live
  recipient that already holds them.
- **Files affected:** this plan file only.

Of note, the user's independent divergent-history probe reproduced the same
result as the probe recorded in Change Request 4 (`HEAD..upstream` → local-only
+ remote-only; `HEAD...upstream` → remote-only) and confirms the corrected
advice now targets only `_load_incoming()`. The retraction therefore holds under
independent verification, not just my own.

## Final Implementation Notes

- **Actual work done:** Exactly the planned three edits to
  `website/content/docs/commands/setup-install.md` (+17/−2, one file): the
  "How it works" step 1 now names the `git ls-remote` fallback and points at the
  new block; a **Bounded version lookup** block documents the 10-second default,
  the `AIT_GIT_LSREMOTE_TIMEOUT` override and its normalization, and the expiry
  outcome **per path**; and the "Automatic update check" paragraph is scoped so
  the dispatcher's daily check is not read as covered by the knob. No code
  changed — the knob already shipped with t1244.
- **Deviations from plan:** None. The plan's own first draft was corrected
  before approval (see the per-path outcome fix recorded in the Risk section).
- **Issues encountered:** None in the implementation. The review loop ran five
  rounds; all eleven findings concerned other tasks, and t1760's diff was
  unchanged from the first round onward. The one substantive problem was mine:
  advice sent to t1725_3 that wrongly implicated a correct `rev-list --count`
  site, retracted in Change Request 4 with a measured probe and a third note.
- **Key decisions:**
  - Outcomes are documented **per path** rather than as one "degrades quietly"
    claim, because the three honoring paths genuinely differ — only `ait setup`
    is silent.
  - No cross-reference from `installation/known-issues.md`: that page is a
    per-code-agent taxonomy and a network knob has no home in it.
  - No central "environment variables" page: the house style is inline prose at
    the point of use (`AIT_GIT_SKIP_STATE_CHECK` in `sync.md`,
    `AIT_GATES_REFERENCE` in `gates.md`).
- **Upstream defects identified:**
  - `website/check_link_relevance.py:492 — --report returns 0 before evaluate_controls() at :518, so report mode neither evaluates nor prints any self-control, contradicting website/README.md:208-209` (routed to **t1770**)
  - `tests/test_check_link_relevance.py:625 — unittest.main() guard precedes 15 later test methods, so direct execution runs 33 of 48 tests and reports a false green` (routed to **t1770**)
  - `.aitask-scripts/aitask_lock.sh:596 — lpid="${lpid:--}" emits a literal "-" for a legacy lock, which lib/sync_action_runner.py:111 (_PID_RE = ^[0-9]*$, applied :186) rejects, turning a valid unknown_liveness deferral into a malformed DEFERRED_FILE` (routed by note to **t1725_3**, its active owner)
  - `.aitask-scripts/aitask_sync.sh:1305 — _load_incoming() uses git diff HEAD..@{u}, comparing endpoints where they can diverge, so local-only paths count as incoming (shell_conventions.md:216-217)` (routed by note to **t1725_3**)
  - `.aitask-scripts/aitask_sync.sh:1149-1166 — the --expect-path guard compares each task group against the single global EXPECT_PATHS set, so a multi-id --commit-for-task rejects every group and commits nothing` (routed by note to **t1725_3**)

  All five are already routed to a named owner; none needs a further follow-up
  offer at Step 8b.
