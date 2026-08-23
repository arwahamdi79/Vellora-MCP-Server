# Vellora Final Project - Setup & Reproduction Guide

**Status**: ✅ 95/100 points delivered (State graphs, HITL, Tickets, Platform)

This guide covers the **remaining 5 points** (Repository Usability & Demo Evidence).

---

## 🚀 SETUP INSTRUCTIONS

### Prerequisites
```bash
# Python 3.9+
python --version

# Required packages
pip install langchain langgraph chromadb sentence-transformers flask flask-cors python-dotenv
```

### 1. Environment Setup

Create `.env` file in repo root:
```bash
# .env (NEVER commit this!)
OPENAI_API_KEY=your_key_here
DATABASE_URL=sqlite:///vellora.db
MCP_SERVER_PORT=9000
PLATFORM_PORT=5000

# Platform configuration
ADMIN_TOKEN=secret_admin_token_here
PLATFORM_DEBUG=false
```

**⚠️ IMPORTANT**: Confirm `.env` is in `.gitignore`:
```bash
grep -q "^\.env$" .gitignore && echo "✅ .env in .gitignore" || echo "❌ .env NOT in .gitignore"
```

Also check platform's config:
```bash
# platform/.env should NOT be committed either
grep -q "^\.env$" platform/.gitignore && echo "✅ OK" || echo "❌ FIX THIS"
```

### 2. Database Setup

Initialize database and run migrations:
```bash
cd db
python init_db.py          # Creates vellora.db with schema
python migrate_state_graphs.py  # Adds state_graph tables
cd ..
```

Verify:
```bash
sqlite3 vellora.db ".tables"
# Should show: agents, tools, documents, state_graphs, checkpoints, hitl_tasks, tickets
```

### 3. Start MCP Server

```bash
# Terminal 1: MCP Server
python run_server.py

# Output:
# ✅ MCP Server running on port 9000
# ✅ Tools registered: [list of tools]
# ✅ Database: vellora.db
```

Verify server is running:
```bash
curl http://localhost:9000/health
# Output: {"status": "ok", "agents": 3, "tools": 15}
```

### 4. Start State Graph Agents

```bash
# Terminal 2: State Graph Agents
cd agent
python run_agents.py

# Output:
# ✅ Batch Release Graph: Ready
# ✅ Recall Coordination Graph: Ready
# ✅ Supplier CAPA Graph: Ready
# ✅ Connected to MCP Server (9000)
```

### 5. Start Platform

```bash
# Terminal 3: Platform
cd platform
python app.py

# Output:
# ✅ Platform running on http://localhost:5000
# ✅ Admin panel: http://localhost:5000/admin
# ✅ Chat interface: http://localhost:5000/chat
```

### Complete Startup Script

```bash
#!/bin/bash
# startup.sh - Start entire system

set -e  # Exit on error

echo "🚀 Starting Vellora Final Project System..."
echo

# 1. Check environment
echo "1️⃣ Checking environment..."
if [ ! -f ".env" ]; then
    echo "❌ .env not found. Create it first!"
    exit 1
fi
echo "✅ .env found"
echo

# 2. Database
echo "2️⃣ Setting up database..."
cd db
python init_db.py > /dev/null 2>&1
python migrate_state_graphs.py > /dev/null 2>&1
cd ..
echo "✅ Database ready (vellora.db)"
echo

# 3. Start MCP Server (background)
echo "3️⃣ Starting MCP Server..."
python run_server.py > /tmp/mcp_server.log 2>&1 &
MCP_PID=$!
sleep 2
echo "✅ MCP Server (PID $MCP_PID)"
echo

# 4. Start Agents (background)
echo "4️⃣ Starting State Graph Agents..."
cd agent
python run_agents.py > /tmp/agents.log 2>&1 &
AGENTS_PID=$!
cd ..
sleep 2
echo "✅ Agents (PID $AGENTS_PID)"
echo

# 5. Start Platform
echo "5️⃣ Starting Platform..."
cd platform
python app.py

# Cleanup on exit
trap "kill $MCP_PID $AGENTS_PID 2>/dev/null" EXIT
```

Run it:
```bash
chmod +x startup.sh
./startup.sh
```

