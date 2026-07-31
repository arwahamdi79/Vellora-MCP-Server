from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).resolve().parent.parent / "db" / "vellora_therapeutics.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# Medicines
# =====================================================

def get_all_medicines():
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT *
            FROM Medicine
            ORDER BY MedicineName
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_medicine_by_id(medicine_id):
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT *
            FROM Medicine
            WHERE MedicineID = ?
        """, (medicine_id,))

        row = cursor.fetchone()

        return dict(row) if row else None


# =====================================================
# Production Orders
# =====================================================

def create_production_order(
    medicine_id,
    supplier_id,
    planned_quantity,
    responsible_employee_id
):

    with get_connection() as conn:

        cursor = conn.execute("""
            INSERT INTO Production_Order
            (
                MedicineID,
                SupplierID,
                PlannedQuantity,
                ResponsibleEmployeeID
            )
            VALUES (?, ?, ?, ?)
        """,
        (
            medicine_id,
            supplier_id,
            planned_quantity,
            responsible_employee_id
        ))

        conn.commit()

        return {
            "ProductionOrderID": cursor.lastrowid,
            "message": "Production order created successfully."
        }



# =====================================================
# Manufacturing Batches
# =====================================================

def list_batches():

    with get_connection() as conn:

        cursor = conn.execute("""
            SELECT *
            FROM Manufacturing_Batch
            ORDER BY BatchID DESC
        """)

        return [
            dict(row)
            for row in cursor.fetchall()
        ]



def update_batch_status(batch_id, new_status):

    with get_connection() as conn:

        conn.execute("""
            UPDATE Manufacturing_Batch
            SET BatchStatus = ?
            WHERE BatchID = ?
        """,
        (
            new_status,
            batch_id
        ))

        conn.commit()


    return {
        "message": "Batch status updated successfully."
    }



# =====================================================
# Quality Tests
# =====================================================

def record_quality_test(
    batch_id,
    test_type,
    test_result,
    qa_employee_id,
    remarks
):

    with get_connection() as conn:

        cursor = conn.execute("""
            INSERT INTO Quality_Test
            (
                BatchID,
                TestType,
                TestResult,
                QAEmployeeID,
                Remarks
            )
            VALUES (?, ?, ?, ?, ?)
        """,
        (
            batch_id,
            test_type,
            test_result,
            qa_employee_id,
            remarks
        ))

        conn.commit()


        return {
            "TestID": cursor.lastrowid,
            "message": "Quality test recorded successfully."
        }



def list_quality_tests():

    with get_connection() as conn:

        cursor = conn.execute("""
            SELECT *
            FROM Quality_Test
            ORDER BY TestDate DESC
        """)

        return [
            dict(row)
            for row in cursor.fetchall()
        ]



# =====================================================
# Product Recall
# =====================================================

def create_product_recall(
    batch_id,
    recall_reason,
    authorized_manager_id
):

    with get_connection() as conn:

        cursor = conn.execute("""
            INSERT INTO Product_Recall
            (
                BatchID,
                RecallReason,
                AuthorizedManagerID
            )
            VALUES (?, ?, ?)
        """,
        (
            batch_id,
            recall_reason,
            authorized_manager_id
        ))

        conn.commit()


        return {
            "RecallID": cursor.lastrowid,
            "message": "Recall created successfully."
        }



def list_recalls():

    with get_connection() as conn:

        cursor = conn.execute("""
            SELECT *
            FROM Product_Recall
            ORDER BY RecallDate DESC
        """)

        return [
            dict(row)
            for row in cursor.fetchall()
        ]



# =====================================================
# Employees
# =====================================================

def get_employee(employee_id):

    with get_connection() as conn:

        cursor = conn.execute("""
            SELECT *
            FROM Employee
            WHERE EmployeeID = ?
        """,
        (employee_id,))

        row = cursor.fetchone()

        return dict(row) if row else None
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "vellora.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# Medicines
# =====================================================

def get_all_medicines():
    conn = get_connection()

    cursor = conn.execute("""
        SELECT *
        FROM Medicine
        ORDER BY MedicineName
    """)

    medicines = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return medicines


def get_medicine_by_id(medicine_id):
    conn = get_connection()

    cursor = conn.execute("""
        SELECT *
        FROM Medicine
        WHERE MedicineID = ?
    """, (medicine_id,))

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


# =====================================================
# Production Orders
# =====================================================

def create_production_order(
    medicine_id,
    supplier_id,
    planned_quantity,
    responsible_employee_id
):
    conn = get_connection()

    cursor = conn.execute("""
        INSERT INTO Production_Order
        (
            MedicineID,
            SupplierID,
            PlannedQuantity,
            ResponsibleEmployeeID
        )
        VALUES (?, ?, ?, ?)
    """, (
        medicine_id,
        supplier_id,
        planned_quantity,
        responsible_employee_id
    ))

    conn.commit()

    order_id = cursor.lastrowid

    conn.close()

    return {
        "ProductionOrderID": order_id,
        "message": "Production order created successfully."
    }


# =====================================================
# Manufacturing Batches
# =====================================================

def list_batches():
    conn = get_connection()

    cursor = conn.execute("""
        SELECT *
        FROM Manufacturing_Batch
        ORDER BY BatchID DESC
    """)

    batches = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return batches


def update_batch_status(batch_id, new_status):
    conn = get_connection()

    conn.execute("""
        UPDATE Manufacturing_Batch
        SET BatchStatus = ?
        WHERE BatchID = ?
    """, (
        new_status,
        batch_id
    ))

    conn.commit()
    conn.close()

    return {
        "message": "Batch status updated successfully."
    }


# =====================================================
# Quality Tests
# =====================================================

def record_quality_test(
    batch_id,
    test_type,
    test_result,
    qa_employee_id,
    remarks
):
    conn = get_connection()

    cursor = conn.execute("""
        INSERT INTO Quality_Test
        (
            BatchID,
            TestType,
            TestResult,
            QAEmployeeID,
            Remarks
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        batch_id,
        test_type,
        test_result,
        qa_employee_id,
        remarks
    ))

    conn.commit()

    test_id = cursor.lastrowid

    conn.close()

    return {
        "TestID": test_id,
        "message": "Quality test recorded successfully."
    }


def list_quality_tests():
    conn = get_connection()

    cursor = conn.execute("""
        SELECT *
        FROM Quality_Test
        ORDER BY TestDate DESC
    """)

    tests = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return tests


# =====================================================
# Product Recalls
# =====================================================

def create_product_recall(
    batch_id,
    recall_reason,
    authorized_manager_id
):
    conn = get_connection()

    cursor = conn.execute("""
        INSERT INTO Product_Recall
        (
            BatchID,
            RecallReason,
            AuthorizedManagerID
        )
        VALUES (?, ?, ?)
    """, (
        batch_id,
        recall_reason,
        authorized_manager_id
    ))

    conn.commit()

    recall_id = cursor.lastrowid

    conn.close()

    return {
        "RecallID": recall_id,
        "message": "Recall created successfully."
    }


def list_recalls():
    conn = get_connection()

    cursor = conn.execute("""
        SELECT *
        FROM Product_Recall
        ORDER BY RecallDate DESC
    """)

    recalls = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return recalls


# =====================================================
# Employees
# =====================================================

def get_employee(employee_id):
    conn = get_connection()

    cursor = conn.execute("""
        SELECT *
        FROM Employee
        WHERE EmployeeID = ?
    """, (employee_id,))

    row = cursor.fetchone()

    conn.close()

    return dict(row) if row else None