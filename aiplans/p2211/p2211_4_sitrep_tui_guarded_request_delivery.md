---
Task: t2211_4_sitrep_tui_guarded_request_delivery.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_1_*.md, aitasks/t2211/t2211_2_*.md, aitasks/t2211/t2211_3_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-10 10:29
---

# t2211_4 — Guarded request delivery into the sitrep agent

## Context

The sitrep TUI (t2211_1/3/8/9/10, landed) shows the store; the agentic work stays in the
sitrep agent pane beside it. This child adds the keys that **type a request into that
agent pane and submit it** (`>t c<N>`, `>q c<N> <text>`, `>w <theme>`, `>tr c<N>`, `>p`).
A live, unfrozen pane is not proof that typing is safe — a dialog would eat the Enter, a
user draft would be submitted mixed with ours, a working agent garbles input, and copy-mode
turns Enter into copy-pipe-and-cancel. Delivery is therefore three separately observed
phases: **readiness → dispatch with an acked result → mode-gated submission**. The task file
is the binding spec (phases, refusal table, result vocabulary, cases (a)–(i), a mutant per
guard). Parent plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`.

## Verification of this plan (2026-11-10, HEAD 0e17732b1)

- Gate holds: t2211_3 (706bf2f6d) and t2037_2 (3594c2798) landed; `git diff HEAD` is empty
  for `monitor_core.py`, `review_loop.py`, `minimonitor_app.py`, `helper_panes.py`,
  `status_client.py`, `sitrep_tui/`.
- Line numbers moved; current anchors: `capture_raw_tail` monitor_core L750,
  `query_pane_mode` L795, `kill_agent_run_guarded` L4278, `find_sitrep_roles` L5236,
  `RunIdentity` L5612, `RUN_IDENTITY_FORMAT` L5635; helper_panes `all_of` L215,
  `run_identity_condition` L251, `readback_state` L278; review_loop `shadow_state` L1003,
  `COMPOSER_DRAIN_SECONDS` L993, `SHADOW_SUBMIT_RETRIES` L1000, HOLD/DISARM codes L109-132;
  minimonitor `_fire_shadow_recheck` L5910, `_submit_shadow_prompt` L6011-6170.
- **Corrections to the earlier plan** (found while verifying):
  1. `p` is taken (`pick_task`). Keys in use: `q enter d l s f F j ? r x p b z P R A`.
     Request keys: **`t`** triage, **`a`** ask, **`w`** situation, **`T`** trail refresh,
     **`n`** pick advice ("what next"). All remappable (`keybinding_registry`).
  2. The TUI has **no `TmuxMonitor`** — `_tmux_seams` builds a `tmux_run`-only duck gateway.
     The dispatch is therefore module-level functions in `monitor_core` duck-typed on
     `monitor.tmux_run` / `monitor.tmux_run_input` (the `capture_raw_tail` /
     `find_sitrep_roles` style), with thin `TmuxMonitor.dispatch_text_guarded` /
     `dispatch_key_guarded` methods beside `kill_agent_run_guarded` as the spec names.
  3. **`set-buffer -- <text>` is NOT parser-free**: tmux's `cmd_parse_from_arguments`
     treats an argv element ending in `;` as a command separator (strips it; `\;` → `;`).
     A question ending in `;` would be silently changed. The text therefore goes through
     **`load-buffer -b <name> -` with the text on stdin** — it never enters any tmux parser
     (the spec's stated intent). Needs one new gateway primitive,
     `TmuxClient.run_with_input` (`set_clipboard` already does `load-buffer -w -` on stdin;
     we do NOT pass `-w`, which would push to the clipboard). The spike (step 2) records
     the `set-buffer` trailing-`;` measurement as the justification.
  4. The sitrep pane records **no launch agent string** (no `@aitask_agent` stamp exists).
     The agent key is resolved from the pane: `#{pane_current_command}` + `pane_pid` →
     `agent_keys.agent_key_from_pane` (the three-rung resolver the shadow path uses; handles
     the native Claude version-named binary). Unresolved → `refused:not_ready:unknown`.
  5. `find_sitrep_roles` can return a **name+cwd fallback** (unstamped) pane. The spec allows
     only the pane **stamped `@aitask_sitrep_root` = this root**, so delivery re-reads the
     stamp (plus frozen / dead / TUI marker) in its own identity read and refuses otherwise.
  6. (Plan review) The composer proof before each Enter is the **complete payload of the
     current composer region** matched exactly against the request, with only justified
     display wraps allowed — not a text search over the capture (see step 3).

