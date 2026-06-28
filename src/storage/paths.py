from pathlib import Path

from src.storage.models import SkillOrigin


DATA_ROOT: Path = Path.home() / ".config" / "scripts" / "mcp-skills"


def get_data_root() -> Path:
    """Return the absolute path to the mcp-skills data root directory."""
    return DATA_ROOT


def get_base_dir() -> Path:
    """Return the absolute path to the base/ skills directory."""
    return DATA_ROOT / "base"


def get_generated_dir() -> Path:
    """Return the absolute path to the generated/ skills directory."""
    return DATA_ROOT / "generated"


def get_profiles_dir() -> Path:
    """Return the absolute path to the profiles/ directory."""
    return DATA_ROOT / "profiles"


def get_registry_path() -> Path:
    """Return the absolute path to registry.json."""
    return DATA_ROOT / "registry.json"


def get_skill_dir(skill_id: str, origin: SkillOrigin) -> Path:
    """Return the absolute path to a skill's root directory.

    Args:
        skill_id: The skill identifier (used as the directory name).
        origin: Whether the skill lives in base/ or generated/.

    Returns:
        Absolute path to the skill directory.
    """
    if origin == SkillOrigin.BASE:
        return get_base_dir() / skill_id
    return get_generated_dir() / skill_id


def get_profile_path(profile_id: str) -> Path:
    """Return the absolute path to a profile JSON file.

    Args:
        profile_id: The profile identifier (filename without .json extension).

    Returns:
        Absolute path to the profile file.
    """
    return get_profiles_dir() / f"{profile_id}.json"
