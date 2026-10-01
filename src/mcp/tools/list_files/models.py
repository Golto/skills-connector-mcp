from pydantic import BaseModel

from src.mcp.tools.shared_models import SandboxPathParameter


DEFAULT_LIST_PATH = "/"

MAX_LISTED_ENTRIES = 200


class ListFilesRequest(BaseModel):
    """Input for the list_files tool.

    Attributes:
        path: Sandbox directory to list recursively.
    """

    path: SandboxPathParameter = DEFAULT_LIST_PATH


class ListFilesResponse(BaseModel):
    """Response returned by the list_files tool.

    Attributes:
        path: The listed directory, normalized.
        entries: Every file under it, as absolute sandbox paths. Empty
            directories end with '/'. An empty list means an empty directory.
        is_truncated: True if the listing stopped at MAX_LISTED_ENTRIES
            entries; list a deeper directory to see the rest.
    """

    path: str
    entries: list[str]
    is_truncated: bool
