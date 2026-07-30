"""
Gemini Client
Handles all communication with the Gemini API.
"""

import json

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, MODEL_NAME, SYSTEM_PROMPT


class GeminiClient:

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
        prompts_description: str
    ):
        """
        Decide whether the user needs:
        - Tool
        - Resource
        - Prompt
        - Normal Chat
        """

        router_prompt = f"""
You are an Intent Router.

Available Tools:

{tools_description}

Available Resources:

{resources_description}

Available Prompts:

{prompts_description}

Analyze the user's request.

Return ONLY valid JSON.

Format:

{{
    "type":"tool | resource | prompt | chat",
    "name":"",
    "arguments":{{}}
}}

User:

{user_message}
"""

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=router_prompt
        )

        return json.loads(response.text)
