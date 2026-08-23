# GitHub Issues - Final Project (For Repository)

Copy these to your GitHub repo Issues. Each should have a real owner, real PR linked with "Closes #X".

---

## Issue #1: State Graph Checkpointing - Batch Release Workflow

**Title**: State Graph Checkpointing - Batch Release Workflow

**Problem**: 
When a batch release process (checking quality, regulatory review, approval) runs for days and crashes mid-execution, we lose all state and must restart from scratch, re-checking already-reviewed batches and re-escalating already-approved items. This wastes 4-6 hours per failure and risks approving the same batch twice.

**Constraint**:
- Checkpoints must be written to durable storage (database) after each state transition, not just in memory
- Resumption must skip already-completed steps (no replay)
- Must survive actual process restarts (kill -9), not just pauses within the same process
- Must be inspectable (admins can see where graph paused)

**Acceptance Criteria**:
- [ ] After each state transition in `agent/batch_release.py`, `checkpointing.py` writes to `db/checkpoints` table
- [ ] Unit test kills process mid-run, restarts, verifies graph resumes from checkpoint
- [ ] Integration test shows HITL pause, admin reviews state in platform UI, approves, graph continues
- [ ] No re-execution of completed steps (verify with test log)
- [ ] `demos/demo_crash_resume.py` demonstrates full cycle

**Owner**: [Your Name]  
**Related**: state_graph/graphs.py, state_graph/checkpointing.py

---

## Issue #2: HITL Escalation - Approval Required for Batch Release

**Title**: HITL Escalation - Approval Required for Batch Release

