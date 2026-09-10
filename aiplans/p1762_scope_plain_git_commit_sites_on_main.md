---
Task: t1762_scope_plain_git_commit_sites_on_main.md
Base branch: main
Output branch: main
---

# t1762 — Scope the plain `git commit` sites on `main`

## Context

t1748 closed the unscoped-commit defect at the **instruction layer** for the
task-data branch: 36 sites where a procedure told an agent to run
`./ait git commit` with no `--` pathspec, taking the whole shared
`.aitask-data` index. Its own Final Implementation Notes recorded what it
deliberately left open — the identical shape on **`main`**, through plain `git`.

`main` is shared by every session on this machine exactly as `.aitask-data` is:
~19 sessions work the same checkout. So

```bash
git add <paths>
git commit -m "bug: ... (t1762)"
```

commits the **entire main-branch index**, and whatever a concurrent session had
staged at that instant lands in a commit whose message names unrelated work.

**Scope (user decision): narrowly scoped hardening.** There is evidence of unsafe
instruction shapes but no recorded main-branch sweep incident, so this task fixes
the direct defect and nothing more — pathspec the commits, delete the staging of
tracked files that the pathspec makes unnecessary, add a small regression scan
for newly introduced bare `git commit` instructions, and use one simple
documented exception for the two sites that cannot be path-scoped. A universal
`git add` manifest, multiple staging-marker modes, and a broad exception taxonomy
were considered and are deliberately **out**; the residual edge cases are
recorded as limitations or follow-ups below rather than built into an enforcement
framework.

## Measured inventory

Line numbers are as of this plan and **must be re-derived before editing** —
t1748's went stale within its own session. Re-derive and diff old-vs-new at the
same instant rather than trusting these absolutes:

```bash
git ls-files -- '*.md' '*.j2' \
  | grep -E '^(\.claude/skills/|\.agents/skills/|\.opencode/(skills|commands)/|aidocs/|\.aitask-scripts/skill_templates/)|^(CLAUDE|AGENTS)\.md$|^\.codex/instructions\.md$|^\.opencode/instructions\.md$|^seed/aitasks_agent_instructions\.seed\.md$' \
  | grep -v '/[^/]*-/' | grep -v '^tests/golden/' \
  | xargs grep -Hn 'git commit' \
  | grep -vE '(\./)?ait[[:space:]]+git[[:space:]]+commit|task_git[[:space:]]+commit|aitask_task_commit|git commit-tree'
```

24 authoring sites in 13 files. The `.agents/` and `.opencode/` per-skill trees
are thin "Source of Truth" pointer wrappers and carry **zero** commands (same
finding as t1748); 56 rendered copies and the `tests/golden/**` fixtures follow
from the sources. `CLAUDE.md`, `AGENTS.md`, the two instruction mirrors and the
seed carry only the `./ait git` snippet and **no** plain `git commit` — verified,
so this task needs none of t1748's four-mirror byte-parity work.

| Class | Sites | Cure |
|---|---|---|
| **Bounded, named paths** — the `add` names 1-5 fixed files | A1 `aitask-add-model:151-154`, A2 `:159-160`, A3 `aitask-refresh-code-models:155-156`, A7 `aitask-reviewguide-classify:134-135`, A9 `aitask-changelog:319-320`, A11 `aitask-audit-wrappers:148-153`, A19 `aitask-pickweb.j2:337-338`, A20 `model_reference_locations.md:206-207`, A21 `:227-228`, A23 `homebrew_maintainer_setup.md:204-205`, A24 `aur_maintainer_setup.md:278-279` | repeat the same path list after `--` |
| **Directory pathspec on the `add`** — strictly worse than an unscoped shell site, exactly as t1748 found | A4 `aitask-reviewguide-import:234-235`, A5 `aitask-reviewguide-merge:140-141`, A6 `:156-157`, A8 `aitask-reviewguide-classify:200-201` (all `git add aireviewguides/`); **A10 `aitask-audit-wrappers:75-76`** (`git add .agents/skills/ .opencode/skills/ .opencode/commands/`) | name the files the procedure just wrote — for A4-A8 the guide file plus the three fixed `aireviewguides/*.txt`; for A10 the helper's own `WROTE:` lines |
| **Agent-substituted placeholder** | A14 `task-workflow/SKILL.md:729-730`, A15 `contributor-attribution.md:64`, A16 `aitask-wrap.j2:265,269`, A17 `aitask-pickrem.j2:374,378`, A12 `aitask-learn-skill/generate.md:122-123` | repeat the **same placeholder** after `--` |
| **Runtime-generated list** — the one real case | A22 `issue_type_vocabulary_duplication.md:157` — "the other 31 files", produced by the procedure's own grep | array + non-empty `if` branch |
| **Cannot take a pathspec** | A13 `aitask-web-merge:92` (concluding a `git merge`), A18 `aitask-pickweb.j2:288,292` (`git add -A` in an isolated single-session cloud sandbox) | one documented exception marker |
| **Prose that blesses the unscoped form** | P1 `website/content/docs/installation/updating-model-lists.md:69` | reword; then `check_links.py --build` |

