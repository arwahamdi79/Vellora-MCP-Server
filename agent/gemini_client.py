"""
Gemini Client
Handles all communication with the Gemini API.
"""

from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from config import (
    GEMINI_API_KEY,
    MODEL_NAME,
    SYSTEM_PROMPT,
)


# ==========================================================
# Models
# ==========================================================

class AgentDecision(BaseModel):
    """
    Structured decision returned by Gemini.
    """

    type: str = Field(
        description="chat | tool | resource | prompt"
    )

    name: str = Field(default="")

    arguments: dict[str, Any] = Field(
        default_factory=dict
    )


# ==========================================================
# Gemini Client
# ==========================================================

class GeminiClient:

    def __init__(self):

        self.client = genai.Client(
            api_key=GEMINI_API_KEY
        )

    # ======================================================
    # Helpers
    # ======================================================

    def _history_to_text(
        self,
        history: list | None,
    ) -> str:

        if not history:
            return "No previous conversation."

        lines = []

        for message in history:

            role = message.get(
                "role",
                "unknown"
            )

            if role == "tool":

                lines.append(
                    f"""
Tool: {message.get('tool')}

Result:
{message.get('result')}
"""
                )

            else:

                lines.append(
                    f"{role.capitalize()}: {message.get('text','')}"
                )

        return "\n".join(lines)

    # ======================================================
    # Low-Level Generator
    # ======================================================

    def _generate(
        self,
        *,
        prompt: str,
        system_prompt: str,
        schema=None,
        mime_type=None,
    ):

        config = types.GenerateContentConfig(
            system_instruction=system_prompt
        )

        if schema is not None:
            config.response_schema = schema

        if mime_type is not None:
            config.response_mime_type = mime_type

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=config,
        )

        return response

    # ======================================================
    # Normal Chat
    # ======================================================

    async def chat(
        self,
        *,
        message: str,
        history: list | None = None,
    ) -> str:

        conversation = self._history_to_text(
            history
        )

        prompt = f"""
Conversation History

{conversation}

Current User Message

{message}

Respond naturally.
"""

        response = self._generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        return response.text

    # ======================================================
    # Decide Action
    # ======================================================

    async def decide_action(
        self,
        *,
        user_message: str,
        history: list | None,
        tools_description: str,
        resources_description: str,
        prompts_description: str,
    ) -> AgentDecision:

        conversation = self._history_to_text(
            history
        )

        router_prompt = f"""
You are the routing engine of the Vellora AI Agent.

Your ONLY responsibility is selecting ONE action.

Conversation History

{conversation}

Available Tools

{tools_description}

Available Resources

{resources_description}

Available Prompts

{prompts_description}

Rules

1. Use "tool" when company data is required.

2. Use "resource" for company policies.

3. Use "prompt" for predefined prompt templates.

4. Otherwise return "chat".

Always use conversation history
to resolve references like:

"it"

"that"

"same medicine"

"previous batch"

Return ONLY valid JSON.
"""

        response = self._generate(
            prompt=user_message,
            system_prompt=router_prompt,
            schema=AgentDecision,
            mime_type="application/json",
        )

        return response.parsed

    # ======================================================
    # Tool Formatting
    # ======================================================

    async def format_tool_response(
        self,
        *,
        user_question: str,
        tool_name: str,
        tool_result,
        history: list | None = None,
    ) -> str:

        conversation = self._history_to_text(
            history
        )

        prompt = f"""
Conversation History

{conversation}

User Question

{user_question}

Executed Tool

{tool_name}

Tool Result

{tool_result}

Write a professional response.

Never mention:

- MCP
- JSON
- Internal tools
"""

        response = self._generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        return response.text

    # ======================================================
    # Resource Formatting
    # ======================================================

    async def format_resource_response(
        self,
        *,
        user_question: str,
        resource,
        history: list | None = None,
    ) -> str:

        conversation = self._history_to_text(
            history
        )

        prompt = f"""
Conversation History

{conversation}

User Question

{user_question}

Company Resource

{resource}

Answer ONLY using the resource.
"""

        response = self._generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        return response.text

    # ======================================================
    # Prompt Formatting
    # ======================================================

    async def format_prompt_response(
        self,
        prompt_result,
        history: list | None = None,
    ) -> str:

        conversation = self._history_to_text(
            history
        )

        prompt = f"""
Conversation History

{conversation}

Generated Prompt

{prompt_result}
"""

        response = self._generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        return response.text
