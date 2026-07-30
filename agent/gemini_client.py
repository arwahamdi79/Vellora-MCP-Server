from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from config import GEMINI_API_KEY, MODEL_NAME, SYSTEM_PROMPT


class AgentDecision(BaseModel):
    """
    Structured decision returned by Gemini Router.
    """

    type: str = Field(
        description="One of: chat, tool, resource, prompt"
    )

    name: str = Field(
        default="",
        description="Tool / Resource / Prompt name"
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments required by the selected action"
    )


class GeminiClient:

    def __init__(self):

        self.client = genai.Client(
            api_key=GEMINI_API_KEY
        )

    def _generate(
        self,
        prompt: str,
        system_prompt: str,
        response_schema=None,
        response_mime_type=None,
    ):

        config = types.GenerateContentConfig(
            system_instruction=system_prompt
        )

        if response_schema:
            config.response_schema = response_schema

        if response_mime_type:
            config.response_mime_type = response_mime_type

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=config
        )

        return response

    async def chat(
        self,
        message: str
    ) -> str:

        response = self._generate(
            prompt=message,
            system_prompt=SYSTEM_PROMPT
        )

        return response.text

    async def decide_action(
        self,
        user_message: str,
        tools_description: str,
        resources_description: str,
        prompts_description: str,
    ) -> AgentDecision:

        router_prompt = f"""
You are the routing engine of the Vellora Therapeutics AI Agent.

Your task is ONLY to decide what action should happen.

Available Tools:
{tools_description}

Available Resources:
{resources_description}

Available Prompts:
{prompts_description}

Rules:

1. Use "tool" ONLY if company data is required.
2. Use "resource" ONLY for company policies.
3. Use "prompt" ONLY for predefined prompt templates.
4. Otherwise use "chat".

Return ONLY valid JSON.
"""

        response = self._generate(
            prompt=user_message,
            system_prompt=router_prompt,
            response_schema=AgentDecision,
            response_mime_type="application/json",
        )

        return response.parsed

    async def format_tool_response(
        self,
        user_question: str,
        tool_result,
    ) -> str:

        prompt = f"""
User Question:

{user_question}

Tool Result:

{tool_result}

Write a professional response.

Do not mention JSON.
Do not mention internal MCP implementation.
"""

        response = self._generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT
        )

        return response.text
