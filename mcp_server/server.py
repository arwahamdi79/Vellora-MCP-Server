from fastmcp import FastMCP
from .elicitation import input_required
from .validation import (
    validate_positive_integer,
    validate_choice,
    validate_exists,
)
from .validation import (
    validate_exists,
    validate_positive_integer,
    validate_choice,
)
from .capabilities import SERVER_DESCRIPTION

mcp = FastMCP(
    name="Vellora Therapeutics MCP Server",
    instructions=SERVER_DESCRIPTION,
)

@mcp.tool()
def hello(name: str) -> str:
    """Simple test tool"""
    return f"Hello {name}"

if __name__ == "__main__":
    mcp.run()