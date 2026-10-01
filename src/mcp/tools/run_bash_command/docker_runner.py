import asyncio
import os
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath

from src.mcp.tools.run_bash_command.config import (
    get_container_kill_timeout_seconds,
    get_docker_cpu_limit,
    get_docker_image,
    get_docker_memory_limit,
    get_docker_pids_limit,
    get_docker_tmp_size,
    get_output_limit_bytes,
)
from src.mcp.tools.run_bash_command.output_capture import BoundedOutputBuffer, drain_stream
from src.mcp.tools.run_bash_command.sandbox_mounts import BindMount


TIMEOUT_EXIT_CODE = 124

RUNNER_LABEL = "mcp-skills.runner"

_CONTAINER_NAME_PREFIX = "mcp-skills-run-"

# NOTE: the container runs as the host user, who has no home directory in
# the image. HOME points to the writable tmpfs so tools that need one (git,
# pip caches, matplotlib) keep working. Bytecode writing is disabled since
# /skills is read-only and the root filesystem too.
_CONTAINER_ENVIRONMENT = {
    "HOME": "/tmp",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUNBUFFERED": "1",
}


# ----------------------------------------------------------------
# Result model
# ----------------------------------------------------------------


@dataclass
class CapturedOutput:
    """Text captured from one output stream of the container.

    Attributes:
        text: The decoded output, with a marker where the middle was cut.
        is_truncated: Whether part of the output was dropped.
    """

    text: str
    is_truncated: bool


@dataclass
class DockerRunResult:
    """Outcome of a single 'docker run' invocation.

    Internal, in-memory result, never serialized directly. The MCP tool layer
    maps this onto RunBashCommandResponse.

    Attributes:
        stdout: Output captured from the container's stdout.
        stderr: Output captured from the container's stderr.
        exit_code: Process exit code, TIMEOUT_EXIT_CODE when the command
            timed out and the container was killed.
        timed_out: True if the command exceeded its timeout.
    """

    stdout: CapturedOutput
    stderr: CapturedOutput
    exit_code: int
    timed_out: bool


# ----------------------------------------------------------------
# Execution
# ----------------------------------------------------------------


async def run_docker_container(
    mounts: list[BindMount],
    working_dir: PurePosixPath,
    command: str,
    timeout_seconds: int,
) -> DockerRunResult:
    """Run a shell command in a disposable, hardened Docker container.

    Asynchronous so that a long command never freezes the MCP server: the
    event loop keeps serving other requests while the container runs.

    The container gets no network, a read-only root filesystem with an
    in-memory /tmp, no Linux capabilities, no privilege escalation, and
    bounded memory, CPU and process count. It runs as the host user, so
    files it writes to bind mounts belong to that user rather than root.
    Only the given mounts expose host data.

    If the command exceeds timeout_seconds, the container is killed via
    'docker kill', since killing the 'docker run' client alone would leave
    the container running in the daemon.

    Args:
        mounts: Host directories to bind into the container.
        working_dir: Working directory of the command inside the container.
        command: Shell command executed via 'bash -c'.
        timeout_seconds: Maximum wall-clock time allowed for the command.

    Returns:
        A DockerRunResult with bounded output, exit code and timeout status.

    Raises:
        FileNotFoundError: If the 'docker' binary is not available on the host.
    """
    container_name = f"{_CONTAINER_NAME_PREFIX}{uuid.uuid4().hex}"
    arguments = build_docker_run_arguments(container_name, mounts, working_dir, command)

    output_limit_bytes = get_output_limit_bytes()
    stdout_buffer = BoundedOutputBuffer(output_limit_bytes)
    stderr_buffer = BoundedOutputBuffer(output_limit_bytes)

    # NOTE: stdin must not be inherited. With the stdio transport, the
    # server's stdin IS the MCP protocol stream.
    process = await asyncio.create_subprocess_exec(
        *arguments,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    timed_out = False
    try:
        await asyncio.wait_for(
            asyncio.gather(
                drain_stream(process.stdout, stdout_buffer),
                drain_stream(process.stderr, stderr_buffer),
                process.wait(),
            ),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        timed_out = True
        await _force_kill_container(container_name)
        await _reap_client_process(process)

    return DockerRunResult(
        stdout=CapturedOutput(stdout_buffer.render(), stdout_buffer.is_truncated),
        stderr=CapturedOutput(stderr_buffer.render(), stderr_buffer.is_truncated),
        exit_code=TIMEOUT_EXIT_CODE if timed_out else process.returncode,
        timed_out=timed_out,
    )


def build_docker_run_arguments(
    container_name: str,
    mounts: list[BindMount],
    working_dir: PurePosixPath,
    command: str,
) -> list[str]:
    """Build the full 'docker run' argument list for one command.

    Kept separate from the execution so the exact sandbox configuration can
    be inspected and tested without Docker.

    Bind mounts use '--mount' rather than '-v': '-v' silently creates a
    missing host directory (owned by root), whereas '--mount' fails loudly.

    Args:
        container_name: Unique name, used to kill the container on timeout.
        mounts: Host directories to bind into the container.
        working_dir: Working directory of the command inside the container.
        command: Shell command executed via 'bash -c'.

    Returns:
        The argument list, starting with 'docker'.
    """
    memory_limit = get_docker_memory_limit()

    arguments = [
        "docker", "run", "--rm",
        "--name", container_name,
        "--label", f"{RUNNER_LABEL}=1",
        "--network", "none",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--read-only",
        "--tmpfs", f"/tmp:rw,exec,nosuid,nodev,size={get_docker_tmp_size()}",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", get_docker_pids_limit(),
        "--memory", memory_limit,
        "--memory-swap", memory_limit,
        "--cpus", get_docker_cpu_limit(),
        "--workdir", str(working_dir),
    ]

    for name, value in _CONTAINER_ENVIRONMENT.items():
        arguments += ["--env", f"{name}={value}"]

    for mount in mounts:
        arguments += ["--mount", _format_mount_option(mount)]

    arguments += [get_docker_image(), "bash", "-c", command]
    return arguments


def _format_mount_option(mount: BindMount) -> str:
    """Format a BindMount as the value of a 'docker run --mount' option.

    Args:
        mount: The bind mount to format.

    Returns:
        A string such as 'type=bind,source=/home/x,target=/skills/y,readonly'.
    """
    option = f"type=bind,source={mount.host_path},target={mount.sandbox_path}"
    return f"{option},readonly" if mount.is_read_only else option


# ----------------------------------------------------------------
# Timeout cleanup
# ----------------------------------------------------------------


async def _force_kill_container(container_name: str) -> None:
    """Forcibly stop a container after its command has timed out.

    Best-effort cleanup: failures are swallowed since '--rm' will eventually
    remove the container once it stops, and surfacing a secondary error here
    would obscure the original timeout to the caller.

    Args:
        container_name: The '--name' value passed to the original 'docker run'.
    """
    try:
        kill_process = await asyncio.create_subprocess_exec(
            "docker", "kill", container_name,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(kill_process.wait(), timeout=get_container_kill_timeout_seconds())
    except (OSError, TimeoutError):
        pass


async def _reap_client_process(process: asyncio.subprocess.Process) -> None:
    """Wait for the 'docker run' client to exit after its container was killed.

    The client normally exits as soon as its container stops. If it does not
    within the kill timeout, it is killed too, so no zombie process is left.

    Args:
        process: The 'docker run' client process.
    """
    try:
        await asyncio.wait_for(process.wait(), timeout=get_container_kill_timeout_seconds())
    except TimeoutError:
        process.kill()
        await process.wait()
