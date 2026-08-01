from .app import mcp
from pathlib import Path
from typing import Optional
from .elicitation import input_required
from .notifications import (
    production_order_created,
    batch_status_changed,
    quality_test_recorded,
    recall_created,
)
from .validation import (
    validate_exists,
    validate_positive_integer,
    validate_choice,
)


from .authorization import authorize


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
DB_PATH = Path(__file__).parent.parent / "db" / "vellora.db"



# --------------------------------------------------
# Medicines
# --------------------------------------------------


@mcp.tool()
def get_medicines(employee_id: int):
    authorize(DB_PATH, employee_id, "get_medicines")
    return get_all_medicines()


@mcp.tool()

def get_medicine(employee_id: int, medicine_id: int):
    """Return one medicine."""
    authorize(DB_PATH, employee_id, "get_medicine")
    return get_medicine_by_id(medicine_id)


# --------------------------------------------------
# Production
# --------------------------------------------------


@mcp.tool()
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

@mcp.tool()
def get_batches(employee_id: int):
    authorize(DB_PATH, employee_id, "get_batches")
    return list_batches()


@mcp.tool()
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

    result = update_batch_status(batch_id, new_status)

    notification = batch_status_changed(batch_id, new_status)

    return {
        "result": result,
        "notification": notification,
    }


# --------------------------------------------------
# Quality
# --------------------------------------------------


@mcp.tool()
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

    notification = quality_test_recorded(
        batch_id,
        test_result,
    )

    return {
        "result": result,
        "notification": notification,
    }

@mcp.tool()
def get_quality_tests(employee_id: int):
    authorize(DB_PATH, employee_id, "get_quality_tests")
    return list_quality_tests()


# --------------------------------------------------
# Recalls
# --------------------------------------------------



@mcp.tool()
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

@mcp.tool()
def get_recalls(employee_id: int):

    authorize(DB_PATH, employee_id, "get_recalls")

    return list_recalls()


# --------------------------------------------------
# Employees
# --------------------------------------------------

@mcp.tool()
def employee(employee_id: int):
    """Get employee information."""
    return get_employee(employee_id)