from src.mcp.context import AppRequestContext
from src.storage.exceptions import SkillNotFoundError


def require_skill_in_scope(skill_id: str, ctx: AppRequestContext) -> None:
    """Raise SkillNotFoundError if a skill_id is not accessible in the current scope.

    Checks both the in-memory scope list and the registry index, so callers
    get a single clear error regardless of which check fails. This double check
    guards against the edge case where a skill was added to scope in memory
    but the registry was not updated (or vice versa).

    Args:
        skill_id: The skill identifier to validate.
        ctx: The active request context.

    Raises:
        SkillNotFoundError: If the skill is not in scope or not in the registry.
    """
    if skill_id not in ctx.scope.skill_ids or skill_id not in ctx.registry.skills:
        raise SkillNotFoundError(
            f"Skill '{skill_id}' is not available in the current scope."
        )
