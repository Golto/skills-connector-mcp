from typing import Annotated

from pydantic import BaseModel, Field

from src.mcp.tools.shared_models import SandboxPathParameter


ContentParameter = Annotated[
    str,
    Field(description="Full content of the file. An existing file is replaced entirely."),
]


class WriteFileRequest(BaseModel):
    """Input for the write_file tool.

    Attributes:
        path: Sandbox path of the file, under /workspace.
        content: Full content of the file.
    """

    path: SandboxPathParameter
    content: ContentParameter


class WriteFileResponse(BaseModel):
    """Response returned by the write_file tool.

    Attributes:
        path: The written file, as a normalized sandbox path.
        size_bytes: Size of the written file.
        was_created: True if the file did not exist before, False if it was replaced.
    """

    path: str
    size_bytes: int
    was_created: bool
