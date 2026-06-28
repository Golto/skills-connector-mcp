class SkillNotFoundError(Exception):
    """Raised when a skill_id is not found in the registry or on disk."""


class ProfileNotFoundError(Exception):
    """Raised when a profile file does not exist on disk."""


class SkillAlreadyExistsError(Exception):
    """Raised when attempting to create a skill whose id already exists."""


class PathEscapeError(Exception):
    """Raised when a relative path resolves outside the skill's root directory."""


class RegistryCorruptedError(Exception):
    """Raised when registry.json exists but cannot be parsed or validated."""


class ProfileCorruptedError(Exception):
    """Raised when a profile file exists but cannot be parsed or validated."""
