"""
Vellora Therapeutics — Interactive MCP Client
===============================================
Connects to the Vellora MCP server over stdio, discovers its tools and
resources, and drives them through a simple numbered menu.

Run with:
    python3 client.py
"""

import asyncio
import json
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_COMMAND = sys.executable

SERVER_ARGS = ["-m", "mcp_server.server"]

RESOURCE_MENU = {
    "1": ("policy://batch_approval", "Batch Approval Policy"),
    "2": ("policy://manufacturing_sop", "Manufacturing SOP"),
    "3": ("policy://product_recall", "Product Recall Procedure"),
    "4": ("policy://storage_guidelines", "Drug Storage Guidelines"),
}


def banner():
    print("=========================================")
    print("      VELLORA THERAPEUTICS CLIENT")
    print("=========================================\n")


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
11. Exit
"""
    )


def pretty(payload):
    """Pretty-print a tool result (list/dict of rows, or an elicitation prompt)."""
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except (json.JSONDecodeError, TypeError):
        print(payload)
        return

    if isinstance(data, dict) and data.get("status") == "input_required":
        print(f"\n[Missing information] {data['message']}")
        print("Missing fields:", ", ".join(data["missing_fields"]))
        return

    print(json.dumps(data, indent=2, default=str))


def ask(prompt, cast=str, allow_blank=False):
    while True:
        raw = input(prompt).strip()
        if raw == "" and allow_blank:
            return None
        try:
            return cast(raw)
        except ValueError:
            print(f"  Please enter a valid {cast.__name__}.")


class VelloraClient:
    def __init__(self, session: ClientSession):
        self.session = session
        self.employee_id = None

    async def login(self):
        while True:
            emp_id = ask("Enter your Employee ID to log in: ", int)
            result = await self.call_tool("employee", {"employee_id": emp_id})
            data = extract_json(result)
            if not data:
                print("  No employee found with that ID. Try again.\n")
                continue
            print(f"\nWelcome, {data['FullName']} ({data['Role']}, {data['Department']}).")
            if data.get("AccountStatus") != "Active":
                print("  NOTE: your account is INACTIVE — actions may be rejected by the server.\n")
            self.employee_id = emp_id
            return

    async def call_tool(self, name, arguments):
        try:
            result = await self.session.call_tool(name, arguments=arguments)
        except Exception as exc:  # transport-level error
            print(f"\n[Error calling {name}]: {exc}")
            return None

        if result.isError:
            for block in result.content:
                if hasattr(block, "text"):
                    print(f"\n[Server error] {block.text}")
            return None

        texts = [block.text for block in result.content if hasattr(block, "text")]
        return "\n".join(texts) if texts else None

    async def call_tool_with_elicitation(self, name, arguments, prompts):
        """Call a tool; if it reports missing fields, prompt for them and retry."""
        while True:
            raw = await self.call_tool(name, arguments)
            if raw is None:
                return
            data = extract_json(raw)
            if isinstance(data, dict) and data.get("status") == "input_required":
                for field in data["missing_fields"]:
                    if field in prompts:
                        label, cast = prompts[field]
                        arguments[field] = ask(label, cast)
                    else:
                        arguments[field] = ask(f"Enter {field}: ")
                continue
            pretty(raw)
            return

    # ---------------- Menu actions ----------------

    async def view_medicines(self):
        raw = await self.call_tool("get_medicines", {"employee_id": self.employee_id})
        if raw:
            pretty(raw)

    async def search_medicine(self):
        medicine_id = ask("Enter Medicine ID: ", int)
        raw = await self.call_tool(
            "get_medicine", {"employee_id": self.employee_id, "medicine_id": medicine_id}
        )
        if raw:
            pretty(raw)

    async def create_order(self):
        args = {"employee_id": self.employee_id}
        prompts = {
            "medicine_id": ("Enter Medicine ID: ", int),
            "supplier_id": ("Enter Supplier ID: ", int),
            "planned_quantity": ("Enter Planned Quantity: ", int),
        }
        for field, (label, cast) in prompts.items():
            args[field] = ask(label, cast)
        await self.call_tool_with_elicitation("create_order", args, prompts)

    async def view_batches(self):
        raw = await self.call_tool("get_batches", {"employee_id": self.employee_id})
        if raw:
            pretty(raw)

    async def update_batch_status(self):
        batch_id = ask("Enter Batch ID: ", int)
        print("Valid statuses: In Production, Pending QA, Approved, Rejected, Distributed, Recalled")
        new_status = ask("Enter new status: ")
        raw = await self.call_tool(
            "change_batch_status",
            {"employee_id": self.employee_id, "batch_id": batch_id, "new_status": new_status},
        )
        if raw:
            pretty(raw)

    async def record_quality_test(self):
        args = {"employee_id": self.employee_id}
        prompts = {
            "batch_id": ("Enter Batch ID: ", int),
            "test_type": ("Enter Test Type (e.g. Assay Test): ", str),
            "test_result": ("Enter Test Result (Pass/Fail): ", str),
            "remarks": ("Enter Remarks: ", str),
        }
        for field, (label, cast) in prompts.items():
            args[field] = ask(label, cast)
        await self.call_tool_with_elicitation("add_quality_test", args, prompts)

    async def view_quality_tests(self):
        raw = await self.call_tool("get_quality_tests", {"employee_id": self.employee_id})
        if raw:
            pretty(raw)

    async def create_recall(self):
        args = {"employee_id": self.employee_id}
        prompts = {
            "batch_id": ("Enter Batch ID: ", int),
            "recall_reason": ("Enter Recall Reason: ", str),
        }
        for field, (label, cast) in prompts.items():
            args[field] = ask(label, cast)
        await self.call_tool_with_elicitation("create_recall", args, prompts)

    async def view_recalls(self):
        raw = await self.call_tool("get_recalls", {"employee_id": self.employee_id})
        if raw:
            pretty(raw)

    async def read_policies(self):
        print("\nAvailable policies:")
        for key, (_, title) in RESOURCE_MENU.items():
            print(f"  {key}. {title}")
        choice = input("Choose a policy: ").strip()
        entry = RESOURCE_MENU.get(choice)
        if not entry:
            print("  Invalid choice.")
            return
        uri, title = entry
        result = await self.session.read_resource(uri)
        print(f"\n--- {title} ---\n")
        for content in result.contents:
            if hasattr(content, "text"):
                print(content.text)
        print()

    async def run_menu(self):
        actions = {
            "1": self.view_medicines,
            "2": self.search_medicine,
            "3": self.create_order,
            "4": self.view_batches,
            "5": self.update_batch_status,
            "6": self.record_quality_test,
            "7": self.view_quality_tests,
            "8": self.create_recall,
            "9": self.view_recalls,
            "10": self.read_policies,
        }
        while True:
            print_menu()
            choice = input("Choose: ").strip()
            if choice == "11":
                print("\nGoodbye.")
                return
            action = actions.get(choice)
            if action is None:
                print("  Invalid choice.\n")
                continue
            try:
                await action()
            except Exception as exc:
                print(f"\n[Unexpected error] {exc}")
            print()


def extract_json(raw):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def main():
    banner()
    print("Connecting to MCP server...")

    server_params = StdioServerParameters(command=SERVER_COMMAND, args=SERVER_ARGS)

    async with AsyncExitStack() as stack:
        read_stream, write_stream = await stack.enter_async_context(stdio_client(server_params))
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        print("✓ Connected\n")

        tools_result = await session.list_tools()
        print("Available tools discovered:")
        for i, tool in enumerate(tools_result.tools, start=1):
            print(f"{i}. {tool.name}")
        print("\n=========================================")

        client = VelloraClient(session)
        await client.login()
        await client.run_menu()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye.")
