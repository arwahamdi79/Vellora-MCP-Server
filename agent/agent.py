"""
Main AI Agent

Coordinates communication between:

User
    │
    ▼
 Gemini
    │
    ▼
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

        history = self.memory.last_messages(10)

        try:

            decision = await self.gemini.decide_action(

                user_message=user_message,

                history=history,

                tools_description=self.mcp.tool_descriptions(),

                resources_description=self.mcp.resource_descriptions(),

                prompts_description=self.mcp.prompt_descriptions(),

            )

            decision_type = decision.type.lower()

            handlers = {

                "chat":
                    lambda: self._handle_chat(
                        user_message
                    ),

                "tool":
                    lambda: self._handle_tool(
                        user_message,
                        decision.name,
                        decision.arguments,
                    ),

                "resource":
                    lambda: self._handle_resource(
                        user_message,
                        decision.name,
                    ),

                "prompt":
                    lambda: self._handle_prompt(
                        decision.name,
                        decision.arguments,
                    ),

            }

            handler = handlers.get(

                decision_type,

                lambda: self._handle_chat(
                    user_message
                ),

            )

            return await handler()

        except Exception as e:

            return f"Unexpected Error: {e}"

    # =====================================================
    # Chat
    # =====================================================

    async def _handle_chat(
        self,
        message: str,
    ) -> str:

        response = await self.gemini.chat(

            message=message,

            history=self.memory.last_messages(10),

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

        if not self.mcp.has_tool(tool_name):

            return (
                f"The requested tool "
                f"'{tool_name}' "
                f"is not available."
            )

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

            history=self.memory.last_messages(10),

        )

        self.memory.add_assistant(response)

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

            history=self.memory.last_messages(10),

        )

        self.memory.add_assistant(response)

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

            prompt,

            history=self.memory.last_messages(10),

        )

        self.memory.add_assistant(response)

        return response
