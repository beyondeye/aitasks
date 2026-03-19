---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [tui, brainstorming]
children_to_implement: [t417_7]
created_at: 2026-03-18 11:08
updated_at: 2026-03-19 11:27
---

in preparation for the ait brainstorm tui that we are designing, we need to create a custom diff viewer and navigator tui that will be later integrated in the ait brainstorm tui. the diff viewer nedd to support only markdown. its purpose is to compare implementation plans for some task in the ait brainstorm tui, so that the user will not have to reread two plans multiple times to see what was changed with respect to the previous plan. because in brainstorming we will multiple plan not only two, the tui should shpport multiway diffs: in other wrods the user would want to know what is in plan3 and not in plan 1 & 2 and viceversa or what is is plan4 and not in plan 1 & 2 and 3 and viceversa. thers is probably a limit on how many  plans we can realistically show in one screen but this is the general motivation. In addition to show the diffs, it should be possible to actually create a modified plan that merge diffs from other plans, automatically naming it based on the plans from which the changes where merged. Also since the differ main purposes and comparing actual plan content and not necessarily structural difference between the plans (like order and positions of paragraphs) the diffing should have a classical mode and a mode that ignore such structural differences. this is a very complex task that must be decomposed in child tasks. the tasks should also create some dummy plans (lets say 5 plans) for testing purposes, we should integrate with a file browser widget (with history) for selecting the plan files to compare (adding them) and view where we have all the currently selected plan with a "button" to the side to remove one of them, and a button to start the diffing view with that specific plan as the main plan, with a dialog to select form the list of current loaded plan the ones to diff against. this is a bery complex task that must be splitted in child tasks
