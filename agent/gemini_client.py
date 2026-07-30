"""
Gemini Client
Handles all communication with the Gemini API.
"""

from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from config import GEMINI_API_KEY, MODEL_NAME, SYSTEM_PROMPT


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

    name: str = Field(
        default=""
    )

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

    # ------------------------------------------------------
    # Private Generator
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # Normal Chat
    # ------------------------------------------------------

    async def chat(
        self,
        message: str
    ) -> str:

        response = self._generate(
            prompt=message,
            system_prompt=SYSTEM_PROMPT,
        )

        return response.text

    # ------------------------------------------------------
    # Decide MCP Action
    # ------------------------------------------------------

    async def decide_action(
        self,
        *,
        user_message: str,
        tools_description: str,
        resources_description: str,
        prompts_description: str,
    ) -> AgentDecision:

        router_prompt = f"""
You are the routing engine of the Vellora Therapeutics AI Agent.

Your ONLY responsibility is choosing ONE action.

Available Tools
================
{tools_description}

Available Resources
===================
{resources_description}

Available Prompts
=================
{prompts_description}

Decision Rules

1. Use "tool" if company database information is required.

2. Use "resource" if the user asks about a policy, guideline,
documentation or company knowledge.

3. Use "prompt" only when a predefined MCP prompt is appropriate.

4. Otherwise use "chat".

Return ONLY valid JSON.

Never explain your decision.
"""

        response = self._generate(
            prompt=user_message,
            system_prompt=router_prompt,
            schema=AgentDecision,
            mime_type="application/json",
        )

        return response.parsed

    # ------------------------------------------------------
    # Generate Final Answer After Tool
    # ------------------------------------------------------

    async def format_tool_response(
        self,
        *,
        user_question: str,
        tool_name: str,
        tool_result,
    ) -> str:

        prompt = f"""
User Question

{user_question}

Executed Tool

{tool_name}

Tool Result

{tool_result}

Write a natural professional response.

Rules

- Never mention JSON.
- Never mention MCP.
- Never mention internal implementation.
- Explain the result clearly.
"""

        response = self._generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        return response.text

    # ------------------------------------------------------
    # Generate Final Answer After Resource
    # ------------------------------------------------------

    async def format_resource_response(
        self,
        *,
        user_question: str,
        resource,
    ) -> str:

        prompt = f"""
User Question

{user_question}

Company Resource

{resource}

Answer using only the provided resource.

If the answer is not available,
say that politely.
"""

        response = self._generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        return response.text

    # ------------------------------------------------------
    # Generate Final Answer After Prompt
    # ------------------------------------------------------

    async def format_prompt_response(
        self,
        prompt_result,
    ) -> str:

        response = self._generate(
            prompt=str(prompt_result),
            system_prompt=SYSTEM_PROMPT,
        )

        return response.text
