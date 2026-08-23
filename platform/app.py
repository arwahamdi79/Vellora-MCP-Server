"""
platform/app.py

Flask website — admin surface + user surface, wired against the live
backend (shared SQLite + state_graph persistence + MCP tool registry).

Routes:
  /                 -> redirect to /chat
  /chat             -> user agent switcher + chat
  /admin            -> admin dashboard
  /admin/tools      -> add/remove MCP tools per agent
  /admin/rag        -> add/remove RAG documents
  /admin/hitl       -> pending HITL tasks, approve/reject
  /admin/tickets    -> open failure tickets, resolve/retry
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make repo root importable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask, redirect, render_template_string, request, jsonify

from state_graph import persistence as store
from state_graph.graphs import GRAPHS, get_graph, list_graphs

app = Flask(__name__)
app.secret_key = os.getenv("PLATFORM_SECRET", "vellora-dev-secret")

# ---------------------------------------------------------------------------
# Minimal HTML shells (no external template dependency)
# ---------------------------------------------------------------------------

BASE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Vellora Platform</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
    nav { background: #1e293b; padding: 12px 20px; display: flex; gap: 16px; align-items: center; }
    nav a { color: #93c5fd; text-decoration: none; }
    nav a:hover { text-decoration: underline; }
    main { padding: 24px; max-width: 960px; margin: 0 auto; }
    .card { background: #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .btn { background: #3b82f6; color: white; border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; }
    .btn.danger { background: #ef4444; }
    .btn.ok { background: #22c55e; }
    input, select, textarea { background: #0f172a; color: #e2e8f0; border: 1px solid #334155; padding: 8px; border-radius: 4px; width: 100%; box-sizing: border-box; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #334155; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
    .badge.pending { background: #f59e0b; color: #000; }
    .badge.open { background: #ef4444; }
    .badge.resolved { background: #22c55e; color: #000; }
  </style>
</head>
<body>
  <nav>
    <strong>Vellora</strong>
    <a href="/chat">User Chat</a>
    <a href="/admin">Admin</a>
    <a href="/admin/tools">Tools</a>
    <a href="/admin/rag">RAG Docs</a>
    <a href="/admin/hitl">HITL Tasks</a>
    <a href="/admin/tickets">Tickets</a>
  </nav>
  <main>{{ body|safe }}</main>
</body>
</html>
"""


def page(body: str) -> str:
    return render_template_string(BASE, body=body)


# ---------------------------------------------------------------------------
# User surface
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect("/chat")


@app.route("/chat", methods=["GET", "POST"])
def chat():
    agents = list(GRAPHS.keys()) + ["memory_rag", "planning"]
    selected = request.form.get("agent") or request.args.get("agent") or agents[0]
    messages = []
    reply = ""

    if request.method == "POST":
        user_msg = request.form.get("message", "").strip()
        if user_msg:
            messages.append({"role": "user", "content": user_msg})
            # Route to state-graph agents when selected
            if selected in GRAPHS:
                mod = get_graph(selected)
                if selected == "batch_release":
                    result = mod.run(batch_id=user_msg or "BATCH-DEMO", is_new_supplier=True)
                elif selected == "recall_execution":
                    result = mod.run(recall_id=user_msg or "RCL-DEMO", units_affected=15000)
                else:
                    result = mod.run(supplier_id=user_msg or "SUP-DEMO", estimated_cost=7500)
                reply = (
                    f"[{selected}] status={result.get('status')} "
                    f"run_id={result.get('run_id')} "
                    f"{result.get('reason') or result.get('error') or ''}"
                )
                if result.get("task_id"):
                    reply += f" | HITL task: {result['task_id']} (resolve at /admin/hitl)"
                if result.get("ticket_id"):
                    reply += f" | Ticket: {result['ticket_id']} (resolve at /admin/tickets)"
            else:
                reply = f"[{selected}] received: {user_msg} (memory/planning agents available in prior labs)"
            messages.append({"role": "assistant", "content": reply})

    opts = "".join(
        f'<option value="{a}" {"selected" if a == selected else ""}>{a}</option>'
        for a in agents
    )
    hist = "".join(
        f'<div class="card"><b>{m["role"]}</b>: {m["content"]}</div>' for m in messages
    )
    body = f"""
    <h2>User Chat</h2>
    <form method="post" class="card">
      <label>Agent</label>
      <select name="agent">{opts}</select>
      <label style="margin-top:12px;display:block">Message</label>
      <textarea name="message" rows="3" placeholder="e.g. BATCH-001 or describe the request"></textarea>
      <p style="margin-top:12px"><button class="btn" type="submit">Send</button></p>
    </form>
    {hist}
    """
    return page(body)


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------

