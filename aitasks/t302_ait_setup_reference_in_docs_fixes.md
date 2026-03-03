---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [install_scripts]
created_at: 2026-03-03 16:24
updated_at: 2026-03-03 16:24
---

in the install documentation of ait setup, and in the ait script itself it is not always clear that ait setup and the curl install. one line command must be run in the project directory (root with the .git repo data) where you want to add support for aitasks, aitasks is heavily integrated with git, also need to add warning it ait setup when running in directory with no git repo to explain all this and make sure that this is the right directory the user want to use the aitasks framework. also need to explore the possibility to install at least part of the aitasks framework globally. I am afraid that this is not trivial, considering that configuring code agents skills globally make updates and a lot of other things very difficult, in any case as part of this task create a new task taht explore this possibility
