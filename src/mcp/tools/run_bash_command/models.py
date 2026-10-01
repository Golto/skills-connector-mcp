from typing import Annotated

from pydantic import BaseModel, Field


DEFAULT_TIMEOUT_SECONDS = 30

MAX_TIMEOUT_SECONDS = 600


CommandParameter = Annotated[
    str,
    Field(
        min_length=1,
        description=(
            "Shell command run with 'bash -c', starting in /workspace. Run skill "
            "scripts by their full path, for example "
            "'python /skills/symbolic-math/scripts/cli.py diff \"x**2\" --var x'."
        ),
    ),
]

TimeoutSecondsParameter = Annotated[
    int,
    Field(
        gt=0,
        le=MAX_TIMEOUT_SECONDS,
        description="Seconds before the command is killed (exit code 124).",
    ),
]


class RunBashCommandRequest(BaseModel):
    """Input for the run_bash_command tool.

    Attributes:
        command: Shell command executed via 'bash -c' inside the container,
            with /workspace as working directory.
        timeout_seconds: Maximum wall-clock time allowed for the command before
            the container is killed.
    """

    command: CommandParameter
    timeout_seconds: TimeoutSecondsParameter = DEFAULT_TIMEOUT_SECONDS


class RunBashCommandResponse(BaseModel):
    """Response returned by the run_bash_command tool.

    Attributes:
        exit_code: Process exit code. 124 means the command was killed after
            exceeding timeout_seconds.
        stdout: Standard output of the command.
        stderr: Standard error of the command.
        is_output_truncated: True if stdout or stderr was too long and had its
            middle replaced by a '[... N bytes truncated ...]' marker.
    """

    exit_code: int
    stdout: str
    stderr: str
    is_output_truncated: bool
