# Vellora-MCP-Server
MCP Server for Vellora Therapeutics A
# Vellora Therapeutics — MCP Server & Client

An agentic Model Context Protocol (MCP) server and client for pharmaceutical
manufacturing operations — production orders, batch tracking, quality
testing, and recalls — built with role-based authorization and policy
resources as first-class citizens.

---

## Team Problem Statement

In a pharmaceutical manufacturing environment, operations — production
orders, batch tracking, quality testing, recalls — are scattered across
separate systems, spreadsheets, and manual sign-offs. That fragmentation
creates two real risks: people can take actions outside their authority
(e.g. a production worker approving a batch that only a QA Manager should
sign off on), and there's no single, reliable way for an AI agent to safely
participate in that workflow without either being locked out entirely or
given dangerously broad access.

**Gap.** Existing approaches force a tradeoff: give an agent broad,
unrestricted database access (fast, but dangerous — anyone or anything can
approve, distribute, or recall product), or keep automation out entirely and
everything manual (safe, but slow and error-prone). Neither preserves the
role-based checks a real pharmaceutical operation requires.

**Solution.** Vellora exposes these operations through one standardized
interface — MCP — where every action is authorized by role, validated
before it touches the database, and grounded in the company's actual
governing policies. The result is a single, auditable interface that both
human employees and AI agents can use to safely operate the same real-world
workflow.

---

## What's in this repo

| Path | What it is |
|---|---|
| `vellora/` | The MCP server package (tools, resources, auth, validation, DB access) |
| `db/` | Schema + seed SQL, and the build script that produces `vellora.db` |
| `docs/policies/` | The 4 governing SOPs, served to clients as MCP resources |
| `client.py` | Interactive MCP client (CLI) that drives the server |
| `requirements.txt` | Python dependencies |

## Architecture

```
MCP Client (client.py)              MCP Server (vellora.server)              Data Layer
─────────────────────              ──────────────────────────              ──────────
Numbered CLI menu                   10 @mcp.tool() functions                SQLite — vellora.db
Employee login                      4 policy:// resources                  7 tables, FK-linked
Asyncio stdio session      <──>     Authorization + validation layer  <──>
Handles elicitation prompts         Notification messages                  docs/policies/*.md
Reads policy resources              FastMCP over stdio transport           4 governing SOPs
```

The client spawns the server as a subprocess and speaks MCP over stdio — no
network port, no separate deployment. The server never trusts the caller:
every tool call re-checks the employee's identity, status, and role against
the database before touching a row.

## Data model

Seven relational tables: `Employee`, `Medicine`, `Supplier`,
`Production_Order`, `Manufacturing_Batch`, `Quality_Test`, `Product_Recall` —
plus `Company_Policy`, which is exposed as read-only MCP resources rather
than a queryable tool. Seed data: 10 employees, 8 medicines, 5 suppliers, 15
production orders, 20 batches, 40 quality tests, 3 recalls.

## Tools (10)

| Domain | Tools |
|---|---|
| Catalog | `get_medicines`, `get_medicine` |
| Production | `create_order`, `get_batches`, `change_batch_status` |
| Quality | `add_quality_test`, `get_quality_tests` |
| Recalls & People | `create_recall`, `get_recalls`, `employee` |

## Authorization

| Tool | Allowed roles |
|---|---|
| `create_order` | Production Staff, Operations Manager |
| `change_batch_status` | Production Staff, QA Staff, QA Manager, Operations Manager |
| `add_quality_test` | QA Staff, QA Manager |
| `create_recall` | QA Manager, Operations Manager |
| all `get_*` tools, `employee` | any **Active** employee |

Inactive employees (e.g. EmployeeID 9, Laila Tarek) are blocked from every
tool, read or write.

## Policy resources (4)

Served via `policy://` URIs, readable the same way a tool is called:

- `policy://batch_approval` — Batch Approval Policy
- `policy://manufacturing_sop` — Manufacturing SOP
- `policy://product_recall` — Product Recall Procedure
- `policy://storage_guidelines` — Drug Storage Guidelines

## Request lifecycle

Every write tool call passes through, in order: **elicitation** (prompt for
missing arguments) → **authorization** (is this employee active and
role-permitted) → **validation** (do the referenced IDs exist, is the value
a valid choice) → **database write** → **notification** (a plain-English
confirmation returned alongside the raw result).

## Setup

```bash
pip install -r requirements.txt
python3 db/build_db.py        # (re)builds db/vellora.db from schema + seed SQL
python3 client.py             # launches the interactive client
```

The client spawns the server itself over stdio — you don't need to run it
separately.

### Try it

- Employee 2 (Youssef Hassan, Production Staff) can create orders and update
  batch status, but not record quality tests or create recalls.
- Employees 4/5/6 (QA Staff) can record quality tests.
- Employee 7 (Dina Farouk, QA Manager) can do everything QA-related plus
  create recalls.
- Employee 9 (Laila Tarek) is Inactive — any action will be rejected.

## Tech stack

- **Server:** Python · FastMCP (`mcp==1.9.4`) · stdio transport
- **Client:** Python · asyncio · `ClientSession` + `stdio_client`
- **Storage:** SQLite (`db/vellora.db`), built from schema + seed SQL
- **Policies:** Markdown files under `docs/policies/`, served as resources


## Final Project Platform

The final system adds three durable state graphs: **Batch Release**, **Recall Coordination**, and **Supplier CAPA**. Each graph persists checkpoints to SQLite and exposes a distinct HITL or failure-recovery path.

### Run

```bash
python -m db.init_db
python platform/app.py
```

Open `http://127.0.0.1:5000/chat` for the user surface and `/admin` for the admin surface.

For a one-command startup:

```bash
chmod +x startup.sh
./startup.sh
```

### Final Project requirements mapped to code

- `state_graph/graphs.py` — three state graphs and technique pairings.
- `state_graph/persistence.py` — durable checkpoints, HITL tasks, and failure tickets.
- `state_graph/nodes/hitl_node.py` — HITL operations.
- `state_graph/nodes/ticket_node.py` — failure-ticket operations.
- `platform/app.py` — user chat/agent switching and admin surfaces.
- `mcp_server/tool_registry.py` — runtime tool enable/disable backed by the shared database.
- `rag/` — existing RAG subsystem.
- `demos/` — HITL, ticket recovery, and crash/restart demonstrations.
- `FINAL_PROJECT_SETUP_GUIDE.md` — detailed setup and demo instructions.

### Demos

```bash
python demos/demo_hitl_pause.py --auto-approve
python demos/demo_failure_ticket.py
python demos/demo_crash_resume.py
python demos/demo_crash_resume.py --resume
```

### Security

Never commit `.env`, API keys, or database credentials. Required environment variables should be loaded with `os.getenv(...)`.
