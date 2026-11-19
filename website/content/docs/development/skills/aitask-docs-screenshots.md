---
title: "/aitask-docs-screenshots"
linkTitle: "/aitask-docs-screenshots"
weight: 58
description: "Generate and repair the website's TUI screenshots from the real TUIs running on a sample project"
maturity: [experimental]
depth: [advanced]
---

`/aitask-docs-screenshots` makes the TUI screenshots for this documentation site. A docs page marks where a screenshot belongs with a one-line comment, the screenshot marker. For each marker the skill starts the real TUI on a sample project inside a tmux session of its own, presses the keys that lead to the state the page describes, and captures the screen as an SVG image. It shows you the new images and puts them into the site only after you approve.

The skill works in the aitasks repository only. It drives a tool, `website/screenshots.sh`, that is not installed into other projects; anywhere else the skill stops at its first step.

**Usage:**
```
/aitask-docs-screenshots
/aitask-docs-screenshots board_child_tasks tui_switcher_dialog
```

Without arguments the skill covers every marker under `website/content/` and every recorded recipe. Scene names limit it to those scenes.

> **Note:** Must be run from the project root directory, in Claude Code. It needs `tmux` and the Python environment installed by `ait setup`; image previews need Chromium.

## When to Use This Skill

- A docs page has a new screenshot marker and needs its image.
- A TUI changed (a key, a label, a layout) and its screenshots should show the new screen.
- A page's text changed and its screenshot may no longer show what the text describes.

To add a screenshot to a page, first leave a marker where the image belongs. The marker's keys and value rules are in `website/README.md`, under "Screenshot Markers":

```markdown
<!-- screenshot: scene=board_child_tasks file=aitasks_board_child_tasks.svg alt="Board with a parent task expanded to show its child tasks" caption="An expanded parent task with its child tasks joined by connector lines." -->
```

## Terms

| Term | Meaning |
|---|---|
| Scene | One screenshot, named by the marker's `scene=` key. Several markers on different pages can use the same scene. |
| Recipe | The recorded route to a scene: the sample data, the launch command, the keys, the texts to wait for, and the texts that must be on screen when the image is taken. Stored as `website/screenshots/scenes/<scene>.yaml`. |
| Dataset | A named set of sample data, such as tasks, a stored trail or a brainstorm session, that a recipe starts from. |
| Batch | The images of one capture run, staged in a directory that git ignores, with a record of which markers they belong to. |

## What the Skill Does

1. **Lists the work.** It runs the screenshot checker and the tool's `list` verb, and separates the scenes that have no recipe from the ones that have one.
2. **Captures each scene that has no recipe.** It reads the page around the marker, with the marker's alt text and caption, and decides which state of which TUI illustrates it. It explores the TUI in one tmux session, reading the screen after each key. When it knows the route it starts a fresh session, follows the route once without detours, takes the shot and saves the recipe. The tool saves a recipe only after the route also works in another fresh session.
3. **Checks each existing recipe.** It replays the recipe. When the replay fails, the session stays open, and the skill looks at the screen there to find what changed. When the replay passes, the skill compares the image with the page. For a failed replay or an image that no longer fits the page, it finds the route again and replaces the recipe.
4. **Shows you one batch.** It replays every scene it wants to apply into a single batch and writes a preview page, `preview.html`, with each image next to its marker's page, alt text and caption. An image that replaces an existing one is shown beside the old one.
5. **Applies the batch you approved.** It copies each image to `website/static/imgs/` and replaces each marker with a `static-img` shortcode, then runs the link check and the screenshot check.

The skill does not commit. You review the changed pages and images and commit them yourself.

## What You Decide

The skill asks one question: whether to apply the batch. The question names the batch, lists each screenshot with its pages, and gives the path of the preview page. Open the preview before you answer. If you ask for a change, the skill captures again and asks again with a new batch.

The skill also reports what it could not do:

- **No route.** The state a recipe describes cannot be reached, because the feature is gone or the sample data cannot hold it. The skill leaves the recipe as it is and tells you what it tried and what the screen showed. The fix is a change to the page, to the TUI or to a dataset.
- **Refused scenes.** During apply, a scene is refused when its staged image, its target file or one of its markers changed after the capture. Nothing of that scene is written. It needs a new capture and a new review.
- **Visual verification pending.** The skill could not render an image to look at it. Check that image in the preview page yourself before you approve.

## What Appears in an Image

Every capture runs on a sample project named `lumen`, with invented tasks and one invented person. The TUI runs in a tmux server started for the capture, without your tmux configuration, with its own home directory, and with a stand-in program in place of the code agent. Your tasks, your sessions and your settings do not appear, and no real code agent is started.

Times that the TUI takes from the clock, such as an agent's idle timer or the time a lock was taken, show the moment of the capture. Two runs of the same recipe therefore differ in those places.

## Related

- [`/aitask-audit-wrappers`](../aitask-audit-wrappers/), the other skill for work on the framework itself.
- [`/aitask-docs-review`]({{< relref "/docs/skills/aitask-docs-review" >}}), which reviews a page's text against the documentation guide.
- `website/README.md`, sections "Screenshot Markers" and "Generating Screenshots", for the marker grammar and the tool's commands.
