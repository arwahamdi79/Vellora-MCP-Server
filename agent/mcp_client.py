from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


class MCPClient:

    def __init__(self, server_path: str):

        self.server_path = server_path

        self.exit_stack = AsyncExitStack()

        self.session = None

        self.tools = []

        self.resources = []

        self.prompts = []

    async def connect(self):

        server = StdioServerParameters(
            command="python",
            args=[self.server_path]
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server)
        )

        read_stream, write_stream = stdio_transport

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(
                read_stream,
                write_stream
            )
        )

        await self.session.initialize()

        print("Connected to MCP Server")

    async def disconnect(self):

        await self.exit_stack.aclose()

    # ================================
    # Discovery Methods
    # ================================

    async def discover_tools(self):

        result = await self.session.list_tools()

        self.tools = result.tools

        return self.tools

    async def discover_resources(self):

        result = await self.session.list_resources()

        self.resources = result.resources

        return self.resources

    async def discover_prompts(self):

        result = await self.session.list_prompts()

        self.prompts = result.prompts

        return self.prompts

    async def discover_everything(self):

        await self.discover_tools()

        await self.discover_resources()

        await self.discover_prompts()

    # ================================
    # Tool / Resource / Prompt
    # ================================

    async def call_tool(
        self,
        tool_name,
        arguments
    ):

        return await self.session.call_tool(
            tool_name,
            arguments
        )

    async def read_resource(
        self,
        uri
    ):

        return await self.session.read_resource(uri)

    async def get_prompt(
        self,
        name,
        arguments
    ):

        return await self.session.get_prompt(
            name=name,
            arguments=arguments
        )

    # ================================
    # Helper Functions
    # ================================

    def tool_descriptions(self):

        text = ""

        for tool in self.tools:

            text += f"""
Tool:
{tool.name}

Description:
{tool.description}

"""

        return text

    def resource_descriptions(self):

        text = ""

        for resource in self.resources:

            text += f"""
Resource:

{resource.uri}

"""

        return text

    def prompt_descriptions(self):

        text = ""

        for prompt in self.prompts:

            text += f"""
Prompt:

{prompt.name}

"""

        return text
