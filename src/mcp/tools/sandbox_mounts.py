from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from src.mcp.context import AppRequestContext
from src.storage.skill_store import SANDBOX_SKILLS_ROOT, resolve_skill_dir


@dataclass(frozen=True)
class BindMount:
    """One host directory exposed inside the sandbox.

    The same list of mounts is used to start the run_bash_command container
    and to resolve the paths given to the file tools, so both always agree
    on what a sandbox path points to.

    Attributes:
        host_path: Absolute, resolved path of the directory on the host.
        sandbox_path: Absolute mount point inside the sandbox.
        is_read_only: Whether the sandbox may only read the directory.
    """

    host_path: Path
    sandbox_path: PurePosixPath
    is_read_only: bool


def build_sandbox_mounts(ctx: AppRequestContext) -> list[BindMount]:
    """List every directory exposed in the sandbox.

    - Each skill of the scope, read-only, at /skills/<skill_id>. Mounting
      them all (rather than one skill per call) is what lets the tool drop
      its skill_id parameter: a script is simply run by its sandbox path.
    - Each workspace mount, read-write, at /workspace or /workspace/<name>.

    Skills in scope but absent from the registry are skipped, consistently
    with list_skills and the skills index.

    Args:
        ctx: The active request context carrying scope, registry and workspace.

    Returns:
        The mounts, skills first, then workspace.
    """
    mounts: list[BindMount] = []

    for skill_id in ctx.scope.skill_ids:
        entry = ctx.registry.skills.get(skill_id)
        if entry is None:
            continue
        mounts.append(
            BindMount(
                host_path=resolve_skill_dir(entry.path).resolve(),
                sandbox_path=SANDBOX_SKILLS_ROOT / skill_id,
                is_read_only=True,
            )
        )

    for workspace_mount in ctx.workspace.mounts:
        mounts.append(
            BindMount(
                host_path=workspace_mount.host_path,
                sandbox_path=workspace_mount.sandbox_path,
                is_read_only=False,
            )
        )

    return mounts
