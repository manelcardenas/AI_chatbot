from enum import Enum


class ModelProvider(Enum):
    """Supported language model providers."""

    OPENAI = "openai"
    GEMINI = "gemini"


class ModelName(Enum):
    """Supported model names for each provider."""

    # OpenAI
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4_1 = "gpt-4.1"

    # Gemini
    GEMINI_3_0_FLASH = "gemini-3-flash-preview"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"

    @property
    def provider(self) -> ModelProvider:
        openai_models = {ModelName.GPT_4O, ModelName.GPT_4O_MINI, ModelName.GPT_4_1}
        if self in openai_models:
            return ModelProvider.OPENAI
        return ModelProvider.GEMINI
