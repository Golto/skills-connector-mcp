from typing import Annotated

from pydantic import BaseModel, Field

from src.mcp.tools.shared_models import SkillIdParameter


RelativePathParameter = Annotated[
    str,
    Field(
        min_length=1,
        description=(
            "Path of the file relative to the skill's root directory, as returned "
            "by list_skill_files. SKILL.md is read with read_skill instead."
        ),
    ),
]


class ReadSkillResourceRequest(BaseModel):
    """Input for the read_skill_resource tool.

    Attributes:
        skill_id: Identifier of the skill that owns the resource.
        relative_path: Path to the file relative to the skill's root directory.
            Obtain valid paths from list_skill_files first.
    """

    skill_id: SkillIdParameter
    relative_path: RelativePathParameter


class ReadSkillResourceResponse(BaseModel):
    """Response returned by the read_skill_resource tool.

    Attributes:
        skill_id: Identifier of the skill that owns the resource.
        relative_path: The path that was read, echoed back for clarity.
        content: Full text content of the resource file.
    """

    skill_id: str
    relative_path: str
    content: str
