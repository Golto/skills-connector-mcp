from pydantic import BaseModel, Field


class RunBashCommandRequest(BaseModel):
    """Input for the run_bash_command tool.

    Attributes:
        skill_id: Identifier of the skill whose directory is mounted read-only
            at /skill inside the container.
        command: Shell command executed via 'bash -c' inside the container.
        timeout_seconds: Maximum wall-clock time allowed for the command before
            the container is killed.
        scratch_id: Optional id of an existing scratch directory to reuse,
            taken from a previous run_bash_command response. Lets an agent
            iterate against the same /workspace across multiple calls instead
            of starting from an empty directory each time. If omitted, a new
            scratch directory is created and its id is returned in the response.
    """

    skill_id: str
    command: str
    timeout_seconds: int = Field(default=30, gt=0)
    scratch_id: str | None = None


class RunBashCommandResponse(BaseModel):
    """Response returned by the run_bash_command tool.

    Attributes:
        stdout: Standard output captured from the command.
        stderr: Standard error captured from the command.
        exit_code: Process exit code. 124 indicates the command was killed
            after exceeding timeout_seconds.
        output_files: Relative paths of files found in the scratch directory
            after the command finished, so the caller knows what to retrieve.
        workspace_path: Absolute host path to the scratch directory. The
            directory is kept on disk after the call so output files remain
            retrievable.
        scratch_id: Id of the scratch directory used for this call. Pass this
            back as scratch_id in a subsequent call to reuse the same
            /workspace instead of starting fresh.
    """

    stdout: str
    stderr: str
    exit_code: int
    output_files: list[str]
    workspace_path: str
    scratch_id: str