## Steps

1. **Gate + rebase check.** Re-run `git diff HEAD --` over the files above; must be empty
   before the first edit (done at plan time; repeat at implementation start).

2. **Measurement spike (before code is final; record results in this plan under
   `## Measurement`).** Isolated server (`TMUX_TMPDIR=<scratch>`, `tmux -f /dev/null`),
   120x30, real claude 2.1.322 / codex-cli 0.167.0 / opencode 1.18.34, each in a scratch
   cwd (answer the trust prompt by hand-driven `send-keys`):
   - `set-buffer -b x -- 'a;'` and `'a\;'` → `show-buffer` (expect mangled → justifies 3.);
     `load-buffer -b x -` round-trips the case-(f) hostile string byte-exactly.
   - `load-buffer` + `paste-buffer -d -b x -t <pane>` of `>t c12` and of a 300-char
     one-line `>q` text: `shadow_state == SHADOW_BUSY`, Claude shows no `[Pasted text`,
     and `composer_payload` (step 3) reads back exactly the request.
   - **Composer payload grammar, per agent** (the evidence step 3's parser is built on):
     capture at the production extent (`capture_raw_tail`, `-S -15`) and store as new
     fixtures in `tests/sitrep_request_fixtures.py`, each with its pane width:
     (i) the short request; (ii) a request longer than the composer width that wraps at a
     word boundary; (iii) one with a token longer than the width (mid-token wrap);
     (iv) the request with user text appended after it; (v) the request already submitted
     (echoed in the transcript) with an unrelated draft in the composer. From these record
     the region delimiters (Claude: the `─` rule lines above/below the `❯` + NBSP line;
     Codex: from `› ` to the first blank line; OpenCode: the `┃` rows between the box top
     and the status row), the continuation-line indent, and the **content width** in
     columns as a function of the pane width (prefix, indent, right margin).
   - the same with an `@` in the text: does a file-suggestion popup appear that would take
     the Enter? If yes for any agent, the ask dialog refuses `@` (message says why).
   - one submit per agent of a harmless prompt ("Reply with the single word OK") after the
     0.5 s drain: post-Enter state is WORKING or READY.
   - **If any agent does not land the paste as typed composer text: stop and report to the
     user** (`AskUserQuestion`); never inline the text into an `if-shell` string.
   - An agent whose composer region cannot be delimited exactly from its captures stays
     out of `PAYLOAD_GRAMMAR_AGENTS` (refused before typing); report which ones. The
     configured sitrep agent (Claude by default) must be in it, else stop and report.

3. **Pure layer — `.aitask-scripts/monitor/agent_request_delivery.py` (new).**
   - Result codes (module constants): `SUBMITTED="submitted"`,
     `TYPED="typed_not_submitted"` (+ `:in_mode` / `:mode_unreadable`),
     `refused:<reason>` (`not_ready:dialog|draft|working|unknown|in_mode|mode_unreadable`,
     `identity_changed`, `no_agent`, `frozen`, `dispatch_failed` = load-buffer failed so
     nothing reached the pane), `SKIPPED="skipped"`, `UNKNOWN="unknown"`.
     `@dataclass(frozen=True) DeliveryResult(code, detail, request)` + `message()` giving
     the user text (e.g. unknown → "could not verify — look at the agent pane", never
     "sent"; typed_not_submitted → "the request is waiting in the agent's composer").
   - `readiness_verdict(tail1, tail2, agent, in_mode) -> "ready" | "not_ready:<r>"`, using
     **only** `review_loop.shadow_state` (no second detector). Agent without a detector or a
     `None` tail → `unknown`; then DIALOG → `dialog`, BUSY → `draft`, WORKING → `working`,
     UNKNOWN → `unknown` (either tail; dialog first, matching `_ordered_state`'s rationale);
     `tail1 != tail2` → `working`; `in_mode is None` → `mode_unreadable`; `True` → `in_mode`.
   - **Composer proof = the current composer's complete payload, never a search of the
     capture.** BUSY only says the composer holds *some* text, and a text search over the
     whole tail cannot tell the composer from the transcript (rejected design: an
     occurrence count accepts "request + appended user text", and on a retry accepts "the
     request echoed in history beside a foreign draft", so the retry Enter would submit
     the user's draft).
     - `review_loop.composer_payload(raw_text, agent) -> ComposerPayload | None`
       (beside the detectors, reusing their composer / gutter / border / status regexes
       and the bottom-up scan; it is a payload READER, not a second readiness detector):
       the bottom-most composer region only, delimited per the step-2 grammar; returns the
       payload display lines (prefix and continuation indent stripped, trailing blanks
       stripped) and the region's content width, or `None` whenever the region cannot be
       delimited exactly (no closing delimiter, a line inside the region that is neither
       the first line nor an indented continuation, the dim placeholder hint, an agent
       without a measured grammar).
     - `PAYLOAD_GRAMMAR_AGENTS`: the agents with a step-2-measured grammar pinned by
       fixtures. An agent outside it is refused **before anything is typed**
       (`refused:not_ready:unknown`): never paste text whose landing cannot be proved.
     - Pure `payload_matches(payload, expected) -> bool` (agent_request_delivery): walk
       `expected`; every display line must equal the next slice of `expected` exactly;
       a line break is allowed only where it is a **justified display wrap**:
       a word wrap (the expected text has ≥1 space there, all consumed, and the next word
       would not have fit: `width(line) + 1 + width(next_word) > content_width`) or a
       mid-token wrap (no space there, and `width(line) == content_width`). Display width
       counts East-Asian W/F as 2. Anything left over on either side, an extra line, or
       an unjustified break → `False`.
   - `TARGET_FORMAT = RUN_IDENTITY_FORMAT + "\t#{@aitask_sitrep_root}\t#{pane_dead}\t#{pane_current_command}"`;
     `parse_target(rc, out, pane_id, root)` → `(RunIdentity | None, refusal | "", command)`:
     the first 5 fields through `monitor_core.parse_run_identity`; frozen → `frozen`; a
     `sitrep_tui_root`, `tmux_os_path(stamp) != root`, or dead → `no_agent`.
   - `async deliver_sitrep_request(monitor, root, text, *, roles=find_sitrep_roles,
     resolve_agent=<pane resolver>, pause=None, sleep=asyncio.sleep, nonce=new_nonce)`:
     1. `roles(monitor, root)` in `asyncio.to_thread` — not ok or no agent → `refused:no_agent`;
     2. identity read (`display-message -p -t <pane> TARGET_FORMAT`) → refusals above;
        agent key from the command + pane_pid; no detector, or not in
        `PAYLOAD_GRAMMAR_AGENTS` → `refused:not_ready:unknown`. **Both re-run on every
        call; nothing cached.**
     3. readiness: `capture_raw_tail` → `sleep(COMPOSER_DRAIN_SECONDS)` → `capture_raw_tail`;
        if both READY + identical, `query_pane_mode` (last read before dispatch); not ready →
        `refused:not_ready:<r>` (never retried);
     4. `await pause("after_readiness")`; text dispatch (to_thread): `sent` → go on;
        `skipped` → `skipped` (detail in_mode | identity_changed); `unknown` → `unknown`;
        `failed` → `refused:dispatch_failed`;
     5. `await pause("after_paste")`; loop `attempt in range(SHADOW_SUBMIT_RETRIES + 1)`
        (each retry preceded by `await pause("before_retry")`):
        drain → capture → **pre-Enter proof on EVERY attempt, retries included**: state
        BUSY **and** `payload_matches(composer_payload(tail, agent), request)`. Otherwise
        withhold the Enter: attempt 0 (no Enter sent yet) with a delimited payload that
        differs → `typed_not_submitted` (detail `composer_changed`: our text is there
        with something else; nothing submitted); a retry whose payload differs →
        `unknown` (detail `composer_changed_after_enter`: the first Enter may have
        submitted and the composer now holds someone else's text); DIALOG / UNKNOWN /
        READY / WORKING / payload `None` → `unknown` (detail `pre_enter_dialog`,
        `pre_enter_unreadable`, `text_not_in_composer`, `composer_unprovable`) →
        `query_pane_mode` as the **last await before the Enter** (None →
        `typed_not_submitted:mode_unreadable`, True → `typed_not_submitted:in_mode`) →
        guarded Enter: `skipped`+in_mode → `typed_not_submitted:in_mode`,
        `skipped`+identity_changed → `refused:identity_changed`, `unknown` → `unknown` →
        drain → capture: READY/WORKING → `submitted`; BUSY → retry; DIALOG/UNKNOWN →
        `unknown`. Budget exhausted → `typed_not_submitted`.
     Modelled on `_submit_shadow_prompt`; the minimonitor path is not touched.

4. **Guarded dispatch — `monitor_core.py` (beside `kill_agent_run_guarded`) + gateway.**
   - `lib/tmux_exec.py`: `TmuxClient.run_with_input(args, data, timeout) -> (rc, stdout)`
     (subprocess only, text on stdin, same failure contract as `run`).
   - `TmuxMonitor.tmux_run_input(args, data, timeout=5.0)` → `self._tmux.run_with_input`
     (never the control client: it cannot carry stdin).
   - Constants: `DISPATCH_ACK_OPTION = "@aitask_dispatch_ack"`,
     `DISPATCH_ACK_FORMAT = "#{pane_id}\t#{pid}\t#{@aitask_dispatch_ack}"`,
     `DISPATCH_BUFFER_PREFIX = "aitask-sitrep-"`, `new_nonce()` = `secrets.token_hex(8)`.
   - `dispatch_condition(identity)` = `all_of([run_identity_condition(pane_pid, server_pid,
     FROZEN_OPTION), "#{==:#{pane_in_mode},0}"])`.
   - Pure `dispatch_ack_state(rc, out, pane_id, server_pid, nonce)`: `sent` only for rc 0,
     3 fields, same pane, same server pid, value == `<nonce>:sent`; `skipped` for
     `<nonce>:skipped` (same pane/server); anything else `unknown`.
   - `guarded_paste_text(monitor, identity, text, nonce) -> (state, reason)`: validate the
     `%N` pane id, hex nonce, pids (`run_identity_condition` raises) → `failed`;
     `load-buffer -b <buf> -` (stdin) rc≠0 → best-effort `delete-buffer`, `failed`;
     `if-shell -F -t <pane> <cond> "paste-buffer -d -b <buf> -t <pane> ; set-option -p -t
     <pane> @aitask_dispatch_ack <nonce>:sent" "delete-buffer -b <buf> ; set-option -p -t
     <pane> @aitask_dispatch_ack <nonce>:skipped"` (controlled tokens only); read back
     `DISPATCH_ACK_FORMAT` → `dispatch_ack_state`; `set-option -pu` the ack; not `sent` →
     `delete-buffer` (no leaked buffer); `skipped` → one `#{pane_in_mode}` + identity read
     labels `in_mode` vs `identity_changed`.
   - `guarded_send_key(monitor, identity, key, nonce)`: same shape, key ∈ `{"Enter"}`, true
     branch `send-keys -t <pane> Enter ; set-option … :sent`, else `set-option … :skipped`.
   - `TmuxMonitor.dispatch_text_guarded(identity, text, nonce)` /
     `dispatch_key_guarded(identity, key, nonce)` → the functions above with `self`.
   - `aidocs/framework/tmux_gateway.md`: add the `@aitask_dispatch_ack` row to the
     `@aitask_*` inventory (writer: the guarded dispatch, `<nonce>:sent|skipped`; lifetime:
     unset right after read-back, pane death; reader: the dispatcher's read-back only; not a
     helper marker) and one line on `TmuxClient.run_with_input`.

5. **Request table — `.aitask-scripts/sitrep_tui/sitrep_tui_requests.py` (new).**
   - `@dataclass(frozen=True) AgentRequest(action, key, label, template)`;
     `AGENT_REQUESTS` (the single source; t2211_5's parity test imports it):
     `request_triage t "Triage" ">t {cid}"`, `request_ask a "Ask agent" ">q {cid} {text}"`,
     `request_situation w "Situation text" ">w {theme}"`,
     `request_trail_refresh T "Trail refresh" ">tr {cid}"`,
     `request_pick_advice n "Pick advice" ">p"`. Re-exported from `sitrep_tui_app`
     (`from sitrep_tui.sitrep_tui_requests import AGENT_REQUESTS`) so the spec's import path
     works; one definition.
   - `validate_ask_text(text) -> str` (reason or ""): stripped, non-empty, ≤ `ASK_MAX_CHARS`
     (300, confirmed by the spike), no `unicodedata` category `Cc`/`Cf`/`Zl`/`Zp` (covers
     `\n`, `\r`, NEL, U+2028/9), plus `@` if the spike says so. `build_request(req, item,
     store, text="")` formats via `str.format` with store/user text only as ARGUMENTS, then
     re-validates the whole line (one line, no control chars); theme via `st.THEME_RE`.
   - `class TmuxGateway` (moved out of `_tmux_seams`): one `TmuxClient`, `tmux_run`,
     `tmux_run_async`, `tmux_run_input`.

6. **TUI wiring.**
   - `sitrep_tui_actions.py`: `ACTION_BINDINGS` gains the five rows **derived from
     `AGENT_REQUESTS`**; `ITEM_ACTIONS` gains the four item-scoped ones;
     `REQUEST_ACTIONS` (all five); `_ACTION_LABEL` entries; `_KEY_PLACEHOLDERS` +
     `model.DEFAULT_KEYS` gain `k_triage`, `k_ask`, `k_trail`.
   - `_item_action_ok`: triage ⇔ `classify ∈ {triage, review}`; ask ⇔ any store item;
     situation ⇔ `store.contexts[num].theme` matches `THEME_RE`; trail refresh ⇔
     `classify == "watch"` (trail-checked).
   - `SitrepTuiApp.check_action`, before the generic item branch: request actions only on
     main/details, only when `agent_state == "running"`, disabled (`None`) while a delivery
     is in flight; item ones then defer to `_item_action_ok`.
   - `_init_actions(..., deliver=None)`; `action_request_*` → `_start_request(action)`:
     re-check agent state and in-flight; item ones `_resolve_action_item(action)` (moved rev →
     refresh, nothing sent); ask → `AskAgentDialog(item)` (LabelFilterDialog short-pane
     layout: docked buttons, one-line `Input`, inline refusal notice from
     `validate_ask_text`); its callback re-resolves the item like the pick dialog. Then a
     worker `_deliver_flow(text)` with an `_request_inflight` flag (a second request is
     refused with a toast, never queued); toast `result.message()` with `markup=False`; any
     code other than `submitted` also opens `ResultDialog` (Content, markup-safe) with the
     code, the request and the detail.
   - `_tmux_seams` returns `(roles_probe, own_session, deliver)`; `deliver(text)` =
     `deliver_sitrep_request(gateway, root, text)`; `main()` passes it.
   - `sitrep_tui_model.NEXT_STEPS` How rows (the ONE table): triage/review name
     `{k_triage}` (`>t {cid}`), decide / watch_manual / unknown_manual name `{k_ask}` and keep
     the literal `>q {cid} …` (pinned by `test_sitrep_tui_app.py` L391), watch adds
     `{k_trail}` (`>tr {cid}`). Text says the key asks the sitrep agent beside this pane.

7. **Tests.**
   - `tests/test_sitrep_request_delivery.py` (pure / FakeMon recording every call):
     refusal table per verdict from `review_loop_fixtures` (`CLAUDE_DIALOG_RAW`,
     `CLAUDE_TYPED_RAW`, `CLAUDE_STREAMING_RAW`, `None`/`""`), unstable hash, mode
     None/True, no-detector agent; `dispatch_ack_state` per field mismatch (rc, arity, pane,
     server, nonce, `sent` vs `skipped` vs other); `dispatch_condition` contains the three
     identity terms + `#{==:#{pane_in_mode},0}`; `parse_target` (frozen, TUI root, wrong /
     empty stamp, dead, short read); the full phase order; identity + roles re-read on each
     of two calls; result mapping for every post-dispatch branch;
     **composer proof** over the step-2 captured fixtures (and modified copies of
     `CLAUDE_TYPED_RAW` / `CODEX_TYPED_RAW` / `OPENCODE_TYPED_RAW`): exact request →
     match; justified word wrap and full-width mid-token wrap → match; a break on a short
     line (unjustified) → no match; **request + appended user text → no match**;
     **request in the transcript beside an unrelated current draft → no match**; the dim
     hint, a missing closing delimiter, a stray non-continuation line → `None`;
     orchestrator regressions: appended text on attempt 0 → `typed_not_submitted`
     (`composer_changed`) with **no** Enter dispatched; a swallowed-looking first Enter
     followed by "request in history + foreign draft" → `unknown` with **exactly one**
     Enter dispatched; an agent outside `PAYLOAD_GRAMMAR_AGENTS` → refused before any
     `load-buffer`; a pre-fix control — the rejected occurrence-count check — accepts both
     regression captures, proving the fixtures exercise the hazard;
     `validate_ask_text` (newline, `\r`, NEL, U+2028, tab, empty, over-long);
     `run_with_input` passes stdin (fake subprocess).
   - `tests/test_sitrep_tui_requests.py` (App.run_test, the t2211_3 fixture builder): the
     binding matrix (which request keys show per item kind, main + details, hidden when the
     agent is absent/unknown, disabled while in flight); triage from details sends
     `>t c<N>`; a moved rev sends nothing; the ask dialog refuses bad text and its callback
     re-resolves; toast + ResultDialog per code; How texts name a remapped `t`;
     `DEFAULT_KEYS` vs `ACTION_BINDINGS` parity; `AGENT_REQUESTS` re-export identity.
   - `tests/test_sitrep_request_delivery_live.sh` (+ `tests/lib/fake_composer_agent.py`):
     `require_isolated_tmux`, modelled on `test_kill_agent_run_guarded.sh`; `mode-keys vi`.
     The fake agent (launched `exec -a claude <python> …` so the pane resolves to `claude`;
     asserted) sets the tty raw, logs every received byte, and redraws a Claude-shaped frame
     (`❯` + NBSP + dim hint / text; dialog = `CLAUDE_DIALOG_RAW`) in modes
     `ready|dialog|draft|stuck|resubmit_draft` (`resubmit_draft`: on the first Enter it
     moves the request into the transcript and shows a foreign draft in the composer,
     the user typing right after the submit), wrapping long composer text with the
     step-2-measured Claude grammar; each case first asserts the fixture classifies as intended
     (a broken fake is a setup failure, never a pass). The pane is stamped
     `@aitask_sitrep_root=<scratch root>` in an `agent-sitrep` window. Cases (a)–(i) as in
     the task, (e) both before the read (`refused:frozen`) and between readiness and
     dispatch (`skipped`), (f) text `>q c1 a;b "d" 'e' #{pane_id} $(echo x) \; ; set-buffer
     -b ait-injected x;` arrives byte-exactly and no `ait-injected` buffer exists, and every
     case asserts no `aitask-sitrep-*` buffer leaked. Added cases:
     (j) user text appended at `after_paste` (`send-keys -l`) → `typed_not_submitted`, the
     pane received the request + the user text and **no** `\r`;
     (k) `resubmit_draft` → `unknown`, exactly **one** `\r` received, the foreign draft
     never submitted;
     (l) a request longer than the composer width (word wrap + mid-token wrap) →
     `submitted`, received byte-exactly + one `\r`.
   - **Mutants** (in-process monkeypatches, each asserting its guard-specific red): no
     identity term → (d) red; readiness forced ready → (b)/(c) red; ack-less classified
     `sent` → (d) red; text inlined into the if-shell (`send-keys -l -t <p> <text>`) → (f)
     red; Python pre-Enter mode read forced `False` **and** no conjunct → (h)/(i) red; only
     the conjunct removed → (h) stays green through the Python gate; the payload proof
     replaced by the rejected occurrence count → (j)/(k) red.

## Verification

- `python3 tests/test_sitrep_request_delivery.py`, `python3 tests/test_sitrep_tui_requests.py`,
  `bash tests/test_sitrep_request_delivery_live.sh`.
- Unchanged: `bash tests/test_kill_agent_run_guarded.sh`, `bash tests/test_no_raw_tmux.sh`,
  `python3 tests/test_monitor_client_surface.py`, `python3 tests/test_sitrep_tui_actions.py`,
  `python3 tests/test_sitrep_tui_app.py`.
- `bash tests/run_all_python_tests.sh --test-dir tests` — last-line verdict, `PIPESTATUS`.
- `shellcheck` on the new shell test.
- Manual, real Claude sitrep agent (`ait sitrep`): `t` on a triage item submits `>t c<N>`;
  with a permission dialog open, or a half-typed draft, the key is refused and the dialog /
  draft is untouched; copy-mode entered during delivery leaves the request typed,
  unsubmitted, clipboard intact.

## Final notes to send (Step 8, after the commit, `/aitask-note`, hedged to the SHA)

- t2211_5: `AGENT_REQUESTS` lives in `sitrep_tui/sitrep_tui_requests.py` (re-exported from
  `sitrep_tui_app`), shape `AgentRequest(action, key, label, template)`, the five templates.
- t2211_6: keys `t a w T n`, the result vocabulary + refusals, `@aitask_dispatch_ack`, the
  load-buffer-on-stdin choice, `refused:dispatch_failed`, the composer-payload proof
  before every Enter and `PAYLOAD_GRAMMAR_AGENTS`.
- Shared-helper follow-up: spawned at Step 8d as the `shared_agent_submit_helper` 'after'
  mitigation (`minimonitor_app.py` `_fire_shadow_recheck` L5910-6009 /
  `_submit_shadow_prompt` L6011-6170 vs `agent_request_delivery.deliver_sitrep_request`).
  The minimonitor path is not touched in this task.

## Risk

### Code-health risk: medium
- Two implementations of the same pre-Enter / mode-gate / bounded-retry loop
  (`minimonitor_app._submit_shadow_prompt` and `deliver_sitrep_request`) can drift; a fix to
  one (e.g. a new t2001-style hazard) silently misses the other · severity: medium ·
  → mitigation: shared_agent_submit_helper
- New gateway primitive (`TmuxClient.run_with_input`, `TmuxMonitor.tmux_run_input`) widens
  the tmux gateway surface; its stdin path deliberately bypasses the control client ·
  severity: low · → mitigation: none (documented in `tmux_gateway.md`, covered by the
  pure test and every live case)
- Edits to the shared action tables / `NEXT_STEPS` How rows touch screens other siblings'
  tests pin · severity: low · → mitigation: none (existing sitrep TUI suites in Verification)

### Goal-achievement risk: medium
- A real agent may not take a pasted line as typed composer text (Claude paste collapse,
  Codex burst coalescing, an `@` file-suggestion popup taking the Enter) · severity:
  medium · → mitigation: none (plan Step 2 spike measures all three agents first, stop and
  report on failure)
- The composer-payload grammar (region delimiters, continuation indent, content width)
  is per agent and version; a wrong width rule would judge a legitimate wrap unjustified ·
  severity: medium · → mitigation: none (built from step-2 real captures pinned as
  fixtures; a mismatch withholds the Enter — `typed_not_submitted` / `unknown`, never a
  wrong submit; agents without a measured grammar are refused before typing)
- A wrapper-style agent install may not resolve to an agent key from the pane · severity:
  low · → mitigation: none (refuses `not_ready:unknown`, never types)

### Planned mitigations
- timing: after | name: shared_agent_submit_helper | type: refactor | priority: medium | effort: medium | inline_risk: high | added_complexity: medium | addresses: code-health — duplicated pre-Enter/mode-gate/retry loop in minimonitor and the sitrep delivery can drift | desc: extract one shared submit helper (pre-Enter verify, mode gate before every Enter, bounded Enter retry) used by minimonitor_app._submit_shadow_prompt (L6011-6170) and agent_request_delivery.deliver_sitrep_request, keeping both callers' result labels

## Step 9

Commit code with `feature: Add guarded request delivery from the sitrep TUI (t2211_4)`;
plan/task via `./ait git`; archive per Step 9.
