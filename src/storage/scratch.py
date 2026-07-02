import re
import uuid
from pathlib import Path

from src.storage.exceptions import PathEscapeError
from src.storage.paths import get_data_root


_SCRATCH_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _get_scratch_root() -> Path:
    """Return the root directory under which all scratch directories live.

    Returns:
        Absolute path to the scratch root, creating it if missing.
    """
    scratch_root = get_data_root() / "scratch"
    scratch_root.mkdir(exist_ok=True)
    return scratch_root


def generate_scratch_id() -> str:
    """Generate a new unique scratch directory id.

    Used when a run_bash_command call does not specify an existing scratch_id
    to reuse, so a fresh isolated workspace is created for it.

    Returns:
        A hex string safe for use as a directory name and as a future scratch_id.
    """
    return uuid.uuid4().hex


def resolve_scratch_dir(scratch_id: str) -> Path:
    """Resolve the scratch directory for a given id, creating it if needed.

    Reused across multiple run_bash_command calls that share the same
    scratch_id, so an agent can iterate on the same /workspace without losing
    intermediate files between calls. Both fresh ids (from generate_scratch_id)
    and caller-supplied ids from a previous response work identically here.

    Args:
        scratch_id: Identifier of the scratch directory.

    Returns:
        Absolute path to the scratch directory.

    Raises:
        PathEscapeError: If scratch_id contains characters other than
            letters, digits, underscores or hyphens. This also rules out
            path traversal attempts such as '../'.
    """
    if not _SCRATCH_ID_PATTERN.match(scratch_id):
        raise PathEscapeError(
            f"Invalid scratch_id '{scratch_id}': only letters, digits, "
            "'_' and '-' are allowed."
        )

    scratch_dir = _get_scratch_root() / scratch_id
    scratch_dir.mkdir(parents=True, exist_ok=True)
    return scratch_dir


def list_scratch_files(scratch_dir: Path) -> list[str]:
    """List all files written to a scratch directory.

    Returns relative paths so the agent can reference output files without
    knowing the host-side absolute path.

    Args:
        scratch_dir: Absolute path to the scratch directory.

    Returns:
        A sorted list of relative file paths within the scratch directory.
    """
    return sorted(
        str(path.relative_to(scratch_dir))
        for path in scratch_dir.rglob("*")
        if path.is_file()
    )
