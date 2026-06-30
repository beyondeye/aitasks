<!-- MAINTAINER: This is the shared "content → static SKILL.md" core of
     aitask-learn-skill. Direct consumer today: aitask-learn-skill/SKILL.md.
     The planned shadow spawn-learner follow-up reuses this by spawning the WHOLE
     skill (/aitask-learn-skill <pane_id>), not by reading this file. Keep it
     SOURCE-AGNOSTIC: the input is already-gathered text, regardless of whether it
     came from a file, URL, repo, or a captured tmux pane. Edits here change every
     learn path. -->

# Generate a skill from gathered content

Shared core of `aitask-learn-skill`. **Input:** `content` — the already-gathered
source text (a document, a fetched page, or a captured terminal session), plus a
short `source_label` describing where it came from (e.g. `pane %5`, a URL, a path).
**Output:** a new static skill at `.claude/skills/<name>/SKILL.md`, committed, with
its invocation path reported back.

Apply **generic** skill-authoring best practices throughout. These are NOT the
aitasks-framework-internal conventions (`aidocs/framework/skill_authoring_conventions.md`
governs framework skills — stubs, profile variants, goldens — which a user's own skill
must not adopt). By default, read the best-practices guide installed with the framework:

```
aireviewguides/aiagents/skill_authoring_best_practices.md
```

(installed by `ait setup` from `seed/reviewguides/`, so it is present in any repo where
aitasks is set up). If that file is absent, fall back to your own knowledge of good
Claude skill authoring (clear `name`/`description`, a focused single responsibility, a
scannable procedure, no inlined long sub-procedures). **The conventions source is meant
to be configurable** — a follow-up task adds a setting so a project can point this at its
own house standards; until then this default applies.

## Procedure

1. **Analyze the content.** Read `content` and work out what it actually teaches:
   the task or workflow it describes, the concrete steps/commands involved, the
   tools or files it touches, and any preconditions. For a captured terminal
   session, reconstruct the *sequence of actions the operator performed* (commands
   run, their purpose, the order), not just the raw scrollback.

2. **Multi-part selection (skip if single-procedure).** If the content holds
   **several distinct procedures** (e.g. a captured session that did two unrelated
   things, or a doc covering multiple independent how-tos), present them as a short
   numbered list and ask which to turn into a skill — `AskUserQuestion`
   (multiSelect), one option per candidate procedure plus a "the whole thing as one
   skill" option. Learn only the selected part(s). If the content is a single
   coherent procedure, skip this step.

3. **Generalization Q&A (skip if not needed).** If the selected material is
   **concrete** — hard-coded paths, specific task ids, repo names, ports, personal
   directories — decide whether the skill should generalize them. When generalization
   would help, ask the user how, with `AskUserQuestion`: which specifics become
   **parameters/placeholders** (the skill takes them as arguments or asks for them)
   versus which stay **literal** (they are intrinsic to the procedure). Keep it
   focused — one question covering the few specifics that matter. If the material is
   already general, skip this step.

4. **Name + description.** Ask the user (`AskUserQuestion`) for:
   - `name` — snake/kebab-case, unique under `.claude/skills/`. Verify it does not
     already exist (`ls .claude/skills/<name>` → must be absent); if it does, ask for
     another.
   - `description` — one clear line describing when to use the skill (house style:
     a full descriptive sentence, as in the other skills' frontmatter).
   Offer a sensible default for each, derived from the analysis, as the first option.

5. **Generate `.claude/skills/<name>/SKILL.md`.** Write a **static** skill:
   - Frontmatter: `name`, `description`, `user-invocable: true`. **No**
     `.j2`/profile/goldens/stub machinery (that is for profile-aware skills and is
     out of scope here).
   - Body: a clear, scannable structure — a short "when to use" framing, the
     **procedure** as numbered steps (the generalized commands/actions, with any
     parameters from step 3), and a brief **verification** of expected outcome.
     Preserve technical specifics (exact commands, flags, file paths that stay
     literal). Drop narration/history that does not help execution.
   - If the procedure is long or has a separable sub-flow, split that into a sibling
     `.md` the SKILL.md reads-and-follows — do **not** inline a long sub-procedure
     (authoring standards).

6. **Verify.** Run `./.aitask-scripts/aitask_skill_verify.sh`. A static skill adds no
   `.j2` templates, so it passes trivially; this confirms nothing else broke. Fix any
   reported issue before committing.

7. **Commit** the generated skill (source code → plain `git`, never `./ait git`):
   ```bash
   git add .claude/skills/<name>/
   git commit -m "feature: Add /<name> skill learned from <source_label>"
   ```

8. **Report** to the user: the new skill's path and its invocation path `/<name>`,
   a one-line summary of what it does, and (if generalized) which inputs it now
   takes as parameters.
