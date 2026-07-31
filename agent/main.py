from agent import VelloraAgent
from config import SERVER_PATH
import asyncio


async def main():

    agent = VelloraAgent(
        SERVER_PATH
    )


    await agent.initialize()


    while True:

        message = input(
            "\nYou: "
        )


        if message.lower() in [
            "exit",
            "quit"
        ]:
            break


        response = await agent.process_message(
            message
        )


        print(
            "\nAssistant:",
            response
        )


    await agent.shutdown()



if __name__ == "__main__":

    asyncio.run(main())