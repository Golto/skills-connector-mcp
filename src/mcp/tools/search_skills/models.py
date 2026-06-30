from pydantic import BaseModel, Field

from src.mcp.tools.shared_models import SkillSummary


class SearchSkillsRequest(BaseModel):
    """Input for the search_skills tool.

    Attributes:
        query: Free-text query. All words must match (AND semantics) against
            each skill's id, description, triggers, and tags.
        limit: Maximum number of results to return. None means no limit.
    """

    query: str
    limit: int | None = Field(default=None, gt=0)


class SearchSkillsResponse(BaseModel):
    """Response returned by the search_skills tool.

    Attributes:
        skills: Skills from the current scope that match all query words.
    """

    skills: list[SkillSummary]
