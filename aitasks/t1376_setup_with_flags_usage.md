---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [bash_scripts, documentation]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-08-03 09:42
updated_at: 2026-08-03 09:42
---

## Origin

Risk-mitigation ("after") follow-up for t1354_3, created at Step 8d after implementation landed.

## Risk addressed

> This adds a **third** opt-in `--with-*` tier while none of the existing two
> appears in any help output, compounding a discoverability gap rather than
> introducing one · severity: low

## Goal

Add a `usage()` to `.aitask-scripts/aitask_setup.sh` enumerating the three
opt-in dependency tiers, and surface it via `ait setup --help`.

## Current state (verified at t1354_3 plan time, re-verify before implementing)

- `aitask_setup.sh` has **no** `usage()` function and prints no flag list.
  It parses `--with-pypy`, `--with-chat` and (as of t1354_3) `--with-dev` in
  `main()`, then silently passes anything else through in `args`.
- `ait:98` documents the subcommand as only `setup    Install dependencies`.
- Consequence: there is no way to discover any of the three flags from the CLI.
  They are documented only in prose — `website/content/docs/commands/setup-install.md`
  (pypy + the two tiers), `aidocs/chat/*_setup.md` (chat), and
  `website/content/docs/installation/pypy.md`.

t1354_3 deliberately scoped this out: it is a UX change spanning three flags,
not one, and folding it into a performance task would have widened that task's
blast radius into the install flow's argument parsing.

## Suggested approach

- Add a `usage()` printing the three tiers with one line each on what they
  install and who needs them:
  - `--with-pypy` — PyPy 3.11 venv, speeds up `ait board`
  - `--with-chat` — chat adapter SDKs (discord.py, slack-bolt, slack-sdk)
  - `--with-dev`  — pytest + pytest-xdist, parallel lane for the Python test suite
- Wire `--help` / `-h` in the `main()` case block. Note the block currently
  collects unknown args into `args` and passes them on, so `--help` must be
  intercepted explicitly.
- Mention that each tier is remembered after first opt-in and revalidated on
  later plain `ait setup` runs — and, for `--with-dev`, that the marker governs
  provisioning only (`AIT_TEST_PARALLEL=0` is the execution opt-out). That
  distinction is documented in `CLAUDE.md` and is easy to get wrong.
- Consider whether `ait:98`'s one-line description should point at
  `ait setup --help`.
- Keep `shellcheck .aitask-scripts/aitask_setup.sh` clean (compare findings
  against the pre-change baseline rather than requiring zero — the file has
  pre-existing informational findings).
