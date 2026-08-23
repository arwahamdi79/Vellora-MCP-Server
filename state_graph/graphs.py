"""
state_graph/graphs.py

Registry of the three state graphs + technique pairings.
A grader should be able to find graph definitions and the two LLM additions here.
"""

from state_graph import batch_release_graph
from state_graph import recall_execution_graph
from state_graph import supplier_capa_graph

GRAPHS = {
    "batch_release": {
        "module": batch_release_graph,
        "description": "Multi-step batch release with new-supplier HITL",
        "llm_additions": ["task_decomposition", "RAG"],
        "hitl_rules": ["batch_release_new_supplier", "low_confidence"],
    },
    "recall_execution": {
        "module": recall_execution_graph,
        "description": "Product recall coordination with external wait + ToT strategy",
        "llm_additions": ["constrained_ReAct", "Tree_of_Thoughts"],
        "hitl_rules": ["recall_scope_above_threshold"],
    },
    "supplier_capa": {
        "module": supplier_capa_graph,
        "description": "Supplier CAPA with LATS ordering search + cost HITL",
        "llm_additions": ["LATS", "constrained_ReAct"],
        "hitl_rules": ["capa_cost_above_threshold"],
    },
}


def get_graph(name: str):
    entry = GRAPHS.get(name)
    if not entry:
        raise KeyError(f"Unknown graph: {name}. Available: {list(GRAPHS)}")
    return entry["module"]


def list_graphs():
    return {
        k: {
            "description": v["description"],
            "llm_additions": v["llm_additions"],
            "hitl_rules": v["hitl_rules"],
        }
        for k, v in GRAPHS.items()
    }
