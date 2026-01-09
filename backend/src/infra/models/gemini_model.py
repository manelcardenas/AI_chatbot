from collections.abc import Sequence

from langchain_core.callbacks import BaseCallbackHandler
from langchain_google_genai import ChatGoogleGenerativeAI

from backend.src.domain.ports.model_port import BindableTool, ModelPort
from backend.src.infra.models.model_names import ModelName


class ChatGoogleGenerativeAIModel(ModelPort):
    def __init__(self, model: ChatGoogleGenerativeAI) -> None:
        self._model = model
        self._bound = model
        self._model_name = model.model

    @classmethod
    def create(
        cls,
        model_name: ModelName,
        callbacks: list[BaseCallbackHandler] | None = None,
    ) -> "ChatGoogleGenerativeAIModel":
        model = ChatGoogleGenerativeAI(
            model=model_name.value,
            callbacks=callbacks if callbacks else None,
            temperature=0.0,
            thinking_budget=0,
        )
        return cls(model=model)

    def bind_tools(self, tools: Sequence[BindableTool]) -> "ChatGoogleGenerativeAIModel":
        self._bound = self._model.bind_tools(tools)
        return self

    async def ainvoke(self, messages: list) -> object:
        response = await self._bound.ainvoke(messages)
        return response
