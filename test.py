from mcp_server.database import get_all_medicines


medicines = get_all_medicines()

print(medicines)


from pathlib import Path
from mcp_server.Authorization import authorize


DB_PATH = Path("db/vellora.db")


# Try a valid employee
try:
    role = authorize(
        DB_PATH,
        1,
        "get_medicines"
    )

    print("Access granted:", role)


except Exception as e:
    print("Denied:", e)



try:
    authorize(
        DB_PATH,
        1,
        "create_order"
    )

    print("Allowed")

except Exception as e:
    print("Denied:", e)



from mcp_server.tools import get_medicines


result = get_medicines(1)

print(result)
from mcp_server.database import get_connection

conn = get_connection()

employees = conn.execute("""
    SELECT EmployeeID, FullName, Role, AccountStatus
    FROM Employee
""").fetchall()

for emp in employees:
    print(dict(emp))

conn.close()
from mcp_server.tools import get_medicines, create_order, add_quality_test



# Test allowed access
print(get_medicines(1))


# Test create order permission
result = add_quality_test(
    employee_id=4,
    batch_id=1,
    test_type="Chemical Analysis",
    test_result="Pass",
    remarks="OK"
)

print(result)

