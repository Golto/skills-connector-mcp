import json
from datetime import datetime, timezone

from src.storage.exceptions import ProfileCorruptedError, RegistryCorruptedError
from src.storage.paths import get_base_dir, get_data_root, get_generated_dir, get_profile_path, get_profiles_dir, get_registry_path


_DEFAULT_PROFILE_ID = "default"


def _build_empty_registry() -> dict:
    return {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "skills": {},
    }


def _build_default_profile() -> dict:
    return {
        "name": "default",
        "description": "Profil par defaut (genéré automatiquement)",
        "allow_generation": False,
        "allow_execution": False,
        "skill_ids": [],
    }


def _validate_existing_json(path, error_class: type[Exception]) -> None:
    """Attempt to parse an existing JSON file and raise error_class if invalid.

    Args:
        path: Path to the JSON file to validate.
        error_class: Exception class to raise on invalid JSON.

    Raises:
        error_class: If the file exists but cannot be parsed as valid JSON.
    """
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise error_class(f"Could not parse {path}: {error}") from error


def ensure_data_directories_exist() -> None:
    """Create any missing entries in the mcp-skills data directory.

    Checks and creates each element independently:
    - ~/.config/scripts/mcp-skills/ (data root)
    - base/, generated/, profiles/ directories
    - registry.json (empty registry)
    - profiles/default.json (default profile)

    If an element already exists, it is left untouched. Existing JSON files
    are validated and raise an error if corrupted, so the caller can surface
    the problem to the user rather than silently overwriting data.

    Raises:
        RegistryCorruptedError: If registry.json exists but cannot be parsed.
        ProfileCorruptedError: If profiles/default.json exists but cannot be parsed.
    """
    get_data_root().mkdir(parents=True, exist_ok=True)
    get_base_dir().mkdir(exist_ok=True)
    get_generated_dir().mkdir(exist_ok=True)
    get_profiles_dir().mkdir(exist_ok=True)

    registry_path = get_registry_path()
    if not registry_path.exists():
        registry_path.write_text(
            json.dumps(_build_empty_registry(), indent=4),
            encoding="utf-8",
        )
    else:
        _validate_existing_json(registry_path, RegistryCorruptedError)

    default_profile_path = get_profile_path(_DEFAULT_PROFILE_ID)
    if not default_profile_path.exists():
        default_profile_path.write_text(
            json.dumps(_build_default_profile(), indent=4),
            encoding="utf-8",
        )
    else:
        _validate_existing_json(default_profile_path, ProfileCorruptedError)
