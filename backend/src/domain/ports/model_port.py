from abc import ABC, abstractmethod
from typing import Protocol


class BindableTool(Protocol):
    name: str
    description: str


class ModelPort(ABC):
    @abstractmethod
    def bind_tools(self, tools: list[BindableTool]) -> None: ...

    @abstractmethod
    async def ainvoke(self, messages: list) -> object: ...
