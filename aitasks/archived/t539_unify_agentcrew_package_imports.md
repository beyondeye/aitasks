---
priority: low
effort: low
depends: []
issue_type: refactor
status: Done
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-13 18:51
updated_at: 2026-04-14 08:07
completed_at: 2026-04-14 08:07
---

Refactor agentcrew_dashboard.py and agentcrew_report.py to use the package-style
import pattern (`from agentcrew.agentcrew_utils import ...` with a
`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` prelude) for
consistency with agentcrew_runner.py and agentcrew_status.py.

Context: t536 fixed a ModuleNotFoundError in agentcrew_status.py by adding the
sys.path insert that agentcrew_runner.py already uses. agentcrew_dashboard.py
and agentcrew_report.py currently use sibling-style imports
(`from agentcrew_utils import ...`), which only work because Python auto-adds
the script's directory to sys.path when the script is launched directly. These
work today but are inconsistent with the rest of the package and fragile if the
scripts are ever imported as modules.

Files to update:
- .aitask-scripts/agentcrew/agentcrew_dashboard.py
- .aitask-scripts/agentcrew/agentcrew_report.py

For each file:
- Add `from pathlib import Path` to imports
- Add `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` before
  the first agentcrew package import
- Change `from agentcrew_utils import ...` to `from agentcrew.agentcrew_utils import ...`
- Any other sibling-style imports of agentcrew_* modules: change to
  `from agentcrew.agentcrew_<name> import ...`

Verification:
- ./ait crew dashboard --help (runs without ModuleNotFoundError)
- ./ait crew report --help (runs without ModuleNotFoundError)
- Run each command from a tempdir cwd to confirm cwd-independence