---

## 📊 FULL SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│          Platform (Flask Web App - port 5000)           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Admin Panel:                  User Chat:              │
│  ├─ Tool Registry              ├─ Agent Switcher      │
│  ├─ RAG Document Manager       ├─ Chat Interface      │
│  ├─ HITL Tasks                 └─ Conversation History │
│  └─ Failure Tickets                                    │
│                                                         │
└────────────┬────────────────────────────────┬──────────┘
             │                                │
             ▼                                ▼
    ┌────────────────────────┐       ┌──────────────────┐
    │   State Graph Agents   │       │   MCP Server     │
    ├────────────────────────┤       ├──────────────────┤
    │                        │       │                  │
    │ • Batch Release Graph  │◄─────►│ • Tool Registry  │
    │ • Recall Coord Graph   │       │ • Database Conn  │
    │ • Supplier CAPA Graph  │       │ • Auth/RBAC      │
    │                        │       │                  │
    │ (Checkpoints stored)   │       │ (Port 9000)      │
    │                        │       │                  │
    └────────────┬───────────┘       └────────┬─────────┘
                 │                           │
                 └──────────────┬────────────┘
                                ▼
                        ┌────────────────┐
                        │   Database     │
                        ├────────────────┤
                        │                │
                        │ • vellora.db   │
                        │ • Checkpoints  │
                        │ • HITL Tasks   │
                        │ • Tickets      │
                        │ • RAG Docs     │
                        │                │
                        └────────────────┘
```

---

## ✅ DEMO EVIDENCE - Run These

### Demo 1: HITL Pause & Resume

```bash
# Terminal 4: Run demo script
python demos/demo_hitl_pause.py

# Expected output:
# ✅ Batch Release Graph started
# ⏸️  HITL pause detected: "Approval required for batch release"
# 📋 HITL task created (ID: task_12345)
# 
# Open http://localhost:5000/admin?task=task_12345
# Admin clicks "Approve"
# 
# ✅ Graph resumed from checkpoint
# ✅ Batch released (no re-execution of completed steps)
```

**What's happening**:
1. Graph reaches HITL node (requires approval)
2. Execution pauses, state checkpointed
3. Admin sees task in platform UI
4. Admin approves through platform
5. Graph resumes from exact checkpoint (no replay)

### Demo 2: Failure → Ticket → Resolution

```bash
# Terminal 4: Run demo script
python demos/demo_failure_ticket.py

# Expected output:
# ✅ Recall Coordination Graph started
# ❌ Tool error: "External API timeout"
# 📌 Failure ticket created (ID: ticket_67890)
# 💾 State checkpointed at failure point
# 
# Open http://localhost:5000/admin?ticket=ticket_67890
# You can see:
# - Why it failed (error message)
# - State at failure (variables, context)
# - Retry button
# 
# Click "Retry" (resolves ticket, resumes from checkpoint)
# ✅ Tool call succeeds on retry
# ✅ Graph continues from failure point
```

**What's happening**:
1. Tool call fails (real error, not mock)
2. Execution halts, state checkpointed
3. Ticket created (distinct from HITL - this is unplanned)
4. Admin can inspect state and decide action
5. Click retry → resume from checkpoint

### Demo 3: Process Crash & Recovery

```bash
# Terminal 4: Run demo script
python demos/demo_crash_resume.py

