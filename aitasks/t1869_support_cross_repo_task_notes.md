---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [framework, skills, documentation]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-23 14:42
updated_at: 2026-09-23 14:44
---

## Context

Task notes are the framework's durable, advisory channel for giving an existing
task context it needs without turning that context into new work. They are often
a better fit for interacting with a task in a foreign repository than creating a
new task there or directly editing that task's description, metadata, or workflow
state. The note still appends a structured `## Inbox` entry to the target task,
but does so through the dedicated locked, path-scoped, untrusted-input channel.

Cross-repository task identity and command routing already use logical project
names from the project registry. `ait note` does not currently expose that path:
normal targets and `--from` senders are local-only. The migration-only
`--claimed-from <project>#<id>` form can preserve a historical cross-repository
sender claim, but it is not a normal send operation and is deliberately
unverified.

## Goal

Add first-class cross-repository task-note sending and acknowledgement using the
existing logical-project registry and cross-repository command conventions.
Make the new grammar strictly additive: every existing in-repository `ait note`
and `/aitask-note` invocation, output contract, provenance rule, and behavior
must remain valid and unchanged.

## Requirements

### 1. Additive CLI grammar and target routing

- Add an explicit cross-repository target form consistent with existing aitasks
  commands, preferably `--project <logical-name>` for both note writes and
  `ait note read`. Do not reinterpret or overload existing positional task IDs.
- Preserve all current local forms exactly, including `--text`, `--file -`,
  `--with-live`, `--migrate`, and read-receipt grammar. Omitting the new option
  must execute the existing local path with the same validation and output.
- Resolve the logical name through the project registry and execute against the
  target project's own installed note helper so task discovery, ledger locking,
  task-data branch behavior, scoped commits, and pushes belong to the target
  repository.
- Missing, stale, ambiguous, or incompatible project registrations must fail
  before mutation with a clear structured outcome. Never auto-clone a project.
- Keep local and cross-repository task identity distinct: equal numeric task IDs
  in two projects are not the same task.

### 2. Define honest cross-repository provenance

- Store an unambiguous project-qualified sender identity for a normal
  cross-repository note; a bare `from=t42` must never be allowed to appear as if
  it referred to t42 in the target repository.
- Validate both the target project and the claimed source project/task using the
  strongest evidence available from the registry and local checkout.
- Preserve the existing meaning of `from_verified=yes`: write it only when the
  implementation can prove that this process owns the claimed sender task's
  lock. If that proof cannot be made across the repository boundary, omit the
  field; never write `no`, and never weaken the local proof.
- Decide and document how the source project's logical name is selected. Reject
  an unregistered or ambiguously registered source rather than inventing a
  portable identity. Any explicit source-project option must be additive and
  must be checked against the actual calling repository.
- Update the Inbox parser/union/validation contract as needed to accept both
  legacy local sender values and the new qualified normal-send form. Existing
  notes and migration records must remain readable and mergeable.
- Keep migration semantics separate: `--migrate --claimed-from` remains a way to
  preserve historical, unverified provenance and must not become the normal
  cross-repository send path.

### 3. Preserve durability and live-lane semantics

- Append under the target repository's note ledger lock, then perform the same
  target-path-scoped task-data commit and best-effort push used by local notes.
- Preserve the existing idempotency/reporting contract around commit failures:
  an id-bearing `NOTE_APPENDED_UNCOMMITTED` is terminal and must not invite a
  retry that duplicates the note.
- `--with-live` must remain durable-first. Resolve a live endpoint only after the
  target-repository note commit succeeds. Cross-host delivery is not required;
  an unavailable live lane remains a successful durable send and must use the
  existing `LIVE_NONE` / `LIVE_ERROR` meanings.
- Do not introduce direct pane driving or any new automatic action by the target
  agent. Cross-repository notes remain untrusted advisory input.

### 4. Support cross-repository acknowledgement

