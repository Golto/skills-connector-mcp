from src.mcp.context import AppRequestContext
from src.mcp.tools.run_bash_command.docker_runner import run_docker_container
from src.mcp.tools.run_bash_command.models import RunBashCommandRequest, RunBashCommandResponse
from src.mcp.tools.run_bash_command.sandbox_mounts import build_sandbox_mounts
from src.storage.workspace import SANDBOX_WORKSPACE_ROOT


async def execute_run_bash_command(
    request: RunBashCommandRequest,
    ctx: AppRequestContext,
) -> RunBashCommandResponse:
    """Run a shell command in a disposable sandbox holding the skills and the workspace.

    Every skill of the scope is mounted read-only under /skills, and the
    workspace read-write under /workspace, which is also the working
    directory. The workspace is made of host directories, so whatever the
    command writes there persists after the container is gone and is visible
    to the host (and to any other tool working on the same directories)
    without any id to carry between calls.

    Args:
        request: Contains the command to run and its timeout.
        ctx: The active request context carrying scope, registry and workspace.

    Returns:
        A RunBashCommandResponse with the exit code and the bounded output.

    Raises:
        FileNotFoundError: If the 'docker' binary is not available on the host.
    """
    result = await run_docker_container(
        mounts=build_sandbox_mounts(ctx),
        working_dir=SANDBOX_WORKSPACE_ROOT,
        command=request.command,
        timeout_seconds=request.timeout_seconds,
    )

    stderr = result.stderr.text
    if result.timed_out:
        stderr += (
            f"\nCommand killed after {request.timeout_seconds} seconds. "
            "Files it wrote to /workspace before that are kept."
        )

    return RunBashCommandResponse(
        exit_code=result.exit_code,
        stdout=result.stdout.text,
        stderr=stderr,
        is_output_truncated=result.stdout.is_truncated or result.stderr.is_truncated,
    )
