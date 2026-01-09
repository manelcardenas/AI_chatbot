from abc import ABC, abstractmethod

from backend.src.app import ChatbotState
from backend.src.app.workflow.prompts import PromptCreator
from backend.src.app.workflow.tools import BaseTool
from backend.src.domain.ports import ModelPort


class BaseNode(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def ainvoke(self, state: ChatbotState) -> ChatbotState: ...


class AgenticNode(BaseNode):
    def __init__(self, name: str, tools: list[BaseTool], model: ModelPort, prompts: PromptCreator) -> None:
        super().__init__(name=name)
        self.tools = tools
        self.model = model
        self.prompts = prompts
        self.model.bind_tools(tools)
