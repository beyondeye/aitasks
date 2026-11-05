---
priority: medium
effort: high
depends: [t2211_3, t2037_2]
issue_type: feature
status: Ready
labels: [sitrep, tui, tmux]
gates: [risk_evaluated]
anchor: 2175
created_at: 2026-11-05 15:37
updated_at: 2026-11-05 15:37
---

## Context

Child 4 of t2211. The sitrep TUI's agentic keys (triage this, ask about, write situation,
refresh trail, pick advice) **type a request into the sitrep agent pane and submit it**. A
live, unfrozen pane is NOT proof that typing is safe:
- if the agent is parked at a confirmation dialog, Enter answers it;
- if it holds the user's unfinished draft, Enter submits the draft mixed with our text;
- if it is working, the input is queued or garbled;
- if the user enters tmux copy-mode at any point, Enter goes to the mode (vi
  copy-pipe-and-cancel clobbers the clipboard).

Delivery is therefore three separately observed phases: readiness, dispatch with an
observable result, and submission. Parent plan:
`aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`. Two plan-review rounds raised
these concerns and they are binding here.

## Gate and first step

- Depends on t2211_3 (sibling chain) and **t2037_2** (uncommitted `monitor_core.py` /
  `status_client.py`). Re-read the landed `monitor/monitor_core.py`, `monitor/review_loop.py`,
  `monitor/minimonitor_app.py` (`_fire_shadow_recheck` ~L5332, `_submit_shadow_prompt`
  ~L5433) and `lib/helper_panes.py`, and confirm `git diff HEAD -- <files>` is empty before
  the first edit.

## Request table

`AGENT_REQUESTS` in `.aitask-scripts/sitrep_tui/sitrep_tui_app.py` is the single source,
and t2211_5's parity test reads it:

| key | request |
|---|---|
| triage this | `>t c<N>` |
| ask about | `>q c<N> <text>`; the text comes from an input dialog, one line, with control characters and newlines refused |
| write situation | `>w <theme>` |
| refresh trail | `>tr c<N>` |
| pick advice | `>p` |

A key is shown only when the selected item fits (e.g. `>tr` only on trail-watch items)
**and** an agent role resolves. The action re-checks both.

## Phase 1 — readiness (positive detection; anything else refuses)

Reuse `monitor/review_loop.py`; do **not** write a second detector:
- `shadow_state(raw_text, agent)` (~L1003);
- `SHADOW_STATE_DETECTORS` (claude / codex / opencode);
- the verdict-order rationale (~L469: dialog first, `working` outranks `ready`).

Steps:
- Resolve the agent key from the sitrep pane's launch agent string.
- Take two raw tails with `capture_raw_tail` (`monitor_core` ~L738, `-e` ANSI kept), about
  `COMPOSER_DRAIN_SECONDS` apart.
- Require `SHADOW_READY` on both and byte-identical tails (the
  `shadow_prompt_ready(..., hash_stable)` contract).
- Require `query_pane_mode` (~L783) not in a mode; unreadable = not ready.

