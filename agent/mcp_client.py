"""
MCP Client

Responsible for communicating with the MCP Server.

Responsibilities
----------------
- Connect to the MCP Server
- Discover available Tools / Resources / Prompts
- Execute Tools
- Read Resources
- Retrieve Prompts
"""

from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import (
    stdio_client,
    StdioServerParameters,
)


class MCPClient:

    def __init__(self, server_path: str):

        self.server_path = server_path

        self.exit_stack = AsyncExitStack()

        self.session: ClientSession | None = None

        self.connected = False

        self.tools = []
        self.resources = []
        self.prompts = []

    # =====================================================
    # Connection
    # =====================================================

    async def connect(self):

        try:

            server = StdioServerParameters(
                command="python",
                args=[self.server_path],
            )

            transport = await self.exit_stack.enter_async_context(
                stdio_client(server)
            )

            read_stream, write_stream = transport

            self.session = await self.exit_stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                )
            )

            await self.session.initialize()

            self.connected = True

            print("✅ Connected to MCP Server")

        except Exception as e:

            self.connected = False

            raise RuntimeError(
                f"Failed to connect to MCP Server.\n{e}"
            )

    async def disconnect(self):

        self.connected = False

        await self.exit_stack.aclose()

    # =====================================================
    # Discovery
    # =====================================================

    async def discover_tools(self):

        self._ensure_connection()

        result = await self.session.list_tools()

        self.tools = result.tools

        return self.tools

    async def discover_resources(self):

        self._ensure_connection()

        result = await self.session.list_resources()

        self.resources = result.resources

        return self.resources

    async def discover_prompts(self):

        self._ensure_connection()

        result = await self.session.list_prompts()

        self.prompts = result.prompts

        return self.prompts

    async def discover_everything(self):

        await self.discover_tools()

        await self.discover_resources()

        await self.discover_prompts()

        print()

        print("========== MCP Discovery ==========")

        print(f"Tools      : {len(self.tools)}")

        print(f"Resources  : {len(self.resources)}")

        print(f"Prompts    : {len(self.prompts)}")

        print("===================================")

        print()

    # =====================================================
    # Tool Calls
    # =====================================================

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
    ):

        self._ensure_connection()

        return await self.session.call_tool(
            tool_name,
            arguments,
        )

    # =====================================================
    # Resources
    # =====================================================

    async def read_resource(
        self,
        uri: str,
    ):

        self._ensure_connection()

        return await self.session.read_resource(uri)

    # =====================================================
    # Prompts
    # =====================================================

    async def get_prompt(
        self,
        name: str,
        arguments: dict,
    ):

        self._ensure_connection()

        return await self.session.get_prompt(
            name=name,
            arguments=arguments,
        )

    # =====================================================
    # Helpers
    # =====================================================

    def is_connected(self):

        return self.connected

    def capability_summary(self):

        return {
            "tools": len(self.tools),
            "resources": len(self.resources),
            "prompts": len(self.prompts),
        }

    def _ensure_connection(self):

        if not self.connected or self.session is None:

            raise RuntimeError(
                "MCP Server is not connected."
            )

    # =====================================================
    # Descriptions
    # =====================================================

    def tool_descriptions(self):

        if not self.tools:

            return "No tools available."

        lines = []

        for tool in self.tools:

            lines.append(
                f"""
Tool:
{tool.name}

Description:
{tool.description}
"""
            )

        return "\n".join(lines)

    def resource_descriptions(self):

        if not self.resources:

            return "No resources available."

        lines = []

        for resource in self.resources:

            description = getattr(
                resource,
                "description",
                "",
            )

            lines.append(
                f"""
Resource:
{resource.uri}

Description:
{description}
"""
            )

        return "\n".join(lines)

    def prompt_descriptions(self):

        if not self.prompts:

            return "No prompts available."

        lines = []

        for prompt in self.prompts:

            description = getattr(
                prompt,
                "description",
                "",
            )

            lines.append(
                f"""
Prompt:
{prompt.name}

Description:
{description}
"""
            )

        return "\n".join(lines)
