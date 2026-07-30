"""
Main AI Agent

Coordinates communication between:

User
↓

Gemini

↓

MCP Server
"""

from conversation import ConversationMemory
from gemini_client import GeminiClient
from mcp_client import MCPClient


class VelloraAgent:

    def __init__(self, server_path: str):

        self.memory = ConversationMemory()

        self.gemini = GeminiClient()

        self.mcp = MCPClient(server_path)

    # =====================================================
    # Initialization
    # =====================================================

    async def initialize(self):

        await self.mcp.connect()

        await self.mcp.discover_everything()

        print("✅ Vellora Agent Ready")

    async def shutdown(self):

        await self.mcp.disconnect()

    # =====================================================
    # Main Entry
    # =====================================================

    async def process_message(
        self,
        user_message: str,
    ) -> str:

        self.memory.add_user(user_message)

        decision = await self.gemini.decide_action(

            user_message=user_message,

            tools_description=self.mcp.tool_descriptions(),

            resources_description=self.mcp.resource_descriptions(),

            prompts_description=self.mcp.prompt_descriptions(),

        )

        try:

            if decision.type == "chat":

                return await self._handle_chat(
                    user_message
                )

            elif decision.type == "tool":

                return await self._handle_tool(
                    user_message,
                    decision.name,
                    decision.arguments,
                )

            elif decision.type == "resource":

                return await self._handle_resource(
                    user_message,
                    decision.name,
                )

            elif decision.type == "prompt":

                return await self._handle_prompt(
                    decision.name,
                    decision.arguments,
                )

            else:

                return await self._handle_chat(
                    user_message
                )

        except Exception as e:

            return f"Error: {e}"

    # =====================================================
    # Chat
    # =====================================================

    async def _handle_chat(
        self,
        message: str,
    ) -> str:

        response = await self.gemini.chat(
            message
        )

        self.memory.add_assistant(response)

        return response

    # =====================================================
    # Tool
    # =====================================================

    async def _handle_tool(
        self,
        user_question: str,
        tool_name: str,
        arguments: dict,
    ) -> str:

        result = await self.mcp.call_tool(
            tool_name,
            arguments,
        )

        self.memory.add_tool(
            tool_name,
            result,
        )

        response = await self.gemini.format_tool_response(

            user_question=user_question,

            tool_name=tool_name,

            tool_result=result,

        )

        self.memory.add_assistant(
            response
        )

        return response

    # =====================================================
    # Resource
    # =====================================================

    async def _handle_resource(
        self,
        user_question: str,
        resource_uri: str,
    ) -> str:

        resource = await self.mcp.read_resource(
            resource_uri
        )

        response = await self.gemini.format_resource_response(

            user_question=user_question,

            resource=resource,

        )

        self.memory.add_assistant(
            response
        )

        return response

    # =====================================================
    # Prompt
    # =====================================================

    async def _handle_prompt(
        self,
        prompt_name: str,
        arguments: dict,
    ) -> str:

        prompt = await self.mcp.get_prompt(
            prompt_name,
            arguments,
        )

        response = await self.gemini.format_prompt_response(
            prompt
        )

        self.memory.add_assistant(
            response
        )

        return response
