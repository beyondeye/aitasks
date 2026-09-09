---
Task: t1748_scope_ait_git_commit_in_skill_procedures.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1748 — Scope the `./ait git commit` sites in skill procedures

## Context

t1728 closed the unscoped-task-data-commit defect in the **shell** layer:
`./ait git` is `task_git` in a subprocess, so `./ait git commit -m "…"` with no
`--` pathspec commits the **entire** shared `.aitask-data` index — whatever a
concurrent session had staged at that instant lands in a commit whose message
names unrelated work. Its guard, `tests/test_no_unscoped_task_commit.sh`, scans
`.aitask-scripts/**/*.sh` only.

The identical defect is still live at the **instruction** layer, where agents
follow it literally. A full sweep found **31 unscoped sites in the Claude Code
sources** and **zero scoped ones** — no instruction site anywhere routes through
the existing seam. Several are worse than the shell sites were: six of them
stage with `./ait git add aitasks/` (or `aitasks/ aiplans/`), a directory
pathspec that sweeps a concurrent session's in-progress task edits into the
commit as well.

This is not hypothetical. While executing t1728 itself, the agent reached
`plan-externalization.md`'s "Commit the externalized plan" block and would have
run the unscoped form had it not just spent the session studying why that is
wrong. Every agent that runs `/aitask-pick` on a machine with a concurrent
session is exposed.

**Outcome:** every instruction-layer task-data commit names its own paths, the
canonical teaching snippets stop seeding the unscoped form, and a third scan in
the existing tripwire stops site 32 from appearing.

## Decisions (confirmed with the user)

1. **Hybrid cure.** Real commit sites route through
   `./.aitask-scripts/aitask_task_commit.sh -m "<msg>" <paths>` — the t1702 seam
   wrapper, which stages only untracked paths, unstages exactly those on
   failure, arms its own EXIT trap, and refuses anything outside
   `aitasks/`/`aiplans/`. The teaching snippets whose *subject* is `./ait git`
   itself (CLAUDE.md and its mirrors, `ait-git/SKILL.md`) keep `./ait git
   commit` but gain an explicit `-- <path>` pathspec, plus a pointer to the
   helper.
2. **Third scan in the same file.** `tests/test_no_unscoped_task_commit.sh`
   grows a markdown scan alongside its two shell patterns, with its own
   allowlist, its own header "Detection scope" bullets, and its own planted
   positive/negative controls. One tripwire keeps owning one defect class — the
   same way it grew a second pattern for t1728.

## Blast radius (measured, not estimated)

| Tree | Hits | Action |
|---|---|---|
| `.claude/skills/**` non-rendered sources | 31 | **edit** — the only files with content to change |
| Root instruction docs + seed | 5 | **edit** (byte-duplicated snippet) |
| `aidocs/` | 2 instruction, 4 prose | **edit** the 2 |
| `.claude/skills/*-<profile>-/` rendered | 70 | regenerate; only the 10 `remote-` files are tracked |
| `.agents/skills/*-<p>-codex-/` rendered | 70 | regenerate; only the 10 `remote-codex-` files are tracked |
| `.opencode/skills/*-<p>-/` rendered | 70 | regenerate; only the 10 `remote-` files are tracked |
| `tests/golden/**` | 55 | regenerate |
| `.agents/skills/<name>/SKILL.md`, `.opencode/skills/<name>/SKILL.md` | **0** | **no port task needed** — verified to be thin "Source of Truth" pointer wrappers (18 lines) that redirect to the Claude source, not content duplicates |

`AGENTS.md`, `.codex/instructions.md` and `.opencode/instructions.md` are
marker-managed (`>>>aitasks` / `<<<aitasks` at line 1 of each) and regenerated
wholly from `seed/aitasks_agent_instructions.seed.md` by `ait setup`
(`assemble_aitasks_instructions`); this repo's `CLAUDE.md` is markerless and
hand-maintained (its sentinel tells setup to leave it alone). So: edit the seed,
hand-apply the identical change to the three mirrors, edit `CLAUDE.md`
separately, then verify the changed snippet is byte-identical across all four
mirrors. `tests/test_agent_instructions.sh` runs against mock fixtures and does
**not** check real-repo seed↔mirror parity, so that verification is a direct
diff of the snippet, not a test run.

## Prerequisite: whitelist the helper

`./.aitask-scripts/aitask_task_commit.sh` is currently **missing from all five**
helper-permission touchpoints — verified:

