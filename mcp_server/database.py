"""
mcp_server/database.py

FIX (Extending & Correcting Prior System):
This file replaces TWO divergent copies that used to exist:
  - one pointed at db/vellora_therapeutics.db and used
    `with get_connection() as conn:` (context manager, connection auto-closed
    even on exception)
  - one pointed at db/vellora.db and used manual conn.close() everywhere

Having both in the repo meant agents were silently split across two
different database files -- a batch created through one code path was
invisible to code importing the other file. That's fixed by deleting one
entirely and keeping only this file, which:
  1. Points at the single real database: db/vellora_therapeutics.db
  2. Uses the context-manager connection pattern throughout (safer --
     no risk of a leaked/open connection if a query raises)
  3. Includes get_batch_details() and get_quality_tests_for_batch(),
     which previously only existed in the vellora.db copy and are required
     by the new state_graph/batch_release_graph.py

Action for your repo: delete the other database.py entirely, replace it
with this one, and grep your codebase for `from .database import` /
`from mcp_server.database import` to make sure nothing still points at the
old vellora.db file or a function signature that no longer matches.
"""

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
        return [dict(row) for row in cursor.fetchall()]


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


def get_batch_details(batch_id):
    """
    Ported from the vellora.db copy of database.py, where this previously
    only existed. Required by state_graph/batch_release_graph.py to read
    a batch's medicine info (strength, dosage form) alongside its status.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                b.BatchID,
                b.ProductionOrderID,
                b.MedicineID,
                m.MedicineName,
                m.ActiveIngredient,
                m.DosageForm,
                m.Strength,
                b.ManufacturingDate,
                b.ExpiryDate,
                b.BatchStatus,
                b.CurrentLocation
            FROM Manufacturing_Batch b
            JOIN Medicine m
                ON b.MedicineID = m.MedicineID
            WHERE b.BatchID = ?
        """, (batch_id,))

        row = cursor.fetchone()
        return dict(row) if row else None


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
        return [dict(row) for row in cursor.fetchall()]


def get_quality_tests_for_batch(batch_id):
    """
    Ported from the vellora.db copy of database.py, where this previously
    only existed. Required by state_graph/batch_release_graph.py's
    await_next_test node, which needs per-batch results, not the global list.
    """
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT
                TestID,
                BatchID,
                TestType,
                TestResult,
                TestDate,
                QAEmployeeID,
                Remarks
            FROM Quality_Test
            WHERE BatchID = ?
            ORDER BY TestDate DESC
        """, (batch_id,))
        return [dict(row) for row in cursor.fetchall()]


# =====================================================
# Product Recalls
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
        return [dict(row) for row in cursor.fetchall()]


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


def employee_exists(employee_id) -> bool:
    """Small helper backing the normalized validate_exists calls in tools.py."""
    return get_employee(employee_id) is not None