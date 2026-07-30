"""
Application Entry Point
Vellora Therapeutics AI Agent
"""

import asyncio

from agent import VelloraAgent
from config import SERVER_PATH
from ui import (
    assistant_output,
    error,
    success,
    user_input,
    welcome,
)


async def main():

    agent = VelloraAgent(SERVER_PATH)

    try:
        # -------------------------------
        # Initialize Agent
        # -------------------------------
        await agent.initialize()

        welcome()

        success("Agent initialized successfully.\n")

        # -------------------------------
        # Main Chat Loop
        # -------------------------------
        while True:

            try:

                message = user_input().strip()

                if not message:
                    continue

                if message.lower() in {
                    "exit",
                    "quit",
                    "q",
                }:
                    break

                response = await agent.process_message(message)

                assistant_output(response)

            except KeyboardInterrupt:
                break

            except Exception as e:
                error(f"\nUnexpected Error:\n{e}\n")

    except Exception as e:

        error(f"\nFailed to start the application.\n{e}\n")

    finally:

        try:
            await agent.shutdown()
            success("Disconnected from MCP Server.")

        except Exception:
            pass


if __name__ == "__main__":

    asyncio.run(main())
