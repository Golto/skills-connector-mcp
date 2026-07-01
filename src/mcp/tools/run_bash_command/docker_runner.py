import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from src.mcp.tools.run_bash_command.config import (
    get_container_kill_timeout_seconds,
    get_docker_cpu_limit,
    get_docker_image,
    get_docker_memory_limit,
)


@dataclass
class DockerRunResult:
    """Outcome of a single 'docker run' invocation.

    Internal, in-memory result, never serialized directly. The MCP tool layer
    maps this onto RunBashCommandResponse.

    Attributes:
        stdout: Standard output captured from the container.
        stderr: Standard error captured from the container.
        exit_code: Process exit code. 124 indicates a timeout was hit and the
            container was forcibly killed.
        timed_out: True if the command exceeded its timeout_seconds.
    """

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def run_docker_container(
    skill_dir: Path,
    scratch_dir: Path,
    command: str,
    timeout_seconds: int,
) -> DockerRunResult:
    """Run a shell command in a disposable Docker container scoped to one skill.

    Mounts skill_dir read-only at /skill and scratch_dir read-write at
    /workspace, sets /workspace as the working directory, and disables
    networking. The image and resource limits are fixed by the server
    operator (see config.py), never chosen by the caller.

    If the command exceeds timeout_seconds, the container is forcibly killed
    via 'docker kill' before returning, since 'docker run --rm' would otherwise
    keep the container alive in the daemon after the subprocess call times out.

    Args:
        skill_dir: Absolute path to the skill's root directory, mounted read-only.
        scratch_dir: Absolute path to the per-call scratch directory, mounted
            read-write as the container's working directory.
        command: Shell command executed via 'bash -c' inside the container.
        timeout_seconds: Maximum wall-clock time allowed for the command.

    Returns:
        A DockerRunResult with captured output, exit code, and timeout status.

    Raises:
        FileNotFoundError: If the 'docker' binary is not available on the host.
    """
    container_name = f"mcp-skills-run-{uuid.uuid4().hex}"
    docker_args = [
        "docker", "run", "--rm",
        "--name", container_name,
        "--network", "none",
        "--memory", get_docker_memory_limit(),
        "--cpus", get_docker_cpu_limit(),
        "-v", f"{skill_dir}:/skill:ro",
        "-v", f"{scratch_dir}:/workspace:rw",
        "-w", "/workspace",
        get_docker_image(),
        "bash", "-c", command,
    ]

    try:
        completed = subprocess.run(
            docker_args,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return DockerRunResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as error:
        _force_kill_container(container_name)
        return DockerRunResult(
            stdout=_coerce_text(error.stdout),
            stderr=_coerce_text(error.stderr) + f"\nCommand timed out after {timeout_seconds} seconds.",
            exit_code=124,
            timed_out=True,
        )


def _force_kill_container(container_name: str) -> None:
    """Forcibly stop a container after its command has timed out.

    Best-effort cleanup: failures are swallowed since '--rm' will eventually
    remove the container once it stops, and surfacing a secondary error here
    would obscure the original timeout to the caller.

    Args:
        container_name: The '--name' value passed to the original 'docker run'.
    """
    try:
        subprocess.run(
            ["docker", "kill", container_name],
            capture_output=True,
            text=True,
            timeout=get_container_kill_timeout_seconds(),
        )
    except subprocess.SubprocessError:
        pass


def _coerce_text(value: str | bytes | None) -> str:
    """Normalize subprocess output captured during a TimeoutExpired into a string.

    With text=True, partial output is typically already a string, but the
    subprocess API documents it as potentially None or bytes depending on
    how much was buffered before the timeout fired.

    Args:
        value: The raw stdout or stderr value from a TimeoutExpired exception.

    Returns:
        A decoded string, or an empty string if no output was captured.
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
