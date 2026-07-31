"""
Gemini Client

Handles communication between
Vellora Agent and Gemini model.
"""


import json
from typing import Any

from google import genai
from google.genai import types

from pydantic import BaseModel, Field

from config import (
    GEMINI_API_KEY,
    MODEL_NAME,
    SYSTEM_PROMPT
)



# ======================================================
# Decision Model
# ======================================================

class AgentDecision(BaseModel):

    type: str = Field(
        description="chat | tool | resource | prompt"
    )

    name: str = Field(
        default=""
    )

    arguments: dict[str, Any] = Field(
        default_factory=dict
    )



# ======================================================
# Gemini Client
# ======================================================

class GeminiClient:


    def __init__(self):

        self.client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        self.model = MODEL_NAME



    # ==================================================
    # Generator
    # ==================================================

    def _generate(
        self,
        *,
        prompt,
        system_prompt,
        schema=None,
        mime_type=None
    ):


        config = types.GenerateContentConfig(

            system_instruction=system_prompt,

            temperature=0

        )


        if mime_type:

            config.response_mime_type = mime_type



        response = self.client.models.generate_content(

            model=self.model,

            contents=prompt,

            config=config

        )


        return response



    # ==================================================
    # Normal Chat
    # ==================================================

    async def chat(
        self,
        message
    ):


        response = self._generate(

            prompt=message,

            system_prompt=SYSTEM_PROMPT

        )


        return response.text



    # ==================================================
    # MCP Router
    # ==================================================

    async def decide_action(
        self,
        *,
        user_message,
        tools_description,
        resources_description,
        prompts_description
    ):


        router_prompt = f"""

You are the routing engine
for Vellora Therapeutics AI Agent.


Available MCP Tools:

{tools_description}



Available MCP Resources:

{resources_description}



Available MCP Prompts:

{prompts_description}



Rules:

1- Choose tool when database information
is required.

2- Choose resource when user asks about:
policies, guidelines, SOPs.

3- Choose prompt when a predefined
report generation prompt is needed.

4- Choose chat for normal questions.



Return ONLY JSON:

{{
"type":"chat | tool | resource | prompt",
"name":"",
"arguments":{{}}
}}

"""


        response = self._generate(

            prompt=user_message,

            system_prompt=router_prompt,

            mime_type="application/json"

        )


        data = json.loads(
            response.text
        )


        return AgentDecision(
            **data
        )



    # ==================================================
    # Tool Response
    # ==================================================

    async def format_tool_response(
        self,
        tool_name,
        tool_result
    ):


        prompt = f"""

Tool executed:

{tool_name}


Result:

{tool_result}


Explain this result professionally.

Do not mention:
- MCP
- JSON
- internal implementation

"""


        response = self._generate(

            prompt=prompt,

            system_prompt=SYSTEM_PROMPT

        )


        return response.text



    # ==================================================
    # Resource Response
    # ==================================================

    async def format_resource_response(
        self,
        resource
    ):


        response = self._generate(

            prompt=str(resource),

            system_prompt=SYSTEM_PROMPT

        )


        return response.text



    # ==================================================
    # Prompt Response
    # ==================================================

    async def format_prompt_response(
        self,
        prompt_result
    ):


        response = self._generate(

            prompt=str(prompt_result),

            system_prompt=SYSTEM_PROMPT

        )


        return response.text