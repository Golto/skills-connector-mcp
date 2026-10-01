import posixpath
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from src.mcp.tools.sandbox_mounts import BindMount
from src.storage.exceptions import PathEscapeError, SandboxPathError
from src.storage.workspace import SANDBOX_WORKSPACE_ROOT


@dataclass(frozen=True)
class ResolvedSandboxPath:
    """A sandbox path matched against the sandbox mounts.

    Either a real location inside one mount (host_path set), or a virtual
    directory that only exists as the parent of mount points, such as '/',
    '/skills' or a '/workspace' made of named mounts (host_path None).

    Attributes:
        sandbox_path: Normalized absolute path inside the sandbox.
        host_path: Matching host path, None for a virtual directory.
        is_writable: Whether the path lies in a read-write mount.
        mount: The mount containing the path, None for a virtual directory.
        child_mounts: Mounts located under a virtual directory, empty otherwise.
    """

    sandbox_path: PurePosixPath
    host_path: Path | None
    is_writable: bool
    mount: BindMount | None
    child_mounts: tuple[BindMount, ...]

    @property
    def is_virtual(self) -> bool:
        """Whether the path is a virtual directory holding mount points."""
        return self.host_path is None


def normalize_sandbox_path(raw_path: str) -> PurePosixPath:
    """Turn a path given by the agent into a normalized absolute sandbox path.

    Relative paths are taken from /workspace, the working directory of
    run_bash_command, so 'out/plot.png' means the same thing in every tool.
    '.' and '..' components are collapsed lexically, so '/workspace/../etc'
    becomes '/etc' and is then rejected for lying outside every mount.

    Args:
        raw_path: Path as written by the agent.

    Returns:
        The normalized absolute path.

    Raises:
        SandboxPathError: If the path is empty.
    """
    stripped_path = raw_path.strip()
    if not stripped_path:
        raise SandboxPathError("Path is empty.")

    if not stripped_path.startswith("/"):
        stripped_path = f"{SANDBOX_WORKSPACE_ROOT}/{stripped_path}"

    # NOTE: posixpath.normpath keeps exactly two leading slashes ('//x'), so
    # they are collapsed first.
    return PurePosixPath(posixpath.normpath("/" + stripped_path.lstrip("/")))


def resolve_sandbox_path(raw_path: str, mounts: list[BindMount]) -> ResolvedSandboxPath:
    """Resolve a sandbox path to the host location it stands for.

    The deepest mount containing the path wins, as it would in the
    container. The host path is resolved (symbolic links included) and must
    stay inside its mount, so a link planted in the workspace cannot expose
    the rest of the host filesystem. The path itself does not need to exist,
    so write_file can target a new file.

    Args:
        raw_path: Path as written by the agent, absolute or relative to /workspace.
        mounts: The sandbox mounts, from build_sandbox_mounts.

    Returns:
        The resolved path.

    Raises:
        SandboxPathError: If the path is empty or outside every mount.
        PathEscapeError: If a symbolic link leads outside the mount.
    """
    sandbox_path = normalize_sandbox_path(raw_path)

    containing_mounts = [
        mount
        for mount in mounts
        if sandbox_path == mount.sandbox_path or mount.sandbox_path in sandbox_path.parents
    ]
    if containing_mounts:
        mount = max(containing_mounts, key=lambda candidate: len(candidate.sandbox_path.parts))
        relative_path = sandbox_path.relative_to(mount.sandbox_path)
        host_path = (mount.host_path / relative_path).resolve()
        if not host_path.is_relative_to(mount.host_path):
            raise PathEscapeError(f"'{sandbox_path}' resolves outside {mount.sandbox_path}.")

        return ResolvedSandboxPath(
            sandbox_path=sandbox_path,
            host_path=host_path,
            is_writable=not mount.is_read_only,
            mount=mount,
            child_mounts=(),
        )

    child_mounts = tuple(
        sorted(
            (mount for mount in mounts if sandbox_path in mount.sandbox_path.parents),
            key=lambda mount: mount.sandbox_path,
        )
    )
    if child_mounts:
        return ResolvedSandboxPath(
            sandbox_path=sandbox_path,
            host_path=None,
            is_writable=False,
            mount=None,
            child_mounts=child_mounts,
        )

    available_roots = ", ".join(str(mount.sandbox_path) for mount in mounts)
    raise SandboxPathError(
        f"'{sandbox_path}' is outside the sandbox. Available directories: {available_roots}."
    )
