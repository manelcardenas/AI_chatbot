from collections.abc import Sequence

from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI

from backend.src.domain.ports.model_port import BindableTool, ModelPort
from backend.src.infra.models.model_names import ModelName


class ChatOpenAIModel(ModelPort):
    def __init__(self, model: ChatOpenAI) -> None:
        self._model = model
        self._bound = model
        self._model_name = model.model_name

    @classmethod
    def create(
        cls,
        model_name: ModelName,
        callbacks: list[BaseCallbackHandler] | None = None,
    ) -> "ChatOpenAIModel":
        model = ChatOpenAI(
            model=model_name.value,
            callbacks=callbacks if callbacks else None,
        )
        return cls(model=model)

    def bind_tools(self, tools: Sequence[BindableTool]) -> "ChatOpenAIModel":
        self._bound = self._model.bind_tools(tools)
        return self

    async def ainvoke(self, messages: list) -> object:
        response = await self._bound.ainvoke(messages)
        return response
