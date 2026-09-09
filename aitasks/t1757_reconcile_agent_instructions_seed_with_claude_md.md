---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [documentation]
created_at: 2026-09-09 09:58
updated_at: 2026-09-09 09:58
---

## Context

`CLAUDE.md` (this repo's always-loaded instructions) and
`seed/aitasks_agent_instructions.seed.md` (what `ait setup` installs into every
consumer project) both describe the same framework behaviours — and they have
**drifted apart in both directions**, with nothing guarding against it.

Found while working t1705_6: an agent used `./ait note` correctly, and the
question "would an installed project's agent know how?" turned out to have a
partial answer. The framework install is otherwise fine — the seed prose is
inserted into `CLAUDE.md` / `AGENTS.md` / `.codex/instructions.md` / the
OpenCode mirror between `>>>aitasks` / `<<<aitasks` markers, the
`aitask-note` skill ships in the release tarball, and all three seed configs
pre-allow `aitask_note.sh`. The gap is purely the **content** of the shared
prose.

## Evidence (measured 2026-09-09)

Six sections exist in both files with different content:

| section | CLAUDE.md | seed |
|---|---|---|
| Sending Notes to Other Tasks | 26 non-blank lines | 30 |
| Git Operations on Task/Plan Files | 13 | 7 |
| Commit Message Format | 10 | 12 |
| Task File Format | ✓ | ✓ (differs) |
| Task Hierarchy | ✓ | ✓ (differs) |
| Folded Task Semantics | ✓ | ✓ (differs) |

Concrete divergences confirmed by grep:

- **`ait note`** — the seed omits `--with-live`, the
  `LIVE_PANE:` / `LIVE_NONE:` / `LIVE_ERROR:` result contract, and the
  "use the `/aitask-note` skill rather than composing the pieces by hand"
  steer. An installed project's agent hand-composes the call, which works, but
  it never learns the live-delivery flag exists.
- **`Manual Verification Tasks`** — present in the seed, absent from
  `CLAUDE.md`.

## Scope — this is NOT "make the two files identical"

Most of `CLAUDE.md` is deliberately repo-only: `TUI Development`,
`Reusable Helpers`, `Project Overview`, `Architecture`, `Mobile Companion`, the
`aidocs/` pointers, `Working on Skills / Custom Commands`. Those describe
developing the framework, not using it, and must NOT reach a consumer project.

The reconciliation covers only the sections describing behaviour **every**
aitasks project has. For each, decide the direction deliberately rather than
diffing mechanically:

- `CLAUDE.md` → seed: content a consumer project needs but does not get
  (the `--with-live` contract is the clear case);
- seed → `CLAUDE.md`: content this repo is missing (`Manual Verification
  Tasks`);
- neither: wording that is legitimately repo-specific inside an otherwise
  shared section.

Do not assume the seed is always the subset — the note section is *longer*
there, so at least one section has content flowing the other way.

## The durable half: a drift guard

A one-time sync will re-drift; nothing today notices when an edit to one file
should have reached the other. Add a guard so the next divergence fails a test
instead of being discovered by accident. Sketch — pick the shape at planning:

- name the shared section headings explicitly (a list in the test, the way
  `tests/test_no_lib_to_tui_import.sh` names `TUI_PACKAGES`), and
- assert some checkable relationship per section — an exact-match set for
  sections that must be verbatim, or a "these phrases must appear in both"
  pin for sections that legitimately differ in framing.

An exact-match rule for every shared section is probably too strict; decide per
section and record why in the test, since a guard that overclaims gets disabled.

## Related, but distinct

- **t1478** — setup regenerates `.codex/instructions.md` /
  `.opencode/instructions.md` only when that agent's CLI is installed, so a
  seed change can reach `AGENTS.md` alone. That is a *propagation* bug
  (seed → mirrors); this task is *content* drift (CLAUDE.md ↔ seed). They
  compound: fixing only one still leaves installed projects with stale prose.
- **t1620** — seed resolution when `seed/` was deleted at install.

## Verification

```bash
bash tests/<new drift guard>.sh          # or the python equivalent
./.aitask-scripts/aitask_setup.sh --help # setup still assembles cleanly
```

Then confirm end to end in a scratch project: run `ait setup`, and check the
`>>>aitasks` block in its `CLAUDE.md` contains the reconciled note section
including `--with-live`.
