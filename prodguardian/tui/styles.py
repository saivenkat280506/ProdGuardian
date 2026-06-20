"""Shared TUI styles — high contrast and Windows-terminal safe."""

GLOBAL_CSS = """
/* Readable text on every surface */
Screen {
    background: $background;
    color: $foreground;
}

Static, Label, RadioButton, TabPane, DirectoryTree, Select {
    color: $foreground;
}

RichLog {
    color: $foreground;
    background: $surface;
}

Input {
    color: $foreground;
    background: $surface;
    border: tall $primary;
    min-height: 3;
}

Select {
    background: $surface;
    border: tall $primary;
}

/* Buttons need room for borders — clipping hides label text on Windows */
Button {
    color: $button-foreground;
    background: $panel;
    border: tall $primary;
    text-style: bold;
    min-height: 3;
    height: 3;
    content-align: center middle;
    width: auto;
}

Button.-primary {
    background: $primary;
    color: $button-color-foreground;
}

Button.-primary:hover {
    background: $primary-lighten-1;
}

Button:hover {
    background: $panel-lighten-1;
}

Button:disabled {
    opacity: 0.65;
    color: $foreground-disabled;
}

#status-msg {
    color: $foreground;
}

.section-title {
    text-style: bold;
    color: $text-accent;
    width: 100%;
    height: auto;
    margin-bottom: 1;
}

.field-hint {
    color: $foreground-muted;
    width: 100%;
    height: auto;
    margin-bottom: 1;
}
"""

MODAL_CSS = """
/* Shared responsive modal dialog sizing */
.modal-dialog {
    width: 96%;
    height: 94%;
    min-width: 72;
    min-height: 26;
    max-width: 150;
    max-height: 66;
    layout: vertical;
    border: solid $primary;
    background: $surface;
    color: $foreground;
    padding: 1 2;
}

.layout-compact .modal-dialog {
    width: 100%;
    height: 100%;
    min-height: 20;
    padding: 1;
}

.layout-expanded .modal-dialog {
    width: 88%;
    height: 88%;
    max-width: 170;
    max-height: 78;
}
"""

MAIN_LAYOUT_CSS = """
/* Main screen spacing — single column, aligned edges */
#main-column {
    height: 1fr;
}

.layout-compact #chat-container {
    min-height: 6;
}

.layout-compact #actions {
    min-height: 3;
}

.layout-expanded #chat-container {
    min-height: 14;
}

/* Shrink chrome while scan/audit is running so controls stay visible */
.operation-active #logo {
    display: none;
    height: 0;
    margin: 0;
    border: none;
}

.operation-active #chat-container {
    min-height: 3;
}

.layout-compact.operation-active #chat-container {
    min-height: 2;
}

.layout-compact OperationProgressPanel {
    max-height: 7;
    padding: 0 1;
}

.layout-compact OperationProgressPanel #progress-stages-scroll {
    display: none;
}

.layout-compact OperationProgressPanel #progress-current {
    display: block;
}

.layout-comfortable OperationProgressPanel {
    max-height: 10;
}

.layout-comfortable OperationProgressPanel #progress-stages-scroll {
    height: 3;
    max-height: 3;
}

.layout-expanded OperationProgressPanel {
    max-height: 12;
}

.layout-expanded OperationProgressPanel #progress-stages-scroll {
    height: 5;
    max-height: 5;
}

.layout-compact #bottom-panel {
    max-height: 9;
}

.layout-comfortable #bottom-panel {
    max-height: 12;
}

#audit-btn.auditing {
    background: $warning;
    color: $text;
}
"""