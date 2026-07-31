from .instance import mcp


from . import tools
from . import resources
from . import prompts


@mcp.tool()
def health_check():

    """
    Check MCP server status.
    """

    return {
        "status": "running",
        "server": "Vellora Therapeutics MCP Server"
    }


if __name__ == "__main__":

    mcp.run()