@app.route("/admin")
def admin_home():
    hitl = store.list_hitl_tasks("pending")
    tickets = store.list_tickets("open")
    body = f"""
    <h2>Admin Dashboard</h2>
    <div class="card">
      <p>Pending HITL tasks: <b>{len(hitl)}</b></p>
      <p>Open failure tickets: <b>{len(tickets)}</b></p>
      <p>Graphs: {', '.join(GRAPHS.keys())}</p>
    </div>
    <div class="card">
      <a class="btn" href="/admin/hitl">Review HITL</a>
      <a class="btn danger" href="/admin/tickets">Review Tickets</a>
      <a class="btn" href="/admin/tools">Manage Tools</a>
      <a class="btn" href="/admin/rag">Manage RAG Docs</a>
    </div>
    """
    return page(body)


# ---------------------------------------------------------------------------
# Admin: HITL
# ---------------------------------------------------------------------------

@app.route("/admin/hitl", methods=["GET", "POST"])
def admin_hitl():
    if request.method == "POST":
        task_id = request.form.get("task_id")
        decision = request.form.get("decision", "approved")
        try:
            resolved = store.resolve_hitl_task(task_id, decision, decided_by="platform_admin")
            # Resume the underlying graph
            run_id = resolved["run_id"]
            # Discover which graph from checkpoints / run table is overkill;
            # try each module's resume.
            for name, entry in GRAPHS.items():
                try:
                    result = entry["module"].resume(run_id, hitl_decision=decision)
                    msg = f"Resumed {name}: status={result.get('status')}"
                    break
                except Exception:
                    continue
            else:
                msg = f"HITL resolved ({decision}) but graph module not auto-resumed — call resume manually."
        except Exception as e:
            msg = f"Error: {e}"
        body = f'<div class="card">{msg}</div><p><a href="/admin/hitl">Back</a></p>'
        return page(body)

    tasks = store.list_hitl_tasks("pending")
    rows = ""
    for t in tasks:
        rows += f"""
        <tr>
          <td>{t['task_id'][:8]}…</td>
          <td>{t['run_id'][:8]}…</td>
          <td>{t['node_id']}</td>
          <td>{t['reason']}</td>
          <td><span class="badge pending">{t['status']}</span></td>
          <td>
            <form method="post" style="display:inline">
              <input type="hidden" name="task_id" value="{t['task_id']}"/>
              <button class="btn ok" name="decision" value="approved">Approve</button>
              <button class="btn danger" name="decision" value="rejected">Reject</button>
            </form>
          </td>
        </tr>
        """
    body = f"""
    <h2>HITL Tasks</h2>
    <div class="card">
      <table>
        <tr><th>Task</th><th>Run</th><th>Node</th><th>Reason</th><th>Status</th><th>Action</th></tr>
        {rows or '<tr><td colspan="6">No pending HITL tasks</td></tr>'}
      </table>
    </div>
    """
    return page(body)


# ---------------------------------------------------------------------------
# Admin: Tickets
# ---------------------------------------------------------------------------

