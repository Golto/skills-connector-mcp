import sys

from mcp.server.fastmcp import FastMCP

from src.mcp.context import AppRequestContext
from src.mcp.launch_options import LaunchOptions
from src.mcp.resources.skills_index.resource import SKILLS_INDEX_URI, build_skills_index
from src.mcp.tools.list_skill_files.models import ListSkillFilesRequest, ListSkillFilesResponse
from src.mcp.tools.list_skill_files.tool import execute_list_skill_files
from src.mcp.tools.list_skills.models import ListSkillsResponse
from src.mcp.tools.list_skills.tool import execute_list_skills
from src.mcp.tools.read_skill.models import ReadSkillRequest, ReadSkillResponse
from src.mcp.tools.read_skill.tool import execute_read_skill
from src.mcp.tools.read_skill_resource.models import (
    ReadSkillResourceRequest,
    ReadSkillResourceResponse,
    RelativePathParameter,
)
from src.mcp.tools.read_skill_resource.tool import execute_read_skill_resource
from src.mcp.tools.run_bash_command.image_builder import ensure_runner_image_available
from src.mcp.tools.run_bash_command.models import (
    DEFAULT_TIMEOUT_SECONDS,
    CommandParameter,
    RunBashCommandRequest,
    RunBashCommandResponse,
    TimeoutSecondsParameter,
)
from src.mcp.tools.run_bash_command.tool import execute_run_bash_command
from src.mcp.tools.search_skills.models import (
    LimitParameter,
    QueryParameter,
    SearchSkillsRequest,
    SearchSkillsResponse,
)
from src.mcp.tools.search_skills.tool import execute_search_skills
from src.mcp.tools.shared_models import SkillIdParameter
from src.storage.bootstrap import ensure_data_directories_exist
from src.storage.models import ServerScope
from src.storage.profile_store import read_profile
from src.storage.registry_store import (
    read_registry,
    sync_skills_to_registry,
    write_registry,
)
from src.storage.workspace import WorkspaceLayout, resolve_workspace_layout


def build_server(options: LaunchOptions) -> FastMCP:
    """Bootstrap, sync, and configure a FastMCP server for the given launch options.

    Runs these startup steps in order:
    1. Bootstrap: create any missing data directories and files.
    2. Registry sync: reconcile registry.json with base/ and generated/ on disk.
    3. Profile load: read the profile and build the in-memory ServerScope.
    4. Workspace: resolve the host directories that make up /workspace.
    5. If allow_execution is set, make sure the runner image exists, building
       it from the bundled Dockerfile if it is missing locally.

    Tools are registered based on the profile's flags. Tools not permitted by
    the profile are not registered at all (absent from the MCP manifest rather
    than refusing at call time).

    Tool parameters are declared flat in each wrapper signature, not wrapped
    in a single request object: a nested {"request": {...}} argument is a
    frequent source of malformed tool calls with small local models. The
    wrappers rebuild the request models before delegating, so validation and
    the execute_* contracts are unchanged.

    The skills index is also exposed as the resource skills://index, meant
    to be injected into an agent's system prompt by the MCP client.

    Args:
        options: Profile and workspace options resolved at launch.

    Returns:
        A configured FastMCP instance ready to serve.

    Raises:
        ProfileNotFoundError: If the profile file does not exist.
        ProfileCorruptedError: If the profile file cannot be parsed.
        RegistryCorruptedError: If registry.json cannot be parsed.
        WorkspaceConfigError: If the workspace options point to an invalid
            paths.json or to a missing directory.
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

    profile = read_profile(options.profile_id)
    scope = ServerScope(
        profile_id=options.profile_id,
        skill_ids=list(profile.skill_ids),
        allow_generation=profile.allow_generation,
        allow_execution=profile.allow_execution,
    )

    workspace = resolve_workspace_layout(
        profile_id=options.profile_id,
        paths_dir=options.paths_dir,
        workspace_dir=options.workspace_dir,
    )

    if profile.allow_execution:
        ensure_runner_image_available()

    ctx = AppRequestContext(scope=scope, registry=registry, workspace=workspace)
    _report_startup_state(ctx.scope, workspace)
    mcp = FastMCP("mcp-skills")

    # ----------------------------------------------------------------
    # Resources
    # ----------------------------------------------------------------

    @mcp.resource(
        SKILLS_INDEX_URI,
        name="skills_index",
        description=(
            "One-line summary of every skill in the current scope, with usage "
            "hints. Meant to be injected into the agent's system prompt."
        ),
        mime_type="text/markdown",
    )
    def skills_index() -> str:
        return build_skills_index(ctx)

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
    def search_skills(
        query: QueryParameter,
        limit: LimitParameter = None,
    ) -> SearchSkillsResponse:
        """Search for skills by keywords within the current scope.

        All query words must appear somewhere in a skill's id, description,
        triggers, or tags for it to be returned (AND semantics).
        """
        return execute_search_skills(SearchSkillsRequest(query=query, limit=limit), ctx)

    @mcp.tool()
    def read_skill(skill_id: SkillIdParameter) -> ReadSkillResponse:
        """Return the full instructions (SKILL.md) of a skill.

        Call this before starting a task the skill applies to, then follow
        the returned instructions.
        """
        return execute_read_skill(ReadSkillRequest(skill_id=skill_id), ctx)

    @mcp.tool()
    def list_skill_files(skill_id: SkillIdParameter) -> ListSkillFilesResponse:
        """Return the sorted file tree of a skill directory.

        Use this before read_skill_resource to discover valid relative paths,
        since a skill's internal structure is not fixed.
        """
        return execute_list_skill_files(ListSkillFilesRequest(skill_id=skill_id), ctx)

    @mcp.tool()
    def read_skill_resource(
        skill_id: SkillIdParameter,
        relative_path: RelativePathParameter,
    ) -> ReadSkillResourceResponse:
        """Return the content of a specific file from a skill directory.

        Use list_skill_files first to discover valid relative paths.
        SKILL.md must be read via read_skill, not this tool.
        """
        request = ReadSkillResourceRequest(skill_id=skill_id, relative_path=relative_path)
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
        async def run_bash_command(
            command: CommandParameter,
            timeout_seconds: TimeoutSecondsParameter = DEFAULT_TIMEOUT_SECONDS,
        ) -> RunBashCommandResponse:
            """Run a shell command in an offline sandbox.

            Skills are read-only under /skills/<skill_id>/. The working
            directory /workspace is read-write: files written there are kept
            between calls, and the response lists those the command created,
            modified or deleted. Long output is cut in the middle.
            """
            request = RunBashCommandRequest(
                command=command,
                timeout_seconds=timeout_seconds,
            )
            return await execute_run_bash_command(request, ctx)

    return mcp


def _report_startup_state(scope: ServerScope, workspace: WorkspaceLayout) -> None:
    """Print the profile and workspace actually loaded to stderr.

    Launchers do not always forward environment variables (the MCP inspector
    started by 'mcp dev' drops them), which silently falls back to the
    default profile. Printing what was really loaded makes that visible at
    once. stderr is safe with the stdio transport, which only uses stdout.

    Args:
        scope: The scope built from the loaded profile.
        workspace: The resolved workspace layout.
    """
    print(
        f"mcp-skills: profile '{scope.profile_id}', {len(scope.skill_ids)} skill(s), "
        f"execution {'on' if scope.allow_execution else 'off'}, "
        f"workspace from {workspace.source.value}",
        file=sys.stderr,
    )
    for mount in workspace.mounts:
        print(f"mcp-skills:   {mount.sandbox_path} -> {mount.host_path}", file=sys.stderr)
