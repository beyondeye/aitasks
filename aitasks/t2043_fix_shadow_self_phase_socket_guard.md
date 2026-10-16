---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tmux, minimonitor]
anchor: 2039
followup_kind: upstream_defect
created_at: 2026-10-16 14:55
updated_at: 2026-10-16 14:55
---

## Origin

Spawned from t2039 during Step 8b review. Found by t2039's sweep of untargeted
in-pane tmux reads; it is a different defect from t2039's own (wrong window), so
it was not fixed there.

## Upstream defect

- `.aitask-scripts/aitask_shadow_capture.sh:321 — the cross-server guard compares #{socket_path} and the -t "$own_pane" read, both taken from the gateway server, so the comparison is always true and the guard never fires (its sibling shadow_self_target compares against ${TMUX%%,*} correctly)`

## Diagnostic context

`shadow_self_phase()` reads the advisory phase stamped on its own pane and is
documented to apply "the same socket check" as `shadow_self_target`: a stamp
read from a pane on ANOTHER tmux server (a same-numbered `%N` there) must not be
used. But both sides of the check come from the gateway:

```bash
own_sock="$(ait_tmux display-message -p "#{socket_path}" ...)"        # gateway server
out="$(ait_tmux display-message -p -t "$own_pane" "#{socket_path}..." )" # gateway server
[[ "$own_sock" == "$sock" ]] || return 0                              # always equal
```

`ait_tmux` always talks to the gateway socket (`-L ait` by default), so the two
`#{socket_path}` values are the same server whatever `$TMUX` says. When the
shadow runs in a pane of a foreign server (the user's personal tmux), `-t
"$own_pane"` can name an unrelated pane on the gateway server, and its phase
stamp is printed as ours. `shadow_self_target` (same file, ~line 243) does it
right: it compares against `${TMUX%%,*}`, the socket of the server this process
actually lives on. `lib/tmux_exec.sh::ait_tmux_self_pane_pid` uses the same
correct pattern.

## Suggested fix

Take `own_sock` from `${TMUX%%,*}` (return 0 when `$TMUX` is empty), exactly as
`shadow_self_target` does. Add a test in the shadow capture suite: a pane id that
exists on the gateway server but `$TMUX` names another socket → `--phase` prints
nothing from that pane; the matching-socket control still prints the stamp.
