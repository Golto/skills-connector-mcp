from pydantic import BaseModel

from src.mcp.tools.shared_models import SkillIdParameter


class ReadSkillRequest(BaseModel):
    """Input for the read_skill tool.

    Attributes:
        skill_id: Identifier of the skill whose SKILL.md should be returned.
    """

    skill_id: SkillIdParameter


class ReadSkillResponse(BaseModel):
    """Response returned by the read_skill tool.

    Attributes:
        skill_id: Identifier of the skill that was read.
        content: Full text content of SKILL.md.
    """

    skill_id: str
    content: str
