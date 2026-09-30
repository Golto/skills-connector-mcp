from typing import Annotated

from pydantic import BaseModel, Field

from src.storage.models import SkillOrigin


# ----------------------------------------------------------------
# Tool parameter types
# ----------------------------------------------------------------

# NOTE: parameter aliases (this one and the tool-specific ones in each
# tools/<name>/models.py) are shared by the Pydantic request models AND the
# flat @mcp.tool() signatures in server.py, so that each parameter's
# description and constraints live in a single place and reach the tool's
# JSON schema, which is all a model sees of the tool.
SkillIdParameter = Annotated[
    str,
    Field(
        min_length=1,
        description="Identifier of the skill, as listed in the skills index or by list_skills.",
    ),
]


# ----------------------------------------------------------------
# Shared response models
# ----------------------------------------------------------------


class SkillSummary(BaseModel):
    """Condensed skill metadata returned by list_skills and search_skills.

    Attributes:
        skill_id: Unique identifier of the skill.
        description: Short description from the skill's SKILL.md frontmatter.
        tags: Domain tags for grouping and filtering.
        origin: Whether the skill is from base/ or generated/.
        has_resources: True if the skill has files beyond SKILL.md.
    """

    skill_id: str
    description: str
    tags: list[str]
    origin: SkillOrigin
    has_resources: bool
