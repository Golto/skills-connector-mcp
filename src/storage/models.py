from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


# ----------------------------------------------------------------
# Enums
# ----------------------------------------------------------------


class SkillOrigin(str, Enum):
    """Origin category of a skill, determining its storage location."""

    BASE = "base"
    GENERATED = "generated"


# ----------------------------------------------------------------
# Pydantic models (JSON <-> disk)
# ----------------------------------------------------------------


class SkillEntry(BaseModel):
    """Registry entry for a single skill.

    Stored in registry.json. The SKILL.md file remains the source of truth
    for full content; this entry only duplicates searchable metadata.

    Attributes:
        origin: Whether the skill lives in base/ or generated/.
        path: Relative path to the skill's root directory from the data root
            (e.g. 'base/python-style/' or 'generated/my-skill/').
        description: Short description extracted from SKILL.md frontmatter.
        triggers: Keywords or phrases that signal this skill should be used.
        tags: Domain tags for grouping and filtering.
        created_at: When the skill was first indexed.
        hash: SHA256 hash over SKILL.md content and resource files,
            used to detect manual modifications on disk.
        has_resources: True if the skill contains files beyond SKILL.md
            and manifest.json. Avoids unnecessary list_skill_files calls.
        composed_from: Ids of skills this one was derived from.
            Only set for generated skills.
    """

    origin: SkillOrigin
    path: str
    description: str
    triggers: list[str]
    tags: list[str]
    created_at: datetime
    hash: str
    has_resources: bool
    composed_from: list[str] = []


class Registry(BaseModel):
    """Root model for registry.json.

    Attributes:
        version: Schema version, incremented on breaking changes.
        updated_at: Timestamp of the last write to registry.json.
        skills: Map of skill_id to its registry entry.
    """

    version: int
    updated_at: datetime
    skills: dict[str, SkillEntry]


class Profile(BaseModel):
    """Content of a profiles/<profile_id>.json file.

    Attributes:
        name: Human-readable profile name.
        description: Purpose or context for this profile.
        allow_generation: Enables create_skill and set_profile_skills tools.
        allow_execution: Enables run_bash_command tool.
        skill_ids: Exhaustive list of skill ids visible in this profile.
    """

    name: str
    description: str
    allow_generation: bool = False
    allow_execution: bool = False
    skill_ids: list[str]


class Manifest(BaseModel):
    """Content of manifest.json inside a generated skill directory.

    Attributes:
        composed_from: Ids of skills used as sources when creating this one.
        created_at: When the skill was created by the agent.
    """

    composed_from: list[str]
    created_at: datetime


# ----------------------------------------------------------------
# Dataclass (in-memory, no serialization)
# ----------------------------------------------------------------


@dataclass
class ServerScope:
    """In-memory representation of the active profile's scope for one server process.

    The scope is resolved once at startup from the loaded profile and remains
    fixed for the lifetime of the process. Two mutation methods are provided
    to reflect immediate in-process changes without requiring a restart:
    - add_skill: called by create_skill after a new skill is written to disk.
    - replace_skill_ids: called by set_profile_skills when targeting the active
      profile.

    Attributes:
        profile_id: Identifier of the loaded profile.
        skill_ids: Ids of skills currently visible in this scope.
        allow_generation: Whether the create_skill and set_profile_skills tools
            are active.
        allow_execution: Whether the run_bash_command tool is active.
    """

    profile_id: str
    skill_ids: list[str] = field(default_factory=list)
    allow_generation: bool = False
    allow_execution: bool = False

    def add_skill(self, skill_id: str) -> None:
        """Add a skill to the in-memory scope.

        A no-op if the skill is already present, to remain idempotent in
        case of retried create_skill calls.

        Args:
            skill_id: The id of the skill to add.
        """
        if skill_id not in self.skill_ids:
            self.skill_ids.append(skill_id)

    def replace_skill_ids(self, skill_ids: list[str]) -> None:
        """Replace the in-memory skill list for the active profile.

        Called by set_profile_skills when it targets the currently loaded
        profile, so that list_skills and search_skills reflect the change
        without a server restart.

        Args:
            skill_ids: The new list of skill ids to make visible.
        """
        self.skill_ids = list(skill_ids)
