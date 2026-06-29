from src.mcp.context import AppRequestContext
from src.mcp.tools.read_skill.models import ReadSkillRequest, ReadSkillResponse
from src.mcp.tools.scope_guard import require_skill_in_scope
from src.storage.skill_store import read_skill_content, resolve_skill_dir


def execute_read_skill(
    request: ReadSkillRequest,
    ctx: AppRequestContext,
) -> ReadSkillResponse:
    """Return the full content of a skill's SKILL.md.

    Args:
        request: Contains the skill_id to read.
        ctx: The active request context carrying scope and registry.

    Returns:
        A ReadSkillResponse with the raw SKILL.md text.

    Raises:
        SkillNotFoundError: If skill_id is not in the current scope or registry.
    """
    require_skill_in_scope(request.skill_id, ctx)

    entry = ctx.registry.skills[request.skill_id]
    skill_dir = resolve_skill_dir(entry.path)
    content = read_skill_content(skill_dir)

    return ReadSkillResponse(skill_id=request.skill_id, content=content)