**Problem**: 
The batch release graph currently decides on its own whether a batch meets regulatory requirements. A wrong decision (approving a batch that shouldn't be approved) exposes the company to regulatory fines and patient safety issues. Someone with authority must review and sign off.

**Constraint**:
- HITL pause must be explicit (a node type, not a buried retry loop)
- State must be fully persisted when paused (variables, collected data, reasoning)
- Admin must see the state in platform UI and make decision through UI (not console, not email, not Slack)
- Graph must resume only after admin action through platform, not auto-continue
- Must show which admin approved and when (audit trail)

**Acceptance Criteria**:
- [ ] `state_graph/nodes/hitl_node.py` implements HITL node type
- [ ] HITL pause condition documented (e.g., "Batch from new supplier" → requires approval)
- [ ] `platform/hitl.html` shows task with full graph state
- [ ] Admin can "Approve" or "Reject" through UI
- [ ] Graph persists decision and resumes (not auto-continues)
- [ ] `demos/demo_hitl_pause.py` shows full cycle: pause → admin action → resume
- [ ] Audit log shows: who approved, timestamp, decision

**Owner**: [Your Name]  
**Related**: state_graph/nodes/hitl_node.py, platform/task_routes.py

---

## Issue #3: Ticket System - Failure Detection & Recovery

**Title**: Ticket System - Failure Detection & Recovery

**Problem**: 
When a tool call fails (e.g., FDA database is down, API times out, response malformed), the graph currently crashes with no record of what failed or how to retry. Admins have no way to see what happened and no clean path to resume. Each failure requires re-running from scratch by hand.

**Constraint**:
- Tickets must be distinct from HITL: a ticket is an unplanned failure (tool error), not an expected pause (admin decision)
- State must be checkpointed at the moment of failure (so retry resumes from that point)
- Ticket must be inspectable by admins (see error, stack trace, current state)
- Ticket must be resolvable (admin clicks "Retry" → graph resumes from checkpoint)
- Must track: when failed, why, who fixed it, when resolved

**Acceptance Criteria**:
- [ ] Tool failures trigger `state_graph/nodes/ticket_node.py` (not halt-and-crash)
- [ ] `db/tickets` table stores: failure_id, error, state_at_failure, status, assigned_to, resolved_at
- [ ] `platform/tickets.html` shows open tickets with error details and state inspector
- [ ] Admin can click "Retry" → graph resumes from checkpoint (no replay)
- [ ] `demos/demo_failure_ticket.py` shows: tool fails → ticket created → admin retries → success
- [ ] Ticket status changes: open → investigating → resolved

**Owner**: [Your Name]  
**Related**: state_graph/nodes/ticket_node.py, platform/ticket_routes.py

---

## Issue #4: Admin Tool Registry - Runtime Tool Management

**Title**: Admin Tool Registry - Runtime Tool Management

**Problem**: 
Currently, to add or remove a tool from an agent (e.g., give batch release agent access to new FDA database), we must hand-edit configuration, restart the server, and redeploy. This takes 30 minutes and risks downtime. Admins have no UI to manage this.

**Constraint**:
- Tool add/remove must reach the live MCP server immediately (not just update a config file)
- Must be persisted (survives server restart)
- Must be audited (log who added/removed tools and when)
- Platform must reflect changes immediately (admin adds tool → agent can call it on next query)

**Acceptance Criteria**:
- [ ] `mcp_server/server.py` supports runtime tool registration (not just startup)
- [ ] `platform/admin.html` shows tool registry with Add/Remove buttons per agent
- [ ] Clicking "Add Tool" updates MCP server (verify with tool list refresh)
- [ ] Tool removal takes effect immediately (agent can't call removed tool)
- [ ] `db/tool_registry` audit log tracks: tool_name, action (add/remove), admin, timestamp
- [ ] Integration test: add tool through UI → agent can call it → remove tool → agent can't call it

**Owner**: [Your Name]  
**Related**: mcp_server/server.py, platform/admin_routes.py

---

## Issue #5: Admin RAG Document Manager - Dynamic Document Updates

**Title**: Admin RAG Document Manager - Dynamic Document Updates

**Problem**: 
When new FDA regulations are released, we upload them to the RAG system, but the batch release agent doesn't retrieve them on the next query because the vector store wasn't reindexed. Admins think they've updated the knowledge base, but the agent still uses old regulations.

**Constraint**:
- Document add/remove must update vector store immediately (not just store file)
- Must reindex and update embeddings
- Must be reflected in agent queries on the next call (no agent restart required)
- Must be audited (log who added/removed docs and when)

**Acceptance Criteria**:
- [ ] `platform/admin.html` has RAG document upload UI
- [ ] Uploading triggers: chunking → embedding → vector store update
- [ ] Integration test: upload doc → run batch release agent → verify doc is retrieved
- [ ] `db/knowledge_store.py` _reindex() is wired to `agent/search_adapter.py` (currently placeholder)
- [ ] Document removal updates vector store (removes embeddings)
- [ ] `db/document_audit` log tracks: doc_id, action, admin, timestamp

**Owner**: [Your Name]  
**Related**: db/knowledge_store.py, platform/admin_routes.py, agent/search_adapter.py

---

## Issue #6: Chat Interface - Multi-Agent Switching

**Title**: Chat Interface - Multi-Agent Switching

**Problem**: 
Users currently can only talk to one agent at a time (memory/RAG agent for questions). They need to switch between: memory/RAG agent (policy questions), batch release state graph (batch approval), recall coordination state graph (product safety), supplier CAPA state graph (supplier issues) — without reloading or losing conversation context.

**Constraint**:
- Agent switcher must be part of the UI (not a separate page reload)
- Switching must not lose previous conversation with the old agent (or must warn)
- User must see which agent they're talking to (clear label)
- Chat history must be per-agent (selecting agent A doesn't show agent B's old messages)

**Acceptance Criteria**:
- [ ] `platform/chat.html` has agent dropdown
- [ ] Selecting agent switches active agent (verify tool calls go to right agent)
- [ ] Conversation history changes per-agent (or user warned before switch)
- [ ] UI clearly shows: current agent, available agents, agent status
- [ ] Integration test: user talks to memory agent → switches to batch release → batch approval works
- [ ] All three state graph agents + memory/RAG agent are listed

**Owner**: [Your Name]  
**Related**: platform/chat_routes.py, platform/templates/chat.html

---

## Issue #7: [From MCP Server Lab] Fix Tool Authorization

**Title**: [Corrected from MCP Server Lab] Fix Tool Authorization - Runtime Scope Enforcement

**Problem**: 
[From MCP Server Lab grading] Tools don't enforce authorization scopes. Any agent can call any tool regardless of assigned role.

**Constraint**:
- Authorization must be checked at MCP server level (not just agent level)
- Scope must be enforced per-agent
- Scope changes must take effect immediately (admin changes scope → agent can/can't call tool)

**Acceptance Criteria**:
- [ ] `mcp_server/auth.py` verifies agent scope before tool call
- [ ] Tool call denied if agent doesn't have scope (returns error)
- [ ] Scope change through platform takes effect immediately
- [ ] Unit test: agent with no scope → tool call fails
- [ ] Unit test: add scope through UI → tool call succeeds

**Owner**: [Your Name]  
**Related**: mcp_server/auth.py, mcp_server/server.py

---

## Issue #8: [From Memory & RAG Lab] Fix RAG Retrieval Integration

**Title**: [Corrected from Memory & RAG Lab] Fix RAG Retrieval Integration - Search Adapter

**Problem**: 
[From Memory & RAG Lab grading] RAG system doesn't actually integrate with agent queries. `db/knowledge_store.py` has placeholder for `_reindex()` that's never wired to `agent/search_adapter.py`.

**Constraint**:
- `_reindex()` must be called when documents are added
- Search adapter must return relevant chunks to agent
- Changes must be reflected on next query (no agent restart)

**Acceptance Criteria**:
- [ ] `db/knowledge_store.py` _reindex() calls `agent/search_adapter.py` methods
- [ ] Agent can retrieve documents added through platform
- [ ] Integration test: add doc through admin UI → agent retrieves it → remove doc → agent can't retrieve it
- [ ] No errors in logs when indexing/reindexing

**Owner**: [Your Name]  
**Related**: db/knowledge_store.py, agent/search_adapter.py

---

## Issue #9: Security - Remove Hardcoded Secrets

**Title**: Security - Remove Hardcoded Secrets & Verify .gitignore

**Problem**: 
API keys and database credentials may be hardcoded or committed to repo, exposing credentials if repo is made public or compromised.

**Constraint**:
- All secrets must come from .env (never hardcoded)
- .env must be in .gitignore (root and platform/)
- No secrets in commit history

**Acceptance Criteria**:
- [ ] `.env` in `.gitignore` (root)
- [ ] `platform/.env` in `platform/.gitignore`
- [ ] All API keys use `os.getenv("KEY_NAME")`
- [ ] All database URLs use `os.getenv("DATABASE_URL")`
- [ ] Git scan shows no "sk-" or credential patterns: `git log --all -S "sk-" --source`
- [ ] README lists required env vars

**Owner**: [Your Name]  
**Related**: .gitignore, platform/.gitignore, all .py files

---

## Issue #10: Documentation - Setup & Reproduction Guide

**Title**: Documentation - Setup & Reproduction Guide

**Problem**: 
New developers and graders can't easily reproduce the entire system. Setup instructions are scattered or missing, making it hard to verify the project works end-to-end.

**Constraint**:
- Guide must cover: environment setup → database migrations → MCP server startup → agents → platform
- Must be step-by-step (copy-paste commands work)
- Must include a single `startup.sh` to start the entire system
- Must list demo evidence scripts

**Acceptance Criteria**:
- [ ] `README.md` (or linked file) lists all setup steps
- [ ] `startup.sh` starts all services with one command
- [ ] Prerequisites listed (Python version, packages)
- [ ] Each major component has its own section
- [ ] Architecture diagram included
- [ ] Demo scripts listed with expected output
- [ ] Security checklist (env vars, .gitignore verification)

**Owner**: [Your Name]  
**Related**: README.md, startup.sh

---

## Issue #11: Demo Evidence - HITL Pause & Resume

**Title**: Demo Evidence - HITL Pause & Resume Cycle

**Problem**: 
Graders need to verify HITL escalation works end-to-end: graph pauses for approval, admin sees task in platform, admin approves, graph resumes.

**Constraint**:
- Must be runnable with one command
- Must show real output (not mocked)
- Must demonstrate: state persistence, platform UI interaction, graph resumption

**Acceptance Criteria**:
- [ ] `demos/demo_hitl_pause.py` runs without modification
- [ ] Output shows: graph started → HITL pause detected → task ID → resume from checkpoint → completion
- [ ] Platform UI shows task (screenshot or live demo)
- [ ] No duplicate execution after resume

**Owner**: [Your Name]  
**Related**: demos/demo_hitl_pause.py

---

## Issue #12: Demo Evidence - Failure Ticket & Recovery

**Title**: Demo Evidence - Failure Ticket & Recovery Cycle

**Problem**: 
Graders need to verify ticket system works: tool fails → ticket created → persisted → admin retries → resumes from checkpoint.

**Constraint**:
- Must show real tool failure (not mocked)
- Must show ticket in platform UI
- Must show resumed execution from checkpoint

**Acceptance Criteria**:
- [ ] `demos/demo_failure_ticket.py` runs without modification
- [ ] Output shows: graph started → tool fails → ticket created → retry → success
- [ ] Platform shows ticket with error and state
- [ ] Checkpoint verified (no re-execution of prior steps)

**Owner**: [Your Name]  
**Related**: demos/demo_failure_ticket.py

---

## Issue #13: Demo Evidence - Process Crash & Recovery

**Title**: Demo Evidence - Process Crash & Recovery from Checkpoint

**Problem**: 
Graders need to verify the system survives actual crashes (kill -9) and resumes exactly from checkpointed state.

**Constraint**:
- Must simulate real process crash (not just pause)
- Must show checkpoint persisted to database
- Must show no re-execution of completed steps

**Acceptance Criteria**:
- [ ] `demos/demo_crash_resume.py` runs, gets to mid-execution checkpoint
- [ ] Script intentionally crashes (or grader kills process)
- [ ] Restart loads checkpoint and resumes
- [ ] Output shows: resumed from step X (not step 1)
- [ ] Verify checkpoint in database before/after crash

**Owner**: [Your Name]  
**Related**: demos/demo_crash_resume.py, db/checkpointing.py

---

## GitHub Issue Template (`.github/ISSUE_TEMPLATE/final-project.md`)

Copy this into your GitHub repo:

```markdown
---
name: Final Project Issue
about: Create an issue for state graphs, platform, or corrections
title: "[Component] - [Problem]"
labels: final-project
assignees: ''

---

## Problem
<!-- One sentence: What real business problem does this solve? -->

## Constraint
<!-- What makes this hard? What must be true for it to be done? -->

## Acceptance Criteria
- [ ] ...
- [ ] ...
- [ ] ...

## Owner
<!-- GitHub username -->

## Related Files
<!-- Which files need changes? -->

---
**PR that closes this**: [Link PR once submitted]
```

---

## How to Use These Issues

1. **Create each issue** in your GitHub repo (copy-paste the content)
2. **Assign an owner** (team member name/handle)
3. **Add label**: `final-project`
4. **Link PRs**: When you submit code, use "Closes #X" in PR description
5. **Verify before closing**: Run demos, check acceptance criteria

**Result**: 10 points for teamwork & issue rationale + strong evidence of genuine team contribution

---

**Ready to submit on GitHub? Copy-paste, assign owners, and link PRs!**
