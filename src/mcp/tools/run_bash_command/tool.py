from src.mcp.context import AppRequestContext
from src.mcp.tools.run_bash_command.docker_runner import run_docker_container
from src.mcp.tools.run_bash_command.models import RunBashCommandRequest, RunBashCommandResponse
from src.mcp.tools.scope_guard import require_skill_in_scope
from src.storage.scratch import generate_scratch_id, list_scratch_files, resolve_scratch_dir
from src.storage.skill_store import resolve_skill_dir


def execute_run_bash_command(
    request: RunBashCommandRequest,
    ctx: AppRequestContext,
) -> RunBashCommandResponse:
    """Run a shell command in a disposable Docker container scoped to one skill.

    The skill's root directory is mounted read-only at /skill so the command
    can never modify the skill it belongs to during execution. The scratch
    directory mounted read-write at /workspace is either freshly created or
    reused from a previous call, depending on request.scratch_id, so an agent
    can iterate against the same /workspace across multiple calls. The
    scratch directory is kept on disk after the call returns, so the agent
    can retrieve any output files via workspace_path.

    Args:
        request: Contains skill_id, the command to run, a timeout, and an
            optional scratch_id to reuse an existing workspace.
        ctx: The active request context carrying scope and registry.

    Returns:
        A RunBashCommandResponse with stdout, stderr, exit_code, the list of
        files found in the scratch directory after execution, its absolute
        host path, and the scratch_id to reuse in a follow-up call.

    Raises:
        SkillNotFoundError: If skill_id is not in the current scope or registry.
        PathEscapeError: If request.scratch_id contains invalid characters.
        FileNotFoundError: If the 'docker' binary is not available on the host.
    """
    require_skill_in_scope(request.skill_id, ctx)

    entry = ctx.registry.skills[request.skill_id]
    skill_dir = resolve_skill_dir(entry.path)

    scratch_id = request.scratch_id or generate_scratch_id()
    scratch_dir = resolve_scratch_dir(scratch_id)

    result = run_docker_container(
        skill_dir=skill_dir,
        scratch_dir=scratch_dir,
        command=request.command,
        timeout_seconds=request.timeout_seconds,
    )

    return RunBashCommandResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        output_files=list_scratch_files(scratch_dir),
        workspace_path=str(scratch_dir),
        scratch_id=scratch_id,
    )
