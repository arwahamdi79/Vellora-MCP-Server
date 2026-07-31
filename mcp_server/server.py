from fastmcp import FastMCP

from .capabilities import SERVER_DESCRIPTION


# Single MCP server instance
# All tools/resources/prompts attach here

mcp = FastMCP(
    name="Vellora Therapeutics MCP Server",
    instructions=SERVER_DESCRIPTION
)



# Import registrations
# These imports must come AFTER mcp creation

from . import tools
from . import resources
from . import prompts



@mcp.tool()
def health_check():

    """
    Check if MCP server is running.
    """

    return {
        "status": "running",
        "server": "Vellora Therapeutics MCP Server"
    }



if __name__ == "__main__":

    mcp.run()