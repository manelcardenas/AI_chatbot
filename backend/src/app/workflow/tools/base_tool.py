from abc import ABC, abstractmethod


class BaseTool(ABC):
    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def process(self, *args, **kwargs) -> object: ...