A14 is the highest-impact single site in the repo: it is the code commit **every**
task runs at Step 8.

## Implementation

### Pre-phase (risk mitigations)

**`scanner_red_proof`** — copied from t1748, because the same failure mode
applies: a scan that matches nothing passes forever, and a red proof run with a
*throwaway* matcher certifies nothing about the one that ships.

Phase 3 is therefore **built before Phases 0-2 edit anything**, and the red
window lives entirely in the uncommitted working tree:

1. Write the scan complete — matcher, exception-marker parser, fixtures,
   controls — and get the *fixture* controls green. Do not commit.
2. Run `bash tests/test_no_unscoped_task_commit.sh` against the untouched tree.
   The new seam **must fail**, naming the measured 24-site inventory. Save the
   output to the scratchpad and diff it against the table. Extra hits mean the
   matcher over-reaches; missing hits mean it under-reaches. Fix the matcher,
   never the expectation.
3. Only then run Phases 0-2. Re-run: green.
4. Commit scan and conversions **together**, one commit. No commit ever contains
   a red tripwire, and no commit contains a guard never observed failing.

Replayable evidence for the Final Implementation Notes — the **shipping** file
against the **pre-conversion** tree, at a literal SHA (`HEAD~1` stops meaning
"before this change" as soon as another session lands one):

```bash
wt="$SCRATCH/t1762-preproof"
git worktree add --detach "$wt" <pre-conversion SHA>
cp tests/test_no_unscoped_task_commit.sh "$wt/tests/"
( cd "$wt" && bash tests/test_no_unscoped_task_commit.sh )   # expect FAIL, naming the inventory
git worktree remove --force "$wt"
```

`git worktree`, **never `git stash`** — this working tree is shared.

### Phase 0 — verify what the plan asserts

In a throwaway scratch repo (`$SCRATCH`, never this one):

1. **A merge commit refuses a pathspec.** `git commit -m x -- <path>` mid-merge →
   expect `fatal: cannot do a partial commit during a merge`. This is what makes
   A13 an exception rather than an oversight; if a pathspec turns out to be legal
   there, A13 moves into the bounded class and the exception is dropped.
2. **A foreign staged file is not swept** by `git commit -m x -- <ours>`, and is
   still staged afterwards — `foreign_staged_control`, established up front so
   the conversions are known to be worth making.
3. **`git commit`'s first output line carries the new short SHA**
   (`[<branch> <sha>] <subject>`). The `--stat` step below reads it. If the
   format is not reliably parseable, fall back to `git rev-parse HEAD`
   immediately after the commit and say in-line that the window is small, not
   zero.

Item 3 matters because ~19 sessions share this worktree: `git show --stat HEAD`
can describe *another* session's commit if it lands in between, so the
verification step would silently validate the wrong object.

### Phase 1 — the conversion (22 sites, 13 files)

One shape. A1 as the worked example:

```diff
-git add seed/models_<agent>.json
-git commit -m "ait: Sync <agent>/<name> registration to seed"
+# `commit -- <paths>` takes worktree content for a tracked path, so no `add` is
+# needed for one. Stage only a path git does not track yet — a pathspec cannot
+# name a file git does not know.
+git add -- seed/models_<agent>.json      # only when registering a NEW agent
+git commit -m "ait: Sync <agent>/<name> registration to seed" \
+    -- seed/models_<agent>.json
+# Read the short SHA from the `[<branch> <sha>] <subject>` line above and show
+# THAT object — a concurrent session sharing this worktree can move HEAD.
+git show --stat <sha>
```

Four rules:

