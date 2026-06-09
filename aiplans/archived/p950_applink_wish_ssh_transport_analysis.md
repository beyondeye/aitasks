---
Task: t950_applink_wish_ssh_transport_analysis.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: applink wish/SSH transport analysis doc (t950)

## Context

The user is exploring (a) porting the aitasks framework TUIs to Go and (b)
`charmbracelet/wish` (SSH serving of Bubble Tea TUIs) as a possible connection
mechanism for the `ait applink` bridge (parent t822). An `/aitask-explore`
session worked through three angles — wish-vs-native-mobile, the hosted-aitasks
deployment topology, and how the framework's tmux usage integrates with wish —
and converged on a coherent recommendation. This task captures that analysis as
a permanent design/analysis aidoc so the conclusions inform the t822 follow-ups
and the `aitasks_go` port, rather than living only in a chat transcript.

Docs-only task: produce one aidoc and wire its cross-references. No code under
`.aitask-scripts/`, no Go/Bubble Tea port, no mobile changes.

## Deliverable

### New file: `aidocs/applink/wish_ssh_evaluation.md`

Style-match the three existing `aidocs/applink/` docs: `##` section headers,
embedded comparison tables, short code/URI snippets, a cross-references section,
an "Out of scope" section. Sections:

1. **Overview / what wish is** — `charmbracelet/wish` = Go SSH-server framework
   (on gliderlabs/ssh) serving Bubble Tea TUIs over SSH; client must be an
   SSH/terminal client receiving a raw VT/ANSI stream; SSH public-key auth;
   middleware (`bubbletea`, `activeterm`, `accesscontrol`, `logging`, `git`,
   port-forwarding). Reference apps: Soft Serve, Wishlist.
2. **Core contrast with applink** — the load-bearing applink decision is *the
   phone is a native client, not a terminal emulator* (server parses ANSI once →
   styled spans in MessagePack; no VT parser on the phone; structured
   permission-gated verbs; QR token→bearer; Suspended→Connected resume). Table
   contrasting "raw VT stream over SSH" vs "styled-span native render."
3. **Per-use-case recommendation** (one subsection + explicit verdict each):
   - **Native mobile companion (t822 goal)** → *keep applink; wish is a
     regression.* Reasons: forces a full VT parser/terminal emulator on mobile;
     loses structured per-verb gating; bandwidth/battery regression vs
     delta/append/zero-idle plane; SSH sessions don't map to backgrounding/
     resume; loses per-pane subscribe/focus/cadence; discards the staged
     cross-network roadmap.
   - **Reaching ait TUIs from another *terminal* (PC/laptop/power-user phone
     terminal)** → *wish is an excellent complementary path*, near-free once TUIs
     are Go/Bubble Tea (`aitasks_go`); a better-built "Phase 2 tunnel escape
     hatch."
   - **Hosted aitasks (framework on a remote box)** → wish is home turf for
     hosted→PC (the PC *is* a terminal). Mobile should connect **directly to the
     hosted box, not via the PC** (avoids the PC-must-be-on dependency, double
     hop, stateful-proxy role). Cleanest topology: both front-ends in parallel
     over one source of truth. Bonus: the public hosted address solves the
     v1 LAN-only limit *without* building the deferred Phase-3 relay broker.
4. **Deployment topologies** — table of local-PC vs hosted; the
   mobile-direct-to-hosted conclusion; **public-exposure hardening list** (real
   TLS cert + rotation, bearer entropy audit, rate-limit pairing attempts) that
   raises the bar on the security review the v1 protocol doc defers under its
   same-LAN assumption.
5. **tmux integration** — two layers of multiplexing: (A) tmux as agent/process
   multiplexer (stays, backend) vs (B) tmux as user-facing window manager
   (`j` switcher + `switch-client` + one-TUI-per-window). The nested-tmux /
   `tmux attach` trap (prefix collisions, resize/DCS pain, bypasses middleware
   AND all per-verb gating). Clean integration: wish serves a single Bubble Tea
   "control" TUI doing navigation in-app; tmux demoted to backend. Enabler:
   `monitor` already renders multiple agents in one screen (`PaneCard` grid) —
   that model ports; the `j`-switcher/`switch-client`/one-TUI-per-window model
   does not.
6. **Unifying conclusion** — the `monitor_core` extraction seam (t822_3) with
   three front-ends over it and tmux below as backend. Reuse this table:

   | Front-end | Navigation layer | tmux role |
   |---|---|---|
   | Local Textual (today) | tmux windows + `j` switcher + `switch-client` | window manager AND backend |
   | wish (SSH/terminal) | in-app, inside the served Bubble Tea TUI | backend only |
   | applink (native mobile) | native mobile UI | backend only |

   Rule: going remote (wish OR mobile) removes tmux's window-manager role;
   navigation moves into the front-end. wish and applink are **complementary**
   (terminal clients vs native mobile), not competing.