| verdict | refusal |
|---|---|
| `SHADOW_DIALOG` | `not_ready:dialog` |
| `SHADOW_BUSY` | `not_ready:draft` (the user's unsent input stays untouched) |
| `SHADOW_WORKING` or an unstable hash | `not_ready:working` |
| `SHADOW_UNKNOWN`, a failed capture, an agent with no detector | `not_ready:unknown` |
| in a mode | `not_ready:in_mode` |
| mode unreadable | `not_ready:mode_unreadable` |

A refusal is shown to the user and never retried automatically.

## Phase 2 — dispatch with an observable result

New `TmuxMonitor.dispatch_text_guarded(identity, text, nonce)` in `monitor_core.py`, beside
`kill_agent_run_guarded` (~L4153). It shares `helper_panes.run_identity_condition` (~L221) /
`all_of` (~L186).

`helper_panes.readback_state` (~L247) cannot classify a send. It was built for kills and
reports only pane present / gone / unknown, and both a pane that got the text and a pane
whose guard skipped stay present. `if-shell` success does not show which branch ran either.

- The text **never enters the tmux command parser**: argv-only `set-buffer -b
  aitask-sitrep-<nonce> -- <text>` first. The guarded branch holds only controlled tokens:
  a validated pane id, a hex nonce, a fixed option name.
- The `if-shell -F -t <pane> <cond>` condition is the run identity + `#{==:#{pane_in_mode},0}`.
  - True branch: `paste-buffer -d -b aitask-sitrep-<nonce> -t <pane> ; set-option -p -t
    <pane> @aitask_dispatch_ack <nonce>:sent`.
  - Else branch: `delete-buffer -b aitask-sitrep-<nonce> ; set-option -p -t <pane>
    @aitask_dispatch_ack <nonce>:skipped`.
- Read back `#{pane_id}\t#{pid}\t#{@aitask_dispatch_ack}` and classify with a pure
  `dispatch_ack_state(rc, out, pane_id, server_pid, nonce)`:
  - `sent` only for the same server pid, the same pane, and ack == `<nonce>:sent`;
  - `skipped` for `<nonce>:skipped`;
  - anything else is `unknown`, never `sent`.
- Then `set-option -pu` the ack. On skipped/unknown, `delete-buffer` (no leaked buffers).
  On `skipped`, one read of `#{pane_in_mode}` + the run identity labels the reason
  (`in_mode` vs `identity_changed`).
- Add `@aitask_dispatch_ack` to the `@aitask_*` inventory in `aidocs/framework/tmux_gateway.md`.
- **Measure first:** confirm live that `paste-buffer` of a short single line lands as typed
  composer text for each supported agent (Claude collapses large pastes into
  `[Pasted text …]`). If it does not for an agent, **stop and report**. Never inline the
  text into the if-shell command string. The replacement design is decided with the user.
  Record the measurement in the plan.

## Phase 3 — submission, separate from dispatch

- Re-capture and require the request text visible in the composer and no dialog: the
  `HOLD_PRE_ENTER_DIALOG` / `DISARM_TEXT_NOT_IN_COMPOSER` analogues (`review_loop.py`
  ~L116-132).
- **Pane-mode gate before EVERY Enter, retries included** (the t2001 rule
  `_submit_shadow_prompt` documents ~L5475):
  - `query_pane_mode` is the last await before each Enter;
  - active or unreadable → no Enter, result `typed_not_submitted:in_mode` /
    `:mode_unreadable`, and the request stays typed for the user;
  - the Enter dispatch's if-shell also carries the `#{pane_in_mode}` conjunct, so the server
    re-checks atomically.
- Enter = a second guarded dispatch (`send-keys -t <pane> Enter`) with its own nonce ack.
- Verify by re-capture that the composer emptied or the agent began working. Retries are
  bounded by `SHADOW_SUBMIT_RETRIES`, and each retry passes the mode gate again.
- Model on `_submit_shadow_prompt`. Do NOT refactor the minimonitor path here. If a shared
  helper looks worthwhile, record it (file + line ranges) for a follow-up.

## Result vocabulary

Shown markup-safe in a toast and the result panel:

| result | meaning |
|---|---|
| `submitted` | text dispatched, Enter acked, submit verified |
| `typed_not_submitted[:in_mode\|:mode_unreadable]` | the text is waiting in the composer; Enter was withheld, skipped or unconfirmed |
| `refused:<reason>` | phase-1 reasons, `identity_changed`, `no_agent`, `frozen` |
| `skipped` | the identity guard declined at dispatch |
| `unknown` | the outcome could not be verified; the user is told to look at the agent pane, never "sent" |

## Identity

The agent is re-resolved through `monitor_core.find_sitrep_roles` (t2211_2), and
`RunIdentity` / `RUN_IDENTITY_FORMAT` (~L5211/5229) is re-read on **every** request. It is
never cached across user actions. Only the pane stamped `@aitask_sitrep_root` for this root,
live, unfrozen and not dead is a target. The TUI never types into any other pane.

## Tests

- `tests/test_sitrep_request_delivery.py` (pure / FakeMon):
  - the refusal table per verdict, using the review_loop fixture captures for dialog, draft,
    working and unknown;
  - `dispatch_ack_state` for each field mismatch;
  - the phase order;
  - the identity re-read per request;
  - the built condition contains the identity terms + the `pane_in_mode` conjunct;
  - one-line validation of `>q` text.
- `tests/test_sitrep_request_delivery_live.sh`: isolated tmux (`require_isolated_tmux`),
  modelled on `tests/test_kill_agent_run_guarded.sh`, with a scripted fake agent pane that
  renders a Claude-shaped composer / dialog / draft from fixtures and a pause seam between
  phases. Cases:
  - (a) ready → `submitted`; the pane received exactly the text + Enter;
  - (b) dialog → `refused:not_ready:dialog`; nothing received;
  - (c) draft → `refused:not_ready:draft`; the draft intact;
  - (d) `respawn-pane -k` between readiness and dispatch → `skipped`, the pane alive, the
    buffer deleted;
  - (e) frozen → refused/skipped;
  - (f) text with `;`, quotes, `#{…}`, `$(…)` arrives literally, and no tmux command runs;
  - (g) the composer never empties → `typed_not_submitted`;
  - (h) copy-mode entered after the paste → `typed_not_submitted:in_mode`: no Enter, the
    composer still holds the request, still in copy-mode, a sentinel buffer unchanged;
  - (i) copy-mode entered between an unconfirmed Enter and its retry → no retry Enter.
- **A mutant per guard:**
  - no identity condition → (d) red;
  - no readiness → (b)/(c) red;
  - ack-less classified `sent` → (d) red;
  - text inlined into the if-shell → (f) red;
  - no Python pre-Enter mode read AND no conjunct → (h)/(i) red.

## Verification

- The tests above; `bash tests/test_no_raw_tmux.sh`; `bash tests/test_kill_agent_run_guarded.sh`
  (unchanged); `bash tests/run_all_python_tests.sh --test-dir tests` (last-line verdict).
- Manual, with a real Claude sitrep agent:
  - `>t c<N>` from the TUI submits;
  - with a permission dialog open, or a half-typed draft, the TUI refuses and the dialog /
    draft is untouched;
  - entering copy-mode during delivery leaves the request typed, unsubmitted.