- **The pathspec repeats the `add`'s path list exactly.** Where the `add` used a
  directory (A4-A6, A8, A10) the pathspec names files instead — a directory
  pathspec would still sweep a concurrent session's edits *inside* that
  directory. Neither case needs new machinery, because both procedures already
  know their file set at that point:
  - A4-A6, A8 — the guide the procedure just imported / merged / classified,
    plus the three fixed `aireviewguides/*.txt` metadata files;
  - **A10** (`aitask-audit-wrappers`, Phase 1 commit) — Step 4 four lines above
    already instructs "Collect the `WROTE:` lines emitted by the helper", and
    `aitask_audit_wrappers.sh:412` prints `WROTE:<target>` per file written. Bind
    those targets and commit them:
    ```bash
    wrote=( <the paths from the helper's WROTE: lines> )
    if (( ${#wrote[@]} )); then
        # A WROTE: line names an OVERWRITTEN file as readily as a new one
        # (Step 4's "Yes, overwrite" re-runs apply-wrapper --force, which
        # overwrites and still prints WROTE:). So stage only the targets git
        # does not track yet: `commit -- <paths>` takes worktree content for a
        # tracked path, while an `add` of one would replace the index entry a
        # concurrent session staged for it.
        new=()
        for f in "${wrote[@]}"; do
            git ls-files --error-unmatch -- "$f" >/dev/null 2>&1 || new+=( "$f" )
        done
        (( ${#new[@]} )) && git add -- "${new[@]}"
        git commit -m "feature: Audit and port aitask skill wrappers across code-agent trees" -- "${wrote[@]}"
        git show --stat <sha>
    else
        echo "no wrappers written — nothing to commit"
    fi
    ```
    The `ls-files --error-unmatch` test is the same tracked-path predicate
    `ait_commit_paths_staging_untracked` uses (`lib/task_utils.sh:680`), written
    against plain `git` — not a new rule, the established one applied on `main`.
    A10 gets the `if` branch for the same reason A22 does: the list comes from a
    helper's run-time output, so it can legitimately be empty when the audit
    closes no gap.
- **Delete the `add` where every path is always tracked** (A2, A9, A11, A20,
  A21, A23, A24) — `commit -- <paths>` needs no staging for a tracked path, and
  an `add` of one replaces the index entry a concurrent session staged for it. It
  survives only where a path can genuinely be new (A1, A3, A4-A8, A10, A12, A14,
  A16, A17, A19).

  **Where a site's set is *mixed* — some targets new, some already tracked — the
  `add` filters to the untracked ones** rather than taking the whole list. A10 is
  the worked example above; A5, A6, A7 and A8 are the same shape (a reviewguide
  merge or classify edits existing tracked guides, while an import writes a new
  one), so they take A10's filter with their own list. Passing an already-tracked
  path to `git add` is the shared-index clobber this task removes everywhere
  else, and it is easy to reintroduce at exactly the sites whose file set is
  computed rather than literal.
- **Pin the SHA; never re-read `HEAD`** (Phase 0 item 3).
- **The `--stat` step is part of the instruction**, not advice — a partial commit
  is silent when the pathspec misses a file the agent also changed.

A14 (`task-workflow/SKILL.md:729-730`) keeps its heredoc message:

```bash
git add -- <changed_code_files_git_does_not_track_yet>
git commit -m "$(cat <<'EOF'
<issue_type>: <description> (t<task_id>)

<optional imported contributor block>
<optional code-agent trailer>
EOF
)" -- <changed_code_files>
git show --stat <sha>
```

A15/A16/A17/A12 take the same shape with their own placeholders.

**A22 and A10 are the only two sites with a runtime-generated file list**, so
they are the only ones that get an empty-list guard — and the guard is an `if`
**containing** the commit, not a short-circuit. `(( ${#files[@]} )) || { …; return 0; }` is wrong
here: an instruction is pasted at an ordinary prompt, where `return` outside a
function or sourced script is an error — bash prints `return: can only 'return'
from a function or sourced script` and **carries on to the next line**, running
the very commit the guard was meant to prevent.

```bash
mapfile -t files < <(grep -rl "<oldvalue>" --include='*.md' --include='*.sh' . | grep -v aitasks/)
if (( ${#files[@]} )); then
    git commit -m "ait: Propagate '<newvalue>' issue_type across docs, skills, and tests" -- "${files[@]}"
    git show --stat <sha>
else
    echo "no files matched '<oldvalue>' — nothing to commit"
fi
```

An empty pathspec is not a cosmetic concern: `git commit -m x --` commits the
**whole index**, and this repo already treats that as load-bearing —
`task_git_commit_scoped` (`lib/task_utils.sh:531-535`) and
`ait_commit_paths_staging_untracked` (`:671-674`) each open with
`(( $# )) || return 2` and a comment saying exactly why. State in-line what the
guard does **not** buy: a set discovered by grep is only as complete as the grep,
so the `--stat` is the check, not the pathspec.

A23/A24 are on this repo's `main` and convert normally. Their siblings A25
(`homebrew_maintainer_setup.md:101-102`, the tap repo) and A26
(`aur_maintainer_setup.md:158-159`, the AUR repo) are different, single-purpose
repos where the hazard does not exist — convert them anyway rather than
excepting them: the pathspec costs nothing there and stops the doc teaching the
bad shape.

