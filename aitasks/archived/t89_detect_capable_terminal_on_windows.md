---
priority: medium
effort: medium
depends: ['85']
issue_type: feature
status: Done
labels: [install_scripts, aitasks, bash, scripting]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 11:17
updated_at: 2026-02-11 22:05
completed_at: 2026-02-11 22:05
boardcol: now
boardidx: 20
---

when running aitasks scripts on windows with WSL we must ensure that we are running in a terminal app capable to use the aitasks bash and python scripts features

In the Windows ecosystem, there are two main hosts that might be running your WSL instance: the Legacy Console Host (conhost.exe) and the modern Windows Terminal.Here is the breakdown of how TUI (Text User Interface) apps function in both environments.1. The Modern Standard: Windows Terminal (Recommended)If you are on Windows 11 (or have installed it on Windows 10), your WSL likely opens in Windows Terminal by default. This is a modern, GPU-accelerated terminal emulator designed specifically to handle complex TUI apps.Capabilities: It fully supports advanced features required by tools like vim, tmux, htop, or mc.Color: Supports 24-bit True Color and varied color schemes.Fonts: Handles Unicode, Powerline glyphs, and ligatures (essential for stylized TUI prompts).Mouse Support: Supports mouse clicks and scrolling within Linux apps (e.g., clicking tabs in tmux or selecting text in vim).Rendering: Much faster and smoother, preventing the screen tearing often seen in older consoles.2. The Legacy Console (conhost.exe)If you open WSL by running wsl.exe from a standard Command Prompt window, or if you are on an older version of Windows 10, you are likely using the legacy Console Host.Capabilities: Microsoft significantly updated this console specifically to support WSL. It does parse ANSI escape sequences, meaning it can render TUI apps correctly. You can run nano, vim, or top, and they will work.Limitations:Glitchy Rendering: Complex TUIs may flicker or render slowly.Color limitations: Often limited to 16 or 256 colors depending on the specific build version, rather than True Color.Font Issues: It struggles with many modern fonts and special characters used in advanced shell themes (like Oh My Zsh).Key Features ChecklistMost modern TUI apps rely on specific protocols. Here is how the Windows WSL environment handles them:FeatureSupport StatusNotesANSI/VT SequencesSupportedEssential for moving the cursor and clearing lines.ColorsSupportedWindows Terminal supports full RGB (True Color). Legacy support varies.Mouse ReportingSupportedYou can use the mouse to interact with TUI elements (if the app supports Xterm mouse mode).Resize EventsSupportedIf you resize the window, the TUI app receives the signal (SIGWINCH) and redraws correctly.SummaryIf you launch a Linux app and it looks like a "DOS" window, it will likely work, but it may look "retro" and feel sluggish.Recommendation: For the best experience with TUI apps, ensure you are using Windows Terminal. You can download it free from the Microsoft Store. It allows you to run WSL, PowerShell, and CMD in tabs side-by-side with full modern rendering support.

Instead of just checking for Windows Terminal (WT_SESSION), it checks a list of known "modern terminal" indicators (like COLORTERM support and specific emulator variables).

#!/bin/bash

Generic Capability Check (COLORTERM): This is the most important addition. Alacritty, WezTerm, and nearly all modern emulators automatically set the environment variable COLORTERM=truecolor or COLORTERM=24bit. The legacy Windows Console does not set this variable automatically.

if the user does not have capable terminal app, suggest steps to fix the issue
