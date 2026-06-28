import json

from src.storage.exceptions import ProfileCorruptedError, ProfileNotFoundError
from src.storage.models import Profile
from src.storage.paths import get_profile_path


def read_profile(profile_id: str) -> Profile:
    """Read and parse a profile JSON file from disk.

    Args:
        profile_id: The profile identifier (filename without .json extension).

    Returns:
        The parsed Profile model.

    Raises:
        ProfileNotFoundError: If the profile file does not exist.
        ProfileCorruptedError: If the file cannot be parsed or validated.
    """
    path = get_profile_path(profile_id)
    if not path.exists():
        raise ProfileNotFoundError(
            f"Profile '{profile_id}' not found at: {path}"
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Profile.model_validate(raw)
    except (json.JSONDecodeError, ValueError) as error:
        raise ProfileCorruptedError(
            f"Could not parse profile '{profile_id}': {error}"
        ) from error


def write_profile(profile_id: str, profile: Profile) -> None:
    """Write a Profile to disk.

    Overwrites the file if it already exists. The profile id determines
    the filename; the Profile model determines the content.

    Args:
        profile_id: The profile identifier (determines the filename).
        profile: The Profile model to serialize and persist.
    """
    path = get_profile_path(profile_id)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