```
$ ./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_task_commit.sh
MISSING:1  .claude/settings.local.json
MISSING:3  .codex/rules/default.rules
MISSING:4  seed/claude_settings.local.json
MISSING:6  seed/codex_rules.default.rules
MISSING:7  seed/opencode_config.seed.json
```

Without this, every converted site prompts for permission — and blocks outright
under a headless/remote profile. Apply with
`./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_task_commit.sh`,
then re-run `audit-helper-whitelist` and require empty output. **This lands
before the site conversions**, so no intermediate commit ships a site the agent
cannot execute.

## Implementation

### Pre-phase (risk mitigations)

**`scanner_red_proof`** — prove the markdown scan is not vacuous by running **the
exact matcher that ships**, never a throwaway lookalike, against the
**pre-conversion** tree. A separately-written probe could differ from the
committed guard in precisely the way that matters and would falsely certify
coverage.

This changes the phase order: **Phase 5 is built before Phases 1-4 edit
anything**, and the red window lives entirely in the uncommitted working tree.

1. Write `tests/test_no_unscoped_task_commit.sh` complete — enumerator, matcher,
   header, fixtures, all controls — and get the *fixture* controls green. Do not
   commit.
2. Run `bash tests/test_no_unscoped_task_commit.sh` against the untouched tree.
   Its markdown scan **must fail**, naming the measured site inventory. Save the
   output to the scratchpad; diff it against the inventory in this plan. Extra
   hits mean the span-rejoin is over-gluing; missing hits mean the matcher is
   under-reaching. Neither is acceptable — fix the matcher, not the expectation.
3. Only then run Phases 0-4. Re-run the guard: green.
4. Commit the guard and the conversions **together**, in one commit. No commit
   ever contains a red tripwire, and no commit contains a guard that was never
   observed failing.

**Replayable evidence, recorded in the Final Implementation Notes.** Step 2's
saved output is a one-shot observation, so pair it with a proof anyone can
re-run later against the shipped guard:

```bash
wt="$SCRATCH/t1748-preproof"
git worktree add --detach "$wt" <pre-conversion SHA>   # record the literal SHA,
cp tests/test_no_unscoped_task_commit.sh "$wt/tests/"  # not HEAD~1 — main
( cd "$wt" && bash tests/test_no_unscoped_task_commit.sh )  # advances under you
echo "expect: FAIL, naming the site inventory"
git worktree remove --force "$wt"
```

The committed matcher, run over the pre-conversion sources. Record the literal
parent SHA in the notes — `HEAD~1` stops meaning "before this change" as soon as
another session lands a commit. Use `git worktree`, **never `git stash`**:
nineteen sessions share this working tree.

### Phase 0 — whitelist (above)

### Phase 1 — task-workflow procedures (13 sites in 9 files)

Canonical conversion, and the one to copy:

```diff
 # .claude/skills/task-workflow/plan-externalization.md:132-136
-./ait git add aiplans/<plan_file>
-./ait git commit -m "ait: Add plan for t<task_id>"    # EXTERNALIZED
-./ait git commit -m "ait: Update plan for t<task_id>" # OVERWRITTEN
+# EXTERNALIZED
+./.aitask-scripts/aitask_task_commit.sh -m "ait: Add plan for t<task_id>" aiplans/<plan_file>
+# OVERWRITTEN
+./.aitask-scripts/aitask_task_commit.sh -m "ait: Update plan for t<task_id>" aiplans/<plan_file>
```

The separate `./ait git add` **goes away** — the helper stages untracked paths
itself and unstages them if the commit fails; leaving the `add` in would
re-introduce the tracked-path index-clobber hazard the seam exists to remove.

**Each converted block gains an outcome note, and the note must say "read the
whole output", not "read the line".** Verified in
`aitask_task_commit.sh:129-133`: a path that is neither tracked nor on disk
prints `SKIPPED:unknown:<path>` **and the loop continues**, so the run commits
the remaining paths and terminates with `COMMITTED:<n>:…` at **exit 0**. An
instruction that read only the last line would report success having silently
dropped a file it asked for. That is reachable in this very plan —
`task-abort.md` passes `<task_file> <plan_file>` and the plan file may not
exist. So the note reads:

