from pydantic import BaseModel, Field


class ResearchPlan(BaseModel):
    steps: list[str] = Field(description="List of research steps to execute")
    query: str = Field(description="The original user query")
