from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel


class ChatbotState(BaseModel):
    user_id: str
    metadata: dict[str, str] = {}
    messages: Annotated[list[BaseMessage], add_messages]
