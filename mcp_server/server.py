from fastmcp import FastMCP

mcp = FastMCP("Vellora Therapeutics A")

@mcp.tool()
def hello(name: str) -> str:
    """Simple test tool"""
    return f"Hello {name}"

if __name__ == "__main__":
    mcp.run()