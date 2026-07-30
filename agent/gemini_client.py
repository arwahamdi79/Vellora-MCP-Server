"""
Gemini Client
Handles all communication with the Gemini API.
"""

from google import genai
from google.genai import types
from pydantic import BaseModel

from config import GEMINI_API_KEY, MODEL_NAME, SYSTEM_PROMPT


class AgentDecision(BaseModel):
    """
    Structured response returned by Gemini.
    """

    type: str
    name: str
    arguments: dict


class GeminiClient:
    """
    Wrapper around the Gemini API.
    """

    def __init__(self):

        self.client = genai.Client(
            api_key=GEMINI_API_KEY
        )

    async def chat(self, user_message: str) -> str:
        """
        Send a normal chat message to Gemini.
        """

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
            )
        )

        return response.text

    async def decide_action(
        self,
        user_message: str,
        tools_description: str,
        resources_description: str,
        prompts_description: str,
    ) -> AgentDecision:
        """
        Decide which MCP capability should be used.
        """

        router_prompt = f"""
You are the routing engine for the Vellora Therapeutics AI Assistant.

Your job is to decide the best action for each user request.

Available Tools:
{tools_description}

Available Resources:
{resources_description}

Available Prompts:
{prompts_description}

Choose ONLY ONE action.

Rules:

- Use "tool" if a tool should be executed.
- Use "resource" if a company policy or document is needed.
- Use "prompt" if a predefined MCP prompt should be used.
- Use "chat" if no MCP capability is required.

Return ONLY structured data.
"""

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=router_prompt,
                response_mime_type="application/json",
                response_schema=AgentDecision,
            ),
        )

        return response.parsed
