"""
Main AI Agent
Coordinates communication between Gemini and the MCP Server.
"""

import json

from gemini_client import GeminiClient
from mcp_client import MCPClient
from conversation import ConversationMemory


class VelloraAgent:

    def __init__(self, server_path):

        self.memory = ConversationMemory()

        self.gemini = GeminiClient()

        self.mcp = MCPClient(server_path)

    async def initialize(self):
        """
        Connect to the MCP Server and discover its capabilities.
        """

        await self.mcp.connect()

        await self.mcp.discover_everything()

        print("Agent initialized successfully.")

    async def shutdown(self):
        """
        Close the MCP connection.
        """

        await self.mcp.disconnect()

    async def process_message(self, user_message: str):

        # Store user message
        self.memory.add_user(user_message)

        # Ask Gemini what action should be taken
        decision = await self.gemini.decide_action(
            user_message=user_message,
            tools_description=self.mcp.tool_descriptions(),
            resources_description=self.mcp.resource_descriptions(),
            prompts_description=self.mcp.prompt_descriptions()
        )

        action_type = decision["type"]

        # -------------------------
        # Normal Chat
        # -------------------------

        if action_type == "chat":

            answer = await self.gemini.chat(user_message)

            self.memory.add_assistant(answer)

            return answer

        # -------------------------
        # Tool
        # -------------------------

        elif action_type == "tool":

            tool_result = await self.mcp.call_tool(
                decision["name"],
                decision["arguments"]
            )

            self.memory.add_tool(
                decision["name"],
                tool_result
            )

            final_answer = await self.gemini.chat(
                f"""
The user asked:

{user_message}

The tool returned:

{tool_result}

Generate a professional response.
"""
            )

            self.memory.add_assistant(final_answer)

            return final_answer

        # -------------------------
        # Resource
        # -------------------------

        elif action_type == "resource":

            resource = await self.mcp.read_resource(
                decision["name"]
            )

            final_answer = await self.gemini.chat(
                f"""
User question:

{user_message}

Resource:

{resource}

Answer the user.
"""
            )

            self.memory.add_assistant(final_answer)

            return final_answer

        # -------------------------
        # Prompt
        # -------------------------

        elif action_type == "prompt":

            prompt = await self.mcp.get_prompt(
                decision["name"],
                decision["arguments"]
            )

            final_answer = await self.gemini.chat(prompt)

            self.memory.add_assistant(final_answer)

            return final_answer

        else:

            return "Unknown action returned by Gemini."
