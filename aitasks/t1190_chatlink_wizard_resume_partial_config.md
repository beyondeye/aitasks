---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [chatlink, tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-20 18:40
updated_at: 2026-07-21 12:46
boardidx: 10
---

## Problem

The `ait chatlink` configuration wizard keeps **all** of its state in a single
in-memory dict. If the user stops mid-configuration (Escape / Cancel / Back out
of step 1, or the TUI is closed), every value entered in that session is lost.
On the next launch the wizard restarts at step 1 pre-filled from the last
**saved** config — an edit flow, not a resume flow. A user who was halfway
through a fresh setup starts over from nothing.

## Current behaviour (as explored)

- `.aitask-scripts/chatlink/wizard.py` — 7 `ModalScreen` steps, sequence in
  `_STEPS` (~:697); `start_wizard()` (~:672) builds the one `state` dict that
  every screen mutates in place. That dict is the only carrier between steps.
- Pinned contract at `wizard.py:10-11`: "Files are written ONLY at the summary
  step; Back/Escape/Cancel before that abort cleanly with zero writes."
  Asserted by `tests/test_chatlink_tui.sh:277-278` ("abort mid-wizard: zero
  writes") and `tests/test_chatlink_wizard.sh:208` (no stray tmp files).
- `initial_state()` (`wizard.py:97-122`) pre-fills from the existing saved
  config when `seams.config_path.exists()`, else from `ChatlinkConfig()`
  defaults. `tests/test_chatlink_tui.sh:302-308` asserts "wizard restarts at
  intake".
- Final writes: config → `aitasks/metadata/chatlink_config.yaml` via
  `config_write.write_config` (`config_write.py:109`, atomic mkstemp +
  `os.replace`, merge-never-drop with a `DELETE` sentinel); bot token →
  `aitasks/metadata/chatlink_sessions/bot_token` via `paths.write_token`
  (`paths.py:93`), gitignored, dir 0700 / file 0600.

## Goal

Persist a **draft** of the in-progress wizard state so an interrupted session
can be resumed, and offer that resume explicitly on re-entry.

## Design notes / constraints

- **The pinned zero-writes contract must be revisited deliberately, not
  silently.** Adding a draft write breaks the letter of `wizard.py:10-11` and
  the two tests above. Either amend the contract to "no writes to the *config
  file or token* before the summary step; drafts are written to the gitignored
  sessions dir" and update the docstring + both tests in the same change, or
  reject the draft approach. Do not leave the contract text untrue.
- **The token must never enter the draft.** `state["token"]`
  (`wizard.py:121`) holds the plaintext secret in the same dict as everything
  else; a draft writer that serialises the whole dict creates a second secret
  store. Exclude the key explicitly and add a test that greps the draft file
  for the token value.
- **Reuse the in-tree draft-writer precedent** rather than inventing one:
  `.aitask-scripts/chatlink/sessions_store.py` already does atomic `*.tmp` +
  `os.replace` JSON records under the same gitignored `chatlink_sessions/`
  directory (readers skip `*.tmp`). That directory is the natural home for a
  draft file.
- **Resume must be an explicit, visible choice**, not an implicit silent
  pre-fill — otherwise the user cannot tell whether they are looking at saved
  config or stale abandoned input. Show which step the draft stopped at and
  offer resume / start-fresh-from-saved-config. `brainstorm_app.py:4913-5160`
  is a UX precedent for a pause/resume confirm-and-apply op.
- **Draft lifecycle:** decide and test when the draft is cleared — at minimum
  on a successful save at step 7, and on an explicit "start fresh". Consider
  staleness (a draft written against a config that has since changed on disk).
- The gate ledger (`.aitask-scripts/lib/gate_ledger.py`) + the `aitask-resume`
  skill are the repo's canonical durable-checkpoint / resume-UX idiom — worth
  reading for shape, though the storage substrate here should be the sessions
  dir, not task markdown.

## Coordination

`t1186` (chatlink wizard allowlist / live pickers, status Implementing) is
reworking step 2 and notes the step ordering may change. Any draft format that
records "which step we stopped at" must not hard-code the current 7-step
numbering, or must be reconciled with t1186 before landing.

## Acceptance criteria

- Interrupting the wizard mid-configuration and relaunching offers to resume
  with the previously entered values restored.
- Declining resume starts from the saved config exactly as today.
- The bot token is provably absent from any persisted draft.
- The wizard's write-contract docstring and the affected tests
  (`tests/test_chatlink_tui.sh`, `tests/test_chatlink_wizard.sh`) are updated
  to state the new, true contract.
- The config file and token file are still written only at the summary step.
