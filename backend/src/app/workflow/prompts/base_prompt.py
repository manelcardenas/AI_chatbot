from abc import ABC, abstractmethod


class PromptCreator(ABC):
    @abstractmethod
    def system_prompt(self) -> str: ...
