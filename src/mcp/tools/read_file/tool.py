from src.mcp.context import AppRequestContext
from src.mcp.tools.read_file.models import (
    MAX_READ_BYTES,
    MAX_READABLE_FILE_SIZE_BYTES,
    ReadFileRequest,
    ReadFileResponse,
)
from src.mcp.tools.sandbox_mounts import build_sandbox_mounts
from src.mcp.tools.sandbox_paths import resolve_sandbox_path
from src.storage.file_access import read_text_file_slice


def execute_read_file(request: ReadFileRequest, ctx: AppRequestContext) -> ReadFileResponse:
    """Read a text file of the sandbox, a skill file or a workspace file alike.

    Returns whole lines from start_line, up to MAX_READ_BYTES of content. A
    longer file is read in several calls, following next_start_line, rather
    than flooding the agent's context in one go.

    Args:
        request: Contains the file path and the first line to read.
        ctx: The active request context carrying scope, registry and workspace.

    Returns:
        A ReadFileResponse with the lines and where to continue.

    Raises:
        SandboxPathError: If the path is outside every mount.
        PathEscapeError: If a symbolic link leads outside its mount.
        IsADirectoryError: If the path is a directory.
        FileNotFoundError: If the file does not exist.
        NonTextFileError: If the file is binary, not UTF-8, or too large.
        ValueError: If start_line is past the end of the file.
    """
    resolved = resolve_sandbox_path(request.path, build_sandbox_mounts(ctx))

    if resolved.is_virtual:
        raise IsADirectoryError(
            f"'{resolved.sandbox_path}' is a directory. Use list_files to see its content."
        )

    try:
        file_slice = read_text_file_slice(
            host_path=resolved.host_path,
            start_line=request.start_line,
            max_bytes=MAX_READ_BYTES,
            max_file_size_bytes=MAX_READABLE_FILE_SIZE_BYTES,
        )
    except FileNotFoundError as error:
        raise FileNotFoundError(f"File not found: {resolved.sandbox_path}") from error
    except IsADirectoryError as error:
        raise IsADirectoryError(
            f"'{resolved.sandbox_path}' is a directory. Use list_files to see its content."
        ) from error

    return ReadFileResponse(
        path=str(resolved.sandbox_path),
        content=file_slice.content,
        start_line=file_slice.start_line,
        end_line=file_slice.end_line,
        total_lines=file_slice.total_lines,
        next_start_line=file_slice.next_start_line,
    )
