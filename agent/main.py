import asyncio

from config import SERVER_PATH
from mcp_client import MCPClient


async def main():
    # Create an MCP client instance
    client = MCPClient(SERVER_PATH)

    try:
        # Connect to the MCP Server
        await client.connect()

        # Discover all available capabilities
        await client.discover_everything()

        # Display all available tools
        print("\n========== TOOLS ==========\n")

        for tool in client.tools:
            print(tool.name)

        # Display all available resources
        print("\n========== RESOURCES ==========\n")

        for resource in client.resources:
            print(resource.uri)

        # Display all available prompts
        print("\n========== PROMPTS ==========\n")

        for prompt in client.prompts:
            print(prompt.name)

    finally:
        # Close the connection gracefully
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
