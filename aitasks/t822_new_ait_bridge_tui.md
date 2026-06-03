---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [ait_bridge]
children_to_implement: [t822_3, t822_4, t822_5]
created_at: 2026-05-24 08:40
updated_at: 2026-05-25 18:03
boardidx: 100
boardcol: now
---

I am planning to support connecting an ait ide instance (that is basically a tmux session where the ait ide lives) to a mobile app. the user will be able to interact with the ait ide like with features like the ait monitor, ait board and so on. from the mobile app. in order to be able to do it we need "bridge" that will be responsible for the connection between the the local tmux session that runs the ait ide and the mobile app. the name I am thinking for this new tui is "bridge" but I am open to "better" i.e. more specific less generic names. still the name should be simple enough to be easy to remember and spell. Anyway the first feature to add to this new tui is allow generate and QR code in textual/python, see for example https://gemini.google.com/share/233de65b7ad0 for possible ideas on how to do. Via the QR code we will have a way to establish the connection between the a local pc and a mobile app. Now about how exacly the mobile app will be able to control what is happening in the ait ide /tmux session. I think the best is going through this bridge tui that will receive the command from the mobile app, gating them with some permission manager/ permission profiles of what can be seen and what can be done. see for example https://gemini.google.com/share/08b546589a97 for some ideas. But basically I would like as I said the connection to be gated and handled by this new ait bridge tui. (bridge name pending confirmation). The development of the mobile app that will connect the ait bridge is done in ../aitasks_mobile. that is a different github repo that is also developed using the task framework. need to coordinate the development of the bridge tui with features in the aitasks_mobile app. this is a complex task. the purpose of this task is 1) design the approach and architecture for the connection: output an aidocs in his repo 2) create the basic brdige tui with the qr code genereation and showing 3) high level design of the rest of the new board tui, like adopting the feature in ait monitor (refactor code) that will be reused to forward the code agent activities to the mobile app and allow to control them like now we can control the with the ait monitor. In short the first TUI taht will be ported to the mobile app and support connection between the local pc and the mobile app will be ait monitor. this is a very complex task that need to be split into child tasks
