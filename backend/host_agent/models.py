from pydantic import BaseModel
from backend.host_agent.utils import Language

class AgentStructuredResponse(BaseModel):
    response: str
    language: Language
