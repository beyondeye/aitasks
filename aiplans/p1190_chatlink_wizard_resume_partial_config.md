---
Task: t1190_chatlink_wizard_resume_partial_config.md
Worktree: (none — current branch, profile 'fast')
Branch: main
Base branch: main
---

# t1190 — chatlink wizard: persist draft + explicit resume

## Context

The `ait chatlink` config wizard keeps all state in one in-memory dict threaded
through 7 ModalScreens; interrupting mid-setup (Escape/Cancel/TUI kill) loses
everything, and relaunch restarts at step 1 pre-filled only from the last
*saved* config. This task persists a **draft** of the non-secret in-progress
state to the gitignored sessions dir on every step transition, and offers an
**explicit resume / start-fresh choice** on the next launch. The pinned
"zero writes" contract (wizard.py:15-18) is deliberately amended — config and
token files are still written only at the summary step; drafts are a separate,
token-free artifact.

Verified baseline (post-t1186_4, commit 976dc4ea2 — tree clean):
- `wizard.py` (1267 lines): `_STEPS` tuple at :1266 is the single source of
  step order/numbering; `initial_state(seams)` :193-222 (19 keys, `token` the
  only secret, init `None`); driver `start_wizard` :1228-1258 with `show(idx)`
  closure — the step index lives only there; `SummaryScreen._do_save`
  :1142-1170 is the only config/token write site; sentinels BACK/NEXT/DONE
  :56-59; `_ReplaceConfirmScreen` :1022-1065 is the modal-confirm template.
- `sessions_store.py` :216-228: atomic write precedent (pid-suffixed `.tmp` +
  `os.replace`, best-effort chmod 0600). **Gotcha:** `chatlink_app.py` :158
  roots its `SessionsStore` at `paths.sessions_dir()` itself, and
  `list_ids()` :241-250 globs `*.json` (excluding only `watch_cursors.json`)
  — a draft JSON there would surface as a bogus session row unless excluded.
- `paths.py`: `sessions_dir()` :66-68 = `aitasks/metadata/chatlink_sessions`
  (gitignored via `.aitask-data/.gitignore:17`, 0700 via `ensure_secure_dir`).
- Tests: `test_chatlink_tui.sh` (Textual Pilot, monkeypatches
  `paths.project_root` at :229; abort/zero-writes block :309-331; "wizard
  restarts at intake" :333-341; `goto_allowlist` helper :609); 
  `test_chatlink_wizard.sh` (headless, textual-free import guard :36-40,
  stray-tmp check :208-210).

## Design decisions

1. **Single draft-write site: the `handle()` callback in `start_wizard`.**
   Screens commit values into `state` only via `_accept()`/`_before_back()`
   before dismissing, so on NEXT/BACK the dict is complete. Writing on every
   transition is what survives a TUI kill; no write needed on abort (state
   unchanged since last transition). Draft I/O is best-effort (`try/except`) —
   a failing draft write never blocks the wizard.
2. **Token excluded by fail-closed allowlist.** `DRAFT_STATE_KEYS` — an
   explicit tuple of the 18 non-secret `initial_state` keys (mirrors the
   `build_edits` never-`**state` discipline). NOT derived from `build_edits`
   output (it emits the non-JSON `DELETE` sentinel and re-nests
   `intake_channel`). A drift-guard test pins
   `set(DRAFT_STATE_KEYS) == set(initial_state(...)) - {"token"}`.
   `load_draft` filters through the same allowlist, so a tampered draft cannot
   inject `token`/`_fetched` into live state.
3. **Step identity = `step_name` string** (each screen's class attr; all 7
   unique), never an index — resume maps it through the current `_STEPS`;
   unknown name falls back to step 0. Survives t1186-style reorders.
4. **Token-step cap on resume.** Token is never drafted. Two loss modes:
   (a) fresh setup, no token on disk — Summary renders `(missing!)` but
   `_do_save` still writes the config and skips the token → broken bot;
   (b) an OLD token exists on disk and the user had typed a REPLACEMENT
   token before the TUI died — the replacement is unrecoverable, and an
   uncapped resume would silently keep the old token. So the draft records
   a non-secret boolean `token_entered` (`bool(state["token"])` at draft
   time — never the value), and resume lands at
   `_STEPS.index(TokenScreen)` whenever
   `recorded_idx > token_idx and (token_entered or
   seams.token_reader() is None)`.
5. **Lifecycle:** draft deleted in `_do_save()` on the fully-successful path
   (covers "saved then killed TUI without Close") and on "Start fresh";
   kept on abort and on Escape from the resume offer. Staleness surfaced via
   a config-file sha256 fingerprint mismatch warning; never auto-deleted.
6. **No new seams:** draft path derives from `paths.sessions_dir()`; the TUI
   tests' `paths.project_root` monkeypatch redirects it transitively (same as
   `write_token`). Headless tests use an explicit `path=` kwarg.

