from typing import Annotated

from pydantic import BaseModel, Field

from src.mcp.tools.shared_models import SkillSummary


QueryParameter = Annotated[
    str,
    Field(
        min_length=1,
        description=(
            "Space-separated keywords. A skill matches only if ALL words appear in "
            "its id, description, triggers or tags. Use one or two short words."
        ),
    ),
]

LimitParameter = Annotated[
    int | None,
    Field(gt=0, description="Maximum number of results. Omit for no limit."),
]


class SearchSkillsRequest(BaseModel):
    """Input for the search_skills tool.

    Attributes:
        query: Free-text query. All words must match (AND semantics) against
            each skill's id, description, triggers, and tags.
        limit: Maximum number of results to return. None means no limit.
    """

    query: QueryParameter
    limit: LimitParameter = None


class SearchSkillsResponse(BaseModel):
    """Response returned by the search_skills tool.

    Attributes:
        skills: Skills from the current scope that match all query words.
    """

    skills: list[SkillSummary]
