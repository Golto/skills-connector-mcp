import os
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PROFILE_ID = "default"

PROFILE_ENV_VAR = "MCP_SKILLS_PROFILE"
PATHS_DIR_ENV_VAR = "MCP_SKILLS_PATHS_DIR"
WORKSPACE_ENV_VAR = "MCP_SKILLS_WORKSPACE"


@dataclass(frozen=True)
class LaunchOptions:
    """Options a client sets when starting one server process.

    Attributes:
        profile_id: Profile to load.
        paths_dir: Directory containing a paths.json, or None.
        workspace_dir: Single directory to use as /workspace, or None.
    """

    profile_id: str
    paths_dir: Path | None
    workspace_dir: Path | None


def resolve_launch_options() -> LaunchOptions:
    """Resolve the launch options from CLI arguments and environment variables.

    Each option is resolved independently, the CLI argument taking precedence
    over its environment variable:
    - profile: --profile, then MCP_SKILLS_PROFILE, then 'default'.
    - paths dir: --paths-dir, then MCP_SKILLS_PATHS_DIR. Same flag name and
      meaning as the project navigator and writer servers, so a client can
      pass them all the same value.
    - workspace: --workspace, then MCP_SKILLS_WORKSPACE.

    Arguments are parsed with parse_known_args to tolerate flags injected by
    uv or 'mcp run'. Both '--flag value' and '--flag=value' are accepted.
    How paths dir and workspace combine is decided by
    resolve_workspace_layout, not here.

    Returns:
        The resolved LaunchOptions.
    """
    parser = ArgumentParser(add_help=False)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--paths-dir", default=None)
    parser.add_argument("--workspace", default=None)
    arguments, _ = parser.parse_known_args()

    profile_id = _pick_value(arguments.profile, PROFILE_ENV_VAR) or DEFAULT_PROFILE_ID
    paths_dir = _pick_value(arguments.paths_dir, PATHS_DIR_ENV_VAR)
    workspace_dir = _pick_value(arguments.workspace, WORKSPACE_ENV_VAR)

    return LaunchOptions(
        profile_id=profile_id,
        paths_dir=Path(paths_dir) if paths_dir else None,
        workspace_dir=Path(workspace_dir) if workspace_dir else None,
    )


def _pick_value(cli_value: str | None, env_var: str) -> str | None:
    """Return the CLI value if set, else the stripped environment value, else None."""
    if cli_value and cli_value.strip():
        return cli_value.strip()

    env_value = os.environ.get(env_var, "").strip()
    return env_value or None