## Step 1 — New module `.aitask-scripts/chatlink/wizard_draft.py` (~110 lines)

Textual-free; imports stdlib + `chatlink.paths` only.

- Constants: `DRAFT_FILENAME = "wizard_draft.json"`, `DRAFT_VERSION = 1`,
  `DRAFT_STATE_KEYS` (the 18 keys: provider, workspace_id, conversation_id,
  thread_id, allowed_user_ids, allowed_role_ids, denied_user_ids,
  denied_role_ids, user_authorization_mode, role_authorization_mode,
  deny_message_mode, repo_name, max_concurrent_sandboxes,
  intake_rate_per_user_per_hour, sandbox_memory, sandbox_cpus, sandbox_pids,
  sandbox_wall_clock_s).
- `draft_path() -> Path` — `paths.sessions_dir() / DRAFT_FILENAME`.
- `config_fingerprint(config_path: Path) -> str | None` — sha256 hex of file
  bytes; `None` if missing/unreadable.
- `save_draft(step_name, state, fingerprint, *, path=None)` —
  `ensure_secure_dir(parent)`; payload
  `{"version": 1, "saved_at": <utc iso>, "step_name": ...,
  "token_entered": bool(state.get("token")),
  "config_fingerprint": ..., "state": {k: state[k] for k in DRAFT_STATE_KEYS
  if k in state}}`; write via pid-suffixed `.tmp` + best-effort
  `chmod(0o600)` + `os.replace` (sessions_store discipline).
  `token_entered` is metadata about the SECRET's existence, never its value.
- `load_draft(*, path=None) -> dict | None` — fail-closed: `None` on missing
  file, parse error, non-dict, version mismatch, non-str `step_name`,
  non-dict `state`, **or any invalid state value** (a tampered/stale draft
  must not inject bad values past the screens that would normally validate
  them — resume can jump straight to later steps/Summary). Per-key
  validation table (reusing `chatlink.config` constants):
  - `provider`, `workspace_id`, `conversation_id`, `thread_id`,
    `repo_name` → `isinstance(v, str)`
  - `allowed_user_ids`, `allowed_role_ids`, `denied_user_ids`,
    `denied_role_ids` → list of str
  - `user_authorization_mode`, `role_authorization_mode` →
    in `config.AUTHORIZATION_MODES`
  - `deny_message_mode` → in `config.DENY_MESSAGE_MODES`
  - `max_concurrent_sandboxes`, `intake_rate_per_user_per_hour`,
    `sandbox_cpus`, `sandbox_pids`, `sandbox_wall_clock_s` →
    `isinstance(v, int) and not isinstance(v, bool)` and within the
    matching `config.RANGE_*` tuple
  - `sandbox_memory` → str matching `config.SANDBOX_MEMORY_RE`
  A key absent from the draft is fine (falls back to `initial_state`);
  a present-but-invalid value rejects the WHOLE draft (matches chatlink's
  fail-closed corrupt-record stance in `reconcile.py`/`sessions_store.py`).
  On success returns `{"saved_at", "step_name", "token_entered" (coerced
  via bool), "config_fingerprint", "state"}` with `state` filtered to
  `DRAFT_STATE_KEYS`.
- `clear_draft(*, path=None)` — `unlink(missing_ok=True)`, idempotent.

Module docstring pins the token-hygiene contract (draft NEVER contains the
token; allowlist + drift test).

## Step 2 — `sessions_store.py`: exclude the draft from record listing

In `list_ids()` (:246-250) add `and p.name != "wizard_draft.json"` beside the
`watch_cursors.json` exclusion, with a short comment (the TUI's store roots at
the sessions dir where the draft lives; the daemon's store roots at a
subdir). Use the literal name (comment referencing
`wizard_draft.DRAFT_FILENAME`) to avoid a new import in the daemon-side
module.

## Step 3 — `wizard.py`

