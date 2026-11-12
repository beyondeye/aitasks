---
Task: t2286_fix_chatlink_invite_permission_integer.md
Base branch: main
Output branch: main
---

# t2286 — Fix the chatlink invite permission integer and four stale statements

## Context

t2258_4 audited the Tasks workflow pages, checked every moved fact against the code, and found five
upstream defects. The worst one: the Discord invite URL's `permissions=397552863296` lacks View
Channels (bit 10) and Attach Files (bit 15). It also grants unrelated voice and moderation rights
(bits 17–27, 31). A bot invited with the URL that the wizard's own fix hint prints can then fail the
wizard's permissions check. The other four are documentation or comment drift.

**Decision (asked and answered):** the invite requests **only the ten required permissions**, not
Manage Messages. Nothing in chatlink calls `delete_message`, so least privilege applies. The value
is `395137109056`, and real `discord.Permissions(**{ten: True}).value` gives the same number.
A bot invited this way gets the live check's existing informational WARN for the optional
`manage_messages` permission. That is unchanged behaviour, and the WARN already says "documented as
drop-if-not-needed".

All work happens on the current branch (`main`); profile `fast` creates no worktree.

## Steps

### 1. Compute the invite integer from the required set — `.aitask-scripts/chatlink/live_check.py`

- After `OPTIONAL_BOT_PERMISSIONS`, add a bit table covering every name in both tuples (Discord API
  bit positions; the module stays discord-import-free):
  ```python
  #: Discord permission bit positions for the names above (module stays
  #: discord-import-free; tests cross-check against discord.Permissions).
  _PERMISSION_BITS = {
      "add_reactions": 6, "view_channel": 10, "send_messages": 11,
      "manage_messages": 13, "embed_links": 14, "attach_files": 15,
      "read_message_history": 16, "manage_threads": 34,
      "create_public_threads": 35, "create_private_threads": 36,
      "send_messages_in_threads": 38,
  }
  #: Invite-URL ``permissions=`` value: exactly REQUIRED_BOT_PERMISSIONS
  #: (Manage Messages is optional and deliberately not requested).
  INVITE_PERMISSIONS = sum(1 << _PERMISSION_BITS[n] for n in REQUIRED_BOT_PERMISSIONS)
  ```
- `_INVITE_URL_TMPL`: replace the literal with `f"&permissions={INVITE_PERMISSIONS}"`. Keep `{cid}`
  as the `.format` placeholder (write it `{{cid}}` inside the f-string, or concatenate a plain string
  so `.format(cid=…)` keeps working).
- Update the comment above `REQUIRED_BOT_PERMISSIONS` so it points at `INVITE_PERMISSIONS` and both
  docs pages.

### 2. Docs: the new integer and the permission lists

- `aidocs/chat/discord_bot_setup.md` step 5: change the URL to `permissions=395137109056`. Move
  Manage Messages out of the minimum list into a separate note: optional, not requested by the
  invite, add 8192 (giving `395137117248`) only when an integration needs to delete other users'
  messages. The "decimal value encodes this set" sentence names `INVITE_PERMISSIONS` in
  `live_check.py` as the source.
- `website/content/docs/workflows/bug-report-intake.md` step 3.4: change the URL to
  `permissions=395137109056`. The ten-permission list there is already correct.

### 3. Tests — `tests/test_chatlink_wizard.sh`

- Line ~510: the existing check becomes `"permissions=395137109056"`, a literal pin.
- New checks, next to the permission tests:
  - `INVITE_PERMISSIONS == 395137109056`, and decoding its set bits gives exactly
    `{_PERMISSION_BITS[n] for n in REQUIRED_BOT_PERMISSIONS}`. This catches a required name added
    without a matching bit.
  - **Independent oracle, in a separate interpreter.** This test process asserts
    `"discord" not in sys.modules` (lines ~352 and ~560, the second one *after* the permission
    tests), so the SDK must never be imported here. Run the probe and the comparison in a child
    process: `subprocess.run([sys.executable, "-c", <script>, <names-csv>], capture_output=True)`.
    The child does `import discord` and prints
    `discord.Permissions(**{n: True for n in names}).value`, or exits with a distinct code when
    `discord` is missing. The parent compares the printed value with `INVITE_PERMISSIONS`, and prints
    a visible SKIP line when the child reported discord unavailable. Neither the probe nor the oracle
    imports the code under test. Add an `assert "discord" not in sys.modules` right after this check
    so the isolation is proven at the point of use.
  - **Docs-drift guard:** both doc files contain `permissions=<INVITE_PERMISSIONS>`, and neither
    contains `397552863296`.

### 4. Seed — `seed/chatlink_config.yaml`

