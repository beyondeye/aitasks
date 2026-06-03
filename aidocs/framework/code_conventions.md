# Code Conventions

Rules for code authoring in the aitasks framework. **Language-agnostic** —
the rules below apply equally to bash, Python, and any other language used in
the project. (Shell-specific portability quirks live in
`aidocs/framework/sed_macos_issues.md`; general shell style — shebang, `set -euo
pipefail`, error helpers — lives in `aidocs/framework/shell_conventions.md`.)

## Source-trace comments for help text condensed from other files

When a constant or dict holds user-facing help/summary text **condensed** from
another canonical file (agent prompt templates, JSON schemas, external docs),
include source-code comments at the data site naming the canonical origin
(file path + relevant section/heading) for each entry.

Archived plans and tasks are not surfaced when a future contributor opens the
source file; the "where did this description come from?" answer must live in
the code so the next person editing the help text can verify and re-derive it
without spelunking through git history or `aitasks/`.

Example (Python):
```python
# Source: .aitask-scripts/brainstorm/templates/explorer.md
# I/O contract from "## Input" + "## Output" sections.
"explore": { ... }
```

Example (bash):
```bash
# Source: .aitask-scripts/lib/profile_keys.md — "default_email" section
help_default_email="Email to use when claiming a task..."
```

If the dict/constant as a whole derives from a single canonical file or
directory, add a top-of-block comment naming that location plus per-entry
comments naming the section backing each entry. Apply only when the
help/summary is a condensation of authoritative content elsewhere — not for
inline help written from scratch.
