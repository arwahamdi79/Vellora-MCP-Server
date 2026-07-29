from pathlib import Path

from mcp.server.fastmcp import FastMCP

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
DB_PATH = Path(__file__).parent.parent / "db" / "vellora.db"
mcp = FastMCP("Vellora MCP")


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
    employee_id: int,
    medicine_id: int,
    supplier_id: int,
    planned_quantity: int,
):
    authorize(DB_PATH, employee_id, "create_order")

    return create_production_order(
        medicine_id,
        supplier_id,
        planned_quantity,
        employee_id,
    )

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

    return update_batch_status(
        batch_id,
        new_status,
    )


# --------------------------------------------------
# Quality
# --------------------------------------------------

@mcp.tool()
def add_quality_test(
    employee_id: int,
    batch_id: int,
    test_type: str,
    test_result: str,
    remarks: str,
):
    authorize(DB_PATH, employee_id, "add_quality_test")

    return record_quality_test(
        batch_id,
        test_type,
        test_result,
        employee_id,
        remarks,
    )
@mcp.tool()
def get_quality_tests(employee_id: int):
    authorize(DB_PATH, employee_id, "get_quality_tests")
    return list_quality_tests()


# --------------------------------------------------
# Recalls
# --------------------------------------------------

@mcp.tool()
def create_recall(
    employee_id: int,
    batch_id: int,
    recall_reason: str,
):
    authorize(DB_PATH, employee_id, "create_recall")

    return create_product_recall(
        batch_id,
        recall_reason,
        employee_id,
    )


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