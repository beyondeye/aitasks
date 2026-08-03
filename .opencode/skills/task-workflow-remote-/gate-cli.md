# Gate CLI Contract (`aitask_gate.sh`)

One reference for how workflow call-sites interact with the gate CLI, so no
call-site needs per-call parsing instructions. Two verb shapes exist:

## Decision verbs — branch on the EXIT CODE, never parse output

| Verb | Exit 0 | Exit 1 |
|------|--------|--------|
| `active <task-id> <gate>` | gate is in the task's **enforced active set** | not active |
| `has-gates-field <task-id>` | the `gates:` key is present (even `[]`) | absent |
| `should-self-record <task-id> <gate>` | workflow should self-record the gate | orchestrator records it — skip |
| `recorded-pass <task-id> <gate>` | the gate's **current recorded run** is `pass` | anything else — absent, `fail`, `skip`, `pending`, `running`, `error` |

All four are pure bash (always available — no python-availability ambiguity).
Usage errors `die` with a nonzero exit and a message on stderr.

`recorded-pass` is the odd one out on *what it reads*: the other three ask about
the task's declared / enforced gate **set**; `recorded-pass` asks about the
**recorded ledger** — what the workflow actually witnessed. Its strict `== pass`
predicate mirrors `resume-point`, **not** the `{pass, skip}` satisfaction rule
`archive-ready` uses: a `skip` means "not applicable", which is not an approval.
It degrades to exit 1 ("not recorded"), which is the safe direction for both of
its consumers — see `plan-approved-stop.md` and `task-abort.md`.

The **enforced active set** is the validated `active_gates` tuple when present
and intact, else the raw `gates:` field (declared intent). Validation covers
the digest halves checkable without a profile: a stale (edited `gates:`) or
corrupt (hand-edited values) tuple is ignored — fail-closed to declared intent.

## Action verbs — run once, parse ONE status line

| Verb | Output (single line) |
|------|----------------------|
| `materialize-active <task-id> --profile <file>` | `MATERIALIZED:<csv>` \| `MATERIALIZED:(empty)` \| `NOOP:unchanged` |

`materialize-active` computes `resolve(task gates:, profile default_gates) ∩
profile rendered set` and persists the four-field tuple (`active_gates`,
`active_gates_filtered`, `active_gates_profile`, `active_gates_digest`) in one
atomic write plus a path-scoped commit. It hard-fails (nonzero, nothing
written) without a readable profile or compute backend — the raw-`gates:`
fallback then governs. Idempotent: unchanged inputs → `NOOP:unchanged`, zero
file diff, no commit.

## Introspection verbs — display, not decisions

| Verb | Shows |
|------|-------|
| `list <task-id>` | the DECLARED set (`gates:` intent) + registry metadata |
| `active-gates-status <task-id> --profile <file>` | first line `ABSENT` \| `FRESH` \| `STALE:<stamped>-><current>`; then the stored tuple as `ACTIVE:`/`FILTERED:`/`PROFILE:` lines |
| `effective-gates <task-id> [--profile <file>]` | the pre-ceiling resolve (task `gates:` else profile `default_gates`), one per line — debug only |

`list` = declared intent; `active-gates-status` = enforced set + freshness.
Never branch workflow behavior on introspection output — use the decision
verbs above.