Add a commented `sandbox_env_passthrough` block in a new `# --- Sandbox credentials ---` section,
written in the existing seed comment style:
```yaml
# --- Sandbox credentials --------------------------------------------------
# Environment-variable NAMES (never values) the gateway copies from its own
# environment into each sandbox. The agent CLI in the sandbox has no other
# credentials, so a session cannot run until this names the variable holding
# the agent's API key. Names must match [A-Z][A-Z0-9_]* (max 64 chars); a
# listed variable unset at launch is skipped and logged. Never list the bot
# token or git credentials here.
#sandbox_env_passthrough:
#  - ANTHROPIC_API_KEY
```
(The repo's own `aitasks/metadata/chatlink_config.yaml` is an older instance copy, not the seed.
It is out of scope.)

### 5. Stale comments

- `.aitask-scripts/aitask_create.sh` ~2029: replace "only invoked from the --batch --commit paths"
  with "invoked after a successful commit — from the --batch --commit paths and from
  `finalize_draft`".
- `.aitask-scripts/chatlink/daemon.py` lines 8–9: change the docstring order to "config → yaml →
  intake ref → token (the shared preflight engine's cheap checks), then the agent-command check".
  That matches `serve()`.

### 6. Doc row — `website/content/docs/commands/codeagent.md:179`

The `--headless` row becomes: "Run `claudecode batch-review` non-interactively (adds `--print`).
Required for `explore-relay`, `relations` and `obsolescence`, which run only headless and refuse
without it. No effect on any other operation. Without it, `batch-review` runs interactively, since
Claude Code bills headless print mode at a higher per-token rate."

**Shared-file hazard:** this file carries another session's uncommitted hunk at line 173 (the Codex
question-server wording, most likely in-flight t2281). Hunk-only staging does **not** protect it:
`git commit -o -- <paths>` commits the named paths' *working-tree* contents, and a plain index
commit would also sweep the shared index's other staged entries (`A .aitask-scripts/aitask_questions/…`).
The commit is therefore gated (see **Commit**).

## Verification

- `bash tests/test_chatlink_wizard.sh` passes, including the new checks.
- `bash tests/test_chatlink_config.sh` passes (the seed is still valid YAML when uncommented).
  A one-off check: load the seed with the key uncommented through `chatlink.config` and confirm
  `sandbox_env_passthrough == ["ANTHROPIC_API_KEY"]`.
- `shellcheck .aitask-scripts/aitask_create.sh` (only a comment changed).
- `python3 -c` import of `chatlink.daemon` / `chatlink.live_check` works, and `_invite_hint` prints a
  URL containing `395137109056`.
- `cd website && python3 check_links.py --build` (two content pages were edited).
- Active code, seed and docs only. Historical records (task files, plans, archives) legitimately keep
  the old value, and so does the regression test's own negative assertion in
  `tests/test_chatlink_wizard.sh`, which names the literal on purpose:
  `grep -rn 397552863296 .aitask-scripts seed aidocs/chat website/content` → no hits;
  `grep -rn 397552863296 tests` → exactly the one docs-drift assertion line.

## Commit

Build the path allowlist from my own edit record, never from `git diff --name-only`:
`live_check.py`, `discord_bot_setup.md`, `bug-report-intake.md`, `test_chatlink_wizard.sh`,
`seed/chatlink_config.yaml`, `aitask_create.sh`, `daemon.py`, plus `codeagent.md` only when the
gate below allows it.

1. **Gate codeagent.md on ownership of its whole diff.** Immediately before committing, run
   `git diff HEAD -- website/content/docs/commands/codeagent.md`.
   - **Only my line-179 hunk present** (the other session has committed its change) → include the
     file in the allowlist.
   - **The foreign hunk is still present** → do not include the file and do not stage any part of
     it. Ask the user (`AskUserQuestion`): "Re-check now" (after the other session commits) or
     "Commit the rest; leave the codeagent.md row uncommitted". With the second choice, send
     `./ait note` to the owning task (t2281 if confirmed; otherwise ask the user to name it) saying
     the line-179 edit is in the working tree and rides in with that task's commit of the file, and
     record this in the plan's Final Implementation Notes.
2. Before committing, take `git diff HEAD --stat -- <allowlist>` and confirm every line is mine.
3. Commit with `git commit -o -m "bug: Fix chatlink invite permission integer and stale docs (t2286)" -- <allowlist>`.
   `-o` commits exactly these paths whatever else the shared index holds. No `git add`, no bare
   `git reset`, no temporary-index machinery.
4. Afterwards, `git show --stat HEAD` must list exactly the allowlist, and
   `git status --porcelain -- <allowlist>` must be empty.

Then Step 9 (Post-Implementation): archival via the workflow.

## Risk

### Code-health risk: low
None identified. The changes are a constant derived from an existing tuple, comments, a seed
comment block and doc text. The one shared-file hazard (codeagent.md, which carries another session's
hunk) is handled by the ownership gate in **Commit**. The discord oracle runs in a child interpreter,
so the test's existing no-SDK-import guards stay meaningful.

### Goal-achievement risk: low
None identified. The integer is confirmed independently by `discord.Permissions`, and the new test
pins code and both docs to it, so this drift cannot recur silently.
