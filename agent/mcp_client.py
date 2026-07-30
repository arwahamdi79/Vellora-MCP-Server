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