a) **Docstring amendment** (:15-18) — replace the zero-writes bullet with:
   the config file and token file are written ONLY at the summary step;
   Back/Escape/Cancel never touch either; a resumable token-free draft
   (`chatlink.wizard_draft.DRAFT_STATE_KEYS`) is written to the gitignored
   sessions dir on every step transition; next launch offers
   resume/start-fresh; draft deleted on successful save or "Start fresh".
   Tag the amendment `(t1190)`.

b) **Import** (:53-54): add `wizard_draft` to the relative import list.

c) **`_resume_index(step_name, token_entered, seams) -> int`** (above
   `start_wizard`): index of the matching `cls.step_name` in `_STEPS`, else
   0; cap at `token_idx = _STEPS.index(TokenScreen)` when
   `idx > token_idx and (token_entered or seams.token_reader() is None)`.
   Docstring explains both loss modes: no-token-on-disk → broken bot, and
   typed-replacement-token lost → old token silently kept.

d) **`_ResumeDraftScreen(ModalScreen)`** (next to `_ReplaceConfirmScreen`,
   copying its shape: escape binding, `#wizard_dialog`/`#wizard_buttons`
   CSS with `$primary` border). `__init__(self, draft, stale: bool)`. Label:
   saved_at, "stopped at: <step_name>", and when `stale` a warning that the
   saved config changed after the draft was written. Buttons:
   "Resume draft" (variant success, `#btn_wiz_resume`) → `dismiss(True)`;
   "Start fresh" (`#btn_wiz_fresh`) → `dismiss(False)`; escape →
   `dismiss(None)` (abort wizard, draft kept). No app-level keybindings
   added.

e) **`start_wizard` rewrite** (:1228-1258): compute
   `fingerprint = wizard_draft.config_fingerprint(seams.config_path)` once;
   add `save_draft_for(idx)` best-effort helper writing
   `_STEPS[idx].step_name` + state; in `handle()`, call it before
   `show(idx-1)` / `show(idx+1)`. If `load_draft()` is None → `show(0)` as
   today. Else push `_ResumeDraftScreen(draft, stale=fingerprint mismatch)`
   with callback: `None` → return (abort); `False` → `clear_draft()`
   (best-effort) + `show(0)`; `True` → `state.update(draft["state"])` +
   `show(_resume_index(draft["step_name"], draft["token_entered"], seams))`.

f) **`SummaryScreen._do_save`**: insert best-effort
   `wizard_draft.clear_draft()` immediately BEFORE
   `self._render_save_state()` at :1167. That line is reached only when the
   save fully succeeded per `_saved()` semantics — config written AND
   (token written OR no new token entered). This covers ALL successful save
   paths: new-token write, keep-existing-token (`state["token"]` falsy →
   token block skipped, `_token_written` stays False), and the
   failure-aware Save retry once it finally succeeds. Do NOT key the clear
   on `_token_written`.

No changes to `chatlink_app.py` or `WizardSeams`.

## Step 4 — `tests/test_chatlink_wizard.sh` (headless)

- Import guard (:36-40): add `chatlink.wizard_draft` import and keep the
  no-textual assert covering it.
- New section after the stray-tmp check (:208-210, unchanged): draft
  round-trip against `tmp/"sessions"/"wizard_draft.json"`:
  - save with a full state dict PLUS `"token": "sekrit-token-xyz"` and
    `"_fetched": {...}`; assert raw file text contains neither
    `sekrit-token-xyz` nor `_fetched` (the acceptance-criteria grep);
  - `load_draft` round-trips step_name/fingerprint/token_entered/all 18
    keys; token absent from loaded state; unknown keys dropped;
  - no `*.tmp` left beside the draft; mode 0600;
  - `load_draft` → None for missing file, corrupt JSON, wrong version;
  - **fail-closed value validation**: drafts with (a) a string where
    `allowed_user_ids` should be a list, (b)
    `user_authorization_mode: "bogus"`, (c) `sandbox_cpus: 999` (out of
    `RANGE_SANDBOX_CPUS`), (d) `sandbox_memory: "lots"` → each loads as
    `None`; a draft with a key absent still loads;
  - `clear_draft` idempotent (twice, no error);
  - `config_fingerprint`: None for missing path, changes with content;
  - **`SessionsStore.list_ids()` excludes the draft**: root a
    `SessionsStore` at a tmp dir containing `wizard_draft.json` (via
    `save_draft(path=...)`) plus one real `save()`d session record; assert
    `list_ids()` returns only the record id (direct regression guard for
    the Step 2 exclusion — the round-trip tests alone would not catch its
    loss).
