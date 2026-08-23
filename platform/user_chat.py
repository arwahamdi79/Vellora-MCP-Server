"""User chat helpers — agent list for the switcher."""
from state_graph.graphs import list_graphs


def available_agents():
    graphs = list(list_graphs().keys())
    return graphs + ["memory_rag", "planning"]
