import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.storage.exceptions import RegistryCorruptedError
from src.storage.hashing import compute_skill_hash
from src.storage.models import Registry, SkillEntry, SkillOrigin
from src.storage.paths import get_base_dir, get_data_root, get_generated_dir, get_registry_path


def read_registry() -> Registry:
    """Read and parse registry.json from disk.

    Returns:
        The parsed Registry model.

    Raises:
        RegistryCorruptedError: If registry.json cannot be parsed as valid JSON
            or does not conform to the expected schema.
    """
    registry_path = get_registry_path()
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
        return Registry.model_validate(raw)
    except (json.JSONDecodeError, ValueError) as error:
        raise RegistryCorruptedError(
            f"Could not parse registry.json: {error}"
        ) from error


def write_registry(registry: Registry) -> None:
    """Write a Registry to disk atomically.

    Uses a temporary file in the same directory, then replaces the target with
    an atomic rename. This guarantees that registry.json is never left in a
    partially-written state on POSIX systems.

    The updated_at timestamp is refreshed to the current UTC time on each write.

    Args:
        registry: The registry to serialize and persist.
    """
    registry_path = get_registry_path()
    payload = registry.model_dump(mode="json")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=registry_path.parent,
        delete=False,
        suffix=".tmp",
    ) as temp_file:
        json.dump(payload, temp_file, indent=2)
        temp_path = Path(temp_file.name)

    temp_path.replace(registry_path)


def _extract_frontmatter_metadata(
    skill_md_path: Path,
) -> dict[str, str | list[str]]:
    """Extract description, triggers and tags from a SKILL.md frontmatter block.

    SKILL.md files may begin with a YAML frontmatter block delimited by '---'
    lines. If no frontmatter is present or a field is missing, empty defaults
    are returned so the registry can still index the skill.

    Args:
        skill_md_path: Path to the SKILL.md file.

    Returns:
        A dict with string keys 'description', 'triggers', and 'tags'.
    """
    content = skill_md_path.read_text(encoding="utf-8")
    description = ""
    triggers: list[str] = []
    tags: list[str] = []

    if content.startswith("---"):
        end_index = content.find("---", 3)
        if end_index != -1:
            frontmatter_text = content[3:end_index].strip()
            try:
                frontmatter = yaml.safe_load(frontmatter_text) or {}
                description = frontmatter.get("description", "")
                triggers = frontmatter.get("triggers", [])
                tags = frontmatter.get("tags", [])
            except yaml.YAMLError:
                pass

    return {"description": description, "triggers": triggers, "tags": tags}


def _build_skill_entry(skill_dir: Path, origin: SkillOrigin) -> SkillEntry:
    """Build a SkillEntry by reading a skill directory on disk.

    For generated skills, the manifest.json is read to populate composed_from
    and created_at. For base skills (no manifest), created_at falls back to
    the directory's ctime as a best-effort approximation.

    Args:
        skill_dir: Absolute path to the skill's root directory.
        origin: Whether the skill is from 'base' or 'generated'.

    Returns:
        A SkillEntry populated with metadata and a freshly computed hash.
    """
    skill_md_path = skill_dir / "SKILL.md"
    metadata = _extract_frontmatter_metadata(skill_md_path)
    skill_hash = compute_skill_hash(skill_dir)

    resource_files = [
        path
        for path in skill_dir.rglob("*")
        if path.is_file() and path.name not in ("SKILL.md", "manifest.json")
    ]
    has_resources = len(resource_files) > 0

    # NOTE: st_ctime on Linux is last metadata change, not creation time.
    # It serves as a best-effort fallback for skills discovered without a manifest.
    created_at = datetime.fromtimestamp(
        skill_dir.stat().st_ctime, tz=timezone.utc
    )
    composed_from: list[str] = []

    manifest_path = skill_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            composed_from = manifest_data.get("composed_from", [])
            if "created_at" in manifest_data:
                created_at = datetime.fromisoformat(manifest_data["created_at"])
        except (json.JSONDecodeError, ValueError):
            pass

    return SkillEntry(
        origin=origin,
        path=f"{origin.value}/{skill_dir.name}/",
        description=metadata["description"],
        triggers=metadata["triggers"],
        tags=metadata["tags"],
        created_at=created_at,
        hash=skill_hash,
        has_resources=has_resources,
        composed_from=composed_from,
    )


def _discover_skills_on_disk() -> dict[str, tuple[Path, SkillOrigin]]:
    """Scan base/ and generated/ and return all valid skill directories.

    A valid skill directory is any immediate subdirectory of base/ or generated/
    that contains a SKILL.md file at its root.

    Returns:
        A dict mapping skill_id to (skill_dir, SkillOrigin).
    """
    discovered: dict[str, tuple[Path, SkillOrigin]] = {}

    for origin, parent_dir in (
        (SkillOrigin.BASE, get_base_dir()),
        (SkillOrigin.GENERATED, get_generated_dir()),
    ):
        if not parent_dir.exists():
            continue
        for skill_dir in parent_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                discovered[skill_dir.name] = (skill_dir, origin)

    return discovered


def sync_skills_to_registry(registry: Registry) -> tuple[Registry, bool]:
    """Reconcile registry.json with the actual state of base/ and generated/ on disk.

    Performs three corrective operations:
    - Skills found on disk but absent from the registry are added.
    - Skills present in the registry but absent on disk are removed.
    - Skills whose hash differs from the stored value are updated.

    This function never raises on detected diffs -- all differences are corrected
    silently. Corrupted manifest.json files are tolerated (composed_from and
    created_at fall back to safe defaults). The case of a corrupted registry.json
    is handled upstream by read_registry before this function is ever called.

    Args:
        registry: The current registry loaded from disk.

    Returns:
        A tuple (updated_registry, was_modified) where was_modified is True if
        any addition, removal or update was applied.
    """
    discovered = _discover_skills_on_disk()
    updated_skills = dict(registry.skills)
    was_modified = False

    for skill_id, (skill_dir, origin) in discovered.items():
        fresh_hash = compute_skill_hash(skill_dir)
        if skill_id not in updated_skills:
            updated_skills[skill_id] = _build_skill_entry(skill_dir, origin)
            was_modified = True
        elif updated_skills[skill_id].hash != fresh_hash:
            updated_skills[skill_id] = _build_skill_entry(skill_dir, origin)
            was_modified = True

    for skill_id in list(updated_skills.keys()):
        if skill_id not in discovered:
            del updated_skills[skill_id]
            was_modified = True

    updated_registry = registry.model_copy(update={"skills": updated_skills})
    return updated_registry, was_modified


def add_skill_to_registry(
    registry: Registry,
    skill_id: str,
    skill_dir: Path,
    origin: SkillOrigin,
) -> Registry:
    """Add a newly created skill to the registry.

    Builds the SkillEntry from the skill directory and returns an updated
    Registry without writing to disk. The caller is responsible for calling
    write_registry afterwards.

    Args:
        registry: The current registry.
        skill_id: The skill identifier (directory name).
        skill_dir: Absolute path to the skill directory.
        origin: Whether the skill is 'base' or 'generated'.

    Returns:
        A new Registry with the skill entry added.
    """
    entry = _build_skill_entry(skill_dir, origin)
    updated_skills = {**registry.skills, skill_id: entry}
    return registry.model_copy(update={"skills": updated_skills})
