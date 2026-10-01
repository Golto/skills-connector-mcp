import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from src.storage.workspace import WorkspaceMount


@dataclass(frozen=True)
class FileSignature:
    """What identifies one version of a file, cheaply, without reading it.

    Attributes:
        size_bytes: File size.
        modified_ns: Last modification time, in nanoseconds.
    """

    size_bytes: int
    modified_ns: int


@dataclass(frozen=True)
class WorkspaceSnapshot:
    """Signatures of every file of the workspace at one point in time.

    Attributes:
        files: Signature of each file, keyed by its path inside the sandbox.
        is_complete: False if the scan stopped at the file limit, in which
            case the snapshot cannot be used to detect changes.
    """

    files: dict[PurePosixPath, FileSignature]
    is_complete: bool


@dataclass(frozen=True)
class WorkspaceChanges:
    """Files of the workspace that a command created, modified or deleted.

    Attributes:
        changed_files: Created or modified files, as sorted sandbox paths.
        deleted_files: Deleted files, as sorted sandbox paths.
    """

    changed_files: list[str]
    deleted_files: list[str]


def take_workspace_snapshot(
    mounts: tuple[WorkspaceMount, ...],
    max_files: int,
) -> WorkspaceSnapshot:
    """Record the signature of every file under the workspace mounts.

    Only metadata is read (one lstat per file), never the content. Symbolic
    links are recorded as entries but never followed, so a link cannot drag
    the scan outside the workspace. Unreadable directories are skipped.
    Blocking: call it through asyncio.to_thread from async code.

    Args:
        mounts: The workspace mounts, mapping host directories to sandbox paths.
        max_files: Number of files after which the scan gives up.

    Returns:
        The snapshot, marked incomplete if max_files was reached.
    """
    files: dict[PurePosixPath, FileSignature] = {}

    for mount in mounts:
        for directory, _, file_names in os.walk(mount.host_path, followlinks=False):
            directory_path = Path(directory)
            for file_name in file_names:
                if len(files) >= max_files:
                    return WorkspaceSnapshot(files=files, is_complete=False)

                host_file = directory_path / file_name
                try:
                    stat_result = host_file.lstat()
                except OSError:
                    continue

                relative_path = host_file.relative_to(mount.host_path).as_posix()
                files[mount.sandbox_path / relative_path] = FileSignature(
                    size_bytes=stat_result.st_size,
                    modified_ns=stat_result.st_mtime_ns,
                )

    return WorkspaceSnapshot(files=files, is_complete=True)


def compute_workspace_changes(
    before: WorkspaceSnapshot,
    after: WorkspaceSnapshot,
) -> WorkspaceChanges | None:
    """Compare two snapshots of the workspace.

    A file counts as changed when it is new or when its size or modification
    time differs. Writes made by other processes during the command (another
    MCP server working on the same directories, for instance) are reported
    too, since they cannot be told apart.

    Args:
        before: Snapshot taken before the command.
        after: Snapshot taken after the command.

    Returns:
        The changes, or None if either snapshot is incomplete.
    """
    if not (before.is_complete and after.is_complete):
        return None

    changed_files = [
        str(path)
        for path, signature in after.files.items()
        if before.files.get(path) != signature
    ]
    deleted_files = [str(path) for path in before.files if path not in after.files]

    return WorkspaceChanges(
        changed_files=sorted(changed_files),
        deleted_files=sorted(deleted_files),
    )


def limit_path_list(paths: list[str], max_entries: int) -> list[str]:
    """Shorten a path list for the response, saying how many were left out.

    Args:
        paths: Sorted sandbox paths.
        max_entries: Maximum number of paths kept.

    Returns:
        The list unchanged if short enough, else its first max_entries paths
        followed by a '... and N more' entry.
    """
    if len(paths) <= max_entries:
        return paths
    return paths[:max_entries] + [f"... and {len(paths) - max_entries} more"]
