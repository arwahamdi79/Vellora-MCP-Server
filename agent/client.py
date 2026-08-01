"""
Vellora Therapeutics — Interactive MCP Client
===============================================

Connects to Vellora MCP Server over stdio.
Discovers tools/resources and provides interactive menu.

Run:
    py agent/client.py
"""

import asyncio
import json
import sys

from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_COMMAND = sys.executable

SERVER_ARGS = [
    "-m",
    "mcp_server.server"
]


RESOURCE_MENU = {

    "1": (
        "policy://batch_approval",
        "Batch Approval Policy"
    ),

    "2": (
        "policy://manufacturing_sop",
        "Manufacturing SOP"
    ),

    "3": (
        "policy://product_recall",
        "Product Recall Procedure"
    ),

    "4": (
        "policy://storage_guidelines",
        "Drug Storage Guidelines"
    )

}



def banner():

    print(
        "========================================="
    )

    print(
        "      VELLORA THERAPEUTICS CLIENT"
    )

    print(
        "=========================================\n"
    )



def print_menu():

    print(
        """

1.  View Medicines
2.  Search Medicine
3.  Create Production Order
4.  View Batches
5.  Update Batch Status
6.  Record Quality Test
7.  View Quality Tests
8.  Create Product Recall
9.  View Product Recalls
10. Read Company Policies
11. Search Company Knowledge (RAG)
12. Exit

"""
    )



def pretty(payload):

    try:

        data = json.loads(payload)

    except:

        print(payload)
        return


    print(
        json.dumps(
            data,
            indent=4,
            default=str
        )
    )



def extract_json(raw):

    try:

        return json.loads(raw)

    except:

        return None




def ask(prompt, cast=str):

    while True:

        value = input(prompt)

        try:

            return cast(value)

        except:

            print(
                "Invalid input"
            )




class VelloraClient:


    def __init__(
        self,
        session: ClientSession
    ):

        self.session = session

        self.employee_id = None



    async def call_tool(
        self,
        name,
        arguments
    ):

        try:

            result = await self.session.call_tool(
                name,
                arguments=arguments
            )


        except Exception as e:

            print(
                f"\nTool error: {e}"
            )

            return None



        texts = []


        for block in result.content:

            if hasattr(block,"text"):

                texts.append(
                    block.text
                )


        return "\n".join(texts)




    async def login(self):


        while True:


            emp_id = ask(
                "Enter Employee ID: ",
                int
            )


            result = await self.call_tool(
                "employee",
                {
                    "employee_id": emp_id
                }
            )


            if result is None:

                continue



            data = extract_json(result)



            if not data:

                print(
                    "Employee not found"
                )

                continue



            print(
                f"\nWelcome {data['FullName']}"
            )

            print(
                f"Role: {data['Role']}"
            )


            self.employee_id = emp_id

            break





    async def view_medicines(self):


        result = await self.call_tool(

            "get_medicines",

            {
                "employee_id":
                self.employee_id
            }

        )


        pretty(result)




    async def search_medicine(self):


        medicine_id = ask(
            "Medicine ID: ",
            int
        )


        result = await self.call_tool(

            "get_medicine",

            {
                "employee_id":
                self.employee_id,

                "medicine_id":
                medicine_id
            }

        )


        pretty(result)





    async def view_batches(self):


        result = await self.call_tool(

            "get_batches",

            {
                "employee_id":
                self.employee_id
            }

        )


        pretty(result)





    async def view_quality_tests(self):


        result = await self.call_tool(

            "get_quality_tests",

            {
                "employee_id":
                self.employee_id
            }

        )


        pretty(result)





    async def view_recalls(self):


        result = await self.call_tool(

            "get_recalls",

            {
                "employee_id":
                self.employee_id
            }

        )


        pretty(result)





    async def read_policies(self):


        print(
            "\nPolicies:"
        )


        for key,value in RESOURCE_MENU.items():

            print(
                key,
                value[1]
            )



        choice=input(
            "Choose: "
        )



        uri,title = RESOURCE_MENU[choice]



        result = await self.session.read_resource(
            uri
        )



        print(
            "\n======",
            title,
            "======\n"
        )


        for item in result.contents:

            if hasattr(item,"text"):

                print(
                    item.text
                )





    async def search_knowledge(self):


        query=input(
            "\nAsk company question: "
        )


        result = await self.call_tool(

            "search_knowledge_base",

            {

                "query":
                query,


                "top_k":
                3

            }

        )


        print(
            "\n====== RAG RESULT ======\n"
        )


        print(result)





    async def run_menu(self):


        actions={


            "1":
            self.view_medicines,


            "2":
            self.search_medicine,


            "4":
            self.view_batches,


            "7":
            self.view_quality_tests,


            "9":
            self.view_recalls,


            "10":
            self.read_policies,


            "11":
            self.search_knowledge

        }



        while True:


            print_menu()


            choice=input(
                "Choose: "
            )



            if choice=="12":

                print(
                    "Goodbye"
                )

                break



            action=actions.get(choice)



            if action:

                await action()

            else:

                print(
                    "Invalid choice"
                )







async def main():


    banner()


    params = StdioServerParameters(

        command=SERVER_COMMAND,

        args=SERVER_ARGS

    )



    async with AsyncExitStack() as stack:


        read,write = await stack.enter_async_context(

            stdio_client(params)

        )



        session = await stack.enter_async_context(

            ClientSession(
                read,
                write
            )

        )



        await session.initialize()



        print(
            "✓ Connected\n"
        )



        tools = await session.list_tools()



        print(
            "Available tools:"
        )


        for tool in tools.tools:

            print(
                "-",
                tool.name
            )


        client = VelloraClient(
            session
        )


        await client.login()


        await client.run_menu()





if __name__=="__main__":


    asyncio.run(main())