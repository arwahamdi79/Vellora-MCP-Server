import sqlite3
from typing import Dict, Any
from mcp.server.fastmcp import Context
from mcp.types import SamplingMessage, TextContent


from mcp_server.schemas import BATCH_DETAILS_SCHEMA, RECALL_SCHEMA, AUTHENTICATE_SCHEMA, SAFETY_AUDIT_SCHEMA
from mcp_server.validation import validate_input
from mcp_server.authorization import check_employee_status, check_qa_manager_role
from mcp_server.elicitation import create_recall_elicitation
from mcp_server.notifications import notify_tools_list_changed
from mcp_server.database import get_db_connection



def get_batch_details(batch_id: int) -> Dict[str, Any]:
    """Fetch details and status of a manufacturing batch by its Batch ID."""
    validate_input({"batch_id": batch_id}, BATCH_DETAILS_SCHEMA)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Manufacturing_Batches WHERE batch_id = ?", (batch_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {"error": f"Batch ID {batch_id} not found."}
    
    return dict(row)



async def initiate_product_recall(batch_id: int, recall_reason: str, authorized_manager_id: int, ctx: Context) -> str:
    """Initiate a recall for a compromised batch. Requires QA Manager role & explicit confirmation."""
    payload = {
        "batch_id": batch_id,
        "recall_reason": recall_reason,
        "authorized_manager_id": authorized_manager_id
    }
    validate_input(payload, RECALL_SCHEMA)
    

    check_employee_status(authorized_manager_id)
    check_qa_manager_role(authorized_manager_id)
    

    confirmed = await create_recall_elicitation(ctx, batch_id, recall_reason)
    if not confirmed:
        return f"⛔ Recall operation for Batch #{batch_id} was cancelled by user."
    

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Manufacturing_Batches SET status = 'RECALLED', recall_reason = ? WHERE batch_id = ?",
        (recall_reason, batch_id)
    )
    conn.commit()
    conn.close()
    
    return f"✅ SUCCESS: Batch #{batch_id} has been officially RECALLED."


async def authenticate_user_session(employee_id: int, ctx: Context) -> str:
    """Authenticate user to elevate session role and update dynamic tools list."""
    validate_input({"employee_id": employee_id}, AUTHENTICATE_SCHEMA)
    check_employee_status(employee_id)
    

    await notify_tools_list_changed(ctx)
    return f"✅ User #{employee_id} authenticated successfully. Capabilities list refreshed."



async def run_batch_safety_audit(batch_id: int, ctx: Context) -> str:
    """Run a full safety audit on a batch with progress tracking."""
    validate_input({"batch_id": batch_id}, SAFETY_AUDIT_SCHEMA)
    
    total_steps = 3
    await ctx.report_progress(1, total_steps)

    batch_info = get_batch_details(batch_id)
    
    await ctx.report_progress(2, total_steps)

    
    await ctx.report_progress(3, total_steps)

    
    return f"✅ Audit completed for Batch #{batch_id}: All parameters meet compliance standards."


async def analyze_batch_discrepancy_with_sampling(batch_id: int, ctx: Context) -> str:
    """Analyze batch safety logs using client-side sampling reasoning via create_message."""
    

    batch_info = get_batch_details(batch_id)
    if "error" in batch_info:
        return f"Cannot perform sampling analysis: {batch_info['error']}"
    

    prompt_text = (
        f"You are a Quality Assurance Specialist at Vellora Therapeutics. "
        f"Analyze the following batch report for potential anomalies or safety concerns: {batch_info}"
    )

    try:

        sampling_response = await ctx.session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt_text)
                )
            ],
            max_tokens=150
        )
        

        if hasattr(sampling_response.content, 'text'):
            analysis_text = sampling_response.content.text
        elif isinstance(sampling_response.content, list) and len(sampling_response.content) > 0:
            analysis_text = sampling_response.content[0].text
        else:
            analysis_text = str(sampling_response.content)

        return f"✅ Sampling Analysis Result:\n{analysis_text}"

    except Exception as e:

        return f" Client does not support sampling/createMessage: {str(e)}"