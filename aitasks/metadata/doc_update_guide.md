# Doc-Update Guide — aitasks

Configured doc-update spec for **this** repository. When a code change lands,
use this to decide whether user-facing docs need updating, which files, and
how to write them. This is aitasks's own config, so real paths are used here.

## Doc landscape

Two doc surfaces:

1. **User-facing site** — `website/content/docs/`, a Hugo/Docsy site. Sections:
   - `concepts/` — mental-model / architecture explanations.
   - `workflows/` — task-oriented how-tos (one per workflow).
   - `skills/` — the skills / custom-command reference.
   - `tuis/` — one page per interactive TUI.
   - `commands/` — the `ait` CLI subcommand reference.
   - `installation/` — install, per-agent setup, known issues.
   - `getting-started.md`, `overview.md`, `_index.md` — landing/intro pages.
2. **Design docs** — `aidocs/` (e.g. `aidocs/framework/`, `aidocs/applink/`).
   Internal engineering references, not the marketing site. Update these when
   the change alters framework internals a maintainer needs documented, but
   they are **not** the user-facing surface the gate primarily targets.

## Change-kind → doc-area map

| Code change | Doc to update |
|---|---|
| TUI change (`.aitask-scripts/…` — board, monitor, minimonitor, codebrowser, settings, brainstorm) | matching `website/content/docs/tuis/<name>.md` (or its dir) |
| Skill / custom-command change (`.claude/skills/…`, ported `.agents/`, `.opencode/`) | `website/content/docs/skills/` |
| `ait` subcommand added/changed (`.aitask-scripts/aitask_*.sh` behavior, new flags) | `website/content/docs/commands/` |
| Workflow behavior change (task/plan/gate/review flow) | matching `website/content/docs/workflows/<name>.md` |
| Concept / architecture change | matching `website/content/docs/concepts/<name>.md` |
| New frontmatter field / install-flow / framework internal | relevant `aidocs/framework/…` design doc |
| NEW `website/content/docs/workflows/*.md` page | the page **plus** a hand-curated bullet in `website/content/docs/workflows/_index.md` |

### Known footgun: the workflows `_index.md` body list

The sidebar/navigation auto-builds from the files, but the **body** of
`website/content/docs/workflows/_index.md` is a hand-curated grouped list
(Tasks / Parallel / Review & Quality / Git). Adding a new workflows page
requires **manually** adding its bullet to the correct group in that index
body. This is easy to miss because the sidebar looks complete without it.

## Writing conventions (distilled from `aidocs/framework/`)

Sourced from `aidocs/framework/documentation_conventions.md` and
`adding_a_new_codeagent.md` §23b. Apply all of these:

- **Current-state-only.** User-facing docs describe the current state. No
  "previously…", "this used to be…", "this corrects an earlier…". State correct
  behavior positively; version history lives in git and PR descriptions, not in
  doc bodies. (Internal `aiplans/` files may record deviations; user-facing docs
  may not.)
- **"Delete X, integrate into Y" = redirect cross-refs now.** Read Y first. If Y
  already covers the content, "integrate" collapses to updating cross-references
  from X to Y; defer wholesale prose migration as a follow-up and call out the
  redirects explicitly (they break silently).
- **"Autonomous", not "auto-execution".** In manual-verification prose (the
  whole-checklist offer, the per-item `auto` verb, the `manual_verification_mode`
  knob), use "autonomous" — an AI agent runs the mechanically-checkable items and
  leaves human-only checks (visual rendering, UX) for the interactive loop. Keep
  literal code/config tokens verbatim (`auto`, `autonomous`,
  `autonomous_with_plan`, `…_manual_verification_auto.md`, `## Execution Log`).
  Canonical heading: `## Autonomous verification`.
- **Genericize the supported-agent set in blurb prose.** In marketing / intro /
  in-paragraph examples, do NOT enumerate all agents — write "Claude Code and all
  other supported coding agents" (or, when an anchor carries weight, "Claude Code,
  Codex, and all other supported coding agents"). Keep literal enumerations ONLY
  where the list IS the documentation: the CLI mapping table in
  `commands/codeagent.md`, per-agent install blocks in `installation/`, per-agent
  known-issue sections, and model-self-detection lists.
- **Generic example project names.** User-facing docs use invented placeholder
  names (frontend / backend / the docs site), never the author's real repos
  (never "aitasks" / "aitasks_mobile" in examples).
- **Never say "sister" repo.** Use "cross-repo" or "linked repo/project", and
  scrub any existing "sister" wording on pages you touch.

## TUI list caveat: diffviewer is transitional

The `diffviewer` TUI is transitional (to be folded into `brainstorm`). Omit it
from user-facing TUI lists and `docs/tuis/`. Document these TUIs: **board,
monitor, minimonitor, codebrowser, settings, brainstorm**. (`diffviewer` stays
switchable in the framework code but is not documented on the site.)

## Terminal outcomes

- **PASS** — doc work performed, or docs inspected and already correct.
- **SKIP** — evaluated; no doc-relevant user-facing surface needed review/update
  (e.g. a pure refactor, test, or internal-only change).
- **FAIL** — docs needed updating but the user rejected the proposed update.
