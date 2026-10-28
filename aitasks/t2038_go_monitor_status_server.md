---
priority: medium
effort: high
depends: [2037]
xdeps: [17, 23]
xdeprepo: aitasks_go
issue_type: feature
status: Postponed
labels: [monitor, tmux, performance]
children_to_implement: [t2038_1, t2038_2, t2038_3, t2038_4]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-28 21:40
---

Reimplement the shared monitor status server in Go as a goengines binary
(proposed name `goengines/cmd/ait-monitord`). It speaks the same protocol
(t2034_3) as the Python server it replaces, and stays behind a switch — the
Python server is the default — until the classifier cross-check (t2034_6)
passes. Background: aitasks#2034. Split out of t2034 because it is a full port
of the producer.

## Children

1. Binary skeleton: protocol codec + lifecycle.
2. Discovery + capture.
3. Classifier.
4. State (idle clock, shadows, task completion) + end-to-end comparison.

## Dependencies

- t2037, the Python server (the Go one mirrors its lifecycle and behaviour).
- The Go tmux package aitasks_go#17. Its location follows the ship-path decision
  in aitasks_go#15.

## Known Go pitfalls

- RE2 has no lookarounds. `monitor/prompt_patterns.py` has none today, but
  `monitor/review_loop.py:611` does (`(?=\x1b\[|$)`); that stays client-side.
- `\s`, `\w` and `\b` are ASCII-only in Go but Unicode in Python 3 `str`
  patterns, and Python's `splitlines()` splits on more than `\n`.

## Not in this task

Event-driven change detection — tmux control-mode `%output` (disabled today by
`-f no-output,ignore-size`) or `refresh-client -B` format subscriptions
(tmux ≥ 3.2) — so quiet panes need no capture. A follow-up once one process owns
the event stream.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T07:37:08Z.a2b254c5df1b76e7ee485373 from=aitasks_go#t15 from_verified=yes at=2026-10-25T07:37:08Z base=60ca89154aa0d66ceec006c9f8c6b764fe661ae6 base_branch=main dirty=yes host=omg16
>
> | Ship-path decision in aitasks_go (t15, aidocs/aitasks_go/ship_path.md there): every framework
> | Go binary — ait-testmap, ait-tui, and ait-monitord — is developed in the private aitasks_go
> | repository (nested module `goengines/`) and exported one way into public goengines. A public
> | export never becomes the development source. ait-monitord is therefore being RE-HOMED to
> | aitasks_go by aitasks_go#t23, which recreates this task and its children there (content
> | preserved; location `goengines/cmd/ait-monitord` in the private nested module, importing the
> | private `goengines/tmux` from aitasks_go#t17).
> | 
> | This task and t2038_1 now carry `xdeps: [17, 23]` (xdeprepo aitasks_go) so they cannot be
> | started in public before the re-home lands — that xdeps edge is the binding dependency; this
> | note is context only. Do not start implementing here. t23 respects live ownership: if this
> | task is ever Implementing/locked, it waits or arranges a checkpointed handoff.

> **✉ note:t23** id=2026-10-28T19:40:57Z.dfcf9b7e4e1de01a67e35be2 from=aitasks_go#t23 from_verified=yes at=2026-10-28T19:40:57Z base=444391966b2c7625e47a8a0b2736cdca84272082 base_branch=main dirty=no host=omg16
>
> | Re-home done (aitasks_go t23). Verified by read-back before this note was written:
> | 
> | - t2038   -> aitasks_go#t47   (go_monitor_status_server)
> | - t2038_1 -> aitasks_go#t47_1 (monitord_skeleton_protocol_lifecycle)
> | - t2038_2 -> aitasks_go#t47_2 (monitord_discovery_capture)
> | - t2038_3 -> aitasks_go#t47_3 (monitord_classifier)
> | - t2038_4 -> aitasks_go#t47_4 (monitord_state_and_e2e)
> | 
> | Content is preserved there; the location is goengines/cmd/ait-monitord in the private nested
> | module, and it reaches public goengines only through the one-way export.
> | aitasks_go#t47 carries depends [17] plus xdeps [t2037, t2034_3] (xdeprepo aitasks). t47_1 also
> | depends on aitasks_go t22_3, because internal/platform arrives with the testmap import.
> | 
> | Here: t2038 and t2038_1..4 are now Postponed. Do not implement them in this repository.
> | t2034_6 now has depends [] and xdeps [47] (xdeprepo aitasks_go), and t2034's description
> | points at aitasks_go#t47.