### Phase 2 — the two exceptions, and the docs

**Exception marker.** One mechanism, one form, reason required:

```markdown
<!-- unscoped-commit-ok: merge commit; git refuses a partial commit during a merge -->
```

It exempts the **next** candidate line only. Line-scoped rather than file-scoped
for one concrete reason: `aitask-pickweb/SKILL.md.j2` carries A18 (exempt) *and*
A19 four lines below (converted normally), so a file-level entry would pin a
bypass over a site that has a cure.

- **A13** `aitask-web-merge/SKILL.md:92` — concluding `git merge`; the commit
  takes the merge's whole index by construction, which is what a merge commit is.
- **A18** `aitask-pickweb/SKILL.md.j2:288,292` — `git add -A` is correct for
  Claude Code Web, whose sandbox is a fresh single-session checkout with no
  concurrent writer. The reason names the isolation, so the shape is never copied
  into a shared-worktree procedure.

`task-fold-marking.md:13` names `git commit --amend --no-edit` while describing
`aitask_fold_mark.sh`'s modes. It is prose about a script, not an instruction —
but it carries arguments, so the bare-name mention rule will not clear it.
**Reword the sentence** (t1748's own precedent) rather than marking something
that is not a command.

**Docs:**

- `aidocs/framework/skill_authoring_conventions.md` — extend the existing "Never
  instruct a bare `./ait git commit`" section with its main-branch sibling: the
  canonical form, why the `add` is deleted for tracked paths, the empty-list
  branch where a list is generated at run time (and why the short-circuit form is
  wrong), the SHA-pinned `--stat`, and the exception marker with the bar for
  using it. One section that points at the task-data rule for the shared
  rationale, not a second copy of it.

  **And what it does not buy**, in the same section: a pathspec stops *unrelated*
  paths riding along; it cannot help when two sessions edit the **same** file,
  because `commit -- <path>` takes that path's worktree content — so the other
  session's in-progress edit is committed under your message just the same.
  Concurrent work on one file needs isolation or coordination, not a pathspec
  (follow-up below).
- `.claude/skills/ait-git/SKILL.md` — its "When NOT to use" bullet reads
  "implementation commits go on the main branch as normal", which is the sentence
  that made this defect invisible. Replace "as normal" with the pathspec rule and
  a pointer to the conventions section.
- `aidocs/framework/shell_conventions.md` — one sentence added to the existing
  instruction-layer cross-reference, naming the main-branch sibling. A pointer,
  not a third copy.
- `website/content/docs/installation/updating-model-lists.md:69` — "plain
  `git add` + `git commit`" becomes the scoped form. Then
  `cd website && python3 check_links.py --build`.

### Phase 3 — the regression scan (BUILT FIRST, committed last)

Extend `tests/test_no_unscoped_task_commit.sh`'s markdown scan (seam 3, t1748)
with a second **pattern**, not a fourth enumeration. `md_in_scope`,
`md_sources_real` / `md_sources_find`, `MD_JOIN_AWK`, `strip_quoted`,
`bare_is_scoped`, the `&&`/`||`/`;`/`|` segmenter, the trailing-comment cut and
the prose mention rule are all **reused verbatim** — the point is that the two
markdown patterns cannot disagree about what "inside a string" or "one segment"
means. Its subject is narrow by design: **newly introduced bare `git commit`
instructions**, nothing else.

Three changes:

1. **`PLAIN_GIT_COMMIT_RE`** — `git` + whitespace + `commit` + a word boundary,
   with a leading character class rejecting `ait git commit`, `task_git commit`
   and any `<word>git`. The word boundary excludes `git commit-tree` (plumbing:
   it writes an object, it has no index).
2. **Widen `MD_JOIN_AWK`'s emit filter.** It currently drops any line not
   matching `ait git commit` — a *performance* contract (the caller forks awk per
   candidate), not a scope one. Widening takes the md-scope candidate set from
   ~40 lines to ~200. The guard already runs ~54s here, so **measure and record**
   the new wall time; if it regresses materially, hoist the per-candidate fork
   rather than narrow the filter.
3. **The exception marker**, parsed as in Phase 2: exempts the next candidate
   line only, reason must be non-empty, and each exempted site plus its reason is
   **printed in the scan's summary** — an exception nobody can see is an
   allowlist with extra steps. `MD_PLAIN_ALLOWLIST=()` is declared **empty**,
   with the same "the bar is high" comment the other three carry; the marker is
   the mechanism precisely because it is line-scoped and self-documenting.

Controls, planted in the existing `$TMP/md/` fixture tree and named `mdp_*` so
the `md_*` and `aitask_*` count pins do not move:

- **Flagged:** unscoped `git commit -m "x"` in a fence · in an inline span ·
  `git add <p> && git commit -m "x"` where only the `add` carries `--` · trailing
  `# … use -- for a pathspec` · a marker with an **empty** reason · a marker
  separated from the command by a blank line (it exempts the *next candidate*,
  not the next command five lines down).
- **Not flagged:** `git commit -m "x" -- <p>` in a fence and inline ·
  `git commit-tree` · `./ait git commit` (seam 3's business; it must not be
  double-reported) · `aitask_task_commit.sh …` · a bare `` `git commit` `` noun
  in prose · a correctly-formed marker immediately above its command.
- **Marker-independence:** a synthetic marker suppresses only the line it
  precedes and leaves the next site in the same file flagged — the assertion that
  pins why A19 stays guarded while A18 is exempt.
- **Anti-vacuity:** the enumerated surface must still carry plain `git commit`
  text after the conversions — pinned as *named files that keep the text*
  (`skill_authoring_conventions.md`, `ait-git/SKILL.md`, whose cure is to
  demonstrate the scoped form), never as a corpus count, which the conversions
  themselves would move.

**What the scan does not see, stated in the header** alongside the existing
boundary bullets:

- a pathspec that *expands* to nothing (`-- "${files[@]}"` empty, an
  unsubstituted placeholder) — textually it carries a `--` and passes. Covered
  behaviourally for A22 and A10 only, by the empty-list control below;
- `git add` of a **tracked** path. This scan judges commits, not staging, so a
  later edit can restore tracked-path staging beside a correct
  `git commit -- <paths>` and stay green. A `git add` manifest was considered and
  deliberately not built (user decision); the limitation is recorded here and as
  a follow-up.

### Phase 4 — regenerate

```bash
./.aitask-scripts/aitask_skill_verify.sh
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done
```

56 render instances follow from A12/A14/A15/A16/A17/A18/A19; then regenerate the
`tests/golden/procs/task-workflow/` and
`tests/golden/skills/{aitask-pickrem,aitask-pickweb,aitask-wrap}/` goldens per
`skill_authoring_conventions.md` → "Regenerate goldens after any `.md.j2` or
closure edit". **Review the golden diff** — it must contain the conversions and
nothing else. Goldens and sources land in the same commit.

The stale `.claude/skills/*-_skillrun_416236_1779701547729-/` dirs found during
the sweep carry frozen copies of A14/A15 and are **not** refreshed by a
re-render. They are gitignored and out of the scan's scope (component ends in
`-`); leave them, and note them.

