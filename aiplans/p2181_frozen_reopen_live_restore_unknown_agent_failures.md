---
Task: t2181_frozen_reopen_live_restore_unknown_agent_failures.md
Base branch: main
Output branch: main
---

# t2181 — frozen-reopen live suite: restores fail with `unknown_agent`

## Context

`bash tests/test_frozen_reopen_live.sh` reports 101/148 passed; every case that
performs a real **resume** restore (c2, c3, k, h2, …) gets
`RESTORE_FAILED:<id>|unknown_agent` before reaching the logic it tests.

**Root cause (established, environment-independent).** t2109 (`ad1e1ddab`)
made `agent_restore._resume_agent` (`.aitask-scripts/lib/agent_restore.py:243-245`)
refuse any record whose `agent_kind` is empty — a session's CLI must be
*proved* before `--resume <sid>` is launched with it. t2109 added the
`upsert --agent-kind <k>` evidence flag and updated the Python unit tests, but
did not touch this live suite. Its `seed()` helper
(`tests/test_frozen_reopen_live.sh:127-143`) upserts with `--session-id` and no
agent string or kind, so every seeded record has `agent_kind=""` and is
refused. The resolver is correct (it is the t2109 contract); the **fixture** is
what never followed.

The fixture's fake agent is `claude` on PATH, and the synthetic project's
`raw` default is `claudecode/sonnet5_5` (copied `codeagent_config.json`), whose
kind is `claudecode` (`agent_sessions.agent_kind_of`).

## Implementation

### Step 1 — pin the fixture's `raw` default (review concern, addressed inline)

Today the fixture copies the repository's live `codeagent_config.json`, while
its fake executable is hard-wired to `claude`. That coupling already exists
(a Codex `raw` default would resolve a `codex` argv the fake PATH cannot
satisfy), and adding a recorded `claudecode` kind makes it fail earlier and
louder (`agent_mismatch:claudecode:codex`). Since the fixture owns the fake
CLI, it should own the default too.

After the existing `cp` (line ~107-108), introduce one constant and pin it:

```bash
# The fake CLI is `claude`, so the project's `raw` default is pinned to a
# claudecode model rather than inherited from the repository's live config
# (whose default may legitimately move to another CLI). Records stay WITHOUT
# an agent string, so restores still exercise the raw-default resolution path.
FIXTURE_RAW_AGENT="claudecode/sonnet5_5"
FIXTURE_AGENT_KIND="${FIXTURE_RAW_AGENT%%/*}"
python3 -I - "$PROJ/aitasks/metadata/codeagent_config.json" "$FIXTURE_RAW_AGENT" <<'PY' \
    || { echo "FAIL: could not pin the fixture's raw default"; exit 1; }
import json, sys
path, raw = sys.argv[1], sys.argv[2]
cfg = json.load(open(path))
cfg.setdefault("defaults", {})["raw"] = raw
json.dump(cfg, open(path, "w"), indent=2)
PY
```

Plus a fail-loud staleness guard, so a future model removal surfaces as a
fixture error instead of 47 opaque `binary` restore failures:

```bash
python3 -I -c 'import json,sys; m=sys.argv[2].split("/",1)[1];
sys.exit(0 if any(x.get("name")==m for x in json.load(open(sys.argv[1]))["models"]) else 1)' \
    "$PROJ/aitasks/metadata/models_claudecode.json" "$FIXTURE_RAW_AGENT" \
    || { echo "FAIL: fixture pin $FIXTURE_RAW_AGENT is not in models_claudecode.json"; exit 1; }
```

(No `codeagent_config.local.json` is copied, and the resolver reads only the
fixture project's own metadata layers, so the pin is authoritative.)

### Step 1b — `seed()`: record the kind

Add `--agent-kind "$FIXTURE_AGENT_KIND"` to the `store upsert` call (both the
session and `nosession` variants — harmless for `nosession`, refused earlier
as `no_session`):

```bash
store upsert --root "$PROJ" --window "$window" --pane "%99999" \
    --pane-pid 999999 "${sess[@]}" --agent-kind "$FIXTURE_AGENT_KIND" \
    --task-id 12 >/dev/null
```

Kind and pinned default derive from the one constant, so they cannot drift.

Keeping **no** `--agent-string` preserves the original test path exactly: a
record with no string resumes on the project's resolved `raw` default, which
`_resume_agent` now accepts because the default's kind matches the recorded
kind. (Passing `--agent-string` instead would change which branch runs.)

### Step 2 — document it in the seed comment

Extend the `seed` comment (line 125-126) and the "Records are seeded…" header
paragraph (line 18-20) with one sentence: the seed carries
`--agent-kind claudecode` — the evidence a SessionStart hook supplies for a
hand-started claude — because since t2109 a resume refuses a record whose CLI
is unproven (`unknown_agent`), and the restore launches the fixture's pinned
`claudecode` raw default. Update the "REAL RESTORES" paragraph (line ~54-60)
to say the model metadata is copied and `raw` is pinned to the fake CLI's kind.

### Scope check (done during planning)

Other shell suites that seed via `upsert` without kind/string:
`test_ide_frozen_all_projects_live.sh` only **reopens viewers** (no resume) —
unaffected. `test_restore_flows_live.sh` seeds onto the hook-created record
(the fake agent's hook supplies the kind). No other change needed.

## Verification

- `bash tests/test_frozen_reopen_live.sh` → expect `Results: 148 passed, 0 failed`
  (suite runs inside a tmux session; `require_isolated_tmux`).
- Negative control: temporarily run it with the flag removed is unnecessary —
  the 47-failure baseline was already recorded in the task (and in
  `42b547c67`'s clean worktree); confirm the failure count before the edit with
  one pre-change run, then the green run after.
- Pin proof: inspect the fixture's `codeagent_config.json` during a run (or a
  one-off probe of the pin snippet against a copy with `raw` set to
  `codex/gpt6_1_sol`) → `raw` reads `claudecode/sonnet5_5` afterwards.
- Guard proof: run the staleness one-liner against a models file lacking
  `sonnet5_5` → exit 1.
- `shellcheck tests/test_frozen_reopen_live.sh` (no new warnings).
- `python3 -m pytest tests/test_agent_restore.py -q` unaffected (no source change).

Step 9 (Post-Implementation): commit `test: …(t2181)`, archive via the
standard workflow.

## Risk

### Code-health risk: low
None identified. Test-fixture-only change; no shipped code touched. The
fixture/live-config coupling raised in review is removed inline (Step 1).

### Goal-achievement risk: low
None identified. Root cause is traced to the exact refusal branch and the
commit that introduced it; the fix supplies the evidence the contract requires
without weakening the resolver.
