from src.mcp.context import AppRequestContext
from src.mcp.tools.list_files.models import MAX_LISTED_ENTRIES, ListFilesRequest, ListFilesResponse
from src.mcp.tools.sandbox_mounts import build_sandbox_mounts
from src.mcp.tools.sandbox_paths import ResolvedSandboxPath, resolve_sandbox_path
from src.storage.file_access import list_directory


def execute_list_files(request: ListFilesRequest, ctx: AppRequestContext) -> ListFilesResponse:
    """List every file under a sandbox directory, as absolute sandbox paths.

    Works on real directories (inside a skill or the workspace) as well as
    on virtual ones made only of mount points ('/', '/skills', or a
    '/workspace' split into named folders), whose listing goes through each
    mount in turn. The returned paths can be passed as they are to read_file,
    write_file or a run_bash_command command.

    Args:
        request: Contains the directory to list.
        ctx: The active request context carrying scope, registry and workspace.

    Returns:
        A ListFilesResponse with the entries, capped at MAX_LISTED_ENTRIES.

    Raises:
        SandboxPathError: If the path is outside every mount.
        PathEscapeError: If a symbolic link leads outside its mount.
        FileNotFoundError: If the directory does not exist.
        NotADirectoryError: If the path is a file.
    """
    resolved = resolve_sandbox_path(request.path, build_sandbox_mounts(ctx))

    if resolved.is_virtual:
        entries, is_truncated = _list_virtual_directory(resolved)
    else:
        entries, is_truncated = _list_real_directory(resolved)

    return ListFilesResponse(
        path=str(resolved.sandbox_path),
        entries=entries,
        is_truncated=is_truncated,
    )


def _list_real_directory(resolved: ResolvedSandboxPath) -> tuple[list[str], bool]:
    """List a directory located inside one mount.

    Args:
        resolved: A resolved, non-virtual sandbox path.

    Returns:
        The absolute sandbox paths and whether the listing was truncated.

    Raises:
        FileNotFoundError: If the directory does not exist.
        NotADirectoryError: If the path is a file.
    """
    if not resolved.host_path.exists():
        raise FileNotFoundError(f"Directory not found: {resolved.sandbox_path}")
    if not resolved.host_path.is_dir():
        raise NotADirectoryError(
            f"'{resolved.sandbox_path}' is a file. Use read_file to read it."
        )

    listing = list_directory(resolved.host_path, MAX_LISTED_ENTRIES)
    entries = [f"{resolved.sandbox_path}/{entry}" for entry in listing.entries]
    return entries, listing.is_truncated


def _list_virtual_directory(resolved: ResolvedSandboxPath) -> tuple[list[str], bool]:
    """List a virtual directory by walking each mount located under it.

    An empty mount is still listed, as '<mount>/', so that a fresh workspace
    shows up rather than vanishing from the listing.

    Args:
        resolved: A resolved, virtual sandbox path.

    Returns:
        The absolute sandbox paths and whether the listing was truncated.
    """
    entries: list[str] = []

    for mount in resolved.child_mounts:
        remaining_entries = MAX_LISTED_ENTRIES - len(entries)
        if remaining_entries <= 0:
            return entries, True

        listing = list_directory(mount.host_path, remaining_entries)
        if not listing.entries:
            entries.append(f"{mount.sandbox_path}/")
        entries.extend(f"{mount.sandbox_path}/{entry}" for entry in listing.entries)
        if listing.is_truncated:
            return entries, True

    return entries, False
