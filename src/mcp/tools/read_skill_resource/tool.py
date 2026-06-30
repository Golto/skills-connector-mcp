from src.mcp.context import AppRequestContext
from src.mcp.tools.read_skill_resource.models import (
    ReadSkillResourceRequest,
    ReadSkillResourceResponse,
)
from src.mcp.tools.scope_guard import require_skill_in_scope
from src.storage.skill_store import read_skill_resource, resolve_skill_dir


def execute_read_skill_resource(
    request: ReadSkillResourceRequest,
    ctx: AppRequestContext,
) -> ReadSkillResourceResponse:
    """Return the content of a specific file from a skill directory.

    SKILL.md must be read via read_skill, not this tool. Use list_skill_files
    first to discover the available relative paths within the skill.

    Args:
        request: Contains the skill_id and relative_path to read.
        ctx: The active request context carrying scope and registry.

    Returns:
        A ReadSkillResourceResponse with the file's text content.

    Raises:
        SkillNotFoundError: If skill_id is not in the current scope or registry.
        ValueError: If relative_path points to SKILL.md.
        PathEscapeError: If relative_path resolves outside the skill directory.
        FileNotFoundError: If the resource file does not exist.
    """
    require_skill_in_scope(request.skill_id, ctx)

    entry = ctx.registry.skills[request.skill_id]
    skill_dir = resolve_skill_dir(entry.path)
    content = read_skill_resource(skill_dir, request.relative_path)

    return ReadSkillResourceResponse(
        skill_id=request.skill_id,
        relative_path=request.relative_path,
        content=content,
    )
