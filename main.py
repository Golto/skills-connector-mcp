import sys

from src.mcp.launch_options import resolve_launch_options
from src.mcp.server import build_server
from src.mcp.tools.run_bash_command.image_builder import DockerImageBuildError
from src.storage.exceptions import (
    ProfileCorruptedError,
    ProfileNotFoundError,
    RegistryCorruptedError,
    WorkspaceConfigError,
)

try:
    mcp = build_server(resolve_launch_options())
except (
    ProfileNotFoundError,
    ProfileCorruptedError,
    RegistryCorruptedError,
    WorkspaceConfigError,
    DockerImageBuildError,
) as error:
    # NOTE: uv run mcp dev silently swallows import exceptions. Printing to
    # stderr explicitly ensures the error is visible in the terminal.
    print(f"ERROR: Failed to start mcp-skills: {error}", file=sys.stderr)
    raise
