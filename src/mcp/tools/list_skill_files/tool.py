from src.mcp.context import AppRequestContext
from src.mcp.tools.list_skill_files.models import ListSkillFilesRequest, ListSkillFilesResponse
from src.mcp.tools.scope_guard import require_skill_in_scope
from src.storage.skill_store import list_skill_files, resolve_skill_dir


def execute_list_skill_files(
    request: ListSkillFilesRequest,
    ctx: AppRequestContext,
) -> ListSkillFilesResponse:
    """Return the sorted list of files in a skill directory.

    Use this before read_skill_resource to discover available relative paths,
    since a skill's internal structure is not fixed by the spec.

    Args:
        request: Contains the skill_id to inspect.
        ctx: The active request context carrying scope and registry.

    Returns:
        A ListSkillFilesResponse with relative file paths (manifest.json excluded).

    Raises:
        SkillNotFoundError: If skill_id is not in the current scope or registry.
    """
    require_skill_in_scope(request.skill_id, ctx)

    entry = ctx.registry.skills[request.skill_id]
    skill_dir = resolve_skill_dir(entry.path)
    files = list_skill_files(skill_dir)

    return ListSkillFilesResponse(skill_id=request.skill_id, files=files)
