"""
state_graph/llm_client.py

Single, real Anthropic client shared by all three graphs' LLM-call
additions (constrained ReAct, Tree of Thoughts, task decomposition, RAG
grounding). Replaces the `from your_llm_client import llm  # TODO`
placeholders that used to sit in each graph file.

Reads ANTHROPIC_API_KEY from the environment -- never hardcode it here,
and make sure your platform's own .env stays out of version control too.
"""

import os
import json
import anthropic

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-6"


def complete_json(system: str, user: str, max_tokens: int = 1024) -> dict:
    """
    Calls the model with a system prompt that demands JSON-only output,
    strips any accidental code-fence wrapping, and parses it. Used by the
    structured-output helpers (Tree of Thoughts scoring, checklist
    evaluation) where the graph needs a machine-readable verdict, not prose.
    """
    response = _client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system + "\n\nRespond with ONLY a JSON object. No preamble, no markdown fences.",
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    cleaned = text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


def complete_text(system: str, user: str, max_tokens: int = 1024) -> str:
    """Plain-text completion, used for the free-text root-cause writeup."""
    response = _client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def run_constrained_react(
    system: str,
    user: str,
    tool_specs: list[dict],
    tool_executor,
    max_turns: int = 4,
) -> dict:
    """
    A minimal constrained ReAct loop: the model may ONLY call tools present
    in `tool_specs` (Anthropic tool-use schema). Any tool_use block whose
    name isn't in that whitelist is rejected with a tool_result error
    instead of being executed -- this is the actual constraint, not just a
    prompt instruction the model could ignore.

    `tool_executor(tool_name: str, tool_input: dict) -> dict` is called only
    for whitelisted tool names, and should be the caller's real MCP tool
    wrapper (e.g. add_quality_test, change_batch_status).

    Returns the final assistant text response once the model stops calling
    tools (or max_turns is hit).
    """
    allowed_names = {spec["name"] for spec in tool_specs}
    messages = [{"role": "user", "content": user}]

    for _ in range(max_turns):
        response = _client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=tool_specs,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {"final_text": final_text, "messages": messages}

        tool_results = []
        for block in tool_uses:
            if block.name not in allowed_names:
                # The actual constraint: refuse anything outside the whitelist
                # rather than executing it.
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Tool '{block.name}' is not permitted in this node.",
                    "is_error": True,
                })
                continue
            try:
                result = tool_executor(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
            except Exception as exc:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Tool execution error: {exc}",
                    "is_error": True,
                })

        messages.append({"role": "user", "content": tool_results})

    return {"final_text": "Max turns reached without a final answer.", "messages": messages}