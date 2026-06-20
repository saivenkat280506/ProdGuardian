from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseAgent(ABC):
    """All agents must implement scan() and return list of issues."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """Return True if this agent should process the given file."""
        pass

    @abstractmethod
    def scan(self, file_path: Path, file_content: str) -> list[dict[str, Any]]:
        """Scan a single file and return issues."""
        pass
