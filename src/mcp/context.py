from dataclasses import dataclass

from src.storage.models import Registry, ServerScope


@dataclass
class AppRequestContext:
    """Carries the fixed server state into every tool call.

    Built once in build_server() from the loaded profile and registry.
    The scope field is a mutable dataclass, so in-process mutations from
    create_skill or set_profile_skills are visible to subsequent tool calls
    without a reference swap. The registry field is replaced (not mutated)
    when a write tool updates it.

    Attributes:
        scope: In-memory representation of the active profile and visible skills.
        registry: The skill index loaded and synced at startup.
    """

    scope: ServerScope
    registry: Registry
