import subprocess

from src.mcp.tools.run_bash_command.config import (
    get_docker_build_context_dir,
    get_docker_image,
    get_image_build_timeout_seconds,
)


class DockerImageBuildError(Exception):
    """Raised when the runner image cannot be found and fails to build."""


def _image_exists(image: str) -> bool:
    """Check whether a Docker image is already present in the local image store.

    Args:
        image: The image reference to check (e.g. 'mcp-skills-runner:latest').

    Returns:
        True if 'docker image inspect' succeeds for this image.

    Raises:
        FileNotFoundError: If the 'docker' binary is not available on the host.
    """
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _build_image(image: str) -> None:
    """Build the runner image from the bundled Dockerfile.

    The build context is docker/mcp-skills-runner/ at the project root, so
    changes to the Dockerfile are picked up automatically the next time the
    image is missing (e.g. after a manual 'docker rmi').

    Args:
        image: The tag to assign to the built image.

    Raises:
        DockerImageBuildError: If the build fails or exceeds its timeout.
        FileNotFoundError: If the 'docker' binary is not available on the host.
    """
    context_dir = get_docker_build_context_dir()

    try:
        result = subprocess.run(
            ["docker", "build", "-t", image, str(context_dir)],
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
    """Make sure the run_bash_command runner image exists locally, building it if needed.

    Called once at server startup when the active profile has allow_execution
    set to True. If the image is already present, this is a no-op (a single
    fast 'docker image inspect' call). Otherwise the image is built from the
    bundled Dockerfile, which can take a while on a cold cache.

    Raises:
        DockerImageBuildError: If the image is missing and the build fails.
        FileNotFoundError: If the 'docker' binary is not available on the host.
    """
    image = get_docker_image()
    if not _image_exists(image):
        _build_image(image)
