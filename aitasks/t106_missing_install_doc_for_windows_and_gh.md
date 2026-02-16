---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [aitasks, install_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-13 00:45
updated_at: 2026-02-16 18:54
boardcol: now
boardidx: 30
---

In the README.md in the Quick Install paragraph information in missing about a few things: 1) it is not clear that the install command (curl ....) should be run when inside WSL shell (that is opened by search WSL in the windows searchbox

Also there should a short reference on how install WSL on windows (see for example https://learn.microsoft.com/en-us/windows/wsl/install)

Also it must be clarified that claude code must also installed from WSL to work we aitasks: see https://code.claude.com/docs/en/quickstart

Installing warp on windows with wsl integration: first need to install warp as per warp for windows installation then Configure your default shell to use WSL:

another option is to use the default windows wsl shell directly it also support tabs

or use the wsl extenstion for vscode search gooogle on how to configure it)

also the install script is currently failing at the question install claude code permissions

also the documentation is missing that it is fundamental to run gh login for github integration

The installation instruction are perhaps better to be replicated with more details in a separate file not in the README.md, a file called INSTALLING.md that is linked at the end of the QuickInstall section of the readme,md

actually the command to run for github authentication is gh auth

gh auth login
