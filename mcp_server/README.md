# 🧪 Vellora Therapeutics - Safe MCP Data Protocol Server

## 🏢 Context & Business Domain
Vellora Therapeutics is a pharmaceutical manufacturing enterprise where safety, compliance, and auditing are strictly mandated. To allow LLM-assisted workflows without granting unmonitored raw access to the SQLite database, this server provides a secure, protocol-compliant Model Context Protocol (MCP) interface.

---

## 🏗️ Architecture & Modular Structure
The server follows a modular architecture separating business logic, validation, security, and protocol primitives:

```text
mcp_server/
├── server.py         # Entry point & FastMCP server setup
├── tools.py          # Business logic handlers for DB reads/writes
├── schemas.py        # Strict JSON Schemas (additionalProperties: False)
├── validation.py     # Independent server-side JSON schema validator
├── authorization.py  # DB-level employee status & Role-Based Access Control (RBAC)
├── elicitation.py    # Mid-call Human-in-the-Loop confirmation
└── notifications.py  # Dynamic capabilities list notification handler

 The 8 Core Protocol Behaviors
1.​Capability Negotiation (initialize): Declares server support for tools, resources, and prompts during the initial JSON-RPC handshake.

2.​Defensive Tool Design & Authorization: Enforces strict JSON schemas (additionalProperties: False) and verifies employee database status (Active) and role (QA Manager) prior to tool execution.

3.​Dynamic Capability Updates (notifications/tools/list_changed): Emits notifications to inform the client whenever tool availability or user permissions change mid-session.

4.​Mid-Call Elicitation (elicitation/create): High-risk actions like initiate_product_recall halt mid-execution to request explicit human confirmation before making permanent database state changes.

5.​Read-Only Resources (policy://quality-approval): Exposes immutable compliance policies as resources for LLM context instead of executable tools.

6.​Canned Prompts (recall_investigation_prompt): Provides pre-defined, parameterized prompt templates to standardize batch audit requests.

7.​Progress Tracking (run_batch_safety_audit): Reports granular progress during long-running tasks using ctx.report_progress().

8.​Embedded Database Design (SQLite): Utilizes vellora_therapeutics.db for zero-dependency local stdio execution and seamless testing.

##  Transport Architecture & Justification
* **Current Implementation:** `stdio` (Standard I/O) transport used during development and local evaluation for fast, zero-dependency testing.
* **Production Deployment Plan:** For multi-facility pharmaceutical operations (Vellora Therapeutics), the server is architected to transition to **Streamable HTTP (SSE)** with TLS encryption and JWT authentication to support remote multi-site access across manufacturing facilities.

##  Client Fallback & Sampling Behavior
* **Sampling (`sampling/createMessage`):** Utilized in `analyze_batch_discrepancy_with_sampling` to delegate complex reasoning to the host model safely.
* **Client Capability Fallback:** If a client connects without `elicitation` capabilities, high-risk tools like `initiate_product_recall` immediately degrade to read-only status and block state mutation to prevent unmonitored changes.
*