> **Read the whole output and the exit status; the status is the authority.**
> Exit 0 → committed (`COMMITTED:<n>:<subject>`). Exit 2 → nothing was committed
> (`NOCHANGE`, the expected idempotent re-run, **or**
> `REFUSED:out_of_scope:<path>` — a path outside `aitasks/`/`aiplans/` reached
> the call; fix the caller, never retry). Exit 1 → `FAILED:<detail>`; the file is
> written but uncommitted — report it.
>
> **`SKIPPED:unknown:<path>` lines can precede any of those, including a
> successful `COMMITTED:`.** For every call site, this procedure names which
> paths are REQUIRED and which are OPTIONAL. A `SKIPPED:` naming a **required**
> path is a failure even at exit 0 — report it and do not treat the commit as
> complete. A `SKIPPED:` naming an **optional** path (a plan file that may not
> exist) is expected and needs no action.

Per-site required/optional split, stated in each converted block:
`task-abort.md` — `<task_file>` required, `<plan_file>` optional; every other
Phase 1/2 site — all named paths required.

That outcome note replaces the existing `2>/dev/null || true` idiom at
`plan-approved-stop.md:69` and `crash-recovery.md:143` — exit 2 *is* the
idempotent case, so it no longer needs to be hidden. Note that hiding it was
never safe anyway: `2>/dev/null` suppresses stderr while these records go to
**stdout**.

| File | Line | Pathspec |
|---|---|---|
| `plan-externalization.md` | 134,135 | `aiplans/<plan_file>` |
| `plan-approved-stop.md` | 69 | `aiplans/<plan_file>` |
| `plan-approved-stop.md` | 127 | `<task_file>` (was `add aitasks/`) |
| `planning.md` | 305 | each child plan file, named — **not** the `aiplans/p<parent>/` directory pathspec, which stages whatever else is in that directory |
| `planning.md` | 209 | prose reference — reword to name the helper |
| `risk-mitigation-followup.md` | 398 | prose — reword to name the helper, `<plan_file>` |
| `auto-verification.md` | 146 | `aiplans/<plan_path>` |
| `manual-verification.md` | 291 | `<task_file>` (was `add aitasks/`) |
| `crash-recovery.md` | 143 | `<task_file>` (was `add aitasks/`) |
| `task-abort.md` | 64 | `<task_file> <plan_file>` (was `add aitasks/ aiplans/`) |
| `SKILL.md` | 603 | `<task_file>` (was `add aitasks/`) |
| `SKILL.md` | 740 | `aiplans/<plan_file>` |

The `./ait git push` line that follows four of these **stays** — the helper
never pushes, by design.

### Phase 2 — entry-point skills (18 sites in 8 files)

Same conversion. Two shapes need care:

- `aitask-revert/SKILL.md.j2` (8 sites) — inline-backtick one-liners of the form
  `./ait git add <paths> && ./ait git commit -m "…"`. The `add` is scoped but
  the commit is not, so these are full violations. Replace the whole pair with
  the single helper call. The deletion branches already `rm` from the worktree
  (never `git rm`), which is exactly the helper's documented deletion contract.
- `aitask-wrap/SKILL.md.j2:277` — sits in a fenced block that also carries a
  plain `git commit` for **code** files. Convert only the `./ait git` pair;
  leave the code commit alone.

Remaining: `aitask-pickrem/SKILL.md.j2:390,557`; `aitask-add-model:141`
(`aitasks/metadata/models_<agent>.json`, plus `codeagent_config.json` in promote
mode); `aitask-contribute:60,274` (`aitasks/metadata/code_areas.yaml`);
`aitask-contribution-review:294`; `aitask-refresh-code-models:146`;
`aitask-web-merge:123`. All resolve to paths under `aitasks/`/`aiplans/`, so all
are in helper scope.

### Phase 3 — the teaching snippets (pathspec cure)

`ait-git/SKILL.md:14-15`, `CLAUDE.md:233-234`, `AGENTS.md:63-64`,
`.codex/instructions.md:63-64`, `.opencode/instructions.md:63-64`,
`seed/aitasks_agent_instructions.seed.md:62-63`:

```diff
 ./ait git add aitasks/t42_foo.md
-./ait git commit -m "ait: Update task t42"
+./ait git commit -m "ait: Update task t42" -- aitasks/t42_foo.md
 ./ait git push
```

plus one sentence: a bare `./ait git commit` commits the whole shared index, and
`./.aitask-scripts/aitask_task_commit.sh -m "<msg>" <paths>` is the preferred
route for task/plan files. `ait-git/SKILL.md` gets a short "Scoped commits"
section carrying the same rule, since it is the skill whose entire purpose is
teaching this.

### Phase 4 — aidocs