### Post-phase (risk mitigations)

**`foreign_staged_control`** — the Phase 0 control, now run against the
**converted** command text verbatim as an agent would run it. Its discriminating
power is established in Phase 0 against the pre-conversion form: that one must
sweep the foreign file into the commit, the converted one must leave it staged
and uncommitted. Without the failing half this proves the conversion changed
prose, not behaviour.

**Empty-list control (A22 and A10).** Same scratch repo, foreign file staged: run
each site's literal converted text with its list empty — A22 with a grep that
matches nothing, A10 with no `WROTE:` lines — and assert no commit is created.
Establish discriminating power first by replacing the `if`
with the rejected `(( … )) || { …; return 0; }` form — that run must print
bash's `return: can only 'return' from a function or sourced script` **and commit
the foreign file anyway**. That failing half is why the branch shape is mandated.

**Force-overwrite control (A10).** The `WROTE:` list can name a **tracked** file,
because Step 4's "Yes, overwrite" re-runs `apply-wrapper --force`, which
overwrites and still prints `WROTE:` (`aitask_audit_wrappers.sh:405-412`). In the
scratch repo: commit a wrapper file so it is tracked, have a "concurrent session"
stage a *different* version of that same path, then overwrite it on disk and run
A10's literal converted text. Assert the commit carries the worktree version
**and the foreign staged entry for that path is still in the index, unreplaced**.
Discriminating half: with the filter removed — an unconditional
`git add -- "${wrote[@]}"` — the foreign staged entry must be clobbered. Without
that half the control cannot tell the filter from its absence.

## Verification

1. `bash tests/test_no_unscoped_task_commit.sh` — green, with the new pattern's
   count pin, the marker-independence assertion, the anti-vacuity pin, and both
   existing seams unchanged. Non-vacuity comes from the `scanner_red_proof`
   pre-phase, not from a committed red test; attach the saved failure output and
   the `git worktree` replay recipe to the Final Implementation Notes. Record the
   new wall time.
2. `bash tests/test_skill_render_task_workflow.sh`,
   `test_skill_render_aitask_pickrem.sh`, `..._aitask_pickweb.sh`,
   `..._aitask_wrap.sh` — golden equality.
