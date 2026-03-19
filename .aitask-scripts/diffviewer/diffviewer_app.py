#!/usr/bin/env python3
"""Diff Viewer TUI for comparing implementation plans."""
from __future__ import annotations

import os
import sys

# Ensure the parent directory is on the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from textual.app import App
from textual.binding import Binding

from diffviewer.plan_manager_screen import PlanManagerScreen


class DiffViewerApp(App):
    """TUI application for viewing diffs between implementation plans."""

    TITLE = "ait diffviewer"

    CSS = """
    /* ── PlanManagerScreen layout ── */

    #manager_container {
        width: 100%;
        height: 1fr;
    }

    #browser {
        width: 40%;
        height: 100%;
        border-right: tall $accent;
        padding: 0 1;
    }

    #loaded_pane {
        width: 60%;
        height: 100%;
        padding: 0 1;
    }

    #loaded_title {
        text-style: bold;
        padding: 0 0 1 0;
        color: $accent;
    }

    #loaded_list {
        height: 1fr;
    }

    #empty_placeholder {
        color: $text-muted;
        padding: 1;
    }

    /* ── PlanBrowser entries ── */

    .browser-breadcrumb {
        color: $accent;
        text-style: bold;
        padding: 0 0 1 0;
    }

    .browser-section-header {
        color: $accent;
        text-style: italic;
        padding: 1 0 0 0;
    }

    .browser-separator {
        color: $text-muted;
    }

    .browser-dir-entry {
        text-style: bold;
    }

    .browser-file-entry {
    }

    .browser-history-entry {
        color: $text-muted;
    }

    .browser-error {
        color: $error;
    }

    .browser-empty {
        color: $text-muted;
    }

    .browser-focused {
        background: $accent 30%;
    }

    /* ── Loaded plan entries ── */

    .loaded-plan-entry {
        height: auto;
        padding: 1 0;
        border-bottom: hkey $surface-lighten-2;
    }

    .plan-entry-info {
        width: 1fr;
        height: auto;
    }

    .plan-entry-name {
        text-style: bold;
    }

    .plan-entry-heading {
        color: $text-muted;
    }

    .plan-remove {
        margin: 0 1;
    }

    .plan-diff {
        margin: 0 1;
    }

    /* ── DiffLaunchDialog ── */

    DiffLaunchDialog {
        align: center middle;
    }

    #diff_launch_dialog {
        width: 60%;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    #diff_launch_title {
        text-style: bold;
        color: $accent;
        padding: 0 0 1 0;
    }

    .diff-section-label {
        text-style: italic;
        padding: 0 0 0 0;
    }

    #diff_targets {
        height: auto;
        max-height: 10;
        padding: 0 0 0 1;
    }

    #diff_mode_set {
        padding: 0 0 0 1;
        height: auto;
    }

    #diff_launch_buttons {
        height: auto;
        padding: 1 0 0 0;
        align-horizontal: right;
    }

    #diff_launch_buttons Button {
        margin: 0 1;
    }

    /* ── DiffViewerScreen ── */

    #info_bar {
        text-style: bold;
        color: $accent;
        padding: 0 1;
        height: 1;
    }

    /* ── SummaryScreen ── */

    SummaryScreen {
        align: center middle;
    }

    #summary_container {
        width: 50%;
        height: auto;
        max-height: 60%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    #summary_title {
        text-style: bold;
        color: $accent;
        padding: 0 0 1 0;
    }

    #btn_close_summary {
        margin: 1 0 0 0;
    }

    /* ── MergeScreen ── */

    #merge_layout {
        width: 100%;
        height: 1fr;
    }

    #merge_hunk_pane {
        width: 50%;
        height: 100%;
        border-right: tall $accent;
        padding: 0 1;
    }

    #merge_preview_pane {
        width: 50%;
        height: 100%;
        padding: 0 1;
    }

    /* ── SaveMergeDialog ── */

    SaveMergeDialog {
        align: center middle;
    }

    #save_merge_dialog {
        width: 60%;
        height: auto;
        max-height: 60%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    #save_merge_title {
        text-style: bold;
        color: $accent;
        padding: 0 0 1 0;
    }

    #save_merge_buttons {
        height: auto;
        padding: 1 0 0 0;
        align-horizontal: right;
    }

    #save_merge_buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.push_screen(PlanManagerScreen())


def main():
    DiffViewerApp().run()


if __name__ == "__main__":
    main()
