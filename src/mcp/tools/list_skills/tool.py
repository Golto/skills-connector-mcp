from src.mcp.context import AppRequestContext
from src.mcp.tools.list_skills.models import ListSkillsResponse
from src.mcp.tools.shared_models import SkillSummary


def execute_list_skills(ctx: AppRequestContext) -> ListSkillsResponse:
    """Build the list of all skills visible in the current scope.

    Skills present in the scope but absent from the registry (e.g. after a
    manual deletion) are silently skipped rather than raising an error, as
    the registry sync at startup is the authoritative reconciliation step.

    Args:
        ctx: The active request context carrying scope and registry.

    Returns:
        A ListSkillsResponse with one SkillSummary per visible skill.
    """
    skills = []
    for skill_id in ctx.scope.skill_ids:
        entry = ctx.registry.skills.get(skill_id)
        if entry is None:
            continue
        skills.append(
            SkillSummary(
                skill_id=skill_id,
                description=entry.description,
                tags=entry.tags,
                origin=entry.origin,
                has_resources=entry.has_resources,
            )
        )
    return ListSkillsResponse(skills=skills)
