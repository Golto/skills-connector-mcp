import hashlib
import subprocess
from pathlib import Path

from src.mcp.tools.run_bash_command.config import (
    get_docker_build_context_dir,
    get_docker_image,
    get_image_build_timeout_seconds,
)


_DOCKERFILE_HASH_LABEL = "mcp-skills.dockerfile-hash"


class DockerImageBuildError(Exception):
    """Raised when the runner image cannot be found and fails to build."""


def _compute_dockerfile_hash(context_dir: Path) -> str:
    """Compute a SHA256 hash over the runner image's Dockerfile content.

    Used to detect whether the bundled Dockerfile has changed since the
    currently built image was produced, so a manual edit (e.g. adding a
    dependency) triggers an automatic rebuild at the next server startup.

    Args:
        context_dir: Absolute path to the Docker build context directory.

    Returns:
        A hex digest string (no 'sha256:' prefix, since it is stored as a
        Docker label value rather than compared against SkillEntry.hash).

    Raises:
        DockerImageBuildError: If no Dockerfile exists in context_dir.
    """
    dockerfile_path = context_dir / "Dockerfile"
    if not dockerfile_path.exists():
        raise DockerImageBuildError(
            f"No Dockerfile found in build context: {context_dir}"
        )
    return hashlib.sha256(dockerfile_path.read_bytes()).hexdigest()


def _get_image_label(image: str, label: str) -> str | None:
    """Read a single label value from a locally built Docker image.

    Args:
        image: The image reference to inspect.
        label: The label key to read.

    Returns:
        The label's value, or None if the image does not exist or the label
        is not set on it.
    """
    result = subprocess.run(
        [
            "docker", "image", "inspect",
            "--format", f'{{{{index .Config.Labels "{label}"}}}}',
            image,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    value = result.stdout.strip()
    return value if value and value != "<no value>" else None


def _image_is_up_to_date(image: str, context_dir: Path) -> bool:
    """Check whether a locally built image matches the current Dockerfile.

    An image is considered up to date only if it exists locally AND its
    stored dockerfile-hash label matches a fresh hash of the Dockerfile on
    disk. This catches both a missing image and a stale one built from an
    older version of the Dockerfile.

    Args:
        image: The image reference to check.
        context_dir: Absolute path to the Docker build context directory.

    Returns:
        True if the image exists and was built from the current Dockerfile.
    """
    stored_hash = _get_image_label(image, _DOCKERFILE_HASH_LABEL)
    if stored_hash is None:
        return False
    return stored_hash == _compute_dockerfile_hash(context_dir)


def _build_image(image: str, context_dir: Path) -> None:
    """Build the runner image from the bundled Dockerfile.

    The image is tagged with a dockerfile-hash label matching the current
    Dockerfile content, so a future call can detect whether a rebuild is
    needed without re-running the build itself.

    Args:
        image: The tag to assign to the built image.
        context_dir: Absolute path to the Docker build context directory.

    Raises:
        DockerImageBuildError: If the build fails or exceeds its timeout.
        FileNotFoundError: If the 'docker' binary is not available on the host.
    """
    dockerfile_hash = _compute_dockerfile_hash(context_dir)

    try:
        result = subprocess.run(
            [
                "docker", "build",
                "-t", image,
                "--label", f"{_DOCKERFILE_HASH_LABEL}={dockerfile_hash}",
                str(context_dir),
            ],
            capture_output=True,
            text=True,
            timeout=get_image_build_timeout_seconds(),
        )
    except subprocess.TimeoutExpired as error:
        raise DockerImageBuildError(
            f"Building image '{image}' exceeded the build timeout."
        ) from error

    if result.returncode != 0:
        raise DockerImageBuildError(
            f"Failed to build image '{image}':\n{result.stderr}"
        )


def ensure_runner_image_available() -> None:
    """Make sure the run_bash_command runner image is present and up to date.

    Called once at server startup when the active profile has allow_execution
    set to True. Compares a hash of the bundled Dockerfile against the label
    stored on the currently built image (if any): if they match, this is a
    no-op; otherwise the image is (re)built from the current Dockerfile,
    which covers both a missing image and one built from a stale Dockerfile.

    Raises:
        DockerImageBuildError: If the image is missing or stale and the build fails.
        FileNotFoundError: If the 'docker' binary is not available on the host.
    """
    image = get_docker_image()
    context_dir = get_docker_build_context_dir()

    if not _image_is_up_to_date(image, context_dir):
        _build_image(image, context_dir)
