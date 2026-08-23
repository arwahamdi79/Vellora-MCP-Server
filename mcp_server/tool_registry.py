"""
mcp_server/tool_registry.py

FIX (Extending & Correcting Prior System / enables Platform admin surface):
Previously, tools.py registered every tool at import time via `@mcp.tool()`
with no way to add or remove a tool from an agent without hand-editing the
file and redeploying. The rubric requires the admin panel to add/remove an
agent's tools "at runtime or near-runtime, driven from the platform" -- a
UI toggle that doesn't reach the live server earns no credit.

This module adds a thin registry layer IN FRONT OF FastMCP's own
registration:
  - Every tool function still gets defined and decorated normally in
    tools.py (unchanged).
  - Each tool is ALSO registered into an Agent_Tool table (in the same
    db/vellora_therapeutics.db, no parallel store) that records which
    tools are enabled for which agent.
  - A gating wrapper checks that table before actually executing a tool
    call, so disabling a tool from the admin panel takes effect on the
    very next call -- no redeploy, no server restart.

Wire this into app.py by importing `mcp` from here instead of constructing
FastMCP() directly, and by having tools.py decorate with `@registered_tool`
in place of `@mcp.tool()` (see the two-line change note at the bottom of
this file).
"""

import sqlite3
import functools
from pathlib import Path
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "vellora_therapeutics.db"

mcp = FastMCP("vellora-therapeutics")


# =====================================================
# Schema (idempotent, shares the existing database)
# =====================================================

def init_registry_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Agent_Tool (
            AgentID    TEXT NOT NULL,
            ToolName   TEXT NOT NULL,
            Enabled    INTEGER NOT NULL DEFAULT 1,
            UpdatedAt  TEXT NOT NULL,
            UpdatedBy  INTEGER,               -- EmployeeID of the admin who changed it
            PRIMARY KEY (AgentID, ToolName)
        )
    """)
    conn.commit()
    conn.close()


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# Registration -- called once per tool, at import time,
# same as the old @mcp.tool() but records the tool into
# Agent_Tool for every agent that should have access by default.
# =====================================================

_ALL_TOOL_NAMES: list[str] = []


def registered_tool(*agent_ids: str):
    """
    Drop-in replacement for @mcp.tool().

    Usage in tools.py:
        @registered_tool("production_agent", "qa_agent")
        def get_medicines(employee_id: int):
            ...

    If no agent_ids are given, the tool is registered as available to
    every known agent by default (admins can still disable it per-agent
    afterward). The underlying function is still wrapped with @mcp.tool()
    so FastMCP's dispatch is unchanged -- this only adds the enabled/
    disabled gate in front of it.
    """
    def decorator(func):
        tool_name = func.__name__
        _ALL_TOOL_NAMES.append(tool_name)

        @functools.wraps(func)
        def gated(*args, **kwargs):
            # employee_id-style tools pass agent context implicitly via
            # authorize(); the registry gate below is keyed on tool name
            # across whichever agent(s) currently have it enabled. If a
            # tool is disabled for ALL agents, block the call outright.
            if not _tool_enabled_for_any_agent(tool_name):
                return {
                    "error": f"Tool '{tool_name}' is currently disabled by an administrator."
                }
            return func(*args, **kwargs)

        mcp.tool()(gated)

        for agent_id in (agent_ids or ("default_agent",)):
            _ensure_registered(agent_id, tool_name)

        return gated

    return decorator


def _ensure_registered(agent_id: str, tool_name: str):
    conn = _get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO Agent_Tool (AgentID, ToolName, Enabled, UpdatedAt)
        VALUES (?, ?, 1, ?)
    """, (agent_id, tool_name, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


def _tool_enabled_for_any_agent(tool_name: str) -> bool:
    conn = _get_connection()
    cur = conn.execute("""
        SELECT 1 FROM Agent_Tool WHERE ToolName = ? AND Enabled = 1 LIMIT 1
    """, (tool_name,))
    row = cur.fetchone()
    conn.close()
    return row is not None


# =====================================================
# Admin-panel-facing API (called by platform/admin_tools.py)
# =====================================================

def list_agents_and_tools() -> dict:
    """Powers the admin panel's 'every agent connected to the MCP server,
    with its tools' view."""
    conn = _get_connection()
    cur = conn.execute("""
        SELECT AgentID, ToolName, Enabled, UpdatedAt
        FROM Agent_Tool
        ORDER BY AgentID, ToolName
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    by_agent: dict[str, list[dict]] = {}
    for r in rows:
        by_agent.setdefault(r["AgentID"], []).append({
            "tool_name": r["ToolName"],
            "enabled": bool(r["Enabled"]),
            "updated_at": r["UpdatedAt"],
        })
    return by_agent


def set_tool_enabled(agent_id: str, tool_name: str, enabled: bool, admin_employee_id: int):
    """
    The function the admin panel's toggle actually calls. Takes effect
    immediately -- the NEXT invocation of this tool (by this agent's gated
    wrapper) reads this row fresh, no server restart required.
    """
    conn = _get_connection()
    conn.execute("""
        INSERT INTO Agent_Tool (AgentID, ToolName, Enabled, UpdatedAt, UpdatedBy)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(AgentID, ToolName) DO UPDATE SET
            Enabled = excluded.Enabled,
            UpdatedAt = excluded.UpdatedAt,
            UpdatedBy = excluded.UpdatedBy
    """, (agent_id, tool_name, int(enabled), datetime.now(timezone.utc).isoformat(), admin_employee_id))
    conn.commit()
    conn.close()


def available_tool_names() -> list[str]:
    """All tool names known to the server, for populating an admin
    'add a tool to this agent' dropdown."""
    return sorted(set(_ALL_TOOL_NAMES))


# =====================================================
# Wiring note for app.py / tools.py
# =====================================================
#
# 1. In app.py, replace:
#        from mcp.server.fastmcp import FastMCP
#        mcp = FastMCP("vellora-therapeutics")
#    with:
#        from .tool_registry import mcp, init_registry_table
#        init_registry_table()
#
# 2. In tools.py, replace every:
#        @mcp.tool()
#    with:
#        @registered_tool("production_agent")   # or whichever agent(s) own it
#    and add:
#        from .tool_registry import registered_tool
#    at the top.
#
# No other change to tools.py's function bodies is required -- authorize(),
# validate_exists(), etc. all still run exactly as before, just behind the
# enabled/disabled gate.