7. **Cross-references** — `protocol.md`, `content_transport.md`, `permissions.md`,
   and the t822_3 `monitor_port_design.md` seam; note `aitasks_go` Bubble Tea
   port as the precondition that makes wish cheap.
8. **Out of scope** — code under `.aitask-scripts/`; the Go/Bubble Tea port
   (aitasks_go); mobile changes (aitasks_mobile); a full public-exposure security
   spec (enumerate hardening items only).

## Cross-reference wiring

- **`aidocs/applink/protocol.md` — "## Transport choice" (line ~21):** add one
  sentence/pointer noting that an SSH-based alternative (charmbracelet/wish) and
  the hosted-deployment topology are evaluated in
  `wish_ssh_evaluation.md`, and that wish is positioned as a *complementary
  terminal-client path*, not a replacement for the native styled-span data plane.
- **`CLAUDE.md` (line ~278-279):** extend the existing `aidocs/applink/` pointer
  to also list `wish_ssh_evaluation.md` (current-state-only prose, no version
  history per documentation conventions).

## Verification

- `aidocs/applink/wish_ssh_evaluation.md` exists and renders cleanly (all 8
  sections present, tables well-formed).
- Every per-use-case subsection ends with an explicit verdict.
- The hardening list and the two multiplexing layers are both present.
- The `monitor_core` three-front-ends table renders.
- Cross-reference links resolve: `grep -l wish_ssh_evaluation aidocs/applink/protocol.md CLAUDE.md`
  returns both; relative links in the new doc point at existing files
  (`protocol.md`, `content_transport.md`, `permissions.md`,
  `../../aitasks/t822/t822_3_monitor_port_design.md`).
- No code files changed (`git diff --name-only` shows only the new doc,
  `protocol.md`, and `CLAUDE.md`).

## Post-implementation

Per task-workflow Step 9: profile 'fast' works on the current branch (no
worktree/merge). Commit the doc + cross-ref edits as
`documentation: Add wish/SSH transport evaluation aidoc (t950)`; plan file
committed via `./ait git`. Then archive via `aitask_archive.sh 950`.
Suggest a follow-up to mirror the analysis into `aitasks_go` planning once the
Bubble Tea port is underway (out of scope here).

## Risk

### Code-health risk: low
- Docs-only change: one new markdown file plus two additive cross-reference
  edits in `protocol.md` and `CLAUDE.md`. No code paths touched, no behavior
  change, negligible blast radius. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The analysis content is already fully scoped and agreed during the explore
  session and embedded in the task description; the remaining work is faithful
  authoring + cross-ref wiring. Minor residual risk that a forward-looking claim
  (e.g. wish's exact middleware set) drifts from upstream, mitigated by framing
  the doc as an evaluation/recommendation rather than an implementation spec.
  · severity: low · → mitigation: TBD

## Final Implementation Notes

- **Actual work done:** Created `aidocs/applink/wish_ssh_evaluation.md` (250
  lines) with all 8 planned sections — overview, what wish is, core contrast
  with applink, per-use-case recommendation (3 verdicts), deployment topologies
  + public-exposure hardening, tmux integration (two layers + nested-tmux trap +
  clean integration), the unifying `monitor_core` three-front-ends table/rule,
  cross-references, and out-of-scope. Wired two cross-references: a pointer from
  `aidocs/applink/protocol.md` "Transport choice" section, and an extension of
  the `aidocs/applink/` pointer in `CLAUDE.md`.
- **Deviations from plan:** None of substance. Added an explicit "Verdict:" line
  to use case 3 (hosted) during verification so all three use-case subsections
  carry a parallel explicit verdict (the plan called for explicit verdicts; the
  first draft left use case 3's verdict implicit in bold bullets).
- **Issues encountered:** During ownership claim (Step 4) the email was first
  set from the system context (`daelyasy@hotmail.com`) instead of the userconfig
  email; corrected via `--force` re-claim to `dario-e@beyond-eye.com` per the
  'fast' profile's `default_email: userconfig`.
- **Key decisions:** Framed wish and applink as *complementary* rather than
  competing — wish for terminal clients / hosted access, applink for the native
  mobile companion — anchored on the `monitor_core` extraction seam (t822_3) so
  all front-ends share one headless core with tmux demoted to backend when
  remote. Kept the doc as an evaluation/recommendation, not an implementation
  spec; the Go/Bubble Tea port and a public-exposure security spec are explicitly
  out of scope.
- **Upstream defects identified:** None
- **Follow-up suggestion:** Mirror this analysis into `aitasks_go` planning once
  the Bubble Tea TUI port is underway (out of scope here; not yet created as a
  task).
