"""Vellora Final Project platform: user chat + admin operations."""
import json, os, sys
from pathlib import Path
from flask import Flask, jsonify, request, render_template_string
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from db.init_db import init_db, DB_PATH
from state_graph.persistence import resolve_hitl, resolve_ticket
from mcp_server.tool_registry import list_agents_and_tools, available_tool_names, set_tool_enabled

init_db()
app=Flask(__name__)

HTML="""<!doctype html><html><head><meta charset=utf-8><title>Vellora</title>
<style>body{font-family:Arial;margin:30px;max-width:1100px}nav a{margin-right:20px}button{margin:3px;padding:7px}.card{border:1px solid #ddd;padding:15px;margin:10px 0;border-radius:8px}pre{background:#f5f5f5;padding:10px}</style></head>
<body><nav><a href="/">Home</a><a href="/chat">User Chat</a><a href="/admin">Admin</a><a href="/admin/hitl">HITL</a><a href="/admin/tickets">Tickets</a><a href="/admin/rag">RAG</a></nav><hr>{{body|safe}}</body></html>"""

@app.get("/")
def home(): return render_template_string(HTML,body="<h1>Vellora Therapeutics</h1><p>Final Project platform is running.</p><p>Use User Chat for agent switching or Admin for operational controls.</p>")

@app.get("/chat")
def chat():
    body="""<h1>User Chat</h1><label>Agent <select id=a><option>memory_rag</option><option>batch_release</option><option>recall_coordination</option><option>supplier_capa</option></select></label>
    <div id=out class=card>Choose an agent and send a request.</div><input id=q style="width:70%" placeholder="Message"><button onclick=send()>Send</button>
    <script>async function send(){let q=document.getElementById('q').value,a=document.getElementById('a').value;let r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:a,message:q})});document.getElementById('out').innerText=JSON.stringify(await r.json(),null,2)}</script>"""
    return render_template_string(HTML,body=body)

@app.post("/api/chat")
def api_chat():
    d=request.json or {}; agent=d.get("agent","memory_rag"); msg=d.get("message","")
    # Route to a real state graph for graph agents; memory/RAG is a safe informational response.
    if agent=="batch_release":
        from state_graph.graphs import BatchReleaseGraph
        r=BatchReleaseGraph({"current_state":"start","completed_steps":[],"request":msg}).run_until_hitl()
        return jsonify({"agent":agent,"status":"waiting_hitl","task_id":r["task_id"],"message":"Approval task created in Admin → HITL."})
    if agent=="recall_coordination":
        from state_graph.graphs import RecallCoordinationGraph
        r=RecallCoordinationGraph({"current_state":"start","completed_steps":[],"request":msg}).run()
        return jsonify({"agent":agent,"result":r})
    if agent=="supplier_capa":
        from state_graph.graphs import SupplierCAPAGraph
        g=SupplierCAPAGraph({"current_state":"start","completed_steps":[],"request":msg}); rid,cp=g.run_until_checkpoint()
        return jsonify({"agent":agent,"run_id":rid,"checkpoint":cp})
    return jsonify({"agent":agent,"answer":"Memory/RAG agent selected. Use the existing RAG modules to answer policy questions; this platform route confirms agent switching works.","message":msg})

@app.get("/admin")
def admin():
    tools=list_agents_and_tools()
    body="<h1>Admin Dashboard</h1><h2>MCP Tools</h2>"
    for agent,ts in tools.items():
        body+=f"<div class=card><b>{agent}</b><br>"
        for t in ts:
            en=t["enabled"]; action="disable" if en else "enable"
            body+=f"{t['tool_name']} — {'enabled' if en else 'disabled'} <button onclick=\"toggle('{agent}','{t['tool_name']}',{str(not en).lower()})\">{action}</button><br>"
        body+="</div>"
    body+="<p><a href='/admin/hitl'>HITL tasks</a> · <a href='/admin/tickets'>Failure tickets</a> · <a href='/admin/rag'>RAG documents</a></p>"
    body+="<script>async function toggle(a,t,e){await fetch('/api/admin/tools',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_id:a,tool_name:t,enabled:e})});location.reload()}</script>"
    return render_template_string(HTML,body=body)

