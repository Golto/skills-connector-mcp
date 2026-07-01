import os
from pathlib import Path


_DEFAULT_IMAGE = "mcp-skills-runner:latest"
_DEFAULT_MEMORY_LIMIT = "512m"
_DEFAULT_CPU_LIMIT = "1.0"
_DEFAULT_CONTAINER_KILL_TIMEOUT_SECONDS = 10
_DEFAULT_IMAGE_BUILD_TIMEOUT_SECONDS = 300


def get_docker_image() -> str:
    """Return the Docker image used for run_bash_command.

    Fixed and never exposed as a tool parameter (spec section 7.2): the agent
    cannot choose which image runs its command. Overridable by the server
    operator via the MCP_SKILLS_DOCKER_IMAGE environment variable.

    Returns:
        The image reference to pass to 'docker run'.
    """
    return os.environ.get("MCP_SKILLS_DOCKER_IMAGE", _DEFAULT_IMAGE)


def get_docker_memory_limit() -> str:
    """Return the memory limit applied to every run_bash_command container.

    Fixed at the server level, not exposed to the agent. Overridable via the
    MCP_SKILLS_DOCKER_MEMORY environment variable (Docker memory syntax,
    e.g. '512m', '1g').

    Returns:
        The memory limit string to pass to 'docker run --memory'.
    """
    return os.environ.get("MCP_SKILLS_DOCKER_MEMORY", _DEFAULT_MEMORY_LIMIT)


def get_docker_cpu_limit() -> str:
    """Return the CPU limit applied to every run_bash_command container.

    Fixed at the server level, not exposed to the agent. Overridable via the
    MCP_SKILLS_DOCKER_CPUS environment variable (Docker CPU count syntax,
    e.g. '1.0', '0.5').

    Returns:
        The CPU limit string to pass to 'docker run --cpus'.
    """
    return os.environ.get("MCP_SKILLS_DOCKER_CPUS", _DEFAULT_CPU_LIMIT)


def get_container_kill_timeout_seconds() -> int:
    """Return the timeout for forcibly killing a container after its command times out.

    This is a separate, short timeout used only for the 'docker kill' cleanup
    call, distinct from the command's own timeout_seconds.

    Returns:
        The number of seconds to wait for 'docker kill' to complete.
    """
    return _DEFAULT_CONTAINER_KILL_TIMEOUT_SECONDS


def get_image_build_timeout_seconds() -> int:
    """Return the timeout allowed for building the runner image at server startup.

    Building only happens once (when the image is missing locally), so a
    generous timeout is used to accommodate apt/pip installs on a cold cache.

    Returns:
        The number of seconds to wait for 'docker build' to complete.
    """
    return _DEFAULT_IMAGE_BUILD_TIMEOUT_SECONDS


def get_docker_build_context_dir() -> Path:
    """Return the absolute path to the runner image's Docker build context.

    Resolved relative to this file's location rather than the process's
    current working directory, so image builds work regardless of where
    'uv run' is invoked from.

    Returns:
        Absolute path to the directory containing the runner image's Dockerfile.
    """
    project_root = Path(__file__).resolve().parents[4]
    return project_root / "docker" / "mcp-skills-runner"
