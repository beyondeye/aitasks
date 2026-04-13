---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [agentcrew, brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-13 17:26
updated_at: 2026-04-13 17:29
---

When running an agentcrew agent interactively from a brainstorm session (e.g. 'detailer_001' in crew 'brainstorm-427'), the agent's attempts to call './ait crew status ...' fail with:

  ModuleNotFoundError: No module named 'agentcrew'

Traceback points to .aitask-scripts/agentcrew/agentcrew_status.py line 15:
  from agentcrew.agentcrew_utils import (...)

The workaround that succeeds is running the script with an explicit PYTHONPATH:
  PYTHONPATH=/home/ddt/Work/aitasks/.aitask-scripts python3 .../agentcrew_status.py ...

Root cause (to verify): the bash wrapper (.aitask-scripts/aitask_crew_status.sh or the ait dispatcher) does not set PYTHONPATH to include .aitask-scripts, and the interactive agent's cwd is the crew worktree (.aitask-crews/crew-brainstorm-427/), not the repo root. Running from the repo root happens to work because of cwd-relative sys.path behavior; from the worktree it does not.

Fix direction:
- In the bash wrapper (or directly in ait dispatcher for the 'crew status' subcommand), export PYTHONPATH to include the absolute path of .aitask-scripts before invoking the Python script.
- Alternatively, make agentcrew_status.py insert its own parent directory into sys.path at the top of the file, mirroring what brainstorm_crew.py does (sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))).
- Add a regression test that calls 'ait crew status ...' from a cwd that is NOT the repo root (e.g. from a tempdir).

Impact: blocks interactive launch mode for code agents that call back into 'ait crew status' mid-run (which is most of them — status updates and progress reporting rely on it). Headless mode probably works because the runner invokes these commands itself from the repo root.