- Header comment: add wizard_draft to covered modules; note the amended
  contract.

## Step 5 — `tests/test_chatlink_tui.sh` (Pilot)

- Header comment (:9-17): amend the abort item to the new contract wording.
- Imports (~:60): `from chatlink import wizard_draft`; `import json` if absent.
- **Abort block (:309-331)** — extend: on TokenScreen type
  `secret-token-123` into `#wiz_token`, enter → assert `LiveCheckScreen`,
  then escape. Keep both zero-write checks. Add: draft file exists at
  `wizard_draft.draft_path()`; raw text does NOT contain `secret-token-123`;
  parsed draft has `state["workspace_id"] == "111"`,
  `step_name == wiz.LiveCheckScreen.step_name`, and
  `token_entered is True` (typed token recorded as metadata only).
- **New resume-accept block** (between abort and full-walk): fresh
  `make_wizard_app()`, `w` → assert `_ResumeDraftScreen`; click
  `#btn_wiz_resume` → assert landed screen is `TokenScreen` (**cap
  exercised**: draft recorded live-check with `token_entered` true and no
  token on disk — both cap conditions hold) and
  `state["workspace_id"] == "111"` restored; escape → draft still exists
  (abort never deletes).
- **Full-walk block (:333-341)**: now expects `_ResumeDraftScreen` first;
  click `#btn_wiz_fresh`; then the existing "wizard restarts at intake"
  check plus: draft file deleted. After the successful save later in the
  walk (~:509): assert draft file absent ("successful save deletes the
  draft").
- **Draft hygiene for later blocks**: add best-effort
  `wizard_draft.clear_draft()` at the top of `goto_allowlist` (:609) and at
  the start of the app4 block, with a comment warning future blocks that
  escape-mid-wizard leaves a draft.
- **Drift guard** (once, near the wizard blocks):
  `set(wizard_draft.DRAFT_STATE_KEYS) == set(wiz.initial_state(
  wiz.resolve_seams(wiz.WizardSeams(config_path=<tmp missing path>)))) -
  {"token"}`.

## Verification

```bash
bash tests/test_chatlink_wizard.sh     # headless: draft module + guards
bash tests/test_chatlink_tui.sh        # Pilot: abort→draft→resume/fresh flows
shellcheck is N/A (Python change); run both suites to PASS/FAIL summary
```
Manual (deferred to live verification): `./ait chatlink`, `w`, fill 2 steps,
kill the TUI, relaunch → resume offer; also confirm no bogus session row
appears in the sessions table while a draft exists.

## Step 9 (Post-Implementation) reference

Standard workflow Step 9: no worktree/branch (current-branch profile), gate
orchestrator run (`./ait gates run 1190` — `risk_evaluated` is machine-typed
and recorded by the orchestrator), archive via
`./.aitask-scripts/aitask_archive.sh 1190`.

## Risk

### Code-health risk: medium
- Shared-tmp TUI suite ordering: any block that escapes mid-wizard now leaves
  a draft that makes the next `w` press open the resume modal, breaking later
  blocks nondeterministically · severity: medium · → mitigation: in-plan
  (clear_draft in `goto_allowlist` + app4 preamble + warning comment)
- Draft JSON at the sessions-dir root is globbed by
  `SessionsStore.list_ids()` and would render as a bogus/corrupt session row
  in the TUI table · severity: medium · → mitigation: in-plan (Step 2
  exclusion + headless assertion)
- `DRAFT_STATE_KEYS` drifting from `initial_state` when future wizard keys
  are added (new fields silently missing from drafts) · severity: low ·
  → mitigation: in-plan (drift-guard test)

- A tampered/stale draft injecting invalid values for allowed keys past the
  screens that would normally validate them (resume jumps ahead) could
  crash screens or write an invalid config · severity: medium ·
  → mitigation: in-plan (fail-closed per-key value validation in
  `load_draft` + four negative-control tests)

### Goal-achievement risk: low
- Silent loss of a typed replacement token: with an old token on disk, an
  uncapped resume past TokenScreen would keep the old token without the
  user noticing · severity: medium · → mitigation: in-plan (`token_entered`
  draft metadata + cap rule + Pilot test exercising the cap)
- Resume-cap correctness depends on `seams.token_reader()` reflecting
  on-disk token state; a seam mismatch could resume past a missing token ·
  severity: low · → mitigation: in-plan (Pilot test exercises the cap on a
  tokenless tree; `token_entered` cap fires independently of the reader)
