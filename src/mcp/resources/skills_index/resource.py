from src.mcp.context import AppRequestContext
from src.mcp.tools.write_file.tool import is_write_file_available
from src.storage.models import SkillEntry
from src.storage.skill_store import SANDBOX_SKILLS_ROOT
from src.storage.workspace import SANDBOX_WORKSPACE_ROOT, WorkspaceLayout


SKILLS_INDEX_URI = "skills://index"

_INDEX_TITLE = "# Available skills"

_INDEX_INTRODUCTION = (
    "Skills are packaged instructions for specific kinds of tasks. Only their "
    "summaries are listed below. When a task matches one of these skills, call "
    "read_skill with its id BEFORE starting the task, then follow the "
    "instructions it returns."
)

_RESOURCES_HINT = (
    "Skills marked [files] ship extra files (scripts, templates, references) "
    f"under {SANDBOX_SKILLS_ROOT}/<skill_id>/: discover them with list_files, "
    "then read them with read_file."
)

_EMPTY_SCOPE_MESSAGE = "No skills are available in the current scope."

_FILES_MARKER = "[files]"

_SENTENCE_ENDINGS = (".", "!", "?")

_SANDBOX_TITLE = "## Sandbox"

_SANDBOX_INTRODUCTION = (
    "run_bash_command runs shell commands in a fresh container, without network: "
    "packages cannot be installed. Paths are the same in every tool:"
)

_SKILLS_MOUNT_LINE = (
    f"- {SANDBOX_SKILLS_ROOT}/<skill_id>/: skill files, read-only. Run a script by "
    f"its full path, for example 'python {SANDBOX_SKILLS_ROOT}/<skill_id>/scripts/"
    "<script>.py', without changing directory."
)

_WRITE_FILE_HINT = "Write files with write_file rather than with shell redirections."


def build_skills_index(ctx: AppRequestContext) -> str:
    """Build a compact Markdown index of the skills visible in the current scope.

    The index is meant to be injected once into an agent's system prompt, so
    that the model knows which skills exist without having to call list_skills
    first. This mirrors progressive disclosure: only one line per skill is
    exposed up front, and the full SKILL.md is fetched on demand via read_skill.

    When execution is allowed, a Sandbox section follows, describing the
    actual workspace layout of this server process. It is the one place
    where the layout is spelled out, rather than in every tool response.

    Usage hints only mention tools that are actually registered for the active
    profile, so the model is never pointed at a tool it cannot call. Skills
    present in the scope but absent from the registry are silently skipped,
    consistently with list_skills.

    Args:
        ctx: The active request context carrying scope, registry and workspace.

    Returns:
        The index as Markdown text. When the scope has no usable skill, a short
        message stating so instead of an empty list.
    """
    sections = [_INDEX_TITLE, _build_skills_section(ctx)]

    if ctx.scope.allow_execution:
        sections.append(_build_sandbox_section(ctx))

    return "\n\n".join(sections)


def _build_skills_section(ctx: AppRequestContext) -> str:
    """Build the usage hints and the one-line-per-skill list.

    Args:
        ctx: The active request context carrying scope and registry.

    Returns:
        The hints followed by the skill list, or the empty-scope message.
    """
    skill_lines: list[str] = []
    has_any_resources = False

    for skill_id in ctx.scope.skill_ids:
        entry = ctx.registry.skills.get(skill_id)
        if entry is None:
            continue

        skill_lines.append(_format_skill_line(skill_id, entry))
        has_any_resources = has_any_resources or entry.has_resources

    if not skill_lines:
        return _EMPTY_SCOPE_MESSAGE

    usage_hints = [_INDEX_INTRODUCTION]
    if has_any_resources:
        usage_hints.append(_RESOURCES_HINT)

    return "\n\n".join([" ".join(usage_hints), "\n".join(skill_lines)])


def _build_sandbox_section(ctx: AppRequestContext) -> str:
    """Describe the sandbox mounts as the agent sees them.

    Args:
        ctx: The active request context carrying scope and workspace.

    Returns:
        The Sandbox section, as Markdown.
    """
    lines = [_SANDBOX_TITLE, "", _SANDBOX_INTRODUCTION, _SKILLS_MOUNT_LINE]
    lines += _format_workspace_lines(ctx.workspace)

    if is_write_file_available(ctx.scope, ctx.workspace):
        lines += ["", _WRITE_FILE_HINT]

    return "\n".join(lines)


def _format_workspace_lines(workspace: WorkspaceLayout) -> list[str]:
    """Describe the workspace, whether a single directory or named folders.

    Named folders come from the client's paths.json, which also configures
    its other file tools: the line ties each folder to that project name, so
    the agent knows the same files are reachable both ways.

    Args:
        workspace: The resolved workspace layout.

    Returns:
        One list item per mount, plus a warning when /workspace itself is
        read-only.
    """
    named_mounts = [mount for mount in workspace.mounts if mount.name is not None]
    if not named_mounts:
        return [
            f"- {SANDBOX_WORKSPACE_ROOT}/: working directory, read-write. Files "
            "written there are kept between calls."
        ]

    lines = [
        f"- {mount.sandbox_path}/: read-write, kept between calls. Same files as "
        f"the project '{mount.name}' of your other file tools."
        for mount in named_mounts
    ]
    lines.append(
        f"{SANDBOX_WORKSPACE_ROOT}/ is the working directory but is itself "
        "read-only: write inside one of the folders above."
    )
    return lines


def _format_skill_line(skill_id: str, entry: SkillEntry) -> str:
    """Format one skill as a single Markdown list item.

    Whitespace in the description and triggers is collapsed so that a
    multi-line frontmatter value never breaks the one-line-per-skill layout.
    The description is closed with a period when it lacks final punctuation,
    so that the trigger list reads as a separate sentence.

    Args:
        skill_id: Identifier of the skill, as expected by read_skill.
        entry: Registry entry holding the skill's metadata.

    Returns:
        A line such as '- python-style: Python conventions. Use when: writing
        Python code; Python style. [files]'.
    """
    description = _collapse_whitespace(entry.description)
    if description and not description.endswith(_SENTENCE_ENDINGS):
        description += "."

    line = f"- {skill_id}: {description}"

    triggers = [_collapse_whitespace(trigger) for trigger in entry.triggers if trigger.strip()]
    if triggers:
        line += f" Use when: {'; '.join(triggers)}."

    if entry.has_resources:
        line += f" {_FILES_MARKER}"

    return line


def _collapse_whitespace(text: str) -> str:
    """Replace every run of whitespace, line breaks included, with a single space.

    Args:
        text: Raw text taken from a SKILL.md frontmatter field.

    Returns:
        The text on a single line, stripped at both ends.
    """
    return " ".join(text.split())
