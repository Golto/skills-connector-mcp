from src.mcp.context import AppRequestContext
from src.mcp.tools.sandbox_mounts import BindMount, build_sandbox_mounts
from src.mcp.tools.sandbox_paths import resolve_sandbox_path
from src.mcp.tools.write_file.models import WriteFileRequest, WriteFileResponse
from src.storage.exceptions import SandboxPathError
from src.storage.file_access import write_text_file_atomic
from src.storage.models import ServerScope
from src.storage.workspace import WorkspaceLayout, WorkspaceSource


def is_write_file_available(scope: ServerScope, workspace: WorkspaceLayout) -> bool:
    """Tell whether the write_file tool is registered for this server process.

    It needs execution to be allowed (without it, the workspace has no use),
    and is left out when the client passed a paths.json: that client already
    runs a file writer on the same directories, and two competing write
    tools confuse small models.

    Args:
        scope: The scope built from the loaded profile.
        workspace: The resolved workspace layout.

    Returns:
        True if write_file is registered.
    """
    return scope.allow_execution and workspace.source != WorkspaceSource.PATHS_DIR


def execute_write_file(request: WriteFileRequest, ctx: AppRequestContext) -> WriteFileResponse:
    """Write a text file in the workspace, creating missing parent directories.

    Meant for small agents that struggle to write files through a shell
    command (quoting, heredocs, escaping). The file lands directly in the
    host directory behind the workspace, so it is immediately visible to
    run_bash_command and to the host.

    Args:
        request: Contains the file path and its full content.
        ctx: The active request context carrying scope, registry and workspace.

    Returns:
        A WriteFileResponse with the normalized path and the written size.

    Raises:
        SandboxPathError: If the path is outside every mount, read-only
            (a skill), or a virtual directory.
        PathEscapeError: If a symbolic link leads outside its mount.
        IsADirectoryError: If the path is an existing directory.
        OSError: If the file cannot be written.
    """
    mounts = build_sandbox_mounts(ctx)
    resolved = resolve_sandbox_path(request.path, mounts)

    if resolved.is_virtual or not resolved.is_writable:
        raise SandboxPathError(
            f"'{resolved.sandbox_path}' is not writable. Write under: "
            f"{_describe_writable_roots(mounts)}."
        )

    try:
        was_created = write_text_file_atomic(resolved.host_path, request.content)
    except IsADirectoryError as error:
        raise IsADirectoryError(f"'{resolved.sandbox_path}' is a directory.") from error

    return WriteFileResponse(
        path=str(resolved.sandbox_path),
        size_bytes=resolved.host_path.stat().st_size,
        was_created=was_created,
    )


def _describe_writable_roots(mounts: list[BindMount]) -> str:
    """List the writable mount points, for an error message the agent can act on."""
    return ", ".join(f"{mount.sandbox_path}/" for mount in mounts if not mount.is_read_only)
