import sqlite3

# ==========================================================
# Role-Based Access Control (RBAC)
# ==========================================================

ROLE_PERMISSIONS = {
    "Researcher": [
        "get_medicines",
        "get_medicine",
    ],

    "Production Staff": [
        "create_order",
        "get_batches",
    ],

    "QA Staff": [
        "get_batches",
        "add_quality_test",
        "get_quality_tests",
    ],

    "QA Manager": [
        "change_batch_status",
        "get_batches",
        "get_quality_tests",
    ],

    "Operations Manager": [
        "create_recall",
        "get_recalls",
    ]
}


# ==========================================================
# Authorization Function
# ==========================================================

def authorize(db_path: str, employee_id: int, tool_name: str):
    """
    Checks whether an employee is allowed to use an MCP tool.

    Raises:
        PermissionError
        ValueError
    Returns:
        Employee role (str)
    """

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT EmployeeID,
                       FullName,
                       Role,
                       AccountStatus
                FROM Employee
                WHERE EmployeeID = ?
            """, (employee_id,))

            employee = cursor.fetchone()

    except sqlite3.Error as e:
        raise RuntimeError(f"Database error: {e}")

    # -------------------------------------------------------

    if employee is None:
        raise ValueError(
            f"Employee ID {employee_id} does not exist."
        )

    # -------------------------------------------------------

    if employee["AccountStatus"] != "Active":
        raise PermissionError(
            f"Employee '{employee['FullName']}' is inactive."
        )

    # -------------------------------------------------------

    role = employee["Role"]

    allowed_tools = ROLE_PERMISSIONS.get(role)

    if allowed_tools is None:
        raise PermissionError(
            f"Unknown role '{role}'."
        )

    # -------------------------------------------------------

    if tool_name not in allowed_tools:
        raise PermissionError(
            f"{role} is not allowed to use '{tool_name}'."
        )

    # -------------------------------------------------------

    return role