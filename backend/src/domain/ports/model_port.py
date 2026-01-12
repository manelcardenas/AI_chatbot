from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel


class BindableTool(Protocol):
    name: str
    description: str


class ModelPort(ABC):
    @abstractmethod
    def bind_tools(self, tools: Sequence[BindableTool]) -> "ModelPort": ...

    @abstractmethod
    def with_structured_output(self, schema: type[BaseModel]) -> "ModelPort": ...

    @abstractmethod
    async def ainvoke(self, messages: list) -> object: ...
