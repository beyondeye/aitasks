---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts, robustness]
gates: [risk_evaluated]
created_at: 2026-08-06 11:54
updated_at: 2026-08-06 11:54
---

## Origin

Surfaced downstream in the `thinking_app` install (its `t103` review, then its
`t109`). `.aitask-scripts/` there is installer-synced, so the fix belongs here;
the downstream task was dropped in favour of this one.

## Defect

Every streaming emitter in `.aitask-scripts/lib/yaml_utils.sh` writes one
diagnostic **per remaining line** when its downstream consumer stops early,
burying the structured result the helper exists to emit:

| Emitter | Diagnostics observed | Writer |
|---|---|---|
| `join_yaml_flow_lists:39` (reached via `read_yaml_field`) | 92 | bash `printf` |
| `read_yaml_list:135` | 199 | `sed: couldn't flush stdout: Broken pipe` |
| `_read_yaml_mappings_emit_field:174` | 158 | bash `printf` |
| `_read_yaml_mappings_flush:213` | 79 | bash `printf` |

In every case **stdout and the exit status were already correct** — only stderr
was polluted.

## Root cause

These helpers stream to consumers that legitimately stop once they have their
value: `read_yaml_field` `return`s mid-stream (line 83) while
`join_yaml_flow_lists` is still writing into the process substitution at line
87; a `| head -1` consumer does the same for `read_yaml_list` /
`read_yaml_mappings`.

Under a **default** SIGPIPE disposition the producer is killed silently, which
is why this never shows up in an interactive shell. But agent harnesses built
on Node/Python leave **SIGPIPE as `SIG_IGN`**, and child processes inherit that
disposition — so the producer is *not* killed: every remaining write returns
`EPIPE`, and bash (or `sed`) reports it. A script cannot repair this from the
inside: signals inherited as `SIG_IGN` cannot be trapped or reset, so `trap -
PIPE` does not help.

## Deterministic reproduction

```bash
cat > case.sh <<'EOF'
source .aitask-scripts/lib/yaml_utils.sh
read_yaml_field big.md priority        # big.md: 200-key frontmatter
EOF
python3 -c 'import signal,subprocess
def pre(): signal.signal(signal.SIGPIPE, signal.SIG_IGN)
p=subprocess.run(["bash","case.sh"], preexec_fn=pre, capture_output=True, text=True)
print(p.stdout, len(p.stderr.splitlines()))'
```

Prints the correct value plus 92 stderr lines. Swap in
`read_yaml_list list.md labels | head -1` (200-item block list) and
`read_yaml_mappings attach.md attachments | head -1` (80 attachments) for the
other two.

## Suggested fix

The invariant across all sites: **stdout of these emitters is always a pipe**
(every in-tree call site is a process substitution or a pipeline), so a write
failure can only mean the reader is gone. Stop cleanly on the first failed
write; never re-report per line.

- `join_yaml_flow_lists` (38-45) — `printf '%s\n' "$buffer" 2>/dev/null || return 0`
  on both the streaming write and the final flush.
- `read_yaml_field` (82, 89) — guard the two single writes and `return 0`
  explicitly (today the bare `return` propagates `echo`'s status).
- `read_yaml_list` block emitter (133-139) — `sed`'s own flush error cannot be
  stopped from the loop; drop the fork and use the regex capture the loop
  already computes:
  `[[ "$fline" =~ ^[[:space:]]*-[[:space:]]+(.*)$ ]]` then
  `printf '%s\n' "${BASH_REMATCH[1]}" 2>/dev/null || break`. Verify the
  substitution is identical for `- a`, `-   a`, `- ` (empty item) and `-a`
  (not a list item). Bonus: removes a fork per list item.
- `read_yaml_mappings` helpers (172-226, 252-316) — `_read_yaml_mappings_emit_field`
  is documented `set -e`-safe (always returns 0) and must stay that way, so
  signal the closed pipe back instead of returning non-zero: add a
  `_yaml_pipe_closed=""` local to `read_yaml_mappings` (same dynamic-scope
  pattern as the existing `f_*`/`p_*` locals), set it from both helpers on a
  failed write, and `break` the read loop / skip the final flush when it is set.

Comment each site with the inherited-`SIG_IGN` condition so the `2>/dev/null`
is not mistaken for blanket error-swallowing.

## Regression test

Extend `tests/test_yaml_utils.sh` (it already sources both libs and
`tests/lib/asserts.sh`). Write a `$TMP` runner that re-executes a snippet with
SIGPIPE ignored — skip with a printed notice if `python3` is absent:

```python
import signal, subprocess, sys
sys.exit(subprocess.call(["bash", sys.argv[1]],
    preexec_fn=lambda: signal.signal(signal.SIGPIPE, signal.SIG_IGN)))
```

Four cases, each asserting **stdout value**, **empty stderr** and **exit 0**:

1. `read_yaml_field` on a 200-key frontmatter (covers `join_yaml_flow_lists`).
2. `read_yaml_list <200-item block list> | head -1`.
3. `read_yaml_mappings <80 attachments> | head -1`.
4. `read_yaml_list <400-entry inline list> | head -1` — this path is already
   clean; the case locks it that way.

Plus a non-truncation guard: the **unpiped** output of cases 2 and 3 still
yields the full item counts (200 and 80), proving the guards stop only on a
real closed pipe.

**Run the new cases against the unpatched file first** and observe the storm
counts tabled above — an unreachable trigger would prove nothing.

## Risk notes for planning

- `lib/yaml_utils.sh` is sourced by `task_utils.sh` and `agentcrew_utils.sh`, so
  it reaches essentially every framework script: a parsing regression would be
  broad and quiet. Before touching the emitters, pin the **current** return
  values of the three readers across every supported shape (wrapped flow list,
  inline list, block list incl. multi-space and empty items, quoted scalars,
  trailing `<ws>#` comment, `bug#3.png` with no space before `#`, `url: null`)
  as characterization assertions — the `sed` → bash-capture rewrite must not
  move them.
- Worth a follow-up: sweep every call site of the four emitters to confirm (and
  record, or enforce) the "stdout is always a pipe" contract that makes
  `2>/dev/null` safe. Where it does not hold, a genuine `ENOSPC` would become
  silent truncation.
