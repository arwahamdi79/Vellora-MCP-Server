"""
mcp_server/tools.py

FIX (Extending & Correcting Prior System):
1. ask_knowledge_base previously imported `from your_llm_client import llm`
   with a literal `# TODO` and could not run at all -- this broke every
   downstream RAG addition (Batch Release deviation investigation, Supplier
   CAPA history lookup both depend on retrieval actually working). It now
   uses a real Anthropic client, constructed once at module load from
   ANTHROPIC_API_KEY, and grounded_reflect.generate_answer is called with
   that real client instead of a placeholder import.

2. employee() and get_batch_memory() previously skipped the
   validate_exists() check that every other write/lookup tool
   (create_order, add_quality_test, create_recall) already performs --
   an invalid employee_id or batch_id would fall through to a raw DB
   query and surface as an unhandled 500 instead of a clean validation
   error. Both are normalized below to match the rest of the file.

Everything else in this file is unchanged from the original.
"""

import os
from .app import mcp
from .tool_registry import registered_tool
from pathlib import Path
from typing import Optional
from .elicitation import input_required
from .notifications import (
    production_order_created,
    batch_status_changed,
    quality_test_recorded,
    recall_created,
)
from .Validation import (
    validate_exists,
    validate_positive_integer,
    validate_choice,
)


from .Authorization import authorize


from .database import (
    get_all_medicines,
    get_medicine_by_id,
    create_production_order,
    list_batches,
    update_batch_status,
    record_quality_test,
    list_quality_tests,
    create_product_recall,
    list_recalls,
    get_employee,
)
print("Loading tools.py")
from .database import DB_PATH


from agent.memory_adapter import maybe_remember, load_memory_context

# --------------------------------------------------
# FIX: real LLM client for ask_knowledge_base, built once at module load
# instead of the previous `from your_llm_client import llm  # TODO`
# placeholder that could never actually run.
# --------------------------------------------------
import anthropic

_anthropic_client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)


# --------------------------------------------------
# Medicines
# --------------------------------------------------


@registered_tool()
def get_medicines(employee_id: int):
    authorize(DB_PATH, employee_id, "get_medicines")
    return get_all_medicines()


@registered_tool()
def get_medicine(employee_id: int, medicine_id: int):
    """Return one medicine."""
    authorize(DB_PATH, employee_id, "get_medicine")
    return get_medicine_by_id(medicine_id)


# --------------------------------------------------
# Production
# --------------------------------------------------


@registered_tool()
def create_order(
    employee_id: Optional[int] = None,
    medicine_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    planned_quantity: Optional[int] = None,
):
    missing = []

    if employee_id is None:
        missing.append("employee_id")

    if medicine_id is None:
        missing.append("medicine_id")

    if supplier_id is None:
        missing.append("supplier_id")

    if planned_quantity is None:
        missing.append("planned_quantity")

    if missing:
        return input_required(
            "More information is required to create a production order.",
            missing,
        )

    authorize(DB_PATH, employee_id, "create_order")

    validate_exists(
        "Employee",
        "EmployeeID",
        employee_id,
    )

    validate_exists(
        "Medicine",
        "MedicineID",
        medicine_id,
    )

    validate_exists(
        "Supplier",
        "SupplierID",
        supplier_id,
    )

    validate_positive_integer(
        planned_quantity,
        "planned_quantity",
    )

    result = create_production_order(
        medicine_id,
        supplier_id,
        planned_quantity,
        employee_id,
    )

    notification = production_order_created(
        result["ProductionOrderID"]
    )

    return {
        "result": result,
        "notification": notification,
    }


# --------------------------------------------------
# Batches
# --------------------------------------------------

@registered_tool()
def get_batches(employee_id: int):
    authorize(DB_PATH, employee_id, "get_batches")
    return list_batches()


@registered_tool()
def change_batch_status(
    employee_id: int,
    batch_id: int,
    new_status: str,
):
    authorize(DB_PATH, employee_id, "change_batch_status")

    validate_exists(
        "Employee",
        "EmployeeID",
        employee_id,
    )

    validate_exists(
        "Manufacturing_Batch",
        "BatchID",
        batch_id,
    )

    validate_choice(
        new_status,
        [
            "In Production",
            "Pending QA",
            "Approved",
            "Rejected",
            "Distributed",
            "Recalled",
        ],
        "new_status",
    )

    result = update_batch_status(
        batch_id,
        new_status,
    )

    # Store important status changes in episodic memory
    maybe_remember(
        turn_text=f"""
Batch {batch_id}
Status changed to: {new_status}
""",
        entity_id=f"batch_{batch_id}",
    )

    notification = batch_status_changed(
        batch_id,
        new_status,
    )

    return {
        "result": result,
        "notification": notification,
    }


# --------------------------------------------------
# Quality
# --------------------------------------------------