@app.route("/admin/tickets", methods=["GET", "POST"])
def admin_tickets():
    if request.method == "POST":
        ticket_id = request.form.get("ticket_id")
        try:
            resolved = store.resolve_ticket(ticket_id, resolution="retry", resolved_by="platform_admin")
            run_id = resolved["run_id"]
            # Clear force_fail so retry succeeds
            state = resolved["state"]
            state["force_fail"] = False
            store.save_checkpoint(run_id, resolved["node_id"], state)
            for name, entry in GRAPHS.items():
                try:
                    result = entry["module"].resume(run_id)
                    msg = f"Ticket resolved; resumed {name}: status={result.get('status')}"
                    break
                except Exception:
                    continue
            else:
                msg = "Ticket resolved; resume graph manually if needed."
        except Exception as e:
            msg = f"Error: {e}"
        body = f'<div class="card">{msg}</div><p><a href="/admin/tickets">Back</a></p>'
        return page(body)

    tickets = store.list_tickets(None)
    rows = ""
    for t in tickets:
        rows += f"""
        <tr>
          <td>{t['ticket_id'][:8]}…</td>
          <td>{t['run_id'][:8]}…</td>
          <td>{t['node_id']}</td>
          <td>{t['error_type']}: {t['error_message'][:80]}</td>
          <td><span class="badge {t['status']}">{t['status']}</span></td>
          <td>
            {"<form method='post' style='display:inline'><input type='hidden' name='ticket_id' value='" + t['ticket_id'] + "'/><button class='btn ok'>Retry / Resolve</button></form>" if t['status'] != 'resolved' else '—'}
          </td>
        </tr>
        """
    body = f"""
    <h2>Failure Tickets</h2>
    <div class="card">
      <table>
        <tr><th>Ticket</th><th>Run</th><th>Node</th><th>Error</th><th>Status</th><th>Action</th></tr>
        {rows or '<tr><td colspan="6">No tickets</td></tr>'}
      </table>
    </div>
    """
    return page(body)


# ---------------------------------------------------------------------------
# Admin: Tools (runtime registry)
# ---------------------------------------------------------------------------

@app.route("/admin/tools", methods=["GET", "POST"])
def admin_tools():
    # Prefer live MCP registry if present
    try:
        from mcp_server.tool_registry import (
            list_tools_for_agent,
            set_tool_enabled,
            init_registry_table,
            _ALL_TOOL_NAMES,
        )
        init_registry_table()
        registry_available = True
    except Exception:
        registry_available = False
        _ALL_TOOL_NAMES = [
            "get_medicines", "get_medicine", "create_order", "get_batches",
            "change_batch_status", "add_quality_test", "get_quality_tests",
            "create_recall", "get_recalls", "employee",
        ]

    agent_id = request.args.get("agent") or request.form.get("agent") or "batch_release"
    msg = ""

    if request.method == "POST" and registry_available:
        tool = request.form.get("tool")
        enabled = request.form.get("enabled") == "1"
        try:
            set_tool_enabled(agent_id, tool, enabled, updated_by=0)
            msg = f"Tool '{tool}' {'enabled' if enabled else 'disabled'} for agent '{agent_id}'"
        except Exception as e:
            msg = f"Error: {e}"

    # Build table
    if registry_available:
        try:
            tools = list_tools_for_agent(agent_id)
        except Exception:
            tools = [{"ToolName": t, "Enabled": 1} for t in _ALL_TOOL_NAMES]
    else:
        tools = [{"ToolName": t, "Enabled": 1} for t in _ALL_TOOL_NAMES]

    rows = ""
    for t in tools:
        name = t.get("ToolName") or t.get("tool_name") or t
        en = t.get("Enabled", t.get("enabled", 1))
        rows += f"""
        <tr>
          <td>{name}</td>
          <td>{'✅ enabled' if en else '❌ disabled'}</td>
          <td>
            <form method="post" style="display:inline">
              <input type="hidden" name="agent" value="{agent_id}"/>
              <input type="hidden" name="tool" value="{name}"/>
              <input type="hidden" name="enabled" value="{'0' if en else '1'}"/>
              <button class="btn">{'Disable' if en else 'Enable'}</button>
            </form>
          </td>
        </tr>
        """

    agent_opts = "".join(
        f'<option value="{a}" {"selected" if a == agent_id else ""}>{a}</option>'
        for a in list(GRAPHS.keys()) + ["memory_rag", "planning"]
    )
    body = f"""
    <h2>Tool Registry (runtime)</h2>
    <p class="card">{'Live MCP registry' if registry_available else 'Registry module not loaded — showing static list. Wire mcp_server.tool_registry for live toggles.'}</p>
    {f'<div class="card">{msg}</div>' if msg else ''}
    <form method="get" class="card">
      <label>Agent</label>
      <select name="agent" onchange="this.form.submit()">{agent_opts}</select>
    </form>
    <div class="card">
      <table>
        <tr><th>Tool</th><th>Status</th><th>Action</th></tr>
        {rows}
      </table>
    </div>
    """
    return page(body)