3. `bash tests/test_skill_verify.sh`, `bash tests/test_skill_dispatch_contract.sh`.
4. `bash tests/run_all_python_tests.sh` — verdict is the **last** line
   (`PYTHON SUITE: …`); `set -o pipefail` if piping.
5. `cd website && python3 check_links.py --build`.
6. The two post-phase controls.
7. Re-run the §"Measured inventory" command: every remaining hit is either an
   exception marker's site or documented prose.
8. This task's own commit is subject to the rule it writes: commit with
   `-- <paths>`, read the short SHA from the commit's own output line, and
   `git show --stat <that sha>` — **not** `HEAD`. The committed path list must
   match the intended edit set exactly.

## Risk

### Code-health risk: low

- The new scan could be **vacuous** — a matcher that finds nothing passes
  forever, and a red proof run with a throwaway lookalike would falsely certify
  the one that ships · severity: medium · → mitigation: inline pre-phase scanner_red_proof
- The exception marker is a **new bypass mechanism**; a marker with no controls
  is a file allowlist at finer grain · severity: low · → mitigation: None
  (addressed in the plan body — non-empty reason required, exempts only the next
  candidate line, every exemption printed in the scan output, and a
  marker-independence control asserting A19-shaped sites stay flagged, Phase 3)
- Widening `MD_JOIN_AWK`'s emit filter multiplies the candidate set ~5× on a
  guard that already takes ~54s, and the caller forks awk per candidate ·
  severity: low · → mitigation: None (addressed in the plan body — measure and
  record the new wall time; hoist the fork rather than narrow the filter,
  Phase 3)
- Wide file count (13 sources + 56 renders + goldens), but every source edit is
  instruction prose; the only executable change is one test file · severity: low
  · → mitigation: None

### Goal-achievement risk: medium

- `git commit -- <paths>` is a **partial** commit: it takes worktree content and
  ignores the index. Where a site's `add` was doing real work — staging an
  untracked path — a pathspec that does not name it silently drops it and the
  commit still succeeds · severity: high · → mitigation: None (addressed in the
  plan body — the `add` survives at every site whose paths can be new, and
  `git show --stat <sha>` is part of the instruction rather than advice, Phase 1)
- The task body named 4 sites; the measured sweep found **24** authoring sites in
  13 files, four staging with a directory pathspec. An implementation that trusts
  the task's list leaves five-sixths of the defect in place · severity: medium ·
  → mitigation: None (addressed in the plan body — the measured inventory plus
  required re-derivation before editing)
- A13's exception rests on git refusing a partial commit during a merge, asserted
  from documentation rather than measured. If wrong, an exception ships over a
  site that had a cure · severity: medium · → mitigation: None (addressed in the
  plan body — Phase 0 item 1 verifies it before the marker is written)
- The conversion could change prose without changing behaviour · severity: medium
  · → mitigation: inline post-phase foreign_staged_control
- At the sites whose file set is **computed rather than literal** (A10, and
  A5-A8), an `add` of the whole computed list re-creates the shared-index clobber
  this task removes elsewhere — `apply-wrapper --force` overwrites a **tracked**
  wrapper and still reports it as `WROTE:` · severity: medium · → mitigation:
  None (addressed in the plan body — those sites filter the `add` to untracked
  targets with the same `ls-files --error-unmatch` predicate the t1702 seam uses,
  and the force-overwrite control asserts a foreign staged entry survives,
  Phase 1 and post-phase)
- **Two residual holes are accepted, not closed** (user decision — keep this
  narrowly scoped): an agent-substituted placeholder that expands to nothing
  leaves `git commit -m … --`, which commits the whole index, and no scan or
  branch covers the placeholder classes (A12/A14/A15/A16/A17); and nothing
  prevents a later edit restoring `git add <tracked>` beside a correct scoped
  commit · severity: medium · → mitigation: None (recorded as limitations in the
  scan header and the conventions section, and as follow-ups below)

### Planned mitigations

- timing: pre-phase | name: scanner_red_proof | type: test | priority: high |
  effort: low | inline_risk: low | added_complexity: medium | addresses: vacuous
  regression scan | desc: build Phase 3 complete but uncommitted BEFORE any site
  edit, observe the shipping guard fail on the pre-conversion tree naming the
  measured inventory, then convert and commit both together; record a
  git-worktree replay recipe at a literal SHA
- timing: post-phase | name: foreign_staged_control | type: test | priority: high
  | effort: low | inline_risk: low | added_complexity: low | addresses:
  conversion changes prose but not behaviour | desc: scratch-repo control — a
  foreign staged file must be absent from a converted site's commit and still
  staged afterwards; establish discriminating power against the pre-conversion
  command first, in Phase 0

