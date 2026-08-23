# state_graph/

Three durable state graphs for Vellora Therapeutics Final Project.

| Graph | File | Why stateful | LLM additions | HITL rule |
|-------|------|--------------|---------------|-----------|
| Batch Release | `batch_release_graph.py` | New supplier needs QA sign-off; LIMS can fail mid-release | Task decomposition + RAG | `batch_release_new_supplier` |
| Recall Execution | `recall_execution_graph.py` | External distributor/regulator wait; appeal strategies | Constrained ReAct + Tree of Thoughts | `recall_scope_above_threshold` |
| Supplier CAPA | `supplier_capa_graph.py` | Supplier ack wait; cost gate; portal failures | LATS + Constrained ReAct | `capa_cost_above_threshold` |

## Locatable concerns

- **Graph definitions**: `graphs.py`, each `*_graph.py` (`NODES`, `_run_node`)
- **Checkpointing**: `persistence.py` → `save_checkpoint` / `load_checkpoint`
- **HITL node**: `nodes/hitl_node.py` → `hitl_gate` / `HitlPause`
- **Ticket / failure path**: `nodes/ticket_node.py` → `failure_gate` / `GraphFailure`

## Quick test

```bash
# from repo root
python demos/demo_hitl_pause.py --auto-approve
python demos/demo_failure_ticket.py
python demos/demo_crash_resume.py
python demos/demo_crash_resume.py --resume
```
