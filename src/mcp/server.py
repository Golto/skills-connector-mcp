import os
from argparse import ArgumentParser

from mcp.server.fastmcp import FastMCP

from src.mcp.context import AppRequestContext
from src.mcp.tools.list_skill_files.models import ListSkillFilesRequest, ListSkillFilesResponse
from src.mcp.tools.list_skill_files.tool import execute_list_skill_files
from src.mcp.tools.list_skills.models import ListSkillsResponse
from src.mcp.tools.list_skills.tool import execute_list_skills
from src.mcp.tools.read_skill.models import ReadSkillRequest, ReadSkillResponse
from src.mcp.tools.read_skill.tool import execute_read_skill
from src.mcp.tools.read_skill_resource.models import (
    ReadSkillResourceRequest,
    ReadSkillResourceResponse,
)
from src.mcp.tools.read_skill_resource.tool import execute_read_skill_resource
from src.mcp.tools.run_bash_command.image_builder import ensure_runner_image_available
from src.mcp.tools.run_bash_command.models import RunBashCommandRequest, RunBashCommandResponse
from src.mcp.tools.run_bash_command.tool import execute_run_bash_command
from src.mcp.tools.search_skills.models import SearchSkillsRequest, SearchSkillsResponse
from src.mcp.tools.search_skills.tool import execute_search_skills
from src.storage.bootstrap import ensure_data_directories_exist
from src.storage.models import ServerScope
from src.storage.profile_store import read_profile
from src.storage.registry_store import (
    read_registry,
    sync_skills_to_registry,
    write_registry,
)


_DEFAULT_PROFILE_ID = "default"


def resolve_profile_id() -> str:
    """Resolve the active profile id from CLI arguments or environment variable.

    Precedence (highest to lowest):
    1. --profile <id> CLI argument (parsed with parse_known_args to tolerate
       flags injected by uv or mcp run).
    2. MCP_SKILLS_PROFILE environment variable.
    3. 'default'.

    Returns:
        The resolved profile identifier.
    """
    parser = ArgumentParser(add_help=False)
    parser.add_argument("--profile", default=None)
    args, _ = parser.parse_known_args()

    if args.profile:
        return args.profile

    env_profile = os.environ.get("MCP_SKILLS_PROFILE", "").strip()
    if env_profile:
        return env_profile

    return _DEFAULT_PROFILE_ID


def build_server(profile_id: str) -> FastMCP:
    """Bootstrap, sync, and configure a FastMCP server for the given profile.

    Runs these startup steps in order:
    1. Bootstrap: create any missing data directories and files.
    2. Registry sync: reconcile registry.json with base/ and generated/ on disk.
    3. Profile load: read the profile and build the in-memory ServerScope.
    4. If allow_execution is set, make sure the runner image exists, building
       it from the bundled Dockerfile if it is missing locally.

    Tools are registered based on the profile's flags. Tools not permitted by
    the profile are not registered at all (absent from the MCP manifest rather
    than refusing at call time).

    Args:
        profile_id: The profile identifier to load.

    Returns:
        A configured FastMCP instance ready to serve.

    Raises:
        ProfileNotFoundError: If the profile file does not exist.
        ProfileCorruptedError: If the profile file cannot be parsed.
        RegistryCorruptedError: If registry.json cannot be parsed.
        DockerImageBuildError: If allow_execution is set and the runner image
            is missing and fails to build.
    """
    # ----------------------------------------------------------------
    # Startup sequence
    # ----------------------------------------------------------------

    ensure_data_directories_exist()

    registry = read_registry()
    registry, was_modified = sync_skills_to_registry(registry)
    if was_modified:
        write_registry(registry)

    profile = read_profile(profile_id)
    scope = ServerScope(
        profile_id=profile_id,
        skill_ids=list(profile.skill_ids),
        allow_generation=profile.allow_generation,
        allow_execution=profile.allow_execution,
    )

    if profile.allow_execution:
        ensure_runner_image_available()

    ctx = AppRequestContext(scope=scope, registry=registry)
    mcp = FastMCP("mcp-skills")

    # ----------------------------------------------------------------
    # Always-loaded tools
    # ----------------------------------------------------------------

    @mcp.tool()
    def list_skills() -> ListSkillsResponse:
        """List all skills available in the current scope.

        Returns each skill's id, description, tags, origin (base or generated),
        and whether it has resource files beyond SKILL.md.
        """
        return execute_list_skills(ctx)

    @mcp.tool()
    def search_skills(request: SearchSkillsRequest) -> SearchSkillsResponse:
        """Search for skills by keywords, triggers, or tags within the current scope.

        All query words must appear somewhere in a skill's id, description,
        triggers, or tags for it to be returned (AND semantics). Results can
        be capped with the optional limit field.
        """
        return execute_search_skills(request, ctx)

    @mcp.tool()
    def read_skill(request: ReadSkillRequest) -> ReadSkillResponse:
        """Return the full content of a skill's SKILL.md.

        Raises an error if the skill_id is not in the current scope.
        """
        return execute_read_skill(request, ctx)

    @mcp.tool()
    def list_skill_files(request: ListSkillFilesRequest) -> ListSkillFilesResponse:
        """Return the sorted file tree of a skill directory, excluding manifest.json.

        Use this before read_skill_resource to discover available relative paths,
        since a skill's internal structure is not fixed.
        """
        return execute_list_skill_files(request, ctx)

    @mcp.tool()
    def read_skill_resource(
        request: ReadSkillResourceRequest,
    ) -> ReadSkillResourceResponse:
        """Return the content of a specific file from a skill directory.

        Use list_skill_files first to discover valid relative paths.
        SKILL.md must be read via read_skill, not this tool.
        """
        return execute_read_skill_resource(request, ctx)

    # ----------------------------------------------------------------
    # Conditional tools: allow_generation
    # ----------------------------------------------------------------
    # NOTE: create_skill and set_profile_skills are registered here when
    # allow_generation is active. Not yet implemented.

    # ----------------------------------------------------------------
    # Conditional tools: allow_execution
    # ----------------------------------------------------------------

    if profile.allow_execution:

        @mcp.tool()
        def run_bash_command(
            request: RunBashCommandRequest,
        ) -> RunBashCommandResponse:
            """Run a shell command in a disposable Docker container scoped to one skill.

            The skill directory is mounted read-only at /skill. The scratch
            directory mounted read-write at /workspace is either freshly
            created or reused from a previous call via scratch_id, so you can
            iterate against the same /workspace across multiple calls instead
            of starting from an empty directory each time. The response
            always returns the scratch_id used, to pass back into a follow-up
            call. The scratch directory is kept on disk after the call so
            output files remain retrievable via workspace_path. Networking is
            disabled inside the container.
            """
            return execute_run_bash_command(request, ctx)

    return mcp
