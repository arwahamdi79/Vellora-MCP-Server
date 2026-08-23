"""Technique adapters used by the state graphs. Real LLM calls can be enabled with a provider key."""
import os
def task_decomposition(goal, items): return {"goal":goal,"steps":list(items)}
def rag(query, documents=None): return {"query":query,"context":documents or []}
def constrained_react(action, allowed): return {"action":action,"allowed":action in allowed}
def tree_of_thoughts(options, score_fn=lambda x:0): return max(options,key=score_fn) if options else None
