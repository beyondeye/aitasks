# Doc-Update Guide (generic default)

You are updating a project's documentation because a code change just landed.
This guide is the **method** — the project layers its own doc roots and
conventions on top (see `project_config.yaml` `doc_update:`, below). Follow the
steps in order. Do not invent docs the project does not have.

## 1. Read the project's doc-update config first

Open `project_config.yaml` and look for a `doc_update:` block:

- `guide:` — a pointer to the project's OWN configured doc-update spec. Read it.
  It names the real doc roots, the change-kind → doc-area map, and the local
  writing conventions. It **overrides and specializes** this generic method.
- `extra_guides:` — optional additional guides (style rules, per-area specs).
  Read each one and apply it.

If there is no `doc_update:` block, fall back to this generic method and infer
the doc landscape from the repository (a docs site directory, per-component
reference pages, a top-level README, etc.).

## 2. Identify which doc areas the change affects

Map the **kind** of code change to the doc area that documents it. Infer the
mapping from the project's configured guide and from the shape of the existing
docs. Typical kinds:

- A user-facing component gained/changed behavior → that component's reference
  page (e.g. a "frontend" widget change → the frontend widget's page).
- A command / subcommand / API surface changed → the command or API reference.
- A workflow, concept, or how-to changed → the matching workflow/concept page.
- A brand-new user-facing surface → a NEW page **and** any index/landing entry
  that lists that section's pages (see step 3).
- A purely internal change (refactor, test, build) with no user-visible surface
  → likely **no** user-facing doc update.

## 3. Infer the concrete update from the shape of existing docs

Match the existing structure — do not impose a new one:

- If each component has its own reference page, update **that component's** page,
  in the same shape/section order the other component pages use.
- If a section has a **hand-curated index or landing page** listing its pages,
  a NEW page also needs its index entry added by hand — the sidebar/navigation
  may auto-build, but a manually written index body will not. Check for this;
  it is a common silent omission.
- Reuse the terminology, heading style, and example conventions already present.

## 4. Writing discipline

- Describe the **current state only**. No version history in doc bodies — no
  "previously…", "this used to…", "this now replaces…". State correct behavior
  positively. History belongs in git and change descriptions.
- Keep example names generic and invented (e.g. "frontend" / "backend" / "the
  docs site"). Do not use real private repo or project names.
- Never call a linked repository a "sister" repo — say "linked repo/project".
- **Confirm proposed changes with the user before applying them.** Summarize
  which files you would touch and the gist of each edit; apply only on approval.

## 5. Record the terminal outcome

The doc-update gate skill records one outcome:

- **PASS** — doc work was performed, OR the docs were inspected and are already
  correct for this change.
- **SKIP** — you evaluated the change and there is no doc-relevant surface that
  needed review or update.
- **FAIL** — docs needed updating but the user rejected the proposed update.
