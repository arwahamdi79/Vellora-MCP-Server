"""Start / resume state-graph agents from the platform."""
from state_graph.graphs import get_graph, GRAPHS


def run_agent(name: str, **kwargs):
    mod = get_graph(name)
    if name == "batch_release":
        return mod.run(
            batch_id=kwargs.get("batch_id", "BATCH-001"),
            is_new_supplier=kwargs.get("is_new_supplier", False),
            force_fail=kwargs.get("force_fail", False),
        )
    if name == "recall_execution":
        return mod.run(
            recall_id=kwargs.get("recall_id", "RCL-001"),
            units_affected=int(kwargs.get("units_affected", 1000)),
            force_fail=kwargs.get("force_fail", False),
        )
    if name == "supplier_capa":
        return mod.run(
            supplier_id=kwargs.get("supplier_id", "SUP-001"),
            estimated_cost=float(kwargs.get("estimated_cost", 1000)),
            force_fail=kwargs.get("force_fail", False),
        )
    raise ValueError(name)


def resume_agent(name: str, run_id: str, hitl_decision=None):
    mod = get_graph(name)
    return mod.resume(run_id, hitl_decision=hitl_decision)
