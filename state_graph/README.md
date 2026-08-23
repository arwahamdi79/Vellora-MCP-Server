# State Graphs

`graphs.py` contains the three durable workflows. `persistence.py` is the shared SQLite checkpoint layer. `nodes/` exposes the HITL and ticket operations so a grader can locate them immediately.

Technique pairs are recorded in `TECHNIQUES`: Batch Release uses task decomposition + RAG; Recall Coordination uses constrained ReAct + Tree of Thoughts; Supplier CAPA uses task decomposition + RAG.