- Extend `ait note read` with the same target-project routing so notes can be
  acknowledged without manually changing into the foreign checkout.
- Preserve current receipt validation, rollback-on-commit-failure behavior,
  unread derivation, `--by` rules, and output codes.
- Ensure listing/surfacing in the target repository treats the new sender form
  safely and displays enough project qualification to avoid ambiguity.

### 5. Update the shipped code-agent guidance

Update every source-of-truth surface that teaches agents how to send notes,
including at minimum:

- `.claude/skills/aitask-note/SKILL.md`, the authoritative installed
  `/aitask-note` procedure, plus any generated or agent-specific wrapper that
  must change;
- `seed/aitasks_agent_instructions.seed.md`, which installs the shared
  `AGENTS.md` / agent-instruction note-sending section, and its contract tests;
- related task-workflow, QA, and review call sites only where their guidance
  needs to distinguish local from foreign-repository recipients.

The agent procedure must teach:

- when a cross-repository note is appropriate: context for work that already
  exists, especially when direct edits in a foreign repository would be too
  intrusive;
- when to create a task instead because the message is itself new work;
- how to select and validate target/source project identity;
- that cross-repository provenance may be unverified and is still only a claim;
- that a durable append is success even when live delivery is unavailable; and
- that the agent must report outcomes without claiming the note was read.

Headless explicit-target usage must remain possible. Do not make existing local
callers answer a new prompt or supply a project name.

### 6. Update end-user and design documentation

Update the note-sending documentation comprehensively, including:

- `website/content/docs/commands/note.md` for the new write/read grammar,
  validation, output, examples, and failure behavior;
- `website/content/docs/skills/aitask-note.md` and
  `website/content/docs/workflows/task-notes.md` for agent and workflow usage;
- the relevant task-notes and cross-repository concept/reference pages, while
  linking rather than duplicating the registry and provenance definitions;
- `aidocs/framework/task_note_mailbox.md` and live-endpoint/design material where
  the storage, provenance, merge, or durable-first contracts change.

State clearly that a note is a structured modification to the target task's
Inbox, not a hidden side channel, and that it does not modify the task's
requirements, state, or authority.

### 7. Verification and regression coverage

Add focused tests using isolated source and target repositories. Cover at least:

- all existing local write, migration, live, receipt, and output-contract tests
  unchanged or with equivalent assertions;
- a cross-repository write landing only in the selected target task and being
  committed through that target's task-data mechanism;
- project-qualified sender rendering and parsing, including the same numeric ID
  existing in both repositories;
- verified versus deliberately unverified provenance behavior;
- missing/stale/ambiguous registrations and missing target/source tasks failing
  without mutation;
- cross-repository read receipts and rollback on commit failure;
- durable success with no cross-host live endpoint, plus any same-host live path
  the design supports;
- installed agent-instruction and `/aitask-note` documentation contracts; and
- website link/build checks for all changed documentation.

## Non-goals

- Automatically cloning, fetching, or discovering an unregistered repository.
- Treating a note as an instruction or automatically changing the recipient's
  plan, task body, metadata, or status.
- Replacing cross-repository dependencies, paired planning, or proper follow-up
  tasks when the content is itself work.
- Guaranteeing live delivery across hosts.

## Acceptance criteria

- A caller can send and acknowledge a durable note in a registered foreign
  project without changing directories, using additive project-qualified
  grammar.
- Existing in-repository commands and agent callers require no changes and retain
  their current syntax, validation, storage, output, live-lane, and receipt
  behavior.
- The stored sender identity cannot be confused with a same-numbered task in the
  target project, and verification is never claimed without proof.
- The target repository owns the lock, mutation, scoped commit, and push; failure
  paths neither mutate the wrong repository nor encourage duplicate notes.
- The installed `/aitask-note` procedure and shared agent instructions teach the
  new cross-repository path and preserve the note-versus-task boundary.
- End-user, workflow, concept, and design documentation accurately describe the
  feature and pass the repository's documentation checks.
