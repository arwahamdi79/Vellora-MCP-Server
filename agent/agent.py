"""
Main AI Agent

Coordinates:
User
 ↓
Gemini
 ↓
MCP Client
 ↓
MCP Server
"""


from conversation import ConversationMemory
from gemini_client import GeminiClient
from mcp_client import MCPClient



class VelloraAgent:


    def __init__(self, server_path):

        self.memory = ConversationMemory()

        self.gemini = GeminiClient()

        self.mcp = MCPClient(
            server_path
        )


    async def initialize(self):

        await self.mcp.connect()

        await self.mcp.discover_everything()

        print(
            "✅ Vellora Agent Ready"
        )


    async def shutdown(self):

        await self.mcp.disconnect()



    async def process_message(
        self,
        user_message
    ):


        self.memory.add_user(
            user_message
        )


        decision = await self.gemini.decide_action(

            user_message=user_message,

            tools_description=
            self.mcp.tool_descriptions(),

            resources_description=
            self.mcp.resource_descriptions(),

            prompts_description=
            self.mcp.prompt_descriptions()

        )


        if decision.type == "tool":

            return await self.handle_tool(
                decision.name,
                decision.arguments
            )


        elif decision.type == "resource":

            return await self.handle_resource(
                decision.name
            )


        elif decision.type == "prompt":

            return await self.handle_prompt(
                decision.name,
                decision.arguments
            )


        else:

            return await self.gemini.chat(
                user_message
            )



    async def handle_tool(
        self,
        name,
        arguments
    ):


        result = await self.mcp.call_tool(
            name,
            arguments
        )


        response = await self.gemini.format_tool_response(
            name,
            result
        )


        self.memory.add_tool(
            name,
            result
        )


        return response



    async def handle_resource(
        self,
        uri
    ):


        result = await self.mcp.read_resource(
            uri
        )


        return await self.gemini.format_resource_response(
            result
        )



    async def handle_prompt(
        self,
        name,
        arguments
    ):


        result = await self.mcp.get_prompt(
            name,
            arguments
        )


        return await self.gemini.format_prompt_response(
            result
        )