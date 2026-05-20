# Skill / Workflow Authoring Conventions

Specialist guidance for authoring or modifying skills under `.claude/skills/`,
`.agents/skills/`, `.gemini/skills/`, `.gemini/commands/`, `.opencode/skills/`,
or `.opencode/commands/`. CLAUDE.md carries only the source-of-truth pointer
and the `aitask_skill_verify.sh` reminder; the rules below apply when actually
editing skill files.

## Verifying `.j2` templates before commit

When you add or modify a `.j2` authoring template (`.claude/skills/<skill>/SKILL.md.j2`)
or any per-agent stub surface (`.claude/skills/<skill>/SKILL.md`,
`.agents/skills/<skill>/SKILL.md`, `.gemini/commands/<skill>.toml`,
`.opencode/commands/<skill>.md`), run before committing:

```bash
./.aitask-scripts/aitask_skill_verify.sh
```

This renders every `.j2` against `default.yaml` for all 4 supported agents
(claude, codex, gemini, opencode), walks each authoring template's dep closure
to verify every transitive `.md` reference resolves and renders cleanly, and
asserts each stub surface contains the canonical markers from
`aidocs/stub-skill-pattern.md` (resolver call, render call, trailing-hyphen
Read path). The script exits non-zero on any render error, broken closure
reference, or stub-pattern violation; address every failure before committing.

If no `.j2` templates exist yet, the command prints
`aitask_skill_verify.sh: no .j2 templates found — nothing to verify.` and
exits 0. `aitask_skill_verify.sh` writes
nothing to disk; it is safe to run anytime.

## Extract new procedures to their own file

