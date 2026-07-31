"""
MCP Client

Responsible for:
- Connecting to MCP Server
- Initialize exchange
- Capability checking
- Discovering tools/resources/prompts
- Calling MCP features
"""

import sys
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import (
    stdio_client,
    StdioServerParameters,
)


class MCPClient:

    def __init__(self, server_path=None):

        self.server_path = server_path

        self.exit_stack = AsyncExitStack()

        self.session = None

        self.connected = False

        self.capabilities = None

        self.tools = []

        self.resources = []

        self.prompts = []


    # =====================================
    # Connect
    # =====================================

    async def connect(self):

        server = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "mcp_server.server"
            ],
        )

        transport = await self.exit_stack.enter_async_context(
            stdio_client(server)
        )

        read_stream, write_stream = transport

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(
                read_stream,
                write_stream
            )
        )

        initialize_result = await self.session.initialize()

        self.capabilities = initialize_result.capabilities

        self.connected = True

        print("✅ Connected to MCP Server")

        self.check_capabilities()


    # =====================================
    # Capability Check
    # =====================================

    def check_capabilities(self):

        if self.capabilities is None:

            raise RuntimeError(
                "Server did not provide capabilities"
            )

        print(
            "✅ Server capabilities received"
        )


    # =====================================
    # Disconnect
    # =====================================

    async def disconnect(self):

        self.connected = False

        await self.exit_stack.aclose()


    # =====================================
    # Discovery
    # =====================================

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

        print()

        print("========== MCP Discovery ==========")

        print(
            f"Tools     : {len(self.tools)}"
        )

        print(
            f"Resources : {len(self.resources)}"
        )

        print(
            f"Prompts   : {len(self.prompts)}"
        )

        print(
            "================================="
        )


    # =====================================
    # Tool Execution
    # =====================================

    async def call_tool(
        self,
        name,
        arguments
    ):

        result = await self.session.call_tool(
            name,
            arguments
        )

        return result.content


    # =====================================
    # Resources
    # =====================================

    async def read_resource(
        self,
        uri
    ):

        return await self.session.read_resource(uri)


    # =====================================
    # Prompts
    # =====================================

    async def get_prompt(
        self,
        name,
        arguments
    ):

        return await self.session.get_prompt(
            name=name,
            arguments=arguments
        )


    # =====================================
    # Descriptions
    # =====================================

    def tool_descriptions(self):

        return "\n".join(
            [
                f"{tool.name}: {tool.description}"
                for tool in self.tools
            ]
        )


    def resource_descriptions(self):

         return "\n".join(
        [
            str(resource.uri)
            for resource in self.resources
        ]
    )


    def prompt_descriptions(self):

        return "\n".join(
        [
            str(prompt.name)
            for prompt in self.prompts
        ]
    )