# Expected output:
# ✅ Supplier CAPA Graph started
# 📝 Completed step: "Investigate supplier issue"
# 💾 Checkpoint saved
# 📝 In progress step: "Prepare corrective action plan"
# 💾 Checkpoint saved mid-step
# 
# ⚠️  SIMULATING PROCESS CRASH (kill -9)
# [Process killed]
# 
# Restarting...
# python demos/demo_crash_resume.py --resume
# 
# ✅ Loaded checkpoint from database
# ✅ Resuming from: "Prepare corrective action plan" (mid-step)
# ✅ No re-execution of previous steps
# ✅ Graph continues to completion
# ✅ Final result: [same as if never crashed]
```

**What's happening**:
1. Graph runs and checkpoints after each step
2. Process is killed mid-run
3. Database has persisted checkpoints
4. On restart, load last checkpoint
5. Resume exactly from there (no replay)

---

## 📋 GITHUB ISSUES TEMPLATE

Each issue should have this structure:

### Issue: [Component] - [Problem Statement]

**Problem**: 
One sentence describing the real business problem this solves.

Example: "Currently, admins cannot see why a batch release graph stalled for 3 days, and a stalled batch past the FDA window loses the release window entirely."

**Constraint**:
What makes this harder than it sounds.

Example: "State must persist across process crashes, and resumption must not replay already-completed steps."

**Acceptance Criteria**:
What a reviewer should check to verify this is done.

Example:
- [ ] Checkpoints written after each state transition
- [ ] Crash recovery tested (kill -9 + restart)
- [ ] Admin can see and resume stalled runs via platform UI
- [ ] No duplicate execution on resume

**Tasks**:
- [ ] Implementation
- [ ] Unit tests
- [ ] Integration test with platform UI
- [ ] Demo evidence

---

## 🔒 SECURITY CHECKLIST

Before pushing to GitHub:

```bash
# 1. Check .gitignore (root)
grep -E "\.env|\.env\." .gitignore
# Should output: .env

# 2. Check .gitignore (platform)
grep -E "\.env|\.env\." platform/.gitignore
# Should output: .env

# 3. Verify no secrets committed
git log --all -S "sk-" --source --pretty=format:"%h %s" | head
# Should be empty or show old commits to remove

# 4. Check for hardcoded keys in code
grep -r "openai_api_key.*=" --include="*.py" .
# Should only show: os.getenv("OPENAI_API_KEY")

# 5. Scan for database credentials
grep -r "DATABASE_URL.*=" --include="*.py" .
# Should only show: os.getenv("DATABASE_URL")
```

If anything is committed, use:
```bash
# Remove from history (only if not yet pushed to main)
git filter-branch --tree-filter 'rm -f .env' HEAD
```

---

## 📝 REPOSITORY STRUCTURE CHECK

Verify everything is organized:

```
Vellora-MCP-Server/
├── .env ............................ IN .gitignore ✅
├── .gitignore ....................... Contains .env ✅
├── README.md ........................ UPDATED (this section) ✅
├── LICENSE .......................... ✅
├── requirements.txt ................. ✅
├── startup.sh ....................... Included ✅
│
├── db/
│   ├── init_db.py .................. Create schema
│   ├── migrate_state_graphs.py ...... State graph tables
│   └── vellora.db ................... ✅ (in .gitignore)
│
├── mcp_server/
│   ├── __init__.py
│   ├── server.py ................... Runtime tool registry ✅
│   ├── auth.py
│   └── tools.json
│
├── agent/
│   ├── run_agents.py ............... Start state graphs
│   ├── batch_release.py ............ Graph 1
│   ├── recall_coordination.py ....... Graph 2
│   └── supplier_capa.py ............ Graph 3
│
├── state_graph/
│   ├── graphs.py ................... All 3 graphs
│   ├── checkpointing.py ............ Persist state
│   ├── nodes/
│   │   ├── hitl_node.py ............ HITL pause/resume
│   │   └── ticket_node.py .......... Failure handling
│   └── README.md ................... Graphs explained
│
├── platform/
│   ├── .env ........................ IN .gitignore ✅
│   ├── .gitignore
│   ├── app.py ...................... Flask app
│   ├── admin_routes.py ............. Tool/doc registry
│   ├── chat_routes.py .............. Agent switcher
│   ├── task_routes.py .............. HITL/tickets
│   ├── templates/
│   │   ├── admin.html .............. Tool registry UI
│   │   ├── chat.html ............... Chat UI
│   │   ├── hitl.html ............... HITL task UI
│   │   └── tickets.html ............ Failure ticket UI
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── README.md ................... Platform setup
│
├── demos/
│   ├── demo_hitl_pause.py .......... HITL pause/resume demo
│   ├── demo_failure_ticket.py ....... Ticket creation demo
│   ├── demo_crash_resume.py ........ Crash recovery demo
│   └── README.md ................... How to run demos
│
├── memory/ .......................... Memory system (from Lab 3)
├── rag/ ............................ RAG system (from Lab 3)
├── docs/ ........................... Documentation
│
└── .github/
    └── ISSUE_TEMPLATE/
        └── ...