Any new procedure added to an aitasks skill (task-workflow or sibling) goes in
its own file (`.claude/skills/<skill>/<name>.md`); the calling `SKILL.md` /
`planning.md` carries only a thin "Execute the **\<Procedure Name\>** (see
`<name>.md`) with: \<context vars\>" reference. No inlined procedure bodies; no
"either inline or extract" alternatives. The agent-specific case (e.g., Claude
Code's internal plan-file externalization) is one instance of this rule — wrap
the reference in a conditional like "If running in Claude Code, execute …. Other
agents skip this step because \<reason\>."

Inlined bodies in shared files duplicate when the procedure fires from multiple
call-sites, drift silently when the tree is ported to `.opencode/` / `.gemini/`
/ `.agents/`, and create conflict surface when multiple aitasks touch the same
SKILL.md region.

## Execution-profile keys vs. guard variables — pick the right lever

- **Profile keys** (e.g., `qa_mode: ask|never`, `post_plan_action`) let users
  opt in/out of a procedure. Use them when a step feels overreaching.
- **Guard variables** (e.g., `feedback_collected`) are set-once-consume-once
  flags that prevent DOUBLE execution when the same procedure can be invoked
  twice via different control-flow paths. They do NOT force a single execution
  and can't be used to "remind agents to fire a prompt."

Rule of thumb: if the concern is "agents might forget to fire X", restructure
control flow (extract X to its own file, reference explicitly from SKILL.md,
make it a numbered step) and add a profile key for opt-out. If the concern is
"X might fire twice via re-entry", add a guard variable to the SKILL.md
context-variables table and check it at procedure entry.

## Context-variable pattern over template substitution engines

When templates need per-instance values like `CREW_ID` / `AGENT_NAME` (or
analogous variables), do NOT introduce a template-substitution engine that
interpolates the values at template-write time (e.g., a sed/envsubst pass added
to a helper). Instead, follow the "context-variable" pattern already used by
`task-workflow`: declare the variables once in a known file the agent reads
(e.g., `_instructions.md`, or a shared `_context_variables.md` include),
reference them as `${VARNAME}` placeholders throughout the template, and let
the agent substitute them at read time.

Agents bind variables from working memory rather than from text mangled at
write time. Adding a new substitution engine duplicates the binding mechanism,
introduces a second code path that can drift, and creates a fragile
transformation step in the script pipeline.

When a template needs per-instance values:
- First, check whether the agent already has the values available via a known
  context source (e.g., its `_instructions.md` written by an existing helper).
  If so, just reference the variables in the template and tell the agent where
  the literal values live.
- If a shared declaration is needed across multiple templates, add a small
  include file (e.g., `_context_variables.md`) and inline it via the existing
  `<!-- include: ... -->` mechanism — do NOT add a new substitution pipeline.
- Reserve write-time variable interpolation for cases where the agent genuinely
  cannot read the literal values from any context file (rare).

## SKILL.md files are re-read during execution — never overwrite an in-use one

Skill definitions on disk (`.claude/skills/<name>/SKILL.md`,
`.agents/skills/<name>/SKILL.md`, `.gemini/skills/<name>/SKILL.md`,
`.opencode/skills/<name>/SKILL.md`) are read MULTIPLE times by the agent during
a skill's execution, not just once at slash-command expansion. Any design that
mutates an in-use `SKILL.md` mid-session produces torn reads and inconsistent
behavior.

How to apply:
- Use per-profile subdirectories (each with its own stable `SKILL.md`) so
  different (skill, profile) combinations live in different files. For dynamic
  profile-driven content, render ONCE atomically (mv from tempfile) into a
  per-profile path, then dispatch via a profile-suffixed slash command (e.g.
  `/aitask-pick-fast`). The committed no-suffix `/aitask-pick` becomes a thin
  stub that resolves the active profile and dispatches.
- Skills must also be invokable from INSIDE a live agent session (typing
  `/aitask-pick 42` in Claude), where no external wrapper can intercept.
  Stub-dispatch from the skill itself is the canonical solution: the stub runs
  `aitask_skill_render.sh …` (bash), then invokes `/skill-<profile>`.
- Atomic mv from tempfile is essential for any render that lands in a skill
  discovery path.

## Use recognizable name-suffix conventions for generated artifact dirs

When a feature generates rendered artifact directories alongside authoring ones
(e.g., per-profile rendered SKILL.md variants), encode "generated" into the
directory NAME with a single recognizable suffix/prefix marker so the
`.gitignore` is one glob per agent root.

Convention for aitasks framework rendered SKILL.md dirs: **trailing hyphen**
(e.g., `aitask-pick-fast-/`); gitignore is `.claude/skills/*-/` (and same for
`.agents/skills/`, `.gemini/skills/`, `.opencode/skills/`).

Per-variant globs (`*-fast/`, `*-default/`, …) require maintenance every time
a new variant lands; the suffix convention does not. Authoring dir names must
NOT end with the marker — verify at design time.

## Profile-aware skills require a stub + `.md.j2` pair

An entry-point skill that needs to vary by execution profile MUST be authored
as two files in `.claude/skills/<skill>/`:

1. `SKILL.md` — the committed, profile-agnostic **stub** (per
   `aidocs/stub-skill-pattern.md` §3b). Resolves the active profile, calls
   `aitask_skill_render.sh`, and Read-and-follows the per-profile rendered variant.
2. `SKILL.md.j2` — the **authoring template** rendered by minijinja against the
   active profile YAML. May reference other `.md` procedures (full-path,
   sibling, or skill-relative — see `aidocs/stub-skill-pattern.md` §3i); the
   dep-walker recursively renders every reachable `.md` into the per-profile
   sibling tree, with cross-references rewritten to point at the rendered
   copies.

Profile-agnostic skills that do not vary by profile keep a single `SKILL.md`
and skip the `.j2` template entirely.

A single `SKILL.md` cannot carry profile-conditional content because the agent
re-reads it during execution; mutating it mid-session would produce torn reads
(see "SKILL.md files are re-read during execution" above). The stub +
render-on-invocation model materialises a stable per-(skill, profile) snapshot
once per invocation, then the agent reads that frozen file.

When converting a skill to be profile-aware, author the `.md.j2` template
first, then drop the canonical stub from `aidocs/stub-skill-pattern.md` §3b at
the existing `SKILL.md` path. The 3 sibling stubs (Codex `SKILL.md`, Gemini
command TOML, OpenCode command MD) follow §3c-§3d. Run
`./.aitask-scripts/aitask_skill_verify.sh` to confirm all 4 stub surfaces
render cleanly and the closure walk-check passes.

## Jinja comment conventions for profile-aware templates

Profile-aware `.md` / `.md.j2` templates accumulate nested `{% if/elif/else/endif %}`
blocks fast. Without annotations the file becomes hard to scan: `{% else %}`
gives no hint about which branch it covers, and `{% endif %}` does not name
the `{% if %}` it closes. When wrapping any profile check, mark the conditional
with three companion comments that share a short `<label>`:

1. **Separator before `{% if %}`** — placed on the **same line** as the
   `{% if %}` tag, plain `{# ... #}`. Keeping it on the same line is the only
   way to add the visual ruler without changing rendered bytes. Minijinja in
   this repo runs without `trim_blocks`/`lstrip_blocks` (see
   `.aitask-scripts/lib/skill_template.py:62-68`), so a comment on its own
   line would add a blank line to every rendered output. Whitespace-stripping
   markers (`{#- ... -#}`) over-strip — they consume the existing blank line
   before `{% if %}`.

2. **Inline comment on `{% elif %}` / `{% else %}`** — same line as the tag,
   plain `{# ... #}`. The comment states *what triggers this branch*.

3. **Inline comment on `{% endif %}`** — same line as the tag, plain
   `{# ... #}`, repeating the `<label>` so the close pairs visually with the
   separator.

The shared `---------- <label> ----------` ruler gives a uniform visual marker
across the file. `grep -nE '^\{# -+' <file>` enumerates every wrapped region
in one shot. `<label>` is typically the profile key under test
(`default_email`, `create_worktree`, `plan_preference`, …); nested blocks get
their own labels (often the inner key plus a value qualifier).

**Full nested example:**

```jinja
{# ---------- default_email ---------- #}{% if profile.default_email is defined %}
  {# ---------- default_email value ---------- #}{% if profile.default_email == "userconfig" %}
  Use the userconfig email …
  {% elif profile.default_email == "first" %}{# default_email: literal "first" #}
  Read emails.txt …
  {% else %}{# default_email: literal email address #}
  Use `{{ profile.default_email }}` directly.
  {% endif %}{# ---------- end default_email value ---------- #}
{% else %}{# default_email: key absent from profile #}
  **Profile check:** If the active profile has `default_email` set …
{% endif %}{# ---------- end default_email ---------- #}
```

**Render-neutrality requirement.** The convention is engineered so that adding
these comments to an already-wrapped template produces zero rendered-byte
change. After adding/editing comments, re-render against every committed
profile and diff against the matching golden under `tests/golden/procs/<scope>/`
— the diff must be empty before committing. A non-empty diff means a separator
was placed on its own line (adds a blank), used `{#- -#}` stripping (drops a
blank), or that whitespace control on a tag itself changed.

This convention applies to any `.md` / `.md.j2` file rendered by
`skill_template.py`, including shared procedure files under
`.claude/skills/task-workflow/`.

## Regenerate goldens after any `.md.j2` or closure edit

When you edit a `.md.j2` template OR any `.md` file in its render closure
(procedure files under `.claude/skills/task-workflow/`, sibling procedures,
includes, etc.), regenerate the affected goldens and commit them in the same
change. Skipping this step causes `tests/test_skill_render_*.sh` Test 1
(`assert_eq` against the committed golden) to fail on the next run; the
failure surfaces in CI / locally, but the template edit ships with stale
goldens until someone notices.

**The diff is the audit signal — review it, don't rubber-stamp it.** Goldens
exist precisely so the template engine cannot silently shift rendered output
(whitespace, comment placement, conditional bodies, reference-rewrite
regressions). The intended diff for a template edit should match what you
changed; an unrelated diff means a regression (canonical memory:
`feedback_golden_file_tests_for_template_engines`).

**Regenerate command** (3 profiles, `claude` render per entry-point skill):

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
TEMPLATE=".claude/skills/<skill>/SKILL.md.j2"
PROFILES_DIR="aitasks/metadata/profiles"
GOLDEN_DIR="tests/golden/skills/<skill>"

for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude \
    > "$GOLDEN_DIR/SKILL-${profile}-claude.md"
done
```

**Golden dimensionality.** Entry-point goldens are `claude`-only: the basic
stdout render applies no per-agent reference rewrites (those are a
walk-write property, covered by Test 4), so a `codex`/`gemini`/`opencode`
golden would be a byte-for-byte copy of the `claude` one. Per-agent goldens
are kept *only* for a skill whose template references `{% if agent %}` (a
gate that makes the render actually diverge per agent). When introducing
such a gate, regenerate goldens for all 4 agents in the same commit; the
per-skill **Test 1b** (agent-invariance check) will fail and remind you.

For procedure goldens under `tests/golden/procs/<scope>/` (e.g.
`task-workflow/`), the render target is the procedure `.md` file and the
agent dimension is flattened — see the loop in
`tests/test_skill_render_task_workflow.sh` for the canonical pattern. A
procedure that is also **profile-invariant** (its profile conditional is
activated by no committed profile) keeps a single canonical
`<stem>-default.md` golden plus a byte-equality invariance assertion across
the other profile renders, rather than one golden per profile.

**Enforcement.** `tests/test_skill_render_*.sh` (per entry-point skill) and
`tests/test_skill_render_task_workflow.sh` run Test 1 with `assert_eq` on
every golden. Run the relevant test after regenerating to confirm all green
before committing.

**Commit rule.** Goldens and the template edit land in the **same commit**.
A separate "regenerate goldens" follow-up commit hides intent — the reviewer
cannot tell whether the diff is the deliberate consequence of the template
edit without rediffing against the prior commit's template.

The narrower Jinja-comment render-neutrality rule above is a special case of
this rule: there the diff MUST be empty; here the diff is whatever the
template edit produced and MUST be reviewed.

## Do not route skill invocation through `claude -p "<inlined prompt>"`

`claude -p` is billed at a higher per-token rate than slash-command invocations
against an existing session. Inlining a rendered SKILL.md (often 200–400 lines)
into the prompt every invocation multiplies that cost. The wrapper's job is to
render → atomically place the rendered file at the agent's discovery path →
exec the agent with the natural slash command (`claude '/skill-name <args>'` or
invocation inside an existing session). Never pipe rendered SKILL.md content
via `-p`.

The constraint applies to all four agents (Claude, Codex, Gemini, OpenCode);
the rate-difference rationale is documented specifically for Claude.

## Post-implementation follow-up offers: cross-step state lives in the plan file

When a Step 8X-style follow-up procedure (8b upstream-defect, 8c manual-
verification, future siblings) needs cross-step state — e.g., "did diagnosis
surface an upstream defect?" — record it in a dedicated bullet of the plan
file's `## Final Implementation Notes` section, and have the follow-up
procedure read from that subsection.

Use `None` (verbatim) as the positive-assertion sentinel when nothing was
found. Do NOT add new entries to SKILL.md's "Context Requirements" table for
this kind of state. Plan-file persistence survives context resumes, stays
auditable in archived plans, and keeps the recorded finding visible even if
the user declines the follow-up offer.

## Mark workflow-defined AskUserQuestion prompts as NON-SKIPPABLE

When you add an AskUserQuestion to a SKILL.md or referenced procedure file
(`task-workflow/*.md`) whose purpose is (a) recording load-bearing data (e.g.
verified-model scores), (b) gating workflow progression (e.g. merge approval,
plan approval), or (c) surfacing a user-owned decision (e.g. create vs. skip
a follow-up task), prefix it with a `⚠️ NON-SKIPPABLE` banner that mirrors
Step 8's wording in `task-workflow/SKILL.md`.

The banner MUST explicitly enumerate what does NOT cover the prompt —
execution profiles (unless a specific key is named), auto mode / 'work without
stopping' system-injected directives, and generic user instructions to 'be
brief' or 'don't ask'. The banner MUST also enumerate the only valid opt-outs:
site-specific profile keys (or `currently: none`) and explicit user
pre-decision in chat.

Without the explicit banner, a system-injected "work without stopping"
directive can be over-applied and silently skip workflow gates, losing
follow-up tasks and verified-model ratings.

When adding a new AskUserQuestion to a workflow procedure, classify it as
either (i) a clarifying question (no banner needed; existing auto-mode/profile
shortcuts may legitimately bypass it) or (ii) a workflow gate / data-recording
prompt (banner required). When in doubt, default to (ii). Existing banners
live at `task-workflow/SKILL.md` Step 8, Step 9 merge-approval; and at the top
of `task-workflow/upstream-followup.md`, `manual-verification-followup.md`,
`satisfaction-feedback.md`.
