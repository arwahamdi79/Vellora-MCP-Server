import sqlite3

def verify_employee_permissions(db_path: str, employee_id: int, allowed_roles: list[str]) -> tuple[bool, str]:
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT Role, AccountStatus FROM Employee WHERE EmployeeID = ?", 
            (employee_id,)
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            return False, f"Employee ID {employee_id} does not exist."

        role, status = result

        if status != 'Active':
            return False, f"Account for employee ID {employee_id} is Inactive."

        if role not in allowed_roles:
            return False, f"Permission Denied: Role '{role}' cannot perform this action. Required: {allowed_roles}"

        return True, "Authorized"

    except Exception as e:
        return False, f"Database error during authorization check: {str(e)}"