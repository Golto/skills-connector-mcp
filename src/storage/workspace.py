import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath

from src.storage.exceptions import WorkspaceConfigError
from src.storage.paths import get_workspaces_dir


SANDBOX_WORKSPACE_ROOT = PurePosixPath("/workspace")

PATHS_FILE_NAME = "paths.json"

_MOUNT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


# ----------------------------------------------------------------
# Models
# ----------------------------------------------------------------


class WorkspaceSource(str, Enum):
    """Where the workspace layout of a server process was taken from."""

    PATHS_DIR = "paths_dir"
    WORKSPACE_DIR = "workspace_dir"
    PROFILE_DEFAULT = "profile_default"


@dataclass(frozen=True)
class WorkspaceMount:
    """One host directory exposed read-write inside the sandbox workspace.

    Attributes:
        name: Mount name. With a paths.json, it is the project id shared with
            the other MCP servers of the client (e.g. 'memory', 'artefacts')
            and the name of the subdirectory under /workspace. With a single
            workspace directory, it is None and the mount IS /workspace.
        host_path: Absolute, resolved path of the directory on the host.
        sandbox_path: Absolute path of the mount point inside the sandbox.
    """

    name: str | None
    host_path: Path
    sandbox_path: PurePosixPath


@dataclass(frozen=True)
class WorkspaceLayout:
    """Every host directory that makes up /workspace for one server process.

    Resolved once at startup, like the profile. Either a single mount sitting
    at /workspace itself, or several named mounts under /workspace/<name>.

    Attributes:
        source: Which launch option produced this layout.
        mounts: The mounts, sorted by sandbox path.
    """

    source: WorkspaceSource
    mounts: tuple[WorkspaceMount, ...]


# ----------------------------------------------------------------
# Resolution
# ----------------------------------------------------------------


def resolve_workspace_layout(
    profile_id: str,
    paths_dir: Path | None,
    workspace_dir: Path | None,
) -> WorkspaceLayout:
    """Resolve the workspace layout from the launch options.

    Precedence, highest first:
    1. paths_dir: a directory holding a paths.json that maps names to host
       directories, the same file other MCP servers of the client (project
       navigator, project writer) receive through --paths-dir. Each entry is
       mounted at /workspace/<name>, so a file seen as project 'memory', path
       'notes.md' by those servers is /workspace/memory/notes.md in the
       sandbox.
    2. workspace_dir: a single host directory mounted as /workspace.
    3. A per-profile default directory under the data root, created on demand.

    Explicitly supplied directories are never created: they belong to the
    client, and a missing one is far more likely a typo than an intent.

    Args:
        profile_id: Active profile, used to name the default directory.
        paths_dir: Directory containing paths.json, or None.
        workspace_dir: Single workspace directory, or None.

    Returns:
        The resolved WorkspaceLayout.

    Raises:
        WorkspaceConfigError: If paths.json is missing or invalid, or if a
            supplied directory does not exist.
    """
    if paths_dir is not None:
        return WorkspaceLayout(
            source=WorkspaceSource.PATHS_DIR,
            mounts=_read_paths_file_mounts(paths_dir),
        )

    if workspace_dir is not None:
        return WorkspaceLayout(
            source=WorkspaceSource.WORKSPACE_DIR,
            mounts=(_build_root_mount(_require_existing_directory(workspace_dir)),),
        )

    default_dir = get_workspaces_dir() / profile_id
    default_dir.mkdir(parents=True, exist_ok=True)
    return WorkspaceLayout(
        source=WorkspaceSource.PROFILE_DEFAULT,
        mounts=(_build_root_mount(default_dir.resolve()),),
    )


def _read_paths_file_mounts(paths_dir: Path) -> tuple[WorkspaceMount, ...]:
    """Read paths.json and turn each entry into a named mount.

    Relative host paths are resolved against paths_dir rather than the
    process working directory, so the file stays valid wherever the server
    is started from.

    Args:
        paths_dir: Directory containing paths.json.

    Returns:
        The named mounts, sorted by name.

    Raises:
        WorkspaceConfigError: If the file is missing, malformed, empty, has a
            name unusable as a directory name, or points to a missing directory.
    """
    paths_file = paths_dir.expanduser() / PATHS_FILE_NAME
    if not paths_file.is_file():
        raise WorkspaceConfigError(f"{PATHS_FILE_NAME} not found at: {paths_file}")

    try:
        raw_mapping = json.loads(paths_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise WorkspaceConfigError(f"Could not parse {paths_file}: {error}") from error

    if not isinstance(raw_mapping, dict) or not raw_mapping:
        raise WorkspaceConfigError(
            f"{paths_file} must be a non-empty JSON object mapping names to directories."
        )

    mounts: list[WorkspaceMount] = []
    for name, raw_host_path in raw_mapping.items():
        if not _MOUNT_NAME_PATTERN.match(name):
            raise WorkspaceConfigError(
                f"Invalid name '{name}' in {paths_file}: only letters, digits, "
                "'_' and '-' are allowed, since it becomes a directory under /workspace."
            )
        if not isinstance(raw_host_path, str) or not raw_host_path.strip():
            raise WorkspaceConfigError(
                f"Entry '{name}' in {paths_file} must be a non-empty path string."
            )

        host_path = Path(raw_host_path).expanduser()
        if not host_path.is_absolute():
            host_path = paths_file.parent / host_path

        mounts.append(
            WorkspaceMount(
                name=name,
                host_path=_require_existing_directory(host_path),
                sandbox_path=SANDBOX_WORKSPACE_ROOT / name,
            )
        )

    return tuple(sorted(mounts, key=lambda mount: mount.sandbox_path))


def _build_root_mount(host_path: Path) -> WorkspaceMount:
    """Build the single unnamed mount that is /workspace itself."""
    return WorkspaceMount(name=None, host_path=host_path, sandbox_path=SANDBOX_WORKSPACE_ROOT)


def _require_existing_directory(path: Path) -> Path:
    """Resolve a supplied directory and check that it exists.

    Args:
        path: Directory supplied by the client, possibly relative or with '~'.

    Returns:
        The absolute, resolved path.

    Raises:
        WorkspaceConfigError: If the path does not exist or is not a directory.
    """
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise WorkspaceConfigError(f"Workspace directory not found: {resolved}")
    return resolved
