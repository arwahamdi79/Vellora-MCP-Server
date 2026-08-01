from .app import mcp

import mcp_server.tools
import mcp_server.resources
import mcp_server.prompts
import mcp_server.rag_tools


if __name__ == "__main__":
    mcp.run()