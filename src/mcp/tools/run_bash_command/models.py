from typing import Annotated

from pydantic import BaseModel, Field

from src.mcp.tools.shared_models import SkillIdParameter


DEFAULT_TIMEOUT_SECONDS = 30


CommandParameter = Annotated[
    str,
    Field(
        min_length=1,
        description=(
            "Shell command run with 'bash -c'. The working directory is /workspace "
            "(read-write), so relative paths resolve there. The skill's files are "
            "read-only under /skill: always prefix them explicitly, for example "
            "'python /skill/scripts/run.py'."
        ),
    ),
]

TimeoutSecondsParameter = Annotated[
    int,
    Field(gt=0, description="Seconds before the container is killed (exit code 124)."),
]

ScratchIdParameter = Annotated[
    str | None,
    Field(
        description=(
            "scratch_id returned by a previous run_bash_command call, to keep "
            "working in the same /workspace. Omit to start from an empty one."
        ),
    ),
]


class RunBashCommandRequest(BaseModel):
    """Input for the run_bash_command tool.

    Attributes:
        skill_id: Identifier of the skill whose directory is mounted read-only
            at /skill inside the container.
        command: Shell command executed via 'bash -c' inside the container.
            The skill's files are available read-only under /skill (e.g.
            /skill/SKILL.md, /skill/scripts/setup.sh). The working directory
            is /workspace, mounted read-write: relative paths in the command
            resolve there, not under /skill. Always prefix skill file paths
            with /skill/ explicitly, for example: 'python /skill/scripts/run.py'.
        timeout_seconds: Maximum wall-clock time allowed for the command before
            the container is killed.
        scratch_id: Optional id of an existing scratch directory to reuse,
            taken from a previous run_bash_command response. Lets an agent
            iterate against the same /workspace across multiple calls instead
            of starting from an empty directory each time. If omitted, a new
            scratch directory is created and its id is returned in the response.
    """

    skill_id: SkillIdParameter
    command: CommandParameter
    timeout_seconds: TimeoutSecondsParameter = DEFAULT_TIMEOUT_SECONDS
    scratch_id: ScratchIdParameter = None


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
        sandbox_layout: ASCII tree of both mount points as they stand after
            the command finished: the read-only /skill directory and the
            read-write /workspace directory. Lets the agent see what was
            produced without a separate list_skill_files or follow-up call.
    """

    stdout: str
    stderr: str
    exit_code: int
    output_files: list[str]
    workspace_path: str
    scratch_id: str
    sandbox_layout: str
