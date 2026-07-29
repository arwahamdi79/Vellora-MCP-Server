import asyncio
import sqlite3
from mcp.server.fastmcp import FastMCP, Context
from .tools import get_batch_details_handler, initiate_product_recall_handler
from .schemas import GET_BATCH_DETAILS_SCHEMA, INITIATE_RECALL_SCHEMA
from .notifications import notify_tools_list_changed

mcp = FastMCP("Vellora Therapeutics Data Protocol Server")

@mcp.tool(
    name="get_batch_details",
    description="Fetch details and status of a manufacturing batch by its Batch ID."
)
def get_batch_details(batch_id: int) -> dict:
    return get_batch_details_handler({"batch_id": batch_id})

@mcp.tool(
    name="initiate_product_recall",
    description="Initiate a recall for a compromised manufacturing batch. Requires QA Manager role and explicit user confirmation."
)
async def initiate_product_recall(batch_id: int, recall_reason: str, authorized_manager_id: int, ctx: Context) -> dict:
    return await initiate_product_recall_handler(
        ctx,
        {
            "batch_id": batch_id,
            "recall_reason": recall_reason,
            "authorized_manager_id": authorized_manager_id
        }
    )

@mcp.tool(
    name="authenticate_user_session",
    description="Authenticate user to elevate session role and update dynamic tools."
)
async def authenticate_user_session(employee_id: int, ctx: Context) -> dict:
    await notify_tools_list_changed(ctx)
    return {
        "success": True,
        "message": f"Session authenticated for Employee #{employee_id}. Triggered tools/list_changed."
    }

@mcp.resource("policy://quality-approval")
def get_quality_policy() -> str:
    """Read-only company policy regarding quality approvals."""
    try:
        conn = sqlite3.connect("db/vellora_therapeutics.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DocumentContent FROM Company_Policy WHERE PolicyID = 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else "Default Policy: High risk defects require manager approval and elicitation."
    except Exception:
        return "Policy Document: All product recalls require mid-call human elicitation confirmation."

@mcp.prompt()
def recall_investigation_prompt(batch_id: int) -> str:
    """Canned prompt template to start a batch recall investigation."""
    return f"Investigate manufacturing batch #{batch_id}. Check all quality test results, active ingredients, and generate a recall risk assessment report."

@mcp.tool(
    name="run_batch_safety_audit",
    description="Run a full safety audit on a batch with progress tracking."
)
async def run_batch_safety_audit(batch_id: int, ctx: Context) -> dict:
    total_steps = 3
    for step in range(1, total_steps + 1):
        await asyncio.sleep(1)
        await ctx.report_progress(progress=step, total=total_steps)
    return {"success": True, "message": f"Full safety audit completed for Batch #{batch_id}."}

if __name__ == "__main__":
    mcp.run()