import sys

from src.mcp.server import build_server, resolve_profile_id
from src.mcp.tools.run_bash_command.image_builder import DockerImageBuildError
from src.storage.exceptions import (
    ProfileCorruptedError,
    ProfileNotFoundError,
    RegistryCorruptedError,
)

try:
    mcp = build_server(resolve_profile_id())
except (
    ProfileNotFoundError,
    ProfileCorruptedError,
    RegistryCorruptedError,
    DockerImageBuildError,
) as error:
    # NOTE: uv run mcp dev silently swallows import exceptions. Printing to
    # stderr explicitly ensures the error is visible in the terminal.
    print(f"ERROR: Failed to start mcp-skills: {error}", file=sys.stderr)
    raise
