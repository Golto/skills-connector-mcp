import hashlib
from pathlib import Path


def compute_skill_hash(skill_dir: Path) -> str:
    """Compute a SHA256 hash over a skill's SKILL.md and all resource files.

    The hash is computed over:
    - The full byte content of SKILL.md.
    - For each resource file (excluding SKILL.md and manifest.json), sorted
      by relative path: the relative path string followed by the file's byte
      content.

    Sorting by relative path guarantees a deterministic hash regardless of
    filesystem traversal order. Including both the path and content means
    the hash changes when files are added, removed, renamed, or modified.

    Args:
        skill_dir: Absolute path to the skill's root directory.

    Returns:
        A hex digest string prefixed with 'sha256:'.

    Raises:
        FileNotFoundError: If SKILL.md does not exist in the given directory.
    """
    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.exists():
        raise FileNotFoundError(f"SKILL.md not found in: {skill_dir}")

    hasher = hashlib.sha256()
    hasher.update(skill_md_path.read_bytes())

    resource_files = sorted(
        path
        for path in skill_dir.rglob("*")
        if path.is_file() and path.name not in ("SKILL.md", "manifest.json")
    )
    for resource_path in resource_files:
        relative = str(resource_path.relative_to(skill_dir))
        hasher.update(relative.encode("utf-8"))
        hasher.update(resource_path.read_bytes())

    return f"sha256:{hasher.hexdigest()}"