## Follow-ups to record (not done here)

- **Placeholder pathspecs can expand to nothing.** A12/A14/A15/A16/A17 substitute
  an agent-chosen file list into the pathspec; if the agent substitutes nothing
  the command is `git commit -m … --`, which commits the whole index. A22's
  `if`-branch shape is the cure but needs a real list to branch on. Raised during
  planning and deliberately scoped out of this task; worth a task that gives each
  placeholder class an executable no-op branch.
- **Tracked-path staging is unguarded.** The scan judges commits, not `git add`.
  A per-site staging manifest was designed and deliberately not built; a future
  task could add one if a real incident appears.
- **Same-file concurrency has no cure at this layer.** A pathspec bounds *which*
  paths a commit takes; it cannot stop a second session's in-progress edit to one
  of *those* paths being committed under the first session's message. Phase 2
  states the limitation in the canonical guidance; the mechanism that would
  address it — routing same-file concurrent work to a worktree, or a coordination
  check before a code commit — is a separate task.
- **Upstream defect, shell layer:** `aitask_setup.sh` runs seven plain unscoped
  `git commit` calls against the user's project worktree — `:1973`, `:1975`, and
  the five `git add .gitignore && git commit -m "…"` pairs at `:2304`, `:2336`,
  `:2368`, `:2414`, `:2448`. The same file already does it correctly at `:3783`
  (`-- "${changed_files[@]}"`, with a comment saying why), so the cure is
  established in-place. `:1973`/`:1975` are additionally gated by a **global**
  `git diff --cached --quiet`, so a foreign pre-staged file both triggers the
  commit and rides along. Out of this task's instruction-layer scope (user
  decision).
- The `.aitask-scripts/agentcrew/` and `aitask_crew_*.sh` commits are unscoped
  but run inside dedicated crew worktrees — no shared index, no defect. Recorded
  so a future sweep does not re-flag them.

## Step 9 (Post-Implementation)

Cleanup, archival and merge follow `task-workflow` Step 9 as normal. Output
branch `main`; this task works on the current branch (profile `fast`), so there
is no task branch to merge.

## Final Implementation Notes

- **Actual work done:** 26 instructed plain-`git commit` sites on `main`
  (A1–A26; the task body named 4). 24 now name their paths after `--`; the 2
  that cannot (A13 merge commit, A18 Claude Code Web sandbox) carry a
  line-scoped `<!-- unscoped-commit-ok: <reason> -->` marker. The `add` is
  deleted wherever every path is tracked — all 19 "always tracked" paths were
  checked with `git ls-files --error-unmatch`, including
  `.claude/settings.local.json` — and filtered to untracked targets where a
  site's set is computed and can mix (A4–A8, A10, A22). Every converted site
  verifies with `git show --stat <sha>`, the SHA read from the commit's own
  `[<branch> <sha>]` line. Runtime-generated lists (A10, A22) hold the commit
  inside an `if`. `task-fold-marking.md:13` was reworded (prose about a script,
  not an instruction). New canonical section "Never instruct a bare `git commit`
  on `main`" in `skill_authoring_conventions.md`; pointers from `ait-git`,
  `shell_conventions` and the website page. Guard seam 4 in
  `tests/test_no_unscoped_task_commit.sh`, reusing seam 3's enumeration, join,
  quote stripping, segmenter and mention rule, with 22 new controls. Renders
  (12 tracked `-remote-` files) and 11 goldens regenerated.
- **Deviations from plan:**
  - Heredoc sites (A14–A17) use `git commit -F - -- <paths> <<'EOF'`, not the
    planned `-m "$(cat <<'EOF' …)" -- <paths>`: the planned form puts the
    pathspec on the heredoc's closing line, which the scanner never joins, so
    every heredoc site would have stayed red permanently. `-F -` verified
    (partial commit, multi-line message intact, foreign entry untouched), and
    both shapes are pinned by fixtures.
  - **The index claim at several sites was wrong and is corrected.** Measured in
    all four combinations: a *successful* `git commit -- P` sets `P`'s index
    entry to what it committed whether or not `P` was `add`ed; only a *failed*
    commit discriminates (no `add` keeps a concurrent session's staged entry,
    `add` has already clobbered it). The misleading "an `add` of a tracked path
    replaces the index entry a concurrent session staged for it" was removed
    from 5 sites and the guard's failure message; the canonical doc carries the
    failure-qualified statement. The force-overwrite control was re-specified
    around the failure path accordingly.
  - Seam 4 does not fail closed on **unformatted** prose (seam 3 does): "the
    path-scoped git commit failed" and similar are real English in this tree.
    An unformatted occurrence counts only when invocation-shaped
    (`git commit -…`). Five real false positives cleared; both directions pinned.
  - A22 enumerates from §2–§5's own edit lists, not a grep — a grep for
    `<newvalue>` matches common words — and gained the untracked filter, since
    regenerated goldens can be new files.
  - A3: the plan's survivor list kept its `add`, but all three seed files are
    tracked, so the plan's own rule deletes it.
  - The seam-separation control is stated as "no site reported by both seams",
    not "no `md_` fixture reaches seam 4": `portrait git commit` is a seam-3
    negative and a genuine plain-`git commit` token sequence, correctly reported
    once by seam 4.