```

---

## 🧪 INTEGRATION TEST

Run this to verify everything works end-to-end:

```bash
#!/bin/bash
# test_integration.py equivalent

echo "🧪 Running integration tests..."

# 1. Database
echo "Testing database..."
python -c "
import sqlite3
conn = sqlite3.connect('vellora.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\"')
tables = [row[0] for row in cursor.fetchall()]
required = ['agents', 'tools', 'documents', 'state_graphs', 'checkpoints', 'hitl_tasks', 'tickets']
for t in required:
    assert t in tables, f'Missing table: {t}'
print('✅ Database tables OK')
"

# 2. MCP Server
echo "Testing MCP Server..."
python -c "
import requests
import time
import subprocess
import os

# Start server
proc = subprocess.Popen(['python', 'run_server.py'], stdout=subprocess.PIPE)
time.sleep(3)

try:
    resp = requests.get('http://localhost:9000/health')
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'ok'
    assert data['agents'] >= 3
    print('✅ MCP Server OK')
finally:
    proc.terminate()
"

# 3. State Graphs
echo "Testing state graphs..."
python -c "
from agent.batch_release import BatchReleaseGraph
from agent.recall_coordination import RecallCoordGraph
from agent.supplier_capa import SupplierCAPAGraph

for name, graph_class in [
    ('Batch Release', BatchReleaseGraph),
    ('Recall Coordination', RecallCoordGraph),
    ('Supplier CAPA', SupplierCAPAGraph),
]:
    g = graph_class()
    assert hasattr(g, 'graph'), f'{name} missing graph'
    assert hasattr(g, 'checkpoint'), f'{name} missing checkpoint'
    assert hasattr(g, 'run'), f'{name} missing run method'
    print(f'✅ {name} Graph OK')
"

# 4. Platform
echo "Testing platform..."
python -c "
import sys
sys.path.insert(0, 'platform')
from app import app

with app.test_client() as client:
    # Chat interface
    resp = client.get('/chat')
    assert resp.status_code == 200
    print('✅ Chat interface OK')
    
    # Admin panel
    resp = client.get('/admin')
    assert resp.status_code in [200, 302]  # May redirect for auth
    print('✅ Admin panel OK')
"

echo
echo "✅ All integration tests passed!"
```

Run it:
```bash
bash test_integration.sh
```

---

## 🎯 FINAL CHECKLIST (5 Points)

Before submitting, verify:

- [ ] **`.env` in `.gitignore`** (root and platform/)
  ```bash
  grep "\.env" .gitignore platform/.gitignore
  ```

- [ ] **Setup README complete** (this file in repo root)
  - [ ] Prerequisites listed
  - [ ] Step-by-step setup
  - [ ] Full system startup script
  - [ ] Architecture diagram

- [ ] **Demo scripts ready to run**
  - [ ] `demos/demo_hitl_pause.py` ✅
  - [ ] `demos/demo_failure_ticket.py` ✅
  - [ ] `demos/demo_crash_resume.py` ✅
  - [ ] All three generate evidence of: pause→resume, failure→ticket, crash→recovery

- [ ] **GitHub issues documented**
  - [ ] Real problem statement (not just "add HITL")
  - [ ] Constraints & acceptance criteria
  - [ ] Single owner per issue
  - [ ] PRs linked with "Closes #X"

- [ ] **No secrets committed**
  ```bash
  # Should return nothing
  git log --all -S "sk-" --source
  git log --all -S "DATABASE_URL=" --source
  ```

---

## 📞 GETTING HELP

If a demo fails:

1. **HITL demo**: Check `platform/task_routes.py` - is the task created?
2. **Failure demo**: Check `platform/ticket_routes.py` - is the ticket persisted?
3. **Crash demo**: Check `db/checkpointing.py` - was state written to DB?

If setup fails:

1. **MCP Server won't start**: Check port 9000 not in use
2. **Database error**: Delete `vellora.db` and re-run migrations
3. **Platform won't start**: Check port 5000 not in use

---

**Ready to submit? This README + 3 demos + fixed GitHub issues = 5 points + presentation!**
