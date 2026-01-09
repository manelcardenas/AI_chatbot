from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Protocol


class BindableTool(Protocol):
    name: str
    description: str


class ModelPort(ABC):
    @abstractmethod
    def bind_tools(self, tools: Sequence[BindableTool]) -> "ModelPort": ...

    @abstractmethod
    async def ainvoke(self, messages: list) -> object: ...