- **Issues encountered:**
  - Guard wall time 56s → 60–66s from the widened `MD_JOIN_AWK` emit filter;
    acceptable, not hoisted.
  - A display bug in the new seam's own report: `printf '%s'` of a multi-line
    value prefixed only the first `EXCEPTION:` line, hiding the second
    exception. Fixed (per-line loop).
  - `main` advanced mid-session (`29d025d1e`, t1772, `install.sh` + its test);
    no intersection with this change. A concurrent session is editing
    `aitask-shadow` (a shortcodes feature) in the shared checkout, which makes
    `test_skill_render_aitask_shadow.sh` fail against the committed golden —
    their in-flight work, not this change (shadow reads only `profile.name`;
    no shadow file is in this commit).
  - The stale `.claude/skills/*-_skillrun_416236_1779701547729-/` render dirs
    carry frozen pre-change copies of A14/A15; gitignored, out of the scan's
    scope, left alone.
- **Key decisions:** (user) narrowly scoped hardening — no main-branch commit
  helper, no `git add` manifest, one exception form. Residuals recorded rather
  than enforced: an agent-substituted placeholder pathspec that expands to
  nothing; a later edit restoring tracked-path staging; after a *failed* commit
  the untracked paths you staged stay staged (the unstage-on-failure half a
  helper would buy); and same-file concurrency, which no pathspec can fix.
- **`scanner_red_proof` (pre-phase) — evidence.** Built complete and uncommitted
  before any site edit. The FINAL shipped guard, replayed against the literal
  pre-conversion SHA:
  ```bash
  git worktree add --detach "$SCRATCH/t1762-preproof" 9cb61927c8910812c2c6a3fa852663cf7ad9bd8e
  cp tests/test_no_unscoped_task_commit.sh "$SCRATCH/t1762-preproof/tests/"
  ( cd "$SCRATCH/t1762-preproof" && bash tests/test_no_unscoped_task_commit.sh )
  # -> exit 1, "100 passed, 1 failed", naming exactly the 26 measured sites
  git worktree remove --force "$SCRATCH/t1762-preproof"
  ```
  Executed: exit 1, 26 sites, identical to the pre-edit measurement.
- **`foreign_staged_control` (post-phase) — evidence**, on the literal text
  extracted from the files: A14's pre-conversion text (from `9cb61927c`)
  committed `foreign.txt ours.sh` and consumed the foreign entry; the converted
  text committed `ours.sh` only and left `foreign.txt` staged. Empty-list:
  A22 and A10 with empty lists created no commit; the rejected
  `(( … )) || { …; return 0; }` form printed bash's `return` error and
  committed the foreign file anyway. Force-overwrite (A10, failed commit): the
  filter kept the concurrent `FOREIGN` entry; with the filter removed (mutation
  confirmed landed) it was clobbered to `OURS`.
- **Verification:** guard 101/101; all 15 render tests pass except pickrem /
  pickweb Test 6 (freshness vs `HEAD`, red until commit by design) and the
  shadow golden above; Python suite PASSED; `aitask_skill_verify.sh` OK;
  `test_skill_verify.sh` / `test_skill_dispatch_contract.sh` pass;
  `check_links.py --build` 0 broken; shellcheck warning classes unchanged.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:1973 — plain unscoped git commit against the user's project worktree (also :1975, :2304, :2336, :2368, :2414, :2448); :1973/:1975 are gated by a global git diff --cached --quiet, so a foreign pre-staged file both triggers the commit and rides along; the same file already does it right at :3783`
  - `aidocs/framework/model_reference_locations.md:229 — promote-mode commit names a file set (aitask_codeagent.sh, brainstorm_crew.py, aitask_brainstorm_init.sh, seed/codeagent_config.json) that disagrees with .claude/skills/aitask-add-model/SKILL.md:167-168 (lib/agent_string.sh, aitask_codeagent.sh), and step 6 still locates DEFAULT_AGENT_STRING in aitask_codeagent.sh while the skill says lib/agent_string.sh; one of the two is stale`
