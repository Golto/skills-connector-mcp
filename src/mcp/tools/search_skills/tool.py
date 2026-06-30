from src.mcp.context import AppRequestContext
from src.mcp.tools.search_skills.models import SearchSkillsRequest, SearchSkillsResponse
from src.mcp.tools.shared_models import SkillSummary


def execute_search_skills(
    request: SearchSkillsRequest,
    ctx: AppRequestContext,
) -> SearchSkillsResponse:
    """Search for skills whose metadata matches all words in the query.

    Each query word is checked case-insensitively against the concatenation of
    the skill's id, description, triggers, and tags. All words must match (AND
    semantics): a query of 'python style' only returns skills that contain both
    words somewhere in their searchable text.

    Results are returned in scope order and capped at request.limit if set.
    Skills present in the scope but absent from the registry are silently skipped.

    Args:
        request: Contains the query string and optional result limit.
        ctx: The active request context carrying scope and registry.

    Returns:
        A SearchSkillsResponse with matching skills, at most request.limit entries.
    """
    query_words = request.query.lower().split()

    matching_skills: list[SkillSummary] = []
    for skill_id in ctx.scope.skill_ids:
        if request.limit is not None and len(matching_skills) >= request.limit:
            break

        entry = ctx.registry.skills.get(skill_id)
        if entry is None:
            continue

        searchable_text = " ".join(
            [skill_id, entry.description, *entry.triggers, *entry.tags]
        ).lower()

        if all(word in searchable_text for word in query_words):
            matching_skills.append(
                SkillSummary(
                    skill_id=skill_id,
                    description=entry.description,
                    tags=entry.tags,
                    origin=entry.origin,
                    has_resources=entry.has_resources,
                )
            )

    return SearchSkillsResponse(skills=matching_skills)