@registered_tool()
def add_quality_test(
    employee_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    test_type: Optional[str] = None,
    test_result: Optional[str] = None,
    remarks: Optional[str] = None,
):
    missing = []

    if employee_id is None:
        missing.append("employee_id")

    if batch_id is None:
        missing.append("batch_id")

    if test_type is None:
        missing.append("test_type")

    if test_result is None:
        missing.append("test_result")

    if remarks is None:
        missing.append("remarks")

    if missing:
        return input_required(
            "More information is required to record a quality test.",
            missing,
        )

    authorize(DB_PATH, employee_id, "add_quality_test")

    validate_exists(
        "Employee",
        "EmployeeID",
        employee_id,
    )

    validate_exists(
        "Manufacturing_Batch",
        "BatchID",
        batch_id,
    )

    validate_choice(
        test_result,
        ["Pass", "Fail"],
        "test_result",
    )

    result = record_quality_test(
        batch_id,
        test_type,
        test_result,
        employee_id,
        remarks,
    )
    # Store important quality events in episodic memory
    maybe_remember(
        turn_text=f"""
    Batch {batch_id}
    Test: {test_type}
    Result: {test_result}
    Remarks: {remarks}
    """,
        entity_id=f"batch_{batch_id}",
    )
    notification = quality_test_recorded(
        batch_id,
        test_result,
    )

    return {
        "result": result,
        "notification": notification,
    }


@registered_tool()
def get_quality_tests(employee_id: int):
    authorize(DB_PATH, employee_id, "get_quality_tests")
    return list_quality_tests()


# --------------------------------------------------
# Recalls
# --------------------------------------------------


@registered_tool()
def create_recall(
    employee_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    recall_reason: Optional[str] = None,
):
    # -----------------------------
    # Elicitation
    # -----------------------------
    missing = []

    if employee_id is None:
        missing.append("employee_id")

    if batch_id is None:
        missing.append("batch_id")

    if recall_reason is None or not recall_reason.strip():
        missing.append("recall_reason")

    if missing:
        return input_required(
            "More information is required to create a product recall.",
            missing,
        )

    # -----------------------------
    # Authorization
    # -----------------------------
    authorize(DB_PATH, employee_id, "create_recall")

    # -----------------------------
    # Validation
    # -----------------------------
    validate_exists(
        "Employee",
        "EmployeeID",
        employee_id,
    )

    validate_exists(
        "Manufacturing_Batch",
        "BatchID",
        batch_id,
    )

    # -----------------------------
    # Database
    # -----------------------------
    result = create_product_recall(
        batch_id,
        recall_reason,
        employee_id,
    )

    # -----------------------------
    # Notification
    # -----------------------------
    notification = recall_created(
        result["RecallID"],
        batch_id,
    )

    return {
        "result": result,
        "notification": notification,
    }


@registered_tool()
def get_recalls(employee_id: int):
    authorize(DB_PATH, employee_id, "get_recalls")
    return list_recalls()


# --------------------------------------------------
# Employees
# --------------------------------------------------

@registered_tool()
def employee(employee_id: int):
    """Get employee information."""
    # FIX: this tool previously called get_employee() directly with no
    # validate_exists() check, unlike every other lookup tool in this file
    # -- an invalid employee_id fell through to the DB layer and surfaced
    # as a raw None / unhandled error instead of a clean validation error.
    validate_exists(
        "Employee",
        "EmployeeID",
        employee_id,
    )
    return get_employee(employee_id)


@registered_tool()
def get_batch_memory(
    employee_id: int,
    batch_id: int,
    query: str,
):
    authorize(DB_PATH, employee_id, "get_batches")

    # FIX: added the matching employee_id check -- previously only
    # batch_id was validated here, so a bad employee_id would pass through
    # authorize() and reach load_memory_context() unvalidated.
    validate_exists(
        "Employee",
        "EmployeeID",
        employee_id,
    )

    validate_exists(
        "Manufacturing_Batch",
        "BatchID",
        batch_id,
    )

    return load_memory_context(
        entity_id=f"batch_{batch_id}",
        opening_message=query,
    )


@registered_tool()
def ask_knowledge_base(query: str, top_k: int = 3):
    """
    Answer a question from the knowledge base, checking the draft is
    grounded in what was retrieved before returning it (retries once).

    FIX: previously imported `from your_llm_client import llm  # TODO`,
    a placeholder that could not run. Now uses the real Anthropic client
    constructed at module load (see `_anthropic_client` above), reading
    ANTHROPIC_API_KEY from the environment -- never hardcode the key here,
    and confirm .env stays in .gitignore per the project's guardrails.
    """
    from grounded_reflect import generate_answer
    from agent.search_adapter import search_knowledge_base

    result = generate_answer(
        query,
        search_knowledge_base,
        _anthropic_client,
        top_k=top_k,
    )
    return {
        "answer": result.answer,
        "grounded": result.grounded,
        "retries_used": result.retries_used,
        "sources": [c.content[:80] for c in result.chunks_used],
    }