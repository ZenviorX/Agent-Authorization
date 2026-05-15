from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    """
    Agent interface.

    Agents may only turn natural-language input into a structured tool-call
    plan. They must not execute tools or make authorization decisions.
    """

    @abstractmethod
    def plan(self, user_input: str) -> Dict[str, Any]:
        pass
