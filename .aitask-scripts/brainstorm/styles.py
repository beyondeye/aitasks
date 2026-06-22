"""Brainstorm TUI: the application-level CSS (moved verbatim from BrainstormApp.CSS)."""

APP_CSS = """
    Screen {
        align: center middle;
    }

    #initializer_row {
        height: 1;
    }

    .initializer-banner {
        width: 1fr;
        height: 1;
        padding: 0 1;
        background: transparent;
        color: $text;
    }

    .initializer-banner.visible {
        background: $error;
    }

    /* Always-on runtime strip above the tabs (t983_9): runner state + count. */
    .runtime-strip {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }

    .status-header {
        height: 1;
        padding: 0 1;
    }

    .status_pane_title {
        width: 1fr;
        text-style: bold;
    }

    #brainstorm_tabs {
        height: 1fr;
    }

    VerticalScroll {
        padding: 1 2;
    }

    /* Status tab */
    GroupRow {
        height: auto;
        padding: 0 1;
    }

    GroupRow:focus {
        background: $accent;
        color: $text;
    }

    GroupRow:hover {
        background: $surface-lighten-1;
    }

    /* Hovering the focused group must stay in the focus-accent family, not
       flip to the gray hover (:hover would otherwise override :focus at equal
       specificity). A lighter shade of $accent reads as "hover" while keeping
       the focused row recognizable. (t1018_3) */
    GroupRow:focus:hover {
        background: $accent-lighten-1;
        color: $text;
    }

    .status_section_title {
        text-style: bold;
        margin-top: 1;
    }

    .status_agent_detail {
        padding: 0 3;
        height: auto;
    }

    AgentStatusRow {
        padding: 0 3;
        height: auto;
    }

    AgentStatusRow:focus {
        background: $accent;
        color: $text;
    }

    AgentStatusRow:hover {
        background: $surface-lighten-1;
    }

    ProcessRow {
        height: auto;
        padding: 0 3;
    }

    ProcessRow:focus {
        background: $accent;
        color: $text;
    }

    ProcessRow:hover {
        background: $surface-lighten-1;
    }

    ProcessRow.-dead {
        opacity: 0.6;
    }

    .status_output_preview {
        padding: 0 5;
        color: $text-muted;
        height: auto;
    }

    .status_empty {
        width: 100%;
        content-align: center middle;
        text-style: italic;
        color: $text-muted;
        height: 100%;
    }

    /* Actions wizard */
    FuzzyCheckList {
        height: auto;
        margin-bottom: 1;
    }

    FuzzyCheckList .fcl_filter {
        margin: 0 1;
    }

    FuzzyCheckList .fcl_list {
        height: auto;
        max-height: 10;
        padding: 0 1;
    }

    .actions_step_indicator {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        color: $accent;
    }

    .actions_section_title {
        text-style: bold;
        margin-top: 1;
    }

    OperationRow {
        padding: 0 1;
        height: 1;
    }

    OperationRow:focus {
        background: $accent;
        color: $text;
    }

    OperationRow:hover {
        background: $surface-lighten-1;
    }

    CycleField {
        height: 1;
        padding: 0 1;
    }

    CycleField:focus {
        background: $accent;
        color: $text;
    }

    .actions_summary {
        padding: 1 2;
    }

    .actions_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    /* Compare matrix overlay table (t983_7) */
    #compare_table {
        height: 1fr;
    }

    /* Node action selection modal */
    #node_action_dialog {
        width: 64;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #node_action_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    /* Effective-target summary line for the Operations dialog (t983_4). */
    #node_action_targets {
        height: auto;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #node_action_hint {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #node_action_list {
        height: auto;
        max-height: 24;
        padding: 0 1;
    }

    /* Picker rows wrap (height: auto overrides the global single-line
       OperationRow) so long descriptions and the disabled-op "(reason)"
       suffix are fully visible instead of truncating. */
    #node_action_list OperationRow {
        height: auto;
    }

    #node_action_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    /* DAG visualization */
    DAGDisplay {
        height: 1fr;
        padding: 1 2;
    }

    /* Browse split pane (t983_3): switcher (graph⇄list) | shared detail */
    #browse_split {
        height: 1fr;
    }

    #browse_switcher {
        width: 60%;
        height: 1fr;
        border-right: solid $primary;
    }

    #node_list_pane {
        width: 1fr;
        height: 1fr;
        padding: 1 1;
    }

    #browse_detail_pane {
        width: 40%;
        padding: 1 2;
    }

    /* Config-step side-by-side preview (t945): input left, proposal right.
       The ratio-cycle action (alt+w) toggles three width splits by adding a
       ratio_* class to BOTH panes; compound selectors give each its width. */
    .config_preview_split {
        height: 1fr;
    }

    .config_preview_left {
        width: 50%;
        height: 1fr;
        padding: 0 1;
    }

    .config_preview_pane {
        width: 50%;
    }

    .config_preview_left.ratio_input_wide { width: 70%; }
    .config_preview_pane.ratio_input_wide { width: 30%; }
    .config_preview_left.ratio_proposal_wide { width: 30%; }
    .config_preview_pane.ratio_proposal_wide { width: 70%; }

    #session_status_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #session_status_info {
        color: $text-muted;
        margin-bottom: 2;
    }

    #module_status_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #module_status_info {
        height: auto;
        margin-bottom: 2;
    }

    /* Marked-node textual summary (t983_4); empty until nodes are space-marked. */
    #browse_marked_info {
        height: auto;
        color: $warning;
        margin-bottom: 2;
    }

    #browse_node_title {
        text-style: bold;
        margin-bottom: 1;
    }

    #browse_node_info {
        height: auto;
        padding: 0;
    }

    /* Graph view fills the Browse switcher when selected. */
    #dag_content {
        width: 1fr;
        height: 1fr;
    }

    .meta_field {
        padding: 0;
    }

    .dim_subheader {
        padding: 0 1;
        margin-top: 1;
    }

    .fcl_subheader {
        padding: 0 1;
        margin-top: 1;
    }

    NodeRow {
        padding: 0 1;
        height: 1;
    }

    NodeRow:focus {
        background: $accent;
        color: $text;
    }

    NodeRow:hover {
        background: $surface-lighten-1;
    }

    /* Delete session modal */
    #delete_dialog {
        width: 60;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }

    #delete_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #delete_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    /* Init modal */
    #init_dialog {
        width: 60;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #init_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #init_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    /* Init failure modal */
    #init_failure_dialog {
        width: 90%;
        height: 80%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }

    #init_failure_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        color: $error;
    }

    #init_failure_hint {
        width: 100%;
        margin-bottom: 1;
    }

    #init_failure_output {
        height: 1fr;
        margin-bottom: 1;
    }

    #init_failure_buttons {
        height: 3;
        align: center middle;
    }

    /* Node detail modal */
    #node_detail_dialog {
        width: 80%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #node_detail_title {
        text-style: bold;
        text-align: center;
        dock: top;
        width: 100%;
        padding: 1;
        background: $secondary;
    }

    #node_detail_tabs {
        height: 1fr;
    }

    #metadata_scroll {
        height: 1fr;
        padding: 1 2;
    }

    #proposal_pane, #plan_pane {
        height: 1fr;
    }

    .node_detail_minimap {
        width: 32;
        max-width: 32;
        height: 1fr;
        max-height: 100%;
    }

    #proposal_content, #plan_content {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }

    #node_detail_buttons {
        dock: bottom;
        height: 3;
        /* Lift the button row one line above the docked Footer (height 1) so
           the buttons' bottom border isn't overdrawn by the footer (t983_5). */
        margin-bottom: 1;
        align: center middle;
    }

    /* Compare matrix overlay (t983_7) — mirrors the node-detail dialog. */
    #compare_matrix_dialog {
        width: 80%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #compare_matrix_title {
        text-style: bold;
        text-align: center;
        dock: top;
        width: 100%;
        padding: 1;
        background: $secondary;
    }

    #compare_matrix_content {
        height: 1fr;
        padding: 1 2;
    }

    /* Operation detail modal (t749_5) */
    #op_detail_dialog {
        width: 80%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #op_detail_title {
        text-style: bold;
        text-align: center;
        dock: top;
        width: 100%;
        padding: 1;
        background: $secondary;
    }

    #op_detail_content {
        height: 1fr;
    }

    #op_detail_loading {
        height: 1fr;
        width: 100%;
    }

    #op_detail_tabs {
        height: 1fr;
    }

    .op_tab_scroll {
        height: 1fr;
        padding: 1 2;
    }

    #op_detail_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    #op_detail_missing {
        padding: 2;
        text-align: center;
        color: $text-muted;
    }

    .op_agent_log {
        padding: 1;
    }

    /* Export node-detail modal */
    #export_modal_dialog {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #export_modal_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        padding-bottom: 1;
    }

    #export_modal_buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    /* Agent launch-mode edit modal */
    #mode_modal_dialog {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #mode_modal_title {
        text-style: bold;
        text-align: center;
        width: 100%;
        padding-bottom: 1;
    }

    #mode_modal_current {
        padding-bottom: 1;
    }

    #mode_modal_note {
        padding-bottom: 1;
    }

    #mode_modal_buttons {
        height: 3;
        align: center middle;
    }

    /* Log browsing widgets (t439_4) */
    StatusLogRow { height: 1; padding: 0 1; }
    StatusLogRow:focus { background: $accent 20%; }

    #log_modal_container {
        width: 90%;
        height: 85%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    #log_modal_title {
        text-style: bold;
        text-align: center;
        dock: top;
        width: 100%;
        padding: 1;
        background: $secondary;
    }

    #log_modal_tabs { height: 1fr; }

    #log_tail_scroll, #log_full_scroll {
        height: 1fr;
        padding: 1 2;
    }

    #log_modal_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    /* Operation help modal */
    #op_help_dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #op_help_title {
        text-style: bold;
        text-align: center;
        dock: top;
        width: 100%;
        padding: 1;
        background: $secondary;
    }

    #op_help_scroll {
        height: 1fr;
        padding: 0 1;
    }

    #op_help_footer {
        dock: bottom;
        width: 100%;
        text-align: center;
        padding: 0 1;
    }

    .runner_bar { height: auto; padding: 0 1; margin-bottom: 1; }

    Button {
        margin: 0 1;
    }
    """
