# Week 4 — Agent Planning & Reasoning Lab

This executable lab turns the **Week 4 agent-planning concepts** into a compact, practical agent pipeline.

The lab implements and compares several agent reasoning and planning strategies, including **Decomposition, Dynamic Decomposition, Plan-and-Solve, Tree of Thoughts, Reflection, Reflexion, and LATS**.

---

## 🚀 Features

### 1. Decomposition-First

**Mistral** decomposes a complex task into a structured **Directed Acyclic Graph (DAG)** of smaller tasks.

* Tasks are represented as nodes.
* Dependencies are represented as edges.
* Pydantic validates task IDs and dependencies.
* NetworkX performs topological sorting.
* Cyclic dependencies are rejected before execution.
* Independent tasks are executed in parallel when possible.

### 2. Dynamic Decomposition

With `--mode dynamic`, planning and execution are interleaved.

Instead of creating the entire plan upfront:

1. The model creates an initial task.
2. The task is executed.
3. The result becomes an observation.
4. The model uses the observation to determine the next task.

This allows the plan to adapt based on what happens during execution.

### 3. Plan-and-Solve

With `--mode ps`, the agent follows two explicit phases:

1. **Plan** — create a complete plan for the problem.
2. **Solve** — execute the plan and produce the final answer.

This provides a simple baseline for comparing planning-based approaches.

### 4. Tree of Thoughts

With `--mode tot`, the agent performs a bounded search over multiple candidate solutions.

The process consists of:

* Candidate generation
* Candidate evaluation
* Beam search
* Bounded search depth

The `--depth` and `--beam-width` parameters control the size of the search.

### 5. Reflection

The default DAG mode includes a reflection stage.

After execution:

1. An independent critic evaluates the result.
2. Deterministic grounding checks verify important facts.
3. Feedback is generated.
4. The solution can be revised.

This allows the agent to identify and correct mistakes before producing the final result.

### 6. Reflexion

With `--mode reflexion`, the complete task can be retried across multiple trials.

Failed trials produce **bounded verbal memories**, which are passed to subsequent trials.

This allows the agent to learn from previous failures without keeping unlimited history.

### 7. LATS — Language Agent Tree Search

With `--mode lats`, the lab implements a compact **Monte Carlo Tree Search (MCTS)** loop.

The process includes:

* Action generation
* Value estimation
* External environment feedback
* Branch reflection
* UCT selection
* Value backpropagation

LATS combines model reasoning with external feedback to guide search toward better solutions.

---

## 🧩 Structured Outputs

The lab uses **Pydantic schemas** to enforce structured model outputs.

Structured responses are implemented using LangChain's maintained:

```python
ChatMistralAI.with_structured_output(
    ...,
    method="json_schema"
)
```

This ensures that generated plans and other structured responses follow the expected schema.

---

## 📊 Graph Processing

The project uses **NetworkX** for graph operations rather than implementing local graph algorithms.

NetworkX is responsible for:

* Task-graph validation
* Topological ordering
* Dependency handling
* Parallel execution batches
* Terminal-node discovery

