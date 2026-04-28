---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [ait_setup, installation, python]
children_to_implement: [t695_1, t695_2, t695_3, t695_4, t695_5]
created_at: 2026-04-28 10:25
updated_at: 2026-04-28 11:31
boardidx: 60
boardcol: now
---

on macos the installed system python is usually quite old (3.9.x) and this is causing problem many items, the latest issue I found is that the linkify dependency that is installed in venv in ait step DOES NOT SUPPROT 3.9.x. perhaps we should refactor all usage of python (every place we invoke the system python) in the aitasks framework (in scripts, in ait, EVERYWHERE) add some internal ENV variable that define the actual python to user, and add ait setup install via the newer python version (perhaps via brew?). this problem is mainly for macos. an alternative simpler solution is prompt the user to update the system python? I am not sure what would the better/more transparent solution for the user. for avoiding bugs and maintenance issue in the future it would probably best to support installation of aitasks "private" instlal of python, if ait setup detect an old version. ask me questions if you need clarfications
