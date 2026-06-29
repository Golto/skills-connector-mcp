from pydantic import BaseModel

from src.storage.models import SkillOrigin


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
