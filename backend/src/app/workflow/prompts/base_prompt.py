from abc import ABC, abstractmethod


class PromptManager(ABC):
    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def research_plan_prompt(self) -> str: ...
