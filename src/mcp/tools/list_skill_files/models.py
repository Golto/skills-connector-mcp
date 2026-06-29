from pydantic import BaseModel


class ListSkillFilesRequest(BaseModel):
    """Input for the list_skill_files tool.

    Attributes:
        skill_id: Identifier of the skill whose file tree should be returned.
    """

    skill_id: str


class ListSkillFilesResponse(BaseModel):
    """Response returned by the list_skill_files tool.

    Attributes:
        skill_id: Identifier of the skill that was inspected.
        files: Sorted list of relative file paths within the skill directory.
            manifest.json is excluded. SKILL.md is included.
    """

    skill_id: str
    files: list[str]
