import os

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tracers import LangChainTracer

from backend.src.domain.ports.model_port import ModelPort
from backend.src.infra.models.gemini_model import ChatGoogleGenerativeAIModel
from backend.src.infra.models.model_names import ModelName, ModelProvider
from backend.src.infra.models.openai_model import ChatOpenAIModel


class ModelFactory:
    def __init__(self) -> None:
        self.callbacks: list[BaseCallbackHandler] = []

        # Initialize tracer if needed
        if os.getenv("ENABLE_LANGSMITH_TRACKING", "false").lower() == "true":
            project_name = os.getenv("LANGCHAIN_PROJECT")
            if not project_name:
                raise ValueError("LANGCHAIN_PROJECT must be set when ENABLE_LANGSMITH_TRACKING is enabled")
            tracer = LangChainTracer(project_name=project_name)
            self.callbacks.append(tracer)

    def get_model(self, model_name: ModelName) -> ModelPort:
        provider = model_name.provider

        if provider == ModelProvider.GEMINI:
            return ChatGoogleGenerativeAIModel.create(model_name, self.callbacks)
        elif provider == ModelProvider.OPENAI:
            return ChatOpenAIModel.create(model_name, self.callbacks)
        else:
            raise ValueError(f"Unsupported model provider: {provider}")