@app.post("/api/admin/tools")
def admin_tools_api():
    d=request.json or {}; set_tool_enabled(d["agent_id"],d["tool_name"],bool(d["enabled"]),1)
    return jsonify({"ok":True,"tools":list_agents_and_tools()})

@app.get("/admin/hitl")
def hitl():
    import sqlite3
    with sqlite3.connect(DB_PATH) as c:
        rows=c.execute("SELECT task_id,reason,status,created_at FROM hitl_tasks ORDER BY created_at DESC").fetchall()
    body="<h1>HITL Tasks</h1>"
    for task,reason,status,created in rows:
        body+=f"<div class=card><b>{task}</b> — {status}<br>{reason}<br>{created}<br>"+("" if status=="resolved" else f"<button onclick=\"resolve('{task}')\">Approve</button>")+"</div>"
    body+="<script>async function resolve(id){await fetch('/api/admin/hitl/'+id+'/resolve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision:'approved'})});location.reload()}</script>"
    return render_template_string(HTML,body=body)

@app.post("/api/admin/hitl/<task_id>/resolve")
def hitl_api(task_id):
    d=request.json or {}; return jsonify({"ok":True,"run_id":resolve_hitl(task_id,d.get("decision","approved"),"admin")})

@app.get("/admin/tickets")
def tickets():
    import sqlite3
    with sqlite3.connect(DB_PATH) as c:
        rows=c.execute("SELECT ticket_id,error,status,created_at FROM tickets ORDER BY created_at DESC").fetchall()
    body="<h1>Failure Tickets</h1>"
    for tid,error,status,created in rows:
        body+=f"<div class=card><b>{tid}</b> — {status}<br>{error}<br>{created}<br>"+("" if status=="resolved" else f"<button onclick=\"retry('{tid}')\">Resolve & Retry</button>")+"</div>"
    body+="<script>async function retry(id){await fetch('/api/admin/tickets/'+id+'/resolve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({resolution:'retry'})});location.reload()}</script>"
    return render_template_string(HTML,body=body)

@app.post("/api/admin/tickets/<ticket_id>/resolve")
def ticket_api(ticket_id):
    d=request.json or {}; return jsonify({"ok":True,"run_id":resolve_ticket(ticket_id,d.get("resolution","retry"),"admin")})

@app.get("/admin/rag")
def rag_admin():
    import sqlite3
    with sqlite3.connect(DB_PATH) as c: rows=c.execute("SELECT document_id,title,active FROM rag_documents ORDER BY created_at DESC").fetchall()
    body="<h1>RAG Documents</h1><form method=post action=/api/admin/rag><input name=title placeholder=Title required><textarea name=content placeholder=Content required></textarea><button>Add</button></form>"
    for did,title,active in rows: body+=f"<div class=card>{title} ({did}) — {'active' if active else 'removed'} <button onclick=\"removeDoc('{did}')\">Remove</button></div>"
    body+="<script>async function removeDoc(id){await fetch('/api/admin/rag/'+id,{method:'DELETE'});location.reload()}</script>"
    return render_template_string(HTML,body=body)

@app.post("/api/admin/rag")
def rag_add():
    import sqlite3, uuid
    d=request.form if request.form else (request.json or {})
    did="doc_"+uuid.uuid4().hex[:10]
    from datetime import datetime, timezone
    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT INTO rag_documents VALUES (?,?,?,?,?)",(did,d["title"],d["content"],datetime.now(timezone.utc).isoformat(),1))
    return jsonify({"ok":True,"document_id":did})

@app.delete("/api/admin/rag/<did>")
def rag_remove(did):
    import sqlite3
    with sqlite3.connect(DB_PATH) as c: c.execute("UPDATE rag_documents SET active=0 WHERE document_id=?",(did,))
    return jsonify({"ok":True})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PLATFORM_PORT","5000")),debug=False)
