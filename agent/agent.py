"""
Main AI Agent
Coordinates communication between Gemini and the MCP Server.
"""

from conversation import ConversationMemory
from gemini_client import GeminiClient
from mcp_client import MCPClient


class VelloraAgent:

    def __init__(self, server_path: str):

        self.memory = ConversationMemory()

        self.gemini = GeminiClient()

        self.mcp = MCPClient(server_path)

    async def initialize(self):
        """
        Initialize the agent.
        """

        await self.mcp.connect()

        await self.mcp.discover_everything()

        print("Vellora Agent initialized successfully.")

    async def shutdown(self):
        """
        Shutdown the agent.
        """

        await self.mcp.disconnect()

    async def process_message(self, user_message: str):

        # Save user message
        self.memory.add_user(user_message)

        # Ask Gemini to decide what to do
        decision = await self.gemini.decide_action(
            user_message=user_message,
            tools_description=self.mcp.tool_descriptions(),
            resources_description=self.mcp.resource_descriptions(),
            prompts_description=self.mcp.prompt_descriptions(),
        )

        # -----------------------------
        # Chat
        # -----------------------------

        if decision.type == "chat":

            response = await self.gemini.chat(user_message)

            self.memory.add_assistant(response)

            return response

        # -----------------------------
        # Tool
        # -----------------------------

        elif decision.type == "tool":

            tool_result = await self.mcp.call_tool(
                decision.name,
                decision.arguments
            )

            self.memory.add_tool(
                decision.name,
                tool_result
            )

            response = await self.gemini.chat(
                f"""
User Question:

{user_message}

Tool Result:

{tool_result}

Answer the user professionally.
"""
            )

            self.memory.add_assistant(response)

            return response

        # -----------------------------
        # Resource
        # -----------------------------

        elif decision.type == "resource":

            resource = await self.mcp.read_resource(
                decision.name
            )

            response = await self.gemini.chat(
                f"""
User Question:

{user_message}

Company Resource:

{resource}

Answer the question.
"""
            )

            self.memory.add_assistant(response)

            return response

        # -----------------------------
        # Prompt
        # -----------------------------

        elif decision.type == "prompt":

            prompt = await self.mcp.get_prompt(
                decision.name,
                decision.arguments
            )

            response = await self.gemini.chat(str(prompt))

            self.memory.add_assistant(response)

            return response

        # -----------------------------
        # Unknown
        # -----------------------------

        return "Unable to determine the correct action."
