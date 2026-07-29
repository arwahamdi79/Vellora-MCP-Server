import sqlite3
from mcp.server.fastmcp import Context
from mcp.types import SamplingMessage, TextContent
from .schemas import GET_BATCH_DETAILS_SCHEMA, INITIATE_RECALL_SCHEMA
from .validation import validate_tool_args
from .authorization import verify_employee_permissions
from .elicitation import request_human_confirmation

DB_PATH = "db/vellora_therapeutics.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_batch_details_handler(payload: dict) -> dict:
    is_valid, error_msg = validate_tool_args(payload, GET_BATCH_DETAILS_SCHEMA)
    if not is_valid:
        return {"error": error_msg}

    batch_id = payload["batch_id"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM Manufacturing_Batch WHERE BatchID = ?",
        (batch_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"error": f"Batch ID {batch_id} not found."}

    return dict(row)


async def initiate_product_recall_handler(ctx: Context, payload: dict) -> dict:
    is_valid, error_msg = validate_tool_args(payload, INITIATE_RECALL_SCHEMA)

    if not is_valid:
        return {"success": False, "message": error_msg}

    batch_id = payload["batch_id"]
    recall_reason = payload["recall_reason"]
    manager_id = payload["authorized_manager_id"]

    is_authorized, auth_msg = verify_employee_permissions(
        db_path=DB_PATH,
        employee_id=manager_id,
        allowed_roles=["QA Manager", "Operations Manager"]
    )

    if not is_authorized:
        return {"success": False, "message": auth_msg}

    action_desc = f"Initiate product recall for Batch #{batch_id}. Reason: {recall_reason}"

    confirmed = await request_human_confirmation(ctx, action_desc)

    if not confirmed:
        return {
            "success": False,
            "message": f"Recall operation for Batch #{batch_id} was cancelled by user."
        }

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE Manufacturing_Batch
        SET BatchStatus = 'Recalled'
        WHERE BatchID = ?
        """,
        (batch_id,)
    )

    cursor.execute(
        """
        INSERT INTO Product_Recall
        (BatchID, RecallReason, RecallStatus, AuthorizedManagerID)
        VALUES (?, ?, 'Initiated', ?)
        """,
        (
            batch_id,
            recall_reason,
            manager_id
        )
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": f"Batch #{batch_id} has been officially RECALLED."
    }


async def analyze_batch_discrepancy_with_sampling_handler(batch_id: int, ctx: Context) -> str:
    batch_info = get_batch_details_handler({"batch_id": batch_id})

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
                    content=TextContent(
                        type="text",
                        text=prompt_text
                    )
                )
            ],
            max_tokens=150
        )

        if hasattr(sampling_response.content, "text"):
            analysis_text = sampling_response.content.text
        elif isinstance(sampling_response.content, list) and len(sampling_response.content) > 0:
            analysis_text = sampling_response.content[0].text
        else:
            analysis_text = str(sampling_response.content)

        return f"Sampling Analysis Result:\n{analysis_text}"

    except Exception as e:
        return f"Client does not support sampling/createMessage: {str(e)}"