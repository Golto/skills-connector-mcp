from typing import Annotated

from pydantic import BaseModel, Field

from src.mcp.tools.shared_models import SandboxPathParameter


MAX_READ_BYTES = 20000

MAX_READABLE_FILE_SIZE_BYTES = 10_000_000


StartLineParameter = Annotated[
    int,
    Field(
        ge=1,
        description="First line to read, starting at 1. Use next_start_line to continue.",
    ),
]


class ReadFileRequest(BaseModel):
    """Input for the read_file tool.

    Attributes:
        path: Sandbox path of the file.
        start_line: One-based number of the first line to return.
    """

    path: SandboxPathParameter
    start_line: StartLineParameter = 1


class ReadFileResponse(BaseModel):
    """Response returned by the read_file tool.

    Attributes:
        path: The file read, as a normalized sandbox path.
        content: The returned lines, line breaks included.
        start_line: Number of the first returned line.
        end_line: Number of the last returned line.
        total_lines: Number of lines in the whole file.
        next_start_line: Line to pass as start_line to read the rest of the
            file, null when the end of the file was reached.
    """

    path: str
    content: str
    start_line: int
    end_line: int
    total_lines: int
    next_start_line: int | None
