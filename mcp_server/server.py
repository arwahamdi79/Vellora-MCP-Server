from .app import mcp

import mcp_server.tools
import mcp_server.resources
import mcp_server.prompts

if __name__ == "__main__":
    mcp.run()