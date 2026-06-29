import json
from datetime import datetime, timezone
from pathlib import Path

from src.storage.exceptions import PathEscapeError
from src.storage.models import Manifest, SkillOrigin
from src.storage.paths import get_data_root, get_skill_dir


def resolve_skill_dir(path: str) -> Path:
    """Resolve the absolute path to a skill's root directory from its registry path.

    Args:
        path: The 'path' field from a SkillEntry (e.g. 'base/python-style/').

    Returns:
        The absolute path to the skill directory.
    """
    return get_data_root() / path


def read_skill_content(skill_dir: Path) -> str:
    """Read and return the content of SKILL.md from a skill directory.

    Args:
        skill_dir: Absolute path to the skill's root directory.

    Returns:
        The full text content of SKILL.md.

    Raises:
        FileNotFoundError: If SKILL.md does not exist in the directory.
    """
    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.exists():
        raise FileNotFoundError(f"SKILL.md not found in: {skill_dir}")
    return skill_md_path.read_text(encoding="utf-8")


def list_skill_files(skill_dir: Path) -> list[str]:
    """List all files in a skill directory, excluding manifest.json.

    SKILL.md is included. Files are returned as relative paths from the skill
    root, sorted for deterministic output.

    Args:
        skill_dir: Absolute path to the skill's root directory.

    Returns:
        A sorted list of relative file paths within the skill directory.
    """
    return sorted(
        str(path.relative_to(skill_dir))
        for path in skill_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )


def resolve_resource_path(skill_dir: Path, relative_path: str) -> Path:
    """Resolve a resource path and verify it stays within the skill directory.

    Resolves symlinks and '..' components before checking containment,
    preventing path traversal attacks.

    Args:
        skill_dir: Absolute path to the skill's root directory.
        relative_path: Caller-supplied path relative to the skill root.

    Returns:
        The resolved absolute path to the resource.

    Raises:
        PathEscapeError: If the resolved path falls outside skill_dir.
    """
    resolved = (skill_dir / relative_path).resolve()
    skill_root = skill_dir.resolve()

    if not resolved.is_relative_to(skill_root):
        raise PathEscapeError(
            f"Path '{relative_path}' resolves outside the skill directory."
        )
    return resolved


def read_skill_resource(skill_dir: Path, relative_path: str) -> str:
    """Read a resource file from a skill directory.

    SKILL.md must be read through read_skill_content, not this function.
    The path must not escape the skill directory.

    Args:
        skill_dir: Absolute path to the skill's root directory.
        relative_path: Path to the resource, relative to the skill root.

    Returns:
        The text content of the resource file.

    Raises:
        ValueError: If relative_path refers to SKILL.md.
        PathEscapeError: If the path resolves outside the skill directory.
        FileNotFoundError: If the resolved resource does not exist.
    """
    if Path(relative_path).name == "SKILL.md":
        raise ValueError(
            "SKILL.md cannot be read via read_skill_resource. Use read_skill_content."
        )

    resolved = resolve_resource_path(skill_dir, relative_path)

    if not resolved.exists():
        raise FileNotFoundError(f"Resource not found: {resolved}")

    return resolved.read_text(encoding="utf-8")


def write_generated_skill(
    name: str,
    content: str,
    composed_from: list[str],
    resources: dict[str, str] | None,
) -> Path:
    """Write a new generated skill to disk.

    Writes SKILL.md, manifest.json, and any provided resource files under
    generated/<name>/. All resource paths are validated before any file
    is written, so a path traversal attempt fails before touching the disk.

    This function handles only filesystem operations. Updating the registry
    and the active profile is the caller's responsibility (MCP tool layer).

    Args:
        name: The skill identifier, used as the directory name.
        content: Full text content to write to SKILL.md.
        composed_from: List of source skill ids to record in the manifest.
        resources: Optional dict mapping relative_path to file content.
            Each path is validated before writing.

    Returns:
        The absolute path to the newly created skill directory.

    Raises:
        FileExistsError: If the skill directory already exists.
        PathEscapeError: If any resource path escapes the skill directory.
    """
    skill_dir = get_skill_dir(name, SkillOrigin.GENERATED)

    if skill_dir.exists():
        raise FileExistsError(f"Skill directory already exists: {skill_dir}")

    # Validate all resource paths before creating any files.
    if resources:
        for relative_path in resources:
            resolve_resource_path(skill_dir, relative_path)

    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    if resources:
        for relative_path, file_content in resources.items():
            resolved = resolve_resource_path(skill_dir, relative_path)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(file_content, encoding="utf-8")

    manifest = Manifest(
        composed_from=composed_from,
        created_at=datetime.now(timezone.utc),
    )
    (skill_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return skill_dir
