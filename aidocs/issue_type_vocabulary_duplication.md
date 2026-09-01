# issue_type Vocabulary Duplication

## Problem

The list of valid `issue_type` values is duplicated across **32+ files** spanning runtime config, agent-instruction mirrors, skill docs, the website, and test fixtures. Adding one new value requires touching every location to keep them consistent.

This violates the single-source-of-truth principle (see `feedback_single_source_of_truth_for_versions.md` in user memory). The runtime is validated against `aitasks/metadata/task_types.txt`, but every doc and skill that *enumerates* the values must be updated by hand or it silently drifts. Drift symptoms:

- Agent skills propose only the older subset → user sees a regression in offered types.
- Website docs lie to users about valid values.
- Test fixtures don't exercise the new value (low risk; consistency only).
- Codex/Gemini/OpenCode agents work from stale instruction mirrors.

## Enforcement (t1666)

`tests/test_docs_vocabulary_coverage.sh` now **fails** when any enumerating site
drifts from `aitasks/metadata/task_types.txt`. It drives
`tests/lib/docs_vocabulary_scan.py`, whose `SITES` table is the machine-readable
form of the checklist below — so when you add a type, run the test rather than
trusting a grep, and when you add a *site*, add it to `SITES` in the same
change. The scanner extracts the enumeration itself (not the surrounding prose),
so a site is free to explain an exclusion in words without tripping the check.

Three expected sets, all derived from `task_types.txt`:

| class | set | why |
|---|---|---|
| `FULL` | every value | the site mirrors the vocabulary |
| `NO_MV` | minus `manual_verification` | **commit types and the wrap suggestion list.** There is no `manual_verification:` commit type: such a task records its own outcome with `ait:`, and any code change a failed check triggers lands on a spawned follow-up under that follow-up's type. A wrap, likewise, always describes code changes that already exist |
| `DETECTED` | minus `manual_verification` and `enhancement` | `github_detect_type()` in `aitask_issue_import.sh` maps issue labels to bug/refactor/test/style/chore/documentation/performance and otherwise falls back to `feature`; it can emit neither of the other two |

The same test also guards the **frontmatter field table** against the writers
(see its header) — a separate dimension that lives in the same file because it
protects the same document.

## Single Source of Truth (the only file that's authoritative)

`aitasks/metadata/task_types.txt` — newline-delimited list, validated against by `.aitask-scripts/aitask_create.sh::is_valid_task_type` (via `get_valid_task_types`). The runtime accepts any value present here.

`seed/task_types.txt` is its bootstrap copy used by `ait setup` for new projects — must stay in sync.

## Add-a-Type Checklist

When adding a new `issue_type`, update **every** location below. Order: runtime first, then docs, then skills, then website, then test fixtures.

### 1. Runtime (required for the value to be accepted)

| File | What to change |
|------|----------------|
| `aitasks/metadata/task_types.txt` | Insert the new value on its own line. Commit via `./ait git`. |
| `seed/task_types.txt` | Mirror — same insertion. Commit via plain `git`. |
| `.aitask-scripts/aitask_ls.sh` | Help-text line near top: `issue_type: bug\|chore\|...` (pipe-separated). |

### 2. Agent-instruction mirrors (one CLAUDE.md, three agent mirrors)

Each has **two** lines: the YAML frontmatter sample and the commit-message-format paragraph.

| File | Sections to update |
|------|---------------------|
| `CLAUDE.md` | "Task File Format" `issue_type:` pipe-list (`FULL`) + "Commit Message Format" backtick-list (**`NO_MV`**). Hand-maintained — edit directly |
| `seed/aitasks_agent_instructions.seed.md` | Same two sections (verbatim mirror for new projects) |
| `.codex/instructions.md` | Same two sections (Codex CLI mirror) |
| `.opencode/instructions.md` | Same two sections (OpenCode mirror) |

`AGENTS.md`, `.codex/instructions.md` and `.opencode/instructions.md` are
**generated from the seed**, not hand-edited: edit
`seed/aitasks_agent_instructions.seed.md` and drive the generator (see
`aidocs/framework/aitasks_extension_points.md` §5 — never copy out of
`AGENTS.md`, which carries the shared layer only). `tests/test_agent_instructions.sh`
T25–T27 pin all three byte-for-byte against the live seed.

Note: `seed/codex_instructions.seed.md`, `seed/opencode_instructions.seed.md` are **agent-identification only** and do not list types — leave alone.

### 3. Claude Code skill files

| File | Where |
|------|-------|
| `.claude/skills/task-workflow/SKILL.md` | "Code commits MUST use ... (one of: ...)" line in the commit-conventions section — **`NO_MV`** |
| `.claude/skills/task-workflow/task-creation-batch.md` | `issue_type` row of the input parameter table |
| `.claude/skills/aitask-wrap/SKILL.md.j2` | "Suggested issue_type: One of `feature`, `bug`, ..." line in the analysis-output section — **`NO_MV`**. Edit the `.j2`, not the stub `SKILL.md` |
| `.claude/skills/aitask-docs-gap/SKILL.md` | `ISSUE_TYPE:` value list in the gather-output parsing section |
| `.claude/skills/aitask-changelog/SKILL.md` | same list, in its own gather-output parsing section |

