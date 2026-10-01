import os
from pathlib import Path


_DEFAULT_IMAGE = "mcp-skills-runner:latest"
_DEFAULT_MEMORY_LIMIT = "512m"
_DEFAULT_CPU_LIMIT = "1.0"
_DEFAULT_PIDS_LIMIT = "256"
_DEFAULT_TMP_SIZE = "256m"
_DEFAULT_OUTPUT_LIMIT_BYTES = 8000
_DEFAULT_SNAPSHOT_MAX_FILES = 20000
_DEFAULT_CHANGED_FILES_MAX_ENTRIES = 50
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

    Also used as the memory+swap limit, so the container cannot spill into
    swap. Fixed at the server level, not exposed to the agent. Overridable
    via the MCP_SKILLS_DOCKER_MEMORY environment variable (Docker memory
    syntax, e.g. '512m', '1g').

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


def get_docker_pids_limit() -> str:
    """Return the maximum number of processes inside one container.

    Guards against fork bombs and runaway process spawning. Overridable via
    the MCP_SKILLS_DOCKER_PIDS environment variable.

    Returns:
        The limit string to pass to 'docker run --pids-limit'.
    """
    return os.environ.get("MCP_SKILLS_DOCKER_PIDS", _DEFAULT_PIDS_LIMIT)


def get_docker_tmp_size() -> str:
    """Return the size of the in-memory /tmp of every container.

    The container root filesystem is read-only, so /tmp is the only scratch
    space outside /workspace. It counts against the memory limit. Overridable
    via the MCP_SKILLS_DOCKER_TMP_SIZE environment variable (e.g. '256m').

    Returns:
        The size string used in the '--tmpfs /tmp' options.
    """
    return os.environ.get("MCP_SKILLS_DOCKER_TMP_SIZE", _DEFAULT_TMP_SIZE)


def get_output_limit_bytes() -> int:
    """Return how many bytes of stdout, and as many of stderr, are returned.

    Anything beyond is cut from the middle of the stream (see
    BoundedOutputBuffer). Kept small by default because the output goes
    straight into the agent's context. Overridable via the
    MCP_SKILLS_OUTPUT_LIMIT_BYTES environment variable.

    Returns:
        The limit in bytes, per stream.

    Raises:
        ValueError: If the environment variable is not an integer.
    """
    raw_value = os.environ.get("MCP_SKILLS_OUTPUT_LIMIT_BYTES")
    return int(raw_value) if raw_value else _DEFAULT_OUTPUT_LIMIT_BYTES


def get_snapshot_max_files() -> int:
    """Return how many workspace files are scanned to detect changed files.

    Past this number, changed_files and deleted_files are not computed (they
    come back as null) rather than slowing every command down. Overridable
    via the MCP_SKILLS_SNAPSHOT_MAX_FILES environment variable.

    Returns:
        The maximum number of files per snapshot.

    Raises:
        ValueError: If the environment variable is not an integer.
    """
    raw_value = os.environ.get("MCP_SKILLS_SNAPSHOT_MAX_FILES")
    return int(raw_value) if raw_value else _DEFAULT_SNAPSHOT_MAX_FILES


def get_changed_files_max_entries() -> int:
    """Return how many paths changed_files and deleted_files each list at most.

    Further paths are summarized as a single '... and N more' entry.

    Returns:
        The maximum number of listed paths.
    """
    return _DEFAULT_CHANGED_FILES_MAX_ENTRIES


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
