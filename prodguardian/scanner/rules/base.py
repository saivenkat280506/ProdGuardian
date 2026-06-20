from abc import ABC, abstractmethod


class Rule(ABC):
    @property
    @abstractmethod
    def id(self) -> str:
        pass

    @property
    @abstractmethod
    def severity(self) -> str:
        pass

    @abstractmethod
    def check(self, ast_data: dict) -> list:
        """Return list of dicts: {'line': int, 'message': str, 'code_snippet': str}"""
        pass
