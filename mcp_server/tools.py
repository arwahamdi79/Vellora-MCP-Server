from pathlib import Path

from .server import mcp

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

from .validation import (
    validate_exists,
    validate_positive_integer,
    validate_choice,
)

from .elicitation import create_elicitation_request

from .notifications import (
    production_order_created,
    batch_status_changed,
    quality_test_recorded,
    recall_created,
)


DB_PATH = Path(__file__).parent.parent / "db" / "vellora.db"


# ==================================================
# Medicines (READ ONLY)
# ==================================================

@mcp.tool()
def get_medicines(employee_id: int):
    """
    Retrieve all medicines available in company database.
    """

    authorize(
        DB_PATH,
        employee_id,
        "get_medicines"
    )

    return get_all_medicines()



@mcp.tool()
def get_medicine(
    employee_id: int,
    medicine_id: int
):
    """
    Retrieve medicine details by ID.
    """

    authorize(
        DB_PATH,
        employee_id,
        "get_medicine"
    )

    validate_exists(
        "Medicine",
        "MedicineID",
        medicine_id
    )

    return get_medicine_by_id(medicine_id)



# ==================================================
# Production Orders (WRITE)
# ==================================================

@mcp.tool()
def create_order(
    employee_id: int,
    medicine_id: int,
    supplier_id: int,
    planned_quantity: int,
):
    """
    Create a new pharmaceutical production order.
    """

    authorize(
        DB_PATH,
        employee_id,
        "create_order"
    )


    validate_exists(
        "Employee",
        "EmployeeID",
        employee_id
    )


    validate_exists(
        "Medicine",
        "MedicineID",
        medicine_id
    )


    validate_exists(
        "Supplier",
        "SupplierID",
        supplier_id
    )


    validate_positive_integer(
        planned_quantity,
        "planned_quantity"
    )


    result = create_production_order(
        medicine_id,
        supplier_id,
        planned_quantity,
        employee_id
    )


    return {

        "result": result,

        "notification":
            production_order_created(
                result["ProductionOrderID"]
            )
    }



# ==================================================
# Manufacturing Batches
# ==================================================

@mcp.tool()
def get_batches(
    employee_id: int
):
    """
    Retrieve manufacturing batches.
    """

    authorize(
        DB_PATH,
        employee_id,
        "get_batches"
    )

    return list_batches()



@mcp.tool()
def change_batch_status(
    employee_id: int,
    batch_id: int,
    new_status: str,
):
    """
    Change manufacturing batch status.

    Only authorized employees can modify
    production states.
    """


    authorize(
        DB_PATH,
        employee_id,
        "change_batch_status"
    )


    validate_exists(
        "Manufacturing_Batch",
        "BatchID",
        batch_id
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
        "new_status"
    )


    result = update_batch_status(
        batch_id,
        new_status
    )


    return {

        "result": result,

        "notification":
            batch_status_changed(
                batch_id,
                new_status
            )
    }



# ==================================================
# Quality Tests
# ==================================================

@mcp.tool()
def add_quality_test(
    employee_id: int,
    batch_id: int,
    test_type: str,
    test_result: str,
    remarks: str,
):
    """
    Add quality inspection result.
    """


    authorize(
        DB_PATH,
        employee_id,
        "add_quality_test"
    )


    validate_exists(
        "Employee",
        "EmployeeID",
        employee_id
    )


    validate_exists(
        "Manufacturing_Batch",
        "BatchID",
        batch_id
    )


    validate_choice(
        test_result,
        [
            "Pass",
            "Fail"
        ],
        "test_result"
    )


    result = record_quality_test(
        batch_id,
        test_type,
        test_result,
        employee_id,
        remarks
    )


    return {

        "result": result,

        "notification":
            quality_test_recorded(
                batch_id,
                test_result
            )

    }



@mcp.tool()
def get_quality_tests(
    employee_id: int
):
    """
    Retrieve quality test records.
    """

    authorize(
        DB_PATH,
        employee_id,
        "get_quality_tests"
    )

    return list_quality_tests()



# ==================================================
# Product Recall (HIGH RISK WRITE)
# ==================================================

@mcp.tool()
def create_recall(
    employee_id: int,
    batch_id: int,
    recall_reason: str,
):
    """
    Create product recall.

    Requires human approval before execution.
    """

    authorize(
        DB_PATH,
        employee_id,
        "create_recall"
    )


    validate_exists(
        "Manufacturing_Batch",
        "BatchID",
        batch_id
    )


    approval = create_elicitation_request(
        action="create_product_recall",
        details={
            "batch_id": batch_id,
            "reason": recall_reason
        }
    )


    return {

        "status": "human_confirmation_required",

        "elicitation": approval
    }



# ==================================================
# Recalls
# ==================================================

@mcp.tool()
def get_recalls(
    employee_id: int
):
    """
    Retrieve product recalls.
    """

    authorize(
        DB_PATH,
        employee_id,
        "get_recalls"
    )


    return list_recalls()



# ==================================================
# Employees
# ==================================================

@mcp.tool()
def employee(
    employee_id: int
):
    """
    Get employee information.
    """

    return get_employee(employee_id)