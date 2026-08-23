"""Thin wrapper around mcp_server.tool_registry for the admin tools page."""
try:
    from mcp_server.tool_registry import (
        list_tools_for_agent,
        set_tool_enabled,
        init_registry_table,
    )
except ImportError:
    def init_registry_table():
        pass

    def list_tools_for_agent(agent_id):
        return []

    def set_tool_enabled(agent_id, tool, enabled, updated_by=None):
        raise RuntimeError("mcp_server.tool_registry not available")

__all__ = ["list_tools_for_agent", "set_tool_enabled", "init_registry_table"]
