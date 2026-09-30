from src.mcp.context import AppRequestContext
from src.storage.models import SkillEntry


SKILLS_INDEX_URI = "skills://index"

_INDEX_TITLE = "# Available skills"

_INDEX_INTRODUCTION = (
    "Skills are packaged instructions for specific kinds of tasks. Only their "
    "summaries are listed below. When a task matches one of these skills, call "
    "read_skill with its id BEFORE starting the task, then follow the "
    "instructions it returns."
)

_RESOURCES_HINT = (
    "Skills marked [files] ship extra files (scripts, templates, references): "
    "discover them with list_skill_files, then read them with read_skill_resource."
)

_EXECUTION_HINT = (
    "Scripts shipped by a skill can be run with run_bash_command, in a sandbox "
    "where the skill's files are mounted read-only under /skill."
)

_EMPTY_SCOPE_MESSAGE = "No skills are available in the current scope."

_FILES_MARKER = "[files]"

_SENTENCE_ENDINGS = (".", "!", "?")


def build_skills_index(ctx: AppRequestContext) -> str:
    """Build a compact Markdown index of the skills visible in the current scope.

    The index is meant to be injected once into an agent's system prompt, so
    that the model knows which skills exist without having to call list_skills
    first. This mirrors progressive disclosure: only one line per skill is
    exposed up front, and the full SKILL.md is fetched on demand via read_skill.

    Usage hints only mention tools that are actually registered for the active
    profile, so the model is never pointed at a tool it cannot call. Skills
    present in the scope but absent from the registry are silently skipped,
    consistently with list_skills.

    Args:
        ctx: The active request context carrying scope and registry.

    Returns:
        The index as Markdown text. When the scope has no usable skill, a short
        message stating so instead of an empty list.
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
        return f"{_INDEX_TITLE}\n\n{_EMPTY_SCOPE_MESSAGE}"

    usage_hints = [_INDEX_INTRODUCTION]
    if has_any_resources:
        usage_hints.append(_RESOURCES_HINT)
    if ctx.scope.allow_execution:
        usage_hints.append(_EXECUTION_HINT)

    return "\n\n".join([_INDEX_TITLE, " ".join(usage_hints), "\n".join(skill_lines)])


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