- `aidocs/framework/model_reference_locations.md:203-204` — real instruction;
  convert to the helper.
- `aidocs/issue_type_vocabulary_duplication.md:156` — says "only
  `aitasks/metadata/task_types.txt`" but names no mechanism; name the helper.
- `aidocs/framework/skill_authoring_conventions.md` — **new section**: the
  instruction-layer rule (never write a bare `./ait git commit` in a procedure;
  route through the helper; the pathspec form is for docs whose subject is
  `./ait git`; the guard that enforces it).
- `website/content/docs/installation/updating-model-lists.md:68` — user-facing
  description of exactly the model-list flow Phase 2 changes; update to name the
  helper, then run `python3 check_links.py --build` in `website/`.

- `aidocs/framework/shell_conventions.md` — add a **short cross-reference only**
  (2-3 lines) at the end of the existing scoped-commit section: the instruction
  layer carries the same hazard, the helper is its cure, and the third scan
  guards it. The normative text lives in `skill_authoring_conventions.md`; this
  is a pointer, not a second copy.

  *(This file was dirty with another session's t1745 work when planning started;
  t1745 has since landed and the file is clean. Re-check `git status` for it
  before editing — if a concurrent session has it dirty again, drop this bullet
  to a follow-up rather than committing someone else's hunk.)*

### Phase 5 — the third scan (BUILT FIRST, see the pre-phase; committed last)

Extend `tests/test_no_unscoped_task_commit.sh` with a third scan,
`scan_docs()`, alongside the existing `scan_dir()`.

**The whole scope decision lives in ONE shared predicate, `md_in_scope`, and
both listers are dumb.** The tempting shape — put the allowed roots in the
`git ls-files` pathspec and give the fixture tree a plain `find` — is wrong: the
allowed-root half of the contract would then exist only on the real-tree path,
so a planted `website/content/x.md` fixture could never test it, and the
"website is excluded" assertion would be vacuous. The predicate is the contract,
and it is exercised identically by both paths:

```bash
# Allowed roots (prefix match) and allowed exact files. THE SCOPE CONTRACT.
MD_ROOTS=( .claude/skills/ .agents/skills/ .opencode/skills/
           .opencode/commands/ .aitask-scripts/skill_templates/ aidocs/ )
MD_FILES=( CLAUDE.md AGENTS.md .codex/instructions.md
           .opencode/instructions.md seed/aitasks_agent_instructions.seed.md )

# md_in_scope <repo-relative-path> — 0 iff this scan owns it.
# THE ONLY JUDGEMENT. Both listers call it; nothing else decides scope.
md_in_scope() {
    local p="$1" r f
    case "$p" in *.md|*.j2) : ;; *) return 1 ;; esac
    # Exclusions first, so an excluded path under an allowed root still loses.
    case "$p" in tests/golden/*) return 1 ;; esac        # render snapshots
    case "/$p" in */*-/*) return 1 ;; esac               # rendered per-profile dirs
    for f in "${MD_FILES[@]}"; do [[ "$p" == "$f" ]] && return 0; done
    for r in "${MD_ROOTS[@]}"; do [[ "$p" == "$r"* ]] && return 0; done
    return 1                                             # default DENY
}

md_filter() { while IFS= read -r p; do md_in_scope "$p" && printf '%s\n' "$p"; done; }

md_sources_real() {      # dumb lister: every tracked .md/.j2, judged by the predicate
    git -C "$PROJECT_DIR" ls-files -- '*.md' '*.j2' | md_filter
}
md_sources_find() {      # dumb lister: same, for the non-git fixture tree
    ( cd "$1" && find . -type f \( -name '*.md' -o -name '*.j2' \) \
        | sed 's|^\./||' | sort ) | md_filter
}
```

**Default-deny is what makes the two paths agree.** `website/`, `docs/`,
`README.md` and the changelogs are out because they match no allowed root — not
because of a subtraction rule that only one lister applies. The broad
`git ls-files '*.md' '*.j2'` (747 files) is deliberate: narrowing it to the
allowed roots would move half the contract back out of the predicate and make
the real-tree out-of-scope assertions untestable. `aitasks/` and `aiplans/` are
not tracked on this branch at all (task data lives on `.aitask-data`), but they
stay out by default-deny anyway, which is what a legacy-mode checkout needs.

**`git ls-files`, not `find`.** The stale orphaned
`.claude/skills/task-workflow-_skillrun_*/` renders exist on disk right now and
are gitignored; `find` walks into them and double-reports. The
component-ending-in-`-` filter catches them too — belt and braces, because the
next orphan may not end in `-`. And the guard's subject is what *ships*: an
uncommitted instruction file is not one any agent follows from a fresh clone.
The cost — a not-yet-`git add`ed file is invisible — goes in the header, not
into a workaround.

**Deliberately out:** `website/` and `docs/` (documentation *about* the tool,
read by humans, not executed); `README`/`CHANGELOG`, `aitasks/`, `aiplans/`,
`.aitask-data/` (records of decisions, not instructions); `tests/`, consistent
with the header's existing exclusion. **`aidocs/` stays in wholesale** — the full
rule over all ~70 aidocs files yields exactly one flag,
`model_reference_locations.md:204`, and it is a true positive the task's own list
missed; excluding the root to dodge `shell_conventions.md` would have cost that
catch. Comment that `X.md` beside `X.md.j2` is a profile-dispatch **stub**, not a
render — checked, and deliberately not excluded.

**Scope assertions — both directions, because a count floor proves neither.**
A floor alone can be satisfied while the interesting root silently drops out of
the pathspec, *and* it cannot detect the pathspec having grown to swallow
`website/`. So assert:

- *in-scope:* the total is above a floor; `grep -qxF` (not substring) membership
  for `.claude/skills/ait-git/SKILL.md`, `CLAUDE.md`,
  `seed/aitasks_agent_instructions.seed.md`, and one `aidocs/` file;
- *out-of-scope:* no enumerated path starts with `website/`, `docs/`, `tests/`,
  `aitasks/`, `aiplans/` or `.aitask-data/`, none is `README.md` or a
  `CHANGELOG*`, none contains a component ending in `-`, and none starts with
  `tests/golden/`. Assert these against the **real** enumeration, not only the
  fixture tree — the exclusions are a claim about this repo.

**And the same predicate is exercised from the fixture side**, which is only
possible because scope is one function rather than a pathspec on one path and a
subtraction on the other. The fixture tree mirrors repo-relative structure, so
plant, each carrying an unscoped command:

| Fixture path under `$TMP/md/` | `md_sources_find` |
|---|---|
| `.claude/skills/foo/SKILL.md` | listed |
| `CLAUDE.md` | listed |
| `aidocs/x.md` | listed |
| `website/content/x.md` | **not** listed — no allowed root |
| `README.md` | **not** listed — not an allowed exact file |
| `docs/x.md`, `tests/x.md` | **not** listed |
| `tests/golden/procs/x.md` | **not** listed — snapshot |
| `.claude/skills/foo-remote-/SKILL.md` | **not** listed — rendered dir |
| `.claude/skills/foo/notes.txt` | **not** listed — extension |

These are **enumerator** controls, distinct from the matcher controls below, and
each excluded fixture deliberately contains a violation — so if the predicate
ever admitted it, the markdown count pin would move and the test would fail
rather than pass quietly. Assert both the membership list and the
`md_in_scope` return code directly, so a lister bug and a predicate bug are
distinguishable.

Plus one anti-vacuity assertion: the enumerated surface must still **carry
`./ait git commit` text at all**, so a green scan provably means "found the
occurrences and judged each" rather than "matched nothing". Pin it as *named
files that keep the text* — `ait-git/SKILL.md` and `CLAUDE.md`, whose Phase-3
cure is the `-- <path>` form and therefore retains the string — **not** as a
corpus count. A count floor derived from the pre-fix tree would break the moment
Phase 2 routes most sites through the helper and deletes the text entirely.

**Extraction — a backtick span is a command container, on a par with a fence
body.** A fenced-only scanner (the `test_skill_errexit_capture.sh` Test 4 shape)
would miss nine real sites: `aitask-revert/SKILL.md.j2`'s eight sit inside a
```markdown fence (opened at :344) as backticked one-liners, and
`risk-mitigation-followup.md:398`'s span wraps across prose lines. So:

1. Inside a fence — the line **is** command text (skip blanks and `#` lines).
2. Outside — each inline backtick span's contents is a candidate. If the pattern
   matches the line with *all* spans removed, the command was written with no
   code formatting at all: **fail closed** and report it, rather than model a
   shape this scanner does not handle.

**Exemption: the mention rule.** In prose only (never inside a fence), a span
whose **entire content is the bare command name with no arguments** is the
command used as a *noun*. That one structural rule clears every known false
positive with no allowlist and no context window, because it is a property of
how English quotes a command rather than a hardcoded fact about six files:

| Site | Span | Verdict |
|---|---|---|
| `shell_conventions.md:89,91,113` | `` `./ait git commit` `` | bare name → exempt |
| `background_work_roadmap.md:168` | `` `ait git commit` `` | bare name → exempt |
| `issue_type_vocabulary_duplication.md:156` | `` `./ait git commit` `` | bare name → exempt |
| `planning.md:209` | two spans joined by the word "and" | bare name → exempt |
| `risk-mitigation-followup.md:398` | `` `./ait git add <f> && ./ait git commit` `` | carries arguments → **flagged** |
| `aitask-revert:382` | `` `./ait git add <p> && ./ait git commit -m "…"` `` | **flagged** |
| `CLAUDE.md:234` | `` `./ait git commit -m "…"` `` | **flagged** |

An allowlist would be worse here: exempting `shell_conventions.md` wholesale to
silence a noun would blind the guard to a bad worked example in the very
document that teaches the rule. A third `MD_ALLOWLIST=()` is still declared,
empty, with the same "the bar is high" comment as `ALLOWLIST`.

**Two false-negative holes a naive line-level rule would leave open** — both
found by stress-testing the design, both must be closed:

- **Segment, don't line.** `./ait git add -- <p> && ./ait git commit -m "x"` is
  a violation: the `--` belongs to the `add`. Split the quote-stripped candidate
  on `&&`/`||`/`;`/`|` and judge each segment that names the command. Splitting
  *after* `strip_quoted` means every separator is provably outside a string.
- **Cut a trailing comment.** `commit -m "x"  # remember to use -- for a
  pathspec` otherwise reads as scoped. Require leading whitespace before the `#`
  so a URL fragment survives.

**Machinery: reuse, with one pure extraction.** `AIT_GIT_COMMIT_RE` (its leading
character class already rejects `portrait git commit`), `SCOPED_RE` and
`strip_quoted` are reused **verbatim**, so the three seams can never disagree
about what counts as "inside a string". The one change to existing code is
splitting the decision half out of `is_scoped` so it can be applied to a single
segment:

```bash
bare_is_scoped() {                    # takes ALREADY-stripped text
    case "$1" in *\"*|*\'*) return 1 ;; esac   # fail closed
    [[ "$1" =~ $SCOPED_RE ]]
}
is_scoped() { bare_is_scoped "$(strip_quoted "$1")"; }
```

Land that extraction **on its own first** and confirm the existing `neg_count`
is still exactly `6` with every existing assertion green — the shell seams must
be behaviourally unchanged.

`JOIN_AWK` is **not** reused: markdown needs fence state to know when a trailing
`\` is a continuation at all, plus a second join for backtick spans that wrap.
Cross-reference both in comments.

**Cure 2 needs no code.** A line reading
`./.aitask-scripts/aitask_task_commit.sh -m "…" <paths>` contains no
`ait git commit` and never becomes a candidate. Assert that with a negative
fixture rather than assuming it.

**`task_git commit` is deliberately NOT matched in markdown** — it is a bash
function with no `PATH` entry, so no markdown instruction can ask an agent to
run it. Same reasoning the header already gives for excluding `*.py`.

**Fails closed on:** unbalanced quoting; a backtick span still open after four
forward lines; a file ending inside a fence; a command written with no backticks
at all; and a Jinja `{% %}` control tag on the same candidate, where the `--`
could be conditional.

**Documented boundary** (header, in its existing voice): a prose instruction
reading only "then run `./ait git commit`", with no arguments, is invisible —
bounded on three sides (fence bodies, any argument, any `&&` all defeat the
exemption). `planning.md:209` and `issue_type_vocabulary_duplication.md:156` sit
in that hole by choice and are fixed by hand in Phase 4. Rendered variants and
goldens are not seen, because flagging a generated copy double-reports one
defect.

Invariants restated for review:

**Controls** — plant the markdown fixtures in `$TMP/md/`, a *sibling* of the
existing `$TMP/.aitask-scripts/`. The shell scan never descends there and the
markdown enumerator never sees the `.sh` fixtures, so the two populations are
isolated by construction — which is what makes the two count pins independent.
Name them `md_*` so the existing `grep -c 'aitask_'` pin stays exactly `6`.

*(Matcher controls. The enumerator controls — including the excluded
`website/`, `README.md` and rendered-dir fixtures — are listed with the scope
assertions above.)*

Flagged: unscoped command in a fence · `&&`-joined span where only the `add`
carries `--` · plain list-item span with `-m` · span inside a ```markdown fence ·
span wrapping across two prose lines (and reported at its *opening* line) · a
lone bare command name **inside a fence** (the mention rule is prose-only) ·
`add` then `commit` on two fence lines (line-scoped, not block-scoped) ·
`-m "title -- annotation"` with no real pathspec · trailing
`# … use -- for a pathspec` · a command with no backticks at all · unbalanced
quote · a `.j2` file.

Not flagged: `-- <path>` in a fence and inline · `add <p> && commit -m "x" -- <p>`
(the converse of the `&&` trap — the segmenter must not over-flag the correct
shape) · `aitask_task_commit.sh …` alone and after an `&&` · prose quoting the
bad shape to forbid it · a bare noun mention with no `./` prefix ·
`task_git commit` in a fence · `portrait git commit` · a `#`-commented fence
line.

Plus the **allowlist-independence** assertions the existing seams carry: a
synthetic `MD_ALLOWLIST` entry suppresses only the markdown seam and leaves both
shell seams guarded in the same file.

**Sequencing within Phase 5** (which, per the pre-phase, runs *before* the
Phase 1-4 edits — all of it in the uncommitted working tree):
(1) extract `bare_is_scoped`, confirm `neg_count` is still exactly `6` and every
existing assertion is green — the two shell seams must be behaviourally
unchanged; (2) add the enumerator and its two-directional scope assertions;
(3) add the matcher and fixtures, tuned against fixtures only; (4) run the whole
guard over the real, still-unconverted tree — this is the `scanner_red_proof`
step, and its diff against the measured inventory is the acceptance check for
the design. The one rule that can *create* candidates no physical line contains
is the backtick-span rejoin; it is narrowed to spans already containing
`ait git` and fails closed, but step 4 is where that gets believed or fixed.

### Phase 6 — regenerate

```bash
./.aitask-scripts/aitask_skill_verify.sh
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done
```

Then regenerate goldens per
`aidocs/framework/skill_authoring_conventions.md` → "Regenerate goldens after any
`.md.j2` or closure edit": `tests/golden/procs/task-workflow/` (23 hits) and
`tests/golden/skills/{aitask-pickrem,aitask-revert,aitask-wrap}/` (32 hits).
**Review the golden diff** — it must contain the conversions and nothing else.

Goldens and the source edits land in the **same commit**.

### Post-phase (risk mitigations)

**`foreign_staged_control`** — control family A from p1728, applied to the
instruction layer. In a scratch repo: stage a foreign file, run one converted
site's command **verbatim** as an agent would, then assert the foreign file is
absent from the resulting commit *and* still staged. Establish its discriminating
power first by running it against the pre-conversion command and requiring it to
fail. This is what proves the conversion changed behaviour rather than only prose.

## Verification

Run each, and read the *last* line of the Python suite for its verdict:

1. `bash tests/test_no_unscoped_task_commit.sh` — passes, with both count pins
   (the existing `6` for the shell fixtures, a new one for the markdown
   fixtures), the two-directional scope assertions, and the allowlist-independence
   assertions. Its non-vacuity is established by the `scanner_red_proof`
   pre-phase — the same file, observed failing on the pre-conversion tree — not
   by a committed red test. Attach the saved failure output and the
   `git worktree` replay recipe to the Final Implementation Notes.
2. `bash tests/test_skill_render_task_workflow.sh`,
   `test_skill_render_aitask_pickrem.sh`, `..._aitask_revert.sh`,
   `..._aitask_wrap.sh` — golden equality.
3. `bash tests/test_skill_verify.sh`, `bash tests/test_skill_dispatch_contract.sh`.
4. `bash tests/test_agent_instructions.sh` — the assembler still works. It runs
   on mock fixtures, so it does **not** prove real-repo seed↔mirror parity;
   verify Phase 3 by diffing the changed snippet directly across
   `seed/aitasks_agent_instructions.seed.md`, `AGENTS.md`,
   `.codex/instructions.md` and `.opencode/instructions.md`.
5. `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_task_commit.sh`
   → empty output.
6. `bash tests/run_all_python_tests.sh` (verdict is the last line;
   `set -o pipefail` if piping).
7. `cd website && python3 check_links.py --build`.
8. The `foreign_staged_control` post-phase above.
9. `git show --stat HEAD` — the committed path list must match the intended edit
   set exactly. Nineteen sessions share this worktree and one has ten files
   dirty; commit with `git commit -- <paths>`, never a bare `git commit`.

## Verification of scope, before starting

Line numbers above are from the sources as of this plan; re-derive with
`for f in $(git ls-files '.claude/skills/**'); do … grep -Hn "ait git commit" …`
before editing, and diff the old-vs-new counts taken at the same instant rather
than trusting the absolute numbers.

## Risk

### Code-health risk: low
- The new markdown scan could be **vacuous** — a scanner that matches nothing passes forever, and a red proof run with a *throwaway* matcher would falsely certify the committed one · severity: medium · → mitigation: inline pre-phase scanner_red_proof
- The scan could **overreach** into human-facing documentation (`website/`, `README`, changelogs), failing the repo on text outside its stated subject — and a scope rule split between a real-tree pathspec and a fixture-tree filter would make the exclusion assertions vacuous on the fixture side · severity: medium · → mitigation: None (addressed in the plan body — one default-deny `md_in_scope` predicate, called by both listers and asserted from both, Phase 5)
- `aitask_task_commit.sh` emits `SKIPPED:unknown:<path>` **per path and keeps going**, so a converted site can exit 0 with `COMMITTED:` while silently omitting a requested file · severity: medium · → mitigation: None (addressed in the plan body — the outcome note requires reading the whole output plus the exit status, and every site declares which paths are required, Phase 1)
- Converting a site changes its **failure semantics**: the helper's exit 2 ("nothing to commit") replaces the `2>/dev/null || true` idiom at two sites, so an instruction that reads a non-zero status as failure would stop a workflow that used to continue · severity: medium · → mitigation: None (addressed in the plan body — every converted block carries the explicit outcome-parse note, Phase 1)
- The scan could **over-flag** a future doc that legitimately names the command, blocking the repo · severity: low · → mitigation: None (addressed in the plan body — the mention rule plus its negative controls, Phase 5)
- Wide file count (28+), but every edit is instruction prose; the only executable changes are one test file and five permission-config files · severity: low · → mitigation: None

### Goal-achievement risk: low
- The task body named 12 sites; the sweep found 31 in the Claude sources alone, so an implementation that trusts the task's list would leave two-thirds of the defect in place · severity: medium · → mitigation: None (addressed in the plan body — the measured inventory, plus required re-derivation before editing)
- `aitask_task_commit.sh` is missing from all five permission touchpoints; if that is skipped, every converted site prompts for permission and blocks outright under a headless profile · severity: medium · → mitigation: None (addressed in the plan body — Phase 0 lands first, with an audit-helper-whitelist empty-output verification step)
- The conversion could change prose without changing behaviour · severity: medium · → mitigation: inline post-phase foreign_staged_control
- Skipping the rendered-variant / golden regeneration would leave the render tests red for the next session · severity: low · → mitigation: None (addressed in the plan body — Phase 6 plus verification step 2)

### Planned mitigations
- timing: pre-phase | name: scanner_red_proof | type: test | priority: high | effort: low | inline_risk: low | added_complexity: medium | addresses: vacuous markdown scan | desc: build Phase 5 complete but uncommitted BEFORE any site edit, observe the shipping guard fail on the pre-conversion tree naming the measured inventory, then convert and commit both together; record a git-worktree replay recipe so the proof is re-runnable
- timing: post-phase | name: foreign_staged_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: conversion changes prose but not behaviour | desc: scratch-repo control — a foreign staged file must be absent from a converted site's commit and still staged; establish its discriminating power against the pre-conversion command first

## Concurrency note

This repo has ~19 live sessions. At planning time a concurrent session (t1725_2)
has `lib/task_utils.sh`, nine `.aitask-scripts/aitask_*.sh` writers and two
tests dirty, plus an untracked `tests/test_task_data_writer_guard.sh`. **This
task touches none of those files** — its edit set is markdown, one test file,
and five permission-touchpoint configs. Commit only the paths this task wrote
(`git commit -- <paths>`, never a bare `git commit`), and verify with
`git show --stat HEAD` that the path list matches the intent. `main` also
advanced mid-planning (t1745 landed), so re-derive line numbers before editing.

## Follow-ups to record (not done here)

- The sibling hazard this task does **not** close: `aitask-add-model` and
  `aitask-refresh-code-models` also run **plain** `git add seed/… && git commit`
  on `main`. That is the same index-wide shape on a different index, out of this
  task's stated scope (`./ait git` on the task-data branch).
