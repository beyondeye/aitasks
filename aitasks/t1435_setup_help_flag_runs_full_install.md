---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [development]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1432
created_at: 2026-08-05 17:38
updated_at: 2026-08-11 16:56
---

## Origin

Spawned from t1432 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:3676-3684` — no `--help` / `-h` handler; the
  flag loop's `*)` catch-all swallows them into `args`, so `ait setup --help`
  runs the **full guided install** (package-manager installs, venv creation,
  git branch initialization) instead of printing help. This contradicts the
  dispatcher's own advice at `ait:105` ("Run 'ait <command> --help' for more
  information on a command") and its documented `-h, --help` option at
  `ait:102`.

## Diagnostic context

Surfaced while documenting the opt-in dev tier for t1432 (gap 5). The task
needed to know whether `ait setup --help` documents `--with-dev`, so that the
website page and the CLI help would not drift. It does not — `aitask_setup.sh`
has no help handler at all (`grep -nE '\-\-help|"-h"|show_help|usage\(\)'`
returns nothing but two unrelated function-header `# Usage:` comments at
`:1277` and `:1317`).

The failure mode is worse than a missing help text: because the flag falls
through to the catch-all rather than erroring, a user who types `ait setup
--help` to find out what the command does triggers the very side effects they
were trying to understand first.

t1432 recorded this as out of scope — it is a CLI behavior change, not a
documentation gap — and the website page now documents `--with-dev` on
`docs/commands/setup-install.md` and `docs/development/_index.md` instead.

## Scope note

35 of 118 `.aitask-scripts/aitask_*.sh` scripts have no `--help` handling, but
most are internal helpers never invoked directly by a user. `setup` is the
notable case because it **is** a documented dispatcher subcommand and its
failure mode is actively harmful rather than merely unhelpful. Scope this task
to `setup` first; widening it to the other dispatcher-exposed commands is a
judgement call for the implementer, not an assumed requirement.

## Suggested fix

Add a `--help|-h)` case to the `main()` flag loop in `aitask_setup.sh` that
prints a usage block and `exit 0` **before** any setup side effects run. The
usage text should cover the three opt-in tiers (`--with-pypy`, `--with-chat`,
`--with-dev`). Per `aidocs/framework/code_conventions.md`, help text condensed
from another canonical file needs a source-trace comment pointing at the
authority.
