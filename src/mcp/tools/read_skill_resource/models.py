from pydantic import BaseModel


class ReadSkillResourceRequest(BaseModel):
    """Input for the read_skill_resource tool.

    Attributes:
        skill_id: Identifier of the skill that owns the resource.
        relative_path: Path to the file relative to the skill's root directory.
            Obtain valid paths from list_skill_files first.
    """

    skill_id: str
    relative_path: str


class ReadSkillResourceResponse(BaseModel):
    """Response returned by the read_skill_resource tool.

    Attributes:
        skill_id: Identifier of the skill that owns the resource.
        relative_path: The path that was read, echoed back for clarity.
        content: Full text content of the resource file.
    """

    skill_id: str
    relative_path: str
    content: str
