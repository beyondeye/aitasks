---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitasks, install_scripts]
created_at: 2026-02-14 23:17
updated_at: 2026-02-14 23:17
---

when running the install script for aitasks ( [200~curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash~) the CHANGELOG.md and VERSION of aitasks projects are installed in the new project: they should not, this is probably an issue in tarball creation in the github workflow run when a new aitasks version is created. also ait shim has been updated to allow the ait setup command to autodownload the aitasks framework latest release and run install, so that he user does not have to do it manually. need to document this in the README.md
also when running ait setup / install in a repostiory without git, the ait framework filea are not added/committed to the repo. they should be autoadded and commited. (with user approval of course). 
perhaps this is a problem only when the git repo is initialized from ait setup, or perhaps this is a general problem. please check
