from pydantic import BaseModel

from src.mcp.tools.shared_models import SkillSummary


class ListSkillsResponse(BaseModel):
    """Response returned by the list_skills tool.

    Attributes:
        skills: All skills visible in the current scope, in scope order.
    """

    skills: list[SkillSummary]
