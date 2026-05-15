from backend.agents.base_agent import BaseAgent
from backend.agents.fake_agent import FakeAgent
from backend.agents.llm_agent import LLMAgent


def get_agent(agent_type: str = "fake") -> BaseAgent:
    normalized_type = (agent_type or "fake").strip().lower()

    if normalized_type in {"fake", "fake_agent", "fakeagent"}:
        return FakeAgent()

    if normalized_type in {"llm", "llm_agent", "llmagent"}:
        return LLMAgent()

    raise ValueError(f"Unsupported agent_type: {agent_type}")
