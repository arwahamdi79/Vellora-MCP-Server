import sqlite3
from .schemas import INITIATE_RECALL_SCHEMA, GET_BATCH_DETAILS_SCHEMA
from .authorization import verify_employee_permissions
from .validation import validate_tool_args
from .elicitation import request_human_confirmation

DB_PATH = "db/vellora_therapeutics.db"

def get_batch_details_handler(arguments: dict) -> dict:
    is_valid, val_msg = validate_tool_args(arguments, GET_BATCH_DETAILS_SCHEMA)
    if not is_valid:
        return {"success": False, "error": val_msg}

    batch_id = arguments["batch_id"]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT b.BatchID, m.MedicineName, b.BatchStatus, b.ManufacturingDate, b.ExpiryDate, b.CurrentLocation
            FROM Manufacturing_Batch b
            JOIN Medicine m ON b.MedicineID = m.MedicineID
            WHERE b.BatchID = ?
            """,
            (batch_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"success": False, "error": f"Batch ID #{batch_id} not found."}

        return {
            "success": True,
            "data": {
                "batch_id": row[0],
                "medicine_name": row[1],
                "status": row[2],
                "manufacturing_date": row[3],
                "expiry_date": row[4],
                "location": row[5]
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

async def initiate_product_recall_handler(ctx, arguments: dict) -> dict:

    is_valid, val_msg = validate_tool_args(arguments, INITIATE_RECALL_SCHEMA)
    if not is_valid:
        return {"success": False, "error": val_msg}

    batch_id = arguments["batch_id"]
    reason = arguments["recall_reason"]
    manager_id = arguments["authorized_manager_id"]

    is_authorized, auth_msg = verify_employee_permissions(
        DB_PATH, manager_id, allowed_roles=["QA Manager", "Operations Manager"]
    )
    if not is_authorized:
        return {"success": False, "error": auth_msg}

    confirmed = await request_human_confirmation(
        ctx,
        f"Initiate Product Recall for Batch #{batch_id} (Manager ID: {manager_id}). Reason: {reason}"
    )
    if not confirmed:
        return {"success": False, "message": "Product recall operation aborted by user during elicitation."}

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO Product_Recall (BatchID, RecallReason, AuthorizedManagerID) VALUES (?, ?, ?)",
            (batch_id, reason, manager_id)
        )
        cursor.execute(
            "UPDATE Manufacturing_Batch SET BatchStatus = 'Recalled' WHERE BatchID = ?",
            (batch_id,)
        )
        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": f"Product Recall initiated successfully for Batch #{batch_id}."
        }
    except Exception as e:
        return {"success": False, "error": f"Database transaction failed: {str(e)}"}