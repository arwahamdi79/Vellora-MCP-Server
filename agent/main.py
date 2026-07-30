import asyncio

from config import SERVER_PATH
from agent import VelloraAgent
from ui import (
    welcome,
    user_input,
    assistant_output
)


async def main():

    agent = VelloraAgent(SERVER_PATH)

    await agent.initialize()

    welcome()

    while True:

        message = user_input()

        if message.lower() in ["exit", "quit"]:

            break

        response = await agent.process_message(message)

        assistant_output(response)

    await agent.shutdown()


if __name__ == "__main__":

    asyncio.run(main())
