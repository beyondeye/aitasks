---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [install_scripts, installation]
children_to_implement: [t623_7]
created_at: 2026-04-22 09:15
updated_at: 2026-05-10 13:45
boardcol: now
boardidx: 10
---

currently the only supported installation method for the aitasks framework is curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash

We want to to add more standard installation methods (like distribution in standard package manager like brew, and the various linux package manager. we want to automate as much as possible the release of new package versions, so this task should also include research of method to automate the release process for the various package managers, when the support for the new distribution and install methods are implemented we must also update the documentation in README>md and wehbsite accordingly. this is a complex task that need to be decomposed in child tasks