**Rendered variants: only the `-remote-` closures are tracked.** `.gitignore`
excludes `.claude/skills/*-/`, but the `-remote-` trees are committed anyway and
therefore ship — six of their files carry an enumeration:

```
{.claude,.opencode}/skills/task-workflow-remote-/{SKILL.md,task-creation-batch.md}
.agents/skills/task-workflow-remote-codex-/{SKILL.md,task-creation-batch.md}
```

They are refreshed by `./.aitask-scripts/aitask_skill_rerender.sh <profile>`
(**it takes a profile argument** — run it for `default`, `fast` and `remote`;
the `remote` pass is the one that touches tracked files). The `-default-` /
`-fast-` variants are genuinely gitignored and never appear in a diff. The
scanner lists all six, so a source edit without a rerender fails the test.

### 3b. Goldens

Regenerate in the **same commit** as the source edit, per
`aidocs/framework/skill_authoring_conventions.md`:
`tests/golden/procs/task-workflow/{SKILL,task-creation-batch}-{default,fast,remote}.md`
and `tests/golden/skills/aitask-wrap/SKILL-{default,fast,remote}-{claude,codex}.md`.

### 4. Website (Hugo/Docsy)

| File | Where |
|------|-------|
| `website/content/docs/development/task-format.md` | `issue_type` row of the frontmatter-fields table, **and** the defaults block under "Customizing Task Types" — two independent sites in one file |
| `website/content/docs/tuis/board/reference.md` | `issue_type` row of the editable-fields table |
| `website/content/docs/tuis/board/how-to.md` | "Type:" bullet in the cycle-fields list |
| `website/content/docs/workflows/issue-tracker.md` | Auto-detection paragraph in step 1 of "The Full Cycle" — **`DETECTED`**, not the full vocabulary: it describes what `github_detect_type()` can infer from a label, so a new type belongs here only if that function learns to emit it |
| `website/content/docs/commands/task-management.md` | "Issue type" bullet in the create-task interactive flow |

### 5. Test fixtures (consistency only — current tests don't validate the new value)

17 tests synthesize a `task_types.txt` via `printf 'bug\nchore\n...' > aitasks/metadata/task_types.txt`. The grep pattern that catches them all:

```bash
grep -lF "documentation\\nfeature\\nperformance" tests/test_*.sh
```

Single-pass update:

```bash
grep -lF "documentation\\nfeature\\nperformance" tests/test_*.sh \
  | xargs sed -i 's/documentation\\nfeature\\nperformance/documentation\\n<newvalue>\\nfeature\\nperformance/g'
```

(Or, for a value placed in a different alphabetical position, adjust the literal context accordingly.)

The four `manual_verification`-suffixed fixtures use the same pattern with an additional trailing `\nmanual_verification` — the same `sed` covers both because it matches only the prefix.

### 6. Final scan

Run the guard — it is the authority, and it checks each site independently:

```bash
bash tests/test_docs_vocabulary_coverage.sh
```

The grep below remains a coarse second opinion; after all edits it should return
zero results:

```bash
grep -rEn "(bug.*feature.*chore|bug.*chore.*documentation|chore.*documentation.*feature|documentation.*feature.*performance)" \
  --include="*.md" --include="*.sh" \
  | grep -v "<newvalue>\|\.git\|CHANGELOG\|aiplans/"
```

### 7. Commit shape

Two commits — runtime data file lives on the data branch (use `./ait git`), everything else on main (plain `git`):

1. `./ait git commit` — only `aitasks/metadata/task_types.txt`. Subject: `ait: Add '<newvalue>' to task_types`.
2. `git commit` — the other 31 files. Subject: `ait: Propagate '<newvalue>' issue_type across docs, skills, and tests`.

Do **not** mix the two — `aitasks/` files cannot be committed together with code/doc files when the data branch is in use.

## Eliminating the Duplication (future work)

The right fix is a generation step that reads `aitasks/metadata/task_types.txt` once and injects the list into the doc/skill/instruction files that currently hardcode it. Sketch:

- A helper script (e.g., `.aitask-scripts/aitask_render_type_list.sh`) emits the list in the three required forms (pipe-separated, backtick-comma-separated, comma-separated plain text).
- Source files (CLAUDE.md, agent-instruction mirrors, skill docs, website pages) use HTML-comment markers like `<!-- BEGIN_ISSUE_TYPES style=pipe --> ... <!-- END_ISSUE_TYPES -->` and a build/sync step rewrites the content between them.
- A pre-commit or `ait` subcommand verifies all marked sections are in sync with `task_types.txt`.

Until that lands, the checklist above is the procedure.

## Case Study

The propagation in commit `d7a96896` ("Propagate 'enhancement' issue_type across docs, skills, and tests") touched 31 files in addition to the runtime data file. The list of paths in that commit can be used as a ground-truth reference if future grep-based discovery misses anything.
