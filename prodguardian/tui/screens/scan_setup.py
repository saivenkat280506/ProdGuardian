"""Scan setup entry point — same UI as settings, scan-specific flow."""

from prodguardian.tui.screens.llm_config import LLMConfigScreen


class ScanSetupScreen(LLMConfigScreen):
    def __init__(self):
        super().__init__(mode="scan")