# ---------------------------------------------------------------------------
# Admin: RAG documents
# ---------------------------------------------------------------------------

_RAG_DOCS: list = []  # in-memory fallback; prefer rag/ store when present


@app.route("/admin/rag", methods=["GET", "POST"])
def admin_rag():
    global _RAG_DOCS
    msg = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            if title and content:
                _RAG_DOCS.append({"title": title, "content": content})
                # Best-effort push into rag subsystem if available
                try:
                    from rag.document_loader import ingest_text
                    ingest_text(title, content)
                except Exception:
                    pass
                msg = f"Added document '{title}'"
        elif action == "remove":
            idx = int(request.form.get("idx", -1))
            if 0 <= idx < len(_RAG_DOCS):
                removed = _RAG_DOCS.pop(idx)
                msg = f"Removed '{removed['title']}'"

    rows = ""
    for i, d in enumerate(_RAG_DOCS):
        rows += f"""
        <tr>
          <td>{d['title']}</td>
          <td>{d['content'][:80]}…</td>
          <td>
            <form method="post">
              <input type="hidden" name="action" value="remove"/>
              <input type="hidden" name="idx" value="{i}"/>
              <button class="btn danger">Remove</button>
            </form>
          </td>
        </tr>
        """
    body = f"""
    <h2>RAG Document Manager</h2>
    {f'<div class="card">{msg}</div>' if msg else ''}
    <form method="post" class="card">
      <input type="hidden" name="action" value="add"/>
      <label>Title</label>
      <input name="title" placeholder="Batch Approval Policy addendum"/>
      <label style="margin-top:8px;display:block">Content</label>
      <textarea name="content" rows="4"></textarea>
      <p style="margin-top:12px"><button class="btn" type="submit">Add Document</button></p>
    </form>
    <div class="card">
      <table>
        <tr><th>Title</th><th>Preview</th><th></th></tr>
        {rows or '<tr><td colspan="3">No documents yet</td></tr>'}
      </table>
    </div>
    """
    return page(body)


# ---------------------------------------------------------------------------
# JSON API helpers (for demos / automation)
# ---------------------------------------------------------------------------

@app.route("/api/hitl")
def api_hitl():
    return jsonify(store.list_hitl_tasks("pending"))


@app.route("/api/tickets")
def api_tickets():
    return jsonify(store.list_tickets(None))


@app.route("/api/graphs")
def api_graphs():
    return jsonify(list_graphs())


if __name__ == "__main__":
    store.init_tables()
    port = int(os.getenv("PLATFORM_PORT", "5000"))
    print(f"Vellora platform on http://127.0.0.1:{port}")
    print(f"  Chat:   http://127.0.0.1:{port}/chat")
    print(f"  Admin:  http://127.0.0.1:{port}/admin")
    app.run(host="0.0.0.0", port=port, debug=os.getenv("PLATFORM_DEBUG", "false") == "true")
