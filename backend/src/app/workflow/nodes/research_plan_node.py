from backend.src.app import ChatbotState
from backend.src.app.workflow.nodes.base_node import LLMNode
from backend.src.app.workflow.prompts import PromptManager
from backend.src.domain.entities.plan import ResearchPlan
from backend.src.domain.ports import ModelPort


class ResearchPlanNode(LLMNode):
    def __init__(
        self,
        model: ModelPort,
        prompts: PromptManager,
        name: str = "research_plan",
    ) -> None:
        super().__init__(name=name, model=model, prompts=prompts)

    async def ainvoke(self, state: ChatbotState) -> ResearchPlan:
        research_plan_messages = self.prompts.research_plan_prompt()
        messages = [{"role": "system", "content": research_plan_messages}] + list(state.messages)
        structured_model = self.model.with_structured_output(ResearchPlan)
        return await structured_model.ainvoke